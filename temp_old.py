from machine import Pin, PWM
import utime

# Configuration for the instrument in X1/9e
TEMP_GAUGE_PIN = 26
TEMP_MIN = 40   # Most often the display starts at 40 or 50 degrees
TEMP_MAX = 120  # Warning range usually starts at 110-120 degrees
PWM_FREQUENCY = 50 
PWM_MIN_DUTY = 7000   # Corresponds to left stop (Cold)
PWM_MAX_DUTY = 40000  # Corresponds to right stop (Hot)

class TempGauge:
    def __init__(self, debug_func_from_main):
        self.debug_print = debug_func_from_main
        self.pin_number = TEMP_GAUGE_PIN
        self.gauge_output = None
        self.current_filtered_temp = None # For the smoothing
        self.init_hardware()

    def init_hardware(self):
        try:
            self.pwm_pin = Pin(self.pin_number)
            self.gauge_output = PWM(self.pwm_pin, freq=PWM_FREQUENCY)
            self.gauge_output.duty_u16(PWM_MIN_DUTY)
            self.debug_print(f"Temp-Gauge (Pin {self.pin_number}) ready.")
                        
        except Exception as e:
            self.debug_print(f"ERROR Temp-Gauge: {e}", level=0)
            self.gauge_output = None

    def update(self, current_temp):
        if self.gauge_output is None:
            return

        # 1. Smoothing (Exponential Moving Average)
        # Prevents needle jittering with unstable CAN values
        if self.current_filtered_temp is None:
            self.current_filtered_temp = current_temp
        else:
            alpha = 0.1 # Very strong damping (10% new value, 90% old value)
            self.current_filtered_temp = (self.current_filtered_temp * (1 - alpha)) + (current_temp * alpha)

        # 2. Clamping & Mapping
        clamped_temp = max(TEMP_MIN, min(TEMP_MAX, self.current_filtered_temp))
        
        # Normalization from 0.0 to 1.0
        normalized = (clamped_temp - TEMP_MIN) / (TEMP_MAX - TEMP_MIN)
        
        # Mapping to PWM Duty Cycle
        pwm_range = PWM_MAX_DUTY - PWM_MIN_DUTY
        duty_cycle = int(normalized * pwm_range + PWM_MIN_DUTY)

        # 3. Hardware-Update
        try:
            self.gauge_output.duty_u16(duty_cycle)
            
            # Debug only for large jumps (e.g., warm-up phase or sudden changes)
            last_debug_temp = getattr(self, 'last_debug_temp', 0)
            if abs(clamped_temp - last_debug_temp) > 5:
                self.debug_print(f"Temp-Gauge: {clamped_temp:.1f}°C (Duty: {duty_cycle})", level=2)
                self.last_debug_temp = clamped_temp
        except:
            pass


from machine import Pin, PWM # Oder DAC, je nach Hardware
import utime

# Globale Konstanten für das Gauge (anpassen!)
TEMP_GAUGE_PIN = 26
TEMP_MIN = 0 # Minimale Temperatur, die der Zeiger anzeigt
TEMP_MAX = 100 # Maximale Temperatur, die der Zeiger anzeigt
PWM_FREQUENCY = 50 # Frequenz (Hz) für den Zeiger (oft 50Hz bis 1000Hz)
PWM_MAX_DUTY = 40000 # Maximale Duty Cycle (für 16-Bit-PWM)
PWM_MIN_DUTY = 7000

class TempGauge:
    def __init__(self, debug_func_from_main):
        self.debug_print = debug_func_from_main
        self.pin_number = TEMP_GAUGE_PIN
        self.gauge_output = None
        self.min_temp = TEMP_MIN
        self.max_temp = TEMP_MAX
        self.init_hardware()

    def init_hardware(self):
        try:
            # Annahme: Verwendung von PWM, da dies universeller ist.
            # Wenn Pin 26 ein DAC ist, ersetzen Sie dies durch: self.gauge_output = DAC(Pin(self.pin_number))
            self.pwm_pin = Pin(self.pin_number)
            self.gauge_output = PWM(self.pwm_pin, freq=PWM_FREQUENCY)
            self.debug_print(f"Temperatur-Zeiger (Pin {self.pin_number}) initialisiert (PWM).")
        except Exception as e:
            self.debug_print(f"ERROR: Fehler bei der Initialisierung des Temperatur-Zeigers: {e}")
            self.gauge_output = None

    def update(self, current_temp):
        if self.gauge_output is None:
             # Wenn die PWM-Initialisierung fehlgeschlagen ist (self.gauge_output = None),
            # beenden wir die Funktion sofort.
            return

        clamped_temp = max(self.min_temp, min(self.max_temp, current_temp))
        temp_range = self.max_temp - self.min_temp

        pwm_range = PWM_MAX_DUTY - PWM_MIN_DUTY # Der nutzbare PWM-Bereich

        if temp_range <= 0:
            duty_cycle = PWM_MIN_DUTY # Setze auf Minimum bei Fehler
        else:
            # Normierung (0.0 bis 1.0)
            normalized = (clamped_temp - self.min_temp) / temp_range

        # Skalierung auf den nutzbaren PWM-Bereich (PWM_MIN_DUTY bis PWM_MAX_DUTY)
            duty_cycle = int(normalized * pwm_range + PWM_MIN_DUTY) # <--- KORRIGIERTE MAPPING-FORMEL

        self.gauge_output.duty_u16(duty_cycle)
