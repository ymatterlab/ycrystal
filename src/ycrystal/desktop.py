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

- ``Ycrystal (development).lnk`` in the user's Start-menu folder of programs: it starts
  the environment's ``pythonw.exe`` (no console window) with ``-m ycrystal.app`` and
  carries the application id of installations from source, so that the running window
  can be pinned to the taskbar;
- ``ycrystal.ico`` in ``%LOCALAPPDATA%\Y-Matter Lab\Ycrystal``, drawn from the SVG icon;
- the file type ``Ycrystal.Project`` for ``*.ycrystal`` projects in
  ``HKEY_CURRENT_USER\Software\Classes``, so that projects open in Ycrystal from File
  Explorer.

These belong to the installation from source only. The packaged Ycrystal (the Windows
installer, ``packaging/windows``) has its own shortcut ``Ycrystal``, application id,
and file type, written and removed by its installer; ``--install-desktop`` refuses to
run in it ([`is_packaged`][ycrystal.desktop.is_packaged]). Each side removes only what
it wrote, and the source installation never takes the opening of ``.ycrystal`` files
from another program, so either can be uninstalled without harming the other.

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


def is_packaged(frozen: bool | None = None) -> bool:
    """Return whether this is the packaged Ycrystal (built by PyInstaller), not a source install.

    Parameters
    ----------
    frozen
        The answer to give; ``None`` asks the running program (``sys.frozen``, set by
        PyInstaller).
    """
    if frozen is None:
        frozen = bool(getattr(sys, "frozen", False))
    return frozen


PACKAGED_MENU_MESSAGE = (
    "This is the installed Ycrystal: its installer manages its Start-menu entry and the "
    ".ycrystal file type, and its uninstaller (Settings > Apps) removes them. "
    "--install-desktop and --uninstall-desktop apply to installations from source."
)
"""Explanation printed when ``--install-desktop`` is run in the packaged program."""


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
"""Name of the file type of ``.ycrystal`` projects in the Windows registry (source install).

The packaged Ycrystal registers its own, ``YMatterLab.Ycrystal.Project``.
"""

CLASSES_KEY = r"Software\Classes"
"""Registry key, under ``HKEY_CURRENT_USER``, of the current user's file types."""

SHORTCUT_NAME = "Ycrystal (development).lnk"
"""File name of the Start-menu shortcut of an installation from source.

``Ycrystal.lnk`` is the packaged program's; the source installation does not use it.
"""

LEGACY_SHORTCUT_NAME = "Ycrystal.lnk"
"""File name the source installation's shortcut had before the packaged installer existed.

[`install_start_menu`][ycrystal.desktop.install_start_menu] and
[`uninstall_start_menu`][ycrystal.desktop.uninstall_start_menu] remove such a shortcut
only if it starts Python with ``-m ycrystal.app``
([`is_source_shortcut`][ycrystal.desktop.is_source_shortcut]): the packaged program's
shortcut of the same name is left alone.
"""

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


def _class_view(classes: str) -> tuple[int, str]:
    r"""Return where File Explorer looks up file types: ``HKEY_CLASSES_ROOT``.

    That view merges the user's types (``HKEY_CURRENT_USER\Software\Classes``) with the
    computer's, so a type that another installation registered for all users counts.
    Tests with their own `classes` key read that key instead.
    """
    import winreg

    if classes == CLASSES_KEY:
        return winreg.HKEY_CLASSES_ROOT, ""
    return winreg.HKEY_CURRENT_USER, f"{classes}\\"


def project_type_handler(classes: str | None = None) -> str | None:
    """Return the file type that ``.ycrystal`` files open with, if it is registered.

    The default value of ``.ycrystal``, as File Explorer sees it; ``None`` if there is
    none, or if it names a file type that no longer exists.
    """
    import winreg

    root, prefix = _class_view(classes or CLASSES_KEY)
    try:
        with winreg.OpenKey(root, f"{prefix}.ycrystal") as key:
            value, _ = winreg.QueryValueEx(key, "")
        if not isinstance(value, str) or not value:
            return None
        with winreg.OpenKey(root, f"{prefix}{value}"):
            return value
    except OSError:
        return None


def register_project_type(command_line: str, icon: Path, classes: str | None = None) -> bool:
    r"""Register ``.ycrystal`` projects for the current user, to open with `command_line`.

    Writes the file type [`WINDOWS_PROG_ID`][ycrystal.desktop.WINDOWS_PROG_ID] (name,
    icon, and ``shell\open\command``) and adds it to the *Open with* list of
    ``.ycrystal``, under ``HKEY_CURRENT_USER\<classes>`` (``None``:
    [`CLASSES_KEY`][ycrystal.desktop.CLASSES_KEY]). It becomes the program that opens
    ``.ycrystal`` files only if no other one does
    ([`project_type_handler`][ycrystal.desktop.project_type_handler]): an installed
    packaged Ycrystal keeps opening them. An application that the user chose in Windows'
    *Open with* dialog also stays their choice.

    Returns
    -------
    bool
        Whether ``.ycrystal`` files now open with this registration.
    """
    import winreg

    classes = classes or CLASSES_KEY

    def write(path: str, name: str, value: str) -> None:
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, rf"{classes}\{path}") as key:
            winreg.SetValueEx(key, name, 0, winreg.REG_SZ, value)

    handler = project_type_handler(classes)
    write(WINDOWS_PROG_ID, "", "Ycrystal project")
    write(rf"{WINDOWS_PROG_ID}\DefaultIcon", "", f"{icon},0")
    write(rf"{WINDOWS_PROG_ID}\shell\open\command", "", command_line)
    owner = handler in (None, WINDOWS_PROG_ID)
    if owner:
        write(".ycrystal", "", WINDOWS_PROG_ID)
    write(r".ycrystal\OpenWithProgids", WINDOWS_PROG_ID, "")
    _notify_file_types()
    return owner


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
        The shortcut and the icon file. Existing ones are replaced. A shortcut of the
        old name ``Ycrystal.lnk`` that an installation from source wrote is removed
        ([`LEGACY_SHORTCUT_NAME`][ycrystal.desktop.LEGACY_SHORTCUT_NAME]).
    """
    from ycrystal.gui.native import WINDOWS_APP_ID
    from ycrystal.windows_shortcut import programs_folder, write_shortcut

    program, arguments = command or windows_launch_command()
    menu = folder or programs_folder()
    icon = write_windows_icon((data or windows_data_folder()) / f"{DESKTOP_ID}.ico")
    shortcut = write_shortcut(
        menu / SHORTCUT_NAME,
        program,
        arguments,
        working_directory=Path.home(),
        icon=icon,
        description="Ycrystal from its source folder (developer installation)",
        app_id=WINDOWS_APP_ID,
    )
    legacy = menu / LEGACY_SHORTCUT_NAME
    if is_source_shortcut(legacy):
        legacy.unlink()
    register_project_type(f'"{program}" {arguments} "%1"', icon, classes)
    return [shortcut, icon]


def is_source_shortcut(path: Path) -> bool:
    """Return whether a shortcut starts Ycrystal from source (Python with ``-m ycrystal.app``).

    Such shortcuts are the ones ``--install-desktop`` writes; the packaged program's
    shortcut starts ``Ycrystal.exe`` and is never one of them. A missing or unreadable
    file is not one either.
    """
    from ycrystal.windows_shortcut import read_shortcut

    if not path.is_file():
        return False
    try:
        shortcut = read_shortcut(path)
    except OSError:
        return False
    program = Path(shortcut.target.replace("\\", "/")).name.lower()
    return program in ("python.exe", "pythonw.exe") and "-m ycrystal.app" in shortcut.arguments


def uninstall_start_menu(
    folder: Path | None = None, data: Path | None = None, classes: str | None = None
) -> list[Path]:
    """Remove what [`install_start_menu`][ycrystal.desktop.install_start_menu] added.

    Shortcuts are removed only if they start Ycrystal from source
    ([`is_source_shortcut`][ycrystal.desktop.is_source_shortcut]), and only this
    installation's file type is removed
    ([`unregister_project_type`][ycrystal.desktop.unregister_project_type]): a packaged
    Ycrystal stays intact.

    Returns
    -------
    list of pathlib.Path
        The files that existed and were removed.
    """
    from ycrystal.windows_shortcut import programs_folder

    menu = folder or programs_folder()
    removed = []
    for path in (menu / SHORTCUT_NAME, menu / LEGACY_SHORTCUT_NAME):
        if is_source_shortcut(path):
            path.unlink()
            removed.append(path)
    icon = (data or windows_data_folder()) / f"{DESKTOP_ID}.ico"
    if icon.is_file():
        icon.unlink()
        removed.append(icon)
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
            "Ycrystal (development) is now in the Start menu, and .ycrystal projects open "
            "with it from File Explorer, unless an installed Ycrystal or another program "
            "already opens them (then it is in their Open with menu)."
        )
    return "Ycrystal is now in the applications menu (Science)."
