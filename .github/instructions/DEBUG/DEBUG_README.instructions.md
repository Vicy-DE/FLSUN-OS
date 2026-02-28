````instructions
---
applyTo: "**"
---

# Command-Line Debugging Guide — CH32V203 (WCH RISC-V)

## Tools

| Tool | Path |
|------|------|
| OpenOCD (WCH) | `C:\MounRiver\MounRiver_Studio2\resources\app\resources\win32\components\WCH\OpenOCD\OpenOCD\bin\openocd.exe` |
| OpenOCD Config | Same directory: `wch-riscv.cfg` |
| GDB | `sdk/xpack-riscv-none-elf-gcc-14.2.0-3/bin/riscv-none-elf-gdb.exe` |
| SVD | `C:\MounRiver\MounRiver_Studio2\...\CH32V203xx.svd` |

Probe: **WCH-LinkE** via single-wire debug (SDI) on PA13.

---

## 1. Build

See [BUILD/BUILD_README.instructions.md](../BUILD/BUILD_README.instructions.md) for full build instructions.

```powershell
cmake --build --preset ch32v203-debug
```

Output: `build/ch32v203-debug/bootloader/bootloader.elf`, `application/application.elf`, `bl_updater/bl_updater.elf`

---

## 2. Flash (OpenOCD Batch Mode — Most Reliable)

```powershell
$ocd = "C:\MounRiver\MounRiver_Studio2\resources\app\resources\win32\components\WCH\OpenOCD\OpenOCD\bin"
& "$ocd\openocd.exe" -f "$ocd\wch-riscv.cfg" `
    -c "init" `
    -c "halt" `
    -c "flash write_image erase path/to/firmware.bin 0x0000" `
    -c "reset halt" `
    -c "resume" `
    -c "shutdown"
```

> **IMPORTANT:** Always use forward slashes in file paths passed to OpenOCD. Backslashes get interpreted as escape sequences (`\b` = backspace, `\t` = tab).

---

## 3. VS Code Debug (Recommended for Interactive Debugging)

Press **F5** with the appropriate launch configuration:

| Configuration | Entry Point | Use Case |
|---------------|-------------|----------|
| Debug Application (CH32V203) | `0x08004000` | Application development |
| Debug Bootloader (CH32V203) | `0x08000000` | Bootloader debugging |
| Debug BL Updater (CH32V203) | `0x08004000` | BL updater debugging |

### What Happens Automatically

1. Build task runs (`cmake --build --preset ch32v203-debug`)
2. OpenOCD starts with WCH RISC-V config
3. GDB connects to OpenOCD on `localhost:3333`
4. Firmware is flashed via `monitor flash write_image erase`
5. CPU is reset and halted
6. PC is set to the correct entry point
7. Execution breaks at `main()`

---

## 4. Manual GDB Session

### Start OpenOCD (Terminal 1)

```powershell
& "C:\MounRiver\MounRiver_Studio2\resources\app\resources\win32\components\WCH\OpenOCD\OpenOCD\bin\openocd.exe" `
    -f "C:\MounRiver\MounRiver_Studio2\resources\app\resources\win32\components\WCH\OpenOCD\OpenOCD\bin\wch-riscv.cfg" `
    -c "chip_id CH32V20x"
```

### Connect GDB (Terminal 2)

```powershell
& "sdk\xpack-riscv-none-elf-gcc-14.2.0-3\bin\riscv-none-elf-gdb.exe" `
    build/ch32v203-debug/bootloader/bootloader.elf
```

```gdb
set mem inaccessible-by-default off
set architecture riscv:rv32
set remotetimeout unlimited
target extended-remote localhost:3333
monitor reset halt
load
monitor reset halt
break main
continue
```

---

## 5. Reading CSRs for Crash Diagnosis

```powershell
$ocd = "C:\MounRiver\MounRiver_Studio2\resources\app\resources\win32\components\WCH\OpenOCD\OpenOCD\bin"
& "$ocd\openocd.exe" -f "$ocd\wch-riscv.cfg" `
    -c "init" -c "halt" `
    -c "reg mcause" `
    -c "reg mepc" `
    -c "reg mtval" `
    -c "reg mstatus" `
    -c "reg pc" `
    -c "shutdown"
```

| mcause | Meaning |
|--------|---------|
| `2` | Illegal instruction |
| `5` | Load access fault |
| `7` | Store/AMO access fault |

`mepc` = instruction that faulted. `mtval` = faulting address.

---

## 6. Automated Bootloader Testing

### Setup (one time per device)

```powershell
py -3 Target/read_uid.py                                    # Get device UID
py -3 Target/test_bootloader_setup.py --uid <12-byte-hex>   # Generate test artifacts
```

### Run Test

```powershell
cd Target
py -3 test_bootloader_final.py
```

Two-phase test:
1. **Phase 1:** Valid signature → app runs (writes to userdata at `0x0800F000`)
2. **Phase 2:** Invalid signature → bootloader stays in update mode (userdata blank)

---

## 7. Memory Map

```
Address         Size    Region
────────────────────────────────────────
0x08000000      16 KB   Bootloader
0x08004000      40 KB   Application
0x0800E000       4 KB   Factory Data
0x0800F000       4 KB   User Data
────────────────────────────────────────
0x20000000      20 KB   RAM
```

---

## 8. WCH OpenOCD Quirks

| Issue | Description | Workaround |
|-------|-------------|------------|
| `halt` resets PC | Issuing `halt` on a running target resets PC to `0x00000000` | Use `reset halt` instead |
| Breakpoints block resume | Hardware breakpoints cause `resume` to fail (`dmstatus=0x00000c82`) | Avoid persistent breakpoints; use batch mode |
| `flash erase_sector` fails | Reports success in 0ms but does not actually erase | Use `flash write_image erase` with `0xFF`-filled binary |
| `reset run` unreliable | May not start the CPU | Use `reset halt` + `resume` |
| Telnet `resume` unreliable | Works intermittently via telnet | Use batch mode for reliable execution |
| Path backslashes | `\b`, `\t` interpreted as escape chars | Always use forward slashes |

---

## 9. Hardware Connections

### WCH-Link SDI Debug

| WCH-Link Pin | Target Pin | Function |
|--------------|------------|----------|
| SWDIO | PA13 | Single-wire debug data |
| GND | GND | Ground |
| 3V3 | 3V3 | Power (optional) |

### UART Serial Output

| Signal | Pin | Baud Rate |
|--------|-----|-----------|
| USART1 TX | PA9 | 115200 |
| USART1 RX | PA10 | 115200 |

---

## 10. RISC-V Startup Remap

WCH RISC-V MCUs boot from physical flash at `0x00000000`, but code is linked at `0x08000000`. The bootloader startup assembly contains a remap jump (`lui` + `addi` + `jr`) that transitions from the physical address space to the aliased address space before any PC-relative (`auipc`) instructions execute.

The application does **not** need this fix because the bootloader jumps to it at `0x08004000` (already in the aliased range).

See `docs/bootloader_startup_fix.md` for the full root cause analysis.

---

## 11. Troubleshooting

**WCH-Link not detected** — Check USB driver (MounRiver Studio installs it). Only one application can use the probe at a time.

**OpenOCD fails to connect** — Kill existing OpenOCD processes: `Get-Process openocd | Stop-Process -Force`

**Flash write fails** — Chip may have read protection. Use WCHISPTool to perform full chip erase.

**Program doesn't start after flash** — Use `reset halt` + `resume` instead of `reset run`. Verify with CSR read that `mcause` is not a fault.

**Breakpoints not hitting** — Confirm debug build (`ch32v203-debug` preset). QingKe V4 has limited hardware breakpoints (typically 4).
````
