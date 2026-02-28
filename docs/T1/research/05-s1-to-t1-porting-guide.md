# S1-to-T1 Porting Guide — Hardware Dependency Comparison & Todo List

**Date researched:** 2025-01-20
**Sources:**
- `resources/S1/klipper-configs/` (S1 Open Source Edition configs)
- `resources/T1/klipper-configs/` (T1-pyro community configs)
- `build/flsun-os.yaml` (debos build recipe, 23 stages)
- `build/overlays/` (systemd services, init scripts, overlay files)
- `docs/T1/research/03-kernel-build-and-display-drivers.md`
- `docs/T1/research/04-stock-firmware-analysis.md`

---

## 1. Hardware Dependency Comparison

### 1.1 SoC & Platform

| Feature | S1 | T1 | Porting Impact |
|---|---|---|---|
| Physical chip | RV1126 | RV1109 | Same die family — DTB uses `rv1126` for both |
| CPU cores | 4× Cortex-A7 @ 1.51 GHz | 2× Cortex-A7 (same clock) | Performance: half the cores — reduce compile parallelism |
| RAM | 1 GB DDR3 | 1 GB DDR3 | Identical |
| NPU | 2 TOPS (RKNN) | 1.2 TOPS (RKNN) | Reduced NPU — `S60NPU_init` service needs review |
| ISP | Dual-camera ISP | Single-camera ISP | Camera stack may need adjustment |
| Platform ID in DTB | `rv1126` | `rv1126` (confirmed in stock DTB) | **No change** — same compatible strings |
| Kernel version (S1 OSE) | 6.1.99 (Rockchip BSP) | N/A — stock uses 4.19.111 | Must build 6.1.99 kernel with T1 DTB |
| Defconfig | `rv1126_defconfig` | `rv1126_defconfig` | **Same defconfig** — only DTB differs |

### 1.2 Boot System

| Feature | S1 | T1 | Porting Impact |
|---|---|---|---|
| Boot image format | Android boot (`ANDROID!` magic) | U-Boot FIT (`D00DFEED` magic) | **Must adapt** — use `mkbootimg` (S1 style) or create FIT |
| U-Boot | Rockchip miniloader + U-Boot | Rockchip miniloader + U-Boot | Both use Rockchip bootloader chain |
| Partition layout | GPT, 6 partitions | GPT, 9 partitions (stock) | Must either repartition or adapt to T1 layout |
| Boot packaging script | `build-boot-img.sh` (mkbootimg) | N/A | Script needs T1 variant (if using Android boot format) |
| eMMC flash tool | RKDevTool v2.96 | RKDevTool (Maskrom via USB-C) | Same tool, different partition addresses |
| SD card boot | Supported (non-destructive) | Unknown (needs testing) | Investigate T1 U-Boot SD card boot support |

### 1.3 Display

| Feature | S1 | T1 | Porting Impact |
|---|---|---|---|
| Interface | RGB parallel (`simple-panel`) | RGB parallel (`simple-panel`) | **Same driver** |
| Resolution | 1024×600 | 800×480 | **DTB change only** — panel timing node |
| Pixel clock | 51.2 MHz | 25 MHz | DTB timing parameters |
| Backlight | PWM (`backlight` node) | PWM (`backlight` node) | Same driver, may need different PWM channel/period |
| Touch | Goodix GT911 (I2C) | Goodix (likely GT911, I2C) | Verify I2C address and IRQ/reset GPIOs |
| KlipperScreen resolution | 1024×600 | 800×480 | Must adjust KlipperScreen display settings |
| rc.local brightness path | `/sys/devices/platform/backlight/backlight/backlight/brightness` | Same path expected | Verify on T1 hardware |

### 1.4 MCU — Main Motherboard

| Feature | S1 | T1 | Porting Impact |
|---|---|---|---|
| MCU chip | STM32 (unspecified model) | GD32F303 (STM32F103xe compatible) | **Different MCU** — build Klipper MCU firmware for STM32F103xe |
| Connection | USB serial (`usb-1a86_USB_Serial`) | USB serial (`usb-1a86_USB_Serial`) | **Same** USB-UART chip (CH340) |
| Baud rate | Implicit (USB) | 250000 (stock), USB with Klipper | Same USB transport |
| Bootloader | Katapult (flash at 0x8007000) | Katapult (flash at 0x8007000) | **Same** bootloader offset |
| Clock reference | Unknown | 8 MHz external crystal | Confirm S1 clock ref |
| Communication | USB serial | USART3 (stock) / USB serial (Klipper) | Same with Klipper |
| Flash method | ST-LINK V2 (initial), Katapult (updates) | ST-LINK V2 or SD card `Robin_nano35.bin` | T1 has easier initial flash via SD |
| Firmware `.config` | Not in repo (built via `make menuconfig`) | Available at `resources/T1/klipper-configs/mcu/.config` | T1 config ready, S1 needs extraction |

### 1.5 MCU — Secondary (T1 Only)

| Feature | S1 | T1 | Porting Impact |
|---|---|---|---|
| Secondary MCU | **None** | STM32F103 (`LoadCell` MCU) | **New component** — must build & flash separate firmware |
| Connection | N/A | UART `/dev/ttyS0` | Serial port must exist in T1 DTB |
| Purpose | N/A | HX717 load cell sensor (strain gauge probe) | Load cell probe support requires this MCU |
| Firmware | N/A | Separate Klipper MCU build | Need `.config` for LoadCell MCU |

### 1.6 MCU — Host (Linux MCU)

| Feature | S1 | T1 | Porting Impact |
|---|---|---|---|
| Host MCU | Not explicitly configured | `[mcu host]` at `/tmp/klipper_host_mcu` | **T1 needs** `klipper_mcu` Linux service |
| Used for | N/A | Caselight (hardware PWM `pwmchip0/pwm0`) | Host MCU needed for PWM-based caselight |

### 1.7 Stepper Motors & TMC Drivers

| Feature | S1 | T1 | Porting Impact |
|---|---|---|---|
| Driver IC | TMC5160 | TMC5160 | **Same driver IC** |
| Interface | SPI (software) | SPI (software) | Same protocol |
| Stepper pins (A) | step=PD6, dir=PD11, en=PD10 | step=PE5, dir=PD7, en=PE1 | **Different pins** — full remap |
| Stepper pins (B) | step=PD15, dir=PE9, en=PE8 | step=PB9, dir=PC7, en=PD3 | **Different pins** |
| Stepper pins (C) | step=PE3, dir=PC5, en=PA4 | step=PB8, dir=PE15, en=PD13 | **Different pins** |
| TMC SPI (A) | Shared SPI bus with extruder | Dedicated SPI (cs=PB4, sclk=PE0, miso=PB3, mosi=PD5) | T1 uses per-stepper SPI buses |
| TMC SPI (B) | Shared SPI bus with extruder | Dedicated SPI (cs=PC6, sclk=PD0, miso=PA8, mosi=PD1) | T1 uses per-stepper SPI buses |
| TMC SPI (C) | Shared SPI bus with extruder | Dedicated SPI (cs=PD9, sclk=PD10, miso=PD8, mosi=PD11) | T1 uses per-stepper SPI buses |
| Extruder TMC SPI | cs=PD7, sclk=PA6, mosi=PA5, miso=PC4 | cs=PC4, sclk=PA7, mosi=PA6, miso=PC5 | **Different pins** |
| Run current (steppers) | Not specified in printer.cfg (step/dir only) | 3.0 A | T1 has explicit TMC config per stepper |
| Run current (extruder) | 0.8 A | 1.2 A (hold=0.3 A) | Different current settings |
| Microsteps | 16 (all) | 32 (steppers), 16 (extruder) | T1 uses higher microsteps for XYZ |
| Sense resistor | 0.0375 Ω | 0.0375 Ω | **Same** |
| Endstop pins (A/B/C) | PD9, PE7, PA3 | PD4, PD14, PE10 | **Different pins** |

### 1.8 Kinematics & Geometry

| Feature | S1 | T1 | Porting Impact |
|---|---|---|---|
| Kinematics | Delta | Delta | **Same** |
| Print radius | 183 mm | 133 mm | Config change |
| Delta radius | 183 mm | ~171.8 mm | Config change |
| Arm length | 385 mm (uniform) | ~333–336 mm (per-arm calibrated) | Config change |
| Position endstop | 435 mm | ~331 mm | Config change |
| Build volume | Ø 366 mm × ~? mm | Ø 260 mm × 330 mm | Config change |
| Max velocity | 1200 mm/s | 1000 mm/s | Config change |
| Max accel | 40000 mm/s² | 30000 mm/s² | Config change |
| Rotation distance | 60 mm | 60 mm | **Same** |
| Motor calibration pins | PD13/PE15/PB0 + PD14/PD8/PB1 | **None** | S1-specific — **remove** |

### 1.9 Extruder & Hotend

| Feature | S1 | T1 | Porting Impact |
|---|---|---|---|
| Extruder step/dir/enable | PE0/PB9/PE4 | PD15/PB0/PB1 | **Different pins** |
| Rotation distance | 4.5 mm | 4.5 mm | **Same** |
| Heater pin | PB8 | PA5 | **Different** |
| Thermistor pin | PC2 | PA4 | **Different** |
| Sensor type | RT 100K 3950 | Generic 3950 | Functionally similar, verify exact NTC |
| Pullup resistor | 510 Ω | 510 Ω | **Same** |
| Max temp | 370°C | 320°C | Config — use T1 value |
| Pressure advance | 0.001 (auto-adjust) | 0.025 | Config change |
| Auto PA adjustment | Yes (firmware feature) | No | S1 Klipper fork feature — verify compatibility |

### 1.10 Heated Bed

| Feature | S1 | T1 | Porting Impact |
|---|---|---|---|
| Bed zones | **Dual** (heater_bed + heater_bed_2) | **Single** (heater_bed only) | **Remove** second bed heater config |
| Heater pin 1 | PD5 | PA2 | **Different** |
| Sensor pin 1 | PC1 | PA1 | **Different** |
| Heater pin 2 | PB3 | N/A | **Remove** |
| Sensor pin 2 | PC0 | N/A | **Remove** |
| Sensor type | RT 100K 3950 | Generic 3950 | Same family |
| Max temp | 140°C | 130°C | Config change |
| Bed mesh radius | 154 mm | 100 mm | Config change |
| Delta calibrate radius | 154 mm | 123.5 mm | Config change |

### 1.11 Probe System

| Feature | S1 | T1 | Porting Impact |
|---|---|---|---|
| Probe type | Switch (`[probe]`) | Load cell (`[load_cell_probe]`) | **Completely different** — major config rewrite |
| Probe pin | PD4 (inverted) | N/A (uses HX717 sensor) | Different architecture |
| Sensor IC | N/A | HX717 (load cell ADC) | T1-specific hardware |
| Communication | MCU GPIO | LoadCell MCU (sclk=PB9, dout=PB8) | Needs secondary MCU |
| Z offset | -0.25 mm | 0.0 mm | Config change |
| Trigger force | N/A | 75 g | T1-specific |
| Requires SciPy | No | Yes (notch/drift filters) | Add `scipy` to Python deps |
| Homing override | Not used | `[homing_override]` with Z-5 correction | T1-specific macro |
| `[simple_tap_classifier]` | No | Yes | T1-specific section for load cell analysis |

### 1.12 Fans

| Feature | S1 | T1 | Porting Impact |
|---|---|---|---|
| Part cooling fan | `[fan]` pin=PC7, max_power=0.90 | `[fan]` pin=!PE6 (**inverted**), max_power=0.60 | **Different pin**, polarity, power |
| Heatsink fan | `[heater_fan]` pin=PA2 | `[fan_generic]` pin=PE8 with template hysteresis | **Different type** — T1 uses template-based control |
| Motherboard fan | `[controller_fan]` pin=PB5 | **None** | **Remove** or check if T1 has one |
| Chamber fan | `[fan_generic]` pin=PB4 | **None** | **Remove** — T1 doesn't have one |
| Drying box fan | `[heater_fan]` pin=PA8 | **None** | **Remove** — T1 has no drying box |
| Delayed gcode for heatsink | Not used | `[delayed_gcode _START_HEATSINK_FAN]` + template | T1-specific — must include |

### 1.13 LEDs & Lighting

| Feature | S1 | T1 | Porting Impact |
|---|---|---|---|
| Chamber LED | `[led]` pin=PC6 (white PWM) | **None** (via MCU) | **Remove** |
| Indicator LEDs | white=PA12, orange=PD1, red=PD0 | **None** | **Remove** — T1 has no indicator LEDs |
| Caselight | Not present | `[output_pin caselight]` host:pwmchip0/pwm0 | **Add** — uses host MCU hardware PWM |
| Neopixel support | Optional (led-mmb-cubic.cfg) | Not present | **Remove** optional config |

### 1.14 Filament Sensors

| Feature | S1 | T1 | Porting Impact |
|---|---|---|---|
| Switch sensor | PA11 (single sensor) | PE7 (effector switch) + PA13 (BTT switch) | **T1 has 2 switches** |
| Motion sensor | PA10 (single sensor) | PA14 (BTT motion) | Different pin |
| Sensor count | 2 (1 switch + 1 motion) | 3 (2 switch + 1 motion) | T1 has extra effector switch |
| Runout behavior | Complex (pause after distance) | Basic pause_on_runout | Different macro approach |

### 1.15 Special Features

| Feature | S1 | T1 | Porting Impact |
|---|---|---|---|
| Drying box | Full system (heater PA9, fan PA8, temp from SHM JSON) | **None** | **Remove** entire drying box subsystem |
| Drying box moonraker sensor | `[sensor_custom Drying_Box]` (jsonfile) | **None** | **Remove** from moonraker.conf |
| Drying box systemd service | `drying-box.service` | N/A | **Don't enable** on T1 |
| Motor calibration | 3× output_pin + 3× gcode_button | **None** | **Remove** — S1-specific auto-calibration |
| Power loss detection | `[gcode_button power_loss]` pin=PD3 | **None** | **Remove** — T1 doesn't have this hardware |
| Relay | pin=PE1 | pin=PD6 | **Different pin** |
| ADXL345 | cs=PE13, sclk=PE10, mosi=PE11, miso=PE12 | cs=PE11, sclk=PE14, mosi=PE13, miso=PE12 | **Different pins** |
| ADXL345 rate | 3200 Hz | 1600 Hz | Config change |
| Endstop phase | Not configured | `[endstop_phase]` enabled | T1-specific — **add** |
| Force move | Enabled | Not used | Keep or remove |
| Beeper | Not present | Commented out (`host:pwmchip0/pwm1`) | Optional — can enable |
| Box fan | Not present | Commented out (PE2) | Optional — can enable |

### 1.16 Software & Klipper Fork

| Feature | S1 | T1 | Porting Impact |
|---|---|---|---|
| Klipper fork | `Guilouz/Klipper-Flsun-S1` | Upstream Klipper (+ load_cell_probe branch) | **Fork compatibility** — S1 fork has custom features |
| KlipperScreen fork | `Guilouz/KlipperScreen-Flsun-S1` | Stock KlipperScreen | S1 fork customized for S1 display/UI |
| Auto PA adjustment | Firmware feature (PA ≤ 0.002 = auto) | Not available | S1 Klipper fork feature |
| Enhanced delta calibrate | `enhanced_method: True` | Not available | S1 Klipper fork feature |
| `x_size_offset` / `y_size_offset` | In `[printer]` section | Not available | S1 Klipper fork feature |
| `load_cell_probe` | Not used | Required for T1 probe | **Must use Klipper branch with load cell support** |
| `simple_tap_classifier` | Not available | Used for probe analysis | Klipper load cell branch feature |
| FLSUN OS Dependencies repo | `Guilouz/FLSUN-S1-Open-Source-Edition-Dependencies` | N/A | Contains easy-installer, OTA update scripts |
| Moonraker update manager | Configured for S1 fork repos | Needs T1 repos | Update all `origin:` URLs |

### 1.17 OS Build & Services

| Feature | S1 | T1 | Porting Impact |
|---|---|---|---|
| Base OS | Debian 13 Trixie (armhf) | Debian 13 Trixie (armhf) target | **Same base** — debos recipe reusable |
| Hostname template | `FLSUN-S1-XXXX` | Needs `FLSUN-T1-XXXX` | Change in `first-boot.sh` |
| NPU init | `S60NPU_init` (galcore.ko, RKNN) | RV1109 has NPU — needs testing | Verify galcore.ko compatibility |
| Power key | `input-event-daemon` → `power-key.sh` | Should work with `rk8xx_pwrkey` | Verify input device paths |
| rc.local | CPU governor, backlight, bluetooth, WiFi | Same functions needed | Verify sysfs paths |
| Systemd services | 7 custom services | Remove `drying-box.service`, add `klipper_mcu` | Service list adjustment |
| webcamd | MJPG-Streamer | Same | Camera device may differ |
| first-boot.sh | rootfs resize, hostname, SSH, web-UI config | Rewrite for T1 partition layout | **Significant rework** |
| zram swap | Enabled in first-boot.sh | Same approach | **No change** |

### 1.18 WiFi & Networking

| Feature | S1 | T1 | Porting Impact |
|---|---|---|---|
| WiFi module | AP6212 (BCM43438) | AP6212 (BCM43438) | **Identical** — no changes |
| WiFi standard | 802.11 b/g/n, 2.4 GHz | 802.11 b/g/n, 2.4 GHz | **Identical** |
| WiFi interface | SDIO at `0xffc70000` | SDIO at `0xffc70000` | **Identical** address & config |
| WiFi driver | `bcmdhd` (built-in) | `bcmdhd` (built-in) | **Identical** |
| Firmware source | Vendor blobs `/vendor/etc/firmware/` | Same path | **No change** — do NOT install `firmware-brcm80211` |
| WiFi power GPIO | GPIO0_A6 (active-low) | GPIO0_A6 (active-low) | **Identical** |
| WiFi wake IRQ | GPIO0_B0 (active-high) | GPIO0_B0 (active-high) | **Identical** |
| Bluetooth | BCM20710 (BT 4.0+BLE) via UART0 | Same | **Identical** |
| BT power GPIO | GPIO0_A7 | GPIO0_A7 | **Identical** |
| NetworkManager | Yes | Same | **Identical** |
| SDIO pinctrl drive | `0xc2` (drive level 2) | `0xc0` (drive level 0) | **Minor** — S1 value works on T1 |
| Hostname template | `FLSUN-S1-XXXX` | Needs `FLSUN-T1-XXXX` | Change in `first-boot.sh` |

> **Detail:** See `docs/T1/research/03-wifi-subsystem-comparison.md` for full DTB node-by-node analysis.

---

## 2. Porting Categories

### 2.1 Identical — No Changes Needed

These components are architecturally the same and need no modification:

- Delta kinematics (same motion system type)
- TMC5160 driver IC (same protocol/registers, different pins)
- Extruder drive (same rotation_distance, same Klipper config structure)
- USB-UART chip (CH340 on both, same device path)
- Katapult bootloader (same flash offset 0x8007000)
- SPI ADXL345 accelerometer (same chip, different pins)
- Debian 13 Trixie base OS
- debos build system structure
- Nginx + Mainsail web UI stack
- Moonraker API server
- KIAUH installer framework
- WiFi module (AP6212/BCM43438 — same chip, same GPIO pins, same SDIO controller, same driver, same firmware)

### 2.2 Pin Remapping Only — Config Changes

These need only GPIO pin changes in Klipper configs:

- All stepper step/dir/enable pins (6 axes × 3 pins = 18 pins)
- All TMC5160 SPI pins (4 drivers × 4 pins = 16 pins)
- All endstop pins (3 pins)
- Extruder heater & thermistor pins
- Bed heater & thermistor pins
- ADXL345 SPI pins
- Relay pin (PE1 → PD6)
- Fan pins (but also change types — see below)

### 2.3 Config/Parameter Changes

Values that differ but stay in the same config structure:

- Print radius (183 → 133)
- Delta radius (183 → 171.8)
- Arm lengths (385 → 333–336, per-arm)
- Position endstop (435 → ~331)
- Max velocity (1200 → 1000)
- Max acceleration (40000 → 30000)
- Bed mesh radius (154 → 100)
- Delta calibrate radius (154 → 123.5)
- Max temps (extruder 370→320, bed 140→130)
- Microsteps (16 → 32 for steppers)
- Run currents (extruder 0.8→1.2 A, steppers need values)
- ADXL345 rate (3200 → 1600)
- KlipperScreen display resolution (1024×600 → 800×480)
- Hostname (FLSUN-S1 → FLSUN-T1)

### 2.4 Features to Remove (S1-only)

These S1-specific features have no T1 hardware counterpart:

- **Drying box** — entire subsystem (heater, fan, temp sensor, systemd service, moonraker sensor)
- **Dual bed heater** — `heater_bed_2` section and verify macros
- **Motor calibration** — 3× `output_pin _motor_cali_*` + 3× `gcode_button motor_*`
- **Power loss detection** — `filament_switch_sensor power_loss` + `gcode_button power_loss`
- **Chamber fan** — `fan_generic chamber_fan`
- **Chamber LED** — `led chamber_led` (white PWM)
- **Indicator LEDs** — 3× `output_pin _led_*` (white, orange, red)
- **S1 Klipper fork features** — auto PA, enhanced delta calibrate, size offsets
- **flsun-os.cfg** macros — setup wizard, OTA update (S1-specific)

### 2.5 Features to Add (T1-specific)

These T1 features don't exist in the S1 build:

- **Load cell probe** — `[load_cell_probe]` with HX717 sensor, `[simple_tap_classifier]`
- **LoadCell MCU** — secondary STM32F103 MCU config, firmware build, `/dev/ttyS0`
- **Host MCU** — `[mcu host]` + `klipper_mcu` Linux service for hardware PWM
- **Caselight** — `[output_pin caselight]` via host PWM (`pwmchip0/pwm0`)
- **Heatsink fan with hysteresis** — `[display_template HEATSINK_FAN]` + `[delayed_gcode _START_HEATSINK_FAN]`
- **Effector filament switch** — additional `[filament_switch_sensor effector_switch]`
- **BTT filament sensors** — `[filament_switch_sensor btt_switch]` + `[filament_motion_sensor btt_motion]`
- **Endstop phase** — `[endstop_phase]` for stepper calibration
- **Homing override** — `[homing_override]` with Z-5 post-home correction
- **SciPy dependency** — needed for load cell probe filters
- **T1-specific DTB** — 800×480 display timing, different GPIO assignments

### 2.6 Decisions Required

Architectural choices that affect the porting strategy:

1. **Klipper fork**: Use Guilouz S1 fork (with S1-specific features removed) or upstream Klipper with load cell branch?
2. **KlipperScreen fork**: Use S1 fork (has FLSUN UI customizations) or upstream (more compatible with load cell)?
3. **Boot image format**: Keep S1's Android boot format (simpler, use existing `mkbootimg` script) or match T1's FIT format?
4. **Partition layout**: Use S1 layout (6 partitions) or T1 layout (9 partitions)?
5. **Kernel version**: Use 6.1.99 (S1 proven, modern) or 4.19.111 (T1 stock proven)?
6. **FLSUN OS Dependencies**: Fork/adapt for T1, or create new T1-specific dependency repo?
7. **Web UI**: Keep Mainsail (used by both) or switch to Fluidd (S1 fork supports both)?

---

## 3. Porting Todo List

### Phase 1: Kernel & Boot (Foundation)

| # | Task | Difficulty | Status | Notes |
|---|---|---|---|---|
| 1.1 | Build 6.1.99 kernel with `rv1126_defconfig` for T1 | Medium | Not started | Same defconfig as S1, verify it boots on 2-core RV1109 |
| 1.2 | Create T1 device tree (DTB) | Hard | Not started | Start from stock T1 DTB (4.19), port to 6.1.99 DTS format. Key nodes: display (800×480), GPIO, SPI, I2C, UART, PWM |
| 1.3 | Verify display panel timing in DTB | Medium | Not started | 800×480 @ 25 MHz pixel clock in `simple-panel` node |
| 1.4 | Verify touch controller (Goodix) in DTB | Easy | Not started | Check I2C address, IRQ pin, reset pin |
| 1.5 | Test kernel boot on T1 hardware | Medium | Not started | Need USB-C Maskrom access to flash |
| 1.6 | Decide on boot image format (Android vs FIT) | Decision | Not started | Android boot is simpler (existing `mkbootimg` pipeline) |
| 1.7 | Create/adapt boot image packaging script | Medium | Not started | Either `build-boot-img.sh` (Android) or FIT `mkimage` |
| 1.8 | Determine eMMC partition layout for T1 | Medium | Not started | Map partition addresses for RKDevTool |

### Phase 2: MCU Firmware (Hardware Interface)

| # | Task | Difficulty | Status | Notes |
|---|---|---|---|---|
| 2.1 | Build Klipper MCU firmware for GD32F303 (main MCU) | Easy | Not started | Use T1 `.config` (STM32F103xe, 72 MHz, USART3, 0x8007000) |
| 2.2 | Build Katapult bootloader for GD32F303 | Easy | Not started | Same target as Klipper MCU, flash offset 0x8000000 |
| 2.3 | Flash main MCU via ST-LINK or SD card | Easy | Not started | SD card method: rename to `Robin_nano35.bin` on FAT32 |
| 2.4 | Build Klipper MCU firmware for LoadCell MCU | Medium | Not started | Need to determine STM32F103 `.config` for secondary MCU |
| 2.5 | Flash LoadCell MCU | Medium | Not started | Likely ST-LINK only — verify flash method |
| 2.6 | Build & install `klipper_mcu` Linux service (host MCU) | Easy | Not started | Standard `klipper/scripts/install-*.sh` script |
| 2.7 | Verify `/dev/ttyS0` UART for LoadCell MCU | Easy | Not started | Ensure DTB enables the correct UART |

### Phase 3: Klipper Configuration (Printer Control)

| # | Task | Difficulty | Status | Notes |
|---|---|---|---|---|
| 3.1 | Create T1 `printer.cfg` with correct pin mapping | Medium | Not started | Use T1-pyro config as reference, adapt to S1 format |
| 3.2 | Configure TMC5160 drivers (4 axes, per-stepper SPI) | Easy | Not started | Pins from T1-pyro config, sense_resistor=0.0375 |
| 3.3 | Configure load cell probe (`[load_cell_probe]`) | Medium | Not started | HX717, LoadCell MCU pins, requires SciPy |
| 3.4 | Configure `[simple_tap_classifier]` | Easy | Not started | Default values likely fine |
| 3.5 | Configure heatsink fan with hysteresis template | Easy | Not started | Copy from T1-pyro config |
| 3.6 | Configure filament sensors (3 sensors) | Easy | Not started | effector_switch + btt_switch + btt_motion |
| 3.7 | Configure caselight (host PWM) | Easy | Not started | `host:pwmchip0/pwm0`, needs host MCU |
| 3.8 | Configure delta geometry (radius, arms, endstops) | Easy | Not started | Use T1-pyro values as starting point |
| 3.9 | Create T1 `config.cfg` (modular includes) | Easy | Not started | Remove S1-only includes, add T1-specific files |
| 3.10 | Create T1 fan config | Easy | Not started | Part cooling (inverted!), heatsink (generic), no chamber/mobo fan |
| 3.11 | Create T1 LED config (caselight only) | Easy | Not started | Remove chamber/indicator LEDs, add caselight |
| 3.12 | Create T1 filament sensor config | Easy | Not started | 2 switches + 1 motion sensor |
| 3.13 | Create T1 macros (PAUSE, RESUME, etc.) | Medium | Not started | Adapt S1 macros: remove dual-bed, drying box, power loss refs |
| 3.14 | Remove S1-specific features from configs | Easy | Not started | Motor calibration, power loss, drying box, dual bed |
| 3.15 | Add `[homing_override]` for T1 | Easy | Not started | G28 + Z-5 + move to center |
| 3.16 | Add `[endstop_phase]` | Easy | Not started | Enable for all 3 steppers |
| 3.17 | Calibrate PID values for T1 extruder and bed | Easy | Not started | Run `PID_CALIBRATE` on actual hardware |

### Phase 4: Moonraker Configuration

| # | Task | Difficulty | Status | Notes |
|---|---|---|---|---|
| 4.1 | Create T1 `moonraker.conf` | Easy | Not started | Remove `[sensor_custom Drying_Box]` |
| 4.2 | Update update_manager repos | Easy | Not started | Change Klipper/KlipperScreen origins if using different forks |
| 4.3 | Remove FLSUN-OS-Dependencies update manager | Easy | Not started | Or create T1-specific dependency repo |
| 4.4 | Add `klipper_mcu` to `moonraker.asvc` | Easy | Not started | Allow moonraker to manage host MCU service |

### Phase 5: Build System Adaptation

| # | Task | Difficulty | Status | Notes |
|---|---|---|---|---|
| 5.1 | Create T1 variant of `flsun-os.yaml` (or parameterize) | Hard | Not started | Add T1 variables (hostname, image_size), conditional stages |
| 5.2 | Add `scipy` to Python packages | Easy | Not started | Required by load cell probe |
| 5.3 | Modify Stage 12 for T1 Klipper fork/branch | Medium | Not started | Decide which Klipper repo/branch to clone |
| 5.4 | Add `klipper_mcu` build step | Medium | Not started | Compile Linux MCU firmware and install service |
| 5.5 | Modify Stage 15 overlays for T1 | Medium | Not started | T1-specific systemd services (no drying-box, add klipper_mcu) |
| 5.6 | Modify Stage 16 printer_data for T1 configs | Easy | Not started | Copy T1 configs instead of S1 configs |
| 5.7 | Modify Stage 18 service list for T1 | Easy | Not started | Remove `drying-box.service`, add `klipper-mcu.service` |
| 5.8 | Update `first-boot.sh` for T1 | Medium | Not started | Hostname `FLSUN-T1-XXXX`, partition resize for T1 layout |
| 5.9 | Update `rc.local` for T1 | Easy | Not started | Verify sysfs paths (backlight, CPU governor) |
| 5.10 | Create T1 `build-boot-img.sh` or adapt existing | Medium | Not started | Depends on boot format decision (Phase 1.6) |
| 5.11 | Create T1 `package-emmc.sh` | Easy | Not started | Adjust partition layout for T1 eMMC |
| 5.12 | Update NPU init script for RV1109 | Low | Not started | May not be needed — NPU is optional |

### Phase 6: KlipperScreen & Display

| # | Task | Difficulty | Status | Notes |
|---|---|---|---|---|
| 6.1 | Configure KlipperScreen for 800×480 | Easy | Not started | Resolution, font sizes, layout adjustments |
| 6.2 | Decide on KlipperScreen fork | Decision | Not started | S1 fork has FLSUN branding/features; upstream is more generic |
| 6.3 | Verify Goodix touch input works | Easy | Not started | Check `/dev/input/event1` path |
| 6.4 | Verify X11/fbdev for 800×480 panel | Easy | Not started | Should work with correct DTB |

### Phase 7: Testing & Validation

| # | Task | Difficulty | Status | Notes |
|---|---|---|---|---|
| 7.1 | Boot test — kernel + rootfs on T1 | Critical | Not started | First hardware test |
| 7.2 | Display test — console + KlipperScreen | Medium | Not started | Verify 800×480 output |
| 7.3 | MCU communication test — main MCU | Medium | Not started | `ls /dev/serial/by-id/` |
| 7.4 | MCU communication test — LoadCell MCU | Medium | Not started | Verify `/dev/ttyS0` |
| 7.5 | Stepper motor test — all 4 axes | Medium | Not started | TMC5160 SPI communication, movement |
| 7.6 | Heater test — extruder + bed | Easy | Not started | PID tune |
| 7.7 | Probe test — load cell homing + mesh | Medium | Not started | Most critical — depends on LoadCell MCU |
| 7.8 | Fan test — part cooling + heatsink | Easy | Not started | Verify inverted fan polarity |
| 7.9 | Filament sensor test — all 3 sensors | Easy | Not started | Switch + motion detection |
| 7.10 | Full print test | Easy | Not started | End-to-end validation |
| 7.11 | WiFi / networking test | Easy | Not started | **Low risk** — same AP6212 chip, same GPIOs, same driver. See `03-wifi-subsystem-comparison.md` |
| 7.12 | Camera test — MJPG-Streamer | Easy | Not started | If T1 has camera |

---

## 4. Risk Assessment

### High Risk

1. **Kernel 6.1.99 boot on RV1109**: The S1 kernel (6.1.99) was built for RV1126 (quad-core). RV1109 is dual-core same die, but kernel boot on RV1109 is unverified. If it fails, may need to use stock 4.19 kernel or investigate compatibility.

2. **Device tree porting**: The T1 stock DTB (4.19) uses older bindings. Porting to 6.1.99 DTS format may require significant changes to node names, compatible strings, and property formats.

3. **Load cell probe Klipper branch**: The `[load_cell_probe]` feature is not in mainline Klipper — it's in an experimental branch (Gareth Farrington's load_cell branch). This creates a fork management challenge: need a Klipper build that has BOTH S1 fork features AND load cell support, or choose one.

4. **S1 Klipper fork compatibility with T1**: The `Guilouz/Klipper-Flsun-S1` fork contains S1-specific patches (auto PA, enhanced delta calibrate). These may not conflict with T1 hardware, but the fork may not include load cell probe support.

### Medium Risk

5. **GD32F303 MCU compatibility**: GD32F303 is STM32F103-compatible but not identical. Some edge cases in Klipper MCU firmware may behave differently (timers, DMA, flash write speeds).

6. **Secondary LoadCell MCU**: Building and flashing firmware for the secondary STM32F103 is undocumented in the S1 build system. Need to add a build step and flash method.

7. **Boot format decision**: Choosing between Android boot (S1 style, existing tooling) and FIT (T1 stock, may be required by T1 U-Boot) affects the entire boot pipeline.

### Low Risk

8. **Display 800×480**: Simple DTB timing change, proven to work on stock T1.
9. **Pin remapping**: Tedious but straightforward — all pin assignments documented.
10. **Service configuration**: Mostly additive/subtractive changes to systemd units.

---

## 5. Recommended Porting Sequence

```
Phase 1 (Kernel & Boot) ──→ Phase 2 (MCU Firmware) ──→ Phase 7.1-7.4 (Boot + MCU Tests)
                                                              │
                                                              ▼
Phase 3 (Klipper Config) + Phase 4 (Moonraker) ──→ Phase 7.5-7.9 (Hardware Tests)
                                                              │
                                                              ▼
Phase 5 (Build System) + Phase 6 (KlipperScreen) ──→ Phase 7.10-7.12 (Full Tests)
```

**Recommended approach:**
1. Start with kernel boot test (Phase 1.1–1.5) — this validates the entire foundation
2. If kernel works, flash MCU firmware (Phase 2) — validates hardware control
3. Create minimal Klipper config (Phase 3, subset) — get motors moving
4. Add probe, fans, sensors incrementally
5. Only automate build system (Phase 5) once manual process is proven

---

## 6. Quick Reference: File Changes Needed

| Source File (S1) | Action | Target File (T1) |
|---|---|---|
| `resources/S1/klipper-configs/printer.cfg` | **Rewrite** | New T1 `printer.cfg` |
| `resources/S1/klipper-configs/config.cfg` | **Modify** | T1 `config.cfg` (different includes) |
| `resources/S1/klipper-configs/Configurations/fan-stock.cfg` | **Rewrite** | T1 fan config |
| `resources/S1/klipper-configs/Configurations/led-stock.cfg` | **Rewrite** | T1 LED/caselight config |
| `resources/S1/klipper-configs/Configurations/filament-sensor-stock.cfg` | **Rewrite** | T1 filament sensor config |
| `resources/S1/klipper-configs/Configurations/flsun-os.cfg` | **Modify** | Remove S1-specific macros |
| `resources/S1/klipper-configs/Configurations/macros.cfg` | **Modify** | Remove dual-bed, drying box, power loss refs |
| `resources/S1/klipper-configs/moonraker.conf` | **Modify** | Remove Drying_Box sensor, update repos |
| `build/flsun-os.yaml` | **Fork or parameterize** | T1 build recipe variant |
| `build/overlays/system/etc/init.d/first-boot.sh` | **Modify** | T1 hostname, partition handling |
| `build/overlays/system/etc/rc.local` | **Verify** | Check sysfs paths |
| `build/overlays/system/etc/systemd/system/*.service` | **Modify** | Remove drying-box, add klipper_mcu |
| `build/build-boot-img.sh` | **Adapt or replace** | T1 boot image format |
| `build/package-emmc.sh` | **Modify** | T1 partition addresses |
