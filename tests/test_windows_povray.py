"""POV-Ray for Windows support, tested on every system.

POV-Ray for Windows (``pvengine64.exe``) is a window program without a ``povray``
command: Ycrystal finds it outside ``PATH``, starts it with ``/EXIT /NR +GA<log>``
and an INI file, and reads its messages from the log file. These tests check that
contract with a stand-in program; the real program is exercised by the Windows CI job
(see ``docs/development/windows-port.md``).
"""

import os
import sys
from pathlib import Path

import pytest

from conftest import python_program
from ycrystal.core.camera import Camera
from ycrystal.core.scene import Environment
from ycrystal.render import povray
from ycrystal.render.jobs import prepare_job, run_job
from ycrystal.render.pov_writer import RenderSettings
from ycrystal.render.povray import (
    LOG_NAME,
    POVRAY_ENV,
    PovrayNotFoundError,
    find_povray,
    installed_windows_engine,
    is_windows_engine,
    povray_version,
    read_log,
    render_arguments,
    windows_engine_candidates,
)

ENGINE = """
    import sys
    from pathlib import Path
    Path("arguments.txt").write_text("\\n".join(sys.argv[1:]))
    log = next(a[3:] for a in sys.argv[1:] if a.startswith("+GA"))
    ini = Path(sys.argv[-1]).read_text()
    if {fail!r}:
        Path(log).write_text("POV-Ray for Windows (stand-in)\\n"
                             "Parse Error: Cannot open include file metals.inc.\\n")
    else:
        Path("scene.png").write_bytes(b"\\x89PNG stand-in")
        Path(log).write_text("POV-Ray for Windows (stand-in)\\nRender completed.\\n")
    """
"""A stand-in for POV-Ray for Windows: prints nothing, writes its log file, exits 0."""


def engine(folder: Path, fail: bool = False) -> str:
    return python_program(
        folder / ("pvengine-fail" if fail else "pvengine"), ENGINE.format(fail=fail)
    )


def job_in(folder: Path):
    camera = Camera(position=(0, 0, 10), focal_point=(0, 0, 0), view_up=(0, 1, 0), parallel_scale=2)
    from conftest import spread_geometry

    return prepare_job(
        spread_geometry(), camera, Environment(), RenderSettings(32, 24), parent=folder
    )


def test_engine_names_and_arguments():
    assert is_windows_engine(r"C:\Program Files\POV-Ray\v3.7\bin\pvengine64.exe")
    assert is_windows_engine("D:/tools/PVENGINE.EXE") and is_windows_engine("pvengine32-sse2.exe")
    assert not is_windows_engine("/usr/bin/povray") and not is_windows_engine("povray.exe")
    assert render_arguments("povray", "scene.ini") == ["scene.ini"]
    assert render_arguments("pvengine64.exe", "scene.ini") == [
        "/EXIT",
        "/NR",
        f"+GA{LOG_NAME}",
        "scene.ini",
    ]


def test_installation_candidates_come_from_registry_and_program_folders():
    environ = {
        "ProgramW6432": "C:/Program Files",
        "ProgramFiles": "C:/Program Files",  # the same folder: listed once
        "ProgramFiles(x86)": "C:/Program Files (x86)",
    }
    paths = [p.as_posix() for p in windows_engine_candidates(environ, ["E:/POV-Ray 3.7"])]
    assert paths[:3] == [
        "E:/POV-Ray 3.7/bin/pvengine64.exe",
        "E:/POV-Ray 3.7/bin/pvengine.exe",
        "E:/POV-Ray 3.7/bin/pvengine32-sse2.exe",
    ]
    assert paths[3] == "C:/Program Files/POV-Ray/v3.7/bin/pvengine64.exe"
    assert paths[-1] == "C:/Program Files (x86)/POV-Ray/v3.7/bin/pvengine32-sse2.exe"
    assert len(paths) == len(set(paths)) == 9
    assert windows_engine_candidates({}) == []


def test_installed_engine_is_searched_only_on_windows(tmp_path, monkeypatch):
    program_files = tmp_path / "Program Files"
    executable = program_files / "POV-Ray" / "v3.7" / "bin" / "pvengine64.exe"
    executable.parent.mkdir(parents=True)
    executable.write_bytes(b"MZ")
    for variable in ("ProgramW6432", "ProgramFiles(x86)"):
        monkeypatch.delenv(variable, raising=False)
    monkeypatch.setenv("ProgramFiles", str(program_files))
    monkeypatch.setenv("PATH", str(tmp_path / "empty"))
    monkeypatch.setattr(povray, "_registry_homes", lambda: [])
    assert installed_windows_engine("linux") is None and installed_windows_engine("darwin") is None
    assert installed_windows_engine("win32") == str(executable)
    # A folder recorded in the registry comes first.
    other = tmp_path / "D" / "POV-Ray" / "bin" / "pvengine.exe"
    other.parent.mkdir(parents=True)
    other.write_bytes(b"MZ")
    monkeypatch.setattr(povray, "_registry_homes", lambda: [str(other.parent.parent)])
    assert installed_windows_engine("win32") == str(other)


def test_find_povray_falls_back_to_povray_for_windows(tmp_path, monkeypatch):
    monkeypatch.setenv("PATH", str(tmp_path))
    monkeypatch.delenv(POVRAY_ENV, raising=False)
    monkeypatch.setattr(povray, "installed_windows_engine", lambda: "C:/POV/bin/pvengine64.exe")
    assert find_povray() == "C:/POV/bin/pvengine64.exe"
    monkeypatch.setattr(povray, "installed_windows_engine", lambda: None)
    with pytest.raises(PovrayNotFoundError, match="POV-Ray for Windows 3.7"):
        find_povray()


def test_version_query_never_starts_povray_for_windows(tmp_path):
    marker = tmp_path / "started"
    program = python_program(tmp_path / "pvengine", f"open({str(marker)!r}, 'w')\n")
    assert povray_version(program) is None  # no version resource in a stand-in
    assert not marker.exists()  # its window was never opened


def test_render_with_povray_for_windows_reads_its_log(tmp_path):
    job = job_in(tmp_path)
    result = run_job(job, engine(tmp_path))
    assert result.ok and result.image_path == job.image_path
    assert "Render completed." in result.log
    arguments = (job.directory / "arguments.txt").read_text().splitlines()
    assert arguments == ["/EXIT", "/NR", f"+GA{LOG_NAME}", "scene.ini"]
    assert read_log(job.directory).startswith("POV-Ray for Windows")
    assert read_log(tmp_path / "nowhere") == ""


def test_failure_of_povray_for_windows_is_explained_from_its_log(tmp_path):
    result = run_job(job_in(tmp_path), engine(tmp_path, fail=True))
    assert not result.ok and result.image_path is None
    assert "include file" in result.message and "metals.inc" in result.message


def test_background_process_reads_the_log(qtbot, tmp_path):
    from ycrystal.render.process import RenderProcess

    process = RenderProcess(job_in(tmp_path), engine(tmp_path))
    with qtbot.waitSignal(process.finished, timeout=60_000) as blocker:
        process.start()
    result = blocker.args[0]
    assert result.ok and "Render completed." in result.log


@pytest.mark.skipif(sys.platform != "win32", reason="the real POV-Ray for Windows")
def test_installed_povray_for_windows_is_found():
    """On the Windows CI runner POV-Ray for Windows is installed but not on PATH."""
    found = installed_windows_engine()
    if found is None:
        pytest.skip("POV-Ray for Windows is not installed here")
    assert is_windows_engine(found) and os.path.isfile(found)
    version = povray_version(found)
    assert version is None or version.startswith("3.7")


def test_include_files_of_a_povray_for_windows_installation(tmp_path):
    from ycrystal.render.povray import include_directories, missing_includes

    home = tmp_path / "Program Files" / "POV-Ray" / "v3.7"
    executable = home / "bin" / "pvengine64.exe"
    executable.parent.mkdir(parents=True)
    executable.write_bytes(b"MZ")
    (home / "include").mkdir()
    (home / "include" / "metals.inc").write_text("// test\n")
    assert home / "include" in include_directories(executable)
    assert missing_includes(["metals.inc", "not-here.inc"], executable) == ["not-here.inc"]
