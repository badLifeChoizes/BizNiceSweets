# Work Log — Milestone v2.0 "Operations"

**Closed:** 2026-07-16 · **Tag:** `v2.0` · **Author:** ne1ne
**Audit:** `.zj/MILESTONE-v2.0-AUDIT.md` (verdict clean, 1 minor gap G1 fixed at close)

## Scope

v2.0 delivered the **operations core**: SYERP inventory + purchasing, a full double-entry
GL with accounts payable and financial statements, and MOUSSE materials-only work orders —
closing the definition of done *"Can track inventory, raise purchase orders, keep real books
(double-entry GL with AP + financial statements), and execute work orders that consume PLUM
BOMs and inventory."*

Delivered across five phases: **Phase 8** (SYERP inventory & purchasing), **Phase 9a/9b/9c**
(GL posting → AP bills/match/payments → AP aging + statements), **Phase 10** (MOUSSE work
orders). Every phase was planned → built → verified goal-backward → retro'd independently.

## Effort

- **Phase 8** shipped inside the v1.0 tag tree (built before v1.0 formally closed, D-P8-11) —
  its ~30 commits are counted in the v1.0-era work log, not double-counted here.
- **Phases 9a→10 + milestone close:** **104 commits** (50 feat · 8 fix · 33 docs · 11 test ·
  2 chore), sole author ne1ne, over **~12.7 hours across 8 inferred work sessions** on 4 active
  days (2026-07-11 → 2026-07-16). Dense pace: 46 commits 07-11, 22 on 07-12, 31 on 07-13, 5 at
  the 07-16 close. (`/zj:timeline` renders the visual; `.zj/logs/timeline.html`.)

## Shipped work, by phase

### Phase 8 — SYERP inventory & purchasing (SYERP-10, SYERP-11)
Inventory items (optional PLUM link) with per-location on-hand derived from an append-only
transaction ledger, moving-weighted-average valuation, manual adjustments + transfers under a
negative-stock floor guard; a Draft→Approve→Receive PO workflow whose receipts post real
inventory at PO unit cost. Migrations 0007/0008. Backend proven live by `verify_inventory`
(14/14), `verify_purchasing` (18/18), fresh-DB `verify_e2e_p8` (18/18).
Tag `zj/good-08-syerp-inventory-purchasing`.

### Phase 9a — GL posting engine + receipt auto-post (SYERP-12 AC1/2/3/8/9)
Append-only, immutable, self-FK-reversible `JournalEntry`/`JournalLine`; balanced-only posting
(422 otherwise); derived account balances + account register; manual general-journal UI; and
the crux — a PO receipt now atomically posts a balanced **Dr 1130 Inventory / Cr 2150 GR/IR**
JE alongside the stock receipt. Seeded 2150 GR/IR. Migration 0009. Verify fix-loop closed two
majors (zero-cost receipt regression, double-reversal guard) and introduced the first HTTP-level
`verify_gl_api.py`. `verify_gl` 28/28, `verify_gl_api` 9/9.
Tag `zj/good-09a-gl-posting-engine`.

### Phase 9b — AP bills, PO match & payments (SYERP-12 AC4/AC5)
Vendor bills matched to PO receipts at PO-line grain (exact match → **Dr GR/IR / Cr AP**, GR/IR
clears to zero, variance rejected 4xx); non-PO expense lines; a Draft→Posted→Paid FSM; payments
(**Dr AP / Cr Cash/Bank**, partial, overpayment 4xx, auto-Paid) modelled as Payment +
PaymentAllocation (1→N bills). Seeded 1111 Bank–Checking. Migration 0010. Verify fix-loop
row-locked a concurrent double-bill/overpayment race (`SELECT … FOR UPDATE`, sorted-id order).
`verify_ap` 24/24 (incl. two concurrency scenarios), `verify_ap_api` + `test_ap` 14.
Tag `zj/good-09b-ap-bills-match-payments`.

### Phase 9c — AP aging + financial statements (SYERP-12 AC6/AC7)
AP aging buckets (per vendor + total) tying Decimal-exact to the 2110 control balance via a real
`Bill.bill_date` unified with the JE `entry_date` (D-P9c-1); Trial Balance, P&L (over a period),
and Balance Sheet (with a computed current-year net-income line), all derived from posted GL
activity. Migration 0011. Zero reviewer majors — first read-only derivation phase.
`verify_reports` 17/17, `verify_reports_api` 13/13.
Tag `zj/good-09c-ap-aging-financial-statements`.

### Prerequisite chore — syerp/service.py split (D-P10-4)
Split the ~3,824-line `syerp/service.py` monolith into a 10-submodule `service/` package behind
unchanged public functions (verbatim AST split, zero behavior change), on a separate chore branch
verified green against all `verify_*` scripts before MOUSSE built on it. Re-export defect
(annotated-assign maps the AST filter dropped) caught by pytest collection, fixed `3d59068`.

### Phase 10 — MOUSSE work-order core, materials-only (MOUSSE-01)
New `backend/app/modules/mousse/` module. Work orders snapshot a PLUM single-level BOM at release,
consume SYERP inventory via explicit component issue (**Dr 1140 WIP / Cr 1130** at moving-avg),
and on completion receive the finished good (**Dr 1130 / Cr 1140**) so WIP clears to zero
Decimal-exact; FSM Draft→Released→In Progress→(On Hold⇄In Progress)→Completed (+Cancelled), with
audited under-issue override. Migration 0012, seeded `mousse:read/write`. Verify fix-loop closed
one major: completion drifted the 1130 control account from the subledger on non-divisible WIP →
now routes the residual to a seeded **5190 Inventory Rounding** account (D-P10-2 amended) so both
1140 clears and 1130 ties. Concurrency pre-empted by design (row lock + `asyncio.Barrier` verify).
`verify_mousse` 34/34, `verify_mousse_api` 34/34.
Tag `zj/good-10-mousse-work-orders`.

### Milestone close (2026-07-16)
Goal-backward audit of all four DoD clauses against the running stack; G1 (P&L empty-`from` 422)
fixed `2578ca5`; records produced; `v2.0` tagged.

## Key decisions (with why)

- **D-P9-1** — GL goes to *full subledger auto-posting* (receipts + AP docs post balanced JEs;
  statements derive from posted activity), not document-only aging. The deepest of three options;
  chosen so the books are real, not reconstructed.
- **D-P9-4** — Accounts receivable *deferred to the CRUMB milestone* (new SYERP-13). AR invoices
  belong downstream of sales orders, which don't exist yet; SYERP-12 narrowed to AP+GL+reporting.
- **D-P9b-2** — Matched bill lines require *exact match* so GR/IR clears to zero; variance rejected
  4xx, no purchase-price-variance account in v2.0. Keeps the clearing invariant provable.
- **D-P10-1** — Phase 10 = *materials-only* WO core; routing/work-centers, labor/overhead, and the
  shop-floor operator view deferred to a follow-on MOUSSE phase. This slice alone closes the DoD.
- **D-P10-2 (amended)** — WO costing = actual moving-average, WIP 1140 clears to zero; the
  completion residual on non-divisible WIP routes to a new 5190 Inventory Rounding account so the
  1130 control account ties to the subledger (the audit-caught major).
- **D-P10-4** — the `syerp/service.py` split runs as a *separate chore branch first*, kept out of
  the MOUSSE feature diff so both reviews stay clean.
- **D-M2-2** — human click-through UAT *deferred to a tracked post-tag task*, not a tag blocker;
  backend is live-proven and the UI is wired + contract-checked by the audit (D-P7-5 precedent).
- **D-M2-4** — next milestone = *Customer & logistics* (CRUMB + GELATO + AR).

## Verification evidence

- **13/13 live `verify_*.py` scripts exit 0** against the running stack (re-run at milestone close):
  inventory, purchasing, e2e_p8, gl, gl_api, ap, ap_api, reports, reports_api, mousse, mousse_api,
  part_numbering, plum_vendor_paths. ~200 assertions.
- Whole-DB **trial balance nets 0.000000**; control accounts tie to subledgers within clean scope.
- Frontend **`npm run build` clean**, **90/90 Vitest** (29 files), `tsc -b` clean.
- Alembic head **0012**. `zj doctor` format-clean (BACKLOG tag-format warnings are known cosmetic).

## Carried debt (into v3.0)

BACKLOG **p1** rode the whole milestone unpaid and was deferred again at close (D-M2-4 chose
features next): **no CI**, the **live-DB pytest harness still broken** (100 skips, D-P7-4), **both
lint gates non-functional**. Correctness rested on `verify_*` + Vitest throughout. Plus the
**master-merge debt** — v2.0 tagged on the unmerged `feature-mousse-work-orders` tip (D-M2-3);
master is 98 commits behind. `/zj:ship` owes the reconciliation. And the **human UAT** (D-M2-2),
now a pre-public-release gate.
