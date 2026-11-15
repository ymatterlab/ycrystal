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

from ycrystal.core.bonds import BondSettings, periodic_bonds
from ycrystal.core.structure import Structure

# A displayed atom: (source atom index, periodic image offset in units of a, b, c).
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
        Whether to draw cell edges in the chosen cell_mode. Ignored without a cell.
    cell_edge_radius
        Radius of the cell-edge cylinders and of the spheres at the cell corners, in Å.
    cell_edge_color
        Colour of the cell edges, as sRGB components between 0 and 1.
    boundary_images
        Boundary policy. If true, atoms are wrapped into the cell along periodic axes,
        and their periodic images on cell faces, edges, and corners are drawn too, as
        VESTA does: a corner atom appears at all eight corners. If false, every atom is
        drawn once per repeated cell at its input position plus the lattice translation.
    boundary_tolerance
        Tolerance in fractional coordinates for wrapping and for deciding that an atom
        lies on a cell face.
    repetitions
        Positive cell counts along a, b, c, recomputed from the original structure.
        Non-periodic axes are not repeated; without a cell all counts act as 1.
    cell_mode
        "all" draws grid lines, "outline" the repeated block outline, and "unit"
        the original cell. show_cell can disable all edges.
    bonds
        BondSettings controlling candidate distances, enabled pairs, and radius.
    material
        Id of the material preset applied to every atom and bond (see
        [`ycrystal.presets`][ycrystal.presets]); ``"satin"`` is Ycrystal's original
        finish. Resolved by the renderers, which reject unknown ids.
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
    material: str = "satin"

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
    """Background and light intensities for the live view and exported scenes.

    Presentation state only. The POV-Ray writer places both lights relative to the
    camera, on the viewer's side of the scene: the key light at the upper left (it
    casts shadows) and the fill light at the lower right (shadowless). The live VTK view
    applies only `background` and keeps its own default lighting.

    Attributes
    ----------
    background
        Background colour as sRGB components between 0 and 1. With `transparent`, it
        is shown only in the live view.
    transparent
        Whether rendered PNGs get an alpha channel with a fully transparent background.
    preset
        Id of the environment preset this environment was made from (see
        [`ycrystal.presets`][ycrystal.presets]); saved in projects.
    key_light
        Intensity of the key light (POV-Ray ``color rgb`` value); non-positive values
        omit the light.
    fill_light
        Intensity of the fill light; non-positive values omit the light.
    """

    background: RGB = (1.0, 1.0, 1.0)  # sRGB
    key_light: float = 1.0
    fill_light: float = 0.35
    transparent: bool = False
    preset: str = "white"


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
        ``E`` depends on repetitions and cell mode; 0 when no cell is drawn.
    cell_edge_radius
        Radius of the cell-edge cylinders in Å.
    cell_edge_color
        Colour of the cell edges as sRGB components between 0 and 1.
    bonds
        Displayed-atom row index pairs, shape (B, 2). Both endpoints must be shown.
    bond_radius
        Cylinder radius in Å; each bond is split and coloured by its endpoints.
    material
        Material preset id for atoms and bonds (from `SceneSettings.material`).
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
    bonds: np.ndarray = field(default_factory=lambda: np.zeros((0, 2), dtype=int))  # (B, 2)
    bond_radius: float = 0.12  # Å
    material: str = "satin"

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
    """Count displayable atoms before hiding without allocating geometry.

    Uses repetitions and the boundary policy; ignores hidden IDs and bond settings.
    Useful for warning before large expansions.
    """
    _, counts = _axis_images(structure, settings)
    return int(np.prod(counts, axis=1).sum()) if len(counts) else 0


def displayed_atoms(
    structure: Structure, settings: SceneSettings
) -> list[tuple[AtomId, np.ndarray]]:
    """Return the displayed atom IDs and their positions before hiding.

    Parameters
    ----------
    structure
        Structure to display; it is not modified.
    settings
        Display repetitions, boundary policy, and fractional tolerance; hiding is ignored.

    Returns
    -------
    list of tuple
        ``(atom_id, position)`` pairs, where ``position`` is a Cartesian position in Å,
        shape ``(3,)``, equal to the input position plus the image offset times the
        cell. Atoms are in input order and the images of one atom are consecutive.

    Notes
    -----
    Without boundary images, input positions are repeated by lattice translations.
    Non-periodic axes are never repeated; structures without a cell appear once.

    Otherwise each periodic axis is treated separately, with the fractional coordinate
    ``f`` and tolerance ``tol``: the atom is shifted by ``-floor(f + tol)`` cells, which
    puts it in ``[-tol, 1 - tol)``. If the shifted coordinate is within ``tol`` of 0,
    one extra image is added at the far face of the repeated block. Each axis normally
    produces repetitions[axis] images. IDs remain relative to input coordinates,
    independent of wrapping or repetition changes.
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
    """Return Cartesian cell-edge segments in Å, shape (E, 2, 3).

    Uses effective periodic repetitions and cell_mode (all, outline, unit).
    Returns an empty array when show_cell is false or the structure has no cell.
    The array is newly computed or derived from the fractional edge template;
    build_geometry makes its resolved arrays read-only.
    """
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
    """Resolve displayed atoms, periodic bonds, and cell edges for a repeated block.

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
    structure has a cell. Repetitions are display state: scientific arrays stay unchanged.
    A bond is drawn only when both endpoint IDs are displayed and its pair is enabled.

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
        material=settings.material,
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
