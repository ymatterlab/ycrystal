# Scene and geometry

::: ycrystal.core.scene
    options:
      members:
        - AtomId
        - RGB
        - SceneSettings
        - Environment
        - element_color
        - count_displayed_atoms
        - cell_edge_segments
        - displayed_atoms
        - build_geometry

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
