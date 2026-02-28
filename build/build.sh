#!/bin/bash
# FLSUN OS Build Script
# Builds a Debian 13 Trixie rootfs.img using debos
# ─────────────────────────────────────────────────
# Usage:
#   ./build.sh                    # Build with defaults (8 GB image)
#   ./build.sh --image-size 4GB   # Custom image size
#   ./build.sh --dry-run          # Validate recipe without building
#
# Prerequisites:
#   - Docker (recommended) or native debos installation
#   - At least 16 GB free disk space
#   - Internet connection for APT + git clone operations

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RECIPE="${SCRIPT_DIR}/flsun-os.yaml"
OUTPUT_DIR="${SCRIPT_DIR}/output"

# Defaults (can be overridden with debos -t flags)
IMAGE_SIZE="8GB"
HOSTNAME="FLSUN-OS"
USER="pi"
PASSWORD="flsun"
ROOT_PASSWORD="flsun"
SUITE="trixie"
ARCH="armhf"
MIRROR="http://deb.debian.org/debian"
DRY_RUN=false
USE_DOCKER=true

# ── Parse arguments ──────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
    case "$1" in
        --image-size)    IMAGE_SIZE="$2";    shift 2 ;;
        --hostname)      HOSTNAME="$2";      shift 2 ;;
        --user)          USER="$2";          shift 2 ;;
        --password)      PASSWORD="$2";      shift 2 ;;
        --root-password) ROOT_PASSWORD="$2"; shift 2 ;;
        --suite)         SUITE="$2";         shift 2 ;;
        --mirror)        MIRROR="$2";        shift 2 ;;
        --dry-run)       DRY_RUN=true;       shift ;;
        --no-docker)     USE_DOCKER=false;   shift ;;
        --help|-h)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --image-size SIZE    Root image size (default: 8GB)"
            echo "  --hostname NAME      Hostname (default: FLSUN-OS)"
            echo "  --user USER          Primary user (default: pi)"
            echo "  --password PASS      User password (default: flsun)"
            echo "  --root-password PASS Root password (default: flsun)"
            echo "  --suite SUITE        Debian suite (default: trixie)"
            echo "  --mirror URL         APT mirror URL"
            echo "  --dry-run            Validate recipe only"
            echo "  --no-docker          Use native debos instead of Docker"
            echo "  -h, --help           Show this help"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# ── Preflight checks ────────────────────────────────────────────────
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║              FLSUN OS Build System                         ║"
echo "║  Debian 13 Trixie (armhf) for Rockchip RV1126             ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""
echo "Configuration:"
echo "  Recipe:         ${RECIPE}"
echo "  Image size:     ${IMAGE_SIZE}"
echo "  Suite:          ${SUITE} (${ARCH})"
echo "  Hostname:       ${HOSTNAME}"
echo "  User:           ${USER}"
echo "  Output:         ${OUTPUT_DIR}/"
echo "  Docker:         ${USE_DOCKER}"
echo ""

if [ ! -f "${RECIPE}" ]; then
    echo "ERROR: Recipe not found: ${RECIPE}"
    exit 1
fi

mkdir -p "${OUTPUT_DIR}"

# ── Build template arguments ────────────────────────────────────────
DEBOS_ARGS=(
    -t "image_size:${IMAGE_SIZE}"
    -t "hostname:${HOSTNAME}"
    -t "user:${USER}"
    -t "password:${PASSWORD}"
    -t "root_password:${ROOT_PASSWORD}"
    -t "suite:${SUITE}"
    -t "arch:${ARCH}"
    -t "mirror:${MIRROR}"
)

if [ "${DRY_RUN}" = true ]; then
    DEBOS_ARGS+=("--dry-run")
    echo "── DRY RUN (recipe validation only) ──"
fi

# ── Build rootfs.img ────────────────────────────────────────────────
echo ""
echo "Starting debos build..."
echo "This may take 30-60 minutes depending on network speed."
echo ""

if [ "${USE_DOCKER}" = true ]; then
    # Docker-based build (works on any host OS including x86_64)
    if ! command -v docker &>/dev/null; then
        echo "ERROR: Docker not found. Install Docker or use --no-docker."
        exit 1
    fi

    docker run --rm \
        --device /dev/kvm \
        --user "$(id -u)" \
        --workdir /recipes \
        --mount "type=bind,source=${SCRIPT_DIR},destination=/recipes" \
        --security-opt label=disable \
        godebos/debos \
        "${DEBOS_ARGS[@]}" \
        /recipes/flsun-os.yaml

else
    # Native debos (requires Linux host with QEMU)
    if ! command -v debos &>/dev/null; then
        echo "ERROR: debos not found. Install with: go install github.com/go-debos/debos/cmd/debos@latest"
        exit 1
    fi

    cd "${SCRIPT_DIR}"
    debos "${DEBOS_ARGS[@]}" "${RECIPE}"
fi

# ── Post-build ──────────────────────────────────────────────────────
if [ "${DRY_RUN}" = true ]; then
    echo ""
    echo "Dry run complete. Recipe is valid."
    exit 0
fi

if [ -f "${SCRIPT_DIR}/rootfs.img" ]; then
    mv "${SCRIPT_DIR}/rootfs.img" "${OUTPUT_DIR}/rootfs.img"
    echo ""
    echo "════════════════════════════════════════════════════════════"
    echo "  BUILD COMPLETE"
    echo ""
    echo "  rootfs.img: ${OUTPUT_DIR}/rootfs.img"
    echo "  Size:       $(du -h "${OUTPUT_DIR}/rootfs.img" | cut -f1)"
    echo ""
    echo "  Next steps:"
    echo "    1. Build boot.img with ./build-boot-img.sh"
    echo "    2. Package for eMMC with ./package-emmc.sh"
    echo "    3. Or write rootfs.img to SD card partition directly"
    echo "════════════════════════════════════════════════════════════"
else
    echo ""
    echo "WARNING: rootfs.img not found in expected location."
    echo "Check debos output for errors."
    exit 1
fi
