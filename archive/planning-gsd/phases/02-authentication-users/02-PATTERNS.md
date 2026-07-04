# Phase 2: Authentication & Users — Pattern Map

**Mapped:** 2026-06-23
**Files analyzed:** 16 new/modified files
**Analogs found:** 14 / 16

---

## File Classification

| New / Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---------------------|------|-----------|----------------|---------------|
| `backend/app/modules/auth/__init__.py` | module-init | request-response | `backend/app/modules/syerp/__init__.py` | exact |
| `backend/app/modules/auth/models.py` | model | CRUD | `backend/app/modules/syerp/models.py` (stub) + `backend/app/core/base.py` | role-match (stub is illustrative; Base pattern is exact) |
| `backend/app/modules/auth/router.py` | controller/route | request-response | `backend/app/api/health.py` | role-match |
| `backend/app/modules/auth/schemas.py` | model/schema | request-response | `backend/app/modules/syerp/schemas.py` (stub, see comments) | role-match |
| `backend/app/modules/auth/service.py` | service | request-response | `backend/app/modules/syerp/service.py` (stub) + health.py get_db pattern | role-match |
| `backend/app/modules/auth/dependencies.py` | middleware/utility | request-response | `backend/app/api/health.py` (`Depends(get_db)` pattern) | partial-match |
| `backend/app/modules/auth/seed.py` | utility/config | batch | `backend/app/core/seed.py` | exact |
| `backend/app/core/config.py` (modify) | config | — | self (extend existing) | exact |
| `backend/app/core/seed.py` (modify) | utility | batch | self (fill existing stub) | exact |
| `backend/app/core/models.py` (modify) | config/aggregator | — | self (add import line) | exact |
| `backend/app/main.py` (modify) | config/factory | request-response | self (add lifespan seed call + importlib line) | exact |
| `backend/tests/test_auth.py` | test | request-response | `backend/tests/test_health.py` | exact |
| `backend/tests/conftest.py` (modify) | test/config | — | self (add auth fixtures) | exact |
| `frontend/src/api/client.ts` | utility | request-response | `frontend/src/routes/Landing.tsx` (fetch pattern) | partial-match |
| `frontend/src/hooks/useAuth.ts` | hook | request-response | `frontend/src/routes/Landing.tsx` (useQuery pattern) | role-match |
| `frontend/src/components/ProtectedRoute.tsx` | component | request-response | `frontend/src/App.tsx` (Routes/Route pattern) | partial-match |
| `frontend/src/routes/Login.tsx` | component/route | request-response | `frontend/src/routes/Landing.tsx` | role-match |
| `frontend/src/routes/admin/Users.tsx` | component/route | CRUD | `frontend/src/routes/Landing.tsx` | partial-match |
| `frontend/src/App.tsx` (modify) | config/router | request-response | self (add ProtectedRoute wrapping) | exact |
| `frontend/src/lib/queryClient.ts` (modify) | config | — | self (no change likely needed) | exact |

---

## Pattern Assignments

### `backend/app/modules/auth/__init__.py` (module-init, request-response)

**Analog:** `backend/app/modules/syerp/__init__.py` (lines 1–22) — copy exactly, change `syerp` to `auth`.

**Module init pattern** (`backend/app/modules/syerp/__init__.py`, lines 13–22):
```python
import sys

from app.core import registry
from app.modules.syerp.router import router  # noqa: F401

MODULE_NAME = "syerp"

registry.register(sys.modules[__name__])
```

**Apply as:**
```python
import sys

from app.core import registry
from app.modules.auth.router import router  # noqa: F401

MODULE_NAME = "auth"

registry.register(sys.modules[__name__])
```

**main.py wiring pattern** (`backend/app/main.py`, line 74) — add one importlib call after the syerp one:
```python
importlib.import_module("app.modules.auth")
```

---

### `backend/app/modules/auth/models.py` (model, CRUD)

**Analog:** `backend/app/core/base.py` (Base class), `backend/app/modules/syerp/models.py` (Base usage pattern).

**Base import pattern** (`backend/app/core/base.py`, lines 10–14):
```python
from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    pass
```

**Model inheritance pattern** (`backend/app/modules/syerp/models.py`, line 11 + comments lines 14–22):
```python
from app.core.base import Base  # noqa: F401

# Every model added here MUST inherit from Base so that Base.metadata is
# populated when app.core.models (the central aggregator) is imported by
# Alembic's env.py.

class Vendor(Base):
    __tablename__ = "syerp_vendor"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
```

**Full auth models:** Use the SQLAlchemy 2.0 code from RESEARCH.md Pattern 1 (lines 239–353) as the implementation template. Key model design points verified against the codebase:
- Inherit from `app.core.base.Base` — same as syerp stub comment.
- Use `Mapped[]` + `mapped_column()` syntax — matches the syerp stub comment.
- `lazy="selectin"` on all relationship collections (avoids async greenlet error — Pitfall 1 in RESEARCH.md).
- Association tables use `Table()` (no mapped class).

---

### `backend/app/modules/auth/router.py` (controller/route, request-response)

**Analog:** `backend/app/api/health.py` — the only concrete FastAPI router in the codebase.

**Router + Depends pattern** (`backend/app/api/health.py`, lines 11–34):
```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db

router = APIRouter(tags=["health"])

@router.get("/health/ready")
async def readiness(db: AsyncSession = Depends(get_db)) -> dict:
    try:
        await db.execute(text("SELECT 1"))
        return {"status": "ok", "db": "connected"}
    except Exception:
        raise HTTPException(status_code=503, detail="Database unavailable")
```

**Apply:** Auth router follows the same `APIRouter` + `Depends(get_db)` + `HTTPException` structure. Add `prefix="/auth"` and `tags=["auth"]` on the `APIRouter()` constructor. The `mount_all()` in `registry.py` (line 46) adds the `/api/v1` prefix automatically — do not hardcode it in the router prefix.

**Core router template** (RESEARCH.md Pattern 4 excerpt for login + refresh):
```python
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db

router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/login")
async def login(
    response: Response,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
):
    ...

@router.post("/refresh")
async def refresh_tokens(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    ...
```

**Error handling pattern** — copy from health.py: `raise HTTPException(status_code=..., detail="...")`. No custom exception wrapper exists yet.

---

### `backend/app/modules/auth/schemas.py` (model/schema, request-response)

**Analog:** `backend/app/modules/syerp/schemas.py` (stub with Pydantic comments, lines 6–18).

**Pydantic schema pattern** (syerp stub, lines 6–18):
```python
# from pydantic import BaseModel
#
# class VendorCreate(BaseModel):
#     name: str
#
# class VendorRead(BaseModel):
#     id: int
#     name: str
#
#     model_config = {"from_attributes": True}
```

**Apply:** All auth response schemas use `model_config = {"from_attributes": True}` (SQLAlchemy ORM → Pydantic). Input schemas (e.g. `UserCreate`) do not need it. Follow RESEARCH.md architecture section for schema list: `TokenResponse`, `UserCreate`, `UserRead`, `UserUpdate`, `RoleRead`, `LoginRequest`.

---

### `backend/app/modules/auth/service.py` (service, request-response)

**Analog:** `backend/app/modules/syerp/service.py` (stub, lines 6–17) + `backend/app/core/db.py` (AsyncSession usage).

**Service function pattern** (syerp stub, lines 6–17):
```python
# from sqlalchemy.ext.asyncio import AsyncSession
# from app.modules.syerp import models, schemas
#
# async def create_vendor(db: AsyncSession, data: schemas.VendorCreate) -> models.Vendor:
#     vendor = models.Vendor(name=data.name)
#     db.add(vendor)
#     await db.commit()
#     await db.refresh(vendor)
#     return vendor
```

**AsyncSession pattern** (`backend/app/core/db.py`, lines 7–19):
```python
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
```

**Apply:** Auth service functions all take `db: AsyncSession` as first parameter, matching the syerp pattern. Add the JWT and password helpers from RESEARCH.md Pattern 2 — these have no existing analog but are fully specified in the research.

**Config access pattern** (`backend/app/core/config.py`, lines 25 and 37):
```python
# Reading a SecretStr:
settings.postgres_password.get_secret_value()
```
Copy this `.get_secret_value()` call for `settings.jwt_secret.get_secret_value()` in `create_access_token()`.

---

### `backend/app/modules/auth/dependencies.py` (middleware/utility, request-response)

**Analog:** `backend/app/api/health.py` — `Depends(get_db)` is the only dependency pattern in the codebase. No auth middleware analog exists yet; this is a net-new pattern.

**Depends pattern** (`backend/app/api/health.py`, line 27):
```python
async def readiness(db: AsyncSession = Depends(get_db)) -> dict:
```

**Apply:** `get_current_user` and `require_permission` follow the same `Depends()` pattern — they are injected into route function signatures. Use RESEARCH.md Pattern 3 as the implementation template. Key points: `OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")`, `Annotated[str, Depends(oauth2_scheme)]`, 401 on bad token, 403 on missing permission.

---

### `backend/app/modules/auth/seed.py` (utility/batch)

**Analog:** `backend/app/core/seed.py` (lines 1–34) — exact structural match.

**Seed pattern** (`backend/app/core/seed.py`, lines 13–34):
```python
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


async def run_seeds(db: "AsyncSession") -> None:  # noqa: ARG001
    """
    Phase 1: intentionally empty — seed hook only, no data inserted.

    Phase 2 extension point:
        from app.modules.auth.seed import seed_admin_user
        await seed_admin_user(db)
    """
    pass
```

**Apply:** `seed_admin_user(db: AsyncSession) -> None` is an `async def` taking `AsyncSession`. It must be idempotent — check-before-insert pattern using `select()`. Follow RESEARCH.md Pattern 7 structure: upsert permissions → upsert roles → assign permissions to admin → create admin user if not exists. Reads `settings.bns_admin_email` and `settings.bns_admin_password.get_secret_value()`.

**Modify `backend/app/core/seed.py`** — fill the stub (lines 31–34):
```python
    from app.modules.auth.seed import seed_admin_user
    await seed_admin_user(db)
```

---

### `backend/app/core/config.py` (config, modify)

**Analog:** Self — extend existing `Settings` class.

**SecretStr pattern** (`backend/app/core/config.py`, lines 8–9, 24–25, 37):
```python
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    postgres_password: SecretStr  # No default — operator must supply

    @property
    def database_url(self) -> str:
        pw = self.postgres_password.get_secret_value()
        ...
```

**Add to Settings class** (after existing fields):
```python
    # JWT
    jwt_secret: SecretStr         # Required — BNS_JWT_SECRET in env
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7

    # First-admin bootstrap (D-02)
    bns_admin_email: str = "admin@example.com"
    bns_admin_password: SecretStr  # Required — BNS_ADMIN_PASSWORD in env

    # Feature flags
    signup_enabled: bool = False
    debug: bool = False            # True in dev compose overlay; gates cookie Secure flag
```

---

### `backend/app/core/models.py` (aggregator, modify)

**Analog:** Self — add one import following the established pattern.

**Existing import pattern** (`backend/app/core/models.py`, line 15):
```python
from app.modules.syerp import models as syerp_models  # noqa: F401
```

**Add (Phase 2):**
```python
from app.modules.auth import models as auth_models  # noqa: F401
```

---

### `backend/app/main.py` (factory, modify)

**Analog:** Self — add lifespan seed hook call and importlib line.

**importlib import pattern** (`backend/app/main.py`, line 74):
```python
importlib.import_module("app.modules.syerp")
```

**Lifespan pattern** (`backend/app/main.py`, lines 51–55):
```python
@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    # Startup
    yield
    # Shutdown
```

**Add to lifespan startup block:**
```python
    async with AsyncSessionLocal() as db:
        from app.core.seed import run_seeds
        await run_seeds(db)
```

**Add importlib line** after syerp (line 74):
```python
importlib.import_module("app.modules.auth")
```

---

### `backend/tests/test_auth.py` (test, request-response)

**Analog:** `backend/tests/test_health.py` (lines 1–27) — exact structural match for async httpx tests.

**Test file pattern** (`backend/tests/test_health.py`, lines 1–27):
```python
"""
Health endpoint tests — Wave 0 harness.
...
"""
import pytest
import httpx


async def test_liveness(client: httpx.AsyncClient) -> None:
    """GET /health/live returns 200 with status=ok (no DB required)."""
    response = await client.get("/health/live")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"


async def test_readiness(client: httpx.AsyncClient, skip_if_no_db: None) -> None:
    """GET /health/ready returns 200 with db=connected when DB is available."""
    response = await client.get("/health/ready")
    assert response.status_code == 200
```

**Apply:** Auth tests use the same `async def test_*(client: httpx.AsyncClient)` signature. For DB-dependent tests (login flow, RBAC), add `skip_if_no_db: None` fixture parameter (already defined in conftest.py, line 88–97).

**New fixtures needed in conftest.py** (add to `backend/tests/conftest.py`):
- `admin_token` — fixture that injects `BNS_ADMIN_EMAIL` / `BNS_ADMIN_PASSWORD` env vars (same pattern as `POSTGRES_PASSWORD` at conftest.py line 24), creates admin via seed, returns `Authorization: Bearer <token>` header dict.
- `regular_token` — same shape, user role only.

**conftest env-var injection pattern** (`backend/tests/conftest.py`, line 24):
```python
os.environ.setdefault("POSTGRES_PASSWORD", "testpassword")
```
Add before `import app.*`:
```python
os.environ.setdefault("BNS_JWT_SECRET", "test-jwt-secret-at-least-32-chars-long")
os.environ.setdefault("BNS_ADMIN_EMAIL", "admin@test.local")
os.environ.setdefault("BNS_ADMIN_PASSWORD", "testadminpass")
```

---

### `frontend/src/api/client.ts` (utility, request-response)

**Analog:** `frontend/src/routes/Landing.tsx` (fetch + TanStack Query pattern, lines 1–15) — partial match only. No axios instance or interceptor exists yet.

**Existing fetch pattern** (`frontend/src/routes/Landing.tsx`, lines 9–15):
```typescript
async function fetchHealth(path: string): Promise<HealthResponse> {
  const res = await fetch(path)
  if (!res.ok) {
    throw new Error(`Health check failed: ${res.status} ${res.statusText}`)
  }
  return res.json() as Promise<HealthResponse>
}
```

**Apply:** `client.ts` replaces bare `fetch` with an axios instance. The failed-queue interceptor pattern has no codebase analog — use RESEARCH.md Pattern 5 as the implementation template. The `withCredentials: true` option ensures the httpOnly refresh cookie is sent automatically on cross-origin dev proxy requests.

**TanStack Query client config** (`frontend/src/lib/queryClient.ts`, lines 1–14) is already configured; `useAuth.ts` adds a new `queryKey: ['auth', 'me']` query alongside existing health queries.

---

### `frontend/src/hooks/useAuth.ts` (hook, request-response)

**Analog:** `frontend/src/routes/Landing.tsx` (useQuery pattern, lines 1–2, 18–22).

**useQuery pattern** (`frontend/src/routes/Landing.tsx`, lines 1–2, 18–22):
```typescript
import { useQuery } from '@tanstack/react-query'

const liveness = useQuery<HealthResponse, Error>({
  queryKey: ['health', 'live'],
  queryFn: () => fetchHealth('/health/live'),
})
```

**Apply:**
```typescript
import { useQuery } from '@tanstack/react-query'
import { apiClient } from '@/api/client'

export function useAuth() {
  const { data: user, isLoading, isError } = useQuery({
    queryKey: ['auth', 'me'],
    queryFn: () => apiClient.get('/api/v1/auth/me').then(r => r.data),
    retry: false,          // 401 = not logged in; don't retry (override queryClient default)
    staleTime: 5 * 60_000,
  })
  return { user: isError ? null : user, isLoading }
}
```

Note: `retry: false` overrides the `queryClient.ts` global `retry: 1` default — correct for auth; a 401 is not transient.

---

### `frontend/src/components/ProtectedRoute.tsx` (component, request-response)

**Analog:** `frontend/src/App.tsx` (Routes/Route usage, lines 1–9).

**Route pattern** (`frontend/src/App.tsx`, lines 1–9):
```typescript
import { Routes, Route } from 'react-router-dom'
import { Landing } from '@/routes/Landing'

export function App() {
  return (
    <Routes>
      <Route path="/" element={<Landing />} />
    </Routes>
  )
}
```

**Apply:** `ProtectedRoute` is a layout route that wraps protected routes. Use RESEARCH.md Pattern 6 as the template. Integrates with `useAuth` hook and `<Navigate>` / `<Outlet>` from react-router-dom (already installed at 7.18.0).

**App.tsx modification:** Wrap existing and new routes:
```typescript
<Route element={<ProtectedRoute />}>
  {/* all authenticated routes here */}
</Route>
<Route path="/login" element={<Login />} />
```

---

### `frontend/src/routes/Login.tsx` (component/route, request-response)

**Analog:** `frontend/src/routes/Landing.tsx` (component structure with shadcn/ui + TanStack Query, lines 17–73).

**Component structure pattern** (`frontend/src/routes/Landing.tsx`, lines 17–30):
```typescript
export function Landing() {
  const liveness = useQuery<HealthResponse, Error>({...})

  return (
    <div className="min-h-screen bg-background flex flex-col items-center justify-center p-8">
      <div className="max-w-lg w-full space-y-8">
        ...
      </div>
    </div>
  )
}
```

**Apply:** Login page uses the same full-screen centered layout (`min-h-screen bg-background flex flex-col items-center justify-center`), Tailwind utility classes, and `cn()` from `@/lib/utils`. Uses `useMutation` (TanStack Query) for the POST /auth/login call — mutation not query, since login is a write operation. On success, store `access_token` in a module-level ref (not localStorage), then navigate to `state.from` or `/`.

---

### `frontend/src/routes/admin/Users.tsx` (component/route, CRUD)

**Analog:** `frontend/src/routes/Landing.tsx` (component + useQuery pattern) — partial match only. No existing CRUD UI exists.

**Apply:** Follow the same component structure as Landing.tsx. Uses `useQuery` for GET /auth/users (list) and `useMutation` for create/edit/deactivate. Requires `useAuth()` to confirm admin role before rendering (or rely on backend 403). Tailwind + shadcn/ui table/form components — no component library analogs exist yet in codebase; use shadcn/ui primitives (`<Table>`, `<Button>`, `<Dialog>`, `<Form>`) per CLAUDE.md stack spec.

---

## Shared Patterns

### DB Session Dependency
**Source:** `backend/app/core/db.py` (lines 7–24), used in `backend/app/api/health.py` (line 27)
**Apply to:** All auth router endpoints, all auth service functions
```python
from app.core.db import get_db
# In route signature:
db: AsyncSession = Depends(get_db)
```

### SecretStr for Sensitive Values
**Source:** `backend/app/core/config.py` (lines 8, 25, 37)
**Apply to:** `config.py` additions (jwt_secret, bns_admin_password), anywhere these values are read
```python
from pydantic import SecretStr
# Reading the value:
settings.jwt_secret.get_secret_value()
```
Never pass `settings.jwt_secret` directly to PyJWT — always call `.get_secret_value()` first.

### HTTPException Error Responses
**Source:** `backend/app/api/health.py` (lines 32–34)
**Apply to:** All auth router endpoints
```python
raise HTTPException(status_code=503, detail="Database unavailable")
# Auth equivalent examples:
raise HTTPException(status_code=401, detail="Could not validate credentials",
                    headers={"WWW-Authenticate": "Bearer"})
raise HTTPException(status_code=403, detail="Permission denied: syerp:read required")
```

### Module Self-Registration
**Source:** `backend/app/modules/syerp/__init__.py` (lines 13–22), `backend/app/core/registry.py` (lines 38–46)
**Apply to:** `backend/app/modules/auth/__init__.py`
```python
import sys
from app.core import registry
from app.modules.auth.router import router  # noqa: F401
MODULE_NAME = "auth"
registry.register(sys.modules[__name__])
```
Then add `importlib.import_module("app.modules.auth")` to `backend/app/main.py`.

### Alembic Model Aggregator
**Source:** `backend/app/core/models.py` (line 15)
**Apply to:** `backend/app/core/models.py` (add one line for auth models)
```python
from app.modules.auth import models as auth_models  # noqa: F401
```
Must be added before running `alembic revision --autogenerate` or the migration will be empty (Pitfall 6 in RESEARCH.md).

### Async Test Client
**Source:** `backend/tests/conftest.py` (lines 74–84), `backend/tests/test_health.py` (lines 13–17)
**Apply to:** `backend/tests/test_auth.py`
```python
# Fixture in conftest.py:
@pytest.fixture
async def client() -> httpx.AsyncClient:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c

# In test file:
async def test_login_success(client: httpx.AsyncClient) -> None:
    response = await client.post("/api/v1/auth/login", data={...})
    assert response.status_code == 200
```

### TanStack Query useQuery Pattern
**Source:** `frontend/src/routes/Landing.tsx` (lines 1–2, 18–22), `frontend/src/lib/queryClient.ts` (lines 1–14)
**Apply to:** `frontend/src/hooks/useAuth.ts`, `frontend/src/routes/admin/Users.tsx`
```typescript
import { useQuery } from '@tanstack/react-query'
const { data, isLoading, isError } = useQuery({
  queryKey: ['auth', 'me'],
  queryFn: () => apiClient.get('/api/v1/auth/me').then(r => r.data),
  retry: false,
})
```

### Tailwind + shadcn/ui Component Layout
**Source:** `frontend/src/routes/Landing.tsx` (lines 29–73)
**Apply to:** `frontend/src/routes/Login.tsx`, `frontend/src/routes/admin/Users.tsx`
```typescript
// Full-screen centered layout:
<div className="min-h-screen bg-background flex flex-col items-center justify-center p-8">
  <div className="max-w-lg w-full space-y-8">
    ...
  </div>
</div>
// Tailwind conditional classes via cn():
import { cn } from '@/lib/utils'
className={cn('base-class', condition && 'conditional-class')}
```

---

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `backend/app/modules/auth/dependencies.py` | middleware/utility | request-response | No auth middleware or FastAPI dependency factory exists yet — first security dependency in the codebase. RESEARCH.md Pattern 3 is the authoritative template. |
| `frontend/src/api/client.ts` | utility | request-response | No HTTP client with interceptors exists — Landing.tsx uses bare `fetch`. RESEARCH.md Pattern 5 (axios + failed-queue interceptor) is the authoritative template. |

---

## Metadata

**Analog search scope:** `backend/app/` (all .py), `frontend/src/` (all .ts/.tsx)
**Files scanned:** 23 Python files, 6 TypeScript/TSX files
**Pattern extraction date:** 2026-06-23

**Critical integration notes:**
1. `backend/app/core/models.py` import must precede any `alembic revision --autogenerate` run.
2. Env vars `BNS_JWT_SECRET` and `BNS_ADMIN_PASSWORD` must be injected in `tests/conftest.py` before `import app.*` — same placement as the existing `POSTGRES_PASSWORD` injection at line 24.
3. `mount_all()` in `registry.py` adds `/api/v1` prefix automatically — do not add it again in the auth `APIRouter(prefix=...)`.
4. Auth `router.py` prefix should be `/auth` only; full path becomes `/api/v1/auth/...` after `mount_all`.
5. `lazy="selectin"` is mandatory on `User.roles` and `Role.permissions` — async SQLAlchemy will raise `MissingGreenlet` without it (Pitfall 1 in RESEARCH.md).
