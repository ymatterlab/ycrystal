"""FR-MATERIAL-01 in the window: Customize Material…, preview, apply, cancel, personal list."""

import json

import pytest
from PySide6.QtCore import QSettings

from test_custom_materials import forget_custom
from test_render_queue import fake_povray
from ycrystal import presets
from ycrystal.core.samples import perovskite_srtio3
from ycrystal.gui.main_window import SETTINGS_POVRAY, MainWindow
from ycrystal.gui.material_editor import PERSONAL_MATERIALS_KEY
from ycrystal.presets import custom_materials, get_material
from ycrystal.presets.custom import base_definition

pytestmark = pytest.mark.gui


@pytest.fixture(autouse=True)
def clean_profile():
    QSettings().remove(PERSONAL_MATERIALS_KEY)
    forget_custom()
    yield
    QSettings().remove(PERSONAL_MATERIALS_KEY)
    forget_custom()


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


def shown_materials(win):
    return set(win.geometry.materials)


def test_preview_then_cancel_leaves_no_trace(win, qtbot):
    steps, settings = win.undo_stack.count(), win.scene_settings
    dialog = win.open_material_editor()
    assert dialog.target() == "default" and dialog.base_combo.currentData() == "satin"
    assert dialog.name_edit.text() == "Satin (custom)"
    assert [k for k in dialog._spins] == ["diffuse", "specular", "roughness", "reflection"]
    dialog.set_value("specular", 0.9)
    qtbot.waitUntil(lambda: any(m.startswith("custom_satin_") for m in shown_materials(win)))
    assert win.scene_settings == settings and win.undo_stack.count() == steps  # preview only
    assert not win.is_modified()
    assert all(not m.custom for m in custom_materials())  # previews are not listed
    dialog.cancel_button.click()
    assert shown_materials(win) == {"satin"} and win.undo_stack.count() == steps


def test_apply_is_one_undoable_step(win, qtbot):
    dialog = win.open_material_editor()
    for value in (0.5, 0.6, 0.7):  # continuous changes: still one step
        dialog.set_value("specular", value)
    dialog.set_value("roughness", 0.005)
    dialog.name_edit.setText("Bright satin")
    dialog.apply_button.click()
    variant = get_material(win.scene_settings.material)
    assert variant.name == "Bright satin" and variant.base == "satin"
    assert "specular 0.7 roughness 0.005" in variant.finish
    assert win.undo_stack.count() == 1 and win.is_modified()
    assert win.undo_stack.undoText() == "Material: Bright satin"
    combo = win.appearance_panel.material_combo
    assert combo.currentData() == variant.id and combo.currentText() == "Bright satin ✎"
    win.undo_action.trigger()
    assert win.scene_settings.material == "satin" and shown_materials(win) == {"satin"}
    win.redo_action.trigger()
    assert win.scene_settings.material == variant.id


def test_selection_is_captured_and_precedence_holds(win, qtbot):
    win.set_element_material("O", "matte")
    picked = {(2, (0, 0, 0)), (3, (0, 0, 0))}
    win.select(picked)
    dialog = win.open_material_editor()
    assert dialog.target() == "selection"
    dialog.base_combo.setCurrentIndex(dialog.base_combo.findData("glass"))
    dialog.set_value("ior", 1.8)
    win.select({(0, (0, 0, 0))})  # a later selection does not redirect the edit
    dialog.apply_button.click()
    variant = win.scene_settings.atom_materials[0][1]
    assert dict(win.scene_settings.atom_materials) == {atom: variant for atom in picked}
    assert get_material(variant).interior == "ior 1.8"
    assert win.scene_settings.material_for((4, (0, 0, 0)), "O") == "matte"  # element override
    assert win.scene_settings.material_for((2, (0, 0, 0)), "O") == variant  # atom wins
    # An element target changes only that element.
    dialog = win.open_material_editor("element:Ti")
    dialog.set_value("diffuse", 0.3)
    dialog.apply_button.click()
    ti = dict(win.scene_settings.element_materials)["Ti"]
    assert get_material(ti).base == "satin" and win.scene_settings.material == "satin"


def test_native_materials_are_read_only_and_reset_restores_the_base(win):
    dialog = win.open_material_editor()
    dialog.base_combo.setCurrentIndex(dialog.base_combo.findData("gold"))
    assert not dialog.apply_button.isEnabled() and not dialog.parameter_group.isEnabled()
    note = dialog.note_label.text()
    assert "T_Gold_3C" in note and "cannot be edited" in note
    dialog.base_combo.setCurrentIndex(dialog.base_combo.findData("glass_frosted"))
    assert "not a generic opacity" in dialog.note_label.text()
    dialog.set_value("bump_strength", 1.5)
    dialog.reset_to_base()
    assert dialog.value("bump_strength") == 0.6 and dialog.definition().changed() == []
    dialog.base_combo.setCurrentIndex(dialog.base_combo.findData("wood"))
    assert list(dialog._spins) == ["pattern_scale"] and dialog.value("pattern_scale") == 0.35
    dialog.cancel_button.click()


def test_personal_materials_persist_and_files_need_no_profile(win, qtbot, tmp_path):
    dialog = win.open_material_editor()
    dialog.set_value("reflection", 0.25)
    dialog.name_edit.setText("Mirror satin")
    dialog.save_button.click()
    stored = json.loads(QSettings().value(PERSONAL_MATERIALS_KEY))
    assert [entry["name"] for entry in stored] == ["Mirror satin"]
    variant_id = stored[0]["id"]
    dialog.apply_button.click()
    gallery = win.open_material_gallery()
    assert variant_id in gallery.visible_ids() or variant_id in [
        gallery.list.item(r).data(256) for r in range(gallery.list.count())
    ]
    assert not gallery.list.item(gallery.list.count() - 1).icon().isNull()  # badge fallback
    project = tmp_path / "mirror.ycrystal"
    assert win.save_as(project)
    qtbot.waitUntil(lambda: not win._thumbnail_renders, timeout=60_000)  # background render
    # A restart: the personal list comes back from the settings.
    forget_custom()
    second = make_window(qtbot)
    try:
        assert any(m.id == variant_id for m in custom_materials())
        assert second.appearance_panel.material_combo.findData(variant_id) >= 0
    finally:
        second.ask_save_changes = lambda: "discard"
        second.close()
    # A clean profile: no personal list; the project carries the definition.
    QSettings().remove(PERSONAL_MATERIALS_KEY)
    forget_custom()
    third = make_window(qtbot)
    try:
        assert custom_materials() == []
        assert third.open_file(project) and third.scene_settings.material == variant_id
        assert "reflection 0.25" in get_material(variant_id).finish
    finally:
        third.ask_save_changes = lambda: "discard"
        third.close()


def test_editing_discards_a_stale_preview(win, qtbot, tmp_path):
    win.settings.setValue(SETTINGS_POVRAY, fake_povray(tmp_path, 0.8))
    assert win.request_preview()
    dialog = win.open_material_editor()
    dialog.set_value("specular", 0.95)  # the view changes while the preview renders
    qtbot.waitUntil(lambda: win.preview_result is not None, timeout=10_000)
    assert win.preview_discarded == 1
    dialog.cancel_button.click()


@pytest.mark.povray
def test_saved_material_gets_a_real_thumbnail(win, qtbot, povray_executable):
    win.settings.setValue(SETTINGS_POVRAY, povray_executable)
    definition = base_definition("glossy").with_values(reflection=0.4).renamed("Glossy mirror")
    assert win.save_personal_material(definition)
    path = presets.CUSTOM_THUMBNAILS / f"{definition.id}.png"
    qtbot.waitUntil(path.is_file, timeout=60_000)
    assert get_material(definition.id).thumbnail() == path
