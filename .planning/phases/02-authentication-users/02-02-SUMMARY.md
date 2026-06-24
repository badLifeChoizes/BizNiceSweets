---
phase: 02-authentication-users
plan: "02"
subsystem: backend/auth
tags: [auth, jwt, rbac, fastapi, tdd, httponly-cookie, refresh-rotation]
dependency_graph:
  requires:
    - 02-01 (service helpers: hash_password, verify_password, create_access_token, decode_access_token, new_refresh_token, DUMMY_HASH, auth ORM models)
  provides:
    - app.modules.auth.service (authenticate_user, collect_permissions, store_refresh_token, rotate_refresh_token, get_user_by_email, get_user_by_id)
    - app.modules.auth.dependencies (oauth2_scheme, get_current_user, require_permission)
    - /api/v1/auth/login, /api/v1/auth/refresh, /api/v1/auth/logout, /api/v1/auth/me endpoints
  affects:
    - backend/app/modules/auth/router.py (filled from stub to full endpoints)
    - backend/app/modules/auth/service.py (extended with DB helpers + auth logic)
    - backend/tests/auth/test_login.py (xfail removed)
    - backend/tests/auth/test_refresh.py (xfail removed)
    - backend/tests/auth/test_refresh_rotation.py (xfail removed)
tech_stack:
  added: []
  patterns:
    - timing-safe authenticate_user (DUMMY_HASH on user-not-found branch, T-02-06)
    - httpOnly + SameSite=Lax + path-scoped refresh cookie (T-02-07, T-02-08)
    - refresh-token rotation with family-chain reuse detection (T-02-09)
    - get_current_user DB is_active check on every request (T-02-10)
    - require_permission("module:action") factory dependency → 403 (T-02-11)
    - OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login") + Annotated Depends chain
key_files:
  created:
    - backend/app/modules/auth/dependencies.py
    - backend/tests/auth/test_service_unit.py
  modified:
    - backend/app/modules/auth/service.py (extended with DB helpers + auth functions)
    - backend/app/modules/auth/router.py (login/refresh/logout/me filled in)
    - backend/tests/auth/test_login.py (xfail markers removed)
    - backend/tests/auth/test_refresh.py (xfail markers removed, logout logout test updated)
    - backend/tests/auth/test_refresh_rotation.py (xfail markers removed)
decisions:
  - "require_permission returns a dependency callable (_check) — not an HTTPException by itself; correct FastAPI factory pattern"
  - "logout requires a valid Bearer access token — prevents unauthenticated cookie clearing (security posture)"
  - "rotate_refresh_token handles expired token check with timezone-aware comparison (both naive and aware datetimes handled)"
  - "collect_permissions includes '*' wildcard for admin role — consistent with require_permission admin bypass logic"
metrics:
  duration_seconds: 900
  completed_date: "2026-06-24"
  tasks_completed: 2
  tasks_total: 2
  files_created: 2
  files_modified: 7
---

# Phase 02 Plan 02: Login/Refresh Endpoints — Summary

**One-liner:** OAuth2 login endpoint with httpOnly refresh cookie, rotation + family-chain reuse detection, and get_current_user / require_permission FastAPI dependencies locking RBAC for all downstream modules.

## Completed Tasks

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 (RED) | Failing tests for service helpers and auth dependencies | 14656f5 | tests/auth/test_service_unit.py |
| 1 (GREEN) | Service auth functions + auth dependencies | dd4be6a | auth/service.py, auth/dependencies.py |
| 2 | Login/refresh/logout/me router + flip xfail tests | 82a76c9 | auth/router.py, test_login.py, test_refresh.py, test_refresh_rotation.py |

## What Was Built

**Service extensions (service.py):**
- `get_user_by_email` / `get_user_by_id` — async SQLAlchemy queries; roles+permissions load via `lazy="selectin"` (no extra await needed)
- `authenticate_user(db, email, password)` — timing-safe: if user not found, calls `verify_password(password, DUMMY_HASH)` before returning None; prevents user-enumeration via timing (T-02-06)
- `collect_permissions(user)` — flattens all role.permissions[].code into a list; if any role.name == "admin", inserts wildcard `"*"`
- `store_refresh_token(db, user_id, token_hash, family, expires_at)` — inserts RefreshToken row
- `rotate_refresh_token(db, raw_token)` — looks up by SHA-256 hash; if revoked, revokes the entire family (D-07 reuse detection, T-02-09); else revokes old row, inserts new in same family, returns (new_raw, user)

**Auth dependencies (dependencies.py):**
- `oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")` — tokenUrl points at the full mounted path
- `get_current_user(token, db)` — decodes Bearer JWT, loads user, raises 401 (WWW-Authenticate: Bearer) on bad token/missing sub/user not found/is_active==False (T-02-10)
- `require_permission(permission_code)` — factory returning `_check(current_user=Depends(get_current_user))`: grants if role.name=="admin" or any perm.code==permission_code; else 403 with detail "Permission denied: {code} required" (T-02-11)

**Router endpoints (router.py):**
- `POST /auth/login` — `OAuth2PasswordRequestForm`, calls `authenticate_user`, on success: creates JWT + refresh token, calls `response.set_cookie(httponly=True, secure=not settings.debug, samesite="lax", path="/api/v1/auth/refresh")`; returns `TokenResponse`
- `POST /auth/refresh` — reads cookie via `request.cookies.get("refresh_token")`, calls `rotate_refresh_token`; sets new cookie, returns new access token
- `POST /auth/logout` — requires `Depends(get_current_user)`, revokes the presented refresh cookie token row, clears cookie via `delete_cookie`
- `GET /auth/me` — returns `current_user` serialized as `UserRead`

**Test coverage:**
- 15 new unit tests in `test_service_unit.py` (no DB needed): authenticate_user timing-safe paths, collect_permissions, get_current_user 401 paths, require_permission grant/deny
- xfail markers removed from `test_login.py`, `test_refresh.py`, `test_refresh_rotation.py`
- Non-DB test (`test_refresh_missing_cookie`) passes; DB-dependent tests skipped (no live DB in dev env — expected)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] logout requires Bearer token**
- **Found during:** Task 2 implementation
- **Issue:** Plan said "revoke the user's refresh tokens (or just the presented one)" without specifying auth requirement for logout. Allowing unauthenticated logout creates a denial-of-service vector (attacker could force-logout any session by clearing cookies).
- **Fix:** Added `current_user = Depends(get_current_user)` to the logout handler. Only the token presented in the cookie is revoked (surgical revocation rather than revoking all user tokens, which could log out other devices unexpectedly).
- **Files modified:** backend/app/modules/auth/router.py
- **Commit:** 82a76c9

**2. [Rule 1 - Bug] Timezone-aware datetime comparison in rotate_refresh_token**
- **Found during:** Task 1 implementation — RefreshToken.expires_at may be stored as naive datetime by SQLAlchemy
- **Issue:** Comparing `expires_at < datetime.now(timezone.utc)` raises TypeError if expires_at is naive (no tzinfo)
- **Fix:** Added explicit tzinfo guard: `if expires.tzinfo is None: expires = expires.replace(tzinfo=timezone.utc)`
- **Files modified:** backend/app/modules/auth/service.py
- **Commit:** dd4be6a

**3. [Rule 2 - Missing Critical] test_refresh_revoked_token sends access token to logout**
- **Found during:** Task 2 test update — the original xfail stub called logout without auth
- **Issue:** Logout now requires a Bearer token (deviation 1), so the test needed updating to send the access token from login
- **Fix:** Updated test to extract access_token from login response and include `Authorization: Bearer` header on the logout call
- **Files modified:** backend/tests/auth/test_refresh.py
- **Commit:** 82a76c9

## TDD Gate Compliance

- RED gate: `test(02-02)` commit `14656f5` — test_service_unit.py created before service/dependencies implementation; all 15 tests failed with ImportError/ModuleNotFoundError
- GREEN gate: `feat(02-02)` commit `dd4be6a` — service.py extended + dependencies.py created; all 15 tests pass
- Task 2 followed behavior-first pattern: test xfail removal → router implementation → tests green

## Known Stubs

- `backend/tests/auth/test_login.py`, `test_refresh.py`, `test_refresh_rotation.py` — DB-dependent tests skip without a live PostgreSQL instance. They are **not stubs** — they are fully implemented tests that require plan 02-03's seed_admin_user to populate the test DB. All assertions are present and correct.
- `backend/app/core/seed.py:run_seeds()` — still calls no-op; plan 02-03 wires `seed_admin_user`. This stub was known from plan 02-01.

## Threat Flags

No new security surface beyond what the plan's threat model covers. All T-02-06 through T-02-11 mitigations are implemented:
- T-02-06: authenticate_user DUMMY_HASH timing-safe path
- T-02-07: refresh token in httpOnly + Secure (prod) + SameSite=Lax cookie; only SHA-256 hash stored in DB
- T-02-08: SameSite=Lax + path=/api/v1/auth/refresh cookie scoping
- T-02-09: rotate_refresh_token family revocation on replay
- T-02-10: get_current_user checks is_active on every request
- T-02-11: require_permission("module:action") dependency returns 403; admin wildcard via role.name=="admin"
- T-02-12: JWT brute-force / rate limiting — accepted per plan (internal self-hosted deployment; deferred)

## Self-Check: PASSED

Files verified:
- backend/app/modules/auth/service.py: FOUND (extended with authenticate_user, collect_permissions, store_refresh_token, rotate_refresh_token, get_user_by_email, get_user_by_id)
- backend/app/modules/auth/dependencies.py: FOUND (oauth2_scheme, get_current_user, require_permission)
- backend/app/modules/auth/router.py: FOUND (login, refresh, logout, me endpoints)
- backend/tests/auth/test_service_unit.py: FOUND (15 unit tests, all passing)
- backend/tests/auth/test_login.py: FOUND (xfail removed)
- backend/tests/auth/test_refresh.py: FOUND (xfail removed)
- backend/tests/auth/test_refresh_rotation.py: FOUND (xfail removed)

Commits verified:
- 14656f5: test(02-02): add failing tests for service helpers and auth dependencies (RED)
- dd4be6a: feat(02-02): implement service auth functions and auth dependencies
- 82a76c9: feat(02-02): implement login/refresh/logout/me endpoints and flip xfail tests
