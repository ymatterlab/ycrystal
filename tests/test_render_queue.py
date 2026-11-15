"""Non-blocking render processes: progress, cancellation, superseded previews, cleanup."""

import stat
from pathlib import Path

import pytest
from PIL import Image

from ycrystal.core.camera import default_camera
from ycrystal.core.samples import perovskite_srtio3
from ycrystal.core.scene import Environment, SceneSettings, build_geometry
from ycrystal.render.jobs import prepare_job
from ycrystal.render.pov_writer import RenderSettings
from ycrystal.render.process import RenderProcess, RenderQueue


def fake_povray(tmp_path: Path, seconds: float, exit_code: int = 0) -> str:
    """A stand-in POV-Ray: waits, prints progress, writes a tiny PNG, exits.

    Like the real renderer, ``--version`` only prints a version line: the GUI's version
    query runs in the caller's working directory, which must stay clean.
    """
    png = tmp_path / "tiny.png"
    Image.new("RGBA", (4, 4), (255, 0, 0, 255)).save(png)
    script = tmp_path / f"fake-povray-{seconds}-{exit_code}"
    script.write_text(
        "#!/bin/sh\n"
        'if [ "$1" = "--version" ]; then echo "POV-Ray 3.7.0.10"; exit 0; fi\n'
        f"sleep {seconds}\n"
        "echo 'Rendered 8 of 16 pixels (50%)'\n"
        f"cp '{png}' scene.png\n"
        f"exit {exit_code}\n"
    )
    script.chmod(script.stat().st_mode | stat.S_IXUSR)
    return str(script)


@pytest.fixture
def make_job(tmp_path):
    geometry = build_geometry(perovskite_srtio3(), SceneSettings())
    camera = default_camera(*geometry.points_and_radii(), 1.5)
    root = tmp_path / "jobs"
    root.mkdir()

    def make(width=120, height=80):
        return prepare_job(
            geometry, camera, Environment(), RenderSettings(width, height), parent=root
        )

    make.root = root
    return make


def test_queue_supersedes_running_and_pending_jobs(qtbot, tmp_path, make_job):
    slow = fake_povray(tmp_path, 1.0)
    queue = RenderQueue()
    started, finished = [], []
    queue.started.connect(started.append)
    queue.finished.connect(lambda result, tag: finished.append((tag, result.ok, result.cancelled)))
    queue.submit(make_job(), slow, "A")
    queue.submit(make_job(), slow, "B")  # waits behind A
    queue.submit(make_job(), slow, "C")  # replaces B before it starts
    assert queue.is_busy() and queue.current_tag == "A"
    qtbot.waitUntil(lambda: not queue.is_busy(), timeout=10_000)
    assert started == ["A", "C"]  # never two processes at once; B never ran
    assert finished == [("A", False, True), ("C", True, False)]
    assert list(make_job.root.iterdir()) == []  # every job directory removed


def test_queue_cancel_and_image_available_inside_slot(qtbot, tmp_path, make_job):
    queue = RenderQueue()
    seen = []
    queue.finished.connect(
        lambda result, tag: seen.append(
            (tag, result.ok, result.image_path is not None and result.image_path.is_file())
        )
    )
    queue.submit(make_job(), fake_povray(tmp_path, 0.1), 1)
    qtbot.waitUntil(lambda: bool(seen), timeout=10_000)
    assert seen == [(1, True, True)]  # the image still exists while slots run
    queue.submit(make_job(), fake_povray(tmp_path, 5.0), 2)
    queue.cancel()
    qtbot.waitUntil(lambda: len(seen) == 2, timeout=10_000)
    assert seen[1] == (2, False, False)
    assert list(make_job.root.iterdir()) == []


def test_process_reports_cancellation_progress_and_failure(qtbot, tmp_path, make_job):
    results, progress = [], []
    process = RenderProcess(make_job(), fake_povray(tmp_path, 0.1, exit_code=3))
    process.finished.connect(lambda result: results.append((result, process.is_running())))
    process.progress.connect(progress.append)
    process.start()
    qtbot.waitUntil(lambda: bool(results), timeout=10_000)
    result, running_in_slot = results[0]
    assert not result.ok and not result.cancelled and result.returncode == 3
    assert "exited with code 3" in result.message
    assert progress == [50] and not running_in_slot and result.elapsed > 0
    process.job.cleanup()

    slow = RenderProcess(make_job(), fake_povray(tmp_path, 5.0))
    done = []
    slow.finished.connect(done.append)
    slow.start()
    qtbot.waitUntil(slow.is_running, timeout=5_000)
    slow.cancel()
    qtbot.waitUntil(lambda: bool(done), timeout=10_000)
    assert done[0].cancelled and done[0].message == "Render cancelled." and not done[0].ok
    slow.job.cleanup()


@pytest.mark.povray
def test_successful_render_ends_at_100_percent(qtbot, make_job, tmp_path):
    progress, done = [], []
    process = RenderProcess(make_job(), fake_povray(tmp_path, 0.1))  # reports only 50 %
    process.progress.connect(progress.append)
    process.finished.connect(done.append)
    process.start()
    qtbot.waitUntil(lambda: bool(done), timeout=10_000)
    assert done[0].ok and progress == [50, 100]
    process.job.cleanup()


def test_real_render_reports_progress(qtbot, make_job, povray_executable):
    results, progress = [], []
    process = RenderProcess(make_job(600, 400), povray_executable)
    process.finished.connect(results.append)
    process.progress.connect(progress.append)
    process.start()
    qtbot.waitUntil(lambda: bool(results), timeout=60_000)
    assert results[0].ok, results[0].message
    assert progress and progress[-1] == 100
    process.job.cleanup()
