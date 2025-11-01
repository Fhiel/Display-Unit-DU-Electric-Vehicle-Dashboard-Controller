# status_codes.py

# === RND FLAGS, displayed on rnd ===
# Bits 2 and 3 of mcuFlags → 0..3
_RND_MAP = {
    0: "N",  # Neutral
    1: "R",  # Reverse
    2: "D",  # Drive
    # 3: not valid → no show
}

def get_rnd_status(mcu_flags: int) -> str:
    """Evaluates the RND flags (bits 2 and 3 of mcuFlags)."""
    rnd_value = (mcu_flags >> 2) & 0x03
    return _RND_MAP.get(rnd_value, " ")  # invalid → show nothing


# === MCU STATES, displayed on central (max. 10 characters) ===
def get_mcu_state(mcu_flags: int) -> str:
    """Evaluates the most important MCU status bits and returns max. 10 characters."""
    if mcu_flags & 0x08:  # Bit 3
        return "MCU WARN"
    if mcu_flags & 0x04:  # Bit 2
        return "MCU LIMIT"
    if mcu_flags & 0x02:  # Bit 1
        return "MCU STOP"
    if mcu_flags & 0x01:  # Bit 0
        return "MCU BLOCK"
    return "MCU OK"


# === IMD STATES, displayed on central (max. 10 characters) ===
def get_imd_state(imd_status: int) -> str:
    """Evaluates IMD status and returns max. 10 characters."""
    iso_error = bool(imd_status & (1 << 0)) or bool(imd_status & (1 << 1))
    imd_error = bool(imd_status & (1 << 2))
    warn = bool(imd_status & (1 << 5))
    calib = bool(imd_status & (1 << 3))
    test = bool(imd_status & (1 << 4))

    if iso_error or (warn and (calib or test)):
        return "ISO ERROR"
    if imd_error:
        return "IMD ERROR"
    if warn:
        return "IMD WARN"
    if test:
        return "IMD TEST"
    if calib:
        return "IMD CALIB"
    return "IMD OK"


# === VIFC STATES, displayed on central (max. 10 characters) ===
def get_vifc_state(vifc_status: int) -> str:
    """Evaluates VIFC status and returns max. 10 characters."""
    bits = {
        'iso_meas_active':       bool(vifc_status & (1 << 0)),
        'imc_connection_err':    bool(vifc_status & (1 << 1)),
        'imc_alive_err':         bool(vifc_status & (1 << 2)),
        'vifc_cmd_err':          bool(vifc_status & (1 << 4)),
        'iso_r_stale':           bool(vifc_status & (1 << 8)),
        'imc_self_test_overall': bool(vifc_status & (1 << 12)),
        'imc_self_test_param':   bool(vifc_status & (1 << 13)),
    }

    if bits['imc_connection_err'] or bits['imc_alive_err'] or bits['vifc_cmd_err']:
        return "VI COM ERR"
    if bits['iso_r_stale']:
        return "VI STALE"
    if bits['imc_self_test_overall'] or bits['imc_self_test_param']:
        return "VI TST ERR"
    if not bits['iso_meas_active']:
        return "VI ISO ON"
    return "VIFC OK"