# pulsecounter.py
# Fully RP2040-safe async pulse counter for speed & distance calculation
# Uses hardware interrupt + micropython.schedule() – no ticks_* calls in ISR!

import utime
import uasyncio as asyncio
from machine import Pin
import micropython

# --- Configuration ---
PULSE_PIN_GPIO = 28                   # GPIO connected to wheel speed sensor
PULSES_PER_REVOLUTION = 1              # Number of pulses per wheel revolution
WHEEL_CIRCUMFERENCE_MM = 1884          # Wheel circumference in mm (e.g. ~60 cm tire)
MM_PER_KM = 1_000_000                  # Millimeters per kilometer

# --- Global state (accessed from ISR and async task) ---
pulse_count = 0                        # Total pulses since last calculation
last_calc_time = 0                     # Last time calculation was performed (ms)
_schedule_calc = False                 # Flag: new pulses arrived → recalc needed

# ----------------------------------------------------------------------
# Ultra-minimal, RP2040-safe ISR – NEVER call utime.ticks_* here!
# ----------------------------------------------------------------------
def pulse_isr(pin):
    """Hardware interrupt handler – must be as short and safe as possible"""
    global pulse_count, _schedule_calc
    pulse_count += 1
    _schedule_calc = True
    # Wake up the async loop safely from ISR context
    micropython.schedule(calc_wrapper, None)

def calc_wrapper(_):
    """Called via micropython.schedule() – just sets the flag again (safe)"""
    global _schedule_calc
    _schedule_calc = True

# ----------------------------------------------------------------------
def init(shared_data):
    """Initialize pulse counter with hardware interrupt"""
    global last_calc_time
    pin = Pin(PULSE_PIN_GPIO, Pin.IN, Pin.PULL_UP)
    pin.irq(trigger=Pin.IRQ_RISING, handler=pulse_isr)
    last_calc_time = utime.ticks_ms()
    shared_data.debug_print("Pulse counter initialized (RP2040-safe mode)", level=1)

# ----------------------------------------------------------------------
async def calculate_speed_and_distance(shared_data):
    """
    Async function called periodically from main loop
    Returns current speed (km/h) and distance increment since last call (km)
    """
    global pulse_count,  last_calc_time, _schedule_calc

    current_time = utime.ticks_ms()
    time_diff_ms = utime.ticks_diff(current_time, last_calc_time)

    # Prevent division by zero or negative time
    if time_diff_ms <= 0:
        await asyncio.sleep_ms(10)
        return shared_data.speed, 0.0

    # Only recalculate if new pulses arrived OR at least 200 ms passed
    if not _schedule_calc and time_diff_ms < 200:
        await asyncio.sleep_ms(10)
        return shared_data.speed, 0.0  # No change

    # Atomically capture and reset pulse count
    pulses = pulse_count
    pulse_count = 0
    _schedule_calc = False
    last_calc_time = current_time

    if pulses == 0:
        speed_kmh = 0.0
        distance_km = 0.0
    else:
        # Total distance traveled in this interval
        distance_mm = pulses * WHEEL_CIRCUMFERENCE_MM / PULSES_PER_REVOLUTION
        distance_km = distance_mm / MM_PER_KM

        # Instantaneous speed calculation
        time_diff_sec = time_diff_ms / 1000.0
        speed_kmh = (distance_km / time_diff_sec) * 3600.0

    # Optional: light low-pass filter for smoother speed display
    alpha = 0.3
    speed_kmh = shared_data.speed * (1 - alpha) + speed_kmh * alpha

    # Debug output only on significant change
    if abs(speed_kmh - shared_data.speed) > 0.5:
        shared_data.debug_print(
            f"Speed: {speed_kmh:.1f} km/h, +{distance_km:.6f} km (pulses: {pulses})",
            level=2
        )

    return speed_kmh, distance_km