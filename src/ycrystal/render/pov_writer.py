"""Write a POV-Ray 3.7 scene (.pov) and render settings (.ini) from the shared scene.

The camera is written with explicit ``location``/``direction``/``right``/``up``
vectors taken from [`Camera`][ycrystal.core.camera.Camera]; ``look_at`` and ``sky`` are
not used, so POV-Ray does not re-derive the basis or flip handedness. Coordinates are
the original right-handed world coordinates in ångström, which keeps the scene
readable and editable.

Scenes use only POV-Ray 3.7 language features (``#version 3.7;``). Materials that use
native POV-Ray identifiers (for example ``T_Gold_3C``) ``#include`` the standard files
that declare them; other scenes are self-contained. Colours are written as sRGB values
and converted to linear light inside the scene (``assumed_gamma 1.0``); the ``.ini``
file writes the PNG with sRGB gamma. The writer produces text only; running POV-Ray is the job of
[`ycrystal.render.jobs`][ycrystal.render.jobs].
"""

from __future__ import annotations

import dataclasses
import datetime as _dt
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from ycrystal import __version__
from ycrystal.core.background import placement
from ycrystal.core.camera import Camera
from ycrystal.core.lighting import (
    AREA_LIGHT_ADAPTIVE,
    AREA_LIGHT_SAMPLES,
    resolve_lighting_for_bounds,
)
from ycrystal.core.scene import RGB, DisplayGeometry, Environment

POV_LANGUAGE_VERSION = "3.7"
"""POV-Ray scene-language version declared in every scene (``#version 3.7;``)."""


@dataclass(frozen=True)
class RenderSettings:
    """Output image settings for an exported or rendered scene.

    Presentation state only. The aspect ratio ``width / height`` decides how much of
    the scene is visible horizontally (see
    [`Camera.visible_size`][ycrystal.core.camera.Camera.visible_size]); the image is
    never stretched.

    Attributes
    ----------
    width
        Image width in pixels.
    height
        Image height in pixels. The GUI derives it from the width and the viewport's
        aspect ratio.
    antialias
        Whether POV-Ray antialiases (adaptive sampling method 1, threshold 0.1, depth
        3, no jitter).
    transparent_background
        Whether the PNG gets an alpha channel with a fully transparent background
        instead of the environment's background colour.
    aspect_locked
        Whether the Render panel keeps `aspect_ratio` when width or height is edited
        (interface state saved in projects; it does not affect the image).
    aspect_ratio
        Target ratio ``width / height`` of the lock, or ``None`` for
        ``width / height`` (see [`ycrystal.core.aspect`][ycrystal.core.aspect]).

    Raises
    ------
    ValueError
        If `width` or `height` is less than 1, or `aspect_ratio` is not positive.
    """

    width: int = 1200
    height: int = 800
    antialias: bool = True
    transparent_background: bool = False
    aspect_locked: bool = True
    aspect_ratio: float | None = None

    def __post_init__(self) -> None:
        if self.width < 1 or self.height < 1:
            raise ValueError("render dimensions must be positive")
        if self.aspect_ratio is not None and not self.aspect_ratio > 0:
            raise ValueError("aspect_ratio must be positive")

    def target_ratio(self) -> float:
        """Return `aspect_ratio`, or ``width / height`` when it is not set."""
        return self.aspect_ratio if self.aspect_ratio is not None else self.width / self.height


def _f(value: float) -> str:
    text = f"{value:.6f}".rstrip("0").rstrip(".")
    return "0" if text in ("-0", "") else text


def _v(vector: np.ndarray | tuple[float, ...]) -> str:
    return "<" + ", ".join(_f(float(c)) for c in vector) + ">"


def _srgb(color: RGB) -> str:
    return "Ycr_sRGB(" + ", ".join(f"{c:.4f}" for c in color) + ")"


FLOOR_TILT_DEG = 20.0
"""Tilt of the floor towards the viewer, in degrees (0 would show it edge-on)."""

_CELL_FINISH = "ambient 0.08 diffuse 0.75 specular 0.35 roughness 0.02"
_FLOOR_FINISH = "ambient 0.3 diffuse 0.65 specular 0.05 roughness 0.05"


def _materials_used(geometry: DisplayGeometry) -> list:
    """Material presets of the geometry in catalog order (the default if no atoms).

    Includes the arrow material when the geometry has vector arrows.
    """
    from ycrystal.presets import get_material

    ids = set(geometry.materials) or {geometry.material}
    if geometry.arrows:
        ids.add(geometry.arrow_material)
    return sorted((get_material(i) for i in ids), key=lambda m: (m.order, m.id))


def required_includes(geometry: DisplayGeometry) -> tuple[str, ...]:
    """Return the standard POV-Ray include files a scene needs, in loading order.

    Parameters
    ----------
    geometry
        Geometry whose resolved materials are inspected.

    Returns
    -------
    tuple of str
        Include file names without duplicates; empty when only Ycrystal recipes are
        used.

    Raises
    ------
    ycrystal.presets.PresetError
        If a material id is unknown.
    """
    names: list[str] = []
    for material in _materials_used(geometry):
        for name in material.includes:
            if name not in names:
                names.append(name)
    return tuple(names)


def _identifier(material: object, element: str, default_id: str) -> str:
    """Return the declared name of a material on one element (shared for own pigments)."""
    prefix = "Ycr_Material_" if material.declaration == "material" else "Ycr_Texture_"
    clean = "".join(ch for ch in element if ch.isalnum())
    if not material.keeps_element_color:
        return prefix + material.id
    if material.id == default_id:
        return prefix + clean
    return prefix + clean + "_" + material.id


def _declaration(material: object, ident: str, color: RGB) -> list[str]:
    """``#declare`` lines for one material (on one element colour)."""
    normal = f" normal {{ {material.normal} }}" if material.normal else ""
    scale = f" scale {_f(material.texture_scale)}" if material.texture_scale != 1.0 else ""
    finish = f"finish {{ {material.finish} }}" if material.finish else ""
    if material.kind == "finish":
        return [
            f"#declare {ident} = texture {{",
            f"  pigment {{ color {_srgb(color)} }}{normal}",
            f"  {finish}",
            "}",
        ]
    if material.kind == "pigment":
        return [
            f"#declare {ident} = texture {{",
            f"  pigment {{ {material.pigment}{scale} }}{normal}",
            f"  {finish}",
            "}",
        ]
    if material.kind == "texture":
        return [f"#declare {ident} = texture {{ {material.texture}{scale} }}"]
    if material.material:  # native material identifier
        return [f"#declare {ident} = material {{ {material.material}{scale} }}"]
    lines = [
        f"#declare {ident} = material {{",
        f"  texture {{ pigment {{ color {_srgb(color)} filter {_f(material.filter)} }}{normal}",
        f"            {finish} }}",
    ]
    if material.interior:
        lines.append(f"  interior {{ {material.interior} }}")
    lines.append("}")
    return lines


def _surface(material: object, ident: str, radius: float, position: np.ndarray) -> str:
    """Object modifier applying a declared material, in its texture space."""
    text = f"{material.declaration} {{ {ident}"
    if material.texture_space == "unit":
        text += f" scale {_f(radius)} translate {_v(position)}"
    return text + " }"


def _environment_comment(environment: Environment, transparent: bool) -> str:
    e = environment
    if transparent:
        background = "transparent (alpha); floor and backdrop left out"
        if e.background_mode == "image" and e.image is not None:
            background += f' (background picture "{_comment_safe(e.image.name)}" kept, not drawn)'
    elif e.background_mode == "solid" or (e.background_mode == "image" and e.image is None):
        background = f"solid {_rgb_text(e.background)}"
    elif e.background_mode == "image":
        image = e.image
        background = (
            f'picture "{_comment_safe(image.name)}" ({image.width} x {image.height} px), '
            f"{image.fit}, zoom {_f(image.zoom)}, offset {_f(image.offset_x)} "
            f"{_f(image.offset_y)}, brightness {_f(image.brightness)}, "
            f"margin {_rgb_text(e.background)}"
        )
    elif e.background_mode == "gradient":
        background = f"gradient {_rgb_text(e.background_bottom)} to {_rgb_text(e.background)}"
    else:
        background = (
            f"sky {_rgb_text(e.background_bottom)} to {_rgb_text(e.background)}, "
            f"clouds {_f(e.clouds)}"
        )
    floor = (
        f"floor {_rgb_text(e.floor_color)}, reflection {_f(e.floor_reflection)}, "
        f"offset {_f(e.floor_offset)} A"
        if e.floor and not transparent
        else "no floor"
    )
    size = f"area light {_f(e.light_size)} x scene radius" if e.light_size > 0 else "point light"
    return (
        f'// Environment "{e.preset}": background {background}; {floor}.\n'
        f'// Lighting "{e.lighting}": key {_f(e.key_light)} at azimuth {_f(e.key_azimuth)} deg, '
        f"elevation {_f(e.key_elevation)} deg, {size}, shadows {'on' if e.shadows else 'off'}; "
        f"fill {_f(e.fill_light)}; reflection panel {'on' if e.reflector else 'off'}."
    )


def _comment_safe(text: str) -> str:
    """Text for a one-line comment (no line breaks or quotes)."""
    return " ".join(str(text).split()).replace('"', "'")


def _rgb_text(color: RGB) -> str:
    return "sRGB(" + ", ".join(f"{c:.3f}" for c in color) + ")"


def scene_to_pov(
    geometry: DisplayGeometry,
    camera: Camera,
    environment: Environment,
    settings: RenderSettings,
    *,
    title: str = "Ycrystal scene",
    renderer_note: str | None = None,
) -> str:
    """Return the text of a POV-Ray scene.

    Parameters
    ----------
    geometry
        Atoms and cell edges to draw; hidden atoms are already absent from it.
    camera
        View to reproduce.
    environment
        Background, floor, transparency, and lighting.
    settings
        Output size and background transparency. The size sets the camera's visible
        width and height; it should match the size in the ``.ini`` file. The background
        is transparent if either ``settings.transparent_background`` or
        ``environment.transparent`` is set.
    title
        Text of the first comment line.
    renderer_note
        Optional comment naming the renderer the scene was written for.

    Returns
    -------
    str
        The scene text. Its header lists the standard ``#include`` files the materials
        need (see [`required_includes`][ycrystal.render.pov_writer.required_includes]);
        a scene without them is self-contained.

    Raises
    ------
    ycrystal.presets.PresetError
        If a material of the geometry is not a known preset.

    Notes
    -----
    The camera is orthographic, with ``direction`` set to the unit viewing direction
    and ``right`` and ``up`` set to the screen vectors scaled to the visible width and
    height in Å. Its ``location`` lies on the line through the focal point along the
    viewing direction, far enough back to keep everything drawn (and, with a floor, the
    whole frame) in front of the eye; under orthographic projection this does not change
    the image.

    Lights come from [`resolve_lighting`][ycrystal.core.lighting.resolve_lighting]: they
    are placed around the camera's focal point at ``4 R + |C - F| + 10`` Å (``R`` and
    ``C`` from the geometry's bounding sphere), the key light in the environment's
    direction (a circular, oriented area light without jitter when ``light_size`` > 0,
    so renders are deterministic) and a shadowless fill light at the lower right; a
    light with non-positive intensity is omitted. There is no distance attenuation.

    A floor is a plane below the drawn spheres as seen in the frame, tilted by
    [`FLOOR_TILT_DEG`][ycrystal.render.pov_writer.FLOOR_TILT_DEG] towards the viewer;
    in an orthographic view it fills the background. Gradients and skies are painted on
    a backdrop plane behind the scene, aligned with the frame (a ``sky_sphere`` would be
    a single colour in an orthographic view); it sits in a ``light_group`` without lights
    because it needs no lighting. Transparent backgrounds leave out floor and backdrop.
    The optional reflection panel is a bright disc on the key-light side of the
    structure (``3 R`` from ``C``) marked ``no_image``: invisible to the camera, it
    appears only in reflections.

    Each material is declared once per element colour (once in total for materials with
    their own pigment), as a ``texture`` or a ``material``. Materials in unit texture
    space are applied to a unit sphere that is scaled and moved to each atom. Each atom
    is a ``sphere`` with a comment giving its 1-based source atom number, element, and
    image offset; a comment states how many atoms are hidden. Bonds are two half
    cylinders with the material of their endpoint atoms, using geometry.bond_radius.
    Cell edges are cylinders with spheres at the corners, marked ``no_shadow``.

    The header records the generation time (UTC), so two exports of the same scene
    differ in that line.
    """
    used = _materials_used(geometry)
    by_id = {m.id: m for m in used}
    includes = required_includes(geometry)
    transparent = settings.transparent_background or environment.transparent
    right, up, direction = camera.basis()
    world_w, world_h = camera.visible_size(settings.width, settings.height)
    focal = np.asarray(camera.focal_point)
    center, radius = geometry.bounding_sphere()
    points, radii = geometry.points_and_radii()

    # The orthographic eye must lie in front of everything drawn.
    depth_needed = float(np.max(-((points - focal) @ direction) + radii)) if len(points) else 0.0
    eye_distance = max(camera.distance, depth_needed + 1.0)

    floor = environment.floor and not transparent
    picture = environment.image if environment.background_mode == "image" else None
    backdrop = (
        environment.background_mode in ("gradient", "sky") or picture is not None
    ) and not transparent
    tilt = np.radians(FLOOR_TILT_DEG)
    floor_normal = np.cos(tilt) * up - np.sin(tilt) * direction
    floor_height = 0.0
    if floor:
        lowest = float(np.min(points @ floor_normal - radii)) if len(points) else focal @ up
        floor_height = lowest - environment.floor_offset
        # The whole frame must start above the floor: the eye plane crosses it otherwise.
        frame_low = float(focal @ floor_normal) - 0.5 * world_h * np.cos(tilt)
        eye_distance = max(eye_distance, (floor_height + 1.0 - frame_low) / np.sin(tilt))
    location = focal - eye_distance * direction

    rig = resolve_lighting_for_bounds(environment, camera, center, radius)

    lines: list[str] = []
    add = lines.append
    stamp = _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    add(f"// {title}")
    add(f"// Generated by Ycrystal {__version__} on {stamp}.")
    if renderer_note:
        add(f"// Renderer used: {renderer_note}")
    add("// Units: angstrom; right-handed world coordinates (unchanged from the structure).")
    add(f"// Image: {settings.width} x {settings.height} px; render with the matching .ini file.")
    if includes:
        add(
            "// Requires standard POV-Ray include files: "
            + ", ".join(includes)
            + " (shipped with POV-Ray; not self-contained)."
        )
    else:
        add("// No #include files are required.")
    add("")
    add(f"#version {POV_LANGUAGE_VERSION};")
    add("global_settings { assumed_gamma 1.0 max_trace_level 8 }")
    for include in includes:
        add(f'#include "{include}"')
    add("")
    add("// Colours below are written as sRGB values and converted to linear light.")
    add(
        "#declare Ycr_Linear = function(c) { select(c - 0.04045, c / 12.92, "
        "pow((c + 0.055) / 1.055, 2.4)) }"
    )
    add("#macro Ycr_sRGB(R, G, B) rgb <Ycr_Linear(R), Ycr_Linear(G), Ycr_Linear(B)> #end")
    add("")
    add("// Orthographic camera. right/up lengths are the visible width/height (angstrom).")
    add("camera {")
    add("  orthographic")
    add(f"  location  {_v(location)}")
    add(f"  direction {_v(direction)}")
    add(f"  right     {_v(right * world_w)}")
    add(f"  up        {_v(up * world_h)}")
    add("}")
    add("")
    add(_environment_comment(environment, transparent))
    if transparent:
        add("background { color rgbt <0, 0, 0, 1> }  // transparent (Output_Alpha=on)")
    elif environment.background_mode == "solid" or (
        environment.background_mode == "image" and picture is None
    ):
        add(f"background {{ color {_srgb(environment.background)} }}")
    elif picture is not None:
        add(f"background {{ color {_srgb(picture.mean_color)} }}  // seen only in reflections")
    else:
        mean = tuple(
            0.5 * (a + b)
            for a, b in zip(environment.background, environment.background_bottom, strict=True)
        )
        add(f"background {{ color {_srgb(mean)} }}  // seen only in reflections")
    if backdrop and picture is not None:
        frame = (focal, right, up, direction, world_w, world_h)
        lines.extend(_image_backdrop(environment, points, radii, *frame))
    elif backdrop:
        lines.extend(_backdrop(environment, points, radii, focal, right, up, direction, world_h))
    if floor:
        add("// Floor: below the structure as seen in the frame, tilted towards the viewer.")
        add(f"plane {{ {_v(floor_normal)}, {_f(floor_height)}")
        add(f"  texture {{ pigment {{ color {_srgb(environment.floor_color)} }}")
        reflection = (
            f" reflection {_f(environment.floor_reflection)}"
            if environment.floor_reflection > 0
            else ""
        )
        add(f"            finish {{ {_FLOOR_FINISH}{reflection} }} }}")
        add("}")
    add("")
    add("// Lights are placed relative to the camera (key from the environment, lower-right fill).")
    key, fill, panel = rig.key, rig.fill, rig.panel
    if key.enabled:
        extra = ""
        if key.area_axes is not None:
            axis1, axis2 = key.area_axes
            extra += (
                f" area_light {_v(axis1)}, {_v(axis2)}, {AREA_LIGHT_SAMPLES}, "
                f"{AREA_LIGHT_SAMPLES} adaptive {AREA_LIGHT_ADAPTIVE} circular orient"
            )
        if not key.shadows:
            extra += " shadowless"
        add(f"light_source {{ {_v(key.position)} color rgb {_f(key.intensity)}{extra} }}")
    if fill.enabled:
        add(f"light_source {{ {_v(fill.position)} color rgb {_f(fill.intensity)} shadowless }}")
    if panel is not None:
        add("// Reflection panel: invisible to the camera, seen in reflections only.")
        add(
            f"disc {{ {_v(panel.center)}, {_v(panel.normal)}, {_f(panel.radius)} "
            "pigment { rgb 1 } finish { ambient 1 diffuse 0 } no_image no_shadow }"
        )
    add("")
    for material in used:
        native = f" Native: {', '.join(material.native)}." if material.native else ""
        add(f'// Material "{material.id}": {material.name}. {material.description}{native}')
    idents: dict[tuple[str, str], str] = {}
    for element, color, material_id in zip(
        geometry.elements, geometry.colors, geometry.materials, strict=True
    ):
        material = by_id[material_id]
        key = (material_id, element if material.keeps_element_color else "")
        if key in idents:
            continue
        ident = _identifier(material, element, geometry.material)
        idents[key] = ident
        rgb = (float(color[0]), float(color[1]), float(color[2]))
        lines.extend(_declaration(material, ident, rgb))
    arrow_material = by_id.get(geometry.arrow_material) if geometry.arrows else None
    arrow_ident = ""
    if arrow_material is not None:  # arrows have their own colour, not an element's
        key = (arrow_material.id, "Arrow" if arrow_material.keeps_element_color else "")
        if key not in idents:
            idents[key] = _identifier(arrow_material, "Arrow", geometry.material)
            lines.extend(_declaration(arrow_material, idents[key], geometry.arrow_color))
        arrow_ident = idents[key]
    add(
        f"#declare Ycr_Texture_Cell = texture {{ pigment {{ color "
        f"{_srgb(geometry.cell_edge_color)} }} finish {{ {_CELL_FINISH} }} }}"
    )

    def declared(row: int) -> tuple[object, str]:
        material = by_id[geometry.materials[row]]
        element = geometry.elements[row]
        return material, idents[(material.id, element if material.keeps_element_color else "")]

    def surface(row: int) -> str:
        material, ident = declared(row)
        return _surface(material, ident, float(geometry.radii[row]), geometry.positions[row])

    add("")
    add(f"// Atoms ({len(geometry)}): source atom number (1-based, input order) and periodic image")
    if geometry.hidden_count:
        add(f"// ({geometry.hidden_count} atoms hidden in Ycrystal are not written.)")
    for row, (atom_id, element, pos, rad) in enumerate(
        zip(geometry.atom_ids, geometry.elements, geometry.positions, geometry.radii, strict=True)
    ):
        source, image = atom_id
        material, ident = declared(row)
        if material.texture_space == "unit":  # unit sphere, then scaled with its texture
            shape = (
                f"sphere {{ <0, 0, 0>, 1 {material.declaration} {{ {ident} }} "
                f"scale {_f(float(rad))} translate {_v(pos)} }}"
            )
        else:
            shape = f"sphere {{ {_v(pos)}, {_f(float(rad))} {surface(row)} }}"
        add(f"{shape}  // atom #{source + 1} {element} image {image}")
    if len(geometry.bonds):
        add("")
        add(f"// Bonds ({len(geometry.bonds)}): each half takes the material of its atom.")
        r_bond = _f(geometry.bond_radius)
        for a, b in geometry.bonds:
            start, end = geometry.positions[a], geometry.positions[b]
            tex_a, tex_b = surface(a), surface(b)
            if tex_a == tex_b:
                add(f"cylinder {{ {_v(start)}, {_v(end)}, {r_bond} {tex_a} }}")
            else:
                mid = 0.5 * (start + end)
                add(f"cylinder {{ {_v(start)}, {_v(mid)}, {r_bond} {tex_a} }}")
                add(f"cylinder {{ {_v(mid)}, {_v(end)}, {r_bond} {tex_b} }}")
    if arrow_material is not None:
        lines.extend(_arrow_lines(geometry, arrow_material, arrow_ident))
    if len(geometry.cell_edges):
        add("")
        add("// Cell edges (no_shadow: edges do not darken atoms).")
        r_edge = _f(geometry.cell_edge_radius)
        corners: dict[tuple[float, ...], np.ndarray] = {}
        for start, end in geometry.cell_edges:
            add(
                f"cylinder {{ {_v(start)}, {_v(end)}, {r_edge} texture {{ Ycr_Texture_Cell }} "
                "no_shadow }"
            )
            for point in (start, end):
                corners.setdefault(tuple(np.round(point, 6)), point)
        for corner in corners.values():
            add(f"sphere {{ {_v(corner)}, {r_edge} texture {{ Ycr_Texture_Cell }} no_shadow }}")
    add("")
    return "\n".join(lines)


def _backdrop(
    environment: Environment,
    points: np.ndarray,
    radii: np.ndarray,
    focal: np.ndarray,
    right: np.ndarray,
    up: np.ndarray,
    direction: np.ndarray,
    world_h: float,
) -> list[str]:
    """Return a self-lit backdrop plane carrying a gradient or sky aligned with the frame."""
    distance = _backdrop_distance(points, radii, focal, direction, world_h)
    # Local pattern coordinates: x right, y up across the frame (0 bottom, 1 top), unit
    # length = frame height. POV-Ray's matrix rows are the images of x, y, z and the shift.
    origin = focal - 0.5 * world_h * up
    matrix = ", ".join(
        ", ".join(_f(float(c)) for c in row)
        for row in (right * world_h, up * world_h, -direction * world_h, origin)
    )
    bottom, top = _srgb(environment.background_bottom), _srgb(environment.background)
    lines = [
        "// Backdrop behind the scene: the gradient/sky runs from the bottom to the top of the "
        "frame.",
        "// It is self-lit; the light_group without lights spares POV-Ray its shadow rays.",
        "light_group {",
        f"plane {{ {_v(-direction)}, {_f(distance)}",
        "  texture {",
        f"    pigment {{ gradient y color_map {{ [0 color {bottom}] [1 color {top}] }}",
        f"              scale 1.02 translate -0.01*y matrix <{matrix}> }}",
        "    finish { ambient 1 diffuse 0 }",
        "  }",
    ]
    if environment.background_mode == "sky" and environment.clouds > 0:
        start = 1.0 - 0.75 * environment.clouds
        lines += [
            "  texture {  // clouds",
            "    pigment { bozo turbulence 0.65 octaves 6 omega 0.6 lambda 2.2",
            f"      color_map {{ [0 rgbt <1, 1, 1, 1>] [{_f(start)} rgbt <1, 1, 1, 1>]",
            f"                  [{_f(min(start + 0.2, 1.0))} rgb <1, 1, 1>] "
            "[1 rgb <0.86, 0.87, 0.9>] }",
            f"      scale <0.55, 0.16, 0.55> matrix <{matrix}> }}",
            "    finish { ambient 1 diffuse 0 }",
            "  }",
        ]
    lines += ["  no_shadow", "}", "global_lights off", "}"]
    return lines


def _arrow_lines(geometry: DisplayGeometry, material: object, ident: str) -> list[str]:
    """Cylinder-and-cone objects of the vector arrows (lit and shadowed like atoms)."""
    from ycrystal.core.vectors import MEANINGS

    lines = [
        "",
        f"// Vectors ({len(geometry.arrows)}): Cartesian components in the structure frame; "
        "each arrow is a",
        "// shaft (cylinder) and head (cone) from tail to tip; the head is part of the "
        "total length.",
    ]
    for arrow in geometry.arrows:
        source, image = arrow.host
        row = geometry.index_of(arrow.host)
        element = geometry.elements[row] if row is not None else "?"
        unit = MEANINGS[arrow.meaning][1]
        comps = ", ".join(_f(c) for c in arrow.components)
        tail, base, tip = (np.asarray(p, dtype=float) for p in (arrow.tail, arrow.base, arrow.tip))
        if material.texture_space == "unit":
            middle = 0.5 * (tail + tip)
            surface = _surface(material, ident, 0.5 * arrow.length, middle)
        else:
            surface = f"{material.declaration} {{ {ident} }}"
        lines.append(
            f"// {MEANINGS[arrow.meaning][0]} on atom #{source + 1} {element} image {image}: "
            f"({comps}){' ' + unit.replace('μ', 'mu_') if unit else ''}"
        )
        lines.append(f"cylinder {{ {_v(tail)}, {_v(base)}, {_f(arrow.shaft_radius)} {surface} }}")
        lines.append(f"cone {{ {_v(base)}, {_f(arrow.head_radius)}, {_v(tip)}, 0 {surface} }}")
    return lines


def _backdrop_distance(
    points: np.ndarray, radii: np.ndarray, focal: np.ndarray, direction: np.ndarray, world_h: float
) -> float:
    """Plane constant of a backdrop behind everything drawn (``plane { -direction, d }``)."""
    far = float(np.max((points - focal) @ direction + radii)) if len(points) else 0.0
    spread = float(np.max(radii)) if len(radii) else 1.0
    depth = far + max(spread, 1.0) + 0.25 * world_h
    return float((-direction) @ (focal + depth * direction))


def _image_backdrop(
    environment: Environment,
    points: np.ndarray,
    radii: np.ndarray,
    focal: np.ndarray,
    right: np.ndarray,
    up: np.ndarray,
    direction: np.ndarray,
    world_w: float,
    world_h: float,
) -> list[str]:
    """Return a self-lit backdrop plane showing the background picture in the frame.

    The picture is an ``image_map`` placed with
    [`placement`][ycrystal.core.background.placement] in frame-height units around the
    frame centre, so its position depends only on the output frame, not on the
    orientation of the structure. ``once`` leaves the plane outside the picture (and
    under its transparent pixels) to the lower texture, which has the background
    colour. The plane casts no shadow, is not lit (``light_group`` without lights), and
    is invisible to reflection rays (``no_reflection``); refracted rays see it.
    """
    from ycrystal.io.images import asset_filename

    image = environment.image
    assert image is not None
    distance = _backdrop_distance(points, radii, focal, direction, world_h)
    cx, cy, w, h = placement(
        image.width,
        image.height,
        world_w / world_h,
        image.fit,
        image.zoom,
        image.offset_x,
        image.offset_y,
    )
    # Local coordinates: x right, y up, unit length = frame height, origin = frame centre.
    matrix = ", ".join(
        ", ".join(_f(float(c)) for c in row)
        for row in (right * world_h, up * world_h, -direction * world_h, focal)
    )
    name = asset_filename(image.asset, image.format)
    kind = "png" if image.format == "png" else "jpeg"
    return [
        f'// Background picture "{_comment_safe(image.name)}", stored as {name} next to this file.',
        "// Placed in the output frame (frame-height units around the frame centre); it is",
        "// self-lit, casts no shadow, and is not seen in reflections (no_reflection).",
        "light_group {",
        f"plane {{ {_v(-direction)}, {_f(distance)}",
        f"  texture {{ pigment {{ color {_srgb(environment.background)} }} "
        "finish { ambient 1 diffuse 0 } }",
        "  texture {",
        f'    pigment {{ image_map {{ {kind} "{name}" gamma srgb once interpolate 2 }}',
        f"              translate <-0.5, -0.5, 0> scale <{_f(w)}, {_f(h)}, 1> "
        f"translate <{_f(cx)}, {_f(cy)}, 0>",
        f"              matrix <{matrix}> }}",
        f"    finish {{ ambient {_f(image.brightness)} diffuse 0 }}",
        "  }",
        "  no_shadow no_reflection",
        "}",
        "global_lights off",
        "}",
    ]


def stage_assets(
    directory: Path, environment: Environment, transparent: bool = False
) -> list[Path]:
    """Copy the pictures a scene draws into ``directory`` and return their paths.

    Only the background picture of an ``"image"`` environment is drawn (not with a
    transparent background). Files are named by content
    ([`asset_filename`][ycrystal.io.images.asset_filename]); an existing file with that
    name is replaced.

    Raises
    ------
    ycrystal.io.images.ImageError
        If the picture is not registered in this session.
    OSError
        If the file cannot be written.
    """
    from ycrystal.io.images import get_image

    image = environment.image
    if environment.background_mode != "image" or image is None or transparent:
        return []
    asset = get_image(image.asset)
    target = Path(directory) / asset.filename
    target.write_bytes(asset.data)
    return [target]


def render_ini(settings: RenderSettings, pov_name: str, image_name: str) -> str:
    """Return the text of a POV-Ray ``.ini`` file for one scene.

    Every option that affects the output is set explicitly, so defaults from a user or
    system ``povray.ini`` (for example ``Display=On``) cannot change the result.

    Parameters
    ----------
    settings
        Image size, antialiasing, and background transparency.
    pov_name
        Scene file name, relative to the directory in which POV-Ray runs. Double
        quotes are removed.
    image_name
        Output PNG name, relative to the same directory. Double quotes are removed.

    Returns
    -------
    str
        The ``.ini`` text: PNG output with 8 bits per channel and sRGB gamma, alpha
        only for transparent backgrounds, ``Quality=9``, the requested size and
        antialiasing, and no display window or pause. ``Verbose=on`` makes POV-Ray
        print ``Rendered N of M pixels`` progress lines, which Ycrystal shows during
        renders; it does not change the image.
    """

    def quoted(name: str) -> str:
        return '"' + name.replace('"', "") + '"'

    lines = [
        "; Ycrystal render settings. Run from this directory:  povray <this file>",
        f"Input_File_Name={quoted(pov_name)}",
        f"Output_File_Name={quoted(image_name)}",
        "Output_to_File=on",
        "Output_File_Type=N",
        "Bits_Per_Color=8",
        "File_Gamma=sRGB",
        f"Output_Alpha={'on' if settings.transparent_background else 'off'}",
        f"Width={settings.width}",
        f"Height={settings.height}",
        "Quality=9",
        f"Antialias={'on' if settings.antialias else 'off'}",
        "Sampling_Method=1",
        "Antialias_Threshold=0.1",
        "Antialias_Depth=3",
        "Jitter=off",
        "Display=off",
        "Pause_When_Done=off",
        "Verbose=on",
        "",
    ]
    return "\n".join(lines)


def write_scene_files(
    directory: Path,
    basename: str,
    geometry: DisplayGeometry,
    camera: Camera,
    environment: Environment,
    settings: RenderSettings,
    **kwargs: str,
) -> tuple[Path, Path, Path]:
    """Write a scene file and its ``.ini`` file into a directory.

    Parameters
    ----------
    directory
        Existing directory for both files.
    basename
        File name without suffix. Spaces and non-ASCII characters are supported;
        avoid double quotes because the INI writer removes them from file names.
    geometry
        Atoms and cell edges to draw.
    camera
        View to reproduce.
    environment
        Background, transparency, and light intensities. A transparent environment
        also switches on ``Output_Alpha`` in the ``.ini`` file.
    settings
        Output image settings.
    **kwargs
        Passed to [`scene_to_pov`][ycrystal.render.pov_writer.scene_to_pov]
        (``title``, ``renderer_note``).

    Returns
    -------
    pov_path : pathlib.Path
        ``directory / f"{basename}.pov"``.
    ini_path : pathlib.Path
        ``directory / f"{basename}.ini"``.
    image_path : pathlib.Path
        ``directory / f"{basename}.png"``, the output named in the ``.ini`` file. It is
        not created here.

    Raises
    ------
    OSError
        If a file cannot be written, for example because `directory` does not exist.

    Notes
    -----
    Both files are written as UTF-8 and replace existing files of the same name without
    asking. The ``.ini`` file refers to the scene and the image by relative names, so
    run ``povray basename.ini`` with `directory` as the working directory (POV-Ray for
    Windows: ``pvengine64.exe /EXIT /NR basename.ini``, see
    [`render_arguments`][ycrystal.render.povray.render_arguments]). The I/O
    restrictions of the Ubuntu and Linux Mint ``povray`` package also allow writing
    the image only there (or under ``/tmp``). A background picture is copied next to
    the scene ([`stage_assets`][ycrystal.render.pov_writer.stage_assets]) and named
    relatively, so the directory can be moved as a whole.
    """
    directory = Path(directory)
    if environment.transparent and not settings.transparent_background:
        settings = dataclasses.replace(settings, transparent_background=True)
    pov_path = directory / f"{basename}.pov"
    ini_path = directory / f"{basename}.ini"
    image_path = directory / f"{basename}.png"
    stage_assets(directory, environment, settings.transparent_background)
    pov_path.write_text(
        scene_to_pov(geometry, camera, environment, settings, **kwargs), encoding="utf-8"
    )
    ini_path.write_text(render_ini(settings, pov_path.name, image_path.name), encoding="utf-8")
    return pov_path, ini_path, image_path
