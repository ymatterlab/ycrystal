<p align="center">
  <img src="docs/assets/logo_horizontal.png" alt="Ycrystal logo: a Y-shaped molecule next to the word crystal" width="480">
</p>

# Ycrystal

[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Colorblind Friendly](https://img.shields.io/badge/Colorblind-Friendly-0077B6)](docs/guide/appearance.md#choosing-colours)
[![CI](https://github.com/ymatterlab/ycrystal/actions/workflows/ci.yml/badge.svg)](https://github.com/ymatterlab/ycrystal/actions/workflows/ci.yml)
[![Version: 0.4.0](https://img.shields.io/badge/version-0.4.0-blue.svg)](CHANGELOG.md)
[![DOI](https://img.shields.io/badge/DOI-10.5281%2Fzenodo.24403163-1682D4.svg)](https://doi.org/10.5281/zenodo.24403163)
[![Platforms: Linux | macOS | Windows](https://img.shields.io/badge/platforms-Linux%20%7C%20macOS%20%7C%20Windows-lightgrey.svg)](docs/guide/support.md)
[![Python 3.12 | 3.13 | 3.14](https://img.shields.io/badge/python-3.12%20%7C%203.13%20%7C%203.14-3776AB.svg)](docs/guide/support.md)
[![Renderer: POV-Ray 3.7](https://img.shields.io/badge/renderer-POV--Ray%203.7-5A2D82.svg)](https://www.povray.org/)
[![Code style: Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

Ycrystal prepares reproducible crystal-structure figures and renders them with
[POV-Ray](https://www.povray.org/), on Linux, macOS, and Windows. It has two faces that
share one scene model and one renderer:

- a **desktop application** (PySide6 + VTK) to open a structure, frame it, and design
  its look interactively, with a live view and a POV-Ray preview;
- a **command line** that renders without a window, from a terminal, a script, or a
  remote machine: apply a saved style to any structure, choose the view and scale, and
  render whole series of structures from one JSON manifest, for high-throughput figure
  production.

A look designed in the window can be saved as a style and reused unchanged on the
command line, so figures made by hand and figures made in bulk match.

## Features

- **Structures and projects:** POSCAR/CONTCAR, CIF, and Quantum ESPRESSO
  (`ibrav = 0`) inputs; `.ycrystal` projects that keep the structure, view, and look,
  and reopen without the original files.
- **Interactive view:** orbit, pan, and zoom; free or axis-constrained rotation;
  lattice and Cartesian view directions; select and hide atoms; supercells with
  draggable a/b/c handles, periodic bonds, and cell-edge modes; distance and
  bond-angle measurements; atom-attached direction and magnetic-moment arrows.
- **Appearance:** 30 materials and 12 environments with POV-Ray thumbnails,
  per-element and per-atom materials, editable material recipes, colours by value or
  name, floors, skies, background pictures, and a Lighting Setup window.
- **Output:** a POV-Ray preview, cancellable renders, PNG, PDF, and JPEG export with
  publication sizes, and editable `.pov`/`.ini` scenes. Every figure change is
  undoable.
- **Command line and high-throughput rendering:** `--render` and `--export-pov` for
  single figures; `--style` with explicit `--element-map` between compositions;
  `--view`, `--camera-policy`, and `--view-height` for consistent orientation and
  scale; `--batch` for a series from a JSON manifest, checked completely before
  rendering, with a JSON report of every job. No display is needed.
- **Reproducibility:** self-contained project snapshots with a provenance record, so
  a figure can be rendered again later or elsewhere; a gallery of example figures
  regenerated from scripts.

The Python interface may still change before version 1.0.

## Install

### Windows: the installer (recommended)

Download `Ycrystal-<version>-windows-x64-setup.exe` from the
[Releases page](https://github.com/ymatterlab/ycrystal/releases), run it, and start
**Ycrystal** from the Start menu. It needs no Python, Git, or PowerShell, and no
administrator rights. Ycrystal renders with POV-Ray for Windows 3.7, installed
separately (the installer says so if it is missing). The installer is not signed yet:
if Windows shows "Windows protected your PC", choose *More info*, then *Run anyway*.
Details: [install guide](docs/guide/install.md#windows).

### From source: Linux, macOS, and Windows for developers

You need Python 3.12 or newer (3.12, 3.13, and 3.14 are tested on Linux and Windows;
3.12 and 3.13 on macOS), and POV-Ray 3.7 for rendering images (the window and `.pov`
export work without it). Git is optional. Ycrystal is installed into a folder `.venv`
inside the Ycrystal folder.

#### Get the code

With Git, which makes updating easy (to install Git: `sudo apt install git` on Linux,
`xcode-select --install` on macOS, and on Windows see below):

```bash
git clone https://github.com/ymatterlab/ycrystal.git
cd ycrystal
```

Without Git, download
[the code as a ZIP file](https://github.com/ymatterlab/ycrystal/archive/refs/heads/main.zip)
(also under the green **Code** button on GitHub), unpack it, and open a terminal in the
unpacked folder `ycrystal-main`. Or, on Linux and macOS, in a terminal:

```bash
curl -L -o ycrystal.zip https://github.com/ymatterlab/ycrystal/archive/refs/heads/main.zip
unzip ycrystal.zip && cd ycrystal-main
```

On Windows, in PowerShell:

```powershell
Invoke-WebRequest https://github.com/ymatterlab/ycrystal/archive/refs/heads/main.zip -OutFile ycrystal.zip
Expand-Archive ycrystal.zip . ; cd ycrystal-main
```

Then follow your system, in that folder.

#### Linux (Mint 22 / Ubuntu 24.04)

```bash
sudo apt install povray povray-includes libxcb-cursor0 python3.12-venv
/usr/bin/python3 -m venv .venv
.venv/bin/python -m pip install -e . -c constraints.txt
.venv/bin/ycrystal --sample perovskite   # opens the window with a sample structure
```

Use the system Python (`/usr/bin/python3`), not Conda's: Conda's libraries can stop the
3D view from starting. To add Ycrystal to the applications menu, run
`.venv/bin/ycrystal --install-desktop`.

#### macOS (15, Apple silicon)

With [Homebrew](https://brew.sh/):

```bash
brew install python@3.12 povray
python3.12 -m venv .venv
.venv/bin/python -m pip install -e . -c constraints.txt
.venv/bin/ycrystal --sample perovskite   # opens the window with a sample structure
```

#### Windows 11 (developer installation)

For working on Ycrystal or running its newest source; other users take
[the installer](#windows-the-installer-recommended). In PowerShell, in the Ycrystal
folder (for Git: `winget install --id Git.Git --exact`, then open a new PowerShell
window before cloning):

```powershell
powershell -ExecutionPolicy Bypass -File scripts\install-windows.ps1
```

The script installs Python and POV-Ray for Windows if they are missing, sets up
Ycrystal, and adds **Ycrystal (development)** to the Start menu. It can live next to
the installed Ycrystal: each has its own Start-menu entry, and uninstalling one leaves
the other working.

#### Check and update

For installations from source, check that rendering works (on Windows:
`.venv\Scripts\ycrystal.exe --check-renderer`; in the installer version: *Render ▸
Check Renderer*):

```bash
.venv/bin/ycrystal --check-renderer
```

To update, run `git pull` in the Ycrystal folder, then the `pip install` line again (on
Windows: the installation script again). Without Git, download and unpack the new ZIP
file and install again in the new folder; then delete the old folder. The [install guide](docs/guide/install.md)
covers each step in detail, the Windows installation without the script, and
uninstalling; [troubleshooting](docs/guide/troubleshooting.md) helps if something fails.

## Command-line examples

Run these in the Ycrystal folder, without opening a window. On Windows, write
`.venv\Scripts\ycrystal.exe` instead of `.venv/bin/ycrystal`, and backslashes in paths.

```bash
# Render a saved project:
.venv/bin/ycrystal examples/SrTiO3-studio.ycrystal --render SrTiO3.png
# Reuse a style (studio, lighting, image size) for another structure:
.venv/bin/ycrystal tests/fixtures/MgB2.cif --style examples/grey-studio.ycstyle --render MgB2.png
# Also give the style's Ti settings (chrome) to Zr, so both perovskites look alike:
.venv/bin/ycrystal tests/fixtures/BaZrO3.cif --style examples/grey-studio.ycstyle --element-map Ti=Zr --render BaZrO3.png
# Look down the c axis, fitted so that nothing is cut off (or --view-height 12 for a fixed scale):
.venv/bin/ycrystal tests/fixtures/MgB2.cif --view c --render MgB2-c.png
# Render a whole series (one style, one view, five structures) from a JSON manifest:
.venv/bin/ycrystal --batch examples/batch-series.json --output-dir renders
# Also save a self-contained snapshot and a provenance record; render the snapshot again later:
.venv/bin/ycrystal tests/fixtures/MgB2.cif --view c --render MgB2-c.png --save-project MgB2-c.ycrystal
.venv/bin/ycrystal MgB2-c.ycrystal --render MgB2-c-again.png
```

Current version 0.4.0. See the
[changelog](CHANGELOG.md), the [support matrix](docs/guide/support.md), and the
[third-party notices](THIRD_PARTY_NOTICES.md).

## Guides and reference

- [Documentation home](docs/index.md), [installation details](docs/guide/install.md), and
  [examples and the command line](docs/guide/examples.md).
- [Your first crystal figure](docs/guide/first-figure.md), [controls](docs/guide/controls.md),
  [supported formats and projects](docs/FORMATS.md), [rendering](docs/guide/rendering.md),
  and [troubleshooting](docs/guide/troubleshooting.md).
- [Developer architecture](docs/development/architecture.md),
  [Python examples](docs/development/examples.md), and [API reference](docs/reference/index.md).
- [Reproducible figures](docs/guide/reproducibility.md) and the
  [figure gallery](docs/guide/gallery.md).
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

On Windows the programs are `.venv\Scripts\python.exe` and `.venv\Scripts\pre-commit.exe`.
GUI tests need a display; renderer tests need POV-Ray. CI runs the full application
suite on Ubuntu under Xvfb with POV-Ray, the tests that need no window on macOS and on
Windows (both with POV-Ray), and builds documentation separately. See
[CONTRIBUTING.md](CONTRIBUTING.md) for strict integration checks and maintenance setup.

## How to cite

Until a journal article is available, please cite the archived software. Version 0.4.0
is on Zenodo:

> Fang, Y.-W. (2026). *Ycrystal: reproducible ray-traced crystal visualization with
> transferable styles and automated workflows* (version v0.4.0) [Computer software].
> Zenodo. https://doi.org/10.5281/zenodo.24403163

```bibtex
@software{Fang2026Ycrystal,
  author    = {Fang, Yue-Wen},
  title     = {Ycrystal: reproducible ray-traced crystal visualization with
               transferable styles and automated workflows},
  version   = {v0.4.0},
  year      = {2026},
  publisher = {Zenodo},
  doi       = {10.5281/zenodo.24403163},
  url       = {https://doi.org/10.5281/zenodo.24403163}
}
```

This DOI identifies version 0.4.0 (Git tag `v0.4.0`). If you used another version,
please name it as well.

## Author

Ycrystal is designed and developed by [@yw-fang](https://github.com/yw-fang)
(Y-Matter Lab).

## License

MIT, see [LICENSE](LICENSE).
