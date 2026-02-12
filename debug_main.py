# SCHRITT 5 – Alles bisher + Odometer-, Central- und RND-Display-Tasks
import uasyncio as asyncio
import os
from machine import Pin, WDT, I2C, SoftI2C
import rp2
import utime

import pulsecounter
import odometer_motor
import button_controller
import rpm2
import store_km
from temp import TempGauge
from ssd1306 import SSD1306_I2C
from myfont import MyFont
import display_manager
from display_manager import DISPLAY_MODE_SPEED, DISPLAY_MODE_TOTAL, DISPLAY_MODE_TRIP, DISPLAY_MODE_TEMP
from RS485_RX import CanBusController

R_ISO_MAX = 50000          # Used in validation and default telemetry
R_ISO_WARNING = 400        # TODO: Implement warning threshold (e.g., flash, icon)
R_ISO_ERROR = 250          # TODO: Implement error threshold (e.g., shutdown, alert)

class SharedData:
    def __init__(self):
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

    def debug_print(self, msg, level=1): print("SHARED:", msg)

shared_data = SharedData()

# --- Inits ---
pulsecounter.init(shared_data)
odometer_motor.init(shared_data.debug_print)
rpm2.init(shared_data.debug_print)
button_controller.init(shared_data.debug_print)
temp_gauge = TempGauge(shared_data.debug_print)

# Displays
i2c1 = I2C(1, scl=Pin(7), sda=Pin(6), freq=400000)
display_manager.odometer = SSD1306_I2C(128, 32, i2c1, addr=0x3c)
i2c2 = SoftI2C(scl=Pin(22), sda=Pin(21), freq=400000)
display_manager.central = SSD1306_I2C(128, 32, i2c2, addr=0x3c)
i2c3 = SoftI2C(scl=Pin(24), sda=Pin(23), freq=400000)
display_manager.rnd = SSD1306_I2C(64, 32, i2c3, addr=0x3c)

display_manager.font_large = MyFont('large')
display_manager.font_small = MyFont('small')
print("MyFont geladen und zugewiesen!")

can_controller = CanBusController(shared_data)

print("=== SCHRITT 5 – ALLES BIS HIERHER INITIALISIERT ===")

# --- Tasks ---
async def block1_task():
    while True:
        current_time = utime.ticks_ms()
        if utime.ticks_diff(current_time, getattr(shared_data, "last_critical_update_time", 0)) >= 50:
            try:
                raw_speed, dist = await pulsecounter.calculate_speed_and_distance(shared_data)
                shared_data.speed = raw_speed
                shared_data.total_km += dist
                shared_data.trip_km += dist
                odometer_motor.odometer_pointer(shared_data.speed, shared_data.debug_print)
                rpm2.set_rpm_output(0, shared_data.debug_print)
            except: pass
            shared_data.last_critical_update_time = current_time
        await asyncio.sleep(0.05)

async def block2_task():   # Odometer Display
    while True:
        await display_manager.update_odometer_display(shared_data)
        await asyncio.sleep(1)

async def block3_task():   # Central Display
    while True:
        await display_manager.update_central_display(shared_data)
        await asyncio.sleep(1)

async def block_rnd_task():   # RND Display
    while True:
        await display_manager.update_rnd_display(shared_data)
        await asyncio.sleep(5)

async def can_receiver_task():
    await can_controller.receiver_task()

async def watchdog_task():
    wdt = WDT(timeout=8000)
    while True:
        wdt.feed()
        await asyncio.sleep(1)

async def main():
    asyncio.create_task(block1_task())
    asyncio.create_task(block2_task())
    asyncio.create_task(block3_task())
    asyncio.create_task(block_rnd_task())
    # asyncio.create_task(can_receiver_task())
    # asyncio.create_task(watchdog_task())
    
    while True:
        await asyncio.sleep(3600)

try:
    asyncio.run(main())
except Exception as e:
    print("FATAL:", e)