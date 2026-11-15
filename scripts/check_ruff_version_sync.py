"""Check that the Ruff pre-commit hook and the Ruff pin in constraints.txt match.

Ruff runs in two places: the pre-commit hook (``rev`` of astral-sh/ruff-pre-commit in
.pre-commit-config.yaml, updated with ``pre-commit autoupdate``) and the development
environment (``ruff==`` in constraints.txt, installed by CI and contributors). Both must
be the same release so that local and CI results agree. When one is
updated, update the other in the same pull request (see CONTRIBUTING.md).

Standard library only, so it runs as a lightweight local pre-commit hook.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HOOK_REPO = "https://github.com/astral-sh/ruff-pre-commit"


def hook_version(config_text: str) -> str | None:
    """Ruff version from the ``rev`` of the ruff-pre-commit repository entry."""
    match = re.search(
        rf"repo:\s*{re.escape(HOOK_REPO)}\s*\n\s*rev:\s*['\"]?v?([0-9][^'\"\s#]*)",
        config_text,
    )
    return match.group(1) if match else None


def pinned_version(constraints_text: str) -> str | None:
    match = re.search(r"^ruff==([^\s#;]+)", constraints_text, re.MULTILINE | re.IGNORECASE)
    return match.group(1) if match else None


def main() -> int:
    config = (ROOT / ".pre-commit-config.yaml").read_text(encoding="utf-8")
    constraints = (ROOT / "constraints.txt").read_text(encoding="utf-8")
    hook, pin = hook_version(config), pinned_version(constraints)
    if hook is None:
        print(f"No {HOOK_REPO} entry with a rev found in .pre-commit-config.yaml.")
        return 1
    if pin is None:
        print("No 'ruff==' pin found in constraints.txt.")
        return 1
    if hook != pin:
        print(
            f"Ruff versions differ: pre-commit hook rev v{hook}, constraints.txt ruff=={pin}.\n"
            f"Set both to the same release (e.g. ruff=={hook} in constraints.txt after a "
            "pre-commit autoupdate) and rerun 'pre-commit run --all-files'."
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
