"""Write a rendered POV-Ray image as PNG, PDF, or JPEG (FR-EXPORT-01).

POV-Ray always writes an 8-bit PNG at the requested pixel size. This module turns that
image into the file the user asked for, without resampling it:

- **PNG**: the rendered file byte for byte; with a resolution, a ``pHYs`` chunk is
  inserted after the header (the image data are not decoded or re-encoded).
- **JPEG**: decoded once and encoded once with the chosen quality. JPEG has no alpha
  channel, so a transparent background is composited over white first. The JFIF
  header carries the resolution.
- **PDF**: one page whose size is the physical size of the image at the chosen
  resolution, with the image embedded losslessly (Flate) at its full pixel size and
  any alpha channel kept as a soft mask. The PDF contains a raster image: it is not a
  vector drawing and does not become sharper when enlarged. PDF page sizes are whole
  PostScript points (1/72 inch), so the page may differ from the exact physical size by
  up to half a point (0.18 mm); the image is centred on it without distortion.

Every format is written to ``<destination>.part``, checked, and then renamed over the
destination, so a failed export never leaves a truncated file under the final name.
Uses Qt's image classes (``QImage``, ``QPdfWriter``), which need no window or display.
"""

from __future__ import annotations

import shutil
import struct
import zlib
from pathlib import Path

from PySide6.QtCore import QMarginsF, QRectF, QSizeF
from PySide6.QtGui import (
    QColor,
    QImage,
    QImageReader,
    QImageWriter,
    QPageLayout,
    QPageSize,
    QPainter,
    QPdfWriter,
)

from ycrystal import __version__
from ycrystal.core.export import MM_PER_INCH, ExportOptions

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"

JPEG_MATTE = QColor(255, 255, 255)
"""Colour that replaces transparent pixels in JPEG files (white)."""

PDF_UNITS_PER_POINT = 100
"""Painter units per PostScript point when placing the image on a PDF page."""


class ExportWriteError(OSError):
    """An exported file could not be written or failed its check; ``str()`` explains it."""


def write_export(
    image: str | Path, destination: str | Path, options: ExportOptions, title: str = ""
) -> Path:
    """Write the rendered PNG ``image`` to ``destination`` in the format of ``options``.

    Parameters
    ----------
    image
        PNG written by POV-Ray (normally in a job directory).
    destination
        File to write; any characters are allowed. Missing parent directories are
        created and an existing file is replaced.
    options
        Format, resolution, and JPEG quality. The pixel size is that of `image`;
        `options` only describes what was requested.
    title
        Document title stored in a PDF.

    Returns
    -------
    pathlib.Path
        `destination` as a ``Path``.

    Raises
    ------
    ExportWriteError
        If the image cannot be read, the file cannot be written, or the written file
        fails its check. The partial ``.part`` file is removed and an existing
        destination is left unchanged.
    """
    image = Path(image)
    destination = Path(destination)
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise ExportWriteError(f"Could not create the folder {destination.parent}: {exc}") from exc
    tmp = destination.with_name(destination.name + ".part")
    try:
        if options.format == "png":
            _write_png(image, tmp, options.dpi)
        elif options.format == "jpeg":
            _write_jpeg(image, tmp, options)
        else:
            _write_pdf(image, tmp, options, title)
        _verify(tmp, image, options.format)
        tmp.replace(destination)
    except ExportWriteError:
        tmp.unlink(missing_ok=True)
        raise
    except OSError as exc:
        tmp.unlink(missing_ok=True)
        raise ExportWriteError(f"Could not write {destination}: {exc}") from exc
    return destination


# ----- PNG ----------------------------------------------------------------------------
def png_with_resolution(data: bytes, dpi: float) -> bytes:
    """Return PNG ``data`` with a ``pHYs`` chunk for ``dpi`` (any old one is replaced).

    Only chunks are rearranged; the compressed image data are unchanged.

    Raises
    ------
    ExportWriteError
        If ``data`` is not a well-formed PNG.
    """
    if not data.startswith(PNG_SIGNATURE):
        raise ExportWriteError("The rendered image is not a PNG file.")
    per_metre = round(dpi / MM_PER_INCH * 1000)
    phys = _png_chunk(b"pHYs", struct.pack(">IIB", per_metre, per_metre, 1))
    out = [PNG_SIGNATURE]
    pos = len(PNG_SIGNATURE)
    while pos < len(data):
        if pos + 8 > len(data):
            raise ExportWriteError("The rendered PNG is truncated.")
        length, kind = struct.unpack(">I4s", data[pos : pos + 8])
        end = pos + 12 + length
        if end > len(data):
            raise ExportWriteError("The rendered PNG is truncated.")
        if kind != b"pHYs":
            out.append(data[pos:end])
        if kind == b"IHDR":
            out.append(phys)
        pos = end
        if kind == b"IEND":
            break
    else:
        raise ExportWriteError("The rendered PNG has no end marker.")
    return b"".join(out)


def png_resolution(data: bytes) -> float | None:
    """Return the resolution (dpi) stored in a PNG's ``pHYs`` chunk, or ``None``."""
    pos = len(PNG_SIGNATURE)
    while pos + 8 <= len(data):
        length, kind = struct.unpack(">I4s", data[pos : pos + 8])
        if kind == b"pHYs":
            x, _y, unit = struct.unpack(">IIB", data[pos + 8 : pos + 17])
            return x * MM_PER_INCH / 1000 if unit == 1 else None
        pos += 12 + length
    return None


def _png_chunk(kind: bytes, payload: bytes) -> bytes:
    crc = zlib.crc32(kind + payload) & 0xFFFFFFFF
    return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", crc)


def _write_png(image: Path, tmp: Path, dpi: float | None) -> None:
    if dpi is None:
        shutil.copyfile(image, tmp)
        return
    tmp.write_bytes(png_with_resolution(image.read_bytes(), dpi))


# ----- JPEG ---------------------------------------------------------------------------
def _load(image: Path) -> QImage:
    loaded = QImage(str(image))
    if loaded.isNull():
        raise ExportWriteError(f"Could not read the rendered image {image.name}.")
    return loaded


def opaque_image(image: QImage, matte: QColor = JPEG_MATTE) -> QImage:
    """Return ``image`` without alpha: transparent pixels composited over ``matte``.

    Partially transparent edge pixels (antialiasing) blend with ``matte``, as they
    would on a page of that colour. Images without alpha are only converted to 32-bit
    RGB.
    """
    if not image.hasAlphaChannel():
        return image.convertToFormat(QImage.Format.Format_RGB32)
    result = QImage(image.size(), QImage.Format.Format_RGB32)
    result.fill(matte)
    painter = QPainter(result)
    painter.drawImage(0, 0, image)
    painter.end()
    return result


def _write_jpeg(image: Path, tmp: Path, options: ExportOptions) -> None:
    opaque = opaque_image(_load(image))
    if options.dpi is not None:
        per_metre = round(options.dpi / MM_PER_INCH * 1000)
        opaque.setDotsPerMeterX(per_metre)
        opaque.setDotsPerMeterY(per_metre)
    writer = QImageWriter(str(tmp), b"jpeg")
    writer.setQuality(options.jpeg_quality)
    if not writer.write(opaque):
        raise ExportWriteError(f"Could not write the JPEG file: {writer.errorString()}")


# ----- PDF ----------------------------------------------------------------------------
def _write_pdf(image: Path, tmp: Path, options: ExportOptions, title: str) -> None:
    picture = _load(image)
    if not picture.hasAlphaChannel():
        picture = picture.convertToFormat(QImage.Format.Format_RGB32)
    width_mm, height_mm = options.physical_size_mm()
    # Physical size of the rendered image (its own pixels at the requested resolution).
    width_mm *= picture.width() / options.width
    height_mm *= picture.height() / options.height
    writer = QPdfWriter(str(tmp))
    writer.setCreator(f"Ycrystal {__version__}")
    if title:
        writer.setTitle(title)
    page = QPageSize(
        QSizeF(width_mm, height_mm),
        QPageSize.Unit.Millimeter,
        "",
        QPageSize.SizeMatchPolicy.ExactMatch,
    )
    layout = QPageLayout(page, QPageLayout.Orientation.Portrait, QMarginsF(0, 0, 0, 0))
    if not writer.setPageLayout(layout):
        raise ExportWriteError("The PDF page size is not supported.")
    writer.setResolution(72 * PDF_UNITS_PER_POINT)
    painter = QPainter()
    if not painter.begin(writer):
        raise ExportWriteError("Could not create the PDF file (is the folder writable?).")
    try:
        painter.setRenderHint(QPainter.RenderHint.LosslessImageRendering)
        painter.drawImage(
            fitted_rect(writer.width(), writer.height(), picture.width(), picture.height()),
            picture,
        )
    finally:
        ended = painter.end()
    if not ended:
        raise ExportWriteError("Could not finish the PDF file.")


def fitted_rect(page_w: float, page_h: float, image_w: int, image_h: int) -> QRectF:
    """Return the largest rectangle of the image's shape centred on the page.

    >>> fitted_rect(200, 100, 400, 100).getRect()
    (0.0, 25.0, 200.0, 50.0)
    """
    scale = min(page_w / image_w, page_h / image_h)
    width, height = image_w * scale, image_h * scale
    return QRectF((page_w - width) / 2, (page_h - height) / 2, width, height)


# ----- checks -------------------------------------------------------------------------
def _verify(path: Path, source: Path, fmt: str) -> None:
    """Check that ``path`` is a complete file of format ``fmt`` (as large as ``source``)."""
    if not path.is_file() or path.stat().st_size == 0:
        raise ExportWriteError("The exported file is empty.")
    if fmt == "pdf":
        data = path.read_bytes()
        if not data.startswith(b"%PDF-") or b"%%EOF" not in data[-64:]:
            raise ExportWriteError("The PDF file is incomplete.")
        return
    reader = QImageReader(str(path), b"png" if fmt == "png" else b"jpeg")
    size = reader.size()
    expected = QImageReader(str(source)).size()
    if not reader.canRead() or size != expected:
        raise ExportWriteError(f"The written {fmt.upper()} file cannot be read back.")
