<p align="center">
  <img src="docs/assets/logo_horizontal.png" alt="Ycrystal logo: a Y-shaped molecule next to the word crystal" width="480">
</p>

# ycrystal

[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Status: early development](https://img.shields.io/badge/status-early%20development-orange.svg)](docs/PROGRESS.md)

Ycrystal is a desktop application for Linux and macOS (PySide6 + VTK) for preparing
reproducible crystal-structure figures and rendering them with
[POV-Ray](https://www.povray.org/).

**Early development.** Open POSCAR/CONTCAR, CIF, and Quantum ESPRESSO (`ibrav = 0`)
inputs, save/reopen `.ycrystal` projects, orbit/pan/zoom, select and hide individual
displayed atoms, and export or render the current orthographic view. Supercell
repetitions, periodic bonds, cell-edge modes, and lattice/Cartesian view directions
are available, as are an output frame, a POV-Ray preview, cancellable renders, and
galleries of 30 materials and 12 environments with POV-Ray thumbnails, per-element and
per-atom materials, floors, skies, and lighting controls. Drag the a/b/c handles to add
cells, rotate freely or about a lattice/Cartesian axis, and reuse a figure's style with
another structure, in the window or from the command line; every figure change is
undoable.
Python interfaces are evolving developer functionality, without a stable API guarantee.

## Install and run

Linux Mint 22 / Ubuntu 24.04, system Python 3.12, X11 with OpenGL:

```bash
sudo apt install git povray povray-includes libxcb-cursor0 python3.12-venv
git clone https://github.com/ymatterlab/ycrystal.git
cd ycrystal
/usr/bin/python3 -m venv .venv
.venv/bin/python -m pip install -e . -c constraints.txt
.venv/bin/ycrystal --sample perovskite
```

On Linux use the system interpreter: Conda's bundled `libstdc++` can prevent Mesa from
loading. POV-Ray is needed for rendering PNG, PDF, and JPEG images; viewing and
exporting `.pov`/`.ini` work without it. Check it with `.venv/bin/ycrystal --check-renderer`. While the
repository is private, clone it with `gh repo clone ymatterlab/ycrystal` or over SSH.

macOS 15 on Apple silicon, with [Homebrew](https://brew.sh/):

```bash
brew install python@3.12 povray
git clone https://github.com/ymatterlab/ycrystal.git
cd ycrystal
python3.12 -m venv .venv
.venv/bin/python -m pip install -e . -c constraints.txt
.venv/bin/ycrystal --sample perovskite
```

```bash
.venv/bin/ycrystal --install-desktop                                    # menu launcher (Linux)
.venv/bin/ycrystal examples/SrTiO3-studio.ycrystal --render SrTiO3.png  # no window
# Reuse a style (studio, lighting, image size) for another structure, without a window:
.venv/bin/ycrystal tests/fixtures/MgB2.cif --style examples/grey-studio.ycstyle --render MgB2.png
# Also give the style's Ti settings (chrome) to Zr, so both perovskites look alike:
.venv/bin/ycrystal tests/fixtures/BaZrO3.cif --style examples/grey-studio.ycstyle --element-map Ti=Zr --render BaZrO3.png
# Look down the c axis, fitted so that nothing is cut off (or --view-height 12 for a fixed scale):
.venv/bin/ycrystal tests/fixtures/MgB2.cif --view c --render MgB2-c.png
```

Latest release 0.3.0; `main` is the development version 0.4.0.dev0. See the [changelog](CHANGELOG.md), the
[support matrix](docs/guide/support.md), and the [third-party notices](THIRD_PARTY_NOTICES.md).

## Guides and reference

- [Documentation home](docs/index.md), [installation details](docs/guide/install.md), and
  [examples and the command line](docs/guide/examples.md).
- [Your first crystal figure](docs/guide/first-figure.md), [controls](docs/guide/controls.md),
  [supported formats and projects](docs/FORMATS.md), [rendering](docs/guide/rendering.md),
  and [troubleshooting](docs/guide/troubleshooting.md).
- [Developer architecture](docs/development/architecture.md),
  [Python examples](docs/development/examples.md), and [API reference](docs/reference/index.md).
- [Progress and roadmap](docs/PROGRESS.md), [release checklist](docs/development/release.md),
  and [contributing](CONTRIBUTING.md).

Preview and build the source-based reference locally:

```bash
.venv/bin/python -m pip install -e ".[docs]" -c constraints.txt -c docs/requirements.txt
.venv/bin/zensical serve                     # local preview
.venv/bin/zensical build --clean --strict     # HTML in site/ (ignored)
```

The [documentation workflow](docs/development/documentation.md) includes a lightweight
docs-only installation, NumPy-style writing conventions, and asset regeneration.

## Development checks

```bash
.venv/bin/python -m pip install -e ".[dev]" -c constraints.txt
.venv/bin/pre-commit install
.venv/bin/pre-commit run --all-files
.venv/bin/python -m pytest -q -rs
```

GUI tests need a display; renderer tests need POV-Ray. CI runs the full application
suite on Ubuntu under Xvfb with POV-Ray, the tests that need no window on macOS, and
builds documentation separately. See
[CONTRIBUTING.md](CONTRIBUTING.md) for strict integration checks and maintenance setup.

## License

MIT, see [LICENSE](LICENSE).
