# FLSUN T1 — Kernel Build Process & Display Driver Analysis

**Date researched:** 2026-02-28  
**Sources:**
- FLSUN OS 3.0 boot.img reverse engineering (kernel-config.txt, rk-kernel.dts)
- Rockchip BSP kernel: https://github.com/rockchip-linux/kernel (branch `develop-6.1`)
- Rockchip rkbin: https://github.com/rockchip-linux/rkbin
- Rockchip boot wiki: https://opensource.rock-chips.com/wiki_Boot_option
- T1-pyro project: https://github.com/mulcmu/T1-pyro
- S1 kernel analysis: docs/S1/research/11-kernel-devicetree-analysis.md

---

## 1. S1 Custom Kernel — Version & Build

### Kernel Version

```
Linux version 6.1.99flsun OS (root@FLSUN-OS)
  (arm-linux-gnueabihf-gcc (Ubuntu 11.4.0-1ubuntu1~22.04) 11.4.0)
  #38 SMP PREEMPT Mon Mar 31 20:03:38 CEST 2025
```

| Property | Value |
|---|---|
| Base version | **6.1.99** (LTS) |
| Local suffix | `flsun OS` |
| Source tree | **Rockchip BSP kernel** (`rockchip-linux/kernel`, branch `develop-6.1`) |
| Build number | #38 |
| Preemption | Full PREEMPT (real-time) |
| Monolithic | **Yes** — zero loadable modules (all `=y`, no `=m`) |
| Cross-compiler | `arm-linux-gnueabihf-gcc` 11.4.0 (Ubuntu 22.04) |
| zImage size | 8.14 MB compressed, 19.70 MB decompressed |
| DTB size | 122 KB (in RSCE container) |

### How to Build the Custom Kernel

The kernel is compiled from the **Rockchip downstream BSP kernel** — not mainline Linux. The `develop-6.1` branch of `rockchip-linux/kernel` contains all necessary Rockchip-specific drivers (ISP, NPU, VPU, RGA, DRM, CAN, etc.).

**Build commands (reconstructed):**

```bash
# 1. Clone the Rockchip BSP kernel
git clone -b develop-6.1 https://github.com/rockchip-linux/kernel.git
cd kernel

# 2. Use the RV1126 defconfig as base
make ARCH=arm rv1126_defconfig

# 3. Customize the config (make everything built-in, no modules)
make ARCH=arm menuconfig
# Key changes from stock defconfig:
#   - Set all =m to =y (fully monolithic)
#   - CONFIG_PREEMPT=y (full preemption)
#   - CONFIG_HZ=300
#   - CONFIG_CAN=y (full CAN stack)
#   - CONFIG_DRM_PANEL_SIMPLE=y
#   - CONFIG_ROCKCHIP_RGB=y
#   - CONFIG_ROCKCHIP_VOP=y
#   - CONFIG_ROCKCHIP_MINI_KERNEL=y
#   - CONFIG_IKCONFIG=y (embed .config in kernel)

# 4. Cross-compile
make ARCH=arm CROSS_COMPILE=arm-linux-gnueabihf- -j$(nproc) zImage dtbs

# Output:
#   arch/arm/boot/zImage                              → compressed kernel
#   arch/arm/boot/dts/rockchip/rv1126-*.dtb           → device tree blob
```

**Packaging into boot.img:**

```bash
# 5. Create Rockchip Resource Image containing the DTB
resource_tool --pack --image=resource.img rk-kernel.dtb

# 6. Package into Android boot image format
mkbootimg \
  --kernel arch/arm/boot/zImage \
  --second resource.img \
  --base 0x10000000 \
  --kernel_offset 0x00008000 \
  --second_offset 0x00F00000 \
  --tags_offset 0x00000100 \
  --pagesize 2048 \
  --output boot.img
```

**Required tools:**
- `arm-linux-gnueabihf-gcc` (Ubuntu/Debian: `gcc-arm-linux-gnueabihf` package)
- `mkbootimg` (from Android tools or Rockchip SDK)
- `resource_tool` (from Rockchip rkbin repo)

---

## 2. Building for the T1 (Rockchip RV1109)

### RV1109 vs RV1126 — Same Kernel Source, Different Config

The RV1109 and RV1126 are from the **same Rockchip RV11xx family** and share the same kernel source tree. Key differences:

| Feature | RV1126 (S1) | RV1109 (T1) |
|---|---|---|
| CPU cores | **Quad**-core Cortex-A7 @ 1.51 GHz | **Dual**-core Cortex-A7 |
| NPU | 2 TOPS (AI inference) | 1.2 TOPS (reduced) |
| ISP | 14-megapixel | 8-megapixel |
| VPU | H.265/H.264 encode+decode | Same |
| Display | MIPI DSI, RGB, LVDS | MIPI DSI, RGB, LVDS |
| GPIO/Peripherals | Same pinmux | Same pinmux |
| Kernel defconfig | `rv1126_defconfig` | **`rv1126_defconfig`** (shared!) |
| Device tree | `rv1126-*.dts` | `rv1109-*.dts` |

> **Critical finding:** The RV1109 and RV1126 share the **same defconfig** (`rv1126_defconfig`) in the Rockchip kernel tree. The SoC distinction is handled entirely by the **device tree** — `rockchip,rv1109` vs `rockchip,rv1126` compatible strings. The kernel binary (zImage) is identical; only the DTB differs.

### Building a Kernel for T1

```bash
# 1. Same kernel source as S1
git clone -b develop-6.1 https://github.com/rockchip-linux/kernel.git
cd kernel

# 2. Same defconfig — RV1109 uses rv1126_defconfig
make ARCH=arm rv1126_defconfig

# 3. Customize config (copy the S1 kernel-config.txt as starting point)
#    Differences for T1:
#    - May want to disable quad-core SMP optimizations (only 2 cores)
#    - Display: need T1-specific panel timings (different screen!)
#    - CAN: may or may not be needed
#    - NPU: reduced, consider disabling if not used
make ARCH=arm menuconfig

# 4. Cross-compile — identical process
make ARCH=arm CROSS_COMPILE=arm-linux-gnueabihf- -j$(nproc) zImage dtbs

# 5. Use a T1-specific device tree
#    Need: rv1109-evb-ddr3-t1.dts (must be created or adapted)
#    Base: rv1109-evb-ddr3-v1x.dts from Rockchip tree + T1 panel definition
```

### T1-Specific rkbin Files

The RV1109 has its own bootloader binaries in the Rockchip rkbin repo:

| File | Purpose |
|---|---|
| `rv1109_ddr_924MHz_v*.bin` | DDR3 initialization |
| `rv1109_spl_v*.bin` | Secondary Program Loader |
| `rv1109_usbplug_v*.bin` | USB flashing mode plugin |
| `rv1109_tee_ta_v*.bin` | OP-TEE (Trusted Execution) |
| `RKBOOT/RV1109MINIALL.ini` | Loader packaging config |
| `RKTRUST/RV1109TOS.ini` | Trust image packaging config |

> **Note:** The DDR init and SPL binaries are SoC-specific and **cannot** be shared between RV1109 and RV1126. You must use the correct RV1109 versions from rkbin.

---

## 3. Display Drivers — Where They Live

### Architecture: All Display Drivers Are in the Kernel

The display pipeline has **three layers**, and **all are compiled into the kernel** (built-in, not modules):

```
┌─────────────────────────────────────────────────────────────┐
│                    USERSPACE                                 │
│  KlipperScreen → X11 (xserver-xorg-video-fbdev) → /dev/fb0 │
│                  or via DRM → /dev/dri/card0                │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────┴──────────────────────────────────┐
│                    KERNEL (built-in)                         │
│                                                              │
│  Layer 1: DRM Subsystem                                      │
│    CONFIG_DRM=y                                              │
│    CONFIG_DRM_KMS_HELPER=y                                   │
│    CONFIG_DRM_FBDEV_EMULATION=y  ← provides /dev/fb0         │
│    CONFIG_DRM_PANEL=y                                        │
│    CONFIG_DRM_PANEL_SIMPLE=y     ← generic panel driver      │
│    CONFIG_DRM_SIMPLEDRM=y                                    │
│    CONFIG_FB=y                   ← framebuffer core          │
│                                                              │
│  Layer 2: Rockchip DRM Driver                                │
│    CONFIG_DRM_ROCKCHIP=y         ← main Rockchip DRM         │
│    CONFIG_ROCKCHIP_VOP=y         ← Video Output Processor    │
│    CONFIG_ROCKCHIP_RGB=y         ← RGB parallel interface    │
│    CONFIG_ROCKCHIP_DW_MIPI_DSI=y ← MIPI DSI (disabled in DTB)│
│    CONFIG_ROCKCHIP_DW_MIPI_DSI2=y                            │
│    CONFIG_ROCKCHIP_LVDS=y        ← LVDS (disabled in DTB)    │
│    CONFIG_ROCKCHIP_RGA=y         ← 2D accelerator            │
│    CONFIG_ROCKCHIP_RGA2=y                                    │
│    CONFIG_ROCKCHIP_DRM_DIRECT_SHOW=y                         │
│                                                              │
│  Layer 3: Backlight                                          │
│    CONFIG_BACKLIGHT_CLASS_DEVICE=y                            │
│    CONFIG_BACKLIGHT_PWM=y        ← PWM-controlled backlight  │
│    CONFIG_BACKLIGHT_GPIO=y                                   │
│                                                              │
│  ONLY external module: galcore.ko (Vivante GPU/NPU)          │
│    → NOT for display, used for NPU AI inference              │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────┴──────────────────────────────────┐
│                DEVICE TREE (DTB in boot.img)                 │
│  Defines: panel timings, interface type, backlight PWM,      │
│           VOP port connections, enable/disable interfaces     │
└─────────────────────────────────────────────────────────────┘
```

### Key Finding: Display Drivers Are NOT on the Rootfs Partition

| Component | Location | Type |
|---|---|---|
| DRM Rockchip driver | **Kernel** (built-in) | `CONFIG_DRM_ROCKCHIP=y` |
| VOP (Video Output Processor) | **Kernel** (built-in) | `CONFIG_ROCKCHIP_VOP=y` |
| RGB parallel interface | **Kernel** (built-in) | `CONFIG_ROCKCHIP_RGB=y` |
| MIPI DSI interface | **Kernel** (built-in) | `CONFIG_ROCKCHIP_DW_MIPI_DSI=y` |
| Panel driver | **Kernel** (built-in) | `CONFIG_DRM_PANEL_SIMPLE=y` |
| Backlight (PWM) | **Kernel** (built-in) | `CONFIG_BACKLIGHT_PWM=y` |
| Panel timing/resolution | **DTB** (in boot.img) | Device tree node `panel@0` |
| Framebuffer emulation | **Kernel** (built-in) | `CONFIG_DRM_FBDEV_EMULATION=y` |
| X11 fbdev driver | **Rootfs** (package) | `xserver-xorg-video-fbdev` |
| galcore.ko (NPU) | **Rootfs** (`/lib/modules/`) | Only loadable module |

> **Conclusion:** The display hardware drivers are **100% in the kernel** (boot partition), compiled as built-in. The rootfs only has the X11 userspace component (`xserver-xorg-video-fbdev`). The `galcore.ko` on the rootfs is for the NPU, NOT the display.

---

## 4. S1 Display — Isolated Configuration

### S1 Panel (from DTB `rk-kernel.dts`)

The S1 uses an **RGB parallel interface** panel — NOT MIPI DSI:

```dts
panel@0 {
    compatible = "simple-panel";
    bus-format = <0x100e>;          /* MEDIA_BUS_FMT_RGB888_1X24 */
    rgb-mode = "p888";              /* 24-bit parallel RGB */
    width-mm = <150>;               /* 150mm physical width */
    height-mm = <94>;               /* 94mm physical height */
    connector-type = "HDMI";        /* Reported as HDMI connector type */
    backlight = <&backlight>;
    status = "okay";

    display-timings {
        native-mode = <&timing0>;
        timing0: timing0 {
            clock-frequency = <51200000>;   /* 51.2 MHz pixel clock */
            hactive = <1024>;               /* 1024 pixels wide */
            vactive = <600>;                /* 600 pixels tall */
            hback-porch = <160>;
            hfront-porch = <160>;
            vback-porch = <23>;
            vfront-porch = <12>;
            hsync-len = <20>;
            vsync-len = <3>;
            de-active = <1>;
        };
    };

    port {
        endpoint {
            remote-endpoint = <&rgb_out_panel>;
        };
    };
};

backlight {
    compatible = "pwm-backlight";
    pwms = <&pwm0 0 25000 0>;       /* PWM0, 25µs period (40 kHz) */
    brightness-levels = <0 1 2 ... 255>;  /* 256 levels */
    default-brightness-level = <100>;
};
```

**S1 display-subsystem routing:**

```dts
display-subsystem {
    compatible = "rockchip,display-subsystem";
    status = "okay";

    route {
        route-dsi {
            status = "disabled";     /* MIPI DSI route: OFF */
        };
        route-rgb {
            status = "okay";         /* RGB route: ACTIVE */
            logo,uboot = "logo.bmp";
            logo,kernel = "logo_kernel.bmp";
        };
    };
};

/* VOP output port connections */
vop@ffb00000 {
    port {
        endpoint@0 { remote-endpoint = <&rgb_in_vop>; };   /* → RGB */
        endpoint@1 { remote-endpoint = <&dsi_in_vop>; };   /* → DSI (disabled) */
    };
};

/* RGB interface in GRF */
syscon@fe000000 {
    rgb {
        compatible = "rockchip,rv1126-rgb";
        status = "okay";
        port@0 { endpoint@0 { remote-endpoint = <&vop_out_rgb>; }; };  /* from VOP */
        port@1 { endpoint@0 { remote-endpoint = <&panel_in_rgb>; }; }; /* to panel */
    };
};
```

### S1 Display Pipeline Summary

```
VOP (ffb00000) → RGB (in GRF fe000000) → panel@0 (simple-panel, 1024×600)
                                           ↑
                                       backlight (PWM0)
```

### S1 Panel Specs

| Property | Value |
|---|---|
| Resolution | 1024 × 600 (WSVGA) |
| Physical size | 150 × 94 mm (~7" diagonal) |
| Pixel format | RGB888 (24-bit, 8 bits per color) |
| Interface | RGB parallel (24 data lines) |
| Pixel clock | 51.2 MHz |
| Refresh rate | ~60 Hz (calculated from timings) |
| Backlight | PWM-controlled, 256 brightness levels |
| Panel driver | `simple-panel` (generic, timings-only) |

---

## 5. T1 Display — Resolved from Stock Firmware

> **Updated 2026-02-28:** All display unknowns have been resolved by extracting and analyzing the T1 stock firmware. See [04-stock-firmware-analysis.md](04-stock-firmware-analysis.md) for the full extraction.

### Confirmed Facts

- The T1 uses **RGB parallel interface** — same as S1, **NOT MIPI DSI**
- DSI hardware exists in the RV1109 silicon but is **explicitly disabled** in the T1 DTB
- The T1 panel is **800×480** at 25 MHz pixel clock (S1 is 1024×600 at 51.2 MHz)
- Physical panel size: **95×54 mm (~3.5")** (S1 is 150×94 mm ~7")
- Bus format: **RGB888 24-bit** (`bus-format = <0x1013>`, `rgb-mode = "p888"`)
- Panel driver: `simple-panel` (generic, timings-only — no IC initialization commands needed)
- Backlight: PWM channel 0 at 40 kHz, 256 brightness levels
- Enable GPIO: GPIO3_D4 (active low, with 20ms enable delay)
- The "vertical lines" seen when running S1 OS on T1 are caused by **wrong resolution and timing parameters**, not an interface mismatch

### T1 Panel Specs (from stock DTB)

| Property | Value |
|---|---|
| Resolution | 800 × 480 (WVGA) |
| Physical size | 95 × 54 mm (~3.5" diagonal) |
| Pixel format | RGB888 (24-bit, `bus-format = <0x1013>`) |
| Interface | RGB parallel (24 data lines) |
| Pixel clock | 25 MHz |
| H back/front porch | 8 / 8 |
| V back/front porch | 8 / 8 |
| H/V sync length | 4 / 4 |
| Backlight | PWM0, 256 levels, default=100 |
| Enable GPIO | GPIO3_D4 (active low) |
| Panel driver | `simple-panel` |

### T1 vs S1 Panel Comparison

| Parameter | T1 Stock | S1 (FLSUN OS) |
|---|---|---|
| Resolution | 800×480 | 1024×600 |
| Physical size | 95×54 mm (~3.5") | 150×94 mm (~7") |
| Interface | RGB parallel (P888) | RGB parallel (P888) |
| Pixel clock | 25 MHz | 51.2 MHz |
| Bus format | 0x1013 (RGB888_1X24) | 0x100E (RGB666_1X18) |
| H back porch | 8 | 160 |
| H front porch | 8 | 160 |
| V back porch | 8 | 23 |
| V front porch | 8 | 12 |
| H sync length | 4 | 20 |
| V sync length | 4 | 3 |
| Enable GPIO | GPIO3_D4 (active low) | None (pinctrl only) |

### T1 Stock Display DTB (extracted)

```dts
panel@0 {
    compatible = "simple-panel";
    bus-format = <0x1013>;          /* MEDIA_BUS_FMT_RGB888_1X24 */
    backlight = <&backlight>;
    enable-gpios = <&gpio3 28 GPIO_ACTIVE_LOW>;
    enable-delay-ms = <20>;
    rgb-mode = "p888";
    width-mm = <95>;
    height-mm = <54>;
    status = "okay";

    display-timings {
        timing0 {
            clock-frequency = <25000000>;
            hactive = <800>;
            vactive = <480>;
            hback-porch = <8>;
            hfront-porch = <8>;
            vback-porch = <8>;
            vfront-porch = <8>;
            hsync-len = <4>;
            vsync-len = <4>;
            hsync-active = <1>;
            vsync-active = <1>;
            de-active = <1>;
            pixelclk-active = <1>;
        };
    };
};

/* Display routing — RGB active, DSI disabled */
display-subsystem {
    route {
        route-dsi { status = "disabled"; };
        route-rgb { status = "okay"; };
    };
};
```

---

## 6. Isolated Display Driver Components

### Files in the Kernel Source Needed for Display

All from `rockchip-linux/kernel` branch `develop-6.1`:

**Core DRM framework:**

| Source file | Config | Purpose |
|---|---|---|
| `drivers/gpu/drm/rockchip/rockchip_drm_drv.c` | `CONFIG_DRM_ROCKCHIP` | Main Rockchip DRM driver |
| `drivers/gpu/drm/rockchip/rockchip_drm_fb.c` | `CONFIG_DRM_ROCKCHIP` | Framebuffer management |
| `drivers/gpu/drm/rockchip/rockchip_drm_gem.c` | `CONFIG_DRM_ROCKCHIP` | GEM buffer objects |
| `drivers/gpu/drm/rockchip/rockchip_vop.c` | `CONFIG_ROCKCHIP_VOP` | Video Output Processor |
| `drivers/gpu/drm/rockchip/rockchip_vop_reg.c` | `CONFIG_ROCKCHIP_VOP` | VOP register definitions |

**Output interfaces:**

| Source file | Config | Used by S1? | Used by T1? |
|---|---|---|---|
| `drivers/gpu/drm/rockchip/rockchip_rgb.c` | `CONFIG_ROCKCHIP_RGB` | **Yes** (active) | **Yes** (active) |
| `drivers/gpu/drm/rockchip/dw-mipi-dsi-rockchip.c` | `CONFIG_ROCKCHIP_DW_MIPI_DSI` | No (disabled in DTB) | No (disabled in DTB) |
| `drivers/gpu/drm/rockchip/dw-mipi-dsi2-rockchip.c` | `CONFIG_ROCKCHIP_DW_MIPI_DSI2` | No (disabled in DTB) | No (disabled in DTB) |
| `drivers/gpu/drm/rockchip/rockchip_lvds.c` | `CONFIG_ROCKCHIP_LVDS` | No | No |

**Panel drivers:**

| Source file | Config | Purpose |
|---|---|---|
| `drivers/gpu/drm/panel/panel-simple.c` | `CONFIG_DRM_PANEL_SIMPLE` | Generic panel (timings from DTB) |
| `drivers/gpu/drm/panel/panel-*.c` | Various | IC-specific panel drivers |

**Backlight:**

| Source file | Config | Purpose |
|---|---|---|
| `drivers/video/backlight/pwm_bl.c` | `CONFIG_BACKLIGHT_PWM` | PWM backlight driver |
| `drivers/video/backlight/gpio_backlight.c` | `CONFIG_BACKLIGHT_GPIO` | GPIO backlight (fallback) |

### Kernel Config Extraction (Display-Related Only)

These are the exact display-related kernel config options from the S1 kernel (extracted from `kernel-config.txt`):

```kconfig
# === DRM Core ===
CONFIG_DRM=y
CONFIG_DRM_EDID=y
CONFIG_DRM_MIPI_DSI=y
CONFIG_DRM_KMS_HELPER=y
CONFIG_DRM_FBDEV_EMULATION=y
CONFIG_DRM_FBDEV_OVERALLOC=100
CONFIG_DRM_LOAD_EDID_FIRMWARE=y
CONFIG_DRM_DP=y
CONFIG_DRM_GEM_DMA_HELPER=y
CONFIG_DRM_GEM_SHMEM_HELPER=y
CONFIG_DRM_SIMPLEDRM=y

# === Rockchip DRM ===
CONFIG_DRM_ROCKCHIP=y
CONFIG_ROCKCHIP_DRM_DIRECT_SHOW=y
CONFIG_ROCKCHIP_VOP=y
CONFIG_ROCKCHIP_DW_MIPI_DSI=y
CONFIG_ROCKCHIP_DW_MIPI_DSI2=y
CONFIG_ROCKCHIP_LVDS=y
CONFIG_ROCKCHIP_RGB=y
CONFIG_ROCKCHIP_RGA=y
CONFIG_ROCKCHIP_RGA2=y

# === Panel ===
CONFIG_DRM_PANEL=y
CONFIG_DRM_PANEL_SIMPLE=y

# === Framebuffer ===
CONFIG_FB=y
CONFIG_FB_CMDLINE=y
CONFIG_FB_NOTIFY=y
CONFIG_FB_CFB_FILLRECT=y
CONFIG_FB_CFB_COPYAREA=y
CONFIG_FB_CFB_IMAGEBLIT=y
CONFIG_FB_SYS_FILLRECT=y
CONFIG_FB_SYS_COPYAREA=y
CONFIG_FB_SYS_IMAGEBLIT=y
CONFIG_FB_SYS_FOPS=y
CONFIG_FB_DEFERRED_IO=y

# === Backlight ===
CONFIG_BACKLIGHT_CLASS_DEVICE=y
CONFIG_BACKLIGHT_PWM=y
CONFIG_BACKLIGHT_GPIO=y

# === Logo ===
CONFIG_LOGO=y
CONFIG_LOGO_LINUX_CLUT224=y
```

### DTB Extraction (Display-Related Only)

Isolated device tree nodes for the display pipeline (S1):

```dts
/* === Backlight === */
backlight {
    compatible = "pwm-backlight";
    pwms = <&pwm0 0 25000 0>;
    brightness-levels = <0 1 2 ... 255>;
    default-brightness-level = <100>;
};

/* === Panel === */
panel@0 {
    compatible = "simple-panel";
    bus-format = <0x100e>;       /* RGB888 */
    rgb-mode = "p888";
    width-mm = <150>;
    height-mm = <94>;
    backlight = <&backlight>;
    status = "okay";

    display-timings {
        native-mode = <&timing0>;
        timing0 {
            clock-frequency = <51200000>;
            hactive = <1024>;
            vactive = <600>;
            hback-porch = <160>;
            hfront-porch = <160>;
            vback-porch = <23>;
            vfront-porch = <12>;
            hsync-len = <20>;
            vsync-len = <3>;
            de-active = <1>;
        };
    };

    port {
        panel_in_rgb: endpoint {
            remote-endpoint = <&rgb_out_panel>;
        };
    };
};

/* === Display Subsystem === */
display-subsystem {
    compatible = "rockchip,display-subsystem";
    ports = <&vop_out>;
    status = "okay";

    route {
        route-dsi { status = "disabled"; };
        route-rgb { status = "okay"; };
    };
};

/* === VOP === */
vop@ffb00000 {
    compatible = "rockchip,rv1126-vop";
    /* ... registers, clocks, power-domains ... */
    status = "okay";

    vop_out: port {
        vop_out_rgb: endpoint@0 {
            remote-endpoint = <&rgb_in_vop>;
        };
        vop_out_dsi: endpoint@1 {
            remote-endpoint = <&dsi_in_vop>;
        };
    };
};

/* === RGB Interface (in GRF syscon) === */
grf: syscon@fe000000 {
    rgb {
        compatible = "rockchip,rv1126-rgb";
        status = "okay";

        ports {
            port@0 {
                rgb_in_vop: endpoint@0 {
                    remote-endpoint = <&vop_out_rgb>;
                };
            };
            port@1 {
                rgb_out_panel: endpoint@0 {
                    remote-endpoint = <&panel_in_rgb>;
                };
            };
        };
    };
};

/* === DSI (disabled on S1) === */
dsi@ffb30000 {
    compatible = "rockchip,rv1126-mipi-dsi";
    status = "disabled";
    /* If T1 uses DSI, this would be "okay" and panel would connect here */
};
```

---

## 7. Adapting for T1 — What to Change

> **Resolved:** The T1 uses **RGB parallel** (confirmed from stock firmware DTB extraction). Only the DTB needs changes — no kernel config changes are required for the display.

### DTB Changes Required

The kernel binary (zImage) can be **identical** to the S1 build. Only the device tree blob (DTB) differs:

1. Use `rv1126` compatible strings (Rockchip uses the same platform ID for RV1109 and RV1126)
2. Copy the T1 `panel@0` node with 800×480 timings (see Section 5 above)
3. Set `width-mm = <95>`, `height-mm = <54>` for the T1 panel
4. Add `enable-gpios = <&gpio3 28 GPIO_ACTIVE_LOW>` and `enable-delay-ms = <20>`
5. Set `bus-format = <0x1013>` (RGB888_1X24 — different from S1's 0x100E RGB666)
6. Keep `route-rgb` active, `route-dsi` disabled
7. Backlight uses the same PWM0 channel as S1 — no change needed

### Kernel Config

No display-related kernel config changes are needed. The S1 config already has:
- `CONFIG_DRM_PANEL_SIMPLE=y` (same driver used by T1)
- `CONFIG_ROCKCHIP_RGB=y` (same interface)
- `CONFIG_ROCKCHIP_VOP=y` (same VOP hardware)
- `CONFIG_BACKLIGHT_PWM=y` (same backlight method)

### galcore.ko (NPU) — Not Display Related

The only loadable kernel module on the rootfs is `galcore.ko` at `/lib/modules/galcore.ko`. This is the **Vivante GPU/NPU driver** used for AI inference, NOT for display output. It is loaded at boot by `/etc/init.d/S60NPU_init`:

```bash
insmod /lib/modules/galcore.ko contiguousSize=0x400000
```

This module can be omitted entirely for a T1 build if NPU features are not needed.

---

## 8. Summary — Action Items for T1 Kernel Build

| Step | Action | Difficulty | Status |
|---|---|---|---|
| 1 | Clone `rockchip-linux/kernel` branch `develop-6.1` | Easy | Ready |
| 2 | Use `rv1126_defconfig` as base config | Easy | Ready |
| 3 | Get RV1109 rkbin files (DDR, SPL, TEE) | Easy | Ready |
| 4 | Extract T1 stock DTB from eMMC boot partition | Medium | **Done** — see [04-stock-firmware-analysis.md](04-stock-firmware-analysis.md) |
| 5 | Identify T1 display interface (RGB vs DSI) | Easy | **Done** — RGB parallel, 800×480 |
| 6 | Create T1 device tree with correct panel timings | Medium | **Ready** — timings extracted (see Section 5) |
| 7 | Build kernel + DTB → boot.img | Easy | Ready |
| 8 | Build rootfs (debos or manual debootstrap) | Medium | Not started |
| 9 | Flash via RKDevTool (USB-C) | Easy | Not started |

**No remaining blockers for the display.** The T1 stock DTB has been extracted and fully decompiled (4326 lines, 484 nodes). The display is confirmed as RGB parallel `simple-panel` at 800×480.

---

## Resolved Questions

1. ~~**T1 stock DTB:**~~ **Extracted and decompiled.** See `resources/T1/firmwares/stock/extracted/fdt.dts` (4326 lines). Model: `RV1126 EVB DDR3 V13 Board flsun-800p`.
2. ~~**T1 kernel version:**~~ **Linux 4.19.111** (Rockchip BSP 4.19, Linaro GCC 6.3.1, build #22, Sep 2024).
3. ~~**T1 display interface:**~~ **RGB parallel** (same as S1). MIPI DSI is disabled in DTB. The "vertical lines" are caused by wrong resolution/timings, not interface mismatch.
4. ~~**T1 panel IC:**~~ **No IC initialization needed** — uses `simple-panel` driver (timings-only, same as S1).
5. ~~**RV1109 DTB compatibility:**~~ **Confirmed.** The T1 stock firmware uses `rv1126-vop`, `rv1126-rgb`, `rv1126-mipi-dsi` compatible strings on an RV1109 chip. Rockchip uses `rv1126` as the shared platform ID.

## Open Questions

1. **SoC physical chip:** The PCB has an **RV1109** (dual-core A7, 1.2 TOPS NPU), but the DTB uses `rv1126` compatible strings. Does the stock RV1109 actually boot with only 2 cores enabled, or does FLSUN use an RV1126 die with RV1109 branding? (`cat /proc/cpuinfo` on a running T1 would confirm.)
2. **Boot format compatibility:** Can the T1 U-Boot load Android boot images (mkbootimg), or is it hardcoded for FIT? Determines whether the S1 build system can be reused as-is.
3. **Full rootfs analysis:** What exact versions of Klipper/Moonraker/Mainsail are installed? What services/scripts manage the printer stack?
