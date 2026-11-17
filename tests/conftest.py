from __future__ import annotations

import os
import shutil
import sys
import textwrap
from pathlib import Path

import numpy as np
import pytest

os.environ["QT_API"] = "pyside6"

from ycrystal.core.camera import Camera  # noqa: E402
from ycrystal.core.scene import DisplayGeometry  # noqa: E402

#: Set to 1 (as CI does) to make a missing display or POV-Ray an error instead of a
#: skip, so that the GUI and rendering tests cannot silently pass as "skipped".
REQUIRE_INTEGRATION = os.environ.get("YCRYSTAL_REQUIRE_INTEGRATION") == "1"


def python_program(path: Path, code: str) -> str:
    """Write a small program that runs ``code`` with this Python; return its path.

    The program is ``path`` itself on Linux and macOS (a shell launcher) and
    ``path.cmd`` on Windows (a batch launcher), so that tests can stand in for POV-Ray
    on every system. The code receives the program's arguments in ``sys.argv``.
    """
    script = path.with_name(path.name + "_main.py")
    script.write_text(textwrap.dedent(code), encoding="utf-8")
    if sys.platform == "win32":
        launcher = path.with_name(path.name + ".cmd")
        launcher.write_text(f'@"{sys.executable}" "{script}" %*\n', encoding="utf-8")
    else:
        launcher = path
        launcher.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{script}" "$@"\n')
        launcher.chmod(0o755)
    return str(launcher)


def fake_povray(folder: Path, fail: bool = False) -> str:
    """Return a stand-in for POV-Ray that writes a plain PNG of the requested size.

    ``--version`` reports ``3.7.0.fake``. The image has the colour given by
    ``$YCRYSTAL_FAKE_COLOR`` (``"r,g,b"``, default ``40,60,80``); with `fail` the
    program prints a parse error and exits with status 1. For tests of the command
    line, snapshots, and scripts that need no real ray tracing.
    """
    name = "fake_povray_fail" if fail else "fake_povray"
    code = f"""
        import os, re, sys
        from pathlib import Path
        if "--version" in sys.argv:
            print("POV-Ray 3.7.0.fake")
            sys.exit(0)
        if {fail!r}:
            print("Parse Error: this renderer always fails")
            sys.exit(1)
        ini = Path(sys.argv[1]).read_text()
        size = [int(re.search(k + r"=(\\d+)", ini).group(1)) for k in ("Width", "Height")]
        color = os.environ.get("YCRYSTAL_FAKE_COLOR", "40,60,80")
        from PIL import Image
        Image.new("RGB", tuple(size), tuple(int(v) for v in color.split(","))).save("scene.png")
        """
    return python_program(folder / name, code)


def display_available() -> bool:
    """Whether Qt can open real windows here (the GUI tests draw with OpenGL).

    macOS and Windows have no display variable: Qt uses the desktop session, so a
    display is assumed unless Qt is told to draw off-screen (``QT_QPA_PLATFORM``).
    Elsewhere an X11 or Wayland display must be named in the environment.
    """
    if sys.platform in ("darwin", "win32"):
        return os.environ.get("QT_QPA_PLATFORM", "") not in ("offscreen", "minimal")
    return bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if display_available():
        return
    gui_items = [item for item in items if "gui" in item.keywords]
    if gui_items and REQUIRE_INTEGRATION:
        raise pytest.UsageError(
            f"YCRYSTAL_REQUIRE_INTEGRATION=1 but no display is available for "
            f"{len(gui_items)} GUI tests. Run in a desktop session (Linux: under X11, "
            f"Wayland, or xvfb-run)."
        )
    skip = pytest.mark.skip(reason="no display available for GUI tests")
    for item in gui_items:
        item.add_marker(skip)


@pytest.fixture(scope="session")
def povray_executable() -> str:
    """A POV-Ray executable that passes the renderer self-test, or skip."""
    from ycrystal.render.selftest import run_self_test

    candidates = []
    for candidate in (os.environ.get("YCRYSTAL_POVRAY"), shutil.which("povray")):
        if candidate and candidate not in candidates:
            candidates.append(candidate)
    reasons = []
    for candidate in candidates:
        result = run_self_test(candidate)
        if result.ok:
            return str(result.executable)
        reasons.append(f"{candidate}: {result.message}")
    message = "no working POV-Ray executable. " + " | ".join(reasons or ["none found"])
    if REQUIRE_INTEGRATION:
        pytest.fail(f"YCRYSTAL_REQUIRE_INTEGRATION=1 but {message}", pytrace=False)
    pytest.skip(message)


@pytest.fixture(scope="session", autouse=True)
def isolated_qsettings(tmp_path_factory: pytest.TempPathFactory) -> None:
    """Keep GUI tests away from the user's real Ycrystal settings."""
    from PySide6.QtCore import QCoreApplication, QSettings

    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    QSettings.setPath(
        QSettings.Format.IniFormat,
        QSettings.Scope.UserScope,
        str(tmp_path_factory.mktemp("qsettings")),
    )
    QCoreApplication.setOrganizationName("Ycrystal-tests")
    QCoreApplication.setApplicationName("Ycrystal-tests")


def spread_geometry() -> DisplayGeometry:
    """Well-separated spheres with distinct dominant colour channels.

    The arrangement is chiral (no mirror symmetry), so a mirrored image cannot match.
    """
    positions = np.array(
        [
            [0.0, 0.0, 0.0],
            [3.2, 0.4, 0.9],
            [-0.6, 2.9, -1.1],
            [0.8, -1.3, 3.1],
            [-2.7, -2.0, 0.6],
            [2.8, -2.4, 2.3],
        ]
    )
    colors = np.array(
        [
            [0.9, 0.1, 0.1],
            [0.1, 0.8, 0.1],
            [0.1, 0.2, 0.9],
            [0.9, 0.2, 0.1],
            [0.1, 0.9, 0.2],
            [0.2, 0.1, 0.9],
        ]
    )
    return DisplayGeometry(
        atom_ids=tuple((i, (0, 0, 0)) for i in range(len(positions))),
        elements=("O", "Cl", "N", "Fe", "B", "Ar"),
        positions=positions,
        radii=np.array([0.42, 0.36, 0.40, 0.33, 0.38, 0.35]),
        colors=colors,
        cell_edges=np.zeros((0, 2, 3)),
        cell_edge_radius=0.03,
        cell_edge_color=(0.2, 0.2, 0.2),
    )


@pytest.fixture
def spread() -> DisplayGeometry:
    return spread_geometry()


def off_axis_camera(geometry: DisplayGeometry, aspect: float) -> Camera:
    """Rotated (azimuth, elevation, roll) and panned view that keeps every sphere in frame."""
    points, radii = geometry.points_and_radii()
    camera = (
        Camera.looking_along((0.3, -1.0, -0.25), (0, 0, 1))
        .orbit(azimuth=-48, elevation=31)
        .roll(23)
        .fitted(points, radii, aspect, margin=0.3)
    )
    return camera.pan(0.12 * camera.parallel_scale, -0.08 * camera.parallel_scale)


@pytest.fixture(autouse=True)
def no_blocking_dialogs(monkeypatch):
    """Windows in tests never block on a dialog.

    Closing a window with unsaved changes discards them; any other dialog that a test
    did not answer explicitly fails the test instead of waiting for a user.
    """
    from ycrystal.gui.main_window import MainWindow

    def unexpected(self, *args, **kwargs):
        raise AssertionError(f"unexpected dialog: {args!r}")

    monkeypatch.setattr(MainWindow, "ask_save_changes", lambda self: "discard")
    # Previews start only when a test asks for them (no background POV-Ray runs).
    monkeypatch.setattr("ycrystal.gui.main_window.AUTO_PREVIEW_DEFAULT", False)
    for name in (
        "ask_open_path",
        "ask_save_path",
        "ask_choice",
        "ask_text",
        "ask_confirm",
        "ask_style_import",
        "ask_export",
    ):
        monkeypatch.setattr(MainWindow, name, unexpected)
