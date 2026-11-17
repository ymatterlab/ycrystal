# Development handoff

The state of Ycrystal for continuing work on another machine: the Linux Mint laptop, the
office Mac mini, or a future Windows system. Rules for Claude Code are in `CLAUDE.md` at
the repository root; the detailed verification record is [PROGRESS.md](PROGRESS.md).

This file records state. It does not authorize work: implement only what the user asks
for in the current task (see [the rules at the end](#handoff-and-maintenance-rules)).

## Current project status

- **Milestone:** version 0.3.0 is tagged (tags `v0.1.0`, `v0.2.0`, `v0.3.0`; no GitHub
  releases). `v0.3.0` marks commit `6ed6b03` (PR #22); the source there still reports
  0.2.0; since the release housekeeping of 17 November 2026, `main` reports the
  development version `0.4.0.dev0`.
  FR-EXPORT-01 (PR #23) and the maintenance in PRs #25–#26 came after the tag and are
  listed as "Unreleased" in `CHANGELOG.md`.
- **Work in progress:** FR-STYLE-CLI-01 (styles from the command line) is implemented
  and tested on the Mac, **not yet committed**. No other feature is open or authorized;
  see [Next recommended steps](#next-recommended-steps).

| Version | Feature | Merged |
| --- | --- | --- |
| 0.1.0 | Milestones M0–M6: import, projects, navigation, selection, supercells, bonds, materials, environments, previews, rendering, styles, desktop launcher | tag `v0.1.0` |
| 0.2.0 | FR-COLOR-01 colour dialog and names; FR-RENDER-01 aspect-ratio lock; FR-LIGHT-01 Lighting Setup window and live lighting | PRs #13–#15, tag `v0.2.0` |
| 0.3.0 | FR-MEASURE-01 distance and bond-angle measurements (Measurements panel) | PR #16 |
| 0.3.0 | FR-PREVIEW-01 adjustable POV-Ray preview resolution | PR #17 |
| 0.3.0 | FR-BGIMAGE-01 background pictures, ZIP project/style packages (project schema 6) | PR #18 |
| 0.3.0 | FR-MATERIAL-01 custom material variants (Customize Material…, personal materials) | PR #18 |
| 0.3.0 | FR-VECTOR-01 atom-attached direction/magnetic-moment vectors (project schema 7) | PR #19 |
| 0.3.0 | Maintenance: macOS (Apple silicon) support, Ubuntu + macOS CI | PR #22, tag `v0.3.0` |
| unreleased | FR-EXPORT-01 PNG/PDF/JPEG export, publication size presets, custom size and dpi | PR #23 |
| unreleased | Maintenance: new application icon and logo, logo-rendering script; Linux launcher refreshes the icon cache | PRs #25, #26 |
| unreleased | FR-STYLE-CLI-01 `--style`/`--style-parts` apply a `.ycstyle` before `--render`/`--export-pov` | Not yet committed |

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

## Latest development session

- **Date and machine:** 17 November 2026, Mac mini (macOS 15.8, Apple silicon).
- **Branch:** `main` at `410d87e` (working tree; no feature branch created yet).
- **Commits:** none — the changes are uncommitted, as requested.
- **Task:** FR-STYLE-CLI-01 only — apply `.ycstyle` files from the command line.
  Evidence: "FR-STYLE-CLI-01" in PROGRESS.md.

Summary of changes:

- `batch.py`: `CLI_STYLE_PARTS`, `StyleTransferError`, `parse_style_parts`,
  `apply_style_file` (load the style, call `apply_style`, return a new `Project` and the
  notes; large-display check). Rendering and export are unchanged.
- `app.py`: `--style STYLE.ycstyle` and `--style-parts LIST` in the "without a window"
  group; notes as `WARNING:` lines; `--style` without `--render`/`--export-pov` and
  `--style-parts` without `--style` are usage errors.
- `core/scene.py`: `LARGE_DISPLAY_ATOMS = 20000`; `gui/main_window.py` uses it
  (`SOFT_LIMIT_ATOMS` stays as an alias).
- Tests: 15 new in `tests/test_style.py`, 14 new in `tests/test_release.py` (one with
  real POV-Ray, one in a subprocess without `DISPLAY`).
- Documentation: examples guide (new section "Apply a style from the command line",
  example table), appearance guide (styles), README and documentation home (command
  example), API reference (`batch`, `scene`), changelog ("Unreleased"), PROGRESS.md.
  `scripts/docs_examples.py` (run in CI) now runs the documented MgB2 `--style` command
  with `--export-pov` and checks its warning, size, and studio.

Tests performed on the Mac:

| Check | Result |
| --- | --- |
| `YCRYSTAL_REQUIRE_INTEGRATION=1 pytest -q -rs` (real windows, Homebrew POV-Ray 3.7.0.10) | 595 passed, none skipped |
| `pytest -m "not gui"` (what the macOS CI job runs) | 430 passed |
| Doctests (`core/scene.py`, `io/style.py`, `batch.py`), `scripts/docs_examples.py`, `pre-commit run --all-files`, `zensical build --clean --strict` | Clean |
| The documented commands (MgB2 with the grey studio, with all parts, the vector example) rendered and inspected | As described in the guide |

Not done: Linux (CI will run it on a push); hands-on use by a person.

## Next recommended steps

1. Review the FR-STYLE-CLI-01 changes; commit, push, and open a PR when the user asks.
   CI then runs the new tests on Ubuntu (not yet run on Linux).
2. Optional check (no new work): place an exported PDF in a LaTeX or Word document and
   check its size there.

The next features in the private plan (FR-STYLE-MAP-01, FR-CAMERA-01, FR-BATCH-01, …)
are **not** authorized by this record; each needs its own request.

Still open from the macOS task: the [hands-on macOS checklist](#hands-on-checks-on-a-mac).

Suggestions only — not approved, ask before starting any of them:

- A command-line option for PDF/JPEG (`--render figure.pdf --dpi 600`); the CLI still
  writes PNG only.
- A macOS application bundle or launcher (name and icon in the Dock, opening
  `.ycrystal` files from Finder).
- Windows: a CI entry and a decision about the renderer there.
- From earlier sessions: hide the disabled Bottom/Clouds rows for the Image background
  type; a way to manage personal materials; hands-on checks of the unreleased features,
  then the next release (FR-EXPORT-01 and the branding): move the changelog's
  "Unreleased" section under a version, bump `__version__`, and run the checklist in
  `docs/development/release.md` before tagging, when the user decides.

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
| Styles from the command line (FR-STYLE-CLI-01) | Not tested (CI runs it once the branch is pushed) | Verified 17 Nov 2026 (automated, real POV-Ray; uncommitted) | Not tested |
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
.venv/bin/ycrystal --version            # ycrystal 0.4.0.dev0
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
| Other private planning files at the root (older plan copies, the owner's notes) | Untracked; excluded in this checkout's `.git/info/exclude`, not in `.gitignore` | Copy manually if wanted, and add them to `.git/info/exclude` in the new checkout; never `git add -A` without checking |
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
- Styles from the command line (FR-STYLE-CLI-01): default parts
  `appearance,environment,output` (`ycrystal.batch.CLI_STYLE_PARTS`), `display` on
  request; the GUI's Import Style dialog is unchanged. A saved project keeps its camera.
  A style may not raise the display above 20,000 atoms (`LARGE_DISPLAY_ATOMS`) from
  the command line; there is no override. Notes are `WARNING:` lines on stderr.
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
