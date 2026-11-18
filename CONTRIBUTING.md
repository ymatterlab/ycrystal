# Contributing to Ycrystal

Thank you for helping. This guide covers the development setup, the checks every change
should pass, and how dependencies and hook versions are kept up to date.

## Development installation

Verified on Linux Mint 22.1 with the system Python 3.12 (see [README.md](README.md)):

```bash
sudo apt install povray libxcb-cursor0 python3.12-venv
git clone https://github.com/ymatterlab/ycrystal.git
cd ycrystal
/usr/bin/python3 -m venv .venv
.venv/bin/python -m pip install -e ".[dev]" -c constraints.txt
```

Use the system interpreter, not Miniconda/Anaconda: their bundled `libstdc++` can stop
Mesa's OpenGL driver from loading ("Could not initialize GLX"). `constraints.txt` pins the
integration-tested versions; always install with `-c constraints.txt`.

On macOS 15 (Apple silicon), with Homebrew:

```bash
brew install python@3.12 povray
git clone https://github.com/ymatterlab/ycrystal.git
cd ycrystal
python3.12 -m venv .venv
.venv/bin/python -m pip install -e ".[dev]" -c constraints.txt
```

There is one repository and one codebase for all systems. Keep code free of fixed
system paths, and keep the few platform checks where they already are
(`src/ycrystal/gui/native.py`, `desktop.py`, `render/povray.py`); see `CLAUDE.md`.

## Pre-commit hooks

```bash
.venv/bin/pre-commit install            # run the hooks automatically on `git commit`
.venv/bin/pre-commit run --all-files    # check every tracked file
```

The hooks are lightweight (no Qt/VTK, GUI, or POV-Ray): Ruff lint with safe fixes, Ruff
formatting (settings in `pyproject.toml`), trailing whitespace and final newlines,
YAML syntax, a 250 KB limit per file, and a check that the Ruff hook version equals
the `ruff==` pin in `constraints.txt`. Test fixtures in `tests/fixtures/` are exempt from
the whitespace fixers so that structure files stay byte-for-byte as written.

The same configuration runs in two places on purpose:

| Where | Role |
| --- | --- |
| Your machine (`pre-commit install`) | Fast feedback before committing |
| GitHub Actions, job `pre-commit` | Authoritative check on every pull request, independent of external services |

pre-commit.ci is not used; the Actions job runs the same pinned hooks.

## Tests

```bash
.venv/bin/python -m pytest -q -rs
```

- GUI tests (`gui` marker) need a display with OpenGL: a desktop session (Linux,
  macOS, or Windows; the windows appear on screen) or, on Linux,
  `xvfb-run -a python -m pytest -q -rs`.
- Rendering tests (`povray` marker) need a POV-Ray 3.7 executable that passes
  `ycrystal --check-renderer`; it is found on `PATH` (on Windows, POV-Ray for Windows
  in its installation folder), or set `YCRYSTAL_POVRAY` to it. POV-Ray for Windows runs
  one copy at a time: keep it closed and render nothing else while the tests run.
- On Windows, `powershell -ExecutionPolicy Bypass -File scripts\install-windows.ps1
  -Dev` sets up `.venv` with the developer tools (and Python and POV-Ray for Windows
  with `winget`, if missing). Run the tools as
  `.venv\Scripts\python.exe -m pytest -q -rs`, `.venv\Scripts\pre-commit.exe`, and so
  on.
- Locally, missing prerequisites skip those tests (`-rs` lists them). CI sets
  `YCRYSTAL_REQUIRE_INTEGRATION=1`, which turns a missing display or renderer into an
  error; set it yourself to make sure nothing was skipped.
- CI runs every test on Ubuntu 24.04 under Xvfb. On macOS it runs the tests that open
  no window (`-m "not gui"`), because GitHub's hosted Macs have no GPU for Qt's
  OpenGL widget; run the GUI tests on a real Mac before relying on a GUI change
  there. On Windows it runs the same tests, with the official POV-Ray for Windows 3.7
  installer kept as an asset of the `ci-assets` release (povray.org blocks downloads
  from CI runners), and it also runs `scripts\install-windows.ps1` into a new `.venv`;
  run the GUI tests on a Windows computer before relying on a GUI change there. To add
  an operating system, add a matrix entry and a system-packages step to the `test` job.
- The Windows installer for users (PyInstaller + Inno Setup) is built by
  `packaging\windows\build.ps1` and checked next to a source installation by
  `packaging\windows\coexistence-check.ps1`. The *Windows installer* workflow runs both
  on pull requests that change `src/` or the packaging, and keeps the installer as an
  artifact. Changes to Start-menu entries, application ids, or file types must keep the
  two Windows installations apart: see
  [Windows installer](docs/development/windows-installer.md).
- `scripts/m0_evidence.py` regenerates screenshots and alignment measurements.
- `scripts/benchmark_scene.py` measures display cost for growing supercells; rerun it
  when changing the viewport, and record the hardware with the numbers.
- `scripts/benchmark_render.py` measures POV-Ray renders through the command line, and
  `scripts/replay_check.py` renders saved snapshots again and compares the pixels (on
  another machine, too); see the [validation report](docs/development/validation.md).
  Never edit their results by hand; record the command and the machine with them.

## Generated files

For NumPy-style docstring conventions, the generated API reference, local preview,
and strict documentation checks, see
[Documentation workflow](docs/development/documentation.md). Update the relevant
docstrings, user instructions, and executable examples in the same change as behavior.

Renders, render caches, screenshots, and evidence output belong in `artifacts/`
(ignored by Git) or outside the repository. Do not commit them. The large-file hook
rejects files above 250 KB; a genuinely needed larger asset must be excluded explicitly
in `.pre-commit-config.yaml` with a reason.

The small `docs/assets/perovskite.png` is an intentional documentation exception:
regenerate it with `python scripts/docs_render_example.py` and inspect it before
committing. Generated HTML (`site/`) and documentation caches stay ignored.

The preset thumbnails in `src/ycrystal/presets/thumbnails/` (128 × 128 px PNGs and
`index.json`) are another intentional exception: they ship with the package. After
changing a preset or the scene writer, `tests/test_presets.py` reports out-of-date
thumbnails; run `python scripts/render_thumbnails.py` (only changed scenes are
rendered), look at the new images, and commit them with the change.

The gallery thumbnails in `docs/assets/gallery/` (480 px JPEG copies of real renders,
about 20 KB each) are a third exception. Regenerate them with `python
scripts/make_gallery.py --out artifacts/gallery --thumbnails docs/assets/gallery`, look
at them, and update the figure-methods table in `docs/guide/gallery.md` from the same
run.

The example projects in `examples/` are generated by `python scripts/make_examples.py`
(fixed timestamps, repository-relative provenance). Regenerate them after a project
schema change and render one with `ycrystal examples/… --render` before committing.

## Releases

See [Release procedure and checklist](docs/development/release.md). Update the version in
`src/ycrystal/__init__.py` and `CHANGELOG.md`; tagging and publishing are the
maintainer's decision.

## Progress record

When a change alters what is implemented or verified, update
[docs/PROGRESS.md](docs/PROGRESS.md): status, evidence (commands and actual results),
unverified items, and the next step. Do not mark a milestone complete without its
acceptance evidence.

## Pull requests

Describe the change briefly and report the validation you actually ran, including what
you could not run (the pull-request template asks for this).

## Dependency and hook updates

- **Python packages:** Dependabot checks monthly. Minor and patch updates arrive in one
  grouped pull request, major updates individually, at most three open per ecosystem.
  It updates the exact pins in `constraints.txt` and leaves the lower bounds in
  `pyproject.toml` alone while they still allow the new release.
- **GitHub Actions:** Dependabot checks monthly with the same grouping.
- **Hooks:** a maintainer runs `pre-commit autoupdate` monthly on a branch and opens a
  pull request (see below for Ruff). Dependabot does not touch hooks.
- No update is merged automatically; CI must pass and a maintainer merges.

### Keeping Ruff in sync

Ruff is pinned twice: `rev` of `astral-sh/ruff-pre-commit` in `.pre-commit-config.yaml`
and `ruff==` in `constraints.txt`. Dependabot ignores Ruff; the pre-commit side leads:

1. On a new branch, run `pre-commit autoupdate` (or only Ruff:
   `pre-commit autoupdate --repo https://github.com/astral-sh/ruff-pre-commit`).
2. The `ruff-version-sync` hook fails in that pull request until
   `ruff==` in `constraints.txt` is set to the same version. Edit it on the same branch.
3. Run `pre-commit run --all-files` and the tests; commit any formatting changes.

### Regenerating constraints.txt

Dependabot changes pins one package (or one group) at a time and does not re-resolve
the environment. If its pull request fails to install or breaks tests, regenerate the
pins in a fresh environment and test them:

```bash
/usr/bin/python3 -m venv /tmp/yc-env
/tmp/yc-env/bin/python -m pip install -e ".[dev]"      # newest compatible releases
/tmp/yc-env/bin/python -m pip install "ruff==<version in .pre-commit-config.yaml>"
/tmp/yc-env/bin/python -m pytest -q -rs                # needs a display and POV-Ray
/tmp/yc-env/bin/python -m pip freeze --exclude-editable > constraints.new
```

Keep the header comment lines of `constraints.txt` and the pins that carry an
environment marker (`; sys_platform == "darwin"`: packages installed on macOS only,
which a freeze on Linux does not list), replace the other pins with those in
`constraints.new`, rerun `pre-commit run --all-files`, and record the change in
`docs/PROGRESS.md`. Then install with the new pins on the other system and run its
tests.

## Repository-owner setup

Committed configuration does not by itself activate these services:

- **pre-commit.ci:** not used. It is free for public repositories such as this one and
  can be enabled at <https://pre-commit.ci>; add a `ci:` section to
  `.pre-commit-config.yaml` for its settings.
- **Dependabot:** version updates start from `.github/dependabot.yml` once Dependabot is
  allowed for the repository; check *Settings ▸ Code security* (also for Dependabot
  alerts and security updates, which this file does not configure).
- **Branch protection (optional):** require the `pre-commit` and `tests` checks on `main`
  (the `tests` job reports one check per operating system; the Ubuntu check keeps its
  earlier name).
  The "Protect main" ruleset is active on `main`: no deletion or force-push, and changes
  only through pull requests (no approval required). Its list of required checks is
  empty, so add the checks there to require them.
