# Install and launch

The integration baseline is Linux Mint 22.1 / Ubuntu 24.04 with the system Python
3.12, an X11 desktop, and working OpenGL. Other operating systems and Python versions
have not been verified. Ycrystal is installed from a source checkout at this stage.

## Linux Mint

```bash
sudo apt update
sudo apt install git povray povray-includes libxcb-cursor0 python3.12-venv
git clone https://github.com/ymatterlab/ycrystal.git
cd ycrystal
/usr/bin/python3 -m venv .venv
.venv/bin/python -m pip install -e . -c constraints.txt
.venv/bin/ycrystal
```

Use `/usr/bin/python3`: Miniconda/Anaconda's bundled `libstdc++` can prevent Mesa
from loading and cause “Could not initialize GLX”. `libxcb-cursor0` is needed by Qt
on X11. POV-Ray is optional for opening structures and exporting scenes, and required
for rendering PNGs. To install developer tools, use `-e ".[dev]"` instead of `-e .`.

If using `uv`, the equivalent environment setup is:

```bash
uv venv --python /usr/bin/python3.12 .venv
uv pip install --python .venv/bin/python -e . -c constraints.txt
```

## Launch options

Run these from the checkout root:

```bash
.venv/bin/ycrystal --sample perovskite
.venv/bin/ycrystal --sample triclinic
.venv/bin/ycrystal tests/fixtures/MgB2.cif
.venv/bin/ycrystal tests/fixtures/Si.pw.in --format qe
.venv/bin/ycrystal --check-renderer
.venv/bin/ycrystal --help
```

The default sample is cubic SrTiO3: 5 scientific atoms, displayed as 15 balls with
boundary images. The triclinic sample contains O, Fe, S, Cl, and N at general positions
in a skewed cell, so it shows 5 balls. Both are synthetic and require no downloaded
data. There is no sample chooser in the current GUI; choose one at launch.

A file argument opens after the window appears. If import fails, a message explains
why and the sample stays. **File ▸ Open…** (Ctrl+O) opens structures or projects;
**File ▸ Open As…** overrides format detection. The checkout's `tests/fixtures/`
contains small valid inputs and deliberate rejection cases; see
[supported formats](../FORMATS.md).

`--check-renderer` runs without a window or display and exits with status 0 for
`PASS`, 1 for `FAIL`. See [renderer setup](rendering.md#configure-and-check-pov-ray).
For documentation-only installation, see the [documentation workflow](../development/documentation.md).
