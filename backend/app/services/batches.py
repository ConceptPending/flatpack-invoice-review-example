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
from sqlalchemy.orm.exc import StaleDataError

from app.models.invoice import Invoice
from app.models.review_batch import ReviewBatch
from app.models.validation_error import ErrorResolution, ValidationError
from app.services.csv_parser import (
    SCHEMA_FIELDS,
    apply_mapping,
    auto_map,
    parse_csv,
)
from app.services.lifecycle_events import LifecycleEventService
from app.services.suppliers import SupplierService
from app.services.validation import normalise_currency, validate_row
from app.statespec import fire
from app.statespec.batch_spec import BATCH_SPEC


class TransitionConflict(Exception):
    """Another transition changed the batch concurrently (optimistic-lock
    version mismatch). The caller should reload and retry; the route maps it
    to HTTP 409."""


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
            status=BATCH_SPEC.initial,
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
    async def unresolved_error_count(db: AsyncSession, batch_id: UUID) -> int:
        """Count unresolved ValidationError rows — the *authoritative* fact the
        approval guard is evaluated against, derived in the transaction rather
        than trusting the cached `error_count` (which a bug or direct edit could
        drift)."""
        result = await db.execute(
            select(func.count())
            .select_from(ValidationError)
            .where(
                ValidationError.batch_id == batch_id,
                ValidationError.resolution == ErrorResolution.unresolved,
            )
        )
        return int(result.scalar_one())

    @staticmethod
    async def transition(
        db: AsyncSession,
        batch: ReviewBatch,
        action: str,
        actor_roles: frozenset[str],
        actor_id: UUID,
        request_id: str | None = None,
    ) -> ReviewBatch:
        """Fire a named lifecycle transition on a batch and record an
        append-only LifecycleEvent **in the same transaction** — so an approved
        batch can never exist without a record of who approved it under which
        policy. Decision logic lives in `fire` (legal state, actor permitted,
        guard incl. maker-checker, invariants); `fire` raises on refusal and the
        route maps that to HTTP (no event written on refusal).
        """
        previous_state = batch.status
        version_before = batch.version
        entity_id = batch.id  # captured now; a rollback would expire the object
        snapshot = {
            "status": batch.status,
            # Authoritative: count live unresolved-error rows, not the cache.
            "error_count": await BatchService.unresolved_error_count(db, batch.id),
            "actor_id": actor_id,
            "uploaded_by_id": batch.uploaded_by_id,
        }
        new_state, evaluations = fire(
            BATCH_SPEC, action, batch.status, actor_roles, snapshot
        )
        batch.status = new_state  # version_id_col bumps `version` on flush
        t = BATCH_SPEC.transition(action)
        LifecycleEventService.record(
            db,
            entity_type="review_batch",
            entity_id=batch.id,
            action=action,
            transition_control_id=(t.control_id or action),
            previous_state=previous_state,
            new_state=new_state,
            actor_id=actor_id,
            actor_roles=list(actor_roles),
            spec=BATCH_SPEC,
            evaluations=evaluations,
            entity_version_before=version_before,
            entity_version_after=version_before + 1,  # version_id_col bumps to this
            request_id=request_id,
        )
        try:
            # Atomic: the batch UPDATE (guarded by WHERE version=version_before)
            # and the event INSERT commit together. A concurrent transition that
            # already bumped the version makes this UPDATE match 0 rows.
            await db.commit()
        except StaleDataError as exc:
            await db.rollback()
            raise TransitionConflict(
                f"batch {entity_id} changed concurrently (expected version "
                f"{version_before})"
            ) from exc
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
