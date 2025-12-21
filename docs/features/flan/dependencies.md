# FLAN Dependencies

What to read before working on this feature.

---

## This Feature Depends On

| Feature | Why | Must Read |
|---------|-----|-----------|
| Core (Auth) | Team members link to users, auth context | `docs/features/core/INVARIANTS.md` |
| SYERP | Vendor data for expenses, customer data | `docs/features/syerp/INVARIANTS.md` |

---

## Other Features Depend On This

| Feature | Integration Point | What They Expect |
|---------|-------------------|------------------|
| PLUM | Product development projects | Project reference by ID, phase links |
| MOUSSE | Manufacturing project coordination | Project milestone links |
| CRISP | Quality milestone tracking | Project and phase references |

---

## Cross-Cutting Concerns

| Concern | Applies When | Must Read |
|---------|--------------|-----------|
| User Authentication | Any project access | Core auth system |
| Audit Logging | All data changes | Activity log patterns |
| Data Export | JSON/Excel generation | Export utilities |

---

## Reading Checklist

Before implementing changes to FLAN:

- [ ] Read this feature's `INVARIANTS.md`
- [ ] Read `docs/features/syerp/INVARIANTS.md` (for vendor/expense integration)
- [ ] Review project data model in `architecture.md`
- [ ] Check the main `docs/ROADMAP.md` for phase requirements

---

## Integration Points

### With SYERP (Hub)

**How they connect:** FLAN references SYERP for vendor master data and integrates expense tracking.

**Data exchanged:**

| Direction | Data | Purpose |
|-----------|------|---------|
| SYERP → FLAN | Vendor list | Expense vendor selection |
| FLAN → SYERP | Project costs | Financial reporting |
| FLAN → SYERP | Time-based invoices | Billing for project work |

**Integration pattern:**

```text
FLAN.expenses.vendor_id ──FK──► SYERP.vendors.id

FLAN reads vendor data via API:
GET /api/syerp/vendors → Used in expense forms

FLAN pushes project cost summaries:
POST /api/syerp/project-costs ← Labor + expenses total
```

---

### With PLUM (PLM)

**How they connect:** Product development projects in FLAN can link to PLUM parts/products being developed.

**Data exchanged:**

| Direction | Data | Purpose |
|-----------|------|---------|
| FLAN → PLUM | Project ID | Link product to its development project |
| PLUM → FLAN | Part/BOM references | Track which products project is building |

**Integration pattern:**

```text
PLUM.parts.development_project_id ──FK──► FLAN.projects.id

Use cases:
- "View the project for this product development"
- "See all parts being developed in this project"
```

---

### With Core (Users)

**How they connect:** Team members can optionally link to Core user accounts for authentication and cross-module identity.

**Data exchanged:**

| Direction | Data | Purpose |
|-----------|------|---------|
| Core → FLAN | User profiles | Team member identity |
| Core → FLAN | Auth context | Permission checking |

**Integration pattern:**

```text
FLAN.team_members.user_id ──FK──► Core.users.id

Benefits of linking:
- Single sign-on identity
- Cross-module activity attribution
- Permission inheritance
```

---

## Dependency Diagram

```text
                    ┌─────────────────┐
                    │      CORE       │
                    │  (Auth, Users)  │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │      SYERP      │
                    │ (Vendors, GL)   │
                    └────────┬────────┘
                             │
         ┌───────────────────┼───────────────────┐
         │                   │                   │
         ▼                   ▼                   ▼
    ┌─────────┐        ┌─────────┐        ┌─────────┐
    │  PLUM   │◄──────►│  FLAN   │        │ CRUMB   │
    │  (PLM)  │        │  (PM)   │        │  (CRM)  │
    └─────────┘        └─────────┘        └─────────┘
         │                   │
         │                   │
         ▼                   ▼
    ┌─────────┐        ┌─────────┐
    │ MOUSSE  │        │ CRISP   │
    │  (MES)  │        │  (QMS)  │
    └─────────┘        └─────────┘
```

**Legend:**
- Solid arrows = direct FK relationships
- Double-headed arrows = bidirectional references

---

## Data Flow Examples

### Example 1: Logging an Expense with Vendor

```text
1. User opens expense form in FLAN
2. FLAN fetches vendor list from SYERP API
3. User selects vendor, enters expense details
4. FLAN saves expense with vendor_id reference
5. SYERP can query all expenses by vendor for reporting
```

### Example 2: Linking Product Development Project

```text
1. User creates project in FLAN for "New Product X"
2. User creates part in PLUM for "Product X Assembly"
3. PLUM associates part with FLAN project ID
4. Both modules can navigate to each other
5. Project completion triggers product release workflow
```

### Example 3: Generating Project Invoice

```text
1. FLAN calculates total labor cost (time entries × rates)
2. FLAN adds expense totals by category
3. FLAN generates invoice document
4. Invoice references SYERP customer (future)
5. Invoice syncs to SYERP for AR tracking (future)
```

---

## Migration Notes

When building production integrations:

1. **Phase 1.0**: FLAN operates standalone with local team members
2. **Future**: Link team_members.user_id to Core.users
3. **Future**: Link expenses.vendor_id to SYERP.vendors
4. **Future**: Add project_id FK to PLUM parts for development tracking