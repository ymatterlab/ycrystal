import json
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest
from vtkmodules.vtkRenderingCore import vtkCamera

from ycrystal.batch import load_input
from ycrystal.core.camera import (
    DEFAULT_MARGIN,
    Camera,
    CameraPolicyError,
    ViewPolicy,
    axis_view,
    default_camera,
)
from ycrystal.core.scene import build_geometry


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


def test_rotate_about_axis_keeps_axis_fixed_on_screen():
    from ycrystal.core.camera import Camera

    camera = Camera.looking_along((0.3, -1.0, -0.4), (0, 0, 1), parallel_scale=4.0).orbit(
        azimuth=20, elevation=10
    )
    axis = np.array([0.2, 0.5, 1.0])
    turned = camera.rotate_about(axis, 37.0)
    before = np.array(camera.basis()) @ (axis / np.linalg.norm(axis))
    after = np.array(turned.basis()) @ (axis / np.linalg.norm(axis))
    np.testing.assert_allclose(after, before, atol=1e-12)  # the axis does not move on screen
    assert turned.distance == pytest.approx(camera.distance)
    assert turned.parallel_scale == camera.parallel_scale
    assert turned.focal_point == camera.focal_point
    # The scene appears rotated by +37°: each point shows up where its rotated image
    # appeared before.
    point = np.array([[1.3, -0.4, 0.8]])
    k = axis / np.linalg.norm(axis)
    theta = np.radians(37.0)
    rotated = (
        point * np.cos(theta)
        + np.cross(k, point) * np.sin(theta)
        + np.outer(point @ k, k) * (1 - np.cos(theta))
    )
    np.testing.assert_allclose(
        turned.project(point, 400, 300), camera.project(rotated, 400, 300), atol=1e-9
    )
    back = turned.rotate_about(axis, -37.0)
    np.testing.assert_allclose(back.position, camera.position, atol=1e-9)
    with pytest.raises(ValueError):
        camera.rotate_about((0, 0, 0), 10)


# ----- view policies (FR-CAMERA-01) -----------------------------------------------------
ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"


def scene_of(name, repetitions=(1, 1, 1)):
    project = load_input(FIXTURES / name if "/" not in name else ROOT / name)
    geometry = build_geometry(project.structure, replace(project.scene, repetitions=repetitions))
    return project, geometry


def assert_inside(camera, geometry, width, height, margin_px=0.0):
    """Every sphere of the framing bounds lies completely inside the image."""
    points, radii = geometry.points_and_radii()
    pixels = camera.project(points, width, height)
    r = np.broadcast_to(radii, (len(points),)) * camera.pixels_per_angstrom(height)
    assert np.all(pixels[:, 0] - r >= -1e-6 - margin_px)
    assert np.all(pixels[:, 0] + r <= width + 1e-6 + margin_px)
    assert np.all(pixels[:, 1] - r >= -1e-6 - margin_px)
    assert np.all(pixels[:, 1] + r <= height + 1e-6 + margin_px)


def test_axis_view_conventions():
    cubic = np.diag([4.0, 4.0, 4.0])
    for axis, direction, up in (
        ("a", (-1, 0, 0), (0, 0, 4)),
        ("b", (0, -1, 0), (0, 0, 4)),
        ("c", (0, 0, -1), (0, 4, 0)),
        ("x", (-1, 0, 0), (0, 0, 1)),
        ("y", (0, -1, 0), (0, 0, 1)),
        ("z", (0, 0, -1), (0, 1, 0)),
    ):
        d, u = axis_view(axis, cubic)
        np.testing.assert_allclose(d, direction, atol=1e-12)
        np.testing.assert_allclose(u, up, atol=1e-12)
    d, _ = axis_view("a", cubic, reverse=True)
    np.testing.assert_allclose(d, (1, 0, 0), atol=1e-12)
    # Triclinic: the real-space vector, not a plane normal.
    project, _ = scene_of("triclinic.cif")
    cell = project.structure.cell
    for index, axis in enumerate("abc"):
        d, u = axis_view(axis, cell)
        np.testing.assert_allclose(-d, cell[index] / np.linalg.norm(cell[index]), atol=1e-12)
        assert np.linalg.norm(np.cross(d, u / np.linalg.norm(u))) > 1e-3
    # Cartesian views need no cell; lattice views do.
    assert axis_view("z", None)[0].tolist() == [-0.0, -0.0, -1.0]
    for cell in (None, np.zeros((3, 3))):
        with pytest.raises(CameraPolicyError, match="has no cell"):
            axis_view("a", cell)
    with pytest.raises(CameraPolicyError, match="Unknown view axis"):
        axis_view("w", np.eye(3))


def test_without_options_nothing_changes():
    _, geometry = scene_of("MgB2.cif")
    points, radii = geometry.points_and_radii()
    saved = Camera((1, 2, 30), (1, 2, 0), (0, 1, 0), parallel_scale=7.0)
    policy = ViewPolicy()
    assert policy.policy == "saved" and policy.resolve(saved, points, radii, 1.5) is saved
    assert policy.resolve(None, points, radii, 1.5) == default_camera(points, radii, 1.5)
    assert ViewPolicy(camera="saved").resolve(saved, points, radii, 1.5) is saved
    # Repeated runs give the same camera.
    view = ViewPolicy(view="c")
    cell = scene_of("MgB2.cif")[0].structure.cell
    assert view.resolve(None, points, radii, 1.5, cell) == view.resolve(
        None, points, radii, 1.5, cell
    )


def test_fit_policy_refits_a_saved_camera_and_keeps_its_orientation():
    _, geometry = scene_of("SrTiO3.cif", (3, 2, 1))
    points, radii = geometry.points_and_radii()
    saved = Camera.looking_along((0.3, 1.0, -0.2), (0, 0, 1), parallel_scale=1.0)  # far too tight
    fitted = ViewPolicy(camera="fit").resolve(saved, points, radii, 1.5)
    for a, b in zip(fitted.basis(), saved.basis(), strict=True):
        np.testing.assert_allclose(a, b, atol=1e-12)  # same orientation
    assert fitted.parallel_scale > 5 * saved.parallel_scale
    assert_inside(fitted, geometry, 600, 400)


@pytest.mark.parametrize("name", ["SrTiO3.cif", "MgB2.cif", "triclinic.cif"])
@pytest.mark.parametrize("view", ["default", "a", "b", "c", "x", "y", "z"])
@pytest.mark.parametrize("size", [(800, 600), (400, 900), (500, 500)])
@pytest.mark.parametrize("repetitions", [(1, 1, 1), (3, 2, 1)])
def test_fitted_views_never_clip(name, view, size, repetitions):
    project, geometry = scene_of(name, repetitions)
    positions = project.structure.positions.copy()
    points, radii = geometry.points_and_radii()
    width, height = size
    camera = ViewPolicy(view=view, margin=0.0).resolve(
        None, points, radii, width / height, project.structure.cell
    )
    assert_inside(camera, geometry, width, height)
    np.testing.assert_array_equal(project.structure.positions, positions)  # camera only


def test_fitted_views_include_whole_vector_arrows():
    project = load_input(ROOT / "examples" / "vectors-synthetic-afm.ycrystal")
    geometry = build_geometry(project.structure, project.scene)
    assert len(geometry.arrows) > 0
    points, radii = geometry.points_and_radii()
    for view in ("c", "a", "x"):
        camera = ViewPolicy(view=view, margin=0.0).resolve(
            project.camera, points, radii, 0.75, project.structure.cell
        )
        assert_inside(camera, geometry, 600, 800)
        tips = np.array([arrow.tip for arrow in geometry.arrows])
        pixels = camera.project(tips, 600, 800)
        assert np.all((pixels >= -1e-6) & (pixels <= np.array([600, 800]) + 1e-6))


def test_margin_and_fixed_visible_height():
    _, geometry = scene_of("SrTiO3.cif")
    points, radii = geometry.points_and_radii()
    tight = ViewPolicy(view="a", margin=0.0).resolve(None, points, radii, 1.0, np.eye(3) * 3.905)
    loose = ViewPolicy(view="a", margin=0.5).resolve(None, points, radii, 1.0, np.eye(3) * 3.905)
    assert loose.parallel_scale == pytest.approx(1.5 * tight.parallel_scale)
    assert ViewPolicy(view="a").margin == DEFAULT_MARGIN == 0.06
    needed = 2 * tight.parallel_scale
    fixed = ViewPolicy(view="a", visible_height=20.0).resolve(
        None, points, radii, 1.0, np.eye(3) * 3.905
    )
    assert fixed.parallel_scale == 10.0 and fixed.focal_point == tight.focal_point
    assert ViewPolicy(visible_height=20.0).policy == "fit"
    with pytest.raises(CameraPolicyError, match=f"needs at least {needed:.2f} Å"):
        ViewPolicy(view="a", visible_height=needed * 0.9).resolve(
            None, points, radii, 1.0, np.eye(3) * 3.905
        )
    # Exactly the needed height is accepted (nothing clipped, no margin).
    exact = ViewPolicy(view="a", visible_height=needed).resolve(
        None, points, radii, 1.0, np.eye(3) * 3.905
    )
    assert_inside(exact, geometry, 500, 500)


@pytest.mark.parametrize(
    "kwargs, message",
    [
        ({"camera": "keep"}, "Unknown camera policy"),
        ({"view": "d"}, "Unknown view"),
        ({"margin": -0.1}, "between 0 and 1"),
        ({"margin": float("nan")}, "between 0 and 1"),
        ({"visible_height": 0.0}, "positive"),
        ({"camera": "saved", "view": "a"}, "replaces the saved camera"),
        ({"camera": "saved", "visible_height": 10.0}, "replaces the saved camera"),
    ],
)
def test_invalid_policies_are_refused(kwargs, message):
    with pytest.raises(CameraPolicyError, match=message):
        ViewPolicy(**kwargs)
