# FLSUN OS 3.0 — Kernel, Device Tree & Package Analysis

**Date researched:** 2025-02-28  
**Source:** FLSUN-OS-S1-EMMC-3.0.7z (v3.0), boot.img → zImage + rk-kernel.dtb; rootfs.img → dpkg/status  
**Method:** Python-based binary analysis (no dtc or external tooling)

---

## 1. Kernel Version & Build Information

### Version String

```
Linux version 6.1.99flsun OS (root@FLSUN-OS)
  (arm-linux-gnueabihf-gcc (Ubuntu 11.4.0-1ubuntu1~22.04) 11.4.0,
   GNU ld (GNU Binutils for Ubuntu) 2.38)
  #38 SMP PREEMPT Mon Mar 31 20:03:38 CEST 2025
```

### Key Facts

| Property | Value |
|---|---|
| Kernel version | 6.1.99 |
| Local version | `flsun OS` (no `CONFIG_LOCALVERSION`; patched into version string directly) |
| Build number | #38 |
| Preemption | Full PREEMPT (real-time capable) |
| SMP | Yes (4 cores) |
| Build date | Mon Mar 31 20:03:38 CEST 2025 |
| Build host | `root@FLSUN-OS` |
| Cross-compiler | arm-linux-gnueabihf-gcc 11.4.0 (Ubuntu 22.04) |
| Linker | GNU ld 2.38 |
| Architecture | ARMv7 (Cortex-A7) |
| zImage compressed size | 8,531,192 bytes (8.14 MB) |
| Decompressed kernel size | 20,654,540 bytes (19.70 MB) |
| Compression | gzip (stream at offset 0x6F60) |

### Kernel Source Lineage

The kernel is based on **Linux 6.1.99**, which is an LTS (Long Term Support) release from the 6.1.x series. The `.99` suffix indicates many stable patches beyond the initial 6.1 release. The `flsun OS` suffix in the version string suggests Guilouz modified the kernel version directly (not via `CONFIG_LOCALVERSION`, which is empty in the config).

The kernel includes the **Rockchip BSP (Board Support Package)** kernel tree patches — evidenced by:
- Massive Rockchip-specific subsystems (ISP, NPU, VPU, DRM, CAN, PVTM, DMC, etc.)
- `CONFIG_ROCKCHIP_MINI_KERNEL=y` (Rockchip's optimized minimal kernel config)
- Rockchip-specific driver strings: `rockchip_wlan/rkwifi/bcmdhd compiled on Mar 31 2025 at 20:01:49`
- Clock/power domain support: `rv1126_pmu_clk_init`, `rv1126_clk_init`

This is the **Rockchip downstream kernel** (not mainline Linux), heavily patched with Rockchip's proprietary ISP/NPU/VPU/multimedia stack.

---

## 2. Kernel Configuration (IKCONFIG)

The kernel has **embedded IKCONFIG** — the full `.config` is compiled into the kernel binary itself (accessible at runtime via `/proc/config.gz`).

**Config statistics:**
| Metric | Count |
|---|---|
| Built-in (=y) | 1,277 |
| Module (=m) | **0** |
| Disabled (not set) | 3,525 |
| Total config lines | 6,529 |

> **Critical finding:** This is a **fully monolithic kernel** — zero loadable modules. Every driver is compiled directly into the kernel. This means the system cannot `modprobe` or `insmod` anything at runtime. All hw support must be built in at compile time.

### Scheduler & Real-Time

```
CONFIG_PREEMPT=y              # Full preemption (lowest latency)
CONFIG_HZ=300                 # Timer tick at 300 Hz
CONFIG_NO_HZ_IDLE=y           # Tickless idle
CONFIG_HIGH_RES_TIMERS=y      # High-resolution timers
CONFIG_SCHED_MC=y             # Multi-core scheduling
CONFIG_SCHED_SMT=y            # SMT-aware scheduling
CONFIG_SCHED_HRTICK=y         # HR tick for scheduler
```

Full `PREEMPT` at 300 Hz with high-res timers — designed for low-latency real-time operation (critical for 3D printer motion control via Klipper).

### CAN Bus (Comprehensive)

```
CONFIG_CAN=y
CONFIG_CAN_RAW=y
CONFIG_CAN_BCM=y
CONFIG_CAN_GW=y
CONFIG_CAN_J1939=y
CONFIG_CAN_ISOTP=y
CONFIG_CAN_DEV=y
CONFIG_CAN_VCAN=y
CONFIG_CAN_VXCAN=y
CONFIG_CAN_NETLINK=y
CONFIG_CAN_CALC_BITTIMING=y
CONFIG_CAN_ROCKCHIP=y         # Rockchip native CAN
CONFIG_CANFD_ROCKCHIP=y       # Rockchip CAN-FD
CONFIG_CAN_GS_USB=y           # USB-CAN adapters (Geschwister Schneider)
CONFIG_CAN_SLCAN=y            # Serial line CAN
CONFIG_CAN_C_CAN=y
CONFIG_CAN_CC770=y
CONFIG_CAN_FLEXCAN=y
CONFIG_CAN_IFI_CANFD=y
CONFIG_CAN_M_CAN=y
CONFIG_CAN_SJA1000=y
CONFIG_CAN_8DEV_USB=y
CONFIG_CAN_EMS_USB=y
CONFIG_CAN_ESD_USB=y
CONFIG_CAN_KVASER_USB=y
CONFIG_CAN_PEAK_USB=y
```

Extremely comprehensive CAN bus support. The S1 uses CAN bus for communication between the main board and closed-loop stepper motor drivers. Both Rockchip native CAN and CAN-FD are enabled, plus nearly every USB-CAN adapter driver.

### Networking

```
CONFIG_NET=y
CONFIG_INET=y
CONFIG_IPV6=y
CONFIG_NETFILTER=y
CONFIG_BRIDGE=y
CONFIG_BT=y                   # Bluetooth
CONFIG_WIRELESS=y
CONFIG_CFG80211=y             # WiFi cfg80211
CONFIG_MAC80211=y             # WiFi mac80211
```

WiFi driver: Broadcom bcmdhd (compiled as built-in, not module): `rockchip_wlan/rkwifi/bcmdhd compiled on Mar 31 2025 at 20:01:49`

### Display / Graphics

```
CONFIG_DRM_ROCKCHIP=y
CONFIG_ROCKCHIP_VOP=y         # Video Output Processor
CONFIG_ROCKCHIP_DW_MIPI_DSI=y # MIPI DSI (disabled in DTB)
CONFIG_ROCKCHIP_DW_MIPI_DSI2=y
CONFIG_ROCKCHIP_LVDS=y
CONFIG_ROCKCHIP_RGB=y         # RGB parallel interface (USED by panel)
CONFIG_ROCKCHIP_RGA=y         # 2D graphics accelerator
CONFIG_ROCKCHIP_RGA2=y
```

### Multimedia / Camera / AI

```
CONFIG_VIDEO_ROCKCHIP_CIF=y   # Camera Input
CONFIG_VIDEO_ROCKCHIP_ISP=y   # Image Signal Processor
CONFIG_VIDEO_ROCKCHIP_ISP_VERSION_V20=y
CONFIG_VIDEO_ROCKCHIP_ISPP=y  # ISP Post-Processor
CONFIG_ROCKCHIP_MPP_SERVICE=y # Media Process Platform
CONFIG_ROCKCHIP_MPP_RKVDEC=y  # Video Decoder
CONFIG_ROCKCHIP_MPP_RKVENC=y  # Video Encoder
CONFIG_ROCKCHIP_MPP_VDPU2=y
CONFIG_ROCKCHIP_MPP_VEPU2=y
CONFIG_ROCKCHIP_MPP_IEP2=y   # Image Enhancement
```

The camera and NPU subsystems are fully enabled — used for the S1's built-in camera and potentially AI-assisted features.

### USB

```
CONFIG_USB_DWC3=y             # DesignWare USB3 controller
CONFIG_USB_DWC3_HOST=y        # Host mode
CONFIG_USB_DWC3_ROCKCHIP_INNO=y
CONFIG_USB_GADGET=y           # USB Device/Gadget mode
CONFIG_USB_CONFIGFS=y
CONFIG_USB_CONFIGFS_RNDIS=y   # USB Ethernet gadget
CONFIG_USB_CONFIGFS_MASS_STORAGE=y
CONFIG_USB_CONFIGFS_F_UVC=y   # USB Video Class gadget
```

USB gadget mode is enabled with RNDIS (USB Ethernet), mass storage, and UVC (USB webcam) support.

### Filesystems

```
CONFIG_EXT4_FS=y              # Root filesystem
CONFIG_VFAT_FS=y              # SD card / USB drives
CONFIG_FAT_FS=y
CONFIG_FUSE_FS=y              # Userspace filesystems
CONFIG_OVERLAY_FS=y           # Overlay (for read-only base + writable overlay)
CONFIG_SQUASHFS=y             # Compressed read-only FS
CONFIG_TMPFS=y
CONFIG_PROC_FS=y
```

### Security

```
CONFIG_LSM="landlock,lockdown,yama,loadpin,safesetid,integrity,bpf"
```

Standard Linux Security Module stack without SELinux or AppArmor.

---

## 3. Device Tree (rk-kernel.dtb)

### Overview

| Property | Value |
|---|---|
| File size | 122,478 bytes |
| FDT version | 17 (compat 16) |
| Model | `Rockchip RV1126 EVB DDR3 V2.3 FLSUN-OS mmc` |
| Compatible | `rockchip,rv1126-evb-ddr3-v13`, `rockchip,rv1126`, `rockchip,rv1126-flsun` |
| Decompiled DTS | 5,657 lines |

### Boot Arguments

```
earlycon=uart8250,mmio32,0xff570000
console=ttyFIQ0
root=PARTUUID=614e0000-0000
rootfstype=ext4
rootwait
snd_aloop.index=7
```

Root is identified by partition UUID (`614e0000-0000`), filesystem is ext4. Early console on UART at `0xff570000`. The `snd_aloop` parameter sets up an ALSA loopback device (index 7).

### CPU & Memory

- **4× ARM Cortex-A7** cores (cpu@f00 through cpu@f03)
- PSCI power management (enable-method = "psci")
- CPU idle states supported (arm,idle-state with 120µs entry / 250µs exit latency)

**CPU Frequency Table (OPP):**

| Frequency | Voltage (typical) | Notes |
|---|---|---|
| 408 MHz | 725 mV | Minimum |
| 600 MHz | 725 mV | |
| 816 MHz | 725 mV | Suspend frequency |
| 1008 MHz | 775 mV | |
| 1200 MHz | 850 mV | |
| 1296 MHz | 875 mV | |
| 1416 MHz | 925 mV | |
| 1512 MHz | 975 mV | Maximum |

*Max frequency is 1.512 GHz (datasheet spec is 1.51 GHz). Voltage scaling uses PVTM (Process-Voltage-Temperature Monitor) with 5 leakage bins.*

**CMA (Contiguous Memory Allocator):** 8 MB (`size = <0x00800000>`)

### PMIC (Power Management IC)

**RK809** on I2C bus 0 (address 0x20):
- System power controller with wakeup capability
- Voltage rails:
  - DCDC1: `vdd_npu_vepu` (0.65–0.95V) — NPU/VPU power
  - DCDC2: `vdd_arm` (0.725–0.975V) — CPU core voltage
  - DCDC3: `vcc_ddr` — DDR memory power
  - DCDC4: `vcc3v3_sys` (3.3V) — System 3.3V
  - DCDC5: `vcc_buck5` (1.4V)
  - LDO1: `vcc_0v8` (0.8V)
  - LDO2: `vcc1v8_pmu` (1.8V)
  - LDO4: `vcc_1v8` (1.8V)
  - LDO6: `vcc_dvdd` (1.2V) — Camera digital
  - LDO7: `vcc_avdd` (2.8V) — Camera analog
  - LDO8: `vccio_sd` (1.8–3.3V) — SD card I/O
  - LDO9: `vcc3v3_sd` (3.3V) — SD card power
  - SWITCH1: `vcc5v0_host` — USB host 5V
  - SWITCH2: `vcc_3v3` — General 3.3V

### Display

The S1 uses an **RGB parallel interface** (not MIPI DSI — DSI is disabled in the DTB):

```
panel@0 {
    compatible = "simple-panel";
    bus-format = <0x100e>;          /* RGB888 */
    rgb-mode = "p888";
    width-mm = 150;                 /* 150mm physical width */
    height-mm = 94;                 /* 94mm physical height */
    connector-type = "HDMI";        /* Reported as HDMI type */
    
    display-timings:
        clock-frequency = 51.2 MHz (0x30d4000)
        hactive = 1024
        vactive = 600
        hback-porch = 160
        hfront-porch = 160
        vback-porch = 23
        vfront-porch = 12
        hsync-len = 20
        vsync-len = 3
};
```

**Panel specifications:**
- Resolution: **1024 × 600** (WSVGA)
- Physical size: 150 × 94 mm (~7 inch diagonal)
- Pixel format: RGB888 (24-bit)
- Interface: RGB parallel (not MIPI DSI)
- Pixel clock: 51.2 MHz
- Backlight: PWM-controlled (`pwm-backlight`)

### Enabled Peripherals

| Peripheral | Address | Status | Notes |
|---|---|---|---|
| I2C0 (PMU) | 0xff3f0000 | **okay** | RK809 PMIC at addr 0x20 |
| I2C1 | 0xff400000 | **okay** | General purpose |
| I2C2–I2C5 | 0xff510000–0xff540000 | disabled | |
| SPI0 | 0xff450000 | **okay** | |
| SPI2 | 0xffc90000 | **okay** | |
| SPI1 | 0xff5b0000 | disabled | |
| UART2 | 0xff560000 | **okay** | |
| UART3 | 0xff590000 | **okay** | |
| UART0–1, 4–5 | various | disabled | |
| CAN | 0xff610000 | **disabled** | CAN driver built-in but bus disabled in DTB |
| USB OTG (DWC3) | 0xffd00000 | **okay** | USB 3.0 OTG controller |
| USB EHCI | 0xffe00000 | **okay** | USB 2.0 Host |
| USB OHCI | 0xffe10000 | **okay** | USB 1.1 Host |
| PWM0 | 0xff430000 | **okay** | Backlight control |
| PWM1-11 | various | disabled | |
| eMMC (SDMMC0) | 0xffc50000 | **okay** | eMMC storage |
| SD (SDMMC1) | 0xffc60000 | **okay** | SD card |
| SDIO (SDMMC2) | 0xffc70000 | **okay** | WiFi module |
| VOP | 0xffb00000 | **okay** | Video Output Processor (display) |
| RGB | (in GRF) | **okay** | Panel interface |
| DSI | 0xffb30000 | **disabled** | MIPI DSI (not used) |
| ISP | 0xffb50000 | **okay** | Camera Image Signal Processor |
| ISPP | 0xffb60000 | **okay** | ISP Post-Processor |
| RGA | 0xffaf0000 | **okay** | 2D Graphics Acceleration |
| NPU | 0xffbc0000 | **okay** | Neural Processing Unit |
| RKVDEC | 0xffb80000 | **okay** | Video Decoder |
| RKVENC | 0xffbb0000 | **okay** | Video Encoder |
| VPU (VEPU/VDPU) | 0xffb90000 | **okay** | Video Processing Unit |
| IEP | 0xffb20000 | **okay** | Image Enhancement |
| RKCIF | 0xffae0000 | **okay** | Camera Interface |
| Ethernet | 0xffc40000 | **disabled** | GMAC (not used) |
| Bluetooth | - | **okay** | Wireless BT |
| WiFi (WLAN) | - | **okay** | Wireless LAN (bcmdhd) |
| LED (white1) | - | **okay** | Status LED |
| SARADC | 0xff5e0000 | **okay** | ADC |
| TSADC × 2 | 0xff5f0000/8000 | **okay** | Temperature sensors |
| OTP | 0xff5c0000 | **okay** | One-Time Programmable fuses |
| RNG | 0xff500400 | **okay** | Hardware random number generator |

### Notable Disabled Peripherals

- **CAN bus:** Hardware present but disabled in DTB (`status = "disabled"`). The kernel has full CAN support built in — this could be enabled by modifying the DTB.
- **MIPI DSI:** Disabled — the S1 uses RGB parallel panel interface instead.
- **Ethernet:** GMAC disabled — networking is WiFi-only.
- **All camera interfaces** (CSI, MIPI-CSI2): Disabled despite ISP being enabled. The camera likely connects through a different path.
- **Audio subsystems:** I2S, PDM, audio PWM, codec — all disabled.
- **DMC (Dynamic Memory Controller):** Disabled — no runtime DRAM frequency scaling.
- **Watchdog:** Disabled.

---

## 4. Installed Debian Packages

**Total:** 1,032 packages installed on the rootfs.

See [10-installed-packages.md](10-installed-packages.md) for the full categorized list.

### Summary by Category

| Category | Count |
|---|---|
| Libraries (C/C++) | 380 |
| Development | 191 |
| Display / X11 / Graphics | 113 |
| Other | 109 |
| Python | 62 |
| Media / Imaging | 49 |
| System Utilities | 39 |
| Networking | 23 |
| Security / Auth | 21 |
| Build Tools & Compilers | 17 |
| Cross-Compilation (ARM/AVR) | 13 |
| Fonts | 11 |
| Base System | 2 |
| Web Server | 2 |

### Notable Package Highlights

**Build Environment (on-device compilation):**
- GCC 14 with cross-compilation support (arm-linux-gnueabihf, arm-none-eabi)
- CMake, Make, pkg-config, autoconf, automake
- AVR toolchain (avr-libc, avrdude, gcc-avr, binutils-avr) — for flashing MCU firmware
- DFU-util — USB DFU firmware flashing

**Python 3.13 Stack:**
- python3.13 with full development headers (python3.13-dev)
- pip, setuptools, wheel, virtualenv
- python3-numpy, python3-pillow — for image processing
- python3-serial — for serial/UART communication (Klipper)
- python3-can — CAN bus communication
- python3-cffi, python3-greenlet — native extensions

**Display System:**
- X11 (xserver-xorg, xinit, x11-utils, x11-xserver-utils)
- Openbox window manager
- No full desktop environment — minimal X11 for KlipperScreen

**Media / Camera:**
- FFmpeg with full libav* stack
- fswebcam, mjpg-streamer-experimental
- libopencv-* (OpenCV for computer vision)
- v4l-utils (Video4Linux)

**Web Server:**
- Nginx (for Moonraker/Fluidd/Mainsail web interface)

**Networking:**
- NetworkManager, wpasupplicant
- Avahi (mDNS/DNS-SD)
- OpenSSH server
- Bluetooth (bluez)

---

## 5. Kernel Modifications Summary

### What Makes This Kernel Custom

1. **Rockchip BSP kernel** — Not mainline Linux. Based on Rockchip's downstream 6.1 kernel tree with massive vendor-specific additions:
   - ISP (Image Signal Processor) v2.0 subsystem
   - NPU (Neural Processing Unit) driver
   - VPU/MPP (Video Processing Unit / Media Process Platform)
   - PVTM (Process-Voltage-Temperature Monitor)
   - DMC (Dynamic Memory Controller) frequency scaling
   - RGA (2D graphics accelerator)
   - Rockchip-specific DRM/display pipeline

2. **Monolithic build** — Zero kernel modules (`CONFIG_*=m` count: 0). Everything is built-in. This eliminates module loading overhead but means any hardware change requires a full kernel rebuild.

3. **Custom version string** — `6.1.99flsun OS` with the `flsun OS` suffix baked directly into the version, not via `CONFIG_LOCALVERSION`.

4. **Full CAN bus stack** — Every CAN driver under the sun is compiled in (Rockchip native, USB-CAN adapters, serial CAN, etc.), even though CAN is disabled in the DTB by default.

5. **WiFi driver** — Broadcom bcmdhd built directly into the kernel (not a module), compiled on the same date as the kernel.

6. **USB gadget support** — RNDIS + mass storage + UVC, allowing the S1 to appear as a USB network adapter, storage device, or webcam when connected to a PC.

7. **PREEMPT configuration** — Full preemption at 300 Hz for real-time responsiveness (important for Klipper motion planning).

8. **Mini kernel optimization** — `CONFIG_ROCKCHIP_MINI_KERNEL=y` enables Rockchip's kernel size optimization features.

### Open Questions

- **Kernel source availability:** The kernel is GPL, so the source should be available. It's likely based on Rockchip's `kernel-6.1` branch with FLSUN-specific DTB and config modifications. Guilouz may have the source in a private repo.
- **CAN bus disabled in DTB:** The kernel has full CAN support, but the DTB has CAN disabled. This may be intentional (S1 might use CAN via a different mechanism) or a default that gets enabled at runtime.
- **Camera path:** The ISP and ISPP are enabled but all CSI/MIPI-CSI2 frontend interfaces are disabled. The camera may connect through the CIF (Camera Interface Framework) which is enabled.

---

## 6. Extracted Files Index

| File | Size | Description |
|---|---|---|
| `extracted/rk-kernel.dts` | 5,657 lines | Full decompiled device tree source |
| `extracted/kernel-config.txt` | 173,960 bytes | Full kernel .config (from IKCONFIG) |
| `extracted/vmlinux-decompressed.bin` | 20,654,540 bytes | Decompressed kernel binary |
| `rootfs-extracted/dpkg-status-full.txt` | 955,773 bytes | Raw dpkg/status with all metadata |
| `rootfs-extracted/packages-with-versions.txt` | - | Tab-separated: name, version, arch |
| `docs/S1/research/10-installed-packages.md` | - | Categorized package list document |
