# temp_gauge.py
from machine import Pin, PWM

# Configuration
TEMP_GAUGE_PIN = 26
PWM_FREQUENCY = 50 
TEMP_MIN = 40 
TEMP_MAX = 170 

# Physical PWM Calibration (Your tested limits)
PWM_0_PCT   = 5000   # 120°F Mark
PWM_100_PCT = 40000  # 260°F Mark

class TempGauge:
    def __init__(self, debug_func):
        self.debug_print = debug_func
        self.pwm_pin = Pin(TEMP_GAUGE_PIN)
        self.gauge_output = PWM(self.pwm_pin, freq=PWM_FREQUENCY)
        self.gauge_output.duty_u16(PWM_0_PCT)
        
        # Pre-defining the segments to avoid recalculating constants
        # (Temp, Percentage)
        self.points = [
            (50.0, 0.0),
            (75.0, 0.5),
            (135.0, 0.875),
            (155.0, 1.0)
        ]

    def update(self, temp_c, is_valid=True):
        """
        Calculates needle position using segment-based linear mapping.
        Efficient enough for ESP32 FPU.
        """
        # 1. Immediate exit for error states
        if not is_valid or temp_c is None or temp_c >= TEMP_MAX:
            self.gauge_output.duty_u16(PWM_100_PCT)
            return

        # 2. Determine target percentage based on segments
        target_pct = 0.0
        
        if temp_c <= self.points[0][0]: # < 50°C
            target_pct = 0.0
        elif temp_c >= self.points[3][0]: # > 155°C
            target_pct = 1.0
        else:
            # Find the correct segment and interpolate
            for i in range(len(self.points) - 1):
                p1 = self.points[i]
                p2 = self.points[i+1]
                if p1[0] <= temp_c <= p2[0]:
                    # Linear interpolation: y = y1 + (x - x1) * (y2 - y1) / (x2 - x1)
                    target_pct = p1[1] + (temp_c - p1[0]) * (p2[1] - p1[1]) / (p2[0] - p1[0])
                    break

        # 3. Map percentage to calibrated PWM duty cycle
        duty = int(target_pct * (PWM_100_PCT - PWM_0_PCT) + PWM_0_PCT)
        self.gauge_output.duty_u16(duty)