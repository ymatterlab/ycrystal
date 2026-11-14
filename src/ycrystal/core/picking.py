"""Pick the displayed sphere under a pixel, using the shared orthographic camera model.

Computed analytically (ray–sphere intersection), so picking does not depend on the
renderer and can be tested without a window.
"""

from __future__ import annotations

import numpy as np

from ycrystal.core.camera import Camera


def pick_sphere(
    camera: Camera,
    width: int,
    height: int,
    pixel: tuple[float, float],
    centers: np.ndarray,
    radii: np.ndarray,
) -> int | None:
    """Index of the front-most sphere covering ``pixel`` (top-left origin), or None."""
    centers = np.asarray(centers, dtype=float).reshape(-1, 3)
    radii = np.asarray(radii, dtype=float).reshape(-1)
    if len(centers) == 0:
        return None
    right, up, direction = camera.basis()
    per_angstrom = camera.pixels_per_angstrom(height)
    x = (pixel[0] - width / 2.0) / per_angstrom
    y = (height / 2.0 - pixel[1]) / per_angstrom
    origin = np.asarray(camera.focal_point) + x * right + y * up  # the ray: origin + t * d
    rel = centers - origin
    along = rel @ direction
    off_axis_sq = np.einsum("ij,ij->i", rel, rel) - along**2
    hit = off_axis_sq <= radii**2
    if not np.any(hit):
        return None
    entry = np.where(hit, along - np.sqrt(np.clip(radii**2 - off_axis_sq, 0.0, None)), np.inf)
    return int(np.argmin(entry))
