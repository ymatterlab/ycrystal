"""Colour dialog: typed notations stay in sync; hovering names colours."""

import pytest
from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication

from ycrystal.core.colors import format_color, parse_color
from ycrystal.core.samples import perovskite_srtio3
from ycrystal.gui.color_dialog import ColorDialog
from ycrystal.gui.main_window import MainWindow
from ycrystal.io.project import Project

pytestmark = pytest.mark.gui


@pytest.fixture
def dialog(qtbot):
    dlg = ColorDialog((0.75, 0.76, 0.78), "Colour of Ti")
    qtbot.addWidget(dlg)
    dlg.show()
    qtbot.waitExposed(dlg)
    return dlg


def move(widget, x, y):
    point = QPointF(x, y)
    QApplication.sendEvent(
        widget,
        QMouseEvent(
            QEvent.Type.MouseMove,
            point,
            widget.mapToGlobal(point),
            Qt.MouseButton.NoButton,
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
        ),
    )


def click(widget, x, y):
    point = QPointF(x, y)
    for kind, buttons in (
        (QEvent.Type.MouseButtonPress, Qt.MouseButton.LeftButton),
        (QEvent.Type.MouseButtonRelease, Qt.MouseButton.NoButton),
    ):
        QApplication.sendEvent(
            widget,
            QMouseEvent(
                kind,
                point,
                widget.mapToGlobal(point),
                Qt.MouseButton.LeftButton,
                buttons,
                Qt.KeyboardModifier.NoModifier,
            ),
        )


def test_initial_colour_is_named_in_every_notation(dialog):
    assert dialog.hex_edit.text() == "#BFC2C7"
    assert [s.value() for s in dialog.rgb255] == [191, 194, 199]
    assert [s.value() for s in dialog.rgb01] == pytest.approx([0.75, 0.76, 0.78])
    assert "light grey" in dialog.name_label.text() and "silver" in dialog.name_label.text()


def test_typed_notations_stay_in_sync(dialog):
    dialog.hex_edit.setText("#ff8000")
    dialog.hex_edit.editingFinished.emit()
    assert format_color(dialog.color()) == "#FF8000"
    assert [s.value() for s in dialog.rgb255] == [255, 128, 0]
    assert [s.value() for s in dialog.hsl] == pytest.approx([30.1, 100, 50])
    assert "orange" in dialog.name_label.text()
    dialog.rgb255[2].setValue(255)  # 255 128 255
    assert format_color(dialog.color()) == "#FF80FF" and dialog.hex_edit.text() == "#FF80FF"
    dialog.rgb01[0].setValue(0.2)  # fractions keep three decimals (not rounded to 8 bit)
    assert dialog.color()[0] == pytest.approx(0.2)
    dialog.hsv[0].setValue(120)
    dialog.hsv[1].setValue(100)
    dialog.hsv[2].setValue(100)
    assert format_color(dialog.color()) == "#00FF00"
    dialog.hsl[2].setValue(25)
    assert format_color(dialog.color()) == format_color(parse_color("hsl(120, 100%, 25%)"))
    dialog.text_edit.setText("steel blue")
    dialog.text_edit.returnPressed.emit()
    assert format_color(dialog.color()) == "#4682B4"
    assert "steel blue" in dialog.name_label.text()
    dialog.text_edit.setText("0.1 0.2 0.3")
    dialog.text_edit.returnPressed.emit()
    assert dialog.color() == pytest.approx((0.1, 0.2, 0.3))


def test_invalid_text_is_explained_and_ignored(dialog):
    before = dialog.color()
    dialog.text_edit.setText("ultraviolet")
    dialog.text_edit.returnPressed.emit()
    assert dialog.color() == before
    assert "colour name" in dialog.error_label.text()
    dialog.hex_edit.setText("#12")
    dialog.hex_edit.editingFinished.emit()
    assert dialog.color() == before and dialog.error_label.text()


def test_hovering_the_spectrum_names_the_colour(dialog):
    field = dialog.spectrum
    dialog.saturation_slider.setValue(100)
    move(field, 1, field.height() / 2)  # hue 0, lightness ~50 %: red
    assert "red" in dialog.hover_text() and "#FF" in dialog.hover_text()
    move(field, field.width() * 240 / 360, field.height() / 2)  # hue 240: blue
    assert "blue" in dialog.hover_text()
    QApplication.sendEvent(field, QEvent(QEvent.Type.Leave))
    assert "Rest the mouse" in dialog.hover_text()
    click(field, field.width() * 120 / 360, field.height() / 2)  # choose green
    assert "green" in dialog.name_label.text()


def test_hovering_a_named_colour_shows_its_name(dialog):
    grid = dialog.swatches
    index = next(i for i, (name, _) in enumerate(grid.swatches) if name == "tomato")
    rect = grid.cell_rect(index)
    move(grid, rect.center().x(), rect.center().y())
    assert "tomato" in dialog.hover_text()
    click(grid, rect.center().x(), rect.center().y())
    assert format_color(dialog.color()) == "#FF6347"


def test_colour_buttons_name_their_colour_and_use_the_dialog(qtbot, monkeypatch):
    window = MainWindow(project=Project(perovskite_srtio3()))
    qtbot.addWidget(window)
    try:
        button, _, _ = window.appearance_panel.element_widgets("O")
        assert "Colour of O: red" in button.toolTip()
        assert button.accessibleName().startswith("Colour of O: red")
        monkeypatch.setattr(
            ColorDialog, "get_color", staticmethod(lambda initial, parent, title: (0.1, 0.3, 0.9))
        )
        button.click()
        assert dict(window.scene_settings.element_colors) == {"O": (0.1, 0.3, 0.9)}
        assert "blue" in window.appearance_panel.element_widgets("O")[0].toolTip()
        monkeypatch.setattr(
            ColorDialog, "get_color", staticmethod(lambda initial, parent, title: None)
        )
        steps = window.undo_stack.count()
        button.click()  # cancelled: nothing changes
        assert window.undo_stack.count() == steps
        assert "floor" in window.appearance_panel.floor_button.toolTip().lower()
    finally:
        window.close()


# ----- FR-COLOR-01 acceptance in the window -----------------------------------------------
def test_each_representation_sets_the_same_dialog_colour(dialog):
    def entered(action):
        action()
        return format_color(dialog.color())

    results = {
        "rgb": entered(
            lambda: [s.setValue(v) for s, v in zip(dialog.rgb255, (255, 0, 0), strict=True)]
        ),
        "hex": entered(
            lambda: (dialog.hex_edit.setText("#ff0000"), dialog.hex_edit.editingFinished.emit())
        ),
        "hsv": entered(
            lambda: [s.setValue(v) for s, v in zip(dialog.hsv, (0, 100, 100), strict=True)]
        ),
        "hsl": entered(
            lambda: [s.setValue(v) for s, v in zip(dialog.hsl, (0, 100, 50), strict=True)]
        ),
        "name": entered(
            lambda: (dialog.text_edit.setText("red"), dialog.text_edit.returnPressed.emit())
        ),
    }
    assert set(results.values()) == {"#FF0000"}, results
    assert dialog.hsv[2].accessibleName() == "HSV value in percent"
    assert dialog.hsl[2].accessibleName() == "HSL lightness in percent"


def test_grey_keeps_the_typed_hue(dialog):
    for spin, value in zip(dialog.hsv, (210, 0, 50), strict=True):
        spin.setValue(value)
    assert format_color(dialog.color()) == "#808080"
    assert dialog.hsl[0].value() == pytest.approx(210)  # hue kept, RGB unchanged
    dialog.hsl[1].setValue(60)  # saturating again continues from that hue
    assert "blue" in dialog.name_label.text()


def test_invalid_text_blocks_ok(dialog):
    dialog.text_edit.setText("ultraviolet")
    dialog.text_edit.textEdited.emit("ultraviolet")
    assert not dialog.ok_button.isEnabled() and dialog.error_label.text()
    dialog.accept()
    assert dialog.result() != dialog.DialogCode.Accepted and dialog.isVisible()
    dialog.text_edit.setText("teal")
    dialog.text_edit.textEdited.emit("teal")
    assert dialog.ok_button.isEnabled()
    dialog.accept()  # unapplied valid text is applied on OK
    assert format_color(dialog.color()) == "#008080"


def test_keyboard_only_selection_and_names(dialog, qtbot):
    grid = dialog.swatches
    grid.setFocus()  # without a window manager (CI) focus may not arrive; keys go directly
    start = grid.current
    qtbot.keyClick(grid, Qt.Key.Key_Right)
    assert grid.current == start + 1
    assert "Keyboard focus" in dialog.hover_text()
    name = grid.swatches[grid.current][0]
    assert name in dialog.hover_text() and "RGB (" in dialog.hover_text()
    assert name in grid.accessibleName()
    qtbot.keyClick(grid, Qt.Key.Key_Return)
    assert dialog.color() == grid.swatches[grid.current][1]
    assert "#" in dialog.name_label.text() and "RGB (" in dialog.name_label.text()


def test_spectrum_hover_does_not_assign(dialog):
    before = dialog.color()
    field = dialog.spectrum
    first, second = field.width() * 0.1, field.width() * 0.6
    move(field, first, field.height() / 2)
    text_one = dialog.hover_text()
    move(field, second, field.height() / 2)
    assert dialog.hover_text() != text_one and "RGB (" in dialog.hover_text()
    assert dialog.color() == before  # hovering identifies; clicking selects


def test_named_swatch_tooltip_text(dialog):
    grid = dialog.swatches
    index = next(i for i, (n, _) in enumerate(grid.swatches) if n == "red")
    assert grid.describe(index) == "red — #FF0000 — RGB (255, 0, 0)"


def test_cancel_undo_persistence_and_export(qtbot, monkeypatch, tmp_path):
    from ycrystal.core.colors import parse_color as parse
    from ycrystal.io.project import load_project
    from ycrystal.io.style import Style, apply_style, load_style, save_style

    window = MainWindow(project=Project(perovskite_srtio3()))
    qtbot.addWidget(window)
    try:
        original = window.structure.positions.copy()
        button = window.appearance_panel.element_widgets("Ti")[0]
        monkeypatch.setattr(ColorDialog, "get_color", staticmethod(lambda *a: None))
        button.click()  # Cancel: nothing changes, nothing on the undo stack
        assert window.scene_settings.element_colors == () and window.undo_stack.count() == 0
        chosen = parse("hsl(200, 80%, 40%)")
        monkeypatch.setattr(ColorDialog, "get_color", staticmethod(lambda *a: chosen))
        window.set_element_material("Ti", "glossy")
        window.set_element_radius("Ti", 0.7)
        before = window.scene_settings
        button.click()
        assert dict(window.scene_settings.element_colors)["Ti"] == chosen
        assert window.undo_stack.count() == 3  # material, radius, colour: one step each
        window.undo_action.trigger()
        assert window.scene_settings == before
        window.redo_action.trigger()
        settings = window.scene_settings
        assert dict(settings.element_materials) == {"Ti": "glossy"}  # unchanged
        assert dict(settings.element_radii) == {"Ti": 0.7}
        ti = window.geometry.elements.index("Ti")
        assert tuple(window.geometry.colors[ti]) == chosen  # live view and export share it
        expected = "Ycr_sRGB(" + ", ".join(f"{c:.4f}" for c in chosen) + ")"
        pov = window.export_pov(tmp_path / "ti.pov").read_text()
        assert expected in pov
        assert window.save_as(tmp_path / "ti.ycrystal")
        assert dict(load_project(tmp_path / "ti.ycrystal").scene.element_colors)["Ti"] == chosen
        style = load_style(save_style(tmp_path / "ti.ycstyle", window.current_style()))
        result = apply_style(style, window.structure, Project(window.structure).scene,
                             window.environment, (100, 100))  # fmt: skip
        assert dict(result.scene.element_colors)["Ti"] == chosen
        assert isinstance(style, Style)
        import numpy as np

        np.testing.assert_array_equal(window.structure.positions, original)
    finally:
        window.close()


def test_colour_note_for_materials_with_own_pigment(qtbot):
    window = MainWindow(project=Project(perovskite_srtio3()))
    qtbot.addWidget(window)
    try:
        window.set_element_material("Ti", "gold")
        tip = window.appearance_panel.element_widgets("Ti")[0].toolTip()
        assert "Not visible with the material Gold" in tip
        assert "Not visible" not in window.appearance_panel.element_widgets("O")[0].toolTip()
    finally:
        window.close()


def test_dialog_does_not_take_the_button_colour(qtbot):
    """Regression: the colour button's style sheet must not cascade into the dialog."""
    window = MainWindow(project=Project(perovskite_srtio3()))
    qtbot.addWidget(window)
    try:
        button = window.appearance_panel.element_widgets("Sr")[0]  # bright green
        assert button.styleSheet().startswith("QPushButton#colorButton {")
        plain = ColorDialog((0.0, 1.0, 0.0), "plain")
        child = ColorDialog((0.0, 1.0, 0.0), "child of the button", button)
        for dlg in (plain, child):
            qtbot.addWidget(dlg)
            dlg.show()
            qtbot.waitExposed(dlg)
        corner = (4, 4)
        assert child.grab().toImage().pixelColor(*corner) == plain.grab().toImage().pixelColor(
            *corner
        )
        captured = {}
        monkey = ColorDialog.get_color
        try:
            ColorDialog.get_color = staticmethod(
                lambda initial, parent, title: captured.update(parent=parent)  # cancel
            )
            button.click()
        finally:
            ColorDialog.get_color = staticmethod(monkey)
        assert captured["parent"] is window  # opened from the window, not the button
    finally:
        window.close()
