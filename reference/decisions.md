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

**Implication:** No read-only `Reporter` accounts at v1. (Update: when
the lifecycle-state-machine recipe was applied, the batch workflow gained
per-user lifecycle roles — `reviewer` and `approver` — on top of the
`is_admin` gate; see `app/roles.py` and `app/statespec/batch_spec.py`.
`Reporter` remains deferred until the audit log gets a non-admin viewer.)

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

### C. `Invoice.supplier_name` becomes `Invoice.supplier_id`

The Flatpack's manifest declares `supplier_name` as a string field on
the Invoice entity. The Baseplate version factors supplier identity
out into a separate `Supplier` table and replaces the field with a
foreign key `supplier_id` on `Invoice`. The supplier's name is on
the `Supplier` row, not on the `Invoice` row.

This is a real semantic change driven by the manifest's
`promotionSignal`: *"Supplier records become a reference list reused
across batches."* Without the FK, cross-batch reuse would either
require name-equality string matching (fragile) or duplicate the
supplier as a string on every Invoice (the Flatpack's behaviour).

`make verify-promotion` correctly flags this as
`MISS entity Invoice.supplier_name — no column named 'supplier_name'
on table 'invoices'`. The MISS is **expected and desirable** — it is
honest about a structural change the promotion made. A real CI gate
in a similar project would either:

1. Accept this MISS by listing it in a project-level allowlist
   (e.g. `reference/expected-misses.json` — not yet a convention).
2. Update the manifest's `entities[]` to reflect the post-promotion
   shape (but the manifest is the **Flatpack's** declaration, frozen
   at promotion time — modifying it muddies the source-of-truth).
3. Make the case in the project README that this MISS represents
   intentional, documented divergence.

For this worked example, option (3) — the README's "What we learned"
section captures the trade-off.

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
