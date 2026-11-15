# Structure and samples

::: ycrystal.core.structure

::: ycrystal.core.structure.Structure
    options:
      members:
        - from_ase
        - replace
        - to_ase
        - symbols
        - has_cell
        - composition

::: ycrystal.core.samples
    options:
      members:
        - perovskite_srtio3
        - triclinic_marker
        - SAMPLES

## Measurements

Distances and bond angles between displayed instances, used by the measurement modes
of the window. Session-only: nothing here is saved in projects.

::: ycrystal.core.measure
    options:
      members:
        - KINDS
        - MeasurementError
        - Measurement
        - atom_position
        - distance
        - bond_angle
        - measure
        - atom_text
        - result_text
        - measurement_text
        - MeasurementSession

## Comparison helpers

These support reader-equivalence checks, not GUI supercell controls.

::: ycrystal.core.compare
    options:
      members:
        - Comparison
        - compare_structures
        - supercell
