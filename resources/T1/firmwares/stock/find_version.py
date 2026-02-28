#!/usr/bin/env python3
"""Find kernel version and analyze resource DTBs"""
import struct
import os
import lzma

base = r'c:\Users\Layer\Documents\FLSUN-OS\resources\T1\firmwares\stock\extracted'

# 1. Try to find kernel version using multiple approaches
kernel_path = os.path.join(base, 'kernel.bin')
with open(kernel_path, 'rb') as f:
    kdata = f.read()

print(f'=== Kernel Version Search ({len(kdata)} bytes) ===\n')

# ARM zImage: header at offset 0-64
# The decompression stub is at the beginning, followed by compressed kernel
# Let's look for compression signatures
patterns = {
    b'\x1f\x8b\x08': 'gzip',
    b'\xfd\x37\x7a\x58\x5a\x00': 'xz',
    b'\x5d\x00\x00': 'lzma',
    b'\x02\x21\x4c\x18': 'lz4',
    b'\x04\x22\x4d\x18': 'lz4-frame',
    b'\x89\x4c\x5a\x4f': 'lzo',
    b'BZh': 'bzip2',
    b'\x28\xb5\x2f\xfd': 'zstd',
}

print('Searching for compression signatures...')
for sig, name in patterns.items():
    pos = 0
    found = []
    while pos < len(kdata):
        idx = kdata.find(sig, pos)
        if idx < 0:
            break
        found.append(idx)
        pos = idx + 1
        if len(found) > 5:
            break
    if found:
        offsets = ', '.join(f'0x{x:X}' for x in found[:5])
        print(f'  {name}: found at {offsets}')

# Try LZMA decompression
lzma_pos = kdata.find(b'\x5d\x00\x00')
if lzma_pos >= 0:
    print(f'\nTrying LZMA decompression from offset 0x{lzma_pos:X}...')
    try:
        # ARM zImage LZMA: the data after the decompression stub
        decomp = lzma.decompress(kdata[lzma_pos:], format=lzma.FORMAT_ALONE)
        print(f'LZMA decompressed: {len(decomp)} bytes')
        pos = decomp.find(b'Linux version ')
        if pos >= 0:
            end = decomp.find(b'\x00', pos)
            ver = decomp[pos:min(end, pos+200)].decode('ascii', errors='replace')
            print(f'*** KERNEL VERSION: {ver}')
            # Save
            with open(os.path.join(base, 'vmlinux-decompressed.bin'), 'wb') as f:
                f.write(decomp)
            print(f'Saved vmlinux ({len(decomp)} bytes)')
    except Exception as e:
        print(f'LZMA failed: {e}')

# Try XZ 
xz_pos = kdata.find(b'\xfd\x37\x7a\x58\x5a\x00')
if xz_pos >= 0:
    print(f'\nTrying XZ decompression from offset 0x{xz_pos:X}...')
    try:
        decomp = lzma.decompress(kdata[xz_pos:], format=lzma.FORMAT_XZ)
        print(f'XZ decompressed: {len(decomp)} bytes')
        pos = decomp.find(b'Linux version ')
        if pos >= 0:
            end = decomp.find(b'\x00', pos)
            ver = decomp[pos:min(end, pos+200)].decode('ascii', errors='replace')
            print(f'*** KERNEL VERSION: {ver}')
            with open(os.path.join(base, 'vmlinux-decompressed.bin'), 'wb') as f:
                f.write(decomp)
    except Exception as e:
        print(f'XZ failed: {e}')

# Try gzip at all found positions
import gzip
gzip_positions = []
pos = 0
while pos < len(kdata):
    idx = kdata.find(b'\x1f\x8b\x08', pos)
    if idx < 0:
        break
    gzip_positions.append(idx)
    pos = idx + 1

for gpos in gzip_positions:
    try:
        decomp = gzip.decompress(kdata[gpos:])
        print(f'\ngzip at 0x{gpos:X}: decompressed {len(decomp)} bytes')
        pos = decomp.find(b'Linux version ')
        if pos >= 0:
            end = decomp.find(b'\x00', pos)
            ver = decomp[pos:min(end, pos+200)].decode('ascii', errors='replace')
            print(f'*** KERNEL VERSION: {ver}')
            with open(os.path.join(base, 'vmlinux-decompressed.bin'), 'wb') as f:
                f.write(decomp)
            break
    except:
        pass

# Direct search for version-like strings in raw kernel
print('\nDirect search for version strings...')
for pattern in [b'Linux version ', b'vermagic=', b'#1 SMP', b'#1 PREEMPT', b'armv7l']:
    pos = kdata.find(pattern)
    if pos >= 0:
        # Get surrounding context
        start = max(0, pos - 40)
        end = min(len(kdata), pos + 200)
        context = kdata[pos:end]
        null_end = context.find(b'\x00')
        if null_end > 0:
            context = context[:null_end]
        try:
            text = context.decode('ascii', errors='replace')
            print(f'  "{pattern.decode()}" at 0x{pos:X}: {text}')
        except:
            pass

# 2. Check resource DTBs
print('\n=== Resource DTBs ===\n')

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

def get_root_props(data):
    """Get root node properties from DTB"""
    header = parse_fdt_header(data)
    if not header:
        return {}
    
    FDT_BEGIN_NODE = 1
    FDT_PROP = 3
    FDT_END_NODE = 2
    
    off = header['off_dt_struct']
    strings_off = header['off_dt_strings']
    
    props = {}
    depth = 0
    in_root = False
    
    while off < len(data):
        token = struct.unpack_from('>I', data, off)[0]
        off += 4
        
        if token == FDT_BEGIN_NODE:
            name_end = data.find(b'\x00', off)
            name = data[off:name_end].decode('ascii', errors='replace')
            off = (name_end + 4) & ~3
            depth += 1
            if depth == 1 and name == '':
                in_root = True
        elif token == FDT_END_NODE:
            if depth == 1:
                in_root = False
            depth -= 1
        elif token == FDT_PROP:
            prop_len = struct.unpack_from('>I', data, off)[0]
            prop_nameoff = struct.unpack_from('>I', data, off + 4)[0]
            off += 8
            if in_root and depth == 1:
                prop_name = get_string(data, strings_off, prop_nameoff)
                prop_data = data[off:off + prop_len]
                props[prop_name] = prop_data
            off = (off + prop_len + 3) & ~3
        elif token == 0x00000009:  # FDT_END
            break
    
    return props

for i in range(2):
    dtb_file = os.path.join(base, f'resource-dtb-{i}.dtb')
    if not os.path.exists(dtb_file):
        continue
    with open(dtb_file, 'rb') as f:
        dtb_data = f.read()
    
    props = get_root_props(dtb_data)
    model = props.get('model', b'').rstrip(b'\x00').decode('ascii', errors='replace')
    compatibles = [c.decode('ascii', errors='replace') for c in props.get('compatible', b'').split(b'\x00') if c]
    
    print(f'Resource DTB {i}: {len(dtb_data)} bytes')
    print(f'  Model: {model}')
    print(f'  Compatible: {", ".join(compatibles)}')
    print()

# 3. Analyze RSCE resource image structure
print('=== RSCE Resource Image Structure ===\n')
boot_path = os.path.join(base, 'p3-boot.img')
with open(boot_path, 'rb') as f:
    boot_data = f.read()

rsce_data = boot_data[0x6F9000:0x6F9000 + 973312]
# RSCE header: https://github.com/nicman23/rkflashtool/blob/master/rkunpack.c
# Magic "RSCE", then entry table
print(f'RSCE Magic: {rsce_data[:4]}')
print(f'  Header bytes 4-32: {rsce_data[4:32].hex(" ")}')

# Try to parse RSCE entry table
# Rockchip resource format:
# 0x00: magic "RSCE" (4 bytes)
# 0x04: version (2 bytes LE)  
# 0x06: reserved (2 bytes)
# 0x08: entry count (2 bytes LE)
# 0x0A: ? 
# 0x0C: ... entries after header

version = struct.unpack_from('<H', rsce_data, 4)[0]
print(f'  RSCE version: {version}')

# The entry table usually starts after a fixed header
# Look for file names in the RSCE
print('\nSearching for file entries in RSCE...')
# Common resource files: logo.bmp, logo_kernel.bmp, *.dtb
for pattern in [b'.bmp', b'.dtb', b'.bin', b'.png', b'.cfg']:
    pos = 0
    while pos < min(len(rsce_data), 0x2000):
        idx = rsce_data.find(pattern, pos)
        if idx < 0 or idx >= 0x2000:
            break
        # Get the filename by searching backwards for printable start
        start = idx
        while start > 0 and 32 <= rsce_data[start-1] <= 126:
            start -= 1
        name = rsce_data[start:idx+len(pattern)].decode('ascii', errors='replace')
        print(f'  Found: "{name}" at offset 0x{start:X}')
        pos = idx + 1
