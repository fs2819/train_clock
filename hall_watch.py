"""Watch all three hall sensors for N seconds, logging every state change.

Unlike test_hall_live.py (which redraws one line in place and is unreadable when
captured non-interactively), this prints a timestamped line per transition and
finishes with a summary of which sensors ever saw a magnet.

Usage on the Pi:
    .venv/bin/python hall_watch.py [seconds]     # default 30
"""

import sys
import time

from gpiozero import DigitalInputDevice

from config import HALL_ACTIVE_LEVEL, HANDS

NAMES = ["bottom", "middle", "top"]
duration = float(sys.argv[1]) if len(sys.argv) > 1 else 30.0

sensors = [DigitalInputDevice(c["hall_pin"], pull_up=True) for c in HANDS]
labels = [f"hand{i + 1} ({NAMES[i]:6s}) GPIO{c['hall_pin']:<2d}" for i, c in enumerate(HANDS)]


def triggered(dev):
    return (1 if dev.value else 0) == HALL_ACTIVE_LEVEL


state = [triggered(s) for s in sensors]
ever = list(state)

print(f"Watching for {duration:.0f}s — wave a magnet at each sensor.\n")
print("Initial state:")
for lab, st in zip(labels, state):
    print(f"  {lab}  {'MAGNET' if st else '---'}")
print("\nTransitions:")

start = time.monotonic()
try:
    while time.monotonic() - start < duration:
        for i, dev in enumerate(sensors):
            now = triggered(dev)
            if now != state[i]:
                elapsed = time.monotonic() - start
                print(
                    f"  [{elapsed:5.1f}s] {labels[i]}  ->  {'MAGNET' if now else '---'}",
                    flush=True,
                )
                state[i] = now
                if now:
                    ever[i] = True
        time.sleep(0.01)
finally:
    print("\n================ SUMMARY ================")
    for lab, saw in zip(labels, ever):
        print(f"  {lab}  {'saw a magnet' if saw else 'NEVER triggered'}")
    for s in sensors:
        s.close()
