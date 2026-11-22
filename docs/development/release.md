# Release procedure and checklist

How a Ycrystal release is prepared, and the checklists of versions 0.4.0, 0.3.0,
0.2.0, and 0.1.0. Publication
(tag, GitHub release, making the repository public) is the maintainer's decision and
is not part of this procedure.

The latest public release is
[Ycrystal 0.4.0](https://github.com/ymatterlab/ycrystal/releases/tag/v0.4.0),
published on 18 November 2026 with a Windows installer and tagged source archives.
The checklists below record verification for each release at the time it was
prepared. Later merges into `main` do not change the contents of those tags or
downloadable installers; see the [current feature table](../HANDOFF.md#current-project-status).

## Procedure

1. Update `__version__` in `src/ycrystal/__init__.py` and `CHANGELOG.md`.
2. Run the checks on the reference machine (Linux Mint, X11, POV-Ray 3.7 package):

    ```bash
    .venv/bin/pre-commit run --all-files
    YCRYSTAL_REQUIRE_INTEGRATION=1 .venv/bin/python -m pytest -q -rs
    .venv/bin/python scripts/docs_examples.py
    .venv-docs/bin/zensical build --clean --strict
    ```

    `tests/test_release.py` includes the end-to-end workflow (open a CIF, rotate and
    pan, expand to 2 × 2 × 2, change an element's finish, choose a studio, render, save,
    close, reopen without the source file, render again, then POSCAR and QE imports
    (`ibrav = 0` and `ibrav = 1`) and the rejection of a QE file whose lattice pw.x would
    refuse), the command line, the desktop launcher, and the
    examples.
3. Clean install: in a new directory, follow [Install and launch](../guide/install.md)
   exactly (clone, `venv`, `pip install -e . -c constraints.txt`), then run
   `ycrystal --version`, `--check-renderer`, an example `--render`, a short GUI launch,
   and `--install-desktop` into a temporary `XDG_DATA_HOME` checked with
   `desktop-file-validate`.
4. Build the artifacts and install the wheel into another fresh environment:

    ```bash
    uv build -o dist        # dist/ycrystal-X.Y.Z.tar.gz and -py3-none-any.whl
    /usr/bin/python3 -m venv /tmp/yc-wheel
    /tmp/yc-wheel/bin/python -m pip install dist/ycrystal-X.Y.Z-py3-none-any.whl -c constraints.txt
    /tmp/yc-wheel/bin/ycrystal examples/SrTiO3-studio.ycrystal --render /tmp/check.png
    ```

    The wheel contains the presets, thumbnails, and icon; the source distribution adds
    `constraints.txt`, the examples, the test fixtures, and the notices.
5. The Windows installer (on a Windows computer, or the `ycrystal-windows-installer`
   artifact of the *Windows installer* workflow run of the release commit): build it
   with `packaging\windows\build.ps1`, run `packaging\windows\coexistence-check.ps1`,
   install it once by hand (wizard, Start menu, a preview), and attach
   `Ycrystal-X.Y.Z-windows-x64-setup.exe` to the GitHub release. It is not signed; see
   [Windows installer](windows-installer.md#releasing).
6. Record the results in `docs/PROGRESS.md` and in the checklist below, marking each
   item passed, failed, or unverified.

## Checklist for 0.4.0

Requested by the user on 18 November 2026: tag `v0.4.0` once PR #40 (the Windows
installer) passed CI, update the files that record the version, then audit the README
before deciding on a GitHub release. The version was set by its own pull request
(branch `release/v0.5.0`); the tag marks its merge. Steps 2–4 of the procedure (the
reference-machine run, a clean install by a person, the wheel) were not run for this
tag; each feature was verified when merged (see `docs/PROGRESS.md`).

| Item | Status | Evidence |
| --- | --- | --- |
| Version | Updated before the tag | `__version__ = "0.4.0"`; changelog section 0.4.0 (PRs #23–#40); README badge and version line; sample outputs in the guides |
| Tests at the last feature merge | Passed | CI run 44401632629 on PR #40: Ubuntu 24.04 with Python 3.12, 3.13, 3.14 (910 passed, 10 skipped each, GUI tests under Xvfb), macOS 15 (738 passed, 10 skipped), Windows Server 2022 (746 passed, 2 skipped), docs, pre-commit; *Windows installer* run 44401632704 (installer built, packaged render, 27 coexistence checks) |
| Tests at the tagged commit | Passed | CI run [44408274074](https://github.com/ymatterlab/ycrystal/actions/runs/44408274074): Ubuntu Python 3.12, 3.13, 3.14, macOS, Windows, docs, pre-commit; Windows installer run [44408273918](https://github.com/ymatterlab/ycrystal/actions/runs/44408273918) also passed at `34c803d` |
| Projects compatible | Passed | Schema 7 unchanged since 0.3.0; older projects open (`test_project.py`) |
| Windows installer | Built by CI (artifact `ycrystal-windows-installer`); built and installed on the Windows laptop | Not signed; built from the tag on the laptop (541 s, 129 MB), installed as an upgrade (reports 0.4.0), and attached to the GitHub release. SHA-256 `B67AF22B46E3B1DCE3A6F646496BBAFDBC64F42F26423C6FC80A5CB9F5ED40FB` |
| Clean install by a person, wheel build | Not run for 0.4.0 | |
| README audit by the user | Done | The user asked for the GitHub release after it |
| Tag `v0.4.0` | Created | Annotated tag at `34c803d` (merge of PR #41) |
| GitHub release | Published 18 November 2026 | [Ycrystal 0.4.0](https://github.com/ymatterlab/ycrystal/releases/tag/v0.4.0), with the Windows installer; not a pre-release |

## Checklist for 0.3.0

Version 0.3.0 did not follow the procedure above. The maintainer tagged `v0.3.0` on
16 November 2026 at the merge of the macOS work (commit `6ed6b03`) after CI passed there,
before `__version__` and the changelog were updated; both were updated afterwards on
`main`. The features in 0.3.0 were each verified when they were merged (see
`docs/PROGRESS.md`); the release checklist itself was not run.

| Item | Status | Evidence |
| --- | --- | --- |
| Version | Fixed after the tag | The source at `v0.3.0` reports 0.2.0; `main` reports the development version `0.4.0.dev0` and has changelog section 0.3.0 |
| Tests at the tagged commit | Passed | CI of `6ed6b03`: pre-commit, documentation, Ubuntu 24.04 (full suite under Xvfb with POV-Ray 3.7), macOS 15 (tests without windows) |
| Projects compatible | Passed | Schema 7; older projects open (`test_project.py`) |
| Clean install, wheel build and install | Not run for 0.3.0 | |
| Hands-on use of the new features by a person | Partial | The user reports FR-VECTOR-01 working; other features have scripted GUI checks only; see `docs/HANDOFF.md` |
| Tag `v0.3.0` | Created | Annotated tag at `6ed6b03`; GitHub release not created |

## Checklist for 0.2.0

Status on 15 November 2026, same reference machine as 0.1.0. 0.2.0 adds three features
(FR-COLOR-01, FR-RENDER-01, FR-LIGHT-01) and no dependencies; the format, renderer, and
platform support is unchanged, so the 0.1.0 items below that concern installation,
licences, and the desktop launcher were not repeated.

| Item | Status | Evidence |
| --- | --- | --- |
| Version | Passed | `__version__ = "0.2.0"`; `ycrystal --version` prints `ycrystal 0.2.0`; changelog section 0.2.0 |
| Tests without POV-Ray | Passed | `YCRYSTAL_REQUIRE_INTEGRATION=1 pytest -m "not povray"`: 346 passed |
| POV-Ray tests | Passed (subset) | `test_release.py` (workflow, command line, examples) and the GUI render tests passed; the preset render tests (`test_presets.py`) were not rerun because every exported scene is byte-identical to 0.1.0 |
| Exported scenes compatible | Passed | 672 scenes (all lighting and environment presets, four cameras, four geometries, two sizes) written by 0.1.0 and 0.2.0 differ only in the header line with the version and time |
| Projects compatible | Passed | Schema 5 unchanged; 0.1.0 projects open (aspect lock defaults to locked); `test_project.py` |
| Renderer check | Passed | `ycrystal --check-renderer`: `PASS … within 0.14 px` |
| Documentation | Passed | `zensical build --clean --strict`: no issues; user guide covers the three features |
| Artifacts | Passed | `uv build`: sdist and wheel `ycrystal-0.2.0` (the wheel contains the new modules and presets) |
| Clean install from a fresh clone, wheel install in a fresh environment | Not repeated | Unchanged packaging; done for 0.1.0 |
| Hands-on use of the new features by a person | Unverified | Scripted GUI checks only |
| Tag `v0.2.0` | See `docs/PROGRESS.md` | Maintainer's decision; GitHub release not created |

## Checklist for 0.1.0

Status on 15 November 2026 (Linux Mint 22.1, Intel Core Ultra 5 135U, 8 GB RAM, Intel
Meteor Lake graphics with Mesa 25.2, POV-Ray 3.7.0.10 package, Python 3.12.3).

### Installation

| Item | Status | Evidence |
| --- | --- | --- |
| System prerequisites (`git povray povray-includes libxcb-cursor0 python3.12-venv`) installed from the Mint repositories | Passed | `dpkg-query`: all installed (POV-Ray 1:3.7.0.10-3build4) |
| Clean checkout + documented `venv`/`pip` commands | Passed | Fresh directory, `/usr/bin/python3 -m venv`, `pip install -e . -c constraints.txt` (warm pip cache) |
| First-time download of the wheels (cold pip cache) | Unverified | The development machine's pip cache was warm |
| `git clone https://…` as documented | Failed while the repository is private | Needs credentials; `gh repo clone` works and is documented |
| `ycrystal --version`, `--check-renderer` | Passed | `ycrystal 0.1.0`; `PASS … within 0.14 px` |
| GUI starts from the clean install | Passed | Example project opened; window running after 10 s without errors |
| Desktop launcher files written, valid, removed | Passed | `--install-desktop` into a temporary `XDG_DATA_HOME`; `desktop-file-validate` silent; `--uninstall-desktop` removed all three files |
| Launcher appears in the Cinnamon menu and starts Ycrystal; double-clicking a `.ycrystal` file opens it | Unverified | Needs a person at the desktop (`ycrystal --install-desktop`, then check the menu and the file manager) |
| Wheel installs into a fresh environment and renders an example | Passed | Non-editable install; 30 materials, 12 environments, 42 thumbnails, icon present |

### Workflow and regressions

| Item | Status | Evidence |
| --- | --- | --- |
| End-to-end workflow of the plan (CIF → … → reopen without source → render again) | Passed (automated, on the Mint display) | `test_release_workflow`: identical images before and after reopening |
| Same workflow by hand | Unverified | Recommended before publishing |
| POSCAR and QE (`ibrav = 0`) imports of the same structure | Passed | Same test; reader equivalence tests (M1) |
| `ibrav ≠ 0` rejected with a clear message | Passed | GUI and command line |
| Example projects render from the command line | Passed | Each in about 1–2 s at 400 × 300 |
| Full automated suite | Passed in CI | Ubuntu 24.04, Xvfb, POV-Ray 3.7 (every pull request) |
| Documentation builds without warnings; examples execute | Passed | `zensical build --strict`; `scripts/docs_examples.py`; CI doctests |

### Performance (development laptop)

| Displayed atoms | Bonds | Load (s) | Drag step (ms) |
| --- | --- | --- | --- |
| 71 (SrTiO3 2³) | 192 | 0.14 | 31 |
| 1,315 (SrTiO3 6³) | 4,320 | 0.10 | 70 |

`scripts/benchmark_scene.py --sizes 2 6 --frames 15`; larger sizes were measured in M2
(20,000 atoms: about 100 ms per drag step). Preview render times are in
[the appearance guide](../guide/appearance.md#lighting) and `docs/PROGRESS.md`.

### Review

| Item | Status | Notes |
| --- | --- | --- |
| Dependency constraints | Passed | Lower bounds in `pyproject.toml`; the tested set pinned in `constraints.txt` (monthly Dependabot updates); Python 3.10/3.11 allowed but unverified |
| Licences | Passed | MIT; LGPL dependencies installed separately; see `THIRD_PARTY_NOTICES.md` |
| Exported include dependencies | Passed | Scene headers list them; export warns when missing; documented (`povray-includes`) |
| Known limitations | Passed | [Troubleshooting and limitations](../guide/troubleshooting.md), [support matrix](../guide/support.md) |
| Artifacts | Passed | `uv build`: sdist and wheel `ycrystal-0.1.0` |
| Tag `v0.1.0`, GitHub release, public repository | Not done | Maintainer's decision |
