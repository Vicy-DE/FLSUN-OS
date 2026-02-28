# FLSUN T1 / T1 Pro — Hardware Overview

**Date researched:** June 2025  
**Sources:**
- https://github.com/mulcmu/T1-pyro (KiCad schematics, printer.cfg, MCU configs)
- https://github.com/Guilouz/FLSUN-S1-Open-Source-Edition/discussions/13
- https://3dprinting.com/3d-printers/flsun-t1/
- https://github.com/mulcmu/T1-pyro/discussions/2

---

## Printer Specifications

| Specification | Value |
|---|---|
| **Kinematics** | Linear delta |
| **Build volume** | Ø 260 mm × 330 mm (height) |
| **Max print speed** | 1000 mm/s |
| **Max acceleration** | 30,000 mm/s² |
| **Nozzle max temp** | 300 °C |
| **Bed max temp** | 110 °C |
| **Enclosure** | Enclosed, passive heating up to 50 °C |
| **Materials** | PLA, ABS, PA, TPU |
| **Extruder** | Dual-gear short-distance direct drive |
| **Part cooling** | CPAP silent turbine fan (55 dB on T1 Pro, 78 dB on original T1) |
| **Bed surface** | PEI spring steel sheet |
| **Probing** | Strain gauge with HX717 load cell sensor |
| **Stepper drivers** | TMC5160 (SPI) |
| **Accelerometer** | ADXL345 (SPI) |
| **Storage** | 8 GB (eMMC) |
| **Connectivity** | WiFi, USB |
| **Price** | ~$500 (T1 Pro), $399 early bird |
| **T1 Pro launch** | October 25, 2024 |

---

## SoC & Operating System

| Detail | Value |
|---|---|
| **SoC** | Rockchip RV1109 |
| **Architecture** | ARMv7, dual-core Cortex-A7 |
| **Stock OS** | Debian 10 (Buster) |
| **Python version** | 3.7 (stock) |
| **Kernel** | Unknown (stock) |

> **Key limitation:** The stock Debian 10 with Python 3.7 causes SSL certificate issues and prevents installation of modern Python packages (pip, OctoAnywhere, etc.). This is one of the main pain points reported by the community.

### Comparison with S1

| Feature | FLSUN S1 | FLSUN T1 |
|---|---|---|
| SoC | Rockchip RV1126 | Rockchip RV1109 |
| CPU cores | Quad-core Cortex-A7 @ 1.51 GHz | Dual-core Cortex-A7 |
| RAM | 1 GB DDR3 | 1 GB DDR3 |
| Stock OS | Debian 13 (Trixie) | Debian 10 (Buster) |
| Python | 3.13 | 3.7 |
| Open Source Edition | Yes (by Guilouz) | **Not planned** |
| Screen | Compatible with S1 OS | Different resolution/driver/pinout |

---

## Board Architecture

The T1 has a modular PCB design with 5 distinct boards connected via ribbon cables:

### 1. Upper "Driver Board" (Motherboard)

The main control board running Klipper MCU firmware.

| Detail | Value |
|---|---|
| **MCU** | GD32F303 (STM32F103 compatible) |
| **Klipper target** | STM32F103 |
| **Clock** | 72 MHz (8 MHz external reference crystal) |
| **Serial** | USART3 on PB11/PB10 |
| **Baud rate** | 250,000 |
| **Flash start** | 0x8007000 (28 KiB bootloader offset for SD card flash) |
| **Bootloader** | 28 KiB offset for SD card flash, 8 KiB for Katapult |
| **Flash firmware name** | `Robin_nano35.bin` |
| **SD card for flash** | FAT32, 8 GB card confirmed working |
| **Stepper drivers** | TMC5160 via SPI |
| **JTAG header** | 6-pin, same marking as S1 |
| **Reset button** | Power cycle only (not MCU reset — connected to buck converter enable pin) |

#### Pin Mapping (from T1-pyro printer.cfg)

**Steppers:**

| Stepper | Step Pin | Dir Pin | Enable Pin | Endstop Pin |
|---|---|---|---|---|
| stepper_a (front-left) | PE5 | PD7 | PC0 | PC3 |
| stepper_b (front-right) | PB9 | PC7 | PE3 | PC2 |
| stepper_c (rear) | PB8 | PE15 | PE1 | PC1 |
| extruder | PD15 | PB0 | PD14 | — |

**TMC5160 SPI (shared bus):**

| Parameter | Value |
|---|---|
| spi_software_sclk_pin | PD0 |
| spi_software_mosi_pin | PD4 |
| spi_software_miso_pin | PD1 |
| CS pins | PD3 (A), PD11 (B), PD9 (C), PD13 (extruder) |
| Run current | 1.8 A (steppers A/B/C), 0.8 A (extruder) |
| Sense resistor | 0.033 Ω |

**Heaters & Sensors:**

| Component | Pin | Details |
|---|---|---|
| Hotend heater | PB1 | max_power: 1.0 |
| Bed heater | PA2 | max_power: 1.0 |
| Hotend thermistor | PA1 | ATC Semitec 104NT-4-R025H42G |
| Bed thermistor | PA0 | EPCOS 100K B57560G104F |

**Fans:**

| Fan | Pin | Type |
|---|---|---|
| Part cooling (CPAP) | PC13 | fan_generic |
| Hotend fan | PB5 | heater_fan |
| Board cooling fan | PA3 | controller_fan |

**Other Pins:**

| Function | Pin |
|---|---|
| Case light (relay) | PD6 |
| Filament sensor | PE6 |
| ADXL345 CS | PE12 |
| ADXL345 SCLK | PE11 |
| ADXL345 MOSI | PE14 |
| ADXL345 MISO | PE13 |
| ADXL345 rate | 1600 Hz |

**Delta Kinematics Configuration:**

| Parameter | Value |
|---|---|
| delta_radius | ~152 mm (calibrated) |
| print_radius | 133 mm |
| arm_length | ~334–336 mm (calibrated per arm) |
| max_velocity | 1000 mm/s |
| max_accel | 30,000 mm/s² |
| minimum_cruise_ratio | 0.5 |
| max_z_velocity | 1000 mm/s |

### 2. Lower "Function Adapter Board" (Core Board)

The secondary microcontroller board that handles the strain gauge probe.

| Detail | Value |
|---|---|
| **MCU** | STM32F103 |
| **Function** | Strain gauge / load cell probe |
| **Sensor** | HX717 load cell sensor |
| **HX717 SCLK** | PB8 |
| **HX717 DOUT** | PB9 |
| **Serial** | USART1 on PA10/PA9 |
| **Connection** | `/dev/ttyS0` at 250,000 baud |
| **WiFi** | Onboard |
| **SD card slot** | Onboard |
| **Power** | 24V-to-5V buck converter |
| **Low noise ADC** | Gen1 has bodge wire from back of PCB |

**Ribbon cable between upper and lower boards carries:**
- Bed heater signal
- Bed thermistor
- Probe signal (load cell)
- 24V power (up to upper board)
- 5V power (down from upper board)

### 3. Core Board (RV1109 SoC Module)

The main computing module running Linux/Klipper host.

| Detail | Value |
|---|---|
| **SoC** | Rockchip RV1109 |
| **OS** | Debian 10 (Buster) |
| **Connection to Klipper MCU** | USB serial + `/dev/ttyS0` |

### 4. Screen / Display Board

Connected via ribbon cable. **Incompatible with S1 display** — different resolution, driver IC, and pinout. Running S1 OS on T1 produces vertical lines on screen.

### 5. USB Hub Board

| Detail | Value |
|---|---|
| **Connector** | 5-pin 2.54 mm JST XH |
| **Components** | USB hub IC + transistor circuit |
| **Extra function** | Case light control via transistor |

---

## MCU Configuration (Klipper menuconfig)

From `T1-pyro/mcu/.config`:

```
CONFIG_LOW_LEVEL_OPTIONS=y
CONFIG_MACH_STM32=y
CONFIG_MACH_STM32F1=y
CONFIG_MACH_STM32F103xe=y    # High density STM32F103
CONFIG_CLOCK_FREQ=72000000
CONFIG_CLOCK_REF_FREQ=8000000
CONFIG_SERIAL=y
CONFIG_STM32_SERIAL_USART3=y
CONFIG_SERIAL_BAUD=250000
CONFIG_FLASH_START=0x8007000  # 28 KiB bootloader offset
CONFIG_FLASH_APPLICATION_ADDRESS=0x8007000
CONFIG_RAM_START=0x20000000
CONFIG_RAM_SIZE=0x5000        # 20 KB
CONFIG_STACK_SIZE=512
CONFIG_FLASH_SIZE=0x1000      # 4 KB
CONFIG_INITIAL_PINS="!PD6"   # Case light off at boot
```

### MCU Firmware Flashing

**Method 1: SD Card (when bootloader accepts it)**
1. Compile Klipper with above config
2. Copy output as `Robin_nano35.bin` to FAT32 SD card (8 GB confirmed working)
3. Insert SD card into motherboard
4. Power cycle and wait 30–60 seconds

> **Note:** Later FLSUN firmware updates may have changed the expected filename or disabled SD card flashing. If SD card flashing doesn't work, use ST-Link.

**Method 2: ST-Link V2 (recommended/reliable)**
1. Connect ST-Link V2 to the 6-pin JTAG header on the motherboard
2. Follow the same procedure as S1 (Guilouz instructions work for T1)
3. The 6-pin JTAG header has the same markings as S1

---

## Hardware Revisions: Gen1 vs Gen2

Source: [mulcmu/T1-pyro README](https://github.com/mulcmu/T1-pyro)

| Feature | Gen1 | Gen2 |
|---|---|---|
| Stepper drivers | BTT brand (silk screen painted over) | FLSUN branded |
| 5-pin firmware download header | **Missing** | Present |
| Under-stepper components | Pin header jumpers | Transistors |
| Low noise ADC | Bodge wire on back of lower adapter board | Presumably integrated |
| CPAP fan alignment | Misaligned with air hole | Properly aligned |

The Gen1 units appear to be earlier production runs, possibly using third-party components that were later replaced with FLSUN's own parts.

---

## T1 Variants

| Model | Notes |
|---|---|
| **FLSUN T1** | Original model, CPAP fan at 78 dB |
| **FLSUN T1-U** | Unknown variant (mentioned in some sources) |
| **FLSUN T1 Pro** | Improved model with quieter CPAP fan (55 dB), launched Oct 2024 |

---

## KiCad Schematics (T1-pyro)

The [mulcmu/T1-pyro](https://github.com/mulcmu/T1-pyro) repository contains reverse-engineered KiCad schematics for all T1 boards:

| Schematic File | Board |
|---|---|
| `motherboard.kicad_sch` | Upper driver board (GD32F303/STM32F103) |
| `core board.kicad_sch` | RV1109 SoC module |
| `lower adapter.kicad_sch` | Lower function adapter (STM32F103 + HX717) |
| `upper adapter.kicad_sch` | Upper adapter / ribbon cable interface |
| `screen.kicad_sch` | Display board |
| `extruder.kicad_sch` | Extruder assembly |
| `blcd.kicad_sch` | BLDC motor driver (CPAP fan?) |
| `mos.kicad_sch` | MOSFET board |
| `usb adapter.kicad_sch` | USB hub board |
| `schematic b&w.pdf` | Combined printable schematic |

A `schematic.kicad_pro` project file is also included for opening all schematics together.

---

## Three MCU Architecture (Klipper)

The T1 runs Klipper with 3 MCU instances:

| MCU Name | Connection | Function |
|---|---|---|
| `[mcu]` (main) | USB serial (`/dev/serial/by-id/...`) | Stepper motors, heaters, fans, ADXL345 |
| `[mcu host]` | `/tmp/klipper_host_mcu` | Host-side operations |
| `[mcu LoadCell]` | `/dev/ttyS0` at 250,000 baud | Strain gauge probe (HX717 on STM32F103) |

---

## Community Hardware Projects

### T1-pyro (mulcmu)

**Repository:** https://github.com/mulcmu/T1-pyro  
**Stars:** 16 | **Forks:** 3

Replaces the stock T1 host board with a **Raspberry Pi 4** and the stock screen with a **Fysetc 5" DSI display**. Provides:

- Full KiCad schematics for all T1 boards
- Working `printer.cfg` with complete pin mappings
- MCU `.config` for Klipper compilation
- Custom cable documentation (USB hub, power, load cell UART)
- Gen1 vs Gen2 hardware comparison
- Installation guide

### Key Community Contributors

| Person | Contribution |
|---|---|
| **mulcmu** | T1-pyro project, KiCad schematics, Gen1/Gen2 docs |
| **Chumannn** | dd-copied entire T1 image, reflashed via USB-C RKDevTool |
| **LayerDE** | Offered T1 firmware image, asked about RV1109 Debian 12 build |
| **BehaviorBean** | Reported Debian 10 / Python 3.7 SSL issues on T1 Pro |
| **dookiejones** | Posted motherboard and display board photos |
| **CmnZnz** | Reported FLSUN custom Klipper modifications |

---

## Open Questions

1. **RV1109 vs RV1126:** Both are Rockchip SoCs. The RV1109 in the T1 has fewer CPU cores (dual vs quad on RV1126). Are the boot processes and SDK toolchains compatible?
2. **Screen controller IC:** What display controller does the T1 use? It's different from the S1, but the specific IC is unknown.
3. **eMMC partition layout:** Is it the same GPT 6-partition layout as the S1 (uboot, misc, boot, recovery, backup, rootfs)?
4. **T1-U variant:** What distinguishes the T1-U from the standard T1? Limited documentation exists.
5. **FLSUN custom Klipper modifications:** CmnZnz reports "lots of custom stuff" in the Klipper image. What specific patches does FLSUN apply?
