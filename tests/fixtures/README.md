# Test fixtures

Small structure files written by hand for this project from textbook lattice constants
(MIT licence, like the rest of the repository; no third-party data). Expected cells and
positions in the tests are computed from the same constants with explicit formulas,
independently of the readers under test.

Which are real compounds and which are synthetic (FR-VALIDATION-01):

- **Real compounds, idealised:** Si, MgB2, SrTiO3, and BaZrO3 describe real crystal
  structures with rounded textbook constants. They are test and demonstration inputs,
  not refined reference data.
- **Synthetic:** the triclinic P1 cell is invented (arbitrary cell, five arbitrary
  atoms; not a compound). `examples/vectors-synthetic-afm.ycrystal` is a synthetic
  two-site cubic cell with magnetic moments of ±2.2 μB assigned by hand; it is not a
  real material.

| Structure | Constants | Files |
| --- | --- | --- |
| Si, diamond | a = 5.431 Å | `Si_primitive.vasp` (fcc primitive cell), `Si.pw.in` (`celldm(1)` = 5.431 Å / 0.5291772083535413 Å, `CELL_PARAMETERS alat`, crystal positions), `Si_conventional.cif` (F d -3 m, origin choice 1, Si at 0 0 0), `Si_ibrav2.pw.in` (`ibrav = 2`, the same `celldm(1)`, alat positions) |
| MgB2, P6/mmm | a = 3.086 Å, c = 3.524 Å | `MgB2.vasp` (Cartesian coordinates), `MgB2.cif` (24 explicit symmetry operations), `MgB2.pw.in` (angstrom cell, crystal positions), `MgB2_ibrav4.pw.in` (`ibrav = 4` with `A`, `C`) |
| SrTiO3, Pm-3m | a = 3.905 Å | `SrTiO3.vasp` (selective dynamics), `SrTiO3.cif` (space-group symbol, uncertainties), `SrTiO3.pw.in` (`A` + alat cell and positions, labels `O1`/`O_2`, `if_pos` flags), `SrTiO3_ibrav1.pw.in` (`ibrav = 1`, `celldm(1)` = 3.905 Å / 0.5291772083535413 Å, crystal positions) |
| BaZrO3, Pm-3m (cubic perovskite, same site positions as SrTiO3) | a = 4.19 Å, rounded; for demonstrating style transfer between compositions, not as reference data | `BaZrO3.cif` |
| Triclinic P1 | a, b, c = 4.6, 5.3, 6.1 Å; α, β, γ = 78°, 84°, 71° | `triclinic.vasp` (vectors and Cartesian positions at half size with a negative scale factor = volume), `triclinic.cif`, `triclinic.pw.in` (bohr cell and positions), `triclinic_ibrav14.pw.in` (`ibrav = 14` with `A, B, C` and cosBC = cos α, cosAC = cos β, cosAB = cos γ; crystal positions) |

The triclinic lattice uses a ∥ x and b in the xy plane:
a = (a, 0, 0); b = (b cos γ, b sin γ, 0);
c = (c cos β, c (cos α − cos β cos γ) / sin γ, c √(1 − cos²β − ((cos α − cos β cos γ)/sin γ)²)).
Lengths in bohr are converted with ASE's bohr, 0.5291772083535413 Å (CODATA 2006), as
Ycrystal does. pw.x itself used 0.52917720859 Å up to QE 6.5 and uses 0.529177210903 Å
(CODATA 2018) since 6.6; the differences are below 5e-9 relative (see
`docs/guide/qe-lattices.md`).

The `ibrav` files describe the same structures as the other files of their row, with
pw.x's lattice vectors (for Si another primitive cell of the same lattice).

Unsupported or malformed inputs: `qe_ibrav4_no_c.pw.in` (`ibrav = 4` without `c`),
`qe_crystal_sg.pw.in`,
`qe_no_cell.pw.in`, `qe_ambiguous_label.pw.in`, `partial_occupancy.cif`,
`overlapping_sites.cif`, `two_blocks.cif` (needs a block choice), `POSCAR_vasp4` (no
element line; misleading comment), `POSCAR_truncated`, `not_a_structure.txt`.
