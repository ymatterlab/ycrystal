"""Render or export projects and structure files without opening a window.

Used by ``ycrystal --render`` and ``ycrystal --export-pov``. A project is drawn exactly
as saved (camera of the output image, output size, materials, environment); a structure
file gets the default display settings and the default view. No Qt or VTK code is
imported, so these functions work without a display.

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
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from ycrystal.core.camera import Camera, default_camera
from ycrystal.core.scene import DisplayGeometry, build_geometry
from ycrystal.io.project import PROJECT_SUFFIX, Project, load_project
from ycrystal.io.readers import read_structure
from ycrystal.render.jobs import RenderResult, copy_result, prepare_job, run_job
from ycrystal.render.pov_writer import RenderSettings, write_scene_files
from ycrystal.render.povray import find_povray, povray_version


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
