#RS485_RX9.py
import uasyncio as asyncio
from machine import UART, Pin
import utime
import collections
from status_codes import get_imd_state, get_vifc_state

# --- Konstanten ---
DEBUG_LEVEL = 1
PACKET_LENGTH = 17
START_BYTE = 0xAA
END_BYTE = 0x55
RS485_BAUDRATE = 115200
UART_READ_TIMEOUT_MS = 10
DATA_BUFFER_MAX_SIZE = 10

def calculate_checksum(data):
    checksum = 0
    for byte in data:
        checksum ^= byte
    return checksum

class CanBusController:
    def __init__(self, shared_data):
        self.shared_data = shared_data
        self.data_buffer = collections.deque([], DATA_BUFFER_MAX_SIZE)
        self.rs485_error_count = 0
        self.last_data_receive_time = 0

        try:
            self.uart = UART(0, baudrate=RS485_BAUDRATE, tx=Pin(0), rx=Pin(1),
                           bits=8, parity=None, stop=1, timeout=UART_READ_TIMEOUT_MS)
            self.shared_data.debug_print("UART initialisiert (async)", level=1)
        except Exception as e:
            self.uart = None
            self.shared_data.debug_print(f"ERROR: UART fehlgeschlagen: {e}", level=0)
            raise

        # Starte async Task
        asyncio.create_task(self._receiver_task())

    async def _receiver_task(self):
        buffer = bytearray()
        while True:
            if self.uart.any():
                buffer.extend(self.uart.read())
            
            while len(buffer) >= 17 and buffer[0] == 0xAA:
                packet = buffer[:17]
                if packet[-1] != 0x55:
                    break
                if packet[15] != calculate_checksum(packet[1:15]):
                    break
                
                data = self._parse_packet(packet)
                if data:
                    if len(self.data_buffer) == DATA_BUFFER_MAX_SIZE:
                        self.data_buffer.popleft()
                    self.data_buffer.append(data)
                    self.last_data_receive_time = utime.ticks_ms()
                
                buffer = buffer[17:]
                continue
                
            buffer = buffer[1:] if buffer and buffer[0] != 0xAA else buffer
            await asyncio.sleep_ms(1)

            except Exception as e:
                self.shared_data.debug_print(f"ERROR in receiver_task: {e}", level=0)
                self.rs485_error_count += 1
                await asyncio.sleep_ms(10)

    def _parse_packet(self, packet):
        try:
            motor_rpm = (packet[1] << 8) | packet[2]
            motor_temp = int.from_bytes(packet[3:4], 'big', signed=True)
            mcu_temp = int.from_bytes(packet[4:5], 'big', signed=True)
            mcu_flags = (packet[5] << 8) | packet[6]
            mcu_fault = packet[7]
            imd_iso_r = (packet[8] << 8) | packet[9]
            imd_status = (packet[10] << 8) | packet[11]
            vifc_status = (packet[12] << 8) | packet[13]
            valid_byte = packet[14]

            return {
                'type': 'telemetry',
                'motorRPM': motor_rpm,
                'motorTemp': motor_temp,
                'mcuTemp': mcu_temp,
                'mcuFlags': mcu_flags,
                'mcuFaultLevel': mcu_fault,
                'imdIsoR': imd_iso_r,
                'imdState': get_imd_state(imd_status),
                'vifcStatus': get_vifc_state(vifc_status),
                'motorDataValid': bool(valid_byte & 0x02),
                'imdDataValid': bool(valid_byte & 0x01),
                'selfTestFailed': bool(valid_byte & 0x80)
            }
        except Exception as e:
            self.shared_data.debug_print(f"ERROR parse: {e}", level=0)
            return None

    def get_data_buffer(self):
        return list(self.data_buffer)

    def clear_data_buffer(self):
        self.data_buffer.clear()