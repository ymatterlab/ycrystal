# Supported formats, renderers, and platforms

Status for Ycrystal 0.3.0 and the development version after it (PDF and JPEG export,
Windows).
*Verified* means tested on the stated system (automatically or by hand); *unverified*
means not tested, not that it fails.

## Input and output files

| File | Read | Write | Notes |
| --- | --- | --- | --- |
| VASP POSCAR / CONTCAR (VASP 5) | Yes | — | Selective dynamics kept as movable flags |
| VASP 4 POSCAR (no element line) | Yes, after naming the elements | — | The window asks |
| CIF, ordered structures | Yes | — | Symmetry expanded by ASE; several data blocks: choose one |
| CIF with partial or mixed occupancy, overlapping sites | Rejected with an explanation | — | |
| Quantum ESPRESSO pw.x input, `ibrav = 0` with `CELL_PARAMETERS` | Yes | — | Ambiguous species labels: the window asks |
| QE `ibrav ≠ 0`, `crystal_sg` positions | Rejected with an explanation | — | Rewrite as `ibrav = 0` |
| Ycrystal project `.ycrystal` (schema 1–8) | Yes | Schema 8 | Self-contained: JSON, or a ZIP package when it carries a background picture |
| Ycrystal style `.ycstyle` (schema 1–3) | Yes | Schema 3 | Presentation only, including the element legend; a ZIP package when it carries a background picture |
| POV-Ray scene `.pov` + `.ini` | — | Yes | Editable; may `#include` standard POV-Ray files |
| PNG image | — | Yes (via POV-Ray) | 8-bit sRGB, optional alpha; resolution (dpi) stored when rendered from the Render Image dialog; an enabled element legend is painted onto it |
| PDF document | — | Yes (via POV-Ray) | One page of the figure's physical size with the POV-Ray image embedded losslessly; raster, not vector graphics |
| JPEG image | — | Yes (via POV-Ray) | Quality 1–100 (default 95), resolution stored; transparent backgrounds become white |

Details: [structure files and projects](../FORMATS.md).

## Renderer

| POV-Ray | Status |
| --- | --- |
| 3.7.0.10, Linux Mint 22.1 / Ubuntu 24.04 package (`povray`, `povray-includes`) | Verified (development machine and CI) |
| 3.7.0.10, Homebrew `povray` on macOS 15 (Apple silicon) | Verified (renderer check and all rendering tests, 16 November 2026) |
| POV-Ray for Windows 3.7.0 (official installer, `pvengine64.exe`) on Windows 11 | Verified on one laptop (renderer check and all rendering tests, 18 November 2026). Runs minimised for each render; cannot render while a copy of it is open with *Keep Single Instance* on (its default) |
| Other 3.7.x builds | Expected to work; `ycrystal --check-renderer` decides |
| 3.7 built from source with `-ffast-math` (POV-Ray's default GCC flags) | Fails: misreported camera angle; the check explains how to rebuild |
| 3.8 betas, UberPOV, other forks | Unverified |
| No POV-Ray | Viewing, editing, projects, styles, and `.pov` export work; preview and rendered images need POV-Ray |

## Platform

| Component | Status |
| --- | --- |
| Linux Mint 22.1 Cinnamon, X11, Intel Meteor Lake graphics (Mesa 25.2) | Verified on the development laptop |
| Ubuntu 24.04 under Xvfb (software OpenGL) | Verified by CI on every change |
| System Python 3.12 | Verified |
| Python 3.13 | Verified on macOS 15.8, Apple silicon (Homebrew Python 3.13.18, full suite including the GUI tests and POV-Ray, 18 November 2026); full suite in CI on Ubuntu 24.04 (Xvfb, POV-Ray 3.7) on every change; verified on the Windows 11 laptop (python.org Python 3.13.17, installation script and full suite including the GUI tests with POV-Ray for Windows, 18 November 2026) |
| Python 3.14 | Full suite in CI on Ubuntu 24.04 (Xvfb, POV-Ray 3.7) on every change; verified on the Windows 11 laptop (python.org Python 3.14.10, installation script and full suite including the GUI tests with POV-Ray for Windows, 18 November 2026); unverified on macOS and on a real Linux machine |
| Python 3.10 and 3.11 | Not supported: the tested NumPy and SciPy need Python 3.12 (`requires-python = ">=3.12"`) |
| macOS 15.8, Apple silicon, Homebrew Python 3.12 and POV-Ray, non-Retina display | Automated tests verified on a Mac mini (full suite including the GUI tests, 16 November 2026); hands-on use not yet checked |
| macOS on a Retina display, Intel Macs, other macOS versions | Unverified (the GUI tests also pass with an emulated 2× display scale) |
| macOS in CI (GitHub-hosted, no GPU) | Tests that open no window only, on every pull request and push to `main` |
| Wayland sessions | Unverified (Qt uses XWayland if available) |
| Windows 11 (x64), Python 3.12, 3.13, or 3.14 from python.org, POV-Ray for Windows 3.7, 125 % display scale | Verified on one laptop (full suite including the GUI tests on each of the three versions; tested by hand with 3.12; 18 November 2026) |
| Windows installation script (`scripts\install-windows.ps1`, Windows PowerShell 5.1), Start-menu entry, `.ycrystal` file type | Verified on the same laptop, with Python and POV-Ray already installed: fresh `.venv`, Start-menu entry and project opened from it, renderer check; run by Windows CI on every pull request. Installing Python and POV-Ray through it with `winget` is unverified |
| Windows installer (`Ycrystal-<version>-windows-x64-setup.exe`, PyInstaller + Inno Setup), next to a developer installation | Built and installed per user on the same laptop (18 November 2026): packaged command line and window, Start-menu entry and `.ycrystal` file type, and the coexistence check (27 checks) passed. Not yet clicked through by a person, installed for all users, or tried on another computer; not signed |
| Windows in CI (GitHub-hosted, Windows Server 2022) | Tests that open no window, with POV-Ray for Windows 3.7, on every pull request (since 18 November 2026) |
| Windows 10, Windows on ARM, other Windows display scales | Unverified |
| Other Linux distributions | Unverified; no packages |
| Miniconda/Anaconda Python | Not recommended on Linux (OpenGL loading problems); unverified on macOS |

## Size and performance

On the development laptop (Intel Core Ultra 5 135U, 8 GB RAM, integrated graphics), a
1,300-atom supercell rotates at about 14 steps per second and a 70-atom cell at about
30; expansions above 20,000 displayed atoms ask for confirmation. POV-Ray preview times
depend on the materials: about 1–2 s for opaque materials at 480 × 320, several seconds
for glass, and much longer for glass with area lights (see
[lighting](appearance.md#lighting)).
