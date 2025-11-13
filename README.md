# Display-Unit-DU-Electric-Vehicle-Dashboard-Controller  

[![MicroPython](https://img.shields.io/badge/MicroPython-v1.26.0-blue)](https://micropython.org)
[![RP2040](https://img.shields.io/badge/RP2040-Longan_CANBed)](https://www.longan-labs.cc/can-bus/canbed.html)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Stars](https://img.shields.io/badge/Stars-42+-yellow?style=social)](https://github.com/Fhiel/Display-Unit-DU-Electric-Vehicle-Dashboard-Controller/stargazers)

**DU = Display Unit** – A modular, non-blocking, flash-optimized controller for EV instrumentation.  
> **Revival of analog precision** using **RP2040 + MicroPython v1.26.0 + uasyncio**

![Dashboard](https://github.com/user-attachments/assets/553f2069-2237-4c77-9480-28c75b683de4)

## Why this project exists
In classic cars, instruments were driven by cables or sensors. After EV conversion? **All gone.**  
This project brings back the **original look** – but smarter, smoother, and fully digital under the hood.

**No direct CANbus** (yet) – we use a pre-processed RS485 telemetry stream.  
Why? **RP2040 + MicroPython** are fast enough for 20 Hz pointers and 12 async tasks – but not for full CAN parsing.  

---

## Core Features (v1.0 – MicroPython 1.26.0)

| Feature | Item | Description | Tech |
|-------|------|------|---|
| **Analog Speedometer** | B | 480-step precision, 20 Hz update | `#stepper-motor`, `FullStep` |
| **Analog Tachometer** | E | 0–12,000 RPM via PWM | `#pwm-output`, `rpm2.py` |
| **Temperature Gauges** | L | Motor + MCU temp | `#temp-gauge` |
| **3x SSD1306 OLED** | A/S/H | Async, dirty-rect, 1 Hz refresh | `#oled`, `#i2c`, `#uasyncio` |
| **Persistent Odometer** | A | Survives power loss (LittleFS) | `#littlefs`, `store_km.py` |
| **Button Matrix** | C | Short/long press, debounce | `#button-input` |
| **RS485 Telemetry** | – | Custom protocol (115200 baud) | `#rs485`, `#serial` |
| **Watchdog + GC** | – | 5s hardware WDT, auto-reboot on freeze | `#stability` |
---

## Hardware

| Component | Details |
|---------|--------|
| **MCU** | Longan CANBED RP2040 |
| **Displays** | 3x SSD1306 OLED (128x32, 64x32), I2C |
| **Stepper Motor** | 4-phase, FullStep, 946 steps/rev, pins 10,20,19,29 |
| **RS485 Transceiver** | TTL to RS485, 115200kbps |
| **Sensors** | Wheel speed pulse, CAN telemetry |
| **Storage** | LittleFS on Pico flash (odometer persistence) |
| **Power** | 12V supply, 5V regulated, 3.3V logic |

---

## Software Architecture

```text
main.py
├── init_displays()        → SSD1306 setup
├── init_hardware()        → RS485, motor, buttons, WDT
├── main_loop_logic()      → 12 async tasks
│   ├── block1_task()      → 20 Hz: pointer, speed, RPM
│   ├── block2_task()      → 1 Hz: Odometer OLED
│   ├── block3_task()      → 1 Hz: Central OLED + status stack
│   ├── block_rnd_task()   → 1 Hz: RND OLED gear
│   ├── block5_task()      → 10 Hz: CAN buffer processing
│   ├── block6_task()      → Save odometer on stop
│   ├── block7_task()      → Button handling
│   ├── block8_task()      → Temp gauge update
│   └── block9_task()      → GC + timeout checks
└── watchdog_task()        → Feed WDT
