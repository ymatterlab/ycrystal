"""Locate the POV-Ray executable and explain its failures in plain language.

Two kinds of POV-Ray are supported:

- the command-line program ``povray`` of Linux and macOS (distribution packages,
  Homebrew), which prints its messages and progress;
- POV-Ray for Windows, a window program (``pvengine64.exe``) without a ``povray``
  command. It renders an INI file given on its command line with ``/EXIT`` and quits;
  its messages go to a log file in the job directory (see
  [`render_arguments`][ycrystal.render.povray.render_arguments]).
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from collections.abc import Iterable, Iterator, Mapping
from contextlib import contextmanager
from pathlib import Path
from typing import Any

POVRAY_ENV = "YCRYSTAL_POVRAY"
"""Environment variable that names the POV-Ray executable."""

INSTALL_HINT = (
    "Install POV-Ray (Linux Mint: sudo apt install povray; macOS: brew install povray; "
    "Windows: POV-Ray for Windows 3.7 from povray.org), choose the executable with "
    "Render > Set POV-Ray Executable…, or set the environment variable "
    f"{POVRAY_ENV}=/path/to/povray. Viewing and exporting .pov/.ini files work without it."
)
"""Setup guidance appended to every "not found" message."""

WINDOWS_ENGINES = ("pvengine64.exe", "pvengine.exe", "pvengine32-sse2.exe")
"""Executable names of POV-Ray for Windows, in order of preference."""

WINDOWS_VERSION_FOLDER = "v3.7"
"""Version folder of POV-Ray for Windows 3.7 (``…\\POV-Ray\\v3.7``) in its installation
and its registry key."""

LOG_NAME = "scene.log"
"""Log file that POV-Ray for Windows writes into the job directory."""


class PovrayNotFoundError(RuntimeError):
    """No usable POV-Ray executable was found.

    ``str(error)`` names the place that was checked and includes setup guidance.
    """


def is_windows_engine(executable: str | os.PathLike[str]) -> bool:
    r"""Return whether an executable is POV-Ray for Windows (``pvengine*.exe``).

    >>> is_windows_engine(r"C:\Program Files\POV-Ray\v3.7\bin\pvengine64.exe")
    True
    >>> is_windows_engine("/usr/bin/povray")
    False
    """
    name = str(executable).replace("\\", "/").rsplit("/", 1)[-1]
    return name.lower().startswith("pvengine")


def windows_engine_candidates(
    environ: Mapping[str, str], registry_homes: Iterable[str] = ()
) -> list[Path]:
    r"""Return where POV-Ray for Windows may be installed, most likely first.

    POV-Ray for Windows does not put itself on ``PATH``. Its installer writes its folder
    to the registry (``Software\POV-Ray\v3.7\Windows``, value ``Home``) and installs
    into ``%ProgramFiles%\POV-Ray\v3.7`` by default; the executables are in its
    ``bin`` folder. Nothing is hard-coded but that layout: the folders come from
    `registry_homes` and the ``ProgramFiles`` variables of `environ`.

    >>> paths = windows_engine_candidates({"ProgramFiles": "C:/PF"}, ["D:/POV"])
    >>> names = [p.as_posix() for p in paths]
    >>> names[0], names[3]
    ('D:/POV/bin/pvengine64.exe', 'C:/PF/POV-Ray/v3.7/bin/pvengine64.exe')
    """
    homes = [Path(home) for home in registry_homes if home]
    for variable in ("ProgramW6432", "ProgramFiles", "ProgramFiles(x86)"):
        folder = environ.get(variable)
        if folder:
            homes.append(Path(folder) / "POV-Ray" / WINDOWS_VERSION_FOLDER)
    candidates: list[Path] = []
    for home in homes:
        for name in WINDOWS_ENGINES:
            candidate = home / "bin" / name
            if candidate not in candidates:
                candidates.append(candidate)
    return candidates


def _registry_folders(name: str) -> list[str]:
    r"""Return a folder POV-Ray for Windows recorded in the registry, per user first.

    Reads the value `name` of ``Software\POV-Ray\v3.7\Windows`` in ``HKEY_CURRENT_USER``
    and ``HKEY_LOCAL_MACHINE``; empty on other systems.
    """
    if sys.platform != "win32":
        return []
    import winreg  # pragma: no cover - Windows only

    folders: list[str] = []
    key_name = rf"Software\POV-Ray\{WINDOWS_VERSION_FOLDER}\Windows"
    for root in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        try:
            with winreg.OpenKey(root, key_name) as key:
                value, _ = winreg.QueryValueEx(key, name)
        except OSError:
            continue
        if isinstance(value, str) and value and value not in folders:
            folders.append(value)
    return folders


def _registry_homes() -> list[str]:
    """Return the installation folders (``Home``) POV-Ray for Windows recorded."""
    return _registry_folders("Home")


def _registry_user_folders() -> list[str]:
    r"""Return the folders of the user files (``DocPath``) POV-Ray for Windows recorded.

    Its installer copies the include and INI files there: normally
    ``Documents\POV-Ray\v3.7``, also when the Documents folder has been moved, for
    example into OneDrive.
    """
    return _registry_folders("DocPath")


def installed_windows_engine(platform: str = sys.platform) -> str | None:
    """Return an installed POV-Ray for Windows, or ``None`` (always ``None`` elsewhere).

    Looks on ``PATH`` first, then in the folders of
    [`windows_engine_candidates`][ycrystal.render.povray.windows_engine_candidates].
    """
    if platform != "win32":
        return None
    for name in WINDOWS_ENGINES:
        found = shutil.which(name)
        if found:
            return found
    for candidate in windows_engine_candidates(os.environ, _registry_homes()):
        if candidate.is_file():
            return str(candidate)
    return None


def find_povray(configured: str | os.PathLike[str] | None = None) -> str:
    """Return the POV-Ray executable to use.

    The first source that is set decides, in this order: `configured`, the
    environment variable ``YCRYSTAL_POVRAY`` (ignored if empty), then ``povray`` on
    ``PATH``, and on Windows an installed POV-Ray for Windows
    ([`installed_windows_engine`][ycrystal.render.povray.installed_windows_engine]).

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
        source is set and no POV-Ray is found.

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
    found = shutil.which("povray") or installed_windows_engine()
    if found:
        return found
    where = "on PATH or in the installation folder of POV-Ray for Windows"
    if sys.platform != "win32":
        where = "on PATH"
    raise PovrayNotFoundError(f"POV-Ray was not found {where}. {INSTALL_HINT}")


def render_arguments(executable: str | os.PathLike[str], ini_name: str) -> list[str]:
    """Return the command-line arguments that render an INI file, without the executable.

    ``povray`` takes the INI file alone. POV-Ray for Windows is a window program: it
    gets ``/EXIT`` (quit when the render is done), ``/NR`` (do not reopen the files of
    its last session), and ``+GA`` with [`LOG_NAME`][ycrystal.render.povray.LOG_NAME]
    (write all messages to that file, because it prints nothing).

    >>> render_arguments("/usr/bin/povray", "scene.ini")
    ['scene.ini']
    >>> render_arguments("C:/POV-Ray/v3.7/bin/pvengine64.exe", "scene.ini")
    ['/EXIT', '/NR', '+GAscene.log', 'scene.ini']
    """
    if is_windows_engine(executable):
        return ["/EXIT", "/NR", f"+GA{LOG_NAME}", ini_name]
    return [ini_name]


def background_startupinfo(executable: str | os.PathLike[str]) -> Any:
    """Return ``subprocess`` start-up information that keeps POV-Ray for Windows minimised.

    Its window would otherwise open at full size for every render. Minimised (not
    hidden), it stays reachable from the taskbar, should it ever wait for an answer in
    a dialog. ``None`` for other executables and on other systems.

    Minimising does not stop POV-Ray for Windows from making itself the foreground
    window; see [`hold_foreground`][ycrystal.render.povray.hold_foreground].
    """
    if sys.platform != "win32" or not is_windows_engine(executable):
        return None
    info = subprocess.STARTUPINFO()  # pragma: no cover - Windows only
    info.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    info.wShowWindow = 7  # SW_SHOWMINNOACTIVE: minimised, without taking the focus
    return info


ENGINE_OPEN_MESSAGE = (
    "POV-Ray for Windows is already open (its window may be minimised), and it keeps a "
    "single copy running (its option Options > Keep Single Instance), so it cannot render "
    "for Ycrystal now. Close POV-Ray for Windows, or turn that option off in its Options "
    "menu, and try again."
)
"""Explanation when a POV-Ray for Windows that keeps a single instance is already open."""


def _engine_window_classes(executable: str | os.PathLike[str]) -> tuple[str, ...]:
    """Return the main-window classes that keep a new POV-Ray for Windows from starting.

    POV-Ray for Windows 3.7 looks for its own main window class at start-up
    (``Pov37-Win64-MainWinClass`` in the 64-bit build, ``…-Win32-…`` in the 32-bit
    builds, with an ``Unofficial-`` prefix in builds of others).
    """
    name = str(executable).replace("\\", "/").rsplit("/", 1)[-1].lower()
    bits = "Win64" if "64" in name else "Win32"
    return (f"Pov37-{bits}-MainWinClass", f"Unofficial-Pov37-{bits}-MainWinClass")


def _engine_window_open(classes: tuple[str, ...]) -> bool:
    """Return whether a window of one of these classes exists (Windows only)."""
    if sys.platform != "win32":
        return False
    try:  # pragma: no cover - Windows only
        import ctypes

        find = ctypes.WinDLL("user32").FindWindowW
        find.restype = ctypes.c_void_p
        return any(find(name, None) for name in classes)
    except (OSError, AttributeError):  # pragma: no cover - Windows only
        return False


def _general_option(settings_file: str | os.PathLike[str] | None, name: str) -> bool:
    """Return whether an on/off option of POV-Ray for Windows is on, as POV-Ray reads it.

    Reads `name` in the ``[General]`` section of ``pvengine.ini`` like
    ``GetPrivateProfileInt``: absent means on (the default of the options read here), and
    a value counts by its leading integer, so that ``0`` or a value without one means off.
    A missing or unreadable file counts as on.
    """
    if settings_file is None:
        return True
    try:
        text = Path(settings_file).read_text(encoding="latin-1")
    except OSError:
        return True
    section = ""
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1].strip().lower()
        elif section == "general" and "=" in line:
            key, value = (part.strip() for part in line.split("=", 1))
            if key.lower() == name.lower():
                match = re.match(r"[+-]?\d+", value)
                return match is not None and int(match.group()) != 0
    return True


def keeps_single_instance(settings_file: str | os.PathLike[str]) -> bool:
    r"""Return whether POV-Ray for Windows keeps a single instance, from its settings file.

    The option *Options ▸ Keep Single Instance* is stored as ``OneInstance`` in the
    ``[General]`` section of ``pvengine.ini`` (in ``Documents\POV-Ray\v3.7\ini``). It is
    read as POV-Ray reads it (``GetPrivateProfileInt``): absent means on (the default),
    and a value counts by its leading integer, so that ``0`` or a value without one
    means off. A missing or unreadable file counts as on.
    """
    return _general_option(settings_file, "OneInstance")


EDITOR_QUESTION_MESSAGE = (
    'POV-Ray for Windows would stop before rendering to ask "Could not load internal '
    'editor - download it?": its editor is not installed, and its option Options > Other '
    "Settings > Use Editor is on. Start POV-Ray for Windows once from the Start menu, "
    "answer No, untick Options > Other Settings > Use Editor (or answer Yes and install "
    "the editor from the page that opens), close POV-Ray, and try again."
)
"""Explanation when POV-Ray for Windows would ask about its missing editor and wait."""


def editor_library(executable: str | os.PathLike[str]) -> str:
    r"""Return the file name of the editor library that POV-Ray for Windows loads.

    The editor is a separately licensed library, not included in the AGPL installer.
    Each build of the program loads its own (``EDITDLLNAME`` in POV-Ray's source).

    >>> editor_library(r"C:\Program Files\POV-Ray\v3.7\bin\pvengine64.exe")
    'cmedit64.dll'
    >>> editor_library("pvengine32-sse2.exe"), editor_library("pvengine.exe")
    ('cmedit32-sse2.dll', 'cmedit32.dll')
    """
    name = str(executable).replace("\\", "/").rsplit("/", 1)[-1].lower()
    if "64" in name:
        return "cmedit64.dll"
    return "cmedit32-sse2.dll" if "sse2" in name else "cmedit32.dll"


def editor_question_pending(
    executable: str | os.PathLike[str],
    settings_file: str | os.PathLike[str] | None,
    homes: Iterable[str] = (),
) -> bool:
    r"""Return whether POV-Ray for Windows will ask about its editor when it starts.

    At every start, also with ``/EXIT``, POV-Ray for Windows loads its editor library
    ([`editor_library`][ycrystal.render.povray.editor_library]) from its own folder,
    then from the ``bin`` folder of its installation (``Home`` in the registry). If both
    fail and *Options ▸ Other Settings ▸ Use Editor* is on (``UseEditors`` in the
    ``[General]`` section of ``pvengine.ini``, on by default), it asks whether to download
    the editor and waits for the answer: a render started by Ycrystal would wait too.

    Only program files (``pvengine*.exe``) are checked; other programs never ask.

    Parameters
    ----------
    executable
        The POV-Ray for Windows program.
    settings_file
        Its ``pvengine.ini``; ``None`` if it has none yet (it has never run), which
        leaves the option on.
    homes
        Installation folders recorded in the registry.
    """
    path = Path(executable)
    if not is_windows_engine(path) or path.suffix.lower() != ".exe":
        return False
    if not _general_option(settings_file, "UseEditors"):
        return False
    library = editor_library(path)
    folders = [path.parent, *(Path(home) / "bin" for home in homes if home)]
    return not any((folder / library).is_file() for folder in folders)


def windows_engine_conflict(
    executable: str | os.PathLike[str], platform: str = sys.platform
) -> str | None:
    """Return why POV-Ray for Windows cannot start a render now, or ``None``.

    Two reasons are checked before POV-Ray starts, so that a render fails at once with
    an explanation instead of waiting for a dialog in a minimised window:

    - its question about a missing editor
      ([`editor_question_pending`][ycrystal.render.povray.editor_question_pending]):
      [`EDITOR_QUESTION_MESSAGE`][ycrystal.render.povray.EDITOR_QUESTION_MESSAGE];
    - with *Keep Single Instance* on (its default), POV-Ray for Windows does not render
      when another copy is open: it brings that copy forward, shows an error dialog for
      the switch ``/EXIT``, and exits without an image:
      [`ENGINE_OPEN_MESSAGE`][ycrystal.render.povray.ENGINE_OPEN_MESSAGE].

    Parameters
    ----------
    executable
        The POV-Ray about to start; ``None`` is returned for other programs than
        POV-Ray for Windows.
    platform
        ``sys.platform`` value to decide for; the default is the running system.
    """
    if platform != "win32" or not is_windows_engine(executable):
        return None
    settings = _engine_settings_file()
    if editor_question_pending(executable, settings, _registry_homes()):
        return EDITOR_QUESTION_MESSAGE
    if not _engine_window_open(_engine_window_classes(executable)):
        return None
    if settings is not None and not keeps_single_instance(settings):
        return None
    return ENGINE_OPEN_MESSAGE


def _engine_settings_file() -> Path | None:
    r"""Return the settings file of POV-Ray for Windows (``ini\pvengine.ini``), if found.

    It lives in the folder of its user files: the one recorded in the registry
    (``DocPath``), else ``Documents\POV-Ray\v3.7`` in the home folder.
    """
    folders = [Path(path) for path in _registry_user_folders()]
    folders.append(Path.home() / "Documents" / "POV-Ray" / WINDOWS_VERSION_FOLDER)
    for folder in folders:
        candidate = folder / "ini" / "pvengine.ini"
        if candidate.is_file():
            return candidate
    return None


_foreground_holds = 0


def hold_foreground(executable: str | os.PathLike[str], platform: str = sys.platform) -> bool:
    """Keep POV-Ray for Windows from taking the keyboard focus while it renders.

    POV-Ray for Windows brings its window to the foreground when it starts, even when
    started minimised, which takes the keyboard focus from the window the user works
    in, for example during every automatic preview. While a hold is active, Ycrystal
    asks Windows to refuse such requests of other programs
    (``LockSetForegroundWindow``). Windows grants this only to the program that owns
    the foreground window: Ycrystal's window when the user works there, not a terminal
    that runs ``ycrystal --render``. It lifts the lock by itself when the user presses
    Alt or clicks another window.

    Every hold asks for the lock again (Windows may have lifted it since), and holds
    are counted, so that renders that overlap keep the lock until the last one ends.

    Parameters
    ----------
    executable
        The POV-Ray that is about to start; only POV-Ray for Windows needs a hold.
    platform
        ``sys.platform`` value to decide for; the default is the running system.

    Returns
    -------
    bool
        Whether a hold was taken; then call
        [`release_foreground`][ycrystal.render.povray.release_foreground] once when
        POV-Ray has exited.
    """
    global _foreground_holds
    if platform != "win32" or not is_windows_engine(executable):
        return False
    _foreground_holds += 1
    _lock_foreground(True)
    return True


def release_foreground() -> None:
    """End one hold of [`hold_foreground`][ycrystal.render.povray.hold_foreground]."""
    global _foreground_holds
    if _foreground_holds == 0:
        return
    _foreground_holds -= 1
    if _foreground_holds == 0:
        _lock_foreground(False)


@contextmanager
def foreground_held(executable: str | os.PathLike[str]) -> Iterator[None]:
    """Hold the foreground for the duration of a ``with`` block.

    See [`hold_foreground`][ycrystal.render.povray.hold_foreground].
    """
    held = hold_foreground(executable)
    try:
        yield
    finally:
        if held:
            release_foreground()


def _lock_foreground(lock: bool) -> None:
    """Call ``LockSetForegroundWindow`` (Windows only; failures are ignored).

    It fails, harmlessly, when Ycrystal does not own the foreground window.
    """
    if sys.platform != "win32":
        return
    try:  # pragma: no cover - Windows only
        import ctypes

        ctypes.WinDLL("user32").LockSetForegroundWindow(1 if lock else 2)  # LSFW_(UN)LOCK
    except (OSError, AttributeError):  # pragma: no cover - Windows only
        pass


def read_log(directory: str | os.PathLike[str]) -> str:
    """Return the log POV-Ray for Windows wrote into a job directory (empty if none)."""
    path = Path(directory) / LOG_NAME
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def povray_version(executable: str, timeout: float = 15.0) -> str | None:
    """Return the version that ``povray --version`` reports.

    Runs the executable synchronously. POV-Ray for Windows has no ``--version`` (it
    would open its window); its version is read from the executable's version
    resource instead, without running it.

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
    if is_windows_engine(executable):
        return windows_file_version(executable)
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


def windows_file_version(path: str | os.PathLike[str]) -> str | None:
    """Return the file version of a Windows executable (``"3.7.0.0"``), or ``None``.

    Reads the fixed version information of the file with the Windows version API;
    ``None`` on other systems, for files without version information, and on errors.
    """
    if sys.platform != "win32":
        return None
    try:  # pragma: no cover - Windows only
        import ctypes
        from ctypes import wintypes

        api = ctypes.WinDLL("version")
        name = str(path)
        size = api.GetFileVersionInfoSizeW(name, None)
        if not size:
            return None
        data = ctypes.create_string_buffer(size)
        if not api.GetFileVersionInfoW(name, 0, size, data):
            return None
        pointer, length = ctypes.c_void_p(), wintypes.UINT()
        if not api.VerQueryValueW(data, "\\", ctypes.byref(pointer), ctypes.byref(length)):
            return None
        # VS_FIXEDFILEINFO: signature, structure version, file version (high, low), ...
        fields = ctypes.cast(pointer, ctypes.POINTER(ctypes.c_uint32 * 4)).contents
        high, low = fields[2], fields[3]
        return f"{high >> 16}.{high & 0xFFFF}.{low >> 16}.{low & 0xFFFF}"
    except (OSError, AttributeError, ValueError):
        return None


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
        "POV-Ray's I/O restrictions (povray.conf; in POV-Ray for Windows, its I/O "
        "restriction options) blocked a file access. Ycrystal renders inside its own "
        "temporary job directory; check that the directory is readable and writable and "
        "that the restrictions permit the working directory ('.').",
    ),
    (
        re.compile(r"Cannot open include file|Cannot find file", re.IGNORECASE),
        "POV-Ray could not find a required include file{name}. Materials that use native "
        "POV-Ray identifiers need the standard include files: on Linux Mint/Ubuntu install "
        "them with 'sudo apt install povray-includes' (Homebrew's povray on macOS contains "
        "them; POV-Ray for Windows keeps them in Documents\\POV-Ray\\v3.7\\include), or "
        "check the include library path (Library_Path) of this installation.",
    ),
)

_INCLUDE_NAME = re.compile(r"(?:Cannot open include file|Cannot find file)\s+'?\"?([\w.\-]+)")

INCLUDE_FALLBACK_DIRS = (
    Path("/usr/share/povray-3.7/include"),
    Path("/usr/local/share/povray-3.7/include"),
)
"""Standard include directories searched in addition to ``Library_Path`` entries and the
installation of the POV-Ray executable (see
[`include_directories`][ycrystal.render.povray.include_directories])."""


def _installation_prefixes(executable: str | os.PathLike[str] | None) -> list[Path]:
    """Return the installation prefixes of a POV-Ray executable (``PREFIX/bin/povray``).

    Both the path as given and the path with symbolic links resolved count, so that a
    package manager's link (Homebrew: ``/opt/homebrew/bin/povray``) and the real
    location (its ``Cellar``) are covered. ``None`` looks the executable up like
    [`find_povray`][ycrystal.render.povray.find_povray]; no executable gives no prefix.
    """
    if executable is None:
        try:
            executable = find_povray()
        except PovrayNotFoundError:
            return []
    path = Path(executable).expanduser()
    prefixes: list[Path] = []
    for candidate in (path.absolute(), path.resolve()):
        prefix = candidate.parent.parent
        if prefix not in prefixes:
            prefixes.append(prefix)
    return prefixes


def _windows_user_folders(prefixes: list[Path]) -> list[Path]:
    r"""Return the folders of POV-Ray for Windows that hold ``include`` and ``ini``.

    Its installation folder (the prefix, ``…\POV-Ray\v3.7``) and the copy of its user
    files: the folder recorded in the registry (``DocPath``), then
    ``Documents\POV-Ray\v3.7`` in the home folder. Only for an installation of POV-Ray
    for Windows (a prefix whose ``bin`` folder has a ``pvengine*.exe``).
    """
    folders: list[Path] = []
    for prefix in prefixes:
        if any(prefix.glob("bin/pvengine*.exe")):
            for folder in (
                prefix,
                *(Path(path) for path in _registry_user_folders()),
                Path.home() / "Documents" / "POV-Ray" / prefix.name,
            ):
                if folder not in folders:
                    folders.append(folder)
    return folders


def include_directories(executable: str | os.PathLike[str] | None = None) -> list[Path]:
    """Return the directories where POV-Ray looks for standard include files.

    POV-Ray is installed under a prefix (``/usr``, ``/usr/local``, Homebrew's
    ``/opt/homebrew``, a Conda environment, …) with its settings in
    ``PREFIX/etc/povray/VERSION/povray.ini`` and its include files in
    ``PREFIX/share/povray-VERSION/include``. This function reads the ``Library_Path``
    entries of the ``povray.ini`` files of the system (``/etc/povray/3.7``), of the
    executable's prefix, and of the user (``~/.povray/3.7``), and adds the prefix's
    include directories and
    [`INCLUDE_FALLBACK_DIRS`][ycrystal.render.povray.INCLUDE_FALLBACK_DIRS].

    Parameters
    ----------
    executable
        POV-Ray executable whose installation is searched; ``None`` uses the one that
        [`find_povray`][ycrystal.render.povray.find_povray] returns without a configured
        path (``$YCRYSTAL_POVRAY``, then ``PATH``), if any.

    Returns
    -------
    list of pathlib.Path
        Existing directories, without duplicates. Nothing is executed.
    """
    prefixes = _installation_prefixes(executable)
    ini_files = [Path("/etc/povray/3.7/povray.ini")]
    for prefix in prefixes:
        ini_files.extend(sorted(prefix.glob("etc/povray/*/povray.ini")))
    ini_files.append(Path.home() / ".povray/3.7/povray.ini")
    windows_folders = _windows_user_folders(prefixes)
    for folder in windows_folders:  # POV-Ray for Windows: FOLDER\ini\povray.ini
        ini_files.append(folder / "ini" / "povray.ini")
    candidates: list[Path] = []
    for ini in ini_files:
        try:
            text = ini.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for line in text.splitlines():
            match = re.match(r"\s*Library_Path\s*=\s*\"?([^\";]+)\"?", line, re.IGNORECASE)
            if match:
                candidates.append(Path(os.path.expanduser(match.group(1).strip())))
    for prefix in prefixes:
        candidates.extend(sorted(prefix.glob("share/povray-*/include")))
    candidates.extend(folder / "include" for folder in windows_folders)
    candidates.extend(INCLUDE_FALLBACK_DIRS)
    result: list[Path] = []
    for directory in candidates:
        if directory.is_dir() and directory not in result:
            result.append(directory)
    return result


def missing_includes(
    names: tuple[str, ...] | list[str], executable: str | os.PathLike[str] | None = None
) -> list[str]:
    """Return the include files of ``names`` that none of the include directories has.

    Parameters
    ----------
    names
        Include file names, for example from
        [`required_includes`][ycrystal.render.pov_writer.required_includes].
    executable
        POV-Ray executable whose installation is searched; see
        [`include_directories`][ycrystal.render.povray.include_directories].

    Returns
    -------
    list of str
        The missing names, in the given order; empty when all are found.
    """
    directories = include_directories(executable)
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
