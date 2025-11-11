# Display-Unit-DU-Electric-Vehicle-Dashboard-Controller
The **Display Unit (DU)** is the central brain of an electric vehicle dashboard. It combines **analog precision** with **digital clarity** using a **Raspberry Pi Pico (RP2040)**, **MicroPython**, and **uasyncio**.  > **DU = Display Unit** – A modular, non-blocking, flash-optimized controller for EV instrumentation.

---

## Core Features
<img width="1573" height="402" alt="dashboard_5" src="https://github.com/user-attachments/assets/553f2069-2237-4c77-9480-28c75b683de4" />

| Feature | Item | Description | Tech |
|-------|------|------|---|
| **Analog Speedometer** | B | Smooth 0–225 km/h pointer via stepper motor | `#stepper-motor`, `FullStep`, `480 steps` |
| **Analog Tachometer** | E | PWM signal (0–12,000 RPM) for tachometer | `#pwm-output`, `rpm2.py` |
| **Analog Temperature Gauge** | L | Motor or MCU temperature via PWM | `#temp-gauge`, `TempGauge` |
| **3x SSD1306 OLED Displays** |  | I2C, async updates, Dirty-Rect optimization | `#oled`, `#ssd1306`, `#i2c` |
| &nbsp;&nbsp;→ **Odometer Display** | A | Speed, total km, trip km, mode switch | `#odometer`, `#trip-counter` |
| &nbsp;&nbsp;→ **Central Display** | S | Motor temp, MCU temp, ISO-R, boot animation, diagnostic stack | `#telemetry`, `#iso-r`, `#diagnostics` |
| &nbsp;&nbsp;→ **RND Display** | H | Gear (R/N/D), inverted in reverse | `#gear-display`, `#reverse-indicator` |
| **Button Control** | C | Short/long press: mode, reset, contrast, zero | `#button-input`, `#ui-control` |
| **RS485 Transceiver** |  | Receives **pre-processed CAN extract** via custom protocol over RS485 | `#rs485`, `#serial-telemetry`, `#custom-protocol` |
| **Persistent Odometer** |  | Saves total/trip km after 2s stop, LittleFS | `#non-volatile`, `#littlefs`, `store_km.py` |
| **Async Architecture** |  | 12 independent tasks, 20 Hz pointer, 1 Hz displays | `#uasyncio`, `#real-time`, `#multitasking` |
| **Watchdog + GC** |  | Hardware WDT (5s), memory monitoring | `#watchdog`, `#gc`, `#stability` |

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
