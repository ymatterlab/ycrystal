"""User controls for coordination polyhedra."""

from __future__ import annotations

from dataclasses import replace

from PySide6.QtCore import QSignalBlocker, Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ycrystal.core.polyhedra import PolyhedronRule
from ycrystal.gui.panels.appearance_panel import ColorButton


class PolyhedraPanel(QWidget):
    """Configure and toggle the coordination rules in the current project."""

    rules_requested = Signal(object, str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._rules: tuple[PolyhedronRule, ...] = ()
        self._elements: tuple[str, ...] = ()
        layout = QVBoxLayout(self)
        instructions = QLabel("Add a rule to draw faces between ligands around a centre atom.")
        instructions.setWordWrap(True)
        layout.addWidget(instructions)
        self.rules_list = QListWidget()
        self.rules_list.setAccessibleName("Coordination rules")
        self.rules_list.currentRowChanged.connect(self._selection_changed)
        self.rules_list.itemChanged.connect(self._toggle_rule)
        self.rules_list.itemDoubleClicked.connect(lambda _item: self._edit_rule())
        layout.addWidget(self.rules_list)

        buttons = QHBoxLayout()
        self.add_button = QPushButton("Add…")
        self.edit_button = QPushButton("Edit…")
        self.remove_button = QPushButton("Remove")
        self.add_button.clicked.connect(lambda: self._edit_rule(add=True))
        self.edit_button.clicked.connect(lambda: self._edit_rule())
        self.remove_button.clicked.connect(self._remove_rule)
        for button in (self.add_button, self.edit_button, self.remove_button):
            buttons.addWidget(button)
        layout.addLayout(buttons)
        self.summary = QLabel()
        self.summary.setWordWrap(True)
        layout.addWidget(self.summary)
        self._selection_changed(-1)

    def sync(
        self, rules: tuple[PolyhedronRule, ...], elements: tuple[str, ...], count: int
    ) -> None:
        """Show the saved rules and the number of currently displayed shells."""
        previous = self.rules_list.currentRow()
        self._rules, self._elements = rules, elements
        with QSignalBlocker(self.rules_list):
            self.rules_list.clear()
            for rule in rules:
                item = QListWidgetItem(f"{rule.centre}–{rule.ligand} · {rule.cutoff:g} Å")
                item.setCheckState(
                    Qt.CheckState.Checked if rule.enabled else Qt.CheckState.Unchecked
                )
                self.rules_list.addItem(item)
            if rules:
                self.rules_list.setCurrentRow(max(0, min(previous, len(rules) - 1)))
        self._selection_changed(self.rules_list.currentRow())
        noun = "polyhedron" if count == 1 else "polyhedra"
        self.summary.setText(f"Showing {count} coordination {noun}.")

    def _selection_changed(self, row: int) -> None:
        self.add_button.setEnabled(bool(self._elements))
        self.edit_button.setEnabled(row >= 0)
        self.remove_button.setEnabled(row >= 0)

    def _toggle_rule(self, item: QListWidgetItem) -> None:
        row = self.rules_list.row(item)
        rules = list(self._rules)
        enabled = item.checkState() == Qt.CheckState.Checked
        rules[row] = replace(rules[row], enabled=enabled)
        self.rules_requested.emit(tuple(rules), "Show Polyhedra" if enabled else "Hide Polyhedra")

    def _remove_rule(self) -> None:
        row = self.rules_list.currentRow()
        if row >= 0:
            self.rules_requested.emit(
                self._rules[:row] + self._rules[row + 1 :], "Remove Polyhedron Rule"
            )

    def _edit_rule(self, add: bool = False) -> None:
        row = self.rules_list.currentRow()
        if not self._elements or (not add and row < 0):
            return
        rule = PolyhedronRule(self._elements[0], self._elements[-1]) if add else self._rules[row]
        dialog = QDialog(self)
        dialog.setWindowTitle("Add Polyhedron Rule" if add else "Edit Polyhedron Rule")
        form = QFormLayout(dialog)
        centre, ligand = QComboBox(), QComboBox()
        for combo, element in ((centre, rule.centre), (ligand, rule.ligand)):
            combo.addItems(list(dict.fromkeys((*self._elements, element))))
            combo.setCurrentText(element)
        form.addRow("Centre element", centre)
        form.addRow("Ligand element", ligand)
        distance = QDoubleSpinBox()
        distance.setRange(0.11, 20.0)
        distance.setDecimals(3)
        distance.setSuffix(" Å")
        distance.setValue(rule.cutoff)
        form.addRow("Maximum distance", distance)
        opacity = QDoubleSpinBox()
        opacity.setRange(1, 100)
        opacity.setSuffix(" %")
        opacity.setValue(100 * rule.opacity)
        form.addRow("Face opacity", opacity)
        colour = ColorButton("Polyhedron Colour")
        colour.set_color(rule.color)
        colour.color_chosen.connect(colour.set_color)
        form.addRow("Face colour", colour)
        edges = QCheckBox("Draw polyhedron edges")
        edges.setChecked(rule.show_edges)
        form.addRow(edges)
        note = QLabel()
        note.setWordWrap(True)
        form.addRow(note)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        taken = {
            (other.centre, other.ligand)
            for index, other in enumerate(self._rules)
            if add or index != row
        }

        def accept():
            if (centre.currentText(), ligand.currentText()) in taken:
                note.setText("This element pair already has a rule. Choose another pair.")
            else:
                dialog.accept()

        buttons.accepted.connect(accept)
        buttons.rejected.connect(dialog.reject)
        form.addRow(buttons)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            updated = PolyhedronRule(
                centre.currentText(),
                ligand.currentText(),
                distance.value(),
                colour.color(),
                opacity.value() / 100,
                edges.isChecked(),
                rule.enabled,
            )
            rules = list(self._rules)
            if add:
                rules.append(updated)
            else:
                rules[row] = updated
            self.rules_requested.emit(tuple(rules), dialog.windowTitle())
