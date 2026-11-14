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
        "file", nargs="?",
        help="structure file (POSCAR/CONTCAR, CIF, QE pw.x input) or .ycrystal project",
    )
    parser.add_argument(
        "--format", choices=["poscar", "cif", "qe", "project"],
        help="read FILE in this format instead of detecting it",
    )
    parser.add_argument(
        "--sample", choices=sorted(SAMPLES), default="perovskite",
        help="synthetic structure shown when no FILE is given",
    )
    parser.add_argument(
        "--check-renderer", action="store_true",
        help="render a small reference scene with POV-Ray, verify it, and exit",
    )
    parser.add_argument(
        "--povray", metavar="PATH",
        help="POV-Ray executable for --check-renderer (default: $YCRYSTAL_POVRAY, then PATH)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)

    if args.check_renderer:
        from ycrystal.render.selftest import run_self_test

        result = run_self_test(args.povray)
        print(("PASS: " if result.ok else "FAIL: ") + result.message)
        return 0 if result.ok else 1

    os.environ["QT_API"] = "pyside6"
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication

    from ycrystal.gui.main_window import MainWindow

    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("Ycrystal")
    app.setOrganizationName("Y-Matter Lab")
    app.setApplicationVersion(__version__)
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
