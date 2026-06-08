"""User lifecycle roles column

Adds `users.roles` — a sorted CSV of lifecycle roles (see app/roles.py) that
gates which batch-review transitions a user may fire. Orthogonal to is_admin.

Backfill: existing admins are granted every known role, so upgrading a live
deployment never strips power from people who already had it. New users get an
explicit (empty) grant and are assigned roles deliberately.

Revision ID: 004
Revises: 003
Create Date: 2026-06-08 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Frozen literal — a historical record that must not shift if the role
# catalogue grows later.
_ADMIN_BACKFILL = "approver,reviewer"


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("roles", sa.String(255), nullable=False, server_default=""),
    )
    users = sa.table(
        "users", sa.column("roles", sa.String), sa.column("is_admin", sa.Boolean)
    )
    op.execute(
        users.update().where(users.c.is_admin.is_(True)).values(roles=_ADMIN_BACKFILL)
    )


def downgrade() -> None:
    op.drop_column("users", "roles")
