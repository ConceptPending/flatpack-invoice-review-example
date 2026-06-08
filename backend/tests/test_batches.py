"""Integration tests for the upload → batch → exports flow.

The cross-file invoice-number uniqueness rule is the key test here —
the Flatpack only enforced per-file uniqueness; the Baseplate version
catches duplicates across batches. See reference/promotion-plan.md
"Validation rules (carry-over from manifest)" for the rule.
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.services.users import UserService
from tests.conftest import _TEST_HASH, TEST_ADMIN_EMAIL

SAMPLE_CSV = """Vendor,Invoice Date,Invoice No.,Total,CCY
Acme Ltd,2026-01-15,INV-001,1200.50,GBP
Borealis Ops,2026-01-18,INV-002,840.00,EUR
"""

DUPE_CSV = """Vendor,Invoice Date,Invoice No.,Total,CCY
Acme Ltd,2026-01-22,INV-001,99.00,GBP
"""

# One row with a non-numeric amount → one unresolved ValidationError, so the
# batch's error_count is 1 (used to exercise the approval guard).
ERROR_CSV = """Vendor,Invoice Date,Invoice No.,Total,CCY
Acme Ltd,2026-01-15,INV-900,abc,GBP
"""


async def _login(client, email: str = TEST_ADMIN_EMAIL) -> dict[str, str]:
    """Returns headers to use on subsequent writes."""
    resp = await client.post(
        "/api/auth/login",
        json={"email": email, "password": "testpass"},
    )
    assert resp.status_code == 200
    return {"X-CSRF-Token": resp.cookies["csrf_token"]}


async def _make_admin(db_engine, email: str, roles: set[str]):
    """Create an admin user holding exactly `roles` (password: testpass)."""
    sf = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    async with sf() as s:
        await UserService.create(
            s, email=email, password_hash=_TEST_HASH, is_admin=True, roles=roles
        )


async def _upload(client, headers, csv: str = SAMPLE_CSV) -> str:
    resp = await client.post(
        "/api/admin/batches",
        files={"file": ("input.csv", csv, "text/csv")},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["batch"]["id"]


async def _fire(client, headers, batch_id, action):
    return await client.post(
        f"/api/admin/batches/{batch_id}/transition",
        json={"action": action},
        headers=headers,
    )


@pytest.mark.asyncio
async def test_upload_creates_batch_with_clean_rows(client):
    headers = await _login(client)
    resp = await client.post(
        "/api/admin/batches",
        files={"file": ("upload.csv", SAMPLE_CSV, "text/csv")},
        headers=headers,
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["clean_count"] == 2
    assert body["error_count"] == 0
    assert body["batch"]["status"] == "pending"
    assert body["batch"]["source_filename"] == "upload.csv"


@pytest.mark.asyncio
async def test_upload_catches_cross_file_duplicate_invoice_number(client):
    """Carried over and strengthened: the Flatpack caught duplicates
    within a file; this test confirms we catch them across files too."""
    headers = await _login(client)

    # First upload — clean.
    resp1 = await client.post(
        "/api/admin/batches",
        files={"file": ("first.csv", SAMPLE_CSV, "text/csv")},
        headers=headers,
    )
    assert resp1.status_code == 201
    assert resp1.json()["clean_count"] == 2

    # Second upload — re-uses INV-001 on Acme Ltd. Cross-file dedup
    # should reject this row.
    resp2 = await client.post(
        "/api/admin/batches",
        files={"file": ("second.csv", DUPE_CSV, "text/csv")},
        headers=headers,
    )
    assert resp2.status_code == 201
    body2 = resp2.json()
    assert body2["clean_count"] == 0
    assert body2["error_count"] == 1


@pytest.mark.asyncio
async def test_export_clean_csv_round_trips(client):
    """The Flatpack's clean_csv export becomes an endpoint here."""
    headers = await _login(client)
    resp = await client.post(
        "/api/admin/batches",
        files={"file": ("input.csv", SAMPLE_CSV, "text/csv")},
        headers=headers,
    )
    assert resp.status_code == 201
    batch_id = resp.json()["batch"]["id"]

    export = await client.get(f"/api/admin/batches/{batch_id}/export-clean.csv")
    assert export.status_code == 200
    assert export.headers["content-type"].startswith("text/csv")
    text = export.text
    assert "supplier_name" in text  # header
    assert "Acme Ltd" in text
    assert "INV-001" in text


@pytest.mark.asyncio
async def test_summary_endpoint_groups_by_currency(client):
    """The Flatpack's summary_print export becomes a JSON endpoint."""
    headers = await _login(client)
    resp = await client.post(
        "/api/admin/batches",
        files={"file": ("input.csv", SAMPLE_CSV, "text/csv")},
        headers=headers,
    )
    assert resp.status_code == 201
    batch_id = resp.json()["batch"]["id"]

    summary = await client.get(f"/api/admin/batches/{batch_id}/summary")
    assert summary.status_code == 200
    body = summary.json()
    assert "totals_by_currency" in body
    # SAMPLE_CSV has one GBP invoice (1200.50) and one EUR invoice (840.00).
    assert "GBP" in body["totals_by_currency"]
    assert "EUR" in body["totals_by_currency"]


@pytest.mark.asyncio
async def test_clean_batch_can_be_approved(client):
    headers = await _login(client)  # bootstrap admin holds all roles
    batch_id = await _upload(client, headers, SAMPLE_CSV)
    r = await _fire(client, headers, batch_id, "approve")
    assert r.status_code == 200
    assert r.json()["status"] == "approved"


@pytest.mark.asyncio
async def test_cannot_approve_batch_with_open_errors(client):
    """The no-unresolved-errors guard: a batch with validation errors can't be
    approved (409), but it can still be rejected."""
    headers = await _login(client)
    batch_id = await _upload(client, headers, ERROR_CSV)  # error_count == 1
    r = await _fire(client, headers, batch_id, "approve")
    assert r.status_code == 409
    assert "guard" in r.json()["detail"].lower() or "error" in r.json()["detail"].lower()
    # rejection is unguarded
    r = await _fire(client, headers, batch_id, "reject")
    assert r.status_code == 200 and r.json()["status"] == "rejected"


@pytest.mark.asyncio
async def test_illegal_and_unknown_transitions(client):
    headers = await _login(client)
    batch_id = await _upload(client, headers, SAMPLE_CSV)
    # reject -> rejected (terminal); approving a rejected batch is illegal
    assert (await _fire(client, headers, batch_id, "reject")).status_code == 200
    assert (await _fire(client, headers, batch_id, "approve")).status_code == 409
    # made-up action
    assert (await _fire(client, headers, batch_id, "teleport")).status_code == 422


@pytest.mark.asyncio
async def test_separation_of_duties(client, db_engine):
    """A reviewer-only admin may reject but not approve; an approver may
    approve. Enforced by each user's roles column through the engine."""
    admin_headers = await _login(client)
    clean = await _upload(client, admin_headers, SAMPLE_CSV)
    other = await _upload(client, admin_headers, SAMPLE_CSV)

    await _make_admin(db_engine, "reviewer@example.com", {"reviewer"})
    rv_headers = await _login(client, "reviewer@example.com")
    # reviewer cannot approve...
    assert (await _fire(client, rv_headers, clean, "approve")).status_code == 403
    # ...but can reject
    assert (await _fire(client, rv_headers, other, "reject")).status_code == 200

    await _make_admin(db_engine, "approver@example.com", {"approver"})
    ap_headers = await _login(client, "approver@example.com")
    assert (await _fire(client, ap_headers, clean, "approve")).status_code == 200


@pytest.mark.asyncio
async def test_lifecycle_endpoint(client):
    await _login(client)
    r = await client.get("/api/admin/batches/lifecycle")
    assert r.status_code == 200
    data = r.json()
    assert data["initial"] == "pending"
    approve = next(t for t in data["transitions"] if t["name"] == "approve")
    assert approve["roles"] == ["approver"]
    # guard is now a structured expression tree + rendered text
    assert approve["guard_text"] == "error_count = 0"
    assert approve["guard"]["kind"] == "compare" and approve["guard"]["op"] == "eq"


@pytest.mark.asyncio
async def test_upload_requires_auth(client):
    """No login → 403 from CSRF middleware before the route runs."""
    resp = await client.post(
        "/api/admin/batches",
        files={"file": ("upload.csv", SAMPLE_CSV, "text/csv")},
    )
    assert resp.status_code in (401, 403)
