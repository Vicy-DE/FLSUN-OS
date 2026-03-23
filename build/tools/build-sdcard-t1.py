#!/usr/bin/env python3
"""
FLSUN-OS T1 SD Card Image Builder
══════════════════════════════════

Builds bootable microSD card images for the FLSUN T1 3D printer.

The T1 uses a Rockchip RV1109 SoC whose BootROM scans SD before eMMC,
so inserting a properly-formatted SD card will auto-boot from it.

Two build phases:

  Phase 1 (--phase1): "Boot-test" SD card
    - S1 rootfs unchanged (configs wrong for T1, but boots and shows display)
    - Verifies: bootloader extraction, display patch, SD boot mechanism
    - Output: FLSUN-OS-T1-SD-phase1.img (+ .gz if --compress)

  Phase 2 (--phase2): "Full T1" SD card
    - S1 rootfs modified for T1 hardware (correct Klipper configs, services, etc.)
    - Requires WSL with Debian (for ext4 mount + rootfs modification)
    - Offline mods applied; git/pip operations deferred to first boot
    - Output: FLSUN-OS-T1-SD.img (+ .gz if --compress)

Image contents:
  - IDBLoader (TPL+SPL) — extracted from T1 stock eMMC dump
  - U-Boot (FIT image)  — extracted from T1 stock eMMC dump
  - boot.img (Android)  — S1 kernel 6.1.99flsun + T1 DTB (800×480)
  - rootfs (ext4)       — FLSUN-OS 3.0 rootfs (S1 base or T1-modified)

Usage:
    py build-sdcard-t1.py --phase1              # Build boot-test SD image
    py build-sdcard-t1.py --phase2              # Build full T1 SD (requires WSL)
    py build-sdcard-t1.py --all                 # Build both images
    py build-sdcard-t1.py --phase1 --compress   # Build + gzip compress

Requirements:
    Python 3.6+ (no external dependencies)
    T1 stock eMMC dump: resources/T1/firmwares/stock/1097_0.img (gzip-compressed)
    T1 stock U-Boot:    resources/T1/firmwares/stock/1097_0p1.img (gzip-compressed)
    S1 FLSUN-OS 3.0:    resources/S1/firmwares/os-images/FLSUN-OS-S1-EMMC-3.0/
    T1 DTB:             resources/T1/firmwares/os-images/rk-kernel-t1.dtb
    WSL Debian (Phase 2 only)

Disk layout (T1 GPT — matches stock partition table):
    Sector 0        Protective MBR
    Sector 1        GPT header
    Sectors 2-33    GPT partition entries (128 × 128 bytes)
    Sector 64+      IDBLoader (TPL + SPL, Rockchip convention)
    Sector 0x4000   uboot partition (4 MB) — U-Boot FIT image
    Sector 0x6000   misc partition (4 MB) — empty
    Sector 0x8000   boot partition (32 MB) — Android boot.img
    Sector 0x18000  recovery partition (32 MB) — empty
    Sector 0x28000  backup partition (32 MB) — empty
    Sector 0x38000  rootfs partition — ext4 filesystem
    End-33          Backup GPT entries
    End             Backup GPT header
"""

import struct
import os
import sys
import gzip
import hashlib
import shutil
import subprocess
import platform
import json
import binascii
import time
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

# T1 files
T1_DTB = REPO_ROOT / "resources" / "T1" / "firmwares" / "os-images" / "rk-kernel-t1.dtb"
T1_STOCK_DIR = REPO_ROOT / "resources" / "T1" / "firmwares" / "stock"
T1_STOCK_FULL = T1_STOCK_DIR / "1097_0.img"       # Gzip-compressed full eMMC dump
T1_STOCK_UBOOT = T1_STOCK_DIR / "1097_0p1.img"    # Gzip-compressed U-Boot partition

# Rootfs modification script (Phase 2)
MOD_ROOTFS_SCRIPT = SCRIPT_DIR / "mod-rootfs-for-t1.sh"

# Output names
PHASE1_IMG_NAME = "FLSUN-OS-T1-SD-phase1.img"
PHASE2_IMG_NAME = "FLSUN-OS-T1-SD.img"

SECTOR = 512

# T1 partition layout — sector offsets match stock T1 GPT
# Non-rootfs partitions keep stock sizes; rootfs is dynamically sized
PARTITION_STARTS = {
    "uboot":    0x00004000,
    "misc":     0x00006000,
    "boot":     0x00008000,
    "recovery": 0x00018000,
    "backup":   0x00028000,
    "rootfs":   0x00038000,
}

# Fixed partition sizes (rootfs is dynamic based on filesystem image)
PARTITION_FIXED_SIZES_MB = {
    "uboot":    4,
    "misc":     4,
    "boot":     32,
    "recovery": 32,
    "backup":   32,
}

# IDBLoader lives at sector 64 (Rockchip convention — raw area before partitions)
IDLOADER_SECTOR = 64

# GPT partition GUIDs (deterministic, same as build-images-t1.py)
LINUX_FS_GUID = "0FC63DAF-8483-4772-8E79-3D69D8477DE4"
DISK_GUID = "614E0000-0000-4000-8000-000000000001"
PART_GUIDS = {
    "uboot":    "614E0000-0000-4000-8000-000000000002",
    "misc":     "614E0000-0000-4000-8000-000000000003",
    "boot":     "614E0000-0000-4000-8000-000000000004",
    "recovery": "614E0000-0000-4000-8000-000000000005",
    "backup":   "614E0000-0000-4000-8000-000000000006",
    "rootfs":   "614E0000-0000-4000-8000-000000000007",
}

# Boot image cmdline — explicit root=PARTUUID ensures correct rootfs mount
# from SD card regardless of eMMC contents or U-Boot default bootargs
SD_BOOT_CMDLINE = (
    b"earlycon=uart8250,mmio32,0xff570000 "
    b"console=ttyFIQ0 "
    b"root=PARTUUID=614e0000-0000-4000-8000-000000000007 "
    b"rootfstype=ext4 rootwait "
    b"snd_aloop.index=7"
)

VERSION = "1.0"
BUILD_DATE = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


# ─── GPT / Boot Image Utilities ──────────────────────────────────────

def align_to(data: bytes, alignment: int) -> bytes:
    """Pad data to alignment boundary with zeros."""
    remainder = len(data) % alignment
    if remainder:
        data += b'\x00' * (alignment - remainder)
    return data


def crc32(data: bytes) -> int:
    """CRC32 (unsigned)."""
    return binascii.crc32(data) & 0xFFFFFFFF


def guid_bytes(guid_str: str) -> bytes:
    """Convert a GUID string (8-4-4-4-12) to mixed-endian bytes (GPT standard)."""
    parts = guid_str.replace('-', '')
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
    name_bytes = name.encode('utf-16-le')[:72]
    entry[56:56 + len(name_bytes)] = name_bytes
    return bytes(entry)


def build_protective_mbr(disk_size_sectors: int) -> bytes:
    """Build a protective MBR for GPT disk."""
    mbr = bytearray(512)
    mbr[446] = 0x00        # status
    mbr[447] = 0x00        # CHS first
    mbr[448] = 0x01
    mbr[449] = 0x00
    mbr[450] = 0xEE        # type = GPT protective
    mbr[451] = 0xFF        # CHS last
    mbr[452] = 0xFF
    mbr[453] = 0xFF
    struct.pack_into('<I', mbr, 454, 1)  # LBA first = 1
    size = min(disk_size_sectors - 1, 0xFFFFFFFF)
    struct.pack_into('<I', mbr, 458, size)
    mbr[510] = 0x55
    mbr[511] = 0xAA
    return bytes(mbr)


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


def build_sd_boot_img(kernel_data: bytes, dtb_data: bytes) -> bytes:
    """Build an Android boot image for T1 SD card boot.

    Uses explicit root=PARTUUID cmdline to ensure the kernel mounts
    the SD card's rootfs partition, not the eMMC rootfs.
    """
    page_size = 2048
    kernel_addr = 0x62008000
    ramdisk_addr = 0x62000000
    second_addr = 0x62000000
    tags_addr = 0x00000100

    rsce = build_rsce(dtb_data)

    kernel_size = len(kernel_data)
    ramdisk_size = 0
    second_size = len(rsce)

    # Compute SHA1 ID
    sha = hashlib.sha1()
    sha.update(kernel_data)
    sha.update(struct.pack('<I', kernel_size))
    sha.update(struct.pack('<I', ramdisk_size))
    sha.update(rsce)
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
    struct.pack_into('<I', header, 40, 0)  # header version
    struct.pack_into('<I', header, 44, 0)  # os version
    header[64:64 + len(SD_BOOT_CMDLINE)] = SD_BOOT_CMDLINE[:512]
    header[576:576 + 32] = id_padded

    img = bytes(header)
    img += align_to(kernel_data, page_size)
    img += align_to(rsce, page_size)

    return img


# ─── Bootloader Extraction ───────────────────────────────────────────

def extract_idloader(stock_dump_path: Path) -> bytes:
    """Extract IDBLoader from gzip-compressed T1 full eMMC dump.

    The IDBLoader sits at sector 64 in raw disk area (Rockchip convention),
    before any GPT partition. Contains TPL (DDR init) + SPL.
    We extract sectors 64 through 0x3FFF (the gap before the uboot partition).
    """
    idloader_offset = IDLOADER_SECTOR * SECTOR  # 32768
    # Read up to the start of the uboot partition
    idloader_max_sectors = PARTITION_STARTS["uboot"] - IDLOADER_SECTOR  # 16320 sectors
    idloader_max_bytes = idloader_max_sectors * SECTOR  # 8,355,840 bytes

    print(f"  Extracting IDBLoader from {stock_dump_path.name}...")
    print(f"    Sector range: {IDLOADER_SECTOR} - {PARTITION_STARTS['uboot'] - 1}")
    print(f"    Byte offset:  0x{idloader_offset:X} ({idloader_offset:,})")
    print(f"    Max size:     {idloader_max_bytes:,} bytes")

    with gzip.open(str(stock_dump_path), 'rb') as f:
        # Seek to IDBLoader position (sequential decompression, fast for small offsets)
        f.seek(idloader_offset)
        data = f.read(idloader_max_bytes)

    if not data:
        print("  ERROR: No data read from IDBLoader area")
        sys.exit(1)

    # Trim trailing zeros (find last non-zero byte)
    last_nonzero = len(data) - 1
    while last_nonzero >= 0 and data[last_nonzero] == 0:
        last_nonzero -= 1

    if last_nonzero < 0:
        print("  ERROR: IDBLoader area is all zeros!")
        sys.exit(1)

    # Round up to sector boundary
    trimmed_size = ((last_nonzero + SECTOR) // SECTOR) * SECTOR
    data = data[:trimmed_size]

    print(f"    Content:      {trimmed_size:,} bytes ({trimmed_size / 1024:.0f} KB)")
    print(f"    ✓ IDBLoader extracted")

    return data


def extract_uboot(stock_uboot_path: Path) -> bytes:
    """Extract U-Boot FIT image from gzip-compressed partition dump.

    The T1 U-Boot is a FIT (Flattened Image Tree) containing U-Boot binary,
    OP-TEE, and device tree. No separate trust partition needed.
    """
    print(f"  Extracting U-Boot from {stock_uboot_path.name}...")

    with gzip.open(str(stock_uboot_path), 'rb') as f:
        data = f.read()

    if len(data) < 4:
        print("  ERROR: U-Boot data too small")
        sys.exit(1)

    # Verify FIT magic (0xD00DFEED = FDT magic)
    magic = struct.unpack_from('>I', data, 0)[0]
    if magic == 0xD00DFEED:
        print(f"    ✓ Valid FIT image (FDT magic)")
    else:
        print(f"    WARNING: Expected FIT magic 0xD00DFEED, got 0x{magic:08X}")

    print(f"    Size: {len(data):,} bytes ({len(data) / 1024 / 1024:.1f} MB)")
    print(f"    ✓ U-Boot extracted")

    return data


# ─── GPT Construction ────────────────────────────────────────────────

def build_gpt_structures(rootfs_sectors: int, total_sectors: int):
    """Build GPT partition table entries and headers.

    Returns (primary_header, entries, backup_header) as bytes.
    The rootfs partition end_lba is set dynamically based on rootfs image size.
    """
    GPT_ENTRIES_START_LBA = 2
    NUM_ENTRIES = 128
    ENTRY_SIZE = 128
    ENTRIES_SECTORS = (NUM_ENTRIES * ENTRY_SIZE + SECTOR - 1) // SECTOR  # 32

    # Build partition entries with dynamic rootfs size
    part_defs = [
        ("uboot",    PART_GUIDS["uboot"]),
        ("misc",     PART_GUIDS["misc"]),
        ("boot",     PART_GUIDS["boot"]),
        ("recovery", PART_GUIDS["recovery"]),
        ("backup",   PART_GUIDS["backup"]),
        ("rootfs",   PART_GUIDS["rootfs"]),
    ]

    entries = bytearray()
    for name, unique_guid in part_defs:
        start_lba = PARTITION_STARTS[name]
        if name == "rootfs":
            end_lba = start_lba + rootfs_sectors - 1
        else:
            size_sectors = PARTITION_FIXED_SIZES_MB[name] * 1024 * 1024 // SECTOR
            end_lba = start_lba + size_sectors - 1

        entry = build_gpt_partition_entry(
            LINUX_FS_GUID, unique_guid,
            start_lba, end_lba, name
        )
        entries += entry

    # Pad entries to 128 slots
    entries += b'\x00' * (NUM_ENTRIES * ENTRY_SIZE - len(entries))
    entries_crc = crc32(bytes(entries))

    # Primary GPT header (LBA 1)
    gpt_hdr = bytearray(92)
    gpt_hdr[0:8] = b'EFI PART'
    struct.pack_into('<I', gpt_hdr, 8, 0x00010000)       # Revision 1.0
    struct.pack_into('<I', gpt_hdr, 12, 92)               # Header size
    struct.pack_into('<I', gpt_hdr, 16, 0)                # CRC placeholder
    struct.pack_into('<I', gpt_hdr, 20, 0)                # Reserved
    struct.pack_into('<Q', gpt_hdr, 24, 1)                # My LBA
    struct.pack_into('<Q', gpt_hdr, 32, total_sectors - 1)  # Alternate LBA
    struct.pack_into('<Q', gpt_hdr, 40, GPT_ENTRIES_START_LBA + ENTRIES_SECTORS)  # First usable
    struct.pack_into('<Q', gpt_hdr, 48, total_sectors - 1 - ENTRIES_SECTORS - 1)  # Last usable
    gpt_hdr[56:72] = guid_bytes(DISK_GUID)
    struct.pack_into('<Q', gpt_hdr, 72, GPT_ENTRIES_START_LBA)  # Entries start
    struct.pack_into('<I', gpt_hdr, 80, NUM_ENTRIES)
    struct.pack_into('<I', gpt_hdr, 84, ENTRY_SIZE)
    struct.pack_into('<I', gpt_hdr, 88, entries_crc)

    header_crc = crc32(bytes(gpt_hdr))
    struct.pack_into('<I', gpt_hdr, 16, header_crc)

    # Backup GPT header (last LBA)
    backup_entries_lba = total_sectors - 1 - ENTRIES_SECTORS
    backup_hdr = bytearray(gpt_hdr)
    struct.pack_into('<Q', backup_hdr, 24, total_sectors - 1)    # My LBA
    struct.pack_into('<Q', backup_hdr, 32, 1)                     # Alternate LBA
    struct.pack_into('<Q', backup_hdr, 72, backup_entries_lba)    # Entries start
    struct.pack_into('<I', backup_hdr, 16, 0)
    backup_crc = crc32(bytes(backup_hdr))
    struct.pack_into('<I', backup_hdr, 16, backup_crc)

    # Pad headers to sector size
    primary_hdr = bytes(gpt_hdr) + b'\x00' * (SECTOR - len(gpt_hdr))
    backup_hdr_bytes = bytes(backup_hdr) + b'\x00' * (SECTOR - len(backup_hdr))

    return primary_hdr, bytes(entries), backup_hdr_bytes


# ─── SD Image Assembly ───────────────────────────────────────────────

def assemble_sd_image(
    output_path: Path,
    boot_img: bytes,
    idloader: bytes,
    uboot: bytes,
    rootfs_path: Path,
) -> Path:
    """Assemble a complete bootable SD card image with GPT.

    Writes directly to file using seek operations — the rootfs is streamed
    in chunks, so memory usage stays low even for 7+ GB images.
    """
    rootfs_size = rootfs_path.stat().st_size
    rootfs_sectors = (rootfs_size + SECTOR - 1) // SECTOR
    rootfs_start = PARTITION_STARTS["rootfs"]
    rootfs_end_lba = rootfs_start + rootfs_sectors - 1

    # Total image: rootfs end + backup GPT (32 entries sectors + 1 header)
    ENTRIES_SECTORS = 32
    total_sectors = rootfs_end_lba + 1 + ENTRIES_SECTORS + 1
    # Round up to 4 MB alignment (SD card block alignment)
    align_sectors = 4 * 1024 * 1024 // SECTOR  # 8192 sectors = 4 MB
    total_sectors = ((total_sectors + align_sectors - 1) // align_sectors) * align_sectors
    total_size = total_sectors * SECTOR

    print(f"\n  Image layout:")
    print(f"    Protective MBR   sector 0")
    print(f"    GPT header       sector 1")
    print(f"    GPT entries      sectors 2-33")
    print(f"    IDBLoader        sector {IDLOADER_SECTOR}  ({len(idloader) / 1024:.0f} KB)")
    print(f"    uboot (U-Boot)   sector 0x{PARTITION_STARTS['uboot']:X}  ({len(uboot) / 1024:.0f} KB)")
    print(f"    misc             sector 0x{PARTITION_STARTS['misc']:X}  (empty)")
    print(f"    boot (boot.img)  sector 0x{PARTITION_STARTS['boot']:X}  ({len(boot_img) / 1024:.0f} KB)")
    print(f"    recovery         sector 0x{PARTITION_STARTS['recovery']:X}  (empty)")
    print(f"    backup           sector 0x{PARTITION_STARTS['backup']:X}  (empty)")
    print(f"    rootfs           sector 0x{PARTITION_STARTS['rootfs']:X}  ({rootfs_size / 1024 / 1024 / 1024:.2f} GB)")
    print(f"    Backup GPT       sector {total_sectors - ENTRIES_SECTORS - 1}")
    print(f"    Total image      {total_size / 1024 / 1024 / 1024:.2f} GB ({total_sectors:,} sectors)")

    # Validate sizes
    boot_partition_size = PARTITION_FIXED_SIZES_MB["boot"] * 1024 * 1024
    if len(boot_img) > boot_partition_size:
        print(f"\n  ERROR: boot.img ({len(boot_img):,} bytes) exceeds boot partition ({boot_partition_size:,} bytes)")
        sys.exit(1)

    uboot_partition_size = PARTITION_FIXED_SIZES_MB["uboot"] * 1024 * 1024
    if len(uboot) > uboot_partition_size:
        print(f"\n  ERROR: U-Boot ({len(uboot):,} bytes) exceeds uboot partition ({uboot_partition_size:,} bytes)")
        sys.exit(1)

    # Build GPT structures
    print(f"\n  Building GPT partition table...")
    primary_hdr, entries, backup_hdr = build_gpt_structures(rootfs_sectors, total_sectors)

    # Create output file and write components
    print(f"  Writing SD card image: {output_path.name}")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    with open(str(output_path), 'wb') as f:
        # Pre-allocate file to total size (creates sparse file on NTFS)
        f.seek(total_size - 1)
        f.write(b'\x00')

        # 1. Protective MBR (sector 0)
        f.seek(0)
        f.write(build_protective_mbr(total_sectors))

        # 2. Primary GPT header (sector 1)
        f.seek(SECTOR)
        f.write(primary_hdr)

        # 3. Primary GPT entries (sectors 2-33)
        f.seek(2 * SECTOR)
        f.write(entries)

        # 4. IDBLoader (sector 64 — raw area before partitions)
        f.seek(IDLOADER_SECTOR * SECTOR)
        f.write(idloader)

        # 5. U-Boot FIT image (uboot partition at sector 0x4000)
        f.seek(PARTITION_STARTS["uboot"] * SECTOR)
        f.write(uboot)

        # 6. boot.img (boot partition at sector 0x8000)
        f.seek(PARTITION_STARTS["boot"] * SECTOR)
        f.write(boot_img)

        # 7. rootfs — stream in 1 MB chunks for memory efficiency
        print(f"  Streaming rootfs ({rootfs_size / 1024 / 1024 / 1024:.2f} GB)...")
        f.seek(PARTITION_STARTS["rootfs"] * SECTOR)
        chunk_size = 1024 * 1024  # 1 MB
        bytes_written = 0
        t_start = time.time()
        with open(str(rootfs_path), 'rb') as rfs:
            while True:
                chunk = rfs.read(chunk_size)
                if not chunk:
                    break
                f.write(chunk)
                bytes_written += len(chunk)
                # Progress every 256 MB
                if bytes_written % (256 * 1024 * 1024) == 0:
                    pct = bytes_written / rootfs_size * 100
                    elapsed = time.time() - t_start
                    speed = bytes_written / elapsed / 1024 / 1024 if elapsed > 0 else 0
                    print(f"    {pct:5.1f}%  ({bytes_written / 1024 / 1024:.0f} MB, {speed:.0f} MB/s)")

        elapsed = time.time() - t_start
        print(f"    100.0%  ({bytes_written / 1024 / 1024:.0f} MB in {elapsed:.1f}s)")

        # 8. Backup GPT entries (near end of disk)
        backup_entries_lba = total_sectors - 1 - ENTRIES_SECTORS
        f.seek(backup_entries_lba * SECTOR)
        f.write(entries)

        # 9. Backup GPT header (last sector)
        f.seek((total_sectors - 1) * SECTOR)
        f.write(backup_hdr)

    final_size = output_path.stat().st_size
    print(f"\n  ✓ SD image written: {output_path}")
    print(f"    Size: {final_size:,} bytes ({final_size / 1024 / 1024 / 1024:.2f} GB)")

    return output_path


# ─── Compression ──────────────────────────────────────────────────────

def compress_image(img_path: Path) -> Path:
    """Compress SD image with gzip."""
    gz_path = img_path.parent / (img_path.name + ".gz")
    img_size = img_path.stat().st_size

    print(f"\n  Compressing {img_path.name} → {gz_path.name}...")
    print(f"  Input size: {img_size / 1024 / 1024 / 1024:.2f} GB")

    t_start = time.time()
    bytes_read = 0
    chunk_size = 4 * 1024 * 1024  # 4 MB

    with open(str(img_path), 'rb') as f_in:
        with gzip.open(str(gz_path), 'wb', compresslevel=6) as f_out:
            while True:
                chunk = f_in.read(chunk_size)
                if not chunk:
                    break
                f_out.write(chunk)
                bytes_read += len(chunk)
                if bytes_read % (256 * 1024 * 1024) == 0:
                    pct = bytes_read / img_size * 100
                    elapsed = time.time() - t_start
                    speed = bytes_read / elapsed / 1024 / 1024 if elapsed > 0 else 0
                    print(f"    {pct:5.1f}%  ({speed:.0f} MB/s)")

    elapsed = time.time() - t_start
    gz_size = gz_path.stat().st_size
    ratio = gz_size / img_size * 100
    print(f"  ✓ Compressed: {gz_path}")
    print(f"    {gz_size / 1024 / 1024:.0f} MB ({ratio:.0f}% of original, {elapsed:.0f}s)")

    return gz_path


# ─── Phase 2: Rootfs Modification via WSL ─────────────────────────────

def windows_to_wsl_path(win_path: Path) -> str:
    """Convert a Windows path to a WSL /mnt/drive/ path."""
    path_str = str(win_path).replace('\\', '/')
    if len(path_str) >= 2 and path_str[1] == ':':
        drive = path_str[0].lower()
        return f'/mnt/{drive}{path_str[2:]}'
    return path_str


def check_wsl_available() -> bool:
    """Check if WSL with Debian is available."""
    try:
        result = subprocess.run(
            ['wsl', '-d', 'Debian', '--', 'echo', 'ok'],
            capture_output=True, text=True, timeout=10
        )
        return result.returncode == 0 and 'ok' in result.stdout
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def modify_rootfs_phase2(rootfs_copy_path: Path) -> bool:
    """Modify S1 rootfs for T1 using WSL Debian.

    Mounts the ext4 rootfs image via loop device in WSL and runs
    mod-rootfs-for-t1.sh in offline mode. This applies file-level changes
    (configs, services, hostname, etc.) and creates a marker file for
    operations that require a running system (git fork switches, pip install).
    """
    print(f"\n  Modifying rootfs for T1 via WSL...")

    if not check_wsl_available():
        print("  ERROR: WSL with Debian not available.")
        print("  Install WSL Debian: wsl --install -d Debian")
        return False

    if not MOD_ROOTFS_SCRIPT.exists():
        print(f"  ERROR: mod-rootfs-for-t1.sh not found: {MOD_ROOTFS_SCRIPT}")
        return False

    wsl_rootfs = windows_to_wsl_path(rootfs_copy_path)
    wsl_repo = windows_to_wsl_path(REPO_ROOT)
    wsl_script = windows_to_wsl_path(MOD_ROOTFS_SCRIPT)

    mount_point = "/tmp/flsun-t1-rootfs"

    # Build the WSL command — mount rootfs, run modification script, unmount
    wsl_commands = f"""
set -e
echo "=== WSL rootfs modification ==="

# Create mount point
mkdir -p {mount_point}

# Mount the ext4 image
echo "Mounting rootfs image..."
mount -o loop "{wsl_rootfs}" {mount_point}
echo "Mounted at {mount_point}"

# Run modification script in offline mode
echo "Running mod-rootfs-for-t1.sh..."
cd "{wsl_repo}"
bash "{wsl_script}" {mount_point}

# Unmount
echo "Unmounting..."
sync
umount {mount_point}
rmdir {mount_point}
echo "=== WSL rootfs modification complete ==="
"""

    print(f"  Running mod-rootfs-for-t1.sh in WSL (offline mode)...")
    print(f"    Rootfs:  {rootfs_copy_path.name}")
    print(f"    Script:  {MOD_ROOTFS_SCRIPT.name}")
    print(f"    Mount:   {mount_point}")

    try:
        result = subprocess.run(
            ['wsl', '-d', 'Debian', '--', 'sudo', 'bash', '-c', wsl_commands],
            capture_output=False,
            timeout=600,  # 10 minute timeout
        )

        if result.returncode != 0:
            print(f"  ERROR: WSL rootfs modification failed (exit code {result.returncode})")
            # Attempt cleanup in case of failure
            subprocess.run(
                ['wsl', '-d', 'Debian', '--', 'sudo', 'bash', '-c',
                 f'umount {mount_point} 2>/dev/null; rmdir {mount_point} 2>/dev/null; true'],
                capture_output=True, timeout=30
            )
            return False

        print(f"  ✓ Rootfs modified for T1")
        return True

    except subprocess.TimeoutExpired:
        print(f"  ERROR: WSL modification timed out after 600s")
        subprocess.run(
            ['wsl', '-d', 'Debian', '--', 'sudo', 'bash', '-c',
             f'umount {mount_point} 2>/dev/null; rmdir {mount_point} 2>/dev/null; true'],
            capture_output=True, timeout=30
        )
        return False


# ─── Build Phases ─────────────────────────────────────────────────────

def validate_inputs(phase: str):
    """Validate all required input files exist."""
    errors = []

    if not S1_ZIMAGE.exists():
        errors.append(f"S1 zImage not found: {S1_ZIMAGE}")
    if not T1_DTB.exists():
        errors.append(f"T1 DTB not found: {T1_DTB}")
    if not T1_STOCK_FULL.exists():
        errors.append(f"T1 stock full dump not found: {T1_STOCK_FULL}")
    if not T1_STOCK_UBOOT.exists():
        errors.append(f"T1 stock U-Boot dump not found: {T1_STOCK_UBOOT}")
    if not S1_ROOTFS.exists():
        errors.append(f"S1 rootfs.img not found: {S1_ROOTFS}")

    if phase in ('phase2', 'all'):
        if not MOD_ROOTFS_SCRIPT.exists():
            errors.append(f"mod-rootfs-for-t1.sh not found: {MOD_ROOTFS_SCRIPT}")
        if platform.system() != 'Windows':
            errors.append(f"Phase 2 requires Windows with WSL (current: {platform.system()})")
        elif not check_wsl_available():
            errors.append("WSL with Debian not available (required for Phase 2)")

    if errors:
        print("\n  Missing prerequisites:")
        for err in errors:
            print(f"    ✗ {err}")
        sys.exit(1)


def prepare_common_components():
    """Extract bootloader and build boot.img — shared by both phases."""
    print("\n" + "─" * 64)
    print("  Preparing common components")
    print("─" * 64)

    # Extract IDBLoader from stock dump
    idloader = extract_idloader(T1_STOCK_FULL)

    # Extract U-Boot from stock dump
    uboot = extract_uboot(T1_STOCK_UBOOT)

    # Read kernel and DTB
    print(f"\n  Reading S1 kernel zImage...")
    kernel_data = S1_ZIMAGE.read_bytes()
    if len(kernel_data) > 40:
        zimg_magic = struct.unpack_from('<I', kernel_data, 36)[0]
        if zimg_magic == 0x016F2818:
            print(f"    ✓ Valid ARM zImage ({len(kernel_data):,} bytes)")
        else:
            print(f"    WARNING: zImage magic mismatch: 0x{zimg_magic:08X}")

    print(f"  Reading T1 DTB...")
    dtb_data = T1_DTB.read_bytes()
    dtb_magic = struct.unpack_from('>I', dtb_data, 0)[0]
    if dtb_magic != 0xD00DFEED:
        print(f"  ERROR: DTB magic mismatch: 0x{dtb_magic:08X}")
        sys.exit(1)
    print(f"    ✓ Valid FDT ({len(dtb_data):,} bytes)")

    # Build SD-specific boot.img
    print(f"\n  Building SD boot.img (T1 DTB + SD cmdline)...")
    boot_img = build_sd_boot_img(kernel_data, dtb_data)
    print(f"    ✓ boot.img: {len(boot_img):,} bytes ({len(boot_img) / 1024 / 1024:.1f} MB)")
    print(f"    Cmdline: {SD_BOOT_CMDLINE.decode()}")

    return idloader, uboot, boot_img


def build_phase1(idloader, uboot, boot_img, compress=False):
    """Phase 1: Build boot-test SD image with unmodified S1 rootfs."""
    print("\n" + "=" * 64)
    print("  PHASE 1: Building Boot-Test SD Card Image")
    print("  " + PHASE1_IMG_NAME)
    print("=" * 64)
    print()
    print("  This image uses the S1 rootfs unchanged.")
    print("  It boots on T1 with correct display (800×480), but")
    print("  Klipper configs are for S1 hardware (will show errors).")
    print("  Purpose: verify bootloader, display, and SD boot mechanism.")

    output_path = OUTPUT_DIR / PHASE1_IMG_NAME

    assemble_sd_image(
        output_path=output_path,
        boot_img=boot_img,
        idloader=idloader,
        uboot=uboot,
        rootfs_path=S1_ROOTFS,
    )

    if compress:
        compress_image(output_path)

    return output_path


def build_phase2(idloader, uboot, boot_img, compress=False):
    """Phase 2: Build full T1 SD image with modified rootfs."""
    print("\n" + "=" * 64)
    print("  PHASE 2: Building Full T1 SD Card Image")
    print("  " + PHASE2_IMG_NAME)
    print("=" * 64)
    print()
    print("  This image has the S1 rootfs modified for T1 hardware:")
    print("    - T1 Klipper configs (3 MCUs, TMC5160, load cell probe)")
    print("    - T1 systemd services (klipper-mcu, no drying-box)")
    print("    - T1 hostname/branding")
    print("    - First-boot marker for git/pip operations")

    # Copy S1 rootfs to working directory for modification
    working_rootfs = OUTPUT_DIR / "rootfs-t1-working.img"
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print(f"\n  Copying S1 rootfs as base...")
    print(f"    Source: {S1_ROOTFS} ({S1_ROOTFS.stat().st_size / 1024 / 1024 / 1024:.2f} GB)")
    print(f"    Target: {working_rootfs}")

    t_start = time.time()
    shutil.copy2(str(S1_ROOTFS), str(working_rootfs))
    elapsed = time.time() - t_start
    print(f"    ✓ Copied ({elapsed:.0f}s)")

    # Modify rootfs via WSL
    success = modify_rootfs_phase2(working_rootfs)
    if not success:
        print("\n  ERROR: Phase 2 rootfs modification failed.")
        print("  The working rootfs copy has been preserved at:")
        print(f"    {working_rootfs}")
        print("  You can retry modification manually via WSL.")
        sys.exit(1)

    # Assemble SD image with modified rootfs
    output_path = OUTPUT_DIR / PHASE2_IMG_NAME

    assemble_sd_image(
        output_path=output_path,
        boot_img=boot_img,
        idloader=idloader,
        uboot=uboot,
        rootfs_path=working_rootfs,
    )

    # Clean up working rootfs
    print(f"\n  Cleaning up working rootfs copy...")
    working_rootfs.unlink()
    print(f"  ✓ Removed {working_rootfs.name}")

    if compress:
        compress_image(output_path)

    return output_path


# ─── Manifest ─────────────────────────────────────────────────────────

def write_manifest(images: dict):
    """Write JSON manifest describing built SD card images."""
    manifest = {
        "build_tool": "build-sdcard-t1.py",
        "version": VERSION,
        "build_date": BUILD_DATE,
        "platform": platform.platform(),
        "target": "FLSUN T1 SD card (Rockchip RV1109)",
        "base": "FLSUN-OS S1 3.0 (Linux 6.1.99flsun)",
        "bootloader_source": "T1 stock eMMC dump",
        "images": {}
    }

    for name, path in images.items():
        if path and path.exists():
            stat = path.stat()
            manifest["images"][name] = {
                "filename": path.name,
                "size_bytes": stat.st_size,
                "size_mb": round(stat.st_size / 1024 / 1024, 2),
            }

    manifest_path = OUTPUT_DIR / "flsun-os-t1-sdcard-manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2))
    print(f"\n  Manifest: {manifest_path}")


# ─── Main ─────────────────────────────────────────────────────────────

def print_banner():
    print()
    print("╔══════════════════════════════════════════════════════════════╗")
    print("║      FLSUN-OS T1 SD Card Image Builder                     ║")
    print("║  Rockchip RV1109 • T1 Stock Bootloader • Auto-boot SD      ║")
    print("╚══════════════════════════════════════════════════════════════╝")
    print()
    print(f"  Build date:  {BUILD_DATE}")
    print(f"  Version:     {VERSION}")
    print(f"  Platform:    {platform.platform()}")
    print(f"  Output dir:  {OUTPUT_DIR}")


def print_usage():
    print(__doc__)
    print("Arguments:")
    print("  --phase1       Build boot-test SD image (S1 rootfs, T1 display)")
    print("  --phase2       Build full T1 SD image (modified rootfs, needs WSL)")
    print("  --all          Build both Phase 1 and Phase 2 images")
    print("  --compress     Compress output with gzip (.img.gz)")
    print("  --help, -h     Show this help message")


def main():
    build_phases = set()
    compress = False

    for arg in sys.argv[1:]:
        if arg == '--phase1':
            build_phases.add('phase1')
        elif arg == '--phase2':
            build_phases.add('phase2')
        elif arg in ('--all', '-a'):
            build_phases = {'phase1', 'phase2'}
        elif arg == '--compress':
            compress = True
        elif arg in ('--help', '-h'):
            print_usage()
            sys.exit(0)
        else:
            print(f"Unknown argument: {arg}")
            print_usage()
            sys.exit(1)

    if not build_phases:
        print_usage()
        sys.exit(1)

    print_banner()

    # Determine validation scope
    validation_scope = 'all' if 'phase2' in build_phases else 'phase1'
    validate_inputs(validation_scope)

    # Prepare shared components (bootloader, boot.img)
    idloader, uboot, boot_img = prepare_common_components()

    images = {}

    if 'phase1' in build_phases:
        images['phase1'] = build_phase1(idloader, uboot, boot_img, compress)

    if 'phase2' in build_phases:
        images['phase2'] = build_phase2(idloader, uboot, boot_img, compress)

    # Write manifest
    write_manifest(images)

    # Final summary
    print("\n" + "=" * 64)
    print("  BUILD COMPLETE")
    print("=" * 64)
    print()
    for name, path in images.items():
        if path and path.exists():
            sz = path.stat().st_size
            print(f"  ✓ {path.name:45s} {sz / 1024 / 1024 / 1024:>6.2f} GB")
            # Also show compressed file if it exists
            gz = path.parent / (path.name + ".gz")
            if gz.exists():
                gsz = gz.stat().st_size
                print(f"  ✓ {gz.name:45s} {gsz / 1024 / 1024:>6.0f} MB")

    print()
    print("  To write to SD card:")
    print("    Use Raspberry Pi Imager, balenaEtcher, or dd:")
    print("    dd if=FLSUN-OS-T1-SD.img of=/dev/sdX bs=4M status=progress")
    print()
    print("  Recommended SD card: ≥ 16 GB (≥ 8 GB minimum)")
    print()

    if 'phase2' in images:
        print("  NOTE: After first boot from SD, complete T1 setup by running:")
        print("    cat ~/.t1-klipper-switch-pending")
        print("  This switches Klipper/KlipperScreen forks and installs SciPy.")
        print()


if __name__ == '__main__':
    main()
