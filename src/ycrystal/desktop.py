"""Desktop integration on Linux: menu launcher, icon, and project file type.

``ycrystal --install-desktop`` writes, for the current user only (no ``sudo``):

- ``$XDG_DATA_HOME/applications/ycrystal.desktop``: the launcher shown in the Linux
  Mint menu (category *Science*). It starts the ``ycrystal`` command of the
  environment it was installed from, by absolute path, and opens files passed to it;
- ``$XDG_DATA_HOME/icons/hicolor/scalable/apps/ycrystal.svg``: the icon;
- ``$XDG_DATA_HOME/mime/packages/ycrystal.xml``: the file type
  ``application/x-ycrystal-project`` for ``*.ycrystal`` projects, so that projects open
  in Ycrystal from the file manager.

``$XDG_DATA_HOME`` defaults to ``~/.local/share``. The desktop and MIME databases are
refreshed when ``update-desktop-database`` and ``update-mime-database`` exist.
``ycrystal --uninstall-desktop`` removes the three files again.

Examples
--------
>>> from ycrystal.desktop import desktop_entry
>>> entry = desktop_entry("/opt/ycrystal/.venv/bin/ycrystal")
>>> 'Exec="/opt/ycrystal/.venv/bin/ycrystal" %f' in entry
True
>>> "MimeType=application/x-ycrystal-project;" in entry
True
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from importlib import resources
from pathlib import Path

DESKTOP_ID = "ycrystal"
"""Name of the launcher, icon, and MIME files (``ycrystal.desktop`` …)."""

PROJECT_MIME_TYPE = "application/x-ycrystal-project"
"""MIME type registered for ``.ycrystal`` project files."""

_MIME_XML = """<?xml version="1.0" encoding="UTF-8"?>
<mime-info xmlns="http://www.freedesktop.org/standards/shared-mime-info">
  <mime-type type="application/x-ycrystal-project">
    <comment>Ycrystal project</comment>
    <sub-class-of type="application/json"/>
    <generic-icon name="ycrystal"/>
    <glob pattern="*.ycrystal"/>
  </mime-type>
</mime-info>
"""


def data_home() -> Path:
    """Return ``$XDG_DATA_HOME`` or ``~/.local/share``."""
    value = os.environ.get("XDG_DATA_HOME")
    return Path(value) if value else Path.home() / ".local" / "share"


def launcher_installed() -> bool:
    """Return whether a ``ycrystal.desktop`` launcher exists (user or system menu)."""
    dirs = [data_home()] + [
        Path(d) for d in os.environ.get("XDG_DATA_DIRS", "/usr/local/share:/usr/share").split(":")
    ]
    return any((d / "applications" / f"{DESKTOP_ID}.desktop").is_file() for d in dirs if d)


def icon_path() -> Path:
    """Return the packaged application icon (SVG)."""
    return Path(str(resources.files("ycrystal.resources").joinpath("ycrystal.svg")))


def ycrystal_command() -> str:
    """Return the absolute path of this environment's ``ycrystal`` command.

    The console script next to the running interpreter (for example
    ``.venv/bin/ycrystal``); if it does not exist, ``python -m ycrystal.app`` with the
    running interpreter. The path is not resolved, so a virtual environment stays in
    use.
    """
    script = Path(sys.executable).parent / "ycrystal"
    if script.is_file():
        return str(script.absolute())
    return f"{Path(sys.executable).absolute()} -m ycrystal.app"


def desktop_entry(command: str) -> str:
    """Return the text of the ``.desktop`` launcher that runs ``command``.

    The command is quoted when it is a single path; files from the file manager are
    passed as ``%f``.
    """
    exec_line = f'"{command}"' if " -m " not in command else command
    return "\n".join(
        [
            "[Desktop Entry]",
            "Type=Application",
            "Version=1.5",
            "Name=Ycrystal",
            "GenericName=Crystal Structure Figures",
            "Comment=Prepare crystal-structure figures and render them with POV-Ray",
            f"Exec={exec_line} %f",
            "Icon=ycrystal",
            "Terminal=false",
            "Categories=Science;Physics;Chemistry;DataVisualization;",
            "Keywords=crystal;structure;POV-Ray;CIF;POSCAR;VASP;Quantum ESPRESSO;",
            f"MimeType={PROJECT_MIME_TYPE};",
            "StartupWMClass=ycrystal",
            "",
        ]
    )


def _targets(base: Path) -> dict[str, Path]:
    return {
        "launcher": base / "applications" / f"{DESKTOP_ID}.desktop",
        "icon": base / "icons" / "hicolor" / "scalable" / "apps" / f"{DESKTOP_ID}.svg",
        "mime": base / "mime" / "packages" / f"{DESKTOP_ID}.xml",
    }


def _refresh(base: Path) -> None:
    for tool, folder in (
        ("update-desktop-database", base / "applications"),
        ("update-mime-database", base / "mime"),
    ):
        if shutil.which(tool) and folder.is_dir():
            subprocess.run([tool, str(folder)], capture_output=True, check=False, timeout=60)


def install_desktop(base: Path | None = None, command: str | None = None) -> list[Path]:
    """Install the launcher, icon, and project file type for the current user.

    Parameters
    ----------
    base
        Data directory; ``None`` uses [`data_home`][ycrystal.desktop.data_home].
    command
        Command the launcher runs; ``None`` uses
        [`ycrystal_command`][ycrystal.desktop.ycrystal_command].

    Returns
    -------
    list of pathlib.Path
        The written files. Existing files of the same name are replaced.
    """
    base = base or data_home()
    targets = _targets(base)
    for path in targets.values():
        path.parent.mkdir(parents=True, exist_ok=True)
    targets["launcher"].write_text(desktop_entry(command or ycrystal_command()), encoding="utf-8")
    shutil.copyfile(icon_path(), targets["icon"])
    targets["mime"].write_text(_MIME_XML, encoding="utf-8")
    _refresh(base)
    return list(targets.values())


def uninstall_desktop(base: Path | None = None) -> list[Path]:
    """Remove the files written by [`install_desktop`][ycrystal.desktop.install_desktop].

    Returns
    -------
    list of pathlib.Path
        The files that existed and were removed.
    """
    base = base or data_home()
    removed = []
    for path in _targets(base).values():
        if path.is_file():
            path.unlink()
            removed.append(path)
    _refresh(base)
    return removed
