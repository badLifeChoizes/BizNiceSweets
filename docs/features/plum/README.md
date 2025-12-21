# PLUM - Product Lifecycle Management

> Manage product data from concept through end-of-life: parts, BOMs, pricing, and margins.

## Quick Links

| Document | Purpose |
|----------|---------|
| [Usage & Examples](usage.md) | User workflows, UI descriptions, example scenarios |
| [Architecture](architecture.md) | Data models, state machines, events, APIs |
| [Dependencies](dependencies.md) | What to read when touching this feature |
| [INVARIANTS](INVARIANTS.md) | Rules that must NEVER be violated |
| [ROADMAP](ROADMAP.md) | PLUM-specific development phases |

## Overview

PLUM is the Product Lifecycle Management module for BizNiceSweets. It provides:

- **Part Management** - Create, revise, and track components
- **Bill of Materials** - Multi-level product structures with cost roll-up
- **Where-Used Analysis** - Impact analysis for part changes
- **Approved Vendor List** - Link parts to approved suppliers
- **Pricing & Margins** - Product economics and profitability analysis

## Status

| Metric | Value |
|--------|-------|
| Phase | 1.0 (Core Migration) |
| Prototype | v54 (feature-complete) |
| Production | Not started |
| Last Updated | 2025-12-21 |

## Key Concepts

- **Part**: A component with a part number, revision, and status (Draft/Released/Obsolete)
- **BOM**: Bill of Materials - hierarchical structure showing what parts make up a product
- **Where-Used**: Reverse BOM lookup - find all products that use a specific part
- **AVL**: Approved Vendor List - which vendors are approved to supply which parts
- **Cost Roll-up**: Calculate total product cost from all BOM levels (materials + labor)

## Feature Summary

### Core (Phase 1.0)

| Feature | Description | Prototype |
|---------|-------------|-----------|
| Part CRUD | Create, read, update, delete parts | Implemented |
| Part Numbers | Auto-generation with prefixes | Implemented |
| Part Revisions | Version history with status workflow | Implemented |
| Part Status | Draft → Released → Obsolete workflow | Implemented |
| BOM Tree View | Expandable/collapsible hierarchy | Implemented |
| BOM Flat View | Consolidated parts list with quantities | Implemented |
| Cost Roll-up | Material + labor costs at all levels | Implemented |
| Where-Used | Reverse BOM lookup with impact analysis | Implemented |
| AVL Management | Part-to-vendor mapping with status | Implemented |
| Substitutes | Alternate part tracking and suggestions | Implemented |
| Product Pricing | Sale price, distributor discounts | Implemented |
| Margin Analysis | Dashboards and comparison charts | Implemented |
| Import/Export | JSON backup, Excel import | Implemented |

### Planned (Phase 1.5+)

| Feature | Phase | Description |
|---------|-------|-------------|
| Document Links | 1.5 | URL/path references to specs, CAD files |
| Document Management | 2.0 | Upload, versioning, preview |
| ECO Workflow | 2.5 | Engineering Change Orders with approvals |

## Integration Points

| Module | Direction | Data |
|--------|-----------|------|
| SYERP | PLUM → SYERP | Product costs, vendor references |
| SYERP | SYERP → PLUM | Vendor master data, inventory levels |
| MOUSSE | PLUM → MOUSSE | BOMs, part specs for manufacturing |
| FLAN | PLUM ↔ FLAN | Product development project links |

## Prototype Reference

The prototype at `plum/app/plm_v54.html` demonstrates all Phase 1.0 features. Key files:

| File | Purpose |
|------|---------|
| `plum/app/plm_v54.html` | Current prototype application |
| `plum/data/plm_database.json` | Sample database |
| `plum/templates/*.xlsx` | Import templates |
| `plum/docs/PLM_FEATURE_ROADMAP.md` | Prototype feature history |

## Getting Started

*Production application not yet available. See prototype for feature preview.*

1. Open `plum/app/plm_v54.html` in a browser
2. Create parts using the + button or Ctrl+N
3. Build BOMs by adding child parts to assemblies
4. Set pricing and view margins in the Margins tab