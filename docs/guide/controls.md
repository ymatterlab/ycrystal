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
| F5 | POV-Ray preview of the framed view |
| Ctrl+R | Render PNG… (toolbar **Cancel Render** stops it) |
| Ctrl+Q | Quit (asks about unsaved changes) |

## Boundary atoms and hiding

**View ▸ Show Boundary Atoms** is on by default. Atoms are wrapped along periodic
cell directions and repeated on equivalent faces, edges, and corners. A corner atom
can appear eight times. Turning the option off shows each input atom once per repeated cell at its
original position plus the cell translation. Repetition controls expand the display from the original structure without changing
the scientific atom count.

Each ball has its own identity: the source atom (0-based internally, 1-based in the
status bar) and an integer image offset `(na, nb, nc)`. The offset is relative to the
input position. A selected ball's Cartesian position is
`input_position + image_offset @ cell`, with lattice vectors as cell rows.

Delete hides only selected balls, including from POV exports and renders. Other
images of the same atom stay visible. **View ▸ Show All Atoms** restores all hidden
IDs. Hidden IDs survive toggling boundary images off and on. Selection highlights
are viewport overlays and do not appear in the figure.

Undo/redo covers hiding, Show All Atoms, boundary images, repetitions, cell-edge
modes, bond settings, materials, and backgrounds. Consecutive tolerance/radius adjustments merge into one step. Camera navigation,
output settings, file opens, and saves are not undoable. Opening a new file clears
the undo history. A changed camera or output setting still marks the project modified.

## Output framing

The output size is set in **Scene ▸ Render** (width and height, 16 to 8000 pixels,
with aspect presets). A blue frame in the 3D view marks the rendered area; outside it
the view is dimmed. Resizing the window moves the frame on screen but does not change
the image. Projection is orthographic; atoms do not shrink with distance from the
camera. See [output size and frame](rendering.md#output-size-and-frame).

The structure's coordinates, occupancies, and movable flags are scientific data.
Camera, radii, colours, boundary images, hiding, materials, background, and lighting
are presentation state. The GUI offers a small material and background catalog
(**Scene ▸ Appearance**); it has no atom editor, per-atom materials, galleries, or
light editor yet.

## Supercells, bonds, and directions

The **Scene** dock has **Structure**, **Bonds**, **Appearance**, and **Render** tabs. If closed, reopen it from
**View ▸ Scene**. Under Structure, set repetitions along a, b, c (1 to 20),
use **+ all** / **− all**, or reset with **1 × 1 × 1**. Typed counts apply on Enter
or focus change. The view refits after a repetition change. Expansions above 20,000
displayable atoms ask for confirmation before building geometry. Non-periodic axes
are not repeated. Hidden IDs persist across expansion and shrinking.

**Cell edges** offers **All unit cells**, **Outline of the repeated block**,
**Original cell only**, or **None**. The boundary option applies to the repeated block.

Under Bonds, **Show bonds** controls visibility. **Max. length** ranges from 0.80
through 1.50 times the sum of covalent radii; **Radius** ranges from 0.02 through
0.50 Å. Element-pair checkboxes override the default rule: metal–metal pairs start
off in compounds containing non-metals. The pair list reports candidates and length
ranges **per original cell**, not the number drawn in the repeated block. A bond
appears only when both endpoint atoms are displayed; hiding an atom removes its bonds.
These are geometric contacts, not calculated chemical bond orders.

The **View along** toolbar offers **a, b, c** and **x, y, z**. The selected positive
axis points toward the viewer; hold **Shift** when clicking to reverse it. For skewed
cells, lattice directions differ from Cartesian directions. These actions fit the view
and affect the camera only; they are outside the display-setting undo stack.
