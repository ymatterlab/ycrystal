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
"""

from __future__ import annotations

import math

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
