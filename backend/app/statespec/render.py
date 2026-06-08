"""Turn a `StateSpec` into artifacts humans read.

These outputs are the half of the value proposition that isn't tests: a
diagram and a plain-English table that a reviewer, auditor, or domain owner
can read to confirm the workflow is *fit for purpose* — without reading
Python. `to_dict` is the same data as JSON, the seed for a future
layperson-facing viewer (a separate tool/repo).
"""

from __future__ import annotations

from app.statespec.core import StateSpec


def to_mermaid(spec: StateSpec) -> str:
    """A Mermaid `stateDiagram-v2`. Renders on GitHub, in docs, and in most
    Markdown viewers — so the diagram lives next to the code and never goes
    stale (it is generated, not drawn)."""
    lines = ["stateDiagram-v2", f"    %% {spec.title}", f"    [*] --> {spec.initial}"]
    for t in spec.transitions:
        roles = "/".join(sorted(t.roles)) or "—"
        guard = f" [{t.guard}]" if t.guard else ""
        edge = f"{t.name} ({roles}){guard}"
        for src in t.sources:
            lines.append(f"    {src} --> {t.dest}: {edge}")
    for term in sorted(spec.terminal):
        lines.append(f"    {term} --> [*]")
    return "\n".join(lines)


def to_table(spec: StateSpec) -> str:
    """A plain-English Markdown transition table — the auditor's checklist."""
    rows = [
        "| Action | From | To | Who may do it | Condition |",
        "| --- | --- | --- | --- | --- |",
    ]
    for t in spec.transitions:
        roles = ", ".join(sorted(t.roles)) or "—"
        guard = t.guard or "—"
        frm = ", ".join(t.sources)
        label = f" — {t.label}" if t.label else ""
        rows.append(f"| **{t.name}**{label} | {frm} | {t.dest} | {roles} | {guard} |")
    return "\n".join(rows)


def to_dict(spec: StateSpec) -> dict:
    """Serialisable form — the machine-readable spec, also what an API can
    hand to a front-end lifecycle viewer."""
    return {
        "name": spec.name,
        "title": spec.title,
        "initial": spec.initial,
        "terminal": sorted(spec.terminal),
        "states": [{"id": s, "description": d} for s, d in spec.states.items()],
        "transitions": [
            {
                "name": t.name,
                "label": t.label,
                "from": list(t.sources),
                "to": t.dest,
                "roles": sorted(t.roles),
                "guard": t.guard,
            }
            for t in spec.transitions
        ],
        "invariants": [
            {"name": i.name, "label": i.label} for i in spec.invariants
        ],
    }


def to_markdown_doc(spec: StateSpec) -> str:
    """The full generated artifact: title, diagram, table, invariants."""
    parts = [
        f"# {spec.title}",
        "",
        "> **Generated file — do not edit by hand.** Regenerate with "
        "`make spec-doc`. The source of truth is the spec in "
        f"`app/statespec/{spec.name}_spec.py`; this document is rendered from "
        "it so the picture can never drift from the enforced behaviour.",
        "",
        "## Lifecycle",
        "",
        "```mermaid",
        to_mermaid(spec),
        "```",
        "",
        "## States",
        "",
        "| State | Meaning |",
        "| --- | --- |",
    ]
    for s, d in spec.states.items():
        tag = " _(start)_" if s == spec.initial else ""
        tag += " _(final)_" if s in spec.terminal else ""
        parts.append(f"| `{s}`{tag} | {d} |")
    parts += ["", "## Transitions", "", to_table(spec)]
    if spec.invariants:
        parts += [
            "",
            "## Guarantees that always hold",
            "",
            "These invariants are checked after *every* transition by the "
            "property-based test suite (Hypothesis), across randomly generated "
            "sequences of actions:",
            "",
        ]
        for inv in spec.invariants:
            parts.append(f"- **{inv.name}** — {inv.label or '(see spec)'}")
    parts.append("")
    return "\n".join(parts)
