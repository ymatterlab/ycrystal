# Export and rendering

## Configure and check POV-Ray

On Linux Mint, install the distribution renderer with `sudo apt install povray`; on
macOS, `brew install povray`. The tested baseline is POV-Ray 3.7. In the GUI,
discovery uses the first source that is set:

1. **Render ▸ Set POV-Ray Executable…** (saved on this machine).
2. The `YCRYSTAL_POVRAY` environment variable.
3. `povray` on `PATH`.

An invalid configured path fails immediately; discovery does not fall back. Choose
the executable in the menu to replace a stale setting (`/usr/bin/povray` on Linux
Mint, `/opt/homebrew/bin/povray` with Homebrew on Apple silicon; `command -v povray`
prints it). GUI settings are separate from projects. On Linux they normally live in
`~/.config/Y-Matter Lab/Ycrystal.conf`, on macOS in
`~/Library/Preferences/com.y-matter-lab.Ycrystal.plist`.

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
POV-Ray at a reduced size — same aspect ratio and background as the output, without
antialiasing — and shows it in the **POV-Ray preview** dock. It is a real POV-Ray image
of the same scene, not an approximation.

**Resolution** in the dock sets the preview's width: **Small** (480 px, the default),
**Medium** (800 px), **Large** (1200 px), or **Custom** (type a width, 16–4000 px). The
height follows the output's aspect ratio, rounded to whole pixels: for a 3:2 output
480 × 320, 800 × 533, and 1200 × 800 px; for a 2:3 portrait output Small gives
480 × 720 px. The line below shows the actual preview size next to the final PNG size.
POV-Ray renders the preview at that size (it is not an enlarged small image), so higher
resolutions show more detail but take longer. A preview is never larger than the final
image; a very tall output is limited to 4000 px of preview height, and an extremely wide
or tall output keeps each side at least 16 px, so the shape is never distorted. The
resolution changes only the preview: the output size, camera, framing, materials, and
lighting stay as they are. The choice is a personal preference, remembered between
sessions and not stored in projects. Resizing the dock only rescales the shown image;
it never starts a render.

With **Update automatically** checked (the default; the choice is remembered), a new
preview starts shortly after each change to the view, scene, appearance, or output size.
Only one preview process runs at a time: a newer request cancels the running preview.
Every change increases a scene revision number; a preview that finishes for an older
revision, or for a resolution that has since changed, is discarded and the dock says so.
When the shown preview no longer matches the view or the resolution, the dock marks it
out of date; a new resolution then renders automatically if **Update automatically** is
on, or when you press **Preview**. Preview problems (for example POV-Ray not
found) appear in the dock, without a dialog.

## Render an image in the application (PNG, PDF, JPEG)

Choose **Render ▸ Render Image…** (Ctrl+R). One dialog sets the format, the size, and
the file; **Render** starts POV-Ray. The defaults (PNG at the output size from the
Render tab) give the same image as earlier versions. Antialiasing is always on in the
GUI.

| Format | What is written |
| --- | --- |
| PNG (`.png`) | The POV-Ray image unchanged (8-bit sRGB, alpha with a transparent background), with the resolution stored in the file. |
| PDF (`.pdf`) | One page of the physical size of the figure, containing the POV-Ray image at full resolution, losslessly compressed. A transparent background stays transparent. |
| JPEG (`.jpg`, `.jpeg`) | The POV-Ray image encoded once with the chosen **Quality** (1–100, default 95), with the resolution stored in the file. JPEG has no transparency: a transparent background becomes white. |

The PDF contains a raster image, like the PNG: it is **not** a vector drawing and does
not become sharper when enlarged. Choose the size and resolution the figure needs.

**Size.** Choose one of:

| Size | Width | Resolution | Pixels (3:2 frame) |
| --- | --- | --- | --- |
| Output size (Render panel) | Render tab width | any | for example 1200 × 800 |
| Single column | 85 mm | 600 dpi | 2008 × 1339 |
| Double column | 180 mm | 600 dpi | 4252 × 2835 |
| Custom | any, in px or mm | any | computed |

The publication sizes are common defaults, not the rule of a particular journal: check
the author guidelines and use **Custom** where they differ. Pixels are
`millimetres / 25.4 × dpi`, rounded to whole pixels. With **Keep the shape of the
output frame** (the default) the height follows the blue frame, so the image shows
exactly the framed area at any size. Unchecked, width and height are independent: the
image then shows a wider or narrower area at the same scale (the dialog says so);
nothing is ever stretched.

Editing a value of a preset switches to **Custom** and keeps the values. In millimetres,
changing the resolution keeps the physical size (more or fewer pixels); in pixels it
keeps the pixel size and changes only the stored resolution and the physical size. The
dialog shows the pixel size POV-Ray renders and the physical size. **Resolution (dpi)**
offers 300 and 600; any whole number from 1 to 100 000 can be typed. Images are limited
to 16–20 000 px per side and 150 megapixels, and PDF pages to 5080 mm (200 inches) per
side. The dialog remembers its settings until Ycrystal is closed.

POV-Ray always renders at the pixel size shown; a small image is never enlarged. The
render uses the current camera, structure, materials, and lighting; it does not change
the scene, the Render tab, or the project. PDF page sizes are whole PostScript points
(1/72 inch), so a page can differ from the exact physical size by up to 0.18 mm; the
image is centred on it without distortion. The PNG stores the resolution in whole
pixels per metre (600 dpi reads back as 599.999 dpi).

After a synchronous version query (up to 15 seconds) and scene preparation,
POV-Ray runs asynchronously through Qt's `QProcess`. The window stays responsive and
the status bar shows the progress in percent as POV-Ray reports it. Only one final
render runs at a time (a preview may run alongside it). **Cancel Render** in the
toolbar or the Render menu stops the final render, or a running preview when no final
render is active. A cancelled render leaves the destination untouched and shows no
error. A failed render shows an explanation; the next render starts normally. Closing
the window stops active processes after handling unsaved changes.

Each job uses a new system temporary directory named `ycrystal-job-*`, containing
`scene.pov`, `scene.ini`, and, on success, `scene.png`. Ycrystal writes the chosen
format to `DESTINATION.part` next to the destination, checks that the file is complete
and readable, and only then replaces the destination. If writing fails, an error
explains why, the `.part` file is removed, and an existing file of that name is left
unchanged. The GUI removes the job directory after handling the result, including
failures and cancellations. The job files are not kept for editing; export a scene if
you need them.

The finished image uses the same displayed atoms, bonds, and framing as the preview and
the frame in the live view. The live view uses the same key and fill light positions,
but its shading is approximate and it has no shadows or reflections (see
[lighting](appearance.md#lighting)). Viewport orientation axes, the frame, and selection highlights are
omitted. A transparent background adds an alpha channel; transparent materials let
part of it through.
