import json

import numpy as np
import pytest
from vtkmodules.vtkRenderingCore import vtkCamera

from ycrystal.core.camera import Camera, default_camera


def simple_camera(scale: float = 5.0) -> Camera:
    # Eye on +z looking at the origin, y up: screen right = +x, screen up = +y.
    return Camera(
        position=(0, 0, 10), focal_point=(0, 0, 0), view_up=(0, 1, 0), parallel_scale=scale
    )


def test_basis_is_orthonormal_and_right_handed():
    camera = Camera(
        position=(3, -7, 2), focal_point=(0.5, 1, -1), view_up=(0.2, 0.1, 1), parallel_scale=4
    )
    r, u, d = camera.basis()
    np.testing.assert_allclose(np.array([r, u, d]) @ np.array([r, u, d]).T, np.eye(3), atol=1e-12)
    assert np.dot(np.cross(r, u), -d) == pytest.approx(1.0)


def test_projection_axes_and_non_square_extent():
    camera = simple_camera(scale=5.0)
    width, height = 400, 200  # 2:1 output, visible 20 x 10 angstrom
    assert camera.visible_size(width, height) == (20.0, 10.0)
    pixels = camera.project(
        [(0, 0, 0), (1, 0, 0), (0, 1, 0), (10, 5, 0), (-10, -5, 3)], width, height
    )
    np.testing.assert_allclose(pixels, [(200, 100), (220, 100), (200, 80), (400, 0), (0, 200)])


def test_pan_moves_the_scene_opposite_to_the_camera():
    camera = simple_camera()
    width, height = 300, 200
    k = camera.pixels_per_angstrom(height)
    before = camera.project([(1, 2, 3)], width, height)[0]
    after = camera.pan(0.5, -0.25).project([(1, 2, 3)], width, height)[0]
    np.testing.assert_allclose(after - before, (-0.5 * k, -0.25 * k))


def test_orbit_keeps_focal_point_distance_and_projects_focal_to_centre():
    camera = simple_camera().pan(1, 2)
    turned = camera.orbit(azimuth=33, elevation=-21).roll(12)
    np.testing.assert_allclose(turned.focal_point, camera.focal_point)
    assert turned.distance == pytest.approx(camera.distance)
    np.testing.assert_allclose(turned.project([turned.focal_point], 640, 360), [(320, 180)])
    back = camera.orbit(azimuth=360)
    np.testing.assert_allclose(back.position, camera.position, atol=1e-9)


def test_orbit_directions_match_vtk_conventions():
    # Signs and axes must agree with vtkCamera.Azimuth/Elevation (screen-up / screen-right
    # axes through the focal point), so scripted views mean the same in both places.
    camera = Camera(
        position=(2, -9, 3), focal_point=(0.3, 0.2, -0.1), view_up=(0, 0, 1), parallel_scale=3
    )
    for azimuth, elevation in ((25, 0), (0, 25), (-40, 15)):
        vtk_cam = vtkCamera()
        vtk_cam.SetPosition(*camera.position)
        vtk_cam.SetFocalPoint(*camera.focal_point)
        vtk_cam.SetViewUp(*camera.view_up)
        vtk_cam.OrthogonalizeViewUp()  # Camera.orbit turns about the orthogonalised up axis
        vtk_cam.Azimuth(azimuth)
        vtk_cam.Elevation(elevation)
        vtk_cam.OrthogonalizeViewUp()
        ours = camera.orbit(azimuth=azimuth, elevation=elevation)
        np.testing.assert_allclose(ours.position, vtk_cam.GetPosition(), atol=1e-9)
        np.testing.assert_allclose(ours.basis()[1], vtk_cam.GetViewUp(), atol=1e-9)


def test_zoom_and_fit():
    camera = simple_camera(scale=5.0)
    assert camera.zoom(2.0).parallel_scale == pytest.approx(2.5)
    points = np.array([(0, 0, 0), (4, 1, -2), (-1, 3, 1)])
    radii = np.array([0.5, 0.3, 0.4])
    turned = camera.orbit(azimuth=40, elevation=25)
    width, height = 500, 300
    fitted = turned.fitted(points, radii, width / height, margin=0.0)
    np.testing.assert_allclose(fitted.basis()[2], turned.basis()[2], atol=1e-12)
    pixels = fitted.project(points, width, height)
    k = fitted.pixels_per_angstrom(height)
    lo = (pixels - radii[:, None] * k).min(axis=0)
    hi = (pixels + radii[:, None] * k).max(axis=0)
    assert np.all(lo >= -1e-6) and hi[0] <= width + 1e-6 and hi[1] <= height + 1e-6
    # Tight in at least one direction when margin is zero.
    assert min(lo.min(), width - hi[0], height - hi[1]) == pytest.approx(0, abs=1e-6)


def test_default_camera_fits_and_has_c_axis_up():
    points = np.random.default_rng(1).normal(size=(10, 3))
    camera = default_camera(points, 0.3, 1.6)
    assert camera.basis()[1][2] > 0.8


def test_serialisation_round_trip():
    camera = simple_camera().orbit(azimuth=10, elevation=20).pan(0.3, 0.1)
    data = json.loads(json.dumps(camera.to_dict()))
    assert Camera.from_dict(data) == camera


def test_invalid_cameras_are_rejected():
    with pytest.raises(ValueError):
        Camera(position=(0, 0, 1), focal_point=(0, 0, 0), view_up=(0, 0, 1), parallel_scale=1)
    with pytest.raises(ValueError):
        Camera(position=(0, 0, 0), focal_point=(0, 0, 0), view_up=(0, 1, 0), parallel_scale=1)
    with pytest.raises(ValueError):
        Camera(position=(0, 0, 1), focal_point=(0, 0, 0), view_up=(0, 1, 0), parallel_scale=0)
    with pytest.raises(ValueError):
        Camera(
            position=(0, 0, 1),
            focal_point=(0, 0, 0),
            view_up=(0, 1, 0),
            parallel_scale=1,
            projection="perspective",
        )


@pytest.mark.parametrize("seed", range(5))
def test_projection_matches_vtk_camera_matrices(seed):
    """Our projection equals VTK's composite projection for random orthographic views."""
    rng = np.random.default_rng(seed)
    position = rng.normal(size=3) * 10
    focal = rng.normal(size=3)
    up = rng.normal(size=3)
    scale = float(rng.uniform(1, 8))
    width, height = int(rng.integers(100, 900)), int(rng.integers(100, 900))
    camera = Camera(position=position, focal_point=focal, view_up=up, parallel_scale=scale)

    vtk_cam = vtkCamera()
    vtk_cam.ParallelProjectionOn()
    vtk_cam.SetPosition(*position)
    vtk_cam.SetFocalPoint(*focal)
    vtk_cam.SetViewUp(*up)
    vtk_cam.SetParallelScale(scale)
    vtk_cam.SetClippingRange(0.1, 1000)
    matrix = vtk_cam.GetCompositeProjectionTransformMatrix(width / height, -1, 1)
    m = np.array([[matrix.GetElement(i, j) for j in range(4)] for i in range(4)])

    points = rng.normal(size=(20, 3)) * 4
    homogeneous = np.column_stack([points, np.ones(len(points))]) @ m.T
    ndc = homogeneous[:, :3] / homogeneous[:, 3:4]
    vtk_pixels = np.column_stack([(ndc[:, 0] + 1) / 2 * width, (1 - (ndc[:, 1] + 1) / 2) * height])
    np.testing.assert_allclose(camera.project(points, width, height), vtk_pixels, atol=1e-9)
