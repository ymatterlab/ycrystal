"""FR-VALIDATION-01: evidence for Ycrystal's scientific claims.

Each test answers part of a question of ``docs/development/validation.md``, where the
tolerances are justified and the results recorded:

A. Does the POV-Ray scene, and the ray-traced image, show the structure where it is:
   atoms and periodic images, bonds, cell edges, vectors, camera projection and
   handedness, nothing clipped?
B. Does applying a style (with or without an element mapping) leave the scientific
   data unchanged?
E. Are the ray-traced effects real: cast shadows, soft shadows of area lights,
   reflections in polished metal, transmission through glass?

Questions C (snapshot replay) and D (render time) are covered by
``tests/test_reproducibility.py`` and ``tests/test_validation_scripts.py``.

Images are checked by measured properties (sphere centroids, disc areas, sampled
colours, colour excess in regions), never by comparison with stored pixels.
"""

import hashlib
import itertools
import re
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from ycrystal.batch import CLI_STYLE_PARTS, apply_style_file, load_input, scene_for
from ycrystal.core.bonds import BondSettings
from ycrystal.core.camera import Camera, ViewPolicy, axis_view
from ycrystal.core.scene import (
    DisplayGeometry,
    Environment,
    SceneSettings,
    build_geometry,
    count_displayed_atoms,
)
from ycrystal.io.project import Project
from ycrystal.io.style import STYLE_PARTS
from ycrystal.presets import environment_from_preset
from ycrystal.render.imagecheck import find_blobs, load_rgba, match_spheres
from ycrystal.render.jobs import prepare_job, run_job
from ycrystal.render.pov_writer import RenderSettings, scene_to_pov

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"
STYLE = ROOT / "examples" / "grey-studio.ycstyle"
AFM = ROOT / "examples" / "vectors-synthetic-afm.ycrystal"  # synthetic, not a real material

# Structures and repetitions used throughout: cubic (with boundary images), hexagonal,
# triclinic (synthetic P1), and the second perovskite used for element mapping.
CASES = {
    "SrTiO3": ("SrTiO3.cif", (1, 1, 1)),
    "SrTiO3-2x2x1": ("SrTiO3.cif", (2, 2, 1)),
    "MgB2-2x2x1": ("MgB2.cif", (2, 2, 1)),
    "triclinic-2x1x1": ("triclinic.cif", (2, 1, 1)),
    "BaZrO3": ("BaZrO3.cif", (1, 1, 1)),
}

# Distinct colours per element, so that each sphere found in an image can be identified.
COLORS = [(0.9, 0.1, 0.1), (0.1, 0.8, 0.1), (0.1, 0.2, 0.9), (0.85, 0.15, 0.6), (0.1, 0.7, 0.7)]

# Tolerances; docs/development/validation.md gives the reasons and the observed values.
WRITER_TOLERANCE = 5e-7  # Å: the scene file has 6 decimals
CENTROID_TOLERANCE_PX = 0.5  # rendered sphere centre vs projected atom centre
AREA_TOLERANCE = 0.08  # relative: rendered disc area vs π (r k)²
BOUNDS_TOLERANCE_PX = 1.5  # rendered extent vs projected framing bounds

CELL_EDGE = re.compile(r"^cylinder \{ <([^>]*)>, <([^>]*)>, \S+ texture \{ Ycr_Texture_Cell", re.M)
CYLINDER = re.compile(r"^cylinder \{ <([^>]*)>, <([^>]*)>, (.*)$", re.M)
ATOM = re.compile(
    r"^sphere \{ <([^>]*)>, ([-\d.e]+) .*// atom #(\d+) (\w+) image \(([-\d, ]+)\)$", re.M
)


def structure_of(case: str):
    name, repetitions = CASES[case]
    return load_input(FIXTURES / name).structure, repetitions


def coloured(scene: SceneSettings, structure) -> SceneSettings:
    for element, color in zip(sorted(set(structure.symbols)), COLORS, strict=False):
        scene = scene.with_element_color(element, color)
    return scene


def render(geometry, camera, environment, size, executable, folder) -> np.ndarray:
    """Render with POV-Ray; return the image as an ``int`` RGBA array."""
    settings = RenderSettings(*size, transparent_background=environment.transparent)
    job = prepare_job(geometry, camera, environment, settings, parent=folder)
    try:
        result = run_job(job, executable, timeout=300)
        assert result.ok, result.message
        return load_rgba(result.image_path).astype(int)
    finally:
        job.cleanup()


def disc_gap_px(geometry: DisplayGeometry, camera: Camera, width: int, height: int) -> float:
    """Return the smallest distance in pixels between the edges of two atom discs."""
    xy = camera.project(geometry.positions, width, height)
    r = geometry.radii * camera.pixels_per_angstrom(height)
    distance = np.hypot(*(xy[:, None, :] - xy[None, :, :]).transpose(2, 0, 1))
    gaps = distance - r[:, None] - r[None, :]
    np.fill_diagonal(gaps, np.inf)
    return float(gaps.min())


def separating_camera(geometry: DisplayGeometry, width: int, height: int) -> Camera:
    """Return the orientation on a fixed 10° grid where projected atoms are farthest apart.

    It is chosen from the camera model alone (deterministically); the render then shows
    whether POV-Ray draws every atom where the model puts it.
    """
    points, radii = geometry.points_and_radii()
    start = Camera.looking_along((0.3, -1.0, -0.25), (0, 0, 1))
    cameras = (
        start.orbit(azimuth=az, elevation=el).fitted(points, radii, width / height, margin=0.1)
        for az, el in itertools.product(range(0, 360, 10), range(-60, 61, 10))
    )
    return max(cameras, key=lambda camera: disc_gap_px(geometry, camera, width, height))


def segment_distance(p, a, b) -> float:
    ab = b - a
    t = np.clip((p - a) @ ab / (ab @ ab), 0.0, 1.0)
    return float(np.hypot(*(p - (a + t * ab))))


def vector3(text: str) -> np.ndarray:
    return np.array([float(v) for v in text.split(",")])


def same_segment(segment, cylinder) -> bool:
    (a, b), (c, d) = segment, cylinder
    tolerance = 2 * WRITER_TOLERANCE
    forward = np.allclose(a, c, atol=tolerance) and np.allclose(b, d, atol=tolerance)
    backward = np.allclose(a, d, atol=tolerance) and np.allclose(b, c, atol=tolerance)
    return bool(forward or backward)


# ----- A. analytic: the scene written for POV-Ray is the shared geometry ------------------
@pytest.mark.parametrize("case", sorted(CASES))
def test_pov_scene_holds_exactly_the_shared_geometry(case):
    structure, repetitions = structure_of(case)
    scene = SceneSettings(repetitions=repetitions)
    geometry = build_geometry(structure, scene)
    camera = Camera.looking_along((0.3, -1.0, -0.25), (0, 0, 1))
    text = scene_to_pov(geometry, camera, Environment(), RenderSettings(400, 300))
    # Atoms: one sphere per displayed atom, at its position, with its radius and identity.
    atoms = ATOM.findall(text)
    assert len(atoms) == len(geometry) == count_displayed_atoms(structure, scene)
    for row, (position, radius, number, element, image) in enumerate(atoms):
        source, offset = geometry.atom_ids[row]
        assert (int(number) - 1, tuple(int(v) for v in image.split(","))) == (source, offset)
        assert element == structure.symbols[source] == geometry.elements[row]
        assert np.allclose(vector3(position), geometry.positions[row], atol=WRITER_TOLERANCE)
        assert abs(float(radius) - geometry.radii[row]) <= WRITER_TOLERANCE
    # Bonds: one cylinder between the two atom centres, or two halves meeting halfway.
    cylinders = [
        (vector3(a), vector3(b))
        for a, b, rest in CYLINDER.findall(text)
        if "Ycr_Texture_Cell" not in rest
    ]
    written = 0
    for i, j in geometry.bonds:
        p, q = geometry.positions[i], geometry.positions[j]
        middle = (p + q) / 2
        for pieces in (((p, q),), ((p, middle), (middle, q))):
            if all(any(same_segment(piece, c) for c in cylinders) for piece in pieces):
                written += len(pieces)
                break
        else:
            pytest.fail(f"bond {i}-{j} is not written")
    assert written == len(cylinders) and len(geometry.bonds) > 0
    # Cell edges: between lattice points, along one lattice vector, a whole number of cells
    # long (an outline of repeated cells spans all of them).
    edges = CELL_EDGE.findall(text)
    assert len(edges) == len(geometry.cell_edges) > 0
    for start, end in edges:
        a, b = vector3(start), vector3(end)
        for corner in (a, b):
            fractional = np.linalg.solve(structure.cell.T, corner)
            assert np.allclose(fractional, np.round(fractional), atol=1e-5)
        step = np.linalg.solve(structure.cell.T, b - a)
        length = np.round(np.abs(step), 5)
        assert sorted(length)[:2] == [0.0, 0.0] and length.max() in (1.0, 2.0, 3.0)


@pytest.mark.parametrize("case", sorted(CASES))
def test_periodic_images_are_exact_lattice_translations(case):
    structure, repetitions = structure_of(case)
    geometry = build_geometry(structure, SceneSettings(repetitions=repetitions))
    for row, (source, image) in enumerate(geometry.atom_ids):
        expected = structure.positions[source] + np.array(image) @ structure.cell
        assert np.allclose(geometry.positions[row], expected, rtol=0, atol=1e-9)
        # Inside the displayed cells (boundary images lie on their faces).
        fractional = np.linalg.solve(structure.cell.T, geometry.positions[row])
        assert np.all(fractional > -1e-6) and np.all(fractional < np.array(repetitions) + 1e-6)


@pytest.mark.parametrize("case", ["SrTiO3", "MgB2-2x2x1", "triclinic-2x1x1"])
@pytest.mark.parametrize("axis", ["a", "b", "c"])
def test_lattice_views_keep_the_cell_right_handed_on_screen(case, axis):
    """Looking down a, b, or c, the other two vectors turn counter-clockwise (a×b = c)."""
    structure, _ = structure_of(case)
    cell = structure.cell
    assert np.linalg.det(cell) > 0  # a right-handed lattice
    direction, up = axis_view(axis, cell)
    right, screen_up, _ = Camera.looking_along(direction, up).basis()
    first, second = {"a": (1, 2), "b": (2, 0), "c": (0, 1)}[axis]
    x1, y1 = cell[first] @ right, cell[first] @ screen_up
    x2, y2 = cell[second] @ right, cell[second] @ screen_up
    assert x1 * y2 - y1 * x2 > 0  # counter-clockwise on screen: not mirrored
    assert cell["abc".index(axis)] @ -np.asarray(direction, dtype=float) > 0  # faces us


def test_vectors_keep_attachment_direction_and_sign_in_every_image():
    """The synthetic antiferromagnet: every displayed Fe carries its source atom's moment."""
    project = load_input(AFM)
    scene = replace(project.scene, repetitions=(2, 2, 2))
    geometry = build_geometry(project.structure, scene)
    moments = dict(project.scene.vectors.sources)
    assert len(geometry.arrows) == len(geometry) > 2  # one arrow per displayed atom
    for arrow in geometry.arrows:
        source, _ = arrow.host
        host = geometry.positions[geometry.index_of(arrow.host)]
        stored = np.array(moments[source].components)
        tail, tip = np.array(arrow.tail), np.array(arrow.tip)
        drawn = tip - tail
        assert np.allclose(np.cross(drawn, stored), 0, atol=1e-9)  # parallel
        assert drawn @ stored > 0  # the same sign: no flipped moment
        assert np.allclose((tip + tail) / 2, host)  # placement "centred" on the atom
        assert np.linalg.norm(drawn) == pytest.approx(scene.vector_style.length)  # uniform
    assert {np.sign(a.tip[2] - a.tail[2]) for a in geometry.arrows} == {-1.0, 1.0}


# ----- B. styles never change the scientific data ------------------------------------------
TARGETS = [
    ("SrTiO3.cif", None),
    ("SrTiO3.vasp", None),  # selective dynamics: movable flags
    ("BaZrO3.cif", {"Ti": "Zr"}),
    ("MgB2.cif", None),
    ("MgB2.pw.in", None),  # Quantum ESPRESSO input
    ("triclinic.cif", None),
    ("Si_conventional.cif", None),
    (AFM, None),  # a project with vectors
]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def science(structure) -> dict:
    """Everything scientific about a structure, comparable with ``==``."""
    source = dict(structure.metadata.get("source") or {})
    source.pop("imported_at", None)  # the time of reading differs between two reads
    return {
        "cell": structure.cell.tolist(),
        "positions": structure.positions.tolist(),
        "numbers": structure.numbers.tolist(),
        "occupancy": structure.occupancy.tolist(),
        "movable": None if structure.movable is None else structure.movable.tolist(),
        "labels": structure.labels,
        "pbc": structure.pbc,
        "source": source,
    }


@pytest.mark.parametrize("parts", [CLI_STYLE_PARTS, STYLE_PARTS], ids=["default", "all"])
@pytest.mark.parametrize("target, mapping", TARGETS, ids=lambda v: getattr(v, "name", v))
def test_styles_never_change_the_scientific_data(target, mapping, parts):
    path = target if isinstance(target, Path) else FIXTURES / target
    stored = (sha(path), sha(STYLE))
    reference = load_input(path)  # read separately, never touched
    original = load_input(path)
    styled, _ = apply_style_file(original, STYLE, parts, element_map=mapping)
    expected = science(reference.structure)
    assert science(styled.structure) == expected
    assert science(original.structure) == expected  # the input object is not modified
    assert styled.scene.vectors == reference.scene.vectors
    if "display" not in parts:  # then the same atoms are drawn at the same places
        before = build_geometry(reference.structure, reference.scene)
        after = build_geometry(styled.structure, styled.scene)
        assert after.atom_ids == before.atom_ids
        assert np.array_equal(after.positions, before.positions)
    assert (sha(path), sha(STYLE)) == stored  # neither file is written


# ----- A. the ray-traced image ---------------------------------------------------------------
@pytest.mark.povray
@pytest.mark.parametrize("case", sorted(CASES))
def test_rendered_atoms_and_periodic_images_follow_the_camera_model(
    case, povray_executable, tmp_path, record_property
):
    structure, repetitions = structure_of(case)
    scene = SceneSettings(
        radius_scale=0.2 if np.prod(repetitions) > 1 else 0.25,
        show_cell=False,
        bonds=BondSettings(enabled=False),
        repetitions=repetitions,
    )
    geometry = build_geometry(structure, coloured(scene, structure))
    size = width, height = 480, 360
    camera = separating_camera(geometry, width, height)
    assert disc_gap_px(geometry, camera, width, height) > 4  # every atom can be seen
    environment = Environment(transparent=True)
    image = render(geometry, camera, environment, size, povray_executable, tmp_path)
    blobs = find_blobs(image.astype(np.uint8))
    assert len(blobs) == len(geometry)  # every atom and periodic image, nothing else
    expected = camera.project(geometry.positions, width, height)
    matches = match_spheres(expected, geometry.colors, blobs)
    errors = [m.error_px for m in matches]
    assert max(errors) < CENTROID_TOLERANCE_PX, errors
    assert all(m.hue_ok for m in matches)  # the right element at each place
    k = camera.pixels_per_angstrom(height)
    area = {b.centroid: b.area for b in blobs}
    areas = [
        area[m.found] / (np.pi * (r * k) ** 2) - 1
        for m, r in zip(matches, geometry.radii, strict=True)
    ]
    assert max(np.abs(areas)) < AREA_TOLERANCE, areas
    # Negative control: the mirror image of the prediction does not match.
    mirrored = expected * (-1, 1) + (width, 0)
    mirror_error = max(m.error_px for m in match_spheres(mirrored, geometry.colors, blobs))
    assert mirror_error > 5
    for name, value in (
        ("atoms", len(geometry)),
        ("max_centroid_error_px", max(errors)),
        ("max_relative_area_error", float(max(np.abs(areas)))),
        ("mirrored_max_error_px", mirror_error),
    ):
        record_property(name, value)


@pytest.mark.povray
@pytest.mark.parametrize("case", ["SrTiO3", "MgB2-2x2x1", "triclinic-2x1x1"])
def test_rendered_half_bonds_join_their_own_atoms(
    case, povray_executable, tmp_path, record_property
):
    structure, repetitions = structure_of(case)
    scene = SceneSettings(radius_scale=0.25, show_cell=False, repetitions=repetitions)
    geometry = build_geometry(structure, coloured(scene, structure))
    assert len(geometry.bonds) > 0
    size = width, height = 480, 360
    camera = separating_camera(geometry, width, height)
    environment = Environment(transparent=True)
    image = render(geometry, camera, environment, size, povray_executable, tmp_path)
    xy = camera.project(geometry.positions, width, height)
    k = camera.pixels_per_angstrom(height)
    radii, bond = geometry.radii * k, geometry.bond_radius * k
    checked = 0
    for number, (i, j) in enumerate(geometry.bonds):
        for fraction, atom in ((0.25, i), (0.75, j)):  # inside each atom's half
            inside = geometry.positions[i] + fraction * (
                geometry.positions[j] - geometry.positions[i]
            )
            point = camera.project([inside], width, height)[0]
            covered = any(np.hypot(*(point - xy[n])) < radii[n] + 2 for n in range(len(xy)))
            crossing = any(
                segment_distance(point, xy[a], xy[b]) < bond + 3
                for other, (a, b) in enumerate(geometry.bonds)
                if other != number
            )
            if covered or crossing:
                continue  # an atom or another bond is in front in this view
            pixel = image[int(point[1]), int(point[0])]
            assert pixel[3] > 200, (i, j, fraction)  # the bond is drawn there
            assert np.argmax(pixel[:3]) == np.argmax(geometry.colors[atom]), (i, j, fraction)
            checked += 1
    assert checked >= 2
    record_property("bonds", len(geometry.bonds))
    record_property("half_bond_samples_checked", checked)


@pytest.mark.povray
def test_rendered_vector_arrows_follow_the_shared_geometry(
    povray_executable, tmp_path, record_property
):
    project = load_input(AFM)
    style = replace(project.scene.vector_style, color=(0.1, 0.8, 0.1))  # green arrows
    project = replace(
        project,
        scene=replace(project.scene, vector_style=style),
        environment=Environment(transparent=True),
    )
    size = width, height = 480, 360
    geometry, camera, _ = scene_for(project, width, height, ViewPolicy(view="a"))
    image = render(geometry, camera, project.environment, size, povray_executable, tmp_path)
    r, g, b = image[..., 0], image[..., 1], image[..., 2]
    green = (g > 90) & (r < 0.6 * g) & (b < 0.6 * g)
    k = camera.pixels_per_angstrom(height)
    xy = camera.project(geometry.positions, width, height)
    radii = geometry.radii * k
    checked = 0
    for arrow in geometry.arrows:
        tail, tip = np.array(arrow.tail), np.array(arrow.tip)
        x, y = camera.project([tail + 0.9 * (tip - tail)], width, height)[0]  # in the head
        if any(np.hypot(x - u, y - v) < rr + 2 for (u, v), rr in zip(xy, radii, strict=True)):
            continue  # an atom is in front of it, or it is in front of an atom
        x, y = int(round(x)), int(round(y))
        assert green[y - 2 : y + 3, x - 2 : x + 3].any(), arrow.host
        checked += 1
    assert checked >= len(geometry.arrows) // 2
    record_property("arrows", len(geometry.arrows))
    record_property("arrow_heads_checked", checked)
    # Arrow pixels appear only where arrows are: within their projected extent.
    ends = camera.project([p for a in geometry.arrows for p in (a.tail, a.tip)], width, height)
    pad = geometry.arrows[0].head_radius * k + 2
    ys, xs = np.nonzero(green)
    assert xs.min() >= ends[:, 0].min() - pad and xs.max() <= ends[:, 0].max() + pad
    assert ys.min() >= ends[:, 1].min() - pad and ys.max() <= ends[:, 1].max() + pad


@pytest.mark.povray
@pytest.mark.parametrize("size", [(480, 300), (300, 480)], ids=["landscape", "portrait"])
@pytest.mark.parametrize(
    "source, view",
    [("SrTiO3-2x2x1", "default"), ("MgB2-2x2x1", "c"), ("triclinic-2x1x1", "b"), ("afm", "a")],
)
def test_fitted_views_are_not_clipped_in_the_render(
    source, view, size, povray_executable, tmp_path, record_property
):
    if source == "afm":
        project = load_input(AFM)  # whole arrows must fit too
    else:
        structure, repetitions = structure_of(source)
        project = Project(structure, SceneSettings(repetitions=repetitions))
    environment = Environment(transparent=True)
    project = replace(project, environment=environment)
    width, height = size
    geometry, camera, _ = scene_for(project, width, height, ViewPolicy(view=view))
    alpha = render(geometry, camera, environment, size, povray_executable, tmp_path)[..., 3]
    assert alpha[0].max() == alpha[-1].max() == alpha[:, 0].max() == alpha[:, -1].max() == 0
    ys, xs = np.nonzero(alpha > 0)
    drawn = np.array([xs.min(), xs.max() + 1, ys.min(), ys.max() + 1])
    points, radii = geometry.points_and_radii()
    xy = camera.project(points, width, height)
    r = np.broadcast_to(radii, len(points)) * camera.pixels_per_angstrom(height)
    bounds = np.array([min(xy[:, 0] - r), max(xy[:, 0] + r), min(xy[:, 1] - r), max(xy[:, 1] + r)])
    tolerance = BOUNDS_TOLERANCE_PX
    assert drawn[0] >= bounds[0] - tolerance and drawn[1] <= bounds[1] + tolerance
    assert drawn[2] >= bounds[2] - tolerance and drawn[3] <= bounds[3] + tolerance
    if not geometry.arrows:  # atoms and cell corners define the bounds exactly
        assert np.allclose(drawn, bounds, atol=tolerance), (drawn, bounds)
    record_property("max_bounds_difference_px", float(np.abs(drawn - bounds).max()))
    record_property(
        "nearest_border_px", float(min(drawn[0], width - drawn[1], drawn[2], height - drawn[3]))
    )


# ----- E. ray-traced effects -----------------------------------------------------------------
EFFECT_SIZE = (320, 240)


def luminance(image: np.ndarray) -> np.ndarray:
    return image[..., :3] @ np.array([0.2126, 0.7152, 0.0722])


def effect_render(scene, environment, executable, folder):
    """Render SrTiO3 in the default fitted view; return image, geometry, and camera."""
    project = Project(load_input(FIXTURES / "SrTiO3.cif").structure, scene, environment)
    geometry, camera, _ = scene_for(project, *EFFECT_SIZE)
    image = render(geometry, camera, environment, EFFECT_SIZE, executable, folder)
    return image.astype(float), geometry, camera


def sphere_regions(geometry, camera, inner=0.7, lower=False):
    """Yield one pixel mask per atom: a disc inside the sphere, or its lower part."""
    width, height = EFFECT_SIZE
    xy = camera.project(geometry.positions, width, height)
    radii = geometry.radii * camera.pixels_per_angstrom(height)
    yy, xx = np.mgrid[0:height, 0:width]
    for (x, y), r in zip(xy, radii, strict=True):
        mask = (xx - x) ** 2 + (yy - y) ** 2 < (inner * r) ** 2
        yield mask & (yy > y + 0.2 * r) if lower else mask


def excess(image, mask, channel) -> float:
    """Mean of one colour channel minus the mean of the other two, inside ``mask``."""
    pixels = image[mask][:, :3]
    others = [c for c in range(3) if c != channel]
    return float(np.mean(pixels[:, channel] - pixels[:, others].mean(axis=1)))


@pytest.mark.povray
def test_cast_shadows_and_soft_shadows_of_area_lights(povray_executable, tmp_path, record_property):
    scene = SceneSettings(repetitions=(2, 2, 1))
    studio = environment_from_preset("studio_white")  # a floor and an area key light
    assert studio.floor and studio.shadows and studio.light_size > 0
    run = povray_executable
    shadowed, _, _ = effect_render(scene, studio, run, tmp_path)
    plain, _, _ = effect_render(scene, replace(studio, shadows=False), run, tmp_path)
    hard, _, _ = effect_render(scene, replace(studio, light_size=0.0), run, tmp_path)
    darker = luminance(plain) - luminance(shadowed)
    assert np.mean(darker > 15) > 0.05  # the structure casts a visible shadow

    def penumbra(image):
        """Fraction of shadow pixels that are only partly dark."""
        shade = luminance(plain) - luminance(image)
        shade = shade[shade > 5]
        peak = np.percentile(shade, 95)
        return np.mean((shade > 0.2 * peak) & (shade < 0.8 * peak))

    assert penumbra(shadowed) > penumbra(hard) + 0.05  # the area light softens the edges
    record_property("shadowed_fraction", float(np.mean(darker > 15)))
    record_property("penumbra_area_light", float(penumbra(shadowed)))
    record_property("penumbra_point_light", float(penumbra(hard)))


@pytest.mark.povray
def test_polished_metal_reflects_and_glass_transmits(povray_executable, tmp_path, record_property):
    grey = SceneSettings(boundary_images=False, show_cell=False)
    for element in ("Sr", "Ti", "O"):
        grey = grey.with_element_color(element, (0.8, 0.8, 0.8))
    run = povray_executable
    # A red floor seen in the lower part of each sphere: chrome mirrors it, matte does not.
    red_floor = replace(environment_from_preset("studio_white"), floor_color=(0.9, 0.1, 0.1))
    for material, low, high in (("chrome", 30, 255), ("matte", -255, 5), ("satin", -255, 5)):
        image, geometry, camera = effect_render(
            replace(grey, material=material), red_floor, run, tmp_path
        )
        values = [excess(image, mask, 0) for mask in sphere_regions(geometry, camera, lower=True)]
        assert all(low < v < high for v in values), (material, values)
        record_property(f"red_excess_{material}", f"{min(values):.1f} to {max(values):.1f}")
    # A blue background seen through the centre of each sphere: glass transmits it.
    blue = replace(Environment(), background=(0.1, 0.2, 0.9), background_bottom=(0.1, 0.2, 0.9))
    for material, low, high in (("glass", 20, 255), ("satin", -255, 5)):
        image, geometry, camera = effect_render(
            replace(grey, material=material), blue, run, tmp_path
        )
        values = [excess(image, mask, 2) for mask in sphere_regions(geometry, camera, inner=0.5)]
        assert all(low < v < high for v in values), (material, values)
        record_property(f"blue_excess_{material}", f"{min(values):.1f} to {max(values):.1f}")
