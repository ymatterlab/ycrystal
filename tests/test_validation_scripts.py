"""FR-VALIDATION-01: the benchmark and replay-check scripts (questions C and D).

``scripts/benchmark_render.py`` times renders through the production command line;
``scripts/replay_check.py`` renders saved snapshots again and compares the pixels.
Most tests use a stand-in for POV-Ray (fast, no ray tracing); one uses the real one.
"""

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from PIL import Image

from conftest import fake_povray
from ycrystal.provenance import provenance_path

ROOT = Path(__file__).resolve().parents[1]
BENCHMARK = ROOT / "scripts" / "benchmark_render.py"
REPLAY = ROOT / "scripts" / "replay_check.py"


def run(script: Path, *args: str, **env: str) -> subprocess.CompletedProcess:
    environment = {k: v for k, v in os.environ.items() if k not in ("DISPLAY", "WAYLAND_DISPLAY")}
    environment.update(env)
    return subprocess.run(
        [sys.executable, str(script), *args],
        capture_output=True,
        text=True,
        env=environment,
        timeout=600,
        cwd=ROOT,
    )


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture(scope="module")
def benchmark_run(tmp_path_factory):
    """One small benchmark run with the stand-in renderer, shared by several tests."""
    folder = tmp_path_factory.mktemp("bench")
    povray = fake_povray(folder)
    out = folder / "result ü"
    cases = ["--cases", "srtio3-1", "mgb2-style", "--warmups", "1", "--repeats", "2"]
    result = run(BENCHMARK, "--out", str(out), *cases, "--scale", "0.2", "--povray", povray)
    return result, out, povray


def test_benchmark_records_runs_inputs_and_system(benchmark_run):
    result, out, _ = benchmark_run
    assert result.returncode == 0, result.stderr
    report = json.loads((out / "benchmark.json").read_text(encoding="utf-8"))
    assert (report["format"], report["schema_version"]) == ("ycrystal-benchmark", 1)
    assert report["options"]["warmups"] == 1 and report["options"]["repeats"] == 2
    system = report["system"]
    assert system["povray"] == "3.7.0.fake" and system["python"] and system["logical_cpus"]
    assert str(out) not in json.dumps(report)  # no paths of this computer
    assert [case["id"] for case in report["cases"]] == ["srtio3-1", "mgb2-style"]
    for case in report["cases"]:
        assert len(case["runs"]) == 2 and (case["width"], case["height"]) == (160, 120)
        wall = case["summary"]["wall_s"]
        assert wall["min"] <= wall["median"] <= wall["max"]
        assert all(run["wall_s"] > 0 and run["render_s"] is not None for run in case["runs"])
        if hasattr(os, "wait4"):
            assert all(run["peak_rss_mib"] > 1 for run in case["runs"])
        assert (out / case["snapshot"]).is_file()
        assert provenance_path(out / case["snapshot"]).is_file()
    srtio3, mgb2 = report["cases"]
    assert srtio3["input"]["sha256"] == sha(out / "inputs" / "srtio3-1.ycrystal")
    assert srtio3["fixture"]["sha256"] == sha(ROOT / "tests" / "fixtures" / "SrTiO3.cif")
    assert srtio3["displayed_atoms"] == 15 and srtio3["style"] is None
    assert mgb2["style"]["sha256"] == sha(ROOT / "examples" / "grey-studio.ycstyle")
    assert "srtio3-1" in result.stdout and "Wrote" in result.stdout


def test_benchmark_refuses_a_used_folder_and_bad_counts(benchmark_run, tmp_path):
    _, out, povray = benchmark_run
    used = run(BENCHMARK, "--out", str(out), "--cases", "srtio3-1", "--povray", povray)
    assert used.returncode == 2 and "is not empty" in used.stderr
    bad = run(BENCHMARK, "--out", str(tmp_path / "x"), "--repeats", "0", "--povray", povray)
    assert bad.returncode == 2 and "at least 1" in bad.stderr


def test_replay_check_same_different_and_modified(benchmark_run, tmp_path):
    _, out, povray = benchmark_run
    reference = out / "snapshots"
    same = run(REPLAY, str(reference), "--out", str(tmp_path / "same"), "--povray", povray)
    assert same.returncode == 0, same.stderr + same.stdout
    report = json.loads((tmp_path / "same" / "replay-check.json").read_text(encoding="utf-8"))
    assert (report["format"], report["schema_version"]) == ("ycrystal-replay-check", 1)
    assert report["summary"] == {
        "figures": 2,
        "same": 2,
        "different": 0,
        "modified": 0,
        "failed": 0,
    }
    assert all(f["identical_pixels"] for f in report["figures"])
    assert report["figures"][0]["reference_renderer"] == "3.7.0.fake"
    # Another renderer output: reported as different, with the size of the difference.
    other = run(
        REPLAY, str(reference), "--out", str(tmp_path / "other"), "--povray", povray,
        YCRYSTAL_FAKE_COLOR="40,60,90",
    )  # fmt: skip
    assert other.returncode == 1
    report = json.loads((tmp_path / "other" / "replay-check.json").read_text(encoding="utf-8"))
    assert {f["status"] for f in report["figures"]} == {"different"}
    assert {f["max_abs_difference"] for f in report["figures"]} == {10}
    assert run(REPLAY, str(reference), "--out", str(tmp_path / "loose"), "--povray", povray,
               "--tolerance", "10", YCRYSTAL_FAKE_COLOR="40,60,90").returncode == 0  # fmt: skip
    # A reference image changed after it was recorded is not compared.
    copy = tmp_path / "copy"
    copy.mkdir()
    for path in reference.iterdir():
        (copy / path.name).write_bytes(path.read_bytes())
    image = copy / "srtio3-1.png"
    Image.new("RGB", (160, 120), (1, 2, 3)).save(image)
    changed = run(REPLAY, str(copy), "--out", str(tmp_path / "changed"), "--povray", povray)
    assert changed.returncode == 1 and "srtio3-1.provenance.json: modified" in changed.stdout
    (tmp_path / "empty").mkdir()
    empty = run(
        REPLAY, str(tmp_path / "empty"), "--out", str(tmp_path / "none"), "--povray", povray
    )
    assert empty.returncode == 2 and "no provenance records" in empty.stderr


@pytest.mark.povray
def test_benchmark_and_replay_with_povray(povray_executable, tmp_path):
    out = tmp_path / "bench"
    args = ["--out", str(out), "--cases", "srtio3-1", "--repeats", "1"]
    result = run(BENCHMARK, *args, "--scale", "0.2", "--povray", povray_executable)
    assert result.returncode == 0, result.stderr
    report = json.loads((out / "benchmark.json").read_text(encoding="utf-8"))
    assert report["system"]["povray"].startswith("3.7")
    replay = run(REPLAY, str(out / "snapshots"), "--out", str(tmp_path / "replay"),
                 "--povray", povray_executable)  # fmt: skip
    assert replay.returncode == 0, replay.stdout + replay.stderr
    check = json.loads((tmp_path / "replay" / "replay-check.json").read_text(encoding="utf-8"))
    assert check["summary"]["same"] == 1
