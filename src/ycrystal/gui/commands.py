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

    The window's current settings, and its environment and output size when
    ``environment`` or ``output_size`` is given, are captured when the command is
    created. ``QUndoStack.push`` applies the new state
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
    output_size
        New output image ``(width, height)`` in pixels, applied in the same step;
        ``None`` leaves it unchanged.
    aspect_ratio
        New target ratio of the Render panel's aspect lock, restored together with the
        output size on undo; ``None`` leaves it unchanged.
    """

    def __init__(
        self,
        window: MainWindow,
        new: SceneSettings,
        text: str,
        merge_key: str = "",
        environment: Environment | None = None,
        output_size: tuple[int, int] | None = None,
        aspect_ratio: float | None = None,
    ) -> None:
        super().__init__(text)
        self._window = window
        self._old = window.scene_settings
        self._new = new
        self._old_environment = window.environment if environment is not None else None
        self._new_environment = environment
        self._old_size = window.output_size() if output_size is not None else None
        self._new_size = output_size
        self._old_ratio = window.aspect_ratio() if aspect_ratio is not None else None
        self._new_ratio = aspect_ratio
        self._merge_key = merge_key

    def id(self) -> int:  # noqa: A003 - Qt API name
        if not self._merge_key:
            return -1
        return zlib.crc32(self._merge_key.encode()) & 0x7FFFFFFF

    def mergeWith(self, other: QUndoCommand) -> bool:  # noqa: N802 - Qt API name
        if not isinstance(other, SceneSettingsCommand) or other._merge_key != self._merge_key:
            return False
        self._new = other._new
        self.setText(other.text())  # the menu names the latest value
        if other._new_environment is not None:
            if self._old_environment is None:
                self._old_environment = other._old_environment
            self._new_environment = other._new_environment
        if other._new_size is not None:
            if self._old_size is None:
                self._old_size = other._old_size
            self._new_size = other._new_size
        if other._new_ratio is not None:
            if self._old_ratio is None:
                self._old_ratio = other._old_ratio
            self._new_ratio = other._new_ratio
        if (
            self._new == self._old
            and self._new_environment == self._old_environment
            and self._new_size == self._old_size
            and self._new_ratio == self._old_ratio
        ):
            self.setObsolete(True)  # merged back to the start: drop the step
        return True

    def redo(self) -> None:
        self._window.apply_scene_settings(
            self._new, self._new_environment, self._new_size, self._new_ratio
        )

    def undo(self) -> None:
        self._window.apply_scene_settings(
            self._old, self._old_environment, self._old_size, self._old_ratio
        )
