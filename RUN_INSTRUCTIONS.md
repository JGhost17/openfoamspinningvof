# Running the Spinning-VOF Mixer Case (interFoam + rotating AMI)

This is an OpenFOAM **v2312 (ESI / openfoam.com)** case: a stirred tank with a
rotating impeller driven by a sliding **AMI** interface, two immiscible oils
solved with **interFoam** (VOF).

It has been verified to mesh, initialise, and run in parallel. These
instructions reproduce the full pipeline on any Linux box — including a
high-core-count machine for the long mixing study.

---

## 1. Prerequisites

- Linux (or WSL2 Ubuntu on Windows) with **OpenFOAM v2312** installed from
  the official ESI repo (`https://dl.openfoam.com`).
- Source the environment in every shell you use:
  ```bash
  source /usr/lib/openfoam/openfoam2312/etc/bashrc
  ```
- **Important (WSL / paths):** run everything from a path **without spaces**
  and, on WSL, from the Linux filesystem (e.g. `~/openfoamspinningvof`), NOT a
  `/mnt/c/...` path with spaces — OpenFOAM's filename checker treats spaces as
  fatal.

Get the case:
```bash
git clone git@github.com:JGhost17/openfoamspinningvof.git
cd openfoamspinningvof
```

---

## 2. Key case settings (already configured)

| File | Setting | Value |
|---|---|---|
| `constant/transportProperties` | oilHeavy | rho=940, nu=3.5e-4 m^2/s (mu=0.329) |
| | oilLight | rho=820, nu=5.0e-6 m^2/s (mu=0.0041) |
| | sigma | 0.02 N/m |
| `constant/dynamicMeshDict` | solidBody rotatingMotion | origin (0 0 0.495), axis (0 0 1), omega=25 rad/s |
| `system/snappyHexMeshDict` | ami cellZone | rotatingZone (`cellZoneInside inside`) |
| `system/controlDict` | adjustTimeStep | yes; maxCo=10, maxAlphaCo=2, maxDeltaT=0.05 |
| `system/fvSolution` | p_rgh / pcorr | **GAMG** (fast multigrid) |

> Note: OpenFOAM's `transportProperties` uses **kinematic** viscosity
> `nu = mu/rho`. The dynamic viscosities (0.329, 0.0041 Pa·s) were converted.

STL geometry (`constant/triSurface/`) is ASCII and pre-centred on the origin.
If you ever re-import from CAD, the raw exports are in mm and off-centre; use
`convert_stl.py` (binary→ASCII) and translate to origin before meshing.

---

## 3. Mesh generation (strict order)

```bash
surfaceFeatureExtract   2>&1 | tee log.surfaceFeatureExtract
blockMesh               2>&1 | tee log.blockMesh
snappyHexMesh -overwrite 2>&1 | tee log.snappyHexMesh
renumberMesh -overwrite  2>&1 | tee log.renumberMesh
createBaffles -overwrite 2>&1 | tee log.createBaffles     # splits rotatingZone faceZone -> ami1/ami2 (cyclicAMI)
checkMesh -allTopology -allGeometry 2>&1 | tee log.checkMesh
```

Expected: ~688k cells; `rotatingZone` cellZone ~289k cells; `ami1`/`ami2`
cyclicAMI patches with **AMI weights ≈ 1.0**. `checkMesh` reports a few
concave/high-determinant cells near the AMI baffle — this is normal for AMI
and not fatal (no negative volumes).

> Use **`createBaffles`** (NOT `createPatch`) — snappy makes the AMI an
> internal faceZone, and createBaffles is what converts it to the two
> cyclicAMI patches.

---

## 4. Initialise the phase field

```bash
setFields 2>&1 | tee log.setFields
```
Fills the lower tank with `alpha.oilHeavy = 1` (~513k of 688k cells).
Verify the "Selected NNNNN/688602 cells" line is a large nonzero count.

---

## 5. Run in parallel — **16 solver processes** (8-core / 16-thread machine)

`system/decomposeParDict` is set to:
```
numberOfSubdomains  16;
method              scotch;
```

Then:
```bash
decomposePar -force 2>&1 | tee log.decomposePar
mpirun -np 16 interFoam -parallel 2>&1 | tee log.interFoam
```
> On an 8-physical-core machine, 16 MPI ranks use the 16 hardware threads. If
> OpenMPI complains about not enough slots, add `--use-hwthread-cpus` (or
> `--oversubscribe`) to the `mpirun` line.

### Timestep / gentle start
`controlDict` is set for a gentle impulsive start (`deltaT 1e-5`) that then
auto-ramps to the Courant-limited step (`adjustTimeStep yes`, `maxCo 10`).
Do **not** start with a large fixed deltaT — the impeller starting from rest
at 25 rad/s will FPE-crash if the first step is too big.

### Physical end time
For the full mixing study set in `controlDict`:
```
endTime         300;     // ~300 s to mix (per Fluent reference)
writeInterval   5;       // write every 5 s of sim time (adjustableRunTime)
```
The convective step is capped by the impeller tip speed (~8.75 m/s) against
~0.01 m cells, so deltaT cruises around **0.005–0.01 s** → ~30,000–60,000
steps for 300 s. With 16 ranks on an 8-core machine this is a long run — use
`writeInterval` checkpoints so you can stop and restart from the latest
written time (`startFrom latestTime` in `controlDict`). For a quick look,
keep `endTime` small (e.g. 0.5–2 s) to see the impeller-driven flow develop.

### Monitor while running
```bash
grep -E '^Time =' log.interFoam | tail                 # progress
grep 'Courant Number mean' log.interFoam | tail        # stability (keep max < maxCo)
grep 'Min(alpha' log.interFoam | tail                  # alpha must stay ~[0,1]
grep 'ExecutionTime' log.interFoam | tail              # wall time / step
```
If Courant explodes, alpha goes far out of [0,1], or a `FOAM FATAL`/FPE
appears, stop and reduce `maxCo`/`maxAlphaCo`.

---

## 6. Reconstruct & post-process

```bash
reconstructPar 2>&1 | tee log.reconstructPar     # merges processor* -> time dirs in case root
foamToVTK -latestTime                            # portable VTK for ParaView on any device
```

Fields to view: `U` (impeller-driven flow), `alpha.oilHeavy` (interface /
mixing). Fully mixed ≈ `alpha.oilHeavy` ≈ 0.5 everywhere.

---

## 6b. Viewing in ParaView (including just the mesh)

### One-time setup (WSL Ubuntu)
WSL2 (Win 11) ships **WSLg**, so Linux GUI apps display natively. Install
ParaView once:
```bash
sudo apt update && sudo apt install -y paraview
```
(If `paraview` won't open a window, update WSL from PowerShell: `wsl --update`.)

### Open the case / mesh
The empty `paraview.foam` stub at the case root is the entry point for
ParaView's OpenFOAM reader. From the case directory:
```bash
source /usr/lib/openfoam/openfoam2312/etc/bashrc
paraview paraview.foam &
```
You can open the **mesh alone right after meshing** (before/without running the
solver) — `constant/polyMesh` is all the reader needs.

In the ParaView GUI:
1. The `paraview.foam` source is selected in the Pipeline Browser → click
   **Apply** (bottom-left of Properties).
2. Under **Mesh Regions**, tick `internalMesh` (volume) and the patches you
   want (`impeller`, `tank`, `ami1`, `ami2`). Under **Cell Arrays** tick
   `alpha.oilHeavy`, `U`, etc. → **Apply**.
3. Set representation to **Surface** (or **Surface With Edges** to see the mesh
   cells). Colour by `alpha.oilHeavy` or `U` via the dropdown.
4. To see the rotating region: filter **Threshold** on `cellZoneId` /
   `rotatingZone`, or Extract Block → the `rotatingZone` cellZone.
5. For the free-surface/interface: **Contour** filter on `alpha.oilHeavy` at
   value **0.5**. For flow: **Glyph** (vectors) or **Stream Tracer** on `U`.
6. Use the VCR ▶ controls (top toolbar) to step through the written times.

### Alternative: `paraFoam`
`paraFoam` (ships with OpenFOAM) auto-creates the reader stub and launches
ParaView in one step:
```bash
paraFoam            # whole case
paraFoam -touch     # just create the .foam stub without launching
```

### Alternative: view on Windows without a Linux GUI
```bash
foamToVTK -latestTime            # writes VTK/ in the case
```
Then open the files in `VTK/` with **ParaView installed on Windows**
(the WSL filesystem is reachable at `\\wsl$\Ubuntu-24.04\home\...`).

---

## 7. Faster turnaround options

- **Coarser mesh** for quicker studies: lower the snappy `refinementSurfaces`
  levels (2 → 1) — cuts cell count ~3–4× and speeds every step.
- Keep **GAMG** for `p_rgh`/`pcorr` (already set) — the single biggest
  speedup vs PCG on this mesh.
- More cores scale well until per-core cell count gets small (16 ranks on
  688k cells = ~43k cells/core).

See **`FIXES.md`** for the full list of problems that were diagnosed and
fixed to get this case running, with the reasoning behind each fix.
