# Release History & Changelog Summary

**Date researched:** 2026-02-28

---

## Release Timeline

| Version | Date | Type | Key Changes |
|---|---|---|---|
| **3.0** | Aug 24, 2025 | **Full reinstall** | Debian 13 Trixie, Python 3.13, KlipperScreen caching |
| **2.0.2** | Jul 13, 2025 | Config update | Motherboard config + environment updates |
| **2.0.1** | May 3, 2025 | Config update | Interactive topbar icons, lock screen during printing |
| **2.0** | Apr 7, 2025 | **Full reinstall** | FLSUN OS Dependencies, ZRAM, Printer Setup Wizard |
| **1.5.1** | Mar 23, 2025 | **Full reinstall** | Katapult bootloader, unified configs, BTT SFS V2.0 |
| **1.4** | Mar 3, 2025 | Image update | eMMC install support, in-image SD bootloader safety |
| **1.3** | Feb 28, 2025 | Config update | Proper shutdown, reworked Power Loss Recovery |
| **1.2.2** | Feb 11, 2025 | Hotfix | Fix `max_power` error on resume |
| **1.2.1** | Feb 7, 2025 | Hotfix | Fix macro error, integrate `SET_TMC_CURRENT` |
| **1.2** | Feb 4, 2025 | **Full reinstall** | Easy Installer, BTT MMB Cubic, numpy, Adaptive Bed Mesh |
| 1.1 | Earlier | — | (page 2 of releases, not fetched) |
| 1.0 | Earlier | — | Initial release |

---

## Release Distribution

Each release provides two image variants:

| File Pattern | Boot Method | Format |
|---|---|---|
| `FLSUN-OS-S1-SD-X.X.img.gz` | microSD card | Gzip-compressed disk image |
| `FLSUN-OS-S1-EMMC-X.X.7z` | eMMC memory | 7-Zip archive (boot.img + rootfs.img) |

Images are hosted on:
1. **GitHub Releases** (primary)
2. **Google Drive** (mirror, for large files)

---

## Notable Version Milestones

### v3.0 — Major OS Upgrade
- Debian 13 Trixie (from Debian 12)
- Python 3.13 (memory management improvements, +5-10% responsiveness)
- KlipperScreen icon/pixbuf/keyboard caching for improved fluidity

### v2.0 — Architecture Overhaul
- FLSUN OS Dependencies system (no more full reinstalls for most updates)
- Kernel v6.1.99 with full 1 GB RAM access
- ZRAM swap (512 MB extra)
- Printer Setup Wizard feature

### v1.5.1 — Bootloader Revolution
- Katapult bootloader integration (flash firmware without physical programmer!)
- Unified configuration files for all variants
- Klipper Print Time Estimator integration

### v1.2 — Feature Expansion
- Easy Installer CLI tool
- BigTreeTech MMB Cubic support
- Enhanced Delta Calibration
- Numpy support for resonance graphics
