"""Gallery thumbnails rendered by POV-Ray with fixed scenes.

Every material is shown on the same three bonded spheres (strontium, titanium, and
oxygen colours) in one fixed environment
([`MATERIAL_ENVIRONMENT`][ycrystal.render.thumbnails.MATERIAL_ENVIRONMENT]), and every
environment on the same SrTiO3 unit cell with the satin material, so thumbnails can be
compared with each other. The scenes are written by the ordinary
[`scene_to_pov`][ycrystal.render.pov_writer.scene_to_pov]; the thumbnails are genuine
POV-Ray images, not approximations.

The thumbnails are shipped in ``ycrystal/presets/thumbnails/`` together with
``index.json``, which records a digest of each scene. When a preset recipe or the scene
writer changes, the digest no longer matches (the test suite checks this), and
``scripts/render_thumbnails.py`` renders the affected thumbnails again.

Examples
--------
>>> from ycrystal.render.thumbnails import material_scene, scene_digest
>>> text = material_scene("gold")
>>> "texture { T_Gold_3C" in text and '#include "metals.inc"' in text
True
>>> len(scene_digest(text))
64
"""

from __future__ import annotations

import hashlib
import json
from importlib import resources
from pathlib import Path

import numpy as np

from ycrystal.core.camera import Camera
from ycrystal.core.samples import perovskite_srtio3
from ycrystal.core.scene import (
    DisplayGeometry,
    Environment,
    SceneSettings,
    build_geometry,
    element_color,
)
from ycrystal.presets import environment_from_preset, get_environment, get_material
from ycrystal.render.pov_writer import RenderSettings, scene_to_pov

THUMBNAIL_SIZE = 128
"""Width and height of every thumbnail in pixels."""

MATERIAL_ENVIRONMENT = Environment(
    preset="gradient_grey",
    background_mode="gradient",
    background=(0.82, 0.82, 0.84),
    background_bottom=(0.32, 0.32, 0.34),
    reflector=True,
)
"""Environment of the material thumbnails: a neutral grey gradient, the default soft
lighting, and the reflection panel, so that metals and glass have something to reflect."""

_SPHERES = (  # element, atomic number, position (Å), radius (Å)
    ("Sr", 38, (0.0, 0.0, 0.0), 1.0),
    ("Ti", 22, (-1.45, -0.55, 0.85), 0.68),
    ("O", 8, (1.5, -0.6, 0.9), 0.62),
)


def _material_geometry(material_id: str) -> DisplayGeometry:
    material = get_material(material_id)
    colors = [
        material.live.color
        if not material.keeps_element_color and material.live.color is not None
        else element_color(z)
        for _, z, _, _ in _SPHERES
    ]
    return DisplayGeometry(
        atom_ids=tuple((i, (0, 0, 0)) for i in range(len(_SPHERES))),
        elements=tuple(element for element, *_ in _SPHERES),
        positions=np.array([pos for *_, pos, _ in _SPHERES], dtype=float),
        radii=np.array([r for *_, r in _SPHERES], dtype=float),
        colors=np.array(colors, dtype=float),
        cell_edges=np.zeros((0, 2, 3)),
        cell_edge_radius=0.03,
        cell_edge_color=(0.15, 0.15, 0.15),
        bonds=np.array([(0, 1), (0, 2)]),
        bond_radius=0.16,
        material=material_id,
    )


def _camera(geometry: DisplayGeometry, margin: float) -> Camera:
    return Camera.looking_along((0.25, -0.35, -1.0), (0.0, 1.0, 0.0)).fitted(
        *geometry.points_and_radii(), 1.0, margin=margin
    )


def material_scene(material_id: str) -> str:
    """Return the POV-Ray scene of the thumbnail of material ``material_id``."""
    geometry = _material_geometry(material_id)
    environment = MATERIAL_ENVIRONMENT
    settings = RenderSettings(THUMBNAIL_SIZE, THUMBNAIL_SIZE)
    return scene_to_pov(
        geometry,
        _camera(geometry, 0.1),
        environment,
        settings,
        title=f"Ycrystal thumbnail: material {material_id}",
    )


def environment_scene(environment_id: str) -> str:
    """Return the POV-Ray scene of the thumbnail of environment ``environment_id``."""
    preset = get_environment(environment_id)
    settings = SceneSettings(cell_edge_color=preset.cell_edge_color, cell_edge_radius=0.05)
    geometry = build_geometry(perovskite_srtio3(), settings)
    camera = (
        Camera.looking_along((0.0, 0.0, -1.0), (0.0, 1.0, 0.0))
        .orbit(azimuth=-28, elevation=18)
        .fitted(*geometry.points_and_radii(), 1.0, margin=0.12)
    )
    environment = environment_from_preset(environment_id)
    render = RenderSettings(
        THUMBNAIL_SIZE, THUMBNAIL_SIZE, transparent_background=environment.transparent
    )
    return scene_to_pov(
        geometry,
        camera,
        environment,
        render,
        title=f"Ycrystal thumbnail: environment {environment_id}",
    )


def scene_digest(text: str) -> str:
    """Return a SHA-256 digest of a scene, ignoring comment lines.

    Comments carry the generation time, the Ycrystal version, and descriptions, which do
    not change the image.
    """
    content = "\n".join(
        line for line in text.splitlines() if line.strip() and not line.lstrip().startswith("//")
    )
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def thumbnail_directory() -> Path:
    """Directory of the shipped thumbnails (``ycrystal/presets/thumbnails``)."""
    return Path(str(resources.files("ycrystal.presets").joinpath("thumbnails")))


def load_index() -> dict[str, dict[str, str]]:
    """Return the recorded scene digests: ``{"materials": {id: digest}, "environments": …}``.

    Missing index files give empty tables.
    """
    path = thumbnail_directory() / "index.json"
    if not path.is_file():
        return {"materials": {}, "environments": {}}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {"materials": data.get("materials", {}), "environments": data.get("environments", {})}
