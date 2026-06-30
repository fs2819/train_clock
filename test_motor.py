"""Bench test for ONE stepper motor — run this first to confirm wiring.

It spins the selected hand's motor one full revolution forward, then one full
revolution back, then releases the coils. The output shaft should rotate ~360°
each way. If it just buzzes or vibrates without turning, a coil wire order is
wrong (swap the IN-pin order in config.py) or STEP_DELAY_SECONDS is too small.

Usage (on the Pi, inside the venv):
    .venv/bin/python test_motor.py        # tests hand 1
    .venv/bin/python test_motor.py 2      # tests hand 2
    .venv/bin/python test_motor.py 3      # tests hand 3
"""

import sys

from config import (
    HANDS,
    HALL_ACTIVE_LEVEL,
    HOMING_MAX_STEPS,
    STEP_DELAY_SECONDS,
    STEPS_PER_REV,
)
from stepper import StepperHand


def main():
    hand_num = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    cfg = HANDS[hand_num - 1]
    print(f"Testing hand {hand_num} on IN pins {cfg['in_pins']}")

    hand = StepperHand(
        in_pins=cfg["in_pins"],
        hall_pin=cfg["hall_pin"],
        steps_per_rev=STEPS_PER_REV,
        step_delay=STEP_DELAY_SECONDS,
        hall_active_level=HALL_ACTIVE_LEVEL,
        homing_max_steps=HOMING_MAX_STEPS,
        name=f"hand{hand_num}",
    )

    try:
        print("Forward one full revolution...")
        hand.step_many(STEPS_PER_REV)
        print("Reverse one full revolution...")
        hand.step_many(-STEPS_PER_REV)
        print("Done. Coils released.")
    finally:
        hand.close()


if __name__ == "__main__":
    main()
