# Plan: Phase 12a — GELATO bins & directed putaway (inbound foundation)
Goal: A warehouse operator can define bins inside a SYERP stock location and direct received (unbinned) stock into bins, with per-bin on-hand deriving from the shared ledger and rolling up exactly to the location total.
Status: draft

## Success criteria
<!-- Traces GELATO-01 (SRD ~596-638); 12a = inbound-foundation subset only. -->
- **SC1 — Module wired + schema.** New `gelato` module self-registers (router mounted at `/api/v1/gelato`; `gelato:read`/`gelato:write` seeded idempotently); migration **0015** adds `gelato_bin` + a nullable `bin_id` column on `syerp_inventory_txn`; `alembic upgrade head` runs clean 0001→0015 on a FRESH DB; full regression `verify_*` still exit 0. *(prereq for all ACs)*
- **SC2 — Bin CRUD (AC1).** Create/edit/archive bins scoped to a location; code unique-within-location; archived hidden from default lists; dup code / non-existent location rejected 4xx; validation server-side.
- **SC3 — Per-bin on-hand derives + rolls up (AC1).** `get_bin_on_hand(item, location, bin)` derives Σ signed qty for `(item, location, bin_id)`; Σ over a location's bins + unbinned (`bin_id IS NULL`) == the SYERP per-location total (`get_item_onhand`), Decimal-exact — the load-bearing roll-up invariant.
- **SC4 — Directed putaway nets zero at location (AC2, AC7-putaway).** Putaway moves qty unbinned→target-bin (and bin→bin) as paired bin-aware `InventoryTxn` legs (`post_transfer` shape, `txn_type="putaway"`); location total UNCHANGED; target-bin rises, source pool falls; putaway exceeding source-pool on-hand rejected 4xx; a directed target-bin suggestion is offered but user-confirmable; two concurrent putaways cannot over-draw the source (FOR UPDATE + Barrier).
- **SC5 — Audit + RBAC at HTTP level (AC8).** Bin create/edit/archive and every putaway emit an attributable audit row; endpoints gated `gelato:read`/`gelato:write` (401/403/200) — proven by `verify_gelato_api.py` (HTTP-level, non-optional).
- **SC6 — Frontend + regression.** GELATO nav gated on module-enabled ∩ `gelato:read`; Bins screen (list/create/edit/archive within a location); Putaway screen (unbinned stock per item/location → suggested target bin → confirm move); TanStack Query invalidation; colocated Vitest + `npm run build` clean; full regression exit 0 and Trial Balance nets zero (12a posts NO GL).

## Context
Read before starting: `.zj/SRD.md` GELATO-01 (~596-638); `.zj/DECISIONS.md` D-V3-7/8/9, D-P8-3/6/7, D-P10-6, D-P9b, D-V3-18; `.zj/LEARNINGS.md` Phase 11a/11b; `.zj/codebase/MAP.md`.

Key real files and the patterns to mirror shape-for-shape:
- **Ledger primitive to clone:** `backend/app/modules/syerp/service/inventory.py`
  - `post_transfer` (lines 471-573) — two paired legs, fresh `transfer_group_id`, net-zero, floor-guarded via `_adjustment_violates_floor` (line 356). Putaway is the same shape, intra-location, with a `bin_id` dimension.
  - `get_item_onhand` (line 99, per-location roll-up) and `get_item_on_hand` (line 147, item total) SUM `InventoryTxn.quantity` and do **not** filter `bin_id` — so adding a nullable `bin_id` leaves location roll-up automatic. Bin on-hand is a NEW derivation filtering `bin_id`.
- **Model + migration convention:** `backend/app/modules/syerp/models.py` `InventoryTxn` (line 240; `location_id` int FK, `item_id` String(36), `txn_type` String(20), `transfer_group_id` for paired legs). Migrations authored **by hand on the host** (autogenerate can't persist in-container — LEARNINGS 11a); latest = `backend/alembic/versions/0014_crumb_sales_orders.py`; **new head = 0015**.
- **New-module shape (mirror exactly):** `backend/app/modules/mousse/` and `backend/app/modules/crumb/`
  - `__init__.py` self-registers via `registry.register(sys.modules[__name__])` (MODULE_NAME="gelato").
  - `crumb/service/` is a PACKAGE from day one (`__init__.py` re-exports the public surface) — GELATO does the same.
  - Router: thin, `require_permission` gate per route, `write_audit` AFTER the service commit (`mousse/router.py` head documents the exact convention).
- **Concurrency lock exemplars:** `crumb/service/sales_orders.py:619` (`select(...).where(id==iid).with_for_update()`) and `:240` (`.order_by(InventoryItem.id)` — lock in sorted-id order); Barrier tests at `scripts/verify_crumb_so.py:922` and `scripts/verify_mousse.py:1003`.
- **Wiring registries (all must gain a `gelato` line):** `app/main.py:79-83` (`importlib.import_module`), `app/core/models.py:27` (model aggregation), `app/modules/auth/seed.py:38-54` (permission catalog + default grants). NOTE: `app/core/modules_seed.py:29` **already** carries `("gelato", "GELATO — Warehouse", False, 60)` — no change needed there.
- **Code generator (if bins auto-number):** `crumb/service/sales_orders.py::_next_sales_order_number` / SYERP `generate_item_code` (D-P8-6 numeric-safe shape).
- **Frontend templates:** `frontend/src/routes/syerp/StockLocations.tsx` + `Vendors.tsx` (list/create/edit/archive), `frontend/src/routes/syerp/components/StockTransferDialog.tsx` (move-between form), `frontend/src/routes/mousse/` (`hooks.ts`, `components/MousseNav.tsx`, colocated `*.test.tsx`); nav gating in `frontend/src/components/AppShell.tsx` (`useVisibleModules` = enabled ∩ perms) + `Sidebar.tsx`; routes in `frontend/src/App.tsx:89-92`.
- **In-container verify runner:** `podman exec -e PYTHONPATH=/app compose_api_1 python scripts/<name>.py`.

## Decisions
<!-- The 6 confirmed by the owner this session are fixed constraints, recorded as D-P12a-1..6; D-P12a-7..10 are the plan-author's calls with rationale. -->
- **D-P12a-1 — 12a/12b split.** 12a = bins + directed putaway (inbound; NO GL, NO sales-order/reservation dependency, NO pick/pack/ship). 12b = pick→pack→ship + COGS JE + reservation relief. This plan is 12a only.
- **D-P12a-2 — Bin dimension on the existing SYERP ledger.** A nullable `bin_id` FK column is added to `syerp_inventory_txn`. Per-bin on-hand = Σ txns for `(item, location, bin)`; location total = Σ over all bins incl. NULL (unchanged from SYERP-10.3). Existing/PO receipts land `bin_id=NULL` (unbinned). One ledger, single source of truth (AC1 roll-up guaranteed by construction).
- **D-P12a-3 — Hub-direction inversion accepted.** The FK points a SYERP-owned ledger row → a GELATO-owned `gelato_bin` table. GELATO owns the bin table + putaway workflow + screen; SYERP owns the ledger + the bin-aware posting primitive GELATO imports (D-V3-9 / D-P10-6). To avoid a Python import cycle, the mapped column uses a **string table-name FK** `ForeignKey("gelato_bin.id")` (SQLAlchemy resolves lazily by name; no import of gelato models into syerp). Both the `bin_id` column and the `gelato_bin` table are created by GELATO's migration **0015**.
- **D-P12a-4 — Branch.** `feature-gelato-bins-putaway`, cut off the verified 11b tip (tag `zj/good-11b-crumb-sales-orders`, commit `fec334f`). 11a/11b are unmerged; 12a stacks on them (per-sub-phase branch precedent).
- **D-P12a-5 — UI folded into this plan, no separate DESIGN.md.** Bins reuse the SYERP list/create/edit/archive template; Putaway is a new directed-move screen.
- **D-P12a-6 — Concurrency pre-empted from the start.** Putaway's source-pool floor guard locks the contended row(s) FOR UPDATE in sorted-id order BEFORE the guard read (D-P9b/D-V3-18); `verify_gelato.py` includes an `asyncio.gather`+`Barrier` two-concurrent-putaway scenario proven load-bearing (fails when the lock is removed).
- **D-P12a-7 (author) — The bin-aware paired-leg primitive lives in SYERP, not GELATO.** Add `post_putaway(...)` and `get_bin_on_hand(...)` to `backend/app/modules/syerp/service/inventory.py`, alongside `post_transfer`. GELATO's service imports them (D-V3-9). Rationale: the primitive writes the SYERP-owned `InventoryTxn` model and reuses `_adjustment_violates_floor`, `get_location`, `get_item`, and the moving-avg cost source — all SYERP-private. Keeping it in SYERP means GELATO never writes the SYERP model directly (mirrors MOUSSE importing SYERP inventory fns, D-P10-6) and keeps GELATO's own service thin (bin CRUD + orchestration only). Alternative (GELATO writes the model directly) rejected: leaks SYERP ledger invariants across a module boundary.
- **D-P12a-8 (author) — `txn_type = "putaway"`.** A new distinct type (not reusing `"transfer"`) so putaway legs are filterable/auditable and never confused with inter-location transfers. Two legs share a fresh `transfer_group_id` (reuse the existing paired-leg column — no schema change for grouping).
- **D-P12a-9 (author) — Bin code is user-supplied, unique-within-location.** Not auto-numbered. Rationale: warehouse bin codes are physical labels (e.g. `A-01-03`) the operator assigns; auto-numbering would fight reality. Uniqueness enforced by a composite unique constraint `(location_id, code)` on `gelato_bin` + a service-level 4xx pre-check (Partner/item dup-code precedent). No numeric-safe generator needed.
- **D-P12a-10 (author) — Directed-putaway heuristic (simple, confirmable).** Suggest the target bin as: (a) a bin in the location already holding on-hand of that item, else (b) the first active bin in the location by code, else (c) none (user picks). The suggestion is a hint only — the user confirms/overrides the target bin before the move posts. No optimization engine in 12a.
- **D-P12a-11 (author, bind 12b) — Staging-bin moves are a 12b concern but not foreclosed.** 12b pick moves pick-bin→staging-bin (net-zero at location) and ship issues from the staging bin. 12a's bin model (any bin can be source or target of a putaway; `bin_id` nullable for unbinned) already supports a staging bin as just another `gelato_bin` row — no 12a schema/API change is needed to admit it later.

## Tasks

### [x] 1. Author the GELATO ORM models (`gelato_bin`) + the `bin_id` mapped column on `InventoryTxn`
- **Files:** `backend/app/modules/gelato/__init__.py` (new), `backend/app/modules/gelato/models.py` (new), `backend/app/modules/syerp/models.py` (edit — add `bin_id`)
- **Do:** Create the `gelato` package. In `gelato/models.py` define `Bin(Base)` → `__tablename__ = "gelato_bin"`: `id` (Integer PK, mirror StockLocation int-PK style), `location_id` (Integer FK `syerp_stock_location.id`, not null, index), `code` (String, not null), `description` (String, nullable), `active` (Boolean default True), `created_at` (tz-aware). Add `UniqueConstraint("location_id", "code", name="uq_gelato_bin_location_code")`. In `syerp/models.py` `InventoryTxn`, add `bin_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("gelato_bin.id"), nullable=True, index=True)` — use the **string** table-name FK so no gelato import is needed (D-P12a-3). `gelato/__init__.py` mirrors `mousse/__init__.py`: `MODULE_NAME="gelato"`, import router, `registry.register`.
- **Done when:** `python -c "from app.modules.gelato import models"` imports clean in-container; `InventoryTxn.bin_id` and `Bin` are visible on `Base.metadata`.
- **Verify:** `podman exec -e PYTHONPATH=/app compose_api_1 python -c "from app.core.models import *; from app.modules.gelato.models import Bin; from app.modules.syerp.models import InventoryTxn; print('bin_id' in InventoryTxn.__table__.c, Bin.__tablename__)"` → prints `True gelato_bin`.
- **Parallel-ok:** no (foundation)

### [x] 2. Register GELATO models in the aggregator + wire module import
- **Files:** `backend/app/core/models.py` (edit), `backend/app/main.py` (edit)
- **Do:** Add `from app.modules.gelato import models as gelato_models  # noqa: F401` to the Phase 4+ block in `core/models.py` (so Alembic sees `gelato_bin`). Add `importlib.import_module("app.modules.gelato")` to the import block in `main.py:79-83` (after crumb). Router does not exist yet — task 6 adds it; keep the `__init__` router import satisfied by a stub or land this after task 6. **Order note:** do this edit but the app won't boot until task 6's router exists; verify at task 6.
- **Done when:** `core/models.py` and `main.py` both name `gelato`.
- **Verify:** `grep -n gelato backend/app/core/models.py backend/app/main.py` shows both lines. (Boot verified in task 6.)
- **Parallel-ok:** no (depends on 1)

### [x] 3. Hand-author migration 0015 (create `gelato_bin`, add `bin_id`)
- **Files:** `backend/alembic/versions/0015_gelato_bins.py` (new)
- **Do:** Author by hand on the host (LEARNINGS 11a — no in-container autogenerate). `down_revision = "0014"`. `upgrade()`: `op.create_table("gelato_bin", ...)` with the columns from task 1 + the `(location_id, code)` unique constraint + FK to `syerp_stock_location.id`; then `op.add_column("syerp_inventory_txn", sa.Column("bin_id", sa.Integer(), nullable=True))`, create the index, and `op.create_foreign_key("fk_inventory_txn_bin", "syerp_inventory_txn", "gelato_bin", ["bin_id"], ["id"])`. `downgrade()`: drop FK/column then drop table. Table-create-order matters (bin table before the FK).
- **Done when:** `alembic upgrade head` runs clean 0001→0015 on a fresh DB; `alembic downgrade -1` then `upgrade head` round-trips clean.
- **Verify:** `podman exec compose_api_1 alembic upgrade head` exits 0 and logs `0015`; `podman exec compose_api_1 python -c "import sqlalchemy as sa; from app.core.db import engine; ..."` or a psql `\d gelato_bin` shows the table + `syerp_inventory_txn.bin_id`.
- **Parallel-ok:** no (depends on 1)

### [x] 4. Seed `gelato:read` / `gelato:write` permissions
- **Files:** `backend/app/modules/auth/seed.py` (edit)
- **Do:** Add `("gelato:read", "Read access to GELATO (warehouse management)")` and `("gelato:write", "Write access to GELATO")` to the permission catalog (mirroring the `mousse:`/`crumb:` entries at lines 38-41), and add both to the admin default-grant list (lines 51-54). Idempotent (seed inserts only if absent).
- **Done when:** After boot, both permissions exist and admin holds them.
- **Verify:** `podman exec -e PYTHONPATH=/app compose_api_1 python -c "import asyncio; ...select Permission where code like 'gelato:%'"` returns 2 rows. (Or exercised by `verify_gelato_api.py` in task 8.)
- **Parallel-ok:** yes (independent of 1-3)

### [x] 5. Define GELATO Pydantic schemas
- **Files:** `backend/app/modules/gelato/schemas.py` (new)
- **Do:** Mirror `crumb/schemas.py`/`mousse/schemas.py` style. Define `BinCreate` (location_id, code, description?), `BinUpdate` (description?, active?), `BinRead` (id, location_id, code, description, active, created_at), `BinOnHandRead` (bin_id, code, quantity: Decimal), `PutawayRequest` (item_id, location_id, to_bin_id, qty: Decimal, from_bin_id: int|None=None → None means the unbinned pool), `PutawayResult` (the two `TransactionRead` legs + resulting bin on-hand + location total), and a `PutawaySuggestion`/`UnbinnedStockRead` for the screen (item_id, location_id, unbinned_qty, suggested_bin_id). Decimals typed `Decimal`.
- **Done when:** `from app.modules.gelato.schemas import PutawayRequest, BinRead` imports clean.
- **Verify:** `podman exec -e PYTHONPATH=/app compose_api_1 python -c "from app.modules.gelato.schemas import PutawayRequest, BinRead, BinOnHandRead; print('ok')"`.
- **Parallel-ok:** yes (independent of 1-4 once package dir exists)

### [x] 6. Add the SYERP bin-aware primitives: `post_putaway` + `get_bin_on_hand`
- **Files:** `backend/app/modules/syerp/service/inventory.py` (edit)
- **Do:** Add `get_bin_on_hand(db, item_id, location_id, bin_id)` — Σ `InventoryTxn.quantity` WHERE item/location match and `bin_id` matches (including `IS NULL` for the unbinned pool); coalesce None→Decimal("0"). Add `post_putaway(db, item_id, location_id, from_bin_id, to_bin_id, qty, actor_id)` cloning `post_transfer` (lines 471-573) but **intra-location, bin-dimensioned**: (1) reject 422 if `from_bin_id == to_bin_id` or `qty <= 0`; (2) 404 if item/location/target-bin missing; **(3) LOCK FIRST** — `select(InventoryTxn... or the source pool row set).where(item,location, from_bin).with_for_update()` in sorted-id order (D-P9b/D-V3-18) BEFORE the guard read (mirror `sales_orders.py:619`); (4) derive source-pool on-hand via `get_bin_on_hand`; (5) reject 422 via `_adjustment_violates_floor(source_onhand, -qty)`; (6) append EXACTLY TWO `txn_type="putaway"` legs sharing a fresh `transfer_group_id`: `-qty` at `(location, from_bin_id)`, `+qty` at `(location, to_bin_id)`, both valued at current `moving_avg_cost`; (7) commit. Net-zero at location grain (both legs same `location_id`). Add both to the inventory service's export surface.
- **Done when:** functions importable; a manual call moves qty unbinned→bin leaving `get_item_onhand` location total unchanged.
- **Verify:** `podman exec -e PYTHONPATH=/app compose_api_1 python -c "from app.modules.syerp.service.inventory import post_putaway, get_bin_on_hand; print('ok')"` (behavior proven in task 9).
- **Parallel-ok:** no (depends on 1, 3)

### [x] 7. GELATO service package: bin CRUD + putaway orchestration
- **Files:** `backend/app/modules/gelato/service/__init__.py` (new), `backend/app/modules/gelato/service/bins.py` (new), `backend/app/modules/gelato/service/putaway.py` (new)
- **Do:** Mirror `crumb/service/` package layout (`__init__.py` re-exports the public surface). `bins.py`: `create_bin` (422 on dup `(location,code)` pre-check + 404 on missing location), `update_bin`, `archive_bin` (set active=False), `get_bin`, `list_bins(location_id, include_archived=False)` (archived hidden by default — Partner precedent). `putaway.py`: `suggest_target_bin(db, item_id, location_id)` (D-P12a-10 heuristic), `list_unbinned_stock(db, location_id)` (items with `bin_id IS NULL` on-hand > 0), and `execute_putaway(...)` which validates the bins belong to the location then delegates to SYERP `post_putaway` (D-P12a-7) and returns `PutawayResult`. Keep GELATO thin — no direct `InventoryTxn` writes.
- **Done when:** `from app.modules.gelato.service import create_bin, execute_putaway, suggest_target_bin, get_bin_on_hand` (re-exported) all import.
- **Verify:** `podman exec -e PYTHONPATH=/app compose_api_1 python -c "from app.modules.gelato.service import create_bin, execute_putaway, list_bins; print('ok')"`.
- **Parallel-ok:** no (depends on 5, 6)

### [x] 8. GELATO router + self-register (thin, RBAC-gated, audit-after-commit)
- **Files:** `backend/app/modules/gelato/router.py` (new)
- **Do:** Mirror `mousse/router.py` head convention. Routes (no prefix; spell `/gelato/...`): `GET /gelato/locations/{loc}/bins` (gelato:read), `POST /gelato/bins` (write), `PATCH /gelato/bins/{id}` (write), `POST /gelato/bins/{id}/archive` (write), `GET /gelato/locations/{loc}/unbinned` (read), `GET /gelato/putaway/suggestion` (read), `POST /gelato/putaway` (write). Each mutation gates via `require_permission("gelato:write")`, reads via `gelato:read`, and writes ONE `write_audit` row AFTER the service commit: `bin.created` / `bin.updated` / `bin.archived` (target_type="bin") and `inventory.putaway` (target_type="inventory_txn", target_id = group id). Now boot the app (task 2 wiring becomes live).
- **Done when:** `podman-compose ... up` boots clean; `GET /api/v1/gelato/...` routes appear in `/docs`; `curl` with admin token returns 200, no token 401.
- **Verify:** `podman exec compose_api_1 python -c "from app.main import app; print([r.path for r in app.routes if 'gelato' in r.path])"` lists all 7 routes; app boots (`/health` 200).
- **Parallel-ok:** no (depends on 7)

### [x] 9. `verify_gelato.py` — service-level invariants (roll-up + net-zero + floor + concurrency)
- **Files:** `backend/scripts/verify_gelato.py` (new)
- **Do:** Live-Postgres script mirroring `scripts/verify_mousse.py`/`verify_crumb_so.py`. Build inputs in the **real router/UI shape** (11b keeper): construct `PutawayRequest` exactly as `POST /gelato/putaway` receives it and drive the service through that shape — not a synthetic hand-fed leg list. Assertions: (a) create bins; receive stock unbinned; putaway unbinned→bin then bin→bin; assert `get_item_onhand` location total is UNCHANGED across putaways (net-zero, SC4); (b) **roll-up equality Decimal-exact** — Σ `get_bin_on_hand` over the location's bins + unbinned == `get_item_onhand` per-location total (SC3); (c) a putaway exceeding source-pool on-hand raises 422, no rows written (SC4/AC7); (d) **concurrency Barrier scenario** — two `execute_putaway` calls on the SAME source pool fired via `asyncio.gather` synchronized on an `asyncio.Barrier(2)` (mirror `verify_mousse.py:1003`); assert exactly one succeeds / total never over-draws, AND prove it load-bearing (documented: passes with FOR UPDATE, fails when the lock is removed — D-P12a-6).
- **Done when:** script exits 0 with all assertions green; removing the lock in `post_putaway` makes the Barrier assertion fail (proven once, then lock restored).
- **Verify:** `podman exec -e PYTHONPATH=/app compose_api_1 python scripts/verify_gelato.py` exits 0.
- **Parallel-ok:** no (depends on 8)

### [x] 10. `verify_gelato_api.py` — HTTP-level RBAC + audit
- **Files:** `backend/scripts/verify_gelato_api.py` (new)
- **Do:** Mirror `scripts/verify_mousse_api.py`/`verify_crumb_api.py` — drive real HTTP against the running API. Assert: no token → 401; a token WITHOUT `gelato:write` → 403 on bin create + putaway; WITHOUT `gelato:read` → 403 on list; admin → 200. After a successful bin create/edit/archive and a putaway, assert the corresponding `AuditLog` rows exist and are attributable (actor_id set). This is the non-optional paired HTTP script (a service script structurally cannot prove router audit/RBAC — 9a/11a keeper).
- **Done when:** script exits 0; all 401/403/200 + audit assertions green.
- **Verify:** `podman exec -e PYTHONPATH=/app compose_api_1 python scripts/verify_gelato_api.py` exits 0.
- **Parallel-ok:** no (depends on 8)

### [x] 11. Full backend regression (migration touches a SYERP core table — load-bearing)
- **Files:** none (run existing scripts)
- **Do:** Run every existing verify script + the two new ones against the fresh-migrated DB and confirm the Trial Balance still nets zero (12a posts NO GL).
- **Done when:** all of `verify_inventory`, `verify_purchasing`, `verify_e2e_p8`, `verify_gl`, `verify_ap`, `verify_reports`, `verify_mousse`, `verify_crumb`, `verify_crumb_so` (+ their `_api` variants) exit 0, plus `verify_gelato` + `verify_gelato_api`.
- **Verify:** loop: `for s in verify_inventory verify_purchasing verify_e2e_p8 verify_gl verify_gl_api verify_ap verify_ap_api verify_reports verify_reports_api verify_mousse verify_mousse_api verify_crumb verify_crumb_api verify_crumb_so verify_crumb_so_api verify_gelato verify_gelato_api; do podman exec -e PYTHONPATH=/app compose_api_1 python scripts/$s.py || echo "FAIL $s"; done` — no FAIL lines.
- **Parallel-ok:** no (depends on 9, 10)

### [x] 12. Frontend: GELATO API hooks + nav gating
- **Files:** `frontend/src/routes/gelato/hooks.ts` (new), `frontend/src/routes/gelato/components/GelatoNav.tsx` (new), `frontend/src/App.tsx` (edit), `frontend/src/components/AppShell.tsx` / `Sidebar.tsx` (verify only — nav is data-driven by `useVisibleModules` = enabled ∩ perms, gelato already in modules catalog)
- **Do:** Mirror `frontend/src/routes/mousse/hooks.ts` — TanStack Query hooks: `useBins(locationId)`, `useCreateBin`, `useUpdateBin`, `useArchiveBin`, `useUnbinnedStock(locationId)`, `usePutawaySuggestion`, `useExecutePutaway` (invalidate bins + unbinned + item on-hand on success). Add routes in `App.tsx` (mirror `:89-92`): `/gelato` → redirect to `/gelato/bins`, `/gelato/bins`, `/gelato/putaway`. `GelatoNav` mirrors `MousseNav`. Confirm sidebar shows GELATO only when the module is enabled AND user has `gelato:read`.
- **Done when:** `npm run build` clean; nav shows GELATO for an admin with the module enabled, hidden when disabled or without `gelato:read`.
- **Verify:** `cd frontend && npm run build`.
- **Parallel-ok:** no (depends on 8 for the API surface)

### [x] 13. Frontend: Bins screen (list/create/edit/archive within a location)
- **Files:** `frontend/src/routes/gelato/Bins.tsx` (new), `frontend/src/routes/gelato/components/BinSheet.tsx` (new), `frontend/src/routes/gelato/Bins.test.tsx` (new)
- **Do:** Mirror `frontend/src/routes/syerp/StockLocations.tsx` + `components/InventoryItemSheet.tsx`. Location selector → bin table (code, description, active); create/edit via a sheet; archive action; archived hidden unless a "show archived" toggle. Surface the server 4xx (dup code / bad location) as a toast (sonner). Colocated Vitest covering list render, create, dup-code error surface, archive-hides.
- **Done when:** `npm run test` for the file passes; `npm run build` clean.
- **Verify:** `cd frontend && npm run test -- Bins`.
- **Parallel-ok:** yes (parallel with task 14 once 12 lands)

### [x] 14. Frontend: Putaway screen (unbinned → suggested bin → confirm)
- **Files:** `frontend/src/routes/gelato/Putaway.tsx` (new), `frontend/src/routes/gelato/components/PutawayDialog.tsx` (new), `frontend/src/routes/gelato/Putaway.test.tsx` (new)
- **Do:** Mirror `frontend/src/routes/syerp/components/StockTransferDialog.tsx`. Location selector → list of unbinned stock (item, unbinned qty); per row a "Put away" action opening a dialog pre-filled with the suggested target bin (from `usePutawaySuggestion`), qty input (default = full unbinned qty), user can override the target bin; submit → `useExecutePutaway`. On success invalidate + toast; surface 422 (over-draw / bad bin) as an error toast. Colocated Vitest covering: list render, suggestion pre-fill, confirm posts the request shape the endpoint expects (11b keeper — assert the payload), over-draw error surface.
- **Done when:** `npm run test` for the file passes; `npm run build` clean.
- **Verify:** `cd frontend && npm run test -- Putaway`.
- **Parallel-ok:** yes (parallel with task 13 once 12 lands)

## Wave structure
- **Wave A (schema foundation, sequential): 1 → 2 → 3**; **4** and **5** parallel alongside.
- **Wave B (backend logic): 6 → 7 → 8** (primitive → thin service → router+boot).
- **Wave C (verify, sequential after 8): 9, 10** then **11** (full regression).
- **Wave D (frontend): 12** then **13 ‖ 14** in parallel.

## Risks
- **Hub-direction FK inversion (SYERP ledger → gelato_bin).** A SYERP-core table now FK-references a GELATO table — the reverse of the normal hub direction. Early-warning: an import cycle at boot, or Alembic failing to resolve the FK. Mitigation: string table-name FK (no Python import); `gelato_bin` created before the FK in migration 0015; task 8 boot check is the tripwire.
- **Migration touches a SYERP core table (`syerp_inventory_txn`).** A bad column/FK could break every inventory-derived path (on-hand, receipts, MOUSSE issue, CRUMB reservation). Early-warning: any regression script in task 11 failing, or Trial Balance not netting zero. Mitigation: task 11 runs the FULL suite; `bin_id` is nullable and unfiltered by existing on-hand SUMs (verified in task 6/9), so existing paths are unaffected by construction.
- **Cross-path ledger race is only PARTIALLY closed in 12a (standing BACKLOG p2).** 12a locks putaway-vs-putaway only. Putaway-vs-adjust/receive/issue on the same item still share the ledger; the full cross-path shared row-lock lands with 12b ship (per SRD AC7 note). Early-warning: none in 12a scope — flagged so 12b doesn't assume 12a already closed it.
- **Bin split desyncs after any bin-blind movement — SEQUENTIAL correctness, not just a race (verify MAJOR, upgraded 2026-07-18).** The above item under-framed this as a concurrency race; the review sharpened it: because ONLY putaway is bin-aware in 12a, a bin-blind draw (`post_transfer`/`post_adjustment`/MOUSSE issue, all `bin_id=NULL`, per-location floor guard) overstates the bin it left and drives the unbinned pool negative **even single-threaded** — receive 10 → putaway into bin A → adjust −10 ⇒ bin A still 10, unbinned −10, location total 0. Every bin figure 12a surfaces silently rots in normal operation. **Location/total on-hand and the SC3 Σ(bins)+unbinned==location roll-up stay exact** — only the split lies. Mitigation shipped at verify: `get_bin_on_hand` docstring trust-boundary note + `verify_gelato.py` scenario (E) pins it + BACKLOG p2 entry. Durable fix = bin-aware pick/issue = **Phase 12b** (GELATO-01 AC3/AC5); 12b MUST NOT assume 12a closed it.
- **Verify green but dead-through-UI (11a/11b recurring failure).** If `verify_gelato.py` feeds a synthetic leg shape instead of the real `PutawayRequest`, a UI-dead feature can certify green. Mitigation: tasks 9/14 explicitly assert the router/UI payload shape; task 10 HTTP script exercises the real endpoint.

## Out of scope (deferred to 12b or later)
- Pick (AC3), pack (AC4), ship + COGS JE + reservation relief (AC5) — all of 12b.
- The ship-side of AC7 (over-ship guard) and the full cross-path shared ledger lock across issue/adjust/receive/transfer/ship — 12b.
- Staging-bin moves (pick-bin→staging, ship-from-staging) — 12b (D-P12a-11 confirms 12a's model doesn't foreclose them).
- Any GL posting / journal entry (12a posts NO GL — Trial Balance must still net zero).
- Lot/serial tracking (D-V3-4, permanently out of v3.0).
- Bin auto-numbering / slotting-optimization engine (D-P12a-9/10 — user-supplied codes, simple heuristic only).

## Noticed (unrelated — surfaced during build, not fixed here)
- **Integer-PK entities audited for the first time.** GELATO's `Bin` is the first int-PK entity written to `audit_log` (mousse/crumb/syerp audited entities all use uuid-string PKs), which is why the `target_id` int→str mismatch (see Deviations) had never surfaced before. Worth a quick repo-wide audit of `write_audit(target_id=...)` call sites for any other int-PK argument as more int-PK entities get audited. (candidate BACKLOG entry)
- **`StarletteDeprecationWarning: HTTP_422_UNPROCESSABLE_ENTITY`** is emitted repo-wide (Starlette wants `HTTP_422_UNPROCESSABLE_CONTENT`). GELATO followed the existing convention. Already tracked as the 422 deprecation sweep (BACKLOG p3) — not new to this phase.

## Decisions needed
None — the six owner-confirmed decisions (D-P12a-1..6) are fixed, and the four author calls (D-P12a-7..10, +11) are recorded with rationale and recommendations. No open question requires the manager before build starts.

## Deviations
- **Branch cut off HEAD (`da9474e`), not the bare tag `fec334f`.** D-P12a-4 said cut off the verified 11b tip; the retro/plan doc commits (`de9e0f0`, `da9474e`) sit on top of that tag and include *this PLAN.md*. Cutting off the tag would drop the plan. HEAD is code-identical to the tag (docs only on top) — mirrors the 11b precedent (branch off code tip, not bare tag). (manager, build start)
- **Task 1 — stub `router.py` created early.** `gelato/__init__.py` mirrors mousse and does `from app.modules.gelato.router import router` at package-import time, so the package (and task 1's own verify) can't import until a router module exists. Task 1 created a minimal `router = APIRouter()` stub; task 8 replaces it with the real routes. (The plan's task-2 note anticipated this and mis-numbered the router task as "6"; the real router is task 8.)
- **Task 1 — commit subject shortened to satisfy `guard-commit-msg.sh` (72-char max).** No content change. String columns sized (`code String(50)`, `description String(255)`) to match SYERP/mousse conventions rather than bare `String`.
- **Task 6 — lock target + bin-validation split, refining the plan.** (1) `post_putaway` locks `InventoryItem` FOR UPDATE (not `InventoryTxn` as the plan's prose implied) — the append-only ledger is not the contention point; the item-master row is, mirroring `sales_orders.py:619`. (2) SYERP `post_putaway` validates only item/location; bin existence + location-membership + archived-guard live in GELATO's `execute_putaway` (task 7), because SYERP must not import gelato models (D-P12a-3). DB FK is the backstop.
- **Task 7 — `get_item_onhand` signature.** Plan referenced `get_item_onhand(db, item_id, location_id)`; the real helper is `get_item_onhand(db, item_id)` returning per-location rows. Service selects the matching location's quantity (0 when the location nets zero). Verified correct (location total unchanged by putaway).
- **Task 8/10 — router audit `target_id` int→str bug (found by the HTTP script, fixed).** Task 8's bin routes passed the integer `Bin.id` to `write_audit(target_id=...)`, but `audit_log.target_id` is `VARCHAR(36)`; asyncpg raised `DataError`, so bin create/patch/archive committed the bin then **500'd on the audit write** — bins created with NO attributable audit row (audit-trail violation). `verify_gelato_api.py` (task 10) caught it — a service-level script structurally could not. Minimal fix `str(bin_.id)` on the three bin routes, committed separately as `136e98d` to keep the task-10 commit clean. Putaway route already used the str uuid out-leg id. **This is the 9a/11a keeper recurring: the paired HTTP script earns its place by catching the one router defect verify_gelato.py can't see.** Audit `target_id` for putaway = the OUT-leg txn id (plan said "group id", which `TransactionRead` doesn't expose).
