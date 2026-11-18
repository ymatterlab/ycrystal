# Install and launch

The integration baseline is Linux Mint 22.1 / Ubuntu 24.04 with the system Python
3.12, an X11 desktop, and working OpenGL. macOS 15 on Apple silicon is supported from
the same source and passes the same automated tests. Windows 11 with POV-Ray for
Windows 3.7 is supported from the same source too: it passes the automated tests and
was tested by hand on one computer; there, a graphical installer is the recommended
way ([Windows](#windows)). Python 3.12, 3.13, and 3.14 are supported; where
each was tested is in the [support matrix](support.md). Ycrystal is installed from its
source folder into its own virtual environment; no `sudo` is needed except for the
system packages.

## Without Git

The sections below get the source with `git clone`, which makes updating a `git pull`.
Git is not needed otherwise: download
[the source as a ZIP file](https://github.com/ymatterlab/ycrystal/archive/refs/heads/main.zip)
(also under the green **Code** button on GitHub), unpack it, and run the remaining
commands of your system in the unpacked folder `ycrystal-main` instead of `ycrystal`:

```bash
curl -L -o ycrystal.zip https://github.com/ymatterlab/ycrystal/archive/refs/heads/main.zip
unzip ycrystal.zip && cd ycrystal-main
```

On Windows, in PowerShell (or unpack with File Explorer's *Extract All*):

```powershell
Invoke-WebRequest https://github.com/ymatterlab/ycrystal/archive/refs/heads/main.zip -OutFile ycrystal.zip
Expand-Archive ycrystal.zip . ; cd ycrystal-main
```

To update without Git, download and unpack the new ZIP file, install again in the new
folder (on Linux also `--install-desktop` again if you use the menu launcher; on
Windows run the installation script there, which also moves the Start-menu entry to
it), and delete the old folder.

## Linux Mint

```bash
sudo apt update
sudo apt install git povray povray-includes libxcb-cursor0 python3.12-venv
git clone https://github.com/ymatterlab/ycrystal.git
cd ycrystal
/usr/bin/python3 -m venv .venv
.venv/bin/python -m pip install -e . -c constraints.txt
.venv/bin/ycrystal
```

Use `/usr/bin/python3`: Miniconda/Anaconda's bundled `libstdc++` can prevent Mesa
from loading and cause “Could not initialize GLX”. `libxcb-cursor0` is needed by Qt
on X11. POV-Ray is optional for opening structures and exporting scenes, and required
for previews and rendering PNGs; `povray-includes` provides the standard include files
that native POV-Ray materials (gold, marble, `M_Glass`, …) need. The `pip install`
step downloads about 300 MB of wheels (Qt, VTK) the first time. To install developer
tools, use `-e ".[dev]"` instead of `-e .`.

If using `uv`, the equivalent environment setup is:

```bash
uv venv --python /usr/bin/python3.12 .venv
uv pip install --python .venv/bin/python -e . -c constraints.txt
```

## macOS

With [Homebrew](https://brew.sh/) on macOS 15 (Apple silicon):

```bash
xcode-select --install            # Git and the command-line tools, if missing
brew install python@3.12 povray
git clone https://github.com/ymatterlab/ycrystal.git
cd ycrystal
python3.12 -m venv .venv
.venv/bin/python -m pip install -e . -c constraints.txt
.venv/bin/ycrystal
```

Homebrew's `povray` is POV-Ray 3.7 and contains the standard include files; Ycrystal
finds it on `PATH` (`/opt/homebrew/bin/povray`). The window is started from the
terminal: there is no application bundle or Dock launcher yet, so the Dock and the
menu bar show “Python”, and `--install-desktop` (below) applies to Linux and Windows
only.
Shortcuts use ⌘ where this guide says Ctrl. A virtual environment cannot be copied
between Linux and macOS: create it on each machine.

## Windows

There are two installations for Windows 11 (x64). Most users want the first:

- **the installer** (recommended): a graphical setup program that installs Ycrystal
  with everything it needs except POV-Ray; no Python, Git, or PowerShell;
- **the developer installation**: Ycrystal from its source folder, set up by a
  PowerShell script, for working on Ycrystal or running its newest source.

Both can be on one computer: they have separate Start-menu entries (**Ycrystal** and
**Ycrystal (development)**), and uninstalling one leaves the other working (see
[both installations](#both-installations-on-one-computer)). Both need POV-Ray for
Windows 3.7 for previews and images ([below](#pov-ray-for-windows)).

### Windows: the installer (recommended)

1. Download `Ycrystal-<version>-windows-x64-setup.exe` from the
   [Releases page](https://github.com/ymatterlab/ycrystal/releases). Version 0.5.0 is
   the first with it; until its GitHub release carries the file, the installer of the
   newest source can be downloaded, with a GitHub account, from the latest run of the
   [*Windows installer* workflow](https://github.com/ymatterlab/ycrystal/actions/workflows/windows-installer.yml)
   (artifact `ycrystal-windows-installer`: a ZIP file with the installer inside).
2. Run it. The installer is not signed yet, so Windows may show "Windows protected your
   PC": choose *More info*, then *Run anyway*.
3. Follow the wizard. By default it installs for you alone, without administrator
   rights, into `%LOCALAPPDATA%\Programs\Ycrystal`; an administrator can choose an
   installation for all users (`Program Files`). It adds **Ycrystal** to the Start
   menu and, unless you untick it, opens `.ycrystal` projects with Ycrystal from File
   Explorer. If it does not find POV-Ray for Windows, it says so and offers its
   download page at the end.
4. Start **Ycrystal** from the Start menu.

The installed folder also holds `ycrystal-cli.exe`, the command line (the `ycrystal`
command of the other installations), for example in PowerShell:
`& "$env:LOCALAPPDATA\Programs\Ycrystal\ycrystal-cli.exe" --check-renderer`. To
update, run the installer of the new version: it replaces the old one. To uninstall,
use *Settings ▸ Apps ▸ Installed apps ▸ Ycrystal ▸ Uninstall*. Settings, favourites,
and personal materials are kept in both cases.

### Windows: developer installation (PowerShell)

In PowerShell. Install [Git for Windows](https://git-scm.com/download/win)
first if it is missing (`winget install --id Git.Git --exact`, then open a new
PowerShell window), or get the source [without Git](#without-git) and skip the first
two lines:

```powershell
git clone https://github.com/ymatterlab/ycrystal.git
cd ycrystal
powershell -ExecutionPolicy Bypass -File scripts\install-windows.ps1
```

The script installs what is missing and checks the result:

1. Python 3.12 with `winget`, for the current user, unless `py` finds Python 3.12,
   3.13, or 3.14 (in this order);
2. the virtual environment `.venv` in the checkout, with Ycrystal and the tested
   package versions of `constraints.txt` (about 300 MB the first time);
3. POV-Ray for Windows 3.7 with `winget`, unless it is installed: its official
   installer from povray.org, which asks Windows for administrator permission;
4. if POV-Ray for Windows would ask at every start whether to download its editor,
   it opens once so that you can answer for good: *No*, then untick
   *Options ▸ Other Settings ▸ Use Editor*, and close it (details below);
5. **Ycrystal (development)** in the Start menu, and `.ycrystal` projects opening
   with it from File Explorer unless the installed Ycrystal already opens them
   ([menu entry](#menu-entry));
6. the renderer check (`--check-renderer`).

Then start **Ycrystal (development)** from the Start menu. The script can run again at any time: after
`git pull` it updates the installation. It ends with "Ycrystal is ready." (exit status
0), or with a list of what is not ready yet. Its options: `-Python C:\path\to\python.exe`
(another Python, 3.12 or newer, for `.venv`; newer than 3.14 with a warning; ignored
once `.venv` exists, so delete `.venv` to change it), `-Dev` (also the developer tools),
`-NoPovray`, and `-NoStartMenu`; `Get-Help .\scripts\install-windows.ps1 -Detailed`
describes them. `-ExecutionPolicy Bypass` lets this one PowerShell run the script,
which Windows' default policy refuses otherwise; it changes no setting.

POV-Ray for Windows is a window program. For each preview and render, Ycrystal starts
it minimised (its button appears on the taskbar while it runs) and it closes by itself.
It cannot render for Ycrystal while you have POV-Ray for Windows open yourself: close it
first, or turn off *Options ▸ Keep Single Instance* in POV-Ray (see
[troubleshooting](troubleshooting.md#renderer)).

#### Developer installation, step by step

The same installation without the script:

```powershell
winget install --id Python.Python.3.12 --exact --scope user       # or python.org's installer
winget install --id PersistenceOfVisionRaytracer.POVRay --exact   # or povray.org's installer
# Then open a NEW PowerShell window (restart VS Code for its terminal), so that py is found.
cd ycrystal
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install -e . -c constraints.txt
.venv\Scripts\ycrystal.exe --install-desktop
.venv\Scripts\ycrystal.exe
```

`py` is the Python launcher that python.org's installer (and `winget`) puts on `PATH`. A
terminal that was open before the installation keeps its old `PATH`, also VS Code's
integrated terminal until VS Code is restarted; there PowerShell answers "The term 'py'
is not recognized". In a new terminal, `py --list` shows the installed versions. Once
`.venv` exists, use its own programs (`.venv\Scripts\python.exe`,
`.venv\Scripts\ycrystal.exe`); they need nothing on `PATH`. The Windows Store `python`
command (an alias that opens the Store) is not used.

### POV-Ray for Windows

Both installations render with POV-Ray for Windows 3.7, installed separately. The
developer script installs it with `winget` if it is missing; for the installer version,
install it yourself:

```powershell
winget install --id PersistenceOfVisionRaytracer.POVRay --exact   # or povray.org's installer
```

The `winget` package of POV-Ray for Windows 3.7 runs its official installer from
[povray.org](https://www.povray.org/download/) (`povwin-3.7-agpl3-setup.exe`, the same
file and checksum), which can also be run by hand; keep its user files: they include
the standard include files, which go to `Documents\POV-Ray\v3.7\include`. Ycrystal
finds `pvengine64.exe` in POV-Ray's installation folder by itself (POV-Ray for Windows
has no `povray` command and is not on `PATH`); **Render ▸ Set POV-Ray Executable…** or
`YCRYSTAL_POVRAY` choose another one.

After installing it, **start POV-Ray for Windows once from the Start menu**. It asks
whether to download its editor ("Could not load internal editor – download it?"): the
AGPL installer does not include it. Either install the editor from the page that *Yes*
opens, or answer *No* and untick *Options ▸ Other Settings ▸ Use Editor*. Otherwise it
asks at every start; Ycrystal then refuses to render and says so, because each render
would wait for that answer. Then close POV-Ray.

### Both installations on one computer

| | Installer version | Developer installation |
| --- | --- | --- |
| Start-menu entry | **Ycrystal** (`Ycrystal.exe` in the installation folder) | **Ycrystal (development)** (the checkout's `.venv\Scripts\pythonw.exe`) |
| Taskbar | its own button and identity | its own: the windows of the two never group together |
| `.ycrystal` file type | registered by the installer, which opens projects | added to *Open with*; opens projects only if no other program does |
| Removed by | *Settings ▸ Apps* (its uninstaller) | `.venv\Scripts\ycrystal.exe --uninstall-desktop` |
| POV-Ray, settings, personal materials | shared | shared |

Each removes only what it added, so uninstalling one leaves the other working.
`--install-desktop` belongs to the developer installation; the installed
`ycrystal-cli.exe` refuses it. A Start-menu entry named **Ycrystal** made by an earlier
developer installation is renamed **Ycrystal (development)** when the script or
`--install-desktop` runs again.

## Check the installation

```bash
.venv/bin/ycrystal --version          # ycrystal 0.5.0
.venv/bin/ycrystal --check-renderer   # PASS: POV-Ray 3.7… passed
.venv/bin/ycrystal examples/SrTiO3-studio.ycrystal --render SrTiO3.png
```

On Windows, in PowerShell:

```powershell
.venv\Scripts\ycrystal.exe --version          # ycrystal 0.5.0
.venv\Scripts\ycrystal.exe --check-renderer   # PASS: POV-Ray 3.7.0.0 at C:\Program Files\POV-Ray\v3.7\bin\pvengine64.exe passed…
.venv\Scripts\ycrystal.exe examples\SrTiO3-studio.ycrystal --render SrTiO3.png
```

The last command renders an [example project](examples.md) without opening a window.
The other commands of this guide work the same way on Windows, with
`.venv\Scripts\ycrystal.exe` for `.venv/bin/ycrystal`, `.venv\Scripts\python.exe` for
`.venv/bin/python`, and backslashes in paths.

## Menu entry

On Linux,

```bash
.venv/bin/ycrystal --install-desktop
```

adds **Ycrystal** to the Linux Mint menu (category *Science*), with an icon, and makes
`.ycrystal` projects open in Ycrystal from the file manager. It writes three files for
the current user only, under `~/.local/share` (`applications/ycrystal.desktop`,
`icons/hicolor/scalable/apps/ycrystal.svg`, `mime/packages/ycrystal.xml`). The launcher
starts this checkout's `.venv/bin/ycrystal` by absolute path: run the command again if
you move the checkout. `.venv/bin/ycrystal --uninstall-desktop` removes the files. The
menu may need a moment (or a new login) to show the entry.

On Windows, in the developer installation, `.venv\Scripts\ycrystal.exe
--install-desktop` (the installation script runs it) adds **Ycrystal (development)** to
the Start menu, for the current user, without administrator rights. The installer
version has its own entry, **Ycrystal**, made by its installer (see
[both installations](#both-installations-on-one-computer)).

- the shortcut `Ycrystal (development).lnk` in the user's Start-menu folder. It starts
  this checkout's `.venv\Scripts\pythonw.exe` with `-I -m ycrystal.app`, so that no
  console window opens, and it carries the application id that this installation's
  window uses on the taskbar (`YMatterLab.Ycrystal`; the installer version uses
  another one);
- its icon, `%LOCALAPPDATA%\Y-Matter Lab\Ycrystal\ycrystal.ico`, drawn from the
  application's SVG icon;
- the file type `Ycrystal.Project` of `.ycrystal` projects, under
  `HKEY_CURRENT_USER\Software\Classes`. It is added to the *Open with* list, and opens
  projects from File Explorer if no other program does: when the installer version
  is installed, it keeps opening them. A program that you chose for `.ycrystal` files
  in Windows' *Open with* dialog stays your choice.

Run the command again if you move the checkout. `--uninstall-desktop` removes the
shortcut, the icon, and the file type, and nothing of the installer version. Started this way, Ycrystal has no console for
messages; to see them, start it from PowerShell with `.venv\Scripts\ycrystal.exe`.

## Update and uninstall

```bash
cd ycrystal
git pull
.venv/bin/python -m pip install -e . -c constraints.txt
```

On Linux, if you installed the menu launcher, refresh it after updating:

```bash
.venv/bin/ycrystal --install-desktop
```

The launcher uses a separate copy of the application icon under `~/.local/share`;
`git pull` updates the source SVG but does not replace that installed copy.

The installer version on Windows is updated by running the installer of the new
version, and uninstalled in *Settings ▸ Apps*; the rest of this section is about
installations from source.

On Windows, update with `git pull`, then run the installation script again
(`powershell -ExecutionPolicy Bypass -File scripts\install-windows.ps1`): it updates
`.venv` and the Start-menu entry. Without the script, run the `pip install` line with
`.venv\Scripts\python.exe`, then `.venv\Scripts\ycrystal.exe --install-desktop`.

Projects and styles from earlier versions keep opening; newer project files are refused
by older versions with a message to update. To uninstall, run
`.venv/bin/ycrystal --uninstall-desktop` (Linux; on Windows
`.venv\Scripts\ycrystal.exe --uninstall-desktop`), then delete the checkout directory.
On Windows, Python and POV-Ray for Windows stay installed; remove them in *Settings ▸
Apps* if nothing else needs them.
Settings (POV-Ray path, favourites, last folder) are in
`~/.config/Y-Matter Lab/Ycrystal.conf` on Linux and in
`~/Library/Preferences/com.y-matter-lab.Ycrystal.plist` on macOS, where the thumbnails
of personal materials are in `~/Library/Application Support/Y-Matter Lab/Ycrystal`. On
Windows the settings are in the registry (`HKEY_CURRENT_USER\Software\Y-Matter
Lab\Ycrystal`) and the thumbnails in `%APPDATA%\Y-Matter Lab\Ycrystal`, for both
Windows installations; neither uninstallation deletes them.

## Launch options

Run these from the checkout root:

```bash
.venv/bin/ycrystal --sample perovskite
.venv/bin/ycrystal --sample triclinic
.venv/bin/ycrystal tests/fixtures/MgB2.cif
.venv/bin/ycrystal tests/fixtures/Si.pw.in --format qe
.venv/bin/ycrystal --check-renderer
.venv/bin/ycrystal --help
```

The default sample is cubic SrTiO3: 5 scientific atoms, displayed as 15 balls with
boundary images. The triclinic sample contains O, Fe, S, Cl, and N at general positions
in a skewed cell, so it shows 5 balls. Both are synthetic and require no downloaded
data. There is no sample chooser in the current GUI; choose one at launch.

A file argument opens after the window appears. If import fails, a message explains
why and the sample stays. **File ▸ Open…** (Ctrl+O) opens structures or projects;
**File ▸ Open As…** overrides format detection. The checkout's `tests/fixtures/`
contains small valid inputs and deliberate rejection cases; see
[supported formats](../FORMATS.md).

`--check-renderer` runs without a window or display and exits with status 0 for
`PASS`, 1 for `FAIL`. See [renderer setup](rendering.md#configure-and-check-pov-ray).
For documentation-only installation, see the [documentation workflow](../development/documentation.md).
