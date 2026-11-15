"""The ``.ycrystal`` project file: versioned JSON with the embedded structure.

A project reopens without the original structure file: the canonical structure (cell,
positions, elements, labels, occupancy, movable flags) is stored in full, together with
its import provenance, the display settings (including hidden atoms), environment,
camera, and output settings. Floats are written with Python's shortest round-trip
representation, so reopening reproduces every coordinate exactly.

The top-level JSON object has the keys ``format`` (always ``"ycrystal-project"``),
``schema_version``, ``generator``, ``saved_at``, ``structure``, ``scene``,
``environment``, ``camera``, and ``output``. Machine-specific settings such as the
POV-Ray path are not stored in projects.

Schema history: 1 — first version (M1); 2 — repetitions, cell mode, and bonds (M2).
Schema-1 files load with bonds disabled to preserve their original appearance.
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
from ycrystal.core.bonds import BondSettings
from ycrystal.core.camera import Camera
from ycrystal.core.scene import AtomId, Environment, SceneSettings
from ycrystal.core.structure import Structure
from ycrystal.render.pov_writer import RenderSettings

PROJECT_FORMAT = "ycrystal-project"
"""Value of the ``format`` key that identifies a project file."""

SCHEMA_VERSION = 2
"""Schema version written by this Ycrystal; newer versions are refused on load."""

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
        Background colour and light intensities.
    camera
        Saved view, or ``None`` to use the default view when the project is opened.
    output
        Output image settings. The GUI restores only the width and the transparency
        setting from it; the height follows the window's aspect ratio when the project
        is opened, and antialiasing is always on.

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
        "saved_at": _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"),
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
        "environment": {
            "background": list(project.environment.background),
            "key_light": project.environment.key_light,
            "fill_light": project.environment.fill_light,
        },
        "camera": None if project.camera is None else project.camera.to_dict(),
        "output": {
            "width": project.output.width,
            "height": project.output.height,
            "antialias": project.output.antialias,
            "transparent_background": project.output.transparent_background,
        },
    }


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
        structure entries, element symbols that contradict the atomic numbers, or
        invalid camera values).
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
        structure = _structure_from(data["structure"])
        scene = _scene_from(data.get("scene") or {}, version)
        environment = _environment_from(data.get("environment") or {})
        camera_data = data.get("camera")
        camera = None if camera_data is None else Camera.from_dict(camera_data)
        output = _output_from(data.get("output") or {})
    except ProjectError:
        raise
    except (KeyError, TypeError, ValueError, IndexError) as exc:
        detail = f"missing entry {exc}" if isinstance(exc, KeyError) else str(exc)
        raise ProjectError(f"The project file is damaged or incomplete: {detail}.") from exc
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
    )


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


def _environment_from(d: dict[str, Any]) -> Environment:
    defaults = Environment()
    return Environment(
        background=_rgb(d.get("background", defaults.background)),
        key_light=float(d.get("key_light", defaults.key_light)),
        fill_light=float(d.get("fill_light", defaults.fill_light)),
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

    The JSON text is written to a temporary file ``.ycrystal-*.tmp`` in the target
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
    """
    path = Path(path)
    text = (
        json.dumps(project_to_dict(project), indent=1, ensure_ascii=False, allow_nan=False) + "\n"
    )
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
        Project file (UTF-8 JSON). The original structure file is not needed.

    Returns
    -------
    Project
        The restored project; coordinates are identical to the saved ones.

    Raises
    ------
    ProjectError
        If the file cannot be read, is not UTF-8 text or valid JSON (the message gives
        the line), or fails the checks of
        [`project_from_dict`][ycrystal.io.project.project_from_dict].

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
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ProjectError(f"Cannot read {path}: {exc.strerror or exc}") from exc
    except UnicodeDecodeError as exc:
        raise ProjectError(f"{path.name} is not a Ycrystal project (not UTF-8 text).") from exc
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ProjectError(
            f"{path.name} is not valid project JSON (line {exc.lineno}: {exc.msg})."
        ) from exc
    try:
        return project_from_dict(data)
    except ProjectError as exc:
        raise ProjectError(f"{path.name}: {exc}") from exc
