#!/usr/bin/env python3
"""
Build an Android boot.img for the FLSUN T1 from S1 components.

Takes the S1 FLSUN-OS 3.0 zImage kernel and a T1-patched DTB,
and packages them into an Android boot.img (mkbootimg format)
that can be flashed to the T1's eMMC boot partition.

This replicates the S1 boot.img format:
  - Kernel: zImage (S1's Linux 6.1.99flsun)
  - Ramdisk: empty (no initramfs)
  - Second stage: RSCE resource container with DTB
  - Page size: 2048

Usage:
    python build-boot-img-t1.py                          # use defaults
    python build-boot-img-t1.py <zImage> <dtb> <output>  # explicit paths

Requirements: Python 3.6+ (no external dependencies)
"""

import struct
import os
import sys
import hashlib


def align_to(data, alignment):
    """Pad data to alignment boundary with zeros."""
    remainder = len(data) % alignment
    if remainder:
        data += b'\x00' * (alignment - remainder)
    return data


def build_rsce(dtb_data):
    """Build a minimal RSCE (Rockchip Resource Container) with a single DTB entry.

    RSCE format:
    - 512-byte header
    - 512-byte entry table (per entry)
    - Data block (DTB file)

    Header (512 bytes):
    - [0:4]   magic: b'RSCE'
    - [4:6]   version: 0x0000
    - [6:8]   entry_count: 1
    - [8:12]  block_size: 512

    Entry (512 bytes, at offset 512):
    - [0:4]   tag: b'ENTR'
    - [4:260] filename: 'rk-kernel.dtb' (null-padded)
    - [260:264] data_offset: in blocks (block = 512 bytes)
    - [264:268] data_size: in bytes
    """
    entry_count = 1
    # Data starts at: header (1 block) + entries (1 block per entry) = 2 blocks = 1024 bytes
    data_offset_blocks = 1 + entry_count  # blocks, not bytes

    # Build header (512 bytes)
    header = bytearray(512)
    header[0:4] = b'RSCE'
    struct.pack_into('<H', header, 4, 0)  # version
    struct.pack_into('<H', header, 6, entry_count)
    struct.pack_into('<I', header, 8, 512)  # block size

    # Build entry table (512 bytes per entry)
    entry = bytearray(512)
    entry[0:4] = b'ENTR'
    filename = b'rk-kernel.dtb'
    entry[4:4 + len(filename)] = filename
    struct.pack_into('<I', entry, 260, data_offset_blocks)
    struct.pack_into('<I', entry, 264, len(dtb_data))

    # Assemble: header + entries + data
    rsce = bytes(header) + bytes(entry) + dtb_data

    return rsce


def build_android_boot_img(kernel_data, rsce_data, page_size=2048):
    """Build an Android boot image.

    Format (all fields little-endian unless noted):
    Page 0: Header (2048 bytes for page_size=2048)
      [0:8]     magic: b'ANDROID!'
      [8:12]    kernel_size
      [12:16]   kernel_addr (0x62008000 — standard Rockchip)
      [16:20]   ramdisk_size (0 — no initramfs)
      [20:24]   ramdisk_addr (0x62000000)
      [24:28]   second_size (RSCE size)
      [28:32]   second_addr (0x62000000)
      [32:36]   tags_addr (0x00000100)
      [36:40]   page_size
      [40:44]   header_version (0)
      [44:48]   os_version (0)
      [48:64]   name (null-padded, max 16 bytes)
      [64:576]  cmdline (null-padded, max 512 bytes)
      [576:608] id (SHA1 digest of kernel + ramdisk + second, padded to 32 bytes)
      [608:1024] extra_cmdline (null-padded)

    After header: kernel pages, ramdisk pages (empty), second pages (RSCE)
    """

    # Standard Rockchip RV1126 addresses (from S1 boot.img)
    kernel_addr = 0x62008000
    ramdisk_addr = 0x62000000
    second_addr = 0x62000000
    tags_addr = 0x00000100

    kernel_size = len(kernel_data)
    ramdisk_size = 0
    second_size = len(rsce_data)

    cmdline = b'earlycon=uart8250,mmio32,0xff570000 console=ttyFIQ0 root=PARTUUID=614e0000-0000 rootfstype=ext4 rootwait snd_aloop.index=7'
    name = b''

    # Compute ID (SHA1 of kernel + ramdisk + second)
    sha = hashlib.sha1()
    sha.update(kernel_data)
    sha.update(struct.pack('<I', kernel_size))
    # ramdisk is empty
    sha.update(struct.pack('<I', ramdisk_size))
    sha.update(rsce_data)
    sha.update(struct.pack('<I', second_size))
    id_bytes = sha.digest()  # 20 bytes
    id_padded = id_bytes + b'\x00' * 12  # pad to 32 bytes

    # Build header
    header = bytearray(page_size)
    header[0:8] = b'ANDROID!'
    struct.pack_into('<I', header, 8, kernel_size)
    struct.pack_into('<I', header, 12, kernel_addr)
    struct.pack_into('<I', header, 16, ramdisk_size)
    struct.pack_into('<I', header, 20, ramdisk_addr)
    struct.pack_into('<I', header, 24, second_size)
    struct.pack_into('<I', header, 28, second_addr)
    struct.pack_into('<I', header, 32, tags_addr)
    struct.pack_into('<I', header, 36, page_size)
    struct.pack_into('<I', header, 40, 0)  # header version
    struct.pack_into('<I', header, 44, 0)  # os version

    # Name (16 bytes max)
    name_bytes = name[:16]
    header[48:48 + len(name_bytes)] = name_bytes

    # Cmdline (512 bytes max)
    cmdline_bytes = cmdline[:512]
    header[64:64 + len(cmdline_bytes)] = cmdline_bytes

    # ID (32 bytes)
    header[576:576 + 32] = id_padded

    # Assemble image
    img = bytes(header)
    img += align_to(kernel_data, page_size)
    # ramdisk is empty (size=0), skip
    img += align_to(rsce_data, page_size)

    return img


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    workspace = os.path.dirname(os.path.dirname(script_dir))

    default_zimage = os.path.join(
        workspace, 'resources', 'S1', 'firmwares', 'os-images',
        'FLSUN-OS-S1-EMMC-3.0', 'extracted', 'zImage'
    )
    default_dtb = os.path.join(
        workspace, 'resources', 'T1', 'firmwares', 'os-images',
        'rk-kernel-t1.dtb'
    )
    default_output = os.path.join(
        workspace, 'resources', 'T1', 'firmwares', 'os-images',
        'boot.img'
    )

    if len(sys.argv) >= 4:
        zimage_path = sys.argv[1]
        dtb_path = sys.argv[2]
        output_path = sys.argv[3]
    elif len(sys.argv) >= 3:
        zimage_path = sys.argv[1]
        dtb_path = sys.argv[2]
        output_path = default_output
    else:
        zimage_path = default_zimage
        dtb_path = default_dtb
        output_path = default_output

    # Validate inputs
    for path, label in [(zimage_path, 'zImage'), (dtb_path, 'DTB')]:
        if not os.path.exists(path):
            print(f"ERROR: {label} not found: {path}")
            if path == default_zimage:
                print(f"\n  Run patch-dtb-for-t1.py first to generate the T1 DTB.")
            sys.exit(1)

    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    print("=== FLSUN T1 boot.img Builder ===\n")
    print(f"Kernel:  {zimage_path} ({os.path.getsize(zimage_path):,} bytes)")
    print(f"DTB:     {dtb_path} ({os.path.getsize(dtb_path):,} bytes)")
    print(f"Output:  {output_path}")
    print()

    # Read inputs
    with open(zimage_path, 'rb') as f:
        kernel_data = f.read()

    with open(dtb_path, 'rb') as f:
        dtb_data = f.read()

    # Validate zImage
    if len(kernel_data) > 40:
        zimage_magic = struct.unpack_from('<I', kernel_data, 36)[0]
        if zimage_magic == 0x016F2818:
            print(f"✓ Valid ARM zImage ({len(kernel_data):,} bytes)")
        else:
            print(f"WARNING: zImage magic mismatch at offset 36: 0x{zimage_magic:08X}")
            print(f"  Expected 0x016F2818. Continuing anyway...")

    # Validate DTB
    dtb_magic = struct.unpack_from('>I', dtb_data, 0)[0]
    if dtb_magic == 0xD00DFEED:
        print(f"✓ Valid FDT/DTB ({len(dtb_data):,} bytes)")
    else:
        print(f"ERROR: DTB magic mismatch: 0x{dtb_magic:08X} (expected 0xD00DFEED)")
        sys.exit(1)

    # Build RSCE container
    print(f"\nBuilding RSCE resource container...")
    rsce = build_rsce(dtb_data)
    print(f"  RSCE size: {len(rsce):,} bytes (header=512 + entry=512 + DTB={len(dtb_data):,})")

    # Build Android boot image
    print(f"Building Android boot.img...")
    boot_img = build_android_boot_img(kernel_data, rsce)
    print(f"  boot.img size: {len(boot_img):,} bytes ({len(boot_img) / 1024 / 1024:.2f} MB)")

    # Write output
    with open(output_path, 'wb') as f:
        f.write(boot_img)

    print(f"\n✓ boot.img written to: {output_path}")
    print(f"  Format: Android mkbootimg (ANDROID! magic)")
    print(f"  Kernel: Linux 6.1.99flsun (S1 kernel, compatible with RV1109)")
    print(f"  DTB: T1-patched (800×480 @ 25 MHz)")
    print(f"  Cmdline: root=PARTUUID=614e0000-0000 rootfstype=ext4 rootwait")
    print(f"\nFlash with RKDevTool to boot partition (offset varies by partition table)")


if __name__ == '__main__':
    main()
