# Controls and display

Use the mouse and view shortcuts over the 3D viewport. VTK's default keys such as
`q` (quit) and `w` (wireframe) are disabled. **Help ▸ Mouse Controls** (F1) opens
the in-app summary.

| Input | Action |
| --- | --- |
| Left drag | Orbit about the view centre |
| Middle drag or Shift + left drag | Pan |
| Wheel or right drag | Zoom |
| F / toolbar Fit | Fit the displayed geometry, preserving orientation |
| View ▸ Reset View | Restore the default orientation and fit |
| Left click without dragging | Select the front-most ball; empty space clears |
| Ctrl + click | Add/remove a ball from the selection |
| Esc | Clear selection |
| Delete or Backspace | Hide selected displayed atoms |
| Ctrl+Z | Undo a display-setting change |
| Ctrl+Shift+Z or Ctrl+Y | Redo a display-setting change |
| Ctrl+O | Open a structure or project |
| Ctrl+S / Ctrl+Shift+S | Save Project / Save Project As… |
| Ctrl+R | Render PNG… |
| Ctrl+Q | Quit (asks about unsaved changes) |

## Boundary atoms and hiding

**View ▸ Show Boundary Atoms** is on by default. Atoms are wrapped along periodic
cell directions and repeated on equivalent faces, edges, and corners. A corner atom
can appear eight times. Turning the option off shows each input atom once at its
original position. It does not generate a supercell or change the atom count in the
scientific structure.

Each ball has its own identity: the source atom (0-based internally, 1-based in the
status bar) and an integer image offset `(na, nb, nc)`. The offset is relative to the
input position. A selected ball's Cartesian position is
`input_position + image_offset @ cell`, with lattice vectors as cell rows.

Delete hides only selected balls, including from POV exports and renders. Other
images of the same atom stay visible. **View ▸ Show All Atoms** restores all hidden
IDs. Hidden IDs survive toggling boundary images off and on. Selection highlights
are viewport overlays and do not appear in the figure.

Undo/redo covers hiding, Show All Atoms, and the boundary toggle. Camera navigation,
output settings, file opens, and saves are not undoable. Opening a new file clears
the undo history. A changed camera or output setting still marks the project modified.

## Output framing

The toolbar accepts widths from 16 to 8000 pixels. Height is calculated from the
viewport's aspect ratio and rounded to the nearest pixel, with a minimum of 1.
Resizing the window can therefore change the output height and horizontal framing.
Projection is orthographic; atoms do not shrink with distance from the camera.

The structure's coordinates, occupancies, and movable flags are scientific data.
Camera, radii, colours, boundary images, hiding, background, and lighting are
presentation state. The GUI currently exposes only some of those settings; it has
no atom editor, material gallery, or light editor.
