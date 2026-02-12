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

# BDEV_OFFSET and BDEV_SIZE are NO LONGER required.

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
        # A simple test for the mount point. os.listdir() is more stable here than os.stat()
        os.listdir(DATA_DIR)
        return True
    except OSError as e:
        if debug_print:
            # Log the error that causes _is_mounted to fail
            debug_print(f"FS_CHECK: Mount check failed with OSError: {e.args[0]}. Assuming unmounted/corrupt.")
        # Error (e.g., EIO 84, ENOENT 2) means it is not mounted/available.
        return False
    except Exception as e:
        if debug_print:
            debug_print(f"FS_CHECK: Mount check failed with unknown error: {e}. Assuming unmounted/corrupt.")
        return False


# --- Formatting Helper Function (ONLY called if ENOSPC/EIO occurs) ---
def _format_and_remount(debug_print):
    """Unmounts, formats the LittleFS, and remounts using the full flash method."""
    global _vfs_obj
    
    if debug_print:
        debug_print("FS_FORMAT: Starting forced format due to critical write error (ENOSPC/EIO).")

    # Block Device must be recreated for formatting
    try:
        # Use rp2.Flash() without start/len to address the entire flash
        bdev = rp2.Flash()
    except Exception as e:
        if debug_print:
            debug_print(f"FS_FORMAT: Block Device creation failed: {e}")
        return False

    # Unmount attempt
    try:
        os.umount(DATA_DIR)
        if debug_print:
            debug_print(f"FS_FORMAT: Unmounted {DATA_DIR}.")
    except Exception:
        pass # Ignore error if not mounted

    try:
        os.VfsLfs2.mkfs(bdev, progsize=256) # Use progsize=256
        
        vfs = os.VfsLfs2(bdev, progsize=256)
        os.mount(vfs, DATA_DIR)
        _vfs_obj = vfs 
        
        os.sync()
        gc.collect() 
        if debug_print:
            debug_print("FS_FORMAT: Successfully formatted and remounted LittleFS.")
        return True
    except Exception as e:
        if debug_print:
            debug_print(f"FS_FORMAT: CRITICAL FORMAT ERROR: {e}")
        _vfs_obj = None 
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

    critical_error_count = 0

    for filepath in [FILE_PRIMARY, FILE_BACKUP]:
        write_success = False
        
        # 1. WRITE ATTEMPT (Standard overwrite)
        try:
            with open(filepath, "w") as f:
                f.write(line)
            os.sync() 
            if debug_print:
                debug_print(f"Saved odometer -> {filepath} (CRC: {checksum})")
            write_success = True
        except Exception as e:
            if debug_print:
                debug_print(f"ERROR writing {filepath}: {e}")
            
            # 2. ERROR RECOVERY: Delete and rewrite (for ENOSPC)
            if not write_success:
                try:
                    # Try to delete
                    os.remove(filepath)
                    os.sync() 
                    if debug_print:
                        debug_print(f"Successfully removed existing file: {filepath}")
                    
                    # 3. RETRY WRITING AFTER DELETION
                    with open(filepath, "w") as f:
                        f.write(line)
                    os.sync() 
                    if debug_print:
                        debug_print(f"Saved odometer -> {filepath} (CRC: {checksum}) [Retry]")
                    write_success = True
                except Exception as e_retry:
                    # Check for ENOSPC (Error 28) or EIO (84) in case it occurs
                    if e_retry.args[0] in (28, 84):
                        critical_error_count += 1
                        if debug_print:
                            debug_print(f"CRITICAL ERROR on retry saving {filepath}: ENOSPC (28) or EIO (84).")
                    else:
                        if debug_print:
                            debug_print(f"CRITICAL ERROR on retry saving {filepath}: {e_retry}")
    
    # Return: If both write operations fail, we signal a critical error
    if critical_error_count >= 2:
        return False 
    return True

# --- Load Odometer (with validation + fallback) ---
def load_odometer(debug_print=None, format_attempted=False): # format_attempted Flag
    """Load from primary, fallback to backup. Initialize if both invalid."""
    
    if not _is_mounted(debug_print):
        if debug_print:
            debug_print("FATAL: Cannot load, filesystem not mounted. Returning 0.0, 0.0.")
        # We return 0.0, 0.0 if no mount point is available
        return 0.0, 0.0

    def read_file(filepath):
        if debug_print:
             debug_print(f"Attempting to read file: {filepath}")
        
        file_existed = True 
        line = ""

        try:
            with open(filepath, "r") as f:
                line = f.read().strip()
                if not line:
                    if debug_print:
                        debug_print(f"Validation FAILED for {filepath}: File is empty.")
                    
                total_str, trip_str, crc_str = line.split(",", 2)
                expected_crc = _crc8(f"{total_str},{trip_str}")
                actual_crc = int(crc_str)
                
                if expected_crc == actual_crc:
                    return float(total_str), float(trip_str)
                else:
                    if debug_print:
                        debug_print(f"Validation FAILED for {filepath}: CRC mismatch. Expected: {expected_crc}, Found: {actual_crc}")
        
        except OSError as e:
            # We catch EIO (84) here if it occurs during the read operation
            if e.args[0] == 2:
                file_existed = False
                if debug_print:
                    debug_print(f"Validation FAILED for {filepath}: File not found (OSError 2).")
            else:
                if debug_print:
                    debug_print(f"Validation FAILED for {filepath}: OSError during open/read: {e}")
            return None
            
        except ValueError as e:
            if debug_print:
                debug_print(f"Validation FAILED for {filepath}: Data parsing failed (ValueError): {e}. Line: '{line}'")
            
        except Exception as e:
            if debug_print:
                debug_print(f"Validation FAILED for {filepath}: UNKNOWN ERROR: {e}")
            
        # --- Cleanup on failure ---
        if file_existed:
            try:
                os.remove(filepath)
                os.sync() 
                if debug_print:
                    debug_print(f"CLEANUP: Removed invalid file: {filepath}")
            except Exception as e_remove:
                if debug_print:
                    debug_print(f"CLEANUP ERROR: Could not remove {filepath}: {e_remove}")
        
        return None


    # Try primary
    result = read_file(FILE_PRIMARY)
    if result is not None:
        if debug_print:
            debug_print(f"Loaded odometer from {FILE_PRIMARY} successfully.")
        return result

    # Try backup
    result = read_file(FILE_BACKUP)
    if result is not None:
        if debug_print:
            debug_print(f"Loaded odometer from {FILE_BACKUP} successfully.")
        return result

    # Both failed -> initialize
    if debug_print:
        debug_print("No valid odometer data -> initializing to 0.0")
    
    # 1. Try to save and catch critical errors
    save_successful = save_odometer(0.0, 0.0, debug_print)
    
    # If saving fails AND we haven't attempted format yet (e.g., due to ENOSPC or persistent EIO)
    if not save_successful and not format_attempted:
        if debug_print:
            debug_print("FATAL FS ERROR: Initial save failed due to persistent ENOSPC/EIO. Attempting forced format...")
        
        # Force formatting and try loading again
        if _format_and_remount(debug_print):
            if debug_print:
                debug_print("FS format successful. Re-running load_odometer to load the newly initialized data.")
            
            # Recursive call after formatting for validation
            return load_odometer(debug_print, format_attempted=True)
    
    # Fallback
    return 0.0, 0.0