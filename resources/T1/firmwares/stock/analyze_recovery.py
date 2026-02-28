#!/usr/bin/env python3
"""Analyze T1 recovery partition and extract rootfs metadata"""
import struct
import gzip
import os

base = r'c:\Users\Layer\Documents\FLSUN-OS\resources\T1\firmwares\stock\extracted'

# 1. Analyze recovery partition (also FIT image)
print('=== Recovery Partition (p4) Analysis ===\n')
recovery_path = os.path.join(base, 'p4-recovery.img')
with open(recovery_path, 'rb') as f:
    rdata = f.read()

print(f'Size: {len(rdata)} bytes ({len(rdata)/1024/1024:.1f} MB)')

def parse_fdt_header(data, offset=0):
    magic = struct.unpack_from('>I', data, offset)[0]
    if magic != 0xd00dfeed:
        return None
    return {
        'totalsize': struct.unpack_from('>I', data, offset + 4)[0],
        'off_dt_struct': struct.unpack_from('>I', data, offset + 8)[0],
        'off_dt_strings': struct.unpack_from('>I', data, offset + 12)[0],
        'version': struct.unpack_from('>I', data, offset + 20)[0],
        'size_dt_strings': struct.unpack_from('>I', data, offset + 32)[0],
        'size_dt_struct': struct.unpack_from('>I', data, offset + 36)[0],
    }

def get_string(data, strings_offset, str_offset):
    start = strings_offset + str_offset
    end = data.find(b'\x00', start)
    return data[start:end].decode('ascii', errors='replace')

def parse_fit_nodes(data, header, base_offset=0):
    FDT_BEGIN_NODE = 1
    FDT_END_NODE = 2
    FDT_PROP = 3
    FDT_NOP = 4
    FDT_END = 9
    
    off = base_offset + header['off_dt_struct']
    strings_off = base_offset + header['off_dt_strings']
    end = off + header['size_dt_struct']
    
    path = []
    nodes = {}
    current_props = {}
    
    while off < end:
        token = struct.unpack_from('>I', data, off)[0]
        off += 4
        if token == FDT_BEGIN_NODE:
            name_end = data.find(b'\x00', off)
            name = data[off:name_end].decode('ascii', errors='replace')
            off = (name_end + 4) & ~3
            path.append(name)
            current_props = {}
            nodes['/'.join(path)] = current_props
        elif token == FDT_END_NODE:
            if path: path.pop()
        elif token == FDT_PROP:
            prop_len = struct.unpack_from('>I', data, off)[0]
            prop_nameoff = struct.unpack_from('>I', data, off + 4)[0]
            off += 8
            prop_name = get_string(data, strings_off, prop_nameoff)
            prop_data = data[off:off + prop_len]
            off = (off + prop_len + 3) & ~3
            current_props[prop_name] = prop_data
        elif token == FDT_NOP:
            pass
        elif token == FDT_END:
            break
    return nodes

header = parse_fdt_header(rdata, 0)
if header:
    print(f'FIT Total size: {header["totalsize"]} bytes')
    nodes = parse_fit_nodes(rdata, header, 0)
    
    for path, props in sorted(nodes.items()):
        desc = props.get('description', b'').rstrip(b'\x00').decode('ascii', errors='replace')
        type_prop = props.get('type', b'').rstrip(b'\x00').decode('ascii', errors='replace')
        comp = props.get('compression', b'').rstrip(b'\x00').decode('ascii', errors='replace')
        data_pos = props.get('data-position', None)
        data_size = props.get('data-size', None)
        inline_data = props.get('data', None)
        
        size_info = ''
        if inline_data:
            size_info = f' [{len(inline_data)} bytes inline]'
        elif data_pos and data_size:
            p = struct.unpack_from('>I', data_pos, 0)[0]
            s = struct.unpack_from('>I', data_size, 0)[0]
            size_info = f' [at 0x{p:X}, {s} bytes ({s/1024/1024:.2f} MB)]'
        
        extra = ''
        if desc: extra += f' desc="{desc}"'
        if type_prop: extra += f' type={type_prop}'
        if comp: extra += f' comp={comp}'
        
        print(f'  /{path}{size_info}{extra}')

# 2. Try to extract first few MB of rootfs to identify filesystem
print('\n=== Rootfs Analysis (first 1MB of compressed) ===\n')
rootfs_gz = os.path.join(base, '..', '1097_0p6.img')
if os.path.exists(rootfs_gz):
    print(f'Rootfs gz: {os.path.getsize(rootfs_gz)} bytes ({os.path.getsize(rootfs_gz)/1024/1024:.1f} MB)')
    
    # Read just the first bit and decompress what we can
    with gzip.open(rootfs_gz, 'rb') as f:
        # Read first 1MB to identify filesystem
        first_mb = f.read(1024 * 1024)
    
    print(f'First 1MB decompressed OK')
    
    # Check filesystem type
    # ext4 superblock at offset 0x400 (1024 bytes)
    if len(first_mb) > 0x470:
        magic = struct.unpack_from('<H', first_mb, 0x438)[0]
        if magic == 0xEF53:
            print(f'Filesystem: ext4 (magic 0x{magic:04X})')
            
            # Parse superblock
            s_inodes_count = struct.unpack_from('<I', first_mb, 0x400)[0]
            s_blocks_count = struct.unpack_from('<I', first_mb, 0x404)[0]
            s_log_block_size = struct.unpack_from('<I', first_mb, 0x418)[0]
            block_size = 1024 << s_log_block_size
            s_blocks_count_hi = struct.unpack_from('<I', first_mb, 0x450)[0]
            total_blocks = s_blocks_count | (s_blocks_count_hi << 32)
            total_size = total_blocks * block_size
            
            # Volume name at offset 0x478
            vol_name = first_mb[0x478:0x478+16].rstrip(b'\x00').decode('ascii', errors='replace')
            
            # UUID at 0x468
            uuid_bytes = first_mb[0x468:0x468+16]
            uuid_str = f'{uuid_bytes[0:4].hex()}-{uuid_bytes[4:6].hex()}-{uuid_bytes[6:8].hex()}-{uuid_bytes[8:10].hex()}-{uuid_bytes[10:16].hex()}'
            
            # Created time at 0x42C
            import datetime
            mkfs_time = struct.unpack_from('<I', first_mb, 0x42C)[0]
            if mkfs_time > 0:
                created = datetime.datetime.fromtimestamp(mkfs_time)
            
            # OS creator at 0x472
            os_creator = struct.unpack_from('<I', first_mb, 0x448)[0]
            os_names = {0: 'Linux', 1: 'HURD', 2: 'MASIX', 3: 'FreeBSD', 4: 'Lites'}
            
            print(f'  Block size: {block_size} bytes')
            print(f'  Total blocks: {total_blocks}')
            print(f'  Total size: {total_size / 1024 / 1024 / 1024:.2f} GB')
            print(f'  Inodes: {s_inodes_count}')
            print(f'  Volume name: "{vol_name}"')
            print(f'  UUID: {uuid_str}')
            if mkfs_time > 0:
                print(f'  Created: {created}')
            print(f'  OS: {os_names.get(os_creator, f"unknown ({os_creator})")}')
        else:
            print(f'Filesystem magic: 0x{magic:04X} (not ext4)')
    
    # Try to extract more filesystem metadata by reading deeper
    # Read 64MB to scan for interesting strings
    print('\nScanning rootfs for metadata (reading first 64MB)...')
    with gzip.open(rootfs_gz, 'rb') as f:
        big_chunk = f.read(64 * 1024 * 1024)
    
    print(f'Read {len(big_chunk)} bytes ({len(big_chunk)/1024/1024:.1f} MB)')
    
    # Search for interesting patterns
    patterns_to_find = [
        (b'PRETTY_NAME=', 'OS Name'),
        (b'VERSION_ID=', 'Version'),
        (b'ID=', 'Distribution'),
        (b'Linux version ', 'Kernel version'),
        (b'klipperscreen', 'KlipperScreen'),
        (b'KlipperScreen', 'KlipperScreen'),
        (b'klipper', 'Klipper'),
        (b'moonraker', 'Moonraker'),
        (b'fluidd', 'Fluidd'),
        (b'mainsail', 'Mainsail'),
        (b'python3.', 'Python version'),
    ]
    
    for pattern, label in patterns_to_find:
        pos = big_chunk.find(pattern)
        if pos >= 0:
            # Get context
            end = big_chunk.find(b'\n', pos)
            if end < 0 or end - pos > 200:
                end = pos + 200
            context = big_chunk[pos:end]
            try:
                text = context.decode('ascii', errors='replace')
                print(f'  [{label}] at 0x{pos:X}: {text.strip()}')
            except:
                pass

else:
    print('Rootfs gz not found')

# 3. Summary of partition layout
print('\n=== T1 Stock Firmware Partition Summary ===\n')
partitions = [
    ('1097_0boot0.img', 'emmc-boot0', 'Empty (all zeros)'),
    ('1097_0boot1.img', 'emmc-boot1', 'Empty (all zeros)'),
    ('1097_0p1.img', 'uboot', 'U-Boot FIT (U-Boot + OP-TEE + DTB)'),
    ('1097_0p2.img', 'misc', 'Empty (all zeros)'),
    ('1097_0p3.img', 'boot', 'FIT image (kernel + DTB + resources)'),
    ('1097_0p4.img', 'recovery', 'FIT recovery image'),
    ('1097_0p5.img', 'backup', 'Empty (all zeros)'),
    ('1097_0p6.img', 'rootfs', 'ext4 filesystem'),
    ('1097_0.img', 'full-disk', 'Complete eMMC dump'),
]

for fname, name, desc in partitions:
    fpath = os.path.join(base, '..', fname)
    if os.path.exists(fpath):
        gz_size = os.path.getsize(fpath)
        extracted = os.path.join(base, f'{fname.replace("1097_0", "").replace(".img", "")}.img')
        raw_size = '?'
        if os.path.exists(extracted):
            raw_size = f'{os.path.getsize(extracted)/1024/1024:.1f} MB'
        print(f'  {name:12s}  gz={gz_size/1024/1024:.2f} MB  raw={raw_size:>10s}  {desc}')
