"""Tests for the policy-identity layer (canonical / digest / diff)."""

from app.statespec import identity
from app.statespec.core import Invariant, StateSpec, Transition
from app.statespec.expr import field, opaque
from app.statespec.batch_spec import BATCH_SPEC


def _spec(*, version=1, guard=None, roles=("r",), label="", control_id=None,
          states=("a", "b"), invariant=None):
    return StateSpec(
        name="t", title="t",
        states={s: "" for s in states},
        fields={"n": "int"},
        initial="a", terminal=frozenset({"b"}),
        transitions=(Transition("go", ("a",), "b", roles=frozenset(roles),
                                 guard=guard, label=label, control_id=control_id),),
        invariants=() if invariant is None else (invariant,),
        version=version,
    )


def test_digest_deterministic():
    assert identity.digest(BATCH_SPEC) == identity.digest(BATCH_SPEC)


def test_digest_changes_on_guard_threshold():
    a = _spec(guard=field("n").le(0))
    b = _spec(guard=field("n").le(5))
    assert identity.digest(a) != identity.digest(b)
    # ...and the diff names it
    lines = identity.diff(identity.canonical(a), identity.canonical(b))
    assert any("guard" in line and "n ≤ 0" in line and "n ≤ 5" in line for line in lines)


def test_digest_changes_on_roles_and_version():
    base = _spec(roles=("r",))
    assert identity.digest(base) != identity.digest(_spec(roles=("r", "s")))
    assert identity.digest(base) != identity.digest(_spec(version=2))
    lines = identity.diff(identity.canonical(base), identity.canonical(_spec(version=2)))
    assert any("version: 1 → 2" in line for line in lines)


def test_control_id_is_stable_across_label_change():
    a = _spec(control_id="GO-1", label="old wording")
    b = _spec(control_id="GO-1", label="new wording")
    ca, cb = identity.canonical(a), identity.canonical(b)
    assert ca["transitions"][0]["id"] == "GO-1"   # id is the control_id, not the name
    lines = identity.diff(ca, cb)
    assert lines == ["transition GO-1: label changed"]   # identity stable, label diffed


def test_opaque_source_is_hashed_into_identity():
    spec = _spec(guard=opaque("credit", 1, "credit check", fn=lambda ctx: True))
    can = identity.canonical(spec)
    op_hashes = can["transitions"][0]["opaque"]
    assert "credit:1" in op_hashes and len(op_hashes["credit:1"]) == 16
    # a baseline whose opaque hash differs (a body swap) is flagged by diff
    stale = identity.canonical(spec)
    stale["transitions"][0]["opaque"]["credit:1"] = "0" * 16
    lines = identity.diff(stale, can)
    assert any("opaque body/version changed" in line for line in lines)


def test_diff_state_and_invariant_changes():
    a = _spec(states=("a", "b"))
    b = _spec(states=("a", "b", "c"),
              invariant=Invariant("inv", field("n").ne(0), control_id="INV-1"))
    lines = identity.diff(identity.canonical(a), identity.canonical(b))
    assert "+ state c" in lines
    assert any("+ invariant INV-1" in line for line in lines)
