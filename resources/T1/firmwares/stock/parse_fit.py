#!/usr/bin/env python3
"""Parse T1 stock boot.img FIT image and extract kernel + DTB"""
import struct
import os
import gzip
import io

base = r'c:\Users\Layer\Documents\FLSUN-OS\resources\T1\firmwares\stock\extracted'

with open(os.path.join(base, 'p3-boot.img'), 'rb') as f:
    data = f.read()

print(f'=== T1 Stock boot.img Analysis ===')
print(f'Size: {len(data)} bytes ({len(data)/1024/1024:.2f} MB)')
print()

# The boot.img is a FIT image (devicetree format)
# Parse the outer FIT header
def parse_fdt_header(data, offset=0):
    """Parse FDT header"""
    magic = struct.unpack_from('>I', data, offset)[0]
    if magic != 0xd00dfeed:
        return None
    totalsize = struct.unpack_from('>I', data, offset + 4)[0]
    off_dt_struct = struct.unpack_from('>I', data, offset + 8)[0]
    off_dt_strings = struct.unpack_from('>I', data, offset + 12)[0]
    off_mem_rsvmap = struct.unpack_from('>I', data, offset + 16)[0]
    version = struct.unpack_from('>I', data, offset + 20)[0]
    last_comp_version = struct.unpack_from('>I', data, offset + 24)[0]
    boot_cpuid_phys = struct.unpack_from('>I', data, offset + 28)[0]
    size_dt_strings = struct.unpack_from('>I', data, offset + 32)[0]
    size_dt_struct = struct.unpack_from('>I', data, offset + 36)[0]
    return {
        'totalsize': totalsize,
        'off_dt_struct': off_dt_struct,
        'off_dt_strings': off_dt_strings,
        'version': version,
        'size_dt_strings': size_dt_strings,
        'size_dt_struct': size_dt_struct,
    }

def get_string(data, strings_offset, str_offset):
    """Get a string from the strings block"""
    start = strings_offset + str_offset
    end = data.find(b'\x00', start)
    return data[start:end].decode('ascii', errors='replace')

def parse_fdt_struct(data, header, base_offset=0):
    """Walk the FDT structure and extract nodes/properties"""
    FDT_BEGIN_NODE = 0x00000001
    FDT_END_NODE = 0x00000002
    FDT_PROP = 0x00000003
    FDT_NOP = 0x00000004
    FDT_END = 0x00000009
    
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
            off = (name_end + 4) & ~3  # Align to 4 bytes
            path.append(name)
            current_props = {}
            nodes['/'.join(path)] = current_props
            
        elif token == FDT_END_NODE:
            if path:
                path.pop()
            
        elif token == FDT_PROP:
            prop_len = struct.unpack_from('>I', data, off)[0]
            prop_nameoff = struct.unpack_from('>I', data, off + 4)[0]
            off += 8
            prop_name = get_string(data, strings_off, prop_nameoff)
            prop_data = data[off:off + prop_len]
            off = (off + prop_len + 3) & ~3  # Align to 4 bytes
            current_props[prop_name] = prop_data
            
        elif token == FDT_NOP:
            pass
            
        elif token == FDT_END:
            break
        else:
            break
    
    return nodes

# Parse the main FIT header
header = parse_fdt_header(data, 0)
if header is None:
    print("ERROR: Not a valid FDT/FIT image")
    exit(1)

print(f'FIT Header:')
print(f'  Total size: {header["totalsize"]} bytes')
print(f'  Version: {header["version"]}')
print()

# Parse FIT structure
nodes = parse_fdt_struct(data, header, 0)

print(f'FIT Image Nodes ({len(nodes)} total):')
for path, props in sorted(nodes.items()):
    if not props:
        print(f'  /{path}')
        continue
    
    desc = props.get('description', b'')
    if desc:
        desc = desc.rstrip(b'\x00').decode('ascii', errors='replace')
    
    data_prop = props.get('data', None)
    data_pos = props.get('data-position', None)
    data_size_prop = props.get('data-size', None)
    comp = props.get('compression', b'')
    if comp:
        comp = comp.rstrip(b'\x00').decode('ascii', errors='replace')
    type_prop = props.get('type', b'')
    if type_prop:
        type_prop = type_prop.rstrip(b'\x00').decode('ascii', errors='replace')
    arch = props.get('arch', b'')
    if arch:
        arch = arch.rstrip(b'\x00').decode('ascii', errors='replace')
    os_prop = props.get('os', b'')
    if os_prop:
        os_prop = os_prop.rstrip(b'\x00').decode('ascii', errors='replace')
    
    size_info = ''
    if data_prop:
        size_info = f' [inline data: {len(data_prop)} bytes]'
    elif data_pos and data_size_prop:
        pos_val = struct.unpack_from('>I', data_pos, 0)[0]
        size_val = struct.unpack_from('>I', data_size_prop, 0)[0]
        size_info = f' [data at 0x{pos_val:X}, size {size_val} bytes ({size_val/1024/1024:.2f} MB)]'
    
    extra = ''
    if desc:
        extra += f' desc="{desc}"'
    if type_prop:
        extra += f' type={type_prop}'
    if comp:
        extra += f' compression={comp}'
    if arch:
        extra += f' arch={arch}'
    if os_prop:
        extra += f' os={os_prop}'
    
    print(f'  /{path}{size_info}{extra}')
    
    # Show all property names for important nodes
    if 'kernel' in path.lower() or 'fdt' in path.lower() or 'images' in path.lower():
        prop_names = [k for k in props.keys() if k not in ('data',)]
        if prop_names:
            print(f'    props: {", ".join(prop_names)}')

print()

# Now extract images based on what we found
# Look for data-position / data-size or inline data
print('=== Extracting Components ===\n')

for path, props in sorted(nodes.items()):
    type_prop = props.get('type', b'').rstrip(b'\x00').decode('ascii', errors='replace')
    comp = props.get('compression', b'').rstrip(b'\x00').decode('ascii', errors='replace')
    desc = props.get('description', b'').rstrip(b'\x00').decode('ascii', errors='replace')
    
    # Get data
    raw_data = None
    if 'data' in props:
        raw_data = props['data']
    elif 'data-position' in props and 'data-size' in props:
        pos = struct.unpack_from('>I', props['data-position'], 0)[0]
        size = struct.unpack_from('>I', props['data-size'], 0)[0]
        raw_data = data[pos:pos + size]
    
    if raw_data is None or len(raw_data) < 16:
        continue
    
    node_name = path.split('/')[-1] if '/' in path else path
    
    # Determine filename
    if type_prop == 'kernel':
        fname = 'kernel.bin'
    elif type_prop == 'flat_dt':
        fname = f'{node_name}.dtb'
    elif type_prop == 'ramdisk':
        fname = 'ramdisk.bin'
    else:
        continue
    
    # Decompress if needed
    if comp == 'gzip':
        try:
            decompressed = gzip.decompress(raw_data)
            print(f'{path}: {len(raw_data)} bytes compressed ({comp}) -> {len(decompressed)} bytes')
            raw_data = decompressed
        except Exception as e:
            print(f'{path}: gzip decompression failed: {e}')
    elif comp == 'lz4':
        print(f'{path}: {len(raw_data)} bytes (LZ4 compressed, cannot decompress here)')
        # Save compressed anyway
        fname = fname + '.lz4'
    elif comp == 'lzma':
        import lzma
        try:
            decompressed = lzma.decompress(raw_data)
            print(f'{path}: {len(raw_data)} bytes compressed ({comp}) -> {len(decompressed)} bytes')
            raw_data = decompressed
        except:
            print(f'{path}: lzma decompression failed')
    else:
        print(f'{path}: {len(raw_data)} bytes (uncompressed)')
    
    out_path = os.path.join(base, fname)
    with open(out_path, 'wb') as f:
        f.write(raw_data)
    print(f'  => Saved to {out_path}')
    
    # If it's a kernel, look for version string
    if type_prop == 'kernel':
        for pattern in [b'Linux version ']:
            pos = raw_data.find(pattern)
            if pos >= 0:
                end_pos = raw_data.find(b'\x00', pos)
                if end_pos < 0:
                    end_pos = pos + 200
                ver_str = raw_data[pos:min(end_pos, pos+200)].decode('ascii', errors='replace')
                print(f'  Kernel version: {ver_str[:150]}')
    
    # If it's a DTB, extract basic info
    if type_prop == 'flat_dt' and raw_data[:4] == b'\xd0\x0d\xfe\xed':
        dtb_header = parse_fdt_header(raw_data, 0)
        dtb_nodes = parse_fdt_struct(raw_data, dtb_header, 0)
        
        # Get root properties
        root = dtb_nodes.get('', {})
        model = root.get('model', b'').rstrip(b'\x00').decode('ascii', errors='replace')
        compatible_raw = root.get('compatible', b'')
        # Compatible is null-separated list
        compatibles = [c.decode('ascii', errors='replace') for c in compatible_raw.split(b'\x00') if c]
        
        print(f'  DTB Model: {model}')
        print(f'  DTB Compatible: {", ".join(compatibles)}')
        
        # Find display/panel nodes
        for npath, nprops in sorted(dtb_nodes.items()):
            npath_lower = npath.lower()
            if any(x in npath_lower for x in ['panel', 'display', 'backlight', 'dsi', 'rgb', 'vop']):
                status = nprops.get('status', b'').rstrip(b'\x00').decode('ascii', errors='replace')
                compat = nprops.get('compatible', b'').rstrip(b'\x00').decode('ascii', errors='replace')
                print(f'  DISPLAY NODE: /{npath} status={status} compatible={compat}')
                
                # If panel, print all properties
                if 'panel' in npath_lower:
                    for pk, pv in sorted(nprops.items()):
                        if pk == 'data':
                            continue
                        if len(pv) <= 256:
                            if len(pv) == 4:
                                val = struct.unpack_from('>I', pv, 0)[0]
                                print(f'    {pk} = <0x{val:08X}> ({val})')
                            elif all(32 <= b <= 126 or b == 0 for b in pv):
                                print(f'    {pk} = "{pv.rstrip(b"\\x00").decode("ascii", errors="replace")}"')
                            else:
                                hex_str = ' '.join(f'{b:02X}' for b in pv[:64])
                                print(f'    {pk} = [{hex_str}]')

    print()

# Also analyze uboot partition  
print('=== U-Boot Partition (p1) Analysis ===\n')
with open(os.path.join(base, 'p1-uboot.img'), 'rb') as f:
    uboot_data = f.read()

uboot_header = parse_fdt_header(uboot_data, 0)
if uboot_header:
    print(f'U-Boot FDT: version={uboot_header["version"]}, size={uboot_header["totalsize"]}')
    uboot_nodes = parse_fdt_struct(uboot_data, uboot_header, 0)
    for path, props in sorted(uboot_nodes.items()):
        desc = props.get('description', b'').rstrip(b'\x00').decode('ascii', errors='replace')
        type_prop = props.get('type', b'').rstrip(b'\x00').decode('ascii', errors='replace')
        comp = props.get('compression', b'').rstrip(b'\x00').decode('ascii', errors='replace')
        data_prop = props.get('data', None)
        size_info = f' [{len(data_prop)} bytes]' if data_prop else ''
        extra = ''
        if desc:
            extra += f' desc="{desc}"'
        if type_prop:
            extra += f' type={type_prop}'
        if comp:
            extra += f' comp={comp}'
        print(f'  /{path}{size_info}{extra}')

# Search for kernel version in the kernel data (even if compressed)
print('\n=== Looking for kernel version in compressed kernel ===\n')
kernel_path = os.path.join(base, 'kernel.bin')
if os.path.exists(kernel_path):
    with open(kernel_path, 'rb') as f:
        kdata = f.read()
    
    # If it's a zImage, find the gzip stream
    for gzip_magic_offset in range(0, min(len(kdata), 100000), 4):
        if kdata[gzip_magic_offset:gzip_magic_offset+2] == b'\x1f\x8b':
            try:
                decompressed = gzip.decompress(kdata[gzip_magic_offset:])
                print(f'Found gzip stream at offset 0x{gzip_magic_offset:X}, decompressed to {len(decompressed)} bytes')
                
                # Search for version string
                pos = decompressed.find(b'Linux version ')
                if pos >= 0:
                    end = decompressed.find(b'\x00', pos)
                    version = decompressed[pos:min(end, pos+200)].decode('ascii', errors='replace')
                    print(f'Kernel version: {version}')
                
                # Save decompressed
                vmlinux_path = os.path.join(base, 'vmlinux-decompressed.bin')
                with open(vmlinux_path, 'wb') as f:
                    f.write(decompressed)
                print(f'Saved decompressed kernel to {vmlinux_path}')
                break
            except:
                continue
    
    # Also try if the kernel data itself is already decompressed
    pos = kdata.find(b'Linux version ')
    if pos >= 0:
        end = kdata.find(b'\x00', pos)
        version = kdata[pos:min(end, pos+200)].decode('ascii', errors='replace')
        print(f'Kernel version (direct search): {version}')
