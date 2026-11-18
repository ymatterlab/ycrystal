"""Run the packaged Ycrystal from a terminal: ``ycrystal-cli.exe``, built by PyInstaller.

The same options as the ``ycrystal`` command of an installation from source, for
example ``ycrystal-cli.exe --check-renderer`` or ``ycrystal-cli.exe FILE --render
OUT.png``. Without options it opens the window, like ``Ycrystal.exe``.
"""

import sys

if __name__ == "__main__":
    from ycrystal.app import main

    sys.exit(main())
