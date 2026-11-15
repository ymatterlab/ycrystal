"""Custom material variants made from Ycrystal's own recipes (FR-MATERIAL-01).

A variant starts from a built-in material whose recipe Ycrystal writes itself and
changes some of its parameters. The parameters are typed numbers with explicit ranges
(see [`SCHEMAS`][ycrystal.presets.custom.SCHEMAS]); the POV-Ray 3.7 recipe text is
generated from them, never edited as text. Built-in presets stay unchanged.

Editable bases:

- Opaque finishes (Matte, Satin, Glossy, Ceramic, Plastic): diffuse, specular highlight
  amount and roughness (Plastic: phong highlight amount and size), reflection.
- Glass (tinted), Frosted glass, Gem: as above plus the pigment filter amount and the
  index of refraction; Frosted glass also the bump strength and scale of its surface
  relief.
- Decorative textures (Marble, Jade, Granite, Stone, Wood): the pattern scale, in the
  material's unit texture space (relative to each atom).

Native POV-Ray definitions (metals, ``M_Glass``, ``M_Ruby_Glass``) and the ASE styles are
not editable.

A [`MaterialDefinition`][ycrystal.presets.custom.MaterialDefinition] stores the base id,
a name, the definition version, and every parameter value (also those not shown in the
dialog), so a saved figure does not change if a built-in default changes later. Its id
is derived from that content (``custom_<base>_<digest>``): two different definitions
can never share an id, and a variant cannot replace a built-in or another variant.

Examples
--------
>>> from ycrystal.presets.custom import base_definition, schema_for
>>> satin = base_definition("satin")
>>> satin.parameter("specular"), satin.parameter("roughness")
(0.35, 0.02)
>>> shiny = satin.with_values(specular=0.7, roughness=0.005).renamed("Shiny satin")
>>> shiny.id.startswith("custom_satin_"), shiny.material().finish
(True, 'ambient 0.08 diffuse 0.75 specular 0.7 roughness 0.005')
>>> [p.key for p in schema_for("glass_frosted").visible()]
['diffuse', 'specular', 'roughness', 'reflection', 'filter', 'ior', 'bump_strength', 'bump_scale']
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, replace

DEFINITION_VERSION = 1
"""Version of the stored definition format; newer versions are refused on load."""

CUSTOM_PREFIX = "custom_"
"""Prefix of every variant id (no built-in id uses it)."""


class DefinitionError(ValueError):
    """A material definition cannot be used; ``str()`` explains why for the user."""


@dataclass(frozen=True)
class Parameter:
    """One editable number of a recipe.

    Attributes
    ----------
    key
        Stable name stored in definitions.
    label, help
        Text in the dialog.
    minimum, maximum
        Allowed range (inclusive).
    step, decimals
        Spin-box increment and shown decimals.
    unit
        Unit or kind of the number, for the dialog.
    visible
        Whether the dialog shows it; hidden parameters keep the base value but are
        stored so the variant is reproducible.
    """

    key: str
    label: str
    minimum: float
    maximum: float
    step: float
    decimals: int
    help: str
    unit: str = ""
    visible: bool = True


_P = {
    "ambient": Parameter("ambient", "Ambient", 0, 1, 0.01, 3, "Self-lit share", visible=False),
    "diffuse": Parameter(
        "diffuse", "Diffuse amount", 0, 1, 0.05, 2, "Share of light scattered evenly (matte part)."
    ),
    "specular": Parameter(
        "specular",
        "Specular amount",
        0,
        1,
        0.05,
        2,
        "Brightness of the highlight from the light sources.",
    ),
    "roughness": Parameter(
        "roughness",
        "Highlight roughness",
        0.0005,
        0.5,
        0.001,
        4,
        "Size of the highlight: small values give small, sharp highlights. This is the "
        "highlight only; it does not change the surface relief.",
    ),
    "phong": Parameter(
        "phong",
        "Specular amount (phong)",
        0,
        1,
        0.05,
        2,
        "Brightness of the phong highlight from the light sources.",
    ),
    "phong_size": Parameter(
        "phong_size",
        "Highlight sharpness",
        1,
        500,
        5,
        0,
        "Phong size: larger values give smaller, sharper highlights.",
    ),
    "reflection": Parameter(
        "reflection",
        "Reflection amount",
        0,
        1,
        0.02,
        2,
        "Share of the surroundings mirrored by the surface.",
    ),
    "reflection_min": Parameter(
        "reflection_min", "Reflection at normal view", 0, 1, 0.01, 2, "", visible=False
    ),
    "filter": Parameter(
        "filter",
        "Glass filter amount",
        0,
        1,
        0.05,
        2,
        "How much light passes through, tinted by the colour (POV-Ray filter). It is not "
        "a generic opacity and not an experimental optical constant.",
    ),
    "ior": Parameter(
        "ior",
        "Refractive index",
        1.0,
        3.0,
        0.01,
        2,
        "POV-Ray index of refraction of the interior (1 bends no light; glass about 1.5).",
    ),
    "bump_strength": Parameter(
        "bump_strength",
        "Bump strength",
        0,
        2,
        0.05,
        2,
        "Depth of the frosted surface relief (normal bumps). This is relief, not the "
        "highlight roughness.",
    ),
    "bump_scale": Parameter(
        "bump_scale",
        "Bump scale",
        0.005,
        1,
        0.005,
        3,
        "Size of the frosted relief relative to the atom radius (unit texture space).",
    ),
    "pattern_scale": Parameter(
        "pattern_scale",
        "Pattern scale",
        0.05,
        5,
        0.05,
        2,
        "Size of the texture pattern relative to the atom radius (unit texture space).",
    ),
}


@dataclass(frozen=True)
class RecipeSchema:
    """The editable recipe of one built-in material.

    Attributes
    ----------
    base
        Built-in material id.
    family
        ``"finish"`` (opaque), ``"glass"`` (filter, ior; ``material`` declaration), or
        ``"pattern"`` (pattern scale only).
    defaults
        Every parameter and its built-in value, as ``(key, value)`` pairs.
    fresnel
        Whether the reflection is written as ``{ min max fresnel on }`` (Gem).
    conserve_energy
        Whether ``conserve_energy`` is written (Gem).
    """

    base: str
    family: str
    defaults: tuple[tuple[str, float], ...]
    fresnel: bool = False
    conserve_energy: bool = False

    def parameters(self) -> list[Parameter]:
        """All parameters of the recipe, in dialog order."""
        return [_P[key] for key, _ in self.defaults]

    def visible(self) -> list[Parameter]:
        """Return the parameters the dialog shows."""
        return [p for p in self.parameters() if p.visible]


def _opaque(base: str, **values: float) -> RecipeSchema:
    order = ("ambient", "diffuse", "specular", "roughness", "phong", "phong_size", "reflection")
    return RecipeSchema(base, "finish", tuple((k, values[k]) for k in order if k in values))


def _glass(base: str, fresnel: bool = False, **values: float) -> RecipeSchema:
    order = (
        "ambient",
        "diffuse",
        "specular",
        "roughness",
        "reflection_min",
        "reflection",
        "filter",
        "ior",
        "bump_strength",
        "bump_scale",
    )
    return RecipeSchema(
        base,
        "glass",
        tuple((k, values[k]) for k in order if k in values),
        fresnel=fresnel,
        conserve_energy=fresnel,
    )


SCHEMAS: dict[str, RecipeSchema] = {
    schema.base: schema
    for schema in (
        # The values are those of the built-in recipes (presets/materials/*.json); the
        # tests check that an untouched variant writes an equivalent declaration.
        _opaque("matte", ambient=0.10, diffuse=0.85, specular=0.05, roughness=0.1, reflection=0),
        _opaque("satin", ambient=0.08, diffuse=0.75, specular=0.35, roughness=0.02, reflection=0),
        _opaque(
            "glossy",
            ambient=0.06,
            diffuse=0.65,
            specular=0.8,
            roughness=0.005,
            phong=0.3,
            phong_size=80,
            reflection=0.06,
        ),
        _opaque(
            "ceramic", ambient=0.07, diffuse=0.72, specular=0.7, roughness=0.003, reflection=0.05
        ),
        _opaque("plastic", ambient=0.07, diffuse=0.8, phong=0.6, phong_size=40, reflection=0),
        _glass(
            "glass",
            ambient=0.02,
            diffuse=0.1,
            specular=0.9,
            roughness=0.002,
            reflection=0.08,
            filter=0.8,
            ior=1.45,
        ),
        _glass(
            "glass_frosted",
            ambient=0.04,
            diffuse=0.25,
            specular=0.4,
            roughness=0.03,
            reflection=0.04,
            filter=0.6,
            ior=1.5,
            bump_strength=0.6,
            bump_scale=0.04,
        ),
        _glass(
            "gem",
            fresnel=True,
            ambient=0.0,
            diffuse=0.05,
            specular=1.0,
            roughness=0.001,
            reflection_min=0.05,
            reflection=0.3,
            filter=0.85,
            ior=2.42,
        ),
        RecipeSchema("marble", "pattern", (("pattern_scale", 0.6),)),
        RecipeSchema("jade", "pattern", (("pattern_scale", 0.6),)),
        RecipeSchema("granite", "pattern", (("pattern_scale", 0.5),)),
        RecipeSchema("stone", "pattern", (("pattern_scale", 0.6),)),
        RecipeSchema("wood", "pattern", (("pattern_scale", 0.35),)),
    )
}
"""Editable recipes by built-in material id."""


def schema_for(base: str) -> RecipeSchema:
    """Return the editable recipe of a built-in material.

    Raises
    ------
    DefinitionError
        If the material is not editable (or unknown), with the reason.
    """
    if base in SCHEMAS:
        return SCHEMAS[base]
    from ycrystal.presets import PresetError, get_material

    try:
        material = get_material(base)
    except PresetError:
        raise DefinitionError(f"The material {base!r} is not known to this Ycrystal.") from None
    if material.native:
        reason = (
            f"{material.name} uses POV-Ray's own definition "
            f"({', '.join(material.native)} from {', '.join(material.includes) or 'POV-Ray'}); "
            "its parameters cannot be edited in Ycrystal."
        )
    else:
        reason = f"{material.name} has no editable parameters in this version."
    raise DefinitionError(reason)


def editable(base: str) -> bool:
    """Return whether variants can be made from built-in material ``base``."""
    return base in SCHEMAS


def _number(value: float) -> str:
    text = repr(round(float(value), 6))
    return text[:-2] if text.endswith(".0") else text


@dataclass(frozen=True)
class MaterialDefinition:
    """A custom variant: base material, name, and every parameter value.

    Attributes
    ----------
    base
        Built-in material id the variant starts from.
    name
        Name shown in the interface and in exported scenes.
    values
        Every parameter of the base's schema, as sorted ``(key, value)`` pairs.
    version
        Definition format version.

    Raises
    ------
    DefinitionError
        For a non-editable base, missing or unknown parameters, non-finite or
        out-of-range values, an empty name, or a newer version.
    """

    base: str
    name: str
    values: tuple[tuple[str, float], ...]
    version: int = DEFINITION_VERSION

    def __post_init__(self) -> None:
        if not isinstance(self.version, int) or self.version < 1:
            raise DefinitionError("The material definition has no valid version.")
        if self.version > DEFINITION_VERSION:
            raise DefinitionError(
                f"The material {self.name!r} was made by a newer Ycrystal (definition "
                f"version {self.version}); update Ycrystal to use it."
            )
        name = " ".join(str(self.name).split())
        if not name or len(name) > 80:
            raise DefinitionError("A custom material needs a name of 1 to 80 characters.")
        object.__setattr__(self, "name", name)
        schema = schema_for(self.base)
        given = dict(self.values)
        expected = {key for key, _ in schema.defaults}
        if set(given) != expected:
            missing, extra = expected - set(given), set(given) - expected
            raise DefinitionError(
                f"The material {name!r} has the wrong parameters for {self.base!r}"
                + (f" (missing {', '.join(sorted(missing))})" if missing else "")
                + (f" (unknown {', '.join(sorted(extra))})" if extra else "")
                + "."
            )
        clean = []
        for key in sorted(given):
            parameter = _P[key]
            try:
                value = float(given[key])
            except (TypeError, ValueError):
                raise DefinitionError(f"{parameter.label} of {name!r} is not a number.") from None
            if not math.isfinite(value) or not parameter.minimum <= value <= parameter.maximum:
                raise DefinitionError(
                    f"{parameter.label} of {name!r} must be between {parameter.minimum:g} and "
                    f"{parameter.maximum:g} (got {value:g})."
                )
            clean.append((key, value))
        object.__setattr__(self, "values", tuple(clean))

    # ----- identity and values ---------------------------------------------------------
    @property
    def id(self) -> str:
        """Content-derived id: ``custom_<base>_<10 hex digits>``."""
        payload = json.dumps(self.to_dict(include_id=False), sort_keys=True)
        digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:10]
        return f"{CUSTOM_PREFIX}{self.base}_{digest}"

    def parameter(self, key: str) -> float:
        """Return one parameter value."""
        return dict(self.values)[key]

    def with_values(self, **values: float) -> MaterialDefinition:
        """Return the definition with some parameters changed (validated)."""
        table = dict(self.values)
        unknown = set(values) - set(table)
        if unknown:
            raise DefinitionError(f"Unknown parameters for {self.base!r}: {sorted(unknown)}")
        table.update({k: float(v) for k, v in values.items()})
        return replace(self, values=tuple(table.items()))

    def renamed(self, name: str) -> MaterialDefinition:
        """Return the definition with another name (and therefore another id)."""
        return replace(self, name=name)

    def changed(self) -> list[str]:
        """Keys whose values differ from the built-in recipe."""
        defaults = dict(SCHEMAS[self.base].defaults)
        return [k for k, v in self.values if not math.isclose(v, defaults[k], abs_tol=1e-12)]

    # ----- persistence -----------------------------------------------------------------
    def to_dict(self, include_id: bool = True) -> dict:
        """Return the stored form (JSON-compatible)."""
        data = {
            "base": self.base,
            "name": self.name,
            "version": self.version,
            "parameters": {key: value for key, value in self.values},
        }
        if include_id:
            data = {"id": self.id, **data}
        return data

    @classmethod
    def from_dict(cls, data: object) -> MaterialDefinition:
        """Read the stored form and check its id.

        Raises
        ------
        DefinitionError
            If the definition is invalid or its recorded id does not match its content.
        """
        if not isinstance(data, dict):
            raise DefinitionError("A custom material definition is damaged.")
        try:
            parameters = data["parameters"]
            if not isinstance(parameters, dict):
                raise TypeError
            definition = cls(
                base=str(data["base"]),
                name=str(data["name"]),
                values=tuple(parameters.items()),
                version=data.get("version", DEFINITION_VERSION),
            )
        except (KeyError, TypeError) as exc:
            raise DefinitionError(f"A custom material definition is incomplete ({exc}).") from None
        recorded = data.get("id")
        if recorded is not None and recorded != definition.id:
            raise DefinitionError(
                f"The custom material {definition.name!r} is damaged: its id does not match "
                "its parameters."
            )
        return definition

    # ----- rendering -------------------------------------------------------------------
    def material(self) -> object:
        """Return the [`Material`][ycrystal.presets.Material] this variant renders as."""
        from ycrystal.presets import LiveLook, get_material

        base = get_material(self.base)
        schema = SCHEMAS[self.base]
        v = dict(self.values)
        changes: dict = {}
        if schema.family == "pattern":
            changes["texture_scale"] = v["pattern_scale"]
            live = base.live
        else:
            changes["finish"] = _finish_text(schema, v)
            if schema.family == "glass":
                changes["filter"] = v["filter"]
                changes["interior"] = f"ior {_number(v['ior'])}"
                if "bump_strength" in v:
                    changes["normal"] = (
                        f"bumps {_number(v['bump_strength'])} scale {_number(v['bump_scale'])}"
                    )
            highlight = v.get("specular", v.get("phong", base.live.specular))
            roughness = v.get("roughness")
            base_roughness = dict(schema.defaults).get("roughness")
            power = base.live.specular_power
            if roughness and base_roughness:
                power = min(128.0, max(1.0, power * base_roughness / roughness))
            elif "phong_size" in v:
                power = min(128.0, max(1.0, v["phong_size"]))
            opacity = base.live.opacity
            if schema.family == "glass":
                opacity = max(0.15, min(1.0, 1.0 - 0.75 * v["filter"]))
            live = LiveLook(
                ambient=base.live.ambient,
                diffuse=v["diffuse"],
                specular=highlight,
                specular_power=power,
                opacity=opacity,
                color=base.live.color,
            )
        description = f"Custom variant of {base.name}" + (
            ": " + ", ".join(f"{_P[k].label.lower()} {_number(v[k])}" for k in self.changed())
            if self.changed()
            else " (unchanged parameters)"
        )
        return replace(
            base,
            id=self.id,
            name=self.name,
            description=description + ".",
            category="custom",
            live=live,
            provenance=f"Ycrystal recipe parameters, variant of {base.id}",
            order=100_000,
            base=self.base,
            parameters=self.values,
            **changes,
        )


def _finish_text(schema: RecipeSchema, v: dict[str, float]) -> str:
    parts = [f"ambient {_number(v['ambient'])}", f"diffuse {_number(v['diffuse'])}"]
    if "specular" in v:
        parts.append(f"specular {_number(v['specular'])} roughness {_number(v['roughness'])}")
    if "phong" in v:
        parts.append(f"phong {_number(v['phong'])} phong_size {_number(v['phong_size'])}")
    if schema.fresnel:
        parts.append(
            f"reflection {{ {_number(v['reflection_min'])} {_number(v['reflection'])} fresnel on }}"
        )
    elif v.get("reflection", 0) > 0:
        parts.append(f"reflection {_number(v['reflection'])}")
    if schema.conserve_energy:
        parts.append("conserve_energy")
    return " ".join(parts)


def base_definition(base: str, name: str | None = None) -> MaterialDefinition:
    """Return an untouched variant of ``base`` (named ``"<Base> (custom)"`` by default).

    Raises
    ------
    DefinitionError
        If ``base`` is not editable.
    """
    from ycrystal.presets import get_material

    schema = schema_for(base)
    return MaterialDefinition(
        base, name or f"{get_material(base).name} (custom)", tuple(schema.defaults)
    )
