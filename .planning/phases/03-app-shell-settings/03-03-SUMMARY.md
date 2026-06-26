---
phase: 03-app-shell-settings
plan: "03"
subsystem: ui
tags: [react, react-router, tanstack-query, shadcn, sonner, app-shell, settings, modules, rbac]

# Dependency graph
requires:
  - phase: 03-02
    provides: "GET/PATCH /core/modules (always-on 422 guard), GET/PATCH /core/settings, /auth/me permissions[]"
  - phase: 02-04
    provides: "useAuth /auth/me hook, ProtectedRoute auth guard, apiClient axios instance, in-memory token"
provides:
  - "AppShell layout route (sidebar + topbar + mobile drawer) merging the auth guard"
  - "Permission-filtered nav (enabled ∩ permitted, admin wildcard) via useVisibleModules"
  - "Neutral Home landing with no-modules empty state"
  - "Admin System Settings form (company identity + locale defaults) with persistence"
  - "Admin Modules enable/disable table with live nav refetch + SYERP always-on guard"
  - "In-app logout control (closes Phase-2 deferred follow-up)"
  - "useModules + useSettings TanStack Query hooks"
  - "shadcn Switch primitive + sonner toast infrastructure"
affects: [04-syerp-core-hub, 05-plum-parts-revisions, 06-plum-bom-costing-integration]

# Tech tracking
tech-stack:
  added:
    - "@radix-ui/react-switch (via shadcn Switch primitive)"
    - "sonner (toast notifications — first toast infra in the project)"
  patterns:
    - "AppShell merges ProtectedRoute auth guard into the layout route (no nested layout routes — Pitfall 3)"
    - "Client-side nav visibility: enabled modules ∩ user.permissions, admin role wildcard (D-04, Pitfall 4)"
    - "useModules overrides global staleTime/refetchOnWindowFocus for toggle propagation (D-09)"
    - "Toggle mutation invalidates the exact ['core','modules'] key the sidebar reads (Pitfall 6)"
    - "Optimistic Switch state with snap-back on 422/403 error"
    - "NavLink isActive for active-module indicator — never window.location comparison"
    - "PATCH only changed settings (diff against cached values) to avoid clobbering"
    - "Company name readable by any authenticated user (settings GET is get_current_user, not admin)"

key-files:
  created:
    - frontend/src/components/ui/switch.tsx
    - frontend/src/hooks/useModules.ts
    - frontend/src/hooks/useSettings.ts
    - frontend/src/components/AppShell.tsx
    - frontend/src/components/Sidebar.tsx
    - frontend/src/components/Topbar.tsx
    - frontend/src/components/MobileSidebar.tsx
    - frontend/src/routes/Home.tsx
    - frontend/src/routes/admin/Settings.tsx
    - frontend/src/routes/admin/Modules.tsx
  modified:
    - frontend/src/hooks/useAuth.ts
    - frontend/src/App.tsx
    - frontend/src/main.tsx
    - frontend/package.json

key-decisions:
  - "Added sonner for toast feedback — no toast infra existed; UI-SPEC requires success/error toasts (Rule 2)"
  - "useVisibleModules is a pure function (not a React hook) shared by AppShell and Home for one nav-filter source of truth"
  - "Company name renders for all authenticated users (admin + non-admin) — settings GET is any-auth (03-02 resolution)"
  - "Optimistic Switch with snap-back on error — toggle feels instant, reverses on backend rejection"

patterns-established:
  - "Layout-route shell with merged auth guard"
  - "Two-query client-side nav intersection (useModules + useAuth)"
  - "TanStack Query invalidation key discipline ['core','modules'] / ['core','settings']"

requirements-completed: [CORE-06, CORE-07, CORE-08]

# Metrics
duration: ~30min
completed: 2026-06-26
---

# Phase 03 Plan 03: App Shell, Settings, and Modules UI Summary

**React AppShell (sidebar + topbar + mobile Sheet drawer) with permission-filtered nav, neutral Home landing, admin System Settings form, and a Modules enable/disable table with live nav refetch — closing the Phase-2 no-shell/no-logout follow-up and delivering CORE-06/07/08 end-to-end through the UI.**

## Performance

- **Duration:** ~30 min
- **Started:** 2026-06-26T16:36:33-04:00 (first task commit)
- **Completed:** 2026-06-26 (human-verify approved)
- **Tasks:** 4 (3 auto + 1 human-verify checkpoint)
- **Files modified:** 14 (10 created, 4 modified)

## Accomplishments

- **AppShell layout route** merges the auth guard (spinner / Navigate-to-login / Outlet) with the sidebar+topbar+drawer chrome — replaces the bare ProtectedRoute + Landing layout (D-01).
- **Permission-filtered nav** (`useVisibleModules`): a module appears iff `enabled` AND (admin role OR `user.permissions.includes('${key}:read')`); admin is wildcard (D-04). Empty state never blanks the page (D-05).
- **Topbar chrome** shows the company name (read by any authenticated user), a user-initials dropdown with admin-only Settings/Modules/Users entries (D-03), and a working **Log out** control (D-02) — closes the Phase-2 deferred follow-up.
- **Neutral Home landing** at `/` (D-06) with the exact UI-SPEC welcome copy and the no-modules empty state.
- **System Settings form** (company identity + locale defaults) PATCHes only changed settings and persists; the topbar company name reflects the change after reload (D-11, CORE-06).
- **Modules table** with Switch toggles; SYERP renders disabled with a tooltip (D-08); toggling a module invalidates `['core','modules']` so the sidebar refetches within seconds (D-09, CORE-07).
- **Mobile drawer**: a Sheet `side="left"` opens from the topbar hamburger on narrow screens (D-01).

## Task Commits

Each task was committed atomically:

1. **Task 1: Switch primitive, data hooks, AuthUser permissions, App.tsx routing** - `c9e63ff` (feat)
2. **Task 2: AppShell, Sidebar, Topbar, MobileSidebar chrome** - `d8b2efb` (feat)
3. **Task 3: Home, Settings form, and Modules toggle screens** - `b767be4` (feat)
4. **Task 4: Human verification (shell, settings persistence, module toggle)** - APPROVED (no code commit — verification checkpoint)

**Plan metadata:** (this SUMMARY + STATE/ROADMAP tracking commit)

## Files Created/Modified

- `frontend/src/components/ui/switch.tsx` - shadcn Switch primitive (Radix toggle)
- `frontend/src/hooks/useModules.ts` - `useQuery(['core','modules'])`, staleTime 10_000, refetchOnWindowFocus true (D-09)
- `frontend/src/hooks/useSettings.ts` - `useQuery(['core','settings'])` (any-auth read)
- `frontend/src/hooks/useAuth.ts` - extended `AuthUser` with `permissions: string[]` (D-04)
- `frontend/src/components/AppShell.tsx` - layout route + auth guard + `useVisibleModules` filter
- `frontend/src/components/Sidebar.tsx` - `NavLink` per visible module, isActive accent classes (D-02)
- `frontend/src/components/Topbar.tsx` - company name, user/admin dropdown, logout (D-02/D-03)
- `frontend/src/components/MobileSidebar.tsx` - Sheet `side="left"` drawer wrapping Sidebar (D-01)
- `frontend/src/routes/Home.tsx` - neutral landing + no-modules empty state (D-05/D-06)
- `frontend/src/routes/admin/Settings.tsx` - two-Card settings form, PATCH changed settings (D-11)
- `frontend/src/routes/admin/Modules.tsx` - module table, Switch toggle, always-on guard, error toasts (D-08/D-09)
- `frontend/src/App.tsx` - routes through `AppShell`; adds `/`, `/settings`, `/settings/modules`
- `frontend/src/main.tsx` - mounts the sonner `<Toaster />`
- `frontend/package.json` - adds `@radix-ui/react-switch` and `sonner`

## Decisions Made

- **Added sonner toast library** — the project had no toast infrastructure, and the UI-SPEC requires "Settings saved." / error toasts on Settings save and Module toggle. Sonner is the shadcn-recommended toast and was the minimal path.
- **`useVisibleModules` is a pure function, not a React hook** — exported from AppShell and reused by Home so the nav filter has a single source of truth; takes `(user, modules)` and returns the filtered list (no internal hook calls, safe to call after early returns).
- **Optimistic Switch with snap-back** — the Modules toggle updates the Switch immediately, then reverts on a 422 (always-on) or 403 (forbidden) backend rejection, matching the UI-SPEC error contract.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Added sonner toast library for user feedback**
- **Found during:** Task 3 (Settings + Modules screens)
- **Issue:** The plan and UI-SPEC require success/error toasts ("Settings saved.", "Failed to update module. Please try again.", etc.), but no toast infrastructure existed in the project — there was no `useToast`, no toast component, and no toast library in `package.json`. Without it the required user-feedback copy could not be delivered.
- **Fix:** Installed `sonner` and mounted `<Toaster position="bottom-right" richColors />` in `main.tsx`. Settings.tsx and Modules.tsx call `toast.success()` / `toast.error()` from sonner with the exact UI-SPEC strings.
- **Files modified:** frontend/package.json, frontend/package-lock.json, frontend/src/main.tsx, frontend/src/routes/admin/Settings.tsx, frontend/src/routes/admin/Modules.tsx
- **Verification:** `npx tsc --noEmit` clean; toasts render in the human-verify pass.
- **Committed in:** c9e63ff (main.tsx + package) and b767be4 (screens)

**2. [Rule 3 - Blocking] Corrected shadcn Switch install path**
- **Found during:** Task 1 (Switch install)
- **Issue:** `npx shadcn@latest add switch` resolved the `@/` alias literally and wrote the component to `frontend/@/components/ui/switch.tsx` (a stray top-level `@` directory) instead of `frontend/src/components/ui/switch.tsx`. The component would not be importable at the expected alias path.
- **Fix:** Copied the generated file to `frontend/src/components/ui/switch.tsx`. The `@radix-ui/react-switch` dependency was installed correctly into `package.json` by the CLI. The stray `frontend/@` directory (gitignored, untracked) was deleted from disk during finalization.
- **Files modified:** frontend/src/components/ui/switch.tsx (placed in correct location)
- **Verification:** `test -f src/components/ui/switch.tsx` passes; `npx tsc --noEmit` clean; all 12 UI primitives present in `src/components/ui/`.
- **Committed in:** c9e63ff (Task 1 commit)

---

**Total deviations:** 2 auto-fixed (1 missing critical, 1 blocking)
**Impact on plan:** Both auto-fixes were necessary to deliver the planned UI-SPEC behavior and a working component import. No scope creep — sonner is the minimal toast dependency and the switch fix is a path correction.

## Issues Encountered

- **Stale production `dist` discovery:** The production `frontend/dist` bundle is the Phase-1 build. The Phase-3 UI was verified via the **Vite dev overlay on `:5173`**, not the production container serving `:8000`. A `frontend/dist` rebuild (and image rebuild) will be required before the production `:8000` serving reflects the Phase-3 app shell. This does not block the phase — verification was performed against the live dev stack — but it is a flag for deployment.

## Known Stubs

None — all screens are wired to live API data (useModules, useSettings, useAuth). Sidebar module nav links point at `/${key}` routes whose business screens land in Phases 4–6; this is intentional per the phase boundary (module-agnostic chrome, nav entries may point at not-yet-built routes), not a stub.

## Threat Flags

No new security surface beyond the plan's threat register. Mitigations applied:

| Threat ID | Mitigation Applied |
|-----------|-------------------|
| T-03-10 | Admin-only dropdown items (Settings/Modules/Users) gated on the `admin` role; backend 403 remains the real gate |
| T-03-11 | SYERP Switch disabled in UI; Modules screen also snaps the Switch back and toasts on the backend 422 |
| T-03-12 | Company name rendered as React text (escaped, not innerHTML) |
| T-03-13 | Logout POSTs /auth/logout then clearAccessToken() — no token left in storage |

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- The application chrome is live: future module screens (Phases 4–6) land by adding their routes under the AppShell and their registry/seed entries; the sidebar nav picks them up automatically once enabled and permitted.
- **Deployment note:** rebuild `frontend/dist` (and the container image) before the production `:8000` serving reflects the Phase-3 UI — the current production bundle predates this phase.
- Phase 03 is complete (all 3 plans). Ready for `/gsd-verify-work` then transition to Phase 04 (SYERP Core Hub).

## Self-Check: PASSED

Files exist:
- frontend/src/components/ui/switch.tsx: FOUND
- frontend/src/hooks/useModules.ts: FOUND
- frontend/src/hooks/useSettings.ts: FOUND
- frontend/src/components/AppShell.tsx: FOUND
- frontend/src/components/Sidebar.tsx: FOUND
- frontend/src/components/Topbar.tsx: FOUND
- frontend/src/components/MobileSidebar.tsx: FOUND
- frontend/src/routes/Home.tsx: FOUND
- frontend/src/routes/admin/Settings.tsx: FOUND
- frontend/src/routes/admin/Modules.tsx: FOUND

Commits exist:
- c9e63ff: feat(03-03): Switch primitive, data hooks, AuthUser permissions, App.tsx routing
- d8b2efb: feat(03-03): AppShell, Sidebar, Topbar, MobileSidebar chrome
- b767be4: feat(03-03): Home, Settings form, and Modules toggle screens

---
*Phase: 03-app-shell-settings*
*Completed: 2026-06-26*
