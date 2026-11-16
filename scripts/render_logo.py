#!/usr/bin/env python3
"""Render Ycrystal branding PNGs from the accompanying POV-Ray scene.

REQUIREMENTS
    Python 3.10+ (standard library only) and POV-Ray 3.7+: the environment variable
    YCRYSTAL_POVRAY, or povray on PATH. The scene is scripts/branding/ycrystal_logo.pov.

QUICK START (run from the repository root)
    python3 scripts/render_logo.py --help
    python3 scripts/render_logo.py --list
    python3 scripts/render_logo.py --only horizontal
    python3 scripts/render_logo.py --only icon
    python3 scripts/render_logo.py --only favicon
    python3 scripts/render_logo.py --only mark
    python3 scripts/render_logo.py                # all images

RENDER JUST ONE FILE
    python3 scripts/render_logo.py --name ycrystal_horizontal_transparent_1920x720.png
    python3 scripts/render_logo.py --name ycrystal_app_icon_1024.png

OTHER USEFUL OPTIONS
    python3 scripts/render_logo.py --only horizontal --gap 0.08
    python3 scripts/render_logo.py --only horizontal --out /some/folder
    python3 scripts/render_logo.py --quality preview
    python3 scripts/render_logo.py --only icon --dry-run

WHAT IS GENERATED?
    horizontal: Y-shaped atomic chain + "crystal" wordmark (white/transparent)
    mark:       isolated Y-shaped atomic chain (transparent)
    icon:       Y-shaped atomic chain on a dark rounded-square tile (transparent)
    favicon:    16, 32 and 64 px versions of the icon (a subset of "icon")

    Files go to artifacts/branding/ by default (gitignored). Each image is rendered
    in a temporary folder and then moved there, because POV-Ray's povray.conf may
    forbid writing elsewhere. Review the result, then copy only final images used by
    the application, website, or README into their respective tracked locations.

    This is a developer utility, not a runtime dependency of Ycrystal.
    The existing app SVG can remain the application's primary icon.
"""

from __future__ import annotations

import argparse
import os
import shlex
import shutil
import subprocess
import tempfile
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
SCENE = SCRIPTS / "branding" / "ycrystal_logo.pov"
OUTPUT = SCRIPTS.parent / "artifacts" / "branding"  # gitignored

# (filename, width, height, POV-Ray LogoMode, transparent, category)
# Keep the published names stable: existing README / website links may use them.
OUTPUTS = (
    ("ycrystal_horizontal_white_1920x720.png", 1920, 720, 0, False, "horizontal"),
    ("ycrystal_horizontal_transparent_1920x720.png", 1920, 720, 0, True, "horizontal"),
    ("ycrystal_horizontal_transparent_1600x600.png", 1600, 600, 0, True, "horizontal"),
    ("ycrystal_mark_transparent_1024.png", 1024, 1024, 1, True, "mark"),
    ("ycrystal_mark_transparent_512.png", 512, 512, 1, True, "mark"),
    ("ycrystal_app_icon_1024.png", 1024, 1024, 2, True, "icon"),
    ("ycrystal_app_icon_512.png", 512, 512, 2, True, "icon"),
    ("ycrystal_app_icon_256.png", 256, 256, 2, True, "icon"),
    ("ycrystal_app_icon_128.png", 128, 128, 2, True, "icon"),
    ("ycrystal_app_icon_64.png", 64, 64, 2, True, "icon"),
    ("ycrystal_app_icon_32.png", 32, 32, 2, True, "icon"),
    ("ycrystal_app_icon_16.png", 16, 16, 2, True, "icon"),
)

# The existing preview selection is deliberately smaller, but uses the same
# output resolutions. It is a quick subset, not a new naming convention.
PREVIEW_NAMES = {
    "ycrystal_horizontal_white_1920x720.png",
    "ycrystal_horizontal_transparent_1920x720.png",
    "ycrystal_mark_transparent_512.png",
    "ycrystal_app_icon_512.png",
    "ycrystal_app_icon_32.png",
}

FAVICON_SIZES = {16, 32, 64}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate Ycrystal horizontal logos, Y marks and app icons using POV-Ray.",
        epilog=(
            "Examples:\n"
            "  python3 scripts/render_logo.py --list\n"
            "  python3 scripts/render_logo.py --only horizontal\n"
            "  python3 scripts/render_logo.py --only icon\n"
            "  python3 scripts/render_logo.py --only favicon\n"
            "  python3 scripts/render_logo.py --name ycrystal_app_icon_1024.png\n"
            "  python3 scripts/render_logo.py --only horizontal --gap 0.08\n"
            "\n"
            "The scene is scripts/branding/ycrystal_logo.pov. Output defaults to\n"
            "artifacts/branding/ (ignored by Git). See the script module docstring\n"
            "for a complete quick-start guide."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--pov",
        type=Path,
        default=SCENE,
        help="POV-Ray scene (default: scripts/branding/ycrystal_logo.pov)",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=OUTPUT,
        help="output directory (default: artifacts/branding/, gitignored)",
    )
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument(
        "--only",
        choices=("all", "horizontal", "mark", "icon", "favicon"),
        default="all",
        help="render one category; 'favicon' means 16/32/64 px icons (default: all)",
    )
    selection.add_argument(
        "--name",
        choices=tuple(item[0] for item in OUTPUTS),
        metavar="FILENAME",
        help="render exactly one PNG listed by --list",
    )
    parser.add_argument(
        "--quality",
        choices=("preview", "final"),
        default="final",
        help="'preview' renders fewer representative sizes; 'final' renders the full selection",
    )
    parser.add_argument(
        "--gap",
        type=float,
        default=0.20,
        help="horizontal Y-to-word spacing in POV-Ray units, 0.00-0.80 (default: 0.20)",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="list available PNGs, their sizes and categories, without rendering",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="show POV-Ray commands without running POV-Ray (no installation needed)",
    )
    return parser


def list_outputs() -> None:
    print("Available outputs (--name FILENAME renders one file):")
    print(f"  {'Category':<12} {'Size':<12} {'Background':<13} Filename")
    print("  " + "-" * 80)
    for name, width, height, _, transparent, category in OUTPUTS:
        print(
            f"  {category:<12} {f'{width}x{height}':<12} "
            f"{'transparent' if transparent else 'white':<13} {name}"
        )
    print("\n--only favicon selects the 16, 32 and 64 px entries in the icon category.")


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    # Listing does not require an existing scene or a POV-Ray installation.
    if args.list:
        list_outputs()
        return 0

    if not 0 <= args.gap <= 0.8:
        parser.error("--gap must be between 0 and 0.8")

    source = args.pov.expanduser().resolve()
    destination = args.out.expanduser().resolve()
    if not source.is_file():
        parser.error(f"POV-Ray scene not found: {source}")

    jobs = [
        job
        for job in OUTPUTS
        if (
            (job[0] == args.name)
            if args.name
            else (
                args.only == "all"
                or job[5] == args.only
                or (args.only == "favicon" and job[5] == "icon" and job[1] in FAVICON_SIZES)
            )
        )
    ]
    if args.quality == "preview" and not args.name:
        jobs = [job for job in jobs if job[0] in PREVIEW_NAMES]
    if not jobs:
        parser.error(
            "No files selected. Use --list to inspect the available outputs, "
            "or omit --quality preview for this category."
        )

    if not args.dry_run:
        povray = os.environ.get("YCRYSTAL_POVRAY") or shutil.which("povray")
        if povray is None:
            parser.error(
                "POV-Ray is not installed or is not on PATH. "
                "Install POV-Ray 3.7+ or use --dry-run to inspect the commands."
            )
        destination.mkdir(parents=True, exist_ok=True)
    else:
        povray = "povray"
        print(f"Commands run in a temporary folder holding a copy of {source.name};")
        print(f"each finished image is moved to {destination}.")

    for name, width, height, mode, transparent, category in jobs:
        target = destination / name
        cmd = [
            povray,
            "+Iscene.pov",
            "+Oimage.png",
            f"+W{width}",
            f"+H{height}",
            "+FN",
            "+A0.1",
            "+R3",
            "-D",
            "+UA" if transparent else "-UA",
            f"Declare=LogoMode={mode}",
            "Declare=ShowWireframe=0",
            f"Declare=TransparentBackground={int(transparent)}",
            f"Declare=WordGap={args.gap:.4f}",
        ]
        print(
            f"{category}: {name} ({width}x{height}, "
            f"{'transparent' if transparent else 'white'} background)",
            flush=True,
        )
        if args.dry_run:
            print("  " + shlex.join(cmd))
            continue
        # Render in a private folder (POV-Ray may only write to its working directory),
        # then move the image: paths with spaces or non-ASCII characters are safe too.
        with tempfile.TemporaryDirectory(prefix="ycrystal-logo-") as work:
            shutil.copyfile(source, Path(work) / "scene.pov")
            try:
                subprocess.run(cmd, check=True, cwd=work)
            except subprocess.CalledProcessError as exc:
                print(f"POV-Ray failed while rendering {name} (exit code {exc.returncode}).")
                return exc.returncode or 1
            except OSError as exc:
                print(f"Could not start POV-Ray ({povray}): {exc}")
                return 1
            image = Path(work) / "image.png"
            if not image.is_file() or image.stat().st_size == 0:
                print(f"POV-Ray finished but wrote no image for {name}.")
                return 1
            shutil.move(image, target)

    verb = "Would render" if args.dry_run else "Generated"
    print(f"{verb} {len(jobs)} image(s) in {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
