# motor.py
# Full-featured stepper motor driver with FullStep and HalfStep modes
# Supports smooth stepping, position tracking, angle control, and timing
# Based on: https://youtu.be/B86nqDRskVU – excellent reference!

import machine
import utime


class Motor:
    """
    Base class for stepper motor control.
    Handles pin setup, state machine, position tracking, and timed stepping.
    """
    stepms = 10          # Default delay between steps (ms)
    maxpos = 0           # Total steps per revolution (set by subclass)
    states = []          # State table: list of [p1, p2, p3, p4] sequences

    def __init__(self, p1, p2, p3, p4, stepms=None):
        """
        Initialize motor with 4 phase pins.
        :param p1, p2, p3, p4: Pin objects (already initialized as OUT)
        :param stepms: Optional step delay in milliseconds
        """
        self.pins = [p1, p2, p3, p4]
        if stepms is not None:
            self.stepms = stepms

        self._state = 0      # Current index in state table
        self._pos = 0        # Current position (0 to maxpos-1)

    def __repr__(self):
        return f'<{self.__class__.__name__} @ {self.pos}>'

    @property
    def pos(self):
        """Current position in steps (read-only)"""
        return self._pos

    @classmethod
    def frompins(cls, *pins, **kwargs):
        """
        Factory method: create motor from pin numbers.
        Automatically initializes pins as OUTPUT.
        """
        return cls(*[machine.Pin(pin, machine.Pin.OUT) for pin in pins], **kwargs)

    def zero(self):
        """Reset internal position counter to 0"""
        self._pos = 0

    def _step(self, dir):
        """
        Perform one microstep in the given direction.
        Updates pins and internal state/position.
        """
        state = self.states[self._state]
        for i, val in enumerate(state):
            self.pins[i].value(val)

        # Advance state index
        self._state = (self._state + dir) % len(self.states)
        # Update position (wrap around)
        self._pos = (self._pos + dir) % self.maxpos

    def step(self, steps):
        """
        Move the motor by a given number of steps.
        Handles direction, timing, and prevents blocking.
        """
        dir = 1 if steps >= 0 else -1
        steps = abs(steps)

        for _ in range(steps):
            t_start = utime.ticks_ms()
            self._step(dir)
            t_end = utime.ticks_ms()
            # Ensure minimum step delay
            t_delta = utime.ticks_diff(t_end, t_start)
            if t_delta < self.stepms:
                utime.sleep_ms(self.stepms - t_delta)

    def step_until(self, target, dir=None):
        """
        Move to absolute position (0 to maxpos-1).
        Auto-detects shortest direction if dir is None.
        """
        if not (0 <= target < self.maxpos):
            raise ValueError(f"Target {target} out of range [0, {self.maxpos})")

        if dir is None:
            diff = (target - self._pos) % self.maxpos
            dir = 1 if diff <= self.maxpos // 2 else -1

        while self._pos != target:
            self.step(dir)

    def step_until_angle(self, angle, dir=None):
        """
        Move to position based on 360° angle.
        :param angle: 0.0 to 360.0 degrees
        """
        if not (0 <= angle <= 360):
            raise ValueError(f"Angle {angle} must be in [0, 360]")

        target = int(angle / 360 * self.maxpos)
        self.step_until(target, dir=dir)


class FullStepMotor(Motor):
    """
    Full-step drive mode: 4 states per cycle.
    Higher torque, simpler wiring.
    """
    stepms = 5           # Faster stepping possible
    maxpos = 946         # Steps per revolution (adjust per motor/gear)
    states = [
        [1, 1, 0, 0],
        [0, 1, 1, 0],
        [0, 0, 1, 1],
        [1, 0, 0, 1],
    ]


class HalfStepMotor(Motor):
    """
    Half-step drive mode: 8 states per cycle.
    Smoother motion, half the step angle.
    """
    stepms = 3
    maxpos = 946
    states = [
        [1, 0, 0, 0],
        [1, 1, 0, 0],
        [0, 1, 0, 0],
        [0, 1, 1, 0],
        [0, 0, 1, 0],
        [0, 0, 1, 1],
        [0, 0, 0, 1],
        [1, 0, 0, 1],
    ]