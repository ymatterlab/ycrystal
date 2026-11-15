"""Regenerate the documentation's genuine SrTiO3 example with POV-Ray, without Qt."""

from __future__ import annotations

import argparse
from pathlib import Path

from ycrystal.core.camera import default_camera
from ycrystal.core.samples import perovskite_srtio3
from ycrystal.core.scene import Environment, build_geometry
from ycrystal.render.jobs import copy_result, prepare_job, run_job
from ycrystal.render.pov_writer import RenderSettings
from ycrystal.render.povray import find_povray


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("docs/assets/perovskite.png"))
    parser.add_argument("--povray", default=None)
    args = parser.parse_args()
    executable = find_povray(args.povray)
    geometry = build_geometry(perovskite_srtio3())
    settings = RenderSettings(width=640, height=400)
    points, radii = geometry.points_and_radii()
    camera = default_camera(points, radii, settings.width / settings.height)
    job = prepare_job(geometry, camera, Environment(), settings)
    try:
        result = run_job(job, executable)
        if not result.ok or result.image_path is None:
            print(result.message)
            return 1
        destination = copy_result(result.image_path, args.output)
        print(f"Rendered {settings.width} x {settings.height}: {destination}")
    finally:
        job.cleanup()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
