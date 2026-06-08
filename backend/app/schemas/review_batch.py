from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

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


class BatchTransition(BaseModel):
    # The lifecycle action to fire (e.g. "approve"). Validated against the
    # spec by the engine, not here — one source of truth.
    action: str = Field(min_length=1)


class UploadResult(BaseModel):
    """Returned from POST /api/admin/batches (CSV upload)."""

    batch: BatchResponse
    clean_count: int
    error_count: int
