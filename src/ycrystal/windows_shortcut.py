r"""Windows shortcuts (``.lnk`` files) that carry an application id, without extra packages.

Ycrystal's Start-menu entry is a shortcut with the application id
``YMatterLab.Ycrystal`` (the shell property ``System.AppUserModel.ID``), the id its
window sets when it starts. Windows then shows the running window under the shortcut's
name and icon, and *Pin to taskbar* pins the shortcut. ``WScript.Shell`` and similar
tools cannot set that property, so shortcuts are written and read here through the
shell's own COM interfaces (``IShellLinkW``, ``IPropertyStore``, ``IPersistFile``) with
``ctypes``. Windows only: on other systems the functions raise ``OSError``.
"""

from __future__ import annotations

import ctypes
import sys
import uuid
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_CLSID_SHELL_LINK = "00021401-0000-0000-C000-000000000046"
_IID_SHELL_LINK_W = "000214F9-0000-0000-C000-000000000046"
_IID_PERSIST_FILE = "0000010B-0000-0000-C000-000000000046"
_IID_PROPERTY_STORE = "886D8EEB-8CF2-4446-8D02-CDBA1DBDCF99"
_PKEY_APP_ID = ("9F4C2855-9F79-4B39-A8D0-E1D42DE1D5F3", 5)  # System.AppUserModel.ID
_FOLDERID_PROGRAMS = "A77F5D77-2E2B-44C3-A6A2-ABA601054A51"  # the user's Start menu

_VT_LPWSTR = 31
_TEXT_SIZE = 1024  # INFOTIPSIZE: the longest text a shortcut stores

# Positions in the method tables (after IUnknown's QueryInterface, AddRef, Release).
_GET_PATH, _GET_DESCRIPTION, _SET_DESCRIPTION = 3, 6, 7
_GET_WORKING_DIRECTORY, _SET_WORKING_DIRECTORY = 8, 9
_GET_ARGUMENTS, _SET_ARGUMENTS = 10, 11
_GET_ICON_LOCATION, _SET_ICON_LOCATION, _SET_PATH = 16, 17, 20
_PERSIST_LOAD, _PERSIST_SAVE = 5, 6
_STORE_GET_VALUE, _STORE_SET_VALUE, _STORE_COMMIT = 5, 6, 7


class _GUID(ctypes.Structure):
    _fields_ = [
        ("data1", ctypes.c_uint32),
        ("data2", ctypes.c_uint16),
        ("data3", ctypes.c_uint16),
        ("data4", ctypes.c_ubyte * 8),
    ]


class _PROPERTYKEY(ctypes.Structure):
    _fields_ = [("fmtid", _GUID), ("pid", ctypes.c_uint32)]


class _PROPVARIANT(ctypes.Structure):
    # 16 bytes on 32-bit, 24 on 64-bit Windows; only the pointer member is used.
    _fields_ = [
        ("vt", ctypes.c_ushort),
        ("reserved", ctypes.c_ushort * 3),
        ("pointer", ctypes.c_void_p),
        ("padding", ctypes.c_void_p),
    ]


@dataclass(frozen=True)
class Shortcut:
    """Describe what a shortcut runs and shows.

    Returned by [`read_shortcut`][ycrystal.windows_shortcut.read_shortcut].

    Attributes
    ----------
    target
        The program it starts.
    arguments
        Its command-line arguments, as one string.
    working_directory
        The folder it starts in; empty if none is set.
    icon
        The icon file; empty if the program's own icon is used.
    description
        The tooltip text.
    app_id
        The application id, or ``None`` if it has none.
    """

    target: str
    arguments: str
    working_directory: str
    icon: str
    description: str
    app_id: str | None


def _guid(text: str) -> _GUID:
    return _GUID.from_buffer_copy(uuid.UUID(text).bytes_le)


def _app_id_key() -> _PROPERTYKEY:
    return _PROPERTYKEY(_guid(_PKEY_APP_ID[0]), _PKEY_APP_ID[1])


def _method(pointer: ctypes.c_void_p, index: int, *argtypes: Any) -> Callable[..., int]:
    """Return method `index` of a COM interface; calls raise ``OSError`` on failure."""
    table = ctypes.cast(pointer, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
    function = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p, *argtypes)(table[index])

    def call(*args: Any) -> int:
        result = function(pointer, *args)
        if result < 0:
            raise OSError(f"Windows shell call failed (HRESULT 0x{result & 0xFFFFFFFF:08X})")
        return result

    return call


def _release(pointer: ctypes.c_void_p) -> None:
    table = ctypes.cast(pointer, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
    ctypes.WINFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p)(table[2])(pointer)


def _query(pointer: ctypes.c_void_p, iid: str) -> ctypes.c_void_p:
    out = ctypes.c_void_p()
    _method(pointer, 0, ctypes.POINTER(_GUID), ctypes.POINTER(ctypes.c_void_p))(
        ctypes.byref(_guid(iid)), ctypes.byref(out)
    )
    return out


@contextmanager
def _shell_link() -> Iterator[tuple[ctypes.c_void_p, Any]]:
    """Yield a new shell link object and ``ole32``, with COM initialised around it."""
    if sys.platform != "win32":
        raise OSError("Windows shortcuts can only be written on Windows")
    ole32 = ctypes.WinDLL("ole32")
    initialised = ole32.CoInitializeEx(None, 2)  # COINIT_APARTMENTTHREADED; S_FALSE if done
    try:
        link = ctypes.c_void_p()
        create = ole32.CoCreateInstance
        create.restype = ctypes.c_long
        create.argtypes = [
            ctypes.POINTER(_GUID),
            ctypes.c_void_p,
            ctypes.c_uint32,
            ctypes.POINTER(_GUID),
            ctypes.POINTER(ctypes.c_void_p),
        ]
        result = create(
            ctypes.byref(_guid(_CLSID_SHELL_LINK)),
            None,
            1,  # CLSCTX_INPROC_SERVER
            ctypes.byref(_guid(_IID_SHELL_LINK_W)),
            ctypes.byref(link),
        )
        if result < 0:
            raise OSError(f"Cannot create a shell link (HRESULT 0x{result & 0xFFFFFFFF:08X})")
        try:
            yield link, ole32
        finally:
            _release(link)
    finally:
        if initialised >= 0:  # not when another threading model was already chosen
            ole32.CoUninitialize()


def write_shortcut(
    path: str | Path,
    target: str | Path,
    arguments: str = "",
    *,
    working_directory: str | Path | None = None,
    icon: str | Path | None = None,
    description: str = "",
    app_id: str | None = None,
) -> Path:
    """Write a shortcut file; an existing one is replaced.

    Parameters
    ----------
    path
        The ``.lnk`` file to write; its folder is created if needed.
    target
        The program the shortcut starts.
    arguments
        Its command-line arguments, as one string (quote paths with spaces).
    working_directory
        The folder it starts in; ``None`` sets none.
    icon
        An ``.ico`` file; ``None`` keeps the program's own icon.
    description
        The tooltip text.
    app_id
        The application id (``System.AppUserModel.ID``); ``None`` sets none.

    Returns
    -------
    pathlib.Path
        `path`.

    Raises
    ------
    OSError
        If a shell call fails, or on another system than Windows.
    """
    path = Path(path)
    text = ctypes.c_wchar_p
    with _shell_link() as (link, _):
        _method(link, _SET_PATH, text)(str(target))
        _method(link, _SET_ARGUMENTS, text)(arguments)
        _method(link, _SET_DESCRIPTION, text)(description)
        if working_directory is not None:
            _method(link, _SET_WORKING_DIRECTORY, text)(str(working_directory))
        if icon is not None:
            _method(link, _SET_ICON_LOCATION, text, ctypes.c_int)(str(icon), 0)
        if app_id is not None:
            store = _query(link, _IID_PROPERTY_STORE)
            try:
                value = ctypes.create_unicode_buffer(app_id)
                variant = _PROPVARIANT(vt=_VT_LPWSTR)
                variant.pointer = ctypes.cast(value, ctypes.c_void_p).value
                _method(
                    store,
                    _STORE_SET_VALUE,
                    ctypes.POINTER(_PROPERTYKEY),
                    ctypes.POINTER(_PROPVARIANT),
                )(ctypes.byref(_app_id_key()), ctypes.byref(variant))
                _method(store, _STORE_COMMIT)()
            finally:
                _release(store)
        persist = _query(link, _IID_PERSIST_FILE)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            _method(persist, _PERSIST_SAVE, text, ctypes.c_int)(str(path), 1)
        finally:
            _release(persist)
    return path


def read_shortcut(path: str | Path) -> Shortcut:
    """Read what a shortcut file runs and shows.

    Raises
    ------
    OSError
        If the file cannot be read as a shortcut, or on another system than Windows.
    """
    text = ctypes.c_wchar_p
    size = ctypes.c_int
    with _shell_link() as (link, ole32):
        persist = _query(link, _IID_PERSIST_FILE)
        try:
            _method(persist, _PERSIST_LOAD, text, ctypes.c_uint32)(str(path), 0)  # STGM_READ
        finally:
            _release(persist)

        def field(index: int, *extra_types: Any, extra: tuple[Any, ...] = ()) -> str:
            buffer = ctypes.create_unicode_buffer(_TEXT_SIZE)
            _method(link, index, ctypes.c_wchar_p, size, *extra_types)(buffer, _TEXT_SIZE, *extra)
            return buffer.value

        target = field(_GET_PATH, ctypes.c_void_p, ctypes.c_uint32, extra=(None, 4))  # SLGP_RAWPATH
        icon_index = ctypes.c_int()
        icon = field(
            _GET_ICON_LOCATION, ctypes.POINTER(ctypes.c_int), extra=(ctypes.byref(icon_index),)
        )
        store = _query(link, _IID_PROPERTY_STORE)
        try:
            variant = _PROPVARIANT()
            _method(
                store, _STORE_GET_VALUE, ctypes.POINTER(_PROPERTYKEY), ctypes.POINTER(_PROPVARIANT)
            )(ctypes.byref(_app_id_key()), ctypes.byref(variant))
            app_id = None
            if variant.vt == _VT_LPWSTR and variant.pointer:
                app_id = ctypes.wstring_at(variant.pointer)
            ole32.PropVariantClear(ctypes.byref(variant))
        finally:
            _release(store)
        return Shortcut(
            target=target,
            arguments=field(_GET_ARGUMENTS),
            working_directory=field(_GET_WORKING_DIRECTORY),
            icon=icon,
            description=field(_GET_DESCRIPTION),
            app_id=app_id,
        )


def programs_folder() -> Path:
    r"""Return the current user's Start-menu folder of programs.

    Normally ``%APPDATA%\Microsoft\Windows\Start Menu\Programs``; asked from Windows
    (``SHGetKnownFolderPath``), so that a redirected folder is found too.

    Raises
    ------
    OSError
        If Windows does not report the folder, or on another system than Windows.
    """
    if sys.platform != "win32":
        raise OSError("The Start menu exists only on Windows")
    shell32 = ctypes.WinDLL("shell32")
    ole32 = ctypes.WinDLL("ole32")
    folder = ctypes.c_wchar_p()
    result = shell32.SHGetKnownFolderPath(
        ctypes.byref(_guid(_FOLDERID_PROGRAMS)), 0, None, ctypes.byref(folder)
    )
    try:
        if result != 0 or not folder.value:
            raise OSError(f"Windows did not report the Start-menu folder (HRESULT {result:#x})")
        return Path(folder.value)
    finally:
        ole32.CoTaskMemFree(folder)
