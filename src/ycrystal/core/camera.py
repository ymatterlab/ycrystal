"""Renderer-independent orthographic camera.

The VTK viewport, atom picking, and the POV-Ray writer share these conventions:

* World coordinates are right-handed Cartesian coordinates in ångström (Å), the same
  coordinates as the structure. Angles are in degrees.
* The viewing direction is ``d = normalize(focal_point - position)``.
* Screen right is ``r = normalize(d × view_up)`` and screen up is ``u = r × d``, as in
  VTK. ``(r, u, -d)`` is a right-handed basis: x to the right, y up, z toward the
  viewer.
* ``parallel_scale`` is half of the visible height in Å (VTK's definition). The visible
  width follows from the output aspect ratio: ``2 * parallel_scale * W / H`` for an image
  of ``W`` × ``H`` pixels, so a wider image shows more of the scene at the same scale
  and is never stretched.
* Pixel coordinates are continuous, with the origin at the top-left image corner, x to
  the right, and y downward; the centre of pixel ``(i, j)`` is ``(i + 0.5, j + 0.5)``.
  The focal point projects to the image centre.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import numpy as np

Vec3 = tuple[float, float, float]
"""A 3-vector stored as a tuple of three floats."""


def _vec(value: Any) -> Vec3:
    array = np.asarray(value, dtype=float).reshape(3)
    if not np.all(np.isfinite(array)):
        raise ValueError(f"non-finite vector: {value!r}")
    return (float(array[0]), float(array[1]), float(array[2]))


def _check_region(region: Any) -> tuple[float, float, float, float]:
    """Validate a frame region ``(left, top, right, bottom)`` in fractions of the frame."""
    left, top, right, bottom = (float(v) for v in region)
    if not (0.0 <= left < right <= 1.0 and 0.0 <= top < bottom <= 1.0):
        raise ValueError("region must lie inside the frame: 0 <= left < right <= 1, same for y")
    return left, top, right, bottom


def _rotate(vector: np.ndarray, axis: np.ndarray, angle_deg: float) -> np.ndarray:
    """Rodrigues rotation of ``vector`` about unit ``axis`` (right-hand rule)."""
    theta = math.radians(angle_deg)
    k = axis / np.linalg.norm(axis)
    return (
        vector * math.cos(theta)
        + np.cross(k, vector) * math.sin(theta)
        + k * np.dot(k, vector) * (1.0 - math.cos(theta))
    )


@dataclass(frozen=True)
class Camera:
    """Orthographic camera shared by the viewport, picking, and the POV-Ray writer.

    Instances are immutable; the navigation methods return new cameras. Vector
    arguments may be any array-like with three elements and are stored as tuples of
    floats.

    Attributes
    ----------
    position
        Eye position in Å. Under orthographic projection only the direction from
        `position` to `focal_point` affects the image; the distance matters only for
        clipping in the live view.
    focal_point
        Point in Å that appears at the image centre.
    view_up
        Approximate screen-up direction. It need not be normalized or perpendicular to
        the viewing direction: [`basis`][ycrystal.core.camera.Camera.basis] uses its
        component perpendicular to the viewing direction.
    parallel_scale
        Half of the visible image height in Å. Larger values show more of the scene.
    projection
        Always ``"orthographic"``; perspective projection is not implemented.

    Raises
    ------
    ValueError
        If a vector is not finite, `parallel_scale` is not a positive finite number,
        `position` and `focal_point` are less than 1e-9 Å apart, `view_up` is zero or
        parallel to the viewing direction, or `projection` is not ``"orthographic"``.

    See Also
    --------
    - [`StructureViewport.camera`][ycrystal.viewport.qt_viewport.StructureViewport.camera]:
      the camera of the live view.
    - [`scene_to_pov`][ycrystal.render.pov_writer.scene_to_pov]: writes the camera
      as an explicit POV-Ray camera.

    Examples
    --------
    A camera on the +z axis looking at the origin, with +y up, so that screen right
    is +x:

    >>> from ycrystal.core.camera import Camera
    >>> camera = Camera(
    ...     position=(0, 0, 10), focal_point=(0, 0, 0), view_up=(0, 1, 0), parallel_scale=5.0
    ... )
    >>> camera.visible_size(400, 200)  # width and height in Å of a 400 x 200 px image
    (20.0, 10.0)
    >>> camera.project([(0, 0, 0), (1, 0, 0), (0, 1, 0)], 400, 200)
    array([[200., 100.],
           [220., 100.],
           [200.,  80.]])
    """

    position: Vec3
    focal_point: Vec3
    view_up: Vec3
    parallel_scale: float
    projection: str = "orthographic"

    def __post_init__(self) -> None:
        object.__setattr__(self, "position", _vec(self.position))
        object.__setattr__(self, "focal_point", _vec(self.focal_point))
        object.__setattr__(self, "view_up", _vec(self.view_up))
        object.__setattr__(self, "parallel_scale", float(self.parallel_scale))
        if self.projection != "orthographic":
            raise ValueError("only orthographic projection is supported")
        if not (self.parallel_scale > 0 and math.isfinite(self.parallel_scale)):
            raise ValueError("parallel_scale must be positive")
        offset = np.subtract(self.focal_point, self.position)
        if np.linalg.norm(offset) < 1e-9:
            raise ValueError("position and focal_point must differ")
        d = offset / np.linalg.norm(offset)
        up = np.asarray(self.view_up)
        up_norm = np.linalg.norm(up)
        if up_norm < 1e-12 or np.linalg.norm(np.cross(d, up)) < 1e-9 * up_norm:
            raise ValueError("view_up must not be parallel to the viewing direction")

    # ----- basis and projection -------------------------------------------------
    @property
    def distance(self) -> float:
        """Distance from `position` to `focal_point` in Å."""
        return float(np.linalg.norm(np.subtract(self.focal_point, self.position)))

    def basis(self) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Return the orthonormal screen basis.

        Returns
        -------
        right : numpy.ndarray
            Unit screen-right vector ``normalize(direction × view_up)``, shape ``(3,)``.
        up : numpy.ndarray
            Unit screen-up vector ``right × direction``, shape ``(3,)``.
        direction : numpy.ndarray
            Unit viewing direction from `position` toward `focal_point`, shape
            ``(3,)``.

        Notes
        -----
        ``(right, up, -direction)`` is right-handed. New arrays are returned on every
        call.
        """
        d = np.subtract(self.focal_point, self.position)
        d = d / np.linalg.norm(d)
        r = np.cross(d, self.view_up)
        r = r / np.linalg.norm(r)
        u = np.cross(r, d)
        return r, u, d

    def visible_size(self, width: int, height: int) -> tuple[float, float]:
        """Return the visible width and height in Å for an image size in pixels.

        Parameters
        ----------
        width
            Image width in pixels.
        height
            Image height in pixels.

        Returns
        -------
        tuple of float
            ``(2 * parallel_scale * width / height, 2 * parallel_scale)``.

        Raises
        ------
        ValueError
            If `width` or `height` is not positive.
        """
        _check_size(width, height)
        return 2.0 * self.parallel_scale * width / height, 2.0 * self.parallel_scale

    def project(self, points: Any, width: int, height: int) -> np.ndarray:
        """Project world points to continuous pixel coordinates.

        Parameters
        ----------
        points
            Points in Å; any array-like that reshapes to ``(K, 3)``.
        width
            Image width in pixels.
        height
            Image height in pixels.

        Returns
        -------
        numpy.ndarray
            Pixel coordinates ``(x, y)``, shape ``(K, 2)``, with the origin at the
            top-left image corner, x to the right, and y downward. Depth is ignored:
            points outside the image or behind the eye are projected as well.

        Raises
        ------
        ValueError
            If `width` or `height` is not positive.
        """
        _check_size(width, height)
        pts = np.asarray(points, dtype=float).reshape(-1, 3)
        r, u, _ = self.basis()
        rel = pts - np.asarray(self.focal_point)
        pixels_per_unit = height / (2.0 * self.parallel_scale)
        x = width / 2.0 + (rel @ r) * pixels_per_unit
        y = height / 2.0 - (rel @ u) * pixels_per_unit
        return np.column_stack([x, y])

    def pixels_per_angstrom(self, height: int) -> float:
        """Return the image scale in pixels per Å for an image `height` pixels high.

        Pixels are square, so the same scale applies horizontally.
        """
        return height / (2.0 * self.parallel_scale)

    # ----- pure navigation helpers (used by scripted views and checks) ----------
    def orbit(self, azimuth: float = 0.0, elevation: float = 0.0) -> Camera:
        """Rotate the eye about the focal point.

        Parameters
        ----------
        azimuth
            Rotation in degrees about the screen-up axis through the focal point.
            Positive values move the eye toward screen right.
        elevation
            Rotation in degrees about the (already turned) screen-right axis. Positive
            values move the eye toward screen up.

        Returns
        -------
        Camera
            A camera with the same focal point, distance, and `parallel_scale`, and a
            rotated `view_up`.

        Notes
        -----
        The axes and signs match ``vtkCamera.Azimuth`` followed by
        ``vtkCamera.Elevation`` applied to a camera whose view-up vector is
        orthogonal to the viewing direction; the tests compare both.
        """
        r, u, _ = self.basis()
        focal = np.asarray(self.focal_point)
        offset = np.asarray(self.position) - focal
        offset = _rotate(offset, u, azimuth)
        up = np.asarray(self.view_up)
        r = _rotate(r, u, azimuth)
        offset = _rotate(offset, r, -elevation)
        up = _rotate(_rotate(up, u, azimuth), r, -elevation)
        return self._replace(position=focal + offset, view_up=up)

    def roll(self, angle: float) -> Camera:
        """Rotate the view about the viewing direction.

        Parameters
        ----------
        angle
            Rotation in degrees. Positive values tilt the up vector toward screen
            right, so the image turns counter-clockwise.

        Returns
        -------
        Camera
            A camera with the same position, focal point, and `parallel_scale`.
        """
        _, u, d = self.basis()
        return self._replace(view_up=_rotate(u, d, angle))

    def rotate_about(self, axis: Any, angle: float) -> Camera:
        """Turn the view so that the scene appears rotated about a fixed world axis.

        Parameters
        ----------
        axis
            Rotation axis in world coordinates (any length), through the focal point;
            for example a lattice vector or a Cartesian axis.
        angle
            Apparent rotation of the scene in degrees, right-handed about `axis`. The
            eye and the view-up vector turn by ``-angle``; the structure itself is not
            changed.

        Returns
        -------
        Camera
            A camera with the same focal point, distance, and `parallel_scale`.

        Raises
        ------
        ValueError
            If `axis` has zero length.

        Examples
        --------
        Looking down -z with y up, a 90° turn about y brings the scene's -x side to the
        front (where +z was), so the eye ends up on the -x side:

        >>> from ycrystal.core.camera import Camera
        >>> cam = Camera.looking_along((0, 0, -1), (0, 1, 0), parallel_scale=5.0)
        >>> turned = cam.rotate_about((0, 1, 0), 90)
        >>> [round(v, 6) + 0.0 for v in turned.position], turned.view_up
        ([-50.0, 0.0, 0.0], (0.0, 1.0, 0.0))
        """
        k = np.asarray(axis, dtype=float)
        if not np.linalg.norm(k) > 0:
            raise ValueError("rotation axis must have non-zero length")
        focal = np.asarray(self.focal_point)
        offset = _rotate(np.asarray(self.position) - focal, k, -angle)
        up = _rotate(np.asarray(self.view_up), k, -angle)
        return self._replace(position=focal + offset, view_up=up)

    def pan(self, dx: float, dy: float) -> Camera:
        """Move the eye and the focal point within the screen plane.

        Parameters
        ----------
        dx
            Shift in Å along screen right.
        dy
            Shift in Å along screen up.

        Returns
        -------
        Camera
            The shifted camera. The scene appears to move the opposite way.
        """
        r, u, _ = self.basis()
        shift = dx * r + dy * u
        return self._replace(
            position=np.asarray(self.position) + shift,
            focal_point=np.asarray(self.focal_point) + shift,
        )

    def zoom(self, factor: float) -> Camera:
        """Return a camera that magnifies the image by `factor`.

        Parameters
        ----------
        factor
            Magnification; values above 1 zoom in. The new `parallel_scale` is
            ``parallel_scale / factor``.

        Returns
        -------
        Camera
            The zoomed camera.

        Raises
        ------
        ValueError
            If `factor` is not positive.
        """
        if factor <= 0:
            raise ValueError("zoom factor must be positive")
        return self._replace(parallel_scale=self.parallel_scale / factor)

    def fitted(
        self,
        points: Any,
        radii: Any,
        aspect: float,
        margin: float = 0.06,
        region: tuple[float, float, float, float] | None = None,
    ) -> Camera:
        """Centre and scale the view on spheres, keeping the orientation.

        Parameters
        ----------
        points
            Sphere centres in Å; any array-like that reshapes to ``(K, 3)``.
        radii
            Sphere radii in Å: one value for all spheres or one per sphere.
        aspect
            Output width divided by output height.
        margin
            Extra space as a fraction of the fitted half-height; 0.06 adds 6 %.
        region
            Part of the frame the spheres are fitted into, as ``(left, top, right,
            bottom)`` fractions of the frame width and height (top-left origin), for
            example the space an element legend leaves free; ``None`` is the whole
            frame (see [`placed_in`][ycrystal.core.camera.Camera.placed_in]).

        Returns
        -------
        Camera
            A camera with the same viewing direction and up vector. The focal point
            moves within the screen plane to the centre of the projected spheres, and
            `parallel_scale` is the smallest value that shows all of them at this
            aspect ratio, enlarged by `margin`. The eye is moved back if necessary so
            that it lies in front of every sphere. If `points` is empty, this camera
            is returned unchanged.

        Raises
        ------
        ValueError
            If `aspect` is not positive or `region` is not inside the frame.

        Examples
        --------
        Fitted into the upper 80 % of the frame, the view is 1.25 times as tall and the
        spheres sit 10 % of the frame height above its centre:

        >>> cam = Camera.looking_along((0, 1, 0), (0, 0, 1))
        >>> points = [[0.0, 0.0, 0.0], [0.0, 0.0, 2.0]]
        >>> full = cam.fitted(points, 1.0, 1.0, margin=0.0)
        >>> upper = cam.fitted(points, 1.0, 1.0, margin=0.0, region=(0.0, 0.0, 1.0, 0.8))
        >>> round(upper.parallel_scale / full.parallel_scale, 6)
        1.25
        >>> float(np.round(upper.project([[0.0, 0.0, 1.0]], 100, 100)[0, 1], 6))
        40.0
        """
        if region is not None:
            left, top, right, bottom = _check_region(region)
            inner = (right - left) / (bottom - top)
            return self.fitted(points, radii, aspect * inner, margin).placed_in(region, aspect)
        if aspect <= 0:
            raise ValueError("aspect must be positive")
        pts = np.asarray(points, dtype=float).reshape(-1, 3)
        rad = np.broadcast_to(np.asarray(radii, dtype=float), (len(pts),))
        if len(pts) == 0:
            return self
        r, u, d = self.basis()
        focal = np.asarray(self.focal_point)
        rel = pts - focal
        xs, ys, zs = rel @ r, rel @ u, rel @ d
        x0, x1 = (xs - rad).min(), (xs + rad).max()
        y0, y1 = (ys - rad).min(), (ys + rad).max()
        new_focal = focal + 0.5 * (x0 + x1) * r + 0.5 * (y0 + y1) * u
        half_h = max(0.5 * (y1 - y0), 0.5 * (x1 - x0) / aspect, 1e-3)
        scale = half_h * (1.0 + margin)
        # Keep the eye in front of the whole scene (orthographic: depth does not
        # change the image, only clipping).
        extent = float(np.max(np.abs(zs) + rad)) + float(np.ptp(xs) + np.ptp(ys))
        distance = max(self.distance, 2.0 * extent, 1.0)
        return Camera(
            position=tuple(new_focal - distance * d),
            focal_point=tuple(new_focal),
            view_up=tuple(u),
            parallel_scale=scale,
        )

    def placed_in(self, region: tuple[float, float, float, float], aspect: float) -> Camera:
        """Return the camera whose frame shows this camera's view inside ``region``.

        This camera's image (at the aspect ratio of `region`) appears, unchanged in
        scale, in the part ``(left, top, right, bottom)`` of the new frame, given as
        fractions of its width and height (top-left origin); the new frame has the
        aspect ratio `aspect`. Only the focal point, the eye, and the parallel scale
        change; the orientation is kept.

        Raises
        ------
        ValueError
            If `aspect` is not positive or `region` is not inside the frame.
        """
        if aspect <= 0:
            raise ValueError("aspect must be positive")
        left, top, right, bottom = _check_region(region)
        scale = self.parallel_scale / (bottom - top)
        full_h = 2.0 * scale
        full_w = full_h * aspect
        r, u, _ = self.basis()
        shift = -r * ((left + right) / 2 - 0.5) * full_w + u * ((top + bottom) / 2 - 0.5) * full_h
        return Camera(
            position=tuple(np.asarray(self.position) + shift),
            focal_point=tuple(np.asarray(self.focal_point) + shift),
            view_up=self.view_up,
            parallel_scale=scale,
        )

    @classmethod
    def looking_along(
        cls,
        direction: Any,
        view_up: Any,
        focal_point: Any = (0, 0, 0),
        distance: float = 50.0,
        parallel_scale: float = 10.0,
    ) -> Camera:
        """Create a camera that looks along a direction at a focal point.

        Parameters
        ----------
        direction
            Viewing direction; normalized internally.
        view_up
            Approximate screen-up direction; must not be parallel to `direction`.
        focal_point
            Point in Å at the image centre.
        distance
            Distance in Å from the eye to the focal point.
        parallel_scale
            Half of the visible height in Å.

        Returns
        -------
        Camera
            The new camera, with its eye at ``focal_point - distance * direction``.

        Raises
        ------
        ValueError
            If the resulting camera is invalid, for example because `view_up` is
            parallel to `direction`.
        """
        d = np.asarray(direction, dtype=float)
        d = d / np.linalg.norm(d)
        focal = np.asarray(focal_point, dtype=float)
        return cls(
            position=tuple(focal - distance * d),
            focal_point=tuple(focal),
            view_up=tuple(np.asarray(view_up, dtype=float)),
            parallel_scale=parallel_scale,
        )

    # ----- serialisation ----------------------------------------------------------
    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-compatible dictionary, as stored in project files.

        Returns
        -------
        dict
            Keys ``projection``, ``position``, ``focal_point``, ``view_up`` (lists of
            three floats), and ``parallel_scale``.
        """
        return {
            "projection": self.projection,
            "position": list(self.position),
            "focal_point": list(self.focal_point),
            "view_up": list(self.view_up),
            "parallel_scale": self.parallel_scale,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Camera:
        """Create a camera from the output of [`to_dict`][ycrystal.core.camera.Camera.to_dict].

        Parameters
        ----------
        data
            Dictionary with ``position``, ``focal_point``, ``view_up``, and
            ``parallel_scale``; ``projection`` is optional.

        Returns
        -------
        Camera
            The validated camera.

        Raises
        ------
        KeyError
            If a required key is missing.
        ValueError
            If a value is invalid (see [`Camera`][ycrystal.core.camera.Camera]).
        """
        return cls(
            position=data["position"],
            focal_point=data["focal_point"],
            view_up=data["view_up"],
            parallel_scale=data["parallel_scale"],
            projection=data.get("projection", "orthographic"),
        )

    def _replace(self, **changes: Any) -> Camera:
        values = {
            "position": self.position,
            "focal_point": self.focal_point,
            "view_up": self.view_up,
            "parallel_scale": self.parallel_scale,
        }
        values.update({k: tuple(v) if isinstance(v, np.ndarray) else v for k, v in changes.items()})
        return Camera(**values)


def default_camera(points: Any, radii: Any, aspect: float) -> Camera:
    """Return the initial view, fitted to the given spheres.

    The view looks along ``(-0.42, 1.0, -0.38)``, slightly from above, with Cartesian
    +z as the up direction. This puts the c axis up only when c points along z, as for
    orthogonal and hexagonal cells read from CIF files (a along x, b in the xy plane).

    Parameters
    ----------
    points
        Sphere centres in Å, shape ``(K, 3)``.
    radii
        Sphere radii in Å: one value or one per sphere.
    aspect
        Output width divided by output height.

    Returns
    -------
    Camera
        The fitted camera (see [`Camera.fitted`][ycrystal.core.camera.Camera.fitted]).
    """
    camera = Camera.looking_along(direction=DEFAULT_DIRECTION, view_up=(0.0, 0.0, 1.0))
    return camera.fitted(points, radii, aspect)


# ----- view policies (FR-CAMERA-01) -------------------------------------------------
DEFAULT_DIRECTION = (-0.42, 1.0, -0.38)
"""Viewing direction of the default view (slightly from above, Cartesian +z up)."""

DEFAULT_MARGIN = 0.06
"""Extra space around fitted views, as a fraction of the fitted half-height."""

VIEWS = ("default", "a", "b", "c", "x", "y", "z")
"""Views of [`ViewPolicy`][ycrystal.core.camera.ViewPolicy]: the default view, the
real-space lattice vectors a, b, c, and the Cartesian axes x, y, z."""

CAMERA_POLICIES = ("saved", "fit")
"""``saved``: use the saved camera as it is; ``fit``: refit the framing to the scene."""


class CameraPolicyError(ValueError):
    """A view or framing cannot be produced; ``str(error)`` is a message for the user."""


def axis_view(axis: str, cell: Any = None, reverse: bool = False) -> tuple[np.ndarray, np.ndarray]:
    """Return ``(viewing direction, view up)`` for looking down a lattice or Cartesian axis.

    The named axis points toward the viewer (away from the viewer with `reverse`), as
    with the view buttons of the window. ``a``, ``b``, ``c`` are the **real-space**
    lattice vectors (the rows of `cell`), not normals of lattice planes (hkl): in a
    non-orthogonal cell, looking down c is not looking at the (001) plane face-on.
    Screen up is the first of c, b, a (or z, y, x) that is not parallel to the viewing
    direction, projected onto the screen; looking down a or b therefore puts c up,
    looking down c puts b up.

    >>> direction, up = axis_view("c", np.diag([3.0, 3.0, 5.0]))
    >>> direction.tolist(), up.tolist()
    ([-0.0, -0.0, -1.0], [0.0, 3.0, 0.0])

    Raises
    ------
    CameraPolicyError
        If `axis` is not one of a, b, c, x, y, z, or a lattice axis is requested for
        a structure without a cell (`cell` is ``None`` or has a zero-length vector).
    """
    if axis in ("a", "b", "c"):
        vectors = None if cell is None else np.asarray(cell, dtype=float).reshape(3, 3)
        if vectors is None or np.any(np.linalg.norm(vectors, axis=1) < 1e-9):
            raise CameraPolicyError(
                f"The view along {axis} needs a lattice, and this structure has no cell; "
                "use x, y, z, or default."
            )
        toward = vectors["abc".index(axis)]
        ups = [vectors[2], vectors[1], vectors[0]]
    elif axis in ("x", "y", "z"):
        toward = np.eye(3)["xyz".index(axis)]
        ups = list(np.eye(3)[::-1])
    else:
        raise CameraPolicyError(f"Unknown view axis {axis!r}; choose from a, b, c, x, y, z.")
    toward = toward / np.linalg.norm(toward)
    if reverse:
        toward = -toward
    up = next(u for u in ups if np.linalg.norm(np.cross(u / np.linalg.norm(u), toward)) > 1e-3)
    return -toward, up


@dataclass(frozen=True)
class ViewPolicy:
    """How to choose the camera of a figure without a window.

    Attributes
    ----------
    camera
        ``"saved"`` keeps a saved camera exactly; ``"fit"`` refits the framing (centre
        and scale) to the scene, keeping the saved orientation unless `view` is set.
        ``None`` (the default) means ``"fit"`` when `view` or `visible_height` is set,
        and ``"saved"`` otherwise.
    view
        Orientation: ``"default"``, ``"a"``, ``"b"``, ``"c"``, ``"x"``, ``"y"``, or
        ``"z"`` (see [`axis_view`][ycrystal.core.camera.axis_view]); ``None`` keeps the
        saved orientation, or the default view if there is no saved camera.
    margin
        Extra space around a fitted view as a fraction of its half-height (0–1).
    visible_height
        Fixed visible height of the image in Å instead of fitting the scale, so that
        figures of different structures share one physical scale. The scene is still
        centred. If the scene does not fit, that is an error, never a silent crop.

    Raises
    ------
    CameraPolicyError
        If a value is out of range, or ``camera="saved"`` is combined with `view` or
        `visible_height` (they change the camera).

    Examples
    --------
    Without options the saved camera is used unchanged; without a saved camera, the
    default view is fitted, exactly as before this policy existed:

    >>> points, radii = np.array([[0.0, 0.0, 0.0], [4.0, 0.0, 0.0]]), 1.0
    >>> ViewPolicy().resolve(None, points, radii, 1.5) == default_camera(points, radii, 1.5)
    True
    >>> along_x = ViewPolicy(view="x").resolve(None, points, radii, 1.5)
    >>> [float(v) for v in along_x.basis()[2]]
    [-1.0, 0.0, 0.0]
    """

    camera: str | None = None
    view: str | None = None
    margin: float = DEFAULT_MARGIN
    visible_height: float | None = None

    def __post_init__(self) -> None:
        if self.camera is not None and self.camera not in CAMERA_POLICIES:
            raise CameraPolicyError(
                f"Unknown camera policy {self.camera!r}; choose from {', '.join(CAMERA_POLICIES)}."
            )
        if self.view is not None and self.view not in VIEWS:
            raise CameraPolicyError(f"Unknown view {self.view!r}; choose from {', '.join(VIEWS)}.")
        if not (math.isfinite(self.margin) and 0.0 <= self.margin <= 1.0):
            raise CameraPolicyError("The fit margin must be between 0 and 1.")
        if self.visible_height is not None and not (
            math.isfinite(self.visible_height) and self.visible_height > 0
        ):
            raise CameraPolicyError("The visible height must be a positive number of Å.")
        if self.camera == "saved" and (self.view is not None or self.visible_height is not None):
            raise CameraPolicyError(
                "A view or a visible height replaces the saved camera, so it cannot be "
                "combined with the saved camera policy; use the fit policy or leave it out."
            )

    @property
    def policy(self) -> str:
        """Return the effective policy, ``"saved"`` or ``"fit"``."""
        if self.camera is not None:
            return self.camera
        return "fit" if self.view is not None or self.visible_height is not None else "saved"

    def resolve(
        self,
        saved: Camera | None,
        points: Any,
        radii: Any,
        aspect: float,
        cell: Any = None,
        region: tuple[float, float, float, float] | None = None,
    ) -> Camera:
        """Return the camera for a scene.

        Parameters
        ----------
        saved
            The project's saved camera, or ``None`` (a structure file).
        points, radii
            Framing bounds of the scene, from
            [`DisplayGeometry.points_and_radii`][ycrystal.core.scene.DisplayGeometry.points_and_radii]:
            atoms, cell edges, and whole vector arrows.
        aspect
            Output width divided by height.
        cell
            Lattice vectors as rows, or ``None`` without a cell (for a, b, c).
        region
            Part of the frame a fitted scene must stay in, for example beside an element
            legend (see [`Camera.fitted`][ycrystal.core.camera.Camera.fitted]); ``None``
            is the whole frame. A saved camera is never changed by it.

        Returns
        -------
        Camera
            The saved camera itself with the ``saved`` policy; otherwise a fitted
            camera. The structure is never moved or rotated: only the camera changes.

        Raises
        ------
        CameraPolicyError
            If a lattice view is requested without a cell, or the scene does not fit in
            `visible_height`.
        """
        if self.policy == "saved" and saved is not None:
            return saved
        if self.view is not None and self.view != "default":
            direction, up = axis_view(self.view, cell)
            base = Camera.looking_along(direction, up)
        elif self.view is None and saved is not None:
            base = saved
        else:
            base = Camera.looking_along(DEFAULT_DIRECTION, (0.0, 0.0, 1.0))
        if self.visible_height is None:
            return base.fitted(points, radii, aspect, self.margin, region)
        left, top, right, bottom = region or (0.0, 0.0, 1.0, 1.0)
        inner = (right - left) / (bottom - top)
        tight = base.fitted(points, radii, aspect * inner, margin=0.0)
        needed = 2.0 * tight.parallel_scale / (bottom - top)
        if self.visible_height < needed * (1.0 - 1e-9):
            raise CameraPolicyError(
                f"The scene does not fit in a visible height of {self.visible_height:g} Å at "
                f"this aspect ratio: it needs at least {needed:.2f} Å. Increase the visible "
                "height, or let the view be fitted."
            )
        fixed = tight._replace(parallel_scale=0.5 * self.visible_height * (bottom - top))
        return fixed if region is None else fixed.placed_in(region, aspect)


def _check_size(width: int, height: int) -> None:
    if width <= 0 or height <= 0:
        raise ValueError("image dimensions must be positive")
