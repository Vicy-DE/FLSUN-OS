#!/bin/bash
# FLSUN OS — Docker Kernel Build Entrypoint
# Runs inside the flsun-kernel-builder container
# ─────────────────────────────────────────────
# Usage (from Docker CMD/entrypoint args):
#   docker-kernel-build.sh              # Build S1 kernel (default)
#   docker-kernel-build.sh --target t1  # Build T1 kernel
#   docker-kernel-build.sh --menuconfig # Interactive menuconfig

set -euo pipefail

KERNEL_SRC="/build/kernel-src"
BUILD_DIR="/build/kernel-build"
OUTPUT_DIR="/build/output"
TOOLS_DIR="/build/tools"
FLSUN_CONFIG="/build/kernel-config.txt"
S1_DTB="/build/rk-kernel.dtb"

TARGET="s1"
DO_MENUCONFIG=false
JOBS="${JOBS:-$(nproc 2>/dev/null || echo 4)}"
CROSS_COMPILE="arm-linux-gnueabihf-"

# ── Parse arguments ──────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
    case "$1" in
        --target)     TARGET="${2,,}"; shift 2 ;;
        --menuconfig) DO_MENUCONFIG=true; shift ;;
        --jobs|-j)    JOBS="$2"; shift 2 ;;
        --help|-h)
            echo "Usage: docker run flsun-kernel-builder [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --target s1|t1   Target printer (default: s1)"
            echo "  --menuconfig     Open menuconfig (needs -it)"
            echo "  --jobs N         Parallel jobs (default: $(nproc))"
            exit 0
            ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

# Use JOBS=0 to auto-detect
if [ "${JOBS}" = "0" ]; then
    JOBS="$(nproc)"
fi

# ── Banner ───────────────────────────────────────────────────────────
KERNEL_VERSION=$(head -5 "${KERNEL_SRC}/Makefile" \
    | awk '/^VERSION|^PATCHLEVEL|^SUBLEVEL/ {v=v $3"."} END {sub(/\.$/, "", v); print v}')
GCC_VERSION=$("${CROSS_COMPILE}gcc" --version | head -1)

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║         FLSUN OS Kernel Builder (Docker)                   ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""
echo "  Target:        ${TARGET^^}"
echo "  Kernel:        ${KERNEL_VERSION}"
echo "  Cross-compile: ${GCC_VERSION}"
echo "  Jobs:          ${JOBS}"
echo "  Build dir:     ${BUILD_DIR} (out-of-tree)"
echo "  Output:        ${OUTPUT_DIR}/"
echo ""

# Common make arguments — out-of-tree build keeps source tree clean
MAKE_ARGS=(ARCH=arm O="${BUILD_DIR}")

# ── Configure ────────────────────────────────────────────────────────
echo "Step 1: Configuring kernel..."
rm -rf "${BUILD_DIR}"
mkdir -p "${BUILD_DIR}"

cp "${FLSUN_CONFIG}" "${BUILD_DIR}/.config"
make -C "${KERNEL_SRC}" "${MAKE_ARGS[@]}" olddefconfig
echo "  Config applied: $(wc -l < "${FLSUN_CONFIG}") lines"
echo ""

# ── menuconfig (optional) ───────────────────────────────────────────
if [ "${DO_MENUCONFIG}" = true ]; then
    echo "Step 2: Opening menuconfig..."
    make -C "${KERNEL_SRC}" "${MAKE_ARGS[@]}" menuconfig
    echo ""
fi

# ── Compile ──────────────────────────────────────────────────────────
echo "Step 2: Compiling kernel (zImage + dtbs)..."
make -C "${KERNEL_SRC}" \
    "${MAKE_ARGS[@]}" \
    CROSS_COMPILE="${CROSS_COMPILE}" \
    -j"${JOBS}" \
    zImage dtbs
echo "  Compile complete."
echo ""

# ── Copy outputs ─────────────────────────────────────────────────────
echo "Step 3: Copying build artifacts..."
mkdir -p "${OUTPUT_DIR}"

cp "${BUILD_DIR}/arch/arm/boot/zImage" "${OUTPUT_DIR}/zImage"
echo "  zImage:  $(du -h "${OUTPUT_DIR}/zImage" | cut -f1)"

cp "${S1_DTB}" "${OUTPUT_DIR}/rk-kernel.dtb"
echo "  S1 DTB:  $(du -h "${OUTPUT_DIR}/rk-kernel.dtb" | cut -f1)"

if [ "${TARGET}" = "t1" ]; then
    echo "  Patching DTB for T1 display (800×480)..."
    python3 "${TOOLS_DIR}/patch-dtb-for-t1.py" \
        "${OUTPUT_DIR}/rk-kernel.dtb" \
        "${OUTPUT_DIR}/rk-kernel-t1.dtb"
    echo "  T1 DTB:  $(du -h "${OUTPUT_DIR}/rk-kernel-t1.dtb" | cut -f1)"
fi
echo ""

# ── Build boot.img ───────────────────────────────────────────────────
echo "Step 4: Building boot.img..."

if [ "${TARGET}" = "t1" ]; then
    DTB_FILE="${OUTPUT_DIR}/rk-kernel-t1.dtb"
else
    DTB_FILE="${OUTPUT_DIR}/rk-kernel.dtb"
fi

python3 "${TOOLS_DIR}/build-boot-img-t1.py" \
    "${OUTPUT_DIR}/zImage" \
    "${DTB_FILE}" \
    "${OUTPUT_DIR}/boot.img"
echo ""

# ── Summary ──────────────────────────────────────────────────────────
ZIMAGE_SIZE=$(stat -c%s "${OUTPUT_DIR}/zImage")
BOOT_SIZE=$(stat -c%s "${OUTPUT_DIR}/boot.img")

echo "════════════════════════════════════════════════════════════"
echo "  KERNEL BUILD COMPLETE — ${TARGET^^}"
echo ""
echo "  Outputs (in /build/output/, mapped to host):"
echo "    zImage:        ${ZIMAGE_SIZE} bytes"
echo "    boot.img:      ${BOOT_SIZE} bytes"
echo "    rk-kernel.dtb: $(stat -c%s "${OUTPUT_DIR}/rk-kernel.dtb") bytes"
if [ "${TARGET}" = "t1" ]; then
echo "    rk-kernel-t1.dtb: $(stat -c%s "${OUTPUT_DIR}/rk-kernel-t1.dtb") bytes"
fi
echo "════════════════════════════════════════════════════════════"
