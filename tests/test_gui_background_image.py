"""FR-BGIMAGE-01 in the window: choosing, framing, undo, notices, previews, projects, styles."""

from dataclasses import replace

import pytest

from test_background_image import quadrants
from test_render_queue import fake_povray
from ycrystal.core.samples import perovskite_srtio3
from ycrystal.gui.main_window import SETTINGS_POVRAY, MainWindow
from ycrystal.io import images
from ycrystal.io.package import is_package

pytestmark = pytest.mark.gui


@pytest.fixture
def picture(tmp_path):
    path = tmp_path / "my photos" / "Ölbild 1.png"
    path.parent.mkdir()
    quadrants(60, 40).save(path)
    return path


def make_window(qtbot):
    win = MainWindow(perovskite_srtio3())
    qtbot.addWidget(win)
    win.resize(1150, 700)
    win.show()
    qtbot.waitExposed(win)
    qtbot.waitUntil(lambda: win._saved_camera is not None, timeout=5000)
    win.preview_panel.auto_check.setChecked(False)
    return win


@pytest.fixture
def win(qtbot):
    window = make_window(qtbot)
    yield window
    window.ask_save_changes = lambda: "discard"
    window.close()


def test_choose_image_is_one_undoable_step_that_changes_nothing_else(win, picture):
    panel = win.appearance_panel
    camera, size, bounds = win.current_camera(), win.output_size(), win.geometry.bounding_sphere()
    revision = win.scene_revision
    assert not panel.fit_combo.isVisibleTo(panel)  # picture controls only for Image
    assert win.choose_background_image(picture)
    env = win.environment
    assert env.background_mode == "image" and env.image.name == "Ölbild 1.png"
    assert (env.image.width, env.image.height, env.image.fit) == (60, 40, "fill")
    assert win.undo_stack.count() == 1 and win.is_modified()
    assert win.scene_revision > revision and not win.preview_queue.is_busy()
    assert panel.fit_combo.isVisibleTo(panel) and panel.mode_combo.currentData() == "image"
    assert panel.image_label.text() == "Ölbild 1.png — 60 × 40 px"
    assert panel.top_label.text() == "Margin"
    assert win.current_camera() == camera and win.output_size() == size
    assert win.geometry.bounding_sphere()[1] == pytest.approx(bounds[1])
    live = win.viewport._plotter.renderer.GetBackground()  # the picture's mean colour
    assert live == pytest.approx(env.image.mean_color, abs=1 / 255)
    win.undo_action.trigger()
    assert win.environment.background_mode == "solid" and win.environment.image is None
    win.redo_action.trigger()
    assert win.environment == env


def test_framing_controls_merge_reset_remove_and_replace(win, picture, tmp_path):
    panel = win.appearance_panel
    win.choose_background_image(picture)
    steps = win.undo_stack.count()
    panel.zoom_spin.setValue(120)
    panel.zoom_spin.setValue(150)  # continuous adjustment: one step
    assert win.environment.image.zoom == 1.5 and win.undo_stack.count() == steps + 1
    panel.offset_x_spin.setValue(-20)
    panel.offset_y_spin.setValue(30)
    panel.brightness_spin.setValue(80)
    panel.fit_combo.setCurrentIndex(panel.fit_combo.findData("fit"))
    image = win.environment.image
    assert (image.offset_x, image.offset_y, image.brightness, image.fit) == (-0.2, 0.3, 0.8, "fit")
    other = tmp_path / "second.png"
    quadrants(30, 30).save(other)
    assert win.choose_background_image(other)  # replace keeps the framing
    replaced = win.environment.image
    assert replaced.asset != image.asset and (replaced.zoom, replaced.fit) == (1.5, "fit")
    panel.reset_framing_button.click()
    assert win.environment.image == replaced.reset_framing()
    panel.image_remove_button.click()
    assert win.environment.image is None and win.environment.background_mode == "image"
    assert panel.image_choose_button.text() == "Choose Image…"
    for _ in range(3):  # remove, reset, replace undone: the replaced picture's state
        win.undo_action.trigger()
    assert win.environment.image == image  # undo still finds the first picture


def test_unusable_file_keeps_the_current_background(win, picture, tmp_path):
    win.choose_background_image(picture)
    env, steps = win.environment, win.undo_stack.count()
    bad = tmp_path / "broken.jpg"
    bad.write_bytes(b"\xff\xd8 not really a jpeg")
    assert not win.choose_background_image(bad)
    assert win.last_error[0] == "Cannot Use This Picture"
    assert win.environment == env and win.undo_stack.count() == steps


def test_floor_and_transparency_notices_and_presets(win, picture):
    panel = win.appearance_panel
    win.choose_background_image(picture)
    win.set_environment(replace(win.environment, floor=True), "Floor")
    assert panel.floor_off_button.isVisibleTo(panel)
    assert "floor covers the picture" in panel.image_note.text()
    panel.floor_off_button.click()
    assert not win.environment.floor and not panel.floor_off_button.isVisibleTo(panel)
    win.set_environment(replace(win.environment, transparent=True), "Transparent")
    assert "left out of renders" in panel.image_note.text()
    assert win.environment.image is not None  # kept for later
    image = win.environment.image
    win.set_background("studio_grey")
    assert win.environment.background_mode != "image" and win.environment.image == image
    panel.mode_combo.setCurrentIndex(panel.mode_combo.findData("image"))
    assert win.environment.background_mode == "image" and win.environment.image == image


def test_framing_change_discards_a_running_preview(win, picture, qtbot, tmp_path):
    win.settings.setValue(SETTINGS_POVRAY, fake_povray(tmp_path, 0.8))
    win.choose_background_image(picture)
    assert win.request_preview()
    win.appearance_panel.zoom_spin.setValue(200)  # while the preview renders
    qtbot.waitUntil(lambda: win.preview_result is not None, timeout=10_000)
    assert win.preview_discarded == 1 and not win.preview_panel.has_image()


def test_project_style_and_export_carry_the_picture(win, picture, qtbot, tmp_path):
    win.choose_background_image(picture)
    win.appearance_panel.zoom_spin.setValue(130)
    env = win.environment
    project = tmp_path / "saved figures" / "fig ü.ycrystal"
    assert win.save_as(project) and is_package(project)
    style = win.export_style(tmp_path / "look.ycstyle")
    assert is_package(style)
    (tmp_path / "export").mkdir()
    pov = win.export_pov(tmp_path / "export" / "scene.pov")
    staged = pov.parent / images.asset_filename(env.image.asset, "png")
    assert staged.is_file() and "with the background picture" in win.statusBar().currentMessage()
    picture.unlink()
    images._REGISTRY.clear()  # as in a new session
    second = make_window(qtbot)
    try:
        assert second.open_file(project)
        assert second.environment == env and not second.is_modified()
        images._REGISTRY.clear()
        third = make_window(qtbot)
        assert third.import_style(style, parts=("environment",))
        assert third.environment == env
        third.ask_save_changes = lambda: "discard"
        third.close()
    finally:
        second.ask_save_changes = lambda: "discard"
        second.close()
