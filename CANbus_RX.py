# CANBus_RX.py - Final Async Version für Longan CANBed + capella-ben MCP2515
import uasyncio as asyncio
from machine import Pin, SPI
import gc
import utime

from canio import Message
from mcp2515 import MCP2515


class CanBusController:
    def __init__(self, shared_data, spi_bus):
        self.shared_data = shared_data

        # === Hardware setup for Longan CANBed RP2040 === 
        self.spi = spi_bus
        self.cs_pin = Pin(9, Pin.OUT, value=1)
        self.int_pin = Pin(11, Pin.IN, Pin.PULL_UP)   # GPIO11 

        # MCP2515 initialize with proper parameters
        self.can = MCP2515(
            spiBlock=0,
            csPin=9,
            baudrate=500000,
            loopback=False,
            silent=False,
            debug=False
        )
        
        # Hard reset of the TX control registers in MCP2515
        for reg in [0x30, 0x40, 0x50]: # TXB0CTRL, TXB1CTRL, TXB2CTRL
           self.can._set_register(reg, 0)

        # =====================================================================
        # === HARDWARE BIT TIMING OVERRIDE (ACK-Fix) ==========================
        # =====================================================================
        # Instead of forcing modes, we write directly to the CNF registers.
        # If the driver leaves the chip in Config mode before init finishes, 
        # this will inject the correct 16MHz Automotive Timing (75% Sample Point).
        try:
            self.can._set_register(0x2A, 0x00) # CNF1 (BRP=0)
            self.can._set_register(0x29, 0x90) # CNF2 (PropSeg/Phase1)
            self.can._set_register(0x28, 0x02) # CNF3 (Phase2)
        except Exception as e:
            self.shared_data.debug_print(f"Timing Override failed: {e}", level=0)
        # =====================================================================

        # 1. Set initial safe values
        t = shared_data.internal_telemetry_data
        
        # 2. Set Raw-values to none
        t['mcuStateRaw'] = None
        t['imdStateRaw'] = None
        t['vifcStatusRaw'] = None
        
        # 3. Set Validity Flags to False
        t['systemStatus'] = 'NDT'
        t['motorDataValid'] = False
        t['imdDataValid'] = False
        t['motorRPM'] = 0
        t['imdIsoR'] = 0

        self.shared_data.debug_print("CAN RX: Initialized - Waiting for Data", level=1)
        self._setup_filters()

        self.shared_data.debug_print("CAN RX: Initialized - Waiting for Data", level=1)
        self._setup_filters()

        # =====================================================================
        # === FORCE NORMAL MODE OVERRIDE (The Real ACK-Fix) ===================
        # =====================================================================
        # The driver often leaves the MCP2515 in Listen-Only (0x60) or Loopback.
        # We overwrite the CANCTRL register (0x0F) to force NORMAL OPERATION MODE (0x00).
        # This reactivates the hardware ACK engine immediately.
        try:
            import utime
            # Read current register state
            current_ctrl = self.can._read_register(0x0F)
            # Mask out the mode bits (Bits 7-5) and set them to 0x00 (Normal Mode)
            # We keep the remaining bits (like clock-out settings) intact
            new_ctrl = (current_ctrl & 0x1F) | 0x00
            self.can._set_register(0x0F, new_ctrl)
            
            # Short verification check
            utime.sleep_ms(5)
            actual_mode = self.can._read_register(0x0E) & 0xE0 # Read CANSTAT mode bits
            if actual_mode == 0x00:
                self.shared_data.debug_print("CAN Hardware: Successfully forced to ACTIVE NORMAL MODE", level=1)
            else:
                self.shared_data.debug_print(f"CAN Hardware: Mode change rejected (Status: {actual_mode})", level=0)
        except Exception as e:
            self.shared_data.debug_print(f"Failed to force Normal Mode: {e}", level=0)
        # =====================================================================

        actual = self.can._read_register(0x0E)  # CANSTAT
        mode = (actual >> 5) & 0x07
        print(f"CANSTAT Mode: {mode:01X} (0=Normal, 1=Sleep, 2=Loopback, 3=Listen-Only, 4-7=Config)")

    def _setup_filters(self):
        """Only allow ID 0x100 and 0x200 through the MCP2515 filters."""  
        try:
            from canio import Match
            matches = [
                Match(address=0x100, mask=0x7FF),
                Match(address=0x200, mask=0x7FF)
            ]
            self.can.listen(matches)
            import utime
            utime.sleep_ms(10)
            self.shared_data.debug_print("CAN Filter: 0x100 + 0x200 aktiviert", level=1)
        except Exception as e:
            self.shared_data.debug_print(f"Filter setup failed: {e}", level=0)

    async def receiver_task(self):
        import gc
        import utime

        print("=== CAN RECEIVER TASK STARTED ===")
        
        # Local references
        read_msg = self.can.read_message
        read_reg = self.can._read_register
        set_reg = self.can._set_register
        int_pin = self.int_pin
        
        last_status_print = utime.ticks_ms()

        # Init Interrupts
        set_reg(0x2B, 0x03)
        set_reg(0x2C, 0x00) 

        self.shared_data.debug_print("CAN RX: Interrupt-driven Mode active", level=1)

        while True:
            try:
                # ==================== DIAGNOSE (immer alle 800ms) ====================
                now = utime.ticks_ms()
                if utime.ticks_diff(now, last_status_print) > 800:
                    eflg    = read_reg(0x2D)
                    tec     = read_reg(0x1C)
                    rec     = read_reg(0x1D)
                    canctrl = read_reg(0x0F)
                    canstat = read_reg(0x0E)
                    
                    print("[CAN] INT:{}  EFLG:0x{:02X}  TEC:{:3d}  REC:{:3d}  CTRL:0x{:02X}  STAT:0x{:02X}".format(
                        int_pin.value(), eflg, tec, rec, canctrl, canstat))
                    
                    last_status_print = now
                # =====================================================================

                # 1. Warte auf Interrupt
                if int_pin.value() == 1:
                    await asyncio.sleep_ms(1)
                    continue   # zurück zum Diagnose-Block

                # 2. Nur wenn Interrupt kam → Nachrichten verarbeiten
                processed_any = False
                
                eflg = read_reg(0x2D)
                if eflg & 0xC0:
                    set_reg(0x2D, 0x00)
                
                while True:
                    msg = read_msg()
                    if msg is None: 
                        break
                    
                    if msg.id in (0x100, 0x200):
                        self._process_frame_raw(msg.id, msg.data)
                        processed_any = True
                    msg = None

                set_reg(0x2C, 0x00)

                if processed_any:
                    gc.collect()

            except Exception as e:
                print(f"CAN Interrupt Task Exception: {e}")
                try: 
                    set_reg(0x2C, 0x00)
                except:
                    pass
                await asyncio.sleep_ms(10)
        

    def _process_frame_raw(self, msg_id: int, data: bytes):
        """
        RAW DATA ONLY: Updates telemetry with integers.
        NO strings, NO logic, NO formatting here.
        """
        # Use local reference for faster access
        t = self.shared_data.internal_telemetry_data
        now = utime.ticks_ms()

        try:
            if msg_id == 0x100:
                # Motor RPM & Temperatures
                t['motorRPM'] = (data[0] << 8) | data[1]
                
                # RAW RND: Store only the byte, don't convert to chr() yet
                t['mcuFlagsRaw'] = data[2] 

                t['motorTemp'] = data[3]
                t['mcuTemp']   = data[4]

                # Binary flags
                valid_mask = data[5]
                t['motorDataValid'] = bool(valid_mask & 0x02)
                t['imdDataValid']   = bool(valid_mask & 0x01)
                
                # Global heartbeat
                self.shared_data.last_valid_data_time = now
                self.shared_data.last_valid_motor_time = now

            elif msg_id == 0x200:
                # Status Bytes (Raw)
                t['mcuStateRaw']   = data[0]
                t['imdStateRaw']   = data[1]
                t['vifcStatusRaw'] = data[2]
                
                # Insulation Resistance
                t['imdIsoR'] = (data[3] << 8) | data[4]
                
                if t.get('imdDataValid', False):
                    self.shared_data.last_valid_imd_time = now

            # DANGER: We strictly avoid ANY print or F-String here!
            # Even if debug_level is 0, F-Strings consume RAM just by being defined.
            
        except Exception:
            pass # Silence is golden in a high-speed loop


    """ def send_odometer_data(self, total_km, trip_km):
            import struct
            import utime
            from canio import Message   

            try:
                can_id = 0x300
                payload = struct.pack('>II', int(total_km), int(trip_km))
                
                # 1. Pre check: Are the buffers clogged due to missing ACKs?
                # One or more of the 3 TX Buffers are still busy with a pending message. 
                # This can happen if the MCP2515 is in a bad state or if the bus is down.
                stat = self.can._read_status()
                
                # Bits 2,4,6 Status-Byte signalisieren 'Message Pending' in den 3 TX Buffern.
                if stat & 0b01010100:
                    # Hard reset of the control registers (clear TXREQ bit 3) to stop the 
                    # endless hardware retries of the MCP2515
                    self.can._set_register(0x30, 0) # TXB0CTRL
                    self.can._set_register(0x40, 0) # TXB1CTRL
                    self.can._set_register(0x50, 0) # TXB2CTRL
                    #  Short delay to allow MCP2515 to process the abort
                    utime.sleep_us(200)

                # 2. Construct the message and send
                msg = Message(id=can_id, data=payload)
                
                # 3. Debug: Read back the error flags and status before sending, to catch issues early
                tec = self.can._read_register(0x1C)
                rec = self.can._read_register(0x1D)
                eflg = self.can._read_register(0x2D)
                
                print("--- CAN TX DEBUG ---")
                print(f"TEC: {tec} | REC: {rec}")
                print(f"EFLG: {bin(eflg)} | Status-Byte: {bin(stat)}")
                
                # 4. Send the message
                success = self.can.send(msg)
                
                # 5. If send failed, we can try one more time after a short delay, in case the first failure was due to a transient bus error or a still-busy buffer.
                if not success:
                    # If the send failed, we can attempt a hard reset of the TX control registers 
                    # to clear any stuck messages that might be clogging the buffers, 
                    # and then try sending again. This is a more aggressive recovery step that can help 
                    # in cases where the MCP2515 is stuck in a bad state due to previous errors, but it 
                    # should be used with caution as it will abort any pending transmissions. The short 
                    # delay allows the MCP2515 to process the abort command before we attempt to send again.
                    self.can._set_register(0x30, 0) # TXB0CTRL
                    self.can._set_register(0x40, 0) # TXB1CTRL
                    self.can._set_register(0x50, 0) # TXB2CTRL
                return success
                
            except Exception as e:
                print(f"CAN TX Exception: {e}")
                return False """