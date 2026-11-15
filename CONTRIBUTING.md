# Contributing to Ycrystal

Thank you for helping. This guide covers the development setup, the checks every change
should pass, and how dependencies and hook versions are kept up to date.

## Development installation

Verified on Linux Mint 22.1 with the system Python 3.12 (see [README.md](README.md)):

```bash
sudo apt install povray libxcb-cursor0 python3.12-venv
git clone https://github.com/ymatterlab/ycrystal.git
cd ycrystal
/usr/bin/python3 -m venv .venv
.venv/bin/python -m pip install -e ".[dev]" -c constraints.txt
```

Use the system interpreter, not Miniconda/Anaconda: their bundled `libstdc++` can stop
Mesa's OpenGL driver from loading ("Could not initialize GLX"). `constraints.txt` pins the
integration-tested versions; always install with `-c constraints.txt`.

## Pre-commit hooks

```bash
.venv/bin/pre-commit install            # run the hooks automatically on `git commit`
.venv/bin/pre-commit run --all-files    # check every tracked file
```

The hooks are lightweight (no Qt/VTK, GUI, or POV-Ray): Ruff lint with safe fixes, Ruff
formatting (settings in `pyproject.toml`), trailing whitespace and final newlines,
YAML syntax, a 250 KB limit per file, and a check that the Ruff hook version equals
the `ruff==` pin in `constraints.txt`. Test fixtures in `tests/fixtures/` are exempt from
the whitespace fixers so that structure files stay byte-for-byte as written.

The same configuration runs in three places on purpose:

| Where | Role |
| --- | --- |
| Your machine (`pre-commit install`) | Fast feedback before committing |
| GitHub Actions, job `pre-commit` | Authoritative check on every pull request, independent of external services |
| pre-commit.ci (once enabled) | Optional automatic fixes on pull requests and monthly hook updates |

The overlap between the Actions job and pre-commit.ci is intentional and harmless: both
run the same pinned hooks, so they agree.

## Tests

```bash
.venv/bin/python -m pytest -q -rs
```

- GUI tests (`gui` marker) need an X11 display: a desktop session or
  `xvfb-run -a python -m pytest -q -rs`.
- Rendering tests (`povray` marker) need a POV-Ray 3.7 executable that passes
  `ycrystal --check-renderer`; set `YCRYSTAL_POVRAY=/usr/bin/povray` if needed.
- Locally, missing prerequisites skip those tests (`-rs` lists them). CI sets
  `YCRYSTAL_REQUIRE_INTEGRATION=1`, which turns a missing display or renderer into an
  error; set it yourself to make sure nothing was skipped.
- `scripts/m0_evidence.py` regenerates screenshots and alignment measurements.

## Generated files

Renders, render caches, screenshots, and evidence output belong in `artifacts/`
(ignored by Git) or outside the repository. Do not commit them. The large-file hook
rejects files above 250 KB; a genuinely needed larger asset must be excluded explicitly
in `.pre-commit-config.yaml` with a reason.

## Progress record

When a change alters what is implemented or verified, update
[docs/PROGRESS.md](docs/PROGRESS.md): status, evidence (commands and actual results),
unverified items, and the next step. Do not mark a milestone complete without its
acceptance evidence.

## Pull requests

Describe the change briefly and report the validation you actually ran, including what
you could not run (the pull-request template asks for this).

## Dependency and hook updates

- **Python packages:** Dependabot checks monthly. Minor and patch updates arrive in one
  grouped pull request, major updates individually, at most three open per ecosystem.
  It updates the exact pins in `constraints.txt` and leaves the lower bounds in
  `pyproject.toml` alone while they still allow the new release.
- **GitHub Actions:** Dependabot checks monthly with the same grouping.
- **Hooks:** pre-commit.ci proposes hook updates monthly. Dependabot does not touch hooks.
- No update is merged automatically; CI must pass and a maintainer merges.

### Keeping Ruff in sync

Ruff is pinned twice: `rev` of `astral-sh/ruff-pre-commit` in `.pre-commit-config.yaml`
and `ruff==` in `constraints.txt`. Dependabot ignores Ruff; the pre-commit side leads:

1. pre-commit.ci opens its monthly autoupdate pull request (or run
   `pre-commit autoupdate --repo https://github.com/astral-sh/ruff-pre-commit`).
2. The `ruff-version-sync` hook fails in that pull request until
   `ruff==` in `constraints.txt` is set to the same version. Edit it on the same branch.
3. Run `pre-commit run --all-files` and the tests; commit any formatting changes.

### Regenerating constraints.txt

Dependabot changes pins one package (or one group) at a time and does not re-resolve
the environment. If its pull request fails to install or breaks tests, regenerate the
pins in a fresh environment and test them:

```bash
/usr/bin/python3 -m venv /tmp/yc-env
/tmp/yc-env/bin/python -m pip install -e ".[dev]"      # newest compatible releases
/tmp/yc-env/bin/python -m pip install "ruff==<version in .pre-commit-config.yaml>"
/tmp/yc-env/bin/python -m pytest -q -rs                # needs a display and POV-Ray
/tmp/yc-env/bin/python -m pip freeze --exclude-editable > constraints.new
```

Keep the two header comment lines of `constraints.txt`, replace the pins with those in
`constraints.new`, rerun `pre-commit run --all-files`, and record the change in
`docs/PROGRESS.md`.

## Repository-owner setup

Committed configuration does not by itself activate these services:

- **pre-commit.ci:** install the pre-commit.ci GitHub app for `ymatterlab/ycrystal` at
  <https://pre-commit.ci>. After its first run, a status badge can be added to the
  README (`https://results.pre-commit.ci/badge/github/ymatterlab/ycrystal/main.svg`).
- **Dependabot:** version updates start from `.github/dependabot.yml` once Dependabot is
  allowed for the repository; check *Settings ▸ Code security* (also for Dependabot
  alerts and security updates, which this file does not configure).
- **Branch protection (optional):** require the `pre-commit` and `tests` checks on `main`.
