# POV export and render jobs

::: ycrystal.render.pov_writer
    options:
      members:
        - RenderSettings
        - FLOOR_TILT_DEG
        - required_includes
        - scene_to_pov
        - render_ini
        - write_scene_files
        - stage_assets

## Lighting

::: ycrystal.core.lighting
    options:
      members:
        - resolve_lighting
        - resolve_lighting_for_bounds
        - LightingRig
        - ResolvedLight
        - ReflectionPanel
        - key_direction
        - angles_of
        - wrap_azimuth
        - light_distance
        - arc_points
        - KEY_AZIMUTH_RANGE
        - KEY_ELEVATION_RANGE
        - FILL_COEFFICIENTS
        - AREA_LIGHT_SAMPLES
        - AREA_LIGHT_ADAPTIVE

## Output size

::: ycrystal.core.aspect
    options:
      members:
        - MIN_OUTPUT_PIXELS
        - MAX_OUTPUT_PIXELS
        - OutputSizeError
        - round_pixels
        - matches_ratio
        - linked_size
        - preset_size
        - swapped
        - PREVIEW_PRESETS
        - DEFAULT_PREVIEW
        - MIN_PREVIEW_PIXELS
        - MAX_PREVIEW_PIXELS
        - PreviewSize
        - preview_size
        - preview_preset_width

## Image export (PNG, PDF, JPEG)

::: ycrystal.core.export
    options:
      members:
        - MM_PER_INCH
        - FORMATS
        - DEFAULT_FORMAT
        - DEFAULT_JPEG_QUALITY
        - DEFAULT_DPI
        - COMMON_DPI
        - MIN_EXPORT_PIXELS
        - MAX_EXPORT_PIXELS
        - MAX_EXPORT_MEGAPIXELS
        - MIN_DPI
        - MAX_DPI
        - MAX_PDF_PAGE_MM
        - SizePreset
        - SIZE_PRESETS
        - ExportSizeError
        - size_preset
        - pixels_from_mm
        - mm_from_pixels
        - convert_length
        - figure_pixels
        - linked_height
        - linked_width
        - format_suffixes
        - format_label
        - format_for_path
        - path_for_format
        - ExportOptions
        - check_export_size

::: ycrystal.render.formats
    options:
      members:
        - ExportWriteError
        - JPEG_MATTE
        - write_export
        - png_with_resolution
        - png_resolution
        - opaque_image
        - fitted_rect

::: ycrystal.render.povray
    options:
      members:
        - PovrayNotFoundError
        - find_povray
        - povray_version
        - explain_failure
        - INCLUDE_FALLBACK_DIRS
        - include_directories
        - missing_includes

::: ycrystal.render.jobs
    options:
      members:
        - RenderResult
        - parse_progress
        - prepare_job
        - finish_job
        - run_job
        - copy_result

::: ycrystal.render.jobs.RenderJob
    options:
      members:
        - arguments
        - cleanup

::: ycrystal.render.selftest
    options:
      members:
        - TOLERANCE_PX
        - SelfTestResult
        - run_self_test
