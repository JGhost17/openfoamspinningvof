import sys, struct

def read_stl(fn):
    with open(fn, 'rb') as f:
        header = f.read(80)
        if header[:5].lower() == b'solid':
            f.seek(0)
            verts = []
            for raw in f:
                parts = raw.split()
                if len(parts) >= 4 and parts[0] == b'vertex':
                    verts.append(list(map(float, parts[1:4])))
            return verts
        f.seek(0)
        f.read(80)
        n = struct.unpack('<I', f.read(4))[0]
        verts = []
        for _ in range(n):
            data = f.read(50)
            if len(data) < 50:
                break
            vals = struct.unpack('<12fH', data)
            verts.append([vals[3], vals[4], vals[5]])
            verts.append([vals[6], vals[7], vals[8]])
            verts.append([vals[9], vals[10], vals[11]])
        return verts

for fn in sys.argv[1:]:
    verts = read_stl(fn)
    mn = [min(v[i] for v in verts) for i in range(3)]
    mx = [max(v[i] for v in verts) for i in range(3)]
    print(fn, 'verts', len(verts), 'min', [round(x,4) for x in mn], 'max', [round(x,4) for x in mx])