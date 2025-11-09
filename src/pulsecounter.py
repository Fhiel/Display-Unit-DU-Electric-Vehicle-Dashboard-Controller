# pulsecounter.py
# Async pulse counter for speed & distance calculation
# Uses hardware interrupt + async timing, shared_data integration

import uasyncio as asyncio
from machine import Pin
import utime

# --- Configuration ---
PULSE_PIN_GPIO = 20          # GPIO for wheel sensor
PULSES_PER_REVOLUTION = 1    # Adjust to your sensor
WHEEL_CIRCUMFERENCE_MM = 1884  # e.g., 60 cm tire → 1884 mm
MM_PER_KM = 1_000_000

# --- Global Variables ---
pulse_count = 0
last_pulse_time = 0
last_calc_time = 0

def pulse_isr(pin):
    """ISR: Count pulses from wheel sensor (rising edge)"""
    global pulse_count, last_pulse_time
    current_time = utime.ticks_us()
    # Simple debounce: ignore if < 1000 µs since last pulse
    if utime.ticks_diff(current_time, last_pulse_time) > 1000:
        pulse_count += 1
        last_pulse_time = current_time

def init(shared_data):
    """Initialize pulse input with interrupt"""
    global last_calc_time
    pin = Pin(PULSE_PIN_GPIO, Pin.IN, Pin.PULL_UP)
    pin.irq(trigger=Pin.IRQ_RISING, handler=pulse_isr)
    last_calc_time = utime.ticks_ms()
    shared_data.debug_print("Pulse counter initialized on GPIO 20.", level=1)

async def calculate_speed_and_distance(shared_data):
    """
    Async task: Calculate speed (km/h) and distance increment (km)
    Called periodically from main loop
    """
    global pulse_count, last_pulse_time, last_calc_time

    current_time = utime.ticks_ms()
    time_diff_ms = utime.ticks_diff(current_time, last_calc_time)
    if time_diff_ms <= 0:
        await asyncio.sleep_ms(10)
        return 0.0, 0.0

    # Capture and reset pulse count atomically
    pulses = pulse_count
    pulse_count = 0
    last_calc_time = current_time

    if pulses == 0:
        # No pulses → speed = 0
        return 0.0, 0.0

    # --- Calculate distance ---
    distance_mm = pulses * WHEEL_CIRCUMFERENCE_MM / PULSES_PER_REVOLUTION
    distance_km = distance_mm / MM_PER_KM

    # --- Calculate speed ---
    time_diff_sec = time_diff_ms / 1000.0
    speed_kmh = (distance_km / time_diff_sec) * 3600.0 if time_diff_sec > 0 else 0.0

    # Debug output (only if speed changed significantly)
    if abs(speed_kmh - shared_data.speed) > 0.5:
        shared_data.debug_print(f"Speed: {speed_kmh:.1f} km/h, +{distance_km:.6f} km", level=2)

    return speed_kmh, distance_km