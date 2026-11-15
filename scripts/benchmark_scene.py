"""Measure display cost for growing supercells (needs an X11 display).

For SrTiO3 (5 atoms per cell, Ti–O and Sr–O bonds) at increasing repetitions, reports:
geometry build time (atoms, boundary images, bonds), time to load the scene into the
VTK viewport, the time per mouse-drag step (synthetic left-button drag through VTK's
interactor, each step repainted before the next; includes waiting for the GPU and the
compositor), and time to write the POV-Ray scene. Used to choose SOFT_LIMIT_ATOMS.

Usage:  python scripts/benchmark_scene.py [--sizes 2 6 10 14 18 20] [--frames 30]
"""

from __future__ import annotations

import argparse
import os
import platform
import sys
import time

os.environ["QT_API"] = "pyside6"

from PySide6.QtCore import QEvent, QPointF, Qt  # noqa: E402
from PySide6.QtGui import QMouseEvent  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from ycrystal.core.camera import default_camera  # noqa: E402
from ycrystal.core.samples import perovskite_srtio3  # noqa: E402
from ycrystal.core.scene import Environment, SceneSettings, build_geometry  # noqa: E402
from ycrystal.render.pov_writer import RenderSettings, scene_to_pov  # noqa: E402
from ycrystal.viewport.qt_viewport import StructureViewport  # noqa: E402


def gl_renderer(viewport: StructureViewport) -> str:
    info = viewport._plotter.render_window.ReportCapabilities()
    for line in info.splitlines():
        if "OpenGL renderer string" in line:
            return line.split(":", 1)[1].strip()
    return "unknown"


def drag_step_seconds(app: QApplication, viewport: StructureViewport, steps: int) -> float:
    widget = viewport.interactor_widget

    def send(kind: QEvent.Type, x: float, buttons: Qt.MouseButton, button: Qt.MouseButton):
        point = QPointF(x, 300.0)
        event = QMouseEvent(
            kind, point, widget.mapToGlobal(point), button, buttons, Qt.KeyboardModifier.NoModifier
        )
        QApplication.sendEvent(widget, event)

    left, none = Qt.MouseButton.LeftButton, Qt.MouseButton.NoButton
    send(QEvent.Type.MouseButtonPress, 300.0, left, left)
    start = time.perf_counter()
    for k in range(steps):
        send(QEvent.Type.MouseMove, 300.0 + 4 * (k + 1), left, none)
        app.processEvents()
    elapsed = (time.perf_counter() - start) / steps
    send(QEvent.Type.MouseButtonRelease, 300.0 + 4 * steps, none, left)
    return elapsed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--sizes", type=int, nargs="+", default=[2, 6, 10, 14, 18, 20])
    parser.add_argument("--frames", type=int, default=30)
    args = parser.parse_args()

    app = QApplication.instance() or QApplication(sys.argv[:1])
    viewport = StructureViewport()
    viewport.resize(1100, 700)
    viewport.show()
    app.processEvents()
    structure = perovskite_srtio3()
    print(f"CPU: {platform.processor() or platform.machine()}; GPU: {gl_renderer(viewport)}")
    print(
        f"{'cells':>10} {'atoms':>7} {'bonds':>7} {'build s':>8} {'load s':>7} "
        f"{'drag ms':>8} {'steps/s':>8} {'detail':>9} {'pov s':>6}"
    )
    for n in args.sizes:
        settings = SceneSettings(repetitions=(n, n, n))
        t0 = time.perf_counter()
        geometry = build_geometry(structure, settings)
        t1 = time.perf_counter()
        viewport.set_scene(geometry, Environment())
        width, height = viewport.render_size()
        points, radii = geometry.points_and_radii()
        camera = default_camera(points, radii, width / height)
        viewport.set_camera(camera)
        app.processEvents()
        t2 = time.perf_counter()
        frame = drag_step_seconds(app, viewport, args.frames)
        t3 = time.perf_counter()
        scene_to_pov(geometry, camera, Environment(), RenderSettings(1200, 800))
        t4 = time.perf_counter()
        detail = "{}x{}/{}".format(*viewport.detail)
        print(
            f"{n:>3}x{n}x{n:<3} {len(geometry):>7} {len(geometry.bonds):>7} "
            f"{t1 - t0:>8.3f} {t2 - t1:>7.3f} {frame * 1000:>8.1f} {1 / frame:>8.1f} "
            f"{detail:>9} {t4 - t3:>6.2f}"
        )
    viewport.close_viewport()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
