# APT-Based Update Concept for FLSUN OS

**Date researched:** 2026-03-17
**Source:** Reverse-engineering of FLSUN OS 3.0 image, debos recipes, overlay analysis

---

## 1. Problem Statement

FLSUN OS is based on Debian 13 Trixie but ships ~100 custom files and 8 components installed from Git (not APT). Running `apt upgrade` can break the printer because:

- Klipper, Moonraker, KlipperScreen are Git clones, not Debian packages
- The kernel is a custom build (`6.1.99flsun`) in an Android boot.img, not a standard `linux-image-*` package
- System configs (nginx, rc.local, systemd services) are customized and could be overwritten by package upgrades
- The current update mechanism (Moonraker update manager / `easy-installer`) updates Git repos individually, with no dependency tracking or rollback

**Goal:** Make every component of FLSUN OS updateable via APT from a custom Debian repository, while keeping full compatibility with the upstream Debian 13 repo for system packages.

---

## 2. eMMC Boot Partition — Why Kernel Updates Need Special Handling

Standard Debian puts the kernel in `/boot/vmlinuz-*` and uses GRUB or extlinux to select it. FLSUN printers do **not** boot this way.

### FLSUN Boot Architecture

| Property | Value |
|---|---|
| Boot format | Android boot.img (magic: `ANDROID!`) |
| Contents | zImage + RSCE container (Rockchip resource image with DTB) |
| Partition | `/dev/mmcblk0p3` (`boot`, GPT partition 3) |
| Write method | Raw `dd` to block device (no filesystem) |
| Bootloader | U-Boot in `mmcblk0p1` — reads Android boot header, loads kernel + DTB |
| No initramfs | ramdisk_size = 0 in header |
| No /boot mount | Boot partition is raw, not mounted in Linux |

### Consequence for APT

A kernel .deb package cannot use the standard Debian `linux-image-*` pattern (install to `/boot`, run `update-grub`). Instead, the `postinst` script must:

1. Write `boot.img` directly to `/dev/mmcblk0p3` via `dd`
2. Back up the previous boot.img before writing (for rollback)
3. Call `sync` to ensure the write is flushed

This is implemented in `build/package-kernel-deb.sh`. The resulting package (`flsun-os-kernel-s1` or `flsun-os-kernel-t1`) `dd`s the boot.img into the boot partition during `dpkg --configure`.

---

## 3. Inventory of Modified Packages and Files

### 3.1 Components Installed from Git (NOT in Debian Repos)

These must become custom .deb packages in the FLSUN OS repo:

| Component | Current Source | Proposed Package Name | Update Trigger |
|---|---|---|---|
| Klipper | `Guilouz/Klipper-Flsun-S1` (git clone) | `flsun-klipper` | Upstream commit |
| Moonraker | `Arksine/moonraker` (git clone) | `flsun-moonraker` | Upstream release |
| KlipperScreen | `Guilouz/KlipperScreen-Flsun-S1` (git clone) | `flsun-klipperscreen` | Upstream commit |
| Katapult | `Arksine/katapult` (git clone) | `flsun-katapult` | Upstream release |
| KIAUH | `dw-0/kiauh` (git clone) | `flsun-kiauh` | Upstream release |
| FLSUN OS Deps | `Guilouz/FLSUN-S1-OSE-Dependencies` (git clone) | `flsun-os-dependencies` | Manual |
| MJPG-Streamer | `jacksonliam/mjpg-streamer` (compiled) | `flsun-mjpg-streamer` | Upstream commit |
| Mainsail | `mainsail-crew/mainsail` (static download) | `flsun-mainsail` | GitHub release |

Each of these needs a `.deb` that:
- Installs files to the same paths as the current Git clones
- Creates/manages Python virtualenvs where needed (klippy-env, moonraker-env, KlipperScreen-env)
- Declares proper `Depends:` on Debian system packages (python3, python3-venv, etc.)
- Ships the systemd service file inside the package (not as a separate overlay)

### 3.2 System Configuration Files Overriding Debian Defaults

These files are shipped in `build/overlays/system/` and replace Debian defaults. If the owning Debian package is upgraded, `dpkg` will ask whether to keep the local version — which breaks unattended upgrades.

| File | Owning Debian Package | Risk on `apt upgrade` | Solution |
|---|---|---|---|
| `/etc/rc.local` | (none — custom) | Low — no package owns it | Ship in `flsun-os-base` |
| `/etc/hostname` | `base-files` | Overwritten on upgrade | Ship in `flsun-os-base`, pin `base-files` |
| `/etc/hosts` | `base-files` | Overwritten on upgrade | Ship in `flsun-os-base`, pin `base-files` |
| `/etc/fstab` | `base-files` | Overwritten on upgrade | Ship in `flsun-os-base` |
| `/etc/power-key.sh` | (none — custom) | Safe | Ship in `flsun-os-base` |
| `/etc/input-event-daemon.conf` | `input-event-daemon` | Could be overwritten | Use `dpkg-divert` |
| `/etc/init.d/first-boot.sh` | (none — custom) | Safe | Ship in `flsun-os-base` |
| `/etc/init.d/S60NPU_init` | (none — custom) | Safe | Ship in `flsun-os-npu` |
| `/etc/nginx/nginx.conf` (or sites-enabled) | `nginx-common` | **Breaks Mainsail** | Use `dpkg-divert` or ship as `flsun-nginx-config` |

**`dpkg-divert`** tells dpkg to install the Debian package's version of a file to a different path, leaving the FLSUN version in place. Example:

```bash
# In flsun-os-base.postinst:
dpkg-divert --add --rename --package flsun-os-base \
    /etc/input-event-daemon.conf
```

### 3.3 Custom Systemd Services

Currently shipped as overlay files in `build/overlays/system/etc/systemd/system/`. These should move into their respective packages:

| Service File | Current Location | Proposed Package |
|---|---|---|
| `klipper.service` | overlay | `flsun-klipper` |
| `moonraker.service` | overlay | `flsun-moonraker` |
| `KlipperScreen.service` | overlay | `flsun-klipperscreen` |
| `webcamd.service` | overlay | `flsun-mjpg-streamer` |
| `FLSUN-OS-Dependencies.service` | overlay | `flsun-os-dependencies` |
| `drying-box.service` | overlay (S1 only) | `flsun-drying-box` |
| `usb-mount@.service` | overlay | `flsun-os-base` |

### 3.4 Python Virtualenvs

The biggest packaging challenge. Klipper, Moonraker, and KlipperScreen each have a Python virtualenv with pip-installed dependencies:

| Virtualenv | Path | Key pip Packages | Size |
|---|---|---|---|
| klippy-env | `/home/pi/klippy-env` | cffi, greenlet, jinja2, pyserial | ~50 MB |
| moonraker-env | `/home/pi/moonraker-env` | tornado, lmdb, inotify, paho-mqtt, zeroconf, libnacl | ~80 MB |
| KlipperScreen-env | `/home/pi/.KlipperScreen-env` | PyGObject, Pillow, matplotlib | ~120 MB |

**Options:**
1. **Build virtualenvs in postinst** — the package `postinst` runs `python3 -m venv` + `pip install -r requirements.txt`. Slow on the printer (~5–10 min per env) but reliable. Requires internet on the printer during install.
2. **Ship pre-built virtualenvs** — build the venvs during packaging and ship them in the .deb. Large packages (~50–120 MB each) but no internet needed on the printer. Virtualenvs are architecture-specific (armhf) so they must be built on ARM or cross-built.
3. **Convert pip deps to Debian packages** — create .deb packages for each pip dependency. Most correct approach but enormous effort (dozens of packages).

**Recommended:** Option 2 (pre-built virtualenvs) for the initial implementation. The packages are large but the install is fast and offline-capable. Option 1 as a fallback for users with internet access.

### 3.5 Kernel Module (galcore.ko)

The Vivante GPU/NPU driver (`galcore.ko`) is a pre-compiled binary shipped in the rootfs at `/lib/modules/galcore.ko`. It is NOT built with the kernel (the kernel is fully monolithic with 0 loadable modules by default). This module needs its own package:

| Item | Details |
|---|---|
| Package name | `flsun-os-npu` |
| Ships | `/lib/modules/galcore.ko`, `/etc/init.d/S60NPU_init` |
| Depends | `flsun-os-kernel-s1 | flsun-os-kernel-t1` |
| Note | Must match kernel version — rebuild when kernel changes |

### 3.6 Packages Safe for Standard `apt upgrade`

Everything NOT listed above is a standard Debian 13 package and can be upgraded normally. The debos recipe installs ~100 Debian packages across stages 3–8. These include:

- System: `systemd`, `udev`, `dbus`, `networkmanager`, `avahi-daemon`, `openssh-server`
- Python: `python3.13`, `python3-venv`, `python3-dev`, `python3-numpy`, `python3-scipy`
- X11/GUI: `xinit`, `xserver-xorg`, `openbox`, `python3-gi`, `gir1.2-gtk-3.0`
- Media: `v4l-utils`, `libjpeg-dev`, `ffmpeg`
- Web: `nginx`
- Tools: `git`, `wget`, `curl`, `sudo`, `rsync`, `p7zip-full`

These are all from the standard Debian 13 repos and can be upgraded safely — **EXCEPT** for `nginx` (needs config divert) and `base-files` (needs pinning for hostname/hosts/fstab).

---

## 4. Package Architecture

### 4.1 Custom Packages (hosted on FLSUN OS repo)

```
flsun-os-base                  # Base config: rc.local, fstab, hostname, power-key,
                                # input-event-daemon, usb-mount, user setup
    Depends: sudo, networkmanager, avahi-daemon, openssh-server,
             input-event-daemon, zram-tools

flsun-os-kernel-s1             # Kernel boot.img for S1 (RV1126, 1024×600)
    Conflicts: flsun-os-kernel-t1
    Provides: flsun-os-kernel

flsun-os-kernel-t1             # Kernel boot.img for T1 (RV1109, 800×480)
    Conflicts: flsun-os-kernel-s1
    Provides: flsun-os-kernel

flsun-os-npu                   # Vivante GPU/NPU module (galcore.ko)
    Depends: flsun-os-kernel

flsun-klipper                  # Klipper + klippy-env virtualenv + service
    Depends: python3, python3-venv, python3-dev, python3-serial,
             python3-can, gcc, make
    Recommends: flsun-katapult

flsun-moonraker                # Moonraker + moonraker-env virtualenv + service
    Depends: python3, python3-venv, flsun-klipper
    Recommends: flsun-mainsail

flsun-klipperscreen            # KlipperScreen + venv + service
    Depends: python3, python3-venv, python3-gi, gir1.2-gtk-3.0,
             xinit, xserver-xorg, openbox
    Depends: flsun-klipper

flsun-mjpg-streamer            # Compiled MJPG-Streamer binary + service
    Depends: libjpeg62-turbo, v4l-utils

flsun-mainsail                 # Mainsail static web UI
    Depends: nginx
    Provides: flsun-web-ui

flsun-katapult                 # Katapult MCU bootloader flashing tool
    Depends: python3

flsun-kiauh                    # Klipper Installation And Update Helper
    Depends: git

flsun-os-dependencies          # FLSUN OS version checker + easy-installer
    Depends: flsun-os-base

flsun-drying-box               # Drying box controller (S1 only)
    Depends: flsun-klipper

flsun-nginx-config             # Nginx reverse proxy config for Mainsail
    Depends: nginx
```

### 4.2 Metapackage for Full Installation

```
flsun-os-s1                    # Metapackage: complete S1 installation
    Depends: flsun-os-base, flsun-os-kernel-s1, flsun-os-npu,
             flsun-klipper, flsun-moonraker, flsun-klipperscreen,
             flsun-mjpg-streamer, flsun-mainsail, flsun-katapult,
             flsun-kiauh, flsun-os-dependencies, flsun-drying-box,
             flsun-nginx-config

flsun-os-t1                    # Metapackage: complete T1 installation
    Depends: flsun-os-base, flsun-os-kernel-t1, flsun-os-npu,
             flsun-klipper, flsun-moonraker, flsun-klipperscreen,
             flsun-mjpg-streamer, flsun-mainsail, flsun-katapult,
             flsun-kiauh, flsun-os-dependencies,
             flsun-nginx-config
```

### 4.3 APT Source Configuration

On the printer, `/etc/apt/sources.list.d/flsun-os.list`:

```
deb [signed-by=/usr/share/keyrings/flsun-os-archive-keyring.gpg] https://packages.flsun-os.example.com/debian trixie main
```

The official Debian repos remain in `/etc/apt/sources.list` for system packages:

```
deb http://deb.debian.org/debian trixie main contrib non-free non-free-firmware
deb http://deb.debian.org/debian-security trixie-security main contrib non-free non-free-firmware
```

### 4.4 APT Pinning — Protecting Custom Packages

`/etc/apt/preferences.d/flsun-os.pref`:

```
# Prefer FLSUN OS repo for all flsun-* packages
Package: flsun-*
Pin: origin packages.flsun-os.example.com
Pin-Priority: 900

# Prevent base-files from overwriting hostname/hosts/fstab
Package: base-files
Pin: release o=Debian
Pin-Priority: 100

# Prevent nginx config from being overwritten (handled by flsun-nginx-config)
Package: nginx-common
Pin: release o=Debian
Pin-Priority: 100
```

---

## 5. APT Update Flow

### 5.1 Safe Unattended Upgrade

With proper packaging, a full `apt upgrade` on the printer:

```bash
sudo apt update
sudo apt upgrade -y
```

Would:

1. ✅ Upgrade all standard Debian packages (python3, systemd, openssh, etc.)
2. ✅ Upgrade `flsun-klipper` if a new version is in the FLSUN repo
3. ✅ Flash a new kernel if `flsun-os-kernel-s1` is updated (via postinst `dd`)
4. ✅ Keep FLSUN-specific configs untouched (owned by `flsun-os-base`)
5. ✅ Keep nginx config untouched (owned by `flsun-nginx-config`, diverted)
6. ❌ NOT break virtualenvs (owned by their respective packages)
7. ❌ NOT touch `/dev/mmcblk0p3` unless `flsun-os-kernel-*` is actually upgraded

### 5.2 Kernel Update Sequence

```
apt upgrade
  └─ flsun-os-kernel-s1 (6.1.99-1 → 6.1.115-1)
       ├─ preinst:  dd /dev/mmcblk0p3 → /usr/share/flsun-os-kernel/boot.img.bak (backup)
       ├─ unpack:   boot.img → /usr/share/flsun-os-kernel/boot.img
       └─ postinst: dd /usr/share/flsun-os-kernel/boot.img → /dev/mmcblk0p3 (flash)
           └─ reboot needed to activate
```

### 5.3 Rollback

```bash
# Restore previous kernel
sudo dd if=/usr/share/flsun-os-kernel/boot.img.bak of=/dev/mmcblk0p3 bs=4M
sudo reboot

# Downgrade via APT
sudo apt install flsun-os-kernel-s1=6.1.99-1
```

---

## 6. Implementation Roadmap

### Phase 1 — Kernel Package (Ready Now)

- [x] `build/package-kernel-deb.sh` — packages boot.img into a .deb
- [ ] Test on live printer: `dpkg -i`, verify `dd` write, verify reboot
- [ ] Set up repository and test `apt install`

### Phase 2 — Base System Package

- [ ] Create `flsun-os-base` .deb with all overlay files
- [ ] Implement `dpkg-divert` for `/etc/input-event-daemon.conf`
- [ ] Pin `base-files` to prevent hostname/fstab overwrite
- [ ] Add `flsun-nginx-config` with nginx reverse proxy site config
- [ ] Test safe `apt upgrade` of Debian packages

### Phase 3 — Application Packages

- [ ] Package Klipper (+ klippy-env pre-built virtualenv)
- [ ] Package Moonraker (+ moonraker-env)
- [ ] Package KlipperScreen (+ KlipperScreen-env)
- [ ] Package MJPG-Streamer (compiled binary)
- [ ] Package Mainsail (static web files)
- [ ] Package Katapult, KIAUH, FLSUN-OS-Dependencies

### Phase 4 — Metapackages & Repository

- [ ] Create `flsun-os-s1` and `flsun-os-t1` metapackages
- [ ] Set up reprepro-based Debian repository
- [ ] Create GPG signing key for the repository
- [ ] Add `flsun-os.list` and keyring to the base OS image
- [ ] Test full `apt update && apt upgrade` lifecycle

### Phase 5 — CI/CD

- [ ] Automate .deb builds in GitHub Actions (on tag/release)
- [ ] Auto-publish to repository
- [ ] Version bumps trigger rebuilds of dependent packages

---

## 7. What Would Break Today Without Custom Packages

This table summarizes the current state — what happens if you run `apt upgrade` on FLSUN OS 3.0 today (without the custom packaging described above):

| Scenario | Impact | Severity |
|---|---|---|
| `base-files` upgraded | `/etc/hostname`, `/etc/hosts` overwritten → printer identity lost | Medium |
| `nginx-common` upgraded | Mainsail reverse proxy config reset → web UI unreachable | Medium |
| `input-event-daemon` upgraded | Button mapping reset → power button stops working | Low |
| `python3.13` upgraded | Usually safe — virtualenvs may need rebuild if ABI changes | Low |
| `systemd` upgraded | Safe — custom services in `/etc/systemd/system/` take precedence | None |
| Kernel packages installed | Debian's `linux-image-*` would go to `/boot` (harmless but wastes space) | None |
| `openssh-server` upgraded | Safe — `sshd_config` may prompt for merge; auto-upgrade keeps local | Low |
| Git-cloned repos | Untouched by APT — they are directories, not packages | None |

**Key insight:** Running `apt upgrade` today is *mostly* safe for system packages. The real risk is not APT breaking things — it's that the custom components (Klipper, Moonraker, kernel) are **invisible to APT** and cannot be upgraded, tracked, or rolled back through the package manager.

---

## 8. Package Build Workflow (for maintainers)

### Building a Kernel Package

```bash
# 1. Build the kernel
./build-kernel.sh --target s1

# 2. Package as .deb
./package-kernel-deb.sh --target s1 --version 6.1.115 --revision 1

# 3. Add to repository (see hosting-debian-repo.md)
reprepro -b /srv/repo includedeb trixie \
    output/flsun-os-kernel-s1_6.1.115-1_armhf.deb
```

### Building an Application Package (Future Pattern)

Each application package would follow this structure:

```
flsun-klipper_1.0-1_armhf/
├── DEBIAN/
│   ├── control          # Package metadata, dependencies
│   ├── postinst         # Create venv, install pip deps, enable service
│   ├── prerm            # Stop service
│   └── postrm           # Remove venv on purge
├── home/pi/
│   ├── klipper/         # Git repo snapshot
│   └── klippy-env/      # Pre-built virtualenv (armhf)
├── etc/systemd/system/
│   └── klipper.service  # Systemd unit
└── home/pi/printer_data/systemd/
    └── klipper.env      # Environment file
```

---

## 9. Open Questions

1. **Virtualenv portability** — Pre-built armhf virtualenvs may have hardcoded paths (`/home/pi/klippy-env/bin/python3`). Need to verify they work when shipped via .deb.

2. **Klipper config ownership** — Printer configs (`printer.cfg`, `macros.cfg`) are user data, not package data. They must NOT be inside a .deb (would be overwritten on upgrade). Solution: ship defaults to `/usr/share/flsun-klipper/defaults/` and copy to `~/printer_data/config/` only on first install.

3. **galcore.ko version coupling** — The NPU module must match the running kernel. If the kernel is upgraded but galcore.ko is not rebuilt, it may fail to load. The `flsun-os-npu` package needs a strict `Depends: flsun-os-kernel (= exact-version)`.

4. **Moonraker update manager conflict** — Moonraker has its own update manager that pulls Git repos. If Klipper is now a .deb package, the Moonraker update manager should be configured to NOT update Klipper (APT handles it). This needs a config change in `moonraker.conf`.

5. **T1 Klipper fork** — The T1 uses `garethky/klipper` (load-cell-probe branch), not `Guilouz/Klipper-Flsun-S1`. The T1 Klipper package needs to be a separate package (`flsun-klipper-t1`) or a variant build of `flsun-klipper`.

6. **Signing** — The repository and packages should be GPG-signed. The signing key needs to be distributed with the base image (in `/usr/share/keyrings/`).
