# Readers, projects, and styles

See the [user-facing format restrictions](../FORMATS.md) before importing data.

::: ycrystal.io.readers
    options:
      members:
        - FORMAT_NAMES
        - StructureImportError
        - UnsupportedStructureError
        - FormatChoiceRequired
        - BlockChoiceRequired
        - ElementMappingRequired
        - detect_format
        - read_structure
        - evaluate_qe_expression
        - fortran_real

## Quantum ESPRESSO lattices (`ibrav`)

::: ycrystal.io.qe_lattice
    options:
      members:
        - IBRAV_LATTICES
        - LatticeError
        - celldm_from_input
        - ibrav_cell

::: ycrystal.io.project
    options:
      members:
        - Project
        - ProjectError
        - project_to_dict
        - project_from_dict
        - save_project
        - load_project
        - SCHEMA_VERSION

## Pictures and packages

::: ycrystal.io.images
    options:
      members:
        - ImageAsset
        - ImageError
        - import_image
        - image_from_bytes
        - register_image
        - get_image
        - asset_filename
        - MAX_IMAGE_BYTES
        - MAX_IMAGE_SIDE
        - MAX_IMAGE_PIXELS

::: ycrystal.io.package
    options:
      members:
        - PackageError
        - is_package
        - write_package
        - read_package
        - MAX_ENTRIES
        - MAX_DOCUMENT_BYTES
        - MAX_TOTAL_BYTES

## Styles

::: ycrystal.io.style
    options:
      members:
        - STYLE_PARTS
        - STYLE_SUFFIX
        - Style
        - StyleResult
        - StyleError
        - apply_style
        - ElementMapError
        - ElementTransfer
        - LEAVE_OUT_LABEL
        - check_element
        - style_elements
        - resolve_element_map
        - style_to_dict
        - style_from_dict
        - save_style
        - load_style
