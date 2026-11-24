"""Coordination polyhedra resolved from periodic ligand positions."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from itertools import combinations
from typing import TYPE_CHECKING

import numpy as np
from ase.data import atomic_numbers

from ycrystal.core.bonds import MIN_BOND_LENGTH

if TYPE_CHECKING:
    from ycrystal.core.scene import RGB, AtomId
    from ycrystal.core.structure import Structure

EDGE_RADIUS = 0.022  # Å


@dataclass(frozen=True)
class PolyhedronRule:
    """Choose a centre element, a ligand element, a cutoff in Å, and a surface style."""

    centre: str
    ligand: str
    cutoff: float = 2.5
    color: RGB = (0.29, 0.76, 0.94)
    opacity: float = 0.45
    show_edges: bool = True
    enabled: bool = True

    def __post_init__(self) -> None:
        if self.centre not in atomic_numbers or self.ligand not in atomic_numbers:
            raise ValueError("polyhedra need valid centre and ligand elements")
        if not MIN_BOND_LENGTH < self.cutoff <= 20.0:
            raise ValueError("polyhedron cutoff must be above 0.1 Å and at most 20 Å")
        color = tuple(float(component) for component in self.color)
        if len(color) != 3 or not all(0.0 <= component <= 1.0 for component in color):
            raise ValueError("polyhedron colour components must be between 0 and 1")
        if not 0.0 < self.opacity <= 1.0:
            raise ValueError("polyhedron opacity must be above 0 and at most 1")
        object.__setattr__(self, "color", color)

    @property
    def edge_color(self) -> RGB:
        """Return a lighter shade of the face colour for the edges."""
        return tuple(channel + 0.34 * (1.0 - channel) for channel in self.color)


@dataclass(frozen=True)
class Polyhedron:
    """An outward-wound triangle mesh indexed into the displayed atom positions."""

    centre: int
    rule: PolyhedronRule
    triangles: tuple[tuple[int, int, int], ...]
    edges: tuple[tuple[int, int], ...]


def _hull(points: np.ndarray) -> tuple[list[tuple[int, int, int]], list[tuple[int, int]]]:
    """Triangulate a shell and keep the edges where the faces change planes."""
    from scipy.spatial import ConvexHull, QhullError

    if len(points) < 4:
        return [], []
    try:
        hull = ConvexHull(points)
    except QhullError:  # e.g. a coplanar coordination environment
        return [], []
    triangles = []
    normals: dict[tuple[int, int], list[np.ndarray]] = defaultdict(list)
    for simplex, equation in zip(hull.simplices, hull.equations, strict=True):
        a, b, c = (int(index) for index in simplex)
        normal = equation[:3]
        if np.dot(np.cross(points[b] - points[a], points[c] - points[a]), normal) < 0:
            b, c = c, b
        triangles.append((a, b, c))
        for i, j in combinations(sorted((a, b, c)), 2):
            normals[i, j].append(normal)
    edges = [
        edge
        for edge, (first, second) in normals.items()
        if not np.allclose(first, second, rtol=0.0, atol=1e-7)
    ]
    return sorted(triangles), sorted(edges)


def resolve_polyhedra(
    structure: Structure, atom_ids: tuple[AtomId, ...], rules: tuple[PolyhedronRule, ...]
) -> tuple[Polyhedron, ...]:
    """Build one hull per coordination shell in the original cell and repeat its topology.

    Ligands come from an absolute distance cutoff, independent of display bonds.
    Draw a shell when its centre and all of its hull vertices are displayed.
    """
    from ase.neighborlist import neighbor_list

    symbols = structure.symbols
    by_elements = {
        (rule.centre, rule.ligand): rule
        for rule in rules
        if rule.enabled and rule.centre in symbols and rule.ligand in symbols
    }
    if not by_elements or not atom_ids:
        return ()

    atoms = structure.to_ase()
    if not structure.has_cell:
        atoms.pbc = False
    cutoff = max(rule.cutoff for rule in by_elements.values())
    i, j, shifts, lengths = neighbor_list("ijSd", atoms, np.nextafter(cutoff, np.inf))
    neighbours: dict[tuple[int, PolyhedronRule], list[AtomId]] = defaultdict(list)
    for a, b, shift, length in zip(i, j, shifts, lengths, strict=True):
        rule = by_elements.get((symbols[a], symbols[b]))
        if rule is not None and MIN_BOND_LENGTH <= length <= rule.cutoff:
            neighbours[int(a), rule].append((int(b), tuple(int(value) for value in shift)))

    by_source = defaultdict(list)
    for (source, rule), neighbours_for_rule in neighbours.items():
        ligands = sorted(set(neighbours_for_rule))
        positions = np.array(
            [
                structure.positions[b]
                - structure.positions[source]
                + np.asarray(shift) @ structure.cell
                for b, shift in ligands
            ]
        )
        triangles, edges = _hull(positions)
        if triangles:
            vertices = sorted({vertex for face in triangles for vertex in face})
            by_source[source].append((rule, ligands, vertices, triangles, edges))

    index = {atom: row for row, atom in enumerate(atom_ids)}
    result = []
    for row, (source, image) in enumerate(atom_ids):
        for rule, ligands, vertices, triangles, edges in by_source.get(source, ()):
            vertex_rows = {}
            for vertex in vertices:
                b, shift = ligands[vertex]
                ligand = (b, tuple(a + s for a, s in zip(image, shift, strict=True)))
                if ligand not in index:
                    break
                vertex_rows[vertex] = index[ligand]
            else:
                result.append(
                    Polyhedron(
                        row,
                        rule,
                        tuple(
                            (vertex_rows[a], vertex_rows[b], vertex_rows[c])
                            for a, b, c in triangles
                        ),
                        tuple((vertex_rows[a], vertex_rows[b]) for a, b in edges)
                        if rule.show_edges
                        else (),
                    )
                )
    return tuple(result)
