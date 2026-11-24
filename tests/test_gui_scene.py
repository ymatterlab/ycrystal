"""M2 interactions in the window: repetitions, bonds, cell edges, view directions."""

import numpy as np
import pytest
from PySide6.QtCore import QPointF, Qt
from PySide6.QtTest import QTest

from ycrystal.core.annotation import TextAnnotation
from ycrystal.core.camera import ViewPolicy
from ycrystal.core.polyhedra import PolyhedronRule
from ycrystal.core.samples import perovskite_srtio3, triclinic_marker
from ycrystal.gui.main_window import SOFT_LIMIT_ATOMS, MainWindow

pytestmark = pytest.mark.gui


def make_window(qtbot, structure):
    win = MainWindow(structure)
    qtbot.addWidget(win)
    win.resize(1100, 650)
    win.show()
    qtbot.waitExposed(win)
    qtbot.waitUntil(lambda: win._saved_camera is not None, timeout=5000)
    return win


@pytest.fixture
def window(qtbot):
    win = make_window(qtbot, perovskite_srtio3())
    yield win
    win.close()


def all_visible(win) -> bool:
    width, height = win.viewport.render_size()
    pixels = win.viewport.vtk_project(win.geometry.positions)
    return bool(np.all((pixels > 0) & (pixels < (width, height))))


def test_selected_bond_buttons_change_one_periodic_pair_and_undo(window):
    panel = window.scene_panel
    assert not panel.selected_bond_hide.isEnabled()
    pair = ((1, (0, 0, 0)), (2, (0, 0, 0)))
    window.select(set(pair))
    count = len(window.geometry.bonds)
    panel.selected_bond_hide.click()
    assert window.scene_settings.bond_overrides == ((pair, False),)
    assert len(window.geometry.bonds) == count - 1
    window.undo_stack.undo()
    assert len(window.geometry.bonds) == count
    window.undo_stack.redo()
    panel.selected_bond_auto.click()
    assert len(window.geometry.bonds) == count
    assert not window.scene_settings.bond_overrides


def test_click_a_bond_and_delete_only_that_bond(window):
    geometry = window.geometry
    points = geometry.positions[geometry.bonds].mean(axis=1)
    pixels = window.viewport.vtk_project(points)
    pixel = next(p for p in pixels if window.viewport.pick_bond(tuple(p)) is not None)
    index = window.viewport.pick_bond(tuple(pixel))
    pair = tuple(geometry.atom_ids[row] for row in geometry.bonds[index])

    window.scene_panel.bond_selection_check.setChecked(True)
    widget = window.viewport.interactor_widget
    window.viewport.handle_click(QPointF(*(pixel / widget.devicePixelRatioF())), False)
    assert window.selected_bond == pair
    assert not window.selection and window.viewport._bond_highlight_actor is not None
    QTest.keyClick(widget, Qt.Key.Key_Delete)
    assert window.scene_settings.bond_overrides == ((pair, False),)
    assert len(window.geometry.bonds) == len(geometry.bonds) - 1
    assert window.selected_bond is None and window.viewport._bond_highlight_actor is None
    assert window.undo_stack.count() == 1
    window.undo_stack.undo()
    np.testing.assert_array_equal(window.geometry.bonds, geometry.bonds)
    window.set_measurement_mode("distance")
    assert not window.scene_panel.bond_selection_check.isChecked()


def test_polyhedra_and_figure_text_are_optional_live_overlays(window):
    assert not window.viewport.polyhedron_actors
    assert not window.viewport._annotation_actor.GetVisibility()
    window.set_polyhedra((PolyhedronRule("Ti", "O"),))
    assert len(window.geometry.polyhedra) == 1
    assert len(window.viewport.polyhedron_actors) == 2
    assert all(not actor.GetPickable() for actor in window.viewport.polyhedron_actors)

    camera = window.current_camera()
    geometry = window.geometry
    window.set_annotations((TextAnnotation("SrTiO₃"),))
    assert window.viewport._annotation_actor.GetVisibility()
    assert window.geometry is geometry and window.current_camera() == camera
    window.undo_stack.undo()
    assert not window.viewport._annotation_actor.GetVisibility()
    window.undo_stack.undo()
    assert not window.viewport.polyhedron_actors


def test_repetition_spin_boxes_undo_redo_and_refit(window):
    panel = window.scene_panel
    positions = window.structure.positions.copy()
    window.select({(0, (1, 1, 1))})
    panel.rep_spins[0].setValue(2)
    panel.rep_spins[1].setValue(3)
    assert window.scene_settings.repetitions == (2, 3, 1)
    assert window.geometry.element_counts()["Ti"] == 6
    assert "2 × 3 × 1 cells" in window.structure_label.text()
    assert "Showing" in panel.counts_label.text() and "2 × 3 × 1" in panel.counts_label.text()
    assert all_visible(window)  # the view was refitted to the larger block
    assert window.selection == {(0, (1, 1, 1))}  # selection kept by stable ID
    assert window.undo_stack.count() == 2
    window.undo_action.trigger()
    assert window.scene_settings.repetitions == (2, 1, 1)
    assert panel.repetitions() == (2, 1, 1)  # panel follows undo
    window.redo_action.trigger()
    assert panel.repetitions() == (2, 3, 1)
    np.testing.assert_array_equal(window.structure.positions, positions)


def test_all_axis_buttons_and_reset(window):
    panel = window.scene_panel
    panel.all_plus.click()
    panel.all_plus.click()
    assert window.scene_settings.repetitions == (3, 3, 3)
    panel.all_minus.click()
    assert window.scene_settings.repetitions == (2, 2, 2)
    panel.reset_button.click()
    assert window.scene_settings.repetitions == (1, 1, 1)
    panel.all_minus.click()  # one-cell minimum: no change, no undo step
    assert window.undo_stack.count() == 4


def test_large_expansion_asks_first(window, monkeypatch):
    asked = []
    monkeypatch.setattr(window, "ask_confirm", lambda title, text: asked.append(text) or False)
    assert window.set_repetitions((16, 16, 16)) is False
    assert asked and f"{SOFT_LIMIT_ATOMS:,}" in asked[0]
    assert window.scene_settings.repetitions == (1, 1, 1)
    assert window.scene_panel.repetitions() == (1, 1, 1)
    monkeypatch.setattr(window, "ask_confirm", lambda title, text: True)
    assert window.set_repetitions((16, 16, 16))
    assert len(window.geometry) > SOFT_LIMIT_ATOMS
    assert window.set_repetitions((2, 2, 2))  # small changes never ask
    monkeypatch.setattr(window, "ask_confirm", lambda *a: pytest.fail("asked for 2x2x2"))
    assert window.set_repetitions((3, 2, 2))


def test_bond_pairs_tolerance_and_visibility(window):
    panel = window.scene_panel
    assert len(window.geometry.bonds) == 30
    items = {
        panel.pair_list.item(i).text().split()[0]: panel.pair_list.item(i)
        for i in range(panel.pair_list.count())
    }
    assert items["O–Sr"].checkState() == Qt.CheckState.Checked
    assert items["Sr–Ti"].checkState() == Qt.CheckState.Unchecked
    items["O–Sr"].setCheckState(Qt.CheckState.Unchecked)
    assert len(window.geometry.bonds) == 6
    window.undo_action.trigger()
    assert len(window.geometry.bonds) == 30

    start = window.undo_stack.index()
    panel.tolerance_spin.setValue(1.20)
    panel.tolerance_spin.setValue(1.30)
    assert window.scene_settings.bonds.tolerance == pytest.approx(1.30)
    assert window.undo_stack.index() == start + 1  # consecutive edits merge
    window.undo_action.trigger()
    assert window.scene_settings.bonds.tolerance == pytest.approx(1.10)

    panel.radius_spin.setValue(0.2)
    assert window.geometry.bond_radius == pytest.approx(0.2)
    panel.bonds_check.setChecked(False)
    assert len(window.geometry.bonds) == 0 and not panel.pair_list.isEnabled()


def test_cell_edge_modes_from_panel(window):
    panel = window.scene_panel
    window.set_repetitions((2, 2, 2))
    assert len(window.geometry.cell_edges) == 27
    panel.cell_combo.setCurrentIndex(panel.cell_combo.findData("outline"))
    assert len(window.geometry.cell_edges) == 12
    panel.cell_combo.setCurrentIndex(panel.cell_combo.findData("none"))
    assert len(window.geometry.cell_edges) == 0
    window.undo_action.trigger()
    assert window.scene_settings.cell_mode == "outline" and window.scene_settings.show_cell


@pytest.mark.parametrize(
    "axis, toward, right, up",
    [
        ("a", (1, 0, 0), (0, 1, 0), (0, 0, 1)),
        ("b", (0, 1, 0), (-1, 0, 0), (0, 0, 1)),
        ("c", (0, 0, 1), (1, 0, 0), (0, 1, 0)),
        ("x", (1, 0, 0), (0, 1, 0), (0, 0, 1)),
        ("z", (0, 0, 1), (1, 0, 0), (0, 1, 0)),
    ],
)
def test_view_along_cubic_axes(window, axis, toward, right, up):
    window.view_along(axis)
    r, u, d = window.current_camera().basis()
    np.testing.assert_allclose(-d, toward, atol=1e-12)  # the axis points at the viewer
    np.testing.assert_allclose(r, right, atol=1e-12)
    np.testing.assert_allclose(u, up, atol=1e-12)
    assert all_visible(window)
    window.view_along(axis, reverse=True)
    np.testing.assert_allclose(window.current_camera().basis()[2], toward, atol=1e-12)


def test_view_along_triclinic_axes(qtbot):
    win = make_window(qtbot, triclinic_marker())
    cell = win.structure.cell
    for index, axis in enumerate("abc"):
        win.view_along(axis)
        d = win.current_camera().basis()[2]
        np.testing.assert_allclose(-d, cell[index] / np.linalg.norm(cell[index]), atol=1e-12)
        assert all_visible(win)
    win.close()


def test_view_buttons_and_command_line_views_agree(qtbot):
    """FR-CAMERA-01: the window and `ycrystal --view` share one camera rule."""
    win = make_window(qtbot, triclinic_marker())
    points, radii = win.geometry.points_and_radii()
    for axis in "abcxyz":
        win.view_along(axis)
        shown = win.current_camera()
        expected = ViewPolicy(view=axis).resolve(
            None, points, radii, win.viewport.output_aspect(), win.structure.cell
        )
        for a, b in zip(shown.basis(), expected.basis(), strict=True):
            np.testing.assert_allclose(a, b, atol=1e-9)
        # Same image: the focal points may differ only along the viewing direction
        # (depth), which does not change an orthographic image.
        offset = np.subtract(shown.focal_point, expected.focal_point)
        direction = expected.basis()[2]
        np.testing.assert_allclose(offset - (offset @ direction) * direction, 0, atol=1e-6)
        assert shown.parallel_scale == pytest.approx(expected.parallel_scale, rel=1e-6)
    win.close()


def test_scene_settings_survive_save_and_reopen(window, qtbot, tmp_path):
    window.set_repetitions((2, 2, 1))
    window.set_bond_pair(("O", "Sr"), False)
    window.set_cell_mode("outline")
    assert window.save_as(tmp_path / "m2.ycrystal")
    other = make_window(qtbot, perovskite_srtio3())
    assert other.open_file(tmp_path / "m2.ycrystal")
    assert other.scene_settings == window.scene_settings
    assert other.scene_panel.repetitions() == (2, 2, 1)
    assert len(other.geometry.bonds) == len(window.geometry.bonds)
    assert not other.is_modified()
    other.close()
