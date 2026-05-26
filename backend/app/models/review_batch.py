import enum
import uuid

from sqlalchemy import Enum, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, uuid_pk


class BatchStatus(str, enum.Enum):
    """ReviewBatch lifecycle. Mirrors the public-submission-and-admin-queue
    recipe's pending/approved/rejected pattern."""

    pending = "pending"
    approved = "approved"
    rejected = "rejected"


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
    status: Mapped[BatchStatus] = mapped_column(
        Enum(BatchStatus, name="batch_status"),
        default=BatchStatus.pending,
        nullable=False,
        index=True,
    )

    # Derived counts, cached so list views don't N+1.
    clean_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
