"""FR-VECTOR-01 in the window: Vectors window, editor, undo, live view, persistence."""

from dataclasses import replace

import numpy as np
import pytest

from test_custom_materials import forget_custom
from test_render_queue import fake_povray
from test_vectors import DOWN, UP, bcc_iron
from ycrystal.core import measure
from ycrystal.core.vectors import VectorRecord, VectorStyle
from ycrystal.gui.main_window import SETTINGS_POVRAY, MainWindow
from ycrystal.presets import register_definition
from ycrystal.presets.custom import base_definition

pytestmark = pytest.mark.gui


def make_window(qtbot, structure=None):
    win = MainWindow(structure or bcc_iron())
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


def hosts(win):
    return {a.host: a for a in win.geometry.arrows}


def test_editor_preview_cancel_and_apply_as_one_step(win, qtbot):
    edit_actions = [a.text() for a in win.menuBar().actions()[1].menu().actions()]
    assert "Vectors…" in edit_actions
    panel = win.open_vector_panel()
    assert not panel.add_button.isEnabled()  # nothing selected
    win.select({(0, (0, 0, 0)), (1, (0, 0, 0))})
    assert panel.add_button.isEnabled()
    dialog = win.open_vector_editor()
    assert dialog.scope() == "images" and dialog.modulus_label.text() == "1.0000 μB"
    dialog.set_components(0.0, 0.0, 2.2)
    win.select({(0, (1, 1, 1))})  # the targets are frozen while the editor is open
    qtbot.waitUntil(lambda: len(win.geometry.arrows) == 2)  # live preview, no undo step
    assert win.undo_stack.count() == 0 and not win.is_modified()
    assert len(win.scene_settings.vectors) == 0
    dialog.cancel_button.click()
    assert win.geometry.arrows == () and win.undo_stack.count() == 0
    win.select({(0, (0, 0, 0)), (1, (0, 0, 0))})
    dialog = win.open_vector_editor()
    dialog.set_components(0.0, 0.0, 2.2)
    dialog.scope_buttons["sources"].setChecked(True)
    dialog.apply_button.click()
    assert win.undo_stack.count() == 1 and win.is_modified()
    vectors = win.scene_settings.vectors
    assert vectors.sources == ((0, UP), (1, UP)) and vectors.images == ()
    assert len(win.geometry.arrows) == len(win.geometry)  # every image of both sources
    assert win.viewport.arrow_mesh is not None
    assert [panel.table.item(r, 0).text() for r in range(2)] == ["All images", "All images"]
    win.undo_action.trigger()
    assert len(win.scene_settings.vectors) == 0 and win.viewport.arrow_mesh is None
    win.redo_action.trigger()
    assert win.scene_settings.vectors == vectors


def test_table_actions_overrides_suppression_and_opposing_moments(win):
    panel = win.open_vector_panel()
    win.set_vector(UP, sources={0})
    win.set_vector(DOWN, sources={1})  # same element, opposite moment: assigned explicitly
    corner = (0, (1, 0, 0))
    win.select({corner})
    panel.suppress_button.click()
    assert corner not in hosts(win) and (0, (0, 0, 0)) in hosts(win)
    assert panel.table.item(2, 0).text() == "Suppressed here"
    steps = win.undo_stack.count()
    panel.select_keys([("source", 0), ("source", 1)])
    assert win.selection == {a for a in win.geometry.atom_ids if a != corner}  # hosts shown
    panel.reverse_button.click()
    assert win.scene_settings.vectors.effective((1, (0, 0, 0))) == UP
    assert win.undo_stack.count() == steps + 1  # one step for both rows
    panel.select_keys([("source", 1)])
    panel.visible_button.click()
    assert all(a.host[0] == 0 for a in win.geometry.arrows)
    assert panel.table.item(1, 6).text() == "hidden"
    panel.select_keys([("image", corner)])
    panel.remove_button.click()  # the source default applies again on that image
    assert corner in hosts(win)
    # Editing a row keeps its visibility and scope.
    panel.select_keys([("source", 1)])
    dialog = win.open_vector_editor(panel.selected_keys())
    assert dialog.scope() == "keys" and not dialog.scope_buttons["keys"].parent().isEnabled()
    dialog.set_components(1.0, 0.0, 0.0)
    dialog.apply_button.click()
    record = win.scene_settings.vectors.effective((1, (0, 0, 0)))
    assert record.components == (1.0, 0.0, 0.0) and not record.visible


def test_live_view_matches_shared_geometry_and_leaves_picking_measuring_lighting(win):
    width, height = win.viewport.render_size()
    camera = win.viewport.camera()
    pixels = camera.project(win.geometry.positions, width, height)
    picks = [win.viewport.pick(tuple(p)) for p in pixels]
    rig = win.viewport.lighting_rig().key.position.copy()
    output_camera = win.current_camera()
    distance = measure.measure(win.structure, "distance", [(0, (0, 0, 0)), (1, (0, 0, 0))]).value
    win.set_vector(VectorRecord((0.0, 0.0, 3.0)), sources={0, 1})
    win.set_vector_style(VectorStyle(length=4.0, placement="tail"), "Arrows")
    mesh = win.viewport.arrow_mesh
    tips = np.array([a.tip for a in win.geometry.arrows])
    tails = np.array([a.tail for a in win.geometry.arrows])
    lo, hi = np.array(mesh.bounds[::2]), np.array(mesh.bounds[1::2])
    head = max(a.head_radius for a in win.geometry.arrows)
    np.testing.assert_allclose(hi[2], tips[:, 2].max(), atol=1e-6)  # VTK tips = POV tips
    np.testing.assert_allclose(lo[2], tails[:, 2].min(), atol=1e-6)
    assert np.all(lo[:2] >= np.minimum(tips, tails)[:, :2].min(axis=0) - head - 1e-6)
    assert [win.viewport.pick(tuple(p)) for p in pixels] == picks  # arrows never picked
    np.testing.assert_array_equal(win.viewport.lighting_rig().key.position, rig)
    assert win.current_camera() == output_camera  # adding vectors does not refit
    after = measure.measure(win.structure, "distance", [(0, (0, 0, 0)), (1, (0, 0, 0))]).value
    assert after == distance
    win.select({(0, (0, 0, 0))})
    assert "vector (0.000, 0.000, 3.000) μB" in win.selection_text()
    win.fit_action.trigger()  # explicit Fit now includes the long arrows
    assert win.current_camera().parallel_scale > output_camera.parallel_scale


def test_appearance_edits_merge_and_custom_arrow_material_persists(win, qtbot, tmp_path):
    panel = win.open_vector_panel()
    win.set_vector(UP, sources={0})
    steps = win.undo_stack.count()
    panel.length_spin.setValue(3.0)
    panel.length_spin.setValue(3.4)
    assert win.scene_settings.vector_style.length == 3.4 and win.undo_stack.count() == steps + 1
    panel.mode_combo.setCurrentIndex(panel.mode_combo.findData("proportional"))
    assert panel.scale_spin.isEnabled() and not panel.length_spin.isEnabled()
    assert win.geometry.arrows[0].length == pytest.approx(0.6 * 2.2)
    variant = register_definition(base_definition("glossy").with_values(reflection=0.3))
    panel._fill_materials()
    panel.material_combo.setCurrentIndex(panel.material_combo.findData(variant.id))
    assert win.scene_settings.vector_style.material == variant.id
    assert win.geometry.arrow_material == variant.id and win.scene_settings.material == "satin"
    project = tmp_path / "arrows.ycrystal"
    assert win.save_as(project)
    forget_custom()  # a clean profile without personal materials
    second = make_window(qtbot, bcc_iron())
    try:
        assert second.open_file(project)
        assert second.scene_settings.vectors == win.scene_settings.vectors
        assert second.geometry.arrow_material == variant.id
        pov = second.export_pov(tmp_path / "arrows.pov")
        text = pov.read_text()
        assert f"#declare Ycr_Texture_Arrow_{variant.id} = texture" in text
        assert "cone {" in text and f"texture {{ Ycr_Texture_Arrow_{variant.id} }}" in text
        assert "reflection 0.3" in text
    finally:
        second.ask_save_changes = lambda: "discard"
        second.close()


def test_style_import_keeps_vectors_and_new_structure_clears_them(win, qtbot, tmp_path):
    win.set_vector(UP, sources={0})
    win.set_vector_style(replace(win.scene_settings.vector_style, length=3.3), "Arrows")
    style = win.export_style(tmp_path / "look.ycstyle")
    other = make_window(qtbot)
    try:
        other.set_vector(DOWN, sources={1})
        assert other.import_style(style, parts=("appearance", "display", "environment"))
        assert other.scene_settings.vectors.sources == ((1, DOWN),)  # target's vectors kept
        assert other.scene_settings.vector_style.length == 3.3  # appearance transferred
    finally:
        other.ask_save_changes = lambda: "discard"
        other.close()
    from ycrystal.core.samples import perovskite_srtio3
    from ycrystal.io.project import Project

    win.install_project(Project(perovskite_srtio3()), None)  # another structure
    assert len(win.scene_settings.vectors) == 0 and win.geometry.arrows == ()


def test_vector_change_discards_a_running_preview(win, qtbot, tmp_path):
    win.settings.setValue(SETTINGS_POVRAY, fake_povray(tmp_path, 0.8))
    assert win.request_preview()
    win.set_vector(UP, sources={0})
    qtbot.waitUntil(lambda: win.preview_result is not None, timeout=10_000)
    assert win.preview_discarded == 1
