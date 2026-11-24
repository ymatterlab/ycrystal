"""Pick displayed spheres and bond cylinders with the orthographic camera model.

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
    origin, direction = _view_ray(camera, width, height, pixel)
    entry = _sphere_entries(origin, direction, centers, radii)
    index = int(np.argmin(entry))
    return index if np.isfinite(entry[index]) else None


def _view_ray(camera, width, height, pixel):
    right, up, direction = camera.basis()
    per_angstrom = camera.pixels_per_angstrom(height)
    x = (pixel[0] - width / 2.0) / per_angstrom
    y = (height / 2.0 - pixel[1]) / per_angstrom
    origin = np.asarray(camera.focal_point) + x * right + y * up
    return origin, direction


def _sphere_entries(origin, direction, centers, radii):
    rel = centers - origin
    along = rel @ direction
    off_axis_sq = np.einsum("ij,ij->i", rel, rel) - along**2
    gap = radii**2 - off_axis_sq
    return np.where(gap >= 0, along - np.sqrt(np.maximum(gap, 0)), np.inf)


def pick_bond(
    camera: Camera,
    width: int,
    height: int,
    pixel: tuple[float, float],
    centers: np.ndarray,
    radii: np.ndarray,
    bonds: np.ndarray,
    radius: float,
    cushion_pixels: float = 0.0,
) -> int | None:
    """Return the nearest bond cylinder under the pointer and in front of any atom.

    Each bond indexes two atom centres. A thin bond can also be picked within
    `cushion_pixels` of its centre line if the ray misses every exposed cylinder.
    Atoms still block padded hits. A ray intersection includes cylinder end caps.
    """
    if not len(bonds):
        return None
    centers = np.asarray(centers, dtype=float)
    radii = np.asarray(radii, dtype=float)
    origin, direction = _view_ray(camera, width, height, pixel)
    atom_entry = _sphere_entries(origin, direction, centers, radii).min(initial=np.inf)
    starts, ends = centers[bonds[:, 0]], centers[bonds[:, 1]]
    vector = ends - starts
    lengths = np.linalg.norm(vector, axis=1)
    axes = np.divide(
        vector, lengths[:, None], out=np.zeros_like(vector), where=lengths[:, None] > 0
    )
    offset = origin - starts
    axial_origin = np.einsum("ij,ij->i", offset, axes)
    axial_direction = axes @ direction
    radial_origin = offset - axial_origin[:, None] * axes
    radial_direction = direction - axial_direction[:, None] * axes
    a = np.einsum("ij,ij->i", radial_direction, radial_direction)
    b = np.einsum("ij,ij->i", radial_direction, radial_origin)
    radial_sq = np.einsum("ij,ij->i", radial_origin, radial_origin)

    # Intersect the infinite cylinder's radial interval with its finite axial interval.
    axial_parallel = np.abs(axial_direction) < 1e-12
    safe_axial = np.where(axial_parallel, 1.0, axial_direction)
    first, last = -axial_origin / safe_axial, (lengths - axial_origin) / safe_axial
    axial_near = np.where(axial_parallel, -np.inf, np.minimum(first, last))
    axial_far = np.where(axial_parallel, np.inf, np.maximum(first, last))
    axial_hit = ~axial_parallel | ((axial_origin >= 0) & (axial_origin <= lengths))
    radial_parallel = a < 1e-24
    safe_radial = np.where(radial_parallel, 1.0, a)

    padded = cushion_pixels / camera.pixels_per_angstrom(height)
    hit_radii = (radius, padded) if padded > radius else (radius,)
    for hit_radius in hit_radii:
        c = radial_sq - hit_radius**2
        discriminant = b**2 - a * c
        root = np.sqrt(np.maximum(discriminant, 0.0))
        radial_near = np.where(radial_parallel, -np.inf, (-b - root) / safe_radial)
        radial_far = np.where(radial_parallel, np.inf, (-b + root) / safe_radial)
        radial_hit = np.where(radial_parallel, c <= 0, discriminant >= 0)
        near, far = np.maximum(axial_near, radial_near), np.minimum(axial_far, radial_far)
        entries = np.where(axial_hit & radial_hit & (near <= far) & (lengths > 0), near, np.inf)
        index = int(np.argmin(entries))
        if entries[index] < atom_entry:
            return index
    return None
