# Flatpack archetype → Baseplate recipe map

The **canonical** mapping. When a Flatpack promotes into Baseplate,
its `archetype` field maps to a recipe set defined here.

The Flatpack repo publishes
[`docs/archetypes.md`](https://github.com/ConceptPending/flatpack/blob/main/docs/archetypes.md)
with the same 8 archetypes. That file gives *hints*; this file is
authoritative because the recipes belong to Baseplate.

If the two files disagree, this one wins. Open a PR against either
side to bring them back into alignment.

## How to read this map

For each archetype:

- **Recipes that always apply** — apply these first, in order.
- **Recipes that often apply** — depends on the open questions in
  the promotion plan. Apply if the relevant `INTERVIEW-REQUIRED`
  answer is yes.
- **Custom code** — what no current recipe covers. You'll write this
  fresh against the conventions in `CLAUDE.md`.
- **Worked example** — a real promoted Flatpack of this archetype,
  when one exists.

## The map

### `internal-tool`

A calculator / estimator / single-purpose form-and-result tool.
A user fills inputs, gets a number/quote/recommendation, sends it on.

**Always apply:**
- [`admin-users`](recipes/admin-users.md) — named users own the records they create.

**Often apply:**
- [`audit-log`](recipes/audit-log.md) — if records are referenced
  later by anyone other than their creator.

**Custom code:**
- The calculation itself. Translate `FLATPACK:CORE_LOGIC` into a
  `*Service` class.

**Worked example:** none yet.

---

### `import-validate-store`

Take a file (usually CSV), validate rows, persist the clean ones,
surface the broken ones for correction.

**Always apply:**
- [`admin-users`](recipes/admin-users.md)
- [`audit-log`](recipes/audit-log.md) — uploads and corrections are
  audit-worthy by default.
- [`public-submission-and-admin-queue`](recipes/public-submission-and-admin-queue.md)
  — *adapted*: the "public" surface becomes the authenticated upload
  page; the queue UI lists batches or rows depending on the answer
  to "are batches the unit of approval?"

**Often apply:**
- [`sso-oidc`](recipes/sso-oidc.md) — if the team uses Google
  Workspace / Entra and "named users" should mean "company login".
- [`email-intake`](recipes/email-intake.md) — if records sometimes
  arrive by email instead of CSV upload.

**Custom code:**
- Column-mapping suggester (carry over from the Flatpack's `autoMap`).
- Cross-file uniqueness checks (the Flatpack's per-file rule almost
  always strengthens to "unique anywhere in the dataset").
- Reference-data entities the Flatpack treated as strings (e.g.
  `Supplier`, `Account`).

**Worked example:**
[invoice-cleaner-promotion](https://github.com/ConceptPending/flatpack/tree/main/case-studies/invoice-cleaner-promotion).

---

### `workflow-with-checklist`

A sectioned checklist someone walks through for a single project,
matter, or kickoff. Progress + notes per item; report on completion.

**Always apply:**
- [`admin-users`](recipes/admin-users.md)
- [`audit-log`](recipes/audit-log.md) — who ticked what, when.

**Often apply:**
- Status-workflow recipe (not yet written; suggested in
  `docs/recipes/README.md`'s future-recipes list). Until that lands,
  write the state machine as custom code on the `Run` model.

**Custom code:**
- The checklist template itself. Templates are versioned data, not
  recipes — keep them in a `checklist_templates` table.
- The `Run` entity (one walk-through of a template) and its progress
  state.

**Worked example:** none yet.

---

### `decision-log`

Guided form producing a structured written decision — title,
context, options, recommendation, risks, next steps.

**Always apply:**
- [`admin-users`](recipes/admin-users.md)
- [`audit-log`](recipes/audit-log.md) — versions of a decision and
  who approved them.

**Often apply:**
- A status-workflow recipe (proposed → approved → superseded) when
  one lands.
- [`sso-oidc`](recipes/sso-oidc.md) — if decisions need to be
  attributed to corporate identities.

**Custom code:**
- The decision shape (often different per decision type — technical,
  hiring, policy). Use a `kind` enum + per-kind validators.
- Cross-references between decisions (supersedes / references / blocks).

**Worked example:** none yet.

---

### `branching-questionnaire`

Walk the user through a decision tree of questions; leaves carry a
recommendation; record of the path.

**Always apply:**
- [`admin-users`](recipes/admin-users.md) — only if the recommendation
  must be logged; otherwise the questionnaire can be anonymous.

**Often apply:**
- [`public-submission-and-admin-queue`](recipes/public-submission-and-admin-queue.md)
  — if the questionnaire is the front end and the recommendations
  become a queue (e.g. eligibility triage).
- [`audit-log`](recipes/audit-log.md) — if recommendations have
  legal or compliance significance.

**Custom code:**
- The tree definition. **Version it** — promoted questionnaires
  almost always need version history of the tree itself.
- The path-record entity (one walk-through, the answers given, the
  recommendation reached).

**Worked example:** none yet.

---

### `case-workspace`

A working file for one matter — dated events with tags, source
references, filterable list, exports.

**Always apply:**
- [`admin-users`](recipes/admin-users.md)
- [`audit-log`](recipes/audit-log.md) — chronologies in legal /
  incident / compliance contexts almost always need a tamper trail.

**Often apply:**
- [`email-intake`](recipes/email-intake.md) — events often arrive by
  email forwarding.
- [`sso-oidc`](recipes/sso-oidc.md) — for organisational
  attribution.

**Custom code:**
- The `Matter` (or `Case`) entity as the parent.
- Tagging vocabulary table (standardised across users — a Flatpack's
  free-text tags don't survive multi-user).
- Document/exhibit reference table if events link to external files.

**Worked example:** none yet.

---

### `searchable-lookup`

Holds a body of reference data (a playbook, glossary, regulation
extract, FAQ) and lets the user search.

**Always apply:**
- [`admin-users`](recipes/admin-users.md) — entry authors are named.
- [`audit-log`](recipes/audit-log.md) — when an entry changes, who
  changed it.

**Often apply:**
- [`sso-oidc`](recipes/sso-oidc.md) — for internal knowledge bases.
- A status/visibility workflow (draft / published / archived) — when
  the recipe lands, until then custom.

**Custom code:**
- Full-text search. Postgres `tsvector` columns and a `to_tsquery`
  endpoint, written against the conventions in `CLAUDE.md`.
- Entry cross-linking and backlinks.

**Worked example:** none yet.

---

### `customer-readout`

Takes internal data and produces a polished customer-facing document
(proposal, status report, board pack).

**Always apply:**
- [`admin-users`](recipes/admin-users.md)
- [`audit-log`](recipes/audit-log.md) — every sent document is a
  logged event.

**Often apply:**
- [`public-submission-and-admin-queue`](recipes/public-submission-and-admin-queue.md)
  — *inverted*: the "public" surface is the customer acceptance
  page, not a submission form.
- Outbound-email recipe (not yet written) for sending the readout.

**Custom code:**
- PDF generation. Browser print is rarely enough for customer-facing
  docs — server-side PDF via a tool like WeasyPrint or Playwright is
  usually needed.
- Brand-controlled templates.
- Acceptance/sign-off workflow if the customer side is interactive.

**Worked example:** none yet.

---

## Unknown archetypes

The Flatpack-side catalogue lists 8 archetypes but `archetype` is
free-text in the manifest. If a promotion plan declares an archetype
not listed above:

1. **Don't reject the promotion.** Free-text is by design.
2. **Read the manifest's `promotionSignals`.** They tell you what
   triggers fired; that's a better guide than the archetype label.
3. **Compose from first principles.** Almost every promoted Flatpack
   wants `admin-users` + `audit-log` as the base. Add other recipes
   per the triggers.
4. **File a follow-up issue** on either repo proposing the new
   archetype, so the catalogues grow.

## Drift policy

The Flatpack side (`docs/archetypes.md`) and this side
(`docs/flatpack-archetype-to-recipe-map.md`) can drift. When they
do:

- This file is **canonical for the recipe mapping**.
- The Flatpack file is **canonical for the archetype shape**
  (what it does, likely entities, what not to assume).

Open a PR against either if the divergence is unjustified. Most
divergences mean Baseplate has gained a new recipe; mark the new
recipe as "Often apply" or "Always apply" in the relevant archetype
entries here.
