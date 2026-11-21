"""Element legend: which elements a figure shows, in which colours (FR-LEGEND-01).

The legend is a two-dimensional annotation drawn on top of the figure: one coloured
circle per chemical element followed by its symbol, in a row or a column. It is not part
of the three-dimensional scene. POV-Ray renders the structure as before, and Ycrystal
then paints the legend onto the rendered image at its full resolution
([`ycrystal.render.legend`][ycrystal.render.legend]); the live view shows the same
legend in its output frame.

This module holds the settings and the choice of entries, without Qt. The entries come
from the [`DisplayGeometry`][ycrystal.core.scene.DisplayGeometry] that both renderers
draw, so a marker has exactly the colour of the element's spheres: the element colour,
its override, or the colour of a material with its own pigment.

Sizes are relative, so that a preview, the output image, and an export at another pixel
size show the same legend: the text height is a percentage of the image height, and
marker size, spacing, and margin are multiples of the text height.

Examples
--------
>>> from ycrystal.core.legend import LegendSettings, legend_entries
>>> from ycrystal.core.samples import perovskite_srtio3
>>> from ycrystal.core.scene import SceneSettings, build_geometry
>>> geometry = build_geometry(perovskite_srtio3())
>>> [entry.element for entry in legend_entries(geometry, LegendSettings())]
['Sr', 'Ti', 'O']
>>> [e.element for e in legend_entries(geometry, LegendSettings(order="atomic_number"))]
['O', 'Ti', 'Sr']

A colour override changes the marker as it changes the spheres:

>>> red = SceneSettings().with_element_color("O", (1.0, 0.0, 0.0))
>>> legend_entries(build_geometry(perovskite_srtio3(), red), LegendSettings())[2]
LegendEntry(element='O', color=(1.0, 0.0, 0.0))
"""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from ase.data import atomic_numbers

if TYPE_CHECKING:  # scene.py imports this module for SceneSettings.legend
    from ycrystal.core.scene import DisplayGeometry

RGB = tuple[float, float, float]

LEGEND_LAYOUTS = ("horizontal", "vertical")
"""Arrangements of the entries: in one row, or in one column."""

LEGEND_POSITIONS = ("bottom", "top", "left", "right", "custom")
"""Places of the legend in the image. ``bottom`` and ``top`` centre it horizontally,
``left`` and ``right`` vertically, each at the margin from that edge; ``custom`` puts
its centre at the fractions ``x`` and ``y`` of the image width and height."""

LEGEND_ORDERS = ("structure", "atomic_number", "alphabetical", "custom")
"""Orders of the entries: first appearance in the structure's atom list, increasing
atomic number, alphabetical symbol, or a custom list (see
[`LegendSettings`][ycrystal.core.legend.LegendSettings])."""

MARKER_STYLES = ("sphere", "flat")
"""Marker looks: a shaded ball with a highlight, or a flat disc; both have a thin outline
in a darker shade of the colour, so that white elements stay visible on white."""

LEGEND_RANGES: dict[str, tuple[float, float]] = {
    "font_size": (0.5, 25.0),
    "marker_size": (0.2, 4.0),
    "spacing": (0.0, 10.0),
    "margin": (0.0, 20.0),
    "x": (0.0, 1.0),
    "y": (0.0, 1.0),
    "background_opacity": (0.0, 1.0),
}
"""Accepted ranges of the numeric settings, inclusive."""


@dataclass(frozen=True)
class LegendSettings:
    """Appearance and placement of the element legend (presentation only).

    Part of [`SceneSettings`][ycrystal.core.scene.SceneSettings] (its ``legend``) and
    saved in projects and styles. A disabled legend draws nothing, and the rendered
    image is exactly as without this feature.

    Attributes
    ----------
    enabled
        Whether the legend is drawn.
    layout
        One of [`LEGEND_LAYOUTS`][ycrystal.core.legend.LEGEND_LAYOUTS].
    position
        One of [`LEGEND_POSITIONS`][ycrystal.core.legend.LEGEND_POSITIONS].
    x, y
        Centre of the legend for the ``custom`` position, as fractions of the image
        width (from the left) and height (from the top). The legend is moved inside
        the image if it would cross an edge.
    font_family
        Font family of the symbols; empty for the default sans-serif family (the
        first installed of
        [`DEFAULT_FONT_FAMILIES`][ycrystal.render.legend.DEFAULT_FONT_FAMILIES]). A
        family that is not installed is replaced by a similar one.
    font_size
        Height of the text (the font's pixel size) in percent of the image height.
    text_color
        Colour of the symbols (sRGB, 0–1).
    marker_size
        Diameter of the circles in multiples of the text height.
    marker_style
        One of [`MARKER_STYLES`][ycrystal.core.legend.MARKER_STYLES].
    spacing
        Gap between neighbouring entries in multiples of the text height (between
        rows of a vertical legend).
    margin
        Gap between the legend and the image edge it is placed at, in multiples of
        the text height (not used for ``custom``).
    background
        Whether a rounded box is drawn behind the legend.
    background_color, background_opacity
        Colour (sRGB) and opacity (0 transparent, 1 opaque) of that box.
    order
        One of [`LEGEND_ORDERS`][ycrystal.core.legend.LEGEND_ORDERS].
    custom_order
        Element symbols in the order of the ``custom`` order. Elements of the figure
        that are not listed follow in structure order; listed elements that the figure
        does not show are ignored, so one list can serve several structures.

    Raises
    ------
    ValueError
        For unknown names, numbers outside
        [`LEGEND_RANGES`][ycrystal.core.legend.LEGEND_RANGES], colour components
        outside 0–1, or a custom order with an unknown or repeated element.
    """

    enabled: bool = False
    layout: str = "horizontal"
    position: str = "bottom"
    x: float = 0.5
    y: float = 0.9
    font_family: str = ""
    font_size: float = 5.0
    text_color: RGB = (0.0, 0.0, 0.0)
    marker_size: float = 0.9
    marker_style: str = "sphere"
    spacing: float = 1.0
    margin: float = 0.6
    background: bool = False
    background_color: RGB = (1.0, 1.0, 1.0)
    background_opacity: float = 0.85
    order: str = "structure"
    custom_order: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for name, allowed in (
            ("layout", LEGEND_LAYOUTS),
            ("position", LEGEND_POSITIONS),
            ("marker_style", MARKER_STYLES),
            ("order", LEGEND_ORDERS),
        ):
            if getattr(self, name) not in allowed:
                raise ValueError(f"legend {name} must be one of {allowed}")
        for name, (low, high) in LEGEND_RANGES.items():
            value = float(getattr(self, name))
            if not (math.isfinite(value) and low <= value <= high):
                raise ValueError(f"legend {name} must be between {low:g} and {high:g}")
            object.__setattr__(self, name, value)
        for name in ("text_color", "background_color"):
            rgb = tuple(float(c) for c in getattr(self, name))
            if len(rgb) != 3 or not all(0.0 <= c <= 1.0 for c in rgb):
                raise ValueError(f"legend {name} components must be between 0 and 1")
            object.__setattr__(self, name, rgb)
        order = tuple(str(e) for e in self.custom_order)
        unknown = [e for e in order if e not in atomic_numbers or e == "X"]
        if unknown:
            raise ValueError(f"unknown element in the legend order: {unknown[0]}")
        if len(set(order)) != len(order):
            raise ValueError("the legend order names an element twice")
        object.__setattr__(self, "custom_order", order)
        object.__setattr__(self, "font_family", str(self.font_family).strip())
        for name in ("enabled", "background"):
            object.__setattr__(self, name, bool(getattr(self, name)))


@dataclass(frozen=True)
class LegendEntry:
    """One line of the legend: an element symbol and its marker colour (sRGB, 0–1)."""

    element: str
    color: RGB


def order_elements(
    elements: Iterable[str], order: str = "structure", custom: Iterable[str] = ()
) -> list[str]:
    """Return distinct ``elements`` in a legend order.

    Parameters
    ----------
    elements
        Element symbols in structure order; repetitions are ignored.
    order
        One of [`LEGEND_ORDERS`][ycrystal.core.legend.LEGEND_ORDERS].
    custom
        For ``"custom"``: symbols that come first, in this order.

    Examples
    --------
    >>> order_elements(["Ru", "Sc", "Be", "Sc"], "atomic_number")
    ['Be', 'Sc', 'Ru']
    >>> order_elements(["Ru", "Sc", "Be"], "alphabetical")
    ['Be', 'Ru', 'Sc']
    >>> order_elements(["Ru", "Sc", "Be"], "custom", ["Sc", "Fe"])
    ['Sc', 'Ru', 'Be']
    """
    distinct = list(dict.fromkeys(elements))
    if order == "atomic_number":
        return sorted(distinct, key=lambda e: atomic_numbers[e])
    if order == "alphabetical":
        return sorted(distinct)
    if order == "custom":
        present = set(distinct)
        first = [e for e in dict.fromkeys(custom) if e in present]
        return first + [e for e in distinct if e not in first]
    if order != "structure":
        raise ValueError(f"legend order must be one of {LEGEND_ORDERS}")
    return distinct


def legend_entries(geometry: DisplayGeometry, settings: LegendSettings) -> tuple[LegendEntry, ...]:
    """Return the legend entries of the elements a geometry displays.

    Parameters
    ----------
    geometry
        The drawn geometry; hidden atoms are not part of it, so an element whose atoms
        are all hidden has no entry.
    settings
        Legend settings; only the order is used here (``enabled`` is not checked).

    Returns
    -------
    tuple of LegendEntry
        One entry per displayed element, in the order of `settings`. The colour is the
        one most of the element's spheres have (per-atom materials with their own
        pigment can give single atoms another colour); on a tie, the colour of the
        first such atom.
    """
    colors: dict[str, Counter[RGB]] = {}
    for element, rgb in zip(geometry.elements, geometry.colors, strict=True):
        key = (float(rgb[0]), float(rgb[1]), float(rgb[2]))
        colors.setdefault(element, Counter())[key] += 1
    ordered = order_elements(colors, settings.order, settings.custom_order)
    return tuple(LegendEntry(e, colors[e].most_common(1)[0][0]) for e in ordered)
