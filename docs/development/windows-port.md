# Windows port

Windows support was developed on branch `feature/windows` (PR #35): the groundwork on
the Linux laptop and Windows CI (17 November 2026), the completion on a Windows 11
laptop (18 November 2026). This page records:

- what was decided, and what is known with sources;
- what is implemented and how it was tested;
- the answers found on the Windows computer;
- what is still open.

**Status (18 November 2026):** Ycrystal runs from a source checkout on Windows 11 with
POV-Ray for Windows 3.7. On one laptop it passes every automated test (below), and the
user tested it by hand there and reports that it works well. Windows CI runs without
POV-Ray (see [the CI decision](#decision-needed-pov-ray-for-windows-on-ci)).

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
| Official installer: `povwin-3.7-agpl3-setup.exe`, SHA-256 `2B1331641B6F96113C2DBA951BE80D99EB548639480399CABB5E3A60DCE5BDC8`, silent with `/S`, installs into `%ProgramFiles%\POV-Ray\v3.7`, executable `bin\pvengine64.exe` | The Chocolatey package `pov-ray` 3.7.0.20161121 (its install script) | Read on community.chocolatey.org. The CI job uses this URL and checksum |
| The installer records `Home` (installation folder) and `DocPath` (user files: `Documents\POV-Ray\v3.7`, with `include` and `ini`) under `HKEY_CURRENT_USER\Software\POV-Ray\v3.7\Windows` | The registry of the Windows computer | Read 18 Nov 2026 |
| Command-line switches of POV-Ray for Windows 3.7: `/EXIT` (quit after the render), `/NR` or `/NORESTORE`, `/RENDER FILE`, `/EDIT FILE`, `/NOEXEC`, `/THREADS N`, `/DEBUG`, `/DEMO`, `/BENCHMARK`; anything else after a `/` is an error dialog. Other arguments (an INI file, `+GA…`) are ordinary POV-Ray options | Its source, `windows/pvtext.cpp` (`preparse_commandline`), branch `3.7-stable` of github.com/POV-Ray/povray | Read 18 Nov 2026 (povray.org refuses automated access, HTTP 403) |
| **Keep Single Instance** is on by default: `[General] OneInstance` in `DocPath\ini\pvengine.ini`, default 1. When a main window of class `Pov37-Win64-MainWinClass` (64-bit build) exists, a new copy brings it forward, shows a one-time notice (`[DontShowAgain] OneInstanceSet`), and passes only `/EDIT` and `/RENDER` to it; with `/EXIT` it shows the modal error box "Only /EDIT and /RENDER may be passed to previous instance" and exits with status 1 | Source: `windows/pvengine.cpp` (`WinMain`), `windows/pvtext.cpp` (`preparse_instance_commandline`), `windows/pvmisc.cpp` (`GetHKCU` reads `pvengine.ini`) | Read 18 Nov 2026, and observed on the Windows computer (experiment 6 below) |
| With `/EXIT`, POV-Ray for Windows closes its window as soon as the render stops, **before** it plays the completion or error sound and before its first-time notices (render-complete sound, output file location) | Source: `windows/pvengine.cpp` (`render_stopped`) | Read 18 Nov 2026 |
| Command-line renders start directly, not through POV-Ray's file queue, so the `[Info] Rendering=1` flag that a killed render leaves behind does not make the next one skipped | Source: `windows/pvengine.cpp` (`WinMain`, the queue code that checks `Rendering`) | Read 18 Nov 2026 |

## What is implemented on `feature/windows`

Linux and macOS behaviour is unchanged: `povray` gets exactly the arguments it got
before and still runs as a `QProcess`; every existing test passes on Linux.

- **`src/ycrystal/render/povray.py`** (the place for renderer platform checks):
  - `is_windows_engine()` recognises `pvengine*.exe` by name.
  - `windows_engine_candidates()` and `installed_windows_engine(platform)` find POV-Ray
    for Windows from the registry `Home` values and the `ProgramFiles` folders (it is not
    on `PATH`); `find_povray()` falls back to it after `povray` on `PATH`.
  - `render_arguments()`: `["scene.ini"]` for `povray`; `["/EXIT", "/NR",
    "+GAscene.log", "scene.ini"]` for POV-Ray for Windows, which prints nothing and
    writes all messages to `scene.log` (`read_log()`).
  - `background_startupinfo()` starts it minimised (`SW_SHOWMINNOACTIVE`).
  - `hold_foreground()` / `release_foreground()` / `foreground_held()`: POV-Ray for
    Windows makes itself the foreground window even when started minimised or hidden.
    While it runs, Ycrystal calls `LockSetForegroundWindow`, which Windows allows only
    to the owner of the foreground window, so it works in the window and is refused
    harmlessly in a terminal. Holds are counted; every hold asks for the lock again.
  - `windows_engine_conflict()`: the same test POV-Ray makes at start-up (a window of
    its main class exists, and `OneInstance` is not 0 in its `pvengine.ini`), so that
    Ycrystal reports `ENGINE_OPEN_MESSAGE` instead of starting a copy that would show
    POV-Ray's modal error box and wait. `keeps_single_instance()` reads the setting as
    `GetPrivateProfileInt` does.
  - `include_directories()` also reads the user-files folder recorded in the registry
    (`DocPath`; right also when Documents was moved, for example into OneDrive), then
    `Documents\POV-Ray\v3.7` in the home folder.
  - `povray_version()` never starts POV-Ray for Windows (no `--version`; it would open
    its window); it reads the executable's version resource.
- **`src/ycrystal/render/jobs.py`:** `run_job()` reports a conflict without starting
  POV-Ray, holds the foreground while it runs, starts it minimised, and appends its log.
- **`src/ycrystal/render/process.py`** (the window's previews, final renders, and
  material thumbnails): PySide6 6.12 has no `QProcess.setCreateProcessArgumentsModifier`,
  so `QProcess` cannot start a program minimised. POV-Ray for Windows therefore runs as
  a `subprocess.Popen`, checked every 100 ms by a `QTimer`. Since only one copy can
  render, the program's own runs take turns (a render started while another runs
  waits, and counts as running); whether one runs is decided by the process itself, and
  a waiting render checks for its turn on its own timer, so a render whose Qt object was
  deleted cannot hold up the others. Cancelling kills POV-Ray and reports at once. It
  reports no progress (POV-Ray for Windows prints none): the window shows a busy
  indicator, then 100 %.
- **`src/ycrystal/gui/native.py`:** `set_taskbar_identity()` (an explicit
  AppUserModelID, so that the window has its own taskbar button and icon, not Python's;
  called from `app.py` before the application object) and `executable_filter()`
  (*Render ▸ Set POV-Ray Executable…* lists `.exe` files on Windows). That dialog now
  starts at the POV-Ray Ycrystal would use, not at `povray` on `PATH`.
- **Tests:**
  - `tests/conftest.py`: `python_program()` makes stand-in programs work everywhere (a
    `.cmd` launcher on Windows); the `povray_executable` fixture also finds an installed
    POV-Ray for Windows.
  - `tests/test_windows_povray.py` checks the Windows contract on any system with
    stand-ins: arguments, log, version query, folder search and the recorded user
    folder, the `Popen` backend (success, failure, cancel, failure to start, preview
    superseding, renders taking turns, a deleted render not holding up the next), the
    foreground holds, the single-instance setting, and the conflict check. One test runs
    only on Windows, against the installed program.
  - Tests that simulate "no POV-Ray" by emptying `PATH` also hide an installed POV-Ray
    for Windows. A test that renders an exported scene by hand uses
    `render_arguments()` (with `povray` unchanged: `povray scene.ini`).
  - `tests/test_preview_resolution.py` compares scene files with the header's time
    aside (a minute could pass between two states: a flake on every system, seen first
    on Windows, where each preview takes longer).
- **`.gitattributes`:** text files keep LF line endings in Windows checkouts. Several
  tests compare SHA-256 digests of tracked files.
- **`scripts/make_examples.py`** writes LF on every system.
- **`scripts/windows_povray_probe.py`** reports how POV-Ray for Windows behaves under
  Ycrystal; it also prints the settings file and the single-instance setting and stops
  when another copy is open.
- **CI** (`.github/workflows/ci.yml`): a third, **experimental** test job
  (`continue-on-error`) on Windows Server 2022 with Python 3.12; see below.
- **Documentation:** a Windows section in the install guide and the README, rows in the
  support matrix and troubleshooting, the architecture page, and the changelog.

## Evidence

### Windows CI (17 November 2026, from the Linux laptop)

| Run | Result |
| --- | --- |
| 1 (`3741931`) | Failed after 13 s at the installer download: povray.org answered the GitHub runner with a **Cloudflare browser challenge** instead of the installer. The official installer, and the Chocolatey package that fetches the same URL, **cannot be installed automatically on CI** |
| 2 (`9d2c4d1`) | The job continues without POV-Ray. **Ycrystal installed with the pinned dependencies**; doctests and `scripts/docs_examples.py` passed; **tests: 621 passed, 98 skipped, none failed** (GUI tests deselected) |

### The Windows computer (18 November 2026)

A laptop with Windows 11 Enterprise (build 26300), x64, a 1536 × 864 logical display at
**125 % scale** (device pixel ratio 1.25), and a UTF-8 system code page (65001). Python
3.12.10 from python.org (installed with `winget`, per user), PySide6 6.12.0, VTK 9.7.2.
POV-Ray for Windows 3.7.0 (file version 3.7.0.0, `VersionNo64=3.7.0.msvc10.win64`),
installed by the user with the official installer, user files included.

| Check | Result |
| --- | --- |
| Install: `py -3.12 -m venv .venv`, `.venv\Scripts\python.exe -m pip install -e ".[dev]" -c constraints.txt` | Installed |
| `scripts/windows_povray_probe.py` | Found `C:\Program Files\POV-Ray\v3.7\bin\pvengine64.exe` (not on `PATH`), version 3.7.0.0, include folder `Documents\POV-Ray\v3.7\include`, no include file missing. First start: no image within 90 s (see question 4); then both command lines rendered |
| Small render (120 × 80) timing, 7 timed runs | 2.3–2.8 s each after the first start (POV-Ray's start-up dominates); the second start of all took 28 s |
| Tests without windows, real POV-Ray for Windows, before the changes of 18 November | 715 passed, 3 skipped (symbolic links unavailable, execute bit, POSIX permissions), 1 failed: the test that ran `pvengine64.exe scene.ini` without `/EXIT` waited 120 s (fixed in the test) |
| GUI tests, first run | 160 passed, 12 failed: one test unexpectedly started a real render (an installed POV-Ray for Windows is found outside `PATH`), its window closed, and the `Popen` backend's "running" marker stayed set, so every later render waited for ever. Fixed (cancel reports at once; the process decides whether one runs) and covered by a new test |
| Full suite after the fixes, `YCRYSTAL_REQUIRE_INTEGRATION=1 pytest -q -rs` | 898 passed, 3 skipped (see [the result](#full-suite) below) |

#### Full suite

| Check | Result |
| --- | --- |
| `YCRYSTAL_REQUIRE_INTEGRATION=1 pytest -q -rs` (GUI tests with real windows at 125 % scale, all POV-Ray tests with POV-Ray for Windows) | **898 passed, 3 skipped, none failed**, 12 min. Skipped by design: symbolic links (need a Windows privilege), the execute bit, POSIX permissions |
| CI's doctest module list and `scripts/docs_examples.py` | Passed |
| `pre-commit run --all-files`; `zensical build --clean --strict` (in `.venv-docs`) | Passed; built without issues |
| `.venv\Scripts\ycrystal.exe --version`; `--check-renderer`; `examples\SrTiO3-studio.ycrystal --render "…\SrTiO3 studio.png"`; `--export-pov` | `ycrystal 0.4.0.dev0`; `PASS: POV-Ray 3.7.0.0 … sphere centres within 0.14 px`; rendered in 4.7 s; exported (into an existing folder; a missing folder is refused, as documented) |
| The rendering guide's command for an exported scene, `Start-Process -Wait "…\pvengine64.exe" "/EXIT /NR SrTiO3.ini"` | Renders `SrTiO3.png`. PowerShell's call operator `&` returns at once instead (POV-Ray for Windows is a window program), hence `-Wait` |
| Scripted run of the real window (as `.venv\Scripts\ycrystal.exe --sample perovskite`): screen capture, 3 previews, 1 final render, foreground watched every 10 ms | Draws correctly at device pixel ratio 1.25 (structure, output frame, a/b/c handles, axes, preview dock; Qt follows the Windows dark theme); previews ready in 2.6–2.7 s each; the final render saved; **the foreground never left the Ycrystal window**; AppUserModelID `YMatterLab.Ycrystal` set |

### Answers to the questions of the takeover

| # | Question | Answer (18 November 2026) |
| --- | --- | --- |
| 1 | Does `pvengine64.exe /EXIT /NR +GAscene.log scene.ini` render `scene.png` and quit? | **Yes**, in 2.3–2.8 s for a small scene. `/EXIT /NR /RENDER scene.ini +GAscene.log` behaves the same; the command line is kept |
| 2 | Exit status after success and after a parse error? | **0 in both cases.** After a parse error there is no image, and `finish_job()` already treats "status 0, no image" as a failure, explained from the log |
| 3 | Does `scene.log` hold POV-Ray's messages, including "Parse Error"? | **Yes** (options, warnings, statistics, and the parse error with file and line). No progress lines |
| 4 | Does a dialog appear on the first start? | The very first render after installation produced no image within 90 s and was killed; the next start took 28 s, all later ones under 3 s. The dialog itself was not seen by the session. POV-Ray's settings file now holds `[DontShowAgain] OneInstanceSet=1`: the one-time *Keep Single Instance* notice, which it shows when another copy is open, so a POV-Ray window the user had open is the likely cause. The completion-sound and output-file notices never appear with `/EXIT` (source). No later render of the session (several full test runs) waited for a dialog |
| 5 | Does the window stay minimised and not take the focus? | **Minimised: yes** (watched in every state, "Starting" to "Done"). **Focus: no** — it makes itself the foreground window even when started minimised or hidden (`SW_HIDE`). A Qt window in the foreground that starts it took the foreground away 2 times in 2 trials without `LockSetForegroundWindow`, and 0 times with it (1 trial; in a second one the window had not got the foreground first, and Windows refused the lock, as documented). Implemented for the window; a terminal cannot do it, so `--render` loses the terminal's focus while POV-Ray runs. `SW_HIDE` would also keep its taskbar button away; minimised was kept, so that a POV-Ray dialog stays reachable |
| 6 | With POV-Ray for Windows already open, does a second render start a new copy? | **No.** It shows the modal "Commandline processing error" box and waits (killed after 15 s; no image). With the new check, `.venv\Scripts\python.exe -m ycrystal --check-renderer` fails in 0.7 s with the explanation, and nothing appears. Ycrystal's own renders now take turns |
| 7 | Where are the include files, and are they found? | `Documents\POV-Ray\v3.7\include` (the installation folder has none). Found; `metals.inc` and the others present. The folder is also read from the registry (`DocPath`) |
| 8 | Does `povray_version()` read a version starting with 3.7? | **Yes**: `3.7.0.0` from the file version resource |
| 9 | Does the window open, draw, and render previews? | **Yes, in scripted runs:** the 172 GUI tests open real windows at 125 % scale and pass, and a scripted run of the main window drew correctly and rendered previews without losing the focus (see [the result](#full-suite)). Not yet checked by hand |
| 10 | Do all tests pass? | **Yes:** 898 passed, 3 skipped by design, with `YCRYSTAL_REQUIRE_INTEGRATION=1` ([full suite](#full-suite)) |

Further observations:

- Job folders whose path contains `ñ`, `ü`, or `晶体 Ω` render, but this computer's
  system code page is UTF-8. Whether POV-Ray for Windows (an ANSI program) renders in a
  `%TEMP%` with characters outside a legacy code page (for example Chinese characters
  in a user name on a Western-European Windows) is **unverified**.
- A clone made from `main` before `.gitattributes` existed keeps CRLF files after a
  switch to this branch; tests that hash tracked files would fail (see HANDOFF.md).

### Decision needed: POV-Ray for Windows on CI

The CI runner cannot download the installer, so real Windows renders in CI need one of
these:

| Option | For | Against |
| --- | --- | --- |
| a. Keep the official installer (SHA-256 above) as a release asset of this repository, and download it from there in CI | Real POV-Ray 3.7 renders on every pull request | Redistributes an AGPL-3.0 binary: check the licence obligations (the corresponding source is POV-Ray's public repository) before the repository or the asset becomes public |
| b. A self-hosted Windows runner with POV-Ray installed by hand | Real renders, the real program, no redistribution | A machine to keep online |
| c. POV-Ray's 3.8 beta installer from its GitHub releases (downloadable) | Automatic | Not 3.7: the tests, the documentation, and the users' version all assume 3.7 |
| d. No POV-Ray on Windows CI; test rendering by hand on a Windows computer | Nothing to decide now | Rendering on Windows is only as tested as the last hand run |

Suggested: **d** for now (the hand run of 18 November 2026 is recorded above), then
**a** or **b** once Windows is a supported target.

## Still open

1. **Hands-on use.** The user tested Ycrystal by hand on the Windows laptop on
   18 November 2026 and reports that it works well; which items were tried was not
   recorded. On another Windows computer, a fuller check can follow the macOS
   checklist in HANDOFF.md, adapted: the window draws sharply at the display's scale;
   mouse and touchpad; selection; menus and Ctrl shortcuts; File Explorer dialogs;
   *Set POV-Ray Executable…* and *Check Renderer*; previews with **Update
   automatically** (the POV-Ray taskbar button, the keyboard focus staying in
   Ycrystal); a long render cancelled; closing the window during a render; a project
   saved on Linux or macOS renders the same on Windows and back; whether POV-Ray plays
   a sound (none expected with `/EXIT`).
2. **CI.** Decide how CI gets POV-Ray for Windows (above). Once the job passes with
   real renders, remove `experimental: true` from its matrix entry and the
   `continue-on-error` of its install and documentation-example steps.
3. **Out of scope until decided:**
   - an installer or launcher (there is no Start-menu entry; `--install-desktop` is
     Linux only), and `.ycrystal` file association;
   - Windows on ARM; Windows 10;
   - progress percentages during renders with POV-Ray for Windows. It prints none, but
     its window title carries them (`POV-Ray for Windows [Rendering scene.pov: 37%]`),
     which a later change could read;
   - an option to start POV-Ray hidden (`SW_HIDE`) instead of minimised.
