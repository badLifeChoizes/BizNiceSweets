# Verification: Phase 09b — AP bills, PO match & payments
Date: 2026-07-12 | Commits: `d7f3294..f7b51ba` (9b work: `9bbfdf0..f7b51ba`, master..feature-syerp-ap-bills)
Verdict: PASS

> **Fix-loop 2026-07-12 (post-review).** The `reviewer` found one MAJOR that the
> sequential verify scripts could not surface: `create_bill` and `record_payment`
> guarded double-billing / overpayment with a read-then-write and no row lock, so two
> concurrent requests for the same PO line (or bill) could both pass and both commit —
> billing a receipt twice (2150 GR/IR never clears) or overpaying a bill (AP negative).
> **Fixed:** `create_bill` now `SELECT … FOR UPDATE`-locks each matched PO-line row and
> `record_payment` locks each target bill row, both up-front in sorted id order
> (deadlock-safe), serializing the contended transactions. Pinned by two new durable
> `verify_ap.py` scenarios (j) concurrent create_bill and (k) concurrent payment, run
> via `asyncio.gather` — each asserts exactly one succeeds, the other 422s, and the
> receipt/bill is billed/paid exactly once. **Full re-verification after the fix (all
> green):** `test_ap.py` 14 · `verify_ap.py` **24/24** · `verify_ap_api.py` all PASS ·
> regression `verify_gl` 28 / `verify_purchasing` 18 / `verify_inventory` 15 /
> `verify_e2e_p8` 18 (all exit 0) · frontend 72/72 unchanged (backend-only fix). Review
> findings #2/#3 (both minor, edge-case) logged to PLAN `## Noticed`.

All six success criteria are proven EMPIRICALLY against the running dev stack
(`compose_db_1` + `compose_api_1`, both up). Pure unit tests, both live verify scripts,
all four regression scripts, and the full frontend suite pass. The GR/IR-clears-to-zero
crux holds Decimal-exact. Only minor documentation-staleness gaps remain (SRD/requirements
status lines not yet advanced to reflect AC4/AC5 delivery — expected pre-close).

## Criteria

### SC1 (AC4) — Receipt-driven bill creation, exact-match or 4xx — VERIFIED
| Truth | Exists | Wired | Works | Evidence |
|---|---|---|---|---|
| `list_unbilled_receipts` surfaces `qty_received − Σ matched_qty` (coalesce each side) | yes (`service.py:2605`) | GET `/ap/unbilled-receipts` in OpenAPI | yes | verify_ap.py (a): received 6@5 line surfaces `unbilled_qty=6, unit_cost=5` PASS |
| Matched line bills exactly `unbilled×unit_cost` or rejects 422 | yes (`_is_exact_match` service.py:2505) | `create_bill` service.py:2676 | yes | verify_ap.py (b): exact match → total 20; qty-variance (3 of 4) → 422, and rejected bill persisted NOTHING (line still fully unbilled) PASS |
Pinned by: `verify_ap.py` (a)(b); unit `tests/syerp/test_ap.py` exact-match + unbilled-qty cases.

### SC2 (AC4) — Non-PO EXPENSE/ASSET lines with positive amount — VERIFIED
| Truth | Exists | Wired | Works | Evidence |
|---|---|---|---|---|
| Expense line on EXPENSE/ASSET account, amount>0 | yes | `create_bill` | yes | verify_ap.py (c): EXPENSE line total 50 PASS |
| REVENUE account rejected 422 | yes | service guard + schema | yes | verify_ap.py (c): REVENUE → 422 PASS |
| amount ≤ 0 rejected | yes (schema validator) | `BillLineCreate` | yes | verify_ap.py (c): amount 0 → pydantic ValidationError PASS |
Pinned by: `verify_ap.py` (c).

### SC3 (AC4) — One balanced JE, Draft→Posted FSM, source-linked — VERIFIED
| Truth | Exists | Wired | Works | Evidence |
|---|---|---|---|---|
| Posting builds ONE balanced JE via `post_journal_entry(commit=False)` | yes (`post_bill` service.py:3026) | POST `/ap/bills/{id}/post` | yes | verify_ap.py (d): Σdebits==Cr 2110==20, source_type='ap_bill', source_id=bill.id, Dr GR/IR 2150=20 PASS |
| Draft→Posted enforced via `BILL_TRANSITIONS`; invalid → 4xx | yes (service.py:2522, `_bill_transition_allowed`) | service | yes | verify_ap.py (d): re-post posted bill → 422 PASS |
| Bill flips to posted + posted_at stamped | yes | service | yes | verify_ap.py (d) PASS |
Pinned by: `verify_ap.py` (d); unit `test_ap.py` transition legal/illegal.

**GR/IR-clears-to-zero crux — VERIFIED.** verify_ap.py (e): 2150 balance **pre-receipt =
-450.000000**, after receive(7@5)+post_bill **post-bill = -450.000000**, delta 0 Decimal-exact.
The receipt's Cr GR/IR 35 and the bill's Dr GR/IR 35 net to zero. Pinned by `verify_ap.py` (e).

### SC4 (AC5) — Payment posting, open-balance math, overpay reject, auto-Paid — VERIFIED
| Truth | Exists | Wired | Works | Evidence |
|---|---|---|---|---|
| Dr AP 2110 / Cr chosen cash-or-bank | yes (`record_payment` service.py:3100) | POST `/ap/payments` | yes | verify_ap.py (f): partial JE Dr 2110/Cr 1110=20; (i) via 1110 and 1111 each credit the chosen account PASS |
| open_balance = billed − Σ alloc (coalesce each side) | yes (`list_bills`/`get_bill` coalesce, service.py:2978) | service | yes | verify_ap.py (f): 50-bill, pay 20 → open 30 PASS |
| Overpayment rejected 422, persists nothing | yes (`_is_overpayment` service.py:2481) | service | yes | verify_ap.py (g): pay 30 vs 25 open → 422; bill unchanged, 0 orphan Payment/allocation rows PASS |
| Auto-advance to Paid at zero open balance | yes (`advance_bill_status`) | service | yes | verify_ap.py (f): final 30 → status 'paid', open 0 PASS |
| Payment JE source-linked `ap_payment` | yes | service | yes | verify_ap.py (f) PASS |
Pinned by: `verify_ap.py` (f)(g)(i); unit `test_ap.py` overpayment reject/boundary.

### SC5 (AC4/AC5 UI) — Create+match, post, pay from UI, reachable from SyerpNav — VERIFIED (component-level)
| Truth | Exists | Wired | Works | Evidence |
|---|---|---|---|---|
| Routes registered | yes (`App.tsx:61-62`, list before `/:id`) | yes | yes | tsc -b clean |
| Bills tab in SyerpNav | yes (`SyerpNav.tsx:24`) | yes | yes | — |
| Post gated draft-only, Pay gated posted-only | yes (`BillDetail.tsx:220-221` canPost/canPay) | yes | yes | `npx vitest run Bills BillDetail` → 8/8 PASS |
| Pay dialog client-guards amount ≤ open_balance | yes (`PayBillDialog`) | yes | yes | BillDetail.test.tsx PASS |
Pinned by: `Bills.test.tsx`, `BillDetail.test.tsx` (8 tests). NOTE: full browser end-to-end
(real partial→full→Paid navigation) is component-mocked, not driven in a real browser — manual
UAT (project already tracks "UI flow UAT pending, v2.0 milestone"). Acceptable per plan.

### SC6 (AC8/AC9) — Audit + RBAC on all endpoints, proven over HTTP — VERIFIED
| Truth | Exists | Wired | Works | Evidence |
|---|---|---|---|---|
| bill.created / bill.posted / payment.recorded audit rows, attributable | yes (router `write_audit` after commit) | yes | yes | verify_ap_api.py: all three found, actor_id==admin, correct target_type PASS |
| All mutations `syerp:write` → 403 read-only, 401 anon | yes | router `require_permission` | yes | verify_ap_api.py: 3 mutation endpoints 403+401 PASS |
| All GETs `syerp:read` → 200 read token, 401 anon | yes | router | yes | verify_ap_api.py: 4 GET endpoints 200+401 PASS |
Pinned by: `verify_ap_api.py` (24 assertions).

## Regression protection
| Criterion | Pinned by |
|---|---|
| SC1 exact-match / unbilled-qty | `verify_ap.py` (a)(b) + `tests/syerp/test_ap.py` |
| SC2 expense-line account-type guard | `verify_ap.py` (c) |
| SC3 balanced JE + FSM | `verify_ap.py` (d) + `test_ap.py` transitions |
| SC3 GR/IR-clears-to-zero crux | `verify_ap.py` (e) — pre/post 2150 balance equality |
| SC4 open-balance / overpay-persists-nothing / auto-Paid | `verify_ap.py` (f)(g)(i) + `test_ap.py` overpayment |
| SC5 UI gating | `Bills.test.tsx`, `BillDetail.test.tsx` |
| SC6 audit + RBAC 403/401/200 | `verify_ap_api.py` |
Note: verify_*.py are the project's accepted backend-truth harness (DB-backed pytest is broken
by design, D-P7-4). They are durable and re-runnable but require the live stack and are NOT part
of an automated CI gate — a standing project-level limitation, not new to this phase.

## Test suite
- `cd backend && .venv/bin/python -m pytest tests/syerp/test_ap.py -q` → **14 passed**.
- `verify_ap.py` (in compose_api_1) → **22/22 PASS, exit 0**. Crux 2150: pre=-450.000000, post=-450.000000.
- `verify_ap_api.py` (in compose_api_1) → **24/24 PASS, exit 0**.
- Regression (PYTHONPATH=/app): `verify_gl.py` 28/0 exit 0 · `verify_purchasing.py` 18/0 exit 0 ·
  `verify_inventory.py` 15/0 exit 0 · `verify_e2e_p8.py` 18/0 exit 0.
- Frontend: `npx tsc -b` exit 0; `npx vitest run` → **22 files, 72 tests passed**.
- OpenAPI confirms the 5 AP routes (get/post bills, get bill, post bill/post, get/post payments,
  get unbilled-receipts); NO PUT/DELETE on a posted bill.

## Gaps
- **Minor (documentation):** `.zj/SRD.md:361` — SYERP-12 status still reads
  "AC1/2/3/8/9 verified Phase 9a; AC4–7 pending 9b/9c" and the AC4–7 bullet (line 427) is
  unchanged. AC4/AC5 are now built and live-verified; the status line and evidence entry
  should be advanced at phase-close. Failure scenario: a reader trusts the SRD and believes AP
  bills/payments are unbuilt.
- **Minor (documentation):** `docs/features/requirements-progress.md:45,55` — the SYERP-12 row
  still says "AC4–7 remain in 9b/9c" with no `verify_ap.py`/`verify_ap_api.py` evidence. Should
  gain a 9b row citing the 22/22 + 24/24 live proofs. Failure scenario: requirements-progress
  under-reports delivered scope.
- **Minor (documentation):** `.zj/codebase/MAP.md` does not mention the new `syerp_bill`,
  `syerp_bill_line`, `syerp_payment`, `syerp_payment_allocation` tables or the AP service
  functions. MAP is high-level so this is low-impact, but the AP subledger is now a real part
  of the SYERP module surface. Failure scenario: MAP under-describes the module.

These are the only gaps; they are documentation catch-up expected at phase-close, not
behavioral defects. No blocker or major gaps found.

## Documentation
See the three minor gaps above. All are stale/missing status entries, not incorrect
architecture claims. The PLAN's own "Noticed" and "Deviations" sections already record the
known cosmetic issues (stale `BillLineRead` interface in `Bills.tsx`, misleading
`partially_paid` schema comment, pre-existing `alembic check` drift) — none affect this phase's
criteria.
