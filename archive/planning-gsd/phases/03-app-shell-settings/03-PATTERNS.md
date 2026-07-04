# Phase 3: App Shell & Settings - Pattern Map

**Mapped:** 2026-06-26
**Files analyzed:** 22 (new) + 6 (modified)
**Analogs found:** 22 / 22 (every new file has a strong in-repo analog)

This map tells the planner exactly which existing file each new file should copy
from, with concrete line ranges. The codebase is small and internally consistent
(Phase 1 + Phase 2 shipped), so every Phase 3 file has a near-exact sibling.

---

## File Classification

### Backend — new files

| New File | Role | Data Flow | Closest Analog | Match Quality |
|----------|------|-----------|----------------|---------------|
| `backend/app/core/modules_model.py` | model | CRUD | `backend/app/modules/auth/models.py` (`Permission`) | exact (role + flow) |
| `backend/app/core/settings_model.py` | model | CRUD | `backend/app/modules/auth/models.py` (`Permission`/`AuditLog`) | exact |
| `backend/app/core/modules_schemas.py` | schema | request-response | `backend/app/modules/auth/schemas.py` (`UserRead`/`UserUpdate`) | exact |
| `backend/app/core/settings_schemas.py` | schema | request-response | `backend/app/modules/auth/schemas.py` | exact |
| `backend/app/core/modules_router.py` | router | CRUD / request-response | `backend/app/modules/auth/router.py` (admin user CRUD block) | exact |
| `backend/app/core/settings_router.py` | router | CRUD / request-response | `backend/app/modules/auth/router.py` | exact |
| `backend/app/core/modules_seed.py` | seed | batch / idempotent-insert | `backend/app/modules/auth/seed.py` | exact |
| `backend/app/core/settings_seed.py` | seed | batch / idempotent-insert | `backend/app/modules/auth/seed.py` | exact |
| `backend/alembic/versions/0003_add_modules_settings_tables.py` | migration | DDL | `backend/alembic/versions/0002_add_auth_tables.py` | exact |
| `backend/tests/core/__init__.py` | test pkg | — | `backend/tests/auth/__init__.py` | exact |
| `backend/tests/core/conftest.py` | test fixture | — | `backend/tests/auth/conftest_helpers.py` | exact |
| `backend/tests/core/test_modules.py` | test | integration | `backend/tests/auth/test_user_admin.py` | exact |
| `backend/tests/core/test_settings.py` | test | integration | `backend/tests/auth/test_user_admin.py` | exact |

### Frontend — new files

| New File | Role | Data Flow | Closest Analog | Match Quality |
|----------|------|-----------|----------------|---------------|
| `frontend/src/components/AppShell.tsx` | component (layout route) | request-response | `frontend/src/components/ProtectedRoute.tsx` | exact (auth-guard) |
| `frontend/src/components/Sidebar.tsx` | component | — | `frontend/src/components/ProtectedRoute.tsx` + Users toolbar | role-match |
| `frontend/src/components/Topbar.tsx` | component | — | `Users.tsx` DropdownMenu usage (lines 350–379) | role-match |
| `frontend/src/components/MobileSidebar.tsx` | component | — | `Users.tsx` Sheet usage (lines 388–500) | role-match |
| `frontend/src/hooks/useModules.ts` | hook | request-response | `frontend/src/hooks/useAuth.ts` | exact |
| `frontend/src/hooks/useSettings.ts` | hook | request-response | `frontend/src/hooks/useAuth.ts` | exact |
| `frontend/src/routes/Home.tsx` | route | — | `frontend/src/routes/admin/Users.tsx` (heading block) | partial (static page) |
| `frontend/src/routes/admin/Settings.tsx` | route | CRUD (form) | `frontend/src/routes/admin/Users.tsx` | exact |
| `frontend/src/routes/admin/Modules.tsx` | route | CRUD (toggle table) | `frontend/src/routes/admin/Users.tsx` | exact |
| `frontend/src/components/ui/switch.tsx` | ui primitive | — | (shadcn add — generated) | new dep |

### Modified files

| Modified File | Change | Analog / Reference |
|---------------|--------|--------------------|
| `backend/app/core/models.py` | Add 2 import lines for new models | existing Phase-2 block, lines 14–18 |
| `backend/app/core/seed.py` | Add 2 seed calls in `run_seeds()` | existing pattern, lines 31–33 |
| `backend/app/main.py` | Mount 2 core routers before `mount_all` | lines 72–83 |
| `backend/app/modules/auth/seed.py` | Add `settings:manage` permission + grant to admin | `_PERMISSIONS` list, lines 32–38 |
| `backend/app/modules/auth/schemas.py` | Add `permissions: list[str]` to `UserRead` | lines 48–57 |
| `backend/app/modules/auth/router.py` | Populate `permissions` in `/me` via `collect_permissions` | lines 234–237 |
| `frontend/src/hooks/useAuth.ts` | Add `permissions: string[]` to `AuthUser` | lines 17–23 |
| `frontend/src/App.tsx` | Replace `ProtectedRoute` route with `AppShell`; add new routes | lines 10–23 |

---

## Pattern Assignments

### `backend/app/core/modules_model.py` (model, CRUD)

**Analog:** `backend/app/modules/auth/models.py` — the `Permission` class (lines 100–112) is the closest sibling: a small entity with a natural string identifier and no relationships in v1.

**Imports + Base pattern** (models.py lines 15–24):
```python
from __future__ import annotations
from sqlalchemy import Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from app.core.base import Base
```

**Column style to copy** (models.py lines 100–108, the `Permission` entity):
```python
class Permission(Base):
    __tablename__ = "permissions"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
```

**Apply to `Module`:** natural string PK `key` (mirrors `Permission.code` being the stable identifier), `display_name`, `enabled` (Boolean default True), `always_on` (Boolean default False), `sort_order` (Integer default 100). RESEARCH §"Key Pattern 1" gives the exact column set. **No relationships in v1** — so do NOT add `lazy="selectin"` (the models.py comment at lines 11–13 / 76–80 explains that selectin is only required for collection relationships).

**CRITICAL (RESEARCH Pitfall 1):** This model is only discovered by Alembic autogenerate if imported in `core/models.py`. See the modified-files section.

---

### `backend/app/core/settings_model.py` (model, CRUD)

**Analog:** same — `backend/app/modules/auth/models.py` `Permission` (lines 100–112) and `AuditLog` (lines 137–151, for the nullable-string-column style used by `owner_id`).

**Per RESEARCH §"Key Pattern 2":** surrogate int PK + `key` (indexed, not unique alone) + `value` (Text nullable) + `value_type` + `category` + `scope` + `owner_id` (nullable, for D-13 groundwork) + `description`. The surrogate-PK-plus-partial-unique-index approach avoids a future breaking migration when per-user settings arrive. Copy the `AuditLog.actor_id` nullable-string pattern (models.py line 142) for `owner_id`:
```python
actor_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
```

**Partial unique index** (RESEARCH Pitfall 5 — Postgres `NULL != NULL`): express as
```python
from sqlalchemy import Index
__table_args__ = (
    Index("uq_settings_global", "key", unique=True, postgresql_where=(owner_id == None)),
)
```

---

### `backend/app/core/modules_schemas.py` & `settings_schemas.py` (schema, request-response)

**Analog:** `backend/app/modules/auth/schemas.py` (whole file, lines 1–81).

**Read schema pattern** (schemas.py lines 48–57 — note `model_config = {"from_attributes": True}` for ORM serialization):
```python
class UserRead(BaseModel):
    id: str
    email: str
    full_name: Optional[str] = None
    is_active: bool
    roles: List[RoleRead] = []
    model_config = {"from_attributes": True}
```

**Update schema pattern (PATCH semantics — all optional)** (schemas.py lines 60–65):
```python
class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    is_active: Optional[bool] = None
    role: Optional[str] = None
```

**Apply to:** `ModuleRead` (key, display_name, enabled, always_on, sort_order + `from_attributes`), `ModuleUpdate` (enabled: Optional[bool]), `SettingRead`, `SettingUpdate` (value: Optional[str]). RESEARCH §"Code Examples" has the exact fields. The docstring convention at schemas.py lines 1–14 (Input vs Response separation) should be reused.

---

### `backend/app/core/modules_router.py` (router, CRUD / request-response)

**Analog:** `backend/app/modules/auth/router.py` — the admin user-CRUD block (lines 240–339) is the exact pattern: admin-gated endpoints using `require_permission`, `Depends(get_db)`, select-first-then-404, then mutate-commit.

**Imports pattern** (router.py lines 28–48):
```python
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.db import get_db
from app.modules.auth.dependencies import get_current_user, require_permission
```

**Router declaration + prefix note** (router.py lines 17–18, 50):
```python
# mount_all() / include_router adds /api/v1 — do NOT include it here.
router = APIRouter(prefix="/auth", tags=["auth"])
```
For Phase 3 use `prefix="/core/modules"` / `tags=["core"]`. NOTE: core routers are NOT mounted via `mount_all()` (they are not registry modules); they are mounted directly in `main.py` WITH the `/api/v1` prefix — see the modified-files section. So the router prefix here is the path *after* `/api/v1`.

**Admin-gated endpoint + 404 + mutate pattern** (router.py lines 291–323 — the PATCH user handler):
```python
@router.patch("/users/{user_id}", response_model=UserRead)
async def update_user_endpoint(
    user_id: str,
    data: UserUpdate,
    acting_admin=Depends(require_permission("users:manage")),
    db: AsyncSession = Depends(get_db),
) -> UserRead:
    ...
    user = await update_user(db, user_id=user_id, ...)
    return user
```

**For Phase 3 specifics:**
- `GET /core/modules` — gate with `Depends(get_current_user)` only (any authenticated user; nav reads it). RESEARCH Open Question 1 resolves to auth-required.
- `PATCH /core/modules/{key}` — gate with `require_permission("settings:manage")`; select module, 404 if missing, **reject always-on disable with 422** (RESEARCH §"Key Pattern 3" + Pitfall 7):
```python
if mod.always_on and data.enabled is False:
    raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail=f"Module '{key}' is always-on and cannot be disabled")
```
- Settings PATCH must use `data.model_dump(exclude_unset=True)` to avoid overwriting omitted fields to None (RESEARCH Pitfall 8).

**Error-handling convention:** the codebase raises `HTTPException(status_code=..., detail=...)` inline at the call site (see router.py lines 119–123, 174–178). There is no centralized error wrapper — match that.

---

### `backend/app/core/modules_seed.py` & `settings_seed.py` (seed, idempotent-insert)

**Analog:** `backend/app/modules/auth/seed.py` (whole file, lines 1–146) — the canonical idempotent select-before-insert seed.

**Idempotent select-before-insert loop** (seed.py lines 64–72):
```python
for code, description in _PERMISSIONS:
    result = await db.execute(select(Permission).where(Permission.code == code))
    perm = result.scalars().first()
    if perm is None:
        perm = Permission(code=code, description=description)
        db.add(perm)
        await db.flush()
```

**Module-level seed-data constant** (seed.py lines 31–41):
```python
_PERMISSIONS: list[tuple[str, str]] = [
    ("users:manage", "Create, edit, and deactivate user accounts"),
    ...
]
```

**Final commit** (seed.py line 145): single `await db.commit()` at the end.

**Apply to:**
- `modules_seed.py` — `_MODULE_SEEDS` static list of all 7 suites (RESEARCH §"Key Pattern 1" gives `(key, display_name, always_on, sort_order)` tuples). Use a **static list, NOT `registry._registry`** (RESEARCH Pitfall in Pattern 1: registry only holds modules imported under the current Compose profile; static list keeps the admin catalog complete). `seed_modules_table(db)` mirrors `seed_admin_user` signature.
- `settings_seed.py` — `_DEFAULT_SETTINGS` list (company.name, company.logo_url, locale.currency, locale.date_format, locale.timezone, locale.units — RESEARCH §"Key Pattern 2"). Select-before-insert must filter `Setting.owner_id.is_(None)` for the global row.

---

### `backend/alembic/versions/0003_add_modules_settings_tables.py` (migration, DDL)

**Analog:** `backend/alembic/versions/0002_add_auth_tables.py` (lines 1–70 read; structure continues for all tables).

**Revision header** (0002 lines 27–36):
```python
revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None
```
For 0003: `revision = "0003"`, `down_revision = "0002"`.

**Table-creation style** (0002 lines 43–63 — note `server_default=sa.true()` for booleans, `server_default=sa.text("now()")` for timestamps, and explicit `op.create_index`):
```python
op.create_table(
    "users",
    sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
    sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
    ...
)
op.create_index("ix_users_email", "users", ["email"], unique=True)
```

**Apply to:** `modules` table + `settings` table. For the settings partial unique index, emit the Postgres-specific partial index in `upgrade()`:
```python
op.create_index("uq_settings_global", "settings", ["key"], unique=True,
                postgresql_where=sa.text("owner_id IS NULL"))
```
NOTE: the repo convention (0002 docstring lines 22–25) is migrations are hand-authored from the ORM models with no live DB at plan time — match the ORM column definitions exactly. Provide a matching `downgrade()` dropping both tables.

---

### `backend/tests/core/test_modules.py` & `test_settings.py` (test, integration)

**Analog:** `backend/tests/auth/test_user_admin.py` (lines 1–349) — admin-gated CRUD integration tests with the exact 200/403/401 coverage Phase 3 needs.

**Test signature + skip_if_no_db + admin-token helper** (test_user_admin.py lines 26–43):
```python
async def test_admin_create_user(client: httpx.AsyncClient, skip_if_no_db: None) -> None:
    token = await admin_login_token(client)
    response = await client.post("/api/v1/auth/users", json={...},
                                 headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 201
```

**Non-admin 403 pattern — mint a token without the permission** (test_user_admin.py lines 45–60):
```python
from app.modules.auth.service import create_access_token
user_token = create_access_token(subject="regular-user-id", permissions=["syerp:read"])
response = await client.patch(..., headers={"Authorization": f"Bearer {user_token}"})
assert response.status_code == 403
```

**Unauthenticated 401 pattern** (test_user_admin.py lines 63–71): request with no header → 401.

**DB-assertion pattern (read a row back)** (test_user_admin.py lines 296–315):
```python
from app.core.db import AsyncSessionLocal
async with AsyncSessionLocal() as session:
    result = await session.execute(select(...).where(...))
    row = result.scalars().first()
assert row is not None
```

**Apply to (per RESEARCH §"Validation Architecture" test map):**
- `test_modules.py`: GET list returns enabled flag; PATCH plum enabled=false → 200; PATCH syerp enabled=false → 422 (always-on guard); non-admin PATCH → 403.
- `test_settings.py`: GET list (admin) → 200; PATCH company.name updates value; seed populates company.name default.
- `test_login.py` addition: `/auth/me` response includes `permissions` list.

---

### `backend/tests/core/conftest.py` & `__init__.py`

**Analog:** `backend/tests/auth/conftest_helpers.py` (lines 1–108) and `backend/tests/auth/__init__.py`.

Reuse `admin_login_token(client)` (conftest_helpers.py lines 75–92) and the `seeded_db` fixture style (lines 52–67). The global `client` / `skip_if_no_db` fixtures already live in `backend/tests/conftest.py` (lines 83–107) and are auto-discovered — the core conftest only needs core-specific seed fixtures (e.g. a `seeded_modules` fixture calling `seed_modules_table`).

---

### `frontend/src/hooks/useModules.ts` & `useSettings.ts` (hook, request-response)

**Analog:** `frontend/src/hooks/useAuth.ts` (whole file, lines 1–34) — exact pattern.

**Full hook pattern to copy** (useAuth.ts lines 14–34):
```typescript
import { useQuery } from '@tanstack/react-query'
import { apiClient } from '@/api/client'

export interface AuthUser { id: string; /* ... */ }

export function useAuth(): { user: AuthUser | null; isLoading: boolean } {
  const { data: user, isLoading, isError } = useQuery<AuthUser, Error>({
    queryKey: ['auth', 'me'],
    queryFn: () => apiClient.get<AuthUser>('/api/v1/auth/me').then((r) => r.data),
    retry: false,
    staleTime: 5 * 60_000,
  })
  return { user: isError ? null : (user ?? null), isLoading }
}
```

**Apply to `useModules`** (RESEARCH §"Key Pattern 6/7"): queryKey `['core', 'modules']`, `queryFn` GET `/api/v1/core/modules`, `staleTime: 10_000`, `refetchOnWindowFocus: true` (override the global `false` from `queryClient.ts` line 7 so toggles propagate on tab focus — D-09). `useSettings`: queryKey `['core', 'settings']`, GET `/api/v1/core/settings`.

---

### `frontend/src/components/AppShell.tsx` (component, layout route / auth-guard)

**Analog:** `frontend/src/components/ProtectedRoute.tsx` (whole file, lines 1–34) — AppShell MERGES this guard (RESEARCH §"Key Pattern 5" + Pitfall 3: do not nest two layout routes).

**Auth-guard + Outlet pattern to absorb** (ProtectedRoute.tsx lines 17–33):
```typescript
import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { Loader2 } from 'lucide-react'
import { useAuth } from '@/hooks/useAuth'

export function ProtectedRoute() {
  const { user, isLoading } = useAuth()
  const location = useLocation()
  if (isLoading) return (<div className="min-h-screen bg-background flex items-center justify-center">
      <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" /></div>)
  if (!user) return <Navigate to="/login" state={{ from: location }} replace />
  return <Outlet />
}
```

**Apply to `AppShell`:** keep the identical loading + redirect guard, but instead of returning bare `<Outlet />`, render the sidebar + topbar chrome around `<Outlet />` (RESEARCH §"Key Pattern 5" gives the flex layout). The existing `ProtectedRoute.tsx` can be deleted or kept as a thin re-export — planner's call.

**Empty-state (D-05):** when `useVisibleModules()` returns `[]`, the shell still renders chrome and the content area shows "No modules available — contact your admin." Reuse the empty-state block style from `Users.tsx` lines 311–318.

---

### `frontend/src/components/Topbar.tsx` & `MobileSidebar.tsx` & `Sidebar.tsx`

**Analog:** `frontend/src/routes/admin/Users.tsx` — it already composes every shadcn primitive the chrome needs, with the project's accessibility conventions.

**DropdownMenu (user/admin menu) pattern** (Users.tsx lines 350–379):
```tsx
<DropdownMenu>
  <DropdownMenuTrigger asChild>
    <Button variant="ghost" size="icon" aria-label={`User actions for ${...}`}>
      <MoreHorizontal className="h-4 w-4" aria-hidden="true" />
      <span className="sr-only">Open actions menu</span>
    </Button>
  </DropdownMenuTrigger>
  <DropdownMenuContent align="end">
    <DropdownMenuItem onClick={...}>Edit</DropdownMenuItem>
  </DropdownMenuContent>
</DropdownMenu>
```
Apply to Topbar: user menu with Logout item, and an admin-only group (Users / System Settings / Modules) gated on `user.roles.some(r => r.name === 'admin')` (D-02, D-03). Logout calls `POST /api/v1/auth/logout` then `clearAccessToken()` — see `api/client.ts` logout flow (lines 94–99) for the redirect-to-`/login` precedent.

**Sheet (mobile drawer) pattern** (Users.tsx lines 388–393, uses `side` prop):
```tsx
<Sheet open={...} onOpenChange={...}>
  <SheetContent side="right" aria-labelledby="sheet-title" aria-describedby="sheet-description">
```
For MobileSidebar use `side="left"` (confirmed available — RESEARCH §"Key Pattern 5").

**Active-module indicator:** use react-router `NavLink` `isActive` (RESEARCH §"Key Pattern 5") — NOT manual `window.location` comparison.

**Accessibility conventions to carry (mandatory in this repo):** every icon-only control has `aria-label` + `<span className="sr-only">`; decorative icons get `aria-hidden="true"`; badges/status use color AND text together (Users.tsx `StatusBadge` lines 129–143). The CLAUDE.md UI conventions and the Users.tsx header comment (lines 1–19) document this.

---

### `frontend/src/routes/admin/Settings.tsx` & `Modules.tsx` (route, CRUD)

**Analog:** `frontend/src/routes/admin/Users.tsx` (whole file, lines 1–548) — exact data + form + mutation pattern.

**Query + mutation + invalidate pattern** (Users.tsx lines 175–195):
```tsx
const queryClient = useQueryClient()
const { data: users = [], isLoading } = useQuery<User[], Error>({
  queryKey: ['users'], queryFn: fetchUsers,
})
const createMutation = useMutation<User, Error, CreatePayload>({
  mutationFn: createUser,
  onSuccess: () => { void queryClient.invalidateQueries({ queryKey: ['users'] }) },
})
```

**Toggle mutation for Modules** (RESEARCH §"Key Pattern 7" — invalidate `['core', 'modules']` on success so nav refetches; Pitfall 6 — key must match `useModules` exactly):
```tsx
const toggleMutation = useMutation({
  mutationFn: ({ key, enabled }) =>
    apiClient.patch(`/api/v1/core/modules/${key}`, { enabled }).then(r => r.data),
  onSuccess: () => queryClient.invalidateQueries({ queryKey: ['core', 'modules'] }),
})
```

**Settings form:** copy the Sheet form-field pattern (Users.tsx lines 406–473) — `Label htmlFor` paired with `Input`, `Select` for locale dropdowns. Page heading block (Users.tsx lines 282–289) for the screen header.

**Modules table:** copy the `Table`/`TableHeader`/`TableRow` structure (Users.tsx lines 320–384). Replace the actions column with a `Switch` (new shadcn component). For always-on rows, render the Switch `disabled` with an explanatory tooltip (D-08) — the backend 422 is the real guard; the disabled Switch is UX only.

---

### `frontend/src/routes/Home.tsx` (route, neutral landing — D-06)

**Analog:** `frontend/src/routes/admin/Users.tsx` heading block (lines 282–289) for the page shell; `frontend/src/routes/Landing.tsx` (current `/` content) for what it replaces.

A static greeting/overview placeholder — no data fetching beyond `useAuth()` for the user's name. Lowest-complexity file in the phase.

---

## Shared Patterns

### Authentication / Authorization gate (backend)
**Source:** `backend/app/modules/auth/dependencies.py` lines 56–127.
**Apply to:** every new backend router.
- Any-authenticated-user read → `current_user=Depends(get_current_user)` (lines 56–89).
- Admin-gated write → `=Depends(require_permission("settings:manage"))` (factory at lines 97–127). The `admin` role is wildcard (line 117), so the seeded admin passes automatically; standard users need the explicit `settings:manage` permission.
```python
async def _check(current_user=Depends(get_current_user)):
    for role in current_user.roles:
        if role.name == "admin":
            return current_user
        for perm in role.permissions:
            if perm.code == permission_code:
                return current_user
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=...)
```

### New permission seed (`settings:manage`) — D-12
**Source:** `backend/app/modules/auth/seed.py` lines 32–41, 100–104.
**Apply to:** the `_PERMISSIONS` list (add `("settings:manage", "Configure system settings and enable/disable modules")`). Admin role auto-gets all permissions (lines 100–103); do NOT add it to `_USER_ROLE_PERMS` (settings stays admin-only). RESEARCH §"Key Pattern 4".

### Async session + commit (backend)
**Source:** `backend/app/core/db.py` (`get_db`) consumed via `db: AsyncSession = Depends(get_db)` everywhere; commit-then-`db.refresh(obj)` after a mutation (router.py PATCH handlers). `Base` is `AsyncAttrs + DeclarativeBase` (`core/base.py` lines 14–18) — use `await obj.awaitable_attrs.<rel>` only if relationships are added (none in v1).

### Alembic discovery (backend)
**Source:** `backend/app/core/models.py` lines 14–29 (the aggregator Alembic imports).
**Apply to:** add `from app.core.modules_model import Module  # noqa: F401` and `from app.core.settings_model import Setting  # noqa: F401`. **Without this, autogenerate produces an empty migration** (RESEARCH Pitfall 1; models.py docstring lines 1–12).

### Seed wiring (backend)
**Source:** `backend/app/core/seed.py` lines 21–33.
**Apply to:** add `seed_modules_table(db)` and `seed_default_settings(db)` calls after `seed_admin_user(db)` in `run_seeds()`. All seeds are idempotent and run on every startup via the lifespan hook (`main.py` lines 52–59).

### Router mounting (backend)
**Source:** `backend/app/main.py` lines 79–83.
**Apply to:** core routers are NOT registry modules — import and mount them directly before `mount_all(app)`:
```python
from app.core.modules_router import router as modules_router
from app.core.settings_router import router as settings_router
app.include_router(modules_router, prefix="/api/v1", tags=["core"])
app.include_router(settings_router, prefix="/api/v1", tags=["core"])
```
Must be added BEFORE the SPA static mount (lines 91–97), which is a catch-all.

### TanStack Query data fetching (frontend)
**Source:** `frontend/src/hooks/useAuth.ts` (hooks) + `frontend/src/routes/admin/Users.tsx` lines 175–195 (mutations) + `frontend/src/lib/queryClient.ts` (global defaults: `staleTime 30_000`, `refetchOnWindowFocus false`, `retry 1`).
**Apply to:** all new hooks/screens. Override `refetchOnWindowFocus: true` + `staleTime: 10_000` specifically on `useModules` for D-09 toggle propagation. Standardize the module query key as `['core', 'modules']` everywhere (RESEARCH Pitfall 6).

### API client (frontend)
**Source:** `frontend/src/api/client.ts` (whole file).
**Apply to:** all requests go through the shared `apiClient` axios instance — it already attaches the Bearer token (lines 25–31) and handles silent refresh on 401 (lines 55–104). New hooks/screens import `apiClient` and never call `axios` directly (except the refresh call itself).

### Frontend accessibility + UI conventions
**Source:** `frontend/src/routes/admin/Users.tsx` lines 1–19 (header contract) + `StatusBadge` lines 129–143.
**Apply to:** all new screens/chrome — `Label htmlFor` pairing, `aria-label` on icon-only buttons with `sr-only` text, `aria-hidden` on decorative icons, `aria-labelledby`/`aria-describedby` on Dialog/Sheet, color-plus-text for status. Also per the phase's committed UI-SPEC (`docs/` / phase 03 UI design contract commits) — planner should read the UI-SPEC before building screens.

---

## No Analog Found

| File | Role | Reason |
|------|------|--------|
| `frontend/src/components/ui/switch.tsx` | ui primitive | Generated by `npx shadcn@latest add switch` — not hand-authored; no in-repo analog needed. RESEARCH §"New shadcn component". |

Everything else has a strong in-repo analog. There are **no** files that must fall back to RESEARCH-only patterns.

---

## Metadata

**Analog search scope:**
- Backend: `backend/app/core/`, `backend/app/modules/auth/`, `backend/alembic/versions/`, `backend/tests/`
- Frontend: `frontend/src/components/`, `frontend/src/hooks/`, `frontend/src/routes/`, `frontend/src/lib/`, `frontend/src/api/`

**Files scanned (read in full or targeted):** auth `models.py`, `seed.py`, `router.py`, `dependencies.py`, `schemas.py`; core `models.py`, `seed.py`, `base.py`, `registry.py`; `main.py`; migration `0002_add_auth_tables.py`; tests `conftest.py`, `conftest_helpers.py`, `test_user_admin.py`; frontend `useAuth.ts`, `App.tsx`, `ProtectedRoute.tsx`, `queryClient.ts`, `Users.tsx`, `api/client.ts`.

**Pattern extraction date:** 2026-06-26
