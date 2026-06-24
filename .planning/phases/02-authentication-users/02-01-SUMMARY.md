---
phase: 02-authentication-users
plan: "01"
subsystem: backend/auth
tags: [auth, jwt, argon2, rbac, alembic, tdd]
dependency_graph:
  requires:
    - 01-project-scaffolding-deployment (Base, registry, seed hook, settings pattern)
  provides:
    - app.modules.auth (module package, registered under /api/v1/auth)
    - auth ORM models (User, Role, Permission, RefreshToken, AuditLog)
    - auth service helpers (hash_password, verify_password, create_access_token, decode_access_token, new_refresh_token)
    - Alembic migration 0002_add_auth_tables (all 7 auth tables)
    - Wave 0 test harness (tests/auth/ — 9 passing, 14 skipped, 2 xfail stubs)
  affects:
    - backend/app/core/config.py (Settings extended with auth fields)
    - backend/app/core/models.py (auth models import added)
    - backend/app/main.py (auth module import + run_seeds startup hook)
    - backend/tests/conftest.py (JWT_SECRET, BNS_ADMIN_EMAIL, BNS_ADMIN_PASSWORD injection)
tech_stack:
  added:
    - pyjwt==2.13.0 (JWT encode/decode, HS256)
    - pwdlib[argon2]==0.3.0 (Argon2id password hashing)
  patterns:
    - Module self-registration via registry.register() (mirrors syerp pattern)
    - SecretStr for jwt_secret + bns_admin_password (extends existing postgres_password discipline)
    - lazy="selectin" on User.roles and Role.permissions (async SQLAlchemy greenlet-safe)
    - SHA-256 of opaque token stored in DB, never the raw token (T-02-04)
    - algorithms=["HS256"] list in decode_access_token (T-02-02 algorithm-confusion mitigation)
    - DUMMY_HASH for constant-time authentication when user not found
    - TDD RED→GREEN: test_hashing.py written before service.py; all 7 hashing tests pass
key_files:
  created:
    - backend/app/modules/auth/__init__.py
    - backend/app/modules/auth/models.py
    - backend/app/modules/auth/service.py
    - backend/app/modules/auth/schemas.py
    - backend/app/modules/auth/router.py
    - backend/alembic/versions/0002_add_auth_tables.py
    - backend/tests/auth/__init__.py
    - backend/tests/auth/test_hashing.py
    - backend/tests/auth/test_login.py
    - backend/tests/auth/test_refresh.py
    - backend/tests/auth/test_refresh_rotation.py
    - backend/tests/auth/test_user_admin.py
    - backend/tests/auth/test_rbac.py
    - backend/tests/auth/test_seed_admin.py
  modified:
    - backend/requirements.txt (pyjwt + pwdlib pins added)
    - backend/app/core/config.py (auth settings fields added)
    - backend/app/core/models.py (auth models import added)
    - backend/app/main.py (auth module import + run_seeds lifespan hook)
    - backend/tests/conftest.py (JWT_SECRET, BNS_ADMIN_EMAIL, BNS_ADMIN_PASSWORD injected)
decisions:
  - "Used pyjwt==2.13.0 + pwdlib[argon2]==0.3.0 (not python-jose/passlib — both have CVEs/abandoned per RESEARCH.md)"
  - "jwt_secret field reads JWT_SECRET env var (pydantic-settings upcases field name); bns_admin_password reads BNS_ADMIN_PASSWORD — consistent with existing postgres_password pattern"
  - "Alembic migration written by hand (no live DB at plan time); structure matches ORM models exactly; upgrade head applies on podman-compose up"
  - "test_rbac.py includes 2 passing unit tests (permission payload assertions) + 2 xfail integration stubs"
  - "lazy='selectin' on User.roles and Role.permissions (mandatory for async SQLAlchemy — RESEARCH.md Pitfall 1)"
metrics:
  duration_seconds: 704
  completed_date: "2026-06-23"
  tasks_completed: 3
  tasks_total: 3
  files_created: 14
  files_modified: 5
---

# Phase 02 Plan 01: Auth Foundation — Summary

**One-liner:** PyJWT + Argon2id (pwdlib) auth foundation with 7-table RBAC schema, Wave 0 TDD harness, and Alembic migration 0002.

## Completed Tasks

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Add security deps and extend config | 068aaa1 | requirements.txt, core/config.py |
| 2 | Auth models, service helpers, schemas, and module registration (TDD RED→GREEN) | 8f7e47c (RED), 2018f8b (GREEN) | auth/*, core/models.py, main.py, conftest.py |
| 3 | Alembic migration + Wave 0 test harness | 66b6a88 | alembic/versions/0002_add_auth_tables.py, tests/auth/* |

## What Was Built

Auth foundation for Phase 2. Every later plan in the phase (02-02 login/refresh, 02-03 admin CRUD + seed, 02-04 frontend) builds on these contracts.

**Security library selection:** Replaced the older tutorial combination (python-jose + passlib) with the FastAPI-recommended stack (PyJWT 2.13.0 + pwdlib[argon2] 0.3.0). python-jose has 4 CVEs including algorithm confusion (CVE-2024-33663); passlib is abandoned and incompatible with bcrypt ≥ 4.1 and Python 3.13.

**ORM models (7 tables):**
- `User` — UUID-string PK, unique+indexed email, Argon2id hash, is_active flag, timestamps
- `Role` — int PK, unique name, description
- `Permission` — int PK, unique+indexed `module:action` code
- `user_roles` + `role_permissions` — M2M association tables (no mapped class)
- `RefreshToken` — SHA-256 token hash (not raw), family for chain revocation, revoked flag
- `AuditLog` — append-only audit trail (actor_id, action, target_type, target_id, detail)

`lazy="selectin"` is set on `User.roles` and `Role.permissions` — mandatory for SQLAlchemy 2.0 async to avoid MissingGreenlet errors.

**Service helpers (service.py):**
- `hash_password` / `verify_password` via Argon2id (OWASP-safe defaults from `PasswordHash.recommended()`)
- `DUMMY_HASH` for constant-time user-not-found path (timing-attack prevention)
- `create_access_token(subject, permissions)` → HS256 JWT with `sub`, `exp`, `perms` payload
- `decode_access_token(token)` → always passes `algorithms=["HS256"]` as a list (not string — CVE class prevention T-02-02)
- `new_refresh_token()` → `(raw, sha256_hex)` via `secrets.token_urlsafe(32)` + `hashlib.sha256`

**Alembic migration:** 0002_add_auth_tables — single revision chained off 0001 (existing history). Written manually (no live DB at plan time); structurally verified against ORM models. `alembic upgrade head` applies on next `podman-compose up`.

**Wave 0 test harness:**
- `test_hashing.py` — 7 fully passing unit tests (hashing round-trip, JWT encode/decode, algorithm allowlist, refresh-token entropy/hash)
- `test_login.py`, `test_refresh.py`, `test_refresh_rotation.py` — xfail stubs (plan 02-02)
- `test_user_admin.py`, `test_rbac.py`, `test_seed_admin.py` — xfail stubs (plan 02-03); test_rbac.py includes 2 passing unit tests
- Full collection: `9 passed, 14 skipped, 2 xfailed` — no import or collection errors

**Module registration:** `auth/__init__.py` mirrors the syerp pattern exactly; `main.py` now calls `importlib.import_module("app.modules.auth")` and runs `run_seeds(db)` in the lifespan startup block.

**Settings extended:**
- `jwt_secret: SecretStr` — reads `JWT_SECRET` env var (pydantic-settings field-name convention; consistent with postgres_password reading POSTGRES_PASSWORD)
- `bns_admin_password: SecretStr` — reads `BNS_ADMIN_PASSWORD`
- `access_token_expire_minutes: int = 15`, `refresh_token_expire_days: int = 7`
- `bns_admin_email: str = "admin@example.com"`, `signup_enabled: bool = False`, `debug: bool = False`

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Env var name mismatch for JWT secret**
- **Found during:** Task 2 (RED test phase) — conftest injected `BNS_JWT_SECRET` but pydantic-settings maps field `jwt_secret` to env var `JWT_SECRET` (no BNS_ prefix for that field)
- **Issue:** Plan comment said env `BNS_JWT_SECRET` but pydantic-settings reads `JWT_SECRET` for the `jwt_secret` field (consistent with how `postgres_password` reads `POSTGRES_PASSWORD`)
- **Fix:** Updated conftest to inject `JWT_SECRET`; updated config.py comment to reflect the actual env var name; `bns_admin_email` and `bns_admin_password` correctly read `BNS_ADMIN_EMAIL` and `BNS_ADMIN_PASSWORD` because their field names carry the `bns_` prefix
- **Files modified:** backend/tests/conftest.py, backend/app/core/config.py
- **Commit:** 8f7e47c (part of RED test commit)

**2. [Rule 3 - Blocking] Alembic autogenerate requires live DB**
- **Found during:** Task 3 — `alembic revision --autogenerate` requires a live PostgreSQL connection to compare against existing schema
- **Issue:** No live DB available in the development environment at plan time
- **Fix:** Wrote the migration manually, deriving it directly from the ORM models defined in models.py. The plan explicitly states "the migration file existence is the deliverable" and "skip upgrade gracefully if no DB". All 7 tables with correct columns, constraints, indexes, and FKs are present.
- **Files modified:** backend/alembic/versions/0002_add_auth_tables.py (created manually)
- **Commit:** 66b6a88

## TDD Gate Compliance

- RED gate: `test(02-01)` commit `8f7e47c` — test_hashing.py created before service.py; all 7 tests failed with `ModuleNotFoundError`
- GREEN gate: `feat(02-01)` commit `2018f8b` — service.py + all auth module files created; all 7 tests pass

## Known Stubs

- `backend/app/modules/auth/router.py` — minimal importable router with no endpoints; login/refresh/logout/me/users endpoints added in plans 02-02 and 02-03. This is intentional per plan scope.
- `backend/app/core/seed.py:run_seeds()` — still calls no-op; `seed_admin_user` import is wired in plan 02-03. The lifespan startup hook in main.py is already in place.

## Threat Flags

No new security surface beyond what the plan's threat model covers. All T-02-01 through T-02-05 mitigations are implemented:
- T-02-01: jwt_secret + bns_admin_password as SecretStr, accessed only via .get_secret_value()
- T-02-02: decode_access_token passes algorithms=["HS256"] as a list
- T-02-03: Argon2id via pwdlib; plaintext never persisted; DUMMY_HASH for constant-time path
- T-02-04: token_hash String(64) in RefreshToken stores SHA-256, not raw token
- T-02-05: pyjwt==2.13.0 + pwdlib[argon2]==0.3.0 pinned; python-jose and passlib excluded

## Self-Check: PASSED

Files verified:
- backend/app/modules/auth/__init__.py: FOUND
- backend/app/modules/auth/models.py: FOUND
- backend/app/modules/auth/service.py: FOUND
- backend/app/modules/auth/schemas.py: FOUND
- backend/app/modules/auth/router.py: FOUND
- backend/alembic/versions/0002_add_auth_tables.py: FOUND
- backend/tests/auth/test_hashing.py: FOUND (7 tests pass)
- backend/tests/auth/test_login.py: FOUND
- backend/tests/auth/test_refresh.py: FOUND
- backend/tests/auth/test_refresh_rotation.py: FOUND
- backend/tests/auth/test_user_admin.py: FOUND
- backend/tests/auth/test_rbac.py: FOUND
- backend/tests/auth/test_seed_admin.py: FOUND

Commits verified:
- 068aaa1: feat(02-01): add pyjwt/pwdlib deps and extend Settings with auth fields
- 8f7e47c: test(02-01): add failing test for auth service helpers (RED)
- 2018f8b: feat(02-01): implement auth models, service helpers, schemas, and module registration
- 66b6a88: feat(02-01): add Wave 0 test harness and auth tables Alembic migration
