"""Unit tests for the declarative expression engine (app/statespec/expr.py)."""

from decimal import Decimal

import pytest

from app.statespec import apply, validate
from app.statespec.core import InvariantViolation, StateSpec, Transition
from app.statespec.expr import (
    ExpressionError,
    all_,
    any_,
    field,
    from_dict,
    literal,
    not_,
    opaque,
    render,
    to_canonical_bytes,
    to_dict,
)


# --- evaluation -------------------------------------------------------------


def test_evaluate_basic():
    assert field("n").eq(0).evaluate({"n": 0}) is True
    assert field("n").le(10).evaluate({"n": 10}) is True
    assert field("n").le(10).evaluate({"n": 11}) is False
    assert field("s").is_in(("a", "b")).evaluate({"s": "a"}) is True
    assert field("s").not_in(("a", "b")).evaluate({"s": "c"}) is True
    assert all_(field("a").eq(1), field("b").eq(2)).evaluate({"a": 1, "b": 2}) is True
    assert any_(field("a").eq(1), field("b").eq(2)).evaluate({"a": 9, "b": 2}) is True
    assert not_(field("a").eq(1)).evaluate({"a": 2}) is True


def test_field_vs_field():
    e = field("actor").ne(field("owner"))
    assert e.evaluate({"actor": "x", "owner": "y"}) is True
    assert e.evaluate({"actor": "x", "owner": "x"}) is False


def test_missing_field_raises():
    with pytest.raises(ExpressionError):
        field("n").eq(0).evaluate({})


def test_float_literal_rejected():
    with pytest.raises(ExpressionError):
        literal(1.5)


# --- serialization round-trip + canonical ----------------------------------


@pytest.mark.parametrize(
    "expr",
    [
        field("amount").le(Decimal("10000")),
        any_(field("status").ne("approved"), field("error_count").eq(0)),
        field("status").is_in(("a", "b", "c")),
        not_(field("flag").eq(True)),
    ],
)
def test_round_trip(expr):
    assert from_dict(to_dict(expr)) == expr
    assert isinstance(to_canonical_bytes(expr), bytes)


def test_decimal_canonical():
    d = to_dict(field("amount").le(Decimal("10000.00")))
    assert d["right"]["value"] == "10000"  # normalized, no trailing zeros


def test_render():
    assert render(field("amount").le(10000)) == "amount ≤ 10000"
    assert render(field("s").eq("x")) == 's = "x"'


# --- typecheck (validate's matrix) ------------------------------------------


def _spec(guard=None, invariant_cond=None, fields=None):
    from app.statespec.core import Invariant

    return StateSpec(
        name="t", title="t",
        states={"a": "", "b": ""},
        fields=fields or {"n": "int"},
        initial="a", terminal=frozenset({"b"}),
        transitions=(Transition("go", ("a",), "b", roles=frozenset({"r"}), guard=guard),),
        invariants=() if invariant_cond is None
        else (Invariant("inv", invariant_cond),),
    )


def test_typecheck_unknown_field():
    problems = validate(_spec(guard=field("missing").eq(0)), known_roles=frozenset({"r"}))
    assert any("not in the spec's field schema" in p for p in problems)


def test_typecheck_cross_type_eq_rejected():
    # uuid field eq str literal — the silent-False vector
    spec = _spec(guard=field("u").eq("x"), fields={"u": "uuid", "n": "int"})
    assert any("incompatible types" in p for p in validate(spec, known_roles=frozenset({"r"})))


def test_typecheck_order_on_str_rejected():
    spec = _spec(guard=field("s").lt("x"), fields={"s": "str"})
    assert any("ordered" in p for p in validate(spec, known_roles=frozenset({"r"})))


def test_typecheck_int_decimal_ok():
    spec = _spec(guard=field("amt").le(10), fields={"amt": "decimal"})
    assert validate(spec, known_roles=frozenset({"r"})) == []


def test_empty_all_rejected():
    spec = _spec(guard=all_())
    assert any("empty All" in p for p in validate(spec, known_roles=frozenset({"r"})))


# --- opaque escape hatch ----------------------------------------------------


def test_opaque_registration_and_validate():
    op = opaque("credit_ok", 1, "Within credit", fn=lambda ctx: ctx["ok"])
    assert op.evaluate({"ok": True}) is True
    # registered → validate clean
    assert validate(_spec(guard=op), known_roles=frozenset({"r"})) == []
    # a different version is unregistered → flagged
    spec2 = _spec(guard=opaque("credit_ok", 2, "v2"))
    assert any("not registered" in p for p in validate(spec2, known_roles=frozenset({"r"})))


def test_opaque_duplicate_registration_rejected():
    opaque("dup", 1, "x", fn=lambda c: True)
    with pytest.raises(ExpressionError):
        opaque("dup", 1, "x", fn=lambda c: False)


# --- runtime invariant enforcement ------------------------------------------


def test_apply_enforces_invariants():
    # status must never become "b" (contrived) — apply must refuse the only
    # transition that produces it, as an InvariantViolation (a backstop).
    spec = _spec(invariant_cond=field("status").ne("b"))
    with pytest.raises(InvariantViolation):
        apply(spec, "go", "a", frozenset({"r"}), {"status": "a", "n": 0})


def test_apply_missing_context_field_raises():
    spec = _spec(guard=field("n").eq(0))
    with pytest.raises(ExpressionError):
        # context lacks "n" (declared field) → contract breach
        apply(spec, "go", "a", frozenset({"r"}), {"status": "a"})
