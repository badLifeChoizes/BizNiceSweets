---
phase: 02-authentication-users
plan: "04"
subsystem: ui
tags: [auth, react, tanstack-query, axios, shadcn, jwt, silent-refresh, rbac, protected-route]

# Dependency graph
requires:
  - phase: 02-02
    provides: "/auth/login, /auth/refresh, /auth/logout, /auth/me endpoints; httpOnly refresh cookie; get_current_user dependency"
  - phase: 02-03
    provides: "/auth/users GET+POST+PATCH (admin-gated); seed_admin_user first-admin bootstrap; D-05 deactivation revokes sessions"
provides:
  - "Login page (/login) with in-memory access-token storage and OAuth2 form submit"
  - "ProtectedRoute layout guard redirecting unauthenticated users to /login"
  - "Axios apiClient with single-flight silent-refresh 401 interceptor (withCredentials)"
  - "useAuth TanStack Query session hook (/auth/me)"
  - "Admin User Management screen (/admin/users) with table, create/edit sheet, deactivate dialog, role select"
  - "Vite test environment + 12 component tests for redirect/login/users behaviors"
affects: [app-shell, settings, navigation, syerp, plum]

# Tech tracking
tech-stack:
  added:
    - "axios ^1.18 (HTTP client + 401-retry interceptor)"
    - "vitest 4.x + @testing-library/react + jsdom (component tests)"
    - "class-variance-authority, @radix-ui/react-slot/dialog/select/separator/dropdown-menu (shadcn deps)"
  patterns:
    - "In-memory access token (module variable, never localStorage/sessionStorage) — T-02-18"
    - "Single-flight silent-refresh interceptor with failedQueue — T-02-21"
    - "Layout-route auth guard (Navigate redirect / Outlet) via TanStack Query isLoading gate"
    - "OAuth2 form-data login (username=email) to match FastAPI OAuth2PasswordRequestForm"
    - "Client-side debounced (300ms) table search; destructive Dialog instead of confirm()"

key-files:
  created:
    - frontend/src/auth/token.ts
    - frontend/src/api/client.ts
    - frontend/src/hooks/useAuth.ts
    - frontend/src/components/ProtectedRoute.tsx
    - frontend/src/routes/Login.tsx
    - frontend/src/routes/admin/Users.tsx
    - frontend/src/components/ui/dropdown-menu.tsx
    - frontend/src/auth/ProtectedRoute.test.tsx
    - frontend/src/auth/Login.test.tsx
    - frontend/src/auth/Users.test.tsx
    - frontend/src/test-setup.ts
  modified:
    - frontend/src/App.tsx
    - frontend/vite.config.ts
    - frontend/package.json

key-decisions:
  - "Access token held only in a module-level JS variable (token.ts) — no localStorage/sessionStorage (D-06, T-02-18)"
  - "OAuth2 login submits URL-encoded form data (username=email, password) to match OAuth2PasswordRequestForm"
  - "Single-flight isRefreshing flag + failedQueue serializes concurrent 401 refreshes (Pitfall 4 / T-02-21)"
  - "Role assignment is single-select (seed has admin + user); multi-role UI deferred"
  - "Deactivate uses a destructive shadcn Dialog (not confirm()); UI gating is convenience only — backend 403 is the real authz gate (T-02-20)"

patterns-established:
  - "ProtectedRoute: isLoading -> spinner, no user -> Navigate to /login (state.from), else Outlet"
  - "apiClient response interceptor: 401 -> POST /auth/refresh -> setAccessToken -> retry; failure -> clear + redirect /login"
  - "shadcn components live in src/components/ui/; CLI mis-emits to frontend/@/ (gitignored) and must be copied"

requirements-completed: [CORE-02, CORE-03, CORE-04, CORE-05]

# Metrics
duration: ~75min
completed: 2026-06-25
---

# Phase 02 Plan 04: Frontend Auth UI Summary

**Three React/shadcn auth surfaces — Login (in-memory token), ProtectedRoute guard, and Admin User Management — wired to the Phase-2 backend via an axios client with a single-flight silent-refresh 401 interceptor and a TanStack Query /auth/me session hook.**

## Performance

- **Duration:** ~75 min (autonomous tasks) + human verification checkpoint
- **Completed:** 2026-06-25
- **Tasks:** 3 autonomous + 1 human-verify checkpoint (passed)
- **Files created:** 11
- **Files modified:** 3
- **Tests:** 12 component tests passing; `tsc --noEmit` clean

## Accomplishments

- Login page (`/login`) per UI-SPEC Screen 1: centered Card, Email/Password with show/hide toggle, "Sign In" / "Signing in…" states, inline 401 + network error copy, no Create-account / Forgot-password links (D-01/D-13). Stores the access token in memory and navigates to `state.from ?? '/'`.
- ProtectedRoute layout guard per UI-SPEC Screen 2: full-screen `Loader2` while resolving, `Navigate` to `/login` when unauthenticated, `Outlet` when authenticated.
- Axios `apiClient` with `withCredentials`, a Bearer request interceptor, and a single-flight 401 silent-refresh response interceptor (failedQueue serialization).
- `useAuth` TanStack Query hook against `/auth/me` (`retry: false`, 5-min staleTime).
- Admin User Management screen (`/admin/users`) per UI-SPEC Screen 3: heading + description, debounced search, accent "Create User" button (sole accent element), table (Full Name | Email | Role(s) | Status | Actions), color+text status badges, overflow Actions menu (Edit / Deactivate User / Activate) with row-scoped aria-labels and 44px targets, right-side Create/Edit Sheet with role Select and create-only password toggle, and a destructive deactivate Dialog with the exact UI-SPEC copy.
- App routing updated: public `/login`, `ProtectedRoute`-wrapped `/` and `/admin/users`.
- Vitest test environment added (jsdom + setup) with 12 passing component tests.

## Task Commits

Each autonomous task was committed atomically:

1. **Task 1: Axios client, silent-refresh interceptor, token store, useAuth, ProtectedRoute** — `3b40b95` (feat)
2. **Task 2: Login page + App routing wiring** — `f28cfd8` (feat)
3. **Task 3: Admin User Management screen** — `748d641` (feat)
4. **Chore: ignore shadcn CLI artifact directory `frontend/@/`** — `8109019` (chore)

## Files Created/Modified

- `frontend/src/auth/token.ts` — in-memory access token (get/set/clear), no web storage
- `frontend/src/api/client.ts` — axios instance + Bearer request interceptor + single-flight 401 silent-refresh
- `frontend/src/hooks/useAuth.ts` — `/auth/me` session query (retry:false, 5-min staleTime)
- `frontend/src/components/ProtectedRoute.tsx` — auth guard layout route
- `frontend/src/routes/Login.tsx` — Login page (UI-SPEC Screen 1)
- `frontend/src/routes/admin/Users.tsx` — Admin User Management (UI-SPEC Screen 3)
- `frontend/src/components/ui/dropdown-menu.tsx` — shadcn dropdown for the Actions overflow menu
- `frontend/src/components/ui/{button,input,label,card,table,badge,dialog,sheet,select,separator}.tsx` — shadcn primitives
- `frontend/src/auth/{ProtectedRoute,Login,Users}.test.tsx` — 12 component tests
- `frontend/src/test-setup.ts` — jest-dom setup for vitest
- `frontend/src/App.tsx` — public `/login` + ProtectedRoute-wrapped routes
- `frontend/vite.config.ts` — vitest test env (jsdom, globals, setup file)
- `frontend/package.json` — axios + vitest/testing-library devDeps + `test` script

## Checkpoint

**Task 4 (human-verify): PASSED.** The user verified in a real browser against the production container at `http://localhost:8000`:

- Login (`admin@example.com`) succeeds and redirects through the route guard.
- `/admin/users` renders the table with the accent "Create User" button as the sole focal accent.
- Create / search / deactivate user flows all work, including the destructive confirmation dialog.
- The `refresh_token` cookie is **HttpOnly**.
- Page reload keeps the session via silent refresh (no re-login prompt).

This confirms the browser-only behaviors (real cookie attributes, end-to-end silent refresh across reload, visual contract) that the automated component tests cannot observe.

## Decisions Made

- Access token kept exclusively in a module-level JS variable (`token.ts`) — never localStorage/sessionStorage (D-06; threat T-02-18).
- Login submits URL-encoded form data (`username=email`, `password`) to match the FastAPI `OAuth2PasswordRequestForm`.
- Concurrent 401s serialized via a single `isRefreshing` flag + `failedQueue` to prevent refresh-rotation self-logout (Pitfall 4; T-02-21).
- Role assignment is single-select (seed has `admin` + `user`); multi-role assignment deferred.
- Deactivation uses a destructive shadcn `Dialog`, not `confirm()`; the UI gate is convenience only — the backend `require_permission("users:manage")` 403 is the real authz boundary (T-02-20).

## Deviations from Plan

No deviations **within this plan's own commits** — the three tasks executed as written. The shadcn CLI mis-emitted generated component files into a literal `frontend/@/` directory (alias-resolution quirk); files were copied to `src/components/ui/` and the stray `frontend/@/` directory was gitignored (commit `8109019`). Missing transitive shadcn deps (`class-variance-authority`, `@radix-ui/react-slot`, `@radix-ui/react-dropdown-menu`) were installed to make the components compile (Rule 3 — blocking).

### Cross-plan fixes (separate commits, NOT part of this plan)

During checkpoint verification, deploy-time defects in the **Phase-2 backend** were discovered and fixed in their own commits (attributed to the originating plans, not 02-04):

1. **`2ae8ebd` fix(02-01):** added the `email-validator` dependency and documented the required auth env vars (`JWT_SECRET`, `BNS_ADMIN_EMAIL`, `BNS_ADMIN_PASSWORD`) in `.env.example`. Without these the API failed to start / seed.
2. **`272db33` fix(02-03):** switched the admin-seed startup to `AsyncAttrs` + `awaitable_attrs` to resolve a `MissingGreenlet` error when loading role permissions during seed.

Additionally, deployment required:
- Rebuilding the **production container image** (the Containerfile builds the SPA inside the image, so the new frontend had to be baked in), and
- Adding `DEBUG=true` to `.env` so the refresh cookie's `Secure` flag is off over plain `http://localhost` (otherwise the cookie is not stored/sent in dev-over-http).

## Issues Encountered

- shadcn CLI alias mis-resolution (files emitted to `frontend/@/`) — resolved by copying into `src/components/ui/` and gitignoring the artifact dir.
- Backend startup `MissingGreenlet` in the admin seed — fixed cross-plan in `272db33`.
- Missing `email-validator` and undocumented auth env vars blocked first boot — fixed cross-plan in `2ae8ebd`.

## Known Follow-ups (deferred — do NOT block phase)

1. **No in-app navigation shell / logout control** linking Landing <-> `/admin/users`. Navigation is route-driven only. Deferred to the app-shell phase per ROADMAP (CORE-06..08).
2. **No DB-backed regression test for the admin-seed/startup path.** Seed tests skip without a live DB, which is why the `MissingGreenlet` slipped past unit tests. Recommend adding a seed integration test (live/throwaway DB) during gap-closure so startup-path defects are caught automatically.

## Next Phase Readiness

- CORE-02/03/04/05 are user-visible and operator-verified end-to-end on the production container.
- Phase 3 (App Shell & Settings) can build navigation + logout on top of the `ProtectedRoute` guard and `useAuth` session hook delivered here.
- The `apiClient` + silent-refresh + in-memory token primitives are reusable by every later module's frontend.

## Self-Check: PASSED

Files verified (created):
- frontend/src/auth/token.ts: FOUND
- frontend/src/api/client.ts: FOUND
- frontend/src/hooks/useAuth.ts: FOUND
- frontend/src/components/ProtectedRoute.tsx: FOUND
- frontend/src/routes/Login.tsx: FOUND
- frontend/src/routes/admin/Users.tsx: FOUND
- frontend/src/components/ui/dropdown-menu.tsx: FOUND
- frontend/src/auth/ProtectedRoute.test.tsx, Login.test.tsx, Users.test.tsx: FOUND
- frontend/src/test-setup.ts: FOUND

Commits verified:
- 3b40b95: feat(02-04) axios client + interceptor + token + useAuth + ProtectedRoute — FOUND
- f28cfd8: feat(02-04) Login page + App routing — FOUND
- 748d641: feat(02-04) Admin User Management screen — FOUND
- 8109019: chore(02-04) gitignore shadcn artifact dir — FOUND
- 2ae8ebd: fix(02-01) email-validator + env docs (cross-plan) — FOUND
- 272db33: fix(02-03) awaitable_attrs seed fix (cross-plan) — FOUND

Verification: 12 component tests pass; `npx tsc --noEmit` clean; human-verify checkpoint passed in a real browser on the production container.

Only the two deferred follow-ups remain, both out of this plan's scope.

---
*Phase: 02-authentication-users*
*Completed: 2026-06-25*
