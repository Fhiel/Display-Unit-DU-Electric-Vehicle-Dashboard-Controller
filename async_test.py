# ULTIMATIVER KILLER-TEST – alle Tasks einzeln aktivieren
import uasyncio as asyncio
from machine import Pin, WDT, reset
import utime

# Deine Module (alle schon gefixt)
import pulsecounter
import odometer_motor
import button_controller
import rpm2
import store_km
import display_manager
from temp import TempGauge
from ssd1306 import SSD1306_I2C
from machine import I2C, SoftI2C
from RS485_RX import CanBusController

# Minimal shared_data
class SharedTelemetryData:
    def __init__(self):
        self.speed = 0.0
        self.total_km = self.trip_km = 0.0
        self.last_critical_update_time = utime.ticks_ms()
        self.last_odometer_display_update_time = utime.ticks_ms()
        self.central_last_cycle_time = utime.ticks_ms()
        self.last_rnd_update_time = utime.ticks_ms()
        self.last_valid_data_time = utime.ticks_ms()
        self.last_valid_motor_time = utime.ticks_ms()
        self.last_valid_imd_time = utime.ticks_ms()
        self.internal_telemetry_data = {'motorDataValid': False, 'imdDataValid': False}
    def debug_print(self, msg, level=1): print("MAIN:", msg)

shared_data = SharedTelemetryData()

# Init alles
def init_all():
    store_km.init_filesystem(lambda x: None)
    pulsecounter.init(shared_data)
    odometer_motor.init(shared_data.debug_print)
    rpm2.init(shared_data.debug_print)
    button_controller.init(shared_data.debug_print)
    temp_gauge = TempGauge(shared_data.debug_print)
    
    i2c1 = I2C(1, scl=Pin(7), sda=Pin(6), freq=400000)
    display_manager.odometer = SSD1306_I2C(128, 32, i2c1, addr=0x3c)
    i2c2 = SoftI2C(scl=Pin(22), sda=Pin(21), freq=400000)
    display_manager.central = SSD1306_I2C(128, 32, i2c2, addr=0x3c)
    i2c3 = SoftI2C(scl=Pin(24), sda=Pin(23), freq=400000)
    display_manager.rnd = SSD1306_I2C(64, 32, i2c3, addr=0x3c)
    
    global can_controller
    can_controller = CanBusController(shared_data)
    # asyncio.create_task(can_controller.receiver_task())
    
    print("=== ALLES INITIALISIERT ===")

init_all()

# Deine Original-Tasks (exakt wie vorher)
async def block1_task():
    while True:
        current_time = utime.ticks_ms()
        if utime.ticks_diff(current_time, shared_data.last_critical_update_time) >= 50:
            try:
                raw_speed, distance_increment = await pulsecounter.calculate_speed_and_distance(shared_data)
                shared_data.speed = raw_speed
                shared_data.total_km += distance_increment
                shared_data.trip_km += distance_increment
            except Exception as e:
                pass
            try:
                odometer_motor.odometer_pointer(shared_data.speed, shared_data.debug_print)
            except Exception as e:
                pass
            try:
                rpm2.set_rpm_output(0, debug_func=shared_data.debug_print)
            except Exception as e:
                pass
            shared_data.last_critical_update_time = current_time
        await asyncio.sleep(0.05)

# Die anderen Tasks – erstmal AUSKOMMENTIERT
# async def block2_task(): ...
# async def block3_task(): ...
# async def block_rnd_task(): ...
# async def block_status_task(): ...
# async def block5_task(): ...
# async def block6_task(): ...
# async def block7_task(): ...
# async def block8_task(): ...
# async def block9a_task(): ...
# async def block9b_task(): ...

async def watchdog_task():
    wdt = WDT(timeout=8000)
    while True:
        wdt.feed()
        await asyncio.sleep(1)

# ================================================
# STARTE NUR BLOCK1 + WATCHDOG
# ================================================
async def main():
    asyncio.create_task(block1_task())
    # Die anderen Tasks kommen erst, wenn das hier 100% stabil läuft
    
    if can_controller:
        asyncio.create_task(can_controller.receiver_task())

    asyncio.create_task(watchdog_task())


    asyncio.create_task(watchdog_task())

    while True:
        await asyncio.sleep(3600)

try:
    asyncio.run(main())
except Exception as e:
    print("FATAL:", e)
    if display_manager.rnd:
        display_manager.rnd.fill(0)
        display_manager.rnd.text("CRASH", 5, 10)
        display_manager.rnd.show()
    reset()