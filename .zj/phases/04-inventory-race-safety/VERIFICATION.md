# Verification: Phase 04 — Inventory ledger race-safety (NFR-7)
Date: 2026-07-25 (re-verified 2026-07-26 after fix loop) | Commits: 7a71fd0..3253917 (branch `chore-inventory-race-safety`, HEAD 3253917)
Verdict: PASS

Initial verification at 3126c48 returned GAPS FOUND (1 major: the transfer/MOUSSE/positive-adjust
bin-aware behaviors were proven only by the verifier's hand check — no automated pin). The fix
loop (`3126c48..3253917`, 5 commits) closed that gap with verify_gelato scenario F and
verify_mousse scenario G, and additionally fixed two review findings (restored per-location
floor in `issue_components`; under-lock `db.refresh` in `post_transfer`). Full re-check on the
new tip: everything holds empirically.

## Criteria

### SC1 — shared FOR-UPDATE lock discipline — PASS
| Truth | Exists | Wired | Works | Evidence |
|---|---|---|---|---|
| `post_receipt` locks item-master before qty_before read | ✓ | ✓ | ✓ | `inventory.py:278-280` lock → `:286` `db.refresh(item)` (T1 deviation — moving-avg re-read under lock, non-vacuous) → `:289-292` aggregate SUM. Proven live by race scenario D (avg 9.583333 exact). |
| `post_adjustment` locks before floor reads | ✓ | ✓ | ✓ | `:422-424` lock → per-location SUM → pool floor. Scenarios A/B live PASS. |
| `post_transfer` locks before floor reads AND refreshes item under lock before leg valuation | ✓ | ✓ | ✓ | Lock `:588-590` → **`db.refresh(item)` `:596` (fix `5a45a7b`, review finding 3)** → source SUM → pool floor → `unit_cost = item.moving_avg_cost` read only after the refresh. Scenario B live PASS. |
| `receive_line` locks PO header before guards; PO→item order documented | ✓ | ✓ | ✓ | `purchasing.py:630` `_get_po_row(db, po_id, for_update=True)` → status guard → `:652` over-receipt guard; ordering contract `:589-591`. Scenario C live PASS. |
| `post_putaway` / `post_issue` / MOUSSE `issue_components` retain their locks | ✓ | ✓ | ✓ | `inventory.py:831`, `:995`; `mousse/service.py:702-708` (sorted-id loop, now also loads the row for valuation). verify_gelato D + race A live PASS. |

### SC2 — mixed-path concurrency, mutation-proven — PASS
| Truth | Exists | Wired | Works | Evidence |
|---|---|---|---|---|
| `verify_inventory_race.py` — 4 scenarios, real router schemas | ✓ | ✓ (CI auto-glob) | ✓ | Re-ran live on tip 3253917: **exit 0**, A–D all PASS, 5 iterations each. |
| Assertions non-vacuous | ✓ | — | ✓ | Pins `successes==1 and http_422==1`, exact remainders (`final_loc==3 and final_pool==3`), `qty_received==7` + header `partially_received` + ONE receipt txn, moving-avg `== 115/12 → 9.583333` quantized exact; `_classify` fails on any non-422 exception. |
| Mutation table M1–M4 executed RED→GREEN | corroborated | — | corroborated | Archived checklist `docs/tasks/_completed/2026-07-25-chore-inventory-race-safety.md:33-38` — concrete per-mutation observations (M1 −4 both-succeed; M3 double GL post + accumulator stuck at 7; M4 10.000000 vs 9.583333). Script GREEN re-confirmed live on tip. |
| **NEW: G2 location-floor mutation-proof** | corroborated | — | corroborated | Commit `3f45685` body + live checklist addendum: guard short-circuited → G2 RED (issue SUCCEEDED, rows 4→5, location −10.000000, exit 1); restored → GREEN. |

### SC3 — bin-aware draws — PASS
| Truth | Exists | Wired | Works | Evidence |
|---|---|---|---|---|
| `post_adjustment(bin_id)` schema→router→service; negative-only pool floor; txn carries bin_id | ✓ | ✓ | ✓ | `schemas.py:370` → `router.py:524` → service `:368/:449-459/:469`. verify_gelato E1–E3 live PASS on tip (422 + zero rows; named bin → 0/0; roll-up exact). |
| `post_transfer(from_bin_id)`; source-pool floor; out leg binned / in leg unbinned (D-P4-5) | ✓ | ✓ | ✓ | `schemas.py:404` → `router.py:576` → service `:517/:616-625/:638/:650`. **verify_gelato scenario F live PASS** (`c692498`): F1 NULL at fully-binned source → 422 + zero rows; F2 out leg bin_id=F1 / in leg NULL, pools + both location totals Decimal-exact. |
| MOUSSE `issue_components` per-line bin_id; pool floor key `(item, location, bin)`; txn carries bin_id | ✓ | ✓ | ✓ | `mousse/schemas.py:160` → router pass-through → `service.py:743-756` pool guard, `:769` txn bin_id. **verify_mousse scenario G1 live PASS** (`3f45685`): NULL → 422 + zero rows; named bin → issue txn carries bin_id, pool 10−6==4, WIP/JE value unchanged (6×4==24.000000). |
| **Per-location floor kept BESIDE the pool floor** (review finding 1 — legacy-desync defense) | ✓ | ✓ | ✓ | Fix `2a87f6d`: `service.py:721-741` — `loc_base_onhand`/`loc_consumed` accumulate jointly across duplicate lines, guard fires BEFORE any txn append, mirrors post_adjustment/post_transfer's two-grain discipline. **verify_mousse G2 live PASS**: raw-inserted desync fixture (bin 10 / unbinned −10 / location 0) → bin-named issue of 10 passes pool guard but 422s on the location floor, ZERO rows written, location never negative. |
| Positive adjust may target a bin, no floor on additions (D-P4-6) | ✓ | ✓ | ✓ | Service guards only `qty_delta < 0`. **verify_gelato F3 live PASS**: +4 into bin F1 → pool 5+4==9, unbinned untouched. |
| `verify_gelato.py` scenario E asserts the FIX | ✓ | ✓ (CI) | ✓ | E1–E3 live PASS on tip; pin language dropped. |

### SC4 — UI wiring end-to-end — PASS
Unchanged since the initial verification — `git diff --stat 3126c48..3253917 -- frontend/` is
empty; the fix commits touch backend + scripts + checklist only.
| Truth | Exists | Wired | Works | Evidence |
|---|---|---|---|---|
| StockAdjustDialog bin picker | ✓ | ✓ | ✓ | Test asserts REAL POST body: `bin_id: 12` chosen / `null` untouched / hidden + `null` on bins-query failure (`StockAdjustDialog.test.tsx:174-241`). |
| StockTransferDialog from-bin picker (source-keyed) | ✓ | ✓ | ✓ | `from_bin_id` both ways + degradation (`StockTransferDialog.test.tsx:182-255`); no destination bin control (D-P4-5), putaway caption. |
| IssueComponentsDialog per-line picker | ✓ | ✓ (`targetLocationId` prop from `WorkOrderDetail.tsx:367`) | ✓ | Per-line `bin_id: 12`/`null` mix + degradation (`IssueComponentsDialog.test.tsx:140-223`); host-screen tests reconciled. |
Vitest 44 files / 139 tests passed at 3126c48; CI `frontend` job green on tip 3253917 re-confirms.

### SC5 — regression — PASS
| Truth | Works | Evidence (re-run on tip 3253917) |
|---|---|---|
| All non-API `verify_*` exit 0 | ✓ | Plan's exact loop in `compose_api_1`: 15/15, `SWEEP_OK`. |
| Trial Balance nets zero | ✓ | `verify_reports.py` trial_balance assertion PASS (in sweep; explicitly observed at initial verify). |
| Backend pytest green, 0 skipped | ✓ | In-container: **232 passed, 0 skipped** (196s). Host-local pytest cannot reach `biznice_test` (DB not host-published) — in-container + CI `backend-tests` cover it. |
| ruff clean | ✓ | `backend/.venv/bin/ruff check .` → "All checks passed!" |
| Frontend Vitest + lint + build | ✓ | Full gate run at 3126c48 (139/139, lint 0, build 0); frontend diff empty since; CI `frontend` green on tip. |
| Four CI jobs green on branch tip | ✓ | `gh run view 30185233894` → headSha `3253917`, verify-scripts / backend-tests / backend-lint / frontend all success. Scenarios F and G run in the `verify-scripts` auto-glob (non-`_api.py`). |

### SC6 — bookkeeping — PASS
| Truth | Evidence |
|---|---|
| SRD NFR-7 flipped with evidence | `.zj/SRD.md:751` "done — pending `/zj:verify 4`" + Delivery block; cited commit hashes match `git log`. |
| requirements-progress row | `docs/features/requirements-progress.md:97` + footer entry. |
| D-P4-1..6 appended | `.zj/DECISIONS.md:1154-1175`. |
| STATE.md updated | Build-complete entry, next `/zj:verify 4`. |
| Checklist archived + fix-loop addendum | `docs/tasks/_completed/2026-07-25-chore-inventory-race-safety.md` (M1–M4 table, sweep log); live addendum `docs/tasks/chore-inventory-race-safety.md` records the G2 mutation-proof and fix-loop gates (`3253917`). |

## Regression protection
| Criterion | Pinned by |
|---|---|
| SC1 locks (all four writers) | `backend/scripts/verify_inventory_race.py` scenarios A–D — CI `verify-scripts` on every push |
| SC2 mixed-path race | same script, scenario A (MOUSSE × SYERP) |
| SC3 — adjust bin-aware (NULL 422 / named-bin draw / roll-up) | `verify_gelato.py` E1–E3 (CI) |
| SC3 — transfer `from_bin_id` (NULL 422 + zero rows; out leg binned / in leg unbinned D-P4-5, exact pools) | `verify_gelato.py` **F1–F2** (CI) — added by fix loop `c692498` |
| SC3 — positive adjust into named bin (D-P4-6) | `verify_gelato.py` **F3** (CI) |
| SC3 — MOUSSE per-line `bin_id` (NULL 422; named-bin txn carries bin, exact remainder, JE value unchanged) | `verify_mousse.py` **G1** (CI) — added by fix loop `3f45685` |
| **Restored MOUSSE per-location floor on legacy-desync data** (review finding 1) | `verify_mousse.py` **G2** (CI) — mutation-proved RED→GREEN at fix time |
| SC4 payloads + degradation | `StockAdjustDialog.test.tsx`, `StockTransferDialog.test.tsx`, `IssueComponentsDialog.test.tsx` (CI `frontend` job) |
| SC5 | the four CI jobs themselves |
| SC6 | manual: documentation state, not automatable |

## Test suite
Re-run on tip 3253917 (2026-07-26):
- `podman exec … verify_gelato.py` → exit 0 (A–F all PASS, incl. F1–F3)
- `podman exec … verify_mousse.py` → exit 0 (incl. G1 + G2 CRUX)
- `podman exec … verify_inventory_race.py` → exit 0 (A–D, 5 iterations each)
- Non-API sweep loop (plan recipe) → 15/15, `SWEEP_OK`
- In-container `python -m pytest -q` → 232 passed, 0 skipped
- `backend/.venv/bin/ruff check .` → clean
- `gh run view 30185233894` → 4/4 jobs success on headSha 3253917
From initial verification at 3126c48 (still valid — frontend untouched since):
- Frontend: Vitest 44 files / 139 tests pass; `npm run lint` exit 0; `npm run build` exit 0
- Verifier hand check (throwaway script) → T1–T5 all PASS (independently confirmed the same behaviors scenarios F/G now pin)

## Gaps
None. The initial major gap (no automated pin for the transfer/MOUSSE/positive-adjust
bin-aware behaviors) is closed by scenarios F (`verify_gelato.py`) and G (`verify_mousse.py`),
both running in CI's `verify-scripts` glob and both green live and in CI run 30185233894.

Observations (not gaps):
- `.zj/BACKLOG.md` carries an UNCOMMITTED working-tree edit adding two review-derived items
  (unvalidated positive-adjust `bin_id` can strand stock in a foreign-location bin — owner
  decision needed; GELATO `pick_for_shipment` unsorted incremental locks — deadlock-500 risk).
  Content is correct and should be committed at verify close so it isn't lost.
- Docs remain truthful post-fix: `get_bin_on_hand` TRUST BOUNDARY closed, `list_unbinned_stock`
  `>0` filter documented as legacy-only, `grep "bin-blind"` over `backend/app/` returns only
  historical/closed phrasings, BACKLOG bin-desync inbound half claimed (final check-off at
  verify close per plan).

---
Close-out addendum (manager, 2026-07-25): the verify close-out commit `835b12a` (artifacts +
roadmap/SRD/backlog/state/requirements-progress bookkeeping) touches **no source** —
`git diff --stat 3253917..835b12a -- backend/ frontend/ compose/ .github/` is empty — so this
verification of tip `3253917` remains valid for the tagged state.
