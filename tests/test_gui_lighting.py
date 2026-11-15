"""FR-LIGHT-01 in the window: live lights, the Lighting Setup overview, handle drags."""

from dataclasses import replace

import numpy as np
import pytest
from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from ycrystal.core.lighting import KEY_ELEVATION_RANGE, resolve_lighting
from ycrystal.core.samples import perovskite_srtio3
from ycrystal.gui.main_window import MainWindow
from ycrystal.io.project import Project, load_project, project_to_dict
from ycrystal.presets import apply_lighting
from ycrystal.render.pov_writer import scene_to_pov

pytestmark = pytest.mark.gui


@pytest.fixture
def window(qtbot):
    win = MainWindow(project=Project(perovskite_srtio3()))
    qtbot.addWidget(win)
    win.resize(1100, 720)
    win.show()
    qtbot.waitExposed(win)
    qtbot.waitUntil(lambda: win._saved_camera is not None, timeout=5000)
    win.preview_panel.auto_check.setChecked(False)
    yield win
    win.close()


@pytest.fixture
def setup(window, qtbot):
    window.set_lighting("dramatic")
    win = window.open_lighting_setup()
    qtbot.waitExposed(win)
    qtbot.waitUntil(lambda: win.overview.rig() is not None, timeout=5000)
    win.overview.render()
    return win


def _mouse(widget, kind, pixel, buttons, button=Qt.MouseButton.LeftButton):
    ratio = widget.devicePixelRatioF()
    point = QPointF(pixel[0] / ratio, pixel[1] / ratio)
    QApplication.sendEvent(
        widget,
        QMouseEvent(
            kind, point, widget.mapToGlobal(point), button, buttons, Qt.KeyboardModifier.NoModifier
        ),
    )


def press_and_move(widget, start, end, steps=6):
    left = Qt.MouseButton.LeftButton
    _mouse(widget, QEvent.Type.MouseButtonPress, start, left)
    for t in np.linspace(0, 1, steps + 1)[1:]:
        point = np.asarray(start) + t * (np.asarray(end) - np.asarray(start))
        _mouse(widget, QEvent.Type.MouseMove, point, left, Qt.MouseButton.NoButton)


def release(widget, pixel):
    _mouse(widget, QEvent.Type.MouseButtonRelease, pixel, Qt.MouseButton.NoButton)


def live_lights(window):
    lights = window.viewport._lights
    return {
        role: (np.array(light.GetPosition()), light.GetIntensity(), light.GetSwitch())
        for role, light in lights.items()
    }


def expected_rig(window, environment=None):
    return resolve_lighting(
        environment or window.environment, window.current_camera(), window.geometry
    )


def light_lines(window):
    text = scene_to_pov(
        window.geometry,
        window.current_camera(),
        window.environment,
        window.current_render_settings(),
    )
    return [line for line in text.splitlines() if line.startswith(("light_source", "disc"))]


# ----- C: the main view's lights ----------------------------------------------------------
def test_main_view_uses_the_resolved_rig_instead_of_the_light_kit(window):
    renderer = window.viewport._plotter.renderer
    window.viewport.render()
    assert renderer.GetLights().GetNumberOfItems() == 2 and not renderer.GetAutomaticLightCreation()
    for light in window.viewport._lights.values():
        assert light.LightTypeIsSceneLight() and light.GetPositional()
        assert light.GetConeAngle() >= 90 and light.GetAttenuationValues() == (1.0, 0.0, 0.0)
    rig = expected_rig(window)
    lights = live_lights(window)
    np.testing.assert_allclose(lights["key"][0], rig.key.position, atol=1e-9)
    np.testing.assert_allclose(lights["fill"][0], rig.fill.position, atol=1e-9)
    assert lights["key"][1:] == (pytest.approx(1.0), 1) and lights["fill"][1:] == (
        pytest.approx(0.35),
        1,
    )


def test_main_view_lights_follow_camera_geometry_and_settings(window):
    camera = window.current_camera().orbit(azimuth=50, elevation=-25).roll(20).pan(0.8, 0.3)
    window.viewport.set_output_camera(camera)
    np.testing.assert_allclose(
        live_lights(window)["key"][0], expected_rig(window).key.position, atol=1e-9
    )
    window.set_repetitions((2, 2, 2))
    window.viewport.render()
    rig = expected_rig(window)
    np.testing.assert_allclose(live_lights(window)["key"][0], rig.key.position, atol=1e-9)
    window.set_environment(replace(window.environment, key_light=0.0, fill_light=1.4), "test")
    lights = live_lights(window)
    assert lights["key"][2] == 0 and lights["fill"][1:] == (pytest.approx(1.4), 1)
    window.set_lighting("dramatic")
    np.testing.assert_allclose(
        live_lights(window)["key"][0], expected_rig(window).key.position, atol=1e-9
    )
    assert window.viewport.lighting_rig().key.intensity == pytest.approx(1.3)


# ----- B: the overview -------------------------------------------------------------------------
def test_lighting_setup_opens_and_shows_the_rig(window, setup):
    panel = window.appearance_panel
    assert panel.lighting_setup_button.text() == "Lighting Setup…"
    assert window.lighting_setup_action.text() == "Lighting Setup…"
    rig = setup.overview.rig()
    np.testing.assert_allclose(rig.key.position, expected_rig(window).key.position, atol=1e-9)
    assert setup.azimuth_spin.value() == -65 and setup.elevation_spin.value() == 25
    assert "point light" in setup.main_label.text() and "1.30" in setup.main_label.text()
    assert "fixed" in setup.fill_label.text() and "D = " in setup.scale_label.text()
    assert setup.azimuth_spin.accessibleName() and setup.azimuth_spin.toolTip()
    assert set(setup.overview.handle_positions()) == {"key", "azimuth"}
    window.set_environment(replace(window.environment, light_size=0.5, reflector=True), "test")
    setup_rig = setup.overview.rig()
    assert setup_rig.key.is_area and setup_rig.panel is not None
    assert "diameter" in setup.main_label.text() and "panel on" in setup.scale_label.text()
    assert setup.overview._labels["area"].GetVisibility()
    assert setup.overview._labels["panel"].GetVisibility()


def test_overview_navigation_changes_nothing_else(window, setup, qtbot):
    camera, env, revision = window.current_camera(), window.environment, window.scene_revision
    lines, props = light_lines(window), window.viewport._plotter.renderer.GetViewProps()
    count = props.GetNumberOfItems()
    overview = setup.overview
    before = overview.overview_camera()
    widget = overview.interactor_widget
    corner = (20.0, 20.0)  # empty space, no handle
    assert overview.handle_at(corner) is None
    press_and_move(widget, corner, (140.0, 90.0))
    release(widget, (140.0, 90.0))
    qtbot.wait(50)
    assert not np.allclose(overview.overview_camera().position, before.position)  # it orbited
    assert window.current_camera() == camera and window.environment == env
    assert window.scene_revision == revision
    assert light_lines(window) == lines  # exports unchanged
    assert window.viewport._plotter.renderer.GetViewProps().GetNumberOfItems() == count
    overview.reset_view()  # back to the fitted overview, still without side effects
    np.testing.assert_allclose(overview.overview_camera().position, before.position, atol=1e-6)
    assert window.current_camera() == camera and window.scene_revision == revision


def test_helper_graphics_stay_out_of_exports_bounds_and_picking(window, setup):
    geometry = window.geometry
    bounds = geometry.bounding_sphere()
    pick = (
        window.viewport.pick((5.0, 5.0)),
        window.viewport.pick(tuple(np.array(window.viewport.render_size()) / 2)),
    )
    window.reset_view()
    fitted = window.current_camera()
    text = scene_to_pov(geometry, fitted, window.environment, window.current_render_settings())
    assert "Lighting setup" not in text and text.count("light_source") == 2
    assert window.geometry is geometry  # the overview never changes the displayed geometry
    np.testing.assert_array_equal(window.geometry.bounding_sphere()[0], bounds[0])
    window.reset_view()
    assert window.current_camera() == fitted  # Fit ignores the overview
    assert (
        window.viewport.pick((5.0, 5.0)),
        window.viewport.pick(tuple(np.array(window.viewport.render_size()) / 2)),
    ) == pick
    assert setup.overview._plotter.renderer is not window.viewport._plotter.renderer


def test_overview_follows_the_output_camera_but_keeps_its_own(window, setup, qtbot):
    overview = setup.overview
    own = overview.overview_camera()
    window.viewport.set_output_camera(window.current_camera().orbit(azimuth=60, elevation=10))
    expected = expected_rig(window).key.position
    qtbot.waitUntil(lambda: np.allclose(overview.rig().key.position, expected), timeout=2000)
    assert overview.overview_camera() == own  # the overview's camera did not move
    width, height = window.output_size()
    window.set_output_size(width, height // 2)  # a new frame shape is shown at once
    w, h = window.current_camera().visible_size(*window.output_size())
    frame = np.array(overview._actors["frame"].GetMapper().GetInput().GetPoints().GetData())
    assert np.linalg.norm(frame[1] - frame[0]) == pytest.approx(w)
    assert np.linalg.norm(frame[2] - frame[1]) == pytest.approx(h)


# ----- numeric and preset synchronisation -------------------------------------------------------
def test_numeric_edits_and_presets_update_the_overview(window, setup):
    panel = window.appearance_panel
    panel.azimuth_spin.setValue(-40)
    panel.elevation_spin.setValue(50)
    assert setup.overview.rig().azimuth == -40 and setup.elevation_spin.value() == 50
    steps = window.undo_stack.count()
    for value in (10, 20, 30):  # stepping the setup's own spin box merges like the panel
        setup.azimuth_spin.setValue(value)
    assert window.environment.key_azimuth == 30 and panel.azimuth_spin.value() == 30
    assert window.undo_stack.count() == steps + 1
    window.set_lighting("top")
    assert setup.overview.rig().elevation == 70 and setup.elevation_spin.value() == 70
    assert setup.overview.rig().key.is_area


# ----- drags ------------------------------------------------------------------------------------
def test_key_drag_previews_then_commits_one_step(window, setup, qtbot):
    overview, widget = setup.overview, setup.overview.interactor_widget
    window.preview_panel.auto_check.setChecked(True)
    window._preview_timer.stop()
    start_env, steps, revision = (
        window.environment,
        window.undo_stack.count(),
        window.scene_revision,
    )
    seen = []
    overview.key_drag_changed.connect(lambda az, el: seen.append((az, el)))
    handle = overview.handle_positions()["key"]
    target = handle + np.array([90.0, 50.0])
    press_and_move(widget, handle, target)
    assert seen and overview.is_dragging()
    az, el = seen[-1]
    assert window.environment == start_env and window.undo_stack.count() == steps  # preview only
    assert window.scene_revision == revision and not window._preview_timer.isActive()
    preview = expected_rig(window, replace(start_env, key_azimuth=az, key_elevation=el))
    np.testing.assert_allclose(live_lights(window)["key"][0], preview.key.position, atol=1e-9)
    assert window.appearance_panel.azimuth_spin.value() == az and setup.azimuth_spin.value() == az
    assert overview.rig().azimuth == az
    release(widget, target)
    assert not overview.is_dragging()
    assert (window.environment.key_azimuth, window.environment.key_elevation) == seen[-1]
    assert window.undo_stack.count() == steps + 1 and window.scene_revision == revision + 1
    assert window._preview_timer.isActive()  # the final POV preview, debounced as usual
    window.preview_panel.auto_check.setChecked(False)
    window.undo_stack.undo()
    assert window.environment == start_env
    assert setup.azimuth_spin.value() == -65 and overview.rig().azimuth == -65


@pytest.mark.parametrize("how", ["escape", "window", "right"])
def test_cancelled_drag_restores_everything(window, setup, how):
    overview, widget = setup.overview, setup.overview.interactor_widget
    start_env, steps, revision = (
        window.environment,
        window.undo_stack.count(),
        window.scene_revision,
    )
    before = live_lights(window)["key"][0]
    handle = overview.handle_positions()["key"]
    press_and_move(widget, handle, handle + np.array([-80.0, 60.0]))
    assert overview.is_dragging() and window.appearance_panel.azimuth_spin.value() != -65
    if how == "escape":
        QTest.keyClick(widget, Qt.Key.Key_Escape)
    elif how == "window":
        window.clear_selection()  # Edit ▸ Select None (Esc in the main window)
    else:
        _mouse(
            widget,
            QEvent.Type.MouseButtonPress,
            handle,
            Qt.MouseButton.RightButton,
            Qt.MouseButton.RightButton,
        )
    assert not overview.is_dragging()
    assert window.environment == start_env and window.undo_stack.count() == steps
    assert window.scene_revision == revision
    np.testing.assert_allclose(live_lights(window)["key"][0], before, atol=1e-9)
    assert window.appearance_panel.azimuth_spin.value() == -65
    assert setup.azimuth_spin.value() == -65 and overview.rig().azimuth == -65
    release(widget, handle)  # a stray release after cancelling changes nothing
    assert window.undo_stack.count() == steps


def test_drag_respects_limits_and_the_output_basis(window, setup):
    overview = setup.overview
    rig = overview.rig()
    # Drag far above the structure: elevation stops at the limit, azimuth stays defined.
    overview.begin_drag("key")
    top = overview._project(rig.origin + 3.0 * rig.distance * rig.up)
    overview.drag_to(top)
    overview.end_drag()
    az, el = window.environment.key_azimuth, window.environment.key_elevation
    assert KEY_ELEVATION_RANGE[0] <= el <= KEY_ELEVATION_RANGE[1] and -180 <= az < 180
    assert el >= 60
    # The azimuth handle changes only the azimuth, interpreted in the output camera.
    rig = overview.rig()
    overview.begin_drag("azimuth")
    target = rig.origin + rig.distance * rig.horizontal(150.0)
    overview.drag_to(overview._project(target))
    overview.end_drag()
    assert window.environment.key_elevation == el
    assert window.environment.key_azimuth == pytest.approx(150.0, abs=3.0)
    # Orbiting the overview does not change how a drag is interpreted.
    cam = overview.overview_camera()
    overview.set_overview_camera(cam.orbit(azimuth=70, elevation=10))
    rig = overview.rig()
    overview.begin_drag("azimuth")
    overview.drag_to(overview._project(rig.origin + rig.distance * rig.horizontal(-100.0)))
    overview.end_drag()
    assert window.environment.key_azimuth == pytest.approx(-100.0, abs=3.0)


def test_unchanged_drag_adds_no_step(window, setup):
    overview = setup.overview
    steps = window.undo_stack.count()
    overview.begin_drag("key")
    overview.end_drag()
    assert window.undo_stack.count() == steps


# ----- presets and projects ---------------------------------------------------------------------
def test_projects_and_presets_keep_their_lighting(window, setup, qtbot, tmp_path):
    overview = setup.overview
    rig = overview.rig()
    overview.begin_drag("azimuth")
    overview.drag_to(overview._project(rig.origin + rig.distance * rig.horizontal(-120.0)))
    overview.end_drag()
    env = window.environment
    assert window.save_as(tmp_path / "lit.ycrystal")
    data = project_to_dict(load_project(tmp_path / "lit.ycrystal"))
    assert set(data["environment"]["lighting"]) == {  # no resolved positions are stored
        "preset",
        "key_light",
        "fill_light",
        "key_azimuth",
        "key_elevation",
        "light_size",
        "shadows",
        "reflector",
    }
    reopened = load_project(tmp_path / "lit.ycrystal")
    assert reopened.environment == env  # only the existing fields are stored
    assert apply_lighting(env, "soft").key_azimuth == -29  # presets unchanged
