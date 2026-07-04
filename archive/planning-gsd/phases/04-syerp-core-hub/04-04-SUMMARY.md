---
phase: 04-syerp-core-hub
plan: "04"
subsystem: frontend/syerp
tags: [react, tanstack-query, shadcn, chart-of-accounts, routing, react-router, tailwind-v4]
dependency_graph:
  requires: ["04-03"]
  provides: ["phase-04-complete"]
  affects: ["frontend/src/routes/syerp/", "frontend/src/App.tsx"]
tech_stack:
  added: []
  patterns:
    - Read-only grouped-Card browse screen (no mutations, no toolbar, no accent — D-11 scope guard)
    - account_type grouping of a flat API list, frontend-side
    - Navigate redirect from module-root path to a concrete default sub-route
    - SYERP sub-nav tab strip (module root only exposed by sidebar)
key_files:
  created:
    - frontend/src/routes/syerp/GLAccounts.tsx
    - frontend/src/routes/syerp/components/SyerpNav.tsx
  modified:
    - frontend/src/App.tsx
    - frontend/src/index.css
    - frontend/src/routes/syerp/components/PartnerSheet.tsx
    - frontend/src/routes/syerp/Vendors.tsx
    - frontend/src/routes/syerp/Customers.tsx
decisions:
  - "Sidebar nav lands on /syerp (module key drives /${key}); App.tsx adds a Navigate redirect /syerp -> /syerp/vendors so the entry resolves to a real screen"
  - "GLAccounts groups the flat GET /gl/accounts list by account_type into 5 fixed-order Cards; round-hundred codes (regex /0+$/) are top-level (bold, no indent), all others get pl-6"
  - "Catch-all route redirects unknown paths to Home instead of a blank screen (UAT fix)"
  - "SYERP sub-nav tab strip (SyerpNav.tsx) added to all three SYERP screens since the sidebar only exposes the SYERP module root"
requirements_completed: [SYERP-01, SYERP-02, SYERP-03, SYERP-04, SYERP-05]
metrics:
  duration: "~20min (autonomous task) + human UAT verification"
  completed_date: "2026-06-27"
  tasks_completed: 2
  files_created: 2
  files_modified: 5
---

# Phase 4 Plan 04: Chart of Accounts Screen + SYERP Route Wiring Summary

**Read-only Chart of Accounts browse screen (5 grouped account-type Cards) plus all three SYERP routes wired under the AppShell, completing the Phase 4 SYERP Core Hub end to end (verified via human UAT).**

## Performance

- **Duration:** ~20 min for the autonomous task; human-verify checkpoint approved after UAT
- **Completed:** 2026-06-27
- **Tasks:** 2 (1 autonomous + 1 human-verify checkpoint, both passed)
- **Files created:** 2 · **Files modified:** 5 (including 4 UAT follow-up fixes)

## Accomplishments

- **GLAccounts.tsx** — read-only Chart of Accounts browse screen. Fetches `GET /api/v1/syerp/gl/accounts` via `useQuery(['syerp','gl','accounts'])`, groups the flat list by `account_type`, and renders 5 fixed-order Cards (Assets / Liabilities / Equity / Revenue / Expenses). Top-level round-hundred accounts are bold with no indent; sub-accounts indented `pl-6`. No toolbar, no mutation controls, no accent elements (D-11 scope guard). Rows are plain non-interactive `div`s (accessibility rule 8). Loading spinner + error-copy states match the other SYERP screens.
- **App.tsx routing** — imports Vendors, Customers, GLAccounts; registers `/syerp/vendors`, `/syerp/customers`, `/syerp/gl` inside the existing `<Route element={<AppShell />}>` block; adds a `/syerp` → `Navigate` redirect to `/syerp/vendors` so the sidebar nav entry (which lands on `/syerp` per the `/${mod.key}` convention) resolves to a real screen.
- **Phase 4 SYERP Core Hub complete** — backend partner + GL API and the Vendor, Customer, and Chart of Accounts screens are wired into app navigation and verified end to end by human UAT (all 5 checks passed: Vendor CRUD + search + archive/restore, Customer CRUD + search, dual-role partner in both lists, CoA read-only tree, role guard blocking save).

## Task Commits

1. **Task 1: Chart of Accounts browse screen + route wiring** — `d90e731` (feat)
2. **Task 2: Human verify — Phase 4 SYERP screens end to end** — verification only (no commit); approved after UAT

**UAT-driven follow-up fixes** (committed on this branch during human verification, after `d90e731` — part of Phase 4's delivered state; see Deviations):

- `41d2fb7` (fix) — register shadcn color tokens via `@theme` in `src/index.css`
- `a3f50da` (fix) — constrain partner country fields to ISO 2-letter + surface API validation errors in toast
- `2e78af8` (fix) — catch-all route redirects unknown paths to Home
- `d88d55e` (feat) — SYERP sub-nav tab strip (`SyerpNav.tsx`) on all three SYERP screens

**Plan metadata:** committed with this SUMMARY (docs: complete plan)

## Files Created/Modified

- `frontend/src/routes/syerp/GLAccounts.tsx` (created) — read-only Chart of Accounts browse screen
- `frontend/src/routes/syerp/components/SyerpNav.tsx` (created, UAT) — Vendors | Customers | Chart of Accounts tab strip
- `frontend/src/App.tsx` (modified) — three SYERP routes + `/syerp` redirect; catch-all → Home (UAT)
- `frontend/src/index.css` (modified, UAT) — shadcn color tokens registered via `@theme` for Tailwind v4
- `frontend/src/routes/syerp/components/PartnerSheet.tsx` (modified, UAT) — ISO 2-letter country constraints + real API error in toast
- `frontend/src/routes/syerp/Vendors.tsx`, `frontend/src/routes/syerp/Customers.tsx` (modified, UAT) — SyerpNav tab strip wired in

## Decisions Made

- **Sidebar → /syerp redirect.** The sidebar renders one NavLink per module at `/${mod.key}`, so the SYERP entry lands on `/syerp`. Rather than change the sidebar convention, App.tsx adds a `Navigate replace` from `/syerp` to `/syerp/vendors` — keeps the sidebar generic and gives the nav entry a valid landing screen.
- **account_type grouping, frontend-side.** The API returns a flat list ordered by code; GLAccounts groups it into 5 fixed-order Cards by `account_type`. Top-level group accounts are identified by a round-hundred code (`/0+$/`) → bold + no indent; all others → `pl-6`. No recursive tree component needed (seeded CoA is shallow and small).
- **SYERP sub-nav (UAT).** Because the sidebar only exposes the SYERP module root, a tab strip (SyerpNav.tsx) was added to all three SYERP screens so users can move between Vendors / Customers / Chart of Accounts without going through the sidebar root each time.

## Deviations from Plan

The Task 1 autonomous work matched the plan exactly. The deviations below are **UAT-driven follow-up fixes** discovered during the human-verify checkpoint (Task 2) and committed on this branch after `d90e731`. They are part of Phase 4's delivered state and are recorded here per the coordinator's instruction. They were already committed and typecheck clean (`npx tsc --noEmit` = 0); they were not re-run or re-committed during finalization.

### UAT Follow-up Fixes

**1. [Rule 1 - Bug] shadcn color tokens not emitted by Tailwind v4**
- **Found during:** Task 2 (human UAT)
- **Issue:** Tailwind v4 was not generating the `bg-background` / `bg-card` / etc. utilities, so Sheet/Dialog/form panels rendered transparent and unreadable app-wide.
- **Fix:** Registered the shadcn color tokens via `@theme inline` in `src/index.css`.
- **Files modified:** `frontend/src/index.css`
- **Verification:** Panels render opaque/readable across the app; `npx tsc --noEmit` clean.
- **Committed in:** `41d2fb7`

**2. [Rule 1 - Bug] Opaque partner save error + unconstrained country fields**
- **Found during:** Task 2 (human UAT)
- **Issue:** `addr_country` / `country_of_origin` accepted free text but the API enforces ISO 2-letter, producing an opaque "Failed to save vendor." with no detail.
- **Fix:** Constrained both fields to ISO 2-letter (`maxLength` + uppercase + helper text) in PartnerSheet.tsx and surfaced the API's real validation/error detail in the toast.
- **Files modified:** `frontend/src/routes/syerp/components/PartnerSheet.tsx`
- **Verification:** Invalid country shows actionable error; valid 2-letter saves; `npx tsc --noEmit` clean.
- **Committed in:** `a3f50da`

**3. [Rule 1 - Bug] Unknown paths rendered a blank screen**
- **Found during:** Task 2 (human UAT)
- **Issue:** No catch-all route — navigating to an unknown path showed a blank screen.
- **Fix:** Added a catch-all route in App.tsx that redirects unknown paths to Home.
- **Files modified:** `frontend/src/App.tsx`
- **Verification:** Unknown paths land on Home; `npx tsc --noEmit` clean.
- **Committed in:** `2e78af8`

**4. [Rule 2 - Missing Critical Functionality] No in-screen SYERP navigation**
- **Found during:** Task 2 (human UAT)
- **Issue:** The sidebar only exposes the SYERP module root, so there was no way to move between the three SYERP screens once inside the module.
- **Fix:** Added `SyerpNav.tsx` tab strip (Vendors | Customers | Chart of Accounts) to all three SYERP screens.
- **Files modified:** `frontend/src/routes/syerp/components/SyerpNav.tsx` (new), `Vendors.tsx`, `Customers.tsx`
- **Verification:** Tabs navigate between all three screens; Vendors/Customers vitest tests pass; `npx tsc --noEmit` clean.
- **Committed in:** `d88d55e`

---

**Total deviations:** 4 UAT follow-up fixes (3 bug, 1 missing critical functionality), all committed during human verification.
**Impact on plan:** All four were necessary for a working, usable Phase 4 experience (readable panels, actionable errors, no blank screens, in-module navigation). No scope creep beyond Phase 4's SYERP UI surface.

## Issues Encountered

None during the autonomous Task 1. The four issues above surfaced during human UAT and were fixed before the checkpoint was approved.

## User Setup Required

None — no external service configuration required.

Note: the production `frontend/dist` predates Phase 3/4. A `frontend/dist` rebuild + container image rebuild is needed before the production `:8000` server reflects the Phase-4 UI; the UI was verified via the Vite dev server (`:5173`).

## Next Phase Readiness

- Phase 4 SYERP Core Hub is complete and human-verified — Vendor/Customer master data and the read-only Chart of Accounts are live and routed.
- SYERP `Partner` (vendors) table now exists, satisfying the FK precondition for PLUM-07 (part-to-vendor links) in Phase 6.
- Ready to begin Phase 5 (PLUM Parts & Revisions).

## Self-Check: PASSED

All created files exist on disk (GLAccounts.tsx, SyerpNav.tsx, App.tsx, 04-04-SUMMARY.md) and all referenced commits (`d90e731`, `41d2fb7`, `a3f50da`, `2e78af8`, `d88d55e`) are present in git history.

---
*Phase: 04-syerp-core-hub*
*Completed: 2026-06-27*
