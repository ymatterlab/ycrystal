"""Opening, saving, and reopening in the main window; unsaved-change handling."""

import shutil
from pathlib import Path

import numpy as np
import pytest

from ycrystal.core.samples import perovskite_srtio3
from ycrystal.gui.main_window import MainWindow
from ycrystal.io.project import load_project

pytestmark = pytest.mark.gui
FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def window(qtbot):
    win = MainWindow(perovskite_srtio3())
    qtbot.addWidget(win)
    win.resize(900, 600)
    win.show()
    qtbot.waitExposed(win)
    qtbot.waitUntil(lambda: win._saved_camera is not None, timeout=5000)
    yield win
    win.close()


def turned(window):
    return window.current_camera().orbit(azimuth=25, elevation=10).pan(0.3, 0.1)


def test_open_structure_file_replaces_scene(window):
    window.select({window.geometry.atom_ids[0]})
    window.hide_selected()
    assert window.undo_stack.count() == 1
    assert window.open_file(FIXTURES / "MgB2.cif")
    assert window.structure.composition() == "MgB2"
    assert window.structure.labels == ("Mg1", "B1", "B1")
    assert window.undo_stack.count() == 0 and window.selection == set()
    assert window.scene_settings.hidden == frozenset()
    assert len(window.geometry) == 10  # Mg on all 8 corners + 2 B inside (z = 1/2)
    assert window.windowTitle().startswith("MgB2 (unsaved)")
    assert not window.is_modified()
    assert "Imported MgB2.cif (CIF, block MgB2)" in window.statusBar().currentMessage()
    pixels = window.current_camera().project(
        window.geometry.positions, *window.viewport.render_size()
    )
    assert np.all((pixels > 0) & (pixels < window.viewport.render_size()))


@pytest.mark.parametrize(
    "name, title",
    [
        ("partial_occupancy.cif", "Cannot Open File"),
        ("qe_ibrav4_no_c.pw.in", "Cannot Open File"),
        ("POSCAR_truncated", "Cannot Open File"),
    ],
)
def test_failed_open_keeps_current_scene(window, name, title):
    structure, geometry = window.structure, window.geometry
    camera = window.current_camera()
    assert window.open_file(FIXTURES / name) is False
    assert window.last_error[0] == title
    assert window.structure is structure and window.geometry is geometry
    assert window.current_camera() == camera
    window._message_box.close()


def test_failed_project_open_keeps_scene(window, tmp_path):
    bad = tmp_path / "broken.ycrystal"
    bad.write_text("{not json")
    structure = window.structure
    assert window.open_file(bad) is False
    assert window.last_error[0] == "Cannot Open Project"
    assert window.structure is structure
    window._message_box.close()


def test_ambiguous_format_asks_and_can_be_cancelled(window, monkeypatch, tmp_path):
    asked = []
    monkeypatch.setattr(window, "ask_choice", lambda t, label, items: asked.append(items))
    assert window.open_file(FIXTURES / "not_a_structure.txt") is False
    assert asked and "CIF" in asked[0]
    plain = tmp_path / "structure.dat"
    shutil.copy(FIXTURES / "SrTiO3.cif", plain)
    assert window.open_file(plain, fmt="cif")  # manual override


def test_data_block_and_element_questions(window, monkeypatch):
    monkeypatch.setattr(window, "ask_choice", lambda title, label, items: items[1])
    assert window.open_file(FIXTURES / "two_blocks.cif")
    assert window.structure.composition() == "MgB2"
    answers = iter(["Ga", "N"])
    monkeypatch.setattr(window, "ask_text", lambda title, label, default="": next(answers))
    assert window.open_file(FIXTURES / "POSCAR_vasp4")
    assert window.structure.symbols == ("Ga", "N")
    monkeypatch.setattr(window, "ask_text", lambda *a, **k: None)  # user cancels
    structure = window.structure
    assert window.open_file(FIXTURES / "qe_ambiguous_label.pw.in") is False
    assert window.structure is structure


def test_save_and_reopen_after_source_file_is_moved(window, qtbot, tmp_path):
    source = tmp_path / "input" / "SrTiO3.vasp"
    source.parent.mkdir()
    shutil.copy(FIXTURES / "SrTiO3.vasp", source)
    assert window.open_file(source)
    window.viewport.set_camera(turned(window))
    window.select({(0, (1, 1, 1)), (1, (0, 0, 0))})
    window.hide_selected()
    window.render_panel.lock_button.click()  # unlock: set width and height independently
    window.width_spin.setValue(900)
    window.height_spin.setValue(500)
    window.set_background("transparent")
    window.set_material("glossy")
    assert window.is_modified()
    project_path = tmp_path / "out" / "my figure"
    assert window.save_as(project_path)
    saved = project_path.with_name("my figure.ycrystal")
    assert window.project_path == saved and saved.is_file()
    assert not window.is_modified()
    assert window.windowTitle().startswith("my figure.ycrystal")

    camera, positions = window.current_camera(), window.structure.positions.copy()
    hidden = window.scene_settings.hidden
    shutil.rmtree(source.parent)  # the original structure file is gone

    other = MainWindow(perovskite_srtio3())
    qtbot.addWidget(other)
    other.resize(1180, 760)  # a differently shaped window: the output framing is kept
    other.show()
    qtbot.waitUntil(lambda: other._saved_camera is not None, timeout=5000)
    assert other.open_file(saved)
    np.testing.assert_array_equal(other.structure.positions, positions)
    assert other.scene_settings.hidden == hidden and other.geometry.hidden_count == 2
    reopened = other.current_camera()
    np.testing.assert_allclose(reopened.position, camera.position, rtol=1e-12)
    np.testing.assert_allclose(reopened.view_up, camera.view_up, atol=1e-12)
    assert reopened.parallel_scale == pytest.approx(camera.parallel_scale, rel=1e-12)
    assert (other.width_spin.value(), other.height_spin.value()) == (900, 500)
    assert not other.aspect_locked()  # the lock state is part of the project
    assert other.environment.transparent and other.environment.preset == "transparent"
    assert other.scene_settings.material == "glossy"
    assert other.appearance_panel.material_combo.currentData() == "glossy"
    assert other.project_path == saved and not other.is_modified()
    assert "fixed x y z" in (other.select({(0, (0, 0, 0))}) or other.selection_text())
    other.close()


def test_project_given_to_constructor_applies_camera(qtbot, tmp_path, window):
    window.viewport.set_camera(turned(window))
    window.save_as(tmp_path / "p.ycrystal")
    project = load_project(tmp_path / "p.ycrystal")
    other = MainWindow(project=project, project_path=tmp_path / "p.ycrystal")
    qtbot.addWidget(other)
    other.resize(900, 600)
    other.show()
    qtbot.waitUntil(lambda: other._saved_camera is not None, timeout=5000)
    assert other.current_camera() == project.camera
    assert not other.is_modified()
    other.close()


def test_modified_tracking(window, tmp_path):
    assert not window.is_modified()
    assert not window.isWindowModified()
    window.viewport.set_camera(turned(window))
    assert window.is_modified() and window.isWindowModified()
    window.save_as(tmp_path / "a.ycrystal")
    assert not window.isWindowModified()
    window.select({window.geometry.atom_ids[0]})
    window.hide_selected()
    assert window.isWindowModified()
    window.undo_action.trigger()
    assert not window.isWindowModified()  # back at the saved state
    window.width_spin.setValue(window.width_spin.value() + 10)
    assert window.isWindowModified()


def test_close_and_open_respect_cancel_save_discard(window, monkeypatch, tmp_path):
    window.viewport.set_camera(turned(window))
    monkeypatch.setattr(window, "ask_save_changes", lambda: "cancel")
    assert window.close() is False and window.isVisible()
    structure = window.structure
    assert window.open_file(FIXTURES / "MgB2.vasp") is False
    assert window.structure is structure

    monkeypatch.setattr(window, "ask_save_changes", lambda: "save")
    monkeypatch.setattr(window, "ask_save_path", lambda: tmp_path / "kept.ycrystal")
    assert window.open_file(FIXTURES / "MgB2.vasp")  # saves first, then opens
    assert load_project(tmp_path / "kept.ycrystal").structure.composition() == "SrTiO3"
    assert window.structure.composition() == "MgB2"

    window.viewport.set_camera(turned(window))
    monkeypatch.setattr(window, "ask_save_path", lambda: None)  # Save dialog cancelled
    assert window.close() is False and window.isVisible()
    monkeypatch.setattr(window, "ask_save_changes", lambda: "discard")
    assert window.close() is True
