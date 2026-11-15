"""FR-MEASURE-01: distances and bond angles between displayed instances (no Qt or VTK)."""

import itertools

import numpy as np
import pytest

from ycrystal.core.measure import (
    MeasurementError,
    MeasurementSession,
    atom_position,
    atom_text,
    bond_angle,
    distance,
    measure,
    measurement_text,
    prompt,
    result_text,
)
from ycrystal.core.samples import perovskite_srtio3
from ycrystal.core.scene import SceneSettings, build_geometry
from ycrystal.core.structure import Structure

A = 3.905  # SrTiO3 lattice parameter of the sample


def molecule(points, symbols=None, labels=None):
    points = np.asarray(points, float)
    symbols = symbols or ["C"] * len(points)
    numbers = {"C": 6, "O": 8, "H": 1, "Fe": 26}
    return Structure(
        cell=np.zeros((3, 3)),
        positions=points,
        numbers=[numbers[s] for s in symbols],
        labels=labels or symbols,
        pbc=(False, False, False),
    )


def hexagonal(a=3.0, c=5.0):
    """One atom in a hexagonal cell (gamma = 120°): a non-orthogonal metric."""
    cell = np.array([[a, 0, 0], [-a / 2, a * np.sqrt(3) / 2, 0], [0, 0, c]])
    return Structure(cell=cell, positions=np.zeros((1, 3)), numbers=[26], labels=["Fe1"])


def triclinic():
    cell = np.array([[4.1, 0.0, 0.0], [0.9, 3.7, 0.0], [-0.6, 0.8, 5.2]])
    frac = np.array([[0.1, 0.2, 0.3], [0.85, 0.75, 0.1], [0.5, 0.05, 0.95]])
    return Structure(
        cell=cell, positions=frac @ cell, numbers=[8, 26, 1], labels=["O1", "Fe1", "H1"]
    )


# ----- known values --------------------------------------------------------------------------
def test_known_distances_and_angles():
    o = np.zeros(3)
    assert distance(o, np.array([1.0, 2.0, 2.0])) == pytest.approx(3.0, abs=1e-15)
    assert bond_angle(np.array([2.0, 0, 0]), o, np.array([0, 5.0, 0])) == 90.0
    assert bond_angle(np.array([2.0, 0, 0]), o, np.array([-0.5, 0, 0])) == 180.0
    assert bond_angle(np.array([2.0, 0, 0]), o, np.array([7.0, 0, 0])) == 0.0
    equilateral = (np.array([1.0, 0, 0]), o, np.array([0.5, np.sqrt(3) / 2, 0]))
    assert bond_angle(*equilateral) == pytest.approx(60.0, abs=1e-12)
    assert bond_angle(np.array([1.0, 0, 0]), o, np.array([-0.5, np.sqrt(3) / 2, 0])) == (
        pytest.approx(120.0, abs=1e-12)
    )


def test_b_is_the_vertex():
    s = molecule([[0, 0, 0], [3, 0, 0], [3, 4, 0]], ["O", "C", "H"])
    ids = [(i, (0, 0, 0)) for i in range(3)]
    assert measure(s, "angle", ids).value == pytest.approx(90.0)  # ∠ABC at (3, 0, 0)
    assert measure(s, "angle", [ids[1], ids[0], ids[2]]).value == pytest.approx(
        np.degrees(np.arctan2(4, 3))
    )  # ∠BAC = 53.13° at the origin
    assert measure(s, "angle", [ids[0], ids[2], ids[1]]).value == pytest.approx(
        np.degrees(np.arctan2(3, 4))
    )
    assert measure(s, "angle", [ids[2], ids[1], ids[0]]).value == pytest.approx(90.0)


def test_roundoff_near_zero_and_straight_angles():
    far = np.array([1e4, -2e4, 3e4])  # large coordinates
    direction = np.array([0.3, -0.5, 0.8])
    straight = bond_angle(far + 1.7 * direction, far, far - 2.9 * direction)
    assert 179.999999 <= straight <= 180.0
    assert 0.0 <= bond_angle(far + direction, far, far + 3 * direction) < 1e-6
    tiny = bond_angle(np.array([1.0, 1e-9, 0]), np.zeros(3), np.array([1.0, 0, 0]))
    assert tiny == pytest.approx(np.degrees(1e-9), rel=1e-6) and not np.isnan(tiny)
    rng = np.random.default_rng(1)
    for _ in range(200):
        a, b, c = rng.normal(size=(3, 3)) * 5
        assert 0.0 <= bond_angle(a, b, c) <= 180.0


def test_degenerate_selections_are_rejected():
    s = molecule([[0, 0, 0], [0, 0, 0], [1, 0, 0]])
    same_place = [(0, (0, 0, 0)), (1, (0, 0, 0)), (2, (0, 0, 0))]
    with pytest.raises(MeasurementError, match="same position as the vertex"):
        measure(s, "angle", same_place)
    with pytest.raises(MeasurementError, match="same position as the vertex"):
        bond_angle(np.zeros(3), np.zeros(3), np.ones(3))
    with pytest.raises(MeasurementError, match="selected twice"):
        measure(s, "distance", [(2, (0, 0, 0)), (2, (0, 0, 0))])
    with pytest.raises(MeasurementError, match="needs 3 atoms"):
        measure(s, "angle", same_place[:2])
    with pytest.raises(ValueError, match="unknown"):
        measure(s, "dihedral", same_place)
    with pytest.raises(MeasurementError, match="does not exist"):
        atom_position(s, (7, (0, 0, 0)))
    with pytest.raises(MeasurementError, match="no periodic images"):
        atom_position(s, (0, (1, 0, 0)))
    # Two distinct atoms at one place: their distance is a valid 0 Å.
    assert measure(s, "distance", same_place[:2]).value == 0.0


# ----- periodic images -----------------------------------------------------------------------
def test_exact_images_not_minimum_image():
    cell = np.diag([10.0, 10.0, 10.0])
    s = Structure(
        cell=cell,
        positions=np.array([[1.0, 0, 0], [9.0, 0, 0]]),
        numbers=[8, 8],
        labels=["O1", "O2"],
    )
    assert measure(s, "distance", [(0, (0, 0, 0)), (1, (0, 0, 0))]).value == pytest.approx(8.0)
    assert measure(s, "distance", [(0, (0, 0, 0)), (1, (-1, 0, 0))]).value == pytest.approx(2.0)
    # Two images of the same source atom are distinct instances.
    assert measure(s, "distance", [(0, (0, 0, 0)), (0, (0, 1, 1))]).value == pytest.approx(
        10.0 * np.sqrt(2)
    )
    straight = [(0, (-1, 0, 0)), (0, (0, 0, 0)), (0, (1, 0, 0))]
    assert measure(s, "angle", straight).value == 180.0


def test_displayed_instances_match_the_geometry_in_supercells():
    structure = perovskite_srtio3()
    for settings in (
        SceneSettings(),
        SceneSettings(repetitions=(2, 3, 1)),
        SceneSettings(repetitions=(2, 2, 2), boundary_images=False),
    ):
        geometry = build_geometry(structure, settings)
        for i, atom_id in enumerate(geometry.atom_ids):
            np.testing.assert_array_equal(atom_position(structure, atom_id), geometry.positions[i])
    ti = (1, (0, 0, 0))
    o_x = [(4, (0, 0, 0)), (4, (1, 0, 0))]  # O at (0, ½, ½) and its +a image
    assert measure(structure, "distance", [ti, o_x[0]]).value == pytest.approx(A / 2)
    assert measure(structure, "angle", [o_x[0], ti, o_x[1]]).value == pytest.approx(180.0)
    assert measure(structure, "angle", [o_x[0], ti, (2, (0, 0, 0))]).value == pytest.approx(90.0)
    assert measure(structure, "distance", [(0, (0, 0, 0)), (0, (1, 1, 1))]).value == (
        pytest.approx(A * np.sqrt(3))
    )


def test_non_orthogonal_cells():
    hexa = hexagonal(a=3.0)
    origin, a_img, b_img = (0, (0, 0, 0)), (0, (1, 0, 0)), (0, (0, 1, 0))
    assert measure(hexa, "angle", [a_img, origin, b_img]).value == pytest.approx(120.0)
    assert measure(hexa, "distance", [a_img, b_img]).value == pytest.approx(3.0 * np.sqrt(3))
    assert measure(hexa, "angle", [a_img, origin, (0, (1, 1, 0))]).value == pytest.approx(60.0)
    # Triclinic: compare with the fractional metric tensor G = cell cellᵀ.
    s = triclinic()
    metric = s.cell @ s.cell.T
    frac = s.positions @ np.linalg.inv(s.cell)
    images = list(itertools.product((-1, 0, 1), repeat=3))[::5]
    for (i, ii), (j, jj) in itertools.product(itertools.product(range(3), images), repeat=2):
        if (i, ii) == (j, jj):
            continue
        df = (frac[j] + jj) - (frac[i] + ii)
        expected = float(np.sqrt(df @ metric @ df))
        assert measure(s, "distance", [(i, ii), (j, jj)]).value == pytest.approx(expected)


def test_results_ignore_display_settings():
    structure = perovskite_srtio3()
    ids = [(4, (0, 0, 0)), (1, (0, 0, 0)), (2, (0, 0, 1))]
    reference = measure(structure, "angle", ids).value
    for settings in (
        SceneSettings(radius_scale=0.2),
        SceneSettings(element_radii=(("Ti", 2.5),)),
        SceneSettings(repetitions=(3, 1, 2), boundary_images=False),
    ):
        build_geometry(structure, settings)  # display changes do not enter the arithmetic
        assert measure(structure, "angle", ids).value == reference


# ----- text ----------------------------------------------------------------------------------
def test_identity_and_result_text():
    s = triclinic()
    assert atom_text(s, (1, (0, -1, 2))) == "Fe (Fe1) #2 [0 -1 2]"
    assert atom_text(perovskite_srtio3(), (0, (1, 0, 0))) == "Sr #1 [1 0 0]"
    assert atom_text(molecule([[0, 0, 0]], ["O"]), (0, (0, 0, 0))) == "O #1"  # no cell
    d = measure(perovskite_srtio3(), "distance", [(1, (0, 0, 0)), (2, (0, 0, 0))])
    assert result_text(d) == "1.9525 Å"
    a = measure(perovskite_srtio3(), "angle", [(2, (0, 0, 0)), (1, (0, 0, 0)), (3, (0, 0, 0))])
    assert result_text(a) == "90.00° — vertex B"
    assert measurement_text(perovskite_srtio3(), d) == (
        "Distance A–B: 1.9525 Å (A = Ti #2 [0 0 0], B = O #3 [0 0 0])"
    )
    assert measurement_text(perovskite_srtio3(), a) == (
        "Angle A–B–C: 90.00° — vertex B (A = O #3 [0 0 0], B = Ti #2 [0 0 0], C = O #4 [0 0 0])"
    )
    assert prompt("angle", 1) == "Bond angle: select atom B — angle vertex (Esc cancels)"
    assert prompt("distance", 0) == "Distance: select atom A"


# ----- interaction state ---------------------------------------------------------------------
def test_session_sequence_cancel_and_modes():
    structure = perovskite_srtio3()
    session = MeasurementSession(structure)
    assert session.prompt() == ""
    with pytest.raises(MeasurementError, match="No measurement mode"):
        session.pick((0, (0, 0, 0)))
    session.set_mode("angle")
    assert session.pick((2, (0, 0, 0))) is None
    assert "angle vertex" in session.prompt()
    with pytest.raises(MeasurementError, match="already A"):
        session.pick((2, (0, 0, 0)))
    assert session.pending == [(2, (0, 0, 0))]  # rejected picks keep the others
    assert session.pick((2, (0, 0, 1))) is None  # another image of the same atom is fine
    result = session.pick((1, (0, 0, 0)))
    assert result is not None and result.kind == "angle" and session.pending == []
    assert session.results == [result] and session.last is result
    assert session.prompt().startswith("Bond angle: select atom A")  # stays in the mode
    session.pick((0, (0, 0, 0)))
    assert session.last is None  # a new measurement replaces the previous guide
    session.set_mode("distance")  # switching cancels the incomplete one
    assert session.pending == [] and session.mode == "distance"
    session.pick((0, (0, 0, 0)))
    assert session.cancel() is True and session.pending == []
    assert session.cancel() is False
    second = (session.pick((0, (0, 0, 0))), session.pick((1, (0, 0, 0))))[1]
    assert second.value == pytest.approx(A * np.sqrt(3) / 2)
    assert len(session.results) == 2  # appended, not replaced
    session.remove([0])
    assert session.results == [second]
    session.clear()
    assert session.results == [] and session.last is None and session.mode == "distance"


def test_session_rejects_zero_length_arms():
    # Atoms 1 and 2 sit at the same place (e.g. a disordered site given twice).
    s = molecule([[0, 0, 0], [1, 0, 0], [1, 0, 0]])
    session = MeasurementSession(s)
    session.set_mode("angle")
    session.pick((1, (0, 0, 0)))
    with pytest.raises(MeasurementError, match="same position as A"):
        session.pick((2, (0, 0, 0)))  # as vertex B: arm A−B would be zero
    session.set_mode("angle")
    session.pick((0, (0, 0, 0)))
    session.pick((1, (0, 0, 0)))
    with pytest.raises(MeasurementError, match="same position as the vertex B"):
        session.pick((2, (0, 0, 0)))
    assert session.pending == [(0, (0, 0, 0)), (1, (0, 0, 0))]
    # C at A's position is a valid 0° angle.
    session.pending = [(1, (0, 0, 0)), (0, (0, 0, 0))]
    assert session.pick((2, (0, 0, 0))).value == 0.0


def test_session_invalidation():
    structure = perovskite_srtio3()
    session = MeasurementSession(structure)
    session.set_mode("distance")
    session.pick((0, (0, 0, 0)))
    kept = session.pick((1, (0, 0, 0)))
    session.pick((0, (1, 1, 1)))
    lost = session.pick((1, (0, 0, 0)))
    session.pick((4, (1, 0, 0)))  # incomplete
    smaller = build_geometry(structure, SceneSettings(boundary_images=False))
    assert session.invalidate(structure, smaller) == (1, True)
    assert session.results == [kept] and session.pending == [] and lost is not kept
    assert session.invalidate(structure, smaller) == (0, False)
    other = perovskite_srtio3()  # a new structure object, even with equal content
    assert session.invalidate(other, build_geometry(other)) == (1, False)
    assert session.results == [] and session.structure is other
