# Ycrystal progress record

Last updated: 18 November 2026 (Windows installation in one command, branch `feature/windows-install`). Before that: Windows CI with the real POV-Ray for Windows (PR #36, merged at `8051f04`). Before that: the Windows port on a Windows computer (PR #35, merged at `ae01f43`). Before that: 17 November 2026 (Windows port started). Before that: FR-GALLERY-01, reproducible publication gallery, and an audit of the next tests on other computers (PR #34). Before that: FR-VALIDATION-01, scientific validation and benchmarks (PR #33). Before that: FR-REPRO-01, figure snapshots and provenance records (PR #32). Before that: FR-BATCH-01, batch manifests (PR #31). Before that: FR-CAMERA-01, view and framing policies (PR #30). Before that: FR-STYLE-MAP-01, element mapping for styles (PR #29). Before that: FR-STYLE-CLI-01, styles from the command line (PR #28). Before that: FR-EXPORT-01, PDF and JPEG export, and macOS support (see "Maintenance: macOS support and cross-platform tests"). M0–M6 complete (version 0.1.0, tag `v0.1.0`). Version 0.2.0 adds the post-0.1.0 features FR-COLOR-01 (PR #13), FR-RENDER-01 (PR #14), and FR-LIGHT-01 (PR #15); see the [0.2.0 checklist](development/release.md#checklist-for-020). Post-0.2.0 work: FR-MEASURE-01 (distance and bond-angle measurements; PR #16), FR-PREVIEW-01 (preview resolution; PR #17), FR-BGIMAGE-01 (background pictures) and FR-MATERIAL-01 (custom material variants; both PR #18), FR-VECTOR-01 (atom-attached vectors; PR #19), and FR-EXPORT-01 (PDF and JPEG export with publication sizes; PR #23); tag `v0.3.0` covers the work up to PR #22. Post-0.3.0: FR-STYLE-CLI-01 (styles from the command line; PR #28) and FR-STYLE-MAP-01 (element mapping for styles; PR #29), FR-CAMERA-01 (view and framing policies; PR #30), FR-BATCH-01 (batch manifests; PR #31), FR-REPRO-01 (figure snapshots and provenance; PR #32), FR-VALIDATION-01 (validation and benchmarks; PR #33), and FR-GALLERY-01 (publication gallery; PR #34). FR-VECTOR-02 (vector tables) is deferred. Repository private.

## Milestones

| Milestone | Goal | Status |
| --- | --- | --- |
| M0 | Desktop/render feasibility: Qt window, embedded VTK view, camera model, first POV-Ray render matching the view | **Complete** (see evidence and caveats) |
| M1 | File import (POSCAR/CIF/QE `ibrav=0`) and save/reopen projects | **Complete** (see evidence) |
| M2 | Navigation tools, selection, supercells, periodic bonds, cell boundary images | **Complete** (see evidence; drag handles are M5) |
| M3 | Complete figure workflow: preview, output frame, cancellation, final PNG | **Complete** (see evidence) |
| M4 | Material and environment galleries, assignment, lighting | **Complete** (see evidence) |
| M5 | Supercell drag handles, axis-constrained rotation, reusable styles, undo coverage | **Complete** (see evidence) |
| M6 | Installation path, launcher, user guide, release checks | **Complete** (see evidence and the [release checklist](development/release.md); publication is the maintainer's decision) |

## M0 acceptance evidence

Gate: launches on the target Mint machine; a rotated, panned, non-square view is
rendered by POV-Ray without mirroring or reframing; a useful message appears when
POV-Ray is missing.

| Check | Result | How |
| --- | --- | --- |
| Application launches on the target desktop | Pass | `ycrystal` started on the Mint X11 display; window screenshot captured by `scripts/m0_evidence.py` |
| Orbit / pan / zoom with the mouse | Pass | Qt mouse events sent to the real VTK widget (`tests/test_gui.py`): left drag orbits about the focal point; Shift + left and middle drag pan (the scene follows the cursor within 1.5 px); wheel and right drag zoom; Fit keeps the orientation |
| Navigation leaves coordinates unchanged | Pass | Structure arrays are read-only; equality is checked after navigation |
| Camera model = VTK view | Pass | VTK world-to-display vs model: ≤ 1e-6 px (GUI test); 1.7e-13 px measured; VTK camera matrices vs model for random views: ≤ 1e-9 px |
| POV-Ray render = camera model | Pass | Rotated + rolled + panned views at 480×270, 240×400, 300×300: sphere centres < 1 px, correct colours (no mirroring), correct disc sizes; a mirrored or 2-px-shifted expectation fails the same check |
| Mouse-navigated view, viewport vs POV-Ray | Pass | `scripts/m0_evidence.py`: 1100×607 viewport, view turned 49.8°, panned 1.08 Å, zoomed 1.21×; all 5 atoms found, max centre error 0.073 px in VTK and 0.115 px in the POV-Ray image; colours match |
| Render from the GUI does not block | Pass | `render_png` returns immediately; POV-Ray runs in `QProcess`; result checked after the event loop delivers it |
| Image size and alpha | Pass | Exact requested dimensions; transparent background has alpha 0; opaque background is white |
| Missing POV-Ray | Pass | GUI shows guidance and `.pov`/`.ini` export still works; `ycrystal --check-renderer` prints `FAIL: POV-Ray was not found on PATH…` and exits 1 |
| Broken POV-Ray build detected | Pass | A self-built 3.8.0-alpha compiled with `-ffast-math` (previously on this machine, since removed) rejected every camera without `angle`; the self-test and render errors explain this |
| Installed renderer | Pass | `sudo apt install povray` (1:3.7.0.10-3build4) at `/usr/bin/povray`, found on `PATH` without configuration; `ycrystal --check-renderer`: PASS, centres within 0.14 px; runs under the package's restricted `povray.conf` (writes only to `/tmp` and `.`) |
| Paths with spaces/non-ASCII | Pass | Render result copied to `…/Résultat final/render ü.png`; export to `exported scene ü.pov` |
| Automated suite | 52 passed, 0 skipped | `pytest -q -rs` with the installed `/usr/bin/povray` (no override); `ruff check` clean |
| Fresh install from `constraints.txt` | Pass | New venv on system Python 3.12.3 via `uv`; 52 tests passed |

Evidence files (local, not tracked: `artifacts/m0/`): `window.png` (application
screenshot), `viewport.png` and `render.png` (same view), `comparison.png`
(side by side), `render_atoms_markers.png` (analytic centres drawn on the POV-Ray
image), `scene.pov`/`scene.ini` (exported scene), `report.json` (environment, cameras,
per-atom errors). Regenerate with the command below.

### Caveats and unverified items

- POV-Ray 3.8 is not verified: no working 3.8 build is available on this machine
  (the self-built one was miscompiled and has been removed).
- `povray` prints a harmless warning when `~/.povray/3.7/povray.conf` does not exist.
- Mouse interaction was driven by synthetic Qt events through the real widget, not by
  a person. A hands-on check of drag feel is recommended but not a gate.
- `python3 -m venv` with the system interpreter needs `python3.12-venv` (not installed
  on the development machine); the verified route used `uv venv`.
- The CI workflow (`.github/workflows/ci.yml`) has not run yet; it needs a push.
- Not covered by M0 (later milestones): file import, projects, bonds, supercells,
  selection, view-direction buttons, render cancellation UI, preview, output-aspect
  frame, material presets.

## M1 acceptance evidence

Gate: equivalent reference inputs give the same scientific geometry; a project opens
after its source file is moved; unsupported QE/CIF cases are explained in the
interface and the guide.

| Check | Result | How |
| --- | --- | --- |
| Format detection and manual choice | Pass | Name + content (`test_readers.py`); misleading extensions resolved by content; undetectable files ask for a format; *File ▸ Open As…* / `--format` override |
| Si: POSCAR (primitive) = QE (`celldm(1)`, alat cell, crystal positions) | Pass | Cells equal the analytic fcc matrix (QE within 1e-8 Å); atoms matched modulo lattice translations |
| Si: conventional CIF (F d -3 m) = primitive POSCAR × P | Pass | `P = [[-1,1,1],[1,-1,1],[1,1,-1]]` recorded; 8 CIF atoms equal the analytic diamond positions |
| MgB2: Cartesian POSCAR = CIF (24 explicit symmetry operations) = QE (angstrom cell) | Pass | Cells equal the analytic hexagonal matrix; space group 191 recorded |
| SrTiO3: POSCAR (selective dynamics) = CIF (symbol, uncertainties) = QE (`A`, alat, labels `O1`/`O_2`, `if_pos`) | Pass | Equal geometry; identical movable flags from VASP and QE; labels kept separately from elements |
| Triclinic: POSCAR (negative scale = volume, Cartesian) = CIF (P1) = QE (bohr cell and positions) | Pass | Cell and positions equal the analytic triclinic formula within 1e-8 Å |
| VASP 4 without element line | Pass | Element mapping is requested; the misleading comment "In plane strained GaN" yields no guess; the mapping is recorded in provenance |
| Rejections with explanations | Pass | CIF partial occupancy (lists sites), overlapping sites, unknown block; QE `ibrav = 2`, `crystal_sg`, missing `CELL_PARAMETERS`; ambiguous QE label (`Cb`) asks for the element; truncated POSCAR ("…3 atoms, but only 1 coordinate line…"); not-a-structure file |
| Failed open keeps the current scene | Pass | Structure, geometry, and camera unchanged after each rejected file and after a damaged project (`test_gui_files.py`) |
| Project round trip | Pass | Exact equality of cell, positions, numbers, occupancy, labels, movable flags, metadata, display settings, hidden atoms, environment, camera, output |
| Reopen after the source file is moved | Pass | Source directory deleted; the project reopens in a new window with identical coordinates, hidden atoms, camera, and output settings (`test_project.py`, `test_gui_files.py`) |
| Versioning and damage | Pass | Newer schema refused with an update message; invalid JSON (with line), wrong format, missing schema, missing sections, inconsistent symbols, wrong array lengths reported clearly; atomic save leaves no temporary files |
| Unsaved changes | Pass | Title shows `*` for camera, display-setting, or output changes (undo back to the saved state clears it); close and open ask Save / Discard / Cancel; Cancel (or a cancelled Save dialog) keeps the window and scene |
| Documented limitations | Pass | *Help ▸ Supported File Formats* and `docs/FORMATS.md` |
| Automated suite | 127 passed, 0 skipped | `pytest -q -rs` with `/usr/bin/povray`; `ruff check` clean |

Hands-on check on the Mint display: `ycrystal tests/fixtures/MgB2.cif` starts with the
file open; opening `SrTiO3.pw.in` shows QE labels in the selection information;
opening `partial_occupancy.cif` shows the explanation while the scene stays.

### M1 caveats

- ~~The rendered image takes its aspect ratio from the window.~~ Resolved in M3: an
  explicit output size and frame; projects reopen with the same framing in any window.
- The view counts as part of the project: rotating marks it modified.
- POSCAR element lines with POTCAR suffixes (`Na_pv`) are reduced to the element; the
  raw token is not kept as a label.

## Windows installation in one command (18 November 2026)

Requested by the user after PR #36 was merged (`8051f04`): "is there a simpler method
for installation?", and to implement it like the other work. Branch
`feature/windows-install`. Details and the findings behind it:
[windows-port.md](development/windows-port.md#installation-in-one-command).

- `scripts/install-windows.ps1`: after `git clone`, one command installs Python 3.12
  and POV-Ray for Windows 3.7 with `winget` where missing (`winget` has the official
  installer, same checksum), `.venv` with the pinned packages, the Start-menu entry,
  and runs the renderer check. When POV-Ray would ask about its editor, it opens POV-Ray
  once with instructions. Rerunnable for updates.
- `ycrystal --install-desktop` on Windows (`desktop.py`, new `windows_shortcut.py`):
  - a Start-menu shortcut to `.venv\Scripts\pythonw.exe -I -m ycrystal.app` (no
    console window) with the application id `YMatterLab.Ycrystal`;
  - an `.ico` drawn from the SVG;
  - the `.ycrystal` file type under `HKEY_CURRENT_USER\Software\Classes`;
  - `--uninstall-desktop` removes all three.
- POV-Ray for Windows' question about a missing editor (`UseEditors` on and no
  `cmedit64.dll`, per its source) is now reported by `windows_engine_conflict()` with
  the remedy, so `--check-renderer`, previews, and renders fail at once instead of
  waiting at a dialog in a minimised window.
- Windows CI runs the script in Windows PowerShell 5.1 into a new `.venv`.
- Install guide (script first; the same steps by hand), README, troubleshooting,
  support matrix, rendering guide, architecture, reference, CLAUDE.md, CONTRIBUTING,
  changelog.

| Check | Result |
| --- | --- |
| The script in Windows PowerShell 5.1 on a copy of the checkout in a folder with a space, without `.venv` (Python 3.12 and POV-Ray already installed) | `.venv` created, packages installed, POV-Ray found, Start-menu entry installed, `PASS: … within 0.14 px`, "Ycrystal is ready.", exit status 0; a second run took 29 s |
| The Start-menu shortcut and a `.ycrystal` file opened as clicks do (`os.startfile`) | Each opened one Ycrystal window run by `pythonw.exe`, no console window; own taskbar button with the Ycrystal icon; the automatic preview rendered. `Get-StartApps`: AppID `YMatterLab.Ycrystal` |
| `tests/test_windows_desktop.py` (7 tests, 4 of them Windows-only) and the editor-question test; the updated platform and conflict tests | Passed on the laptop |
| Full suite on the laptop, `YCRYSTAL_REQUIRE_INTEGRATION=1 pytest -q -rs` (GUI tests with real windows, POV-Ray for Windows) | **906 passed, 3 skipped** (the POSIX-only tests), 12.4 min |
| `pre-commit run --all-files`; `zensical build --clean --strict` | Passed; no issues |

Not verified: the `winget` installs of Python and POV-Ray through the script and its
editor prompt (both programs and the editor were already on the laptop); pinning the
running window to the taskbar by hand.

## Windows CI with the real POV-Ray for Windows (18 November 2026)

Requested by the user after PR #35 was merged (`ae01f43`): render with POV-Ray for
Windows in GitHub's Windows CI job, which povray.org's browser challenge kept from
downloading the installer. Branch `ci/windows-povray`, PR #36.

- The official installer, unmodified (SHA-256 `2B1331641B6F…5BDC8`, checked on the
  user's download), is the asset of a new release `ci-assets` (not a Ycrystal
  release; notes give the licence and the source). The job downloads it with
  `gh release download` and its own token, refuses another checksum, installs it with
  `/S`.
- First run: the install worked, but every render waited. `scripts/windows_povray_probe.py`
  gained `--screenshots` (window texts and a desktop screenshot when a render times
  out; the job uploads them). Its screenshots showed two dialogs: "Could not load
  internal editor – download it?" (every start without the editor DLL) and, from the
  second start on, the About box (when `ItsAboutTime` has passed). POV-Ray's source
  (`pvedit.cpp`, `pvengine.cpp`) confirms both. The job now writes `UseEditors=0` and
  `ItsAboutTime=2147483647` into the runner's `pvengine.ini` before the first start.
- The laptop never showed the editor question to Ycrystal because the user installed
  the editor during the session (its DLLs appeared in the installation folder); this
  also explains the first probe render's 90-second wait.
- The Windows job is no longer experimental and runs with
  `YCRYSTAL_REQUIRE_INTEGRATION=1`.
- Users: the install guide asks to start POV-Ray once and settle the editor question;
  troubleshooting explains the About box (second start, then every 14 days).

| Check | Result |
| --- | --- |
| Windows job, run 44254469298 (`57f1afd`) | Renderer check `PASS: POV-Ray 3.7.0.0 … 0.14 px`; doctests and documentation examples pass; tests: 727 passed, 2 skipped (POSIX-only), 172 GUI deselected |
| Same run, other jobs | Ubuntu (full suite), macOS, docs, pre-commit: pass |
| Probe timeout reporting, on the laptop | Reproduced the single-instance error box: window title, button, and message reported; screenshot saved |

## Windows port, continued on a Windows computer (18 November 2026)

Requested by the user: run Ycrystal natively on Windows, keeping Linux Mint and macOS
working, on branch `feature/windows`. Machine: Windows 11 Enterprise (build 26300) laptop,
x64, 125 % display scale, UTF-8 system code page; Python 3.12.10 (python.org, installed
with `winget` for this work); POV-Ray for Windows 3.7.0 installed by the user. Details,
sources (POV-Ray's own source code for its command line and single-instance rules), and
the answers to the ten questions: `docs/development/windows-port.md`. The user then
tested Ycrystal by hand on the laptop and reports that it works well; Windows is
supported from a source checkout (`CLAUDE.md` targets updated), with Windows CI still
running without POV-Ray.

- **Found on the real system, and handled:**
  - POV-Ray for Windows makes itself the foreground window even when started
    minimised: the window holds the foreground (`LockSetForegroundWindow`) while it runs.
  - It keeps a single instance by default: a second copy shows a modal error box and
    waits. Ycrystal now checks first and explains (`windows_engine_conflict`), and its
    own renders take turns (`render/process.py`).
  - PySide6's `QProcess` cannot start it minimised: the window's renders run it through
    `subprocess.Popen` with a timer.
  - Its user files (include folder, `pvengine.ini`) are found through the registry's
    `DocPath`.
  - Exit status 0 also after a parse error (no image): already handled by
    `finish_job()`; messages come from its log.
- **Bug found and fixed during the work:** the first version of the `Popen` backend kept
  a "running" marker after a window closed with a render in progress, so every later
  render waited for ever (12 GUI tests failed). Cancelling now reports at once, and the
  process itself decides whether one runs; a regression test covers it.
- **Interface:** taskbar identity (own button and icon) and an `.exe` filter for *Set
  POV-Ray Executable…*, in `gui/native.py`.
- **Tests:** new contract tests in `tests/test_windows_povray.py`; tests that simulate a
  missing POV-Ray also hide an installed POV-Ray for Windows; the exported-scene test
  uses `render_arguments()`; a time-stamp flake in `test_preview_resolution.py` fixed.
- **Documentation:** install guide and README (Windows section), support matrix,
  troubleshooting, rendering guide, architecture, changelog, HANDOFF.

| Check | Result |
| --- | --- |
| `scripts/windows_povray_probe.py` | Finds `pvengine64.exe` outside `PATH`, version 3.7.0.0, include files present; renders with Ycrystal's command line in 2.3–2.8 s per small scene after the first start |
| Tests without windows, real POV-Ray, before the changes | 715 passed, 3 skipped, 1 failed (a test ran `pvengine64.exe scene.ini` without `/EXIT`; fixed) |
| GUI tests, first run with the changes | 160 passed, 12 failed (the `Popen` backend bug above; fixed) |
| Targeted files after the fixes (`test_windows_povray`, `test_render_queue`, `test_povray_jobs`, `test_platform`; the six GUI files that had failed) | 42 passed, 2 skipped; 68 passed then 1 (time-stamp flake, fixed) |
| Second copy of POV-Ray for Windows while one is open | Raw: modal "Commandline processing error", no image. `.venv\Scripts\python.exe -m ycrystal --check-renderer`: `FAIL` with the explanation in 0.7 s |
| Full suite, `YCRYSTAL_REQUIRE_INTEGRATION=1 pytest -q -rs` (GUI tests with real windows at 125 % scale; all POV-Ray tests with POV-Ray for Windows) | **898 passed, 3 skipped** (symbolic links, execute bit, POSIX permissions: by design), none failed; 12 min |
| CI's doctest list, `scripts/docs_examples.py`, `pre-commit run --all-files`, `zensical build --clean --strict` | All passed |
| `.venv\Scripts\ycrystal.exe --version`, `--check-renderer`, `--render` of `examples\SrTiO3-studio.ycrystal`, `--export-pov`, and the guide's PowerShell command for an exported scene | As documented; `PASS: POV-Ray 3.7.0.0 … 0.14 px`; the exported scene needs `Start-Process -Wait` (`&` does not wait for a window program) |
| Scripted run of the main window: capture, 3 previews, 1 final render, foreground watched | Draws correctly at scale 1.25; previews 2.6–2.7 s; render saved; the foreground never left Ycrystal |
| Hands-on test by the user on the laptop | "It works well" (the items tried were not recorded) |
| Documentation audit after the hands-on test (user's request) | Windows commands name the programs `.venv\Scripts\ycrystal.exe` and `python.exe`; the `py` launcher needs a terminal opened after Python's installation (checked: with the `PATH` a new terminal gets, `py -3.12 --version` gives Python 3.12.10); new troubleshooting rows; status wording; `CLAUDE.md`, CONTRIBUTING, pyproject classifiers |
| Not run | Linux and macOS in this session (their code paths are unchanged; CI of PR #35 checks them); a `%TEMP%` outside a legacy code page (this computer's code page is UTF-8) |

## Windows port, in progress (17 November 2026)

Requested by the user. Decisions by the user: native Ycrystal rendering with POV-Ray
for Windows 3.7 (`pvengine64.exe`), and a pushed branch with a Windows CI job. Branch
`feature/windows` from `main` at `5b72f92`, draft PR #35. **Not finished; nothing
here establishes that Ycrystal works on Windows.** Full record, sources, and the
experiments still needed: `docs/development/windows-port.md`.

- **Code.**
  - `render/povray.py` finds POV-Ray for Windows outside PATH (registry `Home`, the
    `ProgramFiles` folders, `POV-Ray\v3.7\bin`).
  - It starts it with `/EXIT /NR +GAscene.log scene.ini`, minimised, and reads its
    log file.
  - It reads its version from the file's version resource, never starting it.
  - It finds its include folders.
  - `render/jobs.py` and `render/process.py` use this. Linux and macOS arguments
    are unchanged.
- **Tests.**
  - Fakes are cross-platform (`conftest.python_program`; `.cmd` launchers on
    Windows), and the execute-bit test is skipped on Windows.
  - `tests/test_windows_povray.py` (10 tests) checks the Windows contract with a
    stand-in on any system.
  - `.gitattributes` keeps LF in Windows checkouts, and `make_examples.py` writes
    LF.
- **Tools.** `scripts/windows_povray_probe.py` reports how POV-Ray for Windows
  behaves.
- **CI.** An experimental (`continue-on-error`) Windows Server 2022 job installs the
  official installer (SHA-256 checked) silently, runs the probe, the renderer check,
  and the tests without windows.

| Check | Result |
| --- | --- |
| Linux, `YCRYSTAL_REQUIRE_INTEGRATION=1 pytest -m "not gui" -q` | 718 passed, 1 skipped (Windows-only), 172 GUI deselected |
| Windows CI, run 1 | Installer download blocked by povray.org's Cloudflare challenge; nothing else ran |
| Windows CI, run 2 (job continues without POV-Ray) | Ycrystal installs; doctests and documentation examples pass; tests 621 passed, 98 skipped (95 need POV-Ray, 1 needs POV-Ray for Windows, 2 POSIX-only), none failed |

## Audit: next tests on the Mac and other computers (17 November 2026)

At the user's request, an audit of what has been verified on which system, and of the
tests still to run: `docs/development/next-tests.md` (in the navigation; HANDOFF's next
steps point to it).

Inputs checked:
- the CI workflow: Ubuntu runs all 881 tests under Xvfb; macOS runs the 709 tests
  without windows, among them 95 of the 104 POV-Ray tests, because 9 POV-Ray tests
  also need a window;
- the Mac records in this file: the last local full run was 790 tests at PR #31, so
  91 tests are new since;
- the laptop runs of FR-VALIDATION-01 and FR-GALLERY-01;
- HANDOFF's open hands-on items.

The plan is ordered as follows. On the Mac mini:
1. the full suite with real windows (881 expected);
2. a check of the benchmark's memory figure on macOS (a ready snippet);
3. the benchmark (quick set for comparison, then the full set);
4. replays of the Linux reference sets (`artifacts/gallery/figures`,
   `artifacts/validation/bench-linux/snapshots`, 3.5 MB, copied byte for byte);
5. the gallery on the Mac, and replays Mac → Linux.

Then hands-on items on the Mac and the laptop, and a clean-computer dry run of the
independent evaluation. For each result, the plan says which claim it allows.
Nothing in the plan has been run yet.

## FR-GALLERY-01: reproducible publication gallery (post-0.3.0, 17 November 2026)

Demonstration and documentation work after version 0.3.0 on the Linux Mint 22.1
laptop, on branch `feature/gallery` from `main` at `0c18079` (PR #33 merged);
submitted as PR #34 after the user's review. No application code changed.

What was added:

- `examples/publication/`:
  - `README.md`: cases, files, regeneration, provenance and licences;
  - `gallery.json`: the batch manifest, with `save_projects`;
  - `styles/paper.ycstyle` and `styles/cover.ycstyle`;
  - `structures/`: SrTiO3 and BaZrO3, byte-identical copies of the fixtures, and
    kyanite.

  Two inputs are the existing example projects `../MgB2-gradient.ycrystal` (3 × 3 × 1,
  from the MgB2 fixture) and `../vectors-synthetic-afm.ycrystal`.
- **Styles.** `scripts/make_examples.py` gains `publication_styles()`, which writes
  both styles deterministically.
  - *Paper:* satin, white background, soft lighting, Okabe–Ito colours for the Sr, Ti,
    and O sites, 1600 × 1200.
  - *Cover:* the same colours, ceramic Sr, chrome Ti, ruby-glass O, in the dark studio
    (reflective floor, point key light).
  - Neither changes radii, so the cover keeps a snapshot's geometry.
- **Kyanite.** Al₂SiO₅, P-1, 32 atoms, fully ordered; COD entry 1008755, de Rango et
  al. (1966). Downloaded and kept verbatim with its SHA-256; COD data are CC0, and the
  original authors are credited in the README and `THIRD_PARTY_NOTICES.md`. It
  replaces the invented triclinic cell for the low-symmetry case, because that cell
  has arbitrary atoms and almost no bonds. Ycrystal reads it with Si–O 1.62–1.64 Å
  and Al–O 1.81–1.99 Å bonds.
- `scripts/make_gallery.py`:
  1. copies the inputs to a temporary folder and runs the manifest with
     `ycrystal --batch`;
  2. renders the SrTiO3 snapshot with the cover style: environment only, then
     appearance and environment (same camera and size);
  3. deletes the inputs and replays every snapshot with `scripts/replay_check.py`;
  4. writes `figure-methods.md`/`.json` from the provenance records and snapshots, and
     `commands.txt`;
  5. optionally writes thumbnails.
- `docs/guide/gallery.md`: thumbnails, explanation, commands, and the figure-methods
  table of the recorded run. `docs/assets/gallery/*.jpg`: seven 480 px JPEG thumbnails
  (17–26 KB), downscaled from the real 1600 × 1200 renders.
- `docs/development/manuscript-figures.md`: four proposed journal figures with draft
  captions and stated limitations; which panels exist and which are to do
  (schematic, screenshot, plots).
- Independent evaluation checklist: now uses the supplied paper style and the gallery
  manifest, and asks evaluators to re-open a snapshot in the window.
- Also updated: examples guide, CONTRIBUTING (thumbnail policy), changelog,
  third-party notices.
- `tests/test_gallery.py` (7 tests; 1 with real POV-Ray), checking:
  - the manifest plans the five figures, with the mapping and the shared scale, and
    reports warnings;
  - the structure inputs and their provenance;
  - the styles equal what the generator writes;
  - the cover variants keep positions, radii, camera, and size (colours change only
    through ruby glass);
  - the documents and thumbnails match the script;
  - the whole script runs at 0.1 scale, with 7 of 7 replays the same, equal cameras,
    and a full table.

Choices made while looking at real renders:
- MgB2: one cell down c showed a single B–B bond, so the 3 × 3 × 1 example project is
  used instead.
- Kyanite: the default view instead of down c.
- Cover: other candidate materials made gold look pale and translucent, so the
  materials above were chosen.
- A first description of the cover lighting as an "area light" was wrong: the dark
  studio preset has a point light. It was corrected after the methods table showed it.

| Check | Result |
| --- | --- |
| `make_gallery.py --out artifacts/gallery --thumbnails docs/assets/gallery` (1600 × 1200, POV-Ray 3.7.0.10.unofficial) | 7 figures. Batch of five 9.7 s; variants 2.6 s and 9.2 s; 7 of 7 replays identical after the inputs were deleted |
| `tests/test_gallery.py` with `YCRYSTAL_REQUIRE_INTEGRATION=1` | 7 passed (the script run 24 s) |
| `tests/test_release.py` (examples, CLI, one windowed test) | Passed |

Regression on the laptop:
- `YCRYSTAL_REQUIRE_INTEGRATION=1 pytest -m "not gui" -q`: 709 passed, 172 GUI tests
  deselected, none skipped (210 s);
- `scripts/docs_examples.py`, `pre-commit` on all new and changed files, and
  `zensical build --clean --strict`: clean;
- the verbatim COD file is unchanged after the hooks (SHA-256 checked).

**Not run:** the GUI tests (no GUI code changed), macOS, replays of the gallery on
another machine, and CI. Figure 1 (schematic, screenshot) and the plots of Figure 4
are proposals only.

## FR-VALIDATION-01: scientific validation and benchmarks (post-0.3.0, 17 November 2026)

Evidence work after version 0.3.0 on the Linux Mint 22.1 laptop, on branch
`feature/validation` from `main` at `e7ec99f` (PR #32 merged); committed as `77008d6`
after the user's review, PR #33, merged at `0c18079` after CI passed (pre-commit,
docs, Ubuntu full suite 7 min, macOS without windows 7 min). No
application code changed: tests, two scripts, and documentation only. Evidence report:
`docs/development/validation.md`, with the observed values and the reasons for each
tolerance.

What was added:

- `tests/test_validation.py` (55 tests; 26 with real POV-Ray), checking:
  - **A. Geometry.** The scene file holds exactly the shared geometry:
    - atoms with identity, position, and radius;
    - bonds as whole or half cylinders between atom centres;
    - cell edges between lattice points.

    Also: periodic images are exact lattice translations; lattice views are not
    mirrored; vectors keep their attachment, direction, and sign in every image.
  - **A. Ray-traced images** of SrTiO3, SrTiO3 2 × 2 × 1, MgB2 2 × 2 × 1, triclinic
    2 × 1 × 1, and BaZrO3:
    - every sphere at its projected centre and of its projected size, with a mirrored
      control;
    - half-bonds in their atom's colour;
    - arrow heads where projected;
    - fitted views never cut off (landscape and portrait).

    Views are chosen analytically so that all atoms are visible.
  - **B. Styles.** The grey studio style applied to 8 inputs with 2 sets of parts
    (one with Ti → Zr) changes no scientific data and writes no file.
  - **E. Effects**, each comparison changing one setting:
    - cast shadows;
    - the area light's soft shadows vs a point light;
    - chrome reflecting a red floor, against matte and satin;
    - glass transmitting a blue background, against satin.
- `scripts/benchmark_render.py`. Cases:
  - SrTiO3 1³, 4³, 8³, 12³;
  - a resolution series;
  - plain, studio, chrome, and glass effects;
  - MgB2 with `--style`.

  Method: each run is a new `ycrystal --render` process. Recorded: warm-up and timed
  runs; median, minimum, and maximum of wall time and printed render time; peak
  memory from `wait4`. Also: input, fixture, and style SHA-256, and the system. The
  first warm-up saves a snapshot per case (`--save-project`).

  Peak memory is read by a small launcher process. The first recorded run measured
  from the benchmark process itself, and its memory column rose monotonically
  (84.9 → 87.9 MiB). The cause: on Linux a child's `ru_maxrss` includes the size of the
  process that started it (inherited at fork and exec), here the growing benchmark
  process. The same case alone gave 71 MiB. That run was discarded and the
  measurement fixed. Verified on Linux: a 300 MB parent no longer shows (11.2 MiB for
  a trivial command), and a 200 MB grandchild is still seen (199.9 MiB).
- `scripts/replay_check.py`: for each provenance record in a folder:
  - verifies the recorded SHA-256 of image and snapshot;
  - renders the snapshot with the production command;
  - compares pixels (largest and mean difference, fraction beyond the tolerance) and
    reports both systems.

  This gives a ready command for cross-installation checks.
- `tests/test_validation_scripts.py` (4 tests; 1 with real POV-Ray): reports, inputs,
  snapshots, `same`/`different`/`modified`/no-record outcomes, and usage errors.
  The stand-in renderer moved into `tests/conftest.py::fake_povray` (now with a
  colour setting) and is shared with `tests/test_reproducibility.py`.
- `docs/development/comparison.md`: VESTA, OVITO 3.17.2, and CView 1.3.1, from their
  documentation only, with quotations and links. None was installed. A research
  subagent collected the quotations; three key claims were rechecked against the
  pages: the OVITO POV-Ray removals, where VESTA's `-export_img` is listed, and
  CView's planned items. The CView article's full text was not accessible (its
  abstract was used).
- `docs/development/independent-evaluation.md`: a checklist for two independent
  evaluators. No evaluation has taken place. The journal's requirement is quoted from
  a search summary, because the IUCr pages refused automated access; recheck it
  before submitting.
- `tests/fixtures/README.md` now says which structures are real compounds (idealised)
  and which are synthetic (the triclinic cell, the antiferromagnet example), and
  states the licence.

Runs on the laptop (all with real POV-Ray 3.7.0.10.unofficial):

| Check | Result |
| --- | --- |
| `tests/test_validation.py`, `tests/test_validation_scripts.py`, `tests/test_reproducibility.py` with `YCRYSTAL_REQUIRE_INTEGRATION=1` | 84 passed, none skipped (70 s) |
| Observed margins (`--junitxml` properties) | Sphere centres ≤ 0.19 px (tolerance 0.5); disc areas ≤ 3.5 % (8 %); mirrored control ≥ 51 px; fitted bounds ≤ 0.76 px without arrows (1.5); shadows darken 20.4 % of pixels; penumbra 0.46 vs 0.31; chrome red excess 84–124 vs 0 for matte and satin; glass blue excess 49–78 vs 0 for satin |
| `benchmark_render.py --quick --scale 0.5 --repeats 3` | 9 cases. 15–2,969 atoms: 1.7–2.6 s per command at 400 × 300. Studio +0.5 s; chrome instead of satin in the studio +1.2 s; glass in the studio 65 s (56–75). Peak memory 71–85 MiB. Raw data: `docs/development/validation-results/benchmark-linux-2026-11-17.json` |
| `replay_check.py` of that run's 9 snapshots, same laptop | 9 of 9 identical pixels (largest difference 0), including glass, chrome, area-light shadows. Raw data: `…/replay-check-linux-2026-11-17.json` |
| `YCRYSTAL_REQUIRE_INTEGRATION=1 pytest -m "not gui" -q` | 702 passed, 172 GUI tests deselected, none skipped (184 s); the GUI tests still collect |
| `ruff check`/`format --check`, `pre-commit` on the new and changed files, `scripts/docs_examples.py`, `zensical build --clean --strict` | Clean |

**Not run locally:**
- the GUI tests (no GUI code changed);
- the full benchmark (12³ and 1600 × 1200; too heavy for the laptop);
- anything on macOS;
- replays between two machines.

The CI of PR #33 then passed: the Ubuntu full suite with GUI tests under Xvfb, and
macOS without windows, both running the new POV-Ray tests. The benchmark and the
replay check were not run on the Mac. The comparison rests on documentation only.

## FR-REPRO-01: figure snapshots and provenance records (post-0.3.0, 17 November 2026)

Development after version 0.3.0 on the Linux Mint 22.1 laptop, on branch
`feature/repro-snapshots` from `main` at `5b5791f` (PR #31 merged); committed as
`86ba228` after the user's review, PR #32, merged at `e7ec99f` after CI passed
(pre-commit, docs, Ubuntu full suite under Xvfb, macOS without windows). The user
tested it by hand (17 November 2026) and reports it working.
`ycrystal FILE … --render OUT.png --save-project FIGURE.ycrystal [--overwrite]` and the
manifest's top-level `"save_projects": true` save, next to each image, a self-contained
snapshot (an ordinary `.ycrystal` project) and a provenance record
`FIGURE.provenance.json`. Replay: `ycrystal FIGURE.ycrystal --render OUT.png`. Guide:
`docs/guide/reproducibility.md`.

Design: new module `src/ycrystal/provenance.py` (no Qt or VTK) over the existing
single-figure functions; no new recipe format, no project schema change (a snapshot is
a schema-7 project), no new dependency. `snapshot_project` returns the project with
the camera and size that `scene_for` chooses (aspect lock reset if the shape changed)
and drops the absolute `path` from the structure's import record. `render_snapshot`
finds POV-Ray, saves the snapshot to a temporary file and reads it back, renders that
reloaded project with `render_png` to a temporary image, hashes the temporary files,
writes the record to a temporary file, then renames image, snapshot, and record into
place, record last; on any failure the temporary files and any folder it created are
removed. `provenance_record` (schema 1) records Ycrystal and POV-Ray versions, the
standard include files the scene needs, SHA-256 and size of input, style, manifest,
snapshot, and image, the image size read from the PNG, style parts, element mapping,
camera policy and resolved camera, explicit and final sizes, displayed atoms, system
(OS, machine, Python, NumPy, ASE), warnings, a replay command, and a reproducibility
statement; paths relative to the record's folder, `null` outside it.
`check_snapshot_target` refuses existing files without `--overwrite` and never lets a
snapshot replace the input, style, image, or manifest. Input and style are hashed when
read (`SourceFile`). `app.py`: `--save-project` (needs `--render` and a `.ycrystal`
name; refused with `--batch`); `--overwrite` also accepted with it. `manifest.py`:
`save_projects` (boolean, top level, manifest schema 1 kept), checked in `plan_batch`,
rendered through `render_snapshot`; the report gains `project` and `provenance` per
job (report schema 1, additive); the dry run lists the snapshots.

| Check | Result | Evidence |
| --- | --- | --- |
| Snapshot of BaZrO3 + grey studio + Ti → Zr, view a, width 500: camera and size as `scene_for`, structure arrays identical, import path dropped (SHA-256 kept), input unchanged; after save and reload, `scene_for` without options gives the same camera, settings, positions, radii, colours, materials | Pass | `test_snapshot_fixes_camera_and_size_and_keeps_the_structure` |
| Replay writes the same POV-Ray scene (`.pov` identical except the date line, `.ini` identical): mapped style with fixed view height, vector project refitted, saved camera with a new width, default fitted view, triclinic down c in portrait | Pass | `test_replaying_a_snapshot_writes_the_same_scene` (5) |
| CLI: three files and nothing else (no temporary files); recorded SHA-256 and sizes equal the real bytes of image, snapshot, input, and style; relative paths, `null` outside; quoted replay command; no absolute path of the test folder, checkout, or home in record or snapshot; record keys and order (schema 1); settings, camera, renderer, structure; input and style unchanged | Pass | `test_save_project_writes_figure_snapshot_and_true_record` |
| Existing snapshot/record refused (status 1, files unchanged), accepted with `--overwrite`; a snapshot onto the input project refused even with `--overwrite` | Pass | `test_existing_files_and_inputs_are_never_replaced` |
| Failed render: nothing left, not even the folders created for the files | Pass | `test_failed_render_leaves_nothing_behind` |
| Unwritable folder: error, no image, nothing written | Pass | `test_unwritable_folder_writes_nothing` |
| Usage errors (status 2): without `--render`, with only `--export-pov`, wrong suffix, with `--batch`; `--overwrite` alone still refused | Pass | `test_save_project_usage_errors` (5) |
| Missing and damaged snapshots refused on replay, nothing written | Pass | `test_missing_or_damaged_snapshots_are_refused` |
| Target checks and record naming | Pass | `test_snapshot_target_checks` |
| No window toolkit loaded (subprocess, no `DISPLAY`) | Pass | `test_headless_snapshot_needs_no_window_toolkit` |
| Clean profile: a project with a custom material and vectors, a ZIP style with a background picture; sources deleted, registries cleared, replay in a new process with an empty home: same scene, picture staged from the snapshot package, custom material present, vectors equal | Pass | `test_snapshot_replays_without_style_picture_or_materials[False]` |
| Batch with `save_projects`: dry run lists snapshots; report names project and record per job (subfolder too); every record's job, manifest SHA-256, image and snapshot SHA-256 correct; replay command in the record's folder; snapshots load with mapping and vectors; no temporary files; rerun refused | Pass | `test_batch_saves_a_snapshot_and_record_per_job` |
| Batch validation: non-boolean `save_projects`; a snapshot onto an input (even with `--overwrite`); an existing record; without `save_projects` nothing changes | Pass | `test_batch_snapshot_validation` |
| Batch: failed renders save no snapshot; report has `null`s; no images or folders | Pass | `test_batch_failed_job_saves_no_snapshot` |
| Real POV-Ray: BaZrO3 from copies of the CIF and style, sources then deleted; replay with the recorded command in a new process: same pixels (tolerance 1 of 255 per channel); recorded image SHA-256 equals the file; PNG 240 × 180; renderer 3.7 | Pass | `test_replay_after_removing_the_sources_renders_the_same_image` |
| Real POV-Ray: picture style, custom material, vectors, clean profile: replay has the same pixels | Pass | `test_snapshot_replays_without_style_picture_or_materials[True]` |
| Real POV-Ray: three batch jobs with snapshots, each replayed: same pixels | Pass | `test_batch_snapshots_replay_with_povray` |

Measured on the laptop (POV-Ray 3.7.0.10.unofficial from apt): every replay had exactly
the same pixels as the original (largest difference 0 of 255): the three real POV-Ray
tests rerun with tolerance 0 (a negative control with tolerance −1 failed all three, so
the setting took effect), a 400 × 300 BaZrO3 figure, and four batch jobs (SrTiO3,
BaZrO3, MgB2 down c, vectors) at 240 × 180. The PNG files were never byte-identical:
POV-Ray writes a `tIME` chunk and a "Render Date" comment into every PNG, so the image
SHA-256 differs between renders of the same scene. Pixel differences across systems or
POV-Ray builds were **not** measured; macOS was **not** run for this feature.

Observed, not changed: snapshots, like every project written by `save_project`, have
mode 0600 (owner only), because `save_project` writes through `mkstemp`.

Regression runs on the laptop (Linux Mint 22.1, Python 3.12.3, POV-Ray 3.7.0.10 from
apt): `YCRYSTAL_REQUIRE_INTEGRATION=1 pytest -m "not gui" -q` 643 passed, 172 GUI tests
deselected, none skipped (137 s; 25 new tests in `tests/test_reproducibility.py`, 815
in all); `tests/test_release.py` including its windowed workflow test passed after the
CLI change; the CI doctest list (now with `provenance.py`); `scripts/docs_examples.py`
(now also checks the guide's dry-run line); `pre-commit run --all-files` and on the
new files; `zensical build --clean --strict` clean. Not run locally: the GUI tests (no
GUI code changed; the windows would have taken over the desktop session) and macOS;
both ran in the CI of PR #32 (Ubuntu with GUI tests under Xvfb; macOS without
windows), which passed.

## FR-BATCH-01: render a series from a manifest (post-0.3.0, 17 November 2026)

Development after version 0.3.0, on branch `feature/batch-manifest` from `main` at
`a4ba148` (PR #30 merged); submitted as PR #31. `ycrystal --batch MANIFEST.json
--output-dir DIR [--dry-run] [--overwrite] [--povray PATH]` renders the jobs of a
versioned JSON manifest (`format: ycrystal-batch`, schema 1) to PNGs, sequentially and
without a window. Example: `examples/batch-series.json` (five structures, one style,
one element mapping, two views, a project with vectors).

Design: new module `src/ycrystal/manifest.py`, a thin orchestrator over the
single-figure functions (`load_input`, `apply_style_file`, `ViewPolicy`, `scene_for`,
`render_png`); no second renderer, style parser, or camera code, no queue or
parallelism (POV-Ray already uses every core for one image), no new dependency.
`plan_batch` validates everything first: top-level layout and schema, unknown keys
(typos are errors), unique safe ids, outputs (relative `.png`, no `..` or absolute
paths, unique case-insensitively, existing files refused without `--overwrite`),
inputs (present and readable), styles (each loaded once), style parts, element maps
(symbols, then targets via the style transfer), camera policies (including a fixed
height that does not fit), sizes, and `max_atoms` (default 20,000; never truncated).
All problems of all jobs are reported together; then nothing is rendered or written
(exit status 2). `run_batch` finds POV-Ray before any job (missing: status 1, nothing
written), creates the output folder, renders in manifest order, records a failed job
and continues, and writes `ycrystal-batch-report.json` atomically (job id, input and
output as given, status, seconds, size, atoms, warnings, error; Ycrystal and POV-Ray
versions). Images are copied into place only after a successful render. Status 0 if
all jobs rendered, 1 if any failed. `--batch` refuses the single-figure options; the
batch options need `--batch`.

| Check | Result | Evidence |
| --- | --- | --- |
| Example manifest: five jobs in order, outputs (one in a subfolder), 600 × 450, Ti → Zr mapping, per-job views, environment-only style parts, vectors kept; validation writes nothing | Pass | `test_example_manifest_plans_five_jobs_in_order` |
| One manifest with 19 jobs and 18 different problems (duplicate and invalid ids, case-insensitive output clash, `../` and absolute outputs, non-PNG, missing and unreadable inputs, missing style, bad style parts, bad symbol, absent target, mapping without style, too small view height, bad width, too many atoms, misspelt key, existing output): every problem reported, nothing written | Pass | `test_every_problem_is_reported_and_nothing_is_written` |
| Bad manifest files: not JSON, wrong format, newer schema, no jobs, unknown top-level key | Pass | `test_bad_manifest_files` (5) |
| A failed job does not stop the others; order kept; failed job's image not written; report summary, order, relative paths; no `.part` files | Pass | `test_a_failed_job_does_not_stop_the_others` |
| Dry run and missing POV-Ray write nothing | Pass | `test_dry_run_and_missing_povray_write_nothing` |
| CLI: dry run output and warnings; invalid manifest status 2 with the problem list; failed jobs status 1 with a report; usage errors for mixed options | Pass | `test_batch_command_line_exit_codes`, `test_batch_usage_errors` (6) |
| No window toolkit loaded (subprocess, no `DISPLAY`) | Pass | `test_batch_needs_no_window_toolkit` |
| Real POV-Ray 3.7: the example series into a folder with a space and `ü`: five 600 × 450 PNGs, all `rendered`, renderer recorded, inputs/style/project byte-identical; rerun refused (status 2), `--overwrite` accepted, no `.part` files | Pass | `test_example_series_renders_with_povray` |
| Example manifest paths are relative and exist | Pass | `test_example_manifest_is_listed_in_the_examples` |

Visual check (Claude, on the Mac): the five rendered images side by side (SrTiO3 and
BaZrO3 along a with chrome Ti/Zr, MgB2 down c, the triclinic cell, the vector example
refitted), all in the grey studio. `scripts/docs_examples.py` (run in CI) runs the
example's dry run and checks that every printed line appears in the guide.

Regression runs on the Mac mini (macOS 15.8, Homebrew POV-Ray 3.7.0.10):
`YCRYSTAL_REQUIRE_INTEGRATION=1 pytest -q -rf` 790 passed, none skipped (201 s; 19 new
tests in `tests/test_batch_manifest.py`); doctests of `manifest.py`, `batch.py`;
`pre-commit run --all-files`; `zensical build --clean --strict` clean. **Linux not run
locally** (CI of PR #31).

## FR-CAMERA-01: view and framing policies (post-0.3.0, 17 November 2026)

Development after version 0.3.0, on branch `feature/camera-policy` from `main` at
`445ca84` (PR #29 merged); merged in PR #30 (merge commit `a4ba148`). Reproducible orientation and framing for
figures made without a window: `--view default|a|b|c|x|y|z`, `--camera-policy
saved|fit`, `--fit-margin FRACTION`, `--view-height ANGSTROM`.

Design: one pure helper in `core/camera.py` serves the window and the command line.
`axis_view(axis, cell, reverse)` is the window's former View-along rule, moved
unchanged (the named axis points at the viewer; screen up is the first of c, b, a, or
z, y, x, that is not parallel; a, b, c are real-space lattice vectors, not hkl plane
normals); `MainWindow.view_along` now calls it. `ViewPolicy(camera, view, margin,
visible_height).resolve(saved, points, radii, aspect, cell)` returns the saved camera
untouched with the saved policy (the default without a view), and otherwise fits the
framing bounds of `DisplayGeometry.points_and_radii` (atoms, cell edges, whole arrows)
at the final aspect ratio. A fixed visible height keeps the fitted centre and is
refused, with the height needed, if the scene does not fit; it is never cropped.
`batch.scene_for`, `export_scene`, and `render_png` take an optional policy (`None`:
exactly the previous behaviour), ready for FR-BATCH-01. The structure is never rotated
or moved. No schema change, no new dependency. With `--camera-policy fit` the CLI
leaves out FR-STYLE-CLI-01's note that the saved camera was kept.

Fix found by the new GUI parity test: `StructureViewport.set_camera` applied position,
focal point, and up vector one VTK call at a time, and the camera observer reported each
call; switching the view from c to x of the triclinic sample read a half-applied camera
whose up vector was parallel to the new direction and raised `ValueError` in the Qt
event loop. The observer is now silent while `set_camera` applies a camera, which
reports the change once at the end, as before.

| Check | Result | Evidence |
| --- | --- | --- |
| Axis conventions: cubic a/b/c/x/y/z directions and up vectors; reverse; triclinic a, b, c along the real-space vectors; Cartesian views without a cell; lattice views without a cell or with a zero vector refused | Pass | `test_axis_view_conventions`; doctests in `ycrystal.core.camera` |
| No options: saved camera returned unchanged; without one, identical to `default_camera`; repeated runs identical | Pass | `test_without_options_nothing_changes`, all earlier camera, CLI, and example tests unchanged |
| `fit` refits a saved camera, same orientation | Pass | `test_fit_policy_refits_a_saved_camera_and_keeps_its_orientation` |
| No clipping, zero margin: SrTiO3, MgB2, triclinic × 7 views × 800 × 600, 400 × 900, 500 × 500 × repetitions 1 × 1 × 1 and 3 × 2 × 1, every sphere inside the image; coordinates unchanged | Pass | `test_fitted_views_never_clip` (126 cases) |
| Whole vector arrows (tips) inside fitted views of the vector example, portrait | Pass | `test_fitted_views_include_whole_vector_arrows` |
| Margin scales the frame; fixed visible height keeps the centre; exactly the needed height accepted and unclipped; smaller refused with the needed value | Pass | `test_margin_and_fixed_visible_height` |
| Invalid policies (unknown policy or view, margin outside 0–1 or NaN, non-positive height, saved with a view or height) | Pass | `test_invalid_policies_are_refused` (7) |
| CLI: `--view a`/`c` on MgB2 give −a/−c directions in the exported scene, b up for c; portrait frame; `--view-height 30` gives a 30 Å `up` vector | Pass | `test_views_from_command_line` |
| CLI: saved camera kept with no option and with `--camera-policy saved`; `fit` after a style changed MgB2's 3 × 3 × 1 to 2 × 2 × 1 keeps the direction, changes the frame, and drops the camera note | Pass | `test_saved_camera_is_kept_unless_asked` |
| CLI errors: too small height status 1 with "needs at least 6.14 Å"; conflicts, margin, height, unknown view status 2; options without an output operation status 2; nothing written | Pass | `test_camera_option_errors` |
| Real POV-Ray 3.7: MgB2 down c at 160 × 240 (portrait): the image border is background only, atoms drawn | Pass | `test_render_fitted_view_is_not_clipped` |
| Window and command line agree: View along a, b, c, x, y, z of the triclinic sample equals `ViewPolicy(view=…)` (basis, scale, focal point up to depth) | Pass | `test_view_buttons_and_command_line_views_agree` |

Visual checks (Claude, on the Mac): MgB2 down c (hexagonal cell, b up); SrTiO3 and
BaZrO3 down a at `--view-height 9`, side by side, the larger BaZrO3 cell visibly larger.
`scripts/docs_examples.py` (run in CI) runs the guide's view commands and checks
direction, the 9 Å height, and the "needs at least 5.85 Å" message.

Regression runs on the Mac mini (macOS 15.8, Homebrew POV-Ray 3.7.0.10):
`YCRYSTAL_REQUIRE_INTEGRATION=1 pytest -q -rs` 771 passed, none skipped (183 s; 143 new
tests: 138 in `tests/test_camera.py`, 4 in `tests/test_release.py`, 1 in
`tests/test_gui_scene.py`), twice. One earlier full run reported 1 failure among 771
that did not reproduce in the two following full runs; its name was not captured
(**unidentified intermittent failure**, to watch in CI). Doctests of `core/camera.py`
and `batch.py`; `pre-commit run --all-files`; `zensical build --clean --strict` clean.
**Linux not run locally** (CI of PR #30).

## FR-STYLE-MAP-01: element mapping for styles (post-0.3.0, 17 November 2026)

Development after version 0.3.0, on branch `feature/style-map` from `main` at `f77e163`
(PR #28 merged); submitted as PR #29. A style made for one composition can give its
element settings to other elements of the target structure: `--element-map
Sr=Ba,Ti=Zr` (`O=-` leaves O's settings out) with `--style`, or the rows **Element
settings go to** in the Import Style dialog (`gui/style_dialog.py`). The mapping is a
presentation choice; it is never stored in the style.

Design: `io/style.py::resolve_element_map` decides, without Qt, where each element
setting goes (`ElementTransfer`); `apply_style(…, element_map=None)` uses it for element
materials, colours, radii (appearance) and bond-pair rules (display, re-sorted
alphabetically). Elements that are not mapped keep matching by symbol, so `None`, `{}`,
and identity mappings give exactly the previous result. Validation, all errors before
anything is written: symbols must be chemical elements (ASE's list, case-sensitive,
with a hint such as "did you mean Ti?"); targets must be in the structure; two sources
may not share a target; a mapped element may not land on an element that keeps its own
settings (Ti → O while the style has O settings), and only the parts being applied
count. Notes: mapped elements without settings in the style, settings left out with
`None`/`-`, and structure atoms whose element was mapped elsewhere. Per-atom materials
and hidden atoms still transfer only to the same structure; atoms, labels, coordinates,
vectors, and bond topology are never changed. CLI parsing (`batch.parse_element_map`)
gives usage errors (status 2) for syntax, symbols, and duplicate sources; structure-
dependent errors are `ERROR: Element mapping: …` (status 1). In the window,
`MainWindow.ask_style_import` replaces `ask_style_parts` and returns a
`StyleImportChoice` (parts and mapping); rows start at the matching symbol (or *Do not
transfer*), the summary shows what is applied and left out, an ambiguous choice
disables *Apply*, and the import stays one undo step. No schema change, no new
dependency. New fixture `tests/fixtures/BaZrO3.cif`: an illustrative cubic perovskite
with a rounded a = 4.19 Å, not reference data.

| Check | Result | Evidence |
| --- | --- | --- |
| No mapping, `{}`, and identity mappings give results identical to before (settings and notes), on the same and on another structure | Pass | `test_no_mapping_and_identity_mapping_change_nothing`; all earlier style tests unchanged |
| SrTiO3 → BaZrO3 with Sr→Ba, Ti→Zr: materials, colour, radius, and both bond rules (O–Zr, Ba–O) mapped; O by symbol; per-atom material and hidden atom not transferred; coordinates, cell, and element labels unchanged; Zr drawn with Ti's material | Pass | `test_srtio3_style_maps_onto_bazro3` |
| Deliberately partial SrTiO3 → MgB2 (Ti→Mg): Ti settings on Mg; O and Sr settings and both O rules dropped with the usual notes; nothing invented for B | Pass | `test_partial_mapping_onto_mgb2_explains_what_is_dropped` |
| Invalid symbols (`Xx`, `ti`, `mg`, a number), absent target, duplicate targets, identity conflict (Ti→O); resolved by O→None or a swap (rules follow their elements); conflicts only for applied parts | Pass | `test_invalid_mappings_are_refused` (6), `test_mapping_onto_an_element_with_its_own_settings_is_ambiguous` |
| Notes for unused mappings and moved elements; `resolve_element_map`, `style_elements` | Pass | `test_mapping_notes_unused_and_moved_elements`; doctests in `ycrystal.io.style`, `ycrystal.batch` |
| `--element-map` parsing: pairs, spaces, `-`, identity; empty, missing `=`, empty entries, duplicates, wrong case, unknown symbols refused | Pass | `test_element_maps_are_parsed` (4), `test_bad_element_maps_are_refused` (8) |
| ZIP style with picture and custom material, original picture deleted and registries cleared: custom material mapped Ti→Zr, picture kept, style file bytes unchanged, saved project keeps the resolved appearance | Pass | `test_mapped_packaged_style_and_saved_project` |
| CLI: BaZrO3 + grey studio with `Sr=Ba,Ti=Zr`: Zr gets the chrome texture, O the ceramic one, a warning for Sr (no settings), inputs byte-identical; ambiguous and absent targets status 1, syntax errors status 2, `--element-map` without `--style` status 2, nothing written | Pass | `test_element_map_from_command_line`, `test_bad_element_maps_write_nothing` |
| Real POV-Ray 3.7 render with the mapping: 160 × 120, differs from the unmapped render | Pass | `test_render_with_element_map` |
| Dialog: defaults (matching symbol / *Do not transfer*), live summary, ambiguity disables *Apply* with the reason, *Match Symbols*, parts change the check, hidden when the style has no element settings, accessible names; *Apply* and *Cancel* buttons | Pass | `test_dialog_defaults_preview_and_ambiguity`, `test_dialog_without_element_settings_hides_the_mapping`, `test_dialog_apply_and_cancel_buttons` |
| Window: mapped import is one undo step (undo and redo exact), coordinates and labels unchanged; Cancel and an invalid mapping change nothing and add no undo step | Pass | `test_mapped_import_is_one_undo_step`, `test_cancelled_or_invalid_import_changes_nothing` |

Visual checks (Claude, on the Mac): dialog screenshots in the default, mapped, and
ambiguous states (the summary reserves room so the wrapped text is not squeezed); the
guide's `BaZrO3 … --element-map Ti=Zr --render` shows a chrome Zr in the grey studio,
unlike the unmapped render. `scripts/docs_examples.py` (run in CI) runs the guide's
three mapping commands with `--export-pov` and checks Zr's chrome and the exact quoted
warnings; `test_documented_walkthrough_with_the_example_style` follows the guide's
window steps (dialog texts, Apply, one undo step) with the example style.

Regression runs on the Mac mini (macOS 15.8, Homebrew POV-Ray 3.7.0.10):
`YCRYSTAL_REQUIRE_INTEGRATION=1 pytest -q -rs` 627 passed, none skipped (184 s), then
the documentation walkthrough test (6 passed in `tests/test_gui_style_map.py`); 33 new
tests: 24 in `tests/test_style.py`, 3 in `tests/test_release.py`, 6 in
`tests/test_gui_style_map.py`; `pytest -m "not gui"` 457 passed; doctests of
`io/style.py`, `batch.py`, `core/scene.py`; `pre-commit run --all-files`;
`zensical build --clean --strict` clean. **Linux not run**; hands-on use of the dialog
by a person not done.

## FR-STYLE-CLI-01: styles from the command line (post-0.3.0, 17 November 2026)

Development after version 0.3.0, on branch `feature/style-cli` from `main` at `410d87e`
(0.4.0.dev0); merged in PR #28 (merge commit `f77e163`).
`ycrystal FILE --style STYLE.ycstyle [--style-parts LIST] --render OUT.png | --export-pov
OUT.pov` applies a style without a window. `batch.apply_style_file` loads the style
with `load_style` and calls the existing `apply_style` on the input from `load_input`;
the result is a new `Project` that `scene_for`, `export_scene`, and `render_png` draw
as before. No second style parser, scene builder, or renderer; no new dependency; no
project or style schema change.

Decisions: the command line's default parts are `appearance,environment,output`
(`CLI_STYLE_PARTS`); `display` only on request, because a style's repetitions and
hidden atoms belong to its own structure. The GUI's Import Style dialog is unchanged
(all four parts offered). The saved camera of a project is kept (a warning when
`display` changes its repetitions); a structure without a camera gets the default view
fitted to the styled geometry. A style may not raise the displayed-atom count above
20,000 (`LARGE_DISPLAY_ATOMS`, now in `core/scene.py` and shared with the window's
confirmation, previously `SOFT_LIMIT_ATOMS = 20000` in `gui/main_window.py`, which
remains as an alias) when that is more than the input already shows; the window asks
instead, and there is no command-line override. Style notes go to standard error as
`WARNING:` lines; errors keep `ERROR:` and status 1; usage errors status 2. `--render`
stays PNG-only.

| Check | Result | Evidence |
| --- | --- | --- |
| Same structure: every requested part, no notes | Pass | `test_same_structure_receives_every_requested_part` |
| Different composition (SrTiO3 style → MgB2): default parts leave repetitions, bonds, and hidden atoms; notes for absent elements and per-atom overrides; input project not modified; structure shared, not copied | Pass | `test_cli_default_parts_leave_display_settings_alone`; doctest in `ycrystal.batch` |
| Saved project target (`vectors-synthetic-afm.ycrystal`): camera and vectors kept, arrow appearance transferred, coordinates unchanged, file bytes unchanged, camera warning when repetitions change | Pass | `test_saved_project_keeps_camera_vectors_and_structure`, `test_style_on_a_saved_project_keeps_its_camera_and_vectors` (identical `location`/`look_at` and arrow lines in the exported scene) |
| ZIP style with a background picture and a custom material, original picture deleted and registries cleared: applied, picture staged next to the exported scene, custom declaration written; paths with spaces and non-ASCII | Pass | `test_packaged_style_with_picture_and_custom_material` |
| Parts: parsing, order, duplicates; empty, empty entry, unknown, wrong case refused; `--style-parts` without `--style`; `--style` without an output operation is a usage error (no window) | Pass | `test_style_parts_are_parsed`, `test_bad_style_parts_are_refused`, `test_style_usage_errors` |
| Sizes: style size by default; `--width` and `--height` override each on its own; without `output` the input's size stays | Pass | `test_command_line_sizes_override_the_style` (5 cases) |
| Large display (30 × 30 × 30 SrTiO3 with `display`) refused before writing; without `display` applied; a project already that large draws as saved | Pass | `test_large_display_from_a_style_is_refused`, `test_style_errors_write_nothing` |
| Missing and damaged style, large display, missing POV-Ray: status 1, `ERROR:`, output folder stays empty; inputs (style and structure) byte-identical afterwards; without `--style` the output is as before | Pass | `test_style_errors_write_nothing`, `test_style_from_command_line` |
| No window toolkit: the `--style --export-pov` path, run without `DISPLAY`, loads no `PySide6`, `vtk`, or `pyvista` module | Pass | `test_style_command_needs_no_window_toolkit` (subprocess) |
| Real POV-Ray 3.7 render with a style: 200 × 150 PNG, differs from the unstyled render, warnings printed, no stray files | Pass | `test_render_with_style_from_command_line` |

Visual check (Claude, on the Mac): `ycrystal tests/fixtures/MgB2.cif --style
examples/grey-studio.ycstyle --render MgB2.png` (800 × 600 and 400 × 300) shows MgB2
1 × 1 × 1 in the grey studio with floor shadows; with `--style-parts
appearance,display,environment,output` 2 × 2 × 1, refitted; the vector example keeps
its camera and arrows.

Regression runs on the Mac mini (macOS 15.8, Homebrew POV-Ray 3.7.0.10):
`YCRYSTAL_REQUIRE_INTEGRATION=1 pytest -q -rs` 595 passed, none skipped (180 s; 29 new
tests: 15 in `tests/test_style.py`, 14 in `tests/test_release.py`);
`pytest -m "not gui"` 430 passed; doctests of `core/scene.py`, `io/style.py`,
`batch.py` and `scripts/docs_examples.py` (which now runs the guide's MgB2 `--style`
command with `--export-pov` and checks its exact warning, 800 × 600 size, and studio); `pre-commit run --all-files`;
`zensical build --clean --strict` clean. **Linux not run** (expected from CI when the
branch is pushed); no hands-on GUI change to check.

## FR-EXPORT-01: PDF and JPEG export with publication sizes (post-0.2.0, 16 November 2026)

Development after version 0.2.0; merged in PR #23 (merge commit `52b3e5e`). **Render ▸ Render Image…** (Ctrl+R; formerly
*Render PNG…*) opens one dialog: format (PNG default, PDF, JPEG), size (the Render
panel's output size, Single column 85 mm at 600 dpi, Double column 180 mm at 600 dpi,
Custom), width × height in px or mm, resolution (300/600 offered, 1–100 000 dpi
accepted), shape lock, JPEG quality, and destination. POV-Ray renders once at the
export pixel size with the unchanged camera, geometry, and environment; only the last
step differs per format (`render/formats.py`). The settings persist for the session.

| Check | Result | Evidence |
| --- | --- | --- |
| 1. PNG compatibility: `render_png(path)` copies the POV-Ray file byte for byte (no resolution chunk); from the dialog the PNG gains only a `pHYs` chunk, with identical compressed image data and pixels; an existing `pHYs` is replaced; damaged/truncated PNGs are reported | Pass | `test_png_without_resolution_is_copied_byte_for_byte`, `test_png_resolution_is_added_without_touching_the_pixels`, `test_an_existing_png_resolution_is_replaced`, `test_damaged_png_is_reported`, `test_render_png_keeps_its_former_behaviour`; the existing render tests unchanged |
| 2. PDF: valid header and end marker; page size equals the physical size within half a point (Qt writes whole points); the image is embedded once at its rendered pixel size with Flate (no DCT); transparency kept as a soft mask; title stored | Pass | `test_pdf_page_has_the_physical_size_and_the_full_image` (2008 × 1339 at 600 dpi; portrait 300 × 450 at 150 dpi), `test_pdf_keeps_a_transparent_background` |
| 3. JPEG: rendered size, JFIF resolution, colours; quality 10 < 95 < 100 in file size; transparent background white; half-transparent pixels blend to grey | Pass | `test_jpeg_has_the_rendered_size_resolution_and_colours`, `test_jpeg_quality_changes_the_file`, `test_jpeg_fills_transparency_with_white`, `test_jpeg_blends_partly_transparent_edges_with_white` |
| 4. Sizes: 85 mm/600 dpi → 2008 px, 180 mm/600 dpi → 4252 px; heights for 3:2, 1:1, 2:3, 16:9 frames within one pixel of the shape; custom combinations including 1200 dpi; px ↔ mm round trip; physical size from pixels and dpi | Pass | `test_publication_presets_give_the_documented_pixel_widths`, `test_height_follows_the_frame_shape`, `test_custom_width_and_resolution_combinations`, `test_units_convert_both_ways_without_drift`, `test_options_report_the_physical_size`; doctests in `ycrystal.core.export` |
| 5. Validation: sides 16–20 000 px, at most 150 megapixels, 1–100 000 dpi, quality 1–100, PDF needs a resolution and pages ≤ 5080 mm; unknown formats refused; suffixes follow the format (`.jpg`/`.jpeg` kept, `SrTiO3 v1.2` gets `.png` appended) | Pass | `test_invalid_settings_are_rejected_with_an_explanation`, `test_valid_extremes_are_accepted`, `test_file_suffixes_follow_the_format` |
| 6. Files: paths with spaces and non-ASCII characters (`Figures für Ångström ✓/new folder/SrTiO₃ figure 1`) for each format; a write error leaves no `.part` file, and an export that fails keeps the previous file | Pass | `test_paths_with_spaces_and_non_ascii_characters`, `test_write_errors_leave_no_partial_file`, `test_a_failed_export_keeps_the_previous_file` |
| 7. Dialog: PNG at the output size by default; presets set mm and dpi and follow landscape and portrait frames; editing a preset switches to Custom and keeps the values; mm keep the physical size when the dpi changes, px keep the pixels; height edits compute the width; unlocking allows any shape and explains it; invalid entries and an empty file name disable Render; format changes the suffix, shows JPEG quality (and the white-background note only for transparent backgrounds) and the PDF raster note; remembered choices follow a new frame | Pass | `tests/test_gui_export.py` (dialog tests) |
| 8. Window: each format written through the same render path with a stand-in renderer; scene revision, output size, camera, environment, and modified state unchanged; status bar names format and size; the action opens the dialog; a write failure shows "Could Not Save Image" and leaves no partial file | Pass | `test_render_image_writes_each_format_without_changing_the_scene`, `test_render_image_action_uses_the_dialog_answer`, `test_a_failed_write_is_reported` |
| 9. Real POV-Ray 3.7 (Homebrew, macOS): one scene rendered as PNG, PDF, and JPEG at 40 mm, 150 dpi (236 × 157 px) into a non-ASCII folder: equal pixel sizes, PNG and JPEG at 150 dpi, JPEG within mean 4 levels of the PNG, PDF page within half a point of the physical size with the full image; camera, output size, and modified state unchanged | Pass | `test_same_scene_as_png_pdf_and_jpeg` |
| Dialog layout on macOS (screenshots of the PNG, JPEG, and unlocked PDF states) | Pass (scripted) | screenshots in the session's scratch folder (not kept) |
| CI of PR #23: Ubuntu 24.04 full suite under Xvfb with POV-Ray 3.7 (including all new tests); macOS 15 tests without windows; pre-commit; docs | Pass | GitHub Actions run 43883106317 |
| Hands-on use | Pass (user report) | The user reported that everything works (16 November 2026) |
| PDF opened in specific viewers (Acrobat, Preview) and journal submission systems | Unverified by Claude | |

Decisions: pixel size and dpi are the source of truth; millimetres are derived (a
PDF page is the rendered pixels at the chosen dpi, so 85 mm at 600 dpi becomes 2008 px
and an 85.005 mm page). Exports never resample. JPEG composites transparency over white
(not the live-view colour of a transparent environment). PDF uses `QPdfWriter` with
`LosslessImageRendering`; the page box is in whole points (≤ 0.18 mm difference), with
the image centred without distortion. Exports do not change the project's output size,
so the Render panel and saved projects are unaffected. No new dependency.

Regression runs on the Mac mini (macOS 15.8, Homebrew POV-Ray 3.7.0.10):
`YCRYSTAL_REQUIRE_INTEGRATION=1 pytest -q -rs` 565 passed, none skipped (179 s; 60 new
tests: 43 in `tests/test_export.py`, 17 in `tests/test_gui_export.py`); after a final
one-line dialog change `test_export.py`, `test_gui_export.py`, and `test_gui_render.py`
72 passed and `pytest -m "not gui"` 400 passed; doctests of the CI list including the
two new modules; ruff, `pre-commit run --all-files`, `zensical build --clean --strict`
clean. Linux: CI of PR #23 (Ubuntu, full suite) passed.

## FR-VECTOR-01: manual atom-attached vectors (post-0.2.0, 15 November 2026)

Development after version 0.2.0; merged in PR #19. **Edit ▸ Vectors…** (and
**Vectors…** in the Appearance tab) attaches Cartesian direction or magnetic-moment (μB)
arrows to atoms, as source defaults for all periodic images or as image overrides
(including suppression), with centred or tail-at-centre arrows, uniform or proportional
length, and independent colour and material. One resolver produces arrow geometry for
both renderers. FR-VECTOR-02 (table import/export) is deferred and not started.

| Check | Result | Evidence |
| --- | --- | --- |
| 1. Endpoints for a known direction (3, 0, 4): centred `r ∓ L u/2`, tail `r` → `r + L u`, head inside the length; proportional `L = scale × |v|`; reversal swaps tail and tip; arrows along ±x/±y/±z; short-arrow policy (head ≤ 60 % of L, cross-section scaled); zero vector and modulus ≤ 1e-9 draw nothing; non-zero vectors shorter than 1e-4 Å when proportional draw nothing; hidden records; non-finite/wrong-length/unknown-meaning values and invalid sizes rejected; arrows identical for any camera and atom radius | Pass | `test_endpoints_placements_and_length_modes`, `test_short_arrows_zero_and_invalid_values`, `test_geometry_does_not_depend_on_camera_or_radii`; doctest in `ycrystal.core.vectors` |
| 2. Source defaults with the same components on every image (opposite moments on two Fe sites, 2 × 1 × 1, no inferred alternation); image override and one-image suppression; boundary images (8 Sr corners); hexagonal (non-orthogonal) cell: midpoints at exact instance positions, components Cartesian; repetition shrink keeps but hides an override, restore shows it; hidden host hides its arrow | Pass | `test_source_defaults_overrides_suppression_and_no_inferred_signs`, `test_boundary_images_non_orthogonal_cell_hiding_and_repetitions` |
| 3. POV cylinders and cones equal the shared geometry (parsed, 1e-6 Å); comments name atom, image, components, unit; live-view mesh bounds equal the arrow extents; real POV-Ray 3.7 renders of synthetic ferromagnetic, antiferromagnetic, and canted examples show the arrows with the body-centre tip at its projected pixel; no arrows without vectors | Pass | `test_writer_arrows_match_the_shared_geometry`, `test_live_view_matches_shared_geometry_and_leaves_picking_measuring_lighting`, `test_rendered_ferro_antiferro_and_canted_examples` |
| 4. Framing bounds include arrow tips (12 Å arrow below its atom); Fit grows with long arrows only when requested; the orthographic eye lies in front of tips toward the camera and the gradient backdrop behind tips away from it; the floor lies below an arrow pointing down; lighting rig (atom/cell bounds) unchanged by vector changes; picking at every atom unchanged; distance unchanged | Pass | `test_bounds_fit_lighting_and_floor_include_arrows_correctly`, `test_eye_and_backdrop_stay_clear_of_long_arrows`, `test_live_view_matches_shared_geometry_and_leaves_picking_measuring_lighting` |
| 5. Editor: live preview without undo step or modified flag, frozen targets, Cancel restores, Apply one step (batch), undo/redo; table actions Reverse, Show/Hide, Suppress, Remove (override removal restores the default), row Edit keeps visibility, row selection highlights hosts; appearance edits merge (two length changes → one step), proportional mode; independent arrow colour; custom material only on arrows; a vector change during a running preview discards the stale result; status bar shows the selected atom's vector | Pass | `test_editor_preview_cancel_and_apply_as_one_step`, `test_table_actions_overrides_suppression_and_opposing_moments`, `test_appearance_edits_merge_and_custom_arrow_material_persists`, `test_vector_change_discards_a_running_preview`, `test_eye_and_backdrop_stay_clear_of_long_arrows` |
| 6. Projects (schema 7) round-trip components at full precision, suppressions, hidden records, appearance, and an arrow-only custom material on a clean profile; existing examples load without vectors; an out-of-range attachment is refused; styles carry the appearance only, and importing a style keeps the target's vectors; another structure starts without vectors | Pass | `test_projects_round_trip_and_styles_never_carry_vectors`, `test_appearance_edits_merge_and_custom_arrow_material_persists`, `test_style_import_keeps_vectors_and_new_structure_clears_them` |
| 7. Example `examples/vectors-synthetic-afm.ycrystal` (synthetic two-site cell, ±2.2 μB) generated by `scripts/make_examples.py` and rendered with `ycrystal … --render`; user guide (Controls ▸ Vectors), reference, architecture | Pass | command-line render (1.0 s) |
| GUI on the Mint display (scripted, real POV-Ray): Vectors window with source defaults and a canted image override, editor, live view with arrows and the selected host, POV-Ray preview | Pass (scripted) | `artifacts/vectors/vectors-window.png`, `vector-editor.png`, `window-vectors.png` (gitignored) |
| Hands-on use by a person; very many arrows (live-view mesh speed) | Unverified | |

Decisions: vectors live in `SceneSettings` (`vectors`: source defaults and image
overrides; `vector_style`: appearance), so undo, projects, and geometry building reuse the
existing paths; one vector per displayed atom; the record identity is its attachment
(source index or atom id). `DisplayGeometry.arrows` holds the resolved geometry;
`points_and_radii()` includes arrows (Fit, eye, backdrop, floor), `bounding_sphere()`
does not (lights). Zero tolerance 1e-9 (modulus), minimum drawn length 1e-4 Å, head at
most 60 % of the length. Default appearance: centred, uniform 2.6 Å, satin, dark red.
Arrows are drawn as cylinder + cone in POV-Ray and as one non-pickable mesh in VTK. Live
view and POV-Ray materials are not claimed to match pixel for pixel.

Regression runs: `pytest -m "not povray"` 420 passed (strict mode; 14 new non-POV-Ray
tests at that point, plus `test_eye_and_backdrop_stay_clear_of_long_arrows` added and
passing afterwards; three existing schema assertions now read 7); `pytest -m povray` on
`test_vectors.py`, `test_background_image.py`, `test_custom_materials.py`,
`test_gui_material_editor.py`, `test_gui_render.py`, `test_gui.py`,
`test_preview_resolution.py`, `test_povray_jobs.py`, and the command-line render 12
passed; `test_presets.py` environment, combination, and floor renders 20 passed (the 30
per-material renders were not rerun: scenes without arrows and the thumbnail digests are
unchanged); doctests; `zensical build --clean --strict`; ruff.

## FR-BGIMAGE-01: background pictures with portable assets (post-0.2.0, 15 November 2026)

Development after version 0.2.0; merged in PR #18. Background type **Image**
shows a user's PNG or JPEG picture behind the structure in the POV-Ray preview and the
PNG, framed in the output frame (Fill/Fit, zoom, frame-relative offsets, brightness,
Reset Framing). Projects and styles that use a picture become ZIP packages that carry it.

| Check | Result | Evidence |
| --- | --- | --- |
| Framing arithmetic: Fit/Fill for wide, tall, square, and extreme pictures in 3:2, 1:1, 2:3 frames keep the picture's proportions; Fill covers, Fit fits; zoom and offsets in frame units | Pass | `test_fit_and_fill_keep_the_shape_for_all_orientations`; doctest in `ycrystal.core.background` |
| Reference validation (digest, size, format, mode, finite ranges), Reset Framing, live colour = picture mean | Pass | `test_reference_validation_and_reset` |
| Import: PNG/JPEG kept byte-for-byte when POV-Ray reads them as they are; EXIF orientation 6 normalised to an upright PNG (corner colours checked); content identity (same bytes, other name → same id; same name, other bytes → different id); unreadable, truncated, GIF, missing, oversized files refused with messages | Pass | `test_import_keeps_or_normalises_and_identifies_by_content`, `test_unusable_pictures_are_refused` |
| Writer: self-lit `image_map … once` backdrop in a light group, `no_shadow no_reflection`, margin colour layer, mean colour for reflections; transparent output, other modes, and no picture leave it out (record kept); floor not removed; bounds unchanged; built-in thumbnails' scene digests unchanged | Pass | `test_writer_backdrop_and_precedence`; existing `test_presets.py` digest tests |
| Staging: the picture is copied next to the scene under a short content name (paths with spaces/non-ASCII); not for transparent output | Pass | `test_scene_files_stage_the_picture` |
| Real POV-Ray 3.7 renders with a labelled-quadrant fixture: orientation, Fit margins at 16.7/283.3 px of 300, Fill crop, zoom 0.5 with offsets (centre at the expected pixel), brightness 0.5 (half linear light), PNG alpha shows the margin colour, EXIF JPEG upright, JPEG, portrait picture in 3:2, 1:1, 2:3 outputs undistorted, square picture filling a portrait output, same composition at 150 × 100 and 600 × 400 | Pass | `test_rendered_framing_orientation_and_alpha`, `test_rendered_sources_outputs_and_resolutions` |
| Glass shows the picture through the atom; an exported folder renders after being moved | Pass | `test_glass_shows_the_picture_and_project_renders_after_relocation` |
| Projects: ZIP package (`project.json` + `assets/<sha256>.png`), schema 6, reopened after deleting the source and clearing the session registry; projects without pictures stay JSON; existing example projects load; missing picture, tampered picture, unsafe entry name, corrupt archive, and a JSON project naming a picture fail with messages | Pass | `test_project_package_round_trip_without_the_source`, `test_damaged_and_unsafe_packages_fail_clearly` |
| Styles: Environment style with picture as package (style schema 2), reopened after deleting the source; plain styles stay JSON; a schema-1 style loads; corrupt package refused | Pass | `test_environment_style_carries_its_picture` |
| GUI: Choose Image is one undo step (undo/redo), marks the project modified and the preview out of date, changes neither camera, output size, nor bounds; live view shows the mean colour; continuous zoom edits merge into one step; offsets, brightness, Fit; Replace keeps framing; Reset Framing; Remove; undo still finds a replaced picture; unusable file keeps the background | Pass | `test_choose_image_is_one_undoable_step_that_changes_nothing_else`, `test_framing_controls_merge_reset_remove_and_replace`, `test_unusable_file_keeps_the_current_background` |
| GUI: floor notice with Turn Off Floor, transparency notice (picture kept), presets remember the picture; a framing change during a running preview discards the stale result | Pass | `test_floor_and_transparency_notices_and_presets`, `test_framing_change_discards_a_running_preview` |
| GUI: save project and Environment style as packages, export copies the picture; reopen in a new window and import the style after deleting the source and clearing the registry | Pass | `test_project_style_and_export_carry_the_picture` |
| GUI on the Mint display (scripted, real POV-Ray): Background group with picture controls and floor notice; preview with a landscape picture | Pass (scripted) | `artifacts/appearance/background-group.png`, `window-image-background.png` (gitignored) |
| Hands-on use by a person; very large photographs (time and memory) | Unverified | |

Decisions: the picture is identified by the SHA-256 of its stored bytes and kept in a
session registry, so undo/redo never loses it; it is stored unchanged when POV-Ray reads
it as it is, otherwise as an upright PNG. Projects and styles are ZIP packages only when
they carry a picture (detected by content, suffix unchanged); limits: 64 MB per picture,
12000 px per side, 50 megapixels; packages up to 256 entries and 1 GB unpacked, with
relative safe names only. Preview requests are identified by the scene revision, which
every picture or framing change increases. The picture lies on a self-lit plane behind
the scene (not in a sky sphere), is excluded from reflections (`no_reflection`; reflective
atoms see the picture's mean colour as POV-Ray background), and is seen through
refraction. Applying an environment preset keeps the picture record (not drawn) so that
switching back to Image restores it.

Regression runs (both features together): `pytest -m "not povray"` 406 passed (strict mode; 34 new non-POV-Ray tests for both
features, and three existing assertions updated: schema number 6 in `test_project.py` and
`test_aspect.py`, the reserved `custom` category in `test_presets.py`); `pytest -m
povray` on `test_background_image.py`, `test_custom_materials.py`,
`test_gui_material_editor.py`, `test_gui_render.py`, `test_gui.py`,
`test_preview_resolution.py`, `test_povray_jobs.py`, and the command-line render 11
passed; `test_presets.py` environment, combination, and floor renders 20 passed (the 30
per-material renders were not rerun: built-in declarations and thumbnail scene digests
are unchanged); `ycrystal pkg.ycrystal --render` on a package with a picture and a
variant (path with a space and ü) rendered with both; doctests; `zensical build --clean
--strict`; ruff.

## FR-MATERIAL-01: custom material variants (post-0.2.0, 15 November 2026)

Development after version 0.2.0; merged in PR #18. **Customize Material…**
(Appearance tab, Edit menu) starts from a Ycrystal recipe, edits typed parameters, and
applies the variant to the default material, an element, or the selected atoms, or saves
it as a personal material.

| Check | Result | Evidence |
| --- | --- | --- |
| Untouched variants of all 13 editable bases (Matte, Satin, Glossy, Ceramic, Plastic, Glass, Frosted glass, Gem, Marble, Jade, Granite, Stone, Wood) write declarations token-for-token equal to the built-ins; kind, colour behaviour, includes, texture space unchanged; built-ins unchanged | Pass | `test_untouched_variants_equal_the_built_in_recipes`; doctest in `ycrystal.presets.custom` |
| Each control changes its POV-Ray property: diffuse, specular/roughness, reflection, phong/phong size, filter, interior ior, normal bumps strength/scale, gem fresnel reflection, pattern scale of pigment (marble) and texture (stone) kinds; live look follows | Pass | `test_each_control_changes_its_pov_property` |
| Invalid values (out of range, NaN, ∞), unknown parameters, empty names, native bases (explanation names `T_Gold_3C`), unknown bases, newer versions, tampered ids, missing parameters rejected | Pass | `test_invalid_definitions_are_rejected` |
| Ids derived from content (`custom_<base>_<digest>`): same definition → same id, other name → other id, never a built-in id; registration idempotent; editing previews registered unlisted | Pass | `test_ids_are_content_derived_and_never_collide` |
| Precedence atom > element > default with periodic-image-specific overrides; bond halves take their atom's variant; readable name/description comments; standard include still external | Pass | `test_precedence_periodic_images_and_bond_halves` |
| Projects and styles embed every used definition and reopen on a clean profile (registry cleared) with identical scenes and declarations; style transfer keeps part and compatibility rules; tampered or missing definitions fail with messages | Pass | `test_projects_and_styles_reopen_on_a_clean_profile` |
| Real POV-Ray renders: untouched Satin, Frosted glass, Marble variants pixel-identical to the built-ins; specular, ior, bump strength, and pattern-scale changes change the image | Pass | `test_rendered_variants` |
| GUI: debounced preview without undo step or modified flag; Cancel restores; Apply is one undo step with undo/redo; menu shows the variant (✎); selection captured at opening; element target; precedence | Pass | `test_preview_then_cancel_leaves_no_trace`, `test_apply_is_one_undoable_step`, `test_selection_is_captured_and_precedence_holds` |
| GUI: native materials read-only with explanation; glass filter explanation; Reset to Base; pattern-only controls | Pass | `test_native_materials_are_read_only_and_reset_restores_the_base` |
| Personal materials: Save as My Material stores the definition in QSettings, gallery lists it (badge fallback icon), it returns after a restart, and a project opens on a clean profile without it; editing during a running preview discards the stale result; a real POV-Ray thumbnail is rendered for a saved variant | Pass | `test_personal_materials_persist_and_files_need_no_profile`, `test_editing_discards_a_stale_preview`, `test_saved_material_gets_a_real_thumbnail` |
| GUI on the Mint display (scripted, real POV-Ray): Customize Material dialog (Frosted glass), preview with the applied variant over a background picture | Pass (scripted) | `artifacts/appearance/customize-material.png`, `preview-custom-material.png` (gitignored) |
| Hands-on use by a person (dialog flow, gallery browsing) | Unverified | |

Decisions: parameter defaults are explicit data in `ycrystal.presets.custom.SCHEMAS`
(equal to the built-in recipes, checked by tests), and recipe text is generated from
them; no POV-Ray text is parsed. Every parameter (including hidden ones such as ambient)
is stored, so a saved figure does not change if a built-in default changes. Personal
materials are a JSON list in `QSettings` (`materials/personal`), thumbnails in
`material-thumbnails/` next to the settings file. Projects (schema 6, top-level
`materials`) and styles (schema 2) embed the definitions they use; package and asset
machinery is shared with FR-BGIMAGE-01 (variants need no binary assets). Native
materials and ASE styles stay read-only.

Regression runs: see FR-BGIMAGE-01 above (one run for both features).

## FR-MEASURE-01: distance and bond-angle measurements (post-0.2.0, 15 November 2026)

Development after version 0.2.0; merged in PR #16. **Distance** and **Bond
angle** modes (View along toolbar and Edit menu, mutually exclusive) measure between
clicked displayed atoms; results go to a new **Measurements** dock at the bottom of the
window. Session-only: nothing is saved in projects.

| Check | Result | Evidence |
| --- | --- | --- |
| Known values: 3 Å distance, 0°, 60°, 90°, 120°, 180°; SrTiO₃ Ti–O = a/2, O–Ti–O = 90° and 180°, Sr–Sr images a and a√3 | Pass | `test_known_distances_and_angles`, `test_displayed_instances_match_the_geometry_in_supercells`; doctest in `ycrystal.core.measure` |
| B is the vertex: the same three atoms in different orders give the expected different angles | Pass | `test_b_is_the_vertex`, `test_angle_order_vertex_and_repeated_measurements` |
| Roundoff: `atan2(\|u × v\|, u · v)`; collinear arms give exactly 0°/180°, large coordinates and tiny angles stay accurate; results always within 0–180° | Pass | `test_roundoff_near_zero_and_straight_angles` |
| Degenerate selections: zero-length arms rejected (in the session at the pick that causes them, keeping earlier picks); the same instance twice rejected; wrong counts, unknown kinds, nonexistent atoms, images without a cell rejected; two distinct atoms at one place give a valid 0 Å distance | Pass | `test_degenerate_selections_are_rejected`, `test_session_rejects_zero_length_arms`, `test_escape_mode_switch_and_rejected_picks` |
| Periodic images: exact instances, no minimum image (8 Å vs 2 Å example); images of one source atom measurable; displayed positions in 1 × 1 × 1, 2 × 3 × 1, and 2 × 2 × 2 (boundary images off) equal `positions[source] + image @ cell` bit for bit | Pass | `test_exact_images_not_minimum_image`, `test_displayed_instances_match_the_geometry_in_supercells` |
| Non-orthogonal cells: hexagonal (120° and 60° between image directions, \|a − b\| = a√3); triclinic distances equal the fractional metric-tensor result for 306 ordered instance pairs (3 atoms × 6 images) | Pass | `test_non_orthogonal_cells` |
| Independence: camera orbit and zoom, atom size, material, and repetitions leave values bit-identical; values equal those from input coordinates | Pass | `test_results_ignore_display_settings`, `test_results_ignore_camera_and_appearance` |
| Interaction with real mouse events: prompts (“Bond angle: select atom B — angle vertex …”), A/B/C picks, empty-space clicks keep picks, a drag starting on an atom orbits and picks nothing, ordinary selection untouched in the modes and working after them; Esc cancels (a second Esc clears the selection); mode switch cancels; the mode stays on after a measurement; results are appended | Pass | `test_modes_are_discoverable_and_exclusive`, `test_distance_by_clicks_reveals_the_panel`, `test_angle_order_vertex_and_repeated_measurements`, `test_escape_mode_switch_and_rejected_picks`, `test_drags_navigate_and_ordinary_selection_is_preserved` |
| Panel: revealed on the first measurement under the 3D view only (right docks keep the corner); window size unchanged; rows with type, identities with image offsets, results with units and vertex; Copy Selected and Ctrl+C give self-contained lines; Remove Selected; Clear All; full-precision tooltip | Pass | `test_distance_by_clicks_reveals_the_panel`, `test_copy_remove_and_clear` |
| Invalidation: boundary images off removes only the measurement whose ball disappeared and cancels the incomplete one, with a note; undo does not resurrect it; hiding a measured atom removes its measurement; loading another structure clears everything | Pass | `test_session_invalidation`, `test_invalidation_on_display_and_structure_changes` |
| Helpers: non-pickable VTK actors (cages and labels in the scene renderer, dashed lines in a non-interactive overlay layer with the same camera); picking at all atoms and next to the marks is identical with and without helpers; exported scene text, bounds, lights, output camera, Fit, undo stack, modified flag unchanged; projects contain no measurements | Pass | `test_helpers_stay_out_of_exports_bounds_fit_and_picking`, `test_distance_by_clicks_reveals_the_panel`; existing POV-Ray GUI render test |
| GUI on the Mint display (scripted): angle with cages, labels, dashed arms and arc; distance between two Sr images with the dashed line over the atoms; panel with two rows under the view | Pass (scripted) | `artifacts/measure/angle-pending.png`, `angle-complete.png`, `distance-images.png`, `panel.png` (gitignored) |
| Hands-on use by a person (clicking in different orientations, keyboard use of the table) | Unverified | |

Design: `ycrystal.core.measure` (pure) computes positions from `AtomId`s and the
structure, distances, angles, text, and holds the `MeasurementSession` (mode, picks,
results). The window routes atom clicks to the session while a mode is on, shows the
instruction in the status bar, passes rows to `MeasurementPanel`, and passes picked
positions to `StructureViewport.set_measurement`. After every geometry change the session
drops measurements whose atoms are no longer displayed (or everything for a new
structure object).

Regression runs (on exactly the committed files): `pytest -m "not povray"` 367 passed
(strict mode; 21 new tests, 12 pure and 9 GUI); `pytest -m povray` on
`test_gui_render.py` and `test_gui.py` 4 passed (including the POV-Ray render compared
with the output frame); doctests in `ycrystal.core.measure`; `zensical build --clean
--strict`; ruff. Not run: the other POV-Ray tests (exported scenes are unchanged: the
helpers are not part of the geometry).

Remaining limitations: revealing the panel shrinks the 3D view like any window resize,
so the output camera stays the same but the preview is marked out of date (and refreshed
if automatic) — resolved on 16 November 2026: a resize is no longer a change of the
figure (see the macOS maintenance section); removed measurements are not restored by undo; the dashed lines are drawn
in front of all atoms, so a guide may cross atoms that lie in front of it; a ball hidden
behind others must be brought into view (orbit) before it can be clicked.

## FR-PREVIEW-01: preview resolution (post-0.2.0, 15 November 2026)

Development after version 0.2.0 (not part of 0.1.0 or 0.2.0); merged in PR #17. The POV-Ray preview dock gets a **Resolution** selector: Small 480 px wide (the
default), Medium 800 px, Large 1200 px, or a custom width (16–4000 px). The height
follows the output's aspect ratio. The main viewport stays the interactive VTK view.

Starting point (verified in `MainWindow.preview_settings`): 480 px on the longer side,
never larger than the output, antialiasing off, so 480 × 320 at 3:2 and 320 × 480 at
2:3. The new presets are widths, as requested: landscape and square outputs keep their
previous default size, while a portrait output's default Small preview is now 480 px
wide (480 × 720 at 2:3 instead of 320 × 480).

| Check | Result | Evidence |
| --- | --- | --- |
| Presets and rounding: 3:2 gives 480 × 320, 800 × 533, 1200 × 800; 2:3, 16:9, 4:3, 1:1 outputs; never larger than the output; every combination of 36 output sizes × 6 widths is within half a pixel of the output shape and inside the limits | Pass | `test_presets_at_three_to_two`, `test_portrait_and_other_shapes`, `test_every_size_matches_the_output_shape`; doctest in `ycrystal.core.aspect` |
| Limits: custom width 16–4000 px (spin box range; other values raise and change nothing); preview height at most 4000 px; each side at least 16 px for extreme shapes (8000 × 16 output → 8000 × 16 preview); the shape is never distorted; unreadable stored values fall back to the default | Pass | `test_limits_keep_the_shape`, `test_custom_width_and_limits`, `test_preference_is_restored` |
| Selector shows the actual preview size and the final PNG size, with the reason for any limit; Custom enables the width field and remembers its width; portrait and non-3:2 outputs update the shown size | Pass | `test_selector_presets_show_the_actual_size`, `test_custom_width_and_limits`, `test_portrait_and_non_three_to_two_outputs` |
| No effect on the figure: output size, output settings (incl. lock ratio), camera, exported scene text, undo history, and modified state are unchanged by resolution changes | Pass | `test_selector_presets_show_the_actual_size`, `test_preview_png_has_the_requested_size` |
| POV-Ray receives the requested size (job `.ini` has `Width=800`, `Height=533`, `Antialias=off`); real POV-Ray PNGs are 800 × 533 (Medium, 1200 × 800 output) and 480 × 720 (Small, 800 × 1200 output) | Pass | `test_requested_size_reaches_povray`, `test_preview_png_has_the_requested_size` (POV-Ray 3.7) |
| Preference persists in QSettings (`render/preview_resolution`, `render/preview_custom_width`), not in projects | Pass | `test_preference_is_restored` |
| Lifecycle: automatic preview off marks the shown preview out of date and starts nothing; on, a debounced preview at the new size follows; the scene revision does not change | Pass | `test_resolution_change_marks_outdated_or_updates` |
| Stale results: the request identity is (scene revision, width, height); a result for an older resolution is discarded with an explanation; a newer request supersedes a running one and only the latest is shown | Pass | `test_stale_resolution_results_never_replace_the_latest`; existing `test_stale_preview_is_discarded`, `test_newer_preview_supersedes_older_one` |
| Display: the image fits the dock without distortion; resizing never starts a render; a large image or long status text does not widen the dock or the window | Pass | `test_resizing_the_panel_fits_without_rendering` |
| GUI on the Mint display (scripted, real POV-Ray): dock at 334 × 272 px with Small, Medium, a portrait Large preview limited to the output, and a Custom width marked out of date; the dock width stays constant | Pass (scripted) | `artifacts/preview/dock-*.png` (gitignored) |
| Hands-on use by a person (choosing presets and typing a custom width) | Unverified | |

Design: `ycrystal.core.aspect.preview_size` (pure) computes the preview size from the
output size and the requested width; `MainWindow.preview_settings` uses it, so preview
jobs keep the output's background and the preview's antialiasing setting. The choice is
window state backed by QSettings and is neither undoable nor saved in projects. The
preview queue tags each job with a `PreviewRequest` (revision, width, height); the dock
shows a result only if its request equals the current one. The dock's status and size
labels wrap within the dock width instead of widening it.

Regression runs (on top of the merged FR-MEASURE-01): `pytest -m "not povray"` 379
passed (strict mode; 12 new tests);
`pytest -m povray` on `test_gui_render.py`, `test_preview_resolution.py`, `test_gui.py`,
and `test_release.py::test_render_from_command_line` 6 passed (other POV-Ray tests not
rerun: exported scenes and final renders are unchanged); doctests in
`ycrystal.core.aspect`; `zensical build --clean --strict`; pre-commit on the changed
files.

Remaining limitations: rounding the height to whole pixels changes the preview's frame
by less than half a preview pixel (as before); a requested size larger than the output is
reduced to the output size, so Large on a small output shows the output size; the shown
image is scaled to the dock, so a preview larger than the dock is displayed reduced.

## FR-LIGHT-01: Lighting Setup window and live lighting (post-0.1.0, 15 November 2026)

New development after the 0.1.0 baseline (not part of M0–M6), released in 0.2.0;
branch `feature/lighting-editor`, submitted as a pull request. Three increments: (A) one shared
helper resolves the lights, (B) a Lighting Setup window shows them in 3D with draggable
key-light handles, (C) the live view uses the resolved key and fill lights instead of
VTK's default light kit.

| Check | Result | Evidence |
| --- | --- | --- |
| A: extraction preserves the export: 672 scenes (4 geometries × 4 cameras incl. orbit/roll, pan, zoom × all 6 lighting and 12 environment presets plus custom, zero-intensity, and shadowless area cases × 2 output sizes) byte-identical before/after, apart from the time stamp | Pass | scripted comparison (scratch script, not kept in the repository); `test_reference_example_is_unchanged` (the SrTiO₃ numbers of the lighting analysis: key (−20.576, 13.544, 12.458), fill (17.361, −3.551, 23.965), area axes 2.178 Å); `test_writer_lights_are_the_resolved_rig` (19 presets/cases) |
| A: conventions: azimuth 0 toward the viewer, +90 screen right, elevation toward screen up; orbit and roll move world positions but not view-relative ones; pan adds \|C − F\| to the distance; zoom and output size change nothing; supercells, boundary images, cell edges, and hidden atoms change C and R as documented | Pass | `test_angles_follow_the_output_camera`, `test_pan_zoom_and_output_size`, `test_displayed_geometry_sets_the_scale` |
| A: intensities (0 omits a light), area diameter = light size × R with axes along screen right/up, panel at C + 3R × key direction with radius 1.6R, fill always shadowless; inverse angles with wrapping, clamping, and the pole | Pass | `test_intensities_size_and_panel`, `test_angles_round_trip_wrap_clamp_and_pole`, `test_guide_arcs_lie_on_the_placement_sphere`; doctest in `ycrystal.core.lighting` |
| C: live view has exactly the two rig lights (scene lights, positional, cone ≥ 90°, attenuation (1, 0, 0), no automatic headlight) at the resolved positions and intensities; they follow orbit/roll/pan, repetitions, intensity changes (0 switches off), and presets | Pass | `test_main_view_uses_the_resolved_rig_instead_of_the_light_kit`, `test_main_view_lights_follow_camera_geometry_and_settings` |
| B: button **Lighting Setup…** and **View ▸ Lighting Setup…**; overview shows key/fill (sphere/cube, labels, intensities), F (cross), C (octahedron), output camera (cone and axis) and frame, horizon ring and azimuth/elevation arcs, area-light diameter (wire sphere) and reflection panel when enabled; read-out of D, R, \|C − F\| | Pass | `test_lighting_setup_opens_and_shows_the_rig`; screenshots `artifacts/lighting/setup-dramatic.png`, `setup-studio-like.png` |
| B: independent overview camera: orbiting it changes neither the output camera, the environment, the scene revision, the exported lights, nor the main view's props; the overview follows output-camera changes (throttled) without moving its own camera; output-size changes redraw the frame | Pass | `test_overview_navigation_changes_nothing_else`, `test_overview_follows_the_output_camera_but_keeps_its_own` |
| B: helper graphics are excluded from exports, geometry bounds, Fit, and picking (separate renderer and window) | Pass | `test_helper_graphics_stay_out_of_exports_bounds_and_picking` |
| B: numeric edits (panel and the window's own keyboard spin boxes, merged like the panel) and presets update the overview | Pass | `test_numeric_edits_and_presets_update_the_overview` |
| B: drag with real mouse events: live lights, both spin boxes, and the overview follow without an undo step, revision, or preview; release = one undo step, one revision, the debounced automatic preview starts; undo restores | Pass | `test_key_drag_previews_then_commits_one_step` |
| B: Esc in the overview, Esc in the main window (Select None), and the right button cancel and restore lights, spin boxes, and overview; no undo step | Pass | `test_cancelled_drag_restores_everything` (3 cases) |
| B: limits and basis: dragging above the structure stops at 89°; the azimuth handle changes only the azimuth; angles are interpreted in the output camera's basis also after orbiting the overview; an unchanged drag adds no step | Pass | `test_drag_respects_limits_and_the_output_basis`, `test_unchanged_drag_adds_no_step` |
| Projects and presets: no new stored state (the project's lighting keys are unchanged); a dragged direction survives save/reopen; presets unchanged | Pass | `test_projects_and_presets_keep_their_lighting`; existing project and preset tests |
| GUI on the Mint display (scripted): overview, labels, drag preview and commit, live view lit from the left (dramatic) and from the right (azimuth +60°) | Pass (scripted) | `artifacts/lighting/main-key-left.png`, `main-key-right.png`, `setup-after-drag.png`, `setup-area-panel.png` |
| Hands-on use by a person (mouse drags in the overview, Esc, keyboard spin boxes) | Unverified | |

Design: `ycrystal.core.lighting` (pure) returns a frozen `LightingRig` with world
positions, directions, intensities, shadow flags, area axes, and the panel; it is derived
on demand from the environment, the output camera, and the displayed geometry, and
nothing new is saved. `scene_to_pov` writes its lights from the rig. The live viewport
re-resolves the rig before every redraw (bounds cached per scene) and sets two VTK scene
lights at those world positions, so no second camera-relative transformation is applied.
The Lighting Setup window (`ycrystal.gui.lighting_setup`) wraps a second VTK view
(`ycrystal.viewport.lighting_view`) with its own camera and default readability lights.
Drags report whole-degree angles; the window previews them (live lights, spin boxes,
overview) without touching the environment and applies the final angles on release
through the existing undoable environment command.

Regression runs: `pytest -m "not povray"` 346 passed (strict mode; 40 new tests);
`pytest -m povray` on `test_gui_render.py`, `test_gui.py`, `test_gui_appearance.py`,
`test_release.py::test_render_from_command_line`, and
`test_presets.py::test_mixed_overrides_render_and_floor_shadows` 7 passed (the other
53 POV-Ray tests were not rerun because every exported scene is byte-identical); doctests;
`zensical build --clean --strict`; pre-commit on the changed files.

Remaining limitations: the live view has no shadows, area-light softness, reflections,
refraction, or reflection panel, and its Phong shading is not expected to match POV-Ray
pixel for pixel; the overview's labels can overlap when lights, F, and the camera line up
in the chosen view (orbit the overview or press Reset Overview).

## FR-RENDER-01: lock aspect ratio of the output size (post-0.1.0, 15 November 2026)

New development after the 0.1.0 baseline (not part of M0–M6); branch
`feature/render-aspect-lock`, merged in PR #14. A padlock button beside Width
and Height in the Render panel keeps the output shape while the resolution changes.

| Check | Result | Evidence |
| --- | --- | --- |
| Interface: checkable button, closed/open padlock (shape differs, not only colour), tooltips, Tab + Space, accessible name, locked by default | Pass | `test_lock_button_defaults_and_states`; screenshots `artifacts/aspect/panel-locked.png`, `panel-unlocked.png` |
| Locked, both directions: 2400 × 1600 → Height 1920 → 2880 × 1920 → Width 3000 → 3000 × 2000 | Pass | `test_locked_editing_links_both_dimensions`, `test_examples_from_the_request` |
| Unlocked: independent edits (→ 2400 × 1920); relocking captures the current ratio without changing the size | Pass | `test_unlocked_editing_is_independent_and_relocking_captures` |
| Toggling changes neither dimension, adds no undo step or preview, marks the project modified | Pass | same test |
| Non-integer ratios, half-up rounding, repeated edits without drift (the naive recomputation drifts 1000 × 700 → 1000 × 697) | Pass | `test_repeated_edits_do_not_drift`, `test_non_integer_ratio_repeated_edits_without_drift` |
| Presets (locked: new target; unlocked: once), Custom state, one-step undo restoring the ratio, atomic Swap inverting the target | Pass | `test_presets_set_the_target_when_locked`, `test_presets_apply_once_when_unlocked`, `test_swap_is_atomic_and_inverts_the_target` |
| Limits and invalid input: linked dimension outside 16–8000 px refuses the whole edit, restores the pair, explains (panel and status bar); invalid text ignored | Pass | `test_limits_reject_the_whole_edit`, `test_limits_reject_the_edit_and_explain` |
| No recursive signals or duplicate updates: one request, one frame update, one scene revision (preview trigger) per edit | Pass | `test_one_request_one_refresh_per_edit` (this also removed two to three redundant revision bumps per size change caused by camera notifications) |
| Composition kept when only the resolution changes (camera, roll, pan, zoom, blue frame) | Pass | `test_resolution_change_keeps_the_composition` |
| Persistence and compatibility: lock state and ratio in `output` (optional keys, schema stays 5); 0.1.0 projects open locked to their own ratio; a ratio that does not fit the size is replaced | Pass | `test_lock_state_in_projects_and_old_files`, `test_lock_state_is_saved_and_restored`, `test_old_projects_open_locked_to_their_own_ratio` |
| GUI on the Mint display: button states, linked/unlocked edits, Custom, blue frame ratio (725 × 604 px frame for 2880 × 2400) | Pass (scripted) | `artifacts/aspect/window-unlocked.png` |
| Hands-on use by a person (mouse and keyboard in the Render tab) | Unverified | |

Design: one pure module (`ycrystal.core.aspect`) does the arithmetic; the panel emits one
complete request per edit (width, height, target ratio) and refreshes its controls under
`QSignalBlocker`; the window applies it through the existing undo command, which now also
restores the target ratio. Toggling the lock is not an undo step.

Regression runs: `pytest -m "not povray"` 306 passed (strict mode); `pytest -m povray`
on `test_gui_render.py`, `test_release.py`, `test_gui.py` 9 passed (output frame, framing
gate, release workflow); doctests; `zensical build --clean --strict`; pre-commit on the
changed files. One existing test (`test_save_and_reopen_after_source_file_is_moved`)
typed an independent 900 × 500 size with the spin boxes; with the new locked default it
now unlocks first, and it also checks that the lock state is restored.

## FR-COLOR-01: explicit colour entry and colour names (post-0.1.0, 15 November 2026)

New development after the 0.1.0 baseline (not part of M0–M6); branch
`feature/color-input-names`. Purpose: reproducible element colours without visual
matching, and colours identifiable by text. An audit against the written requirement
found and fixed: three bare numbers ≤ 1 and HSV/HSL percentages were silently read as
fractions; hue ran to 360 with whole-number HSV/HSL (rounding up to two channel steps);
greys lost their hue; OK accepted unapplied invalid text; named-colour and spectrum texts
lacked RGB values; exact named colours were labelled "nearest"; the named-colour grid had
no keyboard access; no note when a material hides the colour.

| Acceptance item | Result | Evidence |
| --- | --- | --- |
| 1. RGB `(255, 0, 0)`, HEX `#FF0000`, HSV `(0°, 100%, 100%)`, HSL `(0°, 100%, 50%)`, and `red` give the same colour; black, white, grey, custom colours, range ends (hue 359), round trips | Pass | `test_five_notations_give_the_same_red`, `test_boundaries_and_custom_colours`, `test_each_representation_sets_the_same_dialog_colour`; repeated HSV↔HSL↔hex switching over 4,096 colours stays within one 8-bit step (`test_representation_round_trips_stay_within_one_channel`); integers are 0–255 and decimals 0–1, never guessed (`test_numbers_are_never_reinterpreted`) |
| 2. Hover/focus texts: named swatch and element colour cell show name, HEX, RGB; spectrum hover updates per location without assigning; non-catalogue colours get exact values plus an explicitly approximate name | Pass | `test_named_swatch_tooltip_text` (`red — #FF0000 — RGB (255, 0, 0)`), `test_colour_buttons_name_their_colour_and_use_the_dialog`, `test_spectrum_hover_does_not_assign`, `test_label_combines_description_and_name` (exact vs nearest) |
| 3. Keyboard-only editing and selection; invalid entries cannot be accepted; Cancel restores; one undo step | Pass | `test_keyboard_only_selection_and_names`, `test_invalid_text_blocks_ok`, `test_cancel_undo_persistence_and_export` |
| 4. Scene, live viewport, `.pov` export, reopened project, and imported style keep the base colour | Pass | same test: geometry colour, `Ycr_sRGB(…)` in the export, project and style values identical |
| 5. Coordinates, radius, material, opacity unchanged by colour edits; own-pigment materials explained | Pass | same test; `test_colour_note_for_materials_with_own_pigment` |
| Bug reported on the Mint desktop: the dialog took the element's colour as background | Fixed | The colour button's style sheet was unscoped and cascaded into the dialog (its child). Now scoped to `QPushButton#colorButton`, and the dialog is parented to the window; `test_dialog_does_not_take_the_button_colour` |
| Manual Appearance check on the Mint desktop (numeric entry, hover/focus texts, keyboard, Cancel/Undo, restoration) | Unverified | Needs a person; the automated GUI tests ran on the Mint display |

Unchanged by design: the plain colour descriptions (vocabulary and rules) approved by the
project owner. The colour model is the existing sRGB 0–1 triple in `SceneSettings`
(no schema change; 0.1.0 projects open unchanged). Tests: 51 conversion and 14 dialog/GUI
tests. Caveats: descriptions are English only and approximate; nearest names use
CIEDE2000 (sRGB, D65); no screen colour picker; the spectrum itself has no keyboard
navigation (the fields and the named-colour grid do).

## M6 acceptance evidence

Gate: a clean-install demonstration using only documented instructions, a reproducible
example project/render, and a release checklist distinguishing passed, failed, and
unverified items; release artifacts prepared. The full checklist is in
[Release procedure and checklist](development/release.md).

| Check | Result | How |
| --- | --- | --- |
| Clean install with the documented commands | Pass | Fresh directory: `gh repo clone`, `/usr/bin/python3 -m venv .venv`, `pip install -e . -c constraints.txt` (42 s, warm pip cache), `ycrystal --version` → 0.1.0, `--check-renderer` → PASS (0.14 px), example `--render` (1.8 s), `--export-pov`, rejection of `ibrav = 2` (exit 1), GUI start (running after 10 s, no errors) |
| Documented HTTPS clone | Fail while private | Needs credentials; `gh repo clone` and SSH documented |
| Linux Mint launcher | Pass (files); menu unverified | `ycrystal --install-desktop` writes launcher, SVG icon, and `.ycrystal` MIME type for the user; `desktop-file-validate` silent; `--uninstall-desktop` removes them; appearance in the Cinnamon menu needs a person |
| Reproducible examples | Pass | `examples/` (3 projects, 1 style; generated by `scripts/make_examples.py`, no machine paths); `ycrystal FILE --render OUT.png` without a window; each renders in 1–2 s at 400 × 300; tests render all examples |
| End-to-end workflow (plan, section 10) | Pass (automated on the Mint display) | `test_release_workflow`: CIF → rotate/pan → 2 × 2 × 2 → Ti glossy → white studio → render → save → close → source deleted → reopen → render again (identical images), then POSCAR and QE imports, `ibrav ≠ 0` rejected; a hands-on run is still recommended |
| User guide | Done | New pages: [examples and the command line](guide/examples.md), [support matrix](guide/support.md); install guide (checks, launcher, update, uninstall); troubleshooting (launcher) |
| Performance on stated hardware | Recorded | Intel Core Ultra 5 135U, 8 GB, Meteor Lake graphics: 71 atoms 31 ms and 1,315 atoms 70 ms per drag step (unchanged from M2 despite the M4/M5 overlays); render times in the guides |
| Review | Done | Constraints (pinned tested set), licences (`THIRD_PARTY_NOTICES.md`: MIT with separately installed LGPL Qt/ASE; POV-Ray AGPL run as a separate program), include dependencies, known limitations |
| Release artifacts | Pass | `uv build`: `ycrystal-0.1.0.tar.gz` (adds constraints, examples, fixtures, notices via `MANIFEST.in`) and `ycrystal-0.1.0-py3-none-any.whl` (presets, 42 thumbnails, icon, notices); the wheel installs into a fresh environment and renders an example |
| Tests | Pass | `tests/test_release.py` (9, including renders); 218+ non-rendering tests locally; full suite in CI |

### M6 caveats

- The clean install used a warm pip cache; a first-time download (about 300 MB) was not
  timed.
- The launcher's appearance in the Cinnamon menu and double-click opening of projects
  need a person at the desktop.
- The end-to-end workflow was driven automatically on the real display; a hands-on run
  before publishing is recommended.
- Python 3.10/3.11, Wayland, other distributions, and POV-Ray 3.8 remain unverified
  (see the support matrix).
- Not tagged or published: the repository is private and publication follows the
  maintainer's workflow.

## M5 acceptance evidence

Gate: dragging is reversible; style reuse preserves the new structure's scientific
coordinates; project round trips retain all implemented settings. The plan splits M5
into M5a (supercell handles), M5b (axis-constrained rotation), and M5c (styles and
complete undo coverage).

| Check | Result | How |
| --- | --- | --- |
| M5a: handles | a/b/c handles (red, green, blue) outside the projected block along each periodic lattice direction; hidden without a cell, for non-periodic axes, and for directions nearly along the line of sight; *View ▸ Supercell Handles* toggles them (remembered); never exported | `test_handle_drag_adds_cells_in_one_undo_step`, `test_handle_drag_clamps_cancels_and_hides`, `test_no_handles_without_cell`; screenshots in `artifacts/m5/` |
| M5a: drag | Integer steps from the mouse movement projected on the lattice direction; orange outline of the new block and a label with cell and atom counts during the drag; no orbit while dragging; geometry built once on release; minimum one cell, maximum 20; Esc or right button cancels | same tests (preview `(3, 1, 1)` before release, camera unchanged during the drag, repetitions unchanged after Esc) |
| M5a: reversible | One undo step per drag; undo/redo restore the repetitions; numeric controls follow; large expansions still ask for confirmation | `test_handle_drag_adds_cells_in_one_undo_step` |
| M5b: rotation modes | *Rotate freely* (trackball, M0) or *about a, b, c, x, y, z*: left drag turns about the chosen axis through the view centre; the axis keeps its screen direction; a circular motion is used when the axis points at the viewer; clicks still select, Shift-drag still pans | `test_axis_rotation_keeps_the_axis_fixed`, `test_click_still_selects_in_axis_mode`; `Camera.rotate_about` checked against an explicit Rodrigues rotation (`test_rotate_about_axis_keeps_axis_fixed_on_screen`) |
| M5b: exact steps | ⟲/⟳ (Ctrl+Left/Right) turn by 5–90° about the axis, or about the line of sight in free mode | `test_rotate_buttons_turn_by_the_step` |
| M5c: styles | `.ycstyle` files (materials, colours, radii, display, environment, output size; no structure, no camera); parts selectable on import; one undo step | `tests/test_style.py`, `test_style_export_import_to_another_structure` |
| M5c: transfer rules | Element-keyed settings and bond-pair rules transfer to elements the target contains; per-atom materials and hidden atoms only when the element sequence is identical; everything left out is explained in a message | `test_other_structure_gets_compatible_parts_and_explanations`, `test_same_structure_receives_everything` |
| Coordinates preserved | Style import, handle drags, and rotation never change scientific positions | assertions in the style, interaction, and docs-example tests |
| M5c: undo coverage | Every figure change is one undo step and undo restores the exact state: hiding, show all, boundary atoms, repetitions, cell mode, bonds (on/off, tolerance, radius, pairs), atom size, element radius, element colour, default/element/atom materials, clearing overrides, environment, lighting, output size; plus handle drags and style imports. Output size is now undoable (an M3 caveat); merged spin-box steps show the latest value | `test_every_presentation_change_is_undoable` (20 operations), `test_output_size_keeps_output_camera_and_marks_modified` |
| Radii | Atom size (× covalent radius) in the Structure tab; per-element radius in Å in the Appearance tab; reset returns colour and radius together | `test_radius_controls_and_project_round_trip` |
| Project round trips | Schema 5 adds element radii; overrides, colours, radii, environment, output size restored exactly; older schemas unchanged | `test_overrides_colours_radii_and_environment_round_trip`, `test_radius_controls_and_project_round_trip` |
| Verification run | 218 non-rendering tests pass locally (strict mode, 62 rendering tests deselected); rendering tests were not rerun locally (M5 does not change the POV-Ray writer) to spare the laptop; CI runs the full suite | `pytest -m "not povray"`; doctests; `scripts/docs_examples.py`; `zensical build --clean --strict`; `pre-commit run --all-files` |

### M5 caveats

- Handles are 2D markers placed outside the projected block and clamped to the view;
  with a strongly tilted cell a handle can sit far from its face. Directions nearly
  along the line of sight have no handle until the view is rotated.
- The view refits after a handle drag (as after numeric changes), so the block stays in
  the frame.
- Esc cancels a drag through the window's *Select None* shortcut; without a focused
  window the viewport's own key handler does it.
- Rotation modes and the step angle are navigation settings, not saved in projects and
  not undoable (camera navigation stays outside the undo stack by design).
- Styles transfer per-atom settings only for identical element sequences; there is no
  matching of atoms between different structures.
- Style files store the source's element sequence (one symbol per atom); for very large
  structures the file grows accordingly.

## M4 acceptance evidence

Gate: at least 20 materials and 12 environments render individually; representative
glass/metal/sky combinations pass; style changes survive reopen; live approximations
are labelled and the actual POV-Ray preview is available for effects VTK cannot show.

| Check | Result | How |
| --- | --- | --- |
| Catalog size | 30 materials, 12 environments, 6 lighting presets | JSON manifests in `src/ycrystal/presets/`; `test_catalog_meets_the_m4_targets` |
| Native material types | All four declaration kinds (13 finish, 4 pigment, 8 texture, 5 material); 16 materials use native POV-Ray 3.7 identifiers (`T_Gold_3C`, `F_MetalD`, `M_Glass`, `White_Marble`, `T_Stone25`, …) with their include files; 14 have their own pigment | `test_writer_declares_each_material_kind`, `test_native_material_and_finish_identifiers`; every listed include file exists in the installed `povray-includes` (`test_manifest_fields_are_consistent`) |
| Every catalog entry renders | Pass: 30 materials and 12 environments, each in its own POV-Ray 3.7 render | `test_every_material_renders`, `test_every_environment_renders` (size, alpha, drawn structure, gradient for gradients and skies) |
| Representative combinations | Pass: glass/cloudy sky (blue sky above), gem/blue gradient, chrome/dark reflective studio (mirror image below), gold/dark grey, polished metal/black, marble/transparent (alpha 0), clear glass/white studio | `test_representative_combinations`; mixed default/element/atom overrides in the grey studio (`test_mixed_overrides_render_and_floor_shadows`) |
| Genuine thumbnails | 42 POV-Ray thumbnails (128 × 128 px, 455 KB total) of fixed scenes; `index.json` records a digest of each scene, and a test fails when a recipe or the writer changes without re-rendering | `scripts/render_thumbnails.py` (all 42 in about 34 s on the development laptop); `test_every_preset_has_a_current_thumbnail`; reviewed visually (`artifacts/m4/`) |
| Galleries, search, favourites | Pass: search by name, description, category, POV-Ray identifier, or include file; category filter; favourites in `QSettings` | `test_material_gallery_search_categories_and_favourites`, `test_environment_gallery_applies_preset` |
| Assignment and precedence | Pass: default, element, and displayed-atom overrides (atom > element > default); half-bonds follow their atom; separate element colours; every step undoable | `test_material_precedence_and_colours`, `test_gallery_targets_apply_and_undo`, `test_element_table_material_and_colour`, `test_selection_buttons_and_edit_menu` |
| Background, floor, lighting | Independent controls; a preset initialises all three. Solid, gradient, and sky backgrounds on a frame-aligned backdrop; tilted floor with shadows and optional reflection; key/fill intensities, direction, area-light size, shadows, reflection panel; spin-box drags merge into one undo step | `test_floor_backdrop_lights_and_reflector`, `test_environment_controls_merge_and_lighting_presets` |
| Transparency | Transparent output leaves out floor and backdrop | writer and render tests (alpha 0 at the corner) |
| Projects | Schema 4 restores overrides, colours, and the full environment exactly; schema-3 files keep their M3 appearance; unknown materials/lighting are refused with an update message | `test_schema4_overrides_colours_and_environment_round_trip`, `test_schema3_file_keeps_its_m3_appearance`, `test_overrides_and_environment_survive_reopen`, `test_render_with_overrides_after_reopen` |
| Includes in exports | Header lists required include files; export warns if one is missing; render failures name the missing file and `povray-includes` | `test_export_reports_include_files`, `test_missing_include_is_explained` |
| Live approximations labelled | One VTK actor per material; gradients and floor colours approximated; the Appearance tab states that shadows, reflections, refraction, clouds, and procedural textures appear only in the POV-Ray preview | `test_live_view_approximations` |
| Earlier gates unchanged | M0 evidence: 0.067 px live view, 0.034 px POV-Ray; M3 gate tests pass | `scripts/m0_evidence.py`; `tests/test_gui_render.py` |
| Packaging and docs | Wheel contains 30 + 12 manifests, `lighting.json`, 42 thumbnails, and `index.json`; new guide page lists every preset (checked by a test); strict docs build clean | `uv build --wheel`; `test_appearance_guide_lists_every_preset`; `zensical build --clean --strict` |
| Automated suite | 260 passed, 0 skipped (strict mode) before the final UI/doc touch-ups; afterwards the non-rendering tests were rerun | `YCRYSTAL_REQUIRE_INTEGRATION=1 pytest -q -rs`; CI runs the full suite |

Render times on the development laptop at preview size (480 × 320, SrTiO3 2 × 2 × 1,
no antialiasing): satin on white 0.9 s, satin in the white studio 1.3 s, chrome in the
dark studio 1.2 s, marble on a gradient 1.0 s, tinted glass on white 4.5 s and on the
cloudy sky 5.2 s, tinted glass in the white studio (area light) 39 s.

### M4 caveats

- Transparent materials with area lights (Studio and Top lighting) are slow: POV-Ray
  traces filtered shadow rays through the glass (5 × 5 area samples). The guide
  recommends Soft/Bright lighting or switching off automatic previews while composing.
  The *Bright* preset is a point light for this reason.
- Live view: one material per actor with Phong approximations; floors become a flat
  colour, skies a gradient; no shadows, reflections, refraction, clouds, or procedural
  patterns (labelled in the panel).
- Native metals (`T_*_3C`, `Polished_Chrome`) keep POV-Ray's own finishes (ambient
  0.1–0.35, strong reflection); on white backgrounds they look pale. Dark and studio
  environments with the reflection panel suit them better.
- Procedural textures use the same pattern orientation on every atom.
- Editable material parameters (for example a custom refractive index), user include
  files, and image backgrounds are not implemented (later work in the plan).
- Floor geometry is tied to the view (below the frame, tilted 20° towards the viewer);
  it is not a fixed plane in crystal coordinates.
- Material overrides refer to displayed-atom IDs, like hiding; transferring a style to
  another structure is M5.
- Thumbnail digests depend on the exact scene text; a different `libm` could in
  principle change the last printed digit of a coordinate (CI and the development
  machine share Ubuntu 24.04's).

## M3 acceptance evidence

Gate: the same saved scene produces correctly framed preview and final images; Cancel
and failure recovery work; dimensions and alpha pass checks; the alpha catalog is
usable from import through project save/reopen and PNG output.

| Check | Result | How |
| --- | --- | --- |
| Saved scene → framed preview and final images | Pass | `test_saved_scene_renders_framed_preview_and_final`: scene saved from a 1150 × 700 window, reopened in a 900 × 820 window; the output camera is restored exactly; the 480 × 300 preview and the 640 × 400 final PNG both have every sphere centre within 1 px of the output camera's projection, correct colours, and a transparent background |
| Output frame | Pass | Largest rectangle with the output aspect ratio inside the view (4 % margin), centred, dimmed outside; the output camera (view camera × frame/height ratio) survives window resizes and output-size changes; resizing does not mark the project modified (`test_gui_render.py`) |
| Live view ↔ POV-Ray through the frame | Pass | Non-square 480 × 320 output in a differently shaped window: POV-Ray centres < 1 px from the model; live-view centres mapped through the frame agree < 1 px (`test_render_from_gui_matches_output_frame`). `scripts/m0_evidence.py` (mouse-navigated, 626 × 417 output): 0.070 px POV-Ray, 0.103 px live view |
| Output size controls | Pass | Width/height 16–8000 px, aspect presets, swap; toolbar label; the preview keeps the output aspect (480 px long side); not undoable but marks the project modified |
| True POV-Ray preview | Pass | Same exporter and output camera at preview size, antialiasing off; F5 / button / automatic after changes (600 ms pause); errors shown in the dock without dialogs |
| Serialized previews, superseded work cancelled | Pass | One preview process at a time: a newer request cancels the running job and replaces any pending one (`test_queue_supersedes_running_and_pending_jobs`: jobs A, B, C → A cancelled, B never started, C rendered; no job directories left) |
| Stale-result suppression | Pass | Each preview carries the scene revision; a result for an older revision is discarded and the dock says so (`test_stale_preview_is_discarded`) |
| Final render, progress, Cancel | Pass | `QProcess`, status-bar progress from POV-Ray's `Rendered N of M pixels` lines (`Verbose=on`); Cancel stops it, leaves the destination untouched, shows no error, re-enables Render (`test_cancel_final_render`) |
| Failure recovery | Pass | A failing renderer shows an explanation; the next render succeeds with the right size (`test_failed_render_then_successful_render`) |
| Dimensions and alpha | Pass | Final and preview sizes exact; transparent background → alpha 0, opaque presets → 255; glass lets alpha through (correct) |
| Alpha catalog | Pass | 5 materials (matte, satin = previous finish, glossy, metallic, glass with `interior { ior 1.45 }`) and 3 backgrounds (white, transparent, dark grey with light cell edges) as JSON manifests; all 15 combinations render with POV-Ray 3.7 (`test_presets.py`); undoable; live view uses each material's approximation |
| Readable export | Pass | `.pov` records Ycrystal and POV-Ray versions and any required standard includes (none for the built-ins; include handling tested with a substituted manifest); `.ini` sets every output option, `Output_Alpha` for transparent backgrounds, `Verbose=on` |
| Project restoration | Pass | Schema 3 stores material, background preset, transparency, explicit output size; schema-1/2 files open unchanged (satin, transparent preset when their output was transparent); unknown presets refused with an update message |
| Packaging | Pass | A non-editable wheel contains the 8 preset manifests (`package-data`) |
| Automated suite | 202 passed, 0 skipped | `YCRYSTAL_REQUIRE_INTEGRATION=1 pytest -q -rs`; doctests incl. presets and progress parser; `scripts/docs_examples.py`; `zensical build --clean --strict`; `pre-commit run --all-files` |

Hands-on on the Mint display (`artifacts/m3/`): SrTiO3 2 × 2 × 1 with glass atoms on dark grey,
4:3 output frame, automatic preview "Up to date · 480 × 360 px · 1.4 s", 1200 × 900
render in 11.2 s showing refraction through the glass.

### M3 caveats

- Previews use full quality without antialiasing; glass, metallic reflection, and large
  supercells make them slower (seconds). Automatic previews are on by default and can be
  switched off in the preview dock (the choice is remembered).
- POV-Ray reports progress about once per second; short renders show only 100 %. A
  successful render always ends at 100 % (added after a CI run whose last report was 99 %).
- Cancel kills the POV-Ray process; nothing partial is kept.
- The frame margin (4 %) is fixed. Output size is not undoable.
- One material for all atoms and bonds; per-element/per-atom assignment, galleries with
  POV-Ray thumbnails, more presets, and lighting controls are M4.
- `python -m doctest docs/development/examples.md` reports fence-line mismatches (the
  closing ``` is read as expected output); the outputs themselves match. Pre-existing on
  `main`; CI does not doctest Markdown.

## M2 acceptance evidence

Gate: triclinic and hexagonal examples preserve correct geometry, stable selection, and
original coordinates; expected bond/image counts; reversible repetition changes;
navigation does not modify coordinates. The first increment (boundary atoms,
selection, hiding, undo) is listed in the next section.

| Check | Result | How |
| --- | --- | --- |
| Orthogonal SrTiO3, n × n × n (n = 1–3) | Pass | (n+1)³ Sr, n³ Ti, 3n²(n+1) O; 6n³ Ti–O and 12n²(n+1) Sr–O bonds; equal to a brute-force distance search over the displayed atoms; no duplicate bonds (`test_supercells_bonds.py`) |
| Hexagonal MgB2, n × n × m | Pass | (n+1)²(m+1) Mg, 2n²m B; (3n² − 2n)·m B–B bonds (honeycomb); brute force agrees |
| Diamond Si (conventional cell) | Pass | (n+1)³ + 3n²(n+1) + 4n³ atoms (18 at 1×1×1, as VESTA); 16n³ bonds, all 2.3517 Å |
| Triclinic cell | Pass | 5n³ atoms at general positions; displayed bonds equal brute force for 1×1×1, 2×3×1, 2×2×2; periodic bonds unique (no reverse pairs) and complete against a search over neighbouring cells |
| Stable IDs, reversibility, coordinates | Pass | Every atom of 1×1×1 has the same ID and position at 3×3×3; 1 → 3 → 1 reproduces IDs, positions, and bonds exactly; hidden IDs persist across repetition changes; structure arrays unchanged |
| Non-periodic axes and molecules | Pass | No repetition along non-periodic axes; a molecule shows O–H bonds only |
| Cell edges | Pass | All unit cells (grid lines), outline of the block, or the original cell; counts checked (e.g. 27 grid lines at 2×2×2) |
| Repetition controls | Pass | Spin boxes a/b/c (1–20), "− all", "+ all", "1 × 1 × 1"; each change one undo step; the panel follows undo/redo; the view is refitted to the new block; selection kept by ID (`test_gui_scene.py`) |
| Large-expansion warning | Pass | Above 20,000 displayed atoms Ycrystal asks before applying (estimate computed without building geometry); declining leaves everything unchanged |
| Bonds panel | Pass | Show/hide, tolerance (× sum of covalent radii; consecutive edits merge into one undo step), radius, per-element-pair switches with per-cell counts and lengths |
| View directions | Pass | a, b, c, x, y, z (Shift: opposite side); the axis points at the viewer with the next axis up (e.g. down c: a right, b up); triclinic directions follow the lattice vectors; result framed |
| POV-Ray export | Pass | Bonds as half cylinders textured like their atoms; grid edges; render matches the live view (`artifacts/m2/`) |
| Projects | Pass | Schema 2 stores repetitions, cell mode, and bond settings; schema-1 projects open with bonds off, exactly as saved |
| Automated suite | 162 passed, 0 skipped | `pytest -q -rs`; `pre-commit run --all-files` clean |

Display benchmark (`scripts/benchmark_scene.py`, SrTiO3, Intel Meteor Lake integrated
graphics, Mesa 25.2.8, 1100 × 700 viewport, 8× MSAA). "Drag step" is a synthetic
left-button drag through VTK's interactor with every step repainted before the next.

| Cells | Atoms | Bonds | Build (s) | Load (s) | Drag step (ms) | Live detail |
| --- | --- | --- | --- | --- | --- | --- |
| 2³ | 71 | 192 | 0.02* | 0.16 | 38 | 40×28 spheres |
| 6³ | 1,315 | 4,320 | 0.03 | 0.09 | 72 | 40×28 |
| 10³ | 5,631 | 19,200 | 0.07 | 0.22 | 84 | 24×16 |
| 14³ | 14,939 | 51,744 | 0.17 | 0.41 | 88 | 16×10 |
| 16³ | 22,065 | 76,800 | 0.26 | 0.50 | 105 | 16×10 |
| 20³ | 42,461 | 148,800 | 0.59 | 0.82 | 150 | 16×10 |

\* first call 0.49 s (one-time import of ASE's neighbour list). The live view lowers
sphere and bond tessellation above 2,000 and 8,000 atoms (POV-Ray always renders exact
spheres); without this, 14³ took 232 ms per step and 20³ 640 ms. The soft limit of
20,000 atoms keeps a drag step near 100 ms or less on this hardware.

### M2 caveats

- The default bond rule (1.1 × sum of covalent radii, metal–metal off in compounds)
  also bonds Sr–O in perovskites; switch the pair off in the Bonds panel if not wanted.
- Bonds are drawn only between displayed atoms (no bonds to atoms beyond the boundary).
- Each synthetic drag step costs at least ~38 ms even for tiny scenes; most of it is
  spent in Qt while PyVistaQt's `QOpenGLWidget` presents the frame. It predates M2 and
  is not investigated further here; VTK's own `QVTKRenderWindowInteractor` is the
  documented fallback if real interaction proves sluggish.
- Supercell drag handles (M5), reciprocal-axis view directions, and lighting (M4,
  POV-Ray currently casts hard shadows) are not part of M2.

## M2 first increment: boundary atoms, selection, hiding (requested ahead of M1)

| Check | Result | How |
| --- | --- | --- |
| Boundary images like VESTA | Pass | SrTiO3 (5 input atoms) shows 15: Sr on all 8 corners, O on all 6 face centres, 1 Ti; each displayed position = input position + integer lattice offset |
| Wrapping and tolerance | Pass | Atoms given outside the cell are wrapped; fractional 0.9999999 is drawn at 0 and 1; no images along non-periodic axes; general positions get none |
| Boundary toggle | Pass | View ▸ Show Boundary Atoms off shows the 5 input atoms at their input positions; undoable |
| Click selection | Pass | Click without drag selects the front-most ball (analytic ray–sphere pick on the shared camera); Ctrl+click toggles; click on empty space or Esc clears; a drag never selects |
| Selection information | Pass | Status bar: element, label, atom number, image offset, fractional and Cartesian coordinates; multiple selection shows counts |
| Hide one of several equivalent balls | Pass | Delete (or Backspace) in the 3D view hides only the selected ball, e.g. one Sr corner leaves the other 7; the POV export omits it and notes the count; structure coordinates unchanged |
| Undo/redo | Pass | Ctrl+Z / Ctrl+Shift+Z (Ctrl+Y) for hide, Show All Atoms, and the boundary toggle; hidden IDs survive toggling |
| Automated suite | 66 passed, 0 skipped | `pytest -q -rs` with `/usr/bin/povray` |

## Maintenance: macOS support and cross-platform tests (16 November 2026)

No feature was added and no milestone status changed. Work done on a Mac mini (macOS
15.8, Apple silicon, one non-Retina 2560 × 1440 display) on the branch
`feature/cross-platform`; one repository and one codebase serve Linux and macOS. Every
result below was observed on that Mac. **Linux was not re-run with these changes**; the
Ubuntu CI job does that when the branch is pushed.

Before the changes, on the Mac (Homebrew Python 3.12.16 and POV-Ray 3.7.0.10, all pins
of `constraints.txt` installed): `ycrystal --check-renderer` passed; 282 tests without
POV-Ray and 67 with it passed; all 147 GUI tests were skipped because the test suite
looked for `DISPLAY`. Run on the macOS desktop, 138 GUI tests passed and 9 failed.

| Finding | Cause | Change | Evidence |
| --- | --- | --- | --- |
| GUI tests skipped on macOS | `tests/conftest.py` required `DISPLAY`/`WAYLAND_DISPLAY` | `display_available()`: macOS and Windows use the desktop session (unless Qt draws off-screen); Linux unchanged | 148 GUI tests run and pass |
| Live view one frame behind: screenshots, lights (3 tests) | PyVistaQt's `QtInteractor.render()` returns before drawing on macOS only (it emits its render signal from a helper thread) | `viewport/interactor.py`: `SynchronousInteractor`, used by both views, draws in the calling thread on every platform | `test_live_view_matches_camera_model`, two lighting tests |
| Previews discarded as "scene changed" in windows up to 714 px high (5 tests) | macOS controls are taller: the window's minimum height is 688 px, and 714 px while the preview progress bar shows, so the window grows, the view is resized, and a resize counted as a view change | A resize keeps the output camera and is no longer reported (`camera_changed` is not emitted for the scale adjustment): no new `scene_revision`. **Applies to Linux too**: resizing the window or a panel no longer marks the preview out of date | The five preview tests; new `test_resizing_the_view_keeps_the_preview_valid` |
| Export warned that `metals.inc` was missing (1 test) | Include files were searched only in `/etc/povray`, `~/.povray`, `/usr/share`, `/usr/local/share` | `include_directories(executable)` reads the `povray.ini` and include folders of the executable's installation prefix (link and real location); the old locations remain | `test_export_reports_include_files`; 4 tests with stand-in installations |
| Personal-material thumbnails would go to `~/Library/Preferences/material-thumbnails` | The folder was "next to the settings file" | `gui/native.py`: Qt's application data folder where the native settings are not a file of their own (macOS, Windows); Linux and INI settings unchanged | `test_personal_thumbnails_stay_out_of_shared_folders`; real launch reports `~/Library/Application Support/Y-Matter Lab/Ycrystal/material-thumbnails` |
| `--install-desktop` wrote freedesktop files on macOS | No platform check | The two options print an error and return 1 outside freedesktop systems; Linux unchanged | `test_launcher_command_applies_to_freedesktop_systems_only`; run by hand: exit 1, nothing written |
| Help texts said "Ctrl" | Qt maps Ctrl to ⌘ on macOS | `native_keys` for the Mouse Controls help and three tooltips; install hints name `brew install povray`; the POV-Ray file dialog starts at the found executable instead of `/usr/bin` | `test_native_key_names` |
| Two GUI tests failed at a 2× display scale | Test assumptions: one compared logical with device pixels; one compared cameras exactly after the output size went to another shape and back (they differ in the last digit) | The expected pan is multiplied by the device pixel ratio (`tests/test_gui.py`); the camera is compared with `_same_camera` (`tests/test_preview_resolution.py`) | Both pass at scale 1 and with `QT_SCALE_FACTOR=2` |

Results after the changes, on the Mac:

- `YCRYSTAL_REQUIRE_INTEGRATION=1 pytest -q -rs`: **505 passed, none skipped** (about 170 s):
  the 496 earlier tests and 9 new ones (`tests/test_platform.py`, one in
  `tests/test_gui_render.py`).
- The steps of the macOS CI job, run locally in order: version, `--check-renderer`
  (PASS, POV-Ray 3.7.0.10 at `/opt/homebrew/bin/povray`, 0.14 px), doctests,
  `scripts/docs_examples.py`, `pytest -m "not gui"` (357 passed).
- GUI tests with an emulated 2× display scale (`QT_SCALE_FACTOR=2`): all 148 passed
  after the two test corrections above (two failed before them). This is not a test on
  a Retina display.
- Real launch through `ycrystal.app.main` (scripted, 7 s): Cocoa platform, native menu
  bar, shortcuts shown as ⌘O, ⇧⌘Z, ⌘←, …; window icon set; the automatic POV-Ray preview
  reached "Up to date" in the default 1100 × 720 window; exit status 0.
- `pre-commit run --all-files` and `zensical build --clean --strict` (documentation
  pins installed on macOS): clean.

Continuous integration: the `test` job is now a matrix with one entry per operating
system. Ubuntu keeps its job name and runs everything under Xvfb; macOS 15 (arm64,
Homebrew POV-Ray) runs the tests that open no window. POV-Ray is found on `PATH` on
both. **The changed workflow has not run on GitHub.** `constraints.txt` gains the two
macOS-only packages that PyVista needs there (`pyobjc-core`, `pyobjc-framework-cocoa`,
with environment markers).

Unverified: Linux with these changes; the macOS CI job; a Retina display; Intel Macs;
hands-on use on macOS (native file dialogs, trackpad scrolling and pinching, ⌘ + click,
dark appearance, long renders); Windows (no test of any kind). On macOS Ycrystal runs
from the checkout: there is no application bundle, so the Dock shows "Python".

## Maintenance: repository tooling (15 November 2026)

No product behaviour changed and no milestone status changed. Inspired by quacc's setup,
with deliberate differences: safe Ruff fixes only (no `--unsafe-fixes`), monthly
updates with at most three open pull requests, and no automatic merging.

| Item | Result | How |
| --- | --- | --- |
| `.pre-commit-config.yaml` | Clean on all tracked files | ruff-check `--fix` and ruff-format v0.17.5; pre-commit-hooks v6.0.0 (trailing whitespace, end of file, check-yaml, large files > 250 KB with `--enforce-all`); local `ruff-version-sync` hook; pre-commit.ci autoupdate monthly. Fixtures exempt from whitespace fixers |
| Ruff version sync | Pass | Hook rev v0.17.5 = `ruff==0.17.5` in constraints.txt; the sync hook exits 1 on a mismatch in either direction (checked) |
| Mechanical formatting | 25 files reformatted, separate commit | `ruff format` output only; syntax trees identical before and after (checked with `ast`); 127 tests pass |
| Dev dependency | `pre-commit>=4` in the dev extra | constraints.txt: `pre-commit==4.7.0` and its 8 dependencies added; all existing pins unchanged |
| CI | Valid; not yet run on GitHub | New lightweight `pre-commit` job (no Qt/VTK/POV-Ray). `test` job keeps Ubuntu 24.04 / Python 3.12 / Xvfb / POV-Ray 3.7 and adds `YCRYSTAL_REQUIRE_INTEGRATION=1`. Read-only permissions, superseded PR runs cancelled, timeouts, pip and hook caching; push trigger limited to `main` (PRs tested once). Actions moved to checkout v7, setup-python v7, cache v6 after the last `main` run warned that the Node 20 versions are deprecated. `actionlint` 1.7.12 and the GitHub-workflow schema: no problems |
| No silent skips | Pass | With `YCRYSTAL_REQUIRE_INTEGRATION=1`: no display → usage error (exit 4); no POV-Ray → 6 rendering tests error; everything present → 127 passed. Without it: 25 GUI tests / 6 rendering tests skip as before |
| Dependabot | Valid; not yet run | pip and github-actions, monthly, minor+patch grouped, majors separate, ≤ 3 open PRs each, Ruff ignored (owned by the hook). pip covers `pyproject.toml` and `constraints.txt` (Dependabot reads any requirements-style root `*.txt`; confirmed in dependabot-core and the docs). `increase-if-necessary` bumps exact pins without raising `pyproject.toml` lower bounds. Dependabot schema: valid |
| Constraints regeneration procedure | Pass | Documented commands rehearsed in a fresh system-Python venv: install, 127 tests in strict mode, freeze identical to the current pins |
| README badges | Added | CI status (main), MIT license, early development; all three URLs resolve. No pre-commit.ci badge: not activated (badge reports "unknown") |
| Contributor guidance | Added | `CONTRIBUTING.md`, `.github/pull_request_template.md` |

Owner setup still needed (configuration is committed, services are not activated):
enable pre-commit.ci for the repository, check Dependabot settings (version updates,
alerts, security updates), and optionally require the `pre-commit` and `tests` checks
on `main`. The new workflow, Dependabot, and pre-commit.ci have not run yet; local
success does not prove them.

### Update: private repository (15 November 2026)

The repository was made private. pre-commit.ci is free only for public repositories, so
its `ci:` section was removed from `.pre-commit-config.yaml`; hooks are now updated
manually with `pre-commit autoupdate` (CONTRIBUTING.md). The README's CI badge was
removed (it does not render for viewers without access); the static license and status
badges remain. GitHub Actions and Dependabot continue unchanged (private repositories
on GitHub Free have 2,000 Actions minutes per month; one CI run uses about 4). On
GitHub Free, the "Protect main" ruleset is not enforced while the repository is
private; it is kept for a return to public visibility. The entries above describe the
setup at the time.

## Documentation increment (15 November 2026)

No runtime behavior, public signatures, or product milestone status changed. The
user guide now supports M0–M2 features; this does not complete M6.

M2 was subsequently merged into main in PR #5 (`49b50ec`). This branch now includes
that merge and documents its repetitions, periodic bonds, cell modes, view directions,
and schema-2 projects. Historical checks below describe the initial increment;
updated integration verification is recorded separately.

### Audit of the interrupted work

- The working tree already contained substantial NumPy-style docstrings in 19 Python
  source files, a `docs` dependency extra and NumPy Ruff rules in `pyproject.toml`,
  and an untracked draft `zensical.toml`. Runtime syntax trees matched HEAD when
  documentation strings were removed. That work was preserved and refined.
- The draft site referred to pages that did not exist. There was no first-figure
  tutorial, architecture/writing guide, generated reference pages, visual asset,
  documentation CI job, or completed build evidence.
- No `AGENTS.md` was present in this checkout or its ancestor directories.
  `docs/IMPLEMENTATION_PLAN.md` was absent (and is ignored as a private planning
  file), so it could not be consulted. Actual source, tests, `FORMATS.md`, and this
  progress record supplied the implementation evidence.
- Existing pre-commit, Dependabot, badge, and application-test configuration was
  retained. CI was extended only with a docs job and display-independent examples.

### Delivered files

- Source docstrings: `app.py`, `__main__.py`; core structure, scene, camera, picking,
  samples, and comparison; I/O readers/projects; GUI window/commands; viewport;
  POV writer, discovery, jobs, process, self-test, and image checking.
- Site: `zensical.toml`, `docs/index.md`, five pages in `docs/guide/`, three in
  `docs/development/`, seven curated `docs/reference/` pages, and
  `docs/assets/perovskite.png` (actual 640 × 400 POV-Ray output, about 63 KB).
- Verification/reproduction: `docs/requirements.txt` (separate 25-package docs-only
  lock), `scripts/docs_examples.py`, `scripts/docs_render_example.py`.
- Integration: docs extra and scoped NumPy Ruff checks in `pyproject.toml`, a docs CI
  job and example check in `.github/workflows/ci.yml`, generated-output ignores,
  shorter `README.md`, contributor links, and the precise CIF occupancy tolerance in
  `FORMATS.md`. Main application constraints and existing hooks were not replaced.

### Verification actually performed

| Check | Result and evidence |
| --- | --- |
| Runtime unchanged | All 19 modified `src/` Python files have identical ASTs to HEAD after removing documentation strings; no public names/signatures changed |
| Application suite | `YCRYSTAL_REQUIRE_INTEGRATION=1 .venv/bin/python -m pytest -q -rs`: **127 passed, 0 skipped**, 306.09 s; real X11 Qt/VTK and `/usr/bin/povray`. The initial sandboxed run aborted because it could not access the display; the successful run had display access |
| NumPy examples | `python -m doctest` on structure, scene, camera, picking, readers, and project: **37 examples passed**; `python scripts/docs_examples.py`: passed, with temporary files cleaned up, no display or renderer |
| Genuine visual asset | `python scripts/docs_render_example.py`: rendered the tracked 640 × 400 SrTiO3 image with POV-Ray 3.7; inspected the image. Script owns job cleanup and supports an alternate output path |
| Tutorial rehearsal | Scripted real Qt events exercised orbit, pan, zoom, Fit, corner selection, Delete, undo, project save/reopen, POV export, and asynchronous GUI render. 5 scientific atoms / 15 displayed; hiding one gave 14; PNG **640 × 376** as the viewport required; coordinates unchanged; render job removed. Evidence under ignored `artifacts/docs/tutorial/`: project, POV/INI, PNG, window screenshot, `report.json` |
| Renderer diagnostic | `/usr/bin/povray` 3.7.0.10.unofficial passed; sphere centres within **0.14 px** |
| Static docs-only build | Fresh `/tmp/ycrystal-docs-env` with Zensical 0.1.1, mkdocstrings-python 2.0.11, and 23 transitive dependencies. Confirmed Qt, VTK, ASE, NumPy, and Ycrystal were not installed. `zensical build --clean --strict`: **no issues** |
| Broken-link controls | Temporarily added a missing page, missing anchor, unresolved API cross-reference, and nonexistent API directive, separately. Every strict build failed; restored the source afterward |
| Rendered reference | Inspected home and camera-reference HTML in headless Chrome; checked all 19 generated HTML pages: no broken local links/anchors or duplicate IDs. Confirmed constructor/method signatures and curated members, without inherited Qt/VTK methods |
| Preview | `zensical serve --dev-addr 127.0.0.1:8765`: home, tutorial, camera reference, and PNG returned HTTP 200; temporary server stopped afterward |
| Maintenance checks | Ruff lint, Ruff format, and `git diff --check` passed. Existing pre-commit hooks passed on tracked **and new** files, including image size, YAML, and Ruff pin sync. CI YAML parsed locally; GitHub execution remains unverified |

Preview and build from the checkout root:

```bash
.venv/bin/python -m pip install -e ".[docs]" -c constraints.txt -c docs/requirements.txt
.venv/bin/zensical serve
.venv/bin/zensical build --clean --strict
```

For the docs-only installation, exact commands and the dependency-update procedure,
see [Documentation workflow](development/documentation.md). The first-figure workflow
is in [the user guide](guide/first-figure.md).

### Discrepancies documented without changing behavior

- The previous progress wording and draft GUI docstring said rendering returned
  immediately. In fact `render_png` queries the renderer version synchronously (up
  to 15 s) and prepares files before starting `QProcess`. The render itself is
  asynchronous. The GUI's renderer check is synchronous.
- Frozen structure arrays do not make metadata immutable: the constructor retains
  the metadata dictionary, and `replace` shallow-copies it. `Project` is mutable.
- Direct `Structure` construction permits occupancy up to `1 + 1e-6`, does not reject
  non-finite coordinates/occupancies, and does not validate `pbc` length. The CIF
  reader rejects occupancy below `1 - 1e-3`, rather than every value below 1. These
  existing tolerances/validation limits are now explicit.
- The renderer self-test converts discovery/render failures to a result, but file
  preparation, image decoding, and measurement errors may propagate. A preparation
  failure after creating a job directory can leave partial files. GUI PNG-copy
  failures can leave a `.part` file; the GUI still removes the render job.
- Project metadata sanitization does not recursively sanitize values converted from
  NumPy; non-finite values can make saving fail. Optional scene/environment/output
  sections default on load; missing required structure entries fail. The old M1
  evidence wording “missing sections” was too broad and is clarified above.
- `core.compare.supercell` is a comparison helper and accepts non-singular integer
  transforms, including orientation reversal; it is not a GUI supercell feature.
  Structure comparison wraps fractional differences component by component, rather
  than performing a general minimum-image search in skewed cells.

### Still unverified / separate publication work

- No human hands-on usability session, fresh system-package installation, Wayland,
  other platforms, or POV-Ray 3.8 validation was performed in this increment. The
  GUI rehearsal used synthetic events through the actual widgets; rendering,
  structure/project output, and dimensions were checked.
- The new docs CI job has not run on GitHub. The site is not deployed. Hosting,
  canonical URL/base path, and deployed navigation/asset checks remain separate;
  [publication notes](development/documentation.md#publication) describe the steps.

## Integration with merged M2 (15 November 2026)

Fetched `origin/main` at `49b50ec` (M2 merged in PR #5) and merged it into
`docs/docstrings`. Resolved overlapping documentation/source files while preserving
M2 runtime code. Every `src/` syntax tree matches `origin/main` after stripping
string documentation. No application behavior or public signatures changed relative
to the merged M2 implementation.

Updated the user guide, first-figure labels, architecture, project-format guide,
curated references, and docstrings for display repetitions, cell-edge modes, periodic
bonds, view directions, undo merging, and schema-2 projects. Added NumPy docstrings
for the new bond models/search and scene-panel interfaces; no lint rules weakened.
The example script now checks 2 × 2 × 2 SrTiO3 (71 atoms, 192 bonds), and the tracked
640 × 400 image was regenerated with the current default bond display.

Verification on the integrated tree:

- Full strict application suite with X11/Qt/VTK and POV-Ray: **162 passed, 0 skipped**
  in 30.24 s (`/tmp/ycrystal-m2-docs-tests.log`).
- Clean strict docs-only build: no issues. Source doctests and
  `scripts/docs_examples.py`: passed. Asset regeneration: passed.
- First-figure rehearsal on the actual Qt/VTK widgets: passed selection, hide/undo,
  save/reopen, scene export, and PNG render (640 × 509 at the new dock layout).
  Renderer check: passed within 0.14 px. Outputs remain in `artifacts/docs/tutorial/`.
- Ruff and existing pre-commit checks: passed on the integrated tree.
- Earlier M2-separate-branch statements in the initial audit are historical;
  M0–M2 are now merged. M3 remains next; documentation hosting is still separate.

## Commands

```bash
# setup (system Python; see README for the reason)
uv venv --python /usr/bin/python3.12 .venv
VIRTUAL_ENV=$PWD/.venv uv pip install -e ".[dev]" -c constraints.txt

# launch
.venv/bin/ycrystal                      # or: --sample triclinic

# checks (POV-Ray found on PATH; override with --povray or $YCRYSTAL_POVRAY)
.venv/bin/ycrystal --check-renderer
.venv/bin/pre-commit run --all-files       # Ruff lint/format, file checks, Ruff sync
YCRYSTAL_REQUIRE_INTEGRATION=1 .venv/bin/python -m pytest -q -rs   # no silent skips
.venv/bin/python scripts/m0_evidence.py    # writes artifacts/m0/
.venv/bin/python scripts/render_thumbnails.py  # re-renders changed preset thumbnails
```

## Environment baseline (development machine)

- Linux Mint 22.1 (Xia), kernel 6.8.0-139, X11 Cinnamon session, 1920×1080 at 96 dpi.
- Intel Meteor Lake integrated graphics, Mesa 25.2.8, OpenGL 4.6.
- Python 3.12.3 (`/usr/bin/python3.12`), venv created with uv 0.8.3.
- Qt / PySide6-Essentials 6.12.0, VTK 9.7.2, PyVista 0.49.2, PyVistaQt 0.13.2,
  QtPy 2.4.3, ASE 3.29.0, NumPy 2.5.4, Pillow 13.0.0 (full pin list: `constraints.txt`).
- POV-Ray 3.7.0.10 (distribution package `1:3.7.0.10-3build4`, `/usr/bin/povray`),
  include files in `/usr/share/povray-3.7/include`.

Second development machine (since 16 November 2026):

- Mac mini, macOS 15.8 (Apple silicon), one external non-Retina display (2560 × 1440,
  scale 1.0).
- Python 3.12.16 and POV-Ray 3.7.0.10 from Homebrew (`/opt/homebrew/bin/povray`, include
  files in `/opt/homebrew/share/povray-3.7/include`); the same pins as above plus
  pyobjc-core and pyobjc-framework-Cocoa 13.0.

## Architecture decisions

- **System Python, not Miniconda.** With Miniconda's interpreter, its bundled
  `libstdc++` (GLIBCXX ≤ 3.4.29) is loaded before the system one, and Mesa 25 cannot
  initialise GLX: the VTK window crashed.
- **PySide6-Essentials only** (no Addons/WebEngine). `QT_API=pyside6` is forced
  before PyVistaQt/QtPy are imported.
- **Ycrystal's own POV-Ray writer from M0.** ASE's exporter frames the image itself
  and writes camera-frame coordinates, so it cannot reproduce an arbitrary panned,
  non-square view. ASE remains the structure library; its exporter is a reference only.
- **Camera export:** explicit `location`/`direction`/`right`/`up` vectors for an
  orthographic camera (no `look_at`, `sky` or `angle`), so POV-Ray does not re-derive
  the basis or change handedness. World coordinates stay right-handed in Å.
  `#version 3.7;`, no include files.
- **Colours:** written as sRGB through a small macro and converted to linear light
  (`assumed_gamma 1.0`, PNG `File_Gamma=sRGB`).
- **Shared geometry:** `core.scene.build_geometry` resolves atoms (stable IDs
  `(source_atom, image)`), radii, colours and cell edges once; the VTK viewport and the
  POV writer both consume it. Atoms are drawn with `vtkGlyph3DMapper` (instancing);
  cell edges are tubes with the same radius as the POV cylinders and cast no shadows.
- **Render jobs:** per-job temporary directory, ASCII names, POV-Ray run with
  cwd = job directory and every output option in the job `.ini` (user `povray.ini`
  defaults such as `Display=On` cannot interfere). The PNG is then copied to the
  user's path. GUI renders use `QProcess`.
- **Renderer discovery:** GUI setting → `$YCRYSTAL_POVRAY` → `povray` on `PATH`.
  `--check-renderer` / Render ▸ Check Renderer renders a tiny reference scene and
  verifies sphere positions and colours.
- **Output framing (M0, superseded in M3):** M0–M2 rendered the viewport's aspect ratio.
  Since M3 the output size is explicit and the GUI shows the output frame.
- **Keys:** VTK/PyVista default keys (e.g. `q` closes, `w` wireframe) are disabled in
  the viewport; application shortcuts (F = Fit, Ctrl+R = Render, Delete = hide,
  Esc = select none, Ctrl+Z / Ctrl+Shift+Z = undo/redo) live on the window.
- **Boundary policy:** along periodic axes atoms are wrapped into the cell (fractional
  tolerance 1e-3) and images on faces/edges/corners are added. A displayed atom's ID
  is `(source atom, image offset)` with position = input + offset @ cell, so IDs are
  stable when display settings change.
- **Hiding is presentation state:** `SceneSettings.hidden` holds displayed-atom IDs;
  hidden balls are absent from the shared geometry, hence from the view and POV
  export. The structure is never modified (atom deletion/editing remains a later,
  separate feature).
- **Picking** uses an analytic ray–sphere intersection with the shared camera model
  (`core/picking.py`), not VTK pickers; a click is a left press/release that moves at
  most 3 px. The selection highlight is a translucent shell drawn only in the live view.
- **Undo/redo:** `QUndoStack` with one command type that swaps `SceneSettings`;
  commands with the same merge key (bond tolerance, bond radius) merge when consecutive.
- **Supercells (M2):** repetitions live in `SceneSettings` and are always expanded from
  the original structure; boundary images are added on the faces of the repeated block.
  Image offsets stay relative to input positions, so IDs, selection, and hidden atoms
  are stable across repetition changes.
- **Bonds (M2):** `core/bonds.py` searches the original cell once with ASE's
  neighbour list (any cell shape) and stores `(i, j, integer shift)` without reverse
  duplicates; `build_geometry` maps them onto displayed images and gives both renderers
  explicit endpoint index pairs. Rule and per-pair overrides are in `BondSettings`.
- **Live-view level of detail (M2):** sphere/bond tessellation drops at 2,000 and 8,000
  displayed atoms; bonds use the same GPU instancing (`vtkGlyph3DMapper`) as atoms.
- **Scene panel (M2):** `gui/panels/scene_panel.py` emits requests only; the window turns
  them into undoable commands and syncs the panel with signals blocked.
- **Import (M1):** ASE parses; `io/readers.py` adds detection, provenance (path, name,
  format, SHA-256, size, time, reader version, block, element mapping), and checks.
  Questions (format, data block, element mapping) are exceptions that the GUI answers
  and retries, so the readers stay GUI-free. Ycrystal's QE reader is assembled from
  ASE's card parsers because ASE's `read_espresso_in` ignores `A` (it looks up an
  upper-case key in a lower-cased namelist) and resolves labels permissively.
- **Comparison:** `core/compare.py` compares lattice matrices directly and matches atoms
  by element and fractional position modulo lattice translations.
- **Projects:** `io/project.py`, JSON schema 2 (schema 1 remains readable), written atomically; numbers are
  canonical, symbols are stored for readability and checked on load. Machine-specific
  settings (POV-Ray path, last directory) stay in QSettings, not in projects.
- **Camera notifications:** the viewport now listens to the VTK camera's
  `ModifiedEvent`; the M0 observer on the interactor never fired because VTK raises
  `EndInteractionEvent` on the interactor style.

- **Output camera (M3):** the GUI keeps VTK's camera for the whole view and derives the
  output camera (same pose, parallel scale × frame/height ratio). Export, preview,
  render, and projects use the output camera with the explicit output size; a render
  start observer keeps it fixed across window resizes.
- **Presets (M3):** `ycrystal.presets` loads JSON manifests (declaration kind, finish,
  filter, interior, includes, live approximation, provenance) shipped as package data.
  Scenes store ids; the POV writer writes a `texture` or a full `material` per element;
  the viewport applies the live approximation. Background presets also set a visible
  cell-edge colour, changed together with the environment in one undo step.
- **Material assignment (M4):** `SceneSettings` stores a default material plus sorted
  element and displayed-atom overrides and element colours; `build_geometry` resolves
  one material and colour per atom. The POV writer declares each material once per
  element colour (once overall for own-pigment materials) and applies unit-space
  textures to a scaled unit sphere. The viewport draws one actor per material.
- **Environment model (M4):** `Environment` holds background (solid, gradient, sky),
  floor, lighting values, and the reflection panel; presets initialise it, the panel
  edits fields. Gradients and skies use a self-lit backdrop aligned with the frame
  (a `sky_sphere` would be one colour under orthographic projection) inside an empty
  `light_group`; the floor is tilted 20° towards the viewer; area lights have no jitter
  so renders are deterministic.
- **Lighting rig (FR-LIGHT-01):** lights are values relative to the output camera
  (origin F, screen basis) resolved on demand by `ycrystal.core.lighting`; the POV
  writer, the live view's two scene lights, and the Lighting Setup overview consume the
  same rig, and no resolved positions are stored.
- **Undo model (M5):** one command type carries scene settings plus optional
  environment and output size; handle drags, style imports, and size changes are single
  steps; merge keys combine spin-box edits. Camera navigation stays outside undo.
- **Styles (M5):** the presentation part of the project format plus the source's element
  sequence; a pure `apply_style` returns new settings and user notes.
- **Handles and axis rotation (M5):** the viewport's input filter routes handle drags and
  axis-mode drags away from VTK's trackball; handles are 2D overlays recomputed before
  each render; repetitions are applied once on release.
- **Thumbnails (M4):** genuine POV-Ray renders of fixed scenes, shipped as package data,
  with scene digests to detect stale images.
- **Render lifecycle (M3):** `RenderProcess` (progress, cancellation, elapsed time,
  completion state) and `RenderQueue` (one process, newest request wins, job directory
  removed after the result slots). The window tags previews with `scene_revision` and
  discards stale results; final renders use a separate process with Cancel.

## Next bounded action

Open: Windows CI with POV-Ray (Windows support itself: PR #35, `docs/development/windows-port.md`); the tests of `docs/development/next-tests.md`. FR-GALLERY-01 is merged (PR #34). FR-VALIDATION-01 is merged (PR #33); its runs on the Mac are still to do. FR-REPRO-01 is merged (PR #32). Merged features after
0.3.0 pass CI on Ubuntu and macOS. Remaining hands-on item from the macOS work: the checklist
in [HANDOFF.md](HANDOFF.md). Still
open from before: hands-on checks of the 0.2.0 features (Lighting Setup window, aspect
lock, colour dialog) by a person; the maintainer decides whether to publish a GitHub
release for `v0.2.0`.
