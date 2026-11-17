# Proposed manuscript figures

A proposal for the four figures of a *Journal of Applied Crystallography* Computer
Programs article (FR-GALLERY-01). It says which images exist, where they come from, and
which still have to be made.

- **Rendered images** are produced by Ycrystal and POV-Ray with
  `python scripts/make_gallery.py`, from the inputs in `examples/publication/`. See
  the [gallery](../guide/gallery.md), which also has the figure-methods table.
- **Other panels** are explicitly marked as illustrations, screenshots, or plots of
  recorded data.
- **No mock-ups.** No image here is a mock-up of a render.

Each caption separates what is implemented and verified from what is a limitation.

## Figure 1: from a structure file to a ray-traced figure

| Panel | Content | Source | Status |
| --- | --- | --- | --- |
| a | Schematic of the workflow (below) | **Illustration**, to be drawn by the authors | To do |
| b | The Ycrystal window with `srtio3.ycrystal` from the gallery open | Screenshot of the real program on a desktop | To do (needs a display; `scripts/m0_evidence.py` shows how the M0 screenshots were taken) |
| c | The POV-Ray image of the same project | `srtio3.png` from the gallery | Available |

Schematic content, from the architecture:

1. A structure file (CIF, POSCAR/CONTCAR, or Quantum ESPRESSO input) is read with ASE
   and checked: partial occupancy and unsupported settings are refused.
2. One shared geometry (atoms, periodic images, bonds, cell edges, vector arrows) is
   drawn by both the interactive OpenGL view (VTK) and the POV-Ray scene writer.
3. POV-Ray 3.7 renders the final image.
4. Around this core sit the reusable parts:
   - styles (`.ycstyle`) with optional element mapping;
   - view policies;
   - batch manifests;
   - snapshots with provenance records.

**Draft caption.** *Ycrystal's workflow. (a) A structure is read and checked once. The
interactive view and the POV-Ray writer draw the same geometry, so the framing chosen
on screen is the framing of the ray-traced figure. A look designed in the window can
be saved as a style and reused for other structures, also from the command line and in
batch series. Every figure can be saved as a self-contained project with a provenance
record. (b) The window. (c) The POV-Ray image of the project shown in (b).*

**Limitations to state.**
- The interactive view approximates POV-Ray's materials and lighting; only the POV-Ray
  image is final. Background pictures appear in the live view as their average colour
  only.
- Rendering needs a separately installed POV-Ray 3.7.

## Figure 2: lighting and materials, with geometry and camera fixed

| Panel | Image | What changes |
| --- | --- | --- |
| a | `srtio3.png` | Paper style: satin, white background, soft lighting |
| b | `srtio3-cover-light.png` | Only the environment: dark studio, reflective floor, brighter point key light with hard shadows |
| c | `srtio3-cover.png` | Environment and materials: ceramic Sr, chrome Ti, ruby-glass O |

**How (b) and (c) are made.** They are rendered from the snapshot of (a) with
`--style styles/cover.ycstyle`, applying the environment part for (b) and the
appearance and environment parts for (c). A snapshot keeps its camera and image size.
The structure, the camera, and the image size are therefore identical in all three
panels. `tests/test_gallery.py` checks this from the snapshots.

**Draft caption.** *The same SrTiO3 cell, camera, and image size rendered with POV-Ray
3.7 in three looks. (a) A restrained style for a journal page. (b) The same materials
in a dark studio with a reflective floor; the reflections in the floor and the cast
shadows are ray-traced. (c) As (b), with chrome Ti, ruby-glass O, and ceramic Sr:
reflection and refraction are computed by POV-Ray, not painted on.*

**Limitations to state.**
- Materials are a presentation choice. Chrome Ti or glassy O says nothing about the
  physical properties of the atoms.
- Glass and reflections raise the render time a lot: in the
  [benchmark](validation.md#d-render-cost), glass in a studio took about 30 times as
  long as the same scene in satin.

## Figure 3: one style, several compositions, one command

| Panel | Image | Note |
| --- | --- | --- |
| a | `srtio3.png` | Source composition of the style |
| b | `bazro3-mapped.png` | Element mapping Sr → Ba, Ti → Zr; the same physical scale as (a) |
| c | `mgb2.png` | No element settings for Mg or B: background, lighting, size, and default material transfer; a warning records the rest |
| d | `kyanite.png` | A real triclinic (P-1) structure, COD 1008755 (de Rango *et al.*, 1966) |
| e | `afm-synthetic.png` | **Synthetic** two-site cell with hand-assigned moments of ±2.2 μB; not a real material |

**How they are made.** All five figures are rendered by one command,
`ycrystal --batch examples/publication/gallery.json`. Each is saved as a snapshot with
a provenance record, and the gallery script renders every snapshot again after the
inputs are deleted.

**Draft caption.** *One style applied with one command to five structures.
(a) SrTiO3, for which the style was designed. (b) BaZrO3 with an explicit element
mapping, Sr → Ba and Ti → Zr, so that the A and B sites keep their colours; (a) and
(b) share a visible height of 9 Å, so the larger BaZrO3 cell appears larger.
(c) MgB2 receives the style's environment, size, and default material; its elements
keep their default colours. (d) Kyanite, Al₂SiO₅ (P-1; COD 1008755), drawn with its
Al–O (1.81–1.99 Å) and Si–O (1.62–1.64 Å) bonds; polyhedra are not drawn by Ycrystal.
(e) A synthetic antiferromagnetic arrangement (not a
real material) with atom-attached moment arrows.*

**Limitations to state.**
- The element mapping is a presentation choice. It is not a statement of chemical
  equivalence or site correspondence, and nothing is inferred.
- Per-atom settings transfer only to the same structure.
- The command line writes PNG only (PDF and JPEG from the window). The PDF holds a
  raster image, not vector graphics.

## Figure 4: evidence for correctness, cost, and reproducibility

| Panel | Content | Data | Status |
| --- | --- | --- | --- |
| a | A rendered test image with the projected atom centres marked | `tests/test_validation.py`: largest centre error 0.19 px over five structures | Plot to be made from the test; values in [validation](validation.md) |
| b | Render time against displayed atoms and against materials | `validation-results/benchmark-linux-2026-11-17.json` | Plot to be made from the JSON |
| c | Replay of snapshots: pixel differences | `validation-results/replay-check-linux-2026-11-17.json`, the gallery's replay check | Table available (same machine) |

**Draft caption.** *(a) Atom centres found in a POV-Ray image agree with the camera
model to 0.19 px at most, including periodic images, for cubic, hexagonal, and
triclinic cells. (b) The time per figure on a laptop (Intel Core Ultra 5 135U, POV-Ray
3.7.0.10) grows slowly with the number of atoms but strongly with refractive materials.
(c) Snapshots rendered again in a new process, after the original structure and style
files were deleted, gave identical pixels.*

**Limitations to state.**
- All measurements come from one Linux laptop.
- Pixel identity between different machines or POV-Ray builds has not been measured.
  `scripts/replay_check.py` is the method.
- The PNG files of two renders are never byte-identical: POV-Ray stores the render
  time in them.

## Before submission

- Rerun `python scripts/make_gallery.py` with the released version and record the
  version, the commands, and the renderer in the figure-methods table.
- Draw panel 1a and take screenshot 1b. Make plots 4a and 4b from the recorded data
  and state the tool used.
- Measure replays between Linux and macOS with `scripts/replay_check.py`. If they
  differ, report the differences instead of claiming identity.
- Have the [independent evaluation](independent-evaluation.md) done by two real
  evaluators.
- Check the comparison with [other programs](comparison.md) against their current
  versions.
