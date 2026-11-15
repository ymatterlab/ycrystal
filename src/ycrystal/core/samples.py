"""Small synthetic sample structures (no external data).

The ``ycrystal`` command shows one of these when it starts without a file
(``--sample perovskite``, the default, or ``--sample triclinic``).
"""

from __future__ import annotations

from collections.abc import Callable

from ase import Atoms
from ase.geometry import cellpar_to_cell

from ycrystal.core.structure import Structure


def perovskite_srtio3() -> Structure:
    """Return cubic SrTiO3, one formula unit (5 atoms, a = 3.905 Å).

    Sr is at the origin, Ti at the cell centre, and O at the three face centres
    ``(½, ½, 0)``, ``(½, 0, ½)``, and ``(0, ½, ½)``. With boundary images the corner Sr
    is drawn 8 times and every O twice, so 15 balls are shown.

    Returns
    -------
    Structure
        A new structure; ``metadata["source"]`` records ``{"format": "sample", ...}``.
    """
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
    """Return a low-symmetry triclinic cell with distinguishable atoms.

    The cell has a, b, c = 4.6, 5.3, 6.1 Å and α, β, γ = 78°, 84°, 71°, with a along x
    and b in the xy plane. It contains one atom each of O, Fe, S, Cl, and N at general
    positions, none on a cell boundary, so exactly 5 balls are shown. Because every
    atom differs and the arrangement has no symmetry, a mirrored or rotated rendering
    is visibly wrong, which makes the structure useful for checking camera export.

    Returns
    -------
    Structure
        A new structure; ``metadata["source"]`` records ``{"format": "sample", ...}``.
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
"""Sample factories by the name accepted by ``ycrystal --sample``."""
