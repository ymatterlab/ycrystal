"""FR-MATERIAL-01: custom material variants (definitions, rendering, persistence)."""

import json

import numpy as np
import pytest
from PIL import Image

from ycrystal import presets
from ycrystal.core.camera import Camera
from ycrystal.core.samples import perovskite_srtio3, triclinic_marker
from ycrystal.core.scene import Environment, SceneSettings, build_geometry
from ycrystal.core.structure import Structure
from ycrystal.io.project import Project, ProjectError, load_project, save_project
from ycrystal.io.style import Style, apply_style, load_style, save_style
from ycrystal.presets import PresetError, get_material, register_definition
from ycrystal.presets.custom import (
    SCHEMAS,
    DefinitionError,
    MaterialDefinition,
    base_definition,
    schema_for,
)
from ycrystal.render.jobs import prepare_job, run_job
from ycrystal.render.pov_writer import RenderSettings, _declaration, scene_to_pov


def tokens(text):
    out = []
    for token in text.replace("{", " { ").replace("}", " } ").split():
        try:
            out.append(round(float(token), 9))
        except ValueError:
            out.append(token)
    return out


def declaration(material, color=(0.5, 0.4, 0.3)):
    return "\n".join(_declaration(material, "X", color))


def forget_custom():
    """A clean profile: no registered custom materials."""
    presets._CUSTOM.clear()
    presets._DEFINITIONS.clear()
    presets._LISTED.clear()


@pytest.fixture(autouse=True)
def isolated_registry():
    """Keep variants registered here out of other test modules."""
    yield
    forget_custom()


# ----- definitions ----------------------------------------------------------------------------
def test_untouched_variants_equal_the_built_in_recipes():
    assert set(SCHEMAS) == {
        "matte", "satin", "glossy", "ceramic", "plastic", "glass", "glass_frosted", "gem",
        "marble", "jade", "granite", "stone", "wood",
    }  # fmt: skip
    for base in SCHEMAS:
        built_in, variant = get_material(base), base_definition(base).material()
        assert tokens(declaration(variant)) == tokens(declaration(built_in)), base
        for field in ("kind", "keeps_element_color", "includes", "texture_space", "native"):
            assert getattr(variant, field) == getattr(built_in, field), (base, field)
        assert variant.custom and variant.base == base and variant.category == "custom"
        assert get_material(base) == built_in  # built-ins stay unchanged


def test_each_control_changes_its_pov_property():
    satin = base_definition("satin")
    text = declaration(satin.with_values(diffuse=0.6).material())
    assert "diffuse 0.6" in text
    text = declaration(satin.with_values(specular=0.9, roughness=0.004).material())
    assert "specular 0.9 roughness 0.004" in text
    assert "reflection" not in declaration(satin.material())
    assert "reflection 0.3" in declaration(satin.with_values(reflection=0.3).material())
    plastic = declaration(
        base_definition("plastic").with_values(phong=0.9, phong_size=150).material()
    )
    assert "phong 0.9 phong_size 150" in plastic
    glass = declaration(base_definition("glass").with_values(filter=0.5, ior=1.9).material())
    assert "filter 0.5" in glass and "interior { ior 1.9 }" in glass
    frosted = base_definition("glass_frosted").with_values(bump_strength=1.2, bump_scale=0.1)
    assert "normal { bumps 1.2 scale 0.1 }" in declaration(frosted.material())
    gem = declaration(base_definition("gem").with_values(reflection=0.5).material())
    assert "reflection { 0.05 0.5 fresnel on }" in gem and "conserve_energy" in gem
    marble = declaration(base_definition("marble").with_values(pattern_scale=1.2).material())
    assert "pigment { White_Marble scale 1.2 }" in marble
    stone = declaration(base_definition("stone").with_values(pattern_scale=2.0).material())
    assert "texture { T_Stone25 scale 2 }" in stone
    # Live approximation follows the parameters (VTK is not the reference).
    live = base_definition("glass").with_values(filter=0.2).material().live
    assert live.opacity > get_material("glass").live.opacity
    assert satin.with_values(specular=0.9).material().live.specular == 0.9


def test_invalid_definitions_are_rejected():
    satin = base_definition("satin")
    for bad in (
        {"specular": 1.5},
        {"roughness": 0.0},
        {"diffuse": float("nan")},
        {"reflection": float("inf")},
    ):
        with pytest.raises(DefinitionError, match="must be between"):
            satin.with_values(**bad)
    with pytest.raises(DefinitionError, match="Unknown parameters"):
        satin.with_values(ior=1.5)
    with pytest.raises(DefinitionError, match="name"):
        satin.renamed("   ")
    with pytest.raises(DefinitionError, match="T_Gold_3C"):
        schema_for("gold")
    with pytest.raises(DefinitionError, match="not known"):
        base_definition("unobtainium")
    data = satin.to_dict()
    with pytest.raises(DefinitionError, match="newer Ycrystal"):
        MaterialDefinition.from_dict({**data, "version": 2})
    with pytest.raises(DefinitionError, match="does not match"):
        MaterialDefinition.from_dict(
            {**data, "parameters": {**data["parameters"], "specular": 0.5}}
        )
    del data["parameters"]["roughness"]
    with pytest.raises(DefinitionError, match="missing roughness"):
        MaterialDefinition.from_dict({**data, "id": None})


def test_ids_are_content_derived_and_never_collide():
    a = base_definition("satin").with_values(specular=0.6).renamed("Shiny")
    same = base_definition("satin").with_values(specular=0.6).renamed("Shiny")
    other_name = a.renamed("Shiny 2")
    assert a.id == same.id and a.id != other_name.id and a.id.startswith("custom_satin_")
    assert a.id not in {m.id for m in presets.materials()}
    material = register_definition(a)
    assert register_definition(same) is material  # idempotent
    hidden = register_definition(a.with_values(specular=0.61), listed=False)
    assert get_material(hidden.id) is hidden
    listed = {m.id for m in presets.custom_materials()}
    assert a.id in listed and hidden.id not in listed
    with pytest.raises(PresetError):
        get_material("custom_satin_0000000000")


# ----- scene, export, persistence -------------------------------------------------------------
def variant_scene():
    shiny = register_definition(base_definition("satin").with_values(specular=0.8).renamed("Shiny"))
    glass = register_definition(
        base_definition("glass").with_values(ior=1.7).renamed("Dense glass")
    )
    marble = register_definition(base_definition("marble").with_values(pattern_scale=1.5))
    scene = (
        SceneSettings(material=shiny.id)
        .with_element_material("O", glass.id)
        .with_atom_materials([(0, (1, 0, 0)), (2, (0, 0, 1))], marble.id)  # periodic images
    )
    return scene, shiny, glass, marble


def test_precedence_periodic_images_and_bond_halves():
    scene, shiny, glass, marble = variant_scene()
    geometry = build_geometry(perovskite_srtio3(), scene)
    table = dict(zip(geometry.atom_ids, geometry.materials, strict=True))
    assert table[(0, (0, 0, 0))] == shiny.id and table[(0, (1, 0, 0))] == marble.id
    assert table[(2, (0, 0, 0))] == glass.id and table[(2, (0, 0, 1))] == marble.id
    camera = Camera((2, 2, 40), (2, 2, 2), (0, 1, 0), parallel_scale=5)
    text = scene_to_pov(geometry, camera, Environment(), RenderSettings(200, 150))
    assert f'// Material "{shiny.id}": Shiny. Custom variant of Satin: specular amount 0.8.' in text
    assert "interior { ior 1.7 }" in text and "White_Marble scale 1.5" in text
    half_bonds = [line for line in text.splitlines() if line.startswith("cylinder")]
    assert any(f"Ycr_Material_O_{glass.id}" in line for line in half_bonds)
    assert any("Ycr_Texture_Ti" in line for line in half_bonds)  # Ti: the default variant
    assert '#include "textures.inc"' in text  # marble's standard include, still external


def test_projects_and_styles_reopen_on_a_clean_profile(tmp_path):
    scene, shiny, glass, marble = variant_scene()
    project = Project(perovskite_srtio3(), scene=scene)
    path = save_project(tmp_path / "variants.ycrystal", project)
    data = json.loads(path.read_text())
    assert [entry["id"] for entry in data["materials"]] == sorted([shiny.id, glass.id, marble.id])
    camera = Camera((2, 2, 40), (2, 2, 2), (0, 1, 0), parallel_scale=5)
    before = scene_to_pov(
        build_geometry(project.structure, scene), camera, Environment(), RenderSettings(80, 60)
    )
    style = save_style(
        tmp_path / "look.ycstyle",
        Style.from_state(project.structure, scene, Environment(), (800, 600)),
    )
    forget_custom()
    again = load_project(path)
    assert again.scene == scene
    after = scene_to_pov(
        build_geometry(again.structure, again.scene), camera, Environment(), RenderSettings(80, 60)
    )
    assert after.splitlines()[2:] == before.splitlines()[2:]  # same declarations (time stamp aside)
    forget_custom()
    loaded = load_style(style)
    result = apply_style(
        loaded, triclinic_marker(), SceneSettings(), Environment(), (100, 100), ("appearance",)
    )
    assert (
        result.scene.material == shiny.id and dict(result.scene.element_materials)["O"] == glass.id
    )
    assert result.scene.atom_materials == ()  # incompatible structure: per-atom left out
    # Damaged or incomplete files fail with an explanation.
    data["materials"][0]["parameters"]["diffuse"] = 0.123
    (tmp_path / "tampered.ycrystal").write_text(json.dumps(data))
    with pytest.raises(ProjectError, match="does not match its parameters"):
        load_project(tmp_path / "tampered.ycrystal")
    data["materials"] = []
    forget_custom()
    (tmp_path / "missing.ycrystal").write_text(json.dumps(data))
    with pytest.raises(ProjectError, match="does not contain its definition"):
        load_project(tmp_path / "missing.ycrystal")


# ----- real POV-Ray renders -------------------------------------------------------------------
def render(material_id, povray_executable, size=64):
    structure = Structure(
        cell=np.zeros((3, 3)), positions=np.zeros((1, 3)), numbers=[26], labels=["Fe"],
        pbc=(False, False, False),
    )  # fmt: skip
    geometry = build_geometry(structure, SceneSettings(radius_scale=3.0, material=material_id))
    camera = Camera((0, 0, 30), (0, 0, 0), (0, 1, 0), parallel_scale=4.5)
    env = Environment(background=(0.2, 0.3, 0.6), reflector=True)
    job = prepare_job(geometry, camera, env, RenderSettings(size, size, antialias=False))
    try:
        result = run_job(job, povray_executable, timeout=120)
        assert result.ok, result.message
        return np.asarray(Image.open(result.image_path).convert("RGB"), dtype=int)
    finally:
        job.cleanup()


@pytest.mark.povray
def test_rendered_variants(povray_executable):
    for base in ("satin", "glass_frosted", "marble"):  # untouched variant = built-in pixels
        untouched = register_definition(base_definition(base))
        assert np.array_equal(
            render(untouched.id, povray_executable), render(base, povray_executable)
        )
    satin = render("satin", povray_executable)
    shiny = render(
        register_definition(base_definition("satin").with_values(specular=1.0, roughness=0.002)).id,
        povray_executable,
    )
    assert shiny.max() >= satin.max() and np.abs(shiny - satin).sum() > 0
    assert (
        render(
            register_definition(base_definition("glass").with_values(ior=2.4)).id, povray_executable
        ).tolist()
        != render("glass", povray_executable).tolist()
    )
    rough = register_definition(base_definition("glass_frosted").with_values(bump_strength=1.8))
    assert (
        np.abs(
            render(rough.id, povray_executable) - render("glass_frosted", povray_executable)
        ).sum()
        > 0
    )
    big = register_definition(base_definition("marble").with_values(pattern_scale=3.0))
    assert np.abs(render(big.id, povray_executable) - render("marble", povray_executable)).sum() > 0
