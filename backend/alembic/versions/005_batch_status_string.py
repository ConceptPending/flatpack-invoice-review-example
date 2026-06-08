"""Convert review_batches.status from a DB enum to a plain string

The lifecycle-state-machine recipe makes app/statespec/batch_spec.py the single
source of truth for the legal status values. The original promotion used a
Postgres ENUM (`batch_status`); this converts the column to VARCHAR and drops
the now-redundant type, so adding a state is a spec change rather than a
database-enum migration. Postgres-only work — under SQLite the column is
already textual (tests build the schema from metadata, not migrations).

Revision ID: 005
Revises: 004
Create Date: 2026-06-08 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    op.alter_column(
        "review_batches",
        "status",
        type_=sa.String(32),
        existing_nullable=False,
        postgresql_using="status::text",
    )
    op.execute("DROP TYPE IF EXISTS batch_status")


def downgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute(
        "CREATE TYPE batch_status AS ENUM ('pending', 'approved', 'rejected')"
    )
    op.alter_column(
        "review_batches",
        "status",
        type_=sa.Enum("pending", "approved", "rejected", name="batch_status"),
        existing_nullable=False,
        postgresql_using="status::batch_status",
    )
