# Promotion decisions log

Answers given to the `INTERVIEW-REQUIRED` items in
[`promotion-plan.md`](promotion-plan.md). Captured here so the
reasoning is traceable from the code back to the promotion event.

> This document is for the worked example. In a real promotion, the
> answers come from the actual finance team — not from a notional
> exercise. Treat the answers below as illustrative.

## 1. Do suppliers submit their own invoices, or only finance uploads?

**Answer:** Finance uploads on suppliers' behalf.

**Implication:** The `public-submission-and-admin-queue` recipe is
**adapted** — the "public" surface becomes the authenticated CSV
upload page. CSRF protection stays on. No anonymous endpoints.

## 2. Are batches the unit of approval, or individual invoices?

**Answer:** Batches.

**Implication:** `ReviewBatch` is a real entity with a state machine
(`pending → approved | rejected`). Individual rows have validation
status but not approval status — they inherit the batch's.

## 3. Read-only `Reporter` accounts?

**Answer:** Not at v1. Defer.

**Implication:** Two roles only — admin and reviewer. Add `Reporter`
later when the audit log gets a non-admin viewer.

## 4. Allow override of duplicate detection?

**Answer:** Yes, but only by admins, and the override is a
high-value audit-log event.

**Implication:** The duplicate check raises an `OverridableError`
in the service layer. The admin UI gets a "duplicate detected —
override?" affordance with a required reason. Each override emits a
`duplicate.override` audit event. **Not built at v1 of this
scaffold** — flagged in the routes' TODO comments.

## 5. Supplier auto-matching by alias?

**Answer:** Require reviewer confirmation the first time a new
alias appears. After that, auto-match silently.

**Implication:** `Supplier.aliases` is a list. The upload service
auto-matches on exact name OR existing alias. New variants of
existing-supplier names raise a `SupplierAliasNeedsConfirmation`
flow. **Not built at v1** — for this scaffold the matcher is
strict-name-only; alias confirmation is on the v2 roadmap.

## 6. Do per-currency totals feed a downstream system?

**Answer:** Not yet — the dashboard is enough.

**Implication:** No webhook or API integration. Per-currency totals
appear in the batch summary endpoint and are visible to admins. No
scheduled job pushing them anywhere.

---

## Decisions logged outside the plan

Two decisions came up during the build that the promotion plan didn't
anticipate but are worth recording for parity-with-Flatpack reasons.

### A. Currency normalisation case

The Flatpack uppercases and trims currency strings. The Baseplate
version does the same in the Pydantic validator — at the API
boundary, not at the database boundary. Reason: the database
constraint is on the canonical form; we want bad inputs to fail
fast at the schema layer with a clear error, not at the DB layer
with a constraint-violation.

### B. The Flatpack's "warning" semantics for unknown currency

The Flatpack treats out-of-list currency as a *warning* and defaults
to GBP. The Baseplate version surfaces this as a `ValidationError`
record with `resolution: unresolved` and a suggested correction
(GBP), but persists no `Invoice` until a reviewer resolves it. This
is *stricter* than the Flatpack — the team flagged that "silently
defaulting" had bitten them once in the Flatpack era. Strengthening
constraints is allowed; relaxing is not.

This is captured under the validator's `currency` rule with an
explicit code comment pointing at this decisions file.
