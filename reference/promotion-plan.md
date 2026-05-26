# Promotion plan: Supplier invoice cleaner

**Source:** `./original-flatpack.html`
**Manifest version:** 0.2.0
**Date:** 2026-05-26
**Prepared by:** Promotion-time agent following `prompts/promote-flatpack.md`

Every claim in this plan is labelled with one of three confidence tiers:

- **MANIFEST-ASSERTED** — taken directly from the Flatpack's
  `<script type="application/json" id="flatpack-manifest">` block. Trust it.
- **CODE-INFERRED** — extracted by reading the JS. Reliable for behaviour,
  worth a second pass with the user.
- **INTERVIEW-REQUIRED** — the Flatpack does not answer this. Asked of the
  user during the promotion conversation.

---

## Why this is being promoted **INTERVIEW-REQUIRED**

The finance team has been using the supplier-invoice cleaner for monthly
batches since March. As of last month, two more reviewers were added.
Three triggers from the Flatpack's `promotionSignals` are now firing:

1. **Multiple reviewers need to share an invoice batch.** Reviewers
   currently email each other a JSON export of column mappings; this is
   already a hack around the single-user assumption.
2. **Validated invoices must be stored centrally and de-duplicated
   across files.** Right now `invoice_number` uniqueness is enforced
   *within* a file. Two separate batches with the same supplier and
   number are not caught.
3. **Audit history of imports and changes is required.** Finance lead
   asked for a paper trail of who approved which corrections.

Two more from the manifest are not firing yet but are visible on the
horizon: supplier records reused across batches, and per-currency
totals to finance on a recurring basis. The new Baseplate app should
make these cheap to add later, not solve them now.

## Archetype and recipe mapping

Archetype (from manifest): `import-validate-store` **MANIFEST-ASSERTED**

Recommended Baseplate recipes (composed):

- `admin-users` — needed for the named reviewers, who must authenticate.
- `audit-log` — covers the new "who approved this correction" requirement.
- `public-submission-and-admin-queue` — adapted: the "public submission"
  surface becomes the authenticated CSV-upload page; the admin queue
  becomes the review interface. **INTERVIEW-REQUIRED:** confirm with the
  user whether suppliers themselves submit, or only finance staff upload
  on their behalf. This document assumes the latter.

Gaps not covered by any current Baseplate recipe:

- Cross-file invoice-number de-duplication (custom; see Validations).
- Per-currency totals dashboard (custom; not blocking).

## Entities

### Invoice **MANIFEST-ASSERTED**

Fields (from manifest):

| Field | Type | Constraints |
|---|---|---|
| `supplier_name` | string | required |
| `invoice_date` | date | required; not in the future |
| `invoice_number` | string | required; unique **per supplier across all batches** (see open questions) |
| `amount` | number | required; > 0 |
| `currency` | string | default GBP; out-of-list is a warning |

Indexes:

- `(supplier_id, invoice_number)` unique — strengthens the Flatpack's
  per-file uniqueness to per-supplier across the whole dataset.
- `invoice_date` for the per-period reporting use case.

### Supplier **CODE-INFERRED**

The Flatpack treats supplier_name as a free-text string. The
`promotionSignals` mention "Supplier records become a reference list
reused across batches." The Baseplate version separates supplier
identity from the string on each invoice.

| Field | Type | Constraints |
|---|---|---|
| `name` | string | required, unique |
| `aliases` | list[string] | optional; covers the same supplier with different spellings |

### ReviewBatch **INTERVIEW-REQUIRED**

Open: does the team think of each upload as a discrete batch (rolled
back or approved as a unit), or as a stream of invoices that happen
to arrive together? The audit-history trigger suggests yes-batches.
If so:

| Field | Type | Constraints |
|---|---|---|
| `uploaded_by` | user | required |
| `uploaded_at` | datetime | required |
| `source_filename` | string | |
| `status` | enum | `pending` / `approved` / `rejected` |
| `clean_count` | int | derived |
| `error_count` | int | derived |

### ValidationError **CODE-INFERRED**

Mirrors the Flatpack's `errors` array shape. Persists across sessions
so a reviewer can come back to a row tomorrow.

| Field | Type | Constraints |
|---|---|---|
| `batch_id` | ReviewBatch | required |
| `original_row` | json | required |
| `reasons` | list[string] | required |
| `resolution` | enum | `unresolved` / `corrected` / `dismissed` |
| `resolved_by` | user | nullable |
| `resolved_at` | datetime | nullable |

## Roles **INTERVIEW-REQUIRED**

Two roles look right based on the team description:

- **Admin.** Manages suppliers, approves/rejects whole batches,
  inspects audit log.
- **Reviewer.** Uploads CSVs, sees own + other reviewers' open
  errors, corrects rows, marks errors resolved or dismissed.

Open: does anyone outside finance need read-only access for
reporting? If yes, a third role `Reporter` is cheap to add now.

## Required features

| Feature | Tier | Notes |
|---|---|---|
| Auth (named users + login) | INTERVIEW-REQUIRED | Recipe: `admin-users` |
| Persistent storage for Invoice, Supplier, ReviewBatch, ValidationError | MANIFEST-ASSERTED | Implied by entities |
| Field-level validation per manifest rules | MANIFEST-ASSERTED | Carry the rules verbatim |
| **Cross-file** invoice-number uniqueness | CODE-INFERRED | Strengthens the Flatpack's per-file rule; flagged in triggers |
| CSV upload endpoint | CODE-INFERRED | Mirrors Flatpack's IMPORT_EXPORT |
| Clean CSV export endpoint | MANIFEST-ASSERTED | Exports list |
| Errors CSV export endpoint | MANIFEST-ASSERTED | Exports list |
| Printable summary | MANIFEST-ASSERTED | Exports list |
| Audit log of corrections + approvals | INTERVIEW-REQUIRED | Recipe: `audit-log` |
| Admin screen for supplier management | INTERVIEW-REQUIRED | Custom |
| Seed data from `./sample-data.csv` (extract from Flatpack) | CODE-INFERRED | Integration tests |

## Validation rules (carry-over from manifest)

Verbatim from the Flatpack's manifest. The Baseplate app must
preserve these:

- `supplier_name, invoice_date, invoice_number, amount are required` **MANIFEST-ASSERTED**
- `amount must be greater than zero` **MANIFEST-ASSERTED**
- `invoice_date must be a valid date and not in the future` **MANIFEST-ASSERTED**
- `currency outside [GBP, EUR, USD] is a warning and defaults to GBP` **MANIFEST-ASSERTED**
- `currency normalises to upper case and trims whitespace` **MANIFEST-ASSERTED**

Strengthened from the Flatpack:

- `duplicate invoice_number within a file is an error` becomes
  `duplicate (supplier, invoice_number) anywhere in the dataset is an
  error` **CODE-INFERRED** (this is the actual user need; the
  per-file rule was a Flatpack limitation, not a business rule).

## UI / screens

| Screen | Mirrors which Flatpack region | Tier |
|---|---|---|
| Upload + column-map page | the dropzone + mapping card | CODE-INFERRED |
| Review queue (rows with errors) | the preview table | CODE-INFERRED |
| Per-row correction modal | new — Flatpack had no inline correction | INTERVIEW-REQUIRED |
| Batch summary + approval | the stats + warnings cards | CODE-INFERRED |
| Supplier management (admin only) | new | INTERVIEW-REQUIRED |
| Audit log (admin only) | new | INTERVIEW-REQUIRED |
| Per-currency totals dashboard | the print summary's currency breakdown | CODE-INFERRED |

## Test cases to carry over

Sourced from `FLATPACK:TEST_CASES`. These become backend unit tests.

| Flatpack test | Baseplate test target |
|---|---|
| `parseCSV handles quoted commas` | CSV parser service |
| `validateRow flags future invoice date` | Invoice validator |
| `amount must be > 0` | Invoice validator |
| `unknown currency is a warning, not an error` | Invoice validator |
| `currency normalisation lowercases gbp → GBP` | Currency normaliser |
| `cleanAndValidate detects duplicate invoice numbers` | Becomes a *cross-file* test, not per-file |
| `autoMap picks Vendor for supplier_name and CCY for currency` | Column-mapping suggester |

Add a parity test (see `tools/verify-promotion.mjs` once Baseplate's
verifier exists): feed the same sample CSV through both the Flatpack
and the Baseplate version, assert identical clean.csv and errors.csv.

## Open questions for the user **INTERVIEW-REQUIRED**

1. Do suppliers ever submit their own invoices, or only finance
   uploads on their behalf? (Determines whether the
   `public-submission-and-admin-queue` recipe's public surface is
   authenticated or open.)
2. Are batches the unit of approval, or are individual invoices
   approved one by one? (Determines whether `ReviewBatch` is a real
   entity with state.)
3. Do you need read-only reporter accounts?
4. Should approvers be allowed to override a duplicate detection?
   If so, that override is a high-value audit-log event.
5. Cross-file dedup: should suppliers be auto-matched by name with
   aliases, or always confirmed by a reviewer the first time?
6. Do per-currency totals need to feed into a downstream system
   (accounts, reporting), or is the dashboard enough?

## What is explicitly out of scope

- Foreign-exchange conversion. The Flatpack reports per-currency
  totals; the Baseplate version does the same. No FX maths.
- Supplier-facing portal. Suppliers are entities in the database; they
  do not log in.
- Invoice-line-item breakdown. The Flatpack treats invoices as single
  amounts; the Baseplate version preserves that. Line items are a
  separate project.
- PDF generation. Print stays as browser print. Server-side PDF is a
  future recipe.
- Multi-tenancy. One organisation. (If multiple orgs become a
  requirement, that is a *second* promotion event.)

## Hand-off

Once this plan is approved:

1. Open a new Baseplate project for `invoice-review`.
2. Copy `./original-flatpack.html` and `./sample-data.csv` (extract
   from the Flatpack's `SAMPLE_CSV`) into the new project's
   `reference/` directory.
3. Apply Baseplate recipes per the mapping above.
4. Carry the validation rules and test cases into the new project's
   tests.
5. Once the Baseplate app is running, use Baseplate's
   `tools/verify-promotion.mjs` (when available) to assert every
   MANIFEST-ASSERTED claim still holds.
6. Keep the Flatpack alive for fast local iteration and parity checks
   until the Baseplate version reaches parity.
