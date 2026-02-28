#!/bin/bash
# FLSUN OS — eMMC Package Creator
# Packages boot.img + rootfs.img into a 7z archive for RKDevTool flashing
# ──────────────────────────────────────────────────────────────────────
# The official FLSUN OS eMMC distribution format is:
#   FLSUN-OS-S1-EMMC-X.X.7z containing:
#     ├── boot.img     (Android boot image: kernel + DTB)
#     └── rootfs.img   (ext4 filesystem)
#
# These are flashed via RKDevTool v2.96 to eMMC partitions:
#   - boot.img   → partition 3 (boot)     @ offset 0x8000 sectors
#   - rootfs.img → partition 6 (rootfs)   @ offset 0x40000 sectors

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
    echo "Run build.sh and build-boot-img.sh first."
    exit 1
fi

ARCHIVE_NAME="FLSUN-OS-S1-EMMC-${VERSION}.7z"

echo "Packaging eMMC image..."
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
echo "  eMMC PACKAGE CREATED"
echo ""
echo "  ${OUTPUT_DIR}/${ARCHIVE_NAME}"
echo "  Size: $(du -h "${OUTPUT_DIR}/${ARCHIVE_NAME}" | cut -f1)"
echo ""
echo "  Flash with RKDevTool v2.96:"
echo "    1. Enter Maskrom mode (hold button + power on)"
echo "    2. Load loader: MiniLoaderAll.bin"
echo "    3. boot partition   (0x8000):  boot.img"
echo "    4. rootfs partition (0x40000): rootfs.img"
echo "    5. Click 'Run'"
echo "════════════════════════════════════════════════════════════"
