"""Renderer self-test: render a tiny known scene and check its geometry.

The scene uses a rotated, panned camera and a non-square image. Three spheres of
different colours must appear at the analytically projected pixels (within one pixel),
with the expected colours (detects mirroring) and the requested dimensions.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from ycrystal.core.camera import Camera
from ycrystal.core.scene import DisplayGeometry, Environment
from ycrystal.render.imagecheck import Match, find_blobs, load_rgba, match_spheres
from ycrystal.render.jobs import prepare_job, run_job
from ycrystal.render.pov_writer import RenderSettings
from ycrystal.render.povray import find_povray, povray_version

TOLERANCE_PX = 1.0
"""Largest accepted distance in pixels between rendered and predicted sphere centres."""


@dataclass
class SelfTestResult:
    """Outcome of [`run_self_test`][ycrystal.render.selftest.run_self_test].

    Attributes
    ----------
    ok
        Whether the renderer passed.
    executable
        Executable that was tested; ``None`` if none was found.
    version
        Version reported by the executable, if any.
    message
        Readable verdict, printed by ``ycrystal --check-renderer``.
    max_error_px
        Largest centre error in pixels, if the image could be measured.
    matches
        Per-sphere measurements, if the image could be measured.
    """

    ok: bool
    executable: str | None
    version: str | None
    message: str
    max_error_px: float | None = None
    matches: list[Match] = field(default_factory=list)


def self_test_geometry() -> DisplayGeometry:
    """Return three spheres with distinct dominant colour channels (red, green, blue)."""
    positions = np.array([[2.0, 0.5, -0.3], [-1.6, 1.2, 0.8], [0.3, -1.7, 0.2]])
    colors = np.array([[0.9, 0.1, 0.1], [0.1, 0.8, 0.1], [0.1, 0.2, 0.9]])
    return DisplayGeometry(
        atom_ids=tuple((i, (0, 0, 0)) for i in range(3)),
        elements=("O", "Cl", "N"),
        positions=positions,
        radii=np.array([0.45, 0.4, 0.35]),
        colors=colors,
        cell_edges=np.zeros((0, 2, 3)),
        cell_edge_radius=0.03,
        cell_edge_color=(0.2, 0.2, 0.2),
    )


def self_test_camera() -> Camera:
    """Return a rotated, rolled, and panned camera for the self-test scene."""
    camera = Camera.looking_along((0.3, -1.0, -0.2), (0.0, 0.0, 1.0), parallel_scale=3.0)
    return camera.orbit(azimuth=37.0, elevation=24.0).roll(17.0).pan(0.4, -0.3)


def run_self_test(configured: str | None = None, timeout: float = 60.0) -> SelfTestResult:
    """Check that a POV-Ray executable reproduces Ycrystal's camera.

    Finds the executable like [`find_povray`][ycrystal.render.povray.find_povray],
    asks for its version, and renders a 120 × 80 pixel image with a transparent
    background in a temporary job directory. The image passes if it has the requested
    size and each sphere is within
    [`TOLERANCE_PX`][ycrystal.render.selftest.TOLERANCE_PX] of its predicted pixel
    position, with the expected dominant colour channel (which detects mirroring).

    Parameters
    ----------
    configured
        Executable to test first; see `find_povray`. The GUI passes its stored setting;
        ``ycrystal --check-renderer`` passes ``--povray``.
    timeout
        Seconds allowed for the render.

    Returns
    -------
    SelfTestResult
        The verdict. A missing or failing renderer gives ``ok=False`` with an
        explanation.

    Raises
    ------
    OSError
        If the temporary job cannot be prepared or its image cannot be read.
        Other image-decoding or measurement errors may also propagate.

    Notes
    -----
    Runs synchronously: the caller waits for the version query (up to 15 s) and the
    render (up to `timeout`). Once preparation succeeds, the job directory is
    removed in ``finally``, including on image-reading or measurement failures.
    """
    try:
        executable = find_povray(configured)
    except Exception as exc:  # PovrayNotFoundError
        return SelfTestResult(False, None, None, str(exc))
    version = povray_version(executable)
    geometry = self_test_geometry()
    camera = self_test_camera()
    settings = RenderSettings(width=120, height=80, antialias=True, transparent_background=True)
    job = prepare_job(geometry, camera, Environment(), settings, title="Ycrystal renderer check")
    try:
        result = run_job(job, executable, timeout=timeout)
        if not result.ok or result.image_path is None:
            return SelfTestResult(False, executable, version, result.message)
        rgba = load_rgba(result.image_path)
        if rgba.shape[:2] != (settings.height, settings.width):
            return SelfTestResult(
                False,
                executable,
                version,
                f"Wrong image size {rgba.shape[1]}x{rgba.shape[0]}; expected "
                f"{settings.width}x{settings.height}.",
            )
        expected = camera.project(geometry.positions, settings.width, settings.height)
        matches = match_spheres(expected, geometry.colors, find_blobs(rgba))
        worst = max(m.error_px for m in matches)
        if worst > TOLERANCE_PX or not all(m.hue_ok for m in matches):
            return SelfTestResult(
                False,
                executable,
                version,
                f"Rendered spheres are misplaced (max error {worst:.2f} px) or have the "
                "wrong colours; the camera export does not match this POV-Ray build.",
                worst,
                matches,
            )
        return SelfTestResult(
            True,
            executable,
            version,
            f"POV-Ray {version or '(unknown version)'} at {executable} passed: sphere centres "
            f"within {worst:.2f} px of the camera model.",
            worst,
            matches,
        )
    finally:
        job.cleanup()
