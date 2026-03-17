#!/bin/bash
# FLSUN OS — Kernel .deb Package Builder
# Packages the kernel boot.img into a Debian package for apt-based updates
# ──────────────────────────────────────────────────────────────────────
# Usage:
#   ./package-kernel-deb.sh                     # Package S1 kernel (default)
#   ./package-kernel-deb.sh --target t1         # Package T1 kernel
#   ./package-kernel-deb.sh --version 6.1.115-1 # Override version
#   ./package-kernel-deb.sh --revision 2        # Override revision
#
# The FLSUN S1/T1 does NOT boot from /boot like standard Debian. The kernel
# lives in an Android boot.img (zImage + RSCE with DTB) written raw to the
# eMMC boot partition (mmcblk0p3). Standard linux-image packages won't work.
#
# This script creates a .deb that:
#   1. Ships boot.img to /usr/share/flsun-os-kernel/boot.img
#   2. On install (postinst), writes boot.img to /dev/mmcblk0p3 via dd
#   3. Keeps a backup of the previous boot.img (rollback support)
#   4. Provides an apt trigger so `apt upgrade` handles kernel updates
#
# The resulting .deb is intended for a custom APT repository, NOT Debian's.
#
# Prerequisites:
#   - build/output/boot.img (from build-kernel.sh)
#   - dpkg-deb (standard on Debian)
#
# Output:
#   build/output/flsun-os-kernel-{s1,t1}_{version}-{rev}_armhf.deb
#
# See docs/S1/research/13-apt-update-concept.md for the full update concept.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUTPUT_DIR="${SCRIPT_DIR}/output"

# ── Defaults ─────────────────────────────────────────────────────────
TARGET="s1"
VERSION=""
REVISION="1"

# ── Parse arguments ──────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
    case "$1" in
        --target)    TARGET="${2,,}"; shift 2 ;;
        --version)   VERSION="$2"; shift 2 ;;
        --revision)  REVISION="$2"; shift 2 ;;
        --help|-h)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --target s1|t1       Target printer (default: s1)"
            echo "  --version VERSION    Override kernel version (default: auto-detect)"
            echo "  --revision N         Package revision number (default: 1)"
            echo "  --help, -h           Show this help"
            exit 0
            ;;
        *)
            echo "Unknown option: $1 (use --help for usage)"
            exit 1
            ;;
    esac
done

# ── Validate inputs ──────────────────────────────────────────────────
BOOT_IMG="${OUTPUT_DIR}/boot.img"
if [ ! -f "${BOOT_IMG}" ]; then
    echo "ERROR: boot.img not found at ${BOOT_IMG}"
    echo ""
    echo "Build the kernel first:"
    echo "  ./build-kernel.sh --target ${TARGET}"
    exit 1
fi

if ! command -v dpkg-deb &>/dev/null; then
    echo "ERROR: dpkg-deb not found. Install dpkg:"
    echo "  sudo apt install dpkg"
    exit 1
fi

# Verify boot.img has Android header (magic: ANDROID!)
MAGIC=$(head -c 8 "${BOOT_IMG}" | tr -d '\0')
if [ "${MAGIC}" != "ANDROID!" ]; then
    echo "ERROR: ${BOOT_IMG} is not a valid Android boot image"
    echo "  Expected magic: ANDROID!, got: ${MAGIC}"
    exit 1
fi

# ── Auto-detect version from zImage if not specified ─────────────────
if [ -z "${VERSION}" ]; then
    KERNEL_DIR="${SCRIPT_DIR}/../kernel"
    if [ -f "${KERNEL_DIR}/Makefile" ]; then
        VERSION=$(head -5 "${KERNEL_DIR}/Makefile" | \
            awk '/^VERSION|^PATCHLEVEL|^SUBLEVEL/ {v=v $3"."} END {sub(/\.$/, "", v); print v}')
    else
        # Fallback: extract from strings in boot.img
        VERSION=$(strings "${BOOT_IMG}" | grep -oP '\d+\.\d+\.\d+flsun' | head -1 || true)
    fi
    if [ -z "${VERSION}" ]; then
        echo "ERROR: Could not detect kernel version. Specify with --version."
        exit 1
    fi
fi

# ── Package metadata ─────────────────────────────────────────────────
PKG_NAME="flsun-os-kernel-${TARGET}"
PKG_VERSION="${VERSION}-${REVISION}"
PKG_ARCH="armhf"
BOOT_IMG_SIZE=$(stat -c%s "${BOOT_IMG}" 2>/dev/null || stat -f%z "${BOOT_IMG}")
INSTALLED_SIZE=$(( BOOT_IMG_SIZE / 1024 + 1 ))  # KB, rounded up

# Boot partition device — same for S1 and T1 (mmcblk0p3)
BOOT_PARTITION="/dev/mmcblk0p3"

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║          FLSUN OS Kernel .deb Packager                     ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""
echo "  Package:     ${PKG_NAME}"
echo "  Version:     ${PKG_VERSION}"
echo "  Target:      ${TARGET^^}"
echo "  boot.img:    ${BOOT_IMG_SIZE} bytes"
echo "  Boot device: ${BOOT_PARTITION}"
echo ""

# ── Build package tree ───────────────────────────────────────────────
DEB_DIR="${OUTPUT_DIR}/${PKG_NAME}_${PKG_VERSION}_${PKG_ARCH}"
rm -rf "${DEB_DIR}"
mkdir -p "${DEB_DIR}/DEBIAN"
mkdir -p "${DEB_DIR}/usr/share/flsun-os-kernel"

# Copy boot.img into package
cp "${BOOT_IMG}" "${DEB_DIR}/usr/share/flsun-os-kernel/boot.img"

# ── DEBIAN/control ───────────────────────────────────────────────────
if [ "${TARGET}" = "t1" ]; then
    CONFLICTS="flsun-os-kernel-s1"
    DESCRIPTION_HW="FLSUN T1 (Rockchip RV1109, 800×480 display)"
else
    CONFLICTS="flsun-os-kernel-t1"
    DESCRIPTION_HW="FLSUN S1 (Rockchip RV1126, 1024×600 display)"
fi

cat > "${DEB_DIR}/DEBIAN/control" << EOF
Package: ${PKG_NAME}
Version: ${PKG_VERSION}
Architecture: ${PKG_ARCH}
Maintainer: FLSUN OS <flsun-os@localhost>
Installed-Size: ${INSTALLED_SIZE}
Conflicts: ${CONFLICTS}
Provides: flsun-os-kernel
Replaces: ${CONFLICTS}
Section: kernel
Priority: required
Homepage: https://github.com/Guilouz/FLSUN-S1-Open-Source-Edition
Description: FLSUN OS kernel boot image for ${DESCRIPTION_HW}
 Android-format boot.img (zImage + DTB) for the FLSUN eMMC boot
 partition. This is NOT a standard linux-image package — the FLSUN
 printers use Rockchip's Android boot format, not /boot or extlinux.
 .
 On install, this package writes boot.img directly to ${BOOT_PARTITION}
 (the eMMC boot partition). A backup of the previous boot.img is saved
 to /usr/share/flsun-os-kernel/boot.img.bak for rollback.
 .
 Kernel: Linux ${VERSION} (armbian/linux-rockchip, branch rk-6.1-rkr5.1)
 Format: Android mkbootimg (ANDROID! magic) + RSCE resource container
EOF

# ── DEBIAN/preinst — backup current boot partition ───────────────────
cat > "${DEB_DIR}/DEBIAN/preinst" << 'PREINST'
#!/bin/bash
# Back up the current boot partition before writing the new one.
# This allows rollback via: dd if=/usr/share/flsun-os-kernel/boot.img.bak of=/dev/mmcblk0p3

set -e

BOOT_PARTITION="/dev/mmcblk0p3"
BACKUP_DIR="/usr/share/flsun-os-kernel"

if [ ! -b "${BOOT_PARTITION}" ]; then
    echo "WARNING: Boot partition ${BOOT_PARTITION} not found."
    echo "  This package is designed for FLSUN S1/T1 printers with eMMC."
    echo "  Skipping backup — boot.img will be installed but not flashed."
    exit 0
fi

mkdir -p "${BACKUP_DIR}"

# Read the current boot.img size from the partition (Android header contains kernel_size)
# Only back up the meaningful portion, not the entire 112 MB partition
MAGIC=$(dd if="${BOOT_PARTITION}" bs=8 count=1 2>/dev/null | tr -d '\0')
if [ "${MAGIC}" = "ANDROID!" ]; then
    # Read total image size from header fields to determine actual content size
    # For safety, back up a generous 16 MB (boot.img is typically ~9 MB)
    echo "Backing up current boot partition..."
    dd if="${BOOT_PARTITION}" of="${BACKUP_DIR}/boot.img.bak" bs=1M count=16 status=none
    echo "  Backup saved to ${BACKUP_DIR}/boot.img.bak"
else
    echo "WARNING: Boot partition does not contain an Android boot image."
    echo "  Skipping backup (partition may be empty or use a different format)."
fi

exit 0
PREINST
chmod 0755 "${DEB_DIR}/DEBIAN/preinst"

# ── DEBIAN/postinst — write boot.img to eMMC ────────────────────────
cat > "${DEB_DIR}/DEBIAN/postinst" << 'POSTINST'
#!/bin/bash
# Flash the new boot.img to the eMMC boot partition.
#
# FLSUN S1/T1 eMMC layout:
#   mmcblk0p3 = boot partition (Android boot.img with zImage + DTB)
#
# This replaces the kernel + device tree in one atomic dd write.

set -e

BOOT_PARTITION="/dev/mmcblk0p3"
BOOT_IMG="/usr/share/flsun-os-kernel/boot.img"

case "$1" in
    configure)
        if [ ! -f "${BOOT_IMG}" ]; then
            echo "ERROR: boot.img not found at ${BOOT_IMG}"
            exit 1
        fi

        if [ ! -b "${BOOT_PARTITION}" ]; then
            echo "WARNING: Boot partition ${BOOT_PARTITION} not found."
            echo "  boot.img installed to ${BOOT_IMG} but NOT flashed."
            echo "  Flash manually on the printer:"
            echo "    dd if=${BOOT_IMG} of=${BOOT_PARTITION} bs=4M"
            exit 0
        fi

        echo "Flashing kernel to boot partition..."
        echo "  Source: ${BOOT_IMG} ($(stat -c%s "${BOOT_IMG}") bytes)"
        echo "  Target: ${BOOT_PARTITION}"

        # Write boot.img to the boot partition
        dd if="${BOOT_IMG}" of="${BOOT_PARTITION}" bs=4M status=progress
        sync

        echo ""
        echo "Kernel update installed successfully."
        echo "Reboot to activate the new kernel."
        ;;

    abort-upgrade|abort-remove|abort-deconfigure)
        ;;

    *)
        echo "postinst called with unknown argument: $1" >&2
        exit 1
        ;;
esac

exit 0
POSTINST
chmod 0755 "${DEB_DIR}/DEBIAN/postinst"

# ── DEBIAN/postrm — cleanup on purge ────────────────────────────────
cat > "${DEB_DIR}/DEBIAN/postrm" << 'POSTRM'
#!/bin/bash
# On purge, remove the backup file.
# On remove, leave the backup in place (rollback safety).

set -e

case "$1" in
    purge)
        rm -f /usr/share/flsun-os-kernel/boot.img.bak
        rmdir --ignore-fail-on-non-empty /usr/share/flsun-os-kernel 2>/dev/null || true
        ;;
    remove|upgrade|failed-upgrade|abort-install|abort-upgrade|disappear)
        ;;
    *)
        echo "postrm called with unknown argument: $1" >&2
        exit 1
        ;;
esac

exit 0
POSTRM
chmod 0755 "${DEB_DIR}/DEBIAN/postrm"

# ── DEBIAN/conffiles (empty — no conffiles) ──────────────────────────
# boot.img is data, not configuration. No conffiles needed.

# ── Build .deb ───────────────────────────────────────────────────────
DEB_FILE="${OUTPUT_DIR}/${PKG_NAME}_${PKG_VERSION}_${PKG_ARCH}.deb"
dpkg-deb --build --root-owner-group "${DEB_DIR}" "${DEB_FILE}"

# ── Cleanup ──────────────────────────────────────────────────────────
rm -rf "${DEB_DIR}"

# ── Summary ──────────────────────────────────────────────────────────
DEB_SIZE=$(stat -c%s "${DEB_FILE}" 2>/dev/null || stat -f%z "${DEB_FILE}")

echo ""
echo "════════════════════════════════════════════════════════════"
echo "  KERNEL .deb PACKAGE CREATED"
echo ""
echo "  ${DEB_FILE}"
echo "  Size: $(du -h "${DEB_FILE}" | cut -f1) (${DEB_SIZE} bytes)"
echo ""
echo "  Install on printer:"
echo "    sudo dpkg -i ${PKG_NAME}_${PKG_VERSION}_${PKG_ARCH}.deb"
echo ""
echo "  Or add to a custom APT repository and:"
echo "    sudo apt update && sudo apt install ${PKG_NAME}"
echo ""
echo "  Rollback to previous kernel:"
echo "    sudo dd if=/usr/share/flsun-os-kernel/boot.img.bak of=/dev/mmcblk0p3 bs=4M"
echo "    sudo reboot"
echo "════════════════════════════════════════════════════════════"
