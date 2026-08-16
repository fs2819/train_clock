# Analog Subway Clock

An analog clock whose hands show the time until the next downtown 1 train arrives at 125th Street (NYC MTA). Runs on a Raspberry Pi Zero 2 W.

## How It Works

The software polls the MTA's public GTFS-Realtime feed every 15 seconds, parses the protobuf response, and extracts arrival predictions for the southbound 1 train at 125th St (GTFS stop `116S`). The minutes until arrival are mapped to positions on the clock face and driven by three independent stepper motors — one per hand, each following its own train (see *Hand assignment* below).

**Countdown mapping.** 12 o'clock represents a train arriving *now*. A hand for a train `m` minutes away sits `m` minutes *before* 12 — i.e. counterclockwise from the top, exactly like reading a normal clock backwards from the hour:

| Minutes to train | Hand position |
| --- | --- |
| 0 (arriving) | 12 o'clock |
| 1 | the "59" mark (just before 12) |
| 15 | 9 o'clock |
| 30 | 6 o'clock |
| 55 (capped) | 1 o'clock |

As a train approaches, its hand sweeps clockwise up toward 12. Trains beyond `CLOCK_MAX_MINUTES` (55) are pegged at the 1 o'clock cap so a far-out train never wraps past 12 and collides with the "arriving now" position.

**Each hand follows one train.** Hands are *not* pinned to "soonest / second /
third". A hand is handed a specific train (identified by its GTFS trip ID) and
tracks that same train all the way in, sweeping clockwise toward 12. When its
train arrives, that hand takes the soonest train no other hand is showing —
which, since the other two hands are holding the nearer trains, is the
furthest-out train on the dial. So the hand that just reached 12 recycles to
the back of the queue and the other two keep sweeping undisturbed, instead of
all three shuffling up a place on every arrival.

**Hands only ever turn clockwise.** The countdown mapping already sweeps a hand
clockwise as its train approaches, and when a hand switches trains it travels
clockwise to the new position too — the long way round the dial rather than
back-tracking. Over a day every hand rotates in one direction only, like a real
clock.

At startup all three hands home to 12 o'clock, then take the three soonest
trains by the shortest path (the clockwise-only rule applies to swapping
trains, not to first placement).

This is a Python translation of the [SubwayTimeService](../SubwayTimeService) Go project, stripped of AWS infrastructure (Lambda, DynamoDB, API Gateway) and adapted to run locally on the Pi.

## Project Structure

```
analog_clock/
  config.py             # Station, route, feed URL, polling, GPIO pins, geometry
  mta_feed.py           # Fetches + parses GTFS-Realtime protobuf from MTA
  subway_times.py       # Caching layer, computes minutes-to-arrival
  clock_controller.py   # Maps minutes -> hand angle, drives the 3 steppers
  stepper.py            # StepperHand: half-stepping, homing, position tracking
  main.py               # Entry point — poll loop
  requirements.txt      # Python dependencies
  # Hardware bring-up / diagnostics (run on the Pi):
  test_motor.py         # Spin one motor a full revolution each way
  test_hall.py          # Live readout of one hall sensor
  test_hall_live.py     # Live readout of all three hall sensors at once
```

When `MOTORS_ENABLED = False` (the default, for laptop development), `clock_controller`
just logs what each hand *would* do, so the whole app runs anywhere without GPIO.
Set it to `True` on the Pi to drive the motors.

## Setup (Local / Development)

```bash
# Install uv if you don't have it:
curl -LsSf https://astral.sh/uv/install.sh | sh

uv venv
source .venv/bin/activate
uv pip install -r requirements.txt
uv run main.py
```

No API key is needed — the MTA GTFS-Realtime endpoint is public.

## Deploying to Raspberry Pi Zero 2 W

### 1. OS Setup

Flash **Raspberry Pi OS Lite (64-bit)** onto a microSD card using [Raspberry Pi Imager](https://www.raspberrypi.com/software/). In the imager's settings:
- Enable SSH
- Set your Wi-Fi credentials
- Set a hostname (e.g., `subwayclock.local`)

### 2. SSH In and Install Dependencies

```bash
ssh pi@subwayclock.local

# Update system
sudo apt update && sudo apt upgrade -y

# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# Clone or copy your code to the Pi
# Option A: git clone
# Option B: scp -r analog_clock/ pi@subwayclock.local:~/analog_clock/

cd ~/analog_clock
uv venv
source .venv/bin/activate
uv pip install -r requirements.txt
```

### 3. Test It

```bash
uv run main.py
```

You should see log output like:
```
2026-06-29 23:38:30 [__main__] INFO: Analog subway clock starting
2026-06-29 23:38:30 [mta_feed] INFO: 1 train at 125th St arriving Mon Jun 29 23:48:25 EDT (9.8 min)
2026-06-29 23:38:30 [__main__] INFO: Next 3 trains (min): ['9.8', '21.0', '34.5']
```

With `MOTORS_ENABLED = True`, you'll also see the hands home on startup and then
each move to its train's position:
```
[clock_controller] INFO: Homing 3 hands sequentially...
[stepper] INFO: [hand1] home found (magnet zone 152 steps, centered, offset +0)
...
[clock_controller] INFO: [hand1] 9.8 min -> -58.8°
```

### 4. Run on Boot (systemd)

Create a service file:

```bash
sudo nano /etc/systemd/system/subwayclock.service
```

```ini
[Unit]
Description=Analog Subway Clock
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/analog_clock
ExecStart=/home/pi/analog_clock/.venv/bin/python main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable subwayclock
sudo systemctl start subwayclock

# Check logs:
journalctl -u subwayclock -f
```

## Hardware

Three **28BYJ-48** stepper motors (one per hand), each driven by a **ULN2003**
board, plus three hall-effect sensors for homing. Everything runs at 5V/3.3V
directly off the Pi — no external driver chips.

### GPIO wiring (BCM numbering)

Each ULN2003 board: `+` → 5V, `−` → GND, IN1–IN4 → four GPIOs.
Each hall sensor: VCC → **3.3V** (not 5V — keeps the signal pin within the
GPIO's safe range), GND → GND, OUT → one GPIO.

| Hand | Position | IN1 | IN2 | IN3 | IN4 | Hall OUT |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | bottom | GPIO6 | GPIO13 | GPIO19 | GPIO26 | GPIO4 |
| 2 | middle | GPIO12 | GPIO16 | GPIO20 | GPIO21 | GPIO5 |
| 3 | top | GPIO17 | GPIO27 | GPIO22 | GPIO23 | GPIO24 |

All pins are defined in `config.py` (the `HANDS` list) — change them there if you
rewire. Use the breadboard power rails to fan out 5V / 3.3V / GND, since the Pi
header doesn't have enough power pins for three boards plus three sensors. **All
grounds must be common.**

> **Power note.** All three boards share the Pi's 5V pin. To stay within budget,
> the firmware moves and homes **one motor at a time** (~250 mA peak). Don't
> drive all three simultaneously on this power setup, or the Pi can brown out.
> For simultaneous motion, feed the boards from an external 5V supply (grounds
> still tied to the Pi).

### Homing

Each hand carries a magnet; a fixed sensor in the top plate detects it at the
12 o'clock position. On startup `StepperHand.home()`:

1. Sweeps until it finds the magnet's **trigger zone** (an arc, not a point).
2. Measures the zone width and parks at its **center** — the most repeatable
   reference — then applies an optional per-hand `home_offset_steps` fudge to
   land exactly on 12. Budget is two full revolutions, so a wide zone or a
   worst-case start position can never run out.

`HALL_ACTIVE_LEVEL` in `config.py` is the level the sensors read with a magnet
present. These modules are **active-HIGH** (read 1 with a magnet, idle 0).

### Geometry / calibration

- `STEPS_PER_REV = 8192` — **measured**, not assumed. On this hardware, 4096
  half-steps produced only 180° of output rotation, so a full revolution is
  8192. Every minutes→angle conversion depends on this; homing is sensor-based
  and unaffected. (~22.8 steps per degree.)
- `home_offset_steps` (per hand in `HANDS`) nudges that hand clockwise after
  homing to correct a magnet that isn't exactly at 12. The top hand uses ~140;
  the others 0. Tune by eye.
- `MINUTES_PER_REV = 60`, `CLOCK_MAX_MINUTES = 55` — the countdown mapping (see
  *How It Works*).

### Bring-up procedure (on the Pi)

Stop the service first so it isn't holding the GPIO: `sudo systemctl stop subwayclock`.

```bash
.venv/bin/python test_motor.py 1      # spin each motor: 1, 2, 3
.venv/bin/python test_hall_live.py    # wave a magnet at each sensor, watch it flip
```

Then set `MOTORS_ENABLED = True` in `config.py`, run `.venv/bin/python main.py`
to watch it home and track trains, and finally `sudo systemctl start subwayclock`.

### GPIO dependencies on the Pi

`gpiozero` + `lgpio` come from apt, **not pip** (the lgpio wheel needs `swig` to
compile and fails under `uv`):

```bash
sudo apt install -y python3-gpiozero python3-lgpio
```

The venv must be able to see them, so create it with system site-packages:

```bash
uv venv --system-site-packages
```

(For an existing venv: set `include-system-site-packages = true` in
`.venv/pyvenv.cfg`.)

### Useful Resources

- `gpiozero` docs: https://gpiozero.readthedocs.io/
- MTA GTFS-Realtime reference: https://api.mta.info/
- Raspberry Pi GPIO pinout: https://pinout.xyz/
