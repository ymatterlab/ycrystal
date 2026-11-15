# GUI adapters

These interfaces need Qt; the viewport also needs a display and OpenGL when created.
Only Ycrystal's selected methods and signals are shown, with inherited members omitted.

::: ycrystal.gui.main_window.MainWindow
    options:
      members:
        - open_file
        - save
        - save_as
        - select
        - hide_selected
        - show_all_atoms
        - set_boundary_images
        - set_repetitions
        - set_cell_mode
        - set_bonds_enabled
        - set_bond_tolerance
        - set_bond_radius
        - set_bond_pair
        - view_along
        - set_material
        - set_element_material
        - set_atom_material
        - set_selection_material
        - clear_atom_materials
        - set_element_color
        - set_radius_scale
        - set_element_radius
        - reset_element_appearance
        - set_background
        - set_environment
        - set_lighting
        - open_lighting_setup
        - lighting_environment
        - open_material_gallery
        - open_environment_gallery
        - set_rotation_mode
        - rotation_mode
        - rotate_step
        - current_style
        - export_style
        - import_style
        - set_output_size
        - output_size
        - aspect_locked
        - aspect_ratio
        - set_aspect_locked
        - current_camera
        - current_render_settings
        - measurement_mode
        - set_measurement_mode
        - pick_measurement_atom
        - cancel_measurement
        - remove_measurements
        - clear_measurements
        - preview_settings
        - request_preview
        - cancel_render
        - export_pov
        - render_png
        - check_renderer

::: ycrystal.gui.color_dialog.ColorDialog
    options:
      members:
        - color_changed
        - color
        - set_color
        - hover_text
        - get_color

::: ycrystal.gui.gallery.PresetGallery
    options:
      members:
        - apply_requested
        - reset_requested
        - favourites
        - set_favourite
        - visible_ids
        - current_id
        - select_preset
        - set_targets
        - target

::: ycrystal.viewport.qt_viewport.StructureViewport
    options:
      members:
        - camera_changed
        - atom_clicked
        - key_pressed
        - set_scene
        - set_lighting
        - lighting_rig
        - set_highlight
        - set_measurement
        - pick
        - camera
        - set_camera
        - fit
        - set_output_aspect
        - output_aspect
        - frame_rect
        - frame_factor
        - output_camera
        - set_output_camera
        - set_frame_visible
        - supercell_drag_changed
        - supercell_drag_finished
        - set_supercell
        - set_handles_visible
        - handle_positions
        - handle_at
        - set_rotation_axis
        - rotation_axis
        - rotate_view
        - cancel_interaction
        - frame_to_output
        - render_size
        - screenshot
        - close_viewport

::: ycrystal.gui.lighting_setup.LightingSetupWindow
    options:
      members:
        - angle_requested
        - show_rig
        - show_angles

::: ycrystal.viewport.lighting_view.LightingOverview
    options:
      members:
        - key_drag_started
        - key_drag_changed
        - key_drag_finished
        - key_drag_cancelled
        - set_geometry
        - set_rig
        - reset_view
        - overview_camera
        - handle_positions
        - handle_at
        - begin_drag
        - drag_to
        - end_drag
        - cancel_drag

::: ycrystal.render.process.RenderProcess
    options:
      members:
        - finished
        - progress
        - start
        - is_running
        - cancel

::: ycrystal.render.process.RenderQueue
    options:
      members:
        - started
        - finished
        - progress
        - submit
        - cancel
        - is_busy
        - current_tag
