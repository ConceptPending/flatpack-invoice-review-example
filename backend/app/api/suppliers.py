from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_admin
from app.schemas.supplier import SupplierCreate, SupplierResponse
from app.services.suppliers import SupplierService

router = APIRouter(
    prefix="/api/admin/suppliers",
    tags=["suppliers"],
    dependencies=[Depends(get_current_admin)],
)


@router.get("", response_model=list[SupplierResponse])
async def list_suppliers(db: AsyncSession = Depends(get_db)):
    return await SupplierService.list_all(db)


@router.post("", response_model=SupplierResponse, status_code=201)
async def create_supplier(body: SupplierCreate, db: AsyncSession = Depends(get_db)):
    existing = await SupplierService.get_by_name(db, body.name)
    if existing is not None:
        raise HTTPException(status_code=409, detail="Supplier already exists")
    return await SupplierService.create(db, body.name, body.aliases)


@router.get("/{supplier_id}", response_model=SupplierResponse)
async def get_supplier(supplier_id: UUID, db: AsyncSession = Depends(get_db)):
    s = await SupplierService.get(db, supplier_id)
    if s is None:
        raise HTTPException(status_code=404, detail="Supplier not found")
    return s
