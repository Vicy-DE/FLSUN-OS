````instructions
---
applyTo: "**/*.c,**/*.h,**/*.S,**/CMakeLists.txt,**/CMakePresets.json"
---

# Change Documentation — Instructions for Copilot

## When to execute

**Step 4 of the workflow — after a successful debug/verification session.**
Run this step every time code, config, or assembly files are changed and the change has been verified on hardware.

## Target file

`CHANGE_LOG.md` in `Documentation`.
Append a new entry at the top of the file (newest entry first). Create the file if it does not exist.

---

## Entry format

```markdown
## [YYYY-MM-DD] <Short title of the change>

### What was changed
- <file or component> — <brief description of the concrete change>
- ...

### Why it was changed
<Reason: bug fix / feature addition / refactoring / hardware requirement / etc.>

### What it does / expected behaviour
<Description of the new or corrected behaviour after the change. What the system should do now.>

### Verified
- Build: OK
- Flash: OK
- Debug: OK — (<optional: observation, test result, CSR values, etc.>)
```

---

## Rules

- **MUST** create an entry for every change session before closing the task.
- **MUST** list every modified file with a one-line summary of what changed.
- **MUST** state a clear reason (the "why").
- **MUST** describe the observable effect / expected behaviour.
- **MUST** confirm build / flash / debug status.
- **MUST NOT** omit the entry even for "small" or "trivial" changes.
- **SHOULD** use past tense for "What was changed", present tense for "What it does".
````
