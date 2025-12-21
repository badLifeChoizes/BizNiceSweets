# PLUM Architecture

Data models, state machines, and APIs for the Product Lifecycle Management module.

---

## Data Model

### Part

```text
Part
├── id: UUID
├── partNumber: string (unique)
├── name: string
├── description: string
├── revision: string (A, B, C...)
├── status: PartStatus
├── type: PartType
├── class: string
├── unitCost: decimal
├── laborCost: decimal
├── salePrice: decimal
├── distributorDiscount: decimal (0-100%)
├── bom: BOMItem[]
├── avl: AVLEntry[]
├── substitutes: SubstituteEntry[]
├── documents: DocumentLink[] (Phase 1.5)
├── created: datetime
├── modified: datetime
└── createdBy: UUID (FK to users)
```

### BOM Item

```text
BOMItem
├── id: UUID
├── parentPartId: UUID (FK to Part)
├── childPartId: UUID (FK to Part)
├── quantity: decimal
├── refDes: string (reference designator)
├── effectiveFrom: date
├── effectiveTo: date
├── notes: string
└── sequence: integer
```

### AVL Entry

```text
AVLEntry
├── id: UUID
├── partId: UUID (FK to Part)
├── vendorId: UUID (FK to SYERP.vendors)
├── vendorPartNumber: string
├── status: AVLStatus
├── leadTime: integer (days)
├── minOrderQty: decimal
├── unitPrice: decimal
├── notes: string
└── lastUpdated: datetime
```

### Substitute Entry

```text
SubstituteEntry
├── id: UUID
├── primaryPartId: UUID (FK to Part)
├── substitutePartId: UUID (FK to Part)
├── type: SubstituteType
├── priority: integer
├── notes: string
└── approved: boolean
```

### Document Link (Phase 1.5)

```text
DocumentLink
├── id: UUID
├── partId: UUID (FK to Part)
├── type: DocumentType
├── name: string
├── url: string
├── revision: string
└── notes: string
```

---

## Enumerations

### PartStatus

```text
Draft ──[Release]──► Released ──[Obsolete]──► Obsolete
  │                      │
  └──────[Delete]────────┘ (only if not used in BOMs)
```

| Status | Description | Allowed Actions |
|--------|-------------|-----------------|
| Draft | Work in progress | Edit, Delete, Release |
| Released | Approved for use | Revise, Obsolete |
| Obsolete | No longer active | View only |

### PartType

| Type | Code | Description |
|------|------|-------------|
| Purchased | PUR | Bought from vendors |
| Manufactured | MFG | Made in-house |
| Assembly | ASM | Built from other parts |
| Raw Material | RAW | Base materials |
| Consumable | CON | Used but not in BOM |

### AVLStatus

| Status | Description |
|--------|-------------|
| Approved | Fully approved for use |
| Preferred | Primary vendor choice |
| Conditional | Approved with restrictions |
| Pending | Awaiting approval |
| Disqualified | Not approved |

### SubstituteType

| Type | Description |
|------|-------------|
| Equivalent | Functionally identical |
| Alternative | Different but acceptable |
| Emergency | Use only when primary unavailable |

### DocumentType (Phase 1.5)

| Type | Description |
|------|-------------|
| Specification | Technical specs |
| Drawing | CAD/engineering drawings |
| Datasheet | Vendor datasheets |
| Certificate | Compliance certificates |
| Other | Miscellaneous |

---

## State Machine: Part Lifecycle

```text
                    ┌─────────────────────────────┐
                    │                             │
                    ▼                             │
┌────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│  New   │───►│  Draft   │───►│ Released │───►│ Obsolete │
└────────┘    └──────────┘    └──────────┘    └──────────┘
                    │              │
                    │              │ (creates new revision)
                    │              ▼
                    │         ┌──────────┐
                    └────────►│  Draft   │ (Rev B, C, D...)
                              └──────────┘
```

### Transitions

| From | To | Trigger | Validations | Side Effects |
|------|-----|---------|-------------|--------------|
| New | Draft | Create | Part number unique | Assign revision A |
| Draft | Released | Release | BOM complete, costs set | Lock editing |
| Draft | (deleted) | Delete | Not used in any BOM | Remove from DB |
| Released | Obsolete | Obsolete | None | Mark end date |
| Released | Draft | Revise | None | Create new revision, copy data |

---

## Cost Calculations

### Material Cost Roll-up

```python
def get_material_cost(part_id, visited=set()):
    """Calculate total material cost from BOM."""
    if part_id in visited:
        return 0  # Prevent circular references
    visited.add(part_id)

    part = get_part(part_id)

    if not part.bom:  # Leaf part
        return part.unit_cost

    total = 0
    for item in part.bom:
        child_cost = get_material_cost(item.child_part_id, visited.copy())
        total += child_cost * item.quantity

    return total
```

### Total Cost with Labor

```python
def get_total_cost(part_id, visited=set()):
    """Calculate total cost including labor at all BOM levels."""
    if part_id in visited:
        return 0
    visited.add(part_id)

    part = get_part(part_id)

    # Start with this part's labor cost
    total = part.labor_cost or 0

    if not part.bom:  # Leaf part
        return part.unit_cost + part.labor_cost

    # Add child costs
    for item in part.bom:
        child_cost = get_total_cost(item.child_part_id, visited.copy())
        total += child_cost * item.quantity

    return total
```

### Margin Calculations

```python
def get_margin(part):
    """Calculate margin metrics for a part."""
    total_cost = get_total_cost(part.id)
    sale_price = part.sale_price or 0
    discount = part.distributor_discount or 0

    direct_margin = sale_price - total_cost
    margin_percent = (direct_margin / sale_price * 100) if sale_price > 0 else 0

    distributor_price = sale_price * (1 - discount / 100)
    distributor_profit = distributor_price - total_cost

    return {
        'total_cost': total_cost,
        'sale_price': sale_price,
        'direct_margin': direct_margin,
        'margin_percent': margin_percent,
        'distributor_price': distributor_price,
        'distributor_profit': distributor_profit
    }
```

---

## API Endpoints (Planned)

### Parts

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/parts` | List parts with filtering |
| GET | `/api/parts/{id}` | Get part details |
| POST | `/api/parts` | Create new part |
| PUT | `/api/parts/{id}` | Update part |
| DELETE | `/api/parts/{id}` | Delete draft part |
| POST | `/api/parts/{id}/release` | Release part |
| POST | `/api/parts/{id}/revise` | Create new revision |
| POST | `/api/parts/{id}/obsolete` | Mark obsolete |

### BOM

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/parts/{id}/bom` | Get BOM tree |
| GET | `/api/parts/{id}/bom/flat` | Get flat BOM |
| POST | `/api/parts/{id}/bom` | Add BOM item |
| PUT | `/api/parts/{id}/bom/{itemId}` | Update BOM item |
| DELETE | `/api/parts/{id}/bom/{itemId}` | Remove BOM item |

### Where-Used

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/parts/{id}/where-used` | Get where-used tree |
| GET | `/api/parts/{id}/impact` | Get change impact analysis |

### AVL

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/parts/{id}/avl` | Get approved vendors |
| POST | `/api/parts/{id}/avl` | Add vendor to AVL |
| PUT | `/api/parts/{id}/avl/{entryId}` | Update AVL entry |
| DELETE | `/api/parts/{id}/avl/{entryId}` | Remove from AVL |

### Import/Export

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/export` | Export database as JSON |
| POST | `/api/import` | Import from JSON |
| POST | `/api/import/excel` | Import from Excel |

---

## Database Schema (PostgreSQL)

```sql
-- Parts table
CREATE TABLE plum_parts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    part_number VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    revision VARCHAR(10) DEFAULT 'A',
    status VARCHAR(20) DEFAULT 'Draft',
    type VARCHAR(20),
    class VARCHAR(50),
    unit_cost DECIMAL(12,4) DEFAULT 0,
    labor_cost DECIMAL(12,4) DEFAULT 0,
    sale_price DECIMAL(12,4),
    distributor_discount DECIMAL(5,2) DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW(),
    modified_at TIMESTAMP DEFAULT NOW(),
    created_by UUID REFERENCES users(id)
);

-- BOM table
CREATE TABLE plum_bom_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    parent_part_id UUID REFERENCES plum_parts(id) ON DELETE CASCADE,
    child_part_id UUID REFERENCES plum_parts(id),
    quantity DECIMAL(12,4) NOT NULL,
    ref_des VARCHAR(100),
    effective_from DATE,
    effective_to DATE,
    notes TEXT,
    sequence INTEGER DEFAULT 0,
    UNIQUE(parent_part_id, child_part_id)
);

-- AVL table
CREATE TABLE plum_avl (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    part_id UUID REFERENCES plum_parts(id) ON DELETE CASCADE,
    vendor_id UUID REFERENCES syerp_vendors(id),
    vendor_part_number VARCHAR(100),
    status VARCHAR(20) DEFAULT 'Pending',
    lead_time INTEGER,
    min_order_qty DECIMAL(12,4),
    unit_price DECIMAL(12,4),
    notes TEXT,
    last_updated TIMESTAMP DEFAULT NOW()
);

-- Substitutes table
CREATE TABLE plum_substitutes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    primary_part_id UUID REFERENCES plum_parts(id) ON DELETE CASCADE,
    substitute_part_id UUID REFERENCES plum_parts(id),
    type VARCHAR(20),
    priority INTEGER DEFAULT 1,
    notes TEXT,
    approved BOOLEAN DEFAULT FALSE
);

-- Indexes
CREATE INDEX idx_parts_number ON plum_parts(part_number);
CREATE INDEX idx_parts_status ON plum_parts(status);
CREATE INDEX idx_bom_parent ON plum_bom_items(parent_part_id);
CREATE INDEX idx_bom_child ON plum_bom_items(child_part_id);
CREATE INDEX idx_avl_part ON plum_avl(part_id);
CREATE INDEX idx_avl_vendor ON plum_avl(vendor_id);
```

---

## Key Implementation Files (Planned)

| Component | Location |
|-----------|----------|
| API routes | `src/api/plum/routes.py` |
| Models | `src/api/plum/models.py` |
| Schemas | `src/api/plum/schemas.py` |
| Services | `src/api/plum/services/` |
| React components | `src/web/features/plum/` |
| State management | `src/web/stores/plumStore.ts` |