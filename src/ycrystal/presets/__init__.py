"""Material and environment presets (the M3 alpha catalog).

Each preset is a small JSON manifest shipped with the package, in
``presets/materials/`` and ``presets/environments/``. A material records how POV-Ray
draws it (a ``finish`` recipe, optionally with a ``filter`` amount and an
``interior`` for transparent materials), the standard include files it needs, and the
approximate surface properties used by the live VTK view. An environment preset sets
the background colour, whether the PNG background is transparent, and a cell-edge
colour that stays visible on that background.

Examples
--------
>>> from ycrystal.presets import DEFAULT_MATERIAL, get_material, materials
>>> DEFAULT_MATERIAL
'satin'
>>> [m.id for m in materials()]
['matte', 'satin', 'glossy', 'metallic', 'glass']
>>> get_material("glass").declaration
'material'
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from functools import cache
from importlib import resources
from typing import Any

DEFAULT_MATERIAL = "satin"
"""Material id used when nothing else is chosen (Ycrystal's finish since M0)."""

DEFAULT_ENVIRONMENT = "white"
"""Environment preset id used when nothing else is chosen."""

RGB = tuple[float, float, float]


class PresetError(ValueError):
    """An unknown preset id or an invalid manifest."""


@dataclass(frozen=True)
class LiveLook:
    """Approximate surface properties for the live VTK view (Phong shading).

    Attributes
    ----------
    ambient, diffuse, specular
        Lighting coefficients between 0 and 1.
    specular_power
        Highlight sharpness (VTK specular power).
    opacity
        1 for opaque materials; lower for transparent ones.
    """

    ambient: float = 0.1
    diffuse: float = 0.8
    specular: float = 0.3
    specular_power: float = 40.0
    opacity: float = 1.0


@dataclass(frozen=True)
class Material:
    """A material preset.

    Attributes
    ----------
    id
        Stable identifier stored in projects (e.g. ``"satin"``).
    name, description, category
        Text shown in the interface.
    kind
        ``"finish"``: an opaque finish recipe applied over the element colour.
        ``"material"``: a complete POV-Ray material with transparency (``filter``) and an
        ``interior``.
    finish
        Contents of the POV-Ray ``finish { … }`` block.
    filter
        Pigment filter amount (0 opaque … 1 fully transparent) for ``"material"`` kinds.
    interior
        Contents of the POV-Ray ``interior { … }`` block, or empty.
    keeps_element_color
        Whether the element colour remains visible (True for every alpha preset).
    includes
        Standard POV-Ray include files the recipe needs (none in the alpha catalog).
    live
        Approximation for the live view.
    min_povray, provenance
        Required POV-Ray version and origin of the recipe.
    """

    id: str
    name: str
    description: str
    category: str
    kind: str
    finish: str
    filter: float = 0.0
    interior: str = ""
    keeps_element_color: bool = True
    includes: tuple[str, ...] = ()
    live: LiveLook = field(default_factory=LiveLook)
    min_povray: str = "3.7"
    provenance: str = ""
    order: int = 0

    @property
    def declaration(self) -> str:
        """POV-Ray declaration kind written for this material: texture or material."""
        return "material" if self.kind == "material" else "texture"


@dataclass(frozen=True)
class EnvironmentPreset:
    """A background preset.

    Attributes
    ----------
    id, name, description
        Stable identifier and interface text.
    background
        Background colour (sRGB, 0–1). With ``transparent``, used only in the live view.
    transparent
        Whether rendered PNGs get a transparent background (alpha channel).
    cell_edge_color
        Cell-edge colour that stays visible on this background (sRGB, 0–1).
    provenance
        Origin of the preset.
    """

    id: str
    name: str
    description: str
    background: RGB
    transparent: bool
    cell_edge_color: RGB
    provenance: str = ""
    order: int = 0


def _rgb(values: Any) -> RGB:
    r, g, b = (float(v) for v in values)
    if not all(0.0 <= v <= 1.0 for v in (r, g, b)):
        raise PresetError("colour components must be between 0 and 1")
    return (r, g, b)


def _manifests(folder: str) -> list[dict[str, Any]]:
    root = resources.files("ycrystal.presets").joinpath(folder)
    items = []
    for entry in root.iterdir():
        if entry.name.endswith(".json"):
            items.append(json.loads(entry.read_text(encoding="utf-8")))
    return items


@cache
def _material_table() -> dict[str, Material]:
    table = {}
    for data in _manifests("materials"):
        pov = data["pov"]
        kind = data["kind"]
        if kind not in ("finish", "material"):
            raise PresetError(f"material {data['id']!r}: unknown kind {kind!r}")
        table[data["id"]] = Material(
            id=data["id"],
            name=data["name"],
            description=data["description"],
            category=data["category"],
            kind=kind,
            finish=pov["finish"],
            filter=float(pov.get("filter", 0.0)),
            interior=pov.get("interior", ""),
            keeps_element_color=bool(data.get("keeps_element_color", True)),
            includes=tuple(data.get("includes", ())),
            live=LiveLook(**data.get("live", {})),
            min_povray=data.get("min_povray", "3.7"),
            provenance=data.get("provenance", ""),
            order=int(data.get("order", 0)),
        )
    return dict(sorted(table.items(), key=lambda item: (item[1].order, item[0])))


@cache
def _environment_table() -> dict[str, EnvironmentPreset]:
    table = {}
    for data in _manifests("environments"):
        table[data["id"]] = EnvironmentPreset(
            id=data["id"],
            name=data["name"],
            description=data["description"],
            background=_rgb(data["background"]),
            transparent=bool(data["transparent"]),
            cell_edge_color=_rgb(data["cell_edge_color"]),
            provenance=data.get("provenance", ""),
            order=int(data.get("order", 0)),
        )
    return dict(sorted(table.items(), key=lambda item: (item[1].order, item[0])))


def materials() -> list[Material]:
    """All material presets in display order."""
    return list(_material_table().values())


def environments() -> list[EnvironmentPreset]:
    """All environment presets in display order."""
    return list(_environment_table().values())


def get_material(material_id: str) -> Material:
    """Return the material preset ``material_id``.

    Raises
    ------
    PresetError
        If no preset has this id.
    """
    try:
        return _material_table()[material_id]
    except KeyError:
        raise PresetError(f"unknown material {material_id!r}") from None


def environment_from_preset(environment_id: str, base: Any = None) -> Any:
    """Return an `Environment` with the background of preset ``environment_id``.

    Parameters
    ----------
    environment_id
        Environment preset id.
    base
        Environment whose light intensities are kept; the default lights otherwise.

    Returns
    -------
    ycrystal.core.scene.Environment
        New environment with the preset's background, transparency, and id.
    """
    from dataclasses import replace

    from ycrystal.core.scene import Environment

    preset = get_environment(environment_id)
    return replace(
        base if base is not None else Environment(),
        background=preset.background,
        transparent=preset.transparent,
        preset=preset.id,
    )


def get_environment(environment_id: str) -> EnvironmentPreset:
    """Return the environment preset ``environment_id``.

    Raises
    ------
    PresetError
        If no preset has this id.
    """
    try:
        return _environment_table()[environment_id]
    except KeyError:
        raise PresetError(f"unknown environment {environment_id!r}") from None
