"""Repetitions, boundary images, periodic bonds, and cell edges (M2).

Expected counts are derived independently: closed-form formulas for the orthogonal
(SrTiO3), hexagonal (MgB2), and diamond (Si) examples, and brute-force distance checks
over the displayed atoms for every case, including the triclinic cell.
"""

from dataclasses import replace
from itertools import product
from pathlib import Path

import numpy as np
import pytest
from ase.data import covalent_radii

from ycrystal.core.bonds import BondSettings, default_pair_enabled, periodic_bonds, summarize_pairs
from ycrystal.core.samples import perovskite_srtio3, triclinic_marker
from ycrystal.core.scene import (
    SceneSettings,
    build_geometry,
    cell_edge_segments,
    count_displayed_atoms,
)
from ycrystal.core.structure import Structure
from ycrystal.io.readers import read_structure

FIXTURES = Path(__file__).parent / "fixtures"


def mgb2() -> Structure:
    return read_structure(FIXTURES / "MgB2.cif")


def silicon() -> Structure:
    return read_structure(FIXTURES / "Si_conventional.cif")


def brute_force_bonds(geometry, structure, bonds: BondSettings) -> set[frozenset]:
    """All displayed pairs within the bond rule, by direct distance comparison."""
    elements = frozenset(structure.symbols)
    radii = covalent_radii[[structure.numbers[i] for i, _ in geometry.atom_ids]]
    found = set()
    for p in range(len(geometry)):
        for q in range(p + 1, len(geometry)):
            d = np.linalg.norm(geometry.positions[p] - geometry.positions[q])
            pair = tuple(sorted((geometry.elements[p], geometry.elements[q])))
            if 0.1 <= d <= bonds.tolerance * (radii[p] + radii[q]) and bonds.pair_enabled(
                pair, elements
            ):
                found.add(frozenset((geometry.atom_ids[p], geometry.atom_ids[q])))
    return found


def bond_set(geometry) -> set[frozenset]:
    return {frozenset((geometry.atom_ids[a], geometry.atom_ids[b])) for a, b in geometry.bonds}


def pair_counts(geometry) -> dict[str, int]:
    counts: dict[str, int] = {}
    for a, b in geometry.bonds:
        key = "-".join(sorted((geometry.elements[a], geometry.elements[b])))
        counts[key] = counts.get(key, 0) + 1
    return counts


# ----- atom and bond counts for the reference examples ------------------------------
@pytest.mark.parametrize("n", [1, 2, 3])
def test_orthogonal_perovskite_counts(n):
    structure = perovskite_srtio3()
    geometry = build_geometry(structure, SceneSettings(repetitions=(n, n, n)))
    assert geometry.element_counts() == {"Sr": (n + 1) ** 3, "Ti": n**3, "O": 3 * n * n * (n + 1)}
    # Each Ti has its 6 O; each face-centre O has the 4 Sr of its face (Sr–Ti and
    # Sr–Sr are metal–metal contacts, off by default in this oxide).
    assert pair_counts(geometry) == {"O-Ti": 6 * n**3, "O-Sr": 12 * n * n * (n + 1)}
    assert bond_set(geometry) == brute_force_bonds(geometry, structure, BondSettings())
    assert len(geometry.bonds) == len(bond_set(geometry))  # no duplicates


@pytest.mark.parametrize("n, m", [(1, 1), (2, 2), (3, 1)])
def test_hexagonal_mgb2_counts(n, m):
    structure = mgb2()
    geometry = build_geometry(structure, SceneSettings(repetitions=(n, n, m)))
    assert geometry.element_counts() == {"Mg": (n + 1) ** 2 * (m + 1), "B": 2 * n * n * m}
    # Honeycomb B layers: 3n² - 2n bonds in an n × n parallelogram, one layer per cell
    # along c. Mg–B (2.50 Å) is just beyond 1.1 × (1.41 + 0.84) Å = 2.475 Å.
    assert pair_counts(geometry) == {"B-B": (3 * n * n - 2 * n) * m}
    assert bond_set(geometry) == brute_force_bonds(geometry, structure, BondSettings())


@pytest.mark.parametrize("n", [1, 2])
def test_diamond_silicon_counts(n):
    structure = silicon()
    geometry = build_geometry(structure, SceneSettings(repetitions=(n, n, n)))
    corners, faces, inside = (n + 1) ** 3, 3 * n * n * (n + 1), 4 * n**3
    assert len(geometry) == corners + faces + inside
    assert len(geometry.bonds) == 16 * n**3  # every tetrahedral atom has its 4 bonds
    lengths = np.linalg.norm(
        geometry.positions[geometry.bonds[:, 0]] - geometry.positions[geometry.bonds[:, 1]], axis=1
    )
    np.testing.assert_allclose(lengths, 5.431 * np.sqrt(3) / 4, atol=1e-9)


@pytest.mark.parametrize("reps", [(1, 1, 1), (2, 3, 1), (2, 2, 2)])
def test_triclinic_counts_and_bonds(reps):
    structure = triclinic_marker()
    geometry = build_geometry(structure, SceneSettings(repetitions=reps))
    assert len(geometry) == 5 * int(np.prod(reps))  # general positions: no boundary images
    assert bond_set(geometry) == brute_force_bonds(geometry, structure, BondSettings())


def test_count_estimate_matches_geometry():
    for structure in (perovskite_srtio3(), mgb2(), silicon(), triclinic_marker()):
        for reps in ((1, 1, 1), (3, 2, 1), (2, 2, 2)):
            for boundary in (True, False):
                settings = SceneSettings(repetitions=reps, boundary_images=boundary)
                assert count_displayed_atoms(structure, settings) == len(
                    build_geometry(structure, settings)
                )


def test_boundary_off_repeats_input_atoms():
    structure = perovskite_srtio3()
    geometry = build_geometry(
        structure, SceneSettings(repetitions=(2, 1, 1), boundary_images=False)
    )
    assert len(geometry) == 10
    for (source, image), position in zip(geometry.atom_ids, geometry.positions, strict=True):
        assert image[1:] == (0, 0) and image[0] in (0, 1)
        np.testing.assert_allclose(
            position, structure.positions[source] + image[0] * structure.cell[0]
        )


# ----- stable identities, reversibility, original coordinates ---------------------------------
def test_ids_are_stable_and_changes_reversible():
    structure = perovskite_srtio3()
    original = structure.positions.copy()
    small = build_geometry(structure, SceneSettings())
    large = build_geometry(structure, SceneSettings(repetitions=(3, 3, 3)))
    for atom_id, position in zip(small.atom_ids, small.positions, strict=True):
        np.testing.assert_array_equal(large.positions[large.index_of(atom_id)], position)
    again = build_geometry(structure, SceneSettings(repetitions=(1, 1, 1)))
    assert again.atom_ids == small.atom_ids
    np.testing.assert_array_equal(again.positions, small.positions)
    np.testing.assert_array_equal(again.bonds, small.bonds)
    np.testing.assert_array_equal(structure.positions, original)  # never modified


def test_hidden_ids_survive_repetition_changes():
    structure = perovskite_srtio3()
    hidden = frozenset({(0, (1, 1, 1)), (0, (2, 2, 2))})  # second exists only at ≥ 2 cells
    small = build_geometry(structure, SceneSettings(hidden=hidden))
    assert small.hidden_count == 1 and (0, (1, 1, 1)) not in small
    large = build_geometry(structure, SceneSettings(hidden=hidden, repetitions=(2, 2, 2)))
    assert large.hidden_count == 2 and (0, (2, 2, 2)) not in large
    # Bonds of hidden atoms are not drawn.
    assert all(
        large.atom_ids[a] not in hidden and large.atom_ids[b] not in hidden for a, b in large.bonds
    )


def test_non_periodic_axes_are_not_repeated():
    slab = Structure(
        cell=np.diag([4.0, 4.0, 20.0]),
        positions=[[0.5, 0.5, 5.0]],
        numbers=[6],
        labels=["C"],
        pbc=(True, True, False),
    )
    geometry = build_geometry(slab, SceneSettings(repetitions=(2, 2, 3), boundary_images=False))
    assert len(geometry) == 4
    assert {image[2] for _, image in geometry.atom_ids} == {0}


# ----- periodic bonds -------------------------------------------------------------
def test_periodic_bonds_are_unique_and_complete_for_triclinic_cell():
    structure = triclinic_marker()
    settings = BondSettings(tolerance=1.4)
    bonds = periodic_bonds(structure, settings)
    seen = set()
    for i, j, shift in zip(bonds.i, bonds.j, bonds.shifts, strict=True):
        key = frozenset({(int(i), tuple(np.zeros(3, int))), (int(j), tuple(shift))})
        reverse = frozenset({(int(j), (0, 0, 0)), (int(i), tuple(-np.asarray(shift)))})
        assert key not in seen and reverse not in seen
        seen.add(key)
    # Brute force over neighbouring cells.
    radii = covalent_radii[structure.numbers]
    expected = 0
    for a, b in product(range(len(structure)), repeat=2):
        for shift in product(range(-2, 3), repeat=3):
            d = np.linalg.norm(
                structure.positions[b] + np.array(shift) @ structure.cell - structure.positions[a]
            )
            if 0.1 <= d <= 1.4 * (radii[a] + radii[b]):
                expected += 1
    assert 2 * len(bonds) == expected  # every bond counted from both ends
    lengths = np.linalg.norm(
        structure.positions[bonds.j] + bonds.shifts @ structure.cell - structure.positions[bonds.i],
        axis=1,
    )
    np.testing.assert_allclose(lengths, bonds.lengths)


def test_default_pair_rule_and_overrides():
    oxide = frozenset({"Sr", "Ti", "O"})
    assert not default_pair_enabled(("Sr", "Ti"), oxide)
    assert default_pair_enabled(("O", "Ti"), oxide)
    assert default_pair_enabled(("Cu", "Cu"), frozenset({"Cu"}))  # metals keep bonds
    structure = perovskite_srtio3()
    summary = {s.pair: s for s in summarize_pairs(periodic_bonds(structure, BondSettings()))}
    assert summary[("O", "Ti")].enabled and summary[("O", "Ti")].count == 6
    assert not summary[("Sr", "Ti")].enabled
    no_sr_o = BondSettings().with_pair(("O", "Sr"), False)
    geometry = build_geometry(structure, SceneSettings(bonds=no_sr_o))
    assert pair_counts(geometry) == {"O-Ti": 6}
    with_sr_ti = BondSettings().with_pair(("Sr", "Ti"), True)
    assert pair_counts(build_geometry(structure, SceneSettings(bonds=with_sr_ti)))["Sr-Ti"] == 8
    assert (
        len(build_geometry(structure, SceneSettings(bonds=replace(no_sr_o, enabled=False))).bonds)
        == 0
    )


def test_bond_settings_validation_and_molecule():
    with pytest.raises(ValueError):
        BondSettings(tolerance=3.0)
    with pytest.raises(ValueError):
        SceneSettings(repetitions=(0, 1, 1))
    water = Structure(
        cell=np.zeros((3, 3)),
        positions=[[0, 0, 0], [0.96, 0, 0], [-0.24, 0.93, 0]],
        numbers=[8, 1, 1],
        labels=["O", "H", "H"],
        pbc=(False, False, False),
    )
    geometry = build_geometry(water, SceneSettings(repetitions=(3, 3, 3)))
    assert len(geometry) == 3 and len(geometry.bonds) == 2  # O–H only; H–H is 1.52 Å


# ----- cell edges -----------------------------------------------------------------
def test_cell_edge_modes():
    structure = perovskite_srtio3()
    a = structure.cell[0, 0]
    for mode in ("all", "outline", "unit"):
        assert len(cell_edge_segments(structure, SceneSettings(cell_mode=mode))) == 12
    grid = cell_edge_segments(structure, SceneSettings(repetitions=(2, 3, 1), cell_mode="all"))
    assert len(grid) == (4 * 2) + (3 * 2) + (3 * 4)  # lines along a, b, c of the grid
    outline = cell_edge_segments(
        structure, SceneSettings(repetitions=(2, 3, 1), cell_mode="outline")
    )
    assert len(outline) == 12
    np.testing.assert_allclose(outline.reshape(-1, 3).max(axis=0), [2 * a, 3 * a, a])
    unit = cell_edge_segments(structure, SceneSettings(repetitions=(2, 3, 1), cell_mode="unit"))
    np.testing.assert_allclose(unit.reshape(-1, 3).max(axis=0), [a, a, a])
    assert len(cell_edge_segments(structure, SceneSettings(show_cell=False))) == 0
