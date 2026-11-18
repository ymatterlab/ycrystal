# Development handoff

The state of Ycrystal for continuing work on another machine: the Linux Mint laptop, the
office Mac mini, or the Windows 11 laptop. Rules for Claude Code are in `CLAUDE.md` at
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
- **Windows support** (requested by the user on 17 November 2026), branch
  `feature/windows`, PR #35: completed on a Windows 11 laptop on 18 November 2026. All
  automated tests pass there with POV-Ray for Windows, and the user tested Ycrystal by
  hand and reports that it works well. PR #35 was merged after CI passed (merge
  commit `ae01f43`). PR #36 (branch `ci/windows-povray`) makes Windows CI render with
  the real POV-Ray for Windows, installed from the `ci-assets` release (see
  [docs/development/windows-port.md](development/windows-port.md#pov-ray-for-windows-on-ci));
  merged. PR #39, branch `feature/windows-install` (the user's request for a simpler Windows
  installation): `scripts\install-windows.ps1`, a Start-menu entry and `.ycrystal`
  file type through `--install-desktop`, and POV-Ray's editor question reported
  instead of waited for (see
  [windows-port.md](development/windows-port.md#installation-in-one-command)).
  Merged before: FR-STYLE-CLI-01 (PR #28), FR-STYLE-MAP-01 (PR #29), FR-CAMERA-01
  (PR #30), FR-BATCH-01 (PR #31), FR-REPRO-01 (PR #32; the user tested it by hand),
  FR-VALIDATION-01 (PR #33), and FR-GALLERY-01 with the next-tests audit (PR #34,
  merge commit `5b72f92`). Nothing else is open or authorized;
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
| unreleased | FR-GALLERY-01 publication gallery (`examples/publication/`, `scripts/make_gallery.py`), gallery and manuscript-figure pages (no application change) | PR #34 |
| unreleased | Maintenance: Windows 11 support with POV-Ray for Windows 3.7 (no FR ID) | PR #35 (`ae01f43`) |
| unreleased | Maintenance: Windows CI with the real POV-Ray for Windows (`ci-assets` release) | PR #36 (`8051f04`) |
| unreleased | Maintenance: Windows installation script, Start-menu entry and `.ycrystal` file type (`--install-desktop` on Windows), editor question reported (no FR ID) | PR #39 |

Each has automated checks recorded in [PROGRESS.md](PROGRESS.md). Hands-on checks by a
person are still open for most of them; the user reports FR-VECTOR-01, FR-EXPORT-01,
and FR-REPRO-01 working, and Ycrystal on Windows working well.

Known limitations and unresolved issues:

- Background pictures show only their average colour in the live VTK view; there is no
  rename/delete UI for personal materials; live-view speed with thousands of vector
  arrows is unmeasured; the Lighting Setup overview does not draw vector arrows.
- macOS: Ycrystal runs from the source checkout. There is no application bundle, so the
  Dock and the menu bar show "Python", and `.ycrystal` files do not open by double click.
- macOS: nothing has been checked by hand yet, and no Retina display was available (see
  [Cross-platform status](#cross-platform-status)).
- Windows: Ycrystal runs from the source checkout, installed by
  `scripts\install-windows.ps1` and started from the Start menu (or
  `.venv\Scripts\ycrystal.exe`). POV-Ray for Windows renders
  one copy at a time (Ycrystal reports a copy the user has open), reports no progress
  percentage, and takes the keyboard focus during renders started from a terminal.
  POV-Ray for Windows shows its About box at its second start and then every 14 days;
  renders wait until the user clicks OK (documented; Ycrystal changes no POV-Ray
  setting). Its question about a missing editor at every start is now reported by
  Ycrystal instead of waited for. Rendering with a `%TEMP%` path outside a legacy
  code page (for example a Chinese user name on a Western-European Windows) is
  unverified.
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
- FR-GALLERY-01: the gallery was rendered on the Linux laptop only. Its snapshots
  have not been replayed on another machine. Figure 1 (schematic, screenshot) and the
  plots of Figure 4 are still to be made (`docs/development/manuscript-figures.md`).
- JAC submission: referees need anonymous access to the program and a web page with
  documentation (per the journal's instructions; recheck them). The repository is now
  public, so the program can be cloned without an account; the documentation web page
  is still to be decided.
- Found during FR-REPRO-01, not changed: `save_project` (and so every project and
  snapshot) is written through `mkstemp` and ends up readable by the owner only (mode
  0600 on Linux/macOS), which matters for shared folders. The new provenance records
  behave the same. Decide whether to change it (a separate task).

## Latest development session

- **Date and machine:** 18 November 2026, a Windows 11 laptop (x64, 125 % display
  scale, Python 3.12.10 from python.org, POV-Ray for Windows 3.7.0 from the official
  installer).
- **Done:** the Windows port on `feature/windows`, continuing PR #35 (summary
  in [PROGRESS.md](PROGRESS.md#windows-port-continued-on-a-windows-computer-18-november-2026),
  details in [windows-port.md](development/windows-port.md)):
  - experiments with the real POV-Ray for Windows answered the takeover's ten
    questions; its source code (GitHub, `3.7-stable`) explained the single-instance
    and command-line rules;
  - it takes the keyboard focus (now held by the window while it runs) and keeps a
    single instance (now checked first and explained; Ycrystal's own renders take turns);
  - the window's renders of POV-Ray for Windows run through `subprocess.Popen`, since
    PySide6's `QProcess` cannot start a program minimised;
  - include files and settings found through the registry's `DocPath`; taskbar
    identity and an `.exe` filter for the executable dialog;
  - a bug of the new process backend (renders waiting for ever after a window closed
    mid-render) found by the GUI tests and fixed, with a regression test.
- **Then:** the user tested Ycrystal by hand on the laptop ("it works well") and asked
  for a documentation audit (Windows commands name `ycrystal.exe` and `python.exe`; the
  `py` launcher needs a terminal opened after Python's installation), a commit, and the
  merge of PR #35 once CI passes. CI passed (Ubuntu, macOS, Windows, docs,
  pre-commit) after one test fix (`metals.inc` exists in Ubuntu's system include
  folder); merged at `ae01f43`.
- **Then (PR #36):** the user chose to keep the official POV-Ray for Windows installer
  as an asset of a `ci-assets` release (povray.org blocks CI downloads). Screenshots
  taken by the probe on the runner showed two POV-Ray dialogs that wait even with
  `/EXIT` (the editor question; the About box from the second start on); the job now
  pre-sets `UseEditors=0` and `ItsAboutTime`. The Windows job is no longer
  experimental: 727 passed, 2 skipped (POSIX-only), with
  `YCRYSTAL_REQUIRE_INTEGRATION=1`.
- **Then:** PR #36's CI passed on its last commit `3535387` (run 44255680680: Ubuntu
  900 passed, 1 skipped; macOS 728 passed, 1 skipped; Windows 727 passed, 2 skipped;
  docs and pre-commit pass), and the user merged it (`8051f04`).
- **Then (PR #39, branch `feature/windows-install`):** the user asked whether Windows could be
  installed more simply, and to implement it like the other work. Done (details in
  [PROGRESS.md](PROGRESS.md#windows-installation-in-one-command-18-november-2026)):
  - `scripts\install-windows.ps1`: Python 3.12 and POV-Ray for Windows through
    `winget` (whose POV-Ray package is the official installer), `.venv`, the
    Start-menu entry, and the renderer check, in one command;
  - `--install-desktop` on Windows: a Start-menu shortcut with Ycrystal's
    application id, an icon, and the `.ycrystal` file type;
  - POV-Ray's question about its missing editor is reported at once instead of
    waited for.

  Tried on the laptop: the script on a fresh copy of the checkout, and the Start-menu
  entry and a project opened by scripted clicks. The laptop's Start menu now has
  **Ycrystal**, pointing at its checkout's `.venv` (`--uninstall-desktop` removes it).
- **Not done:** nothing run on Linux or macOS on a real machine in this session (CI ran
  them); GUI tests on Windows CI (run them on a Windows computer).
- **Then, on the Linux laptop (Python versions):** the user merged PR #38 (3.13 on
  macOS, `e5cf291`) and asked for Python 3.12, 3.13, and 3.14 on PR #39:
  `requires-python >=3.12`, the installation script accepting 3.12–3.14, and CI jobs
  for 3.13 and 3.14 within twice the 3.12 CI cost. Commit `f581801`; CI run
  44366127112 passed, Ubuntu 904 passed / 5 skipped on each of 3.12, 3.13, and 3.14,
  at 1.8× the job time (details in
  [PROGRESS.md](PROGRESS.md#python-312-313-and-314-18-november-2026)). Not run: 3.13
  and 3.14 on Windows and on a real Linux machine, the script's `py` search for them.
- **Then, on the Windows laptop (Python 3.13 and 3.14 on Windows):** the user asked to
  test them there. Python 3.13.17 and 3.14.10 (python.org builds, `winget`, per user)
  were installed next to 3.12.10. For each, the installation script in Windows
  PowerShell 5.1 (`-Python`, `-Dev`, `-NoStartMenu`) on a fresh copy of the checkout:
  "Ycrystal is ready.", renderer check passed, every pin from wheels. Then the full
  suite with real windows and POV-Ray for Windows: **906 passed, 3 skipped** on both,
  as on 3.12 (details in
  [PROGRESS.md](PROGRESS.md#python-313-and-314-on-windows-18-november-2026)). Still not
  run: the script's `py` search finding 3.13 or 3.14 when no 3.12 is installed; 3.14 on
  macOS; 3.13 and 3.14 on a real Linux machine.
- **Then (installation without Git):** at the user's remark, the README and the install
  guide make Git optional: download the ZIP from GitHub, unpack, install in
  `ycrystal-main`. Tried on the Windows laptop: a downloaded ZIP of the branch, no `.git`,
  the installation script passed ("Ycrystal is ready."). Not tried on Linux or macOS
  (see [PROGRESS.md](PROGRESS.md#installation-without-git-18-november-2026)).

Earlier, on 17 November 2026:

- **Date and machine:** 17 November 2026, the Linux laptop (Linux Mint 22.1, Intel
  Core Ultra 5 135U, 14 logical CPUs, 7.2 GiB, Python 3.12.3, POV-Ray 3.7.0.10 from
  apt).
- **Done first:** FR-GALLERY-01 and the next-tests audit, PR #34. CI passed (Ubuntu
  881 passed, macOS 709 passed, the gallery script running there for the first
  time); merged at `5b72f92`, as the user asked.
- **Then:** the Windows port, on the user's request and decisions (native Ycrystal +
  POV-Ray for Windows; a pushed branch with an experimental Windows CI job). The
  user then chose to continue it on a real Windows computer: this session leaves the
  groundwork and [a takeover page](development/windows-port.md) on `feature/windows`,
  draft PR #35. Local check: `pytest -m "not gui"` 718 passed, 1 skipped (the
  Windows-only test).

Earlier in the same session:

Summary of FR-GALLERY-01 changes (no file under `src/` changed):

- `examples/publication/`:
  - README (cases, files, provenance, licences, commands);
  - `gallery.json` (five jobs, mapping Sr → Ba and Ti → Zr, a 9 Å scale for both
    perovskites, `save_projects`);
  - `styles/paper.ycstyle` and `styles/cover.ycstyle`, generated by
    `scripts/make_examples.py::publication_styles`;
  - `structures/`: SrTiO3 and BaZrO3 copied from the fixtures, and kyanite from the
    COD (entry 1008755, CC0, authors credited; also in `THIRD_PARTY_NOTICES.md`).
- `scripts/make_gallery.py`:
  - runs the batch from a temporary copy of the inputs;
  - renders two variants from the SrTiO3 snapshot;
  - deletes the inputs and replays every snapshot;
  - writes the figure-methods table and, optionally, thumbnails.
- Documentation:
  - `docs/guide/gallery.md`, with thumbnails in `docs/assets/gallery/` (seven JPEGs,
    17–26 KB) and the recorded methods table;
  - `docs/development/manuscript-figures.md`;
  - the independent evaluation checklist now uses the supplied style and manifest;
  - examples guide, CONTRIBUTING, changelog.
- `tests/test_gallery.py` (new, 7 tests; 1 runs the whole script with real POV-Ray).

Tests and runs on the laptop:

| Check | Result |
| --- | --- |
| `scripts/make_gallery.py --out artifacts/gallery --thumbnails docs/assets/gallery` (1600 × 1200) | 7 figures rendered; 7 of 7 snapshots replayed with identical pixels after the inputs were deleted; methods table written |
| `tests/test_gallery.py` with `YCRYSTAL_REQUIRE_INTEGRATION=1` | 7 passed |
| `YCRYSTAL_REQUIRE_INTEGRATION=1 pytest -m "not gui" -q` | 709 passed, 172 GUI tests deselected, none skipped |
| `scripts/docs_examples.py`, `pre-commit` on the new and changed files, `zensical build --clean --strict` | Clean |

Not done: GUI tests (no GUI code changed), macOS, replays on another machine, CI;
hands-on runs by a person.

## Next recommended steps

1. On the Mac mini, first: `git checkout main && git pull`, then check whether PR #36
   is merged (`gh pr view 36`); if not, merge it when the user asks (its CI passed).
   Reinstall into the existing `.venv` (`.venv/bin/python -m pip install -e ".[dev]" -c
   constraints.txt`; no dependency changed) and run the full suite with real windows
   (900 passed, 1 skipped expected). The Windows changes keep `povray` on macOS on the
   same `QProcess` path as before, but nothing of them has run on a real Mac yet.
2. Windows, later: a fuller hands-on check on a second Windows computer when one is
   available; decide whether Ycrystal should notice POV-Ray for Windows' About box (see
   [windows-port.md](development/windows-port.md#still-open)).
3. Run the tests of [docs/development/next-tests.md](development/next-tests.md)
   (audited 17 November 2026, counts updated 18 November), in its order:
   - on the Mac mini: the full suite with real windows (900 passed and 1 skipped
     expected, as on Ubuntu CI for PR #36), the memory
     check, the benchmark, replays of the Linux reference sets, and the gallery;
   - by hand on the Mac and the laptop;
   - a clean-computer dry run.

   Record results only as they are obtained.
4. For the manuscript: draw the workflow schematic and take the window screenshot
   (Figure 1), make the plots of Figure 4 from the recorded data, and have two
   independent evaluators work through the checklist.
5. Try the mapping rows of the Import Style dialog by hand once (only scripted GUI
   checks so far), for example with `tests/fixtures/BaZrO3.cif` and
   `examples/grey-studio.ycstyle` as in the examples guide; and the View along buttons
   in every order (the camera fix of PR #30).
6. Watch CI for an intermittent failure: one local full run of PR #30's suite reported
   1 failure that did not reproduce (PR #30's CI and three later full runs passed); its
   name was not captured.
7. Optional check (no new work): place an exported PDF in a LaTeX or Word document and
   check its size there.

Every request of the private plan's section 15 is now merged or in review. Nothing
further is authorized by this record; new work needs its own request.

Still open from the macOS task: the [hands-on macOS checklist](#hands-on-checks-on-a-mac).

Suggestions only — not approved, ask before starting any of them:

- A command-line option for PDF/JPEG (`--render figure.pdf --dpi 600`); the CLI still
  writes PNG only.
- A macOS application bundle or launcher (name and icon in the Dock, opening
  `.ycrystal` files from Finder).
- Windows: progress percentages from POV-Ray for Windows' window title (see
  windows-port.md); a packaged installer with its own Python (needs a freezing tool and
  code signing).
- From earlier sessions: hide the disabled Bottom/Clouds rows for the Image background
  type; a way to manage personal materials; hands-on checks of the unreleased features,
  then the next release (FR-EXPORT-01 and the branding): move the changelog's
  "Unreleased" section under a version, bump `__version__`, and run the checklist in
  `docs/development/release.md` before tagging, when the user decides.

Dependencies and blockers:

- The repository is public, so GitHub's standard hosted runners, macOS included, cost
  nothing. If it became private again, macOS minutes would be billed at a higher rate
  than Linux minutes; then restrict the macOS job (for example to `main` and manual runs).
- GitHub's hosted Macs have no GPU, so the GUI tests cannot run there reliably; they
  need a real Mac.
- Windows: POV-Ray for Windows is a GUI program without a `povray` command. Ycrystal
  drives `pvengine64.exe` with `/EXIT /NR +GAscene.log scene.ini` (PR #35);
  confirmed on a Windows 11 laptop on 18 November 2026. It cannot render while a copy
  of it is open with *Keep Single Instance* on (its default); Ycrystal says so.

## Cross-platform status

Status words: **verified** (tested on that system, date given), **partial** (some of it
tested), **not tested**, **known issue**. Linux results for the macOS changes are the
user's report for PR #22.

| Area | Linux Mint 22.1 / Ubuntu 24.04 | macOS 15 (Apple silicon) | Windows |
| --- | --- | --- | --- |
| Install from source with `constraints.txt` | Verified on `main` (CI, PR #19) | Verified 16 Nov 2026 | Verified 18 Nov 2026 (Windows 11 laptop, Python 3.12.10 from python.org); also CI (PR #35) |
| Command line: `--version`, `--check-renderer`, `--render`, `--export-pov` | Verified (PR #22, user report) | Verified 16 Nov 2026 | Verified 18 Nov 2026 (POV-Ray for Windows 3.7.0) |
| POV-Ray discovery and include files | Verified (PR #22, user report) | Verified 16 Nov 2026 (Homebrew) | Verified 18 Nov 2026: `pvengine64.exe` found outside `PATH` (registry, Program Files), include files in `Documents\POV-Ray\v3.7` (registry `DocPath`); CI installs it from the `ci-assets` release (PR #36) |
| Tests without windows (structures, projects, export, rendering, `QProcess`) | Verified (PR #22, user report) | Verified 16 Nov 2026 | Verified 18 Nov 2026 with POV-Ray for Windows (full suite: 898 passed, 3 skipped by design); CI with POV-Ray for Windows since PR #36 |
| GUI tests (real windows, OpenGL) | Verified (PR #22, user report; CI under Xvfb) | Verified 16 Nov 2026 (non-Retina display) | Verified 18 Nov 2026 (172 GUI tests in the full suite, 125 % display scale) |
| PNG/PDF/JPEG export (FR-EXPORT-01) | Verified by CI (PR #23, Ubuntu, full suite) | Verified 16 Nov 2026 (automated, real POV-Ray; CI without windows); the user reports it working | Verified 18 Nov 2026 (automated, POV-Ray for Windows, one laptop) |
| Styles from the command line (FR-STYLE-CLI-01) | Verified by CI (PR #28, Ubuntu, full suite) | Verified 17 Nov 2026 (automated, real POV-Ray; CI without windows) | Verified 18 Nov 2026 (automated, POV-Ray for Windows, one laptop) |
| Element mapping for styles (FR-STYLE-MAP-01) | Verified by CI (PR #29, Ubuntu, full suite) | Verified 17 Nov 2026 (automated, real POV-Ray, scripted dialog screenshots; CI without windows) | Verified 18 Nov 2026 (automated, POV-Ray for Windows, one laptop) |
| View and framing policies (FR-CAMERA-01) | Verified by CI (PR #30, Ubuntu, full suite) | Verified 17 Nov 2026 (automated, real POV-Ray; CI without windows) | Verified 18 Nov 2026 (automated, POV-Ray for Windows, one laptop) |
| Batch manifests (FR-BATCH-01) | Verified by CI (PR #31, Ubuntu, full suite under Xvfb) | Verified 17 Nov 2026 (automated, real POV-Ray; CI without windows) | Verified 18 Nov 2026 (automated, POV-Ray for Windows, one laptop) |
| Snapshots and provenance (FR-REPRO-01) | Verified 17 Nov 2026 on the Mint laptop (automated, real POV-Ray 3.7.0.10; the user's hand test) and by CI (PR #32, full suite under Xvfb) | CI only (PR #32, tests without windows, real POV-Ray); not run on the Mac itself | Verified 18 Nov 2026 (automated, POV-Ray for Windows, one laptop); no replay between machines |
| Validation suite and benchmark (FR-VALIDATION-01) | Verified 17 Nov 2026 on the Mint laptop (tests with real POV-Ray; benchmark quick set at half size; replay check on the same machine) and by CI (PR #33, full suite under Xvfb) | CI only (PR #33, tests without windows, real POV-Ray); benchmark and replay check not run on the Mac | Validation tests verified 18 Nov 2026 (automated); benchmark and replay scripts only as run by the tests |
| Publication gallery (FR-GALLERY-01) | Verified 17 Nov 2026 on the Mint laptop (full-size render of all 7 figures, replay of all snapshots, gallery tests); CI of PR #34 | Not tested | Gallery test verified 18 Nov 2026 (the script at test size); full-size gallery not rendered |
| Hands-on use of the window | Partial (the user's own use; most post-0.2.0 features not checked by hand) | Not tested | The user reports it working well (hands-on test, 18 Nov 2026); a scripted run of the window passed |
| HiDPI / Retina display | Not tested | Partial: emulated 2× scale only | Partial: 125 % scale (device pixel ratio 1.25), GUI tests and a scripted run |
| Menu launcher, file association | Verified on `main` (`--install-desktop`) | Known issue: none exists; the option refuses | Verified 18 Nov 2026 on one laptop: Start-menu entry starts the window without a console, a `.ycrystal` file opens from File Explorer (scripted clicks); pinning to the taskbar not tried |
| Installation script | Not applicable | Not applicable | Verified 18 Nov 2026 on one laptop with Python and POV-Ray already installed (Windows PowerShell 5.1, fresh `.venv`, rerun); the `winget` installs of Python and POV-Ray and the editor prompt not run |
| Continuous integration | Verified (PR #22, user report) | Job runs without GUI tests by design (PR #22, user report) | Verified: tests without windows with POV-Ray for Windows on every pull request (PR #36, 18 Nov 2026) |

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

Windows 11 (set up 18 November 2026 on a laptop with a 125 % display scale; PowerShell
from the repository root). The installation script installs Python 3.12 and POV-Ray for
Windows with `winget` where missing, `.venv` with the developer tools (`-Dev`), the
Start-menu entry, and checks the renderer:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\install-windows.ps1 -Dev
# By hand instead: winget install --id Python.Python.3.12 --exact --scope user;
# winget install --id PersistenceOfVisionRaytracer.POVRay --exact; a new terminal;
# py -3.12 -m venv .venv; .venv\Scripts\python.exe -m pip install -e ".[dev]" -c constraints.txt
.venv\Scripts\ycrystal.exe --check-renderer
$env:YCRYSTAL_REQUIRE_INTEGRATION = "1"
.venv\Scripts\python.exe -m pytest -q -rs      # GUI tests open windows for several minutes
.venv\Scripts\pre-commit.exe run --all-files
py -3.12 -m venv .venv-docs; .venv-docs\Scripts\python.exe -m pip install -r docs/requirements.txt
.venv-docs\Scripts\zensical.exe build --clean --strict
```

- Windows: the `python` on `PATH` of a fresh Windows is a Microsoft Store alias that
  opens the Store (and hangs a script); use `py -3.12` or the venv's `python.exe`.
  "The term 'py' is not recognized" means the terminal was opened before Python was
  installed (VS Code's terminal until VS Code restarts): open a new one.
- Windows: a clone made from `main` before `.gitattributes` existed has CRLF text files
  (Git for Windows sets `core.autocrlf=true`), and switching to a branch with
  `.gitattributes` does not rewrite them; tests that hash tracked files then fail. Use a
  fresh clone of a branch that has `.gitattributes`. (On 18 November 2026 the files of
  this checkout were converted to LF only where the result hashed to the blob in the
  index, then `git add -u` refreshed Git's file information; nothing was staged.)
- Windows: POV-Ray for Windows must not be open while tests or Ycrystal render (it
  keeps a single instance; Ycrystal reports it). Run nothing else that renders in
  parallel with the test suite.

## Not transferred by Git

| Item | Status | What to do |
| --- | --- | --- |
| `IMPLEMENTATION_PLAN.md` | Private, gitignored | Copy manually (USB drive or private storage) to the repository root; keep it untracked |
| Other private planning files at the root (older plan copies, the owner's notes) | Untracked; excluded in this checkout's `.git/info/exclude`, not in `.gitignore` | Copy manually if wanted, and add them to `.git/info/exclude` in the new checkout; never `git add -A` without checking |
| `.venv/`, `.venv-docs/` | Gitignored | Recreate on each machine (never copy between systems) |
| `artifacts/` | Gitignored | Local screenshots and renders. Exception: the reference sets for replays between machines, `artifacts/gallery/figures/` and `artifacts/validation/bench-linux/snapshots/`, must be copied byte for byte to the other computer (see `docs/development/next-tests.md`) |
| `build/`, `dist/`, `.cache/`, `site/` | Gitignored | Generated; recreate if needed |
| Ycrystal settings | Outside the repository | Preferences, favourites, and personal materials are per machine (`QSettings`): `~/.config/Y-Matter Lab/` on Linux; `~/Library/Preferences/com.y-matter-lab.Ycrystal.plist` and `~/Library/Application Support/Y-Matter Lab/Ycrystal/` on macOS; the registry key `HKEY_CURRENT_USER\Software\Y-Matter Lab\Ycrystal` and `%APPDATA%\Y-Matter Lab\Ycrystal\` on Windows |
| Claude Code memory | Outside the repository | Local to each machine; `CLAUDE.md` and this file replace it |

## Decisions and deferred features

- **FR-VECTOR-02 (CSV/TSV vector tables) is deferred.** Its specification is kept in the
  private plan for possible future use; do not implement or scaffold it unless the user
  explicitly asks to reactivate it. No feature request has been rejected so far.
- One repository and one codebase for all systems; no platform branches. Platform checks
  stay in `gui/native.py`, `desktop.py`, `render/povray.py`, and `tests/conftest.py`.
- A resize of the view is not a change of the figure (16 November 2026).
- macOS CI runs without GUI tests; the GUI is verified on a real Mac.
- Python: 3.12, 3.13, and 3.14 are supported; `requires-python >=3.12` (18 November
  2026). CI runs 3.12 on every system and 3.13 and 3.14 on Ubuntu only, within the
  user's limit of twice the 3.12-only CI cost; check this when adding jobs. Windows
  with 3.13 and 3.14 was verified by hand on the laptop (full suite, 18 November 2026),
  not in CI.
- Vectors: Cartesian components in the structure frame; magnetic moments in μB,
  directions dimensionless; source defaults plus image overrides/suppressions; no
  inferred signs or magnetic symmetry; styles carry arrow appearance, never vectors.
- Pictures and custom materials are content-addressed (SHA-256 / content-derived ids);
  projects embed the custom definitions they use, so they open on a clean profile.
- Projects/styles are ZIP packages only when they carry a picture; otherwise JSON.
- Personal materials are stored in `QSettings` (`materials/personal`) with thumbnails in
  a `material-thumbnails/` folder (per machine, not in Git; locations above).
- Preview resolution presets are widths (Small 480, Medium 800, Large 1200, Custom).
- Gallery (FR-GALLERY-01):
  - The low-symmetry case uses kyanite, COD 1008755 (real, ordered, P-1, CC0, authors
    credited), not the invented triclinic fixture.
  - The SrTiO3 variants are rendered from the paper figure's snapshot with the cover
    style, so geometry, camera, and size are identical by construction.
  - Full-size renders stay out of Git. The docs carry only 480 px JPEG thumbnails of
    real renders, regenerated by the gallery script.
  - The independent-user sheet is the existing checklist, extended; no second sheet.
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
