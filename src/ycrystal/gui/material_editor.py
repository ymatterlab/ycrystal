"""*Customize Material…*: edit the parameters of a material recipe (FR-MATERIAL-01).

The dialog edits a [`MaterialDefinition`][ycrystal.presets.custom.MaterialDefinition]
and only emits requests: while editing it asks the main window to preview the variant
(debounced, without an undo step); *Apply* asks it to assign the variant as one undoable
step; *Cancel* restores the previous display. *Save as My Material* keeps the variant in
the user's settings (see
[`save_personal_material`][ycrystal.gui.material_editor.save_personal_material]).

Personal materials are stored as JSON in ``QSettings`` under
[`PERSONAL_MATERIALS_KEY`][ycrystal.gui.material_editor.PERSONAL_MATERIALS_KEY], never in
the installed package; projects and styles embed the definitions they use, so they do
not depend on this list.
"""

from __future__ import annotations

import json

from PySide6.QtCore import QSettings, Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ycrystal.presets import (
    custom_materials,
    get_definition,
    get_material,
    materials,
    register_definition,
)
from ycrystal.presets.custom import (
    DefinitionError,
    MaterialDefinition,
    base_definition,
    editable,
    schema_for,
)

PERSONAL_MATERIALS_KEY = "materials/personal"
"""``QSettings`` key of the personal custom materials (a JSON list of definitions)."""

PREVIEW_DELAY_MS = 150
"""Pause after the last parameter change before the view shows it."""


def load_personal_materials(settings: QSettings) -> tuple[list[MaterialDefinition], list[str]]:
    """Register the personal materials stored in ``settings``.

    Returns
    -------
    tuple
        The definitions, and one message per entry that could not be used (it is kept
        in the settings, unchanged).
    """
    text = settings.value(PERSONAL_MATERIALS_KEY, "[]")
    try:
        entries = json.loads(str(text))
    except json.JSONDecodeError:
        return [], ["The list of your materials in the settings is damaged."]
    definitions, problems = [], []
    for entry in entries if isinstance(entries, list) else []:
        try:
            definition = MaterialDefinition.from_dict(entry)
        except DefinitionError as exc:
            problems.append(str(exc))
            continue
        register_definition(definition)
        definitions.append(definition)
    return definitions, problems


def save_personal_material(settings: QSettings, definition: MaterialDefinition) -> bool:
    """Add a definition to the personal materials; return False if it was already there."""
    text = settings.value(PERSONAL_MATERIALS_KEY, "[]")
    try:
        entries = json.loads(str(text))
    except json.JSONDecodeError:
        entries = []
    entries = entries if isinstance(entries, list) else []
    if any(isinstance(e, dict) and e.get("id") == definition.id for e in entries):
        return False
    entries.append(definition.to_dict())
    settings.setValue(PERSONAL_MATERIALS_KEY, json.dumps(entries, ensure_ascii=False))
    register_definition(definition)
    return True


class MaterialEditorDialog(QDialog):
    """Edit the parameters of a material recipe and apply or save the variant.

    Parameters
    ----------
    targets
        ``(label, target)`` pairs: ``"default"``, ``"element:<symbol>"``, or
        ``"selection"`` (the atoms selected when the dialog opened).
    current
        Material id currently assigned to each target.
    target
        Initially chosen target.
    parent
        Main window.
    """

    preview_requested = Signal(str, str)
    """Show a variant without an undo step: ``(target, material id)``."""

    applied = Signal(str, str)
    """Assign a variant as one undoable step: ``(target, material id)``."""

    cancelled = Signal()
    """Editing ended without applying: restore the display."""

    saved = Signal(object)
    """A definition was saved as a personal material."""

    def __init__(
        self,
        targets: list[tuple[str, str]],
        current: dict[str, str],
        target: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Customize Material")
        self.setWindowModality(Qt.WindowModality.WindowModal)
        self._current = dict(current)
        self._spins: dict[str, QDoubleSpinBox] = {}
        self._syncing = False
        self._finished = False
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.target_combo = QComboBox()
        for label, key in targets:
            self.target_combo.addItem(label, key)
        self.target_combo.setToolTip(
            "Where the variant is applied. A selection is the one at the time the dialog "
            "opened; selecting other atoms does not change it."
        )
        form.addRow("Apply to", self.target_combo)
        self.base_combo = QComboBox()
        for material in materials():
            label = material.name if editable(material.id) else f"{material.name} (not editable)"
            self.base_combo.addItem(label, material.id)
        for material in custom_materials():
            self.base_combo.addItem(f"{material.name} ✎", material.id)
        self.base_combo.setToolTip("The material whose recipe the variant starts from")
        form.addRow("Start from", self.base_combo)
        self.name_edit = QLineEdit()
        self.name_edit.setMaxLength(80)
        self.name_edit.setToolTip("Name of the variant in menus, the gallery, and exported scenes")
        form.addRow("Name", self.name_edit)
        layout.addLayout(form)
        self.parameter_group = QGroupBox("Parameters")
        self.parameter_form = QFormLayout(self.parameter_group)
        layout.addWidget(self.parameter_group)
        self.note_label = QLabel()
        self.note_label.setWordWrap(True)
        layout.addWidget(self.note_label)
        buttons = QDialogButtonBox()
        self.reset_button = QPushButton("Reset to Base")
        self.reset_button.setToolTip("Use the values of the material the variant starts from")
        self.save_button = QPushButton("Save as My Material")
        self.save_button.setToolTip(
            "Keep this variant in your materials (gallery category My materials)"
        )
        self.apply_button = QPushButton("Apply")
        self.cancel_button = QPushButton("Cancel")
        for button, role in (
            (self.reset_button, QDialogButtonBox.ButtonRole.ResetRole),
            (self.save_button, QDialogButtonBox.ButtonRole.ActionRole),
            (self.apply_button, QDialogButtonBox.ButtonRole.AcceptRole),
            (self.cancel_button, QDialogButtonBox.ButtonRole.RejectRole),
        ):
            buttons.addButton(button, role)
        layout.addWidget(buttons)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(PREVIEW_DELAY_MS)
        self._timer.timeout.connect(self._emit_preview)
        self.reset_button.clicked.connect(self.reset_to_base)
        self.save_button.clicked.connect(self.save_personal)
        self.apply_button.clicked.connect(self.apply)
        self.cancel_button.clicked.connect(self.reject)
        self.base_combo.currentIndexChanged.connect(lambda _i: self._load_start())
        self.target_combo.currentIndexChanged.connect(lambda _i: self._schedule())
        self.name_edit.textEdited.connect(lambda _t: self._update_buttons())
        index = max(self.target_combo.findData(target), 0)
        self.target_combo.setCurrentIndex(index)
        start = self._current.get(self.target(), "satin")
        self._syncing = True
        self.base_combo.setCurrentIndex(max(self.base_combo.findData(start), 0))
        self._syncing = False
        self._load_start(preview=False)

    # ----- state ----------------------------------------------------------------------
    def target(self) -> str:
        """Return the chosen target."""
        return self.target_combo.currentData()

    def base(self) -> str:
        """Return the built-in material the variant is based on."""
        chosen = self.base_combo.currentData()
        material = get_material(chosen)
        return material.base if material.custom else chosen

    def definition(self) -> MaterialDefinition | None:
        """Return the edited variant, or ``None`` if the start material is not editable.

        Raises
        ------
        DefinitionError
            If the name is empty (values are kept within range by the spin boxes).
        """
        if not editable(self.base()):
            return None
        values = {key: spin.value() for key, spin in self._spins.items()}
        start = self._start_definition()
        return start.with_values(**values).renamed(self.name_edit.text())

    def set_value(self, key: str, value: float) -> None:
        """Set one parameter as the user would (for scripts and tests)."""
        self._spins[key].setValue(value)

    def value(self, key: str) -> float:
        """Return one parameter value shown in the dialog."""
        return self._spins[key].value()

    # ----- actions --------------------------------------------------------------------
    def reset_to_base(self) -> None:
        """Show the base recipe's values (the name stays)."""
        if not editable(self.base()):
            return
        defaults = dict(schema_for(self.base()).defaults)
        self._syncing = True
        for key, spin in self._spins.items():
            spin.setValue(defaults[key])
        self._syncing = False
        self._schedule()

    def apply(self) -> None:
        """Assign the variant to the target (one undoable step) and close."""
        definition = self._valid_definition()
        if definition is None:
            return
        register_definition(definition)
        self._timer.stop()
        self._finished = True
        self.applied.emit(self.target(), definition.id)
        self.accept()

    def save_personal(self) -> None:
        """Save the variant as a personal material (the dialog stays open)."""
        definition = self._valid_definition()
        if definition is not None:
            self.saved.emit(definition)
            self.note_label.setText(f"Saved “{definition.name}” in My materials.")

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

    # ----- internals ------------------------------------------------------------------
    def _start_definition(self) -> MaterialDefinition:
        chosen = self.base_combo.currentData()
        if get_material(chosen).custom:
            return get_definition(chosen)
        return base_definition(chosen)

    def _valid_definition(self) -> MaterialDefinition | None:
        try:
            definition = self.definition()
        except DefinitionError as exc:
            self.note_label.setText(str(exc))
            return None
        if definition is None:
            self.note_label.setText(self._explanation())
        return definition

    def _explanation(self) -> str:
        try:
            schema_for(self.base())
        except DefinitionError as exc:
            return str(exc) + " Choose a Ycrystal recipe such as Satin, Glass, or Marble."
        return ""

    def _load_start(self, preview: bool = True) -> None:
        """Rebuild the parameter controls for the chosen start material."""
        while self.parameter_form.rowCount():
            self.parameter_form.removeRow(0)
        self._spins = {}
        base = self.base()
        if not editable(base):
            self.name_edit.setText("")
            self.note_label.setText(self._explanation())
            self.parameter_group.setEnabled(False)
            self._update_buttons()
            if preview and not self._syncing:
                self._schedule()
            return
        start = self._start_definition()
        self.parameter_group.setEnabled(True)
        self.name_edit.setText(start.name)
        schema = schema_for(base)
        values = dict(start.values)
        for parameter in schema.visible():
            spin = QDoubleSpinBox()
            spin.setRange(parameter.minimum, parameter.maximum)
            spin.setDecimals(parameter.decimals)
            spin.setSingleStep(parameter.step)
            spin.setKeyboardTracking(False)
            spin.setValue(values[parameter.key])
            spin.setToolTip(parameter.help)
            spin.setAccessibleName(parameter.label)
            spin.valueChanged.connect(lambda _v: self._schedule())
            self.parameter_form.addRow(parameter.label, spin)
            self._spins[parameter.key] = spin
        material = get_material(base)
        notes = [material.description]
        if schema.family == "glass":
            notes.append(
                "The glass filter amount says how much light passes through, tinted by the "
                "atom colour; it is not a generic opacity or a measured optical constant."
            )
        if schema.family == "pattern":
            notes.append("Only the pattern scale of this texture can be changed.")
        notes.append(
            "The 3D view approximates the highlight and transparency; the POV-Ray preview "
            "(F5) shows the real material."
        )
        self.note_label.setText(" ".join(notes))
        self._update_buttons()
        if preview and not self._syncing:
            self._schedule()

    def _update_buttons(self) -> None:
        ok = editable(self.base())
        named = bool(self.name_edit.text().strip())
        self.apply_button.setEnabled(ok and named)
        self.save_button.setEnabled(ok and named)
        self.reset_button.setEnabled(ok)

    def _schedule(self) -> None:
        if not self._syncing:
            self._timer.start()

    def _emit_preview(self) -> None:
        try:
            definition = self.definition()
        except DefinitionError:
            return
        if definition is None:
            material_id = self._current.get(self.target(), "satin")
        else:
            material_id = register_definition(definition, listed=False).id
        self.preview_requested.emit(self.target(), material_id)
