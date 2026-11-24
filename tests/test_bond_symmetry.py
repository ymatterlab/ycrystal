"""Equivalence tests match crystallographic operations applied to both bond ends."""

from dataclasses import replace

import numpy as np

from ycrystal.core.bond_symmetry import equivalent_displayed_bonds
from ycrystal.core.samples import perovskite_srtio3
from ycrystal.core.scene import SceneSettings, build_geometry
from ycrystal.core.structure import Structure


def titanium_bonds(geometry):
    return [
        (geometry.atom_ids[a], geometry.atom_ids[b])
        for a, b in geometry.bonds
        if {geometry.elements[a], geometry.elements[b]} == {"Ti", "O"}
    ]


def test_selects_the_whole_octahedral_orbit_across_the_supercell():
    structure = perovskite_srtio3()
    positions = structure.positions.copy()
    positions[2] += structure.cell[0]  # an unwrapped oxygen in the input
    structure = structure.replace(positions=positions)
    settings = SceneSettings(repetitions=(3, 3, 2))
    geometry = build_geometry(structure, settings)
    titanium_oxygen = titanium_bonds(geometry)
    assert len(titanium_oxygen) == 108
    assert len(geometry.bonds) > 108
    selected, suppressed = titanium_oxygen[:2]
    settings = settings.with_bond_override(*suppressed, False)
    geometry = build_geometry(structure, settings)
    result = equivalent_displayed_bonds(structure, geometry, selected[::-1])
    assert set(result) == set(titanium_oxygen) - {suppressed}


def test_equal_distance_does_not_group_inequivalent_bonds():
    structure = perovskite_srtio3()
    positions = structure.positions.copy()
    positions[0] += (0.19, 0.41, 0.33)  # lower symmetry without changing the Ti–O distances
    structure = structure.replace(positions=positions)
    geometry = build_geometry(structure, SceneSettings(repetitions=(2, 2, 1)))
    titanium_oxygen = titanium_bonds(geometry)
    selected = titanium_oxygen[-1]
    result = equivalent_displayed_bonds(structure, geometry, selected)
    assert selected in result and len(result) == 4
    assert len(titanium_oxygen) == 24


def test_layer_quarter_turn_equivalence_and_wire_translation():
    structure = Structure(
        np.diag([2.3, 2.3, 10.0]),
        positions=[(0.0, 0.0, 2.1)],
        numbers=[29],
        labels=["Cu"],
        pbc=(True, True, False),
    )
    settings = SceneSettings(repetitions=(2, 2, 1))
    geometry = build_geometry(structure, settings)
    a, b = geometry.bonds[0]
    selected = (geometry.atom_ids[a], geometry.atom_ids[b])
    assert len(geometry.bonds) == 12
    assert len(equivalent_displayed_bonds(structure, geometry, selected)) == 12

    structure = structure.replace(pbc=(True, False, False))
    geometry = build_geometry(structure, replace(settings, repetitions=(3, 1, 1)))
    a, b = geometry.bonds[0]
    selected = (geometry.atom_ids[a], geometry.atom_ids[b])
    assert len(equivalent_displayed_bonds(structure, geometry, selected)) == 3
