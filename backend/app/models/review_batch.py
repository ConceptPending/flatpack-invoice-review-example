import uuid

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, uuid_pk
from app.statespec.batch_spec import BATCH_SPEC


class ReviewBatch(Base, TimestampMixin):
    """One CSV upload. Introduced during promotion to anchor the audit
    trail. See reference/promotion-plan.md 'ReviewBatch **INTERVIEW-REQUIRED**'.

    The decision to make batches (not individual invoices) the unit of
    approval is captured in reference/decisions.md question 2.
    """

    __tablename__ = "review_batches"

    id = uuid_pk()
    uploaded_by_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    source_filename: Mapped[str] = mapped_column(String(255))
    # Plain string, not a DB enum: app/statespec/batch_spec.py is the single
    # source of truth for the legal values and the transitions between them
    # (the engine keeps the column within the spec). Adding a state is a
    # spec change, not a database-enum migration.
    status: Mapped[str] = mapped_column(
        String(32),
        default=BATCH_SPEC.initial,
        server_default=BATCH_SPEC.initial,
        nullable=False,
        index=True,
    )

    # Derived counts, cached so list views don't N+1.
    clean_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Optimistic-lock version. SQLAlchemy bumps it on every row update and adds
    # `WHERE version = <loaded>` to UPDATEs (version_id_col below), so two
    # concurrent transitions on the same version can't both succeed — the loser
    # raises StaleDataError. Recorded before/after on each LifecycleEvent.
    version: Mapped[int] = mapped_column(
        Integer, default=1, server_default="1", nullable=False
    )

    __mapper_args__ = {"version_id_col": version}
