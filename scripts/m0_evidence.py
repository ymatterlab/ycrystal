"""Produce M0 acceptance evidence on the current machine.

Opens the real main window on the display, navigates with synthetic mouse drags
(orbit, Shift+pan, wheel zoom) in a non-square viewport, then:

* saves a screenshot of the application window and of the live viewport,
* renders the same view with POV-Ray through the GUI's non-blocking render path,
* measures atom positions in both images against the camera model, and
* writes environment details and the numerical results to ``report.json``.

Usage:  python scripts/m0_evidence.py [--out artifacts/m0] [--povray PATH]
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import sys
from pathlib import Path

os.environ["QT_API"] = "pyside6"

import numpy as np  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402
from PySide6.QtCore import QEvent, QEventLoop, QPoint, QPointF, Qt, QTimer  # noqa: E402
from PySide6.QtGui import QMouseEvent, QWheelEvent  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from ycrystal.core.bonds import BondSettings  # noqa: E402
from ycrystal.core.camera import Camera  # noqa: E402
from ycrystal.core.samples import triclinic_marker  # noqa: E402
from ycrystal.core.scene import DisplayGeometry, SceneSettings, build_geometry  # noqa: E402
from ycrystal.gui.main_window import SETTINGS_POVRAY, MainWindow  # noqa: E402
from ycrystal.render.imagecheck import Blob, find_blobs, load_rgba, match_spheres  # noqa: E402
from ycrystal.render.povray import find_povray, povray_version  # noqa: E402


def wait(ms: int) -> None:
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


def drag(widget, start, end, button, modifiers=Qt.KeyboardModifier.NoModifier, steps=12):
    def send(kind, pos, btn, buttons):
        point = QPointF(*pos)
        QApplication.sendEvent(
            widget, QMouseEvent(kind, point, widget.mapToGlobal(point), btn, buttons, modifiers)
        )

    start, end = np.asarray(start, float), np.asarray(end, float)
    send(QEvent.Type.MouseButtonPress, start, button, button)
    for i in range(1, steps + 1):
        send(
            QEvent.Type.MouseMove,
            start + (end - start) * i / steps,
            Qt.MouseButton.NoButton,
            button,
        )
        wait(15)
    send(QEvent.Type.MouseButtonRelease, end, button, Qt.MouseButton.NoButton)


def wheel(widget, pos, clicks):
    point = QPointF(*pos)
    for _ in range(abs(clicks)):
        QApplication.sendEvent(
            widget,
            QWheelEvent(
                point,
                widget.mapToGlobal(point),
                QPoint(0, 0),
                QPoint(0, 120 if clicks > 0 else -120),
                Qt.MouseButton.NoButton,
                Qt.KeyboardModifier.NoModifier,
                Qt.ScrollPhase.NoScrollPhase,
                False,
            ),
        )


def render_via_gui(window: MainWindow, destination: Path) -> dict:
    window.render_finished_result = None
    if not window.render_png(destination, show_result=False):
        raise SystemExit(f"render did not start: {window.last_error}")
    while window.render_finished_result is None:
        wait(50)
    result = window.render_finished_result
    if not result.ok:
        raise SystemExit(f"render failed: {result.message}")
    return {"path": str(destination)}


def measure(
    camera: Camera,
    geometry: DisplayGeometry,
    rgba: np.ndarray,
    window: MainWindow | None = None,
    size: tuple[int, int] | None = None,
) -> dict:
    """Compare sphere centres in ``rgba`` with the output camera's projection.

    With ``window`` and ``size``, ``rgba`` is a live-view screenshot: its blob centres
    are mapped from the output frame to output-image pixels first.
    """
    if window is None:
        height, width = rgba.shape[:2]
        blobs = find_blobs(rgba)
    else:
        width, height = size
        blobs = [
            Blob(
                tuple(window.viewport.frame_to_output(np.array([b.centroid]), width, height)[0]),
                b.area,
                b.mean_rgb,
            )
            for b in find_blobs(rgba)
        ]
    expected = camera.project(geometry.positions, width, height)
    matches = match_spheres(expected, geometry.colors, blobs)
    return {
        "image_size": [width, height],
        "spheres_expected": len(geometry),
        "blobs_found": len(blobs),
        "max_error_px": max(m.error_px for m in matches),
        "colours_match": all(m.hue_ok for m in matches),
        "per_sphere": [
            {
                "expected": [round(v, 3) for v in m.expected],
                "found": [round(v, 3) for v in m.found] if m.found else None,
                "error_px": round(m.error_px, 3),
            }
            for m in matches
        ],
    }


def marker_overlay(image_path: Path, points: np.ndarray, out: Path) -> None:
    with Image.open(image_path) as im:
        canvas = Image.new("RGBA", im.size, (255, 255, 255, 255))
        canvas.alpha_composite(im.convert("RGBA"))
    draw = ImageDraw.Draw(canvas)
    for x, y in points:
        draw.line([(x - 9, y), (x + 9, y)], fill=(0, 0, 0, 255), width=1)
        draw.line([(x, y - 9), (x, y + 9)], fill=(0, 0, 0, 255), width=1)
    canvas.convert("RGB").save(out)


def side_by_side(left: Path, right: Path, out: Path, labels: tuple[str, str]) -> None:
    with Image.open(left) as a, Image.open(right) as b:
        a, b = a.convert("RGB"), b.convert("RGB")
        gap, header = 12, 26
        canvas = Image.new(
            "RGB", (a.width + b.width + gap, max(a.height, b.height) + header), "white"
        )
        canvas.paste(a, (0, header))
        canvas.paste(b, (a.width + gap, header))
    draw = ImageDraw.Draw(canvas)
    draw.text((6, 6), labels[0], fill="black")
    draw.text((a.width + gap + 6, 6), labels[1], fill="black")
    canvas.save(out)


def environment(executable: str) -> dict:
    import ase
    import PySide6
    import pyvista
    import pyvistaqt
    import vtk
    from PySide6.QtCore import qVersion

    os_release = {}
    try:
        for line in Path("/etc/os-release").read_text().splitlines():
            key, _, value = line.partition("=")
            os_release[key] = value.strip('"')
    except OSError:
        pass
    return {
        "os": os_release.get("PRETTY_NAME"),
        "kernel": platform.release(),
        "session": f"{os.environ.get('XDG_SESSION_TYPE')} {os.environ.get('XDG_CURRENT_DESKTOP')}",
        "python": f"{platform.python_version()} ({sys.executable})",
        "qt": qVersion(),
        "pyside6": PySide6.__version__,
        "vtk": vtk.vtkVersion.GetVTKVersion(),
        "pyvista": pyvista.__version__,
        "pyvistaqt": pyvistaqt.__version__,
        "ase": ase.__version__,
        "numpy": np.__version__,
        "povray_executable": executable,
        "povray_version": povray_version(executable),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", default="artifacts/m0", type=Path)
    parser.add_argument("--povray", default=None)
    args = parser.parse_args()
    out: Path = args.out
    out.mkdir(parents=True, exist_ok=True)
    executable = find_povray(args.povray)

    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setOrganizationName("Y-Matter Lab")
    app.setApplicationName("Ycrystal-evidence")  # separate settings from the real app
    window = MainWindow(triclinic_marker())
    window.settings.setValue(SETTINGS_POVRAY, executable)
    window.preview_panel.auto_check.setChecked(False)  # no background previews during evidence
    window.resize(1100, 680)
    window.show()
    wait(800)

    # --- navigate with the mouse: orbit, Shift+pan, wheel zoom --------------------
    widget = window.viewport.interactor_widget
    w, h = widget.width(), widget.height()
    initial = window.viewport.camera()
    drag(widget, (w * 0.45, h * 0.55), (w * 0.62, h * 0.40), Qt.MouseButton.LeftButton)
    drag(widget, (w * 0.30, h * 0.30), (w * 0.35, h * 0.62), Qt.MouseButton.LeftButton)
    drag(
        widget,
        (w * 0.5, h * 0.5),
        (w * 0.5 + 70, h * 0.5 - 35),
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.ShiftModifier,
    )
    wheel(widget, (w * 0.5, h * 0.5), 1)
    wait(300)
    vw, vh = window.viewport.render_size()
    # Render at the frame's size in pixels, so the frame region of the live view and the
    # POV-Ray image overlay one to one. The output camera is kept by set_output_size.
    _x0, _y0, frame_w, frame_h = window.viewport.frame_rect()
    window.set_output_size(round(frame_w), round(frame_h))
    wait(200)
    out_w, out_h = window.current_render_settings().width, window.current_render_settings().height
    camera = window.current_camera()

    # --- visual evidence: full scene ---------------------------------------------
    window.grab()  # make sure the window is painted
    wait(200)
    shot = app.primaryScreen().grabWindow(window.winId())
    shot.save(str(out / "window.png"))
    window.viewport.set_frame_visible(False)
    x0, y0, _fw, _fh = (round(v) for v in window.viewport.frame_rect())
    viewport_rgba = window.viewport.screenshot(transparent=False)
    Image.fromarray(viewport_rgba[y0 : y0 + out_h, x0 : x0 + out_w]).save(out / "viewport.png")
    render_via_gui(window, out / "render.png")
    side_by_side(
        out / "viewport.png",
        out / "render.png",
        out / "comparison.png",
        ("Live VTK view inside the output frame", "POV-Ray render, same output camera"),
    )
    window.export_pov(out / "scene.pov")

    # --- numerical evidence: atoms only, transparent background ----------------------
    # Same mouse-navigated camera; no cell edges and half-size spheres so that every atom
    # is a separate disc (atom centres, and hence the expected pixels, are unchanged).
    # Bonds are switched off too: a bond would join two discs into one blob.
    window.set_background("transparent")  # rebuilds the geometry: set it before replacing it
    atoms_only = build_geometry(
        window.structure,
        SceneSettings(radius_scale=0.25, show_cell=False, bonds=BondSettings(enabled=False)),
    )
    window.set_display_geometry(atoms_only)
    window.viewport.set_axes_visible(False)
    assert window.current_camera() == camera
    vtk_rgba = window.viewport.screenshot(transparent=True)
    Image.fromarray(vtk_rgba).save(out / "viewport_atoms.png")
    render_via_gui(window, out / "render_atoms.png")
    pov_rgba = load_rgba(out / "render_atoms.png")
    expected = camera.project(atoms_only.positions, out_w, out_h)
    marker_overlay(out / "render_atoms.png", expected, out / "render_atoms_markers.png")
    report = {
        "environment": environment(executable),
        "viewport_px": [vw, vh],
        "output_px": [out_w, out_h],
        "frame_rect_px": [round(v, 2) for v in window.viewport.frame_rect()],
        "navigation": {
            "initial_camera": initial.to_dict(),
            "final_camera": camera.to_dict(),
            "view_direction_change_deg": float(
                np.degrees(np.arccos(np.clip(initial.basis()[2] @ camera.basis()[2], -1, 1)))
            ),
            "focal_point_shift_A": float(
                np.linalg.norm(np.subtract(camera.focal_point, initial.focal_point))
            ),
            "zoom_ratio": initial.parallel_scale / camera.parallel_scale,
        },
        "coordinates_unchanged": bool(
            np.array_equal(window.structure.positions, triclinic_marker().positions)
        ),
        "vtk_vs_model": measure(camera, atoms_only, vtk_rgba, window, (out_w, out_h)),
        "povray_vs_model": measure(camera, atoms_only, pov_rgba),
    }
    (out / "report.json").write_text(json.dumps(report, indent=2))
    print(
        json.dumps(
            {k: report[k] for k in ("viewport_px", "output_px", "coordinates_unchanged")}, indent=2
        )
    )
    for key in ("vtk_vs_model", "povray_vs_model"):
        r = report[key]
        print(
            f"{key}: {r['blobs_found']}/{r['spheres_expected']} spheres, max error "
            f"{r['max_error_px']:.3f} px, colours match: {r['colours_match']}"
        )
    window.ask_save_changes = lambda: "discard"  # evidence run: nothing to save
    window.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
