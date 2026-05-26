from sqlalchemy import JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, uuid_pk


class Supplier(Base, TimestampMixin):
    """Reference list of suppliers.

    Introduced during the promotion from the Flatpack — see
    reference/promotion-plan.md "Supplier **CODE-INFERRED**" entity.

    The Flatpack stored supplier name as a free-text string on each
    invoice; the Baseplate version separates supplier identity so
    cross-batch reuse and alias matching are first-class.
    """

    __tablename__ = "suppliers"

    id = uuid_pk()
    name: Mapped[str] = mapped_column(String(255), unique=True, index=True)

    # aliases is a list[str]. Stored as JSON to keep SQLite test compatibility
    # (CLAUDE.md "Gotchas": backend tests use SQLite via aiosqlite). On
    # Postgres a native ARRAY(String) would be slightly nicer; the trade-off
    # was decided in reference/decisions.md.
    aliases: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
