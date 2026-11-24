"""Pick explicit bond cylinders with the same orthographic camera as the view."""

import numpy as np

from ycrystal.core.camera import Camera
from ycrystal.core.picking import pick_bond

CAMERA = Camera(position=(0, 0, 10), focal_point=(0, 0, 0), view_up=(0, 1, 0), parallel_scale=5)


def test_pick_uses_cylinder_depth_and_stops_at_atoms():
    centers = np.array([[-2, 0, -1], [2, 0, -1], [-2, 0, 1], [2, 0, 1], [0, 0, 2]])
    bonds = np.array([[0, 1], [2, 3]])
    radii = np.array([0.2, 0.2, 0.2, 0.2, 0.0])
    # Pick an exposed spot one Å to the right of the centre.
    assert pick_bond(CAMERA, 400, 200, (220, 100), centers, radii, bonds, 0.1) == 1
    radii[-1] = 0.3
    assert pick_bond(CAMERA, 400, 200, (200, 100), centers, radii, bonds, 0.1) is None
    assert pick_bond(CAMERA, 400, 200, (260, 100), centers, radii, bonds, 0.1) is None


def test_pick_finite_cylinder_cap_and_screen_space_cushion():
    centers = np.array([[0.0, 0, -1], [0.0, 0, 1]])
    radii = np.array([0.05, 0.05])
    bonds = np.array([[0, 1]])
    assert pick_bond(CAMERA, 400, 200, (203, 100), centers, radii, bonds, 0.2) == 0
    assert pick_bond(CAMERA, 400, 200, (205, 100), centers, radii, bonds, 0.1) is None
    assert pick_bond(CAMERA, 400, 200, (205, 100), centers, radii, bonds, 0.1, 6) == 0
