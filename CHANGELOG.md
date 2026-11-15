# Changelog

All notable changes to Ycrystal. Versions follow [semantic versioning](https://semver.org/);
before 1.0 the Python interface may change between minor versions.

## Unreleased

- Lighting Setup and live lighting (FR-LIGHT-01): **Lighting Setup…** opens a 3D
  overview of the key and fill lights, the output camera and frame, the focal point and
  geometry centre, the azimuth/elevation guides, the area-light diameter, and the
  reflection panel, with its own camera. Dragging the key-light handles sets azimuth and
  elevation (one undo step; Esc cancels). The live view now uses the key and fill lights
  at their real positions and intensities instead of VTK's default light kit. One shared
  helper (`ycrystal.core.lighting.resolve_lighting`) resolves the lights for POV-Ray and
  both views; exported scenes are unchanged.

- Lock aspect ratio (FR-RENDER-01): a padlock button beside Width and Height in the
  Render panel. Locked (default), editing one dimension computes the other from a kept
  target ratio without cumulative drift; unlocked, they are independent. Presets and
  Swap respect the lock; edits that would exceed 16–8000 px are refused with an
  explanation; the lock state is saved in projects (older projects open locked).

- Colour dialog for element, background, and floor colours (FR-COLOR-01): spectrum, the
  140 CSS named colours, and typed input as hex, RGB 0–255, RGB 0–1, HSV, HSL,
  `rgb()/hsv()/hsl()`, or a colour name; all fields stay in sync; numbers are never
  reinterpreted; invalid text cannot be accepted; keyboard operation and accessible
  names.
- Colour names for accessibility: resting the mouse on a colour names it in plain words
  and gives the nearest CSS named colour (CIEDE2000); colour buttons name their colour
  in tooltips and for screen readers (`ycrystal.core.colors`).

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
