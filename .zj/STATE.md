# STATE — BizNiceSweets
Updated: 2026-07-09

## Position

- **Milestone:** v1.0 — Foundation + PLUM (Phase 7 **done**; milestone close still **open** —
  human-UAT owed) · v2.0 — Phase 8 **DONE** (verified + retro complete).
- **Phase:** 7 (close v1.0 gaps) **verified + retro'd 2026-07-09** — roadmap `[done]`. Verified code
  tip `8975eeb`; tag `zj/good-07-close-v1-0-gaps` at the artifacts commit `ac56fa1` (same convention
  as Phase 8). Verdict PASS after a fix loop. Learnings in `.zj/LEARNINGS.md` (Phase 07).
  - **One blocker found and fixed** (`7562a02`): the phase's own SC2 numeric part-number fix cast
    the suffix to **int4**. `part_number` is `String(50)` with no format constraint, so a legal
    `P9999999999` matched `^P[0-9]+$` and overflowed the cast — **every** subsequent auto-numbered
    `create_part` returned 500, permanently, until the row was deleted by hand. Any `plum:write`
    user could trigger it. Reproduced end-to-end (201 to plant, then 500 forever); cast → `Numeric`.
  - **Criteria became executable tests**, each proven red/green:
    `backend/scripts/verify_plum_vendor_paths.py` (SC1, 8 live assertions, drives all four
    function-local alias sites independently), `backend/scripts/verify_part_numbering.py` (SC2 SQL
    half, 7 live assertions incl. the overflow guard), `backend/tests/plum/test_part_number.py`
    (SC2 pure half, 4 tests that run in the ordinary pytest suite),
    `frontend/src/routes/plum/ImportExport.test.tsx` (SC3, positive + negative path).
  - Full re-verification after the fix loop: **66 live-DB assertions, 0 failures** across five
    scripts; backend 90 passed / 98 skipped; frontend 49 passed; build clean.
  - Artifacts: `.zj/phases/07-close-v1-0-gaps/{PLAN.md,VERIFICATION.md,REVIEW.md}`.
  - Retro deferrals homed: lint gates + stale API image → BACKLOG p1; auto-number double-collision
    race → BACKLOG p2; `part_number` format constraint (won't add) → D-P7-6; dev-DB `P-COMMIT-AVL-1`
    artifact → won't fix.
- **Phase:** 8 (SYERP inventory & purchasing) **verified + retro'd 2026-07-08** — roadmap `[done]`.
  All 16 SYERP-10/11 acceptance criteria proven live (`verify_inventory` 15/15,
  `verify_purchasing` 18/18, `verify_e2e_p8` 18/18 fresh-DB). One code defect found + fixed in the
  fix loop (`554c3fe` — bad `plum_part_id` now 4xx not 500). Tag `zj/good-08-syerp-inventory-purchasing`.
  Retro lessons captured in `.zj/LEARNINGS.md` (Phase 08). Deferrals homed: BACKLOG p1 (port
  verify-script assertions to integration tests, D-P7-4/D-P7-5), BACKLOG p2 (audit-write atomicity,
  ledger concurrency races — accepted single-shop; **+ auto-number double-collision race**),
  BACKLOG p3 (Starlette 422 sweep).
- **Branch:** `feature-syerp-inventory-purchasing` (tip now carries the Phase-7 verify fixes), cut
  from `bugfix-plum-v1-gaps` per D-P8-11 — atop unmerged Phase 7, not yet on `master`.
  **Note:** the Phase-7 blocker fix landed on *this* branch, not on `bugfix-plum-v1-gaps`.

## Next action

**Phases 7 and 8 are both verified and retro'd. Choose the next move:**
1. **`/zj:milestone`** — closes v1.0. This is where the **12-check human-UAT** finally runs
   (`.zj/UAT-v1.0.md`, currently **2/12**: checks 1 & 8 passed). Both Phase 7 and Phase 8 deferred
   it here (D-P7-5); it is the last real debt against v1.0 and nothing is marked `implemented` on
   the strength of it. Regression checks 9–12 exercise the exact fixes verified above.
2. `/zj:ship` / merge `feature-syerp-inventory-purchasing` (verified + tagged; carries Phases 7+8).
   Optionally `/zj:log phase 07` / `/zj:log phase 08` first to file the formal work logs.
3. `/zj:plan 09` — SYERP AP/AR & reporting (only once the branch situation above is resolved).

**Standing debt:** the PLUM pytest harness is still broken (BACKLOG p1, D-P7-4) — `tests/plum/*`
DB tests silently skip. It no longer leaves any Phase-7 criterion unprotected (the `verify_*.py`
gates cover them), but repair it before the guards drift out of sync with the pytest suite.

### Prior next action (build, now complete)
**BUILD IN FLIGHT — Phase 8** on branch `feature-syerp-inventory-purchasing` (cut from
`bugfix-plum-v1-gaps` tip `5e77de5` per D-P8-11). Resume at the first unchecked task in
`.zj/phases/08-syerp-inventory-purchasing/PLAN.md`. — **DONE: all 25 tasks + verify complete.**

### Build progress (Phase 8)
**WAVE A (inventory backend) COMPLETE + PROVEN LIVE.**
- **T1** `b5c5c31` — inventory schema (migration 0007: item/location/txn ORM + DDL).
- **T2** `511d6ae` — item CRUD + numeric-safe `ITEM-####` generator (pure boundary tests).
- **T3** `06f318c` — stock-location CRUD + idempotent `Main` seed (wired into `run_seeds`).
- **T4** `e35021e` — derived on-hand-by-location + valuation + txn-history reads (zero-net omitted).
- **T5** `8e1b31f` — receipt posting + pure Decimal `compute_new_moving_avg` (scale-6 ROUND_HALF_UP).
- **T6** `0074bf0` — adjustment posting + per-location negative guard (avg untouched).
- **T7** `5f2a228` — transfer posting (paired legs net-zero, source-underflow guard).
- **T8** `e309260` — standalone live-DB `verify_inventory.py`: **14/14 PASS, exit 0** against live
  Postgres (avg 3.000000, value 60.000000, neg-reject, transfer nets-zero). Gate holds.
**WAVE B (inventory UI) COMPLETE.** All Vitest + `tsc -b` builds green.
- **T9** `1fd2423` — Inventory Items screen (list/sheet/archive, PLUM-link Select degrades safely).
- **T10** `8e75af9` — Stock Locations screen (name-only clone).
- **T11** `8b2c748` — Item detail (on-hand/valuation/ledger) + pre-wired Adjust/Transfer dialog seams.
- **T12** `c9d6952` — Stock Adjustment dialog (signed qty, required reason, 422 keeps-open).
- **T13** `cdf0e6c` — Stock Transfer dialog (from/to guard, 422 keeps-open).
**WAVE C (purchasing backend) COMPLETE + PROVEN LIVE.**
- **T14** `cafa93f` — purchasing schema (migration 0008: PO + PO-line ORM/DDL).
- **T15** `b5d7882` — PO draft CRUD + numeric-safe `PO-####` generator + vendor-only guard.
- **T16** `92896ea` — PO approve/close FSM (`PO_TRANSITIONS`, stamps approved_at/by).
- **T17** `79181bd` — PO receiving → `post_receipt` (crux): over-receipt reject, status roll-up,
  single atomic txn (post_receipt gained `commit=False`).
- **T18** `ce5f666` — vendor PO history: per-PO `total` + ordered/received/outstanding roll-up.
- **T19** `451ec7d` — standalone live-DB `verify_purchasing.py`: **18/18 PASS, exit 0** — PO receive
  posts real inventory txns, moving-avg 5.000000, value 50.000000, over-receipt 422, roll-up
  partially→received, vendor total 50. Crux proven end-to-end.
**WAVE D (purchasing UI) COMPLETE.** All Vitest + builds green.
- **T20** `6d8afcc` — PO list (status badges, totals, vendor filter).
- **T21** `e21ac2a` — PO create/draft-edit (vendor picker + line editor, two-phase submit).
- **T22** `cd03899` — PO detail (roll-up, approve/close, per-line receive seam).
- **T23** `8aa6b65` — Receiving dialog (qty=outstanding default, location Select, 422 keeps-open).

**WAVE E (verify + docs) COMPLETE. PHASE 8 BUILD COMPLETE — all 25 tasks done.**
- **T24** `3703c51` — `verify_e2e_p8.py`: **18/18 PASS on a FRESHLY-MIGRATED DB** (alembic 0001→0008
  from empty, `Main` seeded out-of-the-box, full D-P8-8 flow, exact moving-avg/on-hand). Def-of-done.
- **T25** `0c696a8` — SRD SYERP-10/11 → `implemented (backend verified live; UI flow UAT pending)`;
  requirements-progress updated; `.zj/UAT-v2.0.md` created; task checklist archived.
- **Wrap-up** `e1b7f84` — fixed a full-suite-only test regression (item-detail dialog-seam mock).

### Wrap-up test/lint status
- Backend pure suite: **55 passed, 1 skipped** (skip = live-DB seed test, broken harness/D-P7-4).
- Frontend: **47 Vitest passed (17 files)**, `npm run build` tsc-clean.
- Live-DB proof: verify_inventory 14/14, verify_purchasing 18/18, verify_e2e_p8 18/18 (fresh DB).
- **Lint gates BOTH non-functional (pre-existing):** no `ruff` in `.venv`; ESLint 10 lacks flat
  `eslint.config.js`. Correctness rests on the above, not lint. Pre-merge chore (BACKLOG candidate).

### Prior next action (Phase 8 verify — now complete)

`/zj:verify 08` ran 2026-07-08 (PASS, tag `zj/good-08-syerp-inventory-purchasing`), and
`/zj:verify 07` ran 2026-07-09 (PASS, tag `zj/good-07-close-v1-0-gaps`). **Both are done** — see
"## Next action" at the top of this file for what is actually next. The only v1.0 debt left is the
12-check human-UAT at `/zj:milestone` (`.zj/UAT-v1.0.md`, 2/12).
- **Known non-blockers logged** (PLAN.md Noticed): ruff absent (no backend lint), ESLint 10 flat-config
  missing (no frontend lint — already a Phase-7 item), Starlette 422 deprecation, Radix test-shim.

Original next action (pre-build): `/zj:build 8` — 25 tasks, wave order inventory backend → inventory
UI → purchasing backend → purchasing UI → verify.

## Build result (Phase 7)

- **T1** `5c33ed8` — Partner-alias fix (AVL/import 500s gone; import resolves live).
- **T2** `1b8bfa1` — numeric part# (proven live: DB had `P100000` → returns `P100001`).
- **T3** `37b5f97` — import-commit cache invalidation (tsc-clean, tests pass).
- **T4** `5db8278` — CLAUDE.md stack/architecture refreshed to live FastAPI/React.
- **T5** — stack up, `compose_api_1`, `alembic 0006`; :5173 serves; :8000 serves no SPA.
- **T6** — human-UAT deferred to milestone (D-P7-5); checks 1 & 8 passed.
- **T7** — SRD + requirements-progress reconciled honestly (PLUM-01 defect resolved; PLUM-04..10
  code-verified, UI UAT milestone-pending).

## Two deferrals now owned elsewhere (BACKLOG p1)

1. **PLUM live-DB test harness never runs** (broken probe + async-engine loop + no seed/isolation)
   — D-P7-4, BACKLOG p1. Fixes currently proven via standalone async scripts, not pytest.
2. **v1.0 human-UAT** — `.zj/UAT-v1.0.md`, run at `/zj:milestone` (D-P7-5).

## Adoption note

Adopted from GSD on 2026-07-04. Prior planning system archived at `archive/planning-gsd/`
(phases 01–07, REQUIREMENTS, ROADMAP, STATE, v1.0-MILESTONE-AUDIT, codebase snapshots) and
`archive/planning-docs/` (program ROADMAP.md, decisions.md). `.zj/` is self-contained — the
archive is history, not a dependency.
