#!/bin/bash
# FLSUN OS — Boot Image Builder (T1 Edition)
# Packages kernel (zImage) + DTB into boot image format
# ─────────────────────────────────────────────────────────
# The T1 stock firmware uses U-Boot FIT format, but the S1 uses
# Android boot format (mkbootimg). This script supports BOTH:
#
#   --format android   Use mkbootimg (compatible with S1 pipeline)
#   --format fit       Use mkimage FIT (native T1 U-Boot format)
#
# The default is "android" since the existing build pipeline uses it.
# If the T1 U-Boot only accepts FIT images, use --format fit.
#
# You need:
#   - mkbootimg (Android format) or mkimage (FIT format)
#   - resource_tool (Rockchip RSCE packer — from rkbin repo, Android only)
#   - Pre-built zImage kernel (built from rv1126_defconfig)
#   - Pre-built rk-kernel.dtb (T1: 800×480 panel timings)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUTPUT_DIR="${SCRIPT_DIR}/output"

# ── Configurable paths ──────────────────────────────────────────────
KERNEL="${1:-}"
DTB="${2:-}"
FORMAT="${FORMAT:-android}"
MKBOOTIMG="${MKBOOTIMG:-mkbootimg}"
MKIMAGE="${MKIMAGE:-mkimage}"
RESOURCE_TOOL="${RESOURCE_TOOL:-resource_tool}"

# Parse --format from args
for arg in "$@"; do
    case "$arg" in
        --format)  shift; FORMAT="${1:-android}"; shift ;;
        android|fit) FORMAT="$arg" ;;
    esac
done

# Strip --format from positional args
ARGS=()
while [[ $# -gt 0 ]]; do
    case "$1" in
        --format) shift; shift ;;  # skip --format and its value
        *) ARGS+=("$1"); shift ;;
    esac
done
KERNEL="${ARGS[0]:-$KERNEL}"
DTB="${ARGS[1]:-$DTB}"

if [ -z "$KERNEL" ] || [ -z "$DTB" ]; then
    echo "Usage: $0 <zImage> <rk-kernel.dtb> [--format android|fit]"
    echo ""
    echo "Arguments:"
    echo "  zImage          Pre-built ARM kernel (compressed)"
    echo "  rk-kernel.dtb   Compiled device tree blob (T1: 800×480 panel)"
    echo "  --format        Boot image format: 'android' (default) or 'fit'"
    echo ""
    echo "T1 Notes:"
    echo "  - The T1 stock firmware uses FIT format, S1 uses Android format"
    echo "  - Use --format fit if T1 U-Boot rejects Android boot images"
    echo "  - The DTB must have T1-specific timings (800×480, 25 MHz pixel clock)"
    echo "  - Use rv1126_defconfig to build the kernel (RV1109 shares it)"
    echo ""
    echo "Environment variables:"
    echo "  MKBOOTIMG       Path to mkbootimg (Android format, default: in PATH)"
    echo "  MKIMAGE         Path to mkimage (FIT format, default: in PATH)"
    echo "  RESOURCE_TOOL   Path to Rockchip resource_tool (default: in PATH)"
    echo "  FORMAT          Boot image format (default: android)"
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
echo "║         FLSUN OS Boot Image Builder — T1 Edition           ║"
echo "║  Packages zImage + DTB into boot image                     ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""
echo "  Kernel: ${KERNEL} ($(du -h "$KERNEL" | cut -f1))"
echo "  DTB:    ${DTB} ($(du -h "$DTB" | cut -f1))"
echo "  Format: ${FORMAT}"
echo ""

if [ "$FORMAT" = "fit" ]; then
    # ── FIT Image Format (native T1 U-Boot) ─────────────────────────
    echo "Building FIT image (U-Boot Flattened Image Tree)..."

    if ! command -v "$MKIMAGE" &>/dev/null; then
        echo "ERROR: mkimage not found."
        echo "  Install from: apt install u-boot-tools (Linux)"
        echo "  Or from Rockchip rkbin repo"
        exit 1
    fi

    # Create FIT Image Tree Source (.its) file
    cat > "${WORK_DIR}/boot.its" << 'ITS_EOF'
/dts-v1/;

/ {
    description = "FLSUN OS T1 Boot Image";
    #address-cells = <1>;

    images {
        kernel {
            description = "Linux kernel";
            data = /incbin/("zImage");
            type = "kernel";
            arch = "arm";
            os = "linux";
            compression = "none";
            load = <0x62008000>;
            entry = <0x62008000>;
        };

        fdt {
            description = "Flattened Device Tree";
            data = /incbin/("rk-kernel.dtb");
            type = "flat_dt";
            arch = "arm";
            compression = "none";
        };
    };

    configurations {
        default = "conf";
        conf {
            description = "FLSUN T1 (RV1109)";
            kernel = "kernel";
            fdt = "fdt";
        };
    };
};
ITS_EOF

    # Copy kernel and DTB to work dir
    cp "$KERNEL" "${WORK_DIR}/zImage"
    cp "$DTB" "${WORK_DIR}/rk-kernel.dtb"

    # Build FIT image
    cd "${WORK_DIR}"
    "$MKIMAGE" -f boot.its "${OUTPUT_DIR}/boot.img"

    echo ""
    echo "════════════════════════════════════════════════════════════"
    echo "  T1 BOOT IMAGE CREATED (FIT format)"
    echo ""
    echo "  boot.img: ${OUTPUT_DIR}/boot.img"
    echo "  Size:     $(du -h "${OUTPUT_DIR}/boot.img" | cut -f1)"
    echo ""
    echo "  Layout:"
    echo "    Format:  U-Boot FIT Image (Flattened Image Tree)"
    echo "    Kernel:  zImage @ load 0x62008000"
    echo "    DTB:     T1 device tree (800×480, RV1109)"
    echo "════════════════════════════════════════════════════════════"

else
    # ── Android Boot Format (S1-compatible pipeline) ─────────────────
    echo "Building Android boot image (mkbootimg format)..."

    # Step 1: Create RSCE resource image containing DTB
    echo "Step 1: Packing DTB into RSCE resource image..."

    if command -v "$RESOURCE_TOOL" &>/dev/null; then
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

    # Step 2: Create empty ramdisk
    echo "Step 2: Creating empty ramdisk..."
    touch "${WORK_DIR}/ramdisk.img"

    # Step 3: Build boot.img with mkbootimg
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
    echo "  T1 BOOT IMAGE CREATED (Android boot format)"
    echo ""
    echo "  boot.img: ${OUTPUT_DIR}/boot.img"
    echo "  Size:     $(du -h "${OUTPUT_DIR}/boot.img" | cut -f1)"
    echo ""
    echo "  Layout:"
    echo "    Format:     Android boot (mkbootimg)"
    echo "    Kernel:     0x62008000"
    echo "    Ramdisk:    0x66000000 (empty)"
    echo "    Second:     0x66100000 (RSCE with DTB)"
    echo "    Tags:       0x62000100"
    echo "    Page size:  2048"
    echo ""
    echo "  NOTE: If the T1 U-Boot rejects this format, rebuild with:"
    echo "    $0 $KERNEL $DTB --format fit"
    echo "════════════════════════════════════════════════════════════"
fi
