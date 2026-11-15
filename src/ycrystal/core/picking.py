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
    """Return the front-most sphere under a pixel.

    The viewing ray through `pixel` is parallel to the viewing direction (orthographic
    projection) and is intersected analytically with every sphere.

    Parameters
    ----------
    camera
        Camera of the view.
    width
        Image width in pixels (device pixels in the GUI).
    height
        Image height in pixels.
    pixel
        Continuous pixel coordinates ``(x, y)`` with the origin at the top-left corner,
        x to the right, and y downward, as returned by
        [`Camera.project`][ycrystal.core.camera.Camera.project].
    centers
        Sphere centres in Å, shape ``(K, 3)``.
    radii
        Sphere radii in Å, shape ``(K,)``.

    Returns
    -------
    int or None
        Index into `centers` of the sphere whose surface the ray meets first, coming
        from the viewer's side, or ``None`` if the ray misses every sphere.

    Examples
    --------
    Two unit spheres on the viewing axis; the one nearer the eye (at +z) is picked:

    >>> import numpy as np
    >>> from ycrystal.core.camera import Camera
    >>> from ycrystal.core.picking import pick_sphere
    >>> camera = Camera(
    ...     position=(0, 0, 10), focal_point=(0, 0, 0), view_up=(0, 1, 0), parallel_scale=5.0
    ... )
    >>> centers = np.array([[0.0, 0.0, -3.0], [0.0, 0.0, 0.0]])
    >>> pick_sphere(camera, 400, 200, (200.0, 100.0), centers, np.array([1.0, 1.0]))
    1
    >>> pick_sphere(camera, 400, 200, (5.0, 5.0), centers, np.array([1.0, 1.0])) is None
    True
    """
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
