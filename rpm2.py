# rpm2.py
# Synchronous RPM output via PWM (for external tachometer)
# Maps motor RPM → PWM duty cycle

from machine import Pin, PWM
import utime

# --- Configuration ---
RPM_PIN = 15
PWM_FREQ = 100  # Hz
MIN_RPM = 0
MAX_RPM = 8000

# --- Global PWM ---
pwm = None

def init(debug_print):
    """Initialize PWM output for RPM"""
    global pwm
    pwm = PWM(Pin(RPM_PIN))
    pwm.freq(PWM_FREQ)
    pwm.duty_u16(0)
    debug_print("RPM PWM output initialized on GPIO 15.")

def set_rpm_output(rpm, debug_func=None):
    """
    Set PWM duty cycle based on RPM
    0 RPM → 0% duty, MAX_RPM → 100% duty
    """
    global pwm
    if rpm < MIN_RPM:
        rpm = MIN_RPM
    elif rpm > MAX_RPM:
        rpm = MAX_RPM

    duty_percent = (rpm / MAX_RPM) * 100
    duty_u16 = int((duty_percent / 100) * 65535)
    pwm.duty_u16(duty_u16)

    if debug_func and abs(rpm - getattr(set_rpm_output, 'last_rpm', 0)) > 50:
        debug_func(f"RPM output: {rpm} → {duty_percent:.1f}% duty")
        set_rpm_output.last_rpm = rpm