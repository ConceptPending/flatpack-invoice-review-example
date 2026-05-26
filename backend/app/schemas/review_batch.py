from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.models.review_batch import BatchStatus


class BatchResponse(BaseModel):
    id: UUID
    uploaded_by_id: UUID
    source_filename: str
    status: BatchStatus
    clean_count: int
    error_count: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class BatchStatusUpdate(BaseModel):
    status: BatchStatus


class UploadResult(BaseModel):
    """Returned from POST /api/admin/batches (CSV upload)."""

    batch: BatchResponse
    clean_count: int
    error_count: int
