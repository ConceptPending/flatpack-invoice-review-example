from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class ItemCreate(BaseModel):
    name: str = Field(max_length=255)
    description: str | None = None


class ItemUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=255)
    description: str | None = None
    is_active: bool | None = None


class ItemResponse(BaseModel):
    id: UUID
    name: str
    description: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
