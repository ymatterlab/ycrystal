"""Embedded interactive VTK viewport (PyVistaQt on PySide6).

All VTK objects stay inside this module. The rest of the application exchanges
renderer-independent [`Camera`][ycrystal.core.camera.Camera] and
[`DisplayGeometry`][ycrystal.core.scene.DisplayGeometry] objects with it.

Mouse mapping (VTK trackball-camera style, orthographic projection):
left drag orbits, middle drag or Shift + left drag pans, wheel or right drag zooms.
A left click without dragging picks the atom under the cursor (Ctrl toggles).

An output frame shows which part of the view the rendered image contains: the largest
rectangle with the output aspect ratio that fits inside the view with a small margin;
the area outside it is dimmed. Two cameras are therefore in play. The *view camera*
(``camera``/``set_camera``) is VTK's camera for the whole view; the *output camera*
(``output_camera``/``set_output_camera``) is the camera of the rendered image, with the
same orientation and centre and a parallel scale reduced to the frame. Resizing the view
keeps the output camera unchanged.

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
from pyvistaqt import QtInteractor  # noqa: E402
from vtkmodules.vtkCommonTransforms import vtkTransform  # noqa: E402
from vtkmodules.vtkFiltersGeneral import vtkTransformFilter  # noqa: E402
from vtkmodules.vtkFiltersSources import vtkCylinderSource, vtkSphereSource  # noqa: E402
from vtkmodules.vtkRenderingCore import (  # noqa: E402
    vtkActor,
    vtkActor2D,
    vtkGlyph3DMapper,
    vtkPolyDataMapper2D,
)

from ycrystal.core.camera import Camera  # noqa: E402
from ycrystal.core.picking import pick_sphere  # noqa: E402
from ycrystal.core.scene import DisplayGeometry, Environment  # noqa: E402

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


class _InputFilter(QObject):
    """Separate clicks from drags and block VTK/PyVista default key bindings.

    Keys such as 'q' (close) or 'w' (wireframe) are swallowed; application shortcuts
    (F, Delete, Esc, Ctrl+Z, …) are handled by the main window. Mouse events always
    continue to VTK, so dragging still navigates.
    """

    def __init__(self, viewport: StructureViewport) -> None:
        super().__init__(viewport)
        self._viewport = viewport
        self._press: QPointF | None = None

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        kind = event.type()
        if kind in (QEvent.Type.KeyPress, QEvent.Type.KeyRelease):
            # Window shortcuts normally consume their keys before this point. If the
            # window is not active (e.g. no window manager), offer the key to the
            # application instead of to VTK.
            if kind == QEvent.Type.KeyPress and isinstance(event, QKeyEvent):
                self._viewport.key_pressed.emit(QKeySequence(event.keyCombination()))
            event.ignore()
            return True
        if isinstance(event, QMouseEvent) and event.button() == Qt.MouseButton.LeftButton:
            if kind == QEvent.Type.MouseButtonPress:
                self._press = event.position()
            elif kind == QEvent.Type.MouseButtonRelease and self._press is not None:
                moved = (event.position() - self._press).manhattanLength()
                self._press = None
                if moved <= CLICK_TOLERANCE_PX:
                    toggle = bool(event.modifiers() & Qt.KeyboardModifier.ControlModifier)
                    self._viewport.handle_click(event.position(), toggle)
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
    """Emitted whenever the VTK camera changes: during mouse navigation and after
    [`set_camera`][ycrystal.viewport.qt_viewport.StructureViewport.set_camera] or
    [`fit`][ycrystal.viewport.qt_viewport.StructureViewport.fit]. One change can emit
    it several times."""

    #: A click without dragging: (index into the displayed atoms or -1, Ctrl held)
    atom_clicked = Signal(int, bool)
    """A click without dragging: (index into the displayed atoms or -1 for empty
    space, whether Ctrl was held)."""

    #: A key pressed in the 3D view that no window shortcut consumed
    key_pressed = Signal(QKeySequence)
    """A key pressed in the 3D view that no window shortcut consumed."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._plotter = QtInteractor(self, auto_update=False, multi_samples=8)
        layout.addWidget(self._plotter)
        self._input_filter = _InputFilter(self)
        self._plotter.installEventFilter(self._input_filter)
        self._plotter.enable_trackball_style()
        self._plotter.enable_parallel_projection()
        self._plotter.add_axes(interactive=False, line_width=2)
        self.atom_actors: dict[str, vtkActor] = {}
        self.bond_actors: dict[str, vtkActor] = {}
        self._highlight_actor: vtkActor | None = None
        self.detail: tuple[int, int, int] = detail_for(0)
        self._geometry: DisplayGeometry | None = None
        # Any camera change (mouse navigation, wheel, Fit, programmatic) notifies listeners.
        self._plotter.renderer.GetActiveCamera().AddObserver(
            "ModifiedEvent", self._on_camera_modified
        )
        self._output_aspect = 1.5
        self._frame_visible = True
        self._last_factor: float | None = None
        self._dim_actor, self._frame_actor = _frame_actors()
        self._plotter.renderer.AddViewProp(self._dim_actor)
        self._plotter.renderer.AddViewProp(self._frame_actor)
        # Before each render: keep the output framing across resizes; redraw the frame.
        self._plotter.renderer.AddObserver("StartEvent", self._before_render)

    # ----- scene ------------------------------------------------------------------
    def set_scene(self, geometry: DisplayGeometry, environment: Environment) -> None:
        """Replace drawn atoms, bonds, and cell edges; keep the camera.

        Parameters
        ----------
        geometry
            Geometry to draw. A reference is kept for picking and fitting; it is not
            copied or modified.
        environment
            Background, floor, and transparency are approximated (see Notes); the live
            view keeps VTK's default lighting.

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
        skies. Shadows, reflections, refraction, clouds, and procedural patterns appear
        only in the POV-Ray preview and render.
        """
        from ycrystal.presets import get_material

        plotter = self._plotter
        for actor in [*self.atom_actors.values(), *self.bond_actors.values()]:
            plotter.remove_actor(actor, render=False)
        self.atom_actors, self.bond_actors = {}, {}
        if self._highlight_actor is not None:
            plotter.remove_actor(self._highlight_actor, render=False)
        self._highlight_actor = None
        plotter.remove_actor("cell_edges", render=False)
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
        self._geometry = geometry
        plotter.render()

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
        cam.ParallelProjectionOn()
        cam.SetWindowCenter(0.0, 0.0)
        cam.SetPosition(*camera.position)
        cam.SetFocalPoint(*camera.focal_point)
        cam.SetViewUp(*camera.view_up)
        cam.SetParallelScale(camera.parallel_scale)
        renderer.camera_set = True
        renderer.ResetCameraClippingRange()
        if render:
            self._plotter.render()
        self.camera_changed.emit()

    def fit(self) -> None:
        """Fit the visible structure into the output frame, keeping the orientation."""
        if self._geometry is None:
            return
        points, radii = self._geometry.points_and_radii()
        self.set_output_camera(self.output_camera().fitted(points, radii, self._output_aspect))

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
        """Show or hide the output frame and the dimming outside it."""
        self._frame_visible = bool(visible)
        self._dim_actor.SetVisibility(self._frame_visible)
        self._frame_actor.SetVisibility(self._frame_visible)
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
        self.camera_changed.emit()

    def _before_render(self, *_args: object) -> None:
        factor = self.frame_factor()
        cam = self._plotter.renderer.GetActiveCamera()
        if self._last_factor is not None and abs(factor - self._last_factor) > 1e-12:
            # The view was resized: keep the output camera's parallel scale.
            cam.SetParallelScale(cam.GetParallelScale() * self._last_factor / factor)
        self._last_factor = factor
        self._update_frame_overlay()

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


def _apply_look(actor: vtkActor, look: object) -> None:
    prop = actor.GetProperty()
    prop.SetAmbient(look.ambient)
    prop.SetDiffuse(look.diffuse)
    prop.SetSpecular(look.specular)
    prop.SetSpecularPower(look.specular_power)
    prop.SetOpacity(look.opacity)


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
