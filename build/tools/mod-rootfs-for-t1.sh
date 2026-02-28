#!/bin/bash
# ─────────────────────────────────────────────────────────────
# mod-rootfs-for-t1.sh — Convert S1 FLSUN-OS 3.0 rootfs for T1
# ─────────────────────────────────────────────────────────────
#
# Modifies an S1 rootfs.img (ext4) to run on FLSUN T1 hardware.
# Must be run as root on Linux (or WSL) with the rootfs.img mounted.
#
# What it changes:
#   1. Klipper configs: Replace S1 configs with T1 ported configs
#   2. Moonraker config: Replace with T1 version (no drying box)
#   3. KlipperScreen config: Replace with T1 version (800×480)
#   4. Systemd services: Remove drying-box, add klipper-mcu
#   5. first-boot.sh: T1 hostname, no easy-installer, no JSON restore
#   6. rc.local: Add PWM export, remove brightness file ref
#   7. Klipper fork: Switch from Guilouz/S1 to garethky/load-cell-probe
#   8. KlipperScreen fork: Switch from Guilouz/S1 to upstream
#   9. klipper_mcu: Build and install Linux MCU process
#  10. SciPy: Install into klippy-env (needed for load cell probe)
#  11. Remove S1-specific files (drying-box, flsun-os deps, etc.)
#
# This script can run in two modes:
#   - OFFLINE: Operates on a mounted rootfs.img (for image building)
#   - LIVE:    Runs directly on the T1 after booting the S1 image
#              (since the S1 image boots on T1 hardware)
#
# Usage:
#   # Offline mode (mounted rootfs):
#   sudo ./mod-rootfs-for-t1.sh /mnt/rootfs
#
#   # Live mode (running on T1):
#   sudo ./mod-rootfs-for-t1.sh /
#
#   # Dry-run (show what would change):
#   sudo ./mod-rootfs-for-t1.sh --dry-run /mnt/rootfs
#
# Requirements:
#   - Root access
#   - T1 ported configs at resources/T1/klipper-configs/ported/
#   - T1 build overlays at build/overlays-t1/
#   - Internet access (for live mode git operations)
#
# ─────────────────────────────────────────────────────────────

set -euo pipefail

# ── Configuration ──
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
T1_CONFIGS="$REPO_ROOT/resources/T1/klipper-configs/ported"
T1_OVERLAYS="$REPO_ROOT/build/overlays-t1"

DRY_RUN=false
LIVE_MODE=false

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# ── Functions ──

log_info()  { echo -e "${GREEN}[INFO]${NC} $*"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*"; }
log_step()  { echo -e "${BLUE}[STEP]${NC} $*"; }

usage() {
    echo "Usage: $0 [--dry-run] <rootfs_path>"
    echo ""
    echo "  <rootfs_path>  Path to mounted rootfs (e.g., /mnt/rootfs or / for live mode)"
    echo "  --dry-run      Show what would be changed without modifying files"
    echo ""
    echo "Examples:"
    echo "  sudo $0 /mnt/rootfs       # Offline: modify mounted rootfs image"
    echo "  sudo $0 /                 # Live: modify running system (on T1)"
    echo "  sudo $0 --dry-run /mnt/rootfs"
    exit 1
}

do_copy() {
    local src="$1" dst="$2"
    if $DRY_RUN; then
        echo "  [DRY] cp $src → $dst"
    else
        mkdir -p "$(dirname "$dst")"
        cp -f "$src" "$dst"
    fi
}

do_rm() {
    local target="$1"
    if $DRY_RUN; then
        echo "  [DRY] rm $target"
    else
        rm -f "$target"
    fi
}

do_ln() {
    local target="$1" link_path="$2"
    if $DRY_RUN; then
        echo "  [DRY] ln -sf $target $link_path"
    else
        ln -sf "$target" "$link_path"
    fi
}

do_chmod() {
    local mode="$1" file="$2"
    if $DRY_RUN; then
        echo "  [DRY] chmod $mode $file"
    else
        chmod "$mode" "$file"
    fi
}

do_systemctl() {
    local action="$1" service="$2"
    if $DRY_RUN; then
        echo "  [DRY] systemctl $action $service"
    elif $LIVE_MODE; then
        systemctl "$action" "$service" 2>/dev/null || true
    else
        # Offline: can't systemctl, use symlinks
        local svc_file="$ROOT/etc/systemd/system/$service"
        if [ "$action" = "enable" ] && [ -f "$svc_file" ]; then
            local wants_dir="$ROOT/etc/systemd/system/multi-user.target.wants"
            mkdir -p "$wants_dir"
            ln -sf "../$service" "$wants_dir/$service"
        elif [ "$action" = "disable" ]; then
            rm -f "$ROOT/etc/systemd/system/multi-user.target.wants/$service"
        fi
    fi
}

check_prerequisites() {
    log_step "Checking prerequisites..."

    if [ ! -d "$T1_CONFIGS" ]; then
        log_error "T1 ported configs not found at: $T1_CONFIGS"
        exit 1
    fi

    if [ ! -d "$T1_OVERLAYS" ]; then
        log_error "T1 build overlays not found at: $T1_OVERLAYS"
        exit 1
    fi

    # Verify essential T1 config files exist
    local required_files=(
        "$T1_CONFIGS/printer.cfg"
        "$T1_CONFIGS/config.cfg"
        "$T1_CONFIGS/moonraker.conf"
        "$T1_CONFIGS/KlipperScreen.conf"
        "$T1_CONFIGS/Configurations/macros.cfg"
        "$T1_CONFIGS/Configurations/fan-stock.cfg"
        "$T1_CONFIGS/Configurations/fan-silent-kit.cfg"
        "$T1_CONFIGS/Configurations/led-stock.cfg"
        "$T1_CONFIGS/Configurations/filament-sensor-stock.cfg"
    )
    for f in "${required_files[@]}"; do
        if [ ! -f "$f" ]; then
            log_error "Required config file missing: $f"
            exit 1
        fi
    done

    # Verify rootfs looks like a FLSUN-OS installation
    if [ ! -d "$ROOT/home/pi/klipper" ]; then
        log_error "Not a valid FLSUN-OS rootfs: /home/pi/klipper not found"
        exit 1
    fi

    if [ ! -d "$ROOT/home/pi/printer_data/config" ]; then
        log_error "Not a valid FLSUN-OS rootfs: /home/pi/printer_data/config not found"
        exit 1
    fi

    log_info "Prerequisites OK"
}

# ── Step 1: Replace Klipper Configs ──

step_klipper_configs() {
    log_step "Step 1: Replacing Klipper configs with T1 versions..."

    local config_dir="$ROOT/home/pi/printer_data/config"

    # Replace main printer config
    do_copy "$T1_CONFIGS/printer.cfg" "$config_dir/printer.cfg"

    # Replace config selector
    do_copy "$T1_CONFIGS/config.cfg" "$config_dir/config.cfg"

    # Replace configuration includes
    mkdir -p "$config_dir/Configurations" 2>/dev/null || true
    do_copy "$T1_CONFIGS/Configurations/macros.cfg" "$config_dir/Configurations/macros.cfg"
    do_copy "$T1_CONFIGS/Configurations/fan-stock.cfg" "$config_dir/Configurations/fan-stock.cfg"
    do_copy "$T1_CONFIGS/Configurations/fan-silent-kit.cfg" "$config_dir/Configurations/fan-silent-kit.cfg"
    do_copy "$T1_CONFIGS/Configurations/led-stock.cfg" "$config_dir/Configurations/led-stock.cfg"
    do_copy "$T1_CONFIGS/Configurations/filament-sensor-stock.cfg" "$config_dir/Configurations/filament-sensor-stock.cfg"

    # Remove S1-specific config files that T1 doesn't use
    local s1_only_files=(
        "Configurations/flsun-os.cfg"
        "Configurations/camera-control.cfg"
        "Configurations/led-mmb-cubic.cfg"
        "Configurations/temp-sensor-mmb-cubic.cfg"
        "Configurations/filament-sensor-sfs.cfg"
    )
    for f in "${s1_only_files[@]}"; do
        if [ -f "$config_dir/$f" ]; then
            log_info "  Removing S1-specific: $f"
            do_rm "$config_dir/$f"
        fi
    done

    log_info "Klipper configs replaced"
}

# ── Step 2: Replace Moonraker Config ──

step_moonraker_config() {
    log_step "Step 2: Replacing Moonraker config with T1 version..."

    local config_dir="$ROOT/home/pi/printer_data/config"
    do_copy "$T1_CONFIGS/moonraker.conf" "$config_dir/moonraker.conf"

    log_info "Moonraker config replaced"
}

# ── Step 3: Replace KlipperScreen Config ──

step_klipperscreen_config() {
    log_step "Step 3: Replacing KlipperScreen config with T1 version..."

    local config_dir="$ROOT/home/pi/printer_data/config"
    do_copy "$T1_CONFIGS/KlipperScreen.conf" "$config_dir/KlipperScreen.conf"

    log_info "KlipperScreen config replaced"
}

# ── Step 4: Update Systemd Services ──

step_systemd_services() {
    log_step "Step 4: Updating systemd services..."

    local svc_dir="$ROOT/etc/systemd/system"

    # Remove S1-specific services
    if [ -f "$svc_dir/drying-box.service" ]; then
        log_info "  Disabling and removing drying-box.service"
        do_systemctl disable "drying-box.service"
        do_rm "$svc_dir/drying-box.service"
    fi

    if [ -f "$svc_dir/FLSUN-OS-Dependencies.service" ]; then
        log_info "  Disabling and removing FLSUN-OS-Dependencies.service"
        do_systemctl disable "FLSUN-OS-Dependencies.service"
        do_rm "$svc_dir/FLSUN-OS-Dependencies.service"
    fi

    # Add klipper-mcu service (for host MCU — caselight PWM)
    if [ -f "$T1_OVERLAYS/system/etc/systemd/system/klipper-mcu.service" ]; then
        log_info "  Adding klipper-mcu.service"
        do_copy "$T1_OVERLAYS/system/etc/systemd/system/klipper-mcu.service" \
                "$svc_dir/klipper-mcu.service"
        do_systemctl enable "klipper-mcu.service"
    fi

    # Update existing services (they're identical for S1/T1 except the comment header)
    # klipper.service, moonraker.service, KlipperScreen.service — keep as-is
    # webcamd.service — keep as-is (camera may or may not be present)
    # usb-mount@.service — keep as-is

    log_info "Systemd services updated"
}

# ── Step 5: Update first-boot.sh ──

step_first_boot() {
    log_step "Step 5: Updating first-boot.sh for T1..."

    local first_boot="$ROOT/etc/init.d/first-boot.sh"

    if [ -f "$T1_OVERLAYS/system/etc/init.d/first-boot.sh" ]; then
        do_copy "$T1_OVERLAYS/system/etc/init.d/first-boot.sh" "$first_boot"
        do_chmod "+x" "$first_boot"
    else
        log_warn "T1 first-boot.sh overlay not found, patching in-place..."
        if [ -f "$first_boot" ] && ! $DRY_RUN; then
            # Patch hostname from FLSUN-S1 to FLSUN-T1
            sed -i 's/FLSUN-S1-/FLSUN-T1-/g' "$first_boot"

            # Remove easy-installer symlink creation
            sed -i '/easy-installer/d' "$first_boot"

            # Remove JSON restore function and calls
            sed -i '/restoreJSON/d' "$first_boot"
            sed -i '/Backup-Mainsail/d' "$first_boot"
            sed -i '/Backup-Fluidd/d' "$first_boot"
        fi
    fi

    log_info "first-boot.sh updated for T1"
}

# ── Step 6: Update rc.local ──

step_rc_local() {
    log_step "Step 6: Updating rc.local for T1..."

    local rc_local="$ROOT/etc/rc.local"

    if [ -f "$T1_OVERLAYS/system/etc/rc.local" ]; then
        do_copy "$T1_OVERLAYS/system/etc/rc.local" "$rc_local"
        do_chmod "+x" "$rc_local"
    else
        log_warn "T1 rc.local overlay not found, patching in-place..."
        if [ -f "$rc_local" ] && ! $DRY_RUN; then
            # Remove S1-specific brightness file reference
            sed -i '/flsun-os\/system\/brightness/d' "$rc_local"
            sed -i '/cat.*brightness/d' "$rc_local"

            # Remove usb-mount-delete-unused (S1-specific)
            sed -i '/usb-mount-delete-unused/d' "$rc_local"

            # Add PWM export for caselight before the exit line
            sed -i '/^exit 0/i\
# T1: Export PWM channels for caselight (pwm0) and optional beeper (pwm1)\
if [ -d /sys/class/pwm/pwmchip0 ]; then\
\techo 0 > /sys/class/pwm/pwmchip0/export 2>/dev/null || true\
\techo 1 > /sys/class/pwm/pwmchip0/export 2>/dev/null || true\
fi\
\
# Backlight brightness\
if [ -f /sys/devices/platform/backlight/backlight/backlight/brightness ]; then\
\techo 100 > /sys/devices/platform/backlight/backlight/backlight/brightness\
fi' "$rc_local"
        fi
    fi

    log_info "rc.local updated for T1"
}

# ── Step 7: Switch Klipper Fork ──

step_klipper_fork() {
    log_step "Step 7: Switching Klipper fork for T1..."

    local klipper_dir="$ROOT/home/pi/klipper"

    if ! $LIVE_MODE; then
        log_warn "Offline mode: Cannot switch git remotes. Will create a marker file."
        if ! $DRY_RUN; then
            cat > "$ROOT/home/pi/.t1-klipper-switch-pending" << 'EOF'
# T1 Klipper Fork Switch — Run these commands after first boot:
#
# The T1 requires the garethky/klipper fork for load_cell_probe support.
# The S1 uses Guilouz/Klipper-Flsun-S1 which has features not available
# in the garethky fork (auto pressure advance, enhanced delta calibrate).
#
# To switch:
cd ~/klipper
git remote set-url origin https://github.com/garethky/klipper.git
git fetch origin
git checkout load-cell-probe-community-testing
git reset --hard origin/load-cell-probe-community-testing
sudo systemctl restart klipper

# To install SciPy (required for load cell notch filter):
~/klippy-env/bin/pip install scipy
EOF
        fi
        log_info "Created ~/.t1-klipper-switch-pending marker file"
        return
    fi

    # Live mode: actually switch the fork
    if [ -d "$klipper_dir/.git" ]; then
        log_info "  Switching Klipper remote to garethky/klipper..."
        if ! $DRY_RUN; then
            cd "$klipper_dir"
            # Save current remote for reference
            local old_remote
            old_remote=$(git remote get-url origin 2>/dev/null || echo "unknown")
            echo "# Previous Klipper remote: $old_remote" > "$ROOT/home/pi/.klipper-remote-backup"

            git remote set-url origin https://github.com/garethky/klipper.git
            git fetch origin
            git checkout load-cell-probe-community-testing
            git reset --hard origin/load-cell-probe-community-testing
        fi
        log_info "  Klipper fork switched to garethky/klipper (load-cell-probe branch)"
    else
        log_warn "Klipper directory not a git repo: $klipper_dir"
    fi
}

# ── Step 8: Switch KlipperScreen Fork ──

step_klipperscreen_fork() {
    log_step "Step 8: Switching KlipperScreen fork for T1..."

    local ks_dir="$ROOT/home/pi/KlipperScreen"

    if ! $LIVE_MODE; then
        log_warn "Offline mode: Cannot switch git remotes. Will append to marker file."
        if ! $DRY_RUN; then
            cat >> "$ROOT/home/pi/.t1-klipper-switch-pending" << 'EOF'

# KlipperScreen: Switch from S1 fork to upstream
cd ~/KlipperScreen
git remote set-url origin https://github.com/KlipperScreen/KlipperScreen.git
git fetch origin
git checkout master
git reset --hard origin/master
sudo systemctl restart KlipperScreen
EOF
        fi
        return
    fi

    # Live mode
    if [ -d "$ks_dir/.git" ]; then
        log_info "  Switching KlipperScreen to upstream..."
        if ! $DRY_RUN; then
            cd "$ks_dir"
            git remote set-url origin https://github.com/KlipperScreen/KlipperScreen.git
            git fetch origin
            git checkout master
            git reset --hard origin/master
        fi
        log_info "  KlipperScreen switched to upstream"
    fi
}

# ── Step 9: Build klipper_mcu ──

step_klipper_mcu() {
    log_step "Step 9: Setting up klipper_mcu (Linux MCU process)..."

    if ! $LIVE_MODE; then
        log_warn "Offline mode: Cannot build klipper_mcu. Will be built on first boot."
        if ! $DRY_RUN; then
            cat >> "$ROOT/home/pi/.t1-klipper-switch-pending" << 'EOF'

# Build and install klipper_mcu (Linux MCU process for host PWM):
cd ~/klipper
make clean KCONFIG_CONFIG=.config-mcu-host
cat > .config-mcu-host << 'HOSTCFG'
CONFIG_LOW_LEVEL_OPTIONS=y
CONFIG_MACH_LINUX=y
CONFIG_CLOCK_FREQ=50000000
HOSTCFG
make KCONFIG_CONFIG=.config-mcu-host -j$(nproc)
sudo cp out/klipper.elf /usr/local/bin/klipper_mcu
sudo systemctl enable klipper-mcu
sudo systemctl start klipper-mcu
EOF
        fi
        return
    fi

    # Live mode: build klipper_mcu
    local klipper_dir="$ROOT/home/pi/klipper"
    if [ -d "$klipper_dir" ] && ! $DRY_RUN; then
        log_info "  Building klipper_mcu..."
        cd "$klipper_dir"
        make clean KCONFIG_CONFIG=.config-mcu-host 2>/dev/null || true

        # Create host MCU config
        cat > .config-mcu-host << 'HOSTCFG'
CONFIG_LOW_LEVEL_OPTIONS=y
CONFIG_MACH_LINUX=y
CONFIG_CLOCK_FREQ=50000000
HOSTCFG

        make KCONFIG_CONFIG=.config-mcu-host -j"$(nproc)"
        cp out/klipper.elf /usr/local/bin/klipper_mcu
        chmod +x /usr/local/bin/klipper_mcu

        systemctl enable klipper-mcu
        systemctl restart klipper-mcu
        log_info "  klipper_mcu built and installed"
    fi
}

# ── Step 10: Install SciPy ──

step_scipy() {
    log_step "Step 10: Installing SciPy into klippy-env..."

    if ! $LIVE_MODE; then
        log_warn "Offline mode: Cannot install Python packages. Deferred to first boot."
        return
    fi

    local pip="$ROOT/home/pi/klippy-env/bin/pip"
    if [ -x "$pip" ] && ! $DRY_RUN; then
        log_info "  Installing scipy (this may take a while on ARM)..."
        "$pip" install scipy
        log_info "  SciPy installed"
    else
        log_warn "klippy-env pip not found at: $pip"
    fi
}

# ── Step 11: Remove S1-Specific Files ──

step_remove_s1_files() {
    log_step "Step 11: Removing S1-specific files..."

    # Remove drying-box scripts
    local flsun_os_dir="$ROOT/home/pi/flsun-os"
    if [ -d "$flsun_os_dir" ]; then
        # Remove drying-box info script
        if [ -f "$flsun_os_dir/system/drying-box-info.sh" ]; then
            log_info "  Removing drying-box-info.sh"
            do_rm "$flsun_os_dir/system/drying-box-info.sh"
        fi

        # Remove S1-specific installer files (JSON backups for Web UI restore)
        if [ -d "$flsun_os_dir/installer/files" ]; then
            local json_files=(
                "$flsun_os_dir/installer/files/Backup-Mainsail-FLSUN-S1.json"
                "$flsun_os_dir/installer/files/Backup-Fluidd-FLSUN-S1.json"
            )
            for f in "${json_files[@]}"; do
                if [ -f "$f" ]; then
                    log_info "  Removing $(basename "$f")"
                    do_rm "$f"
                fi
            done
        fi
    fi

    # Remove easy-installer symlink (S1-specific)
    if [ -L "$ROOT/usr/bin/easy-installer" ]; then
        log_info "  Removing easy-installer symlink"
        do_rm "$ROOT/usr/bin/easy-installer"
    fi

    # Remove drying box SHM files
    do_rm "$ROOT/dev/shm/drying_box.json" 2>/dev/null || true
    do_rm "$ROOT/dev/shm/drying_box_temp" 2>/dev/null || true

    # Remove S1-specific brightness file
    if [ -f "$flsun_os_dir/system/brightness" ]; then
        log_info "  Removing brightness state file"
        do_rm "$flsun_os_dir/system/brightness"
    fi

    log_info "S1-specific files removed"
}

# ── Step 12: Update Hostname & Branding ──

step_hostname() {
    log_step "Step 12: Updating hostname and branding for T1..."

    # Update /etc/hostname
    local hostname_file="$ROOT/etc/hostname"
    if [ -f "$hostname_file" ] && ! $DRY_RUN; then
        sed -i 's/FLSUN-S1/FLSUN-T1/g' "$hostname_file"
    fi

    # Update /etc/hosts
    local hosts_file="$ROOT/etc/hosts"
    if [ -f "$hosts_file" ] && ! $DRY_RUN; then
        sed -i 's/FLSUN-S1/FLSUN-T1/g' "$hosts_file"
    fi

    # Update /etc/motd (message of the day)
    local motd_file="$ROOT/etc/motd"
    if [ -f "$motd_file" ] && ! $DRY_RUN; then
        sed -i 's/FLSUN S1/FLSUN T1/g' "$motd_file"
        sed -i 's/FLSUN-S1/FLSUN-T1/g' "$motd_file"
    fi

    # Update os-release
    local os_release="$ROOT/etc/os-release"
    if [ -f "$os_release" ] && ! $DRY_RUN; then
        sed -i 's/FLSUN S1/FLSUN T1/g' "$os_release"
        sed -i 's/FLSUN-S1/FLSUN-T1/g' "$os_release"
    fi

    log_info "Hostname and branding updated for T1"
}

# ── Step 13: Set Permissions ──

step_permissions() {
    log_step "Step 13: Setting correct file permissions..."

    local config_dir="$ROOT/home/pi/printer_data/config"
    local pi_uid pi_gid

    # Find pi user's UID/GID from the rootfs passwd
    if [ -f "$ROOT/etc/passwd" ]; then
        pi_uid=$(grep "^pi:" "$ROOT/etc/passwd" | cut -d: -f3)
        pi_gid=$(grep "^pi:" "$ROOT/etc/passwd" | cut -d: -f4)
    else
        pi_uid=1000
        pi_gid=1000
    fi

    if ! $DRY_RUN; then
        # Configs owned by pi
        chown -R "$pi_uid:$pi_gid" "$config_dir" 2>/dev/null || true
        chown -R "$pi_uid:$pi_gid" "$ROOT/home/pi/.t1-klipper-switch-pending" 2>/dev/null || true

        # Services readable by all
        chmod 644 "$ROOT/etc/systemd/system/klipper-mcu.service" 2>/dev/null || true

        # Init scripts executable
        chmod +x "$ROOT/etc/init.d/first-boot.sh" 2>/dev/null || true
        chmod +x "$ROOT/etc/rc.local" 2>/dev/null || true
    fi

    log_info "Permissions set"
}

# ── Summary ──

print_summary() {
    echo ""
    echo "═══════════════════════════════════════════════════════════════"
    echo "  FLSUN-OS T1 Rootfs Modification Complete"
    echo "═══════════════════════════════════════════════════════════════"
    echo ""
    echo "  Target rootfs:  $ROOT"
    echo "  Mode:           $(if $LIVE_MODE; then echo "LIVE"; else echo "OFFLINE"; fi)"
    echo "  Dry run:        $(if $DRY_RUN; then echo "YES"; else echo "no"; fi)"
    echo ""

    if ! $LIVE_MODE; then
        echo "  ⚠ OFFLINE MODE — The following must be done after first boot:"
        echo "    1. Switch Klipper fork (see ~/.t1-klipper-switch-pending)"
        echo "    2. Switch KlipperScreen fork"
        echo "    3. Build klipper_mcu (Linux MCU process)"
        echo "    4. Install SciPy into klippy-env"
        echo ""
        echo "  Run:  cat ~/.t1-klipper-switch-pending"
        echo ""
    fi

    echo "  Files modified:"
    echo "    - printer_data/config/printer.cfg (T1 hardware definitions)"
    echo "    - printer_data/config/config.cfg (T1 component includes)"
    echo "    - printer_data/config/moonraker.conf (no drying box, garethky fork)"
    echo "    - printer_data/config/KlipperScreen.conf (800x480, T1 branding)"
    echo "    - printer_data/config/Configurations/*.cfg (T1 fans, LEDs, sensors)"
    echo "    - /etc/init.d/first-boot.sh (T1 hostname, no JSON restore)"
    echo "    - /etc/rc.local (PWM export for caselight)"
    echo "    - /etc/systemd/system/ (removed drying-box, added klipper-mcu)"
    echo ""
    echo "  To flash this image:"
    echo "    1. Use build/tools/patch-dtb-for-t1.py to create T1 DTB"
    echo "    2. Use build/tools/build-boot-img-t1.py to create boot.img"
    echo "    3. Flash boot.img + rootfs.img to T1 eMMC via RKDevTool"
    echo ""
    echo "═══════════════════════════════════════════════════════════════"
}

# ── Main ──

main() {
    echo ""
    echo "═══════════════════════════════════════════════════════════════"
    echo "  FLSUN-OS S1→T1 Rootfs Modifier"
    echo "═══════════════════════════════════════════════════════════════"
    echo ""

    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --dry-run)
                DRY_RUN=true
                shift
                ;;
            -h|--help)
                usage
                ;;
            *)
                ROOT="$1"
                shift
                ;;
        esac
    done

    if [ -z "${ROOT:-}" ]; then
        usage
    fi

    # Detect live vs offline mode
    if [ "$ROOT" = "/" ]; then
        LIVE_MODE=true
        log_info "Running in LIVE mode (modifying running system)"
    else
        LIVE_MODE=false
        log_info "Running in OFFLINE mode (modifying mounted rootfs at $ROOT)"
    fi

    # Trim trailing slash (but not if root /)
    if [ "$ROOT" != "/" ]; then
        ROOT="${ROOT%/}"
    fi

    # Check we're root
    if [ "$(id -u)" -ne 0 ] && ! $DRY_RUN; then
        log_error "Must run as root (or use --dry-run)"
        exit 1
    fi

    check_prerequisites

    # Execute all steps
    step_klipper_configs
    step_moonraker_config
    step_klipperscreen_config
    step_systemd_services
    step_first_boot
    step_rc_local
    step_klipper_fork
    step_klipperscreen_fork
    step_klipper_mcu
    step_scipy
    step_remove_s1_files
    step_hostname
    step_permissions

    print_summary
}

main "$@"
