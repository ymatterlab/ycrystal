"""Check Ycrystal's QE lattices (``ibrav`` other than 0) against pw.x's own output.

Quantum ESPRESSO's test suite (``test-suite/pw_lattice-ibrav``) has a pw.x input and a
reference output for most Bravais lattices. The output prints the crystal axes and atom
positions pw.x built, in units of ``alat``. This script downloads the inputs and outputs
(they are GPL files of QE and are not part of Ycrystal), reads each input with
Ycrystal, and compares. pw.x prints the axes with 6 decimals and positions with 7, so
differences up to about 5e-7 alat are rounding.

With ``--qe-checkout``, every pw.x input with ``ibrav`` other than 0 in a local copy
of QE's ``test-suite`` that has a stored pw.x output is compared instead (about 400
such inputs, about 300 of them applicable; no network needed). Inputs where the
comparison does not apply are listed separately: pw.x took the structure from an
earlier run ("unit cell read from directory"), or the positions from a trajectory
(QEHeat: only the axes are compared), or Ycrystal cannot read the file for a reason
unrelated to ``ibrav``.

Usage::

    .venv/bin/python scripts/check_qe_ibrav.py [--ref develop] [--keep FOLDER]
    .venv/bin/python scripts/check_qe_ibrav.py --qe-checkout PATH_TO_Q-E

A checkout that contains only the test suite is enough::

    git clone --depth 1 --filter=blob:none --sparse https://github.com/QEF/q-e.git q-e
    git -C q-e sparse-checkout set test-suite

Exits with status 1 if any lattice differs. Needs no QE installation.
"""

from __future__ import annotations

import argparse
import re
import sys
import tempfile
import urllib.request
from pathlib import Path

import numpy as np
from ase.io.espresso import units

from ycrystal.io.readers import StructureImportError, read_structure

SOURCE = "https://raw.githubusercontent.com/QEF/q-e/{ref}/test-suite/pw_lattice-ibrav/{name}"
CASES = (1, 2, 3, -3, 4, 5, -5, 6, 7, 8, 9, 10, 11, 12, -12, 13, 14)
"""The ``ibrav`` values with a test in QE's suite (it has none for -9, 91, and -13)."""

AXES_TOLERANCE = 2e-6  # alat; pw.x prints 6 decimals
POSITION_TOLERANCE = 2e-7  # alat; pw.x prints 7 decimals


def fetch(name: str, ref: str, folder: Path) -> Path:
    path = folder / name.replace("=", "_")
    if not path.exists():
        with urllib.request.urlopen(SOURCE.format(ref=ref, name=name), timeout=60) as response:
            path.write_bytes(response.read())
    return path


def compare(ibrav: int, ref: str, folder: Path) -> tuple[float, float]:
    """Return the largest axis and position differences in alat for one lattice."""
    name = f"lattice-ibrav{ibrav}.in"
    inp = fetch(name, ref, folder)
    out = fetch(f"benchmark.out.git.inp={name}", ref, folder).read_text()
    alat = float(re.search(r"lattice parameter \(alat\)\s*=\s*([\d.]+)", out).group(1))
    alat *= units["Bohr"]
    triple = r"\(\s*(\S+)\s+(\S+)\s+(\S+)\s*\)"
    axes = np.array(re.findall(r"a\(\d\) = " + triple, out), dtype=float)
    tau = np.array(re.findall(r"tau\(\s*\d+\) = " + triple, out), dtype=float)
    structure = read_structure(inp, fmt="qe")
    if structure.metadata["source"].get("qe_ibrav") != ibrav:
        raise SystemExit(f"{name}: expected ibrav = {ibrav}")
    return (
        float(np.abs(structure.cell / alat - axes).max()),
        float(np.abs(structure.positions / alat - tau[: len(structure)]).max()),
    )


def compare_checkout(checkout: Path) -> int:
    """Compare every applicable test-suite input of a QE checkout; return the failures."""
    triple = r"\(\s*(\S+)\s+(\S+)\s+(\S+)\s*\)"
    results: dict[int, list[tuple[str, float, float, float]]] = {}
    not_applicable: list[tuple[str, str]] = []
    suite = checkout / "test-suite"
    for inp in sorted(suite.rglob("*.in")):
        text = inp.read_text(errors="replace")
        found = re.search(r"\bibrav\s*=\s*(-?\d+)", text, re.I)
        if not found or int(found.group(1)) == 0 or not re.search(r"&system", text, re.I):
            continue
        name = str(inp.relative_to(suite))
        outputs = sorted(inp.parent.glob(f"benchmark.out.*inp={inp.name}*"))
        out = outputs[0].read_text(errors="replace") if outputs else ""
        if not re.search(r"a\(1\) = ", out):
            not_applicable.append((name, "no stored pw.x output"))
            continue
        if "unit cell read from directory" in out:
            not_applicable.append((name, "pw.x read the structure from an earlier run"))
            continue
        try:
            structure = read_structure(inp, fmt="qe")
        except StructureImportError as exc:
            not_applicable.append((name, f"not read: {str(exc).split(': ', 1)[-1][:70]}"))
            continue
        source = structure.metadata["source"]
        alat = source["qe_celldm"][0] * units["Bohr"]
        printed = float(re.search(r"celldm\(1\)=\s*([\d.]+)", out).group(1))
        a_error = abs(source["qe_celldm"][0] - printed) / printed
        axes = np.array(re.findall(r"a\(\d\) = " + triple, out)[:3], dtype=float)
        tau = np.array(re.findall(r"tau\(\s*\d+\) = " + triple, out), dtype=float)
        axes_error = float(np.abs(structure.cell / alat - axes).max())
        if "&energy_current" in text.lower():  # QEHeat: positions come from a trajectory
            positions_error = float("nan")
            not_applicable.append((name, "positions from a trajectory: axes compared only"))
        else:
            tau = tau[: len(structure)]
            positions_error = float(np.abs(structure.positions / alat - tau).max())
        results.setdefault(source["qe_ibrav"], []).append(
            (name, axes_error, positions_error, a_error)
        )
    failures = 0
    for ibrav in sorted(results, key=lambda v: (abs(v), v)):
        rows = results[ibrav]
        bad = [
            r
            for r in rows
            if r[1] > AXES_TOLERANCE
            or r[3] > 2e-7
            or (not np.isnan(r[2]) and r[2] > POSITION_TOLERANCE)
        ]
        failures += len(bad)
        worst_positions = (
            np.nanmax([r[2] for r in rows])
            if any(not np.isnan(r[2]) for r in rows)
            else float("nan")
        )
        print(
            f"ibrav {ibrav:4d}: {len(rows):3d} inputs; worst: axes {max(r[1] for r in rows):.1e}, "
            f"positions {worst_positions:.1e} alat, a {max(r[3] for r in rows):.1e} relative"
            f"{'' if not bad else f'  DIFFERENT: {[r[0] for r in bad]}'}"
        )
    total = sum(len(rows) for rows in results.values())
    print(f"{total - failures} of {total} inputs agree with pw.x's output.")
    print(f"Comparison not applicable ({len(not_applicable)}):")
    for name, why in not_applicable:
        print(f"  {name}: {why}")
    return failures


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--ref", default="develop", help="QE git branch or tag")
    parser.add_argument("--keep", type=Path, help="keep the downloaded files here")
    parser.add_argument(
        "--qe-checkout", type=Path, help="compare every test-suite input of a local QE copy"
    )
    args = parser.parse_args(argv)
    if args.qe_checkout:
        return 1 if compare_checkout(args.qe_checkout) else 0
    with tempfile.TemporaryDirectory() as tmp:
        folder = args.keep or Path(tmp)
        folder.mkdir(parents=True, exist_ok=True)
        failures = 0
        for ibrav in CASES:
            axes, positions = compare(ibrav, args.ref, folder)
            ok = axes <= AXES_TOLERANCE and positions <= POSITION_TOLERANCE
            failures += not ok
            print(
                f"ibrav {ibrav:4d}: axes {axes:.1e} alat, positions {positions:.1e} alat"
                f"  {'ok' if ok else 'DIFFERENT'}"
            )
    print(f"{len(CASES) - failures} of {len(CASES)} lattices agree with pw.x ({args.ref}).")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
