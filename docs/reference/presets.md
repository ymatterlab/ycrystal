# Material, environment, and lighting presets

::: ycrystal.presets
    options:
      members:
        - DEFAULT_MATERIAL
        - DEFAULT_ENVIRONMENT
        - DEFAULT_LIGHTING
        - MATERIAL_KINDS
        - MATERIAL_CATEGORIES
        - ENVIRONMENT_CATEGORIES
        - PresetError
        - LiveLook
        - Material
        - EnvironmentPreset
        - LightingPreset
        - materials
        - environments
        - lighting_presets
        - get_material
        - get_environment
        - get_lighting
        - environment_from_preset
        - apply_lighting
        - register_definition
        - get_definition
        - custom_materials
        - CUSTOM_THUMBNAILS

## Custom material variants

::: ycrystal.presets.custom
    options:
      members:
        - DEFINITION_VERSION
        - CUSTOM_PREFIX
        - DefinitionError
        - Parameter
        - RecipeSchema
        - SCHEMAS
        - MaterialDefinition
        - schema_for
        - editable
        - base_definition

## Gallery thumbnails

::: ycrystal.render.thumbnails
    options:
      members:
        - THUMBNAIL_SIZE
        - MATERIAL_ENVIRONMENT
        - material_scene
        - material_thumbnail_job
        - environment_scene
        - scene_digest
        - thumbnail_directory
        - load_index
