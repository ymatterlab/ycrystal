"""Bravais lattices of Quantum ESPRESSO input with ``ibrav`` other than 0 (FR-QE-IBRAV-01).

In a pw.x input, ``ibrav`` names a Bravais lattice and its parameters are given either as
``celldm(1)`` … ``celldm(6)`` (``celldm(1)`` = a in bohr, the others ratios and cosines)
or as ``A, B, C, cosAB, cosAC, cosBC`` (lengths in Å). pw.x builds the lattice vectors
from them with fixed conventions; this module builds the same vectors, so that a
structure opens with exactly the cell pw.x uses.

The vectors follow the definitions in the pw.x input documentation (``INPUT_PW``, the
``ibrav`` variable) and pw.x's lattice generator (``Modules/latgen.f90``), including its
checks of the parameters, and the mapping of ``A, B, C, cosAB…`` onto ``celldm``
(``abc2celldm``). Every ``ibrav`` value pw.x accepts is supported:

==========  =========================================================
``ibrav``   Lattice
==========  =========================================================
1           cubic P (sc)
2           cubic F (fcc)
3, -3       cubic I (bcc); -3 is the more symmetric axis choice
4           hexagonal and trigonal P
5, -5       trigonal R, threefold axis along z (5) or along (111) (-5)
6           tetragonal P (st)
7           tetragonal I (bct)
8           orthorhombic P
9, -9       orthorhombic base-centred, C type (two axis choices)
91          orthorhombic one-face base-centred, A type
10          orthorhombic face-centred
11          orthorhombic body-centred
12, -12     monoclinic P, unique axis c (12) or b (-12)
13, -13     monoclinic base-centred, unique axis c (13) or b (-13)
14          triclinic
==========  =========================================================

The vectors are those of QE 6.5 and later. They are the same in every older version,
except for ``ibrav = -13``: QE 5.2.0 to 6.4.1 used other axes, v1(old) = −v2 and
v2(old) = v1 (pw.x warns about this change). ``crystal`` positions written for the old
axes therefore describe other atom places here; QE's release notes convert them with
(x, y, z) → (y, −x, z). The mapping of ``A, B, C, cos…`` onto ``celldm`` is that of
QE 6.3 and later (6.2 ignored ``cosAC`` for ``ibrav = -13``). Details, and how this was
checked, are in the user guide (*Quantum ESPRESSO lattices*).

Examples
--------
Silicon in the fcc lattice of pw.x (``ibrav = 2``, ``celldm(1)`` in bohr):

>>> from ycrystal.io.qe_lattice import ibrav_cell
>>> ibrav_cell(2, (10.2631026323, 0, 0, 0, 0, 0), bohr=0.529177).round(4)
array([[-2.7155,  0.    ,  2.7155],
       [ 0.    ,  2.7155,  2.7155],
       [-2.7155,  2.7155,  0.    ]])

MgB2, hexagonal, from crystallographic parameters in Å:

>>> from ycrystal.io.qe_lattice import celldm_from_input
>>> celldm = celldm_from_input(4, {"a": 3.086, "c": 3.524}, bohr=0.529177)
>>> ibrav_cell(4, celldm, bohr=0.529177).round(4)
array([[ 3.086 ,  0.    ,  0.    ],
       [-1.543 ,  2.6726,  0.    ],
       [ 0.    ,  0.    ,  3.524 ]])
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any

import numpy as np

IBRAV_LATTICES: dict[int, str] = {
    1: "cubic P (simple cubic)",
    2: "cubic F (fcc)",
    3: "cubic I (bcc)",
    -3: "cubic I (bcc, symmetric axes)",
    4: "hexagonal and trigonal P",
    5: "trigonal R, threefold axis along z",
    -5: "trigonal R, threefold axis along (111)",
    6: "tetragonal P",
    7: "tetragonal I (bct)",
    8: "orthorhombic P",
    9: "orthorhombic base-centred (C)",
    -9: "orthorhombic base-centred (C), alternate axes",
    91: "orthorhombic one-face base-centred (A)",
    10: "orthorhombic face-centred",
    11: "orthorhombic body-centred",
    12: "monoclinic P, unique axis c",
    -12: "monoclinic P, unique axis b",
    13: "monoclinic base-centred, unique axis c",
    -13: "monoclinic base-centred, unique axis b",
    14: "triclinic",
}
"""Every ``ibrav`` other than 0 that pw.x accepts, with the lattice it names."""

_NEEDS_B_C = {8, 9, -9, 91, 10, 11, 12, -12, 13, -13, 14}  # celldm(2) and celldm(3)
_NEEDS_C = {4, 6, 7}  # celldm(3) only

# Where pw.x puts cosAB, cosAC, cosBC among celldm(4..6) (abc2celldm).
_COSINE_SLOTS: dict[int, dict[str, int]] = {
    14: {"cosbc": 4, "cosac": 5, "cosab": 6},
    -12: {"cosac": 5},
    -13: {"cosac": 5},
    -5: {"cosab": 4},
    5: {"cosab": 4},
    12: {"cosab": 4},
    13: {"cosab": 4},
}

# How the parameters are named in messages: celldm(i) and its crystallographic name.
_NAMES = {
    1: "celldm(1) or A",
    2: "celldm(2) or B",
    3: "celldm(3) or C",
    4: "celldm(4)",
    5: "celldm(5)",
    6: "celldm(6)",
}


class LatticeError(ValueError):
    """The lattice parameters do not define a cell; ``str()`` says which one is wrong."""


def celldm_from_input(ibrav: int, system: Mapping[str, Any], bohr: float) -> tuple[float, ...]:
    """Return the six ``celldm`` values of an ``&SYSTEM`` namelist, as pw.x uses them.

    Parameters
    ----------
    ibrav
        The ``ibrav`` of the input (not 0).
    system
        The ``&SYSTEM`` namelist with lower-case keys: ``celldm(1)`` … ``celldm(6)``, or
        ``a``, ``b``, ``c``, ``cosab``, ``cosac``, ``cosbc``.
    bohr
        Length of the bohr in Å, to convert ``A`` into ``celldm(1)``.

    Returns
    -------
    tuple of float
        ``celldm(1)`` (a in bohr) to ``celldm(6)``; unset values are 0, as in pw.x.

    Raises
    ------
    LatticeError
        If both ``celldm`` and ``A, B, C`` are given, neither is, or a length or cosine
        given as ``A, B, C, cos…`` is out of range (the checks of pw.x).
    """
    celldm_given = any(f"celldm({i})" in system for i in range(1, 7))
    abc_given = any(key in system for key in ("a", "b", "c", "cosab", "cosac", "cosbc"))
    if celldm_given and abc_given:
        raise LatticeError(
            "the lattice is given twice: use either celldm(1)…celldm(6) or A, B, C, "
            "cosAB, cosAC, cosBC, not both (pw.x refuses this too)."
        )
    if celldm_given:
        return tuple(float(system.get(f"celldm({i})", 0.0)) for i in range(1, 7))
    if not abc_given:
        raise LatticeError(
            f"ibrav = {ibrav} needs the lattice parameters: celldm(1)…celldm(6) or A, B, C, "
            "cosAB, cosAC, cosBC in &SYSTEM."
        )
    a = float(system.get("a", 0.0))
    b, c = float(system.get("b", 0.0)), float(system.get("c", 0.0))
    if a <= 0:
        raise LatticeError(f"ibrav = {ibrav} needs A > 0 (the lattice parameter a in Å).")
    if b < 0 or c < 0:
        raise LatticeError("B and C must not be negative.")
    cosines = {key: float(system.get(key, 0.0)) for key in ("cosab", "cosac", "cosbc")}
    for key, value in cosines.items():
        if abs(value) > 1:
            raise LatticeError(f"{key} = {value:g} is not a cosine (it must lie in −1 … 1).")
    celldm = [a / bohr, b / a, c / a, 0.0, 0.0, 0.0]
    for key, slot in _COSINE_SLOTS.get(ibrav, {}).items():
        celldm[slot - 1] = cosines[key]
    return tuple(celldm)


def ibrav_cell(ibrav: int, celldm: tuple[float, ...] | list[float], bohr: float) -> np.ndarray:
    """Return the lattice vectors pw.x builds for ``ibrav`` and ``celldm``, in Å.

    Parameters
    ----------
    ibrav
        One of [`IBRAV_LATTICES`][ycrystal.io.qe_lattice.IBRAV_LATTICES].
    celldm
        ``celldm(1)`` (a, in bohr) to ``celldm(6)``, for example from
        [`celldm_from_input`][ycrystal.io.qe_lattice.celldm_from_input].
    bohr
        Length of the bohr in Å.

    Returns
    -------
    numpy.ndarray
        Lattice vectors as rows, shape ``(3, 3)``, in Å.

    Raises
    ------
    LatticeError
        If ``ibrav`` is not a pw.x lattice, or a parameter the lattice needs is missing
        or out of range (the checks of pw.x: lengths positive, cosines within −1 … 1,
        a trigonal angle with −1/2 < cos α < 1, and a triclinic cell with volume).
    """
    ibrav = int(ibrav)
    if ibrav not in IBRAV_LATTICES:
        known = ", ".join(str(v) for v in IBRAV_LATTICES)
        raise LatticeError(f"ibrav = {ibrav} is not a pw.x Bravais lattice (known: 0, {known}).")
    cd = [float(v) for v in celldm] + [0.0] * (6 - len(celldm))
    if not all(math.isfinite(v) for v in cd):
        raise LatticeError("the lattice parameters must be finite numbers.")
    a, b_a, c_a = cd[0], cd[1], cd[2]
    if a <= 0:
        raise LatticeError(f"ibrav = {ibrav} needs {_NAMES[1]} > 0.")
    if ibrav in _NEEDS_B_C and b_a <= 0:
        raise LatticeError(f"ibrav = {ibrav} needs {_NAMES[2]} > 0.")
    if (ibrav in _NEEDS_B_C or ibrav in _NEEDS_C) and c_a <= 0:
        raise LatticeError(f"ibrav = {ibrav} needs {_NAMES[3]} > 0.")
    b, c = a * b_a, a * c_a
    if ibrav == 1:
        cell = [[a, 0, 0], [0, a, 0], [0, 0, a]]
    elif ibrav == 2:
        h = a / 2
        cell = [[-h, 0, h], [0, h, h], [-h, h, 0]]
    elif ibrav == 3:
        h = a / 2
        cell = [[h, h, h], [-h, h, h], [-h, -h, h]]
    elif ibrav == -3:
        h = a / 2
        cell = [[-h, h, h], [h, -h, h], [h, h, -h]]
    elif ibrav == 4:
        cell = [[a, 0, 0], [-a / 2, a * math.sqrt(3) / 2, 0], [0, 0, c]]
    elif abs(ibrav) == 5:
        cos_alpha = cd[3]
        if not -0.5 < cos_alpha < 1:
            raise LatticeError(
                f"ibrav = {ibrav} needs −1/2 < celldm(4) = cos(alpha) < 1 (or cosAB), "
                f"not {cos_alpha:g}."
            )
        t1 = math.sqrt(1 + 2 * cos_alpha)
        t2 = math.sqrt(1 - cos_alpha)
        if ibrav == 5:
            tx, ty, tz = t2 / math.sqrt(2), t2 / math.sqrt(6), t1 / math.sqrt(3)
            cell = [[a * tx, -a * ty, a * tz], [0, 2 * a * ty, a * tz], [-a * tx, -a * ty, a * tz]]
        else:
            u, v = a * (t1 - 2 * t2) / 3, a * (t1 + t2) / 3
            cell = [[u, v, v], [v, u, v], [v, v, u]]
    elif ibrav == 6:
        cell = [[a, 0, 0], [0, a, 0], [0, 0, c]]
    elif ibrav == 7:
        h, hc = a / 2, c / 2
        cell = [[h, -h, hc], [h, h, hc], [-h, -h, hc]]
    elif ibrav == 8:
        cell = [[a, 0, 0], [0, b, 0], [0, 0, c]]
    elif ibrav == 9:
        cell = [[a / 2, b / 2, 0], [-a / 2, b / 2, 0], [0, 0, c]]
    elif ibrav == -9:
        cell = [[a / 2, -b / 2, 0], [a / 2, b / 2, 0], [0, 0, c]]
    elif ibrav == 91:
        cell = [[a, 0, 0], [0, b / 2, -c / 2], [0, b / 2, c / 2]]
    elif ibrav == 10:
        cell = [[a / 2, 0, c / 2], [a / 2, b / 2, 0], [0, b / 2, c / 2]]
    elif ibrav == 11:
        cell = [[a / 2, b / 2, c / 2], [-a / 2, b / 2, c / 2], [-a / 2, -b / 2, c / 2]]
    elif ibrav in (12, 13):
        cos_gamma = _cosine(ibrav, cd, 4, "gamma")
        sin_gamma = math.sqrt(1 - cos_gamma**2)
        b_vector = [b * cos_gamma, b * sin_gamma, 0]
        if ibrav == 12:
            cell = [[a, 0, 0], b_vector, [0, 0, c]]
        else:
            cell = [[a / 2, 0, -c / 2], b_vector, [a / 2, 0, c / 2]]
    elif ibrav in (-12, -13):
        cos_beta = _cosine(ibrav, cd, 5, "beta")
        c_vector = [c * cos_beta, 0, c * math.sqrt(1 - cos_beta**2)]
        if ibrav == -12:
            cell = [[a, 0, 0], [0, b, 0], c_vector]
        else:
            cell = [[a / 2, b / 2, 0], [-a / 2, b / 2, 0], c_vector]
    else:  # 14, triclinic
        cos_alpha = _cosine(ibrav, cd, 4, "alpha")
        cos_beta = _cosine(ibrav, cd, 5, "beta")
        cos_gamma = _cosine(ibrav, cd, 6, "gamma")
        sin_gamma = math.sqrt(1 - cos_gamma**2)
        volume = (
            1 + 2 * cos_alpha * cos_beta * cos_gamma - cos_alpha**2 - cos_beta**2 - cos_gamma**2
        )
        if volume <= 0:
            raise LatticeError(
                "the angles of this triclinic cell (celldm(4), celldm(5), celldm(6)) do not "
                "make a cell with a volume."
            )
        cell = [
            [a, 0, 0],
            [b * cos_gamma, b * sin_gamma, 0],
            [
                c * cos_beta,
                c * (cos_alpha - cos_beta * cos_gamma) / sin_gamma,
                c * math.sqrt(volume) / sin_gamma,
            ],
        ]
    return np.array(cell, dtype=float) * bohr


def _cosine(ibrav: int, celldm: list[float], index: int, angle: str) -> float:
    value = celldm[index - 1]
    if abs(value) >= 1:
        raise LatticeError(
            f"ibrav = {ibrav} needs celldm({index}) = cos({angle}) strictly between −1 and 1, "
            f"not {value:g}."
        )
    return value
