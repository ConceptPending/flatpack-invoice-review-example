"""Verify that this Baseplate project honours the claims of the Flatpack
it was promoted from.

Reads the inline manifest from `reference/original-flatpack.html` and
asserts each `MANIFEST-ASSERTED` claim still holds in the live app:

- Every entity in the manifest has a matching SQLAlchemy model.
- Every export in the manifest has a matching FastAPI route or job.
- Every validation rule appears somewhere in the codebase (best-effort
  text match).

This is a **skeleton verifier**. The contract is defined; the checks
are intentionally partial in this first version. Extend by filling in
the `_check_*` functions as the project matures.

Run via:

    make verify-promotion
    # or:
    cd backend && DEBUG=true PYTHONPATH=. python scripts/verify_promotion.py \\
        ../reference/original-flatpack.html

Exit codes:
    0 — all MANIFEST-ASSERTED claims verified
    1 — at least one claim could not be verified
    2 — usage error or manifest missing/invalid

The verifier deliberately does NOT check `CODE-INFERRED` or
`INTERVIEW-REQUIRED` claims from the promotion plan — those don't map
to manifest claims by definition. If you want a record of how each
interview-required item was answered, write it down in
`reference/decisions.md`.
"""

from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

# Importing app.main registers the routes and loads the models. Run with
# DEBUG=true so startup validation doesn't kill the import when
# ADMIN_PASSWORD_HASH / JWT_SECRET aren't set locally.
os.environ.setdefault("DEBUG", "true")

from app.main import app  # noqa: E402 — must come after env setup
from app.models.base import Base  # noqa: E402


# -----------------------------------------------------------------------------
# Manifest parsing
# -----------------------------------------------------------------------------

MANIFEST_RE = re.compile(
    r'<script\s+type="application/json"\s+id="flatpack-manifest">'
    r"([\s\S]*?)</script>",
)


def read_manifest(flatpack_path: Path) -> dict:
    """Extract and parse the FLATPACK:MANIFEST block from a Flatpack."""
    html = flatpack_path.read_text(encoding="utf-8")
    match = MANIFEST_RE.search(html)
    if not match:
        raise SystemExit(
            f"No <script type='application/json' id='flatpack-manifest'> block "
            f"in {flatpack_path}",
        )
    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Manifest in {flatpack_path} is not valid JSON: {exc}")


# -----------------------------------------------------------------------------
# Check primitives
# -----------------------------------------------------------------------------

@dataclass
class Finding:
    level: str   # "ok" | "miss" | "warn"
    claim: str
    detail: str = ""


@dataclass
class Report:
    findings: list[Finding] = field(default_factory=list)

    def ok(self, claim: str, detail: str = "") -> None:
        self.findings.append(Finding("ok", claim, detail))

    def miss(self, claim: str, detail: str = "") -> None:
        self.findings.append(Finding("miss", claim, detail))

    def warn(self, claim: str, detail: str = "") -> None:
        self.findings.append(Finding("warn", claim, detail))

    @property
    def has_misses(self) -> bool:
        return any(f.level == "miss" for f in self.findings)


# -----------------------------------------------------------------------------
# Entity check — fully implemented
# -----------------------------------------------------------------------------

def _table_names() -> set[str]:
    return {t.name for t in Base.metadata.tables.values()}


def _model_class_names() -> set[str]:
    return {m.class_.__name__ for m in Base.registry.mappers}


def check_entities(manifest: dict, report: Report) -> None:
    """For each entity in the manifest, assert a matching SQLAlchemy model exists.

    Matching is by name with light normalisation: an entity named
    `Invoice` matches a model named `Invoice` or a table named
    `invoices` / `invoice`. The intent is to catch "we forgot to add a
    model", not to mandate a specific naming convention.
    """
    entities = manifest.get("entities", [])
    if not entities:
        report.warn(
            "entities",
            "manifest has no entities — nothing to verify on the entity side",
        )
        return

    tables = _table_names()
    models = _model_class_names()

    for entity in entities:
        name = entity.get("name")
        if not name:
            report.miss("entity name missing", "")
            continue

        norm = name.lower()
        candidate_tables = {norm, norm + "s", norm.rstrip("y") + "ies"}

        if name in models or candidate_tables & tables:
            report.ok(f"entity {name}", "model present")
        else:
            report.miss(
                f"entity {name}",
                f"no model named {name!r} or table in {sorted(candidate_tables)}; "
                f"available tables: {sorted(tables)}",
            )

        # TODO(verifier-v2): walk entity.fields and assert each one exists
        # as a column on the matched model. For now we only verify the
        # entity is present at all — the strongest signal of a forgotten
        # promotion step.


# -----------------------------------------------------------------------------
# Export check — partial: confirms route presence by URL-fragment search
# -----------------------------------------------------------------------------

def _route_paths() -> list[str]:
    paths = []
    for route in app.routes:
        path = getattr(route, "path", None)
        if path:
            paths.append(path)
    return paths


# Mapping from manifest export label → URL fragment to look for.
# Extend this as new export shapes appear in promoted Flatpacks.
EXPORT_URL_HINTS: dict[str, list[str]] = {
    "clean_csv":            ["/export", "/clean", ".csv"],
    "errors_csv":           ["/errors", ".csv"],
    "csv":                  [".csv", "/export"],
    "json":                 [".json", "/export"],
    "markdown":             [".md", "/export"],
    "markdown_clipboard":   [],   # client-side only; not a server export
    "summary_clipboard":    [],
    "summary_print":        [],   # printable summary; client-side
    "print_pdf":            ["/print", ".pdf"],
}


def check_exports(manifest: dict, report: Report) -> None:
    """For each export in the manifest, look for a route that plausibly serves it."""
    exports = manifest.get("exports", [])
    if not exports:
        report.warn("exports", "manifest declares no exports")
        return

    paths = _route_paths()
    paths_str = " ".join(paths)

    for label in exports:
        hints = EXPORT_URL_HINTS.get(label)
        if hints is None:
            report.warn(
                f"export {label}",
                "no URL hint defined in EXPORT_URL_HINTS; extend the map",
            )
            continue
        if not hints:
            report.ok(
                f"export {label}",
                "client-side export; no server route expected",
            )
            continue
        if any(h in paths_str for h in hints):
            report.ok(f"export {label}", f"route matching one of {hints}")
        else:
            report.miss(
                f"export {label}",
                f"no route containing any of {hints}; "
                f"routes: {paths}",
            )


# -----------------------------------------------------------------------------
# Validation rules check — partial: best-effort text search in app/
# -----------------------------------------------------------------------------

APP_ROOT = Path(__file__).resolve().parents[1] / "app"


def check_validations(manifest: dict, report: Report) -> None:
    """For each plain-English validation rule, search app/ for keyword evidence.

    This is intentionally weak: it tells you "no code in app/ mentions
    'invoice_date' or 'in the future' anywhere" — which is a useful
    signal — without trying to interpret natural-language rules
    formally.
    """
    rules = manifest.get("validations", [])
    if not rules:
        report.warn("validations", "manifest declares no validations")
        return

    # Read all .py files in app/ once.
    sources = {p: p.read_text(encoding="utf-8") for p in APP_ROOT.rglob("*.py")}
    if not sources:
        report.warn("validations", f"no Python sources under {APP_ROOT}")
        return

    combined = "\n".join(sources.values()).lower()

    for rule in rules:
        # Pick keywords from the rule that look like field names or
        # numerical constraints. Drop stopwords; keep tokens of length
        # >= 4 or numbers. This is heuristic by design.
        tokens = [
            t.strip(",.:;\"'`()[]")
            for t in re.split(r"\s+", rule.lower())
            if t.strip(",.:;\"'`()[]")
        ]
        stop = {
            "the", "and", "must", "should", "with", "when", "this",
            "that", "than", "from", "into", "have", "been", "were",
            "will", "would", "could", "any", "all", "are", "not",
        }
        keywords = [t for t in tokens if (len(t) >= 4 and t not in stop) or t.isdigit()]
        if not keywords:
            report.warn(f"validation: {rule}", "no keywords extracted")
            continue

        hits = [k for k in keywords if k in combined]
        if hits:
            report.ok(f"validation: {rule}", f"keywords matched: {hits}")
        else:
            report.miss(
                f"validation: {rule}",
                f"none of {keywords} found in app/ — rule may not be implemented",
            )


# -----------------------------------------------------------------------------
# Entry point
# -----------------------------------------------------------------------------

def main() -> int:
    if len(sys.argv) < 2:
        print(
            "Usage: verify_promotion.py <path-to-original-flatpack.html>",
            file=sys.stderr,
        )
        return 2

    flatpack_path = Path(sys.argv[1]).resolve()
    if not flatpack_path.exists():
        print(f"File not found: {flatpack_path}", file=sys.stderr)
        return 2

    manifest = read_manifest(flatpack_path)
    print(
        f"Verifying against {manifest.get('name', '(unnamed)')} "
        f"v{manifest.get('version', '?')} ({flatpack_path.name})",
    )
    print(f"Archetype: {manifest.get('archetype', '-')}")
    print()

    report = Report()
    check_entities(manifest, report)
    check_exports(manifest, report)
    check_validations(manifest, report)

    by_level = {"ok": 0, "miss": 0, "warn": 0}
    for f in report.findings:
        by_level[f.level] = by_level.get(f.level, 0) + 1
        tag = {"ok": "OK  ", "miss": "MISS", "warn": "WARN"}[f.level]
        line = f"{tag}  {f.claim}"
        if f.detail:
            line += f"\n        {f.detail}"
        print(line)

    print()
    print(
        f"Summary: {by_level['ok']} ok, "
        f"{by_level['miss']} miss, "
        f"{by_level['warn']} warn.",
    )

    return 1 if report.has_misses else 0


if __name__ == "__main__":
    sys.exit(main())
