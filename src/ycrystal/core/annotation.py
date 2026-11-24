"""Text anchored to the output frame independently of the crystal camera."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ycrystal.core.scene import RGB

TEXT_ALIGNMENTS = ("left", "centre", "right")


@dataclass(frozen=True)
class TextAnnotation:
    """Draw plain text with an anchor measured from the top-left of the output frame.

    x and y are fractions of the width and height. Alignment controls which side of
    each line starts at x. The top of the first line is at y. Font size is a percentage
    of the image height, and colour components are in sRGB.
    """

    text: str
    x: float = 0.07
    y: float = 0.07
    font_size: float = 4.0
    font_family: str = ""
    color: RGB = (0.0, 0.0, 0.0)
    alignment: str = "left"
    bold: bool = False
    enabled: bool = True

    def __post_init__(self) -> None:
        if not isinstance(self.text, str) or not self.text.strip():
            raise ValueError("a text annotation needs visible text")
        if not 0.0 <= self.x <= 1.0 or not 0.0 <= self.y <= 1.0:
            raise ValueError("text anchor coordinates must be between 0 and 1")
        if not 0.5 <= self.font_size <= 100.0:
            raise ValueError("text font size must be between 0.5 and 100 percent")
        if self.alignment not in TEXT_ALIGNMENTS:
            raise ValueError("text alignment must be left, centre, or right")
        color = tuple(float(channel) for channel in self.color)
        if len(color) != 3 or not all(0.0 <= channel <= 1.0 for channel in color):
            raise ValueError("text colour components must be between 0 and 1")
        object.__setattr__(self, "color", color)
