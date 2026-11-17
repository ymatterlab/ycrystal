"""M6 release checks: command line, desktop launcher, examples, end-to-end workflow."""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from ycrystal.app import main
from ycrystal.batch import export_scene, load_input, render_png
from ycrystal.desktop import desktop_entry, install_desktop, uninstall_desktop
from ycrystal.io.project import load_project
from ycrystal.io.style import apply_style, load_style
from ycrystal.render.imagecheck import load_rgba

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"
EXAMPLES = sorted((ROOT / "examples").glob("*.ycrystal"))


# ----- command line (no display) ------------------------------------------------------
def test_export_pov_from_structure_and_project(tmp_path, capsys):
    assert main([str(FIXTURES / "MgB2.cif"), "--export-pov", str(tmp_path / "a" / "MgB2")]) == 1
    (tmp_path / "a").mkdir()
    assert main([str(FIXTURES / "MgB2.cif"), "--export-pov", str(tmp_path / "a" / "MgB2")]) == 0
    assert (tmp_path / "a" / "MgB2.pov").is_file() and (tmp_path / "a" / "MgB2.ini").is_file()
    example = ROOT / "examples" / "SrTiO3-studio.ycrystal"
    code = main([str(example), "--export-pov", str(tmp_path / "s.pov"), "--width", "320"])
    assert code == 0
    ini = (tmp_path / "s.ini").read_text()
    assert "Width=320" in ini and "Height=600" in ini
    assert "// Floor:" in (tmp_path / "s.pov").read_text()  # the project's studio
    assert "Exported" in capsys.readouterr().out


def test_command_line_errors(tmp_path, capsys):
    bad = main([str(FIXTURES / "qe_ibrav2.pw.in"), "--export-pov", str(tmp_path / "x.pov")])
    assert bad == 1 and "ibrav" in capsys.readouterr().err
    assert main([str(FIXTURES / "MgB2.cif"), "--render", "x.png", "--width", "5"]) == 2
    with pytest.raises(SystemExit) as exit_info:
        main(["--render", str(tmp_path / "x.png")])  # no FILE
    assert exit_info.value.code == 2


@pytest.mark.povray
def test_render_from_command_line(tmp_path, capsys, povray_executable):
    out = tmp_path / "MgB2.png"
    args = [str(FIXTURES / "MgB2.cif"), "--render", str(out), "--width", "200"]
    assert main([*args, "--height", "150", "--povray", povray_executable]) == 0
    assert load_rgba(out).shape == (150, 200, 4)
    assert "Rendered" in capsys.readouterr().out


# ----- styles from the command line (FR-STYLE-CLI-01) ----------------------------------
STYLE = ROOT / "examples" / "grey-studio.ycstyle"
MGB2 = FIXTURES / "MgB2.cif"


def ini_size(path: Path) -> tuple[int, int]:
    lines = dict(line.split("=", 1) for line in path.read_text().splitlines() if "=" in line)
    return int(lines["Width"]), int(lines["Height"])


def test_style_from_command_line(tmp_path, capsys):
    folder = tmp_path / "Stile ü"  # spaces and non-ASCII in every path
    folder.mkdir()
    style = shutil.copy(STYLE, folder / "grey studio.ycstyle")
    source = shutil.copy(MGB2, folder / "Mg B2.cif")
    before = (Path(style).read_bytes(), Path(source).read_bytes())
    out = folder / "out ü"
    out.mkdir()
    code = main([str(source), "--style", str(style), "--export-pov", str(out / "Mg B2")])
    assert code == 0
    captured = capsys.readouterr()
    assert "Exported" in captured.out
    # What the style could not apply is a warning on stderr, not an error.
    assert "WARNING: Element overrides for O, Ti were not applied" in captured.err
    assert "ERROR" not in captured.err
    assert ini_size(out / "Mg B2.ini") == (800, 600)  # the style's output size
    pov = (out / "Mg B2.pov").read_text(encoding="utf-8")
    assert "// Floor:" in pov  # the style's grey studio
    assert (Path(style).read_bytes(), Path(source).read_bytes()) == before  # inputs untouched
    # Without --style nothing changes: the structure's defaults and no warnings.
    assert main([str(source), "--export-pov", str(out / "plain")]) == 0
    assert ini_size(out / "plain.ini") == (1200, 800)
    assert "WARNING" not in capsys.readouterr().err


@pytest.mark.parametrize(
    "extra, size",
    [
        ([], (800, 600)),
        (["--width", "320"], (320, 600)),
        (["--height", "150"], (800, 150)),
        (["--width", "320", "--height", "240"], (320, 240)),
        (["--style-parts", "appearance,environment"], (1200, 800)),  # FILE's size kept
    ],
)
def test_command_line_sizes_override_the_style(tmp_path, extra, size):
    args = [str(MGB2), "--style", str(STYLE), "--export-pov", str(tmp_path / "s"), *extra]
    assert main(args) == 0
    assert ini_size(tmp_path / "s.ini") == size


def test_style_on_a_saved_project_keeps_its_camera_and_vectors(tmp_path, capsys):
    example = ROOT / "examples" / "vectors-synthetic-afm.ycrystal"
    original = example.read_bytes()
    assert main([str(example), "--export-pov", str(tmp_path / "plain")]) == 0
    code = main([str(example), "--style", str(STYLE), "--export-pov", str(tmp_path / "styled")])
    assert code == 0
    plain = (tmp_path / "plain.pov").read_text().splitlines()
    styled = (tmp_path / "styled.pov").read_text().splitlines()
    camera = [line for line in plain if line.lstrip().startswith(("location", "look_at"))]
    assert camera and camera == [
        line for line in styled if line.lstrip().startswith(("location", "look_at"))
    ]
    arrows = [line for line in plain if "mu_B" in line]
    assert arrows and arrows == [line for line in styled if "mu_B" in line]  # same vectors
    assert "// Floor:" in "\n".join(styled) and example.read_bytes() == original
    capsys.readouterr()


def test_style_errors_write_nothing(tmp_path, capsys):
    out = tmp_path / "out"
    out.mkdir()
    damaged = tmp_path / "damaged.ycstyle"
    damaged.write_bytes(b"PK\x03\x04garbage")
    for style in (tmp_path / "missing.ycstyle", damaged):
        code = main([str(MGB2), "--style", str(style), "--export-pov", str(out / "x")])
        assert code == 1 and "ERROR:" in capsys.readouterr().err
    big = json.loads(STYLE.read_text())
    big["scene"]["repetitions"] = [30, 30, 30]
    (tmp_path / "big.ycstyle").write_text(json.dumps(big))
    args = [str(FIXTURES / "SrTiO3.cif"), "--style", str(tmp_path / "big.ycstyle")]
    code = main([*args, "--style-parts", "display", "--export-pov", str(out / "x")])
    assert code == 1 and "limit of 20,000" in capsys.readouterr().err
    code = main([*args, "--render", str(out / "x.png"), "--povray", str(tmp_path / "none")])
    assert code == 1 and "POV-Ray was not found" in capsys.readouterr().err
    assert list(out.iterdir()) == []  # no scene, no image, no partial file


@pytest.mark.parametrize(
    "args",
    [
        [str(MGB2), "--style", str(STYLE)],  # no --render/--export-pov: no window either
        [str(MGB2), "--style-parts", "display", "--export-pov", "x.pov"],  # no --style
        [str(MGB2), "--style", str(STYLE), "--style-parts", "", "--export-pov", "x.pov"],
        [str(MGB2), "--style", str(STYLE), "--style-parts", "camera", "--export-pov", "x"],
    ],
)
def test_style_usage_errors(args, capsys):
    with pytest.raises(SystemExit) as exit_info:
        main(args)
    assert exit_info.value.code == 2 and "--style" in capsys.readouterr().err


def test_style_command_needs_no_window_toolkit(tmp_path):
    script = (
        "import sys; from ycrystal.app import main; "
        f"code = main([{str(MGB2)!r}, '--style', {str(STYLE)!r}, "
        f"'--export-pov', {str(tmp_path / 'x')!r}]); "
        "loaded = sorted(m for m in sys.modules "
        "if m.split('.')[0] in ('PySide6', 'vtk', 'vtkmodules', 'pyvista', 'pyvistaqt')); "
        "print(code, loaded)"
    )
    env = {k: v for k, v in os.environ.items() if k not in ("DISPLAY", "WAYLAND_DISPLAY")}
    result = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True, env=env, timeout=120
    )
    assert result.stdout.split("\n")[-2] == "0 []", result.stdout + result.stderr


@pytest.mark.povray
def test_render_with_style_from_command_line(tmp_path, capsys, povray_executable):
    size = ["--width", "200", "--height", "150", "--povray", povray_executable]
    assert main([str(MGB2), "--render", str(tmp_path / "plain.png"), *size]) == 0
    styled = tmp_path / "Mg B2 ü.png"
    assert main([str(MGB2), "--style", str(STYLE), "--render", str(styled), *size]) == 0
    captured = capsys.readouterr()
    assert "Rendered" in captured.out and "WARNING:" in captured.err
    image, plain = load_rgba(styled), load_rgba(tmp_path / "plain.png")
    assert image.shape == plain.shape == (150, 200, 4)
    assert not np.array_equal(image, plain)  # the grey studio, not the default look
    assert [p.name for p in tmp_path.iterdir() if p.suffix != ".png"] == []


# ----- element mapping from the command line (FR-STYLE-MAP-01) ---------------------------
BAZRO3 = FIXTURES / "BaZrO3.cif"


def atom_texture(pov: Path, label: str) -> str:
    """Return the texture of the first sphere whose comment names ``label``."""
    for line in pov.read_text(encoding="utf-8").splitlines():
        if line.startswith("sphere") and f"// atom {label} " in line:
            return line.split("texture {")[1].split("}")[0].strip()
    raise AssertionError(f"no atom {label}")


def test_element_map_from_command_line(tmp_path, capsys):
    before = BAZRO3.read_bytes(), STYLE.read_bytes()
    args = [str(BAZRO3), "--style", str(STYLE), "--export-pov"]
    assert main([*args, str(tmp_path / "plain")]) == 0
    assert "Element overrides for Ti were not applied" in capsys.readouterr().err
    assert main([*args, str(tmp_path / "mapped"), "--element-map", "Sr=Ba,Ti=Zr"]) == 0
    captured = capsys.readouterr()
    # The style has no Sr settings: the mapping says so instead of failing.
    assert "WARNING: The style has no element settings for Sr" in captured.err
    assert "Element overrides" not in captured.err
    assert atom_texture(tmp_path / "plain.pov", "#2 Zr") != "Ycr_Texture_chrome"
    assert atom_texture(tmp_path / "mapped.pov", "#2 Zr") == "Ycr_Texture_chrome"  # Ti's look
    assert atom_texture(tmp_path / "mapped.pov", "#3 O") == "Ycr_Texture_O_ceramic"  # by symbol
    assert (BAZRO3.read_bytes(), STYLE.read_bytes()) == before  # inputs untouched


def test_bad_element_maps_write_nothing(tmp_path, capsys):
    out = tmp_path / "out"
    out.mkdir()
    base = [str(BAZRO3), "--style", str(STYLE), "--export-pov", str(out / "x")]
    for mapping, message in (
        ("Ti=O", "O would receive the settings of both O and Ti"),
        ("Ti=Mg", "the structure has no Mg"),
    ):
        assert main([*base, "--element-map", mapping]) == 1
        err = capsys.readouterr().err
        assert "ERROR: Element mapping:" in err and message in err
    for mapping in ("Ti", "ti=Zr", "Ti=Zr,Ti=Ba", ""):
        with pytest.raises(SystemExit) as exit_info:
            main([*base, "--element-map", mapping])
        assert exit_info.value.code == 2 and "--element-map" in capsys.readouterr().err
    with pytest.raises(SystemExit) as exit_info:
        main([str(BAZRO3), "--element-map", "Ti=Zr", "--export-pov", str(out / "x")])
    assert exit_info.value.code == 2 and "--element-map needs --style" in capsys.readouterr().err
    assert list(out.iterdir()) == []


@pytest.mark.povray
def test_render_with_element_map(tmp_path, capsys, povray_executable):
    size = ["--width", "160", "--height", "120", "--povray", povray_executable]
    base = [str(BAZRO3), "--style", str(STYLE)]
    assert main([*base, "--render", str(tmp_path / "plain.png"), *size]) == 0
    mapped = tmp_path / "Ba Zr O3 ü.png"
    assert main([*base, "--element-map", "Ti=Zr", "--render", str(mapped), *size]) == 0
    assert "Rendered" in capsys.readouterr().out
    image, plain = load_rgba(mapped), load_rgba(tmp_path / "plain.png")
    assert image.shape == plain.shape == (120, 160, 4)
    assert not np.array_equal(image, plain)  # chrome Zr instead of the default material


# ----- desktop launcher --------------------------------------------------------------------
def test_desktop_launcher_install_and_uninstall(tmp_path):
    files = install_desktop(tmp_path, command="/opt/yc/.venv/bin/ycrystal")
    launcher, icon, mime = files
    assert launcher.name == "ycrystal.desktop" and icon.suffix == ".svg"
    text = launcher.read_text()
    assert 'Exec="/opt/yc/.venv/bin/ycrystal" %f' in text and "Icon=ycrystal" in text
    assert "*.ycrystal" in mime.read_text()
    if shutil.which("desktop-file-validate"):
        result = subprocess.run(
            ["desktop-file-validate", str(launcher)], capture_output=True, text=True
        )
        assert result.returncode == 0, result.stdout + result.stderr
    assert sorted(uninstall_desktop(tmp_path)) == sorted(files)
    assert not any(path.exists() for path in files)
    assert "-m ycrystal.app %f" in desktop_entry("/usr/bin/python3 -m ycrystal.app")


def test_reinstalling_the_icon_bumps_the_theme_folder_time(tmp_path):
    """Desktops notice a replaced icon only through the theme folder's modification time."""
    _, icon, _ = install_desktop(tmp_path, command="/opt/yc/.venv/bin/ycrystal")
    theme = tmp_path / "icons" / "hicolor"
    os.utime(theme, (1_000_000_000, 1_000_000_000))
    icon.write_text("stale")
    install_desktop(tmp_path, command="/opt/yc/.venv/bin/ycrystal")
    assert theme.stat().st_mtime > 1_000_000_000
    assert icon.read_text() != "stale"


# ----- examples --------------------------------------------------------------------------------
def test_examples_are_self_contained():
    assert len(EXAMPLES) >= 3
    for path in EXAMPLES:
        text = path.read_text(encoding="utf-8")
        assert "/home/" not in text and "\\\\" not in text  # no machine paths
        project = load_project(path)
        assert project.camera is not None and len(project.structure) > 0
        source = project.structure.metadata.get("source", {})
        assert not Path(source.get("path", "relative")).is_absolute()
    style = load_style(ROOT / "examples" / "grey-studio.ycstyle")
    target = load_input(FIXTURES / "MgB2.cif")
    result = apply_style(style, target.structure, target.scene, target.environment, (1, 1))
    assert result.environment.preset == "studio_grey"


@pytest.mark.povray
@pytest.mark.parametrize("path", EXAMPLES, ids=[p.stem for p in EXAMPLES])
def test_examples_render(path, tmp_path, povray_executable):
    project = load_input(path)
    result = render_png(project, tmp_path / "out.png", povray_executable, 160, 120)
    assert result.ok, result.message
    rgba = load_rgba(tmp_path / "out.png")
    assert rgba.shape == (120, 160, 4)
    assert rgba[0, 0, 3] == (0 if project.environment.transparent else 255)
    pov, _ = export_scene(project, tmp_path / "scene.pov")
    assert json.loads(path.read_text())["output"]["width"] == project.output.width
    assert pov.is_file()


# ----- the end-to-end workflow of the plan (section 10) -------------------------------------
@pytest.mark.gui
@pytest.mark.povray
def test_release_workflow(qtbot, tmp_path, povray_executable):
    """Open a CIF, rotate/pan, expand 2x2x2, change an element's finish, choose a
    studio, render, save, close, reopen without the source file, render again."""
    from ycrystal.gui.main_window import SETTINGS_POVRAY, MainWindow
    from ycrystal.io.project import Project

    source = tmp_path / "input" / "SrTiO3.cif"
    source.parent.mkdir()
    shutil.copyfile(FIXTURES / "SrTiO3.cif", source)

    def show(window):
        qtbot.addWidget(window)
        window.resize(1000, 720)
        window.show()
        qtbot.waitExposed(window)
        qtbot.waitUntil(lambda: window._saved_camera is not None, timeout=5000)
        window.settings.setValue(SETTINGS_POVRAY, povray_executable)
        window.preview_panel.auto_check.setChecked(False)
        return window

    def render(window, name):
        window.render_finished_result = None
        assert window.render_png(tmp_path / name, show_result=False)
        qtbot.waitUntil(lambda: window.render_finished_result is not None, timeout=120_000)
        assert window.render_finished_result.ok, window.render_finished_result.message
        return load_rgba(tmp_path / name)

    first = show(MainWindow(project=Project(load_input(FIXTURES / "MgB2.cif").structure)))
    assert first.open_file(source)
    original = first.structure.positions.copy()
    camera = first.current_camera().orbit(azimuth=35, elevation=20).pan(0.4, -0.2)
    first.viewport.set_output_camera(camera)
    assert first.set_repetitions((2, 2, 2))
    first.select(
        {
            a
            for a, e in zip(first.geometry.atom_ids, first.geometry.elements, strict=True)
            if e == "Ti"
        }
    )
    first.set_element_material("Ti", "glossy")
    first.set_background("studio_white")
    first.set_output_size(320, 240)
    image = render(first, "first.png")
    assert image.shape == (240, 320, 4)
    project_path = tmp_path / "workflow.ycrystal"
    assert first.save_as(project_path)
    first.close()

    shutil.rmtree(source.parent)  # the source file is gone
    second = show(MainWindow(project=load_project(project_path), project_path=project_path))
    try:
        np.testing.assert_array_equal(second.structure.positions, original)
        assert second.scene_settings.repetitions == (2, 2, 2)
        assert dict(second.scene_settings.element_materials) == {"Ti": "glossy"}
        again = render(second, "second.png")
        assert again.shape == image.shape
        assert np.abs(again.astype(int) - image.astype(int)).max() <= 2  # same figure

        # Other formats of the same structure, and a rejected QE file.
        for name in ("SrTiO3.vasp", "SrTiO3.pw.in"):
            second.ask_save_changes = lambda: "discard"
            assert second.open_file(FIXTURES / name), name
            assert second.structure.composition() == "SrTiO3"
            assert len(second.structure) == 5
        assert not second.open_file(FIXTURES / "qe_ibrav2.pw.in")
        assert "ibrav" in second.last_error[1]
        second._message_box.close()
    finally:
        second.ask_save_changes = lambda: "discard"
        second.close()
