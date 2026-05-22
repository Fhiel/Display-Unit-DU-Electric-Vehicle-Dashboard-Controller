# status_codes.py
# =========================================================================
# CENTRAL INTELLIGENCE FOR DASHBOARD TELEMETRY DISPATCHING (8-CHAR SAFE)
# =========================================================================

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
    return _RND_MAP.get(rnd_value, " ")


def get_mcu_state(mcu_flags: int, is_valid: bool = True) -> str:
    """Evaluates the most important MCU status bits."""
    if not is_valid or mcu_flags is None:
        return "MCU NDT"

    if mcu_flags & 0x08: return "MCU WARN"
    if mcu_flags & 0x04: return "MCU LIMT"
    if mcu_flags & 0x02: return "MCU STOP"
    if mcu_flags & 0x01: return "MCU BLOCK"
    
    return "MCU OK"


def get_imd_state(imd_status: int, is_valid: bool = True, bms_status: int = 1, master_alarm: bool = False) -> str:
    """
    Evaluates Insulation Monitoring Device (IMD) status matrix.
    Enforces strict automotive safe-state overrides.
    """
    if not is_valid or imd_status is None:
        return "IMD NDT"
    
    # PRIORITY 1: Master safety alarm from VCU (or manual dashboard light test)
    if master_alarm:
        return "ISO ERR"

    # IMD Hardware Status bits mapping (FIXED: Corrected bitwise definitions)
    iso_error = bool(imd_status & (1 << 0)) # Bit 0: Real Isolation Fault
    chk_chass  = bool(imd_status & (1 << 1)) # Bit 1: Chassis Ground Warning
    imd_fault = bool(imd_status & (1 << 2)) # Bit 2: Internal Device Hardware Fault
    calib     = bool(imd_status & (1 << 3)) # Bit 3: Device Calibration active
    test      = bool(imd_status & (1 << 4)) # Bit 4: Device Self-Test active
    warn      = bool(imd_status & (1 << 5)) # Bit 5: Low-Voltage / Dispersed warning

    # --- Strict Evaluation Cascade ---
    if iso_error:  return "ISO ERR"  # Hard structural insulation fault!
    if imd_fault:  return "IMD ERR"  # Bender hardware circuit error!
    if chk_chass:  return "ISO WARN" # Ground potential shifting
    if warn:       return "ISO WARN"
    if test:       return "IMD TEST"
    if calib:      return "IMD CAL"
    
    # PRIORITY 3: SYSTEM READY CHECK ("OK - GO!" TRIGGER)
    # If no faults are active and BMS enters state READY (0x01: Schütze fahrbereit)
    if bms_status == 1: # BMS_STATUS_READY
        return "OK - GO!" # Trigger word that forces injection without "OK" filter clash

    return "IMD OK"


def get_vifc_state(vifc_status: int, is_valid: bool = True) -> str:
    """Evaluates VIFC status with focus on Bender connection and lifesignals."""
    if not is_valid or vifc_status is None:
        return "VIFC NDT"

    comm_error = bool(vifc_status & 0b10110)      
    self_test  = bool(vifc_status & 0b11000000000000) 
    stale      = bool(vifc_status & (1 << 8))
    meas_on    = bool(vifc_status & (1 << 0))
    
    if comm_error: return "V-LINK !"
    if self_test:  return "V-SELF T"
    if stale:      return "V-STALE"
    if not meas_on: return "V-IDLE"

    return "VIFC OK"