# Verification: Phase 12b — GELATO warehouse outbound (pick → pack → ship)
Date: 2026-07-18 (verify) / 2026-07-19 (fix loop) | Commits: bde5b77..553bcfb (code 61a695e..553bcfb)
Verdict: **PASS** (after fix loop — one BLOCKER found by review, fixed, and re-verified)

All six success criteria verified empirically against the running stack (`compose_api_1`).
Every claim below was observed — verify scripts run, migration round-tripped, frontend built
and tested. Nothing taken from the STATE build summary on trust.

> **Fix-loop addendum (2026-07-19).** The paired code review (`REVIEW.md`) found a **BLOCKER** that
> this verification's SC4 concurrency check (scenario g) did NOT surface: two concurrent ships of ONE
> *packed* shipment gated on an UNLOCKED shipment status → a second inventory issue + second Dr 5100 /
> Cr 1130 COGS JE (double-post). Scenario g masked it because its staging bin was seeded to *exactly*
> the ship qty, so `post_issue`'s floor guard incidentally rejected the duplicate; with an ample/reused
> staging bin the double-post goes through. **Fixed** (`553bcfb`): `execute_ship` now loads the shipment
> `SELECT … FOR UPDATE` before the FSM gate. **New durable regression** `verify_gelato_ship.py` scenario
> (h) — one packed shipment partially fulfilling its SO (order 10, ship 5, so the over-ship guard cannot
> mask it) shipped twice concurrently; asserts one 409 + exactly ONE JE + `qty_shipped==5` + staging
> drawn once. **Mutation-proven**: reverting the lock regresses it to `successes=2 / je_count=2 /
> qty_shipped=10 / staging drawn twice`. Full regression re-run after the fix: **21/21 verify_* exit 0**,
> TB nets zero with the COGS JE. Two lower-severity pick-path shipment-header races (review Q1/Q2) and
> the migration-downgrade automated-test gap are logged (BACKLOG p2/p3, PLAN `## Noticed`). Final
> verdict stands at **PASS** on the fixed code (`553bcfb`).

## Criteria

### SC1 — Schema + module extension — PASS
| Truth | Exists | Wired | Works | Evidence |
|---|---|---|---|---|
| Migration 0016 adds `gelato_shipment` + `gelato_shipment_line` | ✓ | ✓ | ✓ | `0016_gelato_shipments.py:67,120` create parent-then-child; `alembic heads` → `0016 (head)`; `down_revision="0015"` (:56) |
| `qty_picked`/`qty_shipped` on `crumb_sales_order_line` | ✓ | ✓ | ✓ | `0016:178-190` two `add_column(... server_default="0")`; downgrade drops both (`:201-202`) |
| Fresh 0001→0016 clean + round-trip | — | — | ✓ | `alembic upgrade head`, `downgrade -1` (0016→0015), `upgrade head` (0015→0016) all exit 0 |
| `gelato` still self-registers; full regression exits 0 | ✓ | ✓ | ✓ | 19/19 `verify_*` OK (see Test suite) |

### SC2 — Pick (bin-aware) — PASS
| Truth | Exists | Wired | Works | Evidence |
|---|---|---|---|---|
| Pick list maps lines → suggested bins w/ on-hand | ✓ | ✓ | ✓ | `shipments.py:123 build_pick_list`; verify_gelato_ship (a/SC2): candidate on_hand 50, suggests bin covering remaining 8 |
| Pick posts bin-aware net-zero via `post_putaway` | ✓ | ✓ | ✓ | `shipments.py:388` post_putaway(commit=False); verify (a/SC2): location total unchanged (200) |
| Stamps `qty_picked` | ✓ | ✓ | ✓ | `shipments.py:408`; verify (a/SC2) |
| Per-bin floor guard rejects over-pick 4xx | ✓ | ✓ | ✓ | verify (e1/SC2): over-pick 5-from-4 rejected 4xx |
| Non-stock line (item_id NULL) rejected 422 | ✓ | ✓ | ✓ | `shipments.py:370-377`; verify (e3/SC2): 422 |

### SC3 — Pack — PASS
| Truth | Exists | Wired | Works | Evidence |
|---|---|---|---|---|
| FSM picking → packed | ✓ | ✓ | ✓ | `shipments.py:465` gate on SHIPMENT_TRANSITIONS; verify_gelato_ship_api (4): pack → 'packed' 200 |
| Partial packs (staged qty trimmed ≤ picked) | ✓ | ✓ | ✓ | `shipments.py:494-503` override >picked → 422, else trims; verify (d/SC3) accumulation |

### SC4 — Ship (accounting crux) — PASS
| Truth | Exists | Wired | Works | Evidence |
|---|---|---|---|---|
| Issue from staging bin at moving-avg via `post_issue` | ✓ | ✓ | ✓ | `inventory.py:843 post_issue` single `-qty` issue leg @ moving_avg_cost, per-bin floor; verify (a/SC4): location 200→192 |
| ATOMIC: one balanced Dr 5100 / Cr 1130 JE, ≥2 lines, source_type gelato_shipment, single commit | ✓ | ✓ | ✓ | `shipments.py:670-690` commit=False on post_issue + JE, one `db.commit()`; verify (b/SC4 CRUX): Dr 5100 == Cr 1130 == 8×7.5 == 60.000000 Decimal-exact, one JE, txn+JE committed together |
| Decrements qty_reserved + stamps qty_shipped | ✓ | ✓ | ✓ | `shipments.py:646-648`; verify (c/D-P12b-5): reserved 5→0, other-SO reservation drops by exactly 5 |
| Partial shipments accumulate | ✓ | ✓ | ✓ | verify (d/SC3): 6 then 4 == 10 == ordered |
| Never over-ships beyond ordered (4xx) | ✓ | ✓ | ✓ | `shipments.py:637-645`; verify (d/SC3): past-ordered ship → 422 |
| Staging on-hand never negative (4xx) | ✓ | ✓ | ✓ | `post_issue` floor `inventory.py:918`; verify (e2/SC4): drained-below-staged → 422 |
| 1130 ties to subledger; TB nets zero | ✓ | ✓ | ✓ | verify (f): Δ1130 == Δsubledger == −80.000000 Decimal-exact; verify_reports OK (TB in_balance) |
| Re-ship blocked (no double relief) | ✓ | ✓ | ✓ | `shipments.py:583` FSM; verify (e4): re-ship 409, reservation unchanged across 409 |
| Concurrency: FOR UPDATE + Barrier, load-bearing | ✓ | ✓ | ✓ | `shipments.py:609-612` up-front item lock + `post_issue:908` re-lock; verify (g): staging seeded EXACTLY 5, 2 ships via asyncio.Barrier(2)+gather on independent sessions → exactly 1 succeeds, 1 rejected 4xx, staging ends 0, 5 iterations. Assertion is mutation-sensitive: without the lock both would read 5, both issue −5, staging = −5 → the `staging_final != 0 / < 0` checks fail. Genuinely load-bearing, not a no-op. |

### SC5 — Audit + RBAC at HTTP level — PASS
| Truth | Exists | Wired | Works | Evidence |
|---|---|---|---|---|
| pick/pack/ship emit attributable audit rows | ✓ | ✓ | ✓ | verify_gelato_ship_api (5): shipment.picked/packed/shipped rows exist, actor_id set, target_type=shipment |
| int-PK → VARCHAR(36) target_id fix | ✓ | ✓ | ✓ | `router.py:314/344/372` str(shipment.id); verify (5/GUARD): target_id round-trips as string '188' |
| Endpoints gated read/write (401/403/200) | ✓ | ✓ | ✓ | verify_gelato_ship_api: no-token 401, read-only 403 on write routes, no-read 403 on pick-list, admin 200 full flow |

### SC6 — Frontend + regression — PASS
| Truth | Exists | Wired | Works | Evidence |
|---|---|---|---|---|
| Fulfillment pick/pack/ship screen | ✓ | ✓ | ✓ | `Fulfillment.tsx`, `PickDialog.tsx`; Vitest 10/10 pass |
| SO-detail Fulfill/Ship affordance, gated | ✓ | ✓ | ✓ | SalesOrderDetail.test: shows on fulfilling SO w/ gelato enabled∩read, hidden when module disabled or no gelato:read |
| Colocated test asserts REAL request payload | ✓ | ✓ | ✓ | Fulfillment.test:203 asserts POST `/api/v1/gelato/shipments/pick` body `{sales_order_id, staging_bin_id, lines:[{sales_order_line_id, from_bin_id, qty:'5.000000'}]}`; ship POSTs `/shipments/100/ship` |
| Dead-through-UI fix (qty_shipped serialized) | ✓ | ✓ | ✓ | `crumb/schemas.py:402-403` SalesOrderLineRead now serializes qty_picked/qty_shipped; UI renders `line.qty_shipped` (SalesOrderDetailLines.tsx:165); test asserts '4' renders |
| npm run build clean; full regression exit 0 | ✓ | ✓ | ✓ | build exit 0; 19/19 verify_* OK |

## Regression protection
| Criterion | Pinned by |
|---|---|
| SC1 schema/round-trip | All 19 `verify_*` run against migrated 0016 DB; downgrade→upgrade round-trip is a manual reproducible command (no automated downgrade-path test — minor) |
| SC2 pick net-zero / over-pick / non-stock | `verify_gelato_ship.py` scenarios a, e1, e3 |
| SC3 pack partial/accumulate | `verify_gelato_ship.py` scenario d; `verify_gelato_ship_api.py` (4) |
| SC4 balanced JE / control-tie / over-ship / staging-floor / re-ship / concurrency | `verify_gelato_ship.py` scenarios b, c, d, e2, e4, f, g |
| SC5 RBAC 401/403/200 + attributable audit + int-PK guard | `verify_gelato_ship_api.py` |
| SC6 real payload / dead-through-UI / gating | `Fulfillment.test.tsx`, `SalesOrderDetail.test.tsx` |

## Test suite
- `podman exec ... python scripts/verify_gelato_ship.py` → EXIT 0; 21 assertions PASS (incl. b/SC4 CRUX Decimal-exact JE, f control-tie, g load-bearing concurrency)
- `podman exec ... python scripts/verify_gelato_ship_api.py` → EXIT 0; all 401/403/200 + audit + int-PK-string guards PASS
- Full regression (19 scripts): verify_inventory, verify_purchasing, verify_e2e_p8, verify_gl, verify_gl_api, verify_ap, verify_ap_api, verify_reports, verify_reports_api, verify_mousse, verify_mousse_api, verify_crumb, verify_crumb_api, verify_crumb_so, verify_crumb_so_api, verify_gelato, verify_gelato_api, verify_gelato_ship, verify_gelato_ship_api — **all OK, no FAIL**
- `alembic upgrade head / downgrade -1 / upgrade head` → all exit 0
- `npx vitest run Fulfillment.test.tsx SalesOrderDetail.test.tsx` → 2 files, 10 tests pass
- `npm run build` → exit 0 (chunk-size warning only, cosmetic/pre-existing)

## Gaps
- **minor (documentation)** — `.zj/SRD.md` GELATO-01 header still reads "outbound pick→pack→ship (AC3/AC4/AC5 + ship-side AC7) **pending Phase 12b**", and `docs/features/requirements-progress.md:86` still shows GELATO-01 as 12a-only with pick/pack/ship "deferred to 12b". Both now understate reality — 12b is built and green. This is the normal verify-before-docs ordering; the fix loop/manager should add the GELATO-02 (12b) row and flip AC3/AC4/AC5/AC7-ship to verified. Suggested fix: append a GELATO-01 12b evidence row + update SRD status line and BACKLOG p2 (outbound half now closed).
- **minor (regression protection)** — the migration **downgrade** path (`0016→0015` drop of tables/columns) is exercised only by the manual round-trip command, not asserted by any automated test. Feasible-but-absent; low value since round-trip is reproducible and every verify runs on the upgraded schema. Not blocking.

No blocker or major gaps. The two known non-functional lint gates (ESLint flat-config / ruff-not-installed) are pre-existing BACKLOG p1, not a 12b regression; correctness rests on the verify suites, which are green.
