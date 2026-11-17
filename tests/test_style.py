"""Reusable styles: capture, files, transfer rules, and scientific data."""

import json
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from ycrystal import presets
from ycrystal.batch import (
    CLI_STYLE_PARTS,
    StyleTransferError,
    apply_style_file,
    export_scene,
    load_input,
    parse_style_parts,
)
from ycrystal.core.bonds import BondSettings
from ycrystal.core.samples import perovskite_srtio3, triclinic_marker
from ycrystal.core.scene import (
    LARGE_DISPLAY_ATOMS,
    Environment,
    SceneSettings,
    build_geometry,
    count_displayed_atoms,
)
from ycrystal.io import images
from ycrystal.io.images import import_image
from ycrystal.io.project import Project
from ycrystal.io.style import (
    STYLE_PARTS,
    Style,
    StyleError,
    apply_style,
    load_style,
    save_style,
    style_to_dict,
)
from ycrystal.presets import apply_lighting, environment_from_preset
from ycrystal.presets.custom import base_definition


def rich_style():
    structure = perovskite_srtio3()
    scene = (
        SceneSettings(
            material="glossy",
            radius_scale=0.4,
            repetitions=(2, 2, 1),
            cell_mode="outline",
            boundary_images=False,
            bonds=BondSettings(radius=0.08, overrides=frozenset({("O", "Ti", False)})),
            hidden=frozenset({(0, (1, 0, 0))}),
            cell_edge_color=(0.8, 0.8, 0.85),
        )
        .with_element_material("O", "glass")
        .with_element_material("Sr", "gold")
        .with_element_color("O", (0.1, 0.2, 0.9))
        .with_element_radius("Ti", 0.55)
        .with_atom_materials([(1, (0, 0, 0))], "chrome")
    )
    environment = apply_lighting(environment_from_preset("studio_dark"), "dramatic")
    return structure, Style.from_state(structure, scene, environment, (900, 700))


def test_file_round_trip_is_exact(tmp_path):
    _, style = rich_style()
    path = save_style(tmp_path / "look.ycstyle", style)
    assert load_style(path) == style
    data = json.loads(path.read_text())
    assert data["format"] == "ycrystal-style" and data["source"]["composition"] == "SrTiO3"
    assert "positions" not in json.dumps(data)  # no scientific data in a style


def test_same_structure_receives_everything():
    structure, style = rich_style()
    result = apply_style(style, structure, SceneSettings(), Environment(), (1200, 800))
    assert result.scene == style.scene
    assert result.environment == style.environment
    assert result.output_size == (900, 700) and result.notes == ()


def test_other_structure_gets_compatible_parts_and_explanations():
    structure, style = rich_style()
    target = triclinic_marker()  # O, Fe, S, Cl, N: shares only O with SrTiO3
    original = target.positions.copy()
    current = SceneSettings(hidden=frozenset({(2, (0, 0, 0))}))
    result = apply_style(style, target, current, Environment(), (1200, 800))
    scene = result.scene
    assert scene.material == "glossy"
    assert scene.element_materials == (("O", "glass"),)  # Sr is absent
    assert scene.element_colors == (("O", (0.1, 0.2, 0.9)),)
    assert scene.element_radii == ()  # Ti is absent
    assert scene.atom_materials == ()  # per-atom: other structure
    assert scene.hidden == current.hidden  # the target's own hidden atoms stay
    assert scene.bonds.overrides == frozenset()  # O-Ti rule: Ti absent
    assert (scene.radius_scale, scene.repetitions, scene.cell_mode) == (0.4, (2, 2, 1), "outline")
    assert result.environment == style.environment and scene.cell_edge_color == (0.8, 0.8, 0.85)
    notes = " ".join(result.notes)
    assert "Sr, Ti" in notes and "per-atom material override was not applied" in notes
    assert "hidden-atom setting was not applied" in notes and "bond-pair rule" in notes
    np.testing.assert_array_equal(target.positions, original)  # scientific data unchanged
    geometry = build_geometry(target, scene)
    assert set(geometry.materials) == {"glossy", "glass"}


def test_parts_are_applied_separately():
    structure, style = rich_style()
    base = SceneSettings()
    only_env = apply_style(style, structure, base, Environment(), (300, 200), ["environment"])
    assert only_env.scene.material == "satin" and only_env.output_size == (300, 200)
    assert only_env.environment.preset == "studio_dark"
    only_look = apply_style(style, structure, base, Environment(), (300, 200), ["appearance"])
    assert only_look.scene.material == "glossy" and only_look.scene.repetitions == (1, 1, 1)
    assert only_look.environment == Environment()
    with pytest.raises(ValueError):
        apply_style(style, structure, base, Environment(), (300, 200), ["camera"])
    assert set(STYLE_PARTS) == {"appearance", "display", "environment", "output"}


@pytest.mark.parametrize(
    "text, message",
    [
        ("not json", "not valid style JSON"),
        ('{"format": "ycrystal-project"}', "not a Ycrystal style"),
        ('{"format": "ycrystal-style", "schema_version": 99}', "newer Ycrystal"),
    ],
)
def test_bad_style_files_are_refused(tmp_path, text, message):
    path = tmp_path / "bad.ycstyle"
    path.write_text(text)
    with pytest.raises(StyleError, match=message):
        load_style(path)


def test_unknown_preset_in_style_is_refused(tmp_path):
    _, style = rich_style()
    data = style_to_dict(style)
    data["scene"]["material"] = "unobtainium"
    path = tmp_path / "future.ycstyle"
    path.write_text(json.dumps(data))
    with pytest.raises(StyleError, match="unobtainium"):
        load_style(path)


# ----- applying a style file without a window (FR-STYLE-CLI-01) --------------------------
ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def clean_registries():
    """Forget pictures and custom materials registered by a test (process-wide)."""
    yield
    images._REGISTRY.clear()
    presets._CUSTOM.clear()
    presets._DEFINITIONS.clear()
    presets._LISTED.clear()


def test_cli_default_parts_leave_display_settings_alone(tmp_path):
    structure, style = rich_style()
    path = save_style(tmp_path / "look.ycstyle", style)
    target = load_input(ROOT / "tests" / "fixtures" / "MgB2.cif")
    scene_before, env_before, output_before = target.scene, target.environment, target.output
    styled, notes = apply_style_file(target, path)
    assert CLI_STYLE_PARTS == ("appearance", "environment", "output")
    assert styled.scene.material == "glossy" and styled.environment == style.environment
    assert (styled.output.width, styled.output.height) == (900, 700)
    assert styled.scene.repetitions == scene_before.repetitions  # display not applied
    assert styled.scene.bonds == scene_before.bonds and styled.scene.hidden == scene_before.hidden
    assert styled.camera is None  # fitted to the styled geometry when drawn
    assert styled.structure is target.structure  # shared, never copied or changed
    # The input project is unchanged.
    assert (target.scene, target.environment, target.output) == (
        scene_before,
        env_before,
        output_before,
    )
    assert any("O, Sr, Ti" in note for note in notes)
    assert any("per-atom material override" in note for note in notes)


def test_same_structure_receives_every_requested_part(tmp_path):
    structure, style = rich_style()
    path = save_style(tmp_path / "look.ycstyle", style)
    styled, notes = apply_style_file(Project(structure), path, STYLE_PARTS)
    assert styled.scene == style.scene and styled.environment == style.environment
    assert notes == ()
    with pytest.raises(StyleTransferError, match="No style parts"):
        apply_style_file(Project(structure), style, ())
    with pytest.raises(StyleTransferError, match="camera"):
        apply_style_file(Project(structure), style, ("appearance", "camera"))


def test_saved_project_keeps_camera_vectors_and_structure():
    path = ROOT / "examples" / "vectors-synthetic-afm.ycrystal"
    original = path.read_bytes()
    target = load_input(path)
    positions = target.structure.positions.copy()
    _, style = rich_style()
    style = replace(style, scene=replace(style.scene, repetitions=(3, 1, 1)))
    styled, notes = apply_style_file(target, style, STYLE_PARTS)
    assert styled.camera == target.camera  # saved camera kept
    assert styled.scene.vectors == target.scene.vectors  # vector data untouched
    assert styled.scene.vector_style == style.scene.vector_style  # arrow look transferred
    assert styled.scene.repetitions == (3, 1, 1)
    np.testing.assert_array_equal(styled.structure.positions, positions)
    assert any("saved camera was kept" in note for note in notes)
    assert path.read_bytes() == original  # the project file is never written


def test_large_display_from_a_style_is_refused():
    structure, style = rich_style()
    big = replace(style, scene=replace(style.scene, repetitions=(30, 30, 30)))
    target = Project(perovskite_srtio3())
    assert count_displayed_atoms(target.structure, big.scene) > LARGE_DISPLAY_ATOMS
    with pytest.raises(StyleTransferError, match="more than the limit of 20,000"):
        apply_style_file(target, big, STYLE_PARTS)
    # Without the display part the repetitions stay, so the style applies.
    styled, _ = apply_style_file(target, big)
    assert styled.scene.repetitions == (1, 1, 1)
    # A project that already shows that many atoms is drawn as saved.
    already = Project(target.structure, scene=replace(target.scene, repetitions=(30, 30, 30)))
    styled, _ = apply_style_file(already, big, STYLE_PARTS)
    assert styled.scene.repetitions == (30, 30, 30)


@pytest.mark.parametrize(
    "text, expected",
    [
        ("appearance", ("appearance",)),
        (" output , environment ", ("environment", "output")),
        ("display,display", ("display",)),
        ("appearance,display,environment,output", STYLE_PARTS),
    ],
)
def test_style_parts_are_parsed(text, expected):
    assert parse_style_parts(text) == expected


@pytest.mark.parametrize(
    "text", ["", " ", "appearance,", "appearance,,output", "camera", "Display"]
)
def test_bad_style_parts_are_refused(text):
    with pytest.raises(ValueError, match="style part"):
        parse_style_parts(text)


def test_packaged_style_with_picture_and_custom_material(tmp_path, clean_registries):
    folder = tmp_path / "Stil ü"
    folder.mkdir()
    Image.new("RGB", (40, 30), (200, 30, 30)).save(folder / "back drop.png")
    asset = import_image(folder / "back drop.png")
    shiny = presets.register_definition(
        base_definition("satin").with_values(specular=0.8).renamed("Shiny")
    )
    environment = Environment(background_mode="image", image=asset.reference())
    scene = SceneSettings(material=shiny.id)
    style = Style.from_state(perovskite_srtio3(), scene, environment, (320, 240))
    path = save_style(folder / "picture look.ycstyle", style)
    (folder / "back drop.png").unlink()  # the package carries the picture
    images._REGISTRY.clear()
    presets._CUSTOM.clear()
    presets._DEFINITIONS.clear()
    presets._LISTED.clear()
    styled, _ = apply_style_file(load_input(ROOT / "tests" / "fixtures" / "MgB2.cif"), path)
    assert styled.scene.material == shiny.id and styled.environment.image is not None
    out = tmp_path / "out ü"
    out.mkdir()
    pov, ini = export_scene(styled, out / "Mg B2.pov")
    text = pov.read_text(encoding="utf-8")
    staged = [p for p in out.iterdir() if p.suffix == ".png"]
    assert len(staged) == 1 and staged[0].name in text  # picture copied next to the scene
    assert "Shiny" in text and "Width=320" in ini.read_text()
