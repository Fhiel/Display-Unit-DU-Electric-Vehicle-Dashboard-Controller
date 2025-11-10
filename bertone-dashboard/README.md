# BERTONE X1/9e Electric Dashboard – MicroPython Zero-Flicker OLED

**1983 BERTONE X1/9e – fully converted to electric drive**  
Triple 128×32 SSD1306 OLED dashboard with pixel-perfect 16×21 font  
Zero flicker thanks to dirty-rect + permanent subtext + async updates

## Features
- 3× SSD1306 (Central + Odometer + RND)
- 16×21 + 12×16 pixel-perfect font (MONO_VLSB)
- Dirty-rect updates (only changed pixels)
- Permanent subtext (drawn once)
- Invert on Reverse gear
- Async-safe, contrast caching
- Boot animation "BERTONE"

## Hardware
- Longan Nano + CAN board
- 3× 128×32 OLED (I2C)
- Real car tested – 300+ km/h

```python
from display_manager import update_odometer_display, update_central_display, update_rnd_display
MIT License • Made with love for the electric BERTONE X1/9e
Special thanks to Grok (xAI) – without him this would still be 8×8 garbage
