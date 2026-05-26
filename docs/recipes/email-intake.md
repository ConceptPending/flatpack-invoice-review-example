# Recipe: Email intake → admin review queue

Turns an inbox into a Baseplate admin review queue. A scheduled job
polls an IMAP mailbox (e.g. `support@yourcompany.com`), creates a
`Submission` for each new message, and marks the email as read so it
isn't picked up twice. Admins triage the resulting queue the same way
they'd review a web-form submission.

This is the "your team already lives in email; let's structure that
without making them change tools" pattern. Common shapes:

- **Support inbox** → triage queue
- **Tip line / report inbox** → review queue
- **Application inbox** → candidate queue
- **Document submission inbox** → processing queue (combine with the
  document-upload recipe when that lands)

## Composes with

This recipe **builds on** [`public-submission-and-admin-queue.md`](public-submission-and-admin-queue.md).
Apply that one first (or to your existing app). The intake mechanism
changes here — IMAP poll instead of HTTP POST — but the `Submission`
model, admin queue UI, and status workflow are reused unchanged.

## What you'll add

- `imapclient` to backend deps (cleaner API than stdlib `imaplib`)
- New env vars: `IMAP_HOST`, `IMAP_USERNAME`, `IMAP_PASSWORD`,
  `IMAP_MAILBOX`, `IMAP_POLL_MINUTES`
- `backend/app/services/email_intake.py` — `poll_inbox()` runs one
  fetch cycle, idempotent via `Message-ID` header
- A new column on `Submission` (or a separate `email_metadata` if you
  want to keep the public-form variant clean) — see "Schema choice"
  below
- Update to `backend/app/tasks/scheduler.py` to register the job
- One backend test using a mocked IMAP client

## Schema choice

You have two reasonable options for storing email-derived submissions:

**Option A — extend `Submission` with an optional `source` column.**
Single table, mixed origins (web form + email). Cleaner UI: admins
see one queue. Trade-off: schema gets union-shaped (`source = "web"
| "email"` with `email_message_id`, `email_received_at` nullable).

**Option B — separate `EmailSubmission` table** with its own admin
queue. Cleaner schema, separate review UI. Trade-off: two queues to
build and maintain.

This recipe goes with **Option A** — the admin's mental model is
usually "stuff to triage," and the source is metadata. If your case
needs different workflow per source (e.g., email needs auto-acknowledge,
form doesn't), Option B is better.

## 1. Install IMAP client

In `backend/pyproject.toml` dependencies:

```toml
"imapclient>=3.0.0",
```

Then `make install`.

## 2. Env vars

`backend/.env`:

```env
IMAP_HOST=imap.gmail.com
IMAP_USERNAME=support@yourcompany.com
IMAP_PASSWORD=...                     # use an app password for Gmail/Workspace
IMAP_MAILBOX=INBOX
IMAP_POLL_MINUTES=5
```

Add to `app/config.py`:

```python
imap_host: str = ""
imap_username: str = ""
imap_password: str = ""
imap_mailbox: str = "INBOX"
imap_poll_minutes: int = 5
```

Empty `imap_host` means the job is disabled — useful for tests and
local dev where you don't want to poll a real inbox.

## 3. Migration: add source columns to Submission

```bash
make migrate-new msg="submission email source"
```

```python
def upgrade() -> None:
    op.add_column(
        "submissions",
        sa.Column(
            "source",
            sa.String(16),
            nullable=False,
            server_default="web",
        ),
    )
    op.add_column(
        "submissions",
        sa.Column("email_message_id", sa.String(255), nullable=True),
    )
    # Unique only when present: dedupe inbound emails by Message-ID.
    op.create_index(
        "ix_submissions_email_message_id",
        "submissions",
        ["email_message_id"],
        unique=True,
        postgresql_where=sa.text("email_message_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_submissions_email_message_id", table_name="submissions")
    op.drop_column("submissions", "email_message_id")
    op.drop_column("submissions", "source")
```

The partial unique index is Postgres-specific. For SQLite (test env),
the unique constraint applies to all rows including NULLs in some
versions; if your tests trip over it, use a non-unique index instead
and rely on the service-layer idempotency check.

Update `backend/app/models/submission.py`:

```python
source: Mapped[str] = mapped_column(String(16), default="web", server_default="web")
email_message_id: Mapped[str | None] = mapped_column(
    String(255), nullable=True, unique=True
)
```

## 4. Service

`backend/app/services/email_intake.py`:

```python
import email
from datetime import datetime, timezone
from email.utils import parseaddr

import structlog
from imapclient import IMAPClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.submission import Submission, SubmissionStatus

logger = structlog.get_logger()


def _extract_plain_text(msg: email.message.Message) -> str:
    """Best-effort body extraction. HTML-only emails get a placeholder."""
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or "utf-8"
                    return payload.decode(charset, errors="replace")
        return "[no text/plain part]"
    payload = msg.get_payload(decode=True)
    if payload:
        charset = msg.get_content_charset() or "utf-8"
        return payload.decode(charset, errors="replace")
    return ""


async def poll_inbox(db: AsyncSession) -> int:
    """Fetch unseen messages, create Submissions, mark as seen. Returns
    the number of submissions created."""
    if not settings.imap_host:
        return 0

    created = 0
    with IMAPClient(settings.imap_host, ssl=True) as client:
        client.login(settings.imap_username, settings.imap_password)
        client.select_folder(settings.imap_mailbox)
        # IMAP "UNSEEN" = not yet marked \Seen.
        message_ids = client.search(["UNSEEN"])
        if not message_ids:
            return 0

        fetched = client.fetch(message_ids, ["RFC822"])
        for imap_uid, data in fetched.items():
            raw = data[b"RFC822"]
            msg = email.message_from_bytes(raw)

            msg_id = (msg.get("Message-ID") or "").strip()
            if not msg_id:
                logger.warning("email_intake_skipped", reason="no Message-ID")
                continue

            # Idempotency check at the application layer (plus the DB unique
            # index as a backstop).
            existing = await db.execute(
                select(Submission).where(Submission.email_message_id == msg_id)
            )
            if existing.scalar_one_or_none():
                logger.info("email_intake_duplicate", message_id=msg_id)
                client.add_flags(imap_uid, [b"\\Seen"])
                continue

            sender_name, sender_email = parseaddr(msg.get("From", ""))
            subject = (msg.get("Subject") or "").strip()
            body = _extract_plain_text(msg)
            # Treat subject + body as the message; admins can scan both.
            combined = f"Subject: {subject}\n\n{body}".strip()[:10_000]

            submission = Submission(
                name=sender_name or sender_email or "unknown",
                email=sender_email or "noreply@invalid",
                message=combined,
                status=SubmissionStatus.pending,
                source="email",
                email_message_id=msg_id,
            )
            db.add(submission)
            await db.commit()
            client.add_flags(imap_uid, [b"\\Seen"])
            created += 1
            logger.info(
                "email_intake_created",
                submission_id=str(submission.id),
                from_addr=sender_email,
                subject=subject[:100],
            )

    return created
```

A few notes:

- **`\Seen` is set after the Submission is committed.** If the script
  crashes mid-loop, the next poll re-fetches the same messages and the
  idempotency check (DB unique constraint on `email_message_id`)
  prevents duplicates.
- **`IMAPClient` opens a connection per poll.** For higher-volume
  inboxes (1 message/sec+), keep a long-lived connection in IDLE mode;
  for the cron-style polling target this recipe is shaped for, per-poll
  connections are simpler and fine.
- **Body extraction is intentionally simple.** Production-grade
  email parsing handles inline images, attachments, quoted-printable,
  base64, HTML-to-text conversion, signatures, and threading. The
  recipe extracts the first `text/plain` part and stops. Add parsing
  sophistication when an actual email surprises you.

## 5. Schedule the job

In `backend/app/tasks/scheduler.py`:

```python
from app.config import settings
from app.database import async_session
from app.services.email_intake import poll_inbox


async def email_intake_job():
    async with async_session() as db:
        try:
            count = await poll_inbox(db)
            if count:
                logger.info("email_intake_cycle", created=count)
        except Exception as exc:
            logger.exception("email_intake_failed", error=str(exc))


def start_scheduler():
    # ... existing jobs ...
    if settings.imap_host:
        scheduler.add_job(
            email_intake_job,
            IntervalTrigger(minutes=settings.imap_poll_minutes),
            id="email_intake",
            replace_existing=True,
        )
    scheduler.start()
```

Wrapping the job body in a `try/except` matters — APScheduler will keep
the job in the queue if it raises, but it'll log noisily. Catch and log
explicitly so transient IMAP outages don't pollute the structlog stream.

## 6. Frontend (optional)

The existing `/admin/submissions` queue already displays the new entries
— no change required. If you want to filter or sort by source:

```tsx
{submission.source === "email" && (
  <span className="text-xs text-muted">via email</span>
)}
```

And maybe a "Source" filter button. Both are <5 line edits.

## 7. Test

`backend/tests/test_email_intake.py`:

```python
import email
from unittest.mock import MagicMock, patch

import pytest

from app.services.email_intake import poll_inbox


def _make_email_bytes(*, msg_id: str, from_addr: str, subject: str, body: str) -> bytes:
    msg = email.message.EmailMessage()
    msg["Message-ID"] = msg_id
    msg["From"] = from_addr
    msg["To"] = "support@example.com"
    msg["Subject"] = subject
    msg.set_content(body)
    return msg.as_bytes()


@pytest.mark.asyncio
async def test_poll_inbox_creates_submissions(db_session, monkeypatch):
    monkeypatch.setattr("app.config.settings.imap_host", "imap.example.com")

    fake_client = MagicMock()
    fake_client.__enter__.return_value = fake_client
    fake_client.search.return_value = [42]
    fake_client.fetch.return_value = {
        42: {
            b"RFC822": _make_email_bytes(
                msg_id="<unique-1@example.com>",
                from_addr="Alice <alice@example.com>",
                subject="Hello",
                body="This is the body.",
            )
        }
    }

    with patch("app.services.email_intake.IMAPClient", return_value=fake_client):
        created = await poll_inbox(db_session)

    assert created == 1
    fake_client.add_flags.assert_called_with(42, [b"\\Seen"])


@pytest.mark.asyncio
async def test_poll_inbox_is_idempotent(db_session, monkeypatch):
    """Two polls picking up the same Message-ID should only create one
    submission. (Simulates the crash-mid-loop recovery case.)"""
    monkeypatch.setattr("app.config.settings.imap_host", "imap.example.com")

    same_email = _make_email_bytes(
        msg_id="<duplicate@example.com>",
        from_addr="dup@example.com",
        subject="x",
        body="x",
    )

    def make_client():
        c = MagicMock()
        c.__enter__.return_value = c
        c.search.return_value = [99]
        c.fetch.return_value = {99: {b"RFC822": same_email}}
        return c

    with patch("app.services.email_intake.IMAPClient", side_effect=make_client):
        first = await poll_inbox(db_session)
        second = await poll_inbox(db_session)

    assert first == 1
    assert second == 0  # idempotency caught it
```

## What to skip until you need it

- **Inbound SMTP server.** Heavier; needs an exposed port, TLS certs,
  bounces, queueing. IMAP polling against an existing inbox (Gmail,
  Workspace, Outlook 365) is dramatically cheaper to set up and
  reaches the same outcome.
- **Postmark / SendGrid / Mailgun inbound webhooks.** Push-based, much
  lower latency, no polling cost. If you're already using one of these
  for outbound email and have <1-minute latency requirements, switch
  this recipe to a webhook endpoint. Otherwise the 5-minute poll is
  fine.
- **Attachment storage.** Skip in v1. When you need it, add a recipe
  that combines this with file-upload — store attachments in object
  storage, link them to the `Submission`.
- **HTML body parsing / sanitisation.** First `text/plain` part is
  enough for triage. Add real HTML extraction (e.g., via `mailparser`
  or `beautifulsoup4`) when the inbound senders are mostly HTML-only.
- **Threading** (group reply-emails under the original submission).
  Worth doing when your queue gets noisy; group by `In-Reply-To` and
  `References` headers. Until then, each reply is a fresh entry.
- **Auto-acknowledge replies** ("we got your email; we'll respond by
  Friday"). Outbound email is its own recipe — defer to
  `docs/recipes/email-notifications.md` when that lands.
- **Multiple inboxes** (e.g., support@ + tips@ on the same Baseplate
  instance). Generalise `IMAP_*` env vars to `IMAP_INBOXES` as a
  JSON list when you need it; not before.
- **OAuth-authenticated IMAP** (e.g., Gmail XOAUTH2). The recipe uses
  app passwords for simplicity. If your IDP forbids app passwords,
  swap to `imapclient.IMAPClient(...).oauth2_login(...)` with a refresh
  token flow. That's an Internal-Tools-track upgrade worth its own
  recipe.
