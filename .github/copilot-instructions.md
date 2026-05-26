# Copilot / agent notes

Mirrors `CLAUDE.md` at the repo root. If you can read that file, prefer it — it's the canonical source. This file exists so non-Claude harnesses (Copilot, Cursor, Codex) get the same context.

Full-stack starter: FastAPI + Next.js 16 + PostgreSQL.

## Dev commands

```bash
make dev                          # Postgres + backend (:8001) + frontend (:3001)
make test-backend                 # pytest — uses SQLite via aiosqlite, no Postgres needed
make test-frontend                # vitest run
make lint                         # ruff (backend) + tsc --noEmit (frontend)
make migrate                      # alembic upgrade head
make migrate-new msg="add foo"    # autogenerate a new migration
```

## Conventions

**Backend** — Routes (`app/api/`) are thin: validate, call service, return. DB logic lives in `app/services/` as static methods. Models inherit `Base, TimestampMixin` and use `uuid_pk()`. Response schemas use `model_config = {"from_attributes": True}`. Register new models in `app/models/__init__.py`.

**Frontend** — Route groups `(public)/` and `admin/` have separate layouts. All API calls go through `lib/api.ts` with `credentials: "include"`. Server components fetch via `API_BASE` from `lib/server-config.ts`. Browser never hits the backend directly — Next.js rewrites `/api/*`.

## Adding a new model

See the 10-step recipe in `README.md` under "Adding a new domain model". The existing `Item` slice is the canonical reference.

## Gotchas

- **Ports**: backend `:8001`, frontend `:3001` everywhere (Makefile + both Dockerfiles). Railway injects `$PORT` to override at runtime.
- **Startup validation**: with `DEBUG=false`, backend refuses to boot with default secrets (`app/config.py:28-39`).
- **Backend tests use SQLite** via aiosqlite. Avoid Postgres-specific SQL in models without verifying SQLite compatibility.
- **Vitest uses happy-dom**; component tests with `@testing-library/react` work — see `__tests__/Button.test.tsx`.

## Patterns to avoid

- `catch (err: any)` — use `unknown` plus a narrow check.
- `.catch(() => {})` swallowing API errors silently — surface or log.

## Before declaring a task done

1. `make lint` must pass.
2. `make test-backend` and `make test-frontend` must pass.
3. Touched a model? Generate the migration with `make migrate-new` and read it.
4. Touched UI? Run `make dev` and verify in the browser.

## CSRF protection

Writes (POST/PUT/PATCH/DELETE) require an `X-CSRF-Token` header matching the `csrf_token` cookie. Login + `GET /api/auth/csrf` are exempt. The frontend's `fetchAPI` auto-attaches the header — don't call `fetch()` directly for writes. In tests, `_login()` returns the token; pass it as `headers={"X-CSRF-Token": csrf}`.
