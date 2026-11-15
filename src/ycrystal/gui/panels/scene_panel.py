"""Scene panel: repetitions, boundary atoms, cell edges, and bonds.

The panel only emits requests; the main window turns them into undoable commands and
calls :meth:`ScenePanel.sync` with the resulting state. Widgets are updated with their
signals blocked, so syncing never issues new requests.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ycrystal.core.bonds import Pair, PairSummary
from ycrystal.core.scene import SceneSettings

MAX_REPETITIONS = 20
CELL_MODE_LABELS = {
    "all": "All unit cells",
    "outline": "Outline of the repeated block",
    "unit": "Original cell only",
}
NO_CELL = "None"


class ScenePanel(QTabWidget):
    repetitions_requested = Signal(tuple)
    boundary_requested = Signal(bool)
    cell_mode_requested = Signal(str)  # a CELL_MODES value or "none"
    bonds_enabled_requested = Signal(bool)
    bond_tolerance_requested = Signal(float)
    bond_radius_requested = Signal(float)
    bond_pair_requested = Signal(tuple, bool)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.addTab(self._structure_tab(), "Structure")
        self.addTab(self._bonds_tab(), "Bonds")

    # ----- construction --------------------------------------------------------------
    def _structure_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)

        group = QGroupBox("Repetitions (cells along a × b × c)")
        group_layout = QVBoxLayout(group)
        row = QHBoxLayout()
        self.rep_spins: list[QSpinBox] = []
        for axis in "abc":
            spin = QSpinBox()
            spin.setRange(1, MAX_REPETITIONS)
            spin.setPrefix(f"{axis}: ")
            spin.setKeyboardTracking(False)  # typed values apply on Enter / focus change
            spin.setToolTip(f"Number of cells along {axis} (1 to {MAX_REPETITIONS})")
            spin.valueChanged.connect(self._emit_repetitions)
            self.rep_spins.append(spin)
            row.addWidget(spin)
        group_layout.addLayout(row)
        buttons = QHBoxLayout()
        self.all_minus = QPushButton("− all")
        self.all_minus.setToolTip("One cell fewer along every axis (minimum 1)")
        self.all_minus.clicked.connect(lambda: self._step_all(-1))
        self.all_plus = QPushButton("+ all")
        self.all_plus.setToolTip("One cell more along every axis")
        self.all_plus.clicked.connect(lambda: self._step_all(+1))
        self.reset_button = QPushButton("1 × 1 × 1")
        self.reset_button.setToolTip("Back to the original cell")
        self.reset_button.clicked.connect(lambda: self.repetitions_requested.emit((1, 1, 1)))
        for button in (self.all_minus, self.all_plus, self.reset_button):
            buttons.addWidget(button)
        group_layout.addLayout(buttons)
        layout.addWidget(group)

        form = QFormLayout()
        self.boundary_check = QCheckBox("Atoms on faces, edges, and corners")
        self.boundary_check.setToolTip(
            "Draw every equivalent boundary position of the repeated block (as VESTA)"
        )
        self.boundary_check.toggled.connect(self.boundary_requested.emit)
        form.addRow("Boundary", self.boundary_check)
        self.cell_combo = QComboBox()
        for mode, label in CELL_MODE_LABELS.items():
            self.cell_combo.addItem(label, mode)
        self.cell_combo.addItem(NO_CELL, "none")
        self.cell_combo.currentIndexChanged.connect(
            lambda _i: self.cell_mode_requested.emit(self.cell_combo.currentData())
        )
        form.addRow("Cell edges", self.cell_combo)
        layout.addLayout(form)

        self.counts_label = QLabel()
        self.counts_label.setWordWrap(True)
        layout.addWidget(self.counts_label)
        layout.addStretch(1)
        return tab

    def _bonds_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        self.bonds_check = QCheckBox("Show bonds")
        self.bonds_check.toggled.connect(self.bonds_enabled_requested.emit)
        layout.addWidget(self.bonds_check)
        form = QFormLayout()
        self.tolerance_spin = QDoubleSpinBox()
        self.tolerance_spin.setRange(0.80, 1.50)
        self.tolerance_spin.setSingleStep(0.05)
        self.tolerance_spin.setDecimals(2)
        self.tolerance_spin.setSuffix(" × (r₁ + r₂)")
        self.tolerance_spin.setKeyboardTracking(False)
        self.tolerance_spin.setToolTip(
            "Atoms closer than this multiple of the sum of their covalent radii are bonded"
        )
        self.tolerance_spin.valueChanged.connect(self.bond_tolerance_requested.emit)
        form.addRow("Max. length", self.tolerance_spin)
        self.radius_spin = QDoubleSpinBox()
        self.radius_spin.setRange(0.02, 0.50)
        self.radius_spin.setSingleStep(0.02)
        self.radius_spin.setDecimals(2)
        self.radius_spin.setSuffix(" Å")
        self.radius_spin.setKeyboardTracking(False)
        self.radius_spin.valueChanged.connect(self.bond_radius_requested.emit)
        form.addRow("Radius", self.radius_spin)
        layout.addLayout(form)
        layout.addWidget(QLabel("Element pairs (bonds per original cell, lengths):"))
        self.pair_list = QListWidget()
        self.pair_list.itemChanged.connect(self._emit_pair)
        layout.addWidget(self.pair_list, 1)
        note = QLabel(
            "Metal–metal pairs start switched off in compounds that contain non-metals. "
            "Bonds are drawn only between displayed atoms."
        )
        note.setWordWrap(True)
        layout.addWidget(note)
        return tab

    # ----- requests ------------------------------------------------------------------
    def repetitions(self) -> tuple[int, int, int]:
        a, b, c = (spin.value() for spin in self.rep_spins)
        return (a, b, c)

    def _emit_repetitions(self, _value: int) -> None:
        self.repetitions_requested.emit(self.repetitions())

    def _step_all(self, step: int) -> None:
        a, b, c = (max(1, min(MAX_REPETITIONS, value + step)) for value in self.repetitions())
        self.repetitions_requested.emit((a, b, c))

    def _emit_pair(self, item: QListWidgetItem) -> None:
        pair = item.data(Qt.ItemDataRole.UserRole)
        if pair is not None:
            self.bond_pair_requested.emit(tuple(pair), item.checkState() == Qt.CheckState.Checked)

    # ----- state ---------------------------------------------------------------------
    def sync(
        self,
        settings: SceneSettings,
        pairs: list[PairSummary],
        shown_atoms: int,
        shown_bonds: int,
        hidden: int,
    ) -> None:
        widgets = [
            *self.rep_spins,
            self.boundary_check,
            self.cell_combo,
            self.bonds_check,
            self.tolerance_spin,
            self.radius_spin,
            self.pair_list,
        ]
        for widget in widgets:
            widget.blockSignals(True)
        try:
            for spin, value in zip(self.rep_spins, settings.repetitions, strict=True):
                spin.setValue(value)
            self.boundary_check.setChecked(settings.boundary_images)
            mode = settings.cell_mode if settings.show_cell else "none"
            self.cell_combo.setCurrentIndex(self.cell_combo.findData(mode))
            self.bonds_check.setChecked(settings.bonds.enabled)
            self.tolerance_spin.setValue(settings.bonds.tolerance)
            self.radius_spin.setValue(settings.bonds.radius)
            for widget in (self.tolerance_spin, self.radius_spin, self.pair_list):
                widget.setEnabled(settings.bonds.enabled)
            self.pair_list.clear()
            for summary in pairs:
                self.pair_list.addItem(_pair_item(summary))
            if not pairs:
                placeholder = QListWidgetItem("No atoms within the bond tolerance")
                placeholder.setFlags(Qt.ItemFlag.NoItemFlags)
                self.pair_list.addItem(placeholder)
        finally:
            for widget in widgets:
                widget.blockSignals(False)
        a, b, c = settings.repetitions
        hidden_text = f", {hidden} hidden" if hidden else ""
        self.counts_label.setText(
            f"Showing {shown_atoms} atom{'' if shown_atoms == 1 else 's'}{hidden_text} and "
            f"{shown_bonds} bond{'' if shown_bonds == 1 else 's'} in {a} × {b} × {c} cells."
        )


def _pair_item(summary: PairSummary) -> QListWidgetItem:
    a, b = summary.pair
    if abs(summary.max_length - summary.min_length) < 5e-4:
        lengths = f"{summary.min_length:.3f} Å"
    else:
        lengths = f"{summary.min_length:.3f}–{summary.max_length:.3f} Å"
    item = QListWidgetItem(f"{a}–{b}   {summary.count} per cell   {lengths}")
    item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable)
    item.setCheckState(Qt.CheckState.Checked if summary.enabled else Qt.CheckState.Unchecked)
    item.setData(Qt.ItemDataRole.UserRole, list(summary.pair))
    return item


def pair_label(pair: Pair) -> str:
    return f"{pair[0]}–{pair[1]}"
