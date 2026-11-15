"""Undoable actions."""

from __future__ import annotations

import zlib
from typing import TYPE_CHECKING

from PySide6.QtGui import QUndoCommand

from ycrystal.core.scene import SceneSettings

if TYPE_CHECKING:
    from ycrystal.gui.main_window import MainWindow


class SceneSettingsCommand(QUndoCommand):
    """Replace the display settings (hidden atoms, repetitions, bonds, …) as one step.

    Commands with the same non-empty ``merge_key`` that follow each other (for example
    repeated steps of the bond-tolerance spin box) merge into a single undo step.
    """

    def __init__(
        self, window: MainWindow, new: SceneSettings, text: str, merge_key: str = ""
    ) -> None:
        super().__init__(text)
        self._window = window
        self._old = window.scene_settings
        self._new = new
        self._merge_key = merge_key

    def id(self) -> int:  # noqa: A003 - Qt API name
        if not self._merge_key:
            return -1
        return zlib.crc32(self._merge_key.encode()) & 0x7FFFFFFF

    def mergeWith(self, other: QUndoCommand) -> bool:  # noqa: N802 - Qt API name
        if not isinstance(other, SceneSettingsCommand) or other._merge_key != self._merge_key:
            return False
        self._new = other._new
        if self._new == self._old:
            self.setObsolete(True)  # merged back to the start: drop the step
        return True

    def redo(self) -> None:
        self._window.apply_scene_settings(self._new)

    def undo(self) -> None:
        self._window.apply_scene_settings(self._old)
