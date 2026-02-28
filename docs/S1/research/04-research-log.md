# Research Log: What I Tried & Discovered

**Date:** 2026-02-28

---

## Research Process

### 1. Initial Exploration of GitHub Repository

**What I did:**  
Fetched the main repository page at `github.com/Guilouz/FLSUN-S1-Open-Source-Edition` to understand the project structure.

**What I found:**
- The repo has only 3 top-level items: `.github/`, `docs/`, `mkdocs.yml`, plus `README.md` and `.gitignore`
- This is a **documentation-only repository** — no build scripts, no Dockerfiles, no Makefiles for the OS itself
- The actual OS images are pre-built and distributed as release assets
- The `docs/` folder contains ~25 markdown files covering the entire installation process
- Latest release: FLSUN OS 3.0 (Aug 24, 2025) with 12 total releases

**Key insight:** "Building" this project does NOT mean compiling an OS from source. It means either:
  - (a) Building the documentation website (MkDocs)
  - (b) Following the documented process to flash FLSUN OS onto a printer

---

### 2. Examining the GitHub Actions Workflow

**What I did:**  
Fetched `.github/workflows/docs.yml` to understand the CI/CD pipeline.

**What I found:**
- Single workflow file: `docs.yml`
- Triggers on push to `main` branch
- Uses Python + `mkdocs-material` + `mkdocs-glightbox`
- Deploys to GitHub Pages via `mkdocs gh-deploy --force`
- No OS build pipeline exists in this repo

**Conclusion:** The GitHub Actions only builds/deploys the documentation site. The OS image build process happens elsewhere (likely on Guilouz's local machine or private infrastructure).

---

### 3. Reading the Wiki/Documentation Site

**What I did:**  
Fetched all major wiki pages from `guilouz.github.io/FLSUN-S1-Open-Source-Edition/`:
- About page
- Complete Process Summary
- Prepare microSD Card
- Flash Motherboard Firmware
- Flash Closed Loops Boards
- First Boot
- Update and Configure Printer
- SSH Connection
- Easy Installer
- Install FLSUN OS on eMMC
- Update Motherboard Firmware

**What I found:**
- The documentation is thorough and well-structured with screenshots
- Installation process is hardware-intensive (requires ST-LINK V2 programmer, Dupont cables)
- Two boot methods: microSD (non-destructive) and eMMC (permanent, faster)
- SSH credentials: `pi`/`flsun` or `root`/`flsun`
- Easy Installer is a CLI tool for managing updates, backups, and installations

---

### 4. Examining the `mkdocs.yml` Configuration

**What I did:**  
Fetched the raw `mkdocs.yml` from the repo.

**What I found:**
- Full navigation structure with 6 sections: PREREQUISITES, PREPARATION, CONFIGURATIONS, EXTRAS, ADVANCED USERS, STL FILES
- Material theme with light/dark mode
- Custom CSS and JavaScript for enhanced styling
- Glightbox plugin for image zoom
- Multiple markdown extensions for rich content
- External links to Printables and Makerworld for STL files
- Link to GitHub Discussions for community engagement

---

### 5. Exploring Related Repositories

**What I did:**  
Fetched the README pages for the two companion repositories:
- `Guilouz/Klipper-Flsun-S1`
- `Guilouz/KlipperScreen-Flsun-S1`

**What I found:**

**Klipper-Flsun-S1:**
- Fork of mainline Klipper with S1-specific modifications
- Contains `config/FLSUN S1/` directory with all printer config files
- Has its own `Makefile` for building Klipper firmware
- Languages: C (98.2%), Python (1.1%), assembly, shell
- Active development — last commit within a month

**KlipperScreen-Flsun-S1:**
- Fork of KlipperScreen touchscreen GUI
- Optimized for delta printers
- Features: Inner/Outer bed, Drying Box, prompt macros
- Languages: Python (91.9%), CSS, Shell
- Installation: `git clone` + run install script

---

### 6. Examining Release Artifacts

**What I did:**  
Fetched the GitHub Releases page.

**What I found:**
- 12 releases total, from 1.2 to 3.0
- Two artifact types per release:
  - `FLSUN-OS-S1-SD-X.X.img.gz` — for microSD boot
  - `FLSUN-OS-S1-EMMC-X.X.7z` — for eMMC installation
- Also hosted on Google Drive (as GitHub has file size limits)
- Release 3.0 upgraded to Debian 13 Trixie + Python 3.13
- Some releases require full reinstall, others just config updates via Easy Installer

---

### 7. Downloading Resources

**What I did:**  
Downloaded all binary resources from the wiki's asset hosting:

**Firmwares (Open Source Edition):**
- `motherboard_fw.bin` (43 KB) — Combined Katapult + Klipper for motherboard
- `closed_loop_board_fw.bin` (52 KB) — Closed loop motor board firmware

**Firmwares (Stock — for reverting):**
- `motherboard_s1_fw_stock.bin` (512 KB) — S1 stock motherboard firmware
- `motherboard_s1pro_fw_stock.bin` (512 KB) — S1 Pro stock motherboard firmware
- `closed_loop_board_fw_stock.bin` (128 KB) — Stock closed loop board firmware

**Tools:**
- `STM32_ST-LINK_Utility_v4.6.0.zip` (26 MB) — Windows flashing utility
- `Closed_Loop_Boards_Tool.stl` (574 KB) — 3D printable flashing jig
- `RKDevTool_Release_v2.96.zip` (2 MB) — Rockchip eMMC flasher
- `DriverAssitant_v5.0.zip` (9.6 MB) — Rockchip USB driver

**Klipper Configs:**
- Cloned from `Guilouz/Klipper-Flsun-S1` → `config/FLSUN S1/`
- 15 config files covering printer, moonraker, KlipperScreen, macros, fans, LEDs, sensors

---

## Open Questions / Things Not Found

1. **How is the actual OS image built?** — No Armbian build scripts or rootfs configuration found in any public repo. Guilouz likely builds the images privately using custom Armbian/Debian tooling for the Rockchip SoC.

2. **Kernel source/config?** — The upgraded kernel v6.1.99 with full RAM access is mentioned but the kernel build process isn't documented publicly.

3. **What Rockchip SoC exactly?** — The core board uses a Rockchip chip (evident from RKDevTool usage) but the exact model isn't explicitly stated in the wiki.

4. **FLSUN OS Dependencies repo?** — Mentioned as an updatable package via Update Manager but the source isn't linked.

---

## Summary of Findings

| Aspect | Finding |
|---|---|
| **Repo type** | Documentation (MkDocs) + release distribution |
| **Docs build** | `pip install mkdocs-material mkdocs-glightbox && mkdocs serve` |
| **OS image build** | Pre-built by Guilouz; not publicly documented |
| **Firmware build** | Can be done on-printer via SSH; documented in wiki |
| **Installation** | Flash image → Flash MCU → Boot → Configure |
| **Hardware needed** | ST-LINK V2 programmer, microSD ≥16GB, Dupont cables |
| **Skill level** | Intermediate (microSD) to Advanced (eMMC) |
