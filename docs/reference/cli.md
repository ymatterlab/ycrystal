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
        - is_packaged
        - PACKAGED_MENU_MESSAGE
        - data_home
        - icon_path
        - launcher_installed
        - ycrystal_command
        - desktop_entry
        - install_desktop
        - uninstall_desktop
        - install_menu_entry
        - uninstall_menu_entry
        - menu_entry_note
        - WINDOWS_PROG_ID
        - CLASSES_KEY
        - SHORTCUT_NAME
        - LEGACY_SHORTCUT_NAME
        - ICON_SIZES
        - windows_data_folder
        - windows_launch_command
        - write_windows_icon
        - project_type_handler
        - register_project_type
        - unregister_project_type
        - install_start_menu
        - is_source_shortcut
        - uninstall_start_menu

::: ycrystal.windows_shortcut
    options:
      members:
        - Shortcut
        - write_shortcut
        - read_shortcut
        - programs_folder
