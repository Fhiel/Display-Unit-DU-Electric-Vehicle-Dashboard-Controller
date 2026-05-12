import utime
import machine
from machine import Pin

# --- Configuration ---
PULSE_PIN_GPIO = 28 
PULSES_PER_REVOLUTION = 1 
WHEEL_CIRCUMFERENCE_MM = 1884 
MM_PER_KM = 1_000_000 

# --- Global state ---
pulse_count = 0 
last_calc_time = 0 
last_pulse_time_us = 0
_pin_ref = None 

def pulse_isr(pin):
    """ Minimal ISR with software debouncing. """
    global pulse_count, last_pulse_time_us
    
    # Simple Debounce: Ignore pulses faster than 300 km/h (approx 2ms interval)
    now = utime.ticks_us()
    if utime.ticks_diff(now, last_pulse_time_us) > 2000:
        pulse_count += 1
        last_pulse_time_us = now

def init(shared_data):
    global last_calc_time, _pin_ref
    _pin_ref = Pin(PULSE_PIN_GPIO, Pin.IN, Pin.PULL_UP)
    _pin_ref.irq(trigger=Pin.IRQ_RISING, handler=pulse_isr)
    last_calc_time = utime.ticks_us() # We switch to microseconds
    
    if shared_data:
        shared_data.debug_print("Pulse counter: Precision ISR initialized (GPIO 28)", level=1)

async def calculate_speed_and_distance(shared_data):
    global pulse_count, last_calc_time

    # 1. Atomic read and reset
    state = machine.disable_irq() # Critical Section Start
    pulses = pulse_count
    pulse_count = 0
    machine.enable_irq(state)      # Critical Section End

    # 2. Timing (Microseconds for high precision)
    current_time = utime.ticks_us()
    time_diff_us = utime.ticks_diff(current_time, last_calc_time)
    last_calc_time = current_time

    if time_diff_us <= 0 or pulses == 0:
        # Stationary or very slow: smooth decay
        new_speed = shared_data.speed * 0.7 if shared_data.speed > 0.5 else 0.0
        return new_speed, 0.0

    # 3. Math: Distance
    distance_km = (pulses * WHEEL_CIRCUMFERENCE_MM) / (PULSES_PER_REVOLUTION * MM_PER_KM)
    
    # 4. Math: Speed (km/h)
    # Conversion: distance_km / (time_us / 1,000,000 / 3600)
    time_diff_hours = time_diff_us / 3_600_000_000.0
    speed_kmh = distance_km / time_diff_hours

    # 5. Signal Smoothing (Low-Pass Filter)
    # 0.3 weight is good for a steady needle that still reacts quickly
    alpha = 0.3
    filtered_speed = (shared_data.speed * (1 - alpha)) + (speed_kmh * alpha)

    # 6. Sanity Clamp
    if filtered_speed > 250: filtered_speed = 250.0

    return filtered_speed, distance_km