# Plan: Phase 04 — Inventory ledger race-safety (NFR-7)
Goal: Every floor-guarded inventory-ledger write serializes on the shared sorted-id `SELECT … FOR UPDATE` discipline so the hard invariants (per-location on-hand ≥ 0, qty_received ≤ qty_ordered) hold under concurrent writers, and the three remaining bin-blind draw primitives become bin-aware so the bin split can no longer desync from location totals.
Status: ready — owner decisions confirmed 2026-07-25 (`/zj:plan 4`); next `/zj:build 4`

## Success criteria  (SRD NFR-7, lines 751–767; ROADMAP v4.0 Phase 4 row)

- **SC1 (shared lock):** all inventory-ledger writers — `post_receipt`, `post_adjustment`, `post_transfer` (`backend/app/modules/syerp/service/inventory.py`), purchasing `receive_line` (`backend/app/modules/syerp/service/purchasing.py`), plus the already-locked `post_putaway` / `post_issue` / MOUSSE `issue_components` — lock the contended row(s) `FOR UPDATE` in sorted-id order **before any floor/guard read**, one consistent discipline (the `create_bill`/`record_payment` template, `syerp/service/bills.py:320-330, :815-818`).
- **SC2 (mixed-path concurrency, mutation-proven):** an `asyncio`-concurrent two-writer scenario across mixed paths (MOUSSE `issue_components` racing SYERP `post_adjustment` on the same item/location) cannot drive derived on-hand negative. Mutation-proven per the table in Task 7: remove a lock → invariant breaches (script RED); restore → exactly one writer succeeds, the other 422s (script GREEN). Concurrency proofs live in `verify_*` scripts, NOT pytest (D-P2a-2).
- **SC3 (bin-aware draws):** `post_adjustment`, `post_transfer`, and MOUSSE `issue_components` accept an optional `bin_id`; a draw at a location with binned stock and `bin_id=NULL` draws ONLY the unbinned pool and floor-guards it (422 when insufficient — the operator must name a bin, D-P4-1). The receive→putaway→bin-blind-draw sequence can no longer leave a bin overstated / the unbinned pool negative. `verify_gelato.py` scenario (E) — which currently PINS the broken behavior (`backend/scripts/verify_gelato.py:393-444`) — is revised to assert the fix.
- **SC4 (UI wiring):** the Adjust/Transfer dialogs and the MOUSSE issue dialog expose the optional bin picker end-to-end (schema → router → FE render → a Vitest asserting the REAL payload shape) — the dead-through-UI trap countered explicitly in each FE task, not assumed.
- **SC5 (regression):** all `verify_*` scripts exit 0, Trial Balance nets zero, full backend pytest passes with **0 skipped**, frontend Vitest + `tsc -b && vite build` green, and all four CI jobs (`frontend`, `backend-lint`, `backend-tests`, `verify-scripts`) pass on the branch. Note: a NEW non-API verify script is auto-globbed by the `verify-scripts` CI job (`.github/workflows/ci.yml:155-160`) and must pass there.
- **SC6 (bookkeeping):** SRD NFR-7 → done pending verify; `docs/features/requirements-progress.md` row added; decisions D-P4-1..6 recorded.

## Context

**Lock state today (verified against code):**

| Writer | File:line | Floor/guard read | Lock today |
|---|---|---|---|
| `post_receipt` | `syerp/service/inventory.py:206` (qty_before read :264) | moving-avg qty_before (item-wide SUM) | **none** |
| `post_adjustment` | `inventory.py:336` (floor read :372) | per-location SUM | **none** |
| `post_transfer` | `inventory.py:438` (floor read :491) | per-location SUM at source | **none** |
| `receive_line` | `syerp/service/purchasing.py:555` (over-receipt guard :628) | `line.qty_received + qty > qty_ordered` | **none** |
| `post_putaway` | `inventory.py:638` | per-bin pool | item FOR UPDATE at :708 ✅ |
| `post_issue` | `inventory.py:809` | per-bin pool | item FOR UPDATE at :871 ✅ |
| MOUSSE `issue_components` | `mousse/service.py:580` | per-location SUM (`_component_onhand`) | sorted-id item FOR UPDATE at :679-685 ✅ |

**Template to copy:** `create_bill` / `record_payment` (`syerp/service/bills.py`) lock contended rows FOR UPDATE up-front in **sorted-id order** (deadlock-safe) before the guard read. `post_putaway`/`post_issue` show the single-item form: `select(InventoryItem.id).where(id==item_id).with_for_update()` immediately after the 404 loads, BEFORE the floor read.

**Bin model:** `bin_id` is a nullable FK already on `syerp_inventory_txn` → `gelato_bin` (D-P12a-2/3) — **no migration expected**. Bin-aware primitives live in SYERP; SYERP never imports gelato models — bin existence/membership validation is the caller's job, DB FK is the backstop (D-P12a-3/8). `get_bin_on_hand` (`inventory.py:591`) is the null-aware per-pool SUM and carries the trust-boundary docstring this phase makes stale. `_adjustment_violates_floor` (`inventory.py:323`) is the shared floor predicate — reuse it.

**Schemas/routers/FE to touch:** `AdjustmentCreate` (`syerp/schemas.py:342`), `TransferCreate` (:364); syerp router endpoints `post_adjustment_endpoint` (:497) / `post_transfer_endpoint` (:541); MOUSSE `IssueLine` (`mousse/schemas.py:~146`) / `IssueComponentsRequest` (:157), router `issue_components_endpoint` (`mousse/router.py:172`). FE dialogs: `frontend/src/routes/syerp/components/StockAdjustDialog.tsx` (+`.test.tsx`), `StockTransferDialog.tsx` (+test), `frontend/src/routes/mousse/components/IssueComponentsDialog.tsx` (+test). Bin data source: `useBins(locationId)` in `frontend/src/routes/gelato/hooks.ts:216`.

**Verify-script environment (Phase 3 keeper — recipes were run-in-head against the real env):** the compose `db` service is not host-published; scripts run via
`podman exec -e PYTHONPATH=/app compose_api_1 python scripts/verify_<name>.py` after `podman-compose -f compose/compose.yml -f compose/compose.dev.yml up -d db api`. Scripts build their own engine from `POSTGRES_*` env, need a migrated+seeded `biznice` DB (app-lifespan CoA seeds — boot `api` once). CI's `verify-scripts` job auto-globs every non-`_api.py` `verify_*.py`.

**No GL/JE changes expected** (locks + a bin dimension on existing legs change no accounting amounts). **No Alembic migration expected.** If a task finds either is needed: STOP and flag the owner.

## Decisions  (owner-made; append to DECISIONS.md at build close)

- **D-P4-1 — Bin semantics = explicit-or-unbinned:** optional `bin_id` on all three draw paths; NULL draws only the unbinned pool with an unbinned-pool floor guard (422 when insufficient — operator must name a bin). No server auto-allocation. Mirrors 12b's operator-selected staging bin (D-P12b-9); traceability-first. Accepted behavior change: an adjust/transfer/issue at a fully-binned location now requires a bin.
- **D-P4-2 — Single phase**, no 4a/4b sub-split: lock discipline and bin-awareness touch the same four functions.
- **D-P4-3 — GELATO pick-path Q1/Q2 shipment-header races stay in BACKLOG p2** (outside NFR-7; don't corrupt the ledger).
- **D-P4-4 — Branch:** fresh `chore-inventory-race-safety` cut off `db725fd` (the `chore-ci-pipeline` tip — Phase 3 verified+retro'd docs atop verified CI code), continuing the unmerged v4.0 stack pattern (D-P3 precedent).
- **D-P4-5 — Transfer in-leg lands UNBINNED at the destination** (`bin_id=NULL` on the `+qty` leg): destination bins belong to a different location's bin set; naming one server-side would be auto-allocation (forbidden by D-P4-1). Stock arrives in the destination's unbinned pool and is directed by putaway — exactly the receive→putaway flow 12a/12b established. Only `from_bin_id` is added to the transfer payload.
- **D-P4-6 — Positive adjustments may target a bin:** `qty_delta > 0` with a concrete `bin_id` adds stock directly to that bin (cycle-count "found in bin" case, traceability); with NULL it adds to the unbinned pool (today's behavior). Additions take no pool floor guard (a pool cannot be overdrawn by adding). Only negative deltas floor-guard the named pool.

## Decisions needed

None. D-P4-5 and D-P4-6 (architect-derived corollaries of D-P4-1) were put to the owner at plan
(AskUserQuestion, 2026-07-25) and **both confirmed as written** — transfers arrive unbinned +
putaway directs them; positive adjustments may target a bin, no floor guard on additions.
D-P4-1..3 were owner-chosen at plan (bin semantics, single phase, Q1/Q2 stay backlog).

## Tasks

### [x] 0. Cut branch and checklist
- **Files:** `docs/tasks/chore-inventory-race-safety.md` (new)
- **Do:** `git checkout db725fd -b chore-inventory-race-safety` (D-P4-4). Create the checklist file listing Tasks 1–13, per project convention. Conventional commits, no attribution lines, throughout.
- **Done when:** branch exists at the correct base; checklist committed.
- **Verify:** `git log --oneline -1` shows base `db725fd`; `ls docs/tasks/chore-inventory-race-safety.md`.
- **Parallel-ok:** no

### [x] 1. Serialize the three unlocked inventory.py writers on the item-master lock (SC1)
- **Files:** `backend/app/modules/syerp/service/inventory.py`
- **Do:** In `post_receipt` (:206), `post_adjustment` (:336), and `post_transfer` (:438), add `await db.execute(select(InventoryItem.id).where(InventoryItem.id == item_id).with_for_update())` immediately after the `get_item`/`get_location` 404 loads and **BEFORE** the on-hand/qty_before SELECT — copy the exact shape and comment style of `post_putaway` (:704-710). Single item per call so sorted-id order is trivial; the item-master row is the single contention point (append-only txn rows can't be locked to serialize inserts). Update each docstring's transaction narrative to name the lock step (mirror post_putaway step 3). For `post_receipt` note the lock also serializes the moving-average read-recompute-write (no lost update) and rides `commit=False` callers' transactions (receive_line holds it until its single commit — correct).
- **Done when:** all three functions lock before their first aggregate read; docstrings updated; no behavior change single-threaded.
- **Verify:** `cd backend && .venv/bin/ruff check . && .venv/bin/python -m pytest -q` (all pass, 0 skipped). Concurrency proof lands in Task 7.
- **Parallel-ok:** yes (with 2)

### [x] 2. Serialize receive_line on the PO-header lock (SC1, qty_received ≤ qty_ordered)
- **Files:** `backend/app/modules/syerp/service/purchasing.py`
- **Do:** In `receive_line` (:555), lock the PO header row FOR UPDATE **before** the status guard and the over-receipt guard read (:628): either add `with_for_update()` to `_get_po_row`'s select via a parameter (mirror how `bills.py:486` conditionally applies it) or issue `select(PurchaseOrder.id).where(id == po_id).with_for_update()` right after loading the PO. One PO row serializes ALL concurrent receives on that PO — covering the `line.qty_received` accumulator (invariant qty_received ≤ qty_ordered) AND the header status roll-up read at :686. Lock ORDER is PO → item (post_receipt's Task-1 lock): no other writer takes item→PO, so no cycle — document this ordering in the docstring. Update the docstring guard-order narrative.
- **Done when:** the PO row is locked before the over-receipt guard read; deadlock-order note in docstring.
- **Verify:** `cd backend && .venv/bin/ruff check . && .venv/bin/python -m pytest -q`. Concurrency proof in Task 7 scenario (c).
- **Parallel-ok:** yes (with 1)

### [x] 3. Make post_adjustment bin-aware, wired schema→router (SC3, D-P4-1, D-P4-6)
- **Files:** `backend/app/modules/syerp/service/inventory.py`, `backend/app/modules/syerp/schemas.py`, `backend/app/modules/syerp/router.py`
- **Do:** Add `bin_id: int | None = None` to `AdjustmentCreate` (schemas.py:342, docstring explains explicit-or-unbinned). Add `bin_id: int | None = None` param to `post_adjustment`; pass through in `post_adjustment_endpoint` (router.py:497-523) and include bin_id in the audit `detail`. Service (after Task 1's lock, which must precede these reads): (a) keep the existing per-location floor (D-P8-7 contract, defends already-desync'd legacy data); (b) for `qty_delta < 0` ALSO floor-guard the named pool via `get_bin_on_hand(db, item_id, location_id, bin_id)` + `_adjustment_violates_floor(pool_onhand, qty_delta)` → 422 naming the pool ("unbinned pool" when NULL — status constant convention); (c) write `bin_id` on the InventoryTxn (positive deltas land in the named bin or unbinned pool, D-P4-6). Bin existence/location-membership NOT validated here (D-P12a-3, FK backstop) — say so in the docstring.
- **Done when:** a −N adjust with `bin_id=NULL` at a location whose stock is all in bins 422s ("unbinned pool insufficient"); the same adjust with the bin named succeeds and the ledger row carries that bin_id; positive delta into a named bin raises that bin's `get_bin_on_hand`.
- **Verify:** `cd backend && .venv/bin/ruff check . && .venv/bin/python -m pytest -q`; behavioral assertions land in Task 8 (revised scenario E).
- **Parallel-ok:** yes (with 4, 5 — different functions; coordinate the shared schemas.py edit)

### [x] 4. Make post_transfer bin-aware (from_bin_id), wired schema→router (SC3, D-P4-1, D-P4-5)
- **Files:** `backend/app/modules/syerp/service/inventory.py`, `backend/app/modules/syerp/schemas.py`, `backend/app/modules/syerp/router.py`
- **Do:** Add `from_bin_id: int | None = None` to `TransferCreate` (schemas.py:364). Add the param to `post_transfer` and pass through in `post_transfer_endpoint` (router.py:541+), bin_id in audit detail. Service: keep the per-location source floor; ALSO floor-guard the source pool (`get_bin_on_hand(..., from_bin_id)`, 422 if `-qty` overdraws it). Write `bin_id=from_bin_id` on the `-qty` out leg; the `+qty` in leg keeps `bin_id=NULL` — destination unbinned pool, putaway directs it later (D-P4-5, document in docstring).
- **Done when:** transferring out of a fully-binned location with `from_bin_id=NULL` 422s; naming the bin succeeds, out leg carries the bin_id, in leg is NULL, location roll-up identity stays exact at both locations.
- **Verify:** `cd backend && .venv/bin/ruff check . && .venv/bin/python -m pytest -q`; behavioral assertions in Task 8.
- **Parallel-ok:** yes (with 3, 5)

### [x] 5. Make MOUSSE issue_components bin-aware, wired schema→router (SC3, D-P4-1)
- **Files:** `backend/app/modules/mousse/schemas.py`, `backend/app/modules/mousse/service.py`
- **Do:** Add `bin_id: int | None = None` to `IssueLine` (schemas.py ~:146, docstring: NULL = unbinned pool only). In `issue_components` (service.py:580): carry bin_id through `resolved`; extend the floor-guard key from `(item_id, location_id)` to `(item_id, location_id, bin_id)` (:690-708) and read the base pool via SYERP's `get_bin_on_hand` (null-aware) instead of the location-level `_component_onhand` — duplicate lines on the same pool still accumulate (keeps the jointly-overdraw guard); write `bin_id` on each issue InventoryTxn (:715). The sorted-id item lock (:679-685) already precedes the reads — unchanged. Leave the release-time availability check (`_component_onhand` at :297) location-level — it is informational availability, not a floor guard; note in its docstring that a fully-binned location will require bin_ids at issue time (D-P4-1 accepted behavior change). Router (`mousse/router.py:172`) passes the request straight through — no change beyond docstring.
- **Done when:** issuing with `bin_id=NULL` against a fully-binned location 422s naming the unbinned pool; issuing with the bin named succeeds, txn rows carry bin_id, JE/WIP amounts unchanged (no GL change — if any JE change becomes necessary, STOP and flag).
- **Verify:** `cd backend && .venv/bin/ruff check . && .venv/bin/python -m pytest -q`; mixed-path + bin behavior proven in Tasks 7–8.
- **Parallel-ok:** yes (with 3, 4)

### [x] 6. Truth-up the bin trust-boundary documentation (SC3 closure)
- **Files:** `backend/app/modules/syerp/service/inventory.py`, `backend/app/modules/gelato/service.py` (if it re-exports/wraps `get_bin_on_hand` or `list_unbinned_stock` docs), `.zj/BACKLOG.md`
- **Do:** Rewrite the `get_bin_on_hand` TRUST BOUNDARY note (:613-621) — after this phase every draw primitive is bin-aware, the split no longer rots; state the new invariant (all pools ≥ 0 for post-Phase-4 data; pre-existing desync'd rows are historical). Update the `list_unbinned_stock` `>0` filter comment: the filter no longer hides live negatives (they can't newly occur), it only masks legacy desync — keep the filter, document that. Update the inventory.py section banners that say "ONLY putaway is bin-aware". Mark the BACKLOG "Bin split desyncs" item's inbound half as closed by this phase (final check-off happens at verify).
- **Done when:** no docstring/comment claims post_transfer/post_adjustment/MOUSSE issue are bin-blind.
- **Verify:** `grep -rn "bin-blind\|bin-BLIND" backend/app/ | grep -iv "historical\|legacy\|was"` returns nothing misleading; `cd backend && .venv/bin/ruff check .`.
- **Parallel-ok:** no (after 3–5)

### [x] 7. Write verify_inventory_race.py — mixed-path concurrency, mutation-proven (SC2, SC1)
- **Files:** `backend/scripts/verify_inventory_race.py` (new)
- **Do:** Model on `verify_gelato.py` (own engine from `POSTGRES_*`, `sys.path` shim, PASS/FAIL + non-zero exit, uniquely-suffixed throwaway items, finally-block cleanup, `asyncio.Barrier(2)` + independent sessions + connection pre-warm, several iterations per race). Drive services through the REAL request schemas/service signatures the routers use (11a/11b keeper). Scenarios — **fixture rule (12b keeper): ample stock everywhere except the ONE contended invariant, so only the guard under test can reject; pick indivisible-remainder quantities (2b keeper), e.g. pool 10, competing draws of 7 (7+7=14>10, remainder 3):**
  - (a) **MOUSSE issue × SYERP adjust** (the SRD's named mixed pair): WO component with plentiful stock at a second location, contended item/location holds 10; MOUSSE issues 7 while `post_adjustment` draws −7 concurrently. Exactly one succeeds, other 422s, final on-hand 3 or the issue's WIP value matches the single success — derived on-hand NEVER < 0.
  - (b) **adjust × transfer** on the same source pool: same 10/7/7 shape.
  - (c) **receive_line × receive_line** on ONE PO line (ordered 10, two concurrent receives of 7): exactly one succeeds; `qty_received ≤ qty_ordered` holds; header status correct.
  - (d) **receipt × receipt** moving-average integrity: two concurrent `post_receipt`s with costs/qtys whose weighted average has an indivisible remainder; final `moving_avg_cost` equals the sequential two-receipt computation exactly (lock prevents the lost update).
  Document the mutation-proof procedure in the script docstring and EXECUTE it during build, recording results in the checklist + build SUMMARY:

  | # | Lock removed (revert) | Expected RED | Restored GREEN |
  |---|---|---|---|
  | M1 | Task-1 lock in `post_adjustment` | (a) on-hand driven negative / both succeed | (a) exactly one 422 |
  | M2 | Task-1 lock in `post_transfer` | (b) breaches | (b) passes |
  | M3 | Task-2 PO lock in `receive_line` | (c) qty_received > qty_ordered | (c) passes |
  | M4 | Task-1 lock in `post_receipt` | (d) moving-avg lost update | (d) passes |

  Note (a) also RED-proves the discipline is SHARED: MOUSSE's own lock alone cannot save it when the adjust path is unlocked. Remember this script auto-runs in CI's `verify-scripts` job — it must pass on a fresh CI database (no reliance on local leftovers; seed everything it needs; self-clean).
- **Done when:** script exits 0 with all scenarios PASS on the live stack; all four mutations demonstrated RED then GREEN and recorded.
- **Verify:** `podman-compose -f compose/compose.yml -f compose/compose.dev.yml up -d db api && podman exec -e PYTHONPATH=/app compose_api_1 python scripts/verify_inventory_race.py` → exit 0.
- **Parallel-ok:** no (after 1–5)

### [x] 8. Revise verify_gelato.py scenario (E) to assert the fix (SC3)
- **Files:** `backend/scripts/verify_gelato.py` (:68-74 header, :393-444 body)
- **Do:** Replace the pin with the fixed contract: receive 10 unbinned → putaway all 10 into bin E1 → (E1) bin-blind `post_adjustment(-10, bin_id=None)` now **422s** with NO ledger rows written (row-count unchanged — reuse the `_txn_count` pattern from scenario C); (E2) `post_adjustment(-10, bin_id=bin_e)` **succeeds**; bin pool → 0, unbinned stays 0, never negative; (E3) roll-up identity Σ bins + unbinned == location total == 0 Decimal-EXACT still holds. Update the module docstring scenario list and drop the "12b closes it / BACKLOG p2" pin language.
- **Done when:** scenario E asserts the fix and the whole script exits 0.
- **Verify:** `podman exec -e PYTHONPATH=/app compose_api_1 python scripts/verify_gelato.py` → exit 0.
- **Parallel-ok:** yes (with 7)

### [x] 9. Behavior-change regression sweep — reconcile every breakage (SC5, keeper 6)
- **Files:** whatever the sweep flags — candidates: `backend/scripts/verify_inventory.py`, `verify_mousse.py`, `verify_purchasing.py`, `verify_gelato_ship.py`, `verify_e2e_p8.py`, the `*_api.py` siblings, `backend/tests/**`
- **Do:** Run ALL `verify_*` scripts (non-API via the podman exec recipe; `_api.py` per their headers) + full backend pytest. For EVERY failure classify: (a) D-P4-1 working as intended (a fixture putaways then draws bin-blind, or draws at a binned location without a bin) → revise the fixture/assertion and say so in the commit message; (b) a real regression → fix the code. Confirm Trial Balance nets zero (`verify_reports.py`/`verify_gl.py` assertions). Zero pytest skips.
- **Done when:** every `verify_*` exits 0, pytest fully green 0 skipped, each reconciliation documented in the checklist.
- **Verify:** `podman exec -e PYTHONPATH=/app compose_api_1 sh -c 'cd /app && for s in scripts/verify_*.py; do case "$s" in *_api.py) continue;; esac; PYTHONPATH=/app python "$s" || exit 1; done'` and `cd backend && .venv/bin/python -m pytest -q`.
- **Parallel-ok:** no (after 7, 8)

### [x] 10. FE: bin picker on StockAdjustDialog + Vitest payload assertion (SC4)
- **Files:** `frontend/src/routes/syerp/components/StockAdjustDialog.tsx`, `StockAdjustDialog.test.tsx`
- **Do:** Add an optional "Bin" select fed by `useBins(locationId)` (`frontend/src/routes/gelato/hooks.ts:216`), rendered once a location is chosen; default option "Unbinned pool" → `bin_id: null`. Degrade gracefully when the bins query errors or returns empty (GELATO off / unbinned location): hide the select, send `bin_id: null`. Extend the in-file `AdjustmentPayload` type (~:165). Vitest: mock the bins response, select a bin, submit, and assert the REAL POST body contains `bin_id: <n>` (and `bin_id: null` when untouched) — the payload assertion is the point, not the render.
- **Done when:** an adjust posted from the UI at a binned location carries the chosen bin_id end-to-end; Vitest asserts both payload shapes.
- **Verify:** `cd frontend && npm run test -- --run StockAdjustDialog && npm run lint && npm run build`.
- **Parallel-ok:** yes (with 11, 12)

### [x] 11. FE: from-bin picker on StockTransferDialog + Vitest payload assertion (SC4)
- **Files:** `frontend/src/routes/syerp/components/StockTransferDialog.tsx`, `StockTransferDialog.test.tsx`
- **Do:** Same pattern as Task 10, keyed off the SOURCE location: `useBins(fromLocationId)`, optional `from_bin_id`, "Unbinned pool" default, graceful degradation. No destination bin control (D-P4-5 — arrives unbinned; a helper caption "arrives in destination's unbinned pool — direct it with Putaway" is welcome). Vitest asserts the POST body `from_bin_id` both ways.
- **Done when:** UI transfer at a binned source carries `from_bin_id`; Vitest asserts the payload.
- **Verify:** `cd frontend && npm run test -- --run StockTransferDialog && npm run lint && npm run build`.
- **Parallel-ok:** yes (with 10, 12)

### [x] 12. FE: per-line bin picker on IssueComponentsDialog + Vitest payload assertion (SC4)
- **Files:** `frontend/src/routes/mousse/components/IssueComponentsDialog.tsx`, `IssueComponentsDialog.test.tsx`
- **Do:** Per component line, an optional bin select fed by `useBins(<draw location>)` — the draw location is the line's `location_id` if the dialog exposes one, else the WO's `target_location_id` (check the dialog's current shape; it currently omits location and lets the server default). Same "Unbinned pool"/degradation semantics. Vitest asserts the issue POST body lines carry `bin_id` when chosen and `bin_id: null` (or absent) otherwise.
- **Done when:** a UI issue at a binned location can name the bin per line; Vitest asserts the real request lines.
- **Verify:** `cd frontend && npm run test -- --run IssueComponentsDialog && npm run lint && npm run build`.
- **Parallel-ok:** yes (with 10, 11)

### [x] 13. Full-gate run + bookkeeping (SC5, SC6)
- **Files:** `.zj/SRD.md` (NFR-7 status + evidence), `docs/features/requirements-progress.md`, `.zj/DECISIONS.md` (append D-P4-1..6), `.zj/STATE.md`, `docs/tasks/chore-inventory-race-safety.md`
- **Do:** Push the branch; confirm all four CI jobs green (the new verify script runs in `verify-scripts`). Flip SRD NFR-7 → done pending verify with the evidence summary (lock table, mutation table results, scenario-E revision, bin-aware payload proofs). Add the requirements-progress row. Append decisions. Update STATE.md (next: `/zj:verify 4`). Complete + archive the checklist per convention.
- **Done when:** CI green on the branch tip; SRD/progress/decisions/state updated.
- **Verify:** `gh run list --branch chore-inventory-race-safety --limit 4` shows all jobs success; `grep -n "NFR-7" .zj/SRD.md` shows the flipped status.
- **Parallel-ok:** no (last)

## Risks

- **D-P4-1 breaks more existing fixtures than expected** (the accepted behavior change ripples through GELATO/MOUSSE verify scripts and e2e flows that putaway then draw). Early sign: Task 9 sweep flags failures outside `verify_gelato.py` scenario E — budget for it; every reconciliation must be classified (a)/(b), never silently patched.
- **Lock-ordering deadlock across PO→item vs multi-item paths.** receive_line takes PO then item; MOUSSE takes items sorted; adjust/transfer take one item. No cycle exists today, but a future writer taking item→PO would create one. Early sign: verify_inventory_race.py hangs/times out under CI. Mitigation: the ordering note in Task 2's docstring is the contract.
- **CI verify-scripts job flakes on the new race script** (timing-sensitive scenarios on shared runners). Mitigation baked in: barrier + independent pre-warmed sessions + multiple iterations (the verify_gelato.py scenario-D recipe, already CI-proven). Early sign: intermittent (a)/(b) failures on re-run.
- **Bins API unavailable to SYERP/MOUSSE screens when GELATO is toggled off** — the picker must degrade to unbinned-only rather than break the dialogs (explicit in Tasks 10–12). Early sign: dialog Vitest or manual smoke shows an error state when bins 404.
- **Hidden GL/JE or migration need** — none expected; any task discovering one STOPS and flags (plan assumption invalidated).

## Out of scope

- GELATO pick-path Q1/Q2 shipment-header races (D-P4-3 — BACKLOG p2).
- Server-side bin auto-allocation / suggested-bin logic on draw paths (D-P4-1 forbids; putaway suggestions already exist and are untouched).
- Destination-bin selection on transfers (D-P4-5 — arrives unbinned, directed by putaway).
- Repairing pre-existing (historical) bin-split desync data; `list_unbinned_stock` keeps its `>0` filter (Task 6 documents why).
- Audit-write atomicity (separate BACKLOG item, pre-CRISP).
- Moving-average *policy* changes — only the lost-update race is fixed; the weighted formula is untouched.

## Deviations

- **T0 (trivial, precedent 12a/12b/P3):** branch cut off the plan-carrying tip `7a71fd0`
  (docs-only atop the D-P4-4 base `db725fd`, `git diff db725fd..7a71fd0` touches `.zj/` only)
  so PLAN.md rides the branch — a bare-`db725fd` branch would have dropped the plan.
- **Manager (process):** T1/T2 and T3/T4/T5 parallel groups executed by ONE engineer each,
  serialized — every backend task's Verify runs the full pytest suite against the single
  shared `biznice_test` DB, and parallel engineers would share one git index (Phase 2b
  serialization precedent). T3–5's shared `schemas.py` edit is coordinated inside one context.

- **T1 (trivial, fix-forward):** `post_receipt` additionally does `await db.refresh(item)` while
  holding the lock — `item` is loaded before the lock, so the identity map would otherwise serve a
  stale pre-lock `moving_avg_cost` and the documented "no lost update on the moving average" claim
  would be false. One extra SELECT, no single-threaded behavior change. T7 M4 exercises it.

- **T5 (trivial):** the plan's `IssueLine` schema class is actually named `IssueComponentLine` —
  edited that; `mousse/router.py` (docstring-only change the task text specifies) added to the
  task's file list.

- **T6 (trivial):** `gelato/service.py` is actually a package — the `list_unbinned_stock` filter
  docs live in `gelato/service/putaway.py` (edited there); the "ONLY putaway is bin-aware" banner
  was a single docstring occurrence, plus one additional stale 12b `post_issue` banner
  ("per-location floor instead") fixed. T7/T8 serialized by the manager (mutation reverts touch
  bind-mounted product code the api container hot-reloads — concurrent script runs would race them).

- **T7 (trivial, recorded):** M3's RED manifests as BOTH receives landing (2 receipt txns + double
  GL post, accumulator lost-update stuck at 7) rather than the literal `qty_received > qty_ordered`
  — the ORM read-modify-write overwrites; scenario pins `successes==1` and `line_receipts==1`, so
  it is non-vacuous. M4 went RED on the lock-alone revert (refresh kept) AND on lock+refresh —
  both recorded in the checklist table.

- **T12 (trivial, direct consequence):** `WorkOrderComponentRead` has no per-line `location_id`, so
  the dialog draws at the WO's `target_location_id` — which the dialog didn't receive; added a
  required `targetLocationId` prop wired from `WorkOrderDetail.tsx` (its only host) and reconciled
  the two affected host-screen tests (`WorkOrderDetail.test.tsx` payload now carries `bin_id: null`;
  `InventoryItemDetail.test.tsx` URL-routes the new bins GET). Dialog test files moved from blanket
  `mockResolvedValue` to the codebase's URL-routed mock pattern so locations + bins GETs coexist.

## Noticed

- T1 engineer: the same identity-map staleness shape exists in `post_transfer`/`post_putaway`/
  `post_issue` where `unit_cost = item.moving_avg_cost` values a leg — there it's valuation
  metadata only (no read-modify-write accumulator), matches the pre-existing post_putaway shape;
  left untouched. Worth a look at verify/retro.
- Product-wide `status.HTTP_422_UNPROCESSABLE_ENTITY` usages emit a Starlette deprecation warning
  (`HTTP_422_UNPROCESSABLE_CONTENT` is the successor) — pre-existing, cosmetic; sweep candidate.
- `verify_purchasing.py` cleanup leaves its `po_receipt`-sourced JEs behind on every run (orphan
  source rows accumulate in dev DBs); the new `verify_inventory_race.py` cleans its own.
- `useBins` has no `retry: false` — a GELATO-off deployment retries the bins GET 3× per location
  before the pickers degrade; harmless but noisy, tweak candidate.
- In-container pytest can't write `/app/.pytest_cache` (rootless bind-mount ownership) — benign
  cache warning.

### Verify fix loop (2026-07-25, `3126c48..3253917`)

- **Fixed (review major #1):** MOUSSE `issue_components` had dropped its per-location floor when
  it went pool-aware — restored beside the pool floor (`2a87f6d`), pinned by `verify_mousse.py`
  scenario G2 (legacy-desync fixture, mutation-proven RED→GREEN).
- **Fixed (verifier major gap):** the hand-checked bin behaviors now have durable CI pins —
  `verify_gelato.py` scenario F (binned transfer + D-P4-5 legs + D-P4-6 positive-into-bin,
  `c692498`) and `verify_mousse.py` scenario G (binned issue, `3f45685`).
- **Fixed (review minor #3):** `post_transfer` now `db.refresh(item)` under the lock before leg
  valuation (`5a45a7b`) — no more stale moving-avg cost provenance on transfer legs.
- **Deferred to BACKLOG (review minor #2, decision needed):** positive adjustment accepts an
  unvalidated `bin_id` → can strand stock in a foreign-location bin pool (p2 entry, owner call:
  membership check vs. accept).
- **Deferred to BACKLOG (review questions):** GELATO `pick_for_shipment` unsorted item-lock
  acquisition (p2); `TransactionRead` omits `bin_id` + MOUSSE issue audit lacks per-line bins (p3).
- Reviewer notes the same pre-lock `moving_avg_cost` staleness shape remains in the pre-existing
  `post_issue`/`post_putaway` (valuation metadata on legs) — left untouched, matches the build
  engineer's T1 Noticed entry above; fold into any future touch of those functions.
