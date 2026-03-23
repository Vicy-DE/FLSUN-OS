#!/bin/bash
# FLSUN OS — SD Card Image Assembly Script
# Assembles a complete bootable SD card image from pre-built components
# ────────────────────────────────────────────────────────────────────
# Can run standalone or as Docker entrypoint (Dockerfile.sdcard).
#
# Usage:
#   ./docker-sdcard-build.sh                    # S1 (default)
#   ./docker-sdcard-build.sh --target t1        # T1
#   ./docker-sdcard-build.sh --image-size 16G   # Custom size
#
# Prerequisites in /build/output/ (or --output-dir):
#   boot.img    — Android boot image (kernel + DTB)
#   rootfs.img  — ext4 root filesystem
#
# Bootloader binaries in /build/bootloader/{s1,t1}/:
#   idbloader.img  — DDR init + SPL (raw, written to sector 64)
#   uboot.img      — U-Boot (GPT partition 1, sector 0x4000)
#   trust.img      — OP-TEE trust firmware (sector 0x6000)
#   [misc.img]     — Optional recovery flags
#
# These bootloader binaries are PROPRIETARY Rockchip components.
# Extract them from a stock eMMC dump:
#   # IDBLoader (raw area before GPT partitions):
#   dd if=stock-emmc.img of=idbloader.img bs=512 skip=64 count=16320
#   # U-Boot partition (p1):
#   dd if=/dev/mmcblk0p1 of=uboot.img bs=1M
#   # Trust (from raw area at sector 0x6000, or part of uboot partition):
#   dd if=stock-emmc.img of=trust.img bs=512 skip=24576 count=8192

set -euo pipefail

# ── Defaults ─────────────────────────────────────────────────────────
TARGET="s1"
OUTPUT_DIR="/build/output"
BOOTLOADER_DIR="/build/bootloader"
IMAGE_SIZE=""   # Auto-calculate from rootfs.img
COMPRESS=true

# ── Parse arguments ──────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
    case "$1" in
        --target)       TARGET="${2,,}"; shift 2 ;;
        --output-dir)   OUTPUT_DIR="$2"; shift 2 ;;
        --bootloader-dir) BOOTLOADER_DIR="$2"; shift 2 ;;
        --image-size)   IMAGE_SIZE="$2"; shift 2 ;;
        --no-compress)  COMPRESS=false; shift ;;
        --help|-h)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Assemble a complete bootable SD card image."
            echo ""
            echo "Options:"
            echo "  --target s1|t1           Target printer (default: s1)"
            echo "  --output-dir DIR         Output directory (default: /build/output)"
            echo "  --bootloader-dir DIR     Bootloader binaries dir (default: /build/bootloader)"
            echo "  --image-size SIZE        Image size in bytes/K/M/G (default: auto)"
            echo "  --no-compress            Skip gzip compression"
            echo "  -h, --help               Show this help"
            echo ""
            echo "Required files:"
            echo "  \$OUTPUT_DIR/boot.img      Kernel + DTB (Android boot image)"
            echo "  \$OUTPUT_DIR/rootfs.img    Root filesystem (ext4)"
            echo "  \$BOOTLOADER_DIR/\$TARGET/idbloader.img  DDR init + SPL"
            echo "  \$BOOTLOADER_DIR/\$TARGET/uboot.img      U-Boot"
            echo "  \$BOOTLOADER_DIR/\$TARGET/trust.img       OP-TEE"
            exit 0
            ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

# ── Rockchip sector offsets (standard for RV1126/RV1109) ─────────────
# These are the standard Rockchip layout (512-byte sectors):
SECTOR_IDBLOADER=64        # LBA 64 — raw area before GPT partitions
SECTOR_UBOOT=16384         # 0x4000 — partition 1
SECTOR_TRUST=24576         # 0x6000 — between uboot and boot partitions
SECTOR_BOOT=32768          # 0x8000 — partition 3
SECTOR_ROOTFS=262144       # 0x40000 — partition 6

# ── Files ────────────────────────────────────────────────────────────
BL_DIR="${BOOTLOADER_DIR}/${TARGET}"
BOOT_IMG="${OUTPUT_DIR}/boot.img"
ROOTFS_IMG="${OUTPUT_DIR}/rootfs.img"
IDBLOADER="${BL_DIR}/idbloader.img"
UBOOT="${BL_DIR}/uboot.img"
TRUST="${BL_DIR}/trust.img"

# ── Preflight checks ────────────────────────────────────────────────
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║         FLSUN OS SD Card Image Builder                     ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""
echo "  Target:     ${TARGET^^}"
echo "  Output dir: ${OUTPUT_DIR}"
echo ""

MISSING=false
for IMG in "$BOOT_IMG" "$ROOTFS_IMG" "$IDBLOADER" "$UBOOT" "$TRUST"; do
    NAME=$(basename "$IMG")
    if [ -f "$IMG" ]; then
        SIZE=$(stat -c%s "$IMG" 2>/dev/null || stat -f%z "$IMG" 2>/dev/null)
        echo "  ✓ ${NAME}  ($(numfmt --to=iec-i --suffix=B "$SIZE" 2>/dev/null || echo "${SIZE} bytes"))"
    else
        echo "  ✗ ${NAME}  MISSING — expected at: ${IMG}"
        MISSING=true
    fi
done
echo ""

if [ "$MISSING" = true ]; then
    echo "ERROR: Missing required files. Cannot build SD card image."
    echo ""
    echo "Build boot.img + rootfs.img first:"
    echo "  ./build-kernel.sh       # produces boot.img"
    echo "  ./build.sh              # produces rootfs.img"
    echo ""
    echo "Bootloader binaries — extract from stock eMMC dump:"
    echo "  dd if=stock-emmc.img of=idbloader.img bs=512 skip=64 count=16320"
    echo "  dd if=/dev/mmcblk0p1 of=uboot.img bs=1M"
    echo "  dd if=stock-emmc.img of=trust.img bs=512 skip=24576 count=8192"
    exit 1
fi

# ── Calculate image size ─────────────────────────────────────────────
ROOTFS_SIZE=$(stat -c%s "$ROOTFS_IMG" 2>/dev/null || stat -f%z "$ROOTFS_IMG" 2>/dev/null)
BOOT_SIZE=$(stat -c%s "$BOOT_IMG" 2>/dev/null || stat -f%z "$BOOT_IMG" 2>/dev/null)

if [ -z "$IMAGE_SIZE" ]; then
    # Rootfs starts at sector 0x40000 (128 MiB), plus rootfs size, plus 64 MiB slack
    ROOTFS_OFFSET=$((SECTOR_ROOTFS * 512))
    TOTAL_BYTES=$((ROOTFS_OFFSET + ROOTFS_SIZE + 67108864))
    IMAGE_SIZE="$TOTAL_BYTES"
fi

# Create SD image name
SDCARD_IMG="${OUTPUT_DIR}/FLSUN-OS-${TARGET^^}-SD.img"

echo "Step 1: Creating ${SDCARD_IMG}..."
echo "  Size: $(numfmt --to=iec-i --suffix=B "$IMAGE_SIZE" 2>/dev/null || echo "${IMAGE_SIZE} bytes")"

# Create sparse image (fast, doesn't allocate zero blocks on disk)
truncate -s "$IMAGE_SIZE" "$SDCARD_IMG"

# ── Write GPT partition table ────────────────────────────────────────
echo "Step 2: Writing GPT partition table..."

# Use sgdisk to create the 6-partition Rockchip layout
# Sector sizes for partitions between fixed offsets:
#   uboot:    0x4000  to 0x5FFF  (8192 sectors = 4 MiB)
#   misc:     auto-sized (1 MiB)
#   boot:     0x8000  to 0x3FFFF (229376 sectors = 112 MiB — fits any boot.img)
#   recovery: auto (32 MiB)
#   backup:   auto (32 MiB)
#   rootfs:   0x40000 to end
sgdisk --clear \
    --set-alignment=1 \
    -n 1:${SECTOR_UBOOT}:$((SECTOR_UBOOT + 8191))     -t 1:8300 -c 1:uboot \
    -n 2:$((SECTOR_UBOOT + 8192)):$((SECTOR_BOOT - 1)) -t 2:8300 -c 2:misc \
    -n 3:${SECTOR_BOOT}:$((SECTOR_ROOTFS - 1))          -t 3:8300 -c 3:boot \
    -n 4:0:+32M                                          -t 4:8300 -c 4:recovery \
    -n 5:0:+32M                                          -t 5:8300 -c 5:backup \
    -n 6:${SECTOR_ROOTFS}:0                              -t 6:8300 -c 6:rootfs \
    --disk-guid=614E0000-0000-4721-A1E7-000000000001 \
    "$SDCARD_IMG"

# Set the rootfs partition GUID to match what fstab/cmdline expects
sgdisk -u 6:614E0000-0000-4721-A1E7-000000000006 "$SDCARD_IMG"

echo "  GPT table written."

# ── Write bootloader components (dd at specific sector offsets) ──────
echo "Step 3: Writing bootloader components..."

# IDBLoader — DDR init + SPL, raw area before GPT partitions
dd if="$IDBLOADER" of="$SDCARD_IMG" seek=$SECTOR_IDBLOADER conv=notrunc bs=512 status=none
echo "  IDBLoader written at sector ${SECTOR_IDBLOADER} (LBA 64)"

# U-Boot — partition 1
dd if="$UBOOT" of="$SDCARD_IMG" seek=$SECTOR_UBOOT conv=notrunc bs=512 status=none
echo "  U-Boot written at sector ${SECTOR_UBOOT} (0x4000)"

# Trust / OP-TEE — between uboot and boot
dd if="$TRUST" of="$SDCARD_IMG" seek=$SECTOR_TRUST conv=notrunc bs=512 status=none
echo "  Trust written at sector ${SECTOR_TRUST} (0x6000)"

# ── Write boot.img and rootfs.img ────────────────────────────────────
echo "Step 4: Writing boot.img and rootfs.img..."

dd if="$BOOT_IMG" of="$SDCARD_IMG" seek=$SECTOR_BOOT conv=notrunc bs=512 status=none
echo "  boot.img written at sector ${SECTOR_BOOT} (0x8000)"

dd if="$ROOTFS_IMG" of="$SDCARD_IMG" seek=$SECTOR_ROOTFS conv=notrunc bs=512 status=none
echo "  rootfs.img written at sector ${SECTOR_ROOTFS} (0x40000)"
echo ""

# ── Compress ─────────────────────────────────────────────────────────
if [ "$COMPRESS" = true ]; then
    echo "Step 5: Compressing with gzip..."
    if command -v pigz &>/dev/null; then
        pigz -f -k "$SDCARD_IMG"
    else
        gzip -f -k "$SDCARD_IMG"
    fi
    GZ_SIZE=$(stat -c%s "${SDCARD_IMG}.gz" 2>/dev/null || stat -f%z "${SDCARD_IMG}.gz" 2>/dev/null)
    echo "  Compressed: $(numfmt --to=iec-i --suffix=B "$GZ_SIZE" 2>/dev/null || echo "${GZ_SIZE} bytes")"
    echo ""
fi

# ── Summary ──────────────────────────────────────────────────────────
RAW_SIZE=$(stat -c%s "$SDCARD_IMG" 2>/dev/null || stat -f%z "$SDCARD_IMG" 2>/dev/null)
echo "════════════════════════════════════════════════════════════"
echo "  SD CARD IMAGE CREATED — ${TARGET^^}"
echo ""
echo "  ${SDCARD_IMG}"
echo "  Raw size:  $(numfmt --to=iec-i --suffix=B "$RAW_SIZE" 2>/dev/null || echo "${RAW_SIZE} bytes")"
if [ "$COMPRESS" = true ] && [ -f "${SDCARD_IMG}.gz" ]; then
echo "  Compressed: ${SDCARD_IMG}.gz"
fi
echo ""
echo "  Partition layout:"
echo "    LBA 64:        IDBLoader (DDR init + SPL)"
echo "    Sector 0x4000: U-Boot (partition 1)"
echo "    Sector 0x6000: Trust / OP-TEE"
echo "    Sector 0x8000: boot.img (partition 3)"
echo "    Sector 0x40000: rootfs (partition 6)"
echo ""
echo "  Write to SD card with Raspberry Pi Imager or:"
echo "    gunzip -c ${SDCARD_IMG}.gz | sudo dd of=/dev/sdX bs=4M status=progress"
echo ""
if [ "${TARGET}" = "t1" ]; then
echo "  WARNING: T1 SD card boot is UNCONFIRMED."
echo "  The RV1109 BootROM should prioritize SD over eMMC"
echo "  (same as the S1's RV1126), but this has not been tested."
echo "  See docs/T1/research/07-sdcard-boot-analysis.md"
fi
echo "════════════════════════════════════════════════════════════"
