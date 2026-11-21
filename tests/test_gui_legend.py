"""FR-LEGEND-01 in the window: Legend tab, live view, fitting, renders, and projects."""

from __future__ import annotations

from dataclasses import replace

import numpy as np
import pytest
from PIL import Image

from conftest import fake_povray
from test_gui_render import make_window
from test_legend import BACKGROUND, SHOWN, rgb255, sphere_extent
from ycrystal.core.export import ExportOptions
from ycrystal.core.legend import LegendSettings, legend_entries
from ycrystal.gui.main_window import SETTINGS_POVRAY
from ycrystal.render.legend import legend_layout

pytestmark = pytest.mark.gui


@pytest.fixture
def window(qtbot):
    win = make_window(qtbot)
    yield win
    win.close()


def show_legend(window, legend: LegendSettings = SHOWN) -> None:
    assert window.set_legend(legend, "Legend")
    window.viewport.render()


def live_marker_colours(window) -> dict[str, np.ndarray]:
    """Colour at the centre of each marker in a screenshot of the live view."""
    viewport = window.viewport
    x0, y0, frame_w, frame_h = viewport.frame_rect()
    legend = window.scene_settings.legend
    entries = viewport.legend_entries()
    layout = legend_layout(entries, legend, round(frame_w), round(frame_h))
    shot = viewport.screenshot()
    colours = {}
    for (centre, _r, _c), entry in zip(layout.markers, entries, strict=True):
        point = layout.to_image(centre)
        x, y = round(x0) + int(point.x()), round(y0) + int(point.y())
        colours[entry.element] = shot[y, x, :3].astype(int)
    return colours


def structure_bottom(window, width: int, height: int) -> float:
    """Lowest pixel row of the drawn spheres and cell in a ``width`` × ``height`` image."""
    points, radii = window.geometry.points_and_radii()
    return sphere_extent(window.current_camera(), points, radii, width, height)[3]


# ----- panel and undo ----------------------------------------------------------------------
def test_the_legend_tab_shows_and_hides_the_legend_as_one_undo_step(window):
    panel = window.legend_panel
    assert window.scene_panel.indexOf(panel) >= 0
    geometry = window.geometry
    revision = window.scene_revision
    assert window.viewport.legend_box is None
    panel.enabled_check.click()
    assert window.scene_settings.legend.enabled
    assert window.undo_stack.undoText() == "Show Legend"
    window.viewport.render()
    assert window.viewport.legend_box is not None
    assert window.geometry is geometry  # drawn on top: no new geometry
    assert window.scene_revision > revision  # the figure changed: the preview is stale
    assert window.isWindowModified()
    assert [panel.element_list.item(i).text() for i in range(3)] == ["Sr", "Ti", "O"]
    window.undo_stack.undo()
    window.viewport.render()
    assert not window.scene_settings.legend.enabled and window.viewport.legend_box is None
    assert not panel.enabled_check.isChecked()


def test_panel_controls_request_complete_legends(window, qtbot):
    panel = window.legend_panel
    show_legend(window)
    panel.position_combo.setCurrentIndex(panel.position_combo.findData("custom"))
    panel.position_combo.activated.emit(panel.position_combo.currentIndex())
    assert window.scene_settings.legend.position == "custom"
    assert panel.x_spin.isEnabled() and not panel.margin_spin.isEnabled()
    assert not panel.fit_button.isEnabled()
    panel.x_spin.setValue(25.0)
    assert window.scene_settings.legend.x == pytest.approx(0.25)
    for value in (6.0, 6.5, 7.0):  # stepping merges into one undo step
        panel.size_spin.setValue(value)
    assert window.scene_settings.legend.font_size == 7.0
    window.undo_stack.undo()
    assert window.scene_settings.legend.font_size == SHOWN.font_size
    panel.element_list.setCurrentRow(2)  # O
    panel.up_button.click()
    legend = window.scene_settings.legend
    assert legend.order == "custom" and legend.custom_order == ("Sr", "O", "Ti")
    assert panel.element_list.currentItem().text() == "O"  # stays selected
    assert panel.order_combo.currentData() == "custom"
    index = panel.font_combo.findData("DejaVu Sans")
    if index < 0:
        index = 1  # the first installed family
    panel.font_combo.setCurrentIndex(index)
    panel.font_combo.activated.emit(index)
    assert window.scene_settings.legend.font_family == panel.font_combo.itemData(index)
    panel.background_check.click()
    assert window.scene_settings.legend.background and panel.opacity_spin.isEnabled()


# ----- live view ---------------------------------------------------------------------------
def test_live_markers_have_the_atom_colours_and_follow_changes(window):
    show_legend(window)
    colours = live_marker_colours(window)
    for entry in legend_entries(window.geometry, SHOWN):
        assert np.abs(colours[entry.element] - rgb255(entry.color)).max() <= 3, entry.element
    window.set_element_color("Ti", (0.0, 0.0, 1.0))  # an element colour override
    window.viewport.render()
    assert np.abs(live_marker_colours(window)["Ti"] - (0, 0, 255)).max() <= 3
    window.set_element_material("O", "gold")  # a material with its own pigment
    window.viewport.render()
    gold = legend_entries(window.geometry, SHOWN)[2].color
    assert np.abs(live_marker_colours(window)["O"] - rgb255(gold)).max() <= 3


def test_hidden_elements_leave_the_legend(window):
    show_legend(window)
    ti = [
        atom_id
        for atom_id, e in zip(window.geometry.atom_ids, window.geometry.elements, strict=True)
        if e == "Ti"
    ]
    window.select(set(ti))
    window.hide_selected()
    window.viewport.render()
    assert [e.element for e in window.viewport.legend_entries()] == ["Sr", "O"]
    assert window.legend_panel.element_list.count() == 2


def test_fit_reset_and_view_along_keep_the_structure_above_the_legend(window):
    show_legend(window)
    width, height = window.output_size()
    rect = legend_layout(window.viewport.legend_entries(), SHOWN, width, height).rect
    assert structure_bottom(window, width, height) > rect.top()  # the start view overlaps
    for move in (window.viewport.fit, window.reset_view, lambda: window.view_along("c")):
        move()
        assert structure_bottom(window, width, height) < rect.top()
    window.legend_panel.fit_button.click()
    assert structure_bottom(window, width, height) < rect.top()


# ----- renders -----------------------------------------------------------------------------
def legend_pixels(path, background=BACKGROUND) -> np.ndarray:
    image = np.asarray(Image.open(path).convert("RGB")).astype(int)
    return np.argwhere(np.abs(image - background).max(axis=2) > 12)


def test_renders_carry_the_legend_where_the_view_shows_it(window, qtbot, tmp_path):
    window.settings.setValue(SETTINGS_POVRAY, fake_povray(tmp_path))
    show_legend(window, replace(SHOWN, position="right", layout="vertical"))
    window.set_output_size(900, 600)
    window.viewport.render()
    destination = tmp_path / "figure.png"
    assert window.render_image(destination, ExportOptions("png", 900, 600), show_result=False)
    qtbot.waitUntil(lambda: window.render_finished_result is not None, timeout=20_000)
    assert window.render_finished_result.ok, window.render_finished_result.message
    legend = window.scene_settings.legend
    entries = window.viewport.legend_entries()
    # Where the image has the legend: inside the layout's box at the output size.
    rect = legend_layout(entries, legend, 900, 600).rect
    found = legend_pixels(destination)
    (y0, x0), (y1, x1) = found.min(axis=0), found.max(axis=0)
    assert rect.left() - 1 <= x0 <= rect.left() + 3 and rect.right() - 3 <= x1 <= rect.right() + 1
    assert rect.top() - 1 <= y0 <= rect.top() + 3 and rect.bottom() - 3 <= y1 <= rect.bottom() + 1
    # Where the view shows it: the same box, in the frame, up to the view's rounding.
    fx, fy, frame_w, frame_h = window.viewport.frame_rect()
    live = legend_layout(entries, legend, round(frame_w), round(frame_h)).rect
    corners = window.viewport.frame_to_output(
        np.array(
            [
                [round(fx) + live.left(), round(fy) + live.top()],
                [round(fx) + live.right(), round(fy) + live.bottom()],
            ]
        ),
        900,
        600,
    )
    tolerance = 900 / frame_w  # one view pixel
    expected = [[rect.left(), rect.top()], [rect.right(), rect.bottom()]]
    assert np.abs(corners - expected).max() <= tolerance
    left, top, w, h = window.viewport.legend_box  # the overlay covers that box
    assert left <= round(fx) + live.left() and left + w >= round(fx) + live.right()
    assert top <= round(fy) + live.top() and top + h >= round(fy) + live.bottom()


@pytest.mark.parametrize("fmt", ["jpeg", "pdf"])
def test_other_export_formats_contain_the_legend(window, qtbot, tmp_path, fmt):
    window.settings.setValue(SETTINGS_POVRAY, fake_povray(tmp_path))
    show_legend(window)
    destination = tmp_path / f"figure.{fmt}"
    options = ExportOptions(fmt, 1200, 800, dpi=300, jpeg_quality=95)
    assert window.render_image(destination, options, show_result=False)
    qtbot.waitUntil(lambda: window.render_finished_result is not None, timeout=20_000)
    assert window.render_finished_result.ok and destination.is_file()
    if fmt == "jpeg":
        image = np.asarray(Image.open(destination).convert("RGB")).astype(int)
        entries = legend_entries(window.geometry, SHOWN)
        layout = legend_layout(entries, SHOWN, 1200, 800)
        for (centre, _r, _c), entry in zip(layout.markers, entries, strict=True):
            point = layout.to_image(centre)
            pixel = image[int(point.y()), int(point.x())]
            assert np.abs(pixel - rgb255(entry.color)).max() <= 12, entry.element
    else:
        assert destination.read_bytes().startswith(b"%PDF-")


def test_preview_shows_the_legend(window, qtbot, tmp_path):
    window.settings.setValue(SETTINGS_POVRAY, fake_povray(tmp_path))
    show_legend(window)
    assert window.request_preview()
    qtbot.waitUntil(lambda: window.preview_panel.state in ("ready", "error"), timeout=20_000)
    assert window.preview_panel.state == "ready"
    image = window.preview_panel._pixmap.toImage()  # the full-size preview
    size = window.preview_size()
    assert (image.width(), image.height()) == (size.width, size.height)
    entries = legend_entries(window.geometry, SHOWN)
    layout = legend_layout(entries, SHOWN, size.width, size.height)
    point = layout.to_image(layout.markers[0][0])
    colour = image.pixelColor(int(point.x()), int(point.y()))
    assert np.abs(np.array(colour.getRgb()[:3]) - rgb255(entries[0].color)).max() <= 12


# ----- projects ----------------------------------------------------------------------------
def test_projects_reopen_with_their_legend(window, qtbot, tmp_path):
    legend = replace(SHOWN, layout="vertical", position="left", background=True)
    show_legend(window, legend)
    path = tmp_path / "legend.ycrystal"
    assert window.save_as(path)
    second = make_window(qtbot)
    assert second.open_file(path)
    try:
        assert second.scene_settings.legend == legend
        second.viewport.render()
        assert second.viewport.legend_box is not None
        assert second.legend_panel.layout_combo.currentData() == "vertical"
    finally:
        second.close()
