"""The few places where the interface depends on the operating system.

Keep platform checks here, so that the rest of the interface stays the same on Linux,
macOS, and Windows.
"""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QSettings, QStandardPaths

THUMBNAIL_FOLDER = "material-thumbnails"
"""Name of the folder that holds the thumbnails of personal materials."""

WINDOWS_APP_ID = "YMatterLab.Ycrystal"
"""Application id (AppUserModelID) of Ycrystal installed from source on Windows.

Its Start-menu entry ``Ycrystal (development)`` (``ycrystal --install-desktop``) carries
the same id, so that the window's taskbar button belongs to that entry.
"""

WINDOWS_PACKAGED_APP_ID = "YMatterLab.Ycrystal.App"
"""Application id of the packaged Ycrystal (the Windows installer's ``Ycrystal.exe``).

Different from [`WINDOWS_APP_ID`][ycrystal.gui.native.WINDOWS_APP_ID], so that both
installations can be on one computer: each window groups under its own Start-menu
entry, and pinning one never starts the other. The installer's shortcut
(``packaging/windows/ycrystal.iss``) carries this id.
"""


def windows_app_id(frozen: bool | None = None) -> str:
    """Return the application id of this installation of Ycrystal.

    Parameters
    ----------
    frozen
        Whether this is the packaged program; ``None`` asks the running one
        ([`is_packaged`][ycrystal.desktop.is_packaged]).

    Examples
    --------
    >>> windows_app_id(frozen=False), windows_app_id(frozen=True)
    ('YMatterLab.Ycrystal', 'YMatterLab.Ycrystal.App')
    """
    from ycrystal.desktop import is_packaged

    return WINDOWS_PACKAGED_APP_ID if is_packaged(frozen) else WINDOWS_APP_ID


def painting_platform(platform: str = sys.platform) -> str | None:
    """Return the Qt platform plug-in for drawing text without a window, or ``None``.

    The command line draws the element legend
    ([`ycrystal.render.legend`][ycrystal.render.legend]) without opening a window. On
    Linux and macOS the ``offscreen`` plug-in finds the installed fonts (fontconfig,
    Core Text) and needs no display, so rendering works over SSH and on servers. On
    Windows it may not find the system fonts, so the native plug-in is kept (``None``);
    it opens no window either.

    Examples
    --------
    >>> painting_platform("linux"), painting_platform("darwin"), painting_platform("win32")
    ('offscreen', 'offscreen', None)
    """
    return None if platform == "win32" else "offscreen"


def set_taskbar_identity(platform: str = sys.platform, frozen: bool | None = None) -> bool:
    """Give Ycrystal its own taskbar button and icon on Windows.

    Installed from source, Ycrystal runs in the Python interpreter, so Windows would
    group its window under Python's taskbar button and show Python's icon. An explicit
    application id ([`windows_app_id`][ycrystal.gui.native.windows_app_id]) makes the
    taskbar use the window's own icon, and ties the window to its Start-menu entry. Call
    it before the first window is shown. Does nothing on other systems (Linux uses the
    desktop file name, macOS has no equivalent without an application bundle).

    Parameters
    ----------
    platform
        ``sys.platform`` value to decide for; the default is the running system.
    frozen
        Whether this is the packaged program; ``None`` asks the running one.

    Returns
    -------
    bool
        Whether the id was set.
    """
    if platform != "win32":
        return False
    try:
        import ctypes

        shell32 = ctypes.WinDLL("shell32")
        app_id = windows_app_id(frozen)
        return shell32.SetCurrentProcessExplicitAppUserModelID(app_id) == 0  # S_OK
    except (OSError, AttributeError):
        return False


def executable_filter(platform: str = sys.platform) -> str:
    """Return the file-dialog filter for choosing a program such as POV-Ray.

    Windows programs are ``.exe`` files (POV-Ray for Windows: ``pvengine64.exe``);
    elsewhere a program has no particular extension, so every file is listed.

    Examples
    --------
    >>> executable_filter("linux")
    ''
    >>> executable_filter("win32")
    'Programs (*.exe);;All files (*)'
    """
    return "Programs (*.exe);;All files (*)" if platform == "win32" else ""


def native_keys(text: str, platform: str = sys.platform) -> str:
    """Return a help text with the modifier key named as this platform shows it.

    Qt maps ``Ctrl`` in shortcuts and mouse modifiers to the Command key on macOS (where
    Control + click is a right click), so texts written with "Ctrl" read "⌘" there.

    Parameters
    ----------
    text
        Text that names shortcuts with "Ctrl", for example a tooltip.
    platform
        ``sys.platform`` value to format for; the default is the running system.

    Examples
    --------
    >>> native_keys("Undo (Ctrl+Z)", "linux")
    'Undo (Ctrl+Z)'
    >>> native_keys("Undo (Ctrl+Z)", "darwin")
    'Undo (⌘+Z)'
    """
    return text.replace("Ctrl", "⌘") if platform == "darwin" else text


def personal_thumbnail_directory(settings: QSettings, platform: str = sys.platform) -> Path:
    """Return the folder for the thumbnails of personal materials.

    On Linux the settings are a file in Ycrystal's own configuration folder
    (``~/.config/Y-Matter Lab``), and the thumbnails are kept next to it. The native
    settings of macOS (a property list in the shared ``~/Library/Preferences``) and of
    Windows (the registry) have no such folder; there Qt's application data location is
    used (macOS: ``~/Library/Application Support/Y-Matter Lab/Ycrystal``).

    Parameters
    ----------
    settings
        The application's settings. Settings stored as an INI file (as in the tests) keep
        the thumbnails next to that file on every platform.
    platform
        ``sys.platform`` value to decide for; the default is the running system.

    Returns
    -------
    pathlib.Path
        The folder; it is not created.
    """
    native = settings.format() == QSettings.Format.NativeFormat
    if native and platform in ("darwin", "win32"):
        base = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation)
        return Path(base) / THUMBNAIL_FOLDER
    return Path(settings.fileName()).parent / THUMBNAIL_FOLDER
