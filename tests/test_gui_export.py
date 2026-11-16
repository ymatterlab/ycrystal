"""FR-EXPORT-01 in the window: the Render Image dialog and PNG/PDF/JPEG renders."""

import re

import pytest
from PIL import Image

from test_export import POINTS_PER_MM, pdf_media_box
from test_gui_render import make_window
from test_render_queue import fake_povray
from ycrystal.core.export import ExportOptions, pixels_from_mm
from ycrystal.gui.export_dialog import ExportChoice, ExportDialog
from ycrystal.gui.main_window import SETTINGS_POVRAY, MainWindow, _same_camera
from ycrystal.render.formats import png_resolution

pytestmark = pytest.mark.gui


@pytest.fixture
def window(qtbot):
    win = make_window(qtbot)
    yield win
    win.close()


def make_dialog(qtbot, tmp_path, output=(1200, 800), transparent=False, **choice):
    choice.setdefault("path", tmp_path / "figure.png")
    dialog = ExportDialog(ExportChoice(**choice).fitted(output), output, transparent)
    qtbot.addWidget(dialog)
    return dialog


def select(combo, key):
    combo.setCurrentIndex(combo.findData(key))


# ----- dialog -----------------------------------------------------------------------------------
def test_default_is_png_at_the_output_size(qtbot, tmp_path):
    dialog = make_dialog(qtbot, tmp_path)
    options = dialog.options()
    assert (options.format, options.width, options.height) == ("png", 1200, 800)
    assert dialog.mode_combo.currentData() == "output" and dialog.lock_check.isChecked()
    assert dialog.destination() == tmp_path / "figure.png"
    assert not dialog.jpeg_group.isVisibleTo(dialog) and dialog.export_button.isEnabled()


@pytest.mark.parametrize(("key", "width_mm"), [("single", 85), ("double", 180)])
def test_publication_presets_set_physical_size_and_resolution(qtbot, tmp_path, key, width_mm):
    dialog = make_dialog(qtbot, tmp_path)
    select(dialog.mode_combo, key)
    choice, options = dialog.choice(), dialog.options()
    assert (choice.unit, choice.width, choice.dpi) == ("mm", width_mm, 600)
    assert options.width == pixels_from_mm(width_mm, 600)  # 2008 or 4252
    assert options.height == round(options.width / 1.5)  # the frame's 3:2 shape
    assert f"{options.width} × {options.height} px" in dialog.summary_label.text()
    assert "600 dpi" in dialog.summary_label.text()


def test_preset_height_follows_a_portrait_frame(qtbot, tmp_path):
    dialog = make_dialog(qtbot, tmp_path, output=(600, 900))
    select(dialog.mode_combo, "single")
    assert (dialog.options().width, dialog.options().height) == (2008, 3012)


def test_editing_a_preset_makes_it_custom_and_keeps_the_values(qtbot, tmp_path):
    dialog = make_dialog(qtbot, tmp_path)
    select(dialog.mode_combo, "single")
    dialog.dpi_combo.setEditText("1200")  # above 600 dpi is allowed
    choice = dialog.choice()
    assert choice.mode == "custom" and dialog.mode_combo.currentData() == "custom"
    assert (choice.unit, choice.width, choice.dpi) == ("mm", 85, 1200)
    assert dialog.options().width == pixels_from_mm(85, 1200)  # 4016: same mm, more pixels
    select(dialog.mode_combo, "custom")  # choosing Custom keeps everything
    assert dialog.choice() == choice


def test_custom_size_in_millimetres_and_pixels(qtbot, tmp_path):
    dialog = make_dialog(qtbot, tmp_path, mode="custom", dpi=300)
    select(dialog.unit_combo, "mm")
    dialog.width_spin.setValue(120.0)
    assert dialog.options().width == pixels_from_mm(120, 300)
    assert dialog.choice().height == pytest.approx(80.0)  # locked 3:2
    select(dialog.unit_combo, "px")
    assert dialog.choice().width == pixels_from_mm(120, 300)  # same size, other unit
    dialog.width_spin.setValue(1001)
    dialog.dpi_combo.setEditText("450")  # pixels stay pixels
    assert (dialog.options().width, dialog.options().height, dialog.options().dpi) == (
        1001,
        667,
        450,
    )
    dialog.height_spin.setValue(500)  # height edits compute the width
    assert (dialog.options().width, dialog.options().height) == (750, 500)


def test_unlocked_size_is_independent_and_explained(qtbot, tmp_path):
    dialog = make_dialog(qtbot, tmp_path)
    dialog.lock_check.setChecked(False)
    dialog.height_spin.setValue(1200)
    assert (dialog.options().width, dialog.options().height) == (1200, 1200)
    assert "wider or narrower area" in dialog.warning_label.text()
    dialog.lock_check.setChecked(True)  # locking restores the frame's shape
    assert (dialog.options().width, dialog.options().height) == (1200, 800)
    assert dialog.warning_label.isHidden()


def test_invalid_entries_disable_render(qtbot, tmp_path):
    dialog = make_dialog(qtbot, tmp_path, mode="custom")
    dialog.width_spin.setValue(30000)
    assert dialog.options() is None and not dialog.export_button.isEnabled()
    assert "20000" in dialog.warning_label.text()
    dialog.width_spin.setValue(3000)
    assert dialog.export_button.isEnabled()
    dialog.dpi_combo.setEditText("")
    assert not dialog.export_button.isEnabled()
    dialog.dpi_combo.setEditText("300")
    dialog.path_edit.clear()
    dialog.path_edit.textEdited.emit("")
    assert not dialog.export_button.isEnabled() and "file name" in dialog.warning_label.text()


def test_format_choice_sets_suffix_and_options(qtbot, tmp_path):
    dialog = make_dialog(qtbot, tmp_path, transparent=True)
    select(dialog.format_combo, "jpeg")
    assert dialog.destination() == tmp_path / "figure.jpg"
    assert dialog.jpeg_group.isVisibleTo(dialog) and dialog.matte_label.isVisibleTo(dialog)
    dialog.quality_spin.setValue(80)
    assert dialog.options().jpeg_quality == 80
    select(dialog.format_combo, "pdf")
    assert dialog.destination() == tmp_path / "figure.pdf"
    assert not dialog.jpeg_group.isVisibleTo(dialog) and dialog.pdf_note.isVisibleTo(dialog)
    assert "raster" in dialog.pdf_note.text() and "vector" in dialog.pdf_note.text()


def test_remembered_choice_follows_a_new_frame(tmp_path):
    custom = ExportChoice(mode="custom", unit="mm", width=100, height=50, dpi=600)
    assert custom.fitted((800, 800)).height == pytest.approx(100)  # locked: new shape
    loose = ExportChoice(mode="custom", width=900, height=300, locked=False)
    assert loose.fitted((800, 800)) == loose  # unlocked: kept
    assert ExportChoice().fitted((640, 480)).pixels() == (640, 480)  # the output size


# ----- window -----------------------------------------------------------------------------------
def scene_state(window: MainWindow):
    return (
        window.scene_revision,
        window._output_size,
        window.current_camera(),
        window.environment,
        window.isWindowModified(),
    )


@pytest.mark.parametrize("fmt", ["png", "pdf", "jpeg"])
def test_render_image_writes_each_format_without_changing_the_scene(window, qtbot, tmp_path, fmt):
    window.settings.setValue(SETTINGS_POVRAY, fake_povray(tmp_path, 0.1))
    before = scene_state(window)
    destination = tmp_path / "Fig ü" / f"figure.{fmt}"
    options = ExportOptions(fmt, 2008, 1339, dpi=600, jpeg_quality=90)
    assert window.render_image(destination, options, show_result=False)
    qtbot.waitUntil(lambda: window.render_finished_result is not None, timeout=10_000)
    assert window.render_finished_result.ok and window.last_error is None
    assert window.last_render_path == destination and destination.is_file()
    after = scene_state(window)
    assert after[:2] == before[:2] and after[3:] == before[3:]
    assert _same_camera(after[2], before[2])
    assert fmt.upper() in window.statusBar().currentMessage()


def test_render_png_keeps_its_former_behaviour(window, qtbot, tmp_path):
    window.settings.setValue(SETTINGS_POVRAY, fake_povray(tmp_path, 0.1))
    assert window.render_png(tmp_path / "plain", show_result=False)
    qtbot.waitUntil(lambda: window.render_finished_result is not None, timeout=10_000)
    written = tmp_path / "plain.png"
    assert written.is_file() and png_resolution(written.read_bytes()) is None


def test_render_image_action_uses_the_dialog_answer(window, qtbot, tmp_path, monkeypatch):
    window.settings.setValue(SETTINGS_POVRAY, fake_povray(tmp_path, 0.1))
    destination = tmp_path / "chosen.pdf"
    options = ExportOptions("pdf", 300, 200, dpi=300)
    monkeypatch.setattr(MainWindow, "ask_export", lambda self: (destination, options))
    assert window.render_action.text() == "Render Image…"
    window.render_action.trigger()
    qtbot.waitUntil(lambda: window.render_finished_result is not None, timeout=10_000)
    assert destination.read_bytes().startswith(b"%PDF-")
    monkeypatch.setattr(MainWindow, "ask_export", lambda self: None)
    assert window.export_image() is False


def test_a_failed_write_is_reported(window, qtbot, tmp_path):
    window.settings.setValue(SETTINGS_POVRAY, fake_povray(tmp_path, 0.1))
    blocked = tmp_path / "figure.jpg"
    blocked.mkdir()
    assert window.render_image(blocked, ExportOptions("jpeg", 100, 80), show_result=False)
    qtbot.waitUntil(lambda: window.render_finished_result is not None, timeout=10_000)
    assert window.last_error[0] == "Could Not Save Image"
    assert blocked.is_dir() and not list(tmp_path.glob("*.part"))
    assert window.render_action.isEnabled()


# ----- real POV-Ray -----------------------------------------------------------------------------
@pytest.mark.povray
def test_same_scene_as_png_pdf_and_jpeg(window, qtbot, tmp_path, povray_executable):
    """One scene, three formats: identical pixel size and framing; PDF at physical size."""
    window.settings.setValue(SETTINGS_POVRAY, povray_executable)
    window.set_output_size(300, 200)
    window._mark_clean()
    camera = window.current_camera()
    width = pixels_from_mm(40, 150)  # a 40 mm figure at 150 dpi: 236 px
    height = round(width / 1.5)
    folder = tmp_path / "Ångström figures"
    images = {}
    for fmt in ("png", "pdf", "jpeg"):
        window.render_finished_result = None
        options = ExportOptions(fmt, width, height, dpi=150, jpeg_quality=95)
        assert window.render_image(folder / f"fig.{fmt}", options, show_result=False)
        qtbot.waitUntil(lambda: window.render_finished_result is not None, timeout=60_000)
        assert window.render_finished_result.ok, window.render_finished_result.message
        images[fmt] = window.last_render_path
    assert window._output_size == (300, 200) and _same_camera(window.current_camera(), camera)
    assert not window.isWindowModified()
    with Image.open(images["png"]) as png, Image.open(images["jpeg"]) as jpeg:
        assert png.size == jpeg.size == (width, height)
        assert png.info["dpi"] == pytest.approx((150, 150), abs=0.05)  # whole px per metre
        assert jpeg.info["dpi"] == pytest.approx((150, 150), abs=0.5)
        # Same picture: the JPEG differs from the PNG only by compression.
        difference = [
            abs(a - b) for a, b in zip(png.convert("RGB").tobytes(), jpeg.tobytes(), strict=True)
        ]
        assert sum(difference) / len(difference) < 4
    data = images["pdf"].read_bytes()
    page_w, page_h = pdf_media_box(data)
    assert page_w == pytest.approx(width / 150 * 25.4 * POINTS_PER_MM, abs=0.5)
    assert page_h == pytest.approx(height / 150 * 25.4 * POINTS_PER_MM, abs=0.5)
    assert re.search(rf"/Width {width}\b".encode(), data)
