# Supported file formats

Ycrystal opens structure files and its own project files with **File ▸ Open…**
(Ctrl+O) or from the command line: `ycrystal FILE [--format poscar|cif|qe|project]`.
The format is detected from the file name and content. If it cannot be determined,
Ycrystal asks; **File ▸ Open As…** (or `--format`) sets it explicitly. A file that
cannot be read leaves the current scene unchanged and shows the reason.

The same summary is available in the application under **Help ▸ Supported File Formats**.

## VASP POSCAR / CONTCAR

Recognised names: `POSCAR*`, `CONTCAR*`, `*.vasp`, `*.poscar`, or POSCAR-like content.

Supported:

- VASP 5 files (element line) and VASP 4 files (no element line).
- Direct or Cartesian coordinates; one or three scale factors; a negative scale factor
  is the cell volume in Å³.
- Selective dynamics: kept per atom and axis, shown in the selection information
  (`fixed x y z` or `free`) and saved in projects.
- Any cell shape.

VASP 4 files carry no element names. Ycrystal does not guess them from the comment
line (a comment such as "In plane strained GaN" would otherwise read as In and Ga).
It asks for the element of each species in the order of the atom counts and proposes
symbols only when the comment lists exactly element symbols.

## CIF

Recognised names: `*.cif`, or content with `data_` and `_cell_length_a`.

Supported:

- Symmetry expansion from the listed symmetry operations or the space-group symbol.
- Any cell shape; the lattice is oriented with a along x and b in the xy plane.
- Several data blocks: Ycrystal asks which structure to open.
- Site labels (e.g. `Fe1`) are kept separately from elements; occupancies are recorded.

Not supported (the file is rejected with an explanation):

- Partially occupied or mixed sites (numeric `_atom_site_occupancy` below
  `1 - 1e-3`; near-unit values within this tolerance are retained).
- Distinct sites at the same position.

Ycrystal draws ordered structures only and never shows a disordered structure as if it
were ordered. Use an ordered model with explicit atoms instead.

## Quantum ESPRESSO pw.x input

Recognised names: `*.in`, `*.pwi`, `pw.in`, `pwscf.in`, or content with `&SYSTEM` and
`ATOMIC_POSITIONS`.

Supported:

- `ibrav = 0` with a `CELL_PARAMETERS` card in `alat`, `bohr`, or `angstrom` units.
  `alat` uses `celldm(1)` (bohr) or `A` (Å).
- `ATOMIC_POSITIONS` in `alat`, `bohr`, `angstrom`, or `crystal` units.
- Species labels such as `Fe1`, `Fe_up`, or `O-2` (an element symbol followed by a digit,
  `_`, `-`, `+`, or `.`). Labels are kept; the element is taken from the label.
- `if_pos` flags (0/1 after the coordinates), kept like selective dynamics.

Not supported (the file is rejected with an explanation):

- `ibrav` other than 0, i.e. lattices defined by `celldm(2…6)` or `A, B, C, cosAB…`.
  Rewrite the cell as `ibrav = 0` with `CELL_PARAMETERS`.
- `ATOMIC_POSITIONS crystal_sg` (symmetry-reduced positions).

Labels that do not name an element unambiguously (for example `Cb`, which could be
carbon) require the element to be entered when opening. Ycrystal never runs pw.x and
does not need pseudopotential files.

## Ycrystal projects (`.ycrystal`)

**File ▸ Save Project** (Ctrl+S) writes a versioned JSON file with:

- the complete structure (cell, positions, elements, labels, occupancies, movable flags),
- where it came from (original path and name, format, SHA-256 checksum, data block,
  element mapping, import time, reader version),
- display settings (repetitions, cell edges, boundary atoms, hidden atoms, bond rules,
  atom size and element radii), materials (default, element, and atom overrides),
  element colours, and the environment (background, floor, lighting),
- the camera of the output image and the output size.

A project reopens without the original structure file and reproduces the coordinates
exactly. Closing or opening another file with unsaved changes (including a changed view)
asks whether to save, discard, or cancel.

The camera is stored for the explicit output size, so a project reopens with the same
framing in a window of any shape.

Current project schema is 8 (schema 6 added background pictures, stored in ZIP
packages, and custom material definitions; schema 7 added atom-attached vectors; schema
8 added the element legend, `scene.legend`). Older projects remain readable with their
original appearance and no legend (schema-1 projects load with bonds switched off, as they were drawn). Newer
schemas are rejected with a message to update Ycrystal.

### Figure snapshots and provenance records

`ycrystal FILE … --render OUT.png --save-project FIGURE.ycrystal` (and
`"save_projects": true` in a batch manifest) saves the rendered figure as an ordinary
project, the *snapshot*, with the camera and output size it was rendered with, and a
JSON provenance record `FIGURE.provenance.json` (`format: ycrystal-provenance`, schema
1) with the versions, settings, and SHA-256 checksums of the input, style, snapshot,
and image. In a snapshot the structure's import record has no `path` (the original
folder); its name, format, and checksum remain. See
[reproducible figures](guide/reproducibility.md).

## Ycrystal styles (`.ycstyle`)

**File ▸ Export Style…** writes the presentation without structure and camera:
materials, colours, radii, the element legend, display settings, the environment, the
output size, and the element sequence of the source structure (used to decide whether per-atom settings can
transfer). See [reusing the look](guide/appearance.md#reusing-the-look-styles) for the
transfer rules. Style files are versioned JSON, or a ZIP package when they carry a
background picture; newer versions are rejected (style schema 3 added the element
legend; older styles load without one). An element mapping chosen when a style
is applied ([element mapping](guide/appearance.md#element-mapping-a-style-for-another-composition))
is not stored in the style file, which stays unchanged; a project saved afterwards
stores the resulting element settings.
