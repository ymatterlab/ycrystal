"""Lighting Setup window: the lighting overview with numeric main-light controls.

The window shows [`LightingOverview`][ycrystal.viewport.lighting_view.LightingOverview]
(the 3D rig with draggable main-light handles), keyboard-accessible azimuth and
elevation spin boxes, and a read-out of the resolved values. It owns no lighting state:
the main window passes the resolved rig in
([`show_rig`][ycrystal.gui.lighting_setup.LightingSetupWindow.show_rig]) and applies the
edits the window requests, through the same undoable path as the Appearance panel.
"""

from __future__ import annotations

from PySide6.QtCore import QSignalBlocker, Qt, Signal
from PySide6.QtWidgets import (
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ycrystal.core.lighting import KEY_AZIMUTH_RANGE, KEY_ELEVATION_RANGE, LightingRig
from ycrystal.core.scene import DisplayGeometry
from ycrystal.viewport.lighting_view import LightingOverview

CONVENTIONS = (
    "Lights are placed relative to the output camera, around its focal point F (the "
    "image centre). Azimuth 0° points from F toward the camera; positive values turn to "
    "the right of the image, ±180° is behind the structure. Elevation is measured above "
    "the image's horizontal. Navigating this overview does not change the image."
)

LEGEND = (
    "Orange sphere: main (key) light · blue cube: fill light (fixed, lower right) · "
    "black cross: F · purple octahedron: C, centre of the displayed geometry · grey "
    "cone: output camera (direction; an orthographic camera's distance does not matter) · "
    "blue rectangle: output frame · flat orange disc: azimuth handle on the horizon ring · "
    "wire sphere: area-light diameter (POV-Ray turns the disc toward each point, so it "
    "acts like a sphere) · white disc: reflection panel."
)

LIMITATIONS = (
    "The live view approximates the main and fill lights. Shadows, area-light softness, "
    "reflections, refraction, and the reflection panel appear only in the POV-Ray "
    "preview."
)


class LightingSetupWindow(QWidget):
    """Top-level window with the lighting overview and main-light angle controls.

    Parameters
    ----------
    parent
        The main window; the setup window stays a separate top-level window.
    """

    angle_requested = Signal(str, float)
    """A numeric edit: (``"key_azimuth"`` or ``"key_elevation"``, value in degrees)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent, Qt.WindowType.Window)
        self.setWindowTitle("Lighting setup — Ycrystal")
        self.setObjectName("lighting_setup")
        self.resize(620, 720)
        layout = QVBoxLayout(self)
        intro = QLabel(CONVENTIONS)
        intro.setWordWrap(True)
        layout.addWidget(intro)
        self.overview = LightingOverview(self)
        self.overview.setMinimumSize(320, 300)
        layout.addWidget(self.overview, 1)

        form = QFormLayout()
        self.azimuth_spin = _angle_spin(*KEY_AZIMUTH_RANGE)
        self.azimuth_spin.setWrapping(True)
        self.azimuth_spin.setAccessibleName("Main light azimuth in degrees")
        self.azimuth_spin.setToolTip(
            "Main-light direction around F: 0° points toward the output camera, positive "
            "to the right of the image, ±180° behind the structure"
        )
        self.elevation_spin = _angle_spin(*KEY_ELEVATION_RANGE)
        self.elevation_spin.setAccessibleName("Main light elevation in degrees")
        self.elevation_spin.setToolTip(
            "Main-light direction: degrees above the image's horizontal (−30° to 89°)"
        )
        self.azimuth_spin.valueChanged.connect(
            lambda v: self.angle_requested.emit("key_azimuth", v)
        )
        self.elevation_spin.valueChanged.connect(
            lambda v: self.angle_requested.emit("key_elevation", v)
        )
        row = QHBoxLayout()
        row.addWidget(self.azimuth_spin)
        row.addWidget(QLabel("Elevation"))
        row.addWidget(self.elevation_spin)
        self.reset_button = QPushButton("Reset Overview")
        self.reset_button.setToolTip("Fit the overview again (the image does not change)")
        self.reset_button.clicked.connect(self.overview.reset_view)
        row.addStretch(1)
        row.addWidget(self.reset_button)
        form.addRow("Main azimuth", row)
        self.main_label = QLabel()
        self.fill_label = QLabel()
        self.scale_label = QLabel()
        for label in (self.main_label, self.fill_label, self.scale_label):
            label.setWordWrap(True)
            label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        form.addRow("Main light", self.main_label)
        form.addRow("Fill light", self.fill_label)
        form.addRow("Placement", self.scale_label)
        layout.addLayout(form)
        for text in (LEGEND, LIMITATIONS):
            label = QLabel(text)
            label.setWordWrap(True)
            layout.addWidget(label)

    def show_rig(
        self,
        rig: LightingRig,
        geometry: DisplayGeometry,
        frame_size: tuple[float, float] | None,
        light_size: float,
    ) -> None:
        """Show a resolved rig, its geometry, and the read-out values.

        Parameters
        ----------
        rig
            Rig resolved from the output camera.
        geometry
            Displayed geometry (drawn lightweight; unchanged geometry is not redrawn).
        frame_size
            Visible output width and height in Å.
        light_size
            The environment's light size (multiples of the scene radius).
        """
        self.overview.set_geometry(geometry)
        self.overview.set_rig(rig, frame_size)
        self.show_angles(rig.azimuth, rig.elevation)
        key, fill = rig.key, rig.fill
        if key.is_area:
            shape = (
                f"circular area light, diameter {key.area_size:.2f} Å "
                f"({light_size:g} × R), 5 × 5 adaptive samples"
            )
        else:
            shape = "point light"
        self.main_label.setText(
            f"{_level(key.intensity)} · {shape} · shadows {'on' if key.shadows else 'off'}"
        )
        self.fill_label.setText(
            f"{_level(fill.intensity)} · fixed at azimuth +35°, elevation −11.6° · shadowless"
        )
        panel = "on" if rig.panel is not None else "off"
        self.scale_label.setText(
            f"distance D = {rig.distance:.2f} Å from F (4 R + |C − F| + 10 Å) · "
            f"R = {rig.radius:.2f} Å · |C − F| = "
            f"{float(((rig.center - rig.origin) ** 2).sum() ** 0.5):.2f} Å · "
            f"reflection panel {panel}"
        )

    def show_angles(self, azimuth: float, elevation: float) -> None:
        """Show main-light angles in the spin boxes without emitting requests."""
        with QSignalBlocker(self.azimuth_spin), QSignalBlocker(self.elevation_spin):
            self.azimuth_spin.setValue(azimuth)
            self.elevation_spin.setValue(elevation)

    def close_view(self) -> None:
        """Release the overview's render window (before the window is discarded)."""
        self.overview.close_view()


def _angle_spin(minimum: float, maximum: float) -> QDoubleSpinBox:
    spin = QDoubleSpinBox()
    spin.setRange(minimum, maximum)
    spin.setSingleStep(5)
    spin.setDecimals(0)
    spin.setSuffix("°")
    spin.setKeyboardTracking(False)
    return spin


def _level(intensity: float) -> str:
    return f"intensity {intensity:.2f}" if intensity > 0 else "off (intensity 0)"
