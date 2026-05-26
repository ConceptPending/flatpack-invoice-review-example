"""Integration tests for the upload → batch → exports flow.

The cross-file invoice-number uniqueness rule is the key test here —
the Flatpack only enforced per-file uniqueness; the Baseplate version
catches duplicates across batches. See reference/promotion-plan.md
"Validation rules (carry-over from manifest)" for the rule.
"""

import pytest

from tests.conftest import TEST_ADMIN_EMAIL

SAMPLE_CSV = """Vendor,Invoice Date,Invoice No.,Total,CCY
Acme Ltd,2026-01-15,INV-001,1200.50,GBP
Borealis Ops,2026-01-18,INV-002,840.00,EUR
"""

DUPE_CSV = """Vendor,Invoice Date,Invoice No.,Total,CCY
Acme Ltd,2026-01-22,INV-001,99.00,GBP
"""


async def _login(client) -> dict[str, str]:
    """Returns headers to use on subsequent writes."""
    resp = await client.post(
        "/api/auth/login",
        json={"email": TEST_ADMIN_EMAIL, "password": "testpass"},
    )
    assert resp.status_code == 200
    return {"X-CSRF-Token": resp.cookies["csrf_token"]}


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
async def test_batch_status_can_be_approved(client):
    headers = await _login(client)
    resp = await client.post(
        "/api/admin/batches",
        files={"file": ("input.csv", SAMPLE_CSV, "text/csv")},
        headers=headers,
    )
    batch_id = resp.json()["batch"]["id"]

    patch = await client.patch(
        f"/api/admin/batches/{batch_id}/status",
        json={"status": "approved"},
        headers=headers,
    )
    assert patch.status_code == 200
    assert patch.json()["status"] == "approved"


@pytest.mark.asyncio
async def test_upload_requires_auth(client):
    """No login → 403 from CSRF middleware before the route runs."""
    resp = await client.post(
        "/api/admin/batches",
        files={"file": ("upload.csv", SAMPLE_CSV, "text/csv")},
    )
    assert resp.status_code in (401, 403)
