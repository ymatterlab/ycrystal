"""Optional user text in projects, the GUI panel, and windowless renders."""

from dataclasses import replace

import numpy as np
from PIL import Image, ImageChops
from PySide6.QtCore import Qt

from conftest import fake_povray
from ycrystal.app import main
from ycrystal.core.annotation import TextAnnotation
from ycrystal.core.legend import LegendSettings
from ycrystal.core.samples import perovskite_srtio3
from ycrystal.core.scene import SceneSettings
from ycrystal.gui.panels.annotation_panel import AnnotationPanel
from ycrystal.io.project import Project, load_project, save_project
from ycrystal.render.annotation import annotation_overlay, annotation_paths
from ycrystal.render.pov_writer import RenderSettings


def test_frame_text_scales_with_the_output_and_can_be_hidden(qapp):
    label = TextAnnotation("SrTiO₃\nCubic perovskite", x=0.9, y=0.07, alignment="right")
    bounds = annotation_paths((label,), 400, 300)[0][0].boundingRect()
    enlarged = annotation_paths((label,), 800, 600)[0][0].boundingRect()
    np.testing.assert_allclose(enlarged.getRect(), np.asarray(bounds.getRect()) * 2)
    assert bounds.right() <= 0.9 * 400 + 1
    assert annotation_overlay((replace(label, enabled=False),), 400, 300) is None
    assert annotation_overlay((replace(label, y=1.0),), 400, 300) is None


def test_project_replay_draws_text_and_legend_into_the_png(qapp, tmp_path):
    label = TextAnnotation("SrTiO₃", x=0.1, y=0.08, font_size=10, color=(1.0, 0.8, 0.2))
    hidden = replace(label, text="Hidden", y=0.35, enabled=False)
    scene = SceneSettings(annotations=(label, hidden), legend=LegendSettings(enabled=True))
    project = Project(perovskite_srtio3(), scene, output=RenderSettings(400, 300))
    path = save_project(tmp_path / "annotation.ycrystal", project)
    replay = load_project(path)
    assert replay.scene == scene
    plain_path = save_project(
        tmp_path / "plain.ycrystal",
        replace(project, scene=replace(scene, annotations=())),
    )
    executable = fake_povray(tmp_path)
    a, b = tmp_path / "text.png", tmp_path / "plain.png"
    assert main([str(path), "--povray", executable, "--render", str(a)]) == 0
    assert main([str(plain_path), "--povray", executable, "--render", str(b)]) == 0
    with Image.open(a) as first, Image.open(b) as second:
        difference = ImageChops.difference(first.convert("RGB"), second.convert("RGB"))
        left, top, right, bottom = difference.getbbox()
        assert 35 < left < right < 200 and 20 < top < bottom < 80


def test_figure_text_ui_can_toggle_and_remove_a_label(qtbot):
    panel = AnnotationPanel()
    qtbot.addWidget(panel)
    label = TextAnnotation("Caption")
    panel.sync((label,))
    with qtbot.waitSignal(panel.annotations_requested) as request:
        panel.annotation_list.item(0).setCheckState(Qt.CheckState.Unchecked)
    assert request.args == [(replace(label, enabled=False),), "Hide Text"]
    with qtbot.waitSignal(panel.annotations_requested) as request:
        panel.remove_button.click()
    assert request.args == [(), "Remove Text"]
