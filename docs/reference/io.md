# Readers and projects

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
