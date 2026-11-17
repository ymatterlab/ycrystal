"""M5 in the window: supercell handles, axis rotation, styles, radii, undo coverage."""

import numpy as np
import pytest
from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication

from ycrystal.core.samples import perovskite_srtio3, triclinic_marker
from ycrystal.gui.main_window import MainWindow
from ycrystal.gui.style_dialog import StyleImportChoice
from ycrystal.io.project import Project, load_project
from ycrystal.io.style import STYLE_PARTS, load_style


def style_parts():
    return STYLE_PARTS


pytestmark = pytest.mark.gui


def make_window(qtbot, structure=None):
    win = MainWindow(project=Project(structure or perovskite_srtio3()))
    qtbot.addWidget(win)
    win.resize(1150, 760)
    win.show()
    qtbot.waitExposed(win)
    qtbot.waitUntil(lambda: win._saved_camera is not None, timeout=5000)
    return win


@pytest.fixture
def window(qtbot):
    win = make_window(qtbot)
    yield win
    win.close()


def _mouse(widget, kind, pixel, buttons, button=Qt.MouseButton.LeftButton, modifiers=None):
    ratio = widget.devicePixelRatioF()
    point = QPointF(pixel[0] / ratio, pixel[1] / ratio)
    QApplication.sendEvent(
        widget,
        QMouseEvent(
            kind,
            point,
            widget.mapToGlobal(point),
            button,
            buttons,
            modifiers or Qt.KeyboardModifier.NoModifier,
        ),
    )


def drag(widget, start, end, steps=6, release=True):
    """Left drag in device pixels, with intermediate moves."""
    left = Qt.MouseButton.LeftButton
    _mouse(widget, QEvent.Type.MouseButtonPress, start, left)
    for t in np.linspace(0, 1, steps + 1)[1:]:
        point = np.asarray(start) + t * (np.asarray(end) - np.asarray(start))
        _mouse(widget, QEvent.Type.MouseMove, point, left, Qt.MouseButton.NoButton)
    if release:
        _mouse(widget, QEvent.Type.MouseButtonRelease, end, Qt.MouseButton.NoButton)


# ----- M5a: supercell handles ------------------------------------------------------------
def test_handle_drag_adds_cells_in_one_undo_step(window):
    viewport, widget = window.viewport, window.viewport.interactor_widget
    handles = viewport.handle_positions()
    assert set(handles) == {0, 1, 2}  # a, b, c handles on the cubic cell
    centre, step = viewport._handle_screen[0]
    seen = []
    viewport.supercell_drag_changed.connect(seen.append)
    camera = window.current_camera()
    steps_before = window.undo_stack.count()
    drag(widget, centre, centre + 2.1 * step, release=False)
    assert viewport.is_dragging_handle() and seen[-1] == (3, 1, 1)
    assert window.current_camera() == camera  # no orbit while dragging a handle
    assert "3 × 1 × 1 cells" in viewport._drag_text.GetInput()
    assert window.scene_settings.repetitions == (1, 1, 1)  # applied only on release
    _mouse(widget, QEvent.Type.MouseButtonRelease, centre + 2.1 * step, Qt.MouseButton.NoButton)
    assert window.scene_settings.repetitions == (3, 1, 1)
    assert window.undo_stack.count() == steps_before + 1
    assert window.scene_panel.rep_spins[0].value() == 3  # numeric controls follow
    window.undo_action.trigger()
    assert window.scene_settings.repetitions == (1, 1, 1)
    window.redo_action.trigger()
    assert window.scene_settings.repetitions == (3, 1, 1)


def test_handle_drag_clamps_cancels_and_hides(window, qtbot):
    viewport, widget = window.viewport, window.viewport.interactor_widget
    window.set_repetitions((2, 2, 2))
    centre, step = viewport._handle_screen[1]
    steps = window.undo_stack.count()
    drag(widget, centre, centre - 5.0 * step)  # cannot go below one cell
    assert window.scene_settings.repetitions == (2, 1, 2)
    centre, step = viewport._handle_screen[2]
    drag(widget, centre, centre + 1.2 * step, release=False)
    window.select_none_action.trigger()  # Esc: cancels the drag, keeps the selection
    assert not viewport.is_dragging_handle()
    _mouse(widget, QEvent.Type.MouseButtonRelease, centre + 1.2 * step, Qt.MouseButton.NoButton)
    assert window.scene_settings.repetitions == (2, 1, 2)  # cancelled: unchanged
    assert window.undo_stack.count() == steps + 1
    window.handles_action.trigger()  # View ▸ Supercell Handles off
    assert viewport.handle_positions() == {}
    window.handles_action.trigger()
    assert len(viewport.handle_positions()) == 3
    viewport.set_frame_visible(False)  # screenshots for comparisons hide all overlays
    assert viewport.handle_positions() == {}


def test_no_handles_without_cell(qtbot):
    from ycrystal.core.structure import Structure

    molecule = Structure(
        cell=np.zeros((3, 3)),
        positions=[[0, 0, 0], [1.2, 0, 0]],
        numbers=[6, 8],
        labels=("C", "O"),
        pbc=(False, False, False),
    )
    win = make_window(qtbot, molecule)
    try:
        assert win.viewport.handle_positions() == {}
        index = win.rotation_combo.findData("a")
        assert not win.rotation_combo.model().item(index).isEnabled()
        win.set_rotation_mode("a")  # falls back to free rotation
        assert win.rotation_mode() == "free"
    finally:
        win.close()


# ----- M5b: axis-constrained rotation -------------------------------------------------------
def test_axis_rotation_keeps_the_axis_fixed(window):
    viewport, widget = window.viewport, window.viewport.interactor_widget
    window.set_rotation_mode("c")
    c = window.structure.cell[2] / np.linalg.norm(window.structure.cell[2])
    before = window.viewport.camera()
    width, height = viewport.render_size()
    start = (width * 0.3, height * 0.85)  # away from the handles
    drag(widget, start, (start[0] + 120, start[1] + 40))
    after = viewport.camera()
    np.testing.assert_allclose(np.array(after.basis()) @ c, np.array(before.basis()) @ c, atol=1e-9)
    assert not np.allclose(after.basis()[2], before.basis()[2])  # the view did turn
    np.testing.assert_array_equal(window.structure.positions, perovskite_srtio3().positions)
    # Free rotation turns about other axes too.
    window.set_rotation_mode("free")
    drag(widget, start, (start[0] + 100, start[1] - 80))
    moved = viewport.camera()
    assert not np.allclose(np.array(moved.basis()) @ c, np.array(after.basis()) @ c, atol=1e-3)


def test_rotate_buttons_turn_by_the_step(window):
    window.set_rotation_mode("z")
    window.view_along("x")
    window.step_combo.setCurrentIndex(window.step_combo.findData(90))
    before = window.viewport.camera().basis()[2]
    window.rotate_ccw_action.trigger()
    after = window.viewport.camera().basis()[2]
    assert after @ before == pytest.approx(0.0, abs=1e-9)  # 90° about z
    assert after[2] == pytest.approx(before[2], abs=1e-9)
    window.rotate_cw_action.trigger()
    np.testing.assert_allclose(window.viewport.camera().basis()[2], before, atol=1e-9)
    window.set_rotation_mode("free")
    up = window.viewport.camera().basis()[1]
    window.step_combo.setCurrentIndex(window.step_combo.findData(30))
    window.rotate_ccw_action.trigger()  # free: about the line of sight
    assert window.viewport.camera().basis()[1] @ up == pytest.approx(np.cos(np.radians(30)))


def test_click_still_selects_in_axis_mode(window):
    window.set_rotation_mode("a")
    width, height = window.viewport.render_size()
    camera = window.viewport.camera()
    pixels = camera.project(window.geometry.positions, width, height)
    index = next(i for i, p in enumerate(pixels) if window.viewport.pick(tuple(p)) == i)
    widget = window.viewport.interactor_widget
    _mouse(widget, QEvent.Type.MouseButtonPress, pixels[index], Qt.MouseButton.LeftButton)
    _mouse(widget, QEvent.Type.MouseButtonRelease, pixels[index], Qt.MouseButton.NoButton)
    assert window.selection == {window.geometry.atom_ids[index]}
    assert window.viewport.camera() == camera


# ----- M5c: styles and undo coverage --------------------------------------------------------
def test_style_export_import_to_another_structure(window, qtbot, tmp_path):
    window.set_material("ceramic")
    window.set_element_material("O", "glass")
    window.set_element_material("Ti", "gold")
    window.set_element_color("O", (0.1, 0.3, 0.95))
    window.select({(0, (0, 0, 0))})
    window.set_selection_material("chrome")
    window.set_background("studio_grey")
    window.set_output_size(800, 600)
    window.set_radius_scale(0.35)
    path = window.export_style(tmp_path / "look")
    assert path.name == "look.ycstyle" and load_style(path).source_name == "SrTiO3"

    target = make_window(qtbot, triclinic_marker())
    asked = []
    target.ask_style_import = lambda style: asked.append(style) or StyleImportChoice(style_parts())
    try:
        positions = target.structure.positions.copy()
        steps = target.undo_stack.count()
        assert target.import_style(path)  # parts from the (patched) dialog
        assert asked and not asked[0].is_compatible(target.structure)
        assert target.undo_stack.count() == steps + 1  # one undoable step
        settings = target.scene_settings
        assert settings.material == "ceramic" and settings.radius_scale == 0.35
        assert settings.element_materials == (("O", "glass"),)
        assert settings.atom_materials == ()
        assert target.environment.preset == "studio_grey"
        assert target.output_size() == (800, 600)
        assert target.last_info is not None and "Ti" in target.last_info[1]
        assert "per-atom material override" in target.last_info[1]
        np.testing.assert_array_equal(target.structure.positions, positions)
        target._message_box.close()
        target.undo_action.trigger()  # everything returns, including the output size
        assert target.scene_settings.material == "satin"
        assert target.environment.preset == "white" and target.output_size() == (1200, 800)
        # Parts can be chosen; nothing else changes.
        target.import_style(path, parts=["output"])
        assert target.output_size() == (800, 600) and target.scene_settings.material == "satin"
    finally:
        target.close()


def test_bad_style_file_shows_error(window, tmp_path):
    bad = tmp_path / "bad.ycstyle"
    bad.write_text("{}")
    assert window.import_style(bad, parts=["appearance"]) is False
    assert window.last_error[0] == "Import Style Failed"


def test_radius_controls_and_project_round_trip(window, qtbot, tmp_path):
    window.scene_panel.size_spin.setValue(0.3)
    assert window.scene_settings.radius_scale == pytest.approx(0.3)
    spin = window.appearance_panel.radius_spin("Ti")
    spin.setValue(0.9)
    spin.setValue(1.0)  # consecutive edits of one element merge
    assert dict(window.scene_settings.element_radii) == {"Ti": 1.0}
    ti = window.geometry.elements.index("Ti")
    assert window.geometry.radii[ti] == pytest.approx(1.0)
    assert window.undo_stack.undoText() == "Radius of Ti: 1.00 Å"
    window.undo_action.trigger()
    assert window.scene_settings.element_radii == ()
    window.redo_action.trigger()
    assert window.save_as(tmp_path / "radii.ycrystal")
    project = load_project(tmp_path / "radii.ycrystal")
    assert project.scene == window.scene_settings
    _, reset, _ = window.appearance_panel.element_widgets("Ti")
    reset.click()  # colour and radius back to the defaults in one step
    assert window.scene_settings.element_radii == ()


def test_every_presentation_change_is_undoable(window):
    """Complete undo coverage: each change is one step and undo restores the state."""
    corner = (0, (1, 1, 1))
    changes = [
        lambda w: (w.select({corner}), w.hide_selected()),
        lambda w: w.show_all_atoms(),
        lambda w: w.set_boundary_images(False),
        lambda w: w.set_repetitions((2, 1, 1)),
        lambda w: w.set_cell_mode("outline"),
        lambda w: w.set_bonds_enabled(False),
        lambda w: w.set_bonds_enabled(True),
        lambda w: w.set_bond_tolerance(1.3),
        lambda w: w.set_bond_radius(0.2),
        lambda w: w.set_bond_pair(("O", "Ti"), False),
        lambda w: w.set_radius_scale(0.42),
        lambda w: w.set_element_radius("O", 0.5),
        lambda w: w.set_element_color("Sr", (0.5, 0.5, 0.1)),
        lambda w: w.set_material("matte"),
        lambda w: w.set_element_material("Ti", "chrome"),
        lambda w: w.set_atom_material({(1, (0, 0, 0))}, "jade"),
        lambda w: w.clear_atom_materials(),
        lambda w: w.set_background("sky_clear"),
        lambda w: w.set_lighting("top"),
        lambda w: w.set_output_size(640, 640),
    ]

    def state(w):
        return (w.scene_settings, w.environment, w.output_size())

    for change in changes:
        before = state(window)
        count = window.undo_stack.count()
        change(window)
        after = state(window)
        assert after != before, change
        assert window.undo_stack.count() == count + 1, window.undo_stack.undoText()
        window.undo_action.trigger()
        assert state(window) == before, window.undo_stack.redoText()
        window.redo_action.trigger()
        assert state(window) == after
