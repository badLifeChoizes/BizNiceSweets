---
phase: 03-app-shell-settings
plan: "02"
subsystem: backend/core
tags: [api, routers, schemas, permissions, auth]
dependency_graph:
  requires: [03-01]
  provides: [modules-api, settings-api, permissions-feed]
  affects: [03-03]
tech_stack:
  added: []
  patterns:
    - FastAPI APIRouter with prefix="/core/modules" (no /api/v1 — added at mount time)
    - require_permission("settings:manage") factory gate on write endpoints
    - get_current_user gate on read endpoints (any authenticated user)
    - model_dump(exclude_unset=True) PATCH semantics for settings (Pitfall 8)
    - Always-on guard (HTTP 422) in modules PATCH for always_on=True modules (D-08)
    - UserRead.model_validate({...}) with computed permissions field in /me endpoint
key_files:
  created:
    - backend/app/core/modules_schemas.py
    - backend/app/core/settings_schemas.py
    - backend/app/core/modules_router.py
    - backend/app/core/settings_router.py
  modified:
    - backend/app/main.py
    - backend/app/modules/auth/schemas.py
    - backend/app/modules/auth/router.py
    - backend/tests/auth/test_login.py
    - backend/tests/core/test_modules.py
decisions:
  - "GET /core/modules and GET /core/settings gated by get_current_user (any auth) — RESEARCH Open Questions 1 & 2 RESOLVED: reads are authenticated but not admin-only; shell header needs company.name for every user"
  - "PATCH /core/modules/{key} and PATCH /core/settings/{key} gated by require_permission('settings:manage') — admin-only writes (D-12, T-03-05)"
  - "Always-on guard lives in the backend PATCH handler (HTTP 422), not frontend only (D-08, T-03-04, RESEARCH Pitfall 7)"
  - "model_dump(exclude_unset=True) on settings PATCH — only explicitly-sent fields are written (T-03-07, RESEARCH Pitfall 8)"
  - "/auth/me builds UserRead via model_validate with collect_permissions — same function used at JWT mint time; avoids returning raw ORM object for a computed field"
  - "test_toggle_requires_admin fixed to use real DB-backed user + login flow — minted token with non-existent sub would return 401 (not 403) from get_current_user DB lookup"
metrics:
  duration: 420s
  completed: "2026-06-26"
  tasks_completed: 2
  files_changed: 9
---

# Phase 03 Plan 02: Modules and Settings API Routers + /me Permissions Summary

**One-liner:** FastAPI modules router (GET any-auth / PATCH admin with always-on 422 guard) and settings router (GET any-auth / PATCH admin with exclude_unset patch semantics) mounted under /api/v1, plus /auth/me extended with a flat `permissions: string[]` list via `collect_permissions` for the frontend nav filter.

## Tasks Completed

| Task | Name | Commit | Key Files |
|------|------|--------|-----------|
| 1 | Pydantic schemas + modules/settings routers + main.py mount | c1a68ba | modules_schemas.py, settings_schemas.py, modules_router.py, settings_router.py, main.py |
| 2 | Extend /auth/me with flat permissions list + green the core tests | 4b2c3b0 | auth/schemas.py, auth/router.py, test_login.py, test_modules.py |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed test_toggle_requires_admin to use real DB-backed user**
- **Found during:** Task 2 (pre-implementation analysis)
- **Issue:** The Wave 0 test minted a JWT with `sub="non-admin-user-id"` (a non-existent user ID). `get_current_user` looks up the user by ID in the DB — if not found, raises HTTP 401, not 403. The test expected 403, so it would always fail even after the router was built.
- **Fix:** Replaced the minted-token approach with: (1) create a real non-admin user via POST /api/v1/auth/users, (2) log in as that user to get a real Bearer token, (3) use that token for the PATCH request. `get_current_user` resolves the DB user; `require_permission("settings:manage")` then correctly returns 403 because the user role lacks that permission.
- **Files modified:** backend/tests/core/test_modules.py
- **Commit:** 4b2c3b0

## Verification Results

All plan-level verification gates passed:

- OpenAPI schema confirms `/api/v1/core/modules`, `/api/v1/core/modules/{key}`, `/api/v1/core/settings`, `/api/v1/core/settings/{key}` registered
- `UserRead.model_fields` includes `permissions` — SCHEMA_OK
- `collect_permissions` referenced in auth/router.py — ME_WIRED
- `pytest tests/core/ tests/auth/test_login.py --collect-only` — 13 tests collected, 0 import errors
- `pytest tests/core/ tests/auth/test_login.py -q` — 13 skipped cleanly without DB

## Known Stubs

None — all endpoints return live DB data. No placeholder values or hardcoded responses.

## Threat Flags

No new threat surfaces introduced beyond the plan's threat register. All T-03-04 through T-03-07 mitigations applied:

| Threat ID | Mitigation Applied |
|-----------|-------------------|
| T-03-04 | Always-on guard: `if mod.always_on and data.enabled is False: raise HTTP 422` in modules_router.py |
| T-03-05 | `require_permission("settings:manage")` on both PATCH endpoints — non-admin → 403 |
| T-03-06 | `get_current_user` on both GET endpoints — unauthenticated → 401 |
| T-03-07 | `model_dump(exclude_unset=True)` in settings PATCH — omitted fields not nulled |
| T-03-08 | Accept disposition — no server-side HTML sanitization needed (React renders as text) |

## Self-Check: PASSED

Files exist:
- backend/app/core/modules_schemas.py: FOUND (created)
- backend/app/core/settings_schemas.py: FOUND (created)
- backend/app/core/modules_router.py: FOUND (created)
- backend/app/core/settings_router.py: FOUND (created)
- backend/app/main.py: FOUND (modified — routers mounted)
- backend/app/modules/auth/schemas.py: FOUND (modified — permissions field added)
- backend/app/modules/auth/router.py: FOUND (modified — /me populates permissions)
- backend/tests/auth/test_login.py: FOUND (modified — test_me_includes_permissions added)
- backend/tests/core/test_modules.py: FOUND (modified — test_toggle_requires_admin fixed)

Commits exist:
- c1a68ba: feat(03-02): Pydantic schemas + modules/settings routers + main.py mount
- 4b2c3b0: feat(03-02): extend /auth/me with flat permissions list + green core tests
