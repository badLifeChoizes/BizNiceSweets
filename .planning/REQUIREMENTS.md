# Requirements: BizNiceSweets — Milestone 1 (Foundation + PLUM)

**Defined:** 2026-06-22
**Core Value:** A small manufacturer can run their real product lifecycle on a suite they self-host and own — no per-seat SaaS lock-in.

## v1 Requirements

Milestone 1 scope: a thin foundation (auth, DB, deploy, module shell) + the SYERP core hub it depends on + the PLUM module port. Ends with: "can deploy it, log in, manage vendors/customers, and design parts with multi-level BOMs and cost roll-up."

### Foundation (Core)

- [ ] **CORE-01**: User can run the suite as a containerized deployment via Podman Compose (`podman-compose up`)
- [x] **CORE-02**: User can create an account and log in via OAuth2/JWT authentication
- [x] **CORE-03**: User session persists securely across requests (token issuance + refresh)
- [x] **CORE-04**: Admin can create, edit, and deactivate user accounts
- [x] **CORE-05**: Admin can assign roles to users, and roles gate access to modules and actions
- [x] **CORE-06**: Admin can configure system settings (company info, defaults)
- [x] **CORE-07**: Admin can enable or disable individual modules
- [x] **CORE-08**: User sees a navigation shell listing enabled modules and can switch between them
- [ ] **CORE-09**: Database schema is managed via versioned migrations (Alembic) that apply cleanly on a fresh deploy

### SYERP Core (Hub)

- [x] **SYERP-01**: User can create, view, edit, and delete vendors
- [x] **SYERP-02**: User can search and filter the vendor list
- [x] **SYERP-03**: User can create, view, edit, and delete customers
- [x] **SYERP-04**: User can search and filter the customer list
- [x] **SYERP-05**: System provides a basic general-ledger account structure (chart-of-accounts skeleton)

### PLUM (PLM Port — Core)

- [x] **PLUM-01**: User can create, view, edit, and delete parts
- [x] **PLUM-02**: User can search and filter parts
- [x] **PLUM-03**: User can create part revisions and advance a part through its status workflow
- [ ] **PLUM-04**: User can build a multi-level BOM and view it as an expandable tree
- [ ] **PLUM-05**: User can view a flat BOM with quantity roll-up across levels
- [ ] **PLUM-06**: User can run where-used analysis to see which assemblies consume a part
- [ ] **PLUM-07**: User can link a part to one or more vendors (FK to SYERP vendors / AVL)
- [ ] **PLUM-08**: User can set part pricing/cost and see cost roll-up across a BOM
- [ ] **PLUM-09**: User can view margin analysis for a product
- [ ] **PLUM-10**: User can import and export PLUM data as JSON and Excel

## v2 Requirements

Acknowledged, deferred to later milestones. Tracked but not in this roadmap.

### FLAN (PM Port)

- **FLAN-01**: Port FLAN project management to the new stack (projects, phases, tasks, timeline, budgets)

### PLUM Advanced

- **PLUM-11**: Document links (URL/path references, document types)
- **PLUM-12**: Document management (file upload, versioning, in-app preview)
- **PLUM-13**: ECO workflow (creation, approval, impact analysis)

### Later Suites

- **MOUSSE-xx**: Manufacturing execution (work orders, routing, work instructions, shop floor)
- **SYERP-xx**: Extended ERP (inventory, purchase orders, AP/AR, financial reporting)
- **CRUMB-xx**: CRM (leads, opportunities, quotes, orders)
- **GELATO-xx**: Warehouse management (locations, pick/pack/ship, lot/serial)
- **CRISP-xx**: Quality management (inspections, NCR, CAPA, audit trail)

## Out of Scope

Explicitly excluded from Milestone 1.

| Feature | Reason |
|---------|--------|
| Re-porting FLAN | HTML prototype covers project mgmt for now; deferred to a later milestone |
| MOUSSE / CRUMB / GELATO / CRISP modules | Later phases per dependency-first roadmap |
| Inventory, purchase orders, work orders | Live in SYERP-extended + MOUSSE (Phase 2), not Milestone 1 |
| Offline capability / sync | Standing constraint but a cross-module Phase 4 concern |
| Cloud/hosted SaaS offering | Product is self-hosted by design |
| Real-time multi-user collaboration | Auth + shared DB only for now |

## Traceability

Which phases cover which requirements. Populated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| CORE-01 | Phase 1 | Pending |
| CORE-09 | Phase 1 | Pending |
| CORE-02 | Phase 2 | Complete |
| CORE-03 | Phase 2 | Complete |
| CORE-04 | Phase 2 | Complete |
| CORE-05 | Phase 2 | Complete |
| CORE-06 | Phase 3 | Complete |
| CORE-07 | Phase 3 | Complete |
| CORE-08 | Phase 3 | Complete |
| SYERP-01 | Phase 4 | Complete |
| SYERP-02 | Phase 4 | Complete |
| SYERP-03 | Phase 4 | Complete |
| SYERP-04 | Phase 4 | Complete |
| SYERP-05 | Phase 4 | Complete |
| PLUM-01 | Phase 5 | Complete |
| PLUM-02 | Phase 5 | Complete |
| PLUM-03 | Phase 5 | Complete |
| PLUM-04 | Phase 6 | Pending |
| PLUM-05 | Phase 6 | Pending |
| PLUM-06 | Phase 6 | Pending |
| PLUM-07 | Phase 6 | Pending |
| PLUM-08 | Phase 6 | Pending |
| PLUM-09 | Phase 6 | Pending |
| PLUM-10 | Phase 6 | Pending |

**Coverage:**
- v1 requirements: 24 total
- Mapped to phases: 24
- Unmapped: 0

---
*Requirements defined: 2026-06-22*
*Last updated: 2026-06-22 after roadmap creation*
