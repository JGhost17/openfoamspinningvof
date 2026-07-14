import math

# Generate an OPEN cylindrical AMI surface (side wall only, no top/bottom disks)
# This creates a faceZone that will be split into ami1/ami2 cyclicAMI patches
# Source units are mm; snappyHexMeshDict applies scale 0.001 -> metres.
#
# impeller.STL bbox (mm): x,y in [920,1620] (centre 1270, radius 350), z in [445,2310]
# tank.STL top z = 2320 (impeller top sits 10 mm below tank top)
# => cylinder must stay inside tank: z_high < 2320, and enclose impeller: z_high > 2310

CX, CY = 1270.0, 1270.0   # cylinder axis centre (matches impeller centre)
R      = 400.0            # radius: 50 mm margin outside impeller radius 350
Z_LOW  = 400.0            # 45 mm below impeller bottom (445)
Z_HIGH = 2315.0           # 5 mm above impeller top (2310), 5 mm below tank top (2320)
N_SEG  = 64

def facet(f, n, v1, v2, v3):
    f.write('  facet normal %e %e %e\n' % n)
    f.write('    outer loop\n')
    f.write('      vertex %e %e %e\n' % v1)
    f.write('      vertex %e %e %e\n' % v2)
    f.write('      vertex %e %e %e\n' % v3)
    f.write('    endloop\n')
    f.write('  endfacet\n')

facets = []
# Side wall (outward normals) - OPEN cylinder, no end caps
for i in range(N_SEG):
    a0 = 2*math.pi*i/N_SEG
    a1 = 2*math.pi*(i+1)/N_SEG
    x0, y0 = CX+R*math.cos(a0), CY+R*math.sin(a0)
    x1, y1 = CX+R*math.cos(a1), CY+R*math.sin(a1)
    nx, ny = math.cos((a0+a1)/2), math.sin((a0+a1)/2)
    facets.append(((nx,ny,0), (x0,y0,Z_LOW), (x1,y1,Z_LOW), (x1,y1,Z_HIGH)))
    facets.append(((nx,ny,0), (x0,y0,Z_LOW), (x1,y1,Z_HIGH), (x0,y0,Z_HIGH)))

with open('constant/triSurface/ami.STL', 'w') as f:
    f.write('solid ami\n')
    for n, v1, v2, v3 in facets:
        facet(f, n, v1, v2, v3)
    f.write('endsolid ami\n')

print('Wrote OPEN ami cylinder: centre (%.0f,%.0f), R=%.0f mm, z=[%.0f,%.0f] mm, %d facets'
      % (CX, CY, R, Z_LOW, Z_HIGH, len(facets)))