"""Self-contained figure snapshots and render provenance (FR-REPRO-01).

``ycrystal FILE … --render OUT.png --save-project FIGURE.ycrystal``, and
``"save_projects": true`` in a batch manifest, save two files next to a rendered image:

``FIGURE.ycrystal``, the *snapshot*
    An ordinary project file holding the figure as it was drawn: the structure, the
    scene settings after the style and element mapping were applied, the environment
    with its background picture, the definitions of the custom materials it uses, the
    vectors, the output size, and the camera actually used (saved or fitted). It needs
    neither the original structure file nor the style, picture, or personal materials,
    and replaying it neither reapplies a style nor refits the camera::

        ycrystal FIGURE.ycrystal --render replay.png

``FIGURE.provenance.json``, the provenance record
    Which inputs, settings, and software made the image; see
    [`provenance_record`][ycrystal.provenance.provenance_record].

The image is rendered *from the saved snapshot file*, so the snapshot draws the same
scene by construction. The three files are moved into place only after POV-Ray has
succeeded, the provenance record last: a failed render leaves none of them (and no
temporary file) behind, and no record ever describes an image that was not made.

What is reproduced, and what is not
------------------------------------
Replaying a snapshot gives exactly the same structure, scene settings, camera, and
image size, hence the same POV-Ray scene. Pixels are a different matter: another
POV-Ray build, another system, or other standard include files (``metals.inc``, …,
which belong to the POV-Ray installation and are not part of the snapshot) may change
the image slightly. The SHA-256 of the image identifies that file; it is a fingerprint,
not a proof that someone else reproduced it.

No absolute paths are recorded. Paths in a provenance record are relative to the
record's folder; a file outside that folder is identified by name and SHA-256 only.
The snapshot also leaves out the absolute path of the original structure file from the
structure's import record (its name, format, and SHA-256 remain).

Examples
--------
>>> from ycrystal.batch import load_input
>>> from ycrystal.core.camera import ViewPolicy
>>> from ycrystal.provenance import provenance_path, snapshot_project
>>> project = load_input("tests/fixtures/MgB2.cif")
>>> project.camera is None
True
>>> snapshot = snapshot_project(project, width=400, view=ViewPolicy(view="c"))
>>> snapshot.camera is not None, (snapshot.output.width, snapshot.output.height)
(True, (400, 800))
>>> source = snapshot.structure.metadata["source"]  # the import record, without the path
>>> "path" in source, source["sha256"] == project.structure.metadata["source"]["sha256"]
(False, True)
>>> provenance_path("figures/MgB2 c.ycrystal").name
'MgB2 c.provenance.json'
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
import os
import platform
import shlex
import struct
import tempfile
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

from ycrystal import __version__
from ycrystal.batch import render_png, scene_for
from ycrystal.core import aspect
from ycrystal.core.camera import ViewPolicy
from ycrystal.core.scene import build_geometry, count_displayed_atoms
from ycrystal.core.structure import Structure
from ycrystal.io.project import (
    PROJECT_SUFFIX,
    SCHEMA_VERSION,
    Project,
    ProjectError,
    load_project,
    save_project,
)
from ycrystal.render.jobs import RenderResult
from ycrystal.render.pov_writer import required_includes
from ycrystal.render.povray import find_povray, povray_version

PROVENANCE_FORMAT = "ycrystal-provenance"
"""Value of the ``format`` key that identifies a provenance record."""

PROVENANCE_SCHEMA_VERSION = 1
"""Schema of the provenance records written by this Ycrystal."""

PROVENANCE_SUFFIX = ".provenance.json"
"""Suffix of a provenance record: ``FIGURE.ycrystal`` → ``FIGURE.provenance.json``."""

REPRODUCIBILITY_NOTE = (
    "Rendering the project again (see 'replay') reproduces the structure, scene "
    "settings, camera, and image size exactly. Pixels may differ slightly with another "
    "POV-Ray build, system, or set of standard include files; the image SHA-256 "
    "identifies this image file only."
)
"""Text of the ``reproducibility`` entry of every record."""

_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


class SnapshotError(Exception):
    """A snapshot or its provenance record cannot be saved; ``str(error)`` is for the user."""


@dataclass(frozen=True)
class SourceFile:
    """A file a figure was made from, identified by content.

    Attributes
    ----------
    path
        The file as it was read.
    sha256
        SHA-256 of its bytes, in hexadecimal.
    size
        Size in bytes.
    """

    path: Path
    sha256: str
    size: int

    @classmethod
    def of(cls, path: str | os.PathLike[str]) -> SourceFile:
        """Read and hash a file.

        Raises
        ------
        OSError
            If the file cannot be read.
        """
        path = Path(path)
        return cls(path, file_sha256(path), path.stat().st_size)


@dataclass(frozen=True)
class FigureRequest:
    """What a figure was asked to be made from, and how (for its provenance record).

    Attributes
    ----------
    input
        The structure file or project, read with
        [`load_input`][ycrystal.batch.load_input]; ``None`` if the figure does not come
        from a file.
    input_format
        ``"poscar"``, ``"cif"``, ``"qe"``, or ``"project"`` (see
        [`input_format`][ycrystal.provenance.input_format]).
    style
        The style file applied, or ``None``.
    style_parts
        The parts of the style applied (empty without a style).
    element_map
        The element mapping given with the style (``{source: target or None}``), or
        ``None``.
    view
        The camera policy.
    width, height
        Image size given explicitly (``--width``/``--height`` or the manifest);
        ``None`` uses the input's or the style's size.
    notes
        Warnings of the style transfer (what was not applied).
    job
        Batch job id, or ``None`` for a single figure.
    manifest
        The batch manifest, or ``None`` for a single figure.
    """

    input: SourceFile | None = None
    input_format: str | None = None
    style: SourceFile | None = None
    style_parts: tuple[str, ...] = ()
    element_map: Mapping[str, str | None] | None = None
    view: ViewPolicy = field(default_factory=ViewPolicy)
    width: int | None = None
    height: int | None = None
    notes: tuple[str, ...] = ()
    job: str | None = None
    manifest: SourceFile | None = None


@dataclass(frozen=True)
class SnapshotRender:
    """Outcome of [`render_snapshot`][ycrystal.provenance.render_snapshot].

    Attributes
    ----------
    result
        The render result; on success ``image_path`` is the final image.
    snapshot, provenance
        The saved project and provenance record, or ``None`` if the render failed
        (then neither file was written).
    record
        The provenance record as written, or ``None``.
    """

    result: RenderResult
    snapshot: Path | None = None
    provenance: Path | None = None
    record: dict[str, Any] | None = None


# ----- small helpers ----------------------------------------------------------------------------
def provenance_path(snapshot: str | os.PathLike[str]) -> Path:
    """Return the provenance record that belongs to a snapshot (same folder and stem)."""
    snapshot = Path(snapshot)
    return snapshot.with_name(snapshot.stem + PROVENANCE_SUFFIX)


def file_sha256(path: str | os.PathLike[str]) -> str:
    """Return the SHA-256 of a file's bytes in hexadecimal.

    Raises
    ------
    OSError
        If the file cannot be read.
    """
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def png_size(path: str | os.PathLike[str]) -> tuple[int, int]:
    """Return ``(width, height)`` of a PNG file from its header.

    Raises
    ------
    ValueError
        If the file is not a PNG image.
    OSError
        If the file cannot be read.
    """
    with open(path, "rb") as handle:
        head = handle.read(24)
    if len(head) < 24 or head[:8] != _PNG_SIGNATURE or head[12:16] != b"IHDR":
        raise ValueError(f"{Path(path).name} is not a PNG image.")
    width, height = struct.unpack(">II", head[16:24])
    return int(width), int(height)


def input_format(path: str | os.PathLike[str], fmt: str | None, project: Project) -> str | None:
    """Return the format an input was read in, as [`load_input`][ycrystal.batch.load_input] did.

    `fmt` is the format asked for (``None``: detected). A ``.ycrystal`` file is a
    project; for a structure file the detected format is in its import record.
    """
    if fmt is not None:
        return fmt
    if Path(path).suffix.lower() == PROJECT_SUFFIX:
        return "project"
    source = project.structure.metadata.get("source")
    return source.get("format") if isinstance(source, dict) else None


def same_file(a: str | os.PathLike[str], b: str | os.PathLike[str]) -> bool:
    """Return whether two paths name the same file (or would, once created).

    Existing files are compared with ``os.path.samefile`` (links, case-insensitive
    file systems); otherwise the resolved paths are compared without regard to case.
    """
    a, b = Path(a), Path(b)
    try:
        if a.exists() and b.exists():
            return os.path.samefile(a, b)
    except OSError:
        pass
    return str(a.resolve()).casefold() == str(b.resolve()).casefold()


def check_snapshot_target(
    snapshot: str | os.PathLike[str],
    protected: Iterable[str | os.PathLike[str]] = (),
    overwrite: bool = False,
) -> list[str]:
    """Return the problems with saving a snapshot and its record at ``snapshot``.

    Parameters
    ----------
    snapshot
        The project file to write; its record is
        [`provenance_path`][ycrystal.provenance.provenance_path] of it.
    protected
        Files that must never be replaced: the input, the style, the image, a manifest.
    overwrite
        Whether existing snapshot and record files may be replaced.

    Returns
    -------
    list of str
        One message per problem; empty if both files can be written.
    """
    problems = []
    protected = [Path(p) for p in protected]
    for path in (Path(snapshot), provenance_path(snapshot)):
        if any(same_file(path, other) for other in protected):
            problems.append(f"{path} would replace a file the figure is made from or written to.")
        elif not overwrite and path.exists():
            problems.append(f"{path} exists; use --overwrite to replace it.")
    return problems


def _portable_structure(structure: Structure) -> Structure:
    """Return the structure without the absolute path in its import record."""
    source = structure.metadata.get("source")
    if not isinstance(source, dict) or "path" not in source:
        return structure
    kept = {key: value for key, value in source.items() if key != "path"}
    return structure.replace(metadata={**structure.metadata, "source": kept})


def _relative(path: Path, base: Path) -> str | None:
    """Return ``path`` relative to ``base`` (POSIX form), or ``None`` if it is outside."""
    try:
        return path.resolve().relative_to(base.resolve()).as_posix()
    except ValueError:
        return None


def _file_entry(path: Path, base: Path, sha256: str, size: int) -> dict[str, Any]:
    return {"name": path.name, "path": _relative(path, base), "sha256": sha256, "bytes": size}


def _system() -> dict[str, str]:
    import ase
    import numpy

    return {
        "os": platform.system(),
        "machine": platform.machine(),
        "python": platform.python_version(),
        "numpy": numpy.__version__,
        "ase": ase.__version__,
    }


def _temporary(folder: Path) -> Path:
    fd, name = tempfile.mkstemp(prefix=".ycrystal-", suffix=".tmp", dir=folder)
    os.close(fd)
    return Path(name)


def _make_folder(folder: Path) -> list[Path]:
    """Create ``folder`` and missing parents; return the folders created, outermost first."""
    missing = []
    for candidate in (folder, *folder.parents):
        if candidate.exists():
            break
        missing.append(candidate)
    folder.mkdir(parents=True, exist_ok=True)
    return missing[::-1]


# ----- snapshot and record -------------------------------------------------------------------
def snapshot_project(
    project: Project,
    width: int | None = None,
    height: int | None = None,
    view: ViewPolicy | None = None,
) -> Project:
    """Return the project exactly as it is drawn: the figure's snapshot.

    Parameters
    ----------
    project
        What is drawn, with any style already applied (see
        [`apply_style_file`][ycrystal.batch.apply_style_file]).
    width, height, view
        As in [`scene_for`][ycrystal.batch.scene_for].

    Returns
    -------
    Project
        The same structure, scene, and environment, with the camera that
        [`scene_for`][ycrystal.batch.scene_for] chooses (saved or fitted) and the final
        output size. Drawn with its saved camera and size (``ycrystal SNAPSHOT
        --render``), it gives the same geometry, camera, and image size. The absolute
        path of the original structure file is left out of its import record.

    Raises
    ------
    ycrystal.core.camera.CameraPolicyError
        If the view cannot be produced.
    """
    _, camera, settings = scene_for(project, width, height, view)
    ratio = settings.aspect_ratio
    if ratio is not None and not aspect.matches_ratio((settings.width, settings.height), ratio):
        ratio = None  # the lock follows the final shape, as in the window
    output = replace(settings, aspect_ratio=ratio)
    structure = _portable_structure(project.structure)
    return Project(structure, project.scene, project.environment, camera, output)


def provenance_record(
    request: FigureRequest,
    snapshot: Project,
    image: Path,
    image_digest: tuple[str, int],
    project_file: Path,
    project_digest: tuple[str, int],
    image_size: tuple[int, int],
    renderer_version: str | None,
) -> dict[str, Any]:
    """Return the provenance record of a rendered figure (JSON-compatible).

    Parameters
    ----------
    request
        What the figure was made from.
    snapshot
        The saved snapshot (from [`snapshot_project`][ycrystal.provenance.snapshot_project]).
    image, project_file
        Final paths of the image and the snapshot; the record belongs next to the
        snapshot, and paths are relative to that folder.
    image_digest, project_digest
        ``(sha256, bytes)`` of the image and snapshot files.
    image_size
        ``(width, height)`` of the image as read from the file.
    renderer_version
        POV-Ray version reported by the executable (``None`` if unknown).

    Returns
    -------
    dict
        Keys, in order: ``format`` (``"ycrystal-provenance"``), ``schema_version`` (1),
        ``generator``, ``created`` (UTC), ``job`` (batch job id or ``null``),
        ``replay`` (the command that renders the snapshot again, run in the record's
        folder), ``image`` and ``project`` (``name``, ``path``, ``sha256``, ``bytes``;
        the image also ``width`` and ``height`` as rendered, the project its
        ``schema_version``), ``input``, ``style``, and ``manifest`` (``name``, ``path``,
        ``sha256``, ``bytes``; the input also its ``format``, the style its ``parts``
        and ``element_map``; ``null`` when not used), ``structure`` (``composition``,
        ``atoms``, ``displayed_atoms``), ``output`` (the image size asked of POV-Ray,
        ``antialias``, ``transparent_background``, and the explicit ``width_option`` and
        ``height_option``), ``camera`` (``policy``, ``view``, ``fit_margin``,
        ``view_height``, and the camera used, as stored in projects), ``renderer``
        (``name``, ``version``, and the standard ``includes`` the scene needs from the
        POV-Ray installation), ``system`` (operating system, machine, Python, NumPy,
        ASE), ``notes`` (warnings), and ``reproducibility``
        ([`REPRODUCIBILITY_NOTE`][ycrystal.provenance.REPRODUCIBILITY_NOTE]).

        Every ``path`` is relative to the record's folder, or ``null`` for a file
        outside it (then ``name`` and ``sha256`` identify it).
    """
    base = project_file.parent
    geometry = build_geometry(snapshot.structure, snapshot.scene)
    output = snapshot.output
    notes = list(request.notes)
    if image_size != (output.width, output.height):
        notes.append(
            f"The image is {image_size[0]} × {image_size[1]} px, but "
            f"{output.width} × {output.height} px were asked for."
        )
    if renderer_version is None:
        notes.append("The POV-Ray version could not be determined.")
    replay_image = _relative(image, base) or image.name
    replay_project = _relative(project_file, base) or project_file.name
    view = request.view
    record: dict[str, Any] = {
        "format": PROVENANCE_FORMAT,
        "schema_version": PROVENANCE_SCHEMA_VERSION,
        "generator": f"Ycrystal {__version__}",
        "created": _dt.datetime.now(_dt.UTC).isoformat(timespec="seconds"),
        "job": request.job,
        "replay": shlex.join(["ycrystal", replay_project, "--render", replay_image]),
        "image": {
            **_file_entry(image, base, *image_digest),
            "width": image_size[0],
            "height": image_size[1],
        },
        "project": {
            **_file_entry(project_file, base, *project_digest),
            "schema_version": SCHEMA_VERSION,
        },
        "input": None,
        "style": None,
        "manifest": None,
        "structure": {
            "composition": snapshot.structure.composition(),
            "atoms": len(snapshot.structure),
            "displayed_atoms": count_displayed_atoms(snapshot.structure, snapshot.scene),
        },
        "output": {
            "width": output.width,
            "height": output.height,
            "antialias": output.antialias,
            "transparent_background": output.transparent_background,
            "width_option": request.width,
            "height_option": request.height,
        },
        "camera": {
            "policy": view.policy,
            "view": view.view,
            "fit_margin": view.margin,
            "view_height": view.visible_height,
            **(snapshot.camera.to_dict() if snapshot.camera is not None else {}),
        },
        "renderer": {
            "name": "POV-Ray",
            "version": renderer_version,
            "includes": list(required_includes(geometry)),
        },
        "system": _system(),
        "notes": notes,
        "reproducibility": REPRODUCIBILITY_NOTE,
    }
    if request.input is not None:
        source = request.input
        record["input"] = {
            **_file_entry(source.path, base, source.sha256, source.size),
            "format": request.input_format,
        }
    if request.style is not None:
        style = request.style
        record["style"] = {
            **_file_entry(style.path, base, style.sha256, style.size),
            "parts": list(request.style_parts),
            "element_map": None if request.element_map is None else dict(request.element_map),
        }
    if request.manifest is not None:
        manifest = request.manifest
        record["manifest"] = _file_entry(manifest.path, base, manifest.sha256, manifest.size)
    return record


def _json_text(data: Any) -> str:
    return json.dumps(data, indent=1, ensure_ascii=False, allow_nan=False) + "\n"


# ----- the whole operation ---------------------------------------------------------------------
def render_snapshot(
    project: Project,
    image: str | os.PathLike[str],
    snapshot: str | os.PathLike[str],
    request: FigureRequest | None = None,
    povray: str | None = None,
    timeout: float | None = 1800.0,
    renderer_version: str | None = None,
) -> SnapshotRender:
    """Render a figure from its snapshot; save the image, snapshot, and provenance record.

    Parameters
    ----------
    project
        What to draw, with any style applied; it is not modified.
    image
        PNG to create or replace (as ``--render`` does).
    snapshot
        Project file to write; the record goes to
        [`provenance_path`][ycrystal.provenance.provenance_path] of it. Whether these
        may be replaced is the caller's decision (see
        [`check_snapshot_target`][ycrystal.provenance.check_snapshot_target]).
    request
        Inputs and options, recorded in the provenance; its `view`, `width`, and
        `height` choose the camera and size. ``None`` is ``FigureRequest()``.
    povray
        POV-Ray executable (default ``$YCRYSTAL_POVRAY``, then ``povray`` on ``PATH``).
    timeout
        Seconds before the render is stopped.
    renderer_version
        POV-Ray version, if already known (otherwise asked from the executable).

    Returns
    -------
    SnapshotRender
        On success the three files are in place. If POV-Ray fails, ``result.ok`` is
        false and nothing was written.

    Raises
    ------
    ycrystal.render.povray.PovrayNotFoundError
        If no POV-Ray executable is found (nothing is written).
    ycrystal.core.camera.CameraPolicyError
        If the view cannot be produced (nothing is written).
    SnapshotError
        If the snapshot or the record cannot be written (nothing is left behind).
    OSError
        If the image cannot be written (nothing is left behind).

    Notes
    -----
    Order: the snapshot is saved to a temporary file and read back; POV-Ray renders
    that reloaded project to a temporary image; the record is computed from the
    temporary files' bytes and written to a temporary file; then image, snapshot, and
    record are renamed into place, in that order. Folders created for the files are
    removed again if anything fails.
    """
    request = request or FigureRequest()
    image, snapshot = Path(image), Path(snapshot)
    record_path = provenance_path(snapshot)
    executable = find_povray(povray)
    resolved = snapshot_project(project, request.width, request.height, request.view)
    created: list[Path] = []
    temporaries: list[Path] = []
    try:
        try:
            created += _make_folder(snapshot.parent)
            temporary_snapshot = _temporary(snapshot.parent)
            temporaries.append(temporary_snapshot)
            save_project(temporary_snapshot, resolved)
            replay = load_project(temporary_snapshot)
        except (OSError, ValueError, ProjectError) as exc:
            detail = exc.strerror if isinstance(exc, OSError) and exc.strerror else exc
            raise SnapshotError(f"Cannot save the project {snapshot}: {detail}") from exc
        created += _make_folder(image.parent)
        temporary_image = _temporary(image.parent)
        temporaries += [temporary_image, temporary_image.with_name(temporary_image.name + ".part")]
        result = render_png(replay, temporary_image, executable, timeout=timeout)
        if not result.ok:
            return SnapshotRender(result)
        try:
            size = png_size(temporary_image)
        except ValueError as exc:
            return SnapshotRender(replace(result, ok=False, image_path=None, message=str(exc)))
        record = provenance_record(
            request,
            resolved,
            image,
            (file_sha256(temporary_image), temporary_image.stat().st_size),
            snapshot,
            (file_sha256(temporary_snapshot), temporary_snapshot.stat().st_size),
            size,
            renderer_version or povray_version(executable),
        )
        try:
            temporary_record = _temporary(record_path.parent)
            temporaries.append(temporary_record)
            temporary_record.write_text(_json_text(record), encoding="utf-8")
        except (OSError, ValueError) as exc:
            detail = exc.strerror if isinstance(exc, OSError) and exc.strerror else exc
            raise SnapshotError(f"Cannot write {record_path}: {detail}") from exc
        os.replace(temporary_image, image)
        os.replace(temporary_snapshot, snapshot)
        os.replace(temporary_record, record_path)
        created.clear()  # keep the folders: they hold the figure now
        return SnapshotRender(replace(result, image_path=image), snapshot, record_path, record)
    finally:
        for temporary in temporaries:
            temporary.unlink(missing_ok=True)
        for folder in reversed(created):
            try:
                folder.rmdir()
            except OSError:
                pass
