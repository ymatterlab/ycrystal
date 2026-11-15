"""Write a POV-Ray 3.7 scene (.pov) and render settings (.ini) from the shared scene.

The camera is written with explicit ``location``/``direction``/``right``/``up``
vectors taken from [`Camera`][ycrystal.core.camera.Camera]; ``look_at`` and ``sky`` are
not used, so POV-Ray does not re-derive the basis or flip handedness. Coordinates are
the original right-handed world coordinates in ångström, which keeps the scene
readable and editable.

Scenes use only POV-Ray 3.7 language features (``#version 3.7;``) and no ``#include``
files. Colours are written as sRGB values and converted to linear light inside the
scene (``assumed_gamma 1.0``); the ``.ini`` file writes the PNG with sRGB gamma. The
writer produces text only; running POV-Ray is the job of
[`ycrystal.render.jobs`][ycrystal.render.jobs].
"""

from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from ycrystal import __version__
from ycrystal.core.camera import Camera
from ycrystal.core.scene import RGB, DisplayGeometry, Environment

POV_LANGUAGE_VERSION = "3.7"
"""POV-Ray scene-language version declared in every scene (``#version 3.7;``)."""


@dataclass(frozen=True)
class RenderSettings:
    """Output image settings for an exported or rendered scene.

    Presentation state only. The aspect ratio ``width / height`` decides how much of
    the scene is visible horizontally (see
    [`Camera.visible_size`][ycrystal.core.camera.Camera.visible_size]); the image is
    never stretched.

    Attributes
    ----------
    width
        Image width in pixels.
    height
        Image height in pixels. The GUI derives it from the width and the viewport's
        aspect ratio.
    antialias
        Whether POV-Ray antialiases (adaptive sampling method 1, threshold 0.1, depth
        3, no jitter).
    transparent_background
        Whether the PNG gets an alpha channel with a fully transparent background
        instead of the environment's background colour.

    Raises
    ------
    ValueError
        If `width` or `height` is less than 1.
    """

    width: int = 1200
    height: int = 800
    antialias: bool = True
    transparent_background: bool = False

    def __post_init__(self) -> None:
        if self.width < 1 or self.height < 1:
            raise ValueError("render dimensions must be positive")


def _f(value: float) -> str:
    text = f"{value:.6f}".rstrip("0").rstrip(".")
    return "0" if text in ("-0", "") else text


def _v(vector: np.ndarray | tuple[float, ...]) -> str:
    return "<" + ", ".join(_f(float(c)) for c in vector) + ">"


def _srgb(color: RGB) -> str:
    return "Ycr_sRGB(" + ", ".join(f"{c:.4f}" for c in color) + ")"


def _identifier(element: str) -> str:
    return "Ycr_Texture_" + "".join(ch for ch in element if ch.isalnum())


def scene_to_pov(
    geometry: DisplayGeometry,
    camera: Camera,
    environment: Environment,
    settings: RenderSettings,
    *,
    title: str = "Ycrystal scene",
    renderer_note: str | None = None,
) -> str:
    """Return the text of a self-contained POV-Ray scene.

    Parameters
    ----------
    geometry
        Atoms and cell edges to draw; hidden atoms are already absent from it.
    camera
        View to reproduce.
    environment
        Background colour and light intensities.
    settings
        Output size and background transparency. The size sets the camera's visible
        width and height; it should match the size in the ``.ini`` file.
    title
        Text of the first comment line.
    renderer_note
        Optional comment naming the renderer the scene was written for.

    Returns
    -------
    str
        The scene text. It needs no ``#include`` files.

    Notes
    -----
    The camera is orthographic, with ``direction`` set to the unit viewing direction
    and ``right`` and ``up`` set to the screen vectors scaled to the visible width and
    height in Å. Its ``location`` lies on the line through the focal point along the
    viewing direction, at the camera's distance or farther back when needed to keep
    every sphere and cell edge in front of the eye; under orthographic projection this
    does not change the image.

    Lights sit on the viewer's side at a distance that grows with the scene: the key
    light at the upper left and a shadowless fill light at the lower right; a light
    with non-positive intensity is omitted. Each element gets one texture (pigment
    from its first displayed colour, a shared finish). Each atom is a ``sphere`` with
    a comment giving its 1-based source atom number, element, and image offset; a comment states how
    many atoms are hidden. Cell edges are cylinders with spheres at the corners, marked
    ``no_shadow``.

    The header records the generation time (UTC), so two exports of the same scene
    differ in that line.
    """
    right, up, direction = camera.basis()
    world_w, world_h = camera.visible_size(settings.width, settings.height)
    focal = np.asarray(camera.focal_point)
    center, radius = geometry.bounding_sphere()

    # The orthographic eye must lie in front of everything drawn.
    points, radii = geometry.points_and_radii()
    depth_needed = float(np.max(-((points - focal) @ direction) + radii)) if len(points) else 0.0
    eye_distance = max(camera.distance, depth_needed + 1.0)
    location = focal - eye_distance * direction

    light_distance = 4.0 * radius + float(np.linalg.norm(center - focal)) + 10.0
    key_pos = focal + light_distance * _unit(-0.55 * right + 0.75 * up - 1.0 * direction)
    fill_pos = focal + light_distance * _unit(0.70 * right - 0.25 * up - 1.0 * direction)

    lines: list[str] = []
    add = lines.append
    stamp = _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    add(f"// {title}")
    add(f"// Generated by Ycrystal {__version__} on {stamp}.")
    if renderer_note:
        add(f"// Renderer used: {renderer_note}")
    add("// Units: angstrom; right-handed world coordinates (unchanged from the structure).")
    add(f"// Image: {settings.width} x {settings.height} px; render with the matching .ini file.")
    add("// No #include files are required.")
    add("")
    add(f"#version {POV_LANGUAGE_VERSION};")
    add("global_settings { assumed_gamma 1.0 }")
    add("")
    add("// Colours below are written as sRGB values and converted to linear light.")
    add(
        "#declare Ycr_Linear = function(c) { select(c - 0.04045, c / 12.92, "
        "pow((c + 0.055) / 1.055, 2.4)) }"
    )
    add("#macro Ycr_sRGB(R, G, B) rgb <Ycr_Linear(R), Ycr_Linear(G), Ycr_Linear(B)> #end")
    add("")
    add("// Orthographic camera. right/up lengths are the visible width/height (angstrom).")
    add("camera {")
    add("  orthographic")
    add(f"  location  {_v(location)}")
    add(f"  direction {_v(direction)}")
    add(f"  right     {_v(right * world_w)}")
    add(f"  up        {_v(up * world_h)}")
    add("}")
    add("")
    if settings.transparent_background:
        add("background { color rgbt <0, 0, 0, 1> }  // transparent (Output_Alpha=on)")
    else:
        add(f"background {{ color {_srgb(environment.background)} }}")
    add("")
    add("// Lights are placed relative to the camera (upper-left key, lower-right fill).")
    if environment.key_light > 0:
        add(f"light_source {{ {_v(key_pos)} color rgb {_f(environment.key_light)} }}")
    if environment.fill_light > 0:
        add(f"light_source {{ {_v(fill_pos)} color rgb {_f(environment.fill_light)} shadowless }}")
    add("")
    add("#declare Ycr_Finish_Default = finish {")
    add("  ambient 0.08 diffuse 0.75 specular 0.35 roughness 0.02")
    add("}")
    textures: dict[str, RGB] = {}
    for element, color in zip(geometry.elements, geometry.colors, strict=True):
        textures.setdefault(element, (float(color[0]), float(color[1]), float(color[2])))
    for element, color in textures.items():
        add(f"#declare {_identifier(element)} = texture {{")
        add(f"  pigment {{ color {_srgb(color)} }}")
        add("  finish { Ycr_Finish_Default }")
        add("}")
    add(
        f"#declare Ycr_Texture_Cell = texture {{ pigment {{ color "
        f"{_srgb(geometry.cell_edge_color)} }} finish {{ Ycr_Finish_Default }} }}"
    )
    add("")
    add(f"// Atoms ({len(geometry)}): source atom number (1-based, input order) and periodic image")
    if geometry.hidden_count:
        add(f"// ({geometry.hidden_count} atoms hidden in Ycrystal are not written.)")
    for atom_id, element, pos, rad in zip(
        geometry.atom_ids, geometry.elements, geometry.positions, geometry.radii, strict=True
    ):
        source, image = atom_id
        add(
            f"sphere {{ {_v(pos)}, {_f(float(rad))} texture {{ {_identifier(element)} }} }}"
            f"  // atom #{source + 1} {element} image {image}"
        )
    if len(geometry.cell_edges):
        add("")
        add("// Unit-cell edges (no_shadow: edges do not darken atoms).")
        r_edge = _f(geometry.cell_edge_radius)
        corners: list[np.ndarray] = []
        for start, end in geometry.cell_edges:
            add(
                f"cylinder {{ {_v(start)}, {_v(end)}, {r_edge} texture {{ Ycr_Texture_Cell }} "
                "no_shadow }"
            )
            for point in (start, end):
                if not any(np.allclose(point, c) for c in corners):
                    corners.append(point)
        for corner in corners:
            add(f"sphere {{ {_v(corner)}, {r_edge} texture {{ Ycr_Texture_Cell }} no_shadow }}")
    add("")
    return "\n".join(lines)


def render_ini(settings: RenderSettings, pov_name: str, image_name: str) -> str:
    """Return the text of a POV-Ray ``.ini`` file for one scene.

    Every option that affects the output is set explicitly, so defaults from a user or
    system ``povray.ini`` (for example ``Display=On``) cannot change the result.

    Parameters
    ----------
    settings
        Image size, antialiasing, and background transparency.
    pov_name
        Scene file name, relative to the directory in which POV-Ray runs. Double
        quotes are removed.
    image_name
        Output PNG name, relative to the same directory. Double quotes are removed.

    Returns
    -------
    str
        The ``.ini`` text: PNG output with 8 bits per channel and sRGB gamma, alpha
        only for transparent backgrounds, ``Quality=9``, the requested size and
        antialiasing, and no display window, pause, or verbose output.
    """

    def quoted(name: str) -> str:
        return '"' + name.replace('"', "") + '"'

    lines = [
        "; Ycrystal render settings. Run from this directory:  povray <this file>",
        f"Input_File_Name={quoted(pov_name)}",
        f"Output_File_Name={quoted(image_name)}",
        "Output_to_File=on",
        "Output_File_Type=N",
        "Bits_Per_Color=8",
        "File_Gamma=sRGB",
        f"Output_Alpha={'on' if settings.transparent_background else 'off'}",
        f"Width={settings.width}",
        f"Height={settings.height}",
        "Quality=9",
        f"Antialias={'on' if settings.antialias else 'off'}",
        "Sampling_Method=1",
        "Antialias_Threshold=0.1",
        "Antialias_Depth=3",
        "Jitter=off",
        "Display=off",
        "Pause_When_Done=off",
        "Verbose=off",
        "",
    ]
    return "\n".join(lines)


def write_scene_files(
    directory: Path,
    basename: str,
    geometry: DisplayGeometry,
    camera: Camera,
    environment: Environment,
    settings: RenderSettings,
    **kwargs: str,
) -> tuple[Path, Path, Path]:
    """Write a scene file and its ``.ini`` file into a directory.

    Parameters
    ----------
    directory
        Existing directory for both files.
    basename
        File name without suffix. Spaces and non-ASCII characters are supported;
        avoid double quotes because the INI writer removes them from file names.
    geometry
        Atoms and cell edges to draw.
    camera
        View to reproduce.
    environment
        Background colour and light intensities.
    settings
        Output image settings.
    **kwargs
        Passed to [`scene_to_pov`][ycrystal.render.pov_writer.scene_to_pov]
        (``title``, ``renderer_note``).

    Returns
    -------
    pov_path : pathlib.Path
        ``directory / f"{basename}.pov"``.
    ini_path : pathlib.Path
        ``directory / f"{basename}.ini"``.
    image_path : pathlib.Path
        ``directory / f"{basename}.png"``, the output named in the ``.ini`` file. It is
        not created here.

    Raises
    ------
    OSError
        If a file cannot be written, for example because `directory` does not exist.

    Notes
    -----
    Both files are written as UTF-8 and replace existing files of the same name without
    asking. The ``.ini`` file refers to the scene and the image by relative names, so
    run ``povray basename.ini`` with `directory` as the working directory. The I/O
    restrictions of the Ubuntu and Linux Mint ``povray`` package also allow writing
    the image only there (or under ``/tmp``).
    """
    directory = Path(directory)
    pov_path = directory / f"{basename}.pov"
    ini_path = directory / f"{basename}.ini"
    image_path = directory / f"{basename}.png"
    pov_path.write_text(
        scene_to_pov(geometry, camera, environment, settings, **kwargs), encoding="utf-8"
    )
    ini_path.write_text(render_ini(settings, pov_path.name, image_path.name), encoding="utf-8")
    return pov_path, ini_path, image_path


def _unit(vector: np.ndarray) -> np.ndarray:
    return vector / np.linalg.norm(vector)
