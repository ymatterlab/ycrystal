"""FR-GALLERY-01: the publication gallery in ``examples/publication`` stays valid.

The images themselves are made by ``scripts/make_gallery.py`` with POV-Ray; these tests
keep its inputs, styles, documentation, and claims from going stale.
"""

import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from ycrystal.batch import apply_style_file, load_input, scene_for
from ycrystal.io.readers import read_structure
from ycrystal.io.style import load_style
from ycrystal.manifest import plan_batch
from ycrystal.provenance import snapshot_project

ROOT = Path(__file__).resolve().parents[1]
PUBLICATION = ROOT / "examples" / "publication"
MANIFEST = PUBLICATION / "gallery.json"
PAPER = PUBLICATION / "styles" / "paper.ycstyle"
COVER = PUBLICATION / "styles" / "cover.ycstyle"
KYANITE = PUBLICATION / "structures" / "kyanite-COD-1008755.cif"
KYANITE_SHA256 = "0d776c5e5c0fff0a45eb763a9dcaa4ab51af2e0d81937fddaa863eea810e36c3"
FIGURES = [
    "srtio3",
    "srtio3-cover-light",
    "srtio3-cover",
    "bazro3-mapped",
    "mgb2",
    "kyanite",
    "afm-synthetic",
]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def planned(tmp_path):
    return {job.id: job for job in plan_batch(MANIFEST, tmp_path / "out")}


def test_manifest_plans_five_figures_with_mapping_scale_and_snapshots(tmp_path):
    jobs = planned(tmp_path)
    assert list(jobs) == ["srtio3", "bazro3-mapped", "mgb2", "kyanite", "afm-synthetic"]
    assert all(job.snapshot == f"{job.id}.ycrystal" for job in jobs.values())
    assert {(job.width, job.height) for job in jobs.values()} == {(1600, 1200)}
    # The same physical scale for both perovskites; BaZrO3 gets the A and B site colours.
    assert jobs["srtio3"].view.visible_height == jobs["bazro3-mapped"].view.visible_height == 9.0
    colors = dict(load_style(PAPER).scene.element_colors)
    mapped = dict(jobs["bazro3-mapped"].project.scene.element_colors)
    assert (mapped["Ba"], mapped["Zr"], mapped["O"]) == (colors["Sr"], colors["Ti"], colors["O"])
    assert jobs["bazro3-mapped"].warnings == ()
    # What does not transfer is reported, not hidden.
    assert any("O, Sr, Ti" in w for w in jobs["mgb2"].warnings)
    assert any("Sr, Ti" in w for w in jobs["kyanite"].warnings)
    assert jobs["mgb2"].project.scene.repetitions == (3, 3, 1)
    assert jobs["afm-synthetic"].project.scene.vectors.sources  # moments kept


def test_structure_inputs_and_their_provenance():
    for name in ("SrTiO3.cif", "BaZrO3.cif"):  # the test fixtures, unchanged
        assert sha(PUBLICATION / "structures" / name) == sha(ROOT / "tests" / "fixtures" / name)
    # Kyanite from the Crystallography Open Database, kept verbatim.
    assert sha(KYANITE) == KYANITE_SHA256
    text = KYANITE.read_text(encoding="utf-8")
    assert "_cod_database_code               1008755" in text
    assert "placed in the public domain" in text and "de Rango, C" in text
    structure = read_structure(KYANITE)
    assert structure.composition() == "O20Si4Al8" and len(structure) == 32
    assert structure.metadata["source"]["spacegroup"]["symbol"] == "P -1"
    assert np.all(structure.occupancy == 1.0)
    assert abs(np.linalg.det(structure.cell) - 292.3) < 0.1
    readme = (PUBLICATION / "README.md").read_text(encoding="utf-8")
    notices = (ROOT / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")
    assert KYANITE_SHA256 in readme and "1008755" in notices


def test_styles_are_the_ones_make_examples_writes(tmp_path):
    sys.path.insert(0, str(ROOT / "scripts"))
    try:
        import make_examples
    finally:
        sys.path.remove(str(ROOT / "scripts"))
    make_examples.publication_styles(tmp_path)
    for name in ("paper.ycstyle", "cover.ycstyle"):
        assert (tmp_path / name).read_bytes() == (PUBLICATION / "styles" / name).read_bytes()
    paper, cover = load_style(PAPER), load_style(COVER)
    assert paper.scene.element_radii == cover.scene.element_radii == ()
    assert paper.scene.element_colors == cover.scene.element_colors


@pytest.mark.parametrize("parts", [("environment",), ("appearance", "environment")])
def test_cover_variants_keep_geometry_camera_and_size(tmp_path, parts):
    """Figure 2: the cover style changes lighting and materials, nothing else."""
    job = planned(tmp_path)["srtio3"]
    paper = snapshot_project(job.project, view=job.view)
    cover, _ = apply_style_file(paper, COVER, parts)
    assert cover.camera == paper.camera and cover.output == paper.output
    first, _, _ = scene_for(paper)
    second, _, _ = scene_for(cover)
    assert first.atom_ids == second.atom_ids
    for name in ("positions", "radii"):
        assert np.array_equal(getattr(first, name), getattr(second, name)), name
    # Colours change only through materials that bring their own (ruby glass).
    assert np.array_equal(first.colors, second.colors) == ("appearance" not in parts)
    assert cover.environment != paper.environment
    assert (cover.scene.element_materials != paper.scene.element_materials) == (
        "appearance" in parts
    )


def test_documents_match_the_gallery():
    script = (ROOT / "scripts" / "make_gallery.py").read_text(encoding="utf-8")
    block = script.split("FIGURES = [", 1)[1].split("\n]\n", 1)[0]
    assert re.findall(r'^    \("([\w-]+)", "', block, re.M) == FIGURES
    figures = (ROOT / "docs" / "development" / "manuscript-figures.md").read_text(encoding="utf-8")
    gallery = (ROOT / "docs" / "guide" / "gallery.md").read_text(encoding="utf-8")
    for stem in FIGURES:
        assert f"{stem}.png" in figures
        thumbnail = ROOT / "docs" / "assets" / "gallery" / f"{stem}.jpg"
        assert f"../assets/gallery/{stem}.jpg" in gallery
        assert thumbnail.is_file() and thumbnail.stat().st_size < 250_000
    readme = (PUBLICATION / "README.md").read_text(encoding="utf-8")
    for path in sorted(PUBLICATION.rglob("*")):
        if path.is_file() and path.name != "README.md":
            assert path.relative_to(PUBLICATION).as_posix() in readme, path
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    for job in data["jobs"]:
        assert (PUBLICATION / job["input"]).is_file()
        assert not Path(job["input"]).is_absolute()
    project = load_input(ROOT / "examples" / "MgB2-gradient.ycrystal")
    source = project.structure.metadata["source"]
    assert source["sha256"] == sha(ROOT / "tests" / "fixtures" / "MgB2.cif")


@pytest.mark.povray
def test_gallery_script_renders_compares_and_tabulates(tmp_path, povray_executable):
    out = tmp_path / "Galerie ü"
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "make_gallery.py"), "--out", str(out),
         "--scale", "0.1", "--povray", povray_executable],
        capture_output=True, text=True, timeout=900,
    )  # fmt: skip
    assert result.returncode == 0, result.stdout[-2000:] + result.stderr[-2000:]
    figures = out / "figures"
    assert sorted(p.stem for p in figures.glob("*.png")) == sorted(FIGURES)
    replay = json.loads((out / "replay" / "replay-check.json").read_text(encoding="utf-8"))
    assert replay["summary"]["same"] == len(FIGURES)  # snapshots without their sources
    cameras = [
        json.loads((figures / f"{stem}.provenance.json").read_text(encoding="utf-8"))["camera"]
        for stem in ("srtio3", "srtio3-cover-light", "srtio3-cover")
    ]
    keys = ("position", "focal_point", "view_up", "parallel_scale")
    assert all({k: c[k] for k in keys} == {k: cameras[0][k] for k in keys} for c in cameras)
    rows = json.loads((out / "figure-methods.json").read_text(encoding="utf-8"))
    assert [row["figure"] for row in rows] == [f"{stem}.png" for stem in FIGURES]
    assert all(row["renderer"].startswith("POV-Ray 3.7") for row in rows)
    table = (out / "figure-methods.md").read_text(encoding="utf-8")
    assert table.count("\n| ") == len(FIGURES) + 1  # separator row and one row per figure
