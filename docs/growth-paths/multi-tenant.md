# Growing into multi-tenancy

Baseplate ships single-tenant by design. This document is what you do when
that's no longer enough — when one customer becomes many, and they each
need their own data, their own users, and their own access.

This is **not** a feature of Baseplate. It's a migration guide. The starter
deliberately doesn't ship `organization_id` columns, membership tables, or
tenant-scoped middleware because **unused multi-tenancy is worse than no
multi-tenancy**. Add this machinery when you actually need it.

## The stages

Most apps don't go straight from single-tenant to SaaS. There's an
intermediate stage worth being honest about.

### Stage 1 — single admin (Baseplate default)

One person logs in. They manage data. The public reads pages. This is
where Baseplate starts. Don't add anything in this guide until you've
outgrown this.

### Stage 2 — multiple admins, same organisation

You need a colleague to log in. The data is still shared (your one
organisation owns all of it), but more than one person needs access.

This **doesn't require multi-tenancy**. The `users` table already
supports it (`is_admin: bool` on each user, JWT carries `sub = user.id`).
What's missing is a UI for creating other users and optionally a
role beyond binary admin/not-admin.

**What to add:**
- `/admin/users` page: list, create, deactivate users.
- Optional: a `role` column (e.g. `admin`, `editor`, `viewer`) and
  per-route checks on the role.
- Optional: password reset flow if you don't want to keep
  hashing-and-pasting via `make hash-password`.

**What NOT to add yet:** organisations, memberships, tenant IDs. Resist.

### Stage 3 — customer-specific workspaces (the real inflection)

Now you have more than one customer/client/company using the app. Each
has their own data; users from customer A must never see customer B's
records. **This is where the architectural changes start.**

The rest of this guide is about Stage 3.

### Stage 4 — full SaaS

Stage 3 plus: public signup, invitations, email flows, billing,
subscription plans, plan limits, customer-support admin console, audit
logs, per-tenant settings, data export/delete. Each is its own decision
and its own complexity budget. Baseplate doesn't help with these; at
this point you're building a SaaS product, not extending the starter.

## The Stage 3 migration

Concrete steps to add multi-tenancy without breaking existing data.

### 1. Add the `Organization` model

New file: `backend/app/models/organization.py`

```python
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, uuid_pk


class Organization(Base, TimestampMixin):
    __tablename__ = "organizations"

    id = uuid_pk()
    name: Mapped[str] = mapped_column(String(255))
    slug: Mapped[str] = mapped_column(String(64), unique=True, index=True)
```

Register in `app/models/__init__.py`.

### 2. Add `OrganizationMember` (the join table)

A user can belong to multiple organisations; each membership has its
own role.

```python
class OrganizationMember(Base, TimestampMixin):
    __tablename__ = "organization_members"

    id = uuid_pk()
    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[str] = mapped_column(String(32))  # admin | editor | viewer
```

Add a composite unique constraint on `(organization_id, user_id)`.

### 3. Add `organization_id` to tenant-owned tables

For Baseplate's example, that's `items`:

```python
class Item(Base, TimestampMixin):
    __tablename__ = "items"
    id = uuid_pk()
    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(255))
    # ...
```

Migration: when adding the column, you'll need to backfill existing
rows. The cleanest path: create a "default" organisation in a data
migration, assign all existing items to it, then add the `NOT NULL`
constraint.

```python
def upgrade():
    op.add_column("items", sa.Column("organization_id", UUID, nullable=True))
    # data migration: create default org, assign existing items
    conn = op.get_bind()
    conn.execute(sa.text(
        "INSERT INTO organizations (id, name, slug) "
        "VALUES (gen_random_uuid(), 'Default', 'default')"
    ))
    conn.execute(sa.text(
        "UPDATE items SET organization_id = "
        "(SELECT id FROM organizations WHERE slug = 'default')"
    ))
    op.alter_column("items", "organization_id", nullable=False)
    op.create_foreign_key(
        "items_org_fk", "items", "organizations",
        ["organization_id"], ["id"], ondelete="CASCADE",
    )
```

Don't skip the data migration. Adding `NOT NULL` on a populated table
without a backfill will fail.

### 4. Thread organisation context through auth

`app/deps.py` currently returns a `User`. Add a parallel dep that returns
both user **and** their currently-selected organisation:

```python
async def get_current_membership(
    user: User = Depends(get_current_admin),
    org_slug: str = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
) -> tuple[User, OrganizationMember]:
    if not org_slug:
        raise HTTPException(401, "No organisation selected")
    membership = await OrganizationMemberService.get_for_user_and_slug(
        db, user.id, org_slug
    )
    if not membership:
        raise HTTPException(403, "Not a member of that organisation")
    return user, membership
```

How the user "selects" an organisation (subdomain, cookie, path param) is
a product decision. A cookie is the lowest-friction starting point.

### 5. Update service signatures

Every query that returns tenant-owned data must now filter by
`organization_id`. The service layer is where this happens.

Before:
```python
async def list_items(db: AsyncSession) -> list[Item]:
    result = await db.execute(select(Item).order_by(Item.created_at.desc()))
    return list(result.scalars().all())
```

After:
```python
async def list_items(db: AsyncSession, organization_id: UUID) -> list[Item]:
    result = await db.execute(
        select(Item)
        .where(Item.organization_id == organization_id)
        .order_by(Item.created_at.desc())
    )
    return list(result.scalars().all())
```

Routes pass the membership's organisation through:

```python
@router.get("", response_model=list[ItemResponse])
async def list_items(
    ctx: tuple[User, OrganizationMember] = Depends(get_current_membership),
    db: AsyncSession = Depends(get_db),
):
    _, membership = ctx
    return await ItemService.list_items(db, membership.organization_id)
```

**The service layer is the reason this migration is feasible.** If
queries were sprayed across route handlers, you'd be touching every
endpoint individually. Because they go through `ItemService.list_items`,
you add the parameter once and update each call site.

### 6. Add tenant-isolation tests

This is the most important step in the whole migration. Tests that prove
a user in organisation A cannot read, write, update, or delete a record
owned by organisation B.

Pattern: create two organisations in the fixture, add a user to each,
then assert cross-tenant access fails:

```python
async def test_user_cannot_read_other_orgs_items(
    client, org_a, org_b, item_in_org_b
):
    await _login_as(client, org_a.admin)
    response = await client.get(f"/api/admin/items/{item_in_org_b.id}")
    assert response.status_code in (403, 404)
```

Test the same for POST/PATCH/DELETE. Test list endpoints — the response
must only contain org A's records.

Without these tests, your multi-tenancy is theatre. Most "multi-tenant
bugs" are missing `where(organization_id == current_org)` clauses
discovered after a customer sees another customer's data.

### 7. Update the frontend

The admin UI needs an organisation switcher (dropdown or subdomain).
The CSRF + auth cookies you already have don't change; add an
`org_slug` cookie that the user can switch between organisations they
belong to.

Server components rendering public pages stay org-aware via URL
(`/{org_slug}/items` etc.) or via subdomain routing — pick one and
commit.

## What to skip until you're sure

Adding any of these prematurely will make the codebase harder for
humans and agents to navigate:

- **Public self-signup** — Stage 3 doesn't need it. Admins add users
  via invitation. Self-signup is Stage 4.
- **Billing / subscriptions** — premature optimisation until you've
  proven the multi-tenant model works.
- **Per-org feature flags** — wait until you actually need to
  differentiate.
- **Audit logging** — add when a customer asks for it, not before.
- **Tenant-aware analytics** — `organization_id` joins are fine
  initially.

## Migration anti-patterns

A few specific things that look reasonable but cause trouble:

**Adding `organization_id` to *every* table.** Some tables genuinely
shouldn't be tenant-scoped (e.g. global feature flags, audit logs
that span tenants). Audit each table; don't blanket-apply.

**Row-level security in Postgres without an escape hatch.** RLS is
appealing for "defence in depth," but it complicates migrations, makes
admin tools harder to write, and obscures the source-level
intent. Application-level filtering is more legible. Add RLS later if
the threat model demands it.

**A single `tenant_id` JWT claim with no membership lookup.** Caching
the user's "current org" in the JWT seems efficient but means demoting
or removing a user from an org doesn't take effect until their token
expires. Look up membership per request.

**One database per tenant.** This solves real isolation problems but
trades them for migration coordination problems, backup complexity,
and per-tenant infrastructure costs. Use a single database with
`organization_id` columns until you have a concrete reason not to.

## When *not* to use this guide

If your app stays at Stage 1 or Stage 2 forever — most internal tools,
most directory products, most narrow operational apps — you never need
any of this. Adding tenancy "just in case" is the failure mode this
guide is designed to prevent.

The goal of Baseplate's design is that the small app stays small and
the migration path stays available. Both are true; pick the one that
matches your situation.
