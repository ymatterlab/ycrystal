# Ycrystal progress record

Last updated: 15 November 2026. M0 complete; M2 increment (boundary atoms, selection, hiding) included. Branch `develop`, pull request into `main`.

## Milestones

| Milestone | Goal | Status |
| --- | --- | --- |
| M0 | Desktop/render feasibility: Qt window, embedded VTK view, camera model, first POV-Ray render matching the view | **Complete** (see evidence and caveats) |
| M1 | File import (POSCAR/CIF/QE `ibrav=0`) and save/reopen projects | Not started |
| M2 | Navigation tools, selection, supercells, periodic bonds, cell boundary images | **In progress**: boundary images, click selection, hiding, undo/redo done; supercells, bonds, view-direction buttons pending |
| M3 | Complete figure workflow: preview, output frame, cancellation, final PNG | Not started |
| M4 | Material and environment galleries | Not started |
| M5 | Supercell drag handles, reusable styles, undo coverage | Not started |
| M6 | Installation path, launcher, user guide, release checks | Not started |

## M0 acceptance evidence

Gate: launches on the target Mint machine; a rotated, panned, non-square view is
rendered by POV-Ray without mirroring or reframing; a useful message appears when
POV-Ray is missing.

| Check | Result | How |
| --- | --- | --- |
| Application launches on the target desktop | Pass | `ycrystal` started on the Mint X11 display; window screenshot captured by `scripts/m0_evidence.py` |
| Orbit / pan / zoom with the mouse | Pass | Qt mouse events sent to the real VTK widget (`tests/test_gui.py`): left drag orbits about the focal point; Shift + left and middle drag pan (the scene follows the cursor within 1.5 px); wheel and right drag zoom; Fit keeps the orientation |
| Navigation leaves coordinates unchanged | Pass | Structure arrays are read-only; equality is checked after navigation |
| Camera model = VTK view | Pass | VTK world-to-display vs model: ≤ 1e-6 px (GUI test); 1.7e-13 px measured; VTK camera matrices vs model for random views: ≤ 1e-9 px |
| POV-Ray render = camera model | Pass | Rotated + rolled + panned views at 480×270, 240×400, 300×300: sphere centres < 1 px, correct colours (no mirroring), correct disc sizes; a mirrored or 2-px-shifted expectation fails the same check |
| Mouse-navigated view, viewport vs POV-Ray | Pass | `scripts/m0_evidence.py`: 1100×607 viewport, view turned 49.8°, panned 1.08 Å, zoomed 1.21×; all 5 atoms found, max centre error 0.073 px in VTK and 0.115 px in the POV-Ray image; colours match |
| Render from the GUI does not block | Pass | `render_png` returns immediately; POV-Ray runs in `QProcess`; result checked after the event loop delivers it |
| Image size and alpha | Pass | Exact requested dimensions; transparent background has alpha 0; opaque background is white |
| Missing POV-Ray | Pass | GUI shows guidance and `.pov`/`.ini` export still works; `ycrystal --check-renderer` prints `FAIL: POV-Ray was not found on PATH…` and exits 1 |
| Broken POV-Ray build detected | Pass | A self-built 3.8.0-alpha compiled with `-ffast-math` (previously on this machine, since removed) rejected every camera without `angle`; the self-test and render errors explain this |
| Installed renderer | Pass | `sudo apt install povray` (1:3.7.0.10-3build4) at `/usr/bin/povray`, found on `PATH` without configuration; `ycrystal --check-renderer`: PASS, centres within 0.14 px; runs under the package's restricted `povray.conf` (writes only to `/tmp` and `.`) |
| Paths with spaces/non-ASCII | Pass | Render result copied to `…/Résultat final/render ü.png`; export to `exported scene ü.pov` |
| Automated suite | 52 passed, 0 skipped | `pytest -q -rs` with the installed `/usr/bin/povray` (no override); `ruff check` clean |
| Fresh install from `constraints.txt` | Pass | New venv on system Python 3.12.3 via `uv`; 52 tests passed |

Evidence files (local, not tracked: `artifacts/m0/`): `window.png` (application
screenshot), `viewport.png` and `render.png` (same view), `comparison.png`
(side by side), `render_atoms_markers.png` (analytic centres drawn on the POV-Ray
image), `scene.pov`/`scene.ini` (exported scene), `report.json` (environment, cameras,
per-atom errors). Regenerate with the command below.

### Caveats and unverified items

- POV-Ray 3.8 is not verified: no working 3.8 build is available on this machine
  (the self-built one was miscompiled and has been removed).
- `povray` prints a harmless warning when `~/.povray/3.7/povray.conf` does not exist.
- Mouse interaction was driven by synthetic Qt events through the real widget, not by
  a person. A hands-on check of drag feel is recommended but not a gate.
- `python3 -m venv` with the system interpreter needs `python3.12-venv` (not installed
  on the development machine); the verified route used `uv venv`.
- The CI workflow (`.github/workflows/ci.yml`) has not run yet; it needs a push.
- Not covered by M0 (later milestones): file import, projects, bonds, supercells,
  selection, view-direction buttons, render cancellation UI, preview, output-aspect
  frame, material presets.

## M2 increment: boundary atoms, selection, hiding (requested ahead of M1)

| Check | Result | How |
| --- | --- | --- |
| Boundary images like VESTA | Pass | SrTiO3 (5 input atoms) shows 15: Sr on all 8 corners, O on all 6 face centres, 1 Ti; each displayed position = input position + integer lattice offset |
| Wrapping and tolerance | Pass | Atoms given outside the cell are wrapped; fractional 0.9999999 is drawn at 0 and 1; no images along non-periodic axes; general positions get none |
| Boundary toggle | Pass | View ▸ Show Boundary Atoms off shows the 5 input atoms at their input positions; undoable |
| Click selection | Pass | Click without drag selects the front-most ball (analytic ray–sphere pick on the shared camera); Ctrl+click toggles; click on empty space or Esc clears; a drag never selects |
| Selection information | Pass | Status bar: element, label, atom number, image offset, fractional and Cartesian coordinates; multiple selection shows counts |
| Hide one of several equivalent balls | Pass | Delete (or Backspace) in the 3D view hides only the selected ball, e.g. one Sr corner leaves the other 7; the POV export omits it and notes the count; structure coordinates unchanged |
| Undo/redo | Pass | Ctrl+Z / Ctrl+Shift+Z (Ctrl+Y) for hide, Show All Atoms, and the boundary toggle; hidden IDs survive toggling |
| Automated suite | 66 passed, 0 skipped | `pytest -q -rs` with `/usr/bin/povray` |

## Commands

```bash
# setup (system Python; see README for the reason)
uv venv --python /usr/bin/python3.12 .venv
VIRTUAL_ENV=$PWD/.venv uv pip install -e ".[dev]" -c constraints.txt

# launch
.venv/bin/ycrystal                      # or: --sample triclinic

# checks (POV-Ray found on PATH; override with --povray or $YCRYSTAL_POVRAY)
.venv/bin/ycrystal --check-renderer
.venv/bin/ruff check src tests scripts
.venv/bin/python -m pytest -q -rs
.venv/bin/python scripts/m0_evidence.py    # writes artifacts/m0/
```

## Environment baseline (development machine)

- Linux Mint 22.1 (Xia), kernel 6.8.0-139, X11 Cinnamon session, 1920×1080 at 96 dpi.
- Intel Meteor Lake integrated graphics, Mesa 25.2.8, OpenGL 4.6.
- Python 3.12.3 (`/usr/bin/python3.12`), venv created with uv 0.8.3.
- Qt / PySide6-Essentials 6.12.0, VTK 9.7.2, PyVista 0.49.2, PyVistaQt 0.13.2,
  QtPy 2.4.3, ASE 3.29.0, NumPy 2.5.4, Pillow 13.0.0 (full pin list: `constraints.txt`).
- POV-Ray 3.7.0.10 (distribution package `1:3.7.0.10-3build4`, `/usr/bin/povray`),
  include files in `/usr/share/povray-3.7/include`.

## Architecture decisions

- **System Python, not Miniconda.** With Miniconda's interpreter, its bundled
  `libstdc++` (GLIBCXX ≤ 3.4.29) is loaded before the system one, and Mesa 25 cannot
  initialise GLX: the VTK window crashed.
- **PySide6-Essentials only** (no Addons/WebEngine). `QT_API=pyside6` is forced
  before PyVistaQt/QtPy are imported.
- **Ycrystal's own POV-Ray writer from M0.** ASE's exporter frames the image itself
  and writes camera-frame coordinates, so it cannot reproduce an arbitrary panned,
  non-square view. ASE remains the structure library; its exporter is a reference only.
- **Camera export:** explicit `location`/`direction`/`right`/`up` vectors for an
  orthographic camera (no `look_at`, `sky` or `angle`), so POV-Ray does not re-derive
  the basis or change handedness. World coordinates stay right-handed in Å.
  `#version 3.7;`, no include files.
- **Colours:** written as sRGB through a small macro and converted to linear light
  (`assumed_gamma 1.0`, PNG `File_Gamma=sRGB`).
- **Shared geometry:** `core.scene.build_geometry` resolves atoms (stable IDs
  `(source_atom, image)`), radii, colours and cell edges once; the VTK viewport and the
  POV writer both consume it. Atoms are drawn with `vtkGlyph3DMapper` (instancing);
  cell edges are tubes with the same radius as the POV cylinders and cast no shadows.
- **Render jobs:** per-job temporary directory, ASCII names, POV-Ray run with
  cwd = job directory and every output option in the job `.ini` (user `povray.ini`
  defaults such as `Display=On` cannot interfere). The PNG is then copied to the
  user's path. GUI renders use `QProcess`.
- **Renderer discovery:** GUI setting → `$YCRYSTAL_POVRAY` → `povray` on `PATH`.
  `--check-renderer` / Render ▸ Check Renderer renders a tiny reference scene and
  verifies sphere positions and colours.
- **Output framing (M0):** the image uses the viewport's aspect ratio; the user sets
  the width. An explicit output-aspect frame comes with the figure workflow (M3).
- **Keys:** VTK/PyVista default keys (e.g. `q` closes, `w` wireframe) are disabled in
  the viewport; application shortcuts (F = Fit, Ctrl+R = Render, Delete = hide,
  Esc = select none, Ctrl+Z / Ctrl+Shift+Z = undo/redo) live on the window.
- **Boundary policy:** along periodic axes atoms are wrapped into the cell (fractional
  tolerance 1e-3) and images on faces/edges/corners are added. A displayed atom's ID
  is `(source atom, image offset)` with position = input + offset @ cell, so IDs are
  stable when display settings change.
- **Hiding is presentation state:** `SceneSettings.hidden` holds displayed-atom IDs;
  hidden balls are absent from the shared geometry, hence from the view and POV
  export. The structure is never modified (atom deletion/editing remains a later,
  separate feature).
- **Picking** uses an analytic ray–sphere intersection with the shared camera model
  (`core/picking.py`), not VTK pickers; a click is a left press/release that moves at
  most 3 px. The selection highlight is a translucent shell drawn only in the live view.
- **Undo/redo:** `QUndoStack` with one command type that swaps `SceneSettings`.

## Next bounded action

Start M1: format detection and readers for POSCAR/CONTCAR, CIF and QE `ibrav=0`, the
versioned project schema with embedded structure and camera, and save/reopen.
