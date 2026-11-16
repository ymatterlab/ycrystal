"""Image export: formats, figure sizes, and resolution arithmetic (FR-EXPORT-01).

POV-Ray renders a raster image; Ycrystal writes it as PNG, PDF, or JPEG. This module
holds the arithmetic shared by the export dialog, the window, and the tests, without
Qt. Writing the files is [`ycrystal.render.formats`][ycrystal.render.formats].

Four quantities are kept apart:

- the *pixel size* POV-Ray renders (``width`` × ``height``), which is the size of the
  PNG and JPEG and of the image embedded in the PDF;
- the *resolution* in dots per inch, stored as metadata in PNG and JPEG files and
  used to compute the PDF page size;
- the *physical size*, ``pixels / dpi × 25.4`` mm;
- the size the user entered, in pixels or millimetres
  ([`figure_pixels`][ycrystal.core.export.figure_pixels] converts it).

Examples
--------
>>> from ycrystal.core.export import pixels_from_mm, mm_from_pixels
>>> pixels_from_mm(85, 600)  # single column at 600 dpi
2008
>>> pixels_from_mm(180, 600)  # double column at 600 dpi
4252
>>> round(mm_from_pixels(2008, 600), 2)
85.01
>>> figure_pixels("mm", 85, 85 / 1.5, 600)
(2008, 1339)
>>> [round(mm, 2) for mm in ExportOptions("pdf", 2008, 1339, dpi=600).physical_size_mm()]
[85.01, 56.68]
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import NamedTuple

from ycrystal.core.aspect import round_pixels

MM_PER_INCH = 25.4
"""Millimetres per inch."""

FORMATS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("png", "PNG image", (".png",)),
    ("pdf", "PDF document", (".pdf",)),
    ("jpeg", "JPEG image", (".jpg", ".jpeg")),
)
"""Export formats: ``(key, label, file suffixes)``; the first suffix is the default."""

DEFAULT_FORMAT = "png"
"""Format offered first and used by *Render PNG*."""

DEFAULT_JPEG_QUALITY = 95
"""JPEG quality used until the user chooses another (1–100)."""

DEFAULT_DPI = 300
"""Resolution offered until the user chooses one."""

COMMON_DPI = (300, 600)
"""Resolutions offered as quick choices; any value in the limits can be entered."""

MIN_EXPORT_PIXELS = 16
"""Smallest width or height of an exported image, in pixels."""

MAX_EXPORT_PIXELS = 20000
"""Largest width or height of an exported image, in pixels (POV-Ray renders it)."""

MAX_EXPORT_MEGAPIXELS = 150
"""Largest exported image area in megapixels (about 600 MB while it is converted)."""

MIN_DPI = 1
"""Smallest accepted resolution, in dots per inch."""

MAX_DPI = 100_000
"""Largest accepted resolution, in dots per inch (a sanity bound, not a quality cap)."""

MAX_PDF_PAGE_MM = 5080.0
"""Largest PDF page side in millimetres (200 inches, the limit of common PDF readers)."""


class SizePreset(NamedTuple):
    """A figure size: a physical width at a resolution; the height follows the frame.

    Attributes
    ----------
    key
        Identifier (``"single"``, ``"double"``).
    label
        Name shown in the export dialog.
    width_mm
        Physical width in millimetres.
    dpi
        Resolution in dots per inch.
    """

    key: str
    label: str
    width_mm: float
    dpi: int


SIZE_PRESETS: tuple[SizePreset, ...] = (
    SizePreset("single", "Single column", 85.0, 600),
    SizePreset("double", "Double column", 180.0, 600),
)
"""Publication figure sizes. Convenient defaults, not the rule of any particular
journal: check the author guidelines and use Custom sizes where they differ."""


class ExportSizeError(ValueError):
    """An export size or setting is outside the limits; ``str()`` explains it."""


def size_preset(key: str) -> SizePreset:
    """Return the size preset ``key``.

    Raises
    ------
    KeyError
        For an unknown key.
    """
    for preset in SIZE_PRESETS:
        if preset.key == key:
            return preset
    raise KeyError(key)


def pixels_from_mm(mm: float, dpi: float) -> int:
    """Return ``mm / 25.4 × dpi`` rounded half up to whole pixels."""
    return round_pixels(float(mm) / MM_PER_INCH * float(dpi))


def mm_from_pixels(pixels: float, dpi: float) -> float:
    """Return the physical length of ``pixels`` at ``dpi``, in millimetres."""
    return float(pixels) / float(dpi) * MM_PER_INCH


def convert_length(value: float, unit: str, new_unit: str, dpi: float) -> float:
    """Convert a length between ``"px"`` and ``"mm"`` at ``dpi``.

    Pixel values are returned as whole numbers (rounded half up).

    >>> convert_length(85, "mm", "px", 600)
    2008.0
    >>> round(convert_length(2008, "px", "mm", 600), 3)
    85.005
    """
    _check_unit(unit)
    _check_unit(new_unit)
    if unit == new_unit:
        return float(value)
    if new_unit == "px":
        return float(pixels_from_mm(value, dpi))
    return mm_from_pixels(value, dpi)


def figure_pixels(unit: str, width: float, height: float, dpi: float) -> tuple[int, int]:
    """Return the pixel size for a size entered in ``unit`` (``"px"`` or ``"mm"``).

    Millimetres are converted at ``dpi``; pixel values are rounded half up.
    """
    _check_unit(unit)
    if unit == "px":
        return round_pixels(width), round_pixels(height)
    return pixels_from_mm(width, dpi), pixels_from_mm(height, dpi)


def linked_height(width: float, ratio: float, unit: str) -> float:
    """Return the height that keeps ``width / height == ratio`` (whole pixels for ``px``)."""
    _check_unit(unit)
    if not ratio > 0:
        raise ValueError("ratio must be positive")
    height = float(width) / ratio
    return float(round_pixels(height)) if unit == "px" else height


def linked_width(height: float, ratio: float, unit: str) -> float:
    """Return the width that keeps ``width / height == ratio`` (whole pixels for ``px``)."""
    _check_unit(unit)
    if not ratio > 0:
        raise ValueError("ratio must be positive")
    width = float(height) * ratio
    return float(round_pixels(width)) if unit == "px" else width


def format_suffixes(fmt: str) -> tuple[str, ...]:
    """Return the file suffixes of format ``fmt`` (the first is the default).

    Raises
    ------
    ValueError
        For an unknown format.
    """
    for key, _label, suffixes in FORMATS:
        if key == fmt:
            return suffixes
    raise ValueError(f"unknown export format {fmt!r}")


def format_label(fmt: str) -> str:
    """Return the readable name of format ``fmt`` (for example ``"PDF document"``)."""
    format_suffixes(fmt)
    return next(label for key, label, _suffixes in FORMATS if key == fmt)


def format_for_path(path: str | Path) -> str | None:
    """Return the export format that the suffix of ``path`` names, or ``None``.

    >>> format_for_path("figure.JPEG"), format_for_path("figure.pdf"), format_for_path("x")
    ('jpeg', 'pdf', None)
    """
    suffix = Path(path).suffix.lower()
    for key, _label, suffixes in FORMATS:
        if suffix in suffixes:
            return key
    return None


def path_for_format(path: str | Path, fmt: str) -> Path:
    """Return ``path`` with a suffix of format ``fmt``.

    A suffix that already belongs to ``fmt`` is kept (``.jpg`` or ``.jpeg``); the
    suffix of another export format is replaced; any other suffix is kept and the
    format's suffix appended, so names such as ``SrTiO3 v1.2`` survive.

    >>> path_for_format("fig.png", "pdf").name, path_for_format("fig.jpeg", "jpeg").name
    ('fig.pdf', 'fig.jpeg')
    >>> path_for_format("SrTiO3 v1.2", "png").name
    'SrTiO3 v1.2.png'
    """
    path = Path(path)
    suffixes = format_suffixes(fmt)
    if path.suffix.lower() in suffixes:
        return path
    if format_for_path(path) is not None:
        return path.with_suffix(suffixes[0])
    return path.with_name(path.name + suffixes[0])


@dataclass(frozen=True)
class ExportOptions:
    """What to write after POV-Ray has rendered: format, pixel size, and metadata.

    Attributes
    ----------
    format
        ``"png"``, ``"pdf"``, or ``"jpeg"``.
    width, height
        Pixel size POV-Ray renders. The image is never resampled afterwards.
    dpi
        Resolution in dots per inch: stored in PNG (``pHYs``) and JPEG (JFIF) files and
        used for the PDF page size. ``None`` writes no resolution metadata (the PNG is
        then copied byte for byte, as before this feature); PDF needs a value.
    jpeg_quality
        JPEG quality from 1 to 100 (ignored by the other formats).

    Raises
    ------
    ExportSizeError
        If a value is outside the limits of this module.
    """

    format: str = DEFAULT_FORMAT
    width: int = 1200
    height: int = 800
    dpi: float | None = None
    jpeg_quality: int = DEFAULT_JPEG_QUALITY

    def __post_init__(self) -> None:
        format_suffixes(self.format)
        check_export_size(self.width, self.height)
        if self.dpi is not None and not MIN_DPI <= self.dpi <= MAX_DPI:
            raise ExportSizeError(f"The resolution must be between {MIN_DPI} and {MAX_DPI} dpi.")
        if not 1 <= self.jpeg_quality <= 100:
            raise ExportSizeError("The JPEG quality must be between 1 and 100.")
        if self.format == "pdf":
            if self.dpi is None:
                raise ExportSizeError("A PDF needs a resolution to set its page size.")
            longest = mm_from_pixels(max(self.width, self.height), self.dpi)
            if longest > MAX_PDF_PAGE_MM:
                raise ExportSizeError(
                    f"The PDF page would be {longest:.0f} mm long; PDF pages can be at most "
                    f"{MAX_PDF_PAGE_MM:.0f} mm. Increase the resolution or reduce the size."
                )

    def physical_size_mm(self) -> tuple[float, float] | None:
        """Return ``(width, height)`` in millimetres at `dpi`, or ``None`` without it."""
        if self.dpi is None:
            return None
        return mm_from_pixels(self.width, self.dpi), mm_from_pixels(self.height, self.dpi)


def check_export_size(width: int, height: int) -> None:
    """Raise [`ExportSizeError`][ycrystal.core.export.ExportSizeError] for a bad pixel size.

    Each side must be `MIN_EXPORT_PIXELS` to `MAX_EXPORT_PIXELS`, and the area at most
    `MAX_EXPORT_MEGAPIXELS`.
    """
    for name, pixels in (("width", width), ("height", height)):
        if not MIN_EXPORT_PIXELS <= pixels <= MAX_EXPORT_PIXELS:
            raise ExportSizeError(
                f"The image {name} would be {pixels} px; it must be between "
                f"{MIN_EXPORT_PIXELS} and {MAX_EXPORT_PIXELS} px."
            )
    megapixels = width * height / 1e6
    if megapixels > MAX_EXPORT_MEGAPIXELS:
        raise ExportSizeError(
            f"The image would have {megapixels:.0f} megapixels; at most "
            f"{MAX_EXPORT_MEGAPIXELS} are allowed. Reduce the size or the resolution."
        )


def _check_unit(unit: str) -> None:
    if unit not in ("px", "mm"):
        raise ValueError("unit must be 'px' or 'mm'")
