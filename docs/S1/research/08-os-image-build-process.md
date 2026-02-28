# OS Image Build Process — Rockchip RV1126 + Debian 13

**Date researched:** 2025-02-28 (updated 2025-05-30 with actual image analysis)  
**Sources:**
- Geekbench comparison: https://browser.geekbench.com/v5/cpu/compare/22823940?baseline=22823878
- Rockchip Boot Option wiki: https://opensource.rock-chips.com/wiki_Boot_option
- Rockchip Partitions wiki: https://opensource.rock-chips.com/wiki_Partitions
- Rockchip rkbin repo: https://github.com/rockchip-linux/rkbin
- FLSUN OS eMMC install page: https://guilouz.github.io/FLSUN-S1-Open-Source-Edition/install-flsun-os-on-emmc/
- FLSUN OS changelogs: https://guilouz.github.io/FLSUN-S1-Open-Source-Edition/changelogs/
- GitHub Discussion #13 (T1 Edition): https://github.com/Guilouz/FLSUN-S1-Open-Source-Edition/discussions/13
- GitHub Discussion #68 (Resize eMMC): https://github.com/Guilouz/FLSUN-S1-Open-Source-Edition/discussions/68

---

## SoC Identification

The FLSUN S1 core board uses a **Rockchip RV1126** SoC, confirmed via Geekbench benchmarks linked from the official About page.

| Property | Value |
|---|---|
| SoC | Rockchip RV1126 |
| Architecture | ARMv7 (ARM Cortex-A7) |
| CPU | Quad-core @ 1.51 GHz |
| RAM | 1 GB DDR3 (733 MB usable to userspace) |
| Board Identifier | `RV1126 EVB DDR3 V1.6` (FLSUN-OS) / `V13` (stock FLSUN) |
| Processor ID | ARM implementer 65 architecture 7 variant 0 part 3079 (0xC07 = Cortex-A7) revision 5 |
| NPU | 2 TOPS (AI vision features, not used by FLSUN OS) |
| Camera ISP | Up to 12-megapixel (original purpose: IP cameras/smart vision) |

> **Note:** The FLSUN T1/T1 Pro uses a different SoC — the **Rockchip RV1109** (same family, reduced variant). Images are NOT interchangeable between S1 and T1.

### OS Version History on this SoC

| FLSUN OS Version | Debian Version | Kernel | Key Changes |
|---|---|---|---|
| Stock | Debian 10 (Buster) | Unknown (~1.0 GHz) | 700 MB RAM accessible, expired support |
| v1.0–1.5.1 | Debian 12 (Bookworm) | → v6.1.99 (from v2.0) | CPU restored to 1.5 GHz, full 1 GB RAM |
| v2.0–2.0.2 | Debian 12 (Bookworm) | v6.1.99 | ZRAM 512 MB swap, Katapult bootloader |
| v3.0 | **Debian 13 (Trixie)** | v6.1.99 | Python 3.13, new OS rebuild required |

---

## Image Distribution Format

FLSUN OS is distributed as two image variants:

### 1. SD Card Image: `FLSUN-OS-S1-SD-3.0.img.gz`

- **Format:** gzip-compressed raw disk image (full GPT disk)
- **Writing tool:** Raspberry Pi Imager (or any dd-style tool)
- **Contains:** Complete disk — GPT table + bootloader + all 6 partitions
- **Minimum card size:** 16 GB
- **First boot behavior:** Auto-resizes rootfs partition to fill card, configures web interfaces, reboots
- **Non-destructive:** eMMC stock OS is untouched; remove SD card to revert

### 2. eMMC Image: `FLSUN-OS-S1-EMMC-3.0.7z`

- **Format:** 7z archive containing `boot.img` and `rootfs.img` only
- **File size:** 818,257,295 bytes (780 MB)
- **SHA256:** `a7c97a1152bc9ea1554f847198cd31226af5055199019cc57eb56230cee05534`
- **Writing tool:** RKDevTool v2.96 (Windows) via USB-C in LOADER mode
- **Contains:** Only boot + rootfs partitions (U-Boot/trust from existing install are preserved)
- **Flash procedure:** USB-C to core board → hold BOOT9200 → press/release BOOT2100 → release BOOT9200 → "Write by Address" in RKDevTool
- **boot.img:** 10,072,064 bytes — Android boot image format (mkbootimg), contains zImage + DTB in Rockchip Resource Image
- **rootfs.img:** 7,882,542,592 bytes — ext4 filesystem, label `rootfs`

> **See also:** [09-image-reverse-engineering.md](09-image-reverse-engineering.md) for detailed binary analysis of both images.

---

## eMMC Partition Layout

The RV1126 eMMC follows the standard Rockchip GPT partition scheme:

```
┌──────────────────────────────────────────────────────────────┐
│ LBA 0-63      │ GPT Partition Table (32 KB)                  │
├───────────────┼──────────────────────────────────────────────┤
│ LBA 64-16383  │ Bootloader / IDBLoader (DDR init + SPL)      │
│               │  ≈ 3.5 MB                                    │
├───────────────┼──────────────────────────────────────────────┤
│ mmcblk0p1     │ uboot.img    — U-Boot         (sector 0x4000)│
│ mmcblk0p2     │ misc.img     — Misc flags     (recovery etc) │
│ mmcblk0p3     │ boot.img     — Kernel + DTB   (sector 0x8000)│
│ mmcblk0p4     │ recovery.img — Recovery OS                   │
│ mmcblk0p5     │ backup.img   — Backup partition              │
│ mmcblk0p6     │ rootfs.img   — Root filesystem (sector 0x40000)│
│               │               ext4, resizable                │
└───────────────┴──────────────────────────────────────────────┘
```

**SD card mapping:**
- SD card = `/dev/mmcblk2` (eMMC = `/dev/mmcblk0`)
- Same 6-partition layout applies; partition 6 is rootfs on both

**Backup commands** (from wiki — proves partition layout):
```bash
sudo dd if=/dev/mmcblk0p1 of=uboot.img status=progress bs=1M
sudo dd if=/dev/mmcblk0p2 of=misc.img status=progress bs=1M
sudo dd if=/dev/mmcblk0p3 of=boot.img status=progress bs=1M
sudo dd if=/dev/mmcblk0p4 of=recovery.img status=progress bs=1M
sudo dd if=/dev/mmcblk0p5 of=backup.img status=progress bs=1M
sudo dd if=/dev/mmcblk0p6 of=rootfs.img status=progress bs=1M
sudo dd if=/dev/mmcblk0 of=gpt.img bs=512 count=64
sudo dd if=/dev/mmcblk0 of=bootloader.img bs=512 count=16320 skip=64
```

---

## Rockchip Boot Flow (5 Stages)

```
Stage 1: BootROM (in silicon)
    │
    ▼
Stage 2: IDBLoader (DDR init + SPL/miniloader)
    │   Source: rkbin → rv1126_ddr_924MHz_v1.14.bin
    │                  + rv1126_spl_v1.10.bin
    │   Written to: sector 0x40 (64)
    ▼
Stage 3: U-Boot + Trust (TEE/OP-TEE)
    │   U-Boot: uboot.img at sector 0x4000 (16384)
    │   Trust:  trust.img at sector 0x6000 (24576)
    │   TEE binary: rv1126_tee_ta_v2.16.bin
    ▼
Stage 4: Linux Kernel + DTB
    │   boot.img at sector 0x8000 (32768)
    │   Format: Android boot image (mkbootimg)
    │   Contains: zImage + RSCE resource image (rk-kernel.dtb)
    │   **NOT** FAT/extlinux — uses Android boot image header
    ▼
Stage 5: Root Filesystem
        rootfs.img at sector 0x40000 (262144)
        Ext4 filesystem with full Debian + Klipper stack
```

### Key rkbin Files for RV1126

From https://github.com/rockchip-linux/rkbin:

| File | Purpose |
|---|---|
| `rv1126_ddr_924MHz_v1.14.bin` | DDR3 initialization at 924 MHz |
| `rv1126_spl_v1.10.bin` | Secondary Program Loader |
| `rv1126_usbplug_v1.24.bin` | USB flashing mode plugin |
| `rv1126_tee_ta_v2.16.bin` | Trusted Execution Environment (OP-TEE) |
| `RKBOOT/RV1126MINIALL.ini` | Loader packaging config |
| `RKTRUST/RV1126TOS.ini` | Trust image packaging config |

**RV1126MINIALL.ini contents:**
```ini
[CHIP_NAME]
NAME=RV1126
[VERSION]
MAJOR=1
MINOR=5
[CODE471_OPTION]
NUM=1
Path1=bin/rv11/rv1126_ddr_924MHz_v1.14.bin
Sleep=1
[CODE472_OPTION]
NUM=1
Path1=bin/rv11/rv1126_usbplug_v1.24.bin
[LOADER_OPTION]
NUM=2
LOADER1=FlashData
LOADER2=FlashBoot
FlashData=bin/rv11/rv1126_ddr_924MHz_v1.14.bin
FlashBoot=bin/rv11/rv1126_spl_v1.10.bin
[OUTPUT]
PATH=rv1126_spl_loader_v1.14.110.bin
```

---

## Inferred Build Process

> **Important:** The build process is **NOT publicly documented**. Guilouz builds images privately. The following is reverse-engineered from partition analysis, Rockchip SDK documentation, changelogs, and release artifacts.

### Step 1: Cross-Compilation Environment

```
Host: Linux PC (likely x86_64)
Target: armhf (ARMv7, hard-float)
Toolchain: arm-linux-gnueabihf-gcc (GCC cross-compiler)
Build vars: ARCH=arm CROSS_COMPILE=arm-linux-gnueabihf-
```

### Step 2: Kernel Build

**Source:** Likely Rockchip BSP kernel fork (https://github.com/rockchip-linux/kernel) at version **6.1.99**, potentially with custom patches for:
- Full 1 GB RAM access (stock kernel limited to ~700 MB)
- RV1126 EVB DDR3 device tree with FLSUN S1 display/GPIO mappings
- ZRAM support enabled
- CPU frequency restored to 1.5 GHz (stock limited to 1.0 GHz in v1.0)

**Likely build commands:**
```bash
# Configure kernel for RV1126
make ARCH=arm rv1126_defconfig  # or custom defconfig
# Customize (enable ZRAM, adjust memory, etc.)
make ARCH=arm menuconfig
# Build
make ARCH=arm CROSS_COMPILE=arm-linux-gnueabihf- -j$(nproc) zImage dtbs
```

**Output:**
- `arch/arm/boot/zImage` — Compressed kernel
- `arch/arm/boot/dts/rockchip/rv1126-evb-ddr3-v1x.dtb` — Device tree blob (filename speculative)

**Packaging boot.img (CORRECTED — uses mkbootimg, not FAT/extlinux):**
```bash
# First, create the Rockchip Resource Image containing the DTB:
resource_tool --pack --image=resource.img rk-kernel.dtb

# Then pack kernel + resource image into Android boot image:
mkbootimg \
  --kernel zImage \
  --second resource.img \
  --base 0x10000000 \
  --kernel_offset 0x00008000 \
  --second_offset 0x00F00000 \
  --tags_offset 0x00000100 \
  --pagesize 2048 \
  --output boot.img
```

> **Actual findings (from image analysis):** boot.img is 9.61 MB, header version 0, no ramdisk, no cmdline. The zImage is 8.14 MB, the RSCE resource image is 1.50 MB containing a single DTB (`rk-kernel.dtb`, 119.6 KB). DTB model: `Rockchip RV1126 EVB DDR3 V2.3 FLSUN-OS mmc`, compatible includes `rockchip,rv1126-flsun`. See [09-image-reverse-engineering.md](09-image-reverse-engineering.md) for full details.

### Step 3: Root Filesystem Build

**Method:** **debos** (Debian OS builder by Collabora) — confirmed by ext4 `Last Mounted` path:
```
/home/pi/Bureau/flsun-os-venv-debian13/.debos-678795514/mnt
```

debos uses YAML recipes to automate `debootstrap` + package installation + file copying + script execution. The build was done on a French-locale Linux desktop ("Bureau" = Desktop folder).

The equivalent manual steps would be:
```bash
# Create Debian 13 Trixie armhf rootfs
debootstrap --arch=armhf --foreign trixie rootfs http://deb.debian.org/debian
# Second stage (run inside chroot or via QEMU user-mode emulation)
chroot rootfs /debootstrap/debootstrap --second-stage
```

**Customization (inside chroot or via scripts):**

1. **System Configuration**
   - Set hostname pattern: `FLSUN-S1-XXXX` (based on MAC address)
   - Create user `pi` with password `flsun`, root password `flsun`
   - Enable SSH server
   - Configure locale, timezone defaults
   - Install NetworkManager for WiFi management

2. **Python & Virtual Environments**
   - Python 3.13 (default in Debian 13 Trixie)
   - Create virtualenvs for Klipper, Moonraker, KlipperScreen

3. **Klipper Ecosystem Installation**
   ```bash
   # Klipper (forked)
   git clone https://github.com/Guilouz/Klipper-Flsun-S1 ~/klipper
   # Moonraker
   git clone https://github.com/Arksine/moonraker ~/moonraker
   # KlipperScreen (forked)
   git clone https://github.com/Guilouz/KlipperScreen-Flsun-S1 ~/KlipperScreen
   # Mainsail web UI
   # Fluidd web UI (pre-configured)
   # MJPG-Streamer
   # Kiauh
   # Klipper Print Time Estimator
   ```

4. **Custom FLSUN OS Components**
   - Easy Installer CLI tool (`~/flsun-os/system/`)
   - FLSUN OS Dependencies (Moonraker update_manager integration)
   - Boot logo ("Open Source Edition" splash image)
   - First-boot script (resizes rootfs partition, configures web interfaces, triggers reboot)
   - Power management (proper shutdown on power button, power loss recovery)

5. **Systemd Services**
   - `klipper.service`
   - `moonraker.service`
   - `KlipperScreen.service`
   - `mjpg-streamer.service` (camera)
   - First-boot oneshot service

6. **Klipper Configuration Files**
   - All config files from https://github.com/Guilouz/Klipper-Flsun-S1 `Configurations/` folder
   - Pre-configured for S1/S1 Pro with unified configs for all variants

**Packaging rootfs.img:**
```bash
# Calculate required size
SIZE=$(du -sm rootfs/ | awk '{print $1}')
# Create ext4 image with some extra space
dd if=/dev/zero of=rootfs.img bs=1M count=$((SIZE + 512))
mkfs.ext4 rootfs.img
mount rootfs.img /mnt/rootfs
cp -a rootfs/* /mnt/rootfs/
umount /mnt/rootfs
```

### Step 4: SD Card Image Assembly

```bash
# Create empty disk image (8 GB target, fits 8 GB eMMC)
dd if=/dev/zero of=FLSUN-OS-S1-SD-3.0.img bs=1M count=8192

# Write GPT partition table
# (using sgdisk, gdisk, or Rockchip parameter file via rkdeveloptool)
sgdisk -n 1:0x4000:+4M -t 1:8300 -c 1:uboot \
       -n 2:0:+1M -t 2:8300 -c 2:misc \
       -n 3:0x8000:+112M -t 3:8300 -c 3:boot \
       -n 4:0:+32M -t 4:8300 -c 4:recovery \
       -n 5:0:+32M -t 5:8300 -c 5:backup \
       -n 6:0x40000:0 -t 6:8300 -c 6:rootfs \
       FLSUN-OS-S1-SD-3.0.img

# Write bootloader components
dd if=idbloader.img of=FLSUN-OS-S1-SD-3.0.img seek=64 conv=notrunc
dd if=uboot.img of=FLSUN-OS-S1-SD-3.0.img seek=16384 conv=notrunc
dd if=trust.img of=FLSUN-OS-S1-SD-3.0.img seek=24576 conv=notrunc

# Write partition images
dd if=boot.img of=FLSUN-OS-S1-SD-3.0.img seek=32768 conv=notrunc
dd if=rootfs.img of=FLSUN-OS-S1-SD-3.0.img seek=262144 conv=notrunc

# Compress
gzip FLSUN-OS-S1-SD-3.0.img
```

### Step 5: eMMC Image Assembly

```bash
# Simply package boot.img + rootfs.img
7z a FLSUN-OS-S1-EMMC-3.0.7z boot.img rootfs.img
```

The eMMC variant only includes boot + rootfs because the bootloader (IDBLoader, U-Boot, Trust) is already present on the eMMC from the stock firmware or a previous FLSUN OS install.

---

## How to Reproduce (Theoretical Guide)

If you wanted to build a similar Debian-based OS image for the RV1126:

### Prerequisites
- Linux PC for cross-compilation
- `arm-linux-gnueabihf-gcc` cross-compiler toolchain
- `debootstrap`, `qemu-user-static` (for chroot into armhf rootfs)
- Rockchip rkbin binaries (for bootloader stages)
- Kernel source (Rockchip BSP kernel 6.1.x branch)
- Access to actual S1 hardware for testing

### High-Level Steps

1. **Clone rkbin** — get DDR init, SPL, TEE binaries for RV1126
2. **Build IDBLoader** — combine DDR + SPL: `mkimage -n rv1126 -T rksd -d rv1126_ddr.bin idbloader.img && cat rv1126_spl.bin >> idbloader.img`
3. **Build U-Boot** — from Rockchip U-Boot fork with RV1126 board config, or reuse stock U-Boot
4. **Build Trust** — package TEE with `tools/trustmerge`: `trustmerge RKTRUST/RV1126TOS.ini`
5. **Build Kernel** — configure for RV1126, compile zImage + DTB
6. **Package boot.img** — mkbootimg with zImage + RSCE resource image (DTB)
7. **Build rootfs** — debootstrap Debian 13 armhf, install Klipper stack
8. **Package rootfs.img** — ext4 image from rootfs directory
9. **Assemble full disk image** — GPT + bootloader + partition images
10. **Test on hardware** — flash SD card, boot, verify

### Alternative: Start from Stock Image

A simpler approach that Guilouz may use:

1. **Backup stock eMMC** (all partitions as documented in the wiki)
2. **Mount rootfs.img** on a Linux PC
3. **Replace the root filesystem** with a fresh Debian 13 debootstrap + Klipper stack
4. **Replace boot.img** with updated kernel
5. **Keep bootloader partitions** (uboot, trust, misc, recovery) from stock
6. **Repackage** as SD image (full disk) and eMMC image (boot + rootfs only)

This would explain why the eMMC image only contains boot.img + rootfs.img — the bootloader partitions are expected to already exist from the stock firmware.

---

## What Is NOT Public

| Item | Status |
|---|---|
| **debos YAML recipe** | **Not published** (confirmed debos is the build tool) |
| Kernel .config | **Not published** |
| Device Tree Source modifications | **Not published** (DTB analyzed — see doc 09) |
| Rootfs customization scripts | **Not published** (but many scripts recovered from image) |
| First-boot script | **Recovered from image** — see [09-image-reverse-engineering.md](09-image-reverse-engineering.md) |
| Easy Installer source code | **Recovered from image** — shell scripts in `~/flsun-os/installer/` |
| Boot.img structure | **Fully analyzed** — Android boot image, not FAT/extlinux |

Guilouz has not shared the image build toolchain. The FLSUN OS images are pre-built and distributed as binary releases only. The "Open Source Edition" name refers to the open-source **software stack** (Klipper, Moonraker, KlipperScreen) replacing FLSUN's proprietary AI features — not the build process itself.

---

## Key Rockchip Resources

| Resource | URL |
|---|---|
| rkbin (binary blobs) | https://github.com/rockchip-linux/rkbin |
| U-Boot fork | https://github.com/rockchip-linux/u-boot |
| Kernel fork | https://github.com/rockchip-linux/kernel |
| Rockchip Wiki — Boot Option | https://opensource.rock-chips.com/wiki_Boot_option |
| Rockchip Wiki — Partitions | https://opensource.rock-chips.com/wiki_Partitions |
| Rockchip Wiki — Distributions | https://opensource.rock-chips.com/wiki_Distribution |
| RKDevTool (Windows) | Distributed with FLSUN OS wiki |
| rkdeveloptool (Linux, open source) | https://github.com/rockchip-linux/rkdeveloptool |
| Stock eMMC backup (v1.0.6.4) | https://drive.google.com/file/d/14JhpC56aXe_kKlerZf43JvFv31ULlQqN |

---

## Open Questions (Updated)

1. ~~**Which kernel source tree does Guilouz use?**~~ — Rockchip BSP kernel v6.1.99. DTB compatible: `rockchip,rv1126-evb-ddr3-v13`, model: `RV1126 EVB DDR3 V2.3 FLSUN-OS mmc`. Source tree not published.
2. ~~**What DTS modifications are needed?**~~ — Custom `rockchip,rv1126-flsun` compatible added. Board model string includes "FLSUN-OS mmc". Actual DTS source not public.
3. ~~**How does the first-boot script work?**~~ — **ANSWERED:** Script at `/etc/init.d/first-boot.sh`, called from `rc.local`. Resizes rootfs (sgdisk+parted+resize2fs), sets hostname from MAC, regenerates SSH keys, creates symlinks, restores Mainsail/Fluidd configs via Moonraker API, adds ZRAM swap, self-removes from rc.local, reboots. See doc 09 for full script.
4. ~~**Is Armbian involved?**~~ — **No.** Build tool is **debos** (confirmed from ext4 metadata).
5. **Could the image be built with Docker/QEMU?** — debos natively supports Docker/QEMU backends, so this is likely how the cross-architecture build works.
6. **Boot logo customization** — Still unknown. May be a U-Boot splash or fbcon logo. Not investigated.
7. **debos recipe** — The exact YAML recipe is not published. Could potentially be reconstructed from the filesystem analysis in doc 09.
