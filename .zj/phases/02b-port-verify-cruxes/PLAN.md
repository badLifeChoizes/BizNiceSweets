# Plan: 02b — Port the DoD-named verify_* cruxes into the repaired pytest suite
Goal: The DoD-named crux behaviors (inventory moving-avg, GL/AP/AR posting ties, MOUSSE WIP-clears, CRUMB reservation, GELATO ship COGS) run inside the ordinary `pytest` suite, so reverting a crux turns a *pytest* test red — not only a `verify_*` script — with the full suite still green at 0 skips.
Status: draft

## Success criteria
Implements **NFR-5** (`.zj/SRD.md`; roadmap Phase 2, the 2b half of the D-P2a-2 split). Concurrency mutation-proofs STAY in `verify_*` (D-P2a-2) and are NOT ported.

- **SC1 — cruxes present & green in pytest (0 skips):** each DoD crux is covered by a suite test that passes:
  (a) inventory moving-average via the SERVICE path (`post_receipt` 10@2 then 10@4 → `item.moving_avg_cost == Decimal("3.000000")`), not only the pure `compute_new_moving_avg` helper;
  (b) GL posting ties (balanced JE, derived balances, receipt auto-post Dr 1130/Cr 2150);
  (c) AP posting ties (bill Dr GR-IR-or-expense/Cr 2110, payment Dr 2110/Cr cash, GR/IR clears to zero, AP control ↔ subledger equality);
  (d) AR posting ties (invoice Dr 1120/Cr 4110, receipt Dr cash/Cr 1120, aging ties Decimal-exact to the debit-normal 1120 control);
  (e) MOUSSE WIP-clears (1140 clears to pre-issue value Decimal-exact AND 1130 control ties to subledger incl. the 5190 rounding residual);
  (f) CRUMB reservation (`qty_reserved = min(qty_ordered, available)`, `available = on_hand − Σ other-open reservations`, non-stock reserves 0, cancel releases);
  (g) GELATO ship COGS (one balanced JE Dr 5100 == Cr 1130 == Σ qty×moving_avg, reservation relief, 1130 control move ties inventory-value move).
- **SC2 — non-vacuity per crux:** for EACH crux a documented product mutation turns a NAMED pytest test RED; reverting restores green (the DoD's "reverting a crux turns a pytest test red, not only a verify_* script").
- **SC3 — new packages + one HTTP audit/RBAC per new module:** new pytest packages under `backend/tests/` for `mousse/`, `crumb/`, `gelato/`, plus AR tests added to `syerp/`. Accounting cruxes asserted at the SERVICE layer via `async_db_session`/`test_sessionmaker`. PLUS one representative HTTP-level test per NEW module surface (MOUSSE/CRUMB/GELATO/AR) driving the `client` fixture, asserting 401 (no token) / 403 (wrong permission) / 200-or-201 (authorized) AND an attributable `AuditLog` row — mirroring the `verify_*_api.py` split. Inventory's audit/RBAC covered too (owner decision 3).
- **SC4 — suite stays healthy:** full `pytest -q` GREEN with **0 skipped**, back-to-back rerunnable, and `tests/test_harness_selfcheck.py` still passes.
- **SC5 — scripts & product unchanged:** the 23 `backend/scripts/verify_*.py` still exit 0; **`git diff -- backend/app/` is empty** at phase end (TEST-ONLY phase). A genuine product bug found while porting is fixed minimally and flagged in `## Noticed`; a schema/Alembic need means STOP + flag owner.
- **SC6 — SRD caveats dropped:** the "script-only / UI-flow-UAT-pending" caveats NFR-5 says the SYERP/MOUSSE/CRUMB/GELATO SRD rows carry are dropped; NFR-5 flips `partial (2a done / 2b pending)` → done; `docs/features/requirements-progress.md` updated.

## Context
- **Branch (D-P2b):** cut `chore-port-verify-cruxes` off the CURRENT tip of `chore-pytest-harness-repair` = **`f97b21a`** (retro docs atop the verified 2a code tip `14d838b` / tag `zj/good-02a-pytest-harness-repair`, code-identical). Cutting the tip (not the bare tag) lets PLAN.md travel onto the build branch — the 12a/12b/13/2a precedent. v4.0 stack stays unmerged to milestone close. Conventional commits (`test:`/`chore:`/`fix:`), **NO** co-authored / generated-with-Claude lines. Checklist at `docs/tasks/chore-port-verify-cruxes.md`.
- **Repaired-harness fixtures to REUSE (do NOT build a new engine)** — `backend/tests/conftest.py` + `backend/tests/auth/conftest_helpers.py`:
  - `test_sessionmaker` → the NullPool `TestSessionLocal`; open a raw session with `async with test_sessionmaker() as s`.
  - `async_db_session` → a ready NullPool `AsyncSession` (from `conftest_helpers`; import into new packages).
  - `client` → httpx-ASGI client driving the app's own `get_db` (overridden onto the test engine).
  - function-scoped autouse `_isolate` → TRUNCATE-all + reseed `seed_admin_user` + `User(id="admin-user")` (wildcard admin) + roster (`syerp-reader`→`syerp:read`, `regular-user-id`→`syerp:read`) before EVERY test.
  - `create_access_token(subject=<id>, permissions=[…])` mints tokens; **RBAC reads the DB user's roles, NOT the token claim** (D-P2a-4) — so an HTTP RBAC test must seed a real limited User to get a genuine 403.
  - `skip_if_no_db` is a **retired no-op**; DB is a hard requirement — do NOT gate new tests on it.
- **The `_isolate` baseline seeds only auth** — NOT the chart of accounts nor the default stock location. Every accounting/inventory ported test must seed them itself: `seed_gl_accounts` (`app/modules/syerp/coa_seed.py:102`) + `seed_default_location` (`app/modules/syerp/inventory_seed.py:29`). Both are idempotent. The CoA seed covers all accounts the cruxes need: **1110 1111 1120 1130 1140 2110 2150 4110 5100 5190** (verified). Task 1 adds one shared opt-in `seeded_ledger_db` fixture so each test gets these without duplication.
- **Crux-source map (read each for the EXACT scenario + Decimal values — do NOT invent numbers; port only the sequential scenarios, leave `asyncio.gather`/`Barrier`/`FOR UPDATE` in the scripts):**
  | Crux | Script | Sequential scenario(s) to port | Headline Decimal |
  |---|---|---|---|
  | inventory moving-avg | `verify_inventory.py` | 3 (10@2,10@4→3.0), 4 (on-hand 20/value 60), 5 (neg-adj reject, avg unchanged), 6 (transfer, avg unchanged) | `moving_avg_cost == 3.000000` |
  | GL ties | `verify_gl.py` | (a) balanced post / unbalanced 422, (c) derived balances 60/−60 + register [10,30,60], (b) reversal, (d) receipt auto-post Dr 1130/Cr 2150 == 20 | receipt JE == `20.000000` |
  | AP ties | `verify_ap.py` | (d) post_bill Σdebits==Cr 2110==20, (e) THE CRUX GR/IR clears to pre-receipt (Decimal-exact), (f) payment Dr 2110/Cr cash, partial→final→paid + **AP control ↔ subledger equality** | GR/IR `grir_post == grir_pre` |
  | AR ties | `verify_ar.py` | (B) invoice Dr 1120/Cr 4110 == 160, receipt Dr cash/Cr 1120, aging `grand_total == control_balance` Decimal-exact at each stage; (C) over-invoice 422; (D) over-receipt 422. (Drives the REAL GELATO ship flow to make shipped SO lines — the 11a/11b keeper) | control move `== 160`, aging in_balance |
  | MOUSSE WIP-clears | `verify_mousse.py` | (A) issue Dr 1140/Cr 1130 == 210, complete → 1140 back to pre-issue exact; (D) under-issue override → 1140 clears exact + 1130 debit == 99.999999 + 5190 residual tie | 1140 `post_complete == pre_issue == 0` |
  | CRUMB reservation | `verify_crumb_so.py` | (E) SO_E1 reserve 6, SO_E2 cap min(8,4)=4 + shortage 4 + non-stock reserves 0, `available == on_hand − Σ open`, cancel releases, SO_E3 reserve 5 | reserved `min(qty, avail)` |
  | GELATO ship COGS | `verify_gelato_ship.py` | (a) pick→pack→ship, (b) one JE Dr 5100==Cr 1130==8×7.5==60.000000, (c) reservation relief accuracy, (d) partial-ship accrual + over-ship 422, (f) 1130 control move == subledger move | COGS `60.000000` |
- **HTTP audit/RBAC pattern** (`verify_mousse_api.py` etc. are the model): mint read/write/noperm identities as real Users bound to real Roles, then assert per route: write token→2xx, read-only token→403, no token→401, and a matching `AuditLog(action, actor_id, target_type, target_id)` row after a successful mutation. Action strings + perms (verified): MOUSSE `work_order.created` / `mousse:read|write`; CRUMB `sales_order.created` / `crumb:read|write`; GELATO `shipment.picked|shipped` (target_type `shipment`) / `gelato:read|write`; AR `invoice.created` / `syerp:read|write`. `AuditLog` model: `app/modules/auth/models.py:135` (`actor_id`, `action`, `target_type`, `target_id`).
- **Real service entry points** (import as the scripts do): `app.modules.syerp.service` (`post_receipt`, `post_adjustment`, `post_transfer`, `get_item`, `get_item_onhand`, `post_journal_entry`, `reverse_journal_entry`, `derive_account_balance`, `get_account_register`, `receive_line`, `create_bill`, `post_bill`, `record_payment`, `trial_balance`); `app.modules.syerp.service.ar` (`create_invoice`, `post_invoice`, `record_receipt`, `list_uninvoiced_shipments`); `app.modules.syerp.service.reports` (`ar_aging_report`); `app.modules.mousse.service`; `app.modules.crumb.service`; `app.modules.gelato.service`.
- **Recurring keepers (LEARNINGS):** protect a GL control account by asserting it DIRECTLY against its subledger (`control == Σ subledger`), never against zero/TB (bake into AP/AR/MOUSSE/GELATO cruxes); when one mutation posts to N accounts, enumerate an invariant per account; re-confirm types/import paths against source; a fix for "X silently passes" ships a RED-on-regress test (SC2 mirrors this per crux).
- **No product change** (SC5): if porting surfaces a genuine bug, fix minimally + flag in `## Noticed`; a schema/Alembic need → STOP + flag owner.

## Decisions
- **D-P2b-1 (single phase 2b, not sub-split — owner):** each crux is a bounded sequential assertion sharing the repaired-harness pattern; no concurrency to port, so the split-driving risk isn't present.
- **D-P2b-2 (coverage depth = headline + key supporting asserts — owner):** the headline red-on-revert assertion PLUS its close supporting sequential asserts (control↔subledger EQUALITY, negative-path rejects, tie-outs). NOT a full re-port of every verify assertion; NOT minimal-headline-only. Concurrency scenarios stay in `verify_*` (D-P2a-2).
- **D-P2b-3 (audit/RBAC = one HTTP audit+RBAC test per NEW module — owner):** MOUSSE/CRUMB/GELATO/AR at the `client` HTTP layer; all other accounting cruxes at the service layer. Inventory's audit/RBAC (named in the SRD) covered too.
- **D-P2b-4 (architect — HTTP RBAC identity mechanism):** the four HTTP audit/RBAC tests mint their own throwaway read/write/noperm Users+Roles inside a **local per-test fixture** (mirroring `verify_*_api.py`), NOT by extending the shared `_isolate` roster. *Why:* HTTP RBAC needs three identities × four modules = 12 rows; loading them into `_isolate` would tax all ~219 existing tests on every function-scoped truncate+reseed, for no benefit to service-layer tests. Local creation runs after `_isolate` on the clean per-test DB and is swept by the next test's TRUNCATE — no cleanup code needed.
- **D-P2b-5 (architect — AR service crux drives the real ship flow):** the ported AR test seeds its shipped SO lines by driving the REAL GELATO `execute_putaway/pick/pack/ship` + CRUMB `create_sales_order/confirm_sales_order` (the `verify_ar._seed_shipped_line` shape), NOT by hand-stamping `qty_shipped` / hand-posting COGS. *Why:* the 11a/11b keeper — hand-fed shapes the UI never sends have twice certified dead features green; the AR match must run against genuinely-shipped qty and a genuinely-posted COGS JE.
- **D-P2b-6 (architect — new test files, do not edit the pure ones):** ported service cruxes go in NEW files (`test_inventory_service.py`, `test_gl_posting.py`, `test_ap_posting.py`, `test_ar.py`, `tests/mousse/…`, `tests/crumb/…`, `tests/gelato/…`) so the existing pure/no-DB tests (`test_ap.py`, `test_gl.py`, `test_inventory.py`, `test_gl_journal.py`, `test_purchasing.py`) are untouched and stay green.

## Decisions needed
None — the owner answers (1–3) plus D-P2b-4..6 fully bound the scope. If Wave A/B porting surfaces a product bug requiring a schema change, that is the one STOP-and-flag trigger (SC5) — surface it in `## Noticed`, do not decide it here.

## Tasks

### [x] 0. Cut branch and open checklist
- **Files:** `docs/tasks/chore-port-verify-cruxes.md` (new)
- **Do:** `git checkout -b chore-port-verify-cruxes f97b21a`. Create the checklist file mirroring this task list.
- **Done when:** branch exists at `f97b21a`; checklist committed (`chore:`).
- **Verify:** `git branch --show-current` == `chore-port-verify-cruxes`; `git log --oneline -1` tip == `f97b21a`.
- **Parallel-ok:** no (gates everything) — serves all SCs.

---
### Wave A — port the DoD cruxes at the service layer (NFR-5, SC1 + SC3-service + SC5)
> Each Wave-A task creates a NEW test file (D-P2b-6), imports the REAL service fns + the repaired fixtures, seeds `seeded_ledger_db` where accounting is involved, and asserts the headline crux + its close supporting asserts (D-P2b-2). Each embeds a red-on-revert note keyed to the SC2 table in Task 14. Wave-A tasks are independent across modules → parallelizable once Task 1 lands.

### [x] 1. Scaffold the new packages + the shared ledger-seed fixture
- **Files:** `backend/tests/mousse/__init__.py`, `backend/tests/crumb/__init__.py`, `backend/tests/gelato/__init__.py` (new, each with a 2-line ABOUTME); `backend/tests/conftest.py` (add ONE opt-in fixture `seeded_ledger_db`).
- **Do:** Create the three empty test packages. Add a function-scoped, **non-autouse** fixture `seeded_ledger_db` to the root conftest that, on `TestSessionLocal()`, runs `await seed_gl_accounts(session)` then `await seed_default_location(session)` (both idempotent) and yields the session — the single opt-in every accounting/inventory ported test depends on. No autouse (keeps the 219 existing tests' baseline unchanged).
- **Done when:** the three packages import cleanly; `seeded_ledger_db` seeds ≥40 GL accounts + exactly one "Main" location; the existing suite is unaffected.
- **Verify:** `podman exec -e PYTHONPATH=/app compose_api_1 sh -c 'cd /app && python -m pytest tests/syerp -q'` still green (baseline untouched).
- **Parallel-ok:** no (Wave A depends on this) — serves SC1/SC3.

### [x] 2. Port the inventory moving-average SERVICE crux (SC1a)
- **Files:** `backend/tests/syerp/test_inventory_service.py` (new)
- **Do:** Mirror `verify_inventory.py` scenarios 3–6 via the SERVICE path using `test_sessionmaker`/`async_db_session` + `seeded_ledger_db`: create an item + two locations (`create_item`/`create_location`); `post_receipt` 10@2 then 10@4 → assert `get_item(...).moving_avg_cost == Decimal("3.000000")`; `get_item_onhand` → loc-A qty 20, total 20, value `60.000000`; a `post_adjustment(-999)` raises `HTTPException`, appends NO txn row, avg still `3.000000`; a valid `post_transfer` A→B leaves total 20, moves per-location, avg unchanged, two legs one `transfer_group_id`. This is the gap the pure `compute_new_moving_avg` test (`test_inventory.py`, 29 tests) does not cover.
- **Done when:** the file passes, 0 skips; the moving-avg assertion is SERVICE-path (goes through `post_receipt`, not the helper).
- **Verify:** `podman exec -e PYTHONPATH=/app compose_api_1 sh -c 'cd /app && python -m pytest tests/syerp/test_inventory_service.py -q'`
- **Parallel-ok:** yes — serves SC1a; red-on-revert = SC2 row (inventory).

### [x] 3. Port the GL posting-ties crux (SC1b)
- **Files:** `backend/tests/syerp/test_gl_posting.py` (new)
- **Do:** Mirror `verify_gl.py` (a)(c)(b)(d) via the service layer + `seeded_ledger_db`: two throwaway GL accounts; `post_journal_entry` balanced (Dr A 10/Cr B 10) persists 2 lines, unbalanced (10/5) raises `HTTPException` 422 and persists nothing; post the 10/20/30 series → `derive_account_balance` A==60, B==−60, `get_account_register` running == [10,30,60] with opening 0/closing 60; `reverse_journal_entry` swaps legs + links `reversal_of_id`, original immutable; then the receipt auto-post — build vendor/item/loc/PO/approve, `receive_line` 4@5 → exactly ONE `po_receipt` JE source-linked to the line, balanced Dr 1130 / Cr 2150 == `20.000000`, and 2150 derived balance moved −20 / 1130 +20.
- **Done when:** the file passes, 0 skips; the receipt auto-post asserts BOTH the 1130 debit and 2150 credit legs (per-account invariant, keeper).
- **Verify:** `podman exec -e PYTHONPATH=/app compose_api_1 sh -c 'cd /app && python -m pytest tests/syerp/test_gl_posting.py -q'`
- **Parallel-ok:** yes — serves SC1b; red-on-revert = SC2 row (GL).

### [x] 4. Port the AP posting-ties crux incl. GR/IR-clears-to-zero (SC1c)
- **Files:** `backend/tests/syerp/test_ap_posting.py` (new)
- **Do:** Mirror `verify_ap.py` (d)(e)(f) + control↔subledger equality via the service layer + `seeded_ledger_db`. Shared vendor/item/location. (d) `post_bill` on a matched 4@5 bill posts ONE balanced JE `source_type='ap_bill'`, Σ debits == Cr 2110 == 20, Dr 2150 == 20; re-post 422. **(e) THE CRUX:** capture `derive_account_balance(2150)` pre-receipt; receive 7@5 (Cr 2150 −35), `make matched bill` + `post_bill` (Dr 2150 35) → 2150 balance EQUALS its pre-receipt value Decimal-exact. (f) `record_payment` partial 20 of 50 → bill 'posted' open 30, JE Dr 2110/Cr 1110 == 20; final 30 → 'paid' open 0. **AP control ↔ subledger EQUALITY (keeper):** assert `derive_account_balance(2110) == Σ(open_balance across posted/unpaid bills)` — not "TB nets zero". Also the overpayment-refused-422-persists-nothing negative path.
- **Done when:** file passes, 0 skips; the GR/IR crux asserts Decimal-exact equality to the pre-receipt value; the 2110 control is asserted DIRECTLY against the bill subledger.
- **Verify:** `podman exec -e PYTHONPATH=/app compose_api_1 sh -c 'cd /app && python -m pytest tests/syerp/test_ap_posting.py -q'`
- **Parallel-ok:** yes — serves SC1c; red-on-revert = SC2 row (AP).

### [x] 5. Port the AR posting-ties crux incl. aging↔1120 tie-out (SC1d)
- **Files:** `backend/tests/syerp/test_ar.py` (new)
- **Do:** Mirror `verify_ar.py` (B)(C)(D) via the service layer + `seeded_ledger_db`. Seed genuinely-shipped SO lines by driving the REAL flow (D-P2b-5): receipts 100@6+100@9 (moving_avg 7.5), putaway into a pick bin, `create_sales_order`/`confirm_sales_order` order 8 @ 20, `execute_pick`/`execute_pack`/`execute_ship`. Then: `create_invoice` from the shipped SO line → total 160, line price LOCKED to SO unit_price 20, `qty_invoiced` bumped to 8; `post_invoice` → Dr 1120/Cr 4110, aging `grand_total == control_balance` Decimal-exact, control rose exactly 160, open 160 in the 0–30 bucket; `record_receipt` partial 60 (Dr cash/Cr 1120) → open 100, aging still ties; final 100 → 'paid' open 0, aging returns to baseline. (C) over-invoice (6 vs shipped 5) 422 persists nothing; (D) over-receipt (100 vs 80) 422 persists nothing. Assert the aging grand_total DIRECTLY against the debit-normal 1120 control (keeper).
- **Done when:** file passes, 0 skips; the aging↔1120 tie is asserted Decimal-exact at post, partial, and final stages.
- **Verify:** `podman exec -e PYTHONPATH=/app compose_api_1 sh -c 'cd /app && python -m pytest tests/syerp/test_ar.py -q'`
- **Parallel-ok:** yes — serves SC1d; red-on-revert = SC2 row (AR).

### [x] 6. Port the MOUSSE WIP-clears crux (SC1e)
- **Files:** `backend/tests/mousse/test_work_orders.py` (new)
- **Do:** Mirror `verify_mousse.py` (A) + (D) via the service layer + `seeded_ledger_db`. Build a PLUM part with a Released revision + a 2-child BOM (qty_per 2 & 3), link stocked SYERP items (post_receipt to set moving avgs 3 & 5), `create_work_order` planned 10, `release_work_order` (snapshot 2 lines, qty_required 20 & 30), snapshot the WO's 1140 balance (0), `issue_components` → ONE JE Dr 1140 210 / Cr 1130 −210 (assert BOTH legs), `complete_work_order` → **CRUX:** WO's 1140-attributable balance returns to the pre-issue snapshot Decimal-exact (== 0). Then the under-issue override path (planned 3, issue one component 10@10 → accumulated_wip 100 not divisible by 3): complete with `override_incomplete=True` → 1140 clears exact, 1130 debit == `99.999999` (== FG receipt value), 5190 residual `receipt_value + 5190 == 100` (**1130 control ties the inventory subledger incl. the 5190 rounding residual** — keeper). Reuse the script's own `_wo_account_balance` derivation as the oracle.
- **Done when:** file passes, 0 skips; both the 1140-clears-exact and the 1130↔subledger+5190 invariants assert.
- **Verify:** `podman exec -e PYTHONPATH=/app compose_api_1 sh -c 'cd /app && python -m pytest tests/mousse/test_work_orders.py -q'`
- **Parallel-ok:** yes — serves SC1e; red-on-revert = SC2 row (MOUSSE).

### [x] 7. Port the CRUMB reservation crux (SC1f)
- **Files:** `backend/tests/crumb/test_sales_orders.py` (new)
- **Do:** Mirror `verify_crumb_so.py` scenario (E) via the service layer + `seeded_ledger_db`. One scarce item on-hand 10. SO_E1 qty 6 → `confirm_sales_order` reserves 6 shortage 0; SO_E2 stock qty 8 + a non-stock line → stock capped at `min(8, available 4)` == 4 with shortage 4, non-stock line reserves 0; assert `available == on_hand − Σ qty_reserved across other open (confirmed/fulfilling) SOs` (10 − (6+4) == 0); `cancel_sales_order(SO_E1)` releases 6 (Σ open → 4); SO_E3 qty 5 → reserves 5 (freed capacity genuinely available). Use the script's `_item_reserved_total` as the oracle.
- **Done when:** file passes, 0 skips; the `min(qty_ordered, available)` cap, the availability formula, the non-stock-reserves-0, and the cancel-releases behaviors all assert.
- **Verify:** `podman exec -e PYTHONPATH=/app compose_api_1 sh -c 'cd /app && python -m pytest tests/crumb/test_sales_orders.py -q'`
- **Parallel-ok:** yes — serves SC1f; red-on-revert = SC2 row (CRUMB).

### [x] 8. Port the GELATO ship-COGS crux (SC1g)
- **Files:** `backend/tests/gelato/test_shipments.py` (new)
- **Do:** Mirror `verify_gelato_ship.py` (a)(b)(c)(d)(f) via the service layer + `seeded_ledger_db`, driving the REAL `PickRequest`/`PackRequest` schemas (keeper). Receipts 100@6+100@9 (moving_avg 7.5), pick bin 50, confirmed SO order 8; `execute_pick` (net-zero at location) → `execute_pack` → `execute_ship`. Assert: **(b) CRUX** exactly ONE `gelato_shipment` JE, Dr 5100 == Cr 1130 == Σ(qty×moving_avg) == 8×7.5 == `60.000000`, and the −8 issue leg + JE share the shipment source (atomic); (c) reservation relief — shipping SO1 drops its `qty_reserved` by exactly the shipped qty and a second SO's availability is CONSERVED; (d) partial-ship accrual (6 then 4 == 10) + a third ship past qty_ordered 422; **(f) 1130 control move == inventory subledger valuation move Decimal-exact** (keeper, `Δ1130 == Δ(qty×avg)`), NOT "TB nets zero". Use the script's `_account_balance`/`_subledger_valuation` oracles.
- **Done when:** file passes, 0 skips; the balanced-COGS-JE, reservation-relief, and control↔subledger-tie invariants all assert.
- **Verify:** `podman exec -e PYTHONPATH=/app compose_api_1 sh -c 'cd /app && python -m pytest tests/gelato/test_shipments.py -q'`
- **Parallel-ok:** yes — serves SC1g; red-on-revert = SC2 row (GELATO).

---
### Wave B — one HTTP audit/RBAC test per NEW module surface (NFR-5, SC3-HTTP)
> Each drives the `client` fixture and asserts 401 (no token) / 403 (wrong-permission real user) / 200-or-201 (authorized) + an attributable `AuditLog` row after a successful mutation. Identities are minted locally per D-P2b-4 (real read/write/noperm Users+Roles created after `_isolate`, swept by the next TRUNCATE). Wave-B tasks are independent → parallelizable once their Wave-A fixtures exist.

### [ ] 9. MOUSSE HTTP audit/RBAC test (SC3)
- **Files:** `backend/tests/mousse/test_api.py` (new)
- **Do:** Mirror `verify_mousse_api.py` at the `client` layer. Local fixture mints writer (`mousse:read`+`mousse:write`), reader (`mousse:read`), noperm (no roles) Users+Roles. Build a buildable PLUM part + stocked items (service layer). Assert `POST /api/v1/mousse/work-orders`: writer token → 201 Draft WO; reader token → 403; no token → 401. After the 201, assert an `AuditLog` row `action="work_order.created"`, `actor_id==writer.id`, `target_type=="work_order"`, `target_id==wo.id`. Add one READ route (`GET /work-orders`): reader → 200, noperm → 403, no token → 401.
- **Done when:** file passes, 0 skips; the 401/403/201 triad + attributable audit row assert.
- **Verify:** `podman exec -e PYTHONPATH=/app compose_api_1 sh -c 'cd /app && python -m pytest tests/mousse/test_api.py -q'`
- **Parallel-ok:** yes — serves SC3 (MOUSSE surface).

### [ ] 10. CRUMB HTTP audit/RBAC test (SC3)
- **Files:** `backend/tests/crumb/test_api.py` (new)
- **Do:** As Task 9 but for the sales-order surface: `POST /api/v1/crumb/sales-orders` with `crumb:write`/`crumb:read`/noperm; assert 201/403/401 and an `AuditLog` `action="sales_order.created"` attributable to the writer targeting the SO; plus a read route 200/403/401.
- **Done when:** file passes, 0 skips.
- **Verify:** `podman exec -e PYTHONPATH=/app compose_api_1 sh -c 'cd /app && python -m pytest tests/crumb/test_api.py -q'`
- **Parallel-ok:** yes — serves SC3 (CRUMB surface).

### [ ] 11. GELATO HTTP audit/RBAC test (SC3)
- **Files:** `backend/tests/gelato/test_api.py` (new)
- **Do:** As Task 9 but for the shipment surface: seed a confirmed SO + stocked pick bin (service layer), then `POST /api/v1/gelato/shipments/pick` with `gelato:write`/`gelato:read`/noperm; assert 2xx/403/401 and an `AuditLog` `action="shipment.picked"`, `target_type=="shipment"`, attributable to the writer; plus a read route 200/403/401. (Use `shipment.picked` as the representative mutation — `shipment.shipped` optional if cheap.)
- **Done when:** file passes, 0 skips.
- **Verify:** `podman exec -e PYTHONPATH=/app compose_api_1 sh -c 'cd /app && python -m pytest tests/gelato/test_api.py -q'`
- **Parallel-ok:** yes — serves SC3 (GELATO surface).

### [ ] 12. AR HTTP audit/RBAC test (SC3)
- **Files:** `backend/tests/syerp/test_ar_api.py` (new)
- **Do:** As Task 9 but for the AR surface: seed a shipped SO line (reuse the Task-5 helper / real ship flow), then `POST /api/v1/syerp/ar/invoices` with `syerp:write`/`syerp:read`/noperm; assert 2xx/403/401 and an `AuditLog` `action="invoice.created"` attributable to the writer targeting the invoice; plus a read route (`GET /ar/aging` or `/ar/invoices`) 200/403/401.
- **Done when:** file passes, 0 skips.
- **Verify:** `podman exec -e PYTHONPATH=/app compose_api_1 sh -c 'cd /app && python -m pytest tests/syerp/test_ar_api.py -q'`
- **Parallel-ok:** yes — serves SC3 (AR surface).

### [ ] 13. Confirm/add the inventory audit/RBAC HTTP test (SC3, owner decision 3)
- **Files:** `backend/tests/syerp/test_inventory_api.py` (new, unless an equivalent is found in `tests/syerp/`)
- **Do:** First check whether an existing syerp test already drives an inventory mutation route over HTTP with the 401/403/2xx triad + audit assertion; if so, cite it in the checklist and this task is a no-op confirmation. If not, add one: a representative inventory mutation route (e.g. `POST /api/v1/syerp/inventory/…/receipt` or the adjustment route — confirm the exact path in `app/modules/syerp/router.py`) with `syerp:write`/`syerp:read`/noperm → 2xx/403/401 and its `AuditLog` row.
- **Done when:** inventory's audit/RBAC is proven by a suite test (found-and-cited or newly added), 0 skips.
- **Verify:** `podman exec -e PYTHONPATH=/app compose_api_1 sh -c 'cd /app && python -m pytest tests/syerp/test_inventory_api.py -q'` (or the cited existing file).
- **Parallel-ok:** yes — serves SC3 (inventory surface).

---
### Wave C — non-vacuity sweep, regression gates, and the SRD caveat-drop (NFR-5, SC2/SC4/SC5/SC6)

### [ ] 14. Prove non-vacuity per crux (SC2)
- **Files:** none committed (transient product mutations, each reverted); record the table in `docs/tasks/chore-port-verify-cruxes.md`
- **Do:** For EACH of the 7 cruxes, apply the documented product mutation, confirm the NAMED pytest test turns RED, then revert and confirm green. Suggested mutations (adjust to the real code): **inventory** — break the weighted-average in `service/inventory.py` (return the old avg) → Task-2 test red; **GL** — comment out the receipt auto-post in `service/purchasing.py::receive_line` → Task-3 receipt-JE test red; **AP** — drop the Dr 2150 GR/IR leg in `service/bills.py::post_bill` → Task-4 GR/IR-clears test red; **AR** — credit the wrong account (not 1120) in `service/ar.py::record_receipt` → Task-5 aging-tie test red; **MOUSSE** — credit 1140 by `planned_qty×fg_unit_cost` instead of the exact accumulated WIP in `mousse/service` completion → Task-6 WIP-clears-exact test red; **CRUMB** — reserve `qty_ordered` instead of `min(qty_ordered, available)` in `crumb/service/sales_orders.py::confirm_sales_order` → Task-7 cap test red; **GELATO** — value COGS at `unit_price` instead of `moving_avg` in `gelato/service/shipments.py::execute_ship` → Task-8 balanced-COGS test red. Record each (crux, file+mutation, RED test name, revert→green) in the checklist.
- **Done when:** all 7 mutations each flip a NAMED pytest test RED and revert to green; `git diff -- backend/app/` is empty afterward (SC5).
- **Verify:** the checklist table lists 7 rows each with a RED test name and a green-after-revert; final `git status` shows no `backend/app/` change.
- **Parallel-ok:** no (run after Wave A/B green) — serves SC2 + guards SC5.

### [ ] 15. Full-suite regression + verify_* still-green + selfcheck (SC4 + SC5)
- **Files:** none (verification task)
- **Do:** (1) full `pytest -q` GREEN with **0 skipped**, run **twice back-to-back** (isolation holds); (2) `tests/test_harness_selfcheck.py` passes; (3) all **23 `verify_*` scripts** still exit 0 in-container; (4) `ruff check .` from `backend/` exit 0; (5) cold boot `import app.main` ok; (6) `git diff -- backend/app/` empty.
- **Done when:** all six gates pass.
- **Verify:**
  - Suite ×2: `podman exec -e PYTHONPATH=/app compose_api_1 sh -c 'cd /app && python -m pytest -q && python -m pytest -q'` — both report 0 skipped.
  - verify_*: `podman exec -e PYTHONPATH=/app compose_api_1 sh -c 'cd /app && for s in scripts/verify_*.py; do python "$s" >/dev/null || echo "FAIL $s"; done'` — no FAIL lines.
  - Lint/boot: `podman exec -e PYTHONPATH=/app compose_api_1 sh -c 'cd /app && ruff check . && python -c "import app.main; print(\"boot-ok\")"'`
  - `git diff --stat -- backend/app/` empty.
- **Parallel-ok:** no (final code gate) — serves SC4 + SC5.

### [ ] 16. Drop the SRD caveats + update requirements-progress + record D-P2b (SC6)
- **Files:** `.zj/SRD.md` (NFR-5 + the SYERP/MOUSSE/CRUMB/GELATO rows' "script-only / UI-flow-UAT-pending" caveats), `docs/features/requirements-progress.md`, `.zj/DECISIONS.md` (append D-P2b-1..6)
- **Do:** Flip NFR-5 status `partial (2a done / 2b pending)` → **done** with this phase's evidence (ported crux test names + the 0-skip suite result + 23/23 verify_* green). Drop the "script-only" caveats NFR-5 names on the SYERP/MOUSSE/CRUMB/GELATO SRD rows (their cruxes are now suite-proven). Update `docs/features/requirements-progress.md` accordingly. Append D-P2b-1..6 to `.zj/DECISIONS.md` (owner 1..3 + architect 4..6).
- **Done when:** NFR-5 reads done; no SRD row still carries a "script-only / verify_*-only" caveat for a now-ported crux; requirements-progress reflects it; D-P2b-1..6 recorded.
- **Verify:** `grep -n "script-only\|2b pending\|verify_\* crux" .zj/SRD.md` returns nothing stale for the ported modules; `grep -n "D-P2b" .zj/DECISIONS.md` shows 1..6.
- **Parallel-ok:** no (docs finalize after Task 15 green) — serves SC6.

## Risks
- **Ported test setup is heavier than the crux itself** (AR/GELATO/MOUSSE each need multi-step fixtures — receipts, bins, SO, ship). *Early warning:* Wave A tasks 5/6/8 exceeding ~1h. *Mitigation:* lift the scripts' own fixture builders (`_seed_shipped_line`, `_make_part_with_revision`) near-verbatim; they are proven and self-contained.
- **`_isolate` truncates the CoA/location every test** — a ported test that forgets `seeded_ledger_db` will fail on a missing seeded account with a confusing error. *Early warning:* `HTTPException 404`/"account 1130 not found" in a fresh file. *Mitigation:* Task 1's shared fixture + this note in Context; every Wave-A file depends on it.
- **A ported crux exposes a genuine product bug** (the cruxes have only ever run against the live `biznice` DB, never a truncate-fresh one). *Early warning:* a headline assert fails on first run with no test-side cause. *Mitigation:* SC5 policy — minimal fix + `## Noticed`; if it needs a schema/Alembic change, STOP + flag owner (forbidden here).
- **RBAC 403-vs-401 shape drift** — RBAC reads DB roles not the token claim (D-P2a-4); a noperm user might 403 where a test expects 401 (401 is only the no-token case). *Early warning:* Wave-B status-code mismatches. *Mitigation:* mirror `verify_*_api.py` exactly — no token → 401, real limited user → 403.

## Deviations
- **Task 0 branch point (trivial):** plan Task 0 names `f97b21a`, but PLAN.md was committed in
  the later plan-doc commit `3f71900` (the actual current tip). Cut off `3f71900` instead so
  PLAN.md travels onto the build branch — honors the plan's own Context rationale (cut the tip,
  not the bare tag; 12a/12b/13/2a precedent).

## Noticed
- **Pre-existing harness SAWarning (Task 1):** `conftest.py` `_isolate` builds its TRUNCATE
  order from `Base.metadata.sorted_tables`, which silently drops `crumb_lead` /
  `crumb_opportunity` from the sort due to an unresolvable FK cycle between them. Those two
  tables may therefore NOT be truncated between tests. Pre-existing (2a harness), not
  introduced here. RISK for CRUMB ported tests (Tasks 7/10) if they touch leads/opportunities;
  watch for cross-test pollution there.
- Populate during Wave A/B: any product bug found (with the minimal fix + follow-up owner), and any assertion in a `verify_*` script deliberately NOT ported (concurrency scenarios are expected; note any *sequential* assert intentionally dropped under D-P2b-2 so the coverage delta is explicit).
- Task 13 may find inventory's HTTP audit/RBAC already covered — record which existing file if so.

## Out of scope (deferred so build doesn't drift)
- **Concurrency mutation-proofs** (`asyncio.gather`/`Barrier` + `FOR UPDATE`) — stay in `verify_*` as a separate CI step (D-P2a-2/D-P2b-1); NOT ported.
- **Removing or thinning the `verify_*` scripts** — they remain the concurrency proof + a redundant CI gate; this phase ADDS pytest coverage, it does not subtract scripts (SC5).
- **Any `backend/app/` change** beyond a minimal, flagged product-bug fix — TEST-ONLY phase; schema/Alembic changes STOP-and-flag.
- **CI auto-run wiring** of the gates — Phase 3 / NFR-4.
- **Human UAT of the flows** — NFR-8.

---
## Run the ported cruxes
**Whole new-coverage set (in-container):**
```
podman exec -e PYTHONPATH=/app compose_api_1 sh -c 'cd /app && python -m pytest \
  tests/syerp/test_inventory_service.py tests/syerp/test_gl_posting.py \
  tests/syerp/test_ap_posting.py tests/syerp/test_ar.py tests/syerp/test_ar_api.py \
  tests/mousse tests/crumb tests/gelato -q'
```
**Full suite (final gate, 0 skipped, ×2 for isolation):**
```
podman exec -e PYTHONPATH=/app compose_api_1 sh -c 'cd /app && python -m pytest -q && python -m pytest -q'
```
