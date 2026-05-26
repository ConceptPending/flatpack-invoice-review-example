from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_admin
from app.schemas.item import ItemCreate, ItemResponse, ItemUpdate
from app.services.items import ItemService

# All routes in this router require an authenticated admin. If a route needs
# the User object itself, add `user: User = Depends(get_current_admin)` to its
# signature — but most routes only need the gate, not the value.
router = APIRouter(
    prefix="/api/admin/items",
    tags=["items"],
    dependencies=[Depends(get_current_admin)],
)


@router.get("", response_model=list[ItemResponse])
async def list_items(db: AsyncSession = Depends(get_db)):
    return await ItemService.list_all(db)


@router.post("", response_model=ItemResponse, status_code=201)
async def create_item(data: ItemCreate, db: AsyncSession = Depends(get_db)):
    return await ItemService.create(db, data)


@router.get("/{item_id}", response_model=ItemResponse)
async def get_item(item_id: str, db: AsyncSession = Depends(get_db)):
    item = await ItemService.get_by_id(db, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return item


@router.patch("/{item_id}", response_model=ItemResponse)
async def update_item(
    item_id: str,
    data: ItemUpdate,
    db: AsyncSession = Depends(get_db),
):
    item = await ItemService.update(db, item_id, data)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return item


@router.delete("/{item_id}", status_code=204)
async def delete_item(item_id: str, db: AsyncSession = Depends(get_db)):
    deleted = await ItemService.delete(db, item_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Item not found")
