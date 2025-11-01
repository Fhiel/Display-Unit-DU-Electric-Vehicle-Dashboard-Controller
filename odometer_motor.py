# odometer_motor.py
# Controls the analog odometer pointer using FullStepMotor from motor.py
# Smooth movement with STEPS_PER_MOVEMENT, clamping, and zero calibration
# Uses original parameters: MAX_SPEED_KMH=225, MAX_STEPS=480, etc.

import motor
from machine import Pin

# --- Configuration (EXACTLY as in your original) ---
MAX_SPEED_KMH = 225               # Maximum speed on the gauge (225 km/h)
MAX_STEPS = 480                   # Total steps for full scale (0 → 225 km/h)
STEPS_PER_MOVEMENT = 4            # Smooth movement: 4 steps per update (~1.5°)

# --- Global State ---
_stepper = None                   # Instance of FullStepMotor
_current_steps = 0                # Current position in steps (0 to MAX_STEPS)


# --- Helper: Linear mapping with clamping ---
def _map(value, in_min, in_max, out_min, out_max):
    if in_max == in_min:
        return out_min
    ratio = (value - in_min) / (in_max - in_min)
    return int(out_min + ratio * (out_max - out_min))


# --- Initialization ---
def init(debug_print):
    """
    Initialize the odometer stepper motor using motor.py's FullStepMotor.
    Pins: A=GP10, B=GP20, A'=GP19, B'=GP29
    """
    global _stepper, _current_steps
    try:
        _stepper = motor.FullStepMotor.frompins(
            Pin(10),   # Phase A
            Pin(20),   # Phase B
            Pin(19),   # Phase A'
            Pin(29)    # Phase B'
        )
        _current_steps = 0
        debug_print("Odometer motor initialized (FullStep, 4-phase, pins 10,20,19,29).", level=1)
    except Exception as e:
        debug_print(f"ERROR: Odometer motor init failed: {e}", level=0)
        _stepper = None


# --- Update pointer position ---
def odometer_pointer(speed_kmh, debug_print=None):
    """
    Move the odometer pointer smoothly toward target speed.
    Uses incremental steps (STEPS_PER_MOVEMENT) to avoid jerking.
    """
    global _current_steps, _stepper

    if _stepper is None:
        if debug_print:
            debug_print("ERROR: Odometer motor not initialized!", level=0)
        return

    try:
        speed_kmh = max(0, min(speed_kmh, MAX_SPEED_KMH))
        target_steps = _map(speed_kmh, 0, MAX_SPEED_KMH, 0, MAX_STEPS)
        diff = target_steps - _current_steps

        if diff > 0:
            steps = min(diff, STEPS_PER_MOVEMENT)
        elif diff < 0:
            steps = max(diff, -STEPS_PER_MOVEMENT)
        else:
            steps = 0

        if steps != 0:
            _stepper.step(steps)
            _current_steps += steps

            if debug_print:
                debug_print(f"Odometer: {speed_kmh:.1f} km/h → {target_steps} steps (+{steps})", level=2)

    except Exception as e:
        if debug_print:
            debug_print(f"ERROR in odometer_pointer: {e}", level=0)


# --- Zero calibration ---
def odometer_pointer_zero(debug_print=None):
    """
    Move pointer to zero position (calibration).
    Applies -40 steps (~15° below zero) to ensure needle rests at 0.
    """
    global _stepper

    if _stepper is None:
        if debug_print:
            debug_print("ERROR: Odometer motor not initialized!", level=0)
        return

    try:
        # Move 40 steps backward to go below zero
        _stepper.step(-40)
        _current_steps = max(_current_steps - 40, 0)  # Prevent negative steps

        if debug_print:
            debug_print("Odometer zeroed: moved -40 steps for calibration.", level=1)

    except Exception as e:
        if debug_print:
            debug_print(f"ERROR in odometer_pointer_zero: {e}", level=0)