````instructions
---
applyTo: "**/*.c,**/*.h,**/*.S,**/CMakeLists.txt,**/CMakePresets.json"
---

# Hardware Change Rules

## On ANY Pin or Peripheral Change — MANDATORY

1. **Read datasheets** — Open and consult every relevant datasheet/reference manual from `datasheets/` before making GPIO, clock, or peripheral changes. Never guess pin alternate-function mappings.
2. **Update PINOUT.md** — Every platform that is affected must have its `Documentation/PINOUT_<MCU>.md` updated to reflect the new pin assignment, mode, speed, and alternate function.
3. **Cross-check all three components** — Bootloader, application, and bl_updater share the same pin assignments per platform. A pin change in one must be mirrored in the other two platform files.

## Datasheet Sources

All datasheets and reference manuals live in `datasheets/`. The following documents MUST be consulted:

| MCU | Document | File |
|-----|----------|------|
| CH32V203 | Datasheet | `datasheets/CH32V20x_30xDS0.PDF` |
| CH32V203 | Reference Manual | `datasheets/CH32FV2x_V3xRM.PDF` |
| CH32V203 | Core Manual | `datasheets/QingKeV4_Processor_Manual.PDF` |
| CH32L103 | Datasheet | `datasheets/CH32L103DS0.PDF` |
| CH32L103 | Reference Manual | `datasheets/CH32L103RM.PDF` |
| STM32C091 | Datasheet | `datasheets/stm32c091xx_datasheet.pdf` |
| STM32C091 | Reference Manual | `datasheets/stm32c0x1_reference_manual.pdf` |

> **If a datasheet is missing from `datasheets/`**, download it from the vendor site and place it there before proceeding.

## PINOUT.md Format

Each `Documentation/PINOUT_<MCU>.md` file must contain:

1. **ASCII art** of the MCU package (LQFP48 / TSSOP20 / etc.) showing every pin number, pin name, and assigned function.
2. **Pin function table** listing: Pin Number, Pin Name, Direction, Mode, Speed, Alternate Function, Purpose.
3. **Peripheral summary** — clock source, baud rate, bus prescalers.
4. **Notes** — pull-up/down rationale, errata, reserved pins.

## Rules

- Pin assignments are defined in platform source files under `<component>/platform/<mcu>/`.
- All three components (bootloader, application, bl_updater) MUST use identical pin assignments for a given MCU.
- Debug pins (PA13 SDI for WCH, PA13/PA14 SWD for STM32) are reserved — never reassign.
- When adding a new peripheral, update `platform.h` with the new abstraction function.
````
