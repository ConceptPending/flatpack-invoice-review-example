from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.supplier import Supplier


class SupplierService:
    """Strict-name-only supplier matching for v1.

    Per reference/decisions.md item 5: alias-based auto-matching is
    v2. For now, two invoices with different supplier_name strings
    create two different Supplier rows. A reviewer can manually merge
    later (post-v1).
    """

    @staticmethod
    async def get_by_name(db: AsyncSession, name: str) -> Supplier | None:
        result = await db.execute(
            select(Supplier).where(Supplier.name == name.strip())
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_or_create(db: AsyncSession, name: str) -> Supplier:
        normalised = name.strip()
        existing = await SupplierService.get_by_name(db, normalised)
        if existing:
            return existing
        supplier = Supplier(name=normalised, aliases=[])
        db.add(supplier)
        await db.commit()
        await db.refresh(supplier)
        return supplier

    @staticmethod
    async def list_all(db: AsyncSession) -> list[Supplier]:
        result = await db.execute(select(Supplier).order_by(Supplier.name))
        return list(result.scalars().all())

    @staticmethod
    async def create(db: AsyncSession, name: str, aliases: list[str]) -> Supplier:
        supplier = Supplier(name=name.strip(), aliases=list(aliases))
        db.add(supplier)
        await db.commit()
        await db.refresh(supplier)
        return supplier

    @staticmethod
    async def get(db: AsyncSession, supplier_id: UUID) -> Supplier | None:
        return await db.get(Supplier, supplier_id)
