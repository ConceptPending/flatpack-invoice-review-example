"""Authoritative transition facts + optimistic concurrency + the case simulator.

- The approval guard is evaluated against the *live* unresolved-error count, not
  the cached `error_count` — a drifted cache can't let an unclean batch through.
- Two transitions on the same batch version can't both succeed (optimistic lock).
- `GET /available-actions` reports what's allowed and why, without firing.
"""

from uuid import UUID

import pytest
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.review_batch import ReviewBatch
from app.services.batches import BatchService, TransitionConflict
from tests.test_batches import _fire, _login, _make_admin, _upload


def _sf(db_engine):
    return async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)


@pytest.mark.asyncio
async def test_approval_uses_authoritative_error_count_not_cache(client, db_engine):
    """Force the cached error_count to lie (set it to 0 while a real unresolved
    error row exists). The guard must still refuse — it counts the rows."""
    up = await _login(client)
    batch_id = await _upload(client, up, "Vendor,Invoice Date,Invoice No.,Total,CCY\n"
                                          "Acme Ltd,2026-01-15,INV-X,abc,GBP\n")  # 1 error
    # Corrupt the cache: pretend the batch is clean.
    async with _sf(db_engine)() as s:
        await s.execute(
            update(ReviewBatch).where(ReviewBatch.id == UUID(batch_id)).values(error_count=0)
        )
        await s.commit()
    await _make_admin(db_engine, "ap@example.com", {"approver"})
    ap = await _login(client, "ap@example.com")
    r = await _fire(client, ap, batch_id, "approve")
    assert r.status_code == 409  # authoritative count is 1 → guard refuses


@pytest.mark.asyncio
async def test_optimistic_lock_blocks_concurrent_transition(client, db_engine):
    """A transition fired against a stale entity version is refused with a
    conflict — two actors can't both transition the same version."""
    up = await _login(client)
    batch_id = await _upload(client, up)  # clean
    await _make_admin(db_engine, "a@example.com", {"approver"})
    a = await _user_id(db_engine, "a@example.com")
    bid = UUID(batch_id)

    sf = _sf(db_engine)
    async with sf() as s:
        batch = await BatchService.get(s, bid)  # loaded at version V
        # A concurrent change bumps the version behind our back.
        async with sf() as other:
            await other.execute(
                update(ReviewBatch).where(ReviewBatch.id == bid)
                .values(version=ReviewBatch.version + 1)
            )
            await other.commit()
        # Our transition still carries version V → 0 rows match → conflict.
        with pytest.raises(TransitionConflict):
            await BatchService.transition(
                s, batch, "approve", frozenset({"approver"}), actor_id=a
            )


async def _user_id(db_engine, email):
    from app.models.user import User
    async with _sf(db_engine)() as s:
        return (await s.execute(select(User).where(User.email == email))).scalar_one().id


@pytest.mark.asyncio
async def test_available_actions_explains_each(client, db_engine):
    """The simulator: as the uploader, approve is refused (maker-checker) and
    reject is allowed; as a distinct approver, approve is allowed."""
    up = await _login(client)
    batch_id = await _upload(client, up)

    # As the uploader (holds approver but is the uploader):
    r = await client.get(f"/api/admin/batches/{batch_id}/available-actions")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "pending"
    assert data["spec_digest"] and data["spec_version"] >= 1
    by = {a["action"]: a for a in data["actions"]}
    assert by["approve"]["allowed"] is False and "rejected" in by["approve"]["reason"]
    assert by["reject"]["allowed"] is True

    # As a distinct approver, approve becomes available (maker-checker satisfied).
    await _make_admin(db_engine, "checker@example.com", {"approver"})
    await _login(client, "checker@example.com")  # re-auths this client
    r2 = await client.get(f"/api/admin/batches/{batch_id}/available-actions")
    by2 = {a["action"]: a for a in r2.json()["actions"]}
    assert by2["approve"]["allowed"] is True
    assert by2["reject"]["allowed"] is True  # approver may also reject
