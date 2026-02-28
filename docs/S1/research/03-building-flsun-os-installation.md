# How to Build: FLSUN OS Installation on Printer

**Date researched:** 2026-02-28  
**Difficulty:** Intermediate to Advanced  
**Time required:** 1-3 hours depending on method

---

## Overview

"Building" FLSUN OS means **flashing a pre-built OS image** onto the printer's core board, then **flashing MCU firmware** onto the motherboard. There is no "compile the OS from scratch" step — the OS images are pre-built by Guilouz and distributed as GitHub release assets.

---

## Two Installation Methods

### Method A: Boot from microSD Card (Recommended for Beginners)

**Non-destructive** — Stock OS on eMMC is preserved. Acts as a dual-boot.

### Method B: Install on eMMC (Advanced Users Only)

**Overwrites eMMC** — Faster read/write, more durable, but riskier.

---

## Complete Process Summary (Official Order)

1. **Prepare microSD Card for FLSUN OS** (or Install on eMMC)
2. **Flash Motherboard Firmware** (Katapult bootloader + Klipper)
   - Install STM32 ST-LINK Utility
   - Connect ST-LINK V2 Programmer
   - Backup Motherboard Firmware
   - Flash Bootloader and Klipper Firmware
3. **Flash Closed Loops Boards** (Optional, recommended for S1 only, NOT S1 Pro)
4. **Insert microSD Card in Core Board** (if using SD method)
5. **First Boot** — OS auto-configures, then reboots
6. **Update and Configure Printer**
7. **SSH Connection** — Set up remote access
8. **Update Time Zone**
9. **Extend Storage Partition** (via Easy Installer)
10. **Configure Slicer Settings**

---

## Step-by-Step Details

### Step 1: Prepare microSD Card

**Prerequisites:**
- microSD card ≥ 16GB (SanDisk Extreme PRO recommended)
- [Raspberry Pi Imager](https://www.raspberrypi.com/software/) (imaging tool)
- FLSUN OS image (SD version): `FLSUN-OS-S1-SD-3.0.img.gz`
  - Download from [GitHub Releases](https://github.com/Guilouz/FLSUN-S1-Open-Source-Edition/releases)
  - Also available on [Google Drive](https://drive.google.com/file/d/1b156EbYKD7dWgTefLHgGV__uUrDGyFWI/view?usp=sharing)

**Process:**
1. Insert microSD into computer
2. Open Raspberry Pi Imager
3. Choose OS → Use Custom → select `.img.gz` file
4. Choose Storage → select microSD card
5. Click NEXT → when asked about OS customisation, click **NO**
6. Confirm with YES
7. Wait for write + verification to complete

### Step 2: Flash Motherboard Firmware

**Why:** The motherboard MCU needs updated firmware to work with the latest Klipper.

**Prerequisites:**
- `motherboard_fw.bin` — Combined Katapult Bootloader + Klipper Firmware
- STM32 ST-LINK Utility v4.6.0 (Windows only)
- ST-LINK V2 Programmer (hardware, ~$10-15 on Amazon)
- 4x Dupont cables (usually included with programmer)

**Process:**
1. Install STM32 ST-LINK Utility on PC
2. Power off printer
3. Connect motherboard JTAG pins to ST-LINK V2 via Dupont cables
4. Connect ST-LINK V2 to PC USB
5. Open STM32 ST-LINK Utility → Connect to target
6. **BACKUP first!** File → Save As → save as `.bin` (should be 512 KB)
7. File → Open file → select `motherboard_fw.bin`
8. Click Program verify → Start
9. Wait for success → Disconnect → remove cables

**Important notes:**
- Pin positions vary between STM32 programmer clones — verify before connecting
- If Read Out Protection error: Target → Option Bytes → set to Disabled → Apply
- Backup is critical — needed to restore stock OS later

### Step 3: Flash Closed Loops Boards (S1 Only)

**Why:** Improves stepper motor resonances and fixes salmon skin artifacts. Uses the same firmware as S1 Pro.

**Prerequisites:**
- `closed_loop_board_fw.bin`  
- STM32 ST-LINK Utility
- ST-LINK V2 Programmer
- Dupont connection cable (from FLSUN Silent Kit)
- `Closed_Loop_Boards_Tool.stl` (3D printed tool for contact)

**Process:**
1. Power off printer
2. Unplug 3 cables from the Closed Loop Board
3. Attach Dupont cable to printed STL tool → connect to ST-LINK V2
4. Place tool on Closed Loop Board (ensure contact)
5. Connect ST-LINK V2 to PC → Connect to target
6. Open `closed_loop_board_fw.bin` → Program verify → Start
7. Repeat for all 3 boards

**Warning:** FLSUN Dupont cable colors for 3.3V and GND are reversed!

### Step 4: Insert microSD Card in Core Board

Physical installation of the prepared microSD card into the printer's core board (behind the screen).

### Step 5: First Boot

1. Power on printer → should see "Open Source Edition" boot logo
2. OS performs initial setup (resizing, configuring), then auto-reboots
3. After reboot, wait for KlipperScreen to appear
4. LEDs on left side light up white when Klipper connects
5. Configure WiFi: Configurations → System → Network

### Step 6: Update and Configure Printer

Three methods available:
- **KlipperScreen:** Configurations → Updates → Full Update + Setup Wizard
- **Mainsail/Fluidd:** Update Manager → refresh → update all
- **SSH Easy Installer:** `easy-installer` command → Update menu

**Post-update calibrations:**
- Motors Calibration
- Z Offset Calibration
- Bed Mesh (Delta Calibration + Bed Leveling)
- Input Shaper (Resonances)

---

## Alternative: Install on eMMC (Advanced)

**Prerequisites:**
- USB-A to USB-C data cable
- RKDevTool v2.96 (Windows only)
- Rockchip DriverAssistant v5.0
- FLSUN OS image (EMMC version): `FLSUN-OS-S1-EMMC-3.0.7z`

**Process:**
1. **Backup eMMC first** by booting from SD, then `dd` each partition to USB drive
2. Install Rockchip drivers
3. Power off → disassemble screen housing → connect USB-C to core board
4. Open RKDevTool
5. Enter USB Mode: Hold BOOT9200 → Press+Release BOOT2100 → Release BOOT9200
6. Select boot.img and rootfs.img → Run → wait for completion
7. Reassemble screen

**Recovery:** Full stock eMMC backup available: `STOCK-OS-S1-EMMC-1.0.6.4.7z` (Google Drive)

---

## Updating MCU Firmware (After Initial Setup)

Once Katapult bootloader is installed, future firmware updates don't need the ST-LINK programmer:

```bash
# Via Easy Installer
easy-installer
# → Update menu → Update Motherboard MCU firmware
```

### Building Custom Firmware (Advanced)

You can compile your own Katapult + Klipper firmware on the printer itself:

```bash
# Build Katapult bootloader
cd ~/katapult && git reset --hard && git pull
make menuconfig   # Configure for STM32
make clean && make

# Build Klipper firmware
cd ~/klipper && git reset --hard && git pull
make menuconfig   # Configure for STM32
make clean && make

# Combine into single flashable binary
cd && ./flsun-os/system/merge_firmware.py
# Output: ~/motherboard_fw.bin
```

---

## SSH Access

- **Software:** MobaXterm recommended
- **Credentials:**
  - User: `pi` / Password: `flsun`
  - User: `root` / Password: `flsun`
- **Connection:** SSH to printer's IP address (shown on KlipperScreen)
