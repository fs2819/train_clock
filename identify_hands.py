"""Park each configured hand at a distinct, unmistakable clock position.

Homes all three, then sends:
    hand1 -> 12 o'clock   (0 deg)
    hand2 ->  3 o'clock  (90 deg)
    hand3 ->  6 o'clock (180 deg)

Then look at the clock and report which PHYSICAL hand (bottom / middle / top)
is sitting at 12, at 3, and at 6. That pins down both the hand<->motor mapping
and whether the angle scaling is right (a hand told 90 deg should land exactly
on 3 o'clock, not near it).
"""

import logging

from config import (
    HALL_ACTIVE_LEVEL,
    HANDS,
    HOMING_MAX_STEPS,
    STEP_DELAY_SECONDS,
    STEPS_PER_REV,
)
from stepper import StepperHand

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")

TARGETS = [(0.0, "12 o'clock"), (90.0, "3 o'clock"), (180.0, "6 o'clock")]

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

try:
    for hand in hands:
        hand.home()

    print("\nAll homed. Now sending each hand to its marker:\n", flush=True)
    for i, (hand, (angle, label)) in enumerate(zip(hands, TARGETS)):
        print(f"  config hand{i + 1} (motor pins {HANDS[i]['in_pins']}) -> {label}", flush=True)
        hand.move_to_angle(angle)

    print("\nDone. Report which physical hand is at 12, at 3, and at 6.", flush=True)
finally:
    for hand in hands:
        hand.close()
