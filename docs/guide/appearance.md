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
the key-light direction (**Key azimuth**: degrees to the right, negative to the left;
**Key elevation**: degrees above the horizontal), **Light size** (an area light, in
multiples of the scene radius; 0 is a point light with sharp shadows), **Shadows**,
and the **Reflection panel**: an invisible bright panel near the key light that only
appears in reflections, so that metals and glass do not look black on dark
backgrounds. Lights move with the view: the key light always comes from the same side
of the image.

Area lights (Studio, Top) soften shadows at little cost for opaque materials, but make
transparent materials much slower to render, because POV-Ray traces shadow rays through
the glass. While composing a glass figure, use *Soft* or *Bright* lighting or switch off
*Update automatically* in the preview dock.

## Reusing the look: styles

Materials, colours, radii, the environment, and the lighting are saved in projects
(`.ycrystal`, schema 5) and restored exactly when the project is reopened. Projects
saved by earlier versions open with their original appearance.

To give another structure the same look, save a **style**: **File ▸ Export Style…**
writes a `.ycstyle` file, and **File ▸ Import Style…** applies one to the open structure.
The import dialog lets you choose the parts to apply:

| Part | Contents |
| --- | --- |
| Materials, colours, and radii | Default material; material, colour, and radius of each element |
| Display | Atom size, repetitions, boundary atoms, cell edges, bond length, radius, and pair rules |
| Environment | Background, floor, lighting, transparency, and the cell-edge colour |
| Output image size | Width and height in pixels |

A style never changes the structure's coordinates, and it has no camera. The import is
one undoable step. Settings that refer to something the new structure does not have are
left out, and a message lists them:

- Element settings (material, colour, radius) and bond-pair rules apply to the elements
  the structure contains; those of other elements are left out.
- Per-atom materials and hidden atoms refer to individual atoms of the original
  structure. They are applied only if the new structure has the same number of atoms
  with the same element at every position (for example the same structure from another
  file, or relaxed); otherwise they are left out.
- Repetitions that would display more than 20,000 atoms ask for confirmation first.
