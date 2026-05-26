# Recipe: Audit log

Record who did what, when. Useful for compliance work, case management,
internal review queues, or anything where "show me everything an admin
did to this record" is a real question.

This recipe builds an append-only `audit_log` table with a single-entry-
point service, hooks into existing CRUD on the example `Item`, exposes a
read endpoint for admins, and adds a frontend page to browse the trail.

## What you'll add

- `backend/app/models/audit_log.py` — the model
- A new alembic migration
- `backend/app/services/audit_log.py` — `record()` + `list_recent()`
- `backend/app/schemas/audit_log.py` — response schema
- `backend/app/api/audit_log.py` — `GET /api/admin/audit-log`
- Updates to `backend/app/api/items.py` — record entries on write
- `frontend/src/app/admin/audit-log/page.tsx` — the viewer
- Nav link in `frontend/src/app/admin/layout.tsx`
- Two backend tests

## 1. Model

`backend/app/models/audit_log.py`:

```python
from typing import Any
from uuid import UUID

from sqlalchemy import JSON, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, uuid_pk


class AuditLog(Base, TimestampMixin):
    __tablename__ = "audit_log"

    id = uuid_pk()
    # ON DELETE SET NULL so deleting a user doesn't lose their trail.
    user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    action: Mapped[str] = mapped_column(String(64), index=True)
    resource_type: Mapped[str] = mapped_column(String(64), index=True)
    resource_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    extra: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
```

Note `extra` (not `metadata`) — SQLAlchemy reserves `metadata` as a
declarative-base attribute. Register in `app/models/__init__.py`.

Generate and apply the migration:

```bash
make migrate-new msg="audit log"
make migrate
```

Read the generated migration before accepting it; autogenerate is a
starting point, not a verdict.

## 2. Service

`backend/app/services/audit_log.py`:

```python
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog


class AuditLogService:
    @staticmethod
    async def record(
        db: AsyncSession,
        *,
        user_id: UUID,
        action: str,
        resource_type: str,
        resource_id: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> AuditLog:
        """Single entry point for audit writes. Every callsite uses the
        same shape so log entries are queryable consistently."""
        entry = AuditLog(
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            extra=extra or {},
        )
        db.add(entry)
        await db.commit()
        await db.refresh(entry)
        return entry

    @staticmethod
    async def list_recent(db: AsyncSession, limit: int = 100) -> list[AuditLog]:
        result = await db.execute(
            select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit)
        )
        return list(result.scalars().all())
```

## 3. Response schema

`backend/app/schemas/audit_log.py`:

```python
from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel


class AuditLogResponse(BaseModel):
    id: UUID
    user_id: UUID | None
    action: str
    resource_type: str
    resource_id: str | None
    extra: dict[str, Any]
    created_at: datetime

    model_config = {"from_attributes": True}
```

## 4. Endpoint to read the log

`backend/app/api/audit_log.py`:

```python
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_admin
from app.schemas.audit_log import AuditLogResponse
from app.services.audit_log import AuditLogService

router = APIRouter(
    prefix="/api/admin/audit-log",
    tags=["audit-log"],
    dependencies=[Depends(get_current_admin)],
)


@router.get("", response_model=list[AuditLogResponse])
async def list_audit_log(db: AsyncSession = Depends(get_db)):
    return await AuditLogService.list_recent(db)
```

Register in `main.py`:

```python
from app.api import audit_log
app.include_router(audit_log.router)
```

Run `make generate-client` so the frontend picks up the new schema.

## 5. Hook into existing endpoints

The minimal change: routes that mutate state call `AuditLogService.record`
after the mutation succeeds.

The current `api/items.py` gates auth at the router level
(`dependencies=[Depends(get_current_admin)]`) so individual handlers
don't receive the `User`. Switch the mutating routes to accept the user
explicitly:

```python
from app.models.user import User
from app.services.audit_log import AuditLogService


@router.post("", response_model=ItemResponse, status_code=201)
async def create_item(
    data: ItemCreate,
    user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    item = await ItemService.create(db, data)
    await AuditLogService.record(
        db,
        user_id=user.id,
        action="create",
        resource_type="item",
        resource_id=str(item.id),
        extra={"name": item.name},
    )
    return item
```

Do the same for `update_item` (action="update", `extra=data.model_dump(exclude_unset=True)`)
and `delete_item` (action="delete"). The router-level dependency stays;
it's now redundant on the routes that take `user` directly but harmless.

## 6. Frontend

API client function in `frontend/src/lib/api.ts`:

```typescript
import type { components } from "./api-types";
type AuditLogEntry = components["schemas"]["AuditLogResponse"];

export async function getAuditLog() {
  return fetchAPI<AuditLogEntry[]>("/api/admin/audit-log", {
    credentials: "include",
  });
}
```

Page at `frontend/src/app/admin/audit-log/page.tsx`: follow the
`admin/items/page.tsx` shape — `useEffect` to load, ErrorBanner for
failures, a Card with a table. Format `created_at` as relative time;
render `extra` JSON in a `<pre>` block or pretty-print specific fields
per `action`.

Add the nav link in `frontend/src/app/admin/layout.tsx`:

```tsx
const NAV_ITEMS = [
  { href: "/admin", label: "Dashboard" },
  { href: "/admin/items", label: "Items" },
  { href: "/admin/audit-log", label: "Audit log" },
];
```

## 7. Tests

`backend/tests/test_audit_log.py`:

```python
import pytest

from tests.conftest import TEST_ADMIN_EMAIL


async def _login(client) -> str:
    resp = await client.post(
        "/api/auth/login",
        json={"email": TEST_ADMIN_EMAIL, "password": "testpass"},
    )
    assert resp.status_code == 200
    return resp.cookies["csrf_token"]


@pytest.mark.asyncio
async def test_create_item_writes_audit_entry(client):
    csrf = await _login(client)
    await client.post(
        "/api/admin/items",
        json={"name": "x"},
        headers={"X-CSRF-Token": csrf},
    )
    response = await client.get("/api/admin/audit-log")
    assert response.status_code == 200
    entries = response.json()
    assert any(
        e["action"] == "create" and e["resource_type"] == "item"
        for e in entries
    )


@pytest.mark.asyncio
async def test_audit_log_requires_admin(client):
    response = await client.get("/api/admin/audit-log")
    assert response.status_code == 401
```

## What to skip until you need it

- **Per-resource drill-down UI** — "show me everything about item X."
  Add when a stakeholder asks; the underlying data is already queryable.
- **`jsonb` GIN index on `extra`** — Postgres-specific optimisation
  for filtering on `extra->>'foo'`. Worth it when the log is large
  enough that `EXPLAIN ANALYZE` flags it. SQLite test backend uses
  plain JSON; the `JSON` column type works on both.
- **Tamper-evidence (hash chains, signed entries, write-only DB role)** —
  overkill unless compliance requires it. The append-only convention plus
  `ON DELETE SET NULL` on `user_id` is enough for most cases.
- **Pagination on `list_recent`** — the `limit=100` default is fine
  until you have a real volume. Add cursor pagination when needed.
- **Auto-recording from every mutation via a SQLAlchemy event listener** —
  tempting, but opaque. Explicit `.record()` calls per route keep the
  action name and `extra` payload meaningful and grep-able.
