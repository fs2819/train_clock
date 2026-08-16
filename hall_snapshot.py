"""One-shot read of all three hall sensors. No motion — safe to run anytime."""

from gpiozero import DigitalInputDevice

from config import HALL_ACTIVE_LEVEL, HANDS

NAMES = ["bottom", "middle", "top"]

print(f"HALL_ACTIVE_LEVEL = {HALL_ACTIVE_LEVEL} (level meaning 'magnet present')\n")
for i, cfg in enumerate(HANDS):
    dev = DigitalInputDevice(cfg["hall_pin"], pull_up=True)
    level = 1 if dev.value else 0
    state = "MAGNET" if level == HALL_ACTIVE_LEVEL else "---"
    print(f"  hand{i + 1} ({NAMES[i]:6s}) GPIO{cfg['hall_pin']:<2d}  level={level}  {state}")
    dev.close()
