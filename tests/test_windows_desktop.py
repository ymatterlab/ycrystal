"""The Windows Start-menu entry of ``ycrystal --install-desktop``.

The launch command and the icon are checked on every system; the shortcut and the
registered file type need Windows. Those tests write into temporary folders and into a
registry key of their own under ``HKEY_CURRENT_USER\\Software\\Y-Matter Lab``, which
they delete again: never into the real Start menu or ``Software\\Classes``.
"""

import sys
import uuid

import pytest
from PIL import Image

from ycrystal import desktop
from ycrystal.app import main
from ycrystal.desktop import (
    ICON_SIZES,
    LEGACY_SHORTCUT_NAME,
    SHORTCUT_NAME,
    WINDOWS_PROG_ID,
    install_start_menu,
    project_type_handler,
    uninstall_start_menu,
    windows_launch_command,
    write_windows_icon,
)
from ycrystal.gui.native import WINDOWS_APP_ID, WINDOWS_PACKAGED_APP_ID

PACKAGED_PROG_ID = "YMatterLab.Ycrystal.Project"  # packaging/windows/ycrystal.iss

windows_only = pytest.mark.skipif(sys.platform != "win32", reason="Windows shell and registry")


def test_start_menu_runs_the_environments_python_without_a_console(tmp_path):
    scripts = tmp_path / "my env" / "Scripts"
    scripts.mkdir(parents=True)
    python = scripts / "python.exe"
    python.write_bytes(b"MZ")
    # No pythonw.exe: the interpreter itself (a console window, but it starts).
    assert windows_launch_command(str(python), True) == (str(python), "-I -m ycrystal.app")
    (scripts / "pythonw.exe").write_bytes(b"MZ")
    program, arguments = windows_launch_command(str(python), True)
    assert program == str(scripts / "pythonw.exe") and arguments == "-I -m ycrystal.app"
    # Outside a virtual environment the user's own packages must stay visible: no -I.
    assert windows_launch_command(str(python), False)[1] == "-m ycrystal.app"


def test_windows_icon_has_every_size_drawn_from_the_svg(tmp_path):
    path = write_windows_icon(tmp_path / "icons" / "ycrystal.ico")
    with Image.open(path) as icon:
        assert sorted(icon.info["sizes"]) == [(s, s) for s in sorted(ICON_SIZES)]
        icon.size = (16, 16)
        small = icon.convert("RGBA")
    assert small.getpixel((0, 0))[3] == 0  # transparent corner
    assert small.getpixel((8, 8))[3] > 0  # the drawing


def test_menu_entry_command_applies_to_linux_and_windows(tmp_path, monkeypatch, capsys):
    """``--install-desktop`` picks this system's menu; macOS has none."""
    assert desktop.desktop_supported("win32") and desktop.desktop_supported("linux")
    assert not desktop.desktop_supported("darwin")
    calls = []
    monkeypatch.setattr(desktop, "install_start_menu", lambda: calls.append("win") or [])
    monkeypatch.setattr(desktop, "install_desktop", lambda: calls.append("linux") or [])
    desktop.install_menu_entry("win32")
    desktop.install_menu_entry("linux")
    assert calls == ["win", "linux"]
    assert "Start menu" in desktop.menu_entry_note("win32")


@pytest.fixture
def registry_classes():
    """Yield a registry key of its own for file types; delete it afterwards."""
    base = rf"Software\Y-Matter Lab\ycrystal-tests-{uuid.uuid4().hex[:8]}"
    yield rf"{base}\Classes"
    desktop._delete_key_tree(base)


def _value(path: str, name: str = ""):
    import winreg

    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path) as key:
        return winreg.QueryValueEx(key, name)[0]


@windows_only
def test_shortcut_carries_the_application_id(tmp_path):
    from ycrystal.windows_shortcut import read_shortcut, write_shortcut

    folder = tmp_path / "Start menü"
    target = tmp_path / "my env ü" / "pythonw.exe"
    target.parent.mkdir()
    target.write_bytes(b"MZ")
    path = write_shortcut(
        folder / "Test.lnk",
        target,
        "-I -m ycrystal.app",
        working_directory=tmp_path,
        icon=tmp_path / "icon.ico",
        description="A test",
        app_id=WINDOWS_APP_ID,
    )
    shortcut = read_shortcut(path)
    assert shortcut.target == str(target) and shortcut.arguments == "-I -m ycrystal.app"
    assert shortcut.working_directory == str(tmp_path)
    assert shortcut.icon == str(tmp_path / "icon.ico") and shortcut.description == "A test"
    assert shortcut.app_id == WINDOWS_APP_ID  # the id the window sets: pinning works
    write_shortcut(path, target)  # replaced, without an id
    assert read_shortcut(path).app_id is None and read_shortcut(path).arguments == ""


@windows_only
def test_start_menu_entry_and_project_type_install_and_uninstall(tmp_path, registry_classes):
    from ycrystal.windows_shortcut import read_shortcut

    program = str(tmp_path / "env" / "Scripts" / "pythonw.exe")
    command = (program, "-I -m ycrystal.app")
    menu, data = tmp_path / "Programs", tmp_path / "Local" / "Y-Matter Lab" / "Ycrystal"
    shortcut, icon = install_start_menu(menu, data, registry_classes, command)
    assert shortcut == menu / SHORTCUT_NAME and icon == data / "ycrystal.ico"
    entry = read_shortcut(shortcut)
    assert (entry.target, entry.arguments, entry.icon) == (program, command[1], str(icon))
    assert entry.app_id == WINDOWS_APP_ID
    assert _value(rf"{registry_classes}\.ycrystal") == WINDOWS_PROG_ID
    prog_id = rf"{registry_classes}\{WINDOWS_PROG_ID}"
    assert _value(prog_id) == "Ycrystal project"
    assert _value(rf"{prog_id}\DefaultIcon") == f"{icon},0"
    assert _value(rf"{prog_id}\shell\open\command") == f'"{program}" -I -m ycrystal.app "%1"'

    assert install_start_menu(menu, data, registry_classes, command) == [shortcut, icon]
    assert sorted(uninstall_start_menu(menu, data, registry_classes)) == sorted([shortcut, icon])
    assert not shortcut.exists() and not icon.exists()
    with pytest.raises(FileNotFoundError):
        _value(prog_id)
    with pytest.raises(FileNotFoundError):
        _value(rf"{registry_classes}\.ycrystal")
    assert uninstall_start_menu(menu, data, registry_classes) == []  # nothing left


@windows_only
def test_another_programs_project_type_is_left_alone(tmp_path, registry_classes):
    import winreg

    extension = rf"{registry_classes}\.ycrystal"
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, extension) as key:
        winreg.SetValueEx(key, "", 0, winreg.REG_SZ, "Other.Program")
    command = (str(tmp_path / "pythonw.exe"), "-I -m ycrystal.app")
    install_start_menu(tmp_path / "menu", tmp_path / "data", registry_classes, command)
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, extension) as key:
        winreg.SetValueEx(key, "", 0, winreg.REG_SZ, "Other.Program")  # chosen later
    uninstall_start_menu(tmp_path / "menu", tmp_path / "data", registry_classes)
    assert _value(extension) == "Other.Program"


@windows_only
def test_install_desktop_command_on_windows(tmp_path, monkeypatch, capsys, registry_classes):
    from ycrystal.windows_shortcut import read_shortcut

    monkeypatch.setattr("ycrystal.windows_shortcut.programs_folder", lambda: tmp_path / "menu")
    monkeypatch.setattr(desktop, "windows_data_folder", lambda: tmp_path / "data")
    monkeypatch.setattr(desktop, "CLASSES_KEY", registry_classes)
    assert main(["--install-desktop"]) == 0
    out = capsys.readouterr().out
    assert "Start menu" in out and str(tmp_path / "menu" / SHORTCUT_NAME) in out
    entry = read_shortcut(tmp_path / "menu" / SHORTCUT_NAME)
    assert entry.target == windows_launch_command()[0]
    assert entry.arguments.endswith("-m ycrystal.app")
    assert main(["--uninstall-desktop"]) == 0
    assert "Removed" in capsys.readouterr().out
    assert not (tmp_path / "menu" / SHORTCUT_NAME).exists()


# ----- coexistence with the packaged Ycrystal (packaging/windows) ---------------------------
def _packaged_shortcut(path, tmp_path):
    """Write a shortcut like the Windows installer's: Ycrystal.exe, the packaged id."""
    from ycrystal.windows_shortcut import write_shortcut

    program = tmp_path / "Programs" / "Ycrystal" / "Ycrystal.exe"
    program.parent.mkdir(parents=True, exist_ok=True)
    program.write_bytes(b"MZ")
    return write_shortcut(path, program, app_id=WINDOWS_PACKAGED_APP_ID)


def _register_packaged_type(classes, tmp_path):
    """Register the file type as the Windows installer does, and make it the default."""
    import winreg

    command = f'"{tmp_path / "Ycrystal.exe"}" "%1"'
    for path, name, value in (
        (rf"{PACKAGED_PROG_ID}\shell\open\command", "", command),
        (r".ycrystal\OpenWithProgids", PACKAGED_PROG_ID, ""),
        (".ycrystal", "", PACKAGED_PROG_ID),
    ):
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, rf"{classes}\{path}") as key:
            winreg.SetValueEx(key, name, 0, winreg.REG_SZ, value)


@windows_only
def test_source_entry_is_named_apart_from_the_packaged_one(tmp_path, registry_classes):
    """``Ycrystal.lnk`` belongs to the installer; the source entry has its own name."""
    from ycrystal.windows_shortcut import read_shortcut

    assert SHORTCUT_NAME == "Ycrystal (development).lnk" and LEGACY_SHORTCUT_NAME == "Ycrystal.lnk"
    menu = tmp_path / "Programs"
    packaged = _packaged_shortcut(menu / LEGACY_SHORTCUT_NAME, tmp_path)
    command = (str(tmp_path / "env" / "pythonw.exe"), "-I -m ycrystal.app")
    shortcut, _ = install_start_menu(menu, tmp_path / "data", registry_classes, command)
    assert shortcut.name == "Ycrystal (development).lnk"
    assert read_shortcut(packaged).app_id == WINDOWS_PACKAGED_APP_ID  # untouched
    assert read_shortcut(shortcut).app_id == WINDOWS_APP_ID != WINDOWS_PACKAGED_APP_ID
    uninstall_start_menu(menu, tmp_path / "data", registry_classes)
    assert not shortcut.exists()
    assert read_shortcut(packaged).target.endswith("Ycrystal.exe")  # still there


@windows_only
def test_old_source_shortcut_is_replaced_by_the_new_name(tmp_path, registry_classes):
    """Before the installer existed, the source entry was ``Ycrystal.lnk``."""
    from ycrystal.windows_shortcut import write_shortcut

    menu = tmp_path / "Programs"
    program = str(tmp_path / "env" / "pythonw.exe")
    old = write_shortcut(menu / LEGACY_SHORTCUT_NAME, program, "-I -m ycrystal.app")
    command = (program, "-I -m ycrystal.app")
    install_start_menu(menu, tmp_path / "data", registry_classes, command)
    assert not old.exists() and (menu / SHORTCUT_NAME).is_file()
    write_shortcut(old, program, "-I -m ycrystal.app")  # an old one left behind again
    removed = uninstall_start_menu(menu, tmp_path / "data", registry_classes)
    assert old in removed and not old.exists()


@windows_only
def test_source_entry_leaves_the_packaged_file_type_alone(tmp_path, registry_classes):
    """The installed program keeps opening .ycrystal files; uninstalling changes nothing."""
    import winreg

    _register_packaged_type(registry_classes, tmp_path)
    assert project_type_handler(registry_classes) == PACKAGED_PROG_ID
    command = (str(tmp_path / "env" / "pythonw.exe"), "-I -m ycrystal.app")
    install_start_menu(tmp_path / "menu", tmp_path / "data", registry_classes, command)
    assert _value(rf"{registry_classes}\.ycrystal") == PACKAGED_PROG_ID  # not taken
    with winreg.OpenKey(
        winreg.HKEY_CURRENT_USER, rf"{registry_classes}\.ycrystal\OpenWithProgids"
    ) as key:
        names = {winreg.EnumValue(key, i)[0] for i in range(winreg.QueryInfoKey(key)[1])}
    assert names == {PACKAGED_PROG_ID, WINDOWS_PROG_ID}  # both in Open with
    uninstall_start_menu(tmp_path / "menu", tmp_path / "data", registry_classes)
    assert _value(rf"{registry_classes}\.ycrystal") == PACKAGED_PROG_ID
    assert _value(rf"{registry_classes}\.ycrystal\OpenWithProgids", PACKAGED_PROG_ID) == ""
    assert _value(rf"{registry_classes}\{PACKAGED_PROG_ID}\shell\open\command").endswith('"%1"')
    with pytest.raises(FileNotFoundError):
        _value(rf"{registry_classes}\{WINDOWS_PROG_ID}")


@windows_only
def test_source_entry_opens_projects_when_no_other_program_does(tmp_path, registry_classes):
    """A default naming a file type that no longer exists does not count."""
    import winreg

    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, rf"{registry_classes}\.ycrystal") as key:
        winreg.SetValueEx(key, "", 0, winreg.REG_SZ, "Gone.Program")
    assert project_type_handler(registry_classes) is None
    command = (str(tmp_path / "env" / "pythonw.exe"), "-I -m ycrystal.app")
    install_start_menu(tmp_path / "menu", tmp_path / "data", registry_classes, command)
    assert project_type_handler(registry_classes) == WINDOWS_PROG_ID


@windows_only
def test_application_id_stored_as_bstr_is_read(tmp_path):
    """Inno Setup stores the id as VT_BSTR (the shell and this module: VT_LPWSTR)."""
    import ctypes

    from ycrystal import windows_shortcut as ws

    path = ws.write_shortcut(tmp_path / "Installer.lnk", tmp_path / "Ycrystal.exe")
    oleaut32 = ctypes.WinDLL("oleaut32")
    oleaut32.SysAllocString.restype = ctypes.c_void_p
    oleaut32.SysAllocString.argtypes = [ctypes.c_wchar_p]
    oleaut32.SysFreeString.argtypes = [ctypes.c_void_p]
    text = oleaut32.SysAllocString(WINDOWS_PACKAGED_APP_ID)
    try:
        with ws._shell_link() as (link, _):
            persist = ws._query(link, ws._IID_PERSIST_FILE)
            ws._method(persist, ws._PERSIST_LOAD, ctypes.c_wchar_p, ctypes.c_uint32)(str(path), 2)
            store = ws._query(link, ws._IID_PROPERTY_STORE)
            variant = ws._PROPVARIANT(vt=8)  # VT_BSTR
            variant.pointer = text
            set_value = ws._method(
                store,
                ws._STORE_SET_VALUE,
                ctypes.POINTER(ws._PROPERTYKEY),
                ctypes.POINTER(ws._PROPVARIANT),
            )
            set_value(ctypes.byref(ws._app_id_key()), ctypes.byref(variant))
            ws._method(store, ws._STORE_COMMIT)()
            ws._release(store)
            ws._method(persist, ws._PERSIST_SAVE, ctypes.c_wchar_p, ctypes.c_int)(str(path), 1)
            ws._release(persist)
    finally:
        oleaut32.SysFreeString(text)
    assert ws.read_shortcut(path).app_id == WINDOWS_PACKAGED_APP_ID
