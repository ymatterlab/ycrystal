"""Colour input, conversion, and colour names.

Colours in Ycrystal are sRGB triples between 0 and 1. This module reads them from text
in several notations, writes them back, converts to HSV/HSL, and names them, so that
colours can be typed exactly and identified without relying on colour vision:

- [`parse_color`][ycrystal.core.colors.parse_color] accepts ``#RRGGBB`` / ``#RGB``,
  ``rgb(255, 128, 0)``, three numbers (integers 0–255, or fractions 0–1 written with a
  decimal point),
  ``hsv(30, 100%, 100%)``, ``hsl(30, 100%, 50%)``, and CSS colour names
  (``"steel blue"``, ``"steelblue"``, any case);
- [`describe_color`][ycrystal.core.colors.describe_color] gives a plain description
  from a small vocabulary ("dark orange", "light grey", "greyish blue");
- [`nearest_named_color`][ycrystal.core.colors.nearest_named_color] finds the closest of
  the 140 CSS named colours by perceived difference (CIEDE2000);
- [`color_label`][ycrystal.core.colors.color_label] combines both for tooltips.

Examples
--------
>>> from ycrystal.core.colors import color_label, format_color, parse_color
>>> parse_color("#ff8000")
(1.0, 0.5019607843137255, 0.0)
>>> parse_color("rgb(255, 0, 0)") == parse_color("1.0 0 0") == parse_color("Red")
True
>>> format_color(parse_color("hsv(240, 100%, 100%)"), "hex")
'#0000FF'
>>> color_label((1.0, 0.05, 0.05))
'red (nearest named colour: red #FF0000)'
>>> color_label((1.0, 0.0, 0.0))
'red (exactly the named colour red #FF0000)'
>>> color_label((0.75, 0.76, 0.78))
'light grey (nearest named colour: silver #C0C0C0)'
"""

from __future__ import annotations

import colorsys
import math
import re
from functools import cache

RGB = tuple[float, float, float]

COLOR_FORMATS = ("hex", "rgb255", "rgb01", "hsv", "hsl")
"""Notations written by [`format_color`][ycrystal.core.colors.format_color]."""

# CSS Color Module Level 4 named colours (display name with spaces, hex). The aliases
# "aqua" (= cyan), "fuchsia" (= magenta), and the "gray" spellings are accepted by
# parse_color but not offered as nearest names.
NAMED_COLORS: tuple[tuple[str, str], ...] = (
    ("alice blue", "#F0F8FF"), ("antique white", "#FAEBD7"), ("aquamarine", "#7FFFD4"),
    ("azure", "#F0FFFF"), ("beige", "#F5F5DC"), ("bisque", "#FFE4C4"),
    ("black", "#000000"), ("blanched almond", "#FFEBCD"), ("blue", "#0000FF"),
    ("blue violet", "#8A2BE2"), ("brown", "#A52A2A"), ("burly wood", "#DEB887"),
    ("cadet blue", "#5F9EA0"), ("chartreuse", "#7FFF00"), ("chocolate", "#D2691E"),
    ("coral", "#FF7F50"), ("cornflower blue", "#6495ED"), ("cornsilk", "#FFF8DC"),
    ("crimson", "#DC143C"), ("cyan", "#00FFFF"), ("dark blue", "#00008B"),
    ("dark cyan", "#008B8B"), ("dark goldenrod", "#B8860B"), ("dark grey", "#A9A9A9"),
    ("dark green", "#006400"), ("dark khaki", "#BDB76B"), ("dark magenta", "#8B008B"),
    ("dark olive green", "#556B2F"), ("dark orange", "#FF8C00"),
    ("dark orchid", "#9932CC"), ("dark red", "#8B0000"), ("dark salmon", "#E9967A"),
    ("dark sea green", "#8FBC8F"), ("dark slate blue", "#483D8B"),
    ("dark slate grey", "#2F4F4F"), ("dark turquoise", "#00CED1"),
    ("dark violet", "#9400D3"), ("deep pink", "#FF1493"), ("deep sky blue", "#00BFFF"),
    ("dim grey", "#696969"), ("dodger blue", "#1E90FF"), ("firebrick", "#B22222"),
    ("floral white", "#FFFAF0"), ("forest green", "#228B22"), ("gainsboro", "#DCDCDC"),
    ("ghost white", "#F8F8FF"), ("gold", "#FFD700"), ("goldenrod", "#DAA520"),
    ("grey", "#808080"), ("green", "#008000"), ("green yellow", "#ADFF2F"),
    ("honeydew", "#F0FFF0"), ("hot pink", "#FF69B4"), ("indian red", "#CD5C5C"),
    ("indigo", "#4B0082"), ("ivory", "#FFFFF0"), ("khaki", "#F0E68C"),
    ("lavender", "#E6E6FA"), ("lavender blush", "#FFF0F5"), ("lawn green", "#7CFC00"),
    ("lemon chiffon", "#FFFACD"), ("light blue", "#ADD8E6"), ("light coral", "#F08080"),
    ("light cyan", "#E0FFFF"), ("light goldenrod yellow", "#FAFAD2"),
    ("light grey", "#D3D3D3"), ("light green", "#90EE90"), ("light pink", "#FFB6C1"),
    ("light salmon", "#FFA07A"), ("light sea green", "#20B2AA"),
    ("light sky blue", "#87CEFA"), ("light slate grey", "#778899"),
    ("light steel blue", "#B0C4DE"), ("light yellow", "#FFFFE0"), ("lime", "#00FF00"),
    ("lime green", "#32CD32"), ("linen", "#FAF0E6"), ("magenta", "#FF00FF"),
    ("maroon", "#800000"), ("medium aquamarine", "#66CDAA"), ("medium blue", "#0000CD"),
    ("medium orchid", "#BA55D3"), ("medium purple", "#9370DB"),
    ("medium sea green", "#3CB371"), ("medium slate blue", "#7B68EE"),
    ("medium spring green", "#00FA9A"), ("medium turquoise", "#48D1CC"),
    ("medium violet red", "#C71585"), ("midnight blue", "#191970"),
    ("mint cream", "#F5FFFA"), ("misty rose", "#FFE4E1"), ("moccasin", "#FFE4B5"),
    ("navajo white", "#FFDEAD"), ("navy", "#000080"), ("old lace", "#FDF5E6"),
    ("olive", "#808000"), ("olive drab", "#6B8E23"), ("orange", "#FFA500"),
    ("orange red", "#FF4500"), ("orchid", "#DA70D6"), ("pale goldenrod", "#EEE8AA"),
    ("pale green", "#98FB98"), ("pale turquoise", "#AFEEEE"),
    ("pale violet red", "#DB7093"), ("papaya whip", "#FFEFD5"), ("peach puff", "#FFDAB9"),
    ("peru", "#CD853F"), ("pink", "#FFC0CB"), ("plum", "#DDA0DD"),
    ("powder blue", "#B0E0E6"), ("purple", "#800080"), ("rebecca purple", "#663399"),
    ("red", "#FF0000"), ("rosy brown", "#BC8F8F"), ("royal blue", "#4169E1"),
    ("saddle brown", "#8B4513"), ("salmon", "#FA8072"), ("sandy brown", "#F4A460"),
    ("sea green", "#2E8B57"), ("seashell", "#FFF5EE"), ("sienna", "#A0522D"),
    ("silver", "#C0C0C0"), ("sky blue", "#87CEEB"), ("slate blue", "#6A5ACD"),
    ("slate grey", "#708090"), ("snow", "#FFFAFA"), ("spring green", "#00FF7F"),
    ("steel blue", "#4682B4"), ("tan", "#D2B48C"), ("teal", "#008080"),
    ("thistle", "#D8BFD8"), ("tomato", "#FF6347"), ("turquoise", "#40E0D0"),
    ("violet", "#EE82EE"), ("wheat", "#F5DEB3"), ("white", "#FFFFFF"),
    ("white smoke", "#F5F5F5"), ("yellow", "#FFFF00"), ("yellow green", "#9ACD32"),
)  # fmt: skip
"""CSS named colours: ``(name, hex)``, with spaces in names and the "grey" spelling."""

_ALIASES = {"aqua": "cyan", "fuchsia": "magenta"}


def _key(name: str) -> str:
    return re.sub(r"[\s_\-]", "", name.casefold()).replace("gray", "grey")


@cache
def _name_table() -> dict[str, RGB]:
    table = {_key(name): hex_to_rgb(code) for name, code in NAMED_COLORS}
    for alias, target in _ALIASES.items():
        table[alias] = table[target]
    return table


def hex_to_rgb(text: str) -> RGB:
    """Return the colour of ``#RRGGBB`` or ``#RGB`` (the ``#`` is optional).

    Raises
    ------
    ValueError
        If the text is not a hexadecimal colour.
    """
    code = text.strip().lstrip("#")
    if len(code) == 3:
        code = "".join(ch * 2 for ch in code)
    if not re.fullmatch(r"[0-9a-fA-F]{6}", code):
        raise ValueError(f"{text!r} is not a hexadecimal colour (#RRGGBB)")
    return tuple(int(code[i : i + 2], 16) / 255.0 for i in (0, 2, 4))  # type: ignore[return-value]


def to_255(color: RGB) -> tuple[int, int, int]:
    """Return 8-bit components (0–255), rounded."""
    r, g, b = (max(0, min(255, round(c * 255))) for c in color)
    return (r, g, b)


def _numbers(text: str) -> list[tuple[float, bool]]:
    parts = [p for p in re.split(r"[\s,;/]+", text.strip()) if p]
    values = []
    for part in parts:
        percent = part.endswith("%")
        number = part.rstrip("%°").removesuffix("deg")
        values.append((float(number), percent))
    return values


def parse_color(text: str) -> RGB:
    """Read a colour from text.

    Accepted notations (case and spacing do not matter):

    - ``#RRGGBB``, ``#RGB``;
    - ``rgb(R, G, B)`` with 0–255 values or percentages;
    - three numbers ``R G B`` (commas allowed): integers are 0–255 (``255 0 0`` is red,
      ``1 0 0`` almost black); numbers with a decimal point are fractions 0–1
      (``1.0 0 0`` is red); mixing is refused rather than guessed;
    - ``hsv(H, S, V)`` and ``hsl(H, S, L)`` with H in degrees and S, V, L always in
      percent (the ``%`` sign is optional: ``hsv(0, 100, 100)`` is red);
    - a CSS colour name such as ``red``, ``steel blue``, ``SteelBlue``, ``light gray``.

    Returns
    -------
    RGB
        sRGB components between 0 and 1.

    Raises
    ------
    ValueError
        With a message naming the accepted notations, if the text cannot be read or a
        value is out of range.
    """
    raw = text.strip()
    if not raw:
        raise ValueError("enter a colour, for example #FF8000, 255 128 0, or orange")
    name = _key(raw)
    if name in _name_table():
        return _name_table()[name]
    if raw.startswith("#") or re.fullmatch(r"[0-9a-fA-F]{6}", raw):
        return hex_to_rgb(raw)
    match = re.fullmatch(r"(?i)\s*(rgb|hsv|hsb|hsl)a?\s*\((.*)\)\s*", raw)
    try:
        if match:
            kind, inner = match.group(1).lower(), match.group(2)
            values = _numbers(inner)[:3]
            if len(values) != 3:
                raise ValueError
            if kind == "rgb":
                comps = [v / 100.0 if pct else v / 255.0 for v, pct in values]
            else:
                hue = (values[0][0] % 360.0) / 360.0
                a, b = (v / 100.0 for v, _ in values[1:])  # always percent, "%" optional
                if kind in ("hsv", "hsb"):
                    comps = list(colorsys.hsv_to_rgb(hue, a, b))
                else:
                    comps = list(colorsys.hls_to_rgb(hue, b, a))
        else:
            values = _numbers(raw)
            if len(values) != 3:
                raise ValueError
            numbers = [v for v, _ in values]
            decimal = "." in raw
            if any(pct for _, pct in values):
                comps = [v / 100.0 for v in numbers]
            elif decimal:  # fractions 0–1 are written with a decimal point
                if max(numbers) > 1.0:
                    raise ValueError(
                        f"{text!r}: write integers 0–255 or fractions 0–1 (with a decimal point)"
                    )
                comps = numbers
            else:
                comps = [v / 255.0 for v in numbers]
    except ValueError as exc:
        if "write integers" in str(exc):
            raise
        raise ValueError(
            f"cannot read {text!r}: use #RRGGBB, R G B (0–255 or 0–1), rgb(…), hsv(…), "
            "hsl(…), or a colour name"
        ) from None
    if not all(0.0 <= c <= 1.0 + 1e-9 for c in comps):
        raise ValueError(f"{text!r}: colour components out of range")
    r, g, b = (min(1.0, max(0.0, float(c))) for c in comps)
    return (r, g, b)


def to_hsv(color: RGB) -> tuple[float, float, float]:
    """Return hue in degrees (0–360) and saturation and value in percent."""
    h, s, v = colorsys.rgb_to_hsv(*color)
    return (h * 360.0, s * 100.0, v * 100.0)


def to_hsl(color: RGB) -> tuple[float, float, float]:
    """Return hue in degrees (0–360) and saturation and lightness in percent."""
    h, lightness, s = colorsys.rgb_to_hls(*color)
    return (h * 360.0, s * 100.0, lightness * 100.0)


def format_color(color: RGB, style: str = "hex") -> str:
    """Write a colour in one of [`COLOR_FORMATS`][ycrystal.core.colors.COLOR_FORMATS].

    ``"hex"`` → ``#FF8000``; ``"rgb255"`` → ``rgb(255, 128, 0)``; ``"rgb01"`` →
    ``1.000 0.502 0.000`` (as stored in projects and POV-Ray scenes); ``"hsv"`` →
    ``hsv(30°, 100%, 100%)``; ``"hsl"`` → ``hsl(30°, 100%, 50%)``. Every result can be
    read back with [`parse_color`][ycrystal.core.colors.parse_color].
    """
    if style == "hex":
        return "#{:02X}{:02X}{:02X}".format(*to_255(color))
    if style == "rgb255":
        return "rgb({}, {}, {})".format(*to_255(color))
    if style == "rgb01":
        return " ".join(f"{c:.3f}" for c in color)
    if style == "hsv":
        h, s, v = to_hsv(color)
        return f"hsv({h:.0f}°, {s:.0f}%, {v:.0f}%)"
    if style == "hsl":
        h, s, lightness = to_hsl(color)
        return f"hsl({h:.0f}°, {s:.0f}%, {lightness:.0f}%)"
    raise ValueError(f"style must be one of {COLOR_FORMATS}")


# ----- perceptual distance ------------------------------------------------------------------
def _linear(c: float) -> float:
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def to_lab(color: RGB) -> tuple[float, float, float]:
    """Return CIE L*a*b* (D65) of an sRGB colour."""
    r, g, b = (_linear(c) for c in color)
    x = (0.4124564 * r + 0.3575761 * g + 0.1804375 * b) / 0.95047
    y = 0.2126729 * r + 0.7151522 * g + 0.0721750 * b
    z = (0.0193339 * r + 0.1191920 * g + 0.9503041 * b) / 1.08883

    def f(t: float) -> float:
        return t ** (1 / 3) if t > 216 / 24389 else (24389 / 27 * t + 16) / 116

    fx, fy, fz = f(x), f(y), f(z)
    return (116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz))


def delta_e(a: RGB, b: RGB) -> float:
    """Return the CIEDE2000 colour difference between two sRGB colours.

    About 1 is a just-noticeable difference; above about 10 colours look clearly
    different.
    """
    return _de2000(to_lab(a), to_lab(b))


def _de2000(lab1: tuple[float, float, float], lab2: tuple[float, float, float]) -> float:
    l1, a1, b1 = lab1
    l2, a2, b2 = lab2
    c1, c2 = math.hypot(a1, b1), math.hypot(a2, b2)
    c_bar = (c1 + c2) / 2
    g = 0.5 * (1 - math.sqrt(c_bar**7 / (c_bar**7 + 25**7)))
    a1p, a2p = (1 + g) * a1, (1 + g) * a2
    c1p, c2p = math.hypot(a1p, b1), math.hypot(a2p, b2)
    h1p = math.degrees(math.atan2(b1, a1p)) % 360 if c1p else 0.0
    h2p = math.degrees(math.atan2(b2, a2p)) % 360 if c2p else 0.0
    dlp, dcp = l2 - l1, c2p - c1p
    if c1p * c2p == 0:
        dhp = 0.0
    elif abs(h2p - h1p) <= 180:
        dhp = h2p - h1p
    else:
        dhp = h2p - h1p - 360 if h2p > h1p else h2p - h1p + 360
    dhp_big = 2 * math.sqrt(c1p * c2p) * math.sin(math.radians(dhp / 2))
    l_bar, c_bar_p = (l1 + l2) / 2, (c1p + c2p) / 2
    if c1p * c2p == 0:
        h_bar = h1p + h2p
    elif abs(h1p - h2p) <= 180:
        h_bar = (h1p + h2p) / 2
    else:
        h_bar = (h1p + h2p + 360) / 2 if h1p + h2p < 360 else (h1p + h2p - 360) / 2
    t = (
        1
        - 0.17 * math.cos(math.radians(h_bar - 30))
        + 0.24 * math.cos(math.radians(2 * h_bar))
        + 0.32 * math.cos(math.radians(3 * h_bar + 6))
        - 0.20 * math.cos(math.radians(4 * h_bar - 63))
    )
    d_theta = 30 * math.exp(-(((h_bar - 275) / 25) ** 2))
    r_c = 2 * math.sqrt(c_bar_p**7 / (c_bar_p**7 + 25**7))
    s_l = 1 + 0.015 * (l_bar - 50) ** 2 / math.sqrt(20 + (l_bar - 50) ** 2)
    s_c = 1 + 0.045 * c_bar_p
    s_h = 1 + 0.015 * c_bar_p * t
    r_t = -math.sin(math.radians(2 * d_theta)) * r_c
    return math.sqrt(
        (dlp / s_l) ** 2
        + (dcp / s_c) ** 2
        + (dhp_big / s_h) ** 2
        + r_t * (dcp / s_c) * (dhp_big / s_h)
    )


@cache
def _named_labs() -> tuple[tuple[str, str, tuple[float, float, float]], ...]:
    return tuple((name, code, to_lab(hex_to_rgb(code))) for name, code in NAMED_COLORS)


def nearest_named_color(color: RGB) -> tuple[str, str, float]:
    """Return the closest CSS named colour: ``(name, hex, CIEDE2000 difference)``.

    The colour is compared at 8-bit precision; a difference of 0 means it is exactly
    that named colour.
    """
    target = to_lab(tuple(c / 255.0 for c in to_255(color)))  # type: ignore[arg-type]
    name, code, lab = min(_named_labs(), key=lambda item: _de2000(target, item[2]))
    return name, code, _de2000(target, lab)


# ----- plain descriptions ---------------------------------------------------------------------
_HUES = (
    (15, "red"),
    (40, "orange"),
    (68, "yellow"),
    (150, "green"),
    (190, "cyan"),
    (250, "blue"),
    (285, "purple"),
    (330, "magenta"),
    (360, "red"),
)


def describe_color(color: RGB) -> str:
    """Return a plain description of a colour from a small vocabulary.

    Hue words: red, orange, yellow, green, cyan, blue, purple, magenta, plus pink,
    brown, and olive; neutral words: black, dark grey, grey, light grey, white. They can
    be qualified by *dark*, *light*, or *greyish*. Meant to help people who perceive
    colours differently, not as a precise colour specification.

    Examples
    --------
    >>> from ycrystal.core.colors import describe_color
    >>> [describe_color(c) for c in [(1, 0, 0), (0.5, 0.25, 0.05), (0.27, 0.51, 0.71)]]
    ['red', 'brown', 'greyish blue']
    """
    hue, sat, light = to_hsl(color)
    s, lightness = sat / 100.0, light / 100.0
    chroma = max(color) - min(color)
    if chroma < 0.06 or (s < 0.1 and 0.1 < lightness < 0.9):
        if lightness < 0.1:
            return "black"
        if lightness < 0.35:
            return "dark grey"
        if lightness < 0.65:
            return "grey"
        if lightness < 0.92:
            return "light grey"
        return "white"
    if lightness < 0.06:
        return "black"
    if lightness > 0.96:
        return "white"
    family = next(word for limit, word in _HUES if hue < limit)
    if family in ("orange", "red") and lightness < 0.4 and 10 <= hue < 45:
        family = "brown"
    elif family == "yellow" and lightness < 0.35:
        family = "olive"
    elif family in ("red", "magenta") and lightness > 0.72:
        family = "pink"
    dark_word = family in ("brown", "olive")  # already names a dark colour
    if family == "magenta" and lightness < 0.35:
        family, dark_word = "purple", lightness >= 0.18  # dark magenta reads as purple
    modifier = ""
    if not dark_word:
        if lightness < 0.3:
            modifier = "dark "
        elif lightness > 0.72 and family != "pink":
            modifier = "light "
    if s < 0.45 and lightness >= 0.3:
        modifier = "greyish " if not modifier else modifier
    return f"{modifier}{family}"


def color_label(color: RGB) -> str:
    """Return ``"description (nearest named colour: name #HEX)"`` for tooltips.

    The named colour is reported as *exactly* when the colour equals it at 8-bit
    precision, otherwise as *nearest* (an approximation; the hex value is exact).
    """
    name, code, difference = nearest_named_color(color)
    relation = "named colour" if difference > 1e-6 else "exactly"
    if relation == "exactly" and _key(name) != _key(describe_color(color)):
        return f"{describe_color(color)} (exactly the named colour {name} {code})"
    if relation == "exactly":
        return f"{name} (exactly the named colour {name} {code})"
    return f"{describe_color(color)} (nearest {relation}: {name} {code})"
