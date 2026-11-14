"""Read POSCAR/CONTCAR, CIF, and Quantum ESPRESSO pw.x input into a :class:`Structure`.

ASE does the parsing; this module adds format detection, provenance, and the checks
that keep Ycrystal from drawing something different from what the file means:

* VASP 4 files (no element line) need an explicit element mapping. ASE would guess
  elements from words in the free-text comment line, which can be silently wrong.
* CIF sites with partial occupancy, or distinct sites at the same position, are
  rejected instead of being drawn as an ordered structure.
* QE input is accepted only with ``ibrav = 0`` and a ``CELL_PARAMETERS`` card;
  ``crystal_sg`` positions are rejected. Species labels are kept separately from
  elements; labels that do not name an element unambiguously need a mapping.

Interactive questions are raised as exceptions (:class:`FormatChoiceRequired`,
:class:`BlockChoiceRequired`, :class:`ElementMappingRequired`) so that the GUI can
ask and call again with the answer.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import io
import re
import warnings
from pathlib import Path
from typing import Any

import ase
import numpy as np
from ase.data import atomic_numbers

from ycrystal.core.structure import Structure

FORMAT_NAMES: dict[str, str] = {
    "project": "Ycrystal project (.ycrystal)",
    "poscar": "VASP POSCAR/CONTCAR",
    "cif": "CIF",
    "qe": "Quantum ESPRESSO pw.x input",
}
STRUCTURE_FORMATS = ("poscar", "cif", "qe")

#: Shown in Help ▸ Supported File Formats and mirrored in docs/FORMATS.md.
SUPPORT_SUMMARY = """\
<b>VASP POSCAR/CONTCAR</b> (VASP 5 and 4): direct or Cartesian coordinates, one or
three scale factors, negative scale = cell volume, selective dynamics (kept as
movable flags). VASP 4 files have no element line, so Ycrystal asks for the elements.
<br><br>
<b>CIF</b>: symmetry expansion from the symmetry operations or space-group symbol,
any cell shape, choice of data block. <i>Not supported:</i> partially occupied or
mixed sites and distinct sites at the same position; such files are rejected rather
than drawn as an ordered structure.
<br><br>
<b>Quantum ESPRESSO pw.x input</b>: <code>ibrav = 0</code> with a
<code>CELL_PARAMETERS</code> card (alat, bohr, or angstrom), positions in alat, bohr,
angstrom, or crystal units, species labels such as Fe1 or Fe_up. <i>Not supported:</i>
<code>ibrav</code> other than 0 (lattice from <code>celldm</code> or
<code>A, B, C, cosAB…</code>) and <code>ATOMIC_POSITIONS crystal_sg</code>. Ycrystal
never runs pw.x and needs no pseudopotential files.
<br><br>
<b>Ycrystal project (.ycrystal)</b>: the structure, camera, and display settings in
one file; it does not need the original structure file.
"""


# ----- errors and questions ---------------------------------------------------------------
class StructureImportError(Exception):
    """A file could not be read; ``str(error)`` is a message for the user."""


class UnsupportedStructureError(StructureImportError):
    """The file is valid but uses a construct Ycrystal does not support."""


class FormatChoiceRequired(StructureImportError):
    def __init__(self, path: Path, candidates: list[str]) -> None:
        self.candidates = candidates or list(STRUCTURE_FORMATS)
        super().__init__(f"Cannot tell which format {path.name} is in.")


class BlockChoiceRequired(StructureImportError):
    def __init__(self, blocks: list[str]) -> None:
        self.blocks = blocks
        super().__init__(f"The CIF contains {len(blocks)} structures; choose a data block.")


class ElementMappingRequired(StructureImportError):
    """Element identities must be given for ``keys`` (species labels or species slots)."""

    def __init__(self, message: str, keys: list[str], suggestions: list[str | None],
                 details: list[str]) -> None:
        self.keys = keys
        self.suggestions = suggestions
        self.details = details
        super().__init__(message)


# ----- format detection ---------------------------------------------------------------------
def guess_format_from_name(path: Path) -> str | None:
    name = path.name.lower()
    suffix = path.suffix.lower()
    if suffix == ".ycrystal":
        return "project"
    if suffix in (".cif", ".mcif"):
        return "cif"
    if name.startswith(("poscar", "contcar")) or suffix in (".vasp", ".poscar", ".contcar"):
        return "poscar"
    if suffix in (".pwi", ".in") or name.endswith(("pw.in", "pwscf.in")):
        return "qe"
    return None


def formats_matching_content(text: str) -> list[str]:
    found = []
    head = text[:4000]
    if head.lstrip().startswith("{") and '"ycrystal-project"' in head:
        found.append("project")
    if re.search(r"^\s*data_\S*", text, re.M) and "_cell_length_a" in text:
        found.append("cif")
    if re.search(r"&system\b", text, re.I) and re.search(r"^\s*ATOMIC_POSITIONS", text,
                                                          re.M | re.I):
        found.append("qe")
    if _looks_like_poscar(text.splitlines()):
        found.append("poscar")
    return found


def detect_format(path: Path, text: str | None = None) -> str:
    """Format from the file name and content; raises :class:`FormatChoiceRequired`."""
    path = Path(path)
    if text is None:
        text = _read_text(path)
    by_name = guess_format_from_name(path)
    by_content = formats_matching_content(text)
    if by_name is not None and (by_name in by_content or not by_content):
        return by_name
    if len(by_content) == 1:
        return by_content[0]
    raise FormatChoiceRequired(path, by_content)


def _floats(tokens: list[str], count: int) -> bool:
    try:
        [float(t) for t in tokens[:count]]
    except ValueError:
        return False
    return len(tokens) >= count


def _looks_like_poscar(lines: list[str]) -> bool:
    if len(lines) < 8:
        return False
    scale = lines[1].split()
    if not (scale and (_floats(scale, 3) or _floats(scale, 1))):
        return False
    if not all(_floats(lines[i].split(), 3) for i in (2, 3, 4)):
        return False
    tokens = lines[5].split()
    if not tokens:
        return False
    if tokens[0].isdigit():
        return True
    following = lines[6].split()
    return bool(following) and following[0].isdigit()


# ----- entry point ------------------------------------------------------------------------
def read_structure(
    path: str | Path,
    fmt: str | None = None,
    *,
    block: str | None = None,
    element_map: dict[str, str] | None = None,
) -> Structure:
    """Read a structure file. ``fmt`` overrides detection ("poscar", "cif", "qe")."""
    path = Path(path)
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise StructureImportError(f"Cannot read {path}: {exc.strerror or exc}") from exc
    text = data.decode("utf-8", errors="replace")
    fmt = fmt or detect_format(path, text)
    if fmt == "project":
        raise StructureImportError(f"{path.name} is a Ycrystal project, not a structure file.")
    if fmt not in STRUCTURE_FORMATS:
        raise StructureImportError(f"Unknown format {fmt!r}.")
    reader = {"poscar": _read_poscar, "cif": _read_cif, "qe": _read_qe}[fmt]
    try:
        structure, extra = reader(text, path, block=block, element_map=element_map or {})
    except StructureImportError:
        raise
    except Exception as exc:  # parser errors from ASE or malformed numbers
        raise StructureImportError(
            f"{path.name} could not be read as {FORMAT_NAMES[fmt]}: {_describe(exc)}"
        ) from exc
    if len(structure) == 0:
        raise StructureImportError(f"{path.name} contains no atoms.")
    source = {
        "path": str(path.resolve()),
        "name": path.name,
        "format": fmt,
        "sha256": hashlib.sha256(data).hexdigest(),
        "size_bytes": len(data),
        "imported_at": _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"),
        "reader": f"ASE {ase.__version__}",
    }
    source.update(extra)
    if element_map:
        source["element_map"] = dict(element_map)
    return structure.replace(metadata={**structure.metadata, "source": source})


def _read_text(path: Path) -> str:
    try:
        return path.read_bytes().decode("utf-8", errors="replace")
    except OSError as exc:
        raise StructureImportError(f"Cannot read {path}: {exc.strerror or exc}") from exc


def _describe(exc: Exception) -> str:
    text = str(exc).strip() or type(exc).__name__
    if isinstance(exc, (IndexError, StopIteration)):
        return "the file ended early or a section is incomplete"
    return text


# ----- POSCAR / CONTCAR -------------------------------------------------------------------
def _read_poscar(text: str, path: Path, *, block: str | None,
                 element_map: dict[str, str]) -> tuple[Structure, dict[str, Any]]:
    from ase.io.vasp import read_vasp

    lines = text.splitlines()
    if not _looks_like_poscar(lines):
        raise StructureImportError(
            f"{path.name} is not a valid POSCAR: expected a comment line, a scale factor, "
            "three lattice vectors, and the atom counts."
        )
    extra: dict[str, Any] = {"comment": lines[0].strip()}
    count_tokens = lines[5].split()
    if count_tokens[0].isdigit():  # VASP 4: no element line
        counts = []
        for token in count_tokens:
            if not token.isdigit():
                break
            counts.append(int(token))
        keys = [f"species {i + 1}" for i in range(len(counts))]
        if not all(key in element_map for key in keys):
            raise ElementMappingRequired(
                f"{path.name} is a VASP 4 file without element names. Enter the element of "
                "each species in the order of the atom counts.",
                keys, _symbols_in_comment(lines[0], len(counts)),
                [f"{n} atom{'s' if n != 1 else ''}" for n in counts],
            )
        symbols = [_checked_symbol(element_map[key]) for key in keys]
        lines.insert(5, " ".join(symbols))
        extra["vasp_version"] = 4
    else:
        extra["vasp_version"] = 5
    selective = lines[7].strip()[:1].lower() == "s" if len(lines) > 7 else False
    try:
        n_atoms = sum(int(t) for t in lines[6].split() if t.isdigit())
    except ValueError:
        n_atoms = 0
    first = 9 if selective else 8
    coordinates = [ln for ln in lines[first:first + n_atoms] if _floats(ln.split(), 3)]
    if n_atoms == 0 or len(coordinates) < n_atoms:
        raise StructureImportError(
            f"{path.name}: the atom counts add up to {n_atoms} atoms, but only "
            f"{len(coordinates)} coordinate lines follow. The file may be truncated."
        )
    atoms = read_vasp(io.StringIO("\n".join(lines) + "\n"))
    movable = None
    if selective:
        fixed = np.zeros((len(atoms), 3), dtype=bool)
        for constraint in atoms.constraints:
            index = np.atleast_1d(constraint.index)
            mask = getattr(constraint, "mask", (True, True, True))
            fixed[index] |= np.asarray(mask, dtype=bool)
        movable = ~fixed
    structure = Structure(
        cell=atoms.cell.array, positions=atoms.positions, numbers=atoms.numbers,
        labels=tuple(atoms.get_chemical_symbols()), pbc=(True, True, True), movable=movable,
    )
    return structure, extra


def _symbols_in_comment(comment: str, count: int) -> list[str | None]:
    symbols = [word for word in re.split(r"[\s,;]+", comment) if word in atomic_numbers
               and word != "X"]
    if len(symbols) >= count:
        return list(symbols[:count])
    return [None] * count


def _checked_symbol(symbol: str) -> str:
    candidate = symbol.strip().capitalize()
    if candidate not in atomic_numbers or candidate == "X":
        raise StructureImportError(f"{symbol!r} is not a chemical element symbol.")
    return candidate


# ----- CIF --------------------------------------------------------------------------------
def _read_cif(text: str, path: Path, *, block: str | None,
              element_map: dict[str, str]) -> tuple[Structure, dict[str, Any]]:
    from ase.io.cif import parse_cif

    blocks = [b for b in parse_cif(io.StringIO(text)) if b.has_structure()]
    if not blocks:
        raise StructureImportError(
            f"{path.name} has no data block with a unit cell and atomic positions."
        )
    if block is None:
        if len(blocks) > 1:
            raise BlockChoiceRequired([b.name for b in blocks])
        chosen = blocks[0]
    else:
        matches = [b for b in blocks if b.name == block]
        if not matches:
            raise StructureImportError(f"{path.name} has no data block named {block!r}.")
        chosen = matches[0]
    if chosen.get_cellpar() is None:
        raise StructureImportError(f"Data block {chosen.name!r} has no complete unit cell.")

    symbols = chosen.get_symbols()
    site_labels = [str(v) for v in (chosen.get("_atom_site_label") or symbols)]
    occupancies = chosen.get("_atom_site_occupancy")
    site_occupancy = [1.0] * len(site_labels)
    if occupancies is not None:
        partial = []
        for i, (label, value) in enumerate(zip(site_labels, occupancies, strict=False)):
            if isinstance(value, (int, float)):
                site_occupancy[i] = float(value)
                if value < 1.0 - 1e-3:
                    partial.append(f"{label} ({value:g})")
        if partial:
            raise UnsupportedStructureError(
                f"{path.name} (block {chosen.name}) has partially occupied or mixed sites: "
                f"{', '.join(partial[:8])}{' …' if len(partial) > 8 else ''}. Ycrystal "
                "draws ordered structures only and will not show a disordered structure as "
                "if it were ordered. Use an ordered model (e.g. a supercell with explicit "
                "atoms) instead."
            )
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        atoms = chosen.get_atoms(fractional_occupancies=False)
    overlaps = []
    for warning in caught:
        match = re.search(r"scaled_positions (\d+) and (\d+) are equivalent", str(warning.message))
        if match:
            i, j = (int(g) for g in match.groups())
            overlaps.append(f"{site_labels[i]} / {site_labels[j]}")
    if overlaps:
        raise UnsupportedStructureError(
            f"{path.name} (block {chosen.name}) has distinct sites at the same position "
            f"({', '.join(overlaps[:8])}), which describes disorder. Ycrystal draws ordered "
            "structures only."
        )
    kinds = atoms.arrays.get("spacegroup_kinds")
    labels = [site_labels[k] for k in kinds] if kinds is not None else list(symbols)
    occupancy = [site_occupancy[k] for k in kinds] if kinds is not None else None
    structure = Structure(
        cell=atoms.cell.array, positions=atoms.positions, numbers=atoms.numbers,
        labels=tuple(labels), pbc=(True, True, True), occupancy=occupancy,
    )
    extra: dict[str, Any] = {"block": chosen.name}
    spacegroup = atoms.info.get("spacegroup")
    if spacegroup is not None:
        extra["spacegroup"] = {"number": int(spacegroup.no), "symbol": str(spacegroup.symbol)}
    return structure, extra


# ----- Quantum ESPRESSO pw.x input --------------------------------------------------------------
def element_from_label(label: str) -> str | None:
    """Element named unambiguously by a QE species label, else None.

    Accepted: an element symbol, optionally followed by a digit, '_', '-', '+' or '.'
    and anything (``Fe``, ``fe1``, ``Fe_up``, ``O-2``). ``Cb`` or ``Feup`` are ambiguous.
    """
    match = re.match(r"^([A-Za-z]+)(?:[0-9_\-+.].*)?$", label.strip())
    if not match:
        return None
    symbol = match.group(1).capitalize()
    if symbol in atomic_numbers and symbol != "X":
        return symbol
    return None


def _read_qe(text: str, path: Path, *, block: str | None,
             element_map: dict[str, str]) -> tuple[Structure, dict[str, Any]]:
    from ase.io.espresso import (
        get_atomic_positions,
        get_atomic_species,
        get_cell_parameters,
        read_fortran_namelist,
        units,
    )

    data, card_lines = read_fortran_namelist(io.StringIO(text))
    system = {str(k).lower(): v for k, v in data.get("system", {}).items()}
    if not system:
        raise StructureImportError(f"{path.name} has no &SYSTEM namelist.")
    for key in ("ibrav", "nat", "ntyp"):
        if key not in system:
            raise StructureImportError(f"{path.name}: &SYSTEM must set {key}.")
    ibrav = int(system["ibrav"])
    if ibrav != 0:
        raise UnsupportedStructureError(
            f"{path.name} uses ibrav = {ibrav}. Ycrystal reads Quantum ESPRESSO input only "
            "with ibrav = 0 and an explicit CELL_PARAMETERS card; it does not convert "
            "celldm(...) or A/B/C/cosAB lattice definitions. Rewrite the cell as ibrav = 0 "
            "with CELL_PARAMETERS."
        )
    if re.search(r"^\s*ATOMIC_POSITIONS\s*[({]?\s*crystal_sg", text, re.M | re.I):
        raise UnsupportedStructureError(
            f"{path.name} gives ATOMIC_POSITIONS in crystal_sg (symmetry-reduced) form, "
            "which Ycrystal does not support. Give all atoms with crystal, alat, bohr, or "
            "angstrom coordinates."
        )
    # Lattice parameter: celldm(1) in bohr takes precedence over A in angstrom (QE rule).
    # (ASE's own reader looks up 'A' in upper case and misses it; keys are lowercase.)
    if "celldm(1)" in system:
        alat = float(system["celldm(1)"]) * units["Bohr"]
    elif "a" in system:
        alat = float(system["a"])
    else:
        alat = None
    if re.search(r"^\s*CELL_PARAMETERS\s*[({]?\s*alat", text, re.M | re.I) and alat is None:
        raise StructureImportError(
            f"{path.name}: CELL_PARAMETERS in alat units needs celldm(1) or A in &SYSTEM."
        )
    cell, _ = get_cell_parameters(card_lines, alat=alat)
    if cell is None:
        raise StructureImportError(
            f"{path.name}: ibrav = 0 requires a CELL_PARAMETERS card, which is missing."
        )
    species = get_atomic_species(card_lines, n_species=int(system["ntyp"]))
    if species is None:
        raise StructureImportError(f"{path.name}: the ATOMIC_SPECIES card is missing.")
    species_labels = [entry[0] for entry in species]
    positions_card = get_atomic_positions(card_lines, n_atoms=int(system["nat"]), cell=cell,
                                          alat=alat)
    if positions_card is None:
        raise StructureImportError(f"{path.name}: the ATOMIC_POSITIONS card is missing.")
    labels = [entry[0] for entry in positions_card]
    unknown = sorted(set(labels) - set(species_labels))
    if unknown:
        raise StructureImportError(
            f"{path.name}: atoms use species {', '.join(unknown)} that are not listed in "
            "ATOMIC_SPECIES."
        )
    elements: dict[str, str] = {}
    unresolved = []
    for label in species_labels:
        if label in element_map:
            elements[label] = _checked_symbol(element_map[label])
        elif (symbol := element_from_label(label)) is not None:
            elements[label] = symbol
        else:
            unresolved.append(label)
    if unresolved:
        from ase.io.espresso import label_to_symbol

        suggestions: list[str | None] = []
        for label in unresolved:
            try:
                suggestions.append(label_to_symbol(label))
            except Exception:
                suggestions.append(None)
        raise ElementMappingRequired(
            f"{path.name}: the species label(s) {', '.join(unresolved)} do not name an "
            "element unambiguously. Enter the element for each label.",
            unresolved, suggestions,
            [f"{labels.count(label)} atoms" for label in unresolved],
        )
    flags = [entry[2] for entry in positions_card]
    movable = None
    if any(flag is not None for flag in flags):
        movable = [[bool(v) for v in flag] if flag is not None else [True] * 3 for flag in flags]
    structure = Structure(
        cell=cell,
        positions=np.array([entry[1] for entry in positions_card], dtype=float),
        numbers=[atomic_numbers[elements[label]] for label in labels],
        labels=tuple(labels),
        pbc=(True, True, True),
        movable=movable,
    )
    return structure, {"qe_species": {label: elements[label] for label in species_labels}}

