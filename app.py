# app.py
# Version 10.0 - async, store_km, debug_print

import uasyncio as asyncio
from machine import Pin, SPI, WDT, reset
import utime
import micropython
import gc

# --- Global Constants ---
WATCHDOG_TIMEOUT_MS = 8000
STATUS_UPDATE_PERIOD_MS = 200
DISPLAY_UPDATE_PERIOD_MS = 1000
RND_UPDATE_PERIOD_MS = 1000
POINTER_UPDATE_PERIOD_MS = 50
TEMP_GAUGE_UPDATE_PERIOD_MS = 1000

# DEBUG_LEVEL = 1 # defined central in shared_data

# Own modules
from shared_data import SharedData, DEBUG_LEVEL, DATA_TIMEOUT_MS
from CANbus_RX import CanBusController
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
        # 1. Create SPI object centrally (5MHz for maximum stability) and 
        # pass it to the CAN controller. This ensures that the SPI bus is properly initialized 
        # and configured before the CAN controller attempts to use it, which can help prevent 
        # initialization issues and improve overall system stability.
        from machine import SPI, Pin
        shared_spi = SPI(0, baudrate=5_000_000, sck=Pin(2), mosi=Pin(3), miso=Pin(4))
        
        # 2. Call the controller with BOTH arguments (shared_data and shared_spi) 
        # to ensure it has all the necessary context and resources for proper initialization 
        # and operation. This allows the controller to access shared data for state management 
        # and debugging, as well as the SPI interface for communication with the CAN transceiver,
        # which can help prevent initialization issues and improve overall system stability.
        can_controller = CanBusController(shared_data, shared_spi)
        
        shared_data.debug_print("CAN controller initialized with shared SPI.")
        utime.sleep_ms(20)
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
        print("DEBUG: rpm2 init successful")
    except Exception as e:
        shared_data.debug_print(f"ERROR: RPM output init failed: {e}", level=0)
        print(f"DEBUG: rpm2 init exception: {e}")

    try:
        temp_gauge = TempGauge(shared_data.debug_print)
        shared_data.debug_print("Temp gauge initialized.")
    except Exception as e:
        shared_data.debug_print(f"ERROR: Temp gauge init failed: {e}", level=0)

    try:
        button_controller.init(shared_data.debug_print)
        # TEST: Direkt nach dem Init prüfen
        if button_controller._button_pin is not None:
             shared_data.debug_print("DEBUG: _button_pin is NOW set in module!")
        else:
             shared_data.debug_print("DEBUG: _button_pin is STILL NONE after init!")
    except Exception as e:
        shared_data.debug_print(f"ERROR: Button init failed: {e}", level=0)
    try:
        watchdog = WDT(timeout=WATCHDOG_TIMEOUT_MS)
        shared_data.debug_print("Watchdog initialized.")
    except Exception as e:
        shared_data.debug_print(f"ERROR: Watchdog init failed: {e}", level=0)


# This block will now be executed synchronously when app.py is imported, 
# ensuring that all hardware initialization and setup is completed 
# before any tasks are started. This is crucial for the stability of the system, 
# as it guarantees that all components are properly initialized and ready to be used 
# by the asynchronous tasks that will be running in the background.
gc.collect() 
print("--- app.py Start: Synchroner Initialisierungs-Block ---")

print(f"TEST: DEBUG LEVEL is {DEBUG_LEVEL}") 

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

print("=== Starting task system - clean version ===")

# =============================================
# TASK DEFINITIONS
# =============================================

async def block1_task():
    """ Essential: Handles speed calculation, odometer increments, and motor pointers. """
    while True:
        current_time = utime.ticks_ms()
        # Ensure we only update at the defined period
        try:
            # 1. Calculation
            raw_speed, distance_increment = await pulsecounter.calculate_speed_and_distance(shared_data)
            shared_data.speed = raw_speed
            shared_data.digital_speed = int(round(raw_speed))
            shared_data.total_km += distance_increment
            shared_data.trip_km += distance_increment
            
            # 2. Hardware Pointer Move
            odometer_motor.odometer_pointer(shared_data.speed, shared_data.debug_print)
            
            # 3. RPM Output Update (if valid)
            t = shared_data.internal_telemetry_data
            if t.get('motorDataValid', False) and t.get('systemStatus') == 'OK':
                rpm2.set_rpm_output(t.get('motorRPM', 0), debug_func=shared_data.debug_print)
            else:
                rpm2.set_rpm_output(0)
                
            # Health Check for Watchdog
            shared_data.last_block1_heartbeat = current_time
            
        except Exception as e:
            shared_data.debug_print(f"CRITICAL in Block 1: {e}", level=0)

        await asyncio.sleep_ms(POINTER_UPDATE_PERIOD_MS)

async def block_status_task():
    """ Processes telemetry and manages the central status message stack. """
    from status_codes import get_mcu_state, get_imd_state, get_vifc_state, get_rnd_status
    
    # We keep track of the last "ready" state to only print a message when we transition into or 
    # out of the ready state. This prevents spamming the debug output with repeated "ALL SYSTEMS OK" 
    # messages when we're already in that state, while still allowing us to see when we first achieve 
    # a ready state after startup or after recovering from an issue.
    last_ready_state = False

    while True:
        telemetry = shared_data.internal_telemetry_data
        mcu_v = telemetry.get('motorDataValid', False)
        imd_v = telemetry.get('imdDataValid', False)
        
        # 1. Evaluate raw status values into human-readable strings using the status_codes module
        new_mcu = get_mcu_state(telemetry.get('mcuStateRaw', 0), mcu_v)
        new_imd = get_imd_state(telemetry.get('imdStateRaw', 0), imd_v)
        new_vifc = get_vifc_state(telemetry.get('vifcStatusRaw', 0), True)

        #  2. Update central status stack if there are changes in any of the main components (MCU, IMD, VIFC)
        if (telemetry.get('mcuStatus') != new_mcu or 
            telemetry.get('imdStatus') != new_imd or 
            telemetry.get('vifcStatus') != new_vifc):
            
            telemetry['mcuStatus'] = new_mcu
            telemetry['imdStatus'] = new_imd
            telemetry['vifcStatus'] = new_vifc
            
            # We filter out ONLY "OK". "NDT", "SELF T", "IDLE" remain visible to allow you to follow the process.
            new_stack = [s for s in [new_mcu, new_imd, new_vifc] if "OK" not in s]
            
            # 3. System-Ready Check
            # If all three components are "OK", we consider the system ready and show a special 
            # "READY" message instead of cycling through the stack.
            is_ready = (len(new_stack) == 0)
            
            if is_ready:
                # We only set the "READY" message if we are actually ready, otherwise we show the stack
                # of issues. This ensures that we don't accidentally hide important status information 
                # by showing "READY" when we're not actually ready.
                new_stack = [" READY  "] # 8 chars to center it.
            
            # 4. Update the central status stack and reset the display index if there are changes
            if new_stack != shared_data.central_status_stack:
                shared_data.central_status_stack = new_stack
                shared_data.central_display_index = 0
                shared_data.central_dirty_flag = True
                
            # 5. Debug Print on Status Change
            if is_ready != last_ready_state:
                if is_ready:
                    shared_data.debug_print("ALL SYSTEMS OK: Drive enabled.", level=1)
                last_ready_state = is_ready
        
        # 6. Update RND status character for the RND display task
        shared_data.current_rnd_status_char = get_rnd_status(telemetry.get('mcuFlagsRaw', 0), mcu_v)
        
        # Health Check for Watchdog
        shared_data.last_status_task_heartbeat = utime.ticks_ms()
        await asyncio.sleep_ms(200)

async def watchdog_feeder_task():
    """ 
    Safety: Only feeds the hardware watchdog if critical tasks are still running.
    Prevents the system from staying alive if the main loop hangs.
    """
    while True:
        if 'watchdog' in globals() and watchdog:
            now = utime.ticks_ms()
            # Check if Block 1 and Status Task have checked in recently (within 5 seconds)
            b1_alive = utime.ticks_diff(now, getattr(shared_data, 'last_block1_heartbeat', 0)) < 5000
            st_alive = utime.ticks_diff(now, getattr(shared_data, 'last_status_task_heartbeat', 0)) < 5000
            
            if b1_alive and st_alive:
                watchdog.feed()
            else:
                # We stop feeding! Hardware reset will occur after watchdog timeout.
                print("WATCHDOG: Task health check failed. Reset imminent.")
        
        await asyncio.sleep_ms(300)


async def block2_task():
    while True:
        current_time = utime.ticks_ms()
        if utime.ticks_diff(current_time, shared_data.last_odometer_display_update_time) >= DISPLAY_UPDATE_PERIOD_MS:
            try:
                await display_manager.update_odometer_display(shared_data)
                shared_data.last_odometer_display_update_time = current_time
            except Exception as e:
                shared_data.debug_print(f"ERROR in odometer display: {e}", level=0)
        await asyncio.sleep_ms(DISPLAY_UPDATE_PERIOD_MS)


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
        await asyncio.sleep_ms(DISPLAY_UPDATE_PERIOD_MS)


async def block_rnd_task():
    while True:
        current_time = utime.ticks_ms()
        if utime.ticks_diff(current_time, shared_data.last_rnd_update_time) >= RND_UPDATE_PERIOD_MS:
            try:
                await display_manager.update_rnd_display(shared_data)
                shared_data.last_rnd_update_time = current_time
            except Exception as e:
                shared_data.debug_print(f"ERROR in RND display: {e}", level=0)
        await asyncio.sleep_ms(RND_UPDATE_PERIOD_MS)


 
# BLOCK 6: Odometer saving (Release Optimized)
async def block6_task():
    # Local references for shared_data (speed optimization)
    import utime
    
    while True:
        current_time_ms = utime.ticks_ms()
        speed = shared_data.speed
        last_speed = shared_data.last_speed

        if speed == 0:
            # Transition: Start timer when we first detect that the vehicle has stopped. 
            # We use a timer to ensure that we only save the odometer reading after the vehicle 
            # has been stationary for a certain period (e.g., 2 seconds). 
            # This prevents unnecessary saves during brief stops (like at traffic lights) and 
            # ensures that we capture the final odometer reading when the vehicle is parked.
            if last_speed != 0:
                shared_data.stop_start_time = current_time_ms
                shared_data.odometer_saved_in_stop = False
                shared_data.debug_print("Vehicle stopped – save timer started (2s).", level=2)
            
            # Stop for 2 seconds and save odometer if not already saved
            elif (shared_data.stop_start_time is not None and
                  utime.ticks_diff(current_time_ms, shared_data.stop_start_time) > 2000 and
                  not shared_data.odometer_saved_in_stop):
                try:
                    # Save odometer reading. This should be done only once per stop event, 
                    # which is ensured by the odometer_saved_in_stop flag. After saving, 
                    # we set this flag to True to prevent multiple saves during the same stop 
                    # event, and we reset the stop_start_time to None to prepare for the next stop event.
                    store_km.save_odometer(shared_data.total_km, shared_data.trip_km, shared_data.debug_print)
                    shared_data.odometer_saved_in_stop = True
                    shared_data.stop_start_time = None
                    shared_data.last_save_time = current_time_ms
                    shared_data.debug_print(f"Odometer saved. Total: {shared_data.total_km:.1f} km", level=1)
                except Exception as e:
                    shared_data.debug_print(f"ERROR saving odometer: {e}", level=0)
        else:
            # Car is moving: Reset timer
            shared_data.stop_start_time = None
            shared_data.odometer_saved_in_stop = False

        # Save current speed for next loop iteration to detect transitions between moving 
        # and stopped states. This is crucial for the logic that determines when to start the 
        # stop timer and when to save the odometer reading, ensuring that we only save when 
        # the vehicle has come to a complete stop and has remained stationary for the defined period.
        shared_data.last_speed = speed
        
        # Set interval to 500ms, which is a good balance for responsiveness and resource usage.
        await asyncio.sleep_ms(500)


async def block7_task():
    shared_data.debug_print("BLOCK 7: Task started", level=1)
    
    # Security Check: Wait for Hardware Init
    while button_controller._button_pin is None:
        await asyncio.sleep_ms(200)
    
    shared_data.debug_print("BLOCK 7: Hardware link established!", level=1)

    while True:
        try:
            action = button_controller.get_button_action_and_clear()
            
            if action == "short":
                # switch mode (0-3)
                shared_data.current_display_mode = (shared_data.current_display_mode + 1) % 4
                shared_data.debug_print(f"Mode changed to {shared_data.current_display_mode}")
                
                # refresh display immediately (setting flag is usually enough)
                shared_data.odo_dirty_flag = True

            elif action == "long":
                mode = shared_data.current_display_mode
                shared_data.debug_print(f"DEBUG: Button LONG pressed, current mode is: {mode}")

                # --- SPEED MODE: set pointer to zero ---
                if mode == 0: # DISPLAY_MODE_SPEED
                    try:
                        odometer_motor.odometer_pointer_zero(shared_data.debug_print)
                        shared_data.debug_print("Odometer pointer zeroed.")
                    except Exception as e:
                        shared_data.debug_print(f"ERROR zeroing pointer: {e}")

                # --- TOTAL MODE: Contrast Toggle ---
                elif mode == 1: # DISPLAY_MODE_TOTAL
                    shared_data.current_contrast = 42 if shared_data.current_contrast == 255 else 255
                    shared_data.debug_print(f"Contrast toggled to {shared_data.current_contrast}")

                # --- TRIP MODE: Reset & Save  ---
                elif mode == 2: # DISPLAY_MODE_TRIP
                    shared_data.trip_km = 0.0
                    store_km.save_odometer(shared_data.total_km, shared_data.trip_km, shared_data.debug_print)
                    shared_data.odo_dirty_flag = True
                    shared_data.debug_print("Trip reset and saved.")

                # --- TEMP MODE: Source Toggle ---
                elif mode == 3: # DISPLAY_MODE_TEMP
                    shared_data.temp_show = 1 - shared_data.temp_show
                    shared_data.debug_print(f"Temp source: {'MOTOR' if shared_data.temp_show == 1 else 'MCU'}")

        except Exception as e:
            shared_data.debug_print(f"BLOCK 7 Logic Error: {e}", level=0)

        await asyncio.sleep_ms(20)

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
        await asyncio.sleep_ms(TEMP_GAUGE_UPDATE_PERIOD_MS)


async def block9b_task():
    while True:
        current_time = utime.ticks_ms()
        if utime.ticks_diff(current_time, shared_data.last_valid_motor_time) > DATA_TIMEOUT_MS:
            shared_data.internal_telemetry_data['motorDataValid'] = False
        if utime.ticks_diff(current_time, shared_data.last_valid_imd_time) > DATA_TIMEOUT_MS:
            shared_data.internal_telemetry_data['imdDataValid'] = False
        if utime.ticks_diff(current_time, shared_data.last_valid_data_time) > DATA_TIMEOUT_MS:
            shared_data.internal_telemetry_data['systemStatus'] = 'NO_DATA_TIMEOUT'
        await asyncio.sleep_ms(1000)


async def block_can_tx_task():
    """
    FUTURE FEATURE:
    Periodic broadcast of vehicle data to the CAN bus.
    Frequency: 0.5 Hz (every 2 seconds)
    """
    shared_data.debug_print("Block CAN-TX: Started", level=1)
    while True:
        # Send only if the controller has been initialized
        if can_controller:
            success = can_controller.send_odometer_data(
                shared_data.total_km, 
                shared_data.trip_km
            )
            
            if not success:
                shared_data.debug_print("CAN TX failed (Bus busy or error)", level=0)
        
        # Wait 2 seconds to avoid bus congestion and to provide a reasonable update interval 
        # for other nodes that might be listening for odometer data. This interval can be adjusted 
        # based on the specific requirements of the application and the expected traffic on the 
        # CAN bus, but 2 seconds is a good starting point for periodic updates without overwhelming
        # the bus or consuming excessive resources on the microcontroller.
        await asyncio.sleep_ms(2000)   


# =============================================
# START TASKS
# =============================================
# =============================================
# MODIFIED START_TASKS WITH MEMORY MANAGEMENT
# =============================================
async def start_tasks():
    print("=== start_tasks() entered ===")
    import gc
    # Trigger GC automatically when only 100KB are free
    # This sets a lower threshold for free memory, prompting the garbage collector to run more frequently and prevent fragmentation issues that can arise in long-running applications with many tasks and dynamic memory usage.
    gc.threshold(100 * 1024)

    # Tasks starten
    asyncio.create_task(block1_task())       # Pulse / Speed / Odometer Logic
    asyncio.create_task(block_status_task()) # Status Processor
    asyncio.create_task(watchdog_feeder_task()) # Watchdog Feeder
    asyncio.create_task(block2_task())       # ODO Display
    asyncio.create_task(block3_task())       # Central Display
    asyncio.create_task(block_rnd_task())    # RND Display
    asyncio.create_task(block6_task())       # Odometer Saving
    asyncio.create_task(block7_task())       # Button Controller
    asyncio.create_task(block8_task())       # Temp Gauge
    asyncio.create_task(block9b_task())      # Validity Checker
    
    #asyncio.create_task(block_can_tx_task()) # CAN Odometer Broadcast

    # START CAN RECEIVER TASK
    if can_controller is not None:
        try:
            asyncio.create_task(can_controller.receiver_task())
            print("DEBUG: CAN Receiver Task pushed to Loop")
        except Exception as e:
            print(f"DEBUG: Failed to start CAN Task: {e}")
    else:
        print("DEBUG: CAN Controller is NONE - check hardware_init!")
        
    # --- MAIN MONITOR LOOP ---
    counter = 0
    while True:
        counter += 1
        import gc
        
        # proactive cleanup remains important for long-term stability, especially in a complex application with multiple tasks and dynamic memory usage. By calling gc.collect() regularly, we can help prevent memory fragmentation and ensure that we have enough free memory for new allocations, which is crucial for the smooth operation of the system over time.
        gc.collect()
        
        # check RAM every 2 seconds and only print if it's critically low, to avoid flooding the debug output while still keeping an eye on memory health.
        free = gc.mem_free()
        
        # 1. critical threshold at 40KB free memory
        if free < 40000: # Schwelle etwas gesenkt für Release
            import micropython
            print(f"!!! RELEASE WARNING: Low RAM detected: {free} bytes !!!")
            micropython.mem_info()
        
        # 2. heartbeat: Show a heartbeat every 60 seconds to indicate the system is alive and to provide a regular RAM status update. This can be helpful for long-term monitoring without overwhelming the debug output with too frequent messages.
        # Helpful for when you connect the laptop for inspection, to see that the system is still alive and to get a regular update on RAM status without flooding the debug output.
        if counter % 30 == 0: # 30 * 2000ms = 60 Sekunden
            stack_size = len(shared_data.central_status_stack)
            print(f"HB | RAM: {free} | Stack: {stack_size}")

        # 3. Automatic Recovery: If free memory drops below 20KB, we trigger a system reset to attempt recovery from a low-memory state. This is a last-resort safety net to prevent the system from becoming unresponsive due to memory exhaustion, especially in scenarios where the application might encounter unexpected conditions leading to increased memory usage.
        # If free memory drops below 20KB, we trigger a system reset to attempt recovery from a low-memory state. This is a last-resort safety net to prevent the system from becoming unresponsive due to memory exhaustion, especially in scenarios where the application might encounter unexpected conditions leading to increased memory usage.
        if len(shared_data.central_status_stack) > 20:
            print("ERROR: Status Stack overflow, clearing...")
            shared_data.central_status_stack = []

        await asyncio.sleep_ms(2000)


def run_app():
    print("=== run_app() called - starting asyncio ===")
    try:
        asyncio.run(start_tasks())
    except Exception as e:
        print(f"FATAL ERROR: {e}")
        import sys
        sys.print_exception(e)
        reset()


print("=== Point D: Calling run_app() ===")
run_app()