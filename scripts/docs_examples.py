"""Exercise the display-independent documentation examples from a source checkout."""

from __future__ import annotations

import contextlib
import io
import json
import tempfile
from dataclasses import replace
from pathlib import Path

import numpy as np

from ycrystal.app import main as ycrystal
from ycrystal.core.camera import default_camera
from ycrystal.core.samples import perovskite_srtio3
from ycrystal.core.scene import Environment, SceneSettings, build_geometry
from ycrystal.io.project import Project, load_project, save_project
from ycrystal.io.readers import read_structure
from ycrystal.io.style import Style, apply_style, load_style, save_style
from ycrystal.presets import environment_from_preset, environments, materials
from ycrystal.render.pov_writer import RenderSettings, required_includes, write_scene_files


def main() -> None:
    structure = perovskite_srtio3()
    original = structure.positions.copy()
    geometry = build_geometry(structure)
    assert (len(structure), len(geometry)) == (5, 15)
    expanded = build_geometry(structure, SceneSettings(repetitions=(2, 2, 2)))
    assert (len(expanded), len(expanded.bonds)) == (71, 192)
    no_bonds = replace(SceneSettings().bonds, enabled=False)
    assert len(build_geometry(structure, SceneSettings(bonds=no_bonds)).bonds) == 0
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

        # Presets: a glass material on a transparent background.
        glass = build_geometry(structure, replace(scene, material="glass"))
        clear = environment_from_preset("transparent")
        pov, ini, _ = write_scene_files(directory, "glass", glass, camera, clear, settings)
        assert "interior { ior 1.45 }" in pov.read_text() and clear.transparent
        assert "Output_Alpha=on" in ini.read_text()
        assert len(materials()) >= 20 and len(environments()) >= 12

        # Overrides: gold Ti (element), one chrome Sr corner (atom), in a white studio.
        styled = scene.with_element_material("Ti", "gold").with_atom_materials(
            [(0, (0, 0, 0))], "chrome"
        )
        studio = build_geometry(structure, styled)
        assert studio.materials[studio.index_of((0, (0, 0, 0)))] == "chrome"
        assert set(studio.materials) == {"satin", "gold", "chrome"}
        environment = environment_from_preset("studio_white")
        pov, _, _ = write_scene_files(directory, "studio", studio, camera, environment, settings)
        text = pov.read_text()
        assert '#include "metals.inc"' in text and "// Floor:" in text
        assert required_includes(studio) == ("metals.inc", "textures.inc")

        # Styles: reuse the look with another structure; coordinates are untouched.
        style_path = save_style(
            directory / "look.ycstyle",
            Style.from_state(structure, styled, environment, (640, 400)),
        )
        mgb2_positions = imported.positions.copy()
        result = apply_style(
            load_style(style_path), imported, SceneSettings(), Environment(), (1200, 800)
        )
        assert result.scene.element_materials == ()  # no Ti in MgB2
        assert result.environment.preset == "studio_white" and result.output_size == (640, 400)
        assert any("Ti" in note for note in result.notes)
        np.testing.assert_array_equal(imported.positions, mgb2_positions)

        # Styles from the command line (examples guide): the grey studio for MgB2.
        root = Path(__file__).resolve().parents[1]
        args = [str(root / "tests" / "fixtures" / "MgB2.cif"), "--style"]
        args += [str(root / "examples" / "grey-studio.ycstyle"), "--export-pov"]
        stderr = io.StringIO()
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(stderr):
            assert ycrystal([*args, str(directory / "MgB2")]) == 0
        assert stderr.getvalue() == (
            "WARNING: Element overrides for O, Ti were not applied: the structure has no O, Ti.\n"
        )
        ini = (directory / "MgB2.ini").read_text()
        assert "Width=800" in ini and "Height=600" in ini  # the style's output size
        assert "// Floor:" in (directory / "MgB2.pov").read_text()  # its grey studio

        # Element mapping (examples guide): Ti's chrome goes to Zr in BaZrO3, no warning.
        args = [str(root / "tests" / "fixtures" / "BaZrO3.cif"), "--style"]
        args += [str(root / "examples" / "grey-studio.ycstyle"), "--element-map", "Ti=Zr"]
        stderr = io.StringIO()
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(stderr):
            assert ycrystal([*args, "--export-pov", str(directory / "BaZrO3")]) == 0
        assert stderr.getvalue() == ""
        zr = next(
            line
            for line in (directory / "BaZrO3.pov").read_text().splitlines()
            if line.startswith("sphere") and "// atom #2 Zr" in line
        )
        assert "Ycr_Texture_chrome" in zr
        # The two further mapping examples and the warnings the guide quotes.
        style = str(root / "examples" / "grey-studio.ycstyle")
        for structure, mapping, warning in (
            (
                "MgB2.cif",
                "Ti=Mg",
                "Element overrides for O were not applied: the structure has no O.",
            ),
            (
                "BaZrO3.cif",
                "Ti=Zr,O=-",
                "Element settings for O were left out by the element mapping.",
            ),
        ):
            args = [str(root / "tests" / "fixtures" / structure), "--style", style]
            args += ["--element-map", mapping, "--export-pov", str(directory / "mapped")]
            stderr = io.StringIO()
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(stderr):
                assert ycrystal(args) == 0
            assert stderr.getvalue() == f"WARNING: {warning}\n"
        # Choose the view and framing (examples guide): down c, a fixed scale, a refit.
        fixtures = root / "tests" / "fixtures"
        with contextlib.redirect_stdout(io.StringIO()):
            assert (
                ycrystal(
                    [
                        str(fixtures / "MgB2.cif"),
                        "--view",
                        "c",
                        "--export-pov",
                        str(directory / "MgB2-c"),
                    ]
                )
                == 0
            )
            for name in ("SrTiO3", "BaZrO3"):
                args = [str(fixtures / f"{name}.cif"), "--view", "a", "--view-height", "9"]
                args += ["--width", "600", "--height", "600", "--export-pov"]
                assert ycrystal([*args, str(directory / f"{name}-a")]) == 0
            refit = [str(root / "examples" / "MgB2-gradient.ycrystal"), "--style"]
            refit += [str(root / "examples" / "grey-studio.ycstyle"), "--style-parts", "display"]
            assert (
                ycrystal(
                    [*refit, "--camera-policy", "fit", "--export-pov", str(directory / "refit")]
                )
                == 0
            )
        assert "direction <0, 0, -1>" in (directory / "MgB2-c.pov").read_text()
        for name in ("SrTiO3", "BaZrO3"):
            assert "up        <0, 0, 9>" in (directory / f"{name}-a.pov").read_text()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(stderr):
            args = [str(fixtures / "SrTiO3.cif"), "--view", "a", "--view-height", "1"]
            assert ycrystal([*args, "--export-pov", str(directory / "small")]) == 1
        assert "it needs at least 5.85 Å" in stderr.getvalue()
        # Render a series (examples guide): the dry run prints what the guide quotes.
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            args = ["--batch", str(root / "examples" / "batch-series.json"), "--output-dir"]
            assert ycrystal([*args, str(directory / "renders"), "--dry-run"]) == 0
        guide = (root / "docs" / "guide" / "examples.md").read_text(encoding="utf-8")
        for line in (stderr.getvalue() + stdout.getvalue()).splitlines():
            assert line in guide, line
        assert not (directory / "renders").exists()
        # Reproducible figures (reproducibility guide): a dry run lists the snapshots.
        manifest = directory / "snapshots.json"
        jobs = [{"id": "SrTiO3", "input": str(fixtures / "SrTiO3.cif")}]
        jobs.append({"id": "BaZrO3", "input": str(fixtures / "BaZrO3.cif")})
        jobs[-1]["element_map"] = {"Ti": "Zr"}
        defaults = {"style": str(root / "examples" / "grey-studio.ycstyle"), "view": "a"}
        defaults.update(width=600, height=450)
        document = {"format": "ycrystal-batch", "schema_version": 1, "save_projects": True}
        document.update(defaults=defaults, jobs=jobs)
        manifest.write_text(json.dumps(document), encoding="utf-8")
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(io.StringIO()):
            args = ["--batch", str(manifest), "--output-dir", str(directory / "figures")]
            assert ycrystal([*args, "--dry-run"]) == 0
        line = "SrTiO3: would render SrTiO3.png and save SrTiO3.ycrystal (600 × 450, 15 atoms)"
        guide = (root / "docs" / "guide" / "reproducibility.md").read_text(encoding="utf-8")
        assert line in stdout.getvalue() and line in guide
        assert not (directory / "figures").exists()
    print("Documentation examples passed (no display or renderer).")


if __name__ == "__main__":
    main()
