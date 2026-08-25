"""Driver for a single 28BYJ-48 stepper motor (via ULN2003) with a hall-effect
home sensor.

One ``StepperHand`` owns four GPIO output pins (the ULN2003 IN1..IN4) and one
input pin (the hall sensor). It tracks absolute position in half-steps from the
home position, can home itself by sweeping until the sensor triggers, and moves
to a target angle by the shorter of the two directions.

Uses gpiozero (backed by lgpio on the Pi Zero 2 W). gpiozero is only imported
when a hand is actually constructed, so this module is importable on a laptop
with no GPIO — handy for editing/linting off-Pi.
"""

import logging
import time

logger = logging.getLogger(__name__)

# Half-step sequence for the 28BYJ-48. Eight states, energising one or two of
# the four coils at a time. Driving the sequence forward turns the shaft one
# way; reversed, the other. Half-stepping gives smoother motion and better
# positional resolution than full-stepping.
HALF_STEP_SEQUENCE = [
    (1, 0, 0, 0),
    (1, 1, 0, 0),
    (0, 1, 0, 0),
    (0, 1, 1, 0),
    (0, 0, 1, 0),
    (0, 0, 1, 1),
    (0, 0, 0, 1),
    (1, 0, 0, 1),
]


class StepperHand:
    def __init__(
        self,
        in_pins,
        hall_pin,
        steps_per_rev,
        step_delay,
        hall_active_level,
        homing_max_steps,
        name="hand",
        home_offset_steps=0,
    ):
        # Import here so the module loads fine on a non-Pi machine.
        from gpiozero import DigitalInputDevice, DigitalOutputDevice

        self.name = name
        self.steps_per_rev = steps_per_rev
        self.step_delay = step_delay
        self.hall_active_level = hall_active_level
        self.homing_max_steps = homing_max_steps
        # Mechanical fudge: after centering on the magnet zone, step this many
        # half-steps before declaring 0. Corrects a hand whose magnet isn't
        # exactly at the true 12 o'clock. Positive = clockwise (forward).
        self.home_offset_steps = home_offset_steps

        self._coils = [DigitalOutputDevice(pin) for pin in in_pins]

        # pull_up=True keeps a floating sensor from reading garbage. These
        # modules are active-HIGH (read HIGH when a magnet is present); the
        # caller's hall_active_level encodes that.
        self._hall = DigitalInputDevice(hall_pin, pull_up=True)

        self._seq_index = 0          # where we are in HALF_STEP_SEQUENCE
        self._position = 0           # absolute half-steps from home (0..steps_per_rev-1)
        self._homed = False

    # -- low level ---------------------------------------------------------

    def _apply(self, pattern):
        for coil, value in zip(self._coils, pattern):
            coil.value = value

    def release(self):
        """De-energise all coils. The motor holds position via gear friction
        and stops drawing current (and stops getting warm)."""
        self._apply((0, 0, 0, 0))

    def _step(self, direction):
        """Advance one half-step. direction is +1 or -1."""
        self._seq_index = (self._seq_index + direction) % len(HALF_STEP_SEQUENCE)
        self._apply(HALF_STEP_SEQUENCE[self._seq_index])
        self._position = (self._position + direction) % self.steps_per_rev
        time.sleep(self.step_delay)

    def step_many(self, steps):
        """Move `steps` half-steps. Positive = forward, negative = reverse."""
        direction = 1 if steps >= 0 else -1
        for _ in range(abs(steps)):
            self._step(direction)
        self.release()

    @property
    def _hall_triggered(self):
        # gpiozero DigitalInputDevice.value is 1 when the pin reads HIGH.
        level = 1 if self._hall.value else 0
        return level == self.hall_active_level

    # -- homing ------------------------------------------------------------

    def home(self):
        """Find the 0 position using the hall sensor, then define it as 0.

        The magnet covers an arc of the revolution (the "trigger zone"), not a
        single point. To get a repeatable home regardless of where we start or
        how wide that zone is, we:

          1. If we start inside the zone, step forward until we exit it (so the
             next entry is a clean rising edge).
          2. Sweep forward until we re-enter the zone (the leading edge).
          3. Keep stepping through the zone to its far edge, then set home to
             the CENTER of the zone — the most repeatable reference point.

        Budget is two full revolutions so a wide trigger zone plus a worst-case
        starting position can never run out prematurely. Raises RuntimeError if
        the sensor never triggers (bad wiring, missing magnet, or wrong
        HALL_ACTIVE_LEVEL)."""
        logger.info("[%s] homing...", self.name)
        budget = 2 * self.steps_per_rev

        # Remember where the step count *claimed* we were, so a re-home can
        # report how wrong that claim turned out to be.
        start_position = self._position
        was_homed = self._homed

        # 1. Exit the zone if we start inside it.
        steps = 0
        while self._hall_triggered and steps < budget:
            self._step(1)
            steps += 1

        # 2. Find the leading edge (first step where the magnet appears).
        while not self._hall_triggered and steps < budget:
            self._step(1)
            steps += 1
        if steps >= budget:
            self.release()
            raise RuntimeError(
                f"[{self.name}] homing failed: hall sensor never triggered in "
                f"{budget} steps — check wiring, magnet, and HALL_ACTIVE_LEVEL"
            )

        # 3. Measure the zone width, then back up to its center.
        zone = 0
        while self._hall_triggered and zone < self.steps_per_rev:
            self._step(1)
            zone += 1
        self.step_many(-(zone // 2))  # land on the middle of the magnet

        # 4. Apply the mechanical home offset so 0 lands on true 12 o'clock.
        if self.home_offset_steps:
            self.step_many(self.home_offset_steps)

        self.release()

        # 5. Compare distance actually travelled against the distance the step
        # count predicted. On a re-home the gap is accumulated open-loop error
        # since the last home — the thing STEP_DELAY_SECONDS is tuned against.
        # Positive = the hand was lagging (lost steps); negative = ran ahead.
        drift = None
        if was_homed:
            travelled = steps + zone - (zone // 2) + self.home_offset_steps
            expected = (0 - start_position) % self.steps_per_rev
            drift = (travelled - expected) % self.steps_per_rev
            if drift > self.steps_per_rev // 2:
                drift -= self.steps_per_rev

        self._position = 0
        self._seq_index = 0
        self._homed = True

        if drift is None:
            logger.info(
                "[%s] home found (magnet zone %d steps, centered, offset %+d)",
                self.name,
                zone,
                self.home_offset_steps,
            )
        else:
            logger.info(
                "[%s] home found (magnet zone %d steps, centered, offset %+d) "
                "— drift since last home: %+d steps (%+.2f°)",
                self.name,
                zone,
                self.home_offset_steps,
                drift,
                drift / self.steps_per_rev * 360.0,
            )

    # -- high level --------------------------------------------------------

    def steps_for_angle(self, angle_deg):
        """Absolute half-step position (0..steps_per_rev-1) for a face angle."""
        angle_deg %= 360.0
        return round(angle_deg / 360.0 * self.steps_per_rev) % self.steps_per_rev

    def move_to_position(self, target_position, forward_only=False):
        """Move to an absolute half-step position.

        By default takes the shorter of the two directions. With
        ``forward_only`` the hand always travels clockwise, even when that
        means going most of the way round the dial — used when a hand is
        handed a different train, so the hands only ever advance clockwise.
        """
        target_position %= self.steps_per_rev
        delta = (target_position - self._position) % self.steps_per_rev
        # delta is now in [0, steps_per_rev): the clockwise distance.
        # Going the "long way" round? Go backwards instead — unless the caller
        # has asked for clockwise-only motion.
        if not forward_only and delta > self.steps_per_rev // 2:
            delta -= self.steps_per_rev
        self.step_many(delta)

    def move_to_angle(self, angle_deg, forward_only=False):
        """Move the hand to a face angle (0° = home = 12 o'clock)."""
        if not self._homed:
            logger.warning(
                "[%s] move requested before homing; position may be wrong",
                self.name,
            )
        self.move_to_position(self.steps_for_angle(angle_deg), forward_only=forward_only)

    def close(self):
        self.release()
        for coil in self._coils:
            coil.close()
        self._hall.close()
