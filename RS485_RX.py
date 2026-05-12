# RS485_RX.py v0.2 – 12.02.2026

import uasyncio as asyncio
from machine import UART, Pin
import utime
import struct

# --- Configuration ---
RS485_BAUDRATE = 115200
PACKET_LENGTH  = 18  # New 18-byte format
START_BYTE     = 0xAA
END_BYTE       = 0x55

# Ready-to-use Display Lists (Indices match the IDs from ESP32)
MCU_STATES = ["MCU OK", "MCU BLCK", "MCU STOP", "MCU LIMT", "MCU WARN"]
IMD_STATES = ["IMD OK", "IMD WARN", "IMD ERR", "IMD TEST", "IMD CAL", "ISO ERR"]
VIFC_STATES = ["SYS OK", "SYS ERR", "SYS STALE", "SYS TST ERR", "SYS ON"]


# ------------------------------------------------------------------
def calculate_checksum(data):
    """ XOR checksum over payload (bytes 1-15 of the packet)"""
    checksum = 0
    for b in data:
        checksum ^= b
    return checksum

# ------------------------------------------------------------------
class CanBusController:
    """
    Handles optimized RS485 telemetry reception from ESP32 VCU.
    Uses binary unpacking for maximum performance on RP2040.
    """
    def __init__(self, shared_data):
        self.shared_data = shared_data
        self.rs485_error_count = 0
        
        # Struct Format: < (Little Endian)
        # H (RPM), c (RND), b (MotT), b (McuT), B (McuID), B (ImdID), B (VifcID), H (IsoR), B (Fault), B (Valid), 3s (Res)
        self.struct_format = "<Hcb b BBB H B B 3s"

        try:
            self.uart = UART(
                0, 
                baudrate=RS485_BAUDRATE, 
                tx=Pin(0), 
                rx=Pin(1), 
                timeout=10
            )
            shared_data.debug_print("RS485 RX: Optimized binary driver ready", level=1)
        except Exception as e:
            self.uart = None
            shared_data.debug_print(f"UART init failed: {e}", level=0)

    async def receiver_task(self):
        """Main loop - parses 18-byte binary packets using struct.unpack"""
        buffer = bytearray()
        shared_data = self.shared_data

        while True:
            if self.uart and self.uart.any():
                data = self.uart.read()
                if data:
                    buffer.extend(data)

            # Process buffer if enough data for a full packet is present
            while len(buffer) >= PACKET_LENGTH:
                # 1. Sync: Look for START_BYTE
                if buffer[0] != START_BYTE:
                    idx = buffer.find(START_BYTE)
                    if idx == -1:
                        buffer.clear()
                        break
                    else:
                        del buffer[:idx]
                        continue

                # 2. Validation: Check END_BYTE and Checksum
                if buffer[17] != END_BYTE:
                    # Packet corrupted or shifted, remove first byte and re-sync
                    del buffer[0]
                    continue

                payload = buffer[1:16] # 15 Bytes of payload (ID to Reserve)
                received_crc = buffer[16]
                
                if calculate_checksum(payload) != received_crc:
                    shared_data.debug_print("RS485 CRC Error", level=2)
                    self.rs485_error_count += 1
                    del buffer[0]
                    continue

                # 3. Parsing: Fast unpacking via struct
                try:
                    # data is a tuple matching our struct_format
                    data = struct.unpack(self.struct_format, payload)
                    
                    t = shared_data.internal_telemetry_data
                    
                    # Mapping fields to shared_data
                    t['motorRPM'] = data[0]
                    shared_data.current_rnd_status_char = data[1].decode('ascii')
                    t['motorTemp'] = data[2]
                    t['mcuTemp'] = data[3]
                    
                    # Map calculated IDs to display strings (O(1) lookup)
                    t['mcuState']  = MCU_STATES[data[4]] if data[4] < len(MCU_STATES) else "MCU ERR"
                    t['imdState']  = IMD_STATES[data[5]] if data[5] < len(IMD_STATES) else "IMD ERR"
                    t['vifcStatus'] = VIFC_STATES[data[6]] if data[6] < len(VIFC_STATES) else "SYS ERR"
                    
                    t['imdIsoR'] = data[7]
                    t['mcuFaultLevel'] = data[8]
                    
                    # Data Validity Bitmask (from ESP32 Byte 11)
                    valid_mask = data[9]
                    t['motorDataValid'] = bool(valid_mask & 0x02)
                    t['imdDataValid']   = bool(valid_mask & 0x01)

                    shared_data.last_valid_data_time = utime.ticks_ms()

                except Exception as e:
                    shared_data.debug_print(f"RS485 Parse Error: {e}", level=0)
                
                # Remove the processed packet from buffer
                del buffer[:PACKET_LENGTH]

            # Brief yield to other asyncio tasks
            await asyncio.sleep_ms(2)