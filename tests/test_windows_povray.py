"""POV-Ray for Windows support, tested on every system.

POV-Ray for Windows (``pvengine64.exe``) is a window program without a ``povray``
command: Ycrystal finds it outside ``PATH``, starts it minimised with
``/EXIT /NR +GA<log>`` and an INI file, keeps it from taking the keyboard focus, and
reads its messages from the log file. These tests check that contract with a stand-in
program; the real program is exercised by the POV-Ray tests on a Windows computer
where it is installed (see ``docs/development/windows-port.md``).
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


real_settings_file = povray._engine_settings_file


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
    progress = []
    process.progress.connect(progress.append)
    with qtbot.waitSignal(process.finished, timeout=60_000) as blocker:
        process.start()
    result = blocker.args[0]
    assert result.ok and "Render completed." in result.log
    assert progress == [100]  # it prints no progress; the end is reported
    assert not process.is_running() and result.elapsed > 0
    arguments = (process.job.directory / "arguments.txt").read_text().splitlines()
    assert arguments == ["/EXIT", "/NR", f"+GA{LOG_NAME}", "scene.ini"]

    failing = RenderProcess(job_in(tmp_path), engine(tmp_path, fail=True))
    with qtbot.waitSignal(failing.finished, timeout=60_000) as blocker:
        failing.start()
    result = blocker.args[0]
    assert not result.ok and result.returncode == 0  # it exits 0 even after a parse error
    assert "metals.inc" in result.message


def test_background_process_of_povray_for_windows_cancels_and_reports_start_failure(
    qtbot, tmp_path
):
    from ycrystal.render.process import RenderProcess

    slow = python_program(tmp_path / "pvengine-slow", "import time\ntime.sleep(5)\n")
    process = RenderProcess(job_in(tmp_path), slow)
    done = []
    process.finished.connect(done.append)
    process.start()
    assert process.is_running()
    process.cancel()
    qtbot.waitUntil(lambda: bool(done), timeout=10_000)
    assert done == [done[0]] and done[0].cancelled and not done[0].ok
    assert done[0].message == "Render cancelled." and not process.is_running()

    missing = RenderProcess(job_in(tmp_path), str(tmp_path / "nowhere" / "pvengine64.exe"))
    failed = []
    missing.finished.connect(failed.append)
    missing.start()
    qtbot.waitUntil(lambda: bool(failed), timeout=5_000)
    assert not failed[0].ok and "Could not start POV-Ray" in failed[0].message
    assert not missing.is_running() and povray._foreground_holds == 0


def test_preview_queue_supersedes_povray_for_windows(qtbot, tmp_path):
    from ycrystal.render.process import RenderQueue

    slow = python_program(tmp_path / "pvengine-slow", "import time\ntime.sleep(5)\n")
    queue = RenderQueue()
    finished = []
    queue.finished.connect(lambda result, tag: finished.append((tag, result.ok, result.cancelled)))
    queue.submit(job_in(tmp_path), slow, "A")
    queue.submit(job_in(tmp_path), engine(tmp_path), "B")  # cancels A, then runs
    qtbot.waitUntil(lambda: not queue.is_busy(), timeout=20_000)
    assert finished == [("A", False, True), ("B", True, False)]


def test_renders_with_povray_for_windows_take_turns(qtbot, tmp_path):
    """POV-Ray for Windows runs once at a time (Keep Single Instance): no overlap."""
    from ycrystal.render.process import RenderProcess

    order = tmp_path / "order.txt"
    code = (
        "import time\nfrom pathlib import Path\n"
        f"log = Path({str(order)!r})\n"
        "with log.open('a') as f: f.write('start\\n')\n"
        "time.sleep(1.0)\n"
        "Path('scene.png').write_bytes(b'PNG stand-in')\n"
        "with log.open('a') as f: f.write('end\\n')\n"
    )
    program = python_program(tmp_path / "pvengine-turns", code)
    first, second, third = (RenderProcess(job_in(tmp_path), program) for _ in range(3))
    done = []
    for process in (first, second, third):
        process.finished.connect(lambda result, p=process: done.append((p, result)))
        process.start()
    assert first.is_running() and second.is_running() and third.is_running()
    third.cancel()  # still waiting for its turn: it never starts
    assert done[0][0] is third and done[0][1].cancelled and not third.is_running()
    qtbot.waitUntil(lambda: len(done) == 3, timeout=30_000)
    assert [p for p, _ in done] == [third, first, second]
    assert all(result.ok for _, result in done[1:])
    assert order.read_text().split() == ["start", "end", "start", "end"]


def test_a_render_deleted_before_it_ended_does_not_hold_up_the_next(qtbot, tmp_path, monkeypatch):
    """A window closed with a render running: its Qt object may be gone before the end."""
    import shiboken6

    from ycrystal.render.process import RenderProcess

    monkeypatch.setattr(povray, "_lock_foreground", lambda lock: None)
    monkeypatch.setattr(povray, "_foreground_holds", 0)
    slow = python_program(tmp_path / "pvengine-slow", "import time\ntime.sleep(30)\n")
    cancelled = RenderProcess(job_in(tmp_path), slow)
    done = []
    cancelled.finished.connect(done.append)
    cancelled.start()
    cancelled.cancel()
    assert done and done[0].cancelled  # at once, not at a later check
    shiboken6.delete(cancelled)

    orphan = RenderProcess(job_in(tmp_path), slow)
    orphan.start()
    popen = orphan._popen
    shiboken6.delete(orphan)  # deleted while running, without cancelling
    popen.kill()
    popen.wait()
    later = RenderProcess(job_in(tmp_path), engine(tmp_path))
    with qtbot.waitSignal(later.finished, timeout=20_000) as blocker:
        later.start()
    assert blocker.args[0].ok


def test_open_povray_for_windows_is_reported_before_starting(qtbot, tmp_path, monkeypatch):
    from ycrystal.render.povray import ENGINE_OPEN_MESSAGE, windows_engine_conflict
    from ycrystal.render.process import RenderProcess

    seen = []
    monkeypatch.setattr(povray, "_engine_window_open", lambda classes: seen.append(classes) or True)
    monkeypatch.setattr(povray, "_engine_settings_file", lambda: None)  # default: single
    monkeypatch.setattr(povray, "editor_question_pending", lambda *args: False)  # settled
    assert windows_engine_conflict("pvengine64.exe", "linux") is None
    assert windows_engine_conflict("/usr/bin/povray", "win32") is None
    assert seen == []
    assert windows_engine_conflict("C:/POV/bin/pvengine64.exe", "win32") == ENGINE_OPEN_MESSAGE
    assert seen[-1][0] == "Pov37-Win64-MainWinClass"  # what the 64-bit build looks for
    windows_engine_conflict("pvengine.exe", "win32")
    assert seen[-1][0] == "Pov37-Win32-MainWinClass"
    # With Keep Single Instance off, a second copy starts normally. The setting is read
    # from the user folder recorded by the installer.
    documents = tmp_path / "Documents" / "POV-Ray" / "v3.7"
    (documents / "ini").mkdir(parents=True)
    (documents / "ini" / "pvengine.ini").write_text("[General]\nOneInstance=0\n")
    monkeypatch.setattr(povray, "_registry_user_folders", lambda: [str(documents)])
    monkeypatch.setattr(povray, "_engine_settings_file", real_settings_file)
    assert povray._engine_settings_file() == documents / "ini" / "pvengine.ini"
    assert windows_engine_conflict("pvengine64.exe", "win32") is None
    (documents / "ini" / "pvengine.ini").write_text("[General]\nOneInstance=1\n")
    assert windows_engine_conflict("pvengine64.exe", "win32") == ENGINE_OPEN_MESSAGE
    monkeypatch.setattr(povray, "_engine_window_open", lambda classes: False)
    assert windows_engine_conflict("pvengine64.exe", "win32") is None  # none is open

    # Rendering: the program is never started, and the result explains why.
    marker = tmp_path / "started"
    program = python_program(tmp_path / "pvengine-marker", f"open({str(marker)!r}, 'w')\n")
    monkeypatch.setattr("ycrystal.render.jobs.windows_engine_conflict", lambda exe: "open!")
    result = run_job(job_in(tmp_path), program)
    assert not result.ok and result.message == "open!" and not marker.exists()
    monkeypatch.setattr("ycrystal.render.process.windows_engine_conflict", lambda exe: "open!")
    process = RenderProcess(job_in(tmp_path), program)
    with qtbot.waitSignal(process.finished, timeout=10_000) as blocker:
        process.start()
    assert blocker.args[0].message == "open!" and not blocker.args[0].ok
    assert not marker.exists() and povray._foreground_holds == 0


def test_editor_question_is_reported_before_starting(tmp_path, monkeypatch):
    """POV-Ray for Windows would wait at its question about a missing editor."""
    from ycrystal.render.povray import (
        EDITOR_QUESTION_MESSAGE,
        editor_question_pending,
        windows_engine_conflict,
    )

    home = tmp_path / "POV-Ray" / "v3.7"
    executable = home / "bin" / "pvengine64.exe"
    executable.parent.mkdir(parents=True)
    executable.write_bytes(b"MZ")
    ini = tmp_path / "Documents" / "pvengine.ini"
    ini.parent.mkdir()
    assert editor_question_pending(executable, None)  # never started: the option is on
    assert editor_question_pending(executable, ini)  # no settings file yet: the same
    ini.write_text("[General]\nUseEditors=0\n")  # Options > Other Settings > Use Editor off
    assert not editor_question_pending(executable, ini)
    ini.write_text("[General]\nUseEditors=1\n")
    assert editor_question_pending(executable, ini)
    elsewhere = tmp_path / "Recorded" / "bin"  # the installation folder in the registry
    elsewhere.mkdir(parents=True)
    (elsewhere / "cmedit64.dll").write_bytes(b"MZ")
    assert not editor_question_pending(executable, ini, [str(elsewhere.parent)])
    (executable.parent / "cmedit32.dll").write_bytes(b"MZ")  # the 32-bit build's
    assert editor_question_pending(executable, ini)
    (executable.parent / "cmedit64.dll").write_bytes(b"MZ")  # the editor is installed
    assert not editor_question_pending(executable, ini)
    # Programs that are not POV-Ray for Windows, and stand-ins in tests, never ask.
    for other in ("/usr/bin/povray", tmp_path / "pvengine.cmd"):
        assert not editor_question_pending(other, None)

    # Rendering: reported before POV-Ray starts, on Windows only.
    (executable.parent / "cmedit64.dll").unlink()
    monkeypatch.setattr(povray, "_engine_settings_file", lambda: ini)
    monkeypatch.setattr(povray, "_registry_homes", lambda: [])
    monkeypatch.setattr(povray, "_engine_window_open", lambda classes: False)
    assert windows_engine_conflict(executable, "win32") == EDITOR_QUESTION_MESSAGE
    assert windows_engine_conflict(executable, "linux") is None
    ini.write_text("[General]\nUseEditors=0\n")
    assert windows_engine_conflict(executable, "win32") is None


def test_single_instance_setting_is_read_as_povray_reads_it(tmp_path):
    from ycrystal.render.povray import keeps_single_instance

    ini = tmp_path / "pvengine.ini"
    assert keeps_single_instance(ini)  # no settings file: the default, on
    for text, expected in (
        ("[General]\nRunCount=3\n", True),
        ("[General]\nOneInstance=0\n", False),
        ("[general]\n oneinstance = 0 \n", False),
        ("[General]\nOneInstance=1\n", True),
        ("[General]\nOneInstance=\n", False),  # GetPrivateProfileInt reads 0
        ("[Other]\nOneInstance=0\n[General]\nRunCount=1\n", True),
    ):
        ini.write_text(text)
        assert keeps_single_instance(ini) is expected, text


def test_foreground_holds_are_counted(monkeypatch):
    calls = []
    monkeypatch.setattr(povray, "_lock_foreground", calls.append)
    monkeypatch.setattr(povray, "_foreground_holds", 0)
    assert not povray.hold_foreground("/usr/bin/povray", "win32")  # prints, keeps no window
    assert not povray.hold_foreground("pvengine64.exe", "linux")
    assert calls == []
    assert povray.hold_foreground("pvengine64.exe", "win32")  # a preview
    assert povray.hold_foreground("pvengine64.exe", "win32")  # and a final render
    assert calls == [True, True]  # asked again: Windows lifts it when the user clicks
    povray.release_foreground()
    assert calls == [True, True]  # one render still runs
    povray.release_foreground()
    povray.release_foreground()  # an extra release changes nothing
    assert calls == [True, True, False] and povray._foreground_holds == 0


def test_renders_with_povray_for_windows_end_their_foreground_hold(qtbot, tmp_path, monkeypatch):
    from ycrystal.render.process import RenderProcess

    calls = []
    monkeypatch.setattr(povray, "_lock_foreground", calls.append)
    expected = [True, False] if sys.platform == "win32" else []  # held on Windows only
    assert run_job(job_in(tmp_path), engine(tmp_path)).ok
    assert calls == expected and povray._foreground_holds == 0
    calls.clear()
    process = RenderProcess(job_in(tmp_path), engine(tmp_path))
    with qtbot.waitSignal(process.finished, timeout=60_000):
        process.start()
    assert calls == expected and povray._foreground_holds == 0


def test_user_files_folder_recorded_by_the_installer(tmp_path, monkeypatch):
    """POV-Ray for Windows records where it put its include files (``DocPath``)."""
    from ycrystal.render.povray import include_directories, missing_includes

    # Test-only names: a system include folder (Linux) must not count.
    ONLY_HERE = "ycrystal-test-only.inc"  # noqa: N806
    # A version folder of its own, so that a real installation's files cannot count.
    executable = tmp_path / "Program Files" / "POV-Ray" / "v-test" / "bin" / "pvengine64.exe"
    executable.parent.mkdir(parents=True)
    executable.write_bytes(b"MZ")
    monkeypatch.setattr(povray, "_registry_user_folders", lambda: [])
    documents = tmp_path / "OneDrive" / "Documents" / "POV-Ray" / "v-test"  # a moved folder
    (documents / "include").mkdir(parents=True)
    (documents / "include" / ONLY_HERE).write_text("// test\n")
    library = tmp_path / "my includes"
    library.mkdir()
    (library / "extra.inc").write_text("// test\n")
    (documents / "ini").mkdir()
    (documents / "ini" / "povray.ini").write_text(f'Library_Path="{library}"\n')
    assert missing_includes([ONLY_HERE, "extra.inc"], executable) == [
        ONLY_HERE,
        "extra.inc",
    ]
    monkeypatch.setattr(povray, "_registry_user_folders", lambda: [str(documents)])
    assert missing_includes([ONLY_HERE, "extra.inc"], executable) == []
    directories = include_directories(executable)
    assert documents / "include" in directories and library in directories


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
