"""The ``.ycrystal`` project file: versioned JSON with the embedded structure.

A project that uses a background picture is saved as a ZIP package instead: the same
JSON document as ``project.json`` plus the picture under ``assets/`` (see
[`ycrystal.io.package`][ycrystal.io.package]). Both forms are recognised by content, so
the suffix stays ``.ycrystal``.

A project reopens without the original structure file: the canonical structure (cell,
positions, elements, labels, occupancy, movable flags) is stored in full, together with
its import provenance, the display settings (including hidden atoms), environment,
camera, and output settings. Floats are written with Python's shortest round-trip
representation, so reopening reproduces every coordinate exactly.

The top-level JSON object has the keys ``format`` (always ``"ycrystal-project"``),
``schema_version``, ``generator``, ``saved_at``, ``structure``, ``scene``,
``environment``, ``camera``, and ``output``. Machine-specific settings such as the
POV-Ray path are not stored in projects.

Schema history: 1 — first version (M1); 2 — repetitions, cell mode, and bonds (M2); 3 —
material and background presets, explicit output size (M3); 4 — element and atom
material overrides, element colours, and the full environment: background type, floor,
lighting, and reflection panel (M4); 5 — element radii (M5); 6 — background pictures
(``environment.background.image``, ZIP packages with assets; FR-BGIMAGE-01) and custom
material variants (top-level ``materials`` list with the full definition of every
variant the scene uses; FR-MATERIAL-01); 7 — atom-attached vectors (``scene.vectors``
with source defaults and image overrides at full precision, ``scene.vector_style``;
FR-VECTOR-01); 8 — the element legend (``scene.legend``; FR-LEGEND-01), absent and so
disabled in older files. Projects without a picture are still single JSON files. Older
files open with the M3 appearance: no overrides, plain background, no floor, and the
"soft" lighting. Schema-1 files load with bonds disabled to preserve their original
appearance. In every schema the saved camera describes the output image of
``output.width`` × ``output.height`` pixels (schemas 1 and 2 recorded the output size
the camera was rendered at), so reopening reproduces the framing exactly, whatever the
window size. Schema-1/2 files get the ``"satin"`` material they were drawn with, and the
``"transparent"`` background preset if their output had a transparent background.

The optional ``output.aspect_locked`` and ``output.aspect_ratio`` keys store the Render
panel's aspect-ratio lock (FR-RENDER-01). They do not change the stored contract, so the
schema version stays 5: files without them open locked to their own ``width / height``,
and Ycrystal 0.1.0 ignores them.
"""

from __future__ import annotations

import datetime as _dt
import json
import math
import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
from ase.data import chemical_symbols

from ycrystal import __version__
from ycrystal.core.annotation import TextAnnotation
from ycrystal.core.background import BackgroundImage
from ycrystal.core.bonds import BondSettings
from ycrystal.core.camera import Camera
from ycrystal.core.legend import LegendSettings
from ycrystal.core.polyhedra import PolyhedronRule
from ycrystal.core.scene import AtomId, BondId, Environment, SceneSettings
from ycrystal.core.structure import Structure
from ycrystal.core.vectors import VectorRecord, VectorSet, VectorStyle
from ycrystal.render.pov_writer import RenderSettings

PROJECT_FORMAT = "ycrystal-project"
"""Value of the ``format`` key that identifies a project file."""

SCHEMA_VERSION = 9
"""Schema version written by this Ycrystal; newer versions are refused on load."""

PACKAGE_DOCUMENT = "project.json"
"""Name of the JSON document inside a project package."""

PROJECT_SUFFIX = ".ycrystal"
"""File-name suffix of project files."""


class ProjectError(Exception):
    """A project file cannot be read; ``str(error)`` is a message for the user.

    The message starts with the file name when raised by
    [`load_project`][ycrystal.io.project.load_project].
    """


@dataclass
class Project:
    """Everything a project file stores, independent of any window.

    Attributes
    ----------
    structure
        The scientific structure, stored in full.
    scene
        Display settings, including hidden atoms and the boundary policy.
    environment
        Background, floor, transparency, and lighting.
    camera
        Camera of the output image (``output.width`` × ``output.height``), or ``None``
        to use the default view when the project is opened.
    output
        Output image size and antialiasing. ``transparent_background`` mirrors
        ``environment.transparent``, which is authoritative.

    Notes
    -----
    This container is mutable. Its scene, environment, camera, and output objects
    are frozen dataclasses. Structure arrays are read-only, but structure metadata
    remains mutable.
    """

    structure: Structure
    scene: SceneSettings = field(default_factory=SceneSettings)
    environment: Environment = field(default_factory=Environment)
    camera: Camera | None = None
    output: RenderSettings = field(default_factory=RenderSettings)


# ----- serialisation ----------------------------------------------------------------------
def project_to_dict(project: Project) -> dict[str, Any]:
    """Convert a project to a JSON-compatible dictionary (current schema).

    Parameters
    ----------
    project
        Project to convert; it is not modified.

    Returns
    -------
    dict
        The project document, with ``saved_at`` set to the current UTC time and
        ``generator`` naming this Ycrystal version. Metadata values are made
        JSON-compatible: NumPy arrays and scalars become lists and numbers, plain
        Python non-finite floats become ``None``, and other objects become strings.
        Values produced by NumPy conversion are not recursively sanitized, so
        non-finite NumPy values can remain. Hidden atoms are sorted.
    """
    s = project.structure
    scene = project.scene
    return {
        "format": PROJECT_FORMAT,
        "schema_version": SCHEMA_VERSION,
        "generator": f"Ycrystal {__version__}",
        "saved_at": _dt.datetime.now(_dt.UTC).isoformat(timespec="seconds"),
        "structure": {
            "cell": s.cell.tolist(),
            "positions": s.positions.tolist(),
            "numbers": s.numbers.tolist(),
            "symbols": list(s.symbols),  # for readers of the file; numbers are canonical
            "labels": list(s.labels),
            "pbc": list(s.pbc),
            "occupancy": s.occupancy.tolist(),
            "movable": None if s.movable is None else s.movable.tolist(),
            "metadata": _jsonable(s.metadata),
        },
        "scene": {
            "radius_scale": scene.radius_scale,
            "show_cell": scene.show_cell,
            "cell_edge_radius": scene.cell_edge_radius,
            "cell_edge_color": list(scene.cell_edge_color),
            "boundary_images": scene.boundary_images,
            "boundary_tolerance": scene.boundary_tolerance,
            "hidden": [
                {"atom": source, "image": list(image)} for source, image in sorted(scene.hidden)
            ],
            "repetitions": list(scene.repetitions),
            "cell_mode": scene.cell_mode,
            "material": scene.material,
            "element_materials": [
                {"element": element, "material": material_id}
                for element, material_id in scene.element_materials
            ],
            "atom_materials": [
                {"atom": source, "image": list(image), "material": material_id}
                for (source, image), material_id in scene.atom_materials
            ],
            "element_radii": [
                {"element": element, "radius": radius} for element, radius in scene.element_radii
            ],
            "element_colors": [
                {"element": element, "color": list(color)}
                for element, color in scene.element_colors
            ],
            "vectors": _vectors_to_dict(scene.vectors),
            "vector_style": _vector_style_to_dict(scene.vector_style),
            "legend": _legend_to_dict(scene.legend),
            "bond_overrides": [
                {
                    "atoms": [{"atom": source, "image": list(image)} for source, image in pair],
                    "visible": visible,
                }
                for pair, visible in scene.bond_overrides
            ],
            "polyhedra": [
                {
                    "centre": rule.centre,
                    "ligand": rule.ligand,
                    "cutoff": rule.cutoff,
                    "color": list(rule.color),
                    "opacity": rule.opacity,
                    "show_edges": rule.show_edges,
                    "enabled": rule.enabled,
                }
                for rule in scene.polyhedron_rules
            ],
            "annotations": [
                {
                    "text": label.text,
                    "x": label.x,
                    "y": label.y,
                    "font_size": label.font_size,
                    "font_family": label.font_family,
                    "color": list(label.color),
                    "alignment": label.alignment,
                    "bold": label.bold,
                    "enabled": label.enabled,
                }
                for label in scene.annotations
            ],
            "bonds": {
                "enabled": scene.bonds.enabled,
                "tolerance": scene.bonds.tolerance,
                "radius": scene.bonds.radius,
                "pairs": [
                    {"elements": [a, b], "enabled": on}
                    for a, b, on in sorted(scene.bonds.overrides)
                ],
            },
        },
        "environment": _environment_to_dict(project.environment),
        "materials": custom_definitions(scene),
        "camera": None if project.camera is None else project.camera.to_dict(),
        "output": {
            "width": project.output.width,
            "height": project.output.height,
            "antialias": project.output.antialias,
            "transparent_background": project.environment.transparent,
            "aspect_locked": project.output.aspect_locked,
            "aspect_ratio": project.output.aspect_ratio,  # null: width / height
        },
    }


def _environment_to_dict(e: Environment) -> dict[str, Any]:
    return {
        "preset": e.preset,
        "transparent": e.transparent,
        "background": {
            "mode": e.background_mode,
            "color": list(e.background),
            "bottom": list(e.background_bottom),
            "clouds": e.clouds,
            "image": None if e.image is None else _image_to_dict(e.image),
        },
        "floor": {
            "enabled": e.floor,
            "color": list(e.floor_color),
            "reflection": e.floor_reflection,
            "offset": e.floor_offset,
        },
        "lighting": {
            "preset": e.lighting,
            "key_light": e.key_light,
            "fill_light": e.fill_light,
            "key_azimuth": e.key_azimuth,
            "key_elevation": e.key_elevation,
            "light_size": e.light_size,
            "shadows": e.shadows,
            "reflector": e.reflector,
        },
    }


def _record_to_dict(record: VectorRecord) -> dict[str, Any]:
    return {
        "components": list(record.components),
        "meaning": record.meaning,
        "visible": record.visible,
    }


def _vectors_to_dict(vectors: VectorSet) -> dict[str, Any]:
    return {
        "sources": [
            {"atom": index, **_record_to_dict(record)} for index, record in vectors.sources
        ],
        "images": [
            {"atom": source, "image": list(image), "suppressed": True}
            if record is None
            else {"atom": source, "image": list(image), **_record_to_dict(record)}
            for (source, image), record in vectors.images
        ],
    }


def _vector_style_to_dict(style: VectorStyle) -> dict[str, Any]:
    return {
        "visible": style.visible,
        "placement": style.placement,
        "length_mode": style.length_mode,
        "length": style.length,
        "scale": style.scale,
        "shaft_radius": style.shaft_radius,
        "head_length": style.head_length,
        "head_radius": style.head_radius,
        "color": list(style.color),
        "material": style.material,
    }


def _record_from(d: dict[str, Any]) -> VectorRecord:
    return VectorRecord(
        components=tuple(float(v) for v in d["components"]),
        meaning=str(d.get("meaning", "moment")),
        visible=bool(d.get("visible", True)),
    )


def _vectors_from(d: Any) -> VectorSet:
    if not d:
        return VectorSet()
    sources = tuple((int(e["atom"]), _record_from(e)) for e in d.get("sources", []))
    images = tuple(
        ((int(e["atom"]), _image(e["image"])), None if e.get("suppressed") else _record_from(e))
        for e in d.get("images", [])
    )
    return VectorSet(sources, images)


def _vector_style_from(d: Any) -> VectorStyle:
    defaults = VectorStyle()
    if not d:
        return defaults
    return VectorStyle(
        visible=bool(d.get("visible", defaults.visible)),
        placement=str(d.get("placement", defaults.placement)),
        length_mode=str(d.get("length_mode", defaults.length_mode)),
        length=float(d.get("length", defaults.length)),
        scale=float(d.get("scale", defaults.scale)),
        shaft_radius=float(d.get("shaft_radius", defaults.shaft_radius)),
        head_length=float(d.get("head_length", defaults.head_length)),
        head_radius=float(d.get("head_radius", defaults.head_radius)),
        color=_rgb(d.get("color", defaults.color)),
        material=_known_material(str(d.get("material", defaults.material))),
    )


def _legend_to_dict(legend: LegendSettings) -> dict[str, Any]:
    return {
        "enabled": legend.enabled,
        "layout": legend.layout,
        "position": legend.position,
        "x": legend.x,
        "y": legend.y,
        "font_family": legend.font_family,
        "font_size": legend.font_size,
        "text_color": list(legend.text_color),
        "marker_size": legend.marker_size,
        "marker_style": legend.marker_style,
        "spacing": legend.spacing,
        "margin": legend.margin,
        "background": legend.background,
        "background_color": list(legend.background_color),
        "background_opacity": legend.background_opacity,
        "order": legend.order,
        "custom_order": list(legend.custom_order),
    }


def _legend_from(d: Any) -> LegendSettings:
    defaults = LegendSettings()
    if not d:
        return defaults
    return LegendSettings(
        enabled=bool(d.get("enabled", defaults.enabled)),
        layout=str(d.get("layout", defaults.layout)),
        position=str(d.get("position", defaults.position)),
        x=float(d.get("x", defaults.x)),
        y=float(d.get("y", defaults.y)),
        font_family=str(d.get("font_family", defaults.font_family)),
        font_size=float(d.get("font_size", defaults.font_size)),
        text_color=_rgb(d.get("text_color", defaults.text_color)),
        marker_size=float(d.get("marker_size", defaults.marker_size)),
        marker_style=str(d.get("marker_style", defaults.marker_style)),
        spacing=float(d.get("spacing", defaults.spacing)),
        margin=float(d.get("margin", defaults.margin)),
        background=bool(d.get("background", defaults.background)),
        background_color=_rgb(d.get("background_color", defaults.background_color)),
        background_opacity=float(d.get("background_opacity", defaults.background_opacity)),
        order=str(d.get("order", defaults.order)),
        custom_order=tuple(str(e) for e in d.get("custom_order", defaults.custom_order)),
    )


def _image_to_dict(image: BackgroundImage) -> dict[str, Any]:
    return {
        "asset": image.asset,
        "name": image.name,
        "width": image.width,
        "height": image.height,
        "format": image.format,
        "mean_color": list(image.mean_color),
        "fit": image.fit,
        "zoom": image.zoom,
        "offset": [image.offset_x, image.offset_y],
        "brightness": image.brightness,
    }


def _image_from(d: Any) -> BackgroundImage | None:
    if d is None:
        return None
    offset = d.get("offset", (0.0, 0.0))
    return BackgroundImage(
        asset=str(d["asset"]),
        name=str(d.get("name", "picture")),
        width=int(d["width"]),
        height=int(d["height"]),
        format=str(d.get("format", "png")),
        mean_color=_rgb(d.get("mean_color", (0.5, 0.5, 0.5))),
        fit=str(d.get("fit", "fill")),
        zoom=float(d.get("zoom", 1.0)),
        offset_x=float(offset[0]),
        offset_y=float(offset[1]),
        brightness=float(d.get("brightness", 1.0)),
    )


def custom_definitions(scene: SceneSettings) -> list[dict[str, Any]]:
    """Return the stored definitions of the custom materials a scene uses, by id."""
    from ycrystal.presets import get_definition
    from ycrystal.presets.custom import CUSTOM_PREFIX

    ids = sorted(m for m in scene.material_ids() if m.startswith(CUSTOM_PREFIX))
    return [get_definition(material_id).to_dict() for material_id in ids]


def register_custom_definitions(entries: Any) -> None:
    """Register the custom material definitions of a project or style document.

    Raises
    ------
    ProjectError
        If a definition is damaged, uses an unknown or non-editable base, has invalid
        values, or was made by a newer Ycrystal.
    """
    from ycrystal.presets import register_definition
    from ycrystal.presets.custom import DefinitionError, MaterialDefinition

    if entries is None:
        return
    if not isinstance(entries, list):
        raise ProjectError("The list of custom materials is damaged.")
    for entry in entries:
        try:
            register_definition(MaterialDefinition.from_dict(entry))
        except DefinitionError as exc:
            raise ProjectError(str(exc)) from None


def referenced_assets(environment: Environment) -> list:
    """Return the stored pictures an environment refers to (from the session registry).

    Raises
    ------
    ycrystal.io.images.ImageError
        If a referenced picture is not registered.
    """
    from ycrystal.io.images import get_image

    return [] if environment.image is None else [get_image(environment.image.asset)]


def check_assets(environment: Environment, assets: dict) -> None:
    """Check that the pictures an environment refers to are present and consistent.

    Raises
    ------
    ProjectError
        If a picture is missing or its recorded size or format differs.
    """
    image = environment.image
    if image is None:
        return
    asset = assets.get(image.asset)
    if asset is None:
        raise ProjectError(
            f"The background picture {image.name!r} is missing from the file. Choose the "
            "picture again, or open a copy of the project that was saved with it."
        )
    if (asset.width, asset.height, asset.format) != (image.width, image.height, image.format):
        raise ProjectError(f"The background picture {image.name!r} does not match its record.")


def project_from_dict(data: Any) -> Project:
    """Validate a project document and convert it to a [`Project`][ycrystal.io.project.Project].

    Parameters
    ----------
    data
        Parsed JSON document.

    Returns
    -------
    Project
        The project. Missing ``scene``, ``environment``, or ``output`` sections, and
        missing keys within them, take default values; a missing ``camera`` gives
        ``None``. Unknown keys are ignored. Schema-1 projects default to bonds off;
        schema-2 projects use current bond defaults when the section is absent.

    Raises
    ------
    ProjectError
        If the document is not a Ycrystal project, has no valid schema version, was
        written with a newer schema, or is damaged or incomplete (for example missing
        structure entries, element symbols that contradict the atomic numbers,
        invalid camera values, or an unknown material or background preset).
    """
    if not isinstance(data, dict) or data.get("format") != PROJECT_FORMAT:
        raise ProjectError("This is not a Ycrystal project file.")
    version = data.get("schema_version")
    if not isinstance(version, int) or version < 1:
        raise ProjectError("The project file has no valid schema version.")
    if version > SCHEMA_VERSION:
        raise ProjectError(
            f"This project was saved by a newer Ycrystal ({data.get('generator', 'unknown')}, "
            f"schema {version}); this version reads schema {SCHEMA_VERSION}. "
            "Update Ycrystal to open it."
        )
    try:
        register_custom_definitions(data.get("materials"))
        structure = _structure_from(data["structure"])
        scene = _scene_from(data.get("scene") or {}, version)
        output = _output_from(data.get("output") or {})
        environment = _environment_from(data.get("environment") or {}, output)
        camera_data = data.get("camera")
        camera = None if camera_data is None else Camera.from_dict(camera_data)
    except ProjectError:
        raise
    except (KeyError, TypeError, ValueError, IndexError) as exc:
        detail = f"missing entry {exc}" if isinstance(exc, KeyError) else str(exc)
        raise ProjectError(f"The project file is damaged or incomplete: {detail}.") from exc
    attached = {i for i, _ in scene.vectors.sources} | {a[0] for a, _ in scene.vectors.images}
    if attached and max(attached) >= len(structure):
        raise ProjectError(
            f"The project file is damaged: a vector is attached to atom #{max(attached) + 1}, "
            f"but the structure has {len(structure)} atoms."
        )
    if any(atom[0] >= len(structure) for pair, _ in scene.bond_overrides for atom in pair):
        raise ProjectError(
            "The project file is damaged: a bond override refers to an unknown atom."
        )
    return Project(structure, scene, environment, camera, output)


def _structure_from(d: dict[str, Any]) -> Structure:
    numbers = [int(z) for z in d["numbers"]]
    symbols = d.get("symbols")
    if symbols is not None and list(symbols) != [chemical_symbols[z] for z in numbers]:
        raise ProjectError("The project's element symbols do not match its atomic numbers.")
    movable = d.get("movable")
    return Structure(
        cell=np.array(d["cell"], dtype=float),
        positions=np.array(d["positions"], dtype=float).reshape(-1, 3),
        numbers=numbers,
        labels=tuple(str(label) for label in d["labels"]),
        pbc=tuple(bool(v) for v in d.get("pbc", (True, True, True))),
        metadata=dict(d.get("metadata") or {}),
        occupancy=d.get("occupancy"),
        movable=None if movable is None else np.array(movable, dtype=bool),
    )


def _scene_from(d: dict[str, Any], version: int = SCHEMA_VERSION) -> SceneSettings:
    defaults = SceneSettings()
    hidden: set[AtomId] = set()
    for entry in d.get("hidden", []):
        image = tuple(int(v) for v in entry["image"])
        if len(image) != 3:
            raise ValueError("hidden atom image offsets need three integers")
        hidden.add((int(entry["atom"]), (image[0], image[1], image[2])))
    return SceneSettings(
        radius_scale=float(d.get("radius_scale", defaults.radius_scale)),
        show_cell=bool(d.get("show_cell", defaults.show_cell)),
        cell_edge_radius=float(d.get("cell_edge_radius", defaults.cell_edge_radius)),
        cell_edge_color=_rgb(d.get("cell_edge_color", defaults.cell_edge_color)),
        boundary_images=bool(d.get("boundary_images", defaults.boundary_images)),
        boundary_tolerance=float(d.get("boundary_tolerance", defaults.boundary_tolerance)),
        hidden=frozenset(hidden),
        repetitions=tuple(int(v) for v in d.get("repetitions", defaults.repetitions)),
        cell_mode=str(d.get("cell_mode", defaults.cell_mode)),
        bonds=_bonds_from(d.get("bonds"), version),
        bond_overrides=_bond_overrides_from(d.get("bond_overrides", [])),
        polyhedron_rules=tuple(
            PolyhedronRule(
                centre=str(entry["centre"]),
                ligand=str(entry["ligand"]),
                cutoff=float(entry["cutoff"]),
                color=_rgb(entry["color"]),
                opacity=float(entry["opacity"]),
                show_edges=bool(entry.get("show_edges", True)),
                enabled=bool(entry.get("enabled", True)),
            )
            for entry in d.get("polyhedra", [])
        ),
        annotations=tuple(
            TextAnnotation(
                text=entry["text"],
                x=float(entry["x"]),
                y=float(entry["y"]),
                font_size=float(entry["font_size"]),
                font_family=str(entry["font_family"]),
                color=_rgb(entry["color"]),
                alignment=str(entry["alignment"]),
                bold=bool(entry.get("bold", False)),
                enabled=bool(entry.get("enabled", True)),
            )
            for entry in d.get("annotations", [])
        ),
        material=_known_material(str(d.get("material", defaults.material))),
        element_materials=tuple(
            (str(entry["element"]), _known_material(str(entry["material"])))
            for entry in d.get("element_materials", [])
        ),
        atom_materials=tuple(
            ((int(entry["atom"]), _image(entry["image"])), _known_material(str(entry["material"])))
            for entry in d.get("atom_materials", [])
        ),
        element_colors=tuple(
            (str(entry["element"]), _rgb(entry["color"])) for entry in d.get("element_colors", [])
        ),
        element_radii=tuple(
            (str(entry["element"]), float(entry["radius"])) for entry in d.get("element_radii", [])
        ),
        vectors=_vectors_from(d.get("vectors")),
        vector_style=_vector_style_from(d.get("vector_style")),
        legend=_legend_from(d.get("legend")),
    )


def _image(value: Any) -> tuple[int, int, int]:
    image = tuple(int(v) for v in value)
    if len(image) != 3:
        raise ValueError("atom image offsets need three integers")
    return (image[0], image[1], image[2])


def _bond_overrides_from(entries: Any) -> tuple[tuple[BondId, bool], ...]:
    overrides = []
    for entry in entries:
        a, b = ((int(atom["atom"]), _image(atom["image"])) for atom in entry["atoms"])
        visible = entry["visible"]
        if not isinstance(visible, bool):
            raise ValueError("bond override visibility must be a boolean")
        overrides.append(((a, b), visible))
    return tuple(overrides)


def _known_material(material_id: str) -> str:
    from ycrystal.presets import PresetError, get_material
    from ycrystal.presets.custom import CUSTOM_PREFIX

    try:
        return get_material(material_id).id
    except PresetError:
        if material_id.startswith(CUSTOM_PREFIX):
            raise ProjectError(
                f"The file uses the custom material {material_id!r} but does not contain its "
                "definition."
            ) from None
        raise ProjectError(
            f"The project uses the material {material_id!r}, which this Ycrystal does not "
            "know. Update Ycrystal to open it."
        ) from None


def _bonds_from(d: Any, version: int) -> BondSettings:
    if d is None:
        # Schema 1 had no bonds: keep old figures unchanged.
        return BondSettings(enabled=False) if version < 2 else BondSettings()
    defaults = BondSettings()
    overrides = set()
    for entry in d.get("pairs", []):
        a, b = (str(e) for e in entry["elements"])
        if a > b:
            a, b = b, a
        overrides.add((a, b, bool(entry["enabled"])))
    return BondSettings(
        enabled=bool(d.get("enabled", defaults.enabled)),
        tolerance=float(d.get("tolerance", defaults.tolerance)),
        radius=float(d.get("radius", defaults.radius)),
        overrides=frozenset(overrides),
    )


def _environment_from(d: dict[str, Any], output: RenderSettings) -> Environment:
    from ycrystal.presets import PresetError, get_environment, get_lighting

    defaults = Environment()
    # Schemas 1–2 had no environment preset; their transparency lived in "output".
    transparent = bool(d.get("transparent", output.transparent_background))
    preset_id = str(d.get("preset", "transparent" if transparent else defaults.preset))
    try:
        get_environment(preset_id)
    except PresetError:
        raise ProjectError(
            f"The project uses the background {preset_id!r}, which this Ycrystal does not "
            "know. Update Ycrystal to open it."
        ) from None
    background = d.get("background", defaults.background)
    if not isinstance(background, dict):  # schemas 1–3: a plain colour
        background = {"mode": "solid", "color": background, "bottom": background}
    floor = d.get("floor") or {}
    light = d.get("lighting") or {}
    lighting_id = str(light.get("preset", defaults.lighting))
    try:
        get_lighting(lighting_id)
    except PresetError:
        raise ProjectError(
            f"The project uses the lighting {lighting_id!r}, which this Ycrystal does not "
            "know. Update Ycrystal to open it."
        ) from None
    return Environment(
        background=_rgb(background.get("color", defaults.background)),
        key_light=float(light.get("key_light", d.get("key_light", defaults.key_light))),
        fill_light=float(light.get("fill_light", d.get("fill_light", defaults.fill_light))),
        transparent=transparent,
        preset=preset_id,
        background_mode=str(background.get("mode", defaults.background_mode)),
        background_bottom=_rgb(background.get("bottom", background.get("color"))),
        clouds=float(background.get("clouds", defaults.clouds)),
        floor=bool(floor.get("enabled", defaults.floor)),
        floor_color=_rgb(floor.get("color", defaults.floor_color)),
        floor_reflection=float(floor.get("reflection", defaults.floor_reflection)),
        floor_offset=float(floor.get("offset", defaults.floor_offset)),
        lighting=lighting_id,
        key_azimuth=float(light.get("key_azimuth", defaults.key_azimuth)),
        key_elevation=float(light.get("key_elevation", defaults.key_elevation)),
        light_size=float(light.get("light_size", defaults.light_size)),
        shadows=bool(light.get("shadows", defaults.shadows)),
        reflector=bool(light.get("reflector", defaults.reflector)),
        image=_image_from(background.get("image")),
    )


def _output_from(d: dict[str, Any]) -> RenderSettings:
    defaults = RenderSettings()
    return RenderSettings(
        width=int(d.get("width", defaults.width)),
        height=int(d.get("height", defaults.height)),
        antialias=bool(d.get("antialias", defaults.antialias)),
        transparent_background=bool(
            d.get("transparent_background", defaults.transparent_background)
        ),
        # Lock of the Render panel (FR-RENDER-01); optional keys, absent before it.
        aspect_locked=bool(d.get("aspect_locked", defaults.aspect_locked)),
        aspect_ratio=None if d.get("aspect_ratio") is None else float(d["aspect_ratio"]),
    )


def _rgb(value: Any) -> tuple[float, float, float]:
    r, g, b = (float(v) for v in value)
    if not all(0.0 <= v <= 1.0 for v in (r, g, b)):
        raise ValueError("colour components must be between 0 and 1")
    return (r, g, b)


def _jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


# ----- files ----------------------------------------------------------------------------------
def save_project(path: str | Path, project: Project) -> Path:
    """Write a project file atomically.

    A project whose environment refers to a background picture is written as a ZIP
    package with the picture (see [`ycrystal.io.package`][ycrystal.io.package]); others
    as plain JSON. The JSON text is written to a temporary file ``.ycrystal-*.tmp`` in the target
    directory, which then replaces `path` with a single rename. An existing file at
    `path` is overwritten without asking; if writing fails, it is left unchanged.

    Parameters
    ----------
    path
        Destination, used as given: no suffix is added. Missing parent directories are
        created.
    project
        Project to save.

    Returns
    -------
    pathlib.Path
        `path` as a ``Path``.

    Raises
    ------
    OSError
        If the directory or file cannot be written; the temporary file is removed.
    ValueError
        If a value cannot be written as JSON, for example a non-finite coordinate.
    ycrystal.io.images.ImageError
        If the background picture is not registered in this session.
    """
    path = Path(path)
    document = project_to_dict(project)
    assets = referenced_assets(project.environment)
    if assets:
        from ycrystal.io.package import write_package

        return write_package(path, PACKAGE_DOCUMENT, document, assets)
    text = json.dumps(document, indent=1, ensure_ascii=False, allow_nan=False) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".ycrystal-", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise
    return path


def load_project(path: str | Path) -> Project:
    """Read a project file.

    Parameters
    ----------
    path
        Project file: UTF-8 JSON or a ZIP package with pictures (recognised by
        content). The original structure and picture files are not needed; the
        package's pictures are registered for this session.

    Returns
    -------
    Project
        The restored project; coordinates are identical to the saved ones.

    Raises
    ------
    ProjectError
        If the file cannot be read, is not UTF-8 text or valid JSON (the message gives
        the line), is a damaged or unsafe package, misses a referenced picture, or
        fails the checks of [`project_from_dict`][ycrystal.io.project.project_from_dict].

    Examples
    --------
    >>> import tempfile
    >>> from pathlib import Path
    >>> from ycrystal.core.samples import perovskite_srtio3
    >>> from ycrystal.io.project import Project, load_project, save_project
    >>> with tempfile.TemporaryDirectory() as tmp:
    ...     path = save_project(Path(tmp) / "SrTiO3.ycrystal", Project(perovskite_srtio3()))
    ...     reopened = load_project(path)
    >>> reopened.structure.composition(), reopened.camera is None
    ('SrTiO3', True)
    """
    path = Path(path)
    data, assets = read_document(path, PACKAGE_DOCUMENT, ProjectError, "project")
    try:
        project = project_from_dict(data)
        check_assets(project.environment, assets)
    except ProjectError as exc:
        raise ProjectError(f"{path.name}: {exc}") from exc
    from ycrystal.io.images import register_image

    for asset in assets.values():
        register_image(asset)
    return project


def read_document(
    path: Path, document_name: str, error: type[Exception], noun: str
) -> tuple[Any, dict]:
    """Read a plain JSON file or a ZIP package: ``(document, pictures by identity)``.

    The form is recognised by content. Errors are raised as ``error`` with a message
    that starts with the file name (``noun`` is ``"project"`` or ``"style"``).
    """
    from ycrystal.io.package import PackageError, is_package, read_package

    try:
        packaged = is_package(path)
    except OSError as exc:
        raise error(f"Cannot read {path}: {exc.strerror or exc}") from exc
    if packaged:
        try:
            return read_package(path, document_name)
        except PackageError as exc:
            raise error(f"{path.name}: {exc}") from exc
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise error(f"Cannot read {path}: {exc.strerror or exc}") from exc
    except UnicodeDecodeError as exc:
        raise error(f"{path.name} is not a Ycrystal {noun} (not UTF-8 text).") from exc
    try:
        return json.loads(text), {}
    except json.JSONDecodeError as exc:
        raise error(
            f"{path.name} is not valid {noun} JSON (line {exc.lineno}: {exc.msg})."
        ) from exc
