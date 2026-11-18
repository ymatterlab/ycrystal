# Windows installer

The graphical Windows installer, `Ycrystal-<version>-windows-x64-setup.exe`, installs
Ycrystal without Python, Git, or PowerShell. It is the recommended installation for
users ([install guide](../guide/install.md#windows)). The PowerShell installation
from a source folder (`scripts/install-windows.ps1`) stays the supported installation
for developers. The two can be installed on one computer at the same time.

Requested by the user on 18 November 2026; branch `feature/windows-installer`.

## How it is built

| Step | Tool | Files |
| --- | --- | --- |
| Freeze Ycrystal with its Python and libraries into one folder | PyInstaller 6 | `packaging/windows/ycrystal.spec`, `ycrystal_gui.py`, `ycrystal_cli.py` |
| Wrap the folder into a setup program | Inno Setup 6 | `packaging/windows/ycrystal.iss` |
| Both, from a clean build environment | PowerShell | `packaging/windows/build.ps1`, build tools pinned in `packaging/windows/requirements.txt` |
| Check both installations side by side | PowerShell | `packaging/windows/coexistence-check.ps1` |
| On pull requests that change the program or its packaging | GitHub Actions | `.github/workflows/windows-installer.yml` |

To build on a Windows computer, from the repository:

```powershell
winget install --id JRSoftware.InnoSetup --exact      # once
powershell -ExecutionPolicy Bypass -File packaging\windows\build.ps1
```

The build:
1. creates `build\windows\venv` with Python 3.12 (`py -3.12`, or `-Python`), Ycrystal
   installed from the folder (not editable) with the pins of `constraints.txt`, and
   PyInstaller;
2. draws `build\windows\ycrystal.ico` from the SVG icon with
   `ycrystal.desktop.write_windows_icon`, as the developer installation does;
3. runs PyInstaller, then checks that `ycrystal-cli.exe --version` reports the version;
4. compiles the installer into `dist\windows`.

`build\` and `dist\` are ignored by Git. Nothing outside them is written, and the
developer installation (`.venv`, its Start-menu entry) is not touched.

The packaged folder holds two programs that share one copy of Python and the libraries:

- `Ycrystal.exe`, the window, without a console. The Start menu and `.ycrystal` files
  start it. VTK's own window for warnings is turned off (`ycrystal_gui.py`).
- `ycrystal-cli.exe`, the command line with a console, for `--render`,
  `--check-renderer`, and `--batch`. Without options it opens the window too.

Both run the same `ycrystal.app.main` as the `ycrystal` command of an installation from
source; there is no packaged-only code path apart from the application id and the
refusal of `--install-desktop` (below).

## Coexistence with the developer installation

The two installations must not share any identity. Then neither can redirect, replace,
or remove the other's parts:

| | Packaged (installer) | From source (`--install-desktop`) |
| --- | --- | --- |
| Start-menu shortcut | `Ycrystal.lnk` → `<app>\Ycrystal.exe`, written by Inno Setup | `Ycrystal (development).lnk` → `.venv\Scripts\pythonw.exe -I -m ycrystal.app` |
| AppUserModelID (taskbar, pinning) | `YMatterLab.Ycrystal.App` (`WINDOWS_PACKAGED_APP_ID`) | `YMatterLab.Ycrystal` (`WINDOWS_APP_ID`) |
| How the window picks its id | `windows_app_id()`: `sys.frozen` is set by PyInstaller | the same function, `sys.frozen` unset |
| File type (ProgID) | `YMatterLab.Ycrystal.Project` | `Ycrystal.Project` |
| Default of `.ycrystal` | set by the installer | set only if no other existing file type is the default |
| Icon | inside `Ycrystal.exe` | `%LOCALAPPDATA%\Y-Matter Lab\Ycrystal\ycrystal.ico` |
| Registry root | `HKEY_CURRENT_USER` (per user) or `HKEY_LOCAL_MACHINE` (all users) | `HKEY_CURRENT_USER` |
| Removed by | its uninstaller: only its own files, shortcuts, and values; the `.ycrystal` default only while it names its file type | `--uninstall-desktop`: shortcuts only if they start Python with `-m ycrystal.app` (`is_source_shortcut`), its own file type, its own default |

Shared on purpose, and never deleted by either uninstallation: the settings
(`HKEY_CURRENT_USER\Software\Y-Matter Lab\Ycrystal`), personal materials and their
thumbnails, and POV-Ray for Windows.

Rules for later changes:

- The packaged program must not write the developer installation's entry: in it,
  `--install-desktop` and `--uninstall-desktop` refuse (`is_packaged`,
  `PACKAGED_MENU_MESSAGE`).
- Before this installer existed, the developer installation's shortcut was also called
  `Ycrystal.lnk`. `--install-desktop` replaces such a shortcut with the new name, and
  `--uninstall-desktop` removes it, only if it starts Python with `-m ycrystal.app`. So
  the installer's `Ycrystal.lnk` is never taken for it.
- The installer's `AppId` GUID (`96A7291E-332A-4D2A-ACAD-E2489153A771`) must never
  change: Windows recognises updates and the uninstaller by it.
- `tests/test_windows_installer.py` checks that the Inno Setup script's ids match the
  Python constants and differ from the source installation's. It also checks that the
  `.ycrystal` default has no uninstall flag (the `[Code]` section removes it
  conditionally) and that the installer never touches the settings key.
  `tests/test_windows_desktop.py` checks the source side.
- `coexistence-check.ps1` runs the whole sequence for real: installer, then source
  entry, then each uninstalled in turn. CI runs it on every relevant pull request.

## POV-Ray

POV-Ray for Windows is not bundled: its licence (AGPL-3.0) and its own installer make it
a separate program, as for the developer installation. The packaged program finds and
drives it with the same code (`ycrystal.render.povray`): registry and Program Files
search, `/EXIT` command line, single-instance and editor-question checks. The installer
looks for it in the same places (`[Code]`, `PovrayFound`) only to tell the user, and
offers the download page at the end; it installs nothing of POV-Ray.

## Releasing

The installer is attached to a GitHub release by hand: build it, or take the
`ycrystal-windows-installer` artifact of the *Windows installer* workflow run of the
release commit, and upload `Ycrystal-<version>-windows-x64-setup.exe` to the release (see
the [release checklist](release.md)). Before it goes to users:

- **Code signing.** The installer and the programs are not signed, so SmartScreen warns
  ("Windows protected your PC") until a certificate is used. Signing needs a
  certificate and a decision about it; `build.ps1` has no signing step yet.
- **Licences.** The installer bundles Python and the packages of `constraints.txt` (see
  `THIRD_PARTY_NOTICES.md`); their licence texts are collected into
  `_internal\licenses` by the PyInstaller specification. ASE (LGPL) is collected as
  plain source files, so that users can replace it.

## Results

See [PROGRESS.md](../PROGRESS.md#windows-installer-18-november-2026) for what was
built and checked, and on which machines.
