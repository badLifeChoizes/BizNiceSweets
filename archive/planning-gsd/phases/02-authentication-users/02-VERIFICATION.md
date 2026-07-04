---
phase: 02-authentication-users
verified: 2026-06-25T21:00:00Z
status: passed
score: 4/4 must-haves verified
overrides_applied: 0
human_verification_resolved: "Both human items confirmed and user approved 2026-06-25: (1) httpOnly cookie + silent-refresh-on-reload verified by user in the production-container browser session; (2) CR-01 role assignment verified live against the container API (create role=admin -> admin assigned; PATCH user->admin -> role replaced)."
human_verification:
  - test: "Confirm refresh-token cookie is actually HttpOnly in the real browser (DevTools > Application > Cookies) and that page reload keeps the session without re-login"
    expected: "refresh_token cookie shows HttpOnly=true in browser DevTools; no re-login prompt after full page reload"
    why_human: "Cookie HttpOnly attribute and silent-refresh end-to-end behavior cannot be verified programmatically without a running stack. SUMMARY claims human checkpoint passed; context confirms this was done, but the verifier cannot independently observe it."
  - test: "Confirm role-assignment fix (CR-01) is observable end-to-end: create a user with role=admin via the UI, then log in as that user and confirm admin-only routes (GET /api/v1/auth/users) return 200, not 403"
    expected: "New user created with admin role receives 200 on /auth/users; user created without a role (old behavior before fix) would have received 403"
    why_human: "The CR-01 fix is verified at the code level (frontend sends role not role_name; backend schema field matches), but end-to-end role-assignment in the running stack can only be confirmed by a human with DB access or a live browser session."
---

# Phase 2: Authentication & Users Verification Report

**Phase Goal:** Users can securely access the suite and admins can manage who has access to what
**Verified:** 2026-06-25T21:00:00Z
**Status:** passed (human items confirmed; user approved)
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | User can create an account and log in with email/password via OAuth2/JWT | VERIFIED | `POST /auth/login` with `OAuth2PasswordRequestForm`, returns JWT access token + sets httpOnly refresh cookie. Admin provisions accounts via `POST /auth/users`. Argon2id hashing via pwdlib confirmed in `service.py`. |
| 2 | Authenticated session persists across page reloads and API requests without re-login (token refresh) | VERIFIED | Silent-refresh interceptor in `client.ts` POSTs to `/api/v1/auth/refresh` on 401, single-flight via `isRefreshing` flag + `failedQueue`. Backend `rotate_refresh_token` issues a new token + revokes old. Access token held in module-level JS variable (never localStorage). Human checkpoint in SUMMARY confirms reload keeps session. |
| 3 | Admin can create, edit, and deactivate other user accounts from the user management screen | VERIFIED | `GET/POST /auth/users` and `PATCH /auth/users/{id}` exist, gated by `require_permission("users:manage")`. `update_user` with `is_active=False` revokes all live RefreshToken rows (D-05). Frontend `Users.tsx` wired to these endpoints via `useQuery`/`useMutation`. Deactivation uses a destructive `Dialog`, not `confirm()`. |
| 4 | Admin can assign roles to users, and a user with an incorrect role is denied access to gated resources | VERIFIED | CR-01 blocker fixed: `Users.tsx` `CreatePayload`/`UpdatePayload` now sends `role: string` (not `role_name`). Backend `UserCreate`/`UserUpdate` schemas use `role` field. `require_permission()` factory in `dependencies.py` enforces 403 for users lacking the permission code. Admin wildcard (`role.name == "admin"`) grants all permissions. |

**Score:** 4/4 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `backend/app/modules/auth/models.py` | User, Role, Permission, user_roles, role_permissions, RefreshToken, AuditLog ORM models | VERIFIED | All 7 models/tables defined. `lazy="selectin"` on `User.roles` and `Role.permissions` (async greenlet protection). RefreshToken has `family` String(36) indexed, `token_hash` String(64) unique. |
| `backend/app/modules/auth/service.py` | hash_password, verify_password, create_access_token, decode_access_token, new_refresh_token, write_audit, create_user, update_user, list_users | VERIFIED | All helpers present and substantive. `decode_access_token` calls `jwt.decode(..., algorithms=["HS256"])` as a list (algorithm-confusion safe). `DUMMY_HASH` for constant-time user-enumeration resistance. |
| `backend/app/core/config.py` | jwt_secret, token TTLs, admin bootstrap creds, signup_enabled flag | VERIFIED | `jwt_secret: SecretStr` (no default), `bns_admin_password: SecretStr` (no default), `access_token_expire_minutes = 15`, `refresh_token_expire_days = 7`, `signup_enabled: bool = False`, `debug: bool = False`. All SecretStr fields use `.get_secret_value()` pattern. |
| `backend/app/modules/auth/router.py` | POST /login, POST /refresh, POST /logout, GET /me, GET+POST /users, PATCH /users/{id}, GET /_rbac_probe | VERIFIED | All endpoints exist. CR-02 fix confirmed: `_rbac_probe` raises HTTP 404 when `not settings.debug`. All `/users` routes gated by `require_permission("users:manage")`. |
| `backend/app/modules/auth/dependencies.py` | get_current_user, require_permission factory | VERIFIED | `get_current_user` decodes JWT, loads user, checks `is_active`. `require_permission` factory checks admin wildcard and per-code permissions, raises 403 on failure. |
| `backend/app/modules/auth/seed.py` | seed_admin_user — idempotent first-admin + role/permission bootstrap | VERIFIED | Upserts 5 permissions, 2 roles, assigns permissions idempotently, creates admin from env. `awaitable_attrs` pattern used for async role loading (MissingGreenlet fix). Writes AuditLog only on first creation. |
| `backend/app/core/seed.py` | run_seeds() calls seed_admin_user | VERIFIED | `run_seeds` calls `await seed_admin_user(db)`. Hooked from `main.py` lifespan. |
| `backend/app/core/models.py` | Aggregates auth models for Alembic autogenerate | VERIFIED | Contains `from app.modules.auth import models as auth_models`. |
| `backend/app/main.py` | importlib.import_module("app.modules.auth"); lifespan runs seeds | VERIFIED | `importlib.import_module("app.modules.auth")` present. Lifespan calls `run_seeds(db)` on startup. |
| `backend/alembic/versions/0002_add_auth_tables.py` | Single migration creating all 7 auth tables | VERIFIED | File exists. Creates users, roles, permissions, user_roles, role_permissions, refresh_tokens, audit_log in `upgrade()`. Correct foreign keys, indexes, `token_hash` unique index. |
| `frontend/src/auth/token.ts` | In-memory access token (no localStorage/sessionStorage) | VERIFIED | Module-level `let _accessToken: string | null = null`. No localStorage/sessionStorage anywhere in the file. |
| `frontend/src/api/client.ts` | axios instance, withCredentials, Bearer request interceptor, single-flight 401 silent-refresh | VERIFIED | `axios.create({ withCredentials: true })`. Request interceptor attaches Bearer. Response interceptor: `isRefreshing` flag + `failedQueue`, POSTs to `/api/v1/auth/refresh` on 401, retries original request. |
| `frontend/src/hooks/useAuth.ts` | /auth/me session query (retry:false, 5-min staleTime) | VERIFIED | `useQuery` against `/api/v1/auth/me`, `retry: false`, `staleTime: 5 * 60_000`. Returns `{ user, isLoading }`. |
| `frontend/src/components/ProtectedRoute.tsx` | Auth guard layout route | VERIFIED | `isLoading` → Loader2 spinner; no user → `<Navigate to="/login" state={{ from: location }} replace />`; else `<Outlet />`. |
| `frontend/src/routes/Login.tsx` | Login page per UI-SPEC Screen 1 | VERIFIED | Centered Card, Email/Password with Eye/EyeOff toggle, "Sign In"/"Signing in…" states, inline error copy, no "Create account"/"Forgot password" links (D-01/D-13). Submits as OAuth2 form data. |
| `frontend/src/routes/admin/Users.tsx` | Admin User Management table + create/edit sheet + deactivate dialog | VERIFIED | Full Name/Email/Role(s)/Status/Actions table, debounced search, accent "Create User" button (sole accent), right-side Sheet with role Select, destructive Dialog with exact copy, Activate/Deactivate actions. |
| `frontend/src/App.tsx` | Public /login + ProtectedRoute-wrapped / and /admin/users | VERIFIED | `/login` is public; `/` and `/admin/users` wrapped in `<Route element={<ProtectedRoute />}>`. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `ProtectedRoute.tsx` | `/auth/me` | `useAuth` → `apiClient.get` | WIRED | `useAuth` calls `apiClient.get('/api/v1/auth/me')`, result drives redirect or Outlet |
| `client.ts` | `/api/v1/auth/refresh` | 401 response interceptor | WIRED | On 401 + not already retried, posts to `/api/v1/auth/refresh` with `withCredentials` |
| `Users.tsx` | `/api/v1/auth/users` | `useQuery`/`useMutation` via `apiClient` | WIRED | `fetchUsers` → `apiClient.get('/api/v1/auth/users')`, create/update mutations post/patch same path |
| `Login.tsx` | `/api/v1/auth/login` | `apiClient.post` with form data | WIRED | `loginRequest` posts URL-encoded form data; on success calls `setAccessToken` |
| `backend/app/main.py` | `app.modules.auth` | `importlib.import_module` | WIRED | `importlib.import_module("app.modules.auth")` triggers `__init__.py` which calls `registry.register()` |
| `backend/app/core/seed.py` | `auth.seed.seed_admin_user` | `run_seeds()` lifespan | WIRED | `run_seeds` imports and awaits `seed_admin_user(db)`; called from `main.py` lifespan startup |
| `/auth/users` (router) | `require_permission("users:manage")` | `Depends()` | WIRED | All three `/users` endpoints have `acting_admin=Depends(require_permission("users:manage"))` |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `Users.tsx` | `users` (user list) | `useQuery` → `apiClient.get('/api/v1/auth/users')` → `list_users(db)` → `SELECT * FROM users` | Yes — `list_users` executes `select(User)` against live DB | FLOWING |
| `Users.tsx` | `createMutation` | `createUser` → `apiClient.post('/api/v1/auth/users', {email, full_name, password, role})` → `create_user(db, ...)` → DB insert | Yes — real DB insert with Argon2id hashed password | FLOWING |
| `Users.tsx` | `updateMutation` | `updateUser` → `apiClient.patch('/api/v1/auth/users/{id}', {role})` → `update_user(db, ...)` → DB update | Yes — real DB update, revokes refresh tokens on deactivate | FLOWING |
| `Login.tsx` | `mutation` | `loginRequest` → `apiClient.post('/api/v1/auth/login', formData)` → `authenticate_user(db, ...)` → `SELECT FROM users WHERE email=...` | Yes — real DB lookup with Argon2id verification | FLOWING |

### Behavioral Spot-Checks

Step 7b: SKIPPED for runnable checks (no live stack available during verification). Human checkpoint in 02-04-SUMMARY.md documents that Task 4 was executed against the production container with all 8 verification steps confirmed passing.

### Probe Execution

Step 7c: No `scripts/*/tests/probe-*.sh` files declared in phase plans or SUMMARY. SKIPPED.

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| CORE-02 | 02-01, 02-02, 02-04 | User can create an account and log in via OAuth2/JWT authentication | SATISFIED | `POST /auth/login` (OAuth2PasswordRequestForm), JWT issued, admin-provisioned account creation at `POST /auth/users`. Login page wired and tested. |
| CORE-03 | 02-02, 02-04 | User session persists securely across requests (token issuance + refresh) | SATISFIED | Two-token model (15-min access + 7-day refresh), rotation with reuse detection, httpOnly cookie, silent-refresh interceptor confirmed. |
| CORE-04 | 02-03, 02-04 | Admin can create, edit, and deactivate user accounts | SATISFIED | `GET/POST /auth/users`, `PATCH /auth/users/{id}` gated by `users:manage`. Deactivation revokes refresh tokens. Frontend admin screen wired. |
| CORE-05 | 02-01, 02-03 | Admin can assign roles to users, and roles gate access to modules and actions | SATISFIED | `require_permission()` factory enforces 403. Admin wildcard grants all. CR-01 fix: frontend sends correct `role` field. Seed bootstraps admin+user roles with `module:action` permissions. |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `backend/app/modules/auth/router.py` | 209-211, 310-312 | Late in-function imports (`import hashlib`, `from ... import User as UserModel`) | Info | IN-01 from review: inconsistent style; no correctness impact. Open warning from code review. |
| `backend/app/modules/auth/router.py` | 308-323 | Double `SELECT` for `is_active` pre-check in `update_user_endpoint` | Info | IN-02 from review: redundant round-trip to label audit action. Performance micro-issue, no correctness impact. |
| `backend/app/modules/auth/schemas.py` | 73-80 | `RoleRead` docstring claims "flattened permission codes" but exposes only `id`, `name`, `description` | Info | IN-03 from review: docstring and schema disagree. No correctness impact for current consumers. |
| `backend/app/modules/auth/service.py` | 24 | `import uuid` unused in service.py | Info | IN-04 from review: dead import. No correctness impact. |
| `backend/app/modules/auth/service.py` | 402-435 | `update_user` docstring says tokens "deleted" but code soft-revokes (`revoked = True`) | Warning | WR-05 from review: misleading security control doc; behavior is correct but doc could invite wrong future change. Open from review. |
| `backend/app/modules/auth/router.py` | 111-118 | Failed-login audit records raw unvalidated email in `detail` field | Warning | WR-07 from review: log-injection / PII surface. Known open warning from code review; no blocking impact on phase goal. |
| `frontend/src/api/client.ts` | 94-99 | `window.location.href = '/login'` hard navigation on refresh failure | Warning | WR-08 from review: discards React Router state.from, defeating post-login redirect-back UX. Known open warning; does not block auth from working. |

No TBD, FIXME, or XXX debt markers found in any phase-modified files.

### Human Verification Required

#### 1. Silent Refresh + httpOnly Cookie Confirmation

**Test:** In a running stack (`podman compose up` or dev server), log in, open DevTools > Application > Cookies, confirm `refresh_token` has HttpOnly=true. Then hard-reload the page. Confirm no re-login prompt — the session persists.
**Expected:** `refresh_token` cookie shows `HttpOnly: true` (and `Secure: true` in a non-debug production build). Session survives page reload without presenting the login screen.
**Why human:** Cookie attribute inspection and real silent-refresh behavior require a running browser + stack. The SUMMARY's Task 4 checkpoint documents this as PASSED against the production container, but the verifier cannot independently observe it.

#### 2. CR-01 End-to-End Role Assignment

**Test:** Log in as admin, open `/admin/users`, create a new user with role=admin. Log out. Log in as the new user. Open DevTools > Network, navigate to `/admin/users` — confirm `GET /api/v1/auth/users` returns HTTP 200 (not 403). Also test: create a user with role=user and confirm that same user gets 403 on `/auth/users`.
**Expected:** Admin-role user receives 200 on the users list; user-role user receives 403.
**Why human:** The code-level fix (CR-01: `role` not `role_name` in frontend payload) is verified by reading the source. The live behavior of role assignment writing correctly to the DB and controlling access requires a running stack to observe.

### Gaps Summary

No blocking gaps. Both blockers from the code review (CR-01 role field mismatch, CR-02 unguarded diagnostic endpoint) are fixed in the current codebase:

- CR-01: `Users.tsx` sends `role: string` in both `CreatePayload` and `UpdatePayload`; the `handleSaveChanges` mutation passes `role: formRole`. Backend `UserCreate`/`UserUpdate` schemas declare the field as `role`. Field names match.
- CR-02: `_rbac_probe` handler checks `if not settings.debug: raise HTTPException(status_code=HTTP_404_NOT_FOUND)`. In production (`debug=False`) the endpoint is unreachable (returns 404 before the permission check runs).

The 8 warnings and 4 info findings from 02-REVIEW.md remain open but are not phase blockers as documented in the verification context. The two known deferred items (no in-app navigation shell, no DB-backed seed/CRUD regression tests) are correctly scoped to Phase 3 and post-phase gap-closure respectively.

---

_Verified: 2026-06-25T21:00:00Z_
_Verifier: Claude (gsd-verifier)_
