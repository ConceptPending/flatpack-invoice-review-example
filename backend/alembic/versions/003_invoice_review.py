"""Drop items, add suppliers + review_batches + invoices + validation_errors + audit_log

Revision ID: 003
Revises: 002
Create Date: 2026-05-26 00:00:00.000000

Promotion from the Flatpack at
github.com/ConceptPending/flatpack/examples/invoice-cleaner.html v0.2.0.

The four primary entities come from reference/promotion-plan.md. The
audit_log table is the audit-log recipe stub — table created, hooks
not wired yet (see TODO(audit-log-recipe) markers in app/api/batches.py).
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop the example Item table — replaced by the four entities below.
    op.drop_table("items")

    # Suppliers — reference list, separated from invoice strings during promotion.
    op.create_table(
        "suppliers",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("aliases", sa.JSON, nullable=False, server_default="[]"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
    )
    op.create_index("ix_suppliers_name", "suppliers", ["name"], unique=True)

    # Review batches — one CSV upload, with a status workflow.
    batch_status = sa.Enum(
        "pending", "approved", "rejected", name="batch_status"
    )
    op.create_table(
        "review_batches",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "uploaded_by_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column("source_filename", sa.String(255), nullable=False),
        sa.Column(
            "status", batch_status, nullable=False, server_default="pending"
        ),
        sa.Column("clean_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("error_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
    )
    op.create_index(
        "ix_review_batches_uploaded_by_id", "review_batches", ["uploaded_by_id"]
    )
    op.create_index("ix_review_batches_status", "review_batches", ["status"])

    # Invoices — promoted directly from the Flatpack manifest's only entity.
    op.create_table(
        "invoices",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "supplier_id",
            UUID(as_uuid=True),
            sa.ForeignKey("suppliers.id"),
            nullable=False,
        ),
        sa.Column("invoice_number", sa.String(64), nullable=False),
        sa.Column("invoice_date", sa.Date, nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column(
            "currency", sa.String(3), nullable=False, server_default="GBP"
        ),
        sa.Column(
            "batch_id",
            UUID(as_uuid=True),
            sa.ForeignKey("review_batches.id"),
            nullable=False,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
        # Strengthened from the Flatpack: cross-file uniqueness per supplier.
        sa.UniqueConstraint(
            "supplier_id", "invoice_number", name="uq_supplier_invoice_number"
        ),
    )
    op.create_index("ix_invoices_supplier_id", "invoices", ["supplier_id"])
    op.create_index("ix_invoices_batch_id", "invoices", ["batch_id"])
    op.create_index("ix_invoices_invoice_date", "invoices", ["invoice_date"])

    # Validation errors — Flatpack's in-memory state.errors persisted here.
    error_resolution = sa.Enum(
        "unresolved", "corrected", "dismissed", name="error_resolution"
    )
    op.create_table(
        "validation_errors",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "batch_id",
            UUID(as_uuid=True),
            sa.ForeignKey("review_batches.id"),
            nullable=False,
        ),
        sa.Column("original_row", sa.JSON, nullable=False),
        sa.Column("reasons", sa.JSON, nullable=False),
        sa.Column(
            "resolution",
            error_resolution,
            nullable=False,
            server_default="unresolved",
        ),
        sa.Column(
            "resolved_by_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True
        ),
        sa.Column(
            "resolved_at", sa.DateTime(timezone=True), nullable=True
        ),
        sa.Column("resolved_to", sa.JSON, nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
    )
    op.create_index(
        "ix_validation_errors_batch_id", "validation_errors", ["batch_id"]
    )
    op.create_index(
        "ix_validation_errors_resolution", "validation_errors", ["resolution"]
    )

    # Audit log — table created per the recipe stub. Hooks not wired yet.
    op.create_table(
        "audit_log",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("resource_type", sa.String(64), nullable=False),
        sa.Column("resource_id", sa.String(64), nullable=True),
        sa.Column("extra", sa.JSON, nullable=False, server_default="{}"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
    )
    op.create_index("ix_audit_log_user_id", "audit_log", ["user_id"])
    op.create_index("ix_audit_log_action", "audit_log", ["action"])
    op.create_index("ix_audit_log_resource_type", "audit_log", ["resource_type"])


def downgrade() -> None:
    op.drop_index("ix_audit_log_resource_type", table_name="audit_log")
    op.drop_index("ix_audit_log_action", table_name="audit_log")
    op.drop_index("ix_audit_log_user_id", table_name="audit_log")
    op.drop_table("audit_log")

    op.drop_index(
        "ix_validation_errors_resolution", table_name="validation_errors"
    )
    op.drop_index(
        "ix_validation_errors_batch_id", table_name="validation_errors"
    )
    op.drop_table("validation_errors")
    op.execute("DROP TYPE IF EXISTS error_resolution")

    op.drop_index("ix_invoices_invoice_date", table_name="invoices")
    op.drop_index("ix_invoices_batch_id", table_name="invoices")
    op.drop_index("ix_invoices_supplier_id", table_name="invoices")
    op.drop_table("invoices")

    op.drop_index("ix_review_batches_status", table_name="review_batches")
    op.drop_index(
        "ix_review_batches_uploaded_by_id", table_name="review_batches"
    )
    op.drop_table("review_batches")
    op.execute("DROP TYPE IF EXISTS batch_status")

    op.drop_index("ix_suppliers_name", table_name="suppliers")
    op.drop_table("suppliers")

    # Recreate items table to match revision 001.
    op.create_table(
        "items",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column(
            "is_active", sa.Boolean, nullable=False, server_default="true"
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
    )
