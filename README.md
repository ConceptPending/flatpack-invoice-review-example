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
  tests/                  33 tests; carries over 11 named tests from the Flatpack
reference/                Preserved Flatpack artefacts
  original-flatpack.html    v0.2.0 invoice-cleaner Flatpack, frozen
  promotion-plan.md         The plan with three confidence tiers
  sample-data.csv           Extracted from the Flatpack's SAMPLE_CSV
  decisions.md              Answers given to INTERVIEW-REQUIRED items
```

Frontend deliberately untouched from the Baseplate template — this is
a **backend-only** worked example. The Flatpack's HTML remains the
user-facing artifact for now.

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
   the manifest in `reference/original-flatpack.html` and asserts each
   `MANIFEST-ASSERTED` claim still holds in the live FastAPI app. As
   of the most recent push it reports **10 OK, 0 miss, 0 warn**.

4. **The Flatpack stays alive.** `reference/original-flatpack.html` is
   on disk and runnable — open it in a browser, click "Load sample
   data", and you have side-by-side parity with this Baseplate app.

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

make verify-promotion        # 10 OK, 0 miss, 0 warn — the bridge proof
make test-backend            # 33 tests pass
```

`make verify-promotion` runs `backend/scripts/verify_promotion.py
../reference/original-flatpack.html` and asserts every
MANIFEST-ASSERTED claim in the Flatpack's inline manifest is honoured
by the live FastAPI app.

## What we learned

The point of building this was to discover what the bridge gets wrong
when actually used. Real findings, filed as issues against the
relevant repos:

1. **Baseplate isn't a GitHub-template repo.** `gh repo create
   --template ConceptPending/baseplate` fails because Baseplate's
   template flag is off. The receiving docs say "use --template" but
   you have to clone + reinit instead. **Issue: Baseplate.**

2. **Verifier validation-rule keyword search is too lax.** The check
   matches keywords from the manifest's rule text against
   `app/*.py`. It matched our `"warning"` keyword because the comment
   in `services/validation.py` *mentions* the original Flatpack
   warning behaviour while *implementing* it as a strengthened error.
   False-positive: the rule was technically not violated, but the
   check would have happily accepted code that had no validation at
   all if the keywords appeared anywhere. **Issue: Baseplate.**

3. **Verifier doesn't check fields-within-entities.** It confirms
   `Invoice` exists; doesn't confirm `invoice_date` is a `Date`
   column. Already flagged with `TODO(verifier-v2)` in
   `verify_promotion.py`.

4. **Verifier doesn't catch missing CODE-INFERRED entities.** The
   Flatpack manifest only declares `Invoice`. The promotion plan
   *introduces* `Supplier`, `ReviewBatch`, `ValidationError`. If we
   had forgotten to add `Supplier` here, the verifier wouldn't catch
   it — only manifest-declared entities are checked. **Issue: open
   question for Baseplate.**

5. **`summary_print` export is flagged as client-side** by the
   verifier's hint-map, but this project *does* expose a server
   `/summary` endpoint that the printable view would call. The
   verifier doesn't flag this contradiction. Minor; documented in
   `verify_promotion.py`'s `EXPORT_URL_HINTS`. **Issue: Baseplate.**

6. **Strengthened-rule case is handled silently.** The Flatpack said
   "warning, defaults to GBP"; we strengthened to "error". The
   verifier doesn't compare the *semantics* of validation rules — it
   only checks the rule's keywords appear somewhere. A Baseplate that
   *weakened* a rule would pass too. **Issue: Baseplate.**

The Flatpack-side issues file separately under
github.com/ConceptPending/flatpack/issues; Baseplate-side ones under
github.com/ConceptPending/baseplate/issues.

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
