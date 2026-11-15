"""FR-RENDER-01 in the window: the lock button beside Width and Height."""

import numpy as np
import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor

from ycrystal.core.samples import perovskite_srtio3
from ycrystal.gui.main_window import MainWindow
from ycrystal.gui.panels.output_panel import padlock_icon
from ycrystal.io.project import Project, load_project, project_to_dict
from ycrystal.render.pov_writer import RenderSettings

pytestmark = pytest.mark.gui


def make_window(qtbot, output=None):
    output = output or RenderSettings(2400, 1600)
    win = MainWindow(project=Project(perovskite_srtio3(), output=output))
    qtbot.addWidget(win)
    win.resize(1100, 720)
    win.show()
    qtbot.waitExposed(win)
    qtbot.waitUntil(lambda: win._saved_camera is not None, timeout=5000)
    win.preview_panel.auto_check.setChecked(False)
    return win


@pytest.fixture
def window(qtbot):
    win = make_window(qtbot)
    yield win
    win.close()


def size(window):
    panel = window.render_panel
    shown = (panel.width_spin.value(), panel.height_spin.value())
    assert shown == window.output_size()  # panel and window always agree
    return shown


def type_value(spin, value):
    """Edit a spin box as a user does (one committed value)."""
    spin.setValue(value)


# ----- interface ----------------------------------------------------------------------
def test_lock_button_defaults_and_states(window, qtbot):
    button = window.render_panel.lock_button
    assert button.isCheckable() and button.isChecked() and window.aspect_locked()
    assert button.accessibleName() == "Lock aspect ratio"
    assert "locked" in button.toolTip().lower() and "1.5" in button.toolTip()
    closed = padlock_icon(True, QColor("black")).pixmap(20, 20).toImage()
    opened = padlock_icon(False, QColor("black")).pixmap(20, 20).toImage()
    assert closed != opened  # different shapes, same colour
    button.setFocus()
    qtbot.keyClick(button, Qt.Key.Key_Space)  # keyboard access
    assert not button.isChecked() and not window.aspect_locked()
    assert "unlocked" in button.toolTip().lower() and button.text() == "Unlocked"
    qtbot.keyClick(button, Qt.Key.Key_Space)
    assert window.aspect_locked() and button.text() == "Locked"


# ----- locked ---------------------------------------------------------------------------
def test_locked_editing_links_both_dimensions(window):
    panel = window.render_panel
    type_value(panel.height_spin, 1920)
    assert size(window) == (2880, 1920)
    type_value(panel.width_spin, 3000)
    assert size(window) == (3000, 2000)
    assert window.aspect_ratio() == 1.5  # the target ratio itself is never recomputed
    assert window.viewport.output_aspect() == pytest.approx(1.5)


def test_non_integer_ratio_repeated_edits_without_drift(qtbot):
    window = make_window(qtbot, RenderSettings(1000, 700))
    try:
        panel = window.render_panel
        for width in (33, 1001, 1517, 4096, 1000):
            type_value(panel.width_spin, width)
        assert size(window) == (1000, 700)
        assert window.aspect_ratio() == 1000 / 700
        type_value(panel.height_spin, 701)
        assert size(window) == (1001, 701)  # 701 × 1.42857… = 1001.4 → 1001
        assert window.viewport.output_aspect() == pytest.approx(1001 / 701)  # actual ratio
    finally:
        window.close()


# ----- unlocked, toggling ----------------------------------------------------------------
def test_unlocked_editing_is_independent_and_relocking_captures(window):
    panel = window.render_panel
    revision, steps = window.scene_revision, window.undo_stack.count()
    panel.lock_button.click()  # unlock
    assert size(window) == (2400, 1600) and not window.aspect_locked()
    assert window.scene_revision == revision and window.undo_stack.count() == steps
    assert window.is_modified()  # saved in projects, so the project changed
    type_value(panel.height_spin, 1920)
    assert size(window) == (2400, 1920)
    type_value(panel.width_spin, 2600)
    assert size(window) == (2600, 1920)
    assert panel.aspect_combo.currentText() == "Custom"
    panel.lock_button.click()  # lock: captures 2600 / 1920, changes nothing
    assert size(window) == (2600, 1920) and window.aspect_ratio() == 2600 / 1920
    type_value(panel.height_spin, 960)
    assert size(window) == (1300, 960)


# ----- presets, Custom, Swap ---------------------------------------------------------------
def test_presets_set_the_target_when_locked(window):
    panel = window.render_panel
    assert panel.aspect_combo.currentText() == "3:2"
    panel._apply_aspect(panel.aspect_combo.findText("16:9"))
    assert size(window) == (2400, 1350) and window.aspect_ratio() == pytest.approx(16 / 9)
    assert panel.aspect_combo.currentText() == "16:9"
    type_value(panel.width_spin, 1920)
    assert size(window) == (1920, 1080)  # the preset is the new locked ratio
    window.undo_action.trigger()  # one undo step back to 3:2, ratio included
    assert size(window) == (2400, 1600) and window.aspect_ratio() == 1.5


def test_presets_apply_once_when_unlocked(window):
    panel = window.render_panel
    panel.lock_button.click()
    panel._apply_aspect(panel.aspect_combo.findText("1:1"))
    assert size(window) == (2400, 2400) and not window.aspect_locked()
    type_value(panel.height_spin, 1000)
    assert size(window) == (2400, 1000) and panel.aspect_combo.currentText() == "Custom"
    panel._apply_aspect(panel.aspect_combo.findText("Custom"))  # a state, not an action
    assert size(window) == (2400, 1000)


def test_swap_is_atomic_and_inverts_the_target(window):
    panel = window.render_panel
    requests = []
    panel.output_requested.connect(lambda *args: requests.append(args))
    revision, steps = window.scene_revision, window.undo_stack.count()
    panel.swap_button.click()
    assert requests == [(1600, 2400, pytest.approx(1 / 1.5))]  # one complete request
    assert size(window) == (1600, 2400) and window.aspect_locked()
    assert window.scene_revision == revision + 1 and window.undo_stack.count() == steps + 1
    type_value(panel.width_spin, 1000)
    assert size(window) == (1000, 1500)
    panel.lock_button.click()  # unlocked Swap keeps the lock off
    panel.swap_button.click()
    assert size(window) == (1500, 1000) and not window.aspect_locked()


# ----- limits and invalid input -------------------------------------------------------------
def test_limits_reject_the_edit_and_explain(window):
    panel = window.render_panel
    steps = window.undo_stack.count()
    type_value(panel.height_spin, 6000)  # width would be 9000 px
    assert size(window) == (2400, 1600) and window.undo_stack.count() == steps
    assert not panel.limit_label.isHidden() and "8000" in panel.limit_label.text()
    assert "8000" in window.statusBar().currentMessage()
    type_value(panel.width_spin, 8000)
    assert size(window) == (8000, 5333) and panel.limit_label.isHidden()
    panel._apply_aspect(panel.aspect_combo.findText("2:3 (portrait)"))  # 12000 px high
    assert size(window) == (8000, 5333) and "12000" in panel.limit_label.text()
    spin = panel.height_spin
    spin.lineEdit().setText("abc")
    spin.interpretText()  # invalid text: rejected by the spin box, nothing requested
    assert size(window) == (8000, 5333)


# ----- one update per edit; composition ------------------------------------------------------
def test_one_request_one_refresh_per_edit(window):
    panel = window.render_panel
    requests, aspects = [], []
    panel.output_requested.connect(lambda *args: requests.append(args))
    original = window.viewport.set_output_aspect
    window.viewport.set_output_aspect = lambda a: (aspects.append(a), original(a))[1]
    revision = window.scene_revision
    type_value(panel.width_spin, 3000)
    assert len(requests) == 1 and len(aspects) == 1  # no recursive second request
    assert window.scene_revision == revision + 1  # one debounced preview trigger
    window.viewport.set_output_aspect = original


def test_resolution_change_keeps_the_composition(window):
    camera = window.current_camera().orbit(azimuth=33, elevation=-12).roll(9).pan(0.4, -0.3)
    window.viewport.set_output_camera(camera)
    frame = window.viewport.frame_rect()
    type_value(window.render_panel.width_spin, 3600)  # 3600 × 2400, same ratio
    after = window.current_camera()
    np.testing.assert_allclose(after.position, camera.position, atol=1e-9)
    np.testing.assert_allclose(after.view_up, camera.view_up, atol=1e-9)
    assert after.parallel_scale == pytest.approx(camera.parallel_scale, rel=1e-12)
    assert window.viewport.frame_rect() == pytest.approx(frame)  # same blue frame


# ----- persistence --------------------------------------------------------------------------
def test_lock_state_is_saved_and_restored(window, qtbot, tmp_path):
    panel = window.render_panel
    panel.lock_button.click()
    type_value(panel.height_spin, 1000)
    assert window.save_as(tmp_path / "unlocked.ycrystal")
    reopened = make_window(qtbot, load_project(tmp_path / "unlocked.ycrystal").output)
    try:
        assert not reopened.aspect_locked() and not reopened.render_panel.is_locked()
        assert size(reopened) == (2400, 1000)
    finally:
        reopened.close()
    panel.lock_button.click()  # lock at 2400 / 1000
    assert window.save_as(tmp_path / "locked.ycrystal")
    project = load_project(tmp_path / "locked.ycrystal")
    assert project.output.aspect_locked and project.output.aspect_ratio == 2.4
    data = project_to_dict(project)
    assert data["output"]["aspect_ratio"] == 2.4


def test_old_projects_open_locked_to_their_own_ratio(qtbot):
    old = make_window(qtbot, RenderSettings(1000, 700))  # no lock fields: 0.1.0 default
    try:
        assert old.aspect_locked() and old.aspect_ratio() == 1000 / 700
    finally:
        old.close()
    odd = make_window(qtbot, RenderSettings(1000, 700, aspect_ratio=3.0))  # does not fit
    try:
        assert odd.aspect_ratio() == 1000 / 700
    finally:
        odd.close()
