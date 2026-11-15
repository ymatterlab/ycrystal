# Troubleshooting and limitations

## Startup and display

| Symptom | Action |
| --- | --- |
| Qt reports an xcb platform-plugin error | Install `libxcb-cursor0` and run in the X11 desktop session used by the supported Mint setup. |
| “Could not initialize GLX” / Mesa cannot load | Recreate the environment with `/usr/bin/python3`, outside Conda. Check the desktop's OpenGL driver. |
| No display on a server | The GUI needs a display and OpenGL. Use display-independent Python examples or `--check-renderer`; GUI tests can use Xvfb as described in the contributor guide. |
| Structure open fails | Read the error and [format restrictions](../FORMATS.md). The previous scene stays. Use Open As… if the format was misdetected. |
| A multi-block CIF or VASP 4 file asks a question | Choose the CIF block or supply the requested species elements. Cancelling keeps the current scene. |

## Renderer

| Symptom | Action |
| --- | --- |
| POV-Ray not found | Install `povray`, then choose `/usr/bin/povray` with Render ▸ Set POV-Ray Executable…. A stale saved path takes precedence over the environment and `PATH`. |
| CLI check passes, GUI rendering fails to find POV-Ray | The CLI does not use the saved GUI setting. Re-select the executable in the application. |
| “Viewing angle has to be smaller than 180” | A known self-built 3.8 build with `-ffast-math` rejects unset camera fields. Use the distribution 3.7 package and run Check Renderer. Rebuild custom binaries without that optimisation if necessary. |
| I/O restriction / permission denied | Ycrystal's jobs write in a temporary working directory. Check its permissions and whether `povray.conf` permits the working directory. Run an exported `.ini` from its own directory. |
| Render finished but cannot save the PNG | Choose a writable destination. The GUI removes its job files after handling the failure; retry the render. |
| The preview dock says “out of date” or “discarded” | The view or scene changed after the preview started. Press **Preview** (F5), or enable **Update automatically**. |
| The preview dock shows an error | Previews report problems in the dock instead of a dialog; the same renderer setup fixes apply. |

For an ordinary render failure the GUI shows an explanation, often with the last
renderer output. A renderer check is a small diagnostic render, not a guarantee
that every scene or output directory will work.

## Menu launcher

- *Ycrystal does not appear in the menu*: run `.venv/bin/ycrystal --install-desktop`
  again from the checkout; Cinnamon may need a few seconds or a new login. The launcher
  runs the checkout's `.venv/bin/ycrystal` by absolute path, so moving or deleting the
  checkout breaks it: reinstall the launcher from the new place.
- *A `.ycrystal` file does not open in Ycrystal*: right-click it, choose
  *Open With ▸ Other Application*, and pick Ycrystal; `xdg-mime query filetype FILE`
  should report `application/x-ycrystal-project`.
- `--uninstall-desktop` removes the launcher, icon, and file type.

## Current limitations and roadmap

- No atom editing or structure-format export. Display repetitions (numeric or with the
  supercell handles) and periodic bonds change only the display. The comparison module's
  `supercell` helper transforms scientific data for developer comparisons.
- Materials and environments come from the built-in catalog; user include files,
  image backgrounds, and editable material parameters (for example a custom refractive
  index) are not supported. The live view approximates materials, floors, and skies.
- Transparent materials with area lights (Studio and Top lighting) render slowly; see
  [lighting](appearance.md#lighting).
- Scenes with native POV-Ray materials need the standard include files
  (`sudo apt install povray-includes`); a missing file is reported on export and render.
- The current reader accepts ordered structures only: partial/mixed CIF occupancy,
  overlapping sites, QE `ibrav != 0`, and QE `crystal_sg` are rejected.
- Camera navigation is outside undo/redo (it still marks the project modified); use
  **View ▸ Reset View** or the view directions. Rotation modes are not saved in projects.
- Styles transfer per-atom settings only between structures with the same atoms in the
  same order.
- Linux Mint 22.1 / Ubuntu 24.04, system Python 3.12, X11, and POV-Ray 3.7 are the
  integration baseline. Other platforms, Wayland, and POV-Ray 3.8 remain unverified.
- Python interfaces are evolving and carry no stable API guarantee yet.

See the [milestone table and acceptance evidence](../PROGRESS.md#milestones) for
the roadmap. This documentation increment does not complete product milestones.
