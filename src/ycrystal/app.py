"""Command-line entry point: ``ycrystal``."""

from __future__ import annotations

import argparse
import os
import sys

from ycrystal import __version__
from ycrystal.core.samples import SAMPLES


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ycrystal", description="Crystal-structure figures rendered with POV-Ray."
    )
    parser.add_argument("--version", action="version", version=f"ycrystal {__version__}")
    parser.add_argument(
        "file",
        nargs="?",
        help="structure file (POSCAR/CONTCAR, CIF, QE pw.x input) or .ycrystal project",
    )
    parser.add_argument(
        "--format",
        choices=["poscar", "cif", "qe", "project"],
        help="read FILE in this format instead of detecting it",
    )
    parser.add_argument(
        "--sample",
        choices=sorted(SAMPLES),
        default="perovskite",
        help="synthetic structure shown when no FILE is given",
    )
    parser.add_argument(
        "--check-renderer",
        action="store_true",
        help="render a small reference scene with POV-Ray, verify it, and exit",
    )
    parser.add_argument(
        "--povray",
        metavar="PATH",
        help="POV-Ray executable for --check-renderer and --render "
        "(default: $YCRYSTAL_POVRAY, then PATH)",
    )
    batch = parser.add_argument_group("without a window (FILE required)")
    batch.add_argument(
        "--render",
        metavar="OUT.png",
        help="render FILE (a project as saved, or a structure with default settings) to a "
        "PNG with POV-Ray and exit",
    )
    batch.add_argument(
        "--export-pov",
        metavar="OUT.pov",
        help="write OUT.pov and OUT.ini for FILE and exit (POV-Ray not needed)",
    )
    batch.add_argument("--width", type=int, help="output width in pixels (default: FILE's)")
    batch.add_argument("--height", type=int, help="output height in pixels (default: FILE's)")
    desktop = parser.add_argument_group("desktop integration (Linux, current user)")
    desktop.add_argument(
        "--install-desktop",
        action="store_true",
        help="add Ycrystal to the applications menu and open .ycrystal projects with it",
    )
    desktop.add_argument(
        "--uninstall-desktop",
        action="store_true",
        help="remove the menu entry, icon, and project file type again",
    )
    return parser


def _batch(args: argparse.Namespace) -> int:
    """Run --render / --export-pov; print a result line and return the exit status."""
    import time

    from ycrystal.batch import export_scene, load_input, render_png
    from ycrystal.io.project import ProjectError
    from ycrystal.io.readers import StructureImportError
    from ycrystal.render.povray import PovrayNotFoundError

    for value, name in ((args.width, "--width"), (args.height, "--height")):
        if value is not None and not 16 <= value <= 8000:
            print(f"ERROR: {name} must be between 16 and 8000 pixels", file=sys.stderr)
            return 2
    try:
        project = load_input(args.file, args.format)
    except (ProjectError, StructureImportError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    if args.export_pov:
        try:
            pov, ini = export_scene(project, args.export_pov, args.width, args.height)
        except OSError as exc:
            print(f"ERROR: cannot write {args.export_pov}: {exc.strerror or exc}", file=sys.stderr)
            return 1
        print(f"Exported {pov} and {ini}")
    if args.render:
        started = time.monotonic()
        try:
            result = render_png(project, args.render, args.povray, args.width, args.height)
        except PovrayNotFoundError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1
        except OSError as exc:
            print(f"ERROR: cannot write {args.render}: {exc.strerror or exc}", file=sys.stderr)
            return 1
        if not result.ok:
            print(f"ERROR: {result.message}", file=sys.stderr)
            return 1
        print(f"Rendered {result.image_path} in {time.monotonic() - started:.1f} s")
    return 0


def main(argv: list[str] | None = None) -> int:
    """Run the ``ycrystal`` command.

    Parameters
    ----------
    argv
        Command-line arguments without the program name; ``None`` uses ``sys.argv``.

    Returns
    -------
    int
        Exit status: for ``--check-renderer``, 0 if the renderer passed and 1
        otherwise; else the status of the Qt event loop when the window closes.

    Notes
    -----
    ``--check-renderer`` runs
    [`run_self_test`][ycrystal.render.selftest.run_self_test] with the ``--povray``
    path (if given), prints ``PASS: …`` or ``FAIL: …``, and exits without creating a
    ``QApplication``. It does not read the executable chosen in the GUI.

    ``--render OUT.png`` and ``--export-pov OUT.pov`` work without a window or display:
    they draw ``FILE`` (a project exactly as saved, or a structure with the default
    settings and view) through [`ycrystal.batch`][ycrystal.batch], print one line, and
    return 0, or 1 with an ``ERROR:`` message on standard error (2 for invalid sizes).
    ``--install-desktop`` / ``--uninstall-desktop`` manage the menu launcher on Linux
    (see [`ycrystal.desktop`][ycrystal.desktop]); on macOS and Windows they print an
    error and return 1 without writing anything.

    Otherwise a window opens with the ``--sample`` structure. A ``FILE`` argument is
    opened once the event loop runs; if it cannot be read, a message appears and the
    sample stays open. Settings are stored for the organization "Y-Matter Lab" and the
    application "Ycrystal" (``~/.config/Y-Matter Lab/Ycrystal.conf`` on Linux,
    ``~/Library/Preferences/com.y-matter-lab.Ycrystal.plist`` on macOS).
    """
    parser = _parser()
    args = parser.parse_args(argv)

    if args.install_desktop or args.uninstall_desktop:
        from ycrystal.desktop import desktop_supported, install_desktop, uninstall_desktop

        if not desktop_supported():
            print(
                "ERROR: --install-desktop and --uninstall-desktop manage a Linux menu "
                "launcher and do not apply to this system; start Ycrystal with the "
                "ycrystal command.",
                file=sys.stderr,
            )
            return 1
        if args.install_desktop:
            for path in install_desktop():
                print(f"Installed {path}")
            print("Ycrystal is now in the applications menu (Science).")
        else:
            removed = uninstall_desktop()
            print("\n".join(f"Removed {path}" for path in removed) or "Nothing to remove.")
        return 0

    if args.render or args.export_pov:
        if not args.file:
            parser.error("--render and --export-pov need a FILE")
        return _batch(args)

    if args.check_renderer:
        from ycrystal.render.selftest import run_self_test

        result = run_self_test(args.povray)
        print(("PASS: " if result.ok else "FAIL: ") + result.message)
        return 0 if result.ok else 1

    os.environ["QT_API"] = "pyside6"
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication

    from ycrystal.desktop import DESKTOP_ID, launcher_installed
    from ycrystal.gui.main_window import MainWindow

    if launcher_installed():
        # Before the application object exists, so that the desktop portal gets this id.
        QApplication.setDesktopFileName(DESKTOP_ID)
    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("Ycrystal")
    app.setOrganizationName("Y-Matter Lab")
    app.setApplicationVersion(__version__)
    from PySide6.QtGui import QIcon

    from ycrystal.desktop import icon_path

    app.setWindowIcon(QIcon(str(icon_path())))
    window = MainWindow(SAMPLES[args.sample]())
    window.resize(1100, 720)
    window.show()
    if args.file:
        # After the window has its size and initial camera; failures show a message
        # and keep the sample open.
        QTimer.singleShot(0, lambda: window.open_file(args.file, args.format))
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
