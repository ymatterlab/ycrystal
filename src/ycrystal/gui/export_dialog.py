"""The Render Image dialog: format, figure size, resolution, and file (FR-EXPORT-01).

The dialog only collects choices; the main window renders with POV-Ray and writes the
file (see [`ycrystal.render.formats`][ycrystal.render.formats]). Sizes are entered in
pixels or millimetres; the pixel size POV-Ray renders follows from them and the
resolution ([`figure_pixels`][ycrystal.core.export.figure_pixels]). With the shape
kept (the default), the height follows the blue output frame of the 3D view, so the
image shows exactly the framed area at any size.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path

from PySide6.QtCore import QSignalBlocker
from PySide6.QtGui import QIntValidator
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ycrystal.core import aspect
from ycrystal.core import export as ex

SIZE_MODES: tuple[tuple[str, str], ...] = (
    ("output", "Output size (Render panel)"),
    *((p.key, f"{p.label} ({p.width_mm:g} mm, {p.dpi} dpi)") for p in ex.SIZE_PRESETS),
    ("custom", "Custom"),
)
"""Size choices of the dialog: ``(key, label)``."""


@dataclass(frozen=True)
class ExportChoice:
    """Everything the dialog shows; the window keeps the last one for the session.

    Attributes
    ----------
    format
        ``"png"``, ``"pdf"``, or ``"jpeg"``.
    mode
        Size choice: ``"output"`` (the Render panel's pixel size), a key of
        [`SIZE_PRESETS`][ycrystal.core.export.SIZE_PRESETS], or ``"custom"``.
    unit
        Unit of `width` and `height`: ``"px"`` or ``"mm"``.
    width, height
        Size in `unit`.
    dpi
        Resolution in dots per inch.
    locked
        Whether the height follows the frame's shape.
    jpeg_quality
        JPEG quality, 1–100.
    path
        Destination file, or ``None`` for a name proposed by the window.
    """

    format: str = ex.DEFAULT_FORMAT
    mode: str = "output"
    unit: str = "px"
    width: float = 1200.0
    height: float = 800.0
    dpi: int = ex.DEFAULT_DPI
    locked: bool = True
    jpeg_quality: int = ex.DEFAULT_JPEG_QUALITY
    path: Path | None = None

    def pixels(self) -> tuple[int, int]:
        """Return the pixel size POV-Ray renders for this choice."""
        return ex.figure_pixels(self.unit, self.width, self.height, self.dpi)

    def options(self) -> ex.ExportOptions:
        """Return the export options.

        Raises
        ------
        ExportSizeError
            If the size, resolution, or quality is outside the limits.
        """
        width, height = self.pixels()
        return ex.ExportOptions(self.format, width, height, self.dpi, self.jpeg_quality)

    def fitted(self, output: tuple[int, int]) -> ExportChoice:
        """Return this choice adapted to the current output frame ``(width, height)``.

        The Output size follows the Render panel; presets and locked custom sizes keep
        their width and take the frame's shape; unlocked custom sizes stay as they are.
        """
        ratio = output[0] / output[1]
        if self.mode == "output":
            return replace(self, unit="px", width=float(output[0]), height=float(output[1]))
        if self.mode != "custom":
            preset = ex.size_preset(self.mode)
            return replace(
                self,
                unit="mm",
                width=preset.width_mm,
                height=ex.linked_height(preset.width_mm, ratio, "mm"),
                dpi=preset.dpi,
                locked=True,
            )
        if self.locked:
            return replace(self, height=ex.linked_height(self.width, ratio, self.unit))
        return self


class ExportDialog(QDialog):
    """Modal dialog for *Render ▸ Render Image…*.

    Parameters
    ----------
    choice
        Initial state (normally the last one of the session, already
        [`fitted`][ycrystal.gui.export_dialog.ExportChoice.fitted]).
    output
        The Render panel's output size in pixels; its shape is the blue frame.
    transparent
        Whether the background is transparent (JPEG then fills it with white).
    parent
        Parent widget.
    """

    def __init__(
        self,
        choice: ExportChoice,
        output: tuple[int, int],
        transparent: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Render Image")
        self._output = (int(output[0]), int(output[1]))
        self._ratio = self._output[0] / self._output[1]
        self._transparent = transparent
        self._choice = choice
        layout = QVBoxLayout(self)

        file_group = QGroupBox("File")
        file_form = QFormLayout(file_group)
        self.format_combo = QComboBox()
        for key, label, suffixes in ex.FORMATS:
            self.format_combo.addItem(f"{label} ({', '.join(suffixes)})", key)
        self.format_combo.setAccessibleName("Export format")
        file_form.addRow("Format", self.format_combo)
        path_row = QHBoxLayout()
        self.path_edit = QLineEdit()
        self.path_edit.setAccessibleName("Destination file")
        self.path_edit.setMinimumWidth(320)
        self.browse_button = QPushButton("Browse…")
        path_row.addWidget(self.path_edit, 1)
        path_row.addWidget(self.browse_button)
        file_form.addRow("Save as", path_row)
        layout.addWidget(file_group)

        size_group = QGroupBox("Size")
        form = QFormLayout(size_group)
        self.mode_combo = QComboBox()
        for key, label in SIZE_MODES:
            self.mode_combo.addItem(label, key)
        self.mode_combo.setAccessibleName("Image size")
        self.mode_combo.setToolTip(
            "Publication sizes are common defaults, not the rule of a particular "
            "journal; check the author guidelines and use Custom where they differ."
        )
        form.addRow("Size", self.mode_combo)
        self.width_spin = QDoubleSpinBox()
        self.height_spin = QDoubleSpinBox()
        for spin, name in ((self.width_spin, "width"), (self.height_spin, "height")):
            spin.setKeyboardTracking(False)
            spin.setRange(0.01, 1e6)
            spin.setAccessibleName(f"Image {name}")
        dims = QHBoxLayout()
        dims.addWidget(self.width_spin, 1)
        dims.addWidget(QLabel("×"))
        dims.addWidget(self.height_spin, 1)
        self.unit_combo = QComboBox()
        self.unit_combo.addItem("px", "px")
        self.unit_combo.addItem("mm", "mm")
        self.unit_combo.setAccessibleName("Unit of width and height")
        dims.addWidget(self.unit_combo)
        form.addRow("Width × height", dims)
        self.dpi_combo = QComboBox()
        self.dpi_combo.setEditable(True)
        self.dpi_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        for dpi in ex.COMMON_DPI:
            self.dpi_combo.addItem(str(dpi))
        self.dpi_combo.setValidator(QIntValidator(ex.MIN_DPI, ex.MAX_DPI, self))
        self.dpi_combo.setAccessibleName("Resolution in dots per inch")
        self.dpi_combo.setToolTip(
            "Dots per inch: converts millimetres to pixels, is stored in PNG and JPEG "
            "files, and sets the PDF page size. Any value can be entered."
        )
        form.addRow("Resolution (dpi)", self.dpi_combo)
        self.lock_check = QCheckBox("Keep the shape of the output frame")
        self.lock_check.setToolTip(
            "The height follows the width so that the image shows exactly the blue "
            "frame of the 3D view. Unchecked, width and height are independent and the "
            "image shows a wider or narrower area at the same scale (never stretched)."
        )
        form.addRow(self.lock_check)
        self.summary_label = QLabel()
        self.summary_label.setWordWrap(True)
        form.addRow(self.summary_label)
        self.warning_label = QLabel()
        self.warning_label.setWordWrap(True)
        form.addRow(self.warning_label)
        layout.addWidget(size_group)

        self.jpeg_group = QGroupBox("JPEG")
        jpeg_form = QFormLayout(self.jpeg_group)
        self.quality_spin = QSpinBox()
        self.quality_spin.setRange(1, 100)
        self.quality_spin.setAccessibleName("JPEG quality")
        self.quality_spin.setToolTip("1 (smallest file) to 100 (best quality); default 95")
        jpeg_form.addRow("Quality", self.quality_spin)
        self.matte_label = QLabel(
            "JPEG has no transparency: the transparent background becomes white."
        )
        self.matte_label.setWordWrap(True)
        jpeg_form.addRow(self.matte_label)
        layout.addWidget(self.jpeg_group)

        self.pdf_note = QLabel(
            "The PDF page has the physical size above and contains the POV-Ray image "
            "at full resolution (a raster image, not vector graphics)."
        )
        self.pdf_note.setWordWrap(True)
        layout.addWidget(self.pdf_note)

        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        self.export_button = self.buttons.addButton(
            "Render", QDialogButtonBox.ButtonRole.AcceptRole
        )
        self.export_button.setDefault(True)
        self.buttons.accepted.connect(self._accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)

        self._show_choice()
        self.format_combo.currentIndexChanged.connect(self._on_format)
        self.path_edit.textEdited.connect(self._on_path_edited)
        self.browse_button.clicked.connect(self.browse)
        self.mode_combo.currentIndexChanged.connect(self._on_mode)
        self.width_spin.valueChanged.connect(lambda v: self._on_dimension("width", v))
        self.height_spin.valueChanged.connect(lambda v: self._on_dimension("height", v))
        self.unit_combo.currentIndexChanged.connect(self._on_unit)
        self.dpi_combo.currentTextChanged.connect(self._on_dpi)
        self.lock_check.toggled.connect(self._on_lock)
        self.quality_spin.valueChanged.connect(
            lambda v: self._set(replace(self._choice, jpeg_quality=int(v)))
        )

    # ----- result -----------------------------------------------------------------------
    def choice(self) -> ExportChoice:
        """Return the current choice (also after the dialog was closed)."""
        return self._choice

    def options(self) -> ex.ExportOptions | None:
        """Return the export options, or ``None`` while the entries are invalid."""
        try:
            return self._choice.options()
        except ex.ExportSizeError:
            return None

    def destination(self) -> Path | None:
        """Return the destination with the format's suffix, or ``None`` without a name."""
        text = self.path_edit.text().strip()
        return ex.path_for_format(Path(text).expanduser(), self._choice.format) if text else None

    def browse(self) -> None:
        """Choose the destination with the system's save dialog."""
        fmt = self._choice.format
        suffixes = " ".join(f"*{s}" for s in ex.format_suffixes(fmt))
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Render Image",
            str(self.destination() or ""),
            f"{ex.format_label(fmt)} ({suffixes})",
        )
        if path:
            self._set(replace(self._choice, path=ex.path_for_format(path, fmt)))
            self._show_choice()

    # ----- edits ------------------------------------------------------------------------
    def _set(self, choice: ExportChoice) -> None:
        self._choice = choice
        self._update_summary()

    def _custom(self, **changes: object) -> ExportChoice:
        """Return the choice with ``changes``; editing a preset's values makes it Custom."""
        return replace(self._choice, mode="custom", **changes)

    def _on_format(self, index: int) -> None:
        fmt = self.format_combo.itemData(index)
        path = self._choice.path
        self._set(
            replace(
                self._choice,
                format=fmt,
                path=ex.path_for_format(path, fmt) if path is not None else None,
            )
        )
        self._show_choice()

    def _on_path_edited(self, text: str) -> None:
        self._choice = replace(
            self._choice, path=Path(text.strip()).expanduser() if text.strip() else None
        )
        self._update_summary()

    def _on_mode(self, index: int) -> None:
        mode = self.mode_combo.itemData(index)
        self._set(replace(self._choice, mode=mode).fitted(self._output))
        self._show_choice()

    def _on_dimension(self, edited: str, value: float) -> None:
        c = self._choice
        if c.unit == "px":
            value = float(aspect.round_pixels(value))
        if edited == "width":
            height = ex.linked_height(value, self._ratio, c.unit) if c.locked else c.height
            choice = self._custom(width=value, height=height)
        else:
            width = ex.linked_width(value, self._ratio, c.unit) if c.locked else c.width
            choice = self._custom(width=width, height=value)
        self._set(choice)
        self._show_choice()

    def _on_unit(self, index: int) -> None:
        unit = self.unit_combo.itemData(index)
        c = self._choice
        width = ex.convert_length(c.width, c.unit, unit, c.dpi)
        if c.locked:
            height = ex.linked_height(width, self._ratio, unit)
        else:
            height = ex.convert_length(c.height, c.unit, unit, c.dpi)
        # Changing the unit keeps the size; a preset stays selected.
        self._set(replace(c, unit=unit, width=width, height=height))
        self._show_choice()

    def _on_dpi(self, text: str) -> None:
        try:
            dpi = int(text)
        except ValueError:
            self._update_summary(invalid_dpi=True)
            return
        if dpi == self._choice.dpi:
            return
        # Millimetres keep the physical size (more pixels); pixels keep the pixel size,
        # so the Output size stays selected while it is given in pixels.
        c = self._choice
        mode = c.mode if c.mode == "output" and c.unit == "px" else "custom"
        self._set(replace(c, dpi=dpi, mode=mode))
        self._show_choice()

    def _on_lock(self, locked: bool) -> None:
        c = self._choice
        height = ex.linked_height(c.width, self._ratio, c.unit) if locked else c.height
        self._set(self._custom(locked=locked, height=height))
        self._show_choice()

    def _accept(self) -> None:
        if not self.export_button.isEnabled():  # for example an empty resolution field
            return
        if self.options() is not None and self.destination() is not None:
            self._choice = replace(self._choice, path=self.destination())
            self.accept()

    # ----- display ----------------------------------------------------------------------
    def _show_choice(self) -> None:
        c = self._choice
        widgets = (
            self.format_combo,
            self.path_edit,
            self.mode_combo,
            self.width_spin,
            self.height_spin,
            self.unit_combo,
            self.dpi_combo,
            self.lock_check,
            self.quality_spin,
        )
        blockers = [QSignalBlocker(w) for w in widgets]
        try:
            self.format_combo.setCurrentIndex(self.format_combo.findData(c.format))
            if c.path is not None and self.path_edit.text() != str(c.path):
                self.path_edit.setText(str(c.path))
            self.mode_combo.setCurrentIndex(self.mode_combo.findData(c.mode))
            decimals, suffix, step = (0, " px", 10.0) if c.unit == "px" else (2, " mm", 1.0)
            for spin, value in ((self.width_spin, c.width), (self.height_spin, c.height)):
                spin.setDecimals(decimals)
                spin.setSuffix(suffix)
                spin.setSingleStep(step)
                spin.setValue(value)
            self.unit_combo.setCurrentIndex(self.unit_combo.findData(c.unit))
            if self.dpi_combo.currentText() != str(c.dpi):
                self.dpi_combo.setEditText(str(c.dpi))
            self.lock_check.setChecked(c.locked)
            self.quality_spin.setValue(c.jpeg_quality)
        finally:
            del blockers
        self.jpeg_group.setVisible(c.format == "jpeg")
        self.matte_label.setVisible(c.format == "jpeg" and self._transparent)
        self.pdf_note.setVisible(c.format == "pdf")
        self._update_summary()

    def _update_summary(self, invalid_dpi: bool = False) -> None:
        c = self._choice
        problem = ""
        if invalid_dpi:
            problem = f"Enter a resolution between {ex.MIN_DPI} and {ex.MAX_DPI} dpi."
        width, height = c.pixels()
        width_mm, height_mm = ex.mm_from_pixels(width, c.dpi), ex.mm_from_pixels(height, c.dpi)
        text = (
            f"POV-Ray renders {width} × {height} px "
            f"({width * height / 1e6:.1f} megapixels) · {width_mm:.1f} × {height_mm:.1f} mm "
            f"at {c.dpi} dpi"
        )
        if c.format == "pdf":
            text += " · PDF page of this size"
        self.summary_label.setText(text)
        if not problem:
            try:
                c.options()
            except ex.ExportSizeError as error:
                problem = str(error)
        if not problem and self.destination() is None:
            problem = "Choose a file name."
        notes = []
        if problem:
            notes.append(f"⚠ {problem}")
        if not c.locked and not aspect.matches_ratio((width, height), self._ratio):
            notes.append(
                "The shape differs from the blue output frame: the image shows a wider "
                "or narrower area at the same scale (nothing is stretched)."
            )
        self.warning_label.setText("\n".join(notes))
        self.warning_label.setVisible(bool(notes))
        self.export_button.setEnabled(not problem)
        self.summary_label.setAccessibleName(text)
