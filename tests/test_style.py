"""Reusable styles: capture, files, transfer rules, and scientific data."""

import json
import re
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
    parse_element_map,
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
from ycrystal.io.project import Project, load_project, save_project
from ycrystal.io.style import (
    STYLE_PARTS,
    ElementMapError,
    Style,
    StyleError,
    apply_style,
    load_style,
    resolve_element_map,
    save_style,
    style_elements,
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


# ----- element mapping between compositions (FR-STYLE-MAP-01) ------------------------------
FIXTURES = ROOT / "tests" / "fixtures"


def srtio3_style():
    """A style with settings for every SrTiO3 element and two bond-pair rules."""
    structure = perovskite_srtio3()
    scene = (
        SceneSettings(
            material="glossy",
            bonds=BondSettings(overrides=frozenset({("O", "Ti", False), ("O", "Sr", True)})),
        )
        .with_element_material("Sr", "gold")
        .with_element_material("Ti", "chrome")
        .with_element_material("O", "glass")
        .with_element_color("Sr", (0.9, 0.2, 0.1))
        .with_element_radius("Ti", 0.55)
        .with_atom_materials([(0, (0, 0, 0))], "copper")
    )
    scene = replace(scene, hidden=frozenset({(1, (0, 0, 0))}))
    return Style.from_state(structure, scene, Environment(), (800, 600))


def test_no_mapping_and_identity_mapping_change_nothing():
    _, style = rich_style()
    for target in (perovskite_srtio3(), triclinic_marker()):
        args = (style, target, SceneSettings(), Environment(), (1200, 800))
        plain = apply_style(*args)
        assert apply_style(*args, element_map=None) == plain
        assert apply_style(*args, element_map={}) == plain
        identity = {e: e for e in {"O", "Sr", "Ti"} & set(target.symbols)}
        assert apply_style(*args, element_map=identity) == plain


def test_srtio3_style_maps_onto_bazro3():
    style = srtio3_style()
    target = load_input(FIXTURES / "BaZrO3.cif").structure
    positions, cell = target.positions.copy(), target.cell.copy()
    result = apply_style(
        style,
        target,
        SceneSettings(),
        Environment(),
        (1200, 800),
        element_map={"Sr": "Ba", "Ti": "Zr"},
    )
    scene = result.scene
    assert scene.element_materials == (("Ba", "gold"), ("O", "glass"), ("Zr", "chrome"))
    assert scene.element_colors == (("Ba", (0.9, 0.2, 0.1)),)
    assert scene.element_radii == (("Zr", 0.55),)
    assert scene.bonds.overrides == frozenset({("O", "Zr", False), ("Ba", "O", True)})
    # Per-atom settings refer to SrTiO3's atoms: never transferred, mapping or not.
    assert scene.atom_materials == () and scene.hidden == frozenset()
    assert any("per-atom material override" in note for note in result.notes)
    assert not any("were not applied: the structure has no" in n for n in result.notes)
    np.testing.assert_array_equal(target.positions, positions)
    np.testing.assert_array_equal(target.cell, cell)
    assert target.symbols == ("Ba", "Zr", "O", "O", "O")  # atoms are never relabelled
    geometry = build_geometry(target, scene)
    assert geometry.materials[geometry.index_of((1, (0, 0, 0)))] == "chrome"  # Zr


def test_partial_mapping_onto_mgb2_explains_what_is_dropped():
    style = srtio3_style()
    target = load_input(FIXTURES / "MgB2.cif").structure
    result = apply_style(
        style, target, SceneSettings(), Environment(), (1, 1), element_map={"Ti": "Mg"}
    )
    scene = result.scene
    assert scene.element_materials == (("Mg", "chrome"),) and scene.element_radii == (("Mg", 0.55),)
    assert scene.element_colors == ()  # Sr's colour has nowhere to go; nothing invented
    assert scene.bonds.overrides == frozenset()  # both rules involve O, absent from MgB2
    notes = "\n".join(result.notes)
    assert "Element overrides for O, Sr were not applied: the structure has no O, Sr." in notes
    assert (
        "2 bond-pair rules for elements the structure does not contain were not applied." in notes
    )
    assert "B" not in {e for e, _ in scene.element_materials}  # no guessed B settings


@pytest.mark.parametrize(
    "mapping, message",
    [
        ({"Xx": "Mg"}, "'Xx' is not a chemical element symbol"),
        ({"ti": "Mg"}, "did you mean Ti"),
        ({"Ti": "mg"}, "did you mean Mg"),
        ({"Ti": 12}, "not a chemical element symbol"),
        ({"Ti": "Zr"}, "the structure has no Zr (it contains B, Mg)"),
        ({"Sr": "Mg", "Ti": "Mg"}, "Sr and Ti are all mapped to Mg"),
    ],
)
def test_invalid_mappings_are_refused(mapping, message):
    target = load_input(FIXTURES / "MgB2.cif").structure
    with pytest.raises(ElementMapError, match=re.escape(message)):
        apply_style(
            srtio3_style(), target, SceneSettings(), Environment(), (1, 1), element_map=mapping
        )


def test_mapping_onto_an_element_with_its_own_settings_is_ambiguous():
    style = srtio3_style()
    target = perovskite_srtio3()
    args = (style, target, SceneSettings(), Environment(), (1, 1))
    with pytest.raises(ElementMapError, match="O would receive the settings of both O and Ti"):
        apply_style(*args, element_map={"Ti": "O"})
    # Resolved explicitly: O's own settings left out, or swapped with Ti.
    left_out = apply_style(*args, element_map={"Ti": "O", "O": None})
    assert dict(left_out.scene.element_materials) == {"O": "chrome", "Sr": "gold"}
    assert any(
        "Element settings for O were left out by the element mapping" in n for n in left_out.notes
    )
    assert left_out.scene.bonds.overrides == frozenset()  # both rules involve O
    assert any("or the element mapping leaves out" in n for n in left_out.notes)
    swapped = apply_style(*args, element_map={"Ti": "O", "O": "Ti"})
    assert dict(swapped.scene.element_materials) == {"O": "chrome", "Sr": "gold", "Ti": "glass"}
    # Rules follow their elements: O-Ti stays O-Ti (swapped), O-Sr becomes Sr-Ti.
    assert swapped.scene.bonds.overrides == frozenset({("O", "Ti", False), ("Sr", "Ti", True)})
    # Only applied parts count: without appearance and display no element settings apply.
    only_env = apply_style(*args, parts=("environment",), element_map={"Ti": "O"})
    assert any("no element settings for Ti" in note for note in only_env.notes)


def test_mapping_notes_unused_and_moved_elements():
    structure = perovskite_srtio3()
    style = Style.from_state(
        structure, SceneSettings().with_element_material("Sr", "gold"), Environment(), (1, 1)
    )
    result = apply_style(
        style, structure, SceneSettings(), Environment(), (1, 1), element_map={"Sr": "Ti", "O": "O"}
    )
    assert result.scene.element_materials == (("Ti", "gold"),)
    notes = "\n".join(result.notes)
    assert "no element settings for O; its mapping changes nothing" in notes
    assert "Atoms of Sr in this structure do not receive the style's settings" in notes
    transfer = resolve_element_map(style, structure, {"Sr": "Ti"})
    assert transfer.targets == (("Sr", "Ti"),) and transfer.target_of("Sr") == "Ti"
    assert style_elements(srtio3_style(), ("appearance",)) == ("O", "Sr", "Ti")


@pytest.mark.parametrize(
    "text, expected",
    [
        ("Sr=Ba", {"Sr": "Ba"}),
        (" Sr = Ba , Ti=Zr ", {"Sr": "Ba", "Ti": "Zr"}),
        ("O=-", {"O": None}),
        ("Ti=Ti", {"Ti": "Ti"}),
    ],
)
def test_element_maps_are_parsed(text, expected):
    assert parse_element_map(text) == expected


@pytest.mark.parametrize(
    "text, message",
    [
        ("", "SOURCE=TARGET"),
        ("Sr", "not SOURCE=TARGET"),
        ("Sr=", "not SOURCE=TARGET"),
        ("=Ba", "not SOURCE=TARGET"),
        ("Sr=Ba,,Ti=Zr", "not SOURCE=TARGET"),
        ("Sr=Ba,Sr=Ca", "Sr is mapped twice"),
        ("Sr=BA", "did you mean Ba"),
        ("Q=Ba", "'Q' is not a chemical element symbol"),
    ],
)
def test_bad_element_maps_are_refused(text, message):
    with pytest.raises(ValueError, match=re.escape(message)):
        parse_element_map(text)


def test_mapped_packaged_style_and_saved_project(tmp_path, clean_registries):
    folder = tmp_path / "Stil ü"
    folder.mkdir()
    Image.new("RGB", (40, 30), (30, 30, 200)).save(folder / "back.png")
    asset = import_image(folder / "back.png")
    dense = presets.register_definition(
        base_definition("glass").with_values(ior=1.7).renamed("Dense glass")
    )
    scene = SceneSettings().with_element_material("Ti", dense.id)
    environment = Environment(background_mode="image", image=asset.reference())
    style = Style.from_state(perovskite_srtio3(), scene, environment, (320, 240))
    path = save_style(folder / "look.ycstyle", style)
    stored = path.read_bytes()
    (folder / "back.png").unlink()
    images._REGISTRY.clear()
    presets._CUSTOM.clear()
    presets._DEFINITIONS.clear()
    presets._LISTED.clear()
    target = load_input(FIXTURES / "BaZrO3.cif")
    styled, notes = apply_style_file(target, path, element_map={"Ti": "Zr"})
    assert dict(styled.scene.element_materials) == {"Zr": dense.id}
    assert styled.environment.image is not None and notes == ()
    assert path.read_bytes() == stored  # the style file is never rewritten
    with pytest.raises(StyleTransferError, match="Element mapping: .*no Ti"):
        apply_style_file(target, path, element_map={"Zr": "Ti"})
    # Saving the result keeps the resolved appearance, not the mapping.
    saved = save_project(tmp_path / "BaZrO3 ü.ycrystal", styled)
    assert dict(load_project(saved).scene.element_materials) == {"Zr": dense.id}
