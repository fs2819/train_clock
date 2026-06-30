"""Live readout of ALL THREE hall sensors at once, refreshing in place.

Wave a magnet in front of each sensor and watch its column flip between
MAGNET and --- . Confirms each sensor works and which hand it belongs to.

Run ON THE PI:
    .venv/bin/python test_hall_live.py
Ctrl+C to stop.
"""

import time

from gpiozero import DigitalInputDevice

from config import HALL_ACTIVE_LEVEL, HANDS

NAMES = ["bottom", "middle", "top"]


def main():
    labels = [f"{NAMES[i]}(GPIO{c['hall_pin']})" for i, c in enumerate(HANDS)]
    sensors = [DigitalInputDevice(c["hall_pin"], pull_up=True) for c in HANDS]

    print("Live hall sensors — wave a magnet at each. Ctrl+C to stop.\n")
    try:
        while True:
            cells = []
            for label, s in zip(labels, sensors):
                level = 1 if s.value else 0
                state = "MAGNET" if level == HALL_ACTIVE_LEVEL else " ---  "
                cells.append(f"{label}: {state}")
            print("\r" + "   ".join(cells) + "   ", end="", flush=True)
            time.sleep(0.05)
    except KeyboardInterrupt:
        print()
    finally:
        for s in sensors:
            s.close()


if __name__ == "__main__":
    main()
