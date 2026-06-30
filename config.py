"""Configuration for the analog clock subway time service."""

# MTA GTFS-Realtime feed URL for 1/2/3/4/5/6/7 trains
FEED_URL = "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs"

# Station: 125th St on the 1 train, southbound (downtown)
STATION_ID = "116S"
STATION_NAME = "125th St"
ROUTE_ID = "1"

# How often to poll the MTA feed (seconds)
POLL_INTERVAL_SECONDS = 15

# Cache duration — don't re-fetch if data is newer than this (seconds)
CACHE_TTL_SECONDS = 60

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
    {  # Hand 3 — third train — TOP hand. Magnet zone widened by a 2nd magnet,
       # so its center sits ~a few° toward 11 o'clock; nudge clockwise to 12.
        "in_pins": (17, 27, 22, 23),
        "hall_pin": 24,
        "home_offset_steps": 140,  # ~6.2° at 8192 steps/rev (~22.8 steps/°)
    },
]

# Seconds between issued half-steps. The 28BYJ-48 stalls if driven too fast;
# ~1.2 ms is a safe, reasonably quick speed. Increase if a motor buzzes/stalls.
STEP_DELAY_SECONDS = 0.0012

# Homing: hall sensor reads this logic level when the magnet is in front of it.
# Verified on the bench: these modules read HIGH (1) when a magnet is present
# and idle LOW (0) — i.e. active-HIGH.
HALL_ACTIVE_LEVEL = 1

# Safety stop for homing: if we sweep this many steps without seeing the
# sensor, give up rather than grind the gears forever.
HOMING_MAX_STEPS = STEPS_PER_REV + STEPS_PER_REV // 4

# Logging
LOG_LEVEL = "INFO"
