"""Preset galleries: POV-Ray thumbnails, search, categories, and favourites.

[`PresetGallery`][ycrystal.gui.gallery.PresetGallery] lists either the materials or the
environments. Like the panels, it only emits requests; the main window applies them as
undoable steps.
"""

from __future__ import annotations

from PySide6.QtCore import QSettings, QSize, Qt, Signal
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListView,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ycrystal.presets import (
    ENVIRONMENT_CATEGORIES,
    MATERIAL_CATEGORIES,
    environments,
    materials,
)

ICON_SIZE = 96
"""Displayed thumbnail size in the gallery, in pixels."""

FAVOURITES_KEY = "favourites/{kind}"
"""QSettings key of the favourite preset ids (``kind`` is ``materials`` or
``environments``); favourites belong to the user, not to projects."""

TARGET_DEFAULT = "default"
TARGET_SELECTION = "selection"


def preset_icon(preset: object) -> QIcon:
    """Return the thumbnail of a preset as an icon (empty if the file is missing)."""
    path = preset.thumbnail()
    return QIcon(QPixmap(str(path))) if path is not None else QIcon()


class PresetGallery(QDialog):
    """Gallery of material or environment presets.

    Parameters
    ----------
    kind
        ``"materials"`` or ``"environments"``.
    settings
        Where favourites are stored.
    parent
        Parent widget.

    Notes
    -----
    Typing in the search field filters by name, id, category, description, native
    POV-Ray identifiers, and include files. The category list includes *Favourites*.
    Double-clicking a thumbnail or pressing *Apply* emits
    [`apply_requested`][ycrystal.gui.gallery.PresetGallery.apply_requested]. The
    material gallery also has a target: the default material, one element, or the
    selected atoms; *Use default* removes the override of an element or the selection.
    """

    apply_requested = Signal(str, str)
    """A preset was chosen: ``(preset_id, target)``. Targets are ``"default"``,
    ``"element:<symbol>"``, and ``"selection"`` (always ``"default"`` for
    environments)."""

    reset_requested = Signal(str)
    """Remove the material override of a target (``"element:<symbol>"`` or
    ``"selection"``)."""

    def __init__(self, kind: str, settings: QSettings, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        if kind not in ("materials", "environments"):
            raise ValueError("kind must be 'materials' or 'environments'")
        self.kind = kind
        self.settings = settings
        self._presets = materials() if kind == "materials" else environments()
        categories = MATERIAL_CATEGORIES if kind == "materials" else ENVIRONMENT_CATEGORIES
        self.setWindowTitle("Material Gallery" if kind == "materials" else "Environment Gallery")
        self.resize(760, 620)
        layout = QVBoxLayout(self)

        filters = QHBoxLayout()
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search names, POV-Ray identifiers, descriptions…")
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.textChanged.connect(self._refilter)
        filters.addWidget(self.search_edit, 1)
        self.category_combo = QComboBox()
        self.category_combo.addItem("All categories", "")
        self.category_combo.addItem("★ Favourites", "favourites")
        for key, name in categories.items():
            self.category_combo.addItem(name, key)
        self.category_combo.currentIndexChanged.connect(self._refilter)
        filters.addWidget(self.category_combo)
        layout.addLayout(filters)

        self.list = QListWidget()
        self.list.setViewMode(QListView.ViewMode.IconMode)
        self.list.setIconSize(QSize(ICON_SIZE, ICON_SIZE))
        self.list.setGridSize(QSize(ICON_SIZE + 52, ICON_SIZE + 50))
        self.list.setTextElideMode(Qt.TextElideMode.ElideNone)
        self.list.setResizeMode(QListView.ResizeMode.Adjust)
        self.list.setMovement(QListView.Movement.Static)
        self.list.setWordWrap(True)
        for preset in self._presets:
            item = QListWidgetItem(preset_icon(preset), preset.name)
            item.setData(Qt.ItemDataRole.UserRole, preset.id)
            item.setToolTip(self._details(preset))
            self.list.addItem(item)
        self.list.currentItemChanged.connect(self._on_current_changed)
        self.list.itemDoubleClicked.connect(lambda _item: self._apply())
        layout.addWidget(self.list, 1)

        self.details_label = QLabel()
        self.details_label.setWordWrap(True)
        self.details_label.setTextFormat(Qt.TextFormat.RichText)
        self.details_label.setMinimumHeight(64)
        layout.addWidget(self.details_label)

        row = QHBoxLayout()
        self.favourite_button = QPushButton("☆ Add to favourites")
        self.favourite_button.setCheckable(True)
        self.favourite_button.toggled.connect(self._on_favourite_toggled)
        row.addWidget(self.favourite_button)
        row.addStretch(1)
        self.target_combo = QComboBox()
        self.reset_button = QPushButton("Use default")
        self.reset_button.setToolTip("Remove the material override of this target")
        self.reset_button.clicked.connect(self._reset)
        self.target_combo.currentIndexChanged.connect(self._update_reset)
        if kind == "materials":
            row.addWidget(QLabel("Apply to"))
            row.addWidget(self.target_combo)
            row.addWidget(self.reset_button)
            self.set_targets([], 0)
        layout.addLayout(row)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        self.apply_button = buttons.addButton("Apply", QDialogButtonBox.ButtonRole.ApplyRole)
        self.apply_button.clicked.connect(self._apply)
        buttons.rejected.connect(self.close)
        layout.addWidget(buttons)
        if self.list.count():
            self.list.setCurrentRow(0)
        self._refilter()

    # ----- public ---------------------------------------------------------------------
    def favourites(self) -> list[str]:
        """Return the favourite preset ids of this gallery."""
        value = self.settings.value(FAVOURITES_KEY.format(kind=self.kind), [])
        if isinstance(value, str):
            value = [value] if value else []
        known = {preset.id for preset in self._presets}
        return [v for v in value if v in known]

    def set_favourite(self, preset_id: str, favourite: bool) -> None:
        """Add a preset to the favourites or remove it."""
        ids = [v for v in self.favourites() if v != preset_id]
        if favourite:
            ids.append(preset_id)
        self.settings.setValue(FAVOURITES_KEY.format(kind=self.kind), ids)
        self._refilter()

    def visible_ids(self) -> list[str]:
        """Return the ids of the presets that pass the current search and category."""
        return [
            self.list.item(row).data(Qt.ItemDataRole.UserRole)
            for row in range(self.list.count())
            if not self.list.item(row).isHidden()
        ]

    def current_id(self) -> str | None:
        """Return the id of the highlighted preset, if any."""
        item = self.list.currentItem()
        return None if item is None else item.data(Qt.ItemDataRole.UserRole)

    def select_preset(self, preset_id: str) -> None:
        """Highlight the preset ``preset_id`` (for example the one in use)."""
        for row in range(self.list.count()):
            if self.list.item(row).data(Qt.ItemDataRole.UserRole) == preset_id:
                self.list.setCurrentRow(row)
                return

    def set_targets(
        self, elements: list[str], selection_count: int, current: str | None = None
    ) -> None:
        """Offer the default material, one entry per element, and the selection."""
        previous = current or self.target_combo.currentData() or TARGET_DEFAULT
        self.target_combo.blockSignals(True)
        self.target_combo.clear()
        self.target_combo.addItem("All atoms (default material)", TARGET_DEFAULT)
        for element in elements:
            self.target_combo.addItem(f"Element {element}", f"element:{element}")
        if selection_count:
            noun = "atom" if selection_count == 1 else "atoms"
            self.target_combo.addItem(f"Selected {noun} ({selection_count})", TARGET_SELECTION)
        index = self.target_combo.findData(previous)
        self.target_combo.setCurrentIndex(max(index, 0))
        self.target_combo.blockSignals(False)
        self._update_reset()

    def target(self) -> str:
        """Return the current target (``"default"`` for environments)."""
        return self.target_combo.currentData() or TARGET_DEFAULT

    # ----- internals ------------------------------------------------------------------
    def _details(self, preset: object) -> str:
        parts = [preset.description, f"Category: {preset.category_name}."]
        if self.kind == "materials":
            parts.append(
                "Keeps the element colours."
                if preset.keeps_element_color
                else "Own colours: replaces the element colours."
            )
            if preset.native:
                parts.append("POV-Ray identifier: " + ", ".join(preset.native) + ".")
            if preset.includes:
                parts.append("Needs include files: " + ", ".join(preset.includes) + ".")
        return " ".join(parts)

    def _preset(self, preset_id: str) -> object:
        return next(p for p in self._presets if p.id == preset_id)

    def _refilter(self, *_args: object) -> None:
        query = self.search_edit.text()
        category = self.category_combo.currentData()
        favourites = set(self.favourites())
        for row in range(self.list.count()):
            item = self.list.item(row)
            preset = self._preset(item.data(Qt.ItemDataRole.UserRole))
            visible = preset.matches(query)
            if category == "favourites":
                visible &= preset.id in favourites
            elif category:
                visible &= preset.category == category
            item.setHidden(not visible)
        current = self.list.currentItem()
        if current is None or current.isHidden():
            visible_rows = [r for r in range(self.list.count()) if not self.list.item(r).isHidden()]
            self.list.setCurrentRow(visible_rows[0] if visible_rows else -1)
        self._on_current_changed()

    def _on_current_changed(self, *_args: object) -> None:
        preset_id = self.current_id()
        visible = preset_id is not None and not self.list.currentItem().isHidden()
        self.apply_button.setEnabled(visible)
        self.favourite_button.setEnabled(visible)
        if not visible:
            self.details_label.setText("No preset matches the search.")
            return
        preset = self._preset(preset_id)
        self.details_label.setText(f"<b>{preset.name}</b><br>{self._details(preset)}")
        favourite = preset_id in self.favourites()
        self.favourite_button.blockSignals(True)
        self.favourite_button.setChecked(favourite)
        self.favourite_button.setText("★ Favourite" if favourite else "☆ Add to favourites")
        self.favourite_button.blockSignals(False)

    def _on_favourite_toggled(self, checked: bool) -> None:
        preset_id = self.current_id()
        if preset_id is not None:
            self.set_favourite(preset_id, checked)

    def _apply(self) -> None:
        preset_id = self.current_id()
        if preset_id is not None and not self.list.currentItem().isHidden():
            self.apply_requested.emit(preset_id, self.target())

    def _reset(self) -> None:
        if self.target() != TARGET_DEFAULT:
            self.reset_requested.emit(self.target())

    def _update_reset(self, *_args: object) -> None:
        self.reset_button.setEnabled(self.target() != TARGET_DEFAULT)
