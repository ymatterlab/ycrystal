"""Locate the POV-Ray executable and explain its failures in plain language."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

POVRAY_ENV = "YCRYSTAL_POVRAY"

INSTALL_HINT = (
    "Install POV-Ray (Linux Mint: sudo apt install povray), choose the executable with "
    "Render > Set POV-Ray Executable…, or set the environment variable "
    f"{POVRAY_ENV}=/path/to/povray. Viewing and exporting .pov/.ini files work without it."
)


class PovrayNotFoundError(RuntimeError):
    """No usable POV-Ray executable was found."""


def find_povray(configured: str | os.PathLike[str] | None = None) -> str:
    """Return the POV-Ray executable path.

    Precedence: ``configured`` (e.g. the GUI setting), then ``$YCRYSTAL_POVRAY``, then
    ``povray`` on ``PATH``. Raises :class:`PovrayNotFoundError` with guidance.
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
    """Return the version string reported by ``povray --version`` (e.g. ``3.7.0.10``)."""
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
        "POV-Ray could not find a required include file. Check the POV-Ray include "
        "library path (Library_Path) of this installation.",
    ),
)


def explain_failure(returncode: int | None, log: str) -> str:
    """Turn POV-Ray's exit status and output into a readable message."""
    for pattern, message in _KNOWN_FAILURES:
        if pattern.search(log):
            return message
    tail = "\n".join(line for line in log.strip().splitlines()[-12:])
    status = "was stopped" if returncode is None else f"exited with code {returncode}"
    return f"POV-Ray {status}. Last output:\n{tail}" if tail else f"POV-Ray {status}."
