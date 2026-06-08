"""Property-based proof that the batch review lifecycle behaves as specified.

Static well-formedness + a Hypothesis state machine that drives the engine over
random (action, roles, error_count) sequences and asserts the spec's invariants
always hold — in particular that an approved batch is never one with unresolved
validation errors.
"""

import uuid

import pytest
from hypothesis import HealthCheck, settings
from hypothesis import strategies as st
from hypothesis.stateful import RuleBasedStateMachine, initialize, invariant, rule

from app.statespec import core, render
from app.statespec.batch_spec import BATCH_SPEC

_OWNER = uuid.UUID(int=1)   # who uploaded the batch
_OTHER = uuid.UUID(int=2)   # a different actor

ROLES = sorted({r for t in BATCH_SPEC.transitions for r in t.roles})
ACTIONS = [t.name for t in BATCH_SPEC.transitions]
ALL_ROLES = frozenset(ROLES)


def test_spec_is_well_formed():
    assert core.validate(BATCH_SPEC) == []
    # ...and clean against the real role catalogue.
    from app.roles import ALL_ROLES as CATALOGUE

    assert core.validate(BATCH_SPEC, known_roles=CATALOGUE) == []


def test_validate_catches_misspelled_role_and_duplicate_action():
    from app.statespec.core import StateSpec, Transition

    # A role not in the catalogue (e.g. a typo) — would be un-grantable, so the
    # transition could never fire; validate must flag it.
    typo = StateSpec(
        name="x", title="x", states={"a": "", "b": ""}, fields={}, initial="a",
        terminal=frozenset({"b"}),
        transitions=(Transition("go", ("a",), "b", roles=frozenset({"aprover"})),),
    )
    problems = core.validate(typo, known_roles=frozenset({"approver"}))
    assert any("not in the catalogue" in p for p in problems)

    # Duplicate action name.
    dup = StateSpec(
        name="y", title="y", states={"a": "", "b": ""}, fields={}, initial="a",
        terminal=frozenset({"b"}),
        transitions=(
            Transition("go", ("a",), "b", roles=frozenset({"r"})),
            Transition("go", ("a",), "b", roles=frozenset({"r"})),
        ),
    )
    assert any("duplicate transition name" in p for p in core.validate(dup))


def test_separation_of_duties_in_spec():
    approve = BATCH_SPEC.transition("approve")
    reject = BATCH_SPEC.transition("reject")
    assert approve.roles == frozenset({"approver"})  # only approver approves
    assert "reviewer" in reject.roles  # reviewer can reject


def test_approve_blocked_by_open_errors():
    clean = {"error_count": 0, "actor_id": _OTHER, "uploaded_by_id": _OWNER}
    # right state + role, but unresolved errors -> guard refuses
    with pytest.raises(core.GuardRejected):
        core.apply(BATCH_SPEC, "approve", "pending", ALL_ROLES, {**clean, "error_count": 3})
    # clean batch, approver != uploader -> approves
    assert core.apply(BATCH_SPEC, "approve", "pending", ALL_ROLES, clean) == "approved"


def test_approve_blocked_when_approver_is_uploader():
    # maker-checker: same actor as uploader is refused even with zero errors
    same = {"error_count": 0, "actor_id": _OWNER, "uploaded_by_id": _OWNER}
    with pytest.raises(core.GuardRejected):
        core.apply(BATCH_SPEC, "approve", "pending", ALL_ROLES, same)


def test_renders():
    assert "pending --> approved" in render.to_mermaid(BATCH_SPEC)
    # the table shows the rendered guard expression, not a guard name
    assert "error_count = 0" in render.to_table(BATCH_SPEC)


class BatchLifecycleMachine(RuleBasedStateMachine):
    def __init__(self):
        super().__init__()
        self.state = BATCH_SPEC.initial
        self.error_count = 0
        self.uploaded_by_id = _OWNER
        self.actor_id = _OTHER  # default distinct (re-chosen each fire)

    @initialize(errors=st.integers(min_value=0, max_value=5))
    def set_errors(self, errors):
        self.error_count = errors

    def _entity(self):
        return {
            "status": self.state,
            "error_count": self.error_count,
            "actor_id": self.actor_id,
            "uploaded_by_id": self.uploaded_by_id,
        }

    @rule(
        action=st.sampled_from(ACTIONS),
        roles=st.sets(st.sampled_from(ROLES)),
        same_actor=st.booleans(),
    )
    def fire(self, action, roles, same_actor):
        roles = frozenset(roles)
        # The actor is either the uploader (maker-checker should block approval)
        # or someone else.
        self.actor_id = self.uploaded_by_id if same_actor else _OTHER
        t = BATCH_SPEC.transition(action)
        guard_ok = t.guard is None or (
            self.error_count == 0 and self.actor_id != self.uploaded_by_id
        )
        expected_ok = (
            self.state in t.sources and bool(roles & t.roles) and guard_ok
        )
        decision = core.can_fire(BATCH_SPEC, action, self.state, roles, self._entity())
        assert decision.allowed == expected_ok, (
            action, sorted(roles), self.state, self.error_count, decision.reason,
        )
        if expected_ok:
            self.state = core.apply(
                BATCH_SPEC, action, self.state, roles, self._entity()
            )
            assert self.state == t.dest
        else:
            with pytest.raises(core.TransitionError):
                core.apply(BATCH_SPEC, action, self.state, roles, self._entity())

    @invariant()
    def spec_invariants_hold(self):
        # Generic: run every invariant predicate declared in the spec after
        # each step, rather than restating them here (so the test can't drift
        # from the spec's stated guarantees).
        snap = self._entity()
        for inv in BATCH_SPEC.invariants:
            assert inv.condition.evaluate(snap), f"invariant {inv.name!r} violated at {snap}"

    @invariant()
    def terminals_are_sinks(self):
        if self.state in BATCH_SPEC.terminal:
            assert (
                core.enabled_transitions(
                    BATCH_SPEC, self.state, ALL_ROLES, self._entity()
                )
                == []
            )


TestBatchLifecycle = BatchLifecycleMachine.TestCase
TestBatchLifecycle.settings = settings(
    max_examples=200,
    stateful_step_count=10,
    deadline=None,
    suppress_health_check=[HealthCheck.filter_too_much],
)
