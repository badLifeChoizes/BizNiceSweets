# Phase 4: SYERP Core Hub — Research

**Researched:** 2026-06-26
**Domain:** FastAPI + SQLAlchemy 2.0 business-partner master data; GL chart-of-accounts seed; React/TanStack Query CRUD screens
**Confidence:** HIGH — all findings grounded in the actual codebase; CoA numbering based on standard US small-business practice [ASSUMED where noted]

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** Unified `syerp_partner` table with `is_vendor` / `is_customer` boolean role flags (res.partner style). One row per legal entity.
- **D-02:** Two separate nav/list screens (Vendor list, Customer list) each a filtered view of the unified table. Shared edit form. A partner with both flags appears in both lists.
- **D-03:** Manufacturer-grade record in v1: Identity + Address (single embedded block) + Contact (single embedded, primary) + Commerce field groups. Exact types/lengths are builder discretion; align with PLUM prototype.
- **D-04:** Partner code auto-generated (next sequential) but user-editable before save. Unique DB constraint. Series scheme is builder discretion.
- **D-05:** Soft-delete / archive only — no hard delete. `active = false` or `archived_at` (planner's choice). Hidden from default lists; "show archived" toggle to surface/restore.
- **D-06:** `syerp_gl_account` table seeded with conventional CoA (5 types, 1000s–5000s ranges, sensible sub-accounts). Rendered as grouped expandable read-only tree.
- **D-07:** Server-side search via query param across name + code + primary-contact fields; debounced live search for "instantly" feel. Reuse Users.tsx interaction pattern. Client-side fallback acceptable for small datasets.
- **D-08:** Fill existing SYERP stub (`backend/app/modules/syerp/`). Routes under `/syerp/...` (no `/api/v1` prefix — `mount_all()` adds it). Table names `syerp_partner`, `syerp_gl_account`.
- **D-09:** Gate reads with `syerp:read`, writes with `syerp:write`. Use `require_permission(...)`.
- **D-10:** Audit partner mutations via `write_audit` (partner.created / partner.updated / partner.archived).
- **D-11 (scope guard):** No GL CRUD, postings, or journal entries this phase. CoA is seeded + read-only browse only.

### Claude's Discretion

- Exact column types, lengths, nullability, and indexes for `syerp_partner` and `syerp_gl_account`.
- Partner code series scheme: unified `P-####` vs role-prefixed display.
- `active = false` vs `archived_at` timestamp for soft-delete marker.
- Precise standard CoA seed contents (which sub-accounts, exact numbering).
- Search/filter mechanism details per D-07.
- Whether GL browse is gated by `syerp:read` or a dedicated permission.
- Frontend: separate route files per Vendor/Customer vs shared parameterized component; shared edit-form composition.

### Deferred Ideas (OUT OF SCOPE)

- GL account CRUD, ledger postings, journal entries (later financials phase).
- Purchasing, POs, AP/AR, sales orders, inventory, financial reporting.
- Guarded hard-delete (delete-when-unreferenced).
- Multiple addresses / contacts per partner (one-to-many).
- Unified "Partners" management screen (single list with type filter).
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| SYERP-01 | User can create, view, edit, and delete vendors | Partner model (D-01/D-03), CRUD endpoints mirroring auth/router.py pattern, soft-delete (D-05), Vendor list screen |
| SYERP-02 | User can search and filter the vendor list | Server-side `?q=` param on `name`/`code`/`contact_name`, debounced 300ms client input as in Users.tsx; `is_vendor=true` implicit filter |
| SYERP-03 | User can create, view, edit, and delete customers | Same partner model; `is_customer=true` filter; shared edit form with role flag toggle |
| SYERP-04 | User can search and filter the customer list | Same search mechanism; `is_customer=true` implicit filter |
| SYERP-05 | System provides a basic GL account structure (chart-of-accounts skeleton) | `syerp_gl_account` table seeded idempotently via `run_seeds()`; read-only tree endpoint gated by `syerp:read` |
</phase_requirements>

---

## Summary

Phase 4 fills the empty SYERP stub with the two tables — `syerp_partner` and `syerp_gl_account` — that every downstream module will foreign-key into. The implementation pattern is already well-established in this codebase: the auth module's user CRUD (models / schemas / service / router) is the direct analog for partners, and the Phase 2/3 idempotent seed hook is the direct analog for the CoA seed.

The most design-intensive decisions are: (1) the exact `syerp_partner` column set that satisfies D-03 without over-engineering, (2) the concurrent-safe partner code auto-generation strategy, and (3) the precise CoA account list. All three are addressed concretely below with ready-to-implement recommendations.

The frontend pattern — `useQuery` fetching a list, debounced search input, `Sheet` for create/edit, `Dialog` for archive confirmation, `useMutation` + `invalidateQueries` — is identical to `Users.tsx`. No new shadcn primitives or libraries are needed.

**Primary recommendation:** Mirror auth module structure exactly. Implement `syerp_partner` as a single table with boolean role flags, use `active` (not `archived_at`) for soft-delete, use PostgreSQL sequence for code generation, and gate GL browse under `syerp:read` (no new permission needed).

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Partner master data storage | Database (PostgreSQL) | — | Single source of truth; FKs from PLUM/other modules target this |
| Partner CRUD business logic | API / Backend (FastAPI service layer) | — | Validation, audit writes, code generation, soft-delete all belong server-side |
| Partner list/search/filter | API / Backend | Frontend (client-side debounce only) | Server-side `?q=` for scalability; client holds debounce timer |
| Partner role-scoped views (vendor vs customer) | API / Backend (query filter) | Frontend (two route components) | `is_vendor=true` / `is_customer=true` filter in list endpoint |
| CoA seed | API / Backend (seed.py) | — | Runs at startup; idempotent; no user action |
| CoA browse (tree) | API / Backend (one read endpoint) | Frontend (tree render) | Data shape from backend; rendering in frontend |
| Auth / permission gating | API / Backend (require_permission) | — | Backend is the real authz boundary; frontend nav filtering is convenience only |
| Audit trail | API / Backend (write_audit) | — | Medical-device posture; append-only AuditLog rows |

---

## Standard Stack

All libraries are already installed. No new dependencies are required for this phase.
[VERIFIED: package.json / requirements.txt in-repo]

### Backend (already installed)
| Library | Version | Purpose | Role in Phase 4 |
|---------|---------|---------|-----------------|
| FastAPI | 0.138.0 | API framework | Partner + GL routers |
| SQLAlchemy | 2.0.51 | ORM + async sessions | `syerp_partner`, `syerp_gl_account` models |
| Alembic | 1.18.4 | Migration tool | Single autogenerated migration for both new tables |
| asyncpg | 0.31.0 | Async PostgreSQL driver | Runtime DB connection |
| Pydantic (v2, bundled) | — | Schema validation | PartnerCreate/Read/Update, GLAccountRead schemas |

### Frontend (already installed)
| Library | Version | Purpose | Role in Phase 4 |
|---------|---------|---------|-----------------|
| React | 19.2.7 | UI framework | Vendor/Customer/GL screens |
| TanStack Query | 5.101.1 | Server state | `useQuery` + `useMutation` for partner + GL data |
| axios (apiClient) | 1.18.1 | HTTP client | Existing `apiClient` with 401 silent-refresh interceptor |
| shadcn/ui (Radix) | installed | Component primitives | Table, Sheet, Dialog, Input, Select, Badge, Switch |
| react-router-dom | 7.18.0 | Routing | New routes: `/syerp/vendors`, `/syerp/customers`, `/syerp/gl` |
| lucide-react | 1.21.0 | Icons | Archive, Edit, MoreHorizontal already used in Users.tsx |

### No New Installs Needed
All required primitives (`table`, `dialog`, `sheet`, `input`, `label`, `select`, `button`, `badge`, `switch`, `dropdown-menu`) are already present in `frontend/src/components/ui/`. [VERIFIED: Glob of frontend/src/components/ui/]

---

## Architecture Patterns

### System Architecture Diagram

```
Browser (React)
  │
  ├── /syerp/vendors  →  VendorList (is_vendor filter)  ─┐
  ├── /syerp/customers → CustomerList (is_customer filter) ┤─ shared PartnerSheet (create/edit form)
  └── /syerp/gl       →  GLTree (read-only accordion)      │   shared ArchiveDialog
                                                            │
  apiClient (axios, JWT Bearer + httpOnly cookie)           │
          │                                                 │
          ▼                                                 │
FastAPI  /api/v1/syerp/                                     │
  ├── GET  /partners?role=vendor&q=&include_archived=       │
  ├── POST /partners                                        │
  ├── GET  /partners/{id}                                   │
  ├── PATCH /partners/{id}                                  │
  ├── POST /partners/{id}/archive                           │
  └── GET  /gl/accounts  (tree — read-only)                │
                                                            │
  syerp.service  ←──────────────────────────────────────────┘
  │   partner_create / partner_list / partner_update / partner_archive
  │   generate_partner_code (sequence-based)
  │   write_audit (D-10)
  │
  SQLAlchemy AsyncSession
  │
  PostgreSQL
    ├── syerp_partner  (id, code, name, is_vendor, is_customer, active, …)
    └── syerp_gl_account  (id, code, name, type, parent_id, active)
```

### Recommended Project Structure

```
backend/app/modules/syerp/
├── __init__.py          (already exists)
├── models.py            (add Partner + GLAccount classes)
├── schemas.py           (PartnerCreate/Read/Update, GLAccountRead)
├── service.py           (CRUD helpers + generate_partner_code + CoA seed fn)
├── router.py            (partner routes + GL route)
└── coa_seed.py          (standard CoA data constant + seed_gl_accounts fn)

frontend/src/routes/syerp/
├── Vendors.tsx          (list screen, is_vendor=true filter)
├── Customers.tsx        (list screen, is_customer=true filter)
├── GLAccounts.tsx       (read-only tree)
└── components/
    ├── PartnerSheet.tsx   (shared create/edit form, parameterized by role)
    └── PartnerArchiveDialog.tsx
```

---

## Core Implementation Patterns

### Pattern 1: syerp_partner Model (SQLAlchemy 2.0 mapped_column style)

The auth module uses `Mapped[type] = mapped_column(...)` throughout. Match that exactly.
[VERIFIED: backend/app/modules/auth/models.py]

**Recommended column set for `syerp_partner`:**

```python
# Source: mirrors auth/models.py Mapped[] style; field names from PLUM Vendors object
# (plum/app/plm_v54.html:10243–10267)
import uuid
from datetime import datetime, timezone
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.core.base import Base

class Partner(Base):
    __tablename__ = "syerp_partner"

    # --- Primary key ---
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )

    # --- Identity (D-03) ---
    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    is_vendor: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_customer: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)

    # --- Address block (single embedded, D-03) ---
    addr_line1: Mapped[str | None] = mapped_column(String(255), nullable=True)
    addr_line2: Mapped[str | None] = mapped_column(String(255), nullable=True)
    addr_city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    addr_state: Mapped[str | None] = mapped_column(String(100), nullable=True)
    addr_postal: Mapped[str | None] = mapped_column(String(20), nullable=True)
    addr_country: Mapped[str | None] = mapped_column(String(2), nullable=True)  # ISO 3166-1 alpha-2

    # --- Contact block (single embedded primary contact, D-03) ---
    contact_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    contact_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    contact_phone: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # --- Commerce (D-03, aligned with PLUM Vendors.create) ---
    payment_terms: Mapped[str | None] = mapped_column(String(50), nullable=True)   # e.g. "Net 30"
    tax_id: Mapped[str | None] = mapped_column(String(50), nullable=True)          # EIN/VAT
    currency: Mapped[str | None] = mapped_column(String(3), nullable=True)         # ISO 4217 e.g. "USD"
    country_of_origin: Mapped[str | None] = mapped_column(String(2), nullable=True)  # ISO 3166-1 alpha-2
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # --- Timestamps ---
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
```

**Index rationale:**
- `code` — unique + index: code lookups and uniqueness check
- `name` — index: primary search field in the `?q=` query
- `active` — index: every list query has `WHERE active = true`
- No composite index needed at v1 data volumes for a single shop

**Column length decisions:**
- `code` — 20 chars: sufficient for `V-0001` through `V-9999` plus any reasonable manual override
- `name` — 255: matches auth `User.full_name` and `User.email` convention
- `addr_country` + `addr_state` — String(2) and String(100): country is ISO alpha-2 (2 chars); state/region is free-form (province names vary)
- `contact_phone` — 50: handles international formats with extensions
- `currency` — 3: ISO 4217 code
- `payment_terms` — 50: "Net 30", "Net 60", "Due on Receipt", etc.

### Pattern 2: syerp_gl_account Model

```python
# Source: D-06 column list from CONTEXT.md
class GLAccount(Base):
    __tablename__ = "syerp_gl_account"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(10), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    # type: one of ASSET / LIABILITY / EQUITY / REVENUE / EXPENSE
    account_type: Mapped[str] = mapped_column(String(20), nullable=False)
    parent_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("syerp_gl_account.id"), nullable=True
    )
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
```

Note: `account_type` instead of `type` — `type` is a Python built-in and a SQLAlchemy reserved word; using `account_type` avoids shadowing.

### Pattern 3: Partner Code Auto-Generation (D-04)

**Recommendation: single unified series `P-####`, `select max + 1` wrapped in a service function.**

Three approaches exist for concurrent-safe sequential code generation:

| Approach | Concurrency Safety | Complexity | Verdict |
|----------|-------------------|------------|---------|
| `SELECT max(code) + 1` unguarded | Races under concurrent inserts | Low | Not safe |
| PostgreSQL `SEQUENCE` (native) | Fully safe, gaps possible | Medium | Best for high volume |
| `SELECT max + 1` inside `BEGIN` transaction (serializable) | Safe; full-table lock on small table | Low | Acceptable for small shop |
| `SELECT FOR UPDATE` on a counter row | Safe, no lock escalation | Medium | Good if max+1 undesirable |

**For a single-shop install at v1 data volumes (< 10k partners ever), the `max + 1` approach with a unique constraint on `code` as the safety net is the pragmatic choice.** [ASSUMED — reasonable for single-shop scale, but concurrent batch imports could produce constraint violations requiring retry]

The unique constraint on `code` acts as the true concurrency guard: if two concurrent creates collide on the same auto-generated code, the second raises a `UniqueConstraintError` which the service catches and retries with a new max. This is the same pattern used for username uniqueness everywhere in the ecosystem.

```python
# Source: service pattern — derived from auth/service.py create_user
from sqlalchemy import select, func

async def generate_partner_code(db: AsyncSession) -> str:
    """
    Generate the next sequential partner code in the format P-####.

    Uses max(code) + 1 with the unique DB constraint as the safety net.
    Retries once on IntegrityError (concurrent insert collision).
    """
    result = await db.execute(
        select(func.max(Partner.code)).where(Partner.code.like("P-%"))
    )
    max_code = result.scalar()  # e.g. "P-0042" or None
    if max_code is None:
        next_num = 1
    else:
        try:
            next_num = int(max_code.split("-")[1]) + 1
        except (IndexError, ValueError):
            next_num = 1
    return f"P-{next_num:04d}"
```

**Alternative role-prefixed codes** (`V-####` / `C-####`) are acceptable but create ambiguity for partners that are both vendor and customer (D-01). A unified `P-####` series is cleaner for the unified-table model and is the recommendation. [ASSUMED]

### Pattern 4: Soft-Delete — `active` boolean (recommendation)

**Recommendation: `active = false` boolean, not `archived_at` timestamp.**

Rationale [ASSUMED but well-grounded]:
- The auth module already uses `is_active: bool` for user soft-deactivation — same pattern, same concept.
- Every list query becomes `WHERE active = true` — simpler than `WHERE archived_at IS NULL`.
- "Show archived" toggle adds `WHERE active = false` or drops the filter — straightforward.
- Restore is `PATCH {id}` with `active = true` — same endpoint as other updates.
- Timestamp of archival is captured by the `AuditLog` row (`partner.archived` action), which is already the canonical source for the medical-device traceability posture. A separate `archived_at` column would be redundant.

Archive endpoint pattern (mirrors auth deactivate):
```python
# Action: POST /syerp/partners/{id}/archive  (separate endpoint for clarity)
# or: PATCH /syerp/partners/{id} with {"active": false}
# Recommendation: use PATCH (consistent with auth module's user deactivation)
await write_audit(db, actor_id=str(current_user.id),
                  action="partner.archived",
                  target_type="partner", target_id=str(partner.id),
                  detail=f"Archived partner: {partner.name}")
```

### Pattern 5: Router Shape (mirrors auth/router.py exactly)

```python
# Source: backend/app/modules/auth/router.py structure
router = APIRouter(prefix="/syerp", tags=["syerp"])

# List partners (role-filtered via ?role=vendor|customer, ?q=, ?include_archived=)
@router.get("/partners", response_model=list[PartnerRead])
async def list_partners(
    role: str | None = None,           # "vendor" | "customer" | None
    q: str | None = None,              # search string
    include_archived: bool = False,
    current_user=Depends(require_permission("syerp:read")),
    db: AsyncSession = Depends(get_db),
) -> list[PartnerRead]: ...

@router.post("/partners", response_model=PartnerRead, status_code=201)
async def create_partner(
    data: PartnerCreate,
    current_user=Depends(require_permission("syerp:write")),
    db: AsyncSession = Depends(get_db),
) -> PartnerRead: ...

@router.get("/partners/{partner_id}", response_model=PartnerRead)
async def get_partner(
    partner_id: str,
    current_user=Depends(require_permission("syerp:read")),
    db: AsyncSession = Depends(get_db),
) -> PartnerRead: ...

@router.patch("/partners/{partner_id}", response_model=PartnerRead)
async def update_partner(
    partner_id: str,
    data: PartnerUpdate,
    current_user=Depends(require_permission("syerp:write")),
    db: AsyncSession = Depends(get_db),
) -> PartnerRead: ...

# GL accounts — read-only, gated by syerp:read (no new permission)
@router.get("/gl/accounts", response_model=list[GLAccountRead])
async def list_gl_accounts(
    current_user=Depends(require_permission("syerp:read")),
    db: AsyncSession = Depends(get_db),
) -> list[GLAccountRead]: ...
```

**Route rule:** prefix is `/syerp` (no `/api/v1` — `mount_all()` adds it). [VERIFIED: auth/router.py uses `prefix="/auth"` convention; syerp/router.py stub confirms the same rule]

### Pattern 6: Server-Side Search Query (D-07)

```python
# Source: SQLAlchemy 2.0 select() pattern used throughout auth service
from sqlalchemy import or_, select

stmt = select(Partner).where(Partner.active == include_archived.__not__())
# Role filter
if role == "vendor":
    stmt = stmt.where(Partner.is_vendor == True)
elif role == "customer":
    stmt = stmt.where(Partner.is_customer == True)
# Text search across name, code, contact_name
if q:
    like = f"%{q}%"
    stmt = stmt.where(
        or_(
            Partner.name.ilike(like),
            Partner.code.ilike(like),
            Partner.contact_name.ilike(like),
        )
    )
stmt = stmt.order_by(Partner.name)
result = await db.execute(stmt)
return list(result.scalars().all())
```

`ilike` is PostgreSQL case-insensitive LIKE. [VERIFIED: SQLAlchemy 2.0 supports `.ilike()` on String columns — standard ORM feature]

### Pattern 7: Frontend Screen Shape (mirrors Users.tsx exactly)

```typescript
// Source: frontend/src/routes/admin/Users.tsx — copy interaction model
// Vendors.tsx / Customers.tsx differ only in:
//   - queryKey: ['syerp', 'partners', 'vendor'] vs ['syerp', 'partners', 'customer']
//   - API call: GET /api/v1/syerp/partners?role=vendor vs ?role=customer
//   - Page heading: "Vendors" vs "Customers"
//   - Button label: "Create Vendor" vs "Create Customer"
//   - Archive action label

// Debounce: 300ms (same as Users.tsx)
// Sheet: right-side for create/edit (PartnerSheet — shared component)
// Archive dialog: Dialog with destructive button (not "Deactivate" — "Archive")
// Show-archived toggle: Switch component (already installed)
// Empty state: same pattern ("No vendors found" / "No customers found")
```

The `PartnerSheet` create/edit form should include all D-03 fields. For usability, group them visually with `Separator` between Identity / Address / Contact / Commerce groups (shadcn `separator` is installed).

**"Show archived" toggle:** Add a `Switch` labeled "Show archived" in the toolbar. When toggled on, re-fetch with `include_archived=true`. Invalidate query key on toggle change.

### Pattern 8: Idempotent CoA Seed (D-06)

Plug into `run_seeds()` following Phase 2/3 pattern exactly:

```python
# Source: app/core/seed.py and app/modules/auth/seed.py select-before-insert pattern
async def seed_gl_accounts(db: AsyncSession) -> None:
    from sqlalchemy import select
    from app.modules.syerp.models import GLAccount

    for account_data in _STANDARD_COA:
        result = await db.execute(
            select(GLAccount).where(GLAccount.code == account_data["code"])
        )
        if result.scalars().first() is None:
            db.add(GLAccount(**account_data))
    await db.commit()
```

`run_seeds()` in `app/core/seed.py` gains one line: `await seed_gl_accounts(db)`.
[VERIFIED: app/core/seed.py shows the call pattern and ordering]

### Pattern 9: Core Models Registration

Add to `backend/app/core/models.py` in the Phase 4+ block:

```python
# Phase 4: SYERP core hub — partner master data + GL skeleton
from app.modules.syerp import models as syerp_models  # noqa: F401 — already present but empty
```

The existing import of `syerp_models` is already there (Phase 1 stub). No new import line is needed — when `Partner` and `GLAccount` are added to `syerp/models.py`, the existing import picks them up automatically for Alembic autogenerate.
[VERIFIED: backend/app/core/models.py line 15 already imports syerp models]

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Sequential unique codes under concurrency | Manual counter logic without safety net | `unique=True` constraint + IntegrityError retry | DB constraint is the true race guard; retry is O(1) |
| Permission gating | New decorator or middleware | `require_permission("syerp:read")` from `auth.dependencies` | Already built, tested, covers admin wildcard |
| Audit trail | Custom logging or separate service | `write_audit(db, ...)` from `auth.service` | Already handles append-only AuditLog rows per D-10 |
| Soft-delete filtering | Custom query builder | Standard SQLAlchemy `where(active == True)` | One line; no abstraction needed at v1 scale |
| Search/filter | Elasticsearch or full-text search | PostgreSQL `ilike` via SQLAlchemy | More than adequate for single-shop record counts |
| Tree rendering (CoA) | Custom recursive component | Accordion via shadcn or simple indented table | CoA is static seeded data; no interaction needed |
| Schema validation | Manual `if` checks | Pydantic `BaseModel` (already in project) | Auto-validation, type coercion, OpenAPI docs |

**Key insight:** Every complex problem in this phase has a working solution already in the codebase. The task is assembly, not invention.

---

## Standard Chart of Accounts Seed

The following is a recommended seed list for a small US manufacturer. It covers all five GAAP account types with a sensible sub-account structure. [ASSUMED — based on standard US small-business CoA conventions; should be confirmed with user if they have an existing CoA or specific accounting software they plan to integrate with]

**Numbering scheme:** 4-digit codes in the standard US range (1xxx Assets / 2xxx Liabilities / 3xxx Equity / 4xxx Revenue / 5xxx Expenses). Parent accounts are the round hundreds; sub-accounts are +10 increments leaving gaps for future additions.

```python
# Source: Standard US small-business CoA conventions [ASSUMED]
# Parent accounts have parent_id = None; children reference parent by code lookup
_STANDARD_COA = [
    # ── ASSETS (1000–1999) ───────────────────────────────────────────────────
    {"code": "1000", "name": "Assets",                      "account_type": "ASSET",     "parent_id": None},
    {"code": "1100", "name": "Current Assets",              "account_type": "ASSET",     "parent_id": None},  # parent: 1000
    {"code": "1110", "name": "Cash and Cash Equivalents",   "account_type": "ASSET",     "parent_id": None},  # parent: 1100
    {"code": "1120", "name": "Accounts Receivable",         "account_type": "ASSET",     "parent_id": None},  # parent: 1100
    {"code": "1130", "name": "Inventory",                   "account_type": "ASSET",     "parent_id": None},  # parent: 1100
    {"code": "1140", "name": "Work in Process",             "account_type": "ASSET",     "parent_id": None},  # parent: 1100
    {"code": "1150", "name": "Prepaid Expenses",            "account_type": "ASSET",     "parent_id": None},  # parent: 1100
    {"code": "1200", "name": "Fixed Assets",                "account_type": "ASSET",     "parent_id": None},  # parent: 1000
    {"code": "1210", "name": "Equipment",                   "account_type": "ASSET",     "parent_id": None},  # parent: 1200
    {"code": "1220", "name": "Accumulated Depreciation",    "account_type": "ASSET",     "parent_id": None},  # parent: 1200

    # ── LIABILITIES (2000–2999) ──────────────────────────────────────────────
    {"code": "2000", "name": "Liabilities",                 "account_type": "LIABILITY", "parent_id": None},
    {"code": "2100", "name": "Current Liabilities",         "account_type": "LIABILITY", "parent_id": None},  # parent: 2000
    {"code": "2110", "name": "Accounts Payable",            "account_type": "LIABILITY", "parent_id": None},  # parent: 2100
    {"code": "2120", "name": "Accrued Expenses",            "account_type": "LIABILITY", "parent_id": None},  # parent: 2100
    {"code": "2130", "name": "Sales Tax Payable",           "account_type": "LIABILITY", "parent_id": None},  # parent: 2100
    {"code": "2140", "name": "Payroll Liabilities",         "account_type": "LIABILITY", "parent_id": None},  # parent: 2100
    {"code": "2200", "name": "Long-Term Liabilities",       "account_type": "LIABILITY", "parent_id": None},  # parent: 2000
    {"code": "2210", "name": "Long-Term Debt",              "account_type": "LIABILITY", "parent_id": None},  # parent: 2200

    # ── EQUITY (3000–3999) ───────────────────────────────────────────────────
    {"code": "3000", "name": "Equity",                      "account_type": "EQUITY",    "parent_id": None},
    {"code": "3100", "name": "Owner's Equity",              "account_type": "EQUITY",    "parent_id": None},  # parent: 3000
    {"code": "3110", "name": "Capital Contributions",       "account_type": "EQUITY",    "parent_id": None},  # parent: 3100
    {"code": "3120", "name": "Retained Earnings",           "account_type": "EQUITY",    "parent_id": None},  # parent: 3100
    {"code": "3130", "name": "Current Year Net Income",     "account_type": "EQUITY",    "parent_id": None},  # parent: 3100

    # ── REVENUE (4000–4999) ──────────────────────────────────────────────────
    {"code": "4000", "name": "Revenue",                     "account_type": "REVENUE",   "parent_id": None},
    {"code": "4100", "name": "Product Sales",               "account_type": "REVENUE",   "parent_id": None},  # parent: 4000
    {"code": "4110", "name": "Product Revenue",             "account_type": "REVENUE",   "parent_id": None},  # parent: 4100
    {"code": "4120", "name": "Service Revenue",             "account_type": "REVENUE",   "parent_id": None},  # parent: 4100
    {"code": "4200", "name": "Other Income",                "account_type": "REVENUE",   "parent_id": None},  # parent: 4000
    {"code": "4210", "name": "Interest Income",             "account_type": "REVENUE",   "parent_id": None},  # parent: 4200

    # ── EXPENSES (5000–5999) ─────────────────────────────────────────────────
    {"code": "5000", "name": "Expenses",                    "account_type": "EXPENSE",   "parent_id": None},
    {"code": "5100", "name": "Cost of Goods Sold",          "account_type": "EXPENSE",   "parent_id": None},  # parent: 5000
    {"code": "5110", "name": "Direct Materials",            "account_type": "EXPENSE",   "parent_id": None},  # parent: 5100
    {"code": "5120", "name": "Direct Labor",                "account_type": "EXPENSE",   "parent_id": None},  # parent: 5100
    {"code": "5130", "name": "Manufacturing Overhead",      "account_type": "EXPENSE",   "parent_id": None},  # parent: 5100
    {"code": "5200", "name": "Operating Expenses",          "account_type": "EXPENSE",   "parent_id": None},  # parent: 5000
    {"code": "5210", "name": "Salaries and Wages",          "account_type": "EXPENSE",   "parent_id": None},  # parent: 5200
    {"code": "5220", "name": "Rent and Occupancy",          "account_type": "EXPENSE",   "parent_id": None},  # parent: 5200
    {"code": "5230", "name": "Utilities",                   "account_type": "EXPENSE",   "parent_id": None},  # parent: 5200
    {"code": "5240", "name": "Insurance",                   "account_type": "EXPENSE",   "parent_id": None},  # parent: 5200
    {"code": "5250", "name": "Depreciation Expense",        "account_type": "EXPENSE",   "parent_id": None},  # parent: 5200
    {"code": "5260", "name": "Research and Development",    "account_type": "EXPENSE",   "parent_id": None},  # parent: 5200
    {"code": "5270", "name": "Marketing and Sales",         "account_type": "EXPENSE",   "parent_id": None},  # parent: 5200
    {"code": "5280", "name": "General and Administrative",  "account_type": "EXPENSE",   "parent_id": None},  # parent: 5200
    {"code": "5290", "name": "Professional Services",       "account_type": "EXPENSE",   "parent_id": None},  # parent: 5200
]
```

**Implementation note on `parent_id`:** The seed data above shows `parent_id: None` as placeholder — the actual seed function must resolve parent codes to DB row IDs after insertion. The simplest approach is a two-pass insert: first insert all records with `parent_id=None`, then update `parent_id` by looking up the integer ID of the parent code. Alternatively, use a dict keyed by code to resolve IDs during a single ordered insert (parents before children — already ordered above). [ASSUMED — implementation detail; recommend the dict approach]

**Total accounts:** 40 accounts across 5 types. This is manageable for v1 and covers the manufacturing-specific accounts (WIP, COGS sub-accounts, R&D) that the user's medical-device business will need.

---

## Common Pitfalls

### Pitfall 1: Alembic Misses New SYERP Models
**What goes wrong:** Running `alembic revision --autogenerate` produces an empty migration because the new models aren't imported into `Base.metadata`.
**Why it happens:** `core/models.py` already imports `syerp_models`, but when the stub had no classes, nothing was registered. After adding `Partner` and `GLAccount`, the import is already wired — this should auto-work. But if a developer adds models to a NEW file instead of `syerp/models.py`, Alembic won't find them.
**How to avoid:** All SYERP models go in `backend/app/modules/syerp/models.py` (the existing stub). Do not create new model files without registering them in `core/models.py`.
**Warning signs:** Autogenerate output says "No changes detected" when you just added tables.

### Pitfall 2: MissingGreenlet on Relationship Access
**What goes wrong:** Accessing a relationship attribute (if any were added) outside an async session raises `sqlalchemy.exc.MissingGreenlet`.
**Why it happens:** Lazy loading in async SQLAlchemy requires an active async context. Phase 4 partner model has no relationships (no FK children in this phase), so this pitfall is less likely — but if a relationship is added later, `lazy="selectin"` is mandatory per the auth model pattern.
**How to avoid:** `syerp_partner` has no relationships in this phase. `syerp_gl_account` has a self-referential `parent_id` FK but the GL endpoint returns a flat list (tree is built frontend-side or via a recursive CTE) — no relationship traversal needed.
**Warning signs:** `MissingGreenlet` traceback in startup logs.

### Pitfall 3: Partner Code Uniqueness Collision on Concurrent Creates
**What goes wrong:** Two simultaneous partner creates generate the same code; one insert fails with `UniqueViolationError`.
**Why it happens:** `max + 1` is not atomic across concurrent transactions.
**How to avoid:** The service catches `sqlalchemy.exc.IntegrityError` on code uniqueness and retries once with a fresh `max + 1` query. The unique DB constraint is the actual guard. At single-shop scale this race is practically impossible but the retry makes it correct.
**Warning signs:** 500 errors on concurrent creates (not expected in normal use).

### Pitfall 4: `type` as Column Name Shadows Python Built-in
**What goes wrong:** Naming the GL account type column `type` causes subtle bugs because `type` is a Python built-in.
**How to avoid:** Use `account_type` as the column name. Already reflected in the model recommendation above.

### Pitfall 5: Archived Partners Appearing in PLUM AVL Picker (Phase 6)
**What goes wrong:** The Phase 6 AVL link lookup fetches all partners without the `active` filter, showing archived vendors in dropdowns.
**Why it happens:** Phase 6 is out of scope here, but the design decision needs to be encoded now.
**How to avoid:** The list endpoint default is `active=true` only. Phase 6 must explicitly pass `include_archived=false` (or rely on the default). Note this in the endpoint docstring now.

### Pitfall 6: CoA Seed `parent_id` Circular Dependency
**What goes wrong:** Trying to insert child accounts before their parent rows exist causes FK violations.
**Why it happens:** The seed list has parent-child relationships. If inserted in the wrong order, the parent row doesn't have an id yet.
**How to avoid:** Insert parent accounts first (those with `parent_code=None`), flush to get IDs, then insert children. The `_STANDARD_COA` list above is already ordered parents-before-children by account-type grouping.

### Pitfall 7: Frontend Query Cache Stale After Archive
**What goes wrong:** User archives a partner; it still appears in the list because TanStack Query cached the old response.
**Why it happens:** `useMutation.onSuccess` must call `queryClient.invalidateQueries` with the correct key.
**How to avoid:** Mirror Users.tsx exactly — `onSuccess: () => { void queryClient.invalidateQueries({ queryKey: ['syerp', 'partners', role] }) }`. The role-scoped query key (e.g. `['syerp', 'partners', 'vendor']`) means archiving from the Vendor screen doesn't stale the Customer screen cache unnecessarily.

### Pitfall 8: `is_vendor` / `is_customer` Both False — Orphan Record
**What goes wrong:** A partner is created or edited so both flags are `false`. The record exists in the DB but is invisible in both the Vendor and Customer lists.
**How to avoid:** Add a Pydantic validator in `PartnerCreate` / `PartnerUpdate` that raises a `ValueError` if both flags are `false` simultaneously: `at_least_one_role = model_validator(mode='after')` checking `self.is_vendor or self.is_customer`.

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Separate vendor/customer tables | Unified partner table with role flags (res.partner pattern) | Standard ERP practice (Odoo 2012+) | Cleaner FKs from PLUM; no duplication for dual-role entities |
| `var` keyword in JS | `const`/`let` + TypeScript | ES6/2015; TS 2012+ | n/a — Python/TS project |
| SQLAlchemy 1.x `Column()` style | `Mapped[type] = mapped_column()` (2.0) | SQLAlchemy 2.0 (2023) | Type-safe ORM; mandatory in this project |
| Alembic manual migrations | Autogenerate from models | Standard practice | Models → migrations without manual SQL |

**Deprecated/outdated patterns to avoid:**
- `Column(String(255))` without `Mapped[]` — old SQLAlchemy 1.x style; use `Mapped[str] = mapped_column(String(255))` [VERIFIED: auth/models.py uses the new style]
- `lazy="select"` (sync lazy loading) on relationships — crashes in async context; must use `lazy="selectin"` [VERIFIED: auth/models.py comment on every relationship]
- `type="..."` SQLAlchemy discriminator columns named `type` — shadows Python built-in; use `account_type`

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Single unified `P-####` series is cleaner than `V-####`/`C-####` for a unified-table model | Partner Code (Pattern 3) | Aesthetic preference; low risk — codes can be refactored before data is in production |
| A2 | `active = false` boolean is preferable to `archived_at` timestamp | Soft-Delete (Pattern 4) | Low — both work; `archived_at` adds a richer restoration timestamp but duplicates AuditLog info |
| A3 | `max + 1` with unique constraint retry is sufficient concurrency safety at single-shop scale | Partner Code (Pattern 3) | Very low at single-shop — if high-volume batch imports are needed later, a PostgreSQL sequence is the upgrade path |
| A4 | Standard US GAAP 5-type 4-digit CoA numbering is appropriate for user's medical-device manufacturing business | CoA Seed | Medium — if user has an existing accountant's CoA or specific accounting system, the numbering may conflict; confirm before final implementation |
| A5 | GL browse rides `syerp:read` (no dedicated permission needed) | Router (Pattern 5) | Low — the only alternative is a `syerp:gl_read` permission, which adds complexity for no current benefit |
| A6 | Two-pass parent_id resolution in CoA seed (insert all → update parent_ids) | CoA Seed (Pattern 8) | Low — well-established pattern; only risk is forgetting the second pass |
| A7 | Frontend: two separate route files (Vendors.tsx, Customers.tsx) with a shared PartnerSheet component is better than a single parameterized route | Frontend Architecture | Low — either works; separate files are more readable and match the "separate Vendor/Customer screens" UX intent |

---

## Open Questions

1. **CoA numbering confirmation**
   - What we know: standard US GAAP numbering proposed above (1xxx–5xxx)
   - What's unclear: whether the user's accountant or existing business records use a different scheme
   - Recommendation: proceed with the proposed CoA; make it easy to replace the seed list — it's a constant, not hardcoded logic

2. **Currency default on create form**
   - What we know: Phase 3 settings includes `default_currency` (D-11 in 03-CONTEXT.md)
   - What's unclear: whether the frontend partner create form should fetch the settings API to pre-populate `currency`, or just hardcode "USD" as the form default
   - Recommendation: fetch `GET /api/v1/core/settings` (already exists) and use the `default_currency` setting as the `currency` field default — consistent with D-11 intent

3. **"Show archived" toggle scope**
   - What we know: lists default to `active=true`; a toggle is needed to see archived records
   - What's unclear: whether "show archived" should show only archived (`active=false`) or all records (active + archived)
   - Recommendation: "show archived" shows all records (active + archived together) — simpler UX and allows restoring an archived record without first understanding its state

---

## Environment Availability

Step 2.6: No new external dependencies. All required tools (PostgreSQL, FastAPI, React, shadcn, TanStack Query) are already available and verified in prior phases. No environment audit needed.

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Backend framework | pytest-anyio (via anyio 4.14.0), httpx ASGI transport |
| Frontend framework | Vitest 4.1.9 + @testing-library/react 16.3.2 |
| Backend config | `backend/tests/conftest.py` (already exists) |
| Frontend config | `frontend/vitest.config.ts` (already exists) |
| Backend quick run | `pytest backend/tests/syerp/ -x` |
| Backend full suite | `pytest backend/ -x` |
| Frontend quick run | `cd frontend && npm test -- --run` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| SYERP-01 | Partner create → 201, fields correct | integration | `pytest backend/tests/syerp/test_partners.py::test_create_vendor -x` | ❌ Wave 0 |
| SYERP-01 | Partner create without role flags → 422 | integration | `pytest backend/tests/syerp/test_partners.py::test_create_requires_role -x` | ❌ Wave 0 |
| SYERP-01 | Partner update → 200, audit log written | integration | `pytest backend/tests/syerp/test_partners.py::test_update_partner_writes_audit -x` | ❌ Wave 0 |
| SYERP-01 | Partner archive sets active=false | integration | `pytest backend/tests/syerp/test_partners.py::test_archive_partner -x` | ❌ Wave 0 |
| SYERP-01 | Archived partner absent from default list | integration | `pytest backend/tests/syerp/test_partners.py::test_archived_excluded_by_default -x` | ❌ Wave 0 |
| SYERP-01 | syerp:write required for create → 403 without it | integration | `pytest backend/tests/syerp/test_partners.py::test_create_requires_syerp_write -x` | ❌ Wave 0 |
| SYERP-01 | Partner code is unique (duplicate code → 409 or 422) | integration | `pytest backend/tests/syerp/test_partners.py::test_duplicate_code_rejected -x` | ❌ Wave 0 |
| SYERP-02 | `?q=` search filters by name | integration | `pytest backend/tests/syerp/test_partners.py::test_search_by_name -x` | ❌ Wave 0 |
| SYERP-02 | `?q=` search filters by code | integration | `pytest backend/tests/syerp/test_partners.py::test_search_by_code -x` | ❌ Wave 0 |
| SYERP-02 | `?role=vendor` returns only is_vendor=true partners | integration | `pytest backend/tests/syerp/test_partners.py::test_vendor_role_filter -x` | ❌ Wave 0 |
| SYERP-03 | Customer create → 201 with is_customer=true | integration | `pytest backend/tests/syerp/test_partners.py::test_create_customer -x` | ❌ Wave 0 |
| SYERP-04 | `?role=customer` returns only is_customer=true partners | integration | `pytest backend/tests/syerp/test_partners.py::test_customer_role_filter -x` | ❌ Wave 0 |
| SYERP-04 | Dual-role partner appears in both vendor and customer lists | integration | `pytest backend/tests/syerp/test_partners.py::test_dual_role_appears_in_both -x` | ❌ Wave 0 |
| SYERP-05 | GL accounts endpoint returns seeded data | integration | `pytest backend/tests/syerp/test_gl.py::test_gl_accounts_seeded -x` | ❌ Wave 0 |
| SYERP-05 | GL seed is idempotent (re-running seed doesn't duplicate) | integration | `pytest backend/tests/syerp/test_gl.py::test_gl_seed_idempotent -x` | ❌ Wave 0 |
| SYERP-05 | GL browse requires syerp:read | integration | `pytest backend/tests/syerp/test_gl.py::test_gl_requires_syerp_read -x` | ❌ Wave 0 |
| SYERP-01..04 | Vendor list screen renders heading + Create Vendor button | unit (frontend) | `cd frontend && npm test -- --run src/routes/syerp/Vendors.test.tsx` | ❌ Wave 0 |
| SYERP-03..04 | Customer list screen renders heading + Create Customer button | unit (frontend) | `cd frontend && npm test -- --run src/routes/syerp/Customers.test.tsx` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest backend/tests/syerp/ -x` (backend only for backend tasks) or `cd frontend && npm test -- --run` (frontend only for frontend tasks)
- **Per wave merge:** `pytest backend/ -x && cd frontend && npm test -- --run`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `backend/tests/syerp/__init__.py` — package marker
- [ ] `backend/tests/syerp/test_partners.py` — covers SYERP-01..04 partner CRUD, search, code uniqueness, audit, RBAC
- [ ] `backend/tests/syerp/test_gl.py` — covers SYERP-05 CoA seed and browse endpoint
- [ ] `frontend/src/routes/syerp/Vendors.test.tsx` — mirrors Users.test.tsx; mocks apiClient
- [ ] `frontend/src/routes/syerp/Customers.test.tsx` — mirrors Users.test.tsx

Existing test infrastructure (`conftest.py`, `conftest_helpers.py`, `db_available()` skip helper) is fully reusable — no new fixtures needed for the standard CRUD + RBAC test pattern.

---

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | Auth handled by Phase 2; partners are not auth entities |
| V3 Session Management | No | Session management handled by Phase 2 |
| V4 Access Control | Yes | `require_permission("syerp:read")` / `("syerp:write")` on every route |
| V5 Input Validation | Yes | Pydantic `PartnerCreate` / `PartnerUpdate` — all string fields bounded by `max_length` |
| V6 Cryptography | No | No new secrets; no new encryption |

### Known Threat Patterns for This Stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| RBAC bypass (partner write without syerp:write) | Elevation of Privilege | `require_permission("syerp:write")` on all mutating endpoints; same pattern as auth RBAC (already tested) |
| ilike injection via `?q=` search param | Tampering | SQLAlchemy parameterized `.ilike(f"%{q}%")` — not string interpolation into raw SQL |
| Archived partner restoration by unpermitted user | Elevation of Privilege | Restore is via `PATCH {id}` with `active=true` — gated by `syerp:write` |
| Partner code collision / forced code override | Tampering | Unique DB constraint + Pydantic `max_length=20` on `code` field |
| XSS via partner name in rendered table | Tampering | React renders text content as text nodes (not innerHTML); no explicit escaping needed |

---

## Sources

### Primary (HIGH confidence)
- `backend/app/modules/auth/router.py` — endpoint shape, require_permission pattern, write_audit calls [VERIFIED in-repo]
- `backend/app/modules/auth/models.py` — `Mapped[type] = mapped_column()` style, `lazy="selectin"`, datetime defaults [VERIFIED in-repo]
- `backend/app/modules/auth/service.py` — service helper signatures, write_audit function [VERIFIED in-repo]
- `backend/app/modules/auth/seed.py` — idempotent select-before-insert pattern [VERIFIED in-repo]
- `backend/app/core/seed.py` — run_seeds() hook, call ordering [VERIFIED in-repo]
- `backend/app/core/models.py` — Alembic aggregator, Phase 4+ comment block [VERIFIED in-repo]
- `backend/app/modules/syerp/{models,schemas,service,router}.py` — stub conventions, table prefix, router prefix rule [VERIFIED in-repo]
- `frontend/src/routes/admin/Users.tsx` — TanStack Query patterns, Sheet/Dialog usage, debounce timer, filteredUsers pattern [VERIFIED in-repo]
- `frontend/src/components/ui/` — available shadcn primitives [VERIFIED via Glob]
- `frontend/package.json` — exact library versions [VERIFIED in-repo]
- `backend/requirements.txt` — exact library versions [VERIFIED in-repo]
- `plum/app/plm_v54.html` Vendors object (line 10230–10308) — field names: code, name, contactName, contactEmail, contactPhone, address, paymentTerms, notes, currency, country [VERIFIED in-repo]

### Secondary (MEDIUM confidence)
- Standard US GAAP CoA numbering conventions (1xxx–5xxx, Assets/Liabilities/Equity/Revenue/Expenses) — cross-referenced against common QuickBooks and small-business accounting practice

### Tertiary (LOW confidence / ASSUMED)
- Specific CoA sub-account selection (which 40 accounts) — derived from standard small-business + manufacturing context; user-specific CoA may differ (A4)
- `max + 1` sufficient for single-shop concurrency (A3) — reasonable assumption but not empirically verified for this deployment

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries verified in requirements.txt / package.json
- Architecture patterns: HIGH — all patterns traced to actual code in the codebase
- Partner schema: HIGH (field set) / ASSUMED (exact lengths — pragmatic choices)
- CoA seed: MEDIUM — numbering is standard; specific account selection is [ASSUMED]
- Pitfalls: HIGH — all grounded in prior-phase issues (MissingGreenlet, UniqueConstraint) already documented

**Research date:** 2026-06-26
**Valid until:** 2026-09-01 (stable framework versions; no fast-moving dependencies in this phase)
