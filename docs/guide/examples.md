# Examples and the command line

The checkout's `examples/` directory contains ready-made projects and a style. They are
ordinary `.ycrystal` files with the structure embedded, so they open anywhere:

| File | Shows |
| --- | --- |
| `examples/SrTiO3-studio.ycrystal` | SrTiO3 2 × 2 × 1, chrome Ti and ceramic O, grey studio with floor shadows, 800 × 600 |
| `examples/MgB2-gradient.ycrystal` | MgB2 3 × 3 × 1 (from `tests/fixtures/MgB2.cif`), glossy B, blue gradient, 700 × 700 |
| `examples/triclinic-transparent.ycrystal` | Low-symmetry triclinic cell, matte, transparent PNG background, 900 × 600 |
| `examples/vectors-synthetic-afm.ycrystal` | Synthetic two-site cubic cell (not a real material) with opposite magnetic-moment arrows (±2.2 μB along z) assigned by hand, 800 × 600 |
| `examples/grey-studio.ycstyle` | The style of the SrTiO3 example, to apply to other structures |

Open one with **File ▸ Open…**, or `.venv/bin/ycrystal examples/MgB2-gradient.ycrystal`.
`python scripts/make_examples.py` regenerates them.

## Render without a window

```bash
.venv/bin/ycrystal examples/SrTiO3-studio.ycrystal --render SrTiO3.png
.venv/bin/ycrystal examples/SrTiO3-studio.ycrystal --render small.png --width 400 --height 300
.venv/bin/ycrystal tests/fixtures/MgB2.cif --render MgB2.png
.venv/bin/ycrystal tests/fixtures/MgB2.cif --export-pov out/MgB2.pov
```

`--render` draws a project exactly as saved (camera, output size, materials,
environment) or a structure file with the default settings and view, runs POV-Ray, and
writes the PNG; `--width`/`--height` override the size (the image keeps its centre and
height, as in the window). `--export-pov` writes `NAME.pov` and `NAME.ini` and needs no
POV-Ray; the directory must exist. Both need no display, so they also work over SSH or
in scripts. `--povray PATH` chooses the POV-Ray executable. Errors print `ERROR: …` and
exit with status 1. Files that need a question answered (format, CIF data block, VASP 4
elements) must be opened in the window first and saved as a project.

On the development laptop (Intel Core Ultra 5 135U), each example renders at 400 × 300
in about 1–2 seconds.

## Reuse the example style

Open your own structure, choose **File ▸ Import Style…**, and pick
`examples/grey-studio.ycstyle`. Element settings apply to the elements your structure
contains; see [styles](appearance.md#reusing-the-look-styles).
