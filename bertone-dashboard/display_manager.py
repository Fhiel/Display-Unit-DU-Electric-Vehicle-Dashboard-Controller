# display_manager.py
# display logic for Odometer, Central, and RND
# Optimized with Dirty-Rect, permanent subtext, async-safe, debug_print
# Compatible with SSD1306_I2C, myfont.py (blit version), and main.py

import utime
from myfont import MyFont

# --- Global Display Objects (set in main.py) ---
central = None
rnd = None
odometer = None

font_small = MyFont('small')  # 12x16 Pixel
font_large = MyFont('large')  # 16x21 Pixel

# --- Display Dimensions ---
central_width = 128
central_height = 32
odo_width = 128
odo_height = 32
rnd_width = 64
rnd_height = 32

# --- Display Modes ---
DISPLAY_MODE_SPEED = 0
DISPLAY_MODE_TOTAL = 1
DISPLAY_MODE_TRIP = 2
DISPLAY_MODE_TEMP = 3

# --- Configuration ---
CENTRAL_BOOT_DURATION_MS = 5000
R_ISO_MIN = 0
R_ISO_MAX = 50000
R_ISO_WARNING = 400
R_ISO_ERROR = 250

# --- Central Subtext: Permanent labels (drawn once) ---
_subtext_drawn = False  # Local flag: ensures subtext is drawn only once


# === ODOMETER DISPLAY (with 16x21 characters and 8x8 standard text) ===
async def update_odometer_display(shared_data):
    """
    Update the Odometer display (128x32) with speed, total km, trip, or temp source.
    Uses Dirty-Rect to update only the changed text region.
    """
    global odometer
    global font_large, font_small 

    if odometer is None:
        shared_data.debug_print("ERROR: Odometer display object is None", level=0)
        return

    # --- 1. Update contrast if changed ---
    if shared_data.current_contrast != shared_data.odo_last_contrast:
        odometer.contrast(shared_data.current_contrast)
        shared_data.odo_last_contrast = shared_data.current_contrast
        shared_data.odo_dirty_flag = True

    # --- 2. Prepare data strings ---
    speed_str = f"{shared_data.digital_speed:>3}"
    km_str = f"{int(shared_data.total_km):06d}"
    
    # NEUE Y-KOORDINATE für 21px hohe Fonts: (32 - 21) // 2 = 5
    Y_LARGE_FONT = 5
    
    # --- 3. Mode handling ---
    mode = shared_data.current_display_mode
    char_changed = False
    dirty_x0, dirty_y0 = 128, 32  # Start with invalid rect
    dirty_x1, dirty_y1 = 0, 0

    # Force full redraw on mode change
    if mode != shared_data.last_displayed_mode:
        shared_data.odo_dirty_flag = True
        shared_data.last_displayed_mode = mode

    try:
        # Modes, die auf 16x21 umgestellt werden sollen
        if mode == DISPLAY_MODE_SPEED:
            X_SPEED_START = 44 # 92 (Ende) - 48 (3 Zif x 16px) = 44
            if shared_data.odo_dirty_flag or speed_str != shared_data.last_displayed_speed_str:
                char_changed = True
                odometer.fill_rect(0, Y_LARGE_FONT, 128, 21, 0) # Clear middle row

                odometer.text(speed_str, X_SPEED_START, Y_LARGE_FONT, 1, font=font_large)
                
                odometer.text("km/h", 97, 17) 
                
                shared_data.last_displayed_speed_str = speed_str
                dirty_x0, dirty_x1 = X_SPEED_START, 127  # Von Speed digits (52) bis Ende der Einheit
                dirty_y0, dirty_y1 = Y_LARGE_FONT, 31    # Gesamte Zeile 5 bis 31 (um 21px Font + Einheit abzudecken)

        elif mode == DISPLAY_MODE_TOTAL:
            X_TOTAL_START = 0 
            if shared_data.odo_dirty_flag or km_str != shared_data.last_displayed_km_str:
                char_changed = True
                odometer.fill_rect(0, 0, 128, 21, 0) # Clear middle row

                # NEU: 16x21 Font für Total-KM (6 Zeichen * 16px/Zeichen = 96px Breite)
                odometer.text(km_str, X_TOTAL_START, Y_LARGE_FONT, 1, font=font_large)
                
                # KORREKTUR: Standard 8x8 Font für die Einheit
                odometer.text("km", 97, 17)
                
                shared_data.last_displayed_km_str = km_str
                dirty_x0, dirty_x1 = X_TOTAL_START, 127  # Von KM digits (16) bis Ende der Einheit
                dirty_y0, dirty_y1 = Y_LARGE_FONT, 31

        elif mode == DISPLAY_MODE_TRIP:
            X_TRIP_START = 28
            X_UNIT_TOTAL = 97

            trip_val = shared_data.trip_km
            trip_str = f"{trip_val:.1f}" if trip_val >= 1000 else f"{trip_val:05.1f}"
            if shared_data.odo_dirty_flag or trip_str != shared_data.last_displayed_trip_str:
                char_changed = True
                odometer.text(trip_str, X_TRIP_START, Y_LARGE_FONT, 1, font=font_large)
                
                odometer.text("km", 97, 17)
                
                shared_data.last_displayed_trip_str = trip_str
                dirty_x0, dirty_x1 = X_TRIP_START, 127
                dirty_y0, dirty_y1 = Y_LARGE_FONT, 31

        elif mode == DISPLAY_MODE_TEMP:
            source_changed = (shared_data.temp_show != shared_data.last_displayed_temp_source)
            if shared_data.odo_dirty_flag or source_changed:
                temp_source_str = "MOTOR" if shared_data.temp_show == 1 else "MCU"
                odometer.fill_rect(0, 8, 128, 21, 0) # Clear middle-Zone
                
                # NEU: Standardaufruf mit der SMALL Font
                odometer.text(temp_source_str, 40, 8, 1, font=font_small)
                
                shared_data.last_displayed_temp_source = shared_data.temp_show
                char_changed = True
                dirty_x0, dirty_x1 = 40, 100
                dirty_y0, dirty_y1 = 8, 23

        # --- 4. Show only if changed, using Dirty-Rect ---
        if shared_data.odo_dirty_flag or char_changed:
            try:
                if shared_data.odo_dirty_flag:
                    # Full screen redraw (z.B. Kontrast- oder Modus-Wechsel)
                    odometer.show()
                    shared_data.debug_print("Odometer: full screen update", level=2)
                else:
                    # Nur den betroffenen Textbereich aktualisieren
                    odometer.show(x0=dirty_x0, y0=dirty_y0, x1=dirty_x1, y1=dirty_y1)
                    shared_data.debug_print(f"Odometer: dirty rect ({dirty_x0},{dirty_y0},{dirty_x1},{dirty_y1})", level=3)
                shared_data.odo_dirty_flag = False
            except OSError as e:
                shared_data.debug_print(f"ERROR: I2C error in odometer.show(): {e}", level=0)
                odometer = None

    except Exception as e:
        shared_data.debug_print(f"ERROR in update_odometer_display: {e}", level=0)

# === CENTRAL DISPLAY ===
async def update_central_display(shared_data):
    """
    Update the Central display (128x32) with motor temp, MCU temp, and ISO-R.
    Subtext ("MOTOR", "MCU", "ISO-R") is drawn once and preserved.
    Only the top row (y=0–15) is updated → no flicker.
    """
    global central, _subtext_drawn
    if central is None:
        return

    # --- 1. Update contrast ---
    if shared_data.current_contrast != shared_data.central_last_contrast:
        central.contrast(shared_data.current_contrast)
        shared_data.central_last_contrast = shared_data.current_contrast
        shared_data.central_dirty_flag = True

    current_time = utime.ticks_ms()

    # --- BOOT SEQUENCE ---
    if shared_data.central_boot_active:
        if utime.ticks_diff(current_time, shared_data.central_ok_start_time) > CENTRAL_BOOT_DURATION_MS:
            shared_data.central_boot_active = False
            shared_data.central_init_step = 0
            shared_data.central_dirty_flag = True
        elif shared_data.central_init_step == 0:
            central.fill_rect(0, 0, 128, 16, 0)
            shared_data.central_init_step = 1
            shared_data.central_dirty_flag = True
        elif shared_data.central_init_step == 1:
            central.text(" BERTONE ", 0, 0, 1, font=font_small)
            shared_data.central_init_step = 2
            shared_data.central_dirty_flag = True
        elif shared_data.central_init_step == 2:
            central.show()
            shared_data.central_init_step = 0
            shared_data.central_dirty_flag = False
        return

    # --- NORMAL DISPLAY ---
    if shared_data.central_last_invert_state != 0:
        central.invert(0)
        shared_data.central_last_invert_state = 0
        shared_data.central_dirty_flag = True

    # --- Draw permanent subtext once (bottom row) ---
    if not _subtext_drawn:
        central.fill_rect(0, 16, 128, 16, 0)  # Clear bottom row
        central.text("MOTOR", 0, 18)
        central.text("MCU", 58, 18)
        central.text("ISO-R", 90, 18)
        _subtext_drawn = True
        # Show bottom row once
        try:
            central.show(x0=0, y0=16, x1=127, y1=31)
            shared_data.debug_print("Central: subtext drawn permanently", level=2)
        except OSError as e:
            shared_data.debug_print(f"ERROR: I2C error in central subtext show(): {e}", level=0)

    # --- Get telemetry ---
    telemetry = shared_data.internal_telemetry_data
    motor_valid = telemetry.get('motorDataValid', False)
    imd_valid = telemetry.get('imdDataValid', False)
    motor_temp = telemetry.get('motorTemp', 0)
    mcu_temp = telemetry.get('mcuTemp', 0)
    imd_iso_r = telemetry.get('imdIsoR', 0)

    values_changed = (
        motor_temp != shared_data.last_displayed_motor_temp or
        mcu_temp != shared_data.last_displayed_mcu_temp or
        imd_iso_r != shared_data.last_displayed_imd_iso_r
    )

    # --- Update only if changed ---
    if values_changed or shared_data.central_dirty_flag:
        central.fill_rect(0, 0, 128, 16, 0)  # Clear top row only

        motor_text = f"{motor_temp:>2d}C" if motor_valid else "--C"
        central.text(motor_text, 0, 0, 1, font=font_small)
        shared_data.last_displayed_motor_temp = motor_temp

        mcu_text = f"{mcu_temp:>2d}C" if motor_valid else "--C"
        central.text(mcu_text, 44, 0, 1, font=font_small)
        shared_data.last_displayed_mcu_temp = mcu_temp

        iso_text = f"{imd_iso_r // 1000:>2d}M" if imd_valid else "--M"
        central.text(iso_text, 93, 0, 1, font=font_small)
        shared_data.last_displayed_imd_iso_r = imd_iso_r

        # Show only top row
        try:
            central.show(x0=0, y0=0, x1=127, y1=15)
            shared_data.debug_print("Central: top row updated", level=2)
        except OSError as e:
            shared_data.debug_print(f"ERROR: I2C error in central.show(): {e}", level=0)

        shared_data.central_dirty_flag = False

# === RND DISPLAY ===
async def update_rnd_display(shared_data):
    """
    Update the RND display (64x32) with gear (R, N, D).
    Uses Dirty-Rect to update only the 16x21 character region.
    Inverted background when in Reverse.
    """
    global rnd
    global font_large 
    if rnd is None:
        return

    X_START = 24  # (64 - 16) // 2
    Y_START = 5   # (32 - 21) // 2
    X_END = 39    # X_START + 16 - 1
    Y_END = 25    # Y_START + 21 - 1
    
    # --- 1. Update contrast ---
    if shared_data.current_contrast != shared_data.rnd_last_contrast:
        rnd.contrast(shared_data.current_contrast)
        shared_data.rnd_last_contrast = shared_data.current_contrast
        shared_data.rnd_dirty_flag = True

    # --- 2. Determine gear character ---
    motor_data_valid = shared_data.internal_telemetry_data.get('motorDataValid', False)
    rnd_char = shared_data.current_rnd_status_char if motor_data_valid else ' '

    # --- 3. Invert display on Reverse ---
    invert_state = 1 if rnd_char == 'R' else 0
    invert_changed = (shared_data.rnd_last_invert_state != invert_state)

    if invert_changed:
        rnd.invert(invert_state)
        shared_data.rnd_last_invert_state = invert_state
        shared_data.rnd_dirty_flag = True

    # --- 4. Update only if character changed ---
    char_changed = (rnd_char != shared_data.rnd_last_displayed_char)

    if char_changed or shared_data.rnd_dirty_flag:
        rnd.fill_rect(X_START, Y_START, 16, 21, 0)
        
        rnd.text(rnd_char, X_START, Y_START, 1, font=font_large) 
        
        shared_data.rnd_last_displayed_char = rnd_char
        shared_data.rnd_dirty_flag = False

        # Show only the 16x21 character region
        try:
            rnd.show(x0=X_START, y0=Y_START, x1=X_END, y1=Y_END)
            shared_data.debug_print("RND: gear updated (dirty rect)", level=2)
        except OSError as e:
            shared_data.debug_print(f"ERROR: I2C error in rnd.show(): {e}", level=0)
            rnd = None