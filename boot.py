# boot.py – WORKS ON v1.23.0 RP2040 (Full Flash + progsize=256)
# This configuration is optimized for stability with MicroPython v1.23.0.

import os
import rp2
import gc

DATA_DIR = "/data"

print("BOOT: Starting LittleFS initialization...")

try:
    # Full flash device (NO start/len keywords!)
    bdev = rp2.Flash()

    try:
        # Attempt to mount
        vfs = os.VfsLfs2(bdev, progsize=256)
        os.mount(vfs, DATA_DIR)
        print(f"BOOT_FS: LittleFS successfully mounted at {DATA_DIR}.")
    except OSError as e:
        if e.args[0] in (1, 84): # EPERM (1) or corrupted (84)
            print("BOOT_FS: FS corrupted -> formatting...")
            os.VfsLfs2.mkfs(bdev, progsize=256)
            vfs = os.VfsLfs2(bdev, progsize=256)
            os.mount(vfs, DATA_DIR)
            print(f"BOOT_FS: LittleFS formatted and mounted at {DATA_DIR}.")
        else:
            raise
    
    os.sync()
    gc.collect()
    print("BOOT_FS: Ready - /data is persistent!")

except Exception as e:
    print(f"BOOT_FS: LittleFS ERROR - running without persistent storage: {e}")

