"""Main application window: sample structure, navigation, selection, POV-Ray output."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import numpy as np
from PySide6.QtCore import QSettings, Qt, QTimer
from PySide6.QtGui import QAction, QKeySequence, QPixmap, QUndoStack
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ycrystal import __version__
from ycrystal.core.camera import Camera, default_camera
from ycrystal.core.scene import (
    AtomId,
    DisplayGeometry,
    Environment,
    SceneSettings,
    build_geometry,
)
from ycrystal.core.structure import Structure
from ycrystal.gui.commands import SceneSettingsCommand
from ycrystal.render.jobs import RenderResult, copy_result, prepare_job
from ycrystal.render.pov_writer import RenderSettings, write_scene_files
from ycrystal.render.povray import PovrayNotFoundError, find_povray, povray_version
from ycrystal.render.process import RenderProcess
from ycrystal.viewport.qt_viewport import StructureViewport

SETTINGS_POVRAY = "render/povray_executable"

MOUSE_HELP = """<table cellspacing="4">
<tr><td><b>Left drag</b></td><td>Orbit around the view centre</td></tr>
<tr><td><b>Middle drag</b> or <b>Shift + left drag</b></td><td>Pan</td></tr>
<tr><td><b>Wheel</b> or <b>right drag</b></td><td>Zoom</td></tr>
<tr><td><b>F</b> / Fit</td><td>Frame the structure (keeps orientation)</td></tr>
<tr><td><b>Click</b> (no drag)</td><td>Select an atom (empty space clears)</td></tr>
<tr><td><b>Ctrl + click</b></td><td>Add or remove an atom from the selection</td></tr>
<tr><td><b>Delete</b></td><td>Hide the selected atoms (view and exports only)</td></tr>
<tr><td><b>Esc</b></td><td>Clear the selection</td></tr>
<tr><td><b>Ctrl + Z</b> / <b>Ctrl + Shift + Z</b></td><td>Undo / redo</td></tr>
</table>
<p>Atoms on cell faces, edges, and corners are drawn at every equivalent boundary
position (View ▸ Show Boundary Atoms). Each drawn ball can be hidden on its own;
View ▸ Show All Atoms brings hidden balls back.</p>
<p>Navigation and hiding change only the presentation, never atomic coordinates.<br>
The live view approximates lighting; Render produces the POV-Ray image of the same
framing. The output image has the viewport's aspect ratio.</p>"""


class RenderResultDialog(QDialog):
    def __init__(self, image: Path, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Rendered image — {image.name}")
        layout = QVBoxLayout(self)
        label = QLabel()
        label.setPixmap(QPixmap(str(image)))
        scroll = QScrollArea()
        scroll.setWidget(label)
        layout.addWidget(scroll)
        layout.addWidget(QLabel(str(image)))
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        screen = QApplication.primaryScreen().availableGeometry()
        pixmap = label.pixmap()
        self.resize(min(pixmap.width() + 60, screen.width() - 80),
                    min(pixmap.height() + 120, screen.height() - 80))


class MainWindow(QMainWindow):
    def __init__(self, structure: Structure, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.structure = structure
        self.scene_settings = SceneSettings()
        self.environment = Environment()
        self.geometry = build_geometry(structure, self.scene_settings)
        self.settings = QSettings()
        self._render: RenderProcess | None = None
        self._render_destination: Path | None = None
        self._result_dialog: RenderResultDialog | None = None
        self._show_result = True
        self._camera_initialised = False
        self.last_error: tuple[str, str] | None = None
        self.last_render_path: Path | None = None
        self.render_finished_result: RenderResult | None = None
        self.selection: set[AtomId] = set()
        self.undo_stack = QUndoStack(self)

        self.setWindowTitle(f"Ycrystal {__version__} — {structure.composition()}")
        self.viewport = StructureViewport(self)
        self.setCentralWidget(self.viewport)
        self._build_actions()
        self._build_status_bar()
        self.set_display_geometry(self.geometry)
        self.viewport.camera_changed.connect(self._update_output_label)
        self.viewport.atom_clicked.connect(self._on_atom_clicked)
        self.viewport.key_pressed.connect(self.trigger_shortcut)

    # ----- construction -------------------------------------------------------------
    def _build_actions(self) -> None:
        self.fit_action = QAction("Fit", self, shortcut=QKeySequence("F"),
                                  toolTip="Frame the structure (F)")
        self.fit_action.triggered.connect(self.viewport.fit)
        self.export_action = QAction("Export POV-Ray…", self,
                                     toolTip="Write editable .pov and .ini files")
        self.export_action.triggered.connect(lambda: self.export_pov())
        self.render_action = QAction("Render PNG…", self, shortcut=QKeySequence("Ctrl+R"),
                                     toolTip="Render the current view with POV-Ray")
        self.render_action.triggered.connect(lambda: self.render_png())
        self.set_povray_action = QAction("Set POV-Ray Executable…", self)
        self.set_povray_action.triggered.connect(self.choose_povray)
        self.check_povray_action = QAction("Check Renderer", self)
        self.check_povray_action.triggered.connect(self.check_renderer)
        help_action = QAction("Mouse Controls", self,
                              shortcut=QKeySequence.StandardKey.HelpContents)
        help_action.triggered.connect(self.show_mouse_help)
        quit_action = QAction("Quit", self, shortcut=QKeySequence.StandardKey.Quit)
        quit_action.triggered.connect(self.close)

        self.undo_action = self.undo_stack.createUndoAction(self, "Undo")
        self.undo_action.setShortcut(QKeySequence.StandardKey.Undo)
        self.redo_action = self.undo_stack.createRedoAction(self, "Redo")
        self.redo_action.setShortcuts([QKeySequence("Ctrl+Shift+Z"), QKeySequence("Ctrl+Y")])
        self.hide_action = QAction(
            "Hide Selected Atoms", self, enabled=False,
            toolTip="Remove the selected balls from the view and exports (Delete). "
                    "The structure is unchanged.",
        )
        self.hide_action.setShortcuts([QKeySequence(Qt.Key.Key_Delete),
                                       QKeySequence(Qt.Key.Key_Backspace)])
        self.hide_action.triggered.connect(self.hide_selected)
        self.select_none_action = QAction("Select None", self,
                                          shortcut=QKeySequence(Qt.Key.Key_Escape))
        self.select_none_action.triggered.connect(self.clear_selection)
        self.show_all_action = QAction("Show All Atoms", self, enabled=False,
                                       toolTip="Bring back every hidden ball")
        self.show_all_action.triggered.connect(self.show_all_atoms)
        self.boundary_action = QAction(
            "Show Boundary Atoms", self, checkable=True, checked=True,
            toolTip="Draw atoms at every equivalent position on cell faces, edges, corners",
        )
        self.boundary_action.triggered.connect(self.set_boundary_images)

        file_menu = self.menuBar().addMenu("&File")
        file_menu.addAction(self.export_action)
        file_menu.addAction(self.render_action)
        file_menu.addSeparator()
        file_menu.addAction(quit_action)
        edit_menu = self.menuBar().addMenu("&Edit")
        edit_menu.addAction(self.undo_action)
        edit_menu.addAction(self.redo_action)
        edit_menu.addSeparator()
        edit_menu.addAction(self.hide_action)
        edit_menu.addAction(self.select_none_action)
        view_menu = self.menuBar().addMenu("&View")
        view_menu.addAction(self.fit_action)
        view_menu.addSeparator()
        view_menu.addAction(self.boundary_action)
        view_menu.addAction(self.show_all_action)
        render_menu = self.menuBar().addMenu("&Render")
        render_menu.addAction(self.render_action)
        render_menu.addAction(self.set_povray_action)
        render_menu.addAction(self.check_povray_action)
        help_menu = self.menuBar().addMenu("&Help")
        help_menu.addAction(help_action)

        toolbar = self.addToolBar("Main")
        toolbar.setObjectName("main_toolbar")
        toolbar.setMovable(False)
        toolbar.addAction(self.fit_action)
        toolbar.addSeparator()
        toolbar.addAction(self.export_action)
        toolbar.addAction(self.render_action)
        toolbar.addSeparator()
        toolbar.addWidget(QLabel(" Output width "))
        self.width_spin = QSpinBox()
        self.width_spin.setRange(16, 8000)
        self.width_spin.setValue(1200)
        self.width_spin.setSuffix(" px")
        self.width_spin.setToolTip("Rendered image width; the height follows the view's aspect")
        self.width_spin.valueChanged.connect(self._update_output_label)
        toolbar.addWidget(self.width_spin)
        self.output_label = QLabel()
        toolbar.addWidget(self.output_label)
        self.transparent_check = QCheckBox("Transparent background")
        self.transparent_check.setToolTip("Write a PNG with an alpha channel")
        toolbar.addWidget(self.transparent_check)
        toolbar.addSeparator()
        toolbar.addAction(help_action)

    def _build_status_bar(self) -> None:
        bar = self.statusBar()
        self.selection_label = QLabel()
        self.structure_label = QLabel()
        bar.addPermanentWidget(self.selection_label)
        bar.addPermanentWidget(self.structure_label)
        bar.showMessage("Drag: orbit · Shift/middle drag: pan · wheel: zoom · click: select · "
                        "Delete: hide")

    def showEvent(self, event) -> None:  # noqa: N802, ANN001
        super().showEvent(event)
        if not self._camera_initialised:
            self._camera_initialised = True
            # Wait until the layout has given the viewport its final size.
            QTimer.singleShot(0, self.reset_view)

    # ----- view -------------------------------------------------------------------
    def set_display_geometry(self, geometry: DisplayGeometry) -> None:
        """Show ``geometry``; the viewport and the POV-Ray export always share it."""
        self.geometry = geometry
        self.viewport.set_scene(geometry, self.environment)
        hidden = f" · {geometry.hidden_count} hidden" if geometry.hidden_count else ""
        self.structure_label.setText(
            f"{self.structure.composition()} · {len(geometry)} atoms shown{hidden} · "
            "repetitions 1 × 1 × 1"
        )
        self.show_all_action.setEnabled(geometry.hidden_count > 0)
        self.selection = {atom_id for atom_id in self.selection if atom_id in geometry}
        self._update_selection()

    def apply_scene_settings(self, settings: SceneSettings) -> None:
        """Rebuild the displayed geometry from the structure (used by undo commands)."""
        self.scene_settings = settings
        self.boundary_action.setChecked(settings.boundary_images)
        self.set_display_geometry(build_geometry(self.structure, settings))

    def trigger_shortcut(self, keys: QKeySequence) -> bool:
        """Trigger the enabled window action bound to ``keys``; True if one matched."""
        for action in self.findChildren(QAction):
            if action.isEnabled() and any(
                shortcut.matches(keys) == QKeySequence.SequenceMatch.ExactMatch
                for shortcut in action.shortcuts()
            ):
                action.trigger()
                return True
        return False

    # ----- selection and hiding ----------------------------------------------------
    def _on_atom_clicked(self, index: int, toggle: bool) -> None:
        atom_id = self.geometry.atom_ids[index] if index >= 0 else None
        if toggle:
            if atom_id is not None:
                self.selection ^= {atom_id}
        else:
            self.selection = {atom_id} if atom_id is not None else set()
        self._update_selection()

    def select(self, atom_ids: set[AtomId]) -> None:
        self.selection = {atom_id for atom_id in atom_ids if atom_id in self.geometry}
        self._update_selection()

    def clear_selection(self) -> None:
        self.select(set())

    def hide_selected(self) -> None:
        if not self.selection:
            return
        count = len(self.selection)
        new = replace(self.scene_settings,
                      hidden=self.scene_settings.hidden | frozenset(self.selection))
        self.selection = set()
        self.undo_stack.push(SceneSettingsCommand(
            self, new, f"Hide {count} Atom{'s' if count > 1 else ''}"))

    def show_all_atoms(self) -> None:
        if self.scene_settings.hidden:
            self.undo_stack.push(SceneSettingsCommand(
                self, replace(self.scene_settings, hidden=frozenset()), "Show All Atoms"))

    def set_boundary_images(self, enabled: bool) -> None:
        if enabled != self.scene_settings.boundary_images:
            text = "Show Boundary Atoms" if enabled else "Hide Boundary Atoms"
            self.undo_stack.push(SceneSettingsCommand(
                self, replace(self.scene_settings, boundary_images=enabled), text))

    def _update_selection(self) -> None:
        indices = [self.geometry.index_of(atom_id) for atom_id in self.selection]
        self.viewport.set_highlight([i for i in indices if i is not None])
        self.hide_action.setEnabled(bool(self.selection))
        self.selection_label.setText(self.selection_text())

    def selection_text(self) -> str:
        if not self.selection:
            return ""
        if len(self.selection) == 1:
            (atom_id,) = self.selection
            index = self.geometry.index_of(atom_id)
            source, image = atom_id
            position = self.geometry.positions[index]
            element = self.geometry.elements[index]
            label = self.structure.labels[source]
            name = element if label == element else f"{element} ({label})"
            text = (f"Selected: {name}, atom #{source + 1}, "
                    f"image {image[0]} {image[1]} {image[2]}")
            if self.structure.has_cell:
                frac = position @ np.linalg.inv(self.structure.cell)
                text += " · frac " + " ".join(f"{v:.4f}" for v in frac)
            return text + " · xyz " + " ".join(f"{v:.4f}" for v in position) + " Å"
        counts: dict[str, int] = {}
        for atom_id in sorted(self.selection):
            element = self.geometry.elements[self.geometry.index_of(atom_id)]
            counts[element] = counts.get(element, 0) + 1
        parts = ", ".join(f"{element} ×{n}" for element, n in counts.items())
        return f"Selected: {len(self.selection)} atoms ({parts})"

    def reset_view(self) -> None:
        width, height = self.viewport.render_size()
        points, radii = self.geometry.points_and_radii()
        self.viewport.set_camera(default_camera(points, radii, width / height))
        self._update_output_label()

    def current_camera(self) -> Camera:
        return self.viewport.camera()

    def current_render_settings(self) -> RenderSettings:
        view_w, view_h = self.viewport.render_size()
        width = self.width_spin.value()
        height = max(1, round(width * view_h / view_w))
        return RenderSettings(width=width, height=height,
                              transparent_background=self.transparent_check.isChecked())

    def _update_output_label(self, *_args: object) -> None:
        settings = self.current_render_settings()
        self.output_label.setText(f" → {settings.width} × {settings.height} px ")

    # ----- export / render ----------------------------------------------------------
    def configured_povray(self) -> str | None:
        value = self.settings.value(SETTINGS_POVRAY, "", type=str)
        return value or None

    def export_pov(self, path: str | Path | None = None) -> Path | None:
        if path is None:
            path, _ = QFileDialog.getSaveFileName(
                self, "Export POV-Ray Scene", str(Path.home() / "ycrystal-scene.pov"),
                "POV-Ray scene (*.pov)",
            )
            if not path:
                return None
        path = Path(path)
        if path.suffix.lower() != ".pov":
            path = path.with_suffix(".pov")
        settings = self.current_render_settings()
        pov, ini, _ = write_scene_files(
            path.parent, path.stem, self.geometry, self.current_camera(), self.environment,
            settings, title=f"Ycrystal scene: {self.structure.composition()}",
        )
        self.statusBar().showMessage(f"Exported {pov} and {ini.name}", 8000)
        return pov

    def render_png(self, path: str | Path | None = None, show_result: bool = True) -> bool:
        """Start a POV-Ray render of the current view. Returns True if it started."""
        if self._render is not None and self._render.is_running():
            self.statusBar().showMessage("A render is already running.", 5000)
            return False
        try:
            executable = find_povray(self.configured_povray())
        except PovrayNotFoundError as exc:
            self.show_error("POV-Ray Not Available", str(exc))
            return False
        if path is None:
            path, _ = QFileDialog.getSaveFileName(
                self, "Render PNG", str(Path.home() / "ycrystal-render.png"), "PNG image (*.png)"
            )
            if not path:
                return False
        destination = Path(path)
        if destination.suffix.lower() != ".png":
            destination = destination.with_suffix(".png")
        settings = self.current_render_settings()
        version = povray_version(executable)
        job = prepare_job(
            self.geometry, self.current_camera(), self.environment, settings,
            title=f"Ycrystal scene: {self.structure.composition()}",
            renderer_note=f"POV-Ray {version or 'unknown version'} ({executable})",
        )
        self._render_destination = destination
        self._show_result = show_result
        self._render = RenderProcess(job, executable, self)
        self._render.finished.connect(self._on_render_finished)
        self.render_action.setEnabled(False)
        self.statusBar().showMessage(
            f"Rendering {settings.width} × {settings.height} px with POV-Ray…"
        )
        self._render.start()
        return True

    def _on_render_finished(self, result: RenderResult) -> None:
        process = self._render
        self.render_action.setEnabled(True)
        destination = self._render_destination
        try:
            if result.ok and result.image_path is not None and destination is not None:
                try:
                    saved = copy_result(result.image_path, destination)
                except OSError as exc:
                    self.show_error("Could Not Save Image", f"{destination}: {exc}")
                    return
                self.last_render_path = saved
                self.statusBar().showMessage(f"Rendered {saved}", 10000)
                if self._show_result:
                    self._result_dialog = RenderResultDialog(saved, self)
                    self._result_dialog.show()
            else:
                self.statusBar().showMessage("Render failed.", 10000)
                self.show_error("Render Failed", result.message)
        finally:
            if process is not None:
                process.job.cleanup()
            self.render_finished_result = result

    def choose_povray(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Select POV-Ray Executable",
                                              self.configured_povray() or "/usr/bin")
        if path:
            self.settings.setValue(SETTINGS_POVRAY, path)
            self.check_renderer()

    def check_renderer(self) -> None:
        from ycrystal.render.selftest import run_self_test

        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            result = run_self_test(self.configured_povray())
        finally:
            QApplication.restoreOverrideCursor()
        if result.ok:
            QMessageBox.information(self, "Renderer Check", result.message)
        else:
            self.show_error("Renderer Check Failed", result.message)

    # ----- messages -----------------------------------------------------------------
    def show_error(self, title: str, text: str) -> None:
        """Report a problem without blocking the event loop."""
        self.last_error = (title, text)
        box = QMessageBox(QMessageBox.Icon.Warning, title, text, QMessageBox.StandardButton.Ok,
                          self)
        box.setWindowModality(Qt.WindowModality.WindowModal)
        box.open()
        self._message_box = box

    def show_mouse_help(self) -> None:
        QMessageBox.information(self, "Mouse Controls", MOUSE_HELP)

    def closeEvent(self, event) -> None:  # noqa: N802, ANN001
        if self._render is not None and self._render.is_running():
            self._render.cancel()
        self.viewport.close_viewport()
        super().closeEvent(event)
