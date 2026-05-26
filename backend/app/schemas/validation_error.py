from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.models.validation_error import ErrorResolution
from app.schemas.invoice import InvoiceCorrection


class ValidationErrorResponse(BaseModel):
    id: UUID
    batch_id: UUID
    original_row: dict
    reasons: list[str]
    resolution: ErrorResolution
    resolved_by_id: UUID | None
    resolved_at: datetime | None
    resolved_to: dict | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ValidationErrorResolutionRequest(BaseModel):
    """How a reviewer resolves a ValidationError.

    Two shapes:
      - resolution=corrected + correction payload → creates an Invoice.
      - resolution=dismissed → just records the dismissal.
    """

    resolution: ErrorResolution
    correction: InvoiceCorrection | None = None
