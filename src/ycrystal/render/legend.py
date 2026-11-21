"""Paint the element legend onto images (FR-LEGEND-01).

The legend is drawn in two dimensions with Qt's ``QPainter`` and is independent of the
three-dimensional scene: POV-Ray renders the structure exactly as without a legend, and
[`draw_legend_on_file`][ycrystal.render.legend.draw_legend_on_file] then paints the
legend onto the rendered PNG at its full pixel size (in
[`finish_job`][ycrystal.render.jobs.finish_job]). PNG, PDF, and JPEG exports, the
preview, and the command line all start from that image. The live view draws the same
legend with [`legend_overlay`][ycrystal.render.legend.legend_overlay], so what the frame
shows is what the image gets.

To stay sharp and identical at every size, the layout is computed once at a reference
text size and scaled to the image: the text height is a fixed fraction of the image
height (see [`LegendSettings`][ycrystal.core.legend.LegendSettings]). Symbols are drawn
as the outlines of their glyphs, antialiased, without font hinting or subpixel (coloured)
antialiasing, so they look the same in a 480-pixel preview and a 6000-pixel export, and
the edges carry no colour fringes in print.

Painting text needs a ``QGuiApplication``. In the window there is one; the command line
creates one without windows when the first legend is drawn
([`ensure_gui_application`][ycrystal.render.legend.ensure_gui_application]).
"""

from __future__ import annotations

import math
import os
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QFontDatabase,
    QFontMetricsF,
    QGuiApplication,
    QImage,
    QImageWriter,
    QPainter,
    QPainterPath,
    QPen,
    QRadialGradient,
)

from ycrystal.core.legend import LegendEntry, LegendSettings

DEFAULT_FONT_FAMILIES = ("Arial", "Helvetica", "Liberation Sans", "Nimbus Sans", "DejaVu Sans")
"""Families tried in turn for the default font (an empty ``font_family``): Arial or
Helvetica, as many journals ask for in figures, or a metric-compatible free family.
If none is installed, Qt's default sans-serif family is used."""

REFERENCE_SIZE = 100.0
"""Text pixel size at which the layout is computed before it is scaled to the image."""

LABEL_GAP = 0.35
"""Gap between a marker and its symbol, in multiples of the text height."""

PADDING = 0.45
"""Space between the legend and the edge of its background box (text heights)."""

CORNER_RADIUS = 0.3
"""Corner radius of the background box (text heights)."""

OUTLINE = 0.04
"""Width of a marker's outline, as a fraction of the marker diameter."""

_application: QGuiApplication | None = None  # created for the command line, kept alive


class LegendError(RuntimeError):
    """The legend could not be drawn; ``str()`` explains why."""


def ensure_gui_application() -> None:
    """Make sure a ``QGuiApplication`` exists, as text drawing needs one.

    In the window, the application exists and nothing happens. Otherwise (the command
    line, scripts) one is created without windows, with the platform plug-in chosen by
    ``ycrystal.gui.native.painting_platform`` (``offscreen`` on Linux and macOS, the
    native one on Windows) unless ``QT_QPA_PLATFORM`` names one.

    Raises
    ------
    LegendError
        If only a non-graphical ``QCoreApplication`` exists (text cannot be drawn then).
    """
    global _application
    from PySide6.QtCore import QCoreApplication

    existing = QCoreApplication.instance()
    if existing is not None:
        if not isinstance(existing, QGuiApplication):
            raise LegendError("Text cannot be drawn in a program without Qt GUI support.")
        return
    from ycrystal.gui.native import painting_platform

    arguments = ["ycrystal"]
    platform = painting_platform()
    if platform and not os.environ.get("QT_QPA_PLATFORM"):
        arguments += ["-platform", platform]
    _application = QGuiApplication(arguments)


def resolved_font_family(name: str = "") -> str:
    """Return the font family that draws the legend for the setting ``name``.

    An empty name selects the first installed family of
    [`DEFAULT_FONT_FAMILIES`][ycrystal.render.legend.DEFAULT_FONT_FAMILIES]. A name that
    is not installed is returned as it is: Qt then draws with a similar family.
    """
    if name:
        return name
    installed = set(QFontDatabase.families())
    for family in DEFAULT_FONT_FAMILIES:
        if family in installed:
            return family
    return QFontDatabase.systemFont(QFontDatabase.SystemFont.GeneralFont).family()


def legend_font(name: str = "") -> QFont:
    """Return the legend's font at [`REFERENCE_SIZE`][ycrystal.render.legend.REFERENCE_SIZE].

    Hinting and subpixel antialiasing are off, so that the glyph outlines scale exactly.
    """
    font = QFont(resolved_font_family(name))
    font.setStyleHint(QFont.StyleHint.SansSerif)
    font.setPixelSize(int(REFERENCE_SIZE))
    font.setHintingPreference(QFont.HintingPreference.PreferNoHinting)
    font.setStyleStrategy(
        QFont.StyleStrategy.PreferAntialias | QFont.StyleStrategy.NoSubpixelAntialias
    )
    font.setKerning(True)
    return font


@dataclass(frozen=True)
class LegendLayout:
    """The legend laid out for one image size.

    Markers and labels are in reference units (text height
    [`REFERENCE_SIZE`][ycrystal.render.legend.REFERENCE_SIZE]); ``rect`` is where the
    legend's box lands in the image, in image pixels.

    Attributes
    ----------
    rect
        Box of the legend in image pixels (top-left origin), including the background
        padding when there is a background.
    scale
        Image pixels per reference unit.
    box
        The same box in reference units.
    markers
        ``(centre, radius, colour)`` of each marker, in reference units.
    labels
        Glyph outlines of each symbol, positioned in reference units.
    """

    rect: QRectF
    scale: float
    box: QRectF
    markers: tuple[tuple[QPointF, float, tuple[float, float, float]], ...]
    labels: tuple[QPainterPath, ...]

    def to_image(self, point: QPointF) -> QPointF:
        """Map a point from reference units to image pixels."""
        return QPointF(
            self.rect.left() + (point.x() - self.box.left()) * self.scale,
            self.rect.top() + (point.y() - self.box.top()) * self.scale,
        )


def legend_layout(
    entries: Sequence[LegendEntry], settings: LegendSettings, width: float, height: float
) -> LegendLayout | None:
    """Lay out the legend for an image of ``width`` × ``height`` pixels.

    Returns ``None`` when there is nothing to draw (no entries). The legend is not
    clipped here: a legend larger than the image extends beyond it.
    """
    if not entries or width <= 0 or height <= 0:
        return None
    ensure_gui_application()
    font = legend_font(settings.font_family)
    metrics = QFontMetricsF(font)
    cap = metrics.capHeight()
    diameter = settings.marker_size * REFERENCE_SIZE
    gap = LABEL_GAP * REFERENCE_SIZE
    spacing = settings.spacing * REFERENCE_SIZE
    row = max(diameter, cap)
    markers, labels = [], []
    content = QRectF()
    cursor = 0.0
    for entry in entries:
        path = QPainterPath()
        path.addText(0.0, 0.0, font, entry.element)
        ink = path.boundingRect()
        if settings.layout == "horizontal":
            left, centre_y = cursor, row / 2
        else:
            left, centre_y = 0.0, cursor + row / 2
        centre = QPointF(left + diameter / 2, centre_y)
        # The symbol starts after the marker; its capitals are centred on the marker.
        path.translate(left + diameter + gap - ink.left(), centre_y + cap / 2)
        markers.append((centre, diameter / 2, entry.color))
        labels.append(path)
        half = diameter / 2 * (1 + OUTLINE)
        content = content.united(
            QRectF(centre.x() - half, centre.y() - half, 2 * half, 2 * half)
        ).united(path.boundingRect())
        if settings.layout == "horizontal":
            cursor += diameter + gap + ink.width() + spacing
        else:
            cursor += row + spacing
    pad = PADDING * REFERENCE_SIZE if settings.background else 0.0
    box = content.adjusted(-pad, -pad, pad, pad)
    font_px = settings.font_size / 100.0 * height
    scale = font_px / REFERENCE_SIZE
    w, h = box.width() * scale, box.height() * scale
    margin = settings.margin * font_px
    if settings.position == "bottom":
        left, top = (width - w) / 2, height - margin - h
    elif settings.position == "top":
        left, top = (width - w) / 2, margin
    elif settings.position == "left":
        left, top = margin, (height - h) / 2
    elif settings.position == "right":
        left, top = width - margin - w, (height - h) / 2
    else:  # custom: centre at (x, y), moved inside the image where it fits
        left = _inside(settings.x * width - w / 2, w, width)
        top = _inside(settings.y * height - h / 2, h, height)
    return LegendLayout(QRectF(left, top, w, h), scale, box, tuple(markers), tuple(labels))


MIN_FREE_FRACTION = 0.2
"""Smallest share of the frame width or height left for the structure by
[`legend_fit_region`][ycrystal.render.legend.legend_fit_region]; a legend that leaves
less reserves nothing."""


def legend_fit_region(
    entries: Sequence[LegendEntry], settings: LegendSettings, aspect: float
) -> tuple[float, float, float, float] | None:
    """Return the part of the frame that a legend at an edge leaves for the structure.

    The region is ``(left, top, right, bottom)`` in fractions of the frame (top-left
    origin), as [`Camera.fitted`][ycrystal.core.camera.Camera.fitted] takes it: the
    frame without the legend and, towards the structure, a gap as wide as the legend's
    margin. Fitting into it puts the structure beside the legend instead of under it.

    Returns
    -------
    tuple or None
        ``None`` (the whole frame) when the legend is disabled, has no entries, is at a
        custom position, or would leave less than
        [`MIN_FREE_FRACTION`][ycrystal.render.legend.MIN_FREE_FRACTION] of the frame.
    """
    if not settings.enabled or settings.position == "custom" or aspect <= 0:
        return None
    height = 1000.0
    width = height * aspect
    layout = legend_layout(entries, settings, width, height)
    if layout is None:
        return None
    gap = settings.margin * settings.font_size / 100.0 * height
    rect = layout.rect
    left, top, right, bottom = 0.0, 0.0, 1.0, 1.0
    if settings.position == "bottom":
        bottom = (rect.top() - gap) / height
    elif settings.position == "top":
        top = (rect.bottom() + gap) / height
    elif settings.position == "left":
        left = (rect.right() + gap) / width
    else:
        right = (rect.left() - gap) / width
    if right - left < MIN_FREE_FRACTION or bottom - top < MIN_FREE_FRACTION:
        return None
    return (left, top, right, bottom)


def _inside(start: float, size: float, limit: float) -> float:
    if size >= limit:
        return (limit - size) / 2
    return min(max(start, 0.0), limit - size)


def _color(rgb: Sequence[float], alpha: float = 1.0) -> QColor:
    return QColor.fromRgbF(float(rgb[0]), float(rgb[1]), float(rgb[2]), float(alpha))


def _mix(rgb: Sequence[float], other: float, amount: float) -> QColor:
    """Blend a colour towards the grey level ``other`` (1 white, 0 black)."""
    return _color([c + (other - c) * amount for c in rgb])


def paint_legend(painter: QPainter, layout: LegendLayout, settings: LegendSettings) -> None:
    """Paint a laid-out legend with ``painter`` (in image pixels)."""
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.translate(layout.rect.left(), layout.rect.top())
    painter.scale(layout.scale, layout.scale)
    painter.translate(-layout.box.left(), -layout.box.top())
    if settings.background:
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(_color(settings.background_color, settings.background_opacity))
        radius = CORNER_RADIUS * REFERENCE_SIZE
        painter.drawRoundedRect(layout.box, radius, radius)
    for centre, radius, rgb in layout.markers:
        if settings.marker_style == "sphere":
            # A ball lit from the upper left, as the default key light.
            focal = QPointF(centre.x() - 0.35 * radius, centre.y() - 0.4 * radius)
            gradient = QRadialGradient(centre, radius, focal)
            gradient.setColorAt(0.0, _mix(rgb, 1.0, 0.7))
            gradient.setColorAt(0.3, _mix(rgb, 1.0, 0.2))
            gradient.setColorAt(0.75, _color(rgb))
            gradient.setColorAt(1.0, _mix(rgb, 0.0, 0.35))
            brush = QBrush(gradient)
        else:
            brush = QBrush(_color(rgb))
        pen = QPen(_mix(rgb, 0.0, 0.5), 2 * radius * OUTLINE)
        painter.setPen(pen)
        painter.setBrush(brush)
        inner = radius * (1 - OUTLINE / 2)  # the outline stays within the diameter
        painter.drawEllipse(centre, inner, inner)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(_color(settings.text_color))
    for path in layout.labels:
        painter.drawPath(path)
    painter.restore()


def legend_overlay(
    entries: Sequence[LegendEntry], settings: LegendSettings, width: float, height: float
) -> tuple[QImage, int, int] | None:
    """Return the legend of a ``width`` × ``height`` image as a small transparent image.

    For the live view: the image covers only the legend (within the image bounds), and
    ``(x, y)`` is its top-left pixel in the ``width`` × ``height`` image.

    Returns
    -------
    tuple or None
        ``(image, x, y)`` with an RGBA image (not premultiplied), or ``None`` when
        nothing would be visible.
    """
    if not settings.enabled:
        return None
    layout = legend_layout(entries, settings, width, height)
    if layout is None:
        return None
    rect = layout.rect
    x0, y0 = max(0, math.floor(rect.left())), max(0, math.floor(rect.top()))
    x1 = min(math.ceil(width), math.ceil(rect.right()) + 1)
    y1 = min(math.ceil(height), math.ceil(rect.bottom()) + 1)
    if x1 <= x0 or y1 <= y0:
        return None
    image = QImage(x1 - x0, y1 - y0, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.translate(-x0, -y0)
    paint_legend(painter, layout, settings)
    painter.end()
    return image.convertToFormat(QImage.Format.Format_RGBA8888), x0, y0


def draw_legend_on_file(
    path: str | Path, entries: Sequence[LegendEntry], settings: LegendSettings
) -> bool:
    """Paint the legend onto the PNG at ``path``, in place, at its full pixel size.

    Pixels outside the legend keep their values, and so does the alpha channel of a
    transparent background (the legend is painted over it). Text chunks are kept; a
    resolution chunk is written only if the file had one.

    Returns
    -------
    bool
        Whether a legend was drawn (``False`` when disabled or without entries; the
        file is then not touched).

    Raises
    ------
    LegendError
        If the image cannot be read or written.
    """
    if not settings.enabled or not entries:
        return False
    path = Path(path)
    ensure_gui_application()
    image = QImage(str(path))
    if image.isNull():
        raise LegendError(f"Could not read the rendered image {path.name}.")
    if image.format() not in (
        QImage.Format.Format_RGB32,
        QImage.Format.Format_ARGB32,
        QImage.Format.Format_ARGB32_Premultiplied,
        QImage.Format.Format_RGBA64,
        QImage.Format.Format_RGBX64,
    ):
        alpha = image.hasAlphaChannel()
        image = image.convertToFormat(
            QImage.Format.Format_ARGB32 if alpha else QImage.Format.Format_RGB32
        )
    layout = legend_layout(entries, settings, image.width(), image.height())
    if layout is None:
        return False
    painter = QPainter(image)
    paint_legend(painter, layout, settings)
    painter.end()
    # Encoded in memory: a file written by QImageWriter stays open (and so cannot be
    # renamed on Windows) until the writer is destroyed.
    from PySide6.QtCore import QBuffer, QIODevice

    from ycrystal.render.formats import png_resolution, png_without_resolution

    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    writer = QImageWriter(buffer, b"png")
    if not writer.write(image):
        raise LegendError(f"Could not encode the image with its legend: {writer.errorString()}")
    del writer
    data = bytes(buffer.data())
    buffer.close()
    if png_resolution(path.read_bytes()) is None:
        data = png_without_resolution(data)
    tmp = path.with_name(path.name + ".legend")
    tmp.write_bytes(data)
    tmp.replace(path)
    return True
