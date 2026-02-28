#!/usr/bin/env python3
"""
Patch FLSUN S1 DTB for T1 hardware.

Takes the S1 FLSUN-OS 3.0 kernel DTB (rk-kernel.dtb) and patches the
display panel node from 1024×600 @ 51.2 MHz to 800×480 @ 25 MHz,
plus compatible/model strings and panel physical dimensions.

The S1 kernel (6.1.99flsun) boots on the T1 because RV1126 and RV1109
share the same platform. Only the DTB needs modification for the display.

Usage:
    python patch-dtb-for-t1.py <input.dtb> <output.dtb>
    python patch-dtb-for-t1.py  # uses default paths

Requirements: Python 3.6+ (no external dependencies)
"""

import struct
import sys
import os
import copy

# ── FDT Constants ──
FDT_MAGIC = 0xD00DFEED
FDT_BEGIN_NODE = 0x00000001
FDT_END_NODE = 0x00000002
FDT_PROP = 0x00000003
FDT_NOP = 0x00000004
FDT_END = 0x00000009


def read_u32(data, offset):
    return struct.unpack_from('>I', data, offset)[0]


def write_u32(data, offset, value):
    struct.pack_into('>I', data, offset, value)


def parse_fdt_header(data):
    magic = read_u32(data, 0)
    if magic != FDT_MAGIC:
        raise ValueError(f"Not a valid DTB: magic=0x{magic:08X}, expected 0x{FDT_MAGIC:08X}")
    return {
        'totalsize': read_u32(data, 4),
        'off_dt_struct': read_u32(data, 8),
        'off_dt_strings': read_u32(data, 12),
        'off_mem_rsvmap': read_u32(data, 16),
        'version': read_u32(data, 20),
        'last_comp_version': read_u32(data, 24),
        'boot_cpuid_phys': read_u32(data, 28),
        'size_dt_strings': read_u32(data, 32),
        'size_dt_struct': read_u32(data, 36),
    }


def get_string(data, strings_base, str_offset):
    start = strings_base + str_offset
    end = data.find(b'\x00', start)
    return data[start:end].decode('ascii', errors='replace')


class DTBPatcher:
    """Parse and patch a Flattened Device Tree blob in-place."""

    def __init__(self, data):
        self.data = bytearray(data)
        self.header = parse_fdt_header(self.data)
        self.struct_start = self.header['off_dt_struct']
        self.strings_start = self.header['off_dt_strings']
        self.patches_applied = []

    def _find_properties(self, node_path_filter, prop_name_filter=None):
        """Walk the FDT struct and yield (offset, name, prop_name, prop_data_offset, prop_len)
        for all properties matching filters.

        node_path_filter: function(path_string) -> bool
        prop_name_filter: function(prop_name) -> bool (optional)
        """
        off = self.struct_start
        end = off + self.header['size_dt_struct']
        path = []

        while off < end:
            token = read_u32(self.data, off)
            off += 4

            if token == FDT_BEGIN_NODE:
                name_end = self.data.find(b'\x00', off)
                name = self.data[off:name_end].decode('ascii', errors='replace')
                off = (name_end + 4) & ~3
                path.append(name)

            elif token == FDT_END_NODE:
                if path:
                    path.pop()

            elif token == FDT_PROP:
                prop_len = read_u32(self.data, off)
                prop_nameoff = read_u32(self.data, off + 4)
                prop_data_off = off + 8
                prop_name = get_string(self.data, self.strings_start, prop_nameoff)

                current_path = '/'.join(path)
                if node_path_filter(current_path):
                    if prop_name_filter is None or prop_name_filter(prop_name):
                        yield {
                            'path': current_path,
                            'prop_name': prop_name,
                            'data_offset': prop_data_off,
                            'data_len': prop_len,
                            'header_offset': off,  # points to len field
                        }

                off = (prop_data_off + prop_len + 3) & ~3

            elif token == FDT_NOP:
                pass
            elif token == FDT_END:
                break

    def patch_u32_property(self, node_path, prop_name, new_value, description=""):
        """Patch a single 4-byte integer property."""
        for prop in self._find_properties(
            lambda p: p == node_path or p.endswith('/' + node_path),
            lambda n: n == prop_name
        ):
            if prop['data_len'] != 4:
                print(f"  WARNING: {prop['path']}/{prop_name} is {prop['data_len']} bytes, expected 4")
                continue
            old_value = read_u32(self.data, prop['data_offset'])
            write_u32(self.data, prop['data_offset'], new_value)
            desc = f" ({description})" if description else ""
            self.patches_applied.append(
                f"{prop['path']}/{prop_name}: 0x{old_value:08X} -> 0x{new_value:08X}{desc}"
            )
            return True
        print(f"  WARNING: Property {node_path}/{prop_name} not found")
        return False

    def patch_string_property(self, node_path, prop_name, new_string):
        """Patch a null-terminated string property.

        WARNING: The new string must be <= the old string in length (including null).
        We pad with nulls if shorter. We cannot grow properties without rewriting the DTB.
        """
        for prop in self._find_properties(
            lambda p: p == node_path or p.endswith('/' + node_path),
            lambda n: n == prop_name
        ):
            old_data = self.data[prop['data_offset']:prop['data_offset'] + prop['data_len']]
            old_str = old_data.split(b'\x00')[0].decode('ascii', errors='replace')

            new_bytes = new_string.encode('ascii') + b'\x00'
            if len(new_bytes) > prop['data_len']:
                print(f"  WARNING: New string '{new_string}' ({len(new_bytes)} bytes) "
                      f"exceeds property space ({prop['data_len']} bytes). Truncating.")
                new_bytes = new_bytes[:prop['data_len'] - 1] + b'\x00'

            # Pad with zeros to fill original property length
            padded = new_bytes + b'\x00' * (prop['data_len'] - len(new_bytes))
            self.data[prop['data_offset']:prop['data_offset'] + prop['data_len']] = padded

            self.patches_applied.append(
                f"{prop['path']}/{prop_name}: \"{old_str}\" -> \"{new_string}\""
            )
            return True
        print(f"  WARNING: String property {node_path}/{prop_name} not found")
        return False

    def patch_compatible_property(self, node_path, new_compatibles):
        """Patch a compatible property (null-separated list of strings).

        new_compatibles: list of strings
        """
        for prop in self._find_properties(
            lambda p: p == node_path or (node_path == '' and p == ''),
            lambda n: n == 'compatible'
        ):
            old_data = self.data[prop['data_offset']:prop['data_offset'] + prop['data_len']]
            old_strs = [s.decode('ascii', errors='replace') for s in old_data.split(b'\x00') if s]

            new_bytes = b'\x00'.join(s.encode('ascii') for s in new_compatibles) + b'\x00'
            if len(new_bytes) > prop['data_len']:
                print(f"  WARNING: New compatible list ({len(new_bytes)} bytes) exceeds "
                      f"property space ({prop['data_len']} bytes). Cannot patch.")
                return False

            padded = new_bytes + b'\x00' * (prop['data_len'] - len(new_bytes))
            self.data[prop['data_offset']:prop['data_offset'] + prop['data_len']] = padded

            self.patches_applied.append(
                f"{node_path or '/'}/compatible: {old_strs} -> {new_compatibles}"
            )
            return True
        print(f"  WARNING: compatible property not found at '{node_path}'")
        return False

    def get_bytes(self):
        return bytes(self.data)


def apply_t1_patches(patcher):
    """Apply all T1-specific patches to an S1 DTB."""

    print("=== Patching S1 DTB for FLSUN T1 ===\n")

    # ── 1. Root node: model and compatible ──
    print("[1/4] Root node identity...")
    patcher.patch_string_property(
        '', 'model',
        'Rockchip RV1126 EVB DDR3 V13 FLSUN-T1'
    )
    patcher.patch_compatible_property('', [
        'rockchip,rv1126-evb-ddr3-v13-flsun-800p',
        'rockchip,flsun-800p',
    ])

    # ── 2. Panel node: bus-format, physical size ──
    print("[2/4] Panel physical properties...")
    # bus-format: 0x100e (RGB666_1X18) -> 0x1013 (RGB888_1X24)
    patcher.patch_u32_property('panel@0', 'bus-format', 0x00001013, 'RGB888_1X24')
    # width-mm: 150 -> 95
    patcher.patch_u32_property('panel@0', 'width-mm', 0x0000005F, '95mm')
    # height-mm: 94 -> 54
    patcher.patch_u32_property('panel@0', 'height-mm', 0x00000036, '54mm')

    # Note: We cannot add enable-gpios or enable-delay-ms to the S1 DTB
    # without rewriting the struct block (properties don't exist in S1).
    # The display should still work — enable-gpios is optional for simple-panel.

    # ── 3. Display timing: 1024×600 @ 51.2 MHz → 800×480 @ 25 MHz ──
    print("[3/4] Display timings (1024×600 → 800×480)...")
    timing_node = 'panel@0/display-timings/timing0'

    patches = [
        # (property, new_value_hex, description)
        ('clock-frequency', 0x017D7840, '25 MHz'),
        ('hactive',         0x00000320, '800'),
        ('vactive',         0x000001E0, '480'),
        ('hback-porch',     0x00000008, '8'),
        ('hfront-porch',    0x00000008, '8'),
        ('vback-porch',     0x00000008, '8'),
        ('vfront-porch',    0x00000008, '8'),
        ('hsync-len',       0x00000004, '4'),
        ('vsync-len',       0x00000004, '4'),
        ('hsync-active',    0x00000001, '1 (active high)'),
        ('vsync-active',    0x00000001, '1 (active high)'),
        ('pixelclk-active', 0x00000001, '1 (active high)'),
        # de-active stays 0x01 (same on both)
    ]

    for prop_name, new_val, desc in patches:
        patcher.patch_u32_property(timing_node, prop_name, new_val, desc)

    # ── 4. Chosen bootargs — same PARTUUID, no change needed ──
    print("[4/4] Bootargs (no change needed — same PARTUUID scheme)...")
    # The bootargs use PARTUUID which works regardless of partition table changes

    print(f"\n=== {len(patcher.patches_applied)} patches applied ===\n")
    for p in patcher.patches_applied:
        print(f"  ✓ {p}")


def main():
    # Default paths relative to workspace
    script_dir = os.path.dirname(os.path.abspath(__file__))
    workspace = os.path.dirname(os.path.dirname(script_dir))

    default_input = os.path.join(
        workspace, 'resources', 'S1', 'firmwares', 'os-images',
        'FLSUN-OS-S1-EMMC-3.0', 'extracted', 'rk-kernel.dtb'
    )
    default_output = os.path.join(
        workspace, 'resources', 'T1', 'firmwares', 'os-images',
        'rk-kernel-t1.dtb'
    )

    if len(sys.argv) >= 3:
        input_dtb = sys.argv[1]
        output_dtb = sys.argv[2]
    elif len(sys.argv) == 2:
        input_dtb = sys.argv[1]
        output_dtb = default_output
    else:
        input_dtb = default_input
        output_dtb = default_output

    if not os.path.exists(input_dtb):
        print(f"ERROR: Input DTB not found: {input_dtb}")
        print(f"\nExpected: S1 FLSUN-OS 3.0 rk-kernel.dtb at:")
        print(f"  {default_input}")
        sys.exit(1)

    # Create output directory if needed
    os.makedirs(os.path.dirname(output_dtb), exist_ok=True)

    print(f"Input:  {input_dtb}")
    print(f"Output: {output_dtb}")
    print(f"Size:   {os.path.getsize(input_dtb)} bytes")
    print()

    with open(input_dtb, 'rb') as f:
        dtb_data = f.read()

    patcher = DTBPatcher(dtb_data)
    apply_t1_patches(patcher)

    patched_data = patcher.get_bytes()

    with open(output_dtb, 'wb') as f:
        f.write(patched_data)

    print(f"\nPatched DTB written to: {output_dtb}")
    print(f"Size: {len(patched_data)} bytes")

    # Verify the output is still valid
    verify_header = parse_fdt_header(patched_data)
    print(f"Valid FDT: magic=0x{FDT_MAGIC:08X}, size={verify_header['totalsize']}")


if __name__ == '__main__':
    main()
