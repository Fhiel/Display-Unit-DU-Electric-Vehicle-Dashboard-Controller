# shared_data.py
import utime
from display_manager import (DISPLAY_MODE_SPEED, DISPLAY_MODE_TOTAL, DISPLAY_MODE_TRIP, DISPLAY_MODE_TEMP)

# --- Application Constants ---
DEBUG_LEVEL = 1                    # Globaler Default Debug Level 
DATA_TIMEOUT_MS = 5000

class SharedData:
    def __init__(self, debug_level=None):
        # 1. Debug Configuration
        self.debug_level = debug_level if debug_level is not None else DEBUG_LEVEL
        self.last_debug_output_time = utime.ticks_ms()

        # 2. Timing & Watchdog Heartbeats
        now = utime.ticks_ms()
        self.last_block1_heartbeat = now
        self.last_status_task_heartbeat = now
        self.last_valid_data_time = now
        self.last_valid_motor_time = now
        self.last_valid_imd_time = now
        self.last_gc_time = now

        # 3. Movement & Odometer Data
        self.speed = 0.0
        self.last_speed = 0.0
        self.digital_speed = 0
        self.total_km = 0.0
        self.trip_km = 0.0
        self.last_save_time = now
        self.stop_start_time = None
        self.odometer_saved_in_stop = False

        # 4. Display States & Updates
        self.current_display_mode = DISPLAY_MODE_SPEED
        self.temp_show = 1  # 1 = MOTOR, 0 = MCU
        self.current_contrast = 42
        
        # Pointer & Gauges
        self.last_critical_update_time = now
        self.last_temp_gauge_update_time = now
        self.last_odometer_display_update_time = now
        self.last_rnd_update_time = now
        self.last_central_display_update_time = now

        # Dirty Flags & Cache (to prevent unnecessary OLED re-draws)
        self.odo_dirty_flag = False
        self.odo_last_contrast = -1
        self.rnd_dirty_flag = False
        self.rnd_last_contrast = -1
        self.central_dirty_flag = False
        self.central_last_contrast = -1
        
        # Display String Cache
        self.last_displayed_speed_str = ""
        self.last_displayed_km_str = ""
        self.last_displayed_trip_str = ""
        self.current_rnd_status_char = ' '
        self.rnd_last_displayed_char = ' '

        # 5. Central Status Stack logic
        self.last_displayed_mode = None
        self.central_boot_active = True
        self.central_ok_start_time = now
        self.central_status_stack = []
        self.central_display_index = 0
        self.central_last_cycle_time = now

        # 6. Pre-allocated Telemetry Structure (Fixed Keys for Stability)
        self.internal_telemetry_data = {
            'motorRPM': 0,
            'motorTemp': 0,
            'mcuTemp': 0,
            'mcuState': "MCU NDT",
            'imdState': "IMD NDT",
            'vifcStatus': "VIFC NDT",
            'mcuStateRaw': 0,
            'imdStateRaw': 0,
            'vifcStatusRaw': 0,
            'mcuFlagsRaw': 0,      # Pre-allocated
            'mcuFaultLevel': 0,
            'imdIsoR': 0,
            'systemStatus': 'NDT',
            'motorDataValid': False,
            'imdDataValid': False,
        }

    def debug_print(self, message, level=1):
        """ 
        Efficient debug printing. 
        Level 0: Always critical (Errors)
        Level 1: Info (Normal behavior)
        Level 2: Verbose (Details)
        """
        if self.debug_level < level:
            return

        now = utime.ticks_ms()
        # Always print Level 0, or rate-limit others to 500ms
        if level == 0 or utime.ticks_diff(now, self.last_debug_output_time) >= 500:
            print(f"[{level}] {message}")
            self.last_debug_output_time = now