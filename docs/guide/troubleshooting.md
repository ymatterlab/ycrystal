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
| A project reopens with a different crop | Match the original window shape. Output height and visible width depend on the viewport aspect. |

For an ordinary render failure the GUI shows an explanation, often with the last
renderer output. A renderer check is a small diagnostic render, not a guarantee
that every scene or output directory will work.

## Current limitations and roadmap

- No GUI supercell repetitions, bonds, view-direction buttons, atom editing, or
  structure-format export. The comparison module's `supercell` helper is developer
  functionality, not a GUI feature.
- No preview/output-aspect frame, render cancellation button, material or environment
  galleries, or light controls.
- The current reader accepts ordered structures only: partial/mixed CIF occupancy,
  overlapping sites, QE `ibrav != 0`, and QE `crystal_sg` are rejected.
- Projects save the view, but viewport aspect still depends on the window. Camera
  navigation and output settings are outside undo/redo.
- Linux Mint 22.1 / Ubuntu 24.04, system Python 3.12, X11, and POV-Ray 3.7 are the
  integration baseline. Other platforms, Wayland, and POV-Ray 3.8 remain unverified.
- Python interfaces are evolving and carry no stable API guarantee yet.

See the [milestone table and acceptance evidence](../PROGRESS.md#milestones) for
the roadmap. This documentation increment does not complete product milestones.
