"""Compare two structures independently of atom order and periodic wrapping.

Lattice matrices are compared directly (same orientation required). Atoms are matched
one-to-one by element and by fractional position modulo lattice translations. When one
description uses a conventional and the other a primitive cell, transform one of them
explicitly first (for example with [`supercell`][ycrystal.core.compare.supercell]) and
record the transformation.

These helpers check reader equivalence in the test suite; the application does not use
them to display anything.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ycrystal.core.structure import Structure


@dataclass(frozen=True)
class Comparison:
    """Result of [`compare_structures`][ycrystal.core.compare.compare_structures].

    Attributes
    ----------
    equivalent
        Whether the structures agree within the tolerance.
    max_cell_deviation
        Largest absolute difference between corresponding lattice-matrix elements, in
        Å; infinite if the atom counts or elements already differ.
    max_position_deviation
        Largest distance in Å between matched atoms, or the distance of the first atom
        without a partner; infinite if positions were not compared.
    message
        ``"equivalent"``, or a short reason for the difference.
    """

    equivalent: bool
    max_cell_deviation: float  # Å, largest |Δ| of a lattice-matrix element
    max_position_deviation: float  # Å, largest distance between matched atoms
    message: str


def compare_structures(a: Structure, b: Structure, tolerance: float = 1e-4) -> Comparison:
    """Check whether two structures describe the same crystal in the same cell.

    The checks run in order and stop at the first difference: atom count, multiset of
    elements, lattice matrices element by element, and finally atom positions. Each atom
    of `a` is matched to the nearest unused atom of `b` with the same element, using
    fractional coordinates in the cell of `a` with whole lattice translations removed;
    the remaining offset is measured in Å.

    Parameters
    ----------
    a
        First structure.
    b
        Second structure.
    tolerance
        Largest accepted deviation in Å, for lattice-matrix elements and for atom
        positions.

    Returns
    -------
    Comparison
        The verdict with the largest deviations found.

    Raises
    ------
    numpy.linalg.LinAlgError
        If the first cell is singular and the checks reach position matching.

    Notes
    -----
    Matching is greedy, which is reliable for atoms that are much farther apart than
    `tolerance`. Lattice translations are removed along all three axes, whatever the
    periodic flags. Labels, occupancies, movable flags, and metadata are not compared.
    Fractional differences are wrapped component by component; this is not a general
    minimum-image search for highly skewed cells.
    """
    if len(a) != len(b):
        return Comparison(False, np.inf, np.inf, f"{len(a)} atoms vs {len(b)} atoms")
    if sorted(a.symbols) != sorted(b.symbols):
        return Comparison(False, np.inf, np.inf, f"{a.composition()} vs {b.composition()}")
    cell_dev = float(np.max(np.abs(a.cell - b.cell)))
    if cell_dev > tolerance:
        return Comparison(False, cell_dev, np.inf, f"lattice matrices differ by {cell_dev:.3g} Å")
    inv = np.linalg.inv(a.cell)
    frac_a = a.positions @ inv
    frac_b = b.positions @ inv
    used = np.zeros(len(b), dtype=bool)
    worst = 0.0
    for i, (symbol, fa) in enumerate(zip(a.symbols, frac_a, strict=True)):
        candidates = [j for j in range(len(b)) if not used[j] and b.symbols[j] == symbol]
        delta = frac_b[candidates] - fa
        delta -= np.round(delta)  # remove whole lattice translations
        distances = np.linalg.norm(delta @ a.cell, axis=1)
        best = int(np.argmin(distances))
        if distances[best] > tolerance:
            return Comparison(
                False,
                cell_dev,
                float(distances[best]),
                f"atom {i + 1} ({symbol}) has no partner within {tolerance} Å",
            )
        used[candidates[best]] = True
        worst = max(worst, float(distances[best]))
    return Comparison(True, cell_dev, worst, "equivalent")


def supercell(structure: Structure, matrix: np.ndarray) -> Structure:
    """Return the same crystal described in the cell ``matrix @ structure.cell``.

    Parameters
    ----------
    structure
        Structure to transform; it is not modified.
    matrix
        Non-singular integer ``(3, 3)`` transformation. Row ``i``
        gives new lattice vector ``i`` in units of the old lattice vectors.

    Returns
    -------
    Structure
        A new structure built with ASE's ``make_supercell`` (atoms wrapped into the new
        cell). Labels are reset to element symbols; occupancies, movable flags, and
        metadata are not carried over.

    Notes
    -----
    This is a comparison helper. It is unrelated to displaying supercell repetitions,
    which Ycrystal does not implement yet.
    """
    from ase.build import make_supercell

    atoms = make_supercell(structure.to_ase(), np.asarray(matrix), wrap=True)
    return Structure.from_ase(atoms)
