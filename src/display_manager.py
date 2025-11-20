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

# font_small = MyFont('small') # 12x16 Pixel: Assignment happens in main
# font_large = MyFont('large') # 16x21 Pixel: Assignment happens in main

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
    
    # NEW Y-COORDINATE for 21px high fonts: (32 - 21) // 2 = 5
    Y_LARGE_FONT = 5
    
    # --- 3. Mode handling ---
    mode = shared_data.current_display_mode
    char_changed = False
    dirty_x0, dirty_y0 = 128, 32  # Start with invalid rect
    dirty_x1, dirty_y1 = 0, 0
    
    # Flag indicating whether a full redraw (Mode/Contrast Change) is necessary
    full_redraw_needed = False 

    # Force full redraw on mode change
    if mode != shared_data.last_displayed_mode:
        shared_data.odo_dirty_flag = True
        shared_data.last_displayed_mode = mode

    # CORRECTION for overlaps: On mode or contrast change (dirty_flag=True) 
    # the entire screen MUST be cleared.
    if shared_data.odo_dirty_flag:
        odometer.fill(0) # Full buffer clear (128x32)
        full_redraw_needed = True
        shared_data.debug_print("Odometer: Full buffer clear due to mode/contrast change.", level=2)

    try:
        # Modes that use the 16x21 font
        if mode == DISPLAY_MODE_SPEED:
            X_SPEED_START = 44
            
            # Check if redrawing is necessary (due to Full Redraw OR text change)
            if full_redraw_needed or speed_str != shared_data.last_displayed_speed_str:
                char_changed = True
                
                # If NO Full Redraw occurred (only text change), we must clear the old text.
                if not full_redraw_needed:
                    # Only text change within the same mode: partial clearing
                    odometer.fill_rect(X_SPEED_START, Y_LARGE_FONT, 128 - X_SPEED_START, 21, 0)
                    odometer.fill_rect(97, 19, 8 * 4, 8, 0) # Clear unit km/h
                    
                font_large.text(speed_str, X_SPEED_START, Y_LARGE_FONT, 1, display=odometer)
                odometer.text("km/h", 97, 19) 
                
                shared_data.last_displayed_speed_str = speed_str
                
                # Dirty rect for partial update, if only text changed
                dirty_x0, dirty_x1 = X_SPEED_START, 127 
                dirty_y0, dirty_y1 = Y_LARGE_FONT, 31 
                
        elif mode == DISPLAY_MODE_TOTAL:
            X_TOTAL_START = 0 
            if full_redraw_needed or km_str != shared_data.last_displayed_km_str:
                char_changed = True
                
                if not full_redraw_needed:
                    # Only text change within the same mode: partial clearing
                    odometer.fill_rect(0, Y_LARGE_FONT, 128, 21, 0) # Clear large font area
                    odometer.fill_rect(97, 19, 8 * 2, 8, 0) # Clear unit km
                
                # NEW: 16x21 font for Total-KM (6 characters * 16px/char = 96px width)
                font_large.text(km_str, X_TOTAL_START, Y_LARGE_FONT, 1, display=odometer)
                
                # CORRECTION: Standard 8x8 font for the unit
                odometer.text("km", 100, 19)
                
                shared_data.last_displayed_km_str = km_str
                
                dirty_x0, dirty_x1 = X_TOTAL_START, 127 
                dirty_y0, dirty_y1 = Y_LARGE_FONT, 31

        elif mode == DISPLAY_MODE_TRIP:
            X_TRIP_START = 16
            trip_val = shared_data.trip_km
            trip_str = f"{trip_val:.1f}" if trip_val >= 1000 else f"{trip_val:05.1f}"
            
            if full_redraw_needed or trip_str != shared_data.last_displayed_trip_str:
                char_changed = True
                
                if not full_redraw_needed:
                    # Only text change within the same mode: partial clearing
                    odometer.fill_rect(X_TRIP_START, Y_LARGE_FONT, 128 - X_TRIP_START, 21, 0)
                    odometer.fill_rect(97, 19, 8 * 2, 8, 0) # Clear unit km
                
                font_large.text(trip_str, X_TRIP_START, Y_LARGE_FONT, 1, display=odometer)
                odometer.text("km", 100, 19)
                
                shared_data.last_displayed_trip_str = trip_str
                
                dirty_x0, dirty_x1 = X_TRIP_START, 127
                dirty_y0, dirty_y1 = Y_LARGE_FONT, 31

        elif mode == DISPLAY_MODE_TEMP:
            source_changed = (shared_data.temp_show != shared_data.last_displayed_temp_source)
            if full_redraw_needed or source_changed:
                char_changed = True
                
                temp_source_str = "MOTOR" if shared_data.temp_show == 1 else "MCU"
                
                if not full_redraw_needed:
                    odometer.fill_rect(0, 8, 128, 16, 0) # Clear middle-Zone (Small Font Area)
                
                # NEW: Standard call with the SMALL font
                font_small.text(temp_source_str, 40, 8, 1, display=odometer)
                
                shared_data.last_displayed_temp_source = shared_data.temp_show
                
                dirty_x0, dirty_x1 = 40, 100
                dirty_y0, dirty_y1 = 8, 23

        # --- 4. Show only if changed, using Dirty-Rect or Full Redraw ---
        if full_redraw_needed or char_changed:
            try:
                if full_redraw_needed:
                    # Full screen redraw (e.g. contrast or mode change)
                    odometer.show()
                    shared_data.debug_print("Odometer: full screen update (mode/contrast)", level=2)
                else:
                    # Only update the affected text area (within the mode)
                    # Ensure coordinates are valid (Dirty Rect is only used when char_changed)
                    if dirty_x0 < dirty_x1 and dirty_y0 < dirty_y1:
                        odometer.show(dirty_x0, dirty_y0, dirty_x1, dirty_y1)
                        shared_data.debug_print(f"Odometer: dirty rect ({dirty_x0},{dirty_y0},{dirty_x1},{dirty_y1})", level=3)
                    else:
                        # Fallback for invalid Dirty Rect (should not happen)
                        odometer.show() 
                        shared_data.debug_print("Odometer: dirty rect fallback to full show", level=3)

                shared_data.odo_dirty_flag = False # Set flag to False after successful show
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
    Only the top row (y=0–15) is updated -> no flicker.
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
            font_small.text(" BERTONE ", 0, 0, 1, display=central)
            shared_data.central_init_step = 2
            shared_data.central_dirty_flag = True
        elif shared_data.central_init_step == 2:
            central.show()
            shared_data.central_init_step = 0
            shared_data.central_dirty_flag = False
        return

    # --- NORMAL DISPLAY ---
    # If an inversion feature for Central is added in the future, 
    # call invert(0) here if necessary. Currently: only tracking.
    if shared_data.central_last_invert_state != 0:
        pass

    # --- Draw permanent subtext once (bottom row) ---
    if not _subtext_drawn:
        central.fill_rect(0, 16, 128, 16, 0)  # Clear bottom row
        central.text("MOTOR", 0, 18)
        central.text("MCU", 55, 18)
        central.text("ISO-R", 90, 18)
        _subtext_drawn = True
        # Show bottom row once
        try:
            central.show(0, 16, 127, 31)
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

        motor_text = f"{motor_temp:>2d}c" if motor_valid else "--c" # c will be replaced by °C
        font_small.text(motor_text, 0, 0, 1, display=central)
        shared_data.last_displayed_motor_temp = motor_temp

        mcu_text = f"{mcu_temp:>2d}c" if motor_valid else "--c"     # ° will be replaced by °C
        font_small.text(mcu_text, 46, 0, 1, display=central)
        shared_data.last_displayed_mcu_temp = mcu_temp

        iso_text = f"{imd_iso_r // 1000:>2d}m" if imd_valid else "--m"  # ® will be replaced by MOhm for Ohm = Omega
        font_small.text(iso_text, 92, 0, 1, display=central)
        shared_data.last_displayed_imd_iso_r = imd_iso_r

        # Show only top row
        try:
            central.show(0, 0, 127, 15)
            shared_data.debug_print("Central: top row updated", level=2)
        except OSError as e:
            shared_data.debug_print(f"ERROR: I2C error in central.show(): {e}", level=0)

        shared_data.central_dirty_flag = False

# === RND DISPLAY ===
async def update_rnd_display(shared_data):
    """
    Update the RND display (64x32) with gear (R, N, D).
    Uses manual color management for local inversion of the character area only.
    Box size is 20x29 pixels.
    """
    global rnd
    global font_large 
    if rnd is None:
        return

    # --- Geometry for 64x32 Display ---
    # Desired box size: 20x29 pixels (contains the 16x21 font + 2px/4px margin)
    RND_BOX_WIDTH = 20
    RND_BOX_HEIGHT = 29
    
    # Box start coordinates (centered in 64x32)
    X_BOX_START = (rnd_width - RND_BOX_WIDTH) // 2 # (64 - 20) / 2 = 22
    Y_BOX_START = (rnd_height - RND_BOX_HEIGHT) // 2 # (32 - 29) / 2 = 1 (or 2, we take 1 for the center)
    
    # Text start coordinates (centered in the box)
    X_TEXT_START = X_BOX_START + (RND_BOX_WIDTH - 16) // 2 # 22 + 2 = 24
    Y_TEXT_START = Y_BOX_START + (RND_BOX_HEIGHT - 21) // 2 # 1 + 4 = 5 (Perfect center)
    
    # Dirty Rect End coordinates (corresponds to box size)
    X_BOX_END = X_BOX_START + RND_BOX_WIDTH - 1 # 22 + 20 - 1 = 41
    Y_BOX_END = Y_BOX_START + RND_BOX_HEIGHT - 1 # 1 + 29 - 1 = 29
    
    # --- 1. Update contrast ---
    if shared_data.current_contrast != shared_data.rnd_last_contrast:
        rnd.contrast(shared_data.current_contrast)
        shared_data.rnd_last_contrast = shared_data.current_contrast
        shared_data.rnd_dirty_flag = True

    # --- 2. Determine gear character ---
    motor_data_valid = shared_data.internal_telemetry_data.get('motorDataValid', False)
    rnd_char = shared_data.current_rnd_status_char if motor_data_valid else ' '

    # --- 3. Determine colors and inversion style (Manual Inversion) ---
    invert_state = 1 if rnd_char == 'R' else 0
    
    if rnd_char == 'R':
        # Reverse Mode: Inverted (Black text on White field)
        char_fg_color = 0 # Text is Black
        char_bg_color = 1 # Box is White
    else:
        # Normal Mode: Normal (White text on Black field)
        char_fg_color = 1 # Text is White
        char_bg_color = 0 # Box is Black (matching the display background)
        
    # Check if the style (R <-> N/D) has changed to force a redraw
    invert_changed = (shared_data.rnd_last_invert_state != invert_state)
    if invert_changed:
        shared_data.rnd_last_invert_state = invert_state
        shared_data.rnd_dirty_flag = True # Force redraw due to style change

    # --- 4. Update only if character or style changed ---
    char_changed = (rnd_char != shared_data.rnd_last_displayed_char)

    if char_changed or shared_data.rnd_dirty_flag:
        
        # 1. Fill the area with the calculated background color (0 or 1)
        # Use the new box coordinates and dimensions
        rnd.fill_rect(X_BOX_START, Y_BOX_START, RND_BOX_WIDTH, RND_BOX_HEIGHT, char_bg_color)
        
        # 2. Draw the text with the calculated foreground color (1 or 0)
        # Use the new, centered text coordinates
        font_large.text(rnd_char, X_TEXT_START, Y_TEXT_START, char_fg_color, display=rnd) 
        
        shared_data.rnd_last_displayed_char = rnd_char
        shared_data.rnd_dirty_flag = False

        # Show only the 20x29 box area (Dirty Rect)
        try:
            rnd.show(X_BOX_START, Y_BOX_START, X_BOX_END, Y_BOX_END)
            shared_data.debug_print("RND: gear updated (dirty rect, 20x29 box)", level=2)
        except OSError as e:
            shared_data.debug_print(f"ERROR: I2C error in rnd.show(): {e}", level=0)
            rnd = None