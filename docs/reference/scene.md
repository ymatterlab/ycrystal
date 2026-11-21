# Scene and geometry

::: ycrystal.core.scene
    options:
      members:
        - AtomId
        - RGB
        - SceneSettings
        - Environment
        - BACKGROUND_MODES
        - LARGE_DISPLAY_ATOMS
        - element_color
        - count_displayed_atoms
        - cell_edge_segments
        - displayed_atoms
        - build_geometry

::: ycrystal.core.scene.SceneSettings
    options:
      members:
        - material_for
        - with_element_material
        - with_atom_materials
        - with_element_color
        - with_element_radius
        - radius_for
        - material_ids

::: ycrystal.core.scene.Environment.live_background

::: ycrystal.core.scene.DisplayGeometry
    options:
      members:
        - index_of
        - element_counts
        - points_and_radii
        - bounding_sphere

## Atom-attached vectors

::: ycrystal.core.vectors
    options:
      members:
        - MEANINGS
        - PLACEMENTS
        - LENGTH_MODES
        - ZERO_MODULUS
        - MIN_ARROW_LENGTH
        - MAX_HEAD_FRACTION
        - STYLE_RANGES
        - VectorRecord
        - VectorSet
        - VectorStyle
        - Arrow
        - arrow_length
        - arrow_for
        - resolve_arrows
        - arrow_spheres

## Element legend

::: ycrystal.core.legend
    options:
      members:
        - LEGEND_LAYOUTS
        - LEGEND_POSITIONS
        - LEGEND_ORDERS
        - MARKER_STYLES
        - LEGEND_RANGES
        - LegendSettings
        - LegendEntry
        - order_elements
        - legend_entries

## Background pictures

::: ycrystal.core.background
    options:
      members:
        - BackgroundImage
        - placement
        - FIT_MODES
        - IMAGE_FORMATS
        - ZOOM_RANGE
        - OFFSET_RANGE
        - BRIGHTNESS_RANGE

## Colours

::: ycrystal.core.colors
    options:
      members:
        - COLOR_FORMATS
        - NAMED_COLORS
        - parse_color
        - format_color
        - hex_to_rgb
        - to_255
        - to_hsv
        - to_hsl
        - to_lab
        - delta_e
        - nearest_named_color
        - describe_color
        - color_label

## Periodic bond rules

::: ycrystal.core.bonds
    options:
      members:
        - BondSettings
        - PeriodicBonds
        - PairSummary
        - periodic_bonds
        - summarize_pairs

::: ycrystal.core.bonds.BondSettings.pair_enabled

::: ycrystal.core.bonds.BondSettings.with_pair
