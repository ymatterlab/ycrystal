# Install and launch

The integration baseline is Linux Mint 22.1 / Ubuntu 24.04 with the system Python
3.12, an X11 desktop, and working OpenGL. macOS 15 on Apple silicon is supported from
the same source and passes the same automated tests. Windows 11 with POV-Ray for
Windows 3.7 is supported from the same source too: it passes the automated tests and
was tested by hand on one computer. Other Python versions have not been verified (see
the [support matrix](support.md)). Ycrystal is installed from a source checkout into
its own virtual environment; no `sudo` is needed except for the system packages.

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

While the GitHub repository is private, `git clone` over HTTPS asks for credentials;
clone with `gh repo clone ymatterlab/ycrystal` (GitHub CLI, after `gh auth login`) or
over SSH (`git clone git@github.com:ymatterlab/ycrystal.git`) instead.

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
menu bar show “Python”, and `--install-desktop` (below) applies to Linux only.
Shortcuts use ⌘ where this guide says Ctrl. A virtual environment cannot be copied
between Linux and macOS: create it on each machine.

## Windows

On Windows 11 (x64), with [Git for Windows](https://git-scm.com/download/win), Python
3.12 from [python.org](https://www.python.org/downloads/windows/) (its installer adds the
`py` launcher), and POV-Ray for Windows 3.7, in PowerShell:

```powershell
winget install --id Python.Python.3.12 --exact --scope user   # or python.org's installer
# Then open a NEW PowerShell window (restart VS Code for its terminal), so that py is found.
git clone https://github.com/ymatterlab/ycrystal.git
cd ycrystal
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install -e . -c constraints.txt
.venv\Scripts\ycrystal.exe
```

`py` is the Python launcher that python.org's installer (and `winget`) puts on `PATH`. A
terminal that was open before the installation keeps its old `PATH`, also VS Code's
integrated terminal until VS Code is restarted; there PowerShell answers "The term 'py'
is not recognized". In a new terminal, `py --list` shows the installed versions. Once
`.venv` exists, use its own programs (`.venv\Scripts\python.exe`,
`.venv\Scripts\ycrystal.exe`); they need nothing on `PATH`. There is no Start-menu entry
yet: start Ycrystal from PowerShell in the checkout with `.venv\Scripts\ycrystal.exe`.
Install
POV-Ray for Windows 3.7 with the official installer from
[povray.org](https://www.povray.org/download/) (`povwin-3.7-agpl3-setup.exe`), keeping
its user files: they include the standard include files, which go to
`Documents\POV-Ray\v3.7\include`. Ycrystal finds `pvengine64.exe` in POV-Ray's
installation folder by itself (POV-Ray for Windows has no `povray` command and is not on
`PATH`); **Render ▸ Set POV-Ray Executable…** or `YCRYSTAL_POVRAY` choose another one.

After installing it, **start POV-Ray for Windows once from the Start menu**. It asks
whether to download its editor ("Could not load internal editor – download it?"): the
AGPL installer does not include it. Either install the editor from the page that *Yes*
opens, or answer *No* and untick *Options ▸ Other Settings ▸ Use Editor*. Otherwise it
asks at every start, and each Ycrystal render waits for the answer. Then close
POV-Ray.

POV-Ray for Windows is a window program. For each preview and render, Ycrystal starts
it minimised (its button appears on the taskbar while it runs) and it closes by itself.
It cannot render for Ycrystal while you have POV-Ray for Windows open yourself: close it
first, or turn off *Options ▸ Keep Single Instance* in POV-Ray (see
[troubleshooting](troubleshooting.md#renderer)). The Windows Store `python` command
(an alias that opens the Store) is not used; `py -3.12` runs the installed Python.

## Check the installation

```bash
.venv/bin/ycrystal --version          # ycrystal 0.4.0.dev0
.venv/bin/ycrystal --check-renderer   # PASS: POV-Ray 3.7… passed
.venv/bin/ycrystal examples/SrTiO3-studio.ycrystal --render SrTiO3.png
```

On Windows, in PowerShell:

```powershell
.venv\Scripts\ycrystal.exe --version          # ycrystal 0.4.0.dev0
.venv\Scripts\ycrystal.exe --check-renderer   # PASS: POV-Ray 3.7.0.0 at C:\Program Files\POV-Ray\v3.7\bin\pvengine64.exe passed…
.venv\Scripts\ycrystal.exe examples\SrTiO3-studio.ycrystal --render SrTiO3.png
```

The last command renders an [example project](examples.md) without opening a window.
The other commands of this guide work the same way on Windows, with
`.venv\Scripts\ycrystal.exe` for `.venv/bin/ycrystal`, `.venv\Scripts\python.exe` for
`.venv/bin/python`, and backslashes in paths.

## Menu launcher (Linux)

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

Projects and styles from earlier versions keep opening; newer project files are refused
by older versions with a message to update. To uninstall, run
`.venv/bin/ycrystal --uninstall-desktop` (Linux), then delete the checkout directory.
Settings (POV-Ray path, favourites, last folder) are in
`~/.config/Y-Matter Lab/Ycrystal.conf` on Linux and in
`~/Library/Preferences/com.y-matter-lab.Ycrystal.plist` on macOS, where the thumbnails
of personal materials are in `~/Library/Application Support/Y-Matter Lab/Ycrystal`. On
Windows the settings are in the registry (`HKEY_CURRENT_USER\Software\Y-Matter
Lab\Ycrystal`) and the thumbnails in `%APPDATA%\Y-Matter Lab\Ycrystal`.

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
