"""Property-based proof that the batch review lifecycle behaves as specified.

Static well-formedness + a Hypothesis state machine that drives the engine over
random (action, roles, error_count) sequences and asserts the spec's invariants
always hold — in particular that an approved batch is never one with unresolved
validation errors.
"""

import pytest
from hypothesis import HealthCheck, settings
from hypothesis import strategies as st
from hypothesis.stateful import RuleBasedStateMachine, initialize, invariant, rule

from app.statespec import core, render
from app.statespec.batch_spec import BATCH_SPEC

ROLES = sorted({r for t in BATCH_SPEC.transitions for r in t.roles})
ACTIONS = [t.name for t in BATCH_SPEC.transitions]
ALL_ROLES = frozenset(ROLES)


def test_spec_is_well_formed():
    assert core.validate(BATCH_SPEC) == []


def test_separation_of_duties_in_spec():
    approve = BATCH_SPEC.transition("approve")
    reject = BATCH_SPEC.transition("reject")
    assert approve.roles == frozenset({"approver"})  # only approver approves
    assert "reviewer" in reject.roles  # reviewer can reject


def test_approve_blocked_by_open_errors():
    # right state + role, but unresolved errors -> guard refuses
    with pytest.raises(core.GuardRejected):
        core.apply(
            BATCH_SPEC, "approve", "pending", ALL_ROLES, {"error_count": 3}
        )
    # clean batch approves
    assert (
        core.apply(BATCH_SPEC, "approve", "pending", ALL_ROLES, {"error_count": 0})
        == "approved"
    )


def test_renders():
    assert "pending --> approved" in render.to_mermaid(BATCH_SPEC)
    assert "no_unresolved_errors" in render.to_table(BATCH_SPEC)


class BatchLifecycleMachine(RuleBasedStateMachine):
    def __init__(self):
        super().__init__()
        self.state = BATCH_SPEC.initial
        self.error_count = 0

    @initialize(errors=st.integers(min_value=0, max_value=5))
    def set_errors(self, errors):
        self.error_count = errors

    def _entity(self):
        return {"status": self.state, "error_count": self.error_count}

    @rule(action=st.sampled_from(ACTIONS), roles=st.sets(st.sampled_from(ROLES)))
    def fire(self, action, roles):
        roles = frozenset(roles)
        t = BATCH_SPEC.transition(action)
        expected_ok = (
            self.state in t.sources
            and bool(roles & t.roles)
            and (t.guard is None or self.error_count == 0)
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
    def status_is_declared(self):
        assert self.state in BATCH_SPEC.states

    @invariant()
    def approved_batches_are_clean(self):
        if self.state == "approved":
            assert self.error_count == 0

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
