````instructions
---
applyTo: "**/*.c,**/*.h"
---

# Coding Conventions — Function Comments & Side Effects

## RULE: Every Function Must Have a Documentation Comment

Every function — public or static — MUST have a Doxygen-style documentation comment immediately above the definition. Use the Google C/C++ Style Guide format:

```c
/**
 * @brief One-line summary ending with a period.
 *
 * Optional longer description explaining behaviour, edge cases, or
 * algorithm notes.  Wrap at 80 columns.
 *
 * @param[in]     name   Description of input parameter.
 * @param[out]    name   Description of output parameter.
 * @param[in,out] name   Description of input/output parameter.
 * @return Description of return value.  Use "void" implicitly (omit @return).
 *
 * @sideeffects Modifies global `tick_ms`.
 *              Writes to USART1 TX register.
 */
```

### Comment Checklist

1. `@brief` — mandatory, one sentence, imperative mood ("Compute …", not "Computes …").
2. `@param` — one per parameter, tagged `[in]`, `[out]`, or `[in,out]`.
3. `@return` — describe what the return value means (omit for `void`).
4. `@sideeffects` — mandatory if the function is *not* side-effect free (see below).

---

## RULE: Functions Must Be Side-Effect Free Unless Tagged `_sideeffects`

A **side-effect free** function:
- Does NOT modify global / static / file-scope variables.
- Does NOT write to hardware registers (GPIO, UART, Flash, SysTick, etc.).
- Does NOT perform I/O (serial, flash, memory-mapped registers).
- May only read its parameters and return a value (+ use local variables).

### Naming Convention

| Function type | Naming rule | Example |
|---------------|-------------|---------|
| Side-effect free | Normal name | `crc16_xmodem()`, `crc32_compute()` |
| Has side effects | Append `_sideeffects` to the name **OR** the function is a well-known platform API where the name already implies side effects | `platform_uart_init()`, `SysTick_Handler()` |

### Well-Known Side-Effect Exceptions

The following function name patterns are inherently understood to have side effects and do **not** need the `_sideeffects` suffix:

- `platform_*` — all platform abstraction functions (init, deinit, read, write, erase, jump, etc.)
- `*_Handler` — interrupt handlers (`SysTick_Handler`, etc.)
- `main` — entry point
- `*_init`, `*_deinit` — initialisation / teardown
- `*_run` — main loop functions (`bootloader_run`, `app_run`, `bl_updater_run`)
- `app_*`, `bl_updater_*` — platform callbacks

Any **other** function with side effects that does not match the patterns above **MUST** be named with a `_sideeffects` suffix.

### When to Use `@sideeffects`

Even for well-known exception names, the `@sideeffects` tag in the doc comment is **always required** when side effects exist. The tag documents *which* side effects occur.

```c
/**
 * @brief Send a null-terminated string over UART.
 *
 * @param[in] s  Null-terminated string to transmit.
 *
 * @sideeffects Writes bytes to USART1 TX register via platform_uart_write.
 */
static void uart_puts(const char *s)
```

---

## RULE: Header-File Declarations

Header files declare the public API. Each declaration MUST have a doc comment. The full `@param`/`@return`/`@sideeffects` block goes in the **header**, not repeated in the `.c` definition:

```c
/* In .h */
/**
 * @brief Verify an ECDSA-P256 signature over a firmware image.
 *
 * @param[in] fw_data  Pointer to firmware binary.
 * @param[in] fw_len   Length of firmware binary in bytes.
 * @param[in] sig      Pointer to 64-byte raw ECDSA signature (r || s).
 * @return 1 if valid, 0 if invalid.
 */
int signature_verify(const uint8_t *fw_data, size_t fw_len, const uint8_t *sig);
```

In the `.c` file, a shorter comment referencing the header is acceptable:

```c
/* See signature.h for full documentation. */
int signature_verify(const uint8_t *fw_data, size_t fw_len, const uint8_t *sig)
{
    ...
}
```

---

## Reference

- [Google C++ Style Guide — Comments](https://google.github.io/styleguide/cppguide.html#Comments)
- Doxygen `@brief`, `@param`, `@return`: <https://www.doxygen.nl/manual/commands.html>
````
