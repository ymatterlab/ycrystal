"""Main application window: projects, structure import, navigation, selection, output.

The window owns the current structure, display settings, selection, and undo stack.
It delegates drawing to
[`StructureViewport`][ycrystal.viewport.qt_viewport.StructureViewport], reading and
saving to [`ycrystal.io.readers`][ycrystal.io.readers] and
[`ycrystal.io.project`][ycrystal.io.project], and export and rendering to
[`ycrystal.render.pov_writer`][ycrystal.render.pov_writer] and
[`ycrystal.render.jobs`][ycrystal.render.jobs]. Dialogs are opened by separate
``ask_*`` methods so that tests can answer them.
"""

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
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ycrystal.core.camera import Camera, default_camera
from ycrystal.core.scene import (
    AtomId,
    DisplayGeometry,
    SceneSettings,
    build_geometry,
)
from ycrystal.core.structure import Structure
from ycrystal.gui.commands import SceneSettingsCommand
from ycrystal.io.project import (
    PROJECT_SUFFIX,
    Project,
    ProjectError,
    load_project,
    save_project,
)
from ycrystal.io.readers import (
    FORMAT_NAMES,
    SUPPORT_SUMMARY,
    BlockChoiceRequired,
    ElementMappingRequired,
    FormatChoiceRequired,
    StructureImportError,
    detect_format,
    read_structure,
)
from ycrystal.render.jobs import RenderResult, copy_result, prepare_job
from ycrystal.render.pov_writer import RenderSettings, write_scene_files
from ycrystal.render.povray import PovrayNotFoundError, find_povray, povray_version
from ycrystal.render.process import RenderProcess
from ycrystal.viewport.qt_viewport import StructureViewport

SETTINGS_POVRAY = "render/povray_executable"
"""``QSettings`` key of the POV-Ray executable chosen with *Render ▸ Set POV-Ray Executable…*."""

SETTINGS_LAST_DIR = "files/last_directory"
"""``QSettings`` key of the directory last used for opening or saving."""

OPEN_FILTERS = ";;".join(
    [
        "Structures and projects (*.ycrystal *.cif *.vasp *.poscar POSCAR* CONTCAR* *.in *.pwi)",
        "Ycrystal projects (*.ycrystal)",
        "CIF (*.cif)",
        "VASP POSCAR/CONTCAR (POSCAR* CONTCAR* *.vasp *.poscar)",
        "Quantum ESPRESSO input (*.in *.pwi)",
        "All files (*)",
    ]
)

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
    """Non-modal dialog that shows a rendered image and its path."""

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
        self.resize(
            min(pixmap.width() + 60, screen.width() - 80),
            min(pixmap.height() + 120, screen.height() - 80),
        )


class MainWindow(QMainWindow):
    """The Ycrystal main window.

    Creating it needs a ``QApplication`` and a display; the 3D view needs OpenGL.

    Parameters
    ----------
    structure
        Structure to show when no project is given.
    parent
        Qt parent widget.
    project
        Project to show, including its view and settings; takes precedence over
        `structure`.
    project_path
        File the project was loaded from; used as the default save location.

    Attributes
    ----------
    structure
        The scientific structure shown. Navigation, selection, and hiding never change
        it; opening a file replaces it.
    scene_settings
        Current display settings; changed only through undoable commands.
    environment
        Background and lights used for export and rendering.
    geometry
        The [`DisplayGeometry`][ycrystal.core.scene.DisplayGeometry] currently drawn
        and exported.
    selection
        Selected displayed atoms, as a set of [`AtomId`][ycrystal.core.scene.AtomId].
    undo_stack
        ``QUndoStack`` of display-setting changes. Camera, output, and file actions are
        not undoable.
    project_path
        Project file of the current scene, or ``None`` if it has not been saved.
    settings
        ``QSettings`` with machine-specific choices (POV-Ray path, last directory).
    last_error
        Title and text of the last error message, for tests and scripts.
    last_render_path
        Destination of the last successful render.
    render_finished_result
        [`RenderResult`][ycrystal.render.jobs.RenderResult] of the last finished render.

    Raises
    ------
    ValueError
        If neither `structure` nor `project` is given.

    Notes
    -----
    The saved or default camera is applied after the window is first shown, once the
    layout has given the 3D view its final size.
    """

    def __init__(
        self,
        structure: Structure | None = None,
        parent: QWidget | None = None,
        *,
        project: Project | None = None,
        project_path: Path | None = None,
    ) -> None:
        super().__init__(parent)
        if project is None:
            if structure is None:
                raise ValueError("MainWindow needs a structure or a project")
            project = Project(structure)
        self.structure = project.structure
        self.scene_settings = project.scene
        self.environment = project.environment
        self.project_path: Path | None = project_path
        self.geometry = build_geometry(self.structure, self.scene_settings)
        self.settings = QSettings()
        self._render: RenderProcess | None = None
        self._render_destination: Path | None = None
        self._result_dialog: RenderResultDialog | None = None
        self._show_result = True
        self._camera_initialised = False
        self._pending_camera: Camera | None = project.camera
        self._saved_camera: Camera | None = None
        self._saved_output: tuple[int, bool] = (
            project.output.width,
            project.output.transparent_background,
        )
        self.last_error: tuple[str, str] | None = None
        self.last_render_path: Path | None = None
        self.render_finished_result: RenderResult | None = None
        self.selection: set[AtomId] = set()
        self.undo_stack = QUndoStack(self)

        self.viewport = StructureViewport(self)
        self.setCentralWidget(self.viewport)
        self._build_actions()
        self._build_status_bar()
        self.width_spin.setValue(project.output.width)
        self.transparent_check.setChecked(project.output.transparent_background)
        self.boundary_action.setChecked(self.scene_settings.boundary_images)
        self.set_display_geometry(self.geometry)
        self.viewport.camera_changed.connect(self._update_output_label)
        self.viewport.camera_changed.connect(self._refresh_title)
        self.viewport.atom_clicked.connect(self._on_atom_clicked)
        self.viewport.key_pressed.connect(self.trigger_shortcut)
        self.undo_stack.cleanChanged.connect(self._refresh_title)
        self.width_spin.valueChanged.connect(self._refresh_title)
        self.transparent_check.toggled.connect(self._refresh_title)
        self._refresh_title()

    # ----- construction -------------------------------------------------------------
    def _build_actions(self) -> None:
        self.open_action = QAction(
            "Open…",
            self,
            shortcut=QKeySequence.StandardKey.Open,
            toolTip="Open a structure file or a Ycrystal project",
        )
        self.open_action.triggered.connect(lambda: self.open_file())
        self.open_as_action = QAction(
            "Open As…", self, toolTip="Open a file, choosing its format explicitly"
        )
        self.open_as_action.triggered.connect(self.open_file_as)
        self.save_action = QAction(
            "Save Project",
            self,
            shortcut=QKeySequence.StandardKey.Save,
            toolTip="Save the structure, view, and settings (.ycrystal)",
        )
        self.save_action.triggered.connect(lambda: self.save())
        self.save_as_action = QAction(
            "Save Project As…", self, shortcut=QKeySequence("Ctrl+Shift+S")
        )
        self.save_as_action.triggered.connect(lambda: self.save_as())
        self.fit_action = QAction(
            "Fit", self, shortcut=QKeySequence("F"), toolTip="Frame the structure (F)"
        )
        self.fit_action.triggered.connect(self.viewport.fit)
        self.reset_view_action = QAction(
            "Reset View", self, toolTip="Default orientation, framed to fit"
        )
        self.reset_view_action.triggered.connect(self.reset_view)
        self.export_action = QAction(
            "Export POV-Ray…", self, toolTip="Write editable .pov and .ini files"
        )
        self.export_action.triggered.connect(lambda: self.export_pov())
        self.render_action = QAction(
            "Render PNG…",
            self,
            shortcut=QKeySequence("Ctrl+R"),
            toolTip="Render the current view with POV-Ray",
        )
        self.render_action.triggered.connect(lambda: self.render_png())
        self.set_povray_action = QAction("Set POV-Ray Executable…", self)
        self.set_povray_action.triggered.connect(self.choose_povray)
        self.check_povray_action = QAction("Check Renderer", self)
        self.check_povray_action.triggered.connect(self.check_renderer)
        help_action = QAction(
            "Mouse Controls", self, shortcut=QKeySequence.StandardKey.HelpContents
        )
        help_action.triggered.connect(self.show_mouse_help)
        formats_action = QAction("Supported File Formats", self)
        formats_action.triggered.connect(self.show_format_help)
        quit_action = QAction("Quit", self, shortcut=QKeySequence.StandardKey.Quit)
        quit_action.triggered.connect(self.close)

        self.undo_action = self.undo_stack.createUndoAction(self, "Undo")
        self.undo_action.setShortcut(QKeySequence.StandardKey.Undo)
        self.redo_action = self.undo_stack.createRedoAction(self, "Redo")
        self.redo_action.setShortcuts([QKeySequence("Ctrl+Shift+Z"), QKeySequence("Ctrl+Y")])
        self.hide_action = QAction(
            "Hide Selected Atoms",
            self,
            enabled=False,
            toolTip="Remove the selected balls from the view and exports (Delete). "
            "The structure is unchanged.",
        )
        self.hide_action.setShortcuts(
            [QKeySequence(Qt.Key.Key_Delete), QKeySequence(Qt.Key.Key_Backspace)]
        )
        self.hide_action.triggered.connect(self.hide_selected)
        self.select_none_action = QAction(
            "Select None", self, shortcut=QKeySequence(Qt.Key.Key_Escape)
        )
        self.select_none_action.triggered.connect(self.clear_selection)
        self.show_all_action = QAction(
            "Show All Atoms", self, enabled=False, toolTip="Bring back every hidden ball"
        )
        self.show_all_action.triggered.connect(self.show_all_atoms)
        self.boundary_action = QAction(
            "Show Boundary Atoms",
            self,
            checkable=True,
            checked=True,
            toolTip="Draw atoms at every equivalent position on cell faces, edges, corners",
        )
        self.boundary_action.triggered.connect(self.set_boundary_images)

        file_menu = self.menuBar().addMenu("&File")
        for action in (
            self.open_action,
            self.open_as_action,
            None,
            self.save_action,
            self.save_as_action,
            None,
            self.export_action,
            self.render_action,
            None,
            quit_action,
        ):
            file_menu.addSeparator() if action is None else file_menu.addAction(action)
        edit_menu = self.menuBar().addMenu("&Edit")
        edit_menu.addAction(self.undo_action)
        edit_menu.addAction(self.redo_action)
        edit_menu.addSeparator()
        edit_menu.addAction(self.hide_action)
        edit_menu.addAction(self.select_none_action)
        view_menu = self.menuBar().addMenu("&View")
        view_menu.addAction(self.fit_action)
        view_menu.addAction(self.reset_view_action)
        view_menu.addSeparator()
        view_menu.addAction(self.boundary_action)
        view_menu.addAction(self.show_all_action)
        render_menu = self.menuBar().addMenu("&Render")
        render_menu.addAction(self.render_action)
        render_menu.addAction(self.set_povray_action)
        render_menu.addAction(self.check_povray_action)
        help_menu = self.menuBar().addMenu("&Help")
        help_menu.addAction(help_action)
        help_menu.addAction(formats_action)

        toolbar = self.addToolBar("Main")
        toolbar.setObjectName("main_toolbar")
        toolbar.setMovable(False)
        toolbar.addAction(self.open_action)
        toolbar.addAction(self.save_action)
        toolbar.addSeparator()
        toolbar.addAction(self.undo_action)
        toolbar.addAction(self.redo_action)
        toolbar.addSeparator()
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
        bar.showMessage(
            "Drag: orbit · Shift/middle drag: pan · wheel: zoom · click: select · Delete: hide"
        )

    def showEvent(self, event) -> None:  # noqa: N802, ANN001
        super().showEvent(event)
        if not self._camera_initialised:
            self._camera_initialised = True
            # Wait until the layout has given the viewport its final size.
            QTimer.singleShot(0, self._initialise_camera)

    def _initialise_camera(self) -> None:
        camera, self._pending_camera = self._pending_camera, None
        if camera is None:
            self.reset_view()
        else:
            self.viewport.set_camera(camera)
            self._update_output_label()
        self._mark_clean()

    # ----- project state ----------------------------------------------------------------
    def current_project(self) -> Project:
        """Return the current state as a [`Project`][ycrystal.io.project.Project]."""
        return Project(
            structure=self.structure,
            scene=self.scene_settings,
            environment=self.environment,
            camera=self.current_camera() if self._camera_initialised else self._pending_camera,
            output=self.current_render_settings(),
        )

    def install_project(self, project: Project, path: Path | None) -> None:
        """Replace everything shown with ``project`` (clears undo history and selection)."""
        self.structure = project.structure
        self.scene_settings = project.scene
        self.environment = project.environment
        self.project_path = path
        self.undo_stack.clear()
        self.selection = set()
        self.boundary_action.setChecked(project.scene.boundary_images)
        self.width_spin.setValue(project.output.width)
        self.transparent_check.setChecked(project.output.transparent_background)
        self.set_display_geometry(build_geometry(self.structure, self.scene_settings))
        if self._camera_initialised:
            if project.camera is None:
                self.reset_view()
            else:
                self.viewport.set_camera(project.camera)
            self._mark_clean()
        else:
            self._pending_camera = project.camera
            self._refresh_title()

    def is_modified(self) -> bool:
        """Return whether the scene differs from the last saved or opened state.

        Display-setting changes, a different output width or transparency setting, and
        any change of the view count as modifications.
        """
        if not self.undo_stack.isClean():
            return True
        if (self.width_spin.value(), self.transparent_check.isChecked()) != self._saved_output:
            return True
        if self._saved_camera is None or not self._camera_initialised:
            return False
        return not _same_camera(self._saved_camera, self.viewport.camera())

    def _mark_clean(self) -> None:
        self.undo_stack.setClean()
        self._saved_output = (self.width_spin.value(), self.transparent_check.isChecked())
        self._saved_camera = self.viewport.camera() if self._camera_initialised else None
        self._refresh_title()

    def _refresh_title(self, *_args: object) -> None:
        if self.project_path is not None:
            name = self.project_path.name
        else:
            name = f"{self.structure.composition()} (unsaved)"
        self.setWindowTitle(f"{name}[*] — Ycrystal")
        self.setWindowModified(self.is_modified())

    def maybe_save(self) -> bool:
        """Ask about unsaved changes. False means: cancel the close/open action."""
        if not self.is_modified():
            return True
        answer = self.ask_save_changes()
        if answer == "save":
            return self.save()
        return answer == "discard"

    # ----- open -------------------------------------------------------------------------
    def open_file(self, path: str | Path | None = None, fmt: str | None = None) -> bool:
        """Open a structure file or a project, replacing the current scene.

        Parameters
        ----------
        path
            File to open; ``None`` shows a file dialog.
        fmt
            Format key (``"poscar"``, ``"cif"``, ``"qe"``, or ``"project"``); ``None``
            detects it and asks if detection is ambiguous.

        Returns
        -------
        bool
            Whether something was loaded. ``False`` if the user cancelled (including
            the question about unsaved changes) or the file could not be read. Read
            failures show an error; cancellation does not. The current scene stays
            unchanged in either case.
        """
        if not self.maybe_save():
            return False
        if path is None:
            path = self.ask_open_path()
            if path is None:
                return False
        return self._load_path(Path(path), fmt)

    def open_file_as(self) -> bool:
        """Ask for a format, then open a file in that format (*File ▸ Open As…*)."""
        names = [FORMAT_NAMES[key] for key in ("cif", "poscar", "qe", "project")]
        choice = self.ask_choice("Open As", "Read the file as:", names)
        if choice is None:
            return False
        fmt = next(key for key, name in FORMAT_NAMES.items() if name == choice)
        return self.open_file(fmt=fmt)

    def _load_path(self, path: Path, fmt: str | None) -> bool:
        if fmt is None:
            try:
                fmt = detect_format(path)
            except FormatChoiceRequired as question:
                names = [FORMAT_NAMES[c] for c in question.candidates]
                choice = self.ask_choice(
                    "Choose Format",
                    f"Ycrystal cannot tell the format of {path.name} from its name and "
                    "content. Read it as:",
                    names,
                )
                if choice is None:
                    return False
                fmt = next(key for key, name in FORMAT_NAMES.items() if name == choice)
            except StructureImportError as exc:
                self.show_error("Cannot Open File", str(exc))
                return False
        if fmt == "project":
            try:
                project = load_project(path)
            except ProjectError as exc:
                self.show_error("Cannot Open Project", str(exc))
                return False
            self.install_project(project, path)
            self.statusBar().showMessage(f"Opened project {path.name}", 8000)
            self._remember_directory(path)
            return True

        block: str | None = None
        element_map: dict[str, str] = {}
        for _attempt in range(6):
            try:
                structure = read_structure(path, fmt, block=block, element_map=element_map)
                break
            except BlockChoiceRequired as question:
                block = self.ask_choice(
                    "Choose Data Block",
                    f"{path.name} contains several structures. Open:",
                    question.blocks,
                )
                if block is None:
                    return False
            except ElementMappingRequired as question:
                answer = self.ask_element_mapping(question)
                if answer is None:
                    return False
                element_map.update(answer)
            except StructureImportError as exc:
                self.show_error("Cannot Open File", str(exc))
                return False
        else:
            self.show_error("Cannot Open File", f"{path.name} could not be read.")
            return False
        self.install_project(Project(structure), None)
        source = _source_info(structure)
        details = f", block {source['block']}" if source.get("block") else ""
        self.statusBar().showMessage(
            f"Imported {path.name} ({FORMAT_NAMES[fmt]}{details}): {len(structure)} atoms, "
            f"{structure.composition()}",
            10000,
        )
        self._remember_directory(path)
        return True

    def ask_element_mapping(self, question: ElementMappingRequired) -> dict[str, str] | None:
        mapping = {}
        for key, suggestion, detail in zip(
            question.keys, question.suggestions, question.details, strict=True
        ):
            symbol = self.ask_text(
                "Element Needed", f"{question}\n\nElement for {key} ({detail}):", suggestion or ""
            )
            if not symbol:
                return None
            mapping[key] = symbol.strip()
        return mapping

    # ----- save -------------------------------------------------------------------------
    def save(self) -> bool:
        """Save to the current project file, or ask for one. Return whether it was saved."""
        if self.project_path is None:
            return self.save_as()
        return self._write_project(self.project_path)

    def save_as(self, path: str | Path | None = None) -> bool:
        """Save the project to a new file.

        Parameters
        ----------
        path
            Destination; ``None`` shows a file dialog. ``.ycrystal`` is appended if the
            name has another suffix.

        Returns
        -------
        bool
            Whether the project was saved; failures are shown in a message.
        """
        if path is None:
            path = self.ask_save_path()
            if path is None:
                return False
        path = Path(path)
        if path.suffix.lower() != PROJECT_SUFFIX:
            path = path.with_name(path.name + PROJECT_SUFFIX)
        return self._write_project(path)

    def _write_project(self, path: Path) -> bool:
        try:
            save_project(path, self.current_project())
        except (OSError, ValueError) as exc:
            self.show_error("Cannot Save Project", f"{path}: {exc}")
            return False
        self.project_path = path
        self._mark_clean()
        self.statusBar().showMessage(f"Saved {path}", 8000)
        self._remember_directory(path)
        return True

    # ----- dialogs (separate methods so tests can answer them) ------------------------------
    def ask_save_changes(self) -> str:
        """Return "save", "discard", or "cancel"."""
        buttons = (
            QMessageBox.StandardButton.Save
            | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel
        )
        answer = QMessageBox.question(
            self,
            "Unsaved Changes",
            "The project has unsaved changes (view, display settings, or output options). "
            "Save them first?",
            buttons,
            QMessageBox.StandardButton.Save,
        )
        return {
            QMessageBox.StandardButton.Save: "save",
            QMessageBox.StandardButton.Discard: "discard",
        }.get(answer, "cancel")

    def ask_open_path(self) -> Path | None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Structure or Project", self._last_directory(), OPEN_FILTERS
        )
        return Path(path) if path else None

    def ask_save_path(self) -> Path | None:
        if self.project_path is not None:
            default = self.project_path
        else:
            source = _source_info(self.structure)
            if source.get("format") in ("poscar", "cif", "qe") and source.get("name"):
                stem = Path(source["name"]).stem
            else:
                stem = self.structure.composition()
            default = Path(self._last_directory()) / f"{stem}{PROJECT_SUFFIX}"
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Project", str(default), f"Ycrystal project (*{PROJECT_SUFFIX})"
        )
        return Path(path) if path else None

    def ask_choice(self, title: str, label: str, items: list[str]) -> str | None:
        item, ok = QInputDialog.getItem(self, title, label, items, 0, False)
        return item if ok else None

    def ask_text(self, title: str, label: str, default: str = "") -> str | None:
        text, ok = QInputDialog.getText(self, title, label, QLineEdit.EchoMode.Normal, default)
        return text if ok else None

    def _last_directory(self) -> str:
        return self.settings.value(SETTINGS_LAST_DIR, str(Path.home()), type=str)

    def _remember_directory(self, path: Path) -> None:
        self.settings.setValue(SETTINGS_LAST_DIR, str(path.resolve().parent))

    # ----- view -------------------------------------------------------------------
    def set_display_geometry(self, geometry: DisplayGeometry) -> None:
        """Show a geometry; the viewport and the POV-Ray export always share it.

        Selected atoms that are not part of `geometry` are deselected.
        """
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
        """Replace the selection; IDs that are not displayed are ignored."""
        self.selection = {atom_id for atom_id in atom_ids if atom_id in self.geometry}
        self._update_selection()

    def clear_selection(self) -> None:
        """Deselect all atoms (*Edit ▸ Select None*, Esc)."""
        self.select(set())

    def hide_selected(self) -> None:
        """Hide the selected displayed atoms as one undoable step (Delete).

        Only the selected balls disappear, from the view and from exports; other images
        of the same atom stay, and the structure is unchanged.
        """
        if not self.selection:
            return
        count = len(self.selection)
        new = replace(
            self.scene_settings, hidden=self.scene_settings.hidden | frozenset(self.selection)
        )
        self.selection = set()
        self.undo_stack.push(
            SceneSettingsCommand(self, new, f"Hide {count} Atom{'s' if count > 1 else ''}")
        )

    def show_all_atoms(self) -> None:
        """Bring back every hidden atom as one undoable step (*View ▸ Show All Atoms*)."""
        if self.scene_settings.hidden:
            self.undo_stack.push(
                SceneSettingsCommand(
                    self, replace(self.scene_settings, hidden=frozenset()), "Show All Atoms"
                )
            )

    def set_boundary_images(self, enabled: bool) -> None:
        """Switch boundary images on or off as one undoable step.

        Hidden IDs are kept while boundary images are off and apply again when they
        are switched back on.
        """
        if enabled != self.scene_settings.boundary_images:
            text = "Show Boundary Atoms" if enabled else "Hide Boundary Atoms"
            self.undo_stack.push(
                SceneSettingsCommand(
                    self, replace(self.scene_settings, boundary_images=enabled), text
                )
            )

    def _update_selection(self) -> None:
        indices = [self.geometry.index_of(atom_id) for atom_id in self.selection]
        self.viewport.set_highlight([i for i in indices if i is not None])
        self.hide_action.setEnabled(bool(self.selection))
        self.selection_label.setText(self.selection_text())

    def selection_text(self) -> str:
        """Return the status-bar description of the selection.

        For one atom: element and label, 1-based atom number, image offset, fractional
        and Cartesian (Å) coordinates, and movable flags if the file had any. For
        several atoms: the number per element.
        """
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
            text = f"Selected: {name}, atom #{source + 1}, image {image[0]} {image[1]} {image[2]}"
            if self.structure.has_cell:
                frac = position @ np.linalg.inv(self.structure.cell)
                text += " · frac " + " ".join(f"{v:.4f}" for v in frac)
            text += " · xyz " + " ".join(f"{v:.4f}" for v in position) + " Å"
            if self.structure.movable is not None:
                fixed = [
                    axis
                    for axis, free in zip("xyz", self.structure.movable[source], strict=True)
                    if not free
                ]
                text += f" · fixed {' '.join(fixed)}" if fixed else " · free"
            return text
        counts: dict[str, int] = {}
        for atom_id in sorted(self.selection):
            element = self.geometry.elements[self.geometry.index_of(atom_id)]
            counts[element] = counts.get(element, 0) + 1
        parts = ", ".join(f"{element} ×{n}" for element, n in counts.items())
        return f"Selected: {len(self.selection)} atoms ({parts})"

    def reset_view(self) -> None:
        """Show the default orientation, framed to fit (*View ▸ Reset View*)."""
        width, height = self.viewport.render_size()
        points, radii = self.geometry.points_and_radii()
        self.viewport.set_camera(default_camera(points, radii, width / height))
        self._update_output_label()

    def current_camera(self) -> Camera:
        """Return the camera of the 3D view."""
        return self.viewport.camera()

    def current_render_settings(self) -> RenderSettings:
        """Return the output settings for export and rendering.

        The width comes from the toolbar; the height is the width times the 3D view's
        height-to-width ratio, rounded, so the image shows exactly what the view
        shows. Antialiasing is always on.
        """
        view_w, view_h = self.viewport.render_size()
        width = self.width_spin.value()
        height = max(1, round(width * view_h / view_w))
        return RenderSettings(
            width=width, height=height, transparent_background=self.transparent_check.isChecked()
        )

    def _update_output_label(self, *_args: object) -> None:
        settings = self.current_render_settings()
        self.output_label.setText(f" → {settings.width} × {settings.height} px ")

    # ----- export / render ----------------------------------------------------------
    def configured_povray(self) -> str | None:
        """Return the POV-Ray executable stored in the settings, or ``None``."""
        value = self.settings.value(SETTINGS_POVRAY, "", type=str)
        return value or None

    def _output_stem(self) -> str:
        if self.project_path is not None:
            return self.project_path.stem
        return self.structure.composition()

    def export_pov(self, path: str | Path | None = None) -> Path | None:
        """Write the current view as an editable POV-Ray scene (*File ▸ Export POV-Ray…*).

        Writes ``NAME.pov`` and ``NAME.ini`` next to each other; the ``.ini`` file
        names ``NAME.png`` as output. POV-Ray is not needed and not started.

        Parameters
        ----------
        path
            Scene file; ``None`` shows a file dialog. The suffix is replaced by
            ``.pov``.

        Returns
        -------
        pathlib.Path or None
            Path of the ``.pov`` file, or ``None`` if the dialog was cancelled.

        Raises
        ------
        OSError
            If the files cannot be written.

        Notes
        -----
        Existing files are replaced. The file dialog asks before replacing the
        ``.pov`` file; the ``.ini`` file is replaced without asking.
        """
        if path is None:
            path, _ = QFileDialog.getSaveFileName(
                self,
                "Export POV-Ray Scene",
                str(Path(self._last_directory()) / f"{self._output_stem()}.pov"),
                "POV-Ray scene (*.pov)",
            )
            if not path:
                return None
        path = Path(path)
        if path.suffix.lower() != ".pov":
            path = path.with_suffix(".pov")
        settings = self.current_render_settings()
        pov, ini, _ = write_scene_files(
            path.parent,
            path.stem,
            self.geometry,
            self.current_camera(),
            self.environment,
            settings,
            title=f"Ycrystal scene: {self.structure.composition()}",
        )
        self.statusBar().showMessage(f"Exported {pov} and {ini.name}", 8000)
        return pov

    def render_png(self, path: str | Path | None = None, show_result: bool = True) -> bool:
        """Start a POV-Ray render of the current view (*Render PNG…*, Ctrl+R).

        After a synchronous version query (up to 15 seconds) and job preparation,
        POV-Ray runs in the background in a temporary job directory. The method
        returns once that process has been requested. When it finishes, the PNG is
        copied to the destination (replacing an existing file), the job directory
        is deleted, and the image is shown or an error message explains the failure.

        Parameters
        ----------
        path
            Destination PNG; ``None`` shows a file dialog. The suffix is replaced by
            ``.png``.
        show_result
            Whether to show the finished image in a dialog.

        Returns
        -------
        bool
            Whether a render started. ``False`` if one is already running, POV-Ray is
            not found (a message explains how to set it up), or the dialog was
            cancelled.

        Raises
        ------
        OSError
            If the temporary job directory or scene files cannot be created.
        """
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
                self,
                "Render PNG",
                str(Path(self._last_directory()) / f"{self._output_stem()}.png"),
                "PNG image (*.png)",
            )
            if not path:
                return False
        destination = Path(path)
        if destination.suffix.lower() != ".png":
            destination = destination.with_suffix(".png")
        settings = self.current_render_settings()
        version = povray_version(executable)
        job = prepare_job(
            self.geometry,
            self.current_camera(),
            self.environment,
            settings,
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
        """Ask for a POV-Ray executable, store it, and check it."""
        path, _ = QFileDialog.getOpenFileName(
            self, "Select POV-Ray Executable", self.configured_povray() or "/usr/bin"
        )
        if path:
            self.settings.setValue(SETTINGS_POVRAY, path)
            self.check_renderer()

    def check_renderer(self) -> None:
        """Run the renderer self-test and show the verdict (*Render ▸ Check Renderer*).

        Runs synchronously: the window does not respond until the test finishes,
        normally within a few seconds.
        """
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
        """Show a warning message without blocking the event loop.

        The title and text are also stored in `last_error`.
        """
        self.last_error = (title, text)
        box = QMessageBox(
            QMessageBox.Icon.Warning, title, text, QMessageBox.StandardButton.Ok, self
        )
        box.setWindowModality(Qt.WindowModality.WindowModal)
        box.open()
        self._message_box = box

    def show_mouse_help(self) -> None:
        """Show the mouse and keyboard summary (*Help ▸ Mouse Controls*, F1)."""
        QMessageBox.information(self, "Mouse Controls", MOUSE_HELP)

    def show_format_help(self) -> None:
        """Show the supported file formats (*Help ▸ Supported File Formats*)."""
        QMessageBox.information(self, "Supported File Formats", SUPPORT_SUMMARY)

    def closeEvent(self, event) -> None:  # noqa: N802, ANN001
        if not self.maybe_save():
            event.ignore()
            return
        if self._render is not None and self._render.is_running():
            self._render.cancel()
        self.viewport.close_viewport()
        super().closeEvent(event)


def _same_camera(a: Camera, b: Camera) -> bool:
    values_a = np.concatenate([a.position, a.focal_point, a.view_up, [a.parallel_scale]])
    values_b = np.concatenate([b.position, b.focal_point, b.view_up, [b.parallel_scale]])
    return bool(np.allclose(values_a, values_b, rtol=1e-9, atol=1e-9))


def _source_info(structure: Structure) -> dict:
    source = structure.metadata.get("source")
    return source if isinstance(source, dict) else {}
