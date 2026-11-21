# Troubleshooting and limitations

## Startup and display

| Symptom | Action |
| --- | --- |
| Qt reports an xcb platform-plugin error | Install `libxcb-cursor0` and run in the X11 desktop session used by the supported Mint setup. |
| “Could not initialize GLX” / Mesa cannot load | Recreate the environment with `/usr/bin/python3`, outside Conda. Check the desktop's OpenGL driver. |
| macOS: the Dock and the menu bar show “Python” | Expected: Ycrystal runs from a source checkout, not from an application bundle. Start it with `.venv/bin/ycrystal`; there is no launcher for the Applications folder yet. |
| Windows: “The term 'py' is not recognized” | Install Python 3.12 from python.org (or `winget install --id Python.Python.3.12 --exact --scope user`), then open a new PowerShell window; a terminal opened before the installation, also VS Code's until VS Code restarts, keeps the old `PATH`. `py --list` shows the installed versions. After `py -3.12 -m venv .venv`, run `.venv\Scripts\python.exe` and `.venv\Scripts\ycrystal.exe`, which need nothing on `PATH`. |
| Windows: `python` opens the Microsoft Store | That `python` is a Store alias, not an installed Python. Use `py -3.12` (above) or the virtual environment's `.venv\Scripts\python.exe`. |
| Windows: the installer shows “Windows protected your PC” | The installer is not signed yet, so SmartScreen does not know it. Choose *More info*, then *Run anyway*, if it came from Ycrystal's Releases page or workflow. |
| Windows: two Ycrystal entries in the Start menu | **Ycrystal** is the installer version, **Ycrystal (development)** the developer installation from a source folder; they are independent (see [both installations](install.md#both-installations-on-one-computer)). Remove the development entry with `.venv\Scripts\ycrystal.exe --uninstall-desktop` in that folder, the installer version in *Settings ▸ Apps*. |
| Windows, installer version: `Ycrystal.exe --render …` prints nothing | `Ycrystal.exe` is the window program, without a console. Use `ycrystal-cli.exe` in the same folder for the command line. Its `--install-desktop` reports that the installer manages the Start menu: that option is for installations from source. |
| Windows: “running scripts is disabled on this system” | Windows' default policy refuses PowerShell scripts. Start the installation script as the [install guide](install.md#windows) writes it, `powershell -ExecutionPolicy Bypass -File scripts\install-windows.ps1`, which allows it for that one run and changes no setting. |
| Windows: the installation script ends with “Not ready yet” | Each line says what is missing and what to do; fix it and run the script again (it repeats only what is needed). If `pip` failed with a broken `.venv`, delete the `.venv` folder first. |
| No display on a server | The GUI needs a display and OpenGL. Use display-independent Python examples or `--check-renderer`; GUI tests can use Xvfb as described in the contributor guide. |
| Structure open fails | Read the error and [format restrictions](../FORMATS.md). The previous scene stays. Use Open As… if the format was misdetected. |
| A multi-block CIF or VASP 4 file asks a question | Choose the CIF block or supply the requested species elements. Cancelling keeps the current scene. |

## Renderer

| Symptom | Action |
| --- | --- |
| POV-Ray not found | Install `povray` (Linux Mint: `sudo apt install povray`; macOS: `brew install povray`; Windows: POV-Ray for Windows 3.7 from povray.org), then choose the executable with Render ▸ Set POV-Ray Executable… (`/usr/bin/povray`, `/opt/homebrew/bin/povray` with Homebrew on Apple silicon, or `C:\Program Files\POV-Ray\v3.7\bin\pvengine64.exe`). A stale saved path takes precedence over the environment and `PATH`. |
| Windows: “POV-Ray for Windows is already open … Keep Single Instance” | POV-Ray for Windows runs only one copy at a time unless its option *Options ▸ Keep Single Instance* is off, so it cannot render for Ycrystal while you have it open (also minimised). Close it, or turn the option off in POV-Ray, and render again. Ycrystal's own previews and renders take turns by themselves. |
| Windows: “POV-Ray for Windows would stop before rendering to ask "Could not load internal editor - download it?"” | Without its editor, POV-Ray for Windows asks this at every start, and each render would wait for the answer, so Ycrystal does not start it. Start POV-Ray for Windows once from the Start menu, answer *No*, untick *Options ▸ Other Settings ▸ Use Editor*, and close it (or answer *Yes* and install the editor). The installation script offers this step. |
| Windows: a preview or render does not finish | POV-Ray for Windows is waiting for an answer in a window of its own; click its button on the taskbar. Its About box appears at its second start and then every 14 days: click *OK*, and the render continues. |
| Windows: a POV-Ray button appears on the taskbar during previews | Expected: POV-Ray for Windows is a window program; Ycrystal starts it minimised and it closes when the image is done. In the window, Ycrystal keeps it from taking the keyboard focus. A render started from a terminal (`--render`) cannot prevent that, so the terminal loses the keyboard focus while POV-Ray runs. |
| CLI check passes, GUI rendering fails to find POV-Ray | The CLI does not use the saved GUI setting. Re-select the executable in the application. |
| “Viewing angle has to be smaller than 180” | A known self-built 3.8 build with `-ffast-math` rejects unset camera fields. Use the distribution 3.7 package and run Check Renderer. Rebuild custom binaries without that optimisation if necessary. |
| I/O restriction / permission denied | Ycrystal's jobs write in a temporary working directory. Check its permissions and whether `povray.conf` permits the working directory. Run an exported `.ini` from its own directory. |
| Render finished but cannot save the image | Choose a writable destination. An existing file of that name is left unchanged and no partial file remains. The GUI removes its job files after handling the failure; retry the render. |
| The preview dock says “out of date” or “discarded” | The view or scene changed after the preview started. Press **Preview** (F5), or enable **Update automatically**. Resizing the window or a panel does not make a preview out of date. |
| The preview dock shows an error | Previews report problems in the dock instead of a dialog; the same renderer setup fixes apply. |

For an ordinary render failure the GUI shows an explanation, often with the last
renderer output. A renderer check is a small diagnostic render, not a guarantee
that every scene or output directory will work.

## Menu launcher

The menu entry of `--install-desktop` exists on Linux (a menu launcher) and Windows (a
Start-menu shortcut, **Ycrystal (development)**); on macOS, and in the Windows installer
version, the two options print an error and write nothing.

- *Windows: Ycrystal in the Start menu does not start, or a `.ycrystal` file does not
  open*: started from the Start menu, Ycrystal has no console that could show an error.
  Start `.venv\Scripts\ycrystal.exe` in PowerShell in the checkout to see it. If the
  checkout was moved, run `.venv\Scripts\ycrystal.exe --install-desktop` again from the
  new place. If another program was chosen for `.ycrystal` files in Windows' *Open
  with* dialog, that choice stays; open projects with **File ▸ Open…** in Ycrystal.
- *Ycrystal does not appear in the menu*: run `.venv/bin/ycrystal --install-desktop`
  again from the checkout; Cinnamon may need a few seconds or a new login. The launcher
  runs the checkout's `.venv/bin/ycrystal` by absolute path, so moving or deleting the
  checkout breaks it: reinstall the launcher from the new place.
- *A `.ycrystal` file does not open in Ycrystal*: right-click it, choose
  *Open With ▸ Other Application*, and pick Ycrystal; `xdg-mime query filetype FILE`
  should report `application/x-ycrystal-project`.
- *The menu or panel still shows the old icon after `git pull`*: run
  `.venv/bin/ycrystal --install-desktop` to replace the installed icon copy with the
  updated SVG. Close and reopen Ycrystal. If Cinnamon still shows the old icon,
  log out and back in to refresh the desktop session.
- `--uninstall-desktop` removes the launcher, icon, and file type.

## Current limitations and roadmap

- No atom editing or structure-format export. Display repetitions (numeric or with the
  supercell handles) and periodic bonds change only the display. The comparison module's
  `supercell` helper transforms scientific data for developer comparisons.
- Materials and environments come from the built-in catalog. Ycrystal recipes can be
  customised (**Customize Material…**), but native POV-Ray materials cannot, user
  include files are not supported, and personal materials cannot yet be renamed or
  deleted in the window. The live view approximates materials, floors, and skies, and
  shows a background picture only as its average colour; the POV-Ray preview shows the
  picture itself.
- Exported PDF files contain the POV-Ray raster image, not vector graphics. The command
  line (`--render`) writes PNG only; PDF and JPEG come from **Render Image…**.
- The [element legend](rendering.md#element-legend) is painted onto images: it is
  raster in a PDF, absent from exported `.pov` scenes, placed by edge or by numbers
  (not by dragging), and drawn with the fonts of the computer that renders. On the
  command line it comes from a project or a style; there is no `--legend` option.
- Vectors are entered by hand in Cartesian components; there is no import from tables
  or DFT output files and no magnetic symmetry. Measurements are not saved in projects.
- Transparent materials with area lights (Studio and Top lighting) render slowly; see
  [lighting](appearance.md#lighting).
- Scenes with native POV-Ray materials need the standard include files
  (`sudo apt install povray-includes`; Homebrew's `povray` on macOS and POV-Ray for
  Windows contain them); a missing file is reported on export and render.
- Windows: POV-Ray for Windows reports no progress, so previews and renders show a busy
  indicator instead of a percentage, and a final render makes later previews wait until
  it has finished.
- The current reader accepts ordered structures only: partial/mixed CIF occupancy,
  overlapping sites, and QE `crystal_sg` are rejected. QE input with `ibrav` other than
  0 is read with pw.x's lattice vectors (see
  [Quantum ESPRESSO lattices](qe-lattices.md), including old `ibrav = −13` files).
- Camera navigation is outside undo/redo (it still marks the project modified); use
  **View ▸ Reset View** or the view directions. Rotation modes are not saved in projects.
- Styles transfer per-atom settings only between structures with the same atoms in the
  same order.
- Linux Mint 22.1 / Ubuntu 24.04, system Python 3.12, X11, and POV-Ray 3.7 are the
  integration baseline. macOS 15 on Apple silicon and Windows 11 with POV-Ray for
  Windows 3.7 pass the same automated tests; Windows was also tested by hand on one
  computer, and hands-on checks on the Mac are still open (see the
  [support matrix](support.md)). Wayland and POV-Ray 3.8 remain unverified.
- Python interfaces are evolving and carry no stable API guarantee yet.

See the [changelog](https://github.com/ymatterlab/ycrystal/blob/main/CHANGELOG.md) for
what each version added and the [progress record](../PROGRESS.md) for the evidence.
