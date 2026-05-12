# button_controller.py
import utime
from machine import Pin

BUTTON_PIN_GPIO = 25
LONG_PRESS_TIME_MS = 1500
DEBOUNCE_TIME_MS = 50

# Internal state for button handling
_button_pin = None
_last_stable_state = 1
_press_start_time = 0

def init(debug_print=None):
    global _button_pin
    _button_pin = Pin(BUTTON_PIN_GPIO, Pin.IN, Pin.PULL_UP)
    if debug_print:
        debug_print(f"Button Controller: Polling Mode on GPIO {BUTTON_PIN_GPIO}")

def get_button_action_and_clear():
    """
    This function is called by the block7_task every 20ms.
    It detects button presses without requiring interrupts.
    """
    global _last_stable_state, _press_start_time
    
    if _button_pin is None:
        return "none"

    # Read current state (0 = pressed, 1 = released)
    current_state = _button_pin.value()
    action = "none"

    # CASE 1: Button just got pressed (transition from 1 to 0)
    if _last_stable_state == 1 and current_state == 0:
        _press_start_time = utime.ticks_ms()
        _last_stable_state = 0

    # CASE 2: Button is still pressed (state 0) - we do nothing until it gets released
    elif _last_stable_state == 0 and current_state == 0:
        pass # We wait only for the release

    # CASE 3: Button was just released (transition from 0 to 1)
    elif _last_stable_state == 0 and current_state == 1:
        duration = utime.ticks_diff(utime.ticks_ms(), _press_start_time)
        _last_stable_state = 1
        
        # Debouncing: Only count actions over 50ms
        if duration >= DEBOUNCE_TIME_MS:
            if duration >= LONG_PRESS_TIME_MS:
                action = "long"
            else:
                action = "short"

    return action