"""FR-MEASURE-01 in the window: modes, picking, the Measurements panel, invalidation."""

import json
from dataclasses import replace

import numpy as np
import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtTest import QTest

from test_gui import _click, _send_drag
from ycrystal.core import measure
from ycrystal.core.samples import perovskite_srtio3
from ycrystal.gui.main_window import MainWindow, _same_camera
from ycrystal.io.project import Project
from ycrystal.render.pov_writer import scene_to_pov

pytestmark = pytest.mark.gui
A = 3.905


@pytest.fixture
def win(qtbot):
    window = MainWindow(perovskite_srtio3())
    qtbot.addWidget(window)
    window.resize(1150, 700)
    window.show()
    qtbot.waitExposed(window)
    qtbot.waitUntil(lambda: window._camera_initialised, timeout=5000)
    window.preview_panel.auto_check.setChecked(False)
    # Small balls and an oblique view, so that every atom can be clicked.
    window.apply_scene_settings(replace(window.scene_settings, radius_scale=0.18))
    window.viewport.set_output_camera(window.current_camera().orbit(azimuth=25, elevation=20))
    qtbot.wait(100)
    assert len(_visible_pixels(window)) == len(window.geometry)
    yield window
    window.ask_save_changes = lambda: "discard"
    window.close()


def _visible_pixels(win):
    """Map displayed atom index -> device pixel where it is front-most (view camera)."""
    width, height = win.viewport.render_size()
    pixels = win.viewport.camera().project(win.geometry.positions, width, height)
    return {i: tuple(p) for i, p in enumerate(pixels) if win.viewport.pick(tuple(p)) == i}


def click_atom(win, atom_id, modifiers=Qt.KeyboardModifier.NoModifier):
    """Click the displayed atom ``atom_id`` where it is front-most (real mouse events)."""
    index = win.geometry.index_of(atom_id)
    pixel = _visible_pixels(win).get(index)
    assert pixel is not None, f"{atom_id} is hidden behind other atoms in this view"
    _click(win.viewport.interactor_widget, pixel, modifiers)


def visible_ids(win):
    return [win.geometry.atom_ids[i] for i in _visible_pixels(win)]


def snapshot(win):
    camera = win.current_camera()
    settings = win.current_render_settings()
    return (
        camera,
        win.viewport.camera(),
        scene_to_pov(win.geometry, camera, win.environment, settings),
        win.geometry.bounding_sphere()[1],
        win.viewport.lighting_rig().key.position.tolist(),
        win.undo_stack.count(),
        win.is_modified(),
        win.scene_settings,
    )


def test_modes_are_discoverable_and_exclusive(win):
    edit = [a.text() for a in win.menuBar().actions()[1].menu().actions()]
    assert "Measure Distance" in edit and "Measure Bond Angle" in edit
    assert win.measure_distance_action.iconText() == "Distance"
    assert win.measure_angle_action.iconText() == "Bond angle"
    win.measure_distance_action.trigger()
    assert win.measurement_mode() == "distance" and win.measure_distance_action.isChecked()
    assert win.measure_label.text().strip() == "Distance: select atom A"
    win.measure_angle_action.trigger()
    assert win.measurement_mode() == "angle" and not win.measure_distance_action.isChecked()
    assert "Bond angle: select atom A" in win.measure_label.text()
    win.measure_angle_action.trigger()  # clicking the active mode leaves it
    assert win.measurement_mode() is None and win.measure_label.text() == ""


def test_distance_by_clicks_reveals_the_panel(win):
    before = snapshot(win)
    size = win.size()
    viewport_height = win.viewport.height()
    assert not win.measure_dock.isVisible()
    ti = (1, (0, 0, 0))
    o = next(i for i in visible_ids(win) if i[0] in (2, 3, 4))  # every O is a/2 from Ti
    win.set_measurement_mode("distance")
    click_atom(win, ti)
    assert "select atom B" in win.measure_label.text()
    assert len(win.viewport.measurement_actors) == 2  # cage + label A
    click_atom(win, o)
    (result,) = win.measurements.results
    assert result.atoms == (ti, o) and result.value == pytest.approx(A / 2, abs=1e-12)
    assert win.measure_dock.isVisible()  # revealed on the first completed measurement
    (row,) = win.measure_panel.rows()
    assert (row.kind, row.result) == ("Distance", "1.9525 Å")
    assert row.atoms == f"A: Ti #2 [0 0 0] · B: {measure.atom_text(win.structure, o)}"
    assert "next: Distance: select atom A" in win.measure_label.text()  # still in the mode
    # The panel takes height from the 3D view, below it; the window does not grow.
    assert win.size() == size and win.viewport.height() < viewport_height
    view_bottom = win.viewport.mapToGlobal(QPoint(0, win.viewport.height())).y()
    assert win.measure_dock.mapToGlobal(QPoint(0, 0)).y() >= view_bottom - 1  # not covering
    assert win.scene_dock.geometry().right() == win.preview_dock.geometry().right()
    # Measuring changed neither the camera, the export, bounds, lights, nor the figure.
    after = snapshot(win)
    assert after[0] == before[0] and after[2:] == before[2:]


def test_angle_order_vertex_and_repeated_measurements(win):
    win.set_measurement_mode("angle")
    ids = visible_ids(win)
    ti = (1, (0, 0, 0))
    oxygens = [i for i in ids if i[0] in (2, 3, 4)]
    assert ti in ids and len(oxygens) >= 2
    click_atom(win, oxygens[0])
    assert win.measure_label.text().strip() == (
        "Bond angle: select atom B — angle vertex (Esc cancels)"
    )
    click_atom(win, ti)
    assert "select atom C — second end" in win.measure_label.text()
    labels = [a.GetInput() for a in win.viewport.measurement_actors if hasattr(a, "GetInput")]
    assert labels == ["A", "B vertex"]
    click_atom(win, oxygens[1])
    first = win.measurements.results[-1]
    assert first.atoms[1] == ti  # B is the vertex
    expected = measure.measure(win.structure, "angle", [oxygens[0], ti, oxygens[1]]).value
    assert first.value == expected and first.value in (pytest.approx(90.0), pytest.approx(180.0))
    assert win.measure_panel.rows()[-1].result.endswith("° — vertex B")
    assert "B (vertex): Ti #2" in win.measure_panel.rows()[-1].atoms
    # Another angle with the vertex on an oxygen: a different value, appended.
    click_atom(win, ti)
    click_atom(win, oxygens[0])
    sr = next(i for i in ids if i[0] == 0)
    click_atom(win, sr)
    assert len(win.measurements.results) == 2
    second = win.measurements.results[-1]
    assert second.atoms == (ti, oxygens[0], sr)
    assert second.value == measure.measure(win.structure, "angle", second.atoms).value


def test_escape_mode_switch_and_rejected_picks(win, qtbot):
    widget = win.viewport.interactor_widget
    win.set_measurement_mode("angle")
    sr_images = [i for i in visible_ids(win) if i[0] == 0]
    assert len(sr_images) >= 2  # periodic images of one source atom
    click_atom(win, sr_images[0])
    click_atom(win, sr_images[0])  # the same instance again: rejected
    assert win.measurements.pending == [sr_images[0]]
    assert "already A" in win.statusBar().currentMessage()
    click_atom(win, sr_images[1])  # another image of the same atom: accepted
    assert win.measurements.pending == sr_images[:2]
    _click(widget, (3.0, 3.0))  # empty space keeps the picks
    assert win.measurements.pending == sr_images[:2]
    QTest.keyClick(widget, Qt.Key.Key_Escape)
    assert win.measurements.pending == [] and win.viewport.measurement_actors == []
    assert win.measurement_mode() == "angle" and win.measurements.results == []
    click_atom(win, sr_images[0])
    win.set_measurement_mode("distance")  # switching cancels the incomplete angle
    assert win.measurements.pending == [] and win.viewport.measurement_actors == []
    # After a completed distance Esc removes its guide; the result stays.
    click_atom(win, sr_images[0])
    click_atom(win, sr_images[1])
    assert win.viewport.measurement_actors and len(win.measurements.results) == 1
    QTest.keyClick(widget, Qt.Key.Key_Escape)
    assert win.viewport.measurement_actors == [] and len(win.measurements.results) == 1
    assert win.measurements.results[0].value == pytest.approx(
        np.linalg.norm(np.subtract(sr_images[1][1], sr_images[0][1])) * A
    )


def test_drags_navigate_and_ordinary_selection_is_preserved(win):
    widget = win.viewport.interactor_widget
    ti = (1, (0, 0, 0))
    click_atom(win, ti)  # ordinary selection before the mode
    assert win.selection == {ti}
    win.set_measurement_mode("distance")
    o = next(i for i in visible_ids(win) if i[0] == 2)
    click_atom(win, o)
    assert win.selection == {ti}  # clicks in the mode do not select
    camera = win.current_camera()
    pixel = _visible_pixels(win)[win.geometry.index_of(ti)]
    ratio = widget.devicePixelRatioF()
    start = (pixel[0] / ratio, pixel[1] / ratio)
    _send_drag(widget, start, (start[0] + 60, start[1] + 15), Qt.MouseButton.LeftButton)
    assert win.current_camera() != camera  # a drag orbits ...
    assert win.measurements.pending == [o]  # ... and picks nothing
    win.set_measurement_mode(None)
    sr = next(i for i in visible_ids(win) if i[0] == 0)
    click_atom(win, sr)
    assert win.selection == {sr}  # ordinary selection works again


def test_results_ignore_camera_and_appearance(win):
    win.set_measurement_mode("distance")
    ti, o = (1, (0, 0, 0)), (3, (0, 0, 0))
    first = win.pick_measurement_atom(ti) or win.pick_measurement_atom(o)
    exact = measure.distance(
        win.structure.positions[1], win.structure.positions[3]
    )  # input coordinates
    assert first.value == exact
    win.viewport.set_output_camera(win.current_camera().orbit(azimuth=37, elevation=-21).zoom(2.5))
    win.set_material("glossy")
    win.apply_scene_settings(replace(win.scene_settings, radius_scale=0.2, repetitions=(2, 1, 1)))
    assert ti in win.geometry and o in win.geometry
    win.pick_measurement_atom(ti)
    again = win.pick_measurement_atom(o)
    assert again.value == first.value  # bit for bit
    assert win.measurements.results[0].value == first.value  # stored result unchanged


def test_copy_remove_and_clear(win):
    win.set_measurement_mode("distance")
    pairs = [((1, (0, 0, 0)), (2, (0, 0, 0))), ((0, (0, 0, 0)), (0, (1, 0, 0)))]
    for a, b in pairs:
        win.pick_measurement_atom(a)
        win.pick_measurement_atom(b)
    win.set_measurement_mode("angle")
    for atom_id in ((2, (0, 0, 0)), (1, (0, 0, 0)), (3, (0, 0, 0))):
        win.pick_measurement_atom(atom_id)
    panel = win.measure_panel
    assert [row.result for row in panel.rows()] == ["1.9525 Å", "3.9050 Å", "90.00° — vertex B"]
    assert not panel.copy_button.isEnabled() and panel.clear_button.isEnabled()
    panel.table.selectRow(1)
    panel.table.selectionModel().select(
        panel.table.model().index(2, 0),
        panel.table.selectionModel().SelectionFlag.Select
        | panel.table.selectionModel().SelectionFlag.Rows,
    )
    assert panel.selected_rows() == [1, 2] and panel.copy_button.isEnabled()
    panel.copy_button.click()
    assert QGuiApplication.clipboard().text() == (
        "Distance A–B: 3.9050 Å (A = Sr #1 [0 0 0], B = Sr #1 [1 0 0])\n"
        "Angle A–B–C: 90.00° — vertex B (A = O #3 [0 0 0], B = Ti #2 [0 0 0], "
        "C = O #4 [0 0 0])"
    )
    assert "exact" in panel.table.item(0, 2).toolTip()
    QGuiApplication.clipboard().clear()
    panel.table.setFocus()
    QTest.keyClick(panel.table, Qt.Key.Key_C, Qt.KeyboardModifier.ControlModifier)
    assert QGuiApplication.clipboard().text().startswith("Distance A–B: 3.9050 Å")
    panel.table.clearSelection()
    panel.table.selectRow(0)
    assert panel.selected_rows() == [0]
    panel.remove_button.click()
    assert [r.result for r in panel.rows()] == ["3.9050 Å", "90.00° — vertex B"]
    assert len(win.measurements.results) == 2
    panel.clear_button.click()
    assert panel.rows() == [] and win.measurements.results == []
    assert not panel.clear_button.isEnabled()


def test_invalidation_on_display_and_structure_changes(win, tmp_path):
    win.set_measurement_mode("distance")
    corner = (0, (1, 1, 1))
    win.pick_measurement_atom((1, (0, 0, 0)))
    win.pick_measurement_atom((2, (0, 0, 0)))  # stays displayed
    win.pick_measurement_atom((1, (0, 0, 0)))
    win.pick_measurement_atom(corner)  # a boundary image
    win.pick_measurement_atom((0, (1, 0, 0)))  # incomplete, also a boundary image
    win.boundary_action.trigger()  # boundary images off: the corners disappear
    assert corner not in win.geometry
    assert [m.atoms for m in win.measurements.results] == [((1, (0, 0, 0)), (2, (0, 0, 0)))]
    assert win.measurements.pending == []
    note = win.measure_panel.note_label.text()
    assert "Removed 1 measurement: an atom is no longer displayed" in note
    assert "Incomplete measurement cancelled" in note
    win.undo_action.trigger()  # the corner is back, the removed result is not
    assert corner in win.geometry and len(win.measurements.results) == 1
    # Hiding a measured atom removes its measurement.
    win.select({(2, (0, 0, 0))})
    win.hide_selected()
    assert win.measurements.results == []
    # A pending pick and results are cleared when a different structure is loaded.
    win.pick_measurement_atom((1, (0, 0, 0)))
    win.pick_measurement_atom((4, (0, 0, 0)))
    win.install_project(Project(perovskite_srtio3()), None)
    assert win.measurements.results == [] and win.measurements.pending == []
    assert "a different structure was loaded" in win.measure_panel.note_label.text()
    assert win.viewport.measurement_actors == []


def test_helpers_stay_out_of_exports_bounds_fit_and_picking(win, tmp_path):
    before = snapshot(win)
    win.set_measurement_mode("angle")
    for atom_id in ((2, (0, 0, 0)), (1, (0, 0, 0)), (3, (0, 0, 0))):
        win.pick_measurement_atom(atom_id)
    assert len(win.viewport.measurement_actors) >= 5  # cage, arms, arc, three labels
    assert all(not actor.GetPickable() for actor in win.viewport.measurement_actors)
    # Picking at every atom, and next to the measured atoms where cages and labels are
    # drawn, gives the same answers with and without the helpers.
    width, height = win.viewport.render_size()
    camera = win.viewport.camera()
    pixels = camera.project(win.geometry.positions, width, height)
    probes = [tuple(p) for p in pixels] + [
        (p[0] + dx, p[1] + dy) for p in pixels[[9, 8, 11]] for dx, dy in ((14, 14), (-12, 3))
    ]
    with_helpers = [win.viewport.pick(p) for p in probes]
    assert with_helpers[: len(pixels)] == list(range(len(pixels)))
    after = snapshot(win)
    assert after[0] == before[0] and after[2:] == before[2:]
    path = win.export_pov(tmp_path / "scene.pov")
    text = path.read_text()
    assert "measure" not in text.lower()
    win.fit_action.trigger()
    fitted = win.current_camera()
    win.cancel_measurement()
    assert win.viewport.measurement_actors == []
    assert [win.viewport.pick(p) for p in probes] == with_helpers
    win.fit_action.trigger()
    # Fit ignores the helpers (refitting may differ by rounding only).
    assert _same_camera(win.current_camera(), fitted)
    # Session-only: projects do not store measurements.
    win.pick_measurement_atom((1, (0, 0, 0)))
    win.pick_measurement_atom((2, (0, 0, 0)))
    saved = tmp_path / "scene.ycrystal"
    assert win.save_as(saved)
    assert "measure" not in json.dumps(json.loads(saved.read_text())).lower()
    assert len(win.measurements.results) == 1  # saving keeps the session's results
