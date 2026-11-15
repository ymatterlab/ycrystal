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
from ycrystal.io.readers import (
    BlockChoiceRequired,
    ElementMappingRequired,
    FormatChoiceRequired,
    StructureImportError,
    UnsupportedStructureError,
    detect_format,
    element_from_label,
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
def test_qe_nonzero_ibrav_is_rejected_without_guessing():
    with pytest.raises(UnsupportedStructureError) as info:
        read_structure(fx("qe_ibrav2.pw.in"))
    message = str(info.value)
    assert "ibrav = 2" in message and "CELL_PARAMETERS" in message


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
