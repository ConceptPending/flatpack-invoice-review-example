from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, uuid_pk
from app.roles import parse_roles


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id = uuid_pk()
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    is_admin: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false"
    )
    # Lifecycle roles this user holds, as a sorted CSV (see app/roles.py).
    # Orthogonal to is_admin: is_admin gates the admin area; roles gate which
    # lifecycle actions the admin may perform.
    roles: Mapped[str] = mapped_column(String(255), default="", server_default="")

    @property
    def role_set(self) -> frozenset[str]:
        """The user's roles as a set — the form the lifecycle engine wants."""
        return parse_roles(self.roles)
