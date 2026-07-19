# Review: Phase 11a — CRUMB CRM & pipeline (`039c409..d996742`, `git diff master..HEAD`)
Date: 2026-07-16

Scope reviewed: `backend/app/modules/crumb/` (models, schemas, router, service package),
migration `0013`, auth seed + core wiring, and the `frontend/src/routes/crumb/` SPA.

The FSM enforcement, won-only spawn guard, numeric-safe quote numbering, Decimal handling,
audit-after-commit, RBAC gating, append-only interactions, migration cycle handling, and
frontend query invalidation all hold up under scrutiny. Three defects and one question below.

## Findings

### 1. [major] Free-text quote line with a price but no description (and no part) is accepted
- **Where:** `backend/app/modules/crumb/service/quotes.py:114-115` (`_resolve_line_amounts`)
- **Failure:** The pricing rules (D-V3-14) and the PLAN require a free-text line — one with
  no `plum_part_id` — to carry a `description`. But the explicit-price branch is checked
  first and returns immediately: `if line.unit_price is not None: return line.unit_price, line.markup_pct`.
  A line with no `plum_part_id`, no `description`, and a `unit_price` skips the free-text
  description guard entirely. `POST /api/v1/crumb/quotes` with
  `{"partner_id":"<customer>","lines":[{"quantity":"2","unit_price":"50"}]}` succeeds and
  persists a `crumb_quote_line` with `plum_part_id=NULL` and `description=NULL` — an
  unlabeled $100 line rendered on a customer-facing quote. Same gap on `add_line` /
  `update_line`, which share this helper.
- **Fix:** Before the explicit-price early return, enforce the identity rule for part-less
  lines: `if line.plum_part_id is None and not line.description: raise HTTPException(422, ...)`.
  I.e. a line must have either a `plum_part_id` or a non-empty `description`, regardless of
  whether a price was supplied.

### 2. [minor] `convert_to_opportunity` does not re-resolve the customer (`is_customer` bypass)
- **Where:** `backend/app/modules/crumb/service/leads.py:186-194`
- **Failure:** AC6 says every Opportunity/Quote/Interaction path must resolve a valid
  `is_customer` partner via `_resolve_customer`. The direct `create_opportunity` and
  `create_quote`/`spawn_quote` paths do. `convert_to_opportunity` only checks
  `lead.partner_id is None`, then builds the Opportunity straight from `lead.partner_id`
  without `_resolve_customer`. Scenario: link a lead to customer A (passes at link time),
  then A's `is_customer` flag is cleared in SYERP, then convert the lead → an opportunity
  is created against a non-customer partner, violating the CRM invariant the other paths
  enforce. (FK still guarantees the partner *row* exists, so this is a flag-consistency gap,
  not a dangling reference — hence minor.)
- **Fix:** Call `await _resolve_customer(db, lead.partner_id)` at the top of
  `convert_to_opportunity` before creating the Opportunity.

### 3. [minor] Bogus `opportunity_id` on direct quote create surfaces as 500, not 4xx
- **Where:** `backend/app/modules/crumb/service/quotes.py:196-210` (`create_quote` retry block)
- **Failure:** `create_quote` (via `POST /api/v1/crumb/quotes`) never validates the
  caller-supplied `opportunity_id`; it relies on the DB FK. The `try/except IntegrityError`
  around `flush()` is written to handle only a `quote_number` collision — it regenerates the
  number and re-flushes. If the IntegrityError is instead a bad `opportunity_id` FK, the
  retry re-flushes with the same bad FK, raises IntegrityError again, and it propagates
  uncaught → HTTP 500. `POST /crumb/quotes` with `{"partner_id":"<customer>","opportunity_id":"does-not-exist"}`
  returns 500 rather than a 404/422. (The `spawn_quote` path is unaffected — it passes a
  real opp id.)
- **Fix:** Either validate `opportunity_id` up front (404 if not found) like `_resolve_customer`
  does for the partner, or narrow the retry to only swallow a `quote_number` unique-violation
  and re-raise other IntegrityErrors as a 4xx.

## Questions

- **Spawn produces no distinct `quote.created` audit row.** `spawn_quote_endpoint`
  (`router.py:342-350`) writes only `opportunity.quote_spawned` targeting the opportunity;
  the newly created quote gets no audit row keyed on its own `target_id` (only its number
  appears in the detail text). Given the medical-device audit posture (SC6), is a separate
  `quote.created` row expected for spawned quotes, or is the spawn event the intended single
  record? Every other quote-creating path (`POST /crumb/quotes`) does emit `quote.created`,
  so the spawn path is the lone asymmetry.

## Resolution (fix loop) — 2026-07-16, commits a697c69 + efcf2e6

All findings addressed and re-verified (verify_crumb 22/22, verify_crumb_api 54/54,
13/13 regression exit 0, crumb Vitest 4/4, build clean):

- **#1 (major)** — FIXED. `_resolve_line_amounts` now enforces the part-or-description
  identity rule before the explicit-price early return; a part-less priced line with no
  description is rejected 422. Pinned by verify_crumb E2 (reject) + E3 (legit free-text accepted).
- **#2 (minor)** — FIXED. `convert_to_opportunity` calls `_resolve_customer(db, lead.partner_id)`
  before creating the opportunity, matching every other opportunity path (AC6).
- **#3 (minor)** — FIXED. `create_quote` validates an optional `opportunity_id` up front (404),
  so a bad link no longer reaches the DB and re-raises as 500. Pinned by verify_crumb_api (C).
- **Question (audit asymmetry)** — RESOLVED (owner: yes). `spawn_quote_endpoint` now writes a
  second `quote.created` audit row keyed on the new quote, alongside `opportunity.quote_spawned`.
  Pinned by verify_crumb_api (C2), which asserts both rows.
