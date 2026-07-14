import struct

def binary_to_ascii_stl(input_path, output_path):
    with open(input_path, 'rb') as f:
        header = f.read(80)
        ntri = struct.unpack('I', f.read(4))[0]
        name = header.split(b'\0')[0].decode('ascii', errors='replace').strip()
        with open(output_path, 'w') as out:
            out.write(f'solid {name}\n')
            for i in range(ntri):
                normal = struct.unpack('3f', f.read(12))
                v1 = struct.unpack('3f', f.read(12))
                v2 = struct.unpack('3f', f.read(12))
                v3 = struct.unpack('3f', f.read(12))
                attr = struct.unpack('H', f.read(2))[0]
                out.write(f'  facet normal {normal[0]:.6e} {normal[1]:.6e} {normal[2]:.6e}\n')
                out.write('    outer loop\n')
                out.write(f'      vertex {v1[0]:.6e} {v1[1]:.6e} {v1[2]:.6e}\n')
                out.write(f'      vertex {v2[0]:.6e} {v2[1]:.6e} {v2[2]:.6e}\n')
                out.write(f'      vertex {v3[0]:.6e} {v3[1]:.6e} {v3[2]:.6e}\n')
                out.write('    endloop\n')
                out.write('  endfacet\n')
            out.write(f'endsolid {name}\n')

for name in ['tank', 'impeller', 'ami']:
    binary_to_ascii_stl(f'constant/triSurface/{name}.STL', f'constant/triSurface/{name}.stl')
    print(f'Converted {name}.STL -> {name}.stl')