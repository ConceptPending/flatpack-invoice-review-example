# Recipes

Guided transformations of Baseplate. Each recipe is a self-contained "if
you need this pattern, here's how it fits onto what Baseplate already
ships."

These are deliberately **not features in the base app**. Adding every
recipe to the default codebase would make it less compact and harder
for an LLM to hold in context — exactly what Baseplate is trying to
avoid. Apply the recipes you need; leave the rest.

## Format

Every recipe follows the same shape:

1. **What it is + when to use it** — one paragraph.
2. **What you'll add** — the file list, so the scope is visible upfront.
3. **Step-by-step** — concrete code snippets, not abstractions. Names the
   convention being used (service layer, router-level deps, CSRF middleware
   contract, etc.).
4. **Tests** — the assertions that prove the recipe is wired correctly.
5. **What to skip** — adjacent things that look like they belong but
   would expand scope unnecessarily.

## How to use a recipe with a coding agent

Point the agent at the recipe file directly:

> Apply `docs/recipes/audit-log.md` to this codebase. Use the existing
> `ItemService` as the model for any service-layer changes.

The agent reads the recipe, follows the steps, and produces a working
implementation. Because Baseplate's conventions are documented in
`CLAUDE.md` and the recipe assumes them, the result lands consistent
with the rest of the codebase.

## Available recipes

### [Audit log](audit-log.md)
Record who did what when. For apps with compliance, case management, or
internal review queues where a tamper-resistant action history matters.

### [Public submission + admin queue](public-submission-and-admin-queue.md)
Unauthenticated public form → admin review queue with status workflow.
The canonical "intake + review" pattern: applications, complaints,
support requests, candidate submissions, content moderation.

### [SSO via OpenID Connect](sso-oidc.md)
Lets users log in via their company identity (Google Workspace as the
canonical example; Microsoft Entra ID and generic OIDC as variants).
Domain-allowlisted, additive to local password auth, with explicit
refusal to auto-link by email collision. The first "Internal Tools"
recipe.

### [User-management admin page](admin-users.md)
Lets admins create, list, and deactivate other admins via the UI. Adds
`is_active` to `User`, blocks self-deactivation, refuses to demote or
deactivate the last active admin. Pairs naturally with the SSO recipe
once people can log in via Google Workspace and you need a place to
see who has access.

### [Email intake → admin review queue](email-intake.md)
Scheduled IMAP poll turns an inbox into a submission queue. Composes
with the public-submission recipe — same queue UI, same status workflow,
just a different intake mechanism. Idempotent via `Message-ID`.

## Suggested future recipes (not yet written)

These came up in scoping but haven't landed yet. Open a PR if you
write one. Grouped by the audience that's most likely to want them.

### General patterns

- **Document upload model** — file storage + metadata + admin viewer (S3/R2-compatible)
- **Scheduled importer** — APScheduler job that fetches external data
  and stores it with a `last_synced_at` column
- **Status workflow with allowed transitions** — explicit state machine
  on a model (composes with `audit-log.md`)
- **Soft delete + archive** — `deleted_at` column, query helpers, admin
  "restore" UI
- **Read-only public page backed by admin CRUD** — `(public)/`-route-group
  pattern, beyond what the example `Item` already shows

### Internal Tools track

These layer onto the existing SSO, admin-users, and email-intake
recipes to make Baseplate a credible internal-app foundation.

- **Google Workspace connector** — read Drive files, list Docs/Sheets,
  optionally Calendar. Service-account auth.
- **Microsoft 365 / Graph connector** — SharePoint, OneDrive, Outlook
  files. Most Microsoft-shop internal tools need this.
- **Read-only database sync** — pull from an existing operational
  database (Postgres / MySQL / SQL Server) into Baseplate tables on a
  schedule; explicit allowlist of source queries/views.
- **Outbound email notifications** — SES / Postmark / SendGrid /
  Resend, with templates and unsubscribe handling
- **AI extraction + human-in-the-loop review** — upload doc, LLM
  extracts structured fields, admin reviews and approves. The
  canonical "AI workflow" use case.
- **Webhook-based email intake** — Postmark/SendGrid inbound webhooks
  as a lower-latency alternative to IMAP polling

### Growth-path recipes

For apps moving from "small one-off" to something bigger. Living in
[`../growth-paths/`](../growth-paths/) when they exist.

- **Multi-tenant migration** — already written; see
  [`../growth-paths/multi-tenant.md`](../growth-paths/multi-tenant.md)
- **Celery / Redis worker for durable jobs** — when APScheduler's
  in-process model isn't enough
- **Stripe billing** — subscription + plan limits; for the SaaS path
- **SAML SSO** — for enterprise customers who can't use OIDC
- **Role-based access control** — beyond the `is_admin` binary
