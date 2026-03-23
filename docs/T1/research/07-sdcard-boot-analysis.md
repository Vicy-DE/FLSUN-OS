# SD Card Boot Mechanism & Docker Build System

**Date researched:** 2025-07-13  
**Sources:**
- `docs/S1/research/08-os-image-build-process.md` — SD card image assembly process
- `docs/S1/research/09-image-reverse-engineering.md` — boot.img binary analysis
- `docs/T1/research/06-partition-layout-and-kernel-flashing.md` — T1 partition layout
- Rockchip Boot Option wiki: https://opensource.rock-chips.com/wiki_Boot_option
- Rockchip partitions wiki: https://opensource.rock-chips.com/wiki_Partitions
- FLSUN OS S1 SD image analysis (GPT partition table and bootloader offsets)
- T1 stock eMMC dumps in `resources/T1/firmwares/stock/`

---

## 1. Why the S1 Auto-Boots from SD Card

The FLSUN S1 boots from an SD card automatically — with no buttons, no menus, and no eMMC modification. Removing the SD card restores the original eMMC boot. This section explains exactly why.

### 1.1 The SD Card Image Is a Complete Bootable Disk

The S1 SD card image (`FLSUN-OS-S1-SD-3.0.img.gz`) is **not** just a rootfs or a kernel — it is a complete GPT disk image containing its **own** bootloader chain:

```
FLSUN-OS-S1-SD-3.0.img layout:
┌─────────────────────────────────────────────────────────────────┐
│ LBA 0-63        GPT partition table (32 KB)                     │
├─────────────────────────────────────────────────────────────────┤
│ LBA 64-16383    IDBLoader (DDR init + SPL)  ← THE KEY PART     │
│                 ~3.5 MB, Rockchip miniloader binary             │
├─────────────────────────────────────────────────────────────────┤
│ p1 (0x4000)     U-Boot (4 MB)                                   │
├─────────────────────────────────────────────────────────────────┤
│ (0x6000)        Trust / OP-TEE (between p1 and p2)              │
├─────────────────────────────────────────────────────────────────┤
│ p2              misc (recovery flags)                            │
├─────────────────────────────────────────────────────────────────┤
│ p3 (0x8000)     boot.img (kernel + DTB, Android format, ~10 MB) │
├─────────────────────────────────────────────────────────────────┤
│ p4              recovery                                         │
├─────────────────────────────────────────────────────────────────┤
│ p5              backup                                           │
├─────────────────────────────────────────────────────────────────┤
│ p6 (0x40000)    rootfs (ext4, fills remaining space)            │
└─────────────────────────────────────────────────────────────────┘
```

This is the exact same structure as the eMMC — a self-contained, independently bootable disk.

### 1.2 Rockchip BootROM Prioritizes SD Over eMMC

The Rockchip RV1126 SoC has a mask ROM burned into silicon that executes on every power-on. This BootROM scans storage devices in a **fixed priority order**:

```
BootROM scan order (RV1126):
  1. SPI NOR Flash
  2. SPI NAND Flash
  3. SD/MMC Card (SDMMC)    ← SD card checked HERE
  4. eMMC                   ← eMMC checked AFTER SD
  5. USB (Maskrom mode — fallback when nothing boots)
```

The BootROM looks for a valid **IDBLoader** signature at sector 64 (LBA 64) on each device. When it finds one on the SD card, it loads the DDR initialization code and SPL from the SD card, which then chain-loads U-Boot from the SD card, which then loads boot.img from the SD card, which mounts rootfs from the SD card.

**The eMMC is never consulted.** The entire boot chain runs from the SD card.

### 1.3 Why Removing the SD Card Reverts to eMMC

When the SD card is removed:
1. BootROM scans SPI NOR/NAND — nothing found (not present on S1/T1)
2. BootROM scans SD card — nothing found (card removed)
3. BootROM scans eMMC — finds valid IDBLoader at sector 64
4. Full eMMC boot chain executes — stock firmware loads normally

The eMMC is completely untouched. This is what makes SD card boot "non-destructive."

### 1.4 Root Filesystem Addressing

The rootfs uses `PARTUUID=614e0000-0000` in the kernel cmdline (or `/dev/root` in fstab), which resolves to partition 6 on whichever disk the kernel booted from. This means the same boot.img works on both SD (`/dev/mmcblk2p6`) and eMMC (`/dev/mmcblk0p6`).

The boot.img cmdline contains `storagemedia=emmc` even for the SD image — this tells Rockchip user-space tools which media to manage, but does not affect the actual boot device selection (that's handled by BootROM).

---

## 2. Why the T1 Requires Button Presses

The "button presses" required for the T1 are **NOT for SD card boot**. They are for **Maskrom mode** — a USB recovery mechanism built into the Rockchip SoC.

### 2.1 No SD Card Image Exists for the T1

Nobody has built an SD card image for the T1. The T1 port of FLSUN-OS is installed via:
1. **Maskrom mode** — USB-C flashing with RKDevTool (requires button combo)
2. **Direct dd** — Writing boot.img to eMMC boot partition over SSH
3. **`flsun_kernel_write`** — Stock tool that writes to eMMC boot partition

All three methods write to the eMMC. There is no SD boot option currently available.

### 2.2 Maskrom Mode Button Sequence

To enter Maskrom mode on the T1's RV1109 SoC board:
1. Power off the printer
2. Hold the **BOOT9200** button on the core board
3. Connect USB-C cable (or press/release **BOOT2100**)
4. Release BOOT9200
5. RKDevTool detects the device in "Maskrom" mode

In Maskrom mode, the BootROM exposes the eMMC as a USB mass storage device. RKDevTool can then write partition images (boot.img, rootfs.img) directly to specific eMMC sector offsets.

### 2.3 T1 SD Card Boot — Unknown but Likely Possible

The T1 uses a Rockchip **RV1109** SoC (same die family as the S1's RV1126). The RV1109 BootROM almost certainly has the same storage scan priority: SD before eMMC.

**What would be needed to boot the T1 from SD card:**

1. **Extract bootloader binaries from the T1 stock eMMC dump:**
   ```bash
   # Decompress the full eMMC dump:
   gunzip -k resources/T1/firmwares/stock/1097_0.img.gz

   # Extract IDBLoader (raw area, sectors 64-16383):
   dd if=1097_0.img of=idbloader.img bs=512 skip=64 count=16320

   # The U-Boot partition:
   # Already available as 1097_0p1.img (4 MB, U-Boot FIT)

   # Trust / OP-TEE:
   # May be embedded within p1 (U-Boot FIT includes OP-TEE on T1)
   # or at sector 0x6000 in the raw dump
   dd if=1097_0.img of=trust.img bs=512 skip=24576 count=8192
   ```

2. **Assemble a complete SD card image** with the bootloader chain + T1 boot.img + rootfs

3. **Test on hardware** — verify the RV1109 BootROM picks up the SD card's IDBLoader

### 2.4 Key Difference: T1 U-Boot FIT vs S1 Android Boot

| Aspect | S1 (RV1126) | T1 (RV1109) |
|---|---|---|
| Stock boot format | Android boot (`ANDROID!`) | U-Boot FIT (`D00DFEED`) |
| FLSUN-OS boot format | Android boot | Android boot (T1 U-Boot accepts both) |
| IDBLoader | At sector 64, standard Rockchip | At sector 64, standard Rockchip |
| U-Boot partition (p1) | U-Boot binary | U-Boot FIT (includes OP-TEE + DTB) |
| boot0/boot1 hardware partitions | Unknown | Empty (all zeros) |
| SD card boot tested? | **Yes — official image exists** | **No — never tested** |

---

## 3. T1 Bootloader Analysis

The T1 stock eMMC dump (`1097_0.img`, ~8 GB decompressed from `1097_0.img.gz`) contains the complete boot chain.

### 3.1 eMMC Hardware Partitions

| Region | File | Contents |
|---|---|---|
| boot0 | `1097_0boot0.img` | Empty (all zeros), 4 MB |
| boot1 | `1097_0boot1.img` | Empty (all zeros), 4 MB |
| User area | `1097_0.img` | GPT disk with IDBLoader + 6 partitions |

The empty boot0/boot1 partitions mean the T1's IDBLoader is in the **main user area** at sector 64, same as the S1.

### 3.2 U-Boot Partition (p1) — FIT Format

The T1's U-Boot partition (`1097_0p1.img`, 1.17 MB compressed, 4 MB decompressed) uses U-Boot FIT format (`D00DFEED` magic). This is different from the S1 which uses a raw U-Boot binary.

The FIT U-Boot image bundles:
- U-Boot proper
- OP-TEE (Trust firmware)
- A DTB for U-Boot itself

This means the "trust" firmware is **inside** the U-Boot partition on the T1, not at a separate sector offset. For SD card image assembly, writing `1097_0p1.img` to the uboot partition covers both U-Boot and Trust.

---

## 4. Docker Build System

The project provides Docker containers for reproducible builds. All Dockerfiles use the workspace root (`FLSUN-OS/`) as the build context.

### 4.1 Architecture

```
┌────────────────────────────────────────────────────────────────────┐
│                      Docker Build Pipeline                         │
│                                                                    │
│  ┌─────────────────────┐    ┌─────────────────────┐               │
│  │  Dockerfile.kernel   │    │  godebos/debos       │               │
│  │  flsun-kernel-builder│    │  (pre-built image)   │               │
│  │                      │    │                      │               │
│  │  Input:              │    │  Input:              │               │
│  │    kernel-config.txt │    │    flsun-os.yaml     │               │
│  │    rk-kernel.dtb     │    │    flsun-os-t1.yaml  │               │
│  │                      │    │    overlays/         │               │
│  │  Output:             │    │    overlays-t1/      │               │
│  │    zImage            │    │                      │               │
│  │    rk-kernel.dtb     │    │  Output:             │               │
│  │    boot.img          │    │    rootfs.img         │               │
│  └──────────┬───────────┘    └──────────┬───────────┘               │
│             │                           │                           │
│             └─────────┬─────────────────┘                           │
│                       ▼                                             │
│             ┌─────────────────────┐                                 │
│             │  Dockerfile.sdcard   │                                │
│             │  flsun-sdcard-builder│                                │
│             │                      │                                │
│             │  Input:              │                                │
│             │    boot.img          │                                │
│             │    rootfs.img        │                                │
│             │    idbloader.img     │ ← from stock firmware          │
│             │    uboot.img         │                                │
│             │    trust.img         │                                │
│             │                      │                                │
│             │  Output:             │                                │
│             │    FLSUN-OS-XX-SD.img│                                │
│             │    FLSUN-OS-XX-SD.img.gz                              │
│             └──────────────────────┘                                │
└────────────────────────────────────────────────────────────────────┘
```

### 4.2 Docker Images

| Image | Dockerfile | Purpose | Base |
|---|---|---|---|
| `flsun-kernel-builder` | `Dockerfile.kernel` | Cross-compile kernel, build boot.img | `debian:trixie-slim` |
| `godebos/debos` | (pre-built) | Build rootfs.img from debos recipe | Upstream |
| `flsun-sdcard-builder` | `Dockerfile.sdcard` | Assemble SD card image from components | `debian:trixie-slim` |

### 4.3 Docker Compose Services

The `docker-compose.yml` orchestrates all build steps:

| Service | Action | Output |
|---|---|---|
| `kernel-s1` | Cross-compile S1 kernel | `output/boot.img`, `output/zImage` |
| `kernel-t1` | Cross-compile T1 kernel | `output/boot.img`, `output/zImage`, `output/rk-kernel-t1.dtb` |
| `rootfs-s1` | Build S1 rootfs via debos | `output/rootfs.img` |
| `rootfs-t1` | Build T1 rootfs via debos | `output/rootfs.img` |
| `sdcard-s1` | Assemble S1 SD card image | `output/FLSUN-OS-S1-SD.img.gz` |
| `sdcard-t1` | Assemble T1 SD card image | `output/FLSUN-OS-T1-SD.img.gz` |
| `emmc-s1` | Package S1 eMMC archive | `output/FLSUN-OS-S1-EMMC-custom.7z` |
| `emmc-t1` | Package T1 eMMC archive | `output/FLSUN-OS-T1-EMMC-custom.7z` |

### 4.4 Build Commands

```bash
cd build/

# ── Build Docker images ──────────────────────────────────────────────
docker compose build

# ── Full S1 build sequence ───────────────────────────────────────────
docker compose run kernel-s1         # → output/boot.img
docker compose run rootfs-s1         # → output/rootfs.img (slow, 30-60 min)
docker compose run sdcard-s1         # → output/FLSUN-OS-S1-SD.img.gz

# ── Full T1 build sequence ───────────────────────────────────────────
docker compose run kernel-t1         # → output/boot.img (T1-patched DTB)
docker compose run rootfs-t1         # → output/rootfs.img
docker compose run sdcard-t1         # → output/FLSUN-OS-T1-SD.img.gz

# ── eMMC-only packages (boot.img + rootfs.img for RKDevTool) ─────────
docker compose run emmc-s1           # → output/FLSUN-OS-S1-EMMC-custom.7z
docker compose run emmc-t1           # → output/FLSUN-OS-T1-EMMC-custom.7z
```

### 4.5 Bootloader Binaries for SD Card Assembly

The SD card image needs proprietary Rockchip bootloader binaries. These must be extracted from stock firmware and placed in `build/bootloader/{s1,t1}/`:

```
build/bootloader/
├── s1/
│   ├── idbloader.img    # From S1 stock eMMC or SD image
│   ├── uboot.img        # From S1 eMMC partition 1
│   └── trust.img        # From S1 eMMC (sector 0x6000)
└── t1/
    ├── idbloader.img    # From T1 stock eMMC (sector 64-16383)
    ├── uboot.img        # From T1 stock 1097_0p1.img (includes OP-TEE)
    └── trust.img        # From T1 stock eMMC (sector 0x6000, or empty if bundled in uboot)
```

**Extracting from T1 stock dump:**
```bash
# Decompress stock eMMC dump
gunzip -k resources/T1/firmwares/stock/1097_0.img.gz

# IDBLoader (raw area before GPT partitions):
dd if=1097_0.img of=build/bootloader/t1/idbloader.img bs=512 skip=64 count=16320

# U-Boot (partition 1 dump — already exists as 1097_0p1.img):
cp resources/T1/firmwares/stock/1097_0p1.img build/bootloader/t1/uboot.img

# Trust (may be inside uboot.img on T1, but try the sector offset too):
dd if=1097_0.img of=build/bootloader/t1/trust.img bs=512 skip=24576 count=8192
```

---

## 5. T1 SD Card Builder — `build-sdcard-t1.py`

A pure-Python SD card image builder was created that resolves all the open questions
from the initial research phase. It builds bootable T1 SD card images directly on
Windows (with WSL Debian for Phase 2 rootfs modification).

### 5.1 Resolved Questions

| Question | Answer |
|---|---|
| Does the RV1109 BootROM scan SD before eMMC? | **Yes, confirmed.** User tested S1 SD card on T1 — it boots (display wrong, but boots). RV1109 has same SD > eMMC priority as RV1126. |
| Does the T1 have an IDBLoader at sector 64? | **Yes.** ~3,616 KB of content at sectors 64–7,295 in the full eMMC dump. |
| Should the SD image cmdline use `storagemedia=sd`? | **No.** We use explicit `root=PARTUUID=614e0000-0000-4000-8000-000000000007` so the kernel mounts the SD rootfs partition by its unique GPT PARTUUID, independent of device naming. The S1's empty cmdline works because U-Boot sets root=, but for SD we want to override that. |
| Does the T1 U-Boot FIT include Trust/OP-TEE? | **Yes.** Sector 0x6000 (misc partition) is all zeros — OP-TEE is bundled inside the FIT U-Boot image at p1. No separate trust.img needed. |
| Can the S1's IDBLoader be used on T1? | **Not needed.** The T1's own IDBLoader is extracted from the stock eMMC dump. |
| Where does T1 rootfs start? | **Sector 0x38000** (229,376) — different from S1's 0x40000 (262,144). |

### 5.2 Build Tool Usage

```bash
# Phase 1: "boot-test" SD image (S1 rootfs unchanged, T1 display)
py build/tools/build-sdcard-t1.py --phase1

# Phase 2: Full T1 SD image (modified rootfs, requires WSL Debian)
py build/tools/build-sdcard-t1.py --phase2

# Both phases:
py build/tools/build-sdcard-t1.py --all

# With gzip compression:
py build/tools/build-sdcard-t1.py --phase1 --compress
```

### 5.3 SD Image Layout (T1)

```
FLSUN-OS-T1-SD.img layout (7.45 GB):
┌─────────────────────────────────────────────────────────────────┐
│ Sector 0        Protective MBR                                   │
│ Sector 1        Primary GPT header                               │
│ Sectors 2-33    Primary GPT entries (128 × 128 bytes)            │
├─────────────────────────────────────────────────────────────────┤
│ Sector 64       IDBLoader (TPL + SPL, ~3.6 MB)                   │
│                 Extracted from T1 stock eMMC dump                │
├─────────────────────────────────────────────────────────────────┤
│ p1 (0x4000)     uboot — U-Boot FIT (4 MB, includes OP-TEE)      │
│                 Decompressed from 1097_0p1.img                   │
├─────────────────────────────────────────────────────────────────┤
│ p2 (0x6000)     misc (4 MB, empty)                               │
├─────────────────────────────────────────────────────────────────┤
│ p3 (0x8000)     boot — Android boot.img (~8.3 MB)                │
│                 S1 zImage 6.1.99flsun + T1 DTB (800×480)        │
│                 Cmdline: root=PARTUUID=614e0000-...-000000000007 │
├─────────────────────────────────────────────────────────────────┤
│ p4 (0x18000)    recovery (32 MB, empty)                          │
├─────────────────────────────────────────────────────────────────┤
│ p5 (0x28000)    backup (32 MB, empty)                            │
├─────────────────────────────────────────────────────────────────┤
│ p6 (0x38000)    rootfs (ext4, ~7.34 GB)                          │
│                 Phase 1: S1 rootfs unchanged                     │
│                 Phase 2: T1-modified rootfs                      │
├─────────────────────────────────────────────────────────────────┤
│ End - 33        Backup GPT entries                               │
│ End             Backup GPT header                                │
└─────────────────────────────────────────────────────────────────┘
```

### 5.4 Phase 2 Rootfs Modifications

Phase 2 applies T1-specific changes via `mod-rootfs-for-t1.sh` in offline mode:

**Applied during image build (offline):**
1. Replace Klipper configs (printer.cfg, config.cfg, Configurations/*.cfg)
2. Replace Moonraker config (no drying box, garethky fork updater)
3. Replace KlipperScreen config (800×480, T1 branding)
4. Update systemd services (remove drying-box, add klipper-mcu)
5. Replace first-boot.sh (T1 hostname, no easy-installer)
6. Update rc.local (PWM export for caselight)
7. Remove S1-specific files (drying-box scripts, S1 JSON backups)
8. Update hostname/branding (FLSUN-T1)
9. Fix file permissions

**Deferred to first boot (via `~/.t1-klipper-switch-pending` marker):**
1. Switch Klipper fork to garethky/klipper (load-cell-probe branch)
2. Switch KlipperScreen to upstream
3. Build and install klipper_mcu (Linux MCU process)
4. Install SciPy into klippy-env (needed for load cell notch filter)

### 5.5 Key Design Decisions

**PARTUUID-based root mount:** The boot.img cmdline uses the full GPT PARTUUID
(`614e0000-0000-4000-8000-000000000007`) rather than the abbreviated form or
device paths. This ensures the kernel mounts the rootfs from the SD card
regardless of the device enumeration order.

**Sparse file creation:** The image uses `seek()` to pre-allocate, which creates
a sparse file on NTFS. The actual disk usage is dominated by the rootfs content.

**Streaming rootfs write:** The rootfs is streamed in 1 MB chunks rather than
loaded entirely into memory, keeping peak RAM usage under 100 MB even for 7+ GB
rootfs images.

**No separate trust.img:** The T1's OP-TEE is bundled inside the U-Boot FIT
image (verified by finding all zeros at the misc partition sector 0x6000).
Only IDBLoader + U-Boot FIT partition are needed for the boot chain.

---

## 6. Open Questions

| Question | Status |
|---|---|
| Does `root=PARTUUID=...` work with the T1's U-Boot? | **Needs hardware test** — should work since the full GUID is passed via cmdline, not relying on U-Boot to set it |
| Can Phase 2 SD card boot and run Klipper after first-boot marker is executed? | **Needs hardware test** — git clone + pip install require internet connectivity on first boot |
| Does the IDBLoader trimming (last non-zero byte + sector alignment) preserve all needed content? | **Needs hardware test** — should be fine since trailing zeros are padding |

---

## 7. Files Created

| File | Purpose |
|---|---|
| `build/Dockerfile.kernel` | Docker image for kernel cross-compilation (S1/T1) |
| `build/docker-kernel-build.sh` | Entrypoint script for kernel Docker container |
| `build/Dockerfile.sdcard` | Docker image for SD card image assembly |
| `build/docker-sdcard-build.sh` | SD card image assembly script (GPT + dd) |
| `build/docker-compose.yml` | Orchestrates all Docker build services |
| `build/tools/build-sdcard-t1.py` | T1 SD card image builder (Phase 1 + Phase 2) |
| `build/output/FLSUN-OS-T1-SD-phase1.img` | Phase 1 boot-test SD image (7.45 GB) |
| `build/output/FLSUN-OS-T1-SD.img` | Phase 2 full T1 SD image (7.45 GB) |
| `docs/T1/research/07-sdcard-boot-analysis.md` | This document |
