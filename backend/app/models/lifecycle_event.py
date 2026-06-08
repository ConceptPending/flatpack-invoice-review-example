from datetime import datetime
from uuid import UUID

from sqlalchemy import JSON, Integer, String
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, uuid_pk


class LifecycleEvent(Base, TimestampMixin):
    """An append-only record of one state-machine transition: who did what, to
    which entity, **under which exact policy** (spec name + version + digest),
    and the structured evidence of every control that was evaluated.

    Purpose-built (not a generic app audit log). Append-only by convention —
    the service layer exposes no update or delete. `created_at` is the
    occurrence time. Roles and evaluated inputs are stored as *historical
    facts*: never re-derived from the current user or re-run against today's
    code. `entity_version_before/after` are recorded now so the schema is ready
    for optimistic concurrency (the next layer), even before it's enforced.
    """

    __tablename__ = "lifecycle_events"

    id = uuid_pk()  # the event_id

    # What entity, what happened.
    entity_type: Mapped[str] = mapped_column(String(64), index=True)
    entity_id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), index=True)
    action: Mapped[str] = mapped_column(String(64))
    transition_control_id: Mapped[str] = mapped_column(String(128))
    previous_state: Mapped[str] = mapped_column(String(32))
    new_state: Mapped[str] = mapped_column(String(32))
    outcome: Mapped[str] = mapped_column(String(32), default="succeeded")

    # Who — snapshotted at the time, not joined to the current user.
    actor_id: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True), nullable=True, index=True
    )
    actor_roles: Mapped[list] = mapped_column(JSON, default=list)

    # Under which exact policy.
    spec_name: Mapped[str] = mapped_column(String(64))
    spec_version: Mapped[int] = mapped_column(Integer)
    spec_digest: Mapped[str] = mapped_column(String(64))

    # Entity version (for optimistic concurrency, recorded now).
    entity_version_before: Mapped[int] = mapped_column(Integer)
    entity_version_after: Mapped[int] = mapped_column(Integer)

    request_id: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Structured rule-evaluation evidence: [{control_id, expression, result,
    # inputs}, ...]. The values evaluated, so a decision can be explained later
    # without re-running today's code.
    guard_results: Mapped[list] = mapped_column(JSON, default=list)
    invariant_results: Mapped[list] = mapped_column(JSON, default=list)

    @property
    def occurred_at(self) -> datetime:
        return self.created_at
