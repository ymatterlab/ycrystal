# Your first crystal figure

Prerequisites: [install Ycrystal](install.md), use an X11 desktop with working
OpenGL, and install POV-Ray for the PNG step. Commands below start in the checkout
root. The built-in sample works without importing a file.

## Start and arrange the sample

1. Create an output directory and launch:

    ```bash
    mkdir -p artifacts/first-figure
    .venv/bin/ycrystal --sample perovskite
    ```

2. The window shows SrTiO3 and reports **15 atoms** and **30 bonds shown**, with
   **1 × 1 × 1 cells**. The default view also draws bonds. Eight Sr corner balls and six O face balls are periodic images of
   the 5 input atoms; the Ti ball is at the centre. Use the **Scene ▸ Structure** tab to change repetitions; leave them at
   **1 × 1 × 1** for this tutorial.
3. Drag with the left mouse button to orbit. Shift + left drag pans; the wheel
   zooms. Press **F** over the 3D view to fit everything while keeping the current
   orientation. **View ▸ Reset View** restores the initial orientation and fits it.
4. Click a visible corner ball without dragging. It gets an orange highlight and
   the status bar reports the element, source atom number, image offset, and
   fractional/Cartesian coordinates. Press **Delete**: just that ball disappears and
   the status shows **14 atoms** with **1 hidden** (the status also includes bond and cell counts). Press **Ctrl+Z** to restore it.
   Press **Esc** to clear the selection. Hiding changes the figure, not the structure.

## Save the project and export the scene

1. Choose **File ▸ Save Project** (Ctrl+S). Navigate to the checkout's
   `artifacts/first-figure/` directory and save as `SrTiO3.ycrystal`. The title loses
   its modified marker (`*`). The project embeds the structure, view, and display
   settings, so reopening it does not need a source structure file.
2. In the toolbar, set **Output width** to **640 px**. The adjacent label gives
   the calculated width × height. Height follows the 3D viewport's aspect ratio;
   keep the window size fixed for subsequent exports. Leave **Transparent
   background** unchecked for a white background.
3. Choose **File ▸ Export POV-Ray…** and save as
   `artifacts/first-figure/SrTiO3.pov`. Ycrystal writes `SrTiO3.pov` and
   `SrTiO3.ini` in that directory. This step runs no renderer and creates no PNG.
   Both text files replace existing files of the same name; use a new name to
   preserve earlier work.

## Render the PNG

1. Choose **Render ▸ Check Renderer**. Expect a pass message naming POV-Ray and
   a sphere-centre error below 1 pixel. The check briefly blocks the window. If it
   fails, follow [renderer setup](rendering.md#configure-and-check-pov-ray).
2. Choose **Render ▸ Render PNG…** (Ctrl+R) and save as
   `artifacts/first-figure/SrTiO3.png`. The status changes to **Rendering …** and
   the window stays responsive during the render. A second render cannot start
   until this one finishes.
3. When complete, a dialog shows the PNG and its path. The image is 640 pixels wide,
   with the height shown in the toolbar. It has the same framing and hidden atoms
   as the live view, with POV-Ray lighting. Orientation axes and selection highlights
   are omitted. See the [example render](../index.md) for the default view at a fixed
   640 × 400 aspect.
4. Press **Ctrl+S** again to save the output settings. Close the window, relaunch,
   and use **File ▸ Open…** to reopen `SrTiO3.ycrystal`. Coordinates, hidden atoms,
   and camera are restored. A differently shaped window shows a different horizontal
   extent, so match the original window shape if you need the same framing.

Your chosen directory now contains the project, two editable scene files, and the
PNG. GUI renders use a separate temporary job directory and remove it after
completion. They do not render the exported `.pov` file; editing that file requires
[running its `.ini` directly](rendering.md#export-an-editable-scene).
