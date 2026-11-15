"""Resolved lighting rig shared by the POV-Ray writer and the live views (FR-LIGHT-01).

The lighting controls of an [`Environment`][ycrystal.core.scene.Environment] are
relative values: angles in the output camera's screen basis and a size in units of the
scene radius. [`resolve_lighting`][ycrystal.core.lighting.resolve_lighting] turns them
into world-space positions in Å for a given output camera and displayed geometry. The
POV-Ray writer, the live view's light approximation, and the Lighting Setup window all
use this one result, so they cannot disagree. Nothing here depends on Qt, VTK, or
POV-Ray syntax, and nothing is stored: the rig is derived from the environment, the
camera, and the geometry whenever it is needed.

Conventions
-----------
The basis is the output camera's ``(right, up, direction)`` from
[`Camera.basis`][ycrystal.core.camera.Camera.basis]; ``direction`` points from the eye
into the scene, so ``-direction`` points toward the viewer.

- Origin: the camera's focal point ``F`` (the point at the image centre).
- Distance: ``D = 4 R + |C - F| + 10`` Å, with ``C`` and ``R`` the centre and radius of
  [`DisplayGeometry.bounding_sphere`][ycrystal.core.scene.DisplayGeometry.bounding_sphere]
  (displayed atoms including boundary images and repetitions, plus cell edges; hidden
  atoms excluded).
- Key light: ``F + D (cos(el) (sin(az) right - cos(az) direction) + sin(el) up)``.
  Azimuth 0 and elevation 0 point from ``F`` toward the viewer; positive azimuth turns
  toward screen right, positive elevation toward screen up. Orbiting or rolling the
  camera turns the whole rig with the image.
- Fill light: fixed direction ``normalize(0.70 right - 0.25 up - 1.0 direction)``
  (lower right, toward the viewer: azimuth +35.0°, elevation -11.6°) at the same
  distance, always shadowless.
- Intensities are white light in linear units; there is no distance attenuation.
- Light size: the key light becomes a circular area light whose diameter is
  ``light_size × R`` Å, sampled on a 5 × 5 grid with adaptive refinement and no jitter;
  ``orient`` turns the disc toward each shaded point, so it acts like a sphere of that
  diameter rather than a fixed panel.
- Reflection panel: a disc of radius ``1.6 R`` at ``C + 3 R × key direction``, facing
  back along the key direction (anchored on ``C``, not ``F``).

Examples
--------
>>> from ycrystal.core.camera import Camera
>>> from ycrystal.core.lighting import resolve_lighting_for_bounds
>>> from ycrystal.core.scene import Environment
>>> camera = Camera((0, 0, 30), (0, 0, 0), (0, 1, 0), parallel_scale=5.0)
>>> env = Environment(key_azimuth=-65, key_elevation=25, key_light=1.3, fill_light=0.12)
>>> rig = resolve_lighting_for_bounds(env, camera, center=(0, 0, 0), radius=4.0)
>>> rig.distance
26.0
>>> [round(float(v), 3) for v in rig.key.position]
[-21.356, 10.988, 9.959]
>>> rig.key.is_area, rig.fill.shadows
(False, False)
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import numpy as np

from ycrystal.core.camera import Camera
from ycrystal.core.scene import DisplayGeometry, Environment

KEY_AZIMUTH_RANGE = (-180.0, 180.0)
"""Allowed key-light azimuth in degrees (the Lighting controls' range)."""

KEY_ELEVATION_RANGE = (-30.0, 89.0)
"""Allowed key-light elevation in degrees; the pole (90°) is excluded."""

FILL_COEFFICIENTS = (0.70, -0.25, -1.0)
"""Fill-light direction as coefficients of the camera's (right, up, direction)."""

DISTANCE_RADII = 4.0
"""Light distance in scene radii, before the pan offset and the margin."""

DISTANCE_MARGIN = 10.0
"""Constant part of the light distance, in Å."""

AREA_LIGHT_SAMPLES = 5
"""Grid size of an area light along each axis (POV-Ray ``5, 5``)."""

AREA_LIGHT_ADAPTIVE = 1
"""POV-Ray ``adaptive`` level of area lights: samples are refined where shadows vary."""

PANEL_DISTANCE_RADII = 3.0
"""Distance of the reflection panel from the bounding centre, in scene radii."""

PANEL_RADIUS_RADII = 1.6
"""Radius of the reflection panel, in scene radii."""


@dataclass(frozen=True, eq=False)
class ResolvedLight:
    """One light of a [`LightingRig`][ycrystal.core.lighting.LightingRig], in world space.

    Attributes
    ----------
    role
        ``"key"`` or ``"fill"``.
    position
        Position in Å, shape ``(3,)``.
    direction
        Unit vector from the rig origin ``F`` toward the light, shape ``(3,)``.
    intensity
        Brightness of white light in linear units (POV-Ray ``color rgb``); the light
        is left out when it is not positive.
    shadows
        Whether the light casts shadows (the fill light never does).
    area_size
        Diameter of the area light in Å; 0 for a point light.
    area_axes
        The two area-light axis vectors in Å (screen right and up, each of length
        `area_size`), or ``None`` for a point light.
    """

    role: str
    position: np.ndarray
    direction: np.ndarray
    intensity: float
    shadows: bool
    area_size: float = 0.0
    area_axes: tuple[np.ndarray, np.ndarray] | None = None

    @property
    def enabled(self) -> bool:
        """Whether the light is written (positive intensity)."""
        return self.intensity > 0

    @property
    def is_area(self) -> bool:
        """Whether the light is an area light."""
        return self.area_axes is not None


@dataclass(frozen=True, eq=False)
class ReflectionPanel:
    """The invisible bright disc that only appears in reflections.

    Attributes
    ----------
    center
        Centre in Å, shape ``(3,)``.
    normal
        Unit normal facing back toward the structure (``-key direction``).
    radius
        Disc radius in Å.
    """

    center: np.ndarray
    normal: np.ndarray
    radius: float


@dataclass(frozen=True, eq=False)
class LightingRig:
    """World-space lighting resolved for one output camera and displayed geometry.

    Attributes
    ----------
    origin
        Focal point ``F`` of the output camera in Å: the origin of all light
        directions.
    center
        Bounding centre ``C`` of the displayed geometry in Å.
    radius
        Bounding radius ``R`` in Å (the "scene radius" of the light size).
    distance
        Light distance ``D`` from ``F`` in Å.
    right, up, direction
        The output camera's orthonormal screen basis.
    azimuth, elevation
        Key-light angles in degrees, as stored in the environment.
    key, fill
        The two lights.
    panel
        The reflection panel, or ``None`` when it is switched off.
    """

    origin: np.ndarray
    center: np.ndarray
    radius: float
    distance: float
    right: np.ndarray
    up: np.ndarray
    direction: np.ndarray
    azimuth: float
    elevation: float
    key: ResolvedLight
    fill: ResolvedLight
    panel: ReflectionPanel | None

    def lights(self) -> tuple[ResolvedLight, ...]:
        """Return the enabled lights (key first)."""
        return tuple(light for light in (self.key, self.fill) if light.enabled)

    def horizontal(self, azimuth: float) -> np.ndarray:
        """Return the unit vector at ``azimuth`` degrees in the camera's horizontal plane."""
        az = np.radians(azimuth)
        return np.sin(az) * self.right - np.cos(az) * self.direction

    def key_point(self, azimuth: float, elevation: float) -> np.ndarray:
        """Return where the key light would be for the given angles (same distance)."""
        return self.origin + self.distance * key_direction(
            azimuth, elevation, self.right, self.up, self.direction
        )


def key_direction(
    azimuth: float, elevation: float, right: Any, up: Any, direction: Any
) -> np.ndarray:
    """Return the unit key-light direction for angles in degrees and a camera basis.

    ``cos(el) (sin(az) right - cos(az) direction) + sin(el) up``: azimuth 0 and
    elevation 0 point toward the viewer (``-direction``).
    """
    az, el = np.radians(azimuth), np.radians(elevation)
    return np.cos(el) * (np.sin(az) * right - np.cos(az) * direction) + np.sin(el) * up


def wrap_azimuth(azimuth: float) -> float:
    """Wrap an angle in degrees to ``[-180, 180)``."""
    return float((azimuth + 180.0) % 360.0 - 180.0)


def angles_of(
    vector: Any,
    right: Any,
    up: Any,
    direction: Any,
    previous_azimuth: float | None = None,
) -> tuple[float, float]:
    """Return key-light angles ``(azimuth, elevation)`` in degrees for a direction.

    The inverse of [`key_direction`][ycrystal.core.lighting.key_direction] in the given
    camera basis (use the output camera's, not that of another view). The elevation is
    clamped to [`KEY_ELEVATION_RANGE`][ycrystal.core.lighting.KEY_ELEVATION_RANGE] and
    the azimuth wrapped to ``[-180, 180)``.

    Parameters
    ----------
    vector
        Direction from the rig origin; it need not be normalized.
    right, up, direction
        Camera basis.
    previous_azimuth
        Azimuth kept when the direction is (nearly) vertical, where the azimuth is
        undefined; 0 when not given.

    Returns
    -------
    tuple of float
        ``(azimuth, elevation)`` in degrees.
    """
    v = np.asarray(vector, dtype=float)
    norm = float(np.linalg.norm(v))
    if norm == 0.0:
        return (previous_azimuth or 0.0, 0.0)
    v = v / norm
    x, y, z = float(v @ right), float(v @ up), float(-(v @ direction))
    elevation = math.degrees(math.asin(max(-1.0, min(1.0, y))))
    elevation = max(KEY_ELEVATION_RANGE[0], min(KEY_ELEVATION_RANGE[1], elevation))
    if math.hypot(x, z) < 1e-6:
        azimuth = previous_azimuth or 0.0
    else:
        azimuth = math.degrees(math.atan2(x, z))
    return wrap_azimuth(azimuth), elevation


def light_distance(center: Any, radius: float, origin: Any) -> float:
    """Return ``D = 4 R + |C - F| + 10`` Å."""
    offset = float(np.linalg.norm(np.asarray(center) - np.asarray(origin)))
    return DISTANCE_RADII * radius + offset + DISTANCE_MARGIN


def resolve_lighting(
    environment: Environment, camera: Camera, geometry: DisplayGeometry
) -> LightingRig:
    """Resolve an environment's lights for an output camera and a displayed geometry.

    Parameters
    ----------
    environment
        Lighting values (intensities, key angles, light size, shadows, panel).
    camera
        Output camera; only its focal point and orientation matter (zoom, output size,
        and the eye distance do not change the rig).
    geometry
        Displayed geometry; its bounding sphere sets the distance and the scale.

    Returns
    -------
    LightingRig
        World-space lights; see the module notes for the formulas.
    """
    center, radius = geometry.bounding_sphere()
    return resolve_lighting_for_bounds(environment, camera, center, radius)


def resolve_lighting_for_bounds(
    environment: Environment, camera: Camera, center: Any, radius: float
) -> LightingRig:
    """Resolve the lights from precomputed bounds ``(center, radius)``.

    Same as [`resolve_lighting`][ycrystal.core.lighting.resolve_lighting] for callers
    that cache the bounding sphere (the live view updates its lights on every redraw).
    """
    right, up, direction = camera.basis()
    focal = np.asarray(camera.focal_point)
    center = np.asarray(center, dtype=float)
    radius = float(radius)
    distance = light_distance(center, radius, focal)
    key_dir = key_direction(
        environment.key_azimuth, environment.key_elevation, right, up, direction
    )
    fill_dir = _unit(
        FILL_COEFFICIENTS[0] * right + FILL_COEFFICIENTS[1] * up + FILL_COEFFICIENTS[2] * direction
    )
    axes = None
    size = 0.0
    if environment.light_size > 0:
        size = environment.light_size * radius
        axes = (right * size, up * size)
    key = ResolvedLight(
        role="key",
        position=focal + distance * key_dir,
        direction=key_dir,
        intensity=float(environment.key_light),
        shadows=bool(environment.shadows),
        area_size=size,
        area_axes=axes,
    )
    fill = ResolvedLight(
        role="fill",
        position=focal + distance * fill_dir,
        direction=fill_dir,
        intensity=float(environment.fill_light),
        shadows=False,
    )
    panel = None
    if environment.reflector:
        panel = ReflectionPanel(
            center=center + PANEL_DISTANCE_RADII * radius * key_dir,
            normal=-key_dir,
            radius=PANEL_RADIUS_RADII * radius,
        )
    return LightingRig(
        origin=focal,
        center=center,
        radius=radius,
        distance=distance,
        right=right,
        up=up,
        direction=direction,
        azimuth=float(environment.key_azimuth),
        elevation=float(environment.key_elevation),
        key=key,
        fill=fill,
        panel=panel,
    )


def arc_points(
    rig: LightingRig,
    azimuths: tuple[float, float],
    elevations: tuple[float, float],
    radius: float,
    count: int = 48,
) -> np.ndarray:
    """Return points on a great-circle-like path around ``F`` for guide drawings.

    Angles are interpolated linearly from the first to the second value, so a constant
    elevation gives an azimuth arc and a constant azimuth an elevation arc.

    Parameters
    ----------
    rig
        Rig whose origin and basis are used.
    azimuths, elevations
        Start and end angles in degrees.
    radius
        Distance of the points from ``F`` in Å.
    count
        Number of points.

    Returns
    -------
    numpy.ndarray
        Points in Å, shape ``(count, 3)``.
    """
    t = np.linspace(0.0, 1.0, count)
    az = azimuths[0] + t * (azimuths[1] - azimuths[0])
    el = elevations[0] + t * (elevations[1] - elevations[0])
    dirs = np.array(
        [key_direction(a, e, rig.right, rig.up, rig.direction) for a, e in zip(az, el, strict=True)]
    )
    return rig.origin + radius * dirs


def _unit(vector: np.ndarray) -> np.ndarray:
    return vector / np.linalg.norm(vector)
