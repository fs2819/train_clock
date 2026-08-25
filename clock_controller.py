"""Clock controller — maps train arrival minutes to physical hand positions.

When MOTORS_ENABLED is True, this drives three 28BYJ-48 steppers (one per hand)
to point at the arrival time of each of the next three trains. When False, it
just logs what each hand would do, so the rest of the app can be developed and
run anywhere.

Mapping: a train `m` minutes away points at angle (m / CLOCK_MAX_MINUTES) * 360,
measured clockwise from the home position (12 o'clock = 0 minutes). Trains
beyond CLOCK_MAX_MINUTES are pegged at the max. Hands with no data park at home.

Hand assignment: each hand follows ONE specific train (tracked by GTFS trip ID)
for that train's whole approach, rather than being pinned to "soonest" /
"second" / "third". When a hand's train arrives, that hand takes the soonest
train no other hand is showing — which, since the other hands are holding the
nearer trains, is the furthest-out train on the dial. So a hand that reaches 12
o'clock recycles to the back of the queue and the other hands keep sweeping
undisturbed, instead of all three shuffling up a place on every arrival.

Direction: a hand always travels CLOCKWISE when it switches trains, even though
that means crossing most of the dial. Combined with the countdown mapping (which
already sweeps a hand clockwise as its train approaches), each hand therefore
only ever advances clockwise, like a real clock.

Drift: half-step slip is invisible on any one move but accumulates over hours,
so a hand homed only at startup is noticeably off by morning. Each hand
therefore RE-HOMES at the one moment it is free — after its train has arrived,
before it swings round to its next one — correcting that hand without
disturbing the two still tracking their own trains. See REHOME_AFTER_ARRIVAL.

Movement is sequential (one motor at a time). With all three boards powered
from the Pi's 5V pin this keeps peak current to a single motor (~250 mA),
avoiding brownouts. If you later add an external 5V supply you can parallelise.
"""

import logging

from config import (
    CLOCK_MAX_MINUTES,
    HANDS,
    HALL_ACTIVE_LEVEL,
    HOMING_MAX_STEPS,
    MINUTES_PER_REV,
    MOTORS_ENABLED,
    NO_SERVICE_ANGLE,
    NUM_HANDS,
    REHOME_AFTER_ARRIVAL,
    STEP_DELAY_SECONDS,
    STEPS_PER_REV,
)
from subway_times import UpcomingTrain

logger = logging.getLogger(__name__)

# Built lazily on first use so importing this module never touches GPIO.
_hands = None

# Which train (GTFS trip ID) each hand is currently following. None = no train.
# Persisted across polls; this is what lets a hand stay with its own train.
_hand_trip_ids: list[str | None] = [None] * NUM_HANDS


def _get_hands():
    """Construct and home the three steppers once, on first call."""
    global _hands
    if _hands is not None:
        return _hands

    from stepper import StepperHand

    hands = [
        StepperHand(
            in_pins=cfg["in_pins"],
            hall_pin=cfg["hall_pin"],
            steps_per_rev=STEPS_PER_REV,
            step_delay=STEP_DELAY_SECONDS,
            hall_active_level=HALL_ACTIVE_LEVEL,
            homing_max_steps=HOMING_MAX_STEPS,
            name=f"hand{i + 1}",
            home_offset_steps=cfg.get("home_offset_steps", 0),
        )
        for i, cfg in enumerate(HANDS)
    ]

    # Home one hand at a time. With all boards on the Pi's 5V rail this keeps
    # peak draw to a single motor; it also makes a stall obvious (you see which
    # hand's homing line never prints its "home found" follow-up).
    logger.info("Homing %d hands sequentially...", len(hands))
    for hand in hands:
        hand.home()
    logger.info("All hands homed.")

    _hands = hands
    return _hands


def _rehome(hand) -> None:
    """Re-find 12 o'clock for one hand, mid-run.

    Called when a hand's train has arrived and it is about to travel the long
    way round to its next train. ``home()`` sweeps forward, so this keeps the
    clockwise-only rule; the cost is up to one extra lap (~10 s) that the hand
    was largely going to make anyway.

    A failure here is logged, not raised: the hand keeps its old (drifted)
    position and the clock carries on, rather than the whole poll dying on one
    bad sensor read.
    """
    logger.info("[%s] train arrived — re-homing before its next train", hand.name)
    try:
        hand.home()
    except Exception:
        logger.exception(
            "[%s] re-home failed — carrying on from last known position", hand.name
        )


def _assign_trains(upcoming: list[UpcomingTrain]) -> list[UpcomingTrain | None]:
    """Work out which train each hand should show, and remember it.

    Hands keep the train they are already following for as long as it is still
    in the feed. Any hand whose train has gone (arrived, or cancelled) takes the
    soonest train nobody else is showing.

    Returns NUM_HANDS entries, each an UpcomingTrain or None when there simply
    aren't enough trains to go round.
    """
    global _hand_trip_ids

    by_id = {t.trip_id: t for t in upcoming}

    # A hand whose train is still coming keeps it.
    assigned: list[UpcomingTrain | None] = [
        by_id.get(trip_id) if trip_id is not None else None
        for trip_id in _hand_trip_ids
    ]

    # Trains no hand is showing, soonest first.
    claimed = {t.trip_id for t in assigned if t is not None}
    unclaimed = [t for t in upcoming if t.trip_id not in claimed]

    # Each free hand picks up the soonest of those.
    for i, current in enumerate(assigned):
        if current is None and unclaimed:
            assigned[i] = unclaimed.pop(0)

    _hand_trip_ids = [t.trip_id if t is not None else None for t in assigned]
    return assigned


def _angle_for_minutes(minutes: float) -> float:
    """Clock-face angle (degrees) for a train this many minutes away.

    Countdown style: 12 o'clock is the train arriving NOW, and a hand sits
    `minutes` BEFORE 12 — i.e. counterclockwise from the top. As the train
    approaches, the hand sweeps clockwise up toward 12.

      0 min  -> 12 o'clock (0°/360°)
      1 min  -> 59 on the dial (354°)
      15 min -> 9 o'clock (270°)
      30 min -> 6 o'clock (180°)
      55 min -> 1 o'clock (30°)

    Minutes are capped at CLOCK_MAX_MINUTES so a far-out train never wraps
    past 12 and collides with the "arriving now" position. The returned angle
    may be negative; callers take it mod 360.
    """
    capped = min(minutes, CLOCK_MAX_MINUTES)
    return -capped / MINUTES_PER_REV * 360.0


def update_clock_hands(upcoming: list[UpcomingTrain]) -> None:
    """Point each hand at the train it is following.

    Args:
        upcoming: every known upcoming arrival, soonest first. Pass more than
            NUM_HANDS of them — a hand whose train has just arrived needs one
            further down the queue to pick up.
    """
    if not MOTORS_ENABLED:
        _log_only(upcoming)
        return

    # Home before mutating any assignment state, so a homing failure leaves
    # the previous assignment intact for the next attempt.
    hands = _get_hands()

    previous = list(_hand_trip_ids)
    assigned = _assign_trains(upcoming)

    for i, (hand, train) in enumerate(zip(hands, assigned)):
        # Only force the long way round when this hand swaps to a different
        # train. The first placement after homing takes the short path, and
        # so does normal minute-by-minute tracking of the same train.
        switched = previous[i] is not None and _hand_trip_ids[i] != previous[i]

        # Its train has left the dial and this hand is idle: the one moment in
        # normal operation when it is safe to re-home and shed accumulated
        # drift. Leaves the hand at a known 0, so the move below is exact.
        if switched and REHOME_AFTER_ARRIVAL:
            _rehome(hand)

        if train is None:
            logger.info(
                "[%s] no train — parking at no-service (%.0f°)",
                hand.name,
                NO_SERVICE_ANGLE,
            )
            hand.move_to_angle(NO_SERVICE_ANGLE, forward_only=switched)
            continue

        angle = _angle_for_minutes(train.minutes)
        if switched:
            logger.info(
                "[%s] train arrived — now tracking %s, %.1f min -> %.1f° (clockwise)",
                hand.name,
                train.trip_id,
                train.minutes,
                angle,
            )
        elif train.minutes > CLOCK_MAX_MINUTES:
            logger.info(
                "[%s] %.1f min beyond %d-min range — pegging at max",
                hand.name,
                train.minutes,
                CLOCK_MAX_MINUTES,
            )
        else:
            logger.info("[%s] %.1f min -> %.1f°", hand.name, train.minutes, angle)

        hand.move_to_angle(angle, forward_only=switched)


def _log_only(upcoming: list[UpcomingTrain]) -> None:
    previous = list(_hand_trip_ids)
    assigned = _assign_trains(upcoming)

    for i, train in enumerate(assigned):
        hand = i + 1
        switched = previous[i] is not None and _hand_trip_ids[i] != previous[i]

        if switched and REHOME_AFTER_ARRIVAL:
            logger.info("Hand %d: train arrived — would re-home before its next train", hand)

        if train is None:
            logger.info(
                "Hand %d: no train — no-service position (%.0f°)",
                hand,
                NO_SERVICE_ANGLE,
            )
            continue

        angle = _angle_for_minutes(train.minutes)
        if switched:
            logger.info(
                "Hand %d: train arrived — now tracking %s, %.1f min -> %.1f° (clockwise)",
                hand,
                train.trip_id,
                train.minutes,
                angle,
            )
        elif train.minutes > CLOCK_MAX_MINUTES:
            logger.info(
                "Hand %d: %.1f min (beyond %d-min range, would peg at max)",
                hand,
                train.minutes,
                CLOCK_MAX_MINUTES,
            )
        else:
            logger.info("Hand %d: %.1f min -> %.1f°", hand, train.minutes, angle)


def shutdown() -> None:
    """Release coils and free GPIO. Safe to call even if motors were never set up."""
    global _hands, _hand_trip_ids
    _hand_trip_ids = [None] * NUM_HANDS
    if _hands is None:
        return
    for hand in _hands:
        try:
            hand.close()
        except Exception:
            logger.exception("[%s] error during close", hand.name)
    _hands = None
