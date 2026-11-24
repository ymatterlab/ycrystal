"""Identify displayed bonds related by crystallographic symmetry."""

from __future__ import annotations

import numpy as np

from ycrystal.core.scene import AtomId, BondId, DisplayGeometry
from ycrystal.core.structure import Structure

SYMMETRY_TOLERANCE = 1e-3  # Å

BondClass = tuple[int, int, tuple[int, int, int]]


def _bond_class(a: AtomId, b: AtomId) -> BondClass:
    """Identify a periodic bond up to a common translation and endpoint order."""
    shift = tuple(j - i for i, j in zip(a[1], b[1], strict=True))
    reverse = tuple(-component for component in shift)
    return min((a[0], b[0], shift), (b[0], a[0], reverse))


def _space_group_classes(
    structure: Structure, selected: BondId, periodic: np.ndarray
) -> set[BondClass]:
    """Transform both endpoints by each crystallographic operation."""
    from spglib import SpglibError, get_symmetry_dataset, get_symmetry_layerdataset

    fractional = np.linalg.solve(structure.cell.T, structure.positions.T).T
    # Separation of site types preserves both the species and the site occupancy.
    site_types = (
        np.unique(
            np.column_stack((structure.numbers, np.round(structure.occupancy, 6))),
            axis=0,
            return_inverse=True,
        )[1]
        + 1
    )
    wrapped = fractional.copy()
    wrapped[:, periodic] %= 1.0
    cell = (structure.cell, wrapped, site_types)
    try:
        if periodic.all():
            dataset = get_symmetry_dataset(cell, symprec=SYMMETRY_TOLERANCE, _throw=True)
        else:
            nonperiodic = int(np.flatnonzero(~periodic)[0])
            dataset = get_symmetry_layerdataset(
                cell, aperiodic_dir=nonperiodic, symprec=SYMMETRY_TOLERANCE, _throw=True
            )
    except SpglibError:
        return set()
    if dataset is None:
        return set()

    positions = np.array([fractional[source] + image for source, image in selected])
    sites = [np.flatnonzero(site_types == site_types[source]) for source, _ in selected]
    result = set()
    for rotation, translation in zip(dataset.rotations, dataset.translations, strict=True):
        endpoints = []
        transformed = positions @ rotation.T + translation
        for point, candidates in zip(transformed, sites, strict=True):
            delta = point - fractional[candidates]
            offsets = np.zeros_like(delta)
            offsets[:, periodic] = np.rint(delta[:, periodic])
            distance = np.linalg.norm((delta - offsets) @ structure.cell, axis=1)
            matches = np.flatnonzero(distance <= SYMMETRY_TOLERANCE)
            if len(matches) != 1:
                break
            index = matches[0]
            image = tuple(int(value) for value in offsets[index])
            endpoints.append((int(candidates[index]), image))
        if len(endpoints) == 2:
            result.add(_bond_class(*endpoints))
    return result


def equivalent_displayed_bonds(
    structure: Structure, geometry: DisplayGeometry, selected: BondId
) -> tuple[BondId, ...]:
    """Return the shown bonds in the selected bond's symmetry orbit.

    Three-dimensional crystals use space-group operations and layers use
    layer-group operations. A periodic wire, or a structure whose symmetry
    cannot be determined, is matched by lattice translations. Both endpoints
    must transform together. Visibility is resolved by the supplied geometry.
    """
    classes = {_bond_class(*selected)}
    periodic = np.asarray(structure.pbc)
    if structure.has_cell and np.count_nonzero(periodic) >= 2:
        classes.update(_space_group_classes(structure, selected, periodic))
    shown = ((geometry.atom_ids[a], geometry.atom_ids[b]) for a, b in geometry.bonds)
    return tuple(pair for pair in shown if _bond_class(*pair) in classes)
