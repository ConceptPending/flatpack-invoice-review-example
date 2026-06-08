#!/usr/bin/env python3
"""Validate and render the project's state-machine specs.

A *spec* (see app/statespec/) is the single source of truth for an entity's
lifecycle. This script is its CI gate and its documentation generator:

    python backend/scripts/statespec.py check    # validate every spec (exit 1 on problems)
    python backend/scripts/statespec.py render    # (re)write docs/specs/<name>-lifecycle.md + .policy.json
    python backend/scripts/statespec.py diff <name>  # semantic diff: live spec vs committed baseline

`check` is fast and import-light enough to run in CI alongside the tests;
`render` keeps the human-readable diagram + the committed policy baseline
(`.policy.json`, version + digest + canonical spec) in sync with the code;
`diff` shows what a change did to the policy (the seam a review renders).

To register a new spec, add it to `SPECS` below.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# Allow running as `python backend/scripts/statespec.py` from the repo root.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("DEBUG", "true")

from app.roles import ALL_ROLES  # noqa: E402
from app.statespec import core, identity, render  # noqa: E402
from app.statespec.batch_spec import BATCH_SPEC  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
DOCS_DIR = ROOT / "docs" / "specs"

# Every spec the project ships. New lifecycle? Add it here.
SPECS = [BATCH_SPEC]


def cmd_check() -> int:
    failed = False
    for spec in SPECS:
        # Validate roles against the catalogue so a misspelled (un-grantable,
        # thus un-fireable) role is caught here, not at runtime.
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
        md = DOCS_DIR / f"{spec.name}-lifecycle.md"
        md.write_text(render.to_markdown_doc(spec), encoding="utf-8")
        # The committed policy baseline: version + digest + canonical spec.
        # A diff against this is "what this change did to the policy."
        pj = DOCS_DIR / f"{spec.name}.policy.json"
        pj.write_text(
            json.dumps(identity.policy_record(spec), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(f"wrote {md.relative_to(ROOT)} + {pj.relative_to(ROOT)}")
    return 0


def cmd_diff(name: str) -> int:
    spec = next((s for s in SPECS if s.name == name), None)
    if spec is None:
        print(f"unknown spec {name!r}; known: {[s.name for s in SPECS]}", file=sys.stderr)
        return 2
    baseline = DOCS_DIR / f"{spec.name}.policy.json"
    if not baseline.exists():
        print(f"no committed baseline at {baseline.relative_to(ROOT)} — run render", file=sys.stderr)
        return 2
    old = json.loads(baseline.read_text())
    new = identity.policy_record(spec)
    if old["digest"] == new["digest"]:
        print(f"{name}: no policy change (digest {new['digest'][:12]}…)")
        return 0
    print(f"{name}: POLICY CHANGED  v{old['version']} ({old['digest'][:12]}…) "
          f"→ v{new['version']} ({new['digest'][:12]}…)")
    for line in identity.diff(old["spec"], new["spec"]):
        print(f"    {line}")
    if old["version"] == new["version"]:
        print("    ⚠ digest changed but version did not — bump StateSpec.version")
    return 0


def main(argv: list[str]) -> int:
    cmd = argv[1] if len(argv) > 1 else "check"
    if cmd == "check":
        return cmd_check()
    if cmd == "render":
        return cmd_render()
    if cmd == "diff":
        if len(argv) < 3:
            print("usage: statespec.py diff <spec-name>", file=sys.stderr)
            return 2
        return cmd_diff(argv[2])
    print(f"unknown command {cmd!r}; use 'check', 'render', or 'diff'", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
