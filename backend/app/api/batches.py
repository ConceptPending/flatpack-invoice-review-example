from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_admin, roles_for
from app.models.user import User
from app.models.validation_error import ErrorResolution
from app.schemas.invoice import InvoiceResponse
from app.schemas.lifecycle import LifecycleSpecResponse
from app.schemas.review_batch import (
    BatchResponse,
    BatchTransition,
    UploadResult,
)
from app.schemas.validation_error import (
    ValidationErrorResolutionRequest,
    ValidationErrorResponse,
)
from app.services.batches import BatchService
from app.services.csv_parser import SCHEMA_FIELDS, to_csv
from app.services.suppliers import SupplierService
from app.statespec import (
    IllegalTransition,
    PermissionDenied,
    TransitionError,
    UnknownAction,
)
from app.statespec.batch_spec import BATCH_SPEC
from app.statespec.render import to_dict

router = APIRouter(
    prefix="/api/admin/batches",
    tags=["batches"],
    dependencies=[Depends(get_current_admin)],
)

# Map each enforcement error to the right HTTP status (guard rejection — e.g.
# unresolved errors — falls through to 409).
_ERROR_STATUS: dict[type[TransitionError], int] = {
    UnknownAction: 422,
    IllegalTransition: 409,
    PermissionDenied: 403,
}


@router.post("", response_model=UploadResult, status_code=201)
async def upload_batch(
    file: UploadFile,
    user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Upload a supplier-invoice CSV. Mirrors the Flatpack's drop-and-go
    flow, except authenticated and persisted.

    The adapted public-submission-and-admin-queue recipe lives here:
    the "public" surface is this authenticated upload endpoint, not an
    open form. See reference/decisions.md question 1.
    """
    raw = await file.read()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="File is not valid UTF-8")

    try:
        batch = await BatchService.create_from_csv(
            db,
            uploaded_by_id=user.id,
            source_filename=file.filename or "upload.csv",
            text=text,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # TODO(audit-log-recipe): emit batch.uploaded event.

    return UploadResult(
        batch=BatchResponse.model_validate(batch),
        clean_count=batch.clean_count,
        error_count=batch.error_count,
    )


@router.get("", response_model=list[BatchResponse])
async def list_batches(db: AsyncSession = Depends(get_db)):
    """The admin queue. Mirrors the public-submission recipe's
    /admin/submissions list."""
    return await BatchService.list_recent(db)


@router.get("/lifecycle", response_model=LifecycleSpecResponse)
async def get_lifecycle():
    """The batch review lifecycle as data — states, transitions, who-can-do-
    what, and the always-true guarantees. Read-only. Declared before the
    `/{batch_id}` route so the literal path isn't captured as an id."""
    return to_dict(BATCH_SPEC)


@router.get("/{batch_id}", response_model=BatchResponse)
async def get_batch(batch_id: UUID, db: AsyncSession = Depends(get_db)):
    batch = await BatchService.get(db, batch_id)
    if batch is None:
        raise HTTPException(status_code=404, detail="Batch not found")
    return batch


@router.post("/{batch_id}/transition", response_model=BatchResponse)
async def transition_batch(
    batch_id: UUID,
    body: BatchTransition,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    """Move the batch through its review lifecycle by firing a named action
    (`approve`, `reject`). Legality, permission, the no-open-errors guard, and
    separation of duties (the approver can't be the uploader) are enforced by
    the state-machine engine; this handler looks up the batch, supplies the
    actor's roles + id, and maps a refusal to an HTTP status.

    The two-step recipe walk (audit-log on every transition) is a TODO here —
    see backend/app/models/audit_log.py for the stub.
    """
    batch = await BatchService.get(db, batch_id)
    if batch is None:
        raise HTTPException(status_code=404, detail="Batch not found")
    try:
        batch = await BatchService.transition(
            db, batch, body.action, roles_for(admin), actor_id=admin.id
        )
    except TransitionError as exc:
        raise HTTPException(
            status_code=_ERROR_STATUS.get(type(exc), 409), detail=str(exc)
        ) from exc
    # TODO(audit-log-recipe): emit batch.status_changed event.
    return batch


@router.get("/{batch_id}/invoices", response_model=list[InvoiceResponse])
async def list_batch_invoices(batch_id: UUID, db: AsyncSession = Depends(get_db)):
    return await BatchService.clean_invoices(db, batch_id)


@router.get(
    "/{batch_id}/errors", response_model=list[ValidationErrorResponse]
)
async def list_batch_errors(batch_id: UUID, db: AsyncSession = Depends(get_db)):
    return await BatchService.errors(db, batch_id)


@router.post(
    "/{batch_id}/errors/{error_id}/resolve",
    response_model=ValidationErrorResponse,
)
async def resolve_error(
    batch_id: UUID,
    error_id: UUID,
    body: ValidationErrorResolutionRequest,
    user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Resolve a ValidationError. If 'corrected' + correction payload is
    supplied, persist the fix as an Invoice on this batch."""
    # Find the error
    errors = await BatchService.errors(db, batch_id)
    err = next((e for e in errors if e.id == error_id), None)
    if err is None:
        raise HTTPException(status_code=404, detail="Validation error not found")
    if err.resolution != ErrorResolution.unresolved:
        raise HTTPException(status_code=409, detail="Already resolved")

    if body.resolution == ErrorResolution.corrected:
        if body.correction is None:
            raise HTTPException(
                status_code=400,
                detail="resolution='corrected' requires a correction payload",
            )
        # Persist the corrected row as a real Invoice on this batch.
        from datetime import datetime, timezone

        from app.models.invoice import Invoice
        supplier = await SupplierService.get_or_create(
            db, body.correction.supplier_name
        )
        inv = Invoice(
            supplier_id=supplier.id,
            invoice_number=body.correction.invoice_number,
            invoice_date=body.correction.invoice_date,
            amount=body.correction.amount,
            currency=body.correction.currency,
            batch_id=batch_id,
        )
        db.add(inv)
        err.resolution = ErrorResolution.corrected
        err.resolved_to = body.correction.model_dump(mode="json")
        err.resolved_by_id = user.id
        err.resolved_at = datetime.now(timezone.utc)
        # Update the batch counts.
        batch = await BatchService.get(db, batch_id)
        if batch is not None:
            batch.clean_count += 1
            batch.error_count = max(0, batch.error_count - 1)
        await db.commit()
        await db.refresh(err)
        # TODO(audit-log-recipe): emit validation_error.resolved event.
        return err

    if body.resolution == ErrorResolution.dismissed:
        from datetime import datetime, timezone

        err.resolution = ErrorResolution.dismissed
        err.resolved_by_id = user.id
        err.resolved_at = datetime.now(timezone.utc)
        batch = await BatchService.get(db, batch_id)
        if batch is not None:
            batch.error_count = max(0, batch.error_count - 1)
        await db.commit()
        await db.refresh(err)
        # TODO(audit-log-recipe): emit validation_error.resolved event.
        return err

    raise HTTPException(status_code=400, detail="Unsupported resolution")


# Exports — these mirror the Flatpack's exports list verbatim.


@router.get("/{batch_id}/export-clean.csv")
async def export_clean_csv(batch_id: UUID, db: AsyncSession = Depends(get_db)):
    """Mirrors the Flatpack's `clean_csv` export."""
    batch = await BatchService.get(db, batch_id)
    if batch is None:
        raise HTTPException(status_code=404, detail="Batch not found")
    invoices = await BatchService.clean_invoices(db, batch_id)

    # We need supplier names; fetch in one query rather than N+1.
    from sqlalchemy import select

    from app.models.supplier import Supplier

    supplier_ids = list({inv.supplier_id for inv in invoices})
    suppliers_by_id: dict = {}
    if supplier_ids:
        result = await db.execute(
            select(Supplier).where(Supplier.id.in_(supplier_ids))
        )
        suppliers_by_id = {s.id: s for s in result.scalars().all()}

    header = SCHEMA_FIELDS
    rows: list[list[object]] = [header]
    for inv in invoices:
        rows.append([
            suppliers_by_id.get(inv.supplier_id).name if suppliers_by_id.get(inv.supplier_id) else "",
            inv.invoice_date.isoformat(),
            inv.invoice_number,
            str(inv.amount),
            inv.currency,
        ])
    csv_body = to_csv(rows)
    filename = (batch.source_filename or "input").rsplit(".csv", 1)[0] + ".clean.csv"
    return PlainTextResponse(
        csv_body,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{batch_id}/export-errors.csv")
async def export_errors_csv(batch_id: UUID, db: AsyncSession = Depends(get_db)):
    """Mirrors the Flatpack's `errors_csv` export."""
    batch = await BatchService.get(db, batch_id)
    if batch is None:
        raise HTTPException(status_code=404, detail="Batch not found")
    errors = await BatchService.errors(db, batch_id)
    header = ["reasons"] + SCHEMA_FIELDS
    rows: list[list[object]] = [header]
    for err in errors:
        if err.resolution != ErrorResolution.unresolved:
            continue
        original = err.original_row
        rows.append(
            ["; ".join(err.reasons)] + [original.get(f, "") for f in SCHEMA_FIELDS]
        )
    csv_body = to_csv(rows)
    filename = (batch.source_filename or "input").rsplit(".csv", 1)[0] + ".errors.csv"
    return PlainTextResponse(
        csv_body,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{batch_id}/summary")
async def batch_summary(batch_id: UUID, db: AsyncSession = Depends(get_db)):
    """Mirrors the Flatpack's `summary_print` export — totals by currency,
    counts, and the top issue reasons. Returned as JSON; rendered by the
    frontend or printed via the browser's print dialog.

    Frontend rendering is out of scope for this backend-only scaffold;
    see the project README "What's stubbed" section.
    """
    batch = await BatchService.get(db, batch_id)
    if batch is None:
        raise HTTPException(status_code=404, detail="Batch not found")
    totals = await BatchService.totals_by_currency(db, batch_id)
    errors = await BatchService.errors(db, batch_id)

    reason_counts: dict[str, int] = {}
    for err in errors:
        for reason in err.reasons:
            reason_counts[reason] = reason_counts.get(reason, 0) + 1
    top_reasons = sorted(reason_counts.items(), key=lambda kv: -kv[1])[:5]

    return {
        "batch": BatchResponse.model_validate(batch).model_dump(mode="json"),
        "totals_by_currency": {k: str(v) for k, v in totals.items()},
        "top_issue_reasons": [
            {"reason": r, "count": c} for r, c in top_reasons
        ],
    }
