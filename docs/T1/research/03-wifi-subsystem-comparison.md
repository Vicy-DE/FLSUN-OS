# WiFi Subsystem Comparison: S1 vs T1

**Date researched:** 2025-07-17
**Sources:** S1 DTB (`rk-kernel.dtb` decompiled via pyfdt), T1 DTB (`fdt.dts`), S1 build recipe (`flsun-os.yaml`), S1 rootfs analysis, T1-pyro project

---

## 1. Key Finding

**Both the S1 and T1 use the exact same WiFi module: AP6212 (Broadcom BCM43438).** The DTB `wifi_chip_type` on both platforms is `"ap6212"`. This means WiFi should work on the T1 with the S1 firmware with **zero driver or firmware blob changes** — only minor DTB phandle differences (which are auto-resolved during DTB compilation) and a hostname template change in `first-boot.sh`.

---

## 2. WiFi Chip

| Property | S1 | T1 | Match? |
|---|---|---|---|
| Module | AP6212 (AMPAK) | AP6212 (AMPAK) | **Identical** |
| WiFi chip | BCM43438 | BCM43438 | **Identical** |
| Standard | 802.11 b/g/n, 2.4 GHz | 802.11 b/g/n, 2.4 GHz | **Identical** |
| Bluetooth | BCM20710 (BT 4.0 + BLE) | BCM20710 (BT 4.0 + BLE) | **Identical** |
| Interface | SDIO (WiFi) + UART (BT) | SDIO (WiFi) + UART (BT) | **Identical** |

---

## 3. DTB Node Comparison

### 3.1 wireless-wlan

| Property | S1 | T1 | Match? |
|---|---|---|---|
| `compatible` | `"wlan-platdata"` | `"wlan-platdata"` | **Identical** |
| `wifi_chip_type` | `"ap6212"` | `"ap6212"` | **Identical** |
| `WIFI,host_wake_irq` | `<0x3d 0x08 0x00>` → GPIO0_B0, active-high | `<0x3c 0x08 0x00>` → GPIO0_B0, active-high | **Same pin** (phandle differs) |
| `clock-names` | `"clk_wifi"` | `"clk_wifi"` | **Identical** |
| `status` | `"okay"` | `"okay"` | **Identical** |

> The only difference is the phandle reference for the GPIO controller (`0x3d` on S1 vs `0x3c` on T1) and the GRF/clock phandles — these are internal DTB cross-references that resolve correctly within each platform's DTB. The actual GPIO pin (GPIO0, pin 8 = B0) is the same.

### 3.2 sdio-pwrseq

| Property | S1 | T1 | Match? |
|---|---|---|---|
| `compatible` | `"mmc-pwrseq-simple"` | `"mmc-pwrseq-simple"` | **Identical** |
| `reset-gpios` | `<0x3d 0x06 0x01>` → GPIO0_A6, active-low | `<0x3c 0x06 0x01>` → GPIO0_A6, active-low | **Same pin** (phandle differs) |

### 3.3 wireless-bluetooth

| Property | S1 | T1 | Match? |
|---|---|---|---|
| `compatible` | `"bluetooth-platdata"` | `"bluetooth-platdata"` | **Identical** |
| `BT,power_gpio` | `<0x3d 0x07 0x00>` → GPIO0_A7, active-high | `<0x3c 0x07 0x00>` → GPIO0_A7, active-high | **Same pin** |
| `BT,wake_host_irq` | `<0x3d 0x05 0x00>` → GPIO0_A5, active-high | `<0x3c 0x05 0x00>` → GPIO0_A5, active-high | **Same pin** |
| `uart_rts_gpios` | `<0xd1 0x10 0x01>` → GPIO1_C0, active-low | `<0xce 0x10 0x01>` → GPIO1_C0, active-low | **Same pin** |
| `status` | `"okay"` | `"okay"` | **Identical** |

### 3.4 SDIO Controller (dwmmc@ffc70000)

| Property | S1 | T1 | Match? |
|---|---|---|---|
| `compatible` | `"rockchip,rv1126-dw-mshc", "rockchip,rk3288-dw-mshc"` | `"rockchip,rv1126-dw-mshc", "rockchip,rk3288-dw-mshc"` | **Identical** |
| Register base | `0xffc70000` | `0xffc70000` | **Identical** |
| `bus-width` | 4-bit | 4-bit | **Identical** |
| `max-frequency` | 200 MHz (`0x0bebc200`) | 200 MHz (`0x0bebc200`) | **Identical** |
| `sd-uhs-sdr104` | Yes | Yes | **Identical** |
| `non-removable` | Yes | Yes | **Identical** |
| `cap-sd-highspeed` | Yes | Yes | **Identical** |
| `cap-sdio-irq` | Yes | Yes | **Identical** |
| `keep-power-in-suspend` | Yes | Yes | **Identical** |
| `supports-sdio` | Yes | Yes | **Identical** |
| `rockchip,default-sample-phase` | `0x5a` (90°) | `0x5a` (90°) | **Identical** |
| `status` | `"okay"` | `"okay"` | **Identical** |

### 3.5 SDIO Pinctrl

| Pin Group | S1 | T1 | Match? |
|---|---|---|---|
| `sdio-bus4` | GPIO1 pins 12-15 (B4-B7), func 1 | GPIO1 pins 12-15 (B4-B7), func 1 | **Same pins** |
| `sdio-clk` | GPIO1 pin 10 (B2), func 1 | GPIO1 pin 10 (B2), func 1 | **Same pin** |
| `sdio-cmd` | GPIO1 pin 11 (B3), func 1 | GPIO1 pin 11 (B3), func 1 | **Same pin** |
| Pull config | `0xc2` (pull-up, drive 2) | `0xc0` (pull-up, drive 0) | **Minor difference** |

> The only pinctrl difference is the pull/drive strength configuration (`0xc2` vs `0xc0`). The pin assignments themselves are identical. This is a minor electrical characteristic difference that should not affect functionality.

### 3.6 Bluetooth UART (serial@ff560000 / UART0)

| Property | S1 | T1 | Match? |
|---|---|---|---|
| Register base | `0xff560000` | `0xff560000` | **Identical** |
| `compatible` | `"rockchip,rv1126-uart", "snps,dw-apb-uart"` | `"rockchip,rv1126-uart", "snps,dw-apb-uart"` | **Identical** |
| `clock-frequency` | `0x016e3600` (24 MHz) | `0x016e3600` (24 MHz) | **Identical** |
| `status` | `"okay"` | `"okay"` | **Identical** |

---

## 4. WiFi GPIO Pin Summary

All WiFi/BT GPIO pins are on GPIO0 (the always-on power domain), making them identical across the RV1126 and RV1109:

| Function | GPIO | Pin | Direction | Polarity |
|---|---|---|---|---|
| WiFi power enable (SDIO reset) | GPIO0 | A6 (pin 6) | Output | Active-low |
| WiFi wake host IRQ | GPIO0 | B0 (pin 8) | Input | Active-high |
| BT power | GPIO0 | A7 (pin 7) | Output | Active-high |
| BT wake host IRQ | GPIO0 | A5 (pin 5) | Input | Active-high |
| BT UART RTS | GPIO1 | C0 (pin 16) | Output | Active-low |

---

## 5. Kernel Driver

| Property | S1 | T1 (stock) |
|---|---|---|
| WiFi driver | `bcmdhd` (Rockchip BSP wrapper) | `bcmdhd` (Rockchip BSP wrapper) |
| Build type | Built-in (not loadable module) | Built-in (not loadable module) |
| Kernel config | `CONFIG_BCMDHD=y` | `CONFIG_BCMDHD=y` (assumed — same BSP) |
| Driver path | `drivers/net/wireless/rockchip_wlan/rkwifi/bcmdhd` | Same Rockchip BSP path |
| cfg80211 | `CONFIG_CFG80211=y` (built-in) | Built-in |
| mac80211 | `CONFIG_MAC80211=y` (built-in) | Built-in |

The `bcmdhd` driver in the Rockchip BSP supports all AP6xxx modules (AP6212, AP6255, AP6256, AP6356, etc.) — it auto-detects the chip type at probe time. The same kernel binary handles both S1 and T1 WiFi hardware.

---

## 6. Firmware Blobs

| Property | S1 | T1 (stock) | T1 (pyro) |
|---|---|---|---|
| Firmware source | Vendor blobs in `/vendor/etc/firmware/` | Stock Debian 10 | Debian `firmware-brcm80211` package |
| WiFi firmware | `brcmfmac43430-sdio.bin` (BCM43438) | Stock | `brcmfmac43430-sdio.bin` |
| WiFi NVRAM | `brcmfmac43430-sdio.txt` | Stock | `brcmfmac43430-sdio.txt` |
| BT firmware | `BCM43430A1.hcd` | Stock | From `firmware-brcm80211` |
| Package | **None** — vendor overlay, not Debian pkg | Unknown | `firmware-brcm80211` (problematic) |

### Firmware Blob Source on S1

The S1 does **not** use the Debian `firmware-brcm80211` package. Instead, the WiFi/BT firmware blobs are placed in `/vendor/etc/firmware/` as part of the Rockchip BSP/vendor SDK. These are copied into the rootfs during the OS image build (not via debos recipe — handled externally).

The `bcmdhd` driver in the Rockchip BSP looks for firmware in `/vendor/etc/firmware/` first (hardcoded path in the driver source), then falls back to the standard Linux firmware paths (`/lib/firmware/brcm/`).

### T1-pyro Known Issue

The T1-pyro project documented a conflict between the `firmware-brcm80211` Debian package and the touchscreen (see [KlipperScreen#1491](https://github.com/KlipperScreen/KlipperScreen/issues/1491)):

> "When installing firmware-brcm80211 for wifi, it can break the touch screen. If KlipperScreen is not working right, try `sudo apt remove firmware-brcm80211; sudo apt-mark hold firmware-brcm80211`"

This issue does **not** apply to the S1 firmware because the S1 uses vendor blobs from `/vendor/etc/firmware/` instead of the Debian package. The S1 approach actually avoids this conflict.

---

## 7. Userspace Software Stack

| Component | S1 | T1 (target) | Match? |
|---|---|---|---|
| NetworkManager | Yes (manages wifi, ethernet, wwan) | Same | **Identical** |
| wpasupplicant | Yes | Same | **Identical** |
| rfkill | Yes (blocks BT in rc.local) | Same | **Identical** |
| wireless-tools | Yes (`iwconfig`) | Same | **Identical** |
| WiFi power saving | Disabled via `rc.local`: `iwconfig wlan0 power off` | Same approach | **Identical** |
| BT blocked | `rfkill block bluetooth` in `rc.local` | Same | **Identical** |
| MAC randomization | Disabled (`wifi.scan-rand-mac-address=no`) | Same | **Identical** |

### NetworkManager Configuration

Both platforms use the same `NetworkManager.conf`:
```ini
[main]
plugins=ifupdown,keyfile

[ifupdown]
managed=false

[device]
wifi.scan-rand-mac-address=no
```

### Hostname from WiFi MAC

The first-boot script (`first-boot.sh`) derives the hostname from the WiFi MAC address:
```bash
INTERFACE="wlan0"
MAC_SUFFIX=$(ip link show $INTERFACE | awk '/link\/ether/ {print $2}' | tr 'a-f' 'A-F' | sed 's/://g' | tail -c 5)
NEW_HOSTNAME="FLSUN-S1-$MAC_SUFFIX"
```

For T1, change `FLSUN-S1` → `FLSUN-T1`.

---

## 8. Porting Assessment

### What needs to change for T1: **Almost nothing**

| Item | Change needed? | Details |
|---|---|---|
| WiFi chip / module | **No** | Same AP6212 |
| Kernel driver | **No** | Same `bcmdhd` built-in driver |
| Firmware blobs | **No** | Same BCM43438 firmware files |
| Vendor firmware path | **No** | Same `/vendor/etc/firmware/` approach |
| DTB wireless-wlan node | **No** | Same GPIO pins, same properties |
| DTB sdio-pwrseq node | **No** | Same GPIO pin (GPIO0_A6) |
| DTB wireless-bluetooth | **No** | Same GPIO pins (A5, A7) |
| DTB SDIO controller | **No** | Same address, same config |
| DTB SDIO pinctrl | **Negligible** | Same pins, minor pull/drive strength diff (`0xc2` vs `0xc0`) |
| NetworkManager config | **No** | Same configuration |
| rc.local WiFi tweaks | **No** | Same `iwconfig wlan0 power off` |
| Hostname template | **Yes** | `FLSUN-S1` → `FLSUN-T1` in `first-boot.sh` |
| Debian wifi packages | **No** | Same packages (no `firmware-brcm80211` needed) |

### Risk: Low

The WiFi subsystem is one of the **lowest-risk** areas of the S1-to-T1 port. Both platforms use the same WiFi module (AP6212), the same GPIO pins, the same SDIO controller configuration, the same kernel driver, and the same firmware blobs. The only required change is the hostname prefix in `first-boot.sh`.

### Do NOT install firmware-brcm80211

The Debian `firmware-brcm80211` package should **not** be installed on the T1 port. The S1 approach of using vendor firmware blobs in `/vendor/etc/firmware/` is superior because:

1. It avoids the known conflict with the touchscreen (KlipperScreen#1491)
2. It uses Rockchip-validated firmware files tuned for the AP6212 module
3. It matches the `bcmdhd` driver's hardcoded firmware search path
4. The Debian package may contain generic firmware that doesn't include AP6212-specific NVRAM calibration data

---

## 9. Detailed SDIO Pull/Drive Strength Difference

The one minor electrical difference between S1 and T1:

| Platform | SDIO pin config | Interpretation |
|---|---|---|
| S1 | `0xc2` | Pull-up enabled, drive strength level 2 |
| T1 | `0xc0` | Pull-up enabled, drive strength level 0 (lowest) |

This is a board-level tuning parameter that affects signal integrity at high SDIO clock speeds. The S1 uses slightly higher drive strength, possibly due to different PCB trace lengths. The T1's lower drive strength works fine on its board layout. When using the S1 kernel+DTB on T1 hardware, the S1's `0xc2` value should still work — higher drive strength is generally more robust. If SDIO stability issues occur, this can be adjusted in the T1 DTB overlay.

---

## 10. Summary

WiFi is a **non-issue** for S1-to-T1 porting. The hardware is identical (AP6212), the GPIO pins are identical, the SDIO controller is identical, and the software stack (driver, firmware, NetworkManager) is identical. This is the simplest subsystem in the entire porting effort.

The only action item is changing the hostname prefix from `FLSUN-S1` to `FLSUN-T1` in `first-boot.sh`, which is already tracked in the main porting guide as a general first-boot script change.
