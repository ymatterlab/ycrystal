# Next tests on the Mac and other computers

An audit, on 17 November 2026, of what has been verified where, and which tests should
run next on the Mac mini, on the Linux laptop by hand, and on a computer that has never
had Ycrystal. Test counts updated on 18 November 2026, after the Windows work (PRs #35
and #36) added tests. It is a plan, not a record: results go to
[PROGRESS.md](../PROGRESS.md), [HANDOFF.md](../HANDOFF.md), and
[validation results](validation.md#results-files) once a test has actually run.

## What is already established

| Evidence | Where | Covers |
| --- | --- | --- |
| CI, Ubuntu 24.04 (every pull request) | Hosted runner, real POV-Ray 3.7 (apt), virtual display (Xvfb) | All 901 tests, GUI tests included, with `YCRYSTAL_REQUIRE_INTEGRATION=1`: 900 passed, 1 skipped (the test of an installed POV-Ray for Windows; PR #36's run, 18 Nov 2026) |
| CI, Windows Server 2022 (every pull request, since PR #36) | Hosted runner, POV-Ray for Windows 3.7 | Tests without windows: 727 passed, 2 skipped (POSIX-only) |
| Windows 11 laptop (18 Nov 2026) | PROGRESS.md, `docs/development/windows-port.md` | Full suite with real windows, 898 passed, 3 skipped by design; the user's hand test |
| CI, macOS 15 arm64 (every pull request) | Hosted runner, real POV-Ray 3.7 (Homebrew) | Tests without windows (728 passed, 1 skipped on 18 Nov 2026; 709 when this audit was written), among them 95 of the 104 POV-Ray tests: validation images, snapshot replays on the same runner, the gallery script at small size. The other 9 POV-Ray tests (preview and release workflow) need a window and run only on Ubuntu and on the Mac by hand |
| Linux laptop runs (Linux Mint 22.1) | `docs/development/validation.md`, PROGRESS.md | Full suite without GUI tests (709 passed); benchmark quick set; same-machine replay check (9 of 9 identical); full-size gallery (7 of 7 identical) |
| Mac mini runs (macOS 15.8, Apple silicon) | PROGRESS.md, up to FR-BATCH-01 (PR #31) | Full suite with real windows, 790 passed at that time |
| The user's hand tests | HANDOFF.md | FR-VECTOR-01, FR-EXPORT-01, FR-REPRO-01 reported working |

## What is not established

1. **The window on a real Mac since PR #31.** Hosted Macs have no GPU for Qt's OpenGL
   widget, so CI never opens a window there. FR-REPRO-01, FR-VALIDATION-01, and
   FR-GALLERY-01 changed no GUI code. Still, the full suite has not run on the Mac
   since they were added: 91 tests are new.
2. **Pixels across machines.** Every replay so far compared renders from one computer.
   Whether a snapshot made on Linux gives the same pixels on the Mac is unknown: POV-Ray
   3.7.0.10 from apt on x86_64 against Homebrew's on arm64. The paper must not claim it
   before this is measured.
3. **Cost on the Mac.** The benchmark has run only on the laptop. Two checks are
   missing:
   - whether its memory figure is correct on macOS (verified on Linux only);
   - the full benchmark set, which is too heavy for the laptop.
4. **The gallery on the Mac**, at full size, inspected by eye.
5. **Hands-on use of the window.** Most post-0.2.0 features have only scripted GUI
   checks. The Mac checklist in HANDOFF.md is entirely open, and a Retina display has
   never been tried.
6. **A clean installation** by someone following the documentation alone, on a
   computer that never had Ycrystal. This is also the first task of the independent
   evaluators; the authors should do a dry run first.
7. **Windows** was added after this audit (PR #35, 18 November 2026): the full suite
   passes on one Windows 11 laptop with POV-Ray for Windows, and the user tested it by
   hand. Not done there: the benchmark, the full-size gallery, and replays between
   machines; see `docs/development/windows-port.md`.

## 1. Mac mini, automated (Claude Code or a terminal)

Start from an up-to-date `main` in the existing checkout. The `.venv` stays, but its
editable install must be refreshed.

```bash
git pull
.venv/bin/python -m pip install -e ".[dev]" -c constraints.txt
.venv/bin/ycrystal --version            # ycrystal 0.4.0.dev0
.venv/bin/ycrystal --check-renderer     # PASS: POV-Ray 3.7… passed
```

**1a. Full suite with real windows.** Leave the machine alone: windows take the focus
for a few minutes.

```bash
YCRYSTAL_REQUIRE_INTEGRATION=1 .venv/bin/python -m pytest -q -rf
```

Expected (18 November 2026): 900 passed, 1 skipped — the skipped one checks an
installed POV-Ray for Windows and runs only on Windows. Record the count, the time,
and any failure by name. An intermittent failure seen once in PR #30 was never captured, so note the
test name if one appears and does not reproduce.

**1b. Is the benchmark's memory figure right on macOS?** On macOS `ru_maxrss` is in
bytes, and whether `wait4` includes grandchildren there is unverified. Run this check
before trusting any memory column:

```bash
.venv/bin/python - <<'EOF'
import sys; sys.path.insert(0, "scripts")
import benchmark_render as b
ballast = bytearray(300_000_000); ballast[::4096] = b"1" * len(ballast[::4096])
print("small command, big parent:", b.run_once([sys.executable, "-c", "pass"])["peak_rss_mib"])
big = "x = bytearray(200_000_000); x[::4096] = b'1' * len(x[::4096])"
code = f"import subprocess, sys; subprocess.run([sys.executable, '-c', {big!r}])"
print("command with 200 MB grandchild:", b.run_once([sys.executable, "-c", code])["peak_rss_mib"])
EOF
```

- **Expected (as on Linux):** about 10–20 MiB for the first line, about 200 MiB for the
  second.
- **If the second line is small,** macOS does not count grandchildren: report memory
  as "not measured on macOS" and do not publish that column.
- **If the first line is large,** the parent leaks into the figure: report it the same
  way.

**1c. Benchmark.** Run the same set as on the laptop, for a direct comparison, then
the full set, which the Mac mini can afford:

```bash
.venv/bin/python scripts/benchmark_render.py --quick --scale 0.5 --repeats 3 --out artifacts/validation/bench-macos
.venv/bin/python scripts/benchmark_render.py --out artifacts/validation/bench-macos-full
```

The full set has the 12 × 12 × 12 case and 1600 × 1200 images, with 1 + 5 runs per
case. Expect tens of minutes, mostly glass. Copy each `benchmark.json` unedited to
`docs/development/validation-results/benchmark-macos-<date>.json` (and `…-full-…`),
and add the tables to [validation](validation.md#d-render-cost).

**1d. Replays across machines, Linux → Mac.** Copy these two folders from the
laptop, byte for byte (`rsync -a`, or a USB drive; not through a program that
recompresses PNGs):

- `artifacts/gallery/figures/` (2.6 MB, 7 figures at 1600 × 1200);
- `artifacts/validation/bench-linux/snapshots/` (0.9 MB, 9 benchmark cases at half
  size).

Then on the Mac:

```bash
.venv/bin/python scripts/replay_check.py PATH/TO/gallery-figures-from-linux --out artifacts/replay-gallery-linux-on-mac
.venv/bin/python scripts/replay_check.py PATH/TO/bench-snapshots-from-linux --out artifacts/replay-bench-linux-on-mac
```

What the results mean:

- **`modified`** means a file changed in the copy; copy it again.
- **`same`** (largest difference ≤ 1 of 255) means the pixels agree across the two
  installations for that figure.
- **`different`** is a result, not an error. Keep the numbers (largest and mean
  difference, fraction of pixels beyond 1) and look at both images side by side.
  Differences are most likely in glass, chrome, area-light shadows, and anti-aliased
  edges.

Copy each `replay-check.json` to
`docs/development/validation-results/replay-check-linux-to-macos-<date>.json`.

**1e. Gallery on the Mac, and replays Mac → Linux.**

```bash
.venv/bin/python scripts/make_gallery.py --out artifacts/gallery-macos
```

Expected: 7 figures, and 7 of 7 replays the same on the Mac itself. Look at all seven
in `artifacts/gallery-macos/figures/` next to the thumbnails of the
[gallery](../guide/gallery.md). Then copy `artifacts/gallery-macos/figures/` to the
laptop and run there:

```bash
.venv/bin/python scripts/replay_check.py PATH/TO/gallery-macos-figures --out artifacts/replay-gallery-macos-on-linux
```

Both directions together answer question C of the validation report for these two
installations.

## 2. Mac mini, by a person

The [hands-on checklist in HANDOFF.md](../HANDOFF.md#hands-on-checks-on-a-mac) is still
entirely open. Add these items for the features since 0.3.0:

- [ ] *File ▸ Import Style…* with the mapping rows: open `tests/fixtures/BaZrO3.cif`,
      import `examples/grey-studio.ycstyle`, set `Ti →` to `Zr`, Apply, then Undo
      (the examples guide gives the expected texts).
- [ ] The **View along** buttons in every order, including directly from c to x (the
      fix of PR #30).
- [ ] Open a gallery snapshot (`artifacts/gallery-macos/figures/kyanite.ycrystal`) in
      the window. The view and the POV-Ray preview (F5) should match the rendered
      PNG's framing.
- [ ] *Render ▸ Render Image…* as PNG, PDF, and JPEG, and place the PDF in a LaTeX or
      Word document at its stated size.
- [ ] On a Retina display, if one is available: sharpness, picking, and the size of
      the view (only an emulated 2× scale has been tried).

Record ticks and problems in HANDOFF.md; a person's report, not a test, establishes
these.

## 3. Linux laptop, by a person

- [ ] FR-EXPORT-01 has run in CI on Ubuntu but has not been checked by hand on Linux:
      *Render Image…* in all three formats.
- [ ] The Import Style mapping rows and the View along buttons, as for the Mac.
- [ ] Open a snapshot made on the Mac (from step 1e) in the window.

## 4. A computer that never had Ycrystal

A dry run of the independent evaluation by the authors, before real evaluators get
it. Use a new user account or a fresh virtual machine running Ubuntu 24.04 or macOS,
with no `~/.config/Y-Matter Lab` and no earlier checkout.

1. Follow `README.md` and `docs/guide/install.md` literally. Note every step that is
   missing, wrong, or needs knowledge the page does not give.
2. Run `ycrystal --check-renderer`, the commands of the examples guide, and
   `python scripts/make_gallery.py --scale 0.25 --out gallery-check`.
3. Replay a copied reference set (step 1d) with `scripts/replay_check.py`. This also
   gives a third installation for the cross-machine question.
4. Work through the [independent evaluation checklist](independent-evaluation.md)
   yourself, and fix the documentation where it failed before sending it out.

The repository is public, so the fresh computer (and a referee) can clone it without a
GitHub account.

## What each result allows us to say

| Result | Then the documents may say |
| --- | --- |
| 1a passes | "All tests pass on macOS 15 (Apple silicon) with real windows" for this version |
| 1b as expected | The benchmark's memory column is valid on macOS too |
| 1d/1e `same` for a figure | That figure's snapshot gives the same pixels on both installations (name both POV-Ray builds) |
| 1d/1e `different` | The size of the difference, per figure; never "identical across platforms" |
| Section 2 or 3 ticked by a person | The hands-on item works on that system, as reported by that person |
| Section 4 done | The installation guide was followed successfully on a clean system, or what was fixed |

Possible next step (a recommendation, not authorised): run `replay_check.py` in the
macOS CI job against a small reference set committed to the repository. Every pull
request would then measure Linux → macOS pixel differences automatically. That needs
a decision about storing reference images (about 0.5 MB at quarter size) in Git.
