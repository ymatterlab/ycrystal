# Materials, backgrounds, and lighting

The **Scene ▸ Appearance** tab and the two galleries (**Edit ▸ Material Gallery…**,
**Edit ▸ Environment Gallery…**) control how atoms, bonds, and their surroundings look
in the POV-Ray preview and the rendered PNG. Every change is undoable (Ctrl+Z) and saved
in projects.

The 3D view approximates materials (colour, highlights, and transparency), gradients,
and floors. Shadows, reflections, refraction, clouds, and procedural textures such as
marble appear only in the **POV-Ray preview** (F5) and the render; use the preview to
judge them.

## Choosing materials

A material decides how a surface reacts to light. Colour and material are separate:
the **Colour** column of the element table sets an element's colour, the **Radius**
column its sphere radius in Å, and the **Material** column its material. The **↺**
button returns an element to its default colour and radius (the covalent radius times
the **Atom size** in the Structure tab).

## Choosing colours

Click a colour button (an element's **Colour**, or the background and floor colours)
to open the colour dialog. Choose a colour in one of three ways:

- **Spectrum**: hue from left to right, lightness from top (white) to bottom (black);
  the **Saturation** slider below it makes the colours more vivid or greyer.
- **Named colours**: the 140 CSS colours (silver, steel blue, tomato, …).
- **Type a colour** in any notation; all fields update together:

| Field | Range | Example (red) |
| --- | --- | --- |
| Hex | `#RRGGBB`, any case (also `#RGB`) | `#FF0000` |
| RGB (0–255) | three integers 0–255 | `255 0 0` |
| RGB (0–1) | three fractions, three decimals — the values stored in projects and POV-Ray scenes | `1.000 0.000 0.000` |
| HSV | hue 0–359°, saturation 0–100 %, **value** 0–100 % | `0, 100, 100` |
| HSL | hue 0–359°, saturation 0–100 %, **lightness** 0–100 % | `0, 100, 50` |
| Name or any notation | a CSS name or any of the notations below | `red` |

In the text field, `rgb(255, 0, 0)`, `rgb(100%, 0%, 0%)`, `hsv(0, 100%, 100%)`,
`hsl(0, 100%, 50%)`, and three numbers are accepted. Numbers are never reinterpreted:
integers are 0–255 (`1 0 0` is almost black), numbers written with a decimal point are
fractions 0–1 (`1.0 0 0` is red), and HSV/HSL saturation, value, and lightness are
always percent, with or without `%`. Names ignore case and spaces; "grey" and "gray",
"aqua" (= cyan), and "fuchsia" (= magenta) are accepted. A field completes names as you
type.

Text that cannot be read is explained below the fields, leaves the colour unchanged,
and disables **OK** until it is corrected; valid text that was typed but not yet
confirmed with Enter is applied when you press OK. HSV and HSL show one decimal, so
switching between notations does not drift (each 8-bit channel stays within one step).
For a grey (no hue), the hue you typed is kept so that adding saturation continues from
it. **OK** applies the colour as one undoable step; **Cancel** keeps the old one; the
**↺** button in the element table returns to the default colour and radius.

The dialog works without a mouse: Tab moves between the fields and the named-colour
grid; in the grid, the arrow keys move and Enter or Space chooses. Every field has an
accessible name (for example "HSL lightness in percent") for screen readers.

**Colour names for everyone.** Rest the mouse on the spectrum or a named colour (or move
the keyboard focus in the grid), and the dialog writes that colour in words with its
exact values, for example
*Under the mouse: brown (nearest named colour: chocolate #D2691E) — #C25200 — RGB (194,
82, 0)*. The first part is a plain description from a small vocabulary (red, orange,
yellow, green, cyan, blue, purple, magenta, pink, brown, olive, black, grey, white, with
*dark*, *light*, or *greyish*); the second is the closest CSS named colour by perceived
difference (CIEDE2000). It says *exactly the named colour …* only when the colour equals
it at 8-bit precision, and *nearest named colour …* otherwise; the hex and RGB values are
always the exact ones. Hovering only identifies a colour; clicking chooses it. The chosen
colour is described the same way above the fields, named-colour tooltips read like
*red — #FF0000 — RGB (255, 0, 0)*, and every colour button's tooltip and accessible name
state its colour (*Colour of O: red (nearest named colour: red #FF0000)* with its
values). This helps people with colour-vision deficiencies tell element colours apart;
descriptions are approximate and supplement, not replace, the colours themselves.

The colour of an element is its base colour: it does not change its radius, material, or
opacity. Materials with their own colours (gold, chrome, marble, …) hide it; the colour
button's tooltip then says so, and the colour returns when you choose another material.

Materials are assigned at three levels. The most specific one wins:

1. **Selected atoms** — click atoms (Ctrl+click for several), then
   **Edit ▸ Material for Selection…** (Ctrl+M) or **Material for Selection…** in the
   Appearance tab. Like hiding, this applies to the displayed balls you picked: other
   periodic images of the same atom keep their material.
2. **Element** — the Material column of the element table, or the gallery with
   *Apply to: Element X*.
3. **Default** — the *Default* menu, or the gallery with *Apply to: All atoms*.

*Use Default* (gallery or panel) removes the override of an element or of the selected
atoms; **Clear All** removes every per-atom override. Each half of a bond uses the
material of its atom.

### The material gallery

The gallery shows a thumbnail of every material rendered by POV-Ray in the same scene,
so materials can be compared directly. Type in the search field to filter by name,
description, category, POV-Ray identifier (for example `T_Gold_3C`), or include file
(`metals.inc`). The category menu also offers **★ Favourites**: mark a material with
*Add to favourites*. Favourites are stored for your user account, not in projects.
Double-click a thumbnail or press **Apply**.

Materials marked *own colours* use POV-Ray's built-in pigments (gold, marble, wood…)
and replace the element colour; the gallery says so for each material. The others keep
the element colours.

### Catalog

| Material | Category | POV-Ray declaration | Include files | Colour |
| --- | --- | --- | --- | --- |
| Matte | Scientific finishes | finish | — | element colour |
| Satin (default) | Scientific finishes | finish | — | element colour |
| Glossy | Scientific finishes | finish | — | element colour |
| Ceramic (glazed) | Scientific finishes | finish | — | element colour |
| Plastic | Scientific finishes | finish | — | element colour |
| VMD style (ASE) | Scientific finishes | finish | — | element colour |
| Jmol style (ASE) | Scientific finishes | finish | — | element colour |
| ASE2 style (ASE) | Scientific finishes | finish | — | element colour |
| ASE3 style (ASE) | Scientific finishes | finish | — | element colour |
| Intermediate (ASE) | Scientific finishes | finish | — | element colour |
| Metallic | Metals | finish | — | element colour |
| Polished metal (F_MetalD) | Metals | finish | metals.inc | element colour |
| Soft metal (F_MetalB) | Metals | finish | metals.inc | element colour |
| Gold (T_Gold_3C) | Metals | texture | metals.inc | own colour |
| Silver (T_Silver_3C) | Metals | texture | metals.inc | own colour |
| Copper (T_Copper_3C) | Metals | texture | metals.inc | own colour |
| Brass (T_Brass_3C) | Metals | texture | metals.inc | own colour |
| Bronze (Bright_Bronze) | Metals | texture | textures.inc | own colour |
| Chrome (Polished_Chrome) | Metals | texture | textures.inc | own colour |
| Aluminium (Aluminum) | Metals | texture | textures.inc | own colour |
| Glass (tinted) | Glass and transparent | material (IOR 1.45) | — | element colour |
| Frosted glass | Glass and transparent | material (IOR 1.5) | — | element colour |
| Gem (IOR 2.4) | Glass and transparent | material (IOR 2.42) | — | element colour |
| Clear glass (M_Glass) | Glass and transparent | material | textures.inc | own colour |
| Ruby glass (M_Ruby_Glass) | Glass and transparent | material | textures.inc | own colour |
| White marble (White_Marble) | Decorative textures | pigment | textures.inc | own colour |
| Jade (Jade) | Decorative textures | pigment | textures.inc | own colour |
| Pink granite (Pink_Granite) | Decorative textures | pigment | textures.inc | own colour |
| Stone (T_Stone25) | Decorative textures | texture | colors.inc, stones.inc | own colour |
| Cherry wood (Cherry_Wood) | Decorative textures | pigment | textures.inc | own colour |

The ASE styles use the finish values of ASE's `ase.io.pov` writer. Names in
parentheses are native POV-Ray identifiers. Exported scenes use them unchanged, so
POV-Ray users can recognise and edit them. Scenes that use them `#include` the standard
files listed above (shipped with POV-Ray: `sudo apt install povray-includes` on Linux
Mint); the export says which files are needed and warns if one is missing.

Procedural textures (marble, granite, stone, wood, frosted glass, and the native metals)
are scaled to each atom, so the pattern has the same size on every atom.

### Customizing a material

**Customize Material…** (Appearance tab, or **Edit ▸ Customize Material…**) starts from a
material and adjusts its parameters. Choose **Apply to** (the default material, an
element, or the selected atoms) and **Start from** (the material to vary). The usual
precedence stays: selected atom > element > default, and each half of a bond takes the
material of its atom. A selection is the one at the moment the dialog opens; selecting
other atoms while the dialog is open does not change where the variant goes.

| Start from | Parameters you can change |
| --- | --- |
| Matte, Satin, Glossy, Ceramic | Diffuse amount, specular amount, highlight roughness, reflection amount |
| Plastic | Diffuse amount, specular amount (phong), highlight sharpness (phong size), reflection amount |
| Glass (tinted), Gem | As above, plus glass filter amount and refractive index |
| Frosted glass | As Glass, plus bump strength and bump scale of the frosted relief |
| Marble, Jade, Granite, Stone, Wood | Pattern scale (relative to each atom) |

*Highlight roughness* changes only the size of the highlight; the *bump* values change
the surface relief. The *glass filter amount* says how much light passes through,
tinted by the atom colour; it is not a generic opacity or a measured optical constant.
Materials that use POV-Ray's own definitions (the metals, `M_Glass`, `M_Ruby_Glass`) and
the ASE styles cannot be edited; the dialog explains why and keeps **Apply** disabled.

While you edit, the 3D view and the POV-Ray preview show the variant (the 3D view only
approximates highlight and transparency; check the preview). **Reset to Base** returns
to the values of the material you started from. **Apply** assigns the variant as one
undoable step; **Cancel** restores the previous look and leaves nothing on the undo
stack. A variant leaves the built-in materials unchanged; an untouched variant renders
exactly like its base.

**Save as My Material** keeps the variant in your user settings. It then appears in the
material menus (marked ✎) and in the gallery's category **My materials**, with a POV-Ray
thumbnail when POV-Ray is available (otherwise the base material's thumbnail with a ✎
badge). Every variant has its own id derived from its name and values, so a variant can
never replace a built-in material or another variant. Projects and styles store the full
definition of every variant they use, so they open on another computer without your
personal list, and exported `.pov` files contain the variant's declaration and name.

## Environments

An environment preset sets the background, the floor, and the lighting together. Choose
one from the **Environment** menu or the environment gallery, then adjust each part in
the groups below it; the note under the menu says when the environment was modified.

| Environment | Background | Floor | Lighting | Description |
| --- | --- | --- | --- | --- |
| White | solid | — | Soft | Plain white background. |
| Transparent (PNG alpha) | solid | — | Soft | Transparent PNG; the live view shows light grey. |
| Light grey | solid | — | Soft | Plain light grey background. |
| Dark grey | solid | — | Bright | Dark background, light cell edges, reflection panel. |
| Black | solid | — | Bright | Black background, light cell edges, reflection panel. |
| White to grey gradient | gradient | — | Soft | White at the top to light grey at the bottom. |
| Blue to white gradient | gradient | — | Soft | Soft blue at the top to white at the bottom. |
| White studio (soft shadows) | solid | white | Studio | White matte floor with soft shadows. |
| Grey studio with floor | solid | grey | Studio | Mid-grey floor with soft shadows. |
| Dark studio, reflective floor | solid | dark, reflective | Bright | Floor mirrors the structure; reflection panel. |
| Clear sky | sky | — | Bright | Pale horizon to a blue zenith. |
| Cloudy sky | sky | — | Bright | Blue sky with white clouds. |

Presets with dark backgrounds also switch the cell edges to a light colour.

### Background

**Type** is *Solid colour*, *Vertical gradient* (top and bottom colours), or *Sky*
(zenith and horizon colours, and **Clouds** from 0 to 100 %). Gradients and skies run
from the bottom to the top of the output frame, whatever the orientation of the
structure. **Transparent PNG background** gives rendered images an alpha channel; floors,
gradients, and skies are then left out (transparent glass still lets the alpha through).

### Background picture

Type *Image* shows one of your own pictures behind the structure in the POV-Ray preview
and the rendered PNG. **Choose Image…** imports a PNG or JPEG file (up to 64 MB, 12000
pixels per side, and 50 megapixels); the panel shows its name and pixel size. **Replace…**
swaps the picture and keeps the framing, **Remove** deletes it (the background colour
remains). A file that cannot be read is refused with a message, and the current
background stays. Camera-phone pictures with an EXIF orientation are shown upright.

- **Framing**: *Fill* covers the whole output frame and crops what does not fit (the
  default); *Fit* shows the whole picture, with margins in the **Margin** colour (the
  background colour). The picture keeps its proportions; it is never stretched.
- **Zoom** (10–1000 %) scales the filled or fitted picture about its centre.
  **Horizontal** and **Vertical** move it by percentages of the output frame's width and
  height (positive: right and up). **Brightness** (0–200 %) scales its colours; 100 %
  shows them unchanged. **Reset Framing** returns to Fill, 100 %, centred.
- The picture belongs to the output frame: orbiting or zooming the structure does not
  move it, and the preview and the final PNG show the same composition at any
  resolution. Changing the output's aspect ratio refits it.
- Transparent pixels of a PNG show the margin colour.

The picture is a backdrop, not a light: it does not light the structure, casts no
shadows, and is not seen in reflections (reflective atoms reflect its average colour).
Transparent and refractive materials such as glass show the picture through the atom,
bent by refraction. The 3D view shows the picture's average colour; the POV-Ray preview
is authoritative. A floor covers the picture in the orthographic view: the panel then
says so and offers **Turn Off Floor**. With **Transparent PNG background** the picture
is left out of renders but kept for later. Choosing an environment preset changes the
background type but remembers the picture, so switching back to *Image* restores it.

The picture is copied into the project when you save, so the original file is not needed
afterwards (see [Reusing the look](#reusing-the-look-styles)). **File ▸ Export POV-Ray…**
copies it next to the `.pov` file as `bg_<digest>.png` (or `.jpg`) and refers to it by
that relative name, so the export folder can be moved as a whole.

### Floor

A floor lies below the structure as seen in the frame, tilted slightly towards the
viewer so that it catches shadows (and, with **Reflection**, mirrors the structure).
**Gap below atoms** moves it down from the lowest atom. In the orthographic view the floor
fills the whole background, so the live view simply shows its colour.

### Lighting

| Lighting | Description |
| --- | --- |
| Soft (default) | Upper-left key light with a soft fill; Ycrystal's lighting since the first version. |
| Studio (soft shadows) | Large area key light from the upper left: soft shadows on floors. |
| Bright | Strong key and fill point lights; for dark backgrounds and skies. |
| Dramatic side light | Hard key light from the side with a weak fill: strong shading and shadows. |
| Top light | Area light from above: shadows fall straight down onto a floor. |
| Flat (no shadows) | Two even, shadowless lights from the front: low contrast for schematic figures. |

The controls below the preset adjust the **Key light** and **Fill light** intensities,
the key-light direction (**Key azimuth** and **Key elevation**), **Light size**,
**Shadows**, and the **Reflection panel**.

#### How the lights are placed

Lights belong to the image, not to the crystal: they are placed relative to the output
camera, so the key light always comes from the same side of the image while you orbit,
roll, or pan.

- **Origin:** the camera's focal point *F*, the point at the centre of the image.
- **Key azimuth:** 0° points from *F* straight toward the camera (a light from the
  viewer's position); positive values turn to the right of the image, negative to the
  left; ±180° is behind the structure. The presets use −20° to −65° (upper left).
- **Key elevation:** degrees above the image's horizontal, toward the top of the image;
  −30° to 89°. When you roll the camera, the horizontal rolls with the image.
- **Distance:** both lights sit at the same distance from *F*: 4 *R* + |*C* − *F*| +
  10 Å, where *C* and *R* are the centre and radius of a sphere around the displayed
  atoms and cell edges (boundary atoms and repeated cells included, hidden atoms left
  out). Zooming or changing the output size does not move the lights; panning away from
  the structure moves them a little further out. Light does not get weaker with
  distance, so the distance changes the direction of shadows slightly, not the
  brightness.
- **Fill light:** a fixed direction at the lower right, in front of the structure
  (azimuth +35°, elevation −11.6° in the same convention). It never casts shadows; only
  its intensity can be changed.
- **Intensities** are the brightness of white light (POV-Ray `color rgb`); 0 switches a
  light off.
- **Light size:** 0 is a point light with sharp shadows. A larger value makes the key
  light a round area light whose *diameter* is the value times the scene radius *R*
  (0.5 on a structure with *R* = 4.4 Å gives a light 2.2 Å across). POV-Ray turns the
  round light toward each point it lights, so it behaves like a glowing ball of that
  size. Shadows are sampled from a 5 × 5 grid of points on the light, refined
  adaptively where a shadow edge needs it.
- **Reflection panel:** an invisible bright disc on the key-light side of the structure
  that only appears in reflections, so that metals and glass do not look black on dark
  backgrounds. It is not a light source and does not light anything.

#### Lighting Setup window

**Lighting Setup…** (below the lighting controls, or **View ▸ Lighting Setup…**) opens a
3D overview of the lights, the output camera, and a lightweight copy of the displayed
structure:

- orange sphere: the key light; blue cube: the fill light; both with labels and guide
  lines from *F*;
- black cross: *F*; purple octahedron: *C*;
- grey cone and line: the output camera's viewing direction (its distance does not
  matter for an orthographic image); blue rectangle: the output frame;
- grey ring: the horizontal circle at the light distance, with the azimuth and elevation
  arcs of the key light;
- wire sphere: the area-light diameter, when the light size is not 0; white disc: the
  reflection panel, when it is on.

Drag the orange key-light sphere to change azimuth and elevation together, or the flat
orange disc on the ring to change only the azimuth. The angles are always measured in
the output camera's frame, whichever way you have turned the overview, and they snap to
whole degrees like the spin boxes. While you drag, the live view, the spin boxes, and
the overview follow; releasing the button applies the change as one undoable step (and
starts the automatic preview if it is on). Esc or the right mouse button cancels the
drag and restores the previous direction. Elsewhere in the overview, drag to orbit,
Shift-drag or middle-drag to pan, and use the wheel to zoom; this never changes the
image. **Reset Overview** fits the overview again. The window also has azimuth and
elevation spin boxes for the keyboard and a read-out of the resolved values.

#### What the live view shows

The live view uses the key and fill lights at their real positions and intensities
(without distance fall-off), so the shading direction matches the POV-Ray image. It
does not show shadows, the softness of area lights, reflections, refraction, or the
reflection panel; check those in the POV-Ray preview. The live view's shading is an
approximation and is not expected to match the POV-Ray image pixel for pixel.

Area lights (Studio, Top) soften shadows at little cost for opaque materials, but make
transparent materials much slower to render, because POV-Ray traces shadow rays through
the glass. While composing a glass figure, use *Soft* or *Bright* lighting or switch off
*Update automatically* in the preview dock.

## Reusing the look: styles

Materials, colours, radii, the environment, and the lighting are saved in projects
(`.ycrystal`, schema 8) and restored exactly when the project is reopened. Projects
saved by earlier versions open with their original appearance. A project or style with
a background picture is saved as a ZIP package that contains the picture (the suffix
stays `.ycrystal` or `.ycstyle`); others remain a single JSON file. Ycrystal recognises
both forms by their content. Damaged or unsafe packages, and packages that miss their
picture, are refused with a message and nothing changes. Ycrystal 0.2.0 and older cannot
open schema-6 or later projects or packages.

Figures that belong together (in one paper, poster, or talk) should look alike: the
same background, lighting, image size, and materials. A **style** keeps that look apart
from any structure, so you design it once and reuse it. **File ▸ Export Style…** writes
a `.ycstyle` file, and **File ▸ Import Style…** applies one to the open structure.
The import dialog lets you choose the parts to apply:

| Part | Contents |
| --- | --- |
| Materials, colours, and radii | Default material; material, colour, and radius of each element; the appearance of vector arrows (never the vectors themselves); the [element legend](rendering.md#element-legend) |
| Display | Atom size, repetitions, boundary atoms, cell edges, bond length, radius, and pair rules |
| Environment | Background (including a background picture), floor, lighting, transparency, and the cell-edge colour |
| Output image size | Width and height in pixels |

A style never changes the structure's coordinates, and it has no camera. The import is
one undoable step. Settings that refer to something the new structure does not have are
left out, and a message lists them:

- Element settings (material, colour, radius) and bond-pair rules apply to the elements
  the structure contains; those of other elements are left out, unless you map them
  (see [element mapping](#element-mapping-a-style-for-another-composition)).
- Per-atom materials and hidden atoms refer to individual atoms of the original
  structure. They are applied only if the new structure has the same number of atoms
  with the same element at every position (for example the same structure from another
  file, or relaxed); otherwise they are left out.
- Repetitions that would display more than 20,000 atoms ask for confirmation first.

A style can also be applied without a window, for example to render many structures
with the same look from a script: `ycrystal FILE --style STYLE.ycstyle --render OUT.png`
(see [styles from the command line](examples.md#apply-a-style-from-the-command-line)).
There, the display part is left out unless you ask for it.

### Element mapping: a style for another composition

Element settings in a style are stored by element symbol. That works for the same
compound, but not for a related one: a style made for SrTiO3 has settings for Sr, Ti,
and O, and applied to BaZrO3 only the O settings find their element. Yet the two
perovskites have the same structure, with Ba where Sr is and Zr where Ti is, and a
series of figures is easiest to compare when corresponding atoms look the same. An
element mapping states that correspondence for drawing: give the Ti settings (for
example chrome) to Zr, and the Sr settings to Ba. Map the elements while importing:

- **In the window:** the Import Style dialog lists every element the style has
  settings for, under **Element settings go to**, with the element of the open
  structure that receives them. Each row starts at the same symbol, or **Do not
  transfer** if the structure does not contain it, so pressing **Apply** without
  changing anything works as before. Choose another element of the structure for a
  row, or **Do not transfer** to leave its settings out. **Match Symbols** returns to
  the start. Below the rows the dialog shows what will be applied and what is left out
  (for example `Element settings applied: O, Sr → Ba, Ti → Zr.`) before you press
  **Apply**. The import stays one undoable step.
- **From the command line:** `--element-map Sr=Ba,Ti=Zr`, with `O=-` to leave the
  settings of O out (see
  [styles from the command line](examples.md#apply-a-style-from-the-command-line)).

The mapping moves the element materials, colours, and radii, and the bond-pair rules
(an O–Ti rule becomes O–Zr). Elements you do not map keep matching by symbol. The
choices must be unambiguous, or Ycrystal refuses them and says why:

- Each element of the structure receives the settings of one element at most:
  mapping both Sr and Ti to Ba is refused.
- If the style also has settings for the target element itself, mapping another
  element onto it is refused (Ti → O when the style has O settings). Map O elsewhere,
  or leave its settings out, to make the choice explicit.
- Targets must be elements of the open structure; symbols are case-sensitive (`Zr`,
  not `ZR`).
- An element mapped elsewhere does not also keep its own settings: with Sr → Ti in a
  structure that contains Sr, the Sr atoms get no Sr settings (a note says so).

The mapping is a **presentation choice**: it decides which colours and materials an
element is drawn with. It does not claim chemical equivalence or that the sites of the
two structures correspond, and it never changes atoms, element labels, coordinates,
vectors, or which bonds exist. Per-atom materials and hidden atoms still transfer only
to the same structure, mapping or not. The mapping is not stored in the style file;
saving the project keeps the resulting appearance.
