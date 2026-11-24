# Controls and display

Use the mouse and view shortcuts over the 3D viewport. VTK's default keys such as
`q` (quit) and `w` (wireframe) are disabled. **Help ▸ Mouse Controls** (F1) opens
the in-app summary.

| Input | Action |
| --- | --- |
| Left drag | Orbit about the view centre (or turn about the chosen axis, see below) |
| Middle drag or Shift + left drag | Pan |
| Wheel or right drag | Zoom |
| F / toolbar Fit | Fit the displayed geometry, preserving orientation |
| View ▸ Reset View | Restore the default orientation and fit |
| Left click without dragging | Select the front-most ball; empty space clears |
| Ctrl + click | Add/remove a ball from the selection |
| Esc | Clear selection (in a measurement mode: cancel the incomplete measurement) |
| **Distance** / **Bond angle** (View along toolbar, Edit menu) | Measure between clicked atoms; see [Measurements](#measurements) |
| **Edit ▸ Vectors…** | Attach direction or magnetic-moment arrows to atoms; see [Vectors](#vectors-arrows-on-atoms) |
| Delete or Backspace | Hide selected displayed atoms |
| Ctrl+M | Material for the selected atoms (Edit ▸ Material for Selection…) |
| Drag an **a**, **b**, or **c** handle | Add or remove whole cells along that axis |
| Esc or right button during a handle drag | Cancel the drag |
| Drag a light handle in **Lighting Setup** | Set the key-light direction (one undo step; Esc cancels) |
| Ctrl+Left / Ctrl+Right | Turn by the step angle about the rotation axis |
| Ctrl+Z | Undo a display-setting change |
| Ctrl+Shift+Z or Ctrl+Y | Redo a display-setting change |
| Ctrl+O | Open a structure or project |
| Ctrl+S / Ctrl+Shift+S | Save Project / Save Project As… |
| F5 | POV-Ray preview of the framed view |
| Ctrl+R | Render Image… as PNG, PDF, or JPEG (toolbar **Cancel Render** stops it) |
| Ctrl+Q | Quit (asks about unsaved changes) |

On macOS, read **Ctrl** as **⌘** (Command) throughout: ⌘ + click toggles the
selection (Control + click is a right click there), ⌘Z undoes, ⌘R renders. The
function keys F1 and F5 may need the Fn key, depending on the keyboard settings. A
mouse or trackpad without a middle button pans with Shift + left drag.

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

Undo/redo covers every change to the figure: hiding, Show All Atoms, boundary images,
repetitions (including handle drags), cell-edge modes, bond settings, atom size and
element radii, materials (default, element, and atom), element colours, environments,
backgrounds, floors, lighting, the output size, and style imports. A handle drag or a
style import is one step; consecutive spin-box adjustments of the same value merge into
one step. Camera navigation (orbit, pan, zoom, rotation, view directions) is not on the
undo stack; **View ▸ Reset View** returns to the default orientation. File opens and
saves are not undoable; opening a new file clears the undo history. A changed camera
still marks the project modified. The aspect-ratio lock in the Render tab is saved in
projects but is not an undo step; see [lock aspect ratio](rendering.md#lock-aspect-ratio).

## Output framing

The output size is set in **Scene ▸ Render** (width and height, 16 to 8000 pixels,
with aspect presets). A blue frame in the 3D view marks the rendered area; outside it
the view is dimmed. Resizing the window moves the frame on screen but does not change
the image. Projection is orthographic; atoms do not shrink with distance from the
camera. See [output size and frame](rendering.md#output-size-and-frame).

The structure's coordinates, occupancies, and movable flags are scientific data.
Camera, radii, colours, boundary images, hiding, materials, background, and lighting
are presentation state; see
[Materials, backgrounds, and lighting](appearance.md) for the **Scene ▸ Appearance**
tab and the galleries. There is no atom editor.

## Supercells, bonds, and directions

The **Scene** dock has **Structure**, **Bonds**, **Appearance**, **Legend** (the
[element legend](rendering.md#element-legend)), and **Render** tabs. If closed, reopen
it from
**View ▸ Scene**. Under Structure, set repetitions along a, b, c (1 to 20),
use **+ all** / **− all**, or reset with **1 × 1 × 1**. Typed counts apply on Enter
or focus change. The view refits after a repetition change. Expansions above 20,000
displayable atoms ask for confirmation before building geometry. Non-periodic axes
are not repeated. Hidden IDs persist across expansion and shrinking. **Atom size** sets
the sphere radius as a multiple of the covalent radius (per-element radii are in the
Appearance tab).

### Supercell handles

Coloured **a** (red), **b** (green), and **c** (blue) handles sit outside the repeated
block, on the line through the centre of its far face along each lattice direction.
Drag a handle outward to add cells along that axis, inward to remove them (at least one
cell remains). While you drag, an orange outline shows the new block and a label gives
the cell counts and the number of atoms; orbiting is disabled. The geometry is rebuilt
when you release the button, as one undoable step; Esc or the right button cancels the
drag. Handles are hidden for non-periodic axes, for structures without a cell, and for
directions that point almost at the viewer (rotate the view to reach them).
**View ▸ Supercell Handles** switches them off. Handles exist only in the live view; they
never appear in exports or renders.

**Cell edges** offers **All unit cells**, **Outline of the repeated block**,
**Original cell only**, or **None**. The boundary option applies to the repeated block.

Under Bonds, **Show bonds** controls visibility. **Max. length** ranges from 0.80
through 1.50 times the sum of covalent radii; **Radius** ranges from 0.02 through
0.50 Å. Element-pair checkboxes override the default rule: metal–metal pairs start
off in compounds containing non-metals. The pair list reports candidates and length
ranges **per original cell**, not the number drawn in the repeated block. A bond
appears only when both endpoint atoms are displayed; hiding an atom removes its bonds.
These are geometric contacts, not calculated chemical bond orders.

To control a specific bond, select two displayed atoms with Ctrl+click. In
**Bond between selected atoms**, choose **Show**, **Hide**, or **Automatic**.
**Show** can draw a connection beyond the automatic distance limit. **Automatic**
restores the distance and element-pair rules. The override applies to the two
selected periodic images and is saved in the project. **Show bonds** controls
visibility for the whole scene.

In **Scene ▸ Polyhedra**, choose **Add…** to select a centre element, ligand
element, and maximum centre–ligand distance in Å. Set the face colour, opacity,
and whether to draw the edges. A polyhedron uses the convex hull of its periodic
ligand positions. It appears when the centre and all of its hull vertices are
displayed. For cubic SrTiO₃, use **Ti** as the centre, **O** as the ligand, and a
cutoff of **2.05 Å**. The rule's checkbox controls its visibility independently
of bonds. Rules are saved with the project and used by the view and POV-Ray.

The **View along** toolbar offers **a, b, c** and **x, y, z**. The selected positive
axis points toward the viewer; hold **Shift** when clicking to reverse it. Screen up is
the first of c, b, a (for x, y, z: z, y, x) that is not parallel to the chosen axis, so
looking down a or b puts c up and looking down c puts b up. **a, b, c are the real-space
lattice vectors**, not normals of lattice planes: in a skewed cell, looking down c is
not the same as looking at the (001) plane face-on, and lattice directions differ from
Cartesian directions. These actions fit the view and affect the camera only; they are
outside the display-setting undo stack. `ycrystal --view` uses exactly the same rule
(see [choose the view](examples.md#choose-the-view-and-framing)).

## Rotation modes

The **Rotate** menu in the View along toolbar chooses how a left drag rotates:

- **freely** (default): trackball rotation in all directions.
- **about a, b, c** (lattice vectors) or **about x, y, z** (Cartesian axes): the
  rotation is restricted to that axis through the view centre. The axis keeps its
  direction on screen while the structure turns around it. Drag across the axis as it
  appears on screen; when the axis points at you, move the mouse in a circle around the
  view centre instead.

The **⟲** and **⟳** buttons (Ctrl+Left, Ctrl+Right) turn by the angle chosen next to
them (5° to 90°) about the rotation axis, or about the line of sight in free mode, for
exact orientations. Clicks still select atoms, and Shift + left drag still pans. Rotation
changes only the view: coordinates are unchanged, and the mode is not saved in projects.
Lattice axes are unavailable for structures without a cell.

## Measurements

**Distance** and **Bond angle** in the View along toolbar (also **Edit ▸ Measure
Distance** and **Edit ▸ Measure Bond Angle**) switch from selecting to measuring. The
two modes exclude each other; click the active button again to return to ordinary
selection. Navigation is unchanged: a drag still orbits, pans, or zooms and never picks
an atom, and only a click without dragging counts.

- **Distance**: click atom A, then atom B. The result is their separation in Å.
- **Bond angle**: click A, then B, then C. The result is the angle A–B–C in degrees
  (0° to 180°) with **B as the vertex**, from the arms A − B and C − B. No bond needs to
  be drawn between the atoms.

The bold text in the status bar says which atom to click next, for example
“Bond angle: select atom B — angle vertex”. The picked atoms get a teal wire cage and a
boxed letter (A, B, or “B vertex”); a dashed line joins them, and an angle shows a small
arc at the vertex. **Esc** cancels an incomplete measurement and removes these marks (a
second Esc clears the ordinary selection); switching modes also cancels it. After a
measurement the mode stays on, so the next click starts a new one. Clicking empty space
keeps the atoms picked so far; clicking the same ball twice in one measurement is
refused with an explanation.

**Which atoms are measured.** Each ball is one displayed instance: a source atom and its
periodic image offset `[na nb nc]` (see [Boundary atoms and hiding](#boundary-atoms-and-hiding)).
Ycrystal measures exactly the instances you click, at `input_position + [na nb nc] @ cell`,
also in supercells, with boundary images, and in non-orthogonal cells. It does **not**
replace them by the nearest periodic image (no minimum-image convention): to measure
across a cell boundary, click the image on the other side. Two images of the same atom
are different balls and can be measured against each other. The values come from the
structure's coordinates and cell only, so the camera, zoom, atom size, materials, and
lighting never change them.

**The Measurements panel** opens at the bottom of the window, under the 3D view, with
the first completed measurement (**View ▸ Measurements** shows or hides it later). Each
row gives the type, the atoms (element, input label, 1-based atom number, and image, e.g.
`A: O #3 [0 0 0] · B (vertex): Ti #2 [0 0 0] · C: O #4 [0 1 0]`), and the result, e.g.
`1.9525 Å` or `90.00° — vertex B`. New measurements are added below the earlier ones.
Distances show four decimals and angles two; the full value is in the tooltip, and the
decimals do not express an uncertainty. **Copy Selected** (or Ctrl+C in the table)
copies the selected rows as text with atoms, units, and the vertex, for example
`Angle A–B–C: 90.00° — vertex B (A = O #3 [0 0 0], B = Ti #2 [0 0 0], C = O #4 [0 0 0])`.
**Remove Selected** and **Clear All** delete rows.

Measurements are inspection data for the current session: they are not saved in
projects, styles, or exports, and the marks never appear in the POV-Ray preview, the
rendered PNG, or the `.pov` file; they do not affect Fit, the lights, or picking.
Opening another structure or project clears all measurements. When a measured ball
disappears from the display (boundary atoms off, fewer repetitions, hiding), the
measurements that use it are removed and the panel says so; the others stay, because
each identity still denotes the same position in the same structure. Undoing the change
does not bring removed measurements back.

## Vectors (arrows on atoms)

**Edit ▸ Vectors…** (or **Vectors…** in the Appearance tab) attaches arrows to atoms, for
example to illustrate a magnetic structure. You enter the vectors yourself; Ycrystal does
not compute, read, or infer magnetic moments.

**What a vector is.** Three Cartesian components in the structure's own right-handed
frame, the frame of the atom positions (not fractional or lattice coordinates, and not a
DFT code's spin axes). The camera never changes them. Each vector has a meaning:

- **Magnetic moment**: components in Bohr magnetons (μB);
- **Direction**: a dimensionless illustration, never presented as a measured moment.

The table shows the components and the modulus. A zero vector is kept as data (modulus 0)
and draws no arrow; vectors with a modulus up to 10⁻⁹ count as zero.

**Attaching.** Select atoms in the 3D view, then **Add/Set for Selection…**. The editor
asks where the vector goes:

- **Selected displayed atom(s) only**: exactly those balls (source atom and periodic
  image), as an *image override*;
- **All periodic images of their source atom(s)**: a *source default* that every image
  of the atom shows, with the same components in every cell.

An image override takes precedence over its source default, and **Suppress on Selected
Images** removes the arrow from chosen balls even if their source has a default. Each ball
shows at most one vector. Atoms of the same element are never grouped: two iron atoms can
carry opposite moments. Ycrystal infers no alternating signs, propagation vector, or
magnetic symmetry, so an antiferromagnetic pattern has to be assigned explicitly (per
source atom, per image, or with a magnetic repeat cell as the structure).

While the editor is open, the 3D view and the POV-Ray preview show the new vector without
an undo step; selecting other atoms does not change the editor's targets. **Apply** is
one undo step (also for many atoms at once), **Cancel** restores the previous state.

The table lists every source default, image override, and suppression with its atom,
image, components, meaning, modulus, and how many displayed balls show it. Choosing rows
selects their balls in the 3D view. **Edit…** changes the components of the chosen rows,
**Reverse** negates them, **Show/Hide** hides arrows without deleting the data, and
**Remove** deletes rows (removing an image override brings back the source default). Each
action is one undo step.

**Arrow appearance** (all arrows): **Placement** *Centred on atom* (the default; the arrow
runs from `r − L u/2` to `r + L u/2`) or *Tail at atom centre* (`r` to `r + L u`), where
`u` is the unit direction and `L` the total length, head included. **Length** is either
*uniform* (`L` in Å for every arrow) or *proportional* (`L` = scale × modulus, with scale
in Å per μB for moments and Å per unit for directions). Switching never changes the
components. Shaft radius, head length and radius, colour, and material (built-in or one
of your custom materials) are separate from the atoms; materials with their own colours
ignore the arrow colour. On short arrows the head takes at most 60 % of the length and
the whole arrow gets thinner in proportion; the length itself is never changed. A short
arrow can be hidden inside its atom: make it longer or the atom smaller.

**In figures.** Arrows are part of the figure: the POV-Ray preview, the PNG, and the
`.pov` file contain them (as a cylinder and a cone each, with a comment naming the atom
and the components), lit and shadowed like the atoms. **Fit** and the render keep whole
arrows in view, including their heads; adding or editing a vector does not move the
camera by itself. The lights stay where they are (they depend on the atoms and cell
only). Arrows are never picked by clicks and do not change measurements, bonds, or atom
counts.

**What happens when the display changes.** Hiding an atom hides its arrow. Fewer
repetitions hide the arrows of images that are no longer displayed, without deleting
their overrides; more repetitions bring them back. Changing atom radii does not change
arrows. Opening another structure starts without vectors.

**Saving.** Projects store all vectors at full precision (since project schema 7), including
suppressions and the arrow appearance, and the definition of a custom arrow material.
Styles carry only the arrow appearance (with the *Materials, colours, and radii* part);
they never transfer vectors to another structure, and importing a style keeps the
current structure's vectors. `examples/vectors-synthetic-afm.ycrystal` shows a small
synthetic two-site cell with opposite moments assigned by hand.
