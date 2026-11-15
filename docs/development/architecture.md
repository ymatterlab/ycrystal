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
half-height scale, and pixels. Changing the output aspect changes the visible
horizontal extent. POV-Ray export writes explicit camera vectors and may move the
orthographic eye backward to put all geometry in front of it without changing
projection. VTK uses its own lighting; axes and selection are overlays only.

Projects embed the structure and provenance, plus camera and presentation state.
They do not store the machine's renderer path or last-used directory; those belong
to `QSettings`. The schema-2 project stores repetitions, cell mode, and bond rules. Schema-1 projects
load with bonds off to preserve their appearance. The GUI restores width and transparency and calculates height
from the current viewport, even though the project file stores all render settings.

## Extension points

- Add future readers in `io/readers.py`, producing `Structure` and provenance.
  Keep questions/errors GUI-free, wire the format into GUI/CLI detection, and add
  equivalence/rejection fixtures. Do not put parsing logic in the viewport.
- Put future material presets in renderer-independent presentation models. Resolve
  them once for both backends, then implement each backend's appearance. A material
  gallery should select presets rather than modify scientific coordinates.
- Extend rendering options in `render/pov_writer.py` and their scene/output models;
  extend job lifecycle in `render/jobs.py` / `render/process.py`. Keep GUI orchestration
  in the interface. A future output frame must establish a shared aspect contract.
- Keep scientific editing separate from the existing display repetitions and bonds.
  Display expansion always starts from the original structure, and is undoable.
  Future scientific editing needs explicit data-layer operations and provenance. `core.compare.supercell` currently exists for reader comparisons
  and discards labels, flags, and metadata.

Read the [curated reference](../reference/index.md) and
[documentation convention](documentation.md#writing-docstrings) before extending an
interface. The repository's
[contributor guide](https://github.com/ymatterlab/ycrystal/blob/main/CONTRIBUTING.md)
covers application tests and maintenance tooling.
