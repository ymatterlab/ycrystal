"""FR-QE-IBRAV-01: the Bravais lattices of pw.x for ibrav other than 0.

Expected vectors are typed from the pw.x input documentation (INPUT_PW, ``ibrav``), not
from the implementation. A second, independent check confirms that each cell spans the
named Bravais lattice: the conventional cell and the centring vectors are whole-number
combinations of the primitive vectors, and the volumes differ by the number of lattice
points.
"""

import math

import numpy as np
import pytest

from ycrystal.io.qe_lattice import IBRAV_LATTICES, LatticeError, celldm_from_input, ibrav_cell

A, B, C = 4.0, 5.2, 6.8
COS_ALPHA, COS_BETA, COS_GAMMA = 0.2, -0.15, 0.3
SIN_BETA, SIN_GAMMA = math.sqrt(1 - COS_BETA**2), math.sqrt(1 - COS_GAMMA**2)
COS_R = 0.35  # rhombohedral angle (ibrav 5, -5)


def celldm(ibrav: int) -> tuple[float, ...]:
    """celldm for a = 4 bohr, b = 5.2, c = 6.8 and the angles above (bohr = 1 here)."""
    fourth = {14: COS_ALPHA, 12: COS_GAMMA, 13: COS_GAMMA, 5: COS_R, -5: COS_R}
    return (A, B / A, C / A, fourth.get(ibrav, 0.0), COS_BETA, COS_GAMMA)


def documented_vectors(ibrav: int) -> list:
    """v1, v2, v3 as INPUT_PW writes them."""
    a, b, c = A, B, C
    tx = math.sqrt((1 - COS_R) / 2)
    ty = math.sqrt((1 - COS_R) / 6)
    tz = math.sqrt((1 + 2 * COS_R) / 3)
    u, v = tz - 2 * math.sqrt(2) * ty, tz + math.sqrt(2) * ty
    ap = a / math.sqrt(3)
    triclinic_z = math.sqrt(
        1 + 2 * COS_ALPHA * COS_BETA * COS_GAMMA - COS_ALPHA**2 - COS_BETA**2 - COS_GAMMA**2
    )
    return {
        1: [(a, 0, 0), (0, a, 0), (0, 0, a)],
        2: [(-a / 2, 0, a / 2), (0, a / 2, a / 2), (-a / 2, a / 2, 0)],
        3: [(a / 2, a / 2, a / 2), (-a / 2, a / 2, a / 2), (-a / 2, -a / 2, a / 2)],
        -3: [(-a / 2, a / 2, a / 2), (a / 2, -a / 2, a / 2), (a / 2, a / 2, -a / 2)],
        4: [(a, 0, 0), (-a / 2, a * math.sqrt(3) / 2, 0), (0, 0, c)],
        5: [(a * tx, -a * ty, a * tz), (0, 2 * a * ty, a * tz), (-a * tx, -a * ty, a * tz)],
        -5: [(ap * u, ap * v, ap * v), (ap * v, ap * u, ap * v), (ap * v, ap * v, ap * u)],
        6: [(a, 0, 0), (0, a, 0), (0, 0, c)],
        7: [(a / 2, -a / 2, c / 2), (a / 2, a / 2, c / 2), (-a / 2, -a / 2, c / 2)],
        8: [(a, 0, 0), (0, b, 0), (0, 0, c)],
        9: [(a / 2, b / 2, 0), (-a / 2, b / 2, 0), (0, 0, c)],
        -9: [(a / 2, -b / 2, 0), (a / 2, b / 2, 0), (0, 0, c)],
        91: [(a, 0, 0), (0, b / 2, -c / 2), (0, b / 2, c / 2)],
        10: [(a / 2, 0, c / 2), (a / 2, b / 2, 0), (0, b / 2, c / 2)],
        11: [(a / 2, b / 2, c / 2), (-a / 2, b / 2, c / 2), (-a / 2, -b / 2, c / 2)],
        12: [(a, 0, 0), (b * COS_GAMMA, b * SIN_GAMMA, 0), (0, 0, c)],
        -12: [(a, 0, 0), (0, b, 0), (c * COS_BETA, 0, c * SIN_BETA)],
        13: [(a / 2, 0, -c / 2), (b * COS_GAMMA, b * SIN_GAMMA, 0), (a / 2, 0, c / 2)],
        -13: [(a / 2, b / 2, 0), (-a / 2, b / 2, 0), (c * COS_BETA, 0, c * SIN_BETA)],
        14: [
            (a, 0, 0),
            (b * COS_GAMMA, b * SIN_GAMMA, 0),
            (
                c * COS_BETA,
                c * (COS_ALPHA - COS_BETA * COS_GAMMA) / SIN_GAMMA,
                c * triclinic_z / SIN_GAMMA,
            ),
        ],
    }[ibrav]


def conventional(ibrav: int) -> tuple[np.ndarray, list, int]:
    """Conventional cell, centring vectors, and lattice points per conventional cell."""
    a, b, c = A, B, C
    cubic, tetragonal, ortho = np.diag([a, a, a]), np.diag([a, a, c]), np.diag([a, b, c])
    mono_c = np.array([(a, 0, 0), (b * COS_GAMMA, b * SIN_GAMMA, 0), (0, 0, c)])
    mono_b = np.array([(a, 0, 0), (0, b, 0), (c * COS_BETA, 0, c * SIN_BETA)])
    hexagonal = np.array([(a, 0, 0), (-a / 2, a * math.sqrt(3) / 2, 0), (0, 0, c)])
    face = [(a / 2, a / 2, 0), (a / 2, 0, a / 2), (0, a / 2, a / 2)]
    return {
        1: (cubic, [], 1),
        2: (cubic, face, 4),
        3: (cubic, [(a / 2, a / 2, a / 2)], 2),
        -3: (cubic, [(a / 2, a / 2, a / 2)], 2),
        4: (hexagonal, [], 1),
        6: (tetragonal, [], 1),
        7: (tetragonal, [(a / 2, a / 2, c / 2)], 2),
        8: (ortho, [], 1),
        9: (ortho, [(a / 2, b / 2, 0)], 2),
        -9: (ortho, [(a / 2, b / 2, 0)], 2),
        91: (ortho, [(0, b / 2, c / 2)], 2),
        10: (ortho, [(a / 2, b / 2, 0), (a / 2, 0, c / 2), (0, b / 2, c / 2)], 4),
        11: (ortho, [(a / 2, b / 2, c / 2)], 2),
        12: (mono_c, [], 1),
        -12: (mono_b, [], 1),
        13: (mono_c, [(a / 2, 0, c / 2)], 2),
        -13: (mono_b, [(a / 2, b / 2, 0)], 2),
    }[ibrav]


def test_every_pw_x_lattice_is_known():
    assert sorted(IBRAV_LATTICES) == sorted(
        [1, 2, 3, -3, 4, 5, -5, 6, 7, 8, 9, -9, 91, 10, 11, 12, -12, 13, -13, 14]
    )


@pytest.mark.parametrize("ibrav", list(IBRAV_LATTICES))
def test_vectors_are_the_documented_ones(ibrav):
    cell = ibrav_cell(ibrav, celldm(ibrav), bohr=1.0)
    np.testing.assert_allclose(cell, documented_vectors(ibrav), atol=1e-12)
    scaled = ibrav_cell(ibrav, celldm(ibrav), bohr=0.5)  # celldm(1) is in bohr
    np.testing.assert_allclose(scaled, 0.5 * cell, atol=1e-12)


@pytest.mark.parametrize("ibrav", [i for i in IBRAV_LATTICES if abs(i) not in (5, 14)])
def test_cells_span_the_named_bravais_lattice(ibrav):
    cell = ibrav_cell(ibrav, celldm(ibrav), bohr=1.0)
    conv, centring, points = conventional(ibrav)
    for vectors in (conv, np.array(centring).reshape(-1, 3)):
        coefficients = vectors @ np.linalg.inv(cell)
        np.testing.assert_allclose(coefficients, np.round(coefficients), atol=1e-9)
    assert abs(np.linalg.det(conv)) == pytest.approx(points * abs(np.linalg.det(cell)))
    assert np.linalg.det(cell) > 0  # right-handed, as pw.x's


@pytest.mark.parametrize("ibrav", [5, -5])
def test_rhombohedral_cells_have_the_angle_and_their_threefold_axis(ibrav):
    cell = ibrav_cell(ibrav, celldm(ibrav), bohr=1.0)
    lengths = np.linalg.norm(cell, axis=1)
    np.testing.assert_allclose(lengths, A, atol=1e-12)
    for i, j in ((0, 1), (1, 2), (0, 2)):
        assert cell[i] @ cell[j] / A**2 == pytest.approx(COS_R)
    if ibrav == 5:  # threefold axis along z: a 120° turn about z cycles the vectors
        t = 2 * math.pi / 3
        turn = np.array([[math.cos(t), -math.sin(t), 0], [math.sin(t), math.cos(t), 0], [0, 0, 1]])
        rotated = cell @ turn.T
        assert {tuple(np.round(r, 9)) for r in rotated} == {tuple(np.round(r, 9)) for r in cell}
    else:  # threefold axis along (111): cycling x, y, z cycles the vectors
        np.testing.assert_allclose(cell[:, [2, 0, 1]], cell[[1, 2, 0]], atol=1e-12)


def test_triclinic_cell_has_its_lengths_and_angles():
    cell = ibrav_cell(14, celldm(14), bohr=1.0)
    a, b, c = np.linalg.norm(cell, axis=1)
    assert (a, b, c) == pytest.approx((A, B, C))
    assert cell[1] @ cell[2] / (b * c) == pytest.approx(COS_ALPHA)
    assert cell[0] @ cell[2] / (a * c) == pytest.approx(COS_BETA)
    assert cell[0] @ cell[1] / (a * b) == pytest.approx(COS_GAMMA)


@pytest.mark.parametrize(
    ("ibrav", "slot", "key"),
    [
        (14, 4, "cosbc"),
        (14, 5, "cosac"),
        (14, 6, "cosab"),
        (-12, 5, "cosac"),
        (-13, 5, "cosac"),
        (5, 4, "cosab"),
        (-5, 4, "cosab"),
        (12, 4, "cosab"),
        (13, 4, "cosab"),
    ],
)
def test_crystallographic_parameters_map_onto_celldm_as_in_pw_x(ibrav, slot, key):
    system = {"a": 2.0, "b": 3.0, "c": 5.0, key: 0.25}
    cd = celldm_from_input(ibrav, system, bohr=0.5)
    assert cd[:3] == pytest.approx((4.0, 1.5, 2.5))  # A in Å / bohr, then b/a, c/a
    assert cd[slot - 1] == 0.25
    assert sum(1 for v in cd[3:] if v) == 1  # only that slot is set


def test_unused_cosines_are_ignored_like_pw_x():
    cd = celldm_from_input(8, {"a": 2.0, "b": 3.0, "c": 5.0, "cosab": 0.4}, bohr=1.0)
    assert cd[3:] == (0.0, 0.0, 0.0)


@pytest.mark.parametrize(
    ("ibrav", "values", "message"),
    [
        (2, (0.0,), "celldm(1) or A > 0"),
        (6, (4.0,), "celldm(3) or C > 0"),
        (11, (4.0, 0.0, 1.5), "celldm(2) or B > 0"),
        (5, (4.0, 0, 0, -0.5), "−1/2 < celldm(4)"),
        (-5, (4.0, 0, 0, 1.0), "−1/2 < celldm(4)"),
        (12, (4.0, 1, 1, 1.0), "celldm(4) = cos(gamma)"),
        (-13, (4.0, 1, 1, 0, -1.0), "celldm(5) = cos(beta)"),
        (14, (4.0, 1, 1, 0.9, -0.9, 0.9), "do not make a cell"),
        (0, (4.0,), "not a pw.x Bravais lattice"),
        (15, (4.0,), "not a pw.x Bravais lattice"),
        (1, (float("nan"),), "finite"),
    ],
)
def test_bad_parameters_are_refused(ibrav, values, message):
    with pytest.raises(LatticeError, match=message.replace("(", r"\(").replace(")", r"\)")):
        ibrav_cell(ibrav, values, bohr=1.0)


@pytest.mark.parametrize(
    ("system", "message"),
    [
        ({"celldm(1)": 9.0, "a": 4.0}, "given twice"),
        ({}, "needs the lattice parameters"),
        ({"a": -1.0}, "A > 0"),
        ({"a": 3.0, "b": -1.0}, "must not be negative"),
        ({"a": 3.0, "cosab": 1.5}, "not a cosine"),
    ],
)
def test_bad_input_parameters_are_refused(system, message):
    with pytest.raises(LatticeError, match=message):
        celldm_from_input(1, system, bohr=1.0)
