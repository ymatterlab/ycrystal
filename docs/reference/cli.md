# Command line, batch rendering, and desktop

::: ycrystal.app.main

::: ycrystal.batch
    options:
      members:
        - load_input
        - CLI_STYLE_PARTS
        - StyleTransferError
        - parse_style_parts
        - parse_element_map
        - apply_style_file
        - scene_for
        - export_scene
        - render_png

::: ycrystal.manifest
    options:
      members:
        - MANIFEST_FORMAT
        - MANIFEST_SCHEMA_VERSION
        - REPORT_NAME
        - SETTINGS
        - ManifestError
        - PlannedJob
        - JobResult
        - BatchReport
        - load_manifest
        - plan_batch
        - run_batch
        - write_report

::: ycrystal.provenance
    options:
      members:
        - PROVENANCE_FORMAT
        - PROVENANCE_SCHEMA_VERSION
        - PROVENANCE_SUFFIX
        - REPRODUCIBILITY_NOTE
        - SnapshotError
        - SourceFile
        - FigureRequest
        - SnapshotRender
        - provenance_path
        - file_sha256
        - png_size
        - input_format
        - same_file
        - check_snapshot_target
        - snapshot_project
        - provenance_record
        - render_snapshot

::: ycrystal.desktop
    options:
      members:
        - DESKTOP_ID
        - PROJECT_MIME_TYPE
        - desktop_supported
        - data_home
        - icon_path
        - launcher_installed
        - ycrystal_command
        - desktop_entry
        - install_desktop
        - uninstall_desktop
