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
    centroid: tuple[float, float]  # continuous pixel coordinates (x, y), top-left origin
    area: int
    mean_rgb: tuple[float, float, float]


def load_rgba(path: Path) -> np.ndarray:
    from PIL import Image

    with Image.open(path) as image:
        return np.asarray(image.convert("RGBA"))


def find_blobs(rgba: np.ndarray, alpha_threshold: int = 128, min_area: int = 12) -> list[Blob]:
    """Connected (4-neighbour) opaque regions of an RGBA image."""
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
    """Match each expected projection to the nearest blob and compare colour channels."""
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
