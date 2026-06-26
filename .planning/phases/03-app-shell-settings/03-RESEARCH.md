# Phase 3: App Shell & Settings - Research

**Researched:** 2026-06-26
**Domain:** React layout-route shell, FastAPI key-value settings + module registry DB table, TanStack Query cache invalidation
**Confidence:** HIGH — all recommendations grounded in existing repo source files; no gaps requiring external lookup for core patterns

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Shell Layout & Chrome**
- D-01: Sidebar + top bar layout. A persistent left sidebar for module navigation, plus a thin top bar for global controls. Sidebar collapses to a shadcn `sheet` drawer on narrow screens (component already installed).
- D-02: Persistent chrome contains: configured company name / branding (from CORE-06 settings), a user menu with a logout control (closes Phase-2 follow-up), an active-module indicator, and an admin/settings entry visible to admins only.
- D-03: Admin screens are reached via a settings/user menu in the chrome (gear icon or user-menu dropdown), not as top-level business-nav items. Groups Users, System Settings, and Modules away from the business-module nav. Admin entry gated to admin users.

**Navigation Visibility Logic**
- D-04: Nav shows a module only if it is ENABLED *and* the user is PERMITTED. Module appears iff enabled (CORE-07) AND user holds the relevant `module:action` permission (Phase 2 RBAC). The literal CORE-08 is satisfied as a superset.
- D-05: Friendly empty state if no modules visible — chrome still renders, content area shows "No modules available — contact your admin."
- D-06: Post-login landing is a neutral home/dashboard at `/`, not a module redirect.

**Module Enable/Disable Model**
- D-07: DB-backed `modules` table, idempotently seeded from the code registry on startup. Columns: `key`, `display_name`, `enabled`, `always_on` (planner refines). Seeding via select-before-insert. Autogenerates into single Alembic history via core/models.py.
- D-08: SYERP always-on enforced via `always_on = true`. UI shows but disables the control with tooltip. Backend rejects any request to disable an always-on module.
- D-09: "Disappears immediately for all users" satisfied by refetch, not live push. TanStack Query refetch after toggle, on navigation, and/or on window focus.

**System Settings Model & Scope**
- D-10: Key-value settings table (`key`, `value`, `type`/`category`). Additive growth without a migration per new setting.
- D-11: v1 settings: company identity (company name, logo/address optional) + locale defaults (default currency, date format, timezone, units).
- D-12: Settings global and admin-only in v1, gated by an admin permission (planner's call within Phase 2 RBAC model).
- D-13: Schema leaves room for per-user override layer as additive change (optional owner/scope dimension). No per-user behavior in Phase 3.

### Claude's Discretion (delegated to researcher/planner)
- Exact column sets for the `modules` and `settings` tables, and whether `settings` carries a `scope`/`owner` column now or reserves the room logically.
- The precise admin permission string gating Settings and Module toggles within the Phase 2 `module:action` model.
- Shell component structure (layout wrapper vs nested routes), active-module indicator from router, which existing shadcn primitives to compose.
- TanStack Query refetch triggers/cadence for toggle propagation.
- Whether enabled-modules + visible-nav is one API response or composed client-side.
- Seed details for the `modules` table (display names, ordering, icons).

### Deferred Ideas (OUT OF SCOPE)
- Live push of module enable/disable to all open clients (WebSocket/SSE) — backlog for future milestone.
- Per-user preferences / settings — only data-model groundwork in scope.
- Rich company branding (logo upload, address blocks, themes) — optional/later.
- Module-level metadata in nav (icons, ordering, grouping) — basic version builder's discretion; richer module catalog UI is later.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| CORE-06 | Admin can configure system settings (company info, defaults) | Key-value `settings` table + admin-gated PATCH endpoint; company name consumed by shell header |
| CORE-07 | Admin can enable or disable individual modules | `modules` table with `enabled`/`always_on` columns + toggle endpoint; SYERP always-on rejection at API layer |
| CORE-08 | User sees a navigation shell listing enabled modules and can switch between them | React Router layout-route shell; nav computed from enabled modules ∩ user permissions |
</phase_requirements>

---

## Summary

Phase 3 adds two new DB tables (`modules` and `settings`) under `backend/app/core/` (not a module package — these are cross-cutting platform concerns), one Alembic revision extending the existing single history, two new FastAPI routers (settings + modules), and a React layout-route shell wrapping all protected routes in `App.tsx`.

The key technical challenge is the nav visibility join: the frontend must intersect the `modules` table state (enabled) with the current user's permissions (from `/auth/me`). The cleanest approach — confirmed by looking at `useAuth.ts` — is to compose this client-side from two existing queries: `useAuth` already fetches user+roles from `/auth/me`, and a new `useModules` hook will fetch `GET /api/v1/core/modules`. A single backend `/api/v1/core/nav` endpoint that computes the intersection server-side is tempting but adds tight coupling between the modules table and the RBAC model; the two-query client-side composition is simpler and consistent with Phase 2 patterns.

The TanStack Query cache is configured globally with `staleTime: 30_000` and `refetchOnWindowFocus: false` in `queryClient.ts`. For module toggle propagation (D-09), the pattern is: toggle mutation calls `queryClient.invalidateQueries({ queryKey: ['core', 'modules'] })` on success, plus bump `staleTime` for the modules query to a short value (5–10 seconds) so window-focus refetches also pick up admin changes quickly. This matches the "within seconds" SLA for a single-instance deployment without WebSockets.

**Primary recommendation:** Place all new backend under `backend/app/core/` (new `modules.py` and `settings.py` in core); add a single Alembic revision `0003_add_modules_settings_tables.py`; create a React `AppShell` layout component that wraps `<Outlet />` in `App.tsx` as a layout route; seed the `modules` table from `registry._registry` in `core/seed.py` following the exact pattern already used in `auth/seed.py`.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Nav visibility (enabled AND permitted) | Browser/Client | — | Intersection computed from two cached queries; no SSR |
| Module enable/disable toggle | API/Backend | Database | Business logic + always-on enforcement lives server-side |
| System settings persistence | Database | API/Backend | Key-value store; API exposes CRUD, DB owns persistence |
| Shell chrome (sidebar, topbar, drawer) | Browser/Client | — | React layout-route; all state in component + TanStack Query |
| Admin gating (settings, toggle) | API/Backend | Browser/Client | Backend `require_permission` is the real gate; UI gating is UX convenience only |
| Company name in header | Browser/Client | API/Backend | Client reads settings query; API provides value from DB |
| Module always-on enforcement | API/Backend | — | Reject disable of always-on at the endpoint level; DB carries the flag |
| Seed modules from static catalog | API/Backend | — | lifespan startup in `core/seed.py` seeds from a static 7-suite module catalog, NOT `registry._registry` (the registry only holds modules under the active Compose profile) |

---

## Standard Stack

### Core — already in repo, no new installs needed

| Library | Version | Purpose | Status |
|---------|---------|---------|--------|
| FastAPI | 0.138.0 | API framework | Installed [VERIFIED: backend/requirements.txt] |
| SQLAlchemy | 2.0.51 | ORM (async) | Installed [VERIFIED: backend/requirements.txt] |
| Alembic | 1.18.4 | Migrations | Installed [VERIFIED: backend/requirements.txt] |
| pydantic-settings | 2.14.2 | Config/settings | Installed [VERIFIED: backend/requirements.txt] |
| React | 19.2.7 | Frontend framework | Installed [VERIFIED: frontend/package.json] |
| react-router-dom | 7.18.0 | Client routing + layout routes | Installed [VERIFIED: frontend/package.json] |
| @tanstack/react-query | 5.101.1 | Data fetching + cache | Installed [VERIFIED: frontend/package.json] |
| lucide-react | 1.21.0 | Icons | Installed [VERIFIED: frontend/package.json] |

### shadcn/ui Primitives — already installed, no new adds for core shell

| Component | File | Use in Phase 3 |
|-----------|------|----------------|
| `Sheet` | `ui/sheet.tsx` | Sidebar drawer on narrow screens (D-01) [VERIFIED: repo] |
| `DropdownMenu` | `ui/dropdown-menu.tsx` | User/settings menu in topbar (D-03) [VERIFIED: repo] |
| `Separator` | `ui/separator.tsx` | Nav section dividers [VERIFIED: repo] |
| `Button` | `ui/button.tsx` | Nav items, form actions [VERIFIED: repo] |
| `Card` | `ui/card.tsx` | Settings panels [VERIFIED: repo] |
| `Input` / `Label` | `ui/input.tsx`, `ui/label.tsx` | Settings form fields [VERIFIED: repo] |
| `Select` | `ui/select.tsx` | Locale dropdowns in settings [VERIFIED: repo] |

### New shadcn component needed

| Component | Install command | Purpose |
|-----------|----------------|---------|
| `Switch` | `npx shadcn@latest add switch` | Module enable/disable toggle (not yet in repo) [VERIFIED: glob search found no switch.tsx] |

The module toggle in the admin Modules screen requires a `Switch` — the radix `@radix-ui/react-switch` primitive. The `Sheet`, `DropdownMenu`, etc. are already installed for the shell itself.

**Installation (one command, run from `frontend/`):**
```bash
npx shadcn@latest add switch
```

---

## Architecture Patterns

### System Architecture Diagram

```
Browser (React SPA)
  │
  ├── App.tsx (React Router)
  │     ├── /login → <Login /> (public)
  │     └── <AppShell /> (layout route — ProtectedRoute merged)
  │           ├── Sidebar (desktop)  ←─────────┐
  │           ├── TopBar                        │  both read:
  │           │     └── DropdownMenu (user+admin)│  - useAuth() → roles
  │           └── <Outlet />                    │  - useModules() → enabled[]
  │                 ├── / → <Home />            │  nav = enabled ∩ permitted
  │                 ├── /settings → <Settings />│
  │                 ├── /settings/modules → <Modules />
  │                 └── /admin/users → <Users /> (existing)
  │
  ├── useModules() ─────────────────────────────────────→ GET /api/v1/core/modules
  ├── useSettings() ──────────────────────────────────→ GET /api/v1/core/settings
  └── useAuth() ──────────────────────────────────────→ GET /api/v1/auth/me
  
Backend (FastAPI + async SQLAlchemy)
  │
  ├── /api/v1/core/modules
  │     ├── GET  (public to any authenticated user — nav reads it)
  │     ├── PATCH /{key} (admin-gated — toggle enabled)
  │     └── always-on enforcement: reject PATCH enabled=false when always_on=true
  │
  ├── /api/v1/core/settings
  │     ├── GET  (admin-gated in v1, or public — planner's call)
  │     └── PATCH (admin-gated)
  │
  └── lifespan startup (seed.py)
        └── seed_modules_table() ← reads registry._registry → modules DB rows
  
Database (PostgreSQL)
  ├── modules (key, display_name, enabled, always_on, sort_order)
  └── settings (key, value, value_type, category, scope, owner_id)
```

### Recommended Project Structure (new files only)

```
backend/app/core/
├── modules_model.py      # Module ORM model (separate file, not in models.py body)
├── modules_router.py     # GET/PATCH /core/modules endpoints
├── modules_schemas.py    # ModuleRead, ModuleUpdate Pydantic schemas
├── modules_seed.py       # seed_modules_table() — called from seed.py
├── settings_model.py     # Setting ORM model
├── settings_router.py    # GET/PATCH /core/settings endpoints
├── settings_schemas.py   # SettingRead, SettingUpdate Pydantic schemas
├── settings_seed.py      # seed_default_settings() — called from seed.py
└── models.py             # ADD import of modules_model + settings_model (existing file)

backend/alembic/versions/
└── 0003_add_modules_settings_tables.py

frontend/src/
├── components/
│   └── AppShell.tsx          # Layout route component (sidebar + topbar + Outlet)
│   └── Sidebar.tsx           # Desktop persistent nav
│   └── Topbar.tsx            # Company name + user/admin dropdown
│   └── MobileSidebar.tsx     # Sheet-wrapped Sidebar for narrow screens
├── hooks/
│   ├── useModules.ts         # useQuery ['core', 'modules']
│   └── useSettings.ts        # useQuery ['core', 'settings']
├── routes/
│   ├── Home.tsx              # Replaces Landing.tsx at / (D-06 post-login home)
│   └── admin/
│       ├── Settings.tsx      # System settings form
│       └── Modules.tsx       # Module enable/disable table with Switch
```

**Note on core/ vs module package placement:** The `modules` and `settings` tables are cross-cutting platform concerns — they belong in `backend/app/core/`, not in a module package. The pattern of separating models/routers/schemas into named files (e.g. `modules_model.py`, `modules_router.py`) rather than a subfolder avoids Python package nesting while keeping `core/` organized. Alternatively, a `backend/app/core/settings/` and `backend/app/core/modules/` sub-package each with `model.py`/`router.py`/`schemas.py` would be cleaner; planner chooses the structure.

---

## Key Pattern 1: `modules` Table — Columns and Seed

**What it is:** A DB-backed registry of which modules exist (seeded from code) and which are enabled (admin-toggled at runtime). Distinct from Compose profiles (deploy-time presence) vs DB flag (runtime on/off).

**Recommended column set** [ASSUMED — no existing schema to verify against, derived from D-07/D-08 and auth/models.py patterns]:

```python
# backend/app/core/modules_model.py
from __future__ import annotations
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import Boolean, Integer, String
from app.core.base import Base

class Module(Base):
    __tablename__ = "modules"

    # Natural key matching MODULE_NAME in each module's __init__.py
    key: Mapped[str] = mapped_column(String(50), primary_key=True)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    # False = currently disabled (admin toggled off); always_on=True cannot go False
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # True = platform-bundled; PATCH to enabled=False is rejected (D-08 SYERP guard)
    always_on: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # Sidebar display order; lower = higher in list
    sort_order: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
```

**Primary key choice:** `key` (natural string PK) rather than a surrogate int. Rationale: the key matches `MODULE_NAME` in each module's `__init__.py`; join queries and API paths use the key everywhere; no FK references from other tables make surrogate-vs-natural less important. This mirrors how `Permission.code` is the stable identifier in auth models.

**Why `sort_order`:** Sidebar order must be deterministic; seeding can assign sort_order=10 for SYERP, 20 for PLUM, 30 for FLAN, etc. without a migration when new modules are added.

**Idempotent seed — exact pattern from `auth/seed.py`:** [VERIFIED: backend/app/modules/auth/seed.py]

```python
# backend/app/core/modules_seed.py
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.modules_model import Module

# Sourced from code registry at seed time — keeps DB in sync with registry
_MODULE_SEEDS = [
    # (key, display_name, always_on, sort_order)
    ("syerp", "SYERP — ERP Core", True, 10),
    ("plum", "PLUM — Product Lifecycle", False, 20),
    ("flan", "FLAN — Project Management", False, 30),
    ("mousse", "MOUSSE — Manufacturing", False, 40),
    ("crumb", "CRUMB — CRM", False, 50),
    ("gelato", "GELATO — Warehouse", False, 60),
    ("crisp", "CRISP — Quality", False, 70),
]

async def seed_modules_table(db: AsyncSession) -> None:
    """Idempotent module seed — insert only if key not present."""
    for key, display_name, always_on, sort_order in _MODULE_SEEDS:
        result = await db.execute(select(Module).where(Module.key == key))
        if result.scalars().first() is None:
            db.add(Module(
                key=key,
                display_name=display_name,
                enabled=True,        # new modules default ON
                always_on=always_on,
                sort_order=sort_order,
            ))
    await db.commit()
```

**Critical: do NOT read `registry._registry` directly in the seed.** The registry only contains modules that have been imported by `main.py`. Compose profiles control which modules are imported — so a `--profile plum` deployment would only have SYERP+PLUM registered. The seed file should have its own static list derived from the full seven-suite catalog, OR only seed what's currently registered. For a modular-monolith where all modules share one DB, seeding all seven rows (even if some aren't imported in this profile) is the safer approach — it means the Modules admin screen always shows the full catalog with accurate enabled/disabled state, even for not-yet-deployed modules.

**Alternative:** seed only from `registry._registry`. Simpler but means a `--profile plum` deployment hides unregistered modules from the admin UI. Either approach is valid; the static list approach is recommended for the admin experience.

**Wire into `core/seed.py`** [VERIFIED: existing pattern in seed.py]:

```python
# backend/app/core/seed.py (updated)
async def run_seeds(db: "AsyncSession") -> None:
    from app.modules.auth.seed import seed_admin_user
    from app.core.modules_seed import seed_modules_table
    from app.core.settings_seed import seed_default_settings

    await seed_admin_user(db)
    await seed_modules_table(db)
    await seed_default_settings(db)
```

**Wire into `core/models.py`** [VERIFIED: existing pattern in models.py]:

```python
# backend/app/core/models.py (add to Phase 3 block)
from app.core.modules_model import Module        # noqa: F401
from app.core.settings_model import Setting      # noqa: F401
```

---

## Key Pattern 2: `settings` Table — Schema for Extensibility (D-10/D-13)

**Recommended column set** [ASSUMED — derived from D-10/D-13 requirements; no existing schema]:

```python
# backend/app/core/settings_model.py
from __future__ import annotations
from typing import Optional
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import Boolean, String, Text
from app.core.base import Base

class Setting(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # Type hint for deserialization: "str", "bool", "int", "json"
    value_type: Mapped[str] = mapped_column(String(20), default="str", nullable=False)
    # Logical grouping for the admin UI: "company", "locale", "feature"
    category: Mapped[str] = mapped_column(String(50), default="general", nullable=False)
    # D-13 groundwork: scope = "global" now; add "user" scope later without rewrite
    scope: Mapped[str] = mapped_column(String(20), default="global", nullable=False)
    # D-13 groundwork: owner_id = None for global; user.id for per-user override later
    owner_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
```

**Composite primary key consideration:** The natural future extension for per-user settings is (key, scope, owner_id). Today `scope='global'` and `owner_id=None`, so `key` alone as PK works for v1. When per-user settings arrive, the PK will need to become `(key, owner_id)` — that requires a migration. To avoid that migration, the planner may choose a surrogate int PK + unique constraint on `(key, owner_id)` from day one. This is the cleaner D-13 groundwork. [ASSUMED — both approaches valid; surrogate PK avoids a future breaking migration]

**Recommended PK approach for D-13 compatibility:**

```python
class Setting(Base):
    __tablename__ = "settings"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    key: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    # ... other columns as above ...
    __table_args__ = (
        # Unique per (key, owner_id): global setting = (key, NULL); per-user = (key, user_id)
        # Note: PostgreSQL treats NULL != NULL in unique constraints — each NULL owner_id
        # is distinct, which is WRONG for global settings. Use a partial index instead.
    )
```

**PostgreSQL NULL uniqueness pitfall for composite unique:** In PostgreSQL, `(key, NULL)` satisfies a standard UNIQUE constraint for multiple rows because `NULL != NULL`. This means two global settings with the same key would both pass. The correct approach is a partial unique index:

```sql
-- unique global settings
CREATE UNIQUE INDEX uq_settings_global ON settings (key) WHERE owner_id IS NULL;
-- unique per-user settings (add later)
CREATE UNIQUE INDEX uq_settings_user ON settings (key, owner_id) WHERE owner_id IS NOT NULL;
```

In SQLAlchemy, partial indexes are expressed as:
```python
from sqlalchemy import Index
__table_args__ = (
    Index("uq_settings_global", "key", unique=True, postgresql_where=(owner_id == None)),
)
```
[ASSUMED — this is the correct PostgreSQL pattern for nullable composite uniqueness; verified by training knowledge of PostgreSQL NULL semantics]

**v1 seed defaults:**

```python
# backend/app/core/settings_seed.py
_DEFAULT_SETTINGS = [
    # (key, default_value, value_type, category, description)
    ("company.name", "BizNiceSweets", "str", "company", "Company display name shown in the app header"),
    ("company.logo_url", None, "str", "company", "Optional URL to company logo"),
    ("locale.currency", "USD", "str", "locale", "Default currency code (ISO 4217)"),
    ("locale.date_format", "YYYY-MM-DD", "str", "locale", "Default date display format"),
    ("locale.timezone", "UTC", "str", "locale", "Default timezone (IANA tz database)"),
    ("locale.units", "metric", "str", "locale", "Default unit system: metric or imperial"),
]

async def seed_default_settings(db: AsyncSession) -> None:
    for key, value, value_type, category, description in _DEFAULT_SETTINGS:
        result = await db.execute(
            select(Setting).where(Setting.key == key, Setting.owner_id.is_(None))
        )
        if result.scalars().first() is None:
            db.add(Setting(
                key=key, value=value, value_type=value_type,
                category=category, description=description,
                scope="global", owner_id=None,
            ))
    await db.commit()
```

**Key naming convention:** `category.name` (e.g. `company.name`, `locale.currency`). Dotted keys are self-documenting and sort naturally by category. This is the industry-standard key-value settings pattern [ASSUMED].

---

## Key Pattern 3: API Endpoints — Modules + Settings Routers

### Modules router

```python
# backend/app/core/modules_router.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.db import get_db
from app.core.modules_model import Module
from app.core.modules_schemas import ModuleRead, ModuleUpdate
from app.modules.auth.dependencies import get_current_user, require_permission

router = APIRouter(prefix="/core/modules", tags=["core"])

@router.get("", response_model=list[ModuleRead])
async def list_modules(
    current_user=Depends(get_current_user),  # requires auth; all users can read
    db: AsyncSession = Depends(get_db),
):
    """List all modules with their enabled state. Consumed by nav."""
    result = await db.execute(select(Module).order_by(Module.sort_order))
    return result.scalars().all()

@router.patch("/{key}", response_model=ModuleRead)
async def toggle_module(
    key: str,
    data: ModuleUpdate,
    admin=Depends(require_permission("settings:manage")),  # admin-gated
    db: AsyncSession = Depends(get_db),
):
    """Toggle a module's enabled state. Rejects always-on modules (D-08)."""
    result = await db.execute(select(Module).where(Module.key == key))
    mod = result.scalars().first()
    if mod is None:
        raise HTTPException(status_code=404, detail=f"Module '{key}' not found")
    if mod.always_on and data.enabled is False:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Module '{key}' is always-on and cannot be disabled",
        )
    if data.enabled is not None:
        mod.enabled = data.enabled
    await db.commit()
    await db.refresh(mod)
    return mod
```

### Settings router (sketch)

```python
# backend/app/core/settings_router.py
@router.get("", response_model=list[SettingRead])
async def list_settings(
    admin=Depends(require_permission("settings:manage")),
    db: AsyncSession = Depends(get_db),
):
    """List all global settings. Admin-gated (D-12)."""
    result = await db.execute(
        select(Setting)
        .where(Setting.owner_id.is_(None))
        .order_by(Setting.category, Setting.key)
    )
    return result.scalars().all()

@router.patch("/{key}", response_model=SettingRead)
async def update_setting(
    key: str,
    data: SettingUpdate,
    admin=Depends(require_permission("settings:manage")),
    db: AsyncSession = Depends(get_db),
):
    """Update a global setting value. Admin-gated."""
    result = await db.execute(
        select(Setting).where(Setting.key == key, Setting.owner_id.is_(None))
    )
    setting = result.scalars().first()
    if setting is None:
        raise HTTPException(status_code=404, detail=f"Setting '{key}' not found")
    setting.value = data.value
    await db.commit()
    await db.refresh(setting)
    return setting
```

### Module self-registration in main.py

The modules and settings routers live in `core/` — they are not a module package and don't use `registry.register()`. They are imported and mounted directly in `main.py`, before `mount_all()`:

```python
# backend/app/main.py (addition)
from app.core.modules_router import router as modules_router
from app.core.settings_router import router as settings_router

app.include_router(modules_router, prefix="/api/v1", tags=["core"])
app.include_router(settings_router, prefix="/api/v1", tags=["core"])
```

---

## Key Pattern 4: Admin Permission String (D-12)

**Decision for Claude's Discretion:** The existing permission seed in `auth/seed.py` defines these codes:
- `users:manage` — user CRUD
- `syerp:read`, `syerp:write` — SYERP access
- `plum:read`, `plum:write` — PLUM access

[VERIFIED: backend/app/modules/auth/seed.py lines 32-38]

For Phase 3, add a new permission code `settings:manage` (rather than reusing `users:manage`). This keeps concerns separated: an operator might want to grant someone settings management without user-management rights. The seed must add this permission to the `admin` role and to the `_PERMISSIONS` list in `auth/seed.py`.

**Revised `_PERMISSIONS` list** (add this entry):
```python
("settings:manage", "Configure system settings and enable/disable modules"),
```

The `require_permission("settings:manage")` gate covers both the Settings router and the Module toggle router — they are both admin-configuration surfaces and share the same permission scope.

---

## Key Pattern 5: React Router Layout-Route Shell (D-01/D-02/D-03)

**Current `App.tsx` structure** [VERIFIED: frontend/src/App.tsx]:
```tsx
<Routes>
  <Route path="/login" element={<Login />} />
  <Route element={<ProtectedRoute />}>       {/* layout route */}
    <Route path="/" element={<Landing />} />
    <Route path="/admin/users" element={<Users />} />
  </Route>
</Routes>
```

`ProtectedRoute` is already a layout route (renders `<Outlet />`). The shell wraps it — replace the bare `<ProtectedRoute>` element with `<AppShell>` that internally calls `useAuth()` (merging ProtectedRoute's guard) and renders the sidebar+topbar around `<Outlet />`.

**Recommended approach: merge ProtectedRoute into AppShell** rather than nesting two layout routes. The shell already needs auth data (for user name in topbar, role check for admin menu) — it can handle the unauthenticated redirect itself. This avoids an extra React element in the tree.

```tsx
// frontend/src/App.tsx (Phase 3 revision)
import { AppShell } from '@/components/AppShell'

export function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route element={<AppShell />}>          {/* layout route — handles auth guard */}
        <Route path="/" element={<Home />} />
        <Route path="/settings" element={<Settings />} />
        <Route path="/settings/modules" element={<Modules />} />
        <Route path="/admin/users" element={<Users />} />
      </Route>
    </Routes>
  )
}
```

**AppShell component structure:**

```tsx
// frontend/src/components/AppShell.tsx
export function AppShell() {
  const { user, isLoading } = useAuth()
  const location = useLocation()

  // Auth guard (replaces ProtectedRoute)
  if (isLoading) return <FullScreenSpinner />
  if (!user) return <Navigate to="/login" state={{ from: location }} replace />

  return (
    <div className="flex h-screen bg-background">
      {/* Desktop sidebar — hidden on small screens */}
      <aside className="hidden md:flex md:w-64 md:flex-col">
        <Sidebar user={user} />
      </aside>

      {/* Main area */}
      <div className="flex flex-1 flex-col overflow-hidden">
        <Topbar user={user} />
        <main className="flex-1 overflow-y-auto p-4">
          <Outlet />
        </main>
      </div>

      {/* Mobile sidebar — Sheet drawer, triggered from Topbar hamburger */}
    </div>
  )
}
```

**Active-module indicator:** Use `NavLink` from react-router-dom (not plain `Link`). NavLink receives an `isActive` boolean and applies classes conditionally:

```tsx
<NavLink
  to={`/${module.key}`}
  className={({ isActive }) =>
    cn(
      "flex items-center gap-2 rounded-md px-3 py-2 text-sm font-medium transition-colors",
      isActive
        ? "bg-accent text-accent-foreground"
        : "text-muted-foreground hover:bg-muted hover:text-foreground"
    )
  }
>
  {module.display_name}
</NavLink>
```

[VERIFIED: react-router-dom 7 NavLink API matches this pattern — training knowledge, HIGH confidence for stable API]

**Mobile Sheet sidebar:**

```tsx
// Sheet side="left" for the mobile nav drawer
<Sheet open={mobileOpen} onOpenChange={setMobileOpen}>
  <SheetContent side="left" className="w-64 p-0">
    <Sidebar user={user} onNavigate={() => setMobileOpen(false)} />
  </SheetContent>
</Sheet>
```

The `SheetContent side="left"` variant is already in the installed `sheet.tsx`. [VERIFIED: frontend/src/components/ui/sheet.tsx — `side: "left"` is a valid variant]

---

## Key Pattern 6: Nav Visibility Logic — Client-Side Composition

**The decision (Claude's Discretion):** Compose nav visibility client-side from two queries, not a single backend endpoint.

**Why:** The `/auth/me` endpoint already returns roles. The `GET /api/v1/core/modules` endpoint returns all modules with `enabled` flag. Client-side intersection: `modules.filter(m => m.enabled && userHasPermission(m.key + ':read', user))`. No additional backend endpoint needed. This is consistent with Phase 2 patterns where `/auth/me` is the session source of truth.

**`useModules` hook:**

```typescript
// frontend/src/hooks/useModules.ts
export interface ModuleRecord {
  key: string
  display_name: string
  enabled: boolean
  always_on: boolean
  sort_order: number
}

export function useModules() {
  return useQuery<ModuleRecord[], Error>({
    queryKey: ['core', 'modules'],
    queryFn: () => apiClient.get<ModuleRecord[]>('/api/v1/core/modules').then(r => r.data),
    staleTime: 10_000,   // short staleTime so focus-refetch picks up toggle changes quickly
  })
}
```

**Permission check helper:**

```typescript
// The nav uses this to filter: show module if enabled AND user has <key>:read
function userCanSeeModule(moduleKey: string, user: AuthUser): boolean {
  // Admin role is wildcard — sees all enabled modules
  if (user.roles.some(r => r.name === 'admin')) return true
  // Check if permissions include <moduleKey>:read
  // NOTE: AuthUser.roles only includes {id, name, description} currently.
  // Phase 3 will need to extend AuthUser with permission codes OR derive from roles.
  ...
}
```

**IMPORTANT GAP — `AuthUser` does not expose permissions:** [VERIFIED: frontend/src/hooks/useAuth.ts]

The current `AuthUser` interface only has `roles: Array<{ name: string }>` — it does not include flat permission codes. The nav filter needs to know if the user has e.g. `plum:read`. Three options:

1. **Extend `UserRead` schema to include flat `permissions: string[]`** — cleanest. Add a `permissions` field to the Pydantic `UserRead` schema populated by `collect_permissions(user)` (already exists in `auth/service.py`). Update `AuthUser` TS interface to include `permissions: string[]`. Nav filter: `user.permissions.includes(moduleKey + ':read')`.

2. **Infer from role name** — `'admin'` wildcard is already handled. Standard `'user'` role has all business read/write permissions. But this is fragile and breaks if roles diverge.

3. **Separate `/api/v1/core/nav` endpoint** — backend computes intersection, returns only modules user should see. Cleaner for future but extra endpoint.

**Recommendation:** Option 1. Extend `UserRead` + `AuthUser` to include `permissions: string[]`. The `collect_permissions()` function in `auth/service.py` already computes this for the JWT — reuse it in the `/auth/me` response. This is a minimal additive change to Phase 2 schemas and is the right long-term shape. [ASSUMED — no user confirmation needed; this is a builder's-discretion improvement]

---

## Key Pattern 7: TanStack Query Refetch for Toggle Propagation (D-09)

**Global queryClient config** [VERIFIED: frontend/src/lib/queryClient.ts]:
- `refetchOnWindowFocus: false` (global default)
- `staleTime: 30_000`
- `retry: 1`

**Propagation strategy for module toggle:**

When admin PATCHes a module enabled state:
1. The mutation's `onSuccess` callback calls `queryClient.invalidateQueries({ queryKey: ['core', 'modules'] })`.
2. All components using `useModules()` will refetch immediately (invalidation triggers background refetch).
3. The `staleTime: 10_000` on `useModules` means other open browser tabs (same session) will refetch when navigating between routes (React Query refetches stale queries on component mount).

**For the "disappears for all users" requirement:** In a single-instance deployment, all users share the same backend. After toggle, any user who navigates (mounts a component consuming `useModules`) gets fresh data within ~10 seconds of their next navigation. This satisfies D-09.

**`refetchOnWindowFocus` for admin changes:** The global default is `false`. Override it for `useModules` specifically with `refetchOnWindowFocus: true` so that if an admin toggles a module in one tab, all other tabs refetch when the user focuses them.

```typescript
export function useModules() {
  return useQuery<ModuleRecord[], Error>({
    queryKey: ['core', 'modules'],
    queryFn: () => apiClient.get<ModuleRecord[]>('/api/v1/core/modules').then(r => r.data),
    staleTime: 10_000,
    refetchOnWindowFocus: true,  // override global false for this query
  })
}
```

**Toggle mutation pattern:**

```typescript
// Inside Modules.tsx admin screen
const queryClient = useQueryClient()
const toggleMutation = useMutation({
  mutationFn: ({ key, enabled }: { key: string; enabled: boolean }) =>
    apiClient.patch(`/api/v1/core/modules/${key}`, { enabled }).then(r => r.data),
  onSuccess: () => {
    queryClient.invalidateQueries({ queryKey: ['core', 'modules'] })
  },
})
```

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Responsive sidebar on mobile | Custom drawer component | shadcn `Sheet` (already installed) | Radix Dialog handles focus trap, escape key, accessibility |
| User/admin dropdown menu | Custom positioned div | shadcn `DropdownMenu` (already installed) | Radix handles keyboard nav, aria, positioning |
| Module enable toggle | Custom checkbox or button | shadcn `Switch` (add via `npx shadcn@latest add switch`) | Accessible toggle with correct ARIA role="switch" |
| Nav active state | Manual className comparison with `window.location` | React Router `NavLink` `isActive` prop | Handles nested routes, active states on SSR-safe way |
| Permission check on frontend | Re-implementing RBAC logic | Read `user.permissions[]` from `/auth/me` | Backend is source of truth; frontend just reads the list |
| Settings key uniqueness for per-user | Manual `NULL` uniqueness workaround | PostgreSQL partial index (`WHERE owner_id IS NULL`) | Standard SQL pattern; avoids NULL comparison pitfall |
| Module always-on enforcement | Frontend-only guard | Backend 422 rejection + frontend disabled Switch | UI gating is convenience only; backend enforces invariant |

---

## Common Pitfalls

### Pitfall 1: Alembic autogenerate misses new tables in `core/`
**What goes wrong:** New ORM models added to `core/modules_model.py` and `core/settings_model.py` are not discovered by `alembic revision --autogenerate`.
**Why it happens:** `alembic/env.py` imports `app.core.models` — only what's imported there is in `Base.metadata`.
**How to avoid:** Add import lines to `core/models.py` for both new models [VERIFIED: this is the documented pattern in core/models.py docstring].
**Warning sign:** Running `alembic revision --autogenerate` produces an empty migration (no `op.create_table` calls).

### Pitfall 2: `lazy="selectin"` missing on Module relationships (if any are added)
**What goes wrong:** `MissingGreenlet` exception when accessing unloaded relationship outside async context.
**Why it happens:** SQLAlchemy 2.0 async engine requires explicit loading strategy; default lazy load triggers sync greenlet that doesn't exist in async context.
**How to avoid:** The `modules` and `settings` tables have no relationships in v1 — this pitfall doesn't apply yet. Add `lazy="selectin"` on any future relationship added to these models. [VERIFIED: auth/models.py comment on lazy="selectin"]

### Pitfall 3: Layout route nesting — double outlet renders
**What goes wrong:** Both `ProtectedRoute` and `AppShell` are layout routes wrapping the same children; children render twice or not at all.
**Why it happens:** React Router 7 layout routes require exactly one `<Outlet />` rendering path.
**How to avoid:** Merge `ProtectedRoute`'s auth guard logic directly into `AppShell` rather than nesting `<AppShell>` inside `<ProtectedRoute>`. The existing `ProtectedRoute.tsx` can be removed or repurposed as a `useRequireAuth` hook.

### Pitfall 4: `AuthUser` missing `permissions` — nav always shows nothing for non-admin
**What goes wrong:** Nav filter checks `user.permissions.includes('plum:read')` but `permissions` is `undefined`; all non-admin users see no modules.
**Why it happens:** `AuthUser` interface only has `roles: Array<{ name: string }>` currently.
**How to avoid:** Extend `UserRead` Pydantic schema to include `permissions: list[str]` populated by `collect_permissions(user)`. Update `AuthUser` TS interface accordingly. This must happen in Phase 3. [VERIFIED: gap confirmed by reading useAuth.ts and schemas.py]

### Pitfall 5: PostgreSQL NULL uniqueness on `settings` table
**What goes wrong:** Two rows with `key='company.name'` and `owner_id=NULL` both pass a standard `UNIQUE (key, owner_id)` constraint.
**Why it happens:** PostgreSQL treats `NULL != NULL` in unique constraint evaluation.
**How to avoid:** Use a partial unique index `UNIQUE (key) WHERE owner_id IS NULL` for global settings. [VERIFIED: standard PostgreSQL behavior]

### Pitfall 6: `queryClient` invalidation targeting wrong query key
**What goes wrong:** After toggle mutation, the nav doesn't update because the invalidation key doesn't match the query key.
**Why it happens:** `queryClient.invalidateQueries({ queryKey: ['modules'] })` doesn't match `useQuery({ queryKey: ['core', 'modules'] })`.
**How to avoid:** Standardize query keys. Use `['core', 'modules']` everywhere. `invalidateQueries` does prefix-matching by default in TanStack Query 5 — `['core']` would invalidate all core queries; `['core', 'modules']` is more precise. [VERIFIED: TanStack Query 5 behavior — training knowledge]

### Pitfall 7: `always_on` enforcement is frontend-only
**What goes wrong:** Admin can POST directly to `PATCH /api/v1/core/modules/syerp` with `enabled: false` and disable SYERP.
**Why it happens:** Developer implements the guard only in the UI (disabling the Switch) but forgets the backend check.
**How to avoid:** The backend PATCH handler must explicitly check `if mod.always_on and data.enabled is False: raise 422`. The frontend disabled Switch is UX convenience; the backend 422 is the real enforcement. [VERIFIED: D-08 requirement]

### Pitfall 8: Settings PATCH overwrites to `None` when field is omitted in PATCH body
**What goes wrong:** Admin updates `company.name` but the PATCH body only includes `value`; Pydantic sets other optional fields to `None`, overwriting DB values.
**Why it happens:** Pydantic model `SettingUpdate(value: str | None = None)` can't distinguish "field omitted" vs "field explicitly set to None".
**How to avoid:** Use `model_exclude_unset=True` pattern or `model_config = {"populate_by_name": True}` — same PATCH semantics as `UserUpdate` in Phase 2. Only update fields that are explicitly set.

```python
# PATCH handler pattern
for field, val in data.model_dump(exclude_unset=True).items():
    setattr(setting, field, val)
```

---

## Code Examples

### Pydantic schemas

```python
# backend/app/core/modules_schemas.py
from pydantic import BaseModel
from typing import Optional

class ModuleRead(BaseModel):
    key: str
    display_name: str
    enabled: bool
    always_on: bool
    sort_order: int
    model_config = {"from_attributes": True}

class ModuleUpdate(BaseModel):
    enabled: Optional[bool] = None

# backend/app/core/settings_schemas.py
class SettingRead(BaseModel):
    key: str
    value: Optional[str]
    value_type: str
    category: str
    scope: str
    description: Optional[str]
    model_config = {"from_attributes": True}

class SettingUpdate(BaseModel):
    value: Optional[str] = None  # set to None to clear; omit to leave unchanged
```

### Extended `UserRead` schema (adds permissions)

```python
# backend/app/modules/auth/schemas.py — extend UserRead
class UserRead(BaseModel):
    id: str
    email: str
    full_name: Optional[str] = None
    is_active: bool
    roles: List[RoleRead] = []
    permissions: List[str] = []  # flat permission codes e.g. ["syerp:read", "plum:write"]
    model_config = {"from_attributes": True}
```

The `/auth/me` endpoint returns a `User` ORM object. The `UserRead.permissions` field requires a validator or computed field — the cleanest approach is to populate it in the endpoint or use a `@model_validator`:

```python
# Alternative: populate in the /me endpoint directly
@router.get("/me", response_model=UserRead)
async def me(current_user=Depends(get_current_user)) -> UserRead:
    from app.modules.auth.service import collect_permissions
    user_dict = {
        "id": current_user.id,
        "email": current_user.email,
        "full_name": current_user.full_name,
        "is_active": current_user.is_active,
        "roles": current_user.roles,
        "permissions": collect_permissions(current_user),
    }
    return UserRead.model_validate(user_dict)
```

`collect_permissions()` is already implemented in `auth/service.py` [VERIFIED: auth/service.py line 14].

### TypeScript `AuthUser` update

```typescript
// frontend/src/hooks/useAuth.ts — extend AuthUser
export interface AuthUser {
  id: string
  email: string
  full_name: string | null
  is_active: boolean
  roles: Array<{ name: string }>
  permissions: string[]   // add this
}
```

### Nav visibility filter function

```typescript
// Computes which modules to show in the sidebar
function useVisibleModules(): ModuleRecord[] {
  const { user } = useAuth()
  const { data: modules = [] } = useModules()

  return modules.filter(mod => {
    if (!mod.enabled) return false
    if (!user) return false
    // Admin role is wildcard
    if (user.roles.some(r => r.name === 'admin')) return true
    // Standard user: must have <key>:read permission
    return user.permissions.includes(`${mod.key}:read`)
  })
}
```

---

## State of the Art

| Old Approach | Current Approach | Impact |
|--------------|------------------|--------|
| Hardcoded nav links | DB-backed modules table, seeded from registry | Admin can toggle; nav is data-driven |
| `ProtectedRoute` as separate layout component | Merge into `AppShell` layout route | Fewer React tree layers; auth + chrome in one component |
| Returning only `roles[]` from `/auth/me` | Return `permissions: string[]` too | Frontend can do proper permission-based UI decisions |
| Single-row typed settings table | Key-value `settings` table with `value_type` | Additive settings growth without migrations |

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `modules` table uses natural string PK (`key`) with no FK references | Pattern 1 | Low — no FK references planned; surrogate PK is easy to switch in the migration |
| A2 | `settings` table uses surrogate int PK + partial index for NULL uniqueness | Pattern 2 | Medium — wrong PK choice requires a later migration if per-user settings arrive differently |
| A3 | `settings:manage` is the correct new permission code (not reusing `users:manage`) | Pattern 4 | Low — admin role is wildcard anyway; only affects standard-role permission assignment |
| A4 | Static `_MODULE_SEEDS` list in `modules_seed.py` rather than reading `registry._registry` | Pattern 1 | Low — both approaches work; static list is safer for partial Compose profiles |
| A5 | Merging `ProtectedRoute` into `AppShell` (single layout component) | Pattern 5 | Low — nesting also works in React Router 7; merge is cleaner |
| A6 | `useModules` returns all modules (admin sees always-on flag + disabled); nav filter applies on client | Pattern 6 | Low — alternative is a `/api/v1/core/nav` endpoint; client-side is simpler |
| A7 | `collect_permissions()` reused to populate `permissions` in `/auth/me` response | Pattern, Code Examples | Low — function already exists; interface extension is straightforward |

---

## Open Questions

1. **Should `GET /api/v1/core/modules` require authentication, or be public?**
   - What we know: The nav is only shown to authenticated users; unauthenticated visitors only see `/login`.
   - What's unclear: Whether the list of module names is considered sensitive.
   - Recommendation: Require auth (use `get_current_user` dependency). The modules list is not public information. This also means unauthenticated requests to the shell API fail cleanly with 401.

2. **Should `GET /api/v1/core/settings` be auth-required (any user) or admin-only?**
   - What we know: The shell header needs `company.name` which must be readable by all users (D-02).
   - What's unclear: Whether all settings fields or only specific keys should be readable by all users.
   - Recommendation: Two options: (a) allow `GET /core/settings` for any authenticated user (simpler, but exposes all setting keys/values including locale defaults that are non-sensitive); (b) add a `GET /core/settings/public` endpoint returning only company-identity fields for the shell header. Option (a) is simpler and the settings in v1 are all non-sensitive — recommended.

3. **How does the `modules` table handle modules not yet in `registry._registry`?**
   - What we know: The static seed list includes all 7 suites; only SYERP+auth are imported in main.py today.
   - What's unclear: Whether the Modules admin UI should show PLUM/FLAN/etc. before Phase 5/6 ships them.
   - Recommendation: Seed all 7 rows but mark non-shipped modules `enabled=false` by default; the admin UI can display them as "not yet available" (or just show the enabled toggle greyed out). This gives the admin visibility without breaking anything.

---

## Environment Availability

All required dependencies are already installed in the repo. No new backend packages are needed; only one new frontend shadcn component (`Switch`) is needed.

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| shadcn Switch | Module toggle UI | Not installed | — | Install via `npx shadcn@latest add switch` |
| @radix-ui/react-switch | shadcn Switch | Not installed | — | Installed automatically by shadcn add |
| All other deps | Shell, settings, modules | Installed | See requirements.txt / package.json | — |

**Missing dependencies with no fallback:** None — `Switch` install is trivial.

**Missing dependencies with fallback:** None.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Backend framework | pytest + httpx ASGITransport (pytest-asyncio auto mode) [VERIFIED: pyproject.toml, conftest.py] |
| Frontend framework | Vitest + Testing Library + jsdom [VERIFIED: package.json] |
| Backend config file | `backend/pyproject.toml` `[tool.pytest.ini_options]` |
| Frontend config file | Vite config (vitest co-located) |
| Backend quick run | `cd backend && pytest tests/ -x -q` |
| Frontend quick run | `cd frontend && npm test` |
| Backend full suite | `cd backend && pytest tests/ -v` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| CORE-07 | GET /core/modules returns list with enabled flag | integration | `pytest tests/core/test_modules.py -x` | Wave 0 |
| CORE-07 | PATCH /core/modules/syerp {enabled:false} returns 422 (always-on guard) | integration | `pytest tests/core/test_modules.py::test_cannot_disable_always_on -x` | Wave 0 |
| CORE-07 | PATCH /core/modules/plum {enabled:false} returns 200, module now disabled | integration | `pytest tests/core/test_modules.py::test_toggle_module -x` | Wave 0 |
| CORE-07 | Non-admin PATCH /core/modules returns 403 | integration | `pytest tests/core/test_modules.py::test_toggle_requires_admin -x` | Wave 0 |
| CORE-06 | GET /core/settings returns settings list (admin) | integration | `pytest tests/core/test_settings.py -x` | Wave 0 |
| CORE-06 | PATCH /core/settings/company.name updates value | integration | `pytest tests/core/test_settings.py::test_update_setting -x` | Wave 0 |
| CORE-06 | Seed populates default settings including company.name | integration | `pytest tests/core/test_settings.py::test_seed_defaults -x` | Wave 0 |
| CORE-08 | /auth/me response includes `permissions` list | integration | `pytest tests/auth/test_login.py::test_me_includes_permissions -x` | Wave 0 |
| CORE-08 | Shell renders with sidebar nav (smoke) | e2e/manual | Manual browser check | N/A — manual |
| CORE-08 | Disabled module nav entry disappears after toggle | e2e/manual | Manual browser check | N/A — manual |

### Sampling Rate
- Per task commit: `cd backend && pytest tests/core/ -x -q`
- Per wave merge: `cd backend && pytest tests/ -v`
- Phase gate: Full backend suite green + manual browser smoke test before `/gsd-verify-work`

### Wave 0 Gaps

- [ ] `backend/tests/core/__init__.py` — test package for core tests
- [ ] `backend/tests/core/test_modules.py` — covers CORE-07 (list, toggle, always-on guard, 403)
- [ ] `backend/tests/core/test_settings.py` — covers CORE-06 (list, update, seed defaults)
- [ ] `backend/tests/core/conftest.py` — seeded DB fixture for modules + settings rows
- [ ] Frontend test: `frontend/src/components/AppShell.test.tsx` — render with mock user, verify nav items shown/hidden

---

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No (Phase 2 shipped this) | — |
| V3 Session Management | No (Phase 2 shipped this) | — |
| V4 Access Control | Yes | `require_permission("settings:manage")` on all admin endpoints |
| V5 Input Validation | Yes | Pydantic schemas on all request bodies; always-on rejection in endpoint |
| V6 Cryptography | No | No new crypto in this phase |

### Known Threat Patterns for This Phase

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Non-admin disabling modules via direct API call | Tampering | `require_permission("settings:manage")` on PATCH endpoint; frontend disable is UX-only |
| Admin disabling SYERP via API | Tampering | Backend 422 when `always_on=true`; frontend Switch disabled with tooltip |
| Unauthenticated access to modules list | Information Disclosure | `get_current_user` dependency on GET /core/modules |
| Settings injection (script in company.name) | Tampering | Pydantic `str` type validates; React renders as text (not innerHTML), so XSS not applicable in the shell header |
| Privilege escalation via `owner_id` in settings | Elevation of Privilege | In Phase 3, all settings are global-only; `owner_id` is not a user-settable field — server always sets scope/owner_id |

---

## Sources

### Primary (HIGH confidence — verified by reading actual source files)
- `backend/app/core/registry.py` — Module Protocol, `_registry` list, `MODULE_NAME` pattern
- `backend/app/core/models.py` — aggregator import pattern for Alembic autogenerate
- `backend/app/core/seed.py` — `run_seeds()` hook, Phase 2 extension point
- `backend/app/core/base.py` — `AsyncAttrs + DeclarativeBase`, `awaitable_attrs` pattern
- `backend/app/core/db.py` — `AsyncSessionLocal`, `get_db` dependency pattern
- `backend/app/core/config.py` — `Settings` class, `SecretStr` pattern
- `backend/app/modules/auth/models.py` — `mapped_column`, `lazy="selectin"`, UUID string PK pattern
- `backend/app/modules/auth/seed.py` — exact idempotent select-before-insert seed pattern
- `backend/app/modules/auth/dependencies.py` — `require_permission()` factory signature
- `backend/app/modules/auth/schemas.py` — `UserRead`, `model_config = {"from_attributes": True}`
- `backend/app/modules/auth/router.py` — admin-gated endpoint pattern, audit log writes
- `backend/app/main.py` — module import + `mount_all()` + SPAStaticFiles pattern, `lifespan` + seed call
- `backend/alembic/env.py` — `import app.core.models` critical side-effect for autogenerate
- `frontend/src/App.tsx` — current layout route structure
- `frontend/src/components/ProtectedRoute.tsx` — auth guard + Outlet pattern
- `frontend/src/hooks/useAuth.ts` — `AuthUser` interface, `useQuery` pattern, staleTime
- `frontend/src/lib/queryClient.ts` — global QueryClient config (staleTime, refetchOnWindowFocus, retry)
- `frontend/src/api/client.ts` — `apiClient` axios instance, interceptor chain
- `frontend/src/auth/token.ts` — in-memory token storage pattern
- `frontend/src/components/ui/sheet.tsx` — `side="left"` variant confirmed available
- `frontend/src/components/ui/dropdown-menu.tsx` — available
- `frontend/package.json` — all installed deps and versions
- `backend/requirements.txt` — all backend deps and versions
- `backend/tests/conftest.py` — test fixture patterns, env var injection

### Secondary (MEDIUM confidence)
- React Router 7 NavLink API — training knowledge, stable API, HIGH confidence for `isActive` prop
- TanStack Query 5 `invalidateQueries` prefix matching — training knowledge, HIGH confidence for stable v5 API
- PostgreSQL NULL uniqueness behavior in UNIQUE constraints — training knowledge, well-established behavior

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries verified from package.json and requirements.txt
- Architecture patterns: HIGH — derived from existing repo code; module/seed/router patterns directly observed
- `modules` table schema: HIGH — column set derived from locked decisions D-07/D-08 and existing model patterns
- `settings` table schema: MEDIUM — D-10/D-13 shape is correct; NULL uniqueness partial-index recommendation is training knowledge
- TanStack Query propagation: MEDIUM — invalidation pattern is correct; exact staleTime tuning may need adjustment
- Pitfalls: HIGH — most derived from actual repo code (lazy="selectin" comment in models.py, Alembic env.py note)

**Research date:** 2026-06-26
**Valid until:** 2026-07-26 (30 days; stable stack)
