"""Renderer-independent display geometry.

[`build_geometry`][ycrystal.core.scene.build_geometry] combines a
[`Structure`][ycrystal.core.structure.Structure] with
[`SceneSettings`][ycrystal.core.scene.SceneSettings] into a
[`DisplayGeometry`][ycrystal.core.scene.DisplayGeometry]: the atoms that are drawn,
with positions, radii, and colours, plus the cell edges. The VTK viewport and the
POV-Ray writer both consume this one object, so neither backend decides on its own
which atoms are visible or where they are.

Every displayed atom has a stable identity, an [`AtomId`][ycrystal.core.scene.AtomId]
``(source_atom_index, image_offset)``. Selection and hiding refer to these IDs, never to
row numbers in the geometry arrays, because rows shift when atoms are hidden or the
boundary policy changes.
"""

from __future__ import annotations

import itertools
from collections import Counter
from dataclasses import dataclass, field

import numpy as np
from ase.data import chemical_symbols, covalent_radii
from ase.data.colors import jmol_colors

from ycrystal.core.structure import Structure

AtomId = tuple[int, tuple[int, int, int]]
"""Identity of one displayed atom: ``(source_atom_index, (na, nb, nc))``.

``source_atom_index`` is the 0-based index of the atom in the structure (input order).
``(na, nb, nc)`` is an integer periodic-image offset in units of the lattice vectors
a, b, and c. The atom is drawn at ``structure.positions[i] + (na, nb, nc) @ structure.cell``,
so an ID always denotes the same Cartesian position, whatever the display settings. The
offset is relative to the input position, not to a wrapped position: an atom given
outside the cell is displayed with a nonzero offset when boundary images are on.
"""

RGB = tuple[float, float, float]
"""A colour as ``(red, green, blue)`` sRGB components between 0 and 1."""


@dataclass(frozen=True)
class SceneSettings:
    """Display choices that do not modify the scientific structure.

    Every field is presentation state: changing it changes what is drawn and exported,
    never the coordinates of the [`Structure`][ycrystal.core.structure.Structure]. All
    fields are saved in projects. Instances are immutable; derive new settings with
    `dataclasses.replace`.

    Attributes
    ----------
    radius_scale
        Sphere radius as a multiple of the element's covalent radius (ASE's
        ``covalent_radii``, in Å).
    show_cell
        Whether to draw the 12 edges of the unit cell. Ignored for structures without a
        cell.
    cell_edge_radius
        Radius of the cell-edge cylinders and of the spheres at the cell corners, in Å.
    cell_edge_color
        Colour of the cell edges, as sRGB components between 0 and 1.
    boundary_images
        Boundary policy. If true, atoms are wrapped into the cell along periodic axes,
        and their periodic images on cell faces, edges, and corners are drawn too, as
        VESTA does: a corner atom appears at all eight corners. If false, every atom is
        drawn once at its input position with image offset ``(0, 0, 0)``.
    boundary_tolerance
        Tolerance in fractional coordinates for wrapping and for deciding that an atom
        lies on a cell face.
    hidden
        Displayed-atom IDs omitted from the view and from exported scenes. IDs that are
        not displayed under the current settings (for example boundary images while
        `boundary_images` is false) have no effect but are kept, so they apply again
        when the images reappear.
    """

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
    """Background colour and light intensities for exported scenes.

    Presentation state only. The POV-Ray writer places both lights relative to the
    camera, on the viewer's side of the scene: the key light at the upper left (it
    casts shadows) and the fill light at the lower right (shadowless). The live VTK view
    applies only `background` and keeps its own default lighting.

    Attributes
    ----------
    background
        Background colour as sRGB components between 0 and 1. Not used for renders
        with a transparent background.
    key_light
        Intensity of the key light (POV-Ray ``color rgb`` value); non-positive values
        omit the light.
    fill_light
        Intensity of the fill light; non-positive values omit the light.
    """

    background: RGB = (1.0, 1.0, 1.0)  # sRGB
    key_light: float = 1.0
    fill_light: float = 0.35


@dataclass(frozen=True, eq=False)
class DisplayGeometry:
    """Resolved geometry shared by the viewport and the POV-Ray writer.

    Contains only what is drawn. All arrays use Cartesian Å, and row ``i`` of each
    per-atom array describes the displayed atom ``atom_ids[i]``. Use
    [`index_of`][ycrystal.core.scene.DisplayGeometry.index_of] to find the row of an ID.

    Attributes
    ----------
    atom_ids
        Unique [`AtomId`][ycrystal.core.scene.AtomId] of each displayed atom, in
        drawing order.
    elements
        Element symbol of each displayed atom.
    positions
        Cartesian positions in Å, shape ``(M, 3)``.
    radii
        Sphere radii in Å, shape ``(M,)``.
    colors
        Sphere colours as sRGB components between 0 and 1, shape ``(M, 3)``.
    cell_edges
        Cell-edge segments in Å, shape ``(E, 2, 3)``: start and end point of each edge.
        ``E`` is 12, or 0 when no cell is drawn.
    cell_edge_radius
        Radius of the cell-edge cylinders in Å.
    cell_edge_color
        Colour of the cell edges as sRGB components between 0 and 1.
    hidden_count
        Number of atoms that the settings would display but that are hidden.

    Raises
    ------
    ValueError
        If `atom_ids` contains duplicates.

    Notes
    -----
    The constructor neither copies nor checks the arrays.
    [`build_geometry`][ycrystal.core.scene.build_geometry] creates consistent,
    read-only arrays; code that constructs a geometry directly (for example the renderer
    self-test) is responsible for matching lengths.
    """

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
        """Return the row of a displayed atom in the per-atom arrays.

        Parameters
        ----------
        atom_id
            Identity of the displayed atom.

        Returns
        -------
        int or None
            Row index, or ``None`` if the atom is not displayed (hidden, or not
            produced by the current boundary policy).
        """
        return self._index.get(atom_id)  # type: ignore[attr-defined]

    def __contains__(self, atom_id: object) -> bool:
        return atom_id in self._index  # type: ignore[attr-defined]

    def element_counts(self) -> Counter[str]:
        """Count the displayed atoms of each element.

        Returns
        -------
        collections.Counter
            Element symbol to number of displayed atoms; hidden atoms are not counted.
        """
        return Counter(self.elements)

    def points_and_radii(self) -> tuple[np.ndarray, np.ndarray]:
        """Return every drawn point with its radius.

        The points are the atom centres followed by both endpoints of every cell edge,
        so cell corners appear several times. Camera fitting and the POV-Ray eye
        placement use them to keep everything that is drawn in view.

        Returns
        -------
        points : numpy.ndarray
            Points in Å, shape ``(K, 3)``.
        radii : numpy.ndarray
            Radius of each point in Å, shape ``(K,)``; edge endpoints have
            `cell_edge_radius`.
        """
        points = [self.positions]
        radii = [self.radii]
        if len(self.cell_edges):
            ends = self.cell_edges.reshape(-1, 3)
            points.append(ends)
            radii.append(np.full(len(ends), self.cell_edge_radius))
        return np.concatenate(points), np.concatenate(radii)

    def bounding_sphere(self) -> tuple[np.ndarray, float]:
        """Return a sphere that encloses every drawn sphere and cell edge.

        The centre is the middle of the axis-aligned bounding box, so the sphere is
        enclosing but not necessarily minimal.

        Returns
        -------
        center : numpy.ndarray
            Centre in Å, shape ``(3,)``; the origin for an empty geometry.
        radius : float
            Radius in Å, at least 0.001; 1.0 for an empty geometry.
        """
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
    """Return the default colour of an element.

    Parameters
    ----------
    number
        Atomic number.

    Returns
    -------
    RGB
        ASE's Jmol colour for the element, as sRGB components between 0 and 1.
    """
    r, g, b = (float(c) for c in jmol_colors[number])
    return (r, g, b)


def displayed_atoms(
    structure: Structure, settings: SceneSettings
) -> list[tuple[AtomId, np.ndarray]]:
    """Return the displayed atom IDs and their positions before hiding.

    Parameters
    ----------
    structure
        Structure to display; it is not modified.
    settings
        Display settings; only `boundary_images` and `boundary_tolerance` are used.

    Returns
    -------
    list of tuple
        ``(atom_id, position)`` pairs, where ``position`` is a Cartesian position in Å,
        shape ``(3,)``, equal to the input position plus the image offset times the
        cell. Atoms are in input order and the images of one atom are consecutive.

    Notes
    -----
    Without boundary images, without a cell, or without any periodic axis, every atom
    is returned once with offset ``(0, 0, 0)``.

    Otherwise each periodic axis is treated separately, with the fractional coordinate
    ``f`` and tolerance ``tol``: the atom is shifted by ``-floor(f + tol)`` cells, which
    puts it in ``[-tol, 1 - tol)``. If the shifted coordinate is within ``tol`` of 0,
    the image on the opposite face (one more cell) is added. Non-periodic axes are
    neither wrapped nor imaged. The combinations over the three axes give 2 images for
    a face atom, 4 for an edge atom, and 8 for a corner atom.
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
    """Resolve the displayed atoms and cell edges of one unit cell.

    Parameters
    ----------
    structure
        Structure to display; it is read, never modified.
    settings
        Display settings; ``None`` uses the defaults of
        [`SceneSettings`][ycrystal.core.scene.SceneSettings].

    Returns
    -------
    DisplayGeometry
        A new geometry with read-only arrays. Displayed atoms come from
        [`displayed_atoms`][ycrystal.core.scene.displayed_atoms]; atoms in
        ``settings.hidden`` are omitted and counted in `hidden_count`.

    Notes
    -----
    Radii are ``settings.radius_scale`` times ASE's covalent radius, and colours are
    ASE's Jmol colours. Cell edges are drawn when ``settings.show_cell`` is true and the
    structure has a cell. Only one unit cell is displayed: supercell repetitions are not
    implemented yet.

    Examples
    --------
    A cubic perovskite has 5 atoms, but with boundary images the corner Sr appears
    8 times and each face-centred O twice:

    >>> from ycrystal.core.samples import perovskite_srtio3
    >>> from ycrystal.core.scene import SceneSettings, build_geometry
    >>> structure = perovskite_srtio3()
    >>> geometry = build_geometry(structure)
    >>> len(structure), len(geometry)
    (5, 15)
    >>> dict(geometry.element_counts())
    {'Sr': 8, 'Ti': 1, 'O': 6}

    Hiding one corner leaves the other seven, and the structure is unchanged:

    >>> corner = (0, (1, 1, 1))
    >>> hidden = build_geometry(structure, SceneSettings(hidden=frozenset({corner})))
    >>> len(hidden), hidden.hidden_count, hidden.index_of(corner)
    (14, 1, None)
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
