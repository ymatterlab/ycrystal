"""Render a series of structures from one JSON manifest (FR-BATCH-01).

``ycrystal --batch MANIFEST --output-dir DIR`` renders every job of a manifest to a PNG,
one after the other, without a window. Each job is an ordinary single figure, built
with the same functions as ``ycrystal FILE --style … --render OUT.png``
([`load_input`][ycrystal.batch.load_input],
[`apply_style_file`][ycrystal.batch.apply_style_file],
[`ViewPolicy`][ycrystal.core.camera.ViewPolicy],
[`render_png`][ycrystal.batch.render_png]); a manifest only states them once, for many
structures.

The run has two phases:

1. **Validation** reads the manifest, every input, and every style, applies the
   styles and element mappings, chooses each camera, and checks the outputs. Every
   problem of every job is reported; if there is any, nothing is rendered or written.
2. **Rendering** runs the jobs in manifest order. A failed job does not stop the
   others; every image is written only when its render succeeded. A JSON report
   records every job.

Manifest format (schema 1)
--------------------------
A UTF-8 JSON object::

    {
        "format": "ycrystal-batch",
        "schema_version": 1,
        "defaults": {"style": "grey-studio.ycstyle", "view": "a", "width": 600},
        "jobs": [
            {"id": "SrTiO3", "input": "../tests/fixtures/SrTiO3.cif"},
            {"id": "BaZrO3", "input": "../tests/fixtures/BaZrO3.cif", "element_map": {"Ti": "Zr"}},
        ],
    }

``jobs`` is required and lists the figures in order. Each job has an ``id`` (letters,
digits, ``.``, ``_``, ``-``; unique) and an ``input`` (a structure file or ``.ycrystal``
project). Any of the following settings may appear in ``defaults`` (for every job)
or in a job (for that job only, replacing the default):

``output``
    PNG file name inside the output directory (default ``<id>.png``); subfolders are
    allowed, ``..`` and absolute paths are not.
``format``
    Input format, ``poscar``, ``cif``, ``qe``, or ``project`` (default: detected).
``style``
    ``.ycstyle`` file, or ``null`` for none. ``style_parts`` is a list of parts
    (default ``appearance``, ``environment``, ``output``, as for ``--style``).
``element_map``
    ``{"Ti": "Zr", "O": null}``: give the style's settings for an element to another
    element (``null`` leaves them out); see
    [`resolve_element_map`][ycrystal.io.style.resolve_element_map].
``view``, ``camera_policy``, ``fit_margin``, ``view_height``
    The camera, as ``--view``, ``--camera-policy``, ``--fit-margin``, and
    ``--view-height``.
``width``, ``height``
    Image size in pixels (16–8000); default: the input's size, or the style's.
``max_atoms``
    Largest number of displayed atoms allowed (default 20,000); larger scenes are
    refused at validation, never truncated.

Paths in a manifest are relative to the manifest's folder (absolute input and style
paths are allowed). Unknown keys are refused, so a misspelt setting is not ignored.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field, replace
from pathlib import Path, PurePosixPath
from typing import Any

from ycrystal import __version__
from ycrystal.batch import (
    CLI_STYLE_PARTS,
    StyleTransferError,
    apply_style_file,
    load_input,
    render_png,
    scene_for,
)
from ycrystal.core.camera import CameraPolicyError, ViewPolicy
from ycrystal.core.scene import LARGE_DISPLAY_ATOMS, count_displayed_atoms
from ycrystal.io.project import Project, ProjectError
from ycrystal.io.readers import StructureImportError
from ycrystal.io.style import STYLE_PARTS, ElementMapError, Style, StyleError, check_element
from ycrystal.io.style import load_style as _load_style

MANIFEST_FORMAT = "ycrystal-batch"
"""Value of the ``format`` key that identifies a batch manifest."""

MANIFEST_SCHEMA_VERSION = 1
"""Manifest schema read by this Ycrystal; newer versions are refused."""

REPORT_NAME = "ycrystal-batch-report.json"
"""File name of the report written into the output directory."""

SETTINGS = (
    "output",
    "format",
    "style",
    "style_parts",
    "element_map",
    "view",
    "camera_policy",
    "fit_margin",
    "view_height",
    "width",
    "height",
    "max_atoms",
)
"""Settings allowed in ``defaults`` and in jobs (jobs also have ``id`` and ``input``)."""

_ID = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9._-]*$")
_FORMATS = ("poscar", "cif", "qe", "project")


class ManifestError(Exception):
    """A manifest is invalid; ``problems`` lists every problem found, one per line."""

    def __init__(self, problems: list[str]):
        self.problems = list(problems)
        super().__init__("\n".join(self.problems))


@dataclass(frozen=True)
class PlannedJob:
    """One validated job, ready to render.

    Attributes
    ----------
    id
        Job identifier.
    input
        Input path as written in the manifest (for messages and the report).
    output
        Output path relative to the output directory (POSIX form).
    project
        The project to draw: the input with its style applied.
    view
        Camera policy.
    width, height
        Final image size in pixels.
    atoms
        Number of displayed atoms.
    warnings
        Notes from the style transfer (what was not applied).
    """

    id: str
    input: str
    output: str
    project: Project
    view: ViewPolicy
    width: int
    height: int
    atoms: int
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class JobResult:
    """The outcome of one job in a run."""

    id: str
    input: str
    output: str
    status: str  # "rendered", "failed", or "planned" (dry run)
    seconds: float = 0.0
    width: int = 0
    height: int = 0
    atoms: int = 0
    warnings: tuple[str, ...] = ()
    error: str = ""


@dataclass
class BatchReport:
    """Everything a run did, as written to the JSON report."""

    manifest: str
    output_dir: str
    dry_run: bool
    renderer: str = ""
    started: str = ""
    seconds: float = 0.0
    jobs: list[JobResult] = field(default_factory=list)

    @property
    def failed(self) -> int:
        """Return the number of failed jobs."""
        return sum(job.status == "failed" for job in self.jobs)

    def to_dict(self) -> dict[str, Any]:
        """Return the JSON-compatible report (paths relative, as in the manifest)."""
        return {
            "format": "ycrystal-batch-report",
            "schema_version": 1,
            "generator": f"Ycrystal {__version__}",
            "renderer": self.renderer,
            "manifest": self.manifest,
            "output_dir": self.output_dir,
            "dry_run": self.dry_run,
            "started": self.started,
            "seconds": round(self.seconds, 3),
            "summary": {
                "jobs": len(self.jobs),
                "rendered": sum(job.status == "rendered" for job in self.jobs),
                "failed": self.failed,
            },
            "jobs": [
                {
                    "id": job.id,
                    "input": job.input,
                    "output": job.output,
                    "status": job.status,
                    "seconds": round(job.seconds, 3),
                    "width": job.width,
                    "height": job.height,
                    "atoms": job.atoms,
                    "warnings": list(job.warnings),
                    "error": job.error,
                }
                for job in self.jobs
            ],
        }


# ----- validation ---------------------------------------------------------------------------
def load_manifest(path: str | Path) -> dict[str, Any]:
    """Read a manifest file and check its top-level layout.

    Raises
    ------
    ManifestError
        If the file cannot be read, is not JSON, or is not a schema-1 manifest.
    """
    path = Path(path)
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except OSError as exc:
        raise ManifestError([f"Cannot read the manifest {path}: {exc.strerror or exc}."]) from exc
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ManifestError([f"{path.name} is not valid JSON: {exc}."]) from exc
    if not isinstance(data, dict) or data.get("format") != MANIFEST_FORMAT:
        raise ManifestError([f"{path.name} is not a Ycrystal batch manifest (format)."])
    version = data.get("schema_version")
    if not isinstance(version, int) or isinstance(version, bool) or version < 1:
        raise ManifestError([f"{path.name} has no valid schema_version."])
    if version > MANIFEST_SCHEMA_VERSION:
        raise ManifestError(
            [f"{path.name} uses manifest schema {version}; this Ycrystal reads schema 1."]
        )
    unknown = sorted(set(data) - {"format", "schema_version", "defaults", "jobs", "comment"})
    if unknown:
        raise ManifestError([f"Unknown top-level keys: {', '.join(unknown)}."])
    if not isinstance(data.get("jobs"), list) or not data["jobs"]:
        raise ManifestError(["The manifest needs a non-empty list of jobs."])
    if not isinstance(data.get("defaults", {}), dict):
        raise ManifestError(["defaults must be an object."])
    return data


def plan_batch(
    manifest_path: str | Path, output_dir: str | Path, overwrite: bool = False
) -> list[PlannedJob]:
    """Validate a manifest completely and return its jobs, ready to render.

    Every input and style is read, styles and element mappings are applied, and every
    camera is chosen, so that rendering can only fail in POV-Ray or when writing.

    Parameters
    ----------
    manifest_path
        The manifest; relative paths in it are relative to its folder.
    output_dir
        Where the images and the report go; it need not exist yet.
    overwrite
        Whether existing images (and an existing report) may be replaced.

    Raises
    ------
    ManifestError
        With every problem of every job, if there is any.
    """
    manifest_path = Path(manifest_path)
    data = load_manifest(manifest_path)
    base = manifest_path.resolve().parent
    output_dir = Path(output_dir)
    defaults = data.get("defaults", {})
    problems: list[str] = []
    unknown = sorted(set(defaults) - set(SETTINGS))
    if unknown:
        problems.append(f"defaults: unknown settings {', '.join(unknown)}.")
    styles: dict[Path, Style | str] = {}
    planned: list[PlannedJob] = []
    seen_ids: set[str] = set()
    seen_outputs: dict[str, str] = {}
    for number, job in enumerate(data["jobs"], start=1):
        label = f"job {number}"
        if not isinstance(job, dict):
            problems.append(f"{label}: must be an object.")
            continue
        job_id = job.get("id")
        if not isinstance(job_id, str) or not _ID.match(job_id):
            problems.append(
                f"{label}: id must be letters, digits, '.', '_', or '-' (got {job_id!r})."
            )
            continue
        label = f"job {job_id}"
        if job_id in seen_ids:
            problems.append(f"{label}: the id is used twice.")
            continue
        seen_ids.add(job_id)
        unknown = sorted(set(job) - set(SETTINGS) - {"id", "input"})
        if unknown:
            problems.append(f"{label}: unknown settings {', '.join(unknown)}.")
            continue
        settings = {**defaults, **{k: v for k, v in job.items() if k not in ("id", "input")}}
        try:
            planned.append(
                _plan_job(
                    job_id,
                    job.get("input"),
                    settings,
                    base,
                    output_dir,
                    overwrite,
                    styles,
                    seen_outputs,
                )
            )
        except _JobProblem as exc:
            problems.append(f"{label}: {exc}")
    report = output_dir / REPORT_NAME
    if not overwrite and report.exists():
        problems.append(f"The report {report} exists; use --overwrite to replace it.")
    if problems:
        raise ManifestError(problems)
    return planned


class _JobProblem(Exception):
    pass


def _path(value: Any, base: Path, what: str) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise _JobProblem(f"{what} must be a file path.")
    path = Path(value).expanduser()
    return path if path.is_absolute() else base / path


def _plan_job(
    job_id: str,
    input_value: Any,
    s: dict[str, Any],
    base: Path,
    output_dir: Path,
    overwrite: bool,
    styles: dict[Path, Style | str],
    seen_outputs: dict[str, str],
) -> PlannedJob:
    # Output: a relative PNG path inside the output directory, unique, not present.
    output = s.get("output", f"{job_id}.png")
    if not isinstance(output, str) or not output:
        raise _JobProblem("output must be a file name.")
    pure = PurePosixPath(output.replace("\\", "/"))
    if pure.is_absolute() or ".." in pure.parts or Path(output).is_absolute():
        raise _JobProblem(f"output {output!r} must stay inside the output directory.")
    if pure.suffix.lower() != ".png":
        raise _JobProblem(f"output {output!r} must be a .png file (batch rendering writes PNG).")
    key = str(pure).casefold()  # case-insensitive file systems (macOS) collide too
    if key in seen_outputs:
        raise _JobProblem(f"output {output!r} is also the output of job {seen_outputs[key]}.")
    seen_outputs[key] = job_id
    target = output_dir / pure
    if not overwrite and target.exists():
        raise _JobProblem(f"{target} exists; use --overwrite to replace it.")

    # Input.
    source = _path(input_value, base, "input")
    if not source.is_file():
        raise _JobProblem(f"input {input_value!r} not found ({source}).")
    fmt = s.get("format")
    if fmt is not None and fmt not in _FORMATS:
        raise _JobProblem(f"format must be one of {', '.join(_FORMATS)}.")
    try:
        project = load_input(source, fmt)
    except (ProjectError, StructureImportError) as exc:
        raise _JobProblem(f"cannot read {input_value!r}: {exc}") from exc

    # Size and limits.
    width, height = s.get("width"), s.get("height")
    for name, value in (("width", width), ("height", height)):
        if value is not None and (
            not isinstance(value, int) or isinstance(value, bool) or not 16 <= value <= 8000
        ):
            raise _JobProblem(f"{name} must be a whole number of pixels from 16 to 8000.")
    max_atoms = s.get("max_atoms", LARGE_DISPLAY_ATOMS)
    if not isinstance(max_atoms, int) or isinstance(max_atoms, bool) or max_atoms < 1:
        raise _JobProblem("max_atoms must be a positive whole number.")

    # Camera.
    try:
        margin = s.get("fit_margin", 0.06)
        if not isinstance(margin, (int, float)) or isinstance(margin, bool):
            raise CameraPolicyError("fit_margin must be a number from 0 to 1.")
        view_height = s.get("view_height")
        if view_height is not None and (
            not isinstance(view_height, (int, float)) or isinstance(view_height, bool)
        ):
            raise CameraPolicyError("view_height must be a number of Å.")
        view = ViewPolicy(
            camera=s.get("camera_policy"),
            view=s.get("view"),
            margin=float(margin),
            visible_height=None if view_height is None else float(view_height),
        )
    except CameraPolicyError as exc:
        raise _JobProblem(str(exc)) from exc

    # Style and element mapping.
    warnings: tuple[str, ...] = ()
    style_value = s.get("style")
    if style_value is not None:
        style_path = _path(style_value, base, "style").resolve()
        if style_path not in styles:
            try:
                styles[style_path] = _load_style(style_path)
            except StyleError as exc:
                styles[style_path] = str(exc)
        style = styles[style_path]
        if isinstance(style, str):
            raise _JobProblem(f"style {style_value!r}: {style}")
        parts = s.get("style_parts", list(CLI_STYLE_PARTS))
        if (
            not isinstance(parts, list)
            or not parts
            or not all(isinstance(p, str) and p in STYLE_PARTS for p in parts)
        ):
            raise _JobProblem(f"style_parts must be a non-empty list of {', '.join(STYLE_PARTS)}.")
        element_map = s.get("element_map")
        if element_map is not None:
            if not isinstance(element_map, dict):
                raise _JobProblem('element_map must be an object such as {"Ti": "Zr"}.')
            try:
                for key, value in element_map.items():
                    check_element(key, "a source element")
                    if value is not None:
                        check_element(value, "a target element")
            except ElementMapError as exc:
                raise _JobProblem(f"element_map: {exc}") from exc
        try:
            project, warnings = apply_style_file(
                project,
                style,
                tuple(parts),
                max_atoms=max_atoms,
                element_map=element_map,
                camera_kept=view.policy == "saved",
            )
        except StyleTransferError as exc:
            raise _JobProblem(str(exc)) from exc
    elif s.get("element_map") is not None or s.get("style_parts") is not None:
        raise _JobProblem("element_map and style_parts need a style.")

    atoms = count_displayed_atoms(project.structure, project.scene)
    if atoms > max_atoms:
        raise _JobProblem(
            f"{atoms:,} displayed atoms exceed max_atoms = {max_atoms:,}; raise max_atoms "
            "if this is intended."
        )
    try:
        _, _, settings = scene_for(project, width, height, view)
    except CameraPolicyError as exc:
        raise _JobProblem(str(exc)) from exc
    return PlannedJob(
        job_id,
        str(input_value),
        str(pure),
        project,
        view,
        settings.width,
        settings.height,
        atoms,
        warnings,
    )


# ----- running ------------------------------------------------------------------------------
def run_batch(
    jobs: list[PlannedJob],
    output_dir: str | Path,
    povray: str | None = None,
    dry_run: bool = False,
    manifest: str = "",
    progress: Any = None,
) -> BatchReport:
    """Render planned jobs in order and return the report (also written as JSON).

    Parameters
    ----------
    jobs
        From [`plan_batch`][ycrystal.manifest.plan_batch].
    output_dir
        Created if missing.
    povray
        POV-Ray executable (default: ``$YCRYSTAL_POVRAY``, then ``povray`` on ``PATH``).
    dry_run
        Do not render or write anything; every job is reported as ``planned``.
    manifest
        Manifest path as given, recorded in the report.
    progress
        Optional ``callable(text)`` for one line per job.

    Raises
    ------
    ycrystal.render.povray.PovrayNotFoundError
        If POV-Ray is not found (before any job runs; nothing is written).
    OSError
        If the output directory or the report cannot be written.
    """
    from ycrystal.render.povray import find_povray, povray_version

    output_dir = Path(output_dir)
    report = BatchReport(manifest=manifest, output_dir=str(output_dir), dry_run=dry_run)
    report.started = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    started = time.monotonic()
    say = progress or (lambda _text: None)
    if dry_run:
        for job in jobs:
            report.jobs.append(_result(job, "planned"))
            say(
                f"{job.id}: would render {job.output} ({job.width} × {job.height}, "
                f"{job.atoms} atoms)"
            )
        return report
    executable = find_povray(povray)
    report.renderer = f"POV-Ray {povray_version(executable) or 'version unknown'}"
    output_dir.mkdir(parents=True, exist_ok=True)
    for number, job in enumerate(jobs, start=1):
        began = time.monotonic()
        try:
            result = render_png(
                job.project,
                output_dir / job.output,
                executable,
                job.width,
                job.height,
                view=job.view,
            )
            error = "" if result.ok else result.message
        except OSError as exc:
            error = f"cannot write {job.output}: {exc.strerror or exc}"
        except Exception as exc:  # one job must not stop the series  # noqa: BLE001
            error = f"{type(exc).__name__}: {exc}"
        status = "failed" if error else "rendered"
        report.jobs.append(
            replace(_result(job, status), seconds=time.monotonic() - began, error=error)
        )
        say(f"[{number}/{len(jobs)}] {job.id}: {status}" + (f" ({error})" if error else ""))
    report.seconds = time.monotonic() - started
    write_report(report, output_dir / REPORT_NAME)
    return report


def _result(job: PlannedJob, status: str) -> JobResult:
    return JobResult(
        job.id, job.input, job.output, status, 0.0, job.width, job.height, job.atoms, job.warnings
    )


def write_report(report: BatchReport, path: str | Path) -> Path:
    """Write the JSON report atomically and return its path."""
    path = Path(path)
    tmp = path.with_name(path.name + ".part")
    tmp.write_text(json.dumps(report.to_dict(), indent=1, ensure_ascii=False) + "\n", "utf-8")
    tmp.replace(path)
    return path
