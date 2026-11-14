"""Undoable actions."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtGui import QUndoCommand

from ycrystal.core.scene import SceneSettings

if TYPE_CHECKING:
    from ycrystal.gui.main_window import MainWindow


class SceneSettingsCommand(QUndoCommand):
    """Replace the display settings (hidden atoms, boundary policy, …) as one step."""

    def __init__(self, window: MainWindow, new: SceneSettings, text: str) -> None:
        super().__init__(text)
        self._window = window
        self._old = window.scene_settings
        self._new = new

    def redo(self) -> None:
        self._window.apply_scene_settings(self._new)

    def undo(self) -> None:
        self._window.apply_scene_settings(self._old)
