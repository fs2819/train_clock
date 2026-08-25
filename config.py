"""Configuration for the analog clock subway time service."""

# MTA GTFS-Realtime feed URL for 1/2/3/4/5/6/7 trains
FEED_URL = "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs"

# Station: 125th St on the 1 train, southbound (downtown)
STATION_ID = "116S"
STATION_NAME = "125th St"
ROUTE_ID = "1"

# How often to recompute and move the hands (seconds)
POLL_INTERVAL_SECONDS = 10

# Cache duration — don't re-fetch from the MTA feed if data is newer than this
# (seconds). Between fetches, hand positions still update from cached arrival
# timestamps, so they keep counting down accurately.
CACHE_TTL_SECONDS = 30

# Number of clock hands (show the N soonest trains)
NUM_HANDS = 3

# ---------------------------------------------------------------------------
# Hardware: stepper motors + hall-effect homing sensors
# ---------------------------------------------------------------------------
# Set to False to keep the old log-only behaviour (e.g. when developing on a
# laptop with no GPIO). On the Pi, set to True.
MOTORS_ENABLED = True

# Real clock-face mapping: a full 360° revolution is 60 minutes, exactly like a
# normal analog clock's minute hand. A train `m` minutes away points where the
# minute hand would sit at `m` past the hour — 0 min = 12 o'clock (home),
# 15 = 3 o'clock, 30 = 6, 45 = 9.
MINUTES_PER_REV = 60

# Trains further out than this are pegged here so a hand never reaches 60 (which
# would collide with the 0-min / "now" position at 12 o'clock). 55 min points at
# 11 o'clock.
CLOCK_MAX_MINUTES = 55

# Where a hand parks when there is no train for it (downtown service skipping or
# suspended at this stop, or simply no prediction). 90° = 3 o'clock. All three
# hands at 3 o'clock = no downtown 1 trains stopping at 125th St.
NO_SERVICE_ANGLE = 90.0

# 28BYJ-48 geometry: half-step mode, gear-reduced output shaft.
# Measured empirically on this hardware: 4096 steps produced only 180° of
# travel, so a full output revolution is 8192 half-steps. (The gearbox ratio
# works out higher than the often-quoted 4096; this clock uses the measured
# value.) Homing is sensor-based so it's unaffected, but every angle->steps
# conversion depends on this being right.
STEPS_PER_REV = 8192

# GPIO pins (BCM numbering) for each hand.
#   "in_pins": the ULN2003 IN1..IN4 inputs, in order.
#   "hall_pin": the hall sensor signal pin for that hand's home position.
# These are sane defaults that avoid the I2C/SPI/UART pins; change to match
# however you actually wire the breadboard.
# "home_offset_steps": after homing centers on the magnet zone, nudge the hand
# this many half-steps before calling it 0, to land on true 12 o'clock. Positive
# = clockwise/forward. ~22.8 steps per degree (8192 steps / 360°). Tune by eye.
HANDS = [
    {  # Hand 1 — soonest train — BOTTOM hand
        "in_pins": (6, 13, 19, 26),
        "hall_pin": 4,
        "home_offset_steps": 0,
    },
    {  # Hand 2 — second train — MIDDLE hand
        "in_pins": (12, 16, 20, 21),
        "hall_pin": 5,
        "home_offset_steps": 0,
    },
    {  # Hand 3 — third train — TOP hand.
        "in_pins": (17, 27, 22, 23),
        "hall_pin": 24,
        # Re-tuned 2026-08-16 for the new magnets (measured zone: ~490 steps).
        # Tuning history: with no offset it parked one minute-mark PAST 12
        # (toward 1), so -137 (1/60th of a rev); that overshot toward 11, so
        # we gave back a third -> -91. The old +140 belonged to the previous
        # two-magnet arrangement and no longer applies.
        "home_offset_steps": -91,
    },
]

# Seconds between issued half-steps — the speed limit. 1.5 ms is ~667
# half-steps/s, so a full revolution takes ~12.3 s.
#
# This is the main drift knob. The 28BYJ-48 runs open-loop with no ramp, so if
# the rotor can't keep up with the commanded field it slips poles silently and
# the hand is offset until its next home. Raised from 1.2 ms on 2026-08-25
# after the first overnight run left all three hands well out of place; slower
# = more torque margin. Room to go to ~2.0 ms if drift persists. If a motor
# buzzes without turning, it's still too fast.
STEP_DELAY_SECONDS = 0.0015

# Re-home a hand each time its train arrives, before it swings round to pick up
# its next train. Half-step slip is invisible on any single move but accumulates
# over hours, so a hand homed only at startup is well out of place by morning.
# The hand is idle and about to travel the long way round anyway, so the extra
# sweep costs ~10 s and nothing visually. Set False to go back to homing only at
# startup (e.g. when timing something and you want no surprise laps).
REHOME_AFTER_ARRIVAL = True

# Homing: hall sensor reads this logic level when the magnet is in front of it.
# Verified on the bench: these modules read HIGH (1) when a magnet is present
# and idle LOW (0) — i.e. active-HIGH.
HALL_ACTIVE_LEVEL = 1

# Safety stop for homing: if we sweep this many steps without seeing the
# sensor, give up rather than grind the gears forever.
HOMING_MAX_STEPS = STEPS_PER_REV + STEPS_PER_REV // 4

# Logging
LOG_LEVEL = "INFO"
