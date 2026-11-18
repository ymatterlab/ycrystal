"""Measure POV-Ray render time and memory through the production command line.

FR-VALIDATION-01, question D: what does a modest, a medium, and a large crystal figure
cost? Every measurement is one run of ``ycrystal INPUT --render OUT.png --width W
--height H`` in a new process, exactly as a user would run it; no rendering code of
its own. (``scripts/benchmark_scene.py`` measures the interactive 3D view instead.)

Cases
-----
- SrTiO3 at growing repetitions (1, 4, 8, 12 cells per axis), satin, white background,
  cell edges and bonds as by default, 800 × 600;
- the 4 × 4 × 4 case at 400 × 300 and 1600 × 1200 (resolution);
- SrTiO3 2 × 2 × 2 plain, in a studio (floor, area light, soft shadows), and in the
  studio with chrome or glass (cost of shadows, reflection, refraction);
- MgB2 with ``--style examples/grey-studio.ycstyle`` (the command-line style path).

The inputs of the SrTiO3 cases are projects written into ``OUT/inputs`` with the
production functions (``load_input``, ``save_project``) from ``tests/fixtures``; their
SHA-256 and the fixture's are recorded.

Method
------
For each case, ``--warmups`` untimed runs come first (the first also saves a snapshot
and provenance record in ``OUT/snapshots`` with ``--save-project``, the reference set
for ``scripts/replay_check.py``); then ``--repeats`` timed runs. Recorded per run:

- ``wall_s``: wall-clock time of the whole command (start of Python to exit);
- ``render_s``: the time ``ycrystal`` prints for the render itself (scene, POV-Ray,
  copying the image), at its printed resolution of 0.1 s;
- ``peak_rss_mib``: peak resident memory of the largest process of the command, the
  Python process or POV-Ray, from ``wait4`` in a small launcher process (Linux:
  verified to include POV-Ray, a child of the command, and not the benchmark's own
  memory; macOS: not verified; Windows: not measured). The launcher's own size, about
  10 MiB, is the smallest value it can report.

The summary of each quantity is the median, minimum, and maximum of the timed runs.
The results go to ``OUT/benchmark.json``; a table is printed.

Usage::

    python scripts/benchmark_render.py --out artifacts/benchmark            # all cases
    python scripts/benchmark_render.py --quick --out artifacts/benchmark    # up to 8×8×8
    python scripts/benchmark_render.py --quick --scale 0.5 --repeats 3 --out DIR  # lighter
    python scripts/benchmark_render.py --cases srtio3-1 effects-glass --repeats 3 --out DIR
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import platform
import re
import shlex
import subprocess
import sys
import time
from dataclasses import dataclass, replace
from pathlib import Path
from statistics import median

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"
STYLE = ROOT / "examples" / "grey-studio.ycstyle"


@dataclass(frozen=True)
class Case:
    """One benchmark case: what is rendered, and how."""

    id: str
    description: str
    fixture: str
    repetitions: tuple[int, int, int] = (1, 1, 1)
    material: str = "satin"
    environment: str = "white"  # an environment preset
    width: int = 800
    height: int = 600
    style: bool = False  # MgB2 with the grey studio style from the command line


def _srtio3(n: int, **kwargs) -> Case:
    return Case(
        f"srtio3-{n}", f"SrTiO3 {n}×{n}×{n}, satin, white", "SrTiO3.cif", (n, n, n), **kwargs
    )


CASES = {
    case.id: case
    for case in (
        _srtio3(1),
        _srtio3(4),
        _srtio3(8),
        _srtio3(12),
        replace(_srtio3(4), id="srtio3-4-small", width=400, height=300),
        replace(_srtio3(4), id="srtio3-4-large", width=1600, height=1200),
        Case("effects-plain", "SrTiO3 2×2×2, satin, white", "SrTiO3.cif", (2, 2, 2)),
        Case(
            "effects-studio",
            "SrTiO3 2×2×2, satin, studio (floor, area light, soft shadows)",
            "SrTiO3.cif",
            (2, 2, 2),
            environment="studio_white",
        ),
        Case(
            "effects-chrome",
            "SrTiO3 2×2×2, chrome (reflection), studio",
            "SrTiO3.cif",
            (2, 2, 2),
            material="chrome",
            environment="studio_white",
        ),
        Case(
            "effects-glass",
            "SrTiO3 2×2×2, glass (refraction), studio",
            "SrTiO3.cif",
            (2, 2, 2),
            material="glass",
            environment="studio_white",
        ),
        Case("mgb2-style", "MgB2 with --style grey-studio.ycstyle", "MgB2.cif", style=True),
    )
}
QUICK = [case for case in CASES if case not in ("srtio3-12", "srtio3-4-large")]

_RENDERED = re.compile(r"Rendered .* in ([\d.]+) s")


# ----- system description --------------------------------------------------------------------
def _run(command: list[str]) -> str:
    try:
        return subprocess.run(command, capture_output=True, text=True, timeout=10).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def _cpu_model() -> str:
    if sys.platform.startswith("linux"):
        try:
            for line in Path("/proc/cpuinfo").read_text().splitlines():
                if line.startswith("model name"):
                    return line.split(":", 1)[1].strip()
        except OSError:
            pass
    if sys.platform == "darwin":
        return _run(["sysctl", "-n", "machdep.cpu.brand_string"])
    return platform.processor()


def _memory_gib() -> float | None:
    try:
        if sys.platform.startswith("linux"):
            for line in Path("/proc/meminfo").read_text().splitlines():
                if line.startswith("MemTotal:"):
                    return round(int(line.split()[1]) / 1024**2, 1)
        if sys.platform == "darwin":
            return round(int(_run(["sysctl", "-n", "hw.memsize"])) / 1024**3, 1)
    except (OSError, ValueError):
        pass
    return None


def _os_name() -> str:
    if sys.platform.startswith("linux"):
        try:
            return platform.freedesktop_os_release().get("PRETTY_NAME", "Linux")
        except OSError:
            return "Linux"
    if sys.platform == "darwin":
        return f"macOS {platform.mac_ver()[0]}"
    return platform.platform(terse=True)


def system_info(povray: str | None) -> dict:
    """Return the operating system, hardware, and software versions (no host or user names)."""
    import ase
    import numpy

    from ycrystal import __version__
    from ycrystal.render.povray import povray_version

    return {
        "os": _os_name(),
        "kernel": f"{platform.system()} {platform.release()}",
        "machine": platform.machine(),
        "cpu": _cpu_model(),
        "logical_cpus": os.cpu_count(),
        "memory_gib": _memory_gib(),
        "python": platform.python_version(),
        "numpy": numpy.__version__,
        "ase": ase.__version__,
        "ycrystal": __version__,
        "povray": povray_version(povray) if povray else None,
    }


def sha256(path: Path) -> str:
    import hashlib

    return hashlib.sha256(path.read_bytes()).hexdigest()


# ----- inputs ----------------------------------------------------------------------------------
def prepare_input(case: Case, folder: Path) -> tuple[Path, dict]:
    """Write the case's input (a project, or the fixture itself); return it and its counts."""
    from ycrystal.batch import apply_style_file, load_input
    from ycrystal.core.scene import SceneSettings, build_geometry
    from ycrystal.io.project import Project, save_project
    from ycrystal.presets import environment_from_preset

    source = FIXTURES / case.fixture
    if case.style:
        project, _ = apply_style_file(load_input(source), STYLE)
        path = source
    else:
        structure = load_input(source).structure
        scene = SceneSettings(repetitions=case.repetitions, material=case.material)
        project = Project(structure, scene, environment_from_preset(case.environment))
        path = save_project(folder / f"{case.id}.ycrystal", project)
    geometry = build_geometry(project.structure, project.scene)
    counts = {"displayed_atoms": len(geometry), "bonds": int(len(geometry.bonds))}
    return path, counts


def command(case: Case, source: Path, image: Path, povray: str, size, extra=()) -> list[str]:
    width, height = size
    args = [sys.executable, "-m", "ycrystal", str(source)]
    if case.style:
        args += ["--style", str(STYLE)]
    args += ["--render", str(image), "--width", str(width), "--height", str(height)]
    return [*args, "--povray", povray, *extra]


# Runs one command and reports its wall time, exit status, output, and peak memory as
# JSON. It runs in a small, new process: on Linux a child's ru_maxrss also counts the
# memory of the process that started it (inherited at fork and exec), so measuring from
# the benchmark process itself, which grows while it prepares inputs, would report that
# process's size instead of the command's.
LAUNCHER = """
import json, os, subprocess, sys, time
started = time.perf_counter()
process = subprocess.Popen(
    sys.argv[1:], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors="replace"
)
with process.stdout:
    output = process.stdout.read()
_, status, usage = os.wait4(process.pid, 0)
print(json.dumps({
    "wall": time.perf_counter() - started,
    "status": os.waitstatus_to_exitcode(status),
    "maxrss": usage.ru_maxrss,
    "output": output,
}))
"""


def run_once(args: list[str]) -> dict:
    """Run one command; return its wall time, printed render time, and peak memory."""
    peak = None
    if hasattr(os, "wait4"):
        launched = subprocess.run(
            [sys.executable, "-I", "-c", LAUNCHER, *args], capture_output=True, text=True
        )
        if launched.returncode != 0:
            raise RuntimeError(f"the measuring process failed:\n{launched.stderr.strip()}")
        result = json.loads(launched.stdout)
        wall, status, output = result["wall"], result["status"], result["output"]
        # ru_maxrss is in KiB on Linux and in bytes on macOS.
        peak = result["maxrss"] / (1024**2 if sys.platform == "darwin" else 1024)
    else:  # pragma: no cover - Windows: time only
        started = time.perf_counter()
        completed = subprocess.run(args, capture_output=True, text=True, errors="replace")
        wall, status = time.perf_counter() - started, completed.returncode
        output = completed.stdout + completed.stderr
    if status != 0:
        raise RuntimeError(f"{shlex.join(args)} failed:\n{output.strip()}")
    match = _RENDERED.search(output)
    return {
        "wall_s": round(wall, 4),
        "render_s": float(match.group(1)) if match else None,
        "peak_rss_mib": None if peak is None else round(peak, 1),
    }


def summary(values: list[float | None]) -> dict | None:
    numbers = [v for v in values if v is not None]
    if not numbers:
        return None
    return {"median": round(median(numbers), 4), "min": min(numbers), "max": max(numbers)}


# ----- main --------------------------------------------------------------------------------------
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", required=True, type=Path, help="folder for inputs, images, JSON")
    parser.add_argument("--cases", nargs="+", choices=list(CASES), help="cases to run")
    parser.add_argument("--quick", action="store_true", help="leave out the two largest cases")
    parser.add_argument("--warmups", type=int, default=1, help="untimed runs per case (≥ 1)")
    parser.add_argument("--repeats", type=int, default=5, help="timed runs per case (≥ 1)")
    parser.add_argument("--povray", help="POV-Ray executable (default: as ycrystal finds it)")
    parser.add_argument(
        "--scale", type=float, default=1.0, help="multiply every image size (e.g. 0.5)"
    )
    parser.add_argument("--overwrite", action="store_true", help="reuse a non-empty --out")
    args = parser.parse_args(argv)
    if args.warmups < 1 or args.repeats < 1:
        parser.error("--warmups and --repeats must be at least 1")
    if not 0.02 <= args.scale <= 4:
        parser.error("--scale must be between 0.02 and 4")
    if args.out.exists() and any(args.out.iterdir()) and not args.overwrite:
        parser.error(f"{args.out} is not empty; use --overwrite or another folder")

    from ycrystal.render.povray import PovrayNotFoundError, find_povray

    try:
        povray = find_povray(args.povray)
    except PovrayNotFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    names = args.cases or (QUICK if args.quick else list(CASES))
    folders = {name: args.out / name for name in ("inputs", "renders", "snapshots")}
    for folder in folders.values():
        folder.mkdir(parents=True, exist_ok=True)
    report = {
        "format": "ycrystal-benchmark",
        "schema_version": 1,
        "created": _dt.datetime.now(_dt.UTC).isoformat(timespec="seconds"),
        "options": {  # no paths: the report may be published
            "cases": names,
            "warmups": args.warmups,
            "repeats": args.repeats,
            "scale": args.scale,
        },
        "method": {
            "warmups": args.warmups,
            "repeats": args.repeats,
            "statistic": "median, minimum, and maximum of the timed runs",
            "wall_s": "whole command, new process each run",
            "render_s": "render time printed by ycrystal (0.1 s resolution)",
            "peak_rss_mib": "largest process of the command (Python or POV-Ray), from wait4 "
            "in a small launcher process (its own size, about 10 MiB, is the floor)",
        },
        "system": system_info(povray),
        "cases": [],
    }
    print(
        f"{'case':<16} {'atoms':>6} {'bonds':>6} {'size':>10} {'wall s (min-max)':>22} "
        f"{'render s':>9} {'MiB':>7}"
    )
    for name in names:
        case = CASES[name]
        size = (max(16, round(case.width * args.scale)), max(16, round(case.height * args.scale)))
        source, counts = prepare_input(case, folders["inputs"])
        reference = folders["snapshots"] / f"{name}.png"
        snapshot = ["--save-project", str(reference.with_suffix(".ycrystal")), "--overwrite"]
        for number in range(args.warmups):
            image = reference if number == 0 else folders["renders"] / f"{name}.png"
            run_once(command(case, source, image, povray, size, snapshot if number == 0 else ()))
        image = folders["renders"] / f"{name}.png"
        runs = [run_once(command(case, source, image, povray, size)) for _ in range(args.repeats)]
        entry = {
            "id": name,
            "description": case.description,
            "input": {"name": source.name, "sha256": sha256(source)},
            "fixture": {"name": case.fixture, "sha256": sha256(FIXTURES / case.fixture)},
            "style": {"name": STYLE.name, "sha256": sha256(STYLE)} if case.style else None,
            "repetitions": list(case.repetitions),
            "material": None if case.style else case.material,
            "environment": None if case.style else case.environment,
            "width": size[0],
            "height": size[1],
            **counts,
            "snapshot": f"snapshots/{name}.ycrystal",
            "runs": runs,
            "summary": {key: summary([run[key] for run in runs]) for key in runs[0]},
        }
        report["cases"].append(entry)
        wall, render, memory = (entry["summary"][k] for k in ("wall_s", "render_s", "peak_rss_mib"))
        spread = f"{wall['median']:.2f} ({wall['min']:.2f}-{wall['max']:.2f})"
        print(
            f"{name:<16} {counts['displayed_atoms']:>6} {counts['bonds']:>6} "
            f"{size[0]:>5}×{size[1]:<4} {spread:>22} "
            f"{render['median'] if render else '-':>9} {memory['median'] if memory else '-':>7}"
        )
    out = args.out / "benchmark.json"
    out.write_text(json.dumps(report, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
