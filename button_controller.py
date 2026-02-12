# button_controller.py
# Fully RP2040-safe button handler with long/short press detection
# NO ticks_ms/diff in ISR → uses micropython.schedule() instead!

import utime
from machine import Pin
import micropython

# Emergency buffer (good practice)
micropython.alloc_emergency_exception_buf(100)

# === Configuration ===
BUTTON_PIN_GPIO = 25
LONG_PRESS_TIME_MS = 2000
DEBOUNCE_TIME_MS = 50

# === Global state (accessed from ISR and main loop) ===
_button_state = 1          # 1 = released, 0 = pressed
_press_start_time = 0
_last_press_duration = 0
_button_event_ready = False

# === ISR – ultra minimal, NO ticks_* calls! ===
# button_controller.py (ISR)

# button_controller.py (Korrekturen)

# === ISR – ultra minimal, NO ticks_* calls! ===
def _button_isr(pin):
    global _button_state, _press_start_time
    current_state = pin.value()

    # Nur auf Zustandswechsel reagieren
    if current_state != _button_state:
        _button_state = current_state
        
        if current_state == 0:  # Button pressed (FALLING)
            # RP2040-safe: Speichern der Startzeit HIER. 
            # WICHTIG: Dies ist der Ausnahmefall, da wir utime im sicheren Handler verwenden müssen.
            _press_start_time = utime.ticks_ms()
            
        # Wenn der Button losgelassen wird (current_state == 1), wird 
        # das Event im Scheduled Handler (unten) verarbeitet.
        
        # Wecken Sie den Haupt-Loop sicher auf
        micropython.schedule(_process_button_event, None)


# === Safe processing outside ISR ===
def _process_button_event(_):
    global _press_start_time, _last_press_duration, _button_event_ready
    
    # 1. Wir verarbeiten nur, wenn der Button jetzt freigegeben ist.
    if _button_state == 0: 
        return

    # 2. Button wurde freigegeben: Dauer messen
    now = utime.ticks_ms()
    duration = utime.ticks_diff(now, _press_start_time)
    
    # 3. Debounce-Prüfung
    if duration >= DEBOUNCE_TIME_MS:
        _last_press_duration = duration
        # Event ist gültig und bereit für die Abholung durch die API
        _button_event_ready = True
    else:
        # Bounce oder zu kurz, ignorieren
        _button_event_ready = False

# === Public API ===
def init(debug_print):
    pin = Pin(BUTTON_PIN_GPIO, Pin.IN, Pin.PULL_UP)
    pin.irq(trigger=Pin.IRQ_FALLING | Pin.IRQ_RISING, handler=_button_isr)
    debug_print("Button controller initialized (RP2040-safe ISR)")

def get_button_action_and_clear():
    """Return 'short', 'long', or 'none' and reset flag"""
    global _button_event_ready, _last_press_duration
    if not _button_event_ready:
        return "none"

    action = "long" if _last_press_duration >= LONG_PRESS_TIME_MS else "short"
    _button_event_ready = False
    return action

def is_pressed():
    """Optional: check current button state"""
    return _button_state == 0