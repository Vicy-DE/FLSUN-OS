#!/bin/bash
# ─────────────────────────────────────────────────────────────────────
# build-rootfs-t1.sh — Build T1 rootfs image from S1 FLSUN-OS 3.0
# ─────────────────────────────────────────────────────────────────────
#
# Creates flsun-os-t1-rootfs.img by:
#   1. Copying the S1 FLSUN-OS 3.0 rootfs.img
#   2. Mounting it as a loop device
#   3. Running mod-rootfs-for-t1.sh to convert S1 → T1
#   4. Unmounting and optionally shrinking
#
# This produces a rootfs ready to flash to the T1's eMMC partition 6.
#
# Usage:
#   sudo ./build-rootfs-t1.sh                    # Build with defaults
#   sudo ./build-rootfs-t1.sh --shrink           # Build and shrink image
#   sudo ./build-rootfs-t1.sh --live             # Run mods on live T1
#   sudo ./build-rootfs-t1.sh --dry-run          # Show what would change
#
# Requirements:
#   - Linux (ext4 mount, loop devices)
#   - Root access
#   - S1 FLSUN-OS 3.0 rootfs.img in resources/
#   - T1 ported configs in resources/T1/klipper-configs/ported/
#   - T1 overlays in build/overlays-t1/
#
# Output:
#   build/output/flsun-os-t1-rootfs.img

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
BUILD_DIR="$SCRIPT_DIR/.."
OUTPUT_DIR="$BUILD_DIR/output"
TOOLS_DIR="$SCRIPT_DIR"

# Source S1 image
S1_ROOTFS="$REPO_ROOT/resources/S1/firmwares/os-images/FLSUN-OS-S1-EMMC-3.0/rootfs.img"

# Tools
MOD_SCRIPT="$TOOLS_DIR/mod-rootfs-for-t1.sh"

# Output
OUTPUT_NAME="flsun-os-t1-rootfs.img"

# Flags
SHRINK=false
LIVE_MODE=false
DRY_RUN=false

# ── Parse Arguments ──────────────────────────────────────────────────

while [[ $# -gt 0 ]]; do
    case "$1" in
        --shrink)   SHRINK=true;    shift ;;
        --live)     LIVE_MODE=true; shift ;;
        --dry-run)  DRY_RUN=true;   shift ;;
        --source)   S1_ROOTFS="$2"; shift 2 ;;
        --output)   OUTPUT_NAME="$2"; shift 2 ;;
        -h|--help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Build FLSUN-OS T1 rootfs from S1 FLSUN-OS 3.0 rootfs"
            echo ""
            echo "Options:"
            echo "  --shrink     Minimize image size with resize2fs"
            echo "  --live       Run mods on live system (T1 running S1 image)"
            echo "  --dry-run    Show what would change without modifying"
            echo "  --source F   Override S1 rootfs.img path"
            echo "  --output F   Override output filename"
            echo "  -h, --help   Show this help"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# ── Preflight Checks ─────────────────────────────────────────────────

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║       FLSUN-OS T1 Rootfs Builder                           ║"
echo "║  Converts S1 FLSUN-OS 3.0 rootfs for T1 hardware          ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

if [ "$(uname -s)" != "Linux" ]; then
    echo "ERROR: This script requires Linux (ext4 mount + loop devices)."
    echo "  Run on a Linux machine or WSL."
    exit 1
fi

if [ "$(id -u)" -ne 0 ] && [ "$DRY_RUN" = false ]; then
    echo "ERROR: Must run as root."
    echo "  Run: sudo $0 $*"
    exit 1
fi

if [ "$LIVE_MODE" = true ]; then
    echo "Mode:    LIVE (modifying running system)"
    echo ""
    echo "WARNING: This will modify the running system!"
    echo "Press Ctrl+C within 5 seconds to abort..."
    sleep 5

    MOD_ARGS="/"
    [ "$DRY_RUN" = true ] && MOD_ARGS="--dry-run /"

    bash "$MOD_SCRIPT" $MOD_ARGS
    echo ""
    echo "Live modification complete. Reboot recommended."
    exit 0
fi

if [ ! -f "$S1_ROOTFS" ]; then
    echo "ERROR: S1 rootfs.img not found: $S1_ROOTFS"
    echo ""
    echo "Expected location:"
    echo "  resources/S1/firmwares/os-images/FLSUN-OS-S1-EMMC-3.0/rootfs.img"
    echo ""
    echo "Download FLSUN-OS S1 EMMC 3.0 and extract rootfs.img there."
    exit 1
fi

if [ ! -f "$MOD_SCRIPT" ]; then
    echo "ERROR: mod-rootfs-for-t1.sh not found: $MOD_SCRIPT"
    exit 1
fi

# ── Print Configuration ──────────────────────────────────────────────

echo "Configuration:"
echo "  Source:     $S1_ROOTFS ($(du -h "$S1_ROOTFS" | cut -f1))"
echo "  Output:     $OUTPUT_DIR/$OUTPUT_NAME"
echo "  Shrink:     $SHRINK"
echo "  Dry run:    $DRY_RUN"
echo ""

mkdir -p "$OUTPUT_DIR"
OUTPUT_PATH="$OUTPUT_DIR/$OUTPUT_NAME"

# ── Step 1: Copy S1 rootfs ──────────────────────────────────────────

echo "Step 1: Copying S1 rootfs as base..."
if [ "$DRY_RUN" = true ]; then
    echo "  [DRY] cp $S1_ROOTFS → $OUTPUT_PATH"
else
    cp --reflink=auto "$S1_ROOTFS" "$OUTPUT_PATH"
    echo "  ✓ Copied ($(du -h "$OUTPUT_PATH" | cut -f1))"
fi

# ── Step 2: Mount rootfs ────────────────────────────────────────────

MOUNT_POINT=$(mktemp -d /tmp/flsun-t1-rootfs.XXXXXX)
cleanup() {
    echo ""
    echo "Cleaning up..."
    if mountpoint -q "$MOUNT_POINT" 2>/dev/null; then
        sync
        umount "$MOUNT_POINT" || umount -l "$MOUNT_POINT"
    fi
    rmdir "$MOUNT_POINT" 2>/dev/null || true
}
trap cleanup EXIT

if [ "$DRY_RUN" = false ]; then
    echo ""
    echo "Step 2: Mounting rootfs at $MOUNT_POINT..."
    mount -o loop "$OUTPUT_PATH" "$MOUNT_POINT"
    echo "  ✓ Mounted"
else
    echo ""
    echo "Step 2: [DRY] Would mount rootfs at $MOUNT_POINT"
fi

# ── Step 3: Run mod-rootfs-for-t1.sh ────────────────────────────────

echo ""
echo "Step 3: Converting S1 rootfs to T1..."

MOD_ARGS="$MOUNT_POINT"
[ "$DRY_RUN" = true ] && MOD_ARGS="--dry-run $MOUNT_POINT"

bash "$MOD_SCRIPT" $MOD_ARGS

echo "  ✓ Rootfs converted to T1"

# ── Step 4: Unmount ──────────────────────────────────────────────────

if [ "$DRY_RUN" = false ]; then
    echo ""
    echo "Step 4: Unmounting..."
    sync
    umount "$MOUNT_POINT"
    rmdir "$MOUNT_POINT"
    # Prevent double-cleanup
    trap - EXIT
    echo "  ✓ Unmounted"
fi

# ── Step 5: Filesystem check ────────────────────────────────────────

if [ "$DRY_RUN" = false ]; then
    echo ""
    echo "Step 5: Checking filesystem integrity..."
    e2fsck -f -y "$OUTPUT_PATH" || true
    echo "  ✓ Filesystem check complete"
fi

# ── Step 6: Shrink (optional) ───────────────────────────────────────

if [ "$SHRINK" = true ] && [ "$DRY_RUN" = false ]; then
    echo ""
    echo "Step 6: Shrinking image to minimum size..."
    resize2fs -M "$OUTPUT_PATH"

    # Calculate new size and truncate file
    BLOCK_COUNT=$(dumpe2fs -h "$OUTPUT_PATH" 2>/dev/null | grep "Block count:" | awk '{print $3}')
    BLOCK_SIZE=$(dumpe2fs -h "$OUTPUT_PATH" 2>/dev/null | grep "Block size:" | awk '{print $3}')
    if [ -n "$BLOCK_COUNT" ] && [ -n "$BLOCK_SIZE" ]; then
        NEW_SIZE=$((BLOCK_COUNT * BLOCK_SIZE))
        truncate -s "$NEW_SIZE" "$OUTPUT_PATH"
        echo "  ✓ Shrunk to $(du -h "$OUTPUT_PATH" | cut -f1)"
    fi
fi

# ── Summary ──────────────────────────────────────────────────────────

echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "  T1 ROOTFS IMAGE COMPLETE"
echo ""
if [ "$DRY_RUN" = false ]; then
    echo "  Output:  $OUTPUT_PATH"
    echo "  Size:    $(du -h "$OUTPUT_PATH" | cut -f1)"
    echo ""
    echo "  Next steps:"
    echo "    1. Build kernel: python3 build/tools/build-images-t1.py --kernel"
    echo "    2. Flash to T1:  Use RKDevTool or dd to eMMC"
    echo "    3. Or build complete image: python3 build/tools/build-images-t1.py --complete"
else
    echo "  [DRY RUN] No files were modified."
fi
echo ""
echo "═══════════════════════════════════════════════════════════════"
