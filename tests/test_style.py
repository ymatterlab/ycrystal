"""Reusable styles: capture, files, transfer rules, and scientific data."""

import json

import numpy as np
import pytest

from ycrystal.core.bonds import BondSettings
from ycrystal.core.samples import perovskite_srtio3, triclinic_marker
from ycrystal.core.scene import Environment, SceneSettings, build_geometry
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
