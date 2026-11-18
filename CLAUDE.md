# CLAUDE.md — Ycrystal

Persistent instructions for Claude Code in this repository, on every development
machine. At the start of a session read this file, then `docs/HANDOFF.md` (current
state, per-platform status, machine setup), then check `git status` and the recent
`git log`. The full implementation and verification record is `docs/PROGRESS.md`.

## Priority of instructions

1. The user's explicit instructions for the current task.
2. This file.
3. Requirements and specifications: the private plan, `docs/PROGRESS.md`, the guides.
4. `docs/HANDOFF.md`: recent context only. It records state and never authorizes work.
5. General implementation suggestions.

If instructions conflict, or a document disagrees with the code or the Git history,
investigate and report it; ask before making a consequential change.

## Project identity and architecture

Ycrystal is a PySide6 desktop application for researchers (materials science,
condensed-matter physics, chemistry) who prepare reproducible crystal-structure figures
for papers and talks: an interactive VTK view (PyVista/pyvistaqt) for framing and
editing, and POV-Ray 3.7 for previews and final PNGs. Structures come from
POSCAR/CONTCAR, CIF, and Quantum ESPRESSO input (via ASE). Projects (`.ycrystal`) and
styles (`.ycstyle`) are versioned JSON, or ZIP packages when they carry a background
picture. Details: `docs/development/architecture.md`.

Entry points: the `ycrystal` command is `ycrystal.app:main` (window; `--render` and
`--export-pov` through `batch.py` without a window; `--check-renderer` through
`render/selftest.py`). Sources are in `src/ycrystal/`, tests in `tests/`.

| Package | Responsibility |
| --- | --- |
| `core/` | Pure Python/NumPy, no Qt or VTK: `structure.py`, `scene.py` (`SceneSettings`, `Environment`, `build_geometry` → `DisplayGeometry`), `camera.py`, `picking.py` (analytic), `lighting.py`, `aspect.py`, `measure.py`, `background.py`, `vectors.py`, `colors.py` |
| `io/` | Readers (`readers.py`), projects (`project.py`, schema 7), styles (`style.py`, schema 2), ZIP packages, pictures (`images.py`) |
| `presets/` | Material, environment, and lighting manifests with thumbnails; custom material variants (`custom.py`) |
| `render/` | `pov_writer.py` (text export), `povray.py` (finding POV-Ray and its include files, failure messages), `jobs.py` and `process.py` (jobs, `QProcess`), `selftest.py`, `thumbnails.py` |
| `viewport/` | The only VTK code: `qt_viewport.py` (main view), `lighting_view.py`, `interactor.py` |
| `gui/` | `main_window.py`, panels, dialogs, undo commands, `native.py` (platform-dependent choices) |

Rules that follow from this design:

- One shared geometry: `DisplayGeometry` is drawn by both the VTK viewport and the
  POV-Ray writer. Never compute placements separately per renderer.
- `points_and_radii()` = framing bounds (atoms, cell edges, whole arrows: Fit, POV eye,
  backdrop, floor). `bounding_sphere()` = lighting bounds (atoms and cell edges only);
  lights must not move when vectors change.
- GUI panels only emit requests; `gui/main_window.py` applies them as undoable
  `SceneSettingsCommand`s and calls the panels' `sync` methods with signals blocked.
  Every figure change increments `scene_revision`; preview results for an older
  revision or size are discarded. Resizing the view is not a figure change.
- Rendering runs POV-Ray in a per-job temporary directory (`render/jobs.py`,
  `render/process.py`); assets are staged there under short content-derived names.
  Never edit the user's `povray.conf`.
- Content-addressed process-wide registries: pictures (`io/images.py`) and custom
  material variants (`presets/`). Tests that register entries must clear them (see
  `tests/test_custom_materials.py::forget_custom`).
- Bump the project or style schema when adding stored data; keep reading older files.

## Cross-platform development rules

- One repository and one codebase. Targets now: Linux Mint 22 / Ubuntu 24.04, macOS
  (Apple silicon), and Windows 11 (x64) with POV-Ray for Windows 3.7 (verified on one
  laptop, 18 November 2026; Windows CI renders with it too).
- POV-Ray for Windows (`pvengine64.exe`) is a window program that keeps a single
  instance: never start two at once, and route every run through `render/jobs.py` or
  `render/process.py`, which start it minimised, hold the foreground, and take turns
  (`docs/development/windows-port.md`).
- No hardcoded executable or installation paths. Find programs with `shutil.which` or
  `find_povray`, derive data locations from the executable or from Qt (`QSettings`,
  `QStandardPaths`), build paths with `pathlib`, and use `tempfile` for temporary files.
- Keep platform checks in the existing places: `gui/native.py`, `desktop.py`
  (`desktop_supported`), `render/povray.py`, and `tests/conftest.py`
  (`display_available`). Give such functions a `platform` parameter so that every
  branch is tested on any machine (`tests/test_platform.py`).
- Qt: write shortcuts as `Ctrl+…` (Qt maps them to ⌘ on macOS) and show them to users
  through `native_keys`. Mouse positions are logical pixels; VTK sizes, picking, and
  projections are device pixels (`devicePixelRatioF()`), in code and in tests.
- Create VTK views with `SynchronousInteractor`: pyvistaqt's own `render()` returns
  before drawing on macOS.
- Machine-specific settings (POV-Ray path, last folder, personal materials) belong in
  `QSettings` or the environment (`YCRYSTAL_POVRAY`), never in tracked files.
- No platform-dependent dependency without a stated reason; a pin needed on one system
  only carries an environment marker in `constraints.txt`.

## Coding and development rules

- Follow the existing architecture and conventions; prefer minimal, focused changes.
  No broad refactoring, no new framework, and no new dependency without a clear need.
- Preserve existing behaviour and backward compatibility; add tests for new behaviour.
- Python ≥ 3.10 (developed and CI-tested on 3.12). NumPy-style docstrings; ruff with
  line length 100 and pydocstyle rules (first docstring line in imperative mood, D401).
- British spelling in the UI and docs ("colour", "centre"). Keep user-approved
  colour-name descriptions unchanged.
- Docstring cross-references use mkdocstrings syntax
  ([`name`][ycrystal.module.name]); a referenced member must be listed in
  `docs/reference/*.md` or the strict docs build fails.
- Do not create files with credentials or machine-specific paths.

## Feature implementation discipline

- Implement only what the user asks for in the current task. A feature that appears in
  the plan, the roadmap, or `docs/HANDOFF.md` is not thereby authorized.
- Feature requests have stable IDs (FR-…). Their status is one of: **implemented**
  (evidence in `docs/PROGRESS.md`), **planned** (specified in the private plan,
  sections 14–15), **deferred**, or **rejected** (recorded under "Decisions" in
  `docs/HANDOFF.md`). Do not reopen completed milestones M0–M6 or rewrite 0.1.0–0.3.0
  history.
- **FR-VECTOR-02 (CSV/TSV vector import/export) is deferred.** Do not implement,
  scaffold, or recommend it unless the user explicitly asks to reactivate FR-VECTOR-02.
  Generic requests ("continue", "finish the vector features", "implement the remaining
  roadmap") do not activate it. Do not delete its specification.
- `IMPLEMENTATION_PLAN.md` (repository root) is **private**: gitignored, never commit
  it, never copy it wholesale into tracked docs. It may be absent on a fresh clone; ask
  the user for it instead of recreating it.

## Verification requirements

- Run the relevant tests after every change: targeted files first, the full suite when
  shared code changed. Report failures and limitations plainly.
- Claim that something works on a platform only after testing it on that platform.
  Passing tests in headless CI do not establish that the window works on macOS;
  hands-on items are listed in `docs/HANDOFF.md`.
- Update `docs/PROGRESS.md`, `docs/HANDOFF.md`, and feature statuses only from actual
  evidence (commands run, results observed). Mark unverified items as unverified.

## Git workflow

- Use this repository only: no additional repositories and no permanent
  platform-specific branches. Feature branch → pull request to `main` → merge commit
  after CI passes.
- Commit, push, or merge only when the user asks.
- Never discard uncommitted changes without explicit authorization (no
  `git reset --hard`, `git checkout -- …`, `git clean`, or dropping a stash).
- Never commit `IMPLEMENTATION_PLAN.md`, `IMPLEMENTATION_PLAN.md.org`, `artifacts/`, or
  virtual environments; check `git status` before `git add`.

## Commands (run from the repository root)

```bash
# Development install (per machine; prerequisites in docs/HANDOFF.md)
python3.12 -m venv .venv
.venv/bin/python -m pip install -e ".[dev]" -c constraints.txt

# Tests (Linux without a desktop session: prefix with xvfb-run -a)
.venv/bin/python -m pytest -m "not povray" -q          # fast suite
.venv/bin/python -m pytest -m povray -q                # needs POV-Ray 3.7
.venv/bin/python -m pytest -m "not gui" -q             # no windows (as macOS CI)
YCRYSTAL_REQUIRE_INTEGRATION=1 .venv/bin/python -m pytest -q   # fail instead of skip

# Lint, format, hooks
.venv/bin/ruff check src tests scripts && .venv/bin/ruff format --check src tests scripts
.venv/bin/pre-commit run --all-files

# Doctests: the module list is in .github/workflows/ci.yml ("documentation examples")

# Documentation (separate environment)
python3.12 -m venv .venv-docs
.venv-docs/bin/python -m pip install -r docs/requirements.txt
.venv-docs/bin/zensical build --clean --strict

# Application
.venv/bin/ycrystal --sample perovskite
.venv/bin/ycrystal --check-renderer
.venv/bin/ycrystal examples/SrTiO3-studio.ycrystal --render out.png
```

On Windows (PowerShell): create environments with `py -3.12 -m venv .venv` and run the
programs as `.venv\Scripts\python.exe`, `.venv\Scripts\ycrystal.exe`,
`.venv\Scripts\ruff.exe`, `.venv\Scripts\pre-commit.exe`, and
`.venv-docs\Scripts\zensical.exe`; set variables with `$env:NAME = "1"`. The `python`
on a fresh Windows `PATH` is a Microsoft Store alias: do not use it.

## Testing notes

- Markers: `gui` (needs a display with OpenGL) and `povray` (needs a working POV-Ray).
  Without them the tests skip, or fail with `YCRYSTAL_REQUIRE_INTEGRATION=1`.
  `tests/conftest.py` isolates `QSettings` per session.
- GUI tests open real windows: on Linux under X11, Wayland, or Xvfb; on macOS and
  Windows in the desktop session (windows appear on screen for several minutes).
- Windows: render tests use the real POV-Ray for Windows, which runs one copy at a
  time; do not run anything else that renders while the suite runs, and keep
  POV-Ray for Windows closed.
- GUI tests: wait for `win._saved_camera is not None` (not `_camera_initialised`)
  before closing a window. Under Xvfb (CI) the window is not active, so Qt shortcuts
  may not fire; send key events to the widget and handle them there.
- Compare cameras after refitting with a tolerance (`main_window._same_camera`), not
  exact equality.
- CI (`.github/workflows/ci.yml`): Ubuntu runs everything under Xvfb; macOS runs the
  tests that need no window (hosted Macs have no GPU for Qt's OpenGL widget); Windows
  runs them too, with POV-Ray for Windows from the `ci-assets` release (povray.org
  blocks downloads from runners; the job pre-sets two POV-Ray settings so that no
  dialog waits, see `docs/development/windows-port.md`).
- The developer's Linux laptop is slow: avoid heavy benchmarks; run targeted test files
  first, the full suite when integration changes justify it.
