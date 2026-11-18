"""FR-BATCH-01: manifest-driven rendering of several structures, without a window."""

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from conftest import python_program
from ycrystal import manifest as batch_manifest
from ycrystal.app import main
from ycrystal.manifest import (
    REPORT_NAME,
    ManifestError,
    load_manifest,
    plan_batch,
    run_batch,
)
from ycrystal.render.imagecheck import load_rgba
from ycrystal.render.povray import PovrayNotFoundError

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples" / "batch-series.json"
FIXTURES = ROOT / "tests" / "fixtures"


def write_manifest(folder: Path, jobs, defaults=None, **extra) -> Path:
    data = {"format": "ycrystal-batch", "schema_version": 1, "jobs": jobs, **extra}
    if defaults is not None:
        data["defaults"] = defaults
    path = folder / "series.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def fake_povray(folder: Path) -> str:
    """An executable that exists (find_povray only checks that) but renders nothing."""
    return python_program(folder / "fake-povray", "pass\n")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# ----- validation ---------------------------------------------------------------------------
def test_example_manifest_plans_five_jobs_in_order(tmp_path):
    out = tmp_path / "renders ü"
    jobs = plan_batch(EXAMPLE, out)
    assert [job.id for job in jobs] == ["SrTiO3", "BaZrO3", "MgB2", "triclinic", "afm-vectors"]
    assert [job.output for job in jobs][-1] == "vectors/afm.png"
    assert {(job.width, job.height) for job in jobs} == {(600, 450)}
    by_id = {job.id: job for job in jobs}
    assert dict(by_id["BaZrO3"].project.scene.element_materials)["Zr"] == "chrome"  # Ti → Zr
    assert by_id["MgB2"].view.view == "c" and by_id["SrTiO3"].view.view == "a"
    assert any("O, Ti" in warning for warning in by_id["MgB2"].warnings)
    assert by_id["triclinic"].project.scene.element_materials == ()  # environment only
    assert by_id["afm-vectors"].project.scene.vectors == (
        batch_manifest.load_input(
            ROOT / "examples" / "vectors-synthetic-afm.ycrystal"
        ).scene.vectors
    )
    assert not out.exists()  # validation writes nothing


def test_every_problem_is_reported_and_nothing_is_written(tmp_path):
    style = ROOT / "examples" / "grey-studio.ycstyle"
    (tmp_path / "out").mkdir()
    (tmp_path / "out" / "exists.png").write_bytes(b"old")
    jobs = [
        {"id": "ok", "input": str(FIXTURES / "SrTiO3.cif")},
        {"id": "ok", "input": str(FIXTURES / "MgB2.cif")},  # duplicate id
        {"id": "bad id!", "input": str(FIXTURES / "MgB2.cif")},
        {"id": "dup", "input": str(FIXTURES / "MgB2.cif"), "output": "OK.png"},  # case clash
        {"id": "up", "input": str(FIXTURES / "MgB2.cif"), "output": "../escape.png"},
        {"id": "abs", "input": str(FIXTURES / "MgB2.cif"), "output": "/tmp/x.png"},
        {"id": "jpeg", "input": str(FIXTURES / "MgB2.cif"), "output": "x.jpg"},
        {"id": "missing", "input": "nowhere.cif"},
        {"id": "unreadable", "input": str(FIXTURES / "not_a_structure.txt")},
        {"id": "nostyle", "input": str(FIXTURES / "MgB2.cif"), "style": "nowhere.ycstyle"},
        {
            "id": "parts",
            "input": str(FIXTURES / "MgB2.cif"),
            "style": str(style),
            "style_parts": ["camera"],
        },
        {
            "id": "symbol",
            "input": str(FIXTURES / "MgB2.cif"),
            "style": str(style),
            "element_map": {"ti": "Mg"},
        },
        {
            "id": "absent",
            "input": str(FIXTURES / "MgB2.cif"),
            "style": str(style),
            "element_map": {"Ti": "Zr"},
        },
        {"id": "maponly", "input": str(FIXTURES / "MgB2.cif"), "element_map": {"Ti": "Mg"}},
        {"id": "height", "input": str(FIXTURES / "MgB2.cif"), "view_height": 1},
        {"id": "size", "input": str(FIXTURES / "MgB2.cif"), "width": 5},
        {"id": "atoms", "input": str(FIXTURES / "SrTiO3.cif"), "max_atoms": 3},
        {"id": "typo", "input": str(FIXTURES / "MgB2.cif"), "veiw": "a"},
        {"id": "exists", "input": str(FIXTURES / "MgB2.cif")},
    ]
    path = write_manifest(tmp_path, jobs)
    with pytest.raises(ManifestError) as info:
        plan_batch(path, tmp_path / "out")
    text = "\n".join(info.value.problems)
    for expected in (
        "job ok: the id is used twice",
        "job 3: id must be letters",
        "job dup: output 'OK.png' is also the output of job ok",
        "job up: output '../escape.png' must stay inside the output directory",
        "job abs: output '/tmp/x.png' must stay inside",
        "job jpeg: output 'x.jpg' must be a .png file",
        "job missing: input 'nowhere.cif' not found",
        "job unreadable: cannot read",
        "job nostyle: style 'nowhere.ycstyle'",
        "job parts: style_parts must be a non-empty list",
        "job symbol: element_map: 'ti' is not a chemical element symbol (did you mean Ti?)",
        "job absent: Element mapping: Ti is mapped to Zr, but the structure has no Zr",
        "job maponly: element_map and style_parts need a style",
        "job height: The scene does not fit in a visible height of 1 Å",
        "job size: width must be a whole number of pixels from 16 to 8000",
        "job atoms: 15 displayed atoms exceed max_atoms = 3",
        "job typo: unknown settings veiw",
        "exists.png exists; use --overwrite",
    ):
        assert expected in text, expected
    assert "job ok:" not in text.replace("job ok: the id is used twice", "")  # first ok is fine
    assert sorted(p.name for p in (tmp_path / "out").iterdir()) == ["exists.png"]


@pytest.mark.parametrize(
    "content, message",
    [
        ("not json", "is not valid JSON"),
        ('{"format": "ycrystal-style"}', "not a Ycrystal batch manifest"),
        ('{"format": "ycrystal-batch", "schema_version": 2, "jobs": [{}]}', "schema 2"),
        ('{"format": "ycrystal-batch", "schema_version": 1, "jobs": []}', "non-empty list"),
        ('{"format": "ycrystal-batch", "schema_version": 1, "jobs": [{}], "x": 1}', "keys: x"),
    ],
)
def test_bad_manifest_files(tmp_path, content, message):
    path = tmp_path / "bad.json"
    path.write_text(content)
    with pytest.raises(ManifestError, match=message):
        load_manifest(path)


# ----- running (no POV-Ray needed) ----------------------------------------------------------
def test_a_failed_job_does_not_stop_the_others(tmp_path, monkeypatch):
    path = write_manifest(
        tmp_path,
        [{"id": name, "input": str(FIXTURES / f"{name}.cif")} for name in ("SrTiO3", "MgB2")]
        + [{"id": "last", "input": str(FIXTURES / "BaZrO3.cif")}],
    )
    out = tmp_path / "out"
    calls = []

    def fake_render(project, destination, povray, width, height, view=None):
        calls.append(Path(destination).name)
        if Path(destination).name == "MgB2.png":
            return SimpleNamespace(ok=False, message="POV-Ray failed: parse error")
        Path(destination).parent.mkdir(parents=True, exist_ok=True)
        Path(destination).write_bytes(b"png")
        return SimpleNamespace(ok=True, message="")

    monkeypatch.setattr(batch_manifest, "render_png", fake_render)
    report = run_batch(plan_batch(path, out), out, fake_povray(tmp_path), manifest="series.json")
    assert calls == ["SrTiO3.png", "MgB2.png", "last.png"]  # in manifest order, all tried
    assert [job.status for job in report.jobs] == ["rendered", "failed", "rendered"]
    assert report.failed == 1 and "parse error" in report.jobs[1].error
    assert sorted(p.name for p in out.iterdir()) == sorted(["SrTiO3.png", "last.png", REPORT_NAME])
    data = json.loads((out / REPORT_NAME).read_text())
    assert data["summary"] == {"jobs": 3, "rendered": 2, "failed": 1}
    assert [job["id"] for job in data["jobs"]] == ["SrTiO3", "MgB2", "last"]
    assert data["jobs"][0]["input"].endswith("SrTiO3.cif") and data["manifest"] == "series.json"
    assert not list(out.glob("*.part"))


def test_dry_run_and_missing_povray_write_nothing(tmp_path, monkeypatch):
    out = tmp_path / "out"
    jobs = plan_batch(EXAMPLE, out)
    report = run_batch(jobs, out, dry_run=True)
    assert {job.status for job in report.jobs} == {"planned"} and not out.exists()
    monkeypatch.setenv("YCRYSTAL_POVRAY", str(tmp_path / "no-povray"))
    with pytest.raises(PovrayNotFoundError):
        run_batch(jobs, out)
    assert not out.exists()


# ----- command line -------------------------------------------------------------------------
def test_batch_command_line_exit_codes(tmp_path, capsys, monkeypatch):
    out = tmp_path / "out"
    assert main(["--batch", str(EXAMPLE), "--output-dir", str(out), "--dry-run"]) == 0
    captured = capsys.readouterr()
    assert "BaZrO3: would render BaZrO3.png (600 × 450, 15 atoms)" in captured.out
    assert "WARNING: MgB2: Element overrides for O, Ti" in captured.err and not out.exists()
    bad = write_manifest(tmp_path, [{"id": "x", "input": "nowhere.cif"}])
    assert main(["--batch", str(bad), "--output-dir", str(out)]) == 2
    err = capsys.readouterr().err
    assert "is not valid; nothing was rendered" in err and "  - job x: input" in err
    monkeypatch.setattr(
        batch_manifest,
        "render_png",
        lambda *a, **k: SimpleNamespace(ok=False, message="POV-Ray failed"),
    )
    code = main(
        ["--batch", str(EXAMPLE), "--output-dir", str(out), "--povray", fake_povray(tmp_path)]
    )
    assert code == 1 and "Rendered 0 of 5 job(s)" in capsys.readouterr().out
    assert (out / REPORT_NAME).is_file()


@pytest.mark.parametrize(
    "args, message",
    [
        (["--batch", "m.json"], "needs --output-dir"),
        (["--batch", "m.json", "--output-dir", "o", "--render", "x.png"], "leave out --render"),
        (["FILE.cif", "--batch", "m.json", "--output-dir", "o"], "leave out FILE"),
        (["--batch", "m.json", "--output-dir", "o", "--view", "a"], "leave out --view"),
        (["FILE.cif", "--export-pov", "x", "--dry-run"], "belong to --batch"),
        (["--overwrite"], "belong to --batch"),
    ],
)
def test_batch_usage_errors(args, message, capsys):
    with pytest.raises(SystemExit) as info:
        main(args)
    assert info.value.code == 2 and message in capsys.readouterr().err


def test_batch_needs_no_window_toolkit(tmp_path):
    script = (
        "import sys; from ycrystal.app import main; "
        f"code = main(['--batch', {str(EXAMPLE)!r}, '--output-dir', {str(tmp_path)!r}, "
        "'--dry-run']); "
        "loaded = sorted(m for m in sys.modules "
        "if m.split('.')[0] in ('PySide6', 'vtk', 'vtkmodules', 'pyvista', 'pyvistaqt')); "
        "print(code, loaded)"
    )
    env = {k: v for k, v in os.environ.items() if k not in ("DISPLAY", "WAYLAND_DISPLAY")}
    result = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True, env=env, timeout=120
    )
    assert result.stdout.strip().splitlines()[-1] == "0 []", result.stdout + result.stderr


# ----- real POV-Ray -------------------------------------------------------------------------
@pytest.mark.povray
def test_example_series_renders_with_povray(tmp_path, capsys, povray_executable):
    sources = [FIXTURES / f"{n}.cif" for n in ("SrTiO3", "BaZrO3", "MgB2", "triclinic")]
    sources += [
        ROOT / "examples" / n for n in ("grey-studio.ycstyle", "vectors-synthetic-afm.ycrystal")
    ]
    before = [sha(p) for p in sources]
    out = tmp_path / "Bilder ü"
    args = ["--batch", str(EXAMPLE), "--output-dir", str(out), "--povray", povray_executable]
    assert main(args) == 0
    assert "Rendered 5 of 5 job(s)" in capsys.readouterr().out
    report = json.loads((out / REPORT_NAME).read_text(encoding="utf-8"))
    assert [job["status"] for job in report["jobs"]] == ["rendered"] * 5
    assert report["renderer"].startswith("POV-Ray 3.7")
    images = [out / job["output"] for job in report["jobs"]]
    shapes = {load_rgba(path).shape for path in images}
    assert shapes == {(450, 600, 4)}
    assert not np.array_equal(load_rgba(images[0]), load_rgba(images[1]))
    assert [sha(p) for p in sources] == before  # inputs, style, and project untouched
    assert main(args) == 2  # no overwriting without --overwrite
    capsys.readouterr()
    assert main([*args, "--overwrite"]) == 0
    assert not list(out.rglob("*.part"))


def test_example_manifest_is_listed_in_the_examples():
    data = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    for job in data["jobs"]:
        assert (EXAMPLE.parent / job["input"]).is_file()
        assert not Path(job["input"]).is_absolute()  # portable: relative to the manifest
