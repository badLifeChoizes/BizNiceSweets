# BizNiceSweets Architecture Decisions

**Created:** 2025-12-20
**Status:** Complete

This document records key architectural decisions made during the planning phase.

---

## Decision Log

| # | Topic | Decision | Date |
|---|-------|----------|------|
| 1 | Business Domain | **Hybrid - Open Source Business Suite** | 2025-12-20 |
| 2 | PLUM Phase 20 (Manufacturing) | **Move to MOUSSE** | 2025-12-20 |
| 3 | Next Suite Priority | **Parallel: SYERP + MOUSSE** | 2025-12-20 |
| 4 | Data Integration Strategy | **Future API Ready (Hybrid)** | 2025-12-20 |
| 5 | Shared Infrastructure | **Progressive Expansion** | 2025-12-20 |

---

## Decision 1: Business Domain

**Status:** DECIDED

### Question

What is the primary business domain for BizNiceSweets?

### Decision

**Option D: Hybrid - Open Source Business Suite**

BizNiceSweets is an open source collection of integrated business software tools:

| Suite | Full Name | Purpose |
| ----- | --------- | ------- |
| FLAN | Project Management | Project planning and tracking |
| PLUM | Product Lifecycle Management | Product/BOM management |
| CRUMB | Customer Relationship Management | Customer and sales management |
| MOUSSE | Manufacturing Execution System | Shop floor and production |
| GELATO | Warehouse Management System | Inventory and logistics |
| CRISP | Quality Management System | Quality assurance |
| SYERP | Enterprise Resource Planning | Financials and core business |

### Implications

- All seven suites are relevant and will be developed
- Integration between suites is critical
- Each suite should be usable standalone but integrate when others are present
- Phased development approach required

---

## Decision 2: PLUM Phase 20 (Manufacturing in PLM)

**Status:** DECIDED

### Question

Should manufacturing features (facilities, work centers, routings) be in PLUM or MOUSSE?

### Decision

**Option A: Move to MOUSSE**

- PLUM is for product **development** - designing parts, BOMs, specifications
- Products are **released** from PLUM, then added to MOUSSE for manufacturing
- Clear handoff point: Released product data flows from PLUM → MOUSSE

### Integration Requirements Identified

| From | To | Data Flow | Trigger |
| ---- | -- | --------- | ------- |
| PLUM | MOUSSE | Released product/BOM | Product release |
| PLUM | MOUSSE | Part specifications | On-demand sync |
| MOUSSE | PLUM | Manufacturing feedback | ECO requests |

### Action Items

- [ ] Mark PLUM Phase 20 as "Relocated to MOUSSE" in PLUM roadmap
- [ ] Create MOUSSE requirements based on Phase 20 features
- [ ] Define PLUM→MOUSSE integration specification

---

## Decision 3: Next Suite Priority

**Status:** DECIDED

### Question

After stabilizing PLUM (v54) and FLAN (v24), which suite should be developed next?

### Decision

**Option D: Parallel Development - SYERP + MOUSSE**

Build both suites simultaneously:

| Suite | Source | Key Features |
| ----- | ------ | ------------ |
| SYERP | Extract from FLAN | Expense ledger, POs, vendors, invoicing, GL |
| MOUSSE | New + PLUM Phase 20 | Work orders, production scheduling, shop floor |

### Development Tracks

```
Track 1 (FLAN → SYERP):
  FLAN Phase 18 budget features → SYERP financials core

Track 2 (PLUM → MOUSSE):
  PLUM Phase 20 features → MOUSSE manufacturing core
```

### Benefits of Parallel Approach

- Addresses both identified migration paths
- Shared integration infrastructure development
- Faster time to complete suite ecosystem

---

## Decision 4: Data Integration Strategy

**Status:** DECIDED

### Question

How should BizNiceSweets suites share data with each other?

### Decision

**Option D: Future API Ready (Hybrid)**

Abstract data layer that works with LocalStorage/IndexedDB now, swappable to API later.

```text
┌─────────────────────────────────────────────────────┐
│                    SUITES                           │
│  ┌─────┐  ┌─────┐  ┌─────┐  ┌──────┐  ┌──────┐    │
│  │PLUM │  │FLAN │  │SYERP│  │MOUSSE│  │ ... │     │
│  └──┬──┘  └──┬──┘  └──┬──┘  └──┬───┘  └──┬───┘    │
│     └────────┴────────┴────────┴─────────┘         │
│                       │                             │
│              ┌────────▼────────┐                   │
│              │   DataService   │ ← Abstract layer  │
│              └────────┬────────┘                   │
│     ┌─────────────────┼─────────────────┐          │
│  ┌──▼──┐         ┌────▼────┐      ┌────▼────┐     │
│  │Local│         │Indexed  │      │  API    │     │
│  │Store│         │   DB    │      │(future) │     │
│  └─────┘         └─────────┘      └─────────┘     │
└─────────────────────────────────────────────────────┘
```

### Benefits

- Works offline now with browser storage
- Clean architecture - suites don't know about storage details
- Easy to add cloud backends later (Firebase, Supabase, self-hosted)
- Open source contributors can add backends without changing suite code

### Action Items

- [ ] Design DataService interface specification
- [ ] Define shared data entities (vendors, products, customers)
- [ ] Create localStorage adapter as first implementation

---

## Decision 5: Shared Infrastructure Components

**Status:** DECIDED

### Question

What infrastructure should be shared across all BizNiceSweets suites?

### Decision

**Option C: Progressive Expansion**

Build shared infrastructure incrementally as needs are validated:

| Phase | Components | Trigger |
| ----- | ---------- | ------- |
| Phase 1 | DataService, Vendor Master | With SYERP/MOUSSE development |
| Phase 2 | Document Storage, Notifications | When needed |
| Phase 3 | User/Auth, UI Library, Reporting | Future |

### Action Items

- [ ] Design DataService interface
- [ ] Define Vendor Master schema (unify PLUM AVL + FLAN vendors)
- [ ] Plan Phase 2 triggers

---

## Summary: All Decisions Complete

| # | Topic | Decision |
| - | ----- | -------- |
| 1 | Business Domain | Hybrid - Open Source Business Suite (7 suites) |
| 2 | PLUM Phase 20 | Move manufacturing features to MOUSSE |
| 3 | Next Priority | Parallel development: SYERP + MOUSSE |
| 4 | Data Integration | Future API Ready with abstract DataService |
| 5 | Infrastructure | Progressive expansion (build as needed) |

### Next Steps

1. Create master `docs/ROADMAP.md` based on these decisions
2. Create suite documentation using templates
3. Define integration specifications

---
