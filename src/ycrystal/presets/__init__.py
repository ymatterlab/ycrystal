"""Material, environment, and lighting presets.

Every preset is a small JSON manifest shipped with the package: one file per material in
``presets/materials/``, one per environment in ``presets/environments/``, and the
lighting presets in ``presets/lighting.json``. Each material and environment also has a
thumbnail rendered by POV-Ray (``presets/thumbnails/``, regenerated with
``scripts/render_thumbnails.py``).

A material records how POV-Ray draws it (one of four declaration kinds, see
[`Material`][ycrystal.presets.Material]), the native POV-Ray identifiers it uses, the
standard include files they need, whether it keeps the element colour, and an
approximation for the live VTK view. An environment preset initialises the background,
the floor, and the lighting of an [`Environment`][ycrystal.core.scene.Environment]; the
user can change each of them afterwards.

Examples
--------
>>> from ycrystal.presets import DEFAULT_MATERIAL, get_material, materials
>>> DEFAULT_MATERIAL
'satin'
>>> len(materials()) >= 20
True
>>> gold = get_material("gold")
>>> gold.kind, gold.native, gold.includes, gold.keeps_element_color
('texture', ('T_Gold_3C',), ('metals.inc',), False)
>>> [m.id for m in materials() if m.matches("marble")]
['marble']
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from functools import cache
from importlib import resources
from pathlib import Path
from typing import Any

DEFAULT_MATERIAL = "satin"
"""Material id used when nothing else is chosen (Ycrystal's finish since M0)."""

DEFAULT_ENVIRONMENT = "white"
"""Environment preset id used when nothing else is chosen."""

DEFAULT_LIGHTING = "soft"
"""Lighting preset id of the default environment (Ycrystal's lights since M0)."""

MATERIAL_KINDS = ("finish", "pigment", "texture", "material")
"""Declaration kinds a material manifest can use."""

MATERIAL_CATEGORIES = {
    "finish": "Scientific finishes",
    "metal": "Metals",
    "transparent": "Glass and transparent",
    "decorative": "Decorative textures",
}
"""Material category ids and their names in the interface, in display order."""

ENVIRONMENT_CATEGORIES = {
    "plain": "Plain backgrounds",
    "gradient": "Gradients",
    "studio": "Studios with floor",
    "sky": "Skies",
}
"""Environment category ids and their names in the interface, in display order."""

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
    color
        Representative colour (sRGB, 0–1) of a material with its own pigment, used in
        the live view instead of the element colour; ``None`` for materials that keep
        the element colour.
    """

    ambient: float = 0.1
    diffuse: float = 0.8
    specular: float = 0.3
    specular_power: float = 40.0
    opacity: float = 1.0
    color: RGB | None = None


@dataclass(frozen=True)
class Material:
    """A material preset.

    Attributes
    ----------
    id
        Stable identifier stored in projects (e.g. ``"satin"``).
    name, description
        Text shown in the interface.
    category
        One of [`MATERIAL_CATEGORIES`][ycrystal.presets.MATERIAL_CATEGORIES].
    kind
        Declaration kind:

        ``"finish"``
            The element colour as pigment with the ``finish`` (and optional
            ``normal``).
        ``"pigment"``
            A native or written ``pigment`` (own colours) with the ``finish``.
        ``"texture"``
            A complete native ``texture`` (own colours), for example ``T_Gold_3C``.
        ``"material"``
            A ``material`` with an ``interior``: either the native identifier in
            ``material`` (own colours) or, without it, the element colour with
            ``filter``, ``finish``, optional ``normal``, and ``interior``.
    finish
        Contents of the ``finish { … }`` block: a recipe or a native identifier.
    pigment
        Contents of the ``pigment { … }`` block of a ``"pigment"`` material.
    texture
        Contents of the ``texture { … }`` block of a ``"texture"`` material.
    material
        Native material identifier of a ``"material"`` kind, or empty for a recipe.
    normal
        Contents of an optional ``normal { … }`` block (surface relief).
    filter
        Pigment filter amount (0 opaque … 1 fully transparent) of a material recipe.
    interior
        Contents of the ``interior { … }`` block of a material recipe, or empty.
    keeps_element_color
        Whether the element colour remains visible. False for materials with their own
        pigment; the gallery says so instead of silently replacing colours.
    native
        Native POV-Ray identifiers the material uses (shown and searchable).
    includes
        Standard POV-Ray include files that declare them, in loading order.
    texture_space
        ``"unit"``: the texture is applied to a unit sphere that is then scaled to the
        atom radius and moved to the atom, so procedural patterns have the same size on
        every atom. ``"world"``: applied in world coordinates (Å).
    texture_scale
        Extra uniform scale of the texture or pigment in its texture space.
    live
        Approximation for the live view.
    min_povray, provenance
        Required POV-Ray version and origin of the recipe or identifiers.
    order
        Position in the catalog.
    """

    id: str
    name: str
    description: str
    category: str
    kind: str
    finish: str = ""
    pigment: str = ""
    texture: str = ""
    material: str = ""
    normal: str = ""
    filter: float = 0.0
    interior: str = ""
    keeps_element_color: bool = True
    native: tuple[str, ...] = ()
    includes: tuple[str, ...] = ()
    texture_space: str = "world"
    texture_scale: float = 1.0
    live: LiveLook = field(default_factory=LiveLook)
    min_povray: str = "3.7"
    provenance: str = ""
    order: int = 0

    @property
    def declaration(self) -> str:
        """POV-Ray declaration written for this material: ``texture`` or ``material``."""
        return "material" if self.kind == "material" else "texture"

    @property
    def category_name(self) -> str:
        """Category name shown in the interface."""
        return MATERIAL_CATEGORIES.get(self.category, self.category)

    def matches(self, query: str) -> bool:
        """Return whether every word of ``query`` occurs in the preset's text.

        Searches the name, id, category, description, native identifiers, and include
        files, ignoring case. An empty query matches everything.
        """
        text = " ".join(
            (self.name, self.id, self.category, self.category_name, self.description)
            + self.native
            + self.includes
        )
        return _matches(text, query)

    def thumbnail(self) -> Path | None:
        """Path of the POV-Ray thumbnail, or ``None`` if it is missing."""
        return _thumbnail("materials", self.id)


@dataclass(frozen=True)
class LightingPreset:
    """A lighting preset: values for the lighting fields of an environment.

    Attributes
    ----------
    id, name, description
        Stable identifier and interface text.
    key_light, fill_light
        Light intensities (POV-Ray ``color rgb`` values).
    key_azimuth, key_elevation
        Direction of the key light in degrees, relative to the view: azimuth to the
        right of the viewer (negative: left), elevation above the frame's horizontal.
    light_size
        Size of the key light as an area light, in multiples of the scene radius; 0
        for a point light with sharp shadows.
    shadows
        Whether the key light casts shadows.
    order
        Position in the list.
    """

    id: str
    name: str
    description: str
    key_light: float
    fill_light: float
    key_azimuth: float
    key_elevation: float
    light_size: float
    shadows: bool
    order: int = 0


@dataclass(frozen=True)
class EnvironmentPreset:
    """An environment preset: background, floor, lighting, and edge colour.

    Attributes
    ----------
    id, name, description
        Stable identifier and interface text.
    category
        One of [`ENVIRONMENT_CATEGORIES`][ycrystal.presets.ENVIRONMENT_CATEGORIES].
    background_mode
        ``"solid"``, ``"gradient"``, or ``"sky"``.
    background
        Solid colour, top colour of a gradient, or zenith colour of a sky (sRGB, 0–1).
        With ``transparent``, used only in the live view.
    background_bottom
        Bottom colour of a gradient or horizon colour of a sky.
    clouds
        Cloud cover of a sky, 0 (clear) to 1.
    transparent
        Whether rendered PNGs get a transparent background (alpha channel).
    floor, floor_color, floor_reflection, floor_offset
        Whether a floor is drawn below the structure, its colour, mirror reflection
        (0–1), and its gap below the lowest atom in Å.
    lighting
        Id of the lighting preset the environment starts with.
    reflector
        Whether an invisible bright panel is added for reflective materials to mirror.
    cell_edge_color
        Cell-edge colour that stays visible on this background (sRGB, 0–1).
    provenance
        Origin of the preset.
    order
        Position in the catalog.
    """

    id: str
    name: str
    description: str
    category: str
    background_mode: str
    background: RGB
    background_bottom: RGB
    clouds: float
    transparent: bool
    floor: bool
    floor_color: RGB
    floor_reflection: float
    floor_offset: float
    lighting: str
    reflector: bool
    cell_edge_color: RGB
    provenance: str = ""
    order: int = 0

    @property
    def category_name(self) -> str:
        """Category name shown in the interface."""
        return ENVIRONMENT_CATEGORIES.get(self.category, self.category)

    def matches(self, query: str) -> bool:
        """Return whether every word of ``query`` occurs in the preset's text."""
        text = " ".join((self.name, self.id, self.category, self.category_name, self.description))
        return _matches(text, query)

    def thumbnail(self) -> Path | None:
        """Path of the POV-Ray thumbnail, or ``None`` if it is missing."""
        return _thumbnail("environments", self.id)


def _matches(text: str, query: str) -> bool:
    haystack = text.casefold()
    return all(word in haystack for word in query.casefold().split())


def _thumbnail(folder: str, preset_id: str) -> Path | None:
    entry = resources.files("ycrystal.presets").joinpath("thumbnails", folder, f"{preset_id}.png")
    return Path(str(entry)) if entry.is_file() else None


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


def _material(data: dict[str, Any]) -> Material:
    pov = data.get("pov", {})
    kind = data["kind"]
    name = data["id"]
    if kind not in MATERIAL_KINDS:
        raise PresetError(f"material {name!r}: unknown kind {kind!r}")
    if data["category"] not in MATERIAL_CATEGORIES:
        raise PresetError(f"material {name!r}: unknown category {data['category']!r}")
    required = {"finish": "finish", "pigment": "pigment", "texture": "texture"}.get(kind)
    if required and not pov.get(required):
        raise PresetError(f"material {name!r}: kind {kind!r} needs pov.{required}")
    own_pigment = kind in ("pigment", "texture") or bool(pov.get("material"))
    live = dict(data.get("live", {}))
    if "color" in live:
        live["color"] = _rgb(live["color"])
    if own_pigment and live.get("color") is None:
        raise PresetError(f"material {name!r}: a material with its own pigment needs live.color")
    space = data.get("texture_space", "world")
    if space not in ("unit", "world"):
        raise PresetError(f"material {name!r}: unknown texture_space {space!r}")
    return Material(
        id=name,
        name=data["name"],
        description=data["description"],
        category=data["category"],
        kind=kind,
        finish=pov.get("finish", ""),
        pigment=pov.get("pigment", ""),
        texture=pov.get("texture", ""),
        material=pov.get("material", ""),
        normal=pov.get("normal", ""),
        filter=float(pov.get("filter", 0.0)),
        interior=pov.get("interior", ""),
        keeps_element_color=not own_pigment,
        native=tuple(data.get("native", ())),
        includes=tuple(data.get("includes", ())),
        texture_space=space,
        texture_scale=float(data.get("texture_scale", 1.0)),
        live=LiveLook(**live),
        min_povray=data.get("min_povray", "3.7"),
        provenance=data.get("provenance", ""),
        order=int(data.get("order", 0)),
    )


@cache
def _material_table() -> dict[str, Material]:
    table = {data["id"]: _material(data) for data in _manifests("materials")}
    return dict(sorted(table.items(), key=lambda item: (item[1].order, item[0])))


@cache
def _lighting_table() -> dict[str, LightingPreset]:
    entry = resources.files("ycrystal.presets").joinpath("lighting.json")
    table = {}
    for order, data in enumerate(json.loads(entry.read_text(encoding="utf-8"))):
        table[data["id"]] = LightingPreset(
            id=data["id"],
            name=data["name"],
            description=data["description"],
            key_light=float(data["key_light"]),
            fill_light=float(data["fill_light"]),
            key_azimuth=float(data["key_azimuth"]),
            key_elevation=float(data["key_elevation"]),
            light_size=float(data["light_size"]),
            shadows=bool(data["shadows"]),
            order=order,
        )
    return table


@cache
def _environment_table() -> dict[str, EnvironmentPreset]:
    table = {}
    for data in _manifests("environments"):
        background = data["background"]
        floor = data.get("floor") or {}
        preset = EnvironmentPreset(
            id=data["id"],
            name=data["name"],
            description=data["description"],
            category=data["category"],
            background_mode=background.get("mode", "solid"),
            background=_rgb(background["color"]),
            background_bottom=_rgb(background.get("bottom", background["color"])),
            clouds=float(background.get("clouds", 0.0)),
            transparent=bool(data.get("transparent", False)),
            floor=bool(floor),
            floor_color=_rgb(floor.get("color", (0.9, 0.9, 0.9))),
            floor_reflection=float(floor.get("reflection", 0.0)),
            floor_offset=float(floor.get("offset", 0.0)),
            lighting=data.get("lighting", DEFAULT_LIGHTING),
            reflector=bool(data.get("reflector", False)),
            cell_edge_color=_rgb(data["cell_edge_color"]),
            provenance=data.get("provenance", ""),
            order=int(data.get("order", 0)),
        )
        if preset.category not in ENVIRONMENT_CATEGORIES:
            raise PresetError(f"environment {preset.id!r}: unknown category {preset.category!r}")
        get_lighting(preset.lighting)
        table[preset.id] = preset
    return dict(sorted(table.items(), key=lambda item: (item[1].order, item[0])))


def materials() -> list[Material]:
    """All material presets in display order."""
    return list(_material_table().values())


def environments() -> list[EnvironmentPreset]:
    """All environment presets in display order."""
    return list(_environment_table().values())


def lighting_presets() -> list[LightingPreset]:
    """All lighting presets in display order."""
    return list(_lighting_table().values())


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


def get_lighting(lighting_id: str) -> LightingPreset:
    """Return the lighting preset ``lighting_id``.

    Raises
    ------
    PresetError
        If no preset has this id.
    """
    try:
        return _lighting_table()[lighting_id]
    except KeyError:
        raise PresetError(f"unknown lighting {lighting_id!r}") from None


def apply_lighting(environment: Any, lighting_id: str) -> Any:
    """Return ``environment`` with the light values of lighting preset ``lighting_id``.

    Background, floor, and transparency are unchanged.

    Parameters
    ----------
    environment
        A [`Environment`][ycrystal.core.scene.Environment].
    lighting_id
        Lighting preset id.

    Returns
    -------
    ycrystal.core.scene.Environment
        New environment; its ``lighting`` field names the preset.
    """
    from dataclasses import replace

    light = get_lighting(lighting_id)
    return replace(
        environment,
        lighting=light.id,
        key_light=light.key_light,
        fill_light=light.fill_light,
        key_azimuth=light.key_azimuth,
        key_elevation=light.key_elevation,
        light_size=light.light_size,
        shadows=light.shadows,
    )


def environment_from_preset(environment_id: str) -> Any:
    """Return the `Environment` that preset ``environment_id`` describes.

    The preset initialises the background, the floor, the lighting (from its lighting
    preset), the reflection panel, and the transparency.

    Parameters
    ----------
    environment_id
        Environment preset id.

    Returns
    -------
    ycrystal.core.scene.Environment
        New environment whose ``preset`` field names the preset.

    Examples
    --------
    >>> from ycrystal.presets import environment_from_preset
    >>> studio = environment_from_preset("studio_white")
    >>> studio.floor, studio.lighting, studio.transparent
    (True, 'studio', False)
    """
    from ycrystal.core.scene import Environment

    preset = get_environment(environment_id)
    environment = Environment(
        background=preset.background,
        transparent=preset.transparent,
        preset=preset.id,
        background_mode=preset.background_mode,
        background_bottom=preset.background_bottom,
        clouds=preset.clouds,
        floor=preset.floor,
        floor_color=preset.floor_color,
        floor_reflection=preset.floor_reflection,
        floor_offset=preset.floor_offset,
        reflector=preset.reflector,
    )
    return apply_lighting(environment, preset.lighting)
