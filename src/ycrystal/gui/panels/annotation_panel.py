"""Controls for titles, captions, and other output-frame text."""

from __future__ import annotations

from dataclasses import replace

from PySide6.QtCore import QSignalBlocker, Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFontComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ycrystal.core.annotation import TEXT_ALIGNMENTS, TextAnnotation
from ycrystal.gui.panels.appearance_panel import ColorButton
from ycrystal.render.legend import resolved_font_family


class AnnotationPanel(QWidget):
    """Add, edit, remove, and toggle the text in a project."""

    annotations_requested = Signal(object, str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._annotations: tuple[TextAnnotation, ...] = ()
        layout = QVBoxLayout(self)
        instructions = QLabel("Add titles or captions inside the output frame.")
        instructions.setWordWrap(True)
        layout.addWidget(instructions)
        self.annotation_list = QListWidget()
        self.annotation_list.setAccessibleName("Figure text")
        self.annotation_list.currentRowChanged.connect(self._selection_changed)
        self.annotation_list.itemChanged.connect(self._toggle_item)
        self.annotation_list.itemDoubleClicked.connect(lambda _item: self._edit_item())
        layout.addWidget(self.annotation_list)

        buttons = QHBoxLayout()
        add = QPushButton("Add…")
        self.edit_button = QPushButton("Edit…")
        self.remove_button = QPushButton("Remove")
        add.clicked.connect(lambda: self._edit_item(add=True))
        self.edit_button.clicked.connect(lambda: self._edit_item())
        self.remove_button.clicked.connect(self._remove_item)
        for button in (add, self.edit_button, self.remove_button):
            buttons.addWidget(button)
        layout.addLayout(buttons)
        self._selection_changed(-1)

    def sync(self, annotations: tuple[TextAnnotation, ...]) -> None:
        """Display the project's text and visibility settings."""
        previous = self.annotation_list.currentRow()
        self._annotations = annotations
        with QSignalBlocker(self.annotation_list):
            self.annotation_list.clear()
            for label in annotations:
                title = label.text.strip().splitlines()[0]
                item = QListWidgetItem(title if len(title) <= 60 else title[:59] + "…")
                item.setCheckState(
                    Qt.CheckState.Checked if label.enabled else Qt.CheckState.Unchecked
                )
                self.annotation_list.addItem(item)
            if annotations:
                self.annotation_list.setCurrentRow(max(0, min(previous, len(annotations) - 1)))
        self._selection_changed(self.annotation_list.currentRow())

    def _selection_changed(self, row: int) -> None:
        self.edit_button.setEnabled(row >= 0)
        self.remove_button.setEnabled(row >= 0)

    def _toggle_item(self, item: QListWidgetItem) -> None:
        row = self.annotation_list.row(item)
        labels = list(self._annotations)
        enabled = item.checkState() == Qt.CheckState.Checked
        labels[row] = replace(labels[row], enabled=enabled)
        self.annotations_requested.emit(tuple(labels), "Show Text" if enabled else "Hide Text")

    def _remove_item(self) -> None:
        row = self.annotation_list.currentRow()
        if row >= 0:
            self.annotations_requested.emit(
                self._annotations[:row] + self._annotations[row + 1 :], "Remove Text"
            )

    def _edit_item(self, add: bool = False) -> None:
        row = self.annotation_list.currentRow()
        if not add and row < 0:
            return
        label = TextAnnotation("Text") if add else self._annotations[row]
        dialog = QDialog(self)
        dialog.setWindowTitle("Add Figure Text" if add else "Edit Figure Text")
        form = QFormLayout(dialog)
        text = QPlainTextEdit()
        text.setPlaceholderText("Title or caption")
        text.setMaximumHeight(108)
        text.setPlainText("" if add else label.text)
        form.addRow("Text", text)
        x = _percent(100 * label.x)
        y = _percent(100 * label.y)
        form.addRow("X from left", x)
        form.addRow("Y from top", y)
        alignment = QComboBox()
        for name in TEXT_ALIGNMENTS:
            alignment.addItem(name.capitalize(), name)
        alignment.setCurrentIndex(alignment.findData(label.alignment))
        form.addRow("Alignment", alignment)
        font = QFontComboBox()
        font.setCurrentFont(QFont(resolved_font_family(label.font_family)))
        form.addRow("Font", font)
        size = _percent(label.font_size, minimum=0.5)
        size.setToolTip("Font size as a percentage of the output image height")
        form.addRow("Font size", size)
        colour = ColorButton("Figure Text Colour")
        colour.set_color(label.color)
        colour.color_chosen.connect(colour.set_color)
        form.addRow("Colour", colour)
        bold = QCheckBox("Bold")
        bold.setChecked(label.bold)
        form.addRow(bold)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        ok = buttons.button(QDialogButtonBox.StandardButton.Ok)
        ok.setEnabled(bool(text.toPlainText().strip()))
        text.textChanged.connect(lambda: ok.setEnabled(bool(text.toPlainText().strip())))
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        form.addRow(buttons)
        text.setFocus()
        if dialog.exec() == QDialog.DialogCode.Accepted:
            updated = TextAnnotation(
                text=text.toPlainText(),
                x=x.value() / 100,
                y=y.value() / 100,
                font_size=size.value(),
                font_family=font.currentFont().family(),
                color=colour.color(),
                alignment=alignment.currentData(),
                bold=bold.isChecked(),
                enabled=label.enabled,
            )
            labels = list(self._annotations)
            if add:
                labels.append(updated)
            else:
                labels[row] = updated
            self.annotations_requested.emit(tuple(labels), dialog.windowTitle())


def _percent(value: float, minimum: float = 0.0) -> QDoubleSpinBox:
    spin = QDoubleSpinBox()
    spin.setRange(minimum, 100)
    spin.setDecimals(2)
    spin.setSuffix(" %")
    spin.setValue(value)
    return spin
