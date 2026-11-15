"""Periodic bonds of a structure, independent of how it is displayed.

Bonds are searched once in the original cell with ASE's lattice-aware neighbour list
(correct for any cell shape) and stored as ``(i, j, shift)``: atom ``j`` translated by
the integer lattice vector ``shift`` is bonded to atom ``i``. Each bond is stored once
(the reverse pair ``(j, i, -shift)`` is dropped). The scene maps these bonds onto the
displayed periodic images, so every renderer receives the same explicit endpoints.

Rule: a pair of atoms is bonded when their distance is at most
``tolerance × (covalent radius A + covalent radius B)``. Element pairs can be switched
on or off; by default, metal–metal contacts are off in compounds that also contain
non-metals (e.g. no Sr–Ti "bonds" in SrTiO3), and on in metals and intermetallics.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from ase.data import covalent_radii

from ycrystal.core.structure import Structure

Pair = tuple[str, str]

#: Elements treated as non-metals (including metalloids) by the default pair rule.
NON_METALS = frozenset("H He B C N O F Ne Si P S Cl Ar Ge As Se Br Kr Sb Te I Xe At Rn".split())

MIN_BOND_LENGTH = 0.1  # Å; closer atoms are overlapping, not bonded


def pair_key(a: str, b: str) -> Pair:
    """Return the two element symbols in alphabetical order for a pair key."""
    return (a, b) if a <= b else (b, a)


@dataclass(frozen=True)
class BondSettings:
    """Rules and appearance of periodic bonds (presentation state only).

    Attributes
    ----------
    enabled
        Whether scene construction draws bonds. Candidate search itself ignores this flag.
    tolerance
        Maximum bond length as a multiple of the sum of ASE covalent radii; default 1.10.
        Accepted range is 0.5 to 2.0; the GUI exposes 0.80 to 1.50.
    radius
        Positive cylinder radius in Å; the GUI exposes 0.02 to 0.50 Å.
    overrides
        Frozen set of (element A, element B, enabled) overrides. Sort symbols
        alphabetically; unspecified pairs use the default metal/non-metal rule.

    Raises
    ------
    ValueError
        If tolerance is outside 0.5 to 2.0 or radius is non-positive.
    """

    enabled: bool = True
    tolerance: float = 1.10  # × sum of covalent radii
    radius: float = 0.12  # Å, drawn cylinder radius
    #: User choices that override the default rule: (element A, element B, enabled),
    #: with A <= B alphabetically.
    overrides: frozenset[tuple[str, str, bool]] = field(default_factory=frozenset)

    def __post_init__(self) -> None:
        if not 0.5 <= self.tolerance <= 2.0:
            raise ValueError("bond tolerance must be between 0.5 and 2.0")
        if self.radius <= 0:
            raise ValueError("bond radius must be positive")

    def pair_enabled(self, pair: Pair, elements: frozenset[str]) -> bool:
        """Return whether an alphabetically sorted pair is enabled for these elements.

        Explicit overrides take precedence over the default composition-dependent rule.
        """
        for a, b, enabled in self.overrides:
            if (a, b) == pair:
                return enabled
        return default_pair_enabled(pair, elements)

    def with_pair(self, pair: Pair, enabled: bool) -> BondSettings:
        """Return new settings overriding one alphabetically sorted element pair."""
        kept = {o for o in self.overrides if (o[0], o[1]) != pair}
        return BondSettings(
            self.enabled,
            self.tolerance,
            self.radius,
            frozenset(kept | {(pair[0], pair[1], enabled)}),
        )


def default_pair_enabled(pair: Pair, elements: frozenset[str]) -> bool:
    """Metal–metal pairs are off when the structure also contains non-metals."""
    a, b = pair
    both_metals = a not in NON_METALS and b not in NON_METALS
    has_non_metal = any(e in NON_METALS for e in elements)
    return not (both_metals and has_non_metal)


@dataclass(frozen=True, eq=False)
class PeriodicBonds:
    """Candidate bonds in the original cell, including disabled pairs.

    Attributes
    ----------
    i, j
        Source atom index arrays, each shape (K,), in input order numbering.
    shifts
        Integer image offsets for atom j, shape (K, 3). Its endpoint is
        structure.positions[j] + shifts @ structure.cell.
    lengths
        Bond lengths in Å, shape (K,).
    pairs
        Alphabetically sorted element pair for each candidate.
    enabled
        Pair-rule decisions, shape (K,), independent of the global enabled setting.

    Notes
    -----
    Arrays are not copied or made read-only by the constructor. Search results are
    sorted by i, j, and shift; reverse duplicates are omitted.
    """

    i: np.ndarray  # (K,) source atom indices
    j: np.ndarray  # (K,)
    shifts: np.ndarray  # (K, 3) integer lattice offsets of atom j
    lengths: np.ndarray  # (K,) Å
    pairs: tuple[Pair, ...]  # element pair of each bond
    enabled: np.ndarray  # (K,) bool, from the pair rule and user overrides

    def __len__(self) -> int:
        return len(self.i)


@dataclass(frozen=True)
class PairSummary:
    """Candidate counts and length range for one element pair in the original cell.

    Attributes
    ----------
    pair
        Alphabetically sorted element symbols.
    count
        Candidate bonds per original cell, including disabled candidates.
    min_length, max_length
        Shortest and longest candidate lengths in Å.
    enabled
        Whether this pair is enabled by its override or default rule.
    """

    pair: Pair
    count: int  # bonds per original cell
    min_length: float
    max_length: float
    enabled: bool


def periodic_bonds(structure: Structure, settings: BondSettings) -> PeriodicBonds:
    """Search the original structure for unique periodic bond candidates.

    Parameters
    ----------
    structure
        Scientific data, read without mutation. Periodicity follows its pbc flags;
        a structure without a cell is treated as non-periodic.
    settings
        Distance threshold and element-pair overrides. The global enabled flag and
        drawn radius do not affect the candidate search.

    Returns
    -------
    PeriodicBonds
        Candidates with lengths from 0.1 Å through tolerance times the sum of
        covalent radii, inclusive after the neighbour-list search. Disabled pairs
        remain in the result so the GUI can list and enable them.

    Notes
    -----
    ASE's lattice-aware neighbour list supports skewed cells. Keep i < j, or i == j
    with a lexicographically positive image shift, to omit reverse duplicates.
    This is a geometric display rule, not a chemical bond-order calculation.
    """
    from ase.neighborlist import neighbor_list

    n = len(structure)
    symbols = structure.symbols
    empty = PeriodicBonds(
        np.zeros(0, int),
        np.zeros(0, int),
        np.zeros((0, 3), int),
        np.zeros(0),
        (),
        np.zeros(0, bool),
    )
    if n == 0:
        return empty
    radii = covalent_radii[structure.numbers]
    cutoff = float(settings.tolerance * 2 * radii.max())
    atoms = structure.to_ase()
    if not structure.has_cell:
        atoms.pbc = False
    i, j, shifts, d = neighbor_list("ijSd", atoms, cutoff, self_interaction=False)
    keep = (d >= MIN_BOND_LENGTH) & (d <= settings.tolerance * (radii[i] + radii[j]))
    # One entry per bond: keep i < j, or i == j with a lexicographically positive shift.
    positive_shift = (shifts[:, 0] > 0) | (
        (shifts[:, 0] == 0) & ((shifts[:, 1] > 0) | ((shifts[:, 1] == 0) & (shifts[:, 2] > 0)))
    )
    keep &= (i < j) | ((i == j) & positive_shift)
    i, j, shifts, d = i[keep], j[keep], shifts[keep].astype(int), d[keep]
    pairs = tuple(pair_key(symbols[a], symbols[b]) for a, b in zip(i, j, strict=True))
    elements = frozenset(symbols)
    enabled = np.array([settings.pair_enabled(p, elements) for p in pairs], dtype=bool)
    order = np.lexsort((shifts[:, 2], shifts[:, 1], shifts[:, 0], j, i))
    return PeriodicBonds(
        i[order], j[order], shifts[order], d[order], tuple(pairs[k] for k in order), enabled[order]
    )


def summarize_pairs(bonds: PeriodicBonds) -> list[PairSummary]:
    """Return alphabetically sorted pair counts and length ranges from candidate bonds."""
    table: dict[Pair, list[float]] = {}
    enabled: dict[Pair, bool] = {}
    for pair, length, on in zip(bonds.pairs, bonds.lengths, bonds.enabled, strict=True):
        table.setdefault(pair, []).append(float(length))
        enabled[pair] = bool(on)
    return [
        PairSummary(pair, len(v), min(v), max(v), enabled[pair])
        for pair, v in sorted(table.items())
    ]
