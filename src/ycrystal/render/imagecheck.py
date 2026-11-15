"""Numerical image checks: locate rendered spheres and compare with the camera model.

Sphere silhouettes under orthographic projection are discs centred on the projected
atom centre, so the alpha-mask centroid of each disc is independent of shading.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from pathlib import Path

import numpy as np


@dataclass(frozen=True)
class Blob:
    """A connected opaque region of an image, usually one rendered sphere.

    Attributes
    ----------
    centroid
        Centre of the region in continuous pixel coordinates ``(x, y)``, top-left
        origin, pixel centres at half-integers.
    area
        Number of pixels.
    mean_rgb
        Mean colour, components between 0 and 1.
    """

    centroid: tuple[float, float]  # continuous pixel coordinates (x, y), top-left origin
    area: int
    mean_rgb: tuple[float, float, float]


def load_rgba(path: Path) -> np.ndarray:
    """Read an image file as an RGBA array.

    Returns
    -------
    numpy.ndarray
        ``uint8`` array of shape ``(height, width, 4)``; row 0 is the top of the image.
    """
    from PIL import Image

    with Image.open(path) as image:
        return np.asarray(image.convert("RGBA"))


def find_blobs(rgba: np.ndarray, alpha_threshold: int = 128, min_area: int = 12) -> list[Blob]:
    """Find the connected opaque regions of an RGBA image.

    Parameters
    ----------
    rgba
        Image array of shape ``(height, width, 4)``.
    alpha_threshold
        Pixels with at least this alpha value count as opaque.
    min_area
        Regions with fewer pixels are ignored.

    Returns
    -------
    list of Blob
        Regions of 4-connected opaque pixels.
    """
    mask = rgba[..., 3] >= alpha_threshold
    seen = np.zeros_like(mask)
    height, width = mask.shape
    blobs: list[Blob] = []
    for y0, x0 in zip(*np.nonzero(mask), strict=True):
        if seen[y0, x0]:
            continue
        seen[y0, x0] = True
        queue = deque([(int(y0), int(x0))])
        ys: list[int] = []
        xs: list[int] = []
        while queue:
            y, x = queue.popleft()
            ys.append(y)
            xs.append(x)
            for ny, nx in ((y - 1, x), (y + 1, x), (y, x - 1), (y, x + 1)):
                if 0 <= ny < height and 0 <= nx < width and mask[ny, nx] and not seen[ny, nx]:
                    seen[ny, nx] = True
                    queue.append((ny, nx))
        if len(ys) < min_area:
            continue
        ya, xa = np.asarray(ys), np.asarray(xs)
        rgb = rgba[ya, xa, :3].astype(float).mean(axis=0) / 255.0
        blobs.append(
            Blob(
                (float(xa.mean() + 0.5), float(ya.mean() + 0.5)),
                len(ys),
                (float(rgb[0]), float(rgb[1]), float(rgb[2])),
            )
        )
    return blobs


@dataclass(frozen=True)
class Match:
    """Comparison of one predicted sphere position with the nearest blob.

    Attributes
    ----------
    expected
        Predicted pixel position ``(x, y)``.
    found
        Centroid of the nearest blob, or ``None`` if the image has no blobs.
    error_px
        Distance in pixels between `expected` and `found`; infinite without blobs.
    expected_rgb
        Expected colour, components between 0 and 1.
    found_rgb
        Mean colour of the nearest blob.
    hue_ok
        Whether both colours have the same dominant channel (red, green, or blue).
    """

    expected: tuple[float, float]
    found: tuple[float, float] | None
    error_px: float
    expected_rgb: tuple[float, float, float]
    found_rgb: tuple[float, float, float] | None
    hue_ok: bool


def _dominant_channel(rgb: tuple[float, float, float] | np.ndarray) -> int:
    return int(np.argmax(np.asarray(rgb)))


def match_spheres(
    expected_xy: np.ndarray, expected_rgb: np.ndarray, blobs: list[Blob]
) -> list[Match]:
    """Match each predicted sphere position to the nearest blob.

    Parameters
    ----------
    expected_xy
        Predicted pixel positions, shape ``(K, 2)``.
    expected_rgb
        Expected colours, shape ``(K, 3)``.
    blobs
        Blobs found in the image; one blob may match several predictions.

    Returns
    -------
    list of Match
        One match per prediction, in the same order.
    """
    matches: list[Match] = []
    for xy, rgb in zip(np.asarray(expected_xy), np.asarray(expected_rgb), strict=True):
        if not blobs:
            matches.append(Match(tuple(xy), None, float("inf"), tuple(rgb), None, False))
            continue
        distances = [np.hypot(b.centroid[0] - xy[0], b.centroid[1] - xy[1]) for b in blobs]
        best = blobs[int(np.argmin(distances))]
        matches.append(
            Match(
                expected=(float(xy[0]), float(xy[1])),
                found=best.centroid,
                error_px=float(min(distances)),
                expected_rgb=(float(rgb[0]), float(rgb[1]), float(rgb[2])),
                found_rgb=best.mean_rgb,
                hue_ok=_dominant_channel(rgb) == _dominant_channel(best.mean_rgb),
            )
        )
    return matches
