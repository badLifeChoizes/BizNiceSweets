# PLUM Dependencies

What to read before working on the Product Lifecycle Management module.

---

## This Module Depends On

| Module | Why | Must Read |
|--------|-----|-----------|
| SYERP (Vendors) | AVL references vendor master data | `docs/features/syerp/INVARIANTS.md` |
| Shared Infrastructure | Authentication, file storage | `docs/architecture/shared.md` |

### SYERP Vendor Integration

PLUM's Approved Vendor List (AVL) stores foreign keys to SYERP vendor records:

```python
# PLUM stores vendor_id, not vendor data
avl_entry.vendor_id = "uuid-from-syerp"

# To display vendor name, PLUM queries SYERP
vendor = syerp.get_vendor(avl_entry.vendor_id)
```

**What PLUM expects from SYERP:**

- Vendor UUID remains stable
- Vendor name, contact info available via API
- Deleted vendors are soft-deleted (PLUM AVL entries remain valid)

---

## Other Modules Depend On This

| Module | Integration Point | What They Expect |
|--------|-------------------|------------------|
| SYERP | Product costs | `get_total_cost(part_id)` returns accurate rolled-up cost |
| MOUSSE | BOMs for manufacturing | Released parts with complete BOMs |
| FLAN | Project-product links | Part IDs for project deliverables |

### SYERP Integration

SYERP reads product cost data from PLUM for:

- Inventory valuation
- Cost of goods sold calculations
- Purchase order cost estimates

```python
# SYERP calls PLUM API
cost = plum.get_total_cost(part_id)
margin = plum.get_margin(part_id)
```

### MOUSSE Integration

MOUSSE (Manufacturing Execution) reads from PLUM:

- Released BOMs for work orders
- Part specifications
- Where-used data for change impact

**PLUM must provide:**

- Only Released parts appear in MOUSSE queries
- BOM structure with quantities
- Part type (MFG vs PUR) for routing decisions

### FLAN Integration

FLAN (Project Management) can link to PLUM products:

- Product development projects reference target parts
- Deliverables can link to part releases

---

## Cross-Cutting Concerns

| Concern | Applies When | Must Read |
|---------|--------------|-----------|
| Authentication | All API calls | `docs/architecture/auth.md` |
| Audit Logging | Part changes, status transitions | `docs/architecture/audit.md` |
| File Storage | Document attachments (Phase 1.5+) | `docs/architecture/storage.md` |

---

## Reading Checklist

Before implementing changes to PLUM:

- [ ] Read this module's `INVARIANTS.md`
- [ ] Read `docs/features/syerp/INVARIANTS.md` if touching AVL
- [ ] Check if change affects MOUSSE (BOM structure changes)
- [ ] Check if change affects SYERP (cost calculation changes)
- [ ] Review root `docs/DEPENDENCIES.md` for full context

---

## Integration Points Detail

### With SYERP

**How they connect:** REST API calls, shared PostgreSQL database

**Data exchanged:**

| Direction | Data | Trigger |
|-----------|------|---------|
| PLUM → SYERP | Product costs, margin data | On request |
| SYERP → PLUM | Vendor IDs, inventory levels | AVL management, availability checks |

**Events:**

| Event | Producer | Consumer | Purpose |
|-------|----------|----------|---------|
| `vendor.updated` | SYERP | PLUM | Refresh cached vendor names |
| `vendor.deleted` | SYERP | PLUM | Mark AVL entries as orphaned |
| `part.released` | PLUM | SYERP | Update inventory item costs |

### With MOUSSE

**How they connect:** REST API calls

**Data exchanged:**

| Direction | Data | Trigger |
|-----------|------|---------|
| PLUM → MOUSSE | BOMs, part specs | Work order creation |
| MOUSSE → PLUM | (none currently) | - |

**Events:**

| Event | Producer | Consumer | Purpose |
|-------|----------|----------|---------|
| `part.released` | PLUM | MOUSSE | New part available for manufacturing |
| `bom.updated` | PLUM | MOUSSE | BOM structure changed |
| `part.obsoleted` | PLUM | MOUSSE | Stop using this part |

### With FLAN

**How they connect:** REST API calls, URL links

**Data exchanged:**

| Direction | Data | Trigger |
|-----------|------|---------|
| PLUM → FLAN | Part IDs, names | Project linking |
| FLAN → PLUM | (none currently) | - |

**Events:**

| Event | Producer | Consumer | Purpose |
|-------|----------|----------|---------|
| `part.released` | PLUM | FLAN | Deliverable completed |

---

## Dependency Diagram

```text
                    ┌─────────────┐
                    │    FLAN     │
                    │ (Projects)  │
                    └──────┬──────┘
                           │ reads part info
                           ▼
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   SYERP     │◄───►│    PLUM     │────►│   MOUSSE    │
│  (Vendors)  │     │   (Parts)   │     │   (Mfg)     │
└─────────────┘     └─────────────┘     └─────────────┘
       │                   │
       │                   │
       └───────────────────┘
         shared vendor data
```