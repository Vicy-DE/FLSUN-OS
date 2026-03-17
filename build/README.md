# FLSUN OS Build System

Build a Debian 13 Trixie (armhf) OS image for **FLSUN delta 3D printers**, based on the Rockchip RV11xx SoC family.

| Printer | SoC | Recipe | Build Script |
|---------|-----|--------|-------------|
| **FLSUN S1** | RV1126 (quad-core) | `flsun-os.yaml` | `build.sh` |
| **FLSUN T1** | RV1109 (dual-core) | `flsun-os-t1.yaml` | `build-t1.sh` |

The S1 build system was reconstructed by reverse-engineering FLSUN OS 3.0 — see the research docs in `docs/S1/research/` for full details. The T1 build is adapted from the S1 recipe with hardware-specific changes documented in `docs/T1/research/05-s1-to-t1-porting-guide.md`.

---

## Overview

Both printers use a dual-image boot layout flashed to eMMC:

| Image | Format | Contents |
|-------|--------|----------|
| `boot.img` | Android mkbootimg or U-Boot FIT | zImage kernel + DTB |
| `rootfs.img` | ext4 filesystem | Full Debian OS + Klipper ecosystem |

This build system produces `rootfs.img` using **[debos](https://github.com/go-debos/debos)** (Debian OS builder by Collabora). The kernel/DTB (`boot.img`) must be sourced separately since the kernel is a pre-built Rockchip BSP.

---

## Quick Start

### Prerequisites

- **Docker** (recommended — works on any host OS including x86_64)
- OR native Linux with `debos`, `qemu-user-static`, `debootstrap`
- At least **16 GB free disk space**
- Internet connection

### Build rootfs.img

```bash
# ── S1 Build ──
chmod +x build.sh
./build.sh

# ── T1 Build ──
chmod +x build-t1.sh
./build-t1.sh

# With custom image size (either printer)
./build-t1.sh --image-size 4GB

# Validate recipe without building
./build-t1.sh --dry-run

# Without Docker (native Linux only)
./build-t1.sh --no-docker
```

Output: `output/rootfs.img`

### Build kernel from source (requires Linux/WSL)

```bash
chmod +x build-kernel.sh

# ── S1 (default) ──
./build-kernel.sh

# ── T1 (patches DTB for 800×480 display) ──
./build-kernel.sh --target t1

# With menuconfig for manual tweaking
./build-kernel.sh --target t1 --menuconfig
```

Output: `output/zImage`, `output/rk-kernel.dtb` (S1) or `output/rk-kernel-t1.dtb` (T1), `output/boot.img`

Requires `gcc-arm-linux-gnueabihf` cross-compiler (install: `sudo apt install gcc-arm-linux-gnueabihf bc flex bison libssl-dev`).

### Build boot.img (requires kernel + DTB)

```bash
# ── S1 ──
chmod +x build-boot-img.sh
./build-boot-img.sh /path/to/zImage /path/to/rk-kernel.dtb

# ── T1 — Android boot format (default) ──
chmod +x build-boot-img-t1.sh
./build-boot-img-t1.sh /path/to/zImage /path/to/rk-kernel-t1.dtb

# ── T1 — FIT format (if T1 U-Boot requires it) ──
./build-boot-img-t1.sh /path/to/zImage /path/to/rk-kernel-t1.dtb --format fit
```

Output: `output/boot.img`

### Package for eMMC flashing

```bash
# ── S1 ──
chmod +x package-emmc.sh
./package-emmc.sh 4.0
# Creates output/FLSUN-OS-S1-EMMC-4.0.7z

# ── T1 ──
chmod +x package-emmc-t1.sh
./package-emmc-t1.sh 1.0
# Creates output/FLSUN-OS-T1-EMMC-1.0.7z
```

### Package kernel as .deb (for apt delivery)

```bash
chmod +x package-kernel-deb.sh

# Package S1 kernel as .deb
./package-kernel-deb.sh --target s1

# Package T1 kernel with explicit version
./package-kernel-deb.sh --target t1 --version 6.1.115 --revision 1
```

Output: `output/flsun-os-kernel-{s1,t1}_{version}-{rev}_armhf.deb`

The .deb `postinst` writes `boot.img` to `/dev/mmcblk0p3` via `dd` on install. See `docs/S1/research/13-apt-update-concept.md` for the full update strategy.

---

## File Structure

```
build/
├── flsun-os.yaml              # S1 debos recipe (23 build stages)
├── flsun-os-t1.yaml            # T1 debos recipe (24 build stages, load cell + host MCU)
├── build.sh                    # S1 rootfs build script (wraps debos)
├── build-t1.sh                 # T1 rootfs build script (wraps debos)
├── build-kernel.sh             # Kernel build script (S1/T1, cross-compile + boot.img)
├── build-boot-img.sh           # S1 boot image packaging (mkbootimg)
├── build-boot-img-t1.sh        # T1 boot image packaging (mkbootimg or FIT)
├── package-emmc.sh             # S1 eMMC archive creator (7z)
├── package-emmc-t1.sh          # T1 eMMC archive creator (7z)
├── package-kernel-deb.sh       # Kernel .deb packager (for apt delivery)
├── README.md                   # This file
├── overlays/                   # S1 overlay files
│   ├── system/                 # Files copied to rootfs as root
│   │   ├── etc/
│   │   │   ├── rc.local                        # Boot-time initialization
│   │   │   ├── power-key.sh                    # Power button handler
│   │   │   ├── input-event-daemon.conf         # Input event routing
│   │   │   ├── init.d/
│   │   │   │   ├── first-boot.sh               # First-boot setup (resize, hostname, SSH)
│   │   │   │   └── S60NPU_init                 # NPU kernel module loader
│   │   │   └── systemd/system/
│   │   │       ├── klipper.service             # Klipper 3D printer firmware
│   │   │       ├── moonraker.service           # Moonraker API server
│   │   │       ├── KlipperScreen.service       # Touchscreen UI
│   │   │       ├── webcamd.service             # MJPG-Streamer camera
│   │   │       ├── FLSUN-OS-Dependencies.service # OS update checker
│   │   │       ├── drying-box.service          # Filament dryer sensor
│   │   │       └── usb-mount@.service          # USB auto-mount template
│   │   └── usr/local/bin/
│   │       └── webcamd                         # MJPG-Streamer wrapper script
│   └── user/                   # Files copied to rootfs (pi user data)
│       └── home/pi/printer_data/config/
│           └── moonraker.conf                  # S1 Moonraker configuration
├── overlays-t1/                # T1 overlay files
│   ├── system/                 # Files copied to rootfs as root
│   │   ├── etc/
│   │   │   ├── rc.local                        # Boot-time init (+ PWM export for caselight)
│   │   │   ├── power-key.sh                    # Power button handler
│   │   │   ├── input-event-daemon.conf         # Input event routing
│   │   │   ├── init.d/
│   │   │   │   ├── first-boot.sh               # First-boot setup (FLSUN-T1-XXXX hostname)
│   │   │   │   └── S60NPU_init                 # NPU kernel module loader (RV1109)
│   │   │   └── systemd/system/
│   │   │       ├── klipper.service             # Klipper service
│   │   │       ├── moonraker.service           # Moonraker API server
│   │   │       ├── KlipperScreen.service       # Touchscreen UI
│   │   │       ├── webcamd.service             # MJPG-Streamer camera
│   │   │       ├── klipper-mcu.service         # Linux host MCU (caselight PWM)
│   │   │       └── usb-mount@.service          # USB auto-mount template
│   │   └── usr/local/bin/
│   │       └── webcamd                         # MJPG-Streamer wrapper script
│   └── user/                   # Files copied to rootfs (pi user data)
│       └── home/pi/printer_data/config/
│           ├── printer.cfg                     # T1 hardware definitions (3 MCUs)
│           ├── config.cfg                      # T1 component include selector
│           ├── moonraker.conf                  # T1 Moonraker config (garethky Klipper)
│           ├── KlipperScreen.conf              # T1 KlipperScreen (800×480)
│           └── Configurations/
│               ├── macros.cfg                  # GCode macros (~940 lines)
│               ├── fan-stock.cfg               # Stock T1 fan (max_power=0.8)
│               ├── fan-silent-kit.cfg          # T1 Pro / silent kit fan (max_power=0.6)
│               ├── led-stock.cfg               # Caselight via host PWM
│               └── filament-sensor-stock.cfg   # 3 filament sensors
├── tools/                      # T1 image modification tools (Python, no deps)
│   ├── patch-dtb-for-t1.py                     # Patch S1 DTB for T1 display (800×480)
│   ├── build-boot-img-t1.py                    # Package zImage + DTB → Android boot.img
│   ├── build-images-t1.py                      # *** Master image builder (3 images) ***
│   ├── build-rootfs-t1.sh                      # Rootfs builder (S1→T1, Linux/WSL only)
│   └── mod-rootfs-for-t1.sh                    # Convert S1 rootfs to T1 (bash, Linux/WSL)
└── output/                     # Build artifacts (gitignored)
    ├── flsun-os-t1-kernel.img                  # T1 boot partition image (Android boot)
    ├── flsun-os-t1-rootfs.img                  # T1 rootfs partition image (ext4)
    ├── flsun-os-t1-complete.img                # T1 complete eMMC disk image (GPT)
    ├── flsun-os-t1-manifest.json               # Build manifest (SHA256, sizes)
    ├── FLSUN-OS-S1-EMMC-*.7z
    └── FLSUN-OS-T1-EMMC-*.7z
```

---

## Build Recipe Stages

### S1 Recipe (`flsun-os.yaml`) — 23 stages

| # | Stage | Description |
|---|-------|-------------|
| 1 | debootstrap | Bootstrap Debian Trixie base system (armhf) |
| 2 | APT sources | Configure main + contrib + non-free + security + backports |
| 3 | Core packages | systemd, sudo, SSH, networking, filesystems, utilities |
| 4 | Build tools | GCC, cross-compilers (ARM + AVR), make, cmake, dfu-util |
| 5 | Python 3 | Python 3.13 + dev packages + venv + scientific libraries |
| 6 | Display stack | X11, GTK3, GObject, OpenBox, fonts (for KlipperScreen) |
| 7 | Media | ffmpeg, v4l-utils, libjpeg (for MJPG-Streamer) |
| 8 | Nginx | Web server for Mainsail/Fluidd UIs |
| 9 | OS identity | `/etc/os-release`, hostname, locale |
| 10 | Users | Create `pi` user (sudo, dialout, tty, video, input, plugdev) |
| 11 | SSH | Enable root login, password auth, X11 forwarding |
| 12 | Klipper ecosystem | Git clone + Python venvs for Klipper, Moonraker, KlipperScreen, Katapult, KIAUH, flsun-os |
| 13 | MJPG-Streamer | Build from source (cmake) |
| 14 | Mainsail | Download latest release ZIP |
| 15 | Overlays | Copy system + user overlay files |
| 16 | printer_data | Create directory structure + env files + moonraker.asvc |
| 17 | KIAUH config | Configure to use FLSUN Klipper fork |
| 18 | Services | Enable all systemd services, chmod scripts |
| 19 | Ownership | `chown -R pi:pi /home/pi/` |
| 20 | Nginx config | Mainsail reverse proxy to Moonraker :7125 |
| 21 | Cleanup | APT cache, logs, regenerate machine-id |
| 22 | fstab | `/dev/root / ext4 defaults 0 1` |
| 23 | Image | Partition + deploy to ext4 rootfs.img |

### T1 Recipe (`flsun-os-t1.yaml`) — 24 stages

Key differences from S1 are marked with **bold**.

| # | Stage | Description |
|---|-------|-------------|
| 1 | debootstrap | Bootstrap Debian Trixie base system (armhf) |
| 2 | APT sources | Configure main + contrib + non-free + security + backports |
| 3 | Core packages | systemd, sudo, SSH, networking, filesystems, utilities |
| 4 | Build tools | GCC, cross-compilers (ARM + AVR), make, cmake, dfu-util |
| 5 | Python 3 | Python 3.13 + dev + venv + **python3-scipy** (load cell probe) |
| 6 | Display stack | X11, GTK3, GObject, OpenBox, fonts (for KlipperScreen) |
| 7 | Media | ffmpeg, v4l-utils, libjpeg (for MJPG-Streamer) |
| 8 | Nginx | Web server for Mainsail/Fluidd UIs |
| 9 | OS identity | `/etc/os-release`, hostname, locale |
| 10 | Users | Create `pi` user (sudo, dialout, tty, video, input, plugdev) |
| 11 | SSH | Enable root login, password auth, X11 forwarding |
| 12 | Klipper ecosystem | **garethky/klipper** (load-cell-probe branch) + **upstream KlipperScreen** + Moonraker, Katapult, KIAUH; **scipy in klippy-env** |
| 13 | MJPG-Streamer | Build from source (cmake) |
| 14 | **klipper_mcu** | **Build Linux MCU firmware (`klipper_mcu` binary) for host process** |
| 15 | Mainsail | Download latest release ZIP |
| 16 | Overlays | Copy **overlays-t1/** system + user files |
| 17 | printer_data | Create directory structure + env files + moonraker.asvc (**includes klipper_mcu**) |
| 18 | KIAUH config | Configure to use **garethky Klipper fork** |
| 19 | Services | Enable services (**klipper-mcu.service**, no drying-box/FLSUN-OS-Dependencies) |
| 20 | Ownership | `chown -R pi:pi /home/pi/` |
| 21 | Nginx config | Mainsail reverse proxy to Moonraker :7125 |
| 22 | Cleanup | APT cache, logs, regenerate machine-id |
| 23 | fstab | `/dev/root / ext4 defaults 0 1` |
| 24 | Image | Partition + deploy to ext4 rootfs.img |

---

## Customization

### Template Variables

Pass with `debos -t key:value` or via `build.sh` flags:

| Variable | Default | Description |
|----------|---------|-------------|
| `image_size` | `8GB` | rootfs.img total size |
| `hostname` | `FLSUN-OS` | Initial hostname (overwritten on first boot by MAC-based name) |
| `user` | `pi` | Primary user account |
| `password` | `flsun` | User password |
| `root_password` | `flsun` | Root password |
| `suite` | `trixie` | Debian release codename |
| `arch` | `armhf` | CPU architecture |
| `mirror` | `http://deb.debian.org/debian` | APT mirror |

### Adding Packages

Edit the `apt` action stages in `flsun-os.yaml`. Packages are grouped by function (core, build tools, Python, display, media, web server).

### Adding Services

1. Create service file in the appropriate overlay directory:
   - S1: `overlays/system/etc/systemd/system/`
   - T1: `overlays-t1/system/etc/systemd/system/`
2. Add `systemctl enable <service>` to the Services stage in the recipe
3. Add to `moonraker.asvc` in the printer_data stage if Moonraker should manage it

### Changing Git Repos

Edit the Klipper ecosystem stage in the recipe to change fork URLs or branches:
- S1 (`flsun-os.yaml` Stage 12): Uses `Guilouz/Klipper-Flsun-S1` + `Guilouz/KlipperScreen-Flsun-S1`
- T1 (`flsun-os-t1.yaml` Stage 12): Uses `garethky/klipper` branch `load-cell-probe-community-testing` + upstream `KlipperScreen/KlipperScreen`

---

## Hardware Reference

### FLSUN S1

| Component | Detail |
|-----------|--------|
| SoC | Rockchip RV1126 (ARMv7, quad Cortex-A7 @ 1.512 GHz) |
| RAM | 1 GB DDR3 |
| Storage | 8 GB eMMC (GPT: 6 partitions) |
| Display | 7" 1024×600 RGB parallel panel, PWM backlight |
| PMIC | RK809 on I2C0 (addr 0x20) |
| MCU | STM32 motherboard (flashed via ST-LINK V2) |
| WiFi | AP6212 (BCM43438) on SDIO |
| NPU | Rockchip NPU @ ffbc0000 (galcore.ko) |
| Kernel | Linux 6.1.99flsun (Rockchip BSP, fully monolithic) |
| Klipper fork | Guilouz/Klipper-Flsun-S1 |

### FLSUN T1 / T1 Pro

| Component | Detail |
|-----------|--------|
| SoC | Rockchip RV1109 (ARMv7, dual Cortex-A7 @ 1.512 GHz) |
| RAM | 1 GB DDR3 |
| Storage | 8 GB eMMC (GPT: 6 partitions) |
| Display | 7" 800×480 RGB parallel panel, PWM backlight (25 MHz pixel clock) |
| PMIC | RK809 on I2C0 |
| Main MCU | GD32F303 (STM32F103xe compatible), 72 MHz, 250000 baud on USB |
| Load Cell MCU | STM32F103 on UART `/dev/ttyS0`, 250000 baud (HX717 strain gauge) |
| Host MCU | klipper_mcu Linux process (caselight PWM via pwmchip0/pwm0) |
| WiFi | AP6212 (BCM43438) on SDIO — same as S1 |
| NPU | Rockchip NPU (galcore.ko) |
| Stepper drivers | TMC5160 via SPI (dedicated per-driver SPI buses) |
| Probe | Load cell (HX717 sensor, requires SciPy for notch/drift filters) |
| Kinematics | Delta, print_radius=133, arm_length≈334-336 |
| Kernel | Linux 4.19.111 (stock, Rockchip BSP) |
| Klipper fork | garethky/klipper (load-cell-probe-community-testing) |

### eMMC Partition Layout

**S1** (6 partitions):

| # | Name | Offset (sectors) | Note |
|---|------|-------------------|------|
| 1 | uboot | 0x2000 | U-Boot bootloader |
| 2 | misc | 0x4000 | Recovery/misc |
| 3 | boot | 0x8000 | boot.img (kernel + DTB) |
| 4 | recovery | 0xC000 | Recovery image |
| 5 | backup | 0x10000 | Backup partition |
| 6 | rootfs | 0x40000 | rootfs.img (resized on first boot) |

**T1** (6 partitions):

| # | Name | Offset (sectors) | Note |
|---|------|-------------------|------|
| 1 | uboot | 0x2000 | U-Boot bootloader |
| 2 | misc | 0x4000 | Recovery/misc |
| 3 | boot | 0x6000 | boot.img (kernel + DTB) |
| 4 | recovery | 0xE000 | Recovery image |
| 5 | backup | 0x16000 | Backup partition |
| 6 | rootfs | 0x56000 | rootfs.img (resized on first boot) |

> **Note:** The T1 stock GPT has 6 partitions (same names as S1: uboot, misc, boot, recovery, backup, rootfs). Earlier documentation incorrectly listed 9 partitions (with oem, userdata, media) based on a standard Rockchip SDK layout, but the actual stock eMMC dump (`1097_0p1.img` through `1097_0p6.img`) confirms only 6 exist. The oem/userdata/media partitions are Rockchip Buildroot/Android conventions that FLSUN did not use.

---

## First Boot Behavior

On first boot, `first-boot.sh` (called from `rc.local`) performs:

| Step | S1 | T1 |
|------|----|----|
| Resize rootfs | Expands partition 6 | Expands last partition |
| Set hostname | `FLSUN-S1-XXXX` (WiFi MAC suffix) | `FLSUN-T1-XXXX` (WiFi MAC suffix) |
| Generate SSH keys | `ssh-keygen -A` | `ssh-keygen -A` |
| Create symlinks | `easy-installer` + `kiauh` | `kiauh` only (no easy-installer) |
| Restore Web UI | Mainsail/Fluidd JSON via Moonraker API | *Skipped* (no pre-built JSON) |
| Enable zram swap | `/dev/zram0` in fstab | `/dev/zram0` in fstab |
| Self-remove | Removes itself from rc.local | Removes itself from rc.local |
| Reboot | Clean restart | Clean restart |

---

## Flashing to eMMC

### Requirements

- Windows PC with **RKDevTool v2.96**
- USB-C cable
- `MiniLoaderAll.bin` (Rockchip loader — different binary for RV1126 vs RV1109)

### Procedure — S1

1. Power off the printer
2. Hold the Maskrom button and connect USB-C
3. RKDevTool should detect the device in Maskrom mode
4. Load `MiniLoaderAll.bin` (RV1126) as the loader
5. Flash `boot.img` to the boot partition (offset `0x8000`)
6. Flash `rootfs.img` to the rootfs partition (offset `0x40000`)
7. Click **Run** and wait for completion
8. Disconnect and power on

### Procedure — T1

1. Power off the printer
2. Hold the Maskrom button and connect USB-C
3. RKDevTool should detect the RV1109 in Maskrom mode
4. Load `MiniLoaderAll.bin` (RV1109) as the loader
5. Flash `boot.img` to the boot partition (offset `0x6000`)
6. Flash `rootfs.img` to the rootfs partition (offset `0x7A000`)
7. Click **Run** and wait for completion
8. Disconnect and power on

> **Note:** The T1 has different partition offsets than the S1. Double-check the offset values against your device's GPT table before flashing.

---

## T1 Image Modification Tools

An alternative to the full debos build: create a T1 firmware by modifying the existing S1 FLSUN-OS 3.0 image. Since the S1 kernel (6.1.99flsun) boots on the T1 (same rv1126 platform), only the DTB and rootfs need modification.

The tools in `build/tools/` are pure Python (no external dependencies) and work on Windows, Linux, and macOS.

### Step 1: Patch DTB for T1 display

```bash
# Patches S1 DTB (1024×600) → T1 DTB (800×480)
py build/tools/patch-dtb-for-t1.py
# Input:  resources/S1/firmwares/os-images/FLSUN-OS-S1-EMMC-3.0/extracted/rk-kernel.dtb
# Output: resources/T1/firmwares/os-images/rk-kernel-t1.dtb

# Or with explicit paths:
py build/tools/patch-dtb-for-t1.py <input.dtb> <output.dtb>
```

Patches 17 properties: model, compatible, bus-format (RGB888), display dimensions (95×54mm), and 12 timing values (clock-frequency 25MHz, hactive 800, vactive 480, porches, sync widths, polarity flags).

### Step 2: Build T1 boot.img

```bash
# Packages S1 zImage + T1-patched DTB → Android boot.img
py build/tools/build-boot-img-t1.py
# Input:  S1 zImage + T1 rk-kernel-t1.dtb
# Output: resources/T1/firmwares/os-images/boot.img

# Or with explicit paths:
py build/tools/build-boot-img-t1.py <zImage> <dtb> <output>
```

Creates an Android mkbootimg (`ANDROID!` magic) with RSCE resource container, matching the S1 boot format.

### Step 3: Modify rootfs for T1

```bash
# Mount the S1 rootfs.img and run the modifier (requires Linux/WSL, root access):
sudo mount -o loop resources/S1/firmwares/os-images/FLSUN-OS-S1-EMMC-3.0/rootfs.img /mnt/rootfs
sudo bash build/tools/mod-rootfs-for-t1.sh /mnt/rootfs
sudo umount /mnt/rootfs

# Or run directly on T1 after booting S1 image (live mode):
sudo bash build/tools/mod-rootfs-for-t1.sh /

# Dry run (show changes without modifying):
sudo bash build/tools/mod-rootfs-for-t1.sh --dry-run /mnt/rootfs
```

The rootfs modifier performs 13 steps:
1. Replace Klipper configs with T1 ported versions
2. Replace Moonraker config (no drying box, garethky fork)
3. Replace KlipperScreen config (800×480, T1 branding)
4. Update systemd services (remove drying-box, add klipper-mcu)
5. Update first-boot.sh (FLSUN-T1 hostname, no JSON restore)
6. Update rc.local (PWM export for caselight)
7. Switch Klipper fork (Guilouz → garethky, live mode only)
8. Switch KlipperScreen fork (S1 fork → upstream, live mode only)
9. Build klipper_mcu (Linux MCU process, live mode only)
10. Install SciPy in klippy-env (live mode only)
11. Remove S1-specific files (drying-box, easy-installer, JSON backups)
12. Update hostname and branding
13. Fix file permissions

In offline mode, steps 7–10 are deferred to a `~/.t1-klipper-switch-pending` marker file with instructions to run after first boot.

---

## Kernel Build from Source

The FLSUN OS kernel is built from the **Armbian fork** of the Rockchip BSP kernel, confirmed by Guilouz in [Discussion #13](https://github.com/Guilouz/FLSUN-S1-Open-Source-Edition/discussions/13).

| Property | Value |
|---|---|
| Repo | [armbian/linux-rockchip](https://github.com/armbian/linux-rockchip) |
| Branch | `rk-6.1-rkr5.1` |
| Defconfig | `arch/arm/configs/rv1126_defconfig` (shared by RV1126 + RV1109) |
| Cross-compiler | `arm-linux-gnueabihf-gcc` 11.4.0 (Ubuntu 22.04) |
| FLSUN OS 3.0 version | 6.1.99 (fully monolithic — zero modules) |
| Submodule path | `kernel/` |

The kernel source is available as a git submodule at `kernel/`. Full build documentation including config strategy, build commands, boot.img packaging, and flashing instructions is in `docs/S1/research/12-kernel-build-from-source.md`.

### Using build-kernel.sh (Recommended)

The `build-kernel.sh` script automates configuration, compilation, DTB patching, and boot.img packaging:

```bash
# Initialize kernel submodule (first time only)
git submodule update --init --depth 1 kernel

# Build for S1 (default)
./build-kernel.sh

# Build for T1 (patches DTB for 800×480 display)
./build-kernel.sh --target t1

# Clean + reconfigure + menuconfig
./build-kernel.sh --target t1 --clean --menuconfig
```

The script:
1. Copies the extracted FLSUN OS 3.0 kernel config as a defconfig
2. Runs `make ARCH=arm flsun_{s1,t1}_defconfig` + `olddefconfig`
3. Cross-compiles with `arm-linux-gnueabihf-gcc`
4. Copies zImage and DTB to `output/`
5. For T1: patches DTB with `patch-dtb-for-t1.py` (1024×600 → 800×480)
6. Packages `boot.img` via `build-boot-img-t1.py`

### Manual Build

```bash
# Clone source (if not using submodule)
git clone --depth 1 -b rk-6.1-rkr5.1 \
    https://github.com/armbian/linux-rockchip.git kernel

# Configure using the extracted FLSUN OS 3.0 config
cp resources/S1/firmwares/os-images/FLSUN-OS-S1-EMMC-3.0/extracted/kernel-config.txt \
    kernel/arch/arm/configs/flsun_s1_defconfig
cd kernel
make ARCH=arm flsun_s1_defconfig

# Build (requires Linux with arm cross-compiler)
make ARCH=arm CROSS_COMPILE=arm-linux-gnueabihf- -j$(nproc) zImage dtbs

# Package boot.img
cd .. && py build/tools/build-boot-img-t1.py output/zImage output/rk-kernel.dtb output/boot.img
```

---

## T1 Master Image Builder (`build-images-t1.py`)

The master tool produces all three T1 firmware images with a single command:

```bash
# Build kernel image only (Windows/Mac/Linux — no dependencies)
py -3 build/tools/build-images-t1.py --kernel

# Build rootfs image (Linux/WSL only — requires root for ext4 mount)
sudo python3 build/tools/build-images-t1.py --rootfs

# Build complete eMMC image (Linux/WSL only — requires rootfs first)
sudo python3 build/tools/build-images-t1.py --complete

# Build ALL three images (Linux/WSL only)
sudo python3 build/tools/build-images-t1.py --all
```

### Output Images

| Image | Format | Size | Use |
|-------|--------|------|-----|
| `flsun-os-t1-kernel.img` | Android boot (ANDROID!) | ~8.3 MB | Flash to boot partition (p3) |
| `flsun-os-t1-rootfs.img` | ext4 partition | ~7.5 GB | Flash to rootfs partition (p6) |
| `flsun-os-t1-complete.img` | GPT disk image | ~7.5 GB | Flash as raw disk or via RKDevTool |

A `flsun-os-t1-manifest.json` with SHA256 hashes is generated alongside the images.

### Rootfs Builder Script

For building the rootfs separately (on Linux/WSL):

```bash
# Standard build
sudo bash build/tools/build-rootfs-t1.sh

# Build with image shrinking (smaller output)
sudo bash build/tools/build-rootfs-t1.sh --shrink

# Modify a live T1 running S1 image (instead of building offline)
sudo bash build/tools/build-rootfs-t1.sh --live

# Dry run (show what would change)
sudo bash build/tools/build-rootfs-t1.sh --dry-run
```

---

## What This Build System Does NOT Include

- **Kernel compilation** — The kernel is a Rockchip BSP that must be cross-compiled separately or extracted from stock firmware (S1: Linux 6.1.99flsun; T1: Linux 4.19.111)
- **Device tree compilation** — The DTB is board-specific and must be sourced from stock firmware or compiled from DTS source
- **U-Boot** — The bootloader is not rebuilt; use the stock `MiniLoaderAll.bin` (different binary per SoC)
- **NPU firmware** — `galcore.ko` and RKNN runtime must be sourced from Rockchip SDK
- **Printer config** — `printer.cfg` must be provided separately; S1 uses the FLSUN installer, T1 uses the ported configs from `resources/T1/klipper-configs/ported/`
- **Web UI backups** — Mainsail/Fluidd JSON config files (S1 only, from the `flsun-os` dependencies repo)
- **MCU firmware** — GD32F303 (T1) / STM32 (S1) motherboard firmware must be flashed separately via ST-LINK V2 or SD card

---

## Troubleshooting

### debos fails with QEMU errors
Ensure `qemu-user-static` is installed and binfmt is configured:
```bash
docker run --rm --privileged multiarch/qemu-user-static --reset -p yes
```

### Image is too large for eMMC
Reduce `--image-size`. Both S1 and T1 have 8 GB eMMC (~4.5 GB usable for rootfs after other partitions).

### Docker permission denied on /dev/kvm
Add your user to the `kvm` group or run Docker with `--privileged`.

### Git clone failures during build
The build requires internet access to clone 6 Git repos. If behind a proxy, configure Docker's proxy settings.

---

## References

### S1
- [FLSUN S1 Open Source Edition Wiki](https://guilouz.github.io/FLSUN-S1-Open-Source-Edition/home.html)
- [Klipper-Flsun-S1](https://github.com/Guilouz/Klipper-Flsun-S1)
- [KlipperScreen-Flsun-S1](https://github.com/Guilouz/KlipperScreen-Flsun-S1)
- [FLSUN-S1-Open-Source-Edition-Dependencies](https://github.com/Guilouz/FLSUN-S1-Open-Source-Edition-Dependencies)

### T1
- [garethky/klipper — Load Cell Probe](https://github.com/garethky/klipper/tree/load-cell-probe-community-testing)
- [mulcmu/T1-pyro — Raspberry Pi replacement project](https://github.com/mulcmu/T1-pyro)
- [T1 Porting Guide](../docs/T1/research/05-s1-to-t1-porting-guide.md)
- [T1 Hardware Overview](../docs/T1/research/01-hardware-overview.md)
- [T1 Klipper Config Analysis](../docs/T1/research/04-klipper-config-analysis.md)

### General
- [debos documentation](https://github.com/go-debos/debos)
- [Rockchip RV1126/RV1109 TRM](https://opensource.rock-chips.com/)
