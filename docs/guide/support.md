# Supported formats, renderers, and platforms

Status for Ycrystal 0.2.0 (unchanged since 0.1.0). *Verified* means tested on the stated system (automatically
or by hand); *unverified* means not tested, not that it fails.

## Input and output files

| File | Read | Write | Notes |
| --- | --- | --- | --- |
| VASP POSCAR / CONTCAR (VASP 5) | Yes | — | Selective dynamics kept as movable flags |
| VASP 4 POSCAR (no element line) | Yes, after naming the elements | — | The window asks |
| CIF, ordered structures | Yes | — | Symmetry expanded by ASE; several data blocks: choose one |
| CIF with partial or mixed occupancy, overlapping sites | Rejected with an explanation | — | |
| Quantum ESPRESSO pw.x input, `ibrav = 0` with `CELL_PARAMETERS` | Yes | — | Ambiguous species labels: the window asks |
| QE `ibrav ≠ 0`, `crystal_sg` positions | Rejected with an explanation | — | Rewrite as `ibrav = 0` |
| Ycrystal project `.ycrystal` (schema 1–5) | Yes | Schema 5 | Self-contained JSON |
| Ycrystal style `.ycstyle` | Yes | Yes | Presentation only |
| POV-Ray scene `.pov` + `.ini` | — | Yes | Editable; may `#include` standard POV-Ray files |
| PNG image | — | Yes (via POV-Ray) | 8-bit sRGB, optional alpha |

Details: [structure files and projects](../FORMATS.md).

## Renderer

| POV-Ray | Status |
| --- | --- |
| 3.7.0.10, Linux Mint 22.1 / Ubuntu 24.04 package (`povray`, `povray-includes`) | Verified (development machine and CI) |
| Other 3.7.x builds | Expected to work; `ycrystal --check-renderer` decides |
| 3.7 built from source with `-ffast-math` (POV-Ray's default GCC flags) | Fails: misreported camera angle; the check explains how to rebuild |
| 3.8 betas, UberPOV, other forks | Unverified |
| No POV-Ray | Viewing, editing, projects, styles, and `.pov` export work; preview and PNG need POV-Ray |

## Platform

| Component | Status |
| --- | --- |
| Linux Mint 22.1 Cinnamon, X11, Intel Meteor Lake graphics (Mesa 25.2) | Verified on the development laptop |
| Ubuntu 24.04 under Xvfb (software OpenGL) | Verified by CI on every change |
| System Python 3.12 | Verified |
| Python 3.10 and 3.11 | Allowed by the package metadata, unverified |
| Wayland sessions | Unverified (Qt uses XWayland if available) |
| Other Linux distributions, Windows, macOS | Unverified; no packages |
| Miniconda/Anaconda Python | Not recommended (OpenGL loading problems) |

## Size and performance

On the development laptop (Intel Core Ultra 5 135U, 8 GB RAM, integrated graphics), a
1,300-atom supercell rotates at about 14 steps per second and a 70-atom cell at about
30; expansions above 20,000 displayed atoms ask for confirmation. POV-Ray preview times
depend on the materials: about 1–2 s for opaque materials at 480 × 320, several seconds
for glass, and much longer for glass with area lights (see
[lighting](appearance.md#lighting)).
