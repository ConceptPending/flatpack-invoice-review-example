# Changelog

All notable changes to this project are documented here. Format based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); this project follows
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Changed
- **Renamed project from Framework to Baseplate.** The repo is now `ConceptPending/baseplate` (old URLs redirect). Doc references updated throughout. Python `app/` package and example "MyApp" placeholders unchanged — those represent the user's app, not Baseplate itself.
- **README rewritten** to lead with concrete use cases ("Directory or data product", "Internal operations dashboard", "Intake + review queue", "AI workflow with human-in-the-loop", "Niche structured CMS", "Scheduled monitor") and named personas (solo founders, consultants, domain experts with technical help, internal tools engineers, founders validating non-SaaS products). Adds explicit "Who this is *not* for" qualifiers. New "What if my app grows into a SaaS?" section pointing at the growth-path doc. New "Portability contract" table documenting the Docker contract.

### Added
- `docs/growth-paths/multi-tenant.md` — step-by-step migration guide for evolving Baseplate from single-tenant → multi-org → SaaS. Names the architectural seams already in place (service layer, centralised auth context, alembic migrations), what to add at each stage, what to test for tenant isolation, and which migration anti-patterns to avoid.
- `frontend/src/app/api/[...path]/route.ts` — runtime proxy for `/api/*` to the backend. Reads `process.env.API_URL` per request rather than at build time.

### Fixed
- **Frontend `API_URL` is now read at runtime.** Previously the `next.config.ts` rewrite baked the destination URL into `server.js` at `next build` time, which meant each environment required its own Docker image (Railway worked only because it auto-passes env vars as `--build-arg` during the Dockerfile build). Replacing the rewrite with a Route Handler at `app/api/[...path]/route.ts` means one image runs unchanged across dev/staging/prod with only the `API_URL` env var differing.

### Removed
- `next.config.ts` rewrites — superseded by the route handler.
- `ARG API_URL` / `ENV API_URL=$API_URL` in `frontend/Dockerfile` — no longer needed at build time.

### Added (recipes)
- `docs/recipes/` — guided transformations of Baseplate. First two:
  - **`audit-log.md`** — append-only audit table with single-entry-point service, hooks into existing CRUD on `Item`, admin viewer. For compliance, case management, internal review queues.
  - **`public-submission-and-admin-queue.md`** — the intake + review pattern. Unauthenticated public form (CSRF-exempt + rate-limited) → admin review queue with status workflow.
- `docs/recipes/README.md` — index + recipe format spec ("what it is", "what you'll add", "step-by-step", "tests", "what to skip until you need it"). Naming conventions so future recipes are consistent.
- README's "Extending Baseplate" section now points at the recipes directory.

### Added (example app)
- **`ConceptPending/baseplate-example-feedback`** — a working application built by taking Baseplate v0.1.0, removing the `Item` example, and applying the public-submission-and-admin-queue recipe. ~12 file changes total, the same kind of work an LLM following the recipe would produce. README now links to it under "Extending Baseplate" so readers can see what a recipe produces.

### Changed (positioning)
- README adds two new sections — **"The core idea"** and **"Why one-off apps matter now"** — between the live-demo callout and "What you can build." Makes the agent-first thesis explicit ("agents are good at extending patterns, bad at inventing foundations") and names the cultural wave ("too important for spreadsheets, too specific for SaaS").
- Sharpened the consultant line in "Who this is for" to call out the consultant use case more concretely: same foundation per engagement, client owns the code, easier handover.

### Added (recipes — Internal Tools track)
- **[`sso-oidc.md`](docs/recipes/sso-oidc.md)** — OIDC SSO recipe leading with Google Workspace. Domain-allowlisted, additive to local password auth (env-var bootstrap admin remains as emergency fallback), explicit refusal to auto-link by email collision (account-takeover defence). Variants for Microsoft Entra ID and generic OIDC. PKCE on by default; refresh tokens, group-claim mapping, and SAML deferred to growth-path recipes. Composes with the audit-log recipe.
- **[`admin-users.md`](docs/recipes/admin-users.md)** — admin UI for inviting + deactivating other admins. Adds `is_active` to `User`; service-layer safety constraints (cannot self-deactivate; refuses to demote/deactivate the last active admin) are deliberate redundancy with the UI. No deletion (preserves audit trail). Pairs with the SSO recipe and audit-log recipe.
- **[`email-intake.md`](docs/recipes/email-intake.md)** — scheduled IMAP poll turns an inbox into an admin review queue. Composes with the public-submission recipe (same queue UI + status workflow; intake mechanism changes). Idempotent via `Message-ID` + DB unique constraint + `\Seen` flag set after commit so crash-mid-loop recovers cleanly. Deferred: inbound SMTP, webhook-based intake, attachments, HTML parsing, threading, auto-acknowledge replies, multiple inboxes, OAuth-IMAP.

### Changed (README headline)
- Hoisted **"Too important for spreadsheets. Too specific for SaaS."** to a blockquote immediately under the badges, before the tagline. The phrase now leads the README rather than living buried in "Why one-off apps matter now." Section 2 rewritten to reference the line inline instead of repeating it as a callout.
- GitHub repo description updated to lead with the same line.
- Dropped the specific "~24 files of business logic" claim (was accurate at v0.1.0; the codebase has grown to ~50 source files and the literal number was undersold + would keep drifting). The substantive claim — "small enough to fit in a coding agent's context window" — stays.

### Changed (Internal Tools surface)
- README's "What you can build with this" list adds **"Internal tool with company data"** as a sixth shape, naming the SSO + user-management + email-intake recipes as the optional layer between the small default app and full company-data integration.
- `docs/recipes/README.md` "Suggested future recipes" reorganised into **General patterns**, **Internal Tools track**, and **Growth-path recipes** with the candidates from the strategic feedback (Google Workspace / Microsoft Graph connectors, read-only DB sync, outbound email, AI extraction + HITL, webhook email intake, Celery/Redis, Stripe, SAML, RBAC, soft delete, status workflow, document upload, scheduled importer).

### Added (OpenAPI typed client)
- **`make generate-client`** — regenerates `frontend/src/lib/api-types.ts` from the FastAPI OpenAPI spec via `openapi-typescript`. No backend server needed; the new `backend/scripts/dump_openapi.py` imports `app.main` directly and prints the schema to stdout.
- **`frontend/src/lib/api-types.ts`** — generated TypeScript types for every Pydantic schema. Committed so LLMs and `tsc` can rely on it without running the generator.
- **`frontend/src/lib/types.ts`** rewritten as a tiny adapter that re-exports clean names (`Item`, `User`, `ItemCreate`, `ItemUpdate`, etc.) from the generated types. Existing imports keep working; the source of truth shifts to the backend Pydantic models.
- `lib/api.ts` updated: `createItem(data: ItemCreate)`, `updateItem(id, data: ItemUpdate)`, `login(...)` returns `LoginResponse`. Request/response shapes are now derived from the backend instead of duplicated.

### Added
- Live demo deployment on Railway (frontend, backend, Postgres). README links to the public URL.
- `DEPLOYMENT.md` with end-to-end CLI deploy steps, GitHub Actions wiring instructions, and a "Issues hit" section documenting the three real footguns (`$PORT` injection, missing `--environment` in CI, `railway up` cwd dependency).

### Fixed
- `deploy-railway.yml`: pass `--environment production` to `railway up`. Without it the CLI errors with "No environment specified" in CI (no `.railway/` link dir).

## [0.1.0] — 2026-05-24

Initial public release.

### Added

**Backend** — FastAPI 0.115+ with SQLAlchemy 2 async, Pydantic v2, Alembic
migrations, and an example `Item` CRUD slice (model → migration → service →
routes). Structured logging via structlog with `X-Request-ID` propagation,
per-endpoint rate limiting via SlowAPI (5/min on `/api/auth/login`, 60/min
default), and a background scheduler scaffold via APScheduler.

**Authentication** — `users` table (`email`, `password_hash`, `is_admin`),
email-based login with bcrypt verification, JWT in `HttpOnly` + `SameSite=Lax`
cookies (JWT `sub = user.id` UUID so renames don't invalidate sessions).
Idempotent admin bootstrap from `ADMIN_EMAIL` + `ADMIN_PASSWORD_HASH` on first
startup. Startup validation refuses to boot with default or short (<32 byte)
JWT secrets. Identical responses for wrong-password vs unknown-user (no
enumeration via timing or error messages).

**CSRF protection** — Double-submit cookie middleware on all non-safe,
non-exempt writes. Token issued on login and via `GET /api/auth/csrf`. Frontend
`fetchAPI` auto-attaches the `X-CSRF-Token` header.

**Frontend** — Next.js 16 App Router with `(public)` and `admin` route groups,
React 19, Tailwind CSS 4, TypeScript strict mode. Shared UI components
(`Button`, `Card`, `Input`, `Modal`, `StatusPill`, `ErrorBanner`) with
CSS-variable theming for light/dark mode. Typed API client. `useRequireAuth`
hook plus Next.js middleware for unauthenticated redirects.

**Infrastructure** — Multi-stage backend Dockerfile (build tools stripped from
runtime), non-root containers (uid 1000 in both images), `HEALTHCHECK`
directives, `/healthz` route on the frontend. Alembic migrations run on
container start; no manual step.

**CI/CD** — Platform-agnostic `ci.yml` (lint + tests + build, runs on every
push/PR). Opt-in `deploy-railway.yml` triggered via `workflow_run` after CI
success, gated on `vars.RAILWAY_DEPLOY_ENABLED == 'true'` so a fresh clone
doesn't fail CI before Railway is set up. Dependabot weekly with majors split
from grouped minor/patch updates.

**Tests** — 21 backend tests (pytest + aiosqlite — no Postgres required), 8
frontend tests (vitest + happy-dom + Testing Library). All gated by CI.

**Developer experience** — `make dev` brings up Postgres + backend (:8001) +
frontend (:3001) in parallel. Pre-commit hooks (ruff check + ruff format + tsc
+ ESLint + standard housekeeping). `make hash-password` for bcrypt generation.
Single-command tests, single-command lint.

**LLM-friendly docs** — [`CLAUDE.md`](CLAUDE.md) documents conventions, dev
commands, gotchas, anti-patterns to fix when seen, and a definition-of-done
checklist. [`.github/copilot-instructions.md`](.github/copilot-instructions.md)
mirrors it for non-Claude harnesses. README includes a 10-step recipe for
adding new domain models, plus full architecture overview.

**Repository hygiene** — MIT licensed, `.env.example` files tracked at three
levels, `CONTRIBUTING.md`, `SECURITY.md`, GitHub PR template, README badges.

[Unreleased]: https://github.com/ConceptPending/baseplate/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/ConceptPending/baseplate/releases/tag/v0.1.0
