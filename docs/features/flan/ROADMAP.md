# FLAN Roadmap

FLAN-specific development phases from prototype to production.

---

## Overview

FLAN's prototype (v24) contains 130+ features, significantly exceeding Phase 1 requirements. This roadmap defines how to migrate and extend these features.

| Phase | Focus | Key Deliverables |
|-------|-------|------------------|
| 1.0 | Core Migration | Port prototype to FastAPI/React/PostgreSQL |
| 1.5 | Portfolio & Resources | Cross-project views, resource leveling |
| 2.0+ | Advanced (Deferred) | EVM metrics, custom fields |

---

## Phase 1.0: Core Migration

**Goal:** Port proven prototype functionality to production stack.

**Milestone:** "Can create and track projects with phases, team, and time"

### Core Project Management

- [ ] Project CRUD with PostgreSQL persistence
- [ ] Project categories and search
- [ ] Project list with pinned/recent
- [ ] Project duplication

### Phase/Epic Management

- [ ] Phase CRUD with all attributes
- [ ] Progress slider (0-100%)
- [ ] Status workflow (pending/in-progress/complete)
- [ ] Phase scheduling (start/due dates)
- [ ] Priority and tags
- [ ] Phase dependencies (no circular)
- [ ] Drag & drop reorder
- [ ] Bulk actions (complete, delete)

### Subtasks

- [ ] Subtask CRUD within phases
- [ ] Checkbox completion tracking
- [ ] JIRA key display (optional)
- [ ] Subtask dates (optional)

### Team Management

- [ ] Team member registry per project
- [ ] Assignees on phases
- [ ] @mentions in comments (display only)
- [ ] Avatar colors

### Time Tracking

- [ ] Time entry CRUD
- [ ] Hours per phase per team member
- [ ] Hourly rates for cost calculation
- [ ] Labor cost roll-up

### Deliverables

- [ ] Deliverable CRUD
- [ ] Date-based tracking
- [ ] Countdown timers
- [ ] Urgency indicators
- [ ] Status workflow

### Visualizations

- [ ] Timeline/Gantt view
- [ ] Calendar view
- [ ] Progress charts (pie/bar)
- [ ] Project dashboard with KPIs

### Notes & Comments

- [ ] Project notes (Markdown)
- [ ] Phase comments
- [ ] Activity log

### Import/Export

- [ ] JSON backup/restore
- [ ] CSV export
- [ ] Excel export
- [ ] PDF report generation

### Project Budget (FLAN-owned)

- [ ] Budget settings per project
- [ ] Phase budget estimates
- [ ] Budget vs actual comparison
- [ ] Budget alerts at thresholds

---

## Phase 1.5: Portfolio & Resources

**Goal:** Enable cross-project management and resource optimization.

**Milestone:** "Can view all projects together and balance team workload"

### Portfolio View

- [ ] Multi-project dashboard
- [ ] Project health comparison
- [ ] Combined timeline view
- [ ] Portfolio-level KPIs
- [ ] Project filtering and grouping

### Resource Leveling

- [ ] Team workload across projects
- [ ] Over-allocation warnings
- [ ] Resource utilization charts
- [ ] Assignment recommendations
- [ ] What-if scenario planning

### Enhanced Reporting

- [ ] Cross-project time reports
- [ ] Resource utilization reports
- [ ] Portfolio status summaries

---

## Future Phases (Deferred)

These features are tracked but not prioritized for Phase 1:

### EVM Metrics (Earned Value Management)

- [ ] Planned Value (PV) calculation
- [ ] Earned Value (EV) calculation
- [ ] Actual Cost (AC) tracking
- [ ] Schedule Performance Index (SPI)
- [ ] Cost Performance Index (CPI)
- [ ] Estimate at Completion (EAC)

**Decision:** Deferred until user demand demonstrates need for formal EVM.

### Custom Fields

- [ ] User-defined fields on phases
- [ ] Field types: text, number, date, dropdown
- [ ] Field validation rules
- [ ] Custom field filtering

**Decision:** Deferred until specific use cases identified.

---

## Features NOT in FLAN

These prototype features belong in other modules:

| Feature | Migrates To | Integration Pattern |
|---------|-------------|---------------------|
| Vendor Management | SYERP | FLAN reads vendor list via API |
| Vendor CRUD | SYERP | FLAN has read-only access |
| Expense Ledger | SYERP | FLAN maps project expenses to phases |
| Purchase Orders | SYERP | FLAN can reference PO numbers |
| Invoice Generation | FLAN + SYERP | FLAN generates, SYERP tracks AR |

### What FLAN Keeps

| Feature | Notes |
|---------|-------|
| Project Budgets | FLAN owns project-level budget settings |
| Phase Budget Estimates | Tracked within FLAN |
| Project Work Invoices | FLAN generates invoices for time-based billing |
| Expense-to-Phase Mapping | FLAN links expenses to phases for cost tracking |

---

## Risk Register & Governance (Included in 1.0)

These prototype features are part of core migration:

- [ ] Risk register (impact, probability, mitigation)
- [ ] Milestones with dates
- [ ] Decision log
- [ ] Recurring phase templates

---

## Technical Migration Notes

### From Prototype to Production

| Aspect | Prototype | Production |
|--------|-----------|------------|
| Storage | LocalStorage | PostgreSQL |
| Frontend | Vanilla JS | React + TypeScript |
| Backend | None (client-only) | FastAPI |
| Auth | None | OAuth2 / JWT |
| Multi-user | Single user | Multi-tenant |

### Data Migration

1. Export prototype data as JSON
2. Transform to match PostgreSQL schema
3. Import via API or migration script
4. Validate data integrity

### API Design Principles

- RESTful endpoints for CRUD operations
- Bulk operations for efficiency
- Optimistic updates with conflict resolution
- Real-time updates via WebSocket (future)

---

## Dependencies

```text
Phase 0 (Foundation)
    │
    ├── Auth system ready
    ├── User management ready
    └── Database schema ready
    │
    ▼
Phase 1.0 (FLAN Core)
    │
    ├── Can operate standalone
    └── Optional: Team members link to Core.users
    │
    ▼
Phase 1.5 (Portfolio + Resources)
    │
    └── Requires multiple projects in system
    │
    ▼
Future (EVM, Custom Fields)
    │
    └── Based on user demand
```

---

## Success Criteria

### Phase 1.0 Complete When

- [ ] Can create projects with phases, subtasks
- [ ] Can assign team members and log time
- [ ] Can track deliverables with dates
- [ ] Can manage project budget
- [ ] Can view timeline/Gantt
- [ ] Can export data as JSON, CSV, Excel
- [ ] Data persists in PostgreSQL
- [ ] Auth required for access

### Phase 1.5 Complete When

- [ ] Can view all projects in portfolio dashboard
- [ ] Can see team workload across projects
- [ ] Can identify over-allocated resources
- [ ] Can run cross-project reports

---

## Related Documents

- [FLAN Gap Analysis](../../interviews/flan-documentation.md) - Prototype vs requirements
- [Main ROADMAP](../../ROADMAP.md) - Overall BizNiceSweets phases
- [Architecture](architecture.md) - Data models and APIs
- [INVARIANTS](INVARIANTS.md) - Rules for implementation