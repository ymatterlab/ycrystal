"""Imported pictures: validation, normalisation, and content-addressed storage.

Background pictures (FR-BGIMAGE-01) are imported once and then referred to by content
identity: the SHA-256 digest of the stored bytes. Renders, projects, styles, and exports
use the stored bytes, never the original path, so moving or deleting the original file
changes nothing.

Import rules: PNG and JPEG files are decoded with Pillow to check them. A file is
stored unchanged when POV-Ray 3.7 can read it as it is (RGB or greyscale PNG, with or
without alpha; RGB or greyscale JPEG) and has normal orientation; otherwise (EXIF
rotation, CMYK, palette, or other modes) the decoded, upright pixels are stored as PNG.
The size limits are
[`MAX_IMAGE_BYTES`][ycrystal.io.images.MAX_IMAGE_BYTES],
[`MAX_IMAGE_SIDE`][ycrystal.io.images.MAX_IMAGE_SIDE], and
[`MAX_IMAGE_PIXELS`][ycrystal.io.images.MAX_IMAGE_PIXELS].

Stored pictures are kept in a process-wide registry
([`register_image`][ycrystal.io.images.register_image],
[`get_image`][ycrystal.io.images.get_image]). Entries are immutable and keyed by their
content, so registering the same picture twice is harmless, and undo/redo steps that
still refer to a replaced or removed picture keep working for the whole session.
"""

from __future__ import annotations

import hashlib
import io
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from ycrystal.core.background import BackgroundImage

MAX_IMAGE_BYTES = 64 * 1024 * 1024
"""Largest picture file accepted, in bytes."""

MAX_IMAGE_SIDE = 12000
"""Largest picture width or height accepted, in pixels."""

MAX_IMAGE_PIXELS = 50_000_000
"""Largest number of pixels (width × height) accepted."""

SUFFIXES = {"png": ".png", "jpeg": ".jpg"}
"""File-name suffix of each stored format."""


class ImageError(ValueError):
    """A picture cannot be used; ``str()`` explains why for the user."""


@dataclass(frozen=True, eq=False)
class ImageAsset:
    """A stored picture.

    Attributes
    ----------
    id
        SHA-256 hex digest of `data`.
    data
        Stored file bytes (PNG or JPEG).
    format
        ``"png"`` or ``"jpeg"``.
    width, height
        Pixel size (upright).
    name
        File name it was imported from.
    mean_color
        Average sRGB colour (0–1) of its opaque pixels.
    has_alpha
        Whether it has transparent pixels.
    """

    id: str
    data: bytes
    format: str
    width: int
    height: int
    name: str
    mean_color: tuple[float, float, float]
    has_alpha: bool

    @property
    def filename(self) -> str:
        """Short ASCII file name used in render jobs and exports."""
        return asset_filename(self.id, self.format)

    def reference(self, **framing: object) -> BackgroundImage:
        """Return a background reference to this picture with the given framing."""
        return BackgroundImage(
            self.id,
            self.name,
            self.width,
            self.height,
            self.format,
            self.mean_color,
            **framing,  # type: ignore[arg-type]
        )


_REGISTRY: dict[str, ImageAsset] = {}


def asset_filename(asset_id: str, image_format: str) -> str:
    """Return the staged file name of a picture, e.g. ``"bg_1f2e3d4c5b6a7980.png"``."""
    return f"bg_{asset_id[:16]}{SUFFIXES[image_format]}"


def register_image(asset: ImageAsset) -> ImageAsset:
    """Add a picture to the session registry (idempotent) and return it."""
    _REGISTRY.setdefault(asset.id, asset)
    return _REGISTRY[asset.id]


def get_image(asset_id: str) -> ImageAsset:
    """Return a registered picture.

    Raises
    ------
    ImageError
        If no picture with this identity was imported or loaded in this session.
    """
    try:
        return _REGISTRY[asset_id]
    except KeyError:
        raise ImageError(
            f"The background picture {asset_id[:12]}… is not available; choose the image "
            "again or reopen the project that contains it."
        ) from None


def import_image(path: str | Path) -> ImageAsset:
    """Read, check, and register a PNG or JPEG file.

    Raises
    ------
    ImageError
        If the file cannot be read, is not a decodable PNG or JPEG, or is too large.
    """
    path = Path(path)
    try:
        size = path.stat().st_size
        if size > MAX_IMAGE_BYTES:
            raise ImageError(
                f"{path.name} is {size / 2**20:.0f} MB; pictures up to "
                f"{MAX_IMAGE_BYTES // 2**20} MB are supported."
            )
        data = path.read_bytes()
    except OSError as exc:
        raise ImageError(f"Cannot read {path.name}: {exc.strerror or exc}") from exc
    return register_image(image_from_bytes(data, path.name))


def image_from_bytes(data: bytes, name: str, *, stored: bool = False) -> ImageAsset:
    """Check picture bytes and return the stored asset (not registered).

    Parameters
    ----------
    data
        PNG or JPEG file contents.
    name
        File name for messages and display.
    stored
        Whether `data` comes from a project or style package: it must then already be
        in stored form (no normalisation), so its digest stays valid.

    Raises
    ------
    ImageError
        For unsupported, damaged, or oversized pictures.
    """
    from PIL import Image, ImageOps, UnidentifiedImageError

    if len(data) > MAX_IMAGE_BYTES:
        raise ImageError(f"{name} is larger than {MAX_IMAGE_BYTES // 2**20} MB.")
    try:
        with Image.open(io.BytesIO(data)) as probe:
            kind = probe.format
            width, height = probe.size
            _check_size(name, width, height)
            probe.verify()
        image = Image.open(io.BytesIO(data))
        image.load()
    except ImageError:
        raise
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError) as exc:
        raise ImageError(
            f"{name} is not a readable PNG or JPEG picture ({exc.__class__.__name__})."
        ) from exc
    except Image.DecompressionBombError as exc:
        raise ImageError(f"{name} is too large to decode safely.") from exc
    if kind not in ("PNG", "JPEG"):
        raise ImageError(f"{name} is a {kind} file; only PNG and JPEG pictures are supported.")
    orientation = image.getexif().get(0x0112, 1)
    keep = (
        (kind == "PNG" and image.mode in ("RGB", "RGBA", "L", "LA"))
        or (kind == "JPEG" and image.mode in ("RGB", "L"))
    ) and orientation in (1, None)
    if stored and not keep:
        raise ImageError(f"{name} in the package is not in stored form.")
    if not keep:
        upright = ImageOps.exif_transpose(image)
        has_alpha = upright.mode in ("RGBA", "LA", "PA") or "transparency" in upright.info
        upright = upright.convert("RGBA" if has_alpha else "RGB")
        buffer = io.BytesIO()
        upright.save(buffer, format="PNG", optimize=False)
        data, kind, image = buffer.getvalue(), "PNG", upright
        width, height = image.size
    rgba = image.convert("RGBA")
    alpha = rgba.getchannel("A")
    has_alpha = alpha.getextrema()[0] < 255
    small = np.asarray(rgba.resize((max(1, min(64, width)), max(1, min(64, height)))), float)
    opaque = small[small[..., 3] > 0][:, :3]
    mean = tuple(
        round(float(v) / 255.0, 4) for v in (opaque.mean(axis=0) if len(opaque) else (0, 0, 0))
    )
    image_format = "png" if kind == "PNG" else "jpeg"
    return ImageAsset(
        id=hashlib.sha256(data).hexdigest(),
        data=bytes(data),
        format=image_format,
        width=width,
        height=height,
        name=name,
        mean_color=mean,  # type: ignore[arg-type]
        has_alpha=has_alpha,
    )


def _check_size(name: str, width: int, height: int) -> None:
    if width < 1 or height < 1:
        raise ImageError(f"{name} has no pixels.")
    if max(width, height) > MAX_IMAGE_SIDE or width * height > MAX_IMAGE_PIXELS:
        raise ImageError(
            f"{name} is {width} × {height} pixels; pictures up to {MAX_IMAGE_SIDE} pixels "
            f"per side and {MAX_IMAGE_PIXELS // 1_000_000} megapixels are supported."
        )
