import struct

def read_stl_bounds(filename):
    with open(filename, 'rb') as f:
        f.read(80)
        ntri = struct.unpack('I', f.read(4))[0]
        verts = set()
        for i in range(ntri):
            f.read(12)  # normal
            v1 = struct.unpack('3f', f.read(12))
            v2 = struct.unpack('3f', f.read(12))
            v3 = struct.unpack('3f', f.read(12))
            f.read(2)   # attr
            verts.update([v1, v2, v3])
        xs = [v[0] for v in verts]
        ys = [v[1] for v in verts]
        zs = [v[2] for v in verts]
        return min(xs), max(xs), min(ys), max(ys), min(zs), max(zs)

for name in ['tank.STL', 'impeller.STL', 'ami.STL']:
    try:
        xmin, xmax, ymin, ymax, zmin, zmax = read_stl_bounds(name)
        print(f'{name}: X=[{xmin:.4f},{xmax:.4f}] Y=[{ymin:.4f},{ymax:.4f}] Z=[{zmin:.4f},{zmax:.4f}] diam={xmax-xmin:.4f} h={zmax-zmin:.4f}')
    except Exception as e:
        print(f'{name}: ERROR: {e}')