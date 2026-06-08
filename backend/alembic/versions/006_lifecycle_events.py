"""Lifecycle events (append-only audit) + review_batches.version

Adds the lifecycle_events table — who did what to which entity under which
exact policy (spec name/version/digest), with structured guard/invariant
evidence — and a `version` column on review_batches (bumped per transition;
recorded before/after on the event and the seam for optimistic concurrency).

Revision ID: 006
Revises: 005
Create Date: 2026-06-08 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "review_batches",
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
    )
    op.create_table(
        "lifecycle_events",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("entity_type", sa.String(64), nullable=False),
        sa.Column("entity_id", UUID(as_uuid=True), nullable=False),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("transition_control_id", sa.String(128), nullable=False),
        sa.Column("previous_state", sa.String(32), nullable=False),
        sa.Column("new_state", sa.String(32), nullable=False),
        sa.Column("outcome", sa.String(32), nullable=False, server_default="succeeded"),
        sa.Column("actor_id", UUID(as_uuid=True), nullable=True),
        sa.Column("actor_roles", sa.JSON, nullable=False),
        sa.Column("spec_name", sa.String(64), nullable=False),
        sa.Column("spec_version", sa.Integer, nullable=False),
        sa.Column("spec_digest", sa.String(64), nullable=False),
        sa.Column("entity_version_before", sa.Integer, nullable=False),
        sa.Column("entity_version_after", sa.Integer, nullable=False),
        sa.Column("request_id", sa.String(64), nullable=True),
        sa.Column("guard_results", sa.JSON, nullable=False),
        sa.Column("invariant_results", sa.JSON, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_lifecycle_events_entity_id", "lifecycle_events", ["entity_id"])
    op.create_index("ix_lifecycle_events_entity_type", "lifecycle_events", ["entity_type"])
    op.create_index("ix_lifecycle_events_actor_id", "lifecycle_events", ["actor_id"])


def downgrade() -> None:
    op.drop_table("lifecycle_events")
    op.drop_column("review_batches", "version")
