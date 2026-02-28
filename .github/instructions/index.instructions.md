````instructions
---
applyTo: "**/*.c,**/*.h,**/*.S,**/CMakeLists.txt,**/CMakePresets.json,**/*.bat,**/*.ps1,**/*.py,**/*.sh"
---

# RC-Servo — Copilot Instructions

## After Every Code Change — MANDATORY

1. **Build** → `cmake --build --preset ch32v203-debug` — fix errors before continuing. [BUILD](BUILD/BUILD_README.instructions.md)
2. **Flash** → OpenOCD batch mode (forward slashes only). [DEBUG](DEBUG/DEBUG_README.instructions.md)
3. **Verify** → bootloader: `py -3 Target/test_bootloader_final.py` · app: VS Code F5 or USART1 check.
4. **Document** → append `Documentation/CHANGE_LOG.md` + update `Documentation/PROJECT_DOC.md`. [CHANGE_DOC](documentation/CHANGE_DOC.instructions.md) · [PROJECT_DOC](documentation/PROJECT_DOC.instructions.md)

## Before New Features

1. Update `Documentation/Requirements/requirements.md` → [REQUIREMENTS_DOC](documentation/REQUIREMENTS_DOC.instructions.md)
2. Create `Documentation/ToDo/<feature>.md` → [TODO_DOC](documentation/TODO_DOC.instructions.md)

## On Hardware / Pin Changes

1. Read relevant datasheets in `datasheets/` before touching GPIO or peripheral config.
2. Update `Documentation/PINOUT_<MCU>.md` for every affected platform.
3. Mirror pin changes in all three components (bootloader, application, bl_updater).
4. [HARDWARE](HARDWARE/HARDWARE.instructions.md)

## Rules

- Scripts: test/debug in `Target/`, build tools in `tools/`. [SCRIPTS](CODING/SCRIPTS.instructions.md)
- Coding: [COMMENTS](CODING/COMMENTS.instructions.md)
- Hardware: [HARDWARE](HARDWARE/HARDWARE.instructions.md) — consult `datasheets/`, update `PINOUT_*.md`.
- OpenOCD: forward slashes only · `flash write_image erase` (not `flash erase_sector`) · `reset halt` + `resume` (not `reset run`) · batch mode preferred.
- GDB masks bugs (`$pc=0x08000000` bypasses remap) — always verify on cold boot.
- ECDSA takes ~20s at 96 MHz — wait before checking results.
````
