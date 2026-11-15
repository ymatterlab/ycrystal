"""Render jobs: isolated temporary directories with short ASCII file names.

POV-Ray runs with the job directory as its working directory and writes only there.
This avoids problems with spaces/non-ASCII characters in user paths and works within
POV-Ray's I/O restrictions (``povray.conf`` normally permits the working directory).
The finished image is copied to the user's destination by Python afterwards.
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


@dataclass(frozen=True)
class RenderJob:
    directory: Path
    pov_path: Path
    ini_path: Path
    image_path: Path
    settings: RenderSettings

    def arguments(self) -> list[str]:
        """Arguments for the POV-Ray process (run with cwd = ``directory``)."""
        return [self.ini_path.name]

    def cleanup(self) -> None:
        shutil.rmtree(self.directory, ignore_errors=True)


@dataclass(frozen=True)
class RenderResult:
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
    directory = Path(tempfile.mkdtemp(prefix="ycrystal-job-", dir=parent))
    pov, ini, image = write_scene_files(
        directory, JOB_BASENAME, geometry, camera, environment, settings, **writer_kwargs
    )
    return RenderJob(directory, pov, ini, image, settings)


def finish_job(job: RenderJob, returncode: int | None, log: str) -> RenderResult:
    """Interpret a finished POV-Ray process for ``job``."""
    if returncode == 0 and job.image_path.is_file() and job.image_path.stat().st_size > 0:
        return RenderResult(True, returncode, log, job.image_path)
    if returncode == 0:
        message = "POV-Ray finished but produced no image.\n" + explain_failure(returncode, log)
    else:
        message = explain_failure(returncode, log)
    return RenderResult(False, returncode, log, None, message)


def run_job(job: RenderJob, executable: str, timeout: float | None = 600.0) -> RenderResult:
    """Run POV-Ray synchronously (CLI, tests, renderer check). The GUI uses QProcess."""
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
    """Copy a finished image to the user's chosen path (any characters allowed)."""
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    tmp = destination.with_name(destination.name + ".part")
    shutil.copyfile(image, tmp)
    tmp.replace(destination)
    return destination
