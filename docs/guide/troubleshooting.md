# Troubleshooting and limitations

## Startup and display

| Symptom | Action |
| --- | --- |
| Qt reports an xcb platform-plugin error | Install `libxcb-cursor0` and run in the X11 desktop session used by the supported Mint setup. |
| “Could not initialize GLX” / Mesa cannot load | Recreate the environment with `/usr/bin/python3`, outside Conda. Check the desktop's OpenGL driver. |
| macOS: the Dock and the menu bar show “Python” | Expected: Ycrystal runs from a source checkout, not from an application bundle. Start it with `.venv/bin/ycrystal`; there is no launcher for the Applications folder yet. |
| No display on a server | The GUI needs a display and OpenGL. Use display-independent Python examples or `--check-renderer`; GUI tests can use Xvfb as described in the contributor guide. |
| Structure open fails | Read the error and [format restrictions](../FORMATS.md). The previous scene stays. Use Open As… if the format was misdetected. |
| A multi-block CIF or VASP 4 file asks a question | Choose the CIF block or supply the requested species elements. Cancelling keeps the current scene. |

## Renderer

| Symptom | Action |
| --- | --- |
| POV-Ray not found | Install `povray` (Linux Mint: `sudo apt install povray`; macOS: `brew install povray`), then choose the executable with Render ▸ Set POV-Ray Executable… (`/usr/bin/povray`, or `/opt/homebrew/bin/povray` with Homebrew on Apple silicon). A stale saved path takes precedence over the environment and `PATH`. |
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

The menu launcher exists on Linux only; on macOS the two options print an error and
write nothing.

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
- Vectors are entered by hand in Cartesian components; there is no import from tables
  or DFT output files and no magnetic symmetry. Measurements are not saved in projects.
- Transparent materials with area lights (Studio and Top lighting) render slowly; see
  [lighting](appearance.md#lighting).
- Scenes with native POV-Ray materials need the standard include files
  (`sudo apt install povray-includes`; Homebrew's `povray` on macOS contains them); a
  missing file is reported on export and render.
- The current reader accepts ordered structures only: partial/mixed CIF occupancy,
  overlapping sites, QE `ibrav != 0`, and QE `crystal_sg` are rejected.
- Camera navigation is outside undo/redo (it still marks the project modified); use
  **View ▸ Reset View** or the view directions. Rotation modes are not saved in projects.
- Styles transfer per-atom settings only between structures with the same atoms in the
  same order.
- Linux Mint 22.1 / Ubuntu 24.04, system Python 3.12, X11, and POV-Ray 3.7 are the
  integration baseline. macOS 15 on Apple silicon passes the same automated tests;
  hands-on checks there are still open (see the [support matrix](support.md)).
  Windows, Wayland, and POV-Ray 3.8 remain unverified.
- Python interfaces are evolving and carry no stable API guarantee yet.

See the [changelog](https://github.com/ymatterlab/ycrystal/blob/main/CHANGELOG.md) for
what each version added and the [progress record](../PROGRESS.md) for the evidence.
