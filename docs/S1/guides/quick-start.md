# Quick Start Guide: FLSUN S1 Open Source Edition

---

## For Documentation Contributors

### Prerequisites
- Python 3.x
- Git

### Setup
```bash
git clone https://github.com/Guilouz/FLSUN-S1-Open-Source-Edition.git
cd FLSUN-S1-Open-Source-Edition
pip install mkdocs-material mkdocs-glightbox
```

### Development
```bash
mkdocs serve          # Live preview at http://127.0.0.1:8000
mkdocs build          # Build static site to site/
```

### Contributing
1. Fork the repository
2. Edit markdown files in `docs/`
3. Preview with `mkdocs serve`
4. Submit a pull request

---

## For Printer Users

### Shopping List
| Item | Purpose | Est. Cost |
|---|---|---|
| microSD card ≥ 16GB | Boot FLSUN OS | ~$10 |
| ST-LINK V2 Programmer | Flash motherboard firmware | ~$10-15 |
| Dupont cables (4x) | Connect programmer to motherboard | Usually included |

### Quick Process
1. Download `FLSUN-OS-S1-SD-3.0.img.gz` from [Releases](https://github.com/Guilouz/FLSUN-S1-Open-Source-Edition/releases)
2. Flash to microSD with [Raspberry Pi Imager](https://www.raspberrypi.com/software/)
3. Flash motherboard with `motherboard_fw.bin` using STM32 ST-LINK Utility + ST-LINK V2
4. Insert microSD into core board (behind screen)
5. Power on → wait for auto-setup → configure WiFi
6. SSH in (`pi`/`flsun`) → run `easy-installer` → update everything
7. Calibrate: Motors → Z Offset → Bed Mesh → Input Shaper
8. Configure slicer → Print!

### Important Links
- **Wiki:** <https://guilouz.github.io/FLSUN-S1-Open-Source-Edition/home.html>
- **Releases:** <https://github.com/Guilouz/FLSUN-S1-Open-Source-Edition/releases>
- **Discussions:** <https://github.com/Guilouz/FLSUN-S1-Open-Source-Edition/discussions>
- **Klipper Source:** <https://github.com/Guilouz/Klipper-Flsun-S1>
- **KlipperScreen Source:** <https://github.com/Guilouz/KlipperScreen-Flsun-S1>
