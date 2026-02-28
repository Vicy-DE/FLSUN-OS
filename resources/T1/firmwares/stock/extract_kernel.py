#!/usr/bin/env python3
"""Extract kernel version from T1 zImage and decompile DTB"""
import struct
import gzip
import os
import subprocess

base = r'c:\Users\Layer\Documents\FLSUN-OS\resources\T1\firmwares\stock\extracted'

# 1. Analyze kernel binary
kernel_path = os.path.join(base, 'kernel.bin')
with open(kernel_path, 'rb') as f:
    kdata = f.read()

print(f'=== Kernel Analysis ({len(kdata)} bytes) ===\n')

# Check if it's a zImage (ARM)
# ARM zImage header: 0x016F2818 at offset 36
if len(kdata) > 40:
    magic = struct.unpack_from('<I', kdata, 36)[0]
    if magic == 0x016F2818:
        print('Kernel is ARM zImage format')
        start = struct.unpack_from('<I', kdata, 40)[0]
        end = struct.unpack_from('<I', kdata, 44)[0]
        print(f'  zImage start: 0x{start:08X}')
        print(f'  zImage end: 0x{end:08X}')
        print(f'  Estimated decompressed: 0x{end-start:X} ({(end-start)/1024/1024:.1f} MB)')

# Search for embedded gzip streams
print('\nSearching for gzip streams in kernel...')
found_version = False
for i in range(0, min(len(kdata), len(kdata)), 1):
    if kdata[i:i+2] == b'\x1f\x8b' and kdata[i+2] == 0x08:
        try:
            decompressed = gzip.decompress(kdata[i:])
            print(f'  gzip at offset 0x{i:X}: {len(decompressed)} bytes decompressed')
            
            # Look for version string
            pos = decompressed.find(b'Linux version ')
            if pos >= 0:
                end = decompressed.find(b'\x00', pos)
                ver = decompressed[pos:min(end, pos+200)].decode('ascii', errors='replace')
                print(f'  *** KERNEL VERSION: {ver}')
                found_version = True
                
                # Save decompressed kernel
                out = os.path.join(base, 'vmlinux-decompressed.bin')
                with open(out, 'wb') as f:
                    f.write(decompressed)
                print(f'  Saved decompressed kernel: {len(decompressed)} bytes')
            break
        except Exception as e:
            # Partial gzip, skip
            continue

if not found_version:
    # Direct search in raw data
    pos = kdata.find(b'Linux version ')
    if pos >= 0:
        end = kdata.find(b'\x00', pos)
        ver = kdata[pos:min(end, pos+200)].decode('ascii', errors='replace')
        print(f'  KERNEL VERSION (direct): {ver}')
    else:
        # Search for banner string
        for pattern in [b'Linux version', b'vermagic=', b'#1 SMP', b'#1 PREEMPT']:
            pos = kdata.find(pattern)
            if pos >= 0:
                context = kdata[max(0,pos-20):pos+200]
                # Find null terminators
                start_null = context.rfind(b'\x00', 0, 20)
                if start_null >= 0:
                    context = context[start_null+1:]
                end_null = context.find(b'\x00')
                if end_null >= 0:
                    context = context[:end_null]
                print(f'  Found "{pattern.decode()}" at offset 0x{pos:X}:')
                print(f'    {context.decode("ascii", errors="replace")}')
                break

# 2. Analyze the resource image
print('\n=== Resource Image Analysis ===\n')
resource_path = os.path.join(base, '..', 'parse_fit.py')

# Re-read boot.img to extract resource image
boot_path = os.path.join(base, 'p3-boot.img')
with open(boot_path, 'rb') as f:
    boot_data = f.read()

# Resource is at offset 0x6F9000, size 973312 bytes
resource_data = boot_data[0x6F9000:0x6F9000 + 973312]
print(f'Resource image: {len(resource_data)} bytes')
print(f'First 64 bytes: {resource_data[:64].hex(" ")}')

# Check if it starts with RSCE (Rockchip resource image)
if resource_data[:4] == b'RSCE':
    print('Resource image format: RSCE (Rockchip Resource Container)')
elif resource_data[:4] == b'\xd0\x0d\xfe\xed':
    print('Resource image format: FDT (Flattened Device Tree)')
else:
    print(f'Resource image format: Unknown (magic: {resource_data[:4].hex()})')

# Search for DTB magic within resource
print('\nSearching for DTBs in resource image...')
pos = 0
dtb_count = 0
while pos < len(resource_data):
    idx = resource_data.find(b'\xd0\x0d\xfe\xed', pos)
    if idx < 0:
        break
    dtb_size = struct.unpack_from('>I', resource_data, idx + 4)[0]
    print(f'  DTB at offset 0x{idx:X}, size {dtb_size} bytes')
    
    # Extract this DTB
    dtb_data = resource_data[idx:idx + dtb_size]
    dtb_out = os.path.join(base, f'resource-dtb-{dtb_count}.dtb')
    with open(dtb_out, 'wb') as f:
        f.write(dtb_data)
    print(f'  Saved to {dtb_out}')
    dtb_count += 1
    pos = idx + dtb_size

# 3. Try to decompile the main DTB using dtc if available  
print('\n=== DTB Decompilation ===\n')
dtb_path = os.path.join(base, 'fdt.dtb')
dts_path = os.path.join(base, 'fdt.dts')

# Try python-based decompilation (basic)
# Parse the DTB fully and output as text
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

def prop_to_str(name, value, indent):
    """Format property value for DTS output"""
    if len(value) == 0:
        return f'{indent}{name};'
    
    # String property heuristic
    is_string = True
    if len(value) > 0 and value[-1:] == b'\x00':
        # Check if printable
        for b in value[:-1]:
            if b == 0:  # Null separates multiple strings
                continue
            if b < 32 or b > 126:
                is_string = False
                break
    else:
        is_string = False
    
    if is_string and len(value) > 1:
        strings = [s.decode('ascii', errors='replace') for s in value[:-1].split(b'\x00') if s]
        if strings:
            str_val = '", "'.join(strings)
            return f'{indent}{name} = "{str_val}";'
    
    if len(value) % 4 == 0 and len(value) <= 64:
        # Cell array
        cells = []
        for i in range(0, len(value), 4):
            val = struct.unpack_from('>I', value, i)[0]
            cells.append(f'0x{val:08x}')
        return f'{indent}{name} = <{" ".join(cells)}>;'
    
    # Raw bytes
    hex_bytes = ' '.join(f'{b:02x}' for b in value)
    return f'{indent}{name} = [{hex_bytes}];'

def decompile_dtb(data, offset=0):
    """Decompile DTB to DTS text (simplified)"""
    FDT_BEGIN_NODE = 0x00000001
    FDT_END_NODE = 0x00000002
    FDT_PROP = 0x00000003
    FDT_NOP = 0x00000004
    FDT_END = 0x00000009
    
    header = parse_fdt_header(data, offset)
    if not header:
        return None
    
    off = offset + header['off_dt_struct']
    strings_off = offset + header['off_dt_strings']
    end = off + header['size_dt_struct']
    
    lines = ['/dts-v1/;\n']
    depth = 0
    
    while off < end:
        token = struct.unpack_from('>I', data, off)[0]
        off += 4
        
        if token == FDT_BEGIN_NODE:
            name_end = data.find(b'\x00', off)
            name = data[off:name_end].decode('ascii', errors='replace')
            off = (name_end + 4) & ~3
            indent = '\t' * depth
            if name:
                lines.append(f'{indent}{name} {{')
            else:
                lines.append(f'{indent}/ {{')
            depth += 1
            
        elif token == FDT_END_NODE:
            depth -= 1
            indent = '\t' * depth
            lines.append(f'{indent}}};')
            lines.append('')
            
        elif token == FDT_PROP:
            prop_len = struct.unpack_from('>I', data, off)[0]
            prop_nameoff = struct.unpack_from('>I', data, off + 4)[0]
            off += 8
            prop_name = get_string(data, strings_off, prop_nameoff)
            prop_data = data[off:off + prop_len]
            off = (off + prop_len + 3) & ~3
            indent = '\t' * depth
            lines.append(prop_to_str(prop_name, prop_data, indent))
            
        elif token == FDT_NOP:
            pass
        elif token == FDT_END:
            break
    
    return '\n'.join(lines)

with open(dtb_path, 'rb') as f:
    dtb_data = f.read()

print(f'Decompiling {dtb_path} ({len(dtb_data)} bytes)...')
dts_text = decompile_dtb(dtb_data)
if dts_text:
    with open(dts_path, 'w', encoding='utf-8') as f:
        f.write(dts_text)
    
    # Count nodes
    node_count = dts_text.count('{')
    line_count = len(dts_text.split('\n'))
    print(f'Decompiled: {line_count} lines, {node_count} nodes')
    print(f'Saved to {dts_path}')
    
    # Extract display-related sections
    print('\n=== Display-Related DTS Sections ===\n')
    lines = dts_text.split('\n')
    in_display = False
    brace_depth = 0
    display_keywords = ['panel', 'backlight', 'display-subsystem', 'route-rgb', 'route-dsi', 'rgb@', 'rgb {', 'vop@', 'dsi@', 'pwm@']
    
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not in_display:
            for kw in display_keywords:
                if kw in stripped.lower() and '{' in stripped:
                    in_display = True
                    brace_depth = 0
                    print(f'--- Line {i+1}: {stripped} ---')
                    break
        
        if in_display:
            print(line)
            brace_depth += line.count('{') - line.count('}')
            if brace_depth <= 0:
                in_display = False
                print()
else:
    print('Failed to decompile DTB')
