"""Measurements panel: the table of completed distances and angles (FR-MEASURE-01).

Like the other panels it holds no measurement state: the main window passes the rows
([`set_rows`][ycrystal.gui.panels.measurement_panel.MeasurementPanel.set_rows]) and
applies the removals the panel requests. Copying is local: the selected rows' copy texts
go to the clipboard.
"""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction, QGuiApplication, QKeySequence
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

HEADERS = ("Type", "Atoms", "Result")

ATOMS_TIP = (
    "A, B, C in the order picked. Each atom: element (input label), atom number, and "
    "periodic image [na nb nc] relative to the input position. The exact picked images "
    "are measured; no minimum-image convention is applied."
)


@dataclass(frozen=True)
class MeasurementRow:
    """Text of one table row.

    Attributes
    ----------
    kind
        ``"Distance"`` or ``"Angle"``.
    atoms
        Labelled atom identities, e.g. ``"A: Sr #1 [0 0 0] · B: O #3 [0 0 0]"``.
    result
        Value with unit, e.g. ``"2.0134 Å"`` or ``"156.28° — vertex B"``.
    copy
        Self-contained line for the clipboard (identities, unit, vertex).
    exact
        Full-precision value for the tooltip.
    """

    kind: str
    atoms: str
    result: str
    copy: str
    exact: str


class MeasurementPanel(QWidget):
    """Table of measurements with Copy Selected, Remove Selected, and Clear All."""

    remove_requested = Signal(list)
    """Rows (indices) the user wants removed."""

    clear_requested = Signal()
    """The user wants all measurements removed."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 4)
        self.table = QTableWidget(0, len(HEADERS))
        self.table.setHorizontalHeaderLabels(HEADERS)
        self.table.horizontalHeaderItem(1).setToolTip(ATOMS_TIP)
        self.table.setAccessibleName("Measurements")
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setWordWrap(False)
        self.table.verticalHeader().setVisible(False)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setMinimumHeight(60)
        self.table.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
        layout.addWidget(self.table, 1)

        row = QHBoxLayout()
        self.note_label = QLabel()
        self.note_label.setWordWrap(True)
        self.note_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        row.addWidget(self.note_label, 1)
        self.copy_button = QPushButton("Copy Selected")
        self.copy_button.setToolTip(
            "Copy the selected measurements with atom identities, units, and the angle "
            "vertex (Ctrl+C in the table)"
        )
        self.remove_button = QPushButton("Remove Selected")
        self.remove_button.setToolTip("Remove the selected measurements from the table")
        self.clear_button = QPushButton("Clear All")
        self.clear_button.setToolTip("Remove all measurements")
        for button in (self.copy_button, self.remove_button, self.clear_button):
            row.addWidget(button)
        layout.addLayout(row)

        copy_action = QAction("Copy", self.table)
        copy_action.setShortcut(QKeySequence.StandardKey.Copy)
        copy_action.setShortcutContext(Qt.ShortcutContext.WidgetShortcut)
        copy_action.triggered.connect(self.copy_selected)
        self.table.addAction(copy_action)
        self.copy_button.clicked.connect(self.copy_selected)
        self.remove_button.clicked.connect(lambda: self.remove_requested.emit(self.selected_rows()))
        self.clear_button.clicked.connect(self.clear_requested.emit)
        self.table.itemSelectionChanged.connect(self._update_buttons)
        self._rows: list[MeasurementRow] = []
        self._update_buttons()

    def set_rows(self, rows: list[MeasurementRow]) -> None:
        """Show ``rows`` (oldest first) and scroll to the newest."""
        self._rows = list(rows)
        self.table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            for column, text in enumerate((row.kind, row.atoms, row.result)):
                item = QTableWidgetItem(text)
                item.setToolTip(row.copy if column != 2 else f"{row.result} (exact {row.exact})")
                self.table.setItem(r, column, item)
        if rows:
            self.table.scrollToBottom()
        self._update_buttons()

    def rows(self) -> list[MeasurementRow]:
        """Return the rows shown."""
        return list(self._rows)

    def selected_rows(self) -> list[int]:
        """Return the indices of the selected rows, in table order."""
        return sorted({index.row() for index in self.table.selectionModel().selectedRows()})

    def copy_text(self) -> str:
        """Return the copy text of the selected rows, one line each."""
        return "\n".join(self._rows[r].copy for r in self.selected_rows())

    def copy_selected(self) -> None:
        """Put the selected rows' copy text on the clipboard."""
        text = self.copy_text()
        if text:
            QGuiApplication.clipboard().setText(text)

    def set_note(self, text: str) -> None:
        """Show a short note under the table (e.g. why measurements were removed)."""
        self.note_label.setText(text)

    def _update_buttons(self) -> None:
        selected = bool(self.selected_rows())
        self.copy_button.setEnabled(selected)
        self.remove_button.setEnabled(selected)
        self.clear_button.setEnabled(bool(self._rows))
