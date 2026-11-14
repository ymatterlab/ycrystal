import os
import stat

import pytest

from ycrystal.core.camera import Camera
from ycrystal.core.scene import Environment
from ycrystal.render.jobs import copy_result, prepare_job, run_job
from ycrystal.render.pov_writer import RenderSettings
from ycrystal.render.povray import (
    POVRAY_ENV,
    PovrayNotFoundError,
    explain_failure,
    find_povray,
)
from ycrystal.render.selftest import run_self_test


def make_script(path, body: str):
    path.write_text("#!/bin/sh\n" + body + "\n")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)
    return path


@pytest.fixture
def no_povray(monkeypatch, tmp_path):
    empty = tmp_path / "empty-bin"
    empty.mkdir()
    monkeypatch.setenv("PATH", str(empty))
    monkeypatch.delenv(POVRAY_ENV, raising=False)


def test_missing_renderer_on_path_gives_guidance(no_povray):
    with pytest.raises(PovrayNotFoundError) as info:
        find_povray()
    message = str(info.value)
    assert "not found on PATH" in message
    assert "sudo apt install povray" in message
    assert "exporting .pov/.ini files work without it" in message


def test_missing_configured_and_env_paths(no_povray, monkeypatch, tmp_path):
    with pytest.raises(PovrayNotFoundError, match="configured POV-Ray path"):
        find_povray(tmp_path / "nope" / "povray")
    monkeypatch.setenv(POVRAY_ENV, str(tmp_path / "missing"))
    with pytest.raises(PovrayNotFoundError, match=POVRAY_ENV):
        find_povray()


def test_precedence_configured_env_path(monkeypatch, tmp_path):
    configured = make_script(tmp_path / "configured", "exit 0")
    env = make_script(tmp_path / "env", "exit 0")
    on_path_dir = tmp_path / "bin"
    on_path_dir.mkdir()
    on_path = make_script(on_path_dir / "povray", "exit 0")
    monkeypatch.setenv("PATH", str(on_path_dir))
    monkeypatch.setenv(POVRAY_ENV, str(env))
    assert find_povray(configured) == str(configured)
    assert find_povray() == str(env)
    monkeypatch.delenv(POVRAY_ENV)
    assert find_povray() == str(on_path)


def test_self_test_reports_missing_renderer(no_povray):
    result = run_self_test()
    assert not result.ok
    assert "sudo apt install povray" in result.message


def test_explain_failure_messages():
    fast_math = explain_failure(1, "File 'scene.pov' line 9: Parse Error: Viewing angle has "
                                   "to be smaller than 180 degrees.")
    assert "-ffast-math" in fast_math and "--disable-optimiz" in fast_math
    io = explain_failure(1, "Parse Error: I/O restriction settings prohibit access to file")
    assert "povray.conf" in io
    generic = explain_failure(2, "line one\nsomething broke")
    assert "exited with code 2" in generic and "something broke" in generic


def _job(tmp_path):
    camera = Camera(position=(0, 0, 10), focal_point=(0, 0, 0), view_up=(0, 1, 0),
                    parallel_scale=2)
    from conftest import spread_geometry

    return prepare_job(spread_geometry(), camera, Environment(), RenderSettings(32, 24),
                       parent=tmp_path)


def test_job_directory_uses_ascii_names(tmp_path):
    job = _job(tmp_path)
    assert job.directory.parent == tmp_path
    assert {p.name for p in job.directory.iterdir()} == {"scene.pov", "scene.ini"}
    assert job.arguments() == ["scene.ini"]
    job.cleanup()
    assert not job.directory.exists()


def test_failed_render_is_explained(tmp_path):
    fake = make_script(tmp_path / "povray", "echo 'Parse Error: Viewing angle has to be "
                                            "smaller than 180' >&2; exit 1")
    result = run_job(_job(tmp_path), str(fake))
    assert not result.ok and result.returncode == 1
    assert "-ffast-math" in result.message


def test_success_without_image_is_a_failure(tmp_path):
    fake = make_script(tmp_path / "povray", "echo done; exit 0")
    result = run_job(_job(tmp_path), str(fake))
    assert not result.ok and "produced no image" in result.message


def test_runs_in_job_directory(tmp_path):
    fake = make_script(tmp_path / "povray", 'pwd > cwd.txt; printf PNG > scene.png; exit 0')
    job = _job(tmp_path)
    result = run_job(job, str(fake))
    assert result.ok and result.image_path == job.image_path
    assert (job.directory / "cwd.txt").read_text().strip() == str(job.directory)


def test_copy_result_to_unusual_destination(tmp_path):
    source = tmp_path / "image.png"
    source.write_bytes(b"png-bytes")
    destination = tmp_path / "Résultats finaux" / "my render (1).png"
    assert copy_result(source, destination) == destination
    assert destination.read_bytes() == b"png-bytes"
    assert not destination.with_name(destination.name + ".part").exists()


def test_uncreatable_executable_is_reported(tmp_path):
    not_exec = tmp_path / "povray"
    not_exec.write_text("plain file")
    os.chmod(not_exec, 0o644)
    with pytest.raises(PovrayNotFoundError, match="not executable"):
        find_povray(not_exec)
