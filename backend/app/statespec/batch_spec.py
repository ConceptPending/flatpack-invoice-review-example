"""The ReviewBatch approval lifecycle, as a declarative spec.

This is the Baseplate `lifecycle-state-machine` recipe applied to this project:
the `ReviewBatch.status` field was a bare enum changed by an unguarded
`set_status` (any value -> any value, no permission check). Modelling it as a
spec makes three rules real and enforced in one place:

- **Legal transitions only.** A batch can be approved or rejected from
  `pending`; the terminal states are sinks (you can't re-approve a rejected
  batch).
- **Separation of duties.** A `reviewer` can reject; only an `approver` can
  approve a batch for downstream processing.
- **No approval with open errors.** The `no_unresolved_errors` guard refuses to
  approve a batch that still has unresolved validation errors — so the
  invariant "an approved batch is clean" holds for every code path.

The guard reads `error_count` from a snapshot the service supplies, keeping the
predicate pure.
"""

from __future__ import annotations

from typing import Mapping

from app.roles import APPROVER, REVIEWER
from app.statespec.core import Invariant, StateSpec, Transition

__all__ = ["BATCH_SPEC"]


def _no_unresolved_errors(entity: Mapping[str, object]) -> bool:
    return int(entity.get("error_count", 0) or 0) == 0


def _status_declared(e: Mapping[str, object]) -> bool:
    return e.get("status") in _STATES


def _approved_implies_clean(e: Mapping[str, object]) -> bool:
    if e.get("status") == "approved":
        return int(e.get("error_count", 0) or 0) == 0
    return True


_STATES = {
    "pending": "Uploaded and awaiting review.",
    "approved": "Cleared for downstream processing.",
    "rejected": "Declined — will not be processed.",
}


BATCH_SPEC = StateSpec(
    name="batch",
    title="Batch review lifecycle",
    states=_STATES,
    initial="pending",
    terminal=frozenset({"approved", "rejected"}),
    guards={"no_unresolved_errors": _no_unresolved_errors},
    transitions=(
        Transition(
            name="approve",
            sources=("pending",),
            dest="approved",
            roles=frozenset({APPROVER}),
            guard="no_unresolved_errors",
            label="Approve the batch (only when every validation error is resolved).",
        ),
        Transition(
            name="reject",
            sources=("pending",),
            dest="rejected",
            roles=frozenset({REVIEWER, APPROVER}),
            label="Reject the batch (final).",
        ),
    ),
    invariants=(
        Invariant(
            "status_declared",
            _status_declared,
            "The status is always one of the declared states.",
        ),
        Invariant(
            "approved_implies_clean",
            _approved_implies_clean,
            "An approved batch has no unresolved validation errors.",
        ),
    ),
)
