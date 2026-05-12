# rpm2.py - Frequencey-Modulation for RPM Output (Optimized für Release)
from machine import Pin, PWM

RPM_PIN = 27
# 50% duty cycle (32768) as fixed value to ensure the signal is recognized by the gauge, while we modulate the frequency to represent RPM.
FIXED_DUTY = 32768 

# The frequency range for the gauge is approximately 15 Hz (ca. 500 RPM) to 300 Hz (ca. 8000 RPM).
# We will use a linear mapping from RPM to frequency:   
# 29 Hz = 1000 RPM
# 200 Hz = 6000 RPM
# That results in the slope (m): (200 - 29) / (6000 - 1000) = 0.0342
# and the offset (b): 29 - (1000 * 0.0342) = -5.2

def init(debug_print):
    global pwm
    try:
        pwm = PWM(Pin(RPM_PIN))
        pwm.duty_u16(0) # Start with 0 duty to prevent any signal until we set the first RPM
        debug_print(f"RPM Pulse-Output auf GPIO {RPM_PIN} initialisiert.")
        return True
    except Exception as e:
        debug_print(f"ERROR RPM Init: {e}", level=0)
        pwm = None
        return False

def set_rpm_output(rpm, debug_func=None):
    global pwm
    if pwm is None:
        return

    try:
        # Range clamping
        if rpm < 600:
            # Below 600 RPM, we set duty to 0 to indicate stationary or very low speed, as the frequency would be too low for the gauge to interpret correctly.
            pwm.duty_u16(0) 
            return

        # --- Regular frequency modulation for RPM representation ---
        # f = rpm * 0.0342 - 5.2
        freq = int(rpm * 0.0342 - 5.2)
        
        # Safety clamping for frequency to ensure we don't set values outside the gauge's expected range
        if freq < 15: freq = 15 
        if freq > 300: freq = 300 

        # Set the fixed duty cycle and modulate the frequency to represent RPM
        pwm.freq(freq)
        
        # Ensure duty is set to the fixed value if it's currently 0, to start the signal. The frequency modulation will then represent the RPM.
        if pwm.duty_u16() == 0:
            pwm.duty_u16(FIXED_DUTY)

        # Debugging
        last_rpm = getattr(set_rpm_output, 'last_rpm', 0)
        if debug_func and abs(rpm - last_rpm) > 200:
            debug_func(f"RPM Update: {rpm} U/min -> {freq} Hz", level=2)
            set_rpm_output.last_rpm = rpm

    except Exception as e:
        if debug_func:
            debug_func(f"ERROR in RPM Freq-Mod: {e}", level=1)