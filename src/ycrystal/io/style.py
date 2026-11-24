"""Reusable figure styles (``.ycstyle`` files).

A style is the presentation of a project without its structure and camera: materials,
colours, radii, display settings, the environment, and the output size. It can be
applied to another structure; the structure's scientific data are never changed.

A style whose environment has a background picture is saved as a ZIP package with the
picture (``style.json`` plus ``assets/``, see [`ycrystal.io.package`][ycrystal.io.package]),
so it works after the original picture file is moved or deleted; other styles stay
plain JSON. Style schema 2 adds the picture record and the definitions of the custom
materials the style uses (FR-MATERIAL-01); schema 3 adds the element legend
(FR-LEGEND-01). Older styles still load, with the legend disabled.

Transfer rules
--------------
A style has four parts; [`apply_style`][ycrystal.io.style.apply_style] applies any
subset of them (see [`STYLE_PARTS`][ycrystal.io.style.STYLE_PARTS]):

``appearance``
    Default material. Material, colour, and radius overrides of elements are applied to
    the elements the target structure contains; overrides of other elements are left
    out and listed in the notes. The vector arrow appearance (placement, length mode,
    sizes, colour, material) and the element legend (FR-LEGEND-01) are applied too; the
    legend's custom element order follows the element mapping.
``display``
    Atom size, repetitions, boundary atoms, cell edges, bond settings. Bond-pair rules
    apply when the target contains both elements.
``environment``
    Background, floor, lighting, transparency, and the cell-edge colour.
``output``
    Output image size in pixels.

Vectors themselves (components and atom attachments, FR-VECTOR-01) are a property of
one structure, not of a look: styles never store or transfer them, and importing a
style keeps the target's vectors unchanged.

Per-atom material overrides and hidden atoms refer to individual atoms of the source
structure. They transfer only if the target is *compatible*: the same number of atoms
with the same element at every position in the input order (for example the same
structure read from another file or relaxed). Otherwise they are left out, and the
notes explain why.

Examples
--------
>>> from ycrystal.core.samples import perovskite_srtio3, triclinic_marker
>>> from ycrystal.core.scene import Environment, SceneSettings
>>> from ycrystal.io.style import Style, apply_style
>>> source = perovskite_srtio3()
>>> scene = (
...     SceneSettings(material="glossy")
...     .with_element_material("O", "glass")
...     .with_element_material("Ti", "gold")
...     .with_atom_materials([(0, (0, 0, 0))], "chrome")
... )
>>> style = Style.from_state(source, scene, Environment(), (800, 600))
>>> target = triclinic_marker()
>>> sorted(set(target.symbols))
['Cl', 'Fe', 'N', 'O', 'S']
>>> result = apply_style(style, target, SceneSettings(), Environment(), (1200, 800))
>>> result.scene.material, result.scene.element_materials, result.scene.atom_materials
('glossy', (('O', 'glass'),), ())
>>> result.output_size
(800, 600)
>>> print(result.notes[0])
Element overrides for Ti were not applied: the structure has no Ti.
>>> print(result.notes[1][:52])
1 per-atom material override was not applied: it ref
"""

from __future__ import annotations

import datetime as _dt
import json
import os
import tempfile
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from ase.data import chemical_symbols

from ycrystal import __version__
from ycrystal.core.bonds import BondSettings
from ycrystal.core.scene import Environment, SceneSettings
from ycrystal.core.structure import Structure

STYLE_FORMAT = "ycrystal-style"
"""Value of the ``format`` key that identifies a style file."""

STYLE_SCHEMA_VERSION = 3
STYLE_PROJECT_SCHEMA_VERSION = 8  # project schema of the shared fields in style schema 3
"""Style schema written by this Ycrystal; newer versions are refused on load."""

STYLE_DOCUMENT = "style.json"
"""Name of the JSON document inside a style package."""

STYLE_SUFFIX = ".ycstyle"
"""File-name suffix of style files."""

STYLE_PARTS = ("appearance", "display", "environment", "output")
"""Parts of a style that can be applied separately (see the module notes)."""

_ELEMENTS = frozenset(chemical_symbols[1:])  # index 0 is ASE's placeholder "X"

LEAVE_OUT_LABEL = "Do not transfer"
"""Name of the choice that leaves an element's settings out, in the import dialog."""


class StyleError(Exception):
    """A style file cannot be read; ``str(error)`` is a message for the user."""


@dataclass(frozen=True)
class Style:
    """The presentation of a project, independent of its structure and camera.

    Attributes
    ----------
    scene
        Complete display settings of the source, including its per-atom overrides and
        hidden atoms (which transfer only to compatible structures).
    environment
        Background, floor, lighting, and transparency.
    output_size
        Output image ``(width, height)`` in pixels.
    source_symbols
        Element of every source atom in input order (decides compatibility).
    source_name
        Composition of the source structure, for messages.
    """

    scene: SceneSettings
    environment: Environment
    output_size: tuple[int, int]
    source_symbols: tuple[str, ...]
    source_name: str

    @classmethod
    def from_state(
        cls,
        structure: Structure,
        scene: SceneSettings,
        environment: Environment,
        output_size: tuple[int, int],
    ) -> Style:
        """Capture the style of a structure's current presentation."""
        return cls(
            scene=scene,
            environment=environment,
            output_size=(int(output_size[0]), int(output_size[1])),
            source_symbols=tuple(structure.symbols),
            source_name=structure.composition(),
        )

    def is_compatible(self, structure: Structure) -> bool:
        """Return whether per-atom settings can transfer to ``structure``.

        True when ``structure`` has the same number of atoms with the same element at
        every position (input order).
        """
        return tuple(structure.symbols) == self.source_symbols


@dataclass(frozen=True)
class StyleResult:
    """Settings after applying a style, and what could not be applied.

    Attributes
    ----------
    scene, environment, output_size
        The new display settings, environment, and output size.
    notes
        One sentence per part of the style that was left out, for the user.
    """

    scene: SceneSettings
    environment: Environment
    output_size: tuple[int, int]
    notes: tuple[str, ...]


class ElementMapError(ValueError):
    """An element mapping is invalid or ambiguous; ``str(error)`` is a message for the user."""


@dataclass(frozen=True)
class ElementTransfer:
    """Where a style's element settings go in a target structure (FR-STYLE-MAP-01).

    Attributes
    ----------
    targets
        ``(source element, target element)`` for every element whose settings are
        applied, sorted by source element. Identity pairs (``("O", "O")``) are included.
    left_out
        Source elements whose settings are not applied: absent from the structure
        without a mapping, or left out on purpose (mapped to ``None``).
    notes
        One sentence per decision the user should know about.
    """

    targets: tuple[tuple[str, str], ...]
    left_out: tuple[str, ...]
    notes: tuple[str, ...]

    def target_of(self, element: str) -> str | None:
        """Return the target element of a source element, or ``None`` if left out."""
        return dict(self.targets).get(element)


def check_element(symbol: object, role: str = "element") -> str:
    """Return ``symbol`` if it is a chemical element symbol, as structures use them.

    >>> check_element("Ti")
    'Ti'

    Raises
    ------
    ElementMapError
        If it is not one (symbols are case-sensitive: ``Ti``, not ``TI``).
    """
    if isinstance(symbol, str) and symbol in _ELEMENTS:
        return symbol
    hint = ""
    if isinstance(symbol, str) and symbol.strip().capitalize() in _ELEMENTS:
        hint = f" (did you mean {symbol.strip().capitalize()}?)"
    raise ElementMapError(f"{symbol!r} is not a chemical element symbol{hint}; {role} expected.")


def style_elements(
    style: Style, parts: tuple[str, ...] | list[str] = STYLE_PARTS
) -> tuple[str, ...]:
    """Return the elements that a style has settings for, in the given parts, sorted.

    ``appearance`` contributes the element materials, colours, and radii; ``display``
    the elements of bond-pair rules. Other parts have no element settings.
    """
    source = style.scene
    elements: set[str] = set()
    if "appearance" in parts:
        for entries in (source.element_materials, source.element_colors, source.element_radii):
            elements.update(entry[0] for entry in entries)
    if "display" in parts:
        for a, b, _ in source.bonds.overrides:
            elements.update((a, b))
    return tuple(sorted(elements))


def resolve_element_map(
    style: Style,
    structure: Structure,
    element_map: dict[str, str | None] | None = None,
    parts: tuple[str, ...] | list[str] = STYLE_PARTS,
) -> ElementTransfer:
    """Decide where each of a style's element settings goes in a structure.

    Without a mapping every element keeps its symbol: its settings apply if the
    structure contains it (the transfer rule of earlier versions). A mapping sends the
    settings of a source element to another element of the structure, or leaves them
    out (``None``); the mapping is a presentation choice, not a statement of chemical
    or crystallographic equivalence.

    Parameters
    ----------
    style
        Style whose element settings are transferred.
    structure
        Target structure; it is read, never modified.
    element_map
        ``{source element: target element or None}``. Elements that are not keys keep
        their symbol. ``{"Ti": "Ti"}`` is allowed and changes nothing.
    parts
        Parts that will be applied (decides which element settings count).

    Returns
    -------
    ElementTransfer

    Raises
    ------
    ElementMapError
        If a key or value is not an element symbol, a target element is not in the
        structure, two source elements are mapped to the same target, or a mapped
        element would land on an element that keeps its own settings by symbol.
        Ambiguity is an error, never resolved by order.

    Examples
    --------
    >>> from ycrystal.core.samples import perovskite_srtio3
    >>> from ycrystal.core.scene import Environment, SceneSettings
    >>> source = perovskite_srtio3()
    >>> scene = (
    ...     SceneSettings()
    ...     .with_element_material("Ti", "gold")
    ...     .with_element_color("O", (1.0, 0.0, 0.0))
    ... )
    >>> style = Style.from_state(source, scene, Environment(), (800, 600))
    >>> resolve_element_map(style, source, {"Ti": None}).targets
    (('O', 'O'),)
    >>> try:
    ...     resolve_element_map(style, source, {"Ti": "O"})
    ... except ElementMapError as error:
    ...     print(str(error)[:45])
    O would receive the settings of both O and Ti
    """
    element_map = dict(element_map or {})
    present = set(structure.symbols)
    for source_element, target in element_map.items():
        check_element(source_element, "a source element")
        if target is not None:
            check_element(target, "a target element")
            if target not in present:
                raise ElementMapError(
                    f"{source_element} is mapped to {target}, but the structure has no "
                    f"{target} (it contains {', '.join(sorted(present))})."
                )
    by_target: dict[str, list[str]] = {}
    for source_element, target in element_map.items():
        if target is not None:
            by_target.setdefault(target, []).append(source_element)
    for target, sources in sorted(by_target.items()):
        if len(sources) > 1:
            raise ElementMapError(
                f"{' and '.join(sorted(sources))} are all mapped to {target}; each element "
                "of the structure can receive the settings of one element only."
            )

    elements = style_elements(style, parts)
    notes: list[str] = []
    targets: dict[str, str] = {}
    left_out: list[str] = []
    for element in elements:
        target = element_map.get(element, element)
        if target is not None and target in present:
            targets[element] = target
        else:
            left_out.append(element)
    receivers: dict[str, list[str]] = {}
    for element, target in targets.items():
        receivers.setdefault(target, []).append(element)
    for target, sources in sorted(receivers.items()):
        if len(sources) > 1:
            others = [s for s in sources if s != target]
            raise ElementMapError(
                f"{target} would receive the settings of both {' and '.join(sorted(sources))}: "
                f"{', '.join(others)} {'is' if len(others) == 1 else 'are'} mapped to {target}, "
                f"and the style has settings for {target} itself. Map {target} to another "
                f"element, or leave its settings out ('{LEAVE_OUT_LABEL}' in the window, "
                f"{target}=- on the command line)."
            )

    unused = sorted(set(element_map) - set(elements))
    if unused:
        names = ", ".join(unused)
        notes.append(
            f"The style has no element settings for {names}; "
            f"{'its' if len(unused) == 1 else 'their'} mapping changes nothing."
        )
    dropped = sorted(e for e in left_out if e in element_map)
    if dropped:
        names = ", ".join(dropped)
        notes.append(f"Element settings for {names} were left out by the element mapping.")
    moved = sorted(e for e, t in targets.items() if t != e and e in present)
    if moved:
        notes.append(
            "Atoms of "
            + ", ".join(moved)
            + " in this structure do not receive the style's settings for "
            + ("that element" if len(moved) == 1 else "these elements")
            + ": they are mapped to "
            + ", ".join(targets[e] for e in moved)
            + "."
        )
    return ElementTransfer(tuple(sorted(targets.items())), tuple(left_out), tuple(notes))


def apply_style(
    style: Style,
    structure: Structure,
    scene: SceneSettings,
    environment: Environment,
    output_size: tuple[int, int],
    parts: tuple[str, ...] | list[str] = STYLE_PARTS,
    element_map: dict[str, str | None] | None = None,
) -> StyleResult:
    """Apply a style to a structure's current presentation.

    Parameters
    ----------
    style
        Style to apply.
    structure
        Target structure; it is read, never modified.
    scene, environment, output_size
        Current presentation of the target; parts that are not applied stay as they are.
    parts
        Parts to apply, a subset of [`STYLE_PARTS`][ycrystal.io.style.STYLE_PARTS].
    element_map
        Optional ``{source element: target element or None}`` that sends the element
        materials, colours, and radii, and the bond-pair rules, of a source element to
        another element of the structure, or leaves them out (``None``); see
        [`resolve_element_map`][ycrystal.io.style.resolve_element_map]. ``None`` (the
        default) transfers by matching symbols, as before. Atoms, coordinates, vectors,
        and bonds themselves are never mapped, and per-atom settings still transfer
        only to the same structure.

    Returns
    -------
    StyleResult
        New settings and notes on what was left out (see the module's transfer rules).

    Raises
    ------
    ValueError
        If `parts` contains an unknown name.
    ElementMapError
        If `element_map` is invalid or ambiguous (a subclass of ``ValueError``).
    """
    unknown = set(parts) - set(STYLE_PARTS)
    if unknown:
        raise ValueError(f"unknown style parts: {sorted(unknown)}")
    source = style.scene
    compatible = style.is_compatible(structure)
    element_map = dict(element_map or {})
    transfer = resolve_element_map(style, structure, element_map, parts)
    notes: list[str] = list(transfer.notes)
    new = scene

    if "appearance" in parts:
        missing: set[str] = set()

        def keep(entries: tuple) -> tuple:
            kept = []
            for element, value in entries:
                target = transfer.target_of(element)
                if target is not None:
                    kept.append((target, value))
                elif element not in element_map:  # left out on purpose: noted already
                    missing.add(element)
            return tuple(sorted(kept))

        # The legend's custom order follows explicit mappings; other symbols stay (an
        # element the structure lacks is simply not shown).
        order = tuple(
            dict.fromkeys(
                target
                for target in (element_map.get(e, e) for e in source.legend.custom_order)
                if target is not None
            )
        )
        new = replace(
            new,
            material=source.material,
            vector_style=source.vector_style,  # arrow appearance only, never vector data
            legend=replace(source.legend, custom_order=order),
            element_materials=keep(source.element_materials),
            element_colors=keep(source.element_colors),
            element_radii=keep(source.element_radii),
            atom_materials=source.atom_materials if compatible else (),
        )
        if missing:
            names = ", ".join(sorted(missing))
            notes.append(
                f"Element overrides for {names} were not applied: the structure has no {names}."
            )
        if source.atom_materials and not compatible:
            notes.append(
                _atom_note(
                    len(source.atom_materials),
                    "per-atom material override",
                    "per-atom material overrides",
                    style,
                )
            )

    if "display" in parts:
        pairs = []
        mapped_out = False  # a dropped rule involves an element the mapping leaves out
        for a, b, on in source.bonds.overrides:
            ta, tb = transfer.target_of(a), transfer.target_of(b)
            if ta is not None and tb is not None:
                pairs.append((*sorted((ta, tb)), on))  # alphabetical, as BondSettings expects
            elif any(element_map.get(e, "") is None for e in (a, b)):
                mapped_out = True
        dropped_pairs = len(source.bonds.overrides) - len(pairs)
        new = replace(
            new,
            radius_scale=source.radius_scale,
            show_cell=source.show_cell,
            cell_edge_radius=source.cell_edge_radius,
            boundary_images=source.boundary_images,
            boundary_tolerance=source.boundary_tolerance,
            repetitions=source.repetitions,
            cell_mode=source.cell_mode,
            bonds=BondSettings(
                enabled=source.bonds.enabled,
                tolerance=source.bonds.tolerance,
                radius=source.bonds.radius,
                overrides=frozenset(pairs),
            ),
            hidden=source.hidden if compatible else scene.hidden,
        )
        if dropped_pairs:
            noun = "rule" if dropped_pairs == 1 else "rules"
            reason = "the structure does not contain"
            if mapped_out:
                reason += " or the element mapping leaves out"
            notes.append(
                f"{dropped_pairs} bond-pair {noun} for elements {reason} were not applied."
            )
        if source.hidden and not compatible:
            notes.append(
                _atom_note(len(source.hidden), "hidden-atom setting", "hidden-atom settings", style)
            )

    new_environment = environment
    if "environment" in parts:
        new_environment = style.environment
        new = replace(new, cell_edge_color=source.cell_edge_color)

    new_size = style.output_size if "output" in parts else output_size
    return StyleResult(new, new_environment, new_size, tuple(notes))


def _atom_note(count: int, singular: str, plural: str, style: Style) -> str:
    noun, verb, pronoun = (
        (singular, "was", "it refers")
        if count == 1
        else (
            plural,
            "were",
            "they refer",
        )
    )
    return (
        f"{count} {noun} {verb} not applied: {pronoun} to atoms of {style.source_name} "
        f"({len(style.source_symbols)} atoms), not to this structure."
    )


# ----- files --------------------------------------------------------------------------------
def style_to_dict(style: Style) -> dict[str, Any]:
    """Convert a style to a JSON-compatible dictionary (current style schema).

    The scene and environment use the same layout as the ``scene`` and ``environment``
    sections of a project file.
    """
    from ycrystal.io.project import Project, project_to_dict

    project = project_to_dict(
        Project(
            structure=_placeholder_structure(),
            scene=style.scene,
            environment=style.environment,
        )
    )
    return {
        "format": STYLE_FORMAT,
        "schema_version": STYLE_SCHEMA_VERSION,
        "project_schema": STYLE_PROJECT_SCHEMA_VERSION,
        "generator": f"Ycrystal {__version__}",
        "saved_at": _dt.datetime.now(_dt.UTC).isoformat(timespec="seconds"),
        "source": {"composition": style.source_name, "symbols": list(style.source_symbols)},
        "scene": {
            key: value
            for key, value in project["scene"].items()
            if key not in ("vectors", "bond_overrides", "polyhedra")
        },
        "environment": project["environment"],
        "materials": project["materials"],
        "output": {"width": style.output_size[0], "height": style.output_size[1]},
    }


def style_from_dict(data: Any) -> Style:
    """Validate a style document and convert it to a [`Style`][ycrystal.io.style.Style].

    Raises
    ------
    StyleError
        If the document is not a Ycrystal style, was written by a newer Ycrystal, or is
        damaged (including unknown material, environment, or lighting presets).
    """
    from ycrystal.io.project import (
        SCHEMA_VERSION,
        ProjectError,
        _environment_from,
        _output_from,
        _scene_from,
        register_custom_definitions,
    )

    if not isinstance(data, dict) or data.get("format") != STYLE_FORMAT:
        raise StyleError("This is not a Ycrystal style file.")
    version = data.get("schema_version")
    if not isinstance(version, int) or version < 1:
        raise StyleError("The style file has no valid schema version.")
    if version > STYLE_SCHEMA_VERSION:
        raise StyleError(
            f"This style was saved by a newer Ycrystal ({data.get('generator', 'unknown')}); "
            "update Ycrystal to use it."
        )
    try:
        project_schema = int(data.get("project_schema", SCHEMA_VERSION))
        if project_schema > SCHEMA_VERSION:
            raise StyleError("This style was saved by a newer Ycrystal; update Ycrystal to use it.")
        output = _output_from(data.get("output") or {})
        register_custom_definitions(data.get("materials"))
        scene = _scene_from(data.get("scene") or {}, project_schema)
        environment = _environment_from(data.get("environment") or {}, output)
        source = data.get("source") or {}
        symbols = tuple(str(s) for s in source.get("symbols", ()))
        name = str(source.get("composition", "the source structure"))
    except StyleError:
        raise
    except ProjectError as exc:
        raise StyleError(str(exc).replace("project", "style")) from exc
    except (KeyError, TypeError, ValueError, IndexError) as exc:
        detail = f"missing entry {exc}" if isinstance(exc, KeyError) else str(exc)
        raise StyleError(f"The style file is damaged or incomplete: {detail}.") from exc
    return Style(scene, environment, (output.width, output.height), symbols, name)


def save_style(path: str | Path, style: Style) -> Path:
    """Write a style file atomically and return its path.

    UTF-8 JSON, or a ZIP package when the environment has a background picture.

    Raises
    ------
    OSError
        If the file cannot be written; an existing file is then left unchanged.
    ycrystal.io.images.ImageError
        If the background picture is not registered in this session.
    """
    from ycrystal.io.project import referenced_assets

    path = Path(path)
    document = style_to_dict(style)
    assets = referenced_assets(style.environment)
    if assets:
        from ycrystal.io.package import write_package

        return write_package(path, STYLE_DOCUMENT, document, assets)
    text = json.dumps(document, indent=1, ensure_ascii=False, allow_nan=False) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".ycstyle-", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise
    return path


def load_style(path: str | Path) -> Style:
    """Read a style file.

    Raises
    ------
    StyleError
        If the file cannot be read, is not valid JSON, is a damaged or unsafe package,
        misses its picture, or fails the checks of
        [`style_from_dict`][ycrystal.io.style.style_from_dict]; the message starts with
        the file name. A package's picture is registered for this session.
    """
    from ycrystal.io.images import register_image
    from ycrystal.io.project import ProjectError, check_assets, read_document

    path = Path(path)
    data, assets = read_document(path, STYLE_DOCUMENT, StyleError, "style")
    try:
        style = style_from_dict(data)
        check_assets(style.environment, assets)
    except ProjectError as exc:
        raise StyleError(f"{path.name}: {str(exc).replace('project', 'style')}") from exc
    except StyleError as exc:
        raise StyleError(f"{path.name}: {exc}") from exc
    for asset in assets.values():
        register_image(asset)
    return style


def _placeholder_structure() -> Structure:
    import numpy as np

    return Structure(
        cell=np.zeros((3, 3)), positions=np.zeros((0, 3)), numbers=[], labels=(), pbc=(False,) * 3
    )
