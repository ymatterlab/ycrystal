# Development handoff

The state of Ycrystal for continuing work on another machine: the Linux Mint laptop, the
office Mac mini, or a future Windows system. Rules for Claude Code are in `CLAUDE.md` at
the repository root; the detailed verification record is [PROGRESS.md](PROGRESS.md).

This file records state. It does not authorize work: implement only what the user asks
for in the current task (see [the rules at the end](#handoff-and-maintenance-rules)).

## Current project status

- **Milestone:** version 0.2.0 is released (tags `v0.1.0`, `v0.2.0`). The features below
  marked "unreleased" are merged on `main` without a changelog entry or tag. macOS
  support (PR #22) and FR-EXPORT-01 (PR #23, merge commit `52b3e5e`) are merged.
- **Work in progress:** none. No feature is open or authorized; see
  [Next recommended steps](#next-recommended-steps).

| Version | Feature | Merged |
| --- | --- | --- |
| 0.1.0 | Milestones M0–M6: import, projects, navigation, selection, supercells, bonds, materials, environments, previews, rendering, styles, desktop launcher | tag `v0.1.0` |
| 0.2.0 | FR-COLOR-01 colour dialog and names; FR-RENDER-01 aspect-ratio lock; FR-LIGHT-01 Lighting Setup window and live lighting | PRs #13–#15, tag `v0.2.0` |
| unreleased | FR-MEASURE-01 distance and bond-angle measurements (Measurements panel) | PR #16 |
| unreleased | FR-PREVIEW-01 adjustable POV-Ray preview resolution | PR #17 |
| unreleased | FR-BGIMAGE-01 background pictures, ZIP project/style packages (project schema 6) | PR #18 |
| unreleased | FR-MATERIAL-01 custom material variants (Customize Material…, personal materials) | PR #18 |
| unreleased | FR-VECTOR-01 atom-attached direction/magnetic-moment vectors (project schema 7) | PR #19 |
| unreleased | Maintenance: macOS (Apple silicon) support, Ubuntu + macOS CI | PR #22 |
| unreleased | FR-EXPORT-01 PNG/PDF/JPEG export, publication size presets, custom size and dpi | PR #23 |

Each has automated checks recorded in [PROGRESS.md](PROGRESS.md). Hands-on checks by a
person are still open for most of them; the user reports FR-VECTOR-01 and FR-EXPORT-01
working.

Known limitations and unresolved issues:

- Background pictures show only their average colour in the live VTK view; there is no
  rename/delete UI for personal materials; live-view speed with thousands of vector
  arrows is unmeasured; the Lighting Setup overview does not draw vector arrows.
- macOS: Ycrystal runs from the source checkout. There is no application bundle, so the
  Dock and the menu bar show "Python", and `.ycrystal` files do not open by double click.
- macOS: nothing has been checked by hand yet, and no Retina display was available (see
  [Cross-platform status](#cross-platform-status)).
- FR-EXPORT-01: the PDF holds the POV-Ray raster image (not vector graphics); PDF page
  sizes are whole points (up to 0.18 mm from the exact size); JPEG fills a transparent
  background with white. Not yet run on Linux or checked by hand.
- `docs/guide/troubleshooting.md` ("Current limitations") still says that image
  backgrounds and editable material parameters are unsupported; both exist since PR #18.

## Latest development session

- **Date and machine:** 16 November 2026, Mac mini (macOS 15.8, Apple silicon).
- **Branch:** `feature/export-formats`, created from `main` at `6ed6b03` (PR #22 merged;
  the user reported the Linux Mint tests and the new CI jobs passing for it).
- **Commits:** `a55b298`, merged into `main` by PR #23 (merge commit `52b3e5e`,
  16 November 2026) after all four CI checks passed. The user reported that everything
  works.
- **Task:** FR-EXPORT-01 — PDF and JPEG export next to PNG, publication size presets,
  and custom size/resolution, as one feature. Evidence: "FR-EXPORT-01" in PROGRESS.md.

Summary of changes:

- `core/export.py` (new, no Qt): formats, presets (85 mm and 180 mm at 600 dpi), mm/px/dpi
  arithmetic, limits, `ExportOptions`.
- `render/formats.py` (new): writes POV-Ray's PNG as PNG (a `pHYs` resolution chunk is
  inserted; pixels and compressed data untouched), JPEG (`QImageWriter`, quality, white
  under transparency), or PDF (`QPdfWriter`, lossless, page = physical size), always via
  a checked `.part` file.
- `gui/export_dialog.py` (new): the Render Image dialog; `gui/main_window.py`: the action
  is now **Render Image…** (Ctrl+R) → `export_image` → `render_image`; `render_png(path)`
  keeps its former output (no resolution chunk). Exports never change the output size,
  camera, or project.
- Tests: `tests/test_export.py` (43, no window or POV-Ray), `tests/test_gui_export.py`
  (17, one with real POV-Ray); `tests/conftest.py` blocks the new `ask_export` dialog.
- Documentation: rendering, first-figure, controls, support, and troubleshooting guides,
  README, index, API reference, architecture; CI doctest list. The private plan has a
  new row and section 14.9 for FR-EXPORT-01.

Tests performed on the Mac (details: "FR-EXPORT-01" in PROGRESS.md):

| Check | Result |
| --- | --- |
| `YCRYSTAL_REQUIRE_INTEGRATION=1 pytest -q -rs` (real windows, Homebrew POV-Ray 3.7.0.10) | 565 passed, none skipped (505 before + 60 new) |
| `pytest -m "not gui"` (what the macOS CI job runs) | 400 passed |
| New doctests (`core/export.py`, `render/formats.py`); ruff; `pre-commit run --all-files`; `zensical build --clean --strict` | Clean |
| Dialog screenshots (PNG, JPEG with preset, unlocked PDF) | Layout correct on macOS |

CI of PR #23 passed: pre-commit, docs, macOS 15 (tests without windows), and Ubuntu
24.04 (full suite under Xvfb with POV-Ray 3.7, including the new export tests).

Not done by Claude: the Linux laptop and hands-on use (the user reports that everything
works); the exported PDFs were checked by their structure (page box, embedded image),
not opened in PDF viewers by Claude.

## Next recommended steps

FR-EXPORT-01 is complete and merged. Optional follow-up checks (no new work):

1. Place an exported PDF in a LaTeX or Word document and check its size there.
2. Delete the merged branch `feature/export-formats` if it is no longer needed.

Still open from the macOS task: the [hands-on macOS checklist](#hands-on-checks-on-a-mac).

Suggestions only — not approved, ask before starting any of them:

- A command-line option for PDF/JPEG (`--render figure.pdf --dpi 600`); the CLI still
  writes PNG only.
- A macOS application bundle or launcher (name and icon in the Dock, opening
  `.ycrystal` files from Finder).
- Correct the outdated limitations list in `docs/guide/troubleshooting.md`.
- Windows: a CI entry and a decision about the renderer there.
- From earlier sessions: hide the disabled Bottom/Clouds rows for the Image background
  type; a way to manage personal materials; hands-on checks of the unreleased features,
  then a release (changelog entry, version bump, tag) when the user decides.

Dependencies and blockers:

- The repository is private, and GitHub bills hosted macOS minutes at a higher rate
  than Linux minutes. The macOS job runs on every pull request and push to `main`; if
  that is too costly, restrict it (for example to `main` and manual runs).
- GitHub's hosted Macs have no GPU, so the GUI tests cannot run there reliably; they
  need a real Mac.
- Windows: POV-Ray for Windows is a GUI program without a `povray` command, so
  rendering needs a different executable or command line there. Nothing is designed.

## Cross-platform status

Status words: **verified** (tested on that system, date given), **partial** (some of it
tested), **not tested**, **known issue**. Linux results for the macOS changes are the
user's report for PR #22.

| Area | Linux Mint 22.1 / Ubuntu 24.04 | macOS 15 (Apple silicon) | Windows |
| --- | --- | --- | --- |
| Install from source with `constraints.txt` | Verified on `main` (CI, PR #19) | Verified 16 Nov 2026 | Not tested |
| Command line: `--version`, `--check-renderer`, `--render`, `--export-pov` | Verified (PR #22, user report) | Verified 16 Nov 2026 | Not tested |
| POV-Ray discovery and include files | Verified (PR #22, user report) | Verified 16 Nov 2026 (Homebrew) | Not tested; known issue: no `povray` command |
| Tests without windows (structures, projects, export, rendering, `QProcess`) | Verified (PR #22, user report) | Verified 16 Nov 2026 | Not tested |
| GUI tests (real windows, OpenGL) | Verified (PR #22, user report; CI under Xvfb) | Verified 16 Nov 2026 (non-Retina display) | Not tested |
| PNG/PDF/JPEG export (FR-EXPORT-01) | Verified by CI (PR #23, Ubuntu, full suite) | Verified 16 Nov 2026 (automated, real POV-Ray; CI without windows); the user reports it working | Not tested |
| Hands-on use of the window | Partial (the user's own use; most post-0.2.0 features not checked by hand) | Not tested | Not tested |
| HiDPI / Retina display | Not tested | Partial: emulated 2× scale only | Not tested |
| Menu launcher, file association | Verified on `main` (`--install-desktop`) | Known issue: none exists; the option refuses | Not tested; none exists |
| Continuous integration | Verified (PR #22, user report) | Job runs without GUI tests by design (PR #22, user report) | None |

### Hands-on checks on a Mac

Automated tests cannot establish these. Start with `.venv/bin/ycrystal --sample
perovskite` and note what fails.

- [ ] The window opens, the structure is drawn sharply, and it fills the whole view
      (on a Retina display: not a quarter of it, not blurred).
- [ ] Mouse: left drag orbits, Shift + left drag pans, right drag and the wheel zoom.
      Trackpad: two-finger scrolling zooms at a usable speed; pinching zooms.
- [ ] Click selects the atom under the cursor (also on a Retina display); ⌘ + click
      toggles; Delete (⌫) hides; Esc clears.
- [ ] Menus: Ycrystal's Quit is in the application menu; ⌘O, ⌘S, ⇧⌘S, ⌘Z, ⇧⌘Z, ⌘R, ⌘M,
      ⌘← / ⌘→, F (Fit), and F5 (Preview; may need Fn) work with the 3D view focused.
- [ ] File dialogs: Open lists POSCAR/CONTCAR files without an extension, `.cif`,
      `.pw.in`; Save Project adds `.ycrystal`; Render Image… (PNG, PDF, JPEG) and
      Export POV-Ray… save.
- [ ] Render ▸ Set POV-Ray Executable… starts in the folder of the found executable;
      Render ▸ Check Renderer passes.
- [ ] Preview with **Update automatically** on: one preview per change, no repeated
      re-rendering while idle, also in a small window.
- [ ] Supercell handles, measurement modes, Lighting Setup window (drag the key
      light), Vectors window, Customize Material… (saving a personal material creates
      its thumbnail), background picture.
- [ ] Appearance: readable in macOS dark mode; colour dialog and galleries.
- [ ] A long render can be cancelled; closing the window during a render exits cleanly.
- [ ] A project saved on Linux opens on the Mac and renders the same image, and the
      reverse.

## Development environment notes

Common to all systems: one virtual environment per machine and per checkout (`.venv`;
`.venv-docs` for the documentation). A virtual environment copied from another
operating system does not work: recreate it with `python3.12 -m venv --clear .venv`.

Linux Mint 22 / Ubuntu 24.04:

```bash
sudo apt install git povray povray-includes libxcb-cursor0 python3.12-venv
/usr/bin/python3 -m venv .venv          # the system Python, not Conda
```

macOS (Homebrew; verified on macOS 15.8, Apple silicon):

```bash
xcode-select --install                  # Git and command-line tools, if missing
brew install python@3.12 povray         # POV-Ray 3.7 with its include files
python3.12 -m venv .venv
```

Then, on either system, from the repository root:

```bash
.venv/bin/python -m pip install -e ".[dev]" -c constraints.txt
.venv/bin/ycrystal --version            # ycrystal 0.2.0
.venv/bin/ycrystal --check-renderer     # PASS: POV-Ray 3.7… passed
.venv/bin/ycrystal --sample perovskite  # opens the window
.venv/bin/python -m pytest -q -rs       # GUI tests open windows for about 1.5 minutes
.venv/bin/pre-commit run --all-files
python3.12 -m venv .venv-docs && .venv-docs/bin/python -m pip install -r docs/requirements.txt
.venv-docs/bin/zensical build --clean --strict
```

POV-Ray is found in this order: the path saved with *Render ▸ Set POV-Ray Executable…*,
the environment variable `YCRYSTAL_POVRAY`, then `povray` on `PATH` (`command -v povray`
shows it: `/usr/bin/povray` from apt, `/opt/homebrew/bin/povray` from Homebrew on Apple
silicon). The include files are looked up in the installation of that executable.

Troubleshooting:

- Linux: "Could not initialize GLX" or an xcb plugin error: use `/usr/bin/python3`
  outside Conda and install `libxcb-cursor0`. Without a desktop session run the tests
  with `xvfb-run -a`.
- macOS: `python3.12: command not found` — install `python@3.12` with Homebrew; the
  system `python3` is too old. Conda's Python is unverified.
- macOS: Qt prints "Can not manage visual effect areas in views without a container
  layer" for the 3D view; it had no visible effect in the tests.
- macOS: GUI tests take the keyboard focus while they run; leave the machine alone or
  run `pytest -m "not gui"`.
- Windows: not set up. Start from the macOS steps with the Windows launcher
  (`py -3.12 -m venv .venv`, `.venv\Scripts\python`) and record what happens here.

## Not transferred by Git

| Item | Status | What to do |
| --- | --- | --- |
| `IMPLEMENTATION_PLAN.md` | Private, gitignored | Copy manually (USB drive or private storage) to the repository root; keep it untracked |
| `IMPLEMENTATION_PLAN.md.org` | Untracked, **not** gitignored | Copy manually if wanted; never `git add -A` without checking |
| `.venv/`, `.venv-docs/` | Gitignored | Recreate on each machine (never copy between systems) |
| `artifacts/` | Gitignored | Local screenshots and renders; not needed |
| `build/`, `dist/`, `.cache/`, `site/` | Gitignored | Generated; recreate if needed |
| Ycrystal settings | Outside the repository | Preferences, favourites, and personal materials are per machine (`QSettings`): `~/.config/Y-Matter Lab/` on Linux; `~/Library/Preferences/com.y-matter-lab.Ycrystal.plist` and `~/Library/Application Support/Y-Matter Lab/Ycrystal/` on macOS |
| Claude Code memory | Outside the repository | Local to each machine; `CLAUDE.md` and this file replace it |

## Decisions and deferred features

- **FR-VECTOR-02 (CSV/TSV vector tables) is deferred.** Its specification is kept in the
  private plan for possible future use; do not implement or scaffold it unless the user
  explicitly asks to reactivate it. No feature request has been rejected so far.
- One repository and one codebase for all systems; no platform branches. Platform checks
  stay in `gui/native.py`, `desktop.py`, `render/povray.py`, and `tests/conftest.py`.
- A resize of the view is not a change of the figure (16 November 2026).
- macOS CI runs without GUI tests; the GUI is verified on a real Mac.
- Vectors: Cartesian components in the structure frame; magnetic moments in μB,
  directions dimensionless; source defaults plus image overrides/suppressions; no
  inferred signs or magnetic symmetry; styles carry arrow appearance, never vectors.
- Pictures and custom materials are content-addressed (SHA-256 / content-derived ids);
  projects embed the custom definitions they use, so they open on a clean profile.
- Projects/styles are ZIP packages only when they carry a picture; otherwise JSON.
- Personal materials are stored in `QSettings` (`materials/personal`) with thumbnails in
  a `material-thumbnails/` folder (per machine, not in Git; locations above).
- Preview resolution presets are widths (Small 480, Medium 800, Large 1200, Custom).
- Export (FR-EXPORT-01): one POV-Ray render per export at the export pixel size; pixels
  and dpi are the source of truth (mm derived); no resampling; JPEG transparency →
  white; PDF = raster image on a page of the physical size, never called vector; the
  export does not change the project's output size; dialog settings last for the
  session only (not `QSettings`).

## Handoff and maintenance rules

- This file is a record of the project's state, **not** an authorization to implement
  anything. The order of authority is in `CLAUDE.md` ("Priority of instructions").
- At the start of a session read `CLAUDE.md`, this file, and the requirements that
  concern the task; then check `git status` and the recent `git log` to see the actual
  state. If a document disagrees with the code or the history, investigate; do not
  assume the document is right.
- After a substantial task, update "Latest development session", the status table, and
  the next steps, from results you observed. Do not report unrun tests as passed or
  planned work as done.
- Keep entries short and actionable. Move finished detail to PROGRESS.md instead of
  growing this file, and keep unresolved issues until they are resolved.
- No machine-specific absolute paths, personal details, or credentials in this file.
