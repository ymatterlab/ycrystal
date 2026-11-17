# Test fixtures

Small synthetic structures written by hand from textbook lattice constants. Expected
cells and positions in the tests are computed from the same constants with explicit
formulas, independently of the readers under test.

| Structure | Constants | Files |
| --- | --- | --- |
| Si, diamond | a = 5.431 Å | `Si_primitive.vasp` (fcc primitive cell), `Si.pw.in` (`celldm(1)` = 5.431 Å / 0.5291772083535413 Å, `CELL_PARAMETERS alat`, crystal positions), `Si_conventional.cif` (F d -3 m, origin choice 1, Si at 0 0 0) |
| MgB2, P6/mmm | a = 3.086 Å, c = 3.524 Å | `MgB2.vasp` (Cartesian coordinates), `MgB2.cif` (24 explicit symmetry operations), `MgB2.pw.in` (angstrom cell, crystal positions) |
| SrTiO3, Pm-3m | a = 3.905 Å | `SrTiO3.vasp` (selective dynamics), `SrTiO3.cif` (space-group symbol, uncertainties), `SrTiO3.pw.in` (`A` + alat cell and positions, labels `O1`/`O_2`, `if_pos` flags) |
| BaZrO3, Pm-3m (cubic perovskite, same site positions as SrTiO3) | a = 4.19 Å, rounded; for demonstrating style transfer between compositions, not as reference data | `BaZrO3.cif` |
| Triclinic P1 | a, b, c = 4.6, 5.3, 6.1 Å; α, β, γ = 78°, 84°, 71° | `triclinic.vasp` (vectors and Cartesian positions at half size with a negative scale factor = volume), `triclinic.cif`, `triclinic.pw.in` (bohr cell and positions) |

The triclinic lattice uses a ∥ x and b in the xy plane:
a = (a, 0, 0); b = (b cos γ, b sin γ, 0);
c = (c cos β, c (cos α − cos β cos γ) / sin γ, c √(1 − cos²β − ((cos α − cos β cos γ)/sin γ)²)).
QE's bohr is 0.5291772083535413 Å (CODATA 2006, as QE and ASE use).

Unsupported or malformed inputs: `qe_ibrav2.pw.in`, `qe_crystal_sg.pw.in`,
`qe_no_cell.pw.in`, `qe_ambiguous_label.pw.in`, `partial_occupancy.cif`,
`overlapping_sites.cif`, `two_blocks.cif` (needs a block choice), `POSCAR_vasp4` (no
element line; misleading comment), `POSCAR_truncated`, `not_a_structure.txt`.
