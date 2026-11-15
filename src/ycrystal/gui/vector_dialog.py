"""Vectors window and vector editor (FR-VECTOR-01).

[`VectorPanel`][ycrystal.gui.vector_dialog.VectorPanel] lists the vectors of the
current structure (source defaults, image overrides, and suppressions), offers the
actions on them, and edits the arrow appearance.
[`VectorEditDialog`][ycrystal.gui.vector_dialog.VectorEditDialog] enters Cartesian
components for frozen targets. Like the other panels, both only emit requests; the
main window applies them as undoable steps and calls ``sync``.
"""

from __future__ import annotations

from dataclasses import replace

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QRadioButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ycrystal.core.measure import atom_text
from ycrystal.core.structure import Structure
from ycrystal.core.vectors import (
    MEANINGS,
    STYLE_RANGES,
    Key,
    VectorRecord,
    VectorSet,
    VectorStyle,
)
from ycrystal.gui.gallery import preset_icon
from ycrystal.gui.panels.appearance_panel import ColorButton
from ycrystal.presets import custom_materials, materials

HEADERS = ("Scope", "Atom", "Image", "Components", "Meaning", "Modulus", "Shown")

NOTE = (
    "Components are Cartesian, in the structure's frame (the frame of the atom "
    "positions); the camera never changes them. A default for a source atom has the same "
    "components in every cell: Ycrystal infers no alternating signs or magnetic order, so "
    "assign an antiferromagnetic pattern explicitly (per atom or per image) or use a "
    "magnetic repeat cell. Directions are illustrations, not measured moments. A short "
    "arrow can be hidden inside its atom; make it longer in the appearance settings."
)

PREVIEW_DELAY_MS = 150
"""Pause after the last component change before the view shows it."""


def _spin(low: float, high: float, step: float, decimals: int, suffix: str = "") -> QDoubleSpinBox:
    spin = QDoubleSpinBox()
    spin.setRange(low, high)
    spin.setSingleStep(step)
    spin.setDecimals(decimals)
    spin.setSuffix(suffix)
    spin.setKeyboardTracking(False)
    return spin


class VectorPanel(QDialog):
    """The *Vectors* window: assignments table, actions, and arrow appearance."""

    add_requested = Signal()
    """Open the editor for the selected atoms."""

    edit_requested = Signal(list)
    """Open the editor for table rows (keys)."""

    reverse_requested = Signal(list)
    """Negate the components of rows."""

    remove_requested = Signal(list)
    """Remove rows."""

    visibility_requested = Signal(list, bool)
    """Show or hide the arrows of rows."""

    suppress_requested = Signal()
    """Suppress the arrows of the selected displayed atoms."""

    rows_selected = Signal(list)
    """Rows chosen in the table (to highlight their displayed atoms)."""

    style_requested = Signal(object, str, str)
    """Apply an arrow appearance: ``(style, undo text, merge key)``."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Vectors")
        self.resize(760, 640)
        self._keys: list[Key] = []
        self._visible: dict[Key, bool | None] = {}  # None: a suppression (no record)
        self._style = VectorStyle()
        self._syncing = False
        layout = QVBoxLayout(self)
        self.table = QTableWidget(0, len(HEADERS))
        self.table.setHorizontalHeaderLabels(HEADERS)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.setAccessibleName("Vectors")
        header = self.table.horizontalHeader()
        for column in range(len(HEADERS)):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.table.itemSelectionChanged.connect(self._on_selection)
        layout.addWidget(self.table, 1)
        self.summary_label = QLabel()
        self.summary_label.setWordWrap(True)
        layout.addWidget(self.summary_label)

        actions = QHBoxLayout()
        self.add_button = QPushButton("Add/Set for Selection…")
        self.add_button.setToolTip(
            "Enter a vector for the atoms selected in the 3D view (that atom or all its "
            "periodic images)"
        )
        self.edit_button = QPushButton("Edit…")
        self.reverse_button = QPushButton("Reverse")
        self.reverse_button.setToolTip("Negate the components of the chosen rows")
        self.visible_button = QPushButton("Show/Hide")
        self.visible_button.setToolTip("Hide or show the arrows of the chosen rows (data kept)")
        self.suppress_button = QPushButton("Suppress on Selected Images")
        self.suppress_button.setToolTip(
            "Draw no arrow on the selected displayed atoms, even if their source atom has a "
            "default vector"
        )
        self.remove_button = QPushButton("Remove")
        self.remove_button.setToolTip(
            "Delete the chosen rows (an image override removed: the source default applies)"
        )
        for button in (
            self.add_button,
            self.edit_button,
            self.reverse_button,
            self.visible_button,
            self.suppress_button,
            self.remove_button,
        ):
            actions.addWidget(button)
        layout.addLayout(actions)
        self.add_button.clicked.connect(self.add_requested.emit)
        self.edit_button.clicked.connect(lambda: self.edit_requested.emit(self.selected_keys()))
        self.reverse_button.clicked.connect(
            lambda: self.reverse_requested.emit(self.selected_keys())
        )
        self.remove_button.clicked.connect(lambda: self.remove_requested.emit(self.selected_keys()))
        self.visible_button.clicked.connect(self._toggle_visible)
        self.suppress_button.clicked.connect(self.suppress_requested.emit)

        group = QGroupBox("Arrow appearance (all arrows)")
        form = QFormLayout(group)
        self.show_check = QCheckBox("Show arrows")
        self.show_check.toggled.connect(lambda on: self._edit("Show Vectors", visible=on))
        form.addRow(self.show_check)
        self.placement_combo = QComboBox()
        self.placement_combo.addItem("Centred on atom", "centred")
        self.placement_combo.addItem("Tail at atom centre", "tail")
        self.placement_combo.currentIndexChanged.connect(
            lambda _i: self._edit("Arrow Placement", placement=self.placement_combo.currentData())
        )
        form.addRow("Placement", self.placement_combo)
        self.mode_combo = QComboBox()
        self.mode_combo.addItem("Uniform length", "uniform")
        self.mode_combo.addItem("Proportional to modulus", "proportional")
        self.mode_combo.setToolTip(
            "Uniform: every arrow has the same length; proportional: length = scale × modulus. "
            "Switching never changes the components."
        )
        self.mode_combo.currentIndexChanged.connect(
            lambda _i: self._edit("Arrow Length Mode", length_mode=self.mode_combo.currentData())
        )
        form.addRow("Length", self.mode_combo)
        self.length_spin = _spin(*STYLE_RANGES["length"], 0.1, 2, " Å")
        self.length_spin.setToolTip("Total arrow length (head included) for uniform length")
        self.length_spin.valueChanged.connect(
            lambda v: self._edit("Arrow Length", "vec:length", length=v)
        )
        form.addRow("Uniform length", self.length_spin)
        self.scale_spin = _spin(*STYLE_RANGES["scale"], 0.05, 2, " Å per unit")
        self.scale_spin.setToolTip(
            "Proportional length: Å per μB for magnetic moments, Å per unit for directions"
        )
        self.scale_spin.valueChanged.connect(
            lambda v: self._edit("Arrow Scale", "vec:scale", scale=v)
        )
        form.addRow("Scale", self.scale_spin)
        self.shaft_spin = _spin(*STYLE_RANGES["shaft_radius"], 0.01, 3, " Å")
        self.shaft_spin.valueChanged.connect(
            lambda v: self._edit("Arrow Shaft", "vec:shaft", shaft_radius=v)
        )
        form.addRow("Shaft radius", self.shaft_spin)
        self.head_length_spin = _spin(*STYLE_RANGES["head_length"], 0.05, 2, " Å")
        self.head_length_spin.setToolTip(
            "Head length; on short arrows the head takes at most 60 % of the length and the "
            "arrow gets thinner in proportion"
        )
        self.head_length_spin.valueChanged.connect(
            lambda v: self._edit("Arrow Head", "vec:head_length", head_length=v)
        )
        form.addRow("Head length", self.head_length_spin)
        self.head_radius_spin = _spin(*STYLE_RANGES["head_radius"], 0.01, 3, " Å")
        self.head_radius_spin.valueChanged.connect(
            lambda v: self._edit("Arrow Head", "vec:head_radius", head_radius=v)
        )
        form.addRow("Head radius", self.head_radius_spin)
        self.color_button = ColorButton("Arrow colour")
        self.color_button.color_chosen.connect(lambda c: self._edit("Arrow Colour", color=c))
        form.addRow("Colour", self.color_button)
        self.material_combo = QComboBox()
        self.material_combo.setToolTip(
            "Material of the arrows (built-in or one of your materials); materials with their "
            "own colours ignore the arrow colour"
        )
        self.material_combo.currentIndexChanged.connect(
            lambda _i: self._edit("Arrow Material", material=self.material_combo.currentData())
        )
        form.addRow("Material", self.material_combo)
        layout.addWidget(group)
        note = QLabel(NOTE)
        note.setWordWrap(True)
        layout.addWidget(note)
        self._fill_materials()

    # ----- public ---------------------------------------------------------------------
    def sync(
        self,
        structure: Structure,
        vectors: VectorSet,
        style: VectorStyle,
        shown: dict[Key, int],
        selection_count: int,
    ) -> None:
        """Show the current vectors and appearance without emitting requests.

        Parameters
        ----------
        structure
            Structure (for atom labels).
        vectors, style
            Current vectors and arrow appearance.
        shown
            Number of displayed host atoms of each row.
        selection_count
            Number of atoms selected in the 3D view.
        """
        self._syncing = True
        try:
            chosen = set(self.selected_keys())
            self._keys = vectors.keys()
            self._visible = {}
            self.table.setRowCount(len(self._keys))
            for row, key in enumerate(self._keys):
                kind, target = key
                record = vectors.record(key)
                self._visible[key] = None if record is None else record.visible
                source = target if kind == "source" else target[0]
                image = "all images" if kind == "source" else _image_text(target[1])
                if kind == "source":
                    scope = "All images"
                elif record is None:
                    scope = "Suppressed here"
                else:
                    scope = "This image"
                cells = [scope, atom_text(structure, (source, (0, 0, 0))).split(" [")[0], image]
                if record is None:
                    cells += ["—", "—", "—", "no arrow"]
                else:
                    unit = f" {record.unit_text}" if record.unit_text else ""
                    cells += [
                        ", ".join(f"{c:.4f}" for c in record.components),
                        record.meaning_name,
                        f"{record.modulus:.4f}{unit}",
                        _shown_text(record, shown.get(key, 0)),
                    ]
                for column, text in enumerate(cells):
                    item = QTableWidgetItem(text)
                    if record is not None:
                        item.setToolTip(f"Exact components: {record.components!r}")
                    self.table.setItem(row, column, item)
            self._select_rows([r for r, key in enumerate(self._keys) if key in chosen])
            n_sources, n_images = len(vectors.sources), len(vectors.images)
            self.summary_label.setText(
                f"{n_sources} source default{'s' if n_sources != 1 else ''}, {n_images} image "
                f"override{'s' if n_images != 1 else ''}. Image overrides (and suppressions) "
                "take precedence over the default of their source atom."
                if len(vectors)
                else "No vectors yet. Select atoms in the 3D view and press Add/Set for Selection…"
            )
            self.add_button.setEnabled(selection_count > 0)
            self.suppress_button.setEnabled(selection_count > 0)
            self._style = style
            self._fill_materials()
            self.show_check.setChecked(style.visible)
            self.placement_combo.setCurrentIndex(self.placement_combo.findData(style.placement))
            self.mode_combo.setCurrentIndex(self.mode_combo.findData(style.length_mode))
            self.length_spin.setValue(style.length)
            self.scale_spin.setValue(style.scale)
            self.length_spin.setEnabled(style.length_mode == "uniform")
            self.scale_spin.setEnabled(style.length_mode == "proportional")
            self.shaft_spin.setValue(style.shaft_radius)
            self.head_length_spin.setValue(style.head_length)
            self.head_radius_spin.setValue(style.head_radius)
            self.color_button.set_color(style.color)
            self.material_combo.setCurrentIndex(
                max(self.material_combo.findData(style.material), 0)
            )
        finally:
            self._syncing = False
        self._update_buttons()

    def selected_keys(self) -> list[Key]:
        """Return the keys of the chosen table rows."""
        rows = sorted({index.row() for index in self.table.selectionModel().selectedRows()})
        return [self._keys[r] for r in rows if r < len(self._keys)]

    def select_keys(self, keys: list[Key]) -> None:
        """Choose table rows by key (as the user would: one selection change)."""
        syncing, self._syncing = self._syncing, True
        try:
            self._select_rows([r for r, key in enumerate(self._keys) if key in keys])
        finally:
            self._syncing = syncing
        self._on_selection()

    def _select_rows(self, rows: list[int]) -> None:
        from PySide6.QtCore import QItemSelection, QItemSelectionModel

        selection = QItemSelection()
        model = self.table.model()
        last = model.columnCount() - 1
        for row in rows:
            selection.select(model.index(row, 0), model.index(row, last))
        self.table.selectionModel().select(
            selection, QItemSelectionModel.SelectionFlag.ClearAndSelect
        )

    # ----- internals ------------------------------------------------------------------
    def _fill_materials(self) -> None:
        wanted = [m.id for m in materials() + custom_materials()]
        current = [self.material_combo.itemData(i) for i in range(self.material_combo.count())]
        if wanted == current:
            return
        self.material_combo.blockSignals(True)
        self.material_combo.clear()
        for material in materials() + custom_materials():
            name = f"{material.name} ✎" if material.custom else material.name
            self.material_combo.addItem(preset_icon(material), name, material.id)
        self.material_combo.blockSignals(False)

    def _edit(self, text: str, merge_key: str = "", **changes: object) -> None:
        if self._syncing:
            return
        new = replace(self._style, **changes)
        if new != self._style:
            self.style_requested.emit(new, text, merge_key)

    def _on_selection(self) -> None:
        self._update_buttons()
        if not self._syncing:
            self.rows_selected.emit(self.selected_keys())

    def _toggle_visible(self) -> None:
        keys = [k for k in self.selected_keys() if self._visible.get(k) is not None]
        if keys:  # any shown: hide all; all hidden: show all
            self.visibility_requested.emit(keys, not any(self._visible[k] for k in keys))

    def _update_buttons(self) -> None:
        keys = self.selected_keys()
        records = [k for k in keys if self._visible.get(k) is not None]
        self.edit_button.setEnabled(bool(records))
        self.reverse_button.setEnabled(bool(records))
        self.visible_button.setEnabled(bool(records))
        self.remove_button.setEnabled(bool(keys))


def _image_text(image: tuple[int, int, int]) -> str:
    return "[" + " ".join(str(int(n)) for n in image) + "]"


def _shown_text(record: VectorRecord, shown: int) -> str:
    if not record.visible:
        return "hidden"
    if record.is_zero:
        return "zero (no arrow)"
    if shown == 0:
        return "not displayed"
    return f"{shown} shown"


class VectorEditDialog(QDialog):
    """Enter one vector for frozen targets; *Apply* is one undoable step.

    Parameters
    ----------
    title
        Window title.
    record
        Initial values.
    scopes
        ``(label, scope)`` choices: ``"images"`` (the selected displayed atoms) and/or
        ``"sources"`` (all periodic images of their source atoms). With one choice the
        scope is fixed.
    overrides
        Number of image overrides that would keep a new source default from showing;
        when positive, a checkbox offers to clear them.
    parent
        Main window.
    """

    preview_requested = Signal(object)
    """Show the edit without an undo step: a ``(record, scope, clear_overrides)`` tuple."""

    applied = Signal(object)
    """Apply the edit: a ``(record, scope, clear_overrides)`` tuple."""

    cancelled = Signal()
    """Editing ended without applying."""

    def __init__(
        self,
        title: str,
        record: VectorRecord,
        scopes: list[tuple[str, str]],
        overrides: int = 0,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setWindowModality(Qt.WindowModality.WindowModal)
        self._finished = False
        layout = QVBoxLayout(self)
        self.scope_group = QButtonGroup(self)
        self.scope_buttons: dict[str, QRadioButton] = {}
        box = QGroupBox("Attach to")
        box_layout = QVBoxLayout(box)
        for label, scope in scopes:
            button = QRadioButton(label)
            self.scope_group.addButton(button)
            self.scope_buttons[scope] = button
            box_layout.addWidget(button)
        self.scope_buttons[scopes[0][1]].setChecked(True)
        box.setEnabled(len(scopes) > 1)
        layout.addWidget(box)
        form = QFormLayout()
        self.meaning_combo = QComboBox()
        for meaning, (name, unit) in MEANINGS.items():
            self.meaning_combo.addItem(
                f"{name} ({unit})" if unit else f"{name} (dimensionless)", meaning
            )
        self.meaning_combo.setToolTip(
            "Magnetic moment: components in Bohr magnetons. Direction: a dimensionless "
            "illustration, never shown as a computed or measured moment."
        )
        form.addRow("Meaning", self.meaning_combo)
        self.component_spins = []
        for axis in "xyz":
            spin = _spin(-1000.0, 1000.0, 0.1, 4)
            spin.setAccessibleName(f"{axis} component")
            spin.setToolTip(f"Cartesian {axis} component in the structure frame")
            form.addRow(f"{axis}", spin)
            self.component_spins.append(spin)
        self.modulus_label = QLabel()
        form.addRow("Modulus", self.modulus_label)
        layout.addLayout(form)
        self.clear_check = QCheckBox(
            f"Also remove {overrides} image override{'s' if overrides != 1 else ''} of these "
            "atoms (they take precedence over the default)"
        )
        self.clear_check.setVisible(overrides > 0)
        self.clear_check.toggled.connect(lambda _on: self._changed())
        layout.addWidget(self.clear_check)
        self.note_label = QLabel()
        self.note_label.setWordWrap(True)
        layout.addWidget(self.note_label)
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        self.apply_button = QPushButton("Apply")
        self.cancel_button = QPushButton("Cancel")
        buttons.addWidget(self.cancel_button)
        buttons.addWidget(self.apply_button)
        layout.addLayout(buttons)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(PREVIEW_DELAY_MS)
        self._timer.timeout.connect(lambda: self.preview_requested.emit(self.edit()))
        self.meaning_combo.setCurrentIndex(self.meaning_combo.findData(record.meaning))
        for spin, value in zip(self.component_spins, record.components, strict=True):
            spin.setValue(value)
        for spin in self.component_spins:
            spin.valueChanged.connect(lambda _v: self._changed())
        for button in self.scope_buttons.values():
            button.toggled.connect(lambda _on: self._changed())
        self.meaning_combo.currentIndexChanged.connect(lambda _i: self._changed())
        self.apply_button.clicked.connect(self.apply)
        self.cancel_button.clicked.connect(self.reject)
        self._update_labels()

    def record(self) -> VectorRecord:
        """Return the entered record."""
        return VectorRecord(
            tuple(spin.value() for spin in self.component_spins),
            self.meaning_combo.currentData(),
        )

    def scope(self) -> str:
        """Return the chosen scope (``"images"`` or ``"sources"``)."""
        return next(s for s, b in self.scope_buttons.items() if b.isChecked())

    def edit(self) -> tuple[VectorRecord, str, bool]:
        """Return ``(record, scope, clear_overrides)``."""
        return self.record(), self.scope(), self.clear_check.isChecked()

    def set_components(self, x: float, y: float, z: float) -> None:
        """Enter components as the user would."""
        for spin, value in zip(self.component_spins, (x, y, z), strict=True):
            spin.setValue(value)

    def apply(self) -> None:
        """Apply (one undoable step) and close."""
        self._timer.stop()
        self._finished = True
        self.applied.emit(self.edit())
        self.accept()

    def reject(self) -> None:  # noqa: D102 - Qt override
        self._timer.stop()
        if not self._finished:
            self._finished = True
            self.cancelled.emit()
        super().reject()

    def closeEvent(self, event) -> None:  # noqa: N802, ANN001, D102 - Qt override
        self._timer.stop()
        if not self._finished:
            self._finished = True
            self.cancelled.emit()
        super().closeEvent(event)

    def _changed(self) -> None:
        self._update_labels()
        self._timer.start()

    def _update_labels(self) -> None:
        record = self.record()
        unit = f" {record.unit_text}" if record.unit_text else ""
        self.modulus_label.setText(f"{record.modulus:.4f}{unit}")
        self.note_label.setText(
            "Zero vector: stored with zero modulus; no arrow is drawn."
            if record.is_zero
            else "The arrow points along the components; its drawn length is set in the "
            "Vectors window (uniform or proportional)."
        )
