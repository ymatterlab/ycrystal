"""FR-EXPORT-01 without a window or POV-Ray: sizes, presets, and the PNG/PDF/JPEG writers."""

import re
import struct
import zlib

import pytest
from PIL import Image

from ycrystal.core import export as ex
from ycrystal.core.export import ExportOptions, ExportSizeError
from ycrystal.render.formats import (
    ExportWriteError,
    png_resolution,
    png_with_resolution,
    write_export,
)

POINTS_PER_MM = 72 / 25.4


def rendered_png(path, size=(120, 80), transparent=False):
    """A stand-in for POV-Ray's output: a red block on blue (or on transparency)."""
    background = (0, 0, 0, 0) if transparent else (20, 40, 200, 255)
    image = Image.new("RGBA" if transparent else "RGB", size, background[: 4 if transparent else 3])
    w, h = size
    block = (200, 30, 30, 255) if transparent else (200, 30, 30)
    image.paste(block, (w // 4, h // 4, 3 * w // 4, 3 * h // 4))
    image.save(path)
    return path


def pdf_media_box(data: bytes) -> tuple[float, float]:
    x0, y0, x1, y1 = (float(v) for v in re.search(rb"/MediaBox \[([^\]]*)\]", data)[1].split())
    return x1 - x0, y1 - y0


# ----- sizes and presets ----------------------------------------------------------------------
def test_publication_presets_give_the_documented_pixel_widths():
    single, double = ex.size_preset("single"), ex.size_preset("double")
    assert (single.width_mm, single.dpi, double.width_mm, double.dpi) == (85, 600, 180, 600)
    assert ex.pixels_from_mm(single.width_mm, single.dpi) == 2008  # 85 / 25.4 × 600 = 2007.9
    assert ex.pixels_from_mm(double.width_mm, double.dpi) == 4252  # 4251.97
    with pytest.raises(KeyError):
        ex.size_preset("custom")


@pytest.mark.parametrize(
    ("ratio", "expected"),
    [(1.5, (2008, 1339)), (1.0, (2008, 2008)), (2 / 3, (2008, 3012)), (16 / 9, (2008, 1129))],
)
def test_height_follows_the_frame_shape(ratio, expected):
    height_mm = ex.linked_height(85, ratio, "mm")
    width, height = ex.figure_pixels("mm", 85, height_mm, 600)
    assert (width, height) == expected
    assert width / height == pytest.approx(ratio, rel=1 / min(expected))  # within a pixel


@pytest.mark.parametrize(
    ("unit", "width", "dpi", "pixels"),
    [
        ("mm", 120, 1200, 5669),  # above 600 dpi: no artificial cap
        ("mm", 50, 450, 886),
        ("mm", 85, 72, 241),
        ("px", 1234, 300, 1234),  # pixels ignore the resolution
        ("px", 1234, 2400, 1234),
    ],
)
def test_custom_width_and_resolution_combinations(unit, width, dpi, pixels):
    assert ex.figure_pixels(unit, width, ex.linked_height(width, 1.25, unit), dpi)[0] == pixels


def test_units_convert_both_ways_without_drift():
    assert ex.convert_length(85, "mm", "px", 600) == 2008
    assert ex.convert_length(2008, "px", "mm", 600) == pytest.approx(2008 / 600 * 25.4)
    assert ex.convert_length(ex.convert_length(2008, "px", "mm", 600), "mm", "px", 600) == 2008
    assert ex.convert_length(85, "mm", "mm", 600) == 85
    assert ex.mm_from_pixels(600, 600) == pytest.approx(25.4)
    assert ex.linked_height(1000, 1.5, "px") == 667  # whole pixels, half up
    assert ex.linked_width(667, 1.5, "px") == 1001  # 1000.5, half up
    with pytest.raises(ValueError):
        ex.convert_length(1, "cm", "px", 300)
    with pytest.raises(ValueError):
        ex.linked_height(1, 0, "px")


def test_options_report_the_physical_size():
    options = ExportOptions("pdf", 2008, 1339, dpi=600)
    width_mm, height_mm = options.physical_size_mm()
    assert width_mm == pytest.approx(85.005, abs=1e-3)
    assert height_mm == pytest.approx(56.684, abs=1e-3)
    assert ExportOptions("png", 100, 100).physical_size_mm() is None


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"width": 15}, "between 16 and 20000"),
        ({"height": 20001}, "between 16 and 20000"),
        ({"width": 15000, "height": 15000}, "megapixels"),
        ({"dpi": 0}, "resolution"),
        ({"dpi": 100_001}, "resolution"),
        ({"jpeg_quality": 0}, "quality"),
        ({"jpeg_quality": 101}, "quality"),
        ({"format": "pdf"}, "needs a resolution"),
        ({"format": "pdf", "width": 20000, "dpi": 50}, "PDF pages"),
    ],
)
def test_invalid_settings_are_rejected_with_an_explanation(kwargs, message):
    values = {"format": "png", "width": 1000, "height": 800, **kwargs}
    with pytest.raises(ExportSizeError, match=message):
        ExportOptions(**values)


def test_valid_extremes_are_accepted():
    ExportOptions("png", 16, 16, dpi=1)
    ExportOptions("jpeg", 20000, 7000, dpi=100_000, jpeg_quality=1)
    ExportOptions("pdf", 4252, 3000, dpi=2400, jpeg_quality=100)
    with pytest.raises(ValueError, match="unknown export format"):
        ExportOptions("tiff", 100, 100)


def test_file_suffixes_follow_the_format():
    assert ex.path_for_format("fig.png", "pdf").name == "fig.pdf"
    assert ex.path_for_format("fig.PDF", "pdf").name == "fig.PDF"
    assert ex.path_for_format("fig.jpeg", "jpeg").name == "fig.jpeg"
    assert ex.path_for_format("fig.jpg", "png").name == "fig.png"
    assert ex.path_for_format("SrTiO3 v1.2", "jpeg").name == "SrTiO3 v1.2.jpg"
    assert ex.format_for_path("a.JPG") == "jpeg" and ex.format_for_path("a.tif") is None
    assert ex.format_label("pdf") == "PDF document"


# ----- PNG --------------------------------------------------------------------------------------
def test_png_without_resolution_is_copied_byte_for_byte(tmp_path):
    source = rendered_png(tmp_path / "scene.png")
    out = write_export(source, tmp_path / "out.png", ExportOptions("png", 120, 80))
    assert out.read_bytes() == source.read_bytes()
    assert not (tmp_path / "out.png.part").exists()


def test_png_resolution_is_added_without_touching_the_pixels(tmp_path):
    source = rendered_png(tmp_path / "scene.png", transparent=True)
    out = write_export(source, tmp_path / "out.png", ExportOptions("png", 120, 80, dpi=600))
    assert png_resolution(out.read_bytes()) == pytest.approx(600, abs=0.05)
    with Image.open(out) as written, Image.open(source) as original:
        assert written.size == (120, 80) and written.mode == "RGBA"
        assert written.info["dpi"] == pytest.approx((600, 600), abs=0.05)
        assert written.tobytes() == original.tobytes()
    # The compressed image data are the same bytes: only a chunk was inserted.
    assert re.findall(rb"IDAT.*?IEND", out.read_bytes(), re.S) == re.findall(
        rb"IDAT.*?IEND", source.read_bytes(), re.S
    )


def test_an_existing_png_resolution_is_replaced(tmp_path):
    source = tmp_path / "with-dpi.png"
    Image.new("RGB", (20, 20)).save(source, dpi=(72, 72))
    data = png_with_resolution(source.read_bytes(), 300)
    assert data.count(b"pHYs") == 1
    assert png_resolution(data) == pytest.approx(300, abs=0.01)


def test_damaged_png_is_reported(tmp_path):
    with pytest.raises(ExportWriteError, match="not a PNG"):
        png_with_resolution(b"GIF89a", 300)
    good = rendered_png(tmp_path / "scene.png").read_bytes()
    with pytest.raises(ExportWriteError, match="truncated|end marker"):
        png_with_resolution(good[:-20], 300)
    chunk = b"tEXt" + b"x"
    broken = good[:33] + struct.pack(">I", 1) + chunk + struct.pack(">I", zlib.crc32(chunk))
    with pytest.raises(ExportWriteError):
        png_with_resolution(broken, 300)


# ----- JPEG -------------------------------------------------------------------------------------
def test_jpeg_has_the_rendered_size_resolution_and_colours(tmp_path):
    source = rendered_png(tmp_path / "scene.png")
    out = write_export(source, tmp_path / "out.jpg", ExportOptions("jpeg", 120, 80, dpi=300))
    with Image.open(out) as image:
        assert image.format == "JPEG" and image.mode == "RGB" and image.size == (120, 80)
        assert image.info["dpi"] == pytest.approx((300, 300), abs=0.5)
        assert image.getpixel((60, 40)) == pytest.approx((200, 30, 30), abs=6)
        assert image.getpixel((2, 2)) == pytest.approx((20, 40, 200), abs=6)


def test_jpeg_quality_changes_the_file(tmp_path):
    source = tmp_path / "noise.png"
    Image.effect_noise((200, 150), 60).convert("RGB").save(source)
    sizes = {}
    for quality in (10, 95, 100):
        out = write_export(
            source,
            tmp_path / f"q{quality}.jpg",
            ExportOptions("jpeg", 200, 150, jpeg_quality=quality),
        )
        sizes[quality] = out.stat().st_size
    assert sizes[10] < sizes[95] < sizes[100]


def test_jpeg_fills_transparency_with_white(tmp_path):
    source = rendered_png(tmp_path / "scene.png", transparent=True)
    out = write_export(source, tmp_path / "out.jpeg", ExportOptions("jpeg", 120, 80))
    with Image.open(out) as image:
        assert image.mode == "RGB"
        assert image.getpixel((2, 2)) == pytest.approx((255, 255, 255), abs=3)
        assert image.getpixel((60, 40)) == pytest.approx((200, 30, 30), abs=6)


def test_jpeg_blends_partly_transparent_edges_with_white(tmp_path):
    source = tmp_path / "half.png"
    Image.new("RGBA", (32, 32), (0, 0, 0, 128)).save(source)
    out = write_export(source, tmp_path / "half.jpg", ExportOptions("jpeg", 32, 32))
    with Image.open(out) as image:
        assert image.getpixel((16, 16)) == pytest.approx((127, 127, 127), abs=4)


# ----- PDF --------------------------------------------------------------------------------------
@pytest.mark.parametrize(("size", "dpi"), [((2008, 1339), 600), ((300, 450), 150)])
def test_pdf_page_has_the_physical_size_and_the_full_image(tmp_path, size, dpi):
    source = rendered_png(tmp_path / "scene.png", size=size)
    options = ExportOptions("pdf", *size, dpi=dpi)
    out = write_export(source, tmp_path / "figure.pdf", options, title="Ycrystal: SrTiO3")
    data = out.read_bytes()
    assert data.startswith(b"%PDF-") and b"%%EOF" in data[-64:]
    width_mm, height_mm = options.physical_size_mm()
    page_w, page_h = pdf_media_box(data)
    # Qt writes whole points: within half a point (0.18 mm) of the physical size.
    assert page_w == pytest.approx(width_mm * POINTS_PER_MM, abs=0.5)
    assert page_h == pytest.approx(height_mm * POINTS_PER_MM, abs=0.5)
    # The image is embedded once at its rendered pixel size, losslessly.
    assert f"/Width {size[0]}".encode() in data and f"/Height {size[1]}".encode() in data
    assert b"/DCTDecode" not in data
    assert b"Ycrystal: SrTiO3" in data or "Ycrystal: SrTiO3".encode("utf-16-be") in data


def test_pdf_keeps_a_transparent_background(tmp_path):
    source = rendered_png(tmp_path / "scene.png", transparent=True)
    data = write_export(
        source, tmp_path / "t.pdf", ExportOptions("pdf", 120, 80, dpi=300)
    ).read_bytes()
    assert b"/SMask" in data


# ----- files ------------------------------------------------------------------------------------
@pytest.mark.parametrize("fmt", ["png", "pdf", "jpeg"])
def test_paths_with_spaces_and_non_ascii_characters(tmp_path, fmt):
    source = rendered_png(tmp_path / "scene.png")
    folder = tmp_path / "Figures für Ångström ✓" / "new folder"
    destination = ex.path_for_format(folder / "SrTiO₃ figure 1", fmt)
    out = write_export(source, destination, ExportOptions(fmt, 120, 80, dpi=300))
    assert out == destination and out.is_file() and out.stat().st_size > 0
    assert sorted(p.name for p in folder.iterdir()) == [destination.name]


@pytest.mark.parametrize("fmt", ["png", "pdf", "jpeg"])
def test_write_errors_leave_no_partial_file(tmp_path, fmt):
    source = rendered_png(tmp_path / "scene.png")
    blocked = tmp_path / f"figure.{fmt}"
    blocked.mkdir()  # a folder where the file should go: renaming onto it fails
    with pytest.raises(ExportWriteError):
        write_export(source, blocked, ExportOptions(fmt, 120, 80, dpi=300))
    assert blocked.is_dir()
    assert not list(tmp_path.glob("*.part"))


@pytest.mark.parametrize("fmt", ["png", "pdf", "jpeg"])
def test_a_failed_export_keeps_the_previous_file(tmp_path, fmt):
    destination = tmp_path / f"figure.{fmt}"
    destination.write_bytes(b"previous")
    damaged = tmp_path / "damaged.png"
    damaged.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 10)
    with pytest.raises(ExportWriteError):
        write_export(damaged, destination, ExportOptions(fmt, 120, 80, dpi=300))
    assert destination.read_bytes() == b"previous"
    assert not list(tmp_path.glob("*.part"))
