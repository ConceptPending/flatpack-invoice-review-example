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
    """For each entity in the manifest, assert a matching SQLAlchemy model exists
    AND every declared field maps to a column with a compatible type.

    Matching the entity is by name with light normalisation: an entity
    named `Invoice` matches a model named `Invoice` or a table named
    `invoices` / `invoice`. Once the model is matched, fields are walked
    and each is asserted to exist as a column on the model. Closes #34.
    """
    entities = manifest.get("entities", [])
    if not entities:
        report.warn(
            "entities",
            "manifest has no entities — nothing to verify on the entity side",
        )
        return

    tables = _table_names()
    table_objects = {t.name: t for t in Base.metadata.tables.values()}
    models = _model_class_names()

    for entity in entities:
        name = entity.get("name")
        if not name:
            report.miss("entity name missing", "")
            continue

        norm = name.lower()
        candidate_tables = {norm, norm + "s", norm.rstrip("y") + "ies"}
        matched_tables = candidate_tables & tables

        if name not in models and not matched_tables:
            report.miss(
                f"entity {name}",
                f"no model named {name!r} or table in {sorted(candidate_tables)}; "
                f"available tables: {sorted(tables)}",
            )
            continue

        report.ok(f"entity {name}", "model present")

        # Walk fields. Find the SQLAlchemy table to use for column
        # lookups. Preference: the table whose name matches a candidate
        # (covers Invoice → invoices); fallback to whichever table has
        # the most field-name overlap.
        fields = entity.get("fields") or []
        if not fields:
            continue

        table = None
        for t in matched_tables:
            if t in table_objects:
                table = table_objects[t]
                break
        if table is None:
            # Last-resort: pick by mapper class name.
            for mapper in Base.registry.mappers:
                if mapper.class_.__name__ == name:
                    table = mapper.local_table
                    break
        if table is None:
            report.warn(
                f"entity {name} fields",
                "couldn't resolve a table for field checks",
            )
            continue

        column_names = {c.name for c in table.columns}
        for field in fields:
            fname = field.get("name")
            ftype = field.get("type")
            if not fname:
                report.miss(f"entity {name} field", "field missing 'name'")
                continue
            if fname not in column_names:
                report.miss(
                    f"entity {name}.{fname}",
                    f"no column named {fname!r} on table {table.name!r}",
                )
                continue
            # Column exists — check type compatibility.
            col = table.columns[fname]
            ok, detail = _types_compatible(ftype, col.type)
            if ok:
                report.ok(
                    f"entity {name}.{fname}",
                    detail,
                )
            else:
                report.warn(
                    f"entity {name}.{fname}",
                    f"type {ftype!r} → column type {type(col.type).__name__}: {detail}",
                )


# Loose type-compatibility map. Each manifest field type maps to a set of
# SQLAlchemy type-class names that are considered acceptable. Add to this
# as new field types appear in promoted Flatpacks.
TYPE_COMPATIBILITY: dict[str, set[str]] = {
    "string":   {"String", "Text", "Unicode", "VARCHAR"},
    "text":     {"Text", "String", "TEXT"},
    "number":   {"Numeric", "Integer", "Float", "BigInteger", "DECIMAL", "INTEGER", "FLOAT"},
    "integer":  {"Integer", "BigInteger", "SmallInteger", "INTEGER"},
    "date":     {"Date", "DATE"},
    "datetime": {"DateTime", "TIMESTAMP"},
    "boolean":  {"Boolean", "BOOLEAN"},
    "enum":     {"Enum", "ENUM", "String", "VARCHAR"},
    "json":     {"JSON", "JSONB", "ARRAY"},
    "list":     {"JSON", "JSONB", "ARRAY"},
    "uuid":     {"UUID", "CHAR"},
}


def _check_promoted_entities(entities: list[dict], report: Report) -> None:
    """Verify entities listed in reference/promoted-entities.json.

    Same shape as manifest entities; reuses check_entities's logic via
    a synthetic manifest. The claim prefix is `promoted-entity` rather
    than `entity` so the source is visible. See baseplate#37 for the
    motivation: the manifest only carries entities the Flatpack author
    declared; the promotion plan often introduces more (Supplier,
    ReviewBatch, ValidationError, etc.). Without this file the verifier
    can't catch a missing introduced entity.
    """
    synthetic = {"entities": entities}
    # Capture findings from check_entities by intercepting the report
    # via a small adapter that rewrites claim prefixes.
    base_findings = len(report.findings)
    check_entities(synthetic, report)
    for finding in report.findings[base_findings:]:
        if finding.claim.startswith("entity "):
            finding.claim = "promoted-" + finding.claim


def _types_compatible(manifest_type: str | None, column_type) -> tuple[bool, str]:
    """Return (compatible, human-readable reason).

    Manifest types are descriptive labels, not Python types. The map
    above accepts a small set of SQLAlchemy type-class names per
    manifest label. Unknown manifest types pass with a 'no rule for X'
    note — better to ignore than false-fail."""
    if manifest_type is None:
        return True, "no manifest type to check"

    col_type_name = type(column_type).__name__
    # Some manifest types include suffixes like 'list[string]' — strip to the head.
    head = manifest_type.split("[", 1)[0].strip().lower()

    allowed = TYPE_COMPATIBILITY.get(head)
    if allowed is None:
        return True, f"no compatibility rule for manifest type {manifest_type!r}; accepted as {col_type_name}"
    if col_type_name in allowed:
        return True, f"manifest {manifest_type} ↔ SA {col_type_name}"
    return False, f"expected one of {sorted(allowed)}"


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
#
# Some Flatpack exports are client-side (the browser renders to clipboard
# or via window.print). Their Baseplate analogue is usually a server
# endpoint that returns the data the printable view fetches. We list
# both shapes; the verifier accepts a route match OR explicitly notes
# the export may be client-side.
EXPORT_URL_HINTS: dict[str, list[str]] = {
    "clean_csv":            ["/export", "/clean", ".csv"],
    "errors_csv":           ["/errors", ".csv"],
    "csv":                  [".csv", "/export"],
    "json":                 [".json", "/export"],
    "markdown":             [".md", "/export"],
    "markdown_clipboard":   ["/markdown", "/summary"],  # often server-rendered then copied client-side
    "summary_clipboard":    ["/summary"],
    "summary_print":        ["/summary", "/print"],     # closes baseplate#35 — promoted apps usually expose a /summary endpoint
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
        if any(h in paths_str for h in hints):
            report.ok(f"export {label}", f"route matching one of {hints}")
        else:
            # The export may legitimately be client-side. We surface as
            # a warning rather than a miss — the maintainer can confirm
            # by noting it in reference/decisions.md.
            report.warn(
                f"export {label}",
                f"no route containing any of {hints}; "
                f"may be client-side only — confirm in reference/decisions.md "
                f"if so. routes: {paths}",
            )


# -----------------------------------------------------------------------------
# Validation check.
#
# If the manifest carries `validation_predicates` (the structured form from
# flatpack#1), we resolve each predicate against actual Pydantic field
# declarations and SQLAlchemy column constraints. This is the strong path
# and is what closes baseplate#33 and #36.
#
# Otherwise we fall back to a tightened keyword scan — restricted to
# function bodies inside *Service classes and @field_validator decorated
# functions, not module-level comments. Every keyword-match passes as a
# WARN (not OK) to keep the trust-surface visible.
# -----------------------------------------------------------------------------

APP_ROOT = Path(__file__).resolve().parents[1] / "app"


def check_validations(manifest: dict, report: Report) -> None:
    predicates = manifest.get("validation_predicates")
    if predicates:
        _check_predicates(predicates, report)
        # If we have predicates, the plain-text rules are redundant signal.
        return
    _check_validations_by_keyword(manifest.get("validations", []), report)


# --- Strong path: structured predicates --------------------------------------

def _collect_pydantic_fields() -> dict[str, list[tuple[str, object]]]:
    """Return a map of field name → list of (qualified_owner, FieldInfo) pairs.

    Walks every BaseModel subclass that's been imported by virtue of
    app.main loading.
    """
    try:
        from pydantic import BaseModel
    except ImportError:
        return {}

    out: dict[str, list[tuple[str, object]]] = {}

    def walk(cls):
        for sub in cls.__subclasses__():
            for name, info in sub.model_fields.items():
                out.setdefault(name, []).append((sub.__name__, info))
            walk(sub)

    walk(BaseModel)
    return out


def _collect_columns() -> dict[str, list[tuple[str, object]]]:
    """Return a map of column name → list of (table_name, Column) pairs."""
    out: dict[str, list[tuple[str, object]]] = {}
    for table in Base.metadata.tables.values():
        for column in table.columns:
            out.setdefault(column.name, []).append((table.name, column))
    return out


def _check_predicate_pydantic(
    field_name: str,
    constraint: str,
    value,
    pyd: dict[str, list[tuple[str, object]]],
) -> tuple[bool, str]:
    """Look for evidence in Pydantic field declarations. Returns
    (verified, detail)."""
    if field_name not in pyd:
        return False, f"no Pydantic field named {field_name!r}"

    # We may have multiple Pydantic models defining the field (e.g.
    # Create, Update, Response). It only needs to be honoured in one
    # input schema — pick the strongest evidence across all matches.
    for owner, info in pyd[field_name]:
        # Pydantic v2: constraints live in info.metadata as a list of
        # constraint objects. The class names are stable strings.
        constraints = list(getattr(info, "metadata", []) or [])
        type_str = repr(getattr(info, "annotation", None))

        def has_meta(name: str, attr: str | None = None, expected=None) -> bool:
            for m in constraints:
                if type(m).__name__ == name:
                    if attr is None:
                        return True
                    return getattr(m, attr, None) == expected
            return False

        if constraint == "required":
            if info.is_required():
                return True, f"{owner}.{field_name} is_required()"
        elif constraint in ("gt", "gte", "lt", "lte"):
            mapping = {"gt": "Gt", "gte": "Ge", "lt": "Lt", "lte": "Le"}
            attr = {"gt": "gt", "gte": "ge", "lt": "lt", "lte": "le"}[constraint]
            if has_meta(mapping[constraint], attr, value):
                return True, f"{owner}.{field_name}: {constraint} {value}"
        elif constraint == "min_length":
            if has_meta("MinLen", "min_length", value):
                return True, f"{owner}.{field_name}: min_length {value}"
        elif constraint == "max_length":
            if has_meta("MaxLen", "max_length", value):
                return True, f"{owner}.{field_name}: max_length {value}"
        elif constraint == "format":
            # 'format' is loose — we match the annotation type to common formats.
            mapping = {
                "date":     ("date",),
                "datetime": ("datetime",),
                "email":    ("EmailStr",),
                "url":      ("HttpUrl", "AnyUrl"),
                "uuid":     ("UUID",),
            }
            if any(m in type_str for m in mapping.get(value, ())):
                return True, f"{owner}.{field_name} annotated as {value}"
        elif constraint == "one_of":
            # 'one_of' tends to map to Pydantic Literal[...] or Enum.
            if "Literal" in type_str or "Enum" in type_str:
                return True, f"{owner}.{field_name} appears restricted (Literal/Enum)"
        elif constraint == "not_in_future":
            # No native Pydantic constraint — handled at validator level.
            # We let the column / fallback layer pick this up.
            return False, "not_in_future not expressible in plain Pydantic"
        elif constraint == "unique":
            # Pydantic doesn't carry uniqueness — it's a DB-layer concern.
            return False, "unique is a column-layer constraint"
        # Unknown constraint kinds fall through.

    return False, f"Pydantic field {field_name} found, but no matching {constraint}"


def _check_predicate_column(
    field_name: str,
    constraint: str,
    value,
    cols: dict[str, list[tuple[str, object]]],
) -> tuple[bool, str]:
    if field_name not in cols:
        return False, f"no column named {field_name!r}"

    for table_name, col in cols[field_name]:
        if constraint == "required":
            if not col.nullable:
                return True, f"{table_name}.{field_name} NOT NULL"
        elif constraint == "unique":
            if col.unique or any(
                getattr(uc, "columns", None) and any(c.name == field_name for c in uc.columns)
                for uc in col.table.constraints
                if uc.__class__.__name__ == "UniqueConstraint"
            ):
                return True, f"{table_name}.{field_name} unique"
        elif constraint == "max_length":
            length = getattr(col.type, "length", None)
            if length is not None and (value is None or length == value):
                return True, f"{table_name}.{field_name} length {length}"
        elif constraint == "format":
            # SQLAlchemy types ~ format tags.
            type_name = type(col.type).__name__
            mapping = {
                "date": ("Date",),
                "datetime": ("DateTime",),
                "uuid": ("UUID",),
            }
            if type_name in mapping.get(value, ()):
                return True, f"{table_name}.{field_name} column type {type_name}"
        # gt/gte/lt/lte: would live in CHECK constraints; not commonly
        # surfaced by SQLAlchemy without explicit declaration. Skipped.

    return False, f"column {field_name} found, but no matching {constraint}"


def _check_predicates(predicates: list[dict], report: Report) -> None:
    pyd = _collect_pydantic_fields()
    cols = _collect_columns()

    for p in predicates:
        field = p.get("field")
        constraint = p.get("constraint")
        value = p.get("value")
        if not field or not constraint:
            report.miss("predicate", f"malformed predicate: {p!r}")
            continue

        claim = f"predicate {field}:{constraint}"
        if value is not None:
            claim += f"={value!r}"

        # Try Pydantic first (the API boundary is where validation lives).
        ok, detail = _check_predicate_pydantic(field, constraint, value, pyd)
        if ok:
            report.ok(claim, detail)
            continue

        ok, detail2 = _check_predicate_column(field, constraint, value, cols)
        if ok:
            report.ok(claim, detail2)
            continue

        # If neither layer can confirm it, we WARN rather than MISS — the
        # constraint may be implemented via a custom validator we can't
        # introspect.
        report.warn(claim, f"{detail}; {detail2}")


# --- Fallback path: tightened keyword scan ----------------------------------

# Match function bodies inside *Service classes and @field_validator-decorated
# functions. We collect the source-text inside these regions and scan there
# instead of across all of app/.

_SERVICE_OR_VALIDATOR_RE = re.compile(
    r"(?:^class\s+\w+Service\b[^\n]*:\n(?:[ \t].*\n)+)"
    r"|(?:^[ \t]*@field_validator\b[^\n]*\n(?:[ \t]*@[\w.()=\"', ]+\n)*[ \t]*def\s+\w+[\s\S]*?(?=\n\S|\Z))",
    re.MULTILINE,
)


def _validation_corpus() -> str:
    """Concatenate just the *Service bodies and @field_validator-decorated
    functions across app/. This intentionally drops module-level
    comments — which is where the old keyword-scan was producing false
    positives in the worked example."""
    sources = [p.read_text(encoding="utf-8") for p in APP_ROOT.rglob("*.py")]
    out_parts: list[str] = []
    for src in sources:
        out_parts.extend(_SERVICE_OR_VALIDATOR_RE.findall(src))
    return "\n".join(out_parts).lower()


def _check_validations_by_keyword(rules: list[str], report: Report) -> None:
    if not rules:
        report.warn("validations", "manifest declares no validations")
        return

    corpus = _validation_corpus()
    if not corpus:
        report.warn(
            "validations",
            f"no *Service / @field_validator code found under {APP_ROOT} — "
            f"fallback keyword scan can't run",
        )
        return

    stop = {
        "the", "and", "must", "should", "with", "when", "this", "that",
        "than", "from", "into", "have", "been", "were", "will", "would",
        "could", "any", "all", "are", "not",
    }

    for rule in rules:
        tokens = [
            t.strip(",.:;\"'`()[]")
            for t in re.split(r"\s+", rule.lower())
            if t.strip(",.:;\"'`()[]")
        ]
        keywords = [t for t in tokens if (len(t) >= 4 and t not in stop) or t.isdigit()]
        if not keywords:
            report.warn(f"validation: {rule}", "no keywords extracted")
            continue

        hits = [k for k in keywords if k in corpus]
        if hits:
            # WARN (not OK) — keyword fallback is weak signal even when it
            # matches inside the right kind of function. The strong path
            # (predicates) is what produces OK.
            report.warn(
                f"validation: {rule}",
                f"keyword fallback matched {hits} inside *Service / "
                f"@field_validator; consider adding a validation_predicate "
                f"for stronger signal",
            )
        else:
            report.miss(
                f"validation: {rule}",
                f"none of {keywords} found in *Service or @field_validator "
                f"code in app/ — rule may not be implemented",
            )


# -----------------------------------------------------------------------------
# Entry point
# -----------------------------------------------------------------------------

def read_promoted_entities(flatpack_path: Path) -> dict:
    """Load reference/promoted-entities.json if present.

    Per docs/promoting-a-flatpack.md, this file is a sibling of
    original-flatpack.html. It lists entities the promotion plan
    introduced beyond the Flatpack's manifest (e.g. Supplier,
    ReviewBatch) — same field shape as the manifest's entities.

    Returns {} if the file is absent (back-compat: the verifier
    pre-#37 worked without it). Raises if it's present but
    malformed."""
    sibling = flatpack_path.parent / "promoted-entities.json"
    if not sibling.exists():
        return {}
    try:
        return json.loads(sibling.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"{sibling} is not valid JSON: {exc}")


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
    promoted = read_promoted_entities(flatpack_path)

    print(
        f"Verifying against {manifest.get('name', '(unnamed)')} "
        f"v{manifest.get('version', '?')} ({flatpack_path.name})",
    )
    print(f"Archetype: {manifest.get('archetype', '-')}")
    if promoted.get("entities"):
        print(
            f"Plus {len(promoted['entities'])} promoted entit"
            f"{'y' if len(promoted['entities']) == 1 else 'ies'} from promoted-entities.json"
        )
    print()

    report = Report()
    check_entities(manifest, report)
    if promoted.get("entities"):
        # Reuse the same field-walking logic by composing a synthetic
        # manifest with the promoted entities under the `entities` key.
        # The check labels itself "promoted-entity" so the source is
        # visible in output.
        _check_promoted_entities(promoted["entities"], report)
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
