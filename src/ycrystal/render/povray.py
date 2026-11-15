"""Locate the POV-Ray executable and explain its failures in plain language."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

POVRAY_ENV = "YCRYSTAL_POVRAY"
"""Environment variable that names the POV-Ray executable."""

INSTALL_HINT = (
    "Install POV-Ray (Linux Mint: sudo apt install povray), choose the executable with "
    "Render > Set POV-Ray Executable…, or set the environment variable "
    f"{POVRAY_ENV}=/path/to/povray. Viewing and exporting .pov/.ini files work without it."
)
"""Setup guidance appended to every "not found" message."""


class PovrayNotFoundError(RuntimeError):
    """No usable POV-Ray executable was found.

    ``str(error)`` names the place that was checked and includes setup guidance.
    """


def find_povray(configured: str | os.PathLike[str] | None = None) -> str:
    """Return the POV-Ray executable to use.

    The first source that is set decides, in this order: `configured`, the
    environment variable ``YCRYSTAL_POVRAY`` (ignored if empty), then ``povray`` on
    ``PATH``.

    Parameters
    ----------
    configured
        Explicit executable, for example the GUI setting (*Render ▸ Set POV-Ray
        Executable…*) or ``ycrystal --check-renderer --povray PATH``. ``~`` is expanded.

    Returns
    -------
    str
        Path of an existing executable file. Whether it is a working POV-Ray is not
        checked; use [`run_self_test`][ycrystal.render.selftest.run_self_test].

    Raises
    ------
    PovrayNotFoundError
        If the deciding source names a missing or non-executable file, or if no
        source is set and ``povray`` is not on ``PATH``.

    Notes
    -----
    A configured or environment path that is invalid raises immediately; the search
    does not fall back to the next source. Nothing is executed.
    """
    for source, candidate in (
        ("the configured POV-Ray path", configured),
        (f"${POVRAY_ENV}", os.environ.get(POVRAY_ENV) or None),
    ):
        if candidate:
            path = Path(candidate).expanduser()
            if path.is_file() and os.access(path, os.X_OK):
                return str(path)
            raise PovrayNotFoundError(
                f"POV-Ray was not found at {path} ({source}); the file is missing or not "
                f"executable. {INSTALL_HINT}"
            )
    found = shutil.which("povray")
    if found:
        return found
    raise PovrayNotFoundError(f"POV-Ray was not found on PATH. {INSTALL_HINT}")


def povray_version(executable: str, timeout: float = 15.0) -> str | None:
    """Return the version that ``povray --version`` reports.

    Runs the executable synchronously.

    Parameters
    ----------
    executable
        POV-Ray executable.
    timeout
        Seconds to wait for the process.

    Returns
    -------
    str or None
        Version string such as ``"3.7.0.10"``; ``None`` if the program cannot be run,
        times out, or prints no recognizable version.
    """
    try:
        result = subprocess.run(
            [executable, "--version"],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    match = re.search(r"POV-Ray\s+(?:v)?(\d[\w.\-+]*)", result.stdout + result.stderr)
    return match.group(1) if match else None


_KNOWN_FAILURES: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(r"Viewing angle has to be smaller than 180"),
        "This POV-Ray build rejects cameras that do not set an angle. Builds compiled "
        "with -ffast-math (added by POV-Ray's configure script for GCC unless "
        "--disable-optimiz is given) misreport unset camera fields this way, which makes "
        "exported cameras unreliable. Use the distribution package (sudo apt install "
        "povray) or rebuild with ./configure --disable-optimiz CXXFLAGS='-O2' ..., then "
        "select that executable.",
    ),
    (
        re.compile(r"I/O restriction|Permission denied|not permitted", re.IGNORECASE),
        "POV-Ray's I/O restrictions (povray.conf) blocked a file access. Ycrystal renders "
        "inside its own temporary job directory; check that the directory is readable "
        "and writable and that povray.conf permits the working directory ('.').",
    ),
    (
        re.compile(r"Cannot open include file|Cannot find file", re.IGNORECASE),
        "POV-Ray could not find a required include file{name}. Materials that use native "
        "POV-Ray identifiers need the standard include files: on Linux Mint/Ubuntu install "
        "them with 'sudo apt install povray-includes', or check the include library path "
        "(Library_Path) of this installation.",
    ),
)

_INCLUDE_NAME = re.compile(r"(?:Cannot open include file|Cannot find file)\s+'?\"?([\w.\-]+)")

INCLUDE_FALLBACK_DIRS = (
    Path("/usr/share/povray-3.7/include"),
    Path("/usr/local/share/povray-3.7/include"),
)
"""Standard include directories searched in addition to ``Library_Path`` entries."""


def include_directories() -> list[Path]:
    """Return the directories where POV-Ray looks for standard include files.

    Reads the ``Library_Path`` entries of the system and user ``povray.ini`` files
    (``/etc/povray/3.7/povray.ini``, ``~/.povray/3.7/povray.ini``) and adds
    [`INCLUDE_FALLBACK_DIRS`][ycrystal.render.povray.INCLUDE_FALLBACK_DIRS]. Only
    existing directories are returned, without duplicates.
    """
    candidates: list[Path] = []
    for ini in (Path("/etc/povray/3.7/povray.ini"), Path.home() / ".povray/3.7/povray.ini"):
        try:
            text = ini.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for line in text.splitlines():
            match = re.match(r"\s*Library_Path\s*=\s*\"?([^\";]+)\"?", line, re.IGNORECASE)
            if match:
                candidates.append(Path(os.path.expanduser(match.group(1).strip())))
    candidates.extend(INCLUDE_FALLBACK_DIRS)
    result: list[Path] = []
    for directory in candidates:
        if directory.is_dir() and directory not in result:
            result.append(directory)
    return result


def missing_includes(names: tuple[str, ...] | list[str]) -> list[str]:
    """Return the include files of ``names`` that none of the include directories has.

    Parameters
    ----------
    names
        Include file names, for example from
        [`required_includes`][ycrystal.render.pov_writer.required_includes].

    Returns
    -------
    list of str
        The missing names, in the given order; empty when all are found.
    """
    directories = include_directories()
    return [name for name in names if not any((d / name).is_file() for d in directories)]


def explain_failure(returncode: int | None, log: str) -> str:
    """Turn POV-Ray's exit status and output into a readable message.

    Parameters
    ----------
    returncode
        Exit status, or ``None`` if the process was stopped or crashed.
    log
        POV-Ray's output.

    Returns
    -------
    str
        An explanation for known problems (a miscompiled build that rejects cameras
        without ``angle``, I/O restrictions, a missing include file); otherwise the
        exit status and the last 12 lines of output.
    """
    for pattern, message in _KNOWN_FAILURES:
        if pattern.search(log):
            if "{name}" in message:
                found = _INCLUDE_NAME.search(log)
                message = message.format(name=f" ({found.group(1).rstrip('.')})" if found else "")
            return message
    tail = "\n".join(line for line in log.strip().splitlines()[-12:])
    status = "was stopped" if returncode is None else f"exited with code {returncode}"
    return f"POV-Ray {status}. Last output:\n{tail}" if tail else f"POV-Ray {status}."
