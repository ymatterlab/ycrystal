# Third-party software and data

Ycrystal is distributed under the MIT License (see `LICENSE`). It does not bundle
third-party code: the Python packages below are installed separately by `pip` from
PyPI (versions as tested, pinned in `constraints.txt`), and POV-Ray is a separate
program installed from the distribution. This file summarises their licences for the
0.1.0 release review (0.2.0 adds no dependencies); consult each project for the
authoritative terms.

## Python runtime dependencies (installed with `pip install .`)

| Package | Tested version | Licence |
| --- | --- | --- |
| PySide6-Essentials, shiboken6 (Qt for Python) | 6.12.0 | LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only |
| vtk | 9.7.2 | BSD-3-Clause |
| pyvista | 0.49.2 | MIT |
| pyvistaqt | 0.13.2 | MIT |
| QtPy | 2.4.3 | MIT |
| ase (Atomic Simulation Environment) | 3.29.0 | LGPL-2.1-or-later |
| numpy | 2.5.4 | BSD-3-Clause (and bundled permissive licences) |
| scipy | 1.18.1 | BSD-3-Clause |
| matplotlib | 3.11.2 | Matplotlib licence (PSF-based) |
| pillow | 13.0.0 | MIT-CMU |
| Other transitive packages (attrs, certifi, charset-normalizer, contourpy, cycler, cyclopts, docstring_parser, fonttools, idna, kiwisolver, markdown-it-py, mdurl, packaging, platformdirs, pooch, Pygments, pyparsing, python-dateutil, pyvista-validation, requests, rich, rich-rst, scooby, typing_extensions, tzdata, urllib3) | see `constraints.txt` | MIT, BSD, Apache-2.0, PSF-2.0, or MPL-2.0 (certifi) |

Qt for Python and ASE are used as unmodified, separately installed libraries, which the
LGPL permits from MIT-licensed code; users can replace them with other versions.

## External programs

| Program | Licence | Use |
| --- | --- | --- |
| POV-Ray 3.7 (`povray`, distribution package) | AGPL-3.0 | Run as a separate process to render scenes; not distributed with Ycrystal |
| POV-Ray standard include files (`povray-includes`) | POV-Ray licence (AGPL-3.0) | Exported scenes `#include` them by name (for example `metals.inc`) and use their identifiers; the files are not copied |

Images rendered by POV-Ray, including the gallery thumbnails shipped in
`src/ycrystal/presets/thumbnails/`, are outputs of Ycrystal's own scenes.

## Data and recipes

- Element colours and covalent radii come from ASE (`ase.data`, Jmol colours) at run
  time.
- The "ASE style" material presets reuse the finish parameters of ASE's `ase.io.pov`
  material styles (LGPL-2.1-or-later); their provenance is recorded in each manifest.
- All other material and environment recipes, the icon, and the example projects are
  Ycrystal's own (MIT).
