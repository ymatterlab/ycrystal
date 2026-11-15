"""FR-VECTOR-01: atom-attached vectors (records, attachment, geometry, export, persistence)."""

import json
import re
from dataclasses import replace

import numpy as np
import pytest
from PIL import Image

from ycrystal.core.camera import Camera, default_camera
from ycrystal.core.lighting import resolve_lighting
from ycrystal.core.measure import atom_position
from ycrystal.core.samples import perovskite_srtio3
from ycrystal.core.scene import Environment, SceneSettings, build_geometry
from ycrystal.core.structure import Structure
from ycrystal.core.vectors import (
    MAX_HEAD_FRACTION,
    MIN_ARROW_LENGTH,
    ZERO_MODULUS,
    VectorRecord,
    VectorSet,
    VectorStyle,
    arrow_for,
)
from ycrystal.io.project import Project, ProjectError, load_project, save_project
from ycrystal.io.style import Style, apply_style, load_style, save_style
from ycrystal.presets import register_definition
from ycrystal.presets.custom import base_definition
from ycrystal.render.jobs import prepare_job, run_job
from ycrystal.render.pov_writer import RenderSettings, scene_to_pov

UP = VectorRecord((0.0, 0.0, 2.2))
DOWN = VectorRecord((0.0, 0.0, -2.2))
HOST = (0, (0, 0, 0))


def bcc_iron():
    """Synthetic two-atom cubic cell (a = 2.87 Å): two Fe sites, documented example only."""
    a = 2.87
    return Structure(
        cell=np.eye(3) * a,
        positions=np.array([[0, 0, 0], [a / 2, a / 2, a / 2]]),
        numbers=[26, 26],
        labels=["Fe1", "Fe2"],
    )


def hexagonal():
    cell = np.array([[3.0, 0, 0], [-1.5, 1.5 * np.sqrt(3), 0], [0, 0, 5.0]])
    frac = np.array([[1 / 3, 2 / 3, 0.25], [2 / 3, 1 / 3, 0.75]])
    return Structure(cell=cell, positions=frac @ cell, numbers=[26, 26], labels=["Fe1", "Fe2"])


def arrows_by_host(geometry):
    return {arrow.host: arrow for arrow in geometry.arrows}


# ----- records and geometry ------------------------------------------------------------------
def test_endpoints_placements_and_length_modes():
    r = np.array([1.0, 2.0, 3.0])
    v = VectorRecord((3.0, 0.0, 4.0))  # |v| = 5, u = (0.6, 0, 0.8)
    u = np.array([0.6, 0.0, 0.8])
    centred = arrow_for(HOST, r, v, VectorStyle(length=2.0, head_length=0.5))
    np.testing.assert_allclose(centred.tail, r - u)
    np.testing.assert_allclose(centred.tip, r + u)
    np.testing.assert_allclose(centred.base, r + u - 0.5 * u)  # head inside the length
    assert centred.length == pytest.approx(2.0)
    tail = arrow_for(HOST, r, v, VectorStyle(length=2.0, placement="tail"))
    np.testing.assert_allclose(tail.tail, r)
    np.testing.assert_allclose(tail.tip, r + 2 * u)
    proportional = arrow_for(HOST, r, v, VectorStyle(length_mode="proportional", scale=0.3))
    assert proportional.length == pytest.approx(1.5)  # 0.3 Å per unit × 5
    reverse = arrow_for(HOST, r, v.reversed(), VectorStyle(length=2.0))
    np.testing.assert_allclose(reverse.tip, centred.tail)
    np.testing.assert_allclose(reverse.tail, centred.tip)
    assert v.reversed().components == (-3.0, 0.0, -4.0) and v.reversed().reversed() == v
    # Along each axis.
    for axis in range(3):
        comps = [0.0, 0.0, 0.0]
        comps[axis] = -1.0
        arrow = arrow_for(HOST, (0, 0, 0), VectorRecord(comps, "direction"), VectorStyle(length=1))
        assert arrow.tip[axis] == pytest.approx(-0.5) and arrow.tail[axis] == pytest.approx(0.5)


def test_short_arrows_zero_and_invalid_values():
    style = VectorStyle(length_mode="proportional", scale=0.1, head_length=0.5, head_radius=0.2)
    short = arrow_for(HOST, (0, 0, 0), VectorRecord((0, 0, 1.0)), style)  # L = 0.1 Å
    assert short.length == pytest.approx(0.1)
    head = np.linalg.norm(np.subtract(short.tip, short.base))
    assert head == pytest.approx(MAX_HEAD_FRACTION * 0.1)
    factor = MAX_HEAD_FRACTION * 0.1 / 0.5
    assert short.head_radius == pytest.approx(0.2 * factor)
    assert short.shaft_radius == pytest.approx(style.shaft_radius * factor)
    zero = VectorRecord((0.0, 0.0, 0.0))
    assert zero.is_zero and zero.modulus == 0.0 and arrow_for(HOST, (0, 0, 0), zero, style) is None
    tiny = VectorRecord((0.0, ZERO_MODULUS / 2, 0.0))
    assert tiny.is_zero and arrow_for(HOST, (0, 0, 0), tiny, VectorStyle()) is None
    small = VectorRecord((0.0, 1e-6, 0.0))  # not zero, but too short when proportional
    assert not small.is_zero
    assert arrow_for(HOST, (0, 0, 0), small, VectorStyle(length_mode="proportional")) is None
    assert arrow_for(HOST, (0, 0, 0), small, VectorStyle()).length == VectorStyle().length
    assert MIN_ARROW_LENGTH > 0
    hidden = replace(UP, visible=False)
    assert arrow_for(HOST, (0, 0, 0), hidden, VectorStyle()) is None
    for bad in ((float("nan"), 0, 0), (0, float("inf"), 0), (1, 2), ("x", 0, 0)):
        with pytest.raises(ValueError):
            VectorRecord(bad)
    with pytest.raises(ValueError, match="meaning"):
        VectorRecord((0, 0, 1), "spin current")
    for bad in ({"length": 0}, {"scale": -1}, {"head_radius": float("nan")}, {"placement": "x"}):
        with pytest.raises(ValueError):
            VectorStyle(**bad)
    assert UP.text() == "(0.000, 0.000, 2.200) μB, |v| = 2.200 μB"


def test_geometry_does_not_depend_on_camera_or_radii():
    structure = bcc_iron()
    vectors = VectorSet(((0, UP), (1, DOWN)))
    small = build_geometry(structure, SceneSettings(radius_scale=0.2, vectors=vectors))
    large = build_geometry(structure, SceneSettings(radius_scale=0.9, vectors=vectors))
    assert small.arrows == large.arrows and len(small.arrows) == len(small)
    camera = default_camera(*small.points_and_radii(), 1.5)
    for moved in (camera.orbit(azimuth=70, elevation=-20), camera.roll(30), camera.zoom(3)):
        assert build_geometry(structure, SceneSettings(vectors=vectors)).arrows == small.arrows
        assert moved != camera  # the camera never enters arrow resolution


# ----- attachment and periodicity ------------------------------------------------------------
def test_source_defaults_overrides_suppression_and_no_inferred_signs():
    structure = bcc_iron()
    vectors = VectorSet(sources=((0, UP), (1, DOWN)))  # opposite moments, same element
    settings = SceneSettings(vectors=vectors, repetitions=(2, 1, 1))
    geometry = build_geometry(structure, settings)
    arrows = arrows_by_host(geometry)
    for atom_id, arrow in arrows.items():  # every image of a source: same components
        assert arrow.components == (UP if atom_id[0] == 0 else DOWN).components
        np.testing.assert_allclose(
            0.5 * (np.add(arrow.tail, arrow.tip)), atom_position(structure, atom_id)
        )
    assert {a.components for a in arrows.values()} == {UP.components, DOWN.components}
    corner, other = (0, (1, 0, 0)), (0, (2, 1, 1))
    canted = VectorRecord((1.0, 0.0, 1.0), "direction")
    vectors = vectors.with_images([corner], canted).with_images([other], None, suppress=True)
    arrows = arrows_by_host(build_geometry(structure, replace(settings, vectors=vectors)))
    assert arrows[corner].components == canted.components and arrows[corner].meaning == "direction"
    assert other not in arrows and (0, (0, 0, 0)) in arrows  # suppression on one image only
    assert vectors.effective(other) is None and vectors.effective((0, (0, 1, 0))) == UP
    restored = vectors.with_images([other], None)  # removing the override: default again
    assert restored.effective(other) == UP


def test_boundary_images_non_orthogonal_cell_hiding_and_repetitions():
    hexa = hexagonal()
    vectors = VectorSet(sources=((0, VectorRecord((1.0, 1.0, 0.0))),))
    geometry = build_geometry(hexa, SceneSettings(vectors=vectors, repetitions=(2, 2, 1)))
    hosts = [a.host for a in geometry.arrows]
    assert len(hosts) == 4 and all(h[0] == 0 for h in hosts)
    for arrow in geometry.arrows:
        np.testing.assert_allclose(
            0.5 * np.add(arrow.tail, arrow.tip), atom_position(hexa, arrow.host), atol=1e-12
        )
        assert arrow.components == (1.0, 1.0, 0.0)  # Cartesian, not lattice coordinates
    # An image override outside the displayed block is kept but draws nothing.
    far = (1, (1, 1, 0))
    override = VectorSet(images=((far, UP),))
    shown = build_geometry(hexa, SceneSettings(vectors=override, repetitions=(2, 2, 1)))
    assert far in arrows_by_host(shown)
    shrunk = SceneSettings(vectors=override, repetitions=(1, 1, 1))
    assert build_geometry(hexa, shrunk).arrows == () and shrunk.vectors == override
    hidden = SceneSettings(vectors=override, repetitions=(2, 2, 1), hidden=frozenset({far}))
    assert build_geometry(hexa, hidden).arrows == ()
    # Perovskite: a corner default reaches all eight boundary images.
    srtio3 = build_geometry(perovskite_srtio3(), SceneSettings(vectors=VectorSet(((0, UP),))))
    assert len(srtio3.arrows) == 8


# ----- framing, lighting, export -------------------------------------------------------------
def test_bounds_fit_lighting_and_floor_include_arrows_correctly():
    structure = bcc_iron()
    base = SceneSettings()
    long_down = VectorSet(((0, VectorRecord((0, 0, -1.0), "direction")),))
    style = VectorStyle(length=12.0, placement="tail")
    with_arrows = build_geometry(structure, replace(base, vectors=long_down, vector_style=style))
    without = build_geometry(structure, base)
    points, radii = with_arrows.points_and_radii()
    lowest_tip = min(a.tip[2] for a in with_arrows.arrows)
    assert lowest_tip == pytest.approx(-12.0)
    assert (points[:, 2] - radii).min() <= lowest_tip  # framing includes the tips
    # Lighting uses the atom/cell sphere only: a vector change does not move the lights.
    assert with_arrows.bounding_sphere()[1] == without.bounding_sphere()[1]
    camera = default_camera(*without.points_and_radii(), 1.5)
    rig_a, rig_b = (
        resolve_lighting(Environment(), camera, without),
        resolve_lighting(Environment(), camera, with_arrows),
    )
    np.testing.assert_array_equal(rig_a.key.position, rig_b.key.position)
    # Fit includes the arrow: a larger frame.
    fitted = camera.fitted(*with_arrows.points_and_radii(), 1.5)
    assert fitted.parallel_scale > camera.fitted(*without.points_and_radii(), 1.5).parallel_scale
    # The floor lies below the lowest arrow tip as seen in the frame.
    front = Camera((0, -40, 0), (0, 0, 0), (0, 0, 1), parallel_scale=10)
    env = Environment(floor=True)
    text = scene_to_pov(with_arrows, front, env, RenderSettings(300, 200))
    normal, height = re.search(r"plane \{ <([^>]*)>, ([-\d.e]+)", text).groups()
    normal = np.array([float(v) for v in normal.split(",")])
    assert float(height) <= np.array(with_arrows.arrows[0].tip) @ normal + 1e-9


def test_writer_arrows_match_the_shared_geometry():
    structure = bcc_iron()
    settings = SceneSettings(vectors=VectorSet(((0, UP), (1, DOWN))))
    geometry = build_geometry(structure, settings)
    camera = default_camera(*geometry.points_and_radii(), 1.5)
    text = scene_to_pov(geometry, camera, Environment(), RenderSettings(300, 200))
    vec = r"<([-\d.e]+), ([-\d.e]+), ([-\d.e]+)>"
    cylinders = re.findall(
        rf"^cylinder \{{ {vec}, {vec}, ([\d.e]+) texture \{{ Ycr_Texture_Arrow", text, re.M
    )
    cones = re.findall(
        rf"^cone \{{ {vec}, ([\d.e]+), {vec}, 0 texture \{{ Ycr_Texture_Arrow", text, re.M
    )
    assert len(cylinders) == len(cones) == len(geometry.arrows)
    for arrow, cyl, cone in zip(geometry.arrows, cylinders, cones, strict=True):
        values = [float(x) for x in cyl]
        np.testing.assert_allclose(values[:3], arrow.tail, atol=1e-6)
        np.testing.assert_allclose(values[3:6], arrow.base, atol=1e-6)
        assert values[6] == pytest.approx(arrow.shaft_radius)
        values = [float(x) for x in cone]
        np.testing.assert_allclose(values[:3], arrow.base, atol=1e-6)
        assert values[3] == pytest.approx(arrow.head_radius)
        np.testing.assert_allclose(values[4:7], arrow.tip, atol=1e-6)
    assert "// Magnetic moment on atom #1 Fe image (0, 0, 0): (0, 0, 2.2) mu_B" in text
    assert "#declare Ycr_Texture_Arrow = texture" in text  # independent arrow colour
    # Without vectors the scene has no arrow section (unchanged output).
    plain = scene_to_pov(build_geometry(structure), camera, Environment(), RenderSettings(300, 200))
    assert "Vectors (" not in plain and "Ycr_Texture_Arrow" not in plain
    # A custom material used only on arrows is declared with its include.
    marble = register_definition(base_definition("marble").with_values(pattern_scale=2.0))
    arrowed = replace(settings, vector_style=VectorStyle(material=marble.id))
    text = scene_to_pov(
        build_geometry(structure, arrowed), camera, Environment(), RenderSettings(300, 200)
    )
    assert f"Ycr_Texture_{marble.id}" in text and '#include "textures.inc"' in text


# ----- persistence ---------------------------------------------------------------------------
def test_projects_round_trip_and_styles_never_carry_vectors(tmp_path):
    structure = bcc_iron()
    precise = VectorRecord((0.1 + 0.2, -1 / 3, 2.0**-30), "moment")
    marble = register_definition(base_definition("marble").with_values(pattern_scale=1.7))
    vectors = (
        VectorSet(sources=((0, precise), (1, DOWN)))
        .with_images([(0, (1, 0, 0))], VectorRecord((1, 0, 0), "direction", visible=False))
        .with_images([(1, (0, 0, 0))], None, suppress=True)
    )
    style = VectorStyle(
        placement="tail",
        length_mode="proportional",
        scale=0.75,
        material=marble.id,
        color=(0.1, 0.4, 0.9),
    )
    scene = SceneSettings(vectors=vectors, vector_style=style)
    path = save_project(tmp_path / "moments.ycrystal", Project(structure, scene=scene))
    data = json.loads(path.read_text())
    assert data["scene"]["vectors"]["images"][1] == {
        "atom": 1,
        "image": [0, 0, 0],
        "suppressed": True,
    }
    assert marble.id in [m["id"] for m in data["materials"]]  # arrow-only custom material
    from test_custom_materials import forget_custom

    forget_custom()  # a clean profile
    again = load_project(path)
    assert again.scene.vectors == vectors and again.scene.vector_style == style
    assert again.scene.vectors.sources[0][1].components == precise.components  # exact
    for example in __import__("pathlib").Path("examples").glob("*.ycrystal"):
        if "vector" not in example.name:
            assert len(load_project(example).scene.vectors) == 0  # older projects
    data["scene"]["vectors"]["sources"][0]["atom"] = 7
    (tmp_path / "bad.ycrystal").write_text(json.dumps(data))
    with pytest.raises(ProjectError, match="attached to atom #8"):
        load_project(tmp_path / "bad.ycrystal")
    # Styles carry the arrow appearance, never vectors; import keeps the target's vectors.
    saved = save_style(
        tmp_path / "look.ycstyle", Style.from_state(structure, scene, Environment(), (800, 600))
    )
    assert "vectors" not in json.loads(saved.read_text())["scene"]
    loaded = load_style(saved)
    target_vectors = VectorSet(((0, VectorRecord((0, 1, 0))),))
    result = apply_style(
        loaded,
        structure,
        SceneSettings(vectors=target_vectors),
        Environment(),
        (100, 100),
        ("appearance", "display", "environment", "output"),
    )
    assert result.scene.vectors == target_vectors and result.scene.vector_style == style


# ----- real POV-Ray ---------------------------------------------------------------------------
GREEN = (0.1, 0.75, 0.15)


def render(structure, vectors, povray_executable, style=None, size=(240, 180)):
    settings = SceneSettings(
        radius_scale=0.25, vectors=vectors, vector_style=style or VectorStyle(color=GREEN)
    )
    geometry = build_geometry(structure, settings)
    camera = Camera.looking_along((0.3, 1.0, -0.25), (0, 0, 1)).fitted(
        *geometry.points_and_radii(), size[0] / size[1]
    )
    job = prepare_job(geometry, camera, Environment(), RenderSettings(*size, antialias=False))
    try:
        result = run_job(job, povray_executable, timeout=120)
        assert result.ok, result.message
        return geometry, camera, np.asarray(Image.open(result.image_path).convert("RGB"), int)
    finally:
        job.cleanup()


def arrow_pixels(image):
    """Pixels of the green test arrows (iron atoms are orange, the background white)."""
    r, g, b = image[..., 0], image[..., 1], image[..., 2]
    return np.argwhere((g > 90) & (r < 0.6 * g) & (b < 0.6 * g))


@pytest.mark.povray
def test_rendered_ferro_antiferro_and_canted_examples(povray_executable):
    structure = bcc_iron()
    examples = {
        "ferromagnetic": VectorSet(((0, UP), (1, UP))),
        "antiferromagnetic": VectorSet(((0, UP), (1, DOWN))),
        "canted": VectorSet(((0, VectorRecord((0.8, 0, 2.0))), (1, VectorRecord((-0.8, 0, -2.0))))),
    }
    tops = {}
    for name, vectors in examples.items():
        geometry, camera, image = render(structure, vectors, povray_executable)
        found = arrow_pixels(image)
        assert len(found) > 50, name  # arrows are drawn and lit
        # The body-centre atom's arrow tip lies where the shared geometry projects it.
        centre = next(a for a in geometry.arrows if a.host == (1, (0, 0, 0)))
        x, y = camera.project(np.array([centre.tip]), *image.shape[1::-1])[0]
        near = found[(np.abs(found[:, 1] - x) < 6) & (np.abs(found[:, 0] - y) < 6)]
        tops[name] = len(near)
    assert tops["ferromagnetic"] > 0 and tops["antiferromagnetic"] > 0 and tops["canted"] > 0
    _, _, none = render(structure, VectorSet(), povray_executable)
    assert len(arrow_pixels(none)) == 0  # no vectors: no arrows


def test_eye_and_backdrop_stay_clear_of_long_arrows():
    structure = bcc_iron()
    up, down = VectorRecord((0, 0, 1.0), "direction"), VectorRecord((0, 0, -1.0), "direction")
    style = VectorStyle(length=20.0, placement="tail", color=(0.2, 0.3, 0.9))
    settings = SceneSettings(vectors=VectorSet(((0, up), (1, down))), vector_style=style)
    geometry = build_geometry(structure, settings)
    camera = Camera((1.4, 1.4, 30.0), (1.4, 1.4, 1.4), (0, 1, 0), parallel_scale=6.0)
    env = Environment(background_mode="gradient", background_bottom=(0.2, 0.2, 0.3))
    text = scene_to_pov(geometry, camera, env, RenderSettings(300, 200))
    toward = max(a.tip[2] for a in geometry.arrows)  # tips toward the camera (+z) ...
    away = min(a.tip[2] for a in geometry.arrows)  # ... and away from it
    assert toward > 20 and away < -18
    eye_z = float(re.search(r"location\s+<([^>]*)>", text).group(1).split(",")[2])
    assert eye_z > toward  # the orthographic eye lies in front of every tip
    normal, distance = re.search(r"^plane \{ <([^>]*)>, ([-\d.e]+)", text, re.M).groups()
    assert [float(v) for v in normal.split(",")] == [0.0, 0.0, 1.0]  # backdrop facing us
    assert float(distance) < away  # the backdrop plane z = d lies behind the far tips
    declaration = text.split("#declare Ycr_Texture_Arrow")[1].split("}")[0]
    assert "Ycr_sRGB(0.2000, 0.3000, 0.9000)" in declaration  # the arrow's own colour
