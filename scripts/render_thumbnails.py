"""Render the gallery thumbnails of all presets with POV-Ray.

Writes ``src/ycrystal/presets/thumbnails/{materials,environments}/<id>.png`` and
``index.json`` (scene digests, checked by the test suite). By default only thumbnails
whose scene changed are rendered again; ``--all`` renders every one.

    python scripts/render_thumbnails.py [--all] [--povray /usr/bin/povray]

Inspect the new images before committing them.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from PIL import Image

from ycrystal.presets import environments, materials
from ycrystal.render.jobs import copy_result
from ycrystal.render.pov_writer import RenderSettings, render_ini
from ycrystal.render.povray import find_povray
from ycrystal.render.thumbnails import (
    THUMBNAIL_SIZE,
    environment_scene,
    load_index,
    material_scene,
    scene_digest,
    thumbnail_directory,
)


def render(text: str, destination: Path, povray: str, transparent: bool) -> None:
    import subprocess
    import tempfile

    with tempfile.TemporaryDirectory(prefix="ycrystal-thumb-") as tmp:
        directory = Path(tmp)
        (directory / "scene.pov").write_text(text, encoding="utf-8")
        settings = RenderSettings(
            THUMBNAIL_SIZE, THUMBNAIL_SIZE, transparent_background=transparent
        )
        (directory / "scene.ini").write_text(
            render_ini(settings, "scene.pov", "scene.png"), encoding="utf-8"
        )
        completed = subprocess.run(
            [povray, "scene.ini"], cwd=directory, capture_output=True, text=True, timeout=600
        )
        result = finish_job_like(directory, completed)
        if result is None:
            sys.exit(f"POV-Ray failed for {destination.name}:\n{completed.stderr[-2000:]}")
        destination.parent.mkdir(parents=True, exist_ok=True)
        copy_result(result, destination)
        with Image.open(destination) as image:
            assert image.size == (THUMBNAIL_SIZE, THUMBNAIL_SIZE), image.size


def finish_job_like(directory: Path, completed) -> Path | None:  # noqa: ANN001
    image = directory / "scene.png"
    return image if completed.returncode == 0 and image.is_file() else None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--all", action="store_true", help="render every thumbnail")
    parser.add_argument("--povray", help="POV-Ray executable (default: discovery)")
    args = parser.parse_args()
    povray = args.povray or find_povray()
    root = thumbnail_directory()
    index = load_index()
    jobs = [("materials", m.id, material_scene(m.id), False) for m in materials()]
    jobs += [("environments", e.id, environment_scene(e.id), e.transparent) for e in environments()]
    rendered = 0
    for folder, preset_id, text, transparent in jobs:
        digest = scene_digest(text)
        target = root / folder / f"{preset_id}.png"
        if not args.all and index[folder].get(preset_id) == digest and target.is_file():
            continue
        print(f"rendering {folder}/{preset_id}")
        render(text, target, povray, transparent)
        index[folder][preset_id] = digest
        rendered += 1
    known = {folder: {pid for f, pid, *_ in jobs if f == folder} for folder in index}
    for folder, table in index.items():
        for stale in set(table) - known[folder]:
            del table[stale]
            (root / folder / f"{stale}.png").unlink(missing_ok=True)
    ordered = {folder: dict(sorted(table.items())) for folder, table in index.items()}
    (root / "index.json").write_text(json.dumps(ordered, indent=1) + "\n", encoding="utf-8")
    print(f"{rendered} thumbnails rendered; index written to {root / 'index.json'}")


if __name__ == "__main__":
    main()
