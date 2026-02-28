````instructions
---
applyTo: "**/*.c,**/*.h,**/*.S,**/CMakeLists.txt,**/CMakePresets.json"
---

# Project Documentation — Instructions for Copilot

## When to execute

**Step 4 of the workflow — after a successful debug session, run after CHANGE_DOC.**
Update the project documentation whenever the overall architecture, module responsibilities, key interfaces, or system behaviour change.

## Target files

Meaningful file names in `Documentation`.
Overwrite / update the relevant sections in-place. Create the file if it does not exist.

---

## Document structure (keep this structure)

```markdown
# Project Documentation — RC-Servo

**Last updated:** YYYY-MM-DD
**Build preset:** `ch32v203-debug`
**Target:** CH32V203 / CH32L103 / STM32C091

---

## 1. Project Overview
<High-level purpose of the firmware. What product/system does it implement?>

## 2. Hardware Platform
<MCU, board, peripherals in use, memory map summary, debug interface.>

## 3. Software Architecture
<Boot flow, bootloader → app handoff, signature verification, XMODEM update.>

## 4. Key Modules

| Module / File | Responsibility |
|---|---|
| `bootloader/src/bootloader.c` | Secure boot logic — signature verification, app validation, XMODEM |
| `bootloader/src/signature.c` | ECDSA P-256 signature verification using micro-ecc |
| `bootloader/platform/ch32v203/` | CH32V203 platform HAL (flash, UART, GPIO, jump-to-app) |
| `application/src/app.c` | Main application — userdata read/write, runtime logic |
| `bl_updater/src/bl_updater.c` | Bootloader updater — receives new BL via XMODEM |
| `shared/no_heap.c` | Stub to prevent heap allocation |
| ... | ... |

## 5. Build System
<CMake preset structure, key build targets, output artifacts.>

## 6. Flashing & Debug Toolchain
<OpenOCD (WCH), GDB, VS Code launch configs, batch mode flashing.>

## 7. Security
<ECDSA P-256 signatures, factory data UID hash, key management.>

## 8. Known Limitations / Open Issues
<Current known bugs, WCH quirks, workarounds, TODOs.>

## 9. Revision History (summary)
<One-line entries linking to CHANGE_LOG.md for details.>
| Date | Summary |
|---|---|
| YYYY-MM-DD | Initial documentation |
```

---

## Rules

- **MUST** update the "Last updated" date on every edit.
- **MUST** update section 4 (Key Modules) whenever files are added, removed, or responsibilities change.
- **MUST** update section 8 (Known Limitations) to reflect resolved issues and newly discovered ones.
- **MUST** add a one-line entry to section 9 (Revision History) for each update session.
- **SHOULD** keep descriptions concise — prefer tables and bullet lists over long paragraphs.
- **MUST NOT** duplicate information already in CHANGE_LOG.md — link to it instead.
- **MUST NOT** describe implementation details that belong in code comments.
````
