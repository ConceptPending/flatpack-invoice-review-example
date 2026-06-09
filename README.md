# Invoice review — a Flatpack promoted into Baseplate

A **worked example** of the [Flatpack](https://github.com/ConceptPending/flatpack) → [Baseplate](https://github.com/ConceptPending/baseplate)
promotion bridge. This project is what a single-file
[`invoice-cleaner.html`](https://github.com/ConceptPending/flatpack/blob/main/examples/invoice-cleaner.html)
Flatpack becomes when "my tool" outgrows being personal and graduates
into a Baseplate-shaped backend.

It is intentionally **not** a finished product. The point of the
exercise is to demonstrate, end-to-end, that the bridge works.

## What's in this repo

```
backend/                  FastAPI app — fully working backend
  app/
    models/               Invoice, Supplier, ReviewBatch, ValidationError, AuditLog (stub)
    schemas/              Pydantic v2 schemas per entity
    services/             csv_parser, validation, batches, suppliers
    api/                  /api/admin/batches, /api/admin/suppliers
  alembic/versions/       Migration 003 promotes the schema
  tests/                  carries over 11 named tests from the Flatpack (+ lifecycle/expression suites; see CI for the count)
reference/                Preserved Flatpack artefacts
  original-flatpack.html    v0.2.0 invoice-cleaner Flatpack, frozen
  promotion-plan.md         The plan with three confidence tiers
  sample-data.csv           Extracted from the Flatpack's SAMPLE_CSV
  decisions.md              Answers given to INTERVIEW-REQUIRED items
```

Frontend is mostly the untouched Baseplate template (the `Item` pages are
template scaffolding) — this is primarily a **backend** worked example. The one
purpose-built screen is the read-only **lifecycle viewer + case simulator** at
`/admin/lifecycle`: it shows the policy in force (version + digest), what's
available to you on a given batch *and why* (`available-actions`), and the
append-only event history.

## What this repo demonstrates

1. **Promotion is not code conversion.** The Flatpack is a single HTML
   file; this is a full FastAPI + SQLAlchemy + Pydantic + Alembic
   project. There is no compilation step between them. What promotes
   is the *understanding* embedded in the Flatpack's manifest, plus
   the answers to the questions the manifest doesn't answer.

2. **The manifest does real work.** Half the entities, all the
   validation rules, all the exports listed in this Baseplate app
   come straight from the Flatpack's `<script type="application/json"
   id="flatpack-manifest">` block. They were extracted mechanically by
   `tools/promote.mjs` on the Flatpack side and translated by hand
   (with the agent's help) into Python.

3. **The verifier closes the loop.** `make verify-promotion` reads
   the manifest in `reference/original-flatpack.html` plus
   `reference/promoted-entities.json` and asserts each
   `MANIFEST-ASSERTED` claim still holds in the live FastAPI app.
   As of the most recent push it reports **33 OK, 1 miss, 1 warn**
   — the MISS is a documented legitimate divergence (see "What we
   learned" below); the WARN is for a custom validator the verifier
   correctly says it can't introspect.

4. **The Flatpack stays alive.** `reference/original-flatpack.html` is
   on disk and runnable — open it in a browser, click "Load sample
   data", and you have side-by-side parity with this Baseplate app.

## Lifecycle governance (the StateSpec kernel)

The `ReviewBatch` lifecycle is the complete reference for Baseplate's
[`lifecycle-state-machine`](https://github.com/ConceptPending/baseplate/blob/main/docs/recipes/lifecycle-state-machine.md)
recipe — the chain *policy → enforcement → tested behaviour → evidence →
visibility*:

```mermaid
flowchart LR
  spec["batch_spec.py<br/>(declarative policy:<br/>states, guards, invariants)"]
  engine["statespec engine<br/>fire(): guard + invariants"]
  svc["BatchService.transition<br/>(atomic + optimistic lock)"]
  ev["LifecycleEvent<br/>(append-only evidence)"]
  id["identity: version + digest"]
  view["/admin/lifecycle<br/>viewer + simulator"]
  gate["control plane<br/>(approval + prod gate)"]:::ext

  spec --> engine --> svc --> ev
  spec --> id
  ev --> view
  id --> view
  id -. policy.json digest .-> gate
  classDef ext stroke-dasharray:5 5,opacity:0.7;
```

This example can now answer, for any batch:

- **What rule is in force?** — `GET /api/admin/batches/lifecycle` (states,
  transitions, guards, invariants), plus its **version + digest**.
- **What actions are available to me, and why?** — `…/available-actions`
  (each action allowed/refused + the reason).
- **Who performed a transition, and under which exact policy?** —
  `…/lifecycle-events`: actor, roles **snapshotted at the time**, prior→new
  state, the spec version + digest, and each control's result + evaluated
  inputs.
- **Could stale data or a concurrent transition have invalidated it?** — the
  guard counts live unresolved-error rows (not a cache), and an optimistic-lock
  `version` makes two transitions on the same version impossible.

**See it:** `make dev`, then open `/admin/lifecycle`, pick a batch, and you get
the policy, the available-actions simulator, and the event history. (Backend
only: upload a CSV → `POST …/transition {"action":"approve"}` as a *different*
user than the uploader → `GET …/lifecycle-events`.)

**Where it stops:** this repo proves the policy *works, is enforced, and is
recorded*. It does **not** approve policies for production — the `.policy.json`
here is a *committed* baseline, not an *approved* one. The approval-authority /
production-gate layer is designed as a **separate control plane** (see
baseplate's [`docs/design/approval-authority.md`](https://github.com/ConceptPending/baseplate/blob/example/state-machine/docs/design/approval-authority.md));
keeping it out of the application is deliberate — the resulting app stays
ordinary, standalone software.

## The promotion journey

Following [`docs/promoting-a-flatpack.md`](https://github.com/ConceptPending/baseplate/blob/main/docs/promoting-a-flatpack.md)
in the Baseplate repo:

1. **Decided** — three of the Flatpack manifest's `promotionSignals`
   started firing (multiple reviewers; cross-batch dedup; audit
   trail). The narrative is at
   [`reference/promotion-plan.md`](reference/promotion-plan.md)
   "Why this is being promoted".
2. **Analysed** — the Flatpack's manifest, schema, validators, exports,
   and test cases were all extracted into the promotion plan. The
   plan labels every claim `MANIFEST-ASSERTED`, `CODE-INFERRED`, or
   `INTERVIEW-REQUIRED`.
3. **Planned** — the four entities, recipe set (`admin-users` +
   `audit-log` + adapted `public-submission-and-admin-queue`), and
   open questions live in
   [`reference/promotion-plan.md`](reference/promotion-plan.md).
4. **Scaffolded** — this repo. Initial commit was a clone of Baseplate
   `400540e`; the second commit dropped `reference/`; the third
   replaced the Item slice with the invoice-review domain.
5. **Preserved** — `reference/` is on disk and stays here.

## Recipe application status

| Recipe | Applied | Note |
|---|---|---|
| `admin-users` | Yes (as-is from base) | Base already supports multiple admins. No `/admin/users` UI built. |
| `audit-log` | **Stubbed** | Table created (matches recipe model). Hooks are TODO markers at each call site (`# TODO(audit-log-recipe)` in `app/api/batches.py`). Recipe walk is unfinished. |
| `public-submission-and-admin-queue` | **Adapted** | The "public" surface is the authenticated CSV upload page; the queue UI is the batch list. No anonymous endpoints. Frontend is out of scope for this scaffold. |
| [`lifecycle-state-machine`](https://github.com/ConceptPending/baseplate/blob/main/docs/recipes/lifecycle-state-machine.md) | **Applied** | `ReviewBatch.status` moves through a declarative state machine (`app/statespec/batch_spec.py`) instead of a free-form setter: legal transitions only, role-gated (`reviewer` can reject, only `approver` approves), a guard that refuses to approve a batch with unresolved validation errors, and **separation of duties** (the uploader can't approve their own batch — `actor_id ≠ uploaded_by_id`). Guards/invariants are declarative expressions, so the rendered doc shows the real policy. Every transition writes an append-only **`LifecycleEvent`** (who, prior/new state, roles-at-the-time, the exact policy version+digest, and the structured guard/invariant evidence) in the same transaction — `GET /api/admin/batches/{id}/lifecycle-events`. Policy identity is the committed baseline `docs/specs/batch.policy.json` (version + digest); `statespec.py diff batch` shows what a change did. Verified by Hypothesis (`tests/test_batch_statespec.py`) + audit tests; renders to [`docs/specs/batch-lifecycle.md`](docs/specs/batch-lifecycle.md). Adds `User.roles`. |

## What's deliberately out of scope

- **Frontend.** Templates from the Baseplate frontend point at the old
  `Item` endpoints; rewriting them is the next exercise. The backend
  is fully functional via OpenAPI/curl.
- **Full audit-log application.** The table exists; the hooks are TODOs.
- **Supplier alias auto-matching.** Strict-name-only matching for v1
  per [`reference/decisions.md`](reference/decisions.md) item 5.
- **Duplicate-override flow.** Admins can't yet override a cross-file
  dedup hit. Listed in `reference/decisions.md` item 4.

These are real gaps — see "What we learned" below for bridge issues
this exercise surfaced.

## How to run

Standard Baseplate setup, with one extra step at the end:

```bash
cp .env.example backend/.env
cp .env.example frontend/.env.local

make install
make hash-password           # paste output into backend/.env
make db
make migrate                 # applies migrations 001 + 002 + 003

make dev                     # backend on :8001
                             # frontend on :3001 (still serving the
                             # template Item UI — see "Out of scope")

make verify-promotion        # 33 OK, 1 miss, 1 warn — see "What the verifier still flags"
make test-backend            # tests pass (see CI for the current count)
```

`make verify-promotion` runs `backend/scripts/verify_promotion.py
../reference/original-flatpack.html` and asserts every
MANIFEST-ASSERTED claim in the Flatpack's inline manifest is honoured
by the live FastAPI app.

## What we learned

The point of building this was to discover what the bridge gets wrong
when actually used. The exercise produced eight issues across both
sides of the bridge — **all closed** as of the most recent push.
Brief history:

1. ~~**Baseplate isn't a GitHub-template repo.**~~ [baseplate#32](https://github.com/ConceptPending/baseplate/issues/32),
   fixed by toggling `is_template: true` on the Baseplate repo. The
   `gh repo create --template ConceptPending/baseplate` flow now
   works.

2. ~~**Verifier validation-rule keyword search is too lax.**~~ [baseplate#33](https://github.com/ConceptPending/baseplate/issues/33),
   fixed by [flatpack#1](https://github.com/ConceptPending/flatpack/issues/1) +
   the smarter verifier. Manifests now carry an optional
   `validation_predicates` array — a structured form of validations.
   The verifier resolves predicates against actual Pydantic and
   SQLAlchemy declarations. The keyword fallback still exists but
   reports WARN-not-OK and is scoped to `*Service` and
   `@field_validator` bodies (no longer matches in comments).

3. ~~**Verifier doesn't check fields-within-entities.**~~ [baseplate#34](https://github.com/ConceptPending/baseplate/issues/34),
   fixed: `check_entities` now walks every field with a loose
   type-compatibility map. This catches the `Invoice.supplier_name`
   divergence (see below) — exactly the kind of finding the v0
   verifier missed.

4. ~~**Verifier doesn't catch missing CODE-INFERRED entities.**~~ [baseplate#37](https://github.com/ConceptPending/baseplate/issues/37),
   fixed: new `reference/promoted-entities.json` convention. The
   promotion-time agent declares the introduced entities here; the
   verifier reads and checks them. This is what catches a forgotten
   `Supplier` table.

5. ~~**`summary_print` export was flagged as client-side.**~~ [baseplate#35](https://github.com/ConceptPending/baseplate/issues/35),
   fixed: `EXPORT_URL_HINTS` updated to look for `/summary` and
   `/print` routes. The verifier now correctly identifies the
   server-side endpoint that backs the printable view.

6. ~~**Strengthened-rule case is handled silently.**~~ [baseplate#36](https://github.com/ConceptPending/baseplate/issues/36),
   fixed alongside #33. With structured predicates, a weakened rule
   (e.g. `Field(gt=-1)` when the predicate said `gt=0`) fails the
   predicate check and reports as MISS or WARN.

7. ~~**`prompts/promote-flatpack.md` didn't reference `tools/promote.mjs`.**~~ [flatpack#2](https://github.com/ConceptPending/flatpack/issues/2),
   fixed: the prompt now opens step 2 with the skeleton-generator
   invocation.

8. ~~**Structured validations in the manifest.**~~ [flatpack#1](https://github.com/ConceptPending/flatpack/issues/1),
   fixed: optional `validation_predicates` array added to
   `manifest.schema.json` with the documented vocabulary. The three
   example Flatpacks (`invoice-cleaner`, `pricing-calculator`,
   `case-chronology-helper`) now carry predicates.

## What the verifier still flags — honestly

After all of the above:

- **1 MISS** on `entity Invoice.supplier_name`. This is **expected
  and desirable**. The Flatpack manifest declared `supplier_name`
  as a string field on Invoice; the Baseplate version factored it
  out into a `Supplier` FK. The MISS represents intentional,
  documented divergence — see [`reference/decisions.md`](reference/decisions.md)
  item C. A real CI gate would either acknowledge this in code or
  add an `expected-misses` convention (not yet a thing).

- **1 WARN** on `predicate invoice_date:not_in_future`. The
  `not_in_future` constraint isn't expressible in plain Pydantic,
  so the predicate-resolver honestly says it can't introspect the
  custom `@field_validator` that implements it. WARN, not MISS:
  evidence is present (the validator exists), but the verifier
  can't prove the predicate holds.

These are honest residuals, not bugs. The verifier is doing the
work — both the strong claims AND the limits are visible.

## Bridge improvements log

| Tier | Closed | Repos touched | Commits |
|---|---|---|---|
| 1 — quick wins | #2, #32, #35 | flatpack, baseplate | 4a280a2, 5470280 |
| 2 — structured predicates | #1 | flatpack | b4043c5 |
| 3 — smarter verifier | #33, #36 | baseplate | 01e77ab |
| 4 — field-level checks | #34 | baseplate | 718bd9f |
| 5 — promoted-entities.json | #37 | baseplate, flatpack | cfa4738, 605513a |
| 6 — re-verify | (this) | flatpack-invoice-review-example | (this commit) |

## Related

- [Flatpack](https://github.com/ConceptPending/flatpack) — the spec
  and templates this Flatpack came from.
- [Flatpack case study](https://github.com/ConceptPending/flatpack/tree/main/case-studies/invoice-cleaner-promotion)
  — the source of the promotion plan in `reference/`.
- [Baseplate](https://github.com/ConceptPending/baseplate) — the
  foundation this app sits on.
- [`docs/promoting-a-flatpack.md`](https://github.com/ConceptPending/baseplate/blob/main/docs/promoting-a-flatpack.md)
  — the receiving flow this project followed.
- [`docs/flatpack-archetype-to-recipe-map.md`](https://github.com/ConceptPending/baseplate/blob/main/docs/flatpack-archetype-to-recipe-map.md)
  — the archetype → recipe set mapping (this is the worked example
  for `import-validate-store`).

## License

MIT, inherited from Baseplate.
