# Verification: Phase 09c — AP aging + financial statements
Date: 2026-07-12 | Commits: 81c2256..226d1b8 (15 build commits)
Verdict: PASS (fix-loop closed the FE-test gap in `0eac5d4`; 2 minor doc gaps remain — SRD
updated at close-out, MAP.md refresh owed to `/zj:docs`; neither blocks the phase goal)

Method: goal-backward, evidence-only. All backend evidence re-run live against
`compose_db_1`/`compose_api_1` (alembic `0011 (head)` confirmed). Frontend suites
re-run on host. Assertion source in `verify_reports.py` inspected to confirm the SC2
tie-out is genuinely exact-Decimal, not a printed claim.

## Criteria

### SC1 (AC6) — AP aging buckets per-vendor + grand total, aged from bill_date, caller as-of — PASS
| Truth | Exists | Wired | Works | Evidence |
|---|---|---|---|---|
| `ap_aging_report(db, as_of)` buckets current/31-60/61-90/90+ from bill_date | yes | yes | yes | `service.py:3404`; endpoint `router.py:1286` `GET /ap/aging?as_of=` |
| Per-bill open = Σbilled − Σpaid, each side coalesced, payments filtered by payment_date | yes | yes | yes | `verify_reports.py` PASS: bills at ages 10/45/75/120 land current==100/d31_60==200/d61_90==300/d90_plus==400 |
| Per-vendor row sums to grand total | yes | yes | yes | `verify_reports.py` PASS: vendor fields sum to 1000, roll into grand total delta-by-delta |
| UI renders per-vendor buckets + grand-total footer, as-of drives refetch | yes | yes | yes | `App.tsx:65`, `SyerpNav.tsx:25`; `ApAging.test.tsx` 4/4 (buckets, footer, as_of refetch, tie-out badge) |

### SC2 (AC6, the crux) — aging grand total == date-filtered derive 2110, exact-Decimal — PASS
| Truth | Exists | Wired | Works | Evidence |
|---|---|---|---|---|
| control_balance = date-filtered 2110 (Σdr−Σcr, entry_date<=as_of), negated to positive payable | yes | yes | yes | `service.py:3404` ap_aging_report; JE entry_date set from bill.bill_date (`729ec00`, post_bill) so subledger & 2110 age on one basis |
| `grand_total.total == control_balance` asserted **exact-Decimal** (no tolerance) | yes | yes | yes | `verify_reports.py:327` `report_a.grand_total.total == report_a.control_balance and in_balance is True` → PASS (1000.000000 == 1000.000000) |
| Partial payment (200 of 500) reduces open AND 2110 leg; tie-out still exact | yes | yes | yes | `verify_reports.py:361-366` PASS — open 300 remains, equality holds exactly |
| DRAFT bill excluded from BOTH aging and 2110 (divergence guard) | yes | yes | yes | `verify_reports.py:378-384` PASS — draft(999) changes neither total, in_balance still True |

The assertions are literal `Decimal == Decimal` equality with no rounding/epsilon;
the partial-payment and DRAFT-exclusion cases are both present and unweakened. Crux holds.

### SC3 (AC7) — Trial Balance, Σdebits == Σcredits exact-Decimal — PASS
| Truth | Exists | Wired | Works | Evidence |
|---|---|---|---|---|
| `trial_balance(db, as_of)` per-account net dr/cr, entry_date<=as_of | yes | yes | yes | `service.py:3567`; endpoint `router.py:1301` |
| total_debit == total_credit exact; rollup parents absent | yes | yes | yes | `verify_reports.py:398` PASS; parents 2100/1000/3100 absent from rows |
| UI Trial Balance tab shows balanced totals | yes | yes | yes | `FinancialReports.test.tsx` (TB tab, balanced footer) |

### SC4 (AC7) — P&L over [from,to], net_income = revenue − expense — PASS
| Truth | Exists | Wired | Works | Evidence |
|---|---|---|---|---|
| `profit_loss(db, from, to)` sums REVENUE/EXPENSE inclusive window | yes | yes | yes | `service.py:3634`; endpoint `router.py:1316` (both bounds required → 422) |
| net_income == total_revenue − total_expense; out-of-period excluded | yes | yes | yes | `verify_reports.py` PASS: Δrev==100/Δexp==40, identity holds, 2000/2002 entries excluded |
| UI P&L tab shows revenue/expense lines + net income | yes | yes | yes | `FinancialReports.test.tsx` (P&L tab) |

### SC5 (AC7) — Balance Sheet, assets == liabilities+equity exact, computed net-income line — PASS
| Truth | Exists | Wired | Works | Evidence |
|---|---|---|---|---|
| `balance_sheet(db, as_of)` sign-normalized sections | yes | yes | yes | `service.py:3704`; endpoint `router.py:1332` |
| total_assets == total_liabilities + total_equity exact | yes | yes | yes | `verify_reports.py:518` PASS, in_balance True |
| Computed 3130 line == Σrev−Σexp to date; ledger 3130 stays empty | yes | yes | yes | `verify_reports.py` PASS: exactly one appended 3130 line == profit_loss(BOT,as_of).net_income; zero posted 3130 lines |
| UI Balance Sheet tab shows sections + balanced total | yes | yes | yes | `FinancialReports.test.tsx` (BS tab) |

Note: the computed 3130 line is appended **unconditionally** (build `## Noticed` T8) —
correct only while ledger 3130 stays empty; a future closing-entry phase must guard it.
Out of scope now; recorded so it is not lost.

### SC6 (AC8/AC9) — every report endpoint gated by syerp:read; read-only ⇒ no mutation audit — PASS
| Truth | Exists | Wired | Works | Evidence |
|---|---|---|---|---|
| All 4 endpoints `Depends(require_permission("syerp:read"))` | yes | yes | yes | `router.py:1289,1304,1320,1335` |
| 401 unauth / 403 no-perm / 200 with perm at HTTP layer | yes | yes | yes | `verify_reports_api.py` PASS — 200/401/403 across all 4 + 422 on missing P&L bound |
| Read-only: no write_audit / no mutation-audit rows | yes | yes | yes | Code inspection: none of the 4 endpoints call `write_audit` (`router.py:1286-1345`); RBAC status codes are the SC6 gate per plan |

## Regression protection
| Criterion | Pinned by |
|---|---|
| SC1 | `backend/scripts/verify_reports.py` (buckets, per-vendor→grand-total) + `frontend/src/routes/syerp/ApAging.test.tsx` |
| SC2 | `backend/scripts/verify_reports.py:327,361,378` (exact-Decimal tie-out incl. partial-pay + draft-exclusion) — the crux pin |
| SC3 | `verify_reports.py:398` + `FinancialReports.test.tsx` |
| SC4 | `verify_reports.py` (P&L Δ + out-of-period) + `FinancialReports.test.tsx` |
| SC5 | `verify_reports.py:518` + `FinancialReports.test.tsx` |
| SC6 | `backend/scripts/verify_reports_api.py` (200/401/403/422) |
| bill_date UI field submission | `frontend/src/routes/syerp/components/BillCreateDialog.test.tsx` (added in fix-loop `0eac5d4`) |

Every success criterion has a durable automated test. Standing caveat (pre-existing,
MAP.md Concern #5, D-P7-4): the `verify_*.py` scripts are not in pytest collection and
there is no CI — they are the backend regression gate re-run at each `/zj:verify`, per
project convention. DB-backed pytest is broken (100 skips), so this is expected, not new.

## Test suite (all re-run this verification)
- `verify_reports.py` (in-container): **17/17 PASS, exit 0** — full output captured, incl. SC2 crux detail `grand_total=1000.000000 control_balance=1000.000000`.
- `verify_reports_api.py` (in-container): **13/13 PASS, exit 0** — 200/401/403 × 4 endpoints + 422 missing-bound.
- Regression (in-container): `verify_ap` 24 PASS / `verify_gl` 29 / `verify_purchasing` 19 / `verify_inventory` 16 / `verify_e2e_p8` 19 — **all exit 0**, counts unchanged from build report.
- Backend pytest (host `.venv`, not runtime container): **117 passed, 100 skipped, exit 0** — corroborates build claim. (pytest is absent from the prod runtime image, so cannot run in-container — expected; verify scripts are the in-container gate.)
- Frontend `npm run test` (vitest): **79/79 passed, 24 files, exit 0**; `npx tsc -b` clean, exit 0.
- `alembic current` in api container: `0011 (head)`.

## Gaps
1. **minor — SRD.md SYERP-12 status stale.** `.zj/SRD.md:361` still reads
   "AC6/7 pending 9c"; `:367-368` and `:433` say AP aging + financial statements
   "unbuilt / NOT yet built, Phase 9b/9c." The functionality is now built and
   live-proven. `docs/features/requirements-progress.md:47,53` IS updated correctly.
   Suggested fix: at ship, flip SYERP-12 status to AC6/AC7 verified and update the
   three prose lines. (SRD is typically ship-time authority, so this is expected lag,
   but it does not yet state the new truth.)
2. **minor (pre-existing, not introduced by this phase) — `.zj/codebase/MAP.md` stale.**
   Migration list stops at 0009 (`:39`, self-flagged "predates Phase 8/9a; refresh owed
   via /zj:docs"); `:124` still claims `syerp/service.py` is 273 lines (now ~3,700 /
   ~133 KB with the four report functions). No 09c report endpoints/screens listed.
   Suggested fix: `/zj:docs` refresh covering Phases 8–9c.
3. **minor — no frontend test pins the bill-date field.** ✅ **FIXED in verify fix-loop
   (`0eac5d4`).** Added `frontend/src/routes/syerp/components/BillCreateDialog.test.tsx`
   (2 tests): the bill-date field renders defaulted to today, and a full submit includes
   the chosen `bill_date` in the POST `/ap/bills` body. FE suite now 81/81 (was 79),
   `tsc -b` clean.
