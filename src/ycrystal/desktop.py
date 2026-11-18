r"""Desktop integration on Linux and Windows: menu entry, icon, and project file type.

``ycrystal --install-desktop`` installs, for the current user only (no ``sudo``, no
administrator rights), the entry of the system's applications menu
([`install_menu_entry`][ycrystal.desktop.install_menu_entry]);
``ycrystal --uninstall-desktop`` removes it. macOS has no such entry yet.

On Linux it writes:

- ``$XDG_DATA_HOME/applications/ycrystal.desktop``: the launcher shown in the Linux
  Mint menu (category *Science*). It starts the ``ycrystal`` command of the
  environment it was installed from, by absolute path, and opens files passed to it;
- ``$XDG_DATA_HOME/icons/hicolor/scalable/apps/ycrystal.svg``: the icon;
- ``$XDG_DATA_HOME/mime/packages/ycrystal.xml``: the file type
  ``application/x-ycrystal-project`` for ``*.ycrystal`` projects, so that projects open
  in Ycrystal from the file manager.

``$XDG_DATA_HOME`` defaults to ``~/.local/share``. The desktop and MIME databases are
refreshed when ``update-desktop-database`` and ``update-mime-database`` exist.

On Windows ([`install_start_menu`][ycrystal.desktop.install_start_menu]):

- ``Ycrystal.lnk`` in the user's Start-menu folder of programs: it starts the
  environment's ``pythonw.exe`` (no console window) with ``-m ycrystal.app`` and carries
  Ycrystal's application id, so that the running window can be pinned to the taskbar;
- ``ycrystal.ico`` in ``%LOCALAPPDATA%\Y-Matter Lab\Ycrystal``, drawn from the SVG icon;
- the file type ``Ycrystal.Project`` for ``*.ycrystal`` projects in
  ``HKEY_CURRENT_USER\Software\Classes``, so that projects open in Ycrystal from File
  Explorer.

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


def desktop_supported(platform: str = sys.platform) -> bool:
    """Return whether ``--install-desktop`` can add Ycrystal to this system's menu.

    True on Linux and other Unix desktops (a freedesktop launcher) and on Windows (a
    Start-menu shortcut); false on macOS, whose applications are bundles (none is
    installed there yet).
    """
    return platform != "darwin"


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
    # Desktops reload icons when the theme folder's modification time changes; replacing
    # the icon file in place leaves that time alone, so an updated icon would stay hidden.
    theme = base / "icons" / "hicolor"
    if theme.is_dir():
        theme.touch()
        if (theme / "icon-theme.cache").is_file() and shutil.which("gtk-update-icon-cache"):
            subprocess.run(
                ["gtk-update-icon-cache", "-f", "-t", str(theme)],
                capture_output=True,
                check=False,
                timeout=60,
            )


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


# ----- Windows: Start menu, icon, and project file type --------------------------------------

WINDOWS_PROG_ID = "Ycrystal.Project"
"""Name of the file type of ``.ycrystal`` projects in the Windows registry."""

CLASSES_KEY = r"Software\Classes"
"""Registry key, under ``HKEY_CURRENT_USER``, of the current user's file types."""

SHORTCUT_NAME = "Ycrystal.lnk"
"""File name of the Start-menu shortcut."""

ICON_SIZES = (16, 20, 24, 32, 40, 48, 64, 256)
"""Pixel sizes drawn into the Windows icon file (taskbar, Start menu, File Explorer)."""


def windows_data_folder() -> Path:
    r"""Return the folder for the Windows icon file: ``%LOCALAPPDATA%\Y-Matter Lab\Ycrystal``.

    Qt's generic data location (the local application data of the current user) with
    the organisation and application names.
    """
    from PySide6.QtCore import QStandardPaths

    base = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.GenericDataLocation)
    return Path(base) / "Y-Matter Lab" / "Ycrystal"


def windows_launch_command(
    executable: str | None = None, in_venv: bool | None = None
) -> tuple[str, str]:
    r"""Return the program and the arguments that start Ycrystal without a console window.

    The program is ``pythonw.exe`` next to the interpreter (in a virtual environment
    ``.venv\Scripts\pythonw.exe``), or the interpreter itself if there is none. It runs
    ``-m ycrystal.app``; in a virtual environment also with ``-I``, so that a
    ``ycrystal`` module in the folder it starts in (the folder of an opened project)
    cannot take the package's place. The path is not resolved, so that the virtual
    environment stays in use.

    Parameters
    ----------
    executable
        The interpreter; ``None`` uses the running one.
    in_venv
        Whether it belongs to a virtual environment; ``None`` asks the running one.
    """
    executable = executable or sys.executable
    if in_venv is None:
        in_venv = sys.prefix != sys.base_prefix
    program = Path(executable).with_name("pythonw.exe")
    if not program.is_file():
        program = Path(executable)
    arguments = "-I -m ycrystal.app" if in_venv else "-m ycrystal.app"
    return str(program.absolute()), arguments


def write_windows_icon(path: Path, sizes: tuple[int, ...] = ICON_SIZES) -> Path:
    """Draw the application icon ([`icon_path`][ycrystal.desktop.icon_path]) into an ``.ico``.

    Each size is drawn from the SVG by Qt, not scaled from a larger picture, and stored
    by Pillow. The folder is created if needed; an existing file is replaced.
    """
    from io import BytesIO

    from PIL import Image
    from PySide6.QtCore import QBuffer, QByteArray, QIODevice, Qt
    from PySide6.QtGui import QImage, QPainter
    from PySide6.QtSvg import QSvgRenderer

    renderer = QSvgRenderer(str(icon_path()))
    if not renderer.isValid():
        raise OSError(f"Cannot read the application icon {icon_path()}")
    pictures = []
    for size in sorted(sizes):
        image = QImage(size, size, QImage.Format.Format_ARGB32)
        image.fill(Qt.GlobalColor.transparent)
        painter = QPainter(image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        renderer.render(painter)
        painter.end()
        data = QByteArray()
        buffer = QBuffer(data)
        buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        image.save(buffer, "PNG")
        buffer.close()
        pictures.append(Image.open(BytesIO(bytes(data))).convert("RGBA"))
    path.parent.mkdir(parents=True, exist_ok=True)
    largest = pictures[-1]
    largest.save(path, format="ICO", sizes=[p.size for p in pictures], append_images=pictures[:-1])
    return path


def _notify_file_types() -> None:
    """Tell File Explorer that file types changed (``SHChangeNotify``)."""
    import ctypes

    ctypes.WinDLL("shell32").SHChangeNotify(0x08000000, 0, None, None)  # SHCNE_ASSOCCHANGED


def register_project_type(command_line: str, icon: Path, classes: str | None = None) -> None:
    r"""Register ``.ycrystal`` projects for the current user, to open with `command_line`.

    Writes the file type [`WINDOWS_PROG_ID`][ycrystal.desktop.WINDOWS_PROG_ID] (name,
    icon, and ``shell\open\command``) and points ``.ycrystal`` to it, under
    ``HKEY_CURRENT_USER\<classes>`` (``None``:
    [`CLASSES_KEY`][ycrystal.desktop.CLASSES_KEY]). An application that the user chose
    for these files in Windows' *Open with* dialog stays their choice.
    """
    import winreg

    classes = classes or CLASSES_KEY

    def write(path: str, name: str, value: str) -> None:
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, rf"{classes}\{path}") as key:
            winreg.SetValueEx(key, name, 0, winreg.REG_SZ, value)

    write(WINDOWS_PROG_ID, "", "Ycrystal project")
    write(rf"{WINDOWS_PROG_ID}\DefaultIcon", "", f"{icon},0")
    write(rf"{WINDOWS_PROG_ID}\shell\open\command", "", command_line)
    write(".ycrystal", "", WINDOWS_PROG_ID)
    write(r".ycrystal\OpenWithProgids", WINDOWS_PROG_ID, "")
    _notify_file_types()


def _delete_key_tree(path: str) -> bool:
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path, 0, winreg.KEY_ALL_ACCESS) as key:
            while True:
                try:
                    child = winreg.EnumKey(key, 0)
                except OSError:
                    break
                _delete_key_tree(rf"{path}\{child}")
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, path)
    except FileNotFoundError:
        return False
    return True


def _delete_key_if_empty(path: str) -> None:
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path) as key:
            subkeys, values, _ = winreg.QueryInfoKey(key)
        if subkeys == 0 and values == 0:
            winreg.DeleteKey(winreg.HKEY_CURRENT_USER, path)
    except OSError:
        pass


def unregister_project_type(classes: str | None = None) -> bool:
    r"""Remove what [`register_project_type`][ycrystal.desktop.register_project_type] wrote.

    The ``.ycrystal`` key is removed only where it points to Ycrystal and holds nothing
    else.

    Returns
    -------
    bool
        Whether the file type was registered.
    """
    import winreg

    classes = classes or CLASSES_KEY
    removed = _delete_key_tree(rf"{classes}\{WINDOWS_PROG_ID}")
    extension = rf"{classes}\.ycrystal"
    for path, name, expected in (
        (rf"{extension}\OpenWithProgids", WINDOWS_PROG_ID, None),
        (extension, "", WINDOWS_PROG_ID),
    ):
        try:
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER, path, 0, winreg.KEY_QUERY_VALUE | winreg.KEY_SET_VALUE
            ) as key:
                value, _ = winreg.QueryValueEx(key, name)
                if expected is None or value == expected:
                    winreg.DeleteValue(key, name)
        except OSError:
            pass
        _delete_key_if_empty(path)
    _notify_file_types()
    return removed


def install_start_menu(
    folder: Path | None = None,
    data: Path | None = None,
    classes: str | None = None,
    command: tuple[str, str] | None = None,
) -> list[Path]:
    """Add Ycrystal to the Windows Start menu and register ``.ycrystal`` projects.

    Parameters
    ----------
    folder
        Start-menu folder; ``None`` uses the current user's
        ([`programs_folder`][ycrystal.windows_shortcut.programs_folder]).
    data
        Folder of the icon file; ``None`` uses
        [`windows_data_folder`][ycrystal.desktop.windows_data_folder].
    classes
        Registry key of the file types; ``None`` uses
        [`CLASSES_KEY`][ycrystal.desktop.CLASSES_KEY] (tests use another one).
    command
        Program and arguments; ``None`` uses
        [`windows_launch_command`][ycrystal.desktop.windows_launch_command].

    Returns
    -------
    list of pathlib.Path
        The shortcut and the icon file. Existing ones are replaced.
    """
    from ycrystal.gui.native import WINDOWS_APP_ID
    from ycrystal.windows_shortcut import programs_folder, write_shortcut

    program, arguments = command or windows_launch_command()
    icon = write_windows_icon((data or windows_data_folder()) / f"{DESKTOP_ID}.ico")
    shortcut = write_shortcut(
        (folder or programs_folder()) / SHORTCUT_NAME,
        program,
        arguments,
        working_directory=Path.home(),
        icon=icon,
        description="Prepare crystal-structure figures and render them with POV-Ray",
        app_id=WINDOWS_APP_ID,
    )
    register_project_type(f'"{program}" {arguments} "%1"', icon, classes)
    return [shortcut, icon]


def uninstall_start_menu(
    folder: Path | None = None, data: Path | None = None, classes: str | None = None
) -> list[Path]:
    """Remove what [`install_start_menu`][ycrystal.desktop.install_start_menu] added.

    Returns
    -------
    list of pathlib.Path
        The files that existed and were removed (the file type is removed too).
    """
    from ycrystal.windows_shortcut import programs_folder

    removed = []
    for path in (
        (folder or programs_folder()) / SHORTCUT_NAME,
        (data or windows_data_folder()) / f"{DESKTOP_ID}.ico",
    ):
        if path.is_file():
            path.unlink()
            removed.append(path)
    unregister_project_type(classes)
    return removed


def install_menu_entry(platform: str | None = None) -> list[Path]:
    """Add Ycrystal to this system's applications menu, for the current user.

    [`install_start_menu`][ycrystal.desktop.install_start_menu] on Windows,
    [`install_desktop`][ycrystal.desktop.install_desktop] elsewhere; check
    [`desktop_supported`][ycrystal.desktop.desktop_supported] first.

    Parameters
    ----------
    platform
        ``sys.platform`` value to decide for; ``None`` uses the running system.
    """
    if (platform or sys.platform) == "win32":
        return install_start_menu()
    return install_desktop()


def uninstall_menu_entry(platform: str | None = None) -> list[Path]:
    """Remove what [`install_menu_entry`][ycrystal.desktop.install_menu_entry] added."""
    if (platform or sys.platform) == "win32":
        return uninstall_start_menu()
    return uninstall_desktop()


def menu_entry_note(platform: str | None = None) -> str:
    """Return the sentence ``--install-desktop`` prints after installing.

    >>> menu_entry_note("linux")
    'Ycrystal is now in the applications menu (Science).'
    """
    if (platform or sys.platform) == "win32":
        return (
            "Ycrystal is now in the Start menu, and .ycrystal projects open with it from "
            "File Explorer."
        )
    return "Ycrystal is now in the applications menu (Science)."
