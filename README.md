# Spinning-VOF Mixer — OpenFOAM stirred-tank simulation

A two-fluid (oil/oil) **stirred-tank mixer**: a rotating impeller stirs two
oils and we watch them mix. It's solved in **OpenFOAM v2312** with `interFoam`
(a Volume-of-Fluid solver) and a sliding **AMI** interface for the spinning
impeller region.

This README is for **running it and looking at the results**. If you're an AI
agent (or want the deep "why is it set up this way / what was fixed" detail),
read **`AGENTS.md`**.

---

## What you get

- A 3-D tank (~2.5 m tall) half-filled with a heavy oil (bottom) and a light
  oil (top), with an impeller spinning at 25 rad/s (~239 rpm).
- Output fields over time: **velocity `U`** and **phase fraction
  `alpha.oilHeavy`** (1 = heavy oil, 0 = light oil, ~0.5 = well mixed).
- Ready-made result images in **`results/`**.

Sample cut-plane images (at t = 0.2 s, a vertical slice through the centre):

| File | Shows |
|---|---|
| `results/alpha_vertical_XZ_t0p2_5050.png` | Volume fraction — the 50/50 oil split |
| `results/U_vertical_XZ_t0p2_5050.png` | Velocity — the impeller's radial jet |
| `results/U_horizontal_XY_t0p2_5050.png` | Velocity, top-down through the impeller (swirl) |

---

## 1. Prerequisites

- Linux with **OpenFOAM v2312** (ESI, from `dl.openfoam.com`), or **WSL2
  Ubuntu** on Windows with it installed.
- Load the environment in every terminal:
  ```bash
  source /usr/lib/openfoam/openfoam2312/etc/bashrc
  ```
- **Work from a path with NO spaces**, on the Linux filesystem
  (`~/openfoamspinningvof`) — not a Windows `/mnt/c/...` path. OpenFOAM
  refuses paths containing spaces.
- (Optional, to view results) ParaView: `sudo apt install -y paraview`.

Get the case:
```bash
git clone git@github.com:JGhost17/openfoamspinningvof.git
cd openfoamspinningvof
```

---

## 2. Run it (copy-paste)

```bash
source /usr/lib/openfoam/openfoam2312/etc/bashrc
cd ~/openfoamspinningvof

# 1) Build the mesh (the repo ships source only; the mesh is rebuilt here)
surfaceFeatureExtract  | tee log.surfaceFeatureExtract
blockMesh              | tee log.blockMesh
snappyHexMesh -overwrite | tee log.snappyHexMesh
renumberMesh  -overwrite | tee log.renumberMesh
createBaffles -overwrite | tee log.createBaffles     # builds the sliding AMI (ami1/ami2)
checkMesh -allTopology -allGeometry | tee log.checkMesh

# 2) Fill the tank (50/50 heavy/light oil)
setFields | tee log.setFields

# 3) Run in parallel. -np must match numberOfSubdomains in system/decomposeParDict.
decomposePar -force | tee log.decomposePar
mpirun -np 8 interFoam -parallel | tee log.interFoam
#   If mpirun says "not enough slots":  mpirun --use-hwthread-cpus -np 8 ...

# 4) Merge parallel output + export for ParaView
reconstructPar        | tee log.reconstructPar
foamToVTK             # writes VTK/  (add -latestTime for just the final frame)
```

> **Heads-up on time:** this is a fine mesh with a robust (but slow) pressure
> solver. On an 8-core laptop, **0.2 s of simulated time takes ~3 hours.** See
> [How long do runs take](#5-how-long-do-runs-take) before setting a big
> `endTime`.

**Check that a run is healthy while it goes:**
```bash
grep -E '^Time = ' log.interFoam | tail          # progress
grep 'Courant Number mean' log.interFoam | tail  # should stay below maxCo
grep 'Min(alpha' log.interFoam | tail            # alpha should stay ~0..1
```

---

## 3. Look at the results

### Quick: open the ready-made images
Open anything in `results/*.png` (from Windows they're at
`\\wsl$\Ubuntu-24.04\home\<you>\openfoamspinningvof\results\`).

### Interactive: ParaView

**Option A — ParaView inside WSL** (needs WSLg, which Win11 has):
```bash
cd ~/openfoamspinningvof
source /usr/lib/openfoam/openfoam2312/etc/bashrc
paraFoam &
```

**Option B — ParaView on Windows** (more reliable): export to VTK, then open
it from the `\\wsl$` path:
```bash
reconstructPar && foamToVTK        # in WSL
```
then in Windows ParaView open
`\\wsl$\Ubuntu-24.04\home\<you>\openfoamspinningvof\VTK\openfoamspinningvof.vtm.series`.

**Make a cross-section coloured by volume fraction (in the ParaView GUI):**
1. Select the loaded source → **Apply**; tick cell arrays `alpha.oilHeavy`,
   `U`.
2. **Filters ▸ Slice.** Set **Origin** `0, 0, 1.0` and **Normal** `0, 1, 0`
   (a vertical slice through the centre — *Z is up here*). Use Normal
   `0, 0, 1` for a horizontal, top-down slice. **Apply**.
3. Colour dropdown → **`alpha.oilHeavy`**; **Rescale to Custom Range 0–1**
   (red = heavy oil, blue = light oil, white ≈ mixed).
4. Press **▶ Play** to watch it evolve.

**Regenerate the PNGs yourself (headless, no GUI):**
```bash
reconstructPar -latestTime && rm -rf VTK && foamToVTK -latestTime
LATEST=$(ls -d VTK/openfoamspinningvof_*/ | sort -V | tail -1)
pvbatch render_vtk.py "${LATEST}internal.vtu" mytag
# -> results/alpha_vertical_XZ_mytag.png, U_vertical_XZ_mytag.png, U_horizontal_XY_mytag.png
```

---

## 4. Understanding what you're seeing

- **`alpha.oilHeavy`** is the fraction of heavy oil in each cell: **1 (red) =
  all heavy oil, 0 (blue) = all light oil, 0.5 = fully mixed.** At the start
  it's a clean split (heavy on the bottom); as the impeller stirs, the
  interface deforms and the colours blend toward 0.5. **Full mixing takes a
  long time (~300 s of simulated time)** — over a short run you mostly see the
  interface start to ripple near the impeller.
- **`U` (velocity)** shows the impeller pumping: a fast **radial jet** off the
  blade tips (~9 m/s) with recirculation loops above/below, and a swirling
  pattern when viewed top-down. This is the flow that does the mixing.
- **Coordinate note:** the tank axis is **Z (up)**. A "vertical" cut is the
  **X–Z plane**; a "horizontal" cut is the **X–Y plane**.

---

## 5. How long do runs take?

Measured on an 8-core laptop (740k cells, robust PCG pressure solver):

| Simulated time | Approx wall-clock |
|---|---|
| 0.2 s (demo) | ~3 hours |
| 1 s | ~14 hours |
| 5 s | ~3 days |
| 60 s | ~36 days |

So the **full mixing timescale (~60–300 s) is not practical on a laptop**. To
go long: use a coarser mesh, widen the AMI so the fast GAMG solver is stable
again, and/or run on a many-core machine (see `AGENTS.md` §3, §7, §10).

---

## 6. Change the settings manually

Edit the file, then re-run (mesh changes need a re-mesh; field/solver changes
usually just need a re-run).

| I want to… | Edit this | Change |
|---|---|---|
| Run longer/shorter | `system/controlDict` | `endTime` (seconds of *simulated* time; demo = 0.2) |
| Write frames more/less often | `system/controlDict` | `writeInterval` |
| Use more/fewer CPU cores | `system/decomposeParDict` **and** the `-np` in `mpirun` | `numberOfSubdomains` (they must match) |
| Change the oils | `constant/transportProperties` | `rho` and `nu` (⚠ `nu` is **kinematic** = µ/ρ) |
| Change impeller speed | `constant/dynamicMeshDict` | the `omega` table (keep the 0→speed ramp) |
| Change the fill ratio | `system/setFieldsDict` | box top-`z`: **1.17 = 50/50**; higher z = more heavy oil |
| Go faster (less accurate) | `system/fvSolution` | switch p_rgh/pcorr back to `GAMG` — but **only after widening the AMI**, or it diverges |
| Finer/coarser mesh | `system/snappyHexMeshDict` | `refinementSurfaces` levels & `refinementRegions/rotatingBox` |

> **Two rules that matter most (don't undo them):**
> 1. Keep the gentle start — `deltaT 1e-5` with `adjustTimeStep yes`. A big
>    first step crashes the impeller-from-rest start.
> 2. Split the AMI with **`createBaffles`** (not `createPatch`).
>
> Full rationale and the complete list of what was fixed is in **`AGENTS.md`**.

---

## 7. If something breaks

- **`surfaceFeatureExtract` hangs forever** → an STL is binary; the shipped
  ones are ASCII, but if you re-export from CAD run `python3 convert_stl.py`.
- **`renumberMesh` errors "Size … not equal to expected length"** → a `0/`
  field has the wrong cell count for a new mesh. Reset it:
  `foamDictionary -entry internalField -set 'uniform 0' 0/alpha.oilHeavy`,
  then re-run `setFields` after meshing.
- **`setFields` "succeeds" but alpha stays 0** → file-permission issue (files
  edited from Windows via `\\wsl$` are root-owned). Run
  `sudo chown -R $USER:$USER .` and re-run `setFields`.
- **interFoam crashes with a NaN / floating-point exception early** → usually
  the impeller-AMI gap / timestep. Keep `deltaT 1e-5` + `adjustTimeStep`, keep
  PCG for pressure, and keep the rotating-region refinement. See `AGENTS.md`
  §7-G.
- **`paraFoam` says "cannot connect to display"** → WSLg isn't wired to that
  terminal; run `wsl --update` in Windows PowerShell and reopen, or use the
  Windows-ParaView route (§3 Option B).
