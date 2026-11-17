"""The *File ▸ Import Style…* dialog: style parts and the optional element mapping.

The dialog only collects a choice; the main window applies it with
[`apply_style`][ycrystal.io.style.apply_style] as one undoable step. The element
mapping (FR-STYLE-MAP-01) sends the style's settings for one element to another element
of the open structure, or leaves them out. Every row starts at the transfer by matching
symbols, so pressing *Apply* without changing a row behaves as before. What will be
applied and left out is shown before *Apply*, from
[`resolve_element_map`][ycrystal.io.style.resolve_element_map]; an ambiguous mapping
disables *Apply* and says why.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QGridLayout,
    QGroupBox,
    QLabel,
    QLayout,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ycrystal.core.structure import Structure
from ycrystal.io.style import (
    LEAVE_OUT_LABEL,
    STYLE_PARTS,
    ElementMapError,
    Style,
    resolve_element_map,
    style_elements,
)

STYLE_PART_LABELS = {
    "appearance": "Materials, colours, and radii",
    "display": "Display: atom size, repetitions, boundary atoms, cell edges, bonds",
    "environment": "Environment: background, floor, lighting, cell-edge colour",
    "output": "Output image size",
}
"""Labels of the style parts in the import dialog."""

LEAVE_OUT = LEAVE_OUT_LABEL
"""Mapping choice that leaves an element's settings out."""


@dataclass(frozen=True)
class StyleImportChoice:
    """What the user chose in the import dialog.

    Attributes
    ----------
    parts
        Parts to apply, in the order of [`STYLE_PARTS`][ycrystal.io.style.STYLE_PARTS].
    element_map
        ``{source element: target element or None}`` for the rows that differ from the
        transfer by matching symbols; empty if no row was changed.
    """

    parts: tuple[str, ...]
    element_map: dict[str, str | None] = field(default_factory=dict)


class StyleImportDialog(QDialog):
    """Choose the parts of a style and, optionally, map its elements to others.

    Parameters
    ----------
    style
        The loaded style.
    structure
        The open structure (read only).
    parent
        Parent widget.
    """

    def __init__(self, style: Style, structure: Structure, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("Import Style")
        self._style = style
        self._structure = structure
        self._present = sorted(set(structure.symbols))
        layout = QVBoxLayout(self)
        # Grow with the summary text instead of squeezing the wrapped labels.
        layout.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)
        compatible = style.is_compatible(structure)
        info = QLabel(
            f"Style from {style.source_name} ({len(style.source_symbols)} atoms). "
            + (
                "Same atoms as this structure: per-atom settings are applied too."
                if compatible
                else "Per-atom materials and hidden atoms refer to that structure and are "
                "not applied here."
            )
        )
        info.setWordWrap(True)
        layout.addWidget(info)
        self._boxes: dict[str, QCheckBox] = {}
        for part in STYLE_PARTS:
            box = QCheckBox(STYLE_PART_LABELS[part])
            box.setChecked(True)
            box.toggled.connect(self._update)
            self._boxes[part] = box
            layout.addWidget(box)

        self._combos: dict[str, QComboBox] = {}
        elements = style_elements(style)
        self.mapping_group = QGroupBox("Element settings go to")
        grid = QGridLayout(self.mapping_group)
        explanation = QLabel(
            "Change a row to give one element's settings (material, colour, radius, bond "
            "rules) to another element of this structure. This is a presentation choice; "
            "it says nothing about chemistry, and atoms and coordinates are not changed."
        )
        explanation.setWordWrap(True)
        grid.addWidget(explanation, 0, 0, 1, 2)
        for row, element in enumerate(elements, start=1):
            combo = QComboBox()
            for target in self._present:
                combo.addItem(target, target)
            combo.addItem(LEAVE_OUT, None)
            combo.setCurrentIndex(combo.findData(self._default(element)))
            combo.setAccessibleName(f"Element that receives the style's settings for {element}")
            combo.setToolTip(f"Element of this structure that gets the style's {element} settings")
            combo.currentIndexChanged.connect(self._update)
            label = QLabel(f"{element} →")
            label.setBuddy(combo)
            grid.addWidget(label, row, 0)
            grid.addWidget(combo, row, 1)
            self._combos[element] = combo
        self.reset_button = QPushButton("Match Symbols")
        self.reset_button.setToolTip("Give every element's settings to the same element again")
        self.reset_button.clicked.connect(self.reset_mapping)
        grid.addWidget(self.reset_button, len(elements) + 1, 1)
        self.mapping_group.setVisible(bool(elements))
        layout.addWidget(self.mapping_group)

        self.summary_label = QLabel()
        self.summary_label.setWordWrap(True)
        # Room for the longest message (an ambiguous mapping), so nothing is squeezed.
        self.summary_label.setMinimumHeight(5 * self.fontMetrics().lineSpacing())
        self.summary_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(self.summary_label)
        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.apply_button = self.buttons.button(QDialogButtonBox.StandardButton.Ok)
        self.apply_button.setText("Apply")
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)
        self._update()

    # ----- choice -----------------------------------------------------------------------
    def _default(self, element: str) -> str | None:
        return element if element in self._present else None

    def parts(self) -> tuple[str, ...]:
        """Return the checked parts."""
        return tuple(part for part, box in self._boxes.items() if box.isChecked())

    def element_map(self) -> dict[str, str | None]:
        """Return the rows that differ from the transfer by matching symbols."""
        mapping: dict[str, str | None] = {}
        for element, combo in self._combos.items():
            target = combo.currentData()
            if target != self._default(element):
                mapping[element] = target
        return mapping

    def mapping_combo(self, element: str) -> QComboBox:
        """Return the target selector of one element of the style."""
        return self._combos[element]

    def set_target(self, element: str, target: str | None) -> None:
        """Choose the element that receives `element`'s settings (``None``: leave out)."""
        combo = self._combos[element]
        combo.setCurrentIndex(combo.findData(target))

    def reset_mapping(self) -> None:
        """Return every row to the transfer by matching symbols."""
        for element in self._combos:
            self.set_target(element, self._default(element))

    def choice(self) -> StyleImportChoice | None:
        """Return the current choice, or ``None`` if the mapping is ambiguous."""
        try:
            resolve_element_map(self._style, self._structure, self.element_map(), self.parts())
        except ElementMapError:
            return None
        return StyleImportChoice(self.parts(), self.element_map())

    def summary(self) -> str:
        """Return the text shown above the buttons."""
        return self.summary_label.text()

    def _update(self, *_args: object) -> None:
        parts = self.parts()
        try:
            transfer = resolve_element_map(self._style, self._structure, self.element_map(), parts)
        except ElementMapError as exc:
            self.summary_label.setText(f"Cannot apply: {exc}")
            self.summary_label.setStyleSheet("color: #b00020;")
            self.apply_button.setEnabled(False)
            return
        lines = []
        if transfer.targets:
            lines.append(
                "Element settings applied: "
                + ", ".join(f"{s} → {t}" if s != t else s for s, t in transfer.targets)
                + "."
            )
        if transfer.left_out:
            lines.append("Left out: " + ", ".join(transfer.left_out) + ".")
        lines.extend(transfer.notes)
        self.summary_label.setText("\n".join(lines))
        self.summary_label.setStyleSheet("")
        self.apply_button.setEnabled(True)
