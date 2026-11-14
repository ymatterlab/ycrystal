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
    # When False, every atom is drawn once at its input position.
    boundary_images: bool = True
    boundary_tolerance: float = 1e-3  # fractional
    # Displayed atoms removed from the view and from exports (presentation only).
    hidden: frozenset[AtomId] = field(default_factory=frozenset)


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


def displayed_atoms(
    structure: Structure, settings: SceneSettings
) -> list[tuple[AtomId, np.ndarray]]:
    """Displayed atom IDs and Cartesian positions before hiding.

    An image offset n means: displayed position = input position + n @ cell. IDs are
    therefore stable across display changes and independent of wrapping.
    """
    n_atoms = len(structure)
    if not (settings.boundary_images and structure.has_cell and any(structure.pbc)):
        return [((i, (0, 0, 0)), structure.positions[i]) for i in range(n_atoms)]
    cell = structure.cell
    frac = structure.positions @ np.linalg.inv(cell)
    tol = settings.boundary_tolerance
    result: list[tuple[AtomId, np.ndarray]] = []
    for i in range(n_atoms):
        choices: list[tuple[int, ...]] = []
        for axis in range(3):
            if not structure.pbc[axis]:
                choices.append((0,))
                continue
            # Wrap into [-tol, 1 - tol); values within tol of 1 become ~0.
            shift = -int(np.floor(frac[i, axis] + tol))
            wrapped = frac[i, axis] + shift
            # On a face (wrapped ~ 0): also draw the image on the opposite face.
            choices.append((shift, shift + 1) if abs(wrapped) < tol else (shift,))
        for image in itertools.product(*choices):
            offset = np.asarray(image, dtype=float) @ cell
            atom_id: AtomId = (i, (int(image[0]), int(image[1]), int(image[2])))
            result.append((atom_id, structure.positions[i] + offset))
    return result


def build_geometry(structure: Structure, settings: SceneSettings | None = None) -> DisplayGeometry:
    """Resolve the displayed atoms and cell edges for one unit cell.

    With ``settings.boundary_images`` (default) atoms are wrapped into the cell and
    their images on faces, edges, and corners are added, so e.g. a corner atom appears
    at all eight corners. Atoms in ``settings.hidden`` are omitted. Repetitions
    (supercells) arrive later.
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
    if settings.show_cell and structure.has_cell:
        edges = _CELL_EDGES_FRAC @ structure.cell
    else:
        edges = np.zeros((0, 2, 3))
    for array in (positions, radii, colors, edges):
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
    )
