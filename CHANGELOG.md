# Changelog

All notable changes to Ycrystal. Versions follow [semantic versioning](https://semver.org/);
before 1.0 the Python interface may change between minor versions.

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
