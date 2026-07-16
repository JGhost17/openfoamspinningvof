# AGENTS.md — Canonical reference for AI agents working on this case

> **This is the source of truth.** It supersedes the older `task.md`,
> `FIXES.md`, and `RUN_INSTRUCTIONS.md` (now consolidated here and in
> `README.md`). Read this fully before changing anything. Humans should read
> `README.md`; everything a human needs to *run* the case is also repeated in
> section 8 below.

---

## 1. TL;DR / current status

- **What:** a stirred-tank **two-phase (VOF) mixer** solved with OpenFOAM
  **v2312 (ESI/openfoam.com)** `interFoam`. A rotating impeller drives mixing
  of two oils; the impeller region rotates via a sliding **AMI** (Arbitrary
  Mesh Interface).
- **State:** **it meshes, initialises, and runs to completion in parallel.**
  The case as *originally committed* could not even mesh — it took a long
  chain of fixes (section 7). Do not assume old comments in dictionaries are
  correct; trust this file + the actual dictionary contents.
- **Last verified run:** 50/50 oil split, ran to `endTime = 0.2 s` (168
  timesteps, 8 MPI ranks, ~740k cells) with no crash; bounded Courant, alpha
  in [0,1]. Wall-clock ≈ 2.9 hours for 0.2 s of simulated time.
- **Rendered output** lives in `results/*.png` (volume-fraction + velocity
  cut-planes at t=0.2 s).

---

## 2. Physics & method

| Item | Value | File |
|---|---|---|
| Solver | `interFoam` (incompressible VOF, MULES) | `system/controlDict` |
| Phase 1 `oilHeavy` | ρ = 940 kg/m³, ν = 3.5e-4 m²/s (µ = 0.329 Pa·s) | `constant/transportProperties` |
| Phase 2 `oilLight` | ρ = 820 kg/m³, ν = 5.0e-6 m²/s (µ = 0.0041 Pa·s) | `constant/transportProperties` |
| Surface tension σ | see file | `constant/transportProperties` |
| Turbulence | RAS **k-omega SST** | `constant/turbulenceProperties` |
| Impeller motion | `solidBody` / `rotatingMotion`, ω ramped **0→25 rad/s over 0.02 s** then held (≈239 rpm) | `constant/dynamicMeshDict` |
| Gravity | (0 0 −9.81) | `constant/g` |

> **transportProperties uses KINEMATIC viscosity ν = µ/ρ.** The dynamic
> viscosities above were divided by density. If someone gives you µ (Pa·s),
> convert before writing `nu`.

---

## 3. Geometry & coordinate system (critical)

- **Z is "up"** — the rotation axis is `(0 0 1)`. (There is no Y-up
  convention here; a "vertical" cut plane is the **X–Z plane**, slice
  normal = `(0 1 0)`.)
- **Everything is centred on the origin.** The raw CAD STLs were exported in
  **millimetres** and offset (centred near (1270,1270) mm); they were
  converted to ASCII and **translated by (−1270,−1270,0) mm** so the assembly
  is origin-centred, and are scaled `×0.001` in `snappyHexMeshDict`.
- Approximate dimensions (metres, after scaling & centring):
  - **Tank:** cylinder, radius ≈ 1.25, z ≈ 0.02 → 2.32 (closed vessel; no
    atmosphere patch).
  - **Impeller:** radius ≈ 0.35, z ≈ 0.445 → 2.31, on the axis.
  - **AMI cylinder (`ami`):** radius **0.40**, z ≈ 0.40 → 2.315 — defines the
    `rotatingZone`.
  - **Background mesh (`blockMeshDict`):** box (−1.35 −1.35 −0.1) →
    (1.35 1.35 2.4), 68×68×63, `convertToMeters 1`.
- ⚠️ **The impeller (r=0.35) is only ~0.05 m from the AMI (r=0.40).** This
  tight gap is the root cause of the hardest stability problem (section 7/G).
  If you want a faster/more robust setup, **widen the AMI radius** (e.g. 0.55)
  — this is the real fix, and lets pressure use fast GAMG again.

---

## 4. File map (what matters)

```
0/            alpha.oilHeavy, U, p_rgh, k, omega, nut  (initial/BC fields; all
              patches: tank, impeller, ami1, ami2 — ami* are cyclicAMI)
constant/
  transportProperties   two oils (see §2)
  turbulenceProperties  RAS kOmegaSST
  dynamicMeshDict       solidBody rotatingMotion, cellZone rotatingZone, ω ramp
  g                     gravity
  triSurface/           tank.stl, impeller.stl, ami.stl  (ASCII, origin-centred)
system/
  blockMeshDict         background hex mesh
  snappyHexMeshDict     snaps STLs; ami -> rotatingZone cell-/faceZone
  surfaceFeatureExtractDict
  createBafflesDict     splits rotatingZone faceZone -> cyclicAMI ami1/ami2  ← USED
  createPatchDict       (legacy; NOT used — see §7 B3)
  controlDict           interFoam, adjustTimeStep, endTime (demo=0.2)
  setFieldsDict         fills lower half (box top z=1.17) -> 50/50 by volume
  fvSchemes / fvSolution
  decomposeParDict      numberOfSubdomains (match your -np)
results/      rendered PNG cut-planes
*.py          STL helpers (convert_stl.py, make_ami_*.py, read_stl*.py)
README.md     human guide (run + view + tweak)
```

Regenerable (git-ignored, rebuilt by the pipeline): `constant/polyMesh/`,
`constant/extendedFeatureEdgeMesh/`, `*.eMesh`, `processor*/`, time dirs,
`VTK/`, `log.*`.

---

## 5. The pipeline (exact order — do not reorder)

```bash
source /usr/lib/openfoam/openfoam2312/etc/bashrc
cd ~/openfoamspinningvof            # a Linux path with NO spaces (see §6)

# --- MESH ---
surfaceFeatureExtract               # feature edges from the 3 STLs
blockMesh                           # background hex mesh
snappyHexMesh -overwrite            # snap; build rotatingZone cell-/faceZone
renumberMesh -overwrite
createBaffles -overwrite            # faceZone -> cyclicAMI ami1/ami2  (NOT createPatch!)
checkMesh -allTopology -allGeometry

# --- INITIALISE ---
setFields                           # ~50/50 fill (Selected ~340k/740k cells)

# --- SOLVE (parallel) ---
decomposePar -force
mpirun -np <N> interFoam -parallel  # N must equal numberOfSubdomains

# --- POST ---
reconstructPar [-latestTime]
foamToVTK [-latestTime]             # portable VTK for ParaView
```

---

## 6. Environment constraints & gotchas (read before running commands)

- **Run from a Linux path without spaces** (e.g. `~/openfoamspinningvof`). Do
  **not** run from a `/mnt/c/...` Windows path — OpenFOAM's filename checker
  treats a space (e.g. in `CFD ML`) as **fatal**.
- **File ownership (WSL):** editing files from Windows via the `\\wsl$` share
  creates them **root-owned**. OpenFOAM tools run as the normal user and can
  *read* but not *overwrite* root-owned files — this silently broke `setFields`
  once (alpha stayed 0). After editing via `\\wsl$`, run
  `chown -R <user>:<user> <case>` before running OpenFOAM.
- **Never edit dictionaries while a `runTimeModifiable` run is live** — a
  partial read throws a fatal parse error.
- **ParaView's OpenFOAM reader is flaky here** (reports zero fields). For
  headless rendering, **read the `foamToVTK` output (`VTK/.../internal.vtu`)
  with an `XMLUnstructuredGridReader` instead** — see `render_vtk.py`.
- Offscreen rendering works: `pvbatch render_vtk.py <internal.vtu> <tag>`.

---

## 7. Bugs that were fixed — DO NOT REINTRODUCE

Condensed. Each was a real blocker; the case won't run if reverted.

**Geometry / STL**
- A1. STLs were **binary with an ASCII `solid` header** → `surfaceFeatureExtract`
  hung forever. Fixed: convert to true ASCII (`convert_stl.py`).
- A2. STLs were **off-centre** (positive octant) while all dicts are
  origin-centred → impeller/AMI fell outside the mesh. Fixed: translate STLs
  by (−1270,−1270,0) mm.
- A3. Added `scale 0.001` to STL `geometry` entries (mm→m).

**Meshing**
- B1. `locationInMesh` was **inside the impeller solid** → mesh collapsed to
  ~11k cells. Fixed: `(0.8 0 0.6)` (in the fluid).
- B2. `faceZone`/`cellZone` must be in `castellatedMeshControls/refinementSurfaces`
  (with `cellZoneInside inside`), **not** in the `geometry{}` block (silently
  ignored there) → otherwise no `rotatingZone`.
- B3. Split the AMI with **`createBaffles`** (internal faceZone → ami1/ami2
  cyclicAMI), **not** `createPatch` (snappy makes the AMI a faceZone, so
  createPatch finds no `ami` patch and makes zero-face patches).

**Fields / models**
- C1. `0/` fields rebuilt with **all** patches (tank, impeller, ami1, ami2);
  `alpha.oilHeavy` reset (was corrupt, wrong cell count).
- C2/C3. Added `constant/turbulenceProperties` (kOmegaSST) and `0/nut`
  (`nutkWallFunction`) — required by interFoam+RAS.

**Solver config (interFoam aborted at t=0 without these)**
- D1. `dynamicMeshDict`: v2312 form `solidBodyMotionFunction rotatingMotion`
  with params nested in `rotatingMotionCoeffs`.
- D2. Closed domain → added `pRefCell 0; pRefValue 0;` (PIMPLE).
- D3. Moving mesh → added a `pcorr` solver.
- D4. `fvSchemes`: added `div(phi,alpha)`, `div(phirb,alpha)` (unsuffixed
  names the solver looks up) and `div(((rho*nuEff)*dev2(T(grad(U)))))`.

**Stability / time-stepping**
- E2. Impulsive impeller start FPE-crashes with a large first step → start
  `deltaT 1e-5` and let `adjustTimeStep yes` ramp it.
- E3. `adjustTimeStep yes` was missing (only `adjustableRunTime`, which is
  *write* timing) → deltaT never grew.

**50/50-specific (the hardest one) — section G**
- The even 50/50 fill puts the interface in the tight impeller-AMI gap →
  **deterministic NaN at t≈0.0055 s**, reproduced identically across GAMG/PCG,
  FP-trap on/off, ω-ramp, sub-cycles ⇒ a **mesh/geometry** problem, not
  numerics. Fixes that make it run:
  - **`refinementRegions/rotatingBox` level 0→1** (decisive — resolves the
    impeller-AMI gap; mesh ~688k→740k). Plus better snap quality
    (`nSolveIter 100`, `nRelaxIter 10`, `nSmoothPatch 5`, `nSmoothScale 10`).
  - **Pressure `p_rgh`/`pcorr`: PCG/DIC** (GAMG diverged to NaN on the
    ill-conditioned AMI-baffle cells; PCG is robust but ~5–8× slower).
  - **ω ramp** (E-class) + `nNonOrthogonalCorrectors 2` + `nAlphaSubCycles 2`.

**Performance note:** `pcorr`/`p_rgh` were switched PCG→GAMG earlier for an
~8× speedup, then **back to PCG** for the 50/50 case because GAMG diverged on
the tight-gap mesh. To use fast GAMG again, first **widen the AMI gap**
(enlarge `ami.stl` radius) — that removes the ill-conditioning at the source.

---

## 8. How to run (for an agent driving the case)

Prereqs: OpenFOAM v2312 installed; run from `~/openfoamspinningvof`.

```bash
source /usr/lib/openfoam/openfoam2312/etc/bashrc
cd ~/openfoamspinningvof

# reset the phase field before (re)meshing so renumberMesh doesn't choke on a
# stale nonuniform field of the wrong cell count:
foamDictionary -entry internalField -set 'uniform 0' 0/alpha.oilHeavy

# mesh + init + solve + post (see §5 for the full list)
surfaceFeatureExtract && blockMesh && snappyHexMesh -overwrite && \
renumberMesh -overwrite && createBaffles -overwrite && \
checkMesh -allTopology -allGeometry
setFields
decomposePar -force
mpirun -np $(grep -oP 'numberOfSubdomains\s+\K[0-9]+' system/decomposeParDict) interFoam -parallel | tee log.interFoam
reconstructPar -latestTime
foamToVTK -latestTime
```

**Monitoring a run** (healthy = bounded Courant < maxCo, alpha in ~[0,1], no
`FOAM FATAL`/`nan`/`exited on signal`):
```bash
grep -E '^Time = ' log.interFoam | tail
grep 'Courant Number mean' log.interFoam | tail
grep 'Min(alpha' log.interFoam | tail
grep 'ExecutionTime' log.interFoam | tail
```

**Rendering cut-planes headlessly** (after reconstruct + foamToVTK):
```bash
pvbatch render_vtk.py VTK/openfoamspinningvof_<N>/internal.vtu <tag>
# outputs results/alpha_vertical_XZ_<tag>.png, U_vertical_XZ_<tag>.png,
#         U_horizontal_XY_<tag>.png
```

---

## 9. Changing common settings

| Goal | Edit | Notes |
|---|---|---|
| Run length | `system/controlDict` `endTime` | Currently **0.2 s** (demo). Full mixing ≈ 300 s. |
| Output frequency | `controlDict` `writeInterval` (with `adjustableRunTime`) | |
| Parallel width | `system/decomposeParDict` `numberOfSubdomains` **and** `-np` | must match |
| Oil properties | `constant/transportProperties` `nu`, `rho` | ν = µ/ρ (kinematic!) |
| Impeller speed | `constant/dynamicMeshDict` `omega` table | keep the 0→ω ramp |
| Split ratio | `system/setFieldsDict` box top-z | z=1.17 ⇒ 50/50; ∝ (z−0.02)/2.30 |
| Speed vs robustness | `fvSolution` p_rgh/pcorr PCG↔GAMG | GAMG needs a wider AMI gap |
| Mesh resolution | `snappyHexMeshDict` `refinementSurfaces` levels, `refinementRegions/rotatingBox` | rotatingBox level drives impeller-AMI gap quality |

---

## 10. Performance reality (measured)

8 ranks, ~740k cells, PCG pressure: **0.2 s took ~2.9 h wall-clock.**
Extrapolated: 1 s ≈ 14 h, 5 s ≈ 3 days, **60 s ≈ ~36 days** — so the full
mixing timescale is **not** feasible on this laptop as-is. To make long runs
practical: coarser mesh + wider AMI (→ GAMG) + more cores, or use a bigger
machine.
