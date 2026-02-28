# Software Architecture & Component Map

**Date researched:** 2026-02-28

---

## System Architecture

```
┌─────────────────────────────────────────────────────┐
│                   FLSUN S1 Printer                  │
│                                                     │
│  ┌──────────────────────────────────────────────┐   │
│  │       Core Board (Rockchip RV1126 SoC)        │   │
│  │                                              │   │
│  │  ┌──────────────────────────────────────┐    │   │
│  │  │     FLSUN OS (Debian 13 Trixie)      │   │   │
│  │  │                                      │    │   │
│  │  │  ┌────────────┐  ┌──────────────┐   │    │   │
│  │  │  │  Klipper    │  │  Moonraker   │   │    │   │
│  │  │  │  (printer   │  │  (API server │   │    │   │
│  │  │  │  firmware)  │←→│  for Klipper)│   │    │   │
│  │  │  └────────────┘  └──────┬───────┘   │    │   │
│  │  │        ↕                │            │    │   │
│  │  │  ┌────────────┐  ┌─────┴────────┐   │    │   │
│  │  │  │ Klipper-    │  │  Mainsail    │   │    │   │
│  │  │  │ Screen      │  │  (Web UI)    │   │    │   │
│  │  │  │ (Touch UI)  │  └──────────────┘   │    │   │
│  │  │  └────────────┘                      │    │   │
│  │  │                                      │    │   │
│  │  │  ┌────────────┐  ┌──────────────┐   │    │   │
│  │  │  │ MJPG-      │  │  Easy        │   │    │   │
│  │  │  │ Streamer   │  │  Installer   │   │    │   │
│  │  │  │ (camera)   │  │  (CLI tool)  │   │    │   │
│  │  │  └────────────┘  └──────────────┘   │    │   │
│  │  └──────────────────────────────────────┘    │   │
│  │                                              │   │
│  │  Boot: microSD card OR eMMC                  │   │
│  └──────────────────────────────────────────────┘   │
│                     ↕ USB/UART                      │
│  ┌──────────────────────────────────────────────┐   │
│  │        Motherboard (STM32 MCU)               │   │
│  │                                              │   │
│  │  ┌──────────────────────────────────────┐    │   │
│  │  │  Katapult Bootloader                 │    │   │
│  │  │  + Klipper MCU Firmware              │    │   │
│  │  └──────────────────────────────────────┘    │   │
│  │       ↕           ↕           ↕              │   │
│  │  ┌────────┐  ┌────────┐  ┌────────┐         │   │
│  │  │Closed  │  │Closed  │  │Closed  │         │   │
│  │  │Loop    │  │Loop    │  │Loop    │         │   │
│  │  │Board 1 │  │Board 2 │  │Board 3 │         │   │
│  │  │(STM32) │  │(STM32) │  │(STM32) │         │   │
│  │  └────────┘  └────────┘  └────────┘         │   │
│  └──────────────────────────────────────────────┘   │
│                                                     │
│  ┌─────────┐  ┌──────┐  ┌─────────┐  ┌─────────┐  │
│  │ Heaters │  │ Fans │  │ Sensors │  │ Steppers│  │
│  └─────────┘  └──────┘  └─────────┘  └─────────┘  │
└─────────────────────────────────────────────────────┘
```

---

## Software Components

### On Core Board (Linux SoC)

| Component | Source | Role |
|---|---|---|
| Debian 13 Trixie | Pre-built image | Base operating system |
| Klipper | [Guilouz/Klipper-Flsun-S1](https://github.com/Guilouz/Klipper-Flsun-S1) | Printer firmware (host side) |
| Moonraker | Upstream | API server connecting UIs to Klipper |
| KlipperScreen | [Guilouz/KlipperScreen-Flsun-S1](https://github.com/Guilouz/KlipperScreen-Flsun-S1) | Touchscreen interface |
| Mainsail | Upstream | Web-based printer interface |
| Fluidd | Upstream (pre-configured) | Alternative web interface |
| MJPG-Streamer | Upstream | Camera streaming server |
| Kiauh | Upstream | Klipper installation/management helper |
| Easy Installer | Custom (part of FLSUN OS) | CLI management tool (`easy-installer` command) |
| Klipper Print Time Estimator | [Annex-Engineering](https://github.com/Annex-Engineering/klipper_estimator) | Accurate print time estimation |

### On Motherboard MCU (STM32)

| Component | Source | Role |
|---|---|---|
| Katapult Bootloader | [Arksine/katapult](https://github.com/Arksine/katapult) | Enables firmware updates without programmer |
| Klipper MCU Firmware | Built from Klipper-Flsun-S1 | Real-time stepper/heater/sensor control |

### On Closed Loop Boards (STM32 × 3)

| Component | Source | Role |
|---|---|---|
| Closed Loop Firmware | Provided as binary | Stepper motor closed-loop control |

---

## Configuration Files Map

```
/home/pi/printer_data/config/
├── printer.cfg              # Main printer configuration
├── config.cfg               # Include file for modular configs
├── moonraker.conf           # Moonraker API configuration
├── KlipperScreen.conf       # Touchscreen UI configuration
├── webcam.txt               # Camera settings
├── macros/
│   └── macros.cfg           # Custom G-code macros
├── hardware/
│   ├── fan-stock.cfg         # Stock fan config
│   ├── fan-silent-kit.cfg    # Silent Kit (CPAP) fan config
│   ├── led-stock.cfg         # Stock LED config
│   ├── led-mmb-cubic.cfg     # BTT MMB Cubic LED config
│   ├── filament-sensor-stock.cfg
│   ├── filament-sensor-sfs.cfg  # BTT Smart Filament Sensor V2.0
│   ├── temp-sensor-mmb-cubic.cfg
│   └── camera-control.cfg   # Camera settings control
└── flsun-os.cfg             # FLSUN OS-specific settings
```

---

## Communication Flow

1. **User** → KlipperScreen (touchscreen) or Mainsail (web browser)
2. **UI** → Moonraker (HTTP/WebSocket API)
3. **Moonraker** → Klipper (Unix socket)
4. **Klipper (host)** → Klipper MCU (USB/UART serial)
5. **Klipper MCU** → Stepper drivers, heaters, sensors, fans
6. **Closed Loop Boards** → Stepper motors (closed-loop feedback)

---

## Update Mechanism

```
Update Manager (Mainsail/KlipperScreen)
    ├── Klipper        → git pull from Guilouz/Klipper-Flsun-S1
    ├── KlipperScreen  → git pull from Guilouz/KlipperScreen-Flsun-S1
    ├── Moonraker      → git pull from upstream
    ├── Mainsail       → git pull from upstream
    └── FLSUN OS Deps  → System file updates

Easy Installer (SSH)
    ├── Update Klipper config files
    ├── Printer Setup Wizard
    ├── Update Motherboard MCU firmware (via Katapult)
    ├── Update MMB Cubic MCU firmware
    └── Update Debian packages (apt)
```
