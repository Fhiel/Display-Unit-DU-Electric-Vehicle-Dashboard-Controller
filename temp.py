from machine import Pin, PWM # Oder DAC, je nach Hardware
import utime

# Globale Konstanten für das Gauge (anpassen!)
TEMP_GAUGE_PIN = 26
TEMP_MIN = 0  # Minimale Temperatur, die der Zeiger anzeigt
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