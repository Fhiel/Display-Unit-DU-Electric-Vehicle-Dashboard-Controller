from machine import Pin, Timer

# === BKA30-R5 Direct Drive Config ===
MAX_SPEED_KMH = 225
MAX_STEPS = 600      # To allow for a bit of overdrive beyond 225 km/h (for calibration)
STEP_DELAY_MS = 2    # Fast stepping for smooth pointer movement (2ms per step = 500 steps/sec max)

PIN_NUMBERS = [10, 20, 19, 29]
PINS = []

# Half-step sequence for smooth movement (8 steps per full step)
HALF_STEP_SEQUENCE = [
    [1, 0, 0, 1], [1, 0, 0, 0], [1, 1, 0, 0], [0, 1, 0, 0],
    [0, 1, 1, 0], [0, 0, 1, 0], [0, 0, 1, 1], [0, 0, 0, 1]
]

_current_step = 0
_target_step = 0
_timer = Timer(-1)
_running = False
_is_calibrating = False 

def _set_coils(state):
    """ Writes to pins. Ensure protection diodes are present! """
    for i in range(4):
        PINS[i].value(state[i])

def _timer_callback(t):
    global _current_step, _target_step, _running, _is_calibrating  

    if _current_step == _target_step:
        _running = False
        t.deinit()
        # Important: We turn off coils when target is reached to prevent overheating without 
        # resistors. This also allows the pointer to settle naturally on the needle stop.
        _set_coils([0, 0, 0, 0]) 
        
        if _is_calibrating:
            _current_step = 0
            _target_step = 0
            _is_calibrating = False
        return

    direction = 1 if (_target_step > _current_step) else -1
    _current_step += direction
    _set_coils(HALF_STEP_SEQUENCE[_current_step % 8])

def _start_timer():
    global _running
    if not _running:
        _running = True
        _timer.init(mode=Timer.PERIODIC, period=STEP_DELAY_MS, callback=_timer_callback)

import machine

def init(debug_print):
    global PINS, _current_step, _target_step, _running
    
    # Address for Pad-Control-Register for GPIO 10, 20, 19, 29
    # Each GPIO has a register that controls the Drive Strength.
    GPIO_PAD_BASE = 0x4001c000
    
    PINS = []
    for p in PIN_NUMBERS:
        pin_obj = Pin(p, Pin.OUT, value=0)
        PINS.append(pin_obj)
        
        # Set Drive Strength to 12mA (Register-Manipulation)
        # Offset for GPIO n is 4 + n*4
        reg_addr = GPIO_PAD_BASE + 4 + (p * 4)
        # Bits 5:4 control the Drive Strength: 00=2mA, 01=4mA, 10=8mA, 11=12mA
        current_val = machine.mem32[reg_addr]
        new_val = (current_val & ~(0b11 << 4)) | (0b11 << 4)
        machine.mem32[reg_addr] = new_val
    
    _current_step = _target_step = 0
    _running = False
    _set_coils([0, 0, 0, 0])
    debug_print("BKA30: Drive Strength set to 12mA (Hardware Register tweak).")

def odometer_pointer(speed_kmh, debug_print=None):
    global _target_step, _is_calibrating
    if _is_calibrating: return

    speed_kmh = max(0.0, min(speed_kmh, MAX_SPEED_KMH))
    new_target = int((speed_kmh / MAX_SPEED_KMH) * MAX_STEPS)

    if new_target != _target_step:
        _target_step = new_target
        _start_timer()

def odometer_pointer_zero(debug_print=None):
    """ Homing: Drive back to zero pin. """
    global _target_step, _is_calibrating 
    if _is_calibrating: return
    _is_calibrating = True 
    _target_step = _current_step - (MAX_STEPS + 60)
    _start_timer()