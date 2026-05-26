import datetime as dt
import enum
import uuid

from sqlalchemy import JSON, DateTime, Enum, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, uuid_pk


class ErrorResolution(str, enum.Enum):
    unresolved = "unresolved"
    corrected = "corrected"
    dismissed = "dismissed"


class ValidationError(Base, TimestampMixin):
    """A row that failed validation at import time.

    Persists across sessions so a reviewer can come back to it. In the
    Flatpack these lived in memory (state.errors); here they live as
    real rows so corrections survive page reloads and other users.

    See reference/promotion-plan.md "ValidationError **CODE-INFERRED**".
    """

    __tablename__ = "validation_errors"

    id = uuid_pk()
    batch_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("review_batches.id"), nullable=False, index=True
    )

    # The raw row from the CSV (already column-mapped to manifest field names
    # but before any type coercion).
    original_row: Mapped[dict] = mapped_column(JSON, nullable=False)

    # Plain-English reasons from the validator. Mirrors the Flatpack's
    # validateRow() output. Stored as JSON list for SQLite compatibility.
    reasons: Mapped[list[str]] = mapped_column(JSON, nullable=False)

    resolution: Mapped[ErrorResolution] = mapped_column(
        Enum(ErrorResolution, name="error_resolution"),
        default=ErrorResolution.unresolved,
        nullable=False,
        index=True,
    )
    resolved_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    resolved_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # The corrected row, if any. When resolution becomes "corrected" this
    # holds the payload used to create the matching Invoice.
    resolved_to: Mapped[dict | None] = mapped_column(JSON, nullable=True)
