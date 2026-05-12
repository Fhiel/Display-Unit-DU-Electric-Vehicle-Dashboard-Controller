# odometer_motor.py
# Fully self-contained, non-blocking stepper driver for analog odometer
# RP2040 + uasyncio safe – no external motor.py needed!
# Uses hardware Timer → zero blocking, perfect with async applications

from machine import Pin, Timer

# === Configuration ===
MAX_SPEED_KMH = 225
MAX_STEPS = 480
STEPS_PER_MOVEMENT = 4
STEP_DELAY_MS = 4                     # 4 ms → ~250 Hz max (perfect for 28BYJ-48 + ULN2003)

# Pin assignment (ULN2003 driver or direct output)
PIN_NUMBERS = [10, 20, 19, 29] # <-- Liste der Nummern, kein Pin-Objekt!
PINS = [] # <-- Leere Liste

# Full-step sequence (high torque, classic 4-phase)
FULL_STEP_SEQUENCE = [
    [1, 1, 0, 0],
    [0, 1, 1, 0],
    [0, 0, 1, 1],
    [1, 0, 0, 1]
]

# === Global state ===
_current_step = 0        # Actual motor position (steps)
_target_step = 0         # Desired position
_timer = Timer(-1)
_running = False
_is_calibrating = False 

# === Private helper functions ===
def _set_coils(state):
    """Set the four coil outputs according to sequence"""
    for pin, value in zip(PINS, state):
        pin.value(value)

def _timer_callback(t):
    global _current_step, _target_step, _running, _is_calibrating  

    if _current_step == _target_step:
        _running = False
        t.deinit()
        _set_coils([0, 0, 0, 0])
        
        if _is_calibrating:
            _current_step = 0
            _is_calibrating = False
        return

    direction = 1 if (_target_step > _current_step) else -1
    _current_step += direction

    base_idx = _current_step % 4 
    
    if direction < 0:
        seq_idx = (base_idx + 2) % 4 
    else:
        seq_idx = base_idx
        
    _set_coils(FULL_STEP_SEQUENCE[seq_idx])

def _start_timer():
    """Start the hardware timer if not already running"""
    global _running
    if not _running:
        _running = True
        _timer.init(mode=Timer.PERIODIC, period=STEP_DELAY_MS, callback=_timer_callback)

# === Public API (same as before) ===
def init(debug_print):
    """Initialize odometer motor – all pins off at start"""
    global _current_step, _target_step, _running, PINS

    PINS = [Pin(p, Pin.OUT) for p in PIN_NUMBERS]
    
    _current_step = _target_step = 0
    _running = False
    _set_coils([0, 0, 0, 0])
    debug_print("Odometer motor: standalone non-blocking driver ready (pins 10,20,19,29)")

def odometer_pointer(speed_kmh, debug_print=None):
    """Move pointer smoothly – completely non-blocking"""
    global _target_step, _is_calibrating

    if _is_calibrating:
        if debug_print:
             debug_print("Odometer update skipped: Calibrating...")
        return

    speed_kmh = max(0.0, min(speed_kmh, MAX_SPEED_KMH))
    new_target = int((speed_kmh / MAX_SPEED_KMH) * MAX_STEPS)
    new_target = max(0, min(new_target, MAX_STEPS))

    if new_target != _target_step:
        old = _target_step
        _target_step = new_target
        _start_timer()

        if debug_print and abs(new_target - old) > 8:
            debug_print(f"Odometer → {speed_kmh:.1f} km/h (target step {new_target})")

def odometer_pointer_zero(debug_print=None):
    global _target_step, _current_step, _is_calibrating 
    
    if _is_calibrating: 
        return
    
    _is_calibrating = True 
    
    _target_step = _current_step - 40
    _start_timer()
    if debug_print:
        debug_print("Odometer zero calibration: moving to target.")

def get_current_steps():
    """Optional: read current position (for debugging)"""
    return _current_step