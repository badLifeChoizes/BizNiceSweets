# Plan: Phase 10 — MOUSSE manufacturing execution core (materials-only)
Goal: A shop can create, release, issue components to, and complete a work order that consumes a PLUM BOM and SYERP inventory to produce a finished good, with material cost flowing through a WIP clearing account that returns to zero — closing the v2.0 "execute work orders that consume PLUM BOMs and inventory" DoD.
Status: draft

## Success criteria
Implements requirement **MOUSSE-01** (materials-only slice). Every task below cites MOUSSE-01.
- **SC1** — WO create + single-level BOM snapshot at release + FSM Draft→Released→In Progress→(On Hold⇄In Progress)→Completed (+Cancelled from Draft/Released), enforced server-side; no-Released-revision → 4xx; component with no linked InventoryItem → reject at release 4xx (D-P10-7).
- **SC1b** — Pause/resume: an In-Progress WO can be put On Hold and resumed back to In Progress (D-P10-9); illegal pause/resume transitions → 4xx.
- **SC2** — Explicit component issue posts signed `issue` InventoryTxn rows (negative qty, `source_type="mousse_work_order"`, `source_id=wo.id`) at each item's `moving_avg_cost`, floor-guarded, atomically with one balanced JE **Dr 1140 / Cr 1130**; first issue → In Progress; audit row.
- **SC3** — Completion receives planned output qty at accumulated-WIP unit cost, atomically with balanced JE **Dr 1130 / Cr 1140**, so the WO's 1140 balance returns to its pre-WO value (Decimal-exact pre/post equality); uses `post_receipt(commit=False)`; audit row. **Completion is rejected 4xx if any component is under-issued (issued < qty_required) unless `override_incomplete=true` is passed — the override is audited** (D-P10-9).
- **SC4** — Regression: `verify_inventory`, `verify_purchasing`, `verify_e2e_p8`, `verify_gl`, `verify_ap`, `verify_reports` still exit 0; trial balance nets zero.
- **SC5** — Two concurrent issues (`asyncio.gather`) cannot drive on-hand negative / double-consume / corrupt WIP; contended rows `SELECT … FOR UPDATE` in sorted-id order.
- **SC6** — Every WO mutation writes an attributable audit row and enforces `mousse:write` (403/401/200), proven at HTTP level.
- **SC7** — Frontend: WO list, create dialog, detail (snapshot lines + on-hand + issued-so-far), Issue action, Complete action; TanStack Query invalidation; Vitest; nav gated on MOUSSE enabled ∩ `mousse:read`.

## Context
Live stack: FastAPI + async SQLAlchemy 2.0 + Alembic + Postgres 17 backend; React 19 + TanStack Query + Vitest frontend. New module `backend/app/modules/mousse/` follows the SYERP package shape exactly.

Verified integration surfaces (do not re-derive — plan against these):
- `backend/app/modules/syerp/service.py`
  - `post_receipt(db, item_id, location_id, qty, unit_cost, actor_id, source_type=None, source_id=None, commit=True)` (:943) — recomputes item moving_avg; use `commit=False` for FG receipt.
  - `post_journal_entry(db, *, entry_date, memo, lines, actor_id, source_type=None, source_id=None, commit=True)` (:2078) — lines are mappings `{"account_id": int, "debit": Decimal}` / `{..., "credit": Decimal}`, exactly one side each; `_je_is_balanced` requires ≥2 lines and Σdr==Σcr at scale-6 else 422; `commit=False` flushes for atomic batching.
  - `_adjustment_violates_floor(current_loc_onhand, qty_delta) -> bool` (:1060) — pure per-location floor predicate; reuse for the issue guard.
  - `_gl_account_id_by_code(db, code) -> int` (:1825) — resolve "1130"/"1140"; raises 500 if unseeded.
  - `derive_account_balance(db, account_id) -> Decimal` (:2326), `get_account_register` (:2349) — WIP pre/post assertion.
  - `_COST_QUANTUM = Decimal("0.000001")` (:808), `ROUND_HALF_UP` — quantize the FG unit cost the same way `compute_new_moving_avg` does.
  - Row-lock template: `create_bill` (:2732-2740) — `select(Model.id).where(...).with_for_update()` in sorted-id order, lock before the read-then-write guard, hold to the single `db.commit()`.
- `backend/app/modules/syerp/models.py` — `InventoryTxn` (:240): `item_id, location_id, txn_type, quantity (signed Numeric18,6), unit_cost (nullable), actor_id (str), source_type/source_id (soft link)`; on-hand is DERIVED (`SUM(quantity)`), per-location = SUM at that location. `InventoryItem` (:153): `id (str uuid), moving_avg_cost, plum_part_id (nullable FK)`.
- CoA already seeded (`coa_seed.py`): **1130 Inventory**, **1140 Work in Process** (unused — MOUSSE owns it). No new accounts.
- `backend/app/modules/plum/service.py` — `get_released_revision(db, part_id) -> Revision|None` (:656); direct BOM = `PlumBomItem` rows (models.py:236) with `parent_revision_id == released_rev.id` (`child_part_id`, `qty`, `sort_order`). `load_bom_tree(db, part_id, revision_id)` (:1334) level-0 nodes = direct children — take level-0 OR query `PlumBomItem` directly. **Do NOT use `load_flat_bom` (:1406)** — multi-level, violates D-P10-5.
- RBAC: `from app.modules.auth.dependencies import require_permission`; `Depends(require_permission("mousse:write"))`. Permissions seeded in `backend/app/modules/auth/seed.py` (`_PERMISSIONS` list `("code","desc")`, `_USER_ROLE_PERMS` set); admin gets all codes automatically.
- Audit: `from app.modules.auth.service import write_audit`; `await write_audit(db, actor_id=str(current_user.id), action="work_order.released", target_type="work_order", target_id=wo.id, detail=...)`. NOTE: `write_audit` itself calls `db.commit()` — call it AFTER the service mutation's own commit (matches the syerp router order).
- Registration: `mousse/__init__.py` calls `registry.register(sys.modules[__name__])`; add `importlib.import_module("app.modules.mousse")` in `backend/app/main.py` (after plum). Module `mousse` is ALREADY seeded in `backend/app/core/modules_seed.py` (:27, key "mousse", enabled default) — no modules-table change.
- Alembic head is **0011** (`backend/alembic/versions/0011_syerp_bill_date.py`); add **0012**. Tables prefixed `mousse_`.
- Verify scripts: `backend/scripts/verify_*.py`, run against live Postgres (pytest live-DB harness is broken — do NOT rely on pytest for the crux). Model on `verify_reports.py` (service) + `verify_reports_api.py` (HTTP, stdlib urllib, throwaway users/roles, cleanup in `finally`). In-container: `PYTHONPATH=/app`.
- Frontend: mirror `frontend/src/routes/syerp/` — screens + `components/` subfolder, TanStack Query hooks, single axios client `src/api/client.ts`, Vitest + Testing Library. Sub-nav via a `MousseNav.tsx` copying `routes/syerp/components/SyerpNav.tsx`. Sidebar (`src/components/Sidebar.tsx`) renders one NavLink per visible `ModuleRecord` at `/${mod.key}` — `/mousse` appears once the module is enabled; add the `/mousse` route + redirect in `frontend/src/App.tsx`. No shadcn tabs primitive (SyerpNav uses NavLink strip; 09c used a Button toggle group).

## Decisions
These are settled (D-P10-1..8, in `.zj/DECISIONS.md`) — honor, do not re-litigate:
- **D-P10-1** materials-only; routing/work-centers/labor/overhead/shop-floor deferred.
- **D-P10-2** actual moving-average costing; WIP **1140** clears to zero; no variance account.
- **D-P10-3** explicit issue action distinct from completion; `txn_type="issue"`.
- **D-P10-4** the `syerp/service.py` split + MAP refresh are a SEPARATE prior chore branch — NOT in this plan; MOUSSE imports SYERP service functions by their current names.
- **D-P10-6** new `backend/app/modules/mousse/`, self-registered, prefix `/mousse`, RBAC `mousse:read`/`mousse:write`.
- **D-P10-7** component with no linked InventoryItem → reject at WO release 4xx.
- **D-P10-8** branch `feature-mousse-work-orders` off tag `zj/good-09c-ap-aging-financial-statements` — cut first.
- **D-P10-9 (owner-resolved at handoff):** WO **completion requires every component fully issued (issued ≥ qty_required)** UNLESS an explicit **`override_incomplete=true`** is passed, which is **audited** (FG still valued at accumulated WIP, WIP still clears exactly). The FSM gains an **On Hold** state — an In-Progress WO can be paused (In Progress→On Hold) and resumed (On Hold→In Progress).

**Owner-confirmed at handoff (were flagged):**
- **D-P10-5 (single-level BOM) — CONFIRMED.** The WO snapshots only the Released revision's DIRECT children (`PlumBomItem` at `parent_revision_id`), NOT a multi-level leaf explosion. Sub-assemblies are issued from stock as components.
- **Completion under/over-issue policy — RESOLVED (D-P10-9):** completion requires full issue by default, allowed on under-issued WOs only via the audited `override_incomplete` flag; plus On Hold pause/resume.

**Implementation decision (manager, not owner-facing):**
- **`mousse_work_order_issue` table:** kept (below) so issued-so-far is tracked per component and each issue links to its InventoryTxn + JE (audit/traceability posture). Alternative — deriving issued-so-far from InventoryTxn by `source_id` — is ambiguous when two components resolve to the same InventoryItem.

## Tasks

### [x] 1. Cut the build branch and open the task checklist
- **Files:** git; `docs/tasks/feature-mousse-work-orders.md`
- **Do:** From the verified 09c tip, `git checkout -b feature-mousse-work-orders zj/good-09c-ap-aging-financial-statements` (D-P10-8). Create the task checklist file listing tasks 2–20 (per CLAUDE.md task-workflow rule). Reference MOUSSE-01.
- **Done when:** branch exists off the tag; checklist file committed.
- **Verify:** `git branch --show-current` → `feature-mousse-work-orders`; `git merge-base --is-ancestor zj/good-09c-ap-aging-financial-statements HEAD && echo ok`.
- **Parallel-ok:** no (blocks everything)

### [x] 2. Define MOUSSE ORM models (WorkOrder, WorkOrderComponent, WorkOrderIssue)
- **Files:** `backend/app/modules/mousse/models.py`, `backend/app/modules/mousse/__init__.py` (stub package)
- **Do:** Import shared `Base` (`from app.core.db import Base`, matching syerp/models.py). Define (all tables prefixed `mousse_`, MOUSSE-01):
  - `WorkOrder` (`mousse_work_order`): `id` (str uuid PK, same default as InventoryItem), `wo_number` (str, unique, not null), `plum_part_id` (FK `plum_part.id`, not null), `released_revision_id` (FK `plum_part_revision.id`, nullable until release), `output_item_id` (FK `syerp_inventory_item.id`, nullable until release — the FG item resolved from the WO part), `planned_qty` (Numeric(18,6), not null, >0), `target_location_id` (FK `syerp_stock_location.id`, not null), `status` (str, not null, default `"draft"`), `wo_date` (Date, not null — single date basis for all this WO's JEs), `actor_id` (str), `created_at`, `completed_at` (nullable).
  - `WorkOrderComponent` (`mousse_work_order_component`): `id` (str uuid PK), `work_order_id` (FK `mousse_work_order.id`, not null), `child_part_id` (FK `plum_part.id`, not null), `item_id` (FK `syerp_inventory_item.id`, nullable — resolved at release), `qty_per` (Numeric(18,6)), `qty_required` (Numeric(18,6)), `unit_of_measure` (str), `sort_order` (int).
  - `WorkOrderIssue` (`mousse_work_order_issue`): `id` (str uuid PK), `work_order_id` FK, `component_id` (FK `mousse_work_order_component.id`), `item_id` FK, `location_id` FK, `quantity` (Numeric(18,6), positive magnitude issued), `unit_cost` (Numeric(18,6)), `inventory_txn_id` (int FK `syerp_inventory_txn.id`), `journal_entry_id` (str FK `syerp_journal_entry.id`), `actor_id` (str), `created_at`.
- **Done when:** `python -c "import app.modules.mousse.models"` imports clean; `Base.metadata.tables` includes the three `mousse_*` tables.
- **Verify:** `cd backend && python -c "import app.core.models; from app.modules.mousse import models; print([t for t in __import__('app.core.db',fromlist=['Base']).Base.metadata.tables if t.startswith('mousse_')])"`
- **Parallel-ok:** no (foundation)

### [ ] 3. Add Alembic migration 0012 for the MOUSSE tables
- **Files:** `backend/alembic/versions/0012_mousse_work_orders.py`
- **Do:** Hand-author revision `0012`, `down_revision="0011"` (follow the 0011 header/ABOUTME convention). `upgrade()` creates the three tables with the columns/FKs/constraints from task 2 (unique on `wo_number`; FKs to `plum_part`, `plum_part_revision`, `syerp_inventory_item`, `syerp_stock_location`, `syerp_inventory_txn`, `syerp_journal_entry`). `downgrade()` drops them in reverse FK order. MOUSSE-01.
- **Done when:** `alembic upgrade head` reaches 0012; `alembic downgrade -1` then `upgrade head` round-trips clean.
- **Verify:** `cd backend && alembic upgrade head && alembic current` shows 0012; then `alembic downgrade 0011 && alembic upgrade head`.
- **Parallel-ok:** no (depends on task 2)

### [x] 4. Seed `mousse:read` / `mousse:write` permissions
- **Files:** `backend/app/modules/auth/seed.py`
- **Do:** Add `("mousse:read", "Read access to MOUSSE (manufacturing execution)")` and `("mousse:write", "Write access to MOUSSE")` to `_PERMISSIONS`; add both to `_USER_ROLE_PERMS` (admin auto-gets all). Idempotent by existing upsert-by-code logic. MOUSSE-01/D-P10-6.
- **Done when:** after a seed run, `Permission` rows `mousse:read`/`mousse:write` exist and are attached to admin + user roles.
- **Verify:** restart stack (lifespan reseeds) then `SELECT code FROM auth_permission WHERE code LIKE 'mousse:%';` returns both rows.
- **Parallel-ok:** yes (independent of models)

### [ ] 5. Define MOUSSE Pydantic schemas
- **Files:** `backend/app/modules/mousse/schemas.py`
- **Do:** `WorkOrderCreate` (`plum_part_id`, `planned_qty` >0, `target_location_id`, optional `wo_date`), `WorkOrderComponentRead` (component fields + `item_id`, `qty_required`, and computed `on_hand`/`issued_so_far` populated by the service), `WorkOrderRead` (header + status + numbers), `WorkOrderDetailRead` (header + `components: list[WorkOrderComponentRead]`), `IssueComponentsRequest` (list of `{component_id, quantity, location_id?}` — location defaults to `target_location_id`), `IssueResultRead`, `WorkOrderCompleteRequest` (`override_incomplete: bool = False` — D-P10-9), `WorkOrderCompleteResult`. `WorkOrderComponentRead` exposes `issued_so_far` and `qty_required` so the UI can show under-issue. `status` values include `on_hold`. Decimal fields as `Decimal`. MOUSSE-01.
- **Done when:** `python -c "import app.modules.mousse.schemas"` clean; schemas validate a sample create payload.
- **Verify:** `cd backend && python -c "from app.modules.mousse.schemas import WorkOrderCreate; WorkOrderCreate(plum_part_id='x', planned_qty='10', target_location_id=1)"`
- **Parallel-ok:** yes (independent of service body)

### [ ] 6. Service — create work order, wo_number generation, list/get
- **Files:** `backend/app/modules/mousse/service.py`
- **Do:** `create_work_order(db, data, actor_id)` — validate `planned_qty>0` (422), resolve the PLUM part exists (404), create a `WorkOrder` in `status="draft"` with `wo_date` (default today), generate `wo_number` as zero-padded sequential (e.g. `WO-000001` from a count/max; note collision risk under concurrency — acceptable for draft creation, unique constraint is the backstop). `get_work_order(db, wo_id)` → 404 if missing; `list_work_orders(db, status=None)`. Detail loader assembles `WorkOrderDetailRead` with per-component `on_hand` (SUM InventoryTxn at target location) and `issued_so_far` (SUM `WorkOrderIssue.quantity` for the component). MOUSSE-01/SC1.
- **Done when:** `create_work_order` persists a Draft WO with a unique number; `get`/`list` return it.
- **Verify:** covered by verify_mousse.py (task 12); interim `python` REPL create+get round-trip against dev DB.
- **Parallel-ok:** no (depends on 2,5)

### [ ] 7. Service — FSM validator + release (BOM snapshot) + cancel + hold/resume
- **Files:** `backend/app/modules/mousse/service.py`
- **Do:** Pure `_validate_transition(current, target) -> bool` allowing Draft→Released, Released→In Progress, **In Progress→On Hold, On Hold→In Progress**, In Progress→Completed, Draft→Cancelled, Released→Cancelled; everything else illegal → caller raises 409/422. Statuses: `draft | released | in_progress | on_hold | completed | cancelled`. `release_work_order(db, wo_id, actor_id)`: require Draft (else 4xx); call `plum.get_released_revision(db, wo.plum_part_id)` → None ⇒ 4xx (SC1); resolve the WO's OUTPUT InventoryItem via `InventoryItem.plum_part_id == wo.plum_part_id` (nullable ⇒ 4xx — cannot receive FG); snapshot the DIRECT BOM (`PlumBomItem` where `parent_revision_id == released_rev.id`, or `load_bom_tree` level-0 — D-P10-5, NOT `load_flat_bom`) into `WorkOrderComponent` rows: `qty_per=bom.qty`, `qty_required=qty_per*planned_qty`, `unit_of_measure` from child revision, resolve `item_id` per child via `plum_part_id`; **if ANY component's child has no linked InventoryItem, reject the whole release 4xx (D-P10-7) — no partial snapshot**; set `released_revision_id`, `output_item_id`, `status="released"`, commit. `cancel_work_order(db, wo_id, actor_id)`: require Draft/Released, set `status="cancelled"`. **`hold_work_order(db, wo_id, actor_id)`: require In Progress (else 4xx), set `status="on_hold"`. `resume_work_order(db, wo_id, actor_id)`: require On Hold (else 4xx), set `status="in_progress"`** (D-P10-9). MOUSSE-01/SC1/SC1b.
- **Done when:** releasing a part with a Released rev + fully-linked BOM snapshots N component lines and moves to Released; no-released-rev and unlinked-component cases raise 4xx with nothing persisted; illegal transitions 4xx; hold from In Progress → On Hold and resume → In Progress; hold/resume from any other state 4xx.
- **Verify:** exercised by verify_mousse.py (task 12).
- **Parallel-ok:** no (depends on 6)

### [ ] 8. Service — issue components (row locks, floor guard, txn + JE, atomic)
- **Files:** `backend/app/modules/mousse/service.py`
- **Do:** `issue_components(db, wo_id, request, actor_id)`: require status Released or In Progress (else 4xx). **Lock the contended rows FOR UPDATE in sorted-id order BEFORE the guard read** (SC5, copy create_bill template): lock each target `InventoryItem` row (or a deterministic per-item/location key) for the components being issued, sorted by id. For each requested component: read per-location on-hand (SUM InventoryTxn at location); apply `_adjustment_violates_floor(on_hand, -qty)` → insufficient ⇒ 4xx, nothing persists. Post one signed `issue` InventoryTxn per component (`quantity = -qty`, `unit_cost = item.moving_avg_cost`, `txn_type="issue"`, `source_type="mousse_work_order"`, `source_id=wo.id`, `actor_id`) — add directly (do NOT call `post_adjustment`: it lacks `commit` and doesn't value at moving_avg). Accumulate total issued value = Σ(qty × moving_avg, quantized `_COST_QUANTUM`). Post ONE balanced JE via `post_journal_entry(commit=False)`: **Dr 1140 WIP / Cr 1130 Inventory** for the total, `entry_date=wo.wo_date`, `source_type="mousse_work_order"`, `source_id=wo.id`. Write a `WorkOrderIssue` row per component linking its txn + the JE. If status was Released, set In Progress. Single `db.commit()` at the end (all-or-nothing). MOUSSE-01/SC2.
- **Done when:** issuing decrements on-hand, posts one Dr1140/Cr1130 JE equal to Σ(qty×moving_avg), moves WO to In Progress on first issue, writes issue rows; insufficient-stock request 4xx with zero rows written.
- **Verify:** verify_mousse.py (task 12) + concurrency (task 13).
- **Parallel-ok:** no (depends on 7)

### [ ] 9. Service — complete work order (WIP clears to zero, FG receipt)
- **Files:** `backend/app/modules/mousse/service.py`
- **Do:** `complete_work_order(db, wo_id, actor_id, override_incomplete=False)`: require In Progress (else 4xx). **Under-issue guard (D-P10-9): if ANY component has `issued_so_far < qty_required`, reject 4xx UNLESS `override_incomplete=True`; when overridden, the audit detail (task 10) records `override_incomplete=true` + which components were short.** Compute accumulated WIP = Σ of this WO's 1140 DEBITS attributable to the WO (sum `WorkOrderIssue.quantity*unit_cost`, or the 1140 debits from `get_account_register` filtered by `source_id=wo.id` — use the same basis consistently). `fg_unit_cost = (accumulated_wip / planned_qty).quantize(_COST_QUANTUM, ROUND_HALF_UP)`. Receive FG via `post_receipt(db, wo.output_item_id, wo.target_location_id, planned_qty, fg_unit_cost, actor_id, source_type="mousse_work_order", source_id=wo.id, commit=False)` (updates FG moving_avg). Post ONE balanced JE `post_journal_entry(commit=False)`: **Dr 1130 Inventory / Cr 1140 WIP** for `planned_qty*fg_unit_cost`, `entry_date=wo.wo_date`, `source_id=wo.id`. Make the Cr-1140 amount equal the total WIP debits BY CONSTRUCTION so 1140-attributable balance returns to pre-WO exactly (SC3 — if a rounding residual appears from the divide, credit the exact accumulated WIP and receive at `accumulated_wip/planned_qty`; the receipt value must equal the WIP credit — do NOT loosen an assert). Set `status="completed"`, `completed_at`. Single `db.commit()`. MOUSSE-01/SC3/D-P10-2.
- **Done when:** completing a fully-issued In-Progress WO receives planned_qty of FG at accumulated-WIP unit cost, posts Dr1130/Cr1140, and the WO's 1140-attributable balance equals its pre-WO value Decimal-exactly; an under-issued WO is rejected 4xx without override and completes (audited) with `override_incomplete=True`.
- **Verify:** verify_mousse.py WIP pre/post equality + under-issue guard assertions (task 12).
- **Parallel-ok:** no (depends on 8)

### [ ] 10. Router — endpoints with RBAC + audit
- **Files:** `backend/app/modules/mousse/router.py`
- **Do:** `APIRouter()` (no prefix — `mount_all` adds `/api/v1`; module tag adds nothing — put paths under `/mousse/...`). Endpoints (mirror syerp router style, `current_user=Depends(require_permission(...))`, `actor_id=str(current_user.id)`, `write_audit` AFTER the service commit): `GET /mousse/work-orders` (read), `POST /mousse/work-orders` (write → `work_order.created`), `GET /mousse/work-orders/{id}` (read, returns detail with on-hand/issued), `POST /mousse/work-orders/{id}/release` (write → `work_order.released`), `POST /mousse/work-orders/{id}/issue` (write → `work_order.issued`), `POST /mousse/work-orders/{id}/hold` (write → `work_order.held`), `POST /mousse/work-orders/{id}/resume` (write → `work_order.resumed`), `POST /mousse/work-orders/{id}/complete` (write → `work_order.completed`; body carries `override_incomplete: bool = False`, threaded to the service; audit detail records the override + short components when true — D-P10-9), `POST /mousse/work-orders/{id}/cancel` (write → `work_order.cancelled`). Reads use `mousse:read`, mutations `mousse:write`. MOUSSE-01/SC1b/SC6.
- **Done when:** router imports clean and exposes the nine routes; write routes gated `mousse:write`, reads `mousse:read`.
- **Verify:** `cd backend && python -c "from app.modules.mousse.router import router; print([r.path for r in router.routes])"`
- **Parallel-ok:** no (depends on 6–9)

### [ ] 11. Register the MOUSSE module + wire nothing else to break
- **Files:** `backend/app/modules/mousse/__init__.py`, `backend/app/main.py`
- **Do:** `__init__.py`: `MODULE_NAME = "mousse"`, `from app.modules.mousse.router import router`, `registry.register(sys.modules[__name__])` (copy plum/__init__.py). In `main.py` add `importlib.import_module("app.modules.mousse")` after the plum import. (Permissions seed already wired via task 4 into `auth/seed.py`; modules table already has `mousse`.) MOUSSE-01/D-P10-6.
- **Done when:** app boots with mousse mounted; `GET /api/v1/mousse/work-orders` responds (200 with token / 401 without).
- **Verify:** boot stack; `curl -s localhost:8000/openapi.json | grep -c '/mousse/'` > 0.
- **Parallel-ok:** no (depends on 10)

### [ ] 12. Write `verify_mousse.py` (service-level lifecycle + WIP-clears-to-zero + rejects)
- **Files:** `backend/scripts/verify_mousse.py`
- **Do:** Model on `verify_reports.py` (owns its own async engine + DSN from POSTGRES_* env). Build a fixture: a PLUM part with a Released revision whose direct BOM has ≥2 children, each linked to an InventoryItem with on-hand stock; a linked FG InventoryItem for the parent; a target location. Assert full happy path: create → release (snapshot line count, qty_required math), **snapshot the WO's 1140-attributable balance**, issue all components (on-hand decrements, JE Dr1140/Cr1130 = Σ qty×moving_avg, status→In Progress), complete (FG received at accumulated-WIP unit cost, FG moving_avg updated), **assert the WO's 1140-attributable balance == the pre-WO snapshot Decimal-exactly** (SC3). Negative cases: part with no Released rev → 4xx; BOM child with no linked InventoryItem → release 4xx (D-P10-7); issue beyond on-hand → 4xx, nothing persisted; illegal FSM transitions → 4xx. **Hold/resume (SC1b): In Progress→hold→On Hold, resume→In Progress; hold/resume from wrong state → 4xx. Under-issue completion (D-P10-9): completing an under-issued WO without override → 4xx; with `override_incomplete=True` → completes and WIP still clears to the pre-WO balance exactly.** Assert **trial balance nets zero** after WO activity (SC4). Clean up fixture rows in `finally`. Exit non-zero on any FAIL. MOUSSE-01/SC1/SC1b/SC2/SC3.
- **Done when:** script exits 0 against a live dev DB with all assertions PASS.
- **Verify:** `podman exec -e PYTHONPATH=/app <api> python scripts/verify_mousse.py` → exit 0.
- **Parallel-ok:** no (depends on 11)

### [ ] 13. Add the concurrency scenario (two concurrent issues via `asyncio.gather`)
- **Files:** `backend/scripts/verify_mousse.py` (add a `run_concurrency()` scenario invoked from `main`)
- **Do:** Set up a Released WO whose component has on-hand exactly enough for ONE of two identical issue requests. Fire both concurrently with `asyncio.gather` on two independent sessions. Assert exactly one succeeds and one fails (floor 4xx / lock serialization), on-hand never goes negative, no double-consume, and the WO's WIP reflects only the successful issue (SC5). A sequential-only test cannot prove this — the row lock (task 8) is what makes it hold. Clean up in `finally`. MOUSSE-01/SC5.
- **Done when:** the concurrency scenario PASSes deterministically across repeated runs; removing the FOR UPDATE lock makes it FAIL (spot-check once, then restore).
- **Verify:** `podman exec -e PYTHONPATH=/app <api> python scripts/verify_mousse.py` includes the concurrency PASS lines; exit 0.
- **Parallel-ok:** no (depends on 12)

### [ ] 14. Write `verify_mousse_api.py` (HTTP-level RBAC + audit rows)
- **Files:** `backend/scripts/verify_mousse_api.py`
- **Do:** Model on `verify_reports_api.py` (stdlib urllib; mint throwaway users/roles with `create_access_token`; cleanup in `finally`). For each MOUSSE mutation route (create/release/issue/complete/cancel) and the read routes: assert `mousse:write` token → 2xx, no-permission token → 403, unauthenticated → 401; reads gated on `mousse:read`. After a successful create/release/issue/complete over HTTP, assert the matching `AuditLog` rows exist (`work_order.created/released/issued/completed`) attributable to the acting user (SC6). Uses its own fixture WO (create the minimal PLUM part/BOM/items via service imports, or reuse a seeded one) and cleans up. MOUSSE-01/SC6.
- **Done when:** script exits 0 with 200/401/403 asserted on every route and audit rows confirmed.
- **Verify:** `podman exec -e PYTHONPATH=/app <api> python scripts/verify_mousse_api.py` → exit 0.
- **Parallel-ok:** no (depends on 11; can run alongside 12/13 authoring)

### [ ] 15. Run the full regression suite
- **Files:** none (execution task); note results in `docs/tasks/feature-mousse-work-orders.md`
- **Do:** Run `verify_inventory`, `verify_purchasing`, `verify_e2e_p8`, `verify_gl`, `verify_ap`, `verify_reports`, plus the new `verify_mousse` and `verify_mousse_api`, all with `PYTHONPATH=/app` in-container. Confirm trial balance still nets zero after MOUSSE activity. MOUSSE-01/SC4.
- **Done when:** all eight scripts exit 0.
- **Verify:** run each; capture exit codes = 0.
- **Parallel-ok:** no (depends on 12–14)

### [ ] 16. Frontend — WO list, hooks, route, and nav wiring
- **Files:** `frontend/src/routes/mousse/WorkOrders.tsx`, `frontend/src/routes/mousse/hooks.ts` (or `frontend/src/hooks/useWorkOrders.ts`), `frontend/src/routes/mousse/components/MousseNav.tsx`, `frontend/src/App.tsx`
- **Do:** TanStack Query hook `useWorkOrders()` → `GET /api/v1/mousse/work-orders` via the axios client. `WorkOrders` screen: table of WOs (number, part, planned qty, status). `MousseNav` copying `SyerpNav.tsx` (Work Orders tab). In `App.tsx` add `<Route path="/mousse" element={<Navigate to="/mousse/work-orders" replace />} />` and `/mousse/work-orders`. Sidebar auto-shows `/mousse` when the module is enabled ∩ user has `mousse:read` (matches existing per-module NavLink gating). MOUSSE-01/SC7.
- **Done when:** with MOUSSE enabled, the sidebar shows MOUSSE, `/mousse/work-orders` lists WOs, nav hidden when module disabled or without `mousse:read`.
- **Verify:** `cd frontend && npm run build`; manual: enable module, load `/mousse/work-orders`.
- **Parallel-ok:** yes (backend 10/11 define the contract; can start once schemas/router paths fixed)

### [ ] 17. Frontend — Work Order create dialog
- **Files:** `frontend/src/routes/mousse/components/WorkOrderCreateDialog.tsx`, list wiring in `WorkOrders.tsx`
- **Do:** Dialog with PLUM part select, planned qty, target location select; `useMutation` → `POST /mousse/work-orders`; on success `invalidateQueries(['mousse','work-orders'])` and toast (sonner). MOUSSE-01/SC7.
- **Done when:** creating a WO from the UI adds it to the list without a manual refresh.
- **Verify:** `npm run build`; manual create round-trip.
- **Parallel-ok:** no (depends on 16)

### [ ] 18. Frontend — Work Order detail with snapshot lines + Issue action
- **Files:** `frontend/src/routes/mousse/WorkOrderDetail.tsx`, `frontend/src/routes/mousse/components/IssueComponentsDialog.tsx`, route in `App.tsx`
- **Do:** `/mousse/work-orders/:id` shows header/status, a Release button (Draft only), and the snapshot component lines with `qty_required`, `on_hand`, `issued_so_far` (visually flag under-issued lines). `IssueComponentsDialog` posts `POST /mousse/work-orders/{id}/issue`; on success invalidate the WO detail + list queries. Release button posts `.../release`. **Hold button (In Progress only) posts `.../hold`; Resume button (On Hold only) posts `.../resume`** (D-P10-9/SC1b) — both invalidate the detail query. MOUSSE-01/SC7.
- **Done when:** detail renders component lines with live on-hand/issued and flags under-issue; releasing, issuing, holding, and resuming update the view via query invalidation.
- **Verify:** `npm run build`; manual release→issue flow.
- **Parallel-ok:** no (depends on 16)

### [ ] 19. Frontend — Complete action
- **Files:** `frontend/src/routes/mousse/WorkOrderDetail.tsx`, `frontend/src/routes/mousse/components/CompleteWorkOrderDialog.tsx`
- **Do:** Complete button (visible only In Progress) → `POST /mousse/work-orders/{id}/complete`. **If any component is under-issued, the dialog surfaces a warning listing the short components and requires ticking an "override incomplete" checkbox before submit (sends `override_incomplete=true`); a fully-issued WO completes without the checkbox** (D-P10-9). On success invalidate WO detail + list + (optionally) the FG inventory item query; toast the received FG qty/cost. On a 4xx under-issue rejection (no override) surface the error. MOUSSE-01/SC7.
- **Done when:** completing a fully-issued In-Progress WO moves it to Completed without manual refresh; an under-issued WO shows the override warning and only completes once the override is confirmed.
- **Verify:** `npm run build`; manual complete flow.
- **Parallel-ok:** no (depends on 18)

### [ ] 20. Frontend — Vitest coverage of the key flows
- **Files:** `frontend/src/routes/mousse/WorkOrders.test.tsx`, `WorkOrderDetail.test.tsx`, `components/WorkOrderCreateDialog.test.tsx`, `components/IssueComponentsDialog.test.tsx`
- **Do:** Testing-Library tests (mirror `routes/syerp/*.test.tsx`) mocking the axios client: list renders WOs; create dialog submits and invalidates; detail renders component lines with on-hand/issued; issue and complete mutations fire the right requests and invalidate. MOUSSE-01/SC7.
- **Done when:** `npm run test` passes with the new tests covering create/issue/complete.
- **Verify:** `cd frontend && npm run test`.
- **Parallel-ok:** no (depends on 16–19)

## Deviations
- **Reference-fact corrections (Task 2, verified against real code):** two "verified" facts in the
  Context were wrong. (a) Shared `Base` is `from app.core.base import Base` (NOT `app.core.db`) —
  matches `syerp/models.py`. (b) `syerp_inventory_txn.id` is **`String(36)` UUID**, not an int PK, so
  `WorkOrderIssue.inventory_txn_id` FK is `String(36)`. Downstream tasks (3 migration, 6-9 service)
  must match `mousse/models.py` types, not the original Context prose. New source files carry the
  `# ABOUTME:` header (zj guard). `app.core.models` uncommented to aggregate mousse models. (`162c463`)
- **Task 4 (verified):** real tables are `permissions` + `role_permissions` (not `auth_permission`);
  only the verification query changed, not the seed logic. (`0ce67ae`)
- **Task 1 base:** branch `feature-mousse-work-orders` cut off the **D-P10-4 chore tip `6293c96`**
  (`chore-syerp-service-split`, which carries the syerp `service/` package split), not tag
  `zj/good-09c` as the task text says. The owner chose "run the syerp split chore first, then build
  MOUSSE on the clean post-split base" (STATE 2026-07-13). The chore tip is a descendant of the tag
  by docs + the split commit only; the verified 9c code is unchanged underneath. MOUSSE imports
  SYERP service functions by their existing public names (D-P10-4), which the split preserves.

## Risks
- **WIP-clears-to-zero rounding (SC3).** `accumulated_wip / planned_qty` can produce a residual; if the FG receipt value ≠ the 1140 credit, 1140 won't return to pre-WO exactly. Mitigation: value the receipt at exactly the accumulated WIP (credit the exact Σ debits), quantize with `_COST_QUANTUM`/`ROUND_HALF_UP` as `compute_new_moving_avg` does; if the assert ever needs tolerance, the posting diverged — fix the posting. Early warning: verify_mousse.py pre/post inequality.
- **Issue concurrency race (SC5).** Read-check-write on on-hand under READ COMMITTED double-consumes without a lock. Mitigation: FOR UPDATE in sorted-id order before the guard (create_bill template) + the task-13 gather scenario. Early warning: task-13 fails or is flaky.
- **Under-issue at completion (D-P10-9).** Completion is blocked 4xx on an under-issued WO unless `override_incomplete=true` (audited); the override path still clears WIP exactly (FG valued at accumulated WIP). Risk: the override becomes a habitual click that hides genuinely incomplete builds — mitigated by auditing the override + the short components. Early warning: verify_mousse.py asserts both the block and the audited override.
- **On Hold state coherence (D-P10-9).** Issuing is disallowed while On Hold (must resume first); ensure the FSM guard and the UI both hide Issue on On Hold. Early warning: verify_mousse.py hold-then-issue → 4xx.
- **Component with no linked InventoryItem (D-P10-7).** A BOM child lacking a stocked item must reject the ENTIRE release (no partial snapshot). Early warning: verify_mousse.py partial-snapshot assertion.
- **wo_number collision under concurrent creation.** Sequential-from-max generation can race; the unique constraint is the backstop (create retries/500 rather than dup). Acceptable for draft creation; revisit if it bites.
- **D-P10-5 scope (confirmed).** Single-level snapshot means sub-assemblies are issued as components, not exploded to leaves — owner-confirmed at handoff. A part whose sub-assembly is not itself stocked/produced will fail the D-P10-7 release guard (no linked InventoryItem), which is the intended fail-fast.

## Noticed / deferred
- Routing, work centers, labor, overhead (5120/5130), shop-floor operator view — deferred (D-P10-1); the 5120/5130 accounts stay unused this phase.
- WO scrap / yield loss, partial/backflush issue automation, WO reopen/uncancel — not in this slice.
- Multi-level BOM explosion for WO components — deferred pending D-P10-5 confirmation.
- `syerp/service.py` split + MAP.md refresh — separate prior chore branch (D-P10-4), explicitly NOT here.
- MOUSSE-specific `verify_mousse` wiring into any CI aggregate script — follow however the other verify_* scripts are aggregated (out of scope to invent one).
