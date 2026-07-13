# STATE — BizNiceSweets
Updated: 2026-07-13 (Phase 10 **build in flight** — MOUSSE WO core on `feature-mousse-work-orders`; D-P10-4 chore DONE)

## Position

- **Step:** **Phase 10 build in flight (2026-07-13)** — MOUSSE materials-only WO core on branch
  `feature-mousse-work-orders`, cut off the chore tip `6293c96` (D-P10-4 done). Executing
  `.zj/phases/10-mousse-work-orders/PLAN.md` (20 tasks). Task checklist:
  `docs/tasks/feature-mousse-work-orders.md`. **Deviation from PLAN Task 1:** branch cut off the
  D-P10-4 chore tip (which carries the syerp `service/` split), NOT tag `zj/good-09c` — the
  owner chose "chore first, build on the clean post-split base."
- **D-P10-4 chore COMPLETE (2026-07-13, committed `6293c96` on `chore-syerp-service-split`).** Split
  `backend/app/modules/syerp/service.py` (3,824 lines) into a `service/` package of 10 cohesive
  submodules (`_common`/`partners`/`locations`/`accounts`/`items`/`inventory`/`journal`/`purchasing`/
  `bills`/`reports`) behind unchanged public functions — zero behavior change, verbatim AST split (93
  top-level defs identical), re-exported via `service/__init__.py` so all `from
  app.modules.syerp.service import X` call sites keep working. `verify_gl.py` monkeypatch retargeted
  to `gl_service.purchasing._gl_account_id_by_code`. All 11 `verify_*` scripts exit 0. MAP.md
  refreshed (migrations→0011, service package). This chore branch merges to master ahead of / with
  the MOUSSE feature branch (stacked).
- **Project:** BizNiceSweets
- **Step:** **Phase 10 planned (2026-07-13)** — MOUSSE manufacturing execution core, materials-only
  slice (MOUSSE-01). `.zj/phases/10-mousse-work-orders/PLAN.md` = **20 tasks** (new
  `backend/app/modules/mousse/` module: models→migration 0012→perm seed→schemas→service→router→
  register→`verify_mousse.py`+`verify_mousse_api.py`→regression→5 frontend). Branch
  `feature-mousse-work-orders` cuts off tag `zj/good-09c-ap-aging-financial-statements` (D-P10-8).
  Goal: a WO consumes a PLUM single-level BOM + SYERP inventory to produce a finished good, cost
  flowing **Dr 1140 WIP / Cr 1130 on issue** and **Dr 1130 / Cr 1140 on completion so WIP clears to
  zero** (the accounting crux, proven pre/post Decimal-exact). Closes the last v2.0 DoD clause.
- **Decisions D-P10-1..9** (in DECISIONS.md): materials-only, routing/labor/shop-floor deferred
  (D-P10-1); actual moving-avg costing, WIP clears, no variance (D-P10-2); explicit issue action
  (D-P10-3); single-level direct BOM, sub-assemblies issued as components (D-P10-5, owner-confirmed);
  reject release if any component has no linked InventoryItem (D-P10-7); **completion blocked on
  under-issue unless an audited `override_incomplete`, plus an On Hold pause/resume state**
  (D-P10-9, owner). Surfaces verified pre-plan: `post_receipt`/`post_journal_entry` (both
  `commit=False`), `_adjustment_violates_floor`, `_gl_account_id_by_code`, the create_bill FOR-UPDATE
  lock template; PLUM `get_released_revision` + direct `PlumBomItem`; CoA 1130/1140 already seeded;
  `mousse` module already in `modules_seed.py`.
- **Next action: the D-P10-4 prerequisite chore FIRST** — split
  `backend/app/modules/syerp/service.py` (**3,824 lines**, BACKLOG p2) into cohesive submodules
  behind unchanged public functions **+** refresh `.zj/codebase/MAP.md` (stale at migration 0009;
  head is 0011) on a **separate chore branch** off `zj/good-09c-ap-aging-financial-statements`,
  verified green against the existing `verify_*` scripts (no behavior change). Then `/zj:build 10`
  builds MOUSSE on a clean base. *(Owner chose "separate chore first" over folding the refactor into
  the feature diff — keeps the MOUSSE review clean. The MAP refresh half can run via `/zj:docs`.)*
- **Retro 09c (2026-07-12) — complete.** Learnings → `.zj/LEARNINGS.md` "Phase 09c": (1) first
  phase since Phase 6 with **zero reviewer majors**, structurally — a read-only derivation phase has
  no read-check-write, so the recurring 7/9a/9b concurrency-major class has no home (triage: report
  phases are low-risk on the concurrency axis, spend review budget on sign-convention + derivation
  correctness); (2) a subledger↔control tie-out holds only if both sides age on the **same date
  basis** — D-P9c-1 unified it at write time (`entry_date=bill_date`), then assert Decimal-exact;
  (3) `in_balance == True` on the balance sheet is **tautological** (identity holds by construction)
  — assert the *composition* (exactly one 3130 row, amount == P&L net income), not the identity.
  Deferrals homed: balance-sheet fiscal-close-gated 3130 double-count + net-income fiscal-year
  bounding → BACKLOG p2; backdated-payment tie-out edge → p3; syerp `service.py` ~3,700 lines +
  MAP.md refresh through 0011 updated in their existing items. Roadmap 9c → `[done]`. Offer:
  `/zj:log phase 09c` files the formal work log.
- **Verify 09c (2026-07-12) — Verdict PASS.** Goal-backward verifier + code reviewer both clean
  (0 blockers, 0 majors). All 6 SCs live-proven: **`verify_reports.py` 17/17** (the exact-Decimal
  2110 subledger↔control tie-out crux `grand_total==control_balance`, incl. partial-payment +
  DRAFT-exclusion divergence guards; TB nets zero; P&L in/out-of-period; BS balances with the
  computed current-year net-income line), **`verify_reports_api.py` 13/13** (200/401/403 × 4
  endpoints + 422 missing-bound); regression `verify_ap` 24 / `verify_gl` 29 / `verify_purchasing`
  19 / `verify_inventory` 16 / `verify_e2e_p8` 19 all exit 0; backend pytest 117 passed/100 skipped;
  FE 81/81, tsc clean; alembic `0011 (head)`. **Fix loop:** added
  `frontend/src/routes/syerp/components/BillCreateDialog.test.tsx` (`0eac5d4`) pinning the bill-date
  field (renders defaulted to today; `bill_date` flows into the POST body) — the one net-new gap.
  Deferred minors (all fiscal-close-gated, out of scope, logged in PLAN `## Noticed` + REVIEW): the
  unconditional computed 3130 line (double-counts only if a future phase posts to 3130), the
  "Current Year Net Income" label being all-time until fiscal-year bounding lands, and the
  backdated-payment (`payment_date < bill_date`) tie-out edge (correct out-of-balance surfacing, not
  a bug). SRD SYERP-12 flipped to **verified (all 9 ACs)** with an AC6/AC7 stamp at `0eac5d4`;
  MAP.md refresh still owed to `/zj:docs` (pre-existing, Phases 8–9c). Artifacts:
  `.zj/phases/09c-ap-aging-financial-statements/{VERIFICATION,REVIEW}.md`.
- **Build 09c (2026-07-12) — 15/15 tasks, on `feature-syerp-financial-reports`** (cut at the 09b HEAD
  `81c2256`; `tag..HEAD` was docs-only so it carries the verified-09b code + planning docs — Deviations).
  Backend: `Bill.bill_date` col (`f6b9635`), migration `0011` NOT NULL + `created_at::date` backfill
  (`cab8531`), bill_date wired through `BillCreate`/`create_bill` + `post_bill` JE `entry_date=bill.bill_date`
  (`729ec00`, the tie-out date-basis), report schemas (`69e4724`), `ap_aging_report`+2110 tie-out
  (`c24c9f6`), `trial_balance` (`7aecf7c`), `profit_loss` (`1d38ddb`), `balance_sheet` w/ computed 3130
  net income (`6f79047`), 4 read-only report endpoints + `syerp:read` (`a9cae54`). Verify:
  **`verify_reports.py` 17/17 PASS ×2** (`9ae4345`) — **tie-out crux `grand_total==control_balance`
  Decimal-exact (1000.000000), incl. partial-payment + draft-exclusion divergence guard; TB nets zero +
  rollup parents absent; P&L in/out-of-period; BS balances with the computed net-income line**;
  **`verify_reports_api.py` PASS ×2** (`fdb0831`) — 200/401/403 across all 4 endpoints + 422 missing-bound,
  read-only ⇒ no mutation audit. Frontend: AP Aging screen (`c6b47d3`, 4 tests), Financial Reports tabbed
  page (`8994f5c`, 3 tests — Button toggle group, no shadcn tabs primitive), routes+nav+optional bill-date
  field on the create dialog (`48c8453`). **Suites:** backend pytest **117 passed / 100 skipped** (D-P7-4,
  unchanged); regression `verify_ap` 23 / `verify_gl` 28 / `verify_purchasing` 18 / `verify_inventory` 15 /
  `verify_e2e_p8` 18 all exit 0 unchanged; frontend **79/79** (24 files). Lint gates still non-functional
  (BACKLOG p1). **Deviations** (PLAN `## Deviations`): branch cut at HEAD not the tag (docs-only delta);
  T3 router call-site threaded `bill_date`; T2/T3/T15 commit subjects trimmed to the ≤72-char guard; T10
  used expense-line bills (Dr ASSET 1150 / Cr 2110) not the PO→receive path and isolates P&L accounts —
  tie-out still real via `post_bill`. **Noticed** (PLAN `## Noticed`): stale `BillRead` FSM docstring
  (`partially_paid`); `balance_sheet` appends the computed 3130 line unconditionally (double-counts IF a
  future phase posts closing entries into 3130); exotic backdated-payment (payment_date<bill_date) tie-out
  edge. **Owner note:** `docs/tasks/{branch}.md` not created for this branch — ZJ PLAN.md is the checklist.
  Original plan crux/patterns recap: coalesce-each-side, `entry_date` filter via the `get_account_register`
  join, HTTP-verify-from-the-start, `service.py` kept cohesive (split deferred to Phase 10).
- **Retro 09b (2026-07-12) — complete.** Learnings → `.zj/LEARNINGS.md` "Phase 09b": (1) sequential
  verify is structurally blind to read-then-write races (reviewer caught the major a 4th time) → row
  lock/constraint **plus** an `asyncio.gather` two-request scenario for any invariant guard; (2) a
  read-check-write race is deferrable only if its breach self-heals — 9b's double-bill/overpay
  corrupts a ledger invariant permanently, so major even single-shop; (3) clearing-account invariant
  proves as a pre/post derived-balance equality; (4) HTTP-verify-from-the-start (09a rule) is now
  settled. Deferrals homed: 2 minor AP correctness edge-cases → BACKLOG p2, stale AP FE types → p3,
  FOR UPDATE template cross-referenced into the inventory-ledger race item. Roadmap 9b marked
  `[done]`; ROADMAP/BACKLOG/LEARNINGS updated. Offer: `/zj:log phase 09b` files the formal work log.
- **Verify 09b (2026-07-12) — Verdict PASS + tagged `zj/good-09b-ap-bills-match-payments`.** Goal-backward + code
  review on `feature-syerp-ap-bills`. All six SCs proven live: `test_ap.py` 14, **`verify_ap.py`
  24/24** (GR/IR-clears-to-zero crux Decimal-exact: 2150 −550 pre-receipt → −550 post-bill; + two
  concurrency race scenarios), **`verify_ap_api.py`** (audit + 403/401/200 RBAC over live HTTP);
  regression `verify_gl` 28 / `verify_purchasing` 18 / `verify_inventory` 15 / `verify_e2e_p8` 18
  all exit 0; FE 72/72. **Fix-loop closed one MAJOR (`380c73b`):** `create_bill`/`record_payment`
  guarded double-bill/overpayment with a read-then-write and no row lock → two concurrent requests
  for the same PO line (or bill) could both commit (2150 never clears / AP negative). Now each
  contended PO-line/bill row is `SELECT … FOR UPDATE`-locked up-front in sorted id order
  (deadlock-safe); pinned by verify scenarios (j)/(k). Two MINOR edge-cases logged to PLAN
  `## Noticed` (fractional multi-lot GR/IR sub-micro residue; zero-qty matched line → unpostable
  draft). Artifacts: `.zj/phases/09b-ap-bills-match-payments/{VERIFICATION,REVIEW}.md`.
- **Prior next action (done):** `/zj:verify 09b` — verified AP bills / PO-match / payments.
  **All 16 PLAN tasks ticked, atomic commits.** Backend: T1 helpers `c1b431b`, T2 models `1697973`,
  T3 migration 0010 `b91ed73`, T4 seed 1111 `5502445`, T5 create-bill `52d9a83` (+dup-guard `13ca4cd`),
  T6 post_bill `3b8eb33`, T7 record_payment `be0a774`, T8 schemas `ff39967`, T9 bill router `7ef302b`,
  T10 payment router `e7bb9b2` (+list_payments `99ef164`). Verify: T11 `verify_ap.py` `e2cd5f2`
  (**22/22 PASS**, the GR/IR crux clears to zero Decimal-exact: 2150 pre-receipt −350 → post-bill −350),
  T12 `verify_ap_api.py` `6aa86af` (**24/24 PASS**, bill.created/bill.posted/payment.recorded audit +
  full 403/401/200 RBAC). T13 regression: verify_gl/purchasing/inventory/e2e_p8 all exit 0 unchanged.
  Frontend: T14 Bills list `4e25ab2`, T15 BillDetail+Pay `bb57463`, T16 routes+nav `72cfd82`.
  Suites green: **backend pytest 117 passed / 100 skipped (D-P7-4) / 0 failed**, **frontend 72/72**.
  **Deviations** (in PLAN.md `## Deviations`): T5 in-payload duplicate `po_line_id` guard added
  (protects the crux); T10 `list_payments` read added post-hoc (Task-7 scope gap); T2 timestamps are
  Python-side defaults (no `server_default`) so 0010 matches the models. **Noticed** (PLAN `## Noticed`):
  stale `Bills.tsx BillLineRead` type, a misleading `partially_paid` schema comment (FSM is
  draft→posted→paid; partial payment stays `posted`), and the pre-existing `alembic check` drift.
- **Prior next action (done):** `/zj:build 09b` — built 2026-07-11 off the 09a tip.
- **Last update:** 2026-07-11
- **Next action:** `/zj:build 09b` — build AP bills / PO-receipt match / payments (SYERP-12 AC4/AC5/AC8/AC9).
  **Plan ready:** `.zj/phases/09b-ap-bills-match-payments/PLAN.md` — 16 tasks, layered
  models→migration→seed→3 service→schemas→2 router→2 verify scripts→regression→3 frontend.
  **First action of the build: cut a fresh branch `feature-syerp-ap-bills` off the current
  `feature-syerp-gl-posting-engine` HEAD (the verified 09a tip, tag `zj/good-09a-gl-posting-engine`)**
  — D-P9b-8. Owner-resolved decisions at plan (D-P9b-1..8): receipt-driven bill creation matched at
  PO-line grain (D-P9b-1); **exact match required** so Dr GR/IR 2150 == Cr AP 2110 and GR/IR clears
  to zero — variance rejected 4xx, no PPV account (D-P9b-2); non-PO expense lines with user-chosen
  EXPENSE/ASSET account (D-P9b-3); payments credit a **selectable cash/bank account** defaulting to
  1110, seed new **1111 Bank – Checking** (D-P9b-4); BILL-#### numbering + Draft→Posted→Paid
  `BILL_TRANSITIONS` FSM + auto-Paid + overpayment 4xx (D-P9b-5); Payment header + PaymentAllocation
  (1 payment → N bills, D-P9b-6); `/syerp/ap/…` paths (D-P9b-7). Crux baked into `verify_ap.py` (e):
  GR/IR balance returns to its pre-receipt value after receive→post_bill. SC6 (audit+RBAC) proven by
  a **first-class HTTP verify** `verify_ap_api.py` (the Phase-09a learning: router behavior needs an
  HTTP-level script, planned from the start).
- **Prior next action (done):** `/zj:plan 09b` — planned 2026-07-11.
  **Phase 9a is verified, tagged `zj/good-09a-gl-posting-engine`, and retro'd.** It delivered
  SYERP-12 **AC1/AC2/AC3 + AC8/AC9**: double-entry JournalEntry/JournalLine (append-only, reversal
  via self-FK), derived balances + account register, the manual general-journal UI, and the crux —
  PO `receive_line` atomically posts a balanced **Dr 1130 / Cr 2150** JE at receipt cost (seeded
  GR/IR 2150). Branch `feature-syerp-gl-posting-engine` off `master` (D-P9a-2).
  - **Retro (2026-07-11) — learnings kept** (`.zj/LEARNINGS.md` "Phase 09a"): (1) service-level
    verify scripts can't prove router behavior (audit/RBAC) — `verify_gl_api.py` over live HTTP was
    needed; **plan an HTTP-level verify from the start in 9b/9c**; (2) a new atomic side-effect
    narrowed a legal input domain (the zero-cost receipt regression); (3) SQL `SUM` NULL-propagates
    on single-sided derived balances → **coalesce each side** (AP-control/cash in 9b/9c derive the
    same way); (4) the review again caught the majors the green live-verify missed. Deferrals homed
    to BACKLOG: alembic autogenerate drift (7 unnamed constraints + `server_default` now()), FE
    reverse-action Vitest, receipt `entry_date` UTC, MAP fuller refresh.
  - **Verify fix-loop (2026-07-11):** two majors fixed — **M1** a zero-cost PO receipt (`unit_cost=0`)
    self-rejected the all-zero JE and rolled back the whole receipt (Phase-8 regression) → now skips
    the GL post; **M2** no double-reversal guard let the derived control account diverge from
    inventory → now 409. Plus **m5** entry-targeted receipt audit and **m7** docs. The two mandated
    criteria-become-tests landed: `verify_gl.py` grew the atomicity-rollback / zero-cost / double-
    reversal scenarios (**28/28**) and a **new `verify_gl_api.py`** pins the audit rows + 403/401
    RBAC over live HTTP (**9/9**). Phase-8 regression unchanged, `test_gl_journal.py` 13, FE 64/64.
  - **Phase 9 split (D-P9a-1..5):** 9a done → `/zj:plan 09b` (AP bills/match/payments, AC4/AC5) →
    `/zj:plan 09c` (AP aging + statements, AC6/AC7). AR stays out (SYERP-13 → CRUMB, D-P9-4).
- **Phase-9 spec (2026-07-11):** owner chose full subledger→GL auto-posting (D-P9-1) over
  document-only aging; AP = vendor bill matched to PO receipts + payments (D-P9-2); GR/IR clearing
  posting model (D-P9-3, CoA account codes to confirm at plan time); AR deferred to CRUMB (D-P9-4,
  new SYERP-13); v2.0 DoD unchanged, MOUSSE stays required (D-P9-5).
- **Ship record (2026-07-11):** **PR #1 MERGED** via local fast-forward
  (`feature-syerp-inventory-purchasing` → `master`, `f4e2bd3..a5ad44b`). Master now carries the
  full re-platform (Phases 1–8); `v1.0` tag (`4b6fee4`) pushed and confirmed an ancestor of
  `master`. FF chosen over GitHub's rebase-button so commit SHAs — and thus the tag — were
  preserved. The 4-year-old `master`-behind problem (standing debt #4) is **resolved**.
- **Milestone:** v1.0 — Foundation + PLUM — **CLOSED + tagged `v1.0` 2026-07-11**.
  v2.0 Operations in progress (Phase 8 done + verified + retro'd).
- **Phase:** none active for v1.0 (Phase 7 archived to `.zj/history/v1.0/phases/`).
  Phase 8 (`.zj/phases/08-syerp-inventory-purchasing/`) belongs to v2.0 and stays active.
- **Branch:** `feature-syerp-inventory-purchasing` — carries Phases 7 + 8 + the milestone close.

## v1.0 milestone close — status

**Audit:** `.zj/MILESTONE-v1.0-AUDIT.md`, verdict **GAPS FOUND**, driven live against the running
stack. All four definition-of-done clauses (deploy / log in / vendors+customers / multi-level BOM
+ cost roll-up) proven at the API layer.

**Gaps triaged with the owner:**
| Gap | Severity | Disposition |
|---|---|---|
| **G1** Where-Used labelled *every* parent "Direct parent" (PLUM-06) | major, unprotected | **Fixed** `63ea954` — backend now emits `via_part_number`; UI keys off `indirect`. Guards: `PartDetail.test.tsx` (5), `test_bom.py`. Proven live 14/14. |
| **G2** Excel export 500 — `openpyxl` absent from the API image | blocker for UAT check 7 | **Fixed** by rebuilding `compose_api`. `/plum/export/excel` → 200, valid `.xlsx`. No code change. |
| **G3** live-DB pytest harness skips 98 tests | systemic | **Deferred** (owner-approved) — BACKLOG p1, D-P7-4, D-M1-2. Not PLUM-only: auth 38, plum 34, syerp 17, core 7. |

**Records produced:**
- `CHANGELOG.md` — generated from commits, 98 `feat:`/`fix:` entries grouped by phase (new file;
  never hand-edit).
- `.zj/logs/milestone-v1.0.md` — work log: ≈47 h over 30 inferred sessions, 224 v1.0-era commits.
- `.zj/LEARNINGS.md` — "Milestone v1.0" roll-up.
- `.zj/DECISIONS.md` — regenerated `## Index` (44 entries) + **D-M1-1** (tag placement),
  **D-M1-2** (G1/G2 fixed, G3 deferred).
- `zj doctor`: **18 errors → 0** (19 warnings remain, all BACKLOG tag-format).

## What is left before the tag

**Human UAT round 1 ran 2026-07-11** (owner). Passed checks 3, 5, 6, 12. Surfaced three UI
defects — **D1** flat-BOM cost footer (280 vs 110), **D2** AVL "Add Vendor" 500 on a duplicate,
**D3** dead import file picker — all now **fixed** (`a88431c`, D-M1-3), tested, and D2 proven live.
**Round 2 owed:** re-run checks **2, 4/9, 7, 10, 11**. These plus the already-passed 1, 3, 5, 6, 8,
12 close all twelve. Residue is genuine visual confirmation: red styling (6 ✓), toast absence
(9, 10), badges/footer (2, 4), visible no-refresh (11).

Stack must be up: `podman-compose -f compose/compose.yml -f compose/compose.dev.yml up -d`
(rebuild `api` if the stack is recreated, or G2 returns). `alembic current` == `0008 (head)`.

Once the UAT passes: `git tag -a v1.0 -m "Foundation + PLUM"` at HEAD (per **D-M1-1**, that tree
also contains Phase 8 / v2.0 work — this is recorded, not accidental).

## Standing debt (carried into v2.0)

1. **Live-DB pytest harness never runs** — 98 skips across every module (BACKLOG p1, D-P7-4).
   Regression protection currently rests on `backend/scripts/verify_*.py` (66 assertions) and the
   Vitest suite, both of which do run.
2. **Both lint gates non-functional** (BACKLOG p1) — ESLint 10 is flat-config-only but the repo
   ships `.eslintrc.cjs` with a removed `--ext` flag and no `@typescript-eslint` parser deps;
   `ruff` is pinned in `requirements-dev.txt` but not installed in `backend/.venv`.
3. **No CI** (BACKLOG p1) — the `SyerpPartner` bug shipped through four plans because live-DB
   tests never ran.
4. **`master` is 263 commits behind** at `f4e2bd3` (2025-12-20) and contains no `backend/`,
   `frontend/`, or `.zj/`. The entire re-platform is unmerged; the merge story is unresolved
   (`/zj:ship`, D-P7-3 / D-P8-11).

## After the tag

1. `/zj:ship` — resolve the `master` merge story for the branch carrying Phases 7 + 8.
2. `/zj:spec` — refine the v2.0 definition of done before planning Phase 9.
3. `/zj:plan 09` — SYERP AP/AR & reporting (SYERP-12).

## Adoption note

Adopted from GSD on 2026-07-04. Prior planning system archived at `archive/planning-gsd/`
(phases 01–07, REQUIREMENTS, ROADMAP, STATE, v1.0-MILESTONE-AUDIT, codebase snapshots) and
`archive/planning-docs/` (program ROADMAP.md, decisions.md). `.zj/` is self-contained — the
archive is history, not a dependency.
