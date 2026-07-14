# Case Debugging Log — Issues Fixed & Why It Works

This document records every problem that was diagnosed and fixed to get the
spinning-VOF mixer case (`interFoam` + rotating AMI, OpenFOAM v2312) running,
with the reasoning behind each fix. Read alongside `RUN_INSTRUCTIONS.md`.

The case as originally committed **could not mesh or run** — it failed at the
very first meshing utility. The problems fell into six groups: geometry, mesh
setup, initial/boundary fields, solver configuration, environment/permissions,
and performance. All are now resolved.

---

## A. Geometry & STL problems

### A1. STL files were binary with an ASCII header → `surfaceFeatureExtract` hung forever
- **Symptom:** `surfaceFeatureExtract` ran at 100% CPU for 20+ minutes on tiny
  (10–60 KB) STL files and never progressed past "Reading dict".
- **Cause:** `tank.stl`, `impeller.stl`, `ami.stl` were **binary STL** files
  whose 80-byte header nonetheless began with the ASCII text `solid tank...`.
  OpenFOAM decides ASCII-vs-binary by looking for the word `solid`, so it
  mis-detected them as ASCII and tried to parse raw binary floats as text —
  an effectively infinite scan.
- **Fix:** Converted all three to genuine ASCII STL (`convert_stl.py` for the
  binaries; `ami.STL` was already ASCII and was copied over).
- **Why it works:** ASCII STL parses deterministically; `surfaceFeatureExtract`
  now finishes in <1 s and `surfaceCheck` confirms all three are closed,
  single-zone manifolds.

### A2. Geometry was off-centre from the mesh domain → impeller & AMI never meshed
- **Symptom:** After the STL fix, `snappyHexMesh` produced only a `tank` patch —
  **no `impeller`, no `ami`, no rotating zone** — and fragmented the mesh into
  tens of thousands of regions.
- **Cause:** Every OpenFOAM dictionary uses an **origin-centred** coordinate
  system (blockMesh domain ±1.35 m, rotation axis through (0,0,z),
  `locationInMesh (0 0 1.5)`, refinement box ±0.45), but the raw CAD-exported
  STLs sat in the **positive octant** centred at (1.27, 1.27) m. After scaling,
  the impeller and AMI cylinder fell almost entirely **outside** the mesh box,
  so snappy never intersected them.
- **Fix:** Translated all three STLs by **(−1270, −1270, 0) mm** so the
  assembly is centred on the origin (they share the same X/Y centre, so one
  translation aligns all of them). Verified by the rotation axis now passing
  exactly through the centre of the re-centred AMI cylinder.
- **Why it works:** Tank now fits the domain with margin; the impeller and the
  AMI cylinder (radius 0.4 m) sit centred on the rotation axis, so snappy
  resolves them and can build the rotating zone.

### A3. Missing `scale` on the STL geometry (mm → m)
- **Cause:** STLs are in millimetres; the background mesh is in metres. The
  `geometry{}` entries had no unit conversion.
- **Fix:** Added `scale 0.001;` to each `triSurfaceMesh` in
  `snappyHexMeshDict`.

---

## B. Mesh-setup problems

### B1. `locationInMesh` was inside the impeller solid → mesh collapsed to a tiny cavity
- **Symptom:** snappy kept only **10,968 cells** (out of ~575k) and `createPatch`
  then found no AMI faces. (Tellingly, the original committed `0/alpha.oilHeavy`
  also had exactly 10,968 values — it had been generated from this same broken
  mesh.)
- **Cause:** `locationInMesh (0 0 1.5)` lies **inside the impeller hub/shaft**,
  so snappy kept only the small void reachable from that point and discarded
  the whole tank fluid volume.
- **Fix:** Moved it to `(0.8 0 0.6)` — inside the tank, outside the impeller
  and the AMI cylinder, i.e. clearly in the fluid.
- **Why it works:** snappy now keeps the full ~688k-cell fluid region.

### B2. `faceZone`/`cellZone` declared in the wrong dictionary block → no rotating zone
- **Symptom:** `cellZones` file was empty (`0()`); every snappy pass reported
  `cellZone : none`.
- **Cause:** In OpenFOAM v2312 the `faceZone`/`cellZone`/`cellZoneInside`
  keywords belong in **`castellatedMeshControls/refinementSurfaces`**, not in
  the top-level `geometry{}` block where they were placed — there they are
  silently ignored.
- **Fix:** Moved `faceZone rotatingZone; cellZone rotatingZone;
  cellZoneInside inside;` into the `refinementSurfaces/ami` entry.
- **Why it works:** snappy now tags the ~289k cells inside the closed AMI
  surface as the `rotatingZone` cellZone and builds the `rotatingZone`
  faceZone (~72k faces). `cellZoneInside inside` uses the closed surface
  geometry directly, avoiding any point-in-solid ambiguity.

### B3. AMI interface: use `createBaffles`, not `createPatch`
- **Symptom:** `createPatch` created and then removed zero-sized `ami1`/`ami2`
  patches ("Cannot find any patch or group names matching ami").
- **Cause:** snappy builds the AMI as an **internal faceZone**, but
  `createPatchDict` was set up to split a boundary *patch* named `ami`, which
  doesn't exist.
- **Fix:** Use **`createBaffles -overwrite`** (the repo already ships a correct
  `createBafflesDict`), which converts the internal `rotatingZone` faceZone
  into the two overlapping `cyclicAMI` patches `ami1`/`ami2`.
- **Why it works:** `checkMesh` now shows `ami1`/`ami2` with 71,884 faces each
  and **AMI weights ≈ 1.0** (near-perfect interface coverage), and the mesh
  splits into the expected static + rotating regions coupled through the AMI.

---

## C. Initial & boundary field problems

### C1. `0/alpha.oilHeavy` was corrupt; all `0/` fields were missing patches
- **Cause:** The committed `0/alpha.oilHeavy` held 10,968 scattered 0/1 values
  (from the old broken mesh) and defined a boundary only for `impeller`. `U`,
  `p_rgh`, `k`, `omega` likewise defined only the `impeller` patch — missing
  `tank`, `ami1`, `ami2`.
- **Fix:** Reset `alpha.oilHeavy` to `uniform 0` (real values come from
  `setFields`) and added the correct boundary conditions for **all** patches
  to every field (noSlip / walls, `cyclicAMI` on ami1/ami2), using the BC
  table documented in `task.md`.
- **Why it works:** field boundaries now match the actual mesh patch set, so
  `renumberMesh` and `interFoam` can read them.

### C2. Missing `constant/turbulenceProperties`
- **Cause:** The case has `k`/`omega` fields (k-omega SST) but no file
  selecting the turbulence model, which `interFoam` requires.
- **Fix:** Created it as `RAS { RASModel kOmegaSST; turbulence on; }`.

### C3. Missing `0/nut`
- **Cause:** kOmegaSST needs the turbulent-viscosity field `nut`; only `k` and
  `omega` were present.
- **Fix:** Created `0/nut` with `nutkWallFunction` on walls, `cyclicAMI` on the
  interface.

---

## D. Solver-configuration problems (`interFoam` aborted at t=0)

### D1. `dynamicMeshDict` used an outdated `solidBody` format
- **Cause:** `solidBodyCoeffs` listed `origin`/`axis`/`omega` directly; v2312
  requires a `solidBodyMotionFunction` selector with the parameters nested in
  its coeffs sub-dict.
- **Fix:** Rewrote as `solidBodyMotionFunction rotatingMotion;
  rotatingMotionCoeffs { origin (0 0 0.495); axis (0 0 1); omega 25; }`.

### D2. Missing pressure reference for the closed domain
- **Cause:** The tank is fully closed (no fixed-pressure patch), so pressure is
  undetermined — `interFoam` aborted in `setRefCell`.
- **Fix:** Added `pRefCell 0; pRefValue 0;` to the PIMPLE dict.

### D3. Missing `pcorr` solver (moving mesh)
- **Cause:** `correctPhi`/`moveMeshOuterCorrectors` need a `pcorr` flux-
  correction solver entry, which was absent.
- **Fix:** Added a `pcorr` solver.

### D4. Missing divergence schemes
- **Cause:** `fvSchemes` lacked the MULES interface-compression term
  `div(phirb,alpha)` / `div(phi,alpha)` (unsuffixed names the solver looks up)
  and the turbulent-stress term `div(((rho*nuEff)*dev2(T(grad(U)))))`.
- **Fix:** Added all three (vanLeer for the alpha convection, linear for the
  compression and stress terms).

---

## E. Environment / permissions

### E1. Root-owned files silently blocked `setFields` → alpha stayed zero
- **Symptom:** After `setFields` reported success, `interFoam` still saw
  `alpha.oilHeavy = 0` everywhere.
- **Cause:** Files edited from Windows via the `\\wsl$` share are created as
  **root**; OpenFOAM tools run as the normal user and could **read but not
  overwrite** them, so `setFields`' write was silently lost (timestamp proved
  the file was never updated).
- **Fix:** `chown -R <user>:<user>` on the whole case, then re-ran `setFields`
  (which then correctly initialised 513,137 of 688,602 cells to
  `alpha.oilHeavy = 1`).
- **Lesson:** When editing an OpenFOAM case that lives in WSL, keep file
  ownership consistent with the user that runs the solver.

### E2. Startup FPE with a large first timestep
- **Symptom:** With `deltaT = 1e-4` the run FPE-crashed within a few steps
  (Courant only ~0.4, so not a Courant-limit issue).
- **Cause:** Starting the impeller from rest at 25 rad/s is an impulsive
  transient; too large a first step blows up the pressure/AMI coupling.
- **Fix:** Gentle start `deltaT = 1e-5` with `adjustTimeStep yes`; the step
  then auto-ramps (+20%/step) to the Courant-limited size.

### E3. `adjustTimeStep` was missing → timestep never grew
- **Cause:** `controlDict` had `adjustableRunTime yes` (that only controls
  *write* timing) but not `adjustTimeStep yes`, so `maxCo`/`maxDeltaT` were
  ignored and deltaT stayed pinned at 1e-5 (~500,000 steps to reach 5 s).
- **Fix:** Added `adjustTimeStep yes;` (with `maxCo`, `maxAlphaCo`,
  `maxDeltaT`).

---

## F. Performance

### F1. Pressure solves were the bottleneck → switched PCG/DIC to GAMG
- **Symptom:** ~40 s of wall time per step; the `pcorr` solve alone used
  ~1,600 CG iterations per timestep (350+200 per outer corrector × 3).
- **Fix:** Switched `pcorr` and `p_rgh` to **GAMG** (geometric multigrid).
- **Why it works:** GAMG converges the same solves in ~15–47 iterations
  instead of ~350 — roughly an **8× reduction** — because multigrid handles
  the low-frequency pressure error that CG struggles with on a 688k-cell mesh.
  This is the single biggest throughput win and is what makes long physical
  times practical.

---

## Current fluid properties (set per request)

| Phase | ρ (kg/m³) | μ (Pa·s) | ν = μ/ρ (m²/s) |
|---|---|---|---|
| oilHeavy | 940 | 0.329 | 3.5e-4 |
| oilLight | 820 | 0.0041 | 5.0e-6 |

> OpenFOAM's `transportProperties` takes **kinematic** viscosity, so the given
> **dynamic** viscosities were divided by density.

---

## Net result

The case meshes cleanly (~688k cells, working AMI with weights ≈ 1.0),
initialises correctly (~74.6% oilHeavy), and `interFoam` runs **stably** in
parallel: bounded Courant number, `alpha` staying within [0, 1], no fatal
errors. The remaining consideration is purely wall-clock time for the ~300 s
mixing study, addressed by GAMG + running on more cores (see
`RUN_INSTRUCTIONS.md`).
