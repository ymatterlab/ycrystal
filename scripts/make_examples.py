"""Regenerate the example projects and style in ``examples/``.

Each example is an ordinary ``.ycrystal`` project (embedded structure, camera, output
size, materials, environment). Provenance paths are stored relative to the repository
and timestamps are fixed, so that regenerating gives the same files.

    python scripts/make_examples.py

It also writes the two styles of the publication gallery in ``examples/publication``.

Render one without opening a window:  ycrystal examples/SrTiO3-studio.ycrystal --render out.png
"""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

from ycrystal.core.camera import Camera
from ycrystal.core.samples import perovskite_srtio3, triclinic_marker
from ycrystal.core.scene import SceneSettings, build_geometry
from ycrystal.io.project import Project, project_to_dict
from ycrystal.io.readers import read_structure
from ycrystal.io.style import Style, style_to_dict
from ycrystal.presets import environment_from_preset, get_environment
from ycrystal.render.pov_writer import RenderSettings

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "examples"
STAMP = "2026-11-15T00:00:00+00:00"


def fitted(structure, settings, direction, up, aspect, orbit=(0.0, 0.0), margin=0.08):
    geometry = build_geometry(structure, settings)
    return (
        Camera.looking_along(direction, up)
        .orbit(*orbit)
        .fitted(*geometry.points_and_radii(), aspect, margin=margin)
    )


def relative_source(structure, path: Path):
    source = dict(structure.metadata.get("source", {}))
    source["path"] = str(path.relative_to(ROOT))
    source["imported_at"] = STAMP
    structure.metadata["source"] = source
    return structure


def write_json(path: Path, data: dict) -> None:
    data["saved_at"] = STAMP
    data["generator"] = "Ycrystal (scripts/make_examples.py)"
    text = json.dumps(data, indent=1, ensure_ascii=False) + "\n"
    path.write_text(text, encoding="utf-8", newline="\n")  # the same bytes on every system
    print(f"wrote {path.relative_to(ROOT) if path.is_relative_to(ROOT) else path}")


def main() -> None:
    EXAMPLES.mkdir(exist_ok=True)

    # 1. SrTiO3 2 x 2 x 1 in the grey studio: chrome Ti, ceramic O, satin Sr.
    srtio3 = perovskite_srtio3()
    preset = get_environment("studio_grey")
    scene = (
        SceneSettings(
            repetitions=(2, 2, 1), cell_mode="outline", cell_edge_color=preset.cell_edge_color
        )
        .with_element_material("Ti", "chrome")
        .with_element_material("O", "ceramic")
    )
    camera = fitted(srtio3, scene, (-1.0, -0.42, -0.3), (0, 0, 1), 4 / 3)
    project = Project(
        srtio3,
        scene=scene,
        environment=environment_from_preset("studio_grey"),
        camera=camera,
        output=RenderSettings(800, 600),
    )
    write_json(EXAMPLES / "SrTiO3-studio.ycrystal", project_to_dict(project))
    style = Style.from_state(srtio3, scene, project.environment, (800, 600))
    write_json(EXAMPLES / "grey-studio.ycstyle", style_to_dict(style))

    # 2. MgB2 (from the CIF fixture) on a blue gradient, looking down c, B glossy.
    cif = ROOT / "tests" / "fixtures" / "MgB2.cif"
    mgb2 = relative_source(read_structure(cif), cif)
    preset = get_environment("gradient_blue")
    scene = SceneSettings(
        repetitions=(3, 3, 1), cell_mode="all", cell_edge_color=preset.cell_edge_color
    ).with_element_material("B", "glossy")
    camera = fitted(mgb2, scene, (0.2, 0.35, -1.0), (0, 1, 0), 1.0)
    project = Project(
        mgb2,
        scene=scene,
        environment=environment_from_preset("gradient_blue"),
        camera=camera,
        output=RenderSettings(700, 700),
    )
    write_json(EXAMPLES / "MgB2-gradient.ycrystal", project_to_dict(project))

    # 3. Triclinic marker cell, transparent PNG background, matte, larger atoms.
    triclinic = triclinic_marker()
    scene = SceneSettings(material="matte", radius_scale=0.6)
    camera = fitted(triclinic, scene, (0.3, -1.0, -0.2), (0, 0, 1), 3 / 2, (25, 10))
    project = Project(
        triclinic,
        scene=scene,
        environment=environment_from_preset("transparent"),
        camera=camera,
        output=RenderSettings(900, 600, transparent_background=True),
    )
    write_json(EXAMPLES / "triclinic-transparent.ycrystal", project_to_dict(project))

    vector_example()
    publication_styles()


# Colour-blind-safe colours (Okabe and Ito) for the perovskite sites of the gallery.
PAPER_COLORS = {
    "Sr": (0.0, 0.62, 0.451),  # A site: bluish green
    "Ti": (0.0, 0.447, 0.698),  # B site: blue
    "O": (0.835, 0.369, 0.0),  # vermillion
}


def publication_styles(folder: Path = EXAMPLES / "publication" / "styles") -> None:
    """5. The two styles of the publication gallery (FR-GALLERY-01).

    ``paper.ycstyle`` is a restrained look for a journal page: satin, a white background,
    soft lighting, and the site colours of ``PAPER_COLORS``, 1600 × 1200 px.
    ``cover.ycstyle`` keeps those colours and adds ceramic Sr, chrome Ti, and ruby-glass
    O in a dark studio with a reflective floor and a point key light (hard shadows).
    Neither changes element radii, so the cover can be applied to a snapshot made with
    the paper style without changing its geometry or camera.
    """
    folder.mkdir(parents=True, exist_ok=True)
    cif = EXAMPLES / "publication" / "structures" / "SrTiO3.cif"
    srtio3 = relative_source(read_structure(cif), cif)
    paper = SceneSettings(
        material="satin", cell_edge_color=get_environment("white").cell_edge_color
    )
    for element, color in PAPER_COLORS.items():
        paper = paper.with_element_color(element, color)
    style = Style.from_state(srtio3, paper, environment_from_preset("white"), (1600, 1200))
    write_json(folder / "paper.ycstyle", style_to_dict(style))
    dark = get_environment("studio_dark")
    cover = replace(paper, cell_edge_color=dark.cell_edge_color)
    for element, material in (("Sr", "ceramic"), ("Ti", "chrome"), ("O", "glass_ruby")):
        cover = cover.with_element_material(element, material)
    style = Style.from_state(srtio3, cover, environment_from_preset("studio_dark"), (1600, 1200))
    write_json(folder / "cover.ycstyle", style_to_dict(style))


def vector_example() -> None:
    """4. Synthetic two-site cubic cell with explicitly assigned opposite moments.

    An illustration of FR-VECTOR-01 (source defaults of +2.2 and -2.2 μB along z), not
    a claim about the magnetic ground state of any real material.
    """
    import numpy as np

    from ycrystal.core.bonds import BondSettings
    from ycrystal.core.structure import Structure
    from ycrystal.core.vectors import VectorRecord, VectorSet, VectorStyle

    a = 2.87
    structure = Structure(
        cell=np.eye(3) * a,
        positions=np.array([[0.0, 0.0, 0.0], [a / 2, a / 2, a / 2]]),
        numbers=[26, 26],
        labels=["Fe1", "Fe2"],
        metadata={
            "note": "Synthetic two-site cubic cell for the vector example (not a real material)."
        },
    )
    vectors = VectorSet(
        sources=((0, VectorRecord((0.0, 0.0, 2.2))), (1, VectorRecord((0.0, 0.0, -2.2))))
    )
    scene = SceneSettings(
        radius_scale=0.35,
        repetitions=(2, 2, 1),
        bonds=BondSettings(enabled=False),
        vectors=vectors,
        vector_style=VectorStyle(length=2.2, color=(0.75, 0.1, 0.1)),
    )
    camera = fitted(structure, scene, (-0.7, -1.0, -0.35), (0, 0, 1), 4 / 3)
    project = Project(
        structure,
        scene=scene,
        environment=environment_from_preset("white"),
        camera=camera,
        output=RenderSettings(800, 600),
    )
    write_json(EXAMPLES / "vectors-synthetic-afm.ycrystal", project_to_dict(project))


if __name__ == "__main__":
    main()
