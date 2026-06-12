Revival of analog precision using RP2040 + MicroPython v1.26.0 + uasyncio

## Why this project exists

In classic cars, instruments were driven by cables or sensors. After EV conversion? **All gone.**
This project brings back the **original look** – but smarter, smoother, and fully digital under the hood.

No direct **CANbus** (yet) – we use a pre-processed RS485 telemetry stream.
**Why?** RP2040 + MicroPython are fast enough for 20 Hz pointers and 12 async tasks – but not for full CAN parsing.

## Core Features (v1.0 – MicroPython 1.26.0)

| Feature | Item | Description | Tech |
| :--- | :--- | :--- | :--- |
| **Analog Speedometer** | B | 480-step precision, 20 Hz update | `#stepper-motor`, `FullStep` |
| **Analog Tachometer** | E | 0–12,000 RPM via PWM | `#pwm-output`, `rpm2.py` |
| **Temperature Gauges** | L | Motor + MCU temp | `#temp-gauge` |
| **3x SSD1306 OLED** | A/S/H | Async, dirty-rect, 1 Hz refresh | `#oled`, `#i2c`, `#uasyncio` |
| **Persistent Odometer** | A | Survives power loss (LittleFS) | `#littlefs`, `store_km.py` |
| **Button Matrix** | C | Short/long press, debounce | `#button-input` |