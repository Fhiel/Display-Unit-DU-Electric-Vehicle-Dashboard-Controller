# Persistent odometer storage with double redundancy and CRC8 checksum
# Mounts on /data, safe for RP2040. Assumes successful mount by boot.py.
# NOTE: This module relies on MicroPython v1.23.0 for stable LittleFS operation 
# (Full Flash + progsize=256 configuration must be set in boot.py).

import os
import rp2
import gc 
# time is no longer needed.

# --- Configuration ---
DATA_DIR = "/data"
FILE_PRIMARY = f"{DATA_DIR}/odo1.txt"
FILE_BACKUP = f"{DATA_DIR}/odo2.txt"


# Holds a Python reference to the VFS object (just for safety).
_vfs_obj = None 


# --- CRC8 Checksum ---
def _crc8(data: str) -> int:
    """Simple XOR-based CRC8 for data integrity."""
    crc = 0
    for byte in data.encode('utf-8'):
        # Simple XOR-based CRC8 table
        crc ^= byte
    return crc & 0xFF 


# --- Filesystem Check ---
def _is_mounted(debug_print=None):
    """Checks if the DATA_DIR is accessible (i.e., successfully mounted)."""
    try:
        os.listdir(DATA_DIR)
        return True
    except OSError:
        # If the directory doesn't exist, we can attempt to create it (for first-time setup)
        try:
            os.mkdir(DATA_DIR)
            return True
        except:
            return False

# --- Save Odometer (double redundant) ---
def save_odometer(total_km: float, trip_km: float, debug_print=None):
    """Save total and trip km to both files with CRC8. Returns True if successful, False if critical error (like ENOSPC) persists."""
    
    if not _is_mounted(debug_print):
        if debug_print:
            debug_print("FATAL: Cannot save, filesystem not mounted. Skipping save operation.")
        return False
    
    # The rest of the logic assumes the FS is now stable (via boot.py)
        
    data = f"{total_km:.6f},{trip_km:.6f}"
    checksum = _crc8(data)
    line = f"{data},{checksum}" 

    success_at_least_one = False
    for filepath in [FILE_PRIMARY, FILE_BACKUP]:
        try:
            # LittleFS is Copy-on-Write, that is very safe against power failure
            with open(filepath, "w") as f:
                f.write(line)
            os.sync() 
            success_at_least_one = True
        except Exception as e:
            if debug_print:
                debug_print(f"Write error {filepath}: {e}")
    
    return success_at_least_one

# --- Load Odometer (with validation + fallback) ---
def load_odometer(debug_print=None):
    if not _is_mounted(debug_print):
        return 0.0, 0.0

    def read_file(filepath):
        try:
            with open(filepath, "r") as f:
                line = f.read().strip()
                if not line: return None
                
                parts = line.split(",")
                if len(parts) != 3: return None
                
                total_str, trip_str, crc_str = parts
                if _crc8(f"{total_str},{trip_str}") == int(crc_str):
                    return float(total_str), float(trip_str)
        except:
            return None
        return None

    # First try the primary file
    res = read_file(FILE_PRIMARY)
    if res: return res

    # Then try the backup file
    res = read_file(FILE_BACKUP)
    if res: return res

    # If both fail: initialize with defaults
    save_odometer(0.0, 0.0, debug_print)
    return 0.0, 0.0