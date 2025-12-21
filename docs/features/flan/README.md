# FLAN - Project Management

> Manage projects from kickoff through delivery: phases, tasks, team coordination, time tracking, and project budgets.

## Quick Links

| Document | Purpose |
|----------|---------|
| [Usage & Examples](usage.md) | User workflows, UI descriptions, example scenarios |
| [Architecture](architecture.md) | Data models, state machines, events, APIs |
| [Dependencies](dependencies.md) | What to read when touching this feature |
| [INVARIANTS](INVARIANTS.md) | Rules that must NEVER be violated |
| [ROADMAP](ROADMAP.md) | FLAN-specific development phases |

## Overview

FLAN is the Project Management module for BizNiceSweets. It provides:

- **Project Management** - Create, organize, and track projects with categories
- **Phase/Epic Tracking** - Break projects into phases with progress tracking
- **Subtask Management** - Checklists within phases for detailed work items
- **Team Coordination** - Assign team members, track workload
- **Time Tracking** - Log hours against phases, calculate labor costs
- **Deliverables** - Track key deliveries with countdown timers
- **Project Budgets** - Budget planning, expense tracking, variance analysis
- **Visualizations** - Timeline, Gantt chart, calendar views

## Status

| Metric | Value |
|--------|-------|
| Phase | 1.0 (Core Migration) |
| Prototype | v24 (feature-rich, 130+ features) |
| Production | Not started |
| Last Updated | 2025-12-21 |

## Key Concepts

- **Project**: A container for all work items with phases, deliveries, team, and budget
- **Phase**: Major work chunk with progress (0-100%), status, dates, and subtasks
- **Subtask**: Checklist item within a phase, can have JIRA key and due dates
- **Delivery**: Key deliverable with date, destination, and urgency tracking
- **Team Member**: Person who can be assigned to phases and log time
- **Time Entry**: Hours logged by a team member against a specific phase
- **Project Budget**: Overall budget with CAPEX approval, expense categories, and variance tracking

## Feature Summary

### Core (Phase 1.0)

| Feature | Description | Prototype |
|---------|-------------|-----------|
| Project CRUD | Create, read, update, delete projects | Implemented |
| Project Categories | Organize projects by category | Implemented |
| Project Isolation | Separate localStorage per project | Implemented |
| Phase CRUD | Create, manage, delete phases | Implemented |
| Phase Progress | 0-100% slider with visual feedback | Implemented |
| Phase Status | Pending/In Progress/Complete workflow | Implemented |
| Subtasks | Checklist items within phases | Implemented |
| Deliverables | Key delivery tracking with dates | Implemented |
| Team Members | Add team members with roles and rates | Implemented |
| Assignees | Assign team members to phases | Implemented |
| Time Entries | Log hours per phase per team member | Implemented |
| Timeline View | Gantt-style date visualization | Implemented |
| Project Dashboard | KPIs, progress charts, alerts | Implemented |
| Notes & Comments | Markdown notes, phase comments | Implemented |
| Import/Export | JSON backup, CSV/Excel export | Implemented |

### Planned (Phase 1.5+)

| Feature | Phase | Description |
|---------|-------|-------------|
| Portfolio View | 1.5 | Cross-project overview and comparison |
| Resource Leveling | 1.5 | Workload balancing across projects |
| EVM Metrics | Deferred | Earned Value Management (SPI, CPI) |
| Custom Fields | Deferred | User-defined fields on phases |

### Features NOT in FLAN

These features exist in the prototype but belong in SYERP:

| Feature | Owner | Integration |
|---------|-------|-------------|
| Vendor Management | SYERP | FLAN reads vendor data via API |
| Expense Ledger | SYERP | FLAN maps expenses to phases |
| Purchase Orders | SYERP | FLAN can reference POs |

These features stay in FLAN:

| Feature | Notes |
|---------|-------|
| Project Budgets | FLAN manages project-level budgets |
| Project Work Invoices | FLAN generates invoices for project work |
| Phase Budget Estimates | FLAN tracks estimated vs actual per phase |

## Integration Points

| Module | Direction | Data |
|--------|-----------|------|
| SYERP | FLAN → SYERP | Project costs, time-based invoices |
| SYERP | SYERP → FLAN | Vendor data, expense ledger |
| PLUM | FLAN ↔ PLUM | Product development project links |
| Core | Core → FLAN | User data for team assignments |

## Prototype Reference

The prototype at `flan/app/prj-mgmt-v24.html` demonstrates 130+ features. Key files:

| File | Purpose |
|------|---------|
| `flan/app/prj-mgmt-v24.html` | Current prototype application |
| `flan/archive/` | Version history of the prototype |
| `flan/data/Crisis.json` | Sample project data |
| `flan/docs/PRJ-MGMT-Roadmap.md` | Prototype feature history |

## Getting Started

*Production application not yet available. See prototype for feature preview.*

1. Open `flan/app/prj-mgmt-v24.html` in a browser
2. Create a new project or select an existing one
3. Add phases with the "Add Phase" button
4. Track progress with sliders and status dropdowns
5. Add team members and log time entries
6. View dashboards for project health metrics