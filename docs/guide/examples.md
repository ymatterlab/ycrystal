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
| `examples/batch-series.json` | A batch manifest: the grey studio style for SrTiO3, BaZrO3 (Ti → Zr), MgB2 (down c), a triclinic cell, and the vector example, all 600 × 450; see [render a series](#render-a-series-from-a-manifest) |
| `examples/publication/` | The publication gallery: two styles (paper and cover), a manifest with snapshots, and structure inputs including kyanite from the Crystallography Open Database; see the [figure gallery](gallery.md) |

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

For a structure with other elements, map them in the same dialog. For example, to give
BaZrO3 the chrome that the style gives Ti:

1. Open `tests/fixtures/BaZrO3.cif` (**File ▸ Open…**).
2. Choose **File ▸ Import Style…** and pick `examples/grey-studio.ycstyle`.
3. Under **Element settings go to**, the row `O →` shows `O` (matching symbol) and the
   row `Ti →` shows **Do not transfer** (BaZrO3 has no Ti). The text below reads
   `Element settings applied: O.` and `Left out: Ti.`
4. Set the `Ti →` row to `Zr`. The text changes to
   `Element settings applied: O, Ti → Zr.`
5. Press **Apply**. Zr is now chrome and O ceramic, in the grey studio; **Edit ▸ Undo**
   removes the whole import in one step.

Setting the `Ti →` row to `O` instead is refused before **Apply**: the dialog explains
that O would receive the settings of both O and Ti, and **Apply** stays disabled until
you choose differently (or set the `O →` row to **Do not transfer**).

## Apply a style from the command line

**Why.** Figures in one paper or talk usually share a look: the same background,
lighting, floor, image size, and materials. Design that look once in the window, save it
as a style (**File ▸ Export Style…**), and give it to every other structure from the
command line, for example from a script that renders a whole series. The figures stay
consistent, and nobody has to repeat the same clicks for each structure.

`--style` applies a `.ycstyle` file to `FILE` before `--render` or `--export-pov`, without
a window. A style has two kinds of settings:

- settings that suit **any structure**: the environment (background, floor, lighting),
  the output size, and the default material;
- settings **for particular elements**: element materials, colours, and radii, and
  bond-pair rules (for example "Ti is chrome").

The first kind always applies. The second kind applies to the elements the structure
contains. The style designed for SrTiO3 therefore gives MgB2 the same grey studio, even
though MgB2 has neither Ti nor O (a warning says that those settings were not used):

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

### Map elements to another composition

**Why.** Element settings are stored by element symbol, so they are lost when the
composition changes, even when the figures should match. SrTiO3 and BaZrO3 are both
ABO3 perovskites: Zr sits where Ti sits, at the centre of the oxygen octahedron. In a
series of perovskite figures you will usually want the B-site atom drawn the same way in
every figure, so readers can compare them at a glance. A mapping says which element of
the new structure takes over which element's look. You decide the correspondence;
Ycrystal never guesses it.

The grey studio style has settings for Ti (chrome) and O (ceramic). BaZrO3
(`tests/fixtures/BaZrO3.cif`, an illustrative cubic perovskite) has O but no Ti, so
without a mapping its Zr atoms keep the default material. `--element-map` gives the Ti
settings to Zr:

```bash
.venv/bin/ycrystal tests/fixtures/BaZrO3.cif --style examples/grey-studio.ycstyle --element-map Ti=Zr --render BaZrO3.png
```

This renders chrome Zr and ceramic O in the grey studio, with no warning. Two more
examples, with the messages they print:

```bash
# A deliberately partial mapping: Ti's chrome goes to Mg; MgB2 has no O.
.venv/bin/ycrystal tests/fixtures/MgB2.cif --style examples/grey-studio.ycstyle --element-map Ti=Mg --render MgB2-chrome.png
# WARNING: Element overrides for O were not applied: the structure has no O.

# Ti's chrome to Zr, and leave the style's O settings out (O keeps its default look).
.venv/bin/ycrystal tests/fixtures/BaZrO3.cif --style examples/grey-studio.ycstyle --element-map Ti=Zr,O=- --render BaZrO3-no-O.png
# WARNING: Element settings for O were left out by the element mapping.
```

Nothing is guessed: B in MgB2 gets no settings, because no element is mapped to it.

- **Syntax.** `SOURCE=TARGET` pairs separated by commas: `--element-map Sr=Ba,Ti=Zr`.
  `SOURCE=-` leaves the style's settings for `SOURCE` out: `--element-map O=-`.
  Symbols are case-sensitive; spaces around them are ignored. Elements that are not
  listed keep matching by symbol. `--element-map` needs `--style`.
- **What moves.** The element materials, colours, and radii of the `appearance` part,
  and the bond-pair rules of the `display` part (when requested with `--style-parts`).
  Atoms, element labels, coordinates, vectors, and which bonds exist are never changed,
  and per-atom settings still transfer only to the same structure.
- **Warnings.** A source element the style has no settings for is reported (with
  `--element-map Sr=Ba` the grey studio prints `WARNING: The style has no element
  settings for Sr; its mapping changes nothing.`), as are settings left out with `=-`.
- **Errors.** A malformed entry, an unknown or wrongly capitalised symbol (`ti`), or an
  element mapped twice is a usage error (status 2). A target the structure does not
  contain (`Ti=Mg` for BaZrO3), two elements mapped to one target, or a mapping onto an
  element that keeps its own settings (`Ti=O`, while the style also has O settings) is
  an error (status 1). In every case nothing is written and POV-Ray does not start.

The mapping is a presentation choice, not a statement of chemical equivalence or site
correspondence; see [element mapping](appearance.md#element-mapping-a-style-for-another-composition).

## Choose the view and framing

**Why.** Without options, `--render` and `--export-pov` draw a project with its saved
camera and a structure file with the default view. That suits one figure. For a series,
or for figures made by a script, you usually want every structure seen along the same
crystallographic direction, framed so that nothing is cut off, and sometimes drawn at
the same physical scale so that sizes can be compared. These options choose the camera
without opening the window; the structure itself is never rotated or moved.

```bash
# Look down the c axis of MgB2 (the hexagonal cell seen from above):
.venv/bin/ycrystal tests/fixtures/MgB2.cif --view c --render MgB2-c.png
# Two perovskites along a, at the same scale: 9 Å of height in both images.
.venv/bin/ycrystal tests/fixtures/SrTiO3.cif --view a --view-height 9 --width 600 --height 600 --render SrTiO3-a.png
.venv/bin/ycrystal tests/fixtures/BaZrO3.cif --view a --view-height 9 --width 600 --height 600 --render BaZrO3-a.png
# A saved project after a style changed its cells: keep its orientation, refit the frame.
.venv/bin/ycrystal examples/MgB2-gradient.ycrystal --style examples/grey-studio.ycstyle --style-parts display --camera-policy fit --render MgB2-refit.png
```

In the second pair the BaZrO3 cell (a = 4.19 Å) is visibly larger than the SrTiO3 cell
(a = 3.905 Å), because both images show 9 Å of height.

- **`--view`** `default`, `a`, `b`, `c`, `x`, `y`, or `z`: the named axis points toward
  the viewer, as with the window's **View along** buttons (same rule, same camera). `a`,
  `b`, `c` are the **real-space lattice vectors**, not normals of lattice planes (hkl);
  for skewed cells they differ from each other and from x, y, z. Screen up is the first
  of c, b, a (z, y, x) that is not parallel to the axis: down a or b, c is up; down c,
  b is up. A structure without a cell has no a, b, c views (an error says so); `x`, `y`,
  `z`, and `default` always work.
- **`--camera-policy`** `saved` or `fit`. `saved` (the default without `--view`) uses
  a project's saved camera exactly as saved; a structure file, which has none, gets the
  default view. `fit` keeps the saved orientation but refits the centre and scale to
  what is drawn now, useful after a style changed the repetitions. `--view` and
  `--view-height` imply `fit`; combining them with `--camera-policy saved` is a usage
  error.
- **Fitting** includes everything drawn: atoms, cell edges, and whole vector arrows.
  Nothing is clipped at any output shape, portrait or landscape. `--fit-margin` sets the
  space around it as a fraction of the half-height, 0–1 (default 0.06).
- **`--view-height ANGSTROM`** shows a fixed height of the scene (in Å) instead of
  fitting the scale, centred on the scene; the width follows the image's shape. If the
  scene does not fit, the command stops with an error that gives the height needed (for
  example `it needs at least 5.85 Å` for SrTiO3 along a at 1200 × 800) instead of
  cutting the figure.
- **Without these options nothing changes**: the camera is chosen exactly as before.
- **Errors.** An unknown view, a margin outside 0–1, a non-positive height, or
  `--camera-policy saved` with `--view` is a usage error (status 2); these options
  without `--render` or `--export-pov` are a usage error too, and open no window. A
  lattice view without a cell, or a scene too large for `--view-height`, is an error
  (status 1). Nothing is written in either case.

Orthographic projection is used throughout, so atoms at the back are as large as atoms
at the front, and the visible height in Å is a true scale of the structure.

## Render a series from a manifest

**Why.** A paper often needs the same kind of figure for many structures: one style,
one orientation, one size, perhaps with an element mapping for some of them. Running
one command per structure works, but the settings end up scattered over a shell
script. A **batch manifest** states them once, in a small JSON file that you can keep
next to the data, check in, and rerun later. Ycrystal checks the whole manifest before
it renders anything, renders the figures one after the other, and writes a report of
what happened.

```bash
.venv/bin/ycrystal --batch examples/batch-series.json --output-dir renders --dry-run
.venv/bin/ycrystal --batch examples/batch-series.json --output-dir renders
```

The first command checks everything and lists what would be rendered, without
rendering or writing anything:

```text
WARNING: MgB2: Element overrides for O, Ti were not applied: the structure has no O, Ti.
WARNING: afm-vectors: Element overrides for O, Ti were not applied: the structure has no O, Ti.
SrTiO3: would render SrTiO3.png (600 × 450, 15 atoms)
BaZrO3: would render BaZrO3.png (600 × 450, 15 atoms)
MgB2: would render MgB2.png (600 × 450, 10 atoms)
triclinic: would render triclinic.png (600 × 450, 5 atoms)
afm-vectors: would render vectors/afm.png (600 × 450, 22 atoms)
Checked 5 job(s); nothing was rendered (--dry-run).
```

The second renders the five PNGs into `renders/` (about 6 s on the development Mac)
and writes `renders/ycrystal-batch-report.json`.

### The manifest

`examples/batch-series.json`, shortened:

```json
{
 "format": "ycrystal-batch",
 "schema_version": 1,
 "defaults": {"style": "grey-studio.ycstyle", "view": "a", "width": 600, "height": 450},
 "jobs": [
  {"id": "SrTiO3", "input": "../tests/fixtures/SrTiO3.cif"},
  {"id": "BaZrO3", "input": "../tests/fixtures/BaZrO3.cif", "element_map": {"Ti": "Zr"}},
  {"id": "MgB2", "input": "../tests/fixtures/MgB2.cif", "view": "c"},
  {"id": "triclinic", "input": "../tests/fixtures/triclinic.cif",
   "style_parts": ["environment", "output"]},
  {"id": "afm-vectors", "input": "vectors-synthetic-afm.ycrystal",
   "output": "vectors/afm.png", "camera_policy": "fit"}
 ]
}
```

- `format` and `schema_version` identify the file. `jobs` lists the figures, rendered
  in this order. Each job needs an `id` (letters, digits, `.`, `_`, `-`; unique) and an
  `input`: a structure file or a `.ycrystal` project.
- `defaults` holds settings for every job; a job can set any of them for itself, which
  replaces the default. The settings are those of the single-figure options:

| Setting | Meaning | Command-line equivalent |
| --- | --- | --- |
| `output` | PNG file in the output folder (default `<id>.png`); subfolders allowed | `--render` |
| `format` | `poscar`, `cif`, `qe`, or `project` (default: detected) | `--format` |
| `style` | `.ycstyle` file, or `null` for none | `--style` |
| `style_parts` | List of parts, default `["appearance", "environment", "output"]` | `--style-parts` |
| `element_map` | `{"Ti": "Zr"}`; `null` as a value leaves an element's settings out | `--element-map Ti=Zr` (`O=-`) |
| `view` | `default`, `a`, `b`, `c`, `x`, `y`, `z` | `--view` |
| `camera_policy` | `saved` or `fit` | `--camera-policy` |
| `fit_margin` | 0–1, default 0.06 | `--fit-margin` |
| `view_height` | Fixed visible height in Å | `--view-height` |
| `width`, `height` | Image size, 16–8000 px (default: the input's, or the style's) | `--width`, `--height` |
| `max_atoms` | Largest number of displayed atoms allowed, default 20,000 | (none) |

- Paths are relative to the manifest's folder, so a manifest works wherever the folder
  is copied with its data. Absolute input and style paths are accepted too; outputs
  must stay inside the output folder (no `..`, no absolute paths).
- Unknown keys are refused (a misspelt `"veiw"` is an error, not silently ignored). A
  `"comment"` key at the top level is allowed for notes.
- `"save_projects": true` at the top level also saves, next to each image, the figure's
  self-contained snapshot (`SrTiO3.ycrystal`) and its provenance record
  (`SrTiO3.provenance.json`); see [reproducible figures](reproducibility.md#a-series-save_projects-in-a-batch-manifest).

### What happens

1. **Everything is checked first.** Ycrystal reads every input and style, applies the
   styles and element mappings, chooses every camera, and checks every output name. It
   reports **all** problems of **all** jobs at once (for example a missing input, an
   unknown element, two jobs writing the same file, `../` in an output, a scene larger
   than `max_atoms` or than `view_height`) and then stops with status 2, before
   rendering or writing anything.
2. **Existing images are not replaced** unless you add `--overwrite`; without it, an
   existing image or report is one of the problems of step 1.
3. **Jobs run one after the other**, in manifest order. POV-Ray already uses all
   processor cores for one image, so jobs are not run in parallel. A job that fails
   (for example a POV-Ray error) is recorded and the others continue; an image is
   written only when its render succeeded, never half-written.
4. **The report** `ycrystal-batch-report.json` lists every job in order with its
   status (`rendered` or `failed`), time, size, number of atoms, warnings, and error
   message, plus the Ycrystal and POV-Ray versions. Paths are written as given in the
   manifest. With `save_projects`, `project` and `provenance` name each job's snapshot
   and record (otherwise they are `null`).
5. **Exit status:** 0 when every job was rendered; 1 when any job failed (or POV-Ray is
   missing, then nothing is rendered); 2 when the manifest is invalid.

`--batch` takes all settings from the manifest: combining it with `FILE`, `--render`,
`--style`, `--view`, or the other single-figure options is a usage error. Batch
rendering writes PNG files; PDF and JPEG come from **Render Image…** in the window.
