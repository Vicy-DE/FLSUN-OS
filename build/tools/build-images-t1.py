#!/usr/bin/env python3
"""
FLSUN-OS T1 Image Builder — Master Build Tool
═══════════════════════════════════════════════

Produces three firmware images for the FLSUN T1:

  1. flsun-os-t1-kernel.img   — Boot partition image (Android boot format)
                                 Contains: Linux 6.1.99flsun zImage + T1 DTB (800×480)

  2. flsun-os-t1-rootfs.img   — Root filesystem (ext4 partition image)
                                 Built from S1 FLSUN-OS 3.0 rootfs, modified for T1
                                 NOTE: Requires Linux (ext4 mount) — see build-rootfs-t1.sh

  3. flsun-os-t1-complete.img — Complete eMMC disk image (GPT, all partitions)
                                 Can be flashed as a single image via RKDevTool

The kernel image can be built on any platform (Windows/Mac/Linux) using Python.
The rootfs and complete images require Linux (or WSL) for ext4 manipulation.

Usage:
    python build-images-t1.py                # Build kernel image (platform-independent)
    python build-images-t1.py --kernel       # Build only kernel image
    python build-images-t1.py --rootfs       # Build only rootfs image (Linux only)
    python build-images-t1.py --complete     # Build only complete eMMC image (Linux only)
    python build-images-t1.py --all          # Build all three images (Linux only)

Requirements:
    Python 3.6+ (no external dependencies for kernel image)
    Linux/WSL + root access (for rootfs and complete images)
    S1 FLSUN-OS 3.0 source images in resources/S1/firmwares/os-images/

See also:
    build-boot-img-t1.py     — Standalone boot image builder (same kernel logic)
    build-boot-img-t1.sh     — Shell-based boot image builder (Android + FIT)
    mod-rootfs-for-t1.sh     — S1→T1 rootfs converter (full modification)
    build-rootfs-t1.sh       — Rootfs image builder script (Linux wrapper)
    build-t1.sh              — Full debos build from scratch (no S1 base required)
"""

import struct
import os
import sys
import hashlib
import shutil
import subprocess
import platform
import tempfile
import json
from datetime import datetime, timezone
from pathlib import Path


# ─── Path Configuration ──────────────────────────────────────────────

SCRIPT_DIR = Path(__file__).parent.resolve()
REPO_ROOT = SCRIPT_DIR.parent.parent
BUILD_DIR = SCRIPT_DIR.parent
OUTPUT_DIR = BUILD_DIR / "output"

# Source images (S1 FLSUN-OS 3.0)
S1_IMAGES = REPO_ROOT / "resources" / "S1" / "firmwares" / "os-images" / "FLSUN-OS-S1-EMMC-3.0"
S1_ZIMAGE = S1_IMAGES / "extracted" / "zImage"
S1_ROOTFS = S1_IMAGES / "rootfs.img"

# T1-specific files
T1_DTB = REPO_ROOT / "resources" / "T1" / "firmwares" / "os-images" / "rk-kernel-t1.dtb"
T1_CONFIGS = REPO_ROOT / "resources" / "T1" / "klipper-configs" / "ported"
T1_OVERLAYS = BUILD_DIR / "overlays-t1"
MOD_ROOTFS_SCRIPT = SCRIPT_DIR / "mod-rootfs-for-t1.sh"

# Output names
KERNEL_IMG_NAME = "flsun-os-t1-kernel.img"
ROOTFS_IMG_NAME = "flsun-os-t1-rootfs.img"
COMPLETE_IMG_NAME = "flsun-os-t1-complete.img"

# T1 eMMC partition layout (sector size = 512 bytes)
# Derived from stock T1 GPT partition table analysis
# Offsets in 512-byte sectors
PARTITION_LAYOUT = {
    "uboot":    {"start": 0x00004000, "size_mb": 4},
    "misc":     {"start": 0x00006000, "size_mb": 4},
    "boot":     {"start": 0x00008000, "size_mb": 32},
    "recovery": {"start": 0x00018000, "size_mb": 32},
    "backup":   {"start": 0x00028000, "size_mb": 32},
    "rootfs":   {"start": 0x00038000, "size_mb": 7340},  # ~7.17 GB — fills rest of 8GB eMMC
}

VERSION = "1.0"
BUILD_DATE = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


# ─── Android Boot Image Builder ──────────────────────────────────────

def align_to(data: bytes, alignment: int) -> bytes:
    """Pad data to alignment boundary with zeros."""
    remainder = len(data) % alignment
    if remainder:
        data += b'\x00' * (alignment - remainder)
    return data


def build_rsce(dtb_data: bytes) -> bytes:
    """Build a minimal RSCE (Rockchip Resource Container) with a single DTB entry."""
    entry_count = 1
    data_offset_blocks = 1 + entry_count

    header = bytearray(512)
    header[0:4] = b'RSCE'
    struct.pack_into('<H', header, 4, 0)
    struct.pack_into('<H', header, 6, entry_count)
    struct.pack_into('<I', header, 8, 512)

    entry = bytearray(512)
    entry[0:4] = b'ENTR'
    filename = b'rk-kernel.dtb'
    entry[4:4 + len(filename)] = filename
    struct.pack_into('<I', entry, 260, data_offset_blocks)
    struct.pack_into('<I', entry, 264, len(dtb_data))

    return bytes(header) + bytes(entry) + dtb_data


def build_android_boot_img(kernel_data: bytes, rsce_data: bytes, page_size: int = 2048) -> bytes:
    """Build an Android boot image (mkbootimg format) for the T1."""

    kernel_addr = 0x62008000
    ramdisk_addr = 0x62000000
    second_addr = 0x62000000
    tags_addr = 0x00000100

    kernel_size = len(kernel_data)
    ramdisk_size = 0
    second_size = len(rsce_data)

    cmdline = b'earlycon=uart8250,mmio32,0xff570000 console=ttyFIQ0 root=PARTUUID=614e0000-0000 rootfstype=ext4 rootwait snd_aloop.index=7'

    # Compute ID
    sha = hashlib.sha1()
    sha.update(kernel_data)
    sha.update(struct.pack('<I', kernel_size))
    sha.update(struct.pack('<I', ramdisk_size))
    sha.update(rsce_data)
    sha.update(struct.pack('<I', second_size))
    id_padded = sha.digest() + b'\x00' * 12

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
    struct.pack_into('<I', header, 40, 0)
    struct.pack_into('<I', header, 44, 0)
    header[64:64 + len(cmdline)] = cmdline[:512]
    header[576:576 + 32] = id_padded

    img = bytes(header)
    img += align_to(kernel_data, page_size)
    img += align_to(rsce_data, page_size)

    return img


# ─── GPT Partition Table Builder ─────────────────────────────────────

def crc32(data: bytes) -> int:
    """CRC32 (unsigned)."""
    import binascii
    return binascii.crc32(data) & 0xFFFFFFFF


def guid_bytes(guid_str: str) -> bytes:
    """Convert a GUID string (8-4-4-4-12) to mixed-endian bytes (GPT standard)."""
    parts = guid_str.replace('-', '')
    # GPT uses mixed endian: first 3 groups LE, last 2 groups BE
    a = int(parts[0:8], 16).to_bytes(4, 'little')
    b = int(parts[8:12], 16).to_bytes(2, 'little')
    c = int(parts[12:16], 16).to_bytes(2, 'little')
    d = bytes.fromhex(parts[16:20])
    e = bytes.fromhex(parts[20:32])
    return a + b + c + d + e


def build_gpt_partition_entry(
    type_guid: str, unique_guid: str,
    start_lba: int, end_lba: int,
    name: str, attributes: int = 0
) -> bytes:
    """Build a 128-byte GPT partition entry."""
    entry = bytearray(128)
    entry[0:16] = guid_bytes(type_guid)
    entry[16:32] = guid_bytes(unique_guid)
    struct.pack_into('<Q', entry, 32, start_lba)
    struct.pack_into('<Q', entry, 40, end_lba)
    struct.pack_into('<Q', entry, 48, attributes)
    # Name is UTF-16LE, max 36 chars (72 bytes)
    name_bytes = name.encode('utf-16-le')[:72]
    entry[56:56 + len(name_bytes)] = name_bytes
    return bytes(entry)


def build_protective_mbr(disk_size_sectors: int) -> bytes:
    """Build a protective MBR for GPT disk."""
    mbr = bytearray(512)
    # Partition entry 1 at offset 446 (16 bytes)
    mbr[446] = 0x00           # status (not active)
    mbr[447] = 0x00           # CHS first (0,0,1)
    mbr[448] = 0x01
    mbr[449] = 0x00
    mbr[450] = 0xEE           # type = GPT protective
    mbr[451] = 0xFF           # CHS last
    mbr[452] = 0xFF
    mbr[453] = 0xFF
    struct.pack_into('<I', mbr, 454, 1)  # LBA first = 1
    size = min(disk_size_sectors - 1, 0xFFFFFFFF)
    struct.pack_into('<I', mbr, 458, size)  # size in sectors
    # Boot signature
    mbr[510] = 0x55
    mbr[511] = 0xAA
    return bytes(mbr)


def build_gpt_image(partitions_data: dict, total_size_bytes: int) -> bytes:
    """Build a complete GPT disk image with partition data.

    Args:
        partitions_data: dict mapping partition name -> bytes data (or None for empty)
        total_size_bytes: total disk image size
    """
    SECTOR = 512
    total_sectors = total_size_bytes // SECTOR

    # GPT layout constants
    GPT_HEADER_LBA = 1
    GPT_ENTRIES_START_LBA = 2
    NUM_ENTRIES = 128
    ENTRY_SIZE = 128
    ENTRIES_SECTORS = (NUM_ENTRIES * ENTRY_SIZE + SECTOR - 1) // SECTOR  # 32 sectors

    # Define partition GUIDs
    LINUX_FS_GUID = "0FC63DAF-8483-4772-8E79-3D69D8477DE4"  # Linux filesystem
    # Use deterministic unique GUIDs based on partition name
    DISK_GUID = "614E0000-0000-4000-8000-000000000001"

    part_defs = [
        ("uboot",    "614E0000-0000-4000-8000-000000000002"),
        ("misc",     "614E0000-0000-4000-8000-000000000003"),
        ("boot",     "614E0000-0000-4000-8000-000000000004"),
        ("recovery", "614E0000-0000-4000-8000-000000000005"),
        ("backup",   "614E0000-0000-4000-8000-000000000006"),
        ("rootfs",   "614E0000-0000-4000-8000-000000000007"),
    ]

    # Build partition entries
    entries = bytearray()
    for name, unique_guid in part_defs:
        layout = PARTITION_LAYOUT[name]
        start_lba = layout["start"]
        size_sectors = layout["size_mb"] * 1024 * 1024 // SECTOR
        end_lba = start_lba + size_sectors - 1

        entry = build_gpt_partition_entry(
            LINUX_FS_GUID, unique_guid,
            start_lba, end_lba, name
        )
        entries += entry

    # Pad entries to fill all 128 slots
    entries += b'\x00' * (NUM_ENTRIES * ENTRY_SIZE - len(entries))
    entries_crc = crc32(bytes(entries))

    # Build primary GPT header (LBA 1)
    gpt_hdr = bytearray(92)
    gpt_hdr[0:8] = b'EFI PART'                          # Signature
    struct.pack_into('<I', gpt_hdr, 8, 0x00010000)       # Revision 1.0
    struct.pack_into('<I', gpt_hdr, 12, 92)              # Header size
    # CRC32 of header will be filled later (offset 16)
    struct.pack_into('<I', gpt_hdr, 16, 0)               # Header CRC (placeholder)
    struct.pack_into('<I', gpt_hdr, 20, 0)               # Reserved
    struct.pack_into('<Q', gpt_hdr, 24, GPT_HEADER_LBA)  # My LBA
    struct.pack_into('<Q', gpt_hdr, 32, total_sectors - 1)  # Alternate LBA
    struct.pack_into('<Q', gpt_hdr, 40, GPT_ENTRIES_START_LBA + ENTRIES_SECTORS)  # First usable LBA
    struct.pack_into('<Q', gpt_hdr, 48, total_sectors - 1 - ENTRIES_SECTORS - 1)  # Last usable LBA
    gpt_hdr[56:72] = guid_bytes(DISK_GUID)               # Disk GUID
    struct.pack_into('<Q', gpt_hdr, 72, GPT_ENTRIES_START_LBA)  # Partition entries start
    struct.pack_into('<I', gpt_hdr, 80, NUM_ENTRIES)      # Number of entries
    struct.pack_into('<I', gpt_hdr, 84, ENTRY_SIZE)       # Entry size
    struct.pack_into('<I', gpt_hdr, 88, entries_crc)      # Entries CRC32

    # Compute header CRC
    header_crc = crc32(bytes(gpt_hdr))
    struct.pack_into('<I', gpt_hdr, 16, header_crc)

    # Assemble disk image
    img = bytearray(total_size_bytes)

    # Write protective MBR (LBA 0)
    mbr = build_protective_mbr(total_sectors)
    img[0:512] = mbr

    # Write primary GPT header (LBA 1)
    hdr_padded = bytes(gpt_hdr) + b'\x00' * (SECTOR - len(gpt_hdr))
    img[SECTOR:SECTOR * 2] = hdr_padded

    # Write primary partition entries (LBA 2+)
    entries_offset = GPT_ENTRIES_START_LBA * SECTOR
    img[entries_offset:entries_offset + len(entries)] = entries

    # Write partition data
    for name, _ in part_defs:
        if name in partitions_data and partitions_data[name] is not None:
            layout = PARTITION_LAYOUT[name]
            offset = layout["start"] * SECTOR
            data = partitions_data[name]
            # Handle data larger than partition — truncate
            max_size = layout["size_mb"] * 1024 * 1024
            if len(data) > max_size:
                print(f"  WARNING: {name} data ({len(data):,} bytes) exceeds partition "
                      f"({max_size:,} bytes), truncating")
                data = data[:max_size]
            img[offset:offset + len(data)] = data

    # Write backup GPT (at end of disk)
    # Backup entries come before backup header
    backup_entries_lba = total_sectors - 1 - ENTRIES_SECTORS
    backup_entries_offset = backup_entries_lba * SECTOR
    img[backup_entries_offset:backup_entries_offset + len(entries)] = entries

    # Backup GPT header (last LBA)
    backup_hdr = bytearray(gpt_hdr)
    struct.pack_into('<Q', backup_hdr, 24, total_sectors - 1)  # My LBA
    struct.pack_into('<Q', backup_hdr, 32, GPT_HEADER_LBA)     # Alternate LBA
    struct.pack_into('<Q', backup_hdr, 72, backup_entries_lba)  # Entries start
    struct.pack_into('<I', backup_hdr, 16, 0)  # Clear CRC for recomputation
    backup_crc = crc32(bytes(backup_hdr))
    struct.pack_into('<I', backup_hdr, 16, backup_crc)

    backup_hdr_offset = (total_sectors - 1) * SECTOR
    backup_hdr_padded = bytes(backup_hdr) + b'\x00' * (SECTOR - len(backup_hdr))
    img[backup_hdr_offset:backup_hdr_offset + SECTOR] = backup_hdr_padded

    return bytes(img)


# ─── Image Builders ──────────────────────────────────────────────────

def build_kernel_image() -> Path:
    """Build the T1 kernel/boot image (platform-independent, Python only)."""
    print("\n" + "=" * 64)
    print("  STAGE 1: Building T1 Kernel Image")
    print("  " + KERNEL_IMG_NAME)
    print("=" * 64)

    # Validate inputs
    if not S1_ZIMAGE.exists():
        print(f"\n  ERROR: S1 zImage not found: {S1_ZIMAGE}")
        print(f"  Extract from S1 FLSUN-OS 3.0 boot.img first.")
        sys.exit(1)

    if not T1_DTB.exists():
        print(f"\n  ERROR: T1 DTB not found: {T1_DTB}")
        print(f"  Run patch-dtb-for-t1.py first.")
        sys.exit(1)

    print(f"\n  Kernel: {S1_ZIMAGE.name} ({S1_ZIMAGE.stat().st_size:,} bytes)")
    print(f"  DTB:    {T1_DTB.name} ({T1_DTB.stat().st_size:,} bytes)")

    # Read inputs
    kernel_data = S1_ZIMAGE.read_bytes()
    dtb_data = T1_DTB.read_bytes()

    # Validate zImage
    if len(kernel_data) > 40:
        zimage_magic = struct.unpack_from('<I', kernel_data, 36)[0]
        if zimage_magic == 0x016F2818:
            print(f"  ✓ Valid ARM zImage")
        else:
            print(f"  WARNING: zImage magic mismatch: 0x{zimage_magic:08X}")

    # Validate DTB
    dtb_magic = struct.unpack_from('>I', dtb_data, 0)[0]
    if dtb_magic != 0xD00DFEED:
        print(f"  ERROR: DTB magic mismatch: 0x{dtb_magic:08X}")
        sys.exit(1)
    print(f"  ✓ Valid FDT/DTB")

    # Build RSCE
    print(f"\n  Building RSCE resource container...")
    rsce = build_rsce(dtb_data)
    print(f"  RSCE: {len(rsce):,} bytes")

    # Build boot image
    print(f"  Building Android boot image...")
    boot_img = build_android_boot_img(kernel_data, rsce)
    print(f"  boot.img: {len(boot_img):,} bytes ({len(boot_img) / 1024 / 1024:.2f} MB)")

    # Write output
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = OUTPUT_DIR / KERNEL_IMG_NAME
    output_path.write_bytes(boot_img)

    print(f"\n  ✓ Written: {output_path}")
    print(f"    Format:  Android boot (ANDROID! magic)")
    print(f"    Kernel:  Linux 6.1.99flsun (S1, compatible with RV1109)")
    print(f"    DTB:     T1-patched (800×480 @ 25 MHz)")
    print(f"    Size:    {output_path.stat().st_size:,} bytes")

    return output_path


def build_rootfs_image() -> Path:
    """Build the T1 rootfs image by modifying S1 rootfs.

    This requires Linux (ext4 mount) and root access.
    """
    print("\n" + "=" * 64)
    print("  STAGE 2: Building T1 Rootfs Image")
    print("  " + ROOTFS_IMG_NAME)
    print("=" * 64)

    if platform.system() != 'Linux':
        print(f"\n  ERROR: Rootfs building requires Linux (ext4 mount).")
        print(f"  Current platform: {platform.system()}")
        print(f"\n  Options:")
        print(f"    1. Run this script on Linux or WSL")
        print(f"    2. Use build-rootfs-t1.sh script directly")
        print(f"    3. Use build-t1.sh for a full debos build")
        sys.exit(1)

    if os.geteuid() != 0:
        print(f"\n  ERROR: Must run as root for ext4 operations.")
        print(f"  Run: sudo python3 {sys.argv[0]} --rootfs")
        sys.exit(1)

    if not S1_ROOTFS.exists():
        print(f"\n  ERROR: S1 rootfs.img not found: {S1_ROOTFS}")
        print(f"  Download FLSUN-OS S1 EMMC 3.0 first.")
        sys.exit(1)

    if not MOD_ROOTFS_SCRIPT.exists():
        print(f"\n  ERROR: mod-rootfs-for-t1.sh not found: {MOD_ROOTFS_SCRIPT}")
        sys.exit(1)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = OUTPUT_DIR / ROOTFS_IMG_NAME

    print(f"\n  Source:  {S1_ROOTFS} ({S1_ROOTFS.stat().st_size / 1024 / 1024:.0f} MB)")
    print(f"  Output:  {output_path}")

    # Copy S1 rootfs as base
    print(f"\n  Copying S1 rootfs as base (this may take a while)...")
    shutil.copy2(str(S1_ROOTFS), str(output_path))
    print(f"  ✓ Copied ({output_path.stat().st_size / 1024 / 1024:.0f} MB)")

    # Mount the rootfs
    mount_point = Path(tempfile.mkdtemp(prefix="flsun-t1-rootfs-"))
    try:
        print(f"\n  Mounting rootfs at {mount_point}...")
        subprocess.run(
            ["mount", "-o", "loop", str(output_path), str(mount_point)],
            check=True
        )
        print(f"  ✓ Mounted")

        # Run mod-rootfs-for-t1.sh
        print(f"\n  Running S1→T1 rootfs modifications...")
        subprocess.run(
            ["bash", str(MOD_ROOTFS_SCRIPT), str(mount_point)],
            check=True,
            env={**os.environ, "TERM": "xterm"}
        )
        print(f"  ✓ Rootfs modified for T1")

    finally:
        # Unmount
        print(f"\n  Unmounting...")
        subprocess.run(["sync"], check=True)
        subprocess.run(["umount", str(mount_point)], check=True)
        mount_point.rmdir()
        print(f"  ✓ Unmounted and cleaned up")

    # Shrink the image with resize2fs (optional, saves space)
    print(f"\n  Checking filesystem...")
    subprocess.run(["e2fsck", "-f", "-y", str(output_path)], check=False)
    # Don't shrink — keep full size for eMMC flash compatibility

    print(f"\n  ✓ Written: {output_path}")
    print(f"    Format:  ext4 partition image")
    print(f"    Size:    {output_path.stat().st_size / 1024 / 1024:.0f} MB")

    return output_path


def build_complete_image(kernel_path: Path = None, rootfs_path: Path = None) -> Path:
    """Build a complete eMMC disk image with GPT partition table.

    Combines kernel (boot) and rootfs images into a single flashable image.
    """
    print("\n" + "=" * 64)
    print("  STAGE 3: Building Complete eMMC Image")
    print("  " + COMPLETE_IMG_NAME)
    print("=" * 64)

    # Find or build component images
    if kernel_path is None:
        kernel_path = OUTPUT_DIR / KERNEL_IMG_NAME
    if rootfs_path is None:
        rootfs_path = OUTPUT_DIR / ROOTFS_IMG_NAME

    if not kernel_path.exists():
        print(f"\n  Kernel image not found, building it now...")
        kernel_path = build_kernel_image()

    if not rootfs_path.exists():
        print(f"\n  ERROR: Rootfs image not found: {rootfs_path}")
        print(f"  Build it first with: {sys.argv[0]} --rootfs")
        sys.exit(1)

    kernel_data = kernel_path.read_bytes()
    rootfs_data = rootfs_path.read_bytes()

    print(f"\n  Kernel:  {kernel_path.name} ({len(kernel_data) / 1024 / 1024:.2f} MB)")
    print(f"  Rootfs:  {rootfs_path.name} ({len(rootfs_data) / 1024 / 1024:.0f} MB)")

    # Calculate total image size
    # rootfs partition starts at PARTITION_LAYOUT["rootfs"]["start"] sectors
    # and needs to fit the entire rootfs.img
    rootfs_start_bytes = PARTITION_LAYOUT["rootfs"]["start"] * 512
    total_size = rootfs_start_bytes + len(rootfs_data)
    # Round up to nearest MB and add 1 MB for backup GPT
    total_size = ((total_size + 1024 * 1024 - 1) // (1024 * 1024) + 1) * 1024 * 1024

    print(f"  Total image size: {total_size / 1024 / 1024:.0f} MB")

    # Build partition data
    partitions_data = {
        "boot": kernel_data,
        "rootfs": rootfs_data,
        # uboot, misc, recovery, backup — left empty (zeros)
        # The T1's existing U-Boot in eMMC handles boot; we only flash boot+rootfs
    }

    print(f"\n  Building GPT disk image...")
    disk_img = build_gpt_image(partitions_data, total_size)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = OUTPUT_DIR / COMPLETE_IMG_NAME

    print(f"  Writing {output_path.name}...")
    output_path.write_bytes(disk_img)

    print(f"\n  ✓ Written: {output_path}")
    print(f"    Format:    GPT disk image")
    print(f"    Size:      {output_path.stat().st_size / 1024 / 1024:.0f} MB")
    print(f"    Partitions:")
    for name in ["uboot", "misc", "boot", "recovery", "backup", "rootfs"]:
        layout = PARTITION_LAYOUT[name]
        has_data = name in partitions_data and partitions_data[name] is not None
        status = f"({len(partitions_data[name]) / 1024 / 1024:.1f} MB)" if has_data else "(empty)"
        print(f"      {name:10s} @ sector 0x{layout['start']:08X}  {layout['size_mb']:>5d} MB  {status}")

    return output_path


# ─── Build Manifest ──────────────────────────────────────────────────

def write_manifest(images: dict):
    """Write a JSON manifest describing the built images."""
    manifest = {
        "build_tool": "build-images-t1.py",
        "version": VERSION,
        "build_date": BUILD_DATE,
        "platform": platform.platform(),
        "target": "FLSUN T1 (Rockchip RV1109)",
        "base": "FLSUN-OS S1 3.0 (Linux 6.1.99flsun)",
        "images": {}
    }

    for name, path in images.items():
        if path and path.exists():
            manifest["images"][name] = {
                "filename": path.name,
                "size_bytes": path.stat().st_size,
                "size_mb": round(path.stat().st_size / 1024 / 1024, 2),
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest()
            }

    manifest_path = OUTPUT_DIR / "flsun-os-t1-manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2))
    print(f"\n  Manifest: {manifest_path}")


# ─── Main ─────────────────────────────────────────────────────────────

def print_banner():
    print()
    print("╔══════════════════════════════════════════════════════════════╗")
    print("║         FLSUN-OS T1 Image Builder — Master Tool            ║")
    print("║  Rockchip RV1109 • Debian 13 Trixie • Linux 6.1.99flsun   ║")
    print("╚══════════════════════════════════════════════════════════════╝")
    print()
    print(f"  Build date:  {BUILD_DATE}")
    print(f"  Version:     {VERSION}")
    print(f"  Platform:    {platform.platform()}")
    print(f"  Output dir:  {OUTPUT_DIR}")
    print()


def main():
    build_modes = set()

    # Parse arguments
    for arg in sys.argv[1:]:
        if arg in ('--kernel', '-k'):
            build_modes.add('kernel')
        elif arg in ('--rootfs', '-r'):
            build_modes.add('rootfs')
        elif arg in ('--complete', '-c'):
            build_modes.add('complete')
        elif arg in ('--all', '-a'):
            build_modes = {'kernel', 'rootfs', 'complete'}
        elif arg in ('--help', '-h'):
            print(__doc__)
            sys.exit(0)
        else:
            print(f"Unknown argument: {arg}")
            print(f"Run: {sys.argv[0]} --help")
            sys.exit(1)

    # Default: build kernel only (works on all platforms)
    if not build_modes:
        build_modes.add('kernel')

    print_banner()

    images = {}

    if 'kernel' in build_modes:
        images['kernel'] = build_kernel_image()

    if 'rootfs' in build_modes:
        images['rootfs'] = build_rootfs_image()

    if 'complete' in build_modes:
        images['complete'] = build_complete_image(
            kernel_path=images.get('kernel'),
            rootfs_path=images.get('rootfs')
        )

    # Write manifest
    write_manifest(images)

    # Final summary
    print("\n" + "=" * 64)
    print("  BUILD COMPLETE")
    print("=" * 64)
    print()
    for name, path in images.items():
        if path and path.exists():
            print(f"  ✓ {path.name:40s} {path.stat().st_size / 1024 / 1024:>8.2f} MB")
    print()

    if 'rootfs' not in build_modes and 'complete' not in build_modes:
        print("  NOTE: Only kernel image was built (platform-independent).")
        print("  For rootfs and complete images, run on Linux/WSL with:")
        print(f"    sudo python3 {sys.argv[0]} --all")
        print()

    print("  Flash instructions:")
    print("    RKDevTool:  Use boot.img (0x8000) + rootfs.img (0x38000)")
    print("    Complete:   Flash flsun-os-t1-complete.img as raw disk image")
    print("    Kernel:     dd flsun-os-t1-kernel.img to /dev/mmcblk0p3")
    print()


if __name__ == '__main__':
    main()
