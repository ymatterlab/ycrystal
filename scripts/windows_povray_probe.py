"""Report how POV-Ray for Windows behaves when Ycrystal drives it (Windows port helper).

Run on Windows from the repository root, with Ycrystal installed in the environment::

    python scripts/windows_povray_probe.py [--povray PATH] [--timeout SECONDS]

It prints, without changing anything outside temporary folders:

1. the executable Ycrystal finds, whether it counts as POV-Ray for Windows, and the
   version read from the file;
2. the include directories Ycrystal sees and whether the standard include files used
   by Ycrystal's materials are among them;
3. for each candidate command line, the exit status, the time, whether ``scene.png``
   and the log file appeared, the files left in the job folder, and the log.

A render that does not finish within the timeout usually means that POV-Ray for
Windows waits for an answer in a dialog (first start, file access): run it once by
hand and look at its window. See ``docs/development/windows-port.md``.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time

from ycrystal.core.scene import Environment
from ycrystal.render.jobs import prepare_job
from ycrystal.render.pov_writer import RenderSettings
from ycrystal.render.povray import (
    LOG_NAME,
    background_startupinfo,
    find_povray,
    include_directories,
    is_windows_engine,
    missing_includes,
    povray_version,
    read_log,
    render_arguments,
)
from ycrystal.render.selftest import self_test_camera, self_test_geometry

INCLUDES = ("colors.inc", "textures.inc", "metals.inc", "glass.inc", "stones.inc")


def candidates(executable: str) -> dict[str, list[str]]:
    """Return the command lines to try, by name (Ycrystal's own first)."""
    ours = render_arguments(executable, "scene.ini")
    if not is_windows_engine(executable):
        return {"ycrystal": ours}
    return {
        "ycrystal": ours,
        "render-switch": ["/NR", "/EXIT", "/RENDER", "scene.ini", f"+GA{LOG_NAME}"],
    }


def probe(executable: str, name: str, arguments: list[str], timeout: float) -> None:
    job = prepare_job(
        self_test_geometry(),
        self_test_camera(),
        Environment(),
        RenderSettings(width=120, height=80, transparent_background=True),
        title="Windows port probe",
    )
    print(f"\n--- {name}: {executable} {' '.join(arguments)}")
    started = time.monotonic()
    try:
        completed = subprocess.run(
            [executable, *arguments],
            cwd=job.directory,
            capture_output=True,
            text=True,
            errors="replace",
            timeout=timeout,
            startupinfo=background_startupinfo(executable),
        )
        print(f"exit status: {completed.returncode}")
        if completed.stdout.strip() or completed.stderr.strip():
            print("printed:", (completed.stdout + completed.stderr).strip()[-2000:])
    except subprocess.TimeoutExpired:
        print(f"TIMEOUT after {timeout} s (a dialog may be waiting for an answer)")
    print(f"seconds: {time.monotonic() - started:.1f}")
    files = sorted(p.name for p in job.directory.iterdir())
    print("job folder:", files)
    image = job.image_path
    print("scene.png:", f"{image.stat().st_size} bytes" if image.is_file() else "missing")
    log = read_log(job.directory)
    print(f"{LOG_NAME}:", "missing" if not log else f"{len(log)} characters")
    if log:
        print(log[-3000:])
    job.cleanup()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--povray", help="POV-Ray executable (default: as Ycrystal finds it)")
    parser.add_argument("--timeout", type=float, default=90.0, help="seconds per render")
    args = parser.parse_args(argv)
    print(f"Python {sys.version.split()[0]} on {sys.platform}")
    executable = find_povray(args.povray)
    print("executable:", executable)
    print("POV-Ray for Windows:", is_windows_engine(executable))
    print("version:", povray_version(executable))
    print("include directories:", [str(d) for d in include_directories(executable)])
    print("missing include files:", missing_includes(INCLUDES, executable))
    for name, arguments in candidates(executable).items():
        probe(executable, name, arguments, args.timeout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
