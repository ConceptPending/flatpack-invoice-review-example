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
- **No approval with open errors.** The `approve` guard refuses to approve a
  batch that still has unresolved validation errors, so the invariant "an
  approved batch is clean" holds for every code path.

Guards and invariants are declarative expressions (app/statespec/expr.py): they
read `status`/`error_count` from the context snapshot the service supplies.
"""

from __future__ import annotations

from app.roles import APPROVER, REVIEWER
from app.statespec.core import Invariant, StateSpec, Transition
from app.statespec.expr import all_, any_, field

__all__ = ["BATCH_SPEC"]

_STATES = {
    "pending": "Uploaded and awaiting review.",
    "approved": "Cleared for downstream processing.",
    "rejected": "Declined — will not be processed.",
}


BATCH_SPEC = StateSpec(
    name="batch",
    title="Batch review lifecycle",
    states=_STATES,
    # Context contract — what a service snapshot must provide. actor_id is the
    # user firing the transition; uploaded_by_id is who uploaded the batch.
    fields={
        "status": "str",
        "error_count": "int",
        "actor_id": "uuid",
        "uploaded_by_id": "uuid",
    },
    initial="pending",
    terminal=frozenset({"approved", "rejected"}),
    transitions=(
        Transition(
            name="approve",
            sources=("pending",),
            dest="approved",
            roles=frozenset({APPROVER}),
            # Separation of duties (maker-checker): every validation error
            # resolved AND the approver is not the uploader.
            guard=all_(
                field("error_count").eq(0),
                field("actor_id").ne(field("uploaded_by_id")),
            ),
            label="Approve the batch — only when clean and by someone other "
            "than the uploader.",
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
            field("status").is_in(tuple(_STATES)),
            "The status is always one of the declared states.",
        ),
        Invariant(
            "approved_implies_clean",
            any_(field("status").ne("approved"), field("error_count").eq(0)),
            "An approved batch has no unresolved validation errors.",
        ),
    ),
)
