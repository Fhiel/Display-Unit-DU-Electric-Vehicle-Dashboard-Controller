# rpm2.py - Optimized for Release
from machine import Pin, PWM

RPM_PIN = 27
PWM_FREQ = 150  
MIN_RPM = 0
MAX_RPM = 8000

# Global PWM object
pwm = None

def init(debug_print):
    global pwm
    try:
        pwm = PWM(Pin(RPM_PIN))
        pwm.freq(PWM_FREQ)
        pwm.duty_u16(0)
        debug_print(f"RPM PWM initialized on GPIO {RPM_PIN} at {PWM_FREQ}Hz.")
        return True
    except Exception as e:
        debug_print(f"ERROR initializing RPM PWM: {e}", level=0)
        pwm = None
        return False

def set_rpm_output(rpm, debug_func=None):
    global pwm
    if pwm is None:
        return

    try:
        # Range clamping
        if rpm < MIN_RPM: rpm = MIN_RPM
        if rpm > MAX_RPM: rpm = MAX_RPM

        # 1. Ducty cycle calculation: Linear mapping from RPM to duty_u16
        # duty_u16: 0 bis 65535
        duty_u16 = int((rpm / MAX_RPM) * 65535)
        
        # 2. update only if significant change (ca. 25 RPM) to reduce jitter
        # That's about 200 in duty_u16 units (65535/8000*25 ≈ 204)
        last_duty = getattr(set_rpm_output, 'last_duty', -1)
        if abs(duty_u16 - last_duty) > 200: # ca. 25 RPM change
            pwm.duty_u16(duty_u16)
            set_rpm_output.last_duty = duty_u16

        # 3. Optional debug print for significant RPM changes (ca. 250 RPM)
        last_rpm = getattr(set_rpm_output, 'last_rpm', 0)
        if debug_func and abs(rpm - last_rpm) > 250:
            debug_func(f"RPM Update: {rpm} U/min", level=2)
            set_rpm_output.last_rpm = rpm

    except Exception as e:
        if debug_func:
            debug_func(f"ERROR in RPM output: {e}", level=1)