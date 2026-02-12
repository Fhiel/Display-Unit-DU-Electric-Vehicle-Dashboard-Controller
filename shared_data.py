# shared_data.py

import utime
from display_manager import (DISPLAY_MODE_SPEED, DISPLAY_MODE_TOTAL, DISPLAY_MODE_TRIP, DISPLAY_MODE_TEMP)

# --- Application Constants (Used in app.py) ---
DEBUG_LEVEL = 0
DATA_TIMEOUT_MS = 4000
WATCHDOG_TIMEOUT_MS = 5000
# IMD R_ISO Values
R_ISO_MIN = 0
R_ISO_MAX = 50000   # Used in validation and default telemetry
R_ISO_WARNING = 400 # TODO: Implement warning threshold (e.g., flash, icon)
R_ISO_ERROR = 250   # TODO: Implement error threshold (e.g., shutdown, alert)

# --- Shared Data ---
class SharedData:
    def __init__(self, debug_level=1):
        # General
        self.last_gc_time = utime.ticks_ms()
        self.last_debug_output_time = 0
        self.current_contrast = 255
        self.rs485_error_count = 0

        # Pointer & sensors
        self.last_pointer_update_time = utime.ticks_ms()
        self.last_critical_update_time = utime.ticks_ms()
        self.last_temp_gauge_update_time = utime.ticks_ms()

        # Odometer display
        self.last_odometer_display_update_time = utime.ticks_ms()
        self.current_display_mode = DISPLAY_MODE_SPEED
        self.temp_show = 1  # 1 = MOTOR, 0 = MCU
        self.odo_last_contrast = -1
        self.odo_dirty_flag = False
        self.last_displayed_speed_str = None
        self.last_displayed_km_str = None
        self.last_displayed_trip_str = None
        self.last_displayed_temp_source = None
        self.last_displayed_mode = None
        self.digital_speed = 0
        self.speed = 0.0
        self.total_km = 0.0
        self.trip_km = 0.0

        # RND display
        self.last_rnd_update_time = utime.ticks_ms()
        self.rnd_last_contrast = -1
        self.rnd_dirty_flag = False
        self.rnd_last_invert_state = -1
        self.rnd_last_displayed_char = ' '
        self.current_rnd_status_char = ' '

        # Central display
        self.last_central_display_update_time = utime.ticks_ms()
        self.central_boot_active = True
        self.central_ok_start_time = utime.ticks_ms()
        self.central_dirty_flag = False
        self.central_last_contrast = -1
        self.central_last_invert_state = -1
        self.central_init_step = 0
        self.central_status_stack = []
        self.central_display_index = 0
        self.central_last_cycle_time = utime.ticks_ms()
        self.last_displayed_motor_temp = -999
        self.last_displayed_mcu_temp = -999
        self.last_displayed_imd_iso_r = -999

        # Odometer saving
        self.last_speed = 0.0
        self.last_save_time = 0
        self.stop_start_time = None
        self.odometer_saved_in_stop = False

        # DEMO MODE TRACKING
        self.last_demo_can = utime.ticks_ms() # NEU

        # Data validation
        self.last_valid_data_time = utime.ticks_ms()
        self.last_valid_motor_time = utime.ticks_ms()
        self.last_valid_imd_time = utime.ticks_ms()

        self.internal_telemetry_data = {
            'motorRPM': 0,
            'mcuFlags': 0,
            'mcuFaultLevel': 0,
            'imdIsoR': R_ISO_MAX,
            'imdState': "IMD NDT",
            'vifcStatus': "VI NDT",
            'motorTemp': 0,
            'mcuTemp': 0,
            'systemStatus': 'WAITING_FOR_DATA',
            'motorDataValid': False,
            'imdDataValid': False
        }

    def debug_print(self, message, level=1):
        if DEBUG_LEVEL >= level:
            if level == 1 or utime.ticks_diff(utime.ticks_ms(), self.last_debug_output_time) >= 500:
                print(f"DEBUG(main): {message}")
                self.last_debug_output_time = utime.ticks_ms()