# CLAUDE.md — Ycrystal

Persistent instructions for Claude Code in this repository (Linux and macOS). For the
current state, open tasks, and machine setup, read `docs/HANDOFF.md` first; the full
implementation and verification record is `docs/PROGRESS.md`.

## What Ycrystal is

A PySide6 desktop application for reproducible crystal-structure figures: an interactive
VTK view (PyVista/pyvistaqt) for framing and editing, and POV-Ray 3.7 for previews and
final PNGs. Structures come from POSCAR/CONTCAR, CIF, and Quantum ESPRESSO input (via
ASE). Projects (`.ycrystal`) and styles (`.ycstyle`) are versioned JSON, or ZIP packages
when they carry a background picture.

## Architecture (see `docs/development/architecture.md`)

- `core/` is pure Python/NumPy, no Qt or VTK: `structure.py`, `scene.py`
  (`SceneSettings`, `Environment`, `build_geometry` → `DisplayGeometry`), `camera.py`,
  `picking.py` (analytic), `lighting.py`, `aspect.py`, `measure.py`, `background.py`,
  `vectors.py`, `colors.py`.
- One shared geometry: `DisplayGeometry` is drawn by both the VTK viewport
  (`viewport/qt_viewport.py`) and the POV-Ray writer (`render/pov_writer.py`). Never
  compute placements separately per renderer.
- `points_and_radii()` = framing bounds (atoms, cell edges, whole arrows: Fit, POV eye,
  backdrop, floor). `bounding_sphere()` = lighting bounds (atoms and cell edges only);
  lights must not move when vectors change.
- GUI panels only emit requests; `gui/main_window.py` applies them as undoable
  `SceneSettingsCommand`s and calls the panels' `sync` methods with signals blocked.
  Every figure change increments `scene_revision`; preview results for an older
  revision/size are discarded.
- Rendering runs POV-Ray in a per-job temp directory via `QProcess`
  (`render/jobs.py`, `render/process.py`); assets (background pictures) are staged
  there under short content-derived names. Never edit the user's `povray.conf`.
- Content-addressed process-wide registries: pictures (`io/images.py`) and custom
  material variants (`presets/__init__.py`, `presets/custom.py`). Tests that register
  entries must clear them (see `tests/test_custom_materials.py::forget_custom`).
- Project schema is 7 (`io/project.py`); style schema 2 (`io/style.py`). Bump the
  schema when adding stored data; keep reading older files.

## Planning and feature IDs

- Feature requests have stable IDs (FR-…). Post-0.2.0 work is recorded in the private
  plan's section 14 and in `docs/PROGRESS.md`. Do not reopen completed milestones M0–M6
  or rewrite 0.1.0/0.2.0 history.
- `IMPLEMENTATION_PLAN.md` (repo root) is **private**: gitignored, never commit it,
  never copy it wholesale into tracked docs. It may be absent on a fresh clone; ask
  the user for it instead of recreating it.
- **FR-VECTOR-02 (CSV/TSV vector import/export) is deferred.** Do not implement,
  scaffold, or recommend it unless the user explicitly asks to reactivate FR-VECTOR-02.
  Generic requests ("continue", "finish the vector features", "implement the remaining
  roadmap") do not activate it.
- Update `docs/PROGRESS.md` and feature statuses only from actual evidence (commands
  run, results observed). Mark unverified items as unverified.

## Conventions

- Python ≥ 3.10 (developed and CI-tested on 3.12). NumPy-style docstrings; ruff with
  line length 100 and pydocstyle rules (first docstring line in imperative mood, D401).
- British spelling in the UI and docs ("colour", "centre"). Keep user-approved
  colour-name descriptions unchanged.
- Docstring cross-references use mkdocstrings syntax
  ([`name`][ycrystal.module.name]); a referenced member must be listed in
  `docs/reference/*.md` or the strict docs build fails.
- No new dependencies without a clear need; pinned integration set in
  `constraints.txt`.
- Git workflow: feature branch → PR to `main` → merge commit after CI passes. Commit or
  push only when the user asks. Never commit `IMPLEMENTATION_PLAN.md`,
  `IMPLEMENTATION_PLAN.md.org`, `artifacts/`, or virtual environments.
- Do not create files with credentials or machine-specific paths for GitHub.

## Commands (run from the repository root)

```bash
# Development install (both platforms; see docs/HANDOFF.md for macOS prerequisites)
python3.12 -m venv .venv
.venv/bin/python -m pip install -e ".[dev]" -c constraints.txt

# Tests (Linux: run under a display, or prefix with: xvfb-run -a)
.venv/bin/python -m pytest -m "not povray" -q          # fast suite
.venv/bin/python -m pytest -m povray -q                # needs POV-Ray 3.7
YCRYSTAL_REQUIRE_INTEGRATION=1 .venv/bin/python -m pytest -q   # fail instead of skip

# Lint, format, hooks
.venv/bin/ruff check src tests scripts && .venv/bin/ruff format --check src tests scripts
.venv/bin/pre-commit run --all-files

# Doctests: the module list is in .github/workflows/ci.yml ("doctest" step)

# Documentation (separate environment)
python3.12 -m venv .venv-docs
.venv-docs/bin/python -m pip install -r docs/requirements.txt
.venv-docs/bin/zensical build --clean --strict

# Application
.venv/bin/ycrystal --sample perovskite
.venv/bin/ycrystal --check-renderer
.venv/bin/ycrystal examples/SrTiO3-studio.ycrystal --render out.png
```

## Testing notes

- Markers: `gui` (needs a display; skipped without `DISPLAY`/`WAYLAND_DISPLAY`) and
  `povray` (needs a working POV-Ray). `tests/conftest.py` isolates `QSettings` per
  session.
- GUI tests: wait for `win._saved_camera is not None` (not `_camera_initialised`)
  before closing a window. Under Xvfb (CI) the window is not active, so Qt shortcuts
  may not fire; send key events to the widget and handle them there.
- Compare cameras after refitting with a tolerance (`main_window._same_camera`), not
  exact equality.
- The developer's Linux laptop is slow: avoid heavy benchmarks; run targeted test files
  first, the full suite when integration changes justify it.
