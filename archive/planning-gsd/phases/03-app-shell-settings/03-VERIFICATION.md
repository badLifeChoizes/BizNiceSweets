---
phase: 03-app-shell-settings
verified: 2026-06-26T00:00:00Z
status: passed
score: 4/4 must-haves verified
overrides_applied: 0
---

# Phase 03: App Shell & Settings Verification Report

**Phase Goal:** Users see a coherent application with navigation, and admins can configure system-wide settings and which modules are active.
**Verified:** 2026-06-26
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | After login, user sees a navigation shell listing all enabled modules and can switch between them | VERIFIED | `AppShell.tsx` wraps all protected routes; `Sidebar.tsx` renders `NavLink` per visible module from `useModules`; `App.tsx` has `<Route element={<AppShell />}>` wrapping all protected routes including `/`; human-verify checkpoint APPROVED |
| 2 | Admin can update system settings (company name, defaults) and changes persist across sessions | VERIFIED | `Settings.tsx` PATCHes `/api/v1/core/settings/{key}` for each changed field; `settings_router.py` writes to DB via `setattr` with `exclude_unset=True`; invalidates `['core','settings']`; Topbar reads `company.name` from `useSettings()`; human-verify checkpoint confirmed persistence after reload |
| 3 | Admin can toggle a module off, and its nav entry disappears for all users immediately | VERIFIED | `Modules.tsx` sends `PATCH /api/v1/core/modules/{key}` then `invalidateQueries(['core','modules'])`; `useModules` has `staleTime: 10_000` and `refetchOnWindowFocus: true`; sidebar reads from the same `['core','modules']` query key; human-verify checkpoint confirmed PLUM nav disappears after toggle |
| 4 | Admin can re-enable a module and it reappears in the navigation shell | VERIFIED | Same toggle mechanism as SC-3 — `PATCH { enabled: true }` + cache invalidation; `useVisibleModules` in `AppShell.tsx` filters on `mod.enabled`; human-verify checkpoint confirmed PLUM reappears |

**Score:** 4/4 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `backend/app/core/modules_model.py` | Module ORM model | VERIFIED | `class Module(Base)` with `key` (string PK), `display_name`, `enabled`, `always_on`, `sort_order`; 33 lines, substantive |
| `backend/app/core/settings_model.py` | Setting ORM model with partial unique index | VERIFIED | `class Setting(Base)` with surrogate int PK, all 7 columns; `Index("uq_settings_global"...)` in `__table_args__`; 57 lines |
| `backend/alembic/versions/0003_add_modules_settings_tables.py` | DDL for modules + settings tables | VERIFIED | `revision="0003"`, `down_revision="0002"`; creates both tables; `uq_settings_global` partial unique index with `postgresql_where=sa.text("owner_id IS NULL")`; proper `downgrade()` |
| `backend/app/core/modules_seed.py` | Idempotent 7-suite seed | VERIFIED | `_MODULE_SEEDS` with exactly 7 tuples; SYERP has `always_on=True`; select-before-insert idempotent; `enabled=True` explicitly mapped |
| `backend/app/core/settings_seed.py` | 6 default settings seed | VERIFIED | `_DEFAULT_SETTINGS` with `company.name`, `company.logo_url`, `locale.currency`, `locale.date_format`, `locale.timezone`, `locale.units`; filters on `key` AND `owner_id.is_(None)` |
| `backend/app/core/seed.py` | run_seeds() wired | VERIFIED | Calls `seed_modules_table(db)` and `seed_default_settings(db)` after `seed_admin_user(db)` |
| `backend/app/core/modules_router.py` | GET + PATCH module endpoints | VERIFIED | GET gated by `get_current_user`; PATCH gated by `require_permission("settings:manage")`; 422 guard on `always_on and data.enabled is False` |
| `backend/app/core/settings_router.py` | GET + PATCH settings endpoints | VERIFIED | GET gated by `get_current_user` (any auth); PATCH gated by `require_permission("settings:manage")`; `model_dump(exclude_unset=True)` applied |
| `backend/app/core/modules_schemas.py` | ModuleRead, ModuleUpdate | VERIFIED | `ModuleRead` with `from_attributes`; `ModuleUpdate(enabled: Optional[bool])` |
| `backend/app/core/settings_schemas.py` | SettingRead, SettingUpdate | VERIFIED | `SettingRead` with `from_attributes`; `SettingUpdate(value: Optional[str])` |
| `backend/app/modules/auth/schemas.py` | UserRead with permissions | VERIFIED | `permissions: List[str] = []` field present in `UserRead`; confirmed via `python -c "from app.modules.auth.schemas import UserRead; print(list(UserRead.model_fields))"` → includes `permissions` |
| `backend/tests/core/test_modules.py` | 4 contract tests | VERIFIED | `test_list_modules_returns_enabled_flag`, `test_toggle_module`, `test_cannot_disable_always_on`, `test_toggle_requires_admin` — all collected (7 core tests total) |
| `backend/tests/core/test_settings.py` | 3 contract tests | VERIFIED | `test_seed_defaults`, `test_list_settings_admin`, `test_update_setting` — collected; skip cleanly without DB |
| `backend/tests/auth/test_login.py` | `test_me_includes_permissions` | VERIFIED | Test exists; asserts `"permissions"` key present in `/me` response and is a list; admin has `"*"` in list |
| `frontend/src/components/ui/switch.tsx` | shadcn Switch primitive | VERIFIED | File exists at correct path; 27-line substantive Radix-based Switch component |
| `frontend/src/hooks/useModules.ts` | useModules query | VERIFIED | `queryKey: ['core', 'modules']`; `staleTime: 10_000`; `refetchOnWindowFocus: true`; real API call to `/api/v1/core/modules` |
| `frontend/src/hooks/useSettings.ts` | useSettings query | VERIFIED | `queryKey: ['core', 'settings']`; real API call to `/api/v1/core/settings` |
| `frontend/src/hooks/useAuth.ts` | AuthUser with permissions | VERIFIED | `permissions: string[]` in `AuthUser` interface |
| `frontend/src/components/AppShell.tsx` | Layout-route shell with auth guard | VERIFIED | 95 lines; auth guard (Loader2 spinner / Navigate to /login / Outlet); `useVisibleModules` filter; `mod.enabled AND (admin OR permissions.includes)` |
| `frontend/src/components/Sidebar.tsx` | NavLink per visible module | VERIFIED | Uses `NavLink` with `isActive` classes; `bg-accent text-accent-foreground` active; `text-muted-foreground hover:bg-muted` inactive; no `window.location` comparison |
| `frontend/src/components/Topbar.tsx` | Company name + user menu + logout | VERIFIED | `useSettings()` for company name (any-auth); `aria-label="Open user menu"`; admin-only items gated on `user.roles.some(r => r.name === 'admin')`; logout POSTs `/api/v1/auth/logout` then `clearAccessToken()` then `window.location.href = '/login'` |
| `frontend/src/components/MobileSidebar.tsx` | Sheet drawer | VERIFIED | `Sheet` with `side="left"`, `className="w-64 p-0"`; wraps `<Sidebar>`; controlled by AppShell state |
| `frontend/src/routes/Home.tsx` | Neutral landing + empty state | VERIFIED | "Welcome to BizNiceSweets" / "Select a module from the sidebar to get started." (D-06); empty state "No modules available" / "No modules are enabled..." (D-05) |
| `frontend/src/routes/admin/Settings.tsx` | Settings form with persistence | VERIFIED | Two Cards (Company Identity + Locale Defaults); "Save Settings" button; PATCHes changed settings only; invalidates `['core','settings']`; success/error toasts via sonner |
| `frontend/src/routes/admin/Modules.tsx` | Module toggle table | VERIFIED | `Table` with `display_name`, status Badge, `Switch`; SYERP Switch `disabled={true}` with tooltip; toggle mutation invalidates `['core','modules']`; 422/403 snap-back + toasts |
| `frontend/src/App.tsx` | Routes through AppShell | VERIFIED | `<Route element={<AppShell />}>` wrapping `/`, `/settings`, `/settings/modules`, `/admin/users` |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `backend/app/core/models.py` | `Module, Setting` | `from app.core.modules_model import Module` / `from app.core.settings_model import Setting` | WIRED | Both imports present with `# noqa: F401`; Alembic discovers both tables |
| `backend/app/core/seed.py` | `seed_modules_table, seed_default_settings` | `await seed_modules_table(db)` / `await seed_default_settings(db)` | WIRED | Both calls present after `seed_admin_user(db)` |
| `backend/app/main.py` | `modules_router, settings_router` | `app.include_router(modules_router, prefix="/api/v1")` | WIRED | Both routers mounted before SPA catch-all; confirmed via OpenAPI schema: `/api/v1/core/modules` and `/api/v1/core/settings` registered |
| `backend/app/modules/auth/router.py` | `collect_permissions` | `/me` endpoint calls `collect_permissions(current_user)` and returns `UserRead` with permissions | WIRED | `collect_permissions` imported at top of file; `/me` endpoint uses `UserRead.model_validate({..., "permissions": collect_permissions(current_user)})` |
| `frontend/src/components/Sidebar.tsx` | `useModules + useAuth` | Props from `AppShell.useVisibleModules(user, modules)` | WIRED | `AppShell` calls both hooks; passes `visibleModules` to `Sidebar` |
| `frontend/src/routes/admin/Modules.tsx` | `['core', 'modules']` query | `invalidateQueries({ queryKey: ['core', 'modules'] })` on success | WIRED | Exact string match with `useModules` query key |
| `frontend/src/App.tsx` | `AppShell` | `<Route element={<AppShell />}>` replacing `ProtectedRoute` | WIRED | Confirmed in `App.tsx` |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `Sidebar.tsx` | `visibleModules` | `useModules()` → GET `/api/v1/core/modules` → DB `select(Module).order_by(Module.sort_order)` | Yes — live DB query | FLOWING |
| `Topbar.tsx` | `companyName` | `useSettings()` → GET `/api/v1/core/settings` → DB `select(Setting).where(owner_id IS NULL)` | Yes — live DB query | FLOWING |
| `Modules.tsx` | `modules` | `useModules()` → same DB path as Sidebar | Yes | FLOWING |
| `Settings.tsx` | `settings` | `useSettings()` → same DB path as Topbar | Yes | FLOWING |
| `AppShell.tsx` | `user` | `useAuth()` → GET `/api/v1/auth/me` → `collect_permissions(current_user)` | Yes — live DB session lookup | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| OpenAPI schema confirms route registration | `python -c "from app.main import app; schema = app.openapi(); print(list(schema['paths'].keys()))"` | `/api/v1/core/modules`, `/api/v1/core/modules/{key}`, `/api/v1/core/settings`, `/api/v1/core/settings/{key}` all present | PASS |
| UserRead.permissions field exists | `python -c "from app.modules.auth.schemas import UserRead; print(list(UserRead.model_fields))"` | `['id', 'email', 'full_name', 'is_active', 'roles', 'permissions']` | PASS |
| models.py registers both tables in Base.metadata | `python -c "import app.core.models; from app.core.base import Base; print(sorted(Base.metadata.tables))"` | `['modules', 'settings']` (only these two — confirmed table names correct) | PASS |
| Core test suite collects 7 tests cleanly | `python -m pytest tests/core/ --collect-only -q` | 7 tests collected, 0 import errors | PASS |
| Core test suite skips cleanly without DB | `python -m pytest tests/core/ -q` | `7 skipped in 0.08s` | PASS |
| Full test suite: 31 pass, 47 skip, 0 fail | `python -m pytest tests/ -q` | `31 passed, 47 skipped, 17 warnings` | PASS |
| Frontend TypeScript clean | `cd frontend && npx tsc --noEmit` | No output, exit 0 | PASS |

### Probe Execution

No conventional `scripts/*/tests/probe-*.sh` probes declared for this phase. Behavioral spot-checks above cover the equivalent verification.

### Requirements Coverage

| Requirement | Source Plan(s) | Description | Status | Evidence |
|-------------|----------------|-------------|--------|----------|
| CORE-06 | 03-01, 03-02, 03-03 | Admin can configure system settings (company info, defaults) | SATISFIED | `settings_model.py` + `settings_seed.py` (6 defaults) + `settings_router.py` (GET/PATCH) + `Settings.tsx` form (two Cards, PATCH on save, persistence) |
| CORE-07 | 03-01, 03-02, 03-03 | Admin can enable or disable individual modules | SATISFIED | `modules_model.py` + `modules_seed.py` (7 suites, SYERP always_on) + `modules_router.py` (GET/PATCH with 422 guard) + `Modules.tsx` toggle table + nav refetch via query invalidation |
| CORE-08 | 03-02, 03-03 | User sees a navigation shell listing enabled modules and can switch between them | SATISFIED | `AppShell.tsx` layout route; `Sidebar.tsx` with `NavLink` per enabled-and-permitted module; `useModules` + `useAuth` → `useVisibleModules` intersection; `/auth/me` returns `permissions: string[]` via `collect_permissions`; `test_me_includes_permissions` covers the feed contract |

All three REQUIREMENTS.md entries for Phase 3 are marked `Complete` in the traceability table.

### Anti-Patterns Found

No blocking anti-patterns detected:
- No `TBD`, `FIXME`, or `XXX` markers in any Phase 3 modified file
- No `return null` / empty-array stubs in router handlers — all return live DB queries
- `placeholder` occurrences in `Settings.tsx` are legitimate HTML `placeholder` attribute values for loading states, not code stubs
- No `font-medium` class in any of the four chrome components (verified by inspection — all use `font-semibold` or `font-normal` per UI-SPEC)
- No `window.location` comparison in `Sidebar.tsx` — uses `NavLink isActive` as required

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| — | — | None found | — | — |

### Human Verification Required

No items require human verification.

The Phase 03 plan 03-03 included a `checkpoint:human-verify` task (Task 4) which was performed by the user and APPROVED prior to submission for goal-backward verification. The human checkpoint covered:
- In-shell Home landing visible after login
- Admin user menu showing Settings/Modules/Users entries
- Settings persistence (company name change persisted after reload; topbar updated)
- Module toggle propagation (PLUM nav disappeared, then reappeared)
- SYERP "Always On" badge and disabled Switch with tooltip
- Active nav item highlighting
- Mobile drawer on narrow screens
- Logout redirecting to /login
- Non-admin user sees company name in topbar (settings GET is any-auth)
- Non-admin user menu shows only Log out

### Deferred Items

**Noted follow-up (not a phase-goal gap):** The production `frontend/dist` is still the Phase-1 build. The Phase-3 UI was verified via the Vite dev server on `:5173`. A `frontend/dist` rebuild and container image rebuild are required before `:8000` production serving reflects Phase 3. This is documented in 03-03-SUMMARY.md and STATE.md. The phase goal concerns app shell + settings + module functionality, which is fully implemented and verified in dev — the stale `dist` is a deployment artifact, not a functional gap.

### Gaps Summary

No gaps. All four success criteria are observably true in the codebase:

1. The navigation shell (AppShell + Sidebar + Topbar + MobileSidebar) wraps all protected routes with a permission-filtered nav that reads live module state from the DB.
2. System settings (company name, locale defaults) are stored in the DB, editable via the Settings screen, and read back into the Topbar and Settings form on reload.
3. Module toggle sends a PATCH to the backend which updates the DB; the sidebar refetches via TanStack Query cache invalidation using the exact same query key (`['core', 'modules']`).
4. Module re-enable uses the identical toggle path; the nav visibility filter (`mod.enabled AND (admin OR permissions.includes)`) causes the entry to reappear.

Backend enforcement is complete: always-on guard (HTTP 422 on SYERP disable), admin-only writes (`settings:manage` permission), and authenticated-only reads (`get_current_user` on GET endpoints). The test suite (7 core contract tests + `test_me_includes_permissions`) skips cleanly without a live DB and encodes the full CORE-06/07/08 contract. 31 non-DB tests pass, 0 failures, 0 collection errors.

---

_Verified: 2026-06-26_
_Verifier: Claude (gsd-verifier)_
