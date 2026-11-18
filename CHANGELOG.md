# Changelog

All notable changes to Ycrystal. Versions follow [semantic versioning](https://semver.org/);
before 1.0 the Python interface may change between minor versions.

## Unreleased

Merged after the `v0.3.0` tag; not yet part of a release.

### Highlights
- **PDF and JPEG export with publication sizes (FR-EXPORT-01).** **Render ▸ Render
  Image…** (Ctrl+R; formerly *Render PNG…*) opens one dialog with a choice of format
  (PNG by default, PDF, JPEG) and size: the Render panel's output size, Single column
  (85 mm at 600 dpi), Double column (180 mm at 600 dpi), or Custom (width and height in
  px or mm, any resolution, optional shape lock). POV-Ray renders once at the export
  pixel size; the camera, the figure, and the project's output size are not changed.
  The PDF page has the figure's physical size and embeds the POV-Ray image losslessly:
  it is a raster image, not vector graphics. JPEG has a quality setting (default 95) and
  fills a transparent background with white. PNG and JPEG files record their resolution.
- **Styles from the command line (FR-STYLE-CLI-01).** `--style STYLE.ycstyle` applies a
  style to the input before `--render` or `--export-pov`, without a window:
  `ycrystal MgB2.cif --style grey-studio.ycstyle --render MgB2.png`. By default the
  materials, colours, and radii, the environment, and the output size are applied; the
  display settings (repetitions, hidden atoms, bonds) only with `--style-parts`. The
  transfer rules are those of *File ▸ Import Style…*; what is left out is printed as
  `WARNING:` lines. The input's coordinates, vectors, and a saved project's camera are
  kept, and `--width`/`--height` override the style's size. A style may not raise the
  display above 20,000 atoms from the command line.
- **Element mapping for styles (FR-STYLE-MAP-01).** A style made for one composition
  can give its element settings to other elements: `--element-map Sr=Ba,Ti=Zr` on the
  command line (`O=-` leaves an element's settings out), or the new **Element settings
  go to** rows in the Import Style dialog, which show what will be applied and left out
  before **Apply**. Materials, colours, radii, and bond-pair rules move; atoms,
  coordinates, vectors, and bonds do not, and per-atom settings still transfer only to
  the same structure. Ambiguous mappings are refused with an explanation. The mapping
  is a presentation choice, not chemistry, and is not stored in the style. New fixture
  `tests/fixtures/BaZrO3.cif` (illustrative cubic perovskite).
- **Choose the view and framing from the command line (FR-CAMERA-01).** `--view a|b|c|
  x|y|z|default` looks down a real-space lattice vector or a Cartesian axis (the same rule
  and camera as the window's View along buttons), fitted so that atoms, cell edges, and
  whole vector arrows are never cut off at any image shape. `--camera-policy fit`
  refits a saved project's frame while keeping its orientation, `--fit-margin` sets the
  space around a fitted view, and `--view-height ANGSTROM` draws several structures at
  the same physical scale (an error, never a crop, if the scene does not fit). Without
  these options the camera is chosen as before.
- **Render a series from a manifest (FR-BATCH-01).** `ycrystal --batch MANIFEST.json
  --output-dir DIR` renders every job of a small JSON manifest (inputs, a shared style,
  element mappings, views, sizes) to PNGs, one after the other, without a window. The
  whole manifest is checked first and every problem reported before anything is
  rendered; existing images are kept unless `--overwrite` is given; a failed job does
  not stop the others; `ycrystal-batch-report.json` records every job. `--dry-run`
  checks without rendering. Example: `examples/batch-series.json`.
- **Reproducible figures: snapshots and provenance (FR-REPRO-01).** `--save-project
  FIGURE.ycrystal` with `--render` (and `"save_projects": true` in a batch manifest)
  also saves the figure as a self-contained project, with the camera and image size it
  was rendered with, the style and element mapping already applied, and any background
  picture and custom materials inside; `ycrystal FIGURE.ycrystal --render OUT.png`
  renders it again without the original structure, style, or picture. A JSON
  provenance record `FIGURE.provenance.json` states the Ycrystal and POV-Ray versions,
  the settings (style parts, element mapping, camera policy and camera, sizes), the
  standard POV-Ray include files needed, and the SHA-256 of the input, style, snapshot,
  and image, with relative paths only. The image is rendered from the saved snapshot;
  the three files are written only if the render succeeds. Existing snapshots and
  records are replaced only with `--overwrite`. Replays give the same POV-Ray scene;
  on one machine they also gave identical pixels, but never identical PNG bytes
  (POV-Ray stores the render time in the file). The batch report names each job's
  snapshot and record. New guide: *Reproducible figures*.
- **Windows.** Ycrystal runs from a source checkout on Windows 11 with Python 3.12
  (`.venv\Scripts\ycrystal.exe`) and renders with POV-Ray for Windows 3.7
  (`pvengine64.exe`), which it finds in its installation folder. POV-Ray for Windows
  starts minimised for each render, writes its messages to a log that failures are
  explained from, and is kept from taking the keyboard focus away from the window.
  Since it runs one copy at a time, Ycrystal's own renders take turns, and a copy the
  user has open is reported with an explanation instead of POV-Ray's error dialog. The
  window has its own taskbar button and icon. Tested on one Windows 11 laptop (all
  automated tests, and by hand); Windows CI runs without POV-Ray. Installation steps
  in the install guide.

### Fixes
- Switching the view directly between some axes in the window (for example from c to
  x) could raise an error while the camera was half updated; the view now reports a
  camera change once, after it is complete.

### Details
- New application icon (a Y-shaped molecule on a dark tile on the macOS icon grid) and
  a horizontal logo in the README and the documentation. `scripts/render_logo.py`
  renders the logo variants with POV-Ray for maintainers; it is not part of the
  application.
- Linux: `--install-desktop` now refreshes the icon theme, so a reinstalled launcher
  shows the current icon in GTK and Cinnamon menus.
- `ycrystal --version` reports `0.4.0.dev0`, the development version after 0.3.0.
- Validation and benchmarks (FR-VALIDATION-01); no change to the application.
  - `tests/test_validation.py` checks the following, by measured image properties
    rather than stored pictures:
    - the scene file against the shared geometry;
    - ray-traced atoms, periodic images, bonds, and vector arrows against the camera
      model;
    - that fitted views are never cut off;
    - that styles leave the scientific data unchanged;
    - shadows, soft shadows, reflection, and refraction.
  - `scripts/benchmark_render.py` times renders through the command line (median and
    range, peak memory).
  - `scripts/replay_check.py` renders saved snapshots again, also on another machine,
    and compares the pixels.
  - New developer pages: *Validation and benchmarks* (evidence and tolerances),
    *Comparison with other programs* (VESTA, OVITO, CView, from their documentation
    only), and an *Independent evaluation checklist*.
- Publication gallery (FR-GALLERY-01); no change to the application.
  - `examples/publication/` contains:
    - two styles: a restrained *paper* style with colour-blind-safe site colours, and a
      ray-traced *cover* style;
    - a batch manifest with an explicit element mapping, a shared physical scale, and
      snapshots;
    - structure inputs, including kyanite (Al₂SiO₅, P-1) from the Crystallography Open
      Database, entry 1008755 (CC0, original authors credited).
  - `scripts/make_gallery.py` renders the seven figures through the command line. It
    adds two controlled variants from one snapshot (same geometry and camera), renders
    every snapshot again after deleting the inputs, and writes a figure-methods table.
  - New pages: *Figure gallery* (thumbnails of real renders) and *Proposed manuscript
    figures* (arrangement and captions).

## 0.3.0 — macOS support and richer scientific figures (16 November 2026)

Tag `v0.3.0` marks the merge of the macOS work (commit `6ed6b03`). The source at that
tag still reports version 0.2.0 (`ycrystal --version`); the version number was raised
afterwards. Projects are now saved with schema 7 (schema 6 added background pictures and
custom materials, schema 7 vectors): projects from 0.1.0 and 0.2.0 open with their
original appearance, but 0.2.0 and older cannot open projects saved by 0.3.0.

### Highlights
- **macOS on Apple silicon** alongside Linux: Homebrew installation, POV-Ray include
  files found next to the executable, native shortcut labels (⌘), and synchronous VTK
  drawing. CI tests on Ubuntu (everything, under Xvfb) and macOS (tests without
  windows). macOS runs from source; there is no application bundle or Finder
  association yet.
- **Measurements (FR-MEASURE-01).** **Distance** and **Bond angle** modes measure
  between clicked atoms, including exact periodic images; results (in Å and degrees,
  with B as the angle's vertex) collect in a **Measurements** panel at the bottom and
  can be copied. Measurements are not saved in projects.
- **Preview resolution (FR-PREVIEW-01).** The POV-Ray preview dock offers Small
  (480 px wide), Medium (800 px), Large (1200 px), or a custom width; the final image
  is unaffected.
- **Background pictures (FR-BGIMAGE-01).** Background type **Image** places a PNG or
  JPEG picture behind the structure in POV-Ray previews and images, with Fill/Fit,
  zoom, offsets, and brightness. Projects and styles with a picture are saved as ZIP
  packages that contain it, so they open on another computer.
- **Custom materials (FR-MATERIAL-01).** **Customize Material…** starts from a built-in
  recipe (Matte, Glossy, Glass, Gem, Marble, Wood, and others), edits its parameters,
  and applies the variant to the default, an element, or selected atoms, or saves it as
  a personal material with a thumbnail. Projects carry the definitions they use.
- **Atom-attached vectors (FR-VECTOR-01).** **Edit ▸ Vectors…** attaches Cartesian
  direction or magnetic-moment (μB) arrows to atoms, for all periodic images or single
  images, drawn in the live view, POV-Ray previews and images, and scene exports.
  Ycrystal infers no signs or magnetic symmetry.

### Details
- Resizing the window or a panel no longer marks the POV-Ray preview out of date (a
  resize is not a change of the figure).
- Personal-material thumbnails on macOS live in the application data folder.
- Background pictures appear in the live view as their average colour only; the
  picture itself appears in POV-Ray output.

## 0.2.0 — lighting, colours, and output size (15 November 2026)

The first release after 0.1.0. Projects, styles, and exported scenes stay compatible:
0.1.0 projects open unchanged (project schema 5), and scenes exported with the same
settings are identical apart from the header line with the version and time. No new
dependencies.

### Highlights
- **See and drag the lights (FR-LIGHT-01).** **Lighting Setup…** (Appearance tab or
  View menu) opens a 3D overview of the key and fill lights, the output camera and
  frame, the focal point *F* and geometry centre *C*, the azimuth and elevation guides,
  the area-light diameter, and the reflection panel. It has its own camera, so looking
  around never changes the image. Drag the key light to set its azimuth and elevation:
  the live view and the spin boxes follow, releasing makes one undo step, Esc cancels.
- **Live view lit like the render (FR-LIGHT-01).** The live view now uses the key and
  fill lights at their real positions and intensities instead of VTK's fixed light
  kit, so the shading direction matches the POV-Ray image (shadows, area-light
  softness, reflections, and the reflection panel still need the POV-Ray preview).
- **Lock aspect ratio (FR-RENDER-01).** A padlock beside Width and Height keeps the
  output shape while the resolution changes, without rounding drift; presets and Swap
  respect it, impossible sizes are refused with an explanation, and projects remember
  the state (0.1.0 projects open locked).
- **Colour dialog and colour names (FR-COLOR-01).** Choose element, background, and
  floor colours from a spectrum, the 140 CSS named colours, or typed hex, RGB 0–255,
  RGB 0–1, HSV, HSL, `rgb()/hsv()/hsl()`, or a name. Resting the mouse on a colour names
  it in plain words with the nearest CSS colour, which helps with colour-vision
  deficiencies; colour buttons announce their colour to screen readers.

### Details
- Lighting: one shared helper (`ycrystal.core.lighting.resolve_lighting`) resolves the
  camera-relative light values into world positions for the POV-Ray writer, the live
  view, and the overview. The user guide now explains the conventions: azimuth 0 points
  from *F* toward the camera, positive to the right of the image; elevation is above
  the image's horizontal; both lights sit 4 *R* + |*C* − *F*| + 10 Å from *F*; Light
  size is the area light's diameter in multiples of the scene radius *R*.
- Output size: locked edits keep the edited value and compute the other from a stored
  target ratio (half-up rounding); limits 16–8000 px; each edit, preset, or Swap is one
  undo step that also restores the ratio. Projects store the lock as two optional keys.
  A size change now triggers exactly one scene update (it used to trigger two or
  three).
- Colours: all fields stay in sync, numbers are never reinterpreted, invalid text
  cannot be accepted, and the dialog works from the keyboard
  (`ycrystal.core.colors`).
- Development: new tests for each feature; CI runs the new doctests; a keyboard test no
  longer depends on window focus under Xvfb.

## 0.1.0 — first usable release (milestones M0–M6)

Linux desktop application for reproducible crystal-structure figures rendered with
POV-Ray 3.7.

### Structures and projects
- Read VASP POSCAR/CONTCAR (VASP 4 and 5), CIF (ordered structures, one or several data
  blocks), and Quantum ESPRESSO pw.x input with `ibrav = 0` and `CELL_PARAMETERS`;
  unsupported constructs (partial occupancy, nonzero `ibrav`, `crystal_sg`) are
  rejected with an explanation.
- Self-contained `.ycrystal` projects (versioned JSON, schema 5) with the embedded
  structure and provenance; projects reopen without the source file and reproduce
  coordinates exactly. Older project schemas open unchanged.

### View and interaction
- Embedded VTK view with orthographic camera: orbit, pan, zoom, fit, reset, view along
  a, b, c, x, y, z; free or axis-constrained rotation (about a lattice or Cartesian
  axis) and step rotations.
- Click and Ctrl+click selection of displayed atoms; hide/show individual balls.
- Display repetitions (1–20 per axis) from numeric controls or by dragging the a/b/c
  supercell handles, boundary images, cell-edge modes, periodic bonds with tolerance,
  radius, and element-pair rules.
- Complete undo/redo for every figure change, including output size and style imports.

### Appearance and rendering
- Output frame with explicit output size; true POV-Ray preview (automatic or on demand,
  stale results discarded); non-blocking final render with progress and Cancel.
- 30 materials (scientific finishes, ASE styles, metals, glass and gems, decorative
  textures; native POV-Ray identifiers with their include files) and 12 environments
  (plain, gradients, studios with floors, skies) with POV-Ray thumbnails, search, and
  favourites; materials per default, element, or selected atom; element colours and
  radii; background, floor, and lighting controls.
- Editable `.pov`/`.ini` export recording versions and required include files.
- Reusable styles (`.ycstyle`) with explicit transfer rules to other structures.

### Command line and desktop
- `ycrystal FILE --render OUT.png` and `--export-pov OUT.pov` work without a window;
  `--check-renderer` verifies POV-Ray; `--install-desktop` adds a Linux Mint menu
  launcher and the `.ycrystal` file type.
- Example projects and a style in `examples/`.
