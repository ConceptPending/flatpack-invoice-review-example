import uuid as _uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.item import Item
from app.schemas.item import ItemCreate, ItemUpdate


class ItemService:
    @staticmethod
    async def list_all(db: AsyncSession) -> list[Item]:
        result = await db.execute(select(Item).order_by(Item.created_at.desc()))
        return list(result.scalars().all())

    @staticmethod
    async def get_by_id(db: AsyncSession, item_id: str) -> Item | None:
        uid = _uuid.UUID(item_id) if isinstance(item_id, str) else item_id
        result = await db.execute(select(Item).where(Item.id == uid))
        return result.scalar_one_or_none()

    @staticmethod
    async def create(db: AsyncSession, data: ItemCreate) -> Item:
        item = Item(name=data.name, description=data.description)
        db.add(item)
        await db.commit()
        await db.refresh(item)
        return item

    @staticmethod
    async def update(db: AsyncSession, item_id: str, data: ItemUpdate) -> Item | None:
        item = await ItemService.get_by_id(db, item_id)
        if not item:
            return None
        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(item, key, value)
        await db.commit()
        await db.refresh(item)
        return item

    @staticmethod
    async def delete(db: AsyncSession, item_id: str) -> bool:
        item = await ItemService.get_by_id(db, item_id)
        if not item:
            return False
        await db.delete(item)
        await db.commit()
        return True
