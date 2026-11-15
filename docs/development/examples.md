# Python examples

These are evolving developer interfaces. Run from a source checkout with the
application dependencies installed; see the generated reference for detailed
parameter contracts. The documentation build itself executes none of these examples.

## Without a display or renderer

This is a short interactive example from the scene reference:

```pycon
>>> from ycrystal.core.samples import perovskite_srtio3
>>> from ycrystal.core.scene import SceneSettings, build_geometry
>>> structure = perovskite_srtio3()
>>> geometry = build_geometry(structure)
>>> len(structure), len(geometry)
(5, 15)
>>> corner = (0, (1, 1, 1))
>>> hidden = build_geometry(structure, SceneSettings(hidden=frozenset({corner})))
>>> len(hidden), hidden.hidden_count, hidden.index_of(corner)
(14, 1, None)
```

Scientific coordinates are unchanged. The arrays produced by `build_geometry` are
read-only, and the image offset is relative to input positions rather than wrapped
positions. See [scene and geometry](../reference/scene.md).

Execute the complete lightweight example with:

```bash
.venv/bin/python scripts/docs_examples.py
```

The [script](https://github.com/ymatterlab/ycrystal/blob/main/scripts/docs_examples.py)
also projects the focal point, imports `tests/fixtures/MgB2.cif`, saves/reopens a
project, and exports `.pov`/`.ini` text in a temporary directory. It checks the
expected outcomes and cleans its files. It does not import the viewport or run
POV-Ray. Source docstrings contain further runnable examples; see
[the doctest command](documentation.md#check-examples).

## With POV-Ray, without a display

```bash
.venv/bin/ycrystal --check-renderer --povray /usr/bin/povray
.venv/bin/python scripts/docs_render_example.py --output artifacts/docs/perovskite.png
```

The second command demonstrates the synchronous job lifecycle:
`prepare_job` → `run_job` → inspect `RenderResult.ok`/`message` → `copy_result` →
`job.cleanup()` in `finally`. The result's `image_path` is inside the temporary job
directory and becomes invalid on cleanup. Keep the copied destination instead.
Discovery and filesystem setup can raise; ordinary renderer failures return a
result. See [rendering reference](../reference/rendering.md).

## With a display and OpenGL

```bash
.venv/bin/ycrystal --sample perovskite
```

Follow the [first-figure tutorial](../guide/first-figure.md). Creating `MainWindow`
or `StructureViewport` needs `QApplication`, a display, and OpenGL. Asynchronous
`RenderProcess` needs a running Qt event loop but no window; it leaves job cleanup
to the caller. Its `finished` signal delivers one `RenderResult` for success or
failure. The GUI copies a successful result and then cleans the job.
