"""Scientific structure data, kept separate from display state.

A [`Structure`][ycrystal.core.structure.Structure] records what a structure file
describes: the lattice, Cartesian atomic positions, elements, species labels, site
occupancies, per-axis movable flags, and import provenance. Display choices such as
boundary images, hidden atoms, radii, and colours belong to
[`SceneSettings`][ycrystal.core.scene.SceneSettings] and never change a structure.

The coordinate arrays of a structure are read-only copies, so viewing, navigating,
hiding atoms, or rendering cannot change scientific coordinates by accident.
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
    """A periodic or molecular structure in Cartesian ångström coordinates.

    The constructor validates its arguments and copies every array into a new,
    read-only NumPy array, so later changes to the caller's arrays do not affect the
    structure and the stored arrays cannot be modified in place. To change a field,
    create a new structure with [`replace`][ycrystal.core.structure.Structure.replace].

    Attributes
    ----------
    cell
        Lattice matrix in Å, shape ``(3, 3)``. Rows are the lattice vectors a, b, and c,
        so the fractional row vector ``f`` is at Cartesian position ``f @ cell``. A
        singular matrix (for example all zeros) means the structure has no cell; see
        [`has_cell`][ycrystal.core.structure.Structure.has_cell].
    positions
        Cartesian atomic positions in Å, shape ``(N, 3)``, in input order. Positions
        are stored as given: atoms outside the cell are not wrapped.
    numbers
        Atomic numbers, shape ``(N,)``, each between 1 and 118. They define the element
        of each atom, and with it the default colour and radius.
    labels
        One species label per atom as written in the source (for example ``"Fe1"`` or
        ``"O_2"``), kept separately from the element in `numbers`. Readers use the
        element symbol when the source has no separate label.
    pbc
        Periodicity along a, b, and c. Display code adds boundary images only along
        periodic axes.
    metadata
        Free-form provenance. The file readers store a ``"source"`` dictionary here
        (path, format, SHA-256 checksum, import time, and reader details).
    occupancy
        Site occupancy of each atom, shape ``(N,)``, nominally in ``(0, 1]``. The
        constructor tolerates values up to ``1 + 1e-6`` without clipping. Passing
        ``None`` stores 1 for every atom, so the stored value is never ``None``.
    movable
        Per-atom, per-axis "may move" flags, shape ``(N, 3)``, from VASP selective
        dynamics or Quantum ESPRESSO ``if_pos``; ``None`` if the source had none.
        Ycrystal displays and saves these flags but never moves atoms.

    Raises
    ------
    ValueError
        If `cell` is not ``(3, 3)``, `positions` is not ``(N, 3)``, the number of
        atomic numbers, labels, occupancies, or movable rows differs from ``N``, an
        atomic number is outside 1 to 118, or an occupancy is non-positive or above
        ``1 + 1e-6``.

    Notes
    -----
    The dataclass is frozen and compares by identity (``eq=False``): two structures with
    equal arrays are not ``==``. Use
    [`compare_structures`][ycrystal.core.compare.compare_structures] for a scientific
    comparison.

    `metadata` is the one mutable part: the dictionary is stored as given, not
    copied, and its contents can still be changed.

    The constructor checks array shapes and the ranges described above, but does
    not reject non-finite coordinates or occupancies, or validate the length of
    `pbc`. Callers constructing structures directly must supply finite scientific
    data and three periodic flags.

    Examples
    --------
    >>> import numpy as np
    >>> from ycrystal.core.structure import Structure
    >>> rocksalt = Structure(
    ...     cell=np.eye(3) * 4.2,
    ...     positions=[[0.0, 0.0, 0.0], [2.1, 2.1, 2.1]],
    ...     numbers=[12, 8],
    ...     labels=["Mg", "O1"],
    ... )
    >>> rocksalt.symbols, rocksalt.labels
    (('Mg', 'O'), ('Mg', 'O1'))
    >>> rocksalt.positions.flags.writeable
    False
    """

    cell: np.ndarray
    positions: np.ndarray
    numbers: np.ndarray
    labels: tuple[str, ...]
    pbc: tuple[bool, bool, bool] = (True, True, True)
    metadata: dict[str, Any] = field(default_factory=dict)
    occupancy: np.ndarray | None = None
    movable: np.ndarray | None = None

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
        occupancy = np.ones(n_atoms) if self.occupancy is None else self.occupancy
        occupancy = _frozen(occupancy, (n_atoms,), float)
        if np.any(occupancy <= 0) or np.any(occupancy > 1 + 1e-6):
            raise ValueError("occupancies must be in (0, 1]")
        object.__setattr__(self, "occupancy", occupancy)
        if self.movable is not None:
            object.__setattr__(self, "movable", _frozen(self.movable, (n_atoms, 3), bool))

    @classmethod
    def from_ase(cls, atoms: Atoms, labels: list[str] | None = None, **metadata: Any) -> Structure:
        """Create a structure from an ASE ``Atoms`` object.

        Parameters
        ----------
        atoms
            Source structure. Its cell, positions (Å), atomic numbers, and periodic
            flags are copied; `atoms` itself is not modified.
        labels
            Species labels, one per atom. ``None`` uses the chemical symbols.
        **metadata
            Keyword arguments stored as the new structure's `metadata`, for example
            ``source={"format": "sample", "name": "..."}``.

        Returns
        -------
        Structure
            A new structure with occupancy 1 for every atom and no movable flags.

        Notes
        -----
        ASE constraints, tags, magnetic moments, and other per-atom arrays are not
        transferred.
        """
        symbols = atoms.get_chemical_symbols()
        return cls(
            cell=atoms.cell.array,
            positions=atoms.positions,
            numbers=atoms.numbers,
            labels=tuple(labels if labels is not None else symbols),
            pbc=tuple(atoms.pbc),
            metadata=dict(metadata),
        )

    def replace(self, **changes: Any) -> Structure:
        """Return a new structure with some fields replaced.

        Parameters
        ----------
        **changes
            New values for any of the fields ``cell``, ``positions``, ``numbers``,
            ``labels``, ``pbc``, ``metadata``, ``occupancy``, and ``movable``.

        Returns
        -------
        Structure
            A new structure, validated and copied by the constructor as usual. Unless a
            new ``metadata`` is given, it receives a shallow copy of this structure's
            metadata.

        Raises
        ------
        ValueError
            If the combined fields are inconsistent, for example new ``positions`` with
            a different number of atoms than the existing ``labels``.
        TypeError
            If `changes` names something that is not a field.
        """
        values = {
            "cell": self.cell,
            "positions": self.positions,
            "numbers": self.numbers,
            "labels": self.labels,
            "pbc": self.pbc,
            "metadata": dict(self.metadata),
            "occupancy": self.occupancy,
            "movable": self.movable,
        }
        values.update(changes)
        return Structure(**values)

    def to_ase(self) -> Atoms:
        """Return an ASE ``Atoms`` object with the same cell, positions, and elements.

        Returns
        -------
        ase.Atoms
            A new object with writable copies of the cell, positions, atomic numbers,
            and periodic flags. Labels, occupancies, movable flags, and metadata are
            not transferred.
        """
        return Atoms(numbers=self.numbers, positions=self.positions, cell=self.cell, pbc=self.pbc)

    def __len__(self) -> int:
        return int(self.positions.shape[0])

    @property
    def symbols(self) -> tuple[str, ...]:
        """Element symbols, one per atom, derived from `numbers`."""
        return tuple(chemical_symbols[z] for z in self.numbers)

    @property
    def has_cell(self) -> bool:
        """Whether the cell is non-singular (``|det(cell)| > 1e-9`` Å³).

        Structures without a cell are drawn without cell edges and without boundary
        images.
        """
        return bool(abs(np.linalg.det(self.cell)) > 1e-9)

    def composition(self) -> str:
        """Return the formula with elements in order of first appearance.

        Returns
        -------
        str
            Element symbols followed by their total atom counts (a count of 1 is
            omitted), for example ``"SrTiO3"``. The formula is not reduced: eight
            silicon atoms give ``"Si8"``.
        """
        counts = Counter(self.symbols)
        return "".join(f"{s}{n if n > 1 else ''}" for s, n in counts.items())
