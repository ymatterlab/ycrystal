"""Small synthetic sample structures (no external data)."""

from __future__ import annotations

from collections.abc import Callable

from ase import Atoms
from ase.geometry import cellpar_to_cell

from ycrystal.core.structure import Structure


def perovskite_srtio3() -> Structure:
    """Cubic ABO3 perovskite (SrTiO3, a = 3.905 Å), one formula unit."""
    atoms = Atoms(
        "SrTiO3",
        scaled_positions=[
            (0.0, 0.0, 0.0),
            (0.5, 0.5, 0.5),
            (0.5, 0.5, 0.0),
            (0.5, 0.0, 0.5),
            (0.0, 0.5, 0.5),
        ],
        cell=[3.905, 3.905, 3.905],
        pbc=True,
    )
    return Structure.from_ase(atoms, source={"format": "sample", "name": "SrTiO3 cubic perovskite"})


def triclinic_marker() -> Structure:
    """Low-symmetry triclinic cell with distinguishable atoms.

    Every atom has a different element and an asymmetric position, so a mirrored
    or rotated rendering is visibly wrong. Useful for checking camera export.
    """
    cell = cellpar_to_cell([4.6, 5.3, 6.1, 78.0, 84.0, 71.0])
    atoms = Atoms(
        "OFeSClN",
        scaled_positions=[
            (0.10, 0.15, 0.20),
            (0.55, 0.30, 0.25),
            (0.25, 0.70, 0.40),
            (0.80, 0.75, 0.65),
            (0.35, 0.25, 0.80),
        ],
        cell=cell,
        pbc=True,
    )
    return Structure.from_ase(
        atoms, source={"format": "sample", "name": "low-symmetry triclinic marker cell"}
    )


SAMPLES: dict[str, Callable[[], Structure]] = {
    "perovskite": perovskite_srtio3,
    "triclinic": triclinic_marker,
}
