"""POV-Ray renders must match the camera model: no mirroring, reframing, or offset.

Requires a working POV-Ray (``$YCRYSTAL_POVRAY`` or ``povray`` on PATH); skipped otherwise.
"""

import numpy as np
import pytest

from conftest import off_axis_camera
from ycrystal.core.scene import Environment
from ycrystal.render.imagecheck import find_blobs, load_rgba, match_spheres
from ycrystal.render.jobs import prepare_job, run_job
from ycrystal.render.pov_writer import RenderSettings
from ycrystal.render.selftest import run_self_test

pytestmark = pytest.mark.povray

TOLERANCE_PX = 1.0


def render(geometry, camera, settings, executable, tmp_path):
    job = prepare_job(geometry, camera, Environment(), settings, parent=tmp_path)
    result = run_job(job, executable, timeout=120)
    assert result.ok, result.message
    return load_rgba(result.image_path)


def test_self_test_passes(povray_executable):
    result = run_self_test(povray_executable)
    assert result.ok, result.message
    assert result.max_error_px < TOLERANCE_PX


@pytest.mark.parametrize("size", [(480, 270), (240, 400), (300, 300)])
def test_rotated_panned_view_matches_camera_model(size, spread, povray_executable, tmp_path):
    width, height = size
    camera = off_axis_camera(spread, width / height)
    settings = RenderSettings(width=width, height=height, transparent_background=True)
    rgba = render(spread, camera, settings, povray_executable, tmp_path)

    assert rgba.shape == (height, width, 4)
    assert rgba[0, 0, 3] == 0  # transparent background
    expected = camera.project(spread.positions, width, height)
    blobs = find_blobs(rgba)
    assert len(blobs) == len(spread), "spheres overlap or are missing"
    matches = match_spheres(expected, spread.colors, blobs)
    errors = [m.error_px for m in matches]
    assert max(errors) < TOLERANCE_PX, errors
    assert all(m.hue_ok for m in matches), [(m.expected_rgb, m.found_rgb) for m in matches]
    # Disc areas agree with the projected radii (no scaling error).
    k = camera.pixels_per_angstrom(height)
    found = {b.centroid: b.area for b in blobs}
    for match, radius in zip(matches, spread.radii, strict=True):
        assert found[match.found] == pytest.approx(np.pi * (radius * k) ** 2, rel=0.08)


def test_check_detects_mirrored_or_shifted_images(spread, povray_executable, tmp_path):
    """Negative control: the comparison is sensitive to mirroring and small offsets."""
    width, height = 480, 270
    camera = off_axis_camera(spread, width / height)
    settings = RenderSettings(width=width, height=height, transparent_background=True)
    blobs = find_blobs(render(spread, camera, settings, povray_executable, tmp_path))
    expected = camera.project(spread.positions, width, height)
    mirrored = expected.copy()
    mirrored[:, 0] = width - mirrored[:, 0]
    mirror_matches = match_spheres(mirrored, spread.colors, blobs)
    assert max(m.error_px for m in mirror_matches) > 5 or not all(m.hue_ok for m in mirror_matches)
    shifted = match_spheres(expected + (2.0, 0.0), spread.colors, blobs)
    assert min(m.error_px for m in shifted) > TOLERANCE_PX


def test_opaque_render_has_requested_size_and_background(spread, povray_executable, tmp_path):
    camera = off_axis_camera(spread, 200 / 120)
    rgba = render(spread, camera, RenderSettings(200, 120), povray_executable, tmp_path)
    assert rgba.shape == (120, 200, 4)
    assert np.all(rgba[..., 3] == 255)
    assert tuple(rgba[0, 0, :3]) == (255, 255, 255)
