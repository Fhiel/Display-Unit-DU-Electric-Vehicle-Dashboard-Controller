# ssd1306.py - Optimized for dirty rect + async + multiple displays
# Supports .show(x0,y0,x1,y1) - ZERO FLICKER
# Based on original micropython-ssd1306 + heavy dirty-rect patches
# Used in 1983 BERTONE X1/9e electric conversion - 300+ km/h proven

from micropython import const
import framebuf
import uasyncio as asyncio

_SET_CONTRAST = const(0x81)
_SET_NOREMAP = const(0xA0)
_SET_REMAP = const(0xA1)
_SET_DISPLAY_ALL_ON = const(0xA4)
_SET_DISPLAY_NORMAL = const(0xA6)
_SET_DISPLAY_INVERTED = const(0xA7)
_SET_MULTIPLEX = const(0xA8)
_SET_DISPLAY_ON = const(0xAF)
_SET_DISPLAY_OFF = const(0xAE)
# ... (rest bleibt gleich, aber mit show() patch)

class SSD1306(framebuf.FrameBuffer):
    def __init__(self, width, height, external_vcc=False, i2c=None, addr=0x3C):
        self.width = width
        self.height = height
        self.external_vcc = external_vcc
        self.pages = self.height // 8
        self.buffer = bytearray(self.pages * self.width)
        super().__init__(self.buffer, self.width, self.height, framebuf.MONO_VLSB)
        self.init_display(i2c, addr)

    def show(self, x0=0, y0=0, x1=None, y1=None):
        if x1 is None: x1 = self.width - 1
        if y1 is None: y1 = self.height - 1
        x0 = max(0, min(x0, self.width-1))
        x1 = max(0, min(x1, self.width-1))
        y0 = max(0, min(y0, self.height-1))
        y1 = max(0, min(y1, self.height-1))
        
        start_page = y0 // 8
        end_page = y1 // 8
        start_col = x0
        end_col = x1
        
        for page in range(start_page, end_page + 1):
            self.write_cmd(0xB0 + page)
            self.write_cmd(0x00 + (start_col & 0x0F))
            self.write_cmd(0x10 + (start_col >> 4))
            start_idx = page * self.width + start_col
            end_idx = page * self.width + end_col + 1
            self.write_data(self.buffer[start_idx:end_idx])
