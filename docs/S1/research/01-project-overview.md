# FLSUN S1 Open Source Edition — Project Overview

**Date researched:** 2026-02-28  
**Source:** <https://github.com/Guilouz/FLSUN-S1-Open-Source-Edition>  
**Author:** Guilouz (Cyril Guislain)  
**Latest release:** FLSUN OS 3.0 (Aug 24, 2025)

---

## What Is This Project?

FLSUN-OS is a **community-built open-source replacement operating system** for the FLSUN S1 and FLSUN S1 Pro delta 3D printers. It replaces the factory Stock OS (Debian 10-based) with a modern, fully open-source Debian 13 Trixie-based OS that runs the Klipper firmware ecosystem.

### Key Insight: Two Different "Builds"

This project has **two distinct meanings** of "build":

1. **Building/deploying the documentation website** — a MkDocs Material site hosted on GitHub Pages  
2. **Building/installing FLSUN OS onto the printer** — flashing a pre-built OS image plus compiling/flashing MCU firmware

The repository itself (`FLSUN-S1-Open-Source-Edition`) is primarily a **documentation repository** — it does NOT contain the OS image build scripts or Armbian rootfs builder. The OS images are pre-built by Guilouz and distributed as release assets (`.img.gz` for SD, `.7z` for eMMC).

---

## Repository Structure

```
FLSUN-S1-Open-Source-Edition/
├── .github/
│   ├── workflows/
│   │   └── docs.yml          # GitHub Actions: MkDocs → GitHub Pages
│   └── FUNDING.yml
├── docs/                      # MkDocs documentation source (markdown)
│   ├── assets/                # Images, CSS, JS, downloadable files
│   │   ├── css/
│   │   ├── images/
│   │   ├── javascript/
│   │   └── downloads/         # Firmwares, tools (hosted here)
│   │       └── firmwares/
│   ├── about.md
│   ├── complete-process-summary.md
│   ├── prepare-microsd-card-for-flsun-os.md
│   ├── flash-motherboard-firmware.md
│   ├── flash-closed-loops-boards.md
│   ├── insert-microsd-card-with-flsun-os-in-core-board.md
│   ├── first-boot.md
│   ├── update-and-configure-printer.md
│   ├── ssh-connection.md
│   ├── update-time-zone.md
│   ├── slicers-settings.md
│   ├── easy-installer.md
│   ├── install-flsun-os-on-emmc.md
│   ├── update-motherboard-firmware.md
│   └── ... (more docs)
├── .gitignore
├── README.md
└── mkdocs.yml                 # MkDocs configuration
```

---

## Related Repositories

| Repository | Purpose |
|---|---|
| [Guilouz/FLSUN-S1-Open-Source-Edition](https://github.com/Guilouz/FLSUN-S1-Open-Source-Edition) | Documentation wiki & release artifacts |
| [Guilouz/Klipper-Flsun-S1](https://github.com/Guilouz/Klipper-Flsun-S1) | Modified Klipper firmware with S1-specific support |
| [Guilouz/KlipperScreen-Flsun-S1](https://github.com/Guilouz/KlipperScreen-Flsun-S1) | Modified KlipperScreen touchscreen UI for S1 |

---

## What's Included in FLSUN OS

- **Debian 13 Trixie** base (support until June 2030)
- **Python 3.13** runtime
- **Upgraded kernel v6.1.99** — full 1 GB RAM access (vs. 700 MB on stock)
- **ZRAM swap** — 512 MB extra virtual RAM
- **Klipper** (S1-modified fork) — 3D printer firmware
- **Moonraker** — Klipper API server
- **KlipperScreen** (S1-modified fork) — touchscreen UI
- **Mainsail** — web interface
- **MJPG-Streamer** — camera streaming
- **Kiauh** — Klipper installation helper
- **Katapult** bootloader — allows firmware updates without physical programmer
- **Easy Installer** — SSH-based management tool
- Enhanced Delta Calibration, Adaptive Bed Heating, Power Loss Recovery
- Moonraker Timelapse, Klipper Print Time Estimator
- BigTreeTech MMB Cubic support

### Removed from Stock

- All AI features (removed as non-functional)
- Only kept: Power Loss Recovery, XY Dimension Calibration

---

## Hardware Target

- **Printer:** FLSUN S1 / FLSUN S1 Pro (delta kinematics)
- **Core Board:** Rockchip-based SBC (RK3xxx) with eMMC + microSD slot
- **Motherboard:** STM32-based MCU (for stepper control)
- **Closed Loop Boards:** STM32-based (3x, one per axis) — S1 only
- **Screen:** Integrated touchscreen running KlipperScreen
