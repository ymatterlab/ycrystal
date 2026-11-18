"""Start the packaged Ycrystal window: ``Ycrystal.exe``, built by PyInstaller without a console.

The program is the same ``ycrystal.app.main`` as the ``ycrystal`` command of an
installation from source. Without a console, VTK would open a window of its own to show
its warnings; that window is turned off here. Use ``ycrystal-cli.exe`` for the command
line (``--render``, ``--check-renderer``), whose messages need a console.
"""

import sys


def _quiet_vtk_warnings() -> None:
    try:
        from vtkmodules.vtkCommonCore import vtkOutputWindow

        vtkOutputWindow.GetInstance().SetDisplayModeToNever()
    except (ImportError, AttributeError):
        pass


if __name__ == "__main__":
    _quiet_vtk_warnings()
    from ycrystal.app import main

    sys.exit(main())
