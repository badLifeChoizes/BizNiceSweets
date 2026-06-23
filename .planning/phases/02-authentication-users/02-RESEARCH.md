# Phase 2: Authentication & Users - Research

**Researched:** 2026-06-23
**Domain:** FastAPI JWT auth, SQLAlchemy 2.0 RBAC models, React protected routing, httpOnly cookie session management
**Confidence:** HIGH (core stack verified via Context7 + official docs; library recommendations verified via PyPI + official FastAPI docs)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** No open public self-signup by default. `signup_enabled` flag (default `false`) via pydantic-settings. Accounts are admin-provisioned.
- **D-02:** First admin bootstrapped from environment via `core/seed.py:run_seeds()` calling `seed_admin_user(db)`. Reads `BNS_ADMIN_EMAIL` / `BNS_ADMIN_PASSWORD` from settings as SecretStr. Idempotent — no-op if already exists.
- **D-03:** OAuth2 = FastAPI's `OAuth2PasswordBearer` + `/token` (login) endpoint. Not social/enterprise SSO.
- **D-04:** Two-token model — short-lived access token (~15–30 min stateless JWT) + longer-lived refresh token (~7-day sliding).
- **D-05:** Refresh tokens tracked server-side and revocable. Deactivating a user kills live sessions.
- **D-06:** Access token in JS memory; refresh token in `httpOnly`, `Secure`, `SameSite` cookie. Preferred over localStorage.
- **D-07:** Refresh-token rotation with reuse detection. Planner may simplify to non-rotating revocable tokens if rotation proves heavy.
- **D-08:** Permission-based RBAC — `User` ↔ `Role`, `Role` ↔ `Permission` where permission is a `module:action` string.
- **D-09:** Seed two roles as data: `admin` (wildcard) and `user` (sensible defaults). Not hardcoded enums.
- **D-10:** Enforcement via FastAPI dependency `require_permission("module:action")` returning 403.
- **D-11:** No ABAC / row-level in Phase 2. `module:action` RBAC is the altitude.
- **D-12:** Passwords hashed with a modern KDF. Minimum length floor enforced.
- **D-13:** Recovery is admin-reset-first. Email-based self-service reset is optional, gated behind SMTP config. MFA deferred.
- **D-14:** Minimal auth audit_log table — login success/failure, user create/edit/deactivate, role/permission change. De-scopable to table + hook.

### Claude's Discretion

- Exact JWT library (`pyjwt` vs `python-jose`), hashing lib, and token signing algorithm/secret-rotation approach.
- Exact env-var names for the admin bootstrap and JWT secret.
- Access/refresh token TTLs within the ranges in D-04.
- Whether user↔role is one-to-many or many-to-many at the schema level.
- Frontend auth implementation: protected-route wrapper, TanStack Query auth/session hooks, Axios/fetch interceptor for silent refresh, login page + admin user-management screens.
- CSRF strategy details given the same-origin SPA.
- Cookie attributes / domain specifics for the refresh-token cookie.

### Deferred Ideas (OUT OF SCOPE)

- Third-party / enterprise SSO (Google, GitHub, SAML, OIDC).
- Multi-factor authentication (TOTP, WebAuthn/passkeys).
- Open public self-signup (flag exists, feature deferred).
- Email-based self-service password reset (optional behind SMTP config).
- Full cross-module audit framework (CRISP / later).
- Fine-grained / ABAC authorization.

</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| CORE-02 | User can create an account and log in via OAuth2/JWT authentication | JWT library selection (PyJWT), OAuth2PasswordBearer pattern, `/auth/login` endpoint, admin-provisioned account creation endpoint |
| CORE-03 | User session persists securely across requests (token issuance + refresh) | Two-token model, httpOnly cookie for refresh token, silent-refresh interceptor, RefreshToken server-side table |
| CORE-04 | Admin can create, edit, and deactivate user accounts | User CRUD endpoints, `is_active` flag pattern, deactivation killing sessions (D-05), admin-only permission gate |
| CORE-05 | Admin can assign roles to users, and roles gate access to modules and actions | User↔Role (M2M), Role↔Permission (M2M), `require_permission` FastAPI dependency, seed `admin`/`user` roles as data |

</phase_requirements>

---

## Summary

Phase 2 delivers the auth/identity foundation that every later module sits behind. The FastAPI ecosystem has undergone a notable library shift in 2024–2025: the official FastAPI tutorial now recommends `PyJWT` + `pwdlib[argon2]` over the previously common `python-jose` + `passlib[bcrypt]` combination. Both `python-jose` and `passlib` have known maintenance problems that make them unsuitable for new code — this is a concrete, research-verified finding that changes the dependency list from what older tutorials show.

The core backend pattern is well-established and maps cleanly onto the Phase-1 skeleton: a new `backend/app/modules/auth/` package follows the same `models.py / router.py / schemas.py / service.py` layout as SYERP, self-registers via the existing registry, inherits from `core/base.py:Base`, and produces a single Alembic migration for all five auth tables (`users`, `roles`, `permissions`, `user_roles`, `role_permissions`, `refresh_tokens`, `audit_log`). The `core/seed.py` hook is already named and ready.

On the frontend, React Router v7 (already installed at 7.18.0) provides the protected route pattern via a layout-route + `<Navigate>` redirect. TanStack Query v5 (already installed at 5.101.1) manages the `/auth/me` session query and acts as the source of truth for auth state. The silent-refresh flow uses an Axios response interceptor (or a `fetch` wrapper) to catch 401s, call `/auth/refresh` (which reads the httpOnly cookie automatically), and retry the original request — transparent to TanStack Query.

**Primary recommendation:** Use `PyJWT 2.13.0` + `pwdlib[argon2] 0.3.0`, HS256 signing, two-token model with server-side refresh-token tracking, httpOnly/SameSite=Lax cookie for the refresh token, and the `require_permission("module:action")` FastAPI dependency pattern. This is what the current FastAPI official documentation prescribes.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Login / token issuance | API / Backend | — | Credentials must never be validated client-side; JWT signing key is server-only |
| Access token storage | Browser / Client (JS memory) | — | In-memory prevents XSS persistence; token lives only for page session |
| Refresh token storage | Browser / Client (httpOnly cookie) | — | httpOnly blocks JS access; SameSite=Lax stops CSRF on same-origin SPA |
| Token refresh (silent) | API / Backend + Browser interceptor | — | Backend mints new tokens; frontend interceptor triggers transparently on 401 |
| Session revocation | API / Backend (DB) | — | Server-side refresh token table; deactivating user deletes their rows |
| RBAC enforcement | API / Backend | — | FastAPI dependency on every gated router; no client-side access control decisions |
| Admin user CRUD | API / Backend | Browser / Client (admin UI) | Backend owns the data; frontend provides the management screens |
| Auth audit log | API / Backend (DB) | — | Medical-device posture — immutable server-side record, not browser-visible |
| Password hashing | API / Backend | — | Never client-side; argon2 via pwdlib at write time, verify at login |

---

## Standard Stack

### Core (backend)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `PyJWT` | 2.13.0 | JWT encode/decode, expiry validation | Actively maintained, MIT, the library the FastAPI official docs now use; no CVEs vs python-jose's 4 CVEs in 2024 |
| `pwdlib[argon2]` | 0.3.0 | Password hashing (Argon2id) | Replaces unmaintained passlib; FastAPI official docs updated to recommend pwdlib with Argon2; actively maintained by François Voron (fastapi-users author) |
| `python-multipart` | 0.0.32 | Required by FastAPI for form data (OAuth2PasswordRequestForm) | Already in requirements.txt — no change needed |

[VERIFIED: PyPI registry, FastAPI official docs https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/]

### Core (frontend — already installed)

| Library | Version | Purpose | Notes |
|---------|---------|---------|-------|
| `react-router-dom` | 7.18.0 | Protected routes, `<Navigate>` redirect | Already in package.json |
| `@tanstack/react-query` | 5.101.1 | Auth session query, cache invalidation on logout | Already in package.json |

[VERIFIED: E:\Projects\BizNiceSweets\frontend\package.json]

### Supporting (to add)

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `axios` | ~1.x | HTTP client with interceptor support for silent refresh | Preferred over raw `fetch` for the 401 retry / token-refresh interceptor; optional if team prefers a fetch wrapper |

[ASSUMED — axios version not verified in registry this session]

### Alternatives Considered and Rejected

| Instead of | Rejected Alternative | Why Rejected |
|------------|---------------------|--------------|
| `PyJWT` | `python-jose` | CVE-2024-33663 (algorithm confusion), CVE-2024-33664 (JWT bomb/DoS), plus 2 earlier CVEs; last PyPI release is 3.3.0 (no fixes released); last substantial commit years ago. Do not use. [VERIFIED: cve.yack.one/products/python-jose-project:python-jose, vicarius.io reports] |
| `pwdlib[argon2]` | `passlib[bcrypt]` | passlib is abandoned (last release 2020, no maintainer response, spam in tracker); incompatible with bcrypt ≥ 4.1 (`__about__.AttributeError` warning), removed `crypt` module in Python 3.13 breaks passlib internals. [VERIFIED: github.com/fastapi/fastapi/discussions/11773] |
| `pwdlib[argon2]` | `argon2-cffi` directly | argon2-cffi (25.1.0, actively maintained) is a valid alternative; pwdlib wraps it and adds bcrypt backward-compat. Either works — pwdlib is preferred for the algorithm-upgrade path it provides. |
| Argon2id | bcrypt | bcrypt silently truncates passwords to 72 bytes (Blowfish key-schedule limit), creating hash collisions for passwords differing only after byte 72. Argon2id has no such limit and is memory-hard. Use Argon2id via pwdlib. [VERIFIED: pkgpulse.com, webpronews.com bcrypt analysis] |
| HS256 | RS256/ES256 | RS256/ES256 require keypair management (rotation, distribution). For a single-server self-hosted deployment, HS256 with a strong random secret is simpler, equally secure, and the FastAPI docs default. RS256 adds value only when multiple services need to verify tokens independently (not Phase 2 scope). |

**Installation (backend additions):**

```bash
pip install "pyjwt==2.13.0" "pwdlib[argon2]==0.3.0"
```

Add to `requirements.txt`:
```
pyjwt==2.13.0
pwdlib[argon2]==0.3.0
```

**Version verification:**

```
PyJWT: 2.13.0 — verified via PyPI, latest stable (pyjwt.readthedocs.io/en/stable/changelog.html)
pwdlib: 0.3.0 — verified via PyPI, released 2025-10-25 (pypi.org/project/pwdlib/)
python-multipart: 0.0.32 — already in requirements.txt
```

---

## Architecture Patterns

### System Architecture Diagram

```
Browser
  │
  ├─[POST /api/v1/auth/login]──────────────────────────────────▶ FastAPI /auth/login
  │   (OAuth2PasswordRequestForm: email+password)                    │
  │                                                                  ├─ authenticate_user()
  │                                                                  │    └─ pwdlib.verify()
  │                                                                  ├─ create_access_jwt()  (HS256, 15 min)
  │                                                                  ├─ create_refresh_token() (opaque, 7 days, stored in DB)
  │                                                                  └─ Response:
  │◀──── { access_token, token_type: "bearer" }  ────────────────────┘
  │◀──── Set-Cookie: refresh_token=<opaque>; HttpOnly; Secure; SameSite=Lax; Path=/api/v1/auth/refresh
  │
  │  JS stores access_token in memory (not localStorage)
  │
  ├─[GET /api/v1/protected-resource]──────────────────────────▶ FastAPI gated endpoint
  │   Authorization: Bearer <access_token>                          │
  │                                                                 ├─ get_current_user() dependency
  │                                                                 │    └─ jwt.decode() → user_id
  │                                                                 ├─ require_permission("module:action")
  │                                                                 │    └─ check user.roles[].permissions[]
  │                                                                 │    └─ 403 if not authorized
  │◀──── 200 resource data ─────────────────────────────────────────┘
  │
  │  [Access token expires → 401]
  │
  ├─[POST /api/v1/auth/refresh]────────────────────────────────▶ FastAPI /auth/refresh
  │   Cookie: refresh_token=<opaque> (sent automatically)           │
  │                                                                 ├─ lookup token in DB
  │                                                                 ├─ verify not expired, not revoked
  │                                                                 ├─ user is_active check
  │                                                                 ├─ rotate: delete old, insert new token
  │                                                                 ├─ create_access_jwt()
  │◀──── { access_token }  ────────────────────────────────────────-┘
  │◀──── Set-Cookie: refresh_token=<new>; HttpOnly...
  │
  │  Interceptor retries original request with new access_token
```

### Recommended Project Structure (auth module)

```
backend/app/modules/auth/
├── __init__.py          # MODULE_NAME = "auth", registry.register(), router import
├── models.py            # User, Role, Permission, user_roles, role_permissions,
│                        #   RefreshToken, AuditLog — all inheriting from Base
├── router.py            # /auth/login, /auth/refresh, /auth/logout, /auth/me
│                        #   /auth/users (admin CRUD), /auth/roles (admin)
├── schemas.py           # Pydantic: TokenResponse, UserCreate, UserRead,
│                        #   UserUpdate, RoleRead, LoginRequest
├── service.py           # authenticate_user(), create_access_token(),
│                        #   create_refresh_token(), rotate_refresh_token(),
│                        #   get_user_by_email(), hash_password(), verify_password()
├── dependencies.py      # get_current_user(), require_permission("module:action")
│                        #   — the security dependency used by all modules
└── seed.py              # seed_admin_user(db) — called from core/seed.py

backend/app/core/
└── seed.py              # Phase 2: import and call seed_admin_user(db) here
```

```
frontend/src/
├── api/
│   └── client.ts        # axios instance with 401-retry interceptor for silent refresh
├── hooks/
│   └── useAuth.ts       # useQuery for /auth/me, returns { user, isLoading, isError }
├── components/
│   └── ProtectedRoute.tsx  # Layout route: checks auth, redirects to /login if not
├── routes/
│   ├── Login.tsx        # Login form, calls POST /auth/login, stores access_token
│   └── admin/
│       └── Users.tsx    # Admin user management screens (CORE-04)
└── App.tsx              # Add <Route element={<ProtectedRoute />}> wrapping app routes
```

### Pattern 1: SQLAlchemy 2.0 Auth Models

**What:** All auth tables in one `models.py`, inheriting from `core/base.py:Base`. Association tables use `Table()` construct; entity tables use `mapped_column()` with `Mapped[]` annotations.

**Why:** The single `Base.metadata` means one `alembic revision --autogenerate` picks up all auth tables automatically. The `core/models.py` aggregator imports `app.modules.auth.models` so Alembic's env.py sees them.

```python
# backend/app/modules/auth/models.py
# Source: SQLAlchemy 2.0 docs (docs.sqlalchemy.org/en/20/orm/basic_relationships.html)
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import List

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String, Table, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base import Base


# Association tables (no mapped class needed)
user_roles = Table(
    "user_roles",
    Base.metadata,
    Column("user_id", ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("role_id", ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
)

role_permissions = Table(
    "role_permissions",
    Base.metadata,
    Column("role_id", ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
    Column("permission_id", ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True),
)


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    roles: Mapped[List[Role]] = relationship(
        secondary=user_roles, back_populates="users", lazy="selectin"
    )
    refresh_tokens: Mapped[List[RefreshToken]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class Role(Base):
    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    users: Mapped[List[User]] = relationship(secondary=user_roles, back_populates="roles")
    permissions: Mapped[List[Permission]] = relationship(
        secondary=role_permissions, back_populates="roles", lazy="selectin"
    )


class Permission(Base):
    __tablename__ = "permissions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    # Format: "module:action" e.g. "syerp:read", "users:manage", "plum:write"
    code: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    roles: Mapped[List[Role]] = relationship(secondary=role_permissions, back_populates="permissions")


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # Family ID enables chain revocation on reuse detection (D-07)
    family: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    user: Mapped[User] = relationship(back_populates="refresh_tokens")


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    # Actor: None = system action (e.g. seed), str = user_id
    actor_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    # "user", "role", "session"
    target_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    target_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
```

**Key design notes:**

- User ID is UUID string (audit-safe, globally unique). Role and Permission IDs are integers (stable seeds).
- `token_hash` stores SHA-256 of the opaque refresh token, not the token itself — database compromise does not expose tokens directly. [CITED: mihai-andrei.com/blog/refresh-token-reuse-interval-and-reuse-detection/]
- `lazy="selectin"` on `User.roles` and `Role.permissions` avoids the async lazy-load pitfall — the collection loads in a single additional SELECT, not N lazy selects that would fire outside the session. [VERIFIED: docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html]
- `family` on RefreshToken links a rotation chain so reuse-detection can revoke the whole chain (D-07).

### Pattern 2: JWT + Password Helpers (service.py)

**What:** PyJWT for token creation/verification; pwdlib for Argon2id password hashing.

```python
# backend/app/modules/auth/service.py
# Source: FastAPI official docs (fastapi.tiangolo.com/tutorial/security/oauth2-jwt/)
#         PyJWT docs (pyjwt.readthedocs.io/en/stable/)
import hashlib
import secrets
from datetime import datetime, timedelta, timezone

import jwt
from jwt.exceptions import InvalidTokenError
from pwdlib import PasswordHash

from app.core.config import settings

# HS256 with the secret from environment (BNS_JWT_SECRET)
ALGORITHM = "HS256"

# PasswordHash.recommended() selects Argon2id with OWASP-safe defaults
_password_hash = PasswordHash.recommended()
# Dummy hash for constant-time comparison when user not found (timing attack prevention)
DUMMY_HASH = _password_hash.hash("dummypassword-constant-time")


def hash_password(plain: str) -> str:
    return _password_hash.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return _password_hash.verify(plain, hashed)


def create_access_token(subject: str, permissions: list[str]) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {"sub": subject, "exp": expire, "perms": permissions}
    return jwt.encode(payload, settings.jwt_secret.get_secret_value(), algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict:
    """Raises jwt.InvalidTokenError if invalid/expired."""
    return jwt.decode(
        token,
        settings.jwt_secret.get_secret_value(),
        algorithms=[ALGORITHM],
    )


def new_refresh_token() -> tuple[str, str]:
    """Returns (raw_token, sha256_hash). Store hash; send raw."""
    raw = secrets.token_urlsafe(32)
    hashed = hashlib.sha256(raw.encode()).hexdigest()
    return raw, hashed
```

### Pattern 3: FastAPI Auth Dependencies (dependencies.py)

**What:** Reusable `get_current_user` and `require_permission` dependencies. These are the integration surface every later module's router uses.

```python
# backend/app/modules/auth/dependencies.py
# Source: FastAPI official docs security tutorial
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jwt.exceptions import InvalidTokenError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.modules.auth.service import decode_access_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: AsyncSession = Depends(get_db),
):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_access_token(token)
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except InvalidTokenError:
        raise credentials_exception
    # Load user + roles (roles are selectin-loaded so no extra await)
    user = await get_user_by_id(db, user_id)
    if user is None or not user.is_active:
        raise credentials_exception
    return user


def require_permission(permission_code: str):
    """
    FastAPI dependency factory. Usage:
        @router.get("/syerp/vendors", dependencies=[Depends(require_permission("syerp:read"))])
    or in a Depends chain.
    """
    async def _check(current_user=Depends(get_current_user)):
        # Admin wildcard: a role whose name is "admin" grants everything.
        # Can be refined to a specific "admin:*" permission later.
        for role in current_user.roles:
            if role.name == "admin":
                return current_user
            for perm in role.permissions:
                if perm.code == permission_code:
                    return current_user
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Permission denied: {permission_code} required",
        )
    return _check
```

### Pattern 4: httpOnly Cookie for Refresh Token (router.py)

**What:** Login endpoint sets the refresh token as a cookie; the refresh endpoint reads it automatically.

```python
# backend/app/modules/auth/router.py (excerpt)
# Source: FastAPI response cookies docs (fastapi.tiangolo.com/advanced/response-cookies/)
from fastapi import APIRouter, Depends, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.config import settings

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login")
async def login(
    response: Response,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
):
    user = await authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(status_code=401, detail="Incorrect email or password")

    access_token = create_access_token(str(user.id), collect_permissions(user))
    raw_refresh, hashed_refresh = new_refresh_token()
    await store_refresh_token(db, user.id, hashed_refresh, family=new_family())

    # httpOnly cookie — JS cannot read it, SameSite=Lax blocks CSRF for same-origin SPA
    response.set_cookie(
        key="refresh_token",
        value=raw_refresh,
        httponly=True,
        secure=not settings.debug,  # False in local dev (HTTP), True in production
        samesite="lax",
        max_age=7 * 24 * 3600,  # 7 days
        path="/api/v1/auth/refresh",  # scope cookie to refresh endpoint only
    )
    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/refresh")
async def refresh_tokens(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    raw_token = request.cookies.get("refresh_token")
    if not raw_token:
        raise HTTPException(status_code=401, detail="No refresh token")
    # ... validate, rotate, return new access token and set new cookie
```

### Pattern 5: Frontend Silent-Refresh Interceptor

**What:** Axios instance with a response interceptor that catches 401 responses, fires `/auth/refresh` once (with queuing to avoid concurrent refresh races), then retries the original request.

```typescript
// frontend/src/api/client.ts
// Source: dev.to/elmehdiamlou/efficient-refresh-token-implementation-with-react-query-and-axios-f8d
import axios from 'axios'

const apiClient = axios.create({ withCredentials: true }) // sends httpOnly cookie

let isRefreshing = false
let failedQueue: Array<{ resolve: (v: string) => void; reject: (e: unknown) => void }> = []

function processQueue(error: unknown, token?: string) {
  failedQueue.forEach(prom => error ? prom.reject(error) : prom.resolve(token!))
  failedQueue = []
}

apiClient.interceptors.response.use(
  res => res,
  async err => {
    const original = err.config
    if (err.response?.status === 401 && !original._retry) {
      if (isRefreshing) {
        return new Promise((resolve, reject) => {
          failedQueue.push({ resolve, reject })
        }).then(token => {
          original.headers['Authorization'] = `Bearer ${token}`
          return apiClient(original)
        })
      }
      original._retry = true
      isRefreshing = true
      try {
        const { data } = await axios.post('/api/v1/auth/refresh', {}, { withCredentials: true })
        const newToken = data.access_token
        // Store in module-level ref or Zustand, NOT localStorage
        setAccessToken(newToken)
        original.headers['Authorization'] = `Bearer ${newToken}`
        processQueue(null, newToken)
        return apiClient(original)
      } catch (refreshErr) {
        processQueue(refreshErr)
        // Redirect to login
        window.location.href = '/login'
        return Promise.reject(refreshErr)
      } finally {
        isRefreshing = false
      }
    }
    return Promise.reject(err)
  }
)
```

**Access token storage:** A module-level variable (or Zustand atom) — not `localStorage` / `sessionStorage`. The token is lost on hard refresh, which is why the refresh flow must fire on page load (via the `/auth/me` query in TanStack Query).

### Pattern 6: Protected Route (React Router v7)

**What:** A layout route that renders `<Outlet />` when authenticated, or `<Navigate to="/login" />` with `state.from` for post-login redirect.

```typescript
// frontend/src/components/ProtectedRoute.tsx
// Source: robinwieruch.de/react-router-private-routes/ + react-router v7 docs
import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { useAuth } from '@/hooks/useAuth'

export function ProtectedRoute() {
  const { user, isLoading } = useAuth()
  const location = useLocation()

  if (isLoading) return <div>Loading...</div>
  if (!user) return <Navigate to="/login" state={{ from: location }} replace />
  return <Outlet />
}

// frontend/src/hooks/useAuth.ts
import { useQuery } from '@tanstack/react-query'
import { apiClient } from '@/api/client'

export function useAuth() {
  const { data: user, isLoading, isError } = useQuery({
    queryKey: ['auth', 'me'],
    queryFn: () => apiClient.get('/api/v1/auth/me').then(r => r.data),
    retry: false,        // 401 = not logged in, don't retry
    staleTime: 5 * 60_000,  // consider session fresh for 5 min
  })
  return { user: isError ? null : user, isLoading }
}
```

### Pattern 7: First-Admin Seed (extending core/seed.py)

```python
# backend/app/modules/auth/seed.py
# Idempotent: no-op if admin already exists. Called from core/seed.py:run_seeds().
async def seed_admin_user(db: AsyncSession) -> None:
    from sqlalchemy import select
    from app.modules.auth.models import User, Role, Permission
    from app.modules.auth.service import hash_password
    from app.core.config import settings

    # 1. Upsert permissions (idempotent by code)
    # 2. Upsert admin + user roles
    # 3. Assign all permissions to admin role
    # 4. Create admin user if not exists (email from settings.bns_admin_email)
    ...

# core/seed.py change:
# from app.modules.auth.seed import seed_admin_user
# await seed_admin_user(db)
```

**Config additions (extend config.py):**

```python
class Settings(BaseSettings):
    # ... existing fields ...

    # JWT
    jwt_secret: SecretStr  # Required — BNS_JWT_SECRET in env
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7

    # First-admin bootstrap (D-02)
    bns_admin_email: str = "admin@example.com"
    bns_admin_password: SecretStr  # Required — BNS_ADMIN_PASSWORD in env

    # Feature flags
    signup_enabled: bool = False
    debug: bool = False  # set True in dev compose overlay; controls cookie Secure flag
```

### Pattern 8: Alembic — Register Auth Models

The `core/models.py` aggregator already exists. Add one import:

```python
# backend/app/core/models.py  (add this line in Phase 2)
from app.modules.auth import models as auth_models  # noqa: F401
```

Then regenerate:

```bash
alembic revision --autogenerate -m "add_auth_tables"
alembic upgrade head
```

The migration will create all auth tables in a single revision within the existing single Alembic history (Phase 1 D-03). No new Alembic history is created.

### Anti-Patterns to Avoid

- **Storing the refresh token in localStorage or sessionStorage:** XSS can read them. Use httpOnly cookie. [CITED: fastapi.tiangolo.com/advanced/response-cookies/]
- **Storing refresh tokens in plain text in the DB:** Store SHA-256 hash. DB compromise should not expose tokens.
- **Lazy-loading relationships in async SQLAlchemy without `selectin`:** Triggers a greenlet error ("MissingGreenlet"). Use `lazy="selectin"` or eager-load explicitly with `options(selectinload(...))`. [VERIFIED: docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html]
- **Setting `allow_origins=["*"]` with `allow_credentials=True` in CORS:** FastAPI/Starlette will raise an error at startup. Must list explicit origins when credentials are enabled. [CITED: fastapi.tiangolo.com/tutorial/cors/]
- **Using python-jose:** Has 4 CVEs as of 2024, including algorithm confusion (CVE-2024-33663) and JWT bomb (CVE-2024-33664). Not safe for new code.
- **Using passlib[bcrypt]:** Abandoned. Breaks with bcrypt ≥ 4.1 (`__about__` AttributeError). Incompatible with Python 3.13 (removed `crypt` module).
- **Hardcoding the JWT secret:** Always read from environment via `SecretStr` (already the pattern in config.py).
- **Making `require_permission` a runtime string comparison without index:** The `permissions.code` column must be indexed (shown in models above) — permission checks fire on every request.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Password hashing | Custom bcrypt or SHA-256 password storage | `pwdlib[argon2]` | Argon2id tuning, salt generation, hash comparison, algorithm upgrade path are non-trivial |
| JWT creation/validation | Custom base64 + HMAC | `PyJWT` | Clock skew, expiry comparison, algorithm confusion attacks, standards compliance |
| Opaque token generation | `random.random()` or `uuid4()` for tokens | `secrets.token_urlsafe(32)` | `random` is not cryptographically secure; `secrets` is the stdlib CSPRNG |
| Timing-safe comparison | `==` on password hashes | `pwdlib.verify()` / `hmac.compare_digest()` | Regular string comparison leaks timing info |
| CORS middleware | Custom headers in every response | FastAPI's `CORSMiddleware` | Preflight, credential handling, vary headers — all covered |

**Key insight:** The critical custom code is `require_permission()` and the module:action permission schema. Everything else has a well-maintained library.

---

## Common Pitfalls

### Pitfall 1: SQLAlchemy Async Lazy Load Outside Session

**What goes wrong:** Accessing `user.roles` in a route handler after the session closes raises `sqlalchemy.exc.MissingGreenlet` (async context missing) or a detached-instance error.

**Why it happens:** SQLAlchemy 2.0 async sessions do not support implicit lazy loading outside an active session. The relationship fires a SELECT only when accessed, which is too late.

**How to avoid:** Set `lazy="selectin"` on `User.roles` and `Role.permissions` (shown in models above). This issues one additional SELECT per collection before returning the result — still efficient for small permission sets. Alternatively, use `options(selectinload(User.roles).selectinload(Role.permissions))` in the query.

**Warning signs:** `MissingGreenlet` traceback in test output after accessing relationship attributes.

### Pitfall 2: python-jose vs PyJWT Confusion

**What goes wrong:** Both expose an `import jwt` (python-jose also uses `jose.jwt`). Tutorials and Stack Overflow answers liberally mix them. If python-jose is installed alongside PyJWT, imports may resolve to the wrong library.

**Why it happens:** python-jose's ECDSA key handling has the algorithm confusion CVE-2024-33663.

**How to avoid:** Do not install python-jose. Use only `pyjwt`. In `requirements.txt`, pin `pyjwt==2.13.0` explicitly.

### Pitfall 3: passlib bcrypt Warning Spam / Breakage

**What goes wrong:** If passlib is installed, it will emit `AttributeError: module 'bcrypt' has no attribute '__about__'` with bcrypt 4.1+. On Python 3.13, passlib's `crypt` module import raises `ModuleNotFoundError`.

**Why it happens:** passlib uses internal private attributes of the bcrypt library that were removed. passlib is unmaintained and cannot be fixed.

**How to avoid:** Do not install passlib. Use pwdlib[argon2] exclusively.

### Pitfall 4: Refresh Token Race Condition (Multiple Concurrent 401s)

**What goes wrong:** If two API calls fire simultaneously and both expire at the same time, both get 401, both call `/auth/refresh`, and the first rotation invalidates the second's token — causing a logout.

**Why it happens:** No serialization of concurrent refresh attempts in the browser.

**How to avoid:** The failed-queue pattern in Pattern 5 above. `isRefreshing` flag ensures only one `/auth/refresh` call is in flight. Others queue and resolve with the new token.

**Warning sign:** Users reporting intermittent logouts under normal usage.

### Pitfall 5: Cookie Not Sent in Dev (Cross-Origin)

**What goes wrong:** In local development, the React dev server runs on `http://localhost:5173` and the FastAPI backend on `http://localhost:8000`. The refresh token cookie has `SameSite=Lax` and `Secure=False` (dev mode). But if the origin port differs, some browsers treat them as cross-site, and `SameSite=Lax` may not send the cookie on cross-origin POST.

**Why it happens:** "Same-site" in the cookie spec is determined by registrable domain, not port — but `localhost` is treated specially by different browsers.

**How to avoid:** Two options:
1. Use Vite's `server.proxy` to proxy `/api` to the backend — browser sees same origin, no CORS, no SameSite issue.
2. Configure FastAPI `CORSMiddleware` with `allow_credentials=True`, `allow_origins=["http://localhost:5173"]`, and `SameSite=None; Secure=False` in dev (requires HTTP).

The Vite proxy approach (option 1) is cleaner and avoids the `SameSite=None` in dev problem. [CITED: vitejs.dev/config/server-options.html — proxy option; fastapi CORS docs]

### Pitfall 6: Alembic Empty Autogenerate (Models Not Imported)

**What goes wrong:** `alembic revision --autogenerate` produces an empty migration (no `op.create_table` calls).

**Why it happens:** `env.py` imports `app.core.models` to populate `Base.metadata`. If the new `app.modules.auth.models` import is not added to `core/models.py`, Alembic never sees the auth tables.

**How to avoid:** Add `from app.modules.auth import models as auth_models  # noqa: F401` to `core/models.py` before running `alembic revision --autogenerate`. This is the same pattern SYERP uses. [VERIFIED: E:\Projects\BizNiceSweets\backend\app\core\models.py]

### Pitfall 7: Bcrypt 72-Byte Silent Truncation (Why We Use Argon2)

**What goes wrong:** If someone had chosen bcrypt, passwords longer than 72 bytes are silently truncated. Two different passwords that share the same first 72 bytes produce identical hashes — authentication bypass.

**Why it happens:** Blowfish key schedule limit in bcrypt. The truncation is silent — no error.

**How to avoid:** Use Argon2id via pwdlib. No truncation limit. Memory-hard. OWASP-recommended current standard. [CITED: pkgpulse.com/guides/bcrypt-vs-argon2-vs-scrypt-password-hashing-2026]

### Pitfall 8: Deactivated User Still Authenticated (Stateless JWT Problem)

**What goes wrong:** Admin deactivates a user. User's access token is still valid for up to 15 minutes. User can still make API calls.

**Why it happens:** Stateless JWTs cannot be revoked without a blocklist.

**How to avoid:** The `get_current_user` dependency queries the DB on every request to check `user.is_active`. This is the correct tradeoff for a self-hosted single-server deployment: one extra DB read per request vs. stale deactivation window. For deactivation to kill the **refresh** token path immediately, delete the user's `refresh_tokens` rows when deactivating. Access tokens expire naturally within 15 minutes. [ASSUMED — this tradeoff is standard for the deployment model but not explicitly verified against a third source]

---

## Code Examples

### Verified Pattern: Timing-Attack-Safe Login

```python
# Source: FastAPI official docs (fastapi.tiangolo.com/tutorial/security/oauth2-jwt/)
async def authenticate_user(db: AsyncSession, email: str, password: str):
    user = await get_user_by_email(db, email)
    if not user:
        verify_password(password, DUMMY_HASH)  # constant-time; discard result
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user
```

### Verified Pattern: PyJWT Decode with Algorithm Allowlist

```python
# Source: PyJWT docs (pyjwt.readthedocs.io)
# CRITICAL: always pass algorithms=[...] to prevent algorithm confusion attacks
payload = jwt.decode(token, secret, algorithms=["HS256"])
# Do NOT use algorithms="HS256" (string) — must be a list
```

### Verified Pattern: FastAPI Set Cookie

```python
# Source: FastAPI docs (fastapi.tiangolo.com/advanced/response-cookies/)
response.set_cookie(
    key="refresh_token",
    value=raw_token,
    httponly=True,
    secure=True,        # True in production (HTTPS); False in local HTTP dev
    samesite="lax",     # Lax blocks CSRF on same-origin SPA; adequate for this use case
    max_age=604800,     # 7 days in seconds
    path="/api/v1/auth/refresh",  # scope to refresh endpoint only
)
```

### Verified Pattern: FastAPI CORS with Credentials

```python
# Source: FastAPI CORS docs (fastapi.tiangolo.com/tutorial/cors/)
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # explicit list, NOT ["*"] with credentials
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `passlib[bcrypt]` + python-jose | `pwdlib[argon2]` + PyJWT | 2024 (FastAPI docs updated) | New projects must use pwdlib/PyJWT; passlib/python-jose are security/compatibility liabilities |
| JWT-only stateless sessions | Two-token model (access JWT + server-side refresh) | Established pattern, now expected | Enables user deactivation, session revocation, audit trail |
| `localStorage` for refresh tokens | `httpOnly` cookie | Ongoing security evolution | Eliminates XSS token theft |
| `bcrypt` password hashing | Argon2id | PHC winner 2015, OWASP recommended 2022+ | Memory-hard, no 72-byte truncation, GPU-resistant |

**Deprecated / outdated:**

- `python-jose`: 4 CVEs (2 in 2024), unmaintained. Do not use.
- `passlib`: Abandoned 2020. Incompatible with bcrypt ≥ 4.1 and Python 3.13. Do not use.
- Storing JWT in `localStorage`: XSS can exfiltrate it. Use memory + httpOnly cookie.
- `declarative_base()` function (SQLAlchemy 1.x): Replaced by `class Base(DeclarativeBase)` in SQLAlchemy 2.0. The project already uses the correct form in `core/base.py`.

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `axios` ~1.x is the right frontend HTTP client to add for the 401 interceptor | Standard Stack / Supporting | axios alternatives (ky, wretch, native fetch + AbortController) also work; the interceptor pattern varies slightly. Low risk — either choice is minor. |
| A2 | Deactivated user's access token can make calls for up to 15 min (DB check on each request is acceptable performance) | Common Pitfalls / Pitfall 8 | If this self-hosted deployment ever becomes high-traffic, the per-request DB user lookup becomes a bottleneck. Acceptable for Phase 2 scope. |
| A3 | Vite proxy is the preferred solution for dev cookie cross-origin | Common Pitfalls / Pitfall 5 | Team may prefer explicit CORS. Both work; planner should choose one approach and document it in the dev compose overlay. |
| A4 | User↔Role as many-to-many is the right schema choice | Architecture Patterns | One-to-many (single role per user) would be simpler. M2M is chosen because CORE-05 says "assign roles" (plural) and Phase 3's module enable/disable will want to combine roles. |

---

## Open Questions

1. **Should `require_permission` check the DB on every call, or embed permissions in the JWT?**
   - What we know: Embedding permissions in the JWT makes the access token self-contained (no DB hit per request) but means permission changes don't take effect until token expiry.
   - What's unclear: Whether a 15-minute lag on permission changes is acceptable for Phase 2.
   - Recommendation: For Phase 2, embed permissions in the JWT payload (`perms: ["syerp:read", "users:manage"]`). The 15-minute window is acceptable; access tokens are short-lived. This avoids a DB read on every API call. The `get_current_user` dependency still queries DB for `is_active` check only.

2. **User↔Role: one role per user (FK) or many-to-many (M2M)?**
   - What we know: CORE-05 says "assign roles" — implying plural. Phase 3 module enable/disable will consume role-based gating.
   - What's unclear: Whether any Phase 2 use case actually requires multiple roles per user simultaneously.
   - Recommendation: Use many-to-many (schema shown in Pattern 1). The `user_roles` association table has zero cost vs. a FK column, and avoids a migration later.

3. **Should audit_log be a PostgreSQL trigger or application-layer write?**
   - What we know: Application-layer write is simpler to implement and visible in code review. DB triggers are harder to test.
   - Recommendation: Application-layer writes in the auth service. The `AuditLog` model is provided above; write to it explicitly in service functions.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.13 | Backend | Yes | 3.13.1 | — |
| Node.js | Frontend build | Yes | 22.13.1 | — |
| Podman | Container deployment | Yes | 5.8.3 | Docker 28.1.1 also available |
| PostgreSQL | Data layer | Via container (podman-compose) | — | — |
| PyJWT | Backend JWT | Not yet installed in venv | — | Add to requirements.txt |
| pwdlib[argon2] | Backend passwords | Not yet installed in venv | — | Add to requirements.txt |
| python-multipart | FastAPI forms | Already in requirements.txt | 0.0.32 | — |

**Missing dependencies with no fallback:**

- `PyJWT` and `pwdlib[argon2]` must be added to `backend/requirements.txt` and installed.

**Missing dependencies with fallback:**

- None.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.1.1 + pytest-asyncio 1.4.0 |
| Config file | `backend/pyproject.toml` (`asyncio_mode = "auto"`, `testpaths = ["tests"]`) |
| Quick run command | `cd backend && pytest tests/test_auth.py -x -q` |
| Full suite command | `cd backend && pytest -q` |

### Phase Requirements to Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| CORE-02 | POST /auth/login with valid credentials returns access_token + sets refresh cookie | Integration (httpx AsyncClient, no live DB needed for unit; live DB for full flow) | `pytest tests/test_auth.py::test_login_success -x` | Wave 0 |
| CORE-02 | POST /auth/login with wrong password returns 401 | Unit | `pytest tests/test_auth.py::test_login_bad_password -x` | Wave 0 |
| CORE-02 | Admin can create a new user via POST /auth/users (admin role required) | Integration | `pytest tests/test_auth.py::test_admin_create_user -x` | Wave 0 |
| CORE-03 | POST /auth/refresh with valid cookie returns new access_token | Integration | `pytest tests/test_auth.py::test_token_refresh -x` | Wave 0 |
| CORE-03 | POST /auth/refresh with revoked token returns 401 | Unit/Integration | `pytest tests/test_auth.py::test_refresh_revoked_token -x` | Wave 0 |
| CORE-04 | Admin can deactivate user; deactivated user's /auth/me returns 401 | Integration | `pytest tests/test_auth.py::test_user_deactivation -x` | Wave 0 |
| CORE-05 | User with admin role can access gated endpoint; user without role gets 403 | Unit/Integration | `pytest tests/test_auth.py::test_rbac_enforcement -x` | Wave 0 |
| CORE-05 | `require_permission("syerp:read")` dependency returns 403 when user lacks it | Unit | `pytest tests/test_auth.py::test_require_permission_denied -x` | Wave 0 |

### Sampling Rate

- **Per task commit:** `cd backend && pytest tests/test_auth.py -x -q`
- **Per wave merge:** `cd backend && pytest -q`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps

- `backend/tests/test_auth.py` — covers all CORE-02 through CORE-05 scenarios above
- `backend/tests/conftest.py` — already exists; needs auth-specific fixtures:
  - `auth_db_session` — in-memory SQLite or test PostgreSQL session with auth tables
  - `admin_token` — fixture that creates an admin user and returns a Bearer token
  - `regular_token` — fixture with a user role, no admin
- Framework already installed (pytest-asyncio, httpx) — no new installs needed

---

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | Yes | PyJWT (token validation), pwdlib/Argon2id (credential storage), timing-safe compare, minimum password length |
| V3 Session Management | Yes | httpOnly/Secure/SameSite cookie for refresh token, server-side token revocation table, 64+ bit entropy via `secrets.token_urlsafe(32)` |
| V4 Access Control | Yes | `require_permission("module:action")` FastAPI dependency, 403 on missing permission, admin wildcard |
| V5 Input Validation | Yes | Pydantic schemas on all auth endpoints (email format, password minimum length, request body shape) |
| V6 Cryptography | Yes | Argon2id (pwdlib), HS256 (PyJWT), SHA-256 for refresh token storage, `secrets.token_urlsafe` for token generation |

### Known Threat Patterns for this Stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Brute-force login | Elevation of Privilege | Rate limiting (Phase 2 lite: rely on short lockout window; full rate-limiting is a later concern but note the gap) |
| XSS token theft | Information Disclosure | Refresh token in httpOnly cookie (not accessible via JS); access token in memory (page lifetime only) |
| CSRF on refresh endpoint | Tampering | SameSite=Lax on refresh cookie; cookie scoped to `/api/v1/auth/refresh` path; same-origin SPA in production eliminates most CSRF surface |
| Algorithm confusion in JWT | Elevation of Privilege | PyJWT replaces python-jose (CVE-2024-33663); always pass `algorithms=["HS256"]` list — never a string |
| Refresh token theft (DB) | Information Disclosure | Store SHA-256 hash of token in DB, not raw token |
| Replay of rotated refresh token | Elevation of Privilege | `family` tracking on RefreshToken; reuse detection revokes entire family (D-07) |
| User enumeration via login timing | Information Disclosure | Always verify dummy hash when user not found (timing-safe constant-time path) |
| Deactivated user session | Elevation of Privilege | `is_active` check in `get_current_user` on every request; deactivation deletes refresh tokens |
| Audit trail tampering | Repudiation | `AuditLog` table is append-only (no update endpoint); D-14 minimum events captured |
| Plaintext credential in config | Information Disclosure | `SecretStr` for `BNS_ADMIN_PASSWORD`, `BNS_JWT_SECRET` in Settings; `get_secret_value()` pattern already established in config.py |

**Brute-force gap:** ASVS V2.1.9 requires anti-automation (rate limiting, lockout, or CAPTCHA). Phase 2 does not implement rate limiting. This is a known gap. Document it in the plan and flag for a later hardening phase. For a self-hosted internal-business deployment, the risk is lower than a public-facing app, but it should be acknowledged.

---

## Sources

### Primary (HIGH confidence)

- `/jpadilla/pyjwt` (Context7) — JWT encode/decode, algorithm list requirement
- `/fastapi/fastapi` (Context7) — OAuth2PasswordBearer, security dependency, response cookies, CORS
- `/websites/sqlalchemy_en_20` (Context7) — async session, relationship lazy loading, selectin strategy
- `https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/` — current official FastAPI auth tutorial; confirmed pwdlib + PyJWT recommendation; full code example verified
- `https://docs.sqlalchemy.org/en/20/orm/basic_relationships.html` — many-to-many pattern with `Table()` and `Mapped[List[...]]`
- `E:\Projects\BizNiceSweets\backend\requirements.txt` — confirmed python-multipart already present; PyJWT and pwdlib not yet installed
- `E:\Projects\BizNiceSweets\frontend\package.json` — confirmed react-router-dom 7.18.0 and @tanstack/react-query 5.101.1 already installed
- `E:\Projects\BizNiceSweets\backend\app\core\*.py` — confirmed existing patterns: `get_db()`, `SecretStr`, registry, `Base`, `run_seeds()`

### Secondary (MEDIUM confidence)

- `https://pypi.org/project/pwdlib/` — version 0.3.0, released 2025-10-25, actively maintained
- `https://pypi.org/project/PyJWT/` — version 2.13.0, actively maintained
- `https://github.com/fastapi/fastapi/discussions/11773` — FastAPI maintainer community confirming passlib is abandoned
- `https://www.vicarius.io/vsociety/posts/algorithm-confusion-in-python-jose-cve-2024-33663` — CVE-2024-33663 detail on python-jose
- `https://www.vicarius.io/vsociety/posts/jwt-bomb-in-python-jose-cve-2024-33664` — CVE-2024-33664 detail on python-jose
- `https://robinwieruch.de/react-router-private-routes/` — React Router v7 protected route pattern
- `https://dev.to/elmehdiamlou/efficient-refresh-token-implementation-with-react-query-and-axios-f8d` — failed-queue pattern for 401 interceptor
- `https://mihai-andrei.com/blog/refresh-token-reuse-interval-and-reuse-detection/` — refresh token family/revocation pattern

### Tertiary (LOW confidence — flagged in Assumptions Log)

- `https://gist.github.com/wwnbb/c06899383e2cc1aa6dec96a9cd95fc3f` — async SQLAlchemy M2M pattern (aligned with official docs but single community source)

---

## Metadata

**Confidence breakdown:**

- Standard stack (PyJWT + pwdlib): HIGH — verified via PyPI, official FastAPI docs, Context7; explicit negative recommendation from FastAPI maintainers on python-jose/passlib
- Architecture (models, dependencies): HIGH — derived from SQLAlchemy 2.0 official docs and existing project patterns
- Frontend patterns (protected route, interceptor): MEDIUM — verified via multiple community sources aligned with React Router v7 and TanStack Query v5 documentation; no contradictions found
- Pitfalls: HIGH for library pitfalls (CVE-cited), MEDIUM for async/CORS gotchas (multiple consistent sources)

**Research date:** 2026-06-23
**Valid until:** 2026-09-23 (90 days — stable libraries; check pwdlib minor versions if delayed significantly)
