"""FR-PREVIEW-01: user-adjustable POV-Ray preview resolution."""

import itertools

import pytest
from PySide6.QtCore import QSettings
from PySide6.QtGui import QPixmap

from test_render_queue import fake_povray
from ycrystal.core.aspect import (
    MAX_PREVIEW_PIXELS,
    MIN_PREVIEW_PIXELS,
    PREVIEW_PRESETS,
    preview_preset_width,
    preview_size,
)
from ycrystal.core.samples import perovskite_srtio3
from ycrystal.gui.main_window import (
    SETTINGS_POVRAY,
    SETTINGS_PREVIEW_RESOLUTION,
    SETTINGS_PREVIEW_WIDTH,
    MainWindow,
    PreviewRequest,
)
from ycrystal.render.pov_writer import scene_to_pov


# ----- size arithmetic (no Qt) ---------------------------------------------------------------
def test_presets_at_three_to_two():
    assert [(key, width) for key, _label, width in PREVIEW_PRESETS] == [
        ("small", 480),
        ("medium", 800),
        ("large", 1200),
    ]
    sizes = [preview_size((2400, 1600), preview_preset_width(k))[:2] for k, *_ in PREVIEW_PRESETS]
    assert sizes == [(480, 320), (800, 533), (1200, 800)]
    with pytest.raises(KeyError):
        preview_preset_width("custom")


def test_portrait_and_other_shapes():
    assert preview_size((1600, 2400), 480)[:2] == (480, 720)
    assert preview_size((1600, 2400), 1200)[:2] == (1200, 1800)
    assert preview_size((1920, 1080), 800)[:2] == (800, 450)
    assert preview_size((1000, 1000), 800)[:2] == (800, 800)
    assert preview_size((1200, 900), 1000)[:2] == (1000, 750)
    # Never larger than the final image; asking for exactly its width is no limit.
    assert preview_size((640, 480), 1200) == (640, 480, 1200, "output")
    assert preview_size((640, 480), 640) == (640, 480, 640, None)


def test_limits_keep_the_shape():
    tall = preview_size((2000, 8000), 1200)  # 1200 × 4800 would be too tall
    assert tall == (1000, 4000, 1200, "maximum")
    wide = preview_size((8000, 16), 480)  # 480 × 1 is impossible: the short side wins
    assert wide == (8000, 16, 480, "minimum")
    assert preview_size((16, 8000), 480) == (16, 8000, 480, "minimum")
    assert preview_size((4000, 50), 800) == (1280, 16, 800, "minimum")
    for bad in (MIN_PREVIEW_PIXELS - 1, MAX_PREVIEW_PIXELS + 1):
        with pytest.raises(ValueError, match="between 16 and 4000"):
            preview_size((2400, 1600), bad)
    with pytest.raises(ValueError):
        preview_size((0, 1600), 480)


def test_every_size_matches_the_output_shape():
    outputs = [(w, h) for w, h in itertools.product((16, 37, 640, 1201, 2400, 8000), repeat=2)]
    for output, request in itertools.product(outputs, (16, 100, 480, 800, 1200, 4000)):
        width, height, requested, limit = preview_size(output, request)
        assert requested == request
        assert MIN_PREVIEW_PIXELS <= min(width, height)
        assert width <= output[0] and height <= output[1]
        assert height <= MAX_PREVIEW_PIXELS or limit == "minimum"
        # One side follows from the other by rounding: under half a pixel off the shape.
        off_h = abs(height - width * output[1] / output[0])
        off_w = abs(width - height * output[0] / output[1])
        assert min(off_h, off_w) <= 0.5 + 1e-9
        if limit is None:
            assert width == request


# ----- in the window -------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def clean_preference():
    """The preference is shared by all windows of the test session: reset it."""

    def clear():
        settings = QSettings()
        settings.remove(SETTINGS_PREVIEW_RESOLUTION)
        settings.remove(SETTINGS_PREVIEW_WIDTH)

    clear()
    yield
    clear()


def make_window(qtbot):
    win = MainWindow(perovskite_srtio3())
    qtbot.addWidget(win)
    win.resize(1150, 700)
    win.show()
    qtbot.waitExposed(win)
    qtbot.waitUntil(lambda: win._saved_camera is not None, timeout=5000)
    win.preview_panel.auto_check.setChecked(False)
    return win


@pytest.fixture
def window(qtbot):
    win = make_window(qtbot)
    yield win
    win.close()


def final_state(win):
    camera = win.current_camera()
    settings = win.current_render_settings()
    return (
        win.output_size(),
        settings,
        camera,
        scene_to_pov(win.geometry, camera, win.environment, settings),
        win.undo_stack.count(),
        win.is_modified(),
    )


def choose(win, key):
    combo = win.preview_panel.resolution_combo
    combo.setCurrentIndex(combo.findData(key))


@pytest.mark.gui
def test_selector_presets_show_the_actual_size(window):
    panel = window.preview_panel
    assert window.output_size() == (1200, 800)
    assert window.preview_resolution() == ("small", 480)  # the default of earlier versions
    assert (window.preview_settings().width, window.preview_settings().height) == (480, 320)
    assert panel.size_label.text() == "Preview 480 × 320 px · final PNG 1200 × 800 px"
    assert not panel.width_spin.isEnabled() and panel.width_spin.value() == 480
    before = final_state(window)
    choose(window, "medium")
    assert window.preview_resolution() == ("medium", 800)
    settings = window.preview_settings()
    assert (settings.width, settings.height) == (800, 533)
    assert settings.antialias is False  # preview quality unchanged
    assert panel.size_label.text().startswith("Preview 800 × 533 px")
    assert panel.width_spin.value() == 800 and not panel.width_spin.isEnabled()
    choose(window, "large")
    assert panel.size_label.text() == ("Preview 1200 × 800 px · final PNG 1200 × 800 px")
    # Output size, ratio, camera, scene, undo history, and modified state are untouched.
    assert final_state(window) == before
    assert "resolution" in panel.resolution_combo.toolTip()
    assert "take longer" in panel.resolution_combo.toolTip()


@pytest.mark.gui
def test_custom_width_and_limits(window):
    panel = window.preview_panel
    choose(window, "custom")
    assert panel.width_spin.isEnabled()
    assert window.preview_resolution() == ("custom", 480)  # starts from the default width
    panel.width_spin.setValue(1000)
    assert window.preview_resolution() == ("custom", 1000)
    assert window.preview_size()[:2] == (1000, 667)
    assert (panel.width_spin.minimum(), panel.width_spin.maximum()) == (16, 4000)
    for bad in (15, 4001):
        with pytest.raises(ValueError, match="between 16 and 4000"):
            window.set_preview_resolution("custom", bad)
    assert window.preview_resolution() == ("custom", 1000)  # rejected edits change nothing
    with pytest.raises(ValueError):
        window.set_preview_resolution("huge")
    # A preset and back to Custom offers the remembered custom width again.
    choose(window, "small")
    assert panel.width_spin.value() == 480 and not panel.width_spin.isEnabled()
    choose(window, "custom")
    assert panel.width_spin.value() == 1000 and window.preview_resolution() == ("custom", 1000)


@pytest.mark.gui
def test_portrait_and_non_three_to_two_outputs(window):
    panel = window.preview_panel
    window.set_output_size(800, 1200)
    assert window.preview_size()[:2] == (480, 720)
    assert panel.size_label.text() == "Preview 480 × 720 px · final PNG 800 × 1200 px"
    choose(window, "large")  # wider than the output: limited to it
    assert window.preview_size() == (800, 1200, 1200, "output")
    assert "never larger than the final image" in panel.size_label.text()
    window.set_output_size(1920, 1080)
    choose(window, "medium")
    assert window.preview_size()[:2] == (800, 450)
    window.set_output_size(8000, 16)  # extreme: the short side stays at 16 px
    assert window.preview_size()[:2] == (8000, 16)
    assert "at least 16 px" in panel.size_label.text()
    assert window.output_size() == (8000, 16)


@pytest.mark.gui
def test_preference_is_restored(qtbot):
    first = make_window(qtbot)
    first.set_preview_resolution("custom", 640)
    first.set_preview_resolution("large")
    first.close()
    second = make_window(qtbot)
    assert second.preview_resolution() == ("large", 1200)
    combo = second.preview_panel.resolution_combo
    assert combo.currentData() == "large"
    choose(second, "custom")
    assert second.preview_resolution() == ("custom", 640)  # custom width remembered too
    second.close()
    settings = QSettings()
    settings.setValue(SETTINGS_PREVIEW_RESOLUTION, "enormous")
    settings.setValue(SETTINGS_PREVIEW_WIDTH, "not a number")
    third = make_window(qtbot)
    assert third.preview_resolution() == ("small", 480)  # unreadable values: default
    third.close()
    settings.setValue(SETTINGS_PREVIEW_RESOLUTION, "custom")
    settings.setValue(SETTINGS_PREVIEW_WIDTH, 99999)
    fourth = make_window(qtbot)
    assert fourth.preview_resolution() == ("custom", 480)  # out of range: default width
    fourth.close()


@pytest.mark.gui
def test_requested_size_reaches_povray(window, tmp_path, monkeypatch):
    window.settings.setValue(SETTINGS_POVRAY, fake_povray(tmp_path, 0.1))
    jobs = []
    submit = window.preview_queue.submit
    monkeypatch.setattr(
        window.preview_queue,
        "submit",
        lambda job, exe, tag: (jobs.append((job.ini_path.read_text(), tag)), submit(job, exe, tag)),
    )
    choose(window, "medium")
    assert window.request_preview()
    ini, tag = jobs[-1]
    assert "Width=800" in ini and "Height=533" in ini and "Antialias=off" in ini
    assert tag == PreviewRequest(window.scene_revision, 800, 533)
    assert "800 × 533 px" in window.preview_panel.status_label.text()


@pytest.mark.gui
def test_resolution_change_marks_outdated_or_updates(window, qtbot, tmp_path):
    window.settings.setValue(SETTINGS_POVRAY, fake_povray(tmp_path, 0.1))
    panel = window.preview_panel
    revision = window.scene_revision
    assert window.request_preview()
    qtbot.waitUntil(lambda: panel.state == "ready", timeout=10_000)
    assert window.preview_shown == PreviewRequest(revision, 480, 320)
    # Automatic preview off: out of date, nothing is rendered until Preview.
    choose(window, "medium")
    assert panel.state == "stale" and "resolution changed" in panel.status_label.text()
    assert "Press Preview" in panel.status_label.text()
    assert not window.preview_queue.is_busy() and not window._preview_timer.isActive()
    assert window.scene_revision == revision  # not a change of the figure
    # Automatic preview on: a debounced update with the new size.
    panel.auto_check.setChecked(True)
    qtbot.waitUntil(lambda: panel.state == "ready", timeout=10_000)
    assert window.preview_shown == PreviewRequest(revision, 800, 533)
    choose(window, "large")
    assert window._preview_timer.isActive() and "A new preview follows" in panel.status_label.text()
    qtbot.waitUntil(lambda: panel.state == "ready", timeout=10_000)
    assert window.preview_shown == PreviewRequest(revision, 1200, 800)
    assert window.preview_discarded == 0


@pytest.mark.gui
def test_stale_resolution_results_never_replace_the_latest(window, qtbot, tmp_path):
    window.settings.setValue(SETTINGS_POVRAY, fake_povray(tmp_path, 0.8))
    panel = window.preview_panel
    assert window.request_preview()  # 480 × 320
    choose(window, "medium")  # while it renders
    qtbot.waitUntil(lambda: window.preview_result is not None, timeout=10_000)
    assert window.preview_discarded == 1 and not panel.has_image()
    assert "preview resolution changed" in panel.status_label.text()
    assert window.preview_shown is None
    # A newer request supersedes an older one; only the latest is shown.
    assert window.request_preview()  # 800 × 533
    choose(window, "large")
    assert window.request_preview()  # 1200 × 800: cancels the running 800 × 533 job
    qtbot.waitUntil(lambda: panel.state == "ready", timeout=10_000)
    assert window.preview_shown == PreviewRequest(window.scene_revision, 1200, 800)
    assert window.preview_discarded == 1


@pytest.mark.gui
def test_resizing_the_panel_fits_without_rendering(window, qtbot, tmp_path):
    window.settings.setValue(SETTINGS_POVRAY, fake_povray(tmp_path, 0.1))
    panel = window.preview_panel
    panel.auto_check.setChecked(True)
    qtbot.waitUntil(lambda: panel.state == "ready", timeout=10_000)
    result, shown = window.preview_result, window.preview_shown
    window_size, minimum = window.size(), panel.minimumSizeHint()
    panel.set_image(QPixmap(1200, 800))  # a large 3:2 image (the fake renderer's is 4 × 4)
    assert panel.minimumSizeHint() == minimum  # a large image does not widen the dock
    for width in (260, 420, 330):
        panel.resize(width, 300)
        qtbot.wait(50)
        label = panel.image_label
        pixmap = label.pixmap()
        assert pixmap.width() <= label.width() and pixmap.height() <= label.height()
        assert pixmap.width() / pixmap.height() == pytest.approx(1.5, abs=0.01)  # undistorted
    assert not window._preview_timer.isActive() and not window.preview_queue.is_busy()
    assert window.preview_result is result and window.preview_shown == shown
    assert window.size() == window_size  # the window did not grow


# ----- real POV-Ray: the PNG has the requested size ------------------------------------------
@pytest.mark.gui
@pytest.mark.povray
def test_preview_png_has_the_requested_size(window, qtbot, povray_executable):
    window.settings.setValue(SETTINGS_POVRAY, povray_executable)
    panel = window.preview_panel
    before = final_state(window)
    for key, output, expected in (
        ("medium", (1200, 800), (800, 533)),
        ("small", (800, 1200), (480, 720)),
    ):
        window.set_output_size(*output)
        choose(window, key)
        assert window.request_preview()
        qtbot.waitUntil(lambda: panel.state in ("ready", "error"), timeout=60_000)
        assert panel.state == "ready", panel.status_label.text()
        assert (panel._pixmap.width(), panel._pixmap.height()) == expected
        assert window.preview_shown[1:] == expected
    window.set_output_size(1200, 800)
    after = final_state(window)
    assert after[:4] == before[:4]  # same output size, settings, camera, and scene
