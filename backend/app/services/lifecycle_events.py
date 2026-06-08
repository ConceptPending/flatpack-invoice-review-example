"""Append-only writer + reader for LifecycleEvent.

`record` adds an event to the session but does NOT commit — the caller commits
it in the *same transaction* as the entity update, so a transition and its
evidence are atomic (no approved batch without a record of who approved it).
There is deliberately no update or delete: the log is append-only.
"""

import datetime as dt
import uuid as _uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.lifecycle_event import LifecycleEvent
from app.statespec import Evaluation
from app.statespec.core import StateSpec
from app.statespec.identity import digest


def _jsonable(value: object) -> object:
    if isinstance(value, _uuid.UUID):
        return str(value)
    if isinstance(value, Decimal):
        return format(value.normalize(), "f")
    if isinstance(value, dt.date):
        return value.isoformat()
    return value


def _evidence(evaluations: list[Evaluation], kind: str) -> list[dict]:
    return [
        {
            "control_id": e.control_id,
            "expression": e.expression,  # already a JSON-safe expr tree
            "result": e.result,
            "inputs": {k: _jsonable(v) for k, v in e.inputs.items()},
        }
        for e in evaluations
        if e.kind == kind
    ]


class LifecycleEventService:
    @staticmethod
    def record(
        db: AsyncSession,
        *,
        entity_type: str,
        entity_id: _uuid.UUID,
        action: str,
        transition_control_id: str,
        previous_state: str,
        new_state: str,
        actor_id: _uuid.UUID | None,
        actor_roles: list[str],
        spec: StateSpec,
        evaluations: list[Evaluation],
        entity_version_before: int,
        entity_version_after: int,
        request_id: str | None = None,
        outcome: str = "succeeded",
    ) -> LifecycleEvent:
        """Build + stage (not commit) a lifecycle event. Roles + evaluated
        inputs are stored as historical facts."""
        event = LifecycleEvent(
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            transition_control_id=transition_control_id,
            previous_state=previous_state,
            new_state=new_state,
            outcome=outcome,
            actor_id=actor_id,
            actor_roles=sorted(actor_roles),
            spec_name=spec.name,
            spec_version=spec.version,
            spec_digest=digest(spec),
            entity_version_before=entity_version_before,
            entity_version_after=entity_version_after,
            request_id=request_id,
            guard_results=_evidence(evaluations, "guard"),
            invariant_results=_evidence(evaluations, "invariant"),
        )
        db.add(event)
        return event

    @staticmethod
    async def list_for_entity(
        db: AsyncSession, entity_type: str, entity_id: _uuid.UUID
    ) -> list[LifecycleEvent]:
        result = await db.execute(
            select(LifecycleEvent)
            .where(
                LifecycleEvent.entity_type == entity_type,
                LifecycleEvent.entity_id == entity_id,
            )
            .order_by(LifecycleEvent.created_at)
        )
        return list(result.scalars().all())
