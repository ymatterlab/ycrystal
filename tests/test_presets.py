"""Material, environment, and lighting presets (M4 catalog), thumbnails, and POV-Ray output."""

from dataclasses import replace

import numpy as np
import pytest
from PIL import Image

from ycrystal.core.camera import default_camera
from ycrystal.core.samples import perovskite_srtio3
from ycrystal.core.scene import Environment, SceneSettings, build_geometry
from ycrystal.presets import (
    DEFAULT_ENVIRONMENT,
    DEFAULT_LIGHTING,
    DEFAULT_MATERIAL,
    MATERIAL_CATEGORIES,
    MATERIAL_KINDS,
    PresetError,
    apply_lighting,
    environment_from_preset,
    environments,
    get_environment,
    get_lighting,
    get_material,
    lighting_presets,
    materials,
)
from ycrystal.render.imagecheck import load_rgba
from ycrystal.render.jobs import parse_progress, prepare_job, run_job
from ycrystal.render.pov_writer import (
    RenderSettings,
    render_ini,
    required_includes,
    scene_to_pov,
    write_scene_files,
)
from ycrystal.render.povray import explain_failure, include_directories, missing_includes
from ycrystal.render.thumbnails import (
    THUMBNAIL_SIZE,
    environment_scene,
    load_index,
    material_scene,
    scene_digest,
)


def scene_text(
    material: str = DEFAULT_MATERIAL,
    environment: Environment | None = None,
    settings: SceneSettings | None = None,
) -> str:
    scene = settings or SceneSettings(material=material)
    geometry = build_geometry(perovskite_srtio3(), scene)
    camera = default_camera(*geometry.points_and_radii(), 1.5)
    return scene_to_pov(geometry, camera, environment or Environment(), RenderSettings(300, 200))


# ----- catalog ---------------------------------------------------------------------------
def test_catalog_meets_the_m4_targets():
    mats, envs = materials(), environments()
    assert len(mats) >= 20 and len(envs) >= 12
    assert len({m.id for m in mats}) == len(mats) and len({e.id for e in envs}) == len(envs)
    assert DEFAULT_MATERIAL in {m.id for m in mats}
    assert DEFAULT_ENVIRONMENT in {e.id for e in envs}
    assert DEFAULT_LIGHTING in {light.id for light in lighting_presets()}
    # Every category is used; "custom" is reserved for variants (FR-MATERIAL-01).
    assert {m.category for m in mats} == set(MATERIAL_CATEGORIES) - {"custom"}
    assert {m.kind for m in mats} == set(MATERIAL_KINDS)  # all four declaration kinds
    assert {e.background_mode for e in envs} == {"solid", "gradient", "sky"}
    assert any(e.floor and e.floor_reflection > 0 for e in envs)  # reflective studio floor
    assert any(e.transparent for e in envs)
    # The alpha catalog's ids remain valid (projects saved by M3 refer to them).
    assert {"matte", "satin", "glossy", "metallic", "glass"} <= {m.id for m in mats}
    assert {"white", "transparent", "dark"} <= {e.id for e in envs}


def test_manifest_fields_are_consistent():
    available = include_directories()
    for material in materials():
        assert material.name and material.description and material.provenance
        if material.native:  # native identifiers come with the files that declare them
            assert material.includes, material.id
            assert material.native[0] in material.name, material.id
        if not material.keeps_element_color:
            assert material.live.color is not None, material.id
        if available:
            assert not missing_includes(material.includes), material.id
    for environment in environments():
        get_lighting(environment.lighting)
        assert environment.name and environment.description


def test_bad_ids_are_refused():
    for getter in (get_material, get_environment, get_lighting):
        with pytest.raises(PresetError):
            getter("no-such-preset")


def test_search_by_name_identifier_include_and_category():
    def ids(query):
        return {m.id for m in materials() if m.matches(query)}

    assert ids("gold") == {"gold"}
    assert ids("t_gold_3c") == {"gold"}  # native identifier, any case
    assert "brass" in ids("metals.inc") and "gold" in ids("metals.inc")
    assert ids("glass refraction") <= {m.id for m in materials() if m.category == "transparent"}
    assert {m.id for m in materials() if m.matches("")} == {m.id for m in materials()}
    assert {e.id for e in environments() if e.matches("sky")} == {"sky_clear", "sky_cloudy"}


def test_environment_and_lighting_presets():
    studio = environment_from_preset("studio_dark")
    assert studio.floor and studio.floor_reflection > 0 and studio.reflector
    assert studio.lighting == "bright" and studio.preset == "studio_dark"
    assert get_environment("dark").cell_edge_color[0] > 0.5  # visible on dark grey
    soft = get_lighting("soft")
    default = Environment()
    assert (default.key_light, default.fill_light, default.key_azimuth) == (
        soft.key_light,
        soft.fill_light,
        soft.key_azimuth,
    )
    top = apply_lighting(studio, "top")
    assert top.lighting == "top" and top.key_elevation == get_lighting("top").key_elevation
    assert top.floor == studio.floor  # the background and floor stay
    with pytest.raises(ValueError):
        Environment(background_mode="stripes")
    with pytest.raises(ValueError):
        Environment(floor_reflection=1.5)


# ----- overrides -------------------------------------------------------------------------
def test_material_precedence_and_colours():
    structure = perovskite_srtio3()
    settings = SceneSettings(
        material="matte",
        element_materials=(("O", "glass"), ("Ti", "gold")),
        element_colors=(("Sr", (0.2, 0.4, 0.9)),),
    )
    corner = (0, (0, 0, 0))
    settings = settings.with_atom_materials([corner], "chrome")
    geometry = build_geometry(structure, settings)
    by_id = dict(zip(geometry.atom_ids, geometry.materials, strict=True))
    assert by_id[corner] == "chrome"  # atom > element > default
    assert by_id[(0, (1, 0, 0))] == "matte"  # other images of the same atom keep the default
    assert {m for e, m in zip(geometry.elements, geometry.materials, strict=True) if e == "O"} == {
        "glass"
    }
    rows = {e: i for i, e in enumerate(geometry.elements)}
    np.testing.assert_allclose(geometry.colors[rows["O"]], (1.0, 0.051, 0.051), atol=1e-3)
    assert tuple(geometry.colors[rows["Ti"]]) == get_material("gold").live.color  # own pigment
    sr = geometry.index_of((0, (1, 0, 0)))
    assert tuple(geometry.colors[sr]) == (0.2, 0.4, 0.9)  # colour override
    assert tuple(geometry.colors[geometry.index_of(corner)]) == get_material("chrome").live.color
    # Removing overrides restores the defaults; equal settings compare equal.
    restored = settings.with_atom_materials([corner], None).with_element_material("O", None)
    assert restored == replace(settings, atom_materials=(), element_materials=(("Ti", "gold"),))
    with pytest.raises(PresetError):
        build_geometry(structure, SceneSettings(element_materials=(("O", "unobtainium"),)))


def test_writer_declares_each_material_kind():
    settings = SceneSettings(
        material="satin",
        element_materials=(("Sr", "gold"), ("Ti", "glass"), ("O", "marble")),
    )
    text = scene_text(settings=settings)
    assert '#include "metals.inc"' in text and '#include "textures.inc"' in text
    assert "#declare Ycr_Texture_gold = texture { T_Gold_3C }" in text  # texture kind, shared
    assert "#declare Ycr_Material_Ti_glass = material {" in text  # recipe on the element colour
    assert "interior { ior 1.45 }" in text
    assert "pigment { White_Marble scale 0.6 }" in text  # pigment kind
    # Unit texture space: a unit sphere carrying the texture, then scaled and moved.
    assert "sphere { <0, 0, 0>, 1 texture { Ycr_Texture_marble } scale" in text
    assert "material { Ycr_Material_Ti_glass }" in text
    assert "Native: T_Gold_3C." in text
    geometry = build_geometry(perovskite_srtio3(), settings)
    assert required_includes(geometry) == ("metals.inc", "textures.inc")


def test_native_material_and_finish_identifiers():
    clear = scene_text("glass_clear")
    assert "#declare Ycr_Material_glass_clear = material { M_Glass }" in clear
    polished = scene_text("metal_polished")
    assert "finish { F_MetalD }" in polished and "Ycr_sRGB(" in polished
    stone = scene_text("stone")
    assert stone.index('#include "colors.inc"') < stone.index('#include "stones.inc"')


def test_default_scene_keeps_the_m3_appearance():
    text = scene_text()
    assert "texture { Ycr_Texture_Sr }" in text
    assert "finish { ambient 0.08 diffuse 0.75 specular 0.35 roughness 0.02 }" in text
    assert "No #include files are required." in text
    assert "plane {" not in text and "area_light" not in text and "no_image" not in text


# ----- environments in the scene ------------------------------------------------------------
def test_floor_backdrop_lights_and_reflector():
    studio = scene_text(environment=environment_from_preset("studio_white"))
    assert "// Floor:" in studio and "area_light" in studio and "jitter" not in studio
    sky = scene_text(environment=environment_from_preset("sky_cloudy"))
    assert "light_group {" in sky and "gradient y" in sky and "bozo" in sky
    assert "global_lights off" in sky
    dark = scene_text(environment=environment_from_preset("studio_dark"))
    assert "no_image no_shadow" in dark and "reflection 0.35" in dark
    flat = scene_text(environment=apply_lighting(Environment(), "flat"))
    assert flat.count("shadowless") == 2
    # Transparent output leaves out floor and backdrop.
    clear_studio = replace(environment_from_preset("studio_white"), transparent=True)
    text = scene_text(environment=clear_studio)
    assert "plane {" not in text and "background { color rgbt <0, 0, 0, 1> }" in text
    assert '// Environment "studio_white": background transparent' in text


def test_ini_progress_and_transparent_environment(tmp_path):
    assert "Verbose=on" in render_ini(RenderSettings(), "a.pov", "a.png")
    assert parse_progress("Rendered 480000 of 480000 pixels (100%)") == 100
    assert parse_progress("\rRendered 10 of 40 pixels\rRendered 30 of 40 pixels") == 75
    geometry = build_geometry(perovskite_srtio3())
    camera = default_camera(*geometry.points_and_radii(), 1.5)
    _, ini, _ = write_scene_files(
        tmp_path, "s", geometry, camera, environment_from_preset("transparent"), RenderSettings()
    )
    assert "Output_Alpha=on" in ini.read_text()


def test_missing_include_is_explained():
    message = explain_failure(1, "Parse Error: Cannot open include file metals.inc.")
    assert "(metals.inc)" in message and "povray-includes" in message
    assert missing_includes(["surely-not-installed.inc"]) == ["surely-not-installed.inc"]


# ----- thumbnails ----------------------------------------------------------------------------
def test_every_preset_has_a_current_thumbnail():
    index = load_index()
    for material in materials():
        path = material.thumbnail()
        assert path is not None, f"missing thumbnail for {material.id}"
        with Image.open(path) as image:
            assert image.size == (THUMBNAIL_SIZE, THUMBNAIL_SIZE)
        assert index["materials"].get(material.id) == scene_digest(material_scene(material.id)), (
            f"thumbnail of {material.id} is out of date: run scripts/render_thumbnails.py"
        )
    for environment in environments():
        path = environment.thumbnail()
        assert path is not None, f"missing thumbnail for {environment.id}"
        with Image.open(path) as image:
            assert image.size == (THUMBNAIL_SIZE, THUMBNAIL_SIZE)
            if environment.transparent:
                assert image.mode == "RGBA" and image.getpixel((0, 0))[3] == 0
        digest = scene_digest(environment_scene(environment.id))
        assert index["environments"].get(environment.id) == digest, (
            f"thumbnail of {environment.id} is out of date: run scripts/render_thumbnails.py"
        )


# ----- POV-Ray: every entry renders individually; representative combinations ----------------
def _render(tmp_path, povray, settings, environment, size=(120, 80)):
    geometry = build_geometry(perovskite_srtio3(), settings)
    camera = default_camera(*geometry.points_and_radii(), size[0] / size[1])
    render = RenderSettings(*size, transparent_background=environment.transparent)
    job = prepare_job(geometry, camera, environment, render, parent=tmp_path)
    result = run_job(job, povray, timeout=300)
    assert result.ok, result.message
    return load_rgba(result.image_path)


@pytest.mark.povray
@pytest.mark.parametrize("material", [m.id for m in materials()])
def test_every_material_renders(material, povray_executable, tmp_path):
    rgba = _render(tmp_path, povray_executable, SceneSettings(material=material), Environment())
    assert rgba.shape == (80, 120, 4)
    assert rgba[0, 0, 3] == 255 and tuple(rgba[0, 0, :3]) == (255, 255, 255)
    centre = rgba[30:50, 50:70, :3].astype(int)
    assert np.abs(centre - 255).sum(axis=2).max() > 60  # the structure is drawn


@pytest.mark.povray
@pytest.mark.parametrize("environment", [e.id for e in environments()])
def test_every_environment_renders(environment, povray_executable, tmp_path):
    preset = get_environment(environment)
    settings = SceneSettings(cell_edge_color=preset.cell_edge_color)
    rgba = _render(tmp_path, povray_executable, settings, environment_from_preset(environment))
    assert rgba.shape == (80, 120, 4)
    assert rgba[0, 0, 3] == (0 if preset.transparent else 255)
    assert rgba[40, 60, 3] == 255  # an atom covers the centre
    if preset.background_mode != "solid" and not preset.floor:
        top, bottom = rgba[1, 1, :3].astype(int), rgba[78, 1, :3].astype(int)
        assert np.abs(top - bottom).sum() > 20  # a vertical gradient


@pytest.mark.povray
@pytest.mark.parametrize(
    "material, environment",
    [
        ("glass", "sky_cloudy"),
        ("gem", "gradient_blue"),
        ("chrome", "studio_dark"),
        ("gold", "dark"),
        ("metal_polished", "black"),
        ("marble", "transparent"),
        ("glass_clear", "studio_white"),
    ],
)
def test_representative_combinations(material, environment, povray_executable, tmp_path):
    preset = get_environment(environment)
    settings = SceneSettings(material=material, cell_edge_color=preset.cell_edge_color)
    rgba = _render(tmp_path, povray_executable, settings, environment_from_preset(environment))
    assert rgba.shape == (80, 120, 4)
    assert rgba[0, 0, 3] == (0 if preset.transparent else 255)
    if environment == "sky_cloudy":
        r, g, b = rgba[0:4, :, :3].reshape(-1, 3).astype(float).mean(axis=0)
        assert b > r + 25  # blue sky (with some clouds) above the structure
    if environment == "studio_dark":
        # The reflective floor mirrors bright atoms below the structure.
        assert rgba[70:80, :, :3].max() > rgba[0:4, :, :3].max()


@pytest.mark.povray
def test_mixed_overrides_render_and_floor_shadows(povray_executable, tmp_path):
    settings = SceneSettings(
        material="satin", element_materials=(("Ti", "gold"), ("O", "glass"))
    ).with_atom_materials([(0, (0, 0, 0))], "marble")
    rgba = _render(
        tmp_path, povray_executable, settings, environment_from_preset("studio_grey"), (160, 120)
    )
    assert rgba.shape == (120, 160, 4)
    corner = rgba[2, 2, :3].astype(int)
    assert 60 < corner.mean() < 235  # the grey floor fills the background (not white)
    assert np.ptp(corner) < 12  # neutral grey


def test_appearance_guide_lists_every_preset():
    from pathlib import Path

    guide = (Path(__file__).parents[1] / "docs" / "guide" / "appearance.md").read_text()
    for material in materials():
        assert f"| {material.name}" in guide, material.name
    for environment in environments():
        assert f"| {environment.name} |" in guide, environment.name
    for light in lighting_presets():
        assert f"| {light.name} |" in guide, light.name
