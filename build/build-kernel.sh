#!/bin/bash
# FLSUN OS — Kernel Build Script
# Cross-compiles the Linux kernel for S1 (RV1126) or T1 (RV1109)
# ─────────────────────────────────────────────────────────────────
# Usage:
#   ./build-kernel.sh              # Build S1 kernel (default)
#   ./build-kernel.sh --target t1  # Build T1 kernel
#   ./build-kernel.sh --menuconfig # Open menuconfig before building
#   ./build-kernel.sh --clean      # Clean build tree first
#
# Targets:
#   s1  — FLSUN S1 (RV1126, quad-core) — uses extracted FLSUN OS 3.0 config
#   t1  — FLSUN T1 (RV1109, dual-core) — uses same config (zImage is identical)
#
# Both targets produce the same zImage (RV1109 and RV1126 share rv1126_defconfig).
# The SoC difference is handled entirely by the device tree (DTB).
#
# For T1, the DTB is patched by build/tools/patch-dtb-for-t1.py after the kernel
# build — the kernel tree does not contain the FLSUN custom DTS.
#
# Prerequisites:
#   - Linux or WSL with arm-linux-gnueabihf-gcc cross-compiler
#   - bc, flex, bison, libssl-dev (kernel build deps)
#   - Kernel source at kernel/ (git submodule)
#
# Output:
#   build/output/zImage           — compressed kernel image
#   build/output/rk-kernel.dtb    — S1 DTB (reused from extracted FLSUN OS 3.0)
#   build/output/rk-kernel-t1.dtb — T1 DTB (patched from S1 via patch-dtb-for-t1.py)
#   build/output/boot.img         — Android boot image (zImage + DTB → mkbootimg)
#
# See docs/S1/research/12-kernel-build-from-source.md for full documentation.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE="$(cd "${SCRIPT_DIR}/.." && pwd)"
KERNEL_DIR="${WORKSPACE}/kernel"
OUTPUT_DIR="${SCRIPT_DIR}/output"
TOOLS_DIR="${SCRIPT_DIR}/tools"

# Extracted FLSUN OS 3.0 config (6,529 lines, fully monolithic)
FLSUN_CONFIG="${WORKSPACE}/resources/S1/firmwares/os-images/FLSUN-OS-S1-EMMC-3.0/extracted/kernel-config.txt"

# Extracted S1 DTB (used as-is for S1, patched for T1)
S1_DTB="${WORKSPACE}/resources/S1/firmwares/os-images/FLSUN-OS-S1-EMMC-3.0/extracted/rk-kernel.dtb"

# ── Defaults ─────────────────────────────────────────────────────────
TARGET="s1"
DO_CLEAN=false
DO_MENUCONFIG=false
JOBS="$(nproc 2>/dev/null || echo 4)"
CROSS_COMPILE="arm-linux-gnueabihf-"

# ── Parse arguments ──────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
    case "$1" in
        --target)   TARGET="${2,,}"; shift 2 ;;  # lowercase
        --clean)    DO_CLEAN=true; shift ;;
        --menuconfig) DO_MENUCONFIG=true; shift ;;
        --jobs|-j)  JOBS="$2"; shift 2 ;;
        --help|-h)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --target s1|t1   Target printer (default: s1)"
            echo "  --clean          Run 'make mrproper' before building"
            echo "  --menuconfig     Open menuconfig for manual config editing"
            echo "  --jobs N, -j N   Parallel build jobs (default: $(nproc 2>/dev/null || echo 4))"
            echo "  --help, -h       Show this help"
            echo ""
            echo "Output files (in build/output/):"
            echo "  zImage             Compressed kernel"
            echo "  rk-kernel.dtb      S1 DTB"
            echo "  rk-kernel-t1.dtb   T1 DTB (patched display timings)"
            echo "  boot.img           Android boot image (S1 or T1)"
            exit 0
            ;;
        *)
            echo "Unknown option: $1 (use --help for usage)"
            exit 1
            ;;
    esac
done

# ── Validate ─────────────────────────────────────────────────────────
if [ ! -d "${KERNEL_DIR}" ] || [ ! -f "${KERNEL_DIR}/Makefile" ]; then
    echo "ERROR: Kernel source not found at ${KERNEL_DIR}"
    echo ""
    echo "Initialize the submodule:"
    echo "  git submodule update --init --depth 1 kernel"
    exit 1
fi

if ! command -v "${CROSS_COMPILE}gcc" &>/dev/null; then
    echo "ERROR: Cross-compiler not found: ${CROSS_COMPILE}gcc"
    echo ""
    echo "Install on Debian/Ubuntu:"
    echo "  sudo apt install gcc-arm-linux-gnueabihf"
    exit 1
fi

if [ ! -f "${FLSUN_CONFIG}" ]; then
    echo "ERROR: FLSUN OS 3.0 kernel config not found at:"
    echo "  ${FLSUN_CONFIG}"
    echo ""
    echo "This file is the extracted /proc/config.gz from FLSUN OS 3.0."
    echo "It should be in the resources/ directory."
    exit 1
fi

if [ ! -f "${S1_DTB}" ]; then
    echo "ERROR: S1 DTB not found at:"
    echo "  ${S1_DTB}"
    exit 1
fi

mkdir -p "${OUTPUT_DIR}"

# ── Banner ───────────────────────────────────────────────────────────
KERNEL_VERSION=$(head -5 "${KERNEL_DIR}/Makefile" | awk '/^VERSION|^PATCHLEVEL|^SUBLEVEL/ {v=v $3"."} END {sub(/\.$/, "", v); print v}')
GCC_VERSION=$("${CROSS_COMPILE}gcc" --version | head -1)

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║              FLSUN OS Kernel Builder                       ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""
echo "  Target:        ${TARGET^^}"
echo "  Kernel:        ${KERNEL_VERSION}"
echo "  Cross-compile: ${GCC_VERSION}"
echo "  Jobs:          ${JOBS}"
echo "  Source:        ${KERNEL_DIR}"
echo "  Output:        ${OUTPUT_DIR}"
echo ""

# ── Step 1: Clean (optional) ─────────────────────────────────────────
if [ "${DO_CLEAN}" = true ]; then
    echo "Step 1: Cleaning build tree..."
    make -C "${KERNEL_DIR}" ARCH=arm mrproper
    echo "  Clean complete."
    echo ""
fi

# ── Step 2: Configure ────────────────────────────────────────────────
echo "Step 2: Configuring kernel..."

# Copy extracted FLSUN OS 3.0 config as a defconfig
DEFCONFIG_NAME="flsun_${TARGET}_defconfig"
cp "${FLSUN_CONFIG}" "${KERNEL_DIR}/arch/arm/configs/${DEFCONFIG_NAME}"

# Apply defconfig (runs olddefconfig to resolve new options with defaults)
make -C "${KERNEL_DIR}" ARCH=arm "${DEFCONFIG_NAME}"
make -C "${KERNEL_DIR}" ARCH=arm olddefconfig

echo "  Config applied: ${DEFCONFIG_NAME}"
echo ""

# ── Step 3: menuconfig (optional) ────────────────────────────────────
if [ "${DO_MENUCONFIG}" = true ]; then
    echo "Step 3: Opening menuconfig..."
    make -C "${KERNEL_DIR}" ARCH=arm menuconfig
    echo ""
fi

# ── Step 4: Compile ──────────────────────────────────────────────────
echo "Step 4: Compiling kernel (zImage + dtbs)..."

make -C "${KERNEL_DIR}" \
    ARCH=arm \
    CROSS_COMPILE="${CROSS_COMPILE}" \
    -j"${JOBS}" \
    zImage dtbs

echo "  Compile complete."
echo ""

# ── Step 5: Copy outputs ─────────────────────────────────────────────
echo "Step 5: Copying build artifacts..."

# Copy zImage
cp "${KERNEL_DIR}/arch/arm/boot/zImage" "${OUTPUT_DIR}/zImage"
echo "  zImage:  $(du -h "${OUTPUT_DIR}/zImage" | cut -f1)"

# Copy S1 DTB (from extracted FLSUN OS 3.0 — custom DTS not in kernel tree)
cp "${S1_DTB}" "${OUTPUT_DIR}/rk-kernel.dtb"
echo "  S1 DTB:  $(du -h "${OUTPUT_DIR}/rk-kernel.dtb" | cut -f1) (extracted from FLSUN OS 3.0)"

# For T1: patch the DTB for 800×480 display
if [ "${TARGET}" = "t1" ]; then
    echo "  Patching DTB for T1 display (800×480)..."
    PYTHON="${PYTHON:-python3}"
    if ! command -v "${PYTHON}" &>/dev/null; then
        PYTHON="python"
    fi
    "${PYTHON}" "${TOOLS_DIR}/patch-dtb-for-t1.py" \
        "${OUTPUT_DIR}/rk-kernel.dtb" \
        "${OUTPUT_DIR}/rk-kernel-t1.dtb"
    echo "  T1 DTB:  $(du -h "${OUTPUT_DIR}/rk-kernel-t1.dtb" | cut -f1) (patched: 800×480 @ 25 MHz)"
fi

echo ""

# ── Step 6: Build boot.img ───────────────────────────────────────────
echo "Step 6: Building boot.img..."

if [ "${TARGET}" = "t1" ]; then
    DTB_FILE="${OUTPUT_DIR}/rk-kernel-t1.dtb"
else
    DTB_FILE="${OUTPUT_DIR}/rk-kernel.dtb"
fi

PYTHON="${PYTHON:-python3}"
if ! command -v "${PYTHON}" &>/dev/null; then
    PYTHON="python"
fi

"${PYTHON}" "${TOOLS_DIR}/build-boot-img-t1.py" \
    "${OUTPUT_DIR}/zImage" \
    "${DTB_FILE}" \
    "${OUTPUT_DIR}/boot.img"

echo ""

# ── Summary ──────────────────────────────────────────────────────────
ZIMAGE_SIZE=$(stat -c%s "${OUTPUT_DIR}/zImage" 2>/dev/null || stat -f%z "${OUTPUT_DIR}/zImage")
BOOT_SIZE=$(stat -c%s "${OUTPUT_DIR}/boot.img" 2>/dev/null || stat -f%z "${OUTPUT_DIR}/boot.img")

echo "════════════════════════════════════════════════════════════"
echo "  KERNEL BUILD COMPLETE — ${TARGET^^}"
echo ""
echo "  Outputs:"
echo "    zImage:    ${OUTPUT_DIR}/zImage (${ZIMAGE_SIZE} bytes)"
echo "    boot.img:  ${OUTPUT_DIR}/boot.img (${BOOT_SIZE} bytes)"
if [ "${TARGET}" = "t1" ]; then
echo "    T1 DTB:    ${OUTPUT_DIR}/rk-kernel-t1.dtb"
fi
echo ""
echo "  Flash to eMMC:"
if [ "${TARGET}" = "t1" ]; then
echo "    RKDevTool → boot partition (offset 0x6000)"
else
echo "    RKDevTool → boot partition (offset 0x8000)"
fi
echo "════════════════════════════════════════════════════════════"
