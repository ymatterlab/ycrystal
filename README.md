# ycrystal

[![CI](https://github.com/ymatterlab/ycrystal/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/ymatterlab/ycrystal/actions/workflows/ci.yml?query=branch%3Amain)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Status: early development](https://img.shields.io/badge/status-early%20development-orange.svg)](docs/PROGRESS.md)

Ycrystal is a Linux desktop application (PySide6 + VTK) for preparing reproducible
crystal-structure figures and rendering them with [POV-Ray](https://www.povray.org/).

**Status: early development.** Ycrystal opens POSCAR/CONTCAR, CIF, and Quantum
ESPRESSO (`ibrav = 0`) files, saves and reopens `.ycrystal` projects, supports
orbit/pan/zoom, selection and hiding of individual atoms, and exports or renders the
current orthographic view with POV-Ray. Supercells, bonds, materials, and lighting
controls are not implemented yet. See [docs/PROGRESS.md](docs/PROGRESS.md) and the
format details in [docs/FORMATS.md](docs/FORMATS.md).

## Requirements (Linux Mint 22 / Ubuntu 24.04)

```bash
sudo apt install povray libxcb-cursor0 python3.12-venv
```

`libxcb-cursor0` is required by Qt 6.5+ on X11. POV-Ray is optional for viewing and
exporting `.pov`/`.ini` files, but needed to render images.

## Install for development

Use the system Python (`/usr/bin/python3`). A Miniconda/Anaconda interpreter can load
an older `libstdc++` that the system's Mesa OpenGL driver cannot use; the 3D view then
fails with "Could not initialize GLX".

```bash
git clone https://github.com/ymatterlab/ycrystal.git
cd ycrystal
/usr/bin/python3 -m venv .venv
.venv/bin/python -m pip install -e ".[dev]" -c constraints.txt
```

(`uv venv --python /usr/bin/python3.12 .venv` followed by
`uv pip install -e ".[dev]" -c constraints.txt` works without `python3.12-venv`.)

## Run

```bash
.venv/bin/ycrystal                             # perovskite sample
.venv/bin/ycrystal path/to/POSCAR              # open a structure file or .ycrystal project
.venv/bin/ycrystal structure.txt --format cif  # set the format explicitly
.venv/bin/ycrystal --check-renderer            # verify that POV-Ray reproduces the camera
```

*File ▸ Open…* (Ctrl+O) reads POSCAR/CONTCAR, CIF, Quantum ESPRESSO pw.x input
(`ibrav = 0` with `CELL_PARAMETERS` only), and `.ycrystal` projects; *File ▸ Save
Project* (Ctrl+S) stores the structure, view, and display settings in one file that
does not need the original structure file. Unsupported cases (CIF partial occupancy,
QE `ibrav ≠ 0` or `crystal_sg`) are rejected with an explanation;
[docs/FORMATS.md](docs/FORMATS.md) lists the details. Small example inputs are in
`tests/fixtures/`.

Mouse: left drag orbits, middle drag or Shift + left drag pans, wheel or right drag
zooms, **F** fits the structure. Click a ball to select it (Ctrl + click adds or
removes, Esc clears); **Delete** hides the selected balls from the view and from exports
without changing the structure (**Ctrl+Z** undoes, *View ▸ Show All Atoms* restores).
Atoms on cell faces, edges, and corners are drawn at every equivalent position, as in
VESTA (*View ▸ Show Boundary Atoms*). *Render PNG…* renders the current view at the
chosen width; the height follows the viewport's aspect ratio.

POV-Ray is found via *Render ▸ Set POV-Ray Executable…*, then `$YCRYSTAL_POVRAY`, then
`povray` on `PATH`. Self-built POV-Ray 3.8 binaries compiled with `-ffast-math` (added
by POV-Ray's `configure` for GCC unless `--disable-optimiz` is given) reject cameras
that do not set `angle`, which includes Ycrystal's; `--check-renderer` detects this.

## Checks

```bash
.venv/bin/pre-commit install                # once: run the hooks on every commit
.venv/bin/pre-commit run --all-files        # Ruff lint/format and file checks
.venv/bin/python -m pytest -q -rs           # GUI tests need an X11 display
.venv/bin/python scripts/m0_evidence.py     # screenshots, render, and alignment report
```

CI runs the same hooks and the full test suite on Ubuntu 24.04 with Python 3.12, a
virtual X display, and POV-Ray 3.7; development and hands-on checks use Linux Mint 22.1.
Other operating systems and Python versions are not tested yet. See
[CONTRIBUTING.md](CONTRIBUTING.md) for the development workflow.

## License

MIT, see [LICENSE](LICENSE).
