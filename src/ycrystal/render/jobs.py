"""Render jobs: isolated temporary directories with short ASCII file names.

POV-Ray runs with the job directory as its working directory and writes only there.
This avoids problems with spaces/non-ASCII characters in user paths and works within
POV-Ray's I/O restrictions (``povray.conf`` normally permits the working directory).
The finished image is copied to the user's destination by Python afterwards.

A job goes through these steps; the caller owns the job directory throughout:

1. [`prepare_job`][ycrystal.render.jobs.prepare_job] creates a new directory
   ``ycrystal-job-*`` (in the system temporary directory by default) containing
   ``scene.pov`` and ``scene.ini``.
2. POV-Ray runs with that directory as its working directory, either synchronously
   with [`run_job`][ycrystal.render.jobs.run_job] or asynchronously with
   [`RenderProcess`][ycrystal.render.process.RenderProcess]. It writes ``scene.png``.
3. [`finish_job`][ycrystal.render.jobs.finish_job] turns the exit status and log into
   a [`RenderResult`][ycrystal.render.jobs.RenderResult]; renderer failures are
   reported in the result, not raised.
4. [`copy_result`][ycrystal.render.jobs.copy_result] copies the image to its
   destination.
5. [`RenderJob.cleanup`][ycrystal.render.jobs.RenderJob.cleanup] deletes the
   directory. Nothing in this module does that automatically.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from ycrystal.core.camera import Camera
from ycrystal.core.scene import DisplayGeometry, Environment
from ycrystal.render.pov_writer import RenderSettings, write_scene_files
from ycrystal.render.povray import explain_failure

JOB_BASENAME = "scene"
"""File-name stem of the scene, settings, and image files inside a job directory."""


@dataclass(frozen=True)
class RenderJob:
    """Files of one render, in a private directory.

    Attributes
    ----------
    directory
        Job directory, created by [`prepare_job`][ycrystal.render.jobs.prepare_job].
    pov_path
        Scene file ``directory / "scene.pov"``.
    ini_path
        Settings file ``directory / "scene.ini"``.
    image_path
        Expected output ``directory / "scene.png"``; it exists only after POV-Ray
        has rendered successfully.
    settings
        Output settings written into the scene and the ``.ini`` file.
    """

    directory: Path
    pov_path: Path
    ini_path: Path
    image_path: Path
    settings: RenderSettings

    def arguments(self) -> list[str]:
        """Return the POV-Ray command-line arguments, without the executable.

        Returns
        -------
        list of str
            ``["scene.ini"]``. The name is relative, so the process must run with
            `directory` as its working directory.
        """
        return [self.ini_path.name]

    def cleanup(self) -> None:
        """Delete the job directory and everything in it, ignoring errors.

        This also deletes the rendered image, so copy it first.
        """
        shutil.rmtree(self.directory, ignore_errors=True)


@dataclass(frozen=True)
class RenderResult:
    """Outcome of one POV-Ray run.

    Attributes
    ----------
    ok
        Whether POV-Ray exited with status 0 and wrote a non-empty image.
    returncode
        Exit status, or ``None`` if POV-Ray could not be started, timed out, crashed,
        or was stopped.
    log
        POV-Ray's combined standard output and standard error.
    image_path
        The rendered PNG inside the job directory when `ok` is true, else ``None``. It
        disappears when the job is cleaned up.
    message
        Readable explanation of a failure; empty when `ok` is true.
    """

    ok: bool
    returncode: int | None
    log: str
    image_path: Path | None
    message: str = ""


def prepare_job(
    geometry: DisplayGeometry,
    camera: Camera,
    environment: Environment,
    settings: RenderSettings,
    parent: Path | None = None,
    **writer_kwargs: str,
) -> RenderJob:
    """Create a job directory and write the scene and settings into it.

    Parameters
    ----------
    geometry
        Atoms and cell edges to draw.
    camera
        View to reproduce.
    environment
        Background colour and light intensities.
    settings
        Output image settings.
    parent
        Directory in which to create the job directory; ``None`` uses the system
        temporary directory (``$TMPDIR``, usually ``/tmp``).
    **writer_kwargs
        Passed to [`scene_to_pov`][ycrystal.render.pov_writer.scene_to_pov].

    Returns
    -------
    RenderJob
        The prepared job. Call [`RenderJob.cleanup`][ycrystal.render.jobs.RenderJob.cleanup]
        when it is no longer needed.

    Raises
    ------
    OSError
        If the directory or the files cannot be created.

    Notes
    -----
    If writing fails after directory creation, the partial directory is retained
    and no job is returned; the caller may need to remove it manually.
    """
    directory = Path(tempfile.mkdtemp(prefix="ycrystal-job-", dir=parent))
    pov, ini, image = write_scene_files(
        directory, JOB_BASENAME, geometry, camera, environment, settings, **writer_kwargs
    )
    return RenderJob(directory, pov, ini, image, settings)


def finish_job(job: RenderJob, returncode: int | None, log: str) -> RenderResult:
    """Interpret the exit status and output of a finished POV-Ray process.

    Parameters
    ----------
    job
        The job that was rendered.
    returncode
        Exit status, or ``None`` if the process crashed or was stopped.
    log
        Combined output of the process.

    Returns
    -------
    RenderResult
        Success if `returncode` is 0 and ``job.image_path`` is a non-empty file;
        otherwise a failure whose message comes from
        [`explain_failure`][ycrystal.render.povray.explain_failure].
    """
    if returncode == 0 and job.image_path.is_file() and job.image_path.stat().st_size > 0:
        return RenderResult(True, returncode, log, job.image_path)
    if returncode == 0:
        message = "POV-Ray finished but produced no image.\n" + explain_failure(returncode, log)
    else:
        message = explain_failure(returncode, log)
    return RenderResult(False, returncode, log, None, message)


def run_job(job: RenderJob, executable: str, timeout: float | None = 600.0) -> RenderResult:
    """Run POV-Ray for a job and wait until it finishes.

    The calling thread blocks for the whole render. The command line interface, the
    tests, and the renderer check use this function; the GUI uses
    [`RenderProcess`][ycrystal.render.process.RenderProcess] so that the window stays
    responsive.

    Parameters
    ----------
    job
        Prepared job; POV-Ray runs with ``job.directory`` as its working directory.
    executable
        POV-Ray executable, for example from
        [`find_povray`][ycrystal.render.povray.find_povray].
    timeout
        Seconds after which POV-Ray is killed; ``None`` waits indefinitely.

    Returns
    -------
    RenderResult
        The outcome. A failure to start, a timeout, or a failed render gives
        ``ok=False`` with an explanation instead of an exception.

    Notes
    -----
    The job directory is not removed; call
    [`RenderJob.cleanup`][ycrystal.render.jobs.RenderJob.cleanup] afterwards.
    """
    try:
        completed = subprocess.run(
            [executable, *job.arguments()],
            cwd=job.directory,
            capture_output=True,
            text=True,
            errors="replace",
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        log = (exc.stdout or "") + (exc.stderr or "") if isinstance(exc.stdout, str) else ""
        return RenderResult(False, None, log, None, f"POV-Ray timed out after {timeout} s.")
    except OSError as exc:
        return RenderResult(False, None, str(exc), None, f"Could not start POV-Ray: {exc}")
    return finish_job(job, completed.returncode, completed.stdout + completed.stderr)


def copy_result(image: Path, destination: Path) -> Path:
    """Copy a finished image to its destination.

    Parameters
    ----------
    image
        Rendered image, usually ``RenderResult.image_path``.
    destination
        Target path; any characters are allowed. Missing parent directories are
        created.

    Returns
    -------
    pathlib.Path
        `destination` as a ``Path``.

    Raises
    ------
    OSError
        If the image cannot be read or the destination cannot be written.

    Notes
    -----
    The image is first copied to ``<destination>.part`` in the same directory and
    then renamed, which replaces an existing file without asking. If copying fails,
    the ``.part`` file is not removed.
    """
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    tmp = destination.with_name(destination.name + ".part")
    shutil.copyfile(image, tmp)
    tmp.replace(destination)
    return destination
