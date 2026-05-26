# Promoting a Flatpack into a Baseplate project

The receiving side of [Flatpack](https://github.com/ConceptPending/flatpack)'s
promotion flow. This document explains how to take a promotion plan
produced by a Flatpack agent (per `prompts/promote-flatpack.md` on the
Flatpack side) and turn it into a Baseplate-shaped project.

This is **not a recipe.** It is the meta-document that tells you which
recipes to apply, in what order, and what to do with the artifacts the
Flatpack hands you. The recipes themselves live in `docs/recipes/`.

## What you receive

A Flatpack promotion produces three things:

1. **`original-flatpack.html`** — the working single-file tool that
   the user has been running locally. Preserve this; don't delete it.
2. **`promotion-plan.md`** — the agent's plan, with every claim
   labelled `MANIFEST-ASSERTED`, `CODE-INFERRED`, or
   `INTERVIEW-REQUIRED`. Read the confidence tier on each claim
   before treating it as a requirement.
3. **`baseplate-target/`** (optional) — a sketch of entities and the
   recipe set the Flatpack-side agent expected. Treat it as the
   *intended* shape, not the final one.

See [`case-studies/invoice-cleaner-promotion/`](https://github.com/ConceptPending/flatpack/tree/main/case-studies/invoice-cleaner-promotion)
in the Flatpack repo for a worked example.

## The receiving flow

### 1. Scaffold a Baseplate project

Start from Baseplate directly — **do not fork a previous promoted
project**. Each promotion stands on its own. The example `Item` slice
becomes your first domain model (rename it, or remove it before you
add yours).

```bash
gh repo create <org>/<project-name> --template ConceptPending/baseplate
git clone git@github.com:<org>/<project-name>
cd <project-name>
# Standard Baseplate setup
make install && make install-hooks
make hash-password   # paste output into backend/.env as ADMIN_PASSWORD_HASH
make db && make migrate && make dev
```

### 2. Drop the Flatpack artifacts into `reference/`

```bash
mkdir reference
cp /path/to/original-flatpack.html       reference/
cp /path/to/promotion-plan.md            reference/
cp -R /path/to/baseplate-target          reference/   # optional
```

The `reference/` directory is preserved on purpose. Two reasons:

- **Parity verification.** `backend/scripts/verify_promotion.py`
  reads `reference/original-flatpack.html`'s manifest and asserts
  the Baseplate app honours its claims. Without the original on
  disk, the verifier has nothing to check against.
- **Side-by-side iteration.** The Flatpack stays useful as a fast
  local prototype while you build the Baseplate version. The user
  can double-check behaviour: same input → same output.

Add to the project's README:

```markdown
This project was promoted from a Flatpack — see `reference/`.
Do not delete `reference/` until parity is verified via
`make verify-promotion`.
```

### 3. Pick the recipe set from the archetype

The promotion plan declares an archetype (free-text whole-app
descriptor, NOT a recipe name). Translate it via
[`docs/flatpack-archetype-to-recipe-map.md`](flatpack-archetype-to-recipe-map.md).

That document gives you, for each archetype, the **canonical** recipe
set Baseplate considers a good starting point. The Flatpack-side
catalogue at [`docs/archetypes.md`](https://github.com/ConceptPending/flatpack/blob/main/docs/archetypes.md)
gives hints; this Baseplate-side map is authoritative.

Apply each recipe in `docs/recipes/` in order. Recipe order matters
when one recipe extends data created by another (e.g. the `audit-log`
recipe hooks into endpoints that other recipes create).

### 4. Walk the confidence tiers

Process the plan section-by-section. The discipline differs per tier:

**MANIFEST-ASSERTED.** These are non-negotiable. Every entity field,
every validation rule, every export listed must appear in the
Baseplate app verbatim — same field names, same constraints, same
output formats. The verifier will fail otherwise. If you want to
*strengthen* a constraint (e.g. per-file uniqueness → cross-file
uniqueness), do so additively. Never relax.

**CODE-INFERRED.** Open `reference/original-flatpack.html` and read
the JS. The `FLATPACK:VALIDATION`, `FLATPACK:CORE_LOGIC`, and
`FLATPACK:IMPORT_EXPORT` regions are the source of truth here. The
plan's inferred claims are usually right but worth a second pass.

**INTERVIEW-REQUIRED.** Stop. These are questions for the user.
Don't invent defaults. Answer them with the user before scaffolding
the relevant code. The promotion plan template
([`prompts/promote-flatpack.md`](https://github.com/ConceptPending/flatpack/blob/main/prompts/promote-flatpack.md)
on the Flatpack side) lists the questions you'll typically need
answered: roles, batch vs. per-record approval, override flows,
downstream integrations, multi-tenancy expectations.

### 5. Carry the test cases

The Flatpack's `FLATPACK:TEST_CASES` array becomes the seed of your
backend test suite. Each test name becomes a function in
`backend/tests/test_<entity>.py`. The assertion changes (pure logic
in the Flatpack → database-backed in Baseplate) but the *behaviour
being tested* is the same.

This is the cheapest fidelity check: if a Flatpack test passes and
the corresponding Baseplate test fails, parity is broken.

### 6. Verify

Once entities, validations, exports, and the recipe set are in place:

```bash
make verify-promotion
```

(Wires `backend/scripts/verify_promotion.py reference/original-flatpack.html`.
See that script for the contract — it walks the manifest and checks
each MANIFEST-ASSERTED claim against the live SQLAlchemy models and
FastAPI routes.)

The verifier deliberately does NOT check INTERVIEW-REQUIRED items.
Those don't map to manifest claims, by definition. If you want a
record of how each one was answered, add it to the project's
`reference/decisions.md`.

## What this is not

- **Not a code transformation.** A Flatpack is one HTML file; a
  Baseplate project is a full stack. You don't convert one into the
  other. The *understanding* promotes — schema, validation, core
  logic, sample data, edge cases, test cases.
- **Not optional.** If a Flatpack hits a promotion trigger (more
  than one user needs it, source of truth, audit history, etc.)
  trying to keep going with the single-file tool will break under
  load. The promotion path exists to catch the moment.
- **Not retroactive.** If you find yourself thinking "my Baseplate
  app would be cleaner as a Flatpack", you've found a tool the
  business doesn't actually need to share. That can be a real
  conclusion. But you don't *demote* — you start a fresh Flatpack
  from the spec.

## Related

- Flatpack `SPEC.md` §8 — when a Flatpack should be promoted.
- Flatpack `prompts/promote-flatpack.md` — the agent flow that
  produces the plan you're reading.
- Flatpack `docs/archetypes.md` — Flatpack's archetype catalogue
  (hints, not canonical).
- Baseplate `docs/flatpack-archetype-to-recipe-map.md` — the
  canonical archetype → recipe set map (this repo).
- Baseplate `docs/recipes/` — the recipes you'll apply.
- Baseplate `backend/scripts/verify_promotion.py` — the verifier.
