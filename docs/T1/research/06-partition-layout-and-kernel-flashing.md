# T1 Partition Layout, Kernel Flashing & Stock Update Analysis

**Date researched:** 2026-03-01  
**Sources:**
- `resources/T1/firmwares/stock/` — eMMC partition dumps (9 files)
- `resources/T1/stock update/T1/T1 - Update 1.0.9.3 (20).zip`
- `resources/T1/stock update/T1 Pro/T1 Pro - Update 1.0.1.1 (20).zip`
- `resources/S1/stock update/S1/S1 - Update 1.0.8.2 (85).zip`
- `resources/S1/stock update/S1 Pro/S1 Pro - Update 1.0.1.1 (85).zip`
- `docs/T1/research/04-stock-firmware-analysis.md`
- `docs/S1/research/09-image-reverse-engineering.md`

---

## 1. T1 eMMC Partition Layout

The FLSUN T1 uses an 8 GB eMMC with a GPT partition table. The chip has three addressable regions: the main user area and two hardware boot partitions (boot0/boot1).

### Physical Layout

| Region | Stock File | Compressed | Decompressed | Contents |
|---|---|---|---|---|
| eMMC boot0 | `1097_0boot0.img` | 4 KB | 4 MB | Empty (all zeros) |
| eMMC boot1 | `1097_0boot1.img` | 4 KB | 4 MB | Empty (all zeros) |
| Full disk | `1097_0.img` | 1,333 MB | ~8 GB | Complete eMMC image with GPT |

### GPT Partition Table

| # | Name | Stock File | Compressed | Decompressed | Format | Contents |
|---|---|---|---|---|---|---|
| p1 | **uboot** | `1097_0p1.img` | 1.17 MB | 4 MB | U-Boot FIT | U-Boot + OP-TEE + DTB |
| p2 | **misc** | `1097_0p2.img` | 4 KB | 4 MB | zeros | Recovery trigger flag |
| p3 | **boot** | `1097_0p3.img` | 6.12 MB | 32 MB | U-Boot FIT | **Kernel + DTB + RSCE resources** |
| p4 | **recovery** | `1097_0p4.img` | 12.61 MB | 32 MB | U-Boot FIT | Kernel + DTB + ramdisk + resources |
| p5 | **backup** | `1097_0p5.img` | 0.03 MB | 32 MB | zeros | Empty |
| p6 | **rootfs** | `1097_0p6.img` | 1,313.7 MB | ~7.17 GB | ext4 | Linux root filesystem |

> **Comparison with S1:** The S1 has the same 6-partition layout (uboot, misc, boot, recovery, backup, rootfs) with identical names and purposes. Both use the standard Rockchip eMMC layout. The key difference is the **boot image format**: T1 stock uses U-Boot FIT, while S1 (and FLSUN-OS) uses Android boot image (mkbootimg).

### Boot Partition (p3) — Stock FIT Image Structure

```
FIT Image (32 MB, D00DFEED magic)
├── /images/
│   ├── kernel     — 7,216,152 bytes (6.88 MB), ARM zImage, LZ4-compressed payload
│   ├── fdt        — 92,572 bytes (90.4 KB), flat_dt (main device tree blob)
│   └── resource   — 973,312 bytes (950 KB), RSCE container
│       ├── rk-kernel.dtb (800p variant — selected via SARADC ch4=500)
│       ├── rv1126-flsun-800p#_saradc_ch4=500.dtb (board-specific overlay)
│       ├── logo.bmp (boot splash)
│       └── logo_kernel.bmp (kernel boot logo)
├── /configurations/
│   └── conf       — signed configuration
└── /conf/signature — signature data
```

### Boot Partition (p3) — FLSUN-OS Android Boot Image Structure

When running FLSUN-OS (ported from S1), the boot partition uses Android boot format instead:

```
Android Boot Image (ANDROID! magic, ~10 MB)
├── Header (2048 bytes, page_size=2048)
├── Kernel (zImage, ~8.5 MB)
│   └── Linux 6.1.99flsun, ARM, gzip-compressed
└── Second Stage (RSCE, ~1.5 MB)
    └── rk-kernel.dtb (T1-patched, 800×480 timings)
```

---

## 2. Where and How to Flash the Kernel

There are **three methods** to update the kernel on the T1, depending on the context:

### Method 1: Full eMMC Flash via RKDevTool (Maskrom Mode)

**When:** Initial FLSUN-OS installation or full recovery  
**What:** Writes boot.img and rootfs.img to eMMC partitions via USB  
**Host OS:** Windows (RKDevTool v2.96)

#### Steps

1. **Enter Maskrom mode**: Power off printer → Hold the Maskrom button on the SoC board → Connect USB-C → Release button
2. **Open RKDevTool v2.96** and verify the device is detected
3. **Flash partition images:**

| Partition | Address | Image File |
|---|---|---|
| boot | (sector for p3) | `boot.img` (Android or FIT format) |
| rootfs | (sector for p6) | `rootfs.img` (ext4) |

> **Note:** The exact sector addresses for the T1 are not yet confirmed. They need to be read from the GPT table on a stock T1 via USB, or calculated from the `1097_0.img` full-disk dump. The S1 uses a `parameter.txt` file to define partition layout for RKDevTool.

4. **Build the boot.img** for T1:
   ```bash
   # Using the Python tool (from S1 FLSUN-OS 3.0 components):
   python build/tools/build-boot-img-t1.py \
       resources/S1/firmwares/os-images/FLSUN-OS-S1-EMMC-3.0/extracted/zImage \
       resources/T1/firmwares/os-images/rk-kernel-t1.dtb \
       resources/T1/firmwares/os-images/boot.img

   # Or using the bash script (supports both Android and FIT formats):
   cd build && ./build-boot-img-t1.sh <zImage> <dtb> [--format android|fit]
   ```

### Method 2: Live Kernel Update via `flsun_kernel_write` (OTA-style)

**When:** Stock firmware OTA updates (used by FLSUN's `update.sh`)  
**What:** Writes a new boot image (`zboot.img`) to the boot partition from within a running system  
**Runs on:** The T1 itself (Linux)

#### How It Works (from stock `update.sh`)

```bash
# The update ZIP contains:
#   others/zboot.img          — new boot image (7.9 MB for T1, 10.67 MB for S1)
#   others/flsun_kernel_write — binary tool that writes zboot.img to boot partition

# The update script calls:
cd /home/pi/upgrade/others/
chmod +x flsun_kernel_write
./flsun_kernel_write          # reads zboot.img from CWD, writes to boot partition
```

The `flsun_kernel_write` tool is a **proprietary Rockchip binary** (~30 KB) that:
1. Opens the eMMC boot partition block device (likely `/dev/mmcblk0p3`)
2. Writes `zboot.img` directly to the partition
3. Does **not** update the rootfs or U-Boot

> **For FLSUN-OS:** This mechanism could be adapted for kernel updates by replacing `zboot.img` with our own boot.img (built from `build-boot-img-t1.py`). However, the exact block device path and partition numbering need to be verified on the T1.

### Method 3: Direct Block Device Write (SSH/Console)

**When:** Manual kernel update on a running FLSUN-OS system  
**What:** Writes boot.img directly to the eMMC boot partition block device  
**Access:** SSH (`pi@<printer-ip>`, password `flsun`)

```bash
# Identify the boot partition block device:
lsblk                           # find mmcblkXp3 (boot partition)
# or
cat /proc/partitions             # list all partitions with sizes

# Example (assuming /dev/mmcblk0p3 is the boot partition):
dd if=boot.img of=/dev/mmcblk0p3 bs=4M
sync
reboot
```

> **Warning:** Writing to the wrong partition will brick the device. Always verify the partition layout with `lsblk` or `fdisk -l` first. Keep the stock firmware partition dumps as backup.

### Boot Format Decision

| Scenario | Format to Use | Tool |
|---|---|---|
| FLSUN-OS (new install) | **Android boot** | `build-boot-img-t1.py` or `mkbootimg` |
| Stock firmware update | U-Boot FIT | `flsun_kernel_write` + `zboot.img` |
| Kernel-only update on FLSUN-OS | **Android boot** | `dd` to boot partition |

The T1's U-Boot **accepts both formats**. This was confirmed by the successful boot of S1's FLSUN-OS 3.0 kernel (Android boot format) on T1 hardware, after patching only the DTB for the 800×480 display.

---

## 3. Stock Update Package Analysis

### 3.1 Update ZIP Structure

Both T1 and S1 stock updates follow the same structure:

| Directory | Contents | Purpose |
|---|---|---|
| `config/` | `printer.cfg` | Klipper printer configuration |
| `klipper/` | ~20-45 patched `.py` files + `.c` files | **Modified Klipper klippy modules** |
| `mainsail/` | Full Mainsail web UI build | Web interface update |
| `qt/out_linux/` | TUI binary + libraries | Touch UI application |
| `others/` | System files, `zboot.img`, `flsun_kernel_write` | Kernel, firmware, system config |
| `flsun_func/` | Shell scripts | Timelapse, power loss recovery |
| `gcodes/` | Sample `.gcode` files + thumbnails | Demo prints |
| `update.sh` | Main update script (~890 lines) | Orchestrates entire update |
| `recovery.sh` | Factory reset script | Restores to update-version defaults |
| `del.py`, `file_del.sh` | Cleanup scripts | Remove obsolete files |

### 3.2 Update Mechanism (`update.sh`)

The update script performs file-by-file replacement with backup/rollback:

1. **Kernel update:** Calls `flsun_kernel_write` with `zboot.img` from `others/` — writes directly to eMMC boot partition
2. **Klipper patches:** Copies individual `.py` files into `~/klipper/klippy/extras/`, `~/klipper/klippy/kinematics/`, etc. — **NOT a git-based update, overrides files directly**
3. **Config update:** Merges new `printer.cfg` with existing (preserves calibration data like `SAVE_CONFIG` block)
4. **TUI update:** Replaces `~/qt/out_linux/` (Qt touch application)
5. **Mainsail update:** Replaces `~/mainsail/` directory
6. **System files:** Updates `rc.local`, WiFi firmware, udev rules, webcam config
7. **IoT/Cloud:** Includes Aliyun SDK libraries (`libaliyunsdk.so`) for FLSUN cloud service
8. **Hostname:** Sets to `FLSunT1` (or `FLSunS1` for S1)
9. **SSH removal:** `rm -rf /usr/sbin/sshd` — **deliberately removes SSH access** (re-enabled by updates that include `uupdate` flag)

> **Critical security note:** The stock update explicitly removes the SSH daemon binary. FLSUN-OS must ensure SSH remains available.

### 3.3 Patched Klipper Modules

Both T1 and S1 stock firmware ship with **FLSUN-modified Klipper Python modules**. These are NOT standard upstream Klipper — they contain proprietary patches for FLSUN features.

#### T1 Patched Modules (17 files)

| Module | Location | FLSUN Modifications |
|---|---|---|
| `delta.py` | `klippy/kinematics/` | Custom delta calibration |
| `bed_mesh.py` | `klippy/extras/` | Modified bed mesh handling |
| `fan.py` | `klippy/extras/` | Custom fan control |
| `filament_switch_sensor.py` | `klippy/extras/` | Modified filament detection |
| `filament_motion_sensor.py` | `klippy/extras/` | Modified motion sensor |
| `gcode_move.py` | `klippy/extras/` | G-code move modifications |
| `heaters.py` | `klippy/extras/` | Heater control patches |
| `homing.py` | `klippy/extras/` | Modified homing sequence |
| `klippy.py` | `klippy/` | Core klippy patches |
| `mcu.py` | `klippy/` | MCU communication patches |
| `toolhead.py` | `klippy/` | Toolhead motion patches |
| `virtual_sdcard.py` | `klippy/extras/` | SD card handling patches |
| `power_loss_recover.py` | `klippy/extras/` | **T1-specific** PLR module |
| `save_temp_variables.py` | `klippy/extras/` | **T1-specific** temp var store |
| `box_light.py` | `klippy/extras/` | **T1-specific** caselight control |
| `resonance_tester.py` | `klippy/extras/` | Modified shaper testing |
| `shaper_calibrate.py` | `klippy/extras/` | Modified shaper calibration |

#### S1-Only Modules (additional)

| Module | Purpose |
|---|---|
| `probe.py` | Custom probe handling |
| `extruder.py` | Auto pressure advance support |
| `configfile.py` | Config file patches |
| `buttons.py` | Button/GPIO patches |
| `gcode_button.py` | G-code button control |
| `webhooks.py` | Webhooks patches |
| `input_shaper.py` | Input shaper patches |
| `edgepoints.py` | Edge calibration points |
| `flsun_warning.py` | FLSUN warning system |
| `c_helper.so` | Pre-compiled C helper (ARMv7) |
| `rotate_logger.py` | Log rotation |
| `pause_resume.py` | Pause/resume patches |

#### S1-Only Features

| Feature | Contents |
|---|---|
| `AI_detect/` | RKNN models (YOLOv5, v8, v10), segmentation, print failure detection |
| `Structured_light/` | First layer inspection via structured light + camera |
| `qt/fonts/` | Font files (NotoColorEmoji, custom TTF) |
| `3d_print_gui` | Qt5 touch UI binary (S1 version — different from T1's `TUI`) |
| `gcode_calibration.sh` | Automated calibration gcode generation |

### 3.4 T1 vs T1 Pro Update Differences

The T1 and T1 Pro firmware updates are almost **identical**, with these differences:

| Feature | T1 | T1 Pro |
|---|---|---|
| Header comment | `#T1` | `#T1Pro` |
| Part fan `max_power` | **0.8** | **0.6** |
| Part fan `cycle_time` | 0.00005 | 0.0001 |
| M106 soft-start macro | Not present | **Present** (ramp from S60 if starting cold) |
| `zboot.img` | Same (7.9 MB) | Same (7.9 MB) |
| All other pins/settings | Identical | Identical |

The T1 Pro uses a quieter CPAP blower that requires lower max power (0.6) and a soft-start macro to avoid stalling the fan. Everything else — MCU pins, stepper config, TMC5160 SPI, probe, bed, sensors — is identical.

### 3.5 S1 vs S1 Pro Update Differences

| Feature | S1 | S1 Pro |
|---|---|---|
| AI detection | Full RKNN models | Same |
| Structured light | Full | Same |
| `zboot.img` size | **10.67 MB** | Same |
| `config.ini` (TUI) | `product.ini` in S1 Pro, `config.ini` in S1 | Different TUI config |
| Main TUI binary | `3d_print_gui` (7.43 MB) | Same |
| Font files | `bb4171.ttf`, `NotoColorEmoji.ttf` | Same |
| Shutdown animation | `shutani`, `shutanima` | Same |
| `others/um`, `others/umb` | Not present in S1 | Present in S1 Pro |

---

## 4. TMC5160 SPI Pin Mapping — Stock vs T1-pyro Discrepancy

### Discovery

A critical discrepancy was found between the **official FLSUN stock firmware** `printer.cfg` and the **T1-pyro community project** `printer.cfg` for TMC5160 SPI pin assignments:

| Stepper | Step/Dir/Enable | Stock SPI (cs, sclk, miso, mosi) | T1-pyro SPI (cs, sclk, miso, mosi) |
|---|---|---|---|
| stepper_a | PE5/PD7/PE1 | **PD9, PD10, PD8, PD11** | PB4, PE0, PB3, PD5 |
| stepper_b | PB9/PC7/PD3 | **PB4, PE0, PB3, PD5** | PC6, PD0, PA8, PD1 |
| stepper_c | PB8/PE15/PD13 | **PC6, PD0, PA8, PD1** | PD9, PD10, PD8, PD11 |
| extruder | PD15/PB0/PB1 | PC4, PA7, PC5, PA6 | PC4, PA7, PC5, PA6 |

**The three SPI buses are rotated:** Stock's stepper_a SPI = T1-pyro's stepper_c SPI, and so on.

### Impact Assessment

**Low functional impact** in practice because:
- Step/dir/enable pins are **identical** in both configs — motors move correctly
- All three TMC5160 steppers use **identical current settings** (3A run, 1.6A hold)
- All three TMC5160 steppers use **identical driver settings** (stealthchop_threshold=0, interpolate=true)

Since the TMC5160 configs are uniform, the SPI bus rotation only affects which physical driver chip receives the `DUMP_TMC` query. The actual motor behavior is the same regardless.

### Which Mapping Is Correct?

The T1-pyro project by mulcmu was developed on actual hardware with individual verification. The stock firmware may use a different naming convention (tower identification differs). **Both work** because the TMC configs are identical.

**Our ported configs follow T1-pyro's mapping**, which matches the physical verification done by the T1-pyro developer.

---

## 5. Config Issues Found — T1 and T1 Pro (Silent Kit)

### 5.1 Fan Config Mismatch (NEEDS FIX)

The ported `fan-stock.cfg` currently uses T1 **Pro** values, not T1 values:

| Parameter | T1 Stock | T1 Pro Stock | Our `fan-stock.cfg` | Our `fan-silent-kit.cfg` |
|---|---|---|---|---|
| `max_power` | **0.8** | 0.6 | 0.6 (wrong!) | 0.5 |
| `cycle_time` | **0.00005** | 0.0001 | 0.0001 (wrong!) | 0.0001 |
| M106 soft-start | No | **Yes** | No | No |

**Required fix:**
1. `fan-stock.cfg` should have `max_power: 0.8` and `cycle_time: 0.00005` (original T1 values)
2. `fan-silent-kit.cfg` should have `max_power: 0.6` and `cycle_time: 0.0001` (T1 Pro values, matching the quieter CPAP fan)
3. Consider adding M106 soft-start macro to `fan-silent-kit.cfg`

### 5.2 Heatsink Fan Differences

| Feature | T1/T1 Pro Stock | Our Ported Config |
|---|---|---|
| Type | `[heater_fan heat_sink_fan]` (built-in) | `[fan_generic heat_sink_fan]` + display template |
| Control | Simple: on when extruder > 50°C | Hysteresis: on at 50°C, off below 35°C |
| Source | FLSUN stock | T1-pyro community config |

Our ported config uses the **more sophisticated** T1-pyro hysteresis approach (prevents rapid cycling). This is an improvement over stock and should be kept.

### 5.3 Bed Mesh / Delta Calibrate Radius

| Parameter | T1/T1 Pro Stock | T1-pyro | Our Ported |
|---|---|---|---|
| `bed_mesh mesh_radius` | 125 | 100 | 100 |
| `delta_calibrate radius` | 120 | 123.5 | 123.5 |
| `bed_mesh horizontal_move_z` | 7 | 10 | 10 |
| `bed_mesh fade_end` | 2 | 5 | 5 |

The T1-pyro uses a slightly smaller mesh_radius (100 vs 125) likely to avoid probing near bed edges with the load cell. The stock uses a standard probe (PA3 switch) with a wider radius. Our ported config correctly uses the T1-pyro values for load cell probe compatibility.

### 5.4 Stock Features NOT in Ported Config (Expected)

These stock features were intentionally removed in the ported config:
- `[power_loss_recover]` — FLSUN custom Klipper module (not in upstream or garethky fork)
- `[save_temp_variables]` — FLSUN custom module
- `[box_light]` — FLSUN custom module (replaced by `[output_pin caselight]`)
- `x_size_offset` / `y_size_offset` in `[printer]` — FLSUN custom Klipper feature
- `max_accel_to_decel` — deprecated Klipper setting (replaced by `minimum_cruise_ratio`)
- `[probe]` pin=PA3 — replaced by `[load_cell_probe]` (T1-pyro upgrade)

### 5.5 Additional Stock Settings to Consider

| Setting | Stock Value | Our Config | Recommendation |
|---|---|---|---|
| `idle_timeout` | 172800 (48h) | 900 (15min) | Keep ours — 48h is wasteful and unsafe |
| `min_extrude_temp` | Not set (default 170) | 180 | Keep ours — safer |
| `delta_calibrate horizontal_move_z` | 10 | 5 | Our value is lower — may be fine with load cell but could hit the bed |
| Resonance tester `min_freq`/`max_freq` | 30/50 Hz | Not set (full range) | Keep ours — full range is better for initial calibration |

---

## 6. Stock Update Version History

### T1 Updates

| Version | Build # | File |
|---|---|---|
| 1.0.8.7 | 10 | `T1 - Update 1.0.8.7 (10).zip` |
| 1.0.9.0 | 15 | `T1 - Update 1.0.9.0 (15).zip` |
| 1.0.9.2 | 17 | `T1 - Update 1.0.9.2 (17).zip` |
| 1.0.9.2.1 | 18 | `T1 - Update 1.0.9.2.1 (18).zip` |
| **1.0.9.3** | **20** | `T1 - Update 1.0.9.3 (20).zip` |

### T1 Pro Updates

| Version | Build # | File |
|---|---|---|
| 1.0.0.11 | 11 | `T1 Pro - Update 1.0.0.11 (11).zip` |
| 1.0.1.0 | 16 | `T1 Pro - Update 1.0.1.0 (16).zip` |
| 1.0.1.0.2 | 18 | `T1 Pro - Update 1.0.1.0.2 (18).zip` |
| **1.0.1.1** | **20** | `T1 Pro - Update 1.0.1.1 (20).zip` |

### S1 Updates

| Version | Build # | File |
|---|---|---|
| 1.0.7.1 | 55 | `S1 - Update 1.0.7.1 (55).zip` |
| 1.0.7.4 | 68 | `S1 - Update 1.0.7.4 (68).zip` |
| 1.0.7.5 | 69 | `S1 - Update 1.0.7.5 (69).zip` |
| 1.0.8.0 | 75 | `S1 - Update 1.0.8.0 (75).zip` |
| 1.0.8.1 | 76 | `S1 - Update 1.0.8.1 (76).zip` |
| 1.0.8.1.1 | 80 | `S1 - Update 1.0.8.1.1 (80).zip` |
| **1.0.8.2** | **85** | `S1 - Update 1.0.8.2 (85).zip` |

### S1 Pro Updates

| Version | Build # | File |
|---|---|---|
| 1.0.0.11 | 68 | `S1 Pro - Update 1.0.0.11 (68).zip` |
| 1.0.0.12 | 69 | `S1 Pro - Update 1.0.0.12 (69).zip` |
| 1.0.0.13 | 70 | `S1 Pro - Update 1.0.0.13 (70).zip` |
| 1.0.1.0 | 76 | `S1 Pro - Update 1.0.1.0 (76).zip` |
| 1.0.1.0.2 | 80 | `S1 Pro - Update 1.0.1.0.2 (80).zip` |
| **1.0.1.1** | **85** | `S1 Pro - Update 1.0.1.1 (85).zip` |

> **Pattern:** T1 and T1 Pro share the same build number (20), and S1 and S1 Pro share the same build number (85). The "Pro" versioning scheme starts at 1.0.0.x while the base model uses the main version series.

---

## 7. Open Questions

- [ ] **RKDevTool partition addresses:** Need the exact eMMC sector addresses for the T1 boot (p3) and rootfs (p6) partitions. These can be obtained by reading the GPT table from the full-disk dump (`1097_0.img`) or from a live T1 via `fdisk -l`.
- [ ] **`flsun_kernel_write` internals:** This is a ~30 KB ARM binary. It likely just does `dd if=zboot.img of=/dev/mmcblkXpY` but the exact partition it targets needs confirmation. Reverse engineering or running `strace ./flsun_kernel_write` on a T1 would reveal this.
- [ ] **U-Boot boot format preference:** The T1 U-Boot successfully boots both FIT and Android boot images, but which does it try first? The bootcmd needs to be dumped from a serial console.
- [ ] **Partition addresses for FLSUN-OS `package-emmc-t1.sh`:** The eMMC packaging script needs the correct addresses to align with the T1's partition table.
