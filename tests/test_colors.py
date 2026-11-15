"""Colour notations, conversions, and names (ycrystal.core.colors)."""

import pytest

from ycrystal.core.colors import (
    COLOR_FORMATS,
    NAMED_COLORS,
    color_label,
    delta_e,
    describe_color,
    format_color,
    hex_to_rgb,
    nearest_named_color,
    parse_color,
)


@pytest.mark.parametrize(
    "text, expected",
    [
        ("#FF8000", "#FF8000"),
        ("ff8000", "#FF8000"),
        ("#f80", "#FF8800"),
        ("rgb(255, 128, 0)", "#FF8000"),
        ("RGB(100%, 50%, 0%)", "#FF8000"),
        ("255 128 0", "#FF8000"),
        ("255,128,0", "#FF8000"),
        ("1 0.5 0", "#FF8000"),
        ("hsv(30, 100%, 100%)", "#FF8000"),
        ("hsl(30, 100%, 50%)", "#FF8000"),
        ("hsv(30°, 100, 100)", "#FF8000"),
        ("orange", "#FFA500"),
        ("Steel Blue", "#4682B4"),
        ("steelblue", "#4682B4"),
        ("lightgray", "#D3D3D3"),
        ("light grey", "#D3D3D3"),
        ("aqua", "#00FFFF"),
        ("fuchsia", "#FF00FF"),
    ],
)
def test_parse_notations(text, expected):
    assert format_color(parse_color(text), "hex") == expected


@pytest.mark.parametrize(
    "text", ["", "not a colour", "#12345", "300 0 0", "rgb(1, 2)", "hsv(a,b,c)"]
)
def test_parse_errors_explain_the_notations(text):
    with pytest.raises(ValueError):
        parse_color(text)


def test_every_format_reads_back():
    for color in [(1.0, 0.5, 0.0), (0.2, 0.4, 0.6), (0.0, 0.0, 0.0), (0.75, 0.76, 0.78)]:
        for style in COLOR_FORMATS:
            back = parse_color(format_color(color, style))
            assert delta_e(back, color) < 1.5, (style, color, back)
    assert format_color((1.0, 0.5, 0.0), "rgb01") == "1.000 0.500 0.000"
    with pytest.raises(ValueError):
        format_color((1, 1, 1), "cmyk")


def test_named_colours_and_nearest_name():
    assert len(NAMED_COLORS) >= 138 and len({n for n, _ in NAMED_COLORS}) == len(NAMED_COLORS)
    for name, code in NAMED_COLORS:
        found, found_code, difference = nearest_named_color(hex_to_rgb(code))
        assert difference == pytest.approx(0.0, abs=1e-9), name
        assert found_code == code
    name, code, difference = nearest_named_color((0.75, 0.76, 0.78))
    assert (name, code) == ("silver", "#C0C0C0") and 0 < difference < 3
    assert delta_e((1, 0, 0), (0, 0, 1)) > 40  # clearly different


@pytest.mark.parametrize(
    "rgb, words",
    [
        ((1.0, 0.0, 0.0), "red"),
        ((0.0, 0.7, 0.0), "green"),
        ((0.0, 0.5, 0.0), "dark green"),
        ((0.0, 0.0, 1.0), "blue"),
        ((1.0, 1.0, 0.0), "yellow"),
        ((1.0, 0.55, 0.0), "orange"),
        ((0.5, 0.0, 0.5), "purple"),
        ((1.0, 0.75, 0.8), "pink"),
        ((0.45, 0.25, 0.1), "brown"),
        ((0.0, 0.0, 0.0), "black"),
        ((1.0, 1.0, 1.0), "white"),
        ((0.5, 0.5, 0.5), "grey"),
        ((0.75, 0.76, 0.78), "light grey"),
        ((0.1, 0.1, 0.45), "dark blue"),
        ((0.6, 0.8, 1.0), "light blue"),
    ],
)
def test_plain_descriptions(rgb, words):
    assert describe_color(rgb) == words


def test_label_combines_description_and_name():
    assert color_label((1.0, 0.0, 0.0)) == "red (exactly the named colour red #FF0000)"
    assert color_label((1.0, 0.05, 0.05)) == "red (nearest named colour: red #FF0000)"
    assert "exactly the named colour lime #00FF00" in color_label((0.0, 1.0, 0.0))
    assert color_label((0.27, 0.51, 0.71)).startswith("greyish blue (nearest named colour: steel")


# ----- FR-COLOR-01 acceptance: equivalent notations, boundaries, no guessing, no drift ----
def test_five_notations_give_the_same_red():
    reds = [
        parse_color("rgb(255, 0, 0)"),
        parse_color("255 0 0"),
        parse_color("#FF0000"),
        parse_color("#ff0000"),
        parse_color("hsv(0, 100%, 100%)"),
        parse_color("hsl(0, 100%, 50%)"),
        parse_color("red"),
    ]
    assert all(c == (1.0, 0.0, 0.0) for c in reds)


@pytest.mark.parametrize(
    "texts, expected",
    [
        (["#000000", "0 0 0", "hsv(0, 0, 0)", "hsl(0, 0, 0)", "black"], "#000000"),
        (["#FFFFFF", "255 255 255", "hsv(0, 0, 100)", "hsl(0, 0, 100)", "white"], "#FFFFFF"),
        (["#808080", "128 128 128", "grey", "gray"], "#808080"),
        (["#4682B4", "70 130 180", "steel blue"], "#4682B4"),
        (["#123ABC", "18 58 188", "rgb(18, 58, 188)"], "#123ABC"),
        (["hsv(359, 100, 100)", "hsl(359, 100, 50)"], "#FF0004"),
    ],
)
def test_boundaries_and_custom_colours(texts, expected):
    assert {format_color(parse_color(t)) for t in texts} == {expected}


def test_numbers_are_never_reinterpreted():
    assert format_color(parse_color("1 0 0")) == "#010000"  # integers are 0–255
    assert format_color(parse_color("1.0 0 0")) == "#FF0000"  # decimals are fractions
    assert format_color(parse_color("hsv(30, 1, 1)")) == "#030303"  # S, V are percent


def test_representation_round_trips_stay_within_one_channel():
    import itertools

    from ycrystal.core.colors import to_255, to_hsl, to_hsv

    for r, g, b in itertools.product(range(0, 256, 17), repeat=3):
        color = (r / 255, g / 255, b / 255)
        for _ in range(5):  # repeated switching must not drift
            h, sv, v = (round(x, 1) for x in to_hsv(color))
            color = parse_color(f"hsv({h}, {sv}, {v})")
            h, sl, lightness = (round(x, 1) for x in to_hsl(color))
            color = parse_color(f"hsl({h}, {sl}, {lightness})")
            color = parse_color(format_color(color, "hex"))
        assert max(abs(a - b) for a, b in zip(to_255(color), (r, g, b), strict=True)) <= 1
