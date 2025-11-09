# temp.py
# Async temperature gauge control (stepper motor)
# Smooth movement, duty cycle control, shared_data debug

import uasyncio as asyncio
from machine import Pin, PWM
import utime

# --- Configuration ---
TEMP_PIN_A = 10
TEMP_PIN_B = 11
TEMP_PIN_C = 12
TEMP_PIN_D = 13
TEMP_MIN = -40
TEMP_MAX = 150
STEPS_PER_DEGREE = 2.4  # Adjust to your gear ratio
DELAY_MS = 2

# --- Stepper sequence (full step) ---
STEP_SEQUENCE = [
    (1, 0, 0, 1),
    (1, 1, 0, 0),
    (0, 1, 1, 0),
    (0, 0, 1, 1)
]

class TempGauge:
    def __init__(self, debug_print):
        self.debug_print = debug_print
        self.pins = [PWM(Pin(TEMP_PIN_A)), PWM(Pin(TEMP_PIN_B)),
                     PWM(Pin(TEMP_PIN_C)), PWM(Pin(TEMP_PIN_D))]
        for p in self.pins:
            p.freq(1000)
            p.duty_ns(0)
        self.current_step = 0
        self.target_step = 0
        self.debug_print("TempGauge initialized (stepper).")

    async def _move_to_step(self, target):
        """Move stepper to target step smoothly"""
        steps_to_move = (target - self.current_step) % (4 * 200)
        direction = 1 if steps_to_move <= 400 else -1
        steps_to_move = min(steps_to_move, 800 - steps_to_move) * direction

        for _ in range(abs(steps_to_move)):
            self.current_step = (self.current_step + direction) % 4
            seq = STEP_SEQUENCE[self.current_step]
            for i, val in enumerate(seq):
                self.pins[i].duty_ns(500000 if val else 0)
            await asyncio.sleep_ms(DELAY_MS)

        # Turn off coils
        for p in self.pins:
            p.duty_ns(0)

    async def update(self, temperature):
        """Update gauge to show temperature (clamped)"""
        if temperature < TEMP_MIN:
            temperature = TEMP_MIN
        elif temperature > TEMP_MAX:
            temperature = TEMP_MAX

        # Map temperature to steps
        temp_range = TEMP_MAX - TEMP_MIN
        degrees = temperature - TEMP_MIN
        target_step = int(degrees * STEPS_PER_DEGREE)

        if target_step != self.target_step:
            self.target_step = target_step
            self.debug_print(f"Temp gauge → {temperature}°C ({target_step} steps)", level=2)
            await self._move_to_step(target_step)