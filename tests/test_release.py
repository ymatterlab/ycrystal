"""M6 release checks: command line, desktop launcher, examples, end-to-end workflow."""

import json
import os
import shutil
import subprocess
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
