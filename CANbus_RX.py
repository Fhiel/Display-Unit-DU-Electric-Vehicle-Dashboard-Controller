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
        #  hard reset of the TX control registers in MCP2515
        for reg in [0x30, 0x40, 0x50]: # TXB0CTRL, TXB1CTRL, TXB2CTRL
           self.can._set_register(reg, 0)



        # 1. Set initial safe values
        t = shared_data.internal_telemetry_data
        
        
        # 2. Set Raw-values to none, that we can distinguish from "Data came but was 0" vs "No data came at all"
        t['mcuStateRaw'] = None
        t['imdStateRaw'] = None
        t['vifcStatusRaw'] = None
        
        # 3. Set Validity Flags to False, so we know when we have received valid data at least once
        t['systemStatus'] = 'NDT'
        t['motorDataValid'] = False
        t['imdDataValid'] = False
        t['motorRPM'] = 0
        t['imdIsoR'] = 0

        self.shared_data.debug_print("CAN RX: Initialized - Waiting for Data", level=1)
        self._setup_filters()

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
        read_msg = self.can.read_message
        read_reg = self.can._read_register
        set_reg = self.can._set_register
        set_mode = self.can._set_mode
        
        while True:
            try: 
                # 1. check for error flags before trying to read messages. If we have an overflow or 
                # bus error, we need to reset the MCP2515 to recover.
                eflg = read_reg(0x2D)
                if eflg & 0x0B: # Passive, Warning or RX1 Overflow
                    # delete all flags and briefly switch mode to reset the internal state of the MCP2515.
                    set_reg(0x2D, 0x00) # EFLG delete   
                    set_reg(0x2C, 0x00) # CANINTF delete
                    
                    # if it gets stuck in a bad state, we can try a hard reset by switching to configuration mode and back to normal mode. 
                    set_mode(0x80) # Configuration
                    utime.sleep_us(500)
                    set_mode(0x00) # Normal
                    # print("DEBUG: MCP Emergency Reset performed")

                # 2.  reading messages (as before)
                processed_any = False
                while True:
                    msg = read_msg()
                    if msg is None: break
                    if msg.id in (0x100, 0x200):
                        self._process_frame_raw(msg.id, msg.data)
                        processed_any = True
                    msg = None

                if processed_any:
                    gc.collect()

                await asyncio.sleep_ms(1)
            except Exception as e:
                print(f"CAN Task Exception: {e}")
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


    def send_odometer_data(self, total_km, trip_km):
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
                return False