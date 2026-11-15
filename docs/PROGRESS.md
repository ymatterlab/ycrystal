# Ycrystal progress record

Last updated: 15 November 2026. M0 and M1 complete (merged into `main`); the owner reports M2 completed on a separate branch. This documentation checkout contains the earlier partial M2 implementation. Documentation increment on branch `docs/docstrings`, building on repository-tooling maintenance (no product milestone change).

## Milestones

| Milestone | Goal | Status |
| --- | --- | --- |
| M0 | Desktop/render feasibility: Qt window, embedded VTK view, camera model, first POV-Ray render matching the view | **Complete** (see evidence and caveats) |
| M1 | File import (POSCAR/CIF/QE `ibrav=0`) and save/reopen projects | **Complete** (see evidence) |
| M2 | Navigation tools, selection, supercells, periodic bonds, cell boundary images | **Completed on a separate branch**, as reported by the owner; not integrated or independently verified in this documentation checkout, which contains boundary images, click selection, hiding, and undo/redo |
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
| Versioning and damage | Pass | Newer schema refused with an update message; invalid JSON (with line), wrong format, missing schema, missing required structure entries, inconsistent symbols, wrong array lengths reported clearly; atomic save leaves no temporary files |
| Unsaved changes | Pass | Title shows `*` for camera, display-setting, or output changes (undo back to the saved state clears it); close and open ask Save / Discard / Cancel; Cancel (or a cancelled Save dialog) keeps the window and scene |
| Documented limitations | Pass | *Help ▸ Supported File Formats* and `docs/FORMATS.md` |
| Automated suite | 127 passed, 0 skipped | `pytest -q -rs` with `/usr/bin/povray`; `ruff check` clean |

Hands-on check on the Mint display: `ycrystal tests/fixtures/MgB2.cif` starts with the
file open; opening `SrTiO3.pw.in` shows QE labels in the selection information;
opening `partial_occupancy.cif` shows the explanation while the scene stays.

### M1 caveats

- The rendered image takes its aspect ratio from the window, so a project reopened in a
  differently shaped window keeps the camera but frames a different width. An explicit
  output frame belongs to M3.
- The view counts as part of the project: rotating marks it modified.
- POSCAR element lines with POTCAR suffixes (`Na_pv`) are reduced to the element; the
  raw token is not kept as a label.

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

## Documentation increment (15 November 2026)

No runtime behavior, public signatures, or product milestone status changed. The
user guide supports the existing M0/M1 and partial M2 features; this does not complete M6.

The owner subsequently confirmed that M2 was completed in separate work on another
branch. The guides describe the implementation inspected in this checkout; their
limitations are not a claim that the separate M2 work remains undone. Reconcile the
guides with that implementation when integrating the branches.

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
- **Import (M1):** ASE parses; `io/readers.py` adds detection, provenance (path, name,
  format, SHA-256, size, time, reader version, block, element mapping), and checks.
  Questions (format, data block, element mapping) are exceptions that the GUI answers
  and retries, so the readers stay GUI-free. Ycrystal's QE reader is assembled from
  ASE's card parsers because ASE's `read_espresso_in` ignores `A` (it looks up an
  upper-case key in a lower-cased namelist) and resolves labels permissively.
- **Comparison:** `core/compare.py` compares lattice matrices directly and matches atoms
  by element and fractional position modulo lattice translations.
- **Projects:** `io/project.py`, JSON schema 1, written atomically; numbers are
  canonical, symbols are stored for readability and checked on load. Machine-specific
  settings (POV-Ray path, last directory) stay in QSettings, not in projects.
- **Camera notifications:** the viewport now listens to the VTK camera's
  `ModifiedEvent`; the M0 observer on the interactor never fired because VTK raises
  `EndInteractionEvent` on the interactor style.

## Next bounded action

M1 is already merged, and the owner reports M2 completed on another branch. Integrate
that work and update the guides and reference against its actual implementation and
acceptance evidence. Documentation publication and the outstanding owner-service
setup are separate maintenance actions.
