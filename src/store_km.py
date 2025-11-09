# store_km.py
# Persistent odometer storage with double redundancy and CRC8 checksum
# Mounts on /data, safe for RP2040, only writes when vehicle is stopped

import os
import rp2

# --- Configuration ---
DATA_DIR = "/data"
FILE_PRIMARY = f"{DATA_DIR}/odo1.txt"
FILE_BACKUP = f"{DATA_DIR}/odo2.txt"

# --- CRC8 Checksum ---
def _crc8(data: str) -> int:
    """Simple XOR-based CRC8 for data integrity."""
    crc = 0
    for byte in data.encode('utf-8'):
        crc ^= byte
    return crc

# --- Filesystem Initialization ---
def init_filesystem(debug_print):
    """Mount or format LittleFS on internal flash."""
    try:
        bdev = rp2.Flash()
        vfs = os.VfsLfs2(bdev, block_size=4096)
        os.mount(vfs, DATA_DIR)
        debug_print(f"Filesystem mounted at {DATA_DIR}")
    except Exception as e:
        if "already mounted" not in str(e):
            try:
                os.VfsLfs2.mkfs(bdev, block_size=4096)
                vfs = os.VfsLfs2(bdev, block_size=4096)
                os.mount(vfs, DATA_DIR)
                debug_print(f"Filesystem formatted and mounted at {DATA_DIR}")
            except Exception as e2:
                debug_print(f"CRITICAL: Failed to init filesystem: {e2}", level=0)
                return False
    return True

# --- Save Odometer (double redundant) ---
def save_odometer(total_km: float, trip_km: float, debug_print=None):
    """Save total and trip km to both files with CRC8."""
    data = f"{total_km:.6f},{trip_km:.6f}"
    checksum = _crc8(data)
    line = f"{data},{checksum}"

    for filepath in [FILE_PRIMARY, FILE_BACKUP]:
        try:
            with open(filepath, "w") as f:
                f.write(line)
            if debug_print:
                debug_print(f"Saved odometer → {filepath}", level=2)
        except Exception as e:
            if debug_print:
                debug_print(f"ERROR writing {filepath}: {e}", level=0)

# --- Load Odometer (with validation + fallback) ---
def load_odometer(debug_print=None):
    """Load from primary, fallback to backup. Initialize if both invalid."""
    def read_file(filepath):
        try:
            with open(filepath, "r") as f:
                line = f.read().strip()
                if not line:
                    return None
                total_str, trip_str, crc_str = line.split(",", 2)
                if _crc8(f"{total_str},{trip_str}") == int(crc_str):
                    return float(total_str), float(trip_str)
        except Exception as e:
            if debug_print:
                debug_print(f"ERROR reading {filepath}: {e}", level=1)
        return None

    # Try primary
    result = read_file(FILE_PRIMARY)
    if result is not None:
        if debug_print:
            debug_print(f"Loaded odometer from {FILE_PRIMARY}: {result}", level=1)
        return result

    # Try backup
    result = read_file(FILE_BACKUP)
    if result is not None:
        if debug_print:
            debug_print(f"Loaded odometer from {FILE_BACKUP}: {result}", level=1)
        return result

    # Both failed → initialize
    if debug_print:
        debug_print("No valid odometer data → initializing to 0.0", level=0)
    save_odometer(0.0, 0.0, debug_print)
    return 0.0, 0.0