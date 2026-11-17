"""Render the snapshots of a reference folder again and compare the images.

FR-VALIDATION-01, question C: does a figure saved as a snapshot come out the same on
another computer, or with another POV-Ray? Make a reference folder on one machine, copy
it to the other, and run this script there (or on the same machine, as a control).

A reference folder holds snapshots with their provenance records (``NAME.ycrystal``,
``NAME.provenance.json``, ``NAME.png``), for example ``OUT/snapshots`` of
``scripts/benchmark_render.py``, figures saved with ``--save-project``, or a batch run
with ``"save_projects": true``. For each record the script:

1. checks that the reference image and snapshot still have the SHA-256 the record
   states (otherwise the figure is ``modified`` and not compared);
2. renders the snapshot with ``ycrystal SNAPSHOT --render OUT/NAME.png`` (a new
   process, the production command line);
3. compares the two images pixel by pixel: largest and mean absolute difference per
   8-bit channel, and the fraction of pixels differing by more than ``--tolerance``.

A figure is ``same`` when no channel of any pixel differs by more than the tolerance
(default 1 of 255), ``different`` otherwise; ``failed`` if the render failed. The
report ``OUT/replay-check.json`` also states both systems and POV-Ray versions. Exit
status: 0 if every figure is ``same``, 1 otherwise, 2 if no record was found.

Usage::

    python scripts/replay_check.py REFERENCE --out DIR [--tolerance 1] [--povray PATH]
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from benchmark_render import sha256, system_info  # noqa: E402


def compare(reference: Path, replay: Path, tolerance: int) -> dict:
    """Return pixel statistics of two images (RGBA, 8 bits per channel)."""
    from ycrystal.render.imagecheck import load_rgba

    a, b = load_rgba(reference).astype(int), load_rgba(replay).astype(int)
    if a.shape != b.shape:
        return {"same_size": False, "reference_size": a.shape[1::-1], "replay_size": b.shape[1::-1]}
    difference = np.abs(a - b).max(axis=2)  # the largest channel difference per pixel
    return {
        "same_size": True,
        "max_abs_difference": int(difference.max()),
        "mean_abs_difference": round(float(np.abs(a - b).mean()), 6),
        "fraction_beyond_tolerance": round(float(np.mean(difference > tolerance)), 6),
        "identical_pixels": bool(difference.max() == 0),
    }


def check(record_path: Path, base: Path, out: Path, tolerance: int, povray: str | None) -> dict:
    """Check, replay, and compare one figure; return its entry of the report."""
    folder = record_path.parent
    record = json.loads(record_path.read_text(encoding="utf-8"))
    image = folder / (record["image"].get("path") or record["image"]["name"])
    project = folder / (record["project"].get("path") or record["project"]["name"])
    entry = {
        "record": record_path.relative_to(base).as_posix(),
        "image": image.name,
        "reference_renderer": record.get("renderer", {}).get("version"),
        "reference_system": record.get("system"),
        "status": "",
        "error": "",
    }
    if record.get("format") != "ycrystal-provenance":
        return {**entry, "status": "failed", "error": "not a Ycrystal provenance record"}
    for name, path in (("image", image), ("project", project)):
        if not path.is_file():
            return {**entry, "status": "failed", "error": f"the {name} {path.name} is missing"}
        if sha256(path) != record[name]["sha256"]:
            return {**entry, "status": "modified", "error": f"the {name} changed after recording"}
    replay = out / folder.relative_to(base) / image.name
    replay.parent.mkdir(parents=True, exist_ok=True)
    command = [sys.executable, "-m", "ycrystal", str(project), "--render", str(replay)]
    if povray:
        command += ["--povray", povray]
    result = subprocess.run(command, capture_output=True, text=True, errors="replace")
    if result.returncode != 0:
        return {**entry, "status": "failed", "error": result.stderr.strip()[-500:]}
    stats = compare(image, replay, tolerance)
    same = stats["same_size"] and stats["max_abs_difference"] <= tolerance
    return {**entry, **stats, "status": "same" if same else "different"}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("reference", type=Path, help="folder with snapshots and records")
    parser.add_argument("--out", required=True, type=Path, help="folder for replays and report")
    parser.add_argument("--tolerance", type=int, default=1, help="allowed difference, 0-255")
    parser.add_argument("--povray", help="POV-Ray executable (default: as ycrystal finds it)")
    args = parser.parse_args(argv)
    if not 0 <= args.tolerance <= 255:
        parser.error("--tolerance must be between 0 and 255")
    records = sorted(args.reference.rglob("*.provenance.json"))
    if not records:
        print(f"ERROR: no provenance records in {args.reference}", file=sys.stderr)
        return 2
    from ycrystal.render.povray import PovrayNotFoundError, find_povray

    try:
        povray = find_povray(args.povray)
    except PovrayNotFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    args.out.mkdir(parents=True, exist_ok=True)
    figures = []
    for record in records:
        entry = check(record, args.reference, args.out, args.tolerance, args.povray)
        figures.append(entry)
        detail = (
            f"max difference {entry['max_abs_difference']}"
            if "max_abs_difference" in entry
            else entry["error"].splitlines()[-1]
            if entry["error"]
            else ""
        )
        print(f"{entry['record']}: {entry['status']} ({detail})")
    counts = {s: sum(f["status"] == s for f in figures) for s in ("same", "different")}
    counts.update({s: sum(f["status"] == s for f in figures) for s in ("modified", "failed")})
    report = {
        "format": "ycrystal-replay-check",
        "schema_version": 1,
        "created": _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"),
        "reference": args.reference.name,  # folder names only: the report may be published
        "tolerance": args.tolerance,
        "system": system_info(povray),
        "summary": {"figures": len(figures), **counts},
        "figures": figures,
    }
    path = args.out / "replay-check.json"
    path.write_text(json.dumps(report, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{counts['same']} of {len(figures)} figure(s) the same; report: {path}")
    return 0 if counts["same"] == len(figures) else 1


if __name__ == "__main__":
    raise SystemExit(main())
