"""Renderer-independent orthographic camera.

Conventions (shared by the VTK viewport and the POV-Ray writer):

* World coordinates are right-handed Cartesian ångström.
* ``direction`` d = normalize(focal_point - position) is the viewing direction.
* Screen right r = normalize(d x view_up); screen up u = r x d. These match VTK's
  camera; (r, u, -d) is a right-handed basis.
* ``parallel_scale`` is half of the visible height in ångström (VTK's definition).
  The visible width follows from the output aspect ratio: 2 * parallel_scale * W / H.
* Pixel coordinates are continuous, origin at the top-left image corner, x to the
  right and y downward; the centre of pixel (i, j) is (i + 0.5, j + 0.5).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import numpy as np

Vec3 = tuple[float, float, float]


def _vec(value: Any) -> Vec3:
    array = np.asarray(value, dtype=float).reshape(3)
    if not np.all(np.isfinite(array)):
        raise ValueError(f"non-finite vector: {value!r}")
    return (float(array[0]), float(array[1]), float(array[2]))


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
        return float(np.linalg.norm(np.subtract(self.focal_point, self.position)))

    def basis(self) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Return orthonormal (right, up, direction) vectors."""
        d = np.subtract(self.focal_point, self.position)
        d = d / np.linalg.norm(d)
        r = np.cross(d, self.view_up)
        r = r / np.linalg.norm(r)
        u = np.cross(r, d)
        return r, u, d

    def visible_size(self, width: int, height: int) -> tuple[float, float]:
        """Visible (width, height) in ångström for an image of ``width`` x ``height`` px."""
        _check_size(width, height)
        return 2.0 * self.parallel_scale * width / height, 2.0 * self.parallel_scale

    def project(self, points: Any, width: int, height: int) -> np.ndarray:
        """Project world points to continuous pixel coordinates (top-left origin)."""
        _check_size(width, height)
        pts = np.asarray(points, dtype=float).reshape(-1, 3)
        r, u, _ = self.basis()
        rel = pts - np.asarray(self.focal_point)
        pixels_per_unit = height / (2.0 * self.parallel_scale)
        x = width / 2.0 + (rel @ r) * pixels_per_unit
        y = height / 2.0 - (rel @ u) * pixels_per_unit
        return np.column_stack([x, y])

    def pixels_per_angstrom(self, height: int) -> float:
        return height / (2.0 * self.parallel_scale)

    # ----- pure navigation helpers (used by scripted views and checks) ----------
    def orbit(self, azimuth: float = 0.0, elevation: float = 0.0) -> Camera:
        """Rotate the position about the focal point.

        ``azimuth`` turns about the screen-up axis, ``elevation`` about the screen-right
        axis (degrees), like VTK's Azimuth/Elevation.
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
        _, u, d = self.basis()
        return self._replace(view_up=_rotate(u, d, angle))

    def pan(self, dx: float, dy: float) -> Camera:
        """Move position and focal point by (dx, dy) ångström in the screen plane."""
        r, u, _ = self.basis()
        shift = dx * r + dy * u
        return self._replace(
            position=np.asarray(self.position) + shift,
            focal_point=np.asarray(self.focal_point) + shift,
        )

    def zoom(self, factor: float) -> Camera:
        if factor <= 0:
            raise ValueError("zoom factor must be positive")
        return self._replace(parallel_scale=self.parallel_scale / factor)

    def fitted(
        self, points: Any, radii: Any, aspect: float, margin: float = 0.06
    ) -> Camera:
        """Keep the orientation; centre and scale so every sphere is visible.

        ``aspect`` is the output width / height.
        """
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

    @classmethod
    def looking_along(
        cls, direction: Any, view_up: Any, focal_point: Any = (0, 0, 0), distance: float = 50.0,
        parallel_scale: float = 10.0,
    ) -> Camera:
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
        return {
            "projection": self.projection,
            "position": list(self.position),
            "focal_point": list(self.focal_point),
            "view_up": list(self.view_up),
            "parallel_scale": self.parallel_scale,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Camera:
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
    """A slightly off-axis view (c axis up) that fits the given spheres."""
    camera = Camera.looking_along(direction=(-0.42, 1.0, -0.38), view_up=(0.0, 0.0, 1.0))
    return camera.fitted(points, radii, aspect)


def _check_size(width: int, height: int) -> None:
    if width <= 0 or height <= 0:
        raise ValueError("image dimensions must be positive")
