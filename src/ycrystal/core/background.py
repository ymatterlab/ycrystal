"""Image backgrounds: the stored reference and the framing arithmetic (FR-BGIMAGE-01).

A [`BackgroundImage`][ycrystal.core.background.BackgroundImage] is part of an
[`Environment`][ycrystal.core.scene.Environment]. It names an imported picture by its
content identity (the SHA-256 of the stored bytes, see
[`ycrystal.io.images`][ycrystal.io.images]) and records how the picture is framed. It
holds no pixels and no file path, so environments stay small, comparable, and
independent of where the original file was.

Framing is defined relative to the output frame, never to a widget or a pixel size:
lengths are in units of the frame height (the frame is ``aspect`` wide and 1 high, with
its centre at the origin, x to the right and y up).
[`placement`][ycrystal.core.background.placement] is the single implementation used by
the POV-Ray writer and the tests.

Examples
--------
>>> from ycrystal.core.background import placement
>>> placement(400, 300, frame_aspect=1.5, fit="fill")  # 4:3 picture fills a 3:2 frame
(0.0, 0.0, 1.5, 1.125)
>>> placement(400, 300, frame_aspect=1.5, fit="fit")  # fits: full height, side margins
(0.0, 0.0, 1.3333333333333333, 1.0)
>>> placement(400, 300, 1.5, "fit", zoom=0.5, offset_x=0.25, offset_y=-0.1)
(0.375, -0.1, 0.6666666666666666, 0.5)
"""

from __future__ import annotations

import math
from dataclasses import dataclass

FIT_MODES = ("fill", "fit")
"""``"fill"`` covers the whole frame (cropping the picture as needed); ``"fit"`` shows
the whole picture inside the frame (with margins in the background colour)."""

IMAGE_FORMATS = ("png", "jpeg")
"""Stored picture formats (as written into the POV-Ray ``image_map``)."""

ZOOM_RANGE = (0.1, 10.0)
"""Allowed zoom factors relative to the fitted or filled size."""

OFFSET_RANGE = (-1.0, 1.0)
"""Allowed offsets, in fractions of the frame width (x) and height (y)."""

BRIGHTNESS_RANGE = (0.0, 2.0)
"""Allowed brightness factors (1 shows the picture's colours unchanged)."""

RGB = tuple[float, float, float]


@dataclass(frozen=True)
class BackgroundImage:
    """An imported picture used as background, and its framing.

    Attributes
    ----------
    asset
        Content identity of the stored picture: 64 lowercase hexadecimal digits (the
        SHA-256 of its bytes).
    name
        File name the picture was imported from (shown to the user; never opened
        again).
    width, height
        Size of the stored picture in pixels, after EXIF orientation.
    format
        ``"png"`` or ``"jpeg"``.
    mean_color
        Average colour (sRGB, 0–1) of the opaque pixels; the live 3D view shows it
        instead of the picture.
    fit
        One of [`FIT_MODES`][ycrystal.core.background.FIT_MODES].
    zoom
        Size relative to the fitted (or filled) size, within
        [`ZOOM_RANGE`][ycrystal.core.background.ZOOM_RANGE].
    offset_x, offset_y
        Shift of the picture's centre from the frame centre, in fractions of the frame
        width and height (positive: right and up), within
        [`OFFSET_RANGE`][ycrystal.core.background.OFFSET_RANGE].
    brightness
        Factor on the picture's linear colours, within
        [`BRIGHTNESS_RANGE`][ycrystal.core.background.BRIGHTNESS_RANGE].

    Raises
    ------
    ValueError
        For an invalid identity, size, format, mode, or a value outside its range.
    """

    asset: str
    name: str
    width: int
    height: int
    format: str = "png"
    mean_color: RGB = (0.5, 0.5, 0.5)
    fit: str = "fill"
    zoom: float = 1.0
    offset_x: float = 0.0
    offset_y: float = 0.0
    brightness: float = 1.0

    def __post_init__(self) -> None:
        if len(self.asset) != 64 or any(c not in "0123456789abcdef" for c in self.asset):
            raise ValueError("background image asset must be a SHA-256 hex digest")
        if int(self.width) < 1 or int(self.height) < 1:
            raise ValueError("background image size must be positive")
        object.__setattr__(self, "width", int(self.width))
        object.__setattr__(self, "height", int(self.height))
        if self.format not in IMAGE_FORMATS:
            raise ValueError(f"background image format must be one of {IMAGE_FORMATS}")
        if self.fit not in FIT_MODES:
            raise ValueError(f"background image fit must be one of {FIT_MODES}")
        rgb = tuple(float(c) for c in self.mean_color)
        if len(rgb) != 3 or not all(0.0 <= c <= 1.0 for c in rgb):
            raise ValueError("background image mean colour components must be between 0 and 1")
        object.__setattr__(self, "mean_color", rgb)
        for name, (low, high) in (
            ("zoom", ZOOM_RANGE),
            ("offset_x", OFFSET_RANGE),
            ("offset_y", OFFSET_RANGE),
            ("brightness", BRIGHTNESS_RANGE),
        ):
            value = float(getattr(self, name))
            if not (math.isfinite(value) and low <= value <= high):
                raise ValueError(f"background image {name} must be between {low} and {high}")
            object.__setattr__(self, name, value)

    def reset_framing(self) -> BackgroundImage:
        """Return the same picture with default framing (Fill, zoom 1, centred, brightness 1)."""
        return BackgroundImage(
            self.asset, self.name, self.width, self.height, self.format, self.mean_color
        )


def placement(
    width: int,
    height: int,
    frame_aspect: float,
    fit: str = "fill",
    zoom: float = 1.0,
    offset_x: float = 0.0,
    offset_y: float = 0.0,
) -> tuple[float, float, float, float]:
    """Return where a picture lies in the output frame: ``(cx, cy, w, h)``.

    Lengths are in units of the frame height; the frame spans ``±aspect/2`` in x and
    ``±1/2`` in y around its centre. The picture keeps its aspect ratio: ``"fit"``
    makes it as large as possible inside the frame, ``"fill"`` as small as possible
    while covering the frame; then `zoom` scales it about its centre, and the offsets
    move its centre by fractions of the frame width and height.

    Parameters
    ----------
    width, height
        Picture size in pixels.
    frame_aspect
        Output width / height.
    fit, zoom, offset_x, offset_y
        As in [`BackgroundImage`][ycrystal.core.background.BackgroundImage].

    Returns
    -------
    tuple of float
        Centre ``(cx, cy)`` and size ``(w, h)`` of the picture, with ``w / h`` equal to
        ``width / height``.
    """
    if width < 1 or height < 1 or not frame_aspect > 0:
        raise ValueError("picture size and frame aspect must be positive")
    if fit not in FIT_MODES:
        raise ValueError(f"fit must be one of {FIT_MODES}")
    ratio = width / height
    wider = ratio >= frame_aspect
    if (fit == "fit") == wider:  # fit a wide picture, or fill with a tall one: full width
        w, h = frame_aspect, frame_aspect / ratio
    else:
        w, h = ratio, 1.0
    return (offset_x * frame_aspect, offset_y, w * zoom, h * zoom)
