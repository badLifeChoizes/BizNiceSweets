# Plan: Phase 11a — CRUMB CRM & pipeline
Goal: Ship a new `crumb` module — leads → opportunities (pipeline stages) → quotes + a customer communication log — against SYERP customers, with PLUM-derived editable line pricing, server-enforced FSMs, audit, and RBAC. (Sales orders + soft-reservation are Phase 11b.)
Status: draft

Branch: `feature-crumb-crm-pipeline` off `master` (D-V3-13) — do not create it yet.
Checklist file to keep: `docs/tasks/feature-crumb-crm-pipeline.md`.

## Success criteria
Delivers the inventory-free portion of **CRUMB-01** (`.zj/SRD.md:535`). Each SC below maps to CRUMB-01 ACs; SO conversion (AC3 tail), AC4 (sales orders), and the AC6 SO-fulfillment clause are explicitly deferred to 11b (D-V3-10).
- **SC1 — Module wiring:** `backend/app/modules/crumb/` self-registers (mirror `mousse`); `crumb:read`/`crumb:write` seeded; crumb models aggregated in `core/models.py`; migration `0013` (head is `0012`) adds the crumb tables; the `crumb` row already exists in `modules_seed.py` (order 50, disabled by default) — do not duplicate.
- **SC2 — Leads (CRUMB-01 AC1):** create/view/edit/archive a lead; qualified lead links-to-or-creates a SYERP customer (`Partner.is_customer`) and converts to an opportunity; server-enforced + audited.
- **SC3 — Opportunity pipeline (AC2):** opportunities carry customer, estimated value, expected close date, stage (Qualify → Proposal → Won/Lost); server-enforced stage transitions (invalid → 4xx, audited); per-stage list; a Won opportunity spawns a quote.
- **SC4 — Quotes (AC3, minus SO conversion):** header (customer) + lines (PLUM part or free-text, qty, unit price); line unit price defaults from the part's PLUM released cost + editable markup (D-V3-6) and is user-editable; line + total value shown; FSM Draft → Sent → Accepted/Rejected/Expired enforced server-side; auto-number `QUOTE-####` (numeric-safe, D-P8-6).
- **SC5 — Communication log (AC5):** append-only interactions (type call/email/note/meeting, UTC timestamp, acting user, body) referencing a customer and optionally a lead/opportunity/quote; per-customer timeline read. Logging only — no email integration.
- **SC6 — Audit + RBAC (AC7, CORE-05):** every mutation (incl. stage/FSM transitions and both conversions) writes an attributable audit event at the router layer; all endpoints gated `crumb:read`/`crumb:write`, refused server-side (401/403). Proven at HTTP level (9a lesson).
- **SC7 — Frontend + regression:** CRUMB nav (gated on CRUMB enabled ∩ `crumb:read`); leads list/sheet/archive; opportunity pipeline (per-stage grouped) + detail w/ stage transitions; quote builder (line editor w/ PLUM-price default + markup) + FSM actions; comm-log timeline; colocated Vitest green; `npm run build` clean; 13/13 `verify_*.py` still exit 0.

## Context
Read before building:
- **New-module pattern (D-P10-6, MAP.md:36):** `backend/app/modules/mousse/{__init__,models,schemas,router,service}.py` is the newest exemplar. `__init__.py` calls `registry.register(sys.modules[__name__])` and imports `router` (`mousse/__init__.py:15-20`). `main.py:79-82` self-registers each module via `importlib.import_module`; add the crumb line there.
- **Service cohesion (D-V3-9, MAP.md:36/Concerns 4):** SYERP was refactored from a 3,824-line monolith into a `syerp/service/` **package** (leaves → `inventory` → `journal` → `purchasing` → `bills`; `service/__init__.py` re-exports the public surface). CRUMB is a fresh module — **architect's call: build `crumb/service/` as a package from day one** (`_common.py`, `leads.py`, `opportunities.py`, `quotes.py`, `interactions.py`, `__init__.py` re-export). Do NOT let one `service.py` metastasize.
- **FSM pattern:** `syerp/service/purchasing.py:483-534` — `PO_TRANSITIONS: dict[str, set[str]]` + `advance_*` that raises 422 on a disallowed target. MOUSSE mirrors it at `mousse/service.py:329` (`_WO_TRANSITIONS`). Two FSMs are needed: opportunity **stage** and quote **status**.
- **Numeric-safe auto-numbering (D-P8-6):** `syerp/service/items.py:59-113` (`_next_item_code` pure helper + `generate_item_code` regex-filter `~ '^ITEM-[0-9]+$'` then `cast(func.substring(...), Integer).desc()`), reused verbatim shape in `mousse/service.py:64-109` (`generate_wo_number`). Copy this shape for `QUOTE-####`.
- **PLUM released cost (D-V3-6, D-V3-9):** `plum/service.py:656` `get_released_revision(db, part_id) -> PlumPartRevision | None`; the released revision carries `released_cost_snapshot` (`plum/models.py:216`). Import it — do NOT re-derive costing. A quote line's default `unit_price = released_cost_snapshot × (1 + markup_pct/100)`; when the part has no released revision or a null snapshot, default to `0` and let the user enter the price.
- **SYERP customer (hub FK, AC6):** `Partner` (`syerp/models.py:49`) has a **String(36) UUID PK** (`syerp/models.py:65` — `Mapped[str]`, verified) with an `is_customer` flag (`:74`); `create_partner(db, data)` (`partners/... :117`), `list_partners(role="customer")`. Import these — do not duplicate. Leads/opportunities/quotes/interactions FK `syerp_partner.id` as **String(36)**.
- **Audit (D-10, SC6):** `write_audit(db, actor_id, action, target_type, target_id, detail)` (`auth/service.py:313`) — self-commits; called at the **router** layer AFTER the service commit (see every mutation in `mousse/router.py`), so HTTP verify can see the rows.
- **Permissions (SC6):** `auth/seed.py:32-51` — `_PERMISSIONS` list + `_USER_ROLE_PERMS` set; add `crumb:read`/`crumb:write` to both (mirrors `mousse:*`). `require_permission("crumb:read"|"crumb:write")` gates routes (reads roles from DB, not JWT claim — see verify_mousse_api.py preamble).
- **Money/qty (D-11):** `Numeric(18,6)` / Python `Decimal`, never float — mirror `mousse/models.py`.
- **Migration:** head is `0012` (`0012_*.py`: `revision="0012"`, `down_revision="0011"`); chain `0013` off `0012`. Runs on container boot via `entrypoint.sh`.
- **Frontend:** per-suite folder `frontend/src/routes/crumb/` w/ local `components/`; `CrumbNav.tsx` mirrors `routes/mousse/components/MousseNav.tsx` / `SyerpNav.tsx`; routes registered in `App.tsx:79-81` block; nav gating is automatic via `AppShell.tsx:39-43` (enabled ∩ `crumb:read`) once the module row is enabled and permission held — no AppShell code change needed beyond confirming the pattern. TanStack Query hooks in `crumb/hooks.ts` (mirror `mousse/hooks.ts`); single axios client `src/api/client.ts`. Colocated `*.test.tsx`.
- **Verify container:** `podman exec -e PYTHONPATH=/app compose_api_1 python scripts/verify_crumb.py` (container name per `verify_mousse.py:40`).

## Decisions (resolved at plan)
1. **Default markup source (D-V3-14, owner).** RESOLVED — the quote line price default = released cost + markup uses a module-level constant `DEFAULT_MARKUP_PCT = Decimal("30")` in `crumb/service/_common.py`, applied as the initial per-line default and **editable per line**. **No settings entity and no price-list** in 11a (D-V3-6 explicitly excludes PLUM-16 territory). Implemented in Tasks 5 and 8.
2. **"Won opportunity spawns a quote" gating (D-V3-15, owner).** RESOLVED — `spawn_quote` **requires the opportunity to be in stage `won`** (else HTTP 422), mirroring "a Won opportunity can spawn a quote" literally. Implemented in Task 7; surfaced in the UI in Task 16.

## Tasks

### [x] 1. Define CRUMB ORM models + aggregate into core/models.py
- **Files:** `backend/app/modules/crumb/models.py` (new), `backend/app/core/models.py` (uncomment line 30)
- **Do:** Create five `crumb_`-prefixed models inheriting `app.core.base.Base`, mirroring `mousse/models.py` style (Decimal `Numeric(18,6)`, tz-aware `DateTime`, `actor_id: String(36)`, UUID `String(36)` PKs on documents/lines). **All hub FKs are `String(36)`** — `syerp_partner.id` and `plum_part.id` are both String(36) UUID PKs (verified `syerp/models.py:65`, `plum/models.py:92`), matching the MOUSSE precedent:
  - `Lead` (`crumb_lead`): `id`, `name`, `company`, `contact` (nullable), `source` (nullable), `status` String(30) default `"new"` (new | qualified | converted), `active` Boolean default True (archive flag), `partner_id` String(36) FK→`syerp_partner.id` nullable (the linked customer), `opportunity_id` String(36) FK→`crumb_opportunity.id` nullable (set on conversion), `actor_id`, `created_at`.
  - `Opportunity` (`crumb_opportunity`): `id`, `name`, `partner_id` String(36) FK→`syerp_partner.id` NOT NULL (customer, AC6), `estimated_value` Numeric(18,6) nullable, `expected_close_date` Date nullable, `stage` String(30) default `"qualify"` (qualify | proposal | won | lost), `lead_id` String(36) FK→`crumb_lead.id` nullable, `actor_id`, `created_at`.
  - `Quote` (`crumb_quote`): `id`, `quote_number` String(30) unique index NOT NULL, `partner_id` String(36) FK→`syerp_partner.id` NOT NULL, `opportunity_id` String(36) FK→`crumb_opportunity.id` nullable, `status` String(30) default `"draft"` (draft | sent | accepted | rejected | expired), `actor_id`, `created_at`.
  - `QuoteLine` (`crumb_quote_line`): `id`, `quote_id` String(36) FK→`crumb_quote.id` NOT NULL index, `plum_part_id` String(36) FK→`plum_part.id` nullable, `description` String (free-text; required when no part — enforced in service), `quantity` Numeric(18,6), `unit_price` Numeric(18,6), `markup_pct` Numeric(18,6) nullable (informational — the markup applied at default time), `sort_order` Integer.
  - `Interaction` (`crumb_interaction`): `id`, `partner_id` String(36) FK→`syerp_partner.id` NOT NULL index (AC5), `lead_id`/`opportunity_id`/`quote_id` String(36) nullable FKs, `interaction_type` String(20) (call | email | note | meeting), `occurred_at` DateTime(timezone=True) default UTC-now, `body` String, `actor_id` String(36), `created_at`. **Append-only** (no update/delete path).
  - Uncomment `from app.modules.crumb import models as crumb_models  # noqa: F401` at `core/models.py:30`.
- **Done when:** `python -c "import app.core.models"` inside the api container imports without error and `Base.metadata.tables` contains the five `crumb_*` tables. Serves SC1/SC2/SC3/SC4/SC5.
- **Verify:** `podman exec -e PYTHONPATH=/app compose_api_1 python -c "from app.core import models; print([t for t in models.plum_models.Base.metadata.tables if t.startswith('crumb_')])"` → lists 5 tables.
- **Parallel-ok:** no (foundation)

### [x] 2. Generate Alembic migration 0013 for the crumb tables
- **Files:** `backend/alembic/versions/0013_*.py` (new, autogenerated then reviewed)
- **Do:** With Task 1 merged, run autogenerate against a live DB at head 0012; confirm `revision="0013"`, `down_revision="0012"`. Review the generated `create_table` ops for all five tables, correct FK types (**String(36) `partner_id` → `syerp_partner.id`** — the Partner PK is String(36) UUID, verified; String(36) → plum/crumb), unique index on `crumb_quote.quote_number`, and the `crumb_quote_line.quote_id` / `crumb_interaction.partner_id` indexes. Remove any spurious diffs (autogenerate must produce ONLY crumb tables — D-11 all-Decimal so no float leaks).
- **Do (cmd):** `podman exec -e PYTHONPATH=/app compose_api_1 alembic revision --autogenerate -m "crumb crm pipeline (0013)"` then hand-review.
- **Done when:** `alembic upgrade head` creates the five tables and `alembic downgrade -1` drops them cleanly; head reports `0013`.
- **Verify:** `podman exec -e PYTHONPATH=/app compose_api_1 alembic upgrade head && podman exec -e PYTHONPATH=/app compose_api_1 alembic current` → shows `0013 (head)`.
- **Parallel-ok:** no (depends on Task 1)

### [x] 3. Seed crumb:read / crumb:write permissions
- **Files:** `backend/app/modules/auth/seed.py`
- **Do:** Add `("crumb:read", "Read access to CRUMB (CRM & sales pipeline)")` and `("crumb:write", "Write access to CRUMB")` to `_PERMISSIONS` (`:32`); add `"crumb:read"`, `"crumb:write"` to `_USER_ROLE_PERMS` (`:44`). Idempotent seed already upserts by code and set-difference-assigns to roles. Cite CORE-05 / SC6.
- **Done when:** after a seed run, the `permissions` table contains `crumb:read`/`crumb:write` and both are assigned to the `admin` and `user` roles.
- **Verify:** restart api (seed runs at lifespan) then `verify_crumb_api.py` (Task 12) asserts the codes gate the endpoints; interim spot-check: `podman exec -e PYTHONPATH=/app compose_api_1 python -c "from app.modules.auth.seed import _PERMISSIONS, _USER_ROLE_PERMS; print('crumb:read' in dict(_PERMISSIONS), 'crumb:write' in _USER_ROLE_PERMS)"`.
- **Parallel-ok:** yes (independent of 1/2)

### [x] 4. Define CRUMB Pydantic schemas
- **Files:** `backend/app/modules/crumb/schemas.py` (new)
- **Do:** Pure Pydantic (never import ORM), mirroring `mousse/schemas.py` (`from_attributes=True` on Reads, `Field(gt=0)` guards, Decimal fields). Define:
  - Leads: `LeadCreate`, `LeadUpdate` (all-optional PATCH), `LeadRead`, `LeadConvertRequest` (optional `partner_id` to link existing customer, or `new_customer_name`/flags to create one), `LeadToOpportunityRequest` (opportunity name, estimated_value, expected_close_date).
  - Opportunities: `OpportunityCreate`, `OpportunityUpdate`, `OpportunityRead`, `OpportunityStageRequest` (`target_stage: str`), `OpportunityToQuoteRequest` (optional initial lines).
  - Quotes: `QuoteLineCreate` (`plum_part_id?`, `description?`, `quantity: Field(gt=0)`, `unit_price?` — when omitted, service defaults from PLUM), `QuoteLineRead` (+ derived `line_total`), `QuoteCreate` (`partner_id`, `opportunity_id?`, `lines`), `QuoteRead` / `QuoteDetailRead` (header + lines + derived `total_value`), `QuoteStatusRequest` (`target_status: str`).
  - Interactions: `InteractionCreate` (`partner_id`, `interaction_type`, `body`, optional `lead_id`/`opportunity_id`/`quote_id`, optional `occurred_at`), `InteractionRead`.
- **Done when:** `python -c "import app.modules.crumb.schemas"` imports clean; positive-qty and enum-ish constraints present.
- **Verify:** `podman exec -e PYTHONPATH=/app compose_api_1 python -c "import app.modules.crumb.schemas as s; print(s.QuoteCreate.model_fields.keys())"`
- **Parallel-ok:** yes (depends only on nothing runtime; can proceed alongside 2/3)

### [x] 5. Scaffold crumb/service package + shared helpers (_common.py)
- **Files:** `backend/app/modules/crumb/service/__init__.py` (new), `backend/app/modules/crumb/service/_common.py` (new)
- **Do:** Create the `service/` package (delete/avoid a single `service.py`). In `_common.py`: the two FSM tables `STAGE_TRANSITIONS: dict[str, set[str]]` (`qualify → {proposal, won, lost}`, `proposal → {won, lost}`, `won → set()`, `lost → set()`) and `QUOTE_TRANSITIONS` (`draft → {sent}`, `sent → {accepted, rejected, expired}`, terminals empty); the constant `DEFAULT_MARKUP_PCT = Decimal("30")` (D-V3-14 — 30% initial per-line default, editable per line); a `_resolve_customer(db, partner_id)` helper that 404s if the partner is missing or not `is_customer`; lazy imports inside functions (mirror `syerp/service/*`). `__init__.py` re-exports the public surface from the four entity modules (populated as Tasks 6–9 land). Cite D-V3-9 / D-P10-6.
- **Done when:** `from app.modules.crumb.service import STAGE_TRANSITIONS, QUOTE_TRANSITIONS` succeeds; `STAGE_TRANSITIONS["won"] == set()`; `DEFAULT_MARKUP_PCT == Decimal("30")`.
- **Verify:** `podman exec -e PYTHONPATH=/app compose_api_1 python -c "from app.modules.crumb.service import _common as c; print(c.STAGE_TRANSITIONS, c.QUOTE_TRANSITIONS, c.DEFAULT_MARKUP_PCT)"`
- **Parallel-ok:** no (Tasks 6–9 import it)

### [x] 6. Leads service — CRUD, archive, customer link/create, convert-to-opportunity
- **Files:** `backend/app/modules/crumb/service/leads.py` (new)
- **Do:** `create_lead`, `list_leads(include_archived=False)`, `get_lead` (404), `update_lead` (PATCH), `archive_lead` (sets `active=False`), `link_or_create_customer(db, lead_id, data, actor_id)` — links an existing `Partner.is_customer` **or** calls SYERP `create_partner` with `is_customer=True` (import from `syerp.service`, D-V3-9), stamps `lead.partner_id`, sets `status="qualified"`; `convert_to_opportunity(db, lead_id, data, actor_id)` — requires a linked customer (422 if none), creates an `Opportunity` (stage `qualify`, `lead_id` set), stamps `lead.opportunity_id` + `status="converted"`, returns the opportunity. All Decimal; commit per operation. Serves SC2 / AC1.
- **Done when:** service functions exist and enforce: convert-without-customer → 422; convert stamps both sides; archive hides from default list.
- **Verify:** exercised by `verify_crumb.py` (Task 11); interim `python -c "from app.modules.crumb.service import leads"` imports clean.
- **Parallel-ok:** yes (with 7/8/9, after 5)

### [x] 7. Opportunities service — CRUD, stage FSM, per-stage list, spawn quote
- **Files:** `backend/app/modules/crumb/service/opportunities.py` (new)
- **Do:** `create_opportunity`, `list_opportunities` (returns rows; `list_pipeline` groups by stage for the per-stage view — SC3), `get_opportunity` (404), `update_opportunity` (PATCH; NOT stage — stage moves only via the FSM), `advance_stage(db, opp_id, target_stage, actor_id)` mirroring `advance_po_status` (`purchasing.py:492`): validates `target ∈ STAGE_TRANSITIONS[current]` else **HTTP 422** (SC3/AC2), sets stage, commits, returns row; `spawn_quote(db, opp_id, data, actor_id)` — **requires the opportunity to be in stage `won` else HTTP 422** (D-V3-15), then delegates to the quotes service to create a Draft quote carrying `opportunity_id` and the opportunity's customer, returns it. Cite D-P8/9 FSM pattern.
- **Done when:** valid stage walk succeeds; an invalid transition (e.g. `qualify → won` if disallowed, or any move off a terminal `won`/`lost`) raises 422; `spawn_quote` on a non-`won` opportunity raises 422; `list_pipeline` returns stage-keyed groups.
- **Verify:** `verify_crumb.py` (Task 11) covers the valid walk + invalid-transition reject + won-only spawn guard.
- **Parallel-ok:** yes (after 5; note spawn_quote depends on Task 8's create — land 8 first or stub the import)

### [x] 8. Quotes service — header+lines, PLUM-derived price default, QUOTE-#### generator, FSM
- **Files:** `backend/app/modules/crumb/service/quotes.py` (new)
- **Do:**
  - Number generator: `_next_quote_number` (pure) + `generate_quote_number(db)` copying `items.py:59-113` / `mousse` shape — regex `~ '^QUOTE-[0-9]+$'`, `cast(func.substring(quote_number, 7), Integer).desc()` (skip the 6-char `QUOTE-` prefix), `f"QUOTE-{n:04d}"`, `"QUOTE-0001"` seed. **Never lexicographic MAX** (D-P8-6). Retry-once on IntegrityError (mirror `create_item`).
  - `create_quote(db, data, actor_id)`: resolves customer (`_resolve_customer`), generates the number, creates header (status `draft`) + lines. **Per line**: if `unit_price` omitted and `plum_part_id` set → look up `get_released_revision(db, part_id)` (import from `plum.service`, D-V3-9); `unit_price = (released_cost_snapshot or 0) × (1 + markup_pct/100)` with `markup_pct` defaulting to `DEFAULT_MARKUP_PCT` (30%, D-V3-14); store the resolved `unit_price` **and** the `markup_pct` used (D-V3-6). A user-supplied `unit_price` overrides and persists verbatim (editable). Free-text line (no part) requires `description` (else 422) and an explicit `unit_price`.
  - `get_quote_detail` (header + lines + derived `total_value = Σ qty×unit_price`, Decimal), `list_quotes`, `add_line`/`update_line`/`delete_line` (Draft only — reject line edits once Sent, 409), `advance_quote_status(db, quote_id, target, actor_id)` validating `QUOTE_TRANSITIONS` else 422.
  - All Decimal, `ROUND_HALF_UP` if quantizing.
- **Done when:** a quote line for a PLUM part with a released `released_cost_snapshot` defaults to `cost×1.30`; a supplied override persists; `QUOTE-####` increments numerically across a digit-width boundary; Draft→Sent→Accepted walk succeeds and Sent→Draft is 422.
- **Verify:** `verify_crumb.py` (Task 11) asserts price default + override + numeric-safe boundary + FSM.
- **Parallel-ok:** no (Task 7's spawn_quote imports `create_quote`)

### [x] 9. Interactions service — append + per-customer timeline
- **Files:** `backend/app/modules/crumb/service/interactions.py` (new)
- **Do:** `create_interaction(db, data, actor_id)` — resolves customer (`_resolve_customer`), validates `interaction_type ∈ {call,email,note,meeting}` (422), defaults `occurred_at` to UTC-now, appends a row (**append-only** — no update/delete). `list_customer_timeline(db, partner_id)` — all interactions for a customer, newest `occurred_at` first (SC5/AC5). No email integration (D-V3-5).
- **Done when:** append persists with acting user + UTC timestamp; timeline returns rows newest-first for the given customer.
- **Verify:** `verify_crumb.py` (Task 11) covers append + timeline ordering.
- **Parallel-ok:** yes (after 5, independent of 6/7/8)

### [x] 10. Router + self-registration (audit at router layer)
- **Files:** `backend/app/modules/crumb/router.py` (new), `backend/app/modules/crumb/__init__.py` (new), `backend/app/main.py` (add import line), `backend/app/modules/crumb/service/__init__.py` (finalize re-exports)
- **Do:** Thin router (mirror `mousse/router.py`), no prefix, each route spells `/crumb/...`. Endpoints (reads gated `crumb:read`, mutations `crumb:write` via `require_permission`):
  - Leads: `GET /crumb/leads`, `POST /crumb/leads`, `GET /crumb/leads/{id}`, `PATCH /crumb/leads/{id}`, `POST /crumb/leads/{id}/archive`, `POST /crumb/leads/{id}/link-customer`, `POST /crumb/leads/{id}/convert`.
  - Opportunities: `GET /crumb/opportunities` (+ `?pipeline=true` grouping), `POST`, `GET /{id}`, `PATCH /{id}`, `POST /{id}/stage`, `POST /{id}/quote` (spawn).
  - Quotes: `GET /crumb/quotes`, `POST`, `GET /{id}`, `POST /{id}/lines`, `PATCH /{id}/lines/{line_id}`, `DELETE /{id}/lines/{line_id}`, `POST /{id}/status`.
  - Interactions: `POST /crumb/interactions`, `GET /crumb/interactions?partner_id=` (timeline).
  - After each service commit, call `write_audit(...)` with a `crumb.*` action (`lead.created`/`lead.archived`/`lead.linked_customer`/`lead.converted`/`opportunity.created`/`opportunity.stage_changed`/`opportunity.quote_spawned`/`quote.created`/`quote.status_changed`/`interaction.logged`, etc.), `target_type`, `target_id`, `detail` (SC6/AC7).
  - `crumb/__init__.py`: `MODULE_NAME = "crumb"`, `from app.modules.crumb.router import router`, `registry.register(sys.modules[__name__])` (copy `mousse/__init__.py`). Add `importlib.import_module("app.modules.crumb")` at `main.py:82` (after mousse, before auth or alongside — match ordering).
- **Done when:** api boots with crumb registered; `GET /api/v1/crumb/leads` returns 401 unauthenticated, 200 with a `crumb:read` token; every mutation writes an audit row.
- **Verify:** `podman exec -e PYTHONPATH=/app compose_api_1 python -c "from app.core import registry; import app.modules.crumb; print('crumb' in [m.MODULE_NAME for m in registry._registry])"` and `curl` / verify_crumb_api.py (Task 12).
- **Parallel-ok:** no (needs 6–9)

### [x] 11. verify_crumb.py — service-level live-Postgres verification
- **Files:** `backend/scripts/verify_crumb.py` (new)
- **Do:** Mirror `verify_mousse.py` (owns its own async engine/session, builds fixtures, self-cleans in `finally`). Assert: (A) lead → link existing customer AND lead → create new customer; (B) lead → opportunity conversion stamps both sides + rejects convert-without-customer 422; (C) opportunity stage FSM — a valid walk (`qualify→proposal→won`) succeeds and an invalid transition (off `won`, and a disallowed skip) raises, plus `spawn_quote` on a non-`won` opportunity is rejected (D-V3-15); (D) quote FSM valid walk + invalid reject; (E) **PLUM-derived price default** — a quote line for a PLUM part with a released `released_cost_snapshot` defaults to `cost×1.30`, and an explicit override persists; also a part with NO released cost defaults to `0` (price entered manually); (F) **numeric-safe `QUOTE-####`** — boundary (`QUOTE-0009`→`QUOTE-0010`) + survival of a non-`QUOTE-[0-9]+` row (the D-P8-6/Phase-7 lesson); (G) quote line integrity (Σ line totals = header total_value, Decimal-exact); (H) interaction append + per-customer timeline ordering. Print PASS/FAIL, exit non-zero on any FAIL.
- **Done when:** script exits 0 against the running DB and self-cleans (no residual crumb rows / fixtures).
- **Verify:** `podman exec -e PYTHONPATH=/app compose_api_1 python scripts/verify_crumb.py`
- **Parallel-ok:** no (needs 6–9)

### [x] 12. verify_crumb_api.py — HTTP RBAC + audit verification
- **Files:** `backend/scripts/verify_crumb_api.py` (new)
- **Do:** Mirror `verify_mousse_api.py` (stdlib `urllib`, mints three throwaway users/roles: `writer` = crumb:read+write, `reader` = crumb:read only, `noperm` = none; tokens via `create_access_token`). For every endpoint assert: mutation → 2xx for writer, 403 for reader, 401 unauthenticated; read → 200 reader, 403 noperm, 401 unauthenticated. After a successful create/convert/stage-change/quote-create/status-change/interaction over HTTP, assert the matching `AuditLog` row exists, is attributable (`actor_id`), and targets the entity (SC6 — the 9a/9b HTTP-verify discipline). Self-clean in `finally` (crumb rows → audit rows written → throwaway users/roles).
- **Done when:** script exits 0; proves `crumb:read`/`crumb:write` gate at HTTP level and audit rows for each mutation type.
- **Verify:** `podman exec -e PYTHONPATH=/app compose_api_1 python scripts/verify_crumb_api.py`
- **Parallel-ok:** no (needs 10 + a serving api)

### [x] 13. Regression — 13 existing verify_*.py still exit 0
- **Files:** none (assertion task)
- **Do:** Run the full existing verify suite; crumb is purely additive (touches no SYERP/PLUM/MOUSSE mutation path), so this should hold trivially — assert it anyway (SC7). List: `verify_inventory`, `verify_purchasing`, `verify_e2e_p8`, `verify_gl`, `verify_ap`, `verify_reports`, `verify_gl_api`, `verify_ap_api`, `verify_reports_api`, `verify_mousse`, `verify_mousse_api`, `verify_part_numbering`, `verify_plum_vendor_paths`.
- **Done when:** all 13 exit 0; trial balance still nets zero (via verify_gl/verify_reports).
- **Verify:** `for s in inventory purchasing e2e_p8 gl ap reports gl_api ap_api reports_api mousse mousse_api part_numbering plum_vendor_paths; do podman exec -e PYTHONPATH=/app compose_api_1 python scripts/verify_$s.py || echo "FAIL $s"; done` (confirm each exits 0).
- **Parallel-ok:** no (after 10–12)

### [x] 14. Frontend — CrumbNav, routes, hooks, nav gating
- **Files:** `frontend/src/routes/crumb/components/CrumbNav.tsx` (new), `frontend/src/routes/crumb/hooks.ts` (new), `frontend/src/App.tsx` (add routes), plus confirm `AppShell.tsx` gating (no change expected)
- **Do:** `CrumbNav.tsx` mirrors `MousseNav.tsx` (links: Leads, Pipeline, Quotes, Communications). `hooks.ts` — TanStack Query hooks (`useLeads`, `useLead`, `useOpportunities`/`usePipeline`, `useQuotes`/`useQuote`, `useCustomerTimeline`) + mutations (create/update/archive/convert/stage/status/line/interaction) hitting `/api/v1/crumb/*` via `src/api/client.ts`, with query invalidation. `App.tsx`: add `/crumb` → redirect to `/crumb/leads`, plus `/crumb/leads`, `/crumb/leads/:id`, `/crumb/opportunities`, `/crumb/opportunities/:id`, `/crumb/quotes`, `/crumb/quotes/:id`, `/crumb/communications` (mirror the `mousse` block at `App.tsx:78-81`). Nav gating (enabled ∩ `crumb:read`) is automatic via `AppShell.tsx:39-43` once the module is enabled and the permission held — confirm, do not duplicate.
- **Done when:** with CRUMB enabled + `crumb:read`, the CRUMB nav item appears and routes resolve; `tsc -b` sees the new modules.
- **Verify:** `cd frontend && npm run build` (after later tasks land pages; interim `tsc -b` on the hooks/nav).
- **Parallel-ok:** no (pages depend on it)

### [x] 15. Frontend — Leads list / sheet / archive
- **Files:** `frontend/src/routes/crumb/Leads.tsx`, `frontend/src/routes/crumb/LeadDetail.tsx`, `+ components/` (new)
- **Do:** List (create dialog, archive toggle) + detail sheet: edit fields, link/create customer, convert-to-opportunity action. Use shadcn/ui primitives + `useLeads`/mutations. Mirror `routes/mousse/WorkOrders.tsx` + `WorkOrderDetail.tsx` structure. Serves SC2/SC7.
- **Done when:** can create, edit, archive, link-customer, and convert a lead through the UI against the running api.
- **Verify:** exercise in dev stack; colocated test in Task 19.
- **Parallel-ok:** yes (with 16/17, after 14)

### [x] 16. Frontend — Opportunity pipeline + detail
- **Files:** `frontend/src/routes/crumb/Pipeline.tsx`, `frontend/src/routes/crumb/OpportunityDetail.tsx`, `+ components/` (new)
- **Do:** Per-stage **grouped list** (columns/sections keyed by stage — Qualify / Proposal / Won / Lost) from `usePipeline`; detail with edit + **stage-transition actions** (only valid targets offered, but server enforces — SC3); a "Create quote" action shown **only on a Won opportunity** (D-V3-15). Serves SC3/SC7.
- **Done when:** pipeline renders grouped by stage; moving a card triggers the stage endpoint; invalid moves surface the server 422 via toast; the Create-quote action appears only in the Won stage.
- **Verify:** dev stack; test in Task 19.
- **Parallel-ok:** yes (with 15/17, after 14)

### [x] 17. Frontend — Quote builder + FSM actions
- **Files:** `frontend/src/routes/crumb/Quotes.tsx`, `frontend/src/routes/crumb/QuoteDetail.tsx`, `+ components/` (new line editor)
- **Do:** List + create; detail = **line editor** — add PLUM-part lines (part picker → server-defaulted `unit_price` from released cost + 30% markup, **editable** field, editable `markup_pct`) or free-text lines (description + price + qty); show per-line total + quote `total_value`; FSM action buttons (Send / Accept / Reject / Expire) reflecting `QUOTE_TRANSITIONS`, server-enforced (SC4/D-V3-6). Serves SC4/SC7.
- **Done when:** a PLUM-part line shows the derived default price and accepts an override; totals compute; status transitions drive the endpoint.
- **Verify:** dev stack; test in Task 19.
- **Parallel-ok:** yes (with 15/16, after 14)

### [x] 18. Frontend — Communication-log timeline
- **Files:** `frontend/src/routes/crumb/Communications.tsx`, `+ components/` (new)
- **Do:** Per-customer timeline view (customer picker → `useCustomerTimeline`), newest-first, with a "log interaction" form (type, body, optional lead/opportunity/quote link). Append-only — no edit/delete affordance (SC5/AC5). Serves SC5/SC7.
- **Done when:** logging an interaction appends to the timeline and the entry shows type, UTC timestamp, acting user, and body.
- **Verify:** dev stack; test in Task 19.
- **Parallel-ok:** yes (with 15/16/17, after 14)

### [x] 19. Frontend tests + build gate
- **Files:** `frontend/src/routes/crumb/*.test.tsx` (new, colocated), build
- **Do:** Colocated Vitest for each page (mirror `WorkOrders.test.tsx` / `WorkOrderDetail.test.tsx`): render + mocked-query assertions covering the leads list, pipeline grouping, quote line-price default display, and the comm-log timeline. Then run the production build.
- **Done when:** `npm run test` green for `routes/crumb/*`; `npm run build` (`tsc -b && vite build`) exits 0.
- **Verify:** `cd frontend && npm run test -- routes/crumb && npm run build`
- **Parallel-ok:** no (after 15–18)

## Risks
- **Autogenerate drift (Task 2):** `alembic revision --autogenerate` may emit unrelated diffs if the running DB is behind or a prior model changed. *Early warning:* the generated 0013 contains ops for non-crumb tables — review before committing; regenerate from a clean head-0012 DB.
- **`spawn_quote` import ordering (Tasks 7↔8):** opportunities.py imports quotes.create — a circular import if done eagerly. *Mitigation:* lazy import inside the function (the established `syerp/service/*` pattern); land Task 8 before wiring Task 7's spawn.
- **Released-cost absence (Task 8):** parts with no released revision / null `released_cost_snapshot` would break a naive default. *Early warning:* verify_crumb.py case E must include a part with no released cost → default `0`, price entered manually. Guard for `None` explicitly.
- **HTTP-verify blind spot repeat (9a lesson):** service-level verify_crumb.py cannot prove router audit/RBAC. *Mitigation:* Task 12 is mandatory and gates SC6 — do not treat Task 11 passing as SC6 coverage.
- **partner_id FK type:** `syerp_partner.id` and `plum_part.id` are both String(36) UUID PKs (verified `syerp/models.py:65`, `plum/models.py:92`) — crumb hub FKs must be `String(36)`, matching the MOUSSE precedent. Using Integer would IntegrityError at migration/insert.

## Out of scope (deferred to 11b / later — D-V3-10)
- **Sales orders** (`crumb_sales_order*`, SO-#### numbering, Draft→Confirmed→Fulfilling→Closed FSM) — CRUMB-01 AC4, Phase 11b.
- **Accepted-quote → sales-order conversion** (copying lines) — the AC3 tail; a quote in 11a reaches `Accepted` but there is no SO to convert into.
- **Soft-reservation invariant** (`available = on-hand − reserved ≥ 0`, backorder indicator, the concurrency `asyncio.gather` scenario) — CRUMB-01 AC4/D-V3-8, Phase 11b.
- **GELATO fulfillment / SYERP-13 invoicing links** off a sales order — Phases 12/13.
- **Email send/receive integration and CRM analytics** — excluded by D-V3-5 (out of the whole CRUMB milestone).
- **A price-list entity / global markup settings row** — D-V3-6 (PLUM-16 territory); 11a uses a per-line editable markup only.

## Deviations
- **Task 1 (trivial):** repo `guard-header` hook rejects source files with no `ABOUTME:` header, so `crumb/__init__.py` carries a 2-line ABOUTME header instead of being empty (still a bare package marker, no registration). Commit subject shortened to ≤72 chars per `guard-commit-msg`; full 5-table list moved to the commit body.

## Noticed
<!-- Build-time observations, surprises, and follow-ups discovered during execution — append as you go. -->
- Task 1: `.zj/STATE.md` step was still `plan`, tripping the `guard-scope` advisory on source edits. Manager advanced STATE to `build in progress` at Task 1 close.
- **Task 2 — pre-existing unrelated drift (UNRELATED BUG, not fixed here):** `alembic revision --autogenerate` detected standing model-vs-DB drift on non-crumb tables — removed named unique constraints `uq_plum_part_number`, `uq_syerp_gl_account_code`, `uq_syerp_inventory_item_code`, `uq_syerp_partner_code`, `uq_syerp_purchase_order_po_number`, `uq_syerp_stock_location_name`, and index `uq_plum_part_one_released`. These were correctly EXCLUDED from migration 0013 (crumb-only). They indicate the ORM models name unique constraints the live DB holds under different/auto-generated names (or vice versa). Worth a future reconciliation migration; out of scope for 11a. → surface to owner at wrap-up.
- **Task 2 (trivial):** container autogenerate wrote the file but `PermissionError` blocked persisting to the bind-mounted host dir (container uid can't write host `versions/`); migration hand-authored on host matching the 0012 convention. Circular `crumb_lead`↔`crumb_opportunity` FK broken via post-create `op.create_foreign_key` (dropped first in downgrade).
- **Tasks 6–9:** `status.HTTP_422_UNPROCESSABLE_ENTITY` emits a Starlette deprecation warning (renamed `..._CONTENT`); kept to match every other module (`purchasing.py`/`items.py`/`mousse`). Future one-shot sweep. → surface to owner.
- **Task 8:** service-derived transient `line_total` (qty×unit_price of two Numeric(18,6)) serializes at 12 dp; Decimal-exact so verify passes, but router/schema may want to quantize to 6 dp for display (addressed at Task 10/17).
