"""FR-LEGEND-01: element legend settings, entries, files, framing, painting, and renders.

Painting needs a Qt GUI application (``qapp``) but no window; the command-line test runs
Ycrystal in a new process, which draws the legend without any window.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from conftest import fake_povray
from ycrystal.batch import render_png, scene_for
from ycrystal.core.camera import Camera, CameraPolicyError, ViewPolicy, default_camera
from ycrystal.core.legend import (
    LEGEND_RANGES,
    LegendEntry,
    LegendSettings,
    legend_entries,
    order_elements,
)
from ycrystal.core.samples import perovskite_srtio3
from ycrystal.core.scene import Environment, SceneSettings, build_geometry, element_color
from ycrystal.io.project import (
    Project,
    ProjectError,
    load_project,
    project_from_dict,
    project_to_dict,
    save_project,
)
from ycrystal.io.style import Style, apply_style, load_style, save_style
from ycrystal.render.formats import PNG_SIGNATURE, png_resolution
from ycrystal.render.jobs import finish_job, prepare_job
from ycrystal.render.pov_writer import RenderSettings

SHOWN = LegendSettings(enabled=True, marker_style="flat")
"""An enabled legend with flat markers, whose centres have exactly the element colour."""

BACKGROUND = (40, 60, 80)
"""Colour of the stand-in renderer's images (``conftest.fake_povray``)."""


def srtio3_geometry(settings: SceneSettings | None = None):
    return build_geometry(perovskite_srtio3(), settings or SceneSettings())


def rgb255(rgb) -> np.ndarray:
    return np.round(np.asarray(rgb) * 255)


def write_png(path: Path, size=(400, 300), mode="RGB", color=BACKGROUND) -> Path:
    fill = color if mode == "RGB" else (*color, 0)
    Image.new(mode, size, fill).save(path)
    return path


def pixels(path: Path) -> np.ndarray:
    return np.asarray(Image.open(path).convert("RGBA")).astype(int)


def marker_centres(entries, settings, width, height) -> list[tuple[int, int]]:
    from ycrystal.render.legend import legend_layout

    layout = legend_layout(entries, settings, width, height)
    points = [layout.to_image(centre) for centre, _r, _c in layout.markers]
    return [(int(p.x()), int(p.y())) for p in points]


# ----- settings -----------------------------------------------------------------------
def test_defaults_are_disabled_and_valid():
    legend = LegendSettings()
    assert not legend.enabled
    assert (legend.layout, legend.position, legend.order) == ("horizontal", "bottom", "structure")
    assert SceneSettings().legend == legend


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"layout": "diagonal"}, "layout"),
        ({"position": "centre"}, "position"),
        ({"order": "random"}, "order"),
        ({"marker_style": "star"}, "marker_style"),
        ({"font_size": 0.0}, "font_size"),
        ({"font_size": float("nan")}, "font_size"),
        ({"marker_size": 5.0}, "marker_size"),
        ({"x": 1.5}, "x"),
        ({"background_opacity": -0.1}, "background_opacity"),
        ({"text_color": (1.2, 0, 0)}, "text_color"),
        ({"custom_order": ("Xx",)}, "unknown element"),
        ({"custom_order": ("O", "O")}, "twice"),
    ],
)
def test_invalid_settings_are_rejected(changes, message):
    with pytest.raises(ValueError, match=message):
        LegendSettings(**changes)


def test_ranges_are_inclusive_and_values_normalised():
    for name, (low, high) in LEGEND_RANGES.items():
        LegendSettings(**{name: low})
        LegendSettings(**{name: high})
    legend = LegendSettings(font_size=4, custom_order=["Ti", "O"], font_family="  Arial ")
    assert legend.font_size == 4.0 and isinstance(legend.font_size, float)
    assert legend.custom_order == ("Ti", "O") and legend.font_family == "Arial"


# ----- entries ------------------------------------------------------------------------
def test_entries_follow_the_chosen_order():
    geometry = srtio3_geometry()
    names = {
        order: [e.element for e in legend_entries(geometry, LegendSettings(order=order))]
        for order in ("structure", "atomic_number", "alphabetical")
    }
    assert names == {
        "structure": ["Sr", "Ti", "O"],
        "atomic_number": ["O", "Ti", "Sr"],
        "alphabetical": ["O", "Sr", "Ti"],
    }
    custom = LegendSettings(order="custom", custom_order=("O", "Fe"))
    assert [e.element for e in legend_entries(geometry, custom)] == ["O", "Sr", "Ti"]
    assert order_elements(["Ru", "Sc", "Be"], "atomic_number") == ["Be", "Sc", "Ru"]
    with pytest.raises(ValueError):
        order_elements(["O"], "sideways")


def test_entries_use_the_drawn_colours_including_overrides_and_pigments():
    plain = legend_entries(srtio3_geometry(), SHOWN)
    assert plain[0] == LegendEntry("Sr", element_color(38))
    settings = SceneSettings().with_element_color("Ti", (0.1, 0.2, 0.9))
    settings = settings.with_element_material("O", "gold")  # a material with its own pigment
    geometry = srtio3_geometry(settings)
    colors = {e.element: e.color for e in legend_entries(geometry, SHOWN)}
    assert colors["Ti"] == (0.1, 0.2, 0.9)
    oxygen = [tuple(c) for e, c in zip(geometry.elements, geometry.colors, strict=True) if e == "O"]
    assert colors["O"] == oxygen[0] != element_color(8)  # what the spheres show


def test_entries_list_only_displayed_elements_and_the_majority_colour():
    structure = perovskite_srtio3()
    ti = list(structure.symbols).index("Ti")
    hidden = SceneSettings(hidden=frozenset({(ti, (0, 0, 0))}))
    assert [e.element for e in legend_entries(srtio3_geometry(hidden), SHOWN)] == ["Sr", "O"]
    corner = (0, (0, 0, 0))  # one of the eight Sr corners gets its own pigment
    one_gold = SceneSettings().with_atom_materials([corner], "gold")
    sr = legend_entries(srtio3_geometry(one_gold), SHOWN)[0]
    assert sr.color == element_color(38)


# ----- projects and styles -------------------------------------------------------------
def test_projects_store_the_legend_exactly(tmp_path):
    legend = LegendSettings(
        enabled=True,
        layout="vertical",
        position="custom",
        x=0.83,
        y=0.25,
        font_family="DejaVu Serif",
        font_size=3.5,
        text_color=(0.2, 0.1, 0.0),
        marker_size=1.3,
        marker_style="flat",
        spacing=0.4,
        margin=1.1,
        background=True,
        background_color=(0.9, 0.95, 1.0),
        background_opacity=0.5,
        order="custom",
        custom_order=("O", "Ti"),
    )
    project = Project(perovskite_srtio3(), scene=SceneSettings(legend=legend))
    path = save_project(tmp_path / "legend.ycrystal", project)
    assert load_project(path).scene.legend == legend
    data = json.loads(path.read_text())
    assert data["schema_version"] == 9 and data["scene"]["legend"]["custom_order"] == ["O", "Ti"]


def test_older_projects_open_without_a_legend_and_damaged_ones_are_refused():
    data = project_to_dict(Project(perovskite_srtio3()))
    del data["scene"]["legend"]
    data["schema_version"] = 7
    assert project_from_dict(data).scene.legend == LegendSettings()
    data["scene"]["legend"] = {"enabled": True, "position": "middle"}
    with pytest.raises(ProjectError, match="damaged"):
        project_from_dict(data)


def test_styles_carry_the_legend_with_the_appearance(tmp_path):
    legend = LegendSettings(enabled=True, order="custom", custom_order=("O", "Sr", "Ti"))
    source = perovskite_srtio3()
    style = Style.from_state(source, SceneSettings(legend=legend), Environment(), (800, 600))
    path = save_style(tmp_path / "legend.ycstyle", style)
    assert json.loads(path.read_text())["schema_version"] == 3
    loaded = load_style(path)
    assert loaded.scene.legend == legend
    same = apply_style(loaded, source, SceneSettings(), Environment(), (400, 300))
    assert same.scene.legend == legend
    kept = apply_style(loaded, source, SceneSettings(), Environment(), (400, 300), ("display",))
    assert kept.scene.legend == LegendSettings()  # not an appearance transfer
    # Sr → Ba: the custom order follows the mapping; elements left out are dropped, and
    # unmapped ones stay (Sr, which BaTiO3 does not show).
    target = Structure_with(source, {"Sr": "Ba"})
    mapped = apply_style(
        loaded, target, SceneSettings(), Environment(), (400, 300), element_map={"Ti": None}
    )
    assert mapped.scene.legend.custom_order == ("O", "Sr")
    mapped = apply_style(
        loaded, target, SceneSettings(), Environment(), (400, 300), element_map={"Sr": "Ba"}
    )
    assert mapped.scene.legend.custom_order == ("O", "Ba", "Ti")


def Structure_with(structure, replacements):  # noqa: N802 - reads as a constructor
    from ase.data import atomic_numbers

    from ycrystal.core.structure import Structure

    symbols = [replacements.get(s, s) for s in structure.symbols]
    return Structure(
        cell=structure.cell,
        positions=structure.positions,
        numbers=[atomic_numbers[s] for s in symbols],
        labels=symbols,
        pbc=structure.pbc,
    )


# ----- framing beside the legend --------------------------------------------------------
def sphere_extent(camera: Camera, points, radii, width, height):
    """Pixel box ``(x0, y0, x1, y1)`` of spheres seen by ``camera`` in a W × H image."""
    xy = camera.project(points, width, height)
    r = np.asarray(radii) * camera.pixels_per_angstrom(height)
    return (xy[:, 0] - r).min(), (xy[:, 1] - r).min(), (xy[:, 0] + r).max(), (xy[:, 1] + r).max()


@pytest.mark.parametrize(
    "region", [(0.0, 0.0, 1.0, 0.8), (0.0, 0.25, 1.0, 1.0), (0.3, 0.0, 1.0, 1.0), (0, 0, 0.6, 1)]
)
def test_fitting_into_a_region_fills_it_and_stays_inside(region):
    geometry = srtio3_geometry()
    points, radii = geometry.points_and_radii()
    width, height = 900, 600
    camera = default_camera(points, radii, 1.5).fitted(points, radii, 1.5, 0.0, region)
    x0, y0, x1, y1 = sphere_extent(camera, points, radii, width, height)
    left, top, right, bottom = (region[0] * width, region[1] * height) + (
        region[2] * width,
        region[3] * height,
    )
    tol = 1e-6 * width
    assert left - tol <= x0 and x1 <= right + tol and top - tol <= y0 and y1 <= bottom + tol
    touching = [abs(x0 - left) < 1e-6, abs(x1 - right) < 1e-6]
    touching += [abs(y0 - top) < 1e-6, abs(y1 - bottom) < 1e-6]
    assert sum(touching) >= 2  # tight in one direction
    assert (x0 + x1) / 2 == pytest.approx((left + right) / 2)  # centred in the region
    assert (y0 + y1) / 2 == pytest.approx((top + bottom) / 2)


def test_without_a_region_fitting_is_unchanged():
    points, radii = srtio3_geometry().points_and_radii()
    camera = default_camera(points, radii, 1.5)
    assert camera.fitted(points, radii, 1.5, region=None) == camera.fitted(points, radii, 1.5)
    assert camera.fitted(points, radii, 1.5, region=(0, 0, 1, 1)).parallel_scale == pytest.approx(
        camera.fitted(points, radii, 1.5).parallel_scale
    )
    with pytest.raises(ValueError, match="region"):
        camera.fitted(points, radii, 1.5, region=(0.5, 0.0, 0.4, 1.0))


def test_a_fixed_visible_height_is_kept_and_centred_in_the_region():
    points, radii = srtio3_geometry().points_and_radii()
    policy = ViewPolicy(visible_height=20.0)
    camera = policy.resolve(None, points, radii, 1.5, region=(0.0, 0.0, 1.0, 0.75))
    assert 2 * camera.parallel_scale == pytest.approx(20.0)
    _x0, y0, _x1, y1 = sphere_extent(camera, points, radii, 900, 600)
    assert (y0 + y1) / 2 == pytest.approx(0.375 * 600)
    with pytest.raises(CameraPolicyError, match="does not fit"):
        ViewPolicy(visible_height=9.0).resolve(None, points, radii, 1.5, region=(0, 0, 1, 0.5))


# ----- painting -------------------------------------------------------------------------
def test_layout_scales_with_the_image_and_keeps_its_place(qapp):
    from ycrystal.render.legend import legend_layout

    entries = legend_entries(srtio3_geometry(), SHOWN)
    small = legend_layout(entries, SHOWN, 480, 320)
    large = legend_layout(entries, SHOWN, 4800, 3200)
    for a, b in zip(small.rect.getRect(), large.rect.getRect(), strict=True):
        assert b == pytest.approx(10 * a, rel=1e-9)
    rect = small.rect
    margin = SHOWN.margin * SHOWN.font_size / 100 * 320
    assert rect.center().x() == pytest.approx(240) and rect.bottom() == pytest.approx(320 - margin)
    assert rect.width() > 3 * rect.height()  # one row
    column = legend_layout(entries, replace(SHOWN, layout="vertical", position="left"), 480, 320)
    assert column.rect.height() > 2 * column.rect.width()
    assert column.rect.left() == pytest.approx(margin)
    assert column.rect.center().y() == pytest.approx(160)
    assert legend_layout((), SHOWN, 480, 320) is None


@pytest.mark.parametrize(
    ("x", "y", "inside"), [(0.5, 0.5, True), (0.0, 0.0, True), (1.0, 1.0, True)]
)
def test_custom_positions_stay_inside_the_image(qapp, x, y, inside):
    from ycrystal.render.legend import legend_layout

    entries = legend_entries(srtio3_geometry(), SHOWN)
    settings = replace(SHOWN, position="custom", x=x, y=y)
    rect = legend_layout(entries, settings, 600, 400).rect
    assert rect.left() >= -1e-9 and rect.top() >= -1e-9
    assert rect.right() <= 600 + 1e-9 and rect.bottom() <= 400 + 1e-9
    if (x, y) == (0.5, 0.5):
        assert rect.center().x() == pytest.approx(300) and rect.center().y() == pytest.approx(200)


def test_fit_region_leaves_the_legend_and_its_margin_free(qapp):
    from ycrystal.render.legend import legend_fit_region, legend_layout

    entries = legend_entries(srtio3_geometry(), SHOWN)
    for position in ("bottom", "top", "left", "right"):
        settings = replace(SHOWN, position=position, layout="vertical")
        region = legend_fit_region(entries, settings, 1.5)
        rect = legend_layout(entries, settings, 1500, 1000).rect
        gap = settings.margin * settings.font_size / 100 * 1000
        left, top, right, bottom = region
        free = {
            "bottom": bottom * 1000 == pytest.approx(rect.top() - gap),
            "top": top * 1000 == pytest.approx(rect.bottom() + gap),
            "left": left * 1500 == pytest.approx(rect.right() + gap),
            "right": right * 1500 == pytest.approx(rect.left() - gap),
        }
        assert free[position], position
    assert legend_fit_region(entries, replace(SHOWN, position="custom"), 1.5) is None
    assert legend_fit_region(entries, LegendSettings(), 1.5) is None  # disabled
    huge = replace(SHOWN, font_size=25.0, layout="vertical", spacing=5.0)
    assert legend_fit_region(entries, huge, 1.5) is None  # would leave too little


def test_the_legend_is_painted_onto_the_image_and_nothing_else_changes(qapp, tmp_path):
    from ycrystal.render.legend import draw_legend_on_file, legend_layout

    path = write_png(tmp_path / "scene.png")
    before = pixels(path)
    entries = legend_entries(srtio3_geometry(), SHOWN)
    assert draw_legend_on_file(path, entries, SHOWN)
    after = pixels(path)
    rect = legend_layout(entries, SHOWN, 400, 300).rect
    changed = np.argwhere(np.any(after != before, axis=2))
    assert len(changed)
    (y0, x0), (y1, x1) = changed.min(axis=0), changed.max(axis=0)
    assert rect.left() - 1 <= x0 and x1 <= rect.right() + 1  # only the legend's box
    assert rect.top() - 1 <= y0 and y1 <= rect.bottom() + 1
    for (x, y), entry in zip(marker_centres(entries, SHOWN, 400, 300), entries, strict=True):
        assert np.abs(after[y, x, :3] - rgb255(entry.color)).max() <= 1, entry.element
    text = np.all(after[..., :3] <= 25, axis=2)  # black symbols on the blue-grey image
    assert text.sum() > 50
    assert png_resolution(path.read_bytes()) is None  # no resolution chunk added


def test_transparent_backgrounds_stay_transparent_outside_the_legend(qapp, tmp_path):
    from ycrystal.render.legend import draw_legend_on_file

    path = write_png(tmp_path / "scene.png", mode="RGBA")
    entries = legend_entries(srtio3_geometry(), SHOWN)
    draw_legend_on_file(path, entries, SHOWN)
    after = pixels(path)
    assert after[0, 0, 3] == 0 and after[150, 200, 3] == 0
    for x, y in marker_centres(entries, SHOWN, 400, 300):
        assert after[y, x, 3] == 255
    boxed = replace(SHOWN, background=True, background_opacity=0.5)
    path = write_png(tmp_path / "boxed.png", mode="RGBA")
    draw_legend_on_file(path, entries, boxed)
    alpha = pixels(path)[..., 3]
    assert 120 <= np.median(alpha[alpha > 0]) <= 135  # the half-transparent box


def test_a_disabled_legend_or_one_without_entries_leaves_the_file_untouched(qapp, tmp_path):
    from ycrystal.render.legend import draw_legend_on_file

    path = write_png(tmp_path / "scene.png")
    data = path.read_bytes()
    entries = legend_entries(srtio3_geometry(), SHOWN)
    assert not draw_legend_on_file(path, entries, LegendSettings())
    assert not draw_legend_on_file(path, (), SHOWN)
    assert path.read_bytes() == data


def test_text_colour_background_and_sphere_markers(qapp, tmp_path):
    from ycrystal.render.legend import draw_legend_on_file

    entries = (LegendEntry("H", (1.0, 1.0, 1.0)),)  # white on white needs its outline
    settings = LegendSettings(
        enabled=True, text_color=(0.8, 0.0, 0.0), background=True, background_opacity=1.0
    )
    path = write_png(tmp_path / "scene.png", size=(800, 600), color=(255, 255, 255))
    draw_legend_on_file(path, entries, replace(settings, background_color=(0.0, 0.0, 1.0)))
    image = pixels(path)[..., :3]
    assert np.all(image == (0, 0, 255), axis=-1).sum() > 500  # the opaque blue box
    assert np.all(image == (204, 0, 0), axis=-1).sum() > 50  # red text, fully covered
    x, y = marker_centres(entries, settings, 800, 600)[0]
    ring = image[y, x - 15 : x + 16]
    assert ring.min() < 200  # a darker outline and shading around the white ball


def test_painting_is_identical_for_identical_input(qapp, tmp_path):
    from ycrystal.render.legend import draw_legend_on_file

    entries = legend_entries(srtio3_geometry(), LegendSettings(enabled=True))
    images = []
    for name in ("a.png", "b.png"):
        path = write_png(tmp_path / name)
        draw_legend_on_file(path, entries, LegendSettings(enabled=True))
        images.append(pixels(path))
    assert np.array_equal(*images)


# ----- render jobs ------------------------------------------------------------------------
def job_with_image(tmp_path, legend):
    geometry = srtio3_geometry()
    camera = default_camera(*geometry.points_and_radii(), 400 / 300)
    job = prepare_job(
        geometry, camera, Environment(), RenderSettings(400, 300), tmp_path, legend=legend
    )
    write_png(job.image_path)
    return job


def test_jobs_paint_an_enabled_legend_when_they_finish(qapp, tmp_path):
    job = job_with_image(tmp_path, SHOWN)
    assert [e.element for e in job.legend_entries] == ["Sr", "Ti", "O"]
    assert "legend" not in job.pov_path.read_text().lower()  # not part of the scene
    result = finish_job(job, 0, "")
    assert result.ok
    x, y = marker_centres(job.legend_entries, SHOWN, 400, 300)[0]
    assert np.abs(pixels(job.image_path)[y, x, :3] - rgb255(element_color(38))).max() <= 1


def test_jobs_without_a_legend_keep_the_renderers_file(tmp_path):
    for legend in (None, LegendSettings()):
        job = job_with_image(tmp_path, legend)
        assert job.legend is None and job.legend_entries == ()
        data = job.image_path.read_bytes()
        assert finish_job(job, 0, "").ok
        assert job.image_path.read_bytes() == data


def test_a_legend_that_cannot_be_drawn_fails_the_render_with_a_message(qapp, tmp_path):
    job = job_with_image(tmp_path, SHOWN)
    job.image_path.write_bytes(PNG_SIGNATURE + b"broken")
    result = finish_job(job, 0, "")
    assert not result.ok and result.image_path is None
    assert "legend" in result.message and "could not read" in result.message.lower()


# ----- whole renders without a window ---------------------------------------------------------
def legend_project(legend: LegendSettings = SHOWN, camera: Camera | None = None) -> Project:
    project = Project(perovskite_srtio3(), scene=SceneSettings(legend=legend), camera=camera)
    project.output = replace(project.output, width=480, height=360)
    return project


def test_fitted_command_line_views_leave_room_for_the_legend(qapp):
    from ycrystal.render.legend import legend_layout

    project = legend_project()
    geometry, camera, settings = scene_for(project)
    points, radii = geometry.points_and_radii()
    _x0, _y0, _x1, y1 = sphere_extent(camera, points, radii, 480, 360)
    rect = legend_layout(legend_entries(geometry, SHOWN), SHOWN, 480, 360).rect
    assert y1 < rect.top()  # the structure ends above the legend
    plain = scene_for(legend_project(LegendSettings()))[1]
    assert camera.parallel_scale > plain.parallel_scale  # zoomed out to make room
    saved = scene_for(legend_project(camera=plain))[1]
    assert saved == plain  # a saved camera is never moved


def test_command_line_render_draws_the_legend_without_a_window(qapp, tmp_path):
    """``ycrystal PROJECT --render`` in a new process: the legend is in the PNG."""
    project_path = save_project(tmp_path / "legend.ycrystal", legend_project())
    out = tmp_path / "figure.png"
    env = dict(os.environ, YCRYSTAL_FAKE_COLOR=",".join(map(str, BACKGROUND)))
    env.pop("QT_QPA_PLATFORM", None)
    if sys.platform.startswith("linux"):
        env.pop("DISPLAY", None)  # no display needed
        env.pop("WAYLAND_DISPLAY", None)
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "ycrystal",
            str(project_path),
            "--render",
            str(out),
            "--povray",
            fake_povray(tmp_path),
        ],
        capture_output=True,
        text=True,
        env=env,
        timeout=120,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    image = pixels(out)
    assert image.shape[:2] == (360, 480)
    entries = legend_entries(srtio3_geometry(), SHOWN)
    for (x, y), entry in zip(marker_centres(entries, SHOWN, 480, 360), entries, strict=True):
        assert np.abs(image[y, x, :3] - rgb255(entry.color)).max() <= 2, entry.element
    assert np.all(image[:200, :, :3] == BACKGROUND)  # the upper part is the "render"


@pytest.mark.povray
def test_real_render_has_the_legend_beneath_the_structure(qapp, tmp_path, povray_executable):
    """Acceptance: markers in the element colours, arranged beneath the structure."""
    from ycrystal.render.legend import legend_layout

    project = legend_project()
    out = tmp_path / "srtio3.png"
    result = render_png(project, out, povray_executable)
    assert result.ok, result.message
    image = pixels(out)
    entries = legend_entries(srtio3_geometry(), SHOWN)
    for (x, y), entry in zip(marker_centres(entries, SHOWN, 480, 360), entries, strict=True):
        assert np.abs(image[y, x, :3] - rgb255(entry.color)).max() <= 2, entry.element
    rect = legend_layout(entries, SHOWN, 480, 360).rect
    background = image[2, 2, :3]
    above = image[: int(rect.top()) - 1, :, :3]
    rows = np.flatnonzero(np.any(np.abs(above - background).max(axis=2) > 30, axis=1))
    assert len(rows) and rows.min() < rect.top() / 2  # the structure is drawn above
    gap = image[int(rect.top()) - 3 : int(rect.top()) - 1, :, :3]
    assert np.abs(gap - background).max() <= 30  # nothing of it touches the legend


def test_exported_scenes_say_that_the_legend_is_not_in_them(qapp, tmp_path, capsys):
    from ycrystal.app import main

    project_path = save_project(tmp_path / "legend.ycrystal", legend_project())
    assert main([str(project_path), "--export-pov", str(tmp_path / "scene.pov")]) == 0
    out = capsys.readouterr().out
    assert "legend is added to rendered images only" in out
    assert "legend" not in (tmp_path / "scene.pov").read_text().lower()
    plain = save_project(tmp_path / "plain.ycrystal", legend_project(LegendSettings()))
    assert main([str(plain), "--export-pov", str(tmp_path / "plain.pov")]) == 0
    assert "legend" not in capsys.readouterr().out
