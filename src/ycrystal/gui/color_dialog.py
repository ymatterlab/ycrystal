"""Colour dialog with typed input in several notations and colour names on hover.

[`ColorDialog`][ycrystal.gui.color_dialog.ColorDialog] replaces Qt's colour dialog in
the Appearance tab. A colour can be chosen on a spectrum or from the CSS named colours,
or typed as hex, RGB 0–255, RGB 0–1, HSV, HSL, or a name; all fields stay in sync.
Wherever the mouse rests (spectrum or named colour), the dialog writes the colour's
plain name and nearest named colour, so that colours can be told apart without relying
on colour vision (see [`ycrystal.core.colors`][ycrystal.core.colors]).
"""

from __future__ import annotations

import numpy as np
from PySide6.QtCore import QPointF, QRect, QSize, Qt, Signal
from PySide6.QtGui import QColor, QImage, QMouseEvent, QPainter, QPen
from PySide6.QtWidgets import (
    QCompleter,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QSlider,
    QSpinBox,
    QToolTip,
    QVBoxLayout,
    QWidget,
)

from ycrystal.core.colors import (
    NAMED_COLORS,
    RGB,
    color_label,
    format_color,
    hex_to_rgb,
    parse_color,
    to_255,
    to_hsl,
    to_hsv,
)


def _hsl_image(width: int, height: int, saturation: float) -> np.ndarray:
    """RGB array (height, width, 3) in 0–1: hue along x, lightness from 1 (top) to 0."""
    hue = (np.arange(width) + 0.5) / width
    light = 1.0 - (np.arange(height) + 0.5) / height
    h = np.broadcast_to(hue[None, :], (height, width))
    lightness = np.broadcast_to(light[:, None], (height, width))
    c = (1 - np.abs(2 * lightness - 1)) * saturation
    hp = h * 6.0
    x = c * (1 - np.abs(hp % 2 - 1))
    zeros = np.zeros_like(c)
    sector = np.floor(hp).astype(int) % 6
    r = np.choose(sector, [c, x, zeros, zeros, x, c])
    g = np.choose(sector, [x, c, c, x, zeros, zeros])
    b = np.choose(sector, [zeros, zeros, x, c, c, x])
    m = lightness - c / 2
    return np.clip(np.stack([r + m, g + m, b + m], axis=-1), 0.0, 1.0)


class SpectrumField(QWidget):
    """Hue (horizontal) × lightness (vertical) field at an adjustable saturation.

    Hovering emits [`hovered`][ycrystal.gui.color_dialog.SpectrumField.hovered];
    clicking or dragging emits [`picked`][ycrystal.gui.color_dialog.SpectrumField.picked].
    """

    hovered = Signal(object)
    """Colour under the mouse (sRGB tuple), or ``None`` when the mouse leaves."""

    picked = Signal(object)
    """Colour clicked or dragged to (sRGB tuple)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMouseTracking(True)
        self.setMinimumSize(300, 160)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self._saturation = 1.0
        self._image: QImage | None = None
        self._marker: tuple[float, float] | None = None
        self.setToolTip("Hover to see the colour name; click to choose")
        self.setAccessibleName("Colour spectrum: hue from left to right, lightness from top")

    def sizeHint(self) -> QSize:  # noqa: N802 - Qt API name
        return QSize(360, 180)

    def saturation(self) -> float:
        """Return the saturation of the field (0–1)."""
        return self._saturation

    def set_saturation(self, saturation: float) -> None:
        """Redraw the field at ``saturation`` (0–1)."""
        self._saturation = max(0.0, min(1.0, float(saturation)))
        self._image = None
        self.update()

    def set_marker(self, color: RGB | None) -> None:
        """Mark the hue and lightness of ``color`` on the field."""
        if color is None:
            self._marker = None
        else:
            hue, _, lightness = to_hsl(color)
            self._marker = (hue / 360.0, lightness / 100.0)
        self.update()

    def color_at(self, x: float, y: float) -> RGB:
        """Return the colour at widget position ``(x, y)``."""
        width, height = max(self.width(), 1), max(self.height(), 1)
        px = int(min(max(x, 0), width - 1))
        py = int(min(max(y, 0), height - 1))
        r, g, b = _hsl_image(width, height, self._saturation)[py, px]
        return (float(r), float(g), float(b))

    def _ensure_image(self) -> QImage:
        if self._image is None or self._image.size() != self.size():
            data = (_hsl_image(self.width(), self.height(), self._saturation) * 255).astype(
                np.uint8
            )
            self._bytes = np.ascontiguousarray(data)
            h, w, _ = self._bytes.shape
            self._image = QImage(self._bytes.data, w, h, 3 * w, QImage.Format.Format_RGB888)
        return self._image

    def paintEvent(self, _event) -> None:  # noqa: N802, ANN001
        painter = QPainter(self)
        painter.drawImage(0, 0, self._ensure_image())
        if self._marker is not None:
            x = self._marker[0] * self.width()
            y = (1.0 - self._marker[1]) * self.height()
            for color, width in ((Qt.GlobalColor.black, 3), (Qt.GlobalColor.white, 1)):
                painter.setPen(QPen(color, width))
                painter.drawEllipse(QPointF(x, y), 6, 6)
        painter.end()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        color = self.color_at(event.position().x(), event.position().y())
        self.hovered.emit(color)
        if event.buttons() & Qt.MouseButton.LeftButton:
            self.picked.emit(color)

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self.picked.emit(self.color_at(event.position().x(), event.position().y()))

    def leaveEvent(self, _event) -> None:  # noqa: N802, ANN001
        self.hovered.emit(None)


def _swatch_order() -> list[tuple[str, RGB]]:
    """Named colours: neutrals by lightness, then the others by hue and lightness."""
    items = [(name, hex_to_rgb(code)) for name, code in NAMED_COLORS]

    def key(item: tuple[str, RGB]) -> tuple:
        hue, sat, light = to_hsl(item[1])
        neutral = sat < 12 or max(item[1]) - min(item[1]) < 0.06
        return (0, -light, 0) if neutral else (1, round(hue / 12), -light)

    return sorted(items, key=key)


class SwatchGrid(QWidget):
    """Grid of the CSS named colours; hovering names them, clicking chooses one."""

    hovered = Signal(object)
    """Colour under the mouse (sRGB tuple), or ``None``."""

    focused = Signal(object)
    """Colour of the keyboard-focused swatch (sRGB tuple)."""

    picked = Signal(object)
    """Colour clicked, or chosen with Enter/Space (sRGB tuple)."""

    CELL = 16
    COLUMNS = 20

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.swatches = _swatch_order()
        self.current = 0
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setToolTip("Named colours: arrow keys move, Enter chooses; hover to read names")
        rows = -(-len(self.swatches) // self.COLUMNS)
        self.setFixedSize(self.COLUMNS * (self.CELL + 2), rows * (self.CELL + 2))

    def cell_rect(self, index: int) -> QRect:
        """Return the rectangle of swatch ``index``."""
        row, col = divmod(index, self.COLUMNS)
        return QRect(col * (self.CELL + 2) + 1, row * (self.CELL + 2) + 1, self.CELL, self.CELL)

    def index_at(self, x: float, y: float) -> int | None:
        """Return the swatch index at widget position ``(x, y)``, or ``None``."""
        col, row = int(x // (self.CELL + 2)), int(y // (self.CELL + 2))
        index = row * self.COLUMNS + col
        if 0 <= col < self.COLUMNS and 0 <= index < len(self.swatches):
            return index
        return None

    def describe(self, index: int) -> str:
        """Return ``"name — #HEX — RGB (r, g, b)"`` for swatch ``index``."""
        name, rgb = self.swatches[index]
        return f"{name} — {color_values(rgb)}"

    def set_current(self, index: int) -> None:
        """Move the keyboard focus to swatch ``index`` and report its colour."""
        self.current = max(0, min(len(self.swatches) - 1, index))
        self.setAccessibleName(f"Named colour: {self.describe(self.current)}")
        self.focused.emit(self.swatches[self.current][1])
        self.update()

    def paintEvent(self, _event) -> None:  # noqa: N802, ANN001
        painter = QPainter(self)
        painter.setPen(QPen(QColor(110, 110, 110), 1))
        for index, (_, rgb) in enumerate(self.swatches):
            painter.setBrush(QColor.fromRgbF(*rgb))
            painter.drawRect(self.cell_rect(index))
        if self.hasFocus():
            painter.setBrush(Qt.BrushStyle.NoBrush)
            rect = self.cell_rect(self.current).adjusted(-1, -1, 1, 1)
            for color, width in ((Qt.GlobalColor.black, 3), (Qt.GlobalColor.white, 1)):
                painter.setPen(QPen(color, width))
                painter.drawRect(rect)
        painter.end()

    def keyPressEvent(self, event) -> None:  # noqa: N802, ANN001
        steps = {
            Qt.Key.Key_Left: -1,
            Qt.Key.Key_Right: 1,
            Qt.Key.Key_Up: -self.COLUMNS,
            Qt.Key.Key_Down: self.COLUMNS,
        }
        key = event.key()
        if key in steps:
            self.set_current(self.current + steps[key])
        elif key in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            self.picked.emit(self.swatches[self.current][1])
        else:
            super().keyPressEvent(event)

    def focusInEvent(self, event) -> None:  # noqa: N802, ANN001
        super().focusInEvent(event)
        self.set_current(self.current)

    def focusOutEvent(self, event) -> None:  # noqa: N802, ANN001
        super().focusOutEvent(event)
        self.update()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        index = self.index_at(event.position().x(), event.position().y())
        if index is None:
            self.hovered.emit(None)
            QToolTip.hideText()
            return
        self.hovered.emit(self.swatches[index][1])
        QToolTip.showText(event.globalPosition().toPoint(), self.describe(index), self)

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        index = self.index_at(event.position().x(), event.position().y())
        if index is not None and event.button() == Qt.MouseButton.LeftButton:
            self.current = index
            self.picked.emit(self.swatches[index][1])
            self.update()

    def leaveEvent(self, _event) -> None:  # noqa: N802, ANN001
        self.hovered.emit(None)


def color_values(rgb: RGB) -> str:
    """Return the exact values of a colour, for example ``#FF0000 — RGB (255, 0, 0)``."""
    r, g, b = to_255(rgb)
    return f"{format_color(rgb, 'hex')} — RGB ({r}, {g}, {b})"


def _swatch_label(rgb: RGB) -> str:
    return (
        f"QLabel {{ background-color: {format_color(rgb)}; border: 1px solid #777; "
        "min-height: 36px; }"
    )


class ColorDialog(QDialog):
    """Choose a colour on a spectrum, from named colours, or by typing it.

    Parameters
    ----------
    initial
        Colour shown at the start (sRGB, 0–1).
    title
        Window title.
    parent
        Parent widget.

    Notes
    -----
    Typed values apply when a field changes (spin boxes) or on Enter (hex and text);
    invalid text is reported below the fields and leaves the colour unchanged. The RGB
    0–1 fields keep three decimals, so colours from projects are not rounded to 8 bits
    unless edited in an 8-bit field.
    """

    color_changed = Signal(object)
    """The chosen colour changed (sRGB tuple)."""

    def __init__(
        self, initial: RGB, title: str = "Choose Colour", parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self._initial = (float(initial[0]), float(initial[1]), float(initial[2]))
        self._color = self._initial
        self._syncing = False
        self._applied_text = ""
        layout = QHBoxLayout(self)

        # ----- left: spectrum, saturation, named colours, hover name ---------------------
        left = QVBoxLayout()
        left.addWidget(QLabel("<b>Spectrum</b> — rest the mouse on a colour to read its name"))
        self.spectrum = SpectrumField()
        self.spectrum.hovered.connect(self._show_hover)
        self.spectrum.picked.connect(lambda rgb: self.set_color(rgb, source="spectrum"))
        left.addWidget(self.spectrum, 1)
        row = QHBoxLayout()
        row.addWidget(QLabel("Saturation"))
        self.saturation_slider = QSlider(Qt.Orientation.Horizontal)
        self.saturation_slider.setRange(0, 100)
        self.saturation_slider.setValue(100)
        self.saturation_slider.valueChanged.connect(
            lambda v: self.spectrum.set_saturation(v / 100.0)
        )
        row.addWidget(self.saturation_slider, 1)
        left.addLayout(row)
        left.addWidget(QLabel("<b>Named colours</b>"))
        self.swatches = SwatchGrid()
        self.swatches.hovered.connect(self._show_hover)
        self.swatches.focused.connect(lambda rgb: self._show_hover(rgb, "Keyboard focus"))
        self.swatches.picked.connect(lambda rgb: self.set_color(rgb, source="swatch"))
        left.addWidget(self.swatches)
        self.hover_label = QLabel()
        self.hover_label.setWordWrap(True)
        self.hover_label.setMinimumHeight(40)
        self.hover_label.setTextFormat(Qt.TextFormat.RichText)
        left.addWidget(self.hover_label)
        self._show_hover(None)
        layout.addLayout(left, 1)

        # ----- right: preview, name, typed input -----------------------------------------
        right = QVBoxLayout()
        previews = QHBoxLayout()
        self.before_swatch, self.after_swatch = QLabel(), QLabel()
        for caption, swatch in (("Current", self.before_swatch), ("New", self.after_swatch)):
            column = QVBoxLayout()
            column.addWidget(QLabel(caption))
            swatch.setMinimumWidth(90)
            column.addWidget(swatch)
            previews.addLayout(column)
        self.before_swatch.setStyleSheet(_swatch_label(self._initial))
        self.before_swatch.setToolTip(color_label(self._initial))
        right.addLayout(previews)
        self.name_label = QLabel()
        self.name_label.setWordWrap(True)
        self.name_label.setTextFormat(Qt.TextFormat.RichText)
        right.addWidget(self.name_label)

        group = QGroupBox("Type a colour")
        form = QFormLayout(group)
        self.hex_edit = QLineEdit()
        self.hex_edit.setPlaceholderText("#RRGGBB")
        self.hex_edit.setMaxLength(7)
        self.hex_edit.editingFinished.connect(lambda: self._apply_text(self.hex_edit, "hex"))
        self.hex_edit.textEdited.connect(lambda _t: self._validate_pending())
        self.hex_edit.setAccessibleName("Hexadecimal colour #RRGGBB")
        form.addRow("Hex", self.hex_edit)
        self.rgb255 = self._triple(
            QSpinBox, (0, 255), 1, "RGB (0–255)", form, "rgb255", ("Red", "Green", "Blue"), 0
        )
        self.rgb01 = self._triple(
            QDoubleSpinBox, (0.0, 1.0), 0.01, "RGB (0–1)", form, "rgb01",
            ("Red fraction", "Green fraction", "Blue fraction"), 3,
        )  # fmt: skip
        self.hsv = self._triple(
            QDoubleSpinBox, (0.0, 100.0), 1.0, "HSV (H°, S%, V%)", form, "hsv",
            ("HSV hue in degrees", "HSV saturation in percent", "HSV value in percent"), 1,
        )  # fmt: skip
        self.hsl = self._triple(
            QDoubleSpinBox, (0.0, 100.0), 1.0, "HSL (H°, S%, L%)", form, "hsl",
            ("HSL hue in degrees", "HSL saturation in percent", "HSL lightness in percent"), 1,
        )  # fmt: skip
        for spins in (self.hsv, self.hsl):
            spins[0].setRange(0.0, 359.9)  # hue 0–359 degrees
            spins[0].setWrapping(True)
        self.text_edit = QLineEdit()
        self.text_edit.setPlaceholderText("name, rgb(…), hsv(…), hsl(…), 0.2 0.4 0.6 …")
        completer = QCompleter([name for name, _ in NAMED_COLORS], self.text_edit)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self.text_edit.setCompleter(completer)
        self.text_edit.returnPressed.connect(lambda: self._apply_text(self.text_edit, "text"))
        self.text_edit.textEdited.connect(lambda _t: self._validate_pending())
        self.text_edit.setAccessibleName("Colour name or any notation")
        form.addRow("Name or any notation", self.text_edit)
        self.error_label = QLabel()
        self.error_label.setWordWrap(True)
        self.error_label.setStyleSheet("QLabel { color: #c0392b; }")
        form.addRow(self.error_label)
        right.addWidget(group)
        right.addStretch(1)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.ok_button = buttons.button(QDialogButtonBox.StandardButton.Ok)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        right.addWidget(buttons)
        layout.addLayout(right)
        self.set_color(self._initial)

    # ----- construction helpers ---------------------------------------------------------
    def _triple(self, kind, limits, step, label, form, source, names, decimals) -> list:  # noqa: ANN001
        row = QHBoxLayout()
        spins = []
        for name in names:
            spin = kind()
            spin.setRange(*limits)
            spin.setSingleStep(step)
            spin.setAccessibleName(name)
            spin.setToolTip(name)
            if isinstance(spin, QDoubleSpinBox):
                spin.setDecimals(decimals)
            spin.valueChanged.connect(lambda _v, s=source: self._apply_spins(s))
            spins.append(spin)
            row.addWidget(spin)
        form.addRow(label, row)
        return spins

    # ----- public -----------------------------------------------------------------------
    def color(self) -> RGB:
        """Return the chosen colour (sRGB, 0–1)."""
        return self._color

    def set_color(self, color: RGB, source: str = "") -> None:
        """Show ``color`` in every field except the one it came from."""
        self._color = (float(color[0]), float(color[1]), float(color[2]))
        self._syncing = True
        try:
            if source != "hex":
                self.hex_edit.setText(format_color(self._color, "hex"))
            if source != "rgb255":
                for spin, value in zip(self.rgb255, to_255(self._color), strict=True):
                    spin.setValue(value)
            if source != "rgb01":
                for spin, value in zip(self.rgb01, self._color, strict=True):
                    spin.setValue(round(value, 3))
            # Hue: keep the edited or previous hue for greys (where it is undefined),
            # without changing the RGB value.
            hue = None
            if source in ("hsv", "hsl"):
                hue = (self.hsv if source == "hsv" else self.hsl)[0].value()
            elif max(self._color) - min(self._color) < 1e-9:
                hue = self.hsv[0].value()
            for name, spins, values in (
                ("hsv", self.hsv, to_hsv(self._color)),
                ("hsl", self.hsl, to_hsl(self._color)),
            ):
                if source == name:
                    continue
                h, a, b = values
                h = hue if hue is not None else round(h, 1) % 360.0
                for spin, value in zip(spins, (h, round(a, 1), round(b, 1)), strict=True):
                    spin.setValue(value)
            saturation = to_hsl(self._color)[1]
            if source != "spectrum" and saturation >= 20:
                # Show the colour's own saturation, but keep a vivid field for greys.
                self.saturation_slider.setValue(round(saturation))
        finally:
            self._syncing = False
        self.error_label.clear()
        self.ok_button.setEnabled(True)
        self._applied_text = self.text_edit.text()
        self.spectrum.set_marker(self._color)
        self.after_swatch.setStyleSheet(_swatch_label(self._color))
        self.after_swatch.setToolTip(color_label(self._color))
        self.name_label.setText(
            f"<b>{color_label(self._color)}</b><br>{color_values(self._color)}"
            f" · {format_color(self._color, 'hsl')}"
        )
        self.after_swatch.setAccessibleName(f"New colour: {color_label(self._color)}")
        self.color_changed.emit(self._color)

    def hover_text(self) -> str:
        """Return the text currently shown for the colour under the mouse."""
        return self.hover_label.text()

    @staticmethod
    def get_color(
        initial: RGB, parent: QWidget | None = None, title: str = "Choose Colour"
    ) -> RGB | None:
        """Show the dialog modally; return the chosen colour or ``None`` if cancelled."""
        dialog = ColorDialog(initial, title, parent)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            return dialog.color()
        return None

    def accept(self) -> None:
        """Accept only a valid colour; typed text that was not applied is applied first."""
        if self.hex_edit.text().strip().upper() != format_color(self._color, "hex"):
            if not self._apply_text(self.hex_edit, "hex"):
                return
        text = self.text_edit.text().strip()
        if text and text != self._applied_text and not self._apply_text(self.text_edit, "text"):
            return
        super().accept()

    # ----- internals --------------------------------------------------------------------
    def _show_hover(self, color: RGB | None, how: str = "Under the mouse") -> None:
        if color is None:
            self.hover_label.setText(
                "<i>Rest the mouse on the spectrum or a named colour to read its name.</i>"
            )
        else:
            self.hover_label.setText(f"{how}: <b>{color_label(color)}</b> — {color_values(color)}")

    def _validate_pending(self) -> None:
        """While typing: block OK and explain if the hex or text field cannot be read."""
        problems = []
        for edit in (self.hex_edit, self.text_edit):
            text = edit.text().strip()
            if text and (edit is self.hex_edit or text != self._applied_text):
                try:
                    parse_color(text)
                except ValueError as exc:
                    problems.append(str(exc).capitalize())
        self.error_label.setText(" ".join(problems))
        self.ok_button.setEnabled(not problems)

    def _apply_spins(self, source: str) -> None:
        if self._syncing:
            return
        if source == "rgb255":
            color = tuple(spin.value() / 255.0 for spin in self.rgb255)
        elif source == "rgb01":
            color = tuple(float(spin.value()) for spin in self.rgb01)
        else:
            h, a, b = (spin.value() for spin in (self.hsv if source == "hsv" else self.hsl))
            color = parse_color(f"{source}({h}, {a}, {b})")
        self.set_color(color, source=source)  # type: ignore[arg-type]

    def _apply_text(self, edit: QLineEdit, source: str) -> bool:
        if self._syncing:
            return True
        try:
            color = parse_color(edit.text())
        except ValueError as exc:
            self.error_label.setText(str(exc).capitalize())
            self.ok_button.setEnabled(False)
            return False
        self.set_color(color, source=source if source == "hex" else "")
        return True
