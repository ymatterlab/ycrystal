"""FR-STYLE-MAP-01 in the window: the element mapping of File ▸ Import Style…."""

from pathlib import Path

import numpy as np
import pytest
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QDialogButtonBox

from ycrystal.batch import load_input
from ycrystal.core.samples import perovskite_srtio3
from ycrystal.core.scene import Environment, SceneSettings
from ycrystal.gui.main_window import MainWindow
from ycrystal.gui.style_dialog import LEAVE_OUT, StyleImportChoice, StyleImportDialog
from ycrystal.io.project import Project
from ycrystal.io.style import STYLE_PARTS, Style, load_style, save_style

pytestmark = pytest.mark.gui

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def srtio3_style():
    scene = (
        SceneSettings(material="glossy")
        .with_element_material("Ti", "chrome")
        .with_element_material("O", "glass")
        .with_element_color("Sr", (0.9, 0.2, 0.1))
    )
    return Style.from_state(perovskite_srtio3(), scene, Environment(), (800, 600))


@pytest.fixture
def bazro3_window(qtbot):
    structure = load_input(FIXTURES / "BaZrO3.cif").structure
    win = MainWindow(project=Project(structure))
    qtbot.addWidget(win)
    win.resize(1150, 760)
    win.show()
    qtbot.waitExposed(win)
    qtbot.waitUntil(lambda: win._saved_camera is not None, timeout=5000)
    yield win
    win.close()


def test_dialog_defaults_preview_and_ambiguity(qtbot):
    structure = load_input(FIXTURES / "BaZrO3.cif").structure
    dialog = StyleImportDialog(srtio3_style(), structure)
    qtbot.addWidget(dialog)
    assert dialog.mapping_group.isVisibleTo(dialog)
    # Rows start at the transfer by matching symbols: O keeps O, Sr and Ti have no match.
    assert dialog.mapping_combo("O").currentText() == "O"
    assert dialog.mapping_combo("Ti").currentText() == LEAVE_OUT
    assert [dialog.mapping_combo("Sr").itemText(i) for i in range(4)] == [
        "Ba",
        "O",
        "Zr",
        LEAVE_OUT,
    ]
    assert dialog.element_map() == {} and dialog.parts() == STYLE_PARTS
    assert "Element settings applied: O." in dialog.summary()
    assert "Left out: Sr, Ti." in dialog.summary() and dialog.apply_button.isEnabled()
    # Choosing targets updates the preview before Apply.
    dialog.set_target("Ti", "Zr")
    dialog.set_target("Sr", "Ba")
    assert dialog.element_map() == {"Ti": "Zr", "Sr": "Ba"}
    assert "Element settings applied: O, Sr → Ba, Ti → Zr." in dialog.summary()
    # An ambiguous choice disables Apply and explains it.
    dialog.set_target("Ti", "O")
    assert not dialog.apply_button.isEnabled() and dialog.choice() is None
    assert dialog.summary().startswith("Cannot apply: O would receive the settings of both")
    dialog.set_target("O", None)  # resolved: O's own settings left out
    assert dialog.apply_button.isEnabled()
    assert dialog.choice() == StyleImportChoice(STYLE_PARTS, {"Ti": "O", "Sr": "Ba", "O": None})
    # Without the appearance part no element settings apply, so the mapping cannot clash.
    dialog.set_target("O", "O")
    dialog._boxes["appearance"].setChecked(False)
    assert dialog.apply_button.isEnabled() and "no element settings" in dialog.summary()
    dialog.reset_mapping()
    assert dialog.element_map() == {}
    # The selectors are keyboard-accessible and named for screen readers.
    combo = dialog.mapping_combo("Ti")
    assert "Ti" in combo.accessibleName() and combo.focusPolicy() != 0


def test_dialog_without_element_settings_hides_the_mapping(qtbot):
    style = Style.from_state(perovskite_srtio3(), SceneSettings(), Environment(), (800, 600))
    dialog = StyleImportDialog(style, perovskite_srtio3())
    qtbot.addWidget(dialog)
    assert not dialog.mapping_group.isVisibleTo(dialog)
    assert dialog.choice() == StyleImportChoice(STYLE_PARTS, {})


def test_dialog_apply_and_cancel_buttons(qtbot):
    structure = load_input(FIXTURES / "BaZrO3.cif").structure
    for accept in (True, False):
        dialog = StyleImportDialog(srtio3_style(), structure)
        qtbot.addWidget(dialog)
        dialog.set_target("Ti", "Zr")
        cancel = dialog.buttons.button(QDialogButtonBox.StandardButton.Cancel)
        button = dialog.apply_button if accept else cancel
        QTimer.singleShot(0, button.click)
        assert (dialog.exec() == dialog.DialogCode.Accepted) is accept


def test_mapped_import_is_one_undo_step(bazro3_window, tmp_path):
    win = bazro3_window
    path = save_style(tmp_path / "SrTiO3 look.ycstyle", srtio3_style())
    positions = win.structure.positions.copy()
    before = win.scene_settings
    steps = win.undo_stack.count()
    asked = []
    win.ask_style_import = lambda style: (
        asked.append(style) or StyleImportChoice(("appearance",), {"Ti": "Zr", "Sr": "Ba"})
    )
    assert win.import_style(path)
    assert asked and win.undo_stack.count() == steps + 1
    scene = win.scene_settings
    assert scene.element_materials == (("O", "glass"), ("Zr", "chrome"))
    assert scene.element_colors == (("Ba", (0.9, 0.2, 0.1)),) and scene.material == "glossy"
    assert win.last_style_notes == []  # everything found a place
    np.testing.assert_array_equal(win.structure.positions, positions)
    assert win.structure.symbols == ("Ba", "Zr", "O", "O", "O")
    win.undo_action.trigger()
    assert win.scene_settings == before
    win.redo_action.trigger()
    assert win.scene_settings == scene


def test_cancelled_or_invalid_import_changes_nothing(bazro3_window, tmp_path):
    win = bazro3_window
    path = save_style(tmp_path / "look.ycstyle", srtio3_style())
    before, steps = win.scene_settings, win.undo_stack.count()
    win.ask_style_import = lambda style: None  # Cancel
    assert win.import_style(path) is False
    assert win.scene_settings == before and win.undo_stack.count() == steps
    assert win.import_style(path, parts=["appearance"], element_map={"Ti": "O"}) is False
    assert win.last_error[0] == "Import Style Failed" and "Element mapping" in win.last_error[1]
    assert win.scene_settings == before and win.undo_stack.count() == steps


def test_documented_walkthrough_with_the_example_style(bazro3_window):
    """The steps of "Reuse the example style" in docs/guide/examples.md."""
    win = bazro3_window
    path = Path(__file__).resolve().parents[1] / "examples" / "grey-studio.ycstyle"
    style = load_style(path)
    dialog = StyleImportDialog(style, win.structure, win)
    assert dialog.mapping_combo("O").currentText() == "O"
    assert dialog.mapping_combo("Ti").currentText() == LEAVE_OUT
    assert dialog.summary() == "Element settings applied: O.\nLeft out: Ti."
    dialog.set_target("Ti", "Zr")
    assert dialog.summary() == "Element settings applied: O, Ti → Zr."
    choice = dialog.choice()
    dialog.set_target("Ti", "O")
    assert not dialog.apply_button.isEnabled()
    assert "O would receive the settings of both O and Ti" in dialog.summary()
    dialog.close()
    steps = win.undo_stack.count()
    assert win.import_style(path, choice.parts, choice.element_map)
    assert dict(win.scene_settings.element_materials) == {"O": "ceramic", "Zr": "chrome"}
    assert win.environment.preset == "studio_grey" and win.undo_stack.count() == steps + 1
    win.undo_action.trigger()
    assert win.scene_settings.element_materials == ()
