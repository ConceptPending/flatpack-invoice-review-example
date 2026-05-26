# Baseplate

[![CI](https://github.com/ConceptPending/baseplate/actions/workflows/ci.yml/badge.svg)](https://github.com/ConceptPending/baseplate/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![Node 20+](https://img.shields.io/badge/node-20+-green.svg)](https://nodejs.org/)

> **Too important for spreadsheets. Too specific for SaaS.**

A small, production-shaped full-stack foundation **designed to be safely extended by AI coding agents**.

Most starter templates are designed for humans to read once and forget. This one is designed to be re-read by an LLM every session. The codebase is deliberately small enough to fit in a coding agent's context window, with conventions, gotchas, and extension recipes documented in [CLAUDE.md](CLAUDE.md) so the next change lands correctly the first time.

**Live demo**: https://frontend-production-7642.up.railway.app — public homepage + items list. Admin login behind a credential gate. See [DEPLOYMENT.md](DEPLOYMENT.md) for what it took to deploy it.

## The core idea

Coding agents are very good at extending clear patterns and very bad at inventing safe foundations. Baseplate gives the agent the boring decisions already made — cookie auth + CSRF, service-layer data access, migrations, typed API boundaries, tests, Docker, documented extension recipes — so the next change is "extend this," not "invent this."

The goal isn't to include every feature. It's to keep the base small enough that both humans and agents can hold it in their heads.

## Why one-off apps matter now

AI coding agents have made a category of software economically viable that wasn't before: small, specific apps that solve one workflow for one team, client, or community. Not SaaS. Not enterprise platforms. Just **situated software** — useful for a particular context, not a generic market. The line at the top of this README is the lane: things too important to leave in a spreadsheet, too specific to justify a SaaS subscription, too narrow for off-the-shelf tools.

Vibe-coded apps work brilliantly until the foundation matters: when something has to handle a password, persist a session, run a scheduled job, or survive a redeploy without losing data. That's where agents typically improvise badly. Baseplate is the foundation underneath, so the agent's free-form work happens on top of safe rails instead of on a blank canvas.

The [recipes](docs/recipes/) are where the growth happens — each one a documented transformation an agent can apply cleanly to extend the base for a specific use case.

## What you can build with this

Baseplate is shaped for **single-tenant, admin-driven apps**: a logged-in admin manages data; the public reads pages backed by that data; scheduled jobs do work in the background. Concrete app shapes that map cleanly onto what Baseplate ships:

- **Directory or data product** — public listings (venues, grants, tools, companies, charities, datasets), admin CRUD, scheduled freshness checks. The canonical use case.
- **Internal operations dashboard** — lightweight CRM, supplier tracker, lead review board, compliance task tracker, contractor pipeline. Single organisation, several internal users.
- **Intake + review queue** — public submits a form (case, application, complaint, candidate), admin reviews internally, status changes through a workflow.
- **AI workflow with human-in-the-loop** — upload documents, LLM extracts/summarises, admin reviews and approves. Scheduler triggers extraction batches; the review queue is the admin-side product.
- **Niche structured CMS** — content database with admin screens and a custom public frontend. Use when WordPress or Sanity is too generic and you want code ownership.
- **Scheduled monitor** — scrape sources daily, store results, surface a digest for admin review. APScheduler handles the cron side; the admin UI is the review layer.
- **Internal tool with company data** — admin app sitting near where work already happens: SSO login via Google Workspace or Microsoft Entra, inbox-as-queue via IMAP, optional read-only links to existing operational data. The base ships with simple local auth; the [SSO](docs/recipes/sso-oidc.md), [user-management](docs/recipes/admin-users.md), and [email-intake](docs/recipes/email-intake.md) recipes layer on when you're ready.

If your app looks like one of these shapes, Baseplate gets you to "production-shaped foundation" in under an hour.

## Coming from Flatpack?

Baseplate is the production-shaped foundation that a [Flatpack](https://github.com/ConceptPending/flatpack) graduates into when "my tool" becomes "our tool" — when a personal single-file utility crosses a real promotion trigger (a second user, shared state, audit history, server-side secrets).

You don't *convert* a Flatpack into a Baseplate project — a Flatpack is one HTML file, this is a full stack. What promotes is the understanding embedded in the Flatpack's inline manifest: entities, validations, exports, sample data, edge cases, test cases. The Flatpack stays alongside the Baseplate version as a reference artifact for parity checks.

If you have a promotion plan in hand:

1. Read [`docs/promoting-a-flatpack.md`](docs/promoting-a-flatpack.md) — the receiving flow.
2. Map the archetype to a recipe set via [`docs/flatpack-archetype-to-recipe-map.md`](docs/flatpack-archetype-to-recipe-map.md).
3. Drop the Flatpack artifacts into `reference/`.
4. Apply the recipes, walk the confidence tiers in the plan.
5. Verify with `make verify-promotion`.

If you don't have a Flatpack yet but your idea is small enough that you're not sure Baseplate is the right starting point, try [Flatpack](https://github.com/ConceptPending/flatpack) first. That repo's [`prompts/generate-flatpack.md`](https://github.com/ConceptPending/flatpack/blob/main/prompts/generate-flatpack.md) is ~100 lines, fits in any agent's context, and produces a working single-file tool you can use locally. Promote later if and when it stops being personal.

## Who this is for

- **Solo founders** prototyping a real product with LLM assistance — who don't want to trust the agent to invent auth, CSRF, and deployment from scratch.
- **Consultants building bespoke internal tools** — start every client engagement from the same production-shaped foundation. Faster delivery, fewer auth/deploy mistakes, easier handover, and the client owns the code outright.
- **Domain experts with technical help** — a lawyer, researcher, or operator working with a technical collaborator (human or LLM) on a custom workflow tool.
- **Internal tools engineers at small companies** — enough structure to be maintainable without becoming enterprise architecture.
- **Founders validating non-SaaS products** — data products, directories, review workflows, AI-assisted services that aren't billable SaaS yet.

## Who this is *not* for

- People building **consumer social apps** or anything needing public user accounts on day one.
- **Multi-tenant B2B SaaS** with organisations, billing, plan limits, invitations (see [What if my app grows into a SaaS?](#what-if-my-app-grows-into-a-saas) below — it's possible, just not the default).
- People who want **Stripe + RBAC + team onboarding on day one** — that's a SaaS boilerplate, this is its smaller cousin.
- **Enterprise teams** needing Terraform, IAM, K8S manifests, observability stacks, policy-as-code.
- **Beginners** who don't know what an HTTP cookie is — Baseplate assumes some web-app fluency.

## How it works in practice

1. Clone the repo. The example `Item` model is a full vertical slice (model → migration → service → routes → frontend page).
2. Point your coding agent at [`CLAUDE.md`](CLAUDE.md). It reads conventions, dev commands, gotchas, and anti-patterns up front.
3. Follow the [10-step recipe](#adding-a-new-domain-model) for adding your own domain models. The agent has every pattern it needs without inventing one from scratch.
4. Tests + lint + CI catch the mistakes coding agents typically make.

## Stack

| Layer      | Technology                                                        |
|------------|-------------------------------------------------------------------|
| Backend    | FastAPI, SQLAlchemy 2 (async), Pydantic v2, Alembic, APScheduler |
| Frontend   | Next.js 16, React 19, Tailwind CSS 4, TypeScript                 |
| Database   | PostgreSQL 16 (asyncpg driver)                                   |
| Auth       | JWT in httpOnly cookies, bcrypt password hashing                 |
| Testing    | pytest + pytest-asyncio (backend), Vitest + Testing Library (frontend) |
| Deploy     | Docker multi-stage builds, Railway via GitHub Actions            |
| Logging    | structlog (structured JSON in prod, colored console in dev)      |

## Scope and limitations

This is a starter, not a finished product. Be aware of these intentional limits before building on top:

- **No user-management UI yet** — the `users` table exists and supports multiple admins, but there's no admin page to create/list/delete them. The bootstrap admin is created from `ADMIN_EMAIL` + `ADMIN_PASSWORD_HASH` on first startup. Add a `/admin/users` page when you need more.
- **No password reset / email verification** — no email infra is wired up. Passwords are managed by re-running `make hash-password` and updating the DB by hand, or via a future user-management UI.
- **No background queue** — `APScheduler` runs in-process for periodic jobs. Fine for cron-style work; not a substitute for Celery/Redis if you need durable retries or a separate worker pool.

## What if my app grows into a SaaS?

Baseplate starts single-tenant on purpose. Most small apps don't need organisations, billing, invitations, or tenant-scoped roles on day one — and adding those abstractions too early makes the code harder for humans and coding agents to understand.

But Baseplate isn't a dead end. The architectural seams that make multi-tenancy feasible later are already in place:

- **All data access goes through a service layer** — adding `organization_id` later means changing service method signatures, not spraying queries across routes.
- **Auth context is centralised** — `deps.get_current_admin` returns a `User`; threading `current_org` through it is mechanical.
- **The users table already supports multiple admins** — adding a `/admin/users` page is the next obvious step *before* introducing tenancy at all.
- **Alembic-managed migrations** — adding tenancy columns and backfilling existing rows is a normal alembic flow.

When (if) you need it, see [docs/growth-paths/multi-tenant.md](docs/growth-paths/multi-tenant.md) for the step-by-step migration guide. Baseplate deliberately does *not* ship unused `organization_id` columns or tenancy machinery you're not using yet — **unsafe or unused multi-tenancy is worse than no multi-tenancy**.

## Quick start

```bash
cp .env.example backend/.env
cp .env.example frontend/.env.local  # only the API_URL line

make install         # pip install backend deps + npm install frontend deps
make db              # start Postgres 16 via Docker on port 5433
make migrate         # run Alembic migrations
make hash-password   # generate a bcrypt hash, paste into backend/.env as ADMIN_PASSWORD_HASH
make dev             # backend on :8001, frontend on :3001
```

Open `http://localhost:3001/admin/login` and log in with the username/password you configured.

## Project structure

```
├── backend/
│   ├── app/
│   │   ├── config.py           # Pydantic Settings (env vars)
│   │   ├── database.py         # async engine + session factory
│   │   ├── deps.py             # FastAPI dependencies (auth)
│   │   ├── bootstrap.py        # Idempotent admin-user seed on startup
│   │   ├── rate_limit.py       # SlowAPI Limiter instance
│   │   ├── main.py             # App factory, middleware, routers
│   │   ├── models/
│   │   │   ├── base.py         # DeclarativeBase, TimestampMixin, uuid_pk()
│   │   │   ├── item.py         # Example model
│   │   │   └── user.py         # Users (email, password_hash, is_admin)
│   │   ├── schemas/
│   │   │   ├── auth.py         # LoginRequest / LoginResponse
│   │   │   ├── item.py         # ItemCreate / ItemUpdate / ItemResponse
│   │   │   └── user.py         # UserResponse (excludes password_hash)
│   │   ├── api/
│   │   │   ├── auth.py         # POST /login, /logout, GET /me
│   │   │   ├── items.py        # Admin CRUD (GET/POST/PATCH/DELETE)
│   │   │   └── public.py       # Public read endpoints
│   │   ├── services/
│   │   │   ├── items.py        # DB query logic, separate from routes
│   │   │   └── users.py        # get_by_email, create, authenticate
│   │   └── tasks/
│   │       └── scheduler.py    # APScheduler with placeholder job
│   ├── alembic/                # Migration config + versions
│   ├── tests/
│   └── pyproject.toml
├── frontend/
│   ├── src/
│   │   ├── app/                # Next.js App Router pages
│   │   │   ├── (public)/       # Public route group (Header + Footer)
│   │   │   └── admin/          # Admin route group (Sidebar)
│   │   ├── components/
│   │   │   ├── ui/             # Button, Card, Input, Modal, StatusPill
│   │   │   └── layout/         # Header, Footer
│   │   ├── lib/
│   │   │   ├── api.ts          # fetchAPI wrapper + typed endpoint functions
│   │   │   ├── auth.ts         # useRequireAuth() hook
│   │   │   ├── types.ts        # TypeScript interfaces
│   │   │   ├── constants.ts    # Site name, description
│   │   │   └── server-config.ts # Server-side API_BASE from env
│   │   └── middleware.ts       # Redirects unauthenticated /admin/* to /login
│   └── package.json
├── docker-compose.yml          # Local Postgres
├── Makefile                    # All dev/test/deploy commands
└── .github/workflows/
    ├── ci.yml                  # Tests + lint (always runs)
    └── deploy-railway.yml      # Railway deploy (opt-in, see Deployment)
```

## Environment variables

### Backend (`backend/.env`)

| Variable              | Required | Default                                              | Description                            |
|-----------------------|----------|------------------------------------------------------|----------------------------------------|
| `DATABASE_URL`        | Yes      | `postgresql+asyncpg://myapp:myapp@localhost:5433/myapp` | Async PostgreSQL connection string  |
| `ADMIN_EMAIL`         | Yes      | —                                                    | Bootstrap admin's email (creates the first user on startup if none exists) |
| `ADMIN_PASSWORD_HASH` | Yes      | —                                                    | bcrypt hash (generate with `make hash-password`) |
| `JWT_SECRET`          | Yes      | —                                                    | Random string for signing tokens       |
| `JWT_ALGORITHM`       | No       | `HS256`                                              | JWT signing algorithm                  |
| `JWT_EXPIRE_MINUTES`  | No       | `1440`                                               | Token lifetime (default 24h)           |
| `COOKIE_SECURE`       | No       | `true`                                               | Set `false` for local HTTP dev         |
| `CORS_ORIGINS`        | No       | `["http://localhost:3001"]`                          | Allowed CORS origins (JSON list)       |
| `DEBUG`               | No       | `false`                                              | Enables `/docs` and `/redoc`, disables startup validation |

### Frontend (`frontend/.env.local`)

| Variable   | Required | Default                  | Description                  |
|------------|----------|--------------------------|------------------------------|
| `API_URL`  | Yes      | `http://localhost:8001`  | Backend URL for API proxying |

### Startup validation

When `DEBUG=false` (the default), the backend will refuse to start if:
- `JWT_SECRET` is the default placeholder or empty
- `ADMIN_PASSWORD_HASH` is empty
- `DATABASE_URL` uses default local credentials

This prevents deploying with insecure defaults. Set `DEBUG=true` locally to skip these checks, or set real values.

## Architecture

### How requests flow

```
Browser → Next.js (:3001) → rewrites /api/* → FastAPI (:8001) → PostgreSQL
```

The Next.js `next.config.ts` proxies all `/api/*` requests to the backend. The browser only talks to the frontend server. In production on Railway, each service gets its own URL and the same rewrite proxy applies — the frontend's `API_URL` env var points to the backend's internal Railway URL.

### Authentication

1. **Bootstrap**: on first startup with no users in the DB, `app/bootstrap.py:ensure_admin_user` creates an admin from `ADMIN_EMAIL` + `ADMIN_PASSWORD_HASH`. Idempotent — subsequent starts skip if any admin exists.
2. **Login**: user submits `{ email, password }` to `POST /api/auth/login`. Backend looks up the user via `UserService.authenticate`, bcrypt-verifies the password, and issues a JWT with `sub = str(user.id)` set as an httpOnly cookie.
3. **Subsequent requests** include the cookie automatically.
4. `middleware.ts` on the frontend checks for the cookie and redirects to `/admin/login` if missing.
5. `useRequireAuth()` hook validates the token server-side via `GET /api/auth/me`.
6. Admin API routes either gate via `dependencies=[Depends(get_current_admin)]` on the router (cleanest when the route doesn't need the User) or accept `user: User = Depends(get_current_admin)` in the signature (when the route does).

### CSRF protection

Cookie auth with `SameSite=lax` blocks cross-origin `fetch()` calls but not top-level form-POST navigation. To close that gap, every write (POST/PUT/PATCH/DELETE) requires a CSRF token:

- **Backend** (`app/middleware/csrf.py`): a global middleware checks every non-safe, non-exempt request. The `X-CSRF-Token` header must equal the `csrf_token` cookie (constant-time comparison via `secrets.compare_digest`).
- **Token issuance**: login sets the `csrf_token` cookie alongside `access_token`. `GET /api/auth/csrf` refreshes it (sets the cookie and returns the token in the body for non-cookie consumers).
- **Cookie attributes**: `Secure=COOKIE_SECURE`, `SameSite=lax`, `HttpOnly=false` — JS must read it.
- **Frontend** (`lib/api.ts`): `fetchAPI` auto-attaches `X-CSRF-Token` on writes by reading the cookie via `lib/csrf.ts:getCSRFToken()`. **Don't call `fetch()` directly for writes** — you'll get 403'd.
- **Exempt paths**: `/api/auth/login` (no prior token possible) and `/api/auth/csrf` (issues the token). Safe methods (`GET`/`HEAD`/`OPTIONS`) bypass the check entirely.

### Backend patterns

**Models** inherit from `Base` and `TimestampMixin`. Use `uuid_pk()` for UUID primary keys with auto-generation:

```python
class Item(Base, TimestampMixin):
    __tablename__ = "items"
    id = uuid_pk()
    name: Mapped[str] = mapped_column(String(255))
```

**Services** contain all database query logic. Routes stay thin — they validate input, call a service method, and return the result:

```python
@router.post("", response_model=ItemResponse, status_code=201)
async def create_item(data: ItemCreate, admin=Depends(get_current_admin), db=Depends(get_db)):
    return await ItemService.create(db, data)
```

**Schemas** use Pydantic v2 with `model_config = {"from_attributes": True}` so SQLAlchemy models serialize directly.

### Frontend patterns

**API client** (`lib/api.ts`): A single `fetchAPI<T>()` wrapper handles JSON headers, error extraction, and 204 responses. All endpoint functions are typed and use `credentials: "include"` for cookie auth.

**Route groups**: `(public)/` has the Header + Footer layout. `admin/` has the sidebar layout. This separation means public pages and admin pages can have completely different chrome.

**Server components** fetch data at the edge. Client components (`"use client"`) handle interactivity. The admin pages are client components because they need auth state and user interaction.

## Make commands

| Command                      | What it does                                    |
|------------------------------|-------------------------------------------------|
| `make dev`                   | Starts Postgres + backend + frontend in parallel |
| `make dev-backend`           | Backend only on :8001                           |
| `make dev-frontend`          | Frontend only on :3001                          |
| `make db`                    | Start Postgres container on port 5433           |
| `make install`               | `pip install -e ".[dev]"` + `npm install`       |
| `make install-hooks`         | Register pre-commit hooks (ruff, tsc, eslint)   |
| `make generate-client`       | Regenerate `frontend/src/lib/api-types.ts` from backend OpenAPI |
| `make migrate`               | `alembic upgrade head`                          |
| `make migrate-new msg="..."` | Generate a new auto-detected migration          |
| `make test-backend`          | `pytest -v`                                     |
| `make test-frontend`         | `vitest run`                                    |
| `make lint`                  | ruff (backend) + tsc + ESLint (frontend)        |
| `make hash-password`         | Interactive bcrypt hash generator                |
| `make stop`                  | Kill dev servers + stop Docker                  |
| `make restart`               | Stop then start everything                      |

## Extending Baseplate

The basic transformation is "add a new domain model" — covered below.
For larger guided transformations, see [`docs/recipes/`](docs/recipes/):

- **[Audit log](docs/recipes/audit-log.md)** — record who did what when. For compliance, case management, internal review queues.
- **[Public submission + admin queue](docs/recipes/public-submission-and-admin-queue.md)** — the intake-and-review pattern: unauthenticated public form → admin review with status workflow.
- **[SSO via OpenID Connect](docs/recipes/sso-oidc.md)** — log in via Google Workspace (canonical) or Microsoft Entra / generic OIDC. Domain-allowlisted, additive to local password auth. The first Internal Tools recipe.
- **[User-management admin page](docs/recipes/admin-users.md)** — admin UI for inviting + deactivating other admins. Refuses to demote or deactivate the last active admin. Pairs with the SSO recipe.
- **[Email intake → admin review queue](docs/recipes/email-intake.md)** — scheduled IMAP poll turns an inbox into a submission queue. Composes with the public-submission recipe.

More recipes welcome — see [`docs/recipes/README.md`](docs/recipes/README.md) for the format and what's planned.

**See a recipe applied**: [`baseplate-example-feedback`](https://github.com/ConceptPending/baseplate-example-feedback) is a working app — public feedback form + admin review queue — built by taking Baseplate v0.1.0, removing the `Item` example, and applying the public-submission recipe. Roughly 12 file changes, the same kind of work an LLM following the recipe would produce.

### Adding a new domain model

This is the most common operation. Replace "Item" or add alongside it.

1. **Create the model** in `backend/app/models/`:
   ```python
   # backend/app/models/widget.py
   from sqlalchemy import String, Integer
   from sqlalchemy.orm import Mapped, mapped_column
   from app.models.base import Base, TimestampMixin, uuid_pk

   class Widget(Base, TimestampMixin):
       __tablename__ = "widgets"
       id = uuid_pk()
       title: Mapped[str] = mapped_column(String(255))
       count: Mapped[int] = mapped_column(Integer, default=0)
   ```

2. **Register the model** in `backend/app/models/__init__.py`:
   ```python
   from app.models.widget import Widget
   ```
   Alembic's `env.py` imports `Base` from here, so any model that inherits `Base` is auto-detected.

3. **Generate the migration**:
   ```bash
   make migrate-new msg="add widgets table"
   make migrate
   ```

4. **Add schemas** in `backend/app/schemas/widget.py`:
   ```python
   from pydantic import BaseModel
   from uuid import UUID
   from datetime import datetime

   class WidgetCreate(BaseModel):
       title: str
       count: int = 0

   class WidgetResponse(BaseModel):
       id: UUID
       title: str
       count: int
       created_at: datetime
       updated_at: datetime
       model_config = {"from_attributes": True}
   ```

5. **Add a service** in `backend/app/services/widget.py` — follow the `ItemService` pattern.

6. **Add routes** in `backend/app/api/widget.py` — follow the `items.py` pattern for admin routes, `public.py` for public routes.

7. **Register the router** in `backend/app/main.py`:
   ```python
   from app.api import widget
   app.include_router(widget.router)
   ```

8. **Add the TypeScript type** in `frontend/src/lib/types.ts`:
   ```typescript
   export interface Widget {
     id: string;
     title: string;
     count: number;
     created_at: string;
     updated_at: string;
   }
   ```

9. **Add API functions** in `frontend/src/lib/api.ts` — follow the Item functions pattern.

10. **Add pages** — copy `admin/items/page.tsx` as a starting point for the admin UI, and `(public)/items/page.tsx` for the public view.

### Adding a background job

Edit `backend/app/tasks/scheduler.py`:

```python
async def my_job():
    async with async_session() as db:
        # your logic here
        pass

def start_scheduler():
    scheduler.add_job(my_job, IntervalTrigger(minutes=15), id="my_job", replace_existing=True)
    scheduler.start()
```

Import `async_session` from `app.database` to get a database session inside jobs — don't use FastAPI's `Depends` outside of request handlers.

### Adding a new UI component

Components live in `frontend/src/components/ui/`. The design system uses CSS custom properties defined in `globals.css`:

- `bg-background` / `text-foreground` — page-level colors
- `bg-surface` / `bg-surface-elevated` — card and panel backgrounds
- `text-muted` — secondary text
- `border-border` — borders
- `bg-accent` / `bg-accent-bright` — primary action color (indigo by default)

Dark mode is available by adding the `dark` class to `<html>`. The CSS variables swap automatically.

### Adding a public-facing route

1. Create `frontend/src/app/(public)/your-page/page.tsx`
2. It automatically inherits the Header + Footer layout from `(public)/layout.tsx`
3. For server-rendered data, fetch from the backend using `API_BASE` from `lib/server-config.ts`:
   ```typescript
   const res = await fetch(`${API_BASE}/api/public/your-endpoint`, { next: { revalidate: 60 } });
   ```

### Adding an admin page

1. Create `frontend/src/app/admin/your-page/page.tsx`
2. It automatically gets the sidebar layout and is protected by `middleware.ts`
3. Add the nav link in `frontend/src/app/admin/layout.tsx`

## Deployment

CI (`.github/workflows/ci.yml`) runs tests + lint on every push and PR — no
platform secrets required. Deploy is a separate, opt-in workflow.

> **See [DEPLOYMENT.md](DEPLOYMENT.md)** for end-to-end notes from the actual
> first deployment, including the three non-obvious issues that came up
> (Railway's `$PORT` injection, missing `--environment` in CI, `railway up`
> picking the wrong Dockerfile when run from the wrong directory). The
> quick path below assumes you've read those caveats.

### Portability contract

Baseplate ships with Railway as the default deployment path because it's the
fastest way to get a small full-stack app online. **It is not Railway-coupled.**
The portability contract — what every supported platform must provide — is:

| Requirement | How Baseplate uses it |
|---|---|
| Standard Docker containers | Both services build as multi-stage images |
| `$PORT` env var at runtime | Both services bind to `$PORT` (or their dev default) |
| Non-root container runtime | Both run as uid 1000 by default |
| HTTP healthchecks | `/api/health` (backend), `/healthz` (frontend) |
| Environment-variable config | All secrets and tunables are env-driven |
| Managed Postgres | The only required external service |
| One-off command on deploy | Backend's CMD runs `alembic upgrade head` before `uvicorn` |

That means Baseplate runs unchanged on Render, Fly.io, Google Cloud Run, AWS
App Runner / ECS Fargate, and Kubernetes — though only **Railway is
first-class-verified today**. Treat other platforms as reachable but
unverified until smoke-tested examples land.

**To swap platforms**: delete `.github/workflows/deploy-railway.yml`, add a
`deploy-<platform>.yml` alongside it using the same `workflow_run` trigger
pattern. Both Dockerfiles are already platform-agnostic; no app-layer change
needed.

### Default: Railway

The repo ships with `.github/workflows/deploy-railway.yml`. It's dormant until
you flip a switch, so a freshly cloned starter doesn't fail CI before a
project exists.

**First-time setup:**

1. Create a Railway project with three services: `backend`, `frontend`, and a PostgreSQL plugin.
2. Set environment variables on each Railway service:
   - **backend**: `DATABASE_URL` (from Postgres plugin), `JWT_SECRET`, `ADMIN_EMAIL`, `ADMIN_PASSWORD_HASH`, `COOKIE_SECURE=true`, `CORS_ORIGINS=["https://your-frontend.up.railway.app"]`
   - **frontend**: `API_URL` (internal Railway URL of the backend, e.g. `http://backend.railway.internal:8001`)
3. Add two GitHub **secrets** to your repo:
   - **`RAILWAY_TOKEN`** — a **workspace/account token** (Railway → Account Settings → Tokens). *Not* a per-project token. The workflow feeds it to the CLI as `RAILWAY_API_TOKEN`; a project token in this slot fails with `Invalid RAILWAY_TOKEN`.
   - **`RAILWAY_PROJECT_ID`** — the project's ID (Railway project → Settings).
4. Add a GitHub **variable** (not secret): **`RAILWAY_DEPLOY_ENABLED=true`** under Settings → Secrets and variables → Actions → Variables. This is the gate that turns deploys on.
5. Push to `main`. CI runs first; once it succeeds, the deploy workflow fires.

### How the workflows fit together

- `ci.yml` runs on every push and PR — backend ruff + pytest, frontend typecheck + ESLint + vitest + build.
- `deploy-railway.yml` triggers on `workflow_run: CI completed`, only when the CI run was successful, only on `main`, and only when `vars.RAILWAY_DEPLOY_ENABLED == 'true'`. Without the variable, the deploy workflow's jobs are skipped (no failure).
- Deploy uses `railway up --service <name>`, which builds each service's Dockerfile on Railway's infrastructure.

### Swapping platforms

Delete `deploy-railway.yml` and add a `deploy-<platform>.yml` alongside it. Use the same `workflow_run` trigger pattern so deploys still gate on CI success. Both Dockerfiles are already platform-agnostic (read `$PORT` at runtime).

### Railway environment notes

- Railway provides `DATABASE_URL` in the standard `postgresql://` format. The backend config expects `postgresql+asyncpg://` — you may need to adjust the variable or add a prefix in Railway's variable references.
- Both Dockerfiles expose their dev ports (backend `8001`, frontend `3001`) and read `$PORT` at runtime. Railway injects `$PORT` automatically.
- Both images run as **non-root** users (uid 1000 in each — `app` for backend, `node` for frontend) and ship a Docker `HEALTHCHECK` directive. The backend image is multi-stage so `build-essential` doesn't ship to production.
- The backend Dockerfile's CMD runs `alembic upgrade head` before launching uvicorn, so migrations apply on every deploy. No manual `make migrate` needed in production.

## Testing

### Backend

Tests use SQLite (via aiosqlite) instead of PostgreSQL so they run without Docker. The `conftest.py` sets up an in-memory test database, overrides FastAPI's `get_db` dependency, and generates a real bcrypt hash for auth tests.

```bash
make test-backend       # runs pytest -v
```

To add tests, create files in `backend/tests/test_*.py`. The `client` fixture gives you an authenticated-capable `httpx.AsyncClient`:

```python
@pytest.mark.asyncio
async def test_my_endpoint(client):
    await _login(client)  # sets auth cookie
    response = await client.get("/api/admin/widgets")
    assert response.status_code == 200
```

### Frontend

Tests use Vitest with jsdom and Testing Library. The setup file is at `src/__tests__/setup.ts`.

```bash
make test-frontend      # runs vitest run
```

## Gotchas and things to know

- **`/docs` is disabled in production.** Set `DEBUG=true` to enable the Swagger UI at `/docs` and ReDoc at `/redoc`. This is controlled in `main.py`.
- **Rate limiting** is set to 60 requests/minute globally via SlowAPI. Adjust in `main.py`. Add per-endpoint limits with `@limiter.limit("10/minute")` on individual route handlers.
- **The middleware.ts deprecation warning** — Next.js 16 is renaming the `middleware.ts` convention to `proxy.ts`. The current file still works but you'll see a build warning. Rename when ready.
- **UUID primary keys** — all models use UUID v4 via PostgreSQL's native UUID type. The `uuid_pk()` helper in `models/base.py` handles this.
- **`from_attributes = True`** on response schemas means you return SQLAlchemy model instances directly from routes — Pydantic serializes them automatically.
- **The frontend proxies `/api/*`** to the backend via Next.js rewrites in `next.config.ts`. The browser never talks to the backend directly. This avoids CORS issues and keeps the backend URL private.
- **Cookies require HTTPS in production.** `COOKIE_SECURE=true` (the default) means auth cookies won't be sent over plain HTTP. This is correct for production. Set `false` for local dev without HTTPS.
