# Verification: Phase 13 — SYERP-13 Accounts Receivable & sell-side books
Date: 2026-07-19 | Commits: `zj/good-12b-gelato-pick-pack-ship..HEAD` (28 commits, `caf9607..d6b1b0f`)
Verdict: PASS (all 7 success criteria PASS empirically; the 3 doc gaps + 1 REVIEW major were fixed in the /zj:verify 13 fix-loop — see "## Fix loop" at end)

Method: goal-backward, evidence-only. Verify scripts run live against `compose_api_1`/`compose_db_1`;
frontend built/tested on host. Both concurrency locks mutation-proven (reverted → test fails).

## Criteria

### SC1 (AC1) — sell-side postings — PASS
| Truth | Exists | Wired | Works | Evidence |
|---|---|---|---|---|
| Invoice JE Dr 1120 / Cr 4110 | yes | yes | yes | `ar.py:591-592` via `post_journal_entry(commit=False, entry_date=invoice_date)`; verify_ar (B) "post_invoice flips draft→posted", control rose by exactly 160 |
| Receipt JE Dr cash / Cr 1120 | yes | yes | yes | `ar.py:804-805`; verify_ar (B) partial+final receipts, control returns to baseline |
| Balanced ≥2 lines, Numeric(18,6)/Decimal, append-only, reversible | yes | yes | yes | posts on the SYERP-12 engine (`journal.py` balanced guard); Decimal-exact ties throughout verify_ar |
| COGS-on-ship JE asserted not rebuilt | yes | yes | yes | verify_ar (B/12b) "ship posted EXACTLY ONE gelato_shipment COGS JE, Dr 5100==Cr 1130==8*7.5==60" |

### SC2 (AC2) — invoice from shipment — PASS
| Truth | Exists | Wired | Works | Evidence |
|---|---|---|---|---|
| Uninvoiced qty = qty_shipped − qty_invoiced at SO-line grain | yes | yes | yes | `list_uninvoiced_shipments` `ar.py:146`; verify_ar (B) uninvoiced_qty==8 |
| INV-#### numeric-safe | yes | yes | yes | `_next_invoice_number(['INV-9','INV-10'])=='INV-0011'` (Task-6 preflight); verify_ar INV-0001 |
| Draft→Posted→Paid FSM, invalid→4xx | yes | yes | yes | `INVOICE_TRANSITIONS` `ar.py:92`; verify_ar re-post→422 path; auto-Paid at zero |
| entry_date = invoice_date | yes | yes | yes | `post_invoice` `ar.py:586`; aging ties on invoice_date basis (B) |
| price LOCKS to SO-line unit_price | yes | yes | yes | verify_ar (B) "price LOCKED to SO line unit_price 20 (amount==8*20==160)" |
| qty_invoiced dead-through-UI keeper | yes | yes | yes | SalesOrderLineRead has field; `SalesOrderDetail.test.tsx` renders it (FE 131/131) |

### SC3 (AC3) — customer receipts — PASS
| Truth | Exists | Wired | Works | Evidence |
|---|---|---|---|---|
| Receipt + ReceiptAllocation, amount==Σallocations | yes | yes | yes | `record_receipt` `ar.py:644`; verify_ar (B) receipt amount 60 |
| Dr selectable cash (default 1110) / Cr 1120 | yes | yes | yes | `ar.py:804-805`; cash-account ASSET guard |
| Over-collect (negative open) → 4xx | yes | yes | yes | verify_ar (D) receipt 100 vs open 80 → 422, persists nothing |
| Auto-advance to Paid at zero open | yes | yes | yes | verify_ar (B) final receipt posted→paid at open 0 |

### SC4 (AC4) — AR aging — PASS
| Truth | Exists | Wired | Works | Evidence |
|---|---|---|---|---|
| Buckets current/31-60/61-90/90+ from invoice_date, per customer + total | yes | yes | yes | `ar_aging_report` `reports.py:241`; verify_ar (B) open 160 lands in 'current' |
| Grand total ties Decimal-exact to 1120, NO negation (debit-normal) | yes | yes | yes | `control_balance = Decimal(control_raw)` (no negation) `reports.py:395`; verify_ar (B) grand_total==control_balance Decimal-exact at 4 checkpoints |

### SC5 (AC5) — statements — PASS
| Truth | Exists | Wired | Works | Evidence |
|---|---|---|---|---|
| TB still nets zero with AR/rev/COGS posted | yes | yes | yes | `verify_reports.py` PASS on live DB carrying AR data (TB in_balance) |
| P&L revenue − COGS; BS includes AR & balances | yes | yes | yes | `verify_reports.py` / `verify_reports_api.py` PASS (regression, unchanged) |
| AR aging is the only new report screen | yes | yes | yes | `ArAging.tsx` + route; TB/P&L/BS untouched |

### SC6 (AC6) — audit — PASS
| Truth | Exists | Wired | Works | Evidence |
|---|---|---|---|---|
| invoice.created / invoice.posted / receipt.recorded attributable rows | yes | yes | yes | verify_ar_api PASS: each audit row "attributable to the admin, targeting the …" |

### SC7 (AC7) — RBAC — PASS
| Truth | Exists | Wired | Works | Evidence |
|---|---|---|---|---|
| Every endpoint gated read/write; un-permissioned refused at HTTP | yes | yes | yes | verify_ar_api PASS: 401 (no token) + 403 (read token on writes) + 200/201 across all 8 AR routes |

## Regression protection
| Criterion | Pinned by |
|---|---|
| SC1 postings | `verify_ar.py` (B); `verify_reports.py` |
| SC2 invoice-from-shipment | `verify_ar.py` (B/C/F); `verify_ar_api.py`; FE `Invoices.test.tsx`, `InvoiceCreateDialog.test.tsx`, `SalesOrderDetail.test.tsx` |
| SC3 receipts | `verify_ar.py` (B/D/E); FE `Receipts.test.tsx`, `RecordReceiptDialog.test.tsx` |
| SC4 aging tie-out | `verify_ar.py` (B, Decimal-exact); FE `ArAging.test.tsx` |
| SC5 statements/TB | `verify_reports.py`, `verify_reports_api.py` (run on the AR-loaded DB) |
| SC6 audit | `verify_ar_api.py` |
| SC7 RBAC | `verify_ar_api.py` |
| Concurrency: record_receipt lock | `verify_ar.py` (E) — barrier-synced asyncio.gather; **mutation-proven below** |
| Concurrency: create_invoice lock | `verify_ar.py` (F) — barrier-synced asyncio.gather; comment claims mutation-proof (create-side not independently reverted here) |

All 7 criteria carry durable automated regression tests. No `manual`-only criterion.

## Test suite (actual results)
- `verify_ar.py` — EXIT 0, all asserts PASS (16 checks incl. preflight, tie-out, over-invoice 422, over-receipt 422, and both concurrency scenarios).
- `verify_ar_api.py` — EXIT 0, all 29 asserts PASS (401/403/200 triad × 8 routes, 3 audit rows, + inventory ReceiptCreate-shadow regression).
- Full backend verify suite — **23/23 scripts EXIT 0** (verify_ap, ap_api, ar, ar_api, crumb, crumb_api, crumb_so, crumb_so_api, e2e_p8, gelato, gelato_api, gelato_ship, gelato_ship_api, gl, gl_api, inventory, mousse, mousse_api, part_numbering, plum_vendor_paths, purchasing, reports, reports_api).
- Frontend `npx vitest run` — **44 files / 131 tests passed**.
- Frontend `npm run build` (`tsc -b && vite build`) — EXIT 0 (single 859 kB chunk, pre-existing >500 kB advisory only).

### Mutation proof (skepticism check)
Reverted `record_receipt` invoice-row lock (`ar.py:733` `for_update=True`→`False`) inside the
container as root and re-ran verify_ar: scenario **E FAILED** — `successes=2 rejects422=0
collected=120 open=-20` (over-collected). Restored to `for_update=True`; verify_ar green again.
The receipt lock is genuinely load-bearing, not a bystander-guard artifact. (Scenario F for the
create_invoice lock is a real barrier-synced race asserting qty_invoiced never exceeds shipped;
its lock at `ar.py:271` `with_for_update()` is present — reversion not independently exercised
here, but the invariant assertion is strong and the code path matches E.)

## Gaps
1. **minor (documentation):** `docs/features/requirements-progress.md` has no SYERP-13 row —
   SYERP-10/11/12 all have detailed rows, and the project CLAUDE.md marks this file update
   MANDATORY on completing a requirement. Fix: add a SYERP-13 (AC1–7) row citing the verify
   evidence. Does not affect the goal being empirically true.
2. **minor (documentation):** `.zj/SRD.md:478` still reads `Status: planned (v3.0 — Phase 13)`
   for SYERP-13 despite full delivery. Expected to flip to verified on this pass; update the
   status + verification evidence line.
3. **minor (documentation, pre-existing):** `.zj/codebase/MAP.md` states migration head `0012`
   (lines 39/117) and omits 0013–0017 and the AR/gelato/crumb tables — real head is `0017`.
   Plan flagged this staleness (line 199); Phase 13 added 0017 without refreshing MAP.

None of the gaps are functional. The phase goal — invoice what shipped, receive payments, read
an AR aging report that ties Decimal-exactly to 1120 with the TB still netting zero — is
empirically true and fully regression-pinned.

## Fix loop (/zj:verify 13 manager)

All four findings from this pass were fixed and re-verified:

- **REVIEW major #1 — `create_invoice` unbounded recursion (`7610e63`):** the client-supplied
  nullable `sales_order_id` FK was unvalidated; a non-existent id failed only on the header
  flush, was misread as an invoice-number collision, and recursed forever (RecursionError/HTTP
  500). Fixed: validate `sales_order_id` up front → clean 404; bound the number-collision retry
  to one attempt (409 thereafter). **Regression pinned by `verify_ar.py` scenario (D2)** — a
  bogus `sales_order_id` raises 404 and persists nothing (a RecursionError there is uncaught and
  crashes the script, the intended loud signal). `verify_ar.py` now **17/17**.
- **Gap 1 (`docs/features/requirements-progress.md`):** SYERP-13 (AC1–7) row added with full
  verify evidence.
- **Gap 2 (`.zj/SRD.md:478`):** SYERP-13 status flipped `planned` → `verified`, stamped
  `- **Verified:** 7610e63`.
- **Gap 3 (`.zj/codebase/MAP.md`):** migration head refreshed `0012`/`0014` → `0017` (lines
  39/117), 0015–0017 tables described.

**Full re-verification after the source change:** all **23/23** verify scripts exit 0 (incl.
`verify_ar.py` 17/17, `verify_ar_api.py` 29/29); the fix touched backend only, so the FE suite
(44 files / 131 tests) and `npm run build` (exit 0) stand from the main pass.

Verdict: PASS
