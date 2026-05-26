import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, uuid_pk


class Invoice(Base, TimestampMixin):
    """A supplier invoice that passed validation. Carried over from the
    Flatpack manifest's only entity.

    Constraints strengthened from the Flatpack:
    - Per-supplier invoice_number uniqueness is enforced **across all
      batches** (the Flatpack only enforced uniqueness within a file).
      Captured in reference/promotion-plan.md "Validation rules
      (carry-over from manifest)".
    """

    __tablename__ = "invoices"
    __table_args__ = (
        # The strengthened uniqueness rule. The Flatpack's per-file rule
        # was a limitation, not a business rule — see
        # reference/promotion-plan.md.
        UniqueConstraint("supplier_id", "invoice_number", name="uq_supplier_invoice_number"),
    )

    id = uuid_pk()
    supplier_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("suppliers.id"), nullable=False, index=True
    )
    invoice_number: Mapped[str] = mapped_column(String(64), nullable=False)
    invoice_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="GBP")
    batch_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("review_batches.id"), nullable=False, index=True
    )
