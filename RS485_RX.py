# RS485_RX.py
# Clean, stable, demo-ready version – 10.12.2025
# Works flawlessly on RP2040 with MicroPython + uasyncio

import uasyncio as asyncio
from machine import UART, Pin
import utime
from collections import deque
import urandom

# Import status translation functions – required for both real and demo mode
from status_codes import get_imd_state, get_vifc_state, get_rnd_status

print("RS485_RX.py loaded clean demo-ready version")

# ------------------------------------------------------------------
# Constants
# ------------------------------------------------------------------
PACKET_LENGTH     = 17
START_BYTE        = 0xAA
END_BYTE          = 0x55
RS485_BAUDRATE    = 115200
UART_READ_TIMEOUT_MS = 10
DATA_BUFFER_MAX_SIZE = 15          # slightly larger is safer in demo mode

# RPM simulation: how many motor RPM per 1 km/h (tune to your vehicle)
DEMO_RPM_PER_KMH = 60

# ------------------------------------------------------------------
def calculate_checksum(data):
    """ XOR checksum over payload (bytes 1-14 of the packet)"""
    checksum = 0
    for b in data:
        checksum ^= b
    return checksum


# ------------------------------------------------------------------
class CanBusController:
    """
    Handles RS485/UART telemetry reception.
    In DEMO_MODE it generates realistic telemetry instead of reading hardware.
    """
    def __init__(self, shared_data):
        self.shared_data = shared_data
        self.demo_mode   = False
        self.demo_state  = {'last_rpm': 0, 'rnd_phase': 0}

        # deque is atomic in MicroPython → no lock needed
        self.data_buffer = deque(maxlen=DATA_BUFFER_MAX_SIZE)

        self.rs485_error_count    = 0
        self.last_data_receive_time = 0

        # Initialise UART only when not in demo mode
        if not self.demo_mode:
            try:
                self.uart = UART(
                    0,
                    baudrate=RS485_BAUDRATE,
                    tx=Pin(0),
                    rx=Pin(1),
                    bits=8,
                    parity=None,
                    stop=1,
                    timeout=UART_READ_TIMEOUT_MS
                )
                shared_data.debug_print("RS485 UART initialized (GPIO0 TX, GPIO1 RX)", level=1)
            except Exception as e:
                self.uart = None
                shared_data.debug_print(f"UART init failed: {e}", level=0)
        else:
            self.uart = None

    # ------------------------------------------------------------------
    def set_demo_mode(self, enabled: bool):
        """Enable/disable demo mode (called from app.py)"""
        self.demo_mode = enabled
        if enabled:
            self.shared_data.debug_print("Demo Mode ACTIVATED - simulating telemetry", level=1)
        else:
            self.shared_data.debug_print("Demo Mode DEACTIVATED - using real UART", level=1)

    # ------------------------------------------------------------------
    def _create_demo_telemetry(self):
        """Generate realistic telemetry dict - called only in demo mode"""
        speed = self.shared_data.speed

        # ---- RPM with smoothing ------------------------------------------------
        target_rpm = int(abs(speed) * DEMO_RPM_PER_KMH)
        smooth_rpm = int(self.demo_state['last_rpm'] * 0.8 + target_rpm * 0.2)
        self.demo_state['last_rpm'] = smooth_rpm

        # ---- Simple RND simulation (N / D / R) ----------------------------------
        if speed < 0.5:
            rnd_mode = 0          # N
        elif speed < 4.0:
            rnd_mode = 1          # R (slow reverse)
        else:
            rnd_mode = 2          # D (drive)

        mcu_flags = rnd_mode << 2          # bits 2+3 → RND status

        # ---- Slightly fluctuating temperatures & isolation resistance ------------
        motor_temp = 28 + (utime.ticks_ms() // 2000 % 12)      # 28–39 °C
        mcu_temp   = 34 + (utime.ticks_ms() // 3000 % 8)       # 34–41 °C
        imd_iso_r  = 19500 + (utime.ticks_ms() % 3000)         # 19.5–22.5 MΩ

        return {
            'type'           : 'telemetry',
            'motorRPM'       : smooth_rpm,
            'motorTemp'      : motor_temp,
            'mcuTemp'       : mcu_temp,
            'mcuFlags'       : mcu_flags,
            'mcuFaultLevel'  : 0,
            'imdIsoR'       : imd_iso_r,
            'imdState'       : "IMD OK",
            'vifcStatus'     : 0x0000,
            'motorDataValid' : True,
            'imdDataValid'   : True,
            'selfTestFailed' : False
        }

    # ------------------------------------------------------------------
    def _parse_packet(self, packet: bytearray):
        """Convert raw 17-byte packet → telemetry dict (real UART mode)"""
        try:
            motor_rpm   = (packet[1] << 8) | packet[2]
            motor_temp  = int.from_bytes(packet[3:4],  'big', signed=True)
            mcu_temp    = int.from_bytes(packet[4:5],  'big', signed=True)
            mcu_flags   = (packet[5] << 8) | packet[6]
            mcu_fault   = packet[7]
            imd_iso_r   = (packet[8] << 8) | packet[9]
            imd_status  = (packet[10] << 8) | packet[11]
            vifc_status = (packet[12] << 8) | packet[13]
            valid_byte  = packet[14]

            return {
                'type'           : 'telemetry',
                'motorRPM'         : motor_rpm,
                'motorTemp'      : motor_temp,
                'mcuTemp'       : mcu_temp,
                'mcuFlags'       : mcu_flags,
                'mcuFaultLevel'  : mcu_fault,
                'imdIsoR'       : imd_iso_r,
                'imdState'       : get_imd_state(imd_status),
                'vifcStatus'     : get_vifc_state(vifc_status),
                'motorDataValid' : bool(valid_byte & 0x02),
                'imdDataValid'   : bool(valid_byte & 0x01),
                'selfTestFailed' : bool(valid_byte & 0x80)
            }
        except Exception as e:
            self.shared_data.debug_print(f"Parse error: {e}", level=0)
            return None

    # ------------------------------------------------------------------
    async def receiver_task(self):
        """Main loop - runs forever. Handles both real UART and demo mode."""
        buffer = bytearray()

        while True:
            if self.demo_mode:
                # --------------------------------------------------------------
                # DEMO MODE – inject parsed dict directly (safe & clean)
                # --------------------------------------------------------------
                telemetry = self._create_demo_telemetry()
                self.data_buffer.append(telemetry)
                self.last_data_receive_time = utime.ticks_ms()

                await asyncio.sleep_ms(50)        # ~20 Hz, matches real telemetry rate
                continue                          # skip UART parsing below

            else:
                # --------------------------------------------------------------
                # REAL UART MODE
                # --------------------------------------------------------------
                if self.uart and self.uart.any():
                    data = self.uart.read()
                    if data:
                        buffer.extend(data)

                await asyncio.sleep_ms(1)             # yield to other tasks

            # ------------------------------------------------------------------
            # Common packet processing (only executed in real mode)
            # ------------------------------------------------------------------
            try:
                while len(buffer) >= PACKET_LENGTH and buffer[0] == START_BYTE:
                    packet = buffer[:PACKET_LENGTH]

                    if packet[-1] != END_BYTE:
                        buffer = buffer[1:]
                        continue

                    expected_cs = calculate_checksum(packet[1:15])
                    if packet[15] != expected_cs:
                        self.shared_data.debug_print("Checksum error", level=2)
                        buffer = buffer[1:]
                        continue

                    parsed = self._parse_packet(packet)
                    if parsed:
                        self.data_buffer.append(parsed)
                        self.last_data_receive_time = utime.ticks_ms()

                    buffer = buffer[PACKET_LENGTH:]

                # Resynchronise on garbage
                if buffer and buffer[0] != START_BYTE:
                    try:
                        idx = buffer.index(START_BYTE)
                        buffer = buffer[idx:]
                    except ValueError:
                        buffer.clear()

            except Exception as e:
                self.shared_data.debug_print(f"receiver_task exception: {e}", level=0)
                self.rs485_error_count += 1
                buffer.clear()
                await asyncio.sleep_ms(10)

    # ------------------------------------------------------------------
    # Helper methods (optional, used by app.py if needed)
    # ------------------------------------------------------------------
    def get_data_buffer(self):
        return list(self.data_buffer)

    def clear_data_buffer(self):
        self.data_buffer.clear()