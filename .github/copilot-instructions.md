applyTo: "**"
---

# FLSUN OS Research & Documentation Workspace

## Project Context

This workspace contains research documentation and downloaded resources for **FLSUN delta 3D printers** — primarily the S1 Open Source Edition by Guilouz and hardware research on the T1/T1 Pro.

**Key repositories:**
- S1 Docs/Wiki: https://github.com/Guilouz/FLSUN-S1-Open-Source-Edition
- S1 Klipper fork: https://github.com/Guilouz/Klipper-Flsun-S1
- S1 KlipperScreen fork: https://github.com/Guilouz/KlipperScreen-Flsun-S1
- S1 Live wiki: https://guilouz.github.io/FLSUN-S1-Open-Source-Edition/home.html
- Kernel source: https://github.com/armbian/linux-rockchip (branch `rk-6.1-rkr5.1`, submodule at `kernel/`)
- T1 Hardware/Pi replacement: https://github.com/mulcmu/T1-pyro

## Workspace Structure

```
FLSUN-OS/
├── .github/
│   └── copilot-instructions.md      # This file
├── build/                            # OS image build system (debos)
│   ├── flsun-os.yaml                # Main debos recipe — S1 (23 stages)
│   ├── build.sh                     # Rootfs build script (Docker/native)
│   ├── build-kernel.sh              # Kernel build script (S1/T1, cross-compile + boot.img)
│   ├── build-boot-img.sh            # Boot image packaging (mkbootimg)
│   ├── package-emmc.sh              # eMMC archive creator (7z)
│   ├── package-kernel-deb.sh        # Kernel .deb packager (for apt delivery)
│   ├── README.md                    # Build system documentation
│   ├── overlays/
│   │   ├── system/                  # S1 system overlay files (services, scripts)
│   │   └── user/                    # S1 user overlay files (moonraker.conf)
│   ├── overlays-t1/
│   │   ├── system/                  # T1 system overlay files
│   │   │   └── etc/                 # rc.local, first-boot.sh, klipper-mcu.service, etc.
│   │   └── user/                    # T1 user overlay files (full Klipper config set)
│   │       └── home/pi/printer_data/config/
│   │           ├── printer.cfg, config.cfg, moonraker.conf, KlipperScreen.conf
│   │           └── Configurations/  # macros, fan, led, filament-sensor configs
│   └── tools/                       # *** T1 IMAGE BUILD TOOLS (Python) ***
│       ├── patch-dtb-for-t1.py      # Patch S1 DTB → T1 display (800×480)
│       ├── build-boot-img-t1.py     # Package zImage + DTB → Android boot.img
│       ├── build-images-t1.py       # *** Master image builder (3 images) ***
│       ├── build-rootfs-t1.sh       # Rootfs builder (S1→T1, Linux only)
│       └── mod-rootfs-for-t1.sh     # Convert S1 rootfs to T1 (bash, Linux/WSL)
├── docs/
│   ├── S1/
│   │   ├── research/                 # S1 research findings (01–11)
│   │   └── guides/                   # S1 quick reference guides
│   └── T1/
│       ├── research/                 # T1 research findings
│       │   ├── 01-hardware-overview.md
│       │   ├── 02-firmware-and-community.md
│       │   ├── 03-wifi-subsystem-comparison.md
│       │   ├── 03-kernel-build-and-display-drivers.md
│       │   ├── 04-klipper-config-analysis.md
│       │   ├── 04-stock-firmware-analysis.md
│       │   └── 05-s1-to-t1-porting-guide.md
│       └── guides/                   # T1 guides (future)
├── resources/
│   ├── S1/
│   │   ├── firmwares/                # S1 firmware binaries
│   │   │   ├── open-source-edition/  # Klipper MCU firmwares
│   │   │   ├── os-images/            # FLSUN-OS images (extracted)
│   │   │   │   └── FLSUN-OS-S1-EMMC-3.0/
│   │   │   │       ├── boot.img      # S1 boot image (Android format)
│   │   │   │       ├── rootfs.img    # S1 rootfs (ext4)
│   │   │   │       ├── extracted/    # zImage, rk-kernel.dtb, kernel-config.txt
│   │   │   │       └── rootfs-extracted/  # Full rootfs contents (configs, services)
│   │   │   └── stock/                # Stock firmware (for reverting)
│   │   ├── tools/                    # Flashing utilities (Windows)
│   │   └── klipper-configs/          # S1 Klipper config files
│   └── T1/
│       ├── firmwares/                # T1 firmware binaries
│       │   ├── stock/                # Stock eMMC partition dumps + analysis scripts
│       │   │   └── extracted/        # DTB, kernel, decompiled DTS from stock
│       │   └── os-images/            # *** T1 BUILT IMAGES ***
│       │       ├── rk-kernel-t1.dtb  # T1-patched DTB (from patch-dtb-for-t1.py)
│       │       └── boot.img          # T1 boot.img (from build-boot-img-t1.py)
│       ├── klipper-configs/          # T1 Klipper config files
│       │   ├── printer.cfg           # T1-pyro reference config (mulcmu)
│       │   ├── mcu/.config           # MCU menuconfig for STM32F103xe
│       │   ├── custom_cables.md      # Cable wiring documentation
│       │   ├── schematic-bw.pdf      # Combined board schematics
│       │   ├── T1-pyro-README.md     # T1-pyro project overview
│       │   └── ported/              # *** T1 PORTED CONFIGS (from S1 OSE) ***
│       │       ├── printer.cfg       # T1 hardware definitions (3 MCUs, load cell, TMC5160)
│       │       ├── config.cfg        # Include selector for T1 components
│       │       ├── moonraker.conf    # Moonraker config (garethky fork updater)
│       │       ├── KlipperScreen.conf # KlipperScreen UI config (800×480)
│       │       └── Configurations/
│       │           ├── macros.cfg     # GCode macros (adapted from S1, ~940 lines)
│       │           ├── fan-stock.cfg  # Part fan + heatsink fan w/ hysteresis
│       │           ├── fan-silent-kit.cfg # Silent kit / T1 Pro fan (lower max_power)
│       │           ├── led-stock.cfg  # Caselight via host PWM
│       │           └── filament-sensor-stock.cfg  # 3 filament sensors
│       └── tools/                    # T1 tools (empty)
├── kernel/                           # Kernel source (git submodule, armbian/linux-rockchip)
└── S1-repo/                          # Full clone of S1 docs repository
```

## Documentation Standards

When creating or editing documentation in this workspace, follow these conventions:

### File Naming
- Use kebab-case for filenames: `my-research-topic.md`
- Prefix research docs with sequential numbers: `08-next-topic.md`
- Keep filenames descriptive but concise

### Markdown Structure
- Every document starts with an H1 title
- Include a metadata block with **Date researched** and **Source** URL
- Use `---` horizontal rules to separate major sections
- Use tables for structured comparisons
- Use fenced code blocks with language identifiers
- Use admonition-style notes for important warnings (bold text or blockquotes)

### Research Documentation Pattern
When documenting research on a new topic:

1. **State what you investigated** — the URL, repo, or resource
2. **State what you found** — factual findings
3. **State what you concluded** — your interpretation
4. **Note what's missing** — open questions for follow-up

### Content Guidelines
- Be factual and specific — include version numbers, file sizes, exact commands
- Link to primary sources (GitHub repos, wiki pages)
- Distinguish between official docs and personal observations
- Note when information might become outdated (version-specific details)
- Include file sizes and checksums when documenting downloads

## Technical Context

### "Building" This Project Has Five Meanings
1. **Docs site build:** `pip install mkdocs-material mkdocs-glightbox && mkdocs serve` (in the `S1-repo/` folder)
2. **Printer OS build (full):** `cd build && ./build.sh` — debos recipe builds rootfs.img from scratch (Docker or native Linux)
3. **Printer OS install (flash):** Flash pre-built images to eMMC via RKDevTool + compile/flash MCU firmware (hardware required)
4. **T1 image from S1 (mod):** Use `build/tools/` Python scripts to patch S1 FLSUN-OS 3.0 for T1 hardware:
   - `py build/tools/patch-dtb-for-t1.py` — patches S1 DTB for T1 display (800×480)
   - `py build/tools/build-boot-img-t1.py` — packages zImage + T1 DTB → boot.img
   - `bash build/tools/mod-rootfs-for-t1.sh /mnt/rootfs` — converts S1 rootfs for T1 (Linux/WSL)
5. **Kernel build:** Cross-compile the kernel from `kernel/` (git submodule of armbian/linux-rockchip) — requires Linux with `arm-linux-gnueabihf-gcc`. See `docs/S1/research/12-kernel-build-from-source.md`

### S1 Key Technical Details
- OS base: Debian 13 Trixie on Rockchip RV1126 SoC (ARMv7, quad-core Cortex-A7 @ 1.51 GHz, 1 GB DDR3)
- Motherboard MCU: STM32 (flashed via ST-LINK V2 programmer)
- Firmware: Katapult bootloader + Klipper MCU
- SSH credentials: `pi`/`flsun` or `root`/`flsun`
- Boot options: microSD card (non-destructive) or eMMC (permanent)
- eMMC partition layout: GPT with 6 partitions (uboot, misc, boot, recovery, backup, rootfs)
- SD image format: gzip-compressed raw disk image (.img.gz), written via Raspberry Pi Imager
- eMMC image format: 7z archive with boot.img + rootfs.img only, flashed via RKDevTool v2.96
- OS image build process: NOT publicly documented; see `docs/S1/research/08-os-image-build-process.md`
- OS image build system: Reconstructed debos recipe in `build/` — see `build/README.md`
- Kernel source: armbian/linux-rockchip branch `rk-6.1-rkr5.1` (confirmed by Guilouz in Discussion #13), submodule at `kernel/`
- Kernel version: 6.1.99flsun (fully monolithic — 1,277 built-in, 0 modules)
- Kernel build: requires Linux with `arm-linux-gnueabihf-gcc` 11.4.0 (Ubuntu 22.04). See `docs/S1/research/12-kernel-build-from-source.md`
- Easy Installer: `easy-installer` CLI command over SSH

### T1 Key Technical Details
- SoC: Rockchip RV1109 (ARMv7, dual-core Cortex-A7) — DTB uses `rv1126` platform ID (same die family)
- RAM: 1 GB DDR3
- Storage: 8 GB eMMC
- Stock OS: Debian 10 Buster, Python 3.7 (causes SSL/pip issues)
- Stock kernel: Linux 4.19.111 (Rockchip BSP, Linaro GCC 6.3.1)
- S1 kernel compatibility: S1's Linux 6.1.99flsun boots on T1 (confirmed — same rv1126 platform)
- Boot format: Stock uses U-Boot FIT; T1 FLSUN-OS uses Android boot (same as S1) with T1-patched DTB
- Display: 800×480 RGB parallel, `simple-panel` driver, 25 MHz pixel clock, bus-format RGB888 (0x1013)
- Motherboard MCU: GD32F303 (STM32F103-compatible), 72 MHz, USART3, 250000 baud
- Stepper drivers: TMC5160 via SPI (dedicated per-driver SPI buses, not shared like S1)
- Probe: Strain gauge with HX717 load cell sensor on secondary STM32F103 MCU
- Kinematics: Delta, print_radius=133, arm_length≈334-336
- Build volume: Ø 260 mm × 330 mm
- Max speed: 1000 mm/s, 30000 mm/s² acceleration
- MCU firmware flash name: `Robin_nano35.bin` on FAT32 SD card (or ST-Link V2)
- eMMC accessible via USB-C in Rockchip Maskrom mode (RKDevTool)
- Open Source Edition: **NOT planned** by Guilouz — this project creates a T1 port independently
- Screen: Different from S1 — 800×480 RGB panel (S1 is 1024×600), same interface type, different timings
- Hardware revisions: Gen1 vs Gen2 (see `docs/T1/research/01-hardware-overview.md`)
- Community project: mulcmu/T1-pyro replaces host with Raspberry Pi 4
- WiFi module: AP6212 (BCM43438) — **same as S1**, same SDIO address, same GPIO pins, same driver. No WiFi changes needed for porting. See `docs/T1/research/03-wifi-subsystem-comparison.md`
- Klipper config: 3 MCUs (main USB + host Linux + LoadCell UART), dedicated per-driver SPI for TMC5160s, load_cell_probe (HX717 strain gauge), single bed heater, 3 filament sensors, no drying box/power loss/motor cal. See `docs/T1/research/04-klipper-config-analysis.md`
- Daughter boards: USB hub board (camera + USB + caselight transistor, 5-pin JST XH), Lower function adapter board (LoadCell STM32F103, HX717 ADC, 5V PSU, JTAG, needs J20 mod for UART)
- Klipper fork: garethky/klipper load-cell-probe-community-testing (requires SciPy); S1 fork features (auto PA, enhanced delta cal, M101) NOT available
- T1 image toolchain: `build/tools/` contains Python scripts to create T1 firmware from S1 FLSUN-OS 3.0 (DTB patcher, boot.img builder, rootfs modifier)

### Working with Downloaded Resources
- S1 firmware `.bin` files in `resources/S1/firmwares/` are ready-to-flash binaries
- S1 tools in `resources/S1/tools/` are Windows-only utilities (ZIP archives)
- S1 Klipper configs in `resources/S1/klipper-configs/` are reference copies from the Klipper-Flsun-S1 repo
- S1 FLSUN-OS 3.0 image in `resources/S1/firmwares/os-images/FLSUN-OS-S1-EMMC-3.0/` — boot.img, rootfs.img, and extracted contents
- T1 Klipper configs in `resources/T1/klipper-configs/` are from the T1-pyro project (mulcmu)
- T1 ported configs in `resources/T1/klipper-configs/ported/` are the T1 port of S1 Open Source Edition configs (created by this project)
- T1 stock firmware dumps in `resources/T1/firmwares/stock/` — gzip-compressed eMMC partitions, extracted to `extracted/` subfolder
- T1 built images in `resources/T1/firmwares/os-images/` — T1-patched DTB and boot.img (generated by build/tools/)
- Large OS images (~1-2 GB) are NOT downloaded locally — see `docs/S1/research/07-resources-index.md` for download links

## When Answering Questions

- Reference the research docs in `docs/S1/research/` or `docs/T1/research/` for detailed findings
- For build instructions, distinguish between docs-site build and printer-OS installation
- For hardware questions, note that ST-LINK V2 programmer is essential for initial motherboard flashing
- For S1 config questions, reference the files in `resources/S1/klipper-configs/`
- For T1 config questions, reference the files in `resources/T1/klipper-configs/` (T1-pyro reference) and `resources/T1/klipper-configs/ported/` (S1 OSE port)
- Always check the live wiki for the most up-to-date information
