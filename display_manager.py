# display_manager.py
from myfont import MyFont
import gc
# Import status code helper functions for central display
from status_codes import get_mcu_state, get_imd_state, get_vifc_state, get_rnd_status

def _get_ticks_ms():
    import utime
    return utime.ticks_ms()

def _ticks_diff(now, then):
    import utime
    return utime.ticks_diff(now, then)

# --- Global Display Objects ---
central = None
rnd = None
odometer = None

# --- Display Modes ---
DISPLAY_MODE_SPEED = 0
DISPLAY_MODE_TOTAL = 1
DISPLAY_MODE_TRIP = 2
DISPLAY_MODE_TEMP = 3

# === ODOMETER DISPLAY ===
async def update_odometer_display(shared_data):
    global odometer, font_large, font_small 
    if odometer is None: return

    if shared_data.current_contrast != shared_data.odo_last_contrast:
        odometer.contrast(shared_data.current_contrast)
        shared_data.odo_last_contrast = shared_data.current_contrast
        shared_data.odo_dirty_flag = True

    mode = shared_data.current_display_mode
    char_changed = False
    full_redraw_needed = False
    Y_LARGE_FONT = 4
    dx0, dy0, dx1, dy1 = 128, 32, 0, 0

    if mode != shared_data.last_displayed_mode or shared_data.odo_dirty_flag:
        odometer.fill(0)
        full_redraw_needed = True
        shared_data.last_displayed_mode = mode
        shared_data.odo_dirty_flag = False

    if mode == DISPLAY_MODE_SPEED:
        speed_str = f"{shared_data.digital_speed:>3}"
        if full_redraw_needed or speed_str != shared_data.last_displayed_speed_str:
            if not full_redraw_needed: odometer.fill_rect(44, Y_LARGE_FONT, 84, 24, 0)
            font_large.text(speed_str, 44, Y_LARGE_FONT, 1, display=odometer)
            odometer.text("km/h", 97, 21)
            shared_data.last_displayed_speed_str = speed_str
            char_changed, dx0, dy0, dx1, dy1 = True, 44, Y_LARGE_FONT, 127, 31
    elif mode == DISPLAY_MODE_TOTAL:
        km_str = f"{int(shared_data.total_km):06d}"
        if full_redraw_needed or km_str != shared_data.last_displayed_km_str:
            if not full_redraw_needed: odometer.fill_rect(0, Y_LARGE_FONT, 128, 24, 0)
            font_large.text(km_str, 0, Y_LARGE_FONT, 1, display=odometer)
            odometer.text("km", 100, 21)
            shared_data.last_displayed_km_str = km_str
            char_changed, dx0, dy0, dx1, dy1 = True, 0, Y_LARGE_FONT, 127, 31
    elif mode == DISPLAY_MODE_TRIP:
        t_val = shared_data.trip_km
        trip_str = f"{t_val:.1f}" if t_val >= 1000 else f"{t_val:05.1f}"
        if full_redraw_needed or trip_str != shared_data.last_displayed_trip_str:
            if not full_redraw_needed: odometer.fill_rect(16, Y_LARGE_FONT, 112, 24, 0)
            font_large.text(trip_str, 16, Y_LARGE_FONT, 1, display=odometer)
            odometer.text("km", 100, 21)
            shared_data.last_displayed_trip_str = trip_str
            char_changed, dx0, dy0, dx1, dy1 = True, 16, Y_LARGE_FONT, 127, 31
    elif mode == DISPLAY_MODE_TEMP:
        if full_redraw_needed or (shared_data.temp_show != shared_data.last_displayed_temp_source):
            temp_source_str = "MOTOR" if shared_data.temp_show == 1 else "MCU"
            odometer.fill_rect(0, 8, 128, 16, 0)
            font_small.text(temp_source_str, 40, 8, 1, display=odometer)
            shared_data.last_displayed_temp_source = shared_data.temp_show
            char_changed, dx0, dy0, dx1, dy1 = True, 0, 8, 127, 23

    if full_redraw_needed or char_changed:
        try:
            if full_redraw_needed: odometer.show()
            elif dx0 < dx1: odometer.show(dx0, dy0, dx1, dy1)
            gc.collect()
        except OSError: pass

# === CENTRAL DISPLAY ===
async def update_central_display(shared_data):
    global central, font_small
    if central is None: return

    if shared_data.current_contrast != shared_data.central_last_contrast:
        central.contrast(shared_data.current_contrast)
        shared_data.central_last_contrast = shared_data.current_contrast
        shared_data.central_dirty_flag = True

    current_time = _get_ticks_ms()
    telemetry = shared_data.internal_telemetry_data
    data_timestamp = shared_data.last_valid_data_time
    
    display_text = "BERTONE" # Default

    if data_timestamp == 0:
        display_text = "NO VCU"
        shared_data.central_ok_start_time = current_time 
    elif _ticks_diff(current_time, data_timestamp) > 8000:
        display_text = "COM ERR"
    else:
        # Get status strings for each component using the raw flags and validity from telemetry
        mcu_s = get_mcu_state(telemetry.get('mcuFlagsRaw'), telemetry.get('motorDataValid', False))
        imd_s = get_imd_state(telemetry.get('imdStateRaw'), telemetry.get('imdDataValid', False))
        vifc_s = get_vifc_state(telemetry.get('vifcStatusRaw'), telemetry.get('vifcDataValid', False))

        if shared_data.central_boot_active:
            boot_steps = [mcu_s, imd_s, vifc_s]
            elapsed = _ticks_diff(current_time, shared_data.central_ok_start_time)
            step_idx = elapsed // 2000
            
            if step_idx < len(boot_steps):
                # Show the status text (e.g., "MCU OK" or "MCU NDT")
                display_text = boot_steps[step_idx]
            else:
                shared_data.central_boot_active = False
                display_text = "BERTONE"
        else:
            # Evaluate active errors and cycle through them if present, otherwise show "BERTONE"
            active_errors = []
            for s in [mcu_s, imd_s, vifc_s]:
                if "OK" not in s and "WAIT" not in s:
                    active_errors.append(s)

            if active_errors:
                idx = (current_time // 2000) % len(active_errors)
                display_text = active_errors[idx]
            else:
                display_text = "BERTONE"

    if getattr(shared_data, 'last_central_text', "") != display_text or shared_data.central_dirty_flag:
        try:
            central.fill(0)
            font_small.text(display_text, 0, 0, 1, display=central)
            central.show()
            shared_data.last_central_text = display_text
            shared_data.central_dirty_flag = False
            gc.collect() # SW-I2C Cleanup
        except: pass

# === RND DISPLAY ===
async def update_rnd_display(shared_data):
    global rnd, font_large
    if rnd is None: return

    if shared_data.current_contrast != shared_data.rnd_last_contrast:
        rnd.contrast(shared_data.current_contrast)
        shared_data.rnd_last_contrast = shared_data.current_contrast
        shared_data.rnd_dirty_flag = True

    rnd_char = get_rnd_status(
        shared_data.internal_telemetry_data.get('mcuFlagsRaw'), 
        shared_data.internal_telemetry_data.get('motorDataValid', False)
    )

    invert_state = 1 if rnd_char == 'R' else 0
    if (rnd_char != shared_data.rnd_last_displayed_char) or (shared_data.rnd_last_invert_state != invert_state) or shared_data.rnd_dirty_flag:
        
        char_fg = 0 if invert_state else 1
        char_bg = 1 if invert_state else 0
        
        rnd.fill_rect(22, 1, 20, 30, char_bg)
        font_large.text(rnd_char, 24, 5, char_fg, display=rnd) 
        
        shared_data.rnd_last_displayed_char = rnd_char
        shared_data.rnd_last_invert_state = invert_state
        shared_data.rnd_dirty_flag = False

        try:
            rnd.show(22, 1, 41, 30)
            gc.collect() # SW-I2C Cleanup
        except: pass