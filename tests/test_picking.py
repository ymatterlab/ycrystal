import numpy as np

from ycrystal.core.camera import Camera
from ycrystal.core.picking import pick_sphere


def top_camera(scale: float = 5.0) -> Camera:
    return Camera(position=(0, 0, 10), focal_point=(0, 0, 0), view_up=(0, 1, 0),
                  parallel_scale=scale)


def test_pick_front_most_sphere_and_misses():
    camera = top_camera()  # 400 x 200 px: 20 px per angstrom, centre at (200, 100)
    centers = np.array([[0, 0, -3.0], [0, 0, 0.0], [3, 0, 0]])
    radii = np.array([1.0, 1.0, 0.5])
    assert pick_sphere(camera, 400, 200, (200, 100), centers, radii) == 1  # nearer to eye
    assert pick_sphere(camera, 400, 200, (200 + 0.9 * 20, 100), centers, radii) == 1
    assert pick_sphere(camera, 400, 200, (200 + 1.1 * 20, 100), centers, radii) is None
    assert pick_sphere(camera, 400, 200, (260, 100), centers, radii) == 2
    assert pick_sphere(camera, 400, 200, (5, 5), centers, radii) is None
    assert pick_sphere(camera, 400, 200, (200, 100), np.zeros((0, 3)), np.zeros(0)) is None


def test_pick_matches_projection_for_rotated_panned_view(spread):
    from conftest import off_axis_camera

    width, height = 500, 320
    camera = off_axis_camera(spread, width / height)
    pixels = camera.project(spread.positions, width, height)
    for index, pixel in enumerate(pixels):
        assert pick_sphere(camera, width, height, tuple(pixel), spread.positions,
                           spread.radii) == index
