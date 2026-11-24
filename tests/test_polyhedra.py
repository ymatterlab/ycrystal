"""Coordination geometry, project replay, and real POV-Ray rendering."""

from dataclasses import replace
from itertools import product

import numpy as np
import pytest
from PIL import Image
from PySide6.QtCore import Qt

from ycrystal.app import main
from ycrystal.core.bonds import BondSettings
from ycrystal.core.camera import Camera
from ycrystal.core.polyhedra import PolyhedronRule
from ycrystal.core.samples import perovskite_srtio3
from ycrystal.core.scene import SceneSettings, build_geometry
from ycrystal.core.structure import Structure
from ycrystal.gui.panels.polyhedra_panel import PolyhedraPanel
from ycrystal.io.project import Project, load_project, save_project
from ycrystal.render.pov_writer import RenderSettings, scene_to_pov


def test_periodic_srtio3_has_eighteen_octahedra_independent_of_bonds():
    structure = perovskite_srtio3()
    scene = SceneSettings(
        repetitions=(3, 3, 2),
        bonds=BondSettings(enabled=False),
        polyhedron_rules=(PolyhedronRule("Ti", "O", cutoff=1.96),),
    )
    geometry = build_geometry(structure, scene)
    assert not len(geometry.bonds)
    assert len(geometry.polyhedra) == 18
    for shell in geometry.polyhedra:
        assert geometry.elements[shell.centre] == "Ti"
        assert len(shell.triangles) == 8 and len(shell.edges) == 12
        vertices = {row for face in shell.triangles for row in face}
        assert len(vertices) == 6
        for row in vertices:
            assert geometry.elements[row] == "O"
            assert np.isclose(
                np.linalg.norm(geometry.positions[row] - geometry.positions[shell.centre]), 1.9525
            )
        for a, b, c in shell.triangles:
            points = geometry.positions[[a, b, c]]
            normal = np.cross(points[1] - points[0], points[2] - points[0])
            assert np.dot(normal, points.mean(axis=0) - geometry.positions[shell.centre]) > 0
    shared = geometry.atom_ids[geometry.polyhedra[0].triangles[0][0]]
    hidden = build_geometry(structure, replace(scene, hidden=frozenset({shared})))
    assert len(hidden.polyhedra) < 18
    assert not build_geometry(structure, replace(scene, polyhedron_rules=())).polyhedra


def test_coplanar_hull_faces_have_no_diagonal_edges():
    structure = Structure(
        cell=np.zeros((3, 3)),
        positions=[(0, 0, 0), *product((-1.0, 1.0), repeat=3)],
        numbers=[22, *([8] * 8)],
        labels=["Ti", *(["O"] * 8)],
        pbc=(False, False, False),
    )
    scene = SceneSettings(polyhedron_rules=(PolyhedronRule("Ti", "O", cutoff=2),))
    geometry = build_geometry(structure, scene)
    (shell,) = geometry.polyhedra
    assert (len(shell.triangles), len(shell.edges)) == (12, 12)
    assert all(
        np.isclose(np.linalg.norm(geometry.positions[a] - geometry.positions[b]), 2.0)
        for a, b in shell.edges
    )
    flat = Structure(
        cell=structure.cell,
        positions=[(0, 0, 0), *product((-1.0, 1.0), (-1.0, 1.0), (0,))],
        numbers=[22, 8, 8, 8, 8],
        labels=["Ti", "O", "O", "O", "O"],
        pbc=structure.pbc,
    )
    assert not build_geometry(flat, scene).polyhedra


def test_polyhedron_ui_can_disable_a_rule(qtbot):
    panel = PolyhedraPanel()
    qtbot.addWidget(panel)
    rule = PolyhedronRule("Ti", "O")
    panel.sync((rule,), ("Sr", "Ti", "O"), 18)
    assert "18" in panel.summary.text()
    with qtbot.waitSignal(panel.rules_requested) as request:
        panel.rules_list.item(0).setCheckState(Qt.CheckState.Unchecked)
    assert request.args == [(replace(rule, enabled=False),), "Hide Polyhedra"]


@pytest.mark.povray
def test_polyhedra_save_and_render(povray_executable, tmp_path):
    structure = perovskite_srtio3()
    scene = SceneSettings(
        show_cell=False,
        polyhedron_rules=(PolyhedronRule("Ti", "O"),),
        bonds=BondSettings(enabled=False),
    )
    geometry = build_geometry(structure, scene)
    camera = Camera.looking_along((-1, -0.5, -0.8), (0, 0, 1)).fitted(
        *geometry.points_and_radii(), 4 / 3
    )
    project = Project(structure, scene, camera=camera, output=RenderSettings(240, 180))
    path = save_project(tmp_path / "shell.ycrystal", project)
    project = load_project(path)
    assert project.scene == scene
    pov = scene_to_pov(geometry, camera, project.environment, project.output)
    assert "Coordination polyhedra (1)" in pov
    assert pov.count("triangle {") == 8
    assert pov.count("texture { Ycr_Polyhedron_0_Edge } no_shadow") == 12
    output = tmp_path / "shell.png"
    assert main([str(path), "--povray", povray_executable, "--render", str(output)]) == 0
    with Image.open(output) as image:
        assert image.size == (240, 180)
