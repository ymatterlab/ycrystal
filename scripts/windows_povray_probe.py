r"""Report how POV-Ray for Windows behaves when Ycrystal drives it (Windows port helper).

Run on Windows from the repository root, with Ycrystal installed in the environment::

    .venv\Scripts\python.exe scripts\windows_povray_probe.py [--povray PATH] [--timeout SECONDS]

It prints, without changing anything outside temporary folders:

1. the executable Ycrystal finds, whether it counts as POV-Ray for Windows, and the
   version read from the file;
2. the include directories Ycrystal sees and whether the standard include files used
   by Ycrystal's materials are among them;
3. for POV-Ray for Windows, its settings file and whether it keeps a single instance;
   if a copy of it is open, the probe stops there (a second copy could not render);
4. for each candidate command line, the exit status, the time, whether ``scene.png``
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
    _engine_settings_file,
    background_startupinfo,
    find_povray,
    include_directories,
    is_windows_engine,
    keeps_single_instance,
    missing_includes,
    povray_version,
    read_log,
    render_arguments,
    windows_engine_conflict,
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


def window_texts(pid: int) -> list[str]:
    """Return the visible windows of a process, with the texts of their controls.

    A dialog that POV-Ray for Windows waits on shows here with its title, message, and
    buttons. Empty on other systems.
    """
    if sys.platform != "win32":
        return []
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.WinDLL("user32")
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def text_of(hwnd) -> str:
        buffer = ctypes.create_unicode_buffer(user32.GetWindowTextLengthW(hwnd) + 1)
        user32.GetWindowTextW(hwnd, buffer, len(buffer))
        return buffer.value

    lines: list[str] = []

    def on_window(hwnd, _):
        owner = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(owner))
        if owner.value == pid and user32.IsWindowVisible(hwnd):
            parts: list[str] = []

            def on_child(child, _):
                if user32.IsWindowVisible(child) and text_of(child).strip():
                    parts.append(text_of(child).strip().replace("\r\n", " ").replace("\n", " "))
                return True

            user32.EnumChildWindows(hwnd, callback_type(on_child), 0)
            lines.append(f"{text_of(hwnd)!r}: " + " | ".join(parts)[:1500])
        return True

    user32.EnumWindows(callback_type(on_window), 0)
    return lines


def save_screenshot(path) -> bool:
    """Save a screenshot of the whole desktop (Windows; needs Pillow)."""
    try:
        from PIL import ImageGrab

        path.parent.mkdir(parents=True, exist_ok=True)
        ImageGrab.grab(all_screens=True).save(path)
        return True
    except Exception as exc:  # diagnostics only: never fail the probe here
        print("  no screenshot:", exc)
        return False


screenshot_dir = None
"""Folder for screenshots of renders that time out (``--screenshots``)."""


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
    process = subprocess.Popen(
        [executable, *arguments],
        cwd=job.directory,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        startupinfo=background_startupinfo(executable),
    )
    try:
        output, _ = process.communicate(timeout=timeout)
        print(f"exit status: {process.returncode}")
        if output.strip():
            print("printed:", output.decode("utf-8", "replace").strip()[-2000:])
    except subprocess.TimeoutExpired:
        print(f"TIMEOUT after {timeout} s (a dialog may be waiting for an answer)")
        for line in window_texts(process.pid):
            print("  window:", line)
        if screenshot_dir is not None:
            shot = screenshot_dir / f"probe-{name}.png"
            if save_screenshot(shot):
                print("  screenshot:", shot)
        process.kill()
        process.communicate()
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
    parser.add_argument("--screenshots", help="folder for screenshots of renders that time out")
    args = parser.parse_args(argv)
    global screenshot_dir
    if args.screenshots:
        from pathlib import Path

        screenshot_dir = Path(args.screenshots)
    print(f"Python {sys.version.split()[0]} on {sys.platform}")
    executable = find_povray(args.povray)
    print("executable:", executable)
    print("POV-Ray for Windows:", is_windows_engine(executable))
    print("version:", povray_version(executable))
    print("include directories:", [str(d) for d in include_directories(executable)])
    print("missing include files:", missing_includes(INCLUDES, executable))
    if is_windows_engine(executable):
        settings = _engine_settings_file()
        print("settings file:", settings)
        print("keeps a single instance:", settings is None or keeps_single_instance(settings))
        conflict = windows_engine_conflict(executable)
        if conflict:
            print("not rendering:", conflict)
            return 1
    for name, arguments in candidates(executable).items():
        probe(executable, name, arguments, args.timeout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
