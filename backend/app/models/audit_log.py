"""Stub of the audit-log recipe's model.

Per reference/decisions.md and the project README, we apply admin-users
fully but stub audit-log and the adapted public-submission recipe.
This file matches the recipe's model exactly (see
docs/recipes/audit-log.md §1) so the migration is real and the table
gets created — but the service and route are skeleton-only.

TODO(recipe-application): finish walking docs/recipes/audit-log.md
so each batch-status transition, override, and supplier change emits
an audit entry. The list lives in
reference/promotion-plan.md → baseplate-target/recipes.md.
"""

from typing import Any
from uuid import UUID

from sqlalchemy import JSON, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, uuid_pk


class AuditLog(Base, TimestampMixin):
    __tablename__ = "audit_log"

    id = uuid_pk()
    user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    action: Mapped[str] = mapped_column(String(64), index=True)
    resource_type: Mapped[str] = mapped_column(String(64), index=True)
    resource_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    extra: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
