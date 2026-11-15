"""Appearance panel: materials, element colours, background, floor, and lighting.

The panel only emits requests; the main window applies them as undoable steps and calls
[`AppearancePanel.sync`][ycrystal.gui.panels.appearance_panel.AppearancePanel.sync]
with signals blocked.
"""

from __future__ import annotations

from dataclasses import replace

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ycrystal.core.colors import color_label, format_color
from ycrystal.core.lighting import KEY_AZIMUTH_RANGE, KEY_ELEVATION_RANGE
from ycrystal.core.scene import RGB, Environment, SceneSettings
from ycrystal.gui.color_dialog import ColorDialog, color_values
from ycrystal.gui.gallery import preset_icon
from ycrystal.presets import (
    environment_from_preset,
    environments,
    get_environment,
    get_lighting,
    get_material,
    lighting_presets,
    materials,
)

BACKGROUND_MODE_NAMES = {"solid": "Solid colour", "gradient": "Vertical gradient", "sky": "Sky"}
"""Background modes as named in the panel."""


class ColorButton(QPushButton):
    """A button showing a colour; clicking it opens a colour dialog.

    Its tooltip (and accessible name) states the colour in words, for example
    "Colour of O: red (nearest named colour: red #FF0000)", so that colours can be
    identified without relying on colour vision. The dialog is
    [`ColorDialog`][ycrystal.gui.color_dialog.ColorDialog]: typed input in several
    notations and colour names on hover.
    """

    color_chosen = Signal(object)
    """A new colour was chosen, as an sRGB tuple between 0 and 1."""

    def __init__(self, title: str = "Choose Colour", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._title = title
        self._color: RGB = (1.0, 1.0, 1.0)
        self._note = ""
        self.setFixedWidth(56)
        self.setObjectName("colorButton")
        self.clicked.connect(self.choose)
        self.set_color(self._color)

    def color(self) -> RGB:
        """Return the shown colour."""
        return self._color

    def set_color(self, color: RGB) -> None:
        """Show ``color`` without emitting a request."""
        self._color = (float(color[0]), float(color[1]), float(color[2]))
        hex_color = format_color(self._color, "hex")
        # Scoped to this button: an unscoped style sheet would cascade to child widgets.
        self.setStyleSheet(
            f"QPushButton#colorButton {{ background-color: {hex_color}; border: 1px solid #777; }}"
        )
        description = f"{self._title}: {color_label(self._color)}"
        tooltip = f"{description}\n{color_values(self._color)} · click to change"
        if self._note:
            tooltip += f"\n{self._note}"
        self.setToolTip(tooltip)
        self.setAccessibleName(f"{description}. {color_values(self._color)}")

    def set_note(self, note: str) -> None:
        """Add a remark to the tooltip, for example that a material hides the colour."""
        self._note = note
        self.set_color(self._color)

    def choose(self) -> None:
        """Open the colour dialog and emit the chosen colour (nothing if cancelled)."""
        # Parented to the window, not the button, so it keeps the application's look.
        chosen = ColorDialog.get_color(self._color, self.window(), self._title)
        if chosen is not None and chosen != self._color:
            self.color_chosen.emit(chosen)


def _spin(
    minimum: float, maximum: float, step: float, decimals: int, suffix: str = ""
) -> QDoubleSpinBox:
    spin = QDoubleSpinBox()
    spin.setRange(minimum, maximum)
    spin.setSingleStep(step)
    spin.setDecimals(decimals)
    spin.setSuffix(suffix)
    spin.setKeyboardTracking(False)
    return spin


def _narrow_combo() -> QComboBox:
    """Return a combo box that does not widen the dock to its longest entry."""
    combo = QComboBox()
    combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
    combo.setMinimumContentsLength(8)
    return combo


class AppearancePanel(QScrollArea):
    """Materials, element colours, and the environment (background, floor, lighting)."""

    material_requested = Signal(str)
    """Set the default material of all atoms and bonds."""

    element_material_requested = Signal(str, str)
    """Set (material id) or remove (empty string) the material override of an element."""

    element_color_requested = Signal(str, object)
    """Set (sRGB tuple) or remove (``None``) the colour override of an element."""

    element_radius_requested = Signal(str, float)
    """Set the sphere radius (Å) of an element."""

    element_reset_requested = Signal(str)
    """Remove the colour and radius overrides of an element."""

    selection_material_cleared = Signal()
    """Remove the material overrides of the selected atoms."""

    atom_materials_cleared = Signal()
    """Remove all per-atom material overrides."""

    gallery_requested = Signal(str)
    """Open a gallery: ``"materials"``, ``"selection"`` (materials for the selection), or
    ``"environments"``."""

    background_requested = Signal(str)
    """Apply an environment preset (background, floor, lighting, edge colour)."""

    environment_requested = Signal(object, str, str)
    """Apply an edited environment: ``(environment, undo text, merge key)``."""

    lighting_requested = Signal(str)
    """Apply a lighting preset."""

    lighting_setup_requested = Signal()
    """Open the Lighting Setup window."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setFrameShape(QScrollArea.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        body = QWidget()
        self.setWidget(body)
        layout = QVBoxLayout(body)
        self._environment = Environment()
        self._elements: list[str] = []
        self._syncing = False

        # ----- materials ----------------------------------------------------------------
        group = QGroupBox("Materials")
        form = QVBoxLayout(group)
        row = QHBoxLayout()
        row.addWidget(QLabel("Default"))
        self.material_combo = self._material_combo(with_default=False)
        self.material_combo.currentIndexChanged.connect(
            lambda _i: self._emit(self.material_requested, self.material_combo.currentData())
        )
        row.addWidget(self.material_combo, 1)
        gallery = QPushButton("Gallery…")
        gallery.setToolTip("Browse all materials with POV-Ray thumbnails")
        gallery.clicked.connect(lambda: self.gallery_requested.emit("materials"))
        row.addWidget(gallery)
        form.addLayout(row)
        self.element_table = QTableWidget(0, 5)
        self.element_table.setHorizontalHeaderLabels(
            ["Element", "Colour", "Radius", "", "Material"]
        )
        self.element_table.verticalHeader().setVisible(False)
        header = self.element_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self.element_table.setMinimumHeight(110)
        form.addWidget(self.element_table)
        self.selection_label = QLabel()
        form.addWidget(self.selection_label)
        selection_row = QHBoxLayout()
        self.selection_button = QPushButton("Material for Selection…")
        self.selection_button.clicked.connect(lambda: self.gallery_requested.emit("selection"))
        selection_row.addWidget(self.selection_button)
        self.clear_selection_button = QPushButton("Use Default")
        self.clear_selection_button.setToolTip("Remove the material overrides of the selection")
        self.clear_selection_button.clicked.connect(self.selection_material_cleared.emit)
        selection_row.addWidget(self.clear_selection_button)
        form.addLayout(selection_row)
        overrides_row = QHBoxLayout()
        self.overrides_label = QLabel()
        overrides_row.addWidget(self.overrides_label, 1)
        self.clear_atoms_button = QPushButton("Clear All")
        self.clear_atoms_button.setToolTip("Remove every per-atom material override")
        self.clear_atoms_button.clicked.connect(self.atom_materials_cleared.emit)
        overrides_row.addWidget(self.clear_atoms_button)
        form.addLayout(overrides_row)
        precedence = QLabel("Precedence: selected atom > element > default.")
        precedence.setWordWrap(True)
        form.addWidget(precedence)
        layout.addWidget(group)

        # ----- environment preset ---------------------------------------------------------
        group = QGroupBox("Environment")
        box = QVBoxLayout(group)
        row = QHBoxLayout()
        self.background_combo = _narrow_combo()
        for preset in environments():
            self.background_combo.addItem(preset_icon(preset), preset.name, preset.id)
            index = self.background_combo.count() - 1
            self.background_combo.setItemData(
                index, preset.description, Qt.ItemDataRole.ToolTipRole
            )
        self.background_combo.currentIndexChanged.connect(
            lambda _i: self._emit(self.background_requested, self.background_combo.currentData())
        )
        row.addWidget(self.background_combo, 1)
        env_gallery = QPushButton("Gallery…")
        env_gallery.clicked.connect(lambda: self.gallery_requested.emit("environments"))
        row.addWidget(env_gallery)
        box.addLayout(row)
        self.background_note = QLabel()
        self.background_note.setWordWrap(True)
        box.addWidget(self.background_note)
        layout.addWidget(group)

        # ----- background -----------------------------------------------------------------
        group = QGroupBox("Background")
        bform = QFormLayout(group)
        self.mode_combo = QComboBox()
        for mode, name in BACKGROUND_MODE_NAMES.items():
            self.mode_combo.addItem(name, mode)
        self.mode_combo.currentIndexChanged.connect(
            lambda _i: self._edit("Background Type", background_mode=self.mode_combo.currentData())
        )
        bform.addRow("Type", self.mode_combo)
        self.top_button = ColorButton("Background Colour")
        self.top_button.color_chosen.connect(
            lambda c: self._edit("Background Colour", background=c)
        )
        self.top_label = QLabel("Colour")
        bform.addRow(self.top_label, self.top_button)
        self.bottom_button = ColorButton("Bottom Colour")
        self.bottom_button.color_chosen.connect(
            lambda c: self._edit("Background Colour", background_bottom=c)
        )
        self.bottom_label = QLabel("Bottom")
        bform.addRow(self.bottom_label, self.bottom_button)
        self.clouds_spin = _spin(0, 100, 5, 0, " %")
        self.clouds_spin.valueChanged.connect(
            lambda v: self._edit("Clouds", "env:clouds", clouds=v / 100.0)
        )
        bform.addRow("Clouds", self.clouds_spin)
        self.transparent_check = QCheckBox("Transparent PNG background")
        self.transparent_check.setToolTip(
            "Rendered images get an alpha channel; floors and backdrops are left out"
        )
        self.transparent_check.toggled.connect(
            lambda on: self._edit("Transparent Background", transparent=on)
        )
        bform.addRow(self.transparent_check)
        layout.addWidget(group)

        # ----- floor ----------------------------------------------------------------------
        self.floor_group = QGroupBox("Floor")
        self.floor_group.setCheckable(True)
        self.floor_group.toggled.connect(lambda on: self._edit("Floor", floor=on))
        fform = QFormLayout(self.floor_group)
        self.floor_button = ColorButton("Floor Colour")
        self.floor_button.color_chosen.connect(lambda c: self._edit("Floor Colour", floor_color=c))
        fform.addRow("Colour", self.floor_button)
        self.reflection_spin = _spin(0, 100, 5, 0, " %")
        self.reflection_spin.valueChanged.connect(
            lambda v: self._edit(
                "Floor Reflection", "env:floor_reflection", floor_reflection=v / 100
            )
        )
        fform.addRow("Reflection", self.reflection_spin)
        self.offset_spin = _spin(0, 20, 0.1, 2, " Å")
        self.offset_spin.valueChanged.connect(
            lambda v: self._edit("Floor Offset", "env:floor_offset", floor_offset=v)
        )
        fform.addRow("Gap below atoms", self.offset_spin)
        layout.addWidget(self.floor_group)

        # ----- lighting -------------------------------------------------------------------
        group = QGroupBox("Lighting")
        lform = QFormLayout(group)
        self.lighting_combo = _narrow_combo()
        for light in lighting_presets():
            self.lighting_combo.addItem(light.name, light.id)
            index = self.lighting_combo.count() - 1
            self.lighting_combo.setItemData(index, light.description, Qt.ItemDataRole.ToolTipRole)
        self.lighting_combo.currentIndexChanged.connect(
            lambda _i: self._emit(self.lighting_requested, self.lighting_combo.currentData())
        )
        lform.addRow("Preset", self.lighting_combo)
        self.key_spin = _spin(0, 3, 0.05, 2)
        self.key_spin.valueChanged.connect(
            lambda v: self._edit("Key Light", "env:key_light", key_light=v)
        )
        lform.addRow("Key light", self.key_spin)
        self.fill_spin = _spin(0, 3, 0.05, 2)
        self.fill_spin.valueChanged.connect(
            lambda v: self._edit("Fill Light", "env:fill_light", fill_light=v)
        )
        lform.addRow("Fill light", self.fill_spin)
        self.azimuth_spin = _spin(*KEY_AZIMUTH_RANGE, 5, 0, "°")
        self.azimuth_spin.setToolTip(
            "Key-light direction around the output camera's focal point F: 0° points toward "
            "the camera, positive to the right of the image (negative: left), ±180° behind "
            "the structure"
        )
        self.azimuth_spin.valueChanged.connect(
            lambda v: self._edit("Light Direction", "env:key_azimuth", key_azimuth=v)
        )
        lform.addRow("Key azimuth", self.azimuth_spin)
        self.elevation_spin = _spin(*KEY_ELEVATION_RANGE, 5, 0, "°")
        self.elevation_spin.setToolTip(
            "Key-light direction: degrees above the image's horizontal (screen up); the "
            "horizontal turns with the camera"
        )
        self.elevation_spin.valueChanged.connect(
            lambda v: self._edit("Light Direction", "env:key_elevation", key_elevation=v)
        )
        lform.addRow("Key elevation", self.elevation_spin)
        self.size_spin = _spin(0, 5, 0.1, 1, " × scene")
        self.size_spin.setToolTip(
            "Diameter of the key light as a circular area light, in multiples of the scene "
            "radius R (the sphere around the displayed atoms and cell edges); 0 is a point "
            "light with sharp shadows. Area lights soften shadows but slow down transparent "
            "materials."
        )
        self.size_spin.valueChanged.connect(
            lambda v: self._edit("Light Size", "env:light_size", light_size=v)
        )
        lform.addRow("Light size", self.size_spin)
        self.shadows_check = QCheckBox("Shadows")
        self.shadows_check.toggled.connect(lambda on: self._edit("Shadows", shadows=on))
        lform.addRow(self.shadows_check)
        self.reflector_check = QCheckBox("Reflection panel (metals, glass)")
        self.reflector_check.setToolTip(
            "An invisible bright panel near the key light that only shows up in reflections"
        )
        self.reflector_check.toggled.connect(
            lambda on: self._edit("Reflection Panel", reflector=on)
        )
        lform.addRow(self.reflector_check)
        self.lighting_setup_button = QPushButton("Lighting Setup…")
        self.lighting_setup_button.setToolTip(
            "Show the lights, the output camera, and the structure in 3D and drag the key "
            "light's direction"
        )
        self.lighting_setup_button.clicked.connect(self.lighting_setup_requested)
        lform.addRow(self.lighting_setup_button)
        self.lighting_note = QLabel()
        self.lighting_note.setWordWrap(True)
        lform.addRow(self.lighting_note)
        layout.addWidget(group)

        live = QLabel(
            "The 3D view approximates materials, backgrounds, and floors; shadows, "
            "reflections, refraction, clouds, and procedural textures appear only in the "
            "POV-Ray preview (F5) and render."
        )
        live.setWordWrap(True)
        layout.addWidget(live)
        layout.addStretch(1)

    def sizeHint(self) -> QSize:  # noqa: N802 - Qt API name
        """Keep the dock narrow; the panel scrolls vertically."""
        return QSize(260, 400)

    # ----- helpers ----------------------------------------------------------------------
    def _material_combo(self, with_default: bool) -> QComboBox:
        combo = _narrow_combo()
        if with_default:
            combo.addItem("Default", "")
        for material in materials():
            combo.addItem(preset_icon(material), material.name, material.id)
            index = combo.count() - 1
            combo.setItemData(index, material.description, Qt.ItemDataRole.ToolTipRole)
        return combo

    def _emit(self, signal: Signal, *args: object) -> None:
        if not self._syncing:
            signal.emit(*args)

    def _edit(self, text: str, merge_key: str = "", **changes: object) -> None:
        if self._syncing:
            return
        new = replace(self._environment, **changes)
        if new != self._environment:
            self.environment_requested.emit(new, text, merge_key)

    def _rebuild_elements(self, elements: list[str]) -> None:
        self._elements = list(elements)
        table = self.element_table
        table.setRowCount(len(elements))
        for row, element in enumerate(elements):
            label = QLabel(f"  {element}  ")
            table.setCellWidget(row, 0, label)
            button = ColorButton(f"Colour of {element}")
            button.color_chosen.connect(
                lambda c, e=element: self.element_color_requested.emit(e, c)
            )
            table.setCellWidget(row, 1, button)
            radius = _spin(0.02, 6.0, 0.05, 2)
            radius.setToolTip(f"Sphere radius of {element} in Å")
            radius.valueChanged.connect(
                lambda v, e=element: self._emit(self.element_radius_requested, e, v)
            )
            table.setCellWidget(row, 2, radius)
            reset = QToolButton()
            reset.setText("↺")
            reset.setToolTip(f"Use the default colour and radius of {element}")
            reset.clicked.connect(lambda _c=False, e=element: self.element_reset_requested.emit(e))
            table.setCellWidget(row, 3, reset)
            combo = self._material_combo(with_default=True)
            combo.currentIndexChanged.connect(
                lambda _i, e=element, c=combo: self._emit(
                    self.element_material_requested, e, c.currentData()
                )
            )
            table.setCellWidget(row, 4, combo)
        table.resizeRowsToContents()

    # ----- public -----------------------------------------------------------------------
    def element_widgets(self, element: str) -> tuple[ColorButton, QToolButton, QComboBox]:
        """Return the colour button, reset button, and material menu of an element."""
        row = self._elements.index(element)
        table = self.element_table
        return table.cellWidget(row, 1), table.cellWidget(row, 3), table.cellWidget(row, 4)

    def radius_spin(self, element: str) -> QDoubleSpinBox:
        """Return the radius spin box (Å) of an element."""
        return self.element_table.cellWidget(self._elements.index(element), 2)

    def show_key_direction(self, azimuth: float, elevation: float) -> None:
        """Show key-light angles (for example during a drag) without emitting requests."""
        self._syncing = True
        try:
            self.azimuth_spin.setValue(azimuth)
            self.elevation_spin.setValue(elevation)
        finally:
            self._syncing = False

    def sync(
        self,
        settings: SceneSettings,
        environment: Environment,
        element_colors: list[tuple[str, RGB, bool]],
        selection_count: int,
        element_radii: dict[str, tuple[float, bool]] | None = None,
    ) -> None:
        """Show the current appearance without emitting requests.

        Parameters
        ----------
        settings
            Scene settings with the default material and the overrides.
        environment
            Current environment.
        element_colors
            ``(element, shown colour, colour is overridden)`` for every element of the
            structure.
        selection_count
            Number of selected atoms.
        element_radii
            ``element → (radius in Å, radius is overridden)``.
        """
        self._syncing = True
        try:
            self._environment = environment
            self.material_combo.setCurrentIndex(self.material_combo.findData(settings.material))
            elements = [element for element, _, _ in element_colors]
            if elements != self._elements:
                self._rebuild_elements(elements)
            overrides = dict(settings.element_materials)
            for element, color, overridden in element_colors:
                button, reset, combo = self.element_widgets(element)
                button.set_color(color)
                material = get_material(overrides.get(element, settings.material))
                button.set_note(
                    ""
                    if material.keeps_element_color
                    else f"Not visible with the material {material.name}, which has its own "
                    "colours; the colour is kept for other materials."
                )
                radius, radius_set = (element_radii or {}).get(element, (1.0, False))
                spin = self.radius_spin(element)
                spin.blockSignals(True)
                spin.setValue(radius)
                spin.blockSignals(False)
                reset.setEnabled(overridden or radius_set)
                combo.blockSignals(True)
                combo.setCurrentIndex(max(combo.findData(overrides.get(element, "")), 0))
                combo.setItemText(0, f"Default ({get_material(settings.material).name})")
                combo.blockSignals(False)
            noun = "atom" if selection_count == 1 else "atoms"
            self.selection_label.setText(
                f"Selection: {selection_count} {noun}" if selection_count else "Selection: none"
            )
            self.selection_button.setEnabled(selection_count > 0)
            self.clear_selection_button.setEnabled(selection_count > 0)
            n_atoms = len(settings.atom_materials)
            self.overrides_label.setText(
                f"{n_atoms} atom override{'s' if n_atoms != 1 else ''}"
                if n_atoms
                else "No per-atom overrides"
            )
            self.clear_atoms_button.setEnabled(n_atoms > 0)

            env = environment
            self.background_combo.setCurrentIndex(self.background_combo.findData(env.preset))
            preset = get_environment(env.preset)
            modified = env != environment_from_preset(env.preset)
            self.background_note.setText(
                preset.description + (" (Modified below.)" if modified else "")
            )
            self.mode_combo.setCurrentIndex(self.mode_combo.findData(env.background_mode))
            self.top_button.set_color(env.background)
            self.bottom_button.set_color(env.background_bottom)
            self.top_label.setText(
                {"solid": "Colour", "gradient": "Top", "sky": "Zenith"}[env.background_mode]
            )
            self.bottom_label.setText("Horizon" if env.background_mode == "sky" else "Bottom")
            self.bottom_button.setEnabled(env.background_mode != "solid")
            self.bottom_label.setEnabled(env.background_mode != "solid")
            self.clouds_spin.setValue(round(env.clouds * 100))
            self.clouds_spin.setEnabled(env.background_mode == "sky")
            self.transparent_check.setChecked(env.transparent)
            self.floor_group.setChecked(env.floor)
            self.floor_button.set_color(env.floor_color)
            self.reflection_spin.setValue(round(env.floor_reflection * 100))
            self.offset_spin.setValue(env.floor_offset)
            self.lighting_combo.setCurrentIndex(self.lighting_combo.findData(env.lighting))
            self.key_spin.setValue(env.key_light)
            self.fill_spin.setValue(env.fill_light)
            self.azimuth_spin.setValue(env.key_azimuth)
            self.elevation_spin.setValue(env.key_elevation)
            self.size_spin.setValue(env.light_size)
            self.shadows_check.setChecked(env.shadows)
            self.reflector_check.setChecked(env.reflector)
            light = get_lighting(env.lighting)
            custom = (
                env.key_light,
                env.fill_light,
                env.key_azimuth,
                env.key_elevation,
                env.light_size,
                env.shadows,
            ) != (
                light.key_light,
                light.fill_light,
                light.key_azimuth,
                light.key_elevation,
                light.light_size,
                light.shadows,
            )
            self.lighting_note.setText(
                light.description + (" (Adjusted.)" if custom else "")
                if not (env.transparent and env.floor)
                else light.description + " The floor is left out of transparent images."
            )
        finally:
            self._syncing = False
