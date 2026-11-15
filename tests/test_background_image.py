"""FR-BGIMAGE-01: background pictures (framing, import, writer, packages, POV-Ray renders)."""

import hashlib
import itertools
import json
import shutil
import zipfile
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from ycrystal.core.background import BackgroundImage, placement
from ycrystal.core.camera import Camera
from ycrystal.core.samples import perovskite_srtio3
from ycrystal.core.scene import Environment, SceneSettings, build_geometry
from ycrystal.core.structure import Structure
from ycrystal.io import images
from ycrystal.io.images import ImageError, import_image
from ycrystal.io.package import is_package
from ycrystal.io.project import SCHEMA_VERSION, Project, ProjectError, load_project, save_project
from ycrystal.io.style import Style, StyleError, load_style, save_style
from ycrystal.render.jobs import prepare_job, run_job
from ycrystal.render.pov_writer import RenderSettings, scene_to_pov, write_scene_files

RED, GREEN, BLUE, YELLOW = (200, 30, 30), (30, 200, 30), (30, 30, 200), (230, 220, 40)
MAGENTA = (1.0, 0.0, 1.0)


def quadrants(width=40, height=30, hole=False):
    """Picture with red/green (top) and blue/yellow (bottom) quadrants."""
    image = Image.new("RGBA", (width, height))
    for x, y in itertools.product(range(width), range(height)):
        top, left = y < height // 2, x < width // 2
        color = (RED if left else GREEN) if top else (BLUE if left else YELLOW)
        alpha = 0 if hole and abs(x - width / 2) < 3 and abs(y - height / 2) < 3 else 255
        image.putpixel((x, y), (*color, alpha))
    return image


@pytest.fixture
def pictures(tmp_path):
    folder = tmp_path / "Bilder ü"  # spaces and non-ASCII in the source path
    folder.mkdir()
    paths = {}
    quadrants(hole=True).save(folder / "corner hole.png")
    paths["png"] = folder / "corner hole.png"
    quadrants().convert("RGB").save(folder / "corners.jpg", quality=98)
    paths["jpeg"] = folder / "corners.jpg"
    # EXIF orientation 6 ("rotate 90° clockwise to display"): store the picture turned
    # counter-clockwise, so the upright result is the plain quadrant picture.
    exif = Image.Exif()
    exif[0x0112] = 6
    stored = quadrants().convert("RGB").transpose(Image.Transpose.ROTATE_90)
    stored.save(folder / "rotated.jpg", quality=98, exif=exif.tobytes())
    paths["exif"] = folder / "rotated.jpg"
    quadrants(30, 40).save(folder / "portrait.png")
    paths["portrait"] = folder / "portrait.png"
    quadrants(32, 32).save(folder / "square.png")
    paths["square"] = folder / "square.png"
    return paths


def frame_check(fit, ratio, aspect, rect):
    _, _, w, h = rect
    assert w / h == pytest.approx(ratio)
    if fit == "fill":
        assert w >= aspect - 1e-12 and h >= 1 - 1e-12
        assert min(w - aspect, h - 1) == pytest.approx(0, abs=1e-12)
    else:
        assert w <= aspect + 1e-12 and h <= 1 + 1e-12
        assert max(w - aspect, h - 1) == pytest.approx(0, abs=1e-12)


# ----- framing --------------------------------------------------------------------------------
def test_fit_and_fill_keep_the_shape_for_all_orientations():
    for (iw, ih), aspect, fit in itertools.product(
        [(400, 300), (300, 400), (500, 500), (4000, 30)], [1.5, 1.0, 2 / 3], ["fit", "fill"]
    ):
        frame_check(fit, iw / ih, aspect, placement(iw, ih, aspect, fit))
    assert placement(400, 300, 1.5, "fill", zoom=2, offset_x=-0.5, offset_y=0.25) == (
        -0.75,
        0.25,
        3.0,
        2.25,
    )
    with pytest.raises(ValueError):
        placement(0, 10, 1.5)


def test_reference_validation_and_reset():
    good = BackgroundImage("a" * 64, "x.png", 40, 30)
    assert (good.fit, good.zoom, good.offset_x, good.brightness) == ("fill", 1.0, 0.0, 1.0)
    for bad in (
        {"asset": "nothex"},
        {"width": 0},
        {"format": "gif"},
        {"fit": "stretch"},
        {"zoom": 0.0},
        {"zoom": float("nan")},
        {"offset_x": 1.5},
        {"brightness": -0.1},
        {"mean_color": (2, 0, 0)},
    ):
        with pytest.raises(ValueError):
            replace(good, **bad)
    changed = replace(good, fit="fit", zoom=2.0, offset_y=-0.3, brightness=0.5)
    assert changed.reset_framing() == good
    assert Environment(background_mode="image", image=good).live_background() == (
        good.mean_color,
        None,
    )


# ----- import ---------------------------------------------------------------------------------
def test_import_keeps_or_normalises_and_identifies_by_content(pictures, tmp_path):
    png = import_image(pictures["png"])
    assert png.format == "png" and png.has_alpha and (png.width, png.height) == (40, 30)
    assert png.id == hashlib.sha256(pictures["png"].read_bytes()).hexdigest()  # kept as is
    assert png.data == pictures["png"].read_bytes()
    jpeg = import_image(pictures["jpeg"])
    assert jpeg.format == "jpeg" and not jpeg.has_alpha
    rotated = import_image(pictures["exif"])
    assert rotated.format == "png" and (rotated.width, rotated.height) == (40, 30)
    upright = Image.open(__import__("io").BytesIO(rotated.data)).convert("RGB")
    for (x, y), color in {(2, 2): RED, (37, 2): GREEN, (2, 27): BLUE, (37, 27): YELLOW}.items():
        assert np.allclose(upright.getpixel((x, y)), color, atol=12), (x, y)
    # Same content under another name: same identity; same name, other content: different.
    copy = tmp_path / "other name.png"
    shutil.copy(pictures["png"], copy)
    assert import_image(copy).id == png.id
    other = tmp_path / "Bilder ü" / "x" / "corner hole.png"
    other.parent.mkdir()
    quadrants(41, 30).save(other)
    assert import_image(other).id != png.id


def test_unusable_pictures_are_refused(tmp_path, monkeypatch):
    text = tmp_path / "notes.png"
    text.write_text("not a picture")
    with pytest.raises(ImageError, match="not a readable PNG or JPEG"):
        import_image(text)
    data = (tmp_path / "ok.png").write_bytes(b"") or None
    quadrants().save(tmp_path / "ok.png")
    data = (tmp_path / "ok.png").read_bytes()
    (tmp_path / "cut.png").write_bytes(data[: len(data) // 2])
    with pytest.raises(ImageError):
        import_image(tmp_path / "cut.png")
    quadrants().save(tmp_path / "anim.gif")
    with pytest.raises(ImageError, match="only PNG and JPEG"):
        import_image(tmp_path / "anim.gif")
    with pytest.raises(ImageError, match="Cannot read"):
        import_image(tmp_path / "missing.png")
    monkeypatch.setattr(images, "MAX_IMAGE_SIDE", 32)
    with pytest.raises(ImageError, match="pixels per side"):
        import_image(tmp_path / "ok.png")


# ----- writer ---------------------------------------------------------------------------------
def scene(environment, size=(300, 200)):
    geometry = build_geometry(perovskite_srtio3())
    camera = Camera((1.95, 1.95, 40), (1.95, 1.95, 1.95), (0, 1, 0), parallel_scale=4.0)
    return geometry, camera, scene_to_pov(geometry, camera, environment, RenderSettings(*size))


def test_writer_backdrop_and_precedence(pictures):
    asset = import_image(pictures["png"])
    env = Environment(background_mode="image", background=MAGENTA, image=asset.reference())
    geometry, _, text = scene(env)
    name = asset.filename
    assert f'image_map {{ png "{name}" gamma srgb once interpolate 2 }}' in text
    assert "no_shadow no_reflection" in text and "light_group" in text
    assert "seen only in reflections" in text  # reflections see the mean colour
    assert 'picture "corner hole.png" (40 x 30 px), fill' in text
    # Transparent output leaves the picture out but keeps its record.
    _, _, transparent = scene(replace(env, transparent=True))
    assert "image_map" not in transparent and "kept, not drawn" in transparent
    # Other modes keep the picture without drawing it; no picture: plain colour.
    for other in (replace(env, background_mode="solid"), replace(env, image=None)):
        _, _, text = scene(other)
        assert "image_map" not in text and "background { color" in text
    # A floor still covers the background (not removed silently).
    _, _, with_floor = scene(replace(env, floor=True))
    assert "image_map" in with_floor and "// Floor:" in with_floor
    # The picture never enters bounds or geometry.
    assert build_geometry(perovskite_srtio3()).bounding_sphere()[1] == pytest.approx(
        geometry.bounding_sphere()[1]
    )


def test_scene_files_stage_the_picture(pictures, tmp_path):
    asset = import_image(pictures["jpeg"])
    env = Environment(background_mode="image", image=asset.reference())
    geometry, camera, _ = scene(env)
    out = tmp_path / "export folder é"
    out.mkdir()
    pov, ini, _ = write_scene_files(out, "fig 1", geometry, camera, env, RenderSettings(300, 200))
    staged = out / asset.filename
    assert staged.read_bytes() == asset.data and asset.filename.endswith(".jpg")
    assert f'jpeg "{asset.filename}"' in pov.read_text()
    transparent = tmp_path / "t"
    transparent.mkdir()
    write_scene_files(
        transparent, "t", geometry, camera, replace(env, transparent=True), RenderSettings(30, 20)
    )
    assert not list(transparent.glob("bg_*"))


# ----- packages -------------------------------------------------------------------------------
def forget_images():
    images._REGISTRY.clear()


def test_project_package_round_trip_without_the_source(pictures, tmp_path):
    asset = import_image(pictures["png"])
    env = Environment(
        background_mode="image",
        background=MAGENTA,
        image=asset.reference(fit="fit", zoom=1.5, offset_x=0.1, offset_y=-0.2, brightness=0.8),
    )
    project = Project(perovskite_srtio3(), environment=env)
    path = save_project(tmp_path / "Ä project folder" / "figure 1.ycrystal", project)
    assert is_package(path)
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        document = json.loads(archive.read("project.json"))
    assert names == ["project.json", f"assets/{asset.id}.png"]
    assert document["schema_version"] == SCHEMA_VERSION and document["assets"][0]["id"] == asset.id
    pictures["png"].unlink()  # the original picture is gone
    forget_images()  # a fresh session
    again = load_project(path)
    assert again.environment == env and again.structure.composition() == "SrTiO3"
    assert images.get_image(asset.id).data == asset.data
    # Without a picture the project stays plain JSON; old JSON projects still load.
    plain = save_project(tmp_path / "plain.ycrystal", Project(perovskite_srtio3()))
    assert not is_package(plain)
    assert json.loads(plain.read_text())["schema_version"] == SCHEMA_VERSION
    for example in Path("examples").glob("*.ycrystal"):
        assert load_project(example).environment.image is None


def broken_package(tmp_path, asset, edit):
    path = tmp_path / "broken.ycrystal"
    env = Environment(background_mode="image", image=asset.reference())
    save_project(path, Project(perovskite_srtio3(), environment=env))
    with zipfile.ZipFile(path) as archive:
        entries = {name: archive.read(name) for name in archive.namelist()}
    entries = edit(entries)
    with zipfile.ZipFile(path, "w") as archive:
        for name, data in entries.items():
            archive.writestr(name, data)
    return path


def test_damaged_and_unsafe_packages_fail_clearly(pictures, tmp_path):
    asset = import_image(pictures["png"])
    picture = f"assets/{asset.id}.png"

    def drop(entries):
        del entries[picture]
        return entries

    def tamper(entries):
        entries[picture] = entries[picture][:-10] + b"0123456789"
        return entries

    def unsafe(entries):
        entries["../evil.txt"] = b"x"
        return entries

    for edit, message in (
        (drop, "missing from the package"),
        (tamper, "damaged"),
        (unsafe, "unsafe entry name"),
    ):
        with pytest.raises(ProjectError, match=message):
            load_project(broken_package(tmp_path, asset, edit))
    (tmp_path / "zip.ycrystal").write_bytes(b"PK\x03\x04garbage")
    with pytest.raises(ProjectError, match="damaged"):
        load_project(tmp_path / "zip.ycrystal")
    # A plain JSON project that names a picture cannot open without it.
    data = json.loads(
        save_project(tmp_path / "p.ycrystal", Project(perovskite_srtio3())).read_text()
    )
    data["environment"]["background"]["image"] = {
        "asset": asset.id,
        "name": "x.png",
        "width": 40,
        "height": 30,
    }
    (tmp_path / "p.ycrystal").write_text(json.dumps(data))
    with pytest.raises(ProjectError, match="missing from the file"):
        load_project(tmp_path / "p.ycrystal")


def test_environment_style_carries_its_picture(pictures, tmp_path):
    asset = import_image(pictures["jpeg"])
    env = Environment(background_mode="image", image=asset.reference(zoom=2.0))
    style = Style.from_state(perovskite_srtio3(), SceneSettings(), env, (800, 600))
    path = save_style(tmp_path / "with picture.ycstyle", style)
    assert is_package(path)
    pictures["jpeg"].unlink()
    forget_images()
    again = load_style(path)
    assert again.environment == env and images.get_image(asset.id).format == "jpeg"
    plain = save_style(tmp_path / "plain.ycstyle", replace(style, environment=Environment()))
    assert not is_package(plain) and json.loads(plain.read_text())["schema_version"] == 2
    data = json.loads(plain.read_text())
    data["schema_version"] = 1  # a 0.1/0.2 style
    (tmp_path / "old.ycstyle").write_text(json.dumps(data))
    assert load_style(tmp_path / "old.ycstyle").environment == Environment()
    (tmp_path / "bad.ycstyle").write_bytes(b"PK\x03\x04garbage")
    with pytest.raises(StyleError, match="damaged"):
        load_style(tmp_path / "bad.ycstyle")


# ----- real POV-Ray renders -------------------------------------------------------------------
def tiny_scene():
    """One small atom at the origin; a fixed camera with a 10 Å high frame."""
    structure = Structure(
        cell=np.zeros((3, 3)), positions=np.zeros((1, 3)), numbers=[1], labels=["H"],
        pbc=(False, False, False),
    )  # fmt: skip
    geometry = build_geometry(structure, SceneSettings(radius_scale=0.3))
    camera = Camera((0, 0, 20), (0, 0, 0), (0, 1, 0), parallel_scale=5.0)
    return geometry, camera


def render(environment, size, povray_executable, geometry=None, camera=None):
    if geometry is None:
        geometry, camera = tiny_scene()
    job = prepare_job(geometry, camera, environment, RenderSettings(*size, antialias=False))
    try:
        result = run_job(job, povray_executable, timeout=120)
        assert result.ok, result.message
        return np.asarray(Image.open(result.image_path).convert("RGB"), dtype=int)
    finally:
        job.cleanup()


def close(pixel, color, tol=14):
    return bool(np.all(np.abs(np.asarray(pixel) - np.asarray(color)) <= tol))


@pytest.mark.povray
def test_rendered_framing_orientation_and_alpha(pictures, povray_executable):
    png = import_image(pictures["png"])
    base = Environment(background_mode="image", background=MAGENTA)
    # Fit: a 4:3 picture in a 3:2 frame spans 266.7 of 300 px; margins in the colour.
    fit = render(replace(base, image=png.reference(fit="fit")), (300, 200), povray_executable)
    assert close(fit[100, 5], (255, 0, 255)) and close(fit[100, 294], (255, 0, 255))
    assert close(fit[5, 25], RED) and close(fit[5, 274], GREEN)
    assert close(fit[194, 25], BLUE) and close(fit[194, 274], YELLOW)
    assert close(fit[100, 162], (255, 0, 255))  # the transparent hole shows the colour
    columns = [x for x in range(300) if not close(fit[30, x], (255, 0, 255))]
    assert abs(columns[0] - 16.7) <= 1 and abs(columns[-1] + 1 - 283.3) <= 1
    # Fill: same picture covers the frame and is cropped at top and bottom.
    fill = render(replace(base, image=png.reference()), (300, 200), povray_executable)
    assert close(fill[2, 2], RED) and close(fill[197, 297], YELLOW)
    # Zoom 0.5 with offsets: the picture's centre moves by fractions of the frame.
    moved = render(
        replace(base, image=png.reference(fit="fit", zoom=0.5, offset_x=0.25, offset_y=0.25)),
        (300, 200),
        povray_executable,
    )
    rows = [y for y in range(200) if not close(moved[y, 200], (255, 0, 255))]
    cols = [x for x in range(300) if not close(moved[60, x], (255, 0, 255))]
    assert abs(np.mean([rows[0], rows[-1]]) - 50) <= 1.5  # 100 - 0.25 * 200
    assert abs(np.mean([cols[0], cols[-1]]) - 225) <= 1.5  # 150 + 0.25 * 300
    assert abs((cols[-1] - cols[0] + 1) - 133.3) <= 2  # half of 266.7 px wide
    # Brightness 0.5 halves the linear light of the picture.
    dim = render(
        replace(base, image=png.reference(fit="fit", brightness=0.5)), (300, 200), povray_executable
    )
    linear = (np.array(RED) / 255) ** 2.2 * 0.5
    assert close(dim[5, 25], (linear ** (1 / 2.2)) * 255, tol=10)


@pytest.mark.povray
def test_rendered_sources_outputs_and_resolutions(pictures, povray_executable):
    base = Environment(background_mode="image", background=MAGENTA)
    exif = import_image(pictures["exif"])  # EXIF orientation applied: upright
    out = render(replace(base, image=exif.reference(fit="fit")), (300, 200), povray_executable)
    assert close(out[5, 25], RED, 16) and close(out[194, 274], YELLOW, 16)
    jpeg = import_image(pictures["jpeg"])
    out = render(replace(base, image=jpeg.reference(fit="fit")), (300, 200), povray_executable)
    assert close(out[5, 25], RED, 16)
    portrait = import_image(pictures["portrait"])
    for size in ((300, 200), (200, 200), (200, 300)):
        out = render(replace(base, image=portrait.reference(fit="fit")), size, povray_executable)
        w, h = size
        cols = [x for x in range(w) if not close(out[h // 3, x], (255, 0, 255))]
        rows = [y for y in range(h) if not close(out[y, w // 3], (255, 0, 255))]
        width, height = cols[-1] - cols[0] + 1, rows[-1] - rows[0] + 1
        assert width / height == pytest.approx(30 / 40, abs=0.03)  # never distorted
    square = import_image(pictures["square"])
    out = render(replace(base, image=square.reference()), (200, 300), povray_executable)
    assert close(out[2, 2], RED) and close(out[297, 197], YELLOW)  # fill, cropped sides
    # Preview and final sizes show the same composition (edges at the same fractions).
    env = replace(base, image=import_image(pictures["png"]).reference(fit="fit", zoom=0.8))
    edges = []
    for size in ((150, 100), (600, 400)):
        out = render(env, size, povray_executable)
        cols = [x for x in range(size[0]) if not close(out[size[1] // 4, x], (255, 0, 255))]
        edges.append((cols[0] / size[0], (cols[-1] + 1) / size[0]))
    assert edges[0] == pytest.approx(edges[1], abs=1.5 / 150)


@pytest.mark.povray
def test_glass_shows_the_picture_and_project_renders_after_relocation(
    pictures, povray_executable, tmp_path
):
    png = import_image(pictures["png"])
    env = Environment(background_mode="image", background=MAGENTA, image=png.reference())
    structure = Structure(
        cell=np.zeros((3, 3)), positions=np.zeros((1, 3)), numbers=[26], labels=["Fe"],
        pbc=(False, False, False),
    )  # fmt: skip
    geometry = build_geometry(structure, SceneSettings(radius_scale=2.0, material="glass"))
    camera = Camera((0, 0, 20), (0, 0, 0), (0, 1, 0), parallel_scale=5.0)
    out = render(env, (300, 200), povray_executable, geometry, camera)
    centre = out[100, 150]
    assert centre[0] + centre[1] + centre[2] > 120 and not close(centre, (255, 255, 255), 20)
    # Export, move the whole folder, render there.
    folder = tmp_path / "export"
    folder.mkdir()
    write_scene_files(folder, "scene", *tiny_scene(), env, RenderSettings(120, 80, antialias=False))
    moved = shutil.move(str(folder), str(tmp_path / "moved elsewhere"))
    import subprocess

    run = subprocess.run(
        [povray_executable, "scene.ini"], cwd=moved, capture_output=True, text=True, timeout=120
    )
    assert run.returncode == 0, run.stderr[-500:]
    image = np.asarray(Image.open(Path(moved) / "scene.png").convert("RGB"), dtype=int)
    assert close(image[2, 2], RED) and close(image[77, 117], YELLOW)
