# ssd1306.py
# Optimized for 3x 128x32 OLEDs on I2C (Pico)
# Faster show(), dirty rect, async-safe, debug_print
# Compatible with display_manager.py, main.py

from micropython import const
import framebuf
import utime

# --- SSD1306 Register ---
SET_CONTRAST = const(0x81)
SET_ENTIRE_ON = const(0xA4)
SET_NORM_INV = const(0xA6)
SET_DISP = const(0xAE)
SET_MEM_ADDR = const(0x20)
SET_COL_ADDR = const(0x21)
SET_PAGE_ADDR = const(0x22)
SET_DISP_START_LINE = const(0x40)
SET_SEG_REMAP = const(0xA0)
SET_MUX_RATIO = const(0xA8)
SET_COM_OUT_DIR = const(0xC0)
SET_DISP_OFFSET = const(0xD3)
SET_COM_PIN_CFG = const(0xDA)
SET_DISP_CLK_DIV = const(0xD5)
SET_PRECHARGE = const(0xD9)
SET_VCOM_DESEL = const(0xDB)
SET_CHARGE_PUMP = const(0x8D)

class SSD1306(framebuf.FrameBuffer):
    def __init__(self, width, height, external_vcc=False, debug_print=None):
        self.width = width
        self.height = height
        self.external_vcc = external_vcc
        self.pages = height // 8
        self.debug_print = debug_print or (lambda *args: None)
        self.buffer = bytearray(self.pages * self.width)
        super().__init__(self.buffer, width, height, framebuf.MONO_VLSB)
        self.init_display()

    def init_display(self):
        """Initialize SSD1306 with optimized settings"""
        cmds = [
            SET_DISP,  # Display off
            SET_MEM_ADDR, 0x00,  # Horizontal addressing
            SET_DISP_START_LINE,
            SET_SEG_REMAP | 0x01,
            SET_MUX_RATIO, self.height - 1,
            SET_COM_OUT_DIR | 0x08,
            SET_DISP_OFFSET, 0x00,
            SET_COM_PIN_CFG, 0x02 if self.width > 2 * self.height else 0x12,
            SET_DISP_CLK_DIV, 0x80,
            SET_PRECHARGE, 0x22 if self.external_vcc else 0xF1,
            SET_VCOM_DESEL, 0x30,
            SET_CONTRAST, 0xFF,
            SET_ENTIRE_ON,
            SET_NORM_INV,
            SET_CHARGE_PUMP, 0x10 if self.external_vcc else 0x14,
            SET_DISP | 0x01  # Display on
        ]
        for cmd in cmds:
            self.write_cmd(cmd)
        self.fill(0)
        self.show()
        self.debug_print("SSD1306 initialized.", level=2)

    def poweroff(self):
        self.write_cmd(SET_DISP)

    def poweron(self):
        self.write_cmd(SET_DISP | 0x01)

    def contrast(self, contrast):
        self.write_cmd(SET_CONTRAST)
        self.write_cmd(contrast & 0xFF)

    def invert(self, invert):
        self.write_cmd(SET_NORM_INV | (invert & 1))

    def rotate(self, rotate):
        self.write_cmd(SET_COM_OUT_DIR | ((rotate & 1) << 3))
        self.write_cmd(SET_SEG_REMAP | (rotate & 1))

    def show(self, x0=0, y0=0, x1=None, y1=None):
        """
        Optimized show() with optional dirty rectangle
        If no rect given → full screen
        """
        if x1 is None: x1 = self.width - 1
        if y1 is None: y1 = self.height - 1

        page0 = y0 // 8
        page1 = y1 // 8

        # Clamp to valid pages
        page0 = max(0, min(page0, self.pages - 1))
        page1 = max(0, min(page1, self.pages - 1))

        col_offset = (128 - self.width) // 2 if self.width < 128 else 0
        col_start = x0 + col_offset
        col_end = x1 + col_offset

        self.write_cmd(SET_COL_ADDR)
        self.write_cmd(col_start)
        self.write_cmd(col_end)
        self.write_cmd(SET_PAGE_ADDR)
        self.write_cmd(page0)
        self.write_cmd(page1)

        # Extract only dirty region from buffer
        start_idx = page0 * self.width + x0
        end_idx = (page1 + 1) * self.width + x1 + 1
        data = self.buffer[start_idx:end_idx]

        self.write_data(data)
        self.debug_print(f"show() → pages {page0}-{page1}, cols {col_start}-{col_end}", level=3)


class SSD1306_I2C(SSD1306):
    def __init__(self, width, height, i2c, addr=0x3C, external_vcc=False, debug_print=None):
        self.i2c = i2c
        self.addr = addr
        self.cmd_buf = bytearray(2)
        self.data_header = bytearray([0x40])
        super().__init__(width, height, external_vcc, debug_print)

    def write_cmd(self, cmd):
        self.cmd_buf[0] = 0x80
        self.cmd_buf[1] = cmd
        try:
            self.i2c.writeto(self.addr, self.cmd_buf)
        except OSError as e:
            self.debug_print(f"I2C write_cmd error: {e}", level=0)

    def write_data(self, buf):
        """Faster: send header + data in one writeto"""
        try:
            # Combine header + data
            full_data = self.data_header + buf
            self.i2c.writeto(self.addr, full_data)
        except OSError as e:
            self.debug_print(f"I2C write_data error: {e}", level=0)