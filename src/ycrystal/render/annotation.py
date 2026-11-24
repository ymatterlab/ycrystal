"""Lay out and paint frame-anchored text for the live view and rendered images."""

from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtCore import QPointF, QRect, Qt
from PySide6.QtGui import QColor, QFontMetricsF, QImage, QPainter, QPainterPath, QTransform

from ycrystal.core.annotation import TextAnnotation


def annotation_paths(
    annotations: Sequence[TextAnnotation], width: int, height: int
) -> list[tuple[QPainterPath, QColor]]:
    """Lay out enabled text as coloured glyph paths in output pixel coordinates."""
    from ycrystal.render.legend import REFERENCE_SIZE, legend_font

    paths = []
    if width <= 0 or height <= 0:
        return paths
    for annotation in annotations:
        if not annotation.enabled:
            continue
        font = legend_font(annotation.font_family)
        font.setBold(annotation.bold)
        metrics = QFontMetricsF(font)
        scale = height * annotation.font_size / (100 * REFERENCE_SIZE)
        x = width * annotation.x / scale
        baseline = height * annotation.y / scale + metrics.ascent()
        align = {"left": 0.0, "centre": 0.5, "right": 1.0}[annotation.alignment]
        path = QPainterPath()
        for index, line in enumerate(annotation.text.splitlines()):
            left = x - align * metrics.horizontalAdvance(line)
            path.addText(QPointF(left, baseline + index * metrics.lineSpacing()), font, line)
        path = QTransform.fromScale(scale, scale).map(path)
        if not path.isEmpty():
            paths.append((path, QColor.fromRgbF(*annotation.color)))
    return paths


def paint_annotations(painter: QPainter, paths: Sequence[tuple[QPainterPath, QColor]]) -> None:
    """Draw a sequence of glyph paths in their stacking order."""
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setPen(Qt.PenStyle.NoPen)
    for path, color in paths:
        painter.setBrush(color)
        painter.drawPath(path)
    painter.restore()


def annotation_overlay(
    annotations: Sequence[TextAnnotation], width: int, height: int
) -> tuple[QImage, int, int] | None:
    """Return a clipped RGBA overlay and its top-left pixel in the output frame."""
    paths = annotation_paths(annotations, width, height)
    rect = QRect()
    for path, _ in paths:
        rect = rect.united(path.boundingRect().toAlignedRect())
    rect = rect.adjusted(-1, -1, 1, 1).intersected(QRect(0, 0, width, height))
    if not paths or rect.isEmpty():
        return None
    image = QImage(rect.size(), QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.translate(-rect.x(), -rect.y())
    paint_annotations(painter, paths)
    painter.end()
    return image.convertToFormat(QImage.Format.Format_RGBA8888), rect.x(), rect.y()
