"""Render the publication gallery with POV-Ray and check that it can be reproduced.

FR-GALLERY-01. Every image is made by the production command line, in five steps:

1. The inputs in ``examples/publication`` (and the two example projects it refers to)
   are copied to a temporary folder, and its manifest ``gallery.json`` is run there with
   ``ycrystal --batch``. Each figure is saved with a snapshot and a provenance record.
2. The SrTiO3 figure is rendered twice more from its snapshot with
   ``styles/cover.ycstyle``: first with the cover's environment only, then with its
   environment and materials. A snapshot keeps its camera and size, so all three share
   exactly the same geometry and camera: a controlled comparison of lighting and
   materials.
3. The temporary inputs are deleted. ``scripts/replay_check.py`` then renders every
   snapshot again and compares the pixels, which shows that the snapshots do not need
   the original files.
4. A figure-methods table is written from the provenance records and snapshots
   (``figure-methods.md`` and ``.json``).
5. With ``--thumbnails DIR``, small JPEG copies are written for the documentation,
   downscaled from the rendered figures.

Usage::

    python scripts/make_gallery.py --out artifacts/gallery
    python scripts/make_gallery.py --out artifacts/gallery --scale 0.25     # quick check
    python scripts/make_gallery.py --out artifacts/gallery --thumbnails docs/assets/gallery

Exit status 0 when every figure was rendered and every replay had the same pixels.
"""

from __future__ import annotations

import argparse
import json
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PUBLICATION = ROOT / "examples" / "publication"
# Example projects in examples/ that the manifest refers to ("../NAME").
EXTERNAL_INPUTS = [
    ROOT / "examples" / n for n in ("MgB2-gradient.ycrystal", "vectors-synthetic-afm.ycrystal")
]
STYLE_SIZE = (1600, 1200)  # the output size of styles/paper.ycstyle

# Figures in reading order: (image stem, short description for the table).
FIGURES = [
    ("srtio3", "SrTiO3, paper style"),
    ("srtio3-cover-light", "SrTiO3, same snapshot: cover environment only"),
    ("srtio3-cover", "SrTiO3, same snapshot: cover environment and materials"),
    ("bazro3-mapped", "BaZrO3, paper style mapped Sr → Ba, Ti → Zr"),
    ("mgb2", "MgB2 3 × 3 × 1 down c, paper style (no settings for Mg, B)"),
    ("kyanite", "Kyanite Al2SiO5 (COD 1008755), paper style"),
    ("afm-synthetic", "Synthetic antiferromagnet (not a real material), paper style"),
]
VARIANTS = [
    ("srtio3-cover-light", "environment"),
    ("srtio3-cover", "appearance,environment"),
]


def run(command: list[str], log: list[str]) -> subprocess.CompletedProcess:
    """Run a command, echo it, and keep it for the log; stop on failure."""
    shown = shlex.join(str(part) for part in command)
    print(f"$ {shown}", flush=True)
    log.append(shown)
    result = subprocess.run(command, capture_output=True, text=True, errors="replace")
    sys.stdout.write(result.stdout)
    sys.stderr.write(result.stderr)
    return result


def ycrystal(*args: str) -> list[str]:
    return [sys.executable, "-m", "ycrystal", *args]


def copy_sources(folder: Path, scale: float) -> Path:
    """Copy the gallery inputs to ``folder``; return the copied manifest."""
    publication = folder / "publication"
    shutil.copytree(PUBLICATION, publication, ignore=shutil.ignore_patterns("*.md"))
    for path in EXTERNAL_INPUTS:
        shutil.copyfile(path, folder / path.name)
    manifest = publication / "gallery.json"
    if scale != 1.0:  # a smaller copy of the same figures, for quick checks
        data = json.loads(manifest.read_text(encoding="utf-8"))
        width, height = (max(16, round(v * scale)) for v in STYLE_SIZE)
        data["defaults"].update(width=width, height=height)
        manifest.write_text(json.dumps(data, indent=1), encoding="utf-8")
    return manifest


def settings_of(snapshot: Path) -> str:
    """Return the key appearance settings of a snapshot, in words."""
    from ycrystal.io.project import load_project

    project = load_project(snapshot)
    scene, environment = project.scene, project.environment
    parts = [f"{environment.preset} background, {environment.lighting} lighting"]
    if environment.floor:
        parts.append(f"floor (reflection {environment.floor_reflection:g})")
    if environment.shadows and environment.light_size > 0:
        parts.append("area light, soft shadows")
    parts.append(f"default material {scene.material}")
    if scene.element_materials:
        parts.append(", ".join(f"{e} {m}" for e, m in scene.element_materials))
    if scene.element_colors:
        parts.append("element colours " + ", ".join(e for e, _ in scene.element_colors))
    if scene.vectors.sources:
        parts.append(f"{len(scene.vectors.sources)} source vectors")
    return "; ".join(parts)


def methods_table(figures: Path) -> tuple[str, list[dict]]:
    """Build the figure-methods table from the provenance records and snapshots."""
    rows = []
    for stem, description in FIGURES:
        record = json.loads((figures / f"{stem}.provenance.json").read_text(encoding="utf-8"))
        style = record["style"] or {}
        camera = record["camera"]
        view = camera["view"] or "saved orientation"
        if camera["view_height"]:
            view += f", fixed height {camera['view_height']:g} Å"
        rows.append(
            {
                "figure": f"{stem}.png",
                "description": description,
                "input": record["input"]["name"],
                "input_sha256": record["input"]["sha256"],
                "composition": record["structure"]["composition"],
                "atoms": record["structure"]["atoms"],
                "displayed_atoms": record["structure"]["displayed_atoms"],
                "size": f"{record['image']['width']} × {record['image']['height']}",
                "style": style.get("name"),
                "style_parts": style.get("parts"),
                "element_map": style.get("element_map"),
                "camera": f"{camera['policy']}: {view}",
                "settings": settings_of(figures / f"{stem}.ycrystal"),
                "renderer": f"POV-Ray {record['renderer']['version']}",
                "includes": record["renderer"]["includes"],
            }
        )
    lines = [
        "| Figure | Input | Atoms (displayed) | Size, px | Style (parts; mapping) | Camera | "
        "Key settings | Renderer |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        mapping = row["element_map"]
        style = "none"
        if row["style"]:
            style = f"{row['style']} ({', '.join(row['style_parts'])}"
            style += "; " + ", ".join(f"{a} → {b}" for a, b in mapping.items()) if mapping else ""
            style += ")"
        lines.append(
            f"| {row['figure']}: {row['description']} | {row['input']} | "
            f"{row['atoms']} ({row['displayed_atoms']}) | {row['size']} | {style} | "
            f"{row['camera']} | {row['settings']} | {row['renderer']} |"
        )
    return "\n".join(lines) + "\n", rows


def thumbnails(figures: Path, folder: Path, width: int = 480) -> list[Path]:
    """Write downscaled JPEG copies of the figures; return their paths."""
    from PIL import Image

    folder.mkdir(parents=True, exist_ok=True)
    written = []
    for stem, _ in FIGURES:
        with Image.open(figures / f"{stem}.png") as image:
            image = image.convert("RGB")
            height = round(image.height * width / image.width)
            small = image.resize((width, height), Image.Resampling.LANCZOS)
            path = folder / f"{stem}.jpg"
            small.save(path, quality=85, optimize=True)
            written.append(path)
    return written


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", required=True, type=Path, help="folder for the gallery")
    parser.add_argument("--scale", type=float, default=1.0, help="image size factor (0.05-1)")
    parser.add_argument("--povray", help="POV-Ray executable (default: as ycrystal finds it)")
    parser.add_argument("--thumbnails", type=Path, help="also write JPEG thumbnails here")
    args = parser.parse_args(argv)
    if not 0.05 <= args.scale <= 1.0:
        parser.error("--scale must be between 0.05 and 1")
    if args.out.exists() and any(args.out.iterdir()):
        parser.error(f"{args.out} is not empty; choose a new folder")
    povray = ["--povray", args.povray] if args.povray else []
    figures = args.out / "figures"
    log: list[str] = []
    with tempfile.TemporaryDirectory(prefix="ycrystal-gallery-") as temporary:
        sources = Path(temporary)
        manifest = copy_sources(sources, args.scale)
        # 1. The series from the manifest, with snapshots and provenance records.
        batch = ycrystal("--batch", str(manifest), "--output-dir", str(figures), *povray)
        if run(batch, log).returncode != 0:
            return 1
        # 2. Controlled comparison: the SrTiO3 snapshot with the cover style.
        cover = manifest.parent / "styles" / "cover.ycstyle"
        for stem, parts in VARIANTS:
            command = ycrystal(
                str(figures / "srtio3.ycrystal"),
                "--style",
                str(cover),
                "--style-parts",
                parts,
                "--render",
                str(figures / f"{stem}.png"),
                "--save-project",
                str(figures / f"{stem}.ycrystal"),
                *povray,
            )
            if run(command, log).returncode != 0:
                return 1
    # 3. The sources are gone now: render every snapshot again and compare.
    replay = [sys.executable, str(ROOT / "scripts" / "replay_check.py"), str(figures)]
    replayed = run([*replay, "--out", str(args.out / "replay"), *povray], log)
    # 4. Methods table.
    table, rows = methods_table(figures)
    (args.out / "figure-methods.md").write_text(table, encoding="utf-8")
    (args.out / "figure-methods.json").write_text(
        json.dumps(rows, indent=1, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    (args.out / "commands.txt").write_text("\n".join(log) + "\n", encoding="utf-8")
    print(f"Wrote {args.out / 'figure-methods.md'} and {args.out / 'commands.txt'}")
    # 5. Thumbnails for the documentation.
    if args.thumbnails:
        for path in thumbnails(figures, args.thumbnails):
            print(f"Wrote {path} ({path.stat().st_size // 1024} KiB)")
    return 0 if replayed.returncode == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
