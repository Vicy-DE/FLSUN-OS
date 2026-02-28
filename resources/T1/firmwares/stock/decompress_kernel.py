#!/usr/bin/env python3
"""Decompress LZ4-compressed kernel from T1 zImage"""
import struct
import os
import lz4.frame
import lz4.block

base = r'c:\Users\Layer\Documents\FLSUN-OS\resources\T1\firmwares\stock\extracted'
kernel_path = os.path.join(base, 'kernel.bin')

with open(kernel_path, 'rb') as f:
    kdata = f.read()

print(f'Kernel binary: {len(kdata)} bytes')

# ARM zImage header analysis
magic = struct.unpack_from('<I', kdata, 36)[0]
print(f'zImage magic: 0x{magic:08X} (expected 0x016F2818)')

# Look for LZ4 frame magic
lz4_magic = b'\x04\x22\x4d\x18'  # LZ4 frame
pos = kdata.find(lz4_magic)
if pos >= 0:
    print(f'\nFound LZ4 frame magic at offset 0x{pos:X}')
    try:
        decomp = lz4.frame.decompress(kdata[pos:])
        print(f'LZ4 frame decompressed: {len(decomp)} bytes ({len(decomp)/1024/1024:.1f} MB)')
        
        # Search for version
        ver_pos = decomp.find(b'Linux version ')
        if ver_pos >= 0:
            end = decomp.find(b'\x00', ver_pos)
            ver = decomp[ver_pos:min(end, ver_pos+200)].decode('ascii', errors='replace')
            print(f'\n*** KERNEL VERSION: {ver}')
        
        # Save
        out = os.path.join(base, 'vmlinux-decompressed.bin')
        with open(out, 'wb') as f:
            f.write(decomp)
        print(f'Saved to {out}')
    except Exception as e:
        print(f'LZ4 frame decompression failed: {e}')

# Also try LZ4 legacy/block format
lz4_legacy = b'\x02\x21\x4c\x18'
pos = kdata.find(lz4_legacy)
if pos >= 0:
    print(f'\nFound LZ4 legacy magic at offset 0x{pos:X}')
    # LZ4 legacy format: magic (4) + block_size (4, LE) + compressed data
    # Blocks repeat until no more data
    try:
        offset = pos + 4
        decompressed_chunks = []
        while offset < len(kdata):
            if offset + 4 > len(kdata):
                break
            block_size = struct.unpack_from('<I', kdata, offset)[0]
            if block_size == 0 or block_size > 16*1024*1024:
                break
            offset += 4
            block_data = kdata[offset:offset + block_size]
            try:
                chunk = lz4.block.decompress(block_data, uncompressed_size=8*1024*1024)
                decompressed_chunks.append(chunk)
            except:
                break
            offset += block_size
        
        if decompressed_chunks:
            decomp = b''.join(decompressed_chunks)
            print(f'LZ4 legacy decompressed: {len(decomp)} bytes ({len(decomp)/1024/1024:.1f} MB)')
            
            ver_pos = decomp.find(b'Linux version ')
            if ver_pos >= 0:
                end = decomp.find(b'\x00', ver_pos)
                ver = decomp[ver_pos:min(end, ver_pos+200)].decode('ascii', errors='replace')
                print(f'\n*** KERNEL VERSION: {ver}')
            
            out = os.path.join(base, 'vmlinux-decompressed.bin')
            with open(out, 'wb') as f:
                f.write(decomp)
            print(f'Saved to {out}')
    except Exception as e:
        print(f'LZ4 legacy decompression failed: {e}')

# Also try all LZ4-like positions for raw block decompression
print('\nTrying raw LZ4 block decompression at suspicious offsets...')
# The zImage decompression stub is small (~5KB), after that is compressed data
for start_offset in [0x3EFC, 0x1304, 0x4000, 0x5000, 0x6000, 0x8000]:
    try:
        # Try with various uncompressed sizes
        for usize in [8*1024*1024, 16*1024*1024, 20*1024*1024]:
            try:
                decomp = lz4.block.decompress(kdata[start_offset:], uncompressed_size=usize)
                if len(decomp) > 100000:
                    print(f'  Offset 0x{start_offset:X}: decompressed {len(decomp)} bytes')
                    ver_pos = decomp.find(b'Linux version ')
                    if ver_pos >= 0:
                        end = decomp.find(b'\x00', ver_pos)
                        ver = decomp[ver_pos:min(end, ver_pos+200)].decode('ascii', errors='replace')
                        print(f'  *** KERNEL VERSION: {ver}')
                        out = os.path.join(base, 'vmlinux-decompressed.bin')
                        with open(out, 'wb') as f:
                            f.write(decomp)
                    break
            except:
                continue
    except:
        pass

# Fallback: search for common kernel version patterns in raw binary
print('\nSearching for kernel version patterns in raw binary...')
for pattern in [b'4.4.', b'4.19.', b'5.4.', b'5.10.', b'5.15.', b'6.1.', b'6.6.']:
    pos = 0
    while pos < len(kdata):
        idx = kdata.find(pattern, pos)
        if idx < 0:
            break
        # Check context - look for surrounding printable chars
        start = max(0, idx - 10)
        end = min(len(kdata), idx + 40)
        context = kdata[start:end]
        # Check if it looks like a version string
        printable = all(32 <= b <= 126 or b == 0 for b in context)
        if printable or True:
            text = context.decode('ascii', errors='.')
            print(f'  Found "{pattern.decode()}" at 0x{idx:X}: ...{text}...')
        pos = idx + 1
        if pos - idx > 5:
            break
