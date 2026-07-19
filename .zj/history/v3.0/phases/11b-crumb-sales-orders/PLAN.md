# Plan: Phase 11b — CRUMB sales orders + soft-reservation
Goal: Extend the `crumb` module with sales orders (Draft→Confirmed→Fulfilling→Closed FSM, +Cancelled from Draft/Confirmed), accepted-quote→SO conversion copying lines, and a soft-reservation mechanism where confirming an SO reserves inventory such that `available(item) = derived_on_hand − Σ open SO-line reservations` never goes negative — completing CRUMB-01 (all ACs).
Status: draft

Branch: `feature-crumb-sales-orders` cut off the verified 11a tip (tag `zj/good-11a-crumb-crm-pipeline`, commit `efcf2e6`) — 11a is unmerged; 11b stacks on it per the per-sub-phase branch precedent (D-V3-19, precedent D-P10-8/D-P9b-8). Do NOT create the branch as a plan task; the manager cuts it.
Checklist file to keep: `docs/tasks/feature-crumb-sales-orders.md`.

## Success criteria
Delivers **CRUMB-01 AC4** (sales orders + soft-reservation) + the **AC3 SO-conversion tail** (`.zj/SRD.md:535`, `:560`), completing CRUMB-01 (all ACs). 11b posts **NO GL** — a reservation is a soft quantity (no `InventoryTxn`, no journal entry); trial balance nets zero unchanged. Each SC maps to CRUMB-01 ACs and drives the tasks below.

- **SC1 — SO model + migration + wiring (AC4, AC6):** `crumb_sales_order` + `crumb_sales_order_line` ORM models added to `crumb/models.py` (crumb already aggregated in `core/models.py` — additive only); migration `0014` chains off head `0013`. The SO line carries a nullable `item_id` FK→`syerp_inventory_item.id` (String(36)), `qty_ordered` / `unit_price` Numeric(18,6), a `qty_reserved` Numeric(18,6) accumulator (default 0, D-V3-11), plus `plum_part_id`/`description` for display and `sort_order`. Header auto-numbers `SO-####` numeric-safe (D-P8-6, copying the `generate_quote_number` shape).
- **SC2 — Direct SO CRUD + FSM (AC4):** create an SO in Draft (header: customer, order date, required date; lines editable **only while Draft** — reject line edits once Confirmed with 409, mirroring the quote/PO guard); server-enforced FSM `Draft→Confirmed→Fulfilling→Closed` (+`Cancelled` from Draft/Confirmed), invalid transitions → 422. `SO_TRANSITIONS` added to `crumb/service/_common.py`; `advance_sales_order_status` mirrors `advance_quote_status`/`advance_po_status`.
- **SC3 — Accepted-quote→SO conversion (AC3 tail):** an **Accepted** quote converts to a Draft SO copying its lines; each converted line resolves `item_id` from the quote line's `plum_part_id` via `InventoryItem.plum_part_id` (import the SYERP inventory read — do not duplicate). A line whose part has no linked `InventoryItem`, or a free-text line (no `plum_part_id`), converts with `item_id=NULL` (a non-stock line). Convert requires `quote.status == "accepted"` else 422. The SO stamps `source_quote_id` and `source_opportunity_id` for two-way traceability.
- **SC4 — Soft-reservation crux (AC4, D-V3-8/11/16/18) — THE hard invariant:** confirming a Draft SO (Draft→Confirmed) reserves, per line, `qty_reserved = min(qty_ordered, available(item))` where `available(item) = get_item_on_hand(item) − Σ qty_reserved across ALL OPEN SO lines for that item` (open = SO status in `{confirmed, fulfilling}`). A reservation **never drives available negative**. A line whose ordered qty exceeds available confirms with a derived **shortage/backorder** indicator (`short = qty_ordered − qty_reserved`), NOT hard-blocked (single-shop, D-V3-16). A non-stock line (`item_id` NULL) reserves 0 and shows non-stock/backorder. **Cancelling** a Confirmed SO releases its reservations (each line `qty_reserved→0`, freeing available). **Concurrency:** two concurrent confirms on the same item (`asyncio.gather`) cannot over-reserve — the contended `InventoryItem` row(s) are `SELECT … FOR UPDATE` locked in **sorted-id order BEFORE** the available read-check-write (copy the `bills.py` `create_bill`/`record_payment` lock template). Lock scope is **narrow** — only the contended `InventoryItem` rows (D-V3-18); the broader SYERP floor-guard ledger lock stays deferred.
- **SC5 — Audit + RBAC (AC7, CORE-05):** every mutation (SO create, line add/update/delete, each FSM transition incl. confirm/cancel, quote→SO conversion) writes an attributable audit row at the **router** layer AFTER the service commit with a `crumb.*` action; endpoints gated `crumb:read`/`crumb:write`, refused server-side (401/403). Proven at HTTP level.
- **SC6 — Frontend + regression (AC7, AC6):** SO list + create (Draft line editor mirroring the quote builder) + detail (lines with ordered/reserved/shortage columns, FSM action buttons Confirm/Cancel/Fulfill/Close); a "Convert to SO" affordance on an Accepted quote (extend the 11a `QuoteDetail`); available/reserved/shortage visible; TanStack Query invalidation; colocated Vitest green; `npm run build` clean; nav already gated (no AppShell change). All **15 existing** `verify_*.py` still exit 0; the **2 new** 11b scripts (`verify_crumb_so.py`, `verify_crumb_so_api.py`) exit 0 → **17/17**; trial balance still nets zero (11b posts no GL).

## Context
This is a **pattern-reuse** phase — extend the 11a `crumb` module, do not rebuild. Read before building:
- **11a plan (task shape, verify-script style, idioms):** `.zj/phases/11a-crumb-crm-pipeline/PLAN.md`. Mirror its Done-when/Verify format and Risks/Out-of-scope structure.
- **Quotes service (the template SO code mirrors closely):** `backend/app/modules/crumb/service/quotes.py` — `generate_quote_number` (numeric-safe `~ '^QUOTE-[0-9]+$'` + `cast(func.substring(...,7), Integer).desc()`, retry-once on IntegrityError), `create_quote` (resolve customer → generate number → header+lines in one commit), `_get_draft_quote` (404+409 draft-only guard), `advance_quote_status` (422 on disallowed target). Copy each shape for the SO.
- **Shared surface:** `backend/app/modules/crumb/service/_common.py` holds `STAGE_TRANSITIONS`, `QUOTE_TRANSITIONS`, `DEFAULT_MARKUP_PCT`, `_resolve_customer(db, partner_id)` (404 if partner missing / not `is_customer`). Add `SO_TRANSITIONS` here; reuse `_resolve_customer`.
- **Service package re-exports:** `backend/app/modules/crumb/service/__init__.py` — extend with the new `sales_orders` public surface. Add a new `crumb/service/sales_orders.py` (do NOT put SO logic in `quotes.py`).
- **Reservation on-hand source (item-level derived):** on-hand is `SUM(InventoryTxn.quantity)` per item across all locations — see `backend/app/modules/syerp/service/inventory.py:277` (`select(func.sum(InventoryTxn.quantity)).where(InventoryTxn.item_id == item_id)`). **There is no `get_on_hand` helper today** — the SUM is inlined at 3 call sites. To avoid duplicating it (SC4), Task 5 adds one `get_item_on_hand(db, item_id) -> Decimal` helper to `inventory.py`, exports it via `syerp/service/__init__.py`, and crumb imports it. `get_item(db, item_id)` (inventory.py) already 404s a missing item.
- **`InventoryItem` model:** `backend/app/modules/syerp/models.py:153` — PK `id` String(36) UUID (`:172`), nullable advisory `plum_part_id` String(36) FK→`plum_part.id` (`:182`, no cascade). Resolve conversion `item_id` by querying `InventoryItem` where `plum_part_id == <quote line's plum_part_id>` (nullable if none, or if the part has no item, or the line is free-text).
- **FOR UPDATE lock template (copy exactly, SC4 crux):** `backend/app/modules/syerp/service/bills.py` — `create_bill` locks matched PO-line rows up-front `for locked_id in sorted({...}): await db.execute(select(...id).where(...id == locked_id).with_for_update())` (`:352`), held until the single `db.commit()`; `record_payment` locks target bills the same way (`:847`). Apply this identical shape to lock the distinct `InventoryItem` rows referenced by the SO's stock lines, in sorted-id order, BEFORE computing `available(item)`.
- **FSM pattern:** `syerp/service/purchasing.py:492` `advance_po_status`; `crumb/service/quotes.py:382` `advance_quote_status` (validate `target ∈ TRANSITIONS[current]` else 422).
- **Audit:** `write_audit(db, actor_id, action, target_type, target_id, detail)` (`auth/service.py:313`, self-commits) — called in the router AFTER the service commit. See every mutation in `crumb/router.py` / `mousse/router.py`.
- **Numeric/Decimal only** — `Numeric(18,6)` / Python `Decimal`, never float (D-11). `ROUND_HALF_UP` if quantizing.
- **Migration:** head is `0013` (`0013_crumb_crm_pipeline.py`). Chain `0014` off `0013`. NOTE the 11a Task-2 finding: container autogenerate cannot persist to the bind-mounted host `versions/` dir (`PermissionError`) — **hand-author** `0014` on the host matching the 0013 convention; use autogenerate against a live head-0013 DB only to *read* the diff, and EXCLUDE the 7 spurious pre-existing unique-constraint drops (BACKLOG p2 alembic drift — do not touch them). No circular FK is expected here (SO→quote/opportunity/item are one-directional), so no post-create `op.create_foreign_key` dance is needed.
- **RBAC codes already exist:** `crumb:read`/`crumb:write` were seeded in 11a (`auth/seed.py`) — no seed change needed; reuse `require_permission("crumb:read"|"crumb:write")`.
- **Frontend structure:** `frontend/src/routes/crumb/` already holds `Quotes.tsx`/`QuoteDetail.tsx`, `components/QuoteLineEditor.tsx`/`QuoteCreateDialog.tsx`, `hooks.ts`, `components/CrumbNav.tsx`, `components/lookups.ts`, `components/apiError.ts`. App routes are `App.tsx:92-100`. Mirror these for the SO pages.
- **Verify container:** `podman exec -e PYTHONPATH=/app compose_api_1 python scripts/verify_crumb_so.py` (container name per `verify_mousse.py`).

## Decisions
Recorded this planning session; the manager appends them to `DECISIONS.md` as D-V3-16..19.
- **D-V3-16 (owner):** Unlinked/free-text SO lines are **non-stock** — they confirm with `qty_reserved=0` and show a non-stock/backorder indicator; the SO still confirms (consistent with D-V3-8 "not hard-blocked, single-shop"). This is NOT a hard-block (the MOUSSE-D-P10-7-style reject is explicitly rejected here). Implemented in Tasks 6/8.
- **D-V3-17 (owner):** **Both** direct SO creation (header+lines, editable while Draft, mirroring the quote/PO create) **and** accepted-quote→SO conversion are in scope — the SO is a first-class document (SRD AC4), not merely a conversion artifact. Implemented in Tasks 6 (direct) and 7 (conversion).
- **D-V3-18 (owner):** Reservation locking is **narrow** — lock only the contended `InventoryItem` row(s) `FOR UPDATE` in sorted-id order on confirm, which is sufficient for the reservation invariant. The broader shared SYERP floor-guard ledger lock (BACKLOG p2) is **NOT** taken on here; it defers to Phase 12 when GELATO ship writes real `issue` txns. The reviewer should read the narrow scope as intentional. Implemented in Task 8.
- **D-V3-19 (manager, precedent D-P10-8/D-P9b-8):** Phase 11b branch = `feature-crumb-sales-orders` cut off the verified 11a tip (tag `zj/good-11a-crumb-crm-pipeline`, commit `efcf2e6`) — 11a is unmerged; 11b stacks on it. Not a plan task (see header).

## Tasks

### [x] 1. Add SalesOrder + SalesOrderLine ORM models
- **Files:** `backend/app/modules/crumb/models.py` (extend)
- **Do:** Append two `crumb_`-prefixed models to the existing file, mirroring `Quote`/`QuoteLine` style (Decimal `Numeric(18,6)`, tz-aware `DateTime`, `actor_id: String(36)`, UUID `String(36)` PKs, all hub FKs `String(36)`):
  - `SalesOrder` (`crumb_sales_order`): `id`, `so_number` String(30) unique index NOT NULL, `partner_id` String(36) FK→`syerp_partner.id` NOT NULL, `source_quote_id` String(36) FK→`crumb_quote.id` nullable, `source_opportunity_id` String(36) FK→`crumb_opportunity.id` nullable, `status` String(30) default `"draft"` (draft | confirmed | fulfilling | closed | cancelled), `order_date` Date, `required_date` Date nullable, `actor_id`, `created_at`.
  - `SalesOrderLine` (`crumb_sales_order_line`): `id`, `sales_order_id` String(36) FK→`crumb_sales_order.id` NOT NULL index, `item_id` String(36) FK→`syerp_inventory_item.id` **nullable** (non-stock line when NULL, D-V3-16), `plum_part_id` String(36) FK→`plum_part.id` nullable (display), `description` String nullable (display / free-text), `qty_ordered` Numeric(18,6) NOT NULL, `unit_price` Numeric(18,6) NOT NULL, `qty_reserved` Numeric(18,6) NOT NULL default `Decimal("0")` (the reservation accumulator, D-V3-11), `sort_order` Integer.
- **Done when:** `import app.core.models` succeeds inside the api container and `Base.metadata.tables` contains `crumb_sales_order` + `crumb_sales_order_line`.
- **Verify:** `podman exec -e PYTHONPATH=/app compose_api_1 python -c "from app.core import models as m; print([t for t in m.plum_models.Base.metadata.tables if t.startswith('crumb_sales')])"` → lists both tables.
- **Parallel-ok:** no (foundation)

### [x] 2. Hand-author Alembic migration 0014 for the SO tables
- **Files:** `backend/alembic/versions/0014_crumb_sales_orders.py` (new, hand-authored)
- **Do:** Hand-author `revision="0014"`, `down_revision="0013"`. `create_table` for `crumb_sales_order` and `crumb_sales_order_line` matching Task-1 columns/types (String(36) FKs to `syerp_partner.id`, `crumb_quote.id`, `crumb_opportunity.id`, `syerp_inventory_item.id`, `plum_part.id`; unique index on `crumb_sales_order.so_number`; index on `crumb_sales_order_line.sales_order_id`). Downgrade drops both (line table first). Optionally run `alembic revision --autogenerate` against a live head-0013 DB to *read* the diff, but **EXCLUDE** the 7 spurious pre-existing unique-constraint drops (BACKLOG p2 drift — do not touch). Persist the file on the host (container cannot write the bind-mount, 11a Task-2 finding).
- **Done when:** `alembic upgrade head` creates both tables and `alembic downgrade -1` drops them cleanly; head reports `0014`.
- **Verify:** `podman exec -e PYTHONPATH=/app compose_api_1 alembic upgrade head && podman exec -e PYTHONPATH=/app compose_api_1 alembic current` → shows `0014 (head)`; then `alembic downgrade -1 && alembic upgrade head` round-trips clean.
- **Parallel-ok:** no (depends on Task 1)

### [x] 3. Define SO Pydantic schemas
- **Files:** `backend/app/modules/crumb/schemas.py` (extend)
- **Do:** Pure Pydantic (never import ORM), mirroring the quote schemas (`from_attributes=True` on Reads, `Field(gt=0)` guards, Decimal fields):
  - `SalesOrderLineCreate` (`item_id?`, `plum_part_id?`, `description?`, `qty_ordered: Field(gt=0)`, `unit_price`), `SalesOrderLineRead` (+ derived `qty_reserved`, `line_total = qty_ordered × unit_price`, and derived `shortage = qty_ordered − qty_reserved`).
  - `SalesOrderCreate` (`partner_id`, `order_date?`, `required_date?`, `lines`), `SalesOrderRead` (header), `SalesOrderDetailRead` (header + lines + derived `total_value`), `SalesOrderStatusRequest` (`target_status: str`).
  - `QuoteToSalesOrderRequest` (empty/thin — conversion pulls lines from the quote; optional `order_date`/`required_date`).
- **Done when:** `import app.modules.crumb.schemas` imports clean; `SalesOrderLineRead` exposes `qty_reserved` + `shortage`; positive-qty guard present.
- **Verify:** `podman exec -e PYTHONPATH=/app compose_api_1 python -c "import app.modules.crumb.schemas as s; print(s.SalesOrderLineRead.model_fields.keys(), s.SalesOrderCreate.model_fields.keys())"`
- **Parallel-ok:** yes (with Tasks 4/5, after 1)

### [x] 4. Add SO_TRANSITIONS to _common.py
- **Files:** `backend/app/modules/crumb/service/_common.py` (extend)
- **Do:** Add `SO_TRANSITIONS: dict[str, set[str]]` alongside `QUOTE_TRANSITIONS`: `"draft": {"confirmed", "cancelled"}`, `"confirmed": {"fulfilling", "cancelled"}`, `"fulfilling": {"closed"}`, `"closed": set()`, `"cancelled": set()`. (Cancel allowed from Draft/Confirmed only — NOT from Fulfilling/Closed, per AC4.) Add a brief banner comment mirroring the existing FSM tables.
- **Done when:** `from app.modules.crumb.service._common import SO_TRANSITIONS` succeeds; `SO_TRANSITIONS["fulfilling"] == {"closed"}`; `"cancelled" not in SO_TRANSITIONS["fulfilling"]`.
- **Verify:** `podman exec -e PYTHONPATH=/app compose_api_1 python -c "from app.modules.crumb.service import _common as c; print(c.SO_TRANSITIONS)"`
- **Parallel-ok:** yes (with Tasks 3/5, after 1)

### [x] 5. Add get_item_on_hand helper to SYERP inventory service
- **Files:** `backend/app/modules/syerp/service/inventory.py` (extend), `backend/app/modules/syerp/service/__init__.py` (re-export)
- **Do:** Add `async def get_item_on_hand(db, item_id: str) -> Decimal` returning `SUM(InventoryTxn.quantity)` for the item across all locations, `Decimal("0")` when None — the single item-level source already inlined at `inventory.py:277`. Do NOT 404 (a caller may probe a non-stock or freshly-created item); the SO service resolves item existence separately. Re-export `get_item_on_hand` from `syerp/service/__init__.py` so crumb imports the public surface. This satisfies the SC4 "do not duplicate the SUM logic" constraint. (Refactoring the 3 inline call sites to use the helper is optional and OUT of scope — additive only, to avoid touching verified SYERP paths.)
- **Done when:** `from app.modules.syerp.service import get_item_on_hand` succeeds and returns a `Decimal` for a known item.
- **Verify:** exercised by Task 10; interim `podman exec -e PYTHONPATH=/app compose_api_1 python -c "from app.modules.syerp.service import get_item_on_hand; print(callable(get_item_on_hand))"`.
- **Parallel-ok:** yes (with Tasks 3/4, after nothing runtime)

### [x] 6. Sales-orders service — SO-#### generator, direct create (header+lines), read/list, draft-only line edits, status FSM
- **Files:** `backend/app/modules/crumb/service/sales_orders.py` (new)
- **Do:** Copy the quotes-service shapes (D-V3-17):
  - `_next_sales_order_number` (pure) + `generate_sales_order_number(db)` — regex `~ '^SO-[0-9]+$'`, `cast(func.substring(so_number, 4), Integer).desc()` (skip the 3-char `SO-` prefix), `f"SO-{n:04d}"`, `"SO-0001"` seed. Never lexicographic MAX (D-P8-6).
  - `create_sales_order(db, data, actor_id)`: `_resolve_customer` (reuse), generate number, create header (status `draft`, `order_date` defaults to today if omitted) + lines (`qty_reserved=0`, `sort_order=index`), retry-once on `so_number` IntegrityError (mirror `create_quote`). If a line supplies `item_id`, validate it exists (404 via `get_item`); a NULL `item_id` line is a non-stock line (D-V3-16). Commit and return via `get_sales_order_detail`.
  - `get_sales_order_detail(db, so_id)` (404) — attach transient `line_total`, `shortage = qty_ordered − qty_reserved` per line and header `total_value = Σ line_total` (mirror `get_quote_detail`); `list_sales_orders(db)`.
  - `_get_draft_sales_order(db, so_id)` (404 + 409 if status != draft) + `add_line`/`update_line`/`delete_line` — Draft only (409 once Confirmed, mirror the quote guards).
  - `advance_sales_order_status(db, so_id, target, actor_id)` validating `SO_TRANSITIONS` else 422 — **BUT** delegate `draft→confirmed` and `→cancelled` to Task-8 functions (they carry reservation side-effects); other transitions (`confirmed→fulfilling`, `fulfilling→closed`) are plain status writes here.
  - All Decimal; one commit per operation. Do NOT write audit here (router owns it).
- **Done when:** direct create yields a Draft SO with `SO-####`; line edits succeed while Draft and 409 once Confirmed; `SO-####` increments across a digit-width boundary; valid FSM walk `draft→confirmed→fulfilling→closed` succeeds and an invalid target (e.g. `fulfilling→cancelled`, or any move off `closed`) is 422.
- **Verify:** `verify_crumb_so.py` (Task 10) covers create + numeric-safe boundary + draft-only 409 + FSM valid/invalid.
- **Parallel-ok:** no (Tasks 7/8 import it; needs 3/4/5)

### [x] 7. Sales-orders service — accepted-quote→SO conversion (item_id resolution, linkage)
- **Files:** `backend/app/modules/crumb/service/sales_orders.py` (extend)
- **Do:** `convert_quote_to_sales_order(db, quote_id, data, actor_id)`:
  - Load the quote (404); require `quote.status == "accepted"` else **422** (AC3 tail).
  - Create a Draft SO for the quote's `partner_id`, stamping `source_quote_id = quote.id` and `source_opportunity_id = quote.opportunity_id` (two-way traceability, AC6).
  - Copy each quote line → an SO line: `qty_ordered = quote_line.quantity`, `unit_price = quote_line.unit_price`, carry `plum_part_id`/`description` for display, `qty_reserved=0`. Resolve `item_id`: if `quote_line.plum_part_id` is set, query `InventoryItem` where `plum_part_id == that` and take its `id` (first match); else / if no linked item / free-text line → `item_id = NULL` (non-stock line, D-V3-16). Do NOT duplicate the SUM/lookup — import the SYERP model/read.
  - Reuse `generate_sales_order_number` + the retry-once idiom. Commit; return via `get_sales_order_detail`.
- **Done when:** converting an Accepted quote yields a Draft SO whose lines mirror the quote's (qty/price copied), a part-linked line resolves a real `item_id`, an unlinked/free-text line has `item_id=NULL`, and both `source_quote_id`/`source_opportunity_id` are stamped; converting a non-Accepted quote raises 422.
- **Verify:** `verify_crumb_so.py` (Task 10) — accepted-only guard, line-copy exactness, item_id resolution incl. a non-stock line, linkage stamped both ways.
- **Parallel-ok:** no (extends Task 6)

### [x] 8. Sales-orders service — confirm (reserve, FOR UPDATE lock) + cancel (release) — THE crux
- **Files:** `backend/app/modules/crumb/service/sales_orders.py` (extend)
- **Do:** This is the adversarial-review centerpiece (SC4, D-V3-8/11/16/18).
  - `confirm_sales_order(db, so_id, actor_id)`: load the Draft SO (404; 422 if not Draft). Collect the **distinct** non-NULL `item_id`s across its lines; **lock them FOR UPDATE in sorted-id order BEFORE any read** (copy `bills.py:352` — `for iid in sorted(item_ids): await db.execute(select(InventoryItem.id).where(InventoryItem.id == iid).with_for_update())`). Then, per item, compute `available(item) = get_item_on_hand(db, item_id) − Σ qty_reserved across all OPEN SO lines for that item` where OPEN = SO status in `{confirmed, fulfilling}` (a SQL sum joined on line→SO, excluding this SO's own lines which are still Draft). For each line (deterministic order) reserve `qty_reserved = min(qty_ordered, remaining_available)` clamped ≥ 0, decrementing an in-memory running `remaining_available` per item so multiple lines of the same item on one SO cannot jointly over-reserve. A non-stock line (`item_id` NULL) reserves 0. Set status `confirmed`. **Single commit** releases the locks. Never drive available negative; shortage is derived, never stored, never blocks.
  - `cancel_sales_order(db, so_id, actor_id)`: allowed from Draft or Confirmed (422 otherwise — belt-and-suspenders with `SO_TRANSITIONS`). If it was Confirmed, set every line's `qty_reserved = 0` (release), so the freed quantity re-enters `available` for other SOs. Set status `cancelled`. Commit.
  - Wire Task-6 `advance_sales_order_status` to dispatch `draft→confirmed` to `confirm_sales_order` and any `→cancelled` to `cancel_sales_order`.
  - Finalize `crumb/service/__init__.py` re-exports for all new public functions.
- **Done when:** confirming reserves `min(qty_ordered, available)` per line; available never goes negative; an over-ordered line confirms with `shortage>0` (not blocked); a non-stock line reserves 0; cancelling a Confirmed SO zeroes its reservations and frees available; and **two `asyncio.gather` concurrent confirms on the same scarce item cannot over-reserve** (their combined `qty_reserved ≤ on_hand`).
- **Verify:** `verify_crumb_so.py` (Task 10) scenarios: reservation math (available = onhand − Σ reservations, min() cap, shortage line, non-stock 0, cancel releases) + the concurrency crux (`asyncio.gather`/`asyncio.Barrier`, mirror `verify_mousse.py` scenario F / `verify_ap.py` (j)/(k)).
- **Parallel-ok:** no (extends Tasks 6/7; the phase's highest-risk task)

### [x] 9. Router endpoints + audit for sales orders + conversion
- **Files:** `backend/app/modules/crumb/router.py` (extend), `backend/app/modules/crumb/service/__init__.py` (confirm re-exports)
- **Do:** Add thin routes (reads `crumb:read`, mutations `crumb:write` via `require_permission`), spelling `/crumb/...`:
  - `GET /crumb/sales-orders` (list), `POST /crumb/sales-orders` (create), `GET /crumb/sales-orders/{so_id}` (detail), `POST /crumb/sales-orders/{so_id}/lines`, `PATCH /crumb/sales-orders/{so_id}/lines/{line_id}`, `DELETE /crumb/sales-orders/{so_id}/lines/{line_id}` (draft only), `POST /crumb/sales-orders/{so_id}/status` (FSM — routes confirm/cancel/fulfill/close through `advance_sales_order_status`).
  - `POST /crumb/quotes/{quote_id}/convert` (accepted-quote→SO conversion).
  - After each service commit, `write_audit(...)` with a `crumb.*` action: `sales_order.created`, `sales_order.line_added`/`.line_updated`/`.line_deleted`, `sales_order.status_changed` (detail carrying from→to; the confirm case may note reserved/shortage), `sales_order.confirmed`, `sales_order.cancelled`, `quote.converted_to_sales_order`. `target_type="sales_order"`, `target_id=so.id`.
  - Update the router module docstring endpoint map.
- **Done when:** api boots; `GET /api/v1/crumb/sales-orders` returns 401 anon / 200 with a `crumb:read` token; a create + a confirm each write an audit row; conversion endpoint 422s a non-Accepted quote.
- **Verify:** `podman exec -e PYTHONPATH=/app compose_api_1 python -c "from app.modules.crumb.router import router; print([r.path for r in router.routes if 'sales-order' in r.path or 'convert' in r.path])"` and `verify_crumb_so_api.py` (Task 11).
- **Parallel-ok:** no (needs 6–8)

### [x] 10. verify_crumb_so.py — service-level live-Postgres verification
- **Files:** `backend/scripts/verify_crumb_so.py` (new)
- **Do:** Mirror `verify_crumb.py`/`verify_mousse.py` (owns its async engine/session, builds fixtures — a customer, an InventoryItem with seeded on-hand via receipt txns, a PLUM part linked to that item, an Accepted quote — self-cleans in `finally`). Assert: (A) direct SO create + `SO-####` numeric-safe boundary (`SO-0009→SO-0010`) + survival of a non-`SO-[0-9]+` row; (B) draft-only line edit + 409 once Confirmed; (C) FSM valid walk `draft→confirmed→fulfilling→closed` + invalid-target 422 (incl. `fulfilling→cancelled`); (D) quote→SO conversion — accepted-only 422 guard, line-copy exactness, item_id resolution from `plum_part_id`, a non-stock (NULL item_id) line, both linkage ids stamped; (E) **reservation math** — `available = onhand − Σ reservations`, `min(qty_ordered, available)` cap, a shortage line (`shortage = qty_ordered − qty_reserved > 0`, still confirms), a non-stock line reserves 0, and cancelling a Confirmed SO releases (available frees back); (F) **concurrency crux** — two `asyncio.gather` concurrent confirms on the same scarce item cannot over-reserve (combined `qty_reserved ≤ on_hand`). Print PASS/FAIL; exit non-zero on any FAIL; leave no residual rows.
- **Done when:** script exits 0 against the running DB and self-cleans.
- **Verify:** `podman exec -e PYTHONPATH=/app compose_api_1 python scripts/verify_crumb_so.py`
- **Parallel-ok:** no (needs 6–8)

### [x] 11. verify_crumb_so_api.py — HTTP RBAC + audit verification
- **Files:** `backend/scripts/verify_crumb_so_api.py` (new)
- **Do:** Mirror `verify_crumb_api.py`/`verify_mousse_api.py` (stdlib `urllib`; mints throwaway `writer` = crumb:read+write, `reader` = crumb:read, `noperm` = none; tokens via `create_access_token`). For every SO mutation + the convert endpoint assert: mutation → 2xx writer, 403 reader, 401 anon; read → 200 reader, 403 noperm, 401 anon. After a successful SO create, a confirm, a cancel, and a quote→SO conversion over HTTP, assert the matching `AuditLog` row exists, is attributable (`actor_id`), and targets the SO (SC5). Self-clean in `finally` (crumb rows, audit rows, throwaway users/roles).
- **Done when:** script exits 0; proves `crumb:read`/`crumb:write` gate SO endpoints at HTTP level and audit rows exist for create/confirm/cancel/convert.
- **Verify:** `podman exec -e PYTHONPATH=/app compose_api_1 python scripts/verify_crumb_so_api.py`
- **Parallel-ok:** no (needs 9 + a serving api)

### [x] 12. Regression — all 15 existing verify_*.py + both 11a crumb scripts still exit 0
- **Files:** none (assertion task)
- **Do:** Run the full existing verify suite; 11b is additive (touches no SYERP/PLUM/MOUSSE *mutation* path — the only SYERP change is the additive read helper in Task 5), so this should hold — assert it anyway (SC6). Existing 15: `verify_inventory`, `verify_purchasing`, `verify_e2e_p8`, `verify_gl`, `verify_ap`, `verify_reports`, `verify_gl_api`, `verify_ap_api`, `verify_reports_api`, `verify_mousse`, `verify_mousse_api`, `verify_part_numbering`, `verify_plum_vendor_paths`, `verify_crumb`, `verify_crumb_api`. With the 2 new (`verify_crumb_so`, `verify_crumb_so_api`) → **17/17**.
- **Done when:** all 15 existing exit 0; trial balance still nets zero (verify_gl/verify_reports); 11b posts no GL/InventoryTxn.
- **Verify:** `for s in inventory purchasing e2e_p8 gl ap reports gl_api ap_api reports_api mousse mousse_api part_numbering plum_vendor_paths crumb crumb_api; do podman exec -e PYTHONPATH=/app compose_api_1 python scripts/verify_$s.py >/dev/null && echo "OK $s" || echo "FAIL $s"; done`
- **Parallel-ok:** no (after 9–11)

### [x] 13. Frontend — SO hooks, routes, nav item
- **Files:** `frontend/src/routes/crumb/hooks.ts` (extend), `frontend/src/App.tsx` (add routes), `frontend/src/routes/crumb/components/CrumbNav.tsx` (add "Sales Orders" link)
- **Do:** Add TanStack Query hooks (`useSalesOrders`, `useSalesOrder`, mutations `useCreateSalesOrder`, `useAddSoLine`/`useUpdateSoLine`/`useDeleteSoLine`, `useAdvanceSalesOrderStatus`, `useConvertQuoteToSalesOrder`) hitting `/api/v1/crumb/sales-orders*` and `/crumb/quotes/{id}/convert` via `src/api/client.ts`, with query invalidation (invalidate SO lists/detail on mutate; the convert mutation also invalidates the source quote). Add `/crumb/sales-orders` and `/crumb/sales-orders/:id` routes in the `App.tsx` crumb block (`:92-100`). Add a "Sales Orders" link to `CrumbNav.tsx`. Nav gating (CRUMB enabled ∩ `crumb:read`) is automatic — no AppShell change.
- **Done when:** with CRUMB enabled + `crumb:read`, the "Sales Orders" nav item appears and both routes resolve; `tsc -b` sees the new hooks.
- **Verify:** `cd frontend && npx tsc -b` (full `npm run build` after pages land in Task 17).
- **Parallel-ok:** no (pages depend on it)

### [x] 14. Frontend — Sales Orders list + create (Draft line editor)
- **Files:** `frontend/src/routes/crumb/SalesOrders.tsx` (new), `frontend/src/routes/crumb/components/SalesOrderCreateDialog.tsx` (new), `frontend/src/routes/crumb/components/SalesOrderLineEditor.tsx` (new)
- **Do:** List view (columns: SO number, customer, status, order date, total) with a create dialog. Create dialog uses a line editor mirroring `QuoteLineEditor.tsx` — add item/part or free-text lines with qty + unit price. Mirror `Quotes.tsx`/`QuoteCreateDialog.tsx` structure and shadcn/ui primitives. Serves SC6.
- **Done when:** can create an SO with lines through the UI against the running api and it appears in the list.
- **Verify:** dev stack; colocated test in Task 17.
- **Parallel-ok:** yes (with Task 15/16, after 13)

### [x] 15. Frontend — Sales Order detail (ordered/reserved/shortage + FSM actions)
- **Files:** `frontend/src/routes/crumb/SalesOrderDetail.tsx` (new), `+ components/` as needed
- **Do:** Detail page: header (customer, dates, status, source quote/opportunity links), a lines table with **ordered / reserved / shortage** columns (shortage highlighted, non-stock lines flagged), Draft-only line editing, and FSM action buttons (Confirm / Cancel / Fulfill / Close) that only offer valid `SO_TRANSITIONS` targets but let the server enforce (surface a 422 via toast). After Confirm, the reserved/shortage figures refresh (query invalidation). Mirror `QuoteDetail.tsx`. Serves SC4/SC6.
- **Done when:** confirming an SO in the UI shows per-line reserved and any shortage; cancelling a Confirmed SO frees reservations; invalid transitions surface a toast.
- **Verify:** dev stack; test in Task 17.
- **Parallel-ok:** yes (with Task 14/16, after 13)

### [x] 16. Frontend — "Convert to SO" affordance on an Accepted quote
- **Files:** `frontend/src/routes/crumb/QuoteDetail.tsx` (extend)
- **Do:** Add a "Convert to Sales Order" button shown **only when `quote.status === "accepted"`**, calling `useConvertQuoteToSalesOrder`; on success, toast + navigate to the new SO detail. Serves SC3/SC6.
- **Done when:** an Accepted quote shows the button; converting creates an SO and navigates to it; a non-Accepted quote does not show the button.
- **Verify:** dev stack; test in Task 17.
- **Parallel-ok:** yes (with Task 14/15, after 13)

### [x] 17. Frontend tests + build gate
- **Files:** `frontend/src/routes/crumb/SalesOrders.test.tsx`, `SalesOrderDetail.test.tsx`, `QuoteDetail.test.tsx` (extend) (colocated), build
- **Do:** Colocated Vitest mirroring `Quotes.test.tsx`/`QuoteDetail.test.tsx`: render + mocked-query assertions covering the SO list, the detail's ordered/reserved/shortage columns, the FSM action buttons, and the "Convert to SO" button visibility (accepted vs non-accepted). Then run the production build.
- **Done when:** `npm run test` green for `routes/crumb/*`; `npm run build` (`tsc -b && vite build`) exits 0.
- **Verify:** `cd frontend && npm run test -- routes/crumb && npm run build`
- **Parallel-ok:** no (after 14–16)

## Risks
- **Reservation over-reserve under concurrency (Task 8, the crux):** the read-check-write of `available` is exactly the shape where 11a's 20 green assertions missed a defect. *Early warning:* if the FOR UPDATE lock is taken AFTER (not before) the available read, or omitted for a same-item multi-line SO, `verify_crumb_so.py` scenario F will show combined `qty_reserved > on_hand`. Mitigation: lock distinct `InventoryItem` rows in sorted-id order up-front (copy `bills.py:352`), and clamp a per-item in-memory running remainder across a single SO's lines. Mandate a full adversarial review of Task 8 before verify.
- **`available` must exclude this SO's own Draft lines (Task 8):** the Σ-reservations term counts OPEN (`confirmed`/`fulfilling`) SO lines only; the SO being confirmed is still Draft, so it is naturally excluded — but a naive "all reserved" sum that includes Draft would be wrong. *Early warning:* self-double-counting shows as under-reservation on the first confirm. Guard the status filter explicitly.
- **Migration autogenerate cannot write the bind-mount (Task 2, 11a Task-2 finding):** `PermissionError` on the host `versions/` dir. Mitigation: hand-author `0014`; use autogenerate only to read the diff, and exclude the 7 spurious pre-existing unique-constraint drops (BACKLOG p2). *Early warning:* a `0014` that drops `uq_*` constraints on non-crumb tables.
- **HTTP-verify blind spot (SC5, 9a/11a lesson):** service-level `verify_crumb_so.py` cannot prove router audit/RBAC. Mitigation: Task 11 is mandatory and gates SC5 — do not treat Task 10 passing as SC5 coverage.
- **item_id resolution ambiguity (Task 7):** multiple `InventoryItem`s could carry the same `plum_part_id` (advisory, no uniqueness). *Early warning:* conversion picks a non-deterministic item. Mitigation: take the first match by a stable order (e.g. `id`); note this is acceptable for the single-shop model and surface it in `## Noticed` if it bites.

## Out of scope (deferred — state explicitly so build does not drift)
- **GELATO pick/pack/ship consuming the reservation** and posting the real `issue` `InventoryTxn` + COGS-on-ship JE — Phase 12 (GELATO-01.5). 11b posts NO GL and NO InventoryTxn; a reservation is a soft quantity only.
- **SYERP-13 invoicing from the SO** — Phase 13.
- **Lot/serial reservation granularity** — D-V3-4.
- **The broader shared SYERP floor-guard ledger lock unification** — BACKLOG p2, deferred to Phase 12 when GELATO writes real issue txns (D-V3-18). 11b takes only the narrow per-`InventoryItem` confirm lock.
- **The Starlette 422 deprecation sweep** (`HTTP_422_UNPROCESSABLE_ENTITY` → `..._CONTENT`) — BACKLOG p3; keep matching the module convention.
- **Refactoring the 3 inline `SUM(InventoryTxn.quantity)` call sites** to use the new `get_item_on_hand` helper — additive only in 11b to avoid touching verified SYERP paths.

## Decisions needed
None — all visible choices (non-stock line handling, direct-create-plus-conversion scope, lock narrowness, branch base) are resolved in `## Decisions` (D-V3-16..19).

## Deviations
<!-- Record any planned-vs-built divergences discovered during execution — append as you go. -->
- **SO list "total" column omitted (trivial, Task 14):** the plan's Task-14 column list names "total", but `GET /crumb/sales-orders` returns header-only `SalesOrderRead` (no `total_value`; that field is derived on the detail schema only). Rendering per-row totals would need an N+1 detail fetch or a backend schema+service change — disproportionate for a cosmetic column, and SC6's substantive requirement (the **detail** page's ordered/reserved/shortage) is unaffected. List columns: SO #, customer, status, order date. `total_value` is shown on the detail page (Task 15). Follow-up if desired: attach `total_value` to the list header schema in a later docs/UX pass.
- **Branch base (trivial):** plan header cites the tag `zj/good-11a-crumb-crm-pipeline` at commit `efcf2e6`, but the tag actually sits at `7c573d3` and the branch tip `a8191cf` carries two docs-only commits on top (11a retro + this 11b plan). `git diff --name-only tag..HEAD` is entirely under `.zj/` — the verified 11a **code** is byte-identical at the tag and at HEAD. Cut `feature-crumb-sales-orders` off `a8191cf` (not the bare tag) so the branch carries the PLAN.md it executes; the D-V3-19 intent ("verified 11a tip") is preserved.

## Noticed
<!-- Build-time observations, surprises, and follow-ups discovered during execution — append as you go. -->
- **Task 8 adversarial review (mandated 11a keeper) → VERDICT PASS** (`.zj/phases/11b-crumb-sales-orders/REVIEW-task8.md`). Reservation invariant holds under concurrency (lock-before-read in sorted-id order, Σ-reserved filtered to `{confirmed,fulfilling}` & excluding self, per-item running remainder, NULL lines reserve 0). Findings: (1) **Medium** — soft reservation does not serialize against `post_adjustment`/`post_transfer` stock write-offs (a `−50` adjustment after a confirm can leave `available` negative); this is **D-V3-18 by-design** (narrow per-`InventoryItem` confirm lock; broader SYERP floor-guard ledger lock deferred to Phase 12 / BACKLOG p2). (2) **Low** — SO router/HTTP surface unreachable until Task 9 (the 11a green-but-broken risk; Task 11 HTTP verify covers it). (3) **Low** — Closed SOs retain stale `qty_reserved` but Closed ∉ OPEN so it is uncounted (cosmetic; a future zero-on-close is optional).
- **Item→InventoryItem ambiguity (Task 7):** `InventoryItem.plum_part_id` has no uniqueness constraint; conversion picks the lowest `id` deterministically. Acceptable for single-shop; a primary/sellable flag or uniqueness constraint is a possible future follow-up.
- **Task 6 — confirm/cancel seam:** `advance_sales_order_status` dispatches the two reservation-bearing moves (`draft→confirmed`, any `→cancelled`) to module-level `confirm_sales_order`/`cancel_sales_order` stubs that currently `raise NotImplementedError("… wired in Task 8")`. Task 8 fills those two bodies with the soft-reservation side-effects — no change needed to the FSM dispatch itself. Added a small private `_validate_line` helper (not named in the plan) for the item-existence 404, mirroring how quotes.py factors `_resolve_line_amounts`.
- **Task 6 — line-editor name collision (for Task 7/wiring):** `sales_orders.py` defines `add_line`/`update_line`/`delete_line`/`_get_line` with the same names as `quotes.py`. Fine while both are imported from their submodules, but the CRUMB `service/__init__.py` cannot re-export both flat sets under those bare names — the router/wiring task must import from the submodules directly or alias (e.g. `add_so_line`).
- **Task 7 — item_id resolution ambiguity (as flagged in Risks):** `InventoryItem.plum_part_id` is advisory with no uniqueness constraint, so multiple stock items can carry the same `plum_part_id`. Conversion resolves it deterministically as the first match `ORDER BY InventoryItem.id LIMIT 1` (helper `_resolve_item_id_for_part`) — acceptable for the single-shop model, but if a shop ever links two items to one PLUM part the chosen item is arbitrary (lowest id), not necessarily the intended sellable one. Follow-up if it bites: add a "primary/sellable" flag or a uniqueness constraint on the advisory link.

## Verify fix loop (2026-07-17)
- **[BLOCKER — FIXED] Direct-create/edit SO lines never reserved (headline feature dead through the UI).** The code review caught what 17 green verify assertions hid: the FE line editor (`SalesOrderLineEditor.tsx`) sends a part line as `plum_part_id` ONLY (never `item_id`), and the **direct** create/add/update service path copied `item_id` verbatim without the `plum_part_id→item_id` bridge that **conversion** already applied — so every UI-created SO line persisted `item_id=NULL`, reserved 0 on confirm, and showed a false "Non-stock" badge + full shortage even with stock on hand. Breaks SC4 + SC6 for direct SOs (first-class scope, D-V3-17). Fix (backend-only): folded resolution into a new `_resolve_and_validate_item_id` used by `create_sales_order`, `add_line`, `update_line` — an explicit `item_id` is validated + used as-is; otherwise resolve via the same `_resolve_item_id_for_part` conversion uses; neither → genuine non-stock (NULL). **Root cause of the blind spot:** `verify_crumb_so.py` passed `item_id=` directly, bypassing the UI shape — the exact 11a "green-but-broken" pattern. Closed with new load-bearing assertions **(D2)** driving a `plum_part_id`-only line through `create_sales_order` and asserting it resolves to the linked stock item (would have failed pre-fix). Re-ran full suite → **17/17 green**, TB still nets zero.
- **[FOLLOW-UP — deferred, owner-approved] Convert has no idempotency guard.** An Accepted quote can be converted to unlimited duplicate SOs — no status change, no guard — while `QuoteDetail.tsx` copy implies the quote "moves to converted." Left open this phase (owner chose fix-blocker-only); revisit when quote lifecycle post-conversion is specified (candidate: 422 re-convert if the quote already has a `source_quote_id` SO, or a `converted` quote status). Logged to BACKLOG.
