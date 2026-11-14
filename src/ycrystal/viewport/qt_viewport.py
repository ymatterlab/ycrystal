"""Embedded interactive VTK viewport (PyVistaQt on PySide6).

All VTK objects stay inside this module. The rest of the application exchanges
renderer-independent :class:`Camera` and :class:`DisplayGeometry` objects with it.

Mouse mapping (VTK trackball-camera style, orthographic projection):
left drag orbits, middle drag or Shift + left drag pans, wheel or right drag zooms.
A left click without dragging picks the atom under the cursor (Ctrl toggles).
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
from vtkmodules.vtkFiltersSources import vtkSphereSource  # noqa: E402
from vtkmodules.vtkRenderingCore import vtkActor, vtkGlyph3DMapper  # noqa: E402

from ycrystal.core.camera import Camera  # noqa: E402
from ycrystal.core.picking import pick_sphere  # noqa: E402
from ycrystal.core.scene import DisplayGeometry, Environment  # noqa: E402

if qtpy.API_NAME != "PySide6":  # pragma: no cover - environment guard
    raise ImportError(f"qtpy selected {qtpy.API_NAME}; Ycrystal requires PySide6")


CLICK_TOLERANCE_PX = 3.0
HIGHLIGHT_SCALE = 1.25
HIGHLIGHT_COLOR = (1.0, 0.72, 0.0)


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
    """Interactive 3D view of a :class:`DisplayGeometry`."""

    camera_changed = Signal()
    #: A click without dragging: (index into the displayed atoms or -1, Ctrl held)
    atom_clicked = Signal(int, bool)
    #: A key pressed in the 3D view that no window shortcut consumed
    key_pressed = Signal(QKeySequence)

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
        self._atoms_actor: vtkActor | None = None
        self._highlight_actor: vtkActor | None = None
        self._geometry: DisplayGeometry | None = None
        self._plotter.iren.add_observer("EndInteractionEvent", self._on_interaction_end)

    # ----- scene ------------------------------------------------------------------
    def set_scene(self, geometry: DisplayGeometry, environment: Environment) -> None:
        plotter = self._plotter
        for actor in (self._atoms_actor, self._highlight_actor):
            if actor is not None:
                plotter.remove_actor(actor, render=False)
        self._highlight_actor = None
        plotter.remove_actor("cell_edges", render=False)
        plotter.set_background(environment.background)

        colors = np.clip(np.round(np.asarray(geometry.colors) * 255), 0, 255).astype(np.uint8)
        actor = _sphere_actor(geometry.positions, geometry.radii, colors)
        prop = actor.GetProperty()
        prop.SetSpecular(0.3)
        prop.SetSpecularPower(40)
        plotter.add_actor(actor, reset_camera=False, render=False)
        self._atoms_actor = actor

        if len(geometry.cell_edges):
            edges = np.asarray(geometry.cell_edges, dtype=float)
            n = len(edges)
            lines = np.column_stack([np.full(n, 2), 2 * np.arange(n), 2 * np.arange(n) + 1])
            mesh = pv.PolyData(edges.reshape(-1, 3), lines=lines.ravel())
            tubes = mesh.tube(radius=geometry.cell_edge_radius, n_sides=16, capping=True)
            corners = pv.PolyData(np.unique(edges.reshape(-1, 3).round(9), axis=0)).glyph(
                geom=pv.Sphere(radius=geometry.cell_edge_radius, theta_resolution=16,
                               phi_resolution=12),
                scale=False, orient=False,
            )
            plotter.add_mesh(
                tubes.merge(corners), color=geometry.cell_edge_color, name="cell_edges",
                reset_camera=False, render=False,
            )
        self._geometry = geometry
        plotter.render()

    def set_highlight(self, indices: list[int]) -> None:
        """Mark displayed atoms (indices into the current geometry) as selected.

        The highlight exists only in the live view; it is never exported.
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
        """Displayed atom under a device-pixel position (top-left origin), or None."""
        if self._geometry is None:
            return None
        width, height = self.render_size()
        return pick_sphere(self.camera(), width, height, pixel, self._geometry.positions,
                           self._geometry.radii)

    def handle_click(self, position: QPointF, toggle: bool) -> None:
        """Called for a left click without dragging (widget coordinates)."""
        ratio = self._plotter.devicePixelRatioF()
        index = self.pick((position.x() * ratio, position.y() * ratio))
        self.atom_clicked.emit(-1 if index is None else index, toggle)

    # ----- camera -----------------------------------------------------------------
    def camera(self) -> Camera:
        cam = self._plotter.renderer.GetActiveCamera()
        return Camera(
            position=cam.GetPosition(),
            focal_point=cam.GetFocalPoint(),
            view_up=cam.GetViewUp(),
            parallel_scale=cam.GetParallelScale(),
        )

    def set_camera(self, camera: Camera, render: bool = True) -> None:
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
        """Frame the visible structure, keeping the current orientation."""
        if self._geometry is None:
            return
        width, height = self.render_size()
        points, radii = self._geometry.points_and_radii()
        self.set_camera(self.camera().fitted(points, radii, width / height))

    def render_size(self) -> tuple[int, int]:
        width, height = self._plotter.render_window.GetSize()
        return max(int(width), 1), max(int(height), 1)

    # ----- evidence / testing helpers ---------------------------------------------------
    def render(self) -> None:
        self._plotter.render()

    def set_axes_visible(self, visible: bool) -> None:
        if visible:
            self._plotter.show_axes()
        else:
            self._plotter.hide_axes()
        self._plotter.render()

    def screenshot(self, transparent: bool = False) -> np.ndarray:
        """RGBA image of the viewport (row 0 at the top)."""
        image = self._plotter.screenshot(transparent_background=transparent, return_img=True)
        if image.shape[2] == 3:
            alpha = np.full(image.shape[:2] + (1,), 255, dtype=image.dtype)
            image = np.concatenate([image, alpha], axis=2)
        return image

    def vtk_project(self, points: np.ndarray) -> np.ndarray:
        """Project world points using VTK's own transform (top-left pixel origin)."""
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
        self._plotter.close()

    # ----- internals --------------------------------------------------------------
    def _on_interaction_end(self, *_args: object) -> None:
        self.camera_changed.emit()


def _sphere_actor(
    positions: np.ndarray, radii: np.ndarray, colors: np.ndarray | None = None
) -> vtkActor:
    """Instanced spheres (one mesh, many atoms) via vtkGlyph3DMapper."""
    points = pv.PolyData(np.asarray(positions, dtype=float).reshape(-1, 3))
    points.point_data["radius"] = np.asarray(radii, dtype=float)
    sphere = vtkSphereSource()
    sphere.SetRadius(1.0)
    sphere.SetThetaResolution(40)
    sphere.SetPhiResolution(28)
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
