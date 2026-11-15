"""Overview of the lighting rig with draggable main-light handles (FR-LIGHT-01).

[`LightingOverview`][ycrystal.viewport.lighting_view.LightingOverview] draws a
lightweight copy of the displayed crystal together with the resolved
[`LightingRig`][ycrystal.core.lighting.LightingRig]: the main (key) and fill lights, the
output camera with its frame, the focal point ``F``, the geometry centre ``C``, the
azimuth and elevation guides, the area-light size, and the reflection panel. It has its
own VTK render window and camera: navigating it never changes the output camera, the
lighting, or the image, and none of its graphics reach the main view, picking, fitting,
or exports.

Two handles edit the main-light direction. The main-light marker itself moves on the
sphere of radius ``D`` around ``F`` (azimuth and elevation); the flat marker on the
horizon ring changes only the azimuth. Angles are always interpreted in the *output*
camera's basis, never in this overview's camera, and are rounded to whole degrees like
the numeric controls. The overview only reports angles
(`key_drag_changed`, `key_drag_finished`, `key_drag_cancelled`); the owner applies them
and passes the updated rig back with
[`set_rig`][ycrystal.viewport.lighting_view.LightingOverview.set_rig].

Mouse: left drag on a handle edits; elsewhere left drag orbits the overview, middle drag
or Shift + left drag pans, the wheel zooms. Esc or another mouse button cancels a handle
drag and restores the starting angles.
"""

from __future__ import annotations

import os

os.environ["QT_API"] = "pyside6"

import math  # noqa: E402

import numpy as np  # noqa: E402
import pyvista as pv  # noqa: E402
from PySide6.QtCore import QEvent, QObject, QPointF, Qt, Signal  # noqa: E402
from PySide6.QtGui import QKeyEvent, QMouseEvent  # noqa: E402
from PySide6.QtWidgets import QVBoxLayout, QWidget  # noqa: E402
from pyvistaqt import QtInteractor  # noqa: E402
from vtkmodules.vtkFiltersSources import vtkSphereSource  # noqa: E402
from vtkmodules.vtkRenderingCore import (  # noqa: E402
    vtkActor,
    vtkBillboardTextActor3D,
    vtkGlyph3DMapper,
    vtkPolyDataMapper,
)

from ycrystal.core.camera import Camera  # noqa: E402
from ycrystal.core.lighting import LightingRig, angles_of, wrap_azimuth  # noqa: E402
from ycrystal.core.scene import DisplayGeometry  # noqa: E402

HANDLE_PICK_PX = 14.0
"""Largest distance in device pixels between the cursor and a handle that grabs it."""

MAX_SPHERE_ATOMS = 3000
"""Above this many displayed atoms the overview draws points instead of spheres."""

KEY_COLOR = (0.95, 0.55, 0.05)
FILL_COLOR = (0.2, 0.5, 0.9)
GUIDE_COLOR = (0.55, 0.55, 0.6)
CAMERA_COLOR = (0.25, 0.25, 0.3)
FRAME_COLOR = (0.15, 0.45, 0.95)
CENTRE_COLOR = (0.55, 0.2, 0.65)
TEXT_COLOR = (0.1, 0.1, 0.12)
OFF_COLOR = (0.6, 0.6, 0.6)
BACKGROUND = (0.97, 0.97, 0.98)

LABEL_OFFSETS = {"focal": (10, 10), "centre": (-95, -30), "camera": (8, -24), "area": (12, -36)}
"""Screen offsets in pixels of labels that would otherwise overlap (F and C are often
almost at the same place)."""


class _OverviewFilter(QObject):
    """Route handle drags to the overview; let VTK navigate otherwise; swallow keys."""

    def __init__(self, view: LightingOverview) -> None:
        super().__init__(view)
        self._view = view

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        view = self._view
        kind = event.type()
        if kind in (QEvent.Type.KeyPress, QEvent.Type.KeyRelease):
            if (
                kind == QEvent.Type.KeyPress
                and isinstance(event, QKeyEvent)
                and event.key() == Qt.Key.Key_Escape
            ):
                view.cancel_drag()
            event.ignore()
            return True  # VTK key bindings (q, e, w, …) stay off
        if not isinstance(event, QMouseEvent):
            return False
        pixel = view._device(event.position())
        if kind == QEvent.Type.MouseButtonPress:
            if view.is_dragging():
                view.cancel_drag()  # another button cancels
                return True
            shift = bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier)
            if event.button() == Qt.MouseButton.LeftButton and not shift:
                handle = view.handle_at(pixel)
                if handle is not None:
                    view.begin_drag(handle)
                    return True
        elif kind == QEvent.Type.MouseMove:
            if view.is_dragging():
                view.drag_to(pixel)
                return True
            view._update_hover(pixel)
        elif kind == QEvent.Type.MouseButtonRelease and view.is_dragging():
            if event.button() == Qt.MouseButton.LeftButton:
                view.end_drag(pixel)
            return True
        return False


class LightingOverview(QWidget):
    """3D overview of the lighting rig with its own camera and two main-light handles.

    Parameters
    ----------
    parent
        Qt parent widget.
    """

    key_drag_started = Signal()
    """A handle drag started."""

    key_drag_changed = Signal(float, float)
    """During a handle drag: new main-light ``(azimuth, elevation)`` in degrees, emitted
    when the rounded angles change."""

    key_drag_finished = Signal(float, float)
    """A handle drag ended (left button released) at ``(azimuth, elevation)``."""

    key_drag_cancelled = Signal()
    """A handle drag was cancelled (Esc, another button); the start angles apply."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._plotter = QtInteractor(self, auto_update=False, multi_samples=4)
        layout.addWidget(self._plotter)
        self._plotter.enable_trackball_style()
        self._plotter.set_background(BACKGROUND)
        # The overview keeps PyVista's light kit: readable shading, independent of the rig.
        self._filter = _OverviewFilter(self)
        self._plotter.installEventFilter(self._filter)
        self._plotter.setToolTip(
            "Drag the orange sphere (main light) to change its azimuth and elevation, or "
            "the flat orange disc on the grey horizon ring to change the azimuth only.\n"
            "Elsewhere: left drag orbits this overview, Shift/middle drag pans, the wheel "
            "zooms. The output camera and the image do not change. Esc cancels a drag."
        )
        renderer = self._plotter.renderer
        self._actors: dict[str, vtkActor] = {}
        self._labels: dict[str, vtkBillboardTextActor3D] = {}
        for name in (
            "cell",
            "horizon",
            "camera_axis",
            "frame",
            "key_line",
            "fill_line",
            "azimuth_arc",
            "elevation_arc",
            "focal",
            "centre",
            "camera",
            "key",
            "fill",
            "azimuth_handle",
            "area",
            "panel",
            "panel_edge",
        ):
            actor = vtkActor()
            mapper = vtkPolyDataMapper()
            mapper.SetInputData(pv.PolyData())
            mapper.ScalarVisibilityOff()
            actor.SetMapper(mapper)
            renderer.AddActor(actor)
            self._actors[name] = actor
        self._style()
        for name in (
            "key",
            "fill",
            "focal",
            "centre",
            "camera",
            "azimuth",
            "elevation",
            "area",
            "panel",
        ):
            label = vtkBillboardTextActor3D()
            prop = label.GetTextProperty()
            prop.SetFontSize(15)
            prop.SetColor(*TEXT_COLOR)
            prop.SetBackgroundColor(1.0, 1.0, 1.0)
            prop.SetBackgroundOpacity(0.75)
            prop.SetBold(name in ("key", "fill"))
            label.SetDisplayOffset(*LABEL_OFFSETS.get(name, (10, 6)))
            label.SetPickable(False)
            renderer.AddActor(label)
            self._labels[name] = label
        self._atoms: vtkActor | None = None
        self._geometry: DisplayGeometry | None = None
        self._rig: LightingRig | None = None
        self._drag: dict | None = None
        self._has_view = False

    # ----- content ------------------------------------------------------------------------
    def set_geometry(self, geometry: DisplayGeometry) -> None:
        """Draw a lightweight copy of the displayed atoms and cell edges.

        Unchanged geometry (same atoms, radii, colours, and edges) is not redrawn.
        """
        if self._geometry is not None and _same_geometry(self._geometry, geometry):
            self._geometry = geometry
            return
        self._geometry = geometry
        renderer = self._plotter.renderer
        if self._atoms is not None:
            renderer.RemoveActor(self._atoms)
            self._atoms = None
        if len(geometry):
            colors = np.clip(np.round(np.asarray(geometry.colors) * 255), 0, 255).astype(np.uint8)
            points = pv.PolyData(np.asarray(geometry.positions, dtype=float))
            points.point_data["colors"] = colors
            actor = vtkActor()
            if len(geometry) <= MAX_SPHERE_ATOMS:
                points.point_data["radius"] = np.asarray(geometry.radii, dtype=float)
                sphere = vtkSphereSource()
                sphere.SetThetaResolution(12)
                sphere.SetPhiResolution(8)
                mapper = vtkGlyph3DMapper()
                mapper.SetSourceConnection(sphere.GetOutputPort())
                mapper.SetScaleArray("radius")
                mapper.SetScaleModeToScaleByMagnitude()
                mapper.SetScaleFactor(2.0)  # the source sphere has radius 0.5
            else:
                mapper = vtkPolyDataMapper()
                actor.GetProperty().SetPointSize(3.0)
                actor.GetProperty().SetRepresentationToPoints()
            mapper.SetInputData(points)
            mapper.SetScalarModeToUsePointFieldData()
            mapper.SelectColorArray("colors")
            mapper.SetColorModeToDirectScalars()
            mapper.ScalarVisibilityOn()
            actor.SetMapper(mapper)
            actor.SetPickable(False)
            renderer.AddActor(actor)
            self._atoms = actor
        edges = np.asarray(geometry.cell_edges, dtype=float)
        if len(edges):
            n = len(edges)
            lines = np.column_stack([np.full(n, 2), 2 * np.arange(n), 2 * np.arange(n) + 1])
            mesh = pv.PolyData(edges.reshape(-1, 3), lines=lines.ravel())
        else:
            mesh = pv.PolyData()
        self._set_mesh("cell", mesh)
        self._render()

    def set_rig(self, rig: LightingRig, frame_size: tuple[float, float] | None = None) -> None:
        """Show a resolved rig; the overview camera is fitted only the first time.

        Parameters
        ----------
        rig
            Lights and reference points to draw (from the output camera).
        frame_size
            Visible width and height of the output image in Å, drawn as a rectangle at
            ``F``; ``None`` leaves the frame out.
        """
        self._rig = rig
        f, d_len = rig.origin, rig.distance
        r, u, d = rig.right, rig.up, rig.direction
        size = 0.05 * d_len
        key, fill = rig.key, rig.fill

        horizon = _polyline(_ring(rig, d_len), closed=True)
        self._set_mesh("horizon", horizon)
        camera_pos = f - d_len * d
        self._set_mesh("camera_axis", pv.Line(camera_pos, f))
        self._set_mesh(
            "camera",
            pv.Cone(
                center=camera_pos + 0.06 * d_len * d,
                direction=d,
                height=0.12 * d_len,
                radius=0.05 * d_len,
                resolution=24,
            ),
        )
        if frame_size is not None:
            w, h = frame_size
            corners = [
                f + sx * 0.5 * w * r + sy * 0.5 * h * u
                for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1))
            ]
            self._set_mesh("frame", _polyline(np.array(corners), closed=True))
        else:
            self._set_mesh("frame", pv.PolyData())
        self._set_mesh("key_line", pv.Line(f, key.position))
        self._set_mesh("fill_line", pv.Line(f, fill.position))
        az, el = rig.azimuth, rig.elevation
        az_pts = _arc(rig, (0.0, az), (0.0, 0.0), d_len)
        el_pts = _arc(rig, (az, az), (0.0, el), d_len)
        self._set_mesh("azimuth_arc", _polyline(az_pts))
        self._set_mesh("elevation_arc", _polyline(el_pts))
        cross = np.array(
            [f - size * r, f + size * r, f - size * u, f + size * u, f - size * d, f + size * d]
        )
        self._set_mesh("focal", pv.PolyData(cross, lines=[2, 0, 1, 2, 2, 3, 2, 4, 5]))
        self._set_mesh("centre", pv.PlatonicSolid("octahedron", radius=size, center=rig.center))
        self._set_mesh("key", pv.Sphere(radius=size, center=key.position))
        self._set_mesh(
            "fill",
            pv.Cube(
                center=fill.position, x_length=1.5 * size, y_length=1.5 * size, z_length=1.5 * size
            ),
        )
        handle = f + d_len * rig.horizontal(az)
        self._set_mesh(
            "azimuth_handle",
            pv.Cylinder(
                center=handle, direction=u, radius=0.8 * size, height=0.25 * size, resolution=24
            ),
        )
        if key.is_area:
            self._set_mesh(
                "area",
                pv.Sphere(
                    radius=0.5 * key.area_size,
                    center=key.position,
                    theta_resolution=24,
                    phi_resolution=16,
                ),
            )
        else:
            self._set_mesh("area", pv.PolyData())
        panel = rig.panel
        if panel is not None:
            self._set_mesh(
                "panel",
                pv.Disc(
                    center=panel.center,
                    inner=0.0,
                    outer=panel.radius,
                    normal=panel.normal,
                    c_res=48,
                ),
            )
            edge = _circle(panel.center, panel.normal, panel.radius)
            self._set_mesh("panel_edge", _polyline(edge, closed=True))
        else:
            self._set_mesh("panel", pv.PolyData())
            self._set_mesh("panel_edge", pv.PolyData())

        for name, on in (("key", key.enabled), ("fill", fill.enabled)):
            prop = self._actors[name].GetProperty()
            prop.SetColor(*((KEY_COLOR if name == "key" else FILL_COLOR) if on else OFF_COLOR))
            prop.SetOpacity(1.0 if on else 0.5)

        self._label("key", key.position, f"Main (key) {_level(key.intensity)}")
        self._label("fill", fill.position, f"Fill {_level(fill.intensity)} (fixed)")
        self._label("focal", f, "F focal point")
        self._label("centre", rig.center, "C centre")
        self._label("camera", camera_pos, "Output camera")
        self._label("azimuth", az_pts[len(az_pts) // 2], f"az {az:+.0f}°")
        self._label("elevation", el_pts[len(el_pts) // 2], f"el {el:+.0f}°")
        self._label(
            "area",
            key.position + 0.5 * key.area_size * u if key.is_area else None,
            f"area light, diameter {key.area_size:.2f} Å",
        )
        self._label("panel", panel.center if panel is not None else None, "Reflection panel")
        if not self._has_view:
            self.reset_view()
        else:
            self._plotter.renderer.ResetCameraClippingRange()
            self._render()

    def rig(self) -> LightingRig | None:
        """Return the rig shown, or ``None``."""
        return self._rig

    # ----- overview camera -----------------------------------------------------------------
    def reset_view(self) -> None:
        """Fit the overview to the rig: an oblique view from the upper right, in front.

        The presets put the key light on the upper left of the image, roughly across this
        line of sight, so the key light, ``F``, and the output camera stay apart.
        """
        rig = self._rig
        if rig is None:
            return
        offset = 0.7 * rig.right + 0.5 * rig.up - 0.5 * rig.direction
        offset /= np.linalg.norm(offset)
        cam = self._plotter.renderer.GetActiveCamera()
        cam.ParallelProjectionOff()
        half_angle = np.radians(cam.GetViewAngle() / 2.0)
        reach = 1.08 * rig.distance  # every marker lies within D of F
        cam.SetFocalPoint(*rig.origin)
        cam.SetPosition(*(rig.origin + reach / np.sin(half_angle) * offset))
        cam.SetViewUp(*rig.up)
        cam.OrthogonalizeViewUp()
        self._plotter.renderer.ResetCameraClippingRange()
        self._has_view = True
        self._render()

    def overview_camera(self) -> Camera:
        """Return the overview's own camera (not the output camera)."""
        cam = self._plotter.renderer.GetActiveCamera()
        return Camera(
            position=cam.GetPosition(),
            focal_point=cam.GetFocalPoint(),
            view_up=cam.GetViewUp(),
            parallel_scale=max(cam.GetParallelScale(), 1e-6),
        )

    def set_overview_camera(self, camera: Camera) -> None:
        """Set the overview's own camera (for tests and restoring a view)."""
        cam = self._plotter.renderer.GetActiveCamera()
        cam.SetPosition(*camera.position)
        cam.SetFocalPoint(*camera.focal_point)
        cam.SetViewUp(*camera.view_up)
        self._plotter.renderer.ResetCameraClippingRange()
        self._has_view = True
        self._render()

    # ----- handles ----------------------------------------------------------------------------
    def handle_positions(self) -> dict[str, np.ndarray]:
        """Return the screen positions of the handles in device pixels (top-left origin)."""
        rig = self._rig
        if rig is None:
            return {}
        world = {
            "key": rig.key.position,
            "azimuth": rig.origin + rig.distance * rig.horizontal(rig.azimuth),
        }
        return {name: self._project(point) for name, point in world.items()}

    def handle_at(self, pixel: tuple[float, float] | np.ndarray) -> str | None:
        """Return the handle under a device pixel (``"key"`` or ``"azimuth"``), or None."""
        best, best_dist = None, HANDLE_PICK_PX
        for name, point in self.handle_positions().items():
            dist = float(np.hypot(*(np.asarray(pixel, dtype=float) - point)))
            if dist <= best_dist:
                best, best_dist = name, dist
        return best

    def is_dragging(self) -> bool:
        """Whether a handle drag is in progress."""
        return self._drag is not None

    def begin_drag(self, handle: str) -> None:
        """Start dragging ``"key"`` or ``"azimuth"``."""
        if self._rig is None or handle not in ("key", "azimuth"):
            return
        start = (self._rig.azimuth, self._rig.elevation)
        self._drag = {"handle": handle, "start": start, "angles": start}
        self._plotter.setCursor(Qt.CursorShape.ClosedHandCursor)
        self.key_drag_started.emit()

    def drag_to(self, pixel: tuple[float, float] | np.ndarray) -> None:
        """Move the dragged handle under a device pixel; emit new angles if they change."""
        if self._drag is None or self._rig is None:
            return
        angles = self._drag_angles(np.asarray(pixel, dtype=float))
        if angles is not None and angles != self._drag["angles"]:
            self._drag["angles"] = angles
            self.key_drag_changed.emit(*angles)

    def end_drag(self, pixel: tuple[float, float] | np.ndarray | None = None) -> None:
        """Finish the drag (one change for the owner to record)."""
        if self._drag is None:
            return
        if pixel is not None:
            self.drag_to(pixel)
        drag, self._drag = self._drag, None
        self._plotter.unsetCursor()
        self.key_drag_finished.emit(*drag["angles"])

    def cancel_drag(self) -> bool:
        """Cancel a drag in progress; return whether one was cancelled."""
        if self._drag is None:
            return False
        self._drag = None
        self._plotter.unsetCursor()
        self.key_drag_cancelled.emit()
        return True

    def _drag_angles(self, pixel: np.ndarray) -> tuple[float, float] | None:
        rig = self._rig
        assert rig is not None and self._drag is not None
        origin, ray = self._ray(pixel)
        f, r, u, d = rig.origin, rig.right, rig.up, rig.direction
        _, elevation = self._drag["angles"]
        previous_az = self._drag["angles"][0]
        if self._drag["handle"] == "key":
            point = _sphere_hit(origin, ray, f, rig.distance, near=rig.key.position)
            az, el = angles_of(point - f, r, u, d, previous_azimuth=previous_az)
        else:
            point = _plane_hit(origin, ray, f, u)
            v = point - f
            x, z = float(v @ r), float(-(v @ d))
            if math.hypot(x, z) < 1e-9 * rig.distance:
                return None
            az, el = math.degrees(math.atan2(x, z)), elevation
        return wrap_azimuth(float(round(az))), float(round(el))

    # ----- helpers ----------------------------------------------------------------------------
    @property
    def interactor_widget(self) -> QWidget:
        """The Qt widget that receives mouse events (for tests)."""
        return self._plotter

    def render(self) -> None:
        """Redraw the overview."""
        self._render()

    def close_view(self) -> None:
        """Release the VTK render window; call before the widget is discarded."""
        self._plotter.close()

    def actor_count(self) -> int:
        """Return the number of props in the overview renderer (for tests)."""
        return self._plotter.renderer.GetViewProps().GetNumberOfItems()

    def _render(self) -> None:
        if self.isVisible():
            self._plotter.render()

    def _device(self, position: QPointF) -> np.ndarray:
        ratio = self._plotter.devicePixelRatioF()
        return np.array([position.x() * ratio, position.y() * ratio])

    def _size(self) -> tuple[int, int]:
        width, height = self._plotter.render_window.GetSize()
        return max(int(width), 1), max(int(height), 1)

    def _project(self, point: np.ndarray) -> np.ndarray:
        renderer = self._plotter.renderer
        _, height = self._size()
        renderer.SetWorldPoint(float(point[0]), float(point[1]), float(point[2]), 1.0)
        renderer.WorldToDisplay()
        x, y, _ = renderer.GetDisplayPoint()
        return np.array([x, height - y])

    def _ray(self, pixel: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        renderer = self._plotter.renderer
        _, height = self._size()
        ends = []
        for depth in (0.0, 1.0):
            renderer.SetDisplayPoint(float(pixel[0]), float(height - pixel[1]), depth)
            renderer.DisplayToWorld()
            x, y, z, w = renderer.GetWorldPoint()
            ends.append(np.array([x, y, z]) / (w if w else 1.0))
        direction = ends[1] - ends[0]
        return ends[0], direction / np.linalg.norm(direction)

    def _update_hover(self, pixel: np.ndarray) -> None:
        if self.handle_at(pixel) is not None:
            self._plotter.setCursor(Qt.CursorShape.OpenHandCursor)
        else:
            self._plotter.unsetCursor()

    def _set_mesh(self, name: str, mesh: pv.PolyData) -> None:
        self._actors[name].GetMapper().SetInputData(mesh)

    def _label(self, name: str, position: np.ndarray | None, text: str) -> None:
        label = self._labels[name]
        if position is None:
            label.SetVisibility(False)
            return
        label.SetInput(text)
        label.SetPosition(*np.asarray(position, dtype=float))
        label.SetVisibility(True)

    def _style(self) -> None:
        def style(name, color, width=None, opacity=1.0, wire=False):  # noqa: ANN001, ANN202
            prop = self._actors[name].GetProperty()
            prop.SetColor(*color)
            prop.SetOpacity(opacity)
            if width is not None:
                prop.SetLineWidth(width)
            if wire:
                prop.SetRepresentationToWireframe()
            self._actors[name].SetPickable(False)

        style("cell", CAMERA_COLOR, 1.0)
        style("horizon", GUIDE_COLOR, 1.0)
        style("camera_axis", CAMERA_COLOR, 1.5)
        style("frame", FRAME_COLOR, 2.0)
        style("key_line", KEY_COLOR, 2.5)
        style("fill_line", FILL_COLOR, 1.5)
        style("azimuth_arc", KEY_COLOR, 3.0)
        style("elevation_arc", KEY_COLOR, 3.0)
        style("focal", TEXT_COLOR, 3.0)
        style("centre", CENTRE_COLOR, 2.0, wire=True)
        style("camera", CAMERA_COLOR)
        style("key", KEY_COLOR)
        style("fill", FILL_COLOR)
        style("azimuth_handle", KEY_COLOR)
        style("area", KEY_COLOR, 1.0, opacity=0.35, wire=True)
        style("panel", (1.0, 1.0, 1.0), opacity=0.45)
        style("panel_edge", CAMERA_COLOR, 1.5)


def _level(intensity: float) -> str:
    return f"{intensity:.2f}" if intensity > 0 else "off"


def _same_geometry(a: DisplayGeometry, b: DisplayGeometry) -> bool:
    if a is b:
        return True
    return (
        len(a) == len(b)
        and np.array_equal(a.positions, b.positions)
        and np.array_equal(a.radii, b.radii)
        and np.array_equal(a.colors, b.colors)
        and np.array_equal(a.cell_edges, b.cell_edges)
    )


def _arc(
    rig: LightingRig, azimuths: tuple[float, float], elevations: tuple[float, float], radius: float
) -> np.ndarray:
    from ycrystal.core.lighting import arc_points

    span = max(abs(azimuths[1] - azimuths[0]), abs(elevations[1] - elevations[0]))
    return arc_points(rig, azimuths, elevations, radius, count=max(2, int(span / 3) + 2))


def _ring(rig: LightingRig, radius: float) -> np.ndarray:
    angles = np.linspace(-np.pi, np.pi, 97)[:-1]
    return rig.origin + radius * (
        np.outer(np.sin(angles), rig.right) - np.outer(np.cos(angles), rig.direction)
    )


def _circle(center: np.ndarray, normal: np.ndarray, radius: float) -> np.ndarray:
    helper = np.array([1.0, 0.0, 0.0]) if abs(normal[0]) < 0.9 else np.array([0.0, 1.0, 0.0])
    a = np.cross(normal, helper)
    a /= np.linalg.norm(a)
    b = np.cross(normal, a)
    angles = np.linspace(0.0, 2.0 * np.pi, 49)[:-1]
    return center + radius * (np.outer(np.cos(angles), a) + np.outer(np.sin(angles), b))


def _polyline(points: np.ndarray, closed: bool = False) -> pv.PolyData:
    points = np.asarray(points, dtype=float)
    n = len(points)
    if n < 2:
        return pv.PolyData()
    ids = list(range(n)) + ([0] if closed else [])
    return pv.PolyData(points, lines=[len(ids), *ids])


def _sphere_hit(
    origin: np.ndarray, ray: np.ndarray, center: np.ndarray, radius: float, near: np.ndarray
) -> np.ndarray:
    """Return the ray's intersection with a sphere closest to ``near``.

    A ray that misses the sphere gives the point of the sphere's silhouette nearest to
    it, so dragging past the edge slides along the outline instead of jumping.
    """
    oc = origin - center
    b = float(ray @ oc)
    c = float(oc @ oc) - radius * radius
    disc = b * b - c
    if disc >= 0.0:
        root = math.sqrt(disc)
        hits = [origin + t * ray for t in (-b - root, -b + root)]
        return min(hits, key=lambda p: float(np.linalg.norm(p - near)))
    closest = origin - b * ray
    offset = closest - center
    return center + radius * offset / np.linalg.norm(offset)


def _plane_hit(
    origin: np.ndarray, ray: np.ndarray, point: np.ndarray, normal: np.ndarray
) -> np.ndarray:
    """Return the ray's intersection with a plane, or the nearest point when parallel."""
    denom = float(ray @ normal)
    if abs(denom) > 1e-6:
        t = float((point - origin) @ normal) / denom
        return origin + t * ray
    closest = origin + float((point - origin) @ ray) * ray
    return closest - float((closest - point) @ normal) * normal
