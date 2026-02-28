# Downloaded Resources Index

**Date:** 2026-02-28  
**Source:** <https://guilouz.github.io/FLSUN-S1-Open-Source-Edition/>

---

## Folder Structure

```
resources/
├── firmwares/
│   ├── open-source-edition/
│   │   ├── motherboard_fw.bin          # Katapult + Klipper combined firmware
│   │   └── closed_loop_board_fw.bin    # Closed loop motor board firmware
│   └── stock/
│       ├── motherboard_s1_fw_stock.bin     # S1 stock firmware (for reverting)
│       ├── motherboard_s1pro_fw_stock.bin  # S1 Pro stock firmware (for reverting)
│       └── closed_loop_board_fw_stock.bin  # Stock closed loop firmware
├── tools/
│   ├── STM32_ST-LINK_Utility_v4.6.0.zip   # STM32 programmer software (Windows)
│   ├── Closed_Loop_Boards_Tool.stl        # 3D-printable flashing jig
│   ├── RKDevTool_Release_v2.96.zip        # Rockchip eMMC flasher (Windows)
│   └── DriverAssitant_v5.0.zip            # Rockchip USB driver (Windows)
└── klipper-configs/
    ├── printer.cfg              # Main printer configuration
    ├── config.cfg               # Modular config includes
    ├── moonraker.conf           # Moonraker API config
    ├── KlipperScreen.conf       # Touchscreen UI config
    ├── webcam.txt               # Camera settings
    ├── macros.cfg               # G-code macros
    ├── flsun-os.cfg             # FLSUN OS specific settings
    ├── fan-stock.cfg            # Stock fan configuration
    ├── fan-silent-kit.cfg       # Silent Kit (CPAP) fan config
    ├── led-stock.cfg            # Stock LED config
    ├── led-mmb-cubic.cfg        # BTT MMB Cubic LED config
    ├── filament-sensor-stock.cfg
    ├── filament-sensor-sfs.cfg  # BTT Smart Filament Sensor V2.0
    ├── temp-sensor-mmb-cubic.cfg
    └── camera-control.cfg       # Camera settings control
```

---

## NOT Downloaded (Too Large / Requires Google Drive)

These files are available but too large to download via simple HTTP fetch:

| File | Size | Source |
|---|---|---|
| `FLSUN-OS-S1-SD-3.0.img.gz` | ~1-2 GB | [GitHub Releases](https://github.com/Guilouz/FLSUN-S1-Open-Source-Edition/releases/tag/FLSUN-OS-3.0) / [Google Drive](https://drive.google.com/file/d/1b156EbYKD7dWgTefLHgGV__uUrDGyFWI/view?usp=sharing) |
| `FLSUN-OS-S1-EMMC-3.0.7z` | ~1-2 GB | [GitHub Releases](https://github.com/Guilouz/FLSUN-S1-Open-Source-Edition/releases/tag/FLSUN-OS-3.0) / [Google Drive](https://drive.google.com/file/d/1GRZF0GbDqUsAQmInlMIeVWWoous_SDXx/view?usp=sharing) |
| `STOCK-OS-S1-EMMC-1.0.6.4.7z` | Large | [Google Drive](https://drive.google.com/file/d/14JhpC56aXe_kKlerZf43JvFv31ULlQqN/view?usp=sharing) (stock eMMC backup for recovery) |

---

## Also Cloned

| Folder | Source |
|---|---|
| `repo/` | Full clone of `Guilouz/FLSUN-S1-Open-Source-Edition` (docs + mkdocs config) |
