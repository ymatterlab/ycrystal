"""Output and preview panels.

Like the scene panel, these widgets only emit requests; the main window applies them
and calls their ``sync`` methods with signals blocked.
"""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, QSignalBlocker, QSize, Qt, Signal
from PySide6.QtGui import QAction, QColor, QIcon, QPainter, QPalette, QPen, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGridLayout,
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

from ycrystal.core import aspect

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

MAX_OUTPUT_PIXELS = aspect.MAX_OUTPUT_PIXELS
"""Largest width or height offered for rendered images, in pixels."""


def padlock_icon(locked: bool, color: QColor, size: int = 20) -> QIcon:
    """Draw a padlock: closed shackle when ``locked``, raised and open otherwise.

    The two states differ in shape (open or closed shackle), not only in colour.
    """
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    unit = size / 20.0
    pen = QPen(color, 2.0 * unit)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    body = QRectF(4 * unit, 9 * unit, 12 * unit, 9 * unit)
    if locked:  # shackle closed onto both sides of the body
        painter.drawArc(QRectF(6 * unit, 2 * unit, 8 * unit, 10 * unit), 0, 180 * 16)
        painter.drawLine(QPointF(6 * unit, 7 * unit), QPointF(6 * unit, 9 * unit))
        painter.drawLine(QPointF(14 * unit, 7 * unit), QPointF(14 * unit, 9 * unit))
    else:  # shackle raised, swung open: free on the right
        painter.drawArc(QRectF(9 * unit, 0.5 * unit, 8 * unit, 8 * unit), 0, 180 * 16)
        painter.drawLine(QPointF(17 * unit, 4.5 * unit), QPointF(17 * unit, 6.5 * unit))
        painter.drawLine(QPointF(9 * unit, 4.5 * unit), QPointF(9 * unit, 9 * unit))
    painter.setBrush(color)
    painter.drawRoundedRect(body, 1.5 * unit, 1.5 * unit)
    painter.end()
    return QIcon(pixmap)


def preset_index(width: int, height: int) -> int:
    """Return the index of the preset that ``width × height`` matches, else 0 (Custom).

    Matching allows the rounding of one dimension (see
    [`matches_ratio`][ycrystal.core.aspect.matches_ratio]).
    """
    for index, (_label, ratio) in enumerate(ASPECT_PRESETS):
        if ratio and aspect.matches_ratio((width, height), ratio):
            return index
    return 0


class RenderPanel(QWidget):
    """Output size and the render actions.

    Width and height are exact pixel counts. The lock button beside them keeps a target
    ratio: while locked, editing one dimension computes the other (see
    [`ycrystal.core.aspect`][ycrystal.core.aspect]); while unlocked they are
    independent. The aspect-ratio menu keeps the width and computes the height. The
    frame in the 3D view always shows the rendered area.

    The panel only requests changes; the window applies them and calls
    [`sync`][ycrystal.gui.panels.output_panel.RenderPanel.sync]. Each edit, preset, or
    Swap emits a single complete request.
    """

    output_requested = Signal(int, int, float)
    """New ``(width, height, target ratio)`` from one user edit, preset, or Swap."""

    lock_requested = Signal(bool)
    """The lock button was toggled: ``True`` locks the ratio of the current size."""

    limit_exceeded = Signal(str)
    """An edit was rejected because a dimension would leave 16–8000 px (message)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._size = (1200, 800)
        self._ratio = 1.5
        layout = QVBoxLayout(self)
        group = QGroupBox("Output image")
        form = QFormLayout(group)
        size_grid = QGridLayout()
        self.width_spin = QSpinBox()
        self.height_spin = QSpinBox()
        for row, (spin, name) in enumerate(
            ((self.width_spin, "Width"), (self.height_spin, "Height"))
        ):
            spin.setRange(aspect.MIN_OUTPUT_PIXELS, aspect.MAX_OUTPUT_PIXELS)
            spin.setSuffix(" px")
            spin.setKeyboardTracking(False)  # typed values apply on Enter / focus change
            spin.setAccessibleName(f"Output {name.lower()} in pixels")
            label = QLabel(f"{name}")
            label.setBuddy(spin)
            size_grid.addWidget(label, row, 0)
            size_grid.addWidget(spin, row, 1)
        self.width_spin.valueChanged.connect(lambda v: self._on_edited("width", v))
        self.height_spin.valueChanged.connect(lambda v: self._on_edited("height", v))
        self.lock_button = QToolButton()
        self.lock_button.setCheckable(True)
        self.lock_button.setChecked(True)
        self.lock_button.setAutoRaise(True)
        self.lock_button.setIconSize(QSize(20, 20))
        self.lock_button.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.lock_button.setAccessibleName("Lock aspect ratio")
        self.lock_button.toggled.connect(self._on_lock_toggled)
        size_grid.addWidget(self.lock_button, 0, 2, 2, 1, Qt.AlignmentFlag.AlignVCenter)
        size_grid.setColumnStretch(1, 1)
        form.addRow(size_grid)
        row = QHBoxLayout()
        self.aspect_combo = QComboBox()
        for label_text, ratio in ASPECT_PRESETS:
            self.aspect_combo.addItem(label_text, ratio)
        self.aspect_combo.activated.connect(self._apply_aspect)
        row.addWidget(self.aspect_combo, 1)
        self.swap_button = QPushButton("Swap")
        self.swap_button.setToolTip("Exchange width and height (portrait ↔ landscape)")
        self.swap_button.clicked.connect(self._swap)
        row.addWidget(self.swap_button)
        form.addRow("Aspect", row)
        self.limit_label = QLabel()
        self.limit_label.setWordWrap(True)
        self.limit_label.setVisible(False)
        form.addRow(self.limit_label)
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
        self._update_lock_look()

    def add_actions(self, first: list[QAction], second: list[QAction]) -> None:
        """Show buttons for window actions (they share enabled state and text)."""
        for row, actions in ((self._button_row, first), (self._second_row, second)):
            for action in actions:
                button = QToolButton()
                button.setDefaultAction(action)
                button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
                button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
                row.addWidget(button)

    # ----- state ------------------------------------------------------------------------
    def is_locked(self) -> bool:
        """Return whether the aspect ratio is locked."""
        return self.lock_button.isChecked()

    def target_ratio(self) -> float:
        """Return the target ratio ``width / height`` kept while locked."""
        return self._ratio

    def sync(
        self, width: int, height: int, locked: bool | None = None, ratio: float | None = None
    ) -> None:
        """Show the output size (and lock state and target ratio) without emitting."""
        self._size = (int(width), int(height))
        if ratio is not None:
            self._ratio = float(ratio)
        with QSignalBlocker(self.width_spin), QSignalBlocker(self.height_spin):
            self.width_spin.setValue(self._size[0])
            self.height_spin.setValue(self._size[1])
        if locked is not None:
            with QSignalBlocker(self.lock_button):
                self.lock_button.setChecked(bool(locked))
        with QSignalBlocker(self.aspect_combo):
            self.aspect_combo.setCurrentIndex(preset_index(*self._size))
        self._update_lock_look()

    def show_limit(self, message: str) -> None:
        """Show (or clear, with an empty message) the explanation of a rejected edit."""
        self.limit_label.setText(f"⚠ {message}" if message else "")
        self.limit_label.setVisible(bool(message))

    # ----- edits ------------------------------------------------------------------------
    def _restore(self) -> None:
        self.sync(*self._size)

    def _request(self, size: tuple[int, int], ratio: float) -> None:
        self.show_limit("")
        if size != self._size or abs(ratio - self._ratio) > 1e-15:
            self.output_requested.emit(size[0], size[1], ratio)

    def _reject(self, error: aspect.OutputSizeError) -> None:
        self._restore()
        self.show_limit(str(error))
        self.limit_exceeded.emit(str(error))

    def _on_edited(self, edited: str, value: int) -> None:
        try:
            size = aspect.linked_size(edited, value, self._size, self._ratio, self.is_locked())
        except aspect.OutputSizeError as error:
            self._reject(error)
            return
        self._request(size, self._ratio)

    def _apply_aspect(self, index: int) -> None:
        ratio = self.aspect_combo.itemData(index)
        if not ratio:
            self._restore()  # "Custom" is a state, not an action
            return
        try:
            size = aspect.preset_size(self._size[0], ratio)
        except aspect.OutputSizeError as error:
            self._reject(error)
            return
        # Locked: the preset becomes the target ratio. Unlocked: applied once.
        self._request(size, ratio if self.is_locked() else self._ratio)

    def _swap(self) -> None:
        size, inverted = aspect.swapped(self._size, self._ratio)
        self._request(size, inverted if self.is_locked() else self._ratio)

    def _on_lock_toggled(self, locked: bool) -> None:
        self._update_lock_look()
        self.lock_requested.emit(locked)

    def _update_lock_look(self) -> None:
        color = self.palette().color(QPalette.ColorRole.ButtonText)
        locked = self.is_locked()
        self.lock_button.setIcon(padlock_icon(locked, color))
        self.lock_button.setText("Locked" if locked else "Unlocked")
        if locked:
            tip = (
                f"Aspect ratio locked at {self._ratio:.4g} : 1 — editing Width or Height "
                "changes the other. Click (or Space) to unlock."
            )
        else:
            tip = (
                "Aspect ratio unlocked — Width and Height change independently. Click (or "
                "Space) to lock the current ratio."
            )
        self.lock_button.setToolTip(tip)
        self.lock_button.setAccessibleDescription(tip)


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
