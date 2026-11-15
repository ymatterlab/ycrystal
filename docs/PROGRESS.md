# Ycrystal progress record

Last updated: 15 November 2026. M0, M1, M2, and M3 complete and merged into `main` (M3 in PR #8). Repository made private; pre-commit.ci and the CI badge removed.

## Milestones

| Milestone | Goal | Status |
| --- | --- | --- |
| M0 | Desktop/render feasibility: Qt window, embedded VTK view, camera model, first POV-Ray render matching the view | **Complete** (see evidence and caveats) |
| M1 | File import (POSCAR/CIF/QE `ibrav=0`) and save/reopen projects | **Complete** (see evidence) |
| M2 | Navigation tools, selection, supercells, periodic bonds, cell boundary images | **Complete** (see evidence; drag handles are M5) |
| M3 | Complete figure workflow: preview, output frame, cancellation, final PNG | **Complete** (see evidence; full galleries are M4) |
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

## M1 acceptance evidence

Gate: equivalent reference inputs give the same scientific geometry; a project opens
after its source file is moved; unsupported QE/CIF cases are explained in the
interface and the guide.

| Check | Result | How |
| --- | --- | --- |
| Format detection and manual choice | Pass | Name + content (`test_readers.py`); misleading extensions resolved by content; undetectable files ask for a format; *File ▸ Open As…* / `--format` override |
| Si: POSCAR (primitive) = QE (`celldm(1)`, alat cell, crystal positions) | Pass | Cells equal the analytic fcc matrix (QE within 1e-8 Å); atoms matched modulo lattice translations |
| Si: conventional CIF (F d -3 m) = primitive POSCAR × P | Pass | `P = [[-1,1,1],[1,-1,1],[1,1,-1]]` recorded; 8 CIF atoms equal the analytic diamond positions |
| MgB2: Cartesian POSCAR = CIF (24 explicit symmetry operations) = QE (angstrom cell) | Pass | Cells equal the analytic hexagonal matrix; space group 191 recorded |
| SrTiO3: POSCAR (selective dynamics) = CIF (symbol, uncertainties) = QE (`A`, alat, labels `O1`/`O_2`, `if_pos`) | Pass | Equal geometry; identical movable flags from VASP and QE; labels kept separately from elements |
| Triclinic: POSCAR (negative scale = volume, Cartesian) = CIF (P1) = QE (bohr cell and positions) | Pass | Cell and positions equal the analytic triclinic formula within 1e-8 Å |
| VASP 4 without element line | Pass | Element mapping is requested; the misleading comment "In plane strained GaN" yields no guess; the mapping is recorded in provenance |
| Rejections with explanations | Pass | CIF partial occupancy (lists sites), overlapping sites, unknown block; QE `ibrav = 2`, `crystal_sg`, missing `CELL_PARAMETERS`; ambiguous QE label (`Cb`) asks for the element; truncated POSCAR ("…3 atoms, but only 1 coordinate line…"); not-a-structure file |
| Failed open keeps the current scene | Pass | Structure, geometry, and camera unchanged after each rejected file and after a damaged project (`test_gui_files.py`) |
| Project round trip | Pass | Exact equality of cell, positions, numbers, occupancy, labels, movable flags, metadata, display settings, hidden atoms, environment, camera, output |
| Reopen after the source file is moved | Pass | Source directory deleted; the project reopens in a new window with identical coordinates, hidden atoms, camera, and output settings (`test_project.py`, `test_gui_files.py`) |
| Versioning and damage | Pass | Newer schema refused with an update message; invalid JSON (with line), wrong format, missing schema, missing sections, inconsistent symbols, wrong array lengths reported clearly; atomic save leaves no temporary files |
| Unsaved changes | Pass | Title shows `*` for camera, display-setting, or output changes (undo back to the saved state clears it); close and open ask Save / Discard / Cancel; Cancel (or a cancelled Save dialog) keeps the window and scene |
| Documented limitations | Pass | *Help ▸ Supported File Formats* and `docs/FORMATS.md` |
| Automated suite | 127 passed, 0 skipped | `pytest -q -rs` with `/usr/bin/povray`; `ruff check` clean |

Hands-on check on the Mint display: `ycrystal tests/fixtures/MgB2.cif` starts with the
file open; opening `SrTiO3.pw.in` shows QE labels in the selection information;
opening `partial_occupancy.cif` shows the explanation while the scene stays.

### M1 caveats

- ~~The rendered image takes its aspect ratio from the window.~~ Resolved in M3: an
  explicit output size and frame; projects reopen with the same framing in any window.
- The view counts as part of the project: rotating marks it modified.
- POSCAR element lines with POTCAR suffixes (`Na_pv`) are reduced to the element; the
  raw token is not kept as a label.

## M3 acceptance evidence

Gate: the same saved scene produces correctly framed preview and final images; Cancel
and failure recovery work; dimensions and alpha pass checks; the alpha catalog is
usable from import through project save/reopen and PNG output.

| Check | Result | How |
| --- | --- | --- |
| Saved scene → framed preview and final images | Pass | `test_saved_scene_renders_framed_preview_and_final`: scene saved from a 1150 × 700 window, reopened in a 900 × 820 window; the output camera is restored exactly; the 480 × 300 preview and the 640 × 400 final PNG both have every sphere centre within 1 px of the output camera's projection, correct colours, and a transparent background |
| Output frame | Pass | Largest rectangle with the output aspect ratio inside the view (4 % margin), centred, dimmed outside; the output camera (view camera × frame/height ratio) survives window resizes and output-size changes; resizing does not mark the project modified (`test_gui_render.py`) |
| Live view ↔ POV-Ray through the frame | Pass | Non-square 480 × 320 output in a differently shaped window: POV-Ray centres < 1 px from the model; live-view centres mapped through the frame agree < 1 px (`test_render_from_gui_matches_output_frame`). `scripts/m0_evidence.py` (mouse-navigated, 626 × 417 output): 0.070 px POV-Ray, 0.103 px live view |
| Output size controls | Pass | Width/height 16–8000 px, aspect presets, swap; toolbar label; the preview keeps the output aspect (480 px long side); not undoable but marks the project modified |
| True POV-Ray preview | Pass | Same exporter and output camera at preview size, antialiasing off; F5 / button / automatic after changes (600 ms pause); errors shown in the dock without dialogs |
| Serialized previews, superseded work cancelled | Pass | One preview process at a time: a newer request cancels the running job and replaces any pending one (`test_queue_supersedes_running_and_pending_jobs`: jobs A, B, C → A cancelled, B never started, C rendered; no job directories left) |
| Stale-result suppression | Pass | Each preview carries the scene revision; a result for an older revision is discarded and the dock says so (`test_stale_preview_is_discarded`) |
| Final render, progress, Cancel | Pass | `QProcess`, status-bar progress from POV-Ray's `Rendered N of M pixels` lines (`Verbose=on`); Cancel stops it, leaves the destination untouched, shows no error, re-enables Render (`test_cancel_final_render`) |
| Failure recovery | Pass | A failing renderer shows an explanation; the next render succeeds with the right size (`test_failed_render_then_successful_render`) |
| Dimensions and alpha | Pass | Final and preview sizes exact; transparent background → alpha 0, opaque presets → 255; glass lets alpha through (correct) |
| Alpha catalog | Pass | 5 materials (matte, satin = previous finish, glossy, metallic, glass with `interior { ior 1.45 }`) and 3 backgrounds (white, transparent, dark grey with light cell edges) as JSON manifests; all 15 combinations render with POV-Ray 3.7 (`test_presets.py`); undoable; live view uses each material's approximation |
| Readable export | Pass | `.pov` records Ycrystal and POV-Ray versions and any required standard includes (none for the built-ins; include handling tested with a substituted manifest); `.ini` sets every output option, `Output_Alpha` for transparent backgrounds, `Verbose=on` |
| Project restoration | Pass | Schema 3 stores material, background preset, transparency, explicit output size; schema-1/2 files open unchanged (satin, transparent preset when their output was transparent); unknown presets refused with an update message |
| Packaging | Pass | A non-editable wheel contains the 8 preset manifests (`package-data`) |
| Automated suite | 202 passed, 0 skipped | `YCRYSTAL_REQUIRE_INTEGRATION=1 pytest -q -rs`; doctests incl. presets and progress parser; `scripts/docs_examples.py`; `zensical build --clean --strict`; `pre-commit run --all-files` |

Hands-on on the Mint display (`artifacts/m3/`): SrTiO3 2 × 2 × 1 with glass atoms on dark grey,
4:3 output frame, automatic preview "Up to date · 480 × 360 px · 1.4 s", 1200 × 900
render in 11.2 s showing refraction through the glass.

### M3 caveats

- Previews use full quality without antialiasing; glass, metallic reflection, and large
  supercells make them slower (seconds). Automatic previews are on by default and can be
  switched off in the preview dock (the choice is remembered).
- POV-Ray reports progress about once per second; short renders show only 100 %. A
  successful render always ends at 100 % (added after a CI run whose last report was 99 %).
- Cancel kills the POV-Ray process; nothing partial is kept.
- The frame margin (4 %) is fixed. Output size is not undoable.
- One material for all atoms and bonds; per-element/per-atom assignment, galleries with
  POV-Ray thumbnails, more presets, and lighting controls are M4.
- `python -m doctest docs/development/examples.md` reports fence-line mismatches (the
  closing ``` is read as expected output); the outputs themselves match. Pre-existing on
  `main`; CI does not doctest Markdown.

## M2 acceptance evidence

Gate: triclinic and hexagonal examples preserve correct geometry, stable selection, and
original coordinates; expected bond/image counts; reversible repetition changes;
navigation does not modify coordinates. The first increment (boundary atoms,
selection, hiding, undo) is listed in the next section.

| Check | Result | How |
| --- | --- | --- |
| Orthogonal SrTiO3, n × n × n (n = 1–3) | Pass | (n+1)³ Sr, n³ Ti, 3n²(n+1) O; 6n³ Ti–O and 12n²(n+1) Sr–O bonds; equal to a brute-force distance search over the displayed atoms; no duplicate bonds (`test_supercells_bonds.py`) |
| Hexagonal MgB2, n × n × m | Pass | (n+1)²(m+1) Mg, 2n²m B; (3n² − 2n)·m B–B bonds (honeycomb); brute force agrees |
| Diamond Si (conventional cell) | Pass | (n+1)³ + 3n²(n+1) + 4n³ atoms (18 at 1×1×1, as VESTA); 16n³ bonds, all 2.3517 Å |
| Triclinic cell | Pass | 5n³ atoms at general positions; displayed bonds equal brute force for 1×1×1, 2×3×1, 2×2×2; periodic bonds unique (no reverse pairs) and complete against a search over neighbouring cells |
| Stable IDs, reversibility, coordinates | Pass | Every atom of 1×1×1 has the same ID and position at 3×3×3; 1 → 3 → 1 reproduces IDs, positions, and bonds exactly; hidden IDs persist across repetition changes; structure arrays unchanged |
| Non-periodic axes and molecules | Pass | No repetition along non-periodic axes; a molecule shows O–H bonds only |
| Cell edges | Pass | All unit cells (grid lines), outline of the block, or the original cell; counts checked (e.g. 27 grid lines at 2×2×2) |
| Repetition controls | Pass | Spin boxes a/b/c (1–20), "− all", "+ all", "1 × 1 × 1"; each change one undo step; the panel follows undo/redo; the view is refitted to the new block; selection kept by ID (`test_gui_scene.py`) |
| Large-expansion warning | Pass | Above 20,000 displayed atoms Ycrystal asks before applying (estimate computed without building geometry); declining leaves everything unchanged |
| Bonds panel | Pass | Show/hide, tolerance (× sum of covalent radii; consecutive edits merge into one undo step), radius, per-element-pair switches with per-cell counts and lengths |
| View directions | Pass | a, b, c, x, y, z (Shift: opposite side); the axis points at the viewer with the next axis up (e.g. down c: a right, b up); triclinic directions follow the lattice vectors; result framed |
| POV-Ray export | Pass | Bonds as half cylinders textured like their atoms; grid edges; render matches the live view (`artifacts/m2/`) |
| Projects | Pass | Schema 2 stores repetitions, cell mode, and bond settings; schema-1 projects open with bonds off, exactly as saved |
| Automated suite | 162 passed, 0 skipped | `pytest -q -rs`; `pre-commit run --all-files` clean |

Display benchmark (`scripts/benchmark_scene.py`, SrTiO3, Intel Meteor Lake integrated
graphics, Mesa 25.2.8, 1100 × 700 viewport, 8× MSAA). "Drag step" is a synthetic
left-button drag through VTK's interactor with every step repainted before the next.

| Cells | Atoms | Bonds | Build (s) | Load (s) | Drag step (ms) | Live detail |
| --- | --- | --- | --- | --- | --- | --- |
| 2³ | 71 | 192 | 0.02* | 0.16 | 38 | 40×28 spheres |
| 6³ | 1,315 | 4,320 | 0.03 | 0.09 | 72 | 40×28 |
| 10³ | 5,631 | 19,200 | 0.07 | 0.22 | 84 | 24×16 |
| 14³ | 14,939 | 51,744 | 0.17 | 0.41 | 88 | 16×10 |
| 16³ | 22,065 | 76,800 | 0.26 | 0.50 | 105 | 16×10 |
| 20³ | 42,461 | 148,800 | 0.59 | 0.82 | 150 | 16×10 |

\* first call 0.49 s (one-time import of ASE's neighbour list). The live view lowers
sphere and bond tessellation above 2,000 and 8,000 atoms (POV-Ray always renders exact
spheres); without this, 14³ took 232 ms per step and 20³ 640 ms. The soft limit of
20,000 atoms keeps a drag step near 100 ms or less on this hardware.

### M2 caveats

- The default bond rule (1.1 × sum of covalent radii, metal–metal off in compounds)
  also bonds Sr–O in perovskites; switch the pair off in the Bonds panel if not wanted.
- Bonds are drawn only between displayed atoms (no bonds to atoms beyond the boundary).
- Each synthetic drag step costs at least ~38 ms even for tiny scenes; most of it is
  spent in Qt while PyVistaQt's `QOpenGLWidget` presents the frame. It predates M2 and
  is not investigated further here; VTK's own `QVTKRenderWindowInteractor` is the
  documented fallback if real interaction proves sluggish.
- Supercell drag handles (M5), reciprocal-axis view directions, and lighting (M4,
  POV-Ray currently casts hard shadows) are not part of M2.

## M2 first increment: boundary atoms, selection, hiding (requested ahead of M1)

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

## Maintenance: repository tooling (15 November 2026)

No product behaviour changed and no milestone status changed. Inspired by quacc's setup,
with deliberate differences: safe Ruff fixes only (no `--unsafe-fixes`), monthly
updates with at most three open pull requests, and no automatic merging.

| Item | Result | How |
| --- | --- | --- |
| `.pre-commit-config.yaml` | Clean on all tracked files | ruff-check `--fix` and ruff-format v0.17.5; pre-commit-hooks v6.0.0 (trailing whitespace, end of file, check-yaml, large files > 250 KB with `--enforce-all`); local `ruff-version-sync` hook; pre-commit.ci autoupdate monthly. Fixtures exempt from whitespace fixers |
| Ruff version sync | Pass | Hook rev v0.17.5 = `ruff==0.17.5` in constraints.txt; the sync hook exits 1 on a mismatch in either direction (checked) |
| Mechanical formatting | 25 files reformatted, separate commit | `ruff format` output only; syntax trees identical before and after (checked with `ast`); 127 tests pass |
| Dev dependency | `pre-commit>=4` in the dev extra | constraints.txt: `pre-commit==4.7.0` and its 8 dependencies added; all existing pins unchanged |
| CI | Valid; not yet run on GitHub | New lightweight `pre-commit` job (no Qt/VTK/POV-Ray). `test` job keeps Ubuntu 24.04 / Python 3.12 / Xvfb / POV-Ray 3.7 and adds `YCRYSTAL_REQUIRE_INTEGRATION=1`. Read-only permissions, superseded PR runs cancelled, timeouts, pip and hook caching; push trigger limited to `main` (PRs tested once). Actions moved to checkout v7, setup-python v7, cache v6 after the last `main` run warned that the Node 20 versions are deprecated. `actionlint` 1.7.12 and the GitHub-workflow schema: no problems |
| No silent skips | Pass | With `YCRYSTAL_REQUIRE_INTEGRATION=1`: no display → usage error (exit 4); no POV-Ray → 6 rendering tests error; everything present → 127 passed. Without it: 25 GUI tests / 6 rendering tests skip as before |
| Dependabot | Valid; not yet run | pip and github-actions, monthly, minor+patch grouped, majors separate, ≤ 3 open PRs each, Ruff ignored (owned by the hook). pip covers `pyproject.toml` and `constraints.txt` (Dependabot reads any requirements-style root `*.txt`; confirmed in dependabot-core and the docs). `increase-if-necessary` bumps exact pins without raising `pyproject.toml` lower bounds. Dependabot schema: valid |
| Constraints regeneration procedure | Pass | Documented commands rehearsed in a fresh system-Python venv: install, 127 tests in strict mode, freeze identical to the current pins |
| README badges | Added | CI status (main), MIT license, early development; all three URLs resolve. No pre-commit.ci badge: not activated (badge reports "unknown") |
| Contributor guidance | Added | `CONTRIBUTING.md`, `.github/pull_request_template.md` |

Owner setup still needed (configuration is committed, services are not activated):
enable pre-commit.ci for the repository, check Dependabot settings (version updates,
alerts, security updates), and optionally require the `pre-commit` and `tests` checks
on `main`. The new workflow, Dependabot, and pre-commit.ci have not run yet; local
success does not prove them.

### Update: private repository (15 November 2026)

The repository was made private. pre-commit.ci is free only for public repositories, so
its `ci:` section was removed from `.pre-commit-config.yaml`; hooks are now updated
manually with `pre-commit autoupdate` (CONTRIBUTING.md). The README's CI badge was
removed (it does not render for viewers without access); the static license and status
badges remain. GitHub Actions and Dependabot continue unchanged (private repositories
on GitHub Free have 2,000 Actions minutes per month; one CI run uses about 4). On
GitHub Free, the "Protect main" ruleset is not enforced while the repository is
private; it is kept for a return to public visibility. The entries above describe the
setup at the time.

## Documentation increment (15 November 2026)

No runtime behavior, public signatures, or product milestone status changed. The
user guide now supports M0–M2 features; this does not complete M6.

M2 was subsequently merged into main in PR #5 (`49b50ec`). This branch now includes
that merge and documents its repetitions, periodic bonds, cell modes, view directions,
and schema-2 projects. Historical checks below describe the initial increment;
updated integration verification is recorded separately.

### Audit of the interrupted work

- The working tree already contained substantial NumPy-style docstrings in 19 Python
  source files, a `docs` dependency extra and NumPy Ruff rules in `pyproject.toml`,
  and an untracked draft `zensical.toml`. Runtime syntax trees matched HEAD when
  documentation strings were removed. That work was preserved and refined.
- The draft site referred to pages that did not exist. There was no first-figure
  tutorial, architecture/writing guide, generated reference pages, visual asset,
  documentation CI job, or completed build evidence.
- No `AGENTS.md` was present in this checkout or its ancestor directories.
  `docs/IMPLEMENTATION_PLAN.md` was absent (and is ignored as a private planning
  file), so it could not be consulted. Actual source, tests, `FORMATS.md`, and this
  progress record supplied the implementation evidence.
- Existing pre-commit, Dependabot, badge, and application-test configuration was
  retained. CI was extended only with a docs job and display-independent examples.

### Delivered files

- Source docstrings: `app.py`, `__main__.py`; core structure, scene, camera, picking,
  samples, and comparison; I/O readers/projects; GUI window/commands; viewport;
  POV writer, discovery, jobs, process, self-test, and image checking.
- Site: `zensical.toml`, `docs/index.md`, five pages in `docs/guide/`, three in
  `docs/development/`, seven curated `docs/reference/` pages, and
  `docs/assets/perovskite.png` (actual 640 × 400 POV-Ray output, about 63 KB).
- Verification/reproduction: `docs/requirements.txt` (separate 25-package docs-only
  lock), `scripts/docs_examples.py`, `scripts/docs_render_example.py`.
- Integration: docs extra and scoped NumPy Ruff checks in `pyproject.toml`, a docs CI
  job and example check in `.github/workflows/ci.yml`, generated-output ignores,
  shorter `README.md`, contributor links, and the precise CIF occupancy tolerance in
  `FORMATS.md`. Main application constraints and existing hooks were not replaced.

### Verification actually performed

| Check | Result and evidence |
| --- | --- |
| Runtime unchanged | All 19 modified `src/` Python files have identical ASTs to HEAD after removing documentation strings; no public names/signatures changed |
| Application suite | `YCRYSTAL_REQUIRE_INTEGRATION=1 .venv/bin/python -m pytest -q -rs`: **127 passed, 0 skipped**, 306.09 s; real X11 Qt/VTK and `/usr/bin/povray`. The initial sandboxed run aborted because it could not access the display; the successful run had display access |
| NumPy examples | `python -m doctest` on structure, scene, camera, picking, readers, and project: **37 examples passed**; `python scripts/docs_examples.py`: passed, with temporary files cleaned up, no display or renderer |
| Genuine visual asset | `python scripts/docs_render_example.py`: rendered the tracked 640 × 400 SrTiO3 image with POV-Ray 3.7; inspected the image. Script owns job cleanup and supports an alternate output path |
| Tutorial rehearsal | Scripted real Qt events exercised orbit, pan, zoom, Fit, corner selection, Delete, undo, project save/reopen, POV export, and asynchronous GUI render. 5 scientific atoms / 15 displayed; hiding one gave 14; PNG **640 × 376** as the viewport required; coordinates unchanged; render job removed. Evidence under ignored `artifacts/docs/tutorial/`: project, POV/INI, PNG, window screenshot, `report.json` |
| Renderer diagnostic | `/usr/bin/povray` 3.7.0.10.unofficial passed; sphere centres within **0.14 px** |
| Static docs-only build | Fresh `/tmp/ycrystal-docs-env` with Zensical 0.1.1, mkdocstrings-python 2.0.11, and 23 transitive dependencies. Confirmed Qt, VTK, ASE, NumPy, and Ycrystal were not installed. `zensical build --clean --strict`: **no issues** |
| Broken-link controls | Temporarily added a missing page, missing anchor, unresolved API cross-reference, and nonexistent API directive, separately. Every strict build failed; restored the source afterward |
| Rendered reference | Inspected home and camera-reference HTML in headless Chrome; checked all 19 generated HTML pages: no broken local links/anchors or duplicate IDs. Confirmed constructor/method signatures and curated members, without inherited Qt/VTK methods |
| Preview | `zensical serve --dev-addr 127.0.0.1:8765`: home, tutorial, camera reference, and PNG returned HTTP 200; temporary server stopped afterward |
| Maintenance checks | Ruff lint, Ruff format, and `git diff --check` passed. Existing pre-commit hooks passed on tracked **and new** files, including image size, YAML, and Ruff pin sync. CI YAML parsed locally; GitHub execution remains unverified |

Preview and build from the checkout root:

```bash
.venv/bin/python -m pip install -e ".[docs]" -c constraints.txt -c docs/requirements.txt
.venv/bin/zensical serve
.venv/bin/zensical build --clean --strict
```

For the docs-only installation, exact commands and the dependency-update procedure,
see [Documentation workflow](development/documentation.md). The first-figure workflow
is in [the user guide](guide/first-figure.md).

### Discrepancies documented without changing behavior

- The previous progress wording and draft GUI docstring said rendering returned
  immediately. In fact `render_png` queries the renderer version synchronously (up
  to 15 s) and prepares files before starting `QProcess`. The render itself is
  asynchronous. The GUI's renderer check is synchronous.
- Frozen structure arrays do not make metadata immutable: the constructor retains
  the metadata dictionary, and `replace` shallow-copies it. `Project` is mutable.
- Direct `Structure` construction permits occupancy up to `1 + 1e-6`, does not reject
  non-finite coordinates/occupancies, and does not validate `pbc` length. The CIF
  reader rejects occupancy below `1 - 1e-3`, rather than every value below 1. These
  existing tolerances/validation limits are now explicit.
- The renderer self-test converts discovery/render failures to a result, but file
  preparation, image decoding, and measurement errors may propagate. A preparation
  failure after creating a job directory can leave partial files. GUI PNG-copy
  failures can leave a `.part` file; the GUI still removes the render job.
- Project metadata sanitization does not recursively sanitize values converted from
  NumPy; non-finite values can make saving fail. Optional scene/environment/output
  sections default on load; missing required structure entries fail. The old M1
  evidence wording “missing sections” was too broad and is clarified above.
- `core.compare.supercell` is a comparison helper and accepts non-singular integer
  transforms, including orientation reversal; it is not a GUI supercell feature.
  Structure comparison wraps fractional differences component by component, rather
  than performing a general minimum-image search in skewed cells.

### Still unverified / separate publication work

- No human hands-on usability session, fresh system-package installation, Wayland,
  other platforms, or POV-Ray 3.8 validation was performed in this increment. The
  GUI rehearsal used synthetic events through the actual widgets; rendering,
  structure/project output, and dimensions were checked.
- The new docs CI job has not run on GitHub. The site is not deployed. Hosting,
  canonical URL/base path, and deployed navigation/asset checks remain separate;
  [publication notes](development/documentation.md#publication) describe the steps.

## Integration with merged M2 (15 November 2026)

Fetched `origin/main` at `49b50ec` (M2 merged in PR #5) and merged it into
`docs/docstrings`. Resolved overlapping documentation/source files while preserving
M2 runtime code. Every `src/` syntax tree matches `origin/main` after stripping
string documentation. No application behavior or public signatures changed relative
to the merged M2 implementation.

Updated the user guide, first-figure labels, architecture, project-format guide,
curated references, and docstrings for display repetitions, cell-edge modes, periodic
bonds, view directions, undo merging, and schema-2 projects. Added NumPy docstrings
for the new bond models/search and scene-panel interfaces; no lint rules weakened.
The example script now checks 2 × 2 × 2 SrTiO3 (71 atoms, 192 bonds), and the tracked
640 × 400 image was regenerated with the current default bond display.

Verification on the integrated tree:

- Full strict application suite with X11/Qt/VTK and POV-Ray: **162 passed, 0 skipped**
  in 30.24 s (`/tmp/ycrystal-m2-docs-tests.log`).
- Clean strict docs-only build: no issues. Source doctests and
  `scripts/docs_examples.py`: passed. Asset regeneration: passed.
- First-figure rehearsal on the actual Qt/VTK widgets: passed selection, hide/undo,
  save/reopen, scene export, and PNG render (640 × 509 at the new dock layout).
  Renderer check: passed within 0.14 px. Outputs remain in `artifacts/docs/tutorial/`.
- Ruff and existing pre-commit checks: passed on the integrated tree.
- Earlier M2-separate-branch statements in the initial audit are historical;
  M0–M2 are now merged. M3 remains next; documentation hosting is still separate.

## Commands

```bash
# setup (system Python; see README for the reason)
uv venv --python /usr/bin/python3.12 .venv
VIRTUAL_ENV=$PWD/.venv uv pip install -e ".[dev]" -c constraints.txt

# launch
.venv/bin/ycrystal                      # or: --sample triclinic

# checks (POV-Ray found on PATH; override with --povray or $YCRYSTAL_POVRAY)
.venv/bin/ycrystal --check-renderer
.venv/bin/pre-commit run --all-files       # Ruff lint/format, file checks, Ruff sync
YCRYSTAL_REQUIRE_INTEGRATION=1 .venv/bin/python -m pytest -q -rs   # no silent skips
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
- **Output framing (M0, superseded in M3):** M0–M2 rendered the viewport's aspect ratio.
  Since M3 the output size is explicit and the GUI shows the output frame.
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
- **Undo/redo:** `QUndoStack` with one command type that swaps `SceneSettings`;
  commands with the same merge key (bond tolerance, bond radius) merge when consecutive.
- **Supercells (M2):** repetitions live in `SceneSettings` and are always expanded from
  the original structure; boundary images are added on the faces of the repeated block.
  Image offsets stay relative to input positions, so IDs, selection, and hidden atoms
  are stable across repetition changes.
- **Bonds (M2):** `core/bonds.py` searches the original cell once with ASE's
  neighbour list (any cell shape) and stores `(i, j, integer shift)` without reverse
  duplicates; `build_geometry` maps them onto displayed images and gives both renderers
  explicit endpoint index pairs. Rule and per-pair overrides are in `BondSettings`.
- **Live-view level of detail (M2):** sphere/bond tessellation drops at 2,000 and 8,000
  displayed atoms; bonds use the same GPU instancing (`vtkGlyph3DMapper`) as atoms.
- **Scene panel (M2):** `gui/panels/scene_panel.py` emits requests only; the window turns
  them into undoable commands and syncs the panel with signals blocked.
- **Import (M1):** ASE parses; `io/readers.py` adds detection, provenance (path, name,
  format, SHA-256, size, time, reader version, block, element mapping), and checks.
  Questions (format, data block, element mapping) are exceptions that the GUI answers
  and retries, so the readers stay GUI-free. Ycrystal's QE reader is assembled from
  ASE's card parsers because ASE's `read_espresso_in` ignores `A` (it looks up an
  upper-case key in a lower-cased namelist) and resolves labels permissively.
- **Comparison:** `core/compare.py` compares lattice matrices directly and matches atoms
  by element and fractional position modulo lattice translations.
- **Projects:** `io/project.py`, JSON schema 2 (schema 1 remains readable), written atomically; numbers are
  canonical, symbols are stored for readability and checked on load. Machine-specific
  settings (POV-Ray path, last directory) stay in QSettings, not in projects.
- **Camera notifications:** the viewport now listens to the VTK camera's
  `ModifiedEvent`; the M0 observer on the interactor never fired because VTK raises
  `EndInteractionEvent` on the interactor style.

- **Output camera (M3):** the GUI keeps VTK's camera for the whole view and derives the
  output camera (same pose, parallel scale × frame/height ratio). Export, preview,
  render, and projects use the output camera with the explicit output size; a render
  start observer keeps it fixed across window resizes.
- **Presets (M3):** `ycrystal.presets` loads JSON manifests (declaration kind, finish,
  filter, interior, includes, live approximation, provenance) shipped as package data.
  Scenes store ids; the POV writer writes a `texture` or a full `material` per element;
  the viewport applies the live approximation. Background presets also set a visible
  cell-edge colour, changed together with the environment in one undo step.
- **Render lifecycle (M3):** `RenderProcess` (progress, cancellation, elapsed time,
  completion state) and `RenderQueue` (one process, newest request wins, job directory
  removed after the result slots). The window tags previews with `scene_revision` and
  discards stale results; final renders use a separate process with Cancel.

## Next bounded action

M3 is merged. Next product work is M4: material/environment manifests at gallery scale
(at least 20 materials and 12 environments) with genuine POV-Ray thumbnails, search and
favourites, global/element/selected-atom assignment, and lighting controls.
