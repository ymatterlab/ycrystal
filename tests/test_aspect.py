"""FR-RENDER-01: output-size arithmetic with a locked aspect ratio (no Qt)."""

import pytest

from ycrystal.core.aspect import (
    MAX_OUTPUT_PIXELS,
    MIN_OUTPUT_PIXELS,
    OutputSizeError,
    linked_size,
    matches_ratio,
    preset_size,
    round_pixels,
    swapped,
)
from ycrystal.io.project import Project, project_from_dict, project_to_dict
from ycrystal.render.pov_writer import RenderSettings


def test_examples_from_the_request():
    ratio = 2400 / 1600
    assert linked_size("height", 1920, (2400, 1600), ratio, True) == (2880, 1920)
    assert linked_size("width", 3000, (2400, 1600), ratio, True) == (3000, 2000)
    assert linked_size("height", 1920, (2400, 1600), ratio, False) == (2400, 1920)
    assert linked_size("width", 3000, (2400, 1600), ratio, False) == (3000, 1600)


def test_rounding_is_half_up_in_whole_pixels():
    assert round_pixels(2.5) == 3 and round_pixels(3.5) == 4 and round_pixels(2.49) == 2
    assert linked_size("width", 101, (100, 50), 2.0, True) == (101, 51)  # 50.5 → 51


def test_repeated_edits_do_not_drift():
    ratio = 1000 / 700  # non-integer ratio
    size = (1000, 700)
    for width in (1001, 1003, 1517, 333, 4096, 999, 1000):
        size = linked_size("width", width, size, ratio, True)
        assert size[1] == round_pixels(width / ratio)
    assert size == (1000, 700)  # back where it started, exactly
    for height in (701, 702, 1919, 455, 700):
        size = linked_size("height", height, size, ratio, True)
    assert size == (1000, 700)
    # The naive alternative (recomputing the ratio from rounded pixels) drifts:
    naive = kept = (1000, 700)
    for width in (33, 1000):
        naive = (width, round_pixels(width / (naive[0] / naive[1])))
        kept = linked_size("width", width, kept, ratio, True)
    assert naive == (1000, 697) and kept == (1000, 700)


def test_limits_reject_the_whole_edit():
    with pytest.raises(OutputSizeError, match="Width would be 9000 px.*at most 8000"):
        linked_size("height", 6000, (2400, 1600), 1.5, True)
    with pytest.raises(OutputSizeError, match="at least 16"):
        linked_size("width", 20, (2400, 1600), 1.5, True)  # height 13 px
    with pytest.raises(OutputSizeError, match="Height must be between"):
        linked_size("height", MAX_OUTPUT_PIXELS + 1, (2400, 1600), 1.5, False)
    assert linked_size("width", MAX_OUTPUT_PIXELS, (2400, 1600), 1.5, True) == (8000, 5333)
    assert linked_size("width", MIN_OUTPUT_PIXELS, (16, 16), 1.0, True) == (16, 16)
    with pytest.raises(ValueError):
        linked_size("depth", 10, (100, 100), 1.0, True)
    with pytest.raises(ValueError):
        linked_size("width", 10, (100, 100), 0.0, True)


def test_presets_matching_and_swap():
    assert preset_size(1920, 16 / 9) == (1920, 1080)
    with pytest.raises(OutputSizeError, match="height of 12000 px"):
        preset_size(8000, 2 / 3)
    assert matches_ratio((1920, 1080), 16 / 9) and not matches_ratio((1920, 1081), 16 / 9)
    (size, ratio) = swapped((2400, 1600), 1.5)
    assert size == (1600, 2400) and ratio == pytest.approx(1 / 1.5)
    assert swapped(*swapped((2400, 1600), 1.5))[1] == pytest.approx(1.5)


def test_lock_state_in_projects_and_old_files():
    from ycrystal.core.samples import perovskite_srtio3

    output = RenderSettings(1000, 700, aspect_locked=False, aspect_ratio=1000 / 700)
    data = project_to_dict(Project(perovskite_srtio3(), output=output))
    assert data["output"]["aspect_locked"] is False
    assert data["output"]["aspect_ratio"] == pytest.approx(1000 / 700)
    again = project_from_dict(data).output
    assert (again.aspect_locked, again.aspect_ratio) == (False, 1000 / 700)
    for key in ("aspect_locked", "aspect_ratio"):  # a 0.1.0 project has neither key
        del data["output"][key]
    old = project_from_dict(data).output
    assert old.aspect_locked is True and old.target_ratio() == pytest.approx(1000 / 700)
    assert data["schema_version"] == 9  # the lock keys alone did not bump the schema (5)
    with pytest.raises(ValueError):
        RenderSettings(10, 10, aspect_ratio=-1.0)
