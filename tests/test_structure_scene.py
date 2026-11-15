import numpy as np
import pytest
from ase.data import covalent_radii

from ycrystal.core.samples import SAMPLES, perovskite_srtio3, triclinic_marker
from ycrystal.core.scene import SceneSettings, build_geometry
from ycrystal.core.structure import Structure


def test_structure_arrays_are_read_only():
    structure = perovskite_srtio3()
    with pytest.raises(ValueError):
        structure.positions[0, 0] = 1.0
    with pytest.raises(ValueError):
        structure.cell[0, 0] = 1.0


def test_structure_copies_input_arrays():
    positions = np.zeros((1, 3))
    structure = Structure(cell=np.eye(3) * 4, positions=positions, numbers=[8], labels=["O1"])
    positions[0, 0] = 9.0
    assert structure.positions[0, 0] == 0.0
    assert structure.labels == ("O1",)
    assert structure.symbols == ("O",)


def test_structure_validation():
    with pytest.raises(ValueError):
        Structure(cell=np.eye(3), positions=np.zeros((2, 3)), numbers=[8], labels=["O", "O"])
    with pytest.raises(ValueError):
        Structure(cell=np.eye(3), positions=np.zeros((1, 3)), numbers=[0], labels=["X"])
    with pytest.raises(ValueError):
        Structure(cell=np.eye(2), positions=np.zeros((1, 3)), numbers=[8], labels=["O"])


def test_ase_round_trip_preserves_geometry():
    structure = triclinic_marker()
    atoms = structure.to_ase()
    again = Structure.from_ase(atoms)
    np.testing.assert_allclose(again.cell, structure.cell)
    np.testing.assert_allclose(again.positions, structure.positions)
    assert again.symbols == structure.symbols


def test_samples_are_valid():
    for name, factory in SAMPLES.items():
        structure = factory()
        assert len(structure) > 0, name
        assert structure.has_cell
    assert perovskite_srtio3().composition() == "SrTiO3"


def test_geometry_ids_radii_colors_and_cell_edges():
    structure = triclinic_marker()
    geometry = build_geometry(structure, SceneSettings(radius_scale=0.5))
    assert geometry.atom_ids == tuple((i, (0, 0, 0)) for i in range(len(structure)))
    np.testing.assert_allclose(geometry.positions, structure.positions)
    np.testing.assert_allclose(geometry.radii, 0.5 * covalent_radii[structure.numbers])
    assert geometry.colors.shape == (len(structure), 3)
    assert geometry.cell_edges.shape == (12, 2, 3)
    corners = {tuple(np.round(p, 9)) for p in geometry.cell_edges.reshape(-1, 3)}
    expected = {tuple(np.round(np.array(f) @ structure.cell, 9)) for f in np.ndindex(2, 2, 2)}
    assert corners == expected
    # Every edge is parallel to one lattice vector and has its length.
    lengths = sorted(np.linalg.norm(e[1] - e[0]) for e in geometry.cell_edges)
    cell_lengths = sorted(np.linalg.norm(structure.cell, axis=1).tolist() * 4)
    np.testing.assert_allclose(lengths, cell_lengths)


def test_geometry_without_cell_and_hidden_cell():
    molecule = Structure(
        cell=np.zeros((3, 3)),
        positions=np.zeros((1, 3)),
        numbers=[6],
        labels=["C"],
        pbc=(False, False, False),
    )
    assert build_geometry(molecule).cell_edges.shape == (0, 2, 3)
    hidden = build_geometry(perovskite_srtio3(), SceneSettings(show_cell=False))
    assert hidden.cell_edges.shape == (0, 2, 3)


def test_bounding_sphere_contains_everything():
    geometry = build_geometry(triclinic_marker())
    center, radius = geometry.bounding_sphere()
    points, radii = geometry.points_and_radii()
    assert np.all(np.linalg.norm(points - center, axis=1) + radii <= radius + 1e-9)


# ----- boundary images and hiding ---------------------------------------------------
def _frac(geometry, structure):
    return geometry.positions @ np.linalg.inv(structure.cell)


def test_perovskite_boundary_images_like_vesta():
    structure = perovskite_srtio3()
    geometry = build_geometry(structure)
    assert len(geometry) == 15
    assert geometry.element_counts() == {"Sr": 8, "Ti": 1, "O": 6}
    frac = _frac(geometry, structure)
    assert np.all(frac > -1e-9) and np.all(frac < 1 + 1e-9)
    pairs = list(zip(np.round(frac, 6), geometry.elements, strict=True))
    corners = {tuple(f) for f, e in pairs if e == "Sr"}
    assert corners == {tuple(map(float, c)) for c in np.ndindex(2, 2, 2)}
    faces = {tuple(f) for f, e in pairs if e == "O"}
    assert len(faces) == 6 and all(sorted(f).count(0.5) == 2 for f in faces)
    # Every displayed position is the input position plus an integer lattice offset.
    for (source, image), position in zip(geometry.atom_ids, geometry.positions, strict=True):
        expected = structure.positions[source] + np.array(image) @ structure.cell
        np.testing.assert_allclose(position, expected, atol=1e-12)
    assert len(set(geometry.atom_ids)) == 15


def test_boundary_images_off_shows_input_atoms_once():
    structure = perovskite_srtio3()
    geometry = build_geometry(structure, SceneSettings(boundary_images=False))
    assert geometry.atom_ids == tuple((i, (0, 0, 0)) for i in range(5))
    np.testing.assert_array_equal(geometry.positions, structure.positions)


def test_wrapping_atoms_outside_the_cell_and_near_one():
    cell = np.diag([4.0, 5.0, 6.0])
    frac = np.array([[1.25, -0.5, 0.3], [0.9999999, 0.5, 0.5]])
    structure = Structure(cell=cell, positions=frac @ cell, numbers=[8, 22], labels=["O", "Ti"])
    geometry = build_geometry(structure)
    assert geometry.atom_ids == ((0, (-1, 1, 0)), (1, (-1, 0, 0)), (1, (0, 0, 0)))
    shown = _frac(geometry, structure)
    np.testing.assert_allclose(shown[0], [0.25, 0.5, 0.3], atol=1e-12)
    np.testing.assert_allclose(shown[1:, 0], [-1e-7, 0.9999999], atol=1e-12)


def test_no_images_along_non_periodic_axes():
    cell = np.diag([4.0, 4.0, 20.0])
    structure = Structure(
        cell=cell, positions=[[0.0, 0.0, 26.0]], numbers=[6], labels=["C"], pbc=(True, True, False)
    )
    geometry = build_geometry(structure)
    assert len(geometry) == 4
    assert {image for _, image in geometry.atom_ids} == {(0, 0, 0), (0, 1, 0), (1, 0, 0), (1, 1, 0)}
    assert np.all(geometry.positions[:, 2] == 26.0)


def test_general_positions_have_no_boundary_images():
    assert len(build_geometry(triclinic_marker())) == 5


def test_hidden_atoms_are_removed_individually():
    structure = perovskite_srtio3()
    corner = (0, (1, 1, 1))
    geometry = build_geometry(structure, SceneSettings(hidden=frozenset({corner})))
    assert len(geometry) == 14 and geometry.hidden_count == 1
    assert corner not in geometry and geometry.index_of(corner) is None
    assert geometry.element_counts()["Sr"] == 7  # the symmetry-equivalent corners remain
    assert geometry.index_of((0, (0, 0, 0))) == 0
    unknown = build_geometry(structure, SceneSettings(hidden=frozenset({(0, (5, 5, 5))})))
    assert len(unknown) == 15 and unknown.hidden_count == 0
    # Hiding never touches the structure.
    np.testing.assert_array_equal(structure.positions, perovskite_srtio3().positions)
