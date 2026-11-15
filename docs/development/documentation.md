# Documentation workflow

Ycrystal uses a small Zensical + mkdocstrings-python site. Navigation separates user
guides, developer guides, and a curated source reference, inspired by
[quacc's documentation](https://github.com/Quantum-Accelerators/quacc/blob/main/_zensical.toml).
Signatures and parameter descriptions come from source rather than duplicate Markdown
tables. NumPy parsing is explicit, `allow_inspection = false` disables runtime import
fallback, and members are listed explicitly to avoid inherited Qt/VTK interfaces.

## Install, preview, and build

From the checkout root, add documentation tools to a development environment:

```bash
.venv/bin/python -m pip install -e ".[dev,docs]" -c constraints.txt -c docs/requirements.txt
.venv/bin/zensical serve
```

Open the local address printed by `serve` (normally `http://127.0.0.1:8000`). To build
the checked HTML into `site/`:

```bash
.venv/bin/zensical build --clean --strict
```

For a lightweight **documentation-only** environment, the application and its
Qt/VTK/ASE dependencies are unnecessary. Use the tested documentation lock:

```bash
/usr/bin/python3 -m venv .venv-docs
.venv-docs/bin/python -m pip install -r docs/requirements.txt
.venv-docs/bin/zensical serve
.venv-docs/bin/zensical build --clean --strict
```

`uv venv --python /usr/bin/python3.12 .venv-docs` and
`uv pip install --python .venv-docs/bin/python -r docs/requirements.txt` are equivalent.
Zensical statically reads `src/` through Griffe. A build must not create a
`QApplication`, window, OpenGL context, or renderer process. `site/`, `.cache/`, and
`.venv-docs/` are ignored. Do not commit generated HTML.

Strict builds reject warnings, broken local links/anchors, and unresolved reference
links. Use `--clean` in verification to avoid cached results. A dedicated docs CI
job uses this same build in a docs-only environment, alongside the existing lint and
application-test jobs. To update the documentation lock, resolve the two requirements
in the `docs` extra in a fresh docs-only Python 3.12 environment, freeze its packages
into `docs/requirements.txt`, and repeat the build and broken-reference probes.

## Writing docstrings

Use NumPy-style sections for meaningful public interfaces. Type annotations remain
the source of types: describe meaning, units, shape, defaults, valid values, copying,
and side effects in prose. Include only useful sections: summary, Parameters,
Returns/Yields, Raises, Attributes, Notes, Examples, and See Also. A one-line summary
is enough for a trivial method; do not add empty sections to callbacks or tests.

For a real example, read
[`Camera.project`](../reference/camera.md#ycrystal.core.camera.Camera.project): its
docstring explains Å inputs reshaped to `(K, 3)`, pixel dimensions, an output of
shape `(K, 2)`, the top-left origin, and the absence of clipping. The signature
supplies the annotations. Its class example projects the origin and unit x/y offsets
to exact pixels, demonstrating the contract rather than restating parameter names.

Use `Attributes` for data models and explain immutability precisely: `Structure`
copies arrays into read-only storage, but its metadata dictionary is mutable.
Describe failure results separately from exceptions and say who owns temporary
files. Keep scientific data changes distinct from presentation changes.

The NumPy convention and explicitly enabled Ruff `D` rules live in `pyproject.toml`.
Tests are exempt; GUI methods are exempt from mandatory method docstrings, while
their substantive interfaces are documented. Existing pre-commit hooks run Ruff.

For every interface or GUI behavior change, update its docstrings, relevant user
instructions, and executable examples **in the same change**. Verify against the
implementation and tests, and record discrepancies in `PROGRESS.md`; do not change
behavior just to fit the prose. Curate new API entries in `docs/reference/` and
`zensical.toml`. Do not expose private helpers or inherited Qt/VTK methods.

## Check examples

Display-independent docstring examples (requires the application dependencies,
not a display or POV-Ray):

```bash
.venv/bin/python -m doctest src/ycrystal/core/structure.py src/ycrystal/core/scene.py src/ycrystal/core/camera.py src/ycrystal/core/picking.py src/ycrystal/io/readers.py src/ycrystal/io/project.py src/ycrystal/presets/__init__.py src/ycrystal/render/jobs.py
.venv/bin/python scripts/docs_examples.py
.venv/bin/ruff check .
.venv/bin/ruff format --check .
```

Run these at the checkout root because the reader examples use `tests/fixtures/`.
The second command exercises scientific/display identities, projection, structure
import, project save/reopen, and POV text export; outputs use a temporary directory.
The [Python examples](examples.md) page separates these from renderer/GUI examples.
Run the existing application tests as documented in the contributor guide.

## Visual assets

`docs/assets/perovskite.png` is an actual POV-Ray render of the built-in sample,
not a UI mockup. It is intentionally tracked as a small documentation asset. From
the checkout root, regenerate it with application dependencies and POV-Ray installed:

```bash
.venv/bin/python scripts/docs_render_example.py
```

The script prepares the default 15-ball SrTiO3 geometry and default camera fitted
to 640 × 400, renders synchronously, copies the PNG to `docs/assets/perovskite.png`,
and removes its temporary job directory in `finally`. It replaces the asset without
asking. Use `--output artifacts/docs/perovskite.png` to inspect a candidate first;
`--povray /usr/bin/povray` overrides discovery. PNG bytes can vary with renderer
versions; inspect framing and appearance before committing. No display is needed.

For full-window screenshots and camera-alignment evidence, use the existing
`scripts/m0_evidence.py` on an X11/OpenGL desktop with POV-Ray. Those outputs stay
under ignored `artifacts/`. Do not present them as the tutorial's default view:
that script uses the triclinic sample and mouse navigation.

## Publication

The build is local and CI verification only. No website deployment is configured or
verified by this increment. To publish later, choose a host and canonical URL,
configure its base path/`site_url`, arrange upload of `site/` after a strict build,
and check navigation, API anchors, and assets at the deployed URL. Record that
verification separately before advertising a hosted site.
