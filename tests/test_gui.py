"""GUI checks on a real display: launch, navigation, live-view/camera agreement, export,
missing renderer, and an end-to-end non-blocking render."""

import numpy as np
import pytest
from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
from PySide6.QtGui import QMouseEvent, QWheelEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from conftest import off_axis_camera
from ycrystal.core.camera import Camera
from ycrystal.core.samples import triclinic_marker
from ycrystal.gui.main_window import SETTINGS_POVRAY, MainWindow
from ycrystal.render.imagecheck import find_blobs, load_rgba, match_spheres
from ycrystal.render.povray import POVRAY_ENV

pytestmark = pytest.mark.gui


@pytest.fixture
def window(qtbot):
    win = MainWindow(triclinic_marker())
    qtbot.addWidget(win)
    win.resize(960, 600)  # non-square viewport
    win.show()
    qtbot.waitExposed(win)
    qtbot.waitUntil(lambda: win._camera_initialised, timeout=5000)
    qtbot.wait(200)
    yield win
    win.close()


def _send_drag(widget, start, end, button, modifiers=Qt.KeyboardModifier.NoModifier, steps=10):
    def send(kind, pos, btn, buttons):
        point = QPointF(*pos)
        event = QMouseEvent(kind, point, widget.mapToGlobal(point), btn, buttons, modifiers)
        QApplication.sendEvent(widget, event)

    start, end = np.asarray(start, float), np.asarray(end, float)
    send(QEvent.Type.MouseButtonPress, start, button, button)
    for i in range(1, steps + 1):
        send(QEvent.Type.MouseMove, start + (end - start) * i / steps,
             Qt.MouseButton.NoButton, button)
    send(QEvent.Type.MouseButtonRelease, end, button, Qt.MouseButton.NoButton)


def _send_wheel(widget, pos, clicks):
    point = QPointF(*pos)
    for _ in range(abs(clicks)):
        event = QWheelEvent(point, widget.mapToGlobal(point), QPoint(0, 0),
                            QPoint(0, 120 if clicks > 0 else -120), Qt.MouseButton.NoButton,
                            Qt.KeyboardModifier.NoModifier, Qt.ScrollPhase.NoScrollPhase, False)
        QApplication.sendEvent(widget, event)


def test_window_launches_with_sample_and_fitted_view(window):
    assert "OFeSClN" in window.windowTitle()
    assert "5 atoms shown" in window.structure_label.text()
    width, height = window.viewport.render_size()
    assert width != height
    pixels = window.current_camera().project(window.geometry.positions, width, height)
    assert np.all((pixels > 0) & (pixels < (width, height)))


def test_camera_round_trip_and_vtk_projection_agree(window):
    width, height = window.viewport.render_size()
    camera = Camera(position=(4, -12, 6), focal_point=(1.5, 2.0, 1.0), view_up=(0.1, 0.2, 1),
                    parallel_scale=3.7).orbit(azimuth=17, elevation=-9).pan(0.4, 0.3)
    window.viewport.set_camera(camera)
    back = window.viewport.camera()
    for ours, theirs in zip(camera.basis(), back.basis(), strict=True):
        np.testing.assert_allclose(ours, theirs, atol=1e-12)
    np.testing.assert_allclose(back.focal_point, camera.focal_point)
    assert back.parallel_scale == pytest.approx(camera.parallel_scale)
    points = window.geometry.positions
    np.testing.assert_allclose(window.viewport.vtk_project(points),
                               camera.project(points, width, height), atol=1e-6)


def test_mouse_navigation_changes_only_the_camera(window):
    widget = window.viewport.interactor_widget
    positions = window.structure.positions.copy()
    geometry_positions = window.geometry.positions.copy()
    w, h = widget.width(), widget.height()
    centre = (w / 2, h / 2)

    before = window.viewport.camera()
    _send_drag(widget, centre, (w / 2 + 120, h / 2 + 40), Qt.MouseButton.LeftButton)
    orbited = window.viewport.camera()
    assert np.degrees(np.arccos(np.clip(before.basis()[2] @ orbited.basis()[2], -1, 1))) > 10
    np.testing.assert_allclose(orbited.focal_point, before.focal_point, atol=1e-9)
    assert orbited.parallel_scale == pytest.approx(before.parallel_scale)

    # Shift + left drag pans in the screen plane: the scene follows the cursor.
    width, height = window.viewport.render_size()
    atom = window.geometry.positions[:1]
    start_px = orbited.project(atom, width, height)[0]
    _send_drag(widget, centre, (w / 2 + 60, h / 2 - 30), Qt.MouseButton.LeftButton,
               Qt.KeyboardModifier.ShiftModifier)
    panned = window.viewport.camera()
    np.testing.assert_allclose(panned.basis()[2], orbited.basis()[2], atol=1e-9)
    moved = panned.project(atom, width, height)[0] - start_px
    np.testing.assert_allclose(moved, (60, -30), atol=1.5)

    # Middle drag also pans.
    _send_drag(widget, centre, (w / 2 - 40, h / 2), Qt.MouseButton.MiddleButton)
    middle = window.viewport.camera()
    np.testing.assert_allclose(middle.basis()[2], panned.basis()[2], atol=1e-9)
    assert not np.allclose(middle.focal_point, panned.focal_point)

    # Wheel forward zooms in; right drag zooms too.
    _send_wheel(widget, centre, 3)
    zoomed = window.viewport.camera()
    assert zoomed.parallel_scale < middle.parallel_scale
    _send_drag(widget, centre, (w / 2, h / 2 + 80), Qt.MouseButton.RightButton)
    assert window.viewport.camera().parallel_scale != pytest.approx(zoomed.parallel_scale)

    # Fit keeps the orientation and brings everything back into view.
    direction = window.viewport.camera().basis()[2]
    window.fit_action.trigger()
    fitted = window.viewport.camera()
    np.testing.assert_allclose(fitted.basis()[2], direction, atol=1e-9)
    pixels = fitted.project(window.geometry.positions, width, height)
    assert np.all((pixels > 0) & (pixels < (width, height)))

    np.testing.assert_array_equal(window.structure.positions, positions)
    np.testing.assert_array_equal(window.geometry.positions, geometry_positions)


def test_vtk_default_keys_are_disabled(window, qtbot):
    widget = window.viewport.interactor_widget
    for key in (Qt.Key.Key_Q, Qt.Key.Key_E, Qt.Key.Key_W):
        QTest.keyClick(widget, key)
    qtbot.wait(100)
    assert window.isVisible()
    window.viewport.render()


def off_axis(window, geometry):
    width, height = window.viewport.render_size()
    return off_axis_camera(geometry, width / height)


def test_live_view_matches_camera_model(window, spread):
    window.set_display_geometry(spread)
    window.viewport.set_axes_visible(False)
    camera = off_axis(window, spread)
    window.viewport.set_camera(camera)
    width, height = window.viewport.render_size()
    rgba = window.viewport.screenshot(transparent=True)
    assert rgba.shape[:2] == (height, width)
    matches = match_spheres(camera.project(spread.positions, width, height), spread.colors,
                            find_blobs(rgba))
    assert max(m.error_px for m in matches) < 1.0, [m.error_px for m in matches]
    assert all(m.hue_ok for m in matches)


def test_missing_renderer_shows_guidance_and_export_still_works(window, monkeypatch, tmp_path):
    empty = tmp_path / "bin"
    empty.mkdir()
    monkeypatch.setenv("PATH", str(empty))
    monkeypatch.delenv(POVRAY_ENV, raising=False)
    window.settings.remove(SETTINGS_POVRAY)
    assert window.render_png(tmp_path / "out.png") is False
    title, text = window.last_error
    assert title == "POV-Ray Not Available"
    assert "sudo apt install povray" in text
    window._message_box.close()
    pov = window.export_pov(tmp_path / "exported scene ü.pov")
    assert pov.is_file() and pov.with_suffix(".ini").is_file()
    assert "#version 3.7;" in pov.read_text(encoding="utf-8")


@pytest.mark.povray
def test_render_from_gui_matches_live_view(window, spread, povray_executable, qtbot, tmp_path):
    window.settings.setValue(SETTINGS_POVRAY, povray_executable)
    window.set_display_geometry(spread)
    window.viewport.set_axes_visible(False)
    camera = off_axis(window, spread)
    window.viewport.set_camera(camera)
    width, height = window.viewport.render_size()
    window.width_spin.setValue(width)
    window.transparent_check.setChecked(True)
    assert (window.current_render_settings().width,
            window.current_render_settings().height) == (width, height)

    destination = tmp_path / "Résultat final" / "render ü.png"
    assert window.render_png(destination, show_result=False) is True
    # The call returns immediately; the event loop keeps running while POV-Ray works.
    assert window.render_finished_result is None
    qtbot.waitUntil(lambda: window.render_finished_result is not None, timeout=120_000)
    result = window.render_finished_result
    assert result.ok, result.message
    assert destination.is_file()

    pov_rgba = load_rgba(destination)
    assert pov_rgba.shape == (height, width, 4)
    vtk_rgba = window.viewport.screenshot(transparent=True)
    expected = camera.project(spread.positions, width, height)
    pov = match_spheres(expected, spread.colors, find_blobs(pov_rgba))
    vtk = match_spheres(expected, spread.colors, find_blobs(vtk_rgba))
    assert max(m.error_px for m in pov) < 1.0
    assert max(m.error_px for m in vtk) < 1.0
    for a, b in zip(pov, vtk, strict=True):
        assert np.hypot(a.found[0] - b.found[0], a.found[1] - b.found[1]) < 1.0
        assert a.hue_ok and b.hue_ok


# ----- boundary atoms, selection, hiding, undo ------------------------------------------
@pytest.fixture
def perovskite_window(qtbot):
    from ycrystal.core.samples import perovskite_srtio3

    win = MainWindow(perovskite_srtio3())
    qtbot.addWidget(win)
    win.resize(960, 640)
    win.show()
    qtbot.waitExposed(win)
    qtbot.waitUntil(lambda: win._camera_initialised, timeout=5000)
    qtbot.wait(200)
    yield win
    win.close()


def _click(widget, pixel, modifiers=Qt.KeyboardModifier.NoModifier):
    """Left click (no drag) at a device-pixel position of the viewport."""
    ratio = widget.devicePixelRatioF()
    point = QPointF(pixel[0] / ratio, pixel[1] / ratio)
    for kind, buttons in ((QEvent.Type.MouseButtonPress, Qt.MouseButton.LeftButton),
                          (QEvent.Type.MouseButtonRelease, Qt.MouseButton.NoButton)):
        QApplication.sendEvent(widget, QMouseEvent(kind, point, widget.mapToGlobal(point),
                                                   Qt.MouseButton.LeftButton, buttons,
                                                   modifiers))


def _visible_pixels(window):
    """Map displayed atom index -> pixel where it is the front-most atom."""
    width, height = window.viewport.render_size()
    pixels = window.current_camera().project(window.geometry.positions, width, height)
    return {i: tuple(p) for i, p in enumerate(pixels) if window.viewport.pick(tuple(p)) == i}


def test_perovskite_shows_boundary_atoms(perovskite_window):
    win = perovskite_window
    assert len(win.geometry) == 15
    assert win.geometry.element_counts() == {"Sr": 8, "Ti": 1, "O": 6}
    assert "15 atoms shown" in win.structure_label.text()
    assert win.boundary_action.isChecked()


def test_click_ctrl_click_and_empty_click(perovskite_window):
    win = perovskite_window
    widget = win.viewport.interactor_widget
    visible = _visible_pixels(win)
    assert len(visible) >= 2
    (first, p1), (second, p2) = list(visible.items())[:2]

    _click(widget, p1)
    assert win.selection == {win.geometry.atom_ids[first]}
    assert win.selection_text().startswith(f"Selected: {win.geometry.elements[first]}")
    assert "frac" in win.selection_text() and win.hide_action.isEnabled()
    assert win.viewport._highlight_actor is not None

    _click(widget, p2, Qt.KeyboardModifier.ControlModifier)
    assert len(win.selection) == 2 and "2 atoms" in win.selection_text()
    _click(widget, p2, Qt.KeyboardModifier.ControlModifier)
    assert win.selection == {win.geometry.atom_ids[first]}

    corner = (3.0, 3.0)
    assert win.viewport.pick(corner) is None
    _click(widget, corner)
    assert win.selection == set() and not win.hide_action.isEnabled()
    assert win.viewport._highlight_actor is None


def test_drag_does_not_select(perovskite_window):
    win = perovskite_window
    widget = win.viewport.interactor_widget
    index, pixel = next(iter(_visible_pixels(win).items()))
    ratio = widget.devicePixelRatioF()
    start = (pixel[0] / ratio, pixel[1] / ratio)
    _send_drag(widget, start, (start[0] + 40, start[1] + 10), Qt.MouseButton.LeftButton)
    assert win.selection == set()


def test_delete_hides_one_equivalent_atom_with_undo_redo(perovskite_window, qtbot, tmp_path):
    win = perovskite_window
    widget = win.viewport.interactor_widget
    positions = win.structure.positions.copy()
    visible = _visible_pixels(win)
    sr = next(i for i in visible if win.geometry.elements[i] == "Sr")
    target = win.geometry.atom_ids[sr]
    _click(widget, visible[sr])
    assert win.selection == {target}

    QTest.keyClick(widget, Qt.Key.Key_Delete)  # key sent to the 3D view itself
    assert len(win.geometry) == 14 and target not in win.geometry
    assert win.geometry.element_counts()["Sr"] == 7  # other equivalent corners stay
    assert "1 hidden" in win.structure_label.text()
    assert win.selection == set() and win.show_all_action.isEnabled()
    np.testing.assert_array_equal(win.structure.positions, positions)

    pov = win.export_pov(tmp_path / "hidden.pov").read_text(encoding="utf-8")
    source, image = target
    assert f"atom #{source + 1} Sr image {image}" not in pov
    assert "1 atoms hidden" in pov
    assert pov.count("// atom #") == 14

    QTest.keyClick(widget, Qt.Key.Key_Z, Qt.KeyboardModifier.ControlModifier)
    assert len(win.geometry) == 15 and target in win.geometry
    QTest.keyClick(widget, Qt.Key.Key_Z,
                   Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier)
    assert len(win.geometry) == 14

    win.show_all_action.trigger()
    assert len(win.geometry) == 15 and not win.show_all_action.isEnabled()
    win.undo_action.trigger()
    assert len(win.geometry) == 14


def test_escape_clears_selection(perovskite_window):
    win = perovskite_window
    widget = win.viewport.interactor_widget
    index, pixel = next(iter(_visible_pixels(win).items()))
    _click(widget, pixel)
    assert win.selection
    QTest.keyClick(widget, Qt.Key.Key_Escape)
    assert win.selection == set()


def test_boundary_toggle_is_undoable_and_keeps_hidden_ids(perovskite_window):
    win = perovskite_window
    win.select({(0, (1, 1, 1))})
    win.hide_selected()
    assert len(win.geometry) == 14
    win.boundary_action.trigger()
    assert not win.boundary_action.isChecked()
    assert len(win.geometry) == 5 and win.geometry.hidden_count == 0
    win.undo_action.trigger()
    assert win.boundary_action.isChecked()
    assert len(win.geometry) == 14 and (0, (1, 1, 1)) not in win.geometry
