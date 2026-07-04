---
phase: 03-app-shell-settings
reviewed: 2026-06-26T00:00:00Z
depth: standard
files_reviewed: 27
files_reviewed_list:
  - backend/alembic/versions/0003_add_modules_settings_tables.py
  - backend/app/core/models.py
  - backend/app/core/modules_model.py
  - backend/app/core/modules_router.py
  - backend/app/core/modules_schemas.py
  - backend/app/core/modules_seed.py
  - backend/app/core/seed.py
  - backend/app/core/settings_model.py
  - backend/app/core/settings_router.py
  - backend/app/core/settings_schemas.py
  - backend/app/core/settings_seed.py
  - backend/app/main.py
  - backend/app/modules/auth/router.py
  - backend/app/modules/auth/schemas.py
  - backend/app/modules/auth/seed.py
  - backend/tests/core/conftest.py
  - backend/tests/core/test_modules.py
  - backend/tests/core/test_settings.py
  - backend/tests/auth/test_login.py
  - frontend/src/App.tsx
  - frontend/src/main.tsx
  - frontend/src/components/AppShell.tsx
  - frontend/src/components/Sidebar.tsx
  - frontend/src/components/Topbar.tsx
  - frontend/src/components/MobileSidebar.tsx
  - frontend/src/hooks/useAuth.ts
  - frontend/src/hooks/useModules.ts
  - frontend/src/hooks/useSettings.ts
  - frontend/src/routes/Home.tsx
  - frontend/src/routes/admin/Modules.tsx
  - frontend/src/routes/admin/Settings.tsx
findings:
  critical: 0
  warning: 5
  info: 4
  total: 9
status: issues_found
---

# Phase 3: Code Review Report

**Reviewed:** 2026-06-26T00:00:00Z
**Depth:** standard
**Files Reviewed:** 27 (3 read-only context source files reviewed plus 27 changed source files in scope)
**Status:** issues_found

## Summary

Phase 3 delivers a well-structured backend data/API layer and a React app-shell with sensibly placed authorization gates. The security-critical invariants the review brief flagged are correctly implemented and provably present in the source:

- **Always-on guard** (`modules_router.py:78`) rejects `enabled=False` on always-on modules with HTTP 422 at the backend, not just the UI — Pitfall 7 avoided.
- **Write endpoints** (`PATCH /core/modules`, `PATCH /core/settings`) are gated by `require_permission("settings:manage")`; reads are gated by `get_current_user` (any-auth) per the resolved open questions. `settings:manage` is correctly excluded from `_USER_ROLE_PERMS` (admin-only).
- **Partial unique index** `uq_settings_global ... WHERE owner_id IS NULL` is present in both the ORM model and migration 0003 — the PostgreSQL NULL-uniqueness pitfall is handled correctly.
- **`exclude_unset`** PATCH semantics on settings prevent omitted-field clobbering.
- **Company name** renders as escaped React text (no `innerHTML`), so the legacy XSS concern does not apply in the shell.

No BLOCKER/Critical defects were found. The issues below are quality and robustness defects: a React Rules-of-Hooks violation that will fail lint, a missing frontend authz guard on admin routes (defense-in-depth — the backend is the real gate, so not a true bypass), an optimistic-UI race in the Modules toggle, and a flaky-ordering assumption in a test. All should be fixed but none block correctness of the security model.

## Warnings

### WR-01: `useVisibleModules` violates the Rules of Hooks (called after conditional early returns)

**File:** `frontend/src/components/AppShell.tsx:36,66`
**Issue:** The function is named with the `use` prefix (`useVisibleModules`), which marks it as a React Hook to both ESLint's `react-hooks/rules-of-hooks` plugin and to human readers. It is then **called after two conditional early returns** (`if (isLoading) return ...` at line 54, `if (!user) return ...` at line 62), and is also called inside `Home.tsx:23` after a guard. Calling a hook conditionally/after early return is a Rules-of-Hooks violation that the linter will flag and that is genuinely unsafe for any real hook. At runtime it happens not to crash only because the function is actually pure (it calls no hooks internally) — the `use` name is a lie. This is fragile: any future maintainer who adds a `useMemo`/`useState` inside it (a natural thing to do given the name) will introduce a real conditional-hook crash.
**Fix:** Rename it to a plain helper so it is not treated as a hook, and keep it pure:
```tsx
// AppShell.tsx
export function getVisibleModules(user: AuthUser | null, modules: ModuleRecord[]): ModuleRecord[] {
  if (!user) return []
  return modules.filter((mod) => {
    if (!mod.enabled) return false
    if (user.roles.some((r) => r.name === 'admin')) return true
    return user.permissions.includes(`${mod.key}:read`)
  })
}
// callers:
const visibleModules = getVisibleModules(user, modules)   // AppShell.tsx & Home.tsx
```

### WR-02: Admin-only frontend routes have no route-level role guard

**File:** `frontend/src/App.tsx:21-24`
**Issue:** `/settings`, `/settings/modules`, and `/admin/users` are nested under `AppShell`, which only enforces *authentication* (`if (!user) Navigate to /login`). There is no *authorization* (admin-role) guard on these routes. Any authenticated non-admin who types `/settings` into the URL bar lands on the fully-rendered Settings form: `GET /core/settings` is any-auth, so the form populates with live company/locale values, and the user can edit fields and click Save. The write `PATCH` is backend-gated (403) so no data is mutated — this is **not** a true authorization bypass — but it presents a broken/forbidden admin surface to non-admins, leaking the existence and current values of admin settings and producing confusing failed-save toasts. The Topbar correctly hides the admin menu items for non-admins (`Topbar.tsx:45,119`), but direct navigation bypasses that UX gate.
**Fix:** Add an admin-guard layout route (or per-route check) around the admin routes so non-admins are redirected to `/`:
```tsx
function RequireAdmin() {
  const { user } = useAuth()
  if (user && !user.roles.some((r) => r.name === 'admin')) return <Navigate to="/" replace />
  return <Outlet />
}
// in App.tsx, wrap the three admin routes:
<Route element={<RequireAdmin />}>
  <Route path="/settings" element={<Settings />} />
  <Route path="/settings/modules" element={<Modules />} />
  <Route path="/admin/users" element={<Users />} />
</Route>
```

### WR-03: Modules toggle clears ALL optimistic overrides on every success, racing concurrent toggles

**File:** `frontend/src/routes/admin/Modules.tsx:117,124,128`
**Issue:** `localOverrides` is a single shared map and `onSuccess` runs `setLocalOverrides({})` — wiping every pending override, not just the one that resolved. With two quick toggles (toggle PLUM off, then FLAN off before PLUM's PATCH resolves), PLUM's success callback clears FLAN's optimistic override while FLAN's request is still in flight, causing FLAN's Switch to visually snap back to the server value mid-flight until its own request resolves and the query refetches. Compounding this, `pendingKey` is a single string (`useState<string | null>`), so only one row can show pending state at a time — a second concurrent toggle clears the first row's pending indicator. The optimistic UI is built as if only one toggle can ever be in flight, but nothing enforces that (rows are independently clickable).
**Fix:** Key the optimistic state and pending state per-module and clear only the resolved key:
```tsx
onSuccess: (_data, variables) => {
  void queryClient.invalidateQueries({ queryKey: ['core', 'modules'] })
  setLocalOverrides((prev) => { const n = { ...prev }; delete n[variables.key]; return n })
  setPendingKeys((prev) => { const n = new Set(prev); n.delete(variables.key); return n })
},
```
(Replace the single `pendingKey` string with a `Set<string>` of pending keys, and `isPending={pendingKeys.has(mod.key)}`.)

### WR-04: Failed-login audit test relies on unordered SELECT returning newest row last

**File:** `backend/tests/auth/test_login.py:149-157`
**Issue:** The test selects all `auth.login_failed` rows with no `ORDER BY`, then asserts on `rows_after[-1]` ("the latest row"). PostgreSQL gives no ordering guarantee for a `SELECT` without `ORDER BY`; the row returned last is not guaranteed to be the most recently inserted, especially against a shared test DB with rows accumulated from prior runs. This test can pass or fail nondeterministically depending on heap/scan order. Because it asserts `actor_id is None` and *all* failed-login rows legitimately have `actor_id is None`, it happens to be robust today — but the `[-1]` "latest row" intent is unsound and will break the moment a differently-shaped failed-login row is introduced.
**Fix:** Order explicitly by the audit log's primary key / timestamp:
```python
result = await session.execute(
    select(AuditLog).where(AuditLog.action == "auth.login_failed").order_by(AuditLog.id)
)
```

### WR-05: Settings PATCH accepts and persists arbitrary `value` strings with no validation against `value_type`

**File:** `backend/app/core/settings_router.py:58-91`, `backend/app/core/settings_schemas.py:34-41`
**Issue:** `update_setting` writes whatever `value: Optional[str]` the admin sends to any existing global setting key, with no validation that the value conforms to the row's declared `value_type` (e.g. `locale.currency` is `"str"` but conceptually an ISO-4217 code; `locale.units` should be `metric|imperial`). An admin can set `locale.timezone` to `"not a tz"` or `locale.units` to `"furlongs"`, and downstream consumers (PLUM costing, SYERP — explicitly named in D-11 as future readers of these locale defaults) will silently ingest invalid config. For a medical-device-origin project where these defaults feed costing/measurement, persisting unvalidated locale config is a latent data-integrity defect. This is admin-only so it is not an attacker surface, but it is a correctness gap.
**Fix:** Add per-key value validation in the PATCH handler (or a Pydantic validator keyed off `value_type`), e.g. reject unknown timezones / non-enumerated units with a 422, mirroring the enumerated option lists already hardcoded client-side in `Settings.tsx` (`UNITS_OPTIONS`, `TIMEZONE_OPTIONS`). At minimum, validate `locale.units ∈ {metric, imperial}` and `locale.currency` against an ISO-4217 set on the server, since the client whitelist is not an enforcement boundary.

## Info

### IN-01: Modules PATCH commits and refreshes even for a no-op request body

**File:** `backend/app/core/modules_router.py:84-89`
**Issue:** When `data.enabled is None` (empty PATCH body `{}`), the handler makes no mutation but still runs `await db.commit()` and `await db.refresh(mod)`, issuing unnecessary DB round-trips and returning 200 for a no-op. Minor inefficiency and a slightly surprising 200-on-noop contract.
**Fix:** Early-return the current state (or 422) when no actionable field is supplied; only commit when a field actually changed.

### IN-02: `User` lucide import and hidden `<User>` icon in Topbar are dead code

**File:** `frontend/src/components/Topbar.tsx:18,100`
**Issue:** `User` is imported from lucide-react and rendered as `<User className="h-4 w-4 hidden" aria-hidden="true" />` — permanently `hidden`, never displayed. It is dead UI and an unused-render. The avatar uses text initials instead.
**Fix:** Remove the `User` import and the hidden `<User>` element.

### IN-03: `pytest` imported but unused in core/auth test modules

**File:** `backend/tests/core/test_modules.py:15`, `backend/tests/core/test_settings.py:18`, `backend/tests/auth/test_login.py:14`
**Issue:** `import pytest` appears at module top but `pytest` is never referenced (no `pytest.mark`, `pytest.raises`, etc.) in these files. Unused import.
**Fix:** Remove the unused `import pytest` lines, or add the `# noqa: F401` if kept intentionally for fixture collection ergonomics.

### IN-04: Settings `getSettingValue` falls back to `''` for an existing setting whose value is genuinely `null`

**File:** `frontend/src/routes/admin/Settings.tsx:78-80,113`
**Issue:** `getSettingValue` returns `''` for both "key not present" and "value is null" (e.g. seeded `company.logo_url` has `value=null`). The save-diff at line 113 compares form state (`''`) against `getSettingValue` (`''`) so a null-valued setting never appears changed — generally fine for the v1 fields shown, but means a field could never be explicitly cleared back to null through this form, and conflates "unset" with "empty string". Not a defect for the current four locale fields + company name, but a latent ambiguity if a nullable field is ever surfaced in this form.
**Fix:** Track the original `null` vs `''` distinction if/when a nullable setting (logo_url, address) is added to the form; for v1 this is acceptable as-is.

---

_Reviewed: 2026-06-26T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
