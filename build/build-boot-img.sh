#!/bin/bash
# FLSUN OS — Boot Image Builder
# Packages kernel (zImage) + DTB into Android boot.img format
# ─────────────────────────────────────────────────────────
# This script is SEPARATE from the rootfs build because:
#   1. The kernel is a pre-built Rockchip BSP (Linux 6.1.99flsun)
#   2. The DTB is board-specific (RV1126 FLSUN S1)
#   3. Neither is built from source in this workflow
#
# You need:
#   - mkbootimg (from Android tools or Rockchip SDK)
#   - resource_tool (Rockchip RSCE resource packer — from rkbin repo)
#   - Pre-built zImage kernel
#   - Pre-built rk-kernel.dtb (or .dts to compile with dtc)
#
# The stock FLSUN OS boot.img structure:
#   - Android boot image (mkbootimg format)
#   - Kernel: zImage at offset after boot header
#   - Ramdisk: empty (size 0)
#   - Second stage: RSCE resource image containing DTB
#   - Page size: 2048 bytes
#   - Kernel load addr: 0x62008000
#   - Ramdisk load addr: 0x64000000
#   - Second load addr: 0x64100000
#   - Tags addr: 0x60000100
#   - cmdline: storagemedia=emmc androidboot.storagemedia=emmc
#              androidboot.mode=normal

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUTPUT_DIR="${SCRIPT_DIR}/output"

# ── Configurable paths ──────────────────────────────────────────────
KERNEL="${1:-}"
DTB="${2:-}"
MKBOOTIMG="${MKBOOTIMG:-mkbootimg}"
RESOURCE_TOOL="${RESOURCE_TOOL:-resource_tool}"

if [ -z "$KERNEL" ] || [ -z "$DTB" ]; then
    echo "Usage: $0 <zImage> <rk-kernel.dtb>"
    echo ""
    echo "Arguments:"
    echo "  zImage          Pre-built ARM kernel (compressed)"
    echo "  rk-kernel.dtb   Compiled device tree blob"
    echo ""
    echo "Environment variables:"
    echo "  MKBOOTIMG       Path to mkbootimg (default: in PATH)"
    echo "  RESOURCE_TOOL   Path to Rockchip resource_tool (default: in PATH)"
    echo ""
    echo "To extract these from a stock boot.img, see docs/S1/research/09-image-reverse-engineering.md"
    exit 1
fi

if [ ! -f "$KERNEL" ]; then
    echo "ERROR: Kernel not found: $KERNEL"
    exit 1
fi

if [ ! -f "$DTB" ]; then
    echo "ERROR: DTB not found: $DTB"
    exit 1
fi

mkdir -p "${OUTPUT_DIR}"
WORK_DIR=$(mktemp -d)
trap "rm -rf ${WORK_DIR}" EXIT

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║              FLSUN OS Boot Image Builder                   ║"
echo "║  Packages zImage + DTB into Android boot.img               ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""
echo "  Kernel: ${KERNEL} ($(du -h "$KERNEL" | cut -f1))"
echo "  DTB:    ${DTB} ($(du -h "$DTB" | cut -f1))"
echo ""

# ── Step 1: Create RSCE resource image containing DTB ────────────────
echo "Step 1: Packing DTB into RSCE resource image..."

if command -v "$RESOURCE_TOOL" &>/dev/null; then
    # Use Rockchip resource_tool to create RSCE image
    cp "$DTB" "${WORK_DIR}/rk-kernel.dtb"
    cd "${WORK_DIR}"
    "$RESOURCE_TOOL" --pack --image=resource.img rk-kernel.dtb
    RESOURCE_IMG="${WORK_DIR}/resource.img"
    echo "  RSCE resource image created: $(du -h "$RESOURCE_IMG" | cut -f1)"
else
    echo "WARNING: resource_tool not found."
    echo "  Falling back to using DTB directly as second-stage payload."
    echo "  This may not boot correctly on all Rockchip platforms."
    RESOURCE_IMG="$DTB"
fi

# ── Step 2: Create empty ramdisk ─────────────────────────────────────
echo "Step 2: Creating empty ramdisk..."
# FLSUN OS uses no initramfs — ramdisk is empty
touch "${WORK_DIR}/ramdisk.img"

# ── Step 3: Build boot.img with mkbootimg ────────────────────────────
echo "Step 3: Building boot.img..."

if ! command -v "$MKBOOTIMG" &>/dev/null; then
    echo "ERROR: mkbootimg not found."
    echo "  Install from: https://github.com/nicholasgasior/mkbootimg"
    echo "  Or from Android SDK platform-tools"
    exit 1
fi

"$MKBOOTIMG" \
    --kernel "$KERNEL" \
    --ramdisk "${WORK_DIR}/ramdisk.img" \
    --second "$RESOURCE_IMG" \
    --kernel_offset 0x00008000 \
    --ramdisk_offset 0x04000000 \
    --second_offset 0x04100000 \
    --tags_offset 0x00000100 \
    --pagesize 2048 \
    --base 0x62000000 \
    --cmdline "storagemedia=emmc androidboot.storagemedia=emmc androidboot.mode=normal" \
    --output "${OUTPUT_DIR}/boot.img"

echo ""
echo "════════════════════════════════════════════════════════════"
echo "  BOOT IMAGE CREATED"
echo ""
echo "  boot.img: ${OUTPUT_DIR}/boot.img"
echo "  Size:     $(du -h "${OUTPUT_DIR}/boot.img" | cut -f1)"
echo ""
echo "  Layout:"
echo "    Kernel addr:  0x62008000"
echo "    Ramdisk addr: 0x66000000 (empty)"
echo "    Second addr:  0x66100000 (RSCE with DTB)"
echo "    Tags addr:    0x62000100"
echo "    Page size:    2048"
echo "════════════════════════════════════════════════════════════"
