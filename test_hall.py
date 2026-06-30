"""Live readout of a hall-effect sensor — run this to confirm homing will work.

Prints the sensor's raw logic level continuously. Wave the magnet past the
sensor and watch the value change. Use this to discover whether your sensor is
active-LOW or active-HIGH, then set HALL_ACTIVE_LEVEL in config.py to whichever
level appears WHEN THE MAGNET IS PRESENT.

For a typical A3144 module the line sits at 1 (HIGH) with no magnet and drops to
0 (LOW) when a magnet is near -> HALL_ACTIVE_LEVEL = 0.

Usage (on the Pi, inside the venv):
    .venv/bin/python test_hall.py        # watches hand 1's sensor
    .venv/bin/python test_hall.py 2      # watches hand 2's sensor
"""

import sys
import time

from gpiozero import DigitalInputDevice

from config import HANDS


def main():
    hand_num = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    pin = HANDS[hand_num - 1]["hall_pin"]
    print(f"Watching hand {hand_num} hall sensor on GPIO{pin}. Ctrl+C to stop.")
    print("Wave a magnet past the sensor; the level should change.\n")

    hall = DigitalInputDevice(pin, pull_up=True)
    try:
        last = None
        while True:
            level = 1 if hall.value else 0
            if level != last:
                state = "magnet?" if level == 0 else "no magnet?"
                print(f"GPIO{pin} = {level}  ({state})")
                last = level
            time.sleep(0.05)
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        hall.close()


if __name__ == "__main__":
    main()
