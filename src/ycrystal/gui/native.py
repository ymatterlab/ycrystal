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
