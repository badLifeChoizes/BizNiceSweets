# BizNiceSweets Roadmap

**Version:** 1.0
**Created:** 2025-12-21
**Based on:** [Roadmap Planning Interview](interviews/roadmap-planning.md)

## Vision

BizNiceSweets is an open source, modular business suite built for small-to-medium manufacturers. Initially developed for a medical simulation training devices company, it's designed to be useful for any business that designs, manufactures, and sells physical products.

## Architecture Summary

| Aspect | Decision |
|--------|----------|
| Deployment | Self-hosted server with offline capability |
| License | Open Core (core open source, premium add-ons) |
| Architecture | Modular Monolith (installable modules, shared database) |
| Tech Stack | Python FastAPI + React + PostgreSQL + Podman |
| Integration | SYERP as hub, modules connect via foreign keys |

## The Seven Suites

| Suite | Full Name | Purpose | Phase |
|-------|-----------|---------|-------|
| SYERP | Enterprise Resource Planning | Financials, vendors, inventory (hub) | 0-2 |
| PLUM | Product Lifecycle Management | Parts, BOMs, product design | 1 |
| FLAN | Project Management | Projects, tasks, team coordination | 1 |
| MOUSSE | Manufacturing Execution System | Work orders, shop floor | 2 |
| CRUMB | Customer Relationship Management | Leads, sales, customer portal | 3 |
| GELATO | Warehouse Management System | Locations, pick/pack/ship | 3 |
| CRISP | Quality Management System | Inspections, compliance, CAPA | 4 |

## Phase Overview

```text
PHASE 0          PHASE 1           PHASE 2           PHASE 3           PHASE 4
Foundation       Product Dev       Operations        Customer/Logistics Quality/Release
    │                │                 │                 │                 │
    ▼                ▼                 ▼                 ▼                 ▼
┌────────┐      ┌─────────┐      ┌──────────┐      ┌──────────┐      ┌──────────┐
│ Core   │      │  PLUM   │      │  SYERP   │      │  CRUMB   │      │  CRISP   │
│ SYERP  │ ───► │  FLAN   │ ───► │  MOUSSE  │ ───► │  GELATO  │ ───► │  Polish  │
│ basics │      │         │      │ extended │      │          │      │          │
└────────┘      └─────────┘      └──────────┘      └──────────┘      └──────────┘
```

---

## Phase 0: Foundation

**Milestone:** "Can log in, manage vendors and customers"

### Deliverables

- [ ] Project scaffolding (FastAPI + React + TypeScript)
- [ ] Database schema and migrations (SQLAlchemy + Alembic)
- [ ] Authentication system (OAuth2 / JWT)
- [ ] User and role management
- [ ] Settings and configuration system
- [ ] Module enable/disable system
- [ ] SYERP Core: Vendors CRUD
- [ ] SYERP Core: Customers CRUD
- [ ] SYERP Core: Basic general ledger structure
- [ ] Deployment: Podman Compose configuration
- [ ] Basic UI shell with navigation

### Technical Foundation

```text
Backend (FastAPI):
├── src/
│   ├── core/           # Auth, users, settings
│   ├── modules/
│   │   └── syerp/      # First module
│   └── shared/         # Database, utilities
└── alembic/            # Migrations

Frontend (React + TypeScript):
├── src/
│   ├── components/     # Shared UI components
│   ├── modules/
│   │   └── syerp/      # Module views
│   └── lib/            # API client, utilities
└── public/
```

---

## Phase 1: Product Development

**Milestone:** "Can design products and manage development projects"

### PLUM Module (PLM)

- [ ] Parts management (CRUD, search, filtering)
- [ ] Part revisions and status workflow
- [ ] Bill of Materials (BOM) tree view
- [ ] BOM flat view with quantity roll-up
- [ ] Part-to-vendor linking (FK to SYERP.vendors)
- [ ] Product pricing and cost roll-up
- [ ] Margin analysis views
- [ ] Where-used analysis
- [ ] Data import/export (JSON, Excel)

### FLAN Module (Project Management)

- [ ] Projects management (CRUD, categories)
- [ ] Phases/epics with progress tracking
- [ ] Subtasks and checklists
- [ ] Team member management
- [ ] Assignees and @mentions
- [ ] Timeline/Gantt view
- [ ] Deliverables tracking
- [ ] Time entry logging
- [ ] Project dashboard

### Integration Points

- PLUM references SYERP.vendors for AVL
- FLAN team members reference Core.users
- Both modules share authentication context

---

## Phase 2: Operations

**Milestone:** "Can manufacture products and track inventory"

### SYERP Extended

- [ ] Inventory management (items, quantities, locations)
- [ ] Inventory transactions and history
- [ ] Purchase order workflow
- [ ] Vendor purchase history
- [ ] Invoice management (AP/AR basics)
- [ ] Basic financial reporting

### MOUSSE Module (Manufacturing)

- [ ] Work order creation and management
- [ ] Work order status workflow
- [ ] Routing definition (operations, work centers)
- [ ] BOM consumption (link to PLUM BOMs)
- [ ] Inventory consumption tracking
- [ ] Shop floor execution view
- [ ] Production scheduling (basic)
- [ ] Work order costing

### Integration Points

- MOUSSE.work_orders reference PLUM.parts and PLUM.boms
- MOUSSE consumes SYERP.inventory
- MOUSSE creates SYERP.inventory_transactions
- Work order costs flow to SYERP

---

## Phase 3: Customer & Logistics

**Milestone:** "Can sell to customers and ship products"

### CRUMB Module (CRM)

- [ ] Lead management
- [ ] Opportunity pipeline
- [ ] Quote generation
- [ ] Customer portal (for marketplace model)
- [ ] Order management
- [ ] Customer communication log
- [ ] Sales dashboard

### GELATO Module (Warehouse)

- [ ] Warehouse and location management
- [ ] Bin/zone organization
- [ ] Receiving workflow
- [ ] Pick/pack/ship workflow
- [ ] Lot tracking
- [ ] Serial number tracking
- [ ] Shipping integration prep
- [ ] Inventory counts

### Integration Points

- CRUMB.customers reference SYERP.customers
- CRUMB.orders create SYERP.sales_orders
- GELATO manages physical SYERP.inventory
- GELATO.shipments link to CRUMB.orders

---

## Phase 4: Quality & Polish

**Milestone:** "Complete suite, ready for public release"

### CRISP Module (Quality)

- [ ] Inspection definitions
- [ ] Inspection execution and recording
- [ ] Non-conformance reports (NCRs)
- [ ] CAPA (Corrective and Preventive Actions)
- [ ] Quality holds on inventory
- [ ] Regulatory compliance tracking
- [ ] Quality metrics dashboard
- [ ] Audit trail for compliance

### Cross-Module Enhancements

- [ ] Offline capability (Service Worker + IndexedDB)
- [ ] Offline sync when reconnected
- [ ] Cross-module reporting dashboard
- [ ] Data export for all modules
- [ ] Backup/restore utilities
- [ ] Documentation for self-hosting
- [ ] Documentation for users
- [ ] Performance optimization
- [ ] Security audit

### Integration Points

- CRISP.inspections link to MOUSSE.work_orders
- CRISP.ncrs can hold SYERP.inventory
- CRISP quality data informs PLUM part quality scores

---

## Technology Stack Reference

### Backend

| Component | Choice | License |
|-----------|--------|---------|
| Framework | FastAPI | MIT |
| ORM | SQLAlchemy 2.0 | MIT |
| Database | PostgreSQL | PostgreSQL License |
| Auth | OAuth2 / JWT | - |
| API Docs | OpenAPI (auto-generated) | - |

### Frontend

| Component | Choice | License |
|-----------|--------|---------|
| Framework | React 18+ | MIT |
| Language | TypeScript | Apache 2.0 |
| Styling | Tailwind CSS | MIT |
| Components | shadcn/ui | MIT |
| State | Zustand or TanStack Query | MIT |
| Offline | Service Worker + IndexedDB | - |

### Deployment

| Component | Choice | License |
|-----------|--------|---------|
| Container | Podman | Apache 2.0 |
| Orchestration | Podman Compose | Apache 2.0 |
| Alternative | Docker Engine CLI | Apache 2.0 |

---

## Module Dependencies

```text
                    ┌─────────────────────────────────────┐
                    │              CORE                    │
                    │  (Auth, Users, Settings, Companies) │
                    └──────────────────┬──────────────────┘
                                       │
                    ┌──────────────────▼──────────────────┐
                    │             SYERP (Hub)              │
                    │  Vendors, Customers, Inventory, GL  │
                    └──────────────────┬──────────────────┘
                                       │
          ┌────────────────────────────┼────────────────────────────┐
          │                            │                            │
          ▼                            ▼                            ▼
    ┌───────────┐              ┌─────────────┐              ┌─────────────┐
    │   PLUM    │              │    FLAN     │              │   CRUMB     │
    │   (PLM)   │              │    (PM)     │              │   (CRM)     │
    └─────┬─────┘              └─────────────┘              └──────┬──────┘
          │                                                        │
          ▼                                                        ▼
    ┌───────────┐                                           ┌─────────────┐
    │  MOUSSE   │◄──────────────────────────────────────────│   GELATO    │
    │   (MES)   │                                           │   (WMS)     │
    └─────┬─────┘                                           └─────────────┘
          │
          ▼
    ┌───────────┐
    │   CRISP   │
    │   (QMS)   │
    └───────────┘
```

---

## Success Criteria

### Phase 0 Complete When

- [ ] Can create a user account and log in
- [ ] Can create, read, update, delete vendors
- [ ] Can create, read, update, delete customers
- [ ] Can deploy with `podman-compose up`

### Phase 1 Complete When

- [ ] Can create parts with full revision history
- [ ] Can build multi-level BOMs
- [ ] Can manage projects with phases and tasks
- [ ] Can track team workload

### Phase 2 Complete When

- [ ] Can track inventory quantities and locations
- [ ] Can create and process purchase orders
- [ ] Can create and execute work orders
- [ ] Manufacturing consumes inventory correctly

### Phase 3 Complete When

- [ ] Can manage sales pipeline from lead to order
- [ ] Can pick, pack, and ship orders
- [ ] Can track lot/serial numbers

### Phase 4 Complete When

- [ ] Can perform inspections and record quality data
- [ ] Can work offline and sync when reconnected
- [ ] Documentation sufficient for self-hosting
- [ ] Ready for public open source release

---

## Related Documents

- [Roadmap Planning Interview](interviews/roadmap-planning.md) - All 7 architecture decisions
- [Analysis Report](reports/analysis-report-existing-apps.md) - PLUM/FLAN prototype analysis
- [Architecture Decisions](decisions.md) - Phase 1 discovery decisions