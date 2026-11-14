# ycrystal

Ycrystal is a Linux desktop application (PySide6 + VTK) for preparing reproducible
crystal-structure figures and rendering them with [POV-Ray](https://www.povray.org/).

**Status: early development (feasibility milestone).** The current build shows synthetic
sample structures, supports orbit/pan/zoom, and exports or renders the current
orthographic view with POV-Ray. Structure-file import, supercells, bonds, materials, and
projects are not implemented yet. See [docs/PROGRESS.md](docs/PROGRESS.md).

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
.venv/bin/ycrystal                     # perovskite sample
.venv/bin/ycrystal --sample triclinic  # low-symmetry sample
.venv/bin/ycrystal --check-renderer    # verify that POV-Ray reproduces the camera
```

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
.venv/bin/ruff check src tests scripts
.venv/bin/python -m pytest -q -rs           # GUI tests need an X11 display
.venv/bin/python scripts/m0_evidence.py     # screenshots, render, and alignment report
```

## License

MIT, see [LICENSE](LICENSE).
