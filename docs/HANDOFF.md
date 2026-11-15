# Development handoff (Linux Mint → macOS)

Written on 16 November 2026 at the end of development on Linux Mint 22.1, for continuing
on a Mac mini running macOS. Project instructions for Claude Code are in `CLAUDE.md` at
the repository root; the detailed verification record is [PROGRESS.md](PROGRESS.md).

## Repository state

- Branch: `main` (the only branch on GitHub), in sync with `origin/main`.
- Latest commit: `49f92e9` — merge of PR #19 (FR-VECTOR-01). Tags: `v0.1.0`, `v0.2.0`.
- Last verified on Linux: CI on PR #19 passed (pre-commit, docs, and the full test
  suite with POV-Ray 3.7 under Xvfb). Local runs before that PR: `pytest -m "not
  povray"` 420 passed (plus one test added afterwards), POV-Ray subsets 12 and 20
  passed.
- Released version: 0.2.0. Everything after it is merged on `main` but **not released**
  (no changelog entry and no tag yet).

## Implemented and verified features

| Version | Feature | Merged |
| --- | --- | --- |
| 0.1.0 | Milestones M0–M6: import, projects, navigation, selection, supercells, bonds, materials, environments, previews, rendering, styles, desktop launcher | tag `v0.1.0` |
| 0.2.0 | FR-COLOR-01 colour dialog and names; FR-RENDER-01 aspect-ratio lock; FR-LIGHT-01 Lighting Setup window and live lighting | PRs #13–#15, tag `v0.2.0` |
| unreleased | FR-MEASURE-01 distance and bond-angle measurements (Measurements panel) | PR #16 |
| unreleased | FR-PREVIEW-01 adjustable POV-Ray preview resolution | PR #17 |
| unreleased | FR-BGIMAGE-01 background pictures, ZIP project/style packages (project schema 6) | PR #18 |
| unreleased | FR-MATERIAL-01 custom material variants (Customize Material…, personal materials) | PR #18 |
| unreleased | FR-VECTOR-01 atom-attached direction/magnetic-moment vectors (project schema 7) | PR #19 |

Each has automated checks recorded in [PROGRESS.md](PROGRESS.md). Hands-on checks by a
person are still open for most of them; the user reports FR-VECTOR-01 working well.

## Work in progress and known issues

- No work in progress: no uncommitted changes besides this handoff and the files listed
  under "Not transferred by Git".
- Known limitations (from PROGRESS.md): background pictures show only their average
  colour in the live VTK view; no rename/delete UI for personal materials; live-view
  speed with thousands of vector arrows is unmeasured; the Lighting Setup overview does
  not draw vector arrows; revealing the Measurements panel resizes the view, which marks
  the preview out of date.
- macOS-specific issues found by reading the code (not yet observed on a Mac):
  - `tests/conftest.py` skips every `gui` test unless `DISPLAY` or `WAYLAND_DISPLAY` is
    set, and macOS sets neither. Without a change, GUI tests are silently skipped on
    macOS (or fail with `YCRYSTAL_REQUIRE_INTEGRATION=1`).
  - `render/povray.py` looks for standard POV-Ray include files only in Linux locations
    (`/etc/povray/3.7/povray.ini`, `~/.povray/3.7/povray.ini`,
    `/usr/share/povray-3.7/include`, `/usr/local/share/povray-3.7/include`). A Homebrew
    POV-Ray on Apple silicon lives under `/opt/homebrew`, so the export may wrongly
    report missing include files (`metals.inc`, `textures.inc`) even though POV-Ray
    finds them.
  - `ycrystal --install-desktop` creates a Linux (freedesktop) menu entry; it does not
    apply to macOS.
  - `pyproject.toml` classifiers say Linux only, and `constraints.txt` was resolved on
    Linux; whether every pinned version has a macOS wheel is unverified.

## Pending tasks and recommended next steps

1. Set up the Mac (below) and run the fast suite, `ycrystal --check-renderer`, and one
   render; record what works.
2. Decide how to handle the macOS findings above (for example detect a non-X11 platform
   in `tests/conftest.py`; add Homebrew include locations). Record them as a feature or
   fix in the private plan before changing code.
3. Hands-on checks of the unreleased features; then prepare a release (changelog entry,
   version bump, tag) when the user decides.
4. Small polish noted earlier: hide the disabled Bottom/Clouds rows for the Image
   background type; a way to manage personal materials.

## Decisions and deferred features

- **FR-VECTOR-02 (CSV/TSV vector tables) is deferred.** Its specification is kept in the
  private plan for possible future use; do not implement or scaffold it unless the user
  explicitly asks to reactivate it.
- Vectors: Cartesian components in the structure frame; magnetic moments in μB,
  directions dimensionless; source defaults plus image overrides/suppressions; no
  inferred signs or magnetic symmetry; styles carry arrow appearance, never vectors.
- Pictures and custom materials are content-addressed (SHA-256 / content-derived ids);
  projects embed the custom definitions they use, so they open on a clean profile.
- Projects/styles are ZIP packages only when they carry a picture; otherwise JSON.
- Personal materials are stored in `QSettings` (`materials/personal`) with thumbnails in
  `material-thumbnails/` next to the settings file — per machine, not in Git.
- Preview resolution presets are widths (Small 480, Medium 800, Large 1200, Custom).

## Not transferred by Git

| Item | Status | What to do |
| --- | --- | --- |
| `IMPLEMENTATION_PLAN.md` | Private, gitignored | Copy manually (USB drive or private storage) to the repository root on the Mac; keep it untracked |
| `IMPLEMENTATION_PLAN.md.org` | Untracked, **not** gitignored | Copy manually if wanted; never `git add -A` without checking |
| `.venv/`, `.venv-docs/` | Gitignored | Recreate on the Mac (platform-specific) |
| `artifacts/` | Gitignored | Local screenshots and renders; not needed |
| `build/`, `dist/`, `.cache/`, `site/` | Gitignored | Generated; recreate if needed |
| Ycrystal settings | Outside the repository | Preferences, favourites, and personal materials are per machine (`QSettings`) |
| Claude Code memory | Outside the repository | Local to each machine; `CLAUDE.md` and this file replace it |

There are no stashes and no extra worktrees.

## macOS setup (unverified on the Mac — check each step)

Prerequisites, assuming Homebrew is installed:

```bash
xcode-select --install          # Git and command-line tools, if missing
brew install python@3.12 git
brew install povray             # POV-Ray 3.7; formula availability not verified here
```

Clone and install (commands taken from the repository's CI and install guide):

```bash
git clone https://github.com/ymatterlab/ycrystal.git
cd ycrystal
python3.12 -m venv .venv
.venv/bin/python -m pip install -e ".[dev]" -c constraints.txt
.venv/bin/ycrystal --version            # expect: ycrystal 0.2.0
.venv/bin/ycrystal --check-renderer     # POV-Ray self-test
.venv/bin/ycrystal --sample perovskite  # opens the window
```

If POV-Ray is not on `PATH`, point Ycrystal to it with the environment variable
`YCRYSTAL_POVRAY=/path/to/povray`, or with *Render ▸ Set POV-Ray Executable…*.

Tests and checks:

```bash
.venv/bin/python -m pytest -m "not povray" -q   # GUI tests skip on macOS (see above)
.venv/bin/python -m pytest -m povray -q
.venv/bin/pre-commit run --all-files
python3.12 -m venv .venv-docs && .venv-docs/bin/python -m pip install -r docs/requirements.txt
.venv-docs/bin/zensical build --clean --strict
```

On Linux the same commands work; run GUI tests under a display (or `xvfb-run -a`), and
install POV-Ray with `sudo apt install povray povray-includes` (see the install guide).
