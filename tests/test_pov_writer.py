import re

import numpy as np
import pytest

from ycrystal.core.camera import Camera
from ycrystal.core.samples import triclinic_marker
from ycrystal.core.scene import Environment, build_geometry
from ycrystal.render.pov_writer import RenderSettings, render_ini, scene_to_pov, write_scene_files

VEC = r"<\s*([-\d.e]+),\s*([-\d.e]+),\s*([-\d.e]+)\s*>"


def camera_vectors(pov: str) -> dict[str, np.ndarray]:
    block = re.search(r"camera \{(.*?)\n\}", pov, re.S).group(1)
    vectors = {}
    for key in ("location", "direction", "right", "up"):
        match = re.search(rf"\b{key}\s+{VEC}", block)
        vectors[key] = np.array([float(v) for v in match.groups()])
    return vectors


@pytest.fixture
def scene():
    geometry = build_geometry(triclinic_marker())
    points, radii = geometry.points_and_radii()
    camera = (
        Camera.looking_along((0.4, -1, -0.3), (0, 0, 1))
        .orbit(azimuth=-35, elevation=20)
        .roll(10)
        .fitted(points, radii, 1.6)
        .pan(0.6, -0.2)
    )
    return geometry, camera


def test_camera_block_uses_explicit_basis(scene):
    geometry, camera = scene
    settings = RenderSettings(width=640, height=400)
    pov = scene_to_pov(geometry, camera, Environment(), settings)
    assert pov.count("#version 3.7;") == 1
    assert "orthographic" in pov
    assert "look_at" not in pov and "sky" not in pov and "angle" not in pov
    assert not any(line.startswith("#include") for line in pov.splitlines())
    vectors = camera_vectors(pov)
    r, u, d = camera.basis()
    width, height = camera.visible_size(640, 400)
    np.testing.assert_allclose(vectors["right"], r * width, atol=2e-6)
    np.testing.assert_allclose(vectors["up"], u * height, atol=2e-6)
    np.testing.assert_allclose(vectors["direction"], d, atol=2e-6)
    # The image centre (location) projects onto the focal point.
    offset = vectors["location"] - np.asarray(camera.focal_point)
    np.testing.assert_allclose(offset - (offset @ d) * d, 0, atol=2e-5)
    # Everything drawn lies in front of the orthographic eye.
    points, radii = geometry.points_and_radii()
    assert np.all((points - vectors["location"]) @ d - radii > 0)


def test_atoms_written_with_ids_and_textures(scene):
    geometry, camera = scene
    pov = scene_to_pov(geometry, camera, Environment(), RenderSettings())
    spheres = [line for line in pov.splitlines() if line.startswith("sphere") and "atom" in line]
    assert len(spheres) == len(geometry)
    for (source, image), element, line in zip(
        geometry.atom_ids, geometry.elements, spheres, strict=True
    ):
        assert f"// atom #{source + 1} {element} image {image}" in line
        assert f"Ycr_Texture_{element}" in line
    for element in set(geometry.elements):
        assert f"#declare Ycr_Texture_{element} = texture" in pov
    assert pov.count("cylinder {") == 12


def test_background_options(scene):
    geometry, camera = scene
    opaque = scene_to_pov(geometry, camera, Environment(background=(1, 1, 1)), RenderSettings())
    assert "background { color Ycr_sRGB(1.0000, 1.0000, 1.0000) }" in opaque
    clear = scene_to_pov(
        geometry, camera, Environment(), RenderSettings(transparent_background=True)
    )
    assert "background { color rgbt <0, 0, 0, 1> }" in clear


def test_ini_sets_every_output_option():
    ini = render_ini(
        RenderSettings(width=321, height=123, transparent_background=True), "scene.pov", "scene.png"
    )
    options = dict(
        line.split("=", 1) for line in ini.splitlines() if "=" in line and not line.startswith(";")
    )
    assert options["Width"] == "321" and options["Height"] == "123"
    assert options["Output_Alpha"] == "on"
    assert options["Display"] == "off"
    assert options["Output_File_Type"] == "N"
    assert options["File_Gamma"] == "sRGB"
    assert options["Antialias"] == "on"
    assert options["Input_File_Name"] == '"scene.pov"'
    assert options["Output_File_Name"] == '"scene.png"'
    opaque = render_ini(RenderSettings(), "a.pov", "a.png")
    assert "Output_Alpha=off" in opaque


def test_write_files_to_directory_with_spaces_and_unicode(tmp_path, scene):
    geometry, camera = scene
    target = tmp_path / "my figures ü"
    target.mkdir()
    pov, ini, image = write_scene_files(
        target, "Fe₂O₃ view", geometry, camera, Environment(), RenderSettings()
    )
    assert pov.is_file() and ini.is_file()
    assert f'Input_File_Name="{pov.name}"' in ini.read_text(encoding="utf-8")
    assert image.name == "Fe₂O₃ view.png"


def test_render_settings_validation():
    with pytest.raises(ValueError):
        RenderSettings(width=0, height=10)
