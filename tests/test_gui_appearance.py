"""M4 in the window: galleries, material assignment, environment controls, projects."""

import pytest

from ycrystal.core.samples import perovskite_srtio3
from ycrystal.gui.gallery import FAVOURITES_KEY
from ycrystal.gui.main_window import SETTINGS_POVRAY, MainWindow
from ycrystal.io.project import load_project
from ycrystal.presets import custom_materials, environment_from_preset, get_lighting, materials
from ycrystal.render.imagecheck import load_rgba

pytestmark = pytest.mark.gui


@pytest.fixture
def window(qtbot):
    win = MainWindow(perovskite_srtio3())
    qtbot.addWidget(win)
    win.resize(1150, 700)
    win.show()
    qtbot.waitExposed(win)
    qtbot.waitUntil(lambda: win._saved_camera is not None, timeout=5000)
    win.settings.remove("favourites")
    yield win
    win.settings.remove("favourites")
    win.close()


def materials_of(window, element):
    return {
        m
        for e, m in zip(window.geometry.elements, window.geometry.materials, strict=True)
        if e == element
    }


# ----- galleries -----------------------------------------------------------------------
def test_material_gallery_search_categories_and_favourites(window):
    gallery = window.open_material_gallery()
    shown = len(materials()) + len(custom_materials())  # custom variants too (FR-MATERIAL-01)
    assert gallery.isVisible() and len(gallery.visible_ids()) == shown
    assert gallery.current_id() == "satin"  # the material in use is highlighted
    gallery.search_edit.setText("T_Gold")  # native identifier
    assert gallery.visible_ids() == ["gold"]
    assert "T_Gold_3C" in gallery.details_label.text()
    assert "metals.inc" in gallery.details_label.text()
    assert "Own colours" in gallery.details_label.text()
    gallery.search_edit.setText("")
    gallery.category_combo.setCurrentIndex(gallery.category_combo.findData("transparent"))
    assert set(gallery.visible_ids()) == {m.id for m in materials() if m.category == "transparent"}
    gallery.category_combo.setCurrentIndex(gallery.category_combo.findData("favourites"))
    assert gallery.visible_ids() == []
    gallery.set_favourite("jade", True)
    gallery.set_favourite("chrome", True)
    assert set(gallery.visible_ids()) == {"jade", "chrome"}
    assert window.settings.value(FAVOURITES_KEY.format(kind="materials")) == ["jade", "chrome"]
    gallery.select_preset("jade")
    assert gallery.favourite_button.isChecked()
    gallery.favourite_button.click()  # remove from favourites
    assert gallery.visible_ids() == ["chrome"]
    gallery.search_edit.setText("zzz-no-match")
    assert gallery.visible_ids() == [] and not gallery.apply_button.isEnabled()


def test_gallery_targets_apply_and_undo(window):
    gallery = window.open_material_gallery()
    targets = [gallery.target_combo.itemData(i) for i in range(gallery.target_combo.count())]
    assert targets == ["default", "element:Sr", "element:Ti", "element:O"]  # no selection yet
    gallery.select_preset("glossy")
    gallery.apply_button.click()
    assert window.scene_settings.material == "glossy"
    gallery.target_combo.setCurrentIndex(gallery.target_combo.findData("element:O"))
    gallery.select_preset("glass")
    gallery.list.itemDoubleClicked.emit(gallery.list.currentItem())
    assert materials_of(window, "O") == {"glass"} and materials_of(window, "Sr") == {"glossy"}
    corner = (0, (0, 0, 0))
    window.select({corner})
    assert gallery.target_combo.findData("selection") >= 0
    gallery.target_combo.setCurrentIndex(gallery.target_combo.findData("selection"))
    gallery.select_preset("gold")
    gallery.apply_button.click()
    index = window.geometry.index_of(corner)
    assert window.geometry.materials[index] == "gold"
    assert materials_of(window, "Sr") == {"glossy", "gold"}  # only the selected image
    gallery.reset_button.click()  # selection back to its element/default material
    assert window.geometry.materials[window.geometry.index_of(corner)] == "glossy"
    for _ in range(4):
        window.undo_action.trigger()
    assert window.scene_settings.material == "satin"
    assert window.scene_settings.element_materials == ()
    assert window.scene_settings.atom_materials == ()


def test_environment_gallery_applies_preset(window):
    gallery = window.open_environment_gallery()
    assert gallery.current_id() == "white" and gallery.target_combo.count() == 0
    gallery.search_edit.setText("reflective")
    assert gallery.visible_ids() == ["studio_dark"]
    gallery.apply_button.click()
    env = window.environment
    assert env.preset == "studio_dark" and env.floor and env.floor_reflection > 0
    assert env.lighting == "bright" and env.reflector
    assert window.scene_settings.cell_edge_color[0] > 0.5  # light edges on the dark floor
    window.undo_action.trigger()
    assert window.environment == environment_from_preset("white")


# ----- appearance panel ------------------------------------------------------------------
def test_element_table_material_and_colour(window):
    panel = window.appearance_panel
    button, reset, combo = panel.element_widgets("Ti")
    combo.setCurrentIndex(combo.findData("chrome"))
    assert materials_of(window, "Ti") == {"chrome"}
    assert window.undo_stack.undoText() == "Material of Ti: Chrome (Polished_Chrome)"
    window.set_element_color("O", (0.2, 0.3, 0.9))
    button, reset, _ = panel.element_widgets("O")
    assert button.color() == (0.2, 0.3, 0.9) and reset.isEnabled()
    o_row = window.geometry.elements.index("O")
    assert tuple(window.geometry.colors[o_row]) == (0.2, 0.3, 0.9)
    reset.click()
    assert window.scene_settings.element_colors == ()
    assert not panel.element_widgets("O")[1].isEnabled()
    _, _, combo = panel.element_widgets("Ti")
    combo.setCurrentIndex(0)  # "Default (…)"
    assert window.scene_settings.element_materials == ()


def test_selection_buttons_and_edit_menu(window):
    panel = window.appearance_panel
    assert not panel.selection_button.isEnabled()
    assert not window.selection_material_action.isEnabled()
    picked = {(1, (0, 0, 0)), (2, (0, 0, 0))}
    window.select(picked)
    assert panel.selection_button.isEnabled() and window.selection_material_action.isEnabled()
    assert "2 atoms" in panel.selection_label.text()
    window.selection_material_action.trigger()
    assert window.material_gallery.target() == "selection"
    window.set_selection_material("jade")
    assert "2 atom overrides" in panel.overrides_label.text()
    panel.clear_atoms_button.click()
    assert window.scene_settings.atom_materials == ()


def test_environment_controls_merge_and_lighting_presets(window, qtbot):
    panel = window.appearance_panel
    panel.background_combo.setCurrentIndex(panel.background_combo.findData("studio_white"))
    assert window.environment.floor and window.environment.lighting == "studio"
    steps = window.undo_stack.count()
    for value in (0.8, 0.7, 0.6):  # dragging a spin box: one undo step
        panel.key_spin.setValue(value)
    assert window.environment.key_light == pytest.approx(0.6)
    assert window.undo_stack.count() == steps + 1
    assert "Adjusted" in panel.lighting_note.text() and "Modified" in panel.background_note.text()
    panel.mode_combo.setCurrentIndex(panel.mode_combo.findData("sky"))
    assert window.environment.background_mode == "sky" and panel.clouds_spin.isEnabled()
    panel.floor_group.setChecked(False)
    assert not window.environment.floor
    panel.lighting_combo.setCurrentIndex(panel.lighting_combo.findData("dramatic"))
    env = window.environment
    assert env.lighting == "dramatic" and env.key_azimuth == get_lighting("dramatic").key_azimuth
    assert env.background_mode == "sky"  # lighting presets keep the background
    panel.transparent_check.setChecked(True)
    assert window.current_render_settings().transparent_background


def test_live_view_approximations(window):
    renderer = window.viewport._plotter.renderer
    window.set_element_material("O", "glass")
    viewport = window.viewport
    assert set(viewport.atom_actors) == {"satin", "glass"}  # one actor per material
    assert viewport.atom_actors["glass"].GetProperty().GetOpacity() == pytest.approx(0.4)
    assert set(viewport.bond_actors) == {"satin", "glass"}  # half-bonds follow their atom
    window.set_background("gradient_blue")
    assert renderer.GetGradientBackground()
    top = renderer.GetBackground2()
    assert top[2] > top[0]  # blue at the top
    window.set_background("studio_grey")
    assert not renderer.GetGradientBackground()
    assert renderer.GetBackground()[0] == pytest.approx(0.62, abs=0.01)  # the floor colour


def test_overrides_and_environment_survive_reopen(window, qtbot, tmp_path):
    window.set_material("ceramic")
    window.set_element_material("Ti", "gold")
    window.select({(0, (0, 0, 0))})
    window.set_selection_material("marble")
    window.set_element_color("O", (0.9, 0.5, 0.1))
    window.set_background("sky_cloudy")
    window.set_lighting("top")
    path = tmp_path / "style.ycrystal"
    assert window.save_as(path)
    project = load_project(path)
    reopened = MainWindow(project=project, project_path=path)
    qtbot.addWidget(reopened)
    try:
        assert reopened.scene_settings == window.scene_settings
        assert reopened.environment == window.environment
        assert reopened.geometry.materials == window.geometry.materials
        panel = reopened.appearance_panel
        assert panel.material_combo.currentData() == "ceramic"
        assert panel.element_widgets("Ti")[2].currentData() == "gold"
        assert panel.lighting_combo.currentData() == "top"
        assert panel.background_combo.currentData() == "sky_cloudy"
    finally:
        reopened.close()


def test_export_reports_include_files(window, tmp_path):
    window.set_element_material("Sr", "gold")
    pov = window.export_pov(tmp_path / "gold.pov")
    text = pov.read_text(encoding="utf-8")
    assert '#include "metals.inc"' in text
    assert "metals.inc" in window.statusBar().currentMessage()
    assert window.last_export_missing_includes == []  # POV-Ray's include files are installed


@pytest.mark.povray
def test_render_with_overrides_after_reopen(window, qtbot, tmp_path, povray_executable):
    window.settings.setValue(SETTINGS_POVRAY, povray_executable)
    window.set_output_size(240, 160)
    window.set_element_material("Ti", "chrome")
    window.set_element_material("O", "glass")
    window.set_background("studio_white")
    assert window.save_as(tmp_path / "s.ycrystal")
    reopened = MainWindow(project=load_project(tmp_path / "s.ycrystal"))
    qtbot.addWidget(reopened)
    reopened.resize(900, 700)
    reopened.show()
    qtbot.waitExposed(reopened)
    qtbot.waitUntil(lambda: reopened._saved_camera is not None, timeout=5000)
    reopened.settings.setValue(SETTINGS_POVRAY, povray_executable)
    try:
        assert reopened.render_png(tmp_path / "out.png", show_result=False)
        qtbot.waitUntil(lambda: reopened.render_finished_result is not None, timeout=120_000)
        assert reopened.render_finished_result.ok, reopened.render_finished_result.message
        rgba = load_rgba(tmp_path / "out.png")
        assert rgba.shape == (160, 240, 4)
        assert rgba[2, 2, :3].min() > 150  # the white studio floor
    finally:
        reopened.close()
