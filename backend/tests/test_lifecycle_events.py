"""Audit-layer tests: a transition writes one append-only LifecycleEvent,
atomically, with snapshotted roles + the exact policy digest + the evaluated
values. Mirrors the requirements in the audit design."""

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.user import User
from app.statespec.batch_spec import BATCH_SPEC
from app.statespec.identity import digest
from tests.test_batches import _fire, _login, _make_admin, _upload


async def _events(client, batch_id):
    r = await client.get(f"/api/admin/batches/{batch_id}/lifecycle-events")
    assert r.status_code == 200
    return r.json()


async def _approve_by_distinct(client, db_engine, batch_id, email="ap@example.com"):
    await _make_admin(db_engine, email, {"approver"})
    ap = await _login(client, email)
    return await _fire(client, ap, batch_id, "approve")


@pytest.mark.asyncio
async def test_successful_transition_writes_one_event(client, db_engine):
    up = await _login(client)
    batch_id = await _upload(client, up)
    assert (await _approve_by_distinct(client, db_engine, batch_id)).status_code == 200

    events = await _events(client, batch_id)
    assert len(events) == 1
    ev = events[0]
    assert ev["action"] == "approve"
    assert ev["previous_state"] == "pending" and ev["new_state"] == "approved"
    assert ev["outcome"] == "succeeded"
    # the transition bumps the optimistic-lock version by exactly one
    assert ev["entity_version_after"] == ev["entity_version_before"] + 1


@pytest.mark.asyncio
async def test_event_records_exact_policy_digest(client, db_engine):
    up = await _login(client)
    batch_id = await _upload(client, up)
    await _approve_by_distinct(client, db_engine, batch_id)
    ev = (await _events(client, batch_id))[0]
    assert ev["spec_name"] == "batch"
    assert ev["spec_version"] == BATCH_SPEC.version
    assert ev["spec_digest"] == digest(BATCH_SPEC)


@pytest.mark.asyncio
async def test_evidence_includes_evaluated_values(client, db_engine):
    up = await _login(client)
    batch_id = await _upload(client, up)
    await _approve_by_distinct(client, db_engine, batch_id)
    ev = (await _events(client, batch_id))[0]

    assert len(ev["guard_results"]) == 1
    guard = ev["guard_results"][0]
    assert guard["result"] is True
    # the maker-checker guard read these fields — recorded as evidence
    assert set(guard["inputs"]) == {"error_count", "actor_id", "uploaded_by_id"}
    assert guard["inputs"]["error_count"] == 0
    assert guard["inputs"]["actor_id"] != guard["inputs"]["uploaded_by_id"]
    # invariants were evaluated too
    assert {i["control_id"] for i in ev["invariant_results"]} == {
        "status_declared", "approved_implies_clean"
    }
    assert all(i["result"] for i in ev["invariant_results"])


@pytest.mark.asyncio
async def test_refused_transition_writes_no_event(client):
    up = await _login(client)  # bootstrap admin uploads AND holds approver
    batch_id = await _upload(client, up)
    # uploader can't approve own batch (maker-checker) -> 409
    assert (await _fire(client, up, batch_id, "approve")).status_code == 409
    # no successful event, and the state is unchanged (atomic)
    assert await _events(client, batch_id) == []
    assert (await client.get(f"/api/admin/batches/{batch_id}")).json()["status"] == "pending"


@pytest.mark.asyncio
async def test_roles_are_snapshotted_not_derived(client, db_engine):
    up = await _login(client)
    batch_id = await _upload(client, up)
    await _approve_by_distinct(client, db_engine, batch_id, email="snap@example.com")
    ev = (await _events(client, batch_id))[0]
    assert ev["actor_roles"] == ["approver"]

    # Strip the approver's roles AFTER the fact; the historical event is unchanged.
    sf = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    async with sf() as s:
        user = (await s.execute(
            select(User).where(User.email == "snap@example.com")
        )).scalar_one()
        user.roles = ""
        await s.commit()
    ev_again = (await _events(client, batch_id))[0]
    assert ev_again["actor_roles"] == ["approver"]  # still the role at the time


def test_event_service_is_append_only():
    from app.services.lifecycle_events import LifecycleEventService

    assert not hasattr(LifecycleEventService, "update")
    assert not hasattr(LifecycleEventService, "delete")
