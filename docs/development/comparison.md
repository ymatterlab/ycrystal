# Feature comparison with VESTA, OVITO, and CView

A factual comparison for the software paper (FR-VALIDATION-01). Read the method first:
the Ycrystal column was **tested** in this repository, while the other three columns
come **only from documentation** and nothing in them was tested.

## Method

- **Sources.** The official documentation of each program, read on 17 November 2026.
  Every entry below has a quotation and a link in the [sources](#sources).
  - VESTA: the online manual (title page dated 10 August 2022) and download page
    (stable 3.5.8; development 3.90.9a).
  - OVITO: user manual and Python reference of version 3.17.2 (released 2 November
    2026).
  - CView: documentation of version 1.3.1, the project repository, and the abstract of
    the 2026 *J. Appl. Cryst.* article. The article's full text could not be retrieved,
    so only its abstract was read.
- **Nothing was installed or tested** for VESTA, OVITO, or CView. Entries mean:
  - **documented**: the documentation describes the feature;
  - **not found**: the consulted documentation does not mention it. This does not mean
    the program lacks it;
  - **planned**: the project lists it as future work;
  - **removed**: the change log says so.
- **Ycrystal entries** were verified by the tests named, on the version in this
  repository (0.4.0.dev0).
- Features change between versions. This table describes the versions listed above
  and must be checked again before publication.

## Comparison

| Feature | Ycrystal (tested) | VESTA (documented) | OVITO (documented) | CView (documented) |
| --- | --- | --- | --- | --- |
| Ray-traced rendering | Yes: POV-Ray 3.7, an external program that must be installed (Y1) | Not found; uses OpenGL (V1) | Yes: built-in Tachyon, OSPRay, VisRTX (Pro in the desktop program). The POV-Ray renderer was removed in 3.0.0, the POV-Ray scene exporter in 3.16.0 (O1) | Not found; Cairo and OpenGL (C1) |
| Vector graphics export of the 3D scene | **No**: PDF export holds a raster image (Y2) | Yes: EPS, PDF, PS, SVG, with stated limits (V2) | Not found; image output is PNG, JPEG, TIFF (O2) | Yes: PDF, SVG (C2) |
| High-resolution raster images | Yes: a chosen pixel size (16–8000 px on the command line, PNG); PNG, JPEG, PDF from the window, with physical size and dpi (Y3) | Yes: scale factor beyond the screen size (V3) | Yes: output size in pixels (O3) | Yes: PNG (2000 × 1500 default), TIFF with dpi (C3) |
| Reusable style or template for other structures | Yes: `.ycstyle` files, in the window and from the command line (Y4) | Yes: `.vesta` file with linked structure as template; `style.ini` (V4) | Yes: session states as templates, "Pick new file", colour and radius themes (O4) | Not found; display preferences are saved (C4) |
| Explicit mapping of one element's appearance to another element | Yes (Y5) | Not found | Not found; themes match type names (O5) | Not found |
| Images without a window, and batch processing | Yes: `--render`, `--export-pov`, `--batch` manifests, no display needed (Y6) | Command-line image export (`-export_img`), listed among commands that work only with the GUI window; batch not found (V5) | Yes: Python module and `ovitos`, headless on Linux, batch processing (O6) | Planned (C5) |
| CIF input | Yes, without partial occupancy or overlapping sites (Y7) | Yes, fractional coordinates only (V6) | Yes, one data block, fractional coordinates (O7) | Yes (C6) |
| VASP POSCAR/CONTCAR input | Yes, VASP 5 and 4 (elements asked for VASP 4) (Y7) | Yes; needs OUTCAR for element symbols (V6) | POSCAR yes; CONTCAR not named (O7) | Yes (C6) |
| Quantum ESPRESSO pw.x input | Yes, `ibrav = 0` only (Y7) | Not found (XSF written by QE is read) (V6) | Yes, `ibrav` = 1, 2, 3, −3 only (O7) | Yes (C6) |
| Atom-attached vectors (magnetic moments) | Yes, entered in the window; no import from calculation output (Y8) | Yes (V7) | Yes, arrow glyphs, centred option (O8) | Planned (C7) |
| One file with structure and all view settings | Yes: `.ycrystal`, self-contained (structure, pictures, custom materials) (Y9) | Yes: `.vesta` holds structure and graphic settings; volumetric data stay external (V8) | Session state with pipeline, viewport, render settings; whether atom data are inside is not stated (O9) | Only for charge-density figures (`.cview.json`) (C8) |
| Provenance record of a rendered image (versions, checksums) | Yes (Y10) | Not found | Not found | Not found |
| Licence; systems | MIT; Linux and macOS (Apple silicon) from source, Windows not verified; repository private at the time of writing (Y11) | Free for academic and non-commercial use, closed source; Windows, macOS, Linux (V9) | OVITO Basic and the Python module MIT, OVITO Pro proprietary; Windows, Linux, macOS (Apple silicon) (O10) | MIT; Windows, macOS, Linux (Flatpak) (C9) |

Things Ycrystal does **not** do, in contrast to at least one of the others according to
their documentation: vector graphics, polyhedra, volumetric data and isosurfaces
(VESTA (V2); CView (C1)), and analysis pipelines or trajectories (OVITO (O4); CView
(C1)). Ycrystal is a figure tool for periodic crystal structures. The case for it rests
on the integrated workflow: a style designed in the window, transferred with an
explicit element mapping, deterministic views, batch rendering, and self-contained
snapshots with provenance. It does not rest on any single feature being unique.

## Sources

### Ycrystal (tested in this repository)

- **(Y1)** POV-Ray 3.7 is found and checked by `ycrystal --check-renderer`. Rendering
  tests: `tests/test_render_alignment.py`, `tests/test_validation.py`.
- **(Y2)** FR-EXPORT-01: the PDF holds the POV-Ray raster image
  ([rendering guide](../guide/rendering.md)). Tests: `tests/test_export.py`,
  `tests/test_gui_export.py`.
- **(Y3)** `--width`/`--height` 16–8000 px; *Render Image…* in the window. Tests:
  `tests/test_release.py`, `tests/test_export.py`.
- **(Y4)** FR-STYLE-CLI-01, *File ▸ Import Style…*. Tests: `tests/test_style.py`,
  `tests/test_validation.py::test_styles_never_change_the_scientific_data`.
- **(Y5)** FR-STYLE-MAP-01, `--element-map`. Tests: `tests/test_style.py`,
  `tests/test_gui_style_map.py`.
- **(Y6)** FR-BATCH-01. Tests: `tests/test_batch_manifest.py`; tests in CI that load no
  window toolkit and need no display.
- **(Y7)** [Supported file formats](../FORMATS.md). Tests: `tests/test_readers.py`.
- **(Y8)** FR-VECTOR-01. Tests: `tests/test_vectors.py`, `tests/test_validation.py`.
- **(Y9)** Project schema 7 with ZIP packages. Tests: `tests/test_project.py`,
  `tests/test_background_image.py`, `tests/test_reproducibility.py`.
- **(Y10)** FR-REPRO-01 ([reproducible figures](../guide/reproducibility.md)). Tests:
  `tests/test_reproducibility.py`.
- **(Y11)** `LICENSE`; [support matrix](../guide/support.md); [handoff](../HANDOFF.md)
  for the verified platforms.

### VESTA (documentation only)

- **(V1)** "Because VESTA utilizes OpenGL technology, the use of an OpenGL-capable
  graphics processing unit (GPU) is highly recommended but not always mandatory."
  POV-Ray, ray tracing, Tachyon, and OSPRay are not mentioned anywhere in the manual.
  [Chapter 3](https://jp-minerals.org/vesta/en/doc/VESTAch3.html)
- **(V2)** "Images of structural and volumetric data displayed in the Graphics Area of
  the Main Window can be saved as vector images." The formats are EPS, PDF, PS, and
  SVG. "Colors of isosurfaces and sections colored according to volumetric data cannot
  be represented with vector image formats. Translucent polygons of polyhedra, lattice
  planes, and isosurfaces become opaque in all the formats except for PDF."
  [18.5.3 Graphic images](https://jp-minerals.org/vesta/en/doc/VESTAch18.html#x37-26400018.5.3)
- **(V3)** "The image size of the exported graphics files is scaled up as a multiple of
  the size of the Graphics Area … VESTA can export huge images that exceed the maximum
  width and height of the viewport." (same section); `-export_img … scale=n`
  ([chapter 17](https://jp-minerals.org/vesta/en/doc/VESTAch17.html)).
- **(V4)** "This option is useful in preparing a file, *.vesta, with the VESTA format as
  a template file for setting objects and overall appearances."
  [6.3.6](https://jp-minerals.org/vesta/en/doc/VESTAch6.html#x18-870006.3.6); "style.ini
  — Default file for styles of the graphic scene" (18.1).
- **(V5)** "-export_img options file … Export an image to file. Image format will be
  automatically recognized by file extension."
  [Chapter 17](https://jp-minerals.org/vesta/en/doc/VESTAch17.html). The command appears
  under "17.4 Commands that only work with GUI window"; the section "17.2 Commands that
  only work with -nogui mode" lists no command (checked on 17 November 2026).
- **(V6)** "Crystallographic Information File (CIF; *.cif)"; "Cartesian coordinates
  included in CIFs cannot be input with VESTA". VASP files including POSCAR and
  CONTCAR "must accompany another file, OUTCAR, to display structural models".
  Quantum ESPRESSO is mentioned only as a program that writes XSF.
  [18.5.1 Input](https://jp-minerals.org/vesta/en/doc/VESTAch18.html#x37-25400018.5.1)
- **(V7)** "These arrows serve to represent magnetic moments or directions of static and
  dynamic displacements of atoms."
  [9.1 Vectors on Atoms](https://jp-minerals.org/vesta/en/doc/VESTAch9.html#x22-1140009.1)
- **(V8)** "Files with the VESTA format contains all the structural data and graphic
  settings whereas volumetric data are not directly recorded in *.vesta but imported
  from external files."
  [18.5.2](https://jp-minerals.org/vesta/en/doc/VESTAch18.html#x37-25800018.5.2)
- **(V9)** "This software is distributed free of charge for academic, scientific,
  educational, and non-commercial users"; its source code is "not open to the public"
  ([licence](https://jp-minerals.org/vesta/en/doc/VESTAli1.html)). "VESTA runs on
  Microsoft Windows …, macOS, and Linux."
  ([chapter 2](https://jp-minerals.org/vesta/en/doc/VESTAch2.html))

### OVITO 3.17.2 (documentation only)

- **(O1)** Rendering engines: Tachyon, OSPRay, and VisRTX ("pro" in the desktop program)
  ([rendering](https://www.ovito.org/manual/reference/rendering/index.html)). Change log
  ([new features](https://www.ovito.org/manual/new_features.html)):
  - 2.8.0: "Added the POV-Ray rendering backend and the POV-Ray scene file exporter."
  - 3.0.0: "Removed the POV-Ray rendering engine (POV-Ray scene file export is still
    available)."
  - 3.16.0: "Removed POV-Ray scene exporter."
- **(O2)** `Viewport.render_image`: "Supported output formats are: .png, .jpeg, and
  .tiff." ([ovito.vis](https://www.ovito.org/manual/python/modules/ovito_vis.html)) Data
  plots can be saved as PDF; no vector export of the 3D scene was found.
- **(O3)** "Output image size — Sets the width and height of the rendered image or movie
  in pixels."
  ([render settings](https://www.ovito.org/manual/reference/rendering/render_settings.html))
- **(O4)** "Create a template to apply the same data analysis pipeline and camera setup
  to multiple simulations."
  ([miscellaneous](https://www.ovito.org/manual/usage/miscellaneous.html)); "Pick new
  file — Selects a different file as input for the pipeline while preserving existing
  modifiers." ([external file](https://www.ovito.org/manual/reference/pipelines/data_sources/external_file.html));
  theme files `.ovito-theme`
  ([particle settings](https://www.ovito.org/manual/reference/app_settings/particle_settings.html)).
- **(O5)** "Only types present in the imported file will be updated…" (particle settings).
- **(O6)** "OVITO's rendering engine works headless on Linux: it requires no desktop
  session, display server, or X11/Wayland connection"
  ([installation](https://www.ovito.org/manual/installation.html)); "ideal for
  batch-processing large numbers of simulation files"
  ([Python introduction](https://www.ovito.org/manual/python/introduction/getting_started/introduction.html)).
- **(O7)** CIF: one data block, fractional coordinates
  ([CIF](https://www.ovito.org/manual/reference/file_formats/input/cif.html)); POSCAR,
  standard and direct format
  ([POSCAR](https://www.ovito.org/manual/reference/file_formats/input/poscar.html));
  Quantum ESPRESSO pw.x input, "Bravais lattice types other than ibrav=1, 2, 3, and -3
  are not supported"
  ([Quantum ESPRESSO](https://www.ovito.org/manual/reference/file_formats/input/quantum_espresso.html)).
- **(O8)** "This visual element shows arrow glyphs to visualize a local vectorial
  property associated with each particle"
  ([vectors](https://www.ovito.org/manual/reference/pipelines/visual_elements/vectors.html)).
- **(O9)** "You can save your current session, including the data pipeline, viewport
  settings, render settings, and other configurations, to a .ovito state file"
  (miscellaneous).
- **(O10)** "OVITO Basic is published … under the terms of the MIT License. OVITO Pro is
  proprietary software"; the Python module is MIT-licensed
  ([licences](https://www.ovito.org/manual/licenses/index.html)). Windows, Linux, and
  "macOS 14.4+, Apple Silicon" (installation).

### CView 1.3.1 (documentation and article abstract only)

- **(C1)** "The main viewer uses CPU-based Cairo rendering … Two optional windows — the
  3D CHGCAR isosurface view and the MD/relaxation Trajectory Player — use OpenGL 3.3"
  ([README](https://github.com/mavensgroup/cview)).
- **(C2)** "All three-dimensional content is rendered through Cairo as
  resolution-independent vector graphics, so that figures exported as PDF or SVG from
  the interactive viewer drop directly into a publication without rasterization
  artefacts." (abstract,
  [doi:10.1107/S1600576726009003](https://doi.org/10.1107/S1600576726009003))
- **(C3)** "PNG Image: Renders a high-resolution raster image (default resolution:
  2000×1500 pixels)." ([documentation](https://mavensgroup.github.io/cview/print.html))
- **(C4)** "How polyhedra are drawn is a saved preference" (documentation); no style or
  template file was found.
- **(C5)** To Do, *Automation*: "Command-line conversion, standardization, k-path and
  figure export without opening the window." (documentation, listed as planned)
- **(C6)** "It reads and writes … CIF, VASP POSCAR and CHGCAR, Quantum ESPRESSO input
  files, extended XYZ" (abstract); file table with POSCAR, CONTCAR, and pw.x input
  (documentation).
- **(C7)** To Do, *Visualization*: "Magnetic moments as arrows, read from VASP (MAGMOM,
  OUTCAR), Quantum Espresso and magnetic CIF." (documentation, listed as planned)
- **(C8)** "A scene file (.cview.json) is saved next to every figure" (charge-density
  figures); "The Atom Instances tab provides session-only cosmetic overrides"
  (documentation).
- **(C9)** "CView is open-source software licensed under the MIT Licence"; Windows 10/11,
  macOS (Intel and Apple silicon), Linux as Flatpak (documentation). The abstract lists
  `.deb` and `.rpm` packages; release 1.3.1 provides `.exe`, `.dmg`, and `.flatpak`.
