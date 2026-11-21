"""Legend panel: the element legend drawn onto the figure (FR-LEGEND-01).

Like the other panels, it only emits requests: each edit is one complete
[`LegendSettings`][ycrystal.core.legend.LegendSettings], which the main window applies
as an undoable step and then shows again through
[`LegendPanel.sync`][ycrystal.gui.panels.legend_panel.LegendPanel.sync], with signals
blocked.
"""

from __future__ import annotations

from dataclasses import replace

from PySide6.QtCore import QSize, Signal
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ycrystal.core.legend import LegendSettings
from ycrystal.gui.panels.appearance_panel import ColorButton

LAYOUT_NAMES = {"horizontal": "Horizontal (one row)", "vertical": "Vertical (one column)"}
"""Legend layouts as named in the panel."""

POSITION_NAMES = {
    "bottom": "Bottom",
    "top": "Top",
    "left": "Left",
    "right": "Right",
    "custom": "Custom",
}
"""Legend positions as named in the panel."""

MARKER_NAMES = {"sphere": "Shaded sphere", "flat": "Flat disc"}
"""Marker styles as named in the panel."""

ORDER_NAMES = {
    "structure": "As in the structure",
    "atomic_number": "By atomic number",
    "alphabetical": "Alphabetical",
    "custom": "Custom",
}
"""Element orders as named in the panel."""

TEXT_UNIT = " × text"
"""Suffix of sizes given in multiples of the text height."""


def _spin(
    minimum: float, maximum: float, step: float, decimals: int, suffix: str
) -> QDoubleSpinBox:
    spin = QDoubleSpinBox()
    spin.setRange(minimum, maximum)
    spin.setSingleStep(step)
    spin.setDecimals(decimals)
    spin.setSuffix(suffix)
    spin.setKeyboardTracking(False)  # typed values apply on Enter / focus change
    return spin


def _combo(names: dict[str, str]) -> QComboBox:
    combo = QComboBox()
    for key, name in names.items():
        combo.addItem(name, key)
    return combo


class LegendPanel(QScrollArea):
    """Show, place, and style the element legend.

    The element list shows the legend's order; moving an element up or down switches to
    the custom order. *Fit View Beside Legend* asks the window to fit the structure into
    the space the legend leaves free.
    """

    legend_requested = Signal(object, str, str)
    """New ``(LegendSettings, undo text, merge key)`` from one edit."""

    fit_requested = Signal()
    """*Fit View Beside Legend* was pressed."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setFrameShape(QScrollArea.Shape.NoFrame)
        self._legend = LegendSettings()
        self._elements: list[str] = []
        self._syncing = False
        self._select_after_sync: str | None = None  # element to reselect after a move
        content = QWidget()
        layout = QVBoxLayout(content)

        group = QGroupBox("Element legend")
        form = QFormLayout(group)
        self.enabled_check = QCheckBox("Show the element legend")
        self.enabled_check.setToolTip(
            "Draw a coloured marker and the symbol of every displayed element onto the "
            "figure: in the view, the preview, renders, and exports."
        )
        self.enabled_check.toggled.connect(
            lambda on: self._edit("Show Legend" if on else "Hide Legend", enabled=on)
        )
        form.addRow(self.enabled_check)
        self.layout_combo = _combo(LAYOUT_NAMES)
        self.layout_combo.activated.connect(
            lambda _i: self._edit("Legend Layout", layout=self.layout_combo.currentData())
        )
        form.addRow("Layout", self.layout_combo)
        self.position_combo = _combo(POSITION_NAMES)
        self.position_combo.activated.connect(
            lambda _i: self._edit("Legend Position", position=self.position_combo.currentData())
        )
        form.addRow("Position", self.position_combo)
        self.x_spin = _spin(0.0, 100.0, 1.0, 1, " %")
        self.y_spin = _spin(0.0, 100.0, 1.0, 1, " %")
        self.x_spin.setToolTip("Centre of the legend, from the left edge of the image")
        self.y_spin.setToolTip("Centre of the legend, from the top edge of the image")
        self.x_spin.valueChanged.connect(
            lambda v: self._edit("Legend Position", "legend-x", x=v / 100.0)
        )
        self.y_spin.valueChanged.connect(
            lambda v: self._edit("Legend Position", "legend-y", y=v / 100.0)
        )
        centre = QHBoxLayout()
        centre.addWidget(QLabel("x"))
        centre.addWidget(self.x_spin)
        centre.addWidget(QLabel("y"))
        centre.addWidget(self.y_spin)
        self.centre_label = QLabel("Centre")
        form.addRow(self.centre_label, centre)
        self.margin_spin = _spin(0.0, 20.0, 0.1, 2, TEXT_UNIT)
        self.margin_spin.setToolTip(
            "Gap between the legend and the image edge, and between the legend and the "
            "structure after Fit, in multiples of the text height"
        )
        self.margin_spin.valueChanged.connect(
            lambda v: self._edit("Legend Margin", "legend-margin", margin=v)
        )
        form.addRow("Margin", self.margin_spin)
        self.fit_button = QPushButton("Fit View Beside Legend")
        self.fit_button.setToolTip(
            "Fit the structure into the part of the frame the legend leaves free (also View ▸ Fit)"
        )
        self.fit_button.clicked.connect(self.fit_requested)
        form.addRow(self.fit_button)
        layout.addWidget(group)

        group = QGroupBox("Text")
        form = QFormLayout(group)
        self.font_combo = QComboBox()
        self.font_combo.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        self.font_combo.setMinimumContentsLength(10)
        self.font_combo.setToolTip("Font family of the element symbols")
        self.font_combo.activated.connect(
            lambda _i: self._edit("Legend Font", font_family=self.font_combo.currentData())
        )
        form.addRow("Font", self.font_combo)
        self.size_spin = _spin(0.5, 25.0, 0.5, 1, " % of height")
        self.size_spin.setToolTip(
            "Text height in percent of the image height, so that previews and exports of "
            "any size show the same legend"
        )
        self.size_spin.valueChanged.connect(
            lambda v: self._edit("Legend Text Size", "legend-font-size", font_size=v)
        )
        form.addRow("Size", self.size_spin)
        self.text_button = ColorButton("Legend Text Colour")
        self.text_button.color_chosen.connect(
            lambda rgb: self._edit("Legend Text Colour", text_color=rgb)
        )
        form.addRow("Colour", self.text_button)
        layout.addWidget(group)

        group = QGroupBox("Markers")
        form = QFormLayout(group)
        self.marker_combo = _combo(MARKER_NAMES)
        self.marker_combo.activated.connect(
            lambda _i: self._edit("Legend Markers", marker_style=self.marker_combo.currentData())
        )
        form.addRow("Style", self.marker_combo)
        self.marker_spin = _spin(0.2, 4.0, 0.05, 2, TEXT_UNIT)
        self.marker_spin.setToolTip("Marker diameter in multiples of the text height")
        self.marker_spin.valueChanged.connect(
            lambda v: self._edit("Legend Marker Size", "legend-marker", marker_size=v)
        )
        form.addRow("Size", self.marker_spin)
        self.spacing_spin = _spin(0.0, 10.0, 0.1, 2, TEXT_UNIT)
        self.spacing_spin.setToolTip(
            "Gap between neighbouring entries in multiples of the text height"
        )
        self.spacing_spin.valueChanged.connect(
            lambda v: self._edit("Legend Spacing", "legend-spacing", spacing=v)
        )
        form.addRow("Spacing", self.spacing_spin)
        layout.addWidget(group)

        group = QGroupBox("Background")
        form = QFormLayout(group)
        self.background_check = QCheckBox("Box behind the legend")
        self.background_check.toggled.connect(
            lambda on: self._edit("Legend Background", background=on)
        )
        form.addRow(self.background_check)
        self.background_button = ColorButton("Legend Background Colour")
        self.background_button.color_chosen.connect(
            lambda rgb: self._edit("Legend Background Colour", background_color=rgb)
        )
        form.addRow("Colour", self.background_button)
        self.opacity_spin = _spin(0.0, 100.0, 5.0, 0, " %")
        self.opacity_spin.setToolTip("Opacity of the box: 0 % transparent, 100 % opaque")
        self.opacity_spin.valueChanged.connect(
            lambda v: self._edit(
                "Legend Background Opacity", "legend-opacity", background_opacity=v / 100.0
            )
        )
        form.addRow("Opacity", self.opacity_spin)
        layout.addWidget(group)

        group = QGroupBox("Order")
        box = QVBoxLayout(group)
        self.order_combo = _combo(ORDER_NAMES)
        self.order_combo.activated.connect(self._order_chosen)
        box.addWidget(self.order_combo)
        row = QHBoxLayout()
        self.element_list = QListWidget()
        self.element_list.setAccessibleName("Legend entries in order")
        self.element_list.setMaximumHeight(140)
        row.addWidget(self.element_list)
        buttons = QVBoxLayout()
        self.up_button = QPushButton("Up")
        self.down_button = QPushButton("Down")
        self.up_button.setToolTip("Move the selected element up (switches to the custom order)")
        self.down_button.setToolTip("Move the selected element down (switches to the custom order)")
        self.up_button.clicked.connect(lambda: self.move_element(-1))
        self.down_button.clicked.connect(lambda: self.move_element(1))
        self.element_list.currentRowChanged.connect(lambda _r: self._update_buttons())
        buttons.addWidget(self.up_button)
        buttons.addWidget(self.down_button)
        buttons.addStretch(1)
        row.addLayout(buttons)
        box.addLayout(row)
        layout.addWidget(group)
        layout.addStretch(1)
        self.setWidget(content)
        self.sync(LegendSettings(), [], "")

    def sizeHint(self) -> QSize:  # noqa: N802 - Qt API name
        hint = super().sizeHint()
        return QSize(max(hint.width(), 300), hint.height())

    # ----- requests -------------------------------------------------------------------
    def _edit(self, text: str, merge_key: str = "", **changes: object) -> None:
        if self._syncing:
            return
        new = replace(self._legend, **changes)
        if new != self._legend:
            self.legend_requested.emit(new, text, merge_key)

    def _order_chosen(self, _index: int) -> None:
        order = self.order_combo.currentData()
        if order == "custom" and not self._legend.custom_order:
            # Start the custom order from the order shown now.
            self._edit("Legend Order", order=order, custom_order=tuple(self._elements))
        else:
            self._edit("Legend Order", order=order)

    def move_element(self, step: int) -> None:
        """Move the selected element by ``step`` rows and request the custom order."""
        row = self.element_list.currentRow()
        target = row + step
        if row < 0 or not 0 <= target < len(self._elements):
            return
        order = list(self._elements)
        order[row], order[target] = order[target], order[row]
        self._select_after_sync = order[target]
        self._edit("Legend Order", order="custom", custom_order=tuple(order))

    # ----- state ----------------------------------------------------------------------
    def sync(self, legend: LegendSettings, elements: list[str], default_family: str) -> None:
        """Show ``legend`` without emitting requests.

        Parameters
        ----------
        legend
            The figure's legend settings.
        elements
            The displayed elements in the legend's order.
        default_family
            The family the default font resolves to here (named in the font list).
        """
        self._syncing = True
        try:
            self._legend = legend
            self._elements = list(elements)
            self.enabled_check.setChecked(legend.enabled)
            for combo, value in (
                (self.layout_combo, legend.layout),
                (self.position_combo, legend.position),
                (self.marker_combo, legend.marker_style),
                (self.order_combo, legend.order),
            ):
                combo.setCurrentIndex(combo.findData(value))
            custom = legend.position == "custom"
            for widget in (self.x_spin, self.y_spin, self.centre_label):
                widget.setEnabled(custom)
            self.margin_spin.setEnabled(not custom)
            self.fit_button.setEnabled(legend.enabled and not custom)
            self.x_spin.setValue(legend.x * 100.0)
            self.y_spin.setValue(legend.y * 100.0)
            self.margin_spin.setValue(legend.margin)
            self._fill_fonts(legend.font_family, default_family)
            self.size_spin.setValue(legend.font_size)
            self.text_button.set_color(legend.text_color)
            self.marker_spin.setValue(legend.marker_size)
            self.spacing_spin.setValue(legend.spacing)
            self.background_check.setChecked(legend.background)
            self.background_button.set_color(legend.background_color)
            self.background_button.setEnabled(legend.background)
            self.opacity_spin.setValue(legend.background_opacity * 100.0)
            self.opacity_spin.setEnabled(legend.background)
            selected = self._select_after_sync
            if selected is None and self.element_list.currentItem() is not None:
                selected = self.element_list.currentItem().text()
            self._select_after_sync = None
            self.element_list.clear()
            self.element_list.addItems(self._elements)
            if selected in self._elements:
                self.element_list.setCurrentRow(self._elements.index(selected))
            self._update_buttons()
        finally:
            self._syncing = False

    def _fill_fonts(self, family: str, default_family: str) -> None:
        if self.font_combo.count() == 0 or self.font_combo.itemData(0) != "":
            self.font_combo.clear()
            self.font_combo.addItem("Default", "")
            for name in QFontDatabase.families():
                if not QFontDatabase.isPrivateFamily(name):
                    self.font_combo.addItem(name, name)
        self.font_combo.setItemText(
            0, f"Default ({default_family})" if default_family else "Default"
        )
        index = self.font_combo.findData(family)
        if index < 0:  # a family saved on another computer and not installed here
            self.font_combo.addItem(f"{family} (not installed)", family)
            index = self.font_combo.count() - 1
        self.font_combo.setCurrentIndex(index)

    def _update_buttons(self) -> None:
        row = self.element_list.currentRow()
        self.up_button.setEnabled(row > 0)
        self.down_button.setEnabled(0 <= row < len(self._elements) - 1)
