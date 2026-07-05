# Plan: Phase 08 — SYERP Extended: inventory & purchasing
Goal: A shop can stock inventory items across named locations with a moving-average-valued
immutable ledger, and run purchase orders (Draft→Approved→Receiving→Closed) whose receipts post
inventory receipts at the PO line unit cost — no AP, no bins, no negative stock, no over-receipt.
Status: ready-to-build (planned 2026-07-05; all decisions resolved)

## Success criteria
Every numbered acceptance criterion of **SYERP-10** (1–8) and **SYERP-11** (1–8) in
`/home/zack/Projects/BizNiceSweets/.zj/SRD.md` must be covered by ≥1 task (see the mapping table
at the end). Requirement statements and their **Verification** paragraphs are authoritative.

## Context

**This phase EXTENDS the existing `syerp` module — do NOT create a new module package.** Grow the
existing files / add cohesive new files inside `backend/app/modules/syerp/`.

Files to read/follow (all patterns already live in the repo):
- Backend module: `backend/app/modules/syerp/{models,schemas,service,router,__init__}.py`,
  `backend/app/modules/syerp/coa_seed.py` (idempotent seed pattern).
- **Numeric-safe code generator (the reference to copy):** `generate_part_number` in
  `backend/app/modules/plum/service.py:108` — regex-filter `^P[0-9]+$` then
  `order_by(cast(func.substring(...), Integer).desc())`. **Do NOT** copy `generate_partner_code`
  (`syerp/service.py:43`) — it uses lexicographic `MAX(code)` (D-P8-6, the Phase-7 defect).
- Collision handling: `create_partner` (`syerp/service.py:105`) — best-effort generator + DB unique
  constraint as the real guard + retry-once on `IntegrityError` for auto-generated codes.
- Thin-router + audit + RBAC: `syerp/router.py` (`create_partner_endpoint`,
  `update_partner_endpoint`). Gate with `Depends(require_permission("syerp:read"|"syerp:write"))`
  from `app.modules.auth.dependencies`; call `write_audit(db, actor_id=str(current_user.id),
  action=..., target_type=..., target_id=..., detail=...)` from `app.modules.auth.service` after
  every mutation (signature at `auth/service.py:313`).
- FSM action-endpoint shape: `advance_revision_status_endpoint` + `VALID_TRANSITIONS`
  (`plum/router.py:351`, `plum/service.py:95`) — the model for PO approve/close/receive.
- Migrations: `backend/alembic/versions/0004_syerp_tables.py` is the DDL template; current head is
  **`0006`**. New revisions chain `0007→0006`, `0008→0007`. Auto-run by `backend/entrypoint.sh`.
- `Numeric(18,6)` / `Decimal` columns: `backend/app/modules/plum/models.py:210` (D-11 — never float).
- PK conventions: `Partner` uses `String(36)` uuid PK (`syerp/models.py:55`); `GLAccount` uses
  `Integer` autoincrement (`syerp/models.py:126`). Pick per-table (justified in Task 1 / Task 15).
- **RBAC already seeded** — `backend/app/modules/auth/seed.py:34-35` seeds `syerp:read`/`syerp:write`
  and grants both to the `user` role and (via wildcard) `admin`. **No new permission seeding**
  (D-P8-10 — a single `syerp:write` gates all mutations incl. PO approval). Verify, do not add.
- Frontend list+sheet+archive template to mirror: `frontend/src/routes/syerp/Vendors.tsx`,
  `Customers.tsx`, `components/PartnerSheet.tsx`, `components/PartnerArchiveDialog.tsx`,
  `components/SyerpNav.tsx`; routes in `frontend/src/App.tsx:37-40`; shadcn primitives in
  `frontend/src/components/ui/` (button, input, sheet, dialog, select, table, switch, badge…);
  single axios client `frontend/src/api/client.ts`; TanStack Query + inline `fetchX` helpers per
  screen; toasts via `sonner`; colocated `*.test.tsx` (Vitest, which **does** run).

**Testing reality (D-P7-4):** the backend live-DB pytest harness is broken (async-engine/event-loop
mismatch — silently skips or errors; repair is BACKLOG p1). Therefore: DO write pytest tests under
`backend/tests/syerp/` (mirroring `test_partners.py` / `backend/tests/plum/test_costing.py`), but no
task's **Verify** may depend solely on `pytest … green`. Verifiable truth comes from (a) **pure-Decimal
unit tests** that need no DB, and (b) **standalone async scripts run against live Postgres** (the
Phase-7 precedent) placed in `backend/scripts/`. Frontend Vitest is trustworthy — use it.

**Owner decisions binding this plan (record as D-P8-8/9/10):**
- D-P8-8 — one phase, sequenced in wave order: inventory backend → inventory UI → purchasing backend
  → purchasing UI → verify. PO receiving is built on a working, verified inventory ledger.
- D-P8-9 — UI folded into these tasks (no separate DESIGN.md); reuse the Partner list+sheet+archive
  template; novel screens are on-hand-by-location, adjust/transfer, and PO create/approve/receive.
- D-P8-10 — a single `syerp:write` gates ALL mutations including PO approval; reads use `syerp:read`.
  No separate approve permission. Approver identity captured via audit only.
Fixed spec scope (D-P8-1..7, D-11 — honor, do not reopen): item is a SYERP master with nullable
`plum_part_id`; flat named locations only; moving weighted-average valuation; PO depth = receive,
no AP; numeric-safe generators; reject negative stock + over-receipt; all money/qty `Decimal`.

## Decisions (resolved with owner 2026-07-05 → DECISIONS.md D-P8-11..15)
1. **Branch = `feature-syerp-inventory-purchasing` cut from the current `bugfix-plum-v1-gaps`
   tip** (D-P8-11). NOT from `master` — verified `master` (HEAD `f4e2bd3`, Dec 2025) predates the
   re-platform and has no `backend/`/`frontend/`/`.zj/` (the D-P7-3 trap). The current tip carries
   all real code + the Phase-7 fixes; Phase 8 builds atop unmerged Phase 7 (owner already chose to
   plan 8 before closing v1.0). Cut the branch before Task 1.
2. **Code prefixes: items `ITEM-0001`, POs `PO-0001`** (D-P8-13) — regex `^ITEM-[0-9]+$` /
   `^PO-[0-9]+$`, order by integer cast of the substring after the prefix (D-P8-6 numeric-safe).
3. **Seed one idempotent `Main` stock location** on fresh deploy (D-P8-14), mirroring `coa_seed.py`
   upsert-by-name — so receiving works out-of-the-box; re-running the seed adds none.
4. **Moving-average = stored `moving_avg_cost Numeric(18,6)` column** on `syerp_inventory_item`,
   recomputed transactionally on each receipt (D-P8-12). On-hand **quantity** stays a derived
   `SUM(quantity)` over the immutable ledger; the ledger keeps every receipt `unit_cost` so the
   average remains auditable/replayable. This is a mutated-by-design column, NOT a violation of the
   "on-hand is derived" rule. (Full ledger-replay was the rejected alternative.)
5. **PO line `qty_received` = stored accumulator** on the PO line (D-P8-15) — POs are mutable working
   documents, not the immutable ledger — cross-checkable against `SUM(quantity)` of receipt txns
   whose `source_id` = the line.

---

## Tasks

### WAVE A — Inventory backend (SYERP-10)

### [ ] 1. Create the inventory schema (migration 0007 + ORM models)
- **Files:** `backend/alembic/versions/0007_syerp_inventory.py` (new, chains `→0006`);
  `backend/app/modules/syerp/models.py` (append three classes).
- **Do:** Add ORM models + matching DDL for:
  - `syerp_inventory_item` — `id` **String(36)** uuid PK (mirrors `Partner`; referenced by FKs from
    txns & PO lines, non-enumerable); `code` String(20) unique+index; `name` String(255) index;
    `unit_of_measure` String(50); `plum_part_id` String(36) **nullable** FK→`plum_part.id`
    (no cascade — D-P8-2, must work with PLUM disabled); `moving_avg_cost` Numeric(18,6) default 0
    (Decision 4); `active` Boolean default True index; `created_at`/`updated_at` tz-aware.
  - `syerp_stock_location` — `id` **Integer** autoincrement PK (small controlled set, mirrors
    `GLAccount`); `name` String(100) unique+index; `active` Boolean default True; timestamps.
  - `syerp_inventory_txn` (append-only ledger, AC10-4) — `id` String(36) uuid PK; `item_id`
    FK→item index; `location_id` FK→location index; `txn_type` String(20)
    (`receipt|issue|adjustment|transfer`); `quantity` Numeric(18,6) **signed**; `unit_cost`
    Numeric(18,6) nullable; `created_at` tz-aware (UTC) index; `actor_id` String(36);
    `source_type` String(50) nullable; `source_id` String(36) nullable; `reason` String(255)
    nullable; `transfer_group_id` String(36) nullable (pairs the two legs of a transfer).
  - Follow `0004_syerp_tables.py` for `UniqueConstraint`/`create_index` naming; author the DDL by
    hand from the models (no autogenerate).
- **Done when:** models import clean and `alembic upgrade head` creates all three tables with the
  unique/index/FK constraints on a fresh DB.
- **Verify:** `cd backend && alembic upgrade head` against the dev Postgres
  (`podman-compose -f compose/compose.yml -f compose/compose.dev.yml up -d db`), then
  `alembic downgrade -1 && alembic upgrade head` round-trips clean; `python -c "import app.modules.syerp.models"` (via backend venv) errors-free.
- **Parallel-ok:** no (foundation for all of Wave A).

### [ ] 2. Inventory item CRUD + numeric-safe item-code generator
- **Files:** `backend/app/modules/syerp/service.py` (add `generate_item_code`, `create_item`,
  `list_items`, `get_item`, `update_item`); `backend/app/modules/syerp/schemas.py`
  (`InventoryItemCreate/Update/Read`); `backend/app/modules/syerp/router.py`
  (`/syerp/inventory/items` GET list+search, POST, GET one, PATCH incl. archive).
- **Do:** Copy the numeric-safe pattern from `plum/service.py:108` (regex `^ITEM-[0-9]+$`,
  `order_by(cast(func.substring(code, 6), Integer).desc())`) — Decision 2 prefix. Copy the
  best-effort-generator + retry-once-on-IntegrityError shape from `create_partner`. Mirror
  `list_partners` (server-side `.ilike` search on code/name; `include_archived` default False) and
  the PATCH-archive audit-action selection (`item.archived` vs `item.updated`). Gate reads
  `syerp:read`, writes `syerp:write`; `write_audit` after each mutation (AC10-7,8).
- **Done when:** create item (with and without `plum_part_id`) auto-numbers `ITEM-####`; duplicate
  explicit code → 409; PATCH `{active:false}` archives and drops from default list; every mutation
  writes an audit row.
- **Verify:** `backend/scripts/verify_inventory.py` (Task 8) exercises this against live Postgres;
  pure-unit test of the generator's digit-boundary in `backend/tests/syerp/test_inventory.py`
  (asserts `ITEM-9` → `ITEM-10`, never lexicographic). (pytest live-DB parts may skip — harness broken.)
- **Parallel-ok:** yes (with Task 3).

### [ ] 3. Stock-location CRUD
- **Files:** `service.py` (`create_location`, `list_locations`, `get_location`, `update_location`);
  `schemas.py` (`StockLocationCreate/Update/Read`); `router.py`
  (`/syerp/inventory/locations` GET/POST/GET-one/PATCH); optional idempotent seed of `Main` in
  `coa_seed.py` or a new `inventory_seed.py` wired into the lifespan seed (Decision 3).
- **Do:** Straight CRUD mirroring Partner (unique `name`, `active` soft-delete, audit
  `location.created|updated|archived`, RBAC as Task 2). If Decision 3 = yes, add
  `seed_default_location(db)` following `coa_seed.py`'s upsert-by-name idempotency and register it
  where seeds run.
- **Done when:** locations CRUD works with audit; archived locations hidden from default list; (if
  seeded) a fresh DB has exactly one `Main` location and re-running the seed adds none.
- **Verify:** covered by `verify_inventory.py` (Task 8); seed idempotency asserted by re-invoking
  the seed twice in that script and counting rows.
- **Parallel-ok:** yes (with Task 2).

### [ ] 4. On-hand & valuation read (derivation query)
- **Files:** `service.py` (`get_item_onhand(db, item_id)` → per-location `SUM(quantity)` + total +
  `total_qty * moving_avg_cost`); `schemas.py` (`OnHandByLocation`, `ItemOnHandRead`); `router.py`
  (`GET /syerp/inventory/items/{item_id}/onhand`, `syerp:read`).
- **Do:** On-hand is a **derived aggregate** — `select(txn.location_id, func.sum(txn.quantity))
  .where(item_id==).group_by(location_id)` joined to location names; NEVER read a stored qty column
  (AC10-3). Value uses the item's `moving_avg_cost` (AC10-5). Return per-location rows + grand total
  qty + on-hand value.
- **Done when:** endpoint returns correct signed sums per location and total value; a location with
  zero net is omitted or shown as 0 (pick and document).
- **Verify:** `verify_inventory.py` posts known txns and asserts the derived on-hand + value match
  hand-computed Decimals.
- **Parallel-ok:** no (depends on Task 1; consumed by Wave B).

### [ ] 5. Receipt transaction posting + moving-average recompute
- **Files:** `service.py` (pure helper `compute_new_moving_avg(qty_before, avg_before, qty_recv,
  unit_cost) -> Decimal`; `post_receipt(db, item_id, location_id, qty, unit_cost, actor_id,
  source_type=None, source_id=None)`); `schemas.py` (`ReceiptCreate`); `router.py`
  (`POST /syerp/inventory/items/{item_id}/receipts`, `syerp:write`).
- **Do:** `qty_before` = total item on-hand across ALL locations (avg is item-level, not per-location);
  `avg_new = (qty_before*avg_before + qty_recv*unit_cost)/(qty_before+qty_recv)` in `Decimal`
  (AC10-5, D-11); first receipt (qty_before 0) → avg = unit_cost with no div-by-zero. Append one
  `receipt` txn (positive signed qty) and update `item.moving_avg_cost`, in one transaction. Reject
  `qty<=0` or `unit_cost<0` (4xx). `write_audit` `inventory.receipt` (AC10-4,7,8).
- **Done when:** posting a receipt appends an immutable txn, updates on-hand (Task 4) and moving-avg
  per the formula; audit row written.
- **Verify:** **pure-Decimal unit tests** (no DB) for `compute_new_moving_avg`: first receipt,
  weighted second receipt (e.g. 10@2 then 10@4 → 3.000000), and exactness (no float drift) in
  `backend/tests/syerp/test_inventory.py`; plus `verify_inventory.py` end-to-end against live DB.
- **Parallel-ok:** no (Tasks 6, 7, and all of Wave C receiving depend on it).

### [ ] 6. Adjustment transaction posting (reason + negative-stock rejection)
- **Files:** `service.py` (`post_adjustment(db, item_id, location_id, qty_delta, reason, actor_id)`);
  `schemas.py` (`AdjustmentCreate`, `reason` required); `router.py`
  (`POST /syerp/inventory/items/{item_id}/adjustments`, `syerp:write`).
- **Do:** Signed `qty_delta` (negative covers the manual "issue" case in v2.0 — the `issue` txn_type
  stays reserved for MOUSSE). Guard: if resulting **location** on-hand (`current_loc_onhand +
  qty_delta`) would be `< 0` → reject 4xx (AC10-6, D-P8-7). Positive adjustment adds qty at the
  current average (avg unchanged — only receipts move the average, AC10-5). Append one `adjustment`
  txn with `reason`; `write_audit` `inventory.adjustment`.
- **Done when:** a valid adjustment posts a txn and shifts on-hand; an adjustment driving a location
  negative returns 4xx and writes no txn; the item's moving-avg is unchanged.
- **Verify:** `verify_inventory.py` asserts the negative-rejection (no row appended, avg unchanged)
  and a positive adjustment path; pure-unit assertion that avg is untouched by adjustments.
- **Parallel-ok:** yes (with Task 7, after Task 5).

### [ ] 7. Transfer transaction posting (paired legs, nets-zero, negative guard)
- **Files:** `service.py` (`post_transfer(db, item_id, from_location_id, to_location_id, qty,
  actor_id)`); `schemas.py` (`TransferCreate`); `router.py`
  (`POST /syerp/inventory/items/{item_id}/transfers`, `syerp:write`).
- **Do:** Reject `from == to` or `qty<=0` (4xx). Guard: if `from`-location on-hand `< qty` → reject
  4xx (AC10-6). Write TWO txns sharing a `transfer_group_id`: `-qty` at `from`, `+qty` at `to`, both
  `txn_type='transfer'`, valued at current `moving_avg_cost`. Total item on-hand nets to zero; item
  moving-avg unchanged. `write_audit` `inventory.transfer`.
- **Done when:** a transfer moves qty between locations, total on-hand and item avg unchanged; an
  over-draw from source returns 4xx and appends nothing.
- **Verify:** `verify_inventory.py` asserts total on-hand invariant across a transfer and the
  source-underflow rejection.
- **Parallel-ok:** yes (with Task 6, after Task 5).

### [ ] 8. Inventory logic tests + standalone live-DB verification script
- **Files:** `backend/tests/syerp/test_inventory.py` (pytest, mirrors `test_partners.py`);
  `backend/scripts/verify_inventory.py` (new standalone `asyncio.run` script).
- **Do:** pytest covers item-code generator boundary (pure), `compute_new_moving_avg` (pure),
  on-hand derivation, negative-stock rejection, transfer-nets-to-zero (live-DB — will skip under the
  broken harness, that's expected/documented). The **standalone script** builds its own async engine
  from `POSTGRES_*` env (does NOT use the broken conftest fixtures), then: creates item+2 locations,
  receives 10@2 then 10@4 (asserts avg 3.0), reads on-hand/value, posts a rejected negative
  adjustment, a valid transfer, prints PASS/FAIL per assertion and exits non-zero on any failure.
- **Done when:** `python backend/scripts/verify_inventory.py` prints all-PASS against live Postgres;
  the pure-Decimal unit tests pass under plain `pytest` (they need no DB).
- **Verify:** run the script against the dev DB; run `cd backend && pytest tests/syerp/test_inventory.py -k "moving_avg or generator"` (the no-DB subset must be green).
- **Parallel-ok:** no (validates Tasks 2–7; gates Wave C receiving).

### WAVE B — Inventory UI (SYERP-10)

### [ ] 9. Inventory Items screen (list + ItemSheet + archive) with route & nav
- **Files:** `frontend/src/routes/syerp/InventoryItems.tsx`,
  `components/InventoryItemSheet.tsx`, reuse `components/PartnerArchiveDialog.tsx` pattern into
  `components/ItemArchiveDialog.tsx`; add tab in `components/SyerpNav.tsx`; route in
  `frontend/src/App.tsx` (`/syerp/inventory/items`); `InventoryItems.test.tsx`.
- **Do:** Copy `Vendors.tsx` structure exactly (debounced server search, Show-archived switch,
  create/edit/archive/restore via TanStack Query mutations against `/api/v1/syerp/inventory/items`).
  ItemSheet fields: name, code (auto/optional), unit_of_measure, **optional PLUM part link** — a
  `Select` populated from `GET /api/v1/plum/parts` that stays fully usable when empty (PLUM disabled
  → no link). Query key `['syerp','inventory','items',{q,includeArchived}]`.
- **Done when:** items CRUD works in-browser incl. optional part link; archived hidden by default;
  colocated Vitest passes.
- **Verify:** `cd frontend && npm run test -- InventoryItems && npm run build` (tsc clean).
- **Parallel-ok:** yes (with Task 10).

### [ ] 10. Stock Locations screen (list + LocationSheet + archive) with route & nav
- **Files:** `frontend/src/routes/syerp/StockLocations.tsx`,
  `components/StockLocationSheet.tsx`; SyerpNav tab; route `/syerp/inventory/locations` in
  `App.tsx`; `StockLocations.test.tsx`.
- **Do:** Simplest Partner-template clone (name only + active); mutations against
  `/api/v1/syerp/inventory/locations`.
- **Done when:** location CRUD + archive works in-browser; Vitest passes.
- **Verify:** `npm run test -- StockLocations && npm run build`.
- **Parallel-ok:** yes (with Task 9).

### [ ] 11. Item detail: on-hand-by-location + valuation + transaction history
- **Files:** `frontend/src/routes/syerp/InventoryItemDetail.tsx`; route
  `/syerp/inventory/items/:id` in `App.tsx`; row/name link from `InventoryItems.tsx`;
  `InventoryItemDetail.test.tsx`.
- **Do:** Fetch `GET …/items/{id}/onhand` → table of location | qty; show total qty, moving-avg
  cost, and on-hand value (AC10-3,5). Below it, a read-only ledger table from
  `GET …/items/{id}/transactions` (add that read endpoint in Task 4's file if not present — thin
  list of txns, `syerp:read`) showing type/qty/unit_cost/location/timestamp/reason (AC10-4). Buttons
  "Adjust Stock" and "Transfer Stock" open the Task 12/13 dialogs.
- **Done when:** detail renders per-location on-hand, value, and immutable history; Vitest passes.
- **Verify:** `npm run test -- InventoryItemDetail && npm run build`.
- **Parallel-ok:** no (hosts Tasks 12–13; needs Tasks 9 & 4).

### [ ] 12. Stock Adjustment dialog
- **Files:** `frontend/src/routes/syerp/components/StockAdjustDialog.tsx`; wired from
  `InventoryItemDetail.tsx`; `StockAdjustDialog.test.tsx`.
- **Do:** Fields: location Select, signed quantity, **required** reason. POST to
  `…/items/{id}/adjustments`; on 4xx negative-stock error surface a `toast.error` with the server
  detail; on success invalidate the on-hand + transactions queries (AC10-6).
- **Done when:** posting an adjustment updates the detail view; a negative-driving adjustment shows
  the rejection toast and changes nothing; Vitest passes.
- **Verify:** `npm run test -- StockAdjustDialog && npm run build`.
- **Parallel-ok:** yes (with Task 13).

### [ ] 13. Stock Transfer dialog
- **Files:** `frontend/src/routes/syerp/components/StockTransferDialog.tsx`; wired from
  `InventoryItemDetail.tsx`; `StockTransferDialog.test.tsx`.
- **Do:** Fields: from-location, to-location, quantity. POST to `…/items/{id}/transfers`; block
  from==to client-side; surface server 4xx (over-draw) as `toast.error`; invalidate on-hand +
  transactions on success (AC10-6).
- **Done when:** a transfer moves qty between locations in the detail view; over-draw shows the
  rejection toast; Vitest passes.
- **Verify:** `npm run test -- StockTransferDialog && npm run build`.
- **Parallel-ok:** yes (with Task 12).

### WAVE C — Purchasing backend (SYERP-11)

### [ ] 14. Create the purchasing schema (migration 0008 + ORM models)
- **Files:** `backend/alembic/versions/0008_syerp_purchasing.py` (chains `→0007`);
  `backend/app/modules/syerp/models.py` (append two classes).
- **Do:**
  - `syerp_purchase_order` — `id` String(36) uuid PK; `po_number` String(20) unique+index;
    `vendor_id` String(36) FK→`syerp_partner.id` index; `status` String(30)
    (`draft|approved|partially_received|received|closed`) default `draft`; `notes` Text nullable;
    `approved_at` DateTime nullable; `approved_by` String(36) nullable (D-P8-10 approver identity);
    timestamps.
  - `syerp_purchase_order_line` — `id` String(36) uuid PK; `po_id` FK→PO index; `item_id`
    FK→`syerp_inventory_item.id`; `line_no` Integer; `qty_ordered` Numeric(18,6); `unit_cost`
    Numeric(18,6); `qty_received` Numeric(18,6) default 0 (Decision 5 accumulator);
    `need_by_date` Date nullable.
  - Hand-author DDL per `0004` template.
- **Done when:** `alembic upgrade head` creates both tables; downgrade/upgrade round-trips clean.
- **Verify:** `cd backend && alembic upgrade head` then `alembic downgrade -1 && alembic upgrade head`
  against dev Postgres; models import clean.
- **Parallel-ok:** no (foundation for Wave C).

### [ ] 15. PO draft CRUD + numeric-safe PO-number generator + vendor-only guard
- **Files:** `service.py` (`generate_po_number`, `create_po`, `list_pos`, `get_po`, `add_line`,
  `update_line`, `remove_line` — line mutations allowed **only while `status=='draft'`**);
  `schemas.py` (`POCreate`, `POLineCreate/Update`, `PORead`, `POLineRead`); `router.py`
  (`/syerp/purchasing/orders` GET list (+`?vendor_id=` filter)/POST/GET-one, and
  `…/orders/{id}/lines` POST/PATCH/DELETE).
- **Do:** `generate_po_number` copies the numeric-safe pattern (regex `^PO-[0-9]+$`, cast substring
  after `PO-`) + retry-once collision handling. `create_po` requires a `vendor_id` whose Partner has
  `is_vendor==True` else 4xx (AC11-3). Line add/edit/remove reject with 4xx when PO not `draft`
  (AC11-1). RBAC `syerp:write`; audit `po.created`, `po.line_added|updated|removed` (AC11-7,8).
- **Done when:** create PO auto-numbers `PO-####`; lines editable only in Draft; non-vendor partner
  rejected; audit rows written.
- **Verify:** `backend/scripts/verify_purchasing.py` (Task 19) covers it; pure-unit PO-number
  boundary test in `backend/tests/syerp/test_purchasing.py`.
- **Parallel-ok:** no (Tasks 16–18 depend on it).

### [ ] 16. PO FSM transitions (approve / close) with server-side rejection
- **Files:** `service.py` (`PO_TRANSITIONS` table + `advance_po_status(db, po_id, target, actor_id)`
  mirroring `plum` `VALID_TRANSITIONS`/`advance_revision_status`); `router.py`
  (`POST …/orders/{id}/approve`, `POST …/orders/{id}/close`, both `syerp:write`).
- **Do:** Transition table: `draft→approved`, `approved→(partially_received|received|closed)`,
  `partially_received→(received|closed)`, `received→closed`, `closed→[]`. **Approve** locks line
  qty/cost edits (enforced already by Task 15's draft-only guard) and stamps
  `approved_at`/`approved_by` (D-P8-10 — same `syerp:write`, identity via audit). Invalid transition
  → 4xx from the service (AC11-1). Audit `po.approved`, `po.closed` (AC11-7).
- **Done when:** approve moves draft→approved and stamps approver; close works from allowed states;
  every illegal transition (e.g. approve an already-approved PO, edit a line post-approve) → 4xx.
- **Verify:** `verify_purchasing.py` walks legal + several illegal transitions asserting status codes.
- **Parallel-ok:** yes (with Task 18, after Task 15).

### [ ] 17. PO receiving → inventory receipt (over-receipt reject + status roll-up)
- **Files:** `service.py` (`receive_line(db, po_id, line_id, location_id, qty, actor_id)`);
  `schemas.py` (`ReceiveLine`); `router.py` (`POST …/orders/{id}/lines/{line_id}/receive`,
  `syerp:write`).
- **Do:** Allowed only when PO is `approved` or `partially_received` (else 4xx). Reject `qty<=0` and
  **over-receipt** (`qty_received + qty > qty_ordered`) → 4xx (AC11-4, D-P8-7). On success, call
  Task-5 `post_receipt(item_id, location_id, qty, unit_cost=line.unit_cost, actor_id,
  source_type='po_receipt', source_id=line.id)` — feeding SYERP-10 on-hand + moving-average
  (AC11-4) — increment `line.qty_received`, then recompute PO status: `received` when every line
  fully received, else `partially_received` (AC11-5), all in one transaction. Audit `po.received`
  (with qty + location detail).
- **Done when:** receiving a line posts a real inventory receipt txn at the PO unit cost, bumps
  on-hand + moving-avg, accumulates partial receipts, auto-advances PO status, and rejects
  over-receipt with 4xx.
- **Verify:** the cross-requirement integration is proven end-to-end in `verify_purchasing.py`
  (Task 19) and Task 20 — NOT by the broken pytest harness.
- **Parallel-ok:** no (the crux; needs Tasks 5, 15, 16).

### [ ] 18. Vendor purchase-history read
- **Files:** `service.py` (extend `list_pos` to accept `vendor_id`; compute per-PO total =
  `SUM(line.qty_ordered*line.unit_cost)`); `schemas.py` (`PORead` includes `total` + received
  roll-up); `router.py` (the `?vendor_id=` list already from Task 15 — ensure totals+status returned).
- **Do:** Return, for a vendor, the list of their POs with status and totals (AC11-3). Include per-PO
  ordered/received/outstanding roll-up so the UI status table (AC11-5) has its numbers.
- **Done when:** `GET …/orders?vendor_id=X` returns that vendor's POs with status + total value +
  received roll-up; `syerp:read`.
- **Verify:** `verify_purchasing.py` asserts the vendor filter returns only that vendor's POs with
  correct totals.
- **Parallel-ok:** yes (with Task 16, after Task 15).

### [ ] 19. Purchasing logic tests + standalone live-DB verification script
- **Files:** `backend/tests/syerp/test_purchasing.py`; `backend/scripts/verify_purchasing.py`.
- **Do:** pytest covers PO-number boundary (pure), FSM rejection, vendor-only guard, partial-receipt
  accumulation, over-receipt rejection, and receipt-creates-inventory-txn (live-DB — skips under
  broken harness). The standalone script (own async engine): create vendor + item + location →
  create PO → add line (qty 10 @ 5) → approve → receive 4 (assert status `partially_received`, item
  on-hand +4, moving-avg reflects 5) → attempt receive 10 (assert 4xx over-receipt) → receive 6
  (assert status `received`) → assert vendor history lists the PO with total 50. Exit non-zero on any
  failed assertion.
- **Done when:** `python backend/scripts/verify_purchasing.py` prints all-PASS against live Postgres;
  no-DB unit subset passes under plain pytest.
- **Verify:** run the script against dev DB;
  `cd backend && pytest tests/syerp/test_purchasing.py -k "po_number or fsm" ` (no-DB subset green).
- **Parallel-ok:** no (validates Tasks 15–18).

### WAVE D — Purchasing UI (SYERP-11)

### [ ] 20. PO list screen (status + totals, vendor filter) with route & nav
- **Files:** `frontend/src/routes/syerp/PurchaseOrders.tsx`; SyerpNav tab; route
  `/syerp/purchasing/orders` in `App.tsx`; `PurchaseOrders.test.tsx`.
- **Do:** Table: PO number | vendor | status badge | total | created. `?vendor_id=` filter Select.
  "Create PO" button → Task 21. Status badge colors per state (AC11-5).
- **Done when:** list renders POs with status + total; vendor filter narrows to one vendor's history
  (AC11-3); Vitest passes.
- **Verify:** `npm run test -- PurchaseOrders && npm run build`.
- **Parallel-ok:** yes (with Task 23, after backend Wave C).

### [ ] 21. PO create / draft-edit screen (vendor picker + line editor)
- **Files:** `frontend/src/routes/syerp/PurchaseOrderCreate.tsx` (or a Sheet); route
  `/syerp/purchasing/orders/new`; `PurchaseOrderCreate.test.tsx`.
- **Do:** Vendor Select populated from `GET /api/v1/syerp/partners?role=vendor` (vendor-only,
  AC11-3). Line editor rows: item Select (from inventory items), qty ordered, unit cost, optional
  need-by date. POST PO then lines. Editing lines available only while Draft (AC11-1).
- **Done when:** a Draft PO with lines can be created in-browser from vendor+items; Vitest passes.
- **Verify:** `npm run test -- PurchaseOrderCreate && npm run build`.
- **Parallel-ok:** yes (with Task 22).

### [ ] 22. PO detail screen (roll-up + approve/close actions)
- **Files:** `frontend/src/routes/syerp/PurchaseOrderDetail.tsx`; route
  `/syerp/purchasing/orders/:id`; `PurchaseOrderDetail.test.tsx`.
- **Do:** Header shows PO number/vendor/status. Lines table: item | ordered | received | outstanding
  (AC11-5). "Approve" (Draft only) and "Close" buttons POST to the FSM endpoints; disable/hide by
  status; surface 4xx as toast. "Receive" per line → Task 23 dialog (visible only when
  approved/partially_received).
- **Done when:** approve/close drive status live; roll-up columns render; illegal actions are
  unavailable in UI and rejected by server if forced; Vitest passes.
- **Verify:** `npm run test -- PurchaseOrderDetail && npm run build`.
- **Parallel-ok:** yes (with Task 21).

### [ ] 23. Receiving dialog (per-line qty + location picker)
- **Files:** `frontend/src/routes/syerp/components/ReceiveLineDialog.tsx`; wired from
  `PurchaseOrderDetail.tsx`; `ReceiveLineDialog.test.tsx`.
- **Do:** Fields: receive qty (default = outstanding), location Select (from stock locations). POST
  to `…/lines/{line_id}/receive`; on success invalidate PO detail + list + (if open) the item
  on-hand queries; surface over-receipt 4xx as `toast.error` (AC11-4).
- **Done when:** receiving from the dialog updates the PO roll-up and status; over-receipt shows the
  rejection toast; Vitest passes.
- **Verify:** `npm run test -- ReceiveLineDialog && npm run build`.
- **Parallel-ok:** no (needs Task 22).

### WAVE E — Verify

### [ ] 24. End-to-end live integration proof (receipt → on-hand → moving-average)
- **Files:** `backend/scripts/verify_e2e_p8.py` (may compose the Task 8 + Task 19 scripts).
- **Do:** Against a **freshly-migrated** live Postgres (`alembic upgrade head` from empty), run the
  full D-P8-8 cross-requirement flow: create item + `Main` location + vendor → PO → approve →
  partial receive → remainder → assert item on-hand and moving-average updated exactly, vendor
  history lists the PO. This is the single most important proof and does NOT rely on the broken
  pytest harness.
- **Done when:** the script exits 0 with every assertion PASS on a fresh DB.
- **Verify:** `podman-compose -f compose/compose.yml -f compose/compose.dev.yml up -d db` →
  `cd backend && alembic upgrade head && python scripts/verify_e2e_p8.py`.
- **Parallel-ok:** no (final gate; needs all of A–D).

### [ ] 25. Update requirement statuses, progress, and UAT checklist
- **Files:** `.zj/SRD.md` (SYERP-10, SYERP-11 → implemented/partial with evidence);
  `docs/features/requirements-progress.md`; the milestone UAT doc (append SYERP-10/11 human-verify
  checks mirroring `.zj/UAT-v1.0.md` style); `docs/tasks/{branch}.md` checklist finalized/archived.
- **Do:** Record evidence (files, migrations 0007/0008, the two verify scripts) and cite D-P8-8/9/10.
  Flag that flow-level UI confirmation lands via the milestone UAT (per the D-P7-5 precedent).
- **Done when:** SRD + progress reflect verified reality; UAT checklist has runnable SYERP-10/11
  steps; task checklist archived per CLAUDE.md.
- **Verify:** docs cross-reference the shipped files/migrations; `grep` confirms SYERP-10/11 no
  longer read `Status: planned`.
- **Parallel-ok:** no (last).

---

## Risks
- **The receipt→moving-average→on-hand integration (Task 17) is the crux, and the broken pytest
  harness (D-P7-4) cannot verify it.** Early-warning: if `verify_inventory.py` (Task 8) can't stand
  up its own async engine against live Postgres, the whole verification strategy stalls — build and
  run that script *before* Wave C so the pattern is proven early.
- **Moving-average as a mutated column (Decision 4) vs the "on-hand is derived" rule.** If the owner
  rejects the stored column, Tasks 1/5 change shape (ledger-replay). Resolve Decision 4 before Task 1.
- **`Decimal` division rounding** in the moving-average (Task 5): non-terminating quotients (e.g.
  /3) must use a fixed quantize/context to stay deterministic at scale 6 — assert exact values in the
  pure unit tests; drift there is the early sign.
- **Concurrent receipts** could race the moving-average read-modify-write. v2.0 is single-shop, low
  concurrency; note as accepted, revisit if it surfaces. Early-warning: divergent on-hand vs
  `SUM(quantity)` in the ledger.

## Out of scope (deferred — do not build)
- AP: vendor invoices, three-way match, payments (SYERP-12, D-P8-5).
- Warehouse bins/zones/hierarchy, lot/serial (GELATO, D-P8-3).
- Negative stock / backorder tolerance; over-receipt tolerance (D-P8-7 — reject in v2.0).
- A user-facing `issue` transaction type/screen — reserved for MOUSSE; negative adjustment covers
  manual write-offs in v2.0.
- Offline/Service-Worker support for these screens (NFR-3, standing cross-module concern).

## Mapping: acceptance criterion → task(s)

| SRD criterion | Tasks |
|---|---|
| SYERP-10.1 Item master (+ numeric-safe code) | 1, 2, 9 |
| SYERP-10.2 Flat locations | 1, 3, 10 |
| SYERP-10.3 On-hand by location (derived) | 1, 4, 11 |
| SYERP-10.4 Immutable transactions | 1, 5, 6, 7, 11 |
| SYERP-10.5 Moving-average valuation | 1, 4, 5, 8, 11 |
| SYERP-10.6 Adjustment & transfer + negative reject | 6, 7, 12, 13 |
| SYERP-10.7 Audit | 2, 3, 5, 6, 7 |
| SYERP-10.8 RBAC | 2, 3, 4, 5, 6, 7 |
| SYERP-11.1 PO lifecycle FSM | 15, 16, 21, 22 |
| SYERP-11.2 Numeric PO numbering | 15, 19 |
| SYERP-11.3 Vendor link & history | 15, 18, 20, 21 |
| SYERP-11.4 Receiving → inventory | 17, 19, 23, 24 |
| SYERP-11.5 Status roll-up | 17, 18, 20, 22 |
| SYERP-11.6 No AP | (scope — Out of scope; confirmed by 19, 24) |
| SYERP-11.7 Audit | 15, 16, 17 |
| SYERP-11.8 RBAC | 15, 16, 17, 18 |
