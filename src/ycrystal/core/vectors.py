"""Atom-attached vectors: records, attachment, appearance, and arrow geometry (FR-VECTOR-01).

A vector is an illustration attached to an atom: a direction or a magnetic moment
given by its Cartesian components in the structure's own right-handed frame (the frame
of the atom positions, in Å). The camera never changes stored values, and nothing here
computes or infers moments.

Attachment has two levels:

- a **source default** applies to every displayed periodic image of a source atom (its
  Cartesian components are the same in every cell: no alternating signs or propagation
  vector are inferred);
- an **image override** applies to one displayed instance
  [`AtomId`][ycrystal.core.scene.AtomId] and takes precedence over the source default;
  an override can also *suppress* the arrow on that image.

Each displayed atom has at most one effective vector. A zero vector (modulus at most
[`ZERO_MODULUS`][ycrystal.core.vectors.ZERO_MODULUS]) is valid data and draws no arrow.

[`resolve_arrows`][ycrystal.core.vectors.resolve_arrows] turns records into
[`Arrow`][ycrystal.core.vectors.Arrow] geometry once; the live view and the POV-Ray
writer both draw that geometry.

Examples
--------
>>> from ycrystal.core.vectors import VectorRecord, VectorStyle, arrow_for
>>> up = VectorRecord((0.0, 0.0, 2.2))  # 2.2 μB along +z
>>> up.modulus, up.unit_text
(2.2, 'μB')
>>> arrow = arrow_for((0, (0, 0, 0)), (1.0, 1.0, 1.0), up, VectorStyle(length=2.0))
>>> arrow.tail, arrow.tip  # centred: r ∓ L u / 2
((1.0, 1.0, 0.0), (1.0, 1.0, 2.0))
>>> proportional = VectorStyle(length_mode="proportional", scale=0.5, placement="tail")
>>> arrow_for((0, (0, 0, 0)), (0.0, 0.0, 0.0), up, proportional).tip  # L = 0.5 × 2.2
(0.0, 0.0, 1.1)
>>> arrow_for((0, (0, 0, 0)), (0.0, 0.0, 0.0), VectorRecord((0, 0, 0)), VectorStyle()) is None
True
"""

from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import dataclass, replace

import numpy as np

AtomId = tuple[int, tuple[int, int, int]]
RGB = tuple[float, float, float]
Key = tuple[str, object]
"""A record key: ``("source", index)`` or ``("image", atom_id)``."""

MEANINGS: dict[str, tuple[str, str]] = {
    "direction": ("Direction", ""),
    "moment": ("Magnetic moment", "μB"),
}
"""Vector meanings: ``id → (name, unit)``. Directions are dimensionless illustrations;
magnetic moments are in Bohr magnetons. Other meanings are reserved for later."""

PLACEMENTS = ("centred", "tail")
"""``"centred"``: the arrow's midpoint is the atom centre; ``"tail"``: the arrow starts
at the atom centre."""

LENGTH_MODES = ("uniform", "proportional")
"""``"uniform"``: every arrow is `VectorStyle.length` long; ``"proportional"``: the
length is `VectorStyle.scale` times the modulus."""

ZERO_MODULUS = 1e-9
"""Vectors whose modulus is at most this (in their own units) are zero vectors: stored,
but drawn without an arrow (no direction is invented)."""

MIN_ARROW_LENGTH = 1e-4
"""Arrows shorter than this (Å) are not drawn (no degenerate cylinders or cones)."""

MAX_HEAD_FRACTION = 0.6
"""Short-arrow policy: the head is at most this fraction of the total length. When the
chosen head length is longer, the whole cross-section (head length, head radius, and
shaft radius) shrinks by the same factor; the total length (and every physical value)
stays as resolved."""

STYLE_RANGES = {
    "length": (0.05, 50.0),
    "scale": (0.01, 20.0),
    "shaft_radius": (0.005, 2.0),
    "head_length": (0.01, 5.0),
    "head_radius": (0.01, 3.0),
}
"""Allowed ranges of the arrow dimensions (Å, or Å per unit for `scale`)."""


def _finite_triple(values: Iterable[float], name: str) -> tuple[float, float, float]:
    try:
        triple = tuple(float(v) for v in values)
    except (TypeError, ValueError):
        raise ValueError(f"{name} must be three numbers") from None
    if len(triple) != 3:
        raise ValueError(f"{name} must be three numbers")
    if not all(math.isfinite(v) for v in triple):
        raise ValueError(f"{name} must be finite")
    return (triple[0], triple[1], triple[2])


@dataclass(frozen=True)
class VectorRecord:
    """One stored vector.

    Attributes
    ----------
    components
        Cartesian components in the structure frame: μB for magnetic moments,
        dimensionless for directions. Finite; zero is allowed.
    meaning
        One of [`MEANINGS`][ycrystal.core.vectors.MEANINGS].
    visible
        Whether the arrow is drawn (the data stay either way).

    Raises
    ------
    ValueError
        For non-finite components or an unknown meaning.
    """

    components: tuple[float, float, float]
    meaning: str = "moment"
    visible: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(self, "components", _finite_triple(self.components, "components"))
        if self.meaning not in MEANINGS:
            raise ValueError(f"meaning must be one of {tuple(MEANINGS)}")
        object.__setattr__(self, "visible", bool(self.visible))

    @property
    def modulus(self) -> float:
        """Euclidean length of the components (in the record's unit)."""
        return float(math.hypot(*self.components))

    @property
    def is_zero(self) -> bool:
        """Whether this is a zero vector (no arrow)."""
        return self.modulus <= ZERO_MODULUS

    @property
    def unit_text(self) -> str:
        """Unit symbol: ``"μB"`` or ``""``."""
        return MEANINGS[self.meaning][1]

    @property
    def meaning_name(self) -> str:
        """Name of the meaning for the interface."""
        return MEANINGS[self.meaning][0]

    def reversed(self) -> VectorRecord:
        """Return the record with negated components."""
        x, y, z = self.components
        return replace(self, components=(-x + 0.0, -y + 0.0, -z + 0.0))

    def text(self, digits: int = 3) -> str:
        """Return ``"(x, y, z) μB, |v| = m μB"`` for the interface."""
        unit = f" {self.unit_text}" if self.unit_text else ""
        comps = ", ".join(f"{c:.{digits}f}" for c in self.components)
        return f"({comps}){unit}, |v| = {self.modulus:.{digits}f}{unit}"


@dataclass(frozen=True)
class VectorSet:
    """Source defaults and image overrides of a structure's vectors.

    Attributes
    ----------
    sources
        Sorted ``(source index, record)`` pairs: defaults for every image of a source
        atom.
    images
        Sorted ``(atom_id, record or None)`` pairs: overrides for one displayed
        instance; ``None`` suppresses the arrow on that instance.
    """

    sources: tuple[tuple[int, VectorRecord], ...] = ()
    images: tuple[tuple[AtomId, VectorRecord | None], ...] = ()

    def __post_init__(self) -> None:
        sources = {}
        for index, record in self.sources:
            if int(index) < 0 or not isinstance(record, VectorRecord):
                raise ValueError("source vectors need a non-negative index and a record")
            sources[int(index)] = record
        images = {}
        for atom_id, record in self.images:
            source, image = atom_id
            key = (int(source), tuple(int(n) for n in image))
            if key[0] < 0 or len(key[1]) != 3:
                raise ValueError("image vectors need an atom id (index, (na, nb, nc))")
            if record is not None and not isinstance(record, VectorRecord):
                raise ValueError("image vectors need a record or None (suppressed)")
            images[key] = record
        object.__setattr__(self, "sources", tuple(sorted(sources.items())))
        object.__setattr__(self, "images", tuple(sorted(images.items())))

    def __len__(self) -> int:
        return len(self.sources) + len(self.images)

    # ----- lookup ---------------------------------------------------------------------
    def effective(self, atom_id: AtomId) -> VectorRecord | None:
        """Return the record that applies to a displayed instance, or ``None``.

        An image override wins over the source default; a suppressing override gives
        ``None`` even if the source has a default.
        """
        images = dict(self.images)
        key = (int(atom_id[0]), tuple(int(n) for n in atom_id[1]))
        if key in images:
            return images[key]
        return dict(self.sources).get(key[0])

    def keys(self) -> list[Key]:
        """All record keys: source defaults first, then image overrides."""
        return [("source", s) for s, _ in self.sources] + [("image", a) for a, _ in self.images]

    def record(self, key: Key) -> VectorRecord | None:
        """Return the record of a key (``None`` for a suppression)."""
        kind, target = key
        table = dict(self.sources) if kind == "source" else dict(self.images)
        return table[target]

    def overrides_of(self, sources: Iterable[int]) -> list[AtomId]:
        """Image overrides (including suppressions) of the given source atoms."""
        wanted = set(sources)
        return [atom_id for atom_id, _ in self.images if atom_id[0] in wanted]

    # ----- edits (each returns a new set) -----------------------------------------------
    def with_sources(self, sources: Iterable[int], record: VectorRecord | None) -> VectorSet:
        """Set (or remove with ``None``) the default of source atoms."""
        table = dict(self.sources)
        for index in sources:
            if record is None:
                table.pop(int(index), None)
            else:
                table[int(index)] = record
        return replace(self, sources=tuple(table.items()))

    def with_images(
        self, atom_ids: Iterable[AtomId], record: VectorRecord | None, *, suppress: bool = False
    ) -> VectorSet:
        """Set overrides of instances: a record, a suppression, or removal.

        ``record=None`` removes the overrides (the source default applies again)
        unless ``suppress`` is true, which stores suppressions.
        """
        table = dict(self.images)
        for atom_id in atom_ids:
            key = (int(atom_id[0]), tuple(int(n) for n in atom_id[1]))
            if record is None and not suppress:
                table.pop(key, None)
            else:
                table[key] = record
        return replace(self, images=tuple(table.items()))

    def without(self, keys: Iterable[Key]) -> VectorSet:
        """Remove records by key."""
        drop = set(_freeze(k) for k in keys)
        return VectorSet(
            tuple(i for i in self.sources if ("source", i[0]) not in drop),
            tuple(i for i in self.images if ("image", i[0]) not in drop),
        )

    def mapped(self, keys: Iterable[Key], change: object) -> VectorSet:
        """Apply ``change(record) -> record`` to the records of some keys (not suppressions)."""
        wanted = set(_freeze(k) for k in keys)
        sources = tuple((s, change(r) if ("source", s) in wanted else r) for s, r in self.sources)
        images = tuple(
            (a, change(r) if ("image", a) in wanted and r is not None else r)
            for a, r in self.images
        )
        return VectorSet(sources, images)


def _freeze(key: Key) -> Key:
    kind, target = key
    if kind == "image":
        source, image = target
        return (kind, (int(source), tuple(int(n) for n in image)))
    return (kind, int(target))


@dataclass(frozen=True)
class VectorStyle:
    """Appearance shared by all arrows (graphical only; never changes vector data).

    Attributes
    ----------
    visible
        Whether arrows are drawn at all.
    placement
        One of [`PLACEMENTS`][ycrystal.core.vectors.PLACEMENTS].
    length_mode
        One of [`LENGTH_MODES`][ycrystal.core.vectors.LENGTH_MODES].
    length
        Total arrow length in Å for uniform length (head included).
    scale
        Å per μB (moments) or Å per unit (directions) for proportional length.
    shaft_radius, head_length, head_radius
        Arrow dimensions in Å (see
        [`MAX_HEAD_FRACTION`][ycrystal.core.vectors.MAX_HEAD_FRACTION] for short arrows).
    color
        Arrow colour (sRGB, 0–1), independent of the host atom; materials with their
        own pigment ignore it.
    material
        Material id (built-in or custom variant) of the arrows.

    Raises
    ------
    ValueError
        For unknown modes or dimensions outside
        [`STYLE_RANGES`][ycrystal.core.vectors.STYLE_RANGES].
    """

    visible: bool = True
    placement: str = "centred"
    length_mode: str = "uniform"
    length: float = 2.6
    scale: float = 0.6
    shaft_radius: float = 0.08
    head_length: float = 0.5
    head_radius: float = 0.2
    color: RGB = (0.80, 0.10, 0.10)
    material: str = "satin"

    def __post_init__(self) -> None:
        if self.placement not in PLACEMENTS:
            raise ValueError(f"placement must be one of {PLACEMENTS}")
        if self.length_mode not in LENGTH_MODES:
            raise ValueError(f"length_mode must be one of {LENGTH_MODES}")
        for name, (low, high) in STYLE_RANGES.items():
            value = float(getattr(self, name))
            if not (math.isfinite(value) and low <= value <= high):
                raise ValueError(f"vector {name} must be between {low} and {high}")
            object.__setattr__(self, name, value)
        rgb = _finite_triple(self.color, "vector colour")
        if not all(0.0 <= c <= 1.0 for c in rgb):
            raise ValueError("vector colour components must be between 0 and 1")
        object.__setattr__(self, "color", rgb)
        object.__setattr__(self, "visible", bool(self.visible))


@dataclass(frozen=True)
class Arrow:
    """Resolved geometry of one arrow (shared by the live view and POV-Ray).

    Attributes
    ----------
    host
        The displayed atom it belongs to.
    components, meaning
        The vector it shows (for comments and the interface).
    tail, base, tip
        Start of the shaft, base of the head (end of the shaft), and tip, in Å.
    shaft_radius, head_radius
        Radii in Å after the short-arrow policy.
    """

    host: AtomId
    components: tuple[float, float, float]
    meaning: str
    tail: tuple[float, float, float]
    base: tuple[float, float, float]
    tip: tuple[float, float, float]
    shaft_radius: float
    head_radius: float

    @property
    def length(self) -> float:
        """Total length tail → tip in Å."""
        return float(np.linalg.norm(np.subtract(self.tip, self.tail)))


def arrow_length(record: VectorRecord, style: VectorStyle) -> float:
    """Return the total arrow length in Å (0 for a zero vector)."""
    if record.is_zero:
        return 0.0
    return style.length if style.length_mode == "uniform" else style.scale * record.modulus


def _triple(v: np.ndarray) -> tuple[float, float, float]:
    return (float(v[0]), float(v[1]), float(v[2]))


def arrow_for(
    host: AtomId, position: Iterable[float], record: VectorRecord, style: VectorStyle
) -> Arrow | None:
    """Return the arrow of one record at an atom position, or ``None`` if none is drawn.

    No arrow for a zero vector, an arrow shorter than
    [`MIN_ARROW_LENGTH`][ycrystal.core.vectors.MIN_ARROW_LENGTH], or a hidden record.
    For unit direction ``u`` and length ``L``: centred endpoints ``r ∓ L u / 2``; tail
    placement ``r`` and ``r + L u``. The head is part of ``L``.
    """
    if not record.visible:
        return None
    length = arrow_length(record, style)
    if length < MIN_ARROW_LENGTH:
        return None
    r = np.asarray(position, dtype=float)
    u = np.asarray(record.components, dtype=float) / record.modulus
    tail = r - 0.5 * length * u if style.placement == "centred" else r
    tip = tail + length * u
    factor = min(1.0, MAX_HEAD_FRACTION * length / style.head_length)
    head = style.head_length * factor
    return Arrow(
        host=host,
        components=record.components,
        meaning=record.meaning,
        tail=_triple(tail),
        base=_triple(tip - head * u),
        tip=_triple(tip),
        shaft_radius=style.shaft_radius * factor,
        head_radius=style.head_radius * factor,
    )


def resolve_arrows(
    atom_ids: Iterable[AtomId],
    positions: np.ndarray,
    vectors: VectorSet,
    style: VectorStyle,
) -> tuple[Arrow, ...]:
    """Return the arrows of the displayed atoms (in display order).

    Hidden atoms and images that are not displayed simply have no position here, so
    their records stay stored but draw nothing.
    """
    if not style.visible or not len(vectors):
        return ()
    sources, images = dict(vectors.sources), dict(vectors.images)
    arrows = []
    for atom_id, position in zip(atom_ids, positions, strict=True):
        record = images[atom_id] if atom_id in images else sources.get(atom_id[0])
        if record is None:
            continue
        arrow = arrow_for(atom_id, position, record, style)
        if arrow is not None:
            arrows.append(arrow)
    return tuple(arrows)


def arrow_spheres(arrows: Iterable[Arrow]) -> tuple[np.ndarray, np.ndarray]:
    """Return points and radii whose spheres enclose the arrows (for framing bounds).

    Each arrow contributes its tail (shaft radius), head base (head radius), and tip
    (radius 0); the arrow lies inside the convex hull of these spheres.
    """
    points, radii = [], []
    for arrow in arrows:
        points += [arrow.tail, arrow.base, arrow.tip]
        radii += [arrow.shaft_radius, arrow.head_radius, 0.0]
    return np.array(points, dtype=float).reshape(-1, 3), np.array(radii, dtype=float)
