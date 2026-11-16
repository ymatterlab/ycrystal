# Development handoff

The state of Ycrystal for continuing work on another machine: the Linux Mint laptop, the
office Mac mini, or a future Windows system. Rules for Claude Code are in `CLAUDE.md` at
the repository root; the detailed verification record is [PROGRESS.md](PROGRESS.md).

This file records state. It does not authorize work: implement only what the user asks
for in the current task (see [the rules at the end](#handoff-and-maintenance-rules)).

## Current project status

- **Milestone:** version 0.2.0 is released (tags `v0.1.0`, `v0.2.0`). The features below
  marked "unreleased" are merged on `main` without a changelog entry or tag. No feature
  milestone is open; the current topic is maintenance: support for macOS next to Linux.
- **Work in progress:** branch `feature/cross-platform` (macOS support), described under
  [Latest development session](#latest-development-session).

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

Known limitations and unresolved issues:

- Background pictures show only their average colour in the live VTK view; there is no
  rename/delete UI for personal materials; live-view speed with thousands of vector
  arrows is unmeasured; the Lighting Setup overview does not draw vector arrows.
- macOS: Ycrystal runs from the source checkout. There is no application bundle, so the
  Dock and the menu bar show "Python", and `.ycrystal` files do not open by double click.
- macOS: nothing has been checked by hand yet, and no Retina display was available (see
  [Cross-platform status](#cross-platform-status)).
- The macOS job in CI and the Linux job with the changes of the latest session have not
  run yet.
- `docs/guide/troubleshooting.md` ("Current limitations") still says that image
  backgrounds and editable material parameters are unsupported; both exist since PR #18.

## Latest development session

- **Date and machine:** 16 November 2026, Mac mini (macOS 15.8, Apple silicon, one
  non-Retina display).
- **Branch:** `feature/cross-platform`, created from `main` at `792df59`.
- **Commits:** none. The changes were in the working tree when this was written;
  committing, pushing, and opening the pull request await the user's instruction.

Summary of changes (causes and evidence: "Maintenance: macOS support" in PROGRESS.md):

- `viewport/interactor.py` (new): both VTK views draw before `render()` returns on every
  platform; on macOS PyVistaQt alone leaves the view one frame behind.
- `viewport/qt_viewport.py`: resizing the view is no longer reported as a view change.
  **This also changes Linux**: resizing the window or a panel no longer marks the preview
  out of date. On macOS it was needed: small windows grow when a preview starts, and the
  preview then discarded itself.
- `render/povray.py`: standard include files are located from the POV-Ray executable's
  installation (Homebrew, `/usr`, `/usr/local`, …); install hints name Homebrew.
- `gui/native.py` (new): ⌘ instead of Ctrl in help texts on macOS; personal-material
  thumbnails go to the application data folder on macOS and Windows.
- `app.py`, `desktop.py`: `--install-desktop` / `--uninstall-desktop` refuse outside
  Linux. `gui/main_window.py`: the POV-Ray file dialog starts at the found executable.
- Tests: `tests/conftest.py` recognizes the macOS/Windows desktop; new
  `tests/test_platform.py` (8 tests) and one test in `tests/test_gui_render.py`; two
  tests corrected for HiDPI displays (`tests/test_gui.py`,
  `tests/test_preview_resolution.py`).
- CI: the `test` job is a matrix (Ubuntu: everything under Xvfb; macOS 15: tests that
  open no window). `pyproject.toml` classifiers; two macOS-only pins in
  `constraints.txt`.
- Documentation: `CLAUDE.md`, this file, PROGRESS.md, README, the install, support,
  rendering, controls, and troubleshooting guides, the architecture page,
  CONTRIBUTING.md.

Tests performed on the Mac (final code):

| Check | Result |
| --- | --- |
| `YCRYSTAL_REQUIRE_INTEGRATION=1 pytest -q -rs` (real windows, Homebrew POV-Ray 3.7.0.10) | 505 passed, none skipped |
| Steps of the macOS CI job run locally (version, `--check-renderer`, doctests, `scripts/docs_examples.py`, `pytest -m "not gui"`) | All pass; 357 tests |
| GUI tests with an emulated 2× display scale (`QT_SCALE_FACTOR=2`) | 148 passed (not a Retina test) |
| Scripted launch of the real application (native settings, automatic preview) | Preview "Up to date", exit status 0 |
| `pre-commit run --all-files`; `zensical build --clean --strict` | Clean |

Before the changes the same Mac gave: 349 passed without windows, all 147 GUI tests
skipped; run on the desktop, 9 of them failed.

Not done in this session: Linux was not available, so nothing was run there; nothing
was pushed, so the changed workflow never ran; no hands-on use of the window.

## Next recommended steps

Open parts of the task the user authorized (macOS support and cross-platform testing):

1. Review the working tree on `feature/cross-platform`; commit and open a pull request
   when the user says so. The pull request is the first run of the Ubuntu job with these
   changes and of the new macOS job: read both results, do not assume them.
2. Go through the [hands-on macOS checklist](#hands-on-checks-on-a-mac) and record the
   outcome in the status table below.
3. On the Linux laptop: pull the branch, run the full suite once, and confirm that
   previews behave as before apart from the resize change.

Suggestions only — not approved, ask before starting any of them:

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
tested), **not tested**, **known issue**. "This branch" means `feature/cross-platform`.

| Area | Linux Mint 22.1 / Ubuntu 24.04 | macOS 15 (Apple silicon) | Windows |
| --- | --- | --- | --- |
| Install from source with `constraints.txt` | Verified on `main` (CI, PR #19) | Verified 16 Nov 2026 | Not tested |
| Command line: `--version`, `--check-renderer`, `--render`, `--export-pov` | Verified on `main`; not tested on this branch | Verified 16 Nov 2026 | Not tested |
| POV-Ray discovery and include files | Verified on `main` (apt package); new prefix lookup not tested on Linux | Verified 16 Nov 2026 (Homebrew) | Not tested; known issue: no `povray` command |
| Tests without windows (structures, projects, export, rendering, `QProcess`) | Verified on `main`; not tested on this branch | Verified 16 Nov 2026 (357 passed) | Not tested |
| GUI tests (real windows, OpenGL) | Verified on `main` under Xvfb (CI) and on the laptop; not tested on this branch | Verified 16 Nov 2026 (148 passed, non-Retina display) | Not tested |
| Hands-on use of the window | Partial (the user's own use; most post-0.2.0 features not checked by hand) | Not tested | Not tested |
| HiDPI / Retina display | Not tested | Partial: emulated 2× scale only | Not tested |
| Menu launcher, file association | Verified on `main` (`--install-desktop`) | Known issue: none exists; the option refuses | Not tested; none exists |
| Continuous integration | Verified on `main`; changed workflow not run | Not tested: job added, never run; no GUI tests by design | None |

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
      `.pw.in`; Save Project adds `.ycrystal`; Render PNG… and Export POV-Ray… save.
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
