# Verification: Phase 12a — GELATO bins & directed putaway (inbound foundation)
Date: 2026-07-17 | Commits: da9474e..db065cf (task commits b0b0dcd..db065cf)
Verdict: PASS

Goal: a warehouse operator can define bins inside a SYERP stock location and direct
received (unbinned) stock into bins, with per-bin on-hand deriving from the shared
ledger and rolling up exactly to the location total. Verified goal-backward,
evidence-only, against a live stack (compose_api_1 + compose_db_1, DB at 0015 head).

## Criteria

### SC1 — Module wired + schema — PASS
| Truth | Exists | Wired | Works | Evidence |
|---|---|---|---|---|
| `gelato` self-registers | yes | yes | yes | `gelato/__init__.py:20` `registry.register`; `main.py:83` `importlib.import_module("app.modules.gelato")`; `core/models.py:31` model aggregation |
| Router at `/api/v1/gelato` | yes | yes | yes | 7 routes in `router.py`; `verify_gelato_api.py` drives them all over real HTTP (200/401/403) |
| `gelato:read`/`gelato:write` seeded idempotently | yes | yes | yes | `auth/seed.py:42-43` catalog + `:57-58` admin grant; `verify_gelato_api.py:178` asserts both resolve |
| Migration 0015 = `gelato_bin` + nullable `bin_id` | yes | yes | yes | `0015_gelato_bins.py` down_revision="0014"; `alembic heads`→`0015 (head)` single linear head |
| Fresh 0001→0015 clean | — | — | yes | Ran `alembic upgrade head` on a scratch DB `gelato_freshcheck`: logged 0001→…→0015 clean; `\d gelato_bin` + `syerp_inventory_txn.bin_id` present; scratch DB dropped |
| Full regression exit 0 | — | — | yes | 17/17 verify_* scripts PASS (loop below) |

### SC2 — Bin CRUD (AC1) — PASS
| Truth | Exists | Wired | Works | Evidence |
|---|---|---|---|---|
| create/edit/archive scoped to location | yes | yes | yes | `service/bins.py` create_bin/update_bin/archive_bin; `Bin.location_id` FK required |
| code unique-within-location | yes | yes | yes | 422 pre-check `bins.py:60-73` + DB `uq_gelato_bin_location_code` (model:58, migration:87) |
| archived hidden from default list | yes | yes | yes | `list_bins` `active==True` filter unless `include_archived`; `verify_gelato_api.py:338` asserts archived A2 hidden |
| dup code / bad location rejected 4xx | yes | yes | yes | 404 on missing loc (`bins.py:57`), 422 dup (`:67`); Bins.test.tsx surfaces dup-code toast |
| validation server-side | yes | yes | yes | all guards in the service, not the client |

### SC3 — Per-bin on-hand derives + rolls up (AC1) — PASS
| Truth | Exists | Wired | Works | Evidence |
|---|---|---|---|---|
| `get_bin_on_hand(item,loc,bin)` = Σ signed qty | yes | yes | yes | `inventory.py:624-658` null-aware (`bin_id.is_(None)` for unbinned) |
| Σ bins + unbinned == per-location total, Decimal-exact | yes | yes | yes | Roll-up holds by construction (existing on-hand SUMs never filter `bin_id`); `verify_gelato.py:320-336` asserts `25+25+50 == 100` with `==` on Decimal + isinstance(Decimal) checks |

### SC4 — Directed putaway nets zero at location (AC2, AC7) — PASS
| Truth | Exists | Wired | Works | Evidence |
|---|---|---|---|---|
| paired bin-aware legs, `txn_type="putaway"` | yes | yes | yes | `post_putaway` `inventory.py:752-771` two legs, fresh `transfer_group_id`, both same `location_id` |
| location total UNCHANGED; bin rises / pool falls | yes | yes | yes | `verify_gelato.py` (A) asserts total==100 across 3 moves; target bin rises, pool falls by exactly qty |
| over-draw rejected 4xx, no rows | yes | yes | yes | floor guard `inventory.py:739` `_adjustment_violates_floor(source_onhand,-qty)`; `verify_gelato.py` (C) asserts 422 + ledger row count unchanged |
| target-bin suggestion offered, user-confirmable | yes | yes | yes | `suggest_target_bin` heuristic (putaway.py:45); PutawayDialog pre-fills but lets user override; Putaway.test.tsx asserts pre-fill |
| two concurrent putaways cannot over-draw | yes | yes | yes | `InventoryItem` FOR UPDATE before floor read (`inventory.py:729-731`); `verify_gelato.py` (D) real `asyncio.Barrier(2)` + `gather`, independent sessions, 5 iters, asserts exactly 1 success + 1 HTTP 422, final pool==3/bin==7 |

Note on the concurrency crux: the Barrier scenario is structurally load-bearing (genuine
`asyncio.Barrier(2)`, two independent sessions, `asyncio.gather`, per-iteration fresh
item — not a no-op). Its documented "fails when the lock is removed" property (D-P12a-6)
is asserted by the script's own header, verified-once-by-the-author; I did not re-mutate
the live source to re-prove failure (destructive in the running env). The lock target is
`InventoryItem` (deviation-corrected from the plan's `InventoryTxn` prose) — correct: the
append-only ledger cannot serialize concurrent inserts; the item-master row is the
contention point.

### SC5 — Audit + RBAC at HTTP level (AC8) — PASS
| Truth | Exists | Wired | Works | Evidence |
|---|---|---|---|---|
| bin create/edit/archive + putaway emit attributable audit | yes | yes | yes | router writes `write_audit` after commit; `str(bin_.id)` fix present (`router.py:115,141,165`) — the 136e98d int→str bug is fixed; `verify_gelato_api.py:276-330,380-388` asserts each AuditLog row exists, `actor_id==writer_id`, correct target_type |
| endpoints gated read/write (401/403/200) | yes | yes | yes | `require_permission("gelato:read"/"gelato:write")` on every route; `verify_gelato_api.py` (B/C) asserts 403 on read-only token for mutations, 403 no-perm on reads, 401 unauth, 200/201 for writer |

### SC6 — Frontend + regression — PASS
| Truth | Exists | Wired | Works | Evidence |
|---|---|---|---|---|
| nav gated on module-enabled ∩ gelato:read | yes | yes | yes | `AppShell.tsx:36-45` `useVisibleModules` = enabled ∩ `${key}:read` (admin wildcard); `Sidebar.tsx:27-30` NavLink→`/${mod.key}`→`/gelato`; gelato in modules catalog (default disabled, modules_seed) |
| Bins screen | yes | yes | yes | `routes/gelato/Bins.tsx` + `BinSheet.tsx`; App.tsx:112 |
| Putaway screen | yes | yes | yes | `routes/gelato/Putaway.tsx` + `PutawayDialog.tsx`; App.tsx:113 |
| TanStack Query invalidation | yes | yes | yes | `hooks.ts:161-203` — putaway invalidates bins+unbinned+item on-hand; bin mutations invalidate bins |
| Vitest + build clean | — | — | yes | `vitest run src/routes/gelato` → 2 files / 8 tests pass; `npm run build` exit 0 (822 kB chunk warning pre-existing, not a gap) |
| full regression + TB nets zero | — | — | yes | 17/17 PASS; `verify_reports.py`: `trial_balance total_debit EXACTLY equals total_credit and in_balance is True` |

## Regression protection
| Criterion | Pinned by |
|---|---|
| SC1 module/schema/fresh-migrate | `scripts/verify_gelato.py` + `verify_gelato_api.py` (import/route/perm) + fresh-DB `alembic upgrade head` (manual this run; migration file is in-repo and CI-runnable) |
| SC2 bin CRUD | `verify_gelato_api.py` (create/patch/archive/list-hides) + `frontend Bins.test.tsx` (dup-code toast, archive-hides) |
| SC3 roll-up Decimal-exact | `verify_gelato.py` scenario (B) |
| SC4 net-zero / over-draw / concurrency | `verify_gelato.py` scenarios (A)(C)(D) |
| SC5 audit + RBAC | `verify_gelato_api.py` (A)(B)(C) |
| SC6 FE + regression | `Bins.test.tsx`, `Putaway.test.tsx`, full `verify_*` loop, `verify_reports.py` TB |

All six criteria are pinned by automated tests. No feasible-but-missing regression test found.

## Test suite
- Backend regression loop (17 scripts) — all PASS:
  verify_inventory, verify_purchasing, verify_e2e_p8, verify_gl, verify_gl_api, verify_ap,
  verify_ap_api, verify_reports, verify_reports_api, verify_mousse, verify_mousse_api,
  verify_crumb, verify_crumb_api, verify_crumb_so, verify_crumb_so_api, verify_gelato, verify_gelato_api
- `verify_reports.py`: Trial Balance `in_balance is True`, total_debit == total_credit (12a posts NO GL).
- Frontend: `vitest run src/routes/gelato` → 2 files / 8 tests pass; `npm run build` exit 0.
- Fresh DB: `alembic upgrade head` on scratch `gelato_freshcheck` ran 0001→0015 clean; gelato_bin + bin_id created.
- `alembic heads` → single linear head `0015`.

## Gaps
1. **Minor — doc-truth lag on GELATO-01 status.** `.zj/SRD.md:596` still reads
   `Status: planned (v3.0 — Phase 12)` and `docs/features/requirements-progress.md`
   contains no GELATO entry, although AC1 (bins + roll-up), AC2 (inbound putaway), the
   putaway half of AC7 (floor guard), and AC8 (audit + RBAC) are now delivered and
   verified. Failure scenario: a reader planning 12b or auditing coverage sees GELATO-01
   as untouched and cannot tell which ACs already hold. Fix: mark AC1/AC2/AC8 + putaway-AC7
   as done-in-12a (or add a "12a partial" note) in the SRD, and add a GELATO-01 row to
   requirements-progress.md. Not blocking — GELATO-01 as a whole remains open pending 12b.

No blocker or major gaps.

## Manager triage + fix loop (2026-07-18)

Verifier PASS + reviewer (`REVIEW.md`) merged. Reviewer found **0 blocker, 1 MAJOR, 0 minor**;
verifier found **1 minor**. No finding failed a success criterion (the concurrency crux came back
clean; the MAJOR preserves the SC3 roll-up identity). Owner chose "cheap mitigation now + mark docs
partial." Handled:

1. **Reviewer MAJOR — bin split desyncs after any bin-blind movement** (`get_bin_on_hand` overstates a
   bin and drives the unbinned pool negative once `post_transfer`/`post_adjustment`/MOUSSE-issue draws
   the location; SC3 roll-up + location total stay exact — only the split lies). Durable fix (bin-aware
   pick/issue) is Phase 12b scope. Mitigation shipped this loop, NOT a value clamp (clamping would break
   the very SC3 identity this phase proved):
   - `get_bin_on_hand` gained a **TRUST BOUNDARY** docstring (`inventory.py`).
   - **`verify_gelato.py` scenario (E)** added — pins the stale-bin/negative-unbinned behavior AND proves
     `Σ bins + unbinned == location total` (and location on-hand == 0) survives a bin-blind draw
     Decimal-exact. Green (11/11).
   - **BACKLOG p2** entry added (folds into the cross-path inventory-ledger race item); **PLAN Risk**
     sharpened from "concurrency race" to "sequential correctness"; 12b explicitly told not to assume
     12a closed it.

2. **Verifier minor — doc-truth lag.** `.zj/SRD.md` GELATO-01 status → "partial — 12a inbound foundation
   VERIFIED (AC1/AC2/AC8 + putaway-side AC6/AC7); outbound pending 12b" with a `Verified: 52eb481` stamp
   scoped to the subset; **GELATO Module** section + row added to `docs/features/requirements-progress.md`.

**Re-verification after the source change** (workflow requires a full re-run — `verify_gelato.py` gained
scenario E, `inventory.py` got a docstring-only edit): full 17/17 regression **GREEN**, `verify_gelato`
**11/11** (incl. E), `verify_gelato_api` **29/29**, Trial Balance `in_balance` True. (One transient
`verify_mousse_api` failure on the first re-run was a uvicorn `--reload` worker-restart race triggered by
`podman cp` of `inventory.py` mid-loop — reproduced clean in isolation and on the settled full re-run.)

**Final verdict: PASS.**
