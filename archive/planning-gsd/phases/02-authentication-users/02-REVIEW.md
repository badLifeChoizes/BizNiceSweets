---
phase: 02-authentication-users
reviewed: 2026-06-25T19:07:15Z
depth: standard
files_reviewed: 32
files_reviewed_list:
  - backend/app/core/base.py
  - backend/app/core/config.py
  - backend/app/core/models.py
  - backend/app/core/seed.py
  - backend/app/main.py
  - backend/alembic/versions/0002_add_auth_tables.py
  - backend/app/modules/auth/__init__.py
  - backend/app/modules/auth/dependencies.py
  - backend/app/modules/auth/models.py
  - backend/app/modules/auth/router.py
  - backend/app/modules/auth/schemas.py
  - backend/app/modules/auth/seed.py
  - backend/app/modules/auth/service.py
  - backend/tests/conftest.py
  - backend/tests/auth/conftest_helpers.py
  - backend/tests/auth/test_hashing.py
  - backend/tests/auth/test_login.py
  - backend/tests/auth/test_rbac.py
  - backend/tests/auth/test_refresh.py
  - backend/tests/auth/test_refresh_rotation.py
  - backend/tests/auth/test_seed_admin.py
  - backend/tests/auth/test_service_unit.py
  - backend/tests/auth/test_user_admin.py
  - frontend/src/api/client.ts
  - frontend/src/auth/token.ts
  - frontend/src/hooks/useAuth.ts
  - frontend/src/components/ProtectedRoute.tsx
  - frontend/src/routes/Login.tsx
  - frontend/src/routes/admin/Users.tsx
  - frontend/src/App.tsx
  - frontend/src/auth/Login.test.tsx
  - frontend/src/auth/ProtectedRoute.test.tsx
  - frontend/src/auth/Users.test.tsx
findings:
  critical: 2
  warning: 8
  info: 4
  total: 14
status: issues_found
---

# Phase 2: Code Review Report

**Reviewed:** 2026-06-25T19:07:15Z
**Depth:** standard
**Files Reviewed:** 32
**Status:** issues_found

## Summary

The auth implementation is well-structured and the core cryptographic primitives are sound: Argon2id via `pwdlib`, HS256 JWT decode with an explicit `algorithms=[...]` allowlist (algorithm-confusion safe), constant-time `DUMMY_HASH` for user-enumeration resistance, refresh-token rotation with family-wide reuse detection, in-memory access-token storage on the client, and an httpOnly/secure/SameSite refresh cookie scoped to the refresh path. Secrets are correctly typed `SecretStr`. RBAC `require_permission` + admin wildcard logic is correct and well-tested at the unit level.

However, there are two BLOCKER-level defects. First, a frontend/backend API contract mismatch: the admin UI sends `role_name` while the backend schema field is `role`, so Pydantic silently discards the role and **no role is ever assigned or changed through the admin UI** — the headline feature of this screen is non-functional and no test catches it. Second, an undocumented diagnostic endpoint (`/auth/_rbac_probe`) is mounted in the production router with no environment guard, increasing attack surface. Beyond those, several robustness gaps (unhandled duplicate-email 500, no password policy, no self-/last-admin-lockout guard, multi-commit non-atomic audit writes) should be addressed.

The test suite is solid but has a blind spot: every admin-mutation test sends the correct `role`/`full_name` JSON shape directly, so it never exercises the actual frontend payload — which is why the contract mismatch slipped through.

## Critical Issues

### CR-01: Admin UI sends `role_name`/`password`/`full_name` but backend schema expects `role` — role assignment silently dropped

**File:** `frontend/src/routes/admin/Users.tsx:101-121`, `frontend/src/routes/admin/Users.tsx:236-251`; backend `backend/app/modules/auth/schemas.py:39-65`

**Issue:** The frontend `CreatePayload`/`UpdatePayload` and the `createUser`/`updateUser` helpers send a `role_name` field:

```ts
interface CreatePayload { email; full_name; password; role_name }
function createUser(payload) { return apiClient.post('/api/v1/auth/users', payload) ... }
```

But the backend Pydantic schemas define the field as `role`:

```python
class UserCreate(BaseModel):
    email: EmailStr
    password: str
    full_name: Optional[str] = None
    role: Optional[str] = None   # ← not "role_name"

class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    is_active: Optional[bool] = None
    role: Optional[str] = None   # ← not "role_name"
```

Pydantic ignores unknown fields by default, so `role_name` is silently dropped. Result: creating a user from the UI always produces a user with **no role** (no permissions), and editing a user's role from the UI is a **no-op** — the primary function of the Users screen does not work. The backend integration tests (`test_admin_create_user`, `test_admin_assign_role`) send `role`/JSON directly and never go through the frontend helper, so the mismatch is invisible to the test suite. The frontend `Users.test.tsx` only asserts rendering, never the mutation payload shape.

This is a correctness/data-integrity blocker: provisioned users land in an unintended permission state.

**Fix:** Rename the frontend fields to match the backend contract (preferred — keep the backend schema as the source of truth):

```ts
interface CreatePayload { email: string; full_name: string; password: string; role: string }
interface UpdatePayload { user_id: string; full_name?: string; is_active?: boolean; role?: string }

function createUser(payload: CreatePayload): Promise<User> {
  return apiClient.post<User>('/api/v1/auth/users', payload).then((r) => r.data)
}
```

And update the two `.mutate({...})` call sites in `handleSaveChanges` (and `role_name: formRole` → `role: formRole`). Then add a test that asserts the exact JSON body sent to `apiClient.post`/`apiClient.patch` so the contract is locked.

### CR-02: Diagnostic `/auth/_rbac_probe` endpoint shipped in the production router with no environment guard

**File:** `backend/app/modules/auth/router.py:347-361`

**Issue:** The `_rbac_probe` endpoint is registered unconditionally on the production `router`. The docstring itself says it is "test/diagnostic only" and "may be removed once SYERP endpoints exist," but nothing prevents it from being exposed in production. It is reachable at `/api/v1/auth/_rbac_probe` by any user holding `syerp:read`. While it leaks little data today, shipping undocumented diagnostic endpoints into a security-sensitive auth surface is an attack-surface and audit-trail defect (a probe endpoint that is gated but unlogged, and not part of the documented API contract). For a medical-device-origin product with a first-class audit/traceability posture, an unaudited diagnostic route in the auth module is a release blocker.

**Fix:** Either remove the endpoint and have `test_rbac.py` gate a real route, or guard registration behind `settings.debug`:

```python
if settings.debug:
    @router.get("/_rbac_probe")
    async def rbac_probe(current_user=Depends(require_permission("syerp:read"))) -> dict:
        return {"probe": "ok", "permission": "syerp:read"}
```

so it never mounts in a production (non-debug) deployment.

## Warnings

### WR-01: Duplicate-email user creation raises an unhandled IntegrityError (HTTP 500)

**File:** `backend/app/modules/auth/service.py:358-390`, router `backend/app/modules/auth/router.py:260-288`

**Issue:** `create_user` inserts a `User` and `await db.commit()`s with no handling for a unique-constraint violation on `email` (the column is `unique=True`). Submitting an already-registered email yields an unhandled `sqlalchemy.exc.IntegrityError` → opaque HTTP 500 instead of a clean 4xx. This is both a UX defect and a minor information/availability concern (a 500 with a DB traceback is worse than a controlled 409).

**Fix:** Pre-check for an existing email (or catch `IntegrityError` and roll back), returning a 409:

```python
existing = await get_user_by_email(db, email)
if existing is not None:
    raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")
```

### WR-02: No password policy / minimum length on user creation or admin seed

**File:** `backend/app/modules/auth/schemas.py:39-45`, `backend/app/modules/auth/seed.py:120-128`

**Issue:** `UserCreate.password` is a bare `str` with no minimum length or complexity constraint, and the seeded admin password (`BNS_ADMIN_PASSWORD`) is accepted verbatim with no floor. An admin can create accounts with empty or trivially weak passwords (the test suite uses `"pass123"`). For an auth module this is a meaningful hardening gap.

**Fix:** Enforce a minimum length in the schema, e.g.:

```python
from pydantic import Field
class UserCreate(BaseModel):
    password: str = Field(min_length=12)
```

and document/validate a minimum for `BNS_ADMIN_PASSWORD` at startup.

### WR-03: No guard against deactivating the last admin or self-deactivation — lockout risk

**File:** `backend/app/modules/auth/service.py:393-449`, router `backend/app/modules/auth/router.py:291-339`

**Issue:** `update_user` lets any `users:manage` holder set `is_active=False` (or replace roles) on any account, including the only admin or the acting admin themselves. Deactivating the last admin permanently locks the installation out of user management (recovery is a manual DB/seed operation). For a self-hosted single-tenant product this is a realistic foot-gun.

**Fix:** Before deactivating or removing the admin role from a user, count remaining active admins and reject the operation if it would drop to zero; optionally reject self-deactivation explicitly:

```python
if is_active is False and str(user_id) == str(acting_admin.id):
    raise HTTPException(status_code=400, detail="You cannot deactivate your own account")
```

### WR-04: Audit-trail writes are committed in separate transactions from the action they record (non-atomic)

**File:** `backend/app/modules/auth/router.py:108-151` (login), `260-339` (create/update); `backend/app/modules/auth/service.py:313-342` (`write_audit`)

**Issue:** `write_audit`, `store_refresh_token`, `create_user`, and `update_user` each call `await db.commit()` independently. In the login handler, for example, the refresh token is committed, then a *separate* commit writes the success audit row. If the second commit fails, the session is authenticated but the audit row is missing — and vice-versa for the create/update handlers where the entity is committed before its audit row. For a product whose CLAUDE.md calls audit trail and traceability "first-class concerns," the action and its audit record should be atomic.

**Fix:** Make the audit insert part of the same transaction as the action (`db.add(audit_row)` without an intermediate commit, then a single commit), or wrap the handler body in one transaction. At minimum, have `write_audit` only `db.add()` and let the caller own the single commit.

### WR-05: `update_user` docstring claims refresh tokens are "deleted" on deactivation, but they are revoked

**File:** `backend/app/modules/auth/service.py:402-435`

**Issue:** The docstring states "the user's RefreshToken rows are deleted to immediately end all active sessions," but the implementation sets `rt.revoked = True` (soft-revoke), it does not delete. The behavior (revoke) is correct and matches the tests; the docstring is wrong. Misleading docs on a security control invite future regressions (someone may "fix" it to actually delete, breaking the family-reuse-detection audit chain).

**Fix:** Update the docstring to say the live refresh tokens are *revoked* (not deleted), consistent with the rotation/reuse-detection design that relies on revoked rows remaining queryable.

### WR-06: `rotate_refresh_token` expiry comparison can break on offset-aware DB timestamps; also old token left revoked-without-replacement on inactive user

**File:** `backend/app/modules/auth/service.py:254-290`

**Issue:** Two robustness concerns:
(a) The expiry guard normalizes only `tzinfo is None` to UTC. If the DB returns an offset-aware datetime in a non-UTC zone the comparison still works, but if `expires_at` were ever read as naive *local* time (driver/config dependent) the `replace(tzinfo=utc)` assumption is wrong and could let an expired token through or reject a valid one. Prefer an explicit conversion.
(b) When the resolved user is `None`/inactive, the old token has already been set `revoked = True` and is committed — correct for security, but worth noting the function commits a partial state then raises 401; ensure no caller assumes the row is untouched on failure.

**Fix:** Normalize defensively with `expires = expires.astimezone(timezone.utc) if expires.tzinfo else expires.replace(tzinfo=timezone.utc)` and add a unit test for an expired-token row to lock the boundary behavior.

### WR-07: Failed-login audit detail records the submitted email verbatim — log-injection / PII surface

**File:** `backend/app/modules/auth/router.py:111-118`

**Issue:** On a failed login the audit `detail` is `f"Failed login attempt for email: {form_data.username}"`, storing the raw, attacker-controlled `username` value. An attacker can submit arbitrary strings (newlines, control chars, very long values up to no enforced bound since `detail` is `Text`) that land in the audit log, enabling log-injection/log-forging and unbounded growth from brute-force enumeration. The value is also unvalidated (not necessarily an email).

**Fix:** Truncate/normalize the stored value (e.g. cap length, strip control characters) before persisting, and consider hashing or partially masking the attempted identifier in failure records.

### WR-08: Frontend silent-refresh redirects with a hard `window.location.href = '/login'`, discarding in-memory token and intended-destination state

**File:** `frontend/src/api/client.ts:94-99`

**Issue:** On refresh failure the interceptor does `clearAccessToken()` then `window.location.href = '/login'`. The hard navigation triggers a full page reload (losing React state and the `from` location that `ProtectedRoute` carefully preserves via `Navigate state={{ from: location }}`), so the post-login "return to where you were" UX is defeated whenever a session expires mid-use. It also bypasses the SPA router.

**Fix:** Surface the auth failure to the app (e.g. clear the token and let `useAuth`/`ProtectedRoute` redirect via React Router, preserving `location`), rather than forcing a full document navigation.

## Info

### IN-01: Unused import `Request`/`Response` symbols and inline late imports in handlers

**File:** `backend/app/modules/auth/router.py:209-211`, `310-312`

**Issue:** `logout` and `update_user_endpoint` perform function-local imports (`import hashlib`, `from app.modules.auth.models import User as UserModel`, `from sqlalchemy import select as sa_select`) instead of module-level imports already present elsewhere in the file (`select` is already imported at module scope, line 30). This is inconsistent and adds noise.

**Fix:** Hoist these to the existing module-level imports; reuse the already-imported `select`.

### IN-02: `was_active_before` pre-fetch in `update_user_endpoint` duplicates a query `update_user` already performs

**File:** `backend/app/modules/auth/router.py:308-323`

**Issue:** The handler runs an extra `SELECT` to read `is_active` before calling `update_user`, which itself re-selects the same user. This is a redundant round-trip purely to choose the audit action label.

**Fix:** Have `update_user` return whether the active state transitioned (or the prior value) so the handler can label the audit action without a second query.

### IN-03: `RoleRead` schema omits permission codes despite docstring claiming "flattened permission codes"

**File:** `backend/app/modules/auth/schemas.py:73-80`

**Issue:** The `RoleRead` docstring says "Role data with flattened permission codes," but the model only exposes `id`, `name`, `description` — there is no `permissions` field. Docstring and shape disagree; UI consumers cannot see a role's permissions through this schema.

**Fix:** Either add a `permissions: List[str]` field (and populate it) or correct the docstring to match the actual fields.

### IN-04: `import uuid` at top of `service.py` is unused

**File:** `backend/app/modules/auth/service.py:24`

**Issue:** `uuid` is imported in `service.py` but the module never references it (UUID generation for refresh-token families happens in the router via `uuid.uuid4()`; the service uses `secrets`/`hashlib`). Dead import.

**Fix:** Remove the unused `import uuid` from `service.py`.

---

_Reviewed: 2026-06-25T19:07:15Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
