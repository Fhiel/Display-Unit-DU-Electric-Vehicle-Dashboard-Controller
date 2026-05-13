# status_codes.py

# === RND FLAGS, displayed on rnd display ===
# Bits 2 and 3 of mcuFlags → 0..3
_RND_MAP = {
    0: "N",  # Neutral
    1: "R",  # Reverse
    2: "D",  # Drive
    3: "-",  # Not Ready
}

def get_rnd_status(mcu_flags: int, is_valid: bool = True) -> str:
    """Evaluates the RND flags (bits 2 and 3 of mcuFlags)."""
    if not is_valid or mcu_flags is None:
        return "-"
    
    rnd_value = (mcu_flags >> 2) & 0x03
    return _RND_MAP.get(rnd_value, " ")  # Invalid → show space


# === MCU STATES, displayed on central display (max. 10 chars) ===
def get_mcu_state(mcu_flags: int, is_valid: bool = True) -> str:
    """Evaluates the most important MCU status bits."""
    if not is_valid or mcu_flags is None:
        return "MCU NDT"  # No Data / Not Valid

    # Bitwise evaluation of MCU status
    if mcu_flags & 0x08:  # Bit 3: Warning active
        return "MCU WARN"
    if mcu_flags & 0x04:  # Bit 2: Performance limited
        return "MCU LIMT"
    if mcu_flags & 0x02:  # Bit 1: Stop condition
        return "MCU STOP"
    if mcu_flags & 0x01:  # Bit 0: System blocked
        return "MCU BLOCK"
    
    return "MCU OK"


# === IMD STATES, displayed on central display (max. 10 chars) ===
def get_imd_state(imd_status: int, is_valid: bool = True) -> str:
    """Evaluates Insulation Monitoring Device (IMD) status."""
    if not is_valid or imd_status is None:
        return "IMD NDT"
    
    # IMD Status bits mapping
    iso_error = bool(imd_status & (1 << 0)) or bool(imd_status & (1 << 1))
    imd_error = bool(imd_status & (1 << 2))
    warn      = bool(imd_status & (1 << 5))
    calib     = bool(imd_status & (1 << 3))
    test      = bool(imd_status & (1 << 4))

    if iso_error or (warn and (calib or test)):
        return "IMD ERR"
    if imd_error:
        return "ISO ERR"
    if warn:
        return "ISO WARN"
    if test:
        return "IMD TEST"
    if calib:
        return "IMD CAL"
    
    return "IMD OK"


# === VIFC STATES, displayed on central display (max. 10 chars) ===
def get_vifc_state(vifc_status: int, is_valid: bool = True) -> str:
    """
    Evaluates VIFC status with focus on Bender iso165c1 self-test and connectivity.
    Display limit: 8 characters.
    """
    if not is_valid or vifc_status is None:
        return "VIFC NDT"

    # Status Bit Mapping
    # bit 0: iso_meas_active
    # bit 1, 2, 4: connection/alive/cmd errors
    # bit 8: iso_r_stale
    # bit 12, 13: self-test results
    
    comm_error = bool(vifc_status & 0b10110)      # Bits 1, 2, 4
    self_test  = bool(vifc_status & 0b11000000000000) # Bits 12, 13
    stale      = bool(vifc_status & (1 << 8))
    meas_on    = bool(vifc_status & (1 << 0))

    # --- Priority Evaluation (Critical first) ---
    
    # 1. Hardware/Communication connection lost
    if comm_error:
        return "V-LINK !"

    # 2. Ongoing or failed self-test (Typical during IGNITION ON)
    if self_test:
        return "V-SELF T"

    # 3. Data integrity issues
    if stale:
        return "V-STALE"

    # 4. Inactive measurement (e.g. Bender in Standby)
    if not meas_on:
        return "V-IDLE"  # "IDLE" signifies that VIFC is powered but not actively measuring, which can be normal in certain conditions (e.g., car off but VIFC still powered).

    # 5. All systems nominal
    return "VIFC OK"