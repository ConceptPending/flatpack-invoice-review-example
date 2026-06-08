"""Declarative state-machine specs with a generic enforcement engine.

Ported from Baseplate's `lifecycle-state-machine` recipe. A *spec* is plain
data describing an entity's lifecycle — its states, the named transitions
between them, who (which roles) may fire each, and the guard predicates that
must hold. The same artifact is human-readable (`render`) and machine-checkable
(`core.validate` + the Hypothesis suite). `core.apply` is the single place a
transition is allowed to happen, so code cannot drift from the spec unnoticed.

Here it governs the `ReviewBatch` approval lifecycle (see `batch_spec`).
"""

from app.statespec.core import (
    Decision,
    GuardRejected,
    IllegalTransition,
    Invariant,
    PermissionDenied,
    StateSpec,
    Transition,
    TransitionError,
    UnknownAction,
    apply,
    can_fire,
    enabled_transitions,
    validate,
)

__all__ = [
    "Decision",
    "GuardRejected",
    "IllegalTransition",
    "Invariant",
    "PermissionDenied",
    "StateSpec",
    "Transition",
    "TransitionError",
    "UnknownAction",
    "apply",
    "can_fire",
    "enabled_transitions",
    "validate",
]
