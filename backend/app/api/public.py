from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.item import Item
from app.schemas.item import ItemResponse

router = APIRouter(prefix="/api/public", tags=["public"])


@router.get("/items", response_model=list[ItemResponse])
async def list_active_items(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Item).where(Item.is_active.is_(True)).order_by(Item.created_at.desc())
    )
    return result.scalars().all()
