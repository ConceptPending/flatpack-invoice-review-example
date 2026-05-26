from uuid import UUID

from pydantic import BaseModel, Field


class SupplierCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    aliases: list[str] = Field(default_factory=list)


class SupplierResponse(BaseModel):
    id: UUID
    name: str
    aliases: list[str]

    model_config = {"from_attributes": True}
