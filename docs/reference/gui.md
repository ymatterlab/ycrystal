# GUI adapters

These interfaces need Qt; the viewport also needs a display and OpenGL when created.
Only Ycrystal's selected methods and signals are shown, with inherited members omitted.

::: ycrystal.app.main

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
        - set_background
        - set_output_size
        - current_camera
        - current_render_settings
        - preview_settings
        - request_preview
        - cancel_render
        - export_pov
        - render_png
        - check_renderer

::: ycrystal.viewport.qt_viewport.StructureViewport
    options:
      members:
        - camera_changed
        - atom_clicked
        - key_pressed
        - set_scene
        - set_highlight
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
        - frame_to_output
        - render_size
        - screenshot
        - close_viewport

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
