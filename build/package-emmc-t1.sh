#!/bin/bash
# FLSUN OS — eMMC Package Creator (T1 Edition)
# Packages boot.img + rootfs.img into a 7z archive for RKDevTool flashing
# ──────────────────────────────────────────────────────────────────────
# The T1 stock eMMC has 6 partitions (same as S1: uboot, misc, boot,
# recovery, backup, rootfs). Earlier references to 9 partitions were
# incorrect — oem/userdata/media are Rockchip SDK defaults not used by FLSUN.
#
# T1 Stock Partition Layout:
#   1. uboot      — U-Boot bootloader
#   2. misc       — Recovery flags
#   3. boot       — Kernel + DTB (boot.img)
#   4. recovery   — Recovery image
#   5. backup     — Empty
#   6. rootfs     — Root filesystem (rootfs.img)
#
# For initial flashing, we only replace boot + rootfs.
# The U-Boot and other partitions are left as stock.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUTPUT_DIR="${SCRIPT_DIR}/output"
VERSION="${1:-custom}"

BOOT_IMG="${OUTPUT_DIR}/boot.img"
ROOTFS_IMG="${OUTPUT_DIR}/rootfs.img"

if [ ! -f "$BOOT_IMG" ] || [ ! -f "$ROOTFS_IMG" ]; then
    echo "Usage: $0 [version]"
    echo ""
    echo "Expected files in ${OUTPUT_DIR}/:"
    echo "  boot.img    $([ -f "$BOOT_IMG" ] && echo "✓ found" || echo "✗ MISSING")"
    echo "  rootfs.img  $([ -f "$ROOTFS_IMG" ] && echo "✓ found" || echo "✗ MISSING")"
    echo ""
    echo "Run build-t1.sh and build-boot-img-t1.sh first."
    exit 1
fi

ARCHIVE_NAME="FLSUN-OS-T1-EMMC-${VERSION}.7z"

echo "Packaging T1 eMMC image..."
echo "  boot.img:   $(du -h "$BOOT_IMG" | cut -f1)"
echo "  rootfs.img: $(du -h "$ROOTFS_IMG" | cut -f1)"
echo ""

if command -v 7z &>/dev/null; then
    cd "${OUTPUT_DIR}"
    7z a -mx=9 "${ARCHIVE_NAME}" boot.img rootfs.img
elif command -v 7za &>/dev/null; then
    cd "${OUTPUT_DIR}"
    7za a -mx=9 "${ARCHIVE_NAME}" boot.img rootfs.img
else
    echo "ERROR: 7-Zip not found. Install p7zip-full or 7zip."
    exit 1
fi

echo ""
echo "════════════════════════════════════════════════════════════"
echo "  T1 eMMC PACKAGE CREATED"
echo ""
echo "  ${OUTPUT_DIR}/${ARCHIVE_NAME}"
echo "  Size: $(du -h "${OUTPUT_DIR}/${ARCHIVE_NAME}" | cut -f1)"
echo ""
echo "  Flash with RKDevTool v2.96:"
echo "    1. Enter Maskrom mode (hold button + USB-C)"
echo "    2. Load loader: MiniLoaderAll.bin (RV1109)"
echo "    3. boot partition   (0x8000):  boot.img"
echo "    4. rootfs partition (0x40000): rootfs.img"
echo "    5. Click 'Run'"
echo ""
echo "  NOTE: Partition offsets are from the S1 layout."
echo "  If the T1 uses different offsets, check the stock"
echo "  partition table with: gdisk -l /dev/mmcblkX"
echo "════════════════════════════════════════════════════════════"
