"""Embedded interactive VTK viewport (PyVistaQt on PySide6).

All VTK objects stay inside this module. The rest of the application exchanges
renderer-independent [`Camera`][ycrystal.core.camera.Camera] and
[`DisplayGeometry`][ycrystal.core.scene.DisplayGeometry] objects with it.

Mouse mapping (VTK trackball-camera style, orthographic projection):
left drag orbits, middle drag or Shift + left drag pans, wheel or right drag zooms.
A left click without dragging picks the atom under the cursor (Ctrl toggles). With a
rotation axis set
([`set_rotation_axis`][ycrystal.viewport.qt_viewport.StructureViewport.set_rotation_axis]),
left drag turns the view about that axis only. Dragging a supercell handle (the a, b, c
markers at the faces of the repeated block) changes the repetitions in whole cells;
orbiting is disabled during that drag, Esc or the right button cancels it.

An output frame shows which part of the view the rendered image contains: the largest
rectangle with the output aspect ratio that fits inside the view with a small margin;
the area outside it is dimmed. Two cameras are therefore in play. The *view camera*
(``camera``/``set_camera``) is VTK's camera for the whole view; the *output camera*
(``output_camera``/``set_output_camera``) is the camera of the rendered image, with the
same orientation and centre and a parallel scale reduced to the frame. Resizing the view
keeps the output camera unchanged.

Lighting: VTK's default light kit is replaced by two scene lights taken from the shared
[`LightingRig`][ycrystal.core.lighting.LightingRig] (the key and fill lights of the
POV-Ray scene, at their world positions, without distance attenuation). They are
re-resolved from the output camera before every redraw, so they follow orbiting, panning,
and rolling exactly as the exported lights do. Shadows, area-light softness, reflections,
refraction, and the reflection panel appear only in POV-Ray.

Element legend (FR-LEGEND-01): an enabled legend is drawn inside the output frame by the
same painter that draws it onto rendered images
([`legend_overlay`][ycrystal.render.legend.legend_overlay]), at the frame's size in
device pixels, so the view shows where the legend lands in the image. Fitting the view
keeps the structure out of the legend's area.

Importing this module sets the environment variable ``QT_API=pyside6`` for the whole
process and imports PyVista, PyVistaQt, and VTK. Creating a
[`StructureViewport`][ycrystal.viewport.qt_viewport.StructureViewport] needs a
``QApplication`` and an OpenGL-capable display.
"""

from __future__ import annotations

import os

# Select the Qt binding for qtpy/pyvistaqt before they are imported.
os.environ["QT_API"] = "pyside6"

import numpy as np  # noqa: E402
import pyvista as pv  # noqa: E402
import qtpy  # noqa: E402
from PySide6.QtCore import QEvent, QObject, QPointF, Qt, Signal  # noqa: E402
from PySide6.QtGui import QKeyEvent, QKeySequence, QMouseEvent  # noqa: E402
from PySide6.QtWidgets import QVBoxLayout, QWidget  # noqa: E402
from vtkmodules.vtkCommonTransforms import vtkTransform  # noqa: E402
from vtkmodules.vtkFiltersGeneral import vtkTransformFilter  # noqa: E402
from vtkmodules.vtkFiltersSources import vtkCylinderSource, vtkSphereSource  # noqa: E402
from vtkmodules.vtkRenderingCore import (  # noqa: E402
    vtkActor,
    vtkActor2D,
    vtkCoordinate,
    vtkGlyph3DMapper,
    vtkLight,
    vtkPolyDataMapper2D,
    vtkTextActor,
    vtkTexture,
    vtkTexturedActor2D,
)

from ycrystal.core.camera import Camera  # noqa: E402
from ycrystal.core.legend import LegendEntry, LegendSettings, legend_entries  # noqa: E402
from ycrystal.core.lighting import LightingRig, resolve_lighting_for_bounds  # noqa: E402
from ycrystal.core.picking import pick_sphere  # noqa: E402
from ycrystal.core.polyhedra import EDGE_RADIUS  # noqa: E402
from ycrystal.core.scene import DisplayGeometry, Environment  # noqa: E402
from ycrystal.render.legend import legend_fit_region, legend_overlay  # noqa: E402
from ycrystal.viewport.interactor import SynchronousInteractor  # noqa: E402

if qtpy.API_NAME != "PySide6":  # pragma: no cover - environment guard
    raise ImportError(f"qtpy selected {qtpy.API_NAME}; Ycrystal requires PySide6")


FRAME_MARGIN = 0.04
"""Gap between the output frame and the view edges, as a fraction of each dimension."""

FRAME_COLOR = (0.15, 0.45, 0.95)
DIM_COLOR = (0.0, 0.0, 0.0)
DIM_OPACITY = 0.18

CLICK_TOLERANCE_PX = 3.0
"""Largest mouse movement (Manhattan distance, logical pixels) that still counts as a click."""


#: Live-view level of detail: (max displayed atoms, sphere theta, sphere phi, bond sides).
#: Fewer triangles keep large supercells interactive; POV-Ray renders exact spheres.
DETAIL_LEVELS = ((2000, 40, 28, 20), (8000, 24, 16, 12), (None, 16, 10, 8))


def detail_for(n_atoms: int) -> tuple[int, int, int]:
    """Return sphere theta/phi resolution and bond sides for the displayed atom count."""
    for limit, theta, phi, sides in DETAIL_LEVELS:
        if limit is None or n_atoms <= limit:
            return theta, phi, sides
    raise AssertionError("unreachable")


HIGHLIGHT_SCALE = 1.25
"""Radius of the selection shell relative to the atom radius."""

HIGHLIGHT_COLOR = (1.0, 0.72, 0.0)
"""Colour of the selection shell (orange, drawn 45 % opaque)."""

MEASURE_SCALE = 1.1
"""Radius of the measurement cage relative to the atom radius: close around the ball
(the coarse wire's edges stay about 6 % outside the ball's surface)."""

MEASURE_COLOR = (0.0, 0.6, 0.75)
"""Colour of the measurement cages (teal). They also differ from the selection by
shape: sparse wire cages, letter labels, and dashed lines."""

GUIDE_COLOR = (0.0, 0.38, 0.5)
"""Colour of the measurement guide lines (dark teal, drawn in front of the atoms)."""

HANDLE_COLORS = ((0.85, 0.2, 0.2), (0.15, 0.62, 0.25), (0.2, 0.38, 0.92))
"""Colours of the a, b, and c supercell handles."""

HANDLE_RADIUS_PX = 10.0
"""Radius of a supercell handle in device pixels (also its pick radius)."""

HANDLE_OFFSET_PX = 18.0
"""Gap between a handle and the projected outline of the repeated block (including the
largest atom radius), in device pixels. Handles sit on the line through the face centre
along their lattice direction."""

HANDLE_MIN_STEP_PX = 12.0
"""Handles of lattice directions that span fewer device pixels per cell are hidden
(the direction points almost along the line of sight)."""

PREVIEW_COLOR = (1.0, 0.55, 0.0)
"""Colour of the block outline shown while a handle is dragged."""

ROTATION_DEG_PER_PX = 0.4
"""Rotation per device pixel of mouse movement in axis-constrained rotation."""


class _InputFilter(QObject):
    """Separate clicks from drags, route handle and axis drags, block VTK key bindings.

    Keys such as 'q' (close) or 'w' (wireframe) are swallowed; application shortcuts
    (F, Delete, Esc, Ctrl+Z, …) are handled by the main window. Left drags on a supercell
    handle, and left drags while a rotation axis is set, are handled by the viewport and
    kept from VTK; all other mouse events continue to VTK, so dragging still navigates.
    """

    def __init__(self, viewport: StructureViewport) -> None:
        super().__init__(viewport)
        self._viewport = viewport
        self._press: QPointF | None = None
        self._consuming = False

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        kind = event.type()
        viewport = self._viewport
        if kind in (QEvent.Type.KeyPress, QEvent.Type.KeyRelease):
            if (
                kind == QEvent.Type.KeyPress
                and isinstance(event, QKeyEvent)
                and event.key() == Qt.Key.Key_Escape
                and viewport.cancel_interaction()
            ):
                self._consuming = False
                return True
            # Window shortcuts normally consume their keys before this point. If the
            # window is not active (e.g. no window manager), offer the key to the
            # application instead of to VTK.
            if kind == QEvent.Type.KeyPress and isinstance(event, QKeyEvent):
                viewport.key_pressed.emit(QKeySequence(event.keyCombination()))
            event.ignore()
            return True
        if not isinstance(event, QMouseEvent):
            return False
        button = event.button()
        if kind == QEvent.Type.MouseButtonPress and button == Qt.MouseButton.LeftButton:
            self._press = event.position()
            if viewport._begin_interaction(event.position(), event.modifiers()):
                self._consuming = True
                return True
        elif kind == QEvent.Type.MouseButtonPress and self._consuming:
            viewport.cancel_interaction()  # another button cancels a handle or axis drag
            self._consuming = False
            return True
        elif kind == QEvent.Type.MouseMove:
            if self._consuming:
                viewport._update_interaction(event.position())
                return True
            viewport._update_hover(event.position())
        elif kind == QEvent.Type.MouseButtonRelease and button == Qt.MouseButton.LeftButton:
            press, self._press = self._press, None
            moved = (event.position() - press).manhattanLength() if press is not None else 1e9
            toggle = bool(event.modifiers() & Qt.KeyboardModifier.ControlModifier)
            if self._consuming:
                self._consuming = False
                was_handle = viewport._end_interaction(event.position())
                if moved <= CLICK_TOLERANCE_PX and not was_handle:
                    viewport.handle_click(event.position(), toggle)
                return True
            if moved <= CLICK_TOLERANCE_PX:
                viewport.handle_click(event.position(), toggle)
        return False


class StructureViewport(QWidget):
    """Interactive 3D view of a [`DisplayGeometry`][ycrystal.core.scene.DisplayGeometry].

    The only place where VTK objects live. It draws exactly the geometry it is given,
    exchanges views as [`Camera`][ycrystal.core.camera.Camera] objects, and reports
    clicks as indices into that geometry. It never changes the structure or the
    geometry. The orientation axes in the corner and the selection highlight exist only
    in this live view. Sphere and bond tessellation drops above 2,000 and
    8,000 displayed atoms; POV-Ray continues to use exact spheres and cylinders.

    Parameters
    ----------
    parent
        Qt parent widget.
    """

    camera_changed = Signal()
    """Emitted whenever the view changes: during mouse navigation and after
    [`set_camera`][ycrystal.viewport.qt_viewport.StructureViewport.set_camera] or
    [`fit`][ycrystal.viewport.qt_viewport.StructureViewport.fit]. One change can emit
    it several times. Resizing the view does not emit it: the view camera's parallel
    scale is adjusted so that the output camera, and so the rendered image, stays the
    same."""

    #: A click without dragging: (index into the displayed atoms or -1, Ctrl held)
    atom_clicked = Signal(int, bool)
    """A click without dragging: (index into the displayed atoms or -1 for empty
    space, whether Ctrl was held)."""

    #: A key pressed in the 3D view that no window shortcut consumed
    key_pressed = Signal(QKeySequence)
    """A key pressed in the 3D view that no window shortcut consumed."""

    supercell_drag_changed = Signal(tuple)
    """While a supercell handle is dragged: the repetitions ``(na, nb, nc)`` it would
    give (emitted when they change, including at the start)."""

    supercell_drag_finished = Signal(tuple)
    """A handle drag ended on repetitions different from the starting ones."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._plotter = SynchronousInteractor(self, auto_update=False, multi_samples=8)
        layout.addWidget(self._plotter)
        self._input_filter = _InputFilter(self)
        self._plotter.installEventFilter(self._input_filter)
        self._plotter.enable_trackball_style()
        self._plotter.enable_parallel_projection()
        self._plotter.add_axes(interactive=False, line_width=2)
        # Lights: the key and fill lights of the shared rig replace PyVista's light kit.
        renderer = self._plotter.renderer
        renderer.remove_all_lights()
        renderer.AutomaticLightCreationOff()  # no automatic headlight when both are off
        self._lights: dict[str, vtkLight] = {"key": _scene_light(), "fill": _scene_light()}
        for light in self._lights.values():
            renderer.AddLight(light)
        self._environment: Environment | None = None
        self._bounds: tuple[np.ndarray, float] | None = None
        self._rig: LightingRig | None = None
        self.atom_actors: dict[str, vtkActor] = {}
        self.bond_actors: dict[str, vtkActor] = {}
        self.polyhedron_actors: list[vtkActor] = []
        self._highlight_actor: vtkActor | None = None
        self.arrow_mesh: pv.PolyData | None = None
        """Mesh of the vector arrows drawn in the live view (``None`` without arrows)."""
        self.measurement_actors: list[vtkActor | vtkTextActor] = []
        """Live-view-only measurement helpers (cages, labels, guides); never exported."""
        self.detail: tuple[int, int, int] = detail_for(0)
        self._geometry: DisplayGeometry | None = None
        # Any camera change (mouse navigation, wheel, Fit, programmatic) notifies listeners,
        # except the scale adjustment that keeps the output camera when the view is resized.
        self._keeping_output = False
        # True while set_camera applies several VTK settings: one change, reported once.
        self._applying_camera = False
        self._plotter.renderer.GetActiveCamera().AddObserver(
            "ModifiedEvent", self._on_camera_modified
        )
        self._output_aspect = 1.5
        self._frame_visible = True
        self._last_factor: float | None = None
        self._dim_actor, self._frame_actor = _frame_actors()
        self._plotter.renderer.AddViewProp(self._dim_actor)
        self._plotter.renderer.AddViewProp(self._frame_actor)
        # Element legend: a picture of the legend at the frame's pixel size.
        self._legend = LegendSettings()
        self._legend_key: tuple | None = None
        self._entries: tuple[LegendEntry, ...] | None = None  # cache for the geometry
        self.legend_box: tuple[int, int, int, int] | None = None
        """Where the legend is drawn: ``(x, y, width, height)`` in device pixels of the
        view (top-left origin), or ``None`` when no legend is shown."""
        self._legend_actor = vtkTexturedActor2D()
        self._legend_actor.SetMapper(vtkPolyDataMapper2D())
        self._legend_actor.SetPickable(False)
        self._legend_actor.SetVisibility(False)
        self._plotter.renderer.AddViewProp(self._legend_actor)
        # Measurement guide lines are drawn in a second, non-interactive layer with the
        # same camera, so that they stay visible in front of the atoms.
        from vtkmodules.vtkRenderingCore import vtkRenderer

        self._guide_renderer = vtkRenderer()
        self._guide_renderer.SetLayer(1)
        self._guide_renderer.InteractiveOff()
        self._guide_renderer.SetActiveCamera(self._plotter.renderer.GetActiveCamera())
        window = self._plotter.render_window
        window.SetNumberOfLayers(max(2, window.GetNumberOfLayers()))
        window.AddRenderer(self._guide_renderer)
        # Supercell handles (2D markers with a letter) and the drag preview.
        self._supercell: tuple[np.ndarray, tuple[int, int, int], tuple[bool, ...]] | None = None
        self._handles_enabled = True
        self._handle_screen: dict[int, tuple[np.ndarray, np.ndarray]] = {}
        self._handle_actors: list[vtkActor2D] = []
        self._handle_labels: list[vtkTextActor] = []
        for axis, color in enumerate(HANDLE_COLORS):
            actor = _overlay_actor(color)
            label = _text_actor("abc"[axis], (1.0, 1.0, 1.0), 13, centred=True)
            self._plotter.renderer.AddViewProp(actor)
            self._plotter.renderer.AddViewProp(label)
            self._handle_actors.append(actor)
            self._handle_labels.append(label)
        self._preview_actor = vtkActor()
        self._preview_actor.SetMapper(_line_mapper())
        self._preview_actor.GetProperty().SetColor(*PREVIEW_COLOR)
        self._preview_actor.GetProperty().SetLineWidth(3.0)
        self._preview_actor.SetPickable(False)
        self._preview_actor.SetVisibility(False)
        self._plotter.renderer.AddActor(self._preview_actor)
        self._drag_text = _text_actor("", PREVIEW_COLOR, 15, centred=False)
        self._drag_text.SetVisibility(False)
        self._plotter.renderer.AddViewProp(self._drag_text)
        self._drag: dict | None = None
        self._rotation_axis: np.ndarray | None = None
        self._rotating: QPointF | None = None
        # Before each render: keep the output framing across resizes; redraw the frame.
        self._plotter.renderer.AddObserver("StartEvent", self._before_render)

    # ----- scene ------------------------------------------------------------------
    def set_scene(self, geometry: DisplayGeometry, environment: Environment) -> None:
        """Replace drawn atoms, bonds, cell edges, and vector arrows; keep the camera.

        Parameters
        ----------
        geometry
            Geometry to draw. A reference is kept for picking and fitting; it is not
            copied or modified.
        environment
            Background, floor, and transparency are approximated (see Notes); the key
            and fill lights are taken from the shared lighting rig (see
            [`set_lighting`][ycrystal.viewport.qt_viewport.StructureViewport.set_lighting]).

        Raises
        ------
        ycrystal.presets.PresetError
            If a material of the geometry is not a known material preset.

        Notes
        -----
        The selection highlight is removed; call
        [`set_highlight`][ycrystal.viewport.qt_viewport.StructureViewport.set_highlight]
        again if needed. Atoms and half-bonds are grouped by material, one actor per
        material (``atom_actors`` and ``bond_actors``), each with the material's live
        approximation (Phong coefficients and opacity); POV-Ray renders the real
        material. The background is
        [`Environment.live_background`][ycrystal.core.scene.Environment.live_background]:
        the floor colour when there is a floor, a vertical gradient for gradients and
        skies. Shadows, area-light softness, reflections, refraction, the reflection
        panel, clouds, and procedural patterns appear only in the POV-Ray preview and
        render.
        """
        from ycrystal.presets import get_material

        plotter = self._plotter
        for actor in [
            *self.atom_actors.values(),
            *self.bond_actors.values(),
            *self.polyhedron_actors,
        ]:
            plotter.remove_actor(actor, render=False)
        self.atom_actors, self.bond_actors = {}, {}
        self.polyhedron_actors = []
        if self._highlight_actor is not None:
            plotter.remove_actor(self._highlight_actor, render=False)
        self._highlight_actor = None
        plotter.remove_actor("cell_edges", render=False)
        plotter.remove_actor("vector_arrows", render=False)
        self.arrow_mesh = None
        bottom, top = environment.live_background()
        if top is None:
            plotter.set_background(bottom)
        else:
            plotter.set_background(bottom, top=top)

        colors = np.clip(np.round(np.asarray(geometry.colors) * 255), 0, 255).astype(np.uint8)
        theta, phi, sides = detail_for(len(geometry))
        self.detail = (theta, phi, sides)
        materials = np.asarray(geometry.materials, dtype=object)
        translucent = False
        for material_id in dict.fromkeys(geometry.materials):
            look = get_material(material_id).live
            translucent |= look.opacity < 1.0
            rows = np.flatnonzero(materials == material_id)
            actor = _sphere_actor(
                geometry.positions[rows], geometry.radii[rows], colors[rows], (theta, phi)
            )
            _apply_look(actor, look)
            plotter.add_actor(actor, reset_camera=False, render=False)
            self.atom_actors[material_id] = actor
            if len(geometry.bonds):
                # Each half-bond belongs to the atom it starts from.
                first = materials[geometry.bonds[:, 0]] == material_id
                second = materials[geometry.bonds[:, 1]] == material_id
                halves = np.vstack([geometry.bonds[first], geometry.bonds[second][:, ::-1]])
                if len(halves):
                    bonds_actor = _bond_actor(
                        geometry.positions, halves, colors, geometry.bond_radius, sides
                    )
                    _apply_look(bonds_actor, look)
                    bonds_actor.SetPickable(False)
                    plotter.add_actor(bonds_actor, reset_camera=False, render=False)
                    self.bond_actors[material_id] = bonds_actor
        translucent |= self._draw_polyhedra(geometry)
        if translucent:
            plotter.enable_depth_peeling()
        else:
            plotter.disable_depth_peeling()

        if len(geometry.cell_edges):
            edges = np.asarray(geometry.cell_edges, dtype=float)
            n = len(edges)
            lines = np.column_stack([np.full(n, 2), 2 * np.arange(n), 2 * np.arange(n) + 1])
            mesh = pv.PolyData(edges.reshape(-1, 3), lines=lines.ravel())
            tubes = mesh.tube(radius=geometry.cell_edge_radius, n_sides=16, capping=True)
            corners = pv.PolyData(np.unique(edges.reshape(-1, 3).round(9), axis=0)).glyph(
                geom=pv.Sphere(
                    radius=geometry.cell_edge_radius, theta_resolution=16, phi_resolution=12
                ),
                scale=False,
                orient=False,
            )
            plotter.add_mesh(
                tubes.merge(corners),
                color=geometry.cell_edge_color,
                name="cell_edges",
                reset_camera=False,
                render=False,
            )
        if geometry.arrows:
            self.arrow_mesh = arrow_mesh(geometry.arrows, max(sides, 12))
            material = get_material(geometry.arrow_material)
            color = (
                geometry.arrow_color
                if material.keeps_element_color or material.live.color is None
                else material.live.color
            )
            actor = plotter.add_mesh(
                self.arrow_mesh,
                color=color,
                name="vector_arrows",
                reset_camera=False,
                render=False,
            )
            _apply_look(actor, material.live)
            actor.SetPickable(False)
        self._geometry = geometry
        self._entries = None  # the legend follows the new colours and elements
        self._environment = environment
        self._bounds = geometry.bounding_sphere()
        plotter.render()  # the lights are resolved before the redraw

    def _draw_polyhedra(self, geometry: DisplayGeometry) -> bool:
        by_rule = {}
        for shell in geometry.polyhedra:
            faces, edges = by_rule.setdefault(shell.rule, ([], []))
            faces.extend(shell.triangles)
            edges.extend(shell.edges)
        translucent = False
        for rule, (faces, edges) in by_rule.items():
            polygons = np.column_stack((np.full(len(faces), 3), faces))
            mesh = pv.PolyData(geometry.positions, faces=polygons.ravel())
            actor = self._plotter.add_mesh(
                mesh,
                color=rule.color,
                opacity=rule.opacity,
                pickable=False,
                reset_camera=False,
                render=False,
            )
            self.polyhedron_actors.append(actor)
            translucent |= rule.opacity < 1.0
            if edges:
                lines = np.column_stack((np.full(len(edges), 2), edges))
                tubes = pv.PolyData(geometry.positions, lines=lines.ravel()).tube(
                    radius=EDGE_RADIUS, n_sides=8, capping=True
                )
                edge_actor = self._plotter.add_mesh(
                    tubes,
                    color=rule.edge_color,
                    opacity=0.76,
                    pickable=False,
                    reset_camera=False,
                    render=False,
                )
                self.polyhedron_actors.append(edge_actor)
                translucent = True
        return translucent

    def set_lighting(self, environment: Environment) -> None:
        """Use the lights of ``environment`` without rebuilding the scene.

        The key and fill lights become VTK scene lights at the world positions of
        [`resolve_lighting`][ycrystal.core.lighting.resolve_lighting] for the output
        camera and the current geometry: positional, white, with the environment's
        intensities, no distance attenuation (constant attenuation 1), and no spotlight
        cone. A light with non-positive intensity is switched off. The positions are
        resolved again before every redraw, so they follow the camera; they are already
        in world coordinates and get no further camera-relative transformation.

        Parameters
        ----------
        environment
            Environment whose lighting values are shown; background and floor are not
            changed (use `set_scene` for those).
        """
        self._environment = environment
        self._plotter.render()

    def lighting_rig(self) -> LightingRig | None:
        """Return the rig the live lights use now, or ``None`` before a scene is set."""
        self._update_lights()
        return self._rig

    def set_highlight(self, indices: list[int]) -> None:
        """Mark displayed atoms as selected.

        Parameters
        ----------
        indices
            Indices into the current geometry; an empty list removes the highlight.

        Notes
        -----
        Selected atoms get a translucent orange shell. The highlight exists only in the
        live view; it is never exported.
        """
        if self._highlight_actor is not None:
            self._plotter.remove_actor(self._highlight_actor, render=False)
            self._highlight_actor = None
        geometry = self._geometry
        if geometry is not None and indices:
            idx = np.asarray(sorted(set(indices)), dtype=int)
            actor = _sphere_actor(geometry.positions[idx], geometry.radii[idx] * HIGHLIGHT_SCALE)
            prop = actor.GetProperty()
            prop.SetColor(*HIGHLIGHT_COLOR)
            prop.SetOpacity(0.45)
            prop.SetAmbient(0.4)
            actor.SetPickable(False)
            self._plotter.add_actor(actor, reset_camera=False, render=False, name="selection")
            self._highlight_actor = actor
        self._plotter.render()

    def set_measurement(self, points: np.ndarray, radii: np.ndarray, kind: str | None) -> None:
        """Show the helpers of a measurement: picked atoms and a guide.

        Parameters
        ----------
        points
            Positions in Å of the picked atoms in order (A, B, C), shape ``(n, 3)``;
            empty removes the helpers.
        radii
            Drawn radii of those atoms (for the cage size).
        kind
            ``"distance"`` (dashed line A–B) or ``"angle"`` (dashed arms B–A and B–C,
            and a solid arc at the vertex B once all three atoms are picked). The lines
            are drawn in front of the atoms.

        Notes
        -----
        Each picked atom gets a wire cage and a boxed letter label (A, B, C; "B vertex"
        for angles) that stays readable in front of the atoms. The helpers are
        separate, non-pickable VTK actors: they are not part of the geometry, so
        exports, bounds, Fit, the lights, and picking ignore them, and the camera does
        not change.
        """
        renderer, guides = self._plotter.renderer, self._guide_renderer
        for actor in self.measurement_actors:
            renderer.RemoveActor(actor)
            guides.RemoveActor(actor)
        self.measurement_actors = []
        on_top: list[vtkActor] = []
        points = np.asarray(points, dtype=float).reshape(-1, 3)
        if len(points):
            cage = _sphere_actor(points, np.asarray(radii, float) * MEASURE_SCALE, None, (12, 7))
            prop = cage.GetProperty()
            prop.SetRepresentationToWireframe()
            prop.SetColor(*MEASURE_COLOR)
            prop.SetLineWidth(1.0)
            prop.LightingOff()
            self.measurement_actors.append(cage)
            segments = []
            if len(points) >= 2:
                if kind == "angle":
                    segments += _dashed(points[1], points[0])
                    if len(points) == 3:
                        segments += _dashed(points[1], points[2])
                else:
                    segments += _dashed(points[0], points[1])
            if segments:
                on_top.append(_segments_actor(np.asarray(segments), 4.0))
            if kind == "angle" and len(points) == 3:
                arc = _angle_arc(points[0], points[1], points[2])
                if arc is not None:
                    on_top.append(_segments_actor(np.stack([arc[:-1], arc[1:]], axis=1), 3.0))
            for i, point in enumerate(points):
                letter = "B vertex" if kind == "angle" and i == 1 else "ABC"[i]
                self.measurement_actors.append(_anchored_label(letter, point))
            for actor in self.measurement_actors:
                actor.SetPickable(False)
                renderer.AddActor(actor)
            for actor in on_top:
                actor.SetPickable(False)
                guides.AddActor(actor)
            self.measurement_actors += on_top
        self._plotter.render()

    def pick(self, pixel: tuple[float, float]) -> int | None:
        """Return the displayed atom under a pixel of the view.

        Parameters
        ----------
        pixel
            Position ``(x, y)`` in device pixels, origin at the top-left corner of the
            view.

        Returns
        -------
        int or None
            Index into the current geometry, or ``None`` for empty space or when no
            geometry is shown.

        See Also
        --------
        - [`pick_sphere`][ycrystal.core.picking.pick_sphere]: the analytic picking
          used here.
        """
        if self._geometry is None:
            return None
        width, height = self.render_size()
        return pick_sphere(
            self.camera(), width, height, pixel, self._geometry.positions, self._geometry.radii
        )

    def handle_click(self, position: QPointF, toggle: bool) -> None:
        """Pick at a click position and emit `atom_clicked`.

        Parameters
        ----------
        position
            Click position in widget (logical) pixels; converted to device pixels.
        toggle
            Whether Ctrl was held.
        """
        ratio = self._plotter.devicePixelRatioF()
        index = self.pick((position.x() * ratio, position.y() * ratio))
        self.atom_clicked.emit(-1 if index is None else index, toggle)

    # ----- camera -----------------------------------------------------------------
    def camera(self) -> Camera:
        """Return the current view as a new [`Camera`][ycrystal.core.camera.Camera]."""
        cam = self._plotter.renderer.GetActiveCamera()
        return Camera(
            position=cam.GetPosition(),
            focal_point=cam.GetFocalPoint(),
            view_up=cam.GetViewUp(),
            parallel_scale=cam.GetParallelScale(),
        )

    def set_camera(self, camera: Camera, render: bool = True) -> None:
        """Show the view described by a camera.

        Parameters
        ----------
        camera
            View to apply. Parallel projection is enforced and VTK's window centre is
            reset, so the live view matches the camera model exactly.
        render
            Whether to redraw immediately.
        """
        renderer = self._plotter.renderer
        cam = renderer.GetActiveCamera()
        # Each Set call below modifies the VTK camera; in between it can be inconsistent
        # (for example an old up vector parallel to the new direction), so listeners are
        # told once, at the end, instead of after every call.
        self._applying_camera = True
        try:
            cam.ParallelProjectionOn()
            cam.SetWindowCenter(0.0, 0.0)
            cam.SetPosition(*camera.position)
            cam.SetFocalPoint(*camera.focal_point)
            cam.SetViewUp(*camera.view_up)
            cam.SetParallelScale(camera.parallel_scale)
        finally:
            self._applying_camera = False
        renderer.camera_set = True
        renderer.ResetCameraClippingRange()
        if render:
            self._plotter.render()
        self.camera_changed.emit()

    def fit(self) -> None:
        """Fit the visible structure into the output frame, keeping the orientation.

        With an element legend at an edge of the frame, the structure is fitted into the
        space beside the legend (see
        [`fit_region`][ycrystal.viewport.qt_viewport.StructureViewport.fit_region]).
        """
        if self._geometry is None:
            return
        points, radii = self._geometry.points_and_radii()
        self.set_output_camera(
            self.output_camera().fitted(
                points, radii, self._output_aspect, region=self.fit_region()
            )
        )

    # ----- element legend -------------------------------------------------------------
    def set_legend(self, legend: LegendSettings) -> None:
        """Show the element legend of ``legend`` in the output frame (or none, if disabled).

        The entries come from the drawn geometry; the camera is not changed.
        """
        if legend != self._legend:
            self._legend = legend
            self._entries = None
            self._plotter.render()

    def legend_entries(self) -> tuple[LegendEntry, ...]:
        """Return the entries of the legend for the drawn geometry (empty if disabled)."""
        if self._geometry is None or not self._legend.enabled:
            return ()
        if self._entries is None:
            self._entries = legend_entries(self._geometry, self._legend)
        return self._entries

    def fit_region(self) -> tuple[float, float, float, float] | None:
        """Return the part of the output frame left free by the legend, or ``None``.

        See [`legend_fit_region`][ycrystal.render.legend.legend_fit_region].
        """
        entries = self.legend_entries()
        if not entries:
            return None
        return legend_fit_region(entries, self._legend, self._output_aspect)

    # ----- output frame -------------------------------------------------------------
    def set_output_aspect(self, aspect: float) -> None:
        """Set the aspect ratio (width / height) of the output frame.

        The output camera is kept: the rendered image keeps its centre and its visible
        height in Å, and only its width changes with the new aspect ratio.

        Parameters
        ----------
        aspect
            Output width divided by height; must be positive.
        """
        if aspect <= 0:
            raise ValueError("aspect ratio must be positive")
        output = self.output_camera()
        self._output_aspect = float(aspect)
        self._last_factor = self.frame_factor()
        self.set_output_camera(output)

    def output_aspect(self) -> float:
        """Return the aspect ratio (width / height) of the output frame."""
        return self._output_aspect

    def frame_rect(self) -> tuple[float, float, float, float]:
        """Return the output frame in device pixels.

        Returns
        -------
        tuple of float
            ``(x, y, width, height)`` with the top-left origin of the view: the largest
            rectangle with the output aspect ratio inside the view minus
            `FRAME_MARGIN` on every side, centred.
        """
        width, height = self.render_size()
        avail_w, avail_h = width * (1 - 2 * FRAME_MARGIN), height * (1 - 2 * FRAME_MARGIN)
        if avail_w / avail_h > self._output_aspect:
            frame_h = avail_h
            frame_w = frame_h * self._output_aspect
        else:
            frame_w = avail_w
            frame_h = frame_w / self._output_aspect
        return ((width - frame_w) / 2, (height - frame_h) / 2, frame_w, frame_h)

    def frame_factor(self) -> float:
        """Return the frame height divided by the view height (between 0 and 1)."""
        _, height = self.render_size()
        return self.frame_rect()[3] / height

    def output_camera(self) -> Camera:
        """Return the camera of the output image (the view inside the output frame).

        Same position, orientation, and centre as
        [`camera`][ycrystal.viewport.qt_viewport.StructureViewport.camera]; the parallel
        scale is multiplied by
        [`frame_factor`][ycrystal.viewport.qt_viewport.StructureViewport.frame_factor].
        """
        view = self.camera()
        return Camera(
            position=view.position,
            focal_point=view.focal_point,
            view_up=view.view_up,
            parallel_scale=view.parallel_scale * self.frame_factor(),
        )

    def set_output_camera(self, camera: Camera, render: bool = True) -> None:
        """Show the view whose output frame matches ``camera``.

        Parameters
        ----------
        camera
            Camera of the output image, for example a saved project camera.
        render
            Whether to redraw immediately.
        """
        self._last_factor = self.frame_factor()
        view = Camera(
            position=camera.position,
            focal_point=camera.focal_point,
            view_up=camera.view_up,
            parallel_scale=camera.parallel_scale / self._last_factor,
        )
        self.set_camera(view, render=render)

    def set_frame_visible(self, visible: bool) -> None:
        """Show or hide the overlays: output frame, dimming, and supercell handles.

        Hiding them is useful for screenshots that are compared with renders.
        """
        self._frame_visible = bool(visible)
        self._dim_actor.SetVisibility(self._frame_visible)
        self._frame_actor.SetVisibility(self._frame_visible)
        self._plotter.render()

    # ----- supercell handles ----------------------------------------------------------
    def set_supercell(
        self,
        cell: np.ndarray | None,
        repetitions: tuple[int, int, int],
        periodic: tuple[bool, bool, bool] = (True, True, True),
    ) -> None:
        """Place the supercell handles on the repeated block.

        Parameters
        ----------
        cell
            Lattice vectors as rows (Å), or ``None`` for a structure without a cell (no
            handles).
        repetitions
            Current cell counts along a, b, c.
        periodic
            Periodic axes; only they get a handle.
        """
        if cell is None:
            self._supercell = None
        else:
            reps = (int(repetitions[0]), int(repetitions[1]), int(repetitions[2]))
            self._supercell = (
                np.asarray(cell, dtype=float),
                reps,
                tuple(bool(p) for p in periodic),
            )
        self._update_handles()
        self._plotter.render()

    def set_handles_visible(self, visible: bool) -> None:
        """Show or hide the supercell handles (*View ▸ Supercell Handles*)."""
        self._handles_enabled = bool(visible)
        self._update_handles()
        self._plotter.render()

    def handle_positions(self) -> dict[int, tuple[float, float]]:
        """Return the visible handles: axis index (0 = a) → centre in device pixels.

        Coordinates have the top-left origin of the view, like
        [`pick`][ycrystal.viewport.qt_viewport.StructureViewport.pick].
        """
        self._update_handles()
        return {
            axis: (float(centre[0]), float(centre[1]))
            for axis, (centre, _) in self._handle_screen.items()
        }

    def handle_at(self, pixel: tuple[float, float]) -> int | None:
        """Return the axis of the handle under a device pixel, or ``None``."""
        point = np.asarray(pixel, dtype=float)
        best, best_distance = None, HANDLE_RADIUS_PX + 3.0
        for axis, (centre, _) in self._handle_screen.items():
            distance = float(np.linalg.norm(point - centre))
            if distance <= best_distance:
                best, best_distance = axis, distance
        return best

    def set_drag_label(self, text: str) -> None:
        """Show ``text`` next to the dragged handle (for example the atom count)."""
        self._drag_text.SetInput(text)
        self._plotter.render()

    def is_dragging_handle(self) -> bool:
        """Return whether a supercell handle is being dragged."""
        return self._drag is not None

    # ----- axis-constrained rotation -----------------------------------------------------
    def set_rotation_axis(self, axis: np.ndarray | tuple[float, float, float] | None) -> None:
        """Constrain left-drag rotation to a world axis, or ``None`` for free rotation.

        With an axis, left drag turns the view about the axis through the view centre:
        the structure follows the mouse across the axis as it appears on screen, or turns
        with a circular mouse motion when the axis points at the viewer. Shift + left
        drag still pans; the other buttons are unchanged.
        """
        if axis is None:
            self._rotation_axis = None
            return
        vector = np.asarray(axis, dtype=float)
        norm = float(np.linalg.norm(vector))
        if not norm > 0:
            raise ValueError("rotation axis must have non-zero length")
        self._rotation_axis = vector / norm

    def rotation_axis(self) -> np.ndarray | None:
        """Return the unit rotation axis, or ``None`` for free rotation."""
        return None if self._rotation_axis is None else self._rotation_axis.copy()

    def rotate_view(self, angle: float, axis: np.ndarray | None = None) -> None:
        """Turn the view so that the scene rotates by ``angle`` degrees about an axis.

        Parameters
        ----------
        angle
            Right-handed rotation in degrees.
        axis
            World axis; defaults to the rotation axis, or to the line of sight
            (pointing at the viewer, so positive angles turn the image
            counter-clockwise) in free rotation.
        """
        camera = self.camera()
        if axis is None:
            axis = self._rotation_axis
        if axis is None:
            axis = -camera.basis()[2]
        self.set_camera(camera.rotate_about(axis, angle))

    def _axis_angle(self, start: np.ndarray, end: np.ndarray) -> float:
        """Rotation in degrees for a mouse move from ``start`` to ``end`` (device px)."""
        axis = self._rotation_axis
        right, up, direction = self.camera().basis()
        screen = np.array([axis @ right, axis @ up])  # y up
        length = float(np.linalg.norm(screen))
        if length > 0.3:
            normal = np.array([screen[1], -screen[0]]) / length
            delta = np.array([end[0] - start[0], -(end[1] - start[1])])
            return ROTATION_DEG_PER_PX * float(delta @ normal)
        width, height = self.render_size()
        centre = np.array([width / 2.0, height / 2.0])
        a0 = np.arctan2(-(start[1] - centre[1]), start[0] - centre[0])
        a1 = np.arctan2(-(end[1] - centre[1]), end[0] - centre[0])
        swept = (a1 - a0 + np.pi) % (2 * np.pi) - np.pi
        return float(np.degrees(swept)) * (1.0 if axis @ -direction >= 0 else -1.0)

    # ----- interaction (called by the input filter) ---------------------------------------
    def _device(self, position: QPointF) -> np.ndarray:
        ratio = self._plotter.devicePixelRatioF()
        return np.array([position.x() * ratio, position.y() * ratio])

    def _begin_interaction(self, position: QPointF, modifiers: Qt.KeyboardModifier) -> bool:
        pixel = self._device(position)
        shift = bool(modifiers & Qt.KeyboardModifier.ShiftModifier)
        axis = None if shift else self.handle_at(tuple(pixel))
        if axis is not None and self._supercell is not None:
            _, reps, _ = self._supercell
            self._drag = {"axis": axis, "start": pixel, "reps0": reps, "reps": reps}
            self._preview_actor.SetVisibility(True)
            self._drag_text.SetVisibility(True)
            self._update_preview()
            self.supercell_drag_changed.emit(reps)
            return True
        if self._rotation_axis is not None and not shift:
            self._rotating = position
            return True
        return False

    def _update_interaction(self, position: QPointF) -> None:
        if self._drag is not None:
            drag = self._drag
            axis = drag["axis"]
            _, step = self._handle_steps(drag["reps0"]).get(axis, (None, None))
            if step is None:
                return
            delta = self._device(position) - drag["start"]
            cells = int(round(float(delta @ step) / float(step @ step)))
            reps = list(drag["reps0"])
            reps[axis] = max(1, min(MAX_HANDLE_REPETITIONS, reps[axis] + cells))
            reps = tuple(reps)
            if reps != drag["reps"]:
                drag["reps"] = reps
                self._update_preview()
                self.supercell_drag_changed.emit(reps)
            return
        if self._rotating is not None:
            angle = self._axis_angle(self._device(self._rotating), self._device(position))
            self._rotating = position
            if angle:
                self.set_camera(self.camera().rotate_about(self._rotation_axis, angle))

    def _end_interaction(self, position: QPointF) -> bool:
        """Finish a handle or axis drag; return whether it was a handle drag."""
        if self._drag is not None:
            self._update_interaction(position)
            drag, self._drag = self._drag, None
            self._preview_actor.SetVisibility(False)
            self._drag_text.SetVisibility(False)
            self._update_handles()
            self._plotter.render()
            if drag["reps"] != drag["reps0"]:
                self.supercell_drag_finished.emit(drag["reps"])
            return True
        self._rotating = None
        return False

    def cancel_interaction(self) -> bool:
        """Cancel a handle or axis drag in progress; return whether one was cancelled.

        A cancelled handle drag leaves the repetitions unchanged.
        """
        if self._drag is not None:
            self._drag = None
            self._preview_actor.SetVisibility(False)
            self._drag_text.SetVisibility(False)
            self._update_handles()
            self._plotter.render()
            return True
        if self._rotating is not None:
            self._rotating = None
            return True
        return False

    def _update_hover(self, position: QPointF) -> None:
        over = self.handle_at(tuple(self._device(position))) is not None
        if over:
            self._plotter.setCursor(Qt.CursorShape.OpenHandCursor)
        else:
            self._plotter.unsetCursor()

    def _handle_steps(self, reps: tuple[int, int, int]) -> dict[int, tuple[np.ndarray, np.ndarray]]:
        """Per periodic axis: projected face centre and pixels per cell (device px)."""
        if self._supercell is None:
            return {}
        cell, _, periodic = self._supercell
        width, height = self.render_size()
        camera = self.camera()
        result = {}
        for axis in range(3):
            if not periodic[axis]:
                continue
            frac = np.array(reps, dtype=float) / 2.0
            frac[axis] = reps[axis]
            face = frac @ cell
            ends = camera.project(np.array([face, face + cell[axis]]), width, height)
            step = ends[1] - ends[0]
            if float(np.linalg.norm(step)) >= HANDLE_MIN_STEP_PX:
                result[axis] = (ends[0], step)
        return result

    def _block_extent(
        self, reps: tuple[int, int, int], face: np.ndarray, direction: np.ndarray
    ) -> float:
        """Pixels from a projected face centre to the far edge of the block along ``direction``.

        Includes the largest atom radius, so that a handle placed beyond it does not
        cover atoms.
        """
        cell = self._supercell[0]
        width, height = self.render_size()
        camera = self.camera()
        corners = np.array(
            [[i, j, k] for i in (0, 1) for j in (0, 1) for k in (0, 1)], dtype=float
        ) * np.array(reps, dtype=float)
        pixels = camera.project(corners @ cell, width, height)
        extent = float(np.max((pixels - face) @ direction))
        if self._geometry is not None and len(self._geometry.radii):
            extent += float(np.max(self._geometry.radii)) * camera.pixels_per_angstrom(height)
        return max(extent, 0.0)

    def _update_handles(self) -> None:
        reps = self._drag["reps"] if self._drag is not None else None
        if self._supercell is not None and reps is None:
            reps = self._supercell[1]
        show = self._handles_enabled and self._frame_visible and self._supercell is not None
        steps = self._handle_steps(reps) if show else {}
        self._handle_screen = {}
        width, height = self.render_size()
        for axis in range(3):
            actor, label = self._handle_actors[axis], self._handle_labels[axis]
            if axis not in steps:
                actor.SetVisibility(False)
                label.SetVisibility(False)
                continue
            face, step = steps[axis]
            direction = step / np.linalg.norm(step)
            outside = self._block_extent(reps, face, direction)
            centre = face + direction * (outside + HANDLE_OFFSET_PX)
            edge = HANDLE_RADIUS_PX + 12.0  # keep the handle (and its arrow) in the view
            centre = np.clip(centre, [edge, edge], [width - edge, height - edge])
            self._handle_screen[axis] = (centre, step)
            _set_handle_shape(actor, centre, direction, height)
            label.SetDisplayPosition(int(round(centre[0])), int(round(height - centre[1])))
            actor.SetVisibility(True)
            label.SetVisibility(True)
        if self._drag is not None and self._drag["axis"] in self._handle_screen:
            centre, _ = self._handle_screen[self._drag["axis"]]
            self._drag_text.SetDisplayPosition(
                int(round(min(centre[0] + 16, width - 220))),
                int(round(min(height - centre[1] + 14, height - 24))),
            )

    def _update_preview(self) -> None:
        if self._drag is None or self._supercell is None:
            return
        cell = self._supercell[0]
        reps = np.array(self._drag["reps"], dtype=float)
        corners = np.array([[i, j, k] for i in (0, 1) for j in (0, 1) for k in (0, 1)], dtype=float)
        points = (corners * reps) @ cell
        edges = [
            (a, b)
            for a in range(8)
            for b in range(a + 1, 8)
            if np.sum(np.abs(corners[a] - corners[b])) == 1
        ]
        lines = np.array([[2, a, b] for a, b in edges]).ravel()
        self._preview_actor.GetMapper().SetInputData(pv.PolyData(points, lines=lines))
        self._update_handles()
        self._plotter.render()

    def frame_to_output(self, pixels: np.ndarray, width: int, height: int) -> np.ndarray:
        """Map view pixels inside the frame to pixels of a ``width`` × ``height`` image.

        Used to compare the live view with a rendered image.

        Parameters
        ----------
        pixels
            View pixel coordinates ``(x, y)``, shape ``(K, 2)``, top-left origin.
        width, height
            Output image size in pixels.

        Returns
        -------
        numpy.ndarray
            Output image coordinates, shape ``(K, 2)``.
        """
        x0, y0, frame_w, frame_h = self.frame_rect()
        pts = np.asarray(pixels, dtype=float).reshape(-1, 2)
        return np.column_stack(
            [(pts[:, 0] - x0) * width / frame_w, (pts[:, 1] - y0) * height / frame_h]
        )

    def render_size(self) -> tuple[int, int]:
        """Return the size of the drawing area in device pixels.

        Returns
        -------
        tuple of int
            ``(width, height)``, each at least 1. This size defines the aspect ratio
            used for fitting, picking, and the rendered image.
        """
        width, height = self._plotter.render_window.GetSize()
        return max(int(width), 1), max(int(height), 1)

    # ----- evidence / testing helpers ---------------------------------------------------
    def render(self) -> None:
        """Redraw the view."""
        self._plotter.render()

    def set_axes_visible(self, visible: bool) -> None:
        """Show or hide the orientation axes in the corner of the view."""
        if visible:
            self._plotter.show_axes()
        else:
            self._plotter.hide_axes()
        self._plotter.render()

    def screenshot(self, transparent: bool = False) -> np.ndarray:
        """Return the current view as an image.

        Parameters
        ----------
        transparent
            Whether the background becomes transparent (alpha 0).

        Returns
        -------
        numpy.ndarray
            RGBA ``uint8`` array of shape ``(height, width, 4)``; row 0 is the top.
        """
        image = self._plotter.screenshot(transparent_background=transparent, return_img=True)
        if image.shape[2] == 3:
            alpha = np.full(image.shape[:2] + (1,), 255, dtype=image.dtype)
            image = np.concatenate([image, alpha], axis=2)
        return image

    def vtk_project(self, points: np.ndarray) -> np.ndarray:
        """Project world points with VTK's own transformation.

        Used to check that the live view agrees with
        [`Camera.project`][ycrystal.core.camera.Camera.project].

        Parameters
        ----------
        points
            Points in Å, shape ``(K, 3)``.

        Returns
        -------
        numpy.ndarray
            Pixel coordinates ``(x, y)``, shape ``(K, 2)``, top-left origin.
        """
        renderer = self._plotter.renderer
        _, height = self.render_size()
        out = []
        for point in np.asarray(points, dtype=float).reshape(-1, 3):
            renderer.SetWorldPoint(point[0], point[1], point[2], 1.0)
            renderer.WorldToDisplay()
            x, y, _ = renderer.GetDisplayPoint()
            out.append((x, height - y))
        return np.asarray(out)

    @property
    def interactor_widget(self) -> QWidget:
        """The Qt widget that receives mouse events (for tests)."""
        return self._plotter

    def close_viewport(self) -> None:
        """Release the VTK render window; call before the widget is discarded."""
        self._plotter.close()

    # ----- internals --------------------------------------------------------------
    def _on_camera_modified(self, *_args: object) -> None:
        if not (self._keeping_output or self._applying_camera):
            self.camera_changed.emit()

    def _before_render(self, *_args: object) -> None:
        factor = self.frame_factor()
        cam = self._plotter.renderer.GetActiveCamera()
        if self._last_factor is not None and abs(factor - self._last_factor) > 1e-12:
            # The view was resized: keep the output camera's parallel scale. The output
            # camera is unchanged, so this is not reported as a change of the view.
            self._keeping_output = True
            try:
                cam.SetParallelScale(cam.GetParallelScale() * self._last_factor / factor)
            finally:
                self._keeping_output = False
        self._last_factor = factor
        self._update_lights()
        self._update_frame_overlay()
        self._update_legend_overlay()
        self._update_handles()

    def _update_lights(self) -> None:
        if self._environment is None or self._bounds is None:
            self._rig = None
            for light in self._lights.values():
                light.SwitchOff()
            return
        rig = resolve_lighting_for_bounds(self._environment, self.output_camera(), *self._bounds)
        self._rig = rig
        for resolved in (rig.key, rig.fill):
            light = self._lights[resolved.role]
            light.SetPosition(*resolved.position)
            light.SetFocalPoint(*rig.origin)
            light.SetIntensity(max(resolved.intensity, 0.0))
            light.SetSwitch(int(resolved.enabled))

    def _update_frame_overlay(self) -> None:
        width, height = self.render_size()
        x0, y0, frame_w, frame_h = self.frame_rect()
        # VTK display coordinates have their origin at the bottom-left.
        left, right = x0, x0 + frame_w
        bottom, top = height - (y0 + frame_h), height - y0
        _set_rectangles(
            self._dim_actor,
            [
                (0, 0, width, bottom),
                (0, top, width, height),
                (0, bottom, left, top),
                (right, bottom, width, top),
            ],
        )
        _set_outline(self._frame_actor, (left, bottom, right, top))

    def _update_legend_overlay(self) -> None:
        """Redraw the legend picture when the legend, the geometry, or the frame changed."""
        x0, y0, frame_w, frame_h = self.frame_rect()
        _, height = self.render_size()
        entries = self.legend_entries()
        key = (entries, self._legend, round(x0), round(y0), round(frame_w), round(frame_h))
        if key == self._legend_key:
            return
        self._legend_key = key
        overlay = legend_overlay(entries, self._legend, round(frame_w), round(frame_h))
        if overlay is None:
            self._legend_actor.SetVisibility(False)
            self.legend_box = None
            return
        image, x, y = overlay
        w, h = image.width(), image.height()
        left, top = round(x0) + x, round(y0) + y
        self.legend_box = (left, top, w, h)
        rows = np.frombuffer(image.constBits(), dtype=np.uint8).reshape(h, image.bytesPerLine())
        pixels = rows[:, : 4 * w].reshape(h, w, 4)[::-1]  # VTK images start at the bottom
        texture = vtkTexture()
        texture.SetInputData(pv.ImageData(dimensions=(w, h, 1)))
        texture.GetInput().GetPointData().SetScalars(
            pv.convert_array(np.ascontiguousarray(pixels).reshape(-1, 4))
        )
        texture.InterpolateOff()
        bottom = height - (top + h)
        quad = pv.PolyData(
            np.array(
                [
                    (left, bottom, 0),
                    (left + w, bottom, 0),
                    (left + w, bottom + h, 0),
                    (left, bottom + h, 0),
                ],
                dtype=float,
            ),
            faces=[4, 0, 1, 2, 3],
        )
        quad.active_texture_coordinates = np.array([(0, 0), (1, 0), (1, 1), (0, 1)], dtype=float)
        self._legend_actor.GetMapper().SetInputData(quad)
        self._legend_actor.SetTexture(texture)
        self._legend_actor.SetVisibility(True)


def _sphere_actor(
    positions: np.ndarray,
    radii: np.ndarray,
    colors: np.ndarray | None = None,
    resolution: tuple[int, int] = (40, 28),
) -> vtkActor:
    """Instanced spheres (one mesh, many atoms) via vtkGlyph3DMapper."""
    points = pv.PolyData(np.asarray(positions, dtype=float).reshape(-1, 3))
    points.point_data["radius"] = np.asarray(radii, dtype=float)
    sphere = vtkSphereSource()
    sphere.SetRadius(1.0)
    sphere.SetThetaResolution(resolution[0])
    sphere.SetPhiResolution(resolution[1])
    mapper = vtkGlyph3DMapper()
    mapper.SetInputData(points)
    mapper.SetSourceConnection(sphere.GetOutputPort())
    mapper.SetScaleArray("radius")
    mapper.SetScaleModeToScaleByMagnitude()
    mapper.SetScaleFactor(1.0)
    if colors is not None:
        points.point_data["colors"] = colors
        mapper.SetScalarModeToUsePointFieldData()
        mapper.SelectColorArray("colors")
        mapper.SetColorModeToDirectScalars()
        mapper.ScalarVisibilityOn()
    else:
        mapper.ScalarVisibilityOff()
    actor = vtkActor()
    actor.SetMapper(mapper)
    return actor


def _bond_actor(
    positions: np.ndarray, bonds: np.ndarray, colors: np.ndarray, radius: float, sides: int = 20
) -> vtkActor:
    """Instanced half-bond cylinders from ``bonds[:, 0]`` to the bond midpoint.

    Each cylinder is coloured like the atom it starts from; pass a bond in both
    orientations to draw both halves.
    """
    positions = np.asarray(positions, dtype=float)
    starts = positions[bonds[:, 0]]
    ends = 0.5 * (starts + positions[bonds[:, 1]])
    vectors = ends - starts
    lengths = np.linalg.norm(vectors, axis=1)
    points = pv.PolyData(0.5 * (starts + ends))
    points.point_data["direction"] = vectors
    points.point_data["scale"] = np.column_stack(
        [lengths, np.full(len(lengths), radius), np.full(len(lengths), radius)]
    )
    points.point_data["colors"] = colors[bonds[:, 0]]
    cylinder = vtkCylinderSource()  # unit height and radius along the y axis
    cylinder.SetHeight(1.0)
    cylinder.SetRadius(1.0)
    cylinder.SetResolution(sides)
    to_x_axis = vtkTransform()
    to_x_axis.RotateZ(-90.0)  # glyph orientation aligns the x axis with each bond
    aligned = vtkTransformFilter()
    aligned.SetInputConnection(cylinder.GetOutputPort())
    aligned.SetTransform(to_x_axis)
    mapper = vtkGlyph3DMapper()
    mapper.SetInputData(points)
    mapper.SetSourceConnection(aligned.GetOutputPort())
    mapper.SetOrientationArray("direction")
    mapper.SetOrientationModeToDirection()
    mapper.SetScaleArray("scale")
    mapper.SetScaleModeToScaleByVectorComponents()
    mapper.SetScalarModeToUsePointFieldData()
    mapper.SelectColorArray("colors")
    mapper.SetColorModeToDirectScalars()
    mapper.ScalarVisibilityOn()
    actor = vtkActor()
    actor.SetMapper(mapper)
    return actor


def arrow_mesh(arrows: tuple, resolution: int = 16) -> pv.PolyData:
    """Return one mesh of shaft cylinders and head cones for resolved arrows.

    The arrows come from [`DisplayGeometry.arrows`][ycrystal.core.scene.DisplayGeometry],
    the same geometry the POV-Ray writer uses (cylinder from tail to head base, cone from
    head base to tip).
    """
    parts = []
    for arrow in arrows:
        tail, base, tip = (np.asarray(p, dtype=float) for p in (arrow.tail, arrow.base, arrow.tip))
        shaft, head = base - tail, tip - base
        if np.linalg.norm(shaft) > 0:
            parts.append(
                pv.Cylinder(
                    center=0.5 * (tail + base),
                    direction=shaft,
                    radius=arrow.shaft_radius,
                    height=float(np.linalg.norm(shaft)),
                    resolution=resolution,
                    capping=True,
                )
            )
        parts.append(
            pv.Cone(
                center=0.5 * (base + tip),
                direction=head,
                height=float(np.linalg.norm(head)),
                radius=arrow.head_radius,
                resolution=resolution,
                capping=True,
            )
        )
    return pv.merge(parts) if len(parts) > 1 else parts[0]


def _apply_look(actor: vtkActor, look: object) -> None:
    prop = actor.GetProperty()
    prop.SetAmbient(look.ambient)
    prop.SetDiffuse(look.diffuse)
    prop.SetSpecular(look.specular)
    prop.SetSpecularPower(look.specular_power)
    prop.SetOpacity(look.opacity)


MAX_HANDLE_REPETITIONS = 20
"""Largest cell count a handle drag can reach (the numeric controls use the same)."""


def _scene_light() -> vtkLight:
    """Return a white positional scene light without attenuation or spotlight cone."""
    light = vtkLight()
    light.SetLightTypeToSceneLight()
    light.PositionalOn()
    light.SetConeAngle(180.0)  # 90° or more: no spotlight
    light.SetAttenuationValues(1.0, 0.0, 0.0)  # constant: no fall-off with distance
    light.SetColor(1.0, 1.0, 1.0)
    light.SwitchOff()
    return light


def _line_mapper() -> object:
    from vtkmodules.vtkRenderingCore import vtkPolyDataMapper

    mapper = vtkPolyDataMapper()
    mapper.SetInputData(pv.PolyData())
    return mapper


def _dashed(start: np.ndarray, end: np.ndarray) -> list[tuple[np.ndarray, np.ndarray]]:
    """Dash segments from ``start`` to ``end`` (dash and gap of about 0.2 Å each)."""
    start, end = np.asarray(start, float), np.asarray(end, float)
    length = float(np.linalg.norm(end - start))
    if length < 1e-9:
        return []
    count = max(3, min(20, round(length / 0.4)))
    t = np.linspace(0.0, 1.0, 2 * count)
    ends = start + np.outer(t, end - start)
    return [(ends[i], ends[i + 1]) for i in range(0, 2 * count - 1, 2)]


def _angle_arc(a: np.ndarray, b: np.ndarray, c: np.ndarray, steps: int = 32) -> np.ndarray | None:
    """Points of an arc at the vertex ``b`` from the arm to ``a`` to the arm to ``c``."""
    u, v = np.asarray(a, float) - b, np.asarray(c, float) - b
    lu, lv = np.linalg.norm(u), np.linalg.norm(v)
    if lu < 1e-9 or lv < 1e-9:
        return None
    u, v = u / lu, v / lv
    angle = float(np.arctan2(np.linalg.norm(np.cross(u, v)), u @ v))
    if angle < 1e-6:
        return None
    w = v - (u @ v) * u  # in-plane direction perpendicular to u
    if np.linalg.norm(w) < 1e-9:  # 180°: any perpendicular direction
        w = np.cross(u, [1.0, 0.0, 0.0] if abs(u[0]) < 0.9 else [0.0, 1.0, 0.0])
    w /= np.linalg.norm(w)
    radius = 0.45 * min(lu, lv)
    t = np.linspace(0.0, angle, steps)
    return b + radius * (np.outer(np.cos(t), u) + np.outer(np.sin(t), w))


def _segments_actor(segments: np.ndarray, width: float) -> vtkActor:
    """Line segments ``(n, 2, 3)`` as one actor in the guide colour."""
    from vtkmodules.vtkRenderingCore import vtkPolyDataMapper

    points = np.asarray(segments, float).reshape(-1, 3)
    pairs = np.arange(len(points)).reshape(-1, 2)
    lines = np.column_stack([np.full(len(pairs), 2), pairs])
    mapper = vtkPolyDataMapper()
    mapper.SetInputData(pv.PolyData(points, lines=lines.ravel()))
    actor = vtkActor()
    actor.SetMapper(mapper)
    prop = actor.GetProperty()
    prop.SetColor(*GUIDE_COLOR)
    prop.SetLineWidth(width)
    prop.LightingOff()
    return actor


def _anchored_label(text: str, point: np.ndarray) -> vtkTextActor:
    """Return a boxed label drawn on top of the scene, offset from a world point by pixels."""
    actor = vtkTextActor()
    actor.SetInput(text)
    prop = actor.GetTextProperty()
    prop.SetFontSize(16)
    prop.BoldOn()
    prop.SetColor(0.05, 0.05, 0.08)
    prop.SetBackgroundColor(1.0, 1.0, 1.0)
    prop.SetBackgroundOpacity(0.85)
    prop.SetFrame(True)
    prop.SetFrameColor(*MEASURE_COLOR)
    prop.SetFrameWidth(2)
    reference = vtkCoordinate()
    reference.SetCoordinateSystemToWorld()
    reference.SetValue(*np.asarray(point, dtype=float))
    position = actor.GetPositionCoordinate()
    position.SetCoordinateSystemToDisplay()
    position.SetReferenceCoordinate(reference)
    position.SetValue(6, 6)
    actor._reference = reference  # keep the coordinate alive with the actor
    return actor


def _overlay_actor(color: tuple[float, float, float]) -> vtkActor2D:
    actor = vtkActor2D()
    mapper = vtkPolyDataMapper2D()
    mapper.SetInputData(pv.PolyData())
    actor.SetMapper(mapper)
    actor.GetProperty().SetColor(*color)
    actor.SetPickable(False)
    actor.SetVisibility(False)
    return actor


def _text_actor(
    text: str, color: tuple[float, float, float], size: int, centred: bool
) -> vtkTextActor:
    actor = vtkTextActor()
    actor.SetInput(text)
    prop = actor.GetTextProperty()
    prop.SetColor(*color)
    prop.SetFontSize(size)
    prop.BoldOn()
    if centred:
        prop.SetJustificationToCentered()
        prop.SetVerticalJustificationToCentered()
    else:
        prop.SetBackgroundColor(1.0, 1.0, 1.0)
        prop.SetBackgroundOpacity(0.85)
    actor.SetPickable(False)
    actor.SetVisibility(False)
    return actor


def _set_handle_shape(
    actor: vtkActor2D, centre: np.ndarray, direction: np.ndarray, height: int
) -> None:
    """Draw a filled disc with an arrowhead pointing along ``direction`` (top-left px)."""
    n = 20
    angles = np.linspace(0.0, 2.0 * np.pi, n, endpoint=False)
    disc = centre + HANDLE_RADIUS_PX * np.column_stack([np.cos(angles), np.sin(angles)])
    normal = np.array([-direction[1], direction[0]])
    tip = centre + direction * (HANDLE_RADIUS_PX + 9.0)
    base = centre + direction * (HANDLE_RADIUS_PX - 1.0)
    arrow = np.array([base + normal * 6.0, tip, base - normal * 6.0])
    points2d = np.vstack([disc, arrow])
    points = np.column_stack([points2d[:, 0], height - points2d[:, 1], np.zeros(len(points2d))])
    faces = [n, *range(n), 3, n, n + 1, n + 2]
    actor.GetMapper().SetInputData(pv.PolyData(points, faces=faces))


def _frame_actors() -> tuple[vtkActor2D, vtkActor2D]:
    dim, frame = vtkActor2D(), vtkActor2D()
    for actor, color in ((dim, DIM_COLOR), (frame, FRAME_COLOR)):
        mapper = vtkPolyDataMapper2D()
        mapper.SetInputData(pv.PolyData())
        actor.SetMapper(mapper)
        actor.GetProperty().SetColor(*color)
        actor.SetPickable(False)
    dim.GetProperty().SetOpacity(DIM_OPACITY)
    frame.GetProperty().SetLineWidth(1.5)
    return dim, frame


def _set_rectangles(actor: vtkActor2D, rectangles: list[tuple[float, ...]]) -> None:
    points, faces = [], []
    for x0, y0, x1, y1 in rectangles:
        if x1 - x0 <= 0 or y1 - y0 <= 0:
            continue
        start = len(points)
        points += [(x0, y0, 0), (x1, y0, 0), (x1, y1, 0), (x0, y1, 0)]
        faces += [4, start, start + 1, start + 2, start + 3]
    mesh = (
        pv.PolyData(np.array(points, float).reshape(-1, 3), faces=faces)
        if points
        else pv.PolyData()
    )
    actor.GetMapper().SetInputData(mesh)


def _set_outline(actor: vtkActor2D, box: tuple[float, float, float, float]) -> None:
    x0, y0, x1, y1 = box
    points = np.array([(x0, y0, 0), (x1, y0, 0), (x1, y1, 0), (x0, y1, 0)], float)
    actor.GetMapper().SetInputData(pv.PolyData(points, lines=[5, 0, 1, 2, 3, 0]))
