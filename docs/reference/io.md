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

::: ycrystal.io.project
    options:
      members:
        - Project
        - ProjectError
        - project_to_dict
        - project_from_dict
        - save_project
        - load_project

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
        - style_to_dict
        - style_from_dict
        - save_style
        - load_style
