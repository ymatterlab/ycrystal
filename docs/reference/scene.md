# Scene and geometry

::: ycrystal.core.scene
    options:
      members:
        - AtomId
        - RGB
        - SceneSettings
        - Environment
        - BACKGROUND_MODES
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
        - material_ids

::: ycrystal.core.scene.Environment.live_background

::: ycrystal.core.scene.DisplayGeometry
    options:
      members:
        - index_of
        - element_counts
        - points_and_radii
        - bounding_sphere

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
