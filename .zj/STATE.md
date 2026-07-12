# STATE — BizNiceSweets
Updated: 2026-07-11 (Phase 9b **BUILD COMPLETE** — all 16 tasks done + verified; next `/zj:verify 09b`)

## Position

- **Project:** BizNiceSweets
- **Step:** build 09b **complete** → next is `/zj:verify 09b`.
- **Next action:** `/zj:verify 09b` — verify AP bills / PO-match / payments (SYERP-12 AC4/AC5/AC8/AC9)
  goal-backward + code review the diff on branch `feature-syerp-ap-bills`.
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
