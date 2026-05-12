# boot.py – WORKS ON v1.23.0 RP2040 (Full Flash + progsize=256)
# This configuration is optimized for stability with MicroPython v1.23.0.

# boot.py – Optimized for Odometer Persistence
import os
import rp2
import gc

DATA_DIR = "/data"

print("BOOT: Starting LittleFS initialization...")

try:
    # Block device for LittleFS (using Flash directly)
    try:
        os.stat(DATA_DIR)
    except OSError:
        os.mkdir(DATA_DIR)
        print("BOOT: Created /data directory")
except Exception as e:
    print(f"BOOT ERROR: {e}")
    
os.sync()
gc.collect()
print("BOOT_FS: Ready.")