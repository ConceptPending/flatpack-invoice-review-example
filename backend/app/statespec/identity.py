"""Policy identity: canonical serialisation, content digest, and semantic diff.

The whole point is to answer, for a governed workflow: *which exact policy is
this, and what changed?* `canonical()` produces a deterministic, content-only
representation; `digest()` hashes it (including a hash of any `Opaque` body, so
opaque code can't change the policy's meaning without changing its identity —
the tamper-evidence the registry alone can't give). `diff()` turns two
canonical forms into a plain-English list of what changed — the seam a policy
review (e.g. a GitHub check) renders for a human approver.
"""

from __future__ import annotations

import hashlib
import inspect
import json

from app.statespec import expr as _expr
from app.statespec.core import StateSpec


def _walk_opaque(node) -> list:
    if isinstance(node, _expr.Opaque):
        return [node]
    if isinstance(node, (_expr.All, _expr.Any)):
        out = []
        for t in node.terms:
            out += _walk_opaque(t)
        return out
    if isinstance(node, _expr.Not):
        return _walk_opaque(node.term)
    return []


def _opaque_hashes(node) -> dict:
    """For each Opaque in the expression, hash its registered source so a body
    change is reflected in the digest even without a version bump."""
    out = {}
    if node is None:
        return out
    for op in _walk_opaque(node):
        fn = _expr._OPAQUE_REGISTRY.get((op.name, op.version))
        src = inspect.getsource(fn) if fn is not None else "<unregistered>"
        out[f"{op.name}:{op.version}"] = hashlib.sha256(src.encode()).hexdigest()[:16]
    return out


def _guard_dict(node):
    return _expr.to_dict(node) if node is not None else None


def canonical(spec: StateSpec) -> dict:
    """Deterministic, content-only representation. Labels/descriptions are
    included (a reworded policy is a changed policy), but rendered text is not
    (it's derivable). Keyed and sorted so the form is stable."""
    return {
        "name": spec.name,
        "version": spec.version,
        "states": {s: d for s, d in sorted(spec.states.items())},
        "initial": spec.initial,
        "terminal": sorted(spec.terminal),
        "fields": dict(sorted(spec.fields.items())),
        "transitions": sorted(
            (
                {
                    "id": t.control_id or t.name,
                    "name": t.name,
                    "from": sorted(t.sources),
                    "to": t.dest,
                    "roles": sorted(t.roles),
                    "label": t.label,
                    "guard": _guard_dict(t.guard),
                    "opaque": _opaque_hashes(t.guard),
                }
                for t in spec.transitions
            ),
            key=lambda d: d["id"],
        ),
        "invariants": sorted(
            (
                {
                    "id": i.control_id or i.name,
                    "name": i.name,
                    "label": i.label,
                    "condition": _expr.to_dict(i.condition),
                    "opaque": _opaque_hashes(i.condition),
                }
                for i in spec.invariants
            ),
            key=lambda d: d["id"],
        ),
    }


def digest(spec: StateSpec) -> str:
    """sha256 of the canonical form. The policy's content identity."""
    blob = json.dumps(canonical(spec), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode()).hexdigest()


def policy_record(spec: StateSpec) -> dict:
    """The committed baseline: version + digest + canonical spec."""
    return {"version": spec.version, "digest": digest(spec), "spec": canonical(spec)}


# --- Semantic diff ----------------------------------------------------------


def _render_guard(d) -> str:
    return _expr.render(_expr.from_dict(d)) if d else "—"


def diff(old: dict, new: dict) -> list[str]:
    """Plain-English changes from one canonical spec to another. `old`/`new`
    are `canonical()` dicts (or the `spec` field of a policy record)."""
    out: list[str] = []

    if old.get("version") != new.get("version"):
        out.append(f"version: {old.get('version')} → {new.get('version')}")

    old_states, new_states = set(old["states"]), set(new["states"])
    for s in sorted(new_states - old_states):
        out.append(f"+ state {s}")
    for s in sorted(old_states - new_states):
        out.append(f"- state {s}")

    of, nf = old["fields"], new["fields"]
    for k in sorted(set(nf) - set(of)):
        out.append(f"+ field {k}: {nf[k]}")
    for k in sorted(set(of) - set(nf)):
        out.append(f"- field {k}")
    for k in sorted(set(of) & set(nf)):
        if of[k] != nf[k]:
            out.append(f"field {k}: type {of[k]} → {nf[k]}")

    out += _diff_items(old["transitions"], new["transitions"], "transition", _diff_transition)
    out += _diff_items(old["invariants"], new["invariants"], "invariant", _diff_invariant)
    return out


def _diff_items(old_list, new_list, kind, differ) -> list[str]:
    out = []
    old_by = {d["id"]: d for d in old_list}
    new_by = {d["id"]: d for d in new_list}
    for i in sorted(set(new_by) - set(old_by)):
        out.append(f"+ {kind} {i}")
    for i in sorted(set(old_by) - set(new_by)):
        out.append(f"- {kind} {i}")
    for i in sorted(set(old_by) & set(new_by)):
        out += differ(i, old_by[i], new_by[i])
    return out


def _diff_transition(tid, o, n) -> list[str]:
    out = []
    if o["from"] != n["from"] or o["to"] != n["to"]:
        out.append(f"transition {tid}: {o['from']}→{o['to']} ⇒ {n['from']}→{n['to']}")
    if o["roles"] != n["roles"]:
        out.append(f"transition {tid}: roles {o['roles']} → {n['roles']}")
    if o["guard"] != n["guard"]:
        out.append(
            f"transition {tid}: guard {_render_guard(o['guard'])} → "
            f"{_render_guard(n['guard'])}"
        )
    if o.get("opaque") != n.get("opaque"):
        out.append(f"transition {tid}: opaque body/version changed")
    if o["label"] != n["label"]:
        out.append(f"transition {tid}: label changed")
    return out


def _diff_invariant(iid, o, n) -> list[str]:
    out = []
    if o["condition"] != n["condition"]:
        out.append(
            f"invariant {iid}: {_render_guard(o['condition'])} → "
            f"{_render_guard(n['condition'])}"
        )
    if o.get("opaque") != n.get("opaque"):
        out.append(f"invariant {iid}: opaque body/version changed")
    if o["label"] != n["label"]:
        out.append(f"invariant {iid}: label changed")
    return out
