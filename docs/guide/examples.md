# Examples and the command line

The checkout's `examples/` directory contains ready-made projects and a style. They are
ordinary `.ycrystal` files with the structure embedded, so they open anywhere:

| File | Shows |
| --- | --- |
| `examples/SrTiO3-studio.ycrystal` | SrTiO3 2 × 2 × 1, chrome Ti and ceramic O, grey studio with floor shadows, 800 × 600 |
| `examples/MgB2-gradient.ycrystal` | MgB2 3 × 3 × 1 (from `tests/fixtures/MgB2.cif`), glossy B, blue gradient, 700 × 700 |
| `examples/triclinic-transparent.ycrystal` | Low-symmetry triclinic cell, matte, transparent PNG background, 900 × 600 |
| `examples/vectors-synthetic-afm.ycrystal` | Synthetic two-site cubic cell (not a real material) with opposite magnetic-moment arrows (±2.2 μB along z) assigned by hand, 800 × 600 |
| `examples/grey-studio.ycstyle` | The style of the SrTiO3 example (chrome Ti, ceramic O, grey studio, 800 × 600, 2 × 2 × 1 cells), to apply to other structures in the window or [with `--style`](#apply-a-style-from-the-command-line) |

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

## Apply a style from the command line

`--style` applies a `.ycstyle` file to `FILE` before `--render` or `--export-pov`, without
a window. The style designed for SrTiO3 gives MgB2 the same grey studio:

```bash
.venv/bin/ycrystal tests/fixtures/MgB2.cif --style examples/grey-studio.ycstyle --render MgB2.png
.venv/bin/ycrystal tests/fixtures/MgB2.cif --style examples/grey-studio.ycstyle --export-pov out/MgB2.pov
.venv/bin/ycrystal examples/vectors-synthetic-afm.ycrystal --style examples/grey-studio.ycstyle --render afm.png
```

The first command prints
`WARNING: Element overrides for O, Ti were not applied: the structure has no O, Ti.`
on standard error and renders an 800 × 600 PNG (the style's size).

- **Parts.** By default the command line applies `appearance` (default material, element
  materials, colours, and radii, arrow appearance), `environment` (background including a
  background picture, floor, lighting, transparency), and `output` (image size).
  `display` (atom size, repetitions, cell edges, bonds, hidden atoms) is left out,
  because the repetitions and hidden atoms of the style's structure rarely suit another
  one. Choose the parts with `--style-parts`, a comma-separated list, for example
  `--style-parts appearance,display,environment,output` for everything, or
  `--style-parts environment` for the studio only. In the window, **File ▸ Import
  Style…** offers all four parts as before.
- **Transfer rules.** The same as in the window: element settings apply to the elements
  the structure contains; per-atom materials and hidden atoms only to the same structure
  (same atoms in the same order). What is left out is printed as `WARNING: …` lines;
  the command still succeeds.
- **What is kept.** The coordinates, the cell, and the vectors of `FILE` are never
  changed, and neither `FILE` nor the style file is written. A saved project keeps its
  camera (with `display`, a warning says if the style's repetitions may not fit in it);
  a structure file gets the default view, fitted to the styled structure.
- **Size.** `--width` and `--height` override the style's size, each on its own:
  `--width 400` with the 800 × 600 style gives 400 × 600.
- **Large displays.** With `display`, a style may not raise the number of displayed
  atoms above 20,000; the command stops with an error before writing anything. Apply
  such a style in the window (which asks) and save a project, or leave out `display`.
- **Errors.** A missing or damaged style file prints `ERROR: …`, writes nothing, and
  exits with status 1. `--style` without `--render` or `--export-pov`, or an unknown
  part in `--style-parts`, is a usage error (status 2) and opens no window.
- A style package with a background picture or custom materials carries them, so it
  works on a machine where the picture and the personal materials do not exist.

`--render` still writes PNG only; PDF and JPEG come from **Render Image…** in the window.
