"""Output-size arithmetic with an optional locked aspect ratio (FR-RENDER-01).

The Render panel keeps a *target ratio* ``r = width / height``. While the ratio is
locked, editing one dimension computes the other from ``r`` in whole pixels; ``r``
itself is kept across edits and never recomputed from the rounded dimensions, so
repeated edits do not drift. These functions hold that arithmetic without Qt, so the
panel, the window, and the tests share one implementation.

Examples
--------
>>> from ycrystal.core.aspect import linked_size, swapped
>>> ratio = 2400 / 1600
>>> linked_size("height", 1920, (2400, 1600), ratio, locked=True)
(2880, 1920)
>>> linked_size("width", 3000, (2400, 1600), ratio, locked=True)
(3000, 2000)
>>> linked_size("height", 1920, (2400, 1600), ratio, locked=False)
(2400, 1920)
>>> swapped((2400, 1600), ratio)
((1600, 2400), 0.6666666666666666)

The POV-Ray preview has its own size (FR-PREVIEW-01): a chosen width, and the height
that keeps the output's shape.

>>> from ycrystal.core.aspect import preview_size
>>> [preview_size((2400, 1600), width)[:2] for width in (480, 800, 1200)]
[(480, 320), (800, 533), (1200, 800)]
>>> preview_size((1600, 2400), 480)[:2]
(480, 720)
>>> preview_size((640, 480), 1200)
PreviewSize(width=640, height=480, requested=1200, limit='output')
"""

from __future__ import annotations

import math
from typing import NamedTuple

MIN_OUTPUT_PIXELS = 16
"""Smallest width or height of an output image, in pixels."""

MAX_OUTPUT_PIXELS = 8000
"""Largest width or height of an output image, in pixels."""

Size = tuple[int, int]


class OutputSizeError(ValueError):
    """An edit would put a dimension outside the pixel limits; ``str()`` explains it."""


def round_pixels(value: float) -> int:
    """Round half up to a whole number of pixels (``2.5`` → 3, unlike ``round``)."""
    return int(math.floor(value + 0.5))


def matches_ratio(size: Size, ratio: float) -> bool:
    """Return whether ``size`` is what the lock would produce from either dimension.

    True when ``height == round(width / ratio)`` or ``width == round(height × ratio)``,
    i.e. the pixel pair is consistent with the target ratio up to rounding.
    """
    width, height = size
    return round_pixels(width / ratio) == height or round_pixels(height * ratio) == width


def _check(size: Size, edited: str, value: int) -> Size:
    width, height = size
    pairs = [("Width", width), ("Height", height)]
    pairs.sort(key=lambda pair: pair[0].lower() != edited)  # report the edited one first
    for name, pixels in pairs:
        if not MIN_OUTPUT_PIXELS <= pixels <= MAX_OUTPUT_PIXELS:
            limit = MAX_OUTPUT_PIXELS if pixels > MAX_OUTPUT_PIXELS else MIN_OUTPUT_PIXELS
            bound = "at most" if pixels > MAX_OUTPUT_PIXELS else "at least"
            raise OutputSizeError(
                f"{name} would be {pixels} px with {edited} {value} px and the locked "
                f"ratio; it must be {bound} {limit} px. The size was not changed."
                if name.lower() != edited
                else f"{name} must be between {MIN_OUTPUT_PIXELS} and {MAX_OUTPUT_PIXELS} px."
            )
    return size


def linked_size(edited: str, value: int, size: Size, ratio: float, locked: bool) -> Size:
    """Return the size after editing one dimension.

    Parameters
    ----------
    edited
        ``"width"`` or ``"height"``: the dimension the user changed.
    value
        Its new value in pixels; it is kept as given.
    size
        Current ``(width, height)``.
    ratio
        Target ratio ``width / height`` (used only when `locked`).
    locked
        Whether the ratio is locked.

    Returns
    -------
    tuple of int
        New ``(width, height)``: unlocked, only the edited dimension changes; locked,
        the other is ``round(width / ratio)`` or ``round(height × ratio)``.

    Raises
    ------
    OutputSizeError
        If either dimension would leave 16–8000 px; the caller keeps the old size.
    ValueError
        If `edited` is not ``"width"`` or ``"height"`` or `ratio` is not positive.
    """
    if edited not in ("width", "height"):
        raise ValueError("edited must be 'width' or 'height'")
    if not ratio > 0:
        raise ValueError("ratio must be positive")
    value = int(value)
    width, height = size
    if edited == "width":
        new = (value, round_pixels(value / ratio) if locked else height)
    else:
        new = (round_pixels(value * ratio) if locked else width, value)
    return _check(new, edited, value)


def preset_size(width: int, preset: float) -> Size:
    """Return ``(width, round(width / preset))`` for an aspect preset.

    Raises
    ------
    OutputSizeError
        If the height would leave 16–8000 px (the preset is not applied).
    """
    height = round_pixels(width / preset)
    if not MIN_OUTPUT_PIXELS <= height <= MAX_OUTPUT_PIXELS:
        bound = MAX_OUTPUT_PIXELS if height > MAX_OUTPUT_PIXELS else MIN_OUTPUT_PIXELS
        raise OutputSizeError(
            f"This aspect ratio would need a height of {height} px at width {width} px "
            f"(limit {bound} px). Change the width first. The size was not changed."
        )
    return (int(width), height)


def swapped(size: Size, ratio: float) -> tuple[Size, float]:
    """Return the exchanged size and the inverted target ratio (``1 / ratio``)."""
    width, height = size
    return (height, width), 1.0 / ratio


PREVIEW_PRESETS: tuple[tuple[str, str, int], ...] = (
    ("small", "Small", 480),
    ("medium", "Medium", 800),
    ("large", "Large", 1200),
)
"""Preview resolution presets: ``(key, label, width in pixels)``; the fourth choice is
``"custom"``, a width the user enters."""

DEFAULT_PREVIEW = "small"
"""Preset used until the user chooses one (480 px wide, the size of earlier versions
for landscape outputs)."""

MIN_PREVIEW_PIXELS = 16
"""Smallest preview width or height, in pixels (as for the output)."""

MAX_PREVIEW_PIXELS = 4000
"""Largest preview width that can be requested, and largest preview height, in pixels."""


class PreviewSize(NamedTuple):
    """Size of a POV-Ray preview.

    Returned by [`preview_size`][ycrystal.core.aspect.preview_size].

    Attributes
    ----------
    width, height
        Pixels POV-Ray renders.
    requested
        The width that was asked for.
    limit
        Why the size differs from the request: ``None`` (it does not), ``"output"``
        (never larger than the output image), ``"maximum"`` (the height would exceed
        `MAX_PREVIEW_PIXELS`), or ``"minimum"`` (a side would be under
        `MIN_PREVIEW_PIXELS`).
    """

    width: int
    height: int
    requested: int
    limit: str | None = None


def preview_size(output: Size, requested_width: int) -> PreviewSize:
    """Return the preview size for a requested width and the output image's shape.

    The height is ``round(width × output height / output width)``, half up, so the
    preview shows the same frame as the final image (rounding moves its edges by less
    than half a preview pixel). The result is never larger than the output. A portrait
    output whose height would exceed `MAX_PREVIEW_PIXELS` is scaled down to that height,
    and an extreme shape whose short side would be under `MIN_PREVIEW_PIXELS` is scaled
    up to it (at most to the output size), so the shape is never distorted.

    Parameters
    ----------
    output
        Output image ``(width, height)`` in pixels.
    requested_width
        Preview width in pixels, `MIN_PREVIEW_PIXELS` to `MAX_PREVIEW_PIXELS`.

    Returns
    -------
    PreviewSize
        Width, height, the request, and the reason for any limit.

    Raises
    ------
    ValueError
        If `requested_width` is outside the limits or the output size is not positive.
    """
    out_w, out_h = (int(v) for v in output)
    requested = int(requested_width)
    if out_w < 1 or out_h < 1:
        raise ValueError("the output size must be positive")
    if not MIN_PREVIEW_PIXELS <= requested <= MAX_PREVIEW_PIXELS:
        raise ValueError(
            f"The preview width must be between {MIN_PREVIEW_PIXELS} and {MAX_PREVIEW_PIXELS} px."
        )
    limit = None
    if requested >= out_w:
        width, height = out_w, out_h
        limit = "output" if requested > out_w else None
    else:
        width, height = requested, round_pixels(requested * out_h / out_w)
    if height > MAX_PREVIEW_PIXELS:
        width, height = round_pixels(MAX_PREVIEW_PIXELS * out_w / out_h), MAX_PREVIEW_PIXELS
        limit = "maximum"
    if min(width, height) < MIN_PREVIEW_PIXELS:
        side = min(MIN_PREVIEW_PIXELS, out_w, out_h)
        if out_w <= out_h:
            width, height = side, min(out_h, round_pixels(side * out_h / out_w))
        else:
            width, height = min(out_w, round_pixels(side * out_w / out_h)), side
        limit = "minimum"
    return PreviewSize(width, height, requested, limit)


def preview_preset_width(key: str) -> int:
    """Return the width of the preview preset ``key`` (``"small"``, ``"medium"``, ``"large"``).

    Raises
    ------
    KeyError
        For an unknown key (including ``"custom"``, which has no fixed width).
    """
    for preset, _label, width in PREVIEW_PRESETS:
        if preset == key:
            return width
    raise KeyError(key)
