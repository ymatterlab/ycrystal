# PyInstaller specification of the packaged Ycrystal for Windows (x64).
#
# Built by packaging/windows/build.ps1, which first draws build/windows/ycrystal.ico.
# Result: one folder (dist/windows/Ycrystal) with two programs that share the bundled
# Python and libraries in its _internal folder:
#   Ycrystal.exe      the window, without a console (Start menu, file type);
#   ycrystal-cli.exe  the command line, with a console (--render, --check-renderer).
# POV-Ray is not bundled: the program finds POV-Ray for Windows as the installation
# from source does (ycrystal.render.povray).
# See docs/development/windows-installer.md.

import importlib.metadata
import re
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules
from PyInstaller.utils.win32.versioninfo import (
    FixedFileInfo,
    StringFileInfo,
    StringStruct,
    StringTable,
    VarFileInfo,
    VarStruct,
    VSVersionInfo,
)

HERE = Path(SPECPATH)  # noqa: F821 - defined by PyInstaller
ROOT = HERE.parents[1]
ICON = ROOT / "build" / "windows" / "ycrystal.ico"

VERSION = re.search(
    r'__version__\s*=\s*"([^"]+)"', (ROOT / "src" / "ycrystal" / "__init__.py").read_text()
).group(1)
NUMBERS = tuple(int(n) for n in re.match(r"(\d+)\.(\d+)\.(\d+)", VERSION).groups()) + (0,)

# The package's own modules and data (presets, thumbnails, icon); ASE chooses its file
# readers by name at run time and reads data files (space groups) of its own.
HIDDEN = collect_submodules("ycrystal") + collect_submodules("ase.io") + ["PySide6.QtSvg"]
DATAS = collect_data_files("ycrystal") + collect_data_files("ase")
EXCLUDES = ["tkinter", "_tkinter", "PyQt5", "PyQt6", "PySide2", "IPython", "pytest"]

# Licence texts of the bundled Python and of every installed distribution except the
# build tools (THIRD_PARTY_NOTICES.md lists them).
BUILD_TOOLS = {"pyinstaller", "pyinstaller-hooks-contrib", "altgraph", "pefile",
               "pywin32-ctypes", "pip", "setuptools", "wheel"}
LICENCE_NAME = re.compile(r"^(licen[cs]e|copying|notice|authors)", re.IGNORECASE)


def licence_files():
    found = []
    python_licence = Path(sys.base_prefix) / "LICENSE.txt"
    if python_licence.is_file():
        found.append((str(python_licence), "licenses/Python"))
    for dist in importlib.metadata.distributions():
        name = dist.metadata["Name"]
        if not name or name.lower() in BUILD_TOOLS:
            continue
        for entry in dist.files or []:
            parts = Path(str(entry)).parts
            in_licence_folder = any(part.lower() in ("licenses", "licences") for part in parts)
            if not (LICENCE_NAME.match(parts[-1]) or in_licence_folder):
                continue
            source = Path(str(dist.locate_file(entry)))
            if source.is_file() and ".dist-info" in str(entry):
                inner = Path(*[p for p in parts[1:-1]]) if len(parts) > 2 else Path()
                found.append((str(source), str(Path("licenses") / name / inner)))
    return found


def version_info(description, filename):
    strings = [
        StringStruct("CompanyName", "Y-Matter Lab"),
        StringStruct("FileDescription", description),
        StringStruct("FileVersion", VERSION),
        StringStruct("InternalName", filename.removesuffix(".exe")),
        StringStruct("LegalCopyright", "MIT License, Y-Matter Lab"),
        StringStruct("OriginalFilename", filename),
        StringStruct("ProductName", "Ycrystal"),
        StringStruct("ProductVersion", VERSION),
    ]
    return VSVersionInfo(
        ffi=FixedFileInfo(filevers=NUMBERS, prodvers=NUMBERS),
        kids=[
            StringFileInfo([StringTable("040904B0", strings)]),
            VarFileInfo([VarStruct("Translation", [1033, 1200])]),
        ],
    )


def analysis(script):
    return Analysis(  # noqa: F821 - defined by PyInstaller
        [str(HERE / script)],
        pathex=[],
        binaries=[],
        datas=DATAS + licence_files(),
        hiddenimports=HIDDEN,
        excludes=EXCLUDES,
        # ASE (LGPL) as plain source files in _internal\ase, not in the archive, so that
        # users can replace it; Qt for Python is a set of separate library files anyway.
        module_collection_mode={"ase": "py"},
        noarchive=False,
    )


gui = analysis("ycrystal_gui.py")
cli = analysis("ycrystal_cli.py")

gui_exe = EXE(  # noqa: F821
    PYZ(gui.pure),  # noqa: F821
    gui.scripts,
    [],
    exclude_binaries=True,
    name="Ycrystal",
    console=False,
    icon=str(ICON),
    version=version_info("Ycrystal", "Ycrystal.exe"),
    upx=False,
)
cli_exe = EXE(  # noqa: F821
    PYZ(cli.pure),  # noqa: F821
    cli.scripts,
    [],
    exclude_binaries=True,
    name="ycrystal-cli",
    console=True,
    icon=str(ICON),
    version=version_info("Ycrystal command line", "ycrystal-cli.exe"),
    upx=False,
)
COLLECT(  # noqa: F821
    gui_exe,
    gui.binaries,
    gui.datas,
    cli_exe,
    cli.binaries,
    cli.datas,
    name="Ycrystal",
    upx=False,
)
