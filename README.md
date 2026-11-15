# ycrystal

[![CI](https://github.com/ymatterlab/ycrystal/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/ymatterlab/ycrystal/actions/workflows/ci.yml?query=branch%3Amain)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Status: early development](https://img.shields.io/badge/status-early%20development-orange.svg)](docs/PROGRESS.md)

Ycrystal is a Linux desktop application (PySide6 + VTK) for preparing reproducible
crystal-structure figures and rendering them with [POV-Ray](https://www.povray.org/).

**Early development.** Open POSCAR/CONTCAR, CIF, and Quantum ESPRESSO (`ibrav = 0`)
inputs, save/reopen `.ycrystal` projects, orbit/pan/zoom, select and hide individual
displayed atoms, and export or render the current orthographic view. Supercell
repetitions, periodic bonds, cell-edge modes, and lattice/Cartesian view directions
are available. Material galleries and the full preview workflow are planned.
Python interfaces are evolving developer functionality, without a stable API guarantee.

## Install and run

Linux Mint 22 / Ubuntu 24.04, system Python 3.12, X11 with OpenGL:

```bash
sudo apt install git povray libxcb-cursor0 python3.12-venv
git clone https://github.com/ymatterlab/ycrystal.git
cd ycrystal
/usr/bin/python3 -m venv .venv
.venv/bin/python -m pip install -e . -c constraints.txt
.venv/bin/ycrystal --sample perovskite
```

Use the system interpreter: Conda's bundled `libstdc++` can prevent Mesa from
loading. POV-Ray is needed for PNG rendering; viewing and exporting `.pov`/`.ini`
work without it. Check it with `.venv/bin/ycrystal --check-renderer`.

## Guides and reference

- [Documentation home](docs/index.md) and [installation details](docs/guide/install.md).
- [Your first crystal figure](docs/guide/first-figure.md), [controls](docs/guide/controls.md),
  [supported formats and projects](docs/FORMATS.md), [rendering](docs/guide/rendering.md),
  and [troubleshooting](docs/guide/troubleshooting.md).
- [Developer architecture](docs/development/architecture.md),
  [Python examples](docs/development/examples.md), and [API reference](docs/reference/index.md).
- [Progress and roadmap](docs/PROGRESS.md) and [contributing](CONTRIBUTING.md).

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

GUI tests need a display; renderer tests need POV-Ray. CI retains the full application
suite under Xvfb with POV-Ray and also builds documentation separately. See
[CONTRIBUTING.md](CONTRIBUTING.md) for strict integration checks and maintenance setup.

## License

MIT, see [LICENSE](LICENSE).
