"""Scientific structure data, kept separate from display state.

A :class:`Structure` is immutable: its coordinate arrays are read-only, so viewing,
navigating, or rendering cannot change scientific coordinates by accident.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Any

import numpy as np
from ase import Atoms
from ase.data import chemical_symbols


def _frozen(array: Any, shape: tuple[int, ...] | None, dtype: Any) -> np.ndarray:
    result = np.array(array, dtype=dtype, copy=True)
    if shape is not None and result.shape != shape:
        raise ValueError(f"expected shape {shape}, got {result.shape}")
    result.setflags(write=False)
    return result


@dataclass(frozen=True, eq=False)
class Structure:
    """A periodic (or molecular) structure in Cartesian ångström coordinates.

    ``cell`` rows are the lattice vectors a, b, c. ``labels`` are species labels as
    given by the source (e.g. ``Fe1``), stored separately from element identities
    (``numbers``).
    """

    cell: np.ndarray
    positions: np.ndarray
    numbers: np.ndarray
    labels: tuple[str, ...]
    pbc: tuple[bool, bool, bool] = (True, True, True)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        positions = _frozen(self.positions, None, float)
        if positions.ndim != 2 or positions.shape[1] != 3:
            raise ValueError("positions must have shape (N, 3)")
        n_atoms = positions.shape[0]
        numbers = _frozen(self.numbers, (n_atoms,), int)
        if np.any(numbers < 1) or np.any(numbers >= len(chemical_symbols)):
            raise ValueError("atomic numbers out of range")
        labels = tuple(str(label) for label in self.labels)
        if len(labels) != n_atoms:
            raise ValueError("one species label per atom is required")
        object.__setattr__(self, "cell", _frozen(self.cell, (3, 3), float))
        object.__setattr__(self, "positions", positions)
        object.__setattr__(self, "numbers", numbers)
        object.__setattr__(self, "labels", labels)
        object.__setattr__(self, "pbc", tuple(bool(flag) for flag in self.pbc))

    @classmethod
    def from_ase(cls, atoms: Atoms, labels: list[str] | None = None, **metadata: Any) -> Structure:
        symbols = atoms.get_chemical_symbols()
        return cls(
            cell=atoms.cell.array,
            positions=atoms.positions,
            numbers=atoms.numbers,
            labels=tuple(labels if labels is not None else symbols),
            pbc=tuple(atoms.pbc),
            metadata=dict(metadata),
        )

    def to_ase(self) -> Atoms:
        return Atoms(
            numbers=self.numbers, positions=self.positions, cell=self.cell, pbc=self.pbc
        )

    def __len__(self) -> int:
        return int(self.positions.shape[0])

    @property
    def symbols(self) -> tuple[str, ...]:
        return tuple(chemical_symbols[z] for z in self.numbers)

    @property
    def has_cell(self) -> bool:
        return bool(abs(np.linalg.det(self.cell)) > 1e-9)

    def composition(self) -> str:
        """Formula in order of first appearance, e.g. ``SrTiO3``."""
        counts = Counter(self.symbols)
        return "".join(f"{s}{n if n > 1 else ''}" for s, n in counts.items())
