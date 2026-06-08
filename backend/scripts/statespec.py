#!/usr/bin/env python3
"""Validate and render the project's state-machine specs (Baseplate
`lifecycle-state-machine` recipe).

    python backend/scripts/statespec.py check    # validate every spec (exit 1 on problems)
    python backend/scripts/statespec.py render    # (re)write docs/specs/<name>-lifecycle.md

`check` runs in CI alongside the tests; `render` keeps the human-readable
diagram + table in sync with the enforced behaviour. Register new specs in
`SPECS`.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("DEBUG", "true")

from app.roles import ALL_ROLES  # noqa: E402
from app.statespec import core, render  # noqa: E402
from app.statespec.batch_spec import BATCH_SPEC  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
DOCS_DIR = ROOT / "docs" / "specs"

SPECS = [BATCH_SPEC]


def cmd_check() -> int:
    failed = False
    for spec in SPECS:
        # Validate roles against the human/system catalogue so a misspelled
        # role (un-grantable, thus un-fireable) is caught here, not at runtime.
        problems = core.validate(spec, known_roles=ALL_ROLES)
        if problems:
            failed = True
            print(f"MISS  {spec.name}: {len(problems)} problem(s)")
            for p in problems:
                print(f"        - {p}")
        else:
            print(f"OK    {spec.name}: well-formed "
                  f"({len(spec.states)} states, {len(spec.transitions)} transitions)")
    if failed:
        print("\nspec-check FAILED")
        return 1
    print("\nspec-check passed")
    return 0


def cmd_render() -> int:
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    for spec in SPECS:
        out = DOCS_DIR / f"{spec.name}-lifecycle.md"
        out.write_text(render.to_markdown_doc(spec), encoding="utf-8")
        print(f"wrote {out.relative_to(ROOT)}")
    return 0


def main(argv: list[str]) -> int:
    cmd = argv[1] if len(argv) > 1 else "check"
    if cmd == "check":
        return cmd_check()
    if cmd == "render":
        return cmd_render()
    print(f"unknown command {cmd!r}; use 'check' or 'render'", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
