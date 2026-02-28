````instructions
---
applyTo: "**/*.c,**/*.h,**/*.S,**/CMakeLists.txt,**/CMakePresets.json,**/*.bat,**/*.ps1,**/*.py,**/*.sh"
---

# Coding Conventions — Scripts

## RULE: Script Locations

Scripts are organized by purpose into two directories:

| Directory | Purpose | Examples |
|-----------|---------|---------|
| `Target/` | Hardware interaction — flashing, debugging, testing, UID reading | `test_bootloader_final.py`, `read_uid.py` |
| `tools/` | Build tools — signing, key generation, factory data creation | `sign_firmware.py`, `generate_keys.py`, `create_factorydata.py` |

**MUST:** Place new scripts in the appropriate directory based on their purpose.

### Exceptions (do NOT move)

| Path pattern | Reason |
|---|---|
| `sdk/**` | Third-party SDK scripts — never modify or move |

---

## RULE: Use Script-Relative Paths

When a script needs to reference files relative to the project root, use the script's own location as the anchor — **never** `os.getcwd()` or `$PWD`.

### Python

```python
import os
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.join(SCRIPT_DIR, "..")
```

### PowerShell

```powershell
$ScriptDir = Split-Path $MyInvocation.MyCommand.Path -Parent
$ProjectRoot = Split-Path $ScriptDir -Parent
```

---

## RULE: OpenOCD Path Handling

When passing file paths to OpenOCD, **always use forward slashes**. Backslashes are interpreted as escape sequences (`\b` = backspace, `\t` = tab).

```python
path = os.path.join(BUILD_DIR, "bootloader.bin").replace("\\", "/")
```

---

## RULE: Naming Convention

- Use `snake_case` for Python scripts: `test_bootloader_final.py`, `read_uid.py`
- Use `kebab-case` for shell scripts: `build-all.ps1`
- Exception: legacy scripts may keep their established names

---

## RULE: Never Create Temporary Scripts in the Workspace Root

Do **NOT** create one-off analysis/debug scripts in the workspace root or random directories.

- Use the terminal directly for one-off commands
- If a diagnostic script is needed, place it in `Target/` with a `diag_` prefix
- Only create a permanent script if it will be reused

---

## Target/ Inventory

| Script | Language | Purpose |
|--------|----------|---------|
| `test_bootloader_final.py` | Python | Two-phase bootloader signature verification test (OpenOCD batch mode) |
| `test_bootloader_setup.py` | Python | Generate signed/unsigned test binaries and factory data |
| `read_uid.py` | Python | Read 12-byte device UID via OpenOCD |

## tools/ Inventory

| Script | Language | Purpose |
|--------|----------|---------|
| `sign_firmware.py` | Python | Sign firmware binary with ECDSA P-256 |
| `generate_keys.py` | Python | Generate ECDSA P-256 key pairs for firmware and factory data signing |
| `create_factorydata.py` | Python | Create factory data binary with UID hash and signature |
````
