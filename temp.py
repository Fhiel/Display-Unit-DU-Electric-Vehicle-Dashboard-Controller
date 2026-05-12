# temp_gauge.py
from machine import Pin, PWM
import utime

# Configuration
TEMP_GAUGE_PIN = 26
TEMP_MIN = 40
TEMP_MAX = 120
PWM_FREQUENCY = 50 

# Logic for BS170 MOSFET Inverter:
# PWM 0% (0)      -> MOSFET open  -> 12V at instrument -> Hot/Full scale
# PWM 100% (65535)-> MOSFET closed -> 0V at instrument  -> Cold/Zero
PWM_MIN_VALUE = 60000 # Cold (high duty cycle due to inverter)
PWM_MAX_VALUE = 10000 # Hot (low duty cycle due to inverter)

class TempGauge:
    def __init__(self, debug_func):
        self.debug_print = debug_func
        self.pwm_pin = Pin(TEMP_GAUGE_PIN)
        self.gauge_output = PWM(self.pwm_pin, freq=PWM_FREQUENCY)
        self.current_filtered_temp = None
        self.debug_print("Temp-Gauge (Pin 26) ready.")

    def update(self, temp_c):
        """
        Updates the analog gauge based on Celsius input.
        Maps Celsius range to the physical Fahrenheit scale of the instrument.
        """
        if temp_c is None: 
            return

        # Define physical display range of the scale
        # Mapping Celsius input to Fahrenheit scale points
        T_MIN_C = 48.8  # corresponds to 120°F (Scale start)
        T_MAX_C = 126.6 # corresponds to 260°F (Scale end)
        
        # Calibrated PWM values (adjust based on hardware testing)
        # Note: If 95°C results in full deflection, PWM_HOT should reflect that value.
        PWM_COLD = 5000  # Needle position at 120°F
        PWM_HOT = 55000  # Needle position at 260°F (or calibrated max)

        # Constrain input to defined range
        temp = max(T_MIN_C, min(T_MAX_C, temp_c))
        
        # Linear mapping calculation
        norm = (temp - T_MIN_C) / (T_MAX_C - T_MIN_C)
        duty = int(norm * (PWM_HOT - PWM_COLD) + PWM_COLD)
        
        self.gauge_output.duty_u16(duty)