from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

# Allowed currencies — kept as a tuple so we can pass it to Literal[] and
# also reference it from the field_validator below. Matches the Flatpack
# manifest's `validation_predicates` for currency:one_of.
Currency = Literal["GBP", "EUR", "USD"]


class InvoiceResponse(BaseModel):
    id: UUID
    supplier_id: UUID
    invoice_number: str
    invoice_date: date
    amount: Decimal
    currency: Currency
    batch_id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class InvoiceCorrection(BaseModel):
    """Payload for resolving a ValidationError by submitting corrected fields.

    Mirrors the Flatpack's manifest schema for an Invoice. Currency
    normalisation (upper + strip) happens here, at the API boundary,
    matching reference/decisions.md item A.
    """

    supplier_name: str = Field(..., min_length=1, max_length=255)
    invoice_number: str = Field(..., min_length=1, max_length=64)
    invoice_date: date
    amount: Decimal = Field(..., gt=0)
    currency: Currency = "GBP"

    @field_validator("currency", mode="before")
    @classmethod
    def normalise_currency(cls, v: str) -> str:
        # Carries over the Flatpack's normaliseCurrency(): upper + strip.
        # Runs BEFORE Pydantic's Literal check so a "gbp" input becomes
        # "GBP" which the Literal accepts.
        if v is None:
            return "GBP"
        return str(v).strip().upper()

    @field_validator("invoice_date")
    @classmethod
    def not_in_future(cls, v: date) -> date:
        # Carries over the Flatpack's "invoice_date must not be in the future".
        from datetime import date as _date

        if v > _date.today():
            raise ValueError("invoice_date must not be in the future")
        return v
