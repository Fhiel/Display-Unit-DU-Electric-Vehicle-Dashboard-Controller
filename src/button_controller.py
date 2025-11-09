# button_controller.py
from machine import Pin
import utime
import micropython

micropython.alloc_emergency_exception_buf(100)

BUTTON_PIN_GPIO = 25
LONG_PRESS_TIME_MS = 2000
DEBOUNCE_TIME_MS = 50

button_press_start_time = 0
last_press_duration = 0
last_isr_time = 0
button_event_flag = False

def button_isr(pin):
    global button_press_start_time, last_press_duration, last_isr_time, button_event_flag
    now = utime.ticks_ms()
    if utime.ticks_diff(now, last_isr_time) < DEBOUNCE_TIME_MS:
        return
    last_isr_time = now
    if pin.value() == 0:
        button_press_start_time = now
    else:
        last_press_duration = utime.ticks_diff(now, button_press_start_time)
        button_event_flag = True

def init(debug_print):
    pin = Pin(BUTTON_PIN_GPIO, Pin.IN, Pin.PULL_UP)
    pin.irq(trigger=Pin.IRQ_FALLING | Pin.IRQ_RISING, handler=button_isr)
    debug_print("Button controller initialized.")

def get_button_action_and_clear():
    global button_event_flag, last_press_duration
    if not button_event_flag:
        return "none"
    action = "long" if last_press_duration >= LONG_PRESS_TIME_MS else "short"
    button_event_flag = False
    return action