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
from typing import NamedTuple

import numpy as np
from PySide6.QtCore import QSettings, QSignalBlocker, Qt, QTimer
from PySide6.QtGui import QAction, QActionGroup, QKeySequence, QPixmap, QUndoStack
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDockWidget,
    QFileDialog,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ycrystal import presets as presets_module
from ycrystal.core import aspect, measure
from ycrystal.core.annotation import TextAnnotation
from ycrystal.core.bond_symmetry import equivalent_displayed_bonds
from ycrystal.core.bonds import Pair, periodic_bonds, summarize_pairs
from ycrystal.core.camera import Camera, CameraPolicyError, axis_view, default_camera
from ycrystal.core.export import ExportOptions, format_label, path_for_format
from ycrystal.core.legend import LegendSettings, legend_entries
from ycrystal.core.lighting import resolve_lighting
from ycrystal.core.polyhedra import PolyhedronRule
from ycrystal.core.scene import (
    LARGE_DISPLAY_ATOMS,
    AtomId,
    BondId,
    DisplayGeometry,
    Environment,
    SceneSettings,
    build_geometry,
    count_displayed_atoms,
    element_color,
)
from ycrystal.core.structure import Structure
from ycrystal.core.vectors import Key, VectorRecord, VectorSet, VectorStyle
from ycrystal.gui.commands import SceneSettingsCommand
from ycrystal.gui.export_dialog import ExportChoice, ExportDialog
from ycrystal.gui.gallery import TARGET_DEFAULT, TARGET_SELECTION, PresetGallery
from ycrystal.gui.lighting_setup import LightingSetupWindow
from ycrystal.gui.material_editor import (
    MaterialEditorDialog,
    load_personal_materials,
    save_personal_material,
)
from ycrystal.gui.native import executable_filter, native_keys, personal_thumbnail_directory
from ycrystal.gui.panels.annotation_panel import AnnotationPanel
from ycrystal.gui.panels.appearance_panel import AppearancePanel
from ycrystal.gui.panels.legend_panel import LegendPanel
from ycrystal.gui.panels.measurement_panel import MeasurementPanel, MeasurementRow
from ycrystal.gui.panels.output_panel import PreviewPanel, RenderPanel
from ycrystal.gui.panels.polyhedra_panel import PolyhedraPanel
from ycrystal.gui.panels.scene_panel import MAX_REPETITIONS, ScenePanel
from ycrystal.gui.style_dialog import (  # noqa: F401 (labels re-exported)
    STYLE_PART_LABELS,
    StyleImportChoice,
    StyleImportDialog,
)
from ycrystal.gui.vector_dialog import VectorEditDialog, VectorPanel
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
from ycrystal.io.style import (
    STYLE_SUFFIX,
    ElementMapError,
    Style,
    StyleError,
    apply_style,
    load_style,
    save_style,
)
from ycrystal.presets import (
    apply_lighting,
    environment_from_preset,
    get_environment,
    get_lighting,
    get_material,
)
from ycrystal.render.formats import write_export
from ycrystal.render.jobs import RenderResult, copy_result, prepare_job
from ycrystal.render.legend import resolved_font_family
from ycrystal.render.pov_writer import RenderSettings, required_includes, write_scene_files
from ycrystal.render.povray import (
    PovrayNotFoundError,
    find_povray,
    missing_includes,
    povray_version,
)
from ycrystal.render.process import RenderProcess, RenderQueue
from ycrystal.viewport.qt_viewport import StructureViewport

SETTINGS_POVRAY = "render/povray_executable"
"""``QSettings`` key of the POV-Ray executable chosen with *Render ▸ Set POV-Ray Executable…*."""

SETTINGS_LAST_DIR = "files/last_directory"
"""``QSettings`` key of the directory last used for opening or saving."""

SETTINGS_AUTO_PREVIEW = "render/auto_preview"
SETTINGS_HANDLES = "view/supercell_handles"
"""QSettings key: whether the supercell handles are shown (default on)."""

ROTATION_AXES = ("free", "a", "b", "c", "x", "y", "z")
"""Rotation modes: free trackball rotation, or rotation about a lattice or Cartesian axis."""

ROTATION_STEPS = (5, 15, 30, 45, 90)
"""Angles in degrees offered for the rotate buttons."""

"""``QSettings`` key of the *Update automatically* choice of the preview panel."""

AUTO_PREVIEW_DEFAULT = True
"""Whether automatic previews are on when the user has not chosen yet."""

SETTINGS_PREVIEW_RESOLUTION = "render/preview_resolution"
"""``QSettings`` key of the preview resolution choice (``small``, ``medium``, ``large``,
or ``custom``; see [`PREVIEW_PRESETS`][ycrystal.core.aspect.PREVIEW_PRESETS])."""

SETTINGS_PREVIEW_WIDTH = "render/preview_custom_width"
"""``QSettings`` key of the custom preview width in pixels."""

PREVIEW_DELAY_MS = 600
"""Pause after the last change before an automatic preview starts."""

LIGHTING_SETUP_DELAY_MS = 30
"""Longest delay before the Lighting Setup window follows a camera or scene change."""


#: Ask before displaying more atoms than this (measured; see docs/PROGRESS.md, M2).
SOFT_LIMIT_ATOMS = LARGE_DISPLAY_ATOMS

#: View-along directions: (label, tooltip). The named axis points toward the viewer.
VIEW_AXES = {
    "a": "Look down a (a toward you)",
    "b": "Look down b (b toward you)",
    "c": "Look down c (c toward you)",
    "x": "Look down Cartesian x",
    "y": "Look down Cartesian y",
    "z": "Look down Cartesian z",
}

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
<tr><td><b>Ctrl + M</b></td><td>Choose a material for the selected atoms</td></tr>
<tr><td><b>Drag an a/b/c handle</b></td><td>Add or remove whole cells along that axis
(Esc or right button cancels)</td></tr>
<tr><td><b>Rotate: about a…z</b></td><td>Left drag turns only about that axis</td></tr>
<tr><td><b>Ctrl + Left / Right</b></td><td>Turn by the step angle about the rotation axis
</td></tr>
<tr><td><b>Ctrl + Z</b> / <b>Ctrl + Shift + Z</b></td><td>Undo / redo</td></tr>
<tr><td><b>a b c / x y z</b> buttons</td><td>Look down an axis (Shift: opposite side)</td></tr>
</table>
<p>The Structure panel sets repetitions (cells along a × b × c), boundary atoms, and
cell edges; the Bonds panel sets bond length tolerance, radius, and element pairs.
Repetitions are always rebuilt from the original structure.</p>
<p>Atoms on cell faces, edges, and corners are drawn at every equivalent boundary
position (View ▸ Show Boundary Atoms). Each drawn ball can be hidden on its own;
View ▸ Show All Atoms brings hidden balls back.</p>
<p>Navigation and hiding change only the presentation, never atomic coordinates.<br>
The blue frame shows the rendered area. The live view approximates materials and
lighting; Preview (F5) renders the framed view small with POV-Ray, Render Image writes
the full-size PNG, PDF, or JPEG, and Cancel stops a running render.</p>"""


class PreviewRequest(NamedTuple):
    """Identity of a preview job: the scene revision and the requested pixel size.

    A finished preview is shown only if its request equals the window's current one,
    so neither an older scene nor an older preview resolution can replace the latest
    result.
    """

    revision: int
    width: int
    height: int


class RenderResultDialog(QDialog):
    """Non-modal dialog that shows a rendered image and its path."""

    def __init__(
        self, image: Path, parent: QWidget | None = None, picture: Path | None = None
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Rendered image — {image.name}")
        layout = QVBoxLayout(self)
        label = QLabel()
        # `picture`: the rendered PNG, shown for files Qt cannot display (PDF).
        label.setPixmap(QPixmap(str(picture or image)))
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
        Background preset, transparency, and lights used for export and rendering;
        changed through undoable commands.
    geometry
        The [`DisplayGeometry`][ycrystal.core.scene.DisplayGeometry] currently drawn
        and exported.
    selection
        Selected displayed atoms, as a set of [`AtomId`][ycrystal.core.scene.AtomId].
    measurements
        [`MeasurementSession`][ycrystal.core.measure.MeasurementSession]: the
        measurement mode, the atoms picked so far, and this session's distances and
        angles (not saved in projects).
    undo_stack
        ``QUndoStack`` of display-setting, material, and background changes. Camera,
        output size, and file actions are not undoable.
    scene_revision
        Counter increased by every change that affects the rendered image (view,
        scene, appearance, output size). Previews made for an older revision are
        discarded when they finish.
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
    preview_result
        ``(RenderResult, revision)`` of the last preview that finished, including
        discarded and cancelled ones.
    preview_shown
        [`PreviewRequest`][ycrystal.gui.main_window.PreviewRequest] of the preview image
        shown in the dock, or ``None``.
    preview_discarded
        Number of preview results discarded because the scene or the preview
        resolution had changed.

    Raises
    ------
    ValueError
        If neither `structure` nor `project` is given.

    Notes
    -----
    The saved or default camera is applied after the window is first shown, once the
    layout has given the 3D view its final size. Cameras exchanged with projects, export,
    and rendering are output cameras: they describe the image inside the output frame.
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
        # Personal custom materials (FR-MATERIAL-01) live in the user's settings, with
        # their rendered thumbnails in a folder next to the settings file (or in the
        # application data folder where the settings are not a file of their own).
        presets_module.CUSTOM_THUMBNAILS = personal_thumbnail_directory(self.settings)
        self.personal_material_notes = load_personal_materials(self.settings)[1]
        self.material_editor: MaterialEditorDialog | None = None
        self._material_preview = False
        self._material_edit_atoms: frozenset[AtomId] = frozenset()
        self._thumbnail_renders: list[RenderProcess] = []
        # Vectors (FR-VECTOR-01): the window, the editor, and the editor's frozen targets.
        self.vector_panel: VectorPanel | None = None
        self.vector_editor: VectorEditDialog | None = None
        self._vector_preview = False
        self._vector_targets: tuple[str, tuple] = ("images", ())
        self._render: RenderProcess | None = None
        self._render_destination: Path | None = None
        self._render_options: ExportOptions | None = None
        # Last choice of the Render Image dialog (this session only).
        self.export_choice: ExportChoice | None = None
        self._result_dialog: RenderResultDialog | None = None
        self._show_result = True
        self._camera_initialised = False
        self._pending_camera: Camera | None = project.camera
        self._saved_camera: Camera | None = None
        self._output_size = (project.output.width, project.output.height)
        self._saved_output: tuple[int, int] = self._output_size
        self._aspect_locked, self._aspect_ratio = _lock_state(project.output)
        self._saved_lock = (self._aspect_locked, self._aspect_ratio)
        self._applying_output = False
        self.scene_revision = 0
        self.preview_result: tuple[RenderResult, int] | None = None
        self.preview_shown: PreviewRequest | None = None
        self.preview_discarded = 0
        # Preview resolution: a user preference (QSettings), not part of the project.
        self._preview_mode = aspect.DEFAULT_PREVIEW
        self._preview_custom_width = aspect.preview_preset_width(aspect.DEFAULT_PREVIEW)
        self.last_error: tuple[str, str] | None = None
        self.last_render_path: Path | None = None
        self.render_finished_result: RenderResult | None = None
        self.last_export_missing_includes: list[str] = []
        self.last_style_notes: list[str] = []
        self.last_info: tuple[str, str] | None = None
        self.selection: set[AtomId] = set()
        self.selected_bond: BondId | None = None
        self.measurements = measure.MeasurementSession(self.structure)
        self._measure_revealed = False  # the panel opens by itself only once
        self.undo_stack = QUndoStack(self)
        # Lighting Setup window (created on first use) and an uncommitted drag preview.
        self.lighting_setup: LightingSetupWindow | None = None
        self._light_preview: Environment | None = None
        self._lighting_timer = QTimer(self)
        self._lighting_timer.setSingleShot(True)
        self._lighting_timer.setInterval(LIGHTING_SETUP_DELAY_MS)
        self._lighting_timer.timeout.connect(self._update_lighting_setup)

        self.viewport = StructureViewport(self)
        self.setCentralWidget(self.viewport)
        self.scene_panel = ScenePanel(self)
        self.scene_dock = QDockWidget("Scene", self)
        self.scene_dock.setObjectName("scene_dock")
        self.scene_dock.setWidget(self.scene_panel)
        self.scene_dock.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetMovable
            | QDockWidget.DockWidgetFeature.DockWidgetClosable
        )
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.scene_dock)
        self.scene_panel.repetitions_requested.connect(self.set_repetitions)
        self.scene_panel.boundary_requested.connect(self.set_boundary_images)
        self.scene_panel.cell_mode_requested.connect(self.set_cell_mode)
        self.scene_panel.bonds_enabled_requested.connect(self.set_bonds_enabled)
        self.scene_panel.bond_tolerance_requested.connect(self.set_bond_tolerance)
        self.scene_panel.bond_radius_requested.connect(self.set_bond_radius)
        self.scene_panel.bond_pair_requested.connect(self.set_bond_pair)
        self.scene_panel.selected_bond_requested.connect(self.set_selected_bond)
        self.scene_panel.bond_selection_requested.connect(self.set_bond_selection_mode)
        self.scene_panel.remove_bond_requested.connect(self.remove_selected_bond)
        self.scene_panel.remove_equivalent_bonds_requested.connect(self.remove_equivalent_bonds)
        self.scene_panel.radius_scale_requested.connect(self.set_radius_scale)
        self.appearance_panel = AppearancePanel(self)
        self.render_panel = RenderPanel(self)
        self.legend_panel = LegendPanel(self)
        self.polyhedra_panel = PolyhedraPanel(self)
        self.annotation_panel = AnnotationPanel(self)
        self.scene_panel.addTab(self.polyhedra_panel, "Polyhedra")
        self.polyhedra_panel.rules_requested.connect(self.set_polyhedra)
        self.scene_panel.addTab(self.appearance_panel, "Appearance")
        self.scene_panel.addTab(self.legend_panel, "Legend")
        self.scene_panel.addTab(self.annotation_panel, "Text")
        self.scene_panel.addTab(self.render_panel, "Render")
        self.legend_panel.legend_requested.connect(self.set_legend)
        self.legend_panel.fit_requested.connect(lambda: self.viewport.fit())
        self.annotation_panel.annotations_requested.connect(self.set_annotations)
        self.width_spin = self.render_panel.width_spin
        self.height_spin = self.render_panel.height_spin
        panel = self.appearance_panel
        panel.material_requested.connect(self.set_material)
        panel.element_material_requested.connect(
            lambda element, material_id: self.set_element_material(element, material_id or None)
        )
        panel.element_color_requested.connect(self.set_element_color)
        panel.element_radius_requested.connect(self.set_element_radius)
        panel.element_reset_requested.connect(self.reset_element_appearance)
        panel.selection_material_cleared.connect(lambda: self.set_selection_material(None))
        panel.atom_materials_cleared.connect(self.clear_atom_materials)
        panel.gallery_requested.connect(self._open_gallery_from_panel)
        panel.background_requested.connect(self.set_background)
        panel.environment_requested.connect(self.set_environment)
        panel.lighting_requested.connect(self.set_lighting)
        panel.lighting_setup_requested.connect(self.open_lighting_setup)
        panel.image_requested.connect(lambda: self.choose_background_image())
        panel.customize_requested.connect(lambda: self.open_material_editor())
        panel.vectors_requested.connect(lambda: self.open_vector_panel())
        self.material_gallery: PresetGallery | None = None
        self.environment_gallery: PresetGallery | None = None
        self.render_panel.output_requested.connect(self.set_output_size)
        self.render_panel.lock_requested.connect(self.set_aspect_locked)
        self.render_panel.limit_exceeded.connect(
            lambda message: self.statusBar().showMessage(message, 8000)
        )
        self.preview_panel = PreviewPanel(self)
        self.preview_dock = QDockWidget("POV-Ray preview", self)
        self.preview_dock.setObjectName("preview_dock")
        self.preview_dock.setWidget(self.preview_panel)
        self.preview_dock.setFeatures(self.scene_dock.features())
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.preview_dock)
        self.splitDockWidget(self.scene_dock, self.preview_dock, Qt.Orientation.Vertical)
        # Measurements: a bottom dock under the 3D view only (the right docks keep the
        # bottom-right corner), hidden until the first measurement is completed.
        self.measure_panel = MeasurementPanel(self)
        self.measure_dock = QDockWidget("Measurements", self)
        self.measure_dock.setObjectName("measure_dock")
        self.measure_dock.setWidget(self.measure_panel)
        self.measure_dock.setFeatures(self.scene_dock.features())
        self.setCorner(Qt.Corner.BottomRightCorner, Qt.DockWidgetArea.RightDockWidgetArea)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self.measure_dock)
        self.measure_dock.hide()
        self.measure_panel.remove_requested.connect(self.remove_measurements)
        self.measure_panel.clear_requested.connect(self.clear_measurements)
        self._restore_preview_resolution()
        self.preview_panel.resolution_requested.connect(self.set_preview_resolution)
        self.preview_queue = RenderQueue(self)
        self.preview_queue.finished.connect(self._on_preview_finished)
        self.preview_queue.progress.connect(self.preview_panel.set_progress)
        self.preview_queue.started.connect(lambda _tag: self._update_cancel_action())
        self._preview_timer = QTimer(self)
        self._preview_timer.setSingleShot(True)
        self._preview_timer.setInterval(PREVIEW_DELAY_MS)
        self._preview_timer.timeout.connect(self.request_preview)
        self._build_actions()
        self._build_status_bar()
        self.render_panel.sync(*self._output_size, self._aspect_locked, self._aspect_ratio)
        self.viewport.set_output_aspect(self._output_size[0] / self._output_size[1])
        self.boundary_action.setChecked(self.scene_settings.boundary_images)
        self.set_display_geometry(self.geometry)
        self.preview_panel.auto_check.setChecked(
            self.settings.value(SETTINGS_AUTO_PREVIEW, AUTO_PREVIEW_DEFAULT, type=bool)
        )
        self.preview_panel.auto_check.toggled.connect(self._on_auto_preview_toggled)
        self.preview_panel.set_status(
            "Press Preview (F5) for a POV-Ray image of the frame.", "empty"
        )
        self.viewport.camera_changed.connect(self._on_view_changed)
        self.viewport.atom_clicked.connect(self._on_atom_clicked)
        self.viewport.bond_clicked.connect(self._on_bond_clicked)
        self.viewport.supercell_drag_changed.connect(self._on_supercell_drag_changed)
        self.viewport.supercell_drag_finished.connect(self._on_supercell_drag_finished)
        self.viewport.set_handles_visible(self.handles_action.isChecked())
        self.set_rotation_mode("free")
        self.viewport.key_pressed.connect(self.trigger_shortcut)
        self.undo_stack.cleanChanged.connect(self._refresh_title)
        self._update_output_label()
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
            "Render Image…",
            self,
            shortcut=QKeySequence("Ctrl+R"),
            toolTip="Render the current view with POV-Ray as PNG, PDF, or JPEG",
        )
        self.render_action.triggered.connect(lambda: self.export_image())
        self.preview_action = QAction(
            "Preview",
            self,
            shortcut=QKeySequence(Qt.Key.Key_F5),
            toolTip="Render a small POV-Ray image of the framed view (F5)",
        )
        self.preview_action.triggered.connect(lambda: self.request_preview())
        self.cancel_action = QAction(
            "Cancel Render",
            self,
            enabled=False,
            toolTip="Stop the running POV-Ray render (or preview)",
        )
        self.cancel_action.triggered.connect(self.cancel_render)
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
            toolTip="Remove the selected atoms or bond from the figure (Delete).",
        )
        self.hide_action.setShortcuts(
            [QKeySequence(Qt.Key.Key_Delete), QKeySequence(Qt.Key.Key_Backspace)]
        )
        self.hide_action.triggered.connect(self._remove_selection)
        self.select_none_action = QAction(
            "Select None", self, shortcut=QKeySequence(Qt.Key.Key_Escape)
        )
        self.select_none_action.triggered.connect(self.clear_selection)
        self.selection_material_action = QAction(
            "Material for Selection…",
            self,
            shortcut=QKeySequence("Ctrl+M"),
            statusTip="Choose a material for the selected atoms (overrides element and default)",
        )
        self.selection_material_action.triggered.connect(
            lambda: self.open_material_gallery(TARGET_SELECTION)
        )
        self.selection_material_action.setEnabled(False)
        self.measure_distance_action = QAction(
            "Measure Distance",
            self,
            checkable=True,
            toolTip="Distance mode: click two atoms, A and B, to measure their separation "
            "in Å. Click again to leave the mode; Esc cancels an incomplete measurement.",
        )
        self.measure_distance_action.setIconText("Distance")
        self.measure_angle_action = QAction(
            "Measure Bond Angle",
            self,
            checkable=True,
            toolTip="Bond-angle mode: click three atoms, A, B, C, to measure the angle "
            "A–B–C with B as the vertex (0–180°). No bond is needed. Esc cancels.",
        )
        self.measure_angle_action.setIconText("Bond angle")
        self.measure_group = QActionGroup(self)
        self.measure_group.setExclusionPolicy(QActionGroup.ExclusionPolicy.ExclusiveOptional)
        for action, mode in (
            (self.measure_distance_action, "distance"),
            (self.measure_angle_action, "angle"),
        ):
            self.measure_group.addAction(action)
            action.triggered.connect(
                lambda checked, m=mode: self.set_measurement_mode(m if checked else None)
            )
        self.vectors_action = QAction(
            "Vectors…",
            self,
            statusTip="Attach direction or magnetic-moment arrows to atoms",
        )
        self.vectors_action.triggered.connect(lambda: self.open_vector_panel())
        self.customize_material_action = QAction(
            "Customize Material…",
            self,
            statusTip="Adjust the parameters of a material recipe and apply or save the variant",
        )
        self.customize_material_action.triggered.connect(lambda: self.open_material_editor())
        self.material_gallery_action = QAction(
            "Material Gallery…", self, statusTip="Browse materials with POV-Ray thumbnails"
        )
        self.material_gallery_action.triggered.connect(lambda: self.open_material_gallery())
        self.environment_gallery_action = QAction(
            "Environment Gallery…",
            self,
            statusTip="Browse backgrounds, studios, and skies with POV-Ray thumbnails",
        )
        self.environment_gallery_action.triggered.connect(self.open_environment_gallery)
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

        self.export_style_action = QAction(
            "Export Style…",
            self,
            statusTip="Save materials, colours, display settings, environment, and output size",
        )
        self.export_style_action.triggered.connect(lambda: self.export_style())
        self.import_style_action = QAction(
            "Import Style…",
            self,
            statusTip="Apply a saved style to this structure (one undoable step)",
        )
        self.import_style_action.triggered.connect(lambda: self.import_style())
        self.handles_action = QAction(
            "Supercell Handles",
            self,
            checkable=True,
            checked=self.settings.value(SETTINGS_HANDLES, True, type=bool),
            toolTip="Show the a, b, c handles: drag them to add or remove cells",
        )
        self.handles_action.toggled.connect(self._on_handles_toggled)
        self.lighting_setup_action = QAction(
            "Lighting Setup…",
            self,
            toolTip="Show the lights, the output camera, and the structure in 3D; drag the "
            "key light",
        )
        self.lighting_setup_action.triggered.connect(self.open_lighting_setup)
        self.rotate_ccw_action = QAction(
            "Rotate Counter-clockwise",
            self,
            shortcut=QKeySequence("Ctrl+Left"),
            toolTip="Turn the structure about the rotation axis (Ctrl+Left)",
        )
        self.rotate_ccw_action.triggered.connect(lambda: self.rotate_step(+1))
        self.rotate_cw_action = QAction(
            "Rotate Clockwise",
            self,
            shortcut=QKeySequence("Ctrl+Right"),
            toolTip="Turn the structure about the rotation axis (Ctrl+Right)",
        )
        self.rotate_cw_action.triggered.connect(lambda: self.rotate_step(-1))

        file_menu = self.menuBar().addMenu("&File")
        for action in (
            self.open_action,
            self.open_as_action,
            None,
            self.save_action,
            self.save_as_action,
            None,
            self.import_style_action,
            self.export_style_action,
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
        edit_menu.addSeparator()
        edit_menu.addAction(self.measure_distance_action)
        edit_menu.addAction(self.measure_angle_action)
        edit_menu.addAction(self.vectors_action)
        edit_menu.addSeparator()
        edit_menu.addAction(self.selection_material_action)
        edit_menu.addAction(self.material_gallery_action)
        edit_menu.addAction(self.customize_material_action)
        edit_menu.addAction(self.environment_gallery_action)
        view_menu = self.menuBar().addMenu("&View")
        view_menu.addAction(self.fit_action)
        view_menu.addAction(self.reset_view_action)
        along_menu = view_menu.addMenu("View Along")
        self.view_actions: dict[str, QAction] = {}
        for axis, tip in VIEW_AXES.items():
            action = QAction(axis, self, toolTip=f"{tip}; Shift: from the opposite side")
            action.triggered.connect(
                lambda _checked=False, a=axis: self.view_along(
                    a,
                    reverse=bool(
                        QApplication.keyboardModifiers() & Qt.KeyboardModifier.ShiftModifier
                    ),
                )
            )
            self.view_actions[axis] = action
            along_menu.addAction(action)
        view_menu.addAction(self.scene_dock.toggleViewAction())
        view_menu.addAction(self.preview_dock.toggleViewAction())
        view_menu.addAction(self.measure_dock.toggleViewAction())
        view_menu.addAction(self.lighting_setup_action)
        view_menu.addSeparator()
        view_menu.addAction(self.rotate_ccw_action)
        view_menu.addAction(self.rotate_cw_action)
        view_menu.addSeparator()
        view_menu.addAction(self.boundary_action)
        view_menu.addAction(self.show_all_action)
        view_menu.addAction(self.handles_action)
        render_menu = self.menuBar().addMenu("&Render")
        render_menu.addAction(self.preview_action)
        render_menu.addAction(self.render_action)
        render_menu.addAction(self.cancel_action)
        render_menu.addSeparator()
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
        # Short toolbar buttons; the Edit menu items carry the shortcuts and full text.
        self.toolbar_undo = QAction("Undo", self, enabled=False)
        self.toolbar_undo.triggered.connect(self.undo_stack.undo)
        self.toolbar_redo = QAction("Redo", self, enabled=False)
        self.toolbar_redo.triggered.connect(self.undo_stack.redo)
        self.undo_stack.canUndoChanged.connect(self.toolbar_undo.setEnabled)
        self.undo_stack.canRedoChanged.connect(self.toolbar_redo.setEnabled)
        self.undo_stack.undoTextChanged.connect(
            lambda text: self.toolbar_undo.setToolTip(native_keys(f"Undo {text} (Ctrl+Z)"))
        )
        self.undo_stack.redoTextChanged.connect(
            lambda text: self.toolbar_redo.setToolTip(native_keys(f"Redo {text} (Ctrl+Shift+Z)"))
        )
        toolbar.addAction(self.toolbar_undo)
        toolbar.addAction(self.toolbar_redo)
        toolbar.addSeparator()
        toolbar.addAction(self.fit_action)
        toolbar.addSeparator()
        toolbar.addAction(self.preview_action)
        toolbar.addAction(self.render_action)
        toolbar.addAction(self.cancel_action)
        self.output_label = QLabel()
        self.output_label.setToolTip("Output image size (Scene panel ▸ Render)")
        toolbar.addWidget(self.output_label)
        toolbar.addSeparator()
        toolbar.addAction(self.export_action)
        toolbar.addSeparator()
        toolbar.addAction(help_action)

        self.addToolBarBreak()
        view_bar = self.addToolBar("View along")
        view_bar.setObjectName("view_toolbar")
        view_bar.setMovable(False)
        view_bar.addWidget(QLabel(" View along "))
        for axis in "abc":
            view_bar.addAction(self.view_actions[axis])
        view_bar.addSeparator()
        for axis in "xyz":
            view_bar.addAction(self.view_actions[axis])
        view_bar.addSeparator()
        view_bar.addWidget(QLabel(" Rotate "))
        self.rotation_combo = QComboBox()
        self.rotation_combo.setToolTip(
            "Left drag rotates freely, or only about the chosen lattice or Cartesian axis"
        )
        for mode in ROTATION_AXES:
            self.rotation_combo.addItem("freely" if mode == "free" else f"about {mode}", mode)
        self.rotation_combo.currentIndexChanged.connect(
            lambda _i: self.set_rotation_mode(self.rotation_combo.currentData())
        )
        view_bar.addWidget(self.rotation_combo)
        view_bar.addAction(self.rotate_ccw_action)
        view_bar.addAction(self.rotate_cw_action)
        self.rotate_ccw_action.setIconText("⟲")
        self.rotate_cw_action.setIconText("⟳")
        self.step_combo = QComboBox()
        self.step_combo.setToolTip("Angle of the rotate buttons")
        for step in ROTATION_STEPS:
            self.step_combo.addItem(f"{step}°", step)
        self.step_combo.setCurrentIndex(ROTATION_STEPS.index(15))
        view_bar.addWidget(self.step_combo)
        view_bar.addSeparator()
        view_bar.addWidget(QLabel(" Measure "))
        view_bar.addAction(self.measure_distance_action)
        view_bar.addAction(self.measure_angle_action)
        self.render_panel.add_actions(
            [self.preview_action, self.render_action], [self.export_action, self.cancel_action]
        )
        self.preview_panel.set_action(self.preview_action)

    def _build_status_bar(self) -> None:
        bar = self.statusBar()
        self.measure_label = QLabel()
        self.measure_label.setStyleSheet("font-weight: bold")
        self.measure_label.setAccessibleName("Measurement instructions")
        bar.addPermanentWidget(self.measure_label)
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
            self.viewport.set_output_camera(camera)
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
        self.selected_bond = None
        self.boundary_action.setChecked(project.scene.boundary_images)
        self.set_rotation_mode(self.rotation_mode())
        self._output_size = (project.output.width, project.output.height)
        self._aspect_locked, self._aspect_ratio = _lock_state(project.output)
        self.render_panel.sync(*self._output_size, self._aspect_locked, self._aspect_ratio)
        self.viewport.set_output_aspect(self._output_size[0] / self._output_size[1])
        self._update_output_label()
        self.set_display_geometry(build_geometry(self.structure, self.scene_settings))
        if self._camera_initialised:
            if project.camera is None:
                self.reset_view()
            else:
                self.viewport.set_output_camera(project.camera)
            self._mark_clean()
        else:
            self._pending_camera = project.camera
            self._refresh_title()

    def is_modified(self) -> bool:
        """Return whether the scene differs from the last saved or opened state.

        Display-setting, material, and background changes, a different output size,
        and any change of the output camera count as modifications. Resizing the
        window does not: the output camera stays the same.
        """
        if not self.undo_stack.isClean():
            return True
        if self._output_size != self._saved_output:
            return True
        if (self._aspect_locked, self._aspect_ratio) != self._saved_lock:
            return True
        if self._saved_camera is None or not self._camera_initialised:
            return False
        return not _same_camera(self._saved_camera, self.current_camera())

    def _mark_clean(self) -> None:
        self.undo_stack.setClean()
        self._saved_output = self._output_size
        self._saved_lock = (self._aspect_locked, self._aspect_ratio)
        self._saved_camera = self.current_camera() if self._camera_initialised else None
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

    def ask_confirm(self, title: str, text: str) -> bool:
        answer = QMessageBox.question(
            self,
            title,
            text,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return answer == QMessageBox.StandardButton.Yes

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
        self.viewport.set_legend(self.scene_settings.legend)
        self.viewport.set_annotations(self.scene_settings.annotations)
        self.viewport.set_supercell(
            self.structure.cell if self.structure.has_cell else None,
            self.scene_settings.repetitions,
            tuple(self.structure.pbc),
        )
        hidden = f" · {geometry.hidden_count} hidden" if geometry.hidden_count else ""
        a, b, c = self.scene_settings.repetitions
        self.structure_label.setText(
            f"{self.structure.composition()} · {_count(len(geometry), 'atom')}, "
            f"{_count(len(geometry.bonds), 'bond')} shown{hidden} · {a} × {b} × {c} cells"
        )
        self.show_all_action.setEnabled(geometry.hidden_count > 0)
        self.selection = {atom_id for atom_id in self.selection if atom_id in geometry}
        self._update_selection()
        self._check_measurements()
        self._sync_vector_panel()
        self._sync_panel()
        self._sync_appearance()
        self.polyhedra_panel.sync(
            self.scene_settings.polyhedron_rules,
            tuple(dict.fromkeys(self.structure.symbols)),
            len(geometry.polyhedra),
        )
        self._sync_legend_panel()
        self.annotation_panel.sync(self.scene_settings.annotations)
        self._update_lighting_setup()
        self._scene_changed()

    def _sync_legend_panel(self) -> None:
        legend = self.scene_settings.legend
        elements = [entry.element for entry in legend_entries(self.geometry, legend)]
        self.legend_panel.sync(legend, elements, resolved_font_family(""))

    def _sync_appearance(self) -> None:
        settings = self.scene_settings
        overrides = dict(settings.element_colors)
        radius_overrides = dict(settings.element_radii)
        rows, radii = [], {}
        symbols = list(self.structure.symbols)
        for element in dict.fromkeys(symbols):
            z = int(self.structure.numbers[symbols.index(element)])
            rows.append((element, overrides.get(element) or element_color(z), element in overrides))
            radii[element] = (settings.radius_for(element, z), element in radius_overrides)
        self.appearance_panel.sync(settings, self.environment, rows, len(self.selection), radii)
        if self.material_gallery is not None:
            self.material_gallery.set_targets(
                list(dict.fromkeys(self.structure.symbols)), len(self.selection)
            )

    def _sync_panel(self) -> None:
        settings = self.scene_settings
        pairs = summarize_pairs(periodic_bonds(self.structure, settings.bonds))
        self.scene_panel.sync(
            settings,
            pairs,
            len(self.geometry),
            len(self.geometry.bonds),
            self.geometry.hidden_count,
        )

    def apply_scene_settings(
        self,
        settings: SceneSettings,
        environment: Environment | None = None,
        output_size: tuple[int, int] | None = None,
        aspect_ratio: float | None = None,
    ) -> None:
        """Apply settings, environment, and output size (used by undo commands).

        Parameters
        ----------
        settings
            New display settings. A change of repetitions also frames the new block.
        environment
            New environment, or ``None`` to keep the current one.
        output_size
            New output size, or ``None`` to keep the current one.
        aspect_ratio
            New target ratio of the aspect lock, or ``None`` to keep it.

        Notes
        -----
        The geometry is rebuilt from the structure only when settings or environment
        change, and not when only the element legend changes (it is drawn on top).
        """
        refit = settings.repetitions != self.scene_settings.repetitions
        changed = settings != self.scene_settings or (
            environment is not None and environment != self.environment
        )
        overlays_only = (
            changed
            and (environment is None or environment == self.environment)
            and replace(
                settings,
                legend=self.scene_settings.legend,
                annotations=self.scene_settings.annotations,
            )
            == self.scene_settings
        )
        if environment is not None:
            self.environment = environment
        self.scene_settings = settings
        if overlays_only:
            if output_size is not None or aspect_ratio is not None:
                self._apply_output_size(*(output_size or self._output_size), aspect_ratio)
            self.viewport.set_legend(settings.legend)
            self.viewport.set_annotations(settings.annotations)
            self._sync_legend_panel()
            self.annotation_panel.sync(settings.annotations)
            self._scene_changed()
            return
        if output_size is not None or aspect_ratio is not None:
            self._apply_output_size(*(output_size or self._output_size), aspect_ratio)
        if changed:
            self.boundary_action.setChecked(settings.boundary_images)
            self.set_display_geometry(build_geometry(self.structure, settings))
            if refit and self._camera_initialised:
                self.viewport.fit()

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
        if self.measurements.mode is not None:
            if atom_id is not None:  # empty space keeps the picks made so far
                self.pick_measurement_atom(atom_id)
            return
        if toggle:
            if atom_id is not None:
                self.selection ^= {atom_id}
        else:
            self.selection = {atom_id} if atom_id is not None else set()
        self._update_selection()

    def select(self, atom_ids: set[AtomId]) -> None:
        """Replace the selection; IDs that are not displayed are ignored."""
        self.selection = {atom_id for atom_id in atom_ids if atom_id in self.geometry}
        self.selected_bond = None
        self._update_selection()

    def clear_selection(self) -> None:
        """Deselect the current atoms or bond (*Edit ▸ Select None*, Esc).

        During a supercell-handle, axis, or light-handle drag, Esc cancels the drag
        instead.
        """
        if self.viewport.cancel_interaction() or (
            self.lighting_setup is not None and self.lighting_setup.overview.cancel_drag()
        ):
            self.statusBar().showMessage("Drag cancelled", 4000)
            return
        if self.cancel_measurement():
            return
        self.select(set())

    def set_bond_selection_mode(self, enabled: bool) -> None:
        """Switch between selecting displayed atoms and bonds."""
        if enabled and self.measurements.mode is not None:
            self.set_measurement_mode(None)
        self.viewport.bond_selection_mode = enabled
        with QSignalBlocker(self.scene_panel.bond_selection_check):
            self.scene_panel.bond_selection_check.setChecked(enabled)
        self.select(set())

    def _on_bond_clicked(self, index: int) -> None:
        if index < 0:
            self.selected_bond = None
        else:
            a, b = self.geometry.bonds[index]
            self.selected_bond = (self.geometry.atom_ids[a], self.geometry.atom_ids[b])
        self._update_selection()

    def _selected_bond_row(self) -> int | None:
        if self.selected_bond is None:
            return None
        a, b = (self.geometry.index_of(atom) for atom in self.selected_bond)
        if a is None or b is None:
            return None
        rows = np.flatnonzero(np.all(self.geometry.bonds == sorted((a, b)), axis=1))
        return int(rows[0]) if len(rows) else None

    def _remove_selection(self) -> None:
        if self.viewport.bond_selection_mode:
            self.remove_selected_bond()
        else:
            self.hide_selected()

    def remove_selected_bond(self) -> None:
        """Hide the clicked bond as an undoable project change."""
        if self.selected_bond is not None:
            new = self.scene_settings.with_bond_override(*self.selected_bond, False)
            self._push_settings(new, "Remove Selected Bond")

    def remove_equivalent_bonds(self) -> None:
        """Hide the selected bond and its shown symmetry orbit in one undoable edit."""
        if self.selected_bond is None:
            return
        bonds = equivalent_displayed_bonds(self.structure, self.geometry, self.selected_bond)
        overrides = dict(self.scene_settings.bond_overrides)
        overrides.update((bond, False) for bond in bonds)
        settings = replace(self.scene_settings, bond_overrides=tuple(overrides.items()))
        if self._push_settings(settings, "Remove Symmetry-Equivalent Bonds"):
            self.statusBar().showMessage(f"Removed {_count(len(bonds), 'displayed bond')}", 5000)

    # ----- measurements -------------------------------------------------------------
    def measurement_mode(self) -> str | None:
        """Return ``"distance"``, ``"angle"``, or ``None`` (ordinary selection)."""
        return self.measurements.mode

    def set_measurement_mode(self, mode: str | None) -> None:
        """Enter a measurement mode, or leave it with ``None``.

        In a mode, clicks on atoms pick A, B (and C) instead of selecting; camera
        navigation is unchanged. Switching modes cancels an incomplete measurement.
        The ordinary selection is kept.
        """
        if mode is not None and self.viewport.bond_selection_mode:
            self.set_bond_selection_mode(False)
        self.measurements.set_mode(mode)
        self.measure_distance_action.setChecked(mode == "distance")
        self.measure_angle_action.setChecked(mode == "angle")
        self._sync_measurements()

    def pick_measurement_atom(self, atom_id: AtomId) -> measure.Measurement | None:
        """Pick a displayed atom for the current measurement (as a click does).

        Returns
        -------
        Measurement or None
            The completed measurement, or ``None`` while more atoms are needed or when
            the pick was rejected (the status bar explains why).
        """
        try:
            result = self.measurements.pick(atom_id)
        except measure.MeasurementError as exc:
            self.statusBar().showMessage(str(exc), 6000)
            return None
        if result is not None:
            text = measure.measurement_text(self.structure, result)
            self.statusBar().showMessage(text, 10000)
            self.measure_panel.set_note("")
            if not self._measure_revealed:
                self._measure_revealed = True
                self.measure_dock.show()
                self.resizeDocks([self.measure_dock], [150], Qt.Orientation.Vertical)
        self._sync_measurements()
        return result

    def cancel_measurement(self) -> bool:
        """Cancel the incomplete measurement and remove its helpers (Esc).

        Also removes the guide of the measurement just completed. Returns whether
        there was anything to cancel; completed results stay in the table.
        """
        pending = bool(self.measurements.pending)
        if not self.measurements.cancel():
            return False
        if pending:
            self.statusBar().showMessage("Measurement cancelled", 4000)
        self._sync_measurements()
        return True

    def remove_measurements(self, rows: list[int]) -> None:
        """Remove completed measurements by table row."""
        self.measurements.remove(rows)
        self._sync_measurements()

    def clear_measurements(self) -> None:
        """Remove all completed measurements."""
        self.measurements.clear()
        self.measure_panel.set_note("")
        self._sync_measurements()

    def _check_measurements(self) -> None:
        """Drop measurements that no longer refer to displayed atoms of the structure."""
        replaced = self.measurements.structure is not self.structure
        removed, cancelled = self.measurements.invalidate(self.structure, self.geometry)
        notes = []
        if replaced and (removed or cancelled):
            notes.append("Measurements cleared: a different structure was loaded.")
        elif removed:
            notes.append(
                f"Removed {removed} measurement{'s' if removed > 1 else ''}: "
                "an atom is no longer displayed."
            )
        if cancelled and not replaced:
            notes.append("Incomplete measurement cancelled: an atom is no longer displayed.")
        if notes:
            text = " ".join(notes)
            self.measure_panel.set_note(text)
            self.statusBar().showMessage(text, 8000)
        self._sync_measurements()

    def _sync_measurements(self) -> None:
        """Show the session: table rows, viewport helpers, and the instruction."""
        session, structure = self.measurements, self.structure
        rows = []
        for m in session.results:
            letters = measure.LETTERS[: len(m.atoms)]
            atoms = " · ".join(
                f"{letter}{' (vertex)' if m.kind == 'angle' and letter == 'B' else ''}: "
                f"{measure.atom_text(structure, atom_id)}"
                for letter, atom_id in zip(letters, m.atoms, strict=True)
            )
            rows.append(
                MeasurementRow(
                    kind="Distance" if m.kind == "distance" else "Angle",
                    atoms=atoms,
                    result=measure.result_text(m),
                    copy=measure.measurement_text(structure, m),
                    exact=f"{m.value!r} {m.unit}",
                )
            )
        self.measure_panel.set_rows(rows)
        shown = session.pending or (list(session.last.atoms) if session.last else [])
        kind = session.mode or (session.last.kind if session.last else None)
        indices = [self.geometry.index_of(atom_id) for atom_id in shown]
        if shown and all(i is not None for i in indices):
            points = np.array([measure.atom_position(structure, a) for a in shown])
            radii = self.geometry.radii[np.array(indices, dtype=int)]
            self.viewport.set_measurement(points, radii, kind)
        else:
            self.viewport.set_measurement(np.zeros((0, 3)), np.zeros(0), None)
        prompt = session.prompt()
        if prompt and session.last is not None:
            prompt = f"{measure.result_text(session.last)} · next: {prompt}"
        self.measure_label.setText(f"  {prompt}  " if prompt else "")

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
            self._push_settings(replace(self.scene_settings, boundary_images=enabled), text)

    # ----- repetitions, cell edges, bonds (all undoable) -------------------------------
    def _push_settings(self, new: SceneSettings, text: str, merge_key: str = "") -> bool:
        if new == self.scene_settings:
            self._sync_panel()
            return False
        self.undo_stack.push(SceneSettingsCommand(self, new, text, merge_key))
        return True

    def set_repetitions(self, repetitions: tuple[int, int, int]) -> bool:
        """Change displayed cell counts as an undoable step and refit the view.

        Parameters
        ----------
        repetitions
            Counts along a, b, c. Values are converted to integers and clamped to 1 through 20.

        Returns
        -------
        bool
            Whether settings changed. Expansions above 20,000 displayable atoms ask for
            confirmation first; cancellation leaves the scene and panel unchanged.
        """
        a, b, c = (max(1, min(MAX_REPETITIONS, int(r))) for r in repetitions)
        new = replace(self.scene_settings, repetitions=(a, b, c))
        if new == self.scene_settings:
            self._sync_panel()
            return False
        count = count_displayed_atoms(self.structure, new)
        if count > SOFT_LIMIT_ATOMS and not self.ask_confirm(
            "Large Expansion",
            f"{a} × {b} × {c} cells would display {count:,} atoms (more than "
            f"{SOFT_LIMIT_ATOMS:,}). The view may become slow and POV-Ray renders take "
            "longer. Continue?",
        ):
            self._sync_panel()
            return False
        return self._push_settings(new, f"Repetitions {a} × {b} × {c}")

    def set_cell_mode(self, mode: str) -> None:
        """Set all, outline, unit, or none cell-edge mode as an undoable change."""
        if mode == "none":
            new = replace(self.scene_settings, show_cell=False)
        else:
            new = replace(self.scene_settings, show_cell=True, cell_mode=mode)
        self._push_settings(new, "Change Cell Edges")

    def set_bonds_enabled(self, enabled: bool) -> None:
        """Toggle displayed bonds without changing candidate rules or scientific data."""
        bonds = replace(self.scene_settings.bonds, enabled=enabled)
        self._push_settings(
            replace(self.scene_settings, bonds=bonds), "Show Bonds" if enabled else "Hide Bonds"
        )

    def set_bond_tolerance(self, value: float) -> None:
        """Set the covalent-radius distance multiplier; consecutive edits merge in undo."""
        bonds = replace(self.scene_settings.bonds, tolerance=round(float(value), 4))
        self._push_settings(
            replace(self.scene_settings, bonds=bonds),
            "Change Bond Length Tolerance",
            merge_key="bond-tolerance",
        )

    def set_bond_radius(self, value: float) -> None:
        """Set the cylinder radius in Å; consecutive edits merge in undo."""
        bonds = replace(self.scene_settings.bonds, radius=round(float(value), 4))
        self._push_settings(
            replace(self.scene_settings, bonds=bonds), "Change Bond Radius", merge_key="bond-radius"
        )

    def set_bond_pair(self, pair: Pair, enabled: bool) -> None:
        """Override visibility for an element pair, sorting its symbols alphabetically."""
        a, b = sorted(pair)
        bonds = self.scene_settings.bonds.with_pair((a, b), enabled)
        verb = "Show" if enabled else "Hide"
        self._push_settings(replace(self.scene_settings, bonds=bonds), f"{verb} {a}–{b} Bonds")

    def set_selected_bond(self, visible: bool | None) -> None:
        """Set or clear a visibility override for the two selected displayed atoms."""
        if len(self.selection) != 2:
            return
        a, b = sorted(self.selection)
        if visible is True:
            i, j = self.geometry.index_of(a), self.geometry.index_of(b)
            if (
                i is None
                or j is None
                or np.linalg.norm(self.geometry.positions[i] - self.geometry.positions[j]) <= 1e-9
            ):
                return
        new = self.scene_settings.with_bond_override(a, b, visible)
        text = {
            True: "Show Selected Bond",
            False: "Hide Selected Bond",
            None: "Restore Automatic Bond",
        }
        self._push_settings(new, text[visible])

    def set_polyhedra(
        self, rules: tuple[PolyhedronRule, ...], text: str = "Change Polyhedra"
    ) -> None:
        """Apply a project’s coordination rules as one undoable change."""
        self._push_settings(replace(self.scene_settings, polyhedron_rules=rules), text)

    # ----- rotation modes -----------------------------------------------------------------
    def rotation_mode(self) -> str:
        """Return the rotation mode: ``"free"`` or an axis name (a, b, c, x, y, z)."""
        return self.rotation_combo.currentData()

    def rotation_axis_vector(self, mode: str) -> np.ndarray | None:
        """Return the world vector of a rotation mode, or ``None`` for free rotation.

        Lattice axes (a, b, c) need a cell; for a structure without one, ``None``.
        """
        if mode == "free":
            return None
        if mode in "abc":
            if not self.structure.has_cell:
                return None
            return np.asarray(self.structure.cell[" abc".index(mode) - 1], dtype=float)
        return np.eye(3)["xyz".index(mode)]

    def set_rotation_mode(self, mode: str) -> None:
        """Rotate freely with left drag, or only about a lattice or Cartesian axis.

        Parameters
        ----------
        mode
            ``"free"``, ``"a"``, ``"b"``, ``"c"``, ``"x"``, ``"y"``, or ``"z"``. Lattice
            axes fall back to free rotation for a structure without a cell.

        Notes
        -----
        The mode is a navigation setting: it is not saved in projects and not undoable.
        Rotations turn the view (camera); the structure's coordinates never change.
        """
        if mode not in ROTATION_AXES:
            raise ValueError(f"rotation mode must be one of {ROTATION_AXES}")
        for index, name in enumerate(ROTATION_AXES):
            item = self.rotation_combo.model().item(index)
            item.setEnabled(name not in "abc" or name == "free" or self.structure.has_cell)
        vector = self.rotation_axis_vector(mode)
        if vector is None:
            mode = "free"
        self.rotation_combo.blockSignals(True)
        self.rotation_combo.setCurrentIndex(ROTATION_AXES.index(mode))
        self.rotation_combo.blockSignals(False)
        self.viewport.set_rotation_axis(vector)
        about = "the line of sight" if vector is None else f"the {mode} axis"
        for action, sense in (
            (self.rotate_ccw_action, "counter-clockwise"),
            (self.rotate_cw_action, "clockwise"),
        ):
            action.setToolTip(f"Turn the structure {sense} about {about}")

    def rotate_step(self, sign: int) -> None:
        """Turn the structure by the step angle about the rotation axis.

        In free rotation the axis is the line of sight. ``sign`` +1 is counter-clockwise
        (right-handed about the axis), -1 clockwise. A view change, not undoable.
        """
        angle = float(self.step_combo.currentData()) * (1 if sign >= 0 else -1)
        self.viewport.rotate_view(angle, self.rotation_axis_vector(self.rotation_mode()))

    # ----- supercell handles -------------------------------------------------------------
    def _on_handles_toggled(self, visible: bool) -> None:
        self.settings.setValue(SETTINGS_HANDLES, visible)
        self.viewport.set_handles_visible(visible)

    def _on_supercell_drag_changed(self, repetitions: tuple[int, int, int]) -> None:
        a, b, c = repetitions
        trial = replace(self.scene_settings, repetitions=(a, b, c))
        count = count_displayed_atoms(self.structure, trial)
        warning = " (large)" if count > SOFT_LIMIT_ATOMS else ""
        self.viewport.set_drag_label(f" {a} × {b} × {c} cells · {count:,} atoms{warning} ")
        self.statusBar().showMessage(
            f"Release to show {a} × {b} × {c} cells ({count:,} atoms); Esc cancels", 4000
        )

    def _on_supercell_drag_finished(self, repetitions: tuple[int, int, int]) -> None:
        """Apply a handle drag as one undoable repetition change."""
        self.set_repetitions(repetitions)

    # ----- styles -----------------------------------------------------------------------
    def current_style(self) -> Style:
        """Return the style of the current presentation.

        See [`ycrystal.io.style`][ycrystal.io.style].
        """
        return Style.from_state(
            self.structure, self.scene_settings, self.environment, self._output_size
        )

    def export_style(self, path: str | Path | None = None) -> Path | None:
        """Save the current style to a ``.ycstyle`` file (*File ▸ Export Style…*).

        Parameters
        ----------
        path
            Destination; ``None`` asks with a file dialog. The suffix is set to
            ``.ycstyle``.

        Returns
        -------
        pathlib.Path or None
            The written file, or ``None`` if cancelled or writing failed (an error
            message is shown).
        """
        if path is None:
            chosen, _ = QFileDialog.getSaveFileName(
                self,
                "Export Style",
                str(Path(self._last_directory()) / f"{self._output_stem()}{STYLE_SUFFIX}"),
                f"Ycrystal style (*{STYLE_SUFFIX})",
            )
            if not chosen:
                return None
            path = chosen
        path = Path(path)
        if path.suffix.lower() != STYLE_SUFFIX:
            path = path.with_suffix(STYLE_SUFFIX)
        try:
            save_style(path, self.current_style())
        except (OSError, ValueError) as exc:
            self.show_error("Export Style Failed", f"Cannot write {path}: {exc}")
            return None
        self._remember_directory(path)
        self.statusBar().showMessage(f"Style saved to {path}", 8000)
        return path

    def ask_style_import(self, style: Style) -> StyleImportChoice | None:
        """Ask which parts of ``style`` to apply and how to map its elements.

        Returns ``None`` if cancelled. See
        [`StyleImportDialog`][ycrystal.gui.style_dialog.StyleImportDialog].
        """
        dialog = StyleImportDialog(style, self.structure, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return None
        return dialog.choice()

    def import_style(
        self,
        path: str | Path | None = None,
        parts: list[str] | tuple[str, ...] | None = None,
        element_map: dict[str, str | None] | None = None,
    ) -> bool:
        """Apply a style file to this structure as one undoable step (*File ▸ Import Style…*).

        Parameters
        ----------
        path
            Style file; ``None`` asks with a file dialog.
        parts
            Parts to apply (see [`STYLE_PARTS`][ycrystal.io.style.STYLE_PARTS]);
            ``None`` asks with a dialog that offers all of them and the element mapping.
        element_map
            ``{source element: target element or None}`` when `parts` is given (see
            [`resolve_element_map`][ycrystal.io.style.resolve_element_map]); ``None``
            transfers by matching symbols. Ignored when the dialog asks.

        Returns
        -------
        bool
            Whether anything changed. Parts that could not be applied (overrides of
            absent elements, per-atom settings of another structure) are explained in a
            message. The structure's coordinates are never changed; the camera is kept,
            except that new repetitions refit the view.
        """
        if path is None:
            chosen, _ = QFileDialog.getOpenFileName(
                self,
                "Import Style",
                self._last_directory(),
                f"Ycrystal style (*{STYLE_SUFFIX});;All files (*)",
            )
            if not chosen:
                return False
            path = chosen
        path = Path(path)
        try:
            style = load_style(path)
        except StyleError as exc:
            self.show_error("Import Style Failed", str(exc))
            return False
        if parts is None:
            choice = self.ask_style_import(style)
            if choice is None:
                return False
            parts, element_map = choice.parts, choice.element_map
        try:
            result = apply_style(
                style,
                self.structure,
                self.scene_settings,
                self.environment,
                self._output_size,
                tuple(parts),
                element_map,
            )
        except ElementMapError as exc:
            self.show_error("Import Style Failed", f"Element mapping: {exc}")
            return False
        new = result.scene
        count = count_displayed_atoms(self.structure, new)
        if (
            new.repetitions != self.scene_settings.repetitions
            and count > SOFT_LIMIT_ATOMS
            and not self.ask_confirm(
                "Large Expansion",
                f"The style's {' × '.join(map(str, new.repetitions))} cells would display "
                f"{count:,} atoms. Apply them anyway? (No keeps the current repetitions.)",
            )
        ):
            new = replace(new, repetitions=self.scene_settings.repetitions)
        self._remember_directory(path)
        self.last_style_notes = list(result.notes)
        changed = (
            new != self.scene_settings
            or result.environment != self.environment
            or result.output_size != self._output_size
        )
        if changed:
            self.undo_stack.push(
                SceneSettingsCommand(
                    self,
                    new,
                    f"Import Style {path.stem}",
                    environment=result.environment,
                    output_size=result.output_size,
                )
            )
        if result.notes:
            self.show_info("Style Applied with Exceptions", "\n\n".join(result.notes))
        self.statusBar().showMessage(
            f"Style {path.name} applied" if changed else f"Style {path.name}: no changes", 8000
        )
        return changed

    # ----- radii --------------------------------------------------------------------------
    def set_radius_scale(self, scale: float) -> None:
        """Set the atom size (radius ÷ covalent radius) as an undoable step.

        Elements with their own radius keep it. Consecutive changes merge into one step.
        """
        scale = max(0.05, min(3.0, float(scale)))
        self._push_settings(
            replace(self.scene_settings, radius_scale=scale),
            f"Atom Size {scale:.2f}",
            "radius-scale",
        )

    def set_element_radius(self, element: str, radius: float | None) -> None:
        """Set or remove (``None``) the sphere radius of ``element`` in Å (undoable).

        Consecutive changes of the same element merge into one step.
        """
        if radius is not None:
            radius = max(0.02, min(6.0, float(radius)))
            text = f"Radius of {element}: {radius:.2f} Å"
        else:
            text = f"Default Radius for {element}"
        self._push_settings(
            self.scene_settings.with_element_radius(element, radius), text, f"radius:{element}"
        )

    def reset_element_appearance(self, element: str) -> None:
        """Remove the colour and radius overrides of ``element`` as one undoable step."""
        new = self.scene_settings.with_element_color(element, None).with_element_radius(
            element, None
        )
        self._push_settings(new, f"Default Colour and Radius for {element}")

    def view_along(self, axis: str, reverse: bool = False) -> None:
        """Look down a lattice (a, b, c) or Cartesian (x, y, z) axis.

        The axis points toward the viewer (away with ``reverse``); the next axis in
        c, b, a (or z, y, x) order that is not parallel to it points up. The same rule
        as ``ycrystal --view`` ([`axis_view`][ycrystal.core.camera.axis_view]).
        """
        cell = self.structure.cell if self.structure.has_cell else None
        try:
            direction, up = axis_view(axis, cell, reverse)
        except CameraPolicyError:
            return  # a lattice axis of a structure without a cell
        current = self.current_camera()
        camera = Camera.looking_along(
            direction,
            up,
            focal_point=current.focal_point,
            distance=current.distance,
            parallel_scale=current.parallel_scale,
        )
        points, radii = self.geometry.points_and_radii()
        self.viewport.set_output_camera(
            camera.fitted(
                points, radii, self.viewport.output_aspect(), region=self.viewport.fit_region()
            )
        )

    def _update_selection(self) -> None:
        if self.vector_panel is not None:
            self._sync_vector_panel()
        indices = [self.geometry.index_of(atom_id) for atom_id in self.selection]
        self.viewport.set_highlight([i for i in indices if i is not None])
        bond_row = self._selected_bond_row()
        if bond_row is None:
            self.selected_bond = None
        self.viewport.set_bond_highlight(bond_row)
        self.scene_panel.remove_bond_button.setEnabled(bond_row is not None)
        self.scene_panel.remove_equivalent_bonds_button.setEnabled(
            bond_row is not None and self.structure.has_cell and any(self.structure.pbc)
        )
        bond_mode = self.viewport.bond_selection_mode
        self.hide_action.setText("Remove Selected Bond" if bond_mode else "Hide Selected Atoms")
        self.hide_action.setEnabled(bond_row is not None if bond_mode else bool(self.selection))
        self.selection_material_action.setEnabled(bool(self.selection))
        override = None
        if len(self.selection) == 2:
            override = dict(self.scene_settings.bond_overrides).get(tuple(sorted(self.selection)))
        pair_selected = len(self.selection) == 2
        self.scene_panel.sync_selected_bond(
            pair_selected and override is not True,
            pair_selected and override is not False,
            override is not None,
        )
        self._sync_appearance()
        self.selection_label.setText(self.selection_text())

    def selection_text(self) -> str:
        """Return the status-bar description of the selection.

        For one atom: element and label, 1-based atom number, image offset, fractional
        and Cartesian (Å) coordinates, and movable flags if the file had any. For
        several atoms: the number per element.
        """
        if self.selected_bond is not None:
            a, b = self.selected_bond
            distance = np.linalg.norm(
                measure.atom_position(self.structure, a) - measure.atom_position(self.structure, b)
            )
            return (
                f"Selected bond: {self.structure.symbols[a[0]]}–{self.structure.symbols[b[0]]}"
                f" · {distance:.3f} Å"
            )
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
            record = self.scene_settings.vectors.effective(atom_id)
            if record is not None:
                text += f" · vector {record.text()}" + ("" if record.visible else " (hidden)")
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
        """Show the default orientation, fitted into the output frame (*View ▸ Reset View*).

        With an element legend at an edge, the structure is fitted beside it.
        """
        points, radii = self.geometry.points_and_radii()
        camera = default_camera(points, radii, self.viewport.output_aspect())
        region = self.viewport.fit_region()
        if region is not None:
            camera = camera.fitted(points, radii, self.viewport.output_aspect(), region=region)
        self.viewport.set_output_camera(camera)

    def current_camera(self) -> Camera:
        """Return the output camera: the view inside the output frame.

        This camera, together with the output size of
        [`current_render_settings`][ycrystal.gui.main_window.MainWindow.current_render_settings],
        defines the exported and rendered image and is saved in projects.
        """
        return self.viewport.output_camera()

    def current_render_settings(self) -> RenderSettings:
        """Return the output settings for export and final renders.

        Width and height are the output size (Scene panel ▸ Render); the background is
        transparent when the background preset is. Antialiasing is on.
        """
        width, height = self._output_size
        return RenderSettings(
            width=width,
            height=height,
            transparent_background=self.environment.transparent,
            aspect_locked=self._aspect_locked,
            aspect_ratio=self._aspect_ratio,
        )

    def preview_settings(self) -> RenderSettings:
        """Return the settings of POV-Ray previews.

        Same aspect ratio and background as the output; the size comes from the
        preview resolution choice
        ([`preview_size`][ycrystal.gui.main_window.MainWindow.preview_size]) and
        antialiasing is off for speed. The output settings are not affected.
        """
        size = self.preview_size()
        return RenderSettings(
            width=size.width,
            height=size.height,
            antialias=False,
            transparent_background=self.environment.transparent,
        )

    def preview_size(self) -> aspect.PreviewSize:
        """Return the preview size for the resolution choice and the current output.

        See [`preview_size`][ycrystal.core.aspect.preview_size] for the rounding and the
        limits.
        """
        return aspect.preview_size(self._output_size, self.preview_resolution()[1])

    def preview_resolution(self) -> tuple[str, int]:
        """Return the preview resolution choice: ``(mode, requested width in px)``.

        ``mode`` is ``"small"``, ``"medium"``, ``"large"``, or ``"custom"``.
        """
        if self._preview_mode == "custom":
            return "custom", self._preview_custom_width
        return self._preview_mode, aspect.preview_preset_width(self._preview_mode)

    def set_preview_resolution(self, mode: str, width: int | None = None) -> None:
        """Choose the resolution of POV-Ray previews (a preference, not undoable).

        The choice is remembered in `settings`, not in the project, and never changes
        the output size, camera, or scene. With automatic previews on, a new preview
        follows after the usual pause; otherwise the shown preview is marked out of
        date.

        Parameters
        ----------
        mode
            ``"small"`` (480 px wide), ``"medium"`` (800 px), ``"large"`` (1200 px), or
            ``"custom"``.
        width
            Custom width in pixels (used with ``"custom"``; ``None`` keeps the
            remembered custom width).

        Raises
        ------
        ValueError
            For an unknown mode or a custom width outside
            [`MIN_PREVIEW_PIXELS`][ycrystal.core.aspect.MIN_PREVIEW_PIXELS] to
            [`MAX_PREVIEW_PIXELS`][ycrystal.core.aspect.MAX_PREVIEW_PIXELS].
        """
        keys = [key for key, _label, _width in aspect.PREVIEW_PRESETS]
        if mode not in (*keys, "custom"):
            raise ValueError(f"unknown preview resolution {mode!r}")
        custom = self._preview_custom_width
        if mode == "custom" and width is not None:
            custom = int(width)
            if not aspect.MIN_PREVIEW_PIXELS <= custom <= aspect.MAX_PREVIEW_PIXELS:
                self._sync_preview_panel()
                raise ValueError(
                    f"The preview width must be between {aspect.MIN_PREVIEW_PIXELS} and "
                    f"{aspect.MAX_PREVIEW_PIXELS} px."
                )
        before = self.preview_size()
        self._preview_mode, self._preview_custom_width = mode, custom
        self.settings.setValue(SETTINGS_PREVIEW_RESOLUTION, mode)
        if mode == "custom":
            self.settings.setValue(SETTINGS_PREVIEW_WIDTH, custom)
        self._sync_preview_panel()
        if self.preview_size()[:2] != before[:2]:
            self._preview_resolution_changed()

    def _restore_preview_resolution(self) -> None:
        """Read the remembered preview resolution; invalid values give the default."""
        mode = str(self.settings.value(SETTINGS_PREVIEW_RESOLUTION, aspect.DEFAULT_PREVIEW))
        keys = [key for key, _label, _width in aspect.PREVIEW_PRESETS]
        try:
            custom = int(self.settings.value(SETTINGS_PREVIEW_WIDTH, self._preview_custom_width))
        except (TypeError, ValueError):
            custom = self._preview_custom_width
        if not aspect.MIN_PREVIEW_PIXELS <= custom <= aspect.MAX_PREVIEW_PIXELS:
            custom = self._preview_custom_width
        self._preview_mode = mode if mode in (*keys, "custom") else aspect.DEFAULT_PREVIEW
        self._preview_custom_width = custom
        self._sync_preview_panel()

    def _sync_preview_panel(self) -> None:
        self.preview_panel.sync_resolution(
            self._preview_mode, self._preview_custom_width, self.preview_size(), self._output_size
        )

    def _preview_resolution_changed(self) -> None:
        """Mark the shown preview out of date and, if automatic, schedule a new one."""
        auto = self._camera_initialised and self.preview_panel.auto_check.isChecked()
        if self.preview_panel.state == "ready":
            follow = "A new preview follows." if auto else "Press Preview (F5)."
            self.preview_panel.set_status(
                f"Out of date: the preview resolution changed. {follow}", "stale"
            )
        if auto:
            self._preview_timer.start()

    def output_size(self) -> tuple[int, int]:
        """Return the output image ``(width, height)`` in pixels."""
        return self._output_size

    def set_output_size(self, width: int, height: int, ratio: float | None = None) -> None:
        """Set the output image size in pixels as an undoable step; the camera is kept.

        The frame in the 3D view takes the new aspect ratio; the image keeps its centre
        and visible height in Å, so a new resolution at the same ratio keeps the
        composition. Values are clamped to 16–8000 pixels. Consecutive size changes merge
        into one undo step.

        Parameters
        ----------
        width, height
            New size in pixels.
        ratio
            New target ratio of the aspect lock (from the Render panel: kept for edits,
            the preset for presets, inverted for Swap). ``None`` keeps the current
            target if the size matches it, and otherwise takes ``width / height``.
        """
        width, height = (
            max(aspect.MIN_OUTPUT_PIXELS, min(aspect.MAX_OUTPUT_PIXELS, int(v)))
            for v in (width, height)
        )
        if ratio is None:
            keep = aspect.matches_ratio((width, height), self._aspect_ratio)
            ratio = self._aspect_ratio if keep else width / height
        if (width, height) == self._output_size:
            if ratio != self._aspect_ratio:  # e.g. a preset the size already matches
                self._aspect_ratio = ratio
                self._refresh_title()
            self._sync_render_panel()
            return
        self.undo_stack.push(
            SceneSettingsCommand(
                self,
                self.scene_settings,
                f"Output Size {width} × {height}",
                "output-size",
                output_size=(width, height),
                aspect_ratio=ratio,
            )
        )

    def aspect_locked(self) -> bool:
        """Return whether the output aspect ratio is locked (Render panel)."""
        return self._aspect_locked

    def aspect_ratio(self) -> float:
        """Return the target ratio ``width / height`` of the aspect lock."""
        return self._aspect_ratio

    def set_aspect_locked(self, locked: bool) -> None:
        """Lock or unlock the output aspect ratio (the lock button beside Width/Height).

        Locking captures the ratio of the current size; neither dimension changes. The
        lock state is saved in projects (a change marks the project modified) but is not
        an undo step, since it does not change the image.
        """
        self._aspect_locked = bool(locked)
        if self._aspect_locked:
            self._aspect_ratio = self._output_size[0] / self._output_size[1]
        self._sync_render_panel()
        self._refresh_title()
        state = "locked" if locked else "unlocked"
        self.statusBar().showMessage(f"Aspect ratio {state}", 3000)

    def _sync_render_panel(self) -> None:
        self.render_panel.sync(*self._output_size, self._aspect_locked, self._aspect_ratio)

    def _apply_output_size(self, width: int, height: int, ratio: float | None = None) -> None:
        if ratio is None and not aspect.matches_ratio((width, height), self._aspect_ratio):
            ratio = width / height  # e.g. a style import: lock onto the new shape
        if ratio is not None:
            self._aspect_ratio = ratio
        if (width, height) == self._output_size:
            self._sync_render_panel()
            return
        self._output_size = (width, height)
        self._sync_render_panel()
        self._applying_output = True  # the camera notifications below are this one change
        try:
            self.viewport.set_output_aspect(width / height)
        finally:
            self._applying_output = False
        self._update_output_label()
        self._update_lighting_setup()
        self._scene_changed()
        self._refresh_title()

    def _update_output_label(self, *_args: object) -> None:
        width, height = self._output_size
        self.output_label.setText(f"  {width} × {height} px  ")
        self._sync_preview_panel()  # the preview height follows the output shape

    # ----- appearance -----------------------------------------------------------------
    def set_material(self, material_id: str) -> None:
        """Set the default material of atoms and bonds (undoable).

        Element and atom overrides keep precedence over the default.
        """
        material = get_material(material_id)
        self._push_settings(
            replace(self.scene_settings, material=material.id), f"Material: {material.name}"
        )

    def set_element_material(self, element: str, material_id: str | None) -> None:
        """Set or remove (``None``) the material override of ``element`` (undoable)."""
        if material_id is not None:
            name = get_material(material_id).name
            text = f"Material of {element}: {name}"
        else:
            text = f"Default Material for {element}"
        self._push_settings(self.scene_settings.with_element_material(element, material_id), text)

    def set_atom_material(self, atom_ids: set[AtomId], material_id: str | None) -> None:
        """Set or remove (``None``) the material override of displayed atoms (undoable).

        Overrides refer to displayed-atom IDs, like hiding, and take precedence over
        element overrides and the default material.
        """
        if not atom_ids:
            return
        count = len(atom_ids)
        noun = "Atom" if count == 1 else "Atoms"
        if material_id is not None:
            text = f"Material of {count} {noun}: {get_material(material_id).name}"
        else:
            text = f"Default Material for {count} {noun}"
        self._push_settings(self.scene_settings.with_atom_materials(atom_ids, material_id), text)

    def set_selection_material(self, material_id: str | None) -> None:
        """Set or remove the material override of the selected atoms (undoable)."""
        self.set_atom_material(set(self.selection), material_id)

    def clear_atom_materials(self) -> None:
        """Remove every per-atom material override as one undoable step."""
        if self.scene_settings.atom_materials:
            self._push_settings(
                replace(self.scene_settings, atom_materials=()), "Clear Atom Materials"
            )

    def set_element_color(self, element: str, color: tuple[float, float, float] | None) -> None:
        """Set or remove (``None``) the colour override of ``element`` (undoable)."""
        text = f"Colour of {element}" if color is not None else f"Default Colour for {element}"
        self._push_settings(self.scene_settings.with_element_color(element, color), text)

    def set_legend(self, legend: LegendSettings, text: str = "Legend", merge_key: str = "") -> bool:
        """Change the element legend (undoable; same merge keys merge into one step).

        The legend is drawn onto the figure (view, preview, renders, exports); the
        camera is not changed. Returns whether the settings changed.
        """
        new = replace(self.scene_settings, legend=legend)
        if new == self.scene_settings:
            self._sync_legend_panel()
            return False
        self.undo_stack.push(SceneSettingsCommand(self, new, text, merge_key))
        return True

    def set_annotations(
        self, annotations: tuple[TextAnnotation, ...], text: str = "Change Figure Text"
    ) -> None:
        """Change the text in the output frame as an undoable step."""
        self._push_settings(replace(self.scene_settings, annotations=annotations), text)

    def set_background(self, environment_id: str) -> None:
        """Apply environment preset ``environment_id`` (undoable).

        The preset sets the background, the floor, the lighting, the transparency, and a
        cell-edge colour that stays visible on it, as one step.
        """
        preset = get_environment(environment_id)
        # The preset replaces the background type; a chosen picture is remembered (not
        # drawn) so that switching back to the Image type restores it.
        environment = replace(environment_from_preset(preset.id), image=self.environment.image)
        settings = replace(self.scene_settings, cell_edge_color=preset.cell_edge_color)
        if environment == self.environment and settings == self.scene_settings:
            self._sync_appearance()
            return
        self.undo_stack.push(
            SceneSettingsCommand(
                self, settings, f"Environment: {preset.name}", environment=environment
            )
        )

    def choose_background_image(self, path: str | Path | None = None) -> bool:
        """Import a PNG or JPEG picture as background (*Background ▸ Choose Image…*).

        The picture is checked and copied into the session (and into the project when it
        is saved); the background type becomes Image. Replacing a picture keeps the
        framing. One undoable step; an unusable file shows a message and changes nothing.

        Parameters
        ----------
        path
            Picture file; ``None`` shows a file dialog.

        Returns
        -------
        bool
            Whether a picture was applied.
        """
        from ycrystal.io.images import ImageError, import_image

        if path is None:
            path, _ = QFileDialog.getOpenFileName(
                self,
                "Choose Background Image",
                self._last_directory(),
                "Pictures (*.png *.jpg *.jpeg);;All files (*)",
            )
            if not path:
                return False
        path = Path(path)
        try:
            asset = import_image(path)
        except ImageError as exc:
            self.show_error("Cannot Use This Picture", str(exc))
            return False
        self._remember_directory(path)
        old = self.environment.image
        framing = (
            {}
            if old is None
            else {
                "fit": old.fit,
                "zoom": old.zoom,
                "offset_x": old.offset_x,
                "offset_y": old.offset_y,
                "brightness": old.brightness,
            }
        )
        image = asset.reference(**framing)
        self.set_environment(
            replace(self.environment, background_mode="image", image=image),
            "Replace Background Image" if old is not None else "Background Image",
        )
        return True

    def set_environment(self, environment: Environment, text: str, merge_key: str = "") -> None:
        """Apply an edited environment (background, floor, or lights) as an undoable step.

        Consecutive edits with the same non-empty ``merge_key`` (for example dragging a
        light-intensity spin box) merge into one step.
        """
        if environment == self.environment:
            self._sync_appearance()
            return
        self.undo_stack.push(
            SceneSettingsCommand(
                self, self.scene_settings, text, merge_key, environment=environment
            )
        )

    def set_lighting(self, lighting_id: str) -> None:
        """Apply lighting preset ``lighting_id``; background and floor stay (undoable)."""
        light = get_lighting(lighting_id)
        self.set_environment(apply_lighting(self.environment, light.id), f"Lighting: {light.name}")

    # ----- lighting setup (FR-LIGHT-01) ----------------------------------------------------
    def lighting_environment(self) -> Environment:
        """Return the environment whose lights are shown: a drag preview or the current one."""
        return self._light_preview if self._light_preview is not None else self.environment

    def open_lighting_setup(self) -> LightingSetupWindow:
        """Show the Lighting Setup window (*View ▸ Lighting Setup…*), creating it once.

        The window has its own overview camera and only shows the rig resolved from the
        output camera; its graphics never reach the main view, picking, fitting, or
        exports.
        """
        if self.lighting_setup is None:
            setup = LightingSetupWindow(self)
            setup.angle_requested.connect(self._on_light_angle_requested)
            overview = setup.overview
            overview.key_drag_changed.connect(self._on_light_drag_changed)
            overview.key_drag_finished.connect(self._on_light_drag_finished)
            overview.key_drag_cancelled.connect(self._on_light_drag_cancelled)
            setup.addAction(self.undo_action)  # Ctrl+Z and Ctrl+Shift+Z work there too
            setup.addAction(self.redo_action)
            self.lighting_setup = setup
        setup = self.lighting_setup
        setup.show()
        setup.raise_()
        setup.activateWindow()
        self._update_lighting_setup()
        return setup

    def _schedule_lighting_setup(self) -> None:
        """Update the Lighting Setup window soon; camera motion is throttled this way."""
        if (
            self.lighting_setup is not None
            and self.lighting_setup.isVisible()
            and not self._lighting_timer.isActive()
        ):
            self._lighting_timer.start()

    def _update_lighting_setup(self) -> None:
        setup = self.lighting_setup
        if setup is None or not setup.isVisible():
            return
        self._lighting_timer.stop()
        environment = self.lighting_environment()
        camera = self.current_camera()
        rig = resolve_lighting(environment, camera, self.geometry)
        setup.show_rig(
            rig, self.geometry, camera.visible_size(*self._output_size), environment.light_size
        )

    def _on_light_angle_requested(self, field: str, value: float) -> None:
        """Apply a numeric angle edit from the Lighting Setup window (merges like the panel)."""
        new = replace(self.environment, **{field: value})
        if new != self.environment:
            self.set_environment(new, "Light Direction", f"env:{field}")

    def _on_light_drag_changed(self, azimuth: float, elevation: float) -> None:
        """Preview a light-handle drag: live lights, overview, and controls; no undo step."""
        preview = replace(self.environment, key_azimuth=azimuth, key_elevation=elevation)
        self._light_preview = preview
        self.viewport.set_lighting(preview)
        self.appearance_panel.show_key_direction(azimuth, elevation)
        self._update_lighting_setup()
        self.statusBar().showMessage(
            f"Key light: azimuth {azimuth:+.0f}°, elevation {elevation:+.0f}° · release to "
            "apply, Esc cancels",
            4000,
        )

    def _on_light_drag_finished(self, azimuth: float, elevation: float) -> None:
        """Apply a light-handle drag as one undoable step (one preview request)."""
        self._light_preview = None
        new = replace(self.environment, key_azimuth=azimuth, key_elevation=elevation)
        if new == self.environment:
            self._restore_lighting_views()
            return
        self.set_environment(new, "Light Direction (Drag)")

    def _on_light_drag_cancelled(self) -> None:
        """Restore the state from before a cancelled light-handle drag."""
        self._light_preview = None
        self._restore_lighting_views()
        self.statusBar().showMessage("Drag cancelled", 4000)

    def _restore_lighting_views(self) -> None:
        self.viewport.set_lighting(self.environment)
        self.appearance_panel.show_key_direction(
            self.environment.key_azimuth, self.environment.key_elevation
        )
        self._update_lighting_setup()

    def _open_gallery_from_panel(self, which: str) -> None:
        if which == "environments":
            self.open_environment_gallery()
        else:
            self.open_material_gallery(TARGET_SELECTION if which == "selection" else None)

    def open_material_gallery(self, target: str | None = None) -> PresetGallery:
        """Show the material gallery (non-modal) and return it.

        Parameters
        ----------
        target
            Preselected target: ``"default"``, ``"element:<symbol>"``, or
            ``"selection"``; ``None`` keeps the previous one.
        """
        if self.material_gallery is None:
            self.material_gallery = PresetGallery("materials", self.settings, self)
            self.material_gallery.apply_requested.connect(self._apply_gallery_material)
            self.material_gallery.reset_requested.connect(self._reset_gallery_material)
        gallery = self.material_gallery
        gallery.refresh_presets()
        elements = list(dict.fromkeys(self.structure.symbols))
        gallery.set_targets(elements, len(self.selection), target)
        current = self.scene_settings.material
        if gallery.target().startswith("element:"):
            element = gallery.target().split(":", 1)[1]
            current = dict(self.scene_settings.element_materials).get(element, current)
        gallery.select_preset(current)
        gallery.show()
        gallery.raise_()
        return gallery

    # ----- vectors (FR-VECTOR-01) ---------------------------------------------------------
    def open_vector_panel(self) -> VectorPanel:
        """Show the *Vectors* window (non-modal), creating it once, and return it."""
        if self.vector_panel is None:
            panel = VectorPanel(self)
            panel.add_requested.connect(lambda: self.open_vector_editor())
            panel.edit_requested.connect(lambda keys: self.open_vector_editor(keys))
            panel.reverse_requested.connect(self.reverse_vectors)
            panel.remove_requested.connect(self.remove_vectors)
            panel.visibility_requested.connect(self.set_vectors_visible)
            panel.suppress_requested.connect(lambda: self.suppress_vectors())
            panel.rows_selected.connect(self._select_vector_hosts)
            panel.style_requested.connect(self.set_vector_style)
            self.vector_panel = panel
        self._sync_vector_panel()
        self.vector_panel.show()
        self.vector_panel.raise_()
        return self.vector_panel

    def vector_hosts(self) -> dict[Key, list[AtomId]]:
        """Return the displayed atoms each vector row applies to (overrides first)."""
        vectors = self.scene_settings.vectors
        images, sources = dict(vectors.images), dict(vectors.sources)
        hosts: dict[Key, list[AtomId]] = {key: [] for key in vectors.keys()}
        for atom_id in self.geometry.atom_ids:
            if atom_id in images:
                hosts[("image", atom_id)].append(atom_id)
            elif atom_id[0] in sources:
                hosts[("source", atom_id[0])].append(atom_id)
        return hosts

    def _sync_vector_panel(self) -> None:
        if self.vector_panel is None:
            return
        shown = {key: len(atoms) for key, atoms in self.vector_hosts().items()}
        settings = self.scene_settings
        self.vector_panel.sync(
            self.structure, settings.vectors, settings.vector_style, shown, len(self.selection)
        )

    def _select_vector_hosts(self, keys: list) -> None:
        hosts = self.vector_hosts()
        self.select({atom for key in keys for atom in hosts.get(key, [])})

    def _push_vectors(self, vectors: VectorSet, text: str) -> bool:
        return self._push_settings(replace(self.scene_settings, vectors=vectors), text)

    def set_vector(
        self,
        record: VectorRecord,
        atom_ids: set[AtomId] | None = None,
        sources: set[int] | None = None,
        clear_overrides: bool = False,
    ) -> bool:
        """Attach one vector as an undoable step.

        Parameters
        ----------
        record
            The vector (Cartesian components, meaning).
        atom_ids
            Displayed instances that get an image override.
        sources
            Source atoms that get a default for all their periodic images.
        clear_overrides
            Also remove the image overrides of `sources`.

        Returns
        -------
        bool
            Whether anything changed.
        """
        new = self._vector_edit(
            self.scene_settings.vectors, record, atom_ids, sources, clear_overrides
        )
        n = len(atom_ids or ()) + len(sources or ())
        return self._push_vectors(new, f"Set Vector ({n} {'atom' if n == 1 else 'atoms'})")

    @staticmethod
    def _vector_edit(
        vectors: VectorSet,
        record: VectorRecord,
        atom_ids: set[AtomId] | None,
        sources: set[int] | None,
        clear_overrides: bool,
    ) -> VectorSet:
        if sources:
            if clear_overrides:
                vectors = vectors.with_images(vectors.overrides_of(sources), None)
            vectors = vectors.with_sources(sources, record)
        if atom_ids:
            vectors = vectors.with_images(atom_ids, record)
        return vectors

    def reverse_vectors(self, keys: list) -> bool:
        """Negate the components of vector rows (one undoable step)."""
        new = self.scene_settings.vectors.mapped(keys, VectorRecord.reversed)
        return self._push_vectors(new, "Reverse Vectors")

    def remove_vectors(self, keys: list) -> bool:
        """Delete vector rows (one undoable step)."""
        return self._push_vectors(self.scene_settings.vectors.without(keys), "Remove Vectors")

    def set_vectors_visible(self, keys: list, visible: bool) -> bool:
        """Show or hide the arrows of vector rows (one undoable step; data kept)."""
        new = self.scene_settings.vectors.mapped(keys, lambda r: replace(r, visible=visible))
        return self._push_vectors(new, "Show Vectors" if visible else "Hide Vectors")

    def suppress_vectors(self, atom_ids: set[AtomId] | None = None) -> bool:
        """Draw no arrow on displayed instances (default: the selection), as one step."""
        targets = set(self.selection if atom_ids is None else atom_ids)
        if not targets:
            return False
        new = self.scene_settings.vectors.with_images(targets, None, suppress=True)
        return self._push_vectors(new, "Suppress Vectors")

    def set_vector_style(self, style: VectorStyle, text: str, merge_key: str = "") -> bool:
        """Change the arrow appearance (undoable; same merge keys merge into one step)."""
        return self._push_settings(
            replace(self.scene_settings, vector_style=style), text, merge_key
        )

    def open_vector_editor(self, keys: list | None = None) -> VectorEditDialog | None:
        """Show the vector editor (window-modal) for the selection or for table rows.

        The targets are frozen when the editor opens: selecting other atoms while it is
        open changes nothing. While editing, the view and the POV-Ray preview show the
        vector without an undo step; *Apply* is one step, *Cancel* restores.
        """
        vectors = self.scene_settings.vectors
        if keys:
            keys = [k for k in keys if vectors.record(k) is not None]
            if not keys:
                return None
            self._vector_targets = ("keys", tuple(keys))
            record = vectors.record(keys[0])
            scopes = [(f"The chosen rows ({len(keys)})", "keys")]
            overrides = 0
        else:
            atoms = tuple(sorted(self.selection))
            if not atoms:
                self.statusBar().showMessage("Select atoms in the 3D view first.", 5000)
                return None
            sources = sorted({a[0] for a in atoms})
            self._vector_targets = ("selection", atoms)
            record = vectors.effective(atoms[0]) or VectorRecord((0.0, 0.0, 1.0))
            n, m = len(atoms), len(sources)
            scopes = [
                (f"Selected displayed atom{'s' if n != 1 else ''} only ({n})", "images"),
                (f"All periodic images of {'their' if n != 1 else 'its'} source atom"
                 f"{'s' if m != 1 else ''} ({m})", "sources"),
            ]  # fmt: skip
            overrides = len(vectors.overrides_of(sources))
        dialog = VectorEditDialog("Vector", record, scopes, overrides, self)
        dialog.preview_requested.connect(self._preview_vector_edit)
        dialog.applied.connect(self._apply_vector_edit)
        dialog.cancelled.connect(self._end_vector_preview)
        dialog.finished.connect(lambda _r: setattr(self, "vector_editor", None))
        self.vector_editor = dialog
        dialog.open()
        return dialog

    def _edited_vectors(self, edit: tuple) -> VectorSet:
        record, scope, clear = edit
        vectors = self.scene_settings.vectors
        kind, targets = self._vector_targets
        if kind == "keys":  # new components and meaning; each row keeps its visibility
            return vectors.mapped(list(targets), lambda old: replace(record, visible=old.visible))
        if scope == "sources":
            return self._vector_edit(vectors, record, None, {a[0] for a in targets}, clear)
        return self._vector_edit(vectors, record, set(targets), None, False)

    def _preview_vector_edit(self, edit: tuple) -> None:
        preview = replace(self.scene_settings, vectors=self._edited_vectors(edit))
        self._vector_preview = preview != self.scene_settings
        self.set_display_geometry(build_geometry(self.structure, preview))

    def _end_vector_preview(self) -> None:
        if self._vector_preview:
            self._vector_preview = False
            self.set_display_geometry(build_geometry(self.structure, self.scene_settings))

    def _apply_vector_edit(self, edit: tuple) -> None:
        self._end_vector_preview()
        new = self._edited_vectors(edit)
        kind, targets = self._vector_targets
        text = "Edit Vectors" if kind == "keys" else f"Set Vector ({len(targets)} selected)"
        self._push_vectors(new, text)

    # ----- custom materials (FR-MATERIAL-01) ----------------------------------------------
    def open_material_editor(self, target: str | None = None) -> MaterialEditorDialog:
        """Show *Customize Material…* (window-modal) and return the dialog.

        Parameters
        ----------
        target
            ``"default"``, ``"element:<symbol>"``, or ``"selection"``; ``None`` chooses
            the selection if atoms are selected, else the default material.

        Notes
        -----
        The selection is captured when the dialog opens. While editing, the view and the
        POV-Ray preview show the variant without an undo step; *Apply* assigns it as one
        step, *Cancel* restores the previous display.
        """
        settings = self.scene_settings
        self._material_edit_atoms = frozenset(self.selection)
        elements = list(dict.fromkeys(self.structure.symbols))
        targets = [("Default material", TARGET_DEFAULT)]
        current = {TARGET_DEFAULT: settings.material}
        overrides = dict(settings.element_materials)
        for element in elements:
            targets.append((f"Element {element}", f"element:{element}"))
            current[f"element:{element}"] = overrides.get(element, settings.material)
        if self._material_edit_atoms:
            n = len(self._material_edit_atoms)
            targets.append((f"Selected atoms ({n})", TARGET_SELECTION))
            first = min(self._material_edit_atoms)
            index = self.geometry.index_of(first)
            element = self.geometry.elements[index] if index is not None else ""
            current[TARGET_SELECTION] = settings.material_for(first, element)
        if target is None:
            target = TARGET_SELECTION if self._material_edit_atoms else TARGET_DEFAULT
        dialog = MaterialEditorDialog(targets, current, target, self)
        dialog.preview_requested.connect(self._preview_material_edit)
        dialog.applied.connect(self._apply_material_edit)
        dialog.cancelled.connect(self._end_material_preview)
        dialog.saved.connect(self.save_personal_material)
        dialog.finished.connect(lambda _r: setattr(self, "material_editor", None))
        self.material_editor = dialog
        dialog.open()
        return dialog

    def _assigned(self, settings: SceneSettings, target: str, material_id: str) -> SceneSettings:
        if target == TARGET_DEFAULT:
            return replace(settings, material=material_id)
        if target == TARGET_SELECTION:
            return settings.with_atom_materials(self._material_edit_atoms, material_id)
        return settings.with_element_material(target.split(":", 1)[1], material_id)

    def _preview_material_edit(self, target: str, material_id: str) -> None:
        preview = self._assigned(self.scene_settings, target, material_id)
        self._material_preview = preview != self.scene_settings
        self.set_display_geometry(build_geometry(self.structure, preview))

    def _end_material_preview(self) -> None:
        if self._material_preview:
            self._material_preview = False
            self.set_display_geometry(build_geometry(self.structure, self.scene_settings))

    def _apply_material_edit(self, target: str, material_id: str) -> None:
        self._end_material_preview()
        name = get_material(material_id).name
        if target == TARGET_DEFAULT:
            text = f"Material: {name}"
        elif target == TARGET_SELECTION:
            n = len(self._material_edit_atoms)
            text = f"Material of {n} {'atom' if n == 1 else 'atoms'}: {name}"
        else:
            text = f"Material of {target.split(':', 1)[1]}: {name}"
        self._push_settings(self._assigned(self.scene_settings, target, material_id), text)
        self._refresh_material_lists()

    def _refresh_material_lists(self) -> None:
        """Show new custom materials and thumbnails in the panel and the gallery."""
        self.appearance_panel.refresh_materials()
        self._sync_appearance()
        if self.material_gallery is not None:
            self.material_gallery.refresh_presets()

    def save_personal_material(self, definition: object) -> bool:
        """Keep a custom material in the user's settings and render its thumbnail.

        Returns
        -------
        bool
            False if the same definition was already saved.
        """
        added = save_personal_material(self.settings, definition)
        self._refresh_material_lists()
        if added:
            self.statusBar().showMessage(f"Saved {definition.name} in My materials.", 6000)
            self._render_custom_thumbnail(definition.id)
        return added

    def _render_custom_thumbnail(self, material_id: str) -> bool:
        """Render a custom material's gallery thumbnail in the background (if POV-Ray is found)."""
        from ycrystal.render.thumbnails import material_thumbnail_job

        try:
            executable = find_povray(self.configured_povray())
        except PovrayNotFoundError:
            return False  # the gallery shows the base thumbnail with a badge
        job = material_thumbnail_job(material_id)
        process = RenderProcess(job, executable, self)

        def finished(result: RenderResult) -> None:
            try:
                if result.ok and result.image_path is not None:
                    folder = Path(presets_module.CUSTOM_THUMBNAILS)
                    folder.mkdir(parents=True, exist_ok=True)
                    copy_result(result.image_path, folder / f"{material_id}.png")
                    self._refresh_material_lists()
            finally:
                job.cleanup()
                if process in self._thumbnail_renders:
                    self._thumbnail_renders.remove(process)

        process.finished.connect(finished)
        self._thumbnail_renders.append(process)
        process.start()
        return True

    def open_environment_gallery(self) -> PresetGallery:
        """Show the environment gallery (non-modal) and return it."""
        if self.environment_gallery is None:
            self.environment_gallery = PresetGallery("environments", self.settings, self)
            self.environment_gallery.apply_requested.connect(
                lambda preset_id, _target: self.set_background(preset_id)
            )
        self.environment_gallery.select_preset(self.environment.preset)
        self.environment_gallery.show()
        self.environment_gallery.raise_()
        return self.environment_gallery

    def _apply_gallery_material(self, material_id: str, target: str) -> None:
        if target == TARGET_DEFAULT:
            self.set_material(material_id)
        elif target == TARGET_SELECTION:
            self.set_selection_material(material_id)
        elif target.startswith("element:"):
            self.set_element_material(target.split(":", 1)[1], material_id)

    def _reset_gallery_material(self, target: str) -> None:
        if target == TARGET_SELECTION:
            self.set_selection_material(None)
        elif target.startswith("element:"):
            self.set_element_material(target.split(":", 1)[1], None)

    # ----- preview and revisions --------------------------------------------------------
    def _on_view_changed(self) -> None:
        if self._applying_output:
            return  # the size change reports itself once, below
        self._schedule_lighting_setup()
        self._update_output_label()
        self._refresh_title()
        self._scene_changed()

    def _scene_changed(self) -> None:
        """Note a change of the rendered image: new revision, stale preview, auto update."""
        self.scene_revision += 1
        if self.preview_panel.state == "ready":
            self.preview_panel.set_status(
                "Out of date: the view or scene changed. Press Preview (F5).", "stale"
            )
        if self._camera_initialised and self.preview_panel.auto_check.isChecked():
            self._preview_timer.start()

    def _on_auto_preview_toggled(self, enabled: bool) -> None:
        self.settings.setValue(SETTINGS_AUTO_PREVIEW, enabled)
        if enabled:
            self._preview_timer.start()
        else:
            self._preview_timer.stop()

    def request_preview(self) -> bool:
        """Render a small POV-Ray preview of the output frame (*Preview*, F5).

        The job runs in the background through a
        [`RenderQueue`][ycrystal.render.process.RenderQueue]: a running preview is
        cancelled and replaced, and a result made for an older `scene_revision` is
        discarded. No dialog is shown; the preview panel reports problems.

        Returns
        -------
        bool
            Whether a preview job was submitted (``False`` if POV-Ray is not found or
            the view is not ready yet).
        """
        self._preview_timer.stop()
        if not self._camera_initialised:
            return False
        try:
            executable = find_povray(self.configured_povray())
        except PovrayNotFoundError as exc:
            self.preview_panel.set_status(str(exc), "error")
            return False
        settings = self.preview_settings()
        request = PreviewRequest(self.scene_revision, settings.width, settings.height)
        job = prepare_job(
            self.geometry,
            self.current_camera(),
            self.environment,
            settings,
            legend=self.scene_settings.legend,
            annotations=self.scene_settings.annotations,
            title=f"Ycrystal preview: {self.structure.composition()}",
        )
        self.preview_queue.submit(job, executable, request)
        self.preview_panel.set_status(
            f"Rendering preview ({settings.width} × {settings.height} px)…", "busy"
        )
        self._update_cancel_action()
        return True

    def _current_preview_request(self) -> PreviewRequest:
        size = self.preview_size()
        return PreviewRequest(self.scene_revision, size.width, size.height)

    def _on_preview_finished(self, result: RenderResult, request: PreviewRequest) -> None:
        self.preview_result = (result, request.revision)
        self._update_cancel_action()
        if result.cancelled:
            if not self.preview_queue.is_busy():
                self.preview_panel.set_status("Preview cancelled.", "stale")
            return
        if request != self._current_preview_request():
            self.preview_discarded += 1
            if not self.preview_queue.is_busy():
                what = "scene" if request.revision != self.scene_revision else "preview resolution"
                self.preview_panel.set_status(
                    f"The {what} changed during rendering; that preview was discarded. "
                    "Press Preview (F5).",
                    "stale",
                )
            return
        size = f"{request.width} × {request.height} px"
        if result.ok and result.image_path is not None:
            self.preview_panel.set_image(QPixmap(str(result.image_path)))
            self.preview_shown = request
            self.preview_panel.set_status(f"Up to date · {size} · {result.elapsed:.1f} s", "ready")
        else:
            self.preview_panel.set_status(f"Preview failed ({size}). {result.message}", "error")

    def _update_cancel_action(self) -> None:
        final = self._render is not None and self._render.is_running()
        self.cancel_action.setEnabled(final or self.preview_queue.is_busy())

    def cancel_render(self) -> None:
        """Stop the running final render, or else the running preview (*Cancel Render*)."""
        if self._render is not None and self._render.is_running():
            self._render.cancel()
        elif self.preview_queue.is_busy():
            self.preview_queue.cancel()

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
        ``.pov`` file; the ``.ini`` file is replaced without asking. The scene header
        records the POV-Ray version found at export time, if any, and the standard
        include files the materials need. If an include file is not found on this
        computer, an error message says so (the files are still written). A background
        picture is copied next to the scene (``bg_<digest>.png`` or ``.jpg``) and named
        relatively, so the folder can be moved as a whole.
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
            renderer_note=self._renderer_note(),
        )
        message = f"Exported {pov} and {ini.name}"
        env = self.environment
        if (
            env.background_mode == "image"
            and env.image is not None
            and not settings.transparent_background
        ):
            from ycrystal.io.images import asset_filename

            message += (
                f" with the background picture {asset_filename(env.image.asset, env.image.format)}"
            )
        includes = required_includes(self.geometry)
        missing = missing_includes(includes, self.configured_povray())
        if includes:
            message += f" (needs POV-Ray include files: {', '.join(includes)})"
        if self.scene_settings.legend.enabled:
            message += "; the element legend is added to rendered images only, not to the scene"
        if any(label.enabled for label in self.scene_settings.annotations):
            message += "; figure text is added to rendered images only"
        self.last_export_missing_includes = missing
        if missing:
            self.show_error(
                "Include Files Not Found",
                f"The exported scene needs the standard POV-Ray include files "
                f"{', '.join(missing)}, which were not found on this computer. Install them "
                "(Linux Mint/Ubuntu: sudo apt install povray-includes; Homebrew's povray on "
                "macOS contains them) before rendering the scene, or choose materials "
                "without native POV-Ray identifiers.",
            )
        self.statusBar().showMessage(message, 8000)
        return pov

    def _renderer_note(self) -> str | None:
        try:
            executable = find_povray(self.configured_povray())
        except PovrayNotFoundError:
            return "none found when this scene was exported"
        return f"POV-Ray {povray_version(executable) or 'unknown version'} ({executable})"

    def export_image(self) -> bool:
        """Ask for format, size, and file, then render (*Render ▸ Render Image…*, Ctrl+R).

        Shows the [`ExportDialog`][ycrystal.gui.export_dialog.ExportDialog] with the
        last choice of this session (fitted to the current output frame) and starts
        [`render_image`][ycrystal.gui.main_window.MainWindow.render_image].

        Returns
        -------
        bool
            Whether a render started.
        """
        if self._render is not None and self._render.is_running():
            self.statusBar().showMessage("A render is already running.", 5000)
            return False
        answer = self.ask_export()
        if answer is None:
            return False
        destination, options = answer
        self._remember_directory(destination)
        return self.render_image(destination, options)

    def ask_export(self) -> tuple[Path, ExportOptions] | None:
        """Show the Render Image dialog; return ``(destination, options)`` or ``None``."""
        choice = self.export_choice or ExportChoice(
            path=Path(self._last_directory()) / f"{self._output_stem()}.png"
        )
        if choice.path is None:
            choice = replace(choice, path=Path(self._last_directory()) / self._output_stem())
        choice = replace(choice, path=path_for_format(choice.path, choice.format))
        dialog = ExportDialog(
            choice.fitted(self._output_size), self._output_size, self.environment.transparent, self
        )
        accepted = dialog.exec() == QDialog.DialogCode.Accepted
        self.export_choice = dialog.choice()
        options = dialog.options()
        destination = dialog.destination()
        if not accepted or options is None or destination is None:
            return None
        return destination, options

    def render_png(self, path: str | Path | None = None, show_result: bool = True) -> bool:
        """Render the current view as a PNG of the output size (as before Render Image).

        Parameters
        ----------
        path
            Destination PNG; ``None`` shows the Render Image dialog instead
            ([`export_image`][ycrystal.gui.main_window.MainWindow.export_image]). The
            suffix is made ``.png``.
        show_result
            Whether to show the finished image in a dialog.

        Returns
        -------
        bool
            Whether a render started (see
            [`render_image`][ycrystal.gui.main_window.MainWindow.render_image]).
        """
        if path is None:
            return self.export_image()
        width, height = self._output_size
        options = ExportOptions("png", width, height)  # no dpi: the PNG is copied unchanged
        return self.render_image(path_for_format(path, "png"), options, show_result)

    def render_image(
        self, path: str | Path, options: ExportOptions, show_result: bool = True
    ) -> bool:
        """Start a POV-Ray render of the current view and write it as PNG, PDF, or JPEG.

        POV-Ray renders ``options.width × options.height`` pixels with the current
        camera, geometry, and environment; a size of another shape than the output frame
        shows a wider or narrower area at the same scale (never stretched). The scene,
        the Render panel's output size, and the project are not changed.

        After a synchronous version query (up to 15 seconds) and job preparation,
        POV-Ray runs in the background in a temporary job directory. The method
        returns once that process has been requested; the toolbar's Cancel stops it
        and the status bar shows its progress. When it finishes, the image is written
        to the destination by [`write_export`][ycrystal.render.formats.write_export]
        (replacing an existing file only once the new one is complete), the job
        directory is deleted, and the image is shown or an error message explains the
        failure. A cancelled render leaves the destination untouched and shows no error.

        Parameters
        ----------
        path
            Destination file; its suffix is made to match ``options.format``.
        options
            Format, pixel size, resolution, and JPEG quality.
        show_result
            Whether to show the finished image in a dialog.

        Returns
        -------
        bool
            Whether a render started. ``False`` if one is already running or POV-Ray is
            not found (a message explains how to set it up).

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
        destination = path_for_format(path, options.format)
        settings = replace(
            self.current_render_settings(), width=options.width, height=options.height
        )
        version = povray_version(executable)
        job = prepare_job(
            self.geometry,
            self.current_camera(),
            self.environment,
            settings,
            legend=self.scene_settings.legend,
            annotations=self.scene_settings.annotations,
            title=f"Ycrystal scene: {self.structure.composition()}",
            renderer_note=f"POV-Ray {version or 'unknown version'} ({executable})",
        )
        self._render_destination = destination
        self._render_options = options
        self._show_result = show_result
        self._render = RenderProcess(job, executable, self)
        self._render.finished.connect(self._on_render_finished)
        self._render.progress.connect(
            lambda percent: self.statusBar().showMessage(
                f"Rendering {settings.width} × {settings.height} px with POV-Ray… {percent} %"
            )
        )
        self.render_action.setEnabled(False)
        self.statusBar().showMessage(
            f"Rendering {settings.width} × {settings.height} px with POV-Ray…"
        )
        self._render.start()
        self._update_cancel_action()
        return True

    def _on_render_finished(self, result: RenderResult) -> None:
        process = self._render
        self.render_action.setEnabled(True)
        destination = self._render_destination
        options = self._render_options
        try:
            if result.cancelled:
                self.statusBar().showMessage("Render cancelled.", 10000)
            elif (
                result.ok
                and result.image_path is not None
                and destination is not None
                and options is not None
            ):
                try:
                    saved = write_export(
                        result.image_path,
                        destination,
                        options,
                        title=f"Ycrystal: {self.structure.composition()}",
                    )
                except OSError as exc:
                    self.show_error("Could Not Save Image", f"{destination}:\n{exc}")
                    return
                self.last_render_path = saved
                self.statusBar().showMessage(
                    f"Rendered {saved} ({_export_summary(options)})", 10000
                )
                if self._show_result:
                    # A PDF cannot be shown directly: show the rendered image instead.
                    self._result_dialog = RenderResultDialog(saved, self, picture=result.image_path)
                    self._result_dialog.show()
            else:
                self.statusBar().showMessage("Render failed.", 10000)
                self.show_error("Render Failed", result.message)
        finally:
            if process is not None:
                process.job.cleanup()
            self.render_finished_result = result
            self._update_cancel_action()

    def choose_povray(self) -> None:
        """Ask for a POV-Ray executable, store it, and check it.

        The dialog starts at the configured executable, else at the POV-Ray that would
        be used (on Windows, POV-Ray for Windows in its installation folder).
        """
        start = self.configured_povray()
        if not start:
            try:
                start = find_povray()
            except PovrayNotFoundError:
                start = str(Path.home())
        path, _ = QFileDialog.getOpenFileName(
            self, "Select POV-Ray Executable", start, executable_filter()
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

    def show_info(self, title: str, text: str) -> None:
        """Show an information message without blocking the event loop.

        The title and text are also stored in `last_info`.
        """
        self.last_info = (title, text)
        box = QMessageBox(
            QMessageBox.Icon.Information, title, text, QMessageBox.StandardButton.Ok, self
        )
        box.setWindowModality(Qt.WindowModality.WindowModal)
        box.open()
        self._message_box = box

    def show_mouse_help(self) -> None:
        """Show the mouse and keyboard summary (*Help ▸ Mouse Controls*, F1)."""
        QMessageBox.information(self, "Mouse Controls", native_keys(MOUSE_HELP))

    def show_format_help(self) -> None:
        """Show the supported file formats (*Help ▸ Supported File Formats*)."""
        QMessageBox.information(self, "Supported File Formats", SUPPORT_SUMMARY)

    def closeEvent(self, event) -> None:  # noqa: N802, ANN001
        if not self.maybe_save():
            event.ignore()
            return
        if self._render is not None and self._render.is_running():
            self._render.cancel()
        self._preview_timer.stop()
        self._lighting_timer.stop()
        self.preview_queue.cancel()
        for process in list(self._thumbnail_renders):
            process.cancel()
        if self.material_editor is not None:
            self.material_editor.reject()
        if self.lighting_setup is not None:
            self.lighting_setup.close_view()
            self.lighting_setup.close()
        self.viewport.close_viewport()
        super().closeEvent(event)


def _export_summary(options: ExportOptions) -> str:
    """Short description of an export for the status bar."""
    text = f"{format_label(options.format)}, {options.width} × {options.height} px"
    size = options.physical_size_mm()
    if size is not None:
        text += f", {size[0]:.1f} × {size[1]:.1f} mm at {options.dpi:g} dpi"
    return text


def _lock_state(output: RenderSettings) -> tuple[bool, float]:
    """Lock state and target ratio of a project's output (consistent with its size)."""
    ratio = output.target_ratio()
    if not aspect.matches_ratio((output.width, output.height), ratio):
        ratio = output.width / output.height  # stored ratio does not fit the size
    return output.aspect_locked, ratio


def _same_camera(a: Camera, b: Camera) -> bool:
    values_a = np.concatenate([a.position, a.focal_point, a.view_up, [a.parallel_scale]])
    values_b = np.concatenate([b.position, b.focal_point, b.view_up, [b.parallel_scale]])
    return bool(np.allclose(values_a, values_b, rtol=1e-9, atol=1e-9))


def _source_info(structure: Structure) -> dict:
    source = structure.metadata.get("source")
    return source if isinstance(source, dict) else {}


def _count(n: int, noun: str) -> str:
    return f"{n} {noun}{'' if n == 1 else 's'}"
