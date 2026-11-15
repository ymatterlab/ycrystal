import json
import shutil
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from ycrystal.core.camera import Camera
from ycrystal.core.scene import Environment, SceneSettings, build_geometry
from ycrystal.io.project import (
    SCHEMA_VERSION,
    Project,
    ProjectError,
    load_project,
    project_to_dict,
    save_project,
)
from ycrystal.io.readers import read_structure
from ycrystal.render.pov_writer import RenderSettings

FIXTURES = Path(__file__).parent / "fixtures"


def full_project(structure) -> Project:
    camera = Camera.looking_along(
        (0.3, -1.0, -0.2), (0, 0, 1), focal_point=(1.1, 0.7, 2.3), parallel_scale=3.21
    ).orbit(azimuth=17.3, elevation=-8.9)
    return Project(
        structure=structure,
        scene=SceneSettings(
            radius_scale=0.42,
            boundary_images=True,
            hidden=frozenset({(0, (1, 1, 1)), (2, (0, 0, 1))}),
        ),
        environment=Environment(
            background=(0.86, 0.86, 0.86),
            key_light=0.9,
            fill_light=0.2,
            transparent=True,
            preset="transparent",
        ),
        camera=camera,
        output=RenderSettings(width=900, height=600, transparent_background=True),
    )


def assert_same_structure(a, b):
    for name in ("cell", "positions", "numbers", "occupancy"):
        np.testing.assert_array_equal(getattr(a, name), getattr(b, name))  # exact
    assert a.labels == b.labels and a.pbc == b.pbc
    if a.movable is None:
        assert b.movable is None
    else:
        np.testing.assert_array_equal(a.movable, b.movable)


def test_round_trip_is_exact(tmp_path):
    structure = read_structure(FIXTURES / "SrTiO3.vasp")  # labels + selective dynamics
    project = full_project(structure)
    path = save_project(tmp_path / "figure.ycrystal", project)
    again = load_project(path)
    assert_same_structure(structure, again.structure)
    assert again.structure.metadata == json.loads(json.dumps(structure.metadata))
    assert again.scene == project.scene
    assert again.environment == project.environment
    assert again.camera == project.camera
    assert again.output == project.output
    # Same displayed geometry, including the hidden boundary atoms.
    g1, g2 = (build_geometry(p.structure, p.scene) for p in (project, again))
    assert g1.atom_ids == g2.atom_ids and g1.hidden_count == 2
    assert [p.name for p in tmp_path.iterdir()] == ["figure.ycrystal"]  # no temp files


def test_file_is_readable_versioned_json(tmp_path):
    path = save_project(
        tmp_path / "p.ycrystal", full_project(read_structure(FIXTURES / "MgB2.cif"))
    )
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["format"] == "ycrystal-project"
    assert data["schema_version"] == SCHEMA_VERSION
    assert data["structure"]["symbols"] == ["Mg", "B", "B"]
    assert data["structure"]["metadata"]["source"]["format"] == "cif"
    assert data["scene"]["hidden"] == [
        {"atom": 0, "image": [1, 1, 1]},
        {"atom": 2, "image": [0, 0, 1]},
    ]


def test_project_reopens_after_source_file_is_moved(tmp_path):
    source = tmp_path / "data" / "triclinic.cif"
    source.parent.mkdir()
    shutil.copy(FIXTURES / "triclinic.cif", source)
    structure = read_structure(source)
    path = save_project(tmp_path / "work.ycrystal", Project(structure))
    shutil.move(source, tmp_path / "elsewhere.cif")
    shutil.rmtree(tmp_path / "data")
    again = load_project(path)
    assert_same_structure(structure, again.structure)
    assert again.structure.metadata["source"]["path"] == str(source.resolve())


def test_newer_schema_is_refused(tmp_path):
    data = project_to_dict(Project(read_structure(FIXTURES / "Si.pw.in")))
    data["schema_version"] = SCHEMA_VERSION + 1
    path = tmp_path / "future.ycrystal"
    path.write_text(json.dumps(data))
    with pytest.raises(ProjectError, match="newer Ycrystal"):
        load_project(path)


@pytest.mark.parametrize(
    "content, message",
    [
        ("{not json", "not valid project JSON"),
        ('{"format": "something-else"}', "not a Ycrystal project"),
        ('{"format": "ycrystal-project"}', "no valid schema version"),
        ('{"format": "ycrystal-project", "schema_version": 1}', "damaged or incomplete"),
    ],
)
def test_damaged_files(tmp_path, content, message):
    path = tmp_path / "bad.ycrystal"
    path.write_text(content)
    with pytest.raises(ProjectError, match=message):
        load_project(path)


def test_inconsistent_content_is_reported(tmp_path):
    data = project_to_dict(Project(read_structure(FIXTURES / "MgB2.vasp")))
    data["structure"]["symbols"] = ["Mg", "C", "B"]
    path = tmp_path / "edited.ycrystal"
    path.write_text(json.dumps(data))
    with pytest.raises(ProjectError, match="do not match"):
        load_project(path)
    data = project_to_dict(Project(read_structure(FIXTURES / "MgB2.vasp")))
    data["structure"]["positions"] = data["structure"]["positions"][:2]
    path.write_text(json.dumps(data))
    with pytest.raises(ProjectError, match="damaged"):
        load_project(path)


def test_missing_optional_sections_use_defaults(tmp_path):
    data = project_to_dict(Project(read_structure(FIXTURES / "MgB2.vasp")))
    for key in ("scene", "environment", "camera", "output"):
        del data[key]
    path = tmp_path / "minimal.ycrystal"
    path.write_text(json.dumps(data))
    project = load_project(path)
    assert project.camera is None and project.scene == SceneSettings()
    assert project.output == RenderSettings()


def test_unreadable_path(tmp_path):
    with pytest.raises(ProjectError, match="Cannot read"):
        load_project(tmp_path / "nope.ycrystal")


def test_structure_replace_keeps_validation():
    structure = read_structure(FIXTURES / "MgB2.vasp")
    with pytest.raises(ValueError):
        structure.replace(occupancy=[0.5, 2.0, 1.0])
    assert replace(SceneSettings(), boundary_images=False).boundary_images is False


def test_round_trip_of_repetitions_cells_and_bonds(tmp_path):
    from ycrystal.core.bonds import BondSettings

    bonds = BondSettings(tolerance=1.25, radius=0.2).with_pair(("O", "Sr"), False)
    scene = SceneSettings(repetitions=(2, 3, 1), cell_mode="outline", bonds=bonds)
    project = Project(read_structure(FIXTURES / "SrTiO3.cif"), scene=scene)
    again = load_project(save_project(tmp_path / "s2.ycrystal", project))
    assert again.scene == scene
    data = json.loads((tmp_path / "s2.ycrystal").read_text())
    assert data["schema_version"] == SCHEMA_VERSION
    assert data["scene"]["repetitions"] == [2, 3, 1]
    assert data["scene"]["bonds"]["pairs"] == [{"elements": ["O", "Sr"], "enabled": False}]


def test_schema1_project_opens_unchanged_without_bonds(tmp_path):
    data = project_to_dict(Project(read_structure(FIXTURES / "SrTiO3.cif")))
    data["schema_version"] = 1
    for key in ("repetitions", "cell_mode", "bonds"):
        del data["scene"][key]
    path = tmp_path / "old.ycrystal"
    path.write_text(json.dumps(data))
    project = load_project(path)
    assert project.scene.repetitions == (1, 1, 1)
    assert project.scene.bonds.enabled is False  # schema 1 had no bonds
    assert len(build_geometry(project.structure, project.scene).bonds) == 0


def test_material_background_and_output_round_trip(tmp_path):
    from ycrystal.presets import environment_from_preset

    scene = SceneSettings(material="glass")
    project = Project(
        read_structure(FIXTURES / "MgB2.cif"),
        scene=scene,
        environment=environment_from_preset("dark"),
        output=RenderSettings(width=640, height=480),
    )
    again = load_project(save_project(tmp_path / "m3.ycrystal", project))
    assert again.scene.material == "glass"
    assert again.environment == project.environment
    assert (again.output.width, again.output.height) == (640, 480)
    data = json.loads((tmp_path / "m3.ycrystal").read_text())
    assert data["environment"]["preset"] == "dark" and data["scene"]["material"] == "glass"


def test_schema2_transparent_output_becomes_transparent_preset(tmp_path):
    data = project_to_dict(Project(read_structure(FIXTURES / "MgB2.cif")))
    data["schema_version"] = 2
    del data["scene"]["material"]
    for key in ("preset", "transparent"):
        del data["environment"][key]
    data["output"]["transparent_background"] = True
    path = tmp_path / "v2.ycrystal"
    path.write_text(json.dumps(data))
    project = load_project(path)
    assert project.scene.material == "satin"  # the finish schema-2 files were drawn with
    assert project.environment.transparent and project.environment.preset == "transparent"


@pytest.mark.parametrize("section, key", [("scene", "material"), ("environment", "preset")])
def test_unknown_presets_are_refused(tmp_path, section, key):
    data = project_to_dict(Project(read_structure(FIXTURES / "MgB2.cif")))
    data[section][key] = "unobtainium"
    path = tmp_path / "future.ycrystal"
    path.write_text(json.dumps(data))
    with pytest.raises(ProjectError, match="unobtainium.*Update Ycrystal"):
        load_project(path)


def test_overrides_colours_radii_and_environment_round_trip(tmp_path):
    from ycrystal.presets import apply_lighting, environment_from_preset

    structure = read_structure(FIXTURES / "MgB2.cif")
    scene = (
        SceneSettings(material="ceramic", repetitions=(2, 2, 1))
        .with_element_material("B", "gold")
        .with_atom_materials([(0, (1, 0, 0)), (1, (0, 0, 0))], "glass_frosted")
        .with_element_color("Mg", (0.1, 0.8, 0.3))
        .with_element_radius("B", 0.37)
    )
    environment = replace(
        apply_lighting(environment_from_preset("sky_cloudy"), "dramatic"),
        clouds=0.35,
        floor=True,
        floor_color=(0.4, 0.42, 0.45),
        floor_reflection=0.2,
        floor_offset=0.75,
        key_azimuth=-50.0,
        light_size=0.8,
    )
    project = Project(structure, scene=scene, environment=environment)
    path = save_project(tmp_path / "m4.ycrystal", project)
    again = load_project(path)
    assert again.scene == project.scene  # overrides and colours, exactly
    assert again.environment == project.environment  # background, floor, lighting
    data = json.loads(path.read_text())
    assert data["schema_version"] == SCHEMA_VERSION == 6  # 6: background pictures
    assert data["scene"]["element_radii"] == [{"element": "B", "radius": 0.37}]
    assert data["scene"]["element_materials"] == [{"element": "B", "material": "gold"}]
    assert data["environment"]["floor"]["reflection"] == 0.2
    assert data["environment"]["lighting"]["preset"] == "dramatic"
    a = build_geometry(project.structure, project.scene)
    b = build_geometry(again.structure, again.scene)
    assert a.materials == b.materials and np.array_equal(a.colors, b.colors)


def test_schema3_file_keeps_its_m3_appearance(tmp_path):
    data = project_to_dict(Project(read_structure(FIXTURES / "MgB2.cif")))
    data["schema_version"] = 3
    for key in ("element_materials", "atom_materials", "element_colors"):
        del data["scene"][key]
    data["scene"]["material"] = "metallic"
    data["environment"] = {
        "preset": "dark",
        "transparent": False,
        "background": [0.13, 0.13, 0.15],
        "key_light": 0.8,
        "fill_light": 0.3,
    }
    path = tmp_path / "m3.ycrystal"
    path.write_text(json.dumps(data))
    project = load_project(path)
    env = project.environment
    assert env.preset == "dark" and env.background == (0.13, 0.13, 0.15)
    assert (env.key_light, env.fill_light) == (0.8, 0.3)
    # Fields that M3 did not have take the M3 behaviour, not the M4 "dark" preset values.
    assert env.background_mode == "solid" and not env.floor and not env.reflector
    assert env.lighting == "soft" and env.light_size == 0.0
    assert project.scene.material == "metallic" and project.scene.element_materials == ()


@pytest.mark.parametrize(
    "path_keys, value",
    [
        (("scene", "element_materials"), [{"element": "O", "material": "unobtainium"}]),
        (("scene", "atom_materials"), [{"atom": 0, "image": [0, 0, 0], "material": "unobtainium"}]),
    ],
)
def test_unknown_override_materials_are_refused(tmp_path, path_keys, value):
    data = project_to_dict(Project(read_structure(FIXTURES / "MgB2.cif")))
    data[path_keys[0]][path_keys[1]] = value
    path = tmp_path / "future.ycrystal"
    path.write_text(json.dumps(data))
    with pytest.raises(ProjectError, match="unobtainium.*Update Ycrystal"):
        load_project(path)


def test_unknown_lighting_is_refused(tmp_path):
    data = project_to_dict(Project(read_structure(FIXTURES / "MgB2.cif")))
    data["environment"]["lighting"]["preset"] = "unobtainium"
    path = tmp_path / "future.ycrystal"
    path.write_text(json.dumps(data))
    with pytest.raises(ProjectError, match="unobtainium.*Update Ycrystal"):
        load_project(path)
