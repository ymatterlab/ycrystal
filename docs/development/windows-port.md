# Windows port: state and takeover

Windows support is **in progress** on branch `feature/windows` (draft pull request).
This page hands the work over to a real Windows computer. It records:

- what was decided, and what is known with sources;
- what is implemented and how it was tested;
- what can only be settled on Windows, as experiments to run;
- what remains before Windows can be called supported.

Nothing here claims that Ycrystal works on Windows. A claim needs the tests on Windows
listed at the end.

## Decision

Taken by the user on 17 November 2026: Ycrystal runs **natively on Windows**, and
renders with the official **POV-Ray for Windows 3.7** (`pvengine64.exe`).

The alternatives were set aside:
- **WSL2 only:** Ycrystal and Linux POV-Ray inside WSL2.
- **Hybrid:** native Ycrystal with `wsl povray` for rendering.

They remain possible later and are not implemented.

## What is known, and from where

| Fact | Source | Checked how |
| --- | --- | --- |
| There is no command-line POV-Ray for Windows from conda-forge | conda-forge `povray` has builds for linux-64, linux-aarch64, osx-64, osx-arm64 only | `api.anaconda.org/package/conda-forge/povray`, 17 Nov 2026 |
| There is no MSYS2 package of POV-Ray | packages.msys2.org search for "povray": no results | 17 Nov 2026 |
| GitHub releases of POV-Ray have Windows builds of 3.8 betas and alphas only, no 3.7 | `gh api repos/POV-Ray/povray/releases` | 17 Nov 2026 |
| POV-Ray for Windows is a window program; `/EXIT` makes it quit after the render given on its command line, `/RENDER FILE` renders a file, `/NR` (`/NORESTORE`) does not reopen the last session | POV-Ray 3.6 documentation, "Special Command-Line Options" | Search summary only. povray.org and its wiki refuse automated access (HTTP 403), so the 3.7 pages were **not read** |
| Official installer: `http://www.povray.org/redirect/www.povray.org/ftp/pub/povray/Official/povwin-3.7-agpl3-setup.exe`, SHA-256 `2B1331641B6F96113C2DBA951BE80D99EB548639480399CABB5E3A60DCE5BDC8`, silent with `/S`, installs into `%ProgramFiles%\POV-Ray\v3.7`, executable `bin\pvengine64.exe`; the package writes the registry value `Software\POV-Ray\v3.7\Windows\Home` | The Chocolatey package `pov-ray` 3.7.0.20161121 (its install script) | Read on community.chocolatey.org. The CI job uses this URL and checksum |
| The installer installs for the installing user only | Same Chocolatey page, note | Not checked |

## What is implemented on `feature/windows`

Linux and macOS behaviour is unchanged: `povray` gets exactly the arguments it got
before, and every existing test passes on Linux.

- **`src/ycrystal/render/povray.py`** (the place for renderer platform checks):
  - `is_windows_engine()` recognises `pvengine*.exe` by name.
  - `windows_engine_candidates()` lists install folders from the registry `Home`
    values and the `ProgramFiles` variables, using the layout `POV-Ray\v3.7\bin`.
  - `installed_windows_engine(platform)` searches `PATH` for `pvengine64.exe`, then
    those folders. Windows only; it takes `platform` so that it can be tested
    anywhere.
  - `find_povray()` falls back to `installed_windows_engine()` after `povray` on
    `PATH`. `INSTALL_HINT` names POV-Ray for Windows.
  - `render_arguments()` returns `["scene.ini"]` for `povray`, and
    `["/EXIT", "/NR", "+GAscene.log", "scene.ini"]` for POV-Ray for Windows. `+GA`
    asks POV-Ray to write all messages to `scene.log`, because it prints nothing.
  - `read_log()` reads that file.
  - `background_startupinfo()` starts the window minimised without taking the focus
    (`SW_SHOWMINNOACTIVE`), on Windows only.
  - `povray_version()` never starts POV-Ray for Windows (it has no `--version`; it
    would open its window). It reads the version resource of the file instead
    (`windows_file_version()`, through ctypes).
  - `include_directories()` also looks in the installation's `include` folder, its
    `ini\povray.ini`, and `Documents\POV-Ray\v3.7`.
- **`src/ycrystal/render/jobs.py`:**
  - `RenderJob.arguments(executable)` uses `render_arguments()`.
  - `run_job()` starts POV-Ray minimised on Windows and appends the log file to the
    result's log, so failures are explained from it.
- **`src/ycrystal/render/process.py`** (the window's previews and renders): the same
  arguments and log. It does not minimise the POV-Ray window: QProcess has no simple
  way to pass `STARTUPINFO`.
- **Tests:**
  - `tests/conftest.py::python_program()` makes the stand-in programs of the tests
    work on every system: a shell launcher on Linux and macOS, a `.cmd` launcher on
    Windows. The shell-script fakes of `test_povray_jobs.py`, `test_render_queue.py`,
    and `test_batch_manifest.py` now use it.
  - The execute-bit test is skipped on Windows, which has no such bit.
  - `tests/test_windows_povray.py` (10 tests) checks the Windows contract on any
    system. A stand-in "POV-Ray for Windows" prints nothing, writes its log, and exits
    0. The tests check:
    - the arguments it receives;
    - that the log reaches successful and failed results;
    - that the version query never starts it;
    - the folder search and the include files of its layout.

    One test runs only on Windows, against the installed program.
- **`.gitattributes`:** text files keep LF line endings in Windows checkouts. Several
  tests compare SHA-256 digests of tracked files. Nothing changes on Linux and macOS,
  where every text file is LF already.
- **`scripts/make_examples.py`** writes LF on every system, so its output is the same
  bytes everywhere.
- **`scripts/windows_povray_probe.py`** (new) reports how POV-Ray for Windows behaves
  under Ycrystal: what is found, its version, include folders, and real renders with
  Ycrystal's command line and one alternative.
- **CI** (`.github/workflows/ci.yml`): a third test job, **experimental**
  (`continue-on-error`). It runs on Windows Server 2022 with Python 3.12, installs
  POV-Ray for Windows silently from the official installer (checksum checked), runs
  the probe, then the renderer check and the tests without windows.

## Evidence from the Windows CI job

Two runs of the experimental job on draft PR #35, 17 November 2026, Windows Server
2022, Python 3.12. The Ubuntu and macOS jobs passed in both runs, so the port changes
nothing there.

| Run | Result |
| --- | --- |
| 1 (`3741931`) | Failed after 13 s at the installer download. povray.org answered the GitHub runner with a **Cloudflare browser challenge** ("Just a moment… Enable JavaScript and cookies to continue") instead of the installer. The official installer, and the Chocolatey package that fetches the same URL, **cannot be installed automatically on CI**. Nothing after that step ran |
| 2 (`9d2c4d1`) | The job now continues without POV-Ray. The installer download failed again, as expected, and the probe was skipped. **Ycrystal installed with the pinned dependencies**, and `ycrystal --version` printed `ycrystal 0.4.0.dev0`. **All doctests and `scripts/docs_examples.py` passed. Tests: 621 passed, 98 skipped, none failed** (GUI tests deselected) |

The 98 skipped tests:
- 95 need a working POV-Ray: presets, validation, release examples, render
  alignment, reproducibility, background pictures, gallery, and others;
- 1 needs an installed POV-Ray for Windows;
- 2 are POSIX-only by design: the execute-bit check and the unwritable-folder test.

What passed on Windows includes:
- structure reading and projects, styles, element mapping, cameras, batch manifests,
  snapshots and provenance;
- the benchmark and replay-check scripts with stand-in renderers (`.cmd` launchers),
  the benchmark without peak memory, since `wait4` does not exist on Windows;
- the 9 Windows contract tests, with a stand-in POV-Ray for Windows.

**Not yet seen on Windows:** a real POV-Ray for Windows render, and the window.

### Decision needed: POV-Ray for Windows on CI

The CI runner cannot download the installer, so real Windows renders in CI need one of
these:

| Option | For | Against |
| --- | --- | --- |
| a. Keep the official installer (SHA-256 above) as a release asset of this repository, and download it from there in CI | Real POV-Ray 3.7 renders on every pull request | Redistributes an AGPL-3.0 binary: check the licence obligations (the corresponding source is POV-Ray's public repository) before the repository or the asset becomes public |
| b. A self-hosted Windows runner with POV-Ray installed by hand | Real renders, the real program, no redistribution | A machine to keep online |
| c. POV-Ray's 3.8 beta installer from its GitHub releases (downloadable) | Automatic | Not 3.7: the tests, the documentation, and the users' version all assume 3.7 |
| d. No POV-Ray on Windows CI; test rendering by hand on a Windows computer | Nothing to decide now | Rendering on Windows is only as tested as the last hand run |

Suggested: **d** while the port is completed by hand, then **a** or **b** once Windows
is a supported target. The experimental job already runs everything else.

## Experiments for the real Windows computer

Everything but rendering and the window already passed on a Windows CI runner (see
above), so the work on a real computer is about POV-Ray for Windows and the GUI. Set
up once, in PowerShell, from a clone of the repository on branch `feature/windows`:

```powershell
py -3.12 -m venv .venv
.venv\Scripts\python -m pip install -e ".[dev]" -c constraints.txt
# Install POV-Ray for Windows 3.7 from povray.org (the normal installer),
# then start it once from the Start menu and close it (first-start dialogs).
.venv\Scripts\python scripts\windows_povray_probe.py
.venv\Scripts\ycrystal --check-renderer
```

Then settle these questions, in this order. Record the answers in this page, and in
the code where they change it.

| # | Question | How to check | If the answer is no |
| --- | --- | --- | --- |
| 1 | Does `pvengine64.exe /EXIT /NR +GAscene.log scene.ini` render `scene.png` and quit? | Probe, candidate `ycrystal` | Try the probe's `render-switch` line (`/RENDER scene.ini`); change `render_arguments()` to what works |
| 2 | Is the exit status 0 after a successful render, and non-zero after a parse error? | Probe; then a scene with an error | If always 0, `finish_job()` already relies on `scene.png`; nothing to do. If non-zero on success, accept success when the image exists |
| 3 | Does `scene.log` appear with POV-Ray's messages (including "Parse Error")? | Probe output `scene.log:` | Look for POV-Ray's own message file option in its INI documentation; error messages otherwise say only that no image was made |
| 4 | Does a dialog appear on the first start, for a newer version, or for file access? | Probe with a fresh user profile; watch the screen | Document the one-time answer; consider `/NR` alternatives; I/O restrictions are set in POV-Ray's options |
| 5 | Does the window stay minimised and not take the focus (`SW_SHOWMINNOACTIVE`)? | Run `ycrystal FILE --render out.png` and watch | If it appears anyway, document it; it does not change the result |
| 6 | If POV-Ray for Windows is already open, does a second render start a new instance, or hand over to the open one and return at once? | Open POV-Ray by hand, then render from Ycrystal | If it hands over, Ycrystal sees no image: document "close POV-Ray" or look for a switch for a new instance |
| 7 | Where are the include files (`Program Files\POV-Ray\v3.7\include` or `Documents\POV-Ray\v3.7\include`), and does `missing_includes()` find `metals.inc`? | Probe lines "include directories", "missing include files" | Add the folder to `_windows_user_folders()` |
| 8 | Does `povray_version()` read a version, and does it start with `3.7`? | Probe line "version" | Read the product version string, or the version printed in `scene.log` |
| 9 | Does the window (`ycrystal --sample perovskite`) open, draw, and render previews (F5)? | By hand; then `pytest -m gui` | Qt/VTK on Windows; see `gui/native.py` for the platform choices already made |
| 10 | Do all tests pass? | `.venv\Scripts\python -m pytest -q -rs` (with windows), and with `YCRYSTAL_REQUIRE_INTEGRATION=1` | Fix per test, keeping Linux and macOS green |

## What remains before "Windows is supported"

1. **CI.** Decide how CI gets POV-Ray for Windows (see the decision above). Once
   the job passes with real renders, remove `experimental: true` from its matrix
   entry and the `continue-on-error` of its install and documentation-example steps,
   so that failures count.
2. **Questions above.** Answer questions 1–10 on a real computer, and change the code
   where an answer requires it.
3. **The window.** Go through the hands-on checklist of HANDOFF.md, adapted: Ctrl
   instead of ⌘, File Explorer dialogs, high-DPI scaling. Decide whether the POV-Ray
   window appearing during previews (QProcess) is acceptable.
4. **Documentation**, then:
   - a Windows section in `docs/guide/install.md` (Python from python.org, POV-Ray for
     Windows, `.venv\Scripts\…`);
   - `docs/guide/support.md` and `docs/guide/troubleshooting.md` (POV-Ray window,
     first-start dialogs, I/O restrictions);
   - `README.md`;
   - the platform table and decisions in `docs/HANDOFF.md`;
   - the target line in `CLAUDE.md` ("Keep Windows feasible; it is not verified"),
     with the user's agreement;
   - `docs/PROGRESS.md` with the evidence.
5. **Out of scope until decided:**
   - an installer or launcher (there is no Start-menu entry; `--install-desktop` is
     Linux only);
   - `.ycrystal` file association;
   - Windows on ARM;
   - progress percentages during renders on Windows: POV-Ray for Windows prints
     none, so the window cannot show how far a render has got. What the progress
     display does instead is unchecked.
