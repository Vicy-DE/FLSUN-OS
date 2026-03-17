# Rebuilding the FLSUN OS Kernel from Source

**Date researched:** 2026-03-16
**Sources:**
- Guilouz confirmation (Discussion #13): https://github.com/Guilouz/FLSUN-S1-Open-Source-Edition/discussions/13
- Kernel repo: https://github.com/armbian/linux-rockchip (branch `rk-6.1-rkr5.1`)
- Extracted FLSUN OS 3.0 kernel config: `resources/S1/firmwares/os-images/FLSUN-OS-S1-EMMC-3.0/extracted/kernel-config.txt`
- Rockchip rkbin tools: https://github.com/rockchip-linux/rkbin
- Existing research: `docs/S1/research/11-kernel-devicetree-analysis.md`, `docs/T1/research/03-kernel-build-and-display-drivers.md`

---

## 1. Kernel Source — Confirmed by Guilouz

Guilouz confirmed the kernel source repository in [Discussion #13](https://github.com/Guilouz/FLSUN-S1-Open-Source-Edition/discussions/13) (2026-03-16):

> "We use this kernel: https://github.com/armbian/linux-rockchip"

This is the **Armbian fork of the Rockchip BSP kernel**, not the upstream `rockchip-linux/kernel` repo. The Armbian fork includes additional board support patches and Armbian-specific fixes on top of the Rockchip BSP tree.

| Property | Value |
|---|---|
| Repository | `armbian/linux-rockchip` |
| Branch | `rk-6.1-rkr5.1` (default) |
| Current version | **6.1.115** (VERSION=6, PATCHLEVEL=1, SUBLEVEL=115) |
| FLSUN OS 3.0 version | **6.1.99** (16 stable patches behind HEAD) |
| Architecture | `arm` (ARMv7 Cortex-A7) |
| Base defconfig | `arch/arm/configs/rv1126_defconfig` |
| Local clone | `kernel/` (git submodule) |

### Previous Assumption Was Wrong

Earlier research assumed the kernel came from `rockchip-linux/kernel` branch `develop-6.1`. The Armbian fork (`armbian/linux-rockchip`) is a separate downstream fork with its own patches. Both originate from Rockchip's BSP but diverge in maintenance.

### Version Discrepancy

The Armbian repo HEAD is at 6.1.115 while FLSUN OS 3.0 uses 6.1.99. Possible explanations:
1. Guilouz used an older commit of the Armbian repo (version 6.1.99)
2. Guilouz manually set SUBLEVEL=99 in the Makefile
3. Both kernel trees share the same Rockchip BSP base and Guilouz used `rockchip-linux/kernel` for the initial build, then switched to Armbian's fork

The FLSUN OS 3.0 kernel version string `6.1.99flsun OS` has `CONFIG_LOCALVERSION=""` (empty), meaning the `flsun OS` suffix was patched directly into the version string, likely by editing the Makefile.

---

## 2. Repository Cloned as Submodule

The kernel source is available as a git submodule at `kernel/`:

```bash
git submodule add --depth 1 -b rk-6.1-rkr5.1 \
    https://github.com/armbian/linux-rockchip.git kernel
```

After cloning, initialize with:

```bash
git submodule update --init --depth 1 kernel
```

---

## 3. FLSUN OS 3.0 Kernel — Facts from Reverse Engineering

These facts are extracted from the FLSUN OS 3.0 boot.img analysis (see `docs/S1/research/11-kernel-devicetree-analysis.md`):

### Version String

```
Linux version 6.1.99flsun OS (root@FLSUN-OS)
  (arm-linux-gnueabihf-gcc (Ubuntu 11.4.0-1ubuntu1~22.04) 11.4.0,
   GNU ld (GNU Binutils for Ubuntu) 2.38)
  #38 SMP PREEMPT Mon Mar 31 20:03:38 CEST 2025
```

### Key Build Properties

| Property | Value |
|---|---|
| Kernel version | 6.1.99 |
| Local version suffix | `flsun OS` |
| Build number | #38 |
| Preemption | Full `CONFIG_PREEMPT=y` |
| SMP | Yes (4 cores) |
| Build date | 2025-03-31 20:03:38 CEST |
| Build host | `root@FLSUN-OS` |
| Cross-compiler | `arm-linux-gnueabihf-gcc` 11.4.0 (Ubuntu 22.04) |
| Linker | GNU ld 2.38 |
| zImage size | 8,531,192 bytes (8.14 MB) |
| Decompressed size | 20,654,540 bytes (19.70 MB) |
| Compression | gzip |
| Modules | **Zero** — fully monolithic (1,277 built-in, 0 modules) |
| Embedded config | Yes (`CONFIG_IKCONFIG=y`, extractable at `/proc/config.gz`) |

### Config Statistics

| Metric | Count |
|---|---|
| Built-in (`=y`) | 1,277 |
| Module (`=m`) | 0 |
| Disabled (`# ... is not set`) | 3,525 |
| Total config lines | 6,529 |

---

## 4. Build Environment Setup

### Ubuntu 22.04 (Matches FLSUN OS Build)

The FLSUN OS 3.0 kernel was built on Ubuntu 22.04 with GCC 11.4.0. To reproduce the exact build environment:

```bash
# Use Ubuntu 22.04 (native, Docker, or WSL2)
sudo apt update
sudo apt install -y \
    build-essential \
    gcc-arm-linux-gnueabihf \
    bc flex bison \
    libssl-dev libncurses-dev \
    lz4 gzip xz-utils \
    git
```

| Tool | Version | Package |
|---|---|---|
| `arm-linux-gnueabihf-gcc` | 11.4.0 | `gcc-arm-linux-gnueabihf` |
| `arm-linux-gnueabihf-ld` | 2.38 | `binutils-arm-linux-gnueabihf` |
| `bc` | any | `bc` |
| `flex` | any | `flex` |
| `bison` | any | `bison` |
| `openssl` | any | `libssl-dev` |
| `ncurses` | any | `libncurses-dev` (for `menuconfig`) |

### Docker (Recommended for Reproducibility)

```bash
docker run --rm -it -v $(pwd):/build ubuntu:22.04 bash
# Inside container:
apt update && apt install -y build-essential gcc-arm-linux-gnueabihf \
    bc flex bison libssl-dev libncurses-dev lz4 gzip xz-utils git
cd /build/kernel
```

---

## 5. Kernel Config Strategy

### Rockchip Config Fragment System

The Rockchip BSP kernel uses a base defconfig plus optional config fragment overlays:

| Config | Path | Purpose |
|---|---|---|
| **Base defconfig** | `arch/arm/configs/rv1126_defconfig` | Core RV1126/RV1109 settings |
| EVB fragment | `arch/arm/configs/rv1126-evb.config` | EVB board additions (WiFi, cameras, touchscreen) |
| eMMC built-in | `arch/arm/configs/rv1126-emmc-drivers-builtin.config` | Makes drivers built-in for eMMC boot |
| Battery | `arch/arm/configs/rv1126-battery.config` | Battery-powered device features |
| Facial gate | `arch/arm/configs/rv1126-facial-gate.config` | Facial recognition features |
| SPI NOR | `arch/arm/configs/rv1126-spi-nor.config` | SPI NOR flash boot |
| Thunder boot | `arch/arm/configs/rv1126-tb.config` | Fast boot (thunder boot) |

Fragments are applied using `scripts/kconfig/merge_config.sh`:

```bash
make ARCH=arm rv1126_defconfig
./scripts/kconfig/merge_config.sh -m .config \
    arch/arm/configs/rv1126-evb.config \
    arch/arm/configs/rv1126-emmc-drivers-builtin.config
make ARCH=arm olddefconfig
```

### Warning: rv1126-emmc-drivers-builtin.config Disables Display

The `rv1126-emmc-drivers-builtin.config` fragment **disables display drivers** needed by FLSUN printers:

```kconfig
# CONFIG_ROCKCHIP_DW_MIPI_DSI is not set
# CONFIG_ROCKCHIP_RGB is not set        ← BREAKS S1/T1 DISPLAY
# CONFIG_BACKLIGHT_LCD_SUPPORT is not set
# CONFIG_INPUT_TOUCHSCREEN is not set
```

The FLSUN S1 and T1 both use `CONFIG_ROCKCHIP_RGB=y` (RGB parallel interface). If using this fragment, the display settings **must be re-enabled** afterward.

### FLSUN OS Config — Use the Extracted Full Config

The most reliable approach is to use the extracted kernel config from FLSUN OS 3.0 as a complete defconfig. This avoids fragment compatibility issues:

```bash
# Copy the extracted config as a defconfig
cp /path/to/kernel-config.txt arch/arm/configs/flsun_s1_defconfig

# Apply it
make ARCH=arm flsun_s1_defconfig
```

The extracted config is at: `resources/S1/firmwares/os-images/FLSUN-OS-S1-EMMC-3.0/extracted/kernel-config.txt`

---

## 6. FLSUN OS Kernel — Key Differences from Stock rv1126_defconfig

The FLSUN OS 3.0 kernel has these significant customizations compared to the stock `rv1126_defconfig`:

| Setting | Stock rv1126_defconfig | FLSUN OS 3.0 |
|---|---|---|
| Modules | Many `=m` | **All `=y`** — zero loadable modules |
| Kernel compression | `CONFIG_KERNEL_LZ4=y` | `CONFIG_KERNEL_GZIP=y` |
| CAN bus | Not in base | **Full CAN stack** (CAN, CAN_RAW, CAN_ROCKCHIP, CANFD_ROCKCHIP, CAN_GS_USB, CAN_SLCAN, etc.) |
| IKCONFIG | Not enabled | `CONFIG_IKCONFIG=y` + `CONFIG_IKCONFIG_PROC=y` |
| CAN-FD | Not in base | `CONFIG_CANFD_ROCKCHIP=y` |
| USB gadgets | Basic | Full ConfigFS (RNDIS, mass storage, UVC) |
| WiFi driver | `BCMDHD` | `CONFIG_BCMDHD=y` (built-in, not module) |
| Local version | Empty | `flsun OS` (patched in Makefile) |
| Preemption | `CONFIG_PREEMPT=y` | `CONFIG_PREEMPT=y` (same) |
| Timer tick | `CONFIG_HZ=300` | `CONFIG_HZ=300` (same) |

### Why Fully Monolithic (No Modules)?

The FLSUN OS kernel has zero loadable modules (`=m` count is 0). This is intentional:
1. **Simpler rootfs** — no `/lib/modules/$(uname -r)/` directory needed
2. **Faster boot** — no module loading at startup
3. **More reliable** — no missing module dependencies
4. **Single exception:** `galcore.ko` (Vivante NPU driver) is loaded from `/lib/modules/galcore.ko` at boot by `/etc/init.d/S60NPU_init`, but this module ships on the rootfs — it's not built with the kernel

---

## 7. Build Commands — Step by Step

### Step 1: Enter the Kernel Source

```bash
cd kernel    # or the cloned linux-rockchip directory
```

### Step 2: Configure

**Option A — Use the FLSUN OS 3.0 config (exact reproduction):**

```bash
cp ../resources/S1/firmwares/os-images/FLSUN-OS-S1-EMMC-3.0/extracted/kernel-config.txt \
    arch/arm/configs/flsun_s1_defconfig
make ARCH=arm flsun_s1_defconfig
```

**Option B — Build from stock defconfig + fragments + customization:**

```bash
make ARCH=arm rv1126_defconfig
./scripts/kconfig/merge_config.sh -m .config \
    arch/arm/configs/rv1126-evb.config
make ARCH=arm olddefconfig

# Then customize interactively
make ARCH=arm menuconfig
# Key changes:
#   - Set all =m to =y (General Setup → Module Support → disable)
#   - Enable CONFIG_CAN=y and full CAN stack
#   - Ensure CONFIG_ROCKCHIP_RGB=y
#   - Ensure CONFIG_DRM_PANEL_SIMPLE=y
#   - Enable CONFIG_IKCONFIG=y and CONFIG_IKCONFIG_PROC=y
#   - Set CONFIG_PREEMPT=y (Processor type → Preemption Model)
#   - Set CONFIG_HZ_300=y (Processor type → Timer frequency)
```

### Step 3: Set Version String (Optional)

To reproduce the `flsun OS` version suffix, edit `Makefile`:

```makefile
VERSION = 6
PATCHLEVEL = 1
SUBLEVEL = 99
EXTRAVERSION =
NAME = Curry Ramen
```

The `flsun OS` suffix in the version string is added by modifying `/include/generated/compile.h` or the Makefile. The exact mechanism used by Guilouz is unknown, but setting `CONFIG_LOCALVERSION=" OS"` and having a build on a machine named `FLSUN-OS` would approximate it.

### Step 4: Compile

```bash
make ARCH=arm CROSS_COMPILE=arm-linux-gnueabihf- -j$(nproc) zImage dtbs
```

**Output files:**

| File | Path | Description |
|---|---|---|
| zImage | `arch/arm/boot/zImage` | Compressed kernel (~8.1 MB) |
| DTB (EVB v13) | `arch/arm/boot/dts/rv1126-evb-ddr3-v13.dtb` | Stock EVB device tree |

### Step 5: Use Custom Device Tree (FLSUN S1)

The FLSUN S1 uses a custom device tree not present in the upstream kernel. The extracted DTB is at `resources/S1/firmwares/os-images/FLSUN-OS-S1-EMMC-3.0/extracted/rk-kernel.dtb` (and decompiled DTS at `rk-kernel.dts`).

To build with the custom DTS:

```bash
# Copy the FLSUN S1 DTS into the kernel tree
cp ../resources/S1/firmwares/os-images/FLSUN-OS-S1-EMMC-3.0/extracted/rk-kernel.dts \
    arch/arm/boot/dts/rv1126-flsun-s1.dts

# Add to DTS Makefile (append to the rv1126 entries)
echo 'dtb-$(CONFIG_ARCH_ROCKCHIP) += rv1126-flsun-s1.dtb' >> arch/arm/boot/dts/Makefile

# Rebuild DTBs
make ARCH=arm CROSS_COMPILE=arm-linux-gnueabihf- dtbs
```

> **Note:** The extracted DTS may need adjustment to compile against the Armbian kernel headers (the DTS was decompiled from a binary DTB and may use absolute phandle references instead of label-based ones). See section 10 for DTB handling alternatives.

---

## 8. Packaging into boot.img

The Rockchip RV1126 boots from an Android-format boot.img containing the zImage and DTB. Two additional tools are needed.

### Required Tools

| Tool | Source | Purpose |
|---|---|---|
| `resource_tool` | [rockchip-linux/rkbin](https://github.com/rockchip-linux/rkbin) | Pack DTB into Rockchip Resource Image (RSCE) |
| `mkbootimg` | Android SDK or [nicholasgasior/mkbootimg](https://github.com/nicholasgasior/mkbootimg) | Create Android boot image |

### Step 6: Create RSCE Resource Image

```bash
# Clone rkbin (for resource_tool)
git clone --depth 1 https://github.com/rockchip-linux/rkbin.git

# Pack the DTB into a Rockchip Resource Image
cp arch/arm/boot/dts/rv1126-flsun-s1.dtb rk-kernel.dtb
rkbin/tools/resource_tool --pack --image=resource.img rk-kernel.dtb
```

### Step 7: Build boot.img

```bash
mkbootimg \
    --kernel arch/arm/boot/zImage \
    --ramdisk /dev/null \
    --second resource.img \
    --base 0x62000000 \
    --kernel_offset 0x00008000 \
    --ramdisk_offset 0x04000000 \
    --second_offset 0x04100000 \
    --tags_offset 0x00000100 \
    --pagesize 2048 \
    --cmdline "storagemedia=emmc androidboot.storagemedia=emmc androidboot.mode=normal" \
    --output boot.img
```

These offsets match the FLSUN OS 3.0 boot.img format documented in `docs/S1/research/09-image-reverse-engineering.md`:

| Parameter | Value | Address |
|---|---|---|
| Base | `0x62000000` | — |
| Kernel offset | `0x00008000` | Load at `0x62008000` |
| Ramdisk offset | `0x04000000` | Load at `0x66000000` (empty) |
| Second offset | `0x04100000` | Load at `0x66100000` (RSCE with DTB) |
| Tags offset | `0x00000100` | Tags at `0x62000100` |
| Page size | `2048` | — |

### Alternative: Use Existing Build Scripts

The project includes build scripts that automate this process:

```bash
# S1 boot.img packaging
./build/build-boot-img.sh arch/arm/boot/zImage rk-kernel.dtb

# T1 boot.img packaging (uses Python, no external dependencies)
python3 build/tools/build-boot-img-t1.py
```

---

## 9. Flashing the Kernel

### Method 1: eMMC via RKDevTool (Windows)

1. Connect USB-C to the S1 core board
2. Enter Loader mode (hold BOOT9200 → press/release BOOT2100 → release BOOT9200)
3. In RKDevTool v2.96: click "Write by Address"
   - boot partition: address `0x8000`, file: `boot.img`
4. Click "Run"

### Method 2: SD Card (Non-Destructive)

Write `boot.img` to partition 3 of the SD card:

```bash
sudo dd if=boot.img of=/dev/mmcblk2p3 bs=1M status=progress
```

### Method 3: Over SSH (Running System)

```bash
# Backup current boot
sudo dd if=/dev/mmcblk0p3 of=/tmp/boot-backup.img bs=1M
# Flash new boot
sudo dd if=boot.img of=/dev/mmcblk0p3 bs=1M status=progress
sudo sync
sudo reboot
```

---

## 10. DTB Handling — Compile vs Reuse

There are two approaches for the device tree:

### Approach A: Reuse the Extracted DTB (Simplest)

Use the pre-built DTB from FLSUN OS 3.0 without recompilation:

```bash
# The DTB is already at:
# resources/S1/firmwares/os-images/FLSUN-OS-S1-EMMC-3.0/extracted/rk-kernel.dtb

# Package directly with mkbootimg
cp resources/S1/firmwares/os-images/FLSUN-OS-S1-EMMC-3.0/extracted/rk-kernel.dtb .
```

This is the safest approach — the DTB is known-good and matches the S1 hardware exactly. The only downside is that DTB changes (e.g., for the T1 display) require binary patching rather than source editing.

### Approach B: Compile DTB from DTS Source (Flexible)

The decompiled DTS (`rk-kernel.dts`) can be edited and recompiled:

```bash
# Compile with the standalone device tree compiler
dtc -I dts -O dtb -o rk-kernel.dtb rk-kernel.dts

# Or compile from the kernel tree (handles includes correctly)
make ARCH=arm CROSS_COMPILE=arm-linux-gnueabihf- \
    arch/arm/boot/dts/rv1126-flsun-s1.dtb
```

> **Caveat:** Decompiled DTS uses numeric phandle references instead of symbolic labels. It compiles fine with `dtc` but may not compile with the kernel build system if it expects standard DTS includes. The FLSUN custom DTS was not found in any public kernel tree — Guilouz appears to have a private/custom DTS file.

### Approach C: Patch the DTB Programmatically (T1 Workflow)

For the T1 project, the `build/tools/patch-dtb-for-t1.py` script patches the S1 DTB binary to change display timings without needing the DTS source:

```bash
python3 build/tools/patch-dtb-for-t1.py
```

---

## 11. Available DTS Files in the Kernel Tree

The `arch/arm/boot/dts/Makefile` lists these RV1126 device tree files:

| DTB | Description |
|---|---|
| `rv1126-evb-ddr3-v10.dtb` | EVB board DDR3 version 1.0 |
| `rv1126-evb-ddr3-v12.dtb` | EVB board DDR3 version 1.2 |
| `rv1126-evb-ddr3-v12-spi-nand.dtb` | EVB v1.2 with SPI NAND |
| `rv1126-evb-ddr3-v12-spi-nor.dtb` | EVB v1.2 with SPI NOR |
| `rv1126-evb-ddr3-v13.dtb` | EVB board DDR3 version 1.3 |

> **None of these are the FLSUN S1 DTS.** The FLSUN S1 uses a custom device tree with model string `Rockchip RV1126 EVB DDR3 V2.3 FLSUN-OS mmc` and compatible strings `rockchip,rv1126-evb-ddr3-v13`, `rockchip,rv1126`, `rockchip,rv1126-flsun`. This custom DTS is not published in any public repository.

---

## 12. Complete Build Workflow Summary

```
┌─────────────────────────────────────────────────────────────────┐
│                    KERNEL BUILD PIPELINE                         │
│                                                                  │
│  1. Source ──────────────────────────────────────────────────     │
│     git clone -b rk-6.1-rkr5.1 --depth 1                        │
│       https://github.com/armbian/linux-rockchip.git              │
│                          │                                       │
│  2. Configure ──────────────────────────────────────────────     │
│     Option A: cp kernel-config.txt arch/arm/configs/flsun_s1_defconfig  │
│               make ARCH=arm flsun_s1_defconfig                   │
│     Option B: make ARCH=arm rv1126_defconfig                     │
│               merge_config.sh + menuconfig                       │
│                          │                                       │
│  3. Compile ────────────────────────────────────────────────     │
│     make ARCH=arm CROSS_COMPILE=arm-linux-gnueabihf-             │
│       -j$(nproc) zImage dtbs                                     │
│                          │                                       │
│     ┌────────────────────┼────────────────────┐                  │
│     ▼                    ▼                    ▼                  │
│   zImage          rv1126-*.dtb        (or reuse stock DTB)       │
│     │                    │                                       │
│  4. Package DTB ────────────────────────────────────────────     │
│     resource_tool --pack --image=resource.img rk-kernel.dtb      │
│                          │                                       │
│  5. Create boot.img ────────────────────────────────────────     │
│     mkbootimg --kernel zImage --second resource.img              │
│       --base 0x62000000 --pagesize 2048 ...                      │
│                          │                                       │
│  6. Flash ──────────────────────────────────────────────────     │
│     RKDevTool (eMMC) │ SD card (dd) │ SSH (dd)                   │
└─────────────────────────────────────────────────────────────────┘
```

---

## 13. Open Questions

1. **Exact source commit:** Which commit of `armbian/linux-rockchip` did Guilouz use for version 6.1.99? The current HEAD is 6.1.115. If he used the Armbian repo, there should be a commit at v6.1.99. Alternatively, he may have used `rockchip-linux/kernel` (branch `develop-6.1`) and reported incorrectly.

2. **Custom DTS source:** Guilouz's custom device tree (`rv1126-flsun-s1.dts`) is not published. The decompiled version works for binary reuse but is not ideal for modification. A proper DTS file would need to be written based on the decompiled output and standard Rockchip DTS conventions.

3. **galcore.ko module:** The NPU driver module is shipped on the rootfs at `/lib/modules/galcore.ko`. Where is this built from? It appears to be a proprietary Vivante GPU driver — source may be in the Rockchip SDK (not public) or an Armbian package.

4. **WiFi firmware paths:** The `rv1126-evb.config` fragment sets WiFi firmware paths to `/vendor/etc/firmware/` (Android convention). FLSUN OS uses `/lib/firmware/`. The kernel config option `CONFIG_BCMDHD_FW_PATH` may need adjustment when building from source.

5. **Version string mechanism:** How exactly does the `flsun OS` suffix get into the kernel version string? `CONFIG_LOCALVERSION=""` is empty. It could be a direct Makefile edit or a custom build script.
