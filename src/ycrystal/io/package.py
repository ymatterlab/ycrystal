"""ZIP packages for projects and styles that carry pictures (FR-BGIMAGE-01).

A package is a ZIP archive with one JSON document (``project.json`` or ``style.json``,
the same document a plain JSON file holds) and the pictures it refers to under
``assets/``, each named by its content identity: ``assets/<sha256>.png`` or ``.jpg``.
Files without pictures stay plain JSON. Readers recognise the two forms by content (the
ZIP signature), not by the file-name suffix.

Reading is defensive: entry names must be relative, without ``..``, backslashes, or
drive letters; sizes are limited (see the constants); every referenced picture must be
present, decode as a picture in stored form, and match its digest. Anything else is
refused with a message, and nothing is changed.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
import zipfile
from pathlib import Path
from typing import Any

from ycrystal.io.images import MAX_IMAGE_BYTES, SUFFIXES, ImageAsset, ImageError, image_from_bytes

ZIP_SIGNATURE = b"PK\x03\x04"
"""First bytes of a ZIP archive (a package); JSON files start with ``{``."""

MAX_ENTRIES = 256
"""Most entries a package may contain."""

MAX_DOCUMENT_BYTES = 256 * 1024 * 1024
"""Largest JSON document in a package, uncompressed."""

MAX_TOTAL_BYTES = 1024 * 1024 * 1024
"""Largest total uncompressed size of a package."""

_ASSET_NAME = re.compile(r"^assets/([0-9a-f]{64})\.(png|jpg)$")


class PackageError(ValueError):
    """A package cannot be read; ``str()`` explains why for the user."""


def is_package(path: str | Path) -> bool:
    """Return whether a file starts with the ZIP signature (a package)."""
    with open(path, "rb") as handle:
        return handle.read(4) == ZIP_SIGNATURE


def asset_entry(asset: ImageAsset) -> str:
    """Return the archive name of a picture: ``assets/<sha256>.png`` or ``.jpg``."""
    return f"assets/{asset.id}{SUFFIXES[asset.format]}"


def write_package(
    path: str | Path, document_name: str, document: dict[str, Any], assets: list[ImageAsset]
) -> Path:
    """Write a package atomically (temporary file in the target directory, then rename).

    The document gets an ``assets`` list describing each picture (archive path, name,
    size, format, digest). An existing file is replaced; on failure it is unchanged.

    Raises
    ------
    OSError
        If the file cannot be written.
    ValueError
        If the document cannot be written as JSON.
    """
    path = Path(path)
    unique = {asset.id: asset for asset in assets}
    document = dict(document)
    document["assets"] = [
        {
            "id": asset.id,
            "path": asset_entry(asset),
            "name": asset.name,
            "format": asset.format,
            "width": asset.width,
            "height": asset.height,
            "bytes": len(asset.data),
        }
        for asset in unique.values()
    ]
    text = json.dumps(document, indent=1, ensure_ascii=False, allow_nan=False) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".ycrystal-", suffix=".tmp", dir=path.parent)
    os.close(fd)
    try:
        with zipfile.ZipFile(tmp, "w") as archive:
            archive.writestr(document_name, text.encode("utf-8"), zipfile.ZIP_DEFLATED)
            for asset in unique.values():  # pictures are compressed already
                archive.writestr(asset_entry(asset), asset.data, zipfile.ZIP_STORED)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise
    return path


def read_package(path: str | Path, document_name: str) -> tuple[Any, dict[str, ImageAsset]]:
    """Read a package: the parsed JSON document and its pictures by identity.

    Pictures are checked but not registered.

    Raises
    ------
    PackageError
        If the archive is damaged or unsafe, too large, misses the document or a listed
        picture, or a picture is damaged or does not match its digest.
    """
    path = Path(path)
    try:
        with zipfile.ZipFile(path) as archive:
            infos = archive.infolist()
            _check_entries(infos)
            names = {info.filename: info for info in infos}
            if document_name not in names:
                raise PackageError(f"The package has no {document_name}.")
            text = _read(archive, names[document_name], MAX_DOCUMENT_BYTES)
            try:
                document = json.loads(text.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise PackageError(f"{document_name} in the package is not valid JSON.") from exc
            if not isinstance(document, dict):
                raise PackageError(f"{document_name} in the package is not a document.")
            assets: dict[str, ImageAsset] = {}
            for entry in document.get("assets") or []:
                asset = _read_asset(archive, names, entry)
                assets[asset.id] = asset
    except zipfile.BadZipFile as exc:
        raise PackageError(f"The package is damaged ({exc}).") from exc
    except OSError as exc:
        raise PackageError(f"Cannot read the package: {exc.strerror or exc}") from exc
    return document, assets


def _check_entries(infos: list[zipfile.ZipInfo]) -> None:
    if len(infos) > MAX_ENTRIES:
        raise PackageError(f"The package has more than {MAX_ENTRIES} entries.")
    total, seen = 0, set()
    for info in infos:
        name = info.filename
        parts = name.split("/")
        if (
            name.startswith("/")
            or "\\" in name
            or ":" in name
            or any(part in ("", ".", "..") for part in parts[:-1])
            or ".." in parts
        ):
            raise PackageError(f"The package contains an unsafe entry name: {name!r}.")
        if name in seen:
            raise PackageError(f"The package contains {name!r} twice.")
        seen.add(name)
        total += info.file_size
    if total > MAX_TOTAL_BYTES:
        raise PackageError("The package is too large when unpacked.")


def _read(archive: zipfile.ZipFile, info: zipfile.ZipInfo, limit: int) -> bytes:
    if info.file_size > limit:
        raise PackageError(f"{info.filename} in the package is too large.")
    with archive.open(info) as handle:
        data = handle.read(limit + 1)
    if len(data) > limit:
        raise PackageError(f"{info.filename} in the package is too large.")
    return data


def _read_asset(
    archive: zipfile.ZipFile, names: dict[str, zipfile.ZipInfo], entry: Any
) -> ImageAsset:
    if not isinstance(entry, dict):
        raise PackageError("The package lists a picture incorrectly.")
    archive_path = str(entry.get("path", ""))
    match = _ASSET_NAME.match(archive_path)
    if match is None:
        raise PackageError(f"The package lists an unexpected picture path {archive_path!r}.")
    if archive_path not in names:
        label = entry.get("name") or archive_path
        raise PackageError(f"The picture {label!r} is missing from the package.")
    data = _read(archive, names[archive_path], MAX_IMAGE_BYTES)
    digest = hashlib.sha256(data).hexdigest()
    if digest != match.group(1) or digest != entry.get("id"):
        raise PackageError(f"The picture {archive_path} in the package is damaged (digest).")
    name = str(entry.get("name") or Path(archive_path).name)
    try:
        asset = image_from_bytes(data, name, stored=True)
    except ImageError as exc:
        raise PackageError(f"The picture {name!r} in the package cannot be used: {exc}") from exc
    if asset.id != digest:  # pragma: no cover - stored form keeps the bytes
        raise PackageError(f"The picture {name!r} in the package is damaged.")
    return asset
