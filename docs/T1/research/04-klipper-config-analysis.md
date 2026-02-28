# Klipper / Moonraker Config Analysis — S1 → T1 Porting

**Date researched:** July 2025  
**Sources:**
- `resources/S1/klipper-configs/` — Full S1 Open Source Edition config set
- `resources/T1/klipper-configs/` — T1-pyro project configs (mulcmu)
- `resources/T1/klipper-configs/T1-pyro-README.md` — T1 board documentation
- `resources/T1/klipper-configs/custom_cables.md` — T1 custom cable wiring
- `resources/T1/klipper-configs/schematic-bw.pdf` — Combined board schematics

---

## 1. Architecture Overview

### S1 Config Structure (Modular — ~2800 lines total)

| File | Lines | Purpose |
|------|-------|---------|
| `printer.cfg` | 423 | Main hardware definitions |
| `config.cfg` | 88 | Include selector (swaps stock/upgrade variants) |
| `Configurations/macros.cfg` | 1910 | All GCode macros |
| `Configurations/flsun-os.cfg` | ~200 | OS management (setup wizard, OTA updates) |
| `Configurations/fan-stock.cfg` | ~30 | Fan pin definitions (stock) |
| `Configurations/fan-silent-kit.cfg` | ~30 | Fan pin definitions (silent kit variant) |
| `Configurations/led-stock.cfg` | ~30 | LED definitions (white only) |
| `Configurations/led-mmb-cubic.cfg` | ~40 | LED definitions (neopixel via MMB Cubic) |
| `Configurations/filament-sensor-stock.cfg` | ~40 | Filament sensor (stock switch+motion) |
| `Configurations/filament-sensor-sfs.cfg` | ~40 | Filament sensor (BTT SFS V2.0 variant) |
| `Configurations/camera-control.cfg` | 139 | Camera v4l2 control macros |
| `Configurations/temp-sensor-mmb-cubic.cfg` | ~25 | Chamber temp via MMB Cubic |
| `moonraker.conf` | 111 | Moonraker server config |
| `KlipperScreen.conf` | 143 | KlipperScreen UI config |

### T1 Config Structure (Monolithic — 716 lines)

| File | Lines | Purpose |
|------|-------|---------|
| `printer.cfg` | 716 | Everything: hardware, macros, SAVE_CONFIG |
| *(no moonraker.conf)* | — | Uses KIAUH defaults + timelapse plugin |
| *(no KlipperScreen.conf)* | — | Uses KlipperScreen defaults |

### Key Structural Decision for T1 Port

The S1 modular structure should be **preserved** for the T1 port because:
- Easier maintenance and version control
- Clean separation of hardware-specific vs macro logic
- Ability to swap components (fan, LED, filament sensor variants)
- `config.cfg` pattern allows user customization without editing core files

---

## 2. MCU Architecture

### S1: Single MCU
```
[mcu]
serial: /dev/serial/by-id/usb-1a86_USB_Serial-if00-port0
restart_method: command
```
- **MCU chip:** STM32 (type unspecified in config, likely STM32F4xx)
- **Connection:** USB via CH340 adapter
- **Single MCU** handles all functions: steppers, extruder, heaters, fans, sensors, probe, ADXL345

### T1: Three MCUs
```
[mcu]
serial: /dev/serial/by-id/usb-1a86_USB_Serial-if00-port0
restart_method: command

[mcu host]
serial: /tmp/klipper_host_mcu

[mcu LoadCell]
serial: /dev/ttyS0
restart_method: command
baud: 250000
```
- **Main MCU:** GD32F303 (STM32F103-compatible) on motherboard — USB via CH341
- **Host MCU:** Linux host process (Raspberry Pi) — for hardware PWM (caselight, beeper)
- **LoadCell MCU:** STM32F103 on lower function adapter board — UART via `/dev/ttyS0`

### Impact on T1 Port

| Change | Detail |
|--------|--------|
| **Add host MCU** | Need `[mcu host]` section + Linux MCU kernel module setup |
| **Add LoadCell MCU** | Need `[mcu LoadCell]` section + UART config via `/dev/ttyS0` |
| **UART setup** | RV1126 has UART ports — need to identify which UART maps to `/dev/ttyS0` equivalent |
| **Host PWM** | RV1126 may expose pwmchip differently than Raspberry Pi — needs investigation |
| **MCU firmware** | Main: `make menuconfig` → STM32F103, 28KiB bootloader (SD) or 8KiB (Katapult), 8MHz, USART3 PB11/PB10, 250000 baud, PE8 startup pin |
| **LoadCell firmware** | STM32F103, 8KiB bootloader, 8MHz, USART1 PA10/PA9, 250000 baud |

---

## 3. Pin Mapping Comparison

### 3.1 Stepper Motors

| Parameter | S1 | T1 | Notes |
|-----------|-----|-----|-------|
| **stepper_a step** | PB2 | PE5 | Different pins |
| **stepper_a dir** | !PA3 | !PD7 | Different pins |
| **stepper_a enable** | !PE6 | !PE1 | Different pins |
| **stepper_a endstop** | ^PD4 | ^PD4 | **SAME** |
| **stepper_b step** | PB6 | PB9 | Different |
| **stepper_b dir** | !PB7 | !PC7 | Different |
| **stepper_b enable** | !PE6 | !PD3 | S1 shared enable; T1 per-stepper |
| **stepper_b endstop** | ^PE3 | ^PD14 | Different |
| **stepper_c step** | PD6 | PB8 | Different |
| **stepper_c dir** | !PD15 | !PE15 | Different |
| **stepper_c enable** | !PE6 | !PD13 | S1 shared enable; T1 per-stepper |
| **stepper_c endstop** | ^PE2 | ^PE10 | Different |

**S1 quirk:** All three steppers share enable pin `!PE6`.  
**T1:** Each stepper has its own enable pin.

### 3.2 TMC5160 Stepper Drivers

| Parameter | S1 | T1 |
|-----------|-----|-----|
| **SPI architecture** | **Shared** software SPI bus | **Dedicated** per-driver SPI buses |
| **stepper_a cs** | PA0 | PB4 |
| **stepper_a sclk** | PA6 (shared) | PE0 |
| **stepper_a mosi** | PA5 (shared) | PD5 |
| **stepper_a miso** | PC4 (shared) | PB3 |
| **stepper_b cs** | PB12 | PC6 |
| **stepper_b sclk** | *(shared)* | PD0 |
| **stepper_b mosi** | *(shared)* | PD1 |
| **stepper_b miso** | *(shared)* | PA8 |
| **stepper_c cs** | PD14 | PD9 |
| **stepper_c sclk** | *(shared)* | PD10 |
| **stepper_c mosi** | *(shared)* | PD11 |
| **stepper_c miso** | *(shared)* | PD8 |
| **run_current** | 3.0A | 3.0A | **Same** |
| **hold_current** | *(not set)* | 1.6A | T1 has explicit hold |
| **sense_resistor** | 0.022 | 0.022 | **Same** |
| **driver_SGT** | 6 | *(not set)* | S1 has StallGuard |
| **interpolate** | True | True | **Same** |

### 3.3 Extruder

| Parameter | S1 | T1 |
|-----------|-----|-----|
| **step_pin** | PE0 | PD15 |
| **dir_pin** | !PB9 | !PB0 |
| **enable_pin** | !PE4 | !PB1 |
| **heater_pin** | PB8 | PA5 |
| **sensor_pin** | PC2 | PA4 |
| **sensor_type** | ATC Semitec 104NT-4-R025H42G | Generic 3950 |
| **pullup_resistor** | 510 | 510 | **Same** |
| **max_temp** | 370 | 320 | S1 higher limit |
| **pressure_advance** | 0.001 (auto) | 0.025 | S1 uses auto PA (fork feature) |
| **rotation_distance** | 4.55 (direct drive) | 4.55 | **Same** |
| **microsteps** | 16 | 16 | **Same** |

**S1 extruder TMC:**

| Parameter | S1 | T1 |
|-----------|-----|-----|
| **cs_pin** | PD7 | PC4 |
| **sclk_pin** | PA6 (shared) | PA7 |
| **mosi_pin** | PA5 (shared) | PA6 |
| **miso_pin** | PC4 (shared) | PC5 |
| **run_current** | 0.8A | 1.2A | T1 higher |
| **hold_current** | *(not set)* | 0.3A | |

### 3.4 Heater Bed

| Parameter | S1 | T1 |
|-----------|-----|-----|
| **heater_pin** | PD5 | PA2 |
| **sensor_pin** | PC1 | PA1 |
| **sensor_type** | ATC Semitec 104NT-4-R025H42G | Generic 3950 |
| **max_temp** | 130 | 130 | **Same** |
| **S1 dual bed** | `heater_bed_2`: PB3/PC0 | **NOT PRESENT** | |

**Critical:** S1 has a dual-zone heated bed (`heater_bed` + `heater_bed_2` as `heater_generic`). T1 has a single bed heater. All S1 macros referencing `heater_bed_2` or adaptive bed heating must be removed/simplified.

### 3.5 Probe

| Feature | S1 | T1 |
|---------|-----|-----|
| **Type** | `[probe]` (switch/microswitch) | `[load_cell_probe]` (strain gauge) |
| **Pin/Sensor** | `!PD4` | HX717 on `LoadCell:PB8/PB9` |
| **z_offset** | -0.25 | *(auto/configurable)* |
| **Samples** | 3 | *(load cell handles internally)* |
| **Extra sections** | — | `[simple_tap_classifier]` |
| **Klipper fork** | Guilouz/Klipper-Flsun-S1 | garethky/klipper load-cell-probe |
| **Dependencies** | None | SciPy, NumPy |

**Critical:** Completely different probe subsystems. The T1 load cell probe requires:
1. A separate Klipper fork (`garethky/klipper`)
2. A third MCU (`LoadCell`) on UART
3. Python SciPy package
4. Different calibration workflow (no Z-offset in traditional sense, uses trigger force in grams)

### 3.6 Fans

| Fan | S1 Pin | T1 Pin | Notes |
|-----|--------|--------|-------|
| **Part cooling fan** | PC7, max_power=0.90 | !PE6, max_power=0.6 | T1 inverted, lower max |
| **Part fan cycle_time** | 0.00005 | 0.0001 | Different PWM freq |
| **Heatsink fan** | PA2 (`heater_fan`) | PE8 (`fan_generic`) | Different control strategy |
| **Motherboard fan** | PB5 (`controller_fan`) | *(not present)* | T1 has no MB fan |
| **Chamber fan** | PB4 (`fan_generic`) | *(not present)* | T1 has no chamber fan |
| **Box fan** | *(not present)* | PE2 (commented out) | T1 only |

**S1 heatsink fan** is a standard `heater_fan` (auto on when extruder >50°C).  
**T1 heatsink fan** is a `fan_generic` with template-based hysteresis control via `[display_template]` and `[delayed_gcode]` — turns on at 50°C, off at 35°C.

### 3.7 LEDs / Lighting

| LED | S1 | T1 |
|-----|-----|-----|
| **Chamber LED** | White: `PC6` (led) or Neopixel: `MMB_Cubic:gpio9` | *(not present)* |
| **Caselight** | *(not present)* | `host:pwmchip0/pwm0` (hardware PWM) |
| **Screen LEDs** | Red: `PD0`, Orange: `PD1`, White: `PA12` | *(not present)* |
| **Beeper** | *(not present)* | `host:pwmchip0/pwm1` (commented out) |

**S1 has 3 screen indicator LEDs** (red/orange/white via output_pin) — T1 has none.  
**T1 caselight** uses host MCU hardware PWM — S1 has no separate caselight (chamber LED serves this purpose).

### 3.8 Filament Sensors

| Sensor | S1 | T1 |
|--------|-----|-----|
| **Switch sensor** | `PA11` | `!PE7` (effector), `^PA13` (BTT) |
| **Motion sensor** | `PA10`, 18mm detection | `^PA14` (BTT), 5mm detection |
| **Sensor count** | 2 | 3 |

T1 has three filament sensors (effector switch + BTT switch + BTT motion) vs S1's two (switch + motion). The BTT filament sensor variant on S1 (`filament-sensor-sfs.cfg`) uses `^PA11`/`^PA10` with 4mm detection — similar to T1's BTT sensor.

### 3.9 ADXL345 Accelerometer

| Parameter | S1 | T1 |
|-----------|-----|-----|
| **cs_pin** | PE13 | PE11 |
| **sclk_pin** | PE10 | PE14 |
| **mosi_pin** | PE11 | PE13 |
| **miso_pin** | PE12 | PE12 | **Same** |
| **rate** | 3200 | 1600 | S1 higher rate |

### 3.10 Other Hardware

| Feature | S1 | T1 |
|---------|-----|-----|
| **Relay** | `PE1` (`_relay` output_pin) | `PD6` (`relay` output_pin) |
| **Power loss sensor** | `PD3` (gcode_button) + `PA11` (filament_switch) | *(not present)* |
| **Motor calibration** | 3× output_pin + gcode_button per axis | *(not present)* |
| **Drying box heater** | `PA9` (heater_generic, watermark) | *(not present)* |
| **Drying box fan** | `PA8` (heater_fan) | *(not present)* |
| **Drying box temp sensor** | Host shared memory (`/dev/shm`) | *(not present)* |

---

## 4. Printer Kinematics Comparison

| Parameter | S1 | T1 |
|-----------|-----|-----|
| **max_velocity** | 1200 | 1000 |
| **max_accel** | 40000 | 30000 |
| **max_z_velocity** | 1200 | 1000 |
| **max_z_accel** | 40000 | 30000 |
| **delta_radius** | 183 | 171.822 |
| **print_radius** | 183 | 133 |
| **minimum_z_position** | -5 | -5 | **Same** |
| **Arm lengths** | All same (calibrated) | Per-arm calibrated (333–336) |
| **Microsteps (steppers)** | 16 | 32 | T1 higher resolution |
| **Homing speed** | 60 | 30 | S1 faster homing |
| **Homing retract** | 5, 2 | *(defaults)* | |
| **Input shaper X** | zero_zv @ 41.6 Hz | 3hump_ei @ 80.0 Hz | |
| **Input shaper Y** | zero_zv @ 40.0 Hz | 3hump_ei @ 84.2 Hz | |

### Delta Calibrate

| Parameter | S1 | T1 |
|-----------|-----|-----|
| **radius** | 154 | 123.5 |
| **horizontal_move_z** | *(default 5)* | 5 |
| **enhanced_method** | True (fork feature) | *(not available)* |

### Bed Mesh

| Parameter | S1 | T1 |
|-----------|-----|-----|
| **radius** | 154 | 100 |
| **round_probe_count** | 9 | 7 |
| **mesh_pps** | 3,3 | *(default 2,2)* |
| **algorithm** | bicubic | *(default)* |
| **fade_end** | *(default)* | 5 |

---

## 5. Daughter Board Architecture & Pinouts

### T1 Board Topology

```
┌─────────────────────────────────────────────────────┐
│                 MOTHERBOARD (Upper)                  │
│                 GD32F303 / STM32F103                 │
│                                                      │
│  Steppers A/B/C ← TMC5160 (dedicated SPI each)      │
│  Extruder       ← TMC5160 (dedicated SPI)            │
│  Heater bed     ← PA2 heater, PA1 thermistor         │
│  Hotend         ← PA5 heater, PA4 thermistor         │
│  Part fan       ← PE6 (inverted)                     │
│  Heatsink fan   ← PE8                                │
│  ADXL345        ← PE11/PE14/PE13/PE12 SPI            │
│  Filament sens  ← PE7, PA13, PA14                    │
│  Relay          ← PD6                                │
│  Probe (legacy) ← PD4 (unused with load cell)        │
│  USB (CH341)    → Host via /dev/serial/by-id/...      │
│  USART3 PB10/11 → Katapult bootloader comms           │
│                                                      │
│  EXP1: PC1,PC3,PA4,PA5,PA6,PA7,PC4,PC5,GND,5V       │
│  EXP2: PB14,PB13,PB11,PA15,PB0,PB15,PC10,RST,GND,NC │
│  SD Card slot    ← SD flash (Robin_nano35.bin)        │
│                                                      │
│  Connectors:                                         │
│   → USB hub board (5-pin JST XH)                     │
│   → Lower function adapter board (ribbon cable)      │
│   → Stepper motors (6× motor connectors)             │
│   → Heater bed, hotend, fans, sensors                │
└───────────────────────┬─────────────────────────────┘
                        │ USB cable
                        │
┌───────────────────────┴─────────────────────────────┐
│              USB HUB BOARD (Side panel)              │
│              USB hub IC                               │
│                                                      │
│  5-pin JST XH connector:                             │
│   Pin 1: USB D+ (white/green data line)              │
│   Pin 2: USB D- (white/green data line)              │
│   Pin 3: GND                                         │
│   Pin 4: 5V                                          │
│   Pin 5: Caselight control (brown wire → GPIO)       │
│                                                      │
│  Downstream:                                         │
│   → USB camera port                                  │
│   → External USB port                                │
│   → Caselight transistor (on/off via pin 5)          │
└──────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────┐
│         LOWER FUNCTION ADAPTER BOARD                  │
│         (Below motherboard, near base)                │
│                                                      │
│  5V Power Supply:                                    │
│   5-pin JST XH connector → Host power                │
│    Pin 1: 5V                                         │
│    Pin 2: 5V                                         │
│    Pin 3: GND                                        │
│    Pin 4: GND                                        │
│    Pin 5: (signal/NC)                                │
│                                                      │
│  STM32F103 MCU (LoadCell):                           │
│   USART1: PA9 (TX) / PA10 (RX) → Host UART          │
│   SPI: PB8 (DOUT) / PB9 (SCLK) → HX717 ADC          │
│   JTAG port for ST-Link programming                  │
│   8 MHz crystal, 250000 baud                         │
│                                                      │
│  HX717 Load Cell ADC:                                │
│   - Low-noise 24-bit ADC for strain gauge readings   │
│   - Gen1: bodged onto back of PCB with silastic      │
│   - Gen2: clean PCB integration                      │
│                                                      │
│  J20 Header (5-pin):                                 │
│   - Needs modification for load cell UART            │
│   - Pin 30 (STM32) → Pin 32 jumper wire (enamel)     │
│   - Replace header pins with right-angle for Pi UART │
│                                                      │
│  Ribbon cable → Motherboard                          │
└──────────────────────────────────────────────────────┘
```

### S1 Board Topology

The S1 uses a **single-board design** with no daughter boards for core MCU functions:

```
┌──────────────────────────────────────────────────────┐
│              S1 MOTHERBOARD                           │
│              STM32 (single MCU)                       │
│                                                      │
│  All stepper/extruder/heater/fan/sensor/probe pins    │
│  on one MCU — no secondary MCUs                       │
│                                                      │
│  Additional S1-specific hardware:                    │
│   Motor calibration pins: 3× output_pin + button     │
│    Motor A: PD12 (out) / PD11 (button)               │
│    Motor B: PD10 (out) / PD9 (button)                │
│    Motor C: PD8 (out) / PE9 (button)                 │
│   Drying box: PA9 (heater), PA8 (fan)                │
│   Power loss: PD3 (detect), PA11 (filament switch)   │
│   Screen LEDs: PD0 (red), PD1 (orange), PA12 (white) │
│   Chamber LED: PC6 (white)                           │
│   Dual bed: PD5/PC1 (inner), PB3/PC0 (outer)        │
│   Relay: PE1                                         │
│                                                      │
│  Optional MMB Cubic (expansion board via MCU section) │
│   Neopixel: gpio9                                    │
│   Chamber temp: gpio26                               │
└──────────────────────────────────────────────────────┘
```

### Board Comparison Summary

| Feature | S1 | T1 |
|---------|-----|-----|
| **MCU count** | 1 | 3 (main + host + LoadCell) |
| **MCU chip** | STM32 (unknown variant) | GD32F303 + STM32F103 (LoadCell) + Linux host |
| **Daughter boards** | Optional MMB Cubic | USB hub board + Lower function adapter board |
| **SPI topology** | Shared bus (all TMC5160s) | Dedicated per-driver SPI |
| **Probe architecture** | Simple switch on main MCU | Strain gauge via separate MCU + ADC |
| **Power loss detection** | Dedicated sensor circuit | None |
| **Motor calibration** | Built-in auto-calibration | None |
| **Drying box** | Integrated subsystem | None |
| **Host PWM** | None needed | pwmchip0 for caselight/beeper |
| **EXP headers** | None documented | EXP1 + EXP2 (20 pins, commented out) |

---

## 6. Macro Analysis — What To Keep / Modify / Remove

### 6.1 Macros to REMOVE (S1-only hardware)

| Macro | Reason |
|-------|--------|
| `CALIBRATION_MOTORS` | S1 motor calibration hardware (output_pin/gcode_button) |
| `CALIBRATION_X_OFFSET` / `CALIBRATION_Y_OFFSET` | Uses M101 (S1 Klipper fork custom command) |
| `CALIBRATION_RESET_XY_OFFSETS` | Depends on M101 |
| `CALIBRATION_PID_BED` (dual bed portion) | References `heater_bed_2` |
| `BED_HEATING_SETTINGS` | Adaptive dual-zone bed heating prompts |
| `M140` override (dual bed) | References `inner_bed_only` / `B` parameter for dual bed |
| `_SCREEN_LED_ON` / `_SCREEN_LED_OFF` | S1 screen LEDs (PD0, PD1, PA12 — T1 has none) |
| **All neopixel macros** *(if no neopixel LED)* | `_NEOPIXELS_ON/OFF`, `_NEOPIXELS_WHITE/BLUE/RED/GREEN/YELLOW/ORANGE/VIOLET`, `_NEOPIXELS_PRESETS`, `_NEOPIXELS_HOTEND/BED/PROGRESS/SPEED` + display templates |
| **All drying box macros** | `MANAGE_DRYING_BOX`, `DRYING_BOX_START/STOP`, `_START_DRYING_BOX_1–9`, `_DRYING_BOX_TEMP`, `_DRYING_BOX_TEMP_1–6`, `RESET_SPOOL_WEIGHT_SENSOR`, `_RESET_SPOOL_WEIGHT` |
| **All power loss macros** | `_SAVE_POWER_LOSS_PARAMS`, `_CLEAR_POWER_LOSS_PARAMS`, `RESUME_PRINT_AFTER_PLR`, `_START_PRINT_RESUME`, `_CANCEL_PLR` + `LOAD_VARIABLES` PLR prompt |
| `_PAUSE_AFTER_DISTANCE` | S1-specific delayed runout behavior |
| `RESTORE_E_CURRENT` | Hardcoded to 1.2A (S1 value) |
| **flsun-os.cfg entirely** | Setup wizard, OTA updates — all S1-specific shell scripts |
| **camera-control.cfg entirely** | References `/dev/video9` — S1-specific v4l2 device |
| `_SCREENSHOT` | S1 screenshot shell command |
| `_PWR_KEY` | S1 power button |

### 6.2 Macros to MODIFY

| Macro | Changes Needed |
|-------|---------------|
| `_START_GCODE` | Remove: adaptive bed heating (dual bed), `heater_bed_2` references, `M140 B0/B1` commands, chamber_fan references. Keep: bed mesh modes, purge line (adjust coordinates for smaller T1 bed — `print_radius` 133 vs 183). |
| `_END_GCODE` | Remove chamber_fan off. Adjust park position for T1 geometry. |
| `_START_PRINT` | Remove: chamber_fan ramp-up, `_CLEAR_POWER_LOSS_PARAMS`, screen LED. Keep: relay on, TMC current set, velocity limits. Adjust TMC current values for T1. |
| `_END_PRINT` | Remove: chamber_fan, screen LED, power loss clear. Keep: cooling delay, relay off. |
| `PAUSE` | Remove: chamber_fan, neopixel/chamber_led references, screen LED, power loss save. Keep: retract, park, cool to 90°C, save nozzle temp. Adjust park position (X0 Y-140 → Y value for T1 radius). |
| `RESUME` | Remove: neopixel/LED references, `m600_state` clear. Keep: reheat, extrude, restore fan. Adjust fan speed correction for T1 `max_power` (0.6 vs 0.9). |
| `CANCEL_PRINT` | Remove: chamber_fan, screen LED. Keep: heaters off, fan, park, home. Adjust park position. |
| `M600` | Remove: neopixel/LED color changes, screen LED. Keep: park, filament change logic. |
| `LOAD_FILAMENT` / `UNLOAD_FILAMENT` | Remove: neopixel LED feedback. Keep: extrude/retract logic, prompt UI. |
| `CALIBRATION_BED` | Remove: `enhanced_method=True` (S1 fork feature). Adjust delta calibrate radius (154 → 123.5). |
| `CALIBRATION_PID_HOTEND` | Keep as-is (generic). Adjust default temp if needed. |
| `CALIBRATION_RESONANCES` | Keep, but adjust shell command paths if needed. |
| `BED_MESH_SETTINGS` | Keep prompt UI. Remove adaptive bed heating reference. |
| `CHAMBER_LED_SWITCH` | Replace with T1 caselight control (`SET_PIN PIN=caselight VALUE=...`). |
| `_CHAMBER_LED_ON/OFF` | Replace with T1 caselight on/off. |
| `M106` override | Remove chamber_fan (`P3`) routing. Keep basic fan control. |
| `SET_GCODE_OFFSET` | Keep as-is (generic persistence macro). |
| `Z_OFFSET_APPLY_ENDSTOP` | Keep as-is. |
| `M204` / `M205` | Keep as-is (generic slicer compatibility). |
| `_RELAY_ON` / `_RELAY_OFF` | Keep, but pin changes handled in hardware config. |
| `_SHUTDOWN` / `_REBOOT` | Keep, remove neopixel conditional. |
| `LOAD_VARIABLES` | Remove: PLR prompt, auto_update_check, reconfigure_needed, delta_calibrate/bed_mesh resume. Simplify to just Z-offset loading. |
| `MANAGE_KLIPPER_CONFIGURATION` / `MANAGE_MOONRAKER_DATABASE` | Keep if backup scripts are ported. Update shell command paths. |
| Idle timeout | S1: 1800s with complex dual-bed/M600/chamber-fan logic. T1: 600s with defaults. Simplify to T1 approach or create clean version. |

### 6.3 Macros to ADD (T1-specific)

| Macro | Purpose |
|-------|---------|
| `relay_on` / `relay_off` | T1 already has these — simple SET_PIN wrappers |
| `[homing_override]` | T1 uses homing override: `G91 → G0 Z-5 → G90 → G0 X0 Y0` — S1 doesn't have this |
| Heatsink fan template | T1 uses `[display_template HEATSINK_FAN]` + `[delayed_gcode _START_HEATSINK_FAN]` for hysteresis-based fan control |
| Load cell probe macros | Any T1-specific probe calibration macros |
| `TMC_DUMP` | T1 has TMC register dump macro — useful for debugging |
| `MEASURING_RESONANCES` | T1 version — adjust ADXL chip name |

### 6.4 Macro Count Summary

| Category | Count | Lines (est.) |
|----------|-------|-------------|
| **Remove entirely** | ~40+ macros | ~800 lines |
| **Modify** | ~20 macros | ~600 lines |
| **Keep as-is** | ~10 macros | ~200 lines |
| **Add new** | ~5-10 macros | ~100 lines |
| **Estimated T1 macros.cfg** | ~35 macros | ~900 lines |

---

## 7. Moonraker Config Changes

### S1 moonraker.conf → T1 moonraker.conf

| Section | S1 | T1 Change |
|---------|-----|-----------|
| `[server]` | host 0.0.0.0:7125 | Keep |
| `[authorization]` | Standard trusted clients + CORS | Keep |
| `[sensor_custom Drying_Box]` | JSON sensor for temp/humidity/spool weight | **REMOVE** — T1 has no drying box |
| `[file_manager]` | enable_object_processing=True | Keep |
| `[update_manager]` | channel=dev, system_updates=False | Modify: may want system_updates=True for T1 |
| `FLSUN-OS-Dependencies` repo | S1-specific update manager | **REMOVE** or replace with T1-specific repo |
| `KlipperScreen` repo | Guilouz S1 fork | **REPLACE** with standard KlipperScreen or T1-specific fork |
| `Katapult` repo | keep | Keep |
| `mainsail` | beta channel | Keep |
| `[timelapse]` | commented out | Keep (T1-pyro uses timelapse) |
| `[spoolman]` | commented out | Keep as optional |

---

## 8. KlipperScreen Config Changes

### S1 KlipperScreen.conf → T1

| Section | S1 | T1 Change |
|---------|-----|-----------|
| `[printer]` name | "FLSUN S1" | Change to "FLSUN T1" |
| `[printer]` move speeds | xy=150, z=100 | Adjust for T1 (likely similar) |
| Preheat profiles | PLA/PETG/TPU/ABS/ASA/PA-CF | Keep (material-agnostic) |
| Max preheat temps | 370°C / 130°C | Change to 320°C / 130°C |
| `[topbar_sensor spool_humidity]` | Drying_Box moonraker sensor | **REMOVE** |
| `[topbar_sensor spool_weight]` | Drying_Box moonraker sensor | **REMOVE** |
| Hidden macros | Long list including drying box, camera, calibration | Trim to T1-relevant macros only |

---

## 9. Klipper Fork Compatibility

### S1 Fork Features (Guilouz/Klipper-Flsun-S1)

These features are **S1-fork-specific** and won't be available on stock Klipper or the T1 load-cell fork:

1. **Auto Pressure Advance** (`pressure_advance: 0.001` with auto-adjustment) — T1 uses manual PA
2. **Enhanced Delta Calibrate** (`enhanced_method: True`) — T1 uses standard delta calibrate
3. **M101 command** (X/Y offset calibration) — completely unavailable
4. **`x_size_offset` / `y_size_offset`** parameters — not in stock Klipper
5. **`M140 B0/B1`** multi-bed parameter — not in stock Klipper (S1 uses M140 rename)
6. **`POWER_LOSS_RESTART_PRINT`** command — S1 fork custom

### T1 Fork Features (garethky/klipper load-cell-probe)

These features are specific to the T1's Klipper fork:

1. **`[load_cell_probe]`** — strain gauge probe with HX717 sensor
2. **`[simple_tap_classifier]`** — probe tap detection algorithm
3. **SciPy dependency** — for signal processing (notch filter)

### Fork Decision

The T1 port must use the **garethky/klipper load-cell-probe** fork if load cell probing is desired. This fork does NOT include S1 fork features. All S1-fork-specific macro references must be removed.

Alternatively, if using a standard probe (unlikely given T1 hardware design), stock Klipper could be used.

---

## 10. Configuration Migration Checklist

### Phase 1: Hardware Config (`printer.cfg`)

- [ ] Update all pin assignments to T1 values  
- [ ] Add `[mcu host]` and `[mcu LoadCell]` sections  
- [ ] Change `[probe]` → `[load_cell_probe]` + `[simple_tap_classifier]`  
- [ ] Update `[printer]` kinematics parameters (delta_radius, print_radius, max_vel/accel)  
- [ ] Change `[tmc5160]` from shared SPI → dedicated per-driver SPI  
- [ ] Update extruder TMC current (0.8A → 1.2A run, add 0.3A hold)  
- [ ] Remove `heater_bed_2` (heater_generic)  
- [ ] Remove drying box heater/fan/sensor  
- [ ] Remove motor calibration pins (output_pin + gcode_button × 3)  
- [ ] Remove power loss sensor  
- [ ] Add `[homing_override]`  
- [ ] Change fan pin polarities and max_power values  
- [ ] Replace chamber LED with caselight (host PWM)  
- [ ] Remove screen LEDs  
- [ ] Update filament sensor pins (2 sensors → 3 sensors)  
- [ ] Update ADXL345 pins  
- [ ] Update relay pin  
- [ ] Update stepper microsteps (16 → 32)  
- [ ] Update input shaper values  
- [ ] Update delta calibrate / bed mesh radii  
- [ ] Add `[endstop_phase]` sections if using endstop phase calibration  
- [ ] Add heatsink fan template control (display_template + delayed_gcode)

### Phase 2: Macros (`macros.cfg`)

- [ ] Remove all drying box macros (~200 lines)  
- [ ] Remove all power loss macros (~120 lines)  
- [ ] Remove all neopixel macros (~200 lines, unless adding neopixels)  
- [ ] Remove screen LED macros  
- [ ] Remove motor calibration macros  
- [ ] Remove M101 / X-Y offset calibration macros  
- [ ] Simplify _START_GCODE (single bed, no adaptive heating)  
- [ ] Update PAUSE/RESUME/CANCEL park positions for T1 radius  
- [ ] Update fan speed calculations for T1 max_power (0.6)  
- [ ] Replace chamber LED control with caselight control  
- [ ] Simplify M140 override (remove dual bed B parameter)  
- [ ] Simplify LOAD_VARIABLES (remove PLR, update checks)  
- [ ] Add T1-specific homing override  
- [ ] Add heatsink fan hysteresis macros  
- [ ] Update RESTORE_E_CURRENT to T1 value  

### Phase 3: Moonraker (`moonraker.conf`)

- [ ] Remove Drying_Box sensor  
- [ ] Replace S1-specific update manager repos  
- [ ] Enable timelapse if desired  
- [ ] Update KlipperScreen repo reference  

### Phase 4: KlipperScreen (`KlipperScreen.conf`)

- [ ] Change printer name to "FLSUN T1"  
- [ ] Remove drying box topbar sensors  
- [ ] Update max temperature limits  
- [ ] Trim hidden macros list  

### Phase 5: Supporting Infrastructure

- [ ] Port or create backup/restore shell scripts  
- [ ] Set up host MCU with PWM export in `/etc/rc.local`  
- [ ] Configure UART for LoadCell MCU  
- [ ] Install SciPy/NumPy dependencies for load cell  
- [ ] Create/adapt `config.cfg` for T1 component variants  

---

## 11. Open Questions

1. **RV1126 UART mapping:** Which UART on the RV1126 SoC corresponds to `/dev/ttyS0` for the LoadCell MCU? The S1 core board may have different UART routing than a Raspberry Pi.
2. **RV1126 PWM:** Does the RV1126 expose `pwmchip0` for hardware PWM (caselight/beeper), or is a different mechanism needed?
3. **S1 MCU type:** The exact STM32 variant on the S1 motherboard is not documented in configs — affects firmware build comparison.
4. **Load cell physical compatibility:** Does the S1 effector have the same strain gauge / HX717 ADC, or is the probe mechanism entirely different?
5. **Neopixel on T1:** The T1 has no neopixel LED by default. Should the neopixel macros be kept as an optional future upgrade?
6. **Camera device path:** What is the USB camera device path on T1 when connected via the USB hub board? Likely different from S1's `/dev/video9`.
7. **T1 connector pinouts (J20):** Exact pin numbering for the J20 header modification on the lower function adapter board — only partially documented (STM32 pin 30 → pin 32 jumper).
8. **S1 motherboard schematic:** No schematic is available for the S1 — pin assignments are derived solely from Klipper configs.
