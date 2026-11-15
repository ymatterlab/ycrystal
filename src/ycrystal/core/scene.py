"""Renderer-independent display geometry.

Both the VTK viewport and the POV-Ray writer consume the same
:class:`DisplayGeometry`; neither backend decides on its own which atoms are
visible or where cell edges are.
"""

from __future__ import annotations

import itertools
from collections import Counter
from dataclasses import dataclass, field

import numpy as np
from ase.data import chemical_symbols, covalent_radii
from ase.data.colors import jmol_colors

from ycrystal.core.bonds import BondSettings, periodic_bonds
from ycrystal.core.structure import Structure

# A displayed atom: (source atom index, periodic image offset in units of a, b, c).
AtomId = tuple[int, tuple[int, int, int]]

RGB = tuple[float, float, float]


@dataclass(frozen=True)
class SceneSettings:
    """Display choices that do not modify the scientific structure."""

    radius_scale: float = 0.5  # sphere radius = radius_scale * covalent radius
    show_cell: bool = True
    cell_edge_radius: float = 0.035  # Å
    cell_edge_color: RGB = (0.15, 0.15, 0.15)  # sRGB
    # Boundary policy: wrap atoms into the cell along periodic axes and also draw the
    # periodic images lying on cell faces, edges, and corners (as VESTA/XCrySDen do).
    # When False, every atom is drawn once per repeated cell at its input position.
    boundary_images: bool = True
    boundary_tolerance: float = 1e-3  # fractional
    # Displayed atoms removed from the view and from exports (presentation only).
    hidden: frozenset[AtomId] = field(default_factory=frozenset)
    # Display repetitions along a, b, c (always recomputed from the original structure).
    repetitions: tuple[int, int, int] = (1, 1, 1)
    # Cell edges: "all" unit cells of the repeated block, its "outline", or the original
    # "unit" cell only. ``show_cell`` switches them off entirely.
    cell_mode: str = "all"
    bonds: BondSettings = field(default_factory=BondSettings)

    def __post_init__(self) -> None:
        reps = tuple(int(r) for r in self.repetitions)
        if len(reps) != 3 or min(reps) < 1:
            raise ValueError("repetitions must be three integers >= 1")
        object.__setattr__(self, "repetitions", reps)
        if self.cell_mode not in CELL_MODES:
            raise ValueError(f"cell_mode must be one of {CELL_MODES}")


CELL_MODES = ("all", "outline", "unit")


@dataclass(frozen=True)
class Environment:
    """Background and lighting. Lights are defined relative to the camera."""

    background: RGB = (1.0, 1.0, 1.0)  # sRGB
    key_light: float = 1.0
    fill_light: float = 0.35


@dataclass(frozen=True, eq=False)
class DisplayGeometry:
    atom_ids: tuple[AtomId, ...]
    elements: tuple[str, ...]
    positions: np.ndarray  # (M, 3) Å
    radii: np.ndarray  # (M,) Å
    colors: np.ndarray  # (M, 3) sRGB in [0, 1]
    cell_edges: np.ndarray  # (E, 2, 3) Å
    cell_edge_radius: float
    cell_edge_color: RGB
    hidden_count: int = 0  # displayable atoms omitted because they are hidden
    bonds: np.ndarray = field(default_factory=lambda: np.zeros((0, 2), dtype=int))  # (B, 2)
    bond_radius: float = 0.12  # Å

    def __post_init__(self) -> None:
        index = {atom_id: i for i, atom_id in enumerate(self.atom_ids)}
        if len(index) != len(self.atom_ids):
            raise ValueError("displayed atom IDs must be unique")
        object.__setattr__(self, "_index", index)

    def __len__(self) -> int:
        return len(self.atom_ids)

    def index_of(self, atom_id: AtomId) -> int | None:
        """Position of a displayed atom in the arrays, or None if it is not shown."""
        return self._index.get(atom_id)  # type: ignore[attr-defined]

    def __contains__(self, atom_id: object) -> bool:
        return atom_id in self._index  # type: ignore[attr-defined]

    def element_counts(self) -> Counter[str]:
        return Counter(self.elements)

    def points_and_radii(self) -> tuple[np.ndarray, np.ndarray]:
        """All drawn points with their radii (atoms and cell-edge endpoints)."""
        points = [self.positions]
        radii = [self.radii]
        if len(self.cell_edges):
            ends = self.cell_edges.reshape(-1, 3)
            points.append(ends)
            radii.append(np.full(len(ends), self.cell_edge_radius))
        return np.concatenate(points), np.concatenate(radii)

    def bounding_sphere(self) -> tuple[np.ndarray, float]:
        points, radii = self.points_and_radii()
        if len(points) == 0:
            return np.zeros(3), 1.0
        lo = (points - radii[:, None]).min(axis=0)
        hi = (points + radii[:, None]).max(axis=0)
        center = 0.5 * (lo + hi)
        radius = float(np.max(np.linalg.norm(points - center, axis=1) + radii))
        return center, max(radius, 1e-3)


# Edges of the unit cell as pairs of fractional corners.
_CELL_EDGES_FRAC = np.array(
    [
        [(0, 0, 0), (1, 0, 0)],
        [(0, 1, 0), (1, 1, 0)],
        [(0, 0, 1), (1, 0, 1)],
        [(0, 1, 1), (1, 1, 1)],
        [(0, 0, 0), (0, 1, 0)],
        [(1, 0, 0), (1, 1, 0)],
        [(0, 0, 1), (0, 1, 1)],
        [(1, 0, 1), (1, 1, 1)],
        [(0, 0, 0), (0, 0, 1)],
        [(1, 0, 0), (1, 0, 1)],
        [(0, 1, 0), (0, 1, 1)],
        [(1, 1, 0), (1, 1, 1)],
    ],
    dtype=float,
)


def element_color(number: int) -> RGB:
    r, g, b = (float(c) for c in jmol_colors[number])
    return (r, g, b)


def _axis_images(structure: Structure, settings: SceneSettings) -> tuple[np.ndarray, list]:
    """Per atom and axis: the base image shift and how many images are drawn."""
    n_atoms = len(structure)
    reps = _effective_repetitions(structure, settings)
    wrap = settings.boundary_images and structure.has_cell and any(structure.pbc)
    base = np.zeros((n_atoms, 3), dtype=int)
    counts = np.tile(np.asarray(reps), (n_atoms, 1))
    if wrap:
        frac = structure.positions @ np.linalg.inv(structure.cell)
        tol = settings.boundary_tolerance
        for axis in range(3):
            if not structure.pbc[axis]:
                continue
            # Wrap into [-tol, 1 - tol); values within tol of 1 become ~0.
            shift = -np.floor(frac[:, axis] + tol).astype(int)
            wrapped = frac[:, axis] + shift
            base[:, axis] = shift
            # On a face (wrapped ~ 0): also draw the image on the far face of the block.
            counts[:, axis] += (np.abs(wrapped) < tol).astype(int)
    return base, counts


def _effective_repetitions(structure: Structure, settings: SceneSettings) -> tuple[int, ...]:
    if not structure.has_cell:
        return (1, 1, 1)
    return tuple(
        r if periodic else 1
        for r, periodic in zip(settings.repetitions, structure.pbc, strict=True)
    )


def count_displayed_atoms(structure: Structure, settings: SceneSettings) -> int:
    """Number of atoms the settings would display before hiding (cheap; no geometry)."""
    _, counts = _axis_images(structure, settings)
    return int(np.prod(counts, axis=1).sum()) if len(counts) else 0


def displayed_atoms(
    structure: Structure, settings: SceneSettings
) -> list[tuple[AtomId, np.ndarray]]:
    """Displayed atom IDs and Cartesian positions before hiding.

    An image offset n means: displayed position = input position + n @ cell. IDs are
    therefore stable across display changes (boundary policy, repetitions) and
    independent of wrapping. Repetitions are recomputed from the original structure.
    """
    base, counts = _axis_images(structure, settings)
    cell = structure.cell
    result: list[tuple[AtomId, np.ndarray]] = []
    for i in range(len(structure)):
        ranges = [range(base[i, a], base[i, a] + counts[i, a]) for a in range(3)]
        for image in itertools.product(*ranges):
            atom_id: AtomId = (i, (int(image[0]), int(image[1]), int(image[2])))
            result.append((atom_id, structure.positions[i] + np.asarray(image, float) @ cell))
    return result


def cell_edge_segments(structure: Structure, settings: SceneSettings) -> np.ndarray:
    """Cell edges as (E, 2, 3) segments for the chosen ``cell_mode``."""
    if not (settings.show_cell and structure.has_cell):
        return np.zeros((0, 2, 3))
    reps = np.asarray(_effective_repetitions(structure, settings), dtype=float)
    if settings.cell_mode == "unit" or (settings.cell_mode == "all" and np.all(reps == 1)):
        frac = _CELL_EDGES_FRAC
    elif settings.cell_mode == "outline":
        frac = _CELL_EDGES_FRAC * reps
    else:  # "all": every grid line of the repeated block, one segment per line
        segments = []
        for axis in range(3):
            others = [a for a in range(3) if a != axis]
            for u in range(int(reps[others[0]]) + 1):
                for v in range(int(reps[others[1]]) + 1):
                    start = np.zeros(3)
                    start[others[0]], start[others[1]] = u, v
                    end = start.copy()
                    end[axis] = reps[axis]
                    segments.append((start, end))
        frac = np.array(segments, dtype=float)
    return frac @ structure.cell


def build_geometry(structure: Structure, settings: SceneSettings | None = None) -> DisplayGeometry:
    """Resolve the displayed atoms, bonds, and cell edges.

    Atoms are generated for ``settings.repetitions`` cells from the original structure.
    With ``settings.boundary_images`` (default) they are wrapped into the cell and the
    images on the faces, edges, and corners of the repeated block are added, so e.g. a
    corner atom appears at every corner. Atoms in ``settings.hidden`` are omitted. A
    bond is drawn when both of its atoms are displayed.
    """
    settings = settings or SceneSettings()
    candidates = displayed_atoms(structure, settings)
    shown = [(atom_id, pos) for atom_id, pos in candidates if atom_id not in settings.hidden]
    atom_ids: tuple[AtomId, ...] = tuple(atom_id for atom_id, _ in shown)
    sources = np.array([atom_id[0] for atom_id in atom_ids], dtype=int)
    numbers = structure.numbers[sources] if len(sources) else np.zeros(0, dtype=int)
    positions = np.array([pos for _, pos in shown], dtype=float).reshape(-1, 3)
    radii = settings.radius_scale * covalent_radii[numbers]
    colors = np.array([element_color(z) for z in numbers], dtype=float).reshape(-1, 3)
    edges = cell_edge_segments(structure, settings)
    bonds = _displayed_bonds(structure, settings, atom_ids)
    for array in (positions, radii, colors, edges, bonds):
        array.setflags(write=False)
    return DisplayGeometry(
        atom_ids=atom_ids,
        elements=tuple(chemical_symbols[z] for z in numbers),
        positions=positions,
        radii=radii,
        colors=colors,
        cell_edges=edges,
        cell_edge_radius=settings.cell_edge_radius,
        cell_edge_color=settings.cell_edge_color,
        hidden_count=len(candidates) - len(shown),
        bonds=bonds,
        bond_radius=settings.bonds.radius,
    )


def _displayed_bonds(
    structure: Structure, settings: SceneSettings, atom_ids: tuple[AtomId, ...]
) -> np.ndarray:
    """Index pairs of displayed atoms joined by an enabled periodic bond."""
    if not settings.bonds.enabled or not atom_ids:
        return np.zeros((0, 2), dtype=int)
    periodic = periodic_bonds(structure, settings.bonds)
    by_source: dict[int, list[tuple[int, tuple[int, int, int]]]] = {}
    for i, j, shift, on in zip(
        periodic.i, periodic.j, periodic.shifts, periodic.enabled, strict=True
    ):
        if on:
            by_source.setdefault(int(i), []).append((int(j), tuple(int(v) for v in shift)))
    index = {atom_id: k for k, atom_id in enumerate(atom_ids)}
    pairs = []
    for k, (source, image) in enumerate(atom_ids):
        for partner, shift in by_source.get(source, ()):
            other = (partner, (image[0] + shift[0], image[1] + shift[1], image[2] + shift[2]))
            q = index.get(other)
            if q is not None:
                pairs.append((k, q))
    return np.array(pairs, dtype=int).reshape(-1, 2)
