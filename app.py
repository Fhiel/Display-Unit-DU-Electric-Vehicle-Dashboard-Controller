# app.py
# Version 10.0 - Complete, English, async, store_km, debug_print

import uasyncio as asyncio
from machine import Pin, WDT, reset
import utime
import micropython
import gc

# --- Global Constants ---
STATUS_UPDATE_PERIOD_MS = 200
DISPLAY_UPDATE_PERIOD_MS = 1000
RND_UPDATE_PERIOD_MS = 1000
POINTER_UPDATE_PERIOD_MS = 50
TEMP_GAUGE_UPDATE_PERIOD_MS = 1000

# DEBUG_LEVEL = 1 # defined central in shared_data

# Own modules
from shared_data import SharedData, DEBUG_LEVEL, DATA_TIMEOUT_MS
from RS485_RX import CanBusController
from status_codes import get_rnd_status, get_mcu_state, get_imd_state, get_vifc_state
from temp import TempGauge, TEMP_MIN
import store_km
from myfont import MyFont
import rpm2
import pulsecounter
import odometer_motor
import button_controller
import display_manager
from display_manager import DISPLAY_MODE_SPEED, DISPLAY_MODE_TOTAL, DISPLAY_MODE_TRIP, DISPLAY_MODE_TEMP


# =================================================================
# RP2040-compatible sleep_ms() Fix
# =================================================================
async def sleep_ms(ms: int):
    if ms > 0:
        await asyncio.sleep(ms / 1000.0)
    else:
        await asyncio.sleep(0)
# =================================================================

# --- Global Instances ---
odometer = None
central = None
rnd = None
can_controller = None
watchdog = None
temp_gauge = None

# --- Init Displays ---
def init_displays(shared_data):
    from machine import I2C, SoftI2C
    from ssd1306 import SSD1306_I2C
    global odometer, central, rnd
    try:
        i2c1 = I2C(1, scl=Pin(7), sda=Pin(6), freq=400000)
        odometer = SSD1306_I2C(128, 32, i2c1, addr=0x3c)
        odometer.rotate(0)
        display_manager.odometer = odometer
        shared_data.debug_print("Odometer display initialized.")
    except Exception as e:
        shared_data.debug_print(f"ERROR: Odometer display init failed: {e}", level=0)

    try:
        i2c2 = SoftI2C(scl=Pin(22), sda=Pin(21), freq=400000)
        central = SSD1306_I2C(128, 32, i2c2, addr=0x3c)
        central.rotate(0)
        display_manager.central = central
        shared_data.debug_print("Central display initialized.") 
    except Exception as e:
        shared_data.debug_print(f"ERROR: Central display init failed: {e}", level=0)

    try:
        i2c3 = SoftI2C(scl=Pin(24), sda=Pin(23), freq=400000)
        rnd = SSD1306_I2C(64, 32, i2c3, addr=0x3c)
        rnd.rotate(0)
        display_manager.rnd = rnd
        shared_data.debug_print("RND display initialized.")
    except Exception as e:
        shared_data.debug_print(f"ERROR: RND display init failed: {e}", level=0)

# --- Init Hardware ---
def init_hardware(shared_data):
    global can_controller, temp_gauge, watchdog
    try:
        can_controller = CanBusController(shared_data)
        asyncio.create_task(can_controller.receiver_task())
        shared_data.debug_print("CAN controller initialized.")
    except Exception as e:
        shared_data.debug_print(f"ERROR: CAN controller init failed: {e}", level=0)

    try:
        pulsecounter.init(shared_data)
        shared_data.debug_print("Pulse counter initialized.")
    except Exception as e:
        shared_data.debug_print(f"ERROR: Pulse counter init failed: {e}", level=0)

    try:
        odometer_motor.init(shared_data.debug_print)
        shared_data.debug_print("Odometer motor initialized.")
    except Exception as e:
        shared_data.debug_print(f"ERROR: Odometer motor init failed: {e}", level=0)

    try:
        rpm2.init(shared_data.debug_print)
        shared_data.debug_print("RPM output initialized.")
    except Exception as e:
        shared_data.debug_print(f"ERROR: RPM output init failed: {e}", level=0)

    try:
        temp_gauge = TempGauge(shared_data.debug_print)
        shared_data.debug_print("Temp gauge initialized.")
    except Exception as e:
        shared_data.debug_print(f"ERROR: Temp gauge init failed: {e}", level=0)

    try:
        button_controller.init(shared_data.debug_print)
        shared_data.debug_print("Button controller initialized.")
    except Exception as e:
        shared_data.debug_print(f"ERROR: Button init failed: {e}", level=0)

    try:
        watchdog = WDT(timeout=WATCHDOG_TIMEOUT_MS)
        shared_data.debug_print("Watchdog initialized.")
    except Exception as e:
        shared_data.debug_print(f"ERROR: Watchdog init failed: {e}", level=0)

# --- Validate Telemetry ---
def validate_telemetry_data(data):
    if not data or data.get('type') != 'telemetry':
        return False
    motor_valid = data.get('motorDataValid', False)
    imd_valid = data.get('imdDataValid', False)
    if not (motor_valid or imd_valid):
        return False
    if motor_valid:
        if not (0 <= data.get('motorRPM', 0) < 12000):
            return False
        if not (-40 <= data.get('motorTemp', 0) <= 150):
            return False
        if not (-40 <= data.get('mcuTemp', 0) <= 150):
            return False
    if imd_valid:
        if not (0 <= data.get('imdIsoR', 0) < R_ISO_MAX):
            return False
    return True

# --- DIESER CODE BLOCK WIRD JETZT SYNCHRON AUSGEFÜHRT, WENN app.py IMPORTIERT WIRD ---
# Die Heap-Messungen sind nicht mehr notwendig, aber ich lasse sie drin
gc.collect() 
print("--- app.py Start: Synchroner Initialisierungs-Block ---")

print(f"TEST: DEBUG LEVEL is {DEBUG_LEVEL}") # Test: Ist es wirklich definiert?

shared_data = SharedData(debug_level=DEBUG_LEVEL)

# local instantiation
font_small_inst = MyFont('small') 
font_large_inst = MyFont('large')

# allocation to display_manager as global
display_manager.font_small = font_small_inst
display_manager.font_large = font_large_inst

# load odometer data
try:
    shared_data.total_km, shared_data.trip_km = store_km.load_odometer(shared_data.debug_print)
    shared_data.debug_print(f"Odometer loaded: total={shared_data.total_km:.3f} km, trip={shared_data.trip_km:.3f} km")
except Exception as e:
    shared_data.debug_print(f"ERROR loading odometer: {e} → using 0.0", level=0)
    shared_data.total_km = 0.0
    shared_data.trip_km = 0.0

init_displays(shared_data)
shared_data.debug_print("Displays initialized")

init_hardware(shared_data)

shared_data.debug_print("Starting main loop - ALL TASKS ACTIVE")

# =================================================================
# TASKS function definitions
# =================================================================
# BLOCK 1: Critical sensors & pointers
async def block1_task():
    while True:
        current_time = utime.ticks_ms()
        if utime.ticks_diff(current_time, shared_data.last_critical_update_time) >= POINTER_UPDATE_PERIOD_MS:
            try:
                raw_speed, distance_increment = await pulsecounter.calculate_speed_and_distance(shared_data)
                shared_data.speed = raw_speed
                shared_data.digital_speed = int(round(raw_speed))
                shared_data.total_km += distance_increment
                shared_data.trip_km += distance_increment
            except Exception as e:
                shared_data.debug_print(f"ERROR in pulse counter: {e}", level=1)

            try:
                odometer_motor.odometer_pointer(shared_data.speed, shared_data.debug_print)
            except Exception as e:
                shared_data.debug_print(f"ERROR in odometer motor: {e}", level=1)

            try:
                system_status = shared_data.internal_telemetry_data.get('systemStatus', 'UNKNOWN')
                motor_data_valid = shared_data.internal_telemetry_data.get('motorDataValid', False)
                current_rpm = shared_data.internal_telemetry_data.get('motorRPM', 0) if system_status == 'OK' and motor_data_valid else 0
                rpm2.set_rpm_output(current_rpm, debug_func=shared_data.debug_print)
            except Exception as e:
                shared_data.debug_print(f"ERROR in RPM output: {e}", level=1)

            shared_data.last_critical_update_time = current_time
        await sleep_ms(POINTER_UPDATE_PERIOD_MS)

# BLOCK 2: Odometer display
async def block2_task():
    while True:
        current_time = utime.ticks_ms()
        if utime.ticks_diff(current_time, shared_data.last_odometer_display_update_time) >= DISPLAY_UPDATE_PERIOD_MS:
            try:
                await display_manager.update_odometer_display(shared_data)
                shared_data.last_odometer_display_update_time = current_time
            except Exception as e:
                shared_data.debug_print(f"ERROR in odometer display: {e}", level=0)
        await sleep_ms(DISPLAY_UPDATE_PERIOD_MS)

# BLOCK 3: Central display
async def block3_task():
    while True:
        current_time = utime.ticks_ms()
        if utime.ticks_diff(current_time, shared_data.central_last_cycle_time) >= 1000:
            stack_len = len(shared_data.central_status_stack)
            if stack_len > 0:
                new_index = (shared_data.central_display_index + 1) % (stack_len + 1)
                if new_index != shared_data.central_display_index:
                    shared_data.central_display_index = new_index
                    shared_data.central_dirty_flag = True
            else:
                if shared_data.central_display_index != 0:
                    shared_data.central_display_index = 0
                    shared_data.central_dirty_flag = True
            shared_data.central_last_cycle_time = current_time

        if utime.ticks_diff(current_time, shared_data.last_central_display_update_time) >= DISPLAY_UPDATE_PERIOD_MS or shared_data.central_dirty_flag:
            try:
                await display_manager.update_central_display(shared_data)
                shared_data.last_central_display_update_time = current_time
            except Exception as e:
                shared_data.debug_print(f"ERROR in central display: {e}", level=0)
        await sleep_ms(DISPLAY_UPDATE_PERIOD_MS)

# BLOCK RND: RND display
async def block_rnd_task():
    while True:
        current_time = utime.ticks_ms()
        if utime.ticks_diff(current_time, shared_data.last_rnd_update_time) >= RND_UPDATE_PERIOD_MS:
            try:
                await display_manager.update_rnd_display(shared_data)
                shared_data.last_rnd_update_time = current_time
            except Exception as e:
                shared_data.debug_print(f"ERROR in RND display: {e}", level=0)
        await sleep_ms(RND_UPDATE_PERIOD_MS)

# BLOCK STATUS: Derive status strings
async def block_status_task():
    while True:
        await sleep_ms(STATUS_UPDATE_PERIOD_MS)
        telemetry = shared_data.internal_telemetry_data
        mcu_flags = telemetry.get('mcuFlags', 0)
        imd_raw = telemetry.get('imdStatusRaw', 0)
        vifc_raw = telemetry.get('vifcStatusRaw', 0)

        new_mcu = get_mcu_state(mcu_flags)
        new_imd = get_imd_state(imd_raw)
        new_vifc = get_vifc_state(vifc_raw)

        if (telemetry.get('mcuStatus') != new_mcu or
            telemetry.get('imdStatus') != new_imd or
            telemetry.get('vifcStatus') != new_vifc):

            telemetry['mcuStatus'] = new_mcu
            telemetry['imdStatus'] = new_imd
            telemetry['vifcStatus'] = new_vifc

            new_stack = []
            if "OK" not in new_mcu and "NDT" not in new_mcu: new_stack.append(new_mcu)
            if "OK" not in new_imd and "NDT" not in new_imd: new_stack.append(new_imd)
            if "OK" not in new_vifc and "NDT" not in new_vifc: new_stack.append(new_vifc)

            if new_stack != shared_data.central_status_stack:
                shared_data.central_status_stack = new_stack
                shared_data.central_display_index = 0
                shared_data.central_dirty_flag = True

            shared_data.current_rnd_status_char = get_rnd_status(mcu_flags)
            shared_data.rnd_dirty_flag = True

# BLOCK 5: CAN processing
async def block5_task():
    while True:
        current_time = utime.ticks_ms()
        if can_controller and len(can_controller.data_buffer) > 0:
            await can_controller.data_buffer_lock.acquire()
            try:
                last_valid = None
                processed = 0
                while can_controller.data_buffer and processed < 10:
                    data = can_controller.data_buffer.popleft()
                    processed += 1
                    if validate_telemetry_data(data):
                        last_valid = data
                if last_valid and last_valid.get('type') == 'telemetry':
                    t = shared_data.internal_telemetry_data
                    get = last_valid.get
                    motor_valid = get('motorDataValid', False)
                    imd_valid = get('imdDataValid', False)
                    t['motorRPM'] = get('motorRPM', 0) if motor_valid else 0
                    t['motorTemp'] = get('motorTemp', 0) if motor_valid else 0
                    t['mcuTemp'] = get('mcuTemp', 0) if motor_valid else 0
                    t['mcuFlags'] = get('mcuFlags', 0) if motor_valid else 0
                    t['mcuFaultLevel'] = get('mcuFaultLevel', 0) if motor_valid else 0
                    t['imdIsoR'] = get('imdIsoR', 0) if imd_valid else 0
                    t['imdState'] = get('imdState', "IMD NDT") if imd_valid else "IMD NDT"
                    t['vifcStatus'] = get('vifcStatus', 0) if imd_valid else 0
                    t['motorDataValid'] = motor_valid
                    t['imdDataValid'] = imd_valid
                    is_ok = (motor_valid or imd_valid) and get('imdIsoR', R_ISO_MAX) >= R_ISO_WARNING
                    t['systemStatus'] = 'OK' if is_ok else 'ISO_ERROR'
                    shared_data.last_valid_motor_time = current_time if motor_valid else shared_data.last_valid_motor_time
                    shared_data.last_valid_imd_time = current_time if imd_valid else shared_data.last_valid_imd_time
                    shared_data.last_valid_data_time = current_time
            finally:
                can_controller.data_buffer_lock.release()
        await sleep_ms(50)

# BLOCK 6: Odometer saving (only when stopped)
async def block6_task():
    while True:
        current_time_us = utime.ticks_us()
        if shared_data.speed == 0:
            if shared_data.last_speed != 0:
                shared_data.stop_start_time = current_time_us
                shared_data.odometer_saved_in_stop = False
                shared_data.debug_print("Vehicle stopped – save timer started.", level=2)
            elif (shared_data.stop_start_time and
                  utime.ticks_diff(current_time_us, shared_data.stop_start_time) > 2_000_000 and
                  not shared_data.odometer_saved_in_stop):
                try:
                    store_km.save_odometer(shared_data.total_km, shared_data.trip_km, shared_data.debug_print)
                    shared_data.odometer_saved_in_stop = True
                    shared_data.stop_start_time = None
                    shared_data.last_save_time = current_time_us
                    shared_data.debug_print("Odometer saved during stop.", level=1)
                except Exception as e:
                    shared_data.debug_print(f"ERROR saving odometer: {e}", level=0)
        else:
            shared_data.stop_start_time = None
            shared_data.odometer_saved_in_stop = False
        shared_data.last_speed = shared_data.speed
        await sleep_ms(500)

# BLOCK 7: Button handling
async def block7_task():
    while True:
        action = button_controller.get_button_action_and_clear()
        if action == "long":
            if shared_data.current_display_mode == display_manager.DISPLAY_MODE_SPEED:
                try:
                    odometer_motor.odometer_pointer_zero(shared_data.debug_print)
                    shared_data.debug_print("Odometer pointer zeroed.")
                except Exception as e:
                    shared_data.debug_print(f"ERROR zeroing pointer: {e}")
            elif shared_data.current_display_mode == display_manager.DISPLAY_MODE_TRIP:
                shared_data.trip_km = 0.0
                store_km.save_odometer(shared_data.total_km, shared_data.trip_km, shared_data.debug_print)
                shared_data.debug_print("Trip reset and saved.")
            elif shared_data.current_display_mode == display_manager.DISPLAY_MODE_TOTAL:
                shared_data.current_contrast = 42 if shared_data.current_contrast == 255 else 255
                shared_data.debug_print("Contrast toggled.")
            elif shared_data.current_display_mode == display_manager.DISPLAY_MODE_TEMP:
                shared_data.temp_show = 1 - shared_data.temp_show
                shared_data.debug_print(f"Temp source: {'MOTOR' if shared_data.temp_show == 1 else 'MCU'}")
        elif action == "short":
            shared_data.current_display_mode = (shared_data.current_display_mode + 1) % 4
            shared_data.debug_print(f"Mode changed to {shared_data.current_display_mode}")
            await display_manager.update_odometer_display(shared_data)
        await sleep_ms(10)

# BLOCK 8: Temp gauge
async def block8_task():
    while True:
        current_time = utime.ticks_ms()
        if utime.ticks_diff(current_time, shared_data.last_temp_gauge_update_time) >= TEMP_GAUGE_UPDATE_PERIOD_MS:
            temp = shared_data.internal_telemetry_data.get('motorTemp' if shared_data.temp_show == 1 else 'mcuTemp', TEMP_MIN)
            if temp_gauge:
                try:
                    temp_gauge.update(temp)
                    shared_data.last_temp_gauge_update_time = current_time
                except Exception as e:
                    shared_data.debug_print(f"ERROR in temp gauge: {e}", level=0)
        await sleep_ms(TEMP_GAUGE_UPDATE_PERIOD_MS)

# BLOCK 9a: GC
async def block9a_task():
    while True:
        if utime.ticks_diff(utime.ticks_ms(), shared_data.last_gc_time) >= 10000:
            if gc.mem_free() < 30720:
                shared_data.debug_print(f"Low memory: {gc.mem_free()} bytes. Running GC.")
                gc.collect()
            shared_data.last_gc_time = utime.ticks_ms()
        await sleep_ms(10000)

# BLOCK 9b: Timeout check
async def block9b_task():
    while True:
        current_time = utime.ticks_ms()
        if utime.ticks_diff(current_time, shared_data.last_valid_motor_time) > DATA_TIMEOUT_MS:
            shared_data.internal_telemetry_data['motorDataValid'] = False
        if utime.ticks_diff(current_time, shared_data.last_valid_imd_time) > DATA_TIMEOUT_MS:
            shared_data.internal_telemetry_data['imdDataValid'] = False
        if utime.ticks_diff(current_time, shared_data.last_valid_data_time) > DATA_TIMEOUT_MS:
            shared_data.internal_telemetry_data['systemStatus'] = 'NO_DATA_TIMEOUT'
        await sleep_ms(1000)

async def watchdog_task():
    while True:
        if watchdog:
            watchdog.feed()
        await asyncio.sleep(0.8) # alle 800 ms feeden → Timeout 5000 ms

# ──────────────────────────────────────────────────────────────
# Start all async tasks
# ──────────────────────────────────────────────────────────────
async def start_tasks():
    # Start all Tasks, defined in the Blocks
    asyncio.create_task(block1_task())
    asyncio.create_task(block2_task())
    asyncio.create_task(block3_task())
    asyncio.create_task(block_rnd_task())
    asyncio.create_task(block_status_task())
    asyncio.create_task(block5_task())
    asyncio.create_task(block6_task())
    asyncio.create_task(block7_task())
    asyncio.create_task(block8_task())
    asyncio.create_task(block9a_task())
    asyncio.create_task(block9b_task())
    asyncio.create_task(watchdog_task())
    
    # The Main-Loop, that keeps the program runnning
    while True:
        await asyncio.sleep(3600) # A long sleep keeps the scheduler alive

# ------------------------------------------------------------
# Function, called by minimal main.py 
# ------------------------------------------------------------
def run_app():
    try:
        asyncio.run(start_tasks())
    except KeyboardInterrupt:
        shared_data.debug_print("stopped manually (Ctrl+C)")
    except Exception as e:
        shared_data.debug_print(f"FATAL ERROR: {e}", level=0)
        if rnd:
            rnd.fill(0)
            rnd.text("CRASH", 10, 10)
            rnd.show()
        reset()