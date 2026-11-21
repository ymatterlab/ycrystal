"""Structure import: detection, cross-format equivalence, and rejections.

Expected cells and positions are computed here from the lattice constants with explicit
formulas (not by ASE), and the fixture files were written from the same constants.
"""

import hashlib
import shutil
from pathlib import Path

import numpy as np
import pytest

from ycrystal.core.compare import compare_structures, supercell
from ycrystal.io.qe_lattice import IBRAV_LATTICES
from ycrystal.io.readers import (
    BlockChoiceRequired,
    ElementMappingRequired,
    FormatChoiceRequired,
    StructureImportError,
    UnsupportedStructureError,
    detect_format,
    element_from_label,
    evaluate_qe_expression,
    fortran_real,
    read_structure,
)

FIXTURES = Path(__file__).parent / "fixtures"


def fx(name: str) -> Path:
    return FIXTURES / name


def triclinic_cell(a, b, c, alpha, beta, gamma) -> np.ndarray:
    """a along x, b in the xy plane (the usual crystallographic setting)."""
    al, be, ga = np.radians([alpha, beta, gamma])
    cy = (np.cos(al) - np.cos(be) * np.cos(ga)) / np.sin(ga)
    return np.array(
        [
            [a, 0, 0],
            [b * np.cos(ga), b * np.sin(ga), 0],
            [c * np.cos(be), c * cy, c * np.sqrt(1 - np.cos(be) ** 2 - cy**2)],
        ]
    )


def frac(structure) -> np.ndarray:
    return structure.positions @ np.linalg.inv(structure.cell)


def same_set_of_fractions(found: np.ndarray, expected: np.ndarray, tol=1e-6) -> bool:
    remaining = [np.asarray(e) for e in expected]
    for f in found:
        for k, e in enumerate(remaining):
            d = f - e
            if np.all(np.abs(d - np.round(d)) < tol):
                remaining.pop(k)
                break
        else:
            return False
    return not remaining


# ----- detection --------------------------------------------------------------------
@pytest.mark.parametrize(
    "name, fmt",
    [
        ("Si_primitive.vasp", "poscar"),
        ("POSCAR_vasp4", "poscar"),
        ("MgB2.cif", "cif"),
        ("triclinic.pw.in", "qe"),
        ("SrTiO3.pw.in", "qe"),
        ("two_blocks.cif", "cif"),
    ],
)
def test_detect_by_name_and_content(name, fmt):
    assert detect_format(fx(name)) == fmt


def test_detect_by_content_when_name_is_unhelpful_or_wrong(tmp_path):
    for source, fmt in (("SrTiO3.cif", "cif"), ("MgB2.vasp", "poscar"), ("Si.pw.in", "qe")):
        plain = tmp_path / f"structure_{fmt}.txt"
        shutil.copy(fx(source), plain)
        assert detect_format(plain) == fmt
    misleading = tmp_path / "really_a_cif.vasp"
    shutil.copy(fx("SrTiO3.cif"), misleading)
    assert detect_format(misleading) == "cif"


def test_undetectable_format_asks_for_a_choice():
    with pytest.raises(FormatChoiceRequired) as info:
        detect_format(fx("not_a_structure.txt"))
    assert set(info.value.candidates) == {"poscar", "cif", "qe"}


# ----- equivalence between formats ---------------------------------------------------------
def assert_equivalent(a, b, tol=1e-6):
    result = compare_structures(a, b, tolerance=tol)
    assert result.equivalent, result.message


def test_si_primitive_poscar_qe_and_conventional_cif():
    a = 5.431
    poscar = read_structure(fx("Si_primitive.vasp"))
    qe = read_structure(fx("Si.pw.in"))  # celldm(1) in bohr, CELL_PARAMETERS alat
    expected_cell = a * np.array([[0, 0.5, 0.5], [0.5, 0, 0.5], [0.5, 0.5, 0]])
    np.testing.assert_allclose(poscar.cell, expected_cell, atol=1e-12)
    np.testing.assert_allclose(qe.cell, expected_cell, atol=1e-8)
    assert_equivalent(poscar, qe)

    cif = read_structure(fx("Si_conventional.cif"))
    np.testing.assert_allclose(cif.cell, a * np.eye(3), atol=1e-12)
    fcc = np.array([(0, 0, 0), (0, 0.5, 0.5), (0.5, 0, 0.5), (0.5, 0.5, 0)])
    assert same_set_of_fractions(frac(cif), np.vstack([fcc, fcc + 0.25]))
    # Conventional = P @ primitive, recorded explicitly for the comparison.
    P = np.array([[-1, 1, 1], [1, -1, 1], [1, 1, -1]])
    np.testing.assert_allclose(P @ poscar.cell, cif.cell, atol=1e-12)
    assert_equivalent(supercell(poscar, P), cif)


def test_mgb2_cartesian_poscar_cif_symops_and_qe():
    a, c = 3.086, 3.524
    expected = np.array([[a, 0, 0], [-a / 2, a * np.sqrt(3) / 2, 0], [0, 0, c]])
    structures = [read_structure(fx(n)) for n in ("MgB2.vasp", "MgB2.cif", "MgB2.pw.in")]
    for s in structures:
        np.testing.assert_allclose(s.cell, expected, atol=1e-8)
        assert s.composition() == "MgB2"
        assert same_set_of_fractions(frac(s), [(0, 0, 0), (1 / 3, 2 / 3, 0.5), (2 / 3, 1 / 3, 0.5)])
    assert_equivalent(structures[0], structures[1])
    assert_equivalent(structures[0], structures[2])
    assert structures[1].metadata["source"]["spacegroup"]["number"] == 191


def test_srtio3_selective_dynamics_and_qe_flags_and_labels():
    vasp, cif, qe = (read_structure(fx(n)) for n in ("SrTiO3.vasp", "SrTiO3.cif", "SrTiO3.pw.in"))
    for s in (vasp, cif, qe):
        np.testing.assert_allclose(s.cell, 3.905 * np.eye(3), atol=1e-12)
    assert_equivalent(vasp, cif)
    assert_equivalent(vasp, qe)  # QE file uses A = 3.905 with alat cell and positions
    expected_movable = [[0, 0, 0], [1, 1, 1], [1, 1, 0], [1, 1, 1], [1, 1, 1]]
    np.testing.assert_array_equal(vasp.movable, np.array(expected_movable, bool))
    np.testing.assert_array_equal(qe.movable, np.array(expected_movable, bool))
    assert cif.movable is None
    # Species labels are kept separately from elements.
    assert qe.labels == ("Sr", "Ti", "O1", "O1", "O_2")
    assert qe.symbols == ("Sr", "Ti", "O", "O", "O")
    assert qe.metadata["source"]["qe_species"] == {"Sr": "Sr", "Ti": "Ti", "O1": "O", "O_2": "O"}
    assert cif.labels == ("Sr1", "Ti1", "O1", "O1", "O1")
    np.testing.assert_array_equal(cif.occupancy, np.ones(5))


def test_triclinic_negative_scale_bohr_units_and_cif():
    expected = triclinic_cell(4.6, 5.3, 6.1, 78, 84, 71)
    fractions = np.array(
        [
            (0.10, 0.15, 0.20),
            (0.55, 0.30, 0.25),
            (0.25, 0.70, 0.40),
            (0.80, 0.75, 0.65),
            (0.35, 0.25, 0.80),
        ]
    )
    structures = [
        read_structure(fx(n)) for n in ("triclinic.vasp", "triclinic.cif", "triclinic.pw.in")
    ]
    for s in structures:
        np.testing.assert_allclose(s.cell, expected, atol=1e-8)
        np.testing.assert_allclose(s.positions, fractions @ expected, atol=1e-8)
        assert s.symbols == ("O", "Fe", "S", "Cl", "N")
    assert_equivalent(structures[0], structures[1])
    assert_equivalent(structures[0], structures[2])


def test_comparison_detects_differences():
    a = read_structure(fx("SrTiO3.vasp"))
    b = read_structure(fx("MgB2.vasp"))
    assert not compare_structures(a, b).equivalent
    shifted = a.replace(positions=a.positions + [0.01, 0, 0])
    result = compare_structures(a, shifted, tolerance=1e-3)
    assert not result.equivalent and "no partner" in result.message
    wrapped = a.replace(positions=a.positions + a.cell[0])  # whole lattice translation
    assert compare_structures(a, wrapped).equivalent


# ----- VASP 4 element mapping -----------------------------------------------------------------
def test_vasp4_requires_element_mapping_and_does_not_guess_from_comment():
    with pytest.raises(ElementMappingRequired) as info:
        read_structure(fx("POSCAR_vasp4"))
    question = info.value
    assert question.keys == ["species 1", "species 2"]
    assert question.suggestions == [None, None]  # "In plane strained GaN" is not trusted
    assert question.details == ["1 atom", "1 atom"]
    s = read_structure(fx("POSCAR_vasp4"), element_map={"species 1": "Ga", "species 2": "N"})
    assert s.symbols == ("Ga", "N")
    np.testing.assert_allclose(s.cell, 4.5 * np.eye(3))
    assert s.metadata["source"]["vasp_version"] == 4
    assert s.metadata["source"]["element_map"] == {"species 1": "Ga", "species 2": "N"}


def test_vasp4_suggests_symbols_listed_in_comment(tmp_path):
    text = fx("POSCAR_vasp4").read_text().replace("In plane strained GaN", "Ga N")
    path = tmp_path / "POSCAR"
    path.write_text(text)
    with pytest.raises(ElementMappingRequired) as info:
        read_structure(path)
    assert info.value.suggestions == ["Ga", "N"]


def test_vasp4_rejects_non_element_symbols():
    with pytest.raises(StructureImportError, match="not a chemical element"):
        read_structure(fx("POSCAR_vasp4"), element_map={"species 1": "Xx", "species 2": "N"})


# ----- CIF rejections and block choice ------------------------------------------------------------
def test_cif_partial_occupancy_is_rejected():
    with pytest.raises(UnsupportedStructureError) as info:
        read_structure(fx("partial_occupancy.cif"))
    assert "Fe1 (0.5)" in str(info.value) and "ordered" in str(info.value)


def test_cif_overlapping_sites_are_rejected():
    with pytest.raises(UnsupportedStructureError, match="Fe1 / Co1"):
        read_structure(fx("overlapping_sites.cif"))


def test_cif_block_choice():
    with pytest.raises(BlockChoiceRequired) as info:
        read_structure(fx("two_blocks.cif"))
    assert info.value.blocks == ["SrTiO3", "MgB2"]
    s = read_structure(fx("two_blocks.cif"), block="MgB2")
    assert s.composition() == "MgB2" and s.metadata["source"]["block"] == "MgB2"
    with pytest.raises(StructureImportError, match="no data block named"):
        read_structure(fx("two_blocks.cif"), block="nope")


# ----- QE rejections and labels -----------------------------------------------------------
# ----- QE input with ibrav other than 0 (FR-QE-IBRAV-01) ---------------------------------------
def test_qe_ibrav_2_is_the_fcc_cell_of_pw_x_and_the_same_silicon():
    a = 5.431
    qe = read_structure(fx("Si_ibrav2.pw.in"))  # celldm(1) in bohr, positions in alat
    expected = a / 2 * np.array([[-1, 0, 1], [0, 1, 1], [-1, 1, 0]])  # pw.x's fcc vectors
    np.testing.assert_allclose(qe.cell, expected, atol=1e-8)
    poscar = read_structure(fx("Si_primitive.vasp"))
    # Same lattice, other primitive vectors: QE's = P @ POSCAR's, with det P = 1.
    P = np.array([[1, 0, -1], [1, 0, 0], [1, -1, 0]])
    assert round(np.linalg.det(P)) == 1
    np.testing.assert_allclose(P @ poscar.cell, qe.cell, atol=1e-8)
    assert_equivalent(supercell(poscar, P), qe)
    source = qe.metadata["source"]
    assert source["qe_ibrav"] == 2 and source["qe_celldm"][0] == pytest.approx(10.2631026323)


def test_qe_ibrav_4_from_a_and_c_in_angstrom_is_mgb2():
    qe = read_structure(fx("MgB2_ibrav4.pw.in"))
    assert_equivalent(read_structure(fx("MgB2.vasp")), qe)
    assert qe.metadata["source"]["qe_celldm"][2] == pytest.approx(3.524 / 3.086)


def test_qe_ibrav_1_keeps_labels_and_flags():
    vasp, qe = read_structure(fx("SrTiO3.vasp")), read_structure(fx("SrTiO3_ibrav1.pw.in"))
    np.testing.assert_allclose(qe.cell, 3.905 * np.eye(3), atol=1e-9)
    assert_equivalent(vasp, qe)
    assert qe.labels == ("Sr", "Ti", "O1", "O1", "O_2")
    np.testing.assert_array_equal(qe.movable, vasp.movable)


def test_qe_ibrav_14_puts_each_cosine_on_its_angle():
    """cosBC is cos(alpha), cosAC cos(beta), cosAB cos(gamma), as in pw.x."""
    qe = read_structure(fx("triclinic_ibrav14.pw.in"))
    np.testing.assert_allclose(qe.cell, triclinic_cell(4.6, 5.3, 6.1, 78, 84, 71), atol=1e-9)
    assert_equivalent(read_structure(fx("triclinic.pw.in")), qe)


@pytest.mark.parametrize("form", ["celldm", "abc"])
@pytest.mark.parametrize("ibrav", list(IBRAV_LATTICES))
def test_every_ibrav_reads_with_the_documented_vectors(tmp_path, ibrav, form):
    """All 20 lattices of pw.x through the reader, in both parameter forms."""
    from ase.io.espresso import units

    from test_qe_lattice import COS_BETA, COS_GAMMA, celldm, documented_vectors

    bohr = units["Bohr"]
    cd = celldm(ibrav)  # a, b/a, c/a in bohr units, and the cosines
    if form == "celldm":
        lattice = ", ".join(f"celldm({i + 1}) = {v!r}" for i, v in enumerate(cd))
    else:
        a = cd[0] * bohr
        cosines = {
            14: {"cosBC": cd[3], "cosAC": COS_BETA, "cosAB": COS_GAMMA},
            -12: {"cosAC": COS_BETA},
            -13: {"cosAC": COS_BETA},
            12: {"cosAB": COS_GAMMA},
            13: {"cosAB": COS_GAMMA},
            5: {"cosAB": cd[3]},
            -5: {"cosAB": cd[3]},
        }.get(ibrav, {})
        parts = [f"A = {a!r}", f"B = {a * cd[1]!r}", f"C = {a * cd[2]!r}"]
        lattice = ", ".join(parts + [f"{k} = {v!r}" for k, v in cosines.items()])
    path = tmp_path / "x.pw.in"
    path.write_text(
        f"&SYSTEM\n  ibrav = {ibrav}, {lattice}, nat = 2, ntyp = 1\n/\n"
        "ATOMIC_SPECIES\n  Mg 1.0 Mg.upf\n"
        "ATOMIC_POSITIONS crystal\n  Mg 0 0 0\n  Mg 0.1 0.2 0.3\n"
    )
    structure = read_structure(path)
    expected = np.array(documented_vectors(ibrav)) * bohr
    np.testing.assert_allclose(structure.cell, expected, atol=1e-9)
    np.testing.assert_allclose(
        structure.positions[1], np.array([0.1, 0.2, 0.3]) @ expected, atol=1e-9
    )
    assert structure.metadata["source"]["qe_ibrav"] == ibrav


def _qe(tmp_path, system: str, positions: str = "crystal\n  Mg 0 0 0", extra: str = ""):
    path = tmp_path / "x.pw.in"
    path.write_text(
        f"&SYSTEM\n  {system}, nat = 1, ntyp = 1\n/\nATOMIC_SPECIES\n  Mg 1.0 Mg.upf\n"
        f"{extra}ATOMIC_POSITIONS {positions}\n"
    )
    return path


def test_qe_alat_positions_use_the_lattice_parameter_of_ibrav(tmp_path):
    s = read_structure(_qe(tmp_path, "ibrav = 6, A = 3.0, C = 5.0", "alat\n  Mg 0.5 0.5 1.0"))
    np.testing.assert_allclose(s.positions, [[1.5, 1.5, 3.0]], atol=1e-12)  # alat = a, not c
    np.testing.assert_allclose(s.cell, np.diag([3.0, 3.0, 5.0]), atol=1e-12)


@pytest.mark.parametrize(
    ("system", "extra", "message"),
    [
        ("ibrav = 4, celldm(1) = 5.83", "", "ibrav = 4 needs celldm(3) or C > 0"),
        ("ibrav = 8, A = 3, C = 4", "", "ibrav = 8 needs celldm(2) or B > 0"),
        ("ibrav = 12, A = 3, B = 4, C = 5, cosAB = 1.0", "", "celldm(4) = cos(gamma)"),
        ("ibrav = 5, celldm(1) = 9, celldm(4) = -0.5", "", "cos(alpha) < 1"),
        ("ibrav = 15, celldm(1) = 9", "", "not a pw.x Bravais lattice"),
        ("ibrav = 1, celldm(1) = 9, A = 4.7", "", "given twice"),
        ("ibrav = 1", "", "needs the lattice parameters"),
        ("ibrav = 1, A = 4", "CELL_PARAMETERS angstrom\n 4 0 0\n 0 4 0\n 0 0 4\n", "redundant"),
        (
            "ibrav = 14, A = 3, B = 3, C = 3, cosAB = 0.9, cosAC = -0.9, cosBC = 0.9",
            "",
            "do not make a cell",
        ),
    ],
)
def test_qe_ibrav_errors_are_explained(tmp_path, system, extra, message):
    with pytest.raises(StructureImportError) as error:
        read_structure(_qe(tmp_path, system, extra=extra))
    assert message in str(error.value) and "x.pw.in" in str(error.value)


# ----- numbers as pw.x reads them -----------------------------------------------------------------
@pytest.mark.parametrize(
    ("expression", "value"),
    [
        ("0.25", 0.25),
        ("1/4", 0.25),
        ("2*(1/8)", 0.25),
        ("1/(2/(1/2))", 0.25),
        ("(1+1)*0", 0.0),
        ("1-1", 0.0),
        ("0/2", 0.0),
        ("1--1", 2.0),
        ("-2^2", -4.0),  # the sign binds like ^, from the right
        ("2^-1", 0.5),
        ("2^3^2", 512.0),  # ^ groups from the right
        ("8/2/2", 2.0),  # / groups from the left
        ("1-2-3", -4.0),
        ("-2*3", -6.0),
        ("+3", 3.0),
        (".5", 0.5),
        ("5.", 5.0),
        ("1.5d-1", 0.15),
        ("2.5D0*2", 5.0),
        ("1e1/4", 2.5),
        ("3^(1/2)^2", 3.0**0.25),
    ],
)
def test_coordinates_are_evaluated_as_pw_x_does(expression, value):
    assert evaluate_qe_expression(expression) == pytest.approx(value, rel=1e-15, abs=1e-15)


@pytest.mark.parametrize("expression", ["", "1/0", "2*", "(1+2", "1+2)", "abc", "1,5", "(-1)^0.5"])
def test_coordinates_pw_x_cannot_evaluate_are_refused(expression):
    with pytest.raises(ValueError):
        evaluate_qe_expression(expression)


def test_fortran_reals_get_python_exponents_and_nothing_else_changes():
    assert [fortran_real(t) for t in ("16.D0", "1.5d-3", "-.5D+2", "7d0")] == [
        "16.E0",
        "1.5e-3",
        "-.5E+2",
        "7e0",
    ]
    for unchanged in ("16.0", "Si.pbe-d.UPF", "d0", "Cd", "1.5e-3", "0.5"):
        assert fortran_real(unchanged) == unchanged


def test_fortran_numbers_and_expressions_read_like_plain_numbers(tmp_path):
    """Masses and cell in Fortran notation, positions as expressions, as pw.x accepts."""
    plain = tmp_path / "plain.pw.in"
    plain.write_text(
        "&SYSTEM\n  ibrav = 0, nat = 2, ntyp = 1\n/\nATOMIC_SPECIES\n  Si 28.0855 Si.upf\n"
        "CELL_PARAMETERS angstrom\n  0.0 2.7155 2.7155\n  2.7155 0.0 2.7155\n"
        "  2.7155 2.7155 0.0\nATOMIC_POSITIONS crystal\n  Si 0.0 0.0 0.0\n"
        "  Si 0.25 0.25 0.25 0 1 1\n"
    )
    fortran = tmp_path / "fortran.pw.in"
    fortran.write_text(
        "&SYSTEM\n  ibrav = 0, nat = 2, ntyp = 1\n/\nATOMIC_SPECIES\n  Si 28.0855D0 Si.upf\n"
        "CELL_PARAMETERS angstrom\n  0.D0 2.7155d0 2.7155D+00\n  2.7155d0 0.d0 2.7155D0\n"
        "  2.7155D0 2.7155D0 0.0\nATOMIC_POSITIONS crystal\n  Si 1-1 0/2 (1+1)*0\n"
        "  Si 1/4 2*(1/8) 1/(2/(1/2)) 0 1 1\n"
    )
    a, b = read_structure(plain), read_structure(fortran)
    np.testing.assert_array_equal(a.cell, b.cell)
    np.testing.assert_array_equal(a.positions, b.positions)
    np.testing.assert_array_equal(a.movable, b.movable)  # the if_pos flags stay integers


def test_a_coordinate_pw_x_cannot_evaluate_is_explained(tmp_path):
    path = _qe(tmp_path, "ibrav = 1, A = 4", "crystal\n  Mg 1/0 0 0")
    with pytest.raises(StructureImportError, match="ATOMIC_POSITIONS line 'Mg 1/0 0 0'.*division"):
        read_structure(path)


def test_qe_crystal_sg_and_missing_cell():
    with pytest.raises(UnsupportedStructureError, match="crystal_sg"):
        read_structure(fx("qe_crystal_sg.pw.in"))
    with pytest.raises(StructureImportError, match="requires a CELL_PARAMETERS card"):
        read_structure(fx("qe_no_cell.pw.in"))


def test_qe_ambiguous_label_needs_mapping():
    with pytest.raises(ElementMappingRequired) as info:
        read_structure(fx("qe_ambiguous_label.pw.in"))
    assert info.value.keys == ["Cb"] and info.value.suggestions == ["C"]
    s = read_structure(fx("qe_ambiguous_label.pw.in"), element_map={"Cb": "C"})
    assert s.symbols == ("C", "Fe") and s.labels == ("Cb", "Fe1")


@pytest.mark.parametrize(
    "label, element",
    [
        ("Fe", "Fe"),
        ("fe1", "Fe"),
        ("Fe_up", "Fe"),
        ("O-2", "O"),
        ("C1", "C"),
        ("Sn", "Sn"),
        ("He", "He"),
        ("Cb", None),
        ("Feup", None),
        ("X1", None),
        ("1Fe", None),
    ],
)
def test_element_from_label(label, element):
    assert element_from_label(label) == element


# ----- malformed files and provenance --------------------------------------------------------
def test_truncated_poscar_message():
    with pytest.raises(StructureImportError) as info:
        read_structure(fx("POSCAR_truncated"))
    assert "3 atoms" in str(info.value) and "truncated" in str(info.value)


def test_missing_file_and_project_passed_as_structure(tmp_path):
    with pytest.raises(StructureImportError, match="Cannot read"):
        read_structure(tmp_path / "missing.cif")
    with pytest.raises(StructureImportError, match="Ycrystal project"):
        read_structure(fx("SrTiO3.cif"), fmt="project")


def test_wrong_explicit_format_gives_a_readable_error():
    with pytest.raises(StructureImportError, match="not a valid POSCAR"):
        read_structure(fx("SrTiO3.cif"), fmt="poscar")
    with pytest.raises(StructureImportError):
        read_structure(fx("SrTiO3.vasp"), fmt="cif")


def test_provenance_is_recorded():
    path = fx("MgB2.cif")
    source = read_structure(path).metadata["source"]
    assert source["format"] == "cif" and source["name"] == "MgB2.cif"
    assert source["path"] == str(path.resolve())
    assert source["sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
    assert source["reader"].startswith("ASE ")
