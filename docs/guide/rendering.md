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

The `.pov` stores the orthographic camera of the output frame, visible spheres,
bonds, cell edges, the material declarations, the background (with floor and backdrop),
and lights in Cartesian Å. Its header records the Ycrystal version, the POV-Ray version
found at export time (or that none was found), and the standard include files the
materials need (none for Ycrystal's own recipes). Comments record the environment and
lighting parameters and the native identifiers of each material. The `.ini` stores
output size, PNG options, antialiasing, alpha for a
transparent background, and the relative output name `NAME.png`. It sets
`Verbose=on`, so a manual render prints progress lines.

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

## Output size and frame

Set the image size in the **Scene ▸ Render** tab: **Width** and **Height** in pixels
(16 to 8000), an **Aspect** preset (1:1, 4:3, 3:2, 16:10, 16:9, and portrait 3:4 and
2:3) that sets the height from the width, and **Swap** for portrait/landscape. The
toolbar shows the current size.

### Lock aspect ratio

The padlock button beside Width and Height keeps the shape of the image while you change
its resolution, as in Inkscape. It is locked by default (closed padlock, pressed button);
click it or press Space when it has the keyboard focus to unlock (open padlock). The
tooltip states the current state and the locked ratio.

- **Locked**: Ycrystal keeps a target ratio *r* = Width ÷ Height. Changing Width sets
  Height = round(Width ÷ *r*); changing Height sets Width = round(Height × *r*). The value
  you typed is kept and the other is rounded to whole pixels; *r* itself is never
  recomputed from the rounded numbers, so repeated edits do not drift. From 2400 × 1600:
  Height 1920 gives 2880 × 1920, Width 3000 gives 3000 × 2000.
- **Unlocked**: Width and Height change independently (from 2400 × 1600, Height 1920
  gives 2400 × 1920). Locking again captures the ratio of the current size without
  changing it.
- **Aspect presets** keep the width and compute the height; when locked, the preset
  becomes the locked ratio, when unlocked it is applied once. The menu shows **Custom**
  when the size matches no preset.
- **Swap** exchanges Width and Height in one step; the lock stays as it was, and a locked
  ratio is inverted.
- If the computed dimension would fall outside 16–8000 px, the whole edit is refused:
  both values stay as they were and a message below the controls (and in the status bar)
  explains the limit. The lock is never broken silently.

Each edit, preset, or Swap is one undo step (consecutive size changes merge) and triggers
one automatic preview. Changing only the resolution keeps the composition: the camera,
rotation, pan, and zoom stay, and nothing is refitted. The lock state and the locked
ratio are saved in projects; projects from version 0.1.0 open locked to their own
ratio. Toggling the lock is not an undo step (it does not change the image), but it
marks the project as modified.

A blue frame in the 3D view shows exactly the area of the image; the region outside
it is dimmed. The frame is the largest rectangle with the output aspect ratio that
fits inside the view with a small margin. Fit (F), Reset View, and the view-along
buttons fit the structure into the frame. Changing the output size keeps the image
centre and its visible height in Å; only the width follows the new aspect ratio.
Resizing the window changes the frame on screen but not the image. Projects store the
camera of the output image together with its size, so a project reopens with the same
framing in a window of any shape.

## Materials and backgrounds

Materials (per default, element, or selected atom), element colours, backgrounds,
floors, and lighting are described in
[Materials, backgrounds, and lighting](appearance.md). Scenes that use native POV-Ray
identifiers such as `T_Gold_3C` include the standard POV-Ray files that declare them;
the export lists them and warns if one is not installed.

## POV-Ray preview

**Render ▸ Preview** (F5, or the **Preview** button) renders the framed view with
POV-Ray at a small size — 480 pixels on the longer side, same aspect ratio and
background as the output, without antialiasing — and shows it in the **POV-Ray
preview** dock. It is a real POV-Ray image of the same scene, not an approximation.

With **Update automatically** checked (the default; the choice is remembered), a new
preview starts shortly after each change to the view, scene, appearance, or output size.
Only one preview process runs at a time: a newer request cancels the running preview.
Every change increases a scene revision number; a preview that finishes for an older
revision is discarded and the dock says so. When the shown preview no longer matches
the view, the dock marks it out of date. Preview problems (for example POV-Ray not
found) appear in the dock, without a dialog.

## Render a PNG in the application

Choose **Render ▸ Render PNG…** (Ctrl+R) and a destination. The image has the output
size from the Render tab and shows exactly the framed area. Antialiasing is always on
in the GUI.

After a synchronous version query (up to 15 seconds) and scene preparation,
POV-Ray runs asynchronously through Qt's `QProcess`. The window stays responsive and
the status bar shows the progress in percent as POV-Ray reports it. Only one final
render runs at a time (a preview may run alongside it). **Cancel Render** in the
toolbar or the Render menu stops the final render, or a running preview when no final
render is active. A cancelled render leaves the destination untouched and shows no
error. A failed render shows an explanation; the next render starts normally. Closing
the window stops active processes after handling unsaved changes.

Each job uses a new system temporary directory named `ycrystal-job-*`, containing
`scene.pov`, `scene.ini`, and, on success, `scene.png`. Python copies the image to
the chosen destination via `DESTINATION.png.part`, then replaces the destination.
The GUI removes the job directory after handling the result, including failures and
cancellations. The job files are not kept for editing; export a scene if you need
them. A failed copy can leave the `.part` file behind.

The finished PNG uses the same displayed atoms, bonds, and framing as the preview and
the frame in the live view. The live view uses the same key and fill light positions,
but its shading is approximate and it has no shadows or reflections (see
[lighting](appearance.md#lighting)). Viewport orientation axes, the frame, and selection highlights are
omitted. A transparent background adds an alpha channel; transparent materials let
part of it through.
