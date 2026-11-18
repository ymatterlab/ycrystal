"""The packaged Windows Ycrystal (``packaging/windows``), checked on every system.

The installer itself is built and tried by ``packaging/windows/build.ps1`` and
``coexistence-check.ps1`` (and the Windows installer CI workflow). These tests keep the
Inno Setup script, the PyInstaller specification, and the Python code consistent: the
packaged program and an installation from source must never share a shortcut,
application id, or file type, and the packaged program must not write the source
installation's Start-menu entry.
"""

import re
import subprocess
import sys
from pathlib import Path

from ycrystal import __version__, desktop
from ycrystal.app import main
from ycrystal.gui.native import WINDOWS_APP_ID, WINDOWS_PACKAGED_APP_ID, windows_app_id

ROOT = Path(__file__).resolve().parents[1]
PACKAGING = ROOT / "packaging" / "windows"
ISS = (PACKAGING / "ycrystal.iss").read_text(encoding="utf-8")
SPEC = (PACKAGING / "ycrystal.spec").read_text(encoding="utf-8")
CHECK = (PACKAGING / "coexistence-check.ps1").read_text(encoding="utf-8")


def _define(name: str) -> str:
    return re.search(rf'^#define {name} "([^"]+)"', ISS, re.MULTILINE).group(1)


def _setup(name: str) -> str:
    return re.search(rf"^{name}=(.+)$", ISS, re.MULTILINE).group(1).strip()


def test_packaged_and_source_identities_differ():
    assert _define("AppUserModelId") == WINDOWS_PACKAGED_APP_ID != WINDOWS_APP_ID
    assert _define("ProgId") == "YMatterLab.Ycrystal.Project" != desktop.WINDOWS_PROG_ID
    shortcut = re.search(r'^Name: "\{autoprograms\}\\([^"]+)"', ISS, re.MULTILINE).group(1)
    assert f"{shortcut}.lnk" == desktop.LEGACY_SHORTCUT_NAME != desktop.SHORTCUT_NAME
    assert 'AppUserModelID: "{#AppUserModelId}"' in ISS  # the shortcut carries the id
    assert windows_app_id(frozen=True) == WINDOWS_PACKAGED_APP_ID
    assert windows_app_id(frozen=False) == WINDOWS_APP_ID


def test_installer_removes_only_what_it_wrote():
    rules = [line for line in ISS.splitlines() if line.startswith("Root: HKA")]
    assert rules and all("Software\\Classes" in rule for rule in rules)
    default = [r for r in rules if 'Subkey: "Software\\Classes\\.ycrystal";' in r]
    assert len(default) == 1 and "uninsdelete" not in default[0]  # see [Code]
    assert "RegQueryStringValue(HKA, 'Software\\Classes\\.ycrystal', '', Value)" in ISS
    assert "(Value = '{#ProgId}')" in ISS
    own_key = 'Root: HKA; Subkey: "Software\\Classes\\{#ProgId}";'
    prog_id = [r for r in rules if r.startswith(own_key)]
    assert any("uninsdeletekey" in r for r in prog_id)
    assert "Y-Matter Lab" not in "".join(rules)  # the shared settings are never touched
    assert "UninstallDelete" not in ISS


def test_installer_ids_are_shared_with_the_check_and_stay_fixed():
    app_id = _setup("AppId").removeprefix("{{").removesuffix("}")
    assert re.fullmatch(r"[0-9A-F]{8}(-[0-9A-F]{4}){3}-[0-9A-F]{12}", app_id)
    assert app_id == "96A7291E-332A-4D2A-ACAD-E2489153A771"  # never change: updates need it
    assert f"{{{app_id}}}_is1" in CHECK
    assert _setup("PrivilegesRequired") == "lowest"  # no administrator rights by default
    assert _setup("ArchitecturesInstallIn64BitMode") == "x64compatible"


def test_specification_builds_both_programs_from_the_entry_scripts():
    for script in ("ycrystal_gui.py", "ycrystal_cli.py"):
        assert (PACKAGING / script).is_file() and f'analysis("{script}")' in SPEC
    assert re.search(r'name="Ycrystal",\s*console=False', SPEC)
    assert re.search(r'name="ycrystal-cli",\s*console=True', SPEC)
    assert 'collect_data_files("ycrystal")' in SPEC  # presets, thumbnails, icon
    # The installer copies the folder PyInstaller makes, under the name it gives it.
    assert re.search(r'COLLECT\([^)]*name="Ycrystal"', SPEC, re.DOTALL)
    assert "dist\\windows\\Ycrystal" in ISS


def test_entry_script_runs_the_application(tmp_path):
    result = subprocess.run(
        [sys.executable, str(PACKAGING / "ycrystal_cli.py"), "--version"],
        capture_output=True,
        text=True,
        timeout=120,
        cwd=tmp_path,
    )
    assert result.returncode == 0 and result.stdout.strip() == f"ycrystal {__version__}"


def test_packaged_program_refuses_the_source_menu_entry(monkeypatch, capsys, tmp_path):
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    assert desktop.is_packaged() and not desktop.is_packaged(frozen=False)
    for option in ("--install-desktop", "--uninstall-desktop"):
        assert main([option]) == 1
        assert "its installer manages its Start-menu entry" in capsys.readouterr().err
    assert list(tmp_path.iterdir()) == []  # nothing written
    monkeypatch.delattr(sys, "frozen")
    assert not desktop.is_packaged()
