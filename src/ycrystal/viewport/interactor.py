"""PyVistaQt interactor that draws before ``render()`` returns, on every platform.

``pyvistaqt.QtInteractor.render`` emits a signal whose slot does the drawing. On Linux
and Windows the signal is emitted in the calling thread, so the view is drawn when
``render()`` returns. On macOS PyVistaQt emits it from a helper thread, which queues the
drawing on the Qt event loop: ``render()`` returns first, and pixels, lights, and the
output frame read immediately afterwards still belong to the previous frame.

Ycrystal renders only from the GUI thread and relies on the first behaviour (the
start-of-render observer keeps the output camera, the lights, and the frame overlay in
step with the view), so both viewports use this subclass.
"""

from __future__ import annotations

import os

# Select the Qt binding for qtpy/pyvistaqt before they are imported.
os.environ["QT_API"] = "pyside6"

from pyvistaqt import QtInteractor  # noqa: E402


class SynchronousInteractor(QtInteractor):
    """``QtInteractor`` whose ``render`` draws in the calling (GUI) thread."""

    def render(self) -> None:
        """Draw the view now; do nothing once the interactor is closed.

        Must be called from the GUI thread, like every other widget method.
        """
        if getattr(self, "_closed", False):
            return
        self._rendered = True  # as QtInteractor.render: the plotter has been drawn
        try:
            self.render_signal.emit()
        except RuntimeError:  # the wrapped Qt object has been deleted
            return
