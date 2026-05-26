"""Batch upload orchestration: parse CSV → validate → dedup → persist.

The cross-file invoice-number uniqueness rule (strengthened from the
Flatpack's per-file rule — see reference/promotion-plan.md) is enforced
here by querying for prior (supplier_id, invoice_number) pairs.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.invoice import Invoice
from app.models.review_batch import BatchStatus, ReviewBatch
from app.models.validation_error import ErrorResolution, ValidationError
from app.services.csv_parser import (
    SCHEMA_FIELDS,
    apply_mapping,
    auto_map,
    parse_csv,
)
from app.services.suppliers import SupplierService
from app.services.validation import normalise_currency, validate_row


class BatchService:
    @staticmethod
    async def create_from_csv(
        db: AsyncSession,
        *,
        uploaded_by_id: UUID,
        source_filename: str,
        text: str,
        mapping: dict[str, str] | None = None,
    ) -> ReviewBatch:
        """Upload, validate, persist. Returns the new ReviewBatch with
        counts populated."""

        # Parse + map.
        rows = parse_csv(text)
        if not rows:
            raise ValueError("CSV is empty")
        headers = [h.strip() for h in rows[0]]
        body = rows[1:]

        resolved_mapping = mapping or auto_map(headers)
        records = apply_mapping(body, headers, resolved_mapping)

        # Open the batch (pending).
        batch = ReviewBatch(
            uploaded_by_id=uploaded_by_id,
            source_filename=source_filename,
            status=BatchStatus.pending,
            clean_count=0,
            error_count=0,
        )
        db.add(batch)
        await db.flush()

        # First pass: per-row validation. Build a {supplier_name -> rows} map
        # so we can resolve suppliers once each.
        clean_rows: list[dict[str, str]] = []
        error_rows: list[tuple[dict[str, str], list[str]]] = []

        # Detect duplicates within the file (carries over the Flatpack's
        # rule; will be strengthened to cross-file below).
        seen_within_file: dict[tuple[str, str], int] = {}
        for i, row in enumerate(records, start=2):  # row 1 is the header
            reasons = validate_row(row)

            # Currency normalisation BEFORE persistence (matches Flatpack).
            if row.get("currency"):
                row["currency"] = normalise_currency(row["currency"])

            # Per-file duplicate (always an error, like the Flatpack).
            key = ((row.get("supplier_name") or "").strip(),
                   (row.get("invoice_number") or "").strip())
            if all(key) and key in seen_within_file:
                reasons.append(
                    f"Invoice number duplicates row {seen_within_file[key]} in this file"
                )
            elif all(key):
                seen_within_file[key] = i

            if reasons:
                error_rows.append((row, reasons))
            else:
                clean_rows.append(row)

        # Second pass: cross-file dedup (the strengthened rule).
        # We collect candidates' (supplier_name, invoice_number) pairs and
        # check the DB for any pre-existing Invoice on the matching Supplier.
        # The check happens *after* per-row validation so missing-field
        # errors are reported first.
        still_clean: list[dict[str, str]] = []
        for row in clean_rows:
            supplier_name = row["supplier_name"].strip()
            invoice_number = row["invoice_number"].strip()

            supplier = await SupplierService.get_by_name(db, supplier_name)
            if supplier is not None:
                existing = await db.execute(
                    select(Invoice).where(
                        Invoice.supplier_id == supplier.id,
                        Invoice.invoice_number == invoice_number,
                    )
                )
                prior = existing.scalar_one_or_none()
                if prior is not None:
                    error_rows.append((
                        row,
                        [f"Invoice number {invoice_number!r} already exists "
                         f"for supplier {supplier_name!r} (batch {prior.batch_id})"],
                    ))
                    continue
            still_clean.append(row)

        # Third pass: persist suppliers + clean invoices.
        for row in still_clean:
            supplier = await SupplierService.get_or_create(
                db, row["supplier_name"].strip()
            )
            inv = Invoice(
                supplier_id=supplier.id,
                invoice_number=row["invoice_number"].strip(),
                invoice_date=_parse_date_strict(row["invoice_date"]),
                amount=Decimal(row["amount"]),
                currency=row.get("currency") or "GBP",
                batch_id=batch.id,
            )
            db.add(inv)

        # Fourth pass: persist validation errors.
        for row, reasons in error_rows:
            ve = ValidationError(
                batch_id=batch.id,
                original_row={k: row.get(k, "") for k in SCHEMA_FIELDS},
                reasons=reasons,
                resolution=ErrorResolution.unresolved,
            )
            db.add(ve)

        # Update derived counts and commit.
        batch.clean_count = len(still_clean)
        batch.error_count = len(error_rows)
        await db.commit()
        await db.refresh(batch)
        return batch

    @staticmethod
    async def list_recent(db: AsyncSession, limit: int = 50) -> list[ReviewBatch]:
        result = await db.execute(
            select(ReviewBatch).order_by(ReviewBatch.created_at.desc()).limit(limit)
        )
        return list(result.scalars().all())

    @staticmethod
    async def get(db: AsyncSession, batch_id: UUID) -> ReviewBatch | None:
        return await db.get(ReviewBatch, batch_id)

    @staticmethod
    async def set_status(
        db: AsyncSession, batch: ReviewBatch, status: BatchStatus
    ) -> ReviewBatch:
        batch.status = status
        await db.commit()
        await db.refresh(batch)
        return batch

    @staticmethod
    async def clean_invoices(db: AsyncSession, batch_id: UUID) -> list[Invoice]:
        result = await db.execute(
            select(Invoice).where(Invoice.batch_id == batch_id).order_by(
                Invoice.invoice_date
            )
        )
        return list(result.scalars().all())

    @staticmethod
    async def errors(
        db: AsyncSession, batch_id: UUID
    ) -> list[ValidationError]:
        result = await db.execute(
            select(ValidationError)
            .where(ValidationError.batch_id == batch_id)
            .order_by(ValidationError.created_at)
        )
        return list(result.scalars().all())

    @staticmethod
    async def totals_by_currency(
        db: AsyncSession, batch_id: UUID
    ) -> dict[str, Decimal]:
        result = await db.execute(
            select(Invoice.currency, func.sum(Invoice.amount))
            .where(Invoice.batch_id == batch_id)
            .group_by(Invoice.currency)
        )
        return {row[0]: row[1] for row in result.all()}


def _parse_date_strict(s: str) -> dt.date:
    """Used only for already-validated rows. Mirrors the parser in
    services/validation.py but raises rather than returning None — by
    the time we reach this point validate_row() has confirmed parsability.
    """
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d"):
        try:
            return dt.datetime.strptime(s.strip(), fmt).date()
        except ValueError:
            continue
    raise ValueError(f"un-parseable date {s!r} reached persistence layer")
