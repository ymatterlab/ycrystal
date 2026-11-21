# Quantum ESPRESSO lattices (`ibrav`)

In a pw.x input, the `ibrav` variable of `&SYSTEM` chooses how the cell is given:

- `ibrav = 0`: the lattice vectors are written out in a `CELL_PARAMETERS` card;
- any other value: `ibrav` names a Bravais lattice, and pw.x builds the lattice vectors
  itself from a few parameters, `celldm(1)` … `celldm(6)` or `A, B, C, cosAB, cosAC,
  cosBC`.

Ycrystal reads both. For `ibrav` other than 0 it builds **the same lattice vectors as
pw.x**, with pw.x's orientation and choice of primitive vectors. This matters because
`ATOMIC_POSITIONS {crystal}` gives fractions of exactly those vectors: another choice of
vectors for the same lattice would put the atoms elsewhere. ASE, which Ycrystal uses
for the rest of the file, does not read `ibrav` other than 0 (ASE 3.29), so the lattice
is built by Ycrystal's own module, [`ycrystal.io.qe_lattice`](../reference/io.md),
following the pw.x input documentation (`INPUT_PW`, variable `ibrav`) and pw.x's lattice
generator (`Modules/latgen.f90`).

## Applicable cases

Every `ibrav` that pw.x accepts is read. In the table, a, b, c are the lattice
parameters, α the angle between b and c, β between a and c, γ between a and b. The
vectors v1, v2, v3 are the rows of the cell that Ycrystal shows and exports.

| `ibrav` | Lattice | Parameters needed | v1, v2, v3 |
| --- | --- | --- | --- |
| 1 | cubic P (simple cubic) | a | (a, 0, 0), (0, a, 0), (0, 0, a) |
| 2 | cubic F (fcc) | a | (a/2)(−1, 0, 1), (a/2)(0, 1, 1), (a/2)(−1, 1, 0) |
| 3 | cubic I (bcc) | a | (a/2)(1, 1, 1), (a/2)(−1, 1, 1), (a/2)(−1, −1, 1) |
| −3 | cubic I (bcc), more symmetric axes | a | (a/2)(−1, 1, 1), (a/2)(1, −1, 1), (a/2)(1, 1, −1) |
| 4 | hexagonal and trigonal P | a, c | (a, 0, 0), (−a/2, a√3/2, 0), (0, 0, c) |
| 5 | trigonal R, threefold axis along z | a, cos α | (a·tx, −a·ty, a·tz), (0, 2a·ty, a·tz), (−a·tx, −a·ty, a·tz) |
| −5 | trigonal R, threefold axis along (111) | a, cos α | (a′u, a′v, a′v), (a′v, a′u, a′v), (a′v, a′v, a′u) |
| 6 | tetragonal P | a, c | (a, 0, 0), (0, a, 0), (0, 0, c) |
| 7 | tetragonal I (bct) | a, c | (a/2, −a/2, c/2), (a/2, a/2, c/2), (−a/2, −a/2, c/2) |
| 8 | orthorhombic P | a, b, c | (a, 0, 0), (0, b, 0), (0, 0, c) |
| 9 | orthorhombic base-centred (C) | a, b, c | (a/2, b/2, 0), (−a/2, b/2, 0), (0, 0, c) |
| −9 | orthorhombic base-centred (C), alternate axes | a, b, c | (a/2, −b/2, 0), (a/2, b/2, 0), (0, 0, c) |
| 91 | orthorhombic one-face base-centred (A) | a, b, c | (a, 0, 0), (0, b/2, −c/2), (0, b/2, c/2) |
| 10 | orthorhombic face-centred | a, b, c | (a/2, 0, c/2), (a/2, b/2, 0), (0, b/2, c/2) |
| 11 | orthorhombic body-centred | a, b, c | (a/2, b/2, c/2), (−a/2, b/2, c/2), (−a/2, −b/2, c/2) |
| 12 | monoclinic P, unique axis c | a, b, c, cos γ | (a, 0, 0), (b cos γ, b sin γ, 0), (0, 0, c) |
| −12 | monoclinic P, unique axis b | a, b, c, cos β | (a, 0, 0), (0, b, 0), (c cos β, 0, c sin β) |
| 13 | monoclinic base-centred, unique axis c | a, b, c, cos γ | (a/2, 0, −c/2), (b cos γ, b sin γ, 0), (a/2, 0, c/2) |
| −13 | monoclinic base-centred, unique axis b | a, b, c, cos β | (a/2, b/2, 0), (−a/2, b/2, 0), (c cos β, 0, c sin β) — see [QE versions](#quantum-espresso-versions) |
| 14 | triclinic | a, b, c, cos α, cos β, cos γ | (a, 0, 0), (b cos γ, b sin γ, 0), (c cos β, c (cos α − cos β cos γ)/sin γ, c √(1 + 2 cos α cos β cos γ − cos²α − cos²β − cos²γ)/sin γ) |

For `ibrav = 5`: tx = √((1 − cos α)/2), ty = √((1 − cos α)/6), tz = √((1 + 2 cos α)/3).
For `ibrav = −5`: a′ = a/√3, u = tz − 2√2·ty, v = tz + √2·ty. In both, a is the length
of each vector and α the angle between any two of them.

### Two ways to give the parameters

Either form works, but not both in one file (pw.x refuses that too):

| Parameter | `celldm` form (lengths in bohr) | Crystallographic form (lengths in Å) |
| --- | --- | --- |
| a | `celldm(1)` | `A` |
| b | `celldm(2)` = b/a | `B` |
| c | `celldm(3)` = c/a | `C` |
| cos α of `ibrav` 5, −5 (rhombohedral angle) | `celldm(4)` | `cosAB` |
| cos γ of `ibrav` 12, 13 | `celldm(4)` | `cosAB` |
| cos β of `ibrav` −12, −13 | `celldm(5)` | `cosAC` |
| cos α, cos β, cos γ of `ibrav` 14 | `celldm(4)`, `celldm(5)`, `celldm(6)` | `cosBC`, `cosAC`, `cosAB` |

This is pw.x's own mapping (its routine `abc2celldm`). Note the one surprise it
contains: for the rhombohedral lattices (5, −5) the angle α is given as `cosAB`.
Parameters a lattice does not use are ignored, as in pw.x (for example `celldm(4)` with
`ibrav = 8`).

### Atom positions

- `crystal`: fractions of v1, v2, v3 above.
- `alat`: multiples of a (`celldm(1)` or `A`), as in pw.x — not of b or c.
- `bohr` and `angstrom`: Cartesian coordinates, as for `ibrav = 0`.
- `if_pos` flags (0/1) are kept, as for `ibrav = 0`.
- As in pw.x, each coordinate may be simple arithmetic (`1/4`, `2*(1/8)`, `1/(2/(1/2))`),
  and numbers may be written in Fortran notation (`0.25d0`, and `16.D0` for a mass); see
  [structure files](../FORMATS.md#quantum-espresso-pwx-input) for the rules. This holds
  for every `ibrav`, 0 included.

### What Ycrystal records

The structure's source record (`metadata["source"]`, saved in projects) keeps
`qe_ibrav` and `qe_celldm` (`celldm(1)` in bohr, then the five other values; from the
crystallographic form after pw.x's mapping), next to the file's name and checksum.

## Cases that are not applicable

Ycrystal refuses these files with a message that names the file and the problem. pw.x
refuses them too, with two exceptions: `crystal_sg` positions, which pw.x supports and
Ycrystal does not, and a triclinic cell of zero volume, which passes pw.x's lattice
check but cannot be used.

| Input | Message (shortened) |
| --- | --- |
| An `ibrav` pw.x does not know (for example 15 or −4) | `ibrav = 15 is not a pw.x Bravais lattice (known: 0, 1, 2, …)` |
| No lattice parameters | `ibrav = 1 needs the lattice parameters: celldm(1)…celldm(6) or A, B, C, …` |
| Both `celldm` and `A, B, C, cos…` | `the lattice is given twice …` |
| A parameter the lattice needs is missing, zero, or negative (for example `C` for `ibrav = 4`) | `ibrav = 4 needs celldm(3) or C > 0.` |
| A cosine outside −1 … 1, or exactly ±1 for an angle the lattice uses | `ibrav = 12 needs celldm(4) = cos(gamma) strictly between −1 and 1, …` |
| A rhombohedral angle with cos α ≤ −1/2 or ≥ 1 (`ibrav` 5, −5) | `ibrav = 5 needs −1/2 < celldm(4) = cos(alpha) < 1 …` |
| Triclinic angles that do not close a cell | `the angles of this triclinic cell … do not make a cell with a volume.` |
| A `CELL_PARAMETERS` card together with `ibrav` other than 0 | `… pw.x refuses this (redundant cell) …` |
| `ATOMIC_POSITIONS {crystal_sg}` (positions reduced by a space group; supported by pw.x, not by Ycrystal) | `… crystal_sg (symmetry-reduced) form, which Ycrystal does not support …` |
| A triclinic cell whose angles give exactly zero volume (passes pw.x's lattice check) | `the angles of this triclinic cell … do not make a cell with a volume.` |
| A coordinate pw.x's arithmetic cannot evaluate (`1/0`, an unbalanced parenthesis, a letter) | `ATOMIC_POSITIONS line 'Mg 1/0 0 0': division by zero in '1/0'.` |

Not detected, and therefore not refused: a file with `ibrav = −13` and `crystal`
positions written for **QE 6.4.1 or older** opens with the current axes, which puts the
atoms in other places (see the next section). Ycrystal cannot tell from the file which
version of QE it was written for.

## Quantum ESPRESSO versions

Ycrystal follows **current QE (6.5 and later)**. For all lattices except one, that is
also every older version: the lattice code of each `ibrav` in `latgen.f90` was compared,
as text, in 23 releases from QE 4.3.2 to the current development branch, and only
`ibrav = −13` changed. In detail:

| What | Depends on the QE version? |
| --- | --- |
| Vectors of `ibrav` 1–14, −3, −5, −9, −12, 91 | No: unchanged since each value appeared |
| Vectors of `ibrav = −13` | **Yes.** QE 5.2.0 to 6.4.1 used other axes: v1(old) = −v2(new), v2(old) = v1(new). QE 6.5 changed them ("crystal axis converted to a more standard orientation", release notes of 6.5), and pw.x prints *BEWARE: axis for ibrav=-13 changed*. The lattice is the same, so `alat`, `bohr`, and `angstrom` positions are unaffected; `crystal` positions written for the old axes must be converted with (x, y, z) → (y, −x, z), as QE's release notes say. Ycrystal reads them as new-axes positions. |
| `A, B, C, cos…` for `ibrav = −13` | **Yes.** QE 6.2.x did not read `cosAC` for −13 (fixed in 6.3, release notes). Ycrystal follows 6.3 and later. Versions before 6.2.0 were not checked for this mapping. |
| Which `ibrav` values exist | 1–14, −5, −12 in every version checked (4.3.2 onwards); −9 since 5.0; 91 and −13 since 5.2.0; −3 since 6.2.0. A file with a newer value does not run on an older pw.x, but Ycrystal reads it. |
| Length of the bohr (for `celldm(1)` and `bohr` units) | Slightly. Ycrystal uses ASE's value, 0.5291772083535 Å (CODATA 2006), as it already did for `ibrav = 0`. QE used 0.52917720859 Å (CODATA 2006) up to 6.5, and uses 0.529177210903 Å (CODATA 2018) since 6.6. The relative differences, 4.5 × 10⁻¹⁰ and 4.8 × 10⁻⁹, are below 5 × 10⁻⁸ Å for a 10 Å cell. Lengths given in Å (`A, B, C`, `angstrom`) are not affected. |

## How this was verified, and what was not

Audited on 21 November 2026. Each lattice is checked in up to five independent ways:

1. **Documented vectors:** the vectors Ycrystal builds equal those written in `INPUT_PW`
   (typed into the test from the documentation, not from the code), within 1e-12
   (`tests/test_qe_lattice.py`).
2. **Through the reader, in both forms:** a pw.x input with `celldm` and one with
   `A, B, C, cos…` are read with `read_structure` and give the documented vectors and
   the right Cartesian positions for crystal coordinates, within 1e-9 Å
   (`tests/test_readers.py`).
3. **Lattice geometry:** the conventional cell and its centring vectors are whole-number
   combinations of v1, v2, v3, and the volumes differ by the number of lattice points;
   for the rhombohedral lattices the lengths, the angle, and the threefold axis; for the
   triclinic lattice the lengths and the three angles (`tests/test_qe_lattice.py`).
4. **pw.x's own output:** every input with `ibrav` other than 0 in QE's test suite that
   has a stored pw.x output, read with Ycrystal and compared with the crystal axes,
   `celldm(1)`, and atom positions pw.x printed (`scripts/check_qe_ibrav.py
   --qe-checkout`, QE development branch). Agreement means within pw.x's printed
   precision: axes 2e-6 alat (6 decimals), positions 2e-7 alat (7 decimals), `celldm(1)`
   2e-7 relative.
5. **Independent code:** ASE 3.22.1's former `ibrav_to_cell`, in a copy with its
   `ibrav = 11` typo fixed and −13 added (not part of Ycrystal), on 200 random parameter
   sets per lattice in both forms; largest difference 4e-15 Å.

| `ibrav` | 1 Documented | 2 Reader, both forms | 3 Geometry | 4 pw.x output: inputs (forms) | 5 Independent code |
| --- | --- | --- | --- | --- | --- |
| 1 | Yes | Yes | Yes | 63 (`celldm`, `A`) | Yes |
| 2 | Yes | Yes | Yes | 140 (`celldm`, `A`) | Yes |
| 3 | Yes | Yes | Yes | 13 (`celldm`) | Yes |
| −3 | Yes | Yes | Yes | 2 (`celldm`) | Yes |
| 4 | Yes | Yes | Yes | 27 (`celldm`, `A`) | Yes |
| 5 | Yes | Yes | Yes (rhombohedral) | 8 (`celldm`) | Yes |
| −5 | Yes | Yes | Yes (rhombohedral) | 4 (`celldm`) | Yes |
| 6 | Yes | Yes | Yes | 10 (`celldm`, `A`) | Yes |
| 7 | Yes | Yes | Yes | 2 (`celldm`) | Yes |
| 8 | Yes | Yes | Yes | 4 (`celldm`) | Yes |
| 9 | Yes | Yes | Yes | 2 (`celldm`) | Yes |
| −9 | Yes | Yes | Yes | **none: no such input in QE** | Yes |
| 91 | Yes | Yes | Yes | **none: no such input in QE** | **No** (that code has no 91) |
| 10 | Yes | Yes | Yes | 2 (`celldm`) | Yes |
| 11 | Yes | Yes | Yes | 2 (`celldm`) | Yes |
| 12 | Yes | Yes | Yes | 2 (`celldm`) | Yes |
| −12 | Yes | Yes | Yes | 2 (`celldm`) | Yes |
| 13 | Yes | Yes | Yes | 2 (`celldm`) | Yes |
| −13 | Yes | Yes | Yes | **none: no such input in QE** | Yes |
| 14 | Yes | Yes | Yes (lengths, angles) | 10 (`celldm`, `A`) | Yes |

In total 295 QE inputs were compared and all agree (for 8 of them, QEHeat inputs whose
atom positions come from a trajectory, only the axes). The tests run every statement of
`ycrystal.io.qe_lattice` and of the reader's `ibrav` branch. Refused inputs and their
messages are tested too (`tests/test_readers.py`, `tests/test_qe_lattice.py`), and the
existing equivalence tests read Si (`ibrav = 2`), MgB2 (4, from `A`, `C`), SrTiO3 (1),
and a triclinic cell (14, from `A, B, C, cos…`) as the same structures as their
POSCAR, CIF, and `ibrav = 0` files.

Where the comparison with pw.x's output does not apply, the script says why. In QE's
test suite these are inputs whose structure pw.x read from an earlier run (a restart:
the printed cell is not the input's) and inputs with no stored pw.x output (for example
CP inputs): 106 in all. Six inputs that Ycrystal could not read at first, for reasons
unrelated to `ibrav`, are read since the same day and agree: five give atomic masses as
Fortran numbers such as `16.D0`, and one gives positions as arithmetic (`1/4`,
`2*(1/8)`); pw.x accepts both. A separate check of the same kind on QE's 37 applicable
`ibrav = 0` inputs found all of them read and in agreement too.

### Check it yourself

The comparison with pw.x's output needs no QE installation and no pw.x run:

```bash
# QE's 17 lattice tests, downloaded from GitHub (network access needed):
.venv/bin/python scripts/check_qe_ibrav.py
# Every applicable input of QE's test suite, from a local copy (about 200 MB):
git clone --depth 1 --filter=blob:none --sparse https://github.com/QEF/q-e.git q-e
git -C q-e sparse-checkout set test-suite
.venv/bin/python scripts/check_qe_ibrav.py --qe-checkout q-e
```

The script prints, per `ibrav`, the number of inputs and the largest differences, then
the inputs where the comparison does not apply and why; it exits with status 1 if any
input differs. QE's files are GPL and stay outside Ycrystal's repository.

Not tested:

- **`ibrav` −9, 91, and −13 against pw.x itself:** no input in QE's test suite or
  examples uses them, and pw.x was not run here. They rest on checks 1–3, and −9 and
  −13 also on 5. `ibrav = 91` is the least checked lattice: its vectors are confirmed
  only against the documentation and by its geometry.
- **The `A, B, C, cos…` form against pw.x for the lattices with angles (5, −5, 12, −12,
  13, −13):** QE's tests give these only with `celldm`. The mapping follows pw.x's
  routine `abc2celldm`, read from its source, and is checked by the tests' own table.
- **Older QE versions by running them:** the version comparison above reads QE's
  source and release notes; no older pw.x was run.
- **macOS and Windows:** the tests run there in continuous integration once the change
  is merged; the comparison with pw.x's output was run on Linux.
