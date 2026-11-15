"""Undoable actions."""

from __future__ import annotations

import zlib
from typing import TYPE_CHECKING

from PySide6.QtGui import QUndoCommand

from ycrystal.core.scene import Environment, SceneSettings

if TYPE_CHECKING:
    from ycrystal.gui.main_window import MainWindow


class SceneSettingsCommand(QUndoCommand):
    """Replace the display settings (hidden atoms, material, …) as one step.

    The window's current settings, and its environment when ``environment`` is given,
    are captured when the command is created. ``QUndoStack.push`` applies the new state
    immediately; undo restores the captured one. Each step rebuilds the displayed
    geometry from the unchanged structure.

    Parameters
    ----------
    window
        Window whose settings are replaced.
    new
        Settings to apply.
    text
        Name shown in the Edit menu, for example ``"Hide 2 Atoms"``.
    merge_key
        Consecutive commands with the same non-empty key merge into one undo step.
        Returning to the initial state marks the merged command obsolete.
    environment
        New environment (background) to apply together with the settings, as one
        step; ``None`` leaves the environment unchanged.
    """

    def __init__(
        self,
        window: MainWindow,
        new: SceneSettings,
        text: str,
        merge_key: str = "",
        environment: Environment | None = None,
    ) -> None:
        super().__init__(text)
        self._window = window
        self._old = window.scene_settings
        self._new = new
        self._old_environment = window.environment if environment is not None else None
        self._new_environment = environment
        self._merge_key = merge_key

    def id(self) -> int:  # noqa: A003 - Qt API name
        if not self._merge_key:
            return -1
        return zlib.crc32(self._merge_key.encode()) & 0x7FFFFFFF

    def mergeWith(self, other: QUndoCommand) -> bool:  # noqa: N802 - Qt API name
        if not isinstance(other, SceneSettingsCommand) or other._merge_key != self._merge_key:
            return False
        self._new = other._new
        if other._new_environment is not None:
            if self._old_environment is None:
                self._old_environment = other._old_environment
            self._new_environment = other._new_environment
        if self._new == self._old and self._new_environment == self._old_environment:
            self.setObsolete(True)  # merged back to the start: drop the step
        return True

    def redo(self) -> None:
        self._window.apply_scene_settings(self._new, self._new_environment)

    def undo(self) -> None:
        self._window.apply_scene_settings(self._old, self._old_environment)
