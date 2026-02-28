#!/usr/bin/env python3
"""Analyze T1 stock boot.img partition"""
import struct
import os

base = r'c:\Users\Layer\Documents\FLSUN-OS\resources\T1\firmwares\stock\extracted'

with open(os.path.join(base, 'p3-boot.img'), 'rb') as f:
    data = f.read()

print(f'p3-boot.img size: {len(data)} bytes ({len(data)/1024/1024:.2f} MB)')
print()

# Check for ANDROID! magic
magic = data[:8]
print(f'Magic at offset 0: {magic} ({" ".join(f"{b:02X}" for b in magic)})')

if magic == b'ANDROID!':
    print('=> Android Boot Image format detected!')
    kernel_size = struct.unpack_from('<I', data, 8)[0]
    kernel_addr = struct.unpack_from('<I', data, 12)[0]
    ramdisk_size = struct.unpack_from('<I', data, 16)[0]
    ramdisk_addr = struct.unpack_from('<I', data, 20)[0]
    second_size = struct.unpack_from('<I', data, 24)[0]
    second_addr = struct.unpack_from('<I', data, 28)[0]
    tags_addr = struct.unpack_from('<I', data, 32)[0]
    page_size = struct.unpack_from('<I', data, 36)[0]
    header_version = struct.unpack_from('<I', data, 40)[0]
    os_version = struct.unpack_from('<I', data, 44)[0]
    name = data[48:64].split(b'\x00')[0].decode('ascii', errors='replace')
    cmdline = data[64:576].split(b'\x00')[0].decode('ascii', errors='replace')
    
    print(f'  Header version: {header_version}')
    print(f'  Page size: {page_size}')
    print(f'  Kernel size: {kernel_size} ({kernel_size/1024/1024:.2f} MB)')
    print(f'  Kernel load addr: 0x{kernel_addr:08X}')
    print(f'  Ramdisk size: {ramdisk_size}')
    print(f'  Ramdisk load addr: 0x{ramdisk_addr:08X}')
    print(f'  Second stage size: {second_size} ({second_size/1024:.1f} KB)')
    print(f'  Second stage addr: 0x{second_addr:08X}')
    print(f'  Tags addr: 0x{tags_addr:08X}')
    print(f'  OS version: 0x{os_version:08X}')
    print(f'  Name: "{name}"')
    print(f'  Cmdline: "{cmdline}"')
    
    # Calculate offsets
    kernel_offset = page_size
    kernel_pages = (kernel_size + page_size - 1) // page_size
    ramdisk_offset = kernel_offset + kernel_pages * page_size
    ramdisk_pages = (ramdisk_size + page_size - 1) // page_size
    second_offset = ramdisk_offset + ramdisk_pages * page_size
    
    print(f'\n  Kernel at offset: 0x{kernel_offset:X} ({kernel_offset})')
    print(f'  Second stage at offset: 0x{second_offset:X} ({second_offset})')
    
    # Check kernel magic
    kernel_start = data[kernel_offset:kernel_offset+64]
    print(f'\n  Kernel header: {" ".join(f"{b:02X}" for b in kernel_start[:16])}')
    if len(kernel_start) >= 40:
        zimage_magic = struct.unpack_from('<I', kernel_start, 36)[0]
        print(f'  zImage magic at +36: 0x{zimage_magic:08X} (expected 0x016F2818)')
    
    # Check second stage for RSCE magic
    if second_size > 0:
        second_start = data[second_offset:second_offset+16]
        second_magic = second_start[:4]
        print(f'\n  Second stage header: {" ".join(f"{b:02X}" for b in second_start[:16])}')
        print(f'  Second stage magic: {second_magic} ({second_magic.decode("ascii", errors="replace")})')
        
        # Parse RSCE resource image
        if second_magic == b'RSCE':
            print('\n  => Rockchip Resource Image (RSCE) found!')
            rsce_data = data[second_offset:second_offset + second_size]
            # RSCE header: 4 magic, 2 version, 2 entry_count, 4 block_size, ...
            # Entry table starts at offset 512
            entry_count = struct.unpack_from('<H', rsce_data, 6)[0]
            print(f'  Entry count: {entry_count}')
            
            for i in range(entry_count):
                entry_offset = 512 + i * 512
                entry_tag = rsce_data[entry_offset:entry_offset+4]
                entry_name = rsce_data[entry_offset+4:entry_offset+260].split(b'\x00')[0].decode('ascii', errors='replace')
                entry_data_offset = struct.unpack_from('<I', rsce_data, entry_offset+260)[0] * 512
                entry_data_size = struct.unpack_from('<I', rsce_data, entry_offset+264)[0]
                print(f'  Entry {i}: tag={entry_tag}, name="{entry_name}", offset={entry_data_offset}, size={entry_data_size}')
                
                # Extract DTB files
                if entry_name.endswith('.dtb'):
                    dtb_data = rsce_data[entry_data_offset:entry_data_offset + entry_data_size]
                    dtb_path = os.path.join(base, entry_name)
                    with open(dtb_path, 'wb') as df:
                        df.write(dtb_data)
                    print(f'    => Extracted to {dtb_path}')
                    
                    # Check FDT magic
                    if dtb_data[:4] == b'\xd0\x0d\xfe\xed':
                        print(f'    => Valid FDT (Flattened Device Tree)')
                        fdt_size = struct.unpack_from('>I', dtb_data, 4)[0]
                        print(f'    => FDT total size: {fdt_size} bytes')
    
    # Save the kernel (zImage) 
    kernel_data = data[kernel_offset:kernel_offset + kernel_size]
    kernel_path = os.path.join(base, 'zImage')
    with open(kernel_path, 'wb') as kf:
        kf.write(kernel_data)
    print(f'\n  Kernel saved to {kernel_path} ({len(kernel_data)} bytes)')
    
    # Search for kernel version string
    # Look for "Linux version" in the kernel data
    for pattern in [b'Linux version ', b'vermagic=']:
        pos = 0
        while True:
            pos = kernel_data.find(pattern, pos)
            if pos < 0:
                break
            end = kernel_data.find(b'\x00', pos)
            if end < 0:
                end = pos + 200
            version_str = kernel_data[pos:min(end, pos+200)].decode('ascii', errors='replace')
            print(f'  Version string at kernel+0x{pos:X}: {version_str[:120]}')
            break

else:
    print('No ANDROID! magic at offset 0')
    # Search for it
    pos = data.find(b'ANDROID!')
    if pos >= 0:
        print(f'Found ANDROID! at offset {pos} (0x{pos:X})')
    
    # Search for FDT magic
    pos = 0
    while True:
        pos = data.find(b'\xd0\x0d\xfe\xed', pos)
        if pos < 0:
            break
        fdt_size = struct.unpack_from('>I', data, pos + 4)[0]
        print(f'Found FDT at offset {pos} (0x{pos:X}), size={fdt_size}')
        pos += 4

print('\n=== Analyzing other partitions ===\n')

# Check p1-uboot
for pname, label in [('p1-uboot.img', 'uboot'), ('p2-misc.img', 'misc'), 
                      ('p4-recovery.img', 'recovery'), ('p5-backup.img', 'backup')]:
    path = os.path.join(base, pname)
    if not os.path.exists(path):
        continue
    with open(path, 'rb') as f:
        pdata = f.read(64)
    psize = os.path.getsize(path)
    hex_str = ' '.join(f'{b:02X}' for b in pdata[:16])
    ascii_str = ''.join(chr(b) if 32 <= b <= 126 else '.' for b in pdata[:16])
    print(f'{label} ({psize/1024/1024:.2f} MB): {hex_str} | {ascii_str}')
    
    # Check for known signatures
    if pdata[:8] == b'ANDROID!':
        print(f'  => Android boot image')
    elif pdata[:4] == b'\xd0\x0d\xfe\xed':
        print(f'  => FDT/DTB')
    elif pdata[:4] == b'RSCE':
        print(f'  => Rockchip Resource Image')

# Check emmc boot partitions
for pname in ['emmc-boot0.img', 'emmc-boot1.img']:
    path = os.path.join(base, pname)
    if not os.path.exists(path):
        continue
    with open(path, 'rb') as f:
        pdata = f.read()
    # Check if it's all zeros
    nonzero = sum(1 for b in pdata if b != 0)
    print(f'{pname} ({len(pdata)} bytes): {nonzero} non-zero bytes')
