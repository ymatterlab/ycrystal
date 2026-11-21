# Architecture

Ycrystal keeps scientific data separate from presentation and rendering backends.
The Python interfaces are still evolving; inspect their source and tests when
extending them.

| Layer | Responsibility and dependency direction |
| --- | --- |
| `core/structure.py` | Scientific cell, positions, elements, labels, occupancy, movable flags, provenance. Lattice rows and positions are Cartesian Å. Array inputs are copied and stored read-only; metadata remains mutable. |
| `core/scene.py` | `SceneSettings` and `Environment` describe presentation. `build_geometry` resolves repetitions, boundary images, hidden IDs, periodic bonds, radii, colours, and cell edges into the shared `DisplayGeometry`. No Qt or VTK. |
| `core/camera.py`, `core/picking.py` | Immutable orthographic camera and analytic picking. Projection uses top-left continuous pixel coordinates. Navigation returns new cameras. No GUI dependency. |
| `io/readers.py`, `io/project.py` | File detection, ASE-backed readers, provenance, and versioned JSON projects. Questions are exceptions that the caller can answer and retry; no GUI dependency. |
| `gui/main_window.py`, `gui/commands.py` | Qt actions, dialogs, project state, selection, and display-setting undo stack. Coordinates are never edited by navigation or hiding. |
| `core/background.py`, `io/images.py`, `io/package.py` | Background pictures: the framing reference stored in an `Environment` and the shared placement arithmetic (no Qt/VTK); checked, content-addressed picture storage (Pillow); and the defensive ZIP container that projects and styles use when they carry a picture. |
| `presets/custom.py`, `gui/material_editor.py` | Custom material variants: typed parameter schemas for Ycrystal's own recipes, content-derived ids, generated POV-Ray recipe text; and the *Customize Material…* dialog with the personal list in `QSettings`. |
| `core/vectors.py`, `gui/vector_dialog.py` | Atom-attached vectors: typed records (Cartesian components, meaning), source defaults and image overrides, arrow appearance, and the single resolver that turns them into arrow geometry for `DisplayGeometry` (drawn by both renderers; no Qt/VTK); and the *Vectors* window and editor. |
| `core/measure.py` | Distances and bond angles between displayed instances (`AtomId`), computed from the structure's coordinates and cell only, plus the session state of the measurement modes. No Qt or VTK; nothing is saved in projects. |
| `core/lighting.py` | `resolve_lighting` turns an environment's relative light values into a world-space `LightingRig` (key, fill, reflection panel) for an output camera and a displayed geometry. Shared by the POV writer, the live view, and the Lighting Setup window; nothing is stored. No Qt or VTK. |
| `viewport/qt_viewport.py` | The VTK/PyVistaQt adapter. It consumes shared geometry, exchanges `Camera` objects, draws overlays, and reports clicks. VTK objects stay here. Its two scene lights come from the resolved rig. |
| `viewport/interactor.py` | The PyVistaQt interactor used by both views. Its `render()` draws before it returns on every platform (PyVistaQt alone defers the drawing to the event loop on macOS), which the start-of-render bookkeeping (output camera, lights, frame overlay) relies on. |
| `viewport/lighting_view.py` | The Lighting Setup overview: a second VTK window with its own camera that draws the rig and reports main-light handle drags as angles. Its graphics never reach the main view, picking, fitting, or exports. |
| `render/pov_writer.py` | Pure text export of shared geometry/camera into POV-Ray 3.7 and INI output. No renderer process or display needed. |
| `render/jobs.py`, `render/povray.py` | Isolated job directories, discovery, synchronous execution, results, and image copying. The caller owns cleanup. POV-Ray is found through the saved setting, `YCRYSTAL_POVRAY`, `PATH`, and on Windows the installation of POV-Ray for Windows (registry, Program Files); its standard include files are located from the executable's installation, never from a fixed system path alone. `render/povray.py` holds every renderer platform difference: POV-Ray for Windows (`pvengine64.exe`) is a window program that gets `/EXIT /NR +GAscene.log`, starts minimised, writes its messages to a log file, is kept from taking the keyboard focus, and is not started while another copy of it that keeps a single instance is open, or while it would ask at start-up whether to download its missing editor. |
| `gui/native.py`, `desktop.py` | The platform-dependent choices of the interface, kept in one place: modifier-key names in help texts, the folder for personal-material thumbnails, the taskbar identity and the program file filter on Windows, and the menu entry of `--install-desktop` (Linux: freedesktop launcher; Windows: Start-menu shortcut and `.ycrystal` file type under `HKEY_CURRENT_USER`; none on macOS). Each takes the platform as a parameter, so every branch is tested on any system. |
| `windows_shortcut.py`, `scripts/install-windows.ps1` | Windows only. Shortcuts (`.lnk`) with the application id that the window sets, so that its taskbar button belongs to the Start-menu entry, written through the shell's COM interfaces with `ctypes` (no extra package). The PowerShell installation script (the developer installation) installs Python and POV-Ray for Windows with `winget` where missing, `.venv`, the Start-menu entry **Ycrystal (development)**, and runs the renderer check; Windows CI runs it. |
| `packaging/windows/` | The graphical Windows installer (recommended for users): a PyInstaller specification that freezes `ycrystal.app.main` into `Ycrystal.exe` (window) and `ycrystal-cli.exe` (command line) sharing one folder, an Inno Setup script, the build script, and a coexistence check. The packaged program runs the same code; `desktop.is_packaged()` (`sys.frozen`) gives it its own application id and refuses `--install-desktop`. Its shortcut, application id, and file type differ from the developer installation's, and each side removes only its own (see [Windows installer](windows-installer.md)). |
| `core/export.py`, `render/formats.py`, `gui/export_dialog.py` | Image export (FR-EXPORT-01): formats, publication sizes, and mm/px/dpi arithmetic without Qt; writing the POV-Ray PNG as PNG (resolution chunk added, pixels untouched), JPEG, or PDF (`QPdfWriter`, lossless) through a checked `.part` file; and the *Render Image* dialog. All formats share one POV-Ray job; only the last step differs. |
| `core/legend.py`, `render/legend.py`, `gui/panels/legend_panel.py` | Element legend (FR-LEGEND-01): `LegendSettings` (in `SceneSettings.legend`) and the entries, read from `DisplayGeometry` so the markers have the drawn colours (no Qt); one `QPainter` layout and painter (QtGui only, no window) that draws the legend onto the rendered PNG in `finish_job`, draws the live view's overlay, and gives the frame region it leaves free for fitting; and the *Legend* tab. The legend is a 2D layer: the POV-Ray scene and the geometry never contain it. |
| `render/process.py` | Asynchronous `QProcess` adapter. Needs a running Qt event loop (`QCoreApplication` is enough), not a window. POV-Ray for Windows runs instead as a `subprocess.Popen` checked by a timer (PySide6's `QProcess` cannot start a program minimised), and the program's own runs of it take turns, since only one copy can render at a time. |
| `render/selftest.py`, `render/imagecheck.py` | Small renderer diagnostic and analytic/image alignment measurements. Runs without a display, but the diagnostic invokes POV-Ray. |

## Shared contracts

Both VTK and POV-Ray consume the same resolved geometry. A displayed atom is
identified by `(source_index, (na, nb, nc))`, with position equal to the input
position plus the offset multiplied by the row-vector lattice. Hiding removes that
ID from the shared geometry; it leaves all scientific data intact. Selection holds
IDs rather than array row indices because rows change when atoms disappear.

The [camera reference](../reference/camera.md) defines direction, handedness,
half-height scale, and pixels. Two cameras exist in the GUI: VTK's camera for the
whole view, and the **output camera** for the image inside the output frame (same
orientation and centre, parallel scale multiplied by the frame-to-view height ratio).
Export, preview, render, and projects use the output camera with the explicit output
size; resizing the window keeps it, so a resize is not a change of the figure (no
new scene revision, and a preview stays current). POV-Ray export writes explicit camera vectors and
may move the orthographic eye backward to put all geometry in front of it without
changing projection. VTK uses the key and fill lights of the shared lighting rig and a
material's live approximation; axes, the frame, and selection are overlays only.

Materials, environments, and lighting are presets (`ycrystal.presets`: JSON manifests
in `presets/materials/` and `presets/environments/`, and `presets/lighting.json`). A
material manifest names its declaration kind (finish, pigment, texture, or material),
the native POV-Ray identifiers and the include files that declare them, whether it
keeps the element colour, its texture space, and a live approximation. Scene settings
store material ids at three levels (default, element, displayed atom);
`build_geometry` resolves them per atom (`DisplayGeometry.materials`) together with the
colours, so the POV writer and the viewport draw the same choice. The environment is a
plain dataclass that a preset initialises; the writer turns it into a background, a
frame-aligned backdrop (gradient or sky, unlit through an empty `light_group`), a
tilted floor, camera-relative lights, and an optional `no_image` reflection panel.
Gallery thumbnails are genuine POV-Ray renders of fixed scenes
(`ycrystal.render.thumbnails`), shipped with the package; `index.json` records a digest
of each thumbnail scene, and a test fails when a recipe changes without re-rendering
(`scripts/render_thumbnails.py`). Previews and final renders run as `QProcess` jobs;
previews go through a `RenderQueue` (one process, newest request wins) and are tagged with the window's scene
revision so that stale results are discarded.

Projects embed the structure and provenance, plus camera and presentation state.
They do not store the machine's renderer path or last-used directory; those belong
to `QSettings` (as do gallery favourites, the handle visibility, and nothing else).
Schema 5 stores repetitions, cell mode, bond rules, atom size and element radii, the
default material with element and atom overrides, element colours, the full environment
(background, floor, lighting), and the explicit output size; the saved camera is the
output camera for that size (as it already was for schemas 1–4). Schema-1 projects load
with bonds off, schema-1/2 projects with the satin material, and schema-1–3 projects
without floor, backdrop, overrides, or new lighting, to preserve their appearance.

Styles (`ycrystal.io.style`) are the presentation part of a project in the same JSON
layout, plus the source's element sequence. `apply_style` is a pure function from
(style, target structure, current settings) to new settings and user notes; the window
applies the result as one undo command. Element-keyed settings transfer to elements the
target contains; atom-keyed settings (per-atom materials, hidden IDs) transfer only when
the element sequence is identical.

All figure changes go through `SceneSettingsCommand`, which carries scene settings and,
optionally, the environment and the output size, so a style import, a handle drag, or a
size change is one undo step; consecutive commands with the same merge key (spin boxes)
merge. Camera navigation stays outside the undo stack.

Supercell handles and axis-constrained rotation live in the viewport. The input filter
routes left drags that start on a handle, or any left drag while a rotation axis is set,
to the viewport instead of VTK's trackball; clicks are still detected on release. Handles
are 2D overlays recomputed before every render from the camera, the cell, and the (preview)
repetitions; the drag emits preview and final repetitions, and the window builds the
geometry once on release. Axis rotation uses `Camera.rotate_about`, so the scene turns
about a fixed world axis while the structure's coordinates stay unchanged.

## Extension points

- Add future readers in `io/readers.py`, producing `Structure` and provenance.
  Keep questions/errors GUI-free, wire the format into GUI/CLI detection, and add
  equivalence/rejection fixtures. Do not put parsing logic in the viewport.
- Add material or environment presets as JSON manifests in `src/ycrystal/presets/`
  (declaration kind, recipe or native identifier, includes, live approximation,
  provenance), render their thumbnails with `scripts/render_thumbnails.py`, inspect
  them, and commit manifest, PNG, and `index.json` together. `tests/test_presets.py`
  renders every entry individually; native identifiers must exist in POV-Ray 3.7's
  standard include files. Assignment selects presets and never modifies coordinates.
- Extend rendering options in `render/pov_writer.py` and their scene/output models;
  extend job lifecycle in `render/jobs.py` / `render/process.py`. Keep GUI orchestration
  in the interface. The output frame is the shared aspect contract: keep exported,
  previewed, and rendered images defined by the output camera and output size.
- Keep scientific editing separate from the existing display repetitions and bonds.
  Display expansion always starts from the original structure, and is undoable.
  Future scientific editing needs explicit data-layer operations and provenance.
  `core.compare.supercell` currently exists for reader comparisons and discards labels,
  flags, and metadata.
- New presentation settings belong in `SceneSettings` or `Environment` (so that undo,
  projects, and styles pick them up), with a schema bump in `io/project.py`, a transfer
  rule in `io/style.py`, and a line in the undo-coverage test.

Read the [curated reference](../reference/index.md) and
[documentation convention](documentation.md#writing-docstrings) before extending an
interface. The repository's
[contributor guide](https://github.com/ymatterlab/ycrystal/blob/main/CONTRIBUTING.md)
covers application tests and maintenance tooling.
