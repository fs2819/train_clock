"""Home the clock hands and report magnet-zone widths. No MTA polling.

Builds the hands exactly the way clock_controller._get_hands() does, homes them
one at a time, and keeps going if one fails so a single bad sensor doesn't hide
the state of the other two.

Usage on the Pi:
    .venv/bin/python home_test.py          # all three
    .venv/bin/python home_test.py 1        # just hand 1
    .venv/bin/python home_test.py 1 3      # hands 1 and 3
"""

import logging
import sys

from config import (
    HALL_ACTIVE_LEVEL,
    HANDS,
    HOMING_MAX_STEPS,
    STEP_DELAY_SECONDS,
    STEPS_PER_REV,
)
from stepper import StepperHand

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)

NAMES = ["bottom", "middle", "top"]

wanted = [int(a) for a in sys.argv[1:]] or [1, 2, 3]

hands = []
for n in wanted:
    cfg = HANDS[n - 1]
    hands.append(
        (
            n,
            StepperHand(
                in_pins=cfg["in_pins"],
                hall_pin=cfg["hall_pin"],
                steps_per_rev=STEPS_PER_REV,
                step_delay=STEP_DELAY_SECONDS,
                hall_active_level=HALL_ACTIVE_LEVEL,
                homing_max_steps=HOMING_MAX_STEPS,
                name=f"hand{n}",
                home_offset_steps=cfg.get("home_offset_steps", 0),
            ),
        )
    )

results = []
try:
    for n, hand in hands:
        print(
            f"\n--- homing hand{n} ({NAMES[n - 1]}), "
            f"hall=GPIO{HANDS[n - 1]['hall_pin']}, offset={hand.home_offset_steps:+d} ---",
            flush=True,
        )
        try:
            hand.home()
            results.append((n, "OK"))
        except RuntimeError as exc:
            print(f"  FAILED: {exc}", flush=True)
            results.append((n, "FAILED"))

    print("\n================ SUMMARY ================", flush=True)
    for n, status in results:
        print(f"  hand{n} ({NAMES[n - 1]:6s}) {status}", flush=True)
finally:
    for _, hand in hands:
        hand.close()
