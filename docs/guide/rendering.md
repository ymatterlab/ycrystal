# Export and rendering

## Configure and check POV-Ray

On Linux Mint, install the distribution renderer with `sudo apt install povray`.
The tested baseline is POV-Ray 3.7. In the GUI, discovery uses the first source that
is set:

1. **Render ▸ Set POV-Ray Executable…** (saved on this machine).
2. The `YCRYSTAL_POVRAY` environment variable.
3. `povray` on `PATH`.

An invalid configured path fails immediately; discovery does not fall back. Choose
`/usr/bin/povray` in the menu to replace a stale setting. GUI settings are separate
from projects. On Linux they normally live in
`~/.config/Y-Matter Lab/Ycrystal.conf`.

**Render ▸ Check Renderer** renders a small known scene, verifies dimensions,
positions, and colours, and shows a verdict. It runs synchronously and briefly
blocks the window. The command-line check needs no display:

```bash
.venv/bin/ycrystal --check-renderer
.venv/bin/ycrystal --check-renderer --povray /usr/bin/povray
```

`--povray` applies only to `--check-renderer`; that command does not read the path
saved by the GUI. Without the option it uses the environment, then `PATH`. A pass
prints `PASS: …`; a renderer failure prints `FAIL: …` and exits 1. The check creates
temporary files and removes the completed job. It launches POV-Ray, but no Qt window.

## Export an editable scene

**File ▸ Export POV-Ray…** writes `NAME.pov` and `NAME.ini` next to each other.
It works without POV-Ray installed. Existing files are replaced; the dialog checks
the `.pov` destination, but its companion `.ini` is replaced without another prompt.
The directory must already exist.

The `.pov` stores the orthographic camera, visible spheres, cell edges, textures,
and lights in Cartesian Å. The `.ini` stores output size, PNG options, antialiasing,
and the relative output name `NAME.png`. No include library is needed.

For the tutorial's exported files, run from the scene directory:

```bash
cd artifacts/first-figure
povray SrTiO3.ini
```

This produces or replaces `SrTiO3.png` there and retains the exported text files.
Keep the `.pov` and `.ini` together. If you change the output aspect in the `.ini`,
also regenerate the matching camera vectors; changing only dimensions can stretch
the exported view. GUI render jobs are prepared afresh and do not use edits made
to previously exported files.

## Render a PNG in the application

Set the toolbar width and transparency, then choose **Render ▸ Render PNG…**
(Ctrl+R) and a destination. The height follows the current viewport. Antialiasing
is always on in the GUI.

After a synchronous version query (up to 15 seconds) and scene preparation,
POV-Ray runs asynchronously through Qt's `QProcess`. The window stays responsive
during that render. Only one render can run at a time. There is no cancel button
yet; closing the window stops an active process after handling unsaved changes.

Each job uses a new system temporary directory named `ycrystal-job-*`, containing
`scene.pov`, `scene.ini`, and, on success, `scene.png`. Python copies the image to
the chosen destination via `DESTINATION.png.part`, then replaces the destination.
The GUI removes the job directory after handling the result, including failures.
The job files are not kept for editing; export a scene if you need them. A failed
copy can leave the `.part` file behind.

The finished PNG uses the same displayed atoms and framing. VTK's approximate
lighting can differ from POV-Ray's key/fill lighting. Viewport orientation axes
and selection highlights are omitted. Transparent background adds an alpha
channel rather than a white background.
