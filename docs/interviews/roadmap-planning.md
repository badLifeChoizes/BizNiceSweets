# ROADMAP Planning Interview

**Created:** 2025-12-21
**Status:** Complete
**Output:** Will generate `docs/ROADMAP.md`

---

## Context

Planning the BizNiceSweets ecosystem roadmap. Started with architecture assumptions based on prototypes (PLUM/FLAN), but discovered those had different constraints. Now gathering actual requirements for BizNiceSweets.

---

## Decision Log

| # | Topic | Decision | Date |
|---|-------|----------|------|
| 1 | Deployment Model | Self-hosted server + offline capability (like Odoo) | 2025-12-21 |
| 2 | Multi-User Scale | Small team (3-10) initially, architect for growth | 2025-12-21 |
| 3 | Open Source Model | Open Core (core open, premium features paid) | 2025-12-21 |
| 4 | Target Users | Medical simulation devices; build for self, release for all | 2025-12-21 |
| 5 | Technology Stack | Python FastAPI + React + PostgreSQL + Podman | 2025-12-21 |
| 6 | Integration Architecture | Modular Monolith (installable modules, shared DB) | 2025-12-21 |
| 7 | Phase Structure | 5-Phase: Foundation → Product → Operations → Customer/Logistics → Quality | 2025-12-21 |

---

## Decision 1: Deployment Model

**Status:** DECIDED

### Question
How do you envision BizNiceSweets being deployed and used?

### Decision
**Self-hosted server application with offline capability**

Key characteristics:
- Server-based architecture (like Odoo)
- User self-hosted (owns their data)
- Works offline when connectivity is unavailable
- Future cloud hosting option for those who prefer managed service

### Rationale
- User mentioned wanting it "like Odoo" with server capability
- Local-first means offline-capable, not desktop-only
- Self-hosted aligns with open source business software model

### Implications
- Need database that works both server and offline modes
- API layer required for client-server communication
- Sync mechanism needed for offline scenarios

---

## Decision 2: Multi-User & Collaboration

**Status:** DECIDED

### Question
How many users do you expect to work with the system simultaneously?

### Decision
**Small team initially (3-10 users) with architecture designed to scale**

Key characteristics:
- Start with basic roles and permissions
- Build foundation that can grow to medium/enterprise
- Don't over-engineer initially, but don't limit future growth

### Rationale
- Early stage business starting small
- Intent to scale as business grows
- Common pattern for open source business software

### Implications
- User/role system from the start
- Database schema should support multi-tenant patterns
- Consider permission model that can evolve

---

## Decision 3: Open Source Model

**Status:** DECIDED

### Question
How do you want to handle the open source aspect of BizNiceSweets?

### Decision
**Open Core model**

Key characteristics:
- Core ERP functionality: Open source
- Premium modules/features: Proprietary license
- Self-host free, pay for extras
- Revenue from: premium modules, enterprise features, hosting

### Rationale
- Balances community contribution with business sustainability
- Proven model (Odoo, GitLab, ERPNext)
- Allows building a business while giving back to community

### Implications
- License choice matters (AGPL common for open core ERP)
- Need to define what's "core" vs "premium"
- Community contribution guidelines needed

---

## Decision 4: Target Users & Business Context

**Status:** DECIDED

### Question
Who is the target user for BizNiceSweets? What kind of businesses?

### Decision
**Build for own business first, release as general-purpose open source**

#### Primary Business Context
Medical simulation training devices company:
- Designs and manufactures training manikins
- Modular framework - customers and developers can extend/modify
- Core product: extendable manikin + controlling app
- Business model: Product company + platform/marketplace for medical simulation

#### Suite Relevance (All 7 Apply)

| Suite | Use Case |
|-------|----------|
| PLUM (PLM) | Manikin component design, BOMs, modular specs |
| FLAN (PM) | Development projects, product roadmaps |
| SYERP (ERP) | Vendors, financials, inventory valuation |
| MOUSSE (MES) | Manufacturing the manikins |
| CRUMB (CRM) | Customers, developers, marketplace participants |
| CRISP (QMS) | Medical device quality, regulatory compliance |
| GELATO (WMS) | Shipping devices, component inventory |

### Rationale
- "Scratch your own itch" development - build what you need
- All suites are relevant to the business
- Will release for anyone interested once mature

### Implications
- Real-world use cases to validate against
- Can prioritize based on immediate business needs
- Quality management (CRISP) may have regulatory importance for medical devices

---

## Decision 5: Technology Stack

**Status:** DECIDED

### Question

What technology stack should BizNiceSweets use?

### Decision

**Modern Python + React stack with fully open source tooling**

```
┌─────────────────────────────────────────────────────────────┐
│                     TECHNOLOGY STACK                         │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  FRONTEND                                                    │
│  ├── Framework: React 18+ with TypeScript                   │
│  ├── UI Library: Tailwind CSS + shadcn/ui                   │
│  ├── State: Zustand or TanStack Query                       │
│  └── Offline: Service Worker + IndexedDB                    │
│                                                              │
│  BACKEND                                                     │
│  ├── Framework: Python FastAPI                              │
│  ├── ORM: SQLAlchemy 2.0                                    │
│  ├── Auth: Built-in OAuth2 / JWT                            │
│  └── API: REST with auto-generated OpenAPI docs             │
│                                                              │
│  DATABASE                                                    │
│  ├── Server: PostgreSQL (open source)                        │
│  └── Offline: SQLite or IndexedDB (browser)                 │
│                                                              │
│  DEPLOYMENT                                                  │
│  ├── Container: Podman (fully open source, no licensing)    │
│  ├── Orchestration: Podman Compose                           │
│  ├── Alternative: Docker Engine CLI (Apache 2.0)            │
│  └── Self-host: Single `podman-compose up`                  │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### Licensing Verification

| Component | License | Commercial Use |
|-----------|---------|----------------|
| React | MIT | Free, unrestricted |
| TypeScript | Apache 2.0 | Free, unrestricted |
| Tailwind CSS | MIT | Free, unrestricted |
| shadcn/ui | MIT | Free, unrestricted |
| FastAPI | MIT | Free, unrestricted |
| SQLAlchemy | MIT | Free, unrestricted |
| PostgreSQL | PostgreSQL License (MIT-like) | Free, unrestricted |
| Podman | Apache 2.0 | Free, unrestricted |
| Docker Engine | Apache 2.0 | Free, unrestricted |

Note: Docker Desktop has commercial restrictions. Podman recommended as primary.

### Rationale

- **FastAPI over Django**: Lighter, modern async, build only what's needed
- **React over Vue**: Larger ecosystem, more third-party components
- **Podman over Docker Desktop**: Truly free for commercial use, daemonless, rootless by default
- **PostgreSQL**: Industry standard for ERP, robust transactions, excellent Python support

### Offline Strategy

```
ONLINE MODE:
  Browser ←→ FastAPI Server ←→ PostgreSQL

OFFLINE MODE:
  Browser ←→ Service Worker ←→ IndexedDB (local cache)

SYNC (when back online):
  IndexedDB changes ←→ Reconciliation logic ←→ PostgreSQL
```

### Development Approach

- Claude Code as primary development resource
- All technologies have extensive documentation Claude can reference
- TypeScript provides type safety and better AI code completion
- OpenAPI spec enables auto-generated client libraries

---

## Decision 6: Integration Architecture

**Status:** DECIDED

### Question

How should the 7 BizNiceSweets suites integrate with each other?

### Decision

**Modular Monolith with installable modules**

```text
┌─────────────────────────────────────────────────────────────┐
│                    BizNiceSweets Core                        │
│  ┌─────────────────────────────────────────────────────────┐│
│  │  Core: Auth, Users, Settings, Shared Entities           ││
│  └─────────────────────────────────────────────────────────┘│
│                                                              │
│  Modules (enable/disable per installation):                  │
│  ┌───────┐ ┌───────┐ ┌───────┐ ┌───────┐ ┌───────┐        │
│  │ PLUM  │ │ FLAN  │ │SYERP  │ │MOUSSE │ │ etc.  │        │
│  └───────┘ └───────┘ └───────┘ └───────┘ └───────┘        │
│                           │                                  │
│                    ┌──────▼──────┐                          │
│                    │ PostgreSQL  │                          │
│                    └─────────────┘                          │
└─────────────────────────────────────────────────────────────┘
```

### Key Characteristics

- Single deployable application with optional modules
- Core always present (auth, users, settings)
- Modules can be enabled/disabled per installation
- Shared PostgreSQL database - cross-module queries via foreign keys
- SYERP as natural hub - shared entities (vendors, customers, inventory) live in SYERP tables

### Database Schema Pattern

```text
Core Tables (always present):
├── users, roles, permissions
├── settings, audit_log
└── companies (multi-tenant ready)

SYERP Tables (hub - when enabled):
├── vendors (master)
├── customers (master)
├── inventory (master)
└── gl_accounts, transactions, purchase_orders

PLUM Tables (when enabled):
├── parts, boms, revisions
├── part_vendors → FK to SYERP.vendors
└── part_inventory → FK to SYERP.inventory

MOUSSE Tables (when enabled):
├── work_orders, routings
├── work_order_parts → FK to PLUM.parts
└── work_order_inventory → FK to SYERP.inventory
```

### Rationale

- Matches Open Core model (core free, premium modules add-on)
- Odoo uses this proven pattern
- Right-sized complexity for small team
- Enables "install what you need"
- Shared database makes cross-module queries trivial
- No message bus or complex sync needed - just foreign keys

---

## Decision 7: Phase Structure

**Status:** DECIDED

### Question

How should BizNiceSweets development be phased?

### Decision

**5-Phase roadmap: Foundation → Product Dev → Operations → Customer & Logistics → Quality & Polish**

```text
PHASE 0: Foundation
├── Core Framework (FastAPI + React + PostgreSQL)
├── Auth, users, roles, settings
├── SYERP Core: Vendors, Customers, basic GL
├── Module system (enable/disable)
└── Deployment: Podman compose
Milestone: "Can log in, manage vendors and customers"

PHASE 1: Product Development
├── PLUM Module (PLM)
│   ├── Parts, BOMs, revisions
│   ├── Vendor linking (FK to SYERP.vendors)
│   └── Product pricing and costing
└── FLAN Module (Project Management)
    ├── Projects, phases, tasks
    ├── Team management
    └── Timeline/Gantt views
Milestone: "Can design products and manage dev projects"

PHASE 2: Operations
├── SYERP Extended
│   ├── Inventory management
│   ├── Purchase orders
│   └── Invoicing, AP/AR
└── MOUSSE Module (Manufacturing)
    ├── Work orders
    ├── Routings (from PLUM BOMs)
    └── Shop floor execution
Milestone: "Can manufacture products, track inventory"

PHASE 3: Customer & Logistics
├── CRUMB Module (CRM)
│   ├── Leads, opportunities, quotes
│   ├── Customer portal (for marketplace)
│   └── Order management
└── GELATO Module (Warehouse)
    ├── Location management
    ├── Pick/pack/ship
    └── Lot/serial tracking
Milestone: "Can sell to customers and ship products"

PHASE 4: Quality & Polish
├── CRISP Module (Quality)
│   ├── Inspections, NCRs
│   ├── CAPA management
│   └── Regulatory compliance tracking
└── Cross-Module Enhancements
    ├── Offline capability
    ├── Reporting/dashboards
    └── Public release preparation
Milestone: "Complete suite, ready for public release"
```

### Phase Summary

| Phase | Modules | Milestone |
|-------|---------|-----------|
| 0 | Core + SYERP basics | Login, vendors, customers |
| 1 | PLUM + FLAN | Design products, manage projects |
| 2 | SYERP extended + MOUSSE | Manufacturing, inventory |
| 3 | CRUMB + GELATO | Sales, shipping |
| 4 | CRISP + Polish | Quality, compliance, release |

### Rationale

- **Phase 0**: SYERP first as hub - core infrastructure before modules
- **Phase 1**: PLUM + FLAN get feature parity with existing prototypes quickly
- **Phase 2**: SYERP inventory + MOUSSE enables manufacturing manikins
- **Phase 3**: CRUMB + GELATO for customer sales and product shipping
- **Phase 4**: CRISP for medical device compliance + final polish for release

---

## Notes

- Prototypes (PLUM v54, FLAN v24) were built with different constraints
- Those were single-file HTML apps to avoid IT involvement at work
- BizNiceSweets is a fresh start without those constraints
- Architecture decisions should not be anchored on prototype patterns

---