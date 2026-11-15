"""FR-LIGHT-01: the shared lighting rig (pure arithmetic, no Qt or VTK)."""

import re
from dataclasses import replace

import numpy as np
import pytest

from ycrystal.core.camera import Camera
from ycrystal.core.lighting import (
    KEY_ELEVATION_RANGE,
    angles_of,
    arc_points,
    key_direction,
    resolve_lighting,
    wrap_azimuth,
)
from ycrystal.core.samples import perovskite_srtio3
from ycrystal.core.scene import Environment, SceneSettings, build_geometry
from ycrystal.presets import apply_lighting, environment_from_preset, environments, lighting_presets
from ycrystal.render.pov_writer import RenderSettings, scene_to_pov

VEC = r"<\s*([-\d.e]+),\s*([-\d.e]+),\s*([-\d.e]+)\s*>"
DRAMATIC = replace(
    Environment(), key_azimuth=-65.0, key_elevation=25.0, key_light=1.30, fill_light=0.12
)


@pytest.fixture
def srtio3():
    geometry = build_geometry(perovskite_srtio3())
    center, _ = geometry.bounding_sphere()
    camera = Camera(tuple(center + [0, 0, 30]), tuple(center), (0, 1, 0), parallel_scale=4.5)
    return geometry, camera


def light_lines(text):
    return [line for line in text.splitlines() if line.startswith(("light_source", "disc"))]


def in_view(rig, point):
    """(right, up, toward viewer) coordinates of a point relative to F."""
    v = np.asarray(point) - rig.origin
    return np.array([v @ rig.right, v @ rig.up, -(v @ rig.direction)])


# ----- exporter equivalence ------------------------------------------------------------------
def test_reference_example_is_unchanged(srtio3):
    """The numbers of the lighting analysis (written before the extraction)."""
    geometry, camera = srtio3
    rig = resolve_lighting(DRAMATIC, camera, geometry)
    assert rig.radius == pytest.approx(4.3568, abs=1e-4) and rig.distance == pytest.approx(
        27.4273, abs=1e-4
    )
    np.testing.assert_allclose(rig.key.position, (-20.576128, 13.543785, 12.457772), atol=1e-6)
    np.testing.assert_allclose(rig.fill.position, (17.361184, -3.550602, 23.964906), atol=1e-6)
    text = scene_to_pov(
        geometry, camera, replace(DRAMATIC, light_size=0.5), RenderSettings(2400, 1600)
    )
    assert light_lines(text) == [
        "light_source { <-20.576128, 13.543785, 12.457772> color rgb 1.3 area_light "
        "<2.178415, 0, 0>, <0, 2.178415, 0>, 5, 5 adaptive 1 circular orient }",
        "light_source { <17.361184, -3.550602, 23.964906> color rgb 0.12 shadowless }",
    ]


@pytest.mark.parametrize(
    "environment",
    [apply_lighting(Environment(), light.id) for light in lighting_presets()]
    + [environment_from_preset(env.id) for env in environments()]
    + [replace(DRAMATIC, light_size=1.5, reflector=True, shadows=False)],
)
def test_writer_lights_are_the_resolved_rig(srtio3, environment):
    geometry, camera = srtio3
    camera = camera.orbit(azimuth=40, elevation=20).roll(15).pan(1.0, -0.5)
    rig = resolve_lighting(environment, camera, geometry)
    lines = light_lines(scene_to_pov(geometry, camera, environment, RenderSettings(800, 600)))
    expected = [light for light in (rig.key, rig.fill) if light.enabled]
    sources = [line for line in lines if line.startswith("light_source")]
    assert len(sources) == len(expected)
    for line, light in zip(sources, expected, strict=True):
        position = np.array([float(v) for v in re.search(VEC, line).groups()])
        np.testing.assert_allclose(position, light.position, atol=1e-6)
        assert f"color rgb {light.intensity:g}" in line
        assert ("area_light" in line) == light.is_area
        assert ("shadowless" in line) == (not light.shadows)
    assert any(line.startswith("disc") for line in lines) == (rig.panel is not None)


# ----- conventions and interaction -----------------------------------------------------------
def test_angles_follow_the_output_camera(srtio3):
    geometry, camera = srtio3
    front = resolve_lighting(replace(DRAMATIC, key_azimuth=0, key_elevation=0), camera, geometry)
    np.testing.assert_allclose(front.key.direction, -front.direction)  # toward the viewer
    right = resolve_lighting(replace(DRAMATIC, key_azimuth=90, key_elevation=0), camera, geometry)
    np.testing.assert_allclose(right.key.direction, right.right, atol=1e-12)
    up = resolve_lighting(replace(DRAMATIC, key_azimuth=0, key_elevation=89), camera, geometry)
    assert up.key.direction @ up.up > 0.999
    base = resolve_lighting(DRAMATIC, camera, geometry)
    for moved in (camera.orbit(azimuth=50, elevation=-30), camera.roll(35)):
        rig = resolve_lighting(DRAMATIC, moved, geometry)
        assert not np.allclose(rig.key.position, base.key.position)  # world positions move
        np.testing.assert_allclose(in_view(rig, rig.key.position), in_view(base, base.key.position))
        np.testing.assert_allclose(
            in_view(rig, rig.fill.position), in_view(base, base.fill.position)
        )
        assert rig.distance == pytest.approx(base.distance)


def test_pan_zoom_and_output_size(srtio3):
    geometry, camera = srtio3
    base = resolve_lighting(DRAMATIC, camera, geometry)
    zoomed = resolve_lighting(DRAMATIC, camera.zoom(3.0), geometry)
    np.testing.assert_array_equal(zoomed.key.position, base.key.position)  # no zoom effect
    panned_camera = camera.pan(2.0, 0.0)
    panned = resolve_lighting(DRAMATIC, panned_camera, geometry)
    offset = np.linalg.norm(panned.center - panned.origin)
    assert offset > 1.5 and panned.distance == pytest.approx(base.distance + offset)
    np.testing.assert_allclose(panned.origin, panned_camera.focal_point)  # origin is F, not C
    a = scene_to_pov(geometry, camera, DRAMATIC, RenderSettings(2400, 1600))
    b = scene_to_pov(geometry, camera, DRAMATIC, RenderSettings(1000, 1000))
    assert light_lines(a) == light_lines(b)  # the output aspect does not move lights


def test_displayed_geometry_sets_the_scale(srtio3):
    geometry, camera = srtio3
    structure = perovskite_srtio3()
    base = resolve_lighting(replace(DRAMATIC, light_size=0.5), camera, geometry)
    block = build_geometry(structure, SceneSettings(repetitions=(2, 2, 2)))
    bigger = resolve_lighting(replace(DRAMATIC, light_size=0.5), camera, block)
    assert bigger.radius > 1.7 * base.radius and bigger.distance > base.distance
    assert bigger.key.area_size == pytest.approx(0.5 * bigger.radius)
    bare = build_geometry(structure, SceneSettings(boundary_images=False, show_cell=False))
    assert resolve_lighting(DRAMATIC, camera, bare).radius < base.radius
    # With the cell drawn, hiding the centre atom leaves the bounds unchanged ...
    hidden = build_geometry(structure, SceneSettings(hidden=frozenset({(1, (0, 0, 0))})))
    assert resolve_lighting(DRAMATIC, camera, hidden).distance == pytest.approx(base.distance)
    # ... but hidden atoms are not part of the bounds when they set the extent.
    face = frozenset((0, (1, b, c)) for b in (0, 1) for c in (0, 1))  # four Sr corners
    lone = build_geometry(structure, SceneSettings(show_cell=False, hidden=face))
    full = build_geometry(structure, SceneSettings(show_cell=False))
    smaller = resolve_lighting(DRAMATIC, camera, lone)
    assert smaller.radius < resolve_lighting(DRAMATIC, camera, full).radius
    assert not np.allclose(smaller.center, full.bounding_sphere()[0])


def test_intensities_size_and_panel(srtio3):
    geometry, camera = srtio3
    off = resolve_lighting(replace(DRAMATIC, key_light=0.0, fill_light=-1.0), camera, geometry)
    assert not off.key.enabled and not off.fill.enabled and off.lights() == ()
    text = scene_to_pov(
        geometry, camera, replace(DRAMATIC, key_light=0.0, fill_light=0.0), RenderSettings(800, 600)
    )
    assert "light_source" not in text
    point = resolve_lighting(DRAMATIC, camera, geometry)
    assert not point.key.is_area and point.key.area_size == 0.0 and point.panel is None
    area = resolve_lighting(replace(DRAMATIC, light_size=2.0), camera, geometry)
    axis1, axis2 = area.key.area_axes
    assert np.linalg.norm(axis1) == pytest.approx(2.0 * area.radius)  # diameter = size × R
    assert abs(axis1 @ axis2) < 1e-9 and axis1 @ area.right > 0 and axis2 @ area.up > 0
    np.testing.assert_array_equal(area.key.position, point.key.position)  # size never moves it
    panel = resolve_lighting(replace(DRAMATIC, reflector=True), camera, geometry).panel
    np.testing.assert_allclose(
        panel.center, point.center + 3.0 * point.radius * point.key.direction
    )
    np.testing.assert_allclose(panel.normal, -point.key.direction)
    assert panel.radius == pytest.approx(1.6 * point.radius)
    assert point.fill.shadows is False
    no_shadow = resolve_lighting(replace(DRAMATIC, shadows=False), camera, geometry)
    assert no_shadow.key.shadows is False


# ----- inverse: angles from a direction ------------------------------------------------------
def test_angles_round_trip_wrap_clamp_and_pole(srtio3):
    geometry, camera = srtio3
    r, u, d = camera.basis()
    for az in (-179.0, -65.0, 0.0, 35.0, 120.0):
        for el in (-30.0, 0.0, 25.0, 80.0):
            got = angles_of(key_direction(az, el, r, u, d) * 7.0, r, u, d)
            assert got == pytest.approx((az, el), abs=1e-9)
    assert angles_of(key_direction(180.0, 10.0, r, u, d), r, u, d)[0] == pytest.approx(-180.0)
    assert wrap_azimuth(190.0) == -170.0 and wrap_azimuth(-180.0) == -180.0
    assert angles_of(-u, r, u, d)[1] == KEY_ELEVATION_RANGE[0]  # below the limit: clamped
    assert angles_of(u, r, u, d, previous_azimuth=-40.0) == (-40.0, KEY_ELEVATION_RANGE[1])
    # Near the pole the azimuth is still defined by the small horizontal component.
    near = key_direction(-40.0, 89.99, r, u, d)
    assert angles_of(near, r, u, d)[0] == pytest.approx(-40.0, abs=1e-6)


def test_guide_arcs_lie_on_the_placement_sphere(srtio3):
    geometry, camera = srtio3
    rig = resolve_lighting(DRAMATIC, camera, geometry)
    arc = arc_points(rig, (0.0, rig.azimuth), (0.0, 0.0), rig.distance, count=20)
    np.testing.assert_allclose(np.linalg.norm(arc - rig.origin, axis=1), rig.distance)
    assert np.allclose((arc - rig.origin) @ rig.up, 0.0)  # azimuth arc: horizontal
    meridian = arc_points(rig, (rig.azimuth,) * 2, (0.0, rig.elevation), rig.distance)
    np.testing.assert_allclose(meridian[-1], rig.key.position)
    np.testing.assert_allclose(rig.key_point(rig.azimuth, rig.elevation), rig.key.position)
