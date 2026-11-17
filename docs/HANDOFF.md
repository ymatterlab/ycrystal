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
- **Work in progress:** FR-VALIDATION-01 (validation tests, benchmark and replay-check
  scripts, evidence report, comparison, evaluation checklist; no application change)
  submitted from branch `feature/validation` as PR #33, to be merged after CI passes.
  FR-STYLE-CLI-01 (PR #28), FR-STYLE-MAP-01 (PR #29), FR-CAMERA-01
  (PR #30), FR-BATCH-01 (PR #31), and FR-REPRO-01 (PR #32, merge commit `e7ec99f`; the
  user tested it by hand) are merged. Nothing else is open or authorized;
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
| unreleased | FR-STYLE-CLI-01 `--style`/`--style-parts` apply a `.ycstyle` before `--render`/`--export-pov` | PR #28 |
| unreleased | FR-STYLE-MAP-01 element mapping for styles (`--element-map`, Import Style dialog) | PR #29 |
| unreleased | FR-CAMERA-01 `--view`, `--camera-policy`, `--fit-margin`, `--view-height` (shared with View along) | PR #30 |
| unreleased | FR-BATCH-01 `--batch MANIFEST --output-dir DIR` (`--dry-run`, `--overwrite`), report JSON | PR #31 |
| unreleased | FR-REPRO-01 `--save-project FIGURE.ycrystal`, manifest `save_projects`, provenance records | PR #32 |
| unreleased | FR-VALIDATION-01 validation tests, `scripts/benchmark_render.py`, `scripts/replay_check.py`, evidence report (no application change) | PR #33 |

Each has automated checks recorded in [PROGRESS.md](PROGRESS.md). Hands-on checks by a
person are still open for most of them; the user reports FR-VECTOR-01, FR-EXPORT-01,
and FR-REPRO-01 working.

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
- FR-REPRO-01: pixel differences of snapshot replays between systems or POV-Ray builds
  are unmeasured (same machine: identical pixels, never identical PNG bytes); not run
  on macOS; snapshots only for PNG renders from the command line.
- FR-VALIDATION-01: everything was measured on the Linux laptop only. Not run: the
  benchmark and the validation tests on the Mac, the full benchmark set (too heavy for
  the laptop), and replays between two machines (commands in
  `docs/development/validation.md`). The comparison with VESTA, OVITO, and CView is
  from their documentation only. No independent evaluation has taken place.
- JAC submission: referees need anonymous access to the program and a web page with
  documentation (per the journal's instructions; recheck them), but the repository
  is private. Decide how to provide access before submitting.
- Found during FR-REPRO-01, not changed: `save_project` (and so every project and
  snapshot) is written through `mkstemp` and ends up readable by the owner only (mode
  0600 on Linux/macOS), which matters for shared folders. The new provenance records
  behave the same. Decide whether to change it (a separate task).

## Latest development session

- **Date and machine:** 17 November 2026, the Linux laptop (Linux Mint 22.1, Intel
  Core Ultra 5 135U, 14 logical CPUs, 7.2 GiB, Python 3.12.3, POV-Ray 3.7.0.10 from
  apt).
- **Done first:** FR-REPRO-01 committed on `feature/repro-snapshots` (`86ba228`) after
  the user's review and hand test, PR #32. CI passed: pre-commit, docs, Ubuntu full
  suite, and macOS without windows. Merged at `e7ec99f`, as the user asked.
- **Then:** FR-VALIDATION-01 on branch `feature/validation` from `e7ec99f`, submitted
  as PR #33 after the user's review. The private plan was read but not changed.

Summary of FR-VALIDATION-01 changes (no file under `src/` changed):

- `tests/test_validation.py` (new, 55 tests; 26 with real POV-Ray), checking:
  - the scene file against the shared geometry;
  - ray-traced atoms, periodic images, bonds, and arrows against the camera model;
  - that fitted views are never clipped;
  - that styles change no scientific data;
  - shadows, soft shadows, reflection, and refraction.
- `tests/test_validation_scripts.py` (new, 4 tests; 1 with real POV-Ray).
  `tests/conftest.py::fake_povray` is shared now (moved from
  `test_reproducibility.py`, with a colour setting).
- `scripts/benchmark_render.py` and `scripts/replay_check.py` (new).
- Documentation:
  - new developer pages `docs/development/validation.md` (evidence, tolerances,
    results), `comparison.md`, and `independent-evaluation.md`, all in the navigation;
  - raw results in `docs/development/validation-results/`;
  - fixture README (real vs synthetic), CONTRIBUTING, changelog.

Tests and runs on the laptop:

| Check | Result |
| --- | --- |
| New and affected test files with `YCRYSTAL_REQUIRE_INTEGRATION=1` (real POV-Ray) | 84 passed, none skipped |
| `YCRYSTAL_REQUIRE_INTEGRATION=1 pytest -m "not gui" -q` | 702 passed, 172 GUI tests deselected (they still collect), none skipped |
| `benchmark_render.py --quick --scale 0.5 --repeats 3` | 9 cases recorded (`docs/development/validation-results/`); glass is by far the costliest (65 s at 400 × 300) |
| `replay_check.py` on the same laptop | 9 of 9 identical pixels |
| Lint, pre-commit on the changed files, `scripts/docs_examples.py`, `zensical build --clean --strict` | Clean |

Not done: GUI tests (no GUI code changed), the full benchmark, macOS, replays between
two machines, CI; hands-on runs by a person. A first benchmark run measured memory
wrongly (it counted the benchmark's own process); it was discarded and the method fixed
(see PROGRESS.md).

## Next recommended steps

1. Watch the CI of PR #33 and merge it when it passes. The new tests add about 1 min
   of POV-Ray renders per CI job.
2. On the Mac, run:
   - the validation tests;
   - `scripts/benchmark_render.py --quick --scale 0.5 --repeats 3`;
   - `scripts/replay_check.py` on a reference set from the other machine (copy the
     `snapshots` folder of a benchmark run).

   Record the results in `docs/development/validation-results/` and the report (see
   `docs/development/validation.md`).
3. Try the mapping rows of the Import Style dialog by hand once (only scripted GUI
   checks so far), for example with `tests/fixtures/BaZrO3.cif` and
   `examples/grey-studio.ycstyle` as in the examples guide; and the View along buttons
   in every order (the camera fix of PR #30).
4. Watch CI for an intermittent failure: one local full run of PR #30's suite reported
   1 failure that did not reproduce (PR #30's CI and three later full runs passed); its
   name was not captured.
5. Optional check (no new work): place an exported PDF in a LaTeX or Word document and
   check its size there.

FR-GALLERY-01 (in the private plan) is **not** authorized by this record; it needs its
own request.

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
| Styles from the command line (FR-STYLE-CLI-01) | Verified by CI (PR #28, Ubuntu, full suite) | Verified 17 Nov 2026 (automated, real POV-Ray; CI without windows) | Not tested |
| Element mapping for styles (FR-STYLE-MAP-01) | Verified by CI (PR #29, Ubuntu, full suite) | Verified 17 Nov 2026 (automated, real POV-Ray, scripted dialog screenshots; CI without windows) | Not tested |
| View and framing policies (FR-CAMERA-01) | Verified by CI (PR #30, Ubuntu, full suite) | Verified 17 Nov 2026 (automated, real POV-Ray; CI without windows) | Not tested |
| Batch manifests (FR-BATCH-01) | Verified by CI (PR #31, Ubuntu, full suite under Xvfb) | Verified 17 Nov 2026 (automated, real POV-Ray; CI without windows) | Not tested |
| Snapshots and provenance (FR-REPRO-01) | Verified 17 Nov 2026 on the Mint laptop (automated, real POV-Ray 3.7.0.10; the user's hand test) and by CI (PR #32, full suite under Xvfb) | CI only (PR #32, tests without windows, real POV-Ray); not run on the Mac itself | Not tested |
| Validation suite and benchmark (FR-VALIDATION-01) | Verified 17 Nov 2026 on the Mint laptop (tests with real POV-Ray; benchmark quick set at half size; replay check on the same machine); CI of PR #33 | Not tested | Not tested |
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
- Validation (FR-VALIDATION-01):
  - Images are checked by measured properties, never against stored pixels.
  - Tolerances: sphere centre 0.5 px, disc area 8 %, fitted bounds 1.5 px, scene file
    5e-7 Å; each is justified in `docs/development/validation.md`.
  - Views for image checks are chosen analytically on a 10° grid.
  - The benchmark uses the production command in new processes (median and range;
    peak memory through a launcher process, see PROGRESS.md).
  - The comparison with other programs rests on their documentation only, quoted with
    links.
  - Evaluator answers are written only by the evaluators.
- Snapshots (FR-REPRO-01): the snapshot is an ordinary `.ycrystal` project (no new
  recipe format, no project schema change) holding the resolved scene, camera, and
  output size; the image is rendered from the saved snapshot; image, snapshot, and
  record are moved into place only after a successful render, the record last.
  Snapshots drop the absolute `path` from the structure's import record; provenance
  paths are relative to the record's folder, files outside it get `path: null` (name and
  SHA-256 only). Existing snapshot/record files need `--overwrite`; the input, style,
  image, or manifest are never replaced; `--render` still replaces its PNG. Manifest key
  `save_projects` is top-level (schema 1 kept; older Ycrystal refuses the unknown key);
  report schema 1 gains `project`/`provenance` per job. The image SHA-256 is a
  fingerprint only: POV-Ray writes the render time into every PNG.
- Batch (FR-BATCH-01): validate the whole manifest first, report every problem, render
  nothing if any (status 2); sequential jobs; no overwriting without `--overwrite`; a
  failed job does not stop the others (status 1); PNG only; paths relative to the
  manifest; unknown keys refused; `max_atoms` default 20,000.
- Views (FR-CAMERA-01): one rule for the window and `--view` (`core/camera.py::axis_view`);
  a, b, c are real-space vectors; a saved camera is kept unless a view, a fixed height,
  or `--camera-policy fit` is asked for; fitted views include whole arrows; a fixed
  visible height that does not fit is an error, never a crop. No reverse views on the
  command line (`--view -a` would clash with option parsing).
- Element mapping (FR-STYLE-MAP-01): explicit only, never inferred; unmapped elements
  match by symbol; ambiguity (shared targets, a mapped element landing on one with its
  own settings) is an error, never resolved by order; per-atom settings never follow a
  mapping; the mapping is not stored in the style. CLI syntax `SOURCE=TARGET`, `-` to
  leave out. The dialog hook is now `MainWindow.ask_style_import` (was
  `ask_style_parts`).
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
