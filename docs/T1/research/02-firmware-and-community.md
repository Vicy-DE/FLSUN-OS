# FLSUN T1 — Firmware, OS Images & Community Status

**Date researched:** June 2025  
**Sources:**
- https://github.com/Guilouz/FLSUN-S1-Open-Source-Edition/discussions/13
- https://flsun3d.com/pages/t1-support
- https://github.com/mulcmu/T1-pyro
- https://github.com/search?q=flsun+t1+firmware&type=repositories

---

## Official Open Source Edition Status

**There is no FLSUN T1 Open Source Edition.** Guilouz (maintainer of the S1 Open Source Edition) has stated that a T1 edition is **"not planned"**.

The S1 Open Source Edition cannot be directly used on the T1 because:

1. **Different SoC:** S1 uses RV1126, T1 uses RV1109 — different device trees and potentially different SDK/kernel builds
2. **Different display:** The T1 screen has a different resolution, driver IC, and pinout — S1 OS produces vertical lines on T1 screen
3. **Different MCU:** T1 uses GD32F303 (STM32F103-compatible) vs S1's STM32 variant
4. **Different probe:** T1 uses strain gauge with HX717 load cell ADC vs S1's approach

---

## Official FLSUN Firmware

### FLSUN T1 Support Page

**URL:** https://flsun3d.com/pages/t1-support

The official FLSUN support page for the T1 exists and contains:
- "DOWNLOAD PRODUCT FIRMWARE" section
- "TROUBLESHOOTING (FAQ)" section

However, the actual download links are loaded via JavaScript and could not be retrieved via static page fetching. Users must visit the page in a browser to access firmware downloads.

> **TODO:** Visit the support page in a browser to obtain direct download URLs for T1 stock firmware files.

### Stock Firmware Content (Expected)

Based on S1 patterns, the T1 stock firmware likely includes:
- Motherboard MCU firmware (`.bin` file for GD32F303/STM32F103)
- OS image or update package
- Possibly closed-loop board firmware (if applicable to T1)

---

## Community Firmware / OS Image Efforts

### Chumannn — dd-copied T1 Image

In [Discussion #13](https://github.com/Guilouz/FLSUN-S1-Open-Source-Edition/discussions/13), user **Chumannn** reported:

- Successfully `dd`-copied the entire T1 eMMC image
- Reflashed it via **USB-C** using **RKDevTool** (same Rockchip tool used for S1)
- Got Klipper + KlipperScreen working with touch calibration after reflash

**Key insight:** The T1 eMMC can be accessed via USB-C in Rockchip Maskrom mode, similar to the S1. The `dd`-copied image was functional after reflash.

**Status:** Chumannn did not publicly share the dd image.

### LayerDE — Offered T1 Firmware Image

In the same discussion, user **LayerDE** (the workspace owner):

- Confirmed the T1 uses RV1109 SoC
- Offered to provide a T1 firmware image
- Asked Guilouz about building Debian 12 for the RV1109

**Status:** No publicly shared image found as of this research.

### mulcmu — T1-pyro (Raspberry Pi Replacement)

Rather than trying to modify the T1's stock OS, mulcmu took a different approach: **replace the entire host board with a Raspberry Pi 4**.

**Repository:** https://github.com/mulcmu/T1-pyro

This project provides:
- Complete `printer.cfg` with all pin mappings
- MCU firmware config (`.config` for Klipper `make menuconfig`)
- Pre-built MCU firmware: `Robin_nano35.bin v0.12.0-432-gfec3e685c`
- KiCad schematics for all T1 boards
- Custom cable wiring documentation

**This is currently the most complete open-source resource for the T1.**

---

## Firmware Binary Dumps — Search Results

### GitHub Repository Search

A search for "flsun t1 firmware" on GitHub returned:
- **0 repositories** matching
- **3 discussions** (all in the Guilouz/FLSUN-S1-Open-Source-Edition repo, already reviewed)
- **12 issues** (mostly S1-related)

### Other Sources Checked

| Source | Result |
|---|---|
| GitHub repos | No T1 firmware repositories found |
| GitHub discussions | Discussion #13 has community hardware findings |
| Reddit r/FLSUN | No T1 firmware dumps found |
| FLSUN wiki (wiki.flsun3d.com) | Page exists but content not extractable |
| FLSUN store (EU/US) | Product pages return 404 or redirect |
| 3D printing review sites | Hardware reviews only, no firmware |

### Available MCU Firmware

The only publicly available T1 MCU firmware binary is in the T1-pyro repository:

| File | Details |
|---|---|
| `Robin_nano35.bin` | Klipper MCU firmware v0.12.0-432-gfec3e685c |
| Location | `https://github.com/mulcmu/T1-pyro/tree/main/mcu` |
| Target | STM32F103xe (GD32F303), 72 MHz, USART3, 28 KiB bootloader |

> **Note:** This is a custom Klipper build, NOT the stock FLSUN firmware. The stock firmware has not been publicly dumped.

---

## OS Image Flashing — What We Know

### Method 1: USB-C + RKDevTool (Confirmed Working)

From Chumannn's report:
1. T1 has a USB-C port that can enter Rockchip Maskrom mode
2. RKDevTool v2.96 (same tool as S1) can communicate with the T1
3. `dd`-copied images can be written back successfully
4. This is the same approach used for S1 eMMC flashing

### Method 2: SD Card Boot (Unconfirmed for T1)

The S1 supports booting from microSD card. It is unknown whether the T1 supports this, but since both use Rockchip SoCs with similar boot flows, it may be possible.

### Building a Custom OS Image for T1

LayerDE asked Guilouz about building Debian 12 for the RV1109. Key challenges:

1. **Rockchip SDK:** Need RV1109-specific device tree and boot components (U-Boot, kernel)
2. **Display driver:** Need the correct framebuffer/DRM driver for the T1's screen
3. **KlipperScreen:** Would need configuration for the T1's different display resolution
4. **MCU firmware:** The GD32F303 requires separate Klipper compilation with STM32F103xe target
5. **Load cell probe:** The STM32F103 on the lower adapter board needs its own firmware

---

## Community Pain Points

Based on Discussion #13 and T1-pyro issues:

### 1. Debian 10 / Python 3.7 Limitations
- SSL certificate verification failures
- Cannot install modern pip packages
- OctoAnywhere and other tools don't work
- No path to upgrade without full OS replacement

### 2. FLSUN Custom Klipper Modifications
- CmnZnz reports "lots of FLSUN custom stuff" in the Klipper image
- Custom macros, modified Klipper source, proprietary screen integration
- Makes it difficult to use standard Klipper updates

### 3. Screen Incompatibility
- S1 OS cannot be used on T1 due to different display hardware
- T1 screen has unknon driver IC, resolution, and pinout
- Running S1 OS on T1 produces vertical lines

### 4. Limited Official Support
- FLSUN support page exists but firmware downloads are behind JavaScript
- No official documentation for board pinouts or MCU configuration
- No official open-source initiative for the T1

---

## Recommendations for T1 Users

1. **For Klipper MCU firmware:** Use the T1-pyro `printer.cfg` and MCU `.config` as a reference, even if not replacing the host board with a Raspberry Pi
2. **For OS-level changes:** Consider the T1-pyro approach (Raspberry Pi 4 replacement) as the most mature option
3. **For firmware backup:** Use USB-C + RKDevTool to `dd`-copy your eMMC before making changes
4. **For MCU flashing:** Acquire an ST-Link V2 programmer as SD card flashing may not work on newer firmware versions
5. **Stay informed:** Monitor Discussion #13 for community developments

---

## Summary

| Aspect | Status |
|---|---|
| Official Open Source Edition | **Not planned** |
| Stock OS firmware dumps | **Not publicly available** |
| Stock MCU firmware dumps | **Not publicly available** |
| Custom Klipper MCU firmware | **Available** (T1-pyro) |
| Board schematics | **Available** (T1-pyro KiCad) |
| Complete printer.cfg | **Available** (T1-pyro) |
| Raspberry Pi replacement project | **Available** (T1-pyro) |
| eMMC flashing method | **Confirmed** (USB-C + RKDevTool) |
| Community OS image | **Not available** |
