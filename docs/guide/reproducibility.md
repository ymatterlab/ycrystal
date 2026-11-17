# Reproducible figures

**Why.** A figure in a paper should still be reproducible months later: by you, after
the structure file has moved and the style has changed, or by a colleague on another
computer. A PNG alone does not say how it was made. With `--save-project`, Ycrystal saves
two more files next to the image:

- a **snapshot**: the figure as an ordinary, self-contained `.ycrystal` project, with
  the camera and image size it was rendered with;
- a **provenance record**: a small JSON file stating which inputs, settings, and
  software versions made the image, with SHA-256 checksums of the files.

The snapshot needs neither the original structure file nor the style, its background
picture, or your personal materials. Rendering it again does not apply the style again
or refit the camera, so it gives the same scene.

## Save a figure with its snapshot

Add `--save-project` to a `--render` command. This example uses the files of the source
checkout (see [element mapping](examples.md#map-elements-to-another-composition) and
[views](examples.md#choose-the-view-and-framing)):

```bash
.venv/bin/ycrystal tests/fixtures/BaZrO3.cif --style examples/grey-studio.ycstyle --element-map Ti=Zr --view a --render figures/BaZrO3.png --save-project figures/BaZrO3.ycrystal
```

```text
Rendered figures/BaZrO3.png in 2.1 s
Saved figures/BaZrO3.ycrystal and figures/BaZrO3.provenance.json
```

| File | Contents |
| --- | --- |
| `figures/BaZrO3.png` | The image, exactly as `--render` alone would write it |
| `figures/BaZrO3.ycrystal` | The snapshot (see below) |
| `figures/BaZrO3.provenance.json` | The provenance record (same folder and name as the snapshot) |

The snapshot holds what was drawn:

- the structure in full (cell, coordinates, elements, labels), unchanged to the last
  digit, and any vectors of the input;
- the display settings and materials **after** the style and the element mapping were
  applied (here: Zr chrome, O ceramic). The mapping itself is not stored, its result is;
- the environment, with a background picture stored inside the file (it is then a ZIP
  package), and the definitions of any custom materials it uses;
- the output size and the camera actually used, here the view along a fitted to an
  800 × 600 image.

The structure's import record keeps the file name, format, and SHA-256 of the original
`BaZrO3.cif`, but not the folder it was in, so the snapshot does not reveal folder or
user names of your computer.

The image is rendered from the saved snapshot itself. The three files are written only
when POV-Ray has succeeded, the record last: if the render fails, none of them exists
afterwards, and no record ever describes an image that was not made.

## Render it again

```bash
.venv/bin/ycrystal figures/BaZrO3.ycrystal --render figures/BaZrO3-again.png
```

No other option is needed: the snapshot is drawn with its saved camera and size, like
any project (see [render without a window](examples.md#render-without-a-window)). The
record's `replay` entry gives the same command for its own folder,
`ycrystal BaZrO3.ycrystal --render BaZrO3.png`; render to another name if you want to
compare the two images. Options such as `--view` or `--width` still work on a snapshot,
but then they make a different figure. You can also open the snapshot in the window
(**File ▸ Open…**) and continue editing it.

To pass a figure on, send the snapshot (and the record, if wanted). The recipient needs
Ycrystal and POV-Ray 3.7 with its standard include files, nothing else.

## What is reproduced, and what is not

- **The scene, exactly.** Rendering the snapshot gives the same structure, settings,
  camera, and image size, so Ycrystal writes the same POV-Ray scene: the `.pov` and
  `.ini` files are identical except for the line with the date. The tests check this
  for structures and projects, styles with element mapping, fitted, saved, and
  fixed-height views, vectors, a background picture, and a custom material.
- **The pixels, on the same setup.** On the development laptop (Linux, POV-Ray
  3.7.0.10), every replay so far had exactly the same pixels as the original image
  (largest difference 0 of 255). The tests compare decoded pixels and allow a
  difference of 1 of 255 per channel.
- **Not the file bytes.** POV-Ray writes the render date and time into every PNG, so a
  re-rendered image never has the same SHA-256 as the original, even when every pixel
  is the same. Compare pixels, not checksums.
- **Not across systems, unless checked.** Another POV-Ray build, another operating
  system, or other versions of POV-Ray's standard include files may change pixels
  slightly. How much has not been measured yet.
- **What the snapshot does not contain:** POV-Ray and its standard include files
  (`textures.inc`, `metals.inc`, …). The record lists the include files the scene
  needs under `renderer.includes`. On Linux Mint and Ubuntu they come from the
  `povray-includes` package; Homebrew's `povray` contains them.

## The provenance record

An excerpt of `figures/BaZrO3.provenance.json`:

```json
{
 "format": "ycrystal-provenance",
 "schema_version": 1,
 "generator": "Ycrystal 0.4.0.dev0",
 "replay": "ycrystal BaZrO3.ycrystal --render BaZrO3.png",
 "image": {"name": "BaZrO3.png", "path": "BaZrO3.png", "sha256": "896f8581…", "bytes": 145288, "width": 800, "height": 600},
 "input": {"name": "BaZrO3.cif", "path": null, "sha256": "ccc0450b…", "bytes": 385, "format": "cif"},
 "style": {"name": "grey-studio.ycstyle", "path": null, "sha256": "bdfb2b3e…", "bytes": 1493,
           "parts": ["appearance", "environment", "output"], "element_map": {"Ti": "Zr"}},
 "camera": {"policy": "fit", "view": "a", "fit_margin": 0.06, "view_height": null, "projection": "orthographic", …},
 "renderer": {"name": "POV-Ray", "version": "3.7.0.10.unofficial", "includes": ["textures.inc"]},
 …
}
```

The entries, in the order they appear:

| Entry | Meaning |
| --- | --- |
| `format`, `schema_version` | `"ycrystal-provenance"`, schema 1 |
| `generator`, `created` | Ycrystal version; time the record was written (UTC) |
| `job` | Batch job id, or `null` for a single figure |
| `replay` | Command that renders the snapshot again, run in the record's folder |
| `image` | The PNG: `name`, `path`, `sha256`, `bytes`, and `width`, `height` as read from the file |
| `project` | The snapshot: `name`, `path`, `sha256`, `bytes`, and its project `schema_version` |
| `input` | The structure file or project the figure was made from, with its `format` |
| `style` | The style file, the `parts` applied, and the `element_map` (or `null`); `null` without a style |
| `manifest` | The batch manifest; `null` for a single figure |
| `structure` | `composition`, number of `atoms`, and `displayed_atoms` (with repetitions and boundary atoms) |
| `output` | The image size asked of POV-Ray, `antialias`, `transparent_background`, and the `width_option`/`height_option` given on the command line or in the manifest (`null` when not given) |
| `camera` | The camera `policy` (`saved` or `fit`), `view`, `fit_margin`, `view_height`, and the camera used, as stored in projects |
| `renderer` | POV-Ray `version` as reported by the executable, and the standard `includes` the scene needs |
| `system` | Operating system, machine, and the Python, NumPy, and ASE versions |
| `notes` | Warnings: what the style did not apply, an image of another size than asked, an unknown POV-Ray version |
| `reproducibility` | The statement of the previous section, in one sentence |

**Paths** are relative to the record's folder. Files outside that folder, usually the
input and the style, have `"path": null` and are identified by `name` and `sha256`.
The record contains no absolute paths, no user or computer name, and not the location
of the POV-Ray executable.

**Checking the files.** Compare a file's SHA-256 with the record:
`sha256sum figures/BaZrO3.png` on Linux, `shasum -a 256 figures/BaZrO3.png` on macOS. A
matching checksum shows that the file is the one the record describes. It does not show
that anyone reproduced the figure independently.

## Existing files and errors

- `--save-project` needs `--render` and a file name ending in `.ycrystal` (otherwise a
  usage error, status 2, and no window opens).
- An existing snapshot or record is not replaced unless you add `--overwrite`; the
  command then stops before rendering, with status 1:

  ```text
  ERROR: figures/BaZrO3.ycrystal exists; use --overwrite to replace it.
  ERROR: figures/BaZrO3.provenance.json exists; use --overwrite to replace it.
  ```

  `--render` itself still replaces an existing PNG, as before.
- The snapshot can never replace the input, the style, or the image (for example
  `ycrystal figure.ycrystal … --save-project figure.ycrystal`), not even with
  `--overwrite`.
- A folder that cannot be written, a missing POV-Ray, or a failed render is an error
  (status 1). Nothing is left behind, not even a folder created for the files.
- A missing or damaged snapshot is refused when you render it, with the reason (for
  example `is not valid project JSON`, or a damaged picture in the package).

## A series: `save_projects` in a batch manifest

In a [batch manifest](examples.md#render-a-series-from-a-manifest), the top-level
setting `"save_projects": true` saves a snapshot and a record for every rendered job,
next to its image: `SrTiO3.png`, `SrTiO3.ycrystal`, `SrTiO3.provenance.json`, and in a
subfolder for an output such as `vectors/afm.png`. For a manifest in the `examples/`
folder (paths are relative to the manifest):

```json
{
 "format": "ycrystal-batch",
 "schema_version": 1,
 "save_projects": true,
 "defaults": {"style": "grey-studio.ycstyle", "view": "a", "width": 600, "height": 450},
 "jobs": [
  {"id": "SrTiO3", "input": "../tests/fixtures/SrTiO3.cif"},
  {"id": "BaZrO3", "input": "../tests/fixtures/BaZrO3.cif", "element_map": {"Ti": "Zr"}}
 ]
}
```

- `--dry-run` lists the snapshots too:
  `SrTiO3: would render SrTiO3.png and save SrTiO3.ycrystal (600 × 450, 15 atoms)`.
- Each record also names its `job` and the `manifest` (name and SHA-256).
- The report `ycrystal-batch-report.json` names each job's snapshot and record under
  `project` and `provenance`, relative to the output folder; both are `null` for a job
  that failed, which writes neither.
- Existing snapshots and records are problems of the validation step, like existing
  images: nothing is rendered unless you add `--overwrite`. A snapshot that would
  replace an input, a style, or the manifest is always refused.

Without `save_projects` (or with `false`), a batch run writes exactly what it wrote
before.

## Limitations

- Snapshots are saved for PNG renders (`--render`, batch jobs) only; `--export-pov`
  alone saves none, and **Render Image…** in the window does not offer them. In the
  window, **File ▸ Save Project** saves a project, but without a provenance record.
- A snapshot is a project of the current schema (7); older Ycrystal versions that read
  an older schema refuse it with a message.
- Pixel differences between systems or POV-Ray builds have not been measured.
