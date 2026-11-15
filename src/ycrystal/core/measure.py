"""Interatomic distances and bond angles between displayed atoms (FR-MEASURE-01).

Measurements use the exact displayed instances the user picked. Each instance is an
[`AtomId`][ycrystal.core.scene.AtomId] ``(source, (na, nb, nc))`` at
``structure.positions[source] + (na, nb, nc) @ structure.cell`` in Å, so the result
depends only on the structure: not on the camera, the projection, the drawn radii, or
the display settings, and no minimum-image convention is applied. Two periodic images of
the same source atom are different instances and may be measured against each other.

The functions are pure (no Qt or VTK).
[`MeasurementSession`][ycrystal.core.measure.MeasurementSession] holds the interaction
state: the mode, the atoms picked so far, and the completed results of this session
(they are not saved in projects).

Examples
--------
>>> import numpy as np
>>> from ycrystal.core.measure import bond_angle, distance
>>> b = np.zeros(3)
>>> round(distance(b, np.array([0.0, 3.0, 4.0])), 6)
5.0
>>> bond_angle(np.array([1.0, 0, 0]), b, np.array([0, 2.0, 0]))  # vertex b
90.0
>>> bond_angle(np.array([1.0, 0, 0]), b, np.array([-3.0, 0, 0]))
180.0
"""

from __future__ import annotations

from collections.abc import Container, Iterable, Sequence
from dataclasses import dataclass, field

import numpy as np

from ycrystal.core.scene import AtomId
from ycrystal.core.structure import Structure

KINDS: dict[str, int] = {"distance": 2, "angle": 3}
"""Measurement kinds and the number of atoms each needs (A, B for a distance; A, B, C
for an angle with B as the vertex)."""

LETTERS = "ABC"
"""Order labels of the picked atoms."""

ZERO_LENGTH = 1e-6
"""Shortest vector (Å) accepted as an angle arm; shorter arms make the angle undefined."""

DISTANCE_DECIMALS = 4
"""Decimal places shown for distances (display only; values keep full precision)."""

ANGLE_DECIMALS = 2
"""Decimal places shown for angles (display only; values keep full precision)."""


class MeasurementError(ValueError):
    """A pick or measurement that cannot be accepted; ``str()`` explains why."""


def atom_position(structure: Structure, atom_id: AtomId) -> np.ndarray:
    """Return the Cartesian position in Å of a displayed instance.

    Parameters
    ----------
    structure
        The scientific structure.
    atom_id
        ``(source index, (na, nb, nc))``.

    Returns
    -------
    numpy.ndarray
        ``structure.positions[source] + (na, nb, nc) @ structure.cell``.

    Raises
    ------
    MeasurementError
        If the source index does not exist, or a structure without a cell is given a
        nonzero image offset.
    """
    source, image = atom_id
    if not 0 <= int(source) < len(structure):
        raise MeasurementError(f"Atom #{int(source) + 1} does not exist in this structure.")
    offset = np.asarray(image, dtype=float)
    if not structure.has_cell:
        if np.any(offset != 0):
            raise MeasurementError("A structure without a cell has no periodic images.")
        return np.array(structure.positions[source], dtype=float)
    return np.asarray(structure.positions[source], dtype=float) + offset @ structure.cell


def distance(a: np.ndarray, b: np.ndarray) -> float:
    """Return the distance between two points (same unit as the input, here Å)."""
    return float(np.linalg.norm(np.asarray(b, dtype=float) - np.asarray(a, dtype=float)))


def bond_angle(a: np.ndarray, b: np.ndarray, c: np.ndarray) -> float:
    """Return the angle ∠ABC in degrees, with ``b`` as the vertex.

    Uses the arms ``a − b`` and ``c − b`` and ``atan2(|u × v|, u · v)``, which stays
    accurate near 0° and 180° (unlike ``arccos`` of a rounded cosine). Collinear arms
    give exactly 0° (same direction) or 180° (opposite directions).

    Raises
    ------
    MeasurementError
        If an arm is shorter than `ZERO_LENGTH` (the angle is undefined).
    """
    vertex = np.asarray(b, dtype=float)
    u = np.asarray(a, dtype=float) - vertex
    v = np.asarray(c, dtype=float) - vertex
    for name, arm in (("A", u), ("C", v)):
        if np.linalg.norm(arm) < ZERO_LENGTH:
            raise MeasurementError(
                f"Atom {name} is at the same position as the vertex B; the angle is undefined."
            )
    return float(np.degrees(np.arctan2(np.linalg.norm(np.cross(u, v)), float(u @ v))))


@dataclass(frozen=True)
class Measurement:
    """A completed measurement.

    Attributes
    ----------
    kind
        ``"distance"`` or ``"angle"``.
    atoms
        The picked instances in order: ``(A, B)`` or ``(A, B, C)``, B being the vertex
        of an angle.
    value
        Distance in Å or angle in degrees (0 to 180), at full precision.
    """

    kind: str
    atoms: tuple[AtomId, ...]
    value: float

    @property
    def unit(self) -> str:
        """``"Å"`` or ``"°"``."""
        return "Å" if self.kind == "distance" else "°"


def measure(structure: Structure, kind: str, atoms: Sequence[AtomId]) -> Measurement:
    """Measure a distance (A, B) or an angle (A, B, C; vertex B) between instances.

    Raises
    ------
    MeasurementError
        For a wrong number of atoms, an instance picked twice, a nonexistent atom, or a
        zero-length angle arm.
    ValueError
        For an unknown kind.
    """
    if kind not in KINDS:
        raise ValueError(f"unknown measurement kind {kind!r}")
    atoms = tuple((int(s), tuple(int(n) for n in image)) for s, image in atoms)
    if len(atoms) != KINDS[kind]:
        raise MeasurementError(f"A {kind} needs {KINDS[kind]} atoms, got {len(atoms)}.")
    if len(set(atoms)) != len(atoms):
        raise MeasurementError("The same displayed atom was selected twice.")
    points = [atom_position(structure, atom_id) for atom_id in atoms]
    value = distance(*points) if kind == "distance" else bond_angle(*points)
    return Measurement(kind, atoms, value)  # type: ignore[arg-type]


def atom_text(structure: Structure, atom_id: AtomId) -> str:
    """Return the identity of an instance, e.g. ``"Sr #1 [0 0 1]"``.

    Element (and the input label in parentheses if it differs, as in the status bar),
    the 1-based atom number, and the periodic image offset ``[na nb nc]`` relative to
    the input position (omitted for structures without a cell).
    """
    source, image = atom_id
    element, label = structure.symbols[source], structure.labels[source]
    name = element if label == element else f"{element} ({label})"
    text = f"{name} #{source + 1}"
    if structure.has_cell:
        text += " [" + " ".join(str(int(n)) for n in image) + "]"
    return text


def result_text(measurement: Measurement) -> str:
    """Return the value with its unit: ``"2.0134 Å"`` or ``"156.28° — vertex B"``."""
    if measurement.kind == "distance":
        return f"{measurement.value:.{DISTANCE_DECIMALS}f} Å"
    return f"{measurement.value:.{ANGLE_DECIMALS}f}° — vertex B"


def measurement_text(structure: Structure, measurement: Measurement) -> str:
    """Return a self-contained line for copying, with identities, unit, and vertex.

    Examples: ``"Distance A–B: 2.0134 Å (A = Sr #1 [0 0 0], B = O #3 [0 0 0])"`` and
    ``"Angle A–B–C: 156.28° — vertex B (A = …, B = …, C = …)"``.
    """
    letters = LETTERS[: len(measurement.atoms)]
    title = "Distance" if measurement.kind == "distance" else "Angle"
    atoms = ", ".join(
        f"{letter} = {atom_text(structure, atom_id)}"
        for letter, atom_id in zip(letters, measurement.atoms, strict=True)
    )
    return f"{title} {'–'.join(letters)}: {result_text(measurement)} ({atoms})"


def prompt(kind: str, picked: int) -> str:
    """Return the instruction for the next pick, e.g. ``"Select atom B — angle vertex"``."""
    letter = LETTERS[picked]
    if kind == "distance":
        return f"Distance: select atom {letter}" + (" (Esc cancels)" if picked else "")
    role = {0: "first end", 1: "angle vertex", 2: "second end"}[picked]
    return f"Bond angle: select atom {letter} — {role}" + (" (Esc cancels)" if picked else "")


@dataclass
class MeasurementSession:
    """Interaction state of the measurement modes (no Qt; session-only data).

    Attributes
    ----------
    structure
        Structure the picked identities refer to.
    mode
        ``"distance"``, ``"angle"``, or ``None`` (ordinary selection).
    pending
        Instances picked for the incomplete measurement, in order.
    results
        Completed measurements, oldest first.
    last
        The measurement just completed, whose guide stays visible until the next pick,
        Esc, or a mode change; ``None`` otherwise.
    """

    structure: Structure
    mode: str | None = None
    pending: list[AtomId] = field(default_factory=list)
    results: list[Measurement] = field(default_factory=list)
    last: Measurement | None = None

    def set_mode(self, mode: str | None) -> None:
        """Switch modes; an incomplete measurement and the last guide are dropped."""
        if mode is not None and mode not in KINDS:
            raise ValueError(f"unknown measurement kind {mode!r}")
        self.mode = mode
        self.pending = []
        self.last = None

    def prompt(self) -> str:
        """Return the instruction for the next pick ('' outside the measurement modes)."""
        return prompt(self.mode, len(self.pending)) if self.mode else ""

    def pick(self, atom_id: AtomId) -> Measurement | None:
        """Add a picked instance; return the measurement when it is complete.

        Raises
        ------
        MeasurementError
            If the instance is already part of this measurement, or it would make an
            angle arm zero-length; the atoms picked so far are kept.
        """
        if self.mode is None:
            raise MeasurementError("No measurement mode is active.")
        atom_id = (int(atom_id[0]), tuple(int(n) for n in atom_id[1]))
        if atom_id in self.pending:
            letter = LETTERS[self.pending.index(atom_id)]
            raise MeasurementError(
                f"That atom is already {letter} in this measurement; select a different "
                "atom (another periodic image of it is fine)."
            )
        position = atom_position(self.structure, atom_id)
        if self.mode == "angle" and len(self.pending) in (1, 2):
            other = self.pending[0] if len(self.pending) == 1 else self.pending[1]
            if distance(atom_position(self.structure, other), position) < ZERO_LENGTH:
                which = "A" if len(self.pending) == 1 else "the vertex B"
                raise MeasurementError(
                    f"This atom is at the same position as {which}; the angle would be "
                    "undefined. Select a different atom."
                )
        self.last = None
        self.pending.append(atom_id)  # type: ignore[arg-type]
        if len(self.pending) < KINDS[self.mode]:
            return None
        result = measure(self.structure, self.mode, self.pending)
        self.results.append(result)
        self.pending, self.last = [], result
        return result

    def cancel(self) -> bool:
        """Drop the incomplete measurement and the last guide; return whether any existed."""
        had = bool(self.pending) or self.last is not None
        self.pending, self.last = [], None
        return had

    def remove(self, rows: Iterable[int]) -> None:
        """Remove completed measurements by row index."""
        drop = set(rows)
        if self.last is not None and any(
            self.results[i] is self.last for i in drop if 0 <= i < len(self.results)
        ):
            self.last = None
        self.results = [m for i, m in enumerate(self.results) if i not in drop]

    def clear(self) -> None:
        """Remove every completed measurement (the mode stays)."""
        self.results, self.last = [], None

    def invalidate(self, structure: Structure, displayed: Container[AtomId]) -> tuple[int, bool]:
        """Drop what no longer refers to displayed instances of ``structure``.

        A different structure object clears everything. Otherwise completed
        measurements with an atom that is no longer displayed are removed and an
        incomplete measurement with such an atom is cancelled; the others stay valid,
        because an identity always denotes the same position in the same structure.

        Returns
        -------
        tuple
            ``(number of removed results, whether an incomplete measurement was
            cancelled)``.
        """
        if structure is not self.structure:
            removed, cancelled = len(self.results), bool(self.pending)
            self.structure = structure
            self.results, self.pending, self.last = [], [], None
            return removed, cancelled
        keep = [m for m in self.results if all(a in displayed for a in m.atoms)]
        removed = len(self.results) - len(keep)
        self.results = keep
        if self.last is not None and not any(m is self.last for m in keep):
            self.last = None
        cancelled = any(a not in displayed for a in self.pending)
        if cancelled:
            self.pending = []
        return removed, cancelled
