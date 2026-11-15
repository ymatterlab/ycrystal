"""Appearance, output, and preview panels.

Like the scene panel, these widgets only emit requests; the main window applies them
and calls their ``sync`` methods with signals blocked.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ycrystal.presets import environments, materials

#: Aspect-ratio presets offered for the output image: (label, width / height or None).
ASPECT_PRESETS: tuple[tuple[str, float | None], ...] = (
    ("Custom", None),
    ("1:1", 1.0),
    ("4:3", 4 / 3),
    ("3:2", 3 / 2),
    ("16:10", 16 / 10),
    ("16:9", 16 / 9),
    ("3:4 (portrait)", 3 / 4),
    ("2:3 (portrait)", 2 / 3),
)

MAX_OUTPUT_PIXELS = 8000
"""Largest width or height offered for rendered images, in pixels."""


class AppearancePanel(QWidget):
    """Material and background choices (the M3 alpha catalog)."""

    material_requested = Signal(str)
    background_requested = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.material_combo = QComboBox()
        for material in materials():
            self.material_combo.addItem(material.name, material.id)
            index = self.material_combo.count() - 1
            self.material_combo.setItemData(
                index, material.description, Qt.ItemDataRole.ToolTipRole
            )
        self.material_combo.currentIndexChanged.connect(
            lambda _i: self.material_requested.emit(self.material_combo.currentData())
        )
        form.addRow("Atoms and bonds", self.material_combo)
        self.material_note = QLabel()
        self.material_note.setWordWrap(True)
        form.addRow("", self.material_note)
        self.background_combo = QComboBox()
        for preset in environments():
            self.background_combo.addItem(preset.name, preset.id)
            index = self.background_combo.count() - 1
            self.background_combo.setItemData(
                index, preset.description, Qt.ItemDataRole.ToolTipRole
            )
        self.background_combo.currentIndexChanged.connect(
            lambda _i: self.background_requested.emit(self.background_combo.currentData())
        )
        form.addRow("Background", self.background_combo)
        self.background_note = QLabel()
        self.background_note.setWordWrap(True)
        form.addRow("", self.background_note)
        layout.addLayout(form)
        live = QLabel(
            "The 3D view approximates materials and lighting. Use Preview (F5) to see "
            "the POV-Ray result."
        )
        live.setWordWrap(True)
        layout.addWidget(live)
        layout.addStretch(1)

    def sync(self, material_id: str, environment_id: str) -> None:
        """Show the current material and background without emitting requests."""
        from ycrystal.presets import get_environment, get_material

        for combo, value in (
            (self.material_combo, material_id),
            (self.background_combo, environment_id),
        ):
            combo.blockSignals(True)
            combo.setCurrentIndex(combo.findData(value))
            combo.blockSignals(False)
        self.material_note.setText(get_material(material_id).description)
        self.background_note.setText(get_environment(environment_id).description)


class RenderPanel(QWidget):
    """Output size and the render actions.

    Width and height are exact pixel counts; the aspect-ratio menu sets the height
    from the width. The frame in the 3D view always shows the rendered area.
    """

    size_requested = Signal(int, int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        group = QGroupBox("Output image")
        form = QFormLayout(group)
        self.width_spin = QSpinBox()
        self.height_spin = QSpinBox()
        for spin, name in ((self.width_spin, "Width"), (self.height_spin, "Height")):
            spin.setRange(16, MAX_OUTPUT_PIXELS)
            spin.setSuffix(" px")
            spin.setKeyboardTracking(False)
            spin.valueChanged.connect(self._emit_size)
            form.addRow(name, spin)
        row = QHBoxLayout()
        self.aspect_combo = QComboBox()
        for label, ratio in ASPECT_PRESETS:
            self.aspect_combo.addItem(label, ratio)
        self.aspect_combo.activated.connect(self._apply_aspect)
        row.addWidget(self.aspect_combo, 1)
        self.swap_button = QPushButton("Swap")
        self.swap_button.setToolTip("Exchange width and height (portrait ↔ landscape)")
        self.swap_button.clicked.connect(
            lambda: self.size_requested.emit(self.height_spin.value(), self.width_spin.value())
        )
        row.addWidget(self.swap_button)
        form.addRow("Aspect", row)
        layout.addWidget(group)
        note = QLabel(
            "The blue frame in the 3D view shows exactly what the image contains. "
            "Preview renders a small POV-Ray image of the same view; Render writes the "
            "full-size PNG."
        )
        note.setWordWrap(True)
        layout.addWidget(note)
        self._button_row = QHBoxLayout()
        layout.addLayout(self._button_row)
        self._second_row = QHBoxLayout()
        layout.addLayout(self._second_row)
        layout.addStretch(1)

    def add_actions(self, first: list[QAction], second: list[QAction]) -> None:
        """Show buttons for window actions (they share enabled state and text)."""
        for row, actions in ((self._button_row, first), (self._second_row, second)):
            for action in actions:
                button = QToolButton()
                button.setDefaultAction(action)
                button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
                button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
                row.addWidget(button)

    def _emit_size(self, _value: int) -> None:
        self.size_requested.emit(self.width_spin.value(), self.height_spin.value())

    def _apply_aspect(self, index: int) -> None:
        ratio = self.aspect_combo.itemData(index)
        if ratio:
            width = self.width_spin.value()
            self.size_requested.emit(width, max(16, round(width / ratio)))

    def sync(self, width: int, height: int) -> None:
        """Show the output size without emitting requests."""
        for spin, value in ((self.width_spin, width), (self.height_spin, height)):
            spin.blockSignals(True)
            spin.setValue(value)
            spin.blockSignals(False)
        index = 0
        for i, (_label, ratio) in enumerate(ASPECT_PRESETS):
            if ratio and abs(width / height - ratio) < 0.5 / height * ratio + 1e-9:
                index = i
                break
        self.aspect_combo.blockSignals(True)
        self.aspect_combo.setCurrentIndex(index)
        self.aspect_combo.blockSignals(False)


class PreviewPanel(QWidget):
    """Shows the latest POV-Ray preview and its state."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        self.image_label = QLabel("No preview yet")
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setMinimumSize(160, 110)
        self.image_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
        layout.addWidget(self.image_label, 1)
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setVisible(False)
        layout.addWidget(self.progress)
        self.status_label = QLabel()
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)
        row = QHBoxLayout()
        self.auto_check = QCheckBox("Update automatically")
        self.auto_check.setToolTip(
            "Render a new preview shortly after each change to the view or the scene"
        )
        row.addWidget(self.auto_check, 1)
        self.preview_button = QToolButton()
        row.addWidget(self.preview_button)
        layout.addLayout(row)
        self._pixmap: QPixmap | None = None
        self.state = "empty"

    def set_action(self, action: QAction) -> None:
        """Use ``action`` for the panel's Preview button."""
        self.preview_button.setDefaultAction(action)

    def set_image(self, pixmap: QPixmap) -> None:
        """Show a new preview image (scaled to the panel)."""
        self._pixmap = pixmap
        self._rescale()

    def set_status(self, text: str, state: str) -> None:
        """Set the status line; ``state`` is one of empty, busy, ready, stale, error."""
        self.state = state
        self.status_label.setText(text)
        self.progress.setVisible(state == "busy")
        if state != "busy":
            self.progress.setRange(0, 0)

    def set_progress(self, percent: int) -> None:
        """Show render progress in percent."""
        self.progress.setRange(0, 100)
        self.progress.setValue(percent)

    def has_image(self) -> bool:
        """Return whether a preview image is shown."""
        return self._pixmap is not None

    def resizeEvent(self, event) -> None:  # noqa: N802, ANN001
        super().resizeEvent(event)
        self._rescale()

    def _rescale(self) -> None:
        if self._pixmap is None:
            return
        size = self.image_label.size()
        self.image_label.setPixmap(
            self._pixmap.scaled(
                size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )
