"""Render or export projects and structure files without opening a window.

Used by ``ycrystal --render`` and ``ycrystal --export-pov``. A project is drawn exactly
as saved (camera of the output image, output size, materials, environment); a structure
file gets the default display settings and the default view. No Qt or VTK code is
imported, so these functions work without a display.

With ``--style`` (FR-STYLE-CLI-01), [`apply_style_file`][ycrystal.batch.apply_style_file]
first applies a ``.ycstyle`` file with the transfer rules of
[`apply_style`][ycrystal.io.style.apply_style], as *File ▸ Import Style…* does in the
window. The command line applies the parts in
[`CLI_STYLE_PARTS`][ycrystal.batch.CLI_STYLE_PARTS] unless told otherwise.

Examples
--------
>>> import tempfile
>>> from pathlib import Path
>>> from ycrystal.batch import export_scene, load_input
>>> project = load_input("tests/fixtures/SrTiO3.cif")
>>> with tempfile.TemporaryDirectory() as tmp:
...     pov, ini = export_scene(project, Path(tmp) / "SrTiO3.pov", width=320, height=240)
...     ("Width=320" in ini.read_text(), pov.name)
(True, 'SrTiO3.pov')

A style designed for SrTiO3 applied to MgB2: the environment and output size transfer,
the Ti and O overrides do not (MgB2 has neither), and a note says so.

>>> from ycrystal.batch import apply_style_file
>>> mgb2 = load_input("tests/fixtures/MgB2.cif")
>>> styled, notes = apply_style_file(mgb2, "examples/grey-studio.ycstyle")
>>> styled.environment.preset, (styled.output.width, styled.output.height)
('studio_grey', (800, 600))
>>> styled.scene.repetitions  # display settings are not applied by default
(1, 1, 1)
>>> print(notes[0])
Element overrides for O, Ti were not applied: the structure has no O, Ti.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import replace
from pathlib import Path

from ycrystal.core import aspect
from ycrystal.core.camera import Camera, default_camera
from ycrystal.core.scene import (
    LARGE_DISPLAY_ATOMS,
    DisplayGeometry,
    build_geometry,
    count_displayed_atoms,
)
from ycrystal.io.project import PROJECT_SUFFIX, Project, load_project
from ycrystal.io.readers import read_structure
from ycrystal.io.style import (
    STYLE_PARTS,
    ElementMapError,
    Style,
    apply_style,
    check_element,
    load_style,
)
from ycrystal.render.jobs import RenderResult, copy_result, prepare_job, run_job
from ycrystal.render.pov_writer import RenderSettings, write_scene_files
from ycrystal.render.povray import find_povray, povray_version

CLI_STYLE_PARTS = ("appearance", "environment", "output")
"""Style parts that ``ycrystal --style`` applies when ``--style-parts`` is not given.

``display`` (repetitions, cell edges, bonds, atom size, hidden atoms) is left out: the
repetitions and hidden atoms of the style's own structure rarely suit another one. Ask
for it with ``--style-parts appearance,display,environment,output``. The window's
*File ▸ Import Style…* still offers all four parts.
"""


class StyleTransferError(ValueError):
    """A style cannot be applied as requested; ``str(error)`` is a message for the user."""


def parse_style_parts(text: str) -> tuple[str, ...]:
    """Parse a comma-separated list of style parts, as given to ``--style-parts``.

    Spaces around names are ignored, and a repeated name counts once; the result is in
    the order of [`STYLE_PARTS`][ycrystal.io.style.STYLE_PARTS].

    >>> parse_style_parts("environment, appearance")
    ('appearance', 'environment')

    Raises
    ------
    ValueError
        If the list is empty, has an empty entry, or names an unknown part.
    """
    names = [name.strip() for name in text.split(",")]
    if not text.strip() or any(not name for name in names):
        raise ValueError(
            "expected a comma-separated list of style parts, for example "
            f"'appearance,environment'; choose from {', '.join(STYLE_PARTS)}"
        )
    unknown = sorted(set(names) - set(STYLE_PARTS))
    if unknown:
        raise ValueError(
            f"unknown style part {', '.join(unknown)}; choose from {', '.join(STYLE_PARTS)}"
        )
    return tuple(part for part in STYLE_PARTS if part in names)


def parse_element_map(text: str) -> dict[str, str | None]:
    """Parse an element mapping, as given to ``--element-map`` (FR-STYLE-MAP-01).

    ``SOURCE=TARGET`` pairs separated by commas: the style's settings for ``SOURCE`` go
    to ``TARGET``. ``SOURCE=-`` leaves them out. Symbols are case-sensitive; spaces
    around them are ignored. Whether the targets exist in the structure is checked
    when the style is applied.

    >>> parse_element_map("Sr=Ba, Ti=Zr, O=-")
    {'Sr': 'Ba', 'Ti': 'Zr', 'O': None}

    Raises
    ------
    ValueError
        If an entry is empty or has no ``=``, a symbol is not a chemical element, or a
        source element appears twice.
    """
    mapping: dict[str, str | None] = {}
    if not text.strip():
        raise ValueError("expected SOURCE=TARGET pairs, for example 'Sr=Ba,Ti=Zr'")
    for entry in text.split(","):
        source, sep, target = (part.strip() for part in entry.partition("="))
        if not sep or not source or not target:
            raise ValueError(
                f"{entry.strip()!r} is not SOURCE=TARGET; write for example 'Ti=Zr', or "
                "'O=-' to leave the settings of O out"
            )
        try:
            check_element(source, "a source element")
            if target != "-":
                check_element(target, "a target element")
        except ElementMapError as exc:
            raise ValueError(str(exc)) from exc
        if source in mapping:
            raise ValueError(f"{source} is mapped twice")
        mapping[source] = None if target == "-" else target
    return mapping


def apply_style_file(
    project: Project,
    style: str | Path | Style,
    parts: Iterable[str] = CLI_STYLE_PARTS,
    max_atoms: int = LARGE_DISPLAY_ATOMS,
    element_map: dict[str, str | None] | None = None,
) -> tuple[Project, tuple[str, ...]]:
    """Return a new project with a style applied, and notes on what was left out.

    Parameters
    ----------
    project
        Target project (a saved project or a structure read by
        [`load_input`][ycrystal.batch.load_input]). It is not modified.
    style
        Style file (JSON or a ZIP package with a background picture), or a loaded
        [`Style`][ycrystal.io.style.Style]. Loading registers the package's picture and
        custom material definitions for this session.
    parts
        Parts to apply, a subset of [`STYLE_PARTS`][ycrystal.io.style.STYLE_PARTS];
        default [`CLI_STYLE_PARTS`][ycrystal.batch.CLI_STYLE_PARTS].
    max_atoms
        Limit on displayed atoms when the style's display settings raise the count.
    element_map
        Optional ``{source element: target element or None}`` for styles made for
        another composition (see
        [`resolve_element_map`][ycrystal.io.style.resolve_element_map]); ``None``
        transfers by matching symbols.

    Returns
    -------
    tuple
        ``(project, notes)``: a new project sharing the structure, with the settings of
        [`apply_style`][ycrystal.io.style.apply_style], and one sentence per part that
        was not applied or deserves attention (for warnings, not errors).

    Raises
    ------
    ycrystal.io.style.StyleError
        If the style file cannot be read.
    StyleTransferError
        If `parts` is empty or names an unknown part, if `element_map` is invalid or
        ambiguous for this structure, or if the style's display settings would raise
        the number of displayed atoms above `max_atoms`.

    Notes
    -----
    The structure, its vectors (components and attachments), and the project's saved
    camera are kept. A structure without a camera gets the default view fitted to the
    styled geometry when it is drawn (see [`scene_for`][ycrystal.batch.scene_for]). A
    style's repetitions are not applied if they would display more than `max_atoms`
    atoms *and* more atoms than the project already shows; a project saved with many
    atoms is drawn as before.
    """
    parts = tuple(parts)
    if not parts:
        raise StyleTransferError("No style parts were chosen.")
    unknown = sorted(set(parts) - set(STYLE_PARTS))
    if unknown:
        raise StyleTransferError(f"Unknown style parts: {', '.join(unknown)}.")
    if not isinstance(style, Style):
        style = load_style(style)
    structure = project.structure
    output = project.output
    try:
        result = apply_style(
            style,
            structure,
            project.scene,
            project.environment,
            (output.width, output.height),
            parts,
            element_map,
        )
    except ElementMapError as exc:
        raise StyleTransferError(f"Element mapping: {exc}") from exc
    notes = list(result.notes)
    scene = result.scene
    before = count_displayed_atoms(structure, project.scene)
    count = count_displayed_atoms(structure, scene)
    if count > max_atoms and count > before:
        cells = " × ".join(map(str, scene.repetitions))
        raise StyleTransferError(
            f"The style's display settings ({cells} cells) would show {count:,} atoms of "
            f"{structure.composition()}, more than the limit of {max_atoms:,} for styles "
            "applied without a window. Leave out the display part (--style-parts), or "
            "apply the style in the window and save a project."
        )
    if project.camera is not None and scene.repetitions != project.scene.repetitions:
        notes.append(
            "The project's saved camera was kept; the style's repetitions "
            f"({' × '.join(map(str, scene.repetitions))}) may extend beyond the frame."
        )
    width, height = result.output_size
    if (width, height) != (output.width, output.height):
        ratio = output.aspect_ratio
        if ratio is not None and not aspect.matches_ratio((width, height), ratio):
            ratio = None  # the lock follows the new shape, as in the window
        output = replace(output, width=width, height=height, aspect_ratio=ratio)
    output = replace(output, transparent_background=result.environment.transparent)
    styled = Project(
        structure=structure,
        scene=scene,
        environment=result.environment,
        camera=project.camera,
        output=output,
    )
    return styled, tuple(notes)


def load_input(path: str | Path, fmt: str | None = None) -> Project:
    """Read a ``.ycrystal`` project, or a structure file as a new project.

    Parameters
    ----------
    path
        Project or structure file (POSCAR/CONTCAR, CIF, QE ``ibrav = 0``).
    fmt
        ``"project"``, ``"poscar"``, ``"cif"``, or ``"qe"``; ``None`` detects it (a
        ``.ycrystal`` suffix means a project).

    Raises
    ------
    ycrystal.io.project.ProjectError
        If a project cannot be read.
    ycrystal.io.readers.StructureImportError
        If a structure cannot be read, including files that need a question answered
        (format, CIF block, element mapping); open those in the window instead.
    """
    path = Path(path)
    if fmt == "project" or (fmt is None and path.suffix.lower() == PROJECT_SUFFIX):
        return load_project(path)
    return Project(read_structure(path, fmt))


def _settings(project: Project, width: int | None, height: int | None) -> RenderSettings:
    output = project.output
    return replace(
        output,
        width=int(width or output.width),
        height=int(height or output.height),
        transparent_background=project.environment.transparent,
    )


def scene_for(
    project: Project, width: int | None = None, height: int | None = None
) -> tuple[DisplayGeometry, Camera, RenderSettings]:
    """Return the geometry, camera, and output settings that draw ``project``.

    The saved camera is used when there is one, otherwise the default view fitted to the
    output aspect ratio. A different `width` or `height` keeps the camera's centre and
    visible height (only the visible width follows the new aspect ratio), as in the
    window.
    """
    settings = _settings(project, width, height)
    geometry = build_geometry(project.structure, project.scene)
    camera = project.camera
    if camera is None:
        points, radii = geometry.points_and_radii()
        camera = default_camera(points, radii, settings.width / settings.height)
    return geometry, camera, settings


def export_scene(
    project: Project,
    pov_path: str | Path,
    width: int | None = None,
    height: int | None = None,
) -> tuple[Path, Path]:
    """Write ``NAME.pov`` and ``NAME.ini`` for a project; POV-Ray is not needed.

    Returns
    -------
    tuple of pathlib.Path
        The scene and settings files (the ``.ini`` names ``NAME.png`` as output).
    """
    pov_path = Path(pov_path).with_suffix(".pov")
    geometry, camera, settings = scene_for(project, width, height)
    pov, ini, _ = write_scene_files(
        pov_path.parent,
        pov_path.stem,
        geometry,
        camera,
        project.environment,
        settings,
        title=f"Ycrystal scene: {project.structure.composition()}",
    )
    return pov, ini


def render_png(
    project: Project,
    destination: str | Path,
    povray: str | None = None,
    width: int | None = None,
    height: int | None = None,
    timeout: float | None = 1800.0,
) -> RenderResult:
    """Render a project to a PNG with POV-Ray and wait for the result.

    Parameters
    ----------
    project
        What to draw; see [`scene_for`][ycrystal.batch.scene_for].
    destination
        PNG file to create or replace (only when the render succeeds).
    povray
        POV-Ray executable; ``None`` uses ``$YCRYSTAL_POVRAY``, then ``povray`` on
        ``PATH``.
    width, height
        Output size in pixels; ``None`` keeps the project's size.
    timeout
        Seconds before the render is stopped.

    Returns
    -------
    ycrystal.render.jobs.RenderResult
        With ``image_path`` set to `destination` on success. The temporary job
        directory is removed.

    Raises
    ------
    ycrystal.render.povray.PovrayNotFoundError
        If no POV-Ray executable is found.
    """
    executable = find_povray(povray)
    geometry, camera, settings = scene_for(project, width, height)
    version = povray_version(executable)
    job = prepare_job(
        geometry,
        camera,
        project.environment,
        settings,
        title=f"Ycrystal scene: {project.structure.composition()}",
        renderer_note=f"{executable} ({version or 'version unknown'})",
    )
    try:
        result = run_job(job, executable, timeout=timeout)
        if result.ok and result.image_path is not None:
            copied = copy_result(result.image_path, Path(destination))
            result = replace(result, image_path=copied)
        return result
    finally:
        job.cleanup()
