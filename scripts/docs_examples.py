"""Exercise the display-independent documentation examples from a source checkout."""

from __future__ import annotations

import tempfile
from pathlib import Path

import numpy as np

from ycrystal.core.camera import default_camera
from ycrystal.core.samples import perovskite_srtio3
from ycrystal.core.scene import Environment, SceneSettings, build_geometry
from ycrystal.io.project import Project, load_project, save_project
from ycrystal.io.readers import read_structure
from ycrystal.render.pov_writer import RenderSettings, write_scene_files


def main() -> None:
    structure = perovskite_srtio3()
    original = structure.positions.copy()
    geometry = build_geometry(structure)
    assert (len(structure), len(geometry)) == (5, 15)
    corner = (0, (1, 1, 1))
    scene = SceneSettings(hidden=frozenset({corner}))
    hidden = build_geometry(structure, scene)
    assert (len(hidden), hidden.hidden_count, hidden.index_of(corner)) == (14, 1, None)
    for (source, offset), position in zip(hidden.atom_ids, hidden.positions, strict=True):
        np.testing.assert_allclose(position, original[source] + np.array(offset) @ structure.cell)
    np.testing.assert_array_equal(structure.positions, original)

    settings = RenderSettings(width=640, height=400)
    points, radii = hidden.points_and_radii()
    camera = default_camera(points, radii, settings.width / settings.height)
    np.testing.assert_allclose(camera.project([camera.focal_point], 640, 400), [[320, 200]])
    imported = read_structure("tests/fixtures/MgB2.cif")
    assert imported.composition() == "MgB2"

    with tempfile.TemporaryDirectory(prefix="ycrystal-docs-example-") as temporary:
        directory = Path(temporary)
        project = Project(structure, scene=scene, camera=camera, output=settings)
        saved = save_project(directory / "SrTiO3.ycrystal", project)
        reopened = load_project(saved)
        np.testing.assert_array_equal(reopened.structure.positions, original)
        assert reopened.scene.hidden == scene.hidden
        assert reopened.camera == camera
        pov, ini, image = write_scene_files(
            directory, "SrTiO3", hidden, camera, Environment(), settings
        )
        assert pov.is_file() and ini.is_file() and not image.exists()
        assert "(1 atoms hidden in Ycrystal are not written.)" in pov.read_text()
        assert 'Output_File_Name="SrTiO3.png"' in ini.read_text()
    print("Documentation examples passed (no display or renderer).")


if __name__ == "__main__":
    main()
