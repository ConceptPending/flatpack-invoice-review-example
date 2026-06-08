"""The generic state-machine engine: data model, enforcement, and analysis.

Nothing in here is invoice-specific. A `StateSpec` is pure data; `apply` is
the only place a transition is ever allowed to happen; `validate` proves a
spec is well-formed before it can mislead anyone. Keep this file small and
domain-free — that is what lets one Hypothesis test (driving `apply` over
random sequences) stand in as a correctness proof for *every* spec.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Callable, Mapping


# --- Data model -------------------------------------------------------------
#
# Guards and invariants are referenced by *name* from the spec and resolved to
# callables at enforcement time. This keeps the spec itself serialisable (a
# future layperson-facing viewer can read it without importing Python) while
# the predicates live in code next to the domain they describe.

# A guard answers: "given this entity's data, may the transition proceed?"
GuardFn = Callable[[Mapping[str, object]], bool]
# An invariant answers: "is the entity still internally consistent?" It is
# checked after every transition and must hold in every reachable state.
InvariantFn = Callable[[Mapping[str, object]], bool]


@dataclass(frozen=True)
class Transition:
    """A named, role-gated edge from one or more source states to a dest."""

    name: str
    sources: tuple[str, ...]
    dest: str
    # Roles permitted to fire this transition. Empty = no one (a deliberate
    # dead edge is a spec error; `validate` flags it).
    roles: frozenset[str] = frozenset()
    # Optional named guard predicate that must return True to proceed.
    guard: str | None = None
    # Plain-English description for the human-readable render.
    label: str = ""


@dataclass(frozen=True)
class Invariant:
    name: str
    predicate: InvariantFn
    label: str = ""


@dataclass(frozen=True)
class StateSpec:
    """A complete lifecycle: states, transitions, guards, invariants."""

    name: str
    title: str
    # state id -> human description
    states: Mapping[str, str]
    initial: str
    terminal: frozenset[str]
    transitions: tuple[Transition, ...]
    guards: Mapping[str, GuardFn] = field(default_factory=dict)
    invariants: tuple[Invariant, ...] = ()

    def transition(self, action: str) -> Transition | None:
        for t in self.transitions:
            if t.name == action:
                return t
        return None


# --- Enforcement errors -----------------------------------------------------


class TransitionError(Exception):
    """Base for every reason a transition can be refused."""


class UnknownAction(TransitionError):
    """The action name isn't defined in the spec at all."""


class IllegalTransition(TransitionError):
    """The action exists but not from the entity's current state."""


class PermissionDenied(TransitionError):
    """The actor's roles don't include any role permitted to fire it."""


class GuardRejected(TransitionError):
    """The action's guard predicate returned False for this entity."""


@dataclass(frozen=True)
class Decision:
    """The outcome of a `can_fire` check — allowed, or why not."""

    allowed: bool
    dest: str | None = None
    reason: str = ""
    error: type[TransitionError] | None = None


# --- The single enforcement path -------------------------------------------


def can_fire(
    spec: StateSpec,
    action: str,
    current_state: str,
    actor_roles: frozenset[str],
    entity: Mapping[str, object] | None = None,
) -> Decision:
    """Pure decision function. Never mutates anything; never raises.

    Checks, in order: action exists -> reachable from current state ->
    actor permitted -> guard holds. The ordering is deliberate and matches
    the error precedence callers (and tests) rely on.
    """
    t = spec.transition(action)
    if t is None:
        return Decision(False, reason=f"unknown action {action!r}", error=UnknownAction)
    if current_state not in t.sources:
        return Decision(
            False,
            reason=f"{action!r} not allowed from state {current_state!r}",
            error=IllegalTransition,
        )
    if not (actor_roles & t.roles):
        return Decision(
            False,
            reason=f"none of roles {set(actor_roles)} may fire {action!r}",
            error=PermissionDenied,
        )
    if t.guard is not None:
        guard = spec.guards.get(t.guard)
        if guard is None:
            # A spec that references a missing guard is a programming error,
            # not a runtime refusal — surface it loudly.
            raise KeyError(f"spec {spec.name!r} references unknown guard {t.guard!r}")
        if not guard(entity or {}):
            return Decision(
                False,
                reason=f"guard {t.guard!r} rejected {action!r}",
                error=GuardRejected,
            )
    return Decision(True, dest=t.dest, reason="ok")


def apply(
    spec: StateSpec,
    action: str,
    current_state: str,
    actor_roles: frozenset[str],
    entity: Mapping[str, object] | None = None,
) -> str:
    """Enforce a transition and return the destination state, or raise.

    This is the ONLY function the service layer should call to change an
    entity's lifecycle state. Routing every change through one generic
    interpreter is what makes the spec authoritative.
    """
    decision = can_fire(spec, action, current_state, actor_roles, entity)
    if not decision.allowed:
        assert decision.error is not None
        raise decision.error(decision.reason)
    assert decision.dest is not None
    return decision.dest


def enabled_transitions(
    spec: StateSpec,
    current_state: str,
    actor_roles: frozenset[str],
    entity: Mapping[str, object] | None = None,
) -> list[Transition]:
    """Every transition the given actor could fire right now."""
    return [
        t
        for t in spec.transitions
        if can_fire(spec, t.name, current_state, actor_roles, entity).allowed
    ]


# --- Static analysis (well-formedness) -------------------------------------


def reachable_states(spec: StateSpec) -> set[str]:
    """States reachable from `initial` by following transitions (roles/guards
    ignored — this is structural reachability)."""
    seen = {spec.initial}
    queue: deque[str] = deque([spec.initial])
    while queue:
        s = queue.popleft()
        for t in spec.transitions:
            if s in t.sources and t.dest not in seen:
                seen.add(t.dest)
                queue.append(t.dest)
    return seen


def _can_reach_terminal(spec: StateSpec, start: str) -> bool:
    if not spec.terminal:
        return True  # nothing to reach; treated as vacuously fine
    seen = {start}
    queue: deque[str] = deque([start])
    while queue:
        s = queue.popleft()
        if s in spec.terminal:
            return True
        for t in spec.transitions:
            if s in t.sources and t.dest not in seen:
                seen.add(t.dest)
                queue.append(t.dest)
    return False


def validate(spec: StateSpec) -> list[str]:
    """Return a list of human-readable problems. Empty list == well-formed.

    A well-formed spec has: a declared initial state; declared, terminal-only
    sink states; every state reachable from initial; every non-terminal state
    able to reach some terminal (no traps); no transition referencing an
    undeclared state, an empty role set, or a missing guard.
    """
    problems: list[str] = []
    states = set(spec.states)

    if spec.initial not in states:
        problems.append(f"initial state {spec.initial!r} is not declared")
    for term in spec.terminal:
        if term not in states:
            problems.append(f"terminal state {term!r} is not declared")

    for t in spec.transitions:
        for s in t.sources:
            if s not in states:
                problems.append(f"transition {t.name!r} has undeclared source {s!r}")
        if t.dest not in states:
            problems.append(f"transition {t.name!r} has undeclared dest {t.dest!r}")
        if t.dest in spec.terminal and False:
            pass  # transitions *into* terminals are fine
        if any(src in spec.terminal for src in t.sources):
            problems.append(
                f"transition {t.name!r} leaves terminal state(s) "
                f"{set(t.sources) & spec.terminal} — terminals must be sinks"
            )
        if not t.roles:
            problems.append(f"transition {t.name!r} has no permitted roles (dead edge)")
        if t.guard is not None and t.guard not in spec.guards:
            problems.append(
                f"transition {t.name!r} references unknown guard {t.guard!r}"
            )

    reachable = reachable_states(spec)
    for s in states - reachable:
        problems.append(f"state {s!r} is unreachable from initial {spec.initial!r}")

    for s in states - spec.terminal:
        if not _can_reach_terminal(spec, s):
            problems.append(f"state {s!r} cannot reach any terminal state (trap)")

    return problems
