# Scientific validation and benchmarks

Evidence for the claims a paper about Ycrystal would make (FR-VALIDATION-01): what was
tested, how, with which tolerance, and what was observed. Everything here was measured
by running the named tests and scripts; anything not run is marked **unverified**,
with the command that would run it. A reading of the source code is not counted as
validation.

All measurements below were made on 17 November 2026 on one machine: a Linux Mint 22.1
laptop with an Intel Core Ultra 5 135U (14 logical CPUs, 7.2 GiB of memory), Python 3.12.3, and
POV-Ray 3.7.0.10 from the distribution package. They were not repeated on macOS, on
Windows, or with another POV-Ray build.

## Questions and status

| Question | Answer from the evidence | Status |
| --- | --- | --- |
| A. Does the POV-Ray scene, and the ray-traced image, show the structure where it is (atoms, periodic images, bonds, cell, vectors, projection, handedness), with nothing cut off? | Yes, within the tolerances below, for every fixture tested | Verified on Linux; macOS unverified |
| B. Can one style be applied to different materials without changing their scientific data? | Yes: no coordinate, cell, element, label, occupancy, flag, or vector changed, for 8 inputs × 2 sets of style parts | Verified (no renderer involved) |
| C. Do snapshots give the same figure again, in a new session and on other installations? | Same machine: the same scene exactly and identical pixels (tests, and 9 of 9 benchmark figures), also in a new process with the sources deleted. Other installations: not yet measured | Same machine verified; **other machines unverified** |
| D. How much time and memory do modest, medium, and large figures take? | See [render cost](#d-render-cost) for this laptop | Measured on Linux only; macOS unverified |
| E. Are the ray-traced effects real: shadows, soft shadows, reflection, refraction? | Yes, each measured as a property of the image | Verified on Linux |

## Test structures

Small input files written for this project (MIT licence); see `tests/fixtures/README.md`.

| Structure | Kind | Used for |
| --- | --- | --- |
| SrTiO3, Pm-3m, `tests/fixtures/SrTiO3.cif` (also `.vasp`, `.pw.in`) | Real compound, rounded textbook constant (a = 3.905 Å) | Cubic cell with boundary images, styles, effects |
| BaZrO3, Pm-3m, `tests/fixtures/BaZrO3.cif` | Real compound, rounded constant (a = 4.19 Å), for demonstration | Second perovskite for element mapping (Ti → Zr) |
| MgB2, P6/mmm, `tests/fixtures/MgB2.cif` (also `.vasp`, `.pw.in`) | Real compound, rounded constants | Hexagonal cell |
| Triclinic P1, `tests/fixtures/triclinic.cif` | **Synthetic**: invented cell and atoms | Low symmetry, skewed axes |
| Antiferromagnet, `examples/vectors-synthetic-afm.ycrystal` | **Synthetic**: not a real material; ±2.2 μB assigned by hand | Atom-attached vectors |
| Si, diamond, `tests/fixtures/Si_conventional.cif` | Real compound, rounded constant | Style transfer |

## A. Geometry, from the scene file to the image

The live view and the POV-Ray writer draw one shared geometry
(`DisplayGeometry`). The checks go in three steps:

1. The geometry is right.
2. The scene file for POV-Ray holds exactly that geometry.
3. POV-Ray draws it where the camera model says.

| Check | Test (`tests/…`) | Tolerance | Observed |
| --- | --- | --- | --- |
| Periodic images are exact lattice translations of their source atoms and lie inside the displayed cells | `test_validation.py::test_periodic_images_are_exact_lattice_translations` (5 structures) | 1e-9 Å | Pass |
| The scene file has one sphere per displayed atom with its position, radius, element, and image; each bond as one cylinder or two halves between the atom centres; cell edges between lattice points along a lattice vector | `test_validation.py::test_pov_scene_holds_exactly_the_shared_geometry` (5) | 5e-7 Å (the file has 6 decimals) | Pass |
| Looking down a, b, or c, the other two lattice vectors turn counter-clockwise on screen (no mirror image), and the named axis faces the viewer | `test_validation.py::test_lattice_views_keep_the_cell_right_handed_on_screen` (3 cells × 3 axes) | Exact sign | Pass |
| Every displayed image of an atom carries its source's vector: parallel, same sign, centred, of the set length | `test_validation.py::test_vectors_keep_attachment_direction_and_sign_in_every_image` | 1e-9 | Pass (2 × 2 × 2 cells, 35 arrows) |
| **Rendered** atoms and periodic images: every sphere found, at the projected centre, of the projected size, with the right colour; the mirror image does not match | `test_validation.py::test_rendered_atoms_and_periodic_images_follow_the_camera_model` (SrTiO3, SrTiO3 2 × 2 × 1, MgB2 2 × 2 × 1, triclinic 2 × 1 × 1, BaZrO3) | Centre 0.5 px; area 8 %; mirror > 5 px | Largest centre error 0.19 px (others 0.08–0.16); largest area error 3.5 %; mirror errors 51–119 px; 10 to 42 spheres each |
| **Rendered** bonds: at ¼ and ¾ of each bond the pixel is opaque and has the colour of the atom of that half | `test_validation.py::test_rendered_half_bonds_join_their_own_atoms` (3) | Dominant colour channel | All samples not hidden by an atom: 16 (SrTiO3, 30 bonds), 16 (MgB2, 8 bonds), 4 (triclinic, 2 bonds) |
| **Rendered** vector arrows: arrow colour near each projected head; no arrow colour outside the projected arrows | `test_validation.py::test_rendered_vector_arrows_follow_the_shared_geometry` | ±2 px around the head point | 22 of 22 heads |
| **Rendered** fitted views are never cut off: transparent border on all four sides, drawn extent inside the projected framing bounds (equal to them without arrows), landscape and portrait | `test_validation.py::test_fitted_views_are_not_clipped_in_the_render` (4 scenes × 2 shapes) | 1.5 px | Border pixels transparent in all 8; drawn extent within 0.76 px of the bounds without arrows; with arrows up to 4.5 px inside them (the arrow bounds are conservative); nearest border 8 px |
| Synthetic arrangement, rotated, rolled, panned view; mirrored and shifted controls | `test_render_alignment.py` (existing) | 1 px | Pass |
| Camera model equal to VTK's matrices; fitted views never clip; arrows included in the framing | `test_camera.py` (existing) | 1e-9 | Pass |

**Why these tolerances.**
- *Sphere centres, 0.5 px.* The centroid of a disc found in the image is its centre to
  well below a pixel, even with anti-aliasing. Half a pixel is far smaller than any
  visible misplacement, and twice the largest error observed.
- *Disc areas, 8 %.* An edge pixel counts as inside when its alpha is ≥ 128. For the
  smallest discs (radius about 4 px) that changes the area by several per cent.
- *Bounds, 1.5 px.* The drawn extent is quantised to whole pixels (up to 1 px), and
  anti-aliasing may leave a barely covered edge pixel transparent.
- *Analytic checks.* These use the precision of the numbers involved: 1e-9 Å in
  memory, 5e-7 Å in the scene file.

Views for the image checks are chosen from the camera model alone. The test searches a
fixed 10° grid of orientations for the one where projected atoms are farthest apart,
then requires every atom to be visible (a gap of more than 4 px between discs). The
render then shows whether POV-Ray agrees.

## B. Styles do not change the science

`test_validation.py::test_styles_never_change_the_scientific_data` applies
`examples/grey-studio.ycstyle` to 8 inputs:

- SrTiO3 as CIF and as POSCAR with selective dynamics;
- BaZrO3 with the element mapping Ti → Zr;
- MgB2 as CIF and as Quantum ESPRESSO input;
- the triclinic cell;
- silicon;
- the vector project.

It does this with the default command-line parts and with all four parts. The test
then checks:

- **Data unchanged.** Cell, positions, atomic numbers, labels, periodicity, occupancy,
  movable flags, import record (except the time of reading), and vectors are identical
  to a separately read copy.
- **Input object untouched.** The input object itself is unchanged.
- **Same atoms drawn.** Without the display part, the same atoms are drawn at the same
  positions.
- **Files untouched.** Neither the input nor the style file is written.

All 16 cases pass.

Related existing tests:
- `test_style.py`: transfer rules, element mapping, packaged styles;
- `test_release.py`: command line;
- `test_batch_manifest.py`: a real POV-Ray series with inputs unchanged byte for byte;
- `test_camera.py`: view policies.

## C. Snapshots give the same figure again

Same machine, verified (`tests/test_reproducibility.py`, FR-REPRO-01):

- **Same scene.** The replayed scene file is identical except for its date line, for:
  - styles with element mapping;
  - fixed, fitted, and saved cameras;
  - vectors;
  - a background picture;
  - a custom material.
- **Identical pixels.** Real POV-Ray replays had identical pixels: the tests allow 1 of
  255 per channel, and every replay had a difference of 0. This held:
  - after the structure, style, and picture were deleted;
  - in a new process with an empty home folder;
  - for three batch jobs.
- **PNG bytes always differ.** POV-Ray writes the render time into the file, so a
  replay never has the original's SHA-256.

Other installations: **unverified.** To measure them:

```bash
# On machine A: renders the benchmark cases once and saves their snapshots.
python scripts/benchmark_render.py --quick --scale 0.5 --repeats 3 --out bench-A
# Copy bench-A/snapshots to machine B, then on machine B:
python scripts/replay_check.py bench-A/snapshots --out replay-on-B
```

`replay_check.py` first checks the recorded SHA-256 of every reference image and
snapshot. It then renders each snapshot with the production command line and reports
per figure:
- the largest and the mean difference per 8-bit channel;
- the fraction of pixels beyond the tolerance;
- both systems and POV-Ray versions.

The result is written to `replay-check.json`. As a control, the check was run on the
same laptop with the snapshots of the benchmark run below. All 9 figures had identical
pixels (largest difference 0), including glass, chrome, and the studio's area-light
shadows; see [results](#results-files).

## D. Render cost

`scripts/benchmark_render.py` times the production command (`ycrystal INPUT --render
OUT.png --width W --height H`), each run in a new process.

- **Warm-up.** One untimed run per case, which also saves the snapshot for question C.
- **Timed runs.** Then the timed repeats.
- **Reported.** The median, minimum, and maximum of:
  - the wall time of the whole command;
  - the render time that `ycrystal` prints (0.1 s resolution);
  - the peak resident memory of the largest process, the Python process or POV-Ray,
    from `wait4`, read by a small launcher process. On Linux, a child's peak memory also
    counts the size of the process that started it, so measuring from the benchmark
    process itself would report that process's size. The first recorded attempt did
    exactly that and was discarded. On Linux it was verified that the launcher reports
    a 200 MB grandchild (199.9 MiB) and not a 300 MB benchmark process (11.2 MiB for a
    trivial command). The launcher's own size, about 10 MiB, is the smallest value it
    can report. On macOS this is unverified.
- **Not controlled.** CPU frequency scaling, other programs, and the thermal state.
  POV-Ray uses every core.

Results on the laptop: `benchmark_render.py --quick --scale 0.5 --repeats 3`, so
1 warm-up and 3 timed runs per case, at half the default image sizes. Raw data:
[results files](#results-files).

| Case | Displayed atoms | Bonds | Image (px) | Wall time, s: median (min–max) | Printed render time, s (median) | Peak memory, MiB (median) |
| --- | --- | --- | --- | --- | --- | --- |
| `srtio3-1`: SrTiO3 1×1×1, satin, white | 15 | 30 | 400 × 300 | 1.68 (1.65–1.71) | 1.4 | 71.5 |
| `srtio3-4`: SrTiO3 4×4×4, satin, white | 429 | 1,344 | 400 × 300 | 1.93 (1.91–1.98) | 1.6 | 72.3 |
| `srtio3-8`: SrTiO3 8×8×8, satin, white | 2,969 | 9,984 | 400 × 300 | 2.57 (2.48–2.59) | 2.2 | 79.2 |
| `srtio3-4-small`: SrTiO3 4×4×4, satin, white | 429 | 1,344 | 200 × 150 | 1.78 (1.77–1.80) | 1.5 | 72.5 |
| `effects-plain`: SrTiO3 2×2×2, satin, white | 71 | 192 | 400 × 300 | 1.74 (1.74–1.77) | 1.4 | 71.6 |
| `effects-studio`: SrTiO3 2×2×2, satin, studio (floor, area light, soft shadows) | 71 | 192 | 400 × 300 | 2.21 (2.19–2.27) | 1.9 | 71.6 |
| `effects-chrome`: SrTiO3 2×2×2, chrome (reflection), studio | 71 | 192 | 400 × 300 | 3.39 (3.38–3.44) | 3.1 | 71.4 |
| `effects-glass`: SrTiO3 2×2×2, glass (refraction), studio | 71 | 192 | 400 × 300 | 65.48 (56.21–74.95) | 65.1 | 71.5 |
| `mgb2-style`: MgB2 with --style grey-studio.ycstyle | 10 | 1 | 400 × 300 | 2.05 (2.03–2.06) | 1.1 | 85.0 |

What the numbers show, for this laptop only:

- **Atom count.** From 15 to 2,969 displayed atoms (9,984 bonds), the whole command
  takes 1.7 to 2.6 s at 400 × 300 px. A fixed cost dominates: Python start-up, reading
  the input, and POV-Ray's start-up and parsing, about 1.4 s of the printed render time
  even for 15 atoms.
- **Image size.** Halving the image size (`srtio3-4-small`) saves only 0.15 s at this
  scale.
- **Effects.**
  - The studio (floor, area light, soft shadows) adds about 0.5 s to the plain scene.
  - In the same studio, chrome (reflection) instead of satin adds about 1.2 s.
  - **Glass (refraction) in the studio takes about 65 s**, some 30 times the satin
    studio scene. Its runs also vary most (56–75 s). The cause was not investigated;
    the laptop may lower its clock under long full load.
- **Memory.** The largest process of each command used 71–85 MiB. The measurement
  does not say whether that was the Python process or POV-Ray.
- **Larger cases not run.** The 12 × 12 × 12 case and 1600 × 1200 images were not run
  (too heavy for this laptop). In an interrupted trial at 800 × 600, process listings
  showed single renders of about 3 min for SrTiO3 12 × 12 × 12 and more than 3.5 min
  for the glass studio scene. These are rough observations, not recorded results.

**Caveats.**
- **Settings dominate the cost.** Render time depends on the image size, the materials
  (glass refracts and chrome reflects, so each ray spawns more rays), area lights
  (5 × 5 samples with adaptive refinement), floors and shadows, and the hardware.
- **Not an estimate for other figures.** These numbers describe these cases on this
  laptop, nothing more.
- **Not run here.** The full default set at 800 × 600, with 1 + 5 runs per case, takes
  far longer on this laptop and was **not run**. The command for a faster machine:
  `python scripts/benchmark_render.py --out bench-full`.

## E. Ray-traced effects

`test_validation.py::test_cast_shadows_and_soft_shadows_of_area_lights` and
`::test_polished_metal_reflects_and_glass_transmits` render SrTiO3. Each comparison
changes exactly one setting, with the same geometry and camera.

| Effect | Measurement | Required | Observed |
| --- | --- | --- | --- |
| Cast shadows (studio: floor and area key light) | Fraction of pixels darker by more than 15 of 255 than with shadows off | > 5 % | 20.4 % |
| Soft shadows of the area light | Fraction of shadow pixels between 20 % and 80 % of the full darkening, area light vs point light | Area > point + 0.05 | 0.46 vs 0.31 |
| Polished metal reflects a red floor | Red excess (red minus the mean of green and blue) in the lower part of each grey sphere | Chrome > 30; matte and satin < 5 | Chrome 84–124; matte 0.0; satin 0.0 |
| Glass transmits a blue background | Blue excess in the centre of each grey sphere | Glass > 20; satin < 5 | Glass 49–78; satin 0.0 |

The existing tests add:
- glass showing a background picture (`test_background_image.py`);
- custom material parameters changing the image (`test_custom_materials.py`);
- vector arrows (`test_vectors.py`).

## Reproduce

```bash
# A, B, E (and C on one machine): about 70 s on the laptop.
.venv/bin/python -m pytest tests/test_validation.py tests/test_reproducibility.py tests/test_validation_scripts.py -q
# The observed values above, as JUnit XML properties:
.venv/bin/python -m pytest tests/test_validation.py -o junit_family=legacy --junitxml=validation.xml
# D and the reference set for C:
.venv/bin/python scripts/benchmark_render.py --quick --scale 0.5 --repeats 3 --out bench
.venv/bin/python scripts/replay_check.py bench/snapshots --out replay
```

Tests that need POV-Ray are skipped without it, unless `YCRYSTAL_REQUIRE_INTEGRATION=1`
is set, which makes them fail instead.

## Results files

The raw, machine-readable results of the runs reported here, unedited (they contain no
paths, user names, or host names):

- [`validation-results/benchmark-linux-2026-11-17.json`](validation-results/benchmark-linux-2026-11-17.json):
  `benchmark_render.py --quick --scale 0.5 --repeats 3` on the laptop (every run,
  inputs and their SHA-256, system);
- [`validation-results/replay-check-linux-2026-11-17.json`](validation-results/replay-check-linux-2026-11-17.json):
  `replay_check.py` of that run's snapshots on the same laptop. This is the control
  experiment; checks between different machines are still to be run.

The images, snapshots, and generated inputs of the run stay outside Git (in
`artifacts/validation/`, which is ignored). Rerun the commands above to regenerate
them.

## Limitations and unsupported input

- **Platforms.** Everything here was measured on one Linux laptop. Unverified:
  - macOS (the CI job runs the tests without windows and with real POV-Ray, but not
    the benchmark);
  - Windows (the validation tests pass there with POV-Ray for Windows on one laptop,
    18 November 2026, but the benchmark and the replay check were not run);
  - other POV-Ray builds;
  - pixel differences between machines.
- **Not checked by hand.** These checks are automated and involve no window. Hands-on
  use of the window is listed in [HANDOFF.md](../HANDOFF.md).
- **Unsupported input.** Refused rather than drawn:
  - CIF files with partial occupancy or overlapping sites;
  - Quantum ESPRESSO input with `ibrav` other than 0 or `crystal_sg` positions.

  VASP 4 files need the elements: the window asks for them, and the command line
  refuses the file. See [supported formats](../FORMATS.md).
- **Not vector graphics.** The PDF export holds a raster image.
- **The test structures are small** (5 to 42 atoms in the image checks). Large scenes
  are covered by the benchmark only, for cost, not for correctness.
- **Comparison with other programs.** See [the comparison](comparison.md). It rests on
  their documentation only; none of them was run.
- **Independent users.** The [evaluation checklist](independent-evaluation.md) is
  prepared; no evaluation has taken place.
