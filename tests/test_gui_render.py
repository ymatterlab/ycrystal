"""M3 in the window: output frame, preview, final render, cancel, appearance, projects."""

import numpy as np
import pytest
from PySide6.QtWidgets import QApplication

from conftest import spread_geometry
from test_render_queue import fake_povray
from ycrystal.core.bonds import BondSettings
from ycrystal.core.camera import Camera
from ycrystal.core.samples import perovskite_srtio3
from ycrystal.core.scene import SceneSettings
from ycrystal.core.structure import Structure
from ycrystal.gui.main_window import SETTINGS_POVRAY, MainWindow
from ycrystal.io.project import load_project
from ycrystal.render.imagecheck import find_blobs, load_rgba, match_spheres
from ycrystal.render.povray import POVRAY_ENV
from ycrystal.viewport.qt_viewport import FRAME_MARGIN

pytestmark = pytest.mark.gui


def make_window(qtbot, structure=None, size=(1150, 700), project=None):
    win = MainWindow(structure or perovskite_srtio3(), project=project)
    qtbot.addWidget(win)
    win.resize(*size)
    win.show()
    qtbot.waitExposed(win)
    qtbot.waitUntil(lambda: win._saved_camera is not None, timeout=5000)
    return win


@pytest.fixture
def window(qtbot):
    win = make_window(qtbot)
    yield win
    win.close()


def separated_structure() -> Structure:
    """Six well-separated atoms without a cell or bonds (for image measurements)."""
    spread = spread_geometry()
    return Structure(
        cell=np.zeros((3, 3)),
        positions=spread.positions,
        numbers=[8, 17, 7, 26, 5, 18],
        labels=["O", "Cl", "N", "Fe", "B", "Ar"],
        pbc=(False, False, False),
    )


# ----- output frame -----------------------------------------------------------------
def test_frame_matches_output_aspect_and_survives_resize(window, qtbot):
    window.set_output_size(800, 400)
    x0, y0, w, h = window.viewport.frame_rect()
    width, height = window.viewport.render_size()
    assert w / h == pytest.approx(2.0)
    assert x0 == pytest.approx((width - w) / 2) and y0 == pytest.approx((height - h) / 2)
    assert min(x0, y0) >= min(width, height) * FRAME_MARGIN - 1e-9
    window._mark_clean()  # the new output size is now the saved state
    camera = window.current_camera()
    view_scale = window.viewport.camera().parallel_scale
    window.resize(820, 760)  # a different shape: the frame changes, the output does not
    qtbot.wait(300)
    window.viewport.render()
    after = window.current_camera()
    assert after.parallel_scale == pytest.approx(camera.parallel_scale, rel=1e-9)
    np.testing.assert_allclose(after.focal_point, camera.focal_point, atol=1e-12)
    assert window.viewport.camera().parallel_scale != pytest.approx(view_scale)
    assert not window.is_modified()  # resizing the window is not a change of the figure


def test_output_size_keeps_output_camera_and_marks_modified(window):
    camera = window.current_camera()
    window.render_panel.aspect_combo.setCurrentIndex(
        window.render_panel.aspect_combo.findText("1:1")
    )
    window.render_panel._apply_aspect(window.render_panel.aspect_combo.currentIndex())
    assert (window.width_spin.value(), window.height_spin.value()) == (1200, 1200)
    assert window.viewport.output_aspect() == pytest.approx(1.0)
    assert window.current_camera().parallel_scale == pytest.approx(camera.parallel_scale)
    assert window.is_modified() and window.undo_stack.count() == 0
    window.render_panel.swap_button.click()
    window.set_output_size(640, 480)
    assert window.output_label.text().strip() == "640 × 480 px"
    assert window.preview_settings().width == 480 and window.preview_settings().height == 360


# ----- appearance ------------------------------------------------------------------
def test_material_and_background_are_undoable(window, tmp_path):
    window.appearance_panel.material_combo.setCurrentIndex(
        window.appearance_panel.material_combo.findData("glass")
    )
    assert window.scene_settings.material == "glass"
    assert window.viewport.atom_actors["glass"].GetProperty().GetOpacity() == pytest.approx(0.4)
    pov = window.export_pov(tmp_path / "glass.pov").read_text(encoding="utf-8")
    assert "material { Ycr_Material_Sr }" in pov and "interior { ior 1.45 }" in pov
    assert "// Renderer used:" in pov
    window.set_background("dark")
    assert window.environment.preset == "dark"
    assert window.scene_settings.cell_edge_color[0] > 0.5
    window.undo_action.trigger()  # background and edge colour return together
    assert window.environment.preset == "white"
    assert window.scene_settings.cell_edge_color[0] < 0.5
    assert window.appearance_panel.background_combo.currentData() == "white"
    window.undo_action.trigger()
    assert window.scene_settings.material == "satin"


# ----- preview -----------------------------------------------------------------------
@pytest.mark.povray
def test_preview_renders_the_frame(window, qtbot, povray_executable):
    window.settings.setValue(SETTINGS_POVRAY, povray_executable)
    window.set_output_size(900, 600)
    assert window.request_preview()
    assert window.preview_panel.state == "busy" and window.cancel_action.isEnabled()
    qtbot.waitUntil(lambda: window.preview_result is not None, timeout=60_000)
    result, revision = window.preview_result
    assert result.ok and revision == window.scene_revision
    assert window.preview_panel.state == "ready" and window.preview_panel.has_image()
    assert window.preview_panel._pixmap.width() == 480
    assert window.preview_panel._pixmap.height() == 320
    window.viewport.set_output_camera(window.current_camera().orbit(azimuth=10))
    assert window.preview_panel.state == "stale"


def test_stale_preview_is_discarded(window, qtbot, tmp_path):
    window.settings.setValue(SETTINGS_POVRAY, fake_povray(tmp_path, 0.8))
    assert window.request_preview()
    window.set_material("metallic")  # the scene changes while POV-Ray is rendering
    qtbot.waitUntil(lambda: window.preview_result is not None, timeout=10_000)
    result, revision = window.preview_result
    assert result.ok and revision < window.scene_revision
    assert window.preview_discarded == 1
    assert not window.preview_panel.has_image() and window.preview_panel.state == "stale"


def test_newer_preview_supersedes_older_one(window, qtbot, tmp_path):
    window.settings.setValue(SETTINGS_POVRAY, fake_povray(tmp_path, 0.8))
    window.request_preview()
    window.viewport.set_output_camera(window.current_camera().orbit(azimuth=15))
    window.request_preview()  # cancels the first, then runs for the new revision
    qtbot.waitUntil(lambda: window.preview_panel.state == "ready", timeout=10_000)
    result, revision = window.preview_result
    assert result.ok and revision == window.scene_revision
    assert window.preview_discarded == 0


def test_automatic_preview_after_changes(window, qtbot, tmp_path):
    window.settings.setValue(SETTINGS_POVRAY, fake_povray(tmp_path, 0.1))
    window.preview_panel.auto_check.setChecked(True)
    window.set_material("matte")
    qtbot.waitUntil(lambda: window.preview_panel.state == "ready", timeout=10_000)
    assert window.preview_result[1] == window.scene_revision
    window.preview_panel.auto_check.setChecked(False)


def test_preview_without_povray_explains_without_dialog(window, monkeypatch, tmp_path):
    empty = tmp_path / "bin"
    empty.mkdir()
    monkeypatch.setenv("PATH", str(empty))
    monkeypatch.delenv(POVRAY_ENV, raising=False)
    window.settings.remove(SETTINGS_POVRAY)
    assert window.request_preview() is False
    assert window.preview_panel.state == "error"
    assert "sudo apt install povray" in window.preview_panel.status_label.text()
    assert window.last_error is None


# ----- final render: cancel and failure recovery ---------------------------------------------
def test_cancel_final_render(window, qtbot, tmp_path):
    window.settings.setValue(SETTINGS_POVRAY, fake_povray(tmp_path, 5.0))
    destination = tmp_path / "out.png"
    assert window.render_png(destination, show_result=False)
    assert window.cancel_action.isEnabled() and not window.render_action.isEnabled()
    window.cancel_action.trigger()
    qtbot.waitUntil(lambda: window.render_finished_result is not None, timeout=10_000)
    assert window.render_finished_result.cancelled
    assert not destination.exists() and window.last_error is None
    assert window.render_action.isEnabled() and not window.cancel_action.isEnabled()
    assert "cancelled" in window.statusBar().currentMessage()


@pytest.mark.povray
def test_failed_render_then_successful_render(window, qtbot, tmp_path, povray_executable):
    window.settings.setValue(SETTINGS_POVRAY, fake_povray(tmp_path, 0.1, exit_code=2))
    assert window.render_png(tmp_path / "fail.png", show_result=False)
    qtbot.waitUntil(lambda: window.render_finished_result is not None, timeout=10_000)
    assert not window.render_finished_result.ok
    assert window.last_error[0] == "Render Failed" and window.render_action.isEnabled()
    window._message_box.close()
    window.render_finished_result = None
    window.settings.setValue(SETTINGS_POVRAY, povray_executable)
    window.set_output_size(300, 200)
    assert window.render_png(tmp_path / "ok.png", show_result=False)
    qtbot.waitUntil(lambda: window.render_finished_result is not None, timeout=60_000)
    assert window.render_finished_result.ok
    assert load_rgba(tmp_path / "ok.png").shape == (200, 300, 4)


# ----- the M3 gate: a saved scene gives correctly framed preview and final images ------
@pytest.mark.povray
def test_saved_scene_renders_framed_preview_and_final(qtbot, tmp_path, povray_executable):
    first = make_window(qtbot, separated_structure(), size=(1150, 700))
    first.set_output_size(640, 400)
    # Small spheres, no bonds: every atom is a separate disc to measure.
    first.apply_scene_settings(SceneSettings(radius_scale=0.3, bonds=BondSettings(enabled=False)))
    first.set_background("transparent")
    camera = (
        Camera.looking_along((0.3, -1.0, -0.25), (0, 0, 1))
        .orbit(azimuth=-48, elevation=31)
        .roll(23)
        .fitted(*first.geometry.points_and_radii(), 640 / 400, margin=0.3)
        .pan(0.4, -0.3)
    )
    first.viewport.set_output_camera(camera)
    assert first.save_as(tmp_path / "gate.ycrystal")
    first.close()

    project = load_project(tmp_path / "gate.ycrystal")
    second = make_window(qtbot, size=(900, 820), project=project)  # another window shape
    second.settings.setValue(SETTINGS_POVRAY, povray_executable)
    out = second.current_camera()
    np.testing.assert_allclose(out.position, camera.position, rtol=1e-12)
    assert out.parallel_scale == pytest.approx(camera.parallel_scale, rel=1e-12)
    geometry = second.geometry

    assert second.request_preview()
    qtbot.waitUntil(lambda: second.preview_panel.state in ("ready", "error"), timeout=60_000)
    assert second.preview_panel.state == "ready"
    preview = second.preview_panel._pixmap.toImage()
    pw, ph = preview.width(), preview.height()
    assert (pw, ph) == (480, 300)
    preview_path = tmp_path / "preview.png"
    preview.save(str(preview_path))
    rgba = load_rgba(preview_path)
    assert rgba[0, 0, 3] == 0  # transparent background in the preview too
    matches = match_spheres(
        out.project(geometry.positions, pw, ph), geometry.colors, find_blobs(rgba)
    )
    assert max(m.error_px for m in matches) < 1.0

    destination = tmp_path / "final.png"
    assert second.render_png(destination, show_result=False)
    qtbot.waitUntil(lambda: second.render_finished_result is not None, timeout=60_000)
    assert second.render_finished_result.ok
    final = load_rgba(destination)
    assert final.shape == (400, 640, 4) and final[0, 0, 3] == 0
    matches = match_spheres(
        out.project(geometry.positions, 640, 400), geometry.colors, find_blobs(final)
    )
    assert max(m.error_px for m in matches) < 1.0
    assert all(m.hue_ok for m in matches)
    QApplication.processEvents()
    second.close()
