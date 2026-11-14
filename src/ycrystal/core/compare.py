"""Compare two structures independently of atom order and periodic wrapping.

Lattice matrices are compared directly (same orientation required). Atoms are matched
one-to-one by element and by fractional position modulo lattice translations. When one
description uses a conventional and the other a primitive cell, transform one of them
explicitly first (e.g. with :func:`supercell`) and record the transformation.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ycrystal.core.structure import Structure


@dataclass(frozen=True)
class Comparison:
    equivalent: bool
    max_cell_deviation: float  # Å, largest |Δ| of a lattice-matrix element
    max_position_deviation: float  # Å, largest distance between matched atoms
    message: str


def compare_structures(a: Structure, b: Structure, tolerance: float = 1e-4) -> Comparison:
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
            return Comparison(False, cell_dev, float(distances[best]),
                              f"atom {i + 1} ({symbol}) has no partner within {tolerance} Å")
        used[candidates[best]] = True
        worst = max(worst, float(distances[best]))
    return Comparison(True, cell_dev, worst, "equivalent")


def supercell(structure: Structure, matrix: np.ndarray) -> Structure:
    """Structure in the cell ``matrix @ structure.cell`` (integer matrix, det ≥ 1)."""
    from ase.build import make_supercell

    atoms = make_supercell(structure.to_ase(), np.asarray(matrix), wrap=True)
    return Structure.from_ase(atoms)
