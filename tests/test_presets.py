"""Material and background presets (the M3 alpha catalog) and their POV-Ray output."""

from dataclasses import replace

import pytest

from ycrystal.core.camera import default_camera
from ycrystal.core.samples import perovskite_srtio3
from ycrystal.core.scene import Environment, SceneSettings, build_geometry
from ycrystal.presets import (
    DEFAULT_ENVIRONMENT,
    DEFAULT_MATERIAL,
    PresetError,
    environment_from_preset,
    environments,
    get_environment,
    get_material,
    materials,
)
from ycrystal.render.imagecheck import load_rgba
from ycrystal.render.jobs import parse_progress, prepare_job, run_job
from ycrystal.render.pov_writer import RenderSettings, render_ini, scene_to_pov, write_scene_files


def scene_text(material: str = DEFAULT_MATERIAL, environment: Environment | None = None) -> str:
    geometry = build_geometry(perovskite_srtio3(), SceneSettings(material=material))
    points, radii = geometry.points_and_radii()
    camera = default_camera(points, radii, 1.5)
    return scene_to_pov(geometry, camera, environment or Environment(), RenderSettings(300, 200))


def test_catalog_size_and_ids():
    ids = [m.id for m in materials()]
    assert 4 <= len(ids) <= 6 and len(set(ids)) == len(ids)
    assert DEFAULT_MATERIAL in ids
    assert [e.id for e in environments()] == ["white", "transparent", "dark"]
    assert DEFAULT_ENVIRONMENT == "white"
    for material in materials():
        assert material.name and material.description and material.finish
        assert material.keeps_element_color and material.includes == ()
        assert 0 < material.live.opacity <= 1
    assert get_material("glass").declaration == "material"
    assert {m.declaration for m in materials() if m.id != "glass"} == {"texture"}
    with pytest.raises(PresetError):
        get_material("unobtainium")
    with pytest.raises(PresetError):
        get_environment("unobtainium")


def test_default_material_keeps_the_original_finish():
    text = scene_text()
    assert (
        "#declare Ycr_Finish = finish { ambient 0.08 diffuse 0.75 specular 0.35 roughness 0.02 }"
        in text
    )
    assert "texture { Ycr_Texture_Sr }" in text and "material {" not in text


def test_glass_is_written_as_a_material_with_interior():
    text = scene_text("glass")
    assert "#declare Ycr_Material_O = material {" in text
    assert "filter 0.8" in text and "interior { ior 1.45 }" in text
    assert "material { Ycr_Material_Ti }" in text
    assert "texture { Ycr_Texture_Ti }" not in text
    assert "#declare Ycr_Texture_Cell" in text  # cell edges stay opaque


def test_include_files_are_listed_and_declared(monkeypatch):
    metal = replace(get_material("metallic"), includes=("metals.inc",))
    monkeypatch.setattr("ycrystal.presets.get_material", lambda _id: metal)
    text = scene_text("metallic")
    assert "// Requires standard POV-Ray include files: metals.inc" in text
    assert '#include "metals.inc"' in text
    assert "No #include files are required" not in text


def test_environment_presets():
    dark = environment_from_preset("dark", Environment(key_light=0.7))
    assert dark.preset == "dark" and dark.key_light == 0.7 and not dark.transparent
    assert get_environment("dark").cell_edge_color[0] > 0.5  # visible on dark grey
    clear = environment_from_preset("transparent")
    assert clear.transparent
    assert "background { color rgbt <0, 0, 0, 1> }" in scene_text(environment=clear)


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


@pytest.mark.povray
@pytest.mark.parametrize("material", [m.id for m in materials()])
@pytest.mark.parametrize("environment", [e.id for e in environments()])
def test_every_preset_combination_renders(material, environment, povray_executable, tmp_path):
    preset = get_environment(environment)
    scene = SceneSettings(material=material, cell_edge_color=preset.cell_edge_color)
    geometry = build_geometry(perovskite_srtio3(), scene)
    camera = default_camera(*geometry.points_and_radii(), 1.5)
    job = prepare_job(
        geometry,
        camera,
        environment_from_preset(environment),
        RenderSettings(120, 80),
        parent=tmp_path,
    )
    result = run_job(job, povray_executable, timeout=120)
    assert result.ok, result.message
    rgba = load_rgba(result.image_path)
    assert rgba.shape == (80, 120, 4)
    assert rgba[0, 0, 3] == (0 if preset.transparent else 255)
    assert rgba[40, 60, 3] > 0  # an atom covers the centre (glass lets some alpha through)
