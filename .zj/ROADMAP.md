# ROADMAP — BizNiceSweets
Updated: 2026-07-16 (**v3.0 "Customer & logistics" spec'd** — DoD sharpened into 3 clauses, CRUMB-01/GELATO-01/SYERP-13 expanded to full ACs, Phase 11→12→13 mapping proposed; D-V3-1..9. Next: `/zj:plan 11`.)
Prior: 2026-07-16 (**Milestone v2.0 "Operations" CLOSED + tagged `v2.0`** — DoD audited goal-backward vs the running stack (`.zj/MILESTONE-v2.0-AUDIT.md`: 13/13 verify scripts, TB nets zero, subledgers tie; 1 minor gap G1 fixed at close `2578ca5`). Phases 8/9a/9b/9c/10 archived to `.zj/history/v2.0/`. **Next milestone = v3.0 Customer & logistics** (CRUMB + GELATO + AR, D-M2-4). Next action: `/zj:ship` (2-milestone master-merge debt) then `/zj:spec` for v3.0.)
Prior: 2026-07-16 (Phase 10 done + retro'd — MOUSSE WO core verified/tagged; v2.0 code-complete)
Prior: 2026-07-13 (Phase 10 **planned** — MOUSSE materials-only WO core, 20 tasks, D-P10-1..9; next = the D-P10-4 syerp split chore, then `/zj:build 10`)
Prior: 2026-07-12 (Phase 9c **done + retro'd** → next `/zj:plan 10` (MOUSSE); learnings in LEARNINGS.md "Phase 09c")
Prior: 2026-07-12 (Phase 9c verified + tagged `zj/good-09c-ap-aging-financial-statements` → next `/zj:retro 09c`)
Prior: 2026-07-12 (Phase 9b done + retro'd → next `/zj:plan 09c`; learnings in LEARNINGS.md "Phase 09b")
Prior: 2026-07-11 (Phase-9 spec — SYERP-12 = GL+AP+reporting, AR→CRUMB, v2.0 DoD confirmed; D-P9-1..5)
Prior: 2026-07-09 (v1.0 milestone close; history reconstructed at ZJ adoption from git + GSD artifacts archived at `archive/planning-gsd/`)

## v1.0 — Foundation + PLUM  [done]

**Closed 2026-07-09.** Definition of done — *"Can deploy it, log in, manage vendors/customers,
and design parts with multi-level BOMs and cost roll-up"* — audited goal-backward against the
running stack (`.zj/MILESTONE-v1.0-AUDIT.md`). All four clauses proven live.

- **Audit found what seven phase verifications missed:** G1 (Where-Used labelled every parent
  "Direct parent" — a backend/frontend contract drift, fixed `63ea954`), G2 (Excel export 500 on
  a stale API image, fixed by rebuild), G3 (live-DB pytest harness skips 98 tests — deferred,
  BACKLOG p1 / D-P7-4).
- **Evidence:** 66 live-DB assertions across five `backend/scripts/verify_*.py`, 0 failures;
  backend pytest 90 passed / 98 skipped; frontend Vitest 54 passed; `tsc -b` clean;
  `zj doctor` 0 errors.
- **Records:** `CHANGELOG.md` (98 entries), `.zj/logs/milestone-v1.0.md` (≈47 h over 30 sessions),
  `.zj/LEARNINGS.md` "Milestone v1.0", `.zj/DECISIONS.md` index (44 entries).
- **Tag:** `v1.0` applied 2026-07-11 at `4b6fee4` — the tree also contains Phase 8 (v2.0) work,
  see **D-M1-1**. No commit in history is a clean v1.0 tree, because Phase 8 was built on the
  unclosed Phase-7 branch (D-P8-11).
- **Human UAT:** run in two rounds (`.zj/UAT-v1.0.md`). Round 1 (2026-07-11) passed 6 checks and
  found three UI defects (D1/D2/D3), all fixed in `a88431c` (D-M1-3) with tests + live proof.

### Phase 0: Prototypes & program planning  [done — adopted 2026-07-04]
- **Goal:** Prove the domain logic and plan the re-platform.
- **Delivers:** PLUM v54 prototype (`plum/app/plm_v54.html`, ~31k lines) and FLAN v24
  prototype (`flan/app/prj-mgmt-v24.html`, ~11.5k lines) — both now frozen reference; the
  7-suite architecture decisions, program roadmap, and per-suite docs (`docs/features/`).
- **Evidence:** git era 2025-12 (16 commits: analysis report, suite restructure, decisions,
  roadmap, PLUM/FLAN doc sets); archived `docs/ROADMAP.md` + `docs/decisions.md`.
- **Notes:** reconstructed from git history at adoption.

### Phase 1: Project Scaffolding & Deployment  [done — verified]
- **Goal:** Target stack scaffolded and deployable in one command.
- **Delivers:** CORE-01, CORE-09 — FastAPI + SQLAlchemy async + Alembic backend, React 19 +
  Vite + Tailwind 4 frontend, module registry, Podman Compose (prod + dev overlay),
  auto-migrating entrypoint.
- **Evidence:** `compose/compose.yml`, `backend/entrypoint.sh`, `backend/app/core/registry.py`;
  operator-live checkpoint 23/23 (archived 01-VERIFICATION.md).

### Phase 2: Authentication & Users  [done — verified]
- **Goal:** Real multi-user access control.
- **Delivers:** CORE-02..05 — JWT two-token auth (PyJWT + Argon2), refresh rotation with
  httpOnly cookie + single-flight axios interceptor, admin user management, RBAC
  (User↔Role↔Permission, `module:action` codes), login audit events.
- **Evidence:** `backend/app/modules/auth/`, `backend/tests/auth/` (8 test files),
  `frontend/src/auth/`; human-verified 2026-06-25.

### Phase 3: App Shell & Settings  [done — verified]
- **Goal:** The modular-suite chrome: navigation, settings, module toggles.
- **Delivers:** CORE-06..08 — AppShell (nav = enabled modules ∩ permissions), admin
  Settings + Modules screens, live toggle propagation, always-on SYERP guard, sonner toasts.
- **Evidence:** `frontend/src/components/AppShell.tsx`, `frontend/src/routes/admin/`,
  `backend/app/core/{modules_router,settings_router}.py`; human-verify approved.

### Phase 4: SYERP Core Hub  [done — verified]
- **Goal:** The hub every module FKs into: partners + GL skeleton.
- **Delivers:** SYERP-01..05 — Partner model (vendor/customer flags), Vendors/Customers
  screens with search + archive-via-PATCH, seeded chart of accounts with read-only screen,
  SYERP sub-nav; 4 UAT fixes (Tailwind v4 tokens, country validation, catch-all route, tab strip).
- **Evidence:** `backend/app/modules/syerp/`, `frontend/src/routes/syerp/`,
  `backend/tests/syerp/test_gl.py`; human-verify approved after UAT.

### Phase 5: PLUM Parts & Revisions  [done — verified]
- **Goal:** First real PLUM capability: parts with revision workflow.
- **Delivers:** PLUM-01..03 — parts CRUD/search, revision FSM with DB-level one-Released
  invariant, SemVer/ASME labels, tag join table, audit events, PartsList/PartDetail UI.
- **Evidence:** `backend/app/modules/plum/`, migration 0005, `backend/tests/plum/test_parts.py`
  + `test_revisions.py`, `frontend/src/routes/plum/`; human UAT 10/10.

### Phase 6: PLUM BOM, Costing & Integration  [done — code-complete, verification pending]
- **Goal:** Multi-level product structures, cost analysis, vendor links, import/export.
- **Delivers:** PLUM-04..10 (all partial pending Phase 7) — BOM tree/flat/where-used with
  cycle detection, AVL + price breaks, Decimal effective-cost chain + margin + release
  snapshot, JSON/Excel import-export with preview/commit, PartDetail four cards + ImportExport page.
- **Evidence:** migration 0006, `service.py`/`router.py` (~4k lines combined),
  `backend/tests/plum/{test_bom,test_avl,test_costing,test_import_export}.py`,
  `frontend/src/routes/plum/components/`.
- **Notes:** the only unverified phase — human-verify checkpoint never ran; milestone audit
  (2026-07-01) found the `SyerpPartner` blocker and the part-number bug → Phase 7.

### Phase 7: Close v1.0 gaps  [done]
- **Goal:** PLUM AVL and vendor import/export work end-to-end without runtime errors,
  auto part-numbering is numerically correct, the Parts List refreshes after import, and
  Phase 6's flows are human-verified with traceability reconciled.
- **Delivers:** PLUM-07, PLUM-10 (fix); PLUM-01 defect (fix); PLUM-04..06, 08, 09 (verify → implemented).
- **Verified 2026-07-09** (`/zj:verify 07`, verified code tip `8975eeb`; tag
  `zj/good-07-close-v1-0-gaps` at the artifacts commit `ac56fa1`):
  SC1/SC2/SC3/SC5/SC6 proven empirically; SC4 met as amended by D-P7-4 (standalone live-Postgres
  proof substitutes for the broken pytest harness) and D-P7-5 (human-UAT owned by `/zj:milestone`).
  Artifacts: `VERIFICATION.md`, `REVIEW.md`.
  - **One blocker found and fixed in the verify fix loop** (`7562a02`): the phase's own SC2 fix cast
    the part-number suffix to int4, so a legal `P9999999999` row made **every** auto-numbered
    `create_part` return 500 permanently — a user-triggerable, persistent DoS. Cast is now `Numeric`.
  - **Criteria became executable tests** (each proven red/green): `scripts/verify_plum_vendor_paths.py`
    (SC1, 8 live assertions across all four alias sites), `scripts/verify_part_numbering.py` (SC2 SQL
    half, 7 live assertions incl. the overflow guard), `tests/plum/test_part_number.py` (SC2 pure
    half, runs in the ordinary pytest suite), `ImportExport.test.tsx` (SC3, positive + negative path).
  - **Still owed:** the 12-check human-UAT (`.zj/UAT-v1.0.md`, 2/12 done) at `/zj:milestone`, and the
    PLUM pytest-harness repair (BACKLOG p1) — the latter no longer leaves any criterion unprotected.
- **Retro 2026-07-09** (`/zj:retro 07`): learnings in `.zj/LEARNINGS.md` "Phase 07" — the review, not
  the live verify, caught the blocker (domain reasoning vs. happy-path drive); a fix can be worse than
  its bug; "verified live" ≠ "protected". Deferrals homed: lint gates + stale API image → BACKLOG p1;
  auto-number race → BACKLOG p2; `part_number` format constraint + dev-DB artifact → D-P7-6 / won't-fix.
- **Scope (adopted as-is from GSD Phase 7, owner decision 2026-07-04):**
  1. Backend `service.py`: alias/rename `SyerpPartner` → `Partner` at 4 sites + numeric-safe
     `generate_part_number` + live-DB regression coverage.
  2. Frontend: invalidate `['plum','parts']` on import-commit success.
  3. Consolidated human-verify: 7 PLUM flows + 4 regression checks.
  4. Reconcile SRD statuses + `docs/features/requirements-progress.md` (currently falsely
     marks PLUM-07/10 Complete).
  Source plans archived at `archive/planning-gsd/phases/07-*/` (provenance; `/zj:plan 7`
  produces the ZJ PLAN.md).
- **Closes milestone v1.0** (run `/zj:milestone` after verification).

---

## v2.0 — Operations (SYERP extended + MOUSSE)  [done — closed 2026-07-16, tag `v2.0`]

**Closed 2026-07-16.** Definition of done — *"Can track inventory, raise purchase orders, keep
real books (double-entry GL with AP + financial statements), and execute work orders that consume
PLUM BOMs and inventory"* — audited goal-backward against the running stack
(`.zj/MILESTONE-v2.0-AUDIT.md`). All four clauses proven end-to-end, backend↔frontend↔DB.

- **Audit verdict:** clean but for one minor gap — **G1** (Profit & Loss report fired with an empty
  `from` date on first tab open → backend 422 → load error). Fixed at close (`2578ca5`, default
  `from` to year-start + a pinning Vitest), mirroring the v1.0 fix-at-close of G1/G2 (D-M2-1a).
- **Evidence:** 13/13 live `verify_*.py` scripts exit 0 (~200 assertions); whole-DB trial balance
  nets 0.000000; control accounts tie to their subledgers; `npm run build` clean; 90/90 Vitest;
  `tsc -b` clean; alembic head 0012.
- **Records:** `CHANGELOG.md` (v2.0 released — Phases 8/9a/9b/9c/10), `.zj/logs/milestone-v2.0.md`
  (≈12.7 h over 8 sessions, 104 post-v1.0 commits), `.zj/LEARNINGS.md` "Milestone v2.0",
  `.zj/DECISIONS.md` D-M2-1..4 + regenerated index, `.zj/MILESTONE-v2.0-AUDIT.md`.
- **Tag:** `v2.0` at the `feature-mousse-work-orders` HEAD. As with v1.0 (D-M1-1), that tree is the
  working tip of an **unmerged** branch — master is 98 commits behind and carries none of Phases
  9–10. The master-merge is the standing `/zj:ship` debt (D-M2-3).
- **Deferred at close (owner-approved):** the human click-through UAT (`.zj/UAT-v2.0.md` + owed
  v1.0 round-2) → BACKLOG p1 pre-release gate (D-M2-2); BACKLOG p1 infra debt (CI, live-DB pytest
  harness, both lint gates) carried into v3.0 again — correctness rested on `verify_*` + Vitest.

Phase 8 shipped inside the v1.0 tag tree (built pre-close, D-P8-11); Phases 9–10 built after.
Phase directories archived to `.zj/history/v2.0/phases/`.

### Phase 8: SYERP Extended — inventory & purchasing  [done]
- **Goal:** Inventory items (optional PLUM link) with per-location on-hand, immutable
  transaction history, and moving-average valuation; a Draft→Approve→Receive purchase-order
  workflow whose receipts feed inventory. No AP (SYERP-12), no warehouse bins (GELATO-01).
- **Delivers:** SYERP-10, SYERP-11 — built + verified live (Phase 8, branch
  `feature-syerp-inventory-purchasing`, `b5c5c31~1..554c3fe`). All 16 ACs proven against live
  Postgres (`verify_inventory` 15/15, `verify_purchasing` 18/18, `verify_e2e_p8` 18/18 fresh-DB);
  FK-degradation defect fixed in verify (`554c3fe`). Deferred (BACKLOG p1, D-P7-4): port the
  verify-script assertions into runnable integration tests once the async pytest harness is
  repaired; UI-flow human UAT at the v2.0 milestone (`.zj/UAT-v2.0.md`, D-P7-5).
- **Depends on:** SYERP hub (Partner, done) + PLUM parts (done). MOUSSE (Phase 10) and
  GELATO both build on this inventory ledger.
- **Evidence:** `.zj/phases/08-syerp-inventory-purchasing/{PLAN,VERIFICATION,REVIEW}.md`;
  tag `zj/good-08-syerp-inventory-purchasing`.

### Phase 9: SYERP Extended — GL, AP & financial reporting  [pending — spec'd 2026-07-11; SPLIT into 9a/9b/9c at plan, 2026-07-11]
- **Goal:** Real books: a double-entry GL posting engine, an accounts-payable workflow (vendor
  bills matched to PO receipts, with payments), and financial reporting — with inventory receipts
  and AP documents auto-posting balanced journal entries so AP aging and the Trial Balance / P&L /
  Balance Sheet derive from posted GL activity.
- **Delivers:** SYERP-12 (9 acceptance criteria — see SRD). **AR is not here** — SYERP-13 (AR)
  is deferred to the CRUMB milestone (D-P9-4).
- **Scope decisions:** D-P9-1 (full subledger auto-post, chosen over document-only aging),
  D-P9-2 (AP = bill↔PO-receipt match + payments), D-P9-3 (GR/IR clearing posting model — codes
  now confirmed, see 9a), D-P9-4 (AR → CRUMB).
- **Split confirmed at `/zj:plan 09` (D-P9a-1..5):** broken into three ZJ sub-phases rather than one
  mega-phase, each planned/built/verified independently:

#### Phase 9a: GL posting engine + receipt auto-post  [done — verified 2026-07-11, tag `zj/good-09a-gl-posting-engine`, retro'd]
- **Goal:** A double-entry GL posting engine — balanced, immutable, reversible journal entries with
  derived account balances and an account register — plus a manual general-journal UI, and PO
  receipts auto-post a balanced GR/IR journal entry atomically with the stock ledger.
- **Delivers:** SYERP-12 **AC1** (journal & posting engine), **AC2** (derived balances + register),
  **AC3** (receipt → Dr Inventory 1130 / Cr GR/IR 2150 auto-post), plus AC8/AC9 for that surface.
- **Key decisions:** GR/IR = new seeded **2150** LIABILITY under 2100 (Inventory 1130 / AP 2110 /
  Cash 1110 already exist); JEs append-only immutable (D-P9a-1); manual JE UI in scope; branch off
  **master** (D-P9a-2 — the D-P8-11 master-behind trap is resolved). Extends Phase-8 `receive_line`
  with an atomic JE side-effect → the Phase-8 verify scripts are a regression gate.
- **Plan:** `.zj/phases/09a-gl-posting-engine/PLAN.md` — 13 tasks, all built + verified.
- **Verified:** `/zj:verify 09a` (2026-07-11) — verdict PASS after a fix loop closing 2 majors
  (M1 zero-cost receipt regression, M2 double-reversal guard) + the 2 mandated criteria-become-tests
  (SC3 atomicity rollback, SC5 audit+RBAC). Live proof: `verify_gl.py` 28/28, new `verify_gl_api.py`
  9/9, Phase-8 regression unchanged, `test_gl_journal.py` 13, FE 64/64. Minors logged in PLAN `## Noticed`.
- **Retro 2026-07-11** (`/zj:retro 09a`): learnings in `.zj/LEARNINGS.md` "Phase 09a" — service-level
  verify scripts can't prove router behavior (audit/RBAC) → HTTP-level verify needed, plan it from the
  start in 9b/9c; a new atomic side-effect narrowed a legal input domain (zero-cost receipt regression);
  SQL `SUM` NULL-propagates on single-sided derived balances → coalesce each side; review again caught
  the majors the green live-verify missed. Deferrals homed to BACKLOG (alembic drift, reverse-UI Vitest,
  entry_date UTC, MAP refresh). **Next: `/zj:plan 09b`.**

#### Phase 9b: AP bills, PO match & payments  [done — verified 2026-07-12, tag `zj/good-09b-ap-bills-match-payments`, retro'd]
- **Delivers:** SYERP-12 **AC4** (vendor bill + PO-receipt match, Dr GR/IR-or-Expense / Cr AP,
  Draft→Posted→Paid FSM), **AC5** (payments Dr AP / Cr Cash-or-Bank, partial, overpayment 4xx),
  plus AC8/AC9 (audit + RBAC) for that surface.
- **Verified (2026-07-12):** goal-backward + code review on branch `feature-syerp-ap-bills`.
  All six SCs proven live: `test_ap.py` 14, **`verify_ap.py` 24/24** (incl. the GR/IR-clears-to-zero
  crux Decimal-exact and two concurrency race scenarios), **`verify_ap_api.py`** (audit +
  403/401/200 RBAC over live HTTP); regression `verify_gl` 28 / `verify_purchasing` 18 /
  `verify_inventory` 15 / `verify_e2e_p8` 18 all exit 0; frontend 72/72. **Verify fix-loop closed
  one major** (`380c73b`): concurrent `create_bill`/`record_payment` could defeat the
  double-bill/overpayment guards under READ COMMITTED — now `SELECT … FOR UPDATE`-serialized and
  pinned by verify scenarios (j)/(k). Two minor edge-cases logged to PLAN `## Noticed` (fractional
  multi-lot GR/IR sub-micro residue; zero-qty matched line → unpostable draft). Artifacts:
  `VERIFICATION.md`, `REVIEW.md`.
- **Plan:** `.zj/phases/09b-ap-bills-match-payments/PLAN.md` — 16 tasks (models→migration→seed→
  3 service→schemas→2 router→`verify_ap.py`+`verify_ap_api.py`→regression→3 frontend), branch
  `feature-syerp-ap-bills` off the 09a tip (D-P9b-8).
- **Decisions resolved at plan (D-P9b-1..8):** receipt-driven bill creation, PO-line-grain match
  (D-P9b-1); **exact match** → GR/IR clears to zero, variance 4xx, no PPV account (D-P9b-2); non-PO
  expense lines, user-chosen account (D-P9b-3); selectable cash/bank account, seed 1111 Bank –
  Checking (D-P9b-4); BILL-#### + Draft→Posted→Paid FSM + auto-Paid + overpayment 4xx (D-P9b-5);
  Payment + PaymentAllocation, 1→N bills (D-P9b-6); `/syerp/ap/…` paths (D-P9b-7). GR/IR-clears-to-
  zero is the accounting crux, asserted in `verify_ap.py`; SC6 audit+RBAC proven by HTTP-level
  `verify_ap_api.py` (Phase-09a learning applied).
- **Retro 2026-07-12** (`/zj:retro 09b`): learnings in `.zj/LEARNINGS.md` "Phase 09b" — (1) a
  sequential verify script is structurally blind to read-then-write races (the reviewer caught the
  major again, 4th time) → any read-check-write guarding a hard invariant needs a row lock/constraint
  **and** an `asyncio.gather` two-concurrent-request verify scenario; (2) a read-check-write race is
  deferrable only if its breach self-heals — a double-billed receipt / overpaid bill corrupts a
  ledger invariant permanently, so it's a major even single-shop (unlike the deferred inventory-ledger
  drift); (3) the clearing-account invariant proves best as a pre/post derived-balance *equality*
  (snapshot 2150, mutate, assert it returns); (4) planning the HTTP-level verify from the start (09a
  rule) removed the router-gap before it opened — now settled practice. Deferrals homed: 2 minor AP
  correctness edge-cases (GR/IR sub-micro residue, zero-qty matched line) → BACKLOG p2; stale AP FE
  types + `partially_paid` comment → BACKLOG p3; FOR UPDATE template cross-referenced into the
  inventory-ledger race item. **Next: `/zj:plan 09c`.**

#### Phase 9c: AP aging + financial statements  [done — verified + retro'd 2026-07-12, tag `zj/good-09c-ap-aging-financial-statements`]
- **Delivers:** SYERP-12 **AC6** (AP aging buckets, ties to AP control balance), **AC7** (Trial
  Balance, P&L, Balance Sheet from posted GL activity).
- **Plan:** `.zj/phases/09c-ap-aging-financial-statements/PLAN.md` — 15 tasks (models→migration→
  schemas→4 service reports→router→2 verify scripts→regression→3 frontend), all built + verified.
- **Verified:** `/zj:verify 09c` (2026-07-12) — verdict **PASS**, no blockers/majors from either
  the goal-backward verifier or the code reviewer. All 6 SCs live-proven: `verify_reports.py` 17/17
  (the exact-Decimal 2110 subledger↔control tie-out crux, incl. partial-payment + DRAFT-exclusion
  divergence guards; TB nets zero; P&L in/out-of-period; BS balances with the computed net-income
  line), `verify_reports_api.py` 13/13 (200/401/403 × 4 endpoints + 422); regression verify_ap 24 /
  verify_gl 29 / verify_purchasing 19 / verify_inventory 16 / verify_e2e_p8 19 all exit 0; FE 81/81
  (fix loop added `BillCreateDialog.test.tsx` pinning the bill-date field, `0eac5d4`). Deferred
  minors logged (unconditional 3130 line, all-time net-income label, backdated-payment edge — all
  gated on fiscal-close, out of scope). Artifacts: `.zj/phases/09c-.../{VERIFICATION,REVIEW}.md`.
- **Retro 2026-07-12** (`/zj:retro 09c`): learnings in `.zj/LEARNINGS.md` "Phase 09c" — (1) first
  phase since Phase 6 with zero reviewer majors, structurally: a read-only derivation phase has no
  read-check-write, so the recurring 7/9a/9b concurrency-major class has no home (triage signal:
  report phases are low-risk on the concurrency axis — spend review budget on sign-convention +
  derivation correctness); (2) a subledger↔control tie-out holds only if both sides age on the same
  date basis — D-P9c-1 unified it at write time (`entry_date=bill_date`), then assert Decimal-exact;
  (3) `in_balance == True` on the balance sheet is tautological (identity holds by construction) —
  assert the *composition* (exactly one 3130 row, its amount == P&L net income), not the identity
  that must be true. Deferrals homed to BACKLOG p2/p3: the fiscal-close-gated 3130 double-count +
  net-income fiscal-year bounding, and the backdated-payment tie-out edge; syerp `service.py` size
  bumped in the split item (~3,700 lines). **Next: `/zj:plan 10` (MOUSSE).**

### Phase 10: MOUSSE — manufacturing execution core (materials-only)  [done — verified + retro'd 2026-07-16]
- **Goal:** Work orders that consume a PLUM BOM and SYERP inventory to produce a finished good,
  with material cost flowing through a **WIP clearing account (1140) that returns to zero** —
  closing the v2.0 DoD clause "execute work orders that consume PLUM BOMs and inventory."
- **Delivers:** MOUSSE-01 (materials-only slice). New `backend/app/modules/mousse/` module.
- **Scope (D-P10-1, owner):** WO header + FSM Draft→Released→In Progress→(On Hold⇄In Progress)→
  Completed (+Cancelled), single-level BOM snapshot at release, **explicit component issue**
  (Dr 1140 / Cr 1130 at moving-avg cost), completion → FG receipt (Dr 1130 / Cr 1140).
  **Deferred to a follow-on MOUSSE phase:** routing/work-centers, labor + overhead costing
  (5120/5130), the shop-floor operator execution view.
- **Key decisions (D-P10-1..9):** actual moving-avg costing, WIP clears to zero, no variance
  account (D-P10-2); explicit issue (D-P10-3); single-level direct BOM, sub-assemblies issued as
  components (D-P10-5, owner-confirmed); reject release if any component has no linked InventoryItem
  (D-P10-7); completion blocked on under-issue unless an audited `override_incomplete`, plus On Hold
  pause/resume (D-P10-9).
- **Plan:** `.zj/phases/10-mousse-work-orders/PLAN.md` — 20 tasks (models→migration 0012→perm
  seed→schemas→service[create/release/issue/complete/hold/resume]→router→register→`verify_mousse.py`
  +`verify_mousse_api.py`→regression→5 frontend). Branch `feature-mousse-work-orders` off tag
  `zj/good-09c-ap-aging-financial-statements` (D-P10-8).
- **Prerequisite chore first (D-P10-4):** split `backend/app/modules/syerp/service.py` (~3,824
  lines, BACKLOG p2) into cohesive submodules behind unchanged public functions + refresh
  `.zj/codebase/MAP.md` (stale at migration 0009; head 0011) on a **separate chore branch**,
  verified green against existing `verify_*` scripts, BEFORE the MOUSSE build — kept out of the
  MOUSSE feature diff.
- **Notes:** the PLUM `service.py` split (~3k lines, BACKLOG p2) is the other half of the same
  monolith-file item; MOUSSE, as a new module, does not extend either file — it imports SYERP's
  inventory/GL service functions.
- **Verified 2026-07-16 (`/zj:verify 10`, tag `zj/good-10-mousse-work-orders`):** Verdict PASS.
  All 7 SCs live-proven — `verify_mousse.py` 34/34 (WIP-clears-to-zero Decimal-exact + concurrency
  race via `asyncio.Barrier`), `verify_mousse_api.py` 34/34 (HTTP RBAC + audit); full regression
  13/13 verify_* exit 0, TB nets zero; FE Vitest + build clean; alembic head 0012. **Fix loop
  closed one major** (`5cffeeb`): completion debited 1130 / credited 1140 for the same
  `accumulated_wip`, but the FG receipt capitalises only `planned_qty × fg_unit_cost` into the
  inventory subledger, so on non-divisible WIP (100/3) the 1130 control account permanently drifted
  from the subledger — now a 3-line JE routes the residual to a new seeded **5190 Inventory
  Rounding** account (D-P10-2 amended), so 1140 clears AND 1130 ties to the subledger, both exact;
  pinned by `verify_mousse.py` scenario D. The AST-split chore (`6293c96`+`3d59068`) reviewed clean.
  Artifacts: `.zj/phases/10-mousse-work-orders/{VERIFICATION,REVIEW}.md`.
- **Retro 2026-07-16** (`/zj:retro 10`): learnings in `.zj/LEARNINGS.md` "Phase 10" — (1) "WIP clears
  to zero" + "TB nets zero" are both Σdr==Σcr identities and neither can catch a GL-control-vs-subledger
  drift; assert a control account directly against its subledger, never against zero (the 1130 major);
  (2) one completion JE moved two accounts and only one had an invariant → enumerate an invariant per
  account a mutation posts to; (3) the recurring concurrency-major was *pre-empted by design* for the
  first time (lock + `asyncio.Barrier` verify planned in from the start, the 9b rule paying off);
  (4) a mechanical AST refactor's parity check must not reuse the transform's own node filter, and
  import-surface completeness is proven by import (pytest collection), not by behavioral verify scripts.
  Deferrals homed: MOUSSE↔SYERP cross-path inventory-ledger lock gap → the existing BACKLOG p2
  inventory-race item (trigger now live); zero-cost lone-component issue → p3; 422 sweep now includes
  mousse. **This closes the last v2.0 DoD clause ("execute work orders that consume PLUM BOMs and
  inventory") — v2.0 is code-complete; next is `/zj:milestone` for v2.0.**

---

## v3.0 — Customer & logistics (CRUMB + GELATO + AR)  [in progress — spec'd 2026-07-16; Phase 11 split 11a/11b and Phase 11a planned 2026-07-16, D-V3-1..15]

Owner chose this as the milestone after v2.0 (over the FLAN port and PLUM-advanced): it completes
the **sell-side + fulfillment loop** on top of the now-complete operations core, and it is where
**accounts receivable** was explicitly parked (SYERP-13, split out of Phase 9 at D-P9-4 so AR
invoices flow from CRUMB sales orders rather than being keyed standalone).

**Definition of done (sharpened at `/zj:spec`, D-V3-1) — three clauses:**
1. **CRM & sales pipeline (CRUMB-01)** — manage customers and run leads → opportunities → quotes →
   sales orders, with PLUM-derived editable line pricing and a customer communication log; confirming
   an order **soft-reserves inventory**.
2. **Warehouse fulfillment (GELATO-01)** — bins within SYERP stock locations; directed putaway on
   inbound receipts; outbound **pick → pack → ship** of sales orders; shipping **relieves the reserved
   inventory** (quantities only — lot/serial deferred).
3. **Accounts receivable & sell-side books (SYERP-13)** — shipment posts Dr COGS / Cr Inventory;
   invoice-from-shipment posts Dr AR / Cr Revenue; customer receipt posts Dr Cash / Cr AR; **AR aging
   ties Decimal-exactly to the 1120 control account** and the **Trial Balance still nets zero**.

**Scope decisions (D-V3-1..9, see SRD preamble):** sell-side = two-event real books, no clearing
account (all CoA accounts already seeded); invoices are shipment-driven; **deferred** — lot/serial
(D-V3-4), email/analytics (D-V3-5), price lists (D-V3-6); GELATO does inbound **and** outbound
(D-V3-7); orders soft-reserve (D-V3-8); CRUMB & GELATO are new modules that import SYERP inventory/GL
service fns (D-V3-9).

**Phase → FR mapping (proposed; confirm/sub-split at `/zj:plan`, mirroring the 9a/9b/9c precedent):**

| Phase | Delivers | Depends on | Notes |
|-------|----------|-----------|-------|
| **11a — CRUMB CRM & pipeline** `[done — verified + retro'd 2026-07-16]` | CRUMB-01 AC1/2/3−/5/6/7 (leads → opps → quotes + comm log, no inventory) | SYERP customers ✓, PLUM parts ✓ | New `crumb` module; **verified 2026-07-16** (`efcf2e6`, tag `zj/good-11a-crumb-crm-pipeline`). 19 tasks; verify_crumb 22/22 + verify_crumb_api 54/54 + 13/13 regression + FE 4/4 + build. 4 review/verify gaps fixed at close (`a697c69`). No inventory, no GL. Split from Phase 11 at D-V3-10. |
| **11b — CRUMB sales orders + reservation** `[verified 2026-07-17]` | CRUMB-01 AC4 (+ AC3 SO-conversion tail) — **CRUMB-01 now complete** | Phase 11a, SYERP inventory (reservation) | Sales-order FSM + accepted-quote→SO conversion; **soft-reservation crux** (D-V3-8, `qty_reserved` accumulator on SO line D-V3-11). **Verified 2026-07-17** (`fec334f`, tag `zj/good-11b-crumb-sales-orders`). 17 tasks; verify_crumb_so 27/27 (incl. concurrency scenario F) + verify_crumb_so_api 40 + 15/15 regression = 17/17; FE Vitest + build; TB nets zero (no GL). Verify fix loop caught + fixed a blocker (direct-create lines never resolved `plum_part_id→item_id` → UI orders reserved 0), pinned by new (D2) assertions. Posts no GL/InventoryTxn — reservation is a soft quantity. |
| **12 — GELATO warehouse core** | GELATO-01 (8 ACs) | Phase 11 (orders to fulfil), SYERP inventory ledger | New `gelato` module; **ship posts the COGS JE** (imports SYERP GL fns). Bins realize the D-P8-3 deferral. |
| **13 — SYERP-13 AR & sell-side books** | SYERP-13 (7 ACs) | Phase 12 (invoices from shipments), SYERP-12 GL engine ✓ | Extends `syerp`; invoice-from-shipment + receipts + AR aging tie-out. New report screen: AR aging. |

Build order follows the money: order (11) → ship (12) → invoice/collect (13). Likely to sub-split at
plan the way Phase 9 became 9a/9b/9c; **the DoD, not the phase count, is the contract.**

**Carried debt to weigh at planning:** the BACKLOG p1 infra debt (CI, live-DB pytest harness, both
lint gates) is now two milestones old; the standing **inventory-ledger row-lock race** (BACKLOG p2)
gains a third writer when GELATO ship lands — plan the shared FOR-UPDATE lock across every
floor-guarded path (issue/adjust/receive/transfer/**ship**) rather than a per-module lock. The
`/zj:ship` master-merge debt (D-M2-3) is **resolved** (v2.0 shipped via PR #2).

---

## Later milestones (unordered candidates — sequence at v3.0 close)

- **FLAN port** (FLAN-01) — retire the second frozen prototype.
- **PLUM advanced** (PLUM-11..16) — documents, ECO workflow, labor costing, cost ranges,
  distributor pricing.
- **Quality & release** (CRISP-01, NFR-3 offline, license audit, public open-source release
  prep).
