# T1 Stock Firmware Analysis

**Date researched:** 2025-05-29  
**Source:** `resources/T1/firmwares/stock/` — 9 gzip-compressed eMMC partition dumps

---

## Overview

This document covers the extraction, reverse engineering, and detailed analysis of the **FLSUN T1 stock firmware**, obtained as gzip-compressed per-partition eMMC dumps. The firmware contains a complete Linux system built around the **Rockchip RV1109** SoC running **Linux 4.19.111** on **Debian 10 Buster**.

> **SoC naming note:** The physical chip on the T1 PCB is **RV1109** (dual-core Cortex-A7, 1.2 TOPS NPU). However, the device tree uses `rv1126` compatible strings (e.g. `rockchip,rv1126-evb-ddr3-v13-flsun-800p`) because Rockchip treats RV1109 and RV1126 as the **same platform** — they share the same die, defconfig, kernel source, and driver bindings. The only differences are disabled CPU cores and reduced NPU performance on the RV1109. All `rv1126` references in the DTB are Rockchip platform identifiers, not the actual chip SKU.

Key findings:

| Aspect | T1 Stock | S1 Open Source Edition |
|---|---|---|
| Kernel | 4.19.111 | 6.1.99 |
| Kernel branch | Rockchip BSP 4.19 (legacy) | Rockchip BSP 6.1 (develop-6.1) |
| Boot format | **U-Boot FIT image** | Android boot image (mkbootimg) |
| DTB location | Embedded in FIT + RSCE resource | RSCE resource container |
| Display interface | RGB parallel | RGB parallel |
| Panel resolution | **800×480** | 1024×600 |
| Pixel clock | 25 MHz | 51.2 MHz |
| OS base | Debian 10 Buster | Debian 13 Trixie |
| Python | 3.7 | 3.13+ |
| Compiler | Linaro GCC 6.3.1 (2017) | GCC 11.4.0 |
| SoC compatible | `rockchip,flsun-800p` | `rockchip,rv1126` |
| DTB model | `RV1126 EVB DDR3 V13 Board flsun-800p` | `Rockchip RV1126 EVB DDR3 V13 Board` |

---

## Partition Layout

The firmware consists of 9 gzip-compressed files representing separate eMMC regions:

| File | Partition | Compressed | Decompressed | Format | Contents |
|---|---|---|---|---|---|
| `1097_0boot0.img` | eMMC boot0 | 4 KB | 4 MB | zeros | Empty |
| `1097_0boot1.img` | eMMC boot1 | 4 KB | 4 MB | zeros | Empty |
| `1097_0p1.img` | uboot | 1.17 MB | 4 MB | U-Boot FIT | U-Boot + OP-TEE + DTB |
| `1097_0p2.img` | misc | 4 KB | 4 MB | zeros | Empty (recovery trigger flag) |
| `1097_0p3.img` | boot | 6.12 MB | 32 MB | U-Boot FIT | Kernel + DTB + RSCE resources |
| `1097_0p4.img` | recovery | 12.61 MB | 32 MB | U-Boot FIT | Kernel + DTB + ramdisk + resources |
| `1097_0p5.img` | backup | 0.03 MB | 32 MB | zeros | Empty |
| `1097_0p6.img` | rootfs | 1313.7 MB | ~7.17 GB | ext4 | Linux root filesystem |
| `1097_0.img` | full-disk | 1333.3 MB | ~8 GB | GPT | Complete eMMC image |

> **Note:** The partition layout follows the standard Rockchip eMMC layout, identical in structure to the S1 (see [S1 Research 09](../../S1/research/09-image-reverse-engineering.md)), but the boot format is fundamentally different.

---

## Boot Format: U-Boot FIT Image

Unlike the S1 which uses Android boot image format (mkbootimg with `ANDROID!` magic), the T1 uses **U-Boot FIT (Flattened Image Tree)** format. FIT images use the device tree (FDT) structure to package multiple components together.

### Boot Partition (p3) FIT Structure

```
FIT Image (32 MB, D00DFEED magic)
├── /images/
│   ├── kernel     — 7,216,152 bytes (6.88 MB), ARM zImage, LZ4-compressed payload
│   ├── fdt        — 92,572 bytes, flat_dt (the main device tree blob)
│   └── resource   — 973,312 bytes, RSCE container (Rockchip resource image)
├── /configurations/
│   └── conf       — signed configuration (boot verification)
└── /conf/signature — signature data for secure boot
```

### U-Boot Partition (p1) FIT Structure

```
FIT Image (4 MB)
├── /images/
│   ├── uboot      — "U-Boot (32-bit)", gzip compressed
│   ├── optee      — "OP-TEE", gzip compressed  
│   └── fdt        — U-Boot device tree blob
└── /configurations/
    └── conf       — "rv1126-evb" configuration
```

### Recovery Partition (p4) FIT Structure

```
FIT Image (32 MB)
├── /images/
│   ├── kernel     — 7,075,280 bytes (6.75 MB)
│   ├── fdt        — 92,393 bytes
│   ├── ramdisk    — 6,973,695 bytes (6.65 MB)
│   └── resource   — 973,312 bytes (RSCE)
└── /configurations/
    └── conf       — signed configuration
```

### RSCE Resource Container

The RSCE (Rockchip Resource Container) within the boot partition contains:

| Entry | Description |
|---|---|
| `rk-kernel.dtb` | Base device tree blob |
| `rv1126-flsun-800p#_saradc_ch4=500.dtb` | Board-specific DTB overlay (800p panel variant) |
| `logo.bmp` | Boot splash logo |
| `logo_kernel.bmp` | Kernel boot logo |

> **Board variant selection:** The `#_saradc_ch4=500` suffix indicates U-Boot reads SARADC channel 4 at boot. When the ADC value equals ~500, this DTB is selected. This is a standard Rockchip mechanism for hardware revision detection.

---

## Kernel Analysis

### Version and Build Info

```
Linux version 4.19.111 (linux-dzh@ubuntu) (gcc version 6.3.1 20170404 (Linaro GCC 6.3-2017.05)) #22 SMP PREEMPT Sun Sep 29 02:43:49 PDT 2024
```

| Field | Value |
|---|---|
| Version | **4.19.111** |
| Builder | `linux-dzh@ubuntu` |
| Compiler | Linaro GCC 6.3.1 (2017.05) |
| Build # | 22 |
| Config | SMP PREEMPT |
| Build date | September 29, 2024 |
| Source branch | Rockchip BSP `linux-4.19` (legacy) |
| Format | ARM zImage with LZ4-compressed payload |
| Compressed size | 7,216,152 bytes (6.88 MB) |
| Decompressed size | 15,066,436 bytes (14.4 MB) |

### Kernel Branch Comparison

| Feature | T1 (4.19.111) | S1 (6.1.99) |
|---|---|---|
| DRM/Rockchip VOP | Legacy VOP driver | Updated VOP driver |
| Display pipeline | DRM + VOP + RGB | DRM + VOP + RGB |
| Device model | Monolithic (no modules expected) | Monolithic (zero `=m`) |
| NPU driver | `galcore.ko` (expected) | `galcore.ko` |
| Cross compiler | Linaro GCC 6.3.1 | GCC 11.4.0 |

> **Implication:** The T1 runs a **significantly older kernel**. For a custom OS, upgrading to the 6.1 branch (as used by the S1 Open Source Edition) would provide better security, newer DRM drivers, and modern toolchain compatibility. The 4.19 kernel uses the older Rockchip BSP codebase.

---

## Device Tree Analysis

### Board Identity

```dts
/ {
    model = "Rockchip RV1126 EVB DDR3 V13 Board flsun-800p";
    compatible = "rockchip,rv1126-evb-ddr3-v13-flsun-800p", "rockchip,flsun-800p";
};
```

The DTB confirms:
- **SoC**: RV1109 on PCB (DTB uses `rv1126` platform identifier — same die, shared kernel/driver source)
- **Board**: EVB DDR3 V13 (Rockchip evaluation board design)
- **Variant**: `flsun-800p` (FLSUN custom for 800×480 panel)

### Display Configuration

The T1 display pipeline is: **VOP → RGB → Panel**

#### Panel Node

```dts
panel@0 {
    compatible = "simple-panel";
    bus-format = <0x1013>;          /* MEDIA_BUS_FMT_RGB888_1X24 */
    backlight = <&backlight>;
    enable-gpios = <&gpio3 28 GPIO_ACTIVE_LOW>;
    enable-delay-ms = <20>;
    rgb-mode = "p888";              /* 24-bit parallel RGB */
    width-mm = <95>;                /* Physical: 95mm × 54mm */
    height-mm = <54>;
    status = "okay";

    display-timings {
        timing0 {
            clock-frequency = <25000000>;   /* 25 MHz */
            hactive = <800>;
            vactive = <480>;
            hback-porch = <8>;
            hfront-porch = <8>;
            vback-porch = <8>;
            vfront-porch = <8>;
            hsync-len = <4>;
            vsync-len = <4>;
            hsync-active = <1>;
            vsync-active = <1>;
            de-active = <1>;
            pixelclk-active = <1>;
        };
    };
};
```

#### S1 vs T1 Panel Comparison

| Parameter | T1 Stock | S1 (FLSUN OS) |
|---|---|---|
| Resolution | **800×480** | 1024×600 |
| Physical size | 95×54 mm (~3.5") | 150×94 mm (~7") |
| Interface | RGB parallel (P888) | RGB parallel (P888) |
| Pixel clock | 25 MHz | 51.2 MHz (0x030D4000) |
| Bus format | 0x1013 (RGB888_1X24) | 0x100E (RGB666_1X18) |
| H back porch | 8 | 160 |
| H front porch | 8 | 160 |
| V back porch | 8 | 23 |
| V front porch | 8 | 12 |
| H sync length | 4 | 20 |
| V sync length | 4 | 3 |
| Enable GPIO | GPIO3_D4 (active low) | None (pinctrl only) |
| Backlight | PWM-backlight, 256 levels | PWM-backlight |

#### Display Pipeline Routing

```dts
display-subsystem {
    compatible = "rockchip,display-subsystem";
    status = "okay";
    route {
        route-dsi { status = "disabled"; };   /* MIPI DSI NOT used */
        route-rgb { status = "okay"; };       /* RGB parallel ACTIVE */
    };
};

vop@ffb00000 {
    compatible = "rockchip,rv1126-vop";
    status = "okay";
    /* endpoint@0 → RGB interface */
    /* endpoint@1 → DSI interface (disabled) */
};

rgb {
    compatible = "rockchip,rv1126-rgb";
    status = "okay";
    /* port@0 → VOP input */
    /* port@1 → Panel output */
};

dsi@ffb30000 {
    compatible = "rockchip,rv1126-mipi-dsi";
    status = "disabled";    /* DSI present in silicon but NOT used */
};
```

> **Critical finding:** Both S1 and T1 use **RGB parallel interface** for their displays. The community speculation that the T1 might use MIPI DSI (based on display incompatibility) is **incorrect**. The panels differ in resolution (800×480 vs 1024×600), physical size, and bus format (RGB888 vs RGB666), but use the same interface type. DSI hardware exists in the RV1109/RV1126 silicon but is explicitly disabled in the T1 DTB.

#### Backlight

```dts
backlight {
    compatible = "pwm-backlight";
    pwms = <&pwm0 0 25000 0>;      /* PWM0, period 25µs (40 kHz) */
    brightness-levels = <0 1 2 ... 254 255>;  /* 256 levels (0-255) */
    default-brightness-level = <100>;
};
```

The backlight uses PWM channel 0 (`pwm@ff430000`) at 40 kHz with 256 brightness levels.

---

## Rootfs Analysis (Partial)

The rootfs partition was only partially analyzed (first 64 MB of 7.17 GB decompressed) without full extraction.

### Filesystem Metadata

| Field | Value |
|---|---|
| Filesystem | ext4 |
| Total size | 7.17 GB (1,880,056 blocks × 4096 bytes) |
| Inodes | 474,208 |
| Volume label | `linuxroot` |
| UUID | `eeebcd0a-2b00-4f29-94dc-8cee4eedc976` |
| Created | 2019-02-14 (mkfs timestamp) |
| OS | Linux |

### Software Components Detected

From string scanning of the first 64 MB:

| Component | Evidence |
|---|---|
| **Python 3.7** | `python3.7m` binary found |
| **Klipper** | `klipper/` directory reference |
| **Moonraker** | `moonraker-env`, `printer_data` |
| **Mainsail** | `mainsail-access.log` |

> **Note:** The stock T1 runs **Mainsail** as its web interface, not Fluidd. It uses Python 3.7 (Debian 10 default), which is EOL and causes SSL/pip compatibility issues documented in [T1 Research 02](02-firmware-and-community.md).

---

## Extracted Files Inventory

All extracted files are in `resources/T1/firmwares/stock/extracted/`:

| File | Size | Description |
|---|---|---|
| `fdt.dtb` | 92,572 bytes | Main device tree blob (800p variant) |
| `fdt.dts` | ~170 KB | Decompiled device tree source (4326 lines, 484 nodes) |
| `kernel.bin` | 7,216,152 bytes | ARM zImage (LZ4-compressed) |
| `vmlinux-decompressed.bin` | 15,066,436 bytes | Decompressed kernel binary |
| `resource-dtb-0.dtb` | 92,934 bytes | RSCE DTB 0: base `rv1126-flsun` variant |
| `resource-dtb-1.dtb` | 92,934 bytes | RSCE DTB 1: base `rv1126-flsun` variant |
| `emmc-boot0.img` | 4 MB | eMMC boot0 (zeros) |
| `emmc-boot1.img` | 4 MB | eMMC boot1 (zeros) |
| `p1-uboot.img` | 4 MB | U-Boot partition |
| `p2-misc.img` | 4 MB | Misc partition (zeros) |
| `p3-boot.img` | 32 MB | Boot partition (FIT image) |
| `p4-recovery.img` | 32 MB | Recovery partition (FIT image) |
| `p5-backup.img` | 32 MB | Backup partition (zeros) |

> **Not extracted:** `1097_0p6.img` (rootfs, 1314 MB compressed → 7.17 GB) and `1097_0.img` (full disk, 1333 MB compressed) were skipped due to size.

---

## RSCE Resource DTB Variants

The resource container includes two DTB variants:

| DTB | Model | Compatible |
|---|---|---|
| `rk-kernel.dtb` (via FIT) | `RV1126 EVB DDR3 V13 Board flsun-800p` | `rockchip,rv1126-evb-ddr3-v13-flsun-800p, rockchip,flsun-800p` |
| Resource DTB 0 & 1 | `RV1126 EVB DDR3 V13 Board flsun` | `rockchip,rv1126-evb-ddr3-v13, rockchip,rv1126-flsun` |

The "flsun-800p" variant (selected via SARADC ch4=500) is the active DTB. The base "flsun" variants likely target a different display or hardware revision.

---

## Implications for Custom OS Development

### Display Compatibility

Since both S1 and T1 use RGB parallel interface with `simple-panel` driver:
1. The **kernel display driver stack is identical** — both use DRM → VOP → RGB → simple-panel
2. Only the **DTB display-timings node** needs to change for panel compatibility
3. A custom T1 OS needs a DTB with `hactive=800, vactive=480, clock=25MHz` instead of the S1's 1024×600

### Kernel Upgrade Path

The T1 (RV1109) currently runs kernel 4.19.111. To use the S1's kernel 6.1.99:
1. Use the same `rv1126_defconfig` (RV1109 and RV1126 share defconfig and kernel source)
2. Create a new DTB based on the T1's extracted `rv1126-flsun-800p` device tree (800×480 panel timings)
3. Adapt the boot partition from Android boot image format (S1) or FIT format (T1 stock)
4. The display, GPIO, pinctrl, and peripheral configuration from the extracted T1 DTB provides the complete reference
5. Use RV1109-specific rkbin files (DDR init, SPL) — these are NOT shared with RV1126

### Boot Format Decision

| Option | Format | Tool | Pros | Cons |
|---|---|---|---|---|
| Keep T1 format | FIT | mkimage | Native U-Boot support, secure boot | Different from S1, requires U-Boot config changes |
| Use S1 format | Android boot | mkbootimg | Compatible with S1 build system | May need U-Boot reconfiguration |

The choice depends on the T1 U-Boot's bootcmd — it may be hardcoded to load FIT images. The stock U-Boot should be analyzed further to determine which format it expects.

### What's Missing

- [ ] Full rootfs extraction and analysis (Klipper/Moonraker/Mainsail versions, service configuration)
- [ ] U-Boot environment variables (`env print` from serial console)
- [ ] U-Boot bootcmd to determine exact boot sequence
- [ ] Kernel `.config` extraction (not embedded in zImage; need rootfs `/proc/config.gz` or build system)
- [ ] MCU firmware analysis (GD32F303 / STM32F103-compatible, separate from SoC)
- [ ] NPU (galcore) kernel module version
- [ ] Screen driver IC identification (likely identifiable from the panel enable sequence or from hardware inspection)

---

## Analysis Scripts

The following Python scripts were created during analysis (in `resources/T1/firmwares/stock/`):

| Script | Purpose |
|---|---|
| `analyze_boot.py` | Initial boot partition format identification |
| `parse_fit.py` | FIT image parser — extracts kernel, DTB, resources |
| `extract_kernel.py` | DTB decompilation and resource DTB analysis |
| `find_version.py` | Compression signature search and resource DTB comparison |
| `decompress_kernel.py` | LZ4 kernel decompression and version string extraction |
| `analyze_recovery.py` | Recovery partition analysis, rootfs metadata scan |
