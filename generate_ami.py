#!/usr/bin/env python3
"""Generate a proper annular AMI STL at Z=0.4m to 0.59m."""
import struct, math

R_inner = 0.35
R_outer = 0.40
Z_bot = 0.40
Z_top = 0.59
N_circle = 64
N_z = 1

def write_stl(filename, facets):
    with open(filename, 'wb') as f:
        f.write(struct.pack('<80s', b'annular_ami'))
        f.write(struct.pack('<I', len(facets)))
        for normal, (v1, v2, v3) in facets:
            f.write(struct.pack('<3f', *normal))
            f.write(struct.pack('<3f', *v1))
            f.write(struct.pack('<3f', *v2))
            f.write(struct.pack('<3f', *v3))
            f.write(struct.pack('<H', 0))

facets = []
# Bottom ring
for i in range(N_circle):
    a1 = 2*math.pi*i/N_circle
    a2 = 2*math.pi*(i+1)/N_circle
    c1 = (R_inner*math.cos(a1), R_inner*math.sin(a1), Z_bot)
    c2 = (R_outer*math.cos(a1), R_outer*math.sin(a1), Z_bot)
    c3 = (R_outer*math.cos(a2), R_outer*math.sin(a2), Z_bot)
    c4 = (R_inner*math.cos(a2), R_inner*math.sin(a2), Z_bot)
    # outward face
    facets.append(((0,0,-1), (c2, c3, c4)))
    # inward face
    facets.append(((0,0,-1), (c4, c3, c1)))
# Top ring
for i in range(N_circle):
    a1 = 2*math.pi*i/N_circle
    a2 = 2*math.pi*(i+1)/N_circle
    c1 = (R_inner*math.cos(a1), R_inner*math.sin(a1), Z_top)
    c2 = (R_outer*math.cos(a1), R_outer*math.sin(a1), Z_top)
    c3 = (R_outer*math.cos(a2), R_outer*math.sin(a2), Z_top)
    c4 = (R_inner*math.cos(a2), R_inner*math.sin(a2), Z_top)
    facets.append(((0,0,1), (c4, c3, c2)))
    facets.append(((0,0,1), (c1, c4, c2)))
# Outer wall
for i in range(N_circle):
    a1 = 2*math.pi*i/N_circle
    a2 = 2*math.pi*(i+1)/N_circle
    b1 = (R_outer*math.cos(a1), R_outer*math.sin(a1), Z_bot)
    b2 = (R_outer*math.cos(a2), R_outer*math.sin(a2), Z_bot)
    t1 = (R_outer*math.cos(a1), R_outer*math.sin(a1), Z_top)
    t2 = (R_outer*math.cos(a2), R_outer*math.sin(a2), Z_top)
    nx, ny = math.cos(a1), math.sin(a1)
    facets.append(((nx, ny, 0), (b1, t1, t2)))
    facets.append(((nx, ny, 0), (t2, b2, b1)))
# Inner wall
for i in range(N_circle):
    a1 = 2*math.pi*i/N_circle
    a2 = 2*math.pi*(i+1)/N_circle
    b1 = (R_inner*math.cos(a1), R_inner*math.sin(a1), Z_bot)
    b2 = (R_inner*math.cos(a2), R_inner*math.sin(a2), Z_bot)
    t1 = (R_inner*math.cos(a1), R_inner*math.sin(a1), Z_top)
    t2 = (R_inner*math.cos(a2), R_inner*math.sin(a2), Z_top)
    nx, ny = -math.cos(a1), -math.sin(a1)
    facets.append(((nx, ny, 0), (b1, t2, t1)))
    facets.append(((nx, ny, 0), (t2, b2, b1)))

write_stl('constant/triSurface/ami.stl', facets)
print(f"Generated {len(facets)} facets")