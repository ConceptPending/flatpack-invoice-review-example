# Recipe: Public submission + admin queue

The classic "intake + review" pattern. The public submits something
unauthenticated (an application, a complaint, a content moderation flag,
a candidate, a tip), then an authenticated admin reviews it in a queue
and moves it through a status workflow.

This is one of the most useful shapes for the kinds of apps Baseplate
targets — directories with user-submitted entries, internal review
tools, simple CMS-with-submissions, lightweight case intake.

## What you'll add

Backend:
- `backend/app/models/submission.py` — model with status enum
- New alembic migration
- `backend/app/services/submissions.py` — `create()`, `list_by_status()`, `update_status()`
- `backend/app/schemas/submission.py` — `SubmissionCreate`, `SubmissionResponse`, `SubmissionUpdate`
- `backend/app/api/submissions_public.py` — public `POST /api/submissions`
- `backend/app/api/submissions_admin.py` — admin list + status PATCH
- **CSRF exemption** for the public submit endpoint
- **Per-endpoint rate limit** for the public submit endpoint
- Tests for both public + admin flows

Frontend:
- `frontend/src/app/submit/page.tsx` — public form (no auth)
- `frontend/src/app/admin/submissions/page.tsx` — review queue
- API client functions
- Nav link in admin sidebar

## 1. Model

`backend/app/models/submission.py`:

```python
import enum
from sqlalchemy import Enum, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, uuid_pk


class SubmissionStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"


class Submission(Base, TimestampMixin):
    __tablename__ = "submissions"

    id = uuid_pk()
    # Replace with whatever fields the submission collects.
    name: Mapped[str] = mapped_column(String(255))
    email: Mapped[str] = mapped_column(String(255))
    message: Mapped[str] = mapped_column(Text)

    status: Mapped[SubmissionStatus] = mapped_column(
        Enum(SubmissionStatus, name="submission_status"),
        default=SubmissionStatus.pending,
        index=True,
    )
    # Set by admin when status transitions out of pending.
    reviewer_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
```

Register in `app/models/__init__.py`. Generate + apply migration.

## 2. Schemas

`backend/app/schemas/submission.py`:

```python
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

from app.models.submission import SubmissionStatus


class SubmissionCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    email: EmailStr
    message: str = Field(min_length=1, max_length=10_000)


class SubmissionUpdate(BaseModel):
    status: SubmissionStatus
    reviewer_notes: str | None = None


class SubmissionResponse(BaseModel):
    id: UUID
    name: str
    email: EmailStr
    message: str
    status: SubmissionStatus
    reviewer_notes: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
```

## 3. Service

`backend/app/services/submissions.py`:

```python
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.submission import Submission, SubmissionStatus
from app.schemas.submission import SubmissionCreate, SubmissionUpdate


class SubmissionService:
    @staticmethod
    async def create(db: AsyncSession, data: SubmissionCreate) -> Submission:
        submission = Submission(**data.model_dump())
        db.add(submission)
        await db.commit()
        await db.refresh(submission)
        return submission

    @staticmethod
    async def list_by_status(
        db: AsyncSession,
        status: SubmissionStatus | None = None,
    ) -> list[Submission]:
        query = select(Submission).order_by(Submission.created_at.desc())
        if status is not None:
            query = query.where(Submission.status == status)
        result = await db.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def update_status(
        db: AsyncSession,
        submission_id: UUID,
        data: SubmissionUpdate,
    ) -> Submission | None:
        result = await db.execute(
            select(Submission).where(Submission.id == submission_id)
        )
        submission = result.scalar_one_or_none()
        if not submission:
            return None
        submission.status = data.status
        if data.reviewer_notes is not None:
            submission.reviewer_notes = data.reviewer_notes
        await db.commit()
        await db.refresh(submission)
        return submission
```

## 4. Public endpoint

`backend/app/api/submissions_public.py`:

```python
from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.rate_limit import limiter
from app.schemas.submission import SubmissionCreate, SubmissionResponse
from app.services.submissions import SubmissionService

router = APIRouter(prefix="/api/submissions", tags=["submissions-public"])


@router.post("", response_model=SubmissionResponse, status_code=201)
# Tight per-IP rate limit — public endpoints attract spam and probes.
@limiter.limit("3/minute")
async def create_submission(
    data: SubmissionCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    return await SubmissionService.create(db, data)
```

Register in `main.py`.

## 5. CSRF exemption

The CSRF middleware protects every write that isn't on an exempt path.
For **unauthenticated** public endpoints, CSRF doesn't add protection:
there's no logged-in user identity for a malicious cross-origin site to
abuse. The right pattern is to exempt the path and rely on rate
limiting (above) plus input validation for abuse defence.

In `backend/app/middleware/csrf.py`, extend `EXEMPT_PATHS`:

```python
EXEMPT_PATHS = frozenset({
    "/api/auth/login",
    "/api/auth/csrf",
    "/api/submissions",  # public, unauthenticated; rate-limited instead
})
```

**Important**: only exempt unauthenticated endpoints. Any endpoint that
*reads or writes the cookie session* must stay CSRF-protected.

## 6. Admin endpoints

`backend/app/api/submissions_admin.py`:

```python
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_admin
from app.models.submission import SubmissionStatus
from app.schemas.submission import SubmissionResponse, SubmissionUpdate
from app.services.submissions import SubmissionService

router = APIRouter(
    prefix="/api/admin/submissions",
    tags=["submissions-admin"],
    dependencies=[Depends(get_current_admin)],
)


@router.get("", response_model=list[SubmissionResponse])
async def list_submissions(
    status: SubmissionStatus | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    return await SubmissionService.list_by_status(db, status)


@router.patch("/{submission_id}", response_model=SubmissionResponse)
async def review_submission(
    submission_id: UUID,
    data: SubmissionUpdate,
    db: AsyncSession = Depends(get_db),
):
    submission = await SubmissionService.update_status(db, submission_id, data)
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")
    return submission
```

Register in `main.py`. Run `make generate-client`.

## 7. Frontend: public form

`frontend/src/app/submit/page.tsx` (new public route — adjust the
`(public)` layout group if you want header/footer chrome around it):

```tsx
"use client";

import { useState } from "react";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { errorMessage } from "@/lib/errors";
import type { components } from "@/lib/api-types";

type SubmissionCreate = components["schemas"]["SubmissionCreate"];

export default function SubmitPage() {
  const [form, setForm] = useState<SubmissionCreate>({
    name: "", email: "", message: "",
  });
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sent, setSent] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const res = await fetch("/api/submissions", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(form),
      });
      if (!res.ok) throw new Error((await res.json()).detail ?? "Failed");
      setSent(true);
    } catch (err) {
      setError(errorMessage(err, "Submission failed"));
    } finally {
      setSubmitting(false);
    }
  }

  if (sent) return <p>Thanks — we'll review your submission shortly.</p>;

  return (
    <form onSubmit={handleSubmit} className="space-y-4 max-w-md mx-auto p-6">
      <ErrorBanner error={error} onDismiss={() => setError(null)} />
      <Input id="name" label="Name" required
        value={form.name}
        onChange={(e) => setForm({ ...form, name: e.target.value })}/>
      <Input id="email" type="email" label="Email" required
        value={form.email}
        onChange={(e) => setForm({ ...form, email: e.target.value })}/>
      <textarea required maxLength={10000}
        className="w-full rounded-lg border border-border bg-surface px-3 py-2"
        rows={6}
        value={form.message}
        onChange={(e) => setForm({ ...form, message: e.target.value })}/>
      <Button type="submit" disabled={submitting}>
        {submitting ? "Sending..." : "Submit"}
      </Button>
    </form>
  );
}
```

Note: this bypasses the typed `lib/api.ts` wrapper because the wrapper
auto-attaches the CSRF header, which the exempt public endpoint
doesn't need (and which the unauthenticated user doesn't have anyway).

## 8. Frontend: admin queue

Follow the `admin/items/page.tsx` pattern. Add API client functions for
`getSubmissions(status?)` and `reviewSubmission(id, update)`, then a
page that lists pending submissions and lets the admin approve/reject
with optional reviewer notes.

Nav link in `frontend/src/app/admin/layout.tsx`:

```tsx
{ href: "/admin/submissions", label: "Submissions" },
```

## 9. Tests

`backend/tests/test_submissions.py`:

```python
import pytest

from tests.conftest import TEST_ADMIN_EMAIL


@pytest.mark.asyncio
async def test_public_can_submit_without_auth_or_csrf(client):
    """Unauthenticated POST to /api/submissions should succeed —
    exempt from CSRF, no login required."""
    response = await client.post(
        "/api/submissions",
        json={
            "name": "Alice",
            "email": "alice@example.com",
            "message": "Hello",
        },
    )
    assert response.status_code == 201
    assert response.json()["status"] == "pending"


@pytest.mark.asyncio
async def test_public_submit_is_rate_limited(client):
    """Public endpoint is 3/minute; 4th attempt 429s."""
    payload = {"name": "x", "email": "x@example.com", "message": "x"}
    for _ in range(3):
        await client.post("/api/submissions", json=payload)
    response = await client.post("/api/submissions", json=payload)
    assert response.status_code == 429


@pytest.mark.asyncio
async def test_admin_can_review_submission(client):
    # Create a submission first
    create = await client.post("/api/submissions", json={
        "name": "Bob", "email": "b@example.com", "message": "Help",
    })
    sub_id = create.json()["id"]

    # Login as admin
    login = await client.post("/api/auth/login", json={
        "email": TEST_ADMIN_EMAIL, "password": "testpass",
    })
    csrf = login.cookies["csrf_token"]

    # Review
    response = await client.patch(
        f"/api/admin/submissions/{sub_id}",
        json={"status": "approved", "reviewer_notes": "Looks good"},
        headers={"X-CSRF-Token": csrf},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "approved"
    assert response.json()["reviewer_notes"] == "Looks good"


@pytest.mark.asyncio
async def test_admin_list_requires_auth(client):
    response = await client.get("/api/admin/submissions")
    assert response.status_code == 401
```

## What to skip until you need it

- **Email notifications** on submit and status change. Needs email infra
  (SES, Postmark, etc.) — significant scope. Add when you actually have
  someone to notify.
- **CAPTCHA / hCaptcha on the public form.** Rate limiting buys you a
  lot. Add CAPTCHA when you see real spam pressure, not preemptively.
- **Admin reply via the admin UI.** If you want to message the
  submitter back, that's an outbound-email feature — see above.
- **Status workflow with allowed-transitions enforcement.** The current
  PATCH lets any status go to any other status. If you need
  "approved" → "rejected" to be illegal, add a check in the service:
  ```python
  ALLOWED_TRANSITIONS = {
      SubmissionStatus.pending: {SubmissionStatus.approved, SubmissionStatus.rejected},
      SubmissionStatus.approved: set(),  # terminal
      SubmissionStatus.rejected: {SubmissionStatus.pending},  # allow re-review
  }
  ```
- **Audit log entries on every status change.** Combine this recipe
  with [`audit-log.md`](audit-log.md): call `AuditLogService.record`
  from the `review_submission` route with `action="submission_review"`,
  `extra={"old": ..., "new": data.status.value}`.
