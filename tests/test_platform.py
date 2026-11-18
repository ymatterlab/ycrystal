"""Cross-platform behaviour that does not need a display: POV-Ray include discovery,
platform-dependent interface choices, the Linux-only launcher command, and the display
check of the test suite itself."""

import sys
from pathlib import Path

import pytest
from PySide6.QtCore import QSettings, QStandardPaths

import conftest
from ycrystal.app import main
from ycrystal.desktop import desktop_supported
from ycrystal.gui.native import (
    THUMBNAIL_FOLDER,
    executable_filter,
    native_keys,
    personal_thumbnail_directory,
    set_taskbar_identity,
)
from ycrystal.render.povray import POVRAY_ENV, include_directories, missing_includes

ONLY_HERE = "ycrystal-test-only.inc"  # no real installation has this include file


def fake_installation(prefix: Path) -> Path:
    """A POV-Ray installation layout under ``prefix``; returns its executable."""
    executable = prefix / "bin" / "povray"
    executable.parent.mkdir(parents=True)
    executable.write_text("#!/bin/sh\n")
    executable.chmod(0o755)
    include = prefix / "share" / "povray-3.7" / "include"
    include.mkdir(parents=True)
    (include / ONLY_HERE).write_text("// test\n")
    return executable


# ----- POV-Ray include files ---------------------------------------------------------------
def test_include_directories_follow_the_executable(tmp_path):
    executable = fake_installation(tmp_path / "prefix")
    include = tmp_path / "prefix" / "share" / "povray-3.7" / "include"
    assert include in include_directories(executable)
    assert missing_includes([ONLY_HERE, "surely-not-installed.inc"], executable) == [
        "surely-not-installed.inc"
    ]
    # Another installation does not see these files.
    other = fake_installation(tmp_path / "other")
    (tmp_path / "other" / "share" / "povray-3.7" / "include" / ONLY_HERE).unlink()
    assert missing_includes([ONLY_HERE], other) == [ONLY_HERE]


def test_library_path_of_the_installation_is_read(tmp_path):
    executable = fake_installation(tmp_path / "prefix")
    library = tmp_path / "library with spaces"
    library.mkdir()
    (library / "extra.inc").write_text("// test\n")
    ini = tmp_path / "prefix" / "etc" / "povray" / "3.7" / "povray.ini"
    ini.parent.mkdir(parents=True)
    ini.write_text(f'; settings\nLibrary_Path="{library}"\nLibrary_Path="{tmp_path / "gone"}"\n')
    directories = include_directories(executable)
    assert library in directories and tmp_path / "gone" not in directories
    assert missing_includes(["extra.inc", ONLY_HERE], executable) == []


def test_linked_executable_finds_the_real_installation(tmp_path):
    """Package managers link the executable (Homebrew: bin/povray -> Cellar/…/bin/povray)."""
    real = fake_installation(tmp_path / "cellar" / "povray" / "3.7")
    link = tmp_path / "prefix" / "bin" / "povray"
    link.parent.mkdir(parents=True)
    try:
        link.symlink_to(real)
    except OSError:
        pytest.skip("symbolic links are not available here")
    assert missing_includes([ONLY_HERE], link) == []


def test_include_lookup_without_povray(tmp_path, monkeypatch):
    monkeypatch.setenv("PATH", str(tmp_path))
    monkeypatch.delenv(POVRAY_ENV, raising=False)
    assert all(directory.is_dir() for directory in include_directories())
    assert missing_includes([ONLY_HERE]) == [ONLY_HERE]
    # The environment variable names the installation to search.
    monkeypatch.setenv(POVRAY_ENV, str(fake_installation(tmp_path / "prefix")))
    assert missing_includes([ONLY_HERE]) == []


# ----- interface choices ---------------------------------------------------------------------
def test_windows_only_interface_choices():
    assert executable_filter("linux") == "" and executable_filter("darwin") == ""
    assert executable_filter("win32").startswith("Programs (*.exe)")
    assert not set_taskbar_identity("linux") and not set_taskbar_identity("darwin")
    if sys.platform == "win32":  # sets the id of this test process; harmless
        assert set_taskbar_identity()


def test_native_key_names():
    text = "Undo (Ctrl+Z) · Ctrl + click"
    assert native_keys(text, "linux") == text and native_keys(text, "win32") == text
    assert native_keys(text, "darwin") == "Undo (⌘+Z) · ⌘ + click"
    assert native_keys("Fit (F)", "darwin") == "Fit (F)"


def test_personal_thumbnails_stay_out_of_shared_folders(tmp_path):
    ini = QSettings(str(tmp_path / "own folder" / "Ycrystal.ini"), QSettings.Format.IniFormat)
    for platform in ("linux", "darwin", "win32"):  # a settings file of its own: next to it
        folder = personal_thumbnail_directory(ini, platform)
        assert folder == tmp_path / "own folder" / THUMBNAIL_FOLDER
    native = QSettings(
        QSettings.Format.NativeFormat, QSettings.Scope.UserScope, "Ycrystal-tests", "Ycrystal-tests"
    )
    beside = Path(native.fileName()).parent / THUMBNAIL_FOLDER
    assert personal_thumbnail_directory(native, "linux") == beside
    data = Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation))
    for platform in ("darwin", "win32"):  # property list in a shared folder / the registry
        assert personal_thumbnail_directory(native, platform) == data / THUMBNAIL_FOLDER
    if sys.platform == "darwin":
        assert "Preferences" not in personal_thumbnail_directory(native).parts


# ----- Linux menu launcher -------------------------------------------------------------------
def test_launcher_command_applies_to_linux_and_windows_only(tmp_path, monkeypatch, capsys):
    assert desktop_supported("linux") and desktop_supported("freebsd14")
    assert desktop_supported("win32")  # the Start menu (tests/test_windows_desktop.py)
    assert not desktop_supported("darwin")
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    monkeypatch.setattr("ycrystal.desktop.desktop_supported", lambda: False)
    for option in ("--install-desktop", "--uninstall-desktop"):
        assert main([option]) == 1
        assert "applications menu of Linux" in capsys.readouterr().err
    assert list(tmp_path.iterdir()) == []  # nothing was written
    monkeypatch.setattr("ycrystal.desktop.desktop_supported", lambda: True)
    monkeypatch.setattr(sys, "platform", "linux")  # the Linux launcher, on any system
    assert main(["--install-desktop"]) == 0
    assert (tmp_path / "applications" / "ycrystal.desktop").is_file()
    assert main(["--uninstall-desktop"]) == 0
    assert not (tmp_path / "applications" / "ycrystal.desktop").exists()


# ----- the test suite's own display check ----------------------------------------------------
def test_display_check_knows_each_platform(monkeypatch):
    for name in ("DISPLAY", "WAYLAND_DISPLAY", "QT_QPA_PLATFORM"):
        monkeypatch.delenv(name, raising=False)
    for platform, expected in (("linux", False), ("darwin", True), ("win32", True)):
        monkeypatch.setattr(sys, "platform", platform)
        assert conftest.display_available() is expected, platform
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")  # no OpenGL window on any platform
    assert not conftest.display_available()
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.delenv("QT_QPA_PLATFORM")
    monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-0")
    assert conftest.display_available()
