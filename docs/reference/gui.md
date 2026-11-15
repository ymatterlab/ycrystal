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
        - current_camera
        - current_render_settings
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
        - render_size
        - screenshot
        - close_viewport

::: ycrystal.render.process.RenderProcess
    options:
      members:
        - finished
        - start
        - is_running
        - cancel
