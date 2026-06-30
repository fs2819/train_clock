"""Clock controller — maps train arrival minutes to physical hand positions.

When MOTORS_ENABLED is True, this drives three 28BYJ-48 steppers (one per hand)
to point at the arrival time of each of the next three trains. When False, it
just logs what each hand would do, so the rest of the app can be developed and
run anywhere.

Mapping: a train `m` minutes away points at angle (m / CLOCK_MAX_MINUTES) * 360,
measured clockwise from the home position (12 o'clock = 0 minutes). Trains
beyond CLOCK_MAX_MINUTES are pegged at the max. Hands with no data park at home.

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
    STEP_DELAY_SECONDS,
    STEPS_PER_REV,
)

logger = logging.getLogger(__name__)

# Built lazily on first use so importing this module never touches GPIO.
_hands = None


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


def update_clock_hands(train_minutes: list[float | None]) -> None:
    """Set all three clock hands to display the next 3 train arrival times.

    Args:
        train_minutes: List of NUM_HANDS values — minutes until each of the
            soonest trains. None entries mean no train for that hand (the hand
            parks at the no-service position; all three there = no downtown
            trains stopping at this station).
    """
    if not MOTORS_ENABLED:
        _log_only(train_minutes)
        return

    hands = _get_hands()
    for hand, minutes in zip(hands, train_minutes):
        if minutes is None:
            logger.info(
                "[%s] no train — parking at no-service (%.0f°)",
                hand.name,
                NO_SERVICE_ANGLE,
            )
            hand.move_to_angle(NO_SERVICE_ANGLE)
            continue

        angle = _angle_for_minutes(minutes)
        if minutes > CLOCK_MAX_MINUTES:
            logger.info(
                "[%s] %.1f min beyond %d-min range — pegging at max",
                hand.name,
                minutes,
                CLOCK_MAX_MINUTES,
            )
        else:
            logger.info("[%s] %.1f min -> %.1f°", hand.name, minutes, angle)
        hand.move_to_angle(angle)


def _log_only(train_minutes: list[float | None]) -> None:
    for i, minutes in enumerate(train_minutes):
        hand = i + 1
        if minutes is None:
            logger.info(
                "Hand %d: no train — no-service position (%.0f°)",
                hand,
                NO_SERVICE_ANGLE,
            )
            continue
        angle = _angle_for_minutes(minutes)
        if minutes > CLOCK_MAX_MINUTES:
            logger.info(
                "Hand %d: %.1f min (beyond %d-min range, would peg at max)",
                hand,
                minutes,
                CLOCK_MAX_MINUTES,
            )
        else:
            logger.info("Hand %d: %.1f min -> %.1f°", hand, minutes, angle)


def shutdown() -> None:
    """Release coils and free GPIO. Safe to call even if motors were never set up."""
    global _hands
    if _hands is None:
        return
    for hand in _hands:
        try:
            hand.close()
        except Exception:
            logger.exception("[%s] error during close", hand.name)
    _hands = None
