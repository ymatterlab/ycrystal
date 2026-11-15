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
| `viewport/qt_viewport.py` | The VTK/PyVistaQt adapter. It consumes shared geometry, exchanges `Camera` objects, draws overlays, and reports clicks. VTK objects stay here. |
| `render/pov_writer.py` | Pure text export of shared geometry/camera into POV-Ray 3.7 and INI output. No renderer process or display needed. |
| `render/jobs.py`, `render/povray.py` | Isolated job directories, discovery, synchronous execution, results, and image copying. The caller owns cleanup. |
| `render/process.py` | Asynchronous `QProcess` adapter. Needs a running Qt event loop (`QCoreApplication` is enough), not a window. |
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
size; resizing the window keeps it. POV-Ray export writes explicit camera vectors and
may move the orthographic eye backward to put all geometry in front of it without
changing projection. VTK uses its own lighting and a material's live approximation;
axes, the frame, and selection are overlays only.

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
(`scripts/render_thumbnails.py`). Previews and final renders run as `QProcess` jobs; previews go through a
`RenderQueue` (one process, newest request wins) and are tagged with the window's scene
revision so that stale results are discarded.

Projects embed the structure and provenance, plus camera and presentation state.
They do not store the machine's renderer path or last-used directory; those belong
to `QSettings` (as do gallery favourites). Schema 4 stores repetitions, cell mode, bond
rules, the default material with element and atom overrides, element colours, the full
environment (background, floor, lighting), and the explicit output size; the saved
camera is the output camera for that size (as it already was for schemas 1–3).
Schema-1 projects load with bonds off, schema-1/2 projects with the satin material, and
schema-1–3 projects without floor, backdrop, overrides, or new lighting, to preserve
their appearance.

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
  Future scientific editing needs explicit data-layer operations and provenance. `core.compare.supercell` currently exists for reader comparisons
  and discards labels, flags, and metadata.

Read the [curated reference](../reference/index.md) and
[documentation convention](documentation.md#writing-docstrings) before extending an
interface. The repository's
[contributor guide](https://github.com/ymatterlab/ycrystal/blob/main/CONTRIBUTING.md)
covers application tests and maintenance tooling.
