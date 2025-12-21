# Analysis Report: Existing Applications Review

**Date:** December 20, 2025
**Branch:** `chore-analysis-report`
**Analyst:** Claude (AI-assisted analysis)

---

## Executive Summary

This report provides a comprehensive analysis of the two existing applications in the BizNiceSweets suite:

| Application | Suite | Version | Size | Status |
|-------------|-------|---------|------|--------|
| **PLUM** | PLM (Product Lifecycle Management) | v54 | ~1.3MB | Active |
| **FLAN** | PRJ-MGMT (Project Management) | v24 | ~1.6MB | Active |

### Key Findings

1. **Both applications are mature, feature-rich single-file HTML applications** using LocalStorage for persistence
2. **Significant feature overlap exists** in financial/vendor management areas
3. **Several features are misplaced** relative to the planned suite structure
4. **Manufacturing features planned for PLUM** should be in MOUSSE
5. **Financial features in FLAN** should be in SYERP
6. **No integration exists** between the two applications despite natural connection points

---

## Part 1: PLUM (PLM v54) Analysis

### Overview

PLUM is a Product Lifecycle Management system designed to manage product data from concept through end-of-life. It's implemented as a single-file HTML application with embedded JavaScript (~1.3MB).

### Current Features

#### Core Part Management
| Feature | Status | Notes |
|---------|--------|-------|
| Part creation/editing | Implemented | Full CRUD operations |
| Part numbers (PN) | Implemented | Auto-generation supported |
| Part revisions | Implemented | Revision history tracking |
| Part status (Draft/Released/Obsolete) | Implemented | Status workflow |
| Part classes/types | Implemented | Classification system |
| Part descriptions | Implemented | Rich text support |
| Custom fields | Not Implemented | Deferred per roadmap |

#### Bill of Materials (BOM)
| Feature | Status | Notes |
|---------|--------|-------|
| Multi-level BOM tree view | Implemented | Expandable/collapsible |
| Flat BOM view | Implemented | Consolidated parts list |
| BOM quantity tracking | Implemented | Per-level quantities |
| BOM cost roll-up | Implemented | Material + labor costs |
| BOM configurations | Implemented | Multiple configs per product |
| BOM effectivity dates | Implemented | Date-based validity |
| BOM health score | Implemented | Quality indicators |
| RefDes validation | Implemented | Reference designator tracking |

#### Where-Used Analysis
| Feature | Status | Notes |
|---------|--------|-------|
| Where-used tree | Implemented | Reverse BOM lookup |
| Impact analysis | Implemented | Change impact visibility |

#### Approved Vendor List (AVL)
| Feature | Status | Notes |
|---------|--------|-------|
| AVL management | Implemented | Vendor-to-part mapping |
| AVL status (Approved/Preferred/Conditional) | Implemented | Multi-status support |
| AVL view | Implemented | Dedicated view |

#### Substitutes & Alternates
| Feature | Status | Notes |
|---------|--------|-------|
| Substitute parts | Implemented | Alternate part tracking |
| Substitute suggestions | Implemented | AI-suggested substitutes |
| Substitute view | Implemented | Management interface |

#### Pricing & Margin Analysis (Phase 19 - Complete)
| Feature | Status | Notes |
|---------|--------|-------|
| Product sale price | Implemented | User-set pricing |
| Distributor discount | Implemented | Percentage-based |
| Package pricing | Implemented | Independent of products |
| Assembly labor cost roll-up | Implemented | All BOM levels |
| Margin dashboards | Implemented | Profitability metrics |
| Margin comparison charts | Implemented | Visual comparisons |
| Cost simulator | Implemented | What-if analysis |

#### Data Management
| Feature | Status | Notes |
|---------|--------|-------|
| JSON export/import | Implemented | Full database backup |
| Excel import | Implemented | Bulk data loading |
| Data integrity checks | Implemented | Validation tools |
| Part comparison tool | Implemented | Diff between parts |
| Database checkout/checkin | Implemented | Collaborative editing |
| Duplicate detection | Implemented | Merge workflow |

#### UI/UX Features
| Feature | Status | Notes |
|---------|--------|-------|
| Command palette (Ctrl+K) | Implemented | Quick navigation |
| Advanced search with syntax | Implemented | Filter expressions |
| Column sorting/filtering | Implemented | Per-column controls |
| Quick preview panel | Implemented | Slide-out details |
| Compact mode toggle | Implemented | Density control |
| Dark theme | Implemented | Single theme |
| Toast notifications | Implemented | Status feedback |

### Planned Features (From Roadmap)

#### Phase 20: Manufacturing Operations (NOT IMPLEMENTED)

**Critical Issue:** These features are planned for PLUM but belong in MOUSSE (MES):

| Feature | Planned For | Should Be In |
|---------|-------------|--------------|
| Facility management | PLUM | MOUSSE |
| Work center registry | PLUM | MOUSSE |
| Work center costing | PLUM | MOUSSE |
| Production routings | PLUM | MOUSSE |
| Calculated labor cost from routing | PLUM | MOUSSE |
| Manufacturing lead time | PLUM | MOUSSE |
| Routing version control | PLUM | MOUSSE |

**Recommendation:** Do NOT implement Phase 20 in PLUM. Create these features in MOUSSE with integration to PLUM for part/BOM data.

### PLUM Feature Gaps

| Gap | Priority | Notes |
|-----|----------|-------|
| Document management (CAD, PDFs, specs) | High | Critical for PLM |
| Engineering Change Order (ECO) workflow | High | Formal change control |
| Compliance/regulatory tracking | Medium | Industry requirements |
| Product portfolio view | Medium | Multi-product overview |
| Lifecycle state machine configuration | Medium | Customizable workflows |
| Multi-unit support | Low | Different UoM per part |
| Localization/multi-language | Low | International use |

---

## Part 2: FLAN (PRJ-MGMT v24) Analysis

### Overview

FLAN is a Project Management tool for planning, tracking, and coordinating projects. It's implemented as a single-file HTML application (~1.6MB).

### Current Features

#### Project Management
| Feature | Status | Notes |
|---------|--------|-------|
| Multiple projects | Implemented | Project list with search |
| Project isolation (separate storage) | Implemented | Per-project keys |
| Project categories | Implemented | Grouping support |
| Pinned/Recent projects | Implemented | Quick access |
| Project duplication | Implemented | Clone projects |
| Auto-load last project | Implemented | Session persistence |
| Project deletion with confirmation | Implemented | Safe deletion |
| Shareable project links | Implemented | URL-encoded sharing |

#### Phase/Epic Management
| Feature | Status | Notes |
|---------|--------|-------|
| Phase CRUD | Implemented | Full operations |
| Progress slider (0-100%) | Implemented | Visual progress |
| Status tracking | Implemented | Pending/Progress/Complete |
| Phase scheduling (start/due dates) | Implemented | Date ranges |
| Actual vs planned dates | Implemented | Variance tracking |
| Phase dependencies | Implemented | Predecessor/successor |
| Phase priority (High/Medium/Low) | Implemented | Click-to-cycle |
| Tags/Labels | Implemented | Colored categorization |
| Hide/unhide phases | Implemented | Visibility toggle |
| Archive phases | Implemented | Soft delete |
| Drag & drop reorder | Implemented | Native HTML5 |
| Bulk actions | Implemented | Multi-select operations |
| Double-click to edit | Implemented | Quick access |

#### Subtasks
| Feature | Status | Notes |
|---------|--------|-------|
| Subtasks within phases | Implemented | Checklist items |
| Subtask scheduling | Implemented | Start/due/completed dates |
| Subtask completion tracking | Implemented | Checkbox toggle |
| Overdue indicators | Implemented | Visual warnings |
| JIRA key display | Implemented | External reference |

#### Deliverables
| Feature | Status | Notes |
|---------|--------|-------|
| Deliverable management | Implemented | CRUD operations |
| Date-based tracking | Implemented | Due dates |
| Countdown timers | Implemented | Days remaining |
| Urgency indicators | Implemented | Color-coded |
| Link to phases | Implemented | Association |
| Status (Open/Pending/Delivered) | Implemented | Workflow |
| Assignees | Implemented | Team member assignment |
| Comments | Implemented | Discussion threads |

#### Team Management
| Feature | Status | Notes |
|---------|--------|-------|
| Team member registry | Implemented | Name/role/rate |
| Avatar colors | Implemented | Visual identification |
| Assignees on phases/deliveries | Implemented | Assignment system |
| @mentions in comments | Implemented | Autocomplete |
| Team workload view | Implemented | Allocation analysis |

#### Time Tracking
| Feature | Status | Notes |
|---------|--------|-------|
| Time entries per phase | Implemented | Hours logging |
| Team member rates | Implemented | Cost calculation |
| Labor cost roll-up | Implemented | Financial tracking |
| Time summary | Implemented | Reporting |

#### Resource Tracking
| Feature | Status | Notes |
|---------|--------|-------|
| Materials/equipment | Implemented | Resource registry |
| Quantity and cost | Implemented | Per-resource tracking |
| Status (Needed/Ordered/Received) | Implemented | Workflow |

#### Budget Management (Phase 18 - Extensive)

**Note:** Many of these features overlap with ERP functionality.

| Feature | Status | Belongs In |
|---------|--------|------------|
| Budget overview with CAPEX | Implemented | SYERP |
| Fiscal year tracking | Implemented | SYERP |
| Approval status workflow | Implemented | SYERP |
| Expense ledger with CRUD | Implemented | SYERP |
| Expense categories (7 types) | Implemented | SYERP |
| Budget alerts at thresholds | Implemented | SYERP |
| Burn rate calculation | Implemented | SYERP |
| Forecast at completion | Implemented | SYERP |
| CAPEX document attachments | Implemented | SYERP |
| Receipt/invoice attachments | Implemented | SYERP |
| Purchase orders with workflow | Implemented | SYERP |
| Vendor management registry | Implemented | SYERP |
| Expense import from Excel | Implemented | SYERP |
| Auto-map expenses to phases | Implemented | Keep in FLAN (project context) |
| Generate invoices | Implemented | SYERP |
| Budget export reports | Partial | SYERP |

#### Visualizations
| Feature | Status | Notes |
|---------|--------|-------|
| Timeline view | Implemented | Horizontal timeline |
| Calendar view | Implemented | Monthly calendar |
| Gantt chart (date-aware) | Implemented | Phase scheduling |
| Progress charts (pie/bar) | Implemented | Status breakdown |
| Burndown summary | Implemented | Work remaining |
| Critical path display | Implemented | Calculation only |

#### Risk & Governance
| Feature | Status | Notes |
|---------|--------|-------|
| Risk register | Implemented | Likelihood/impact matrix |
| Risk scoring | Implemented | Automated calculation |
| Mitigation tracking | Implemented | Action items |
| Milestones | Implemented | Key decision points |
| Decision log | Implemented | Rationale capture |
| Recurring templates | Implemented | Repeating work |

#### Analytics
| Feature | Status | Notes |
|---------|--------|-------|
| Project health score | Implemented | Composite metric |
| Team workload | Implemented | Allocation view |
| Estimate vs actual | Implemented | Variance analysis |
| Velocity tracking | Implemented | Completion rate |

#### Import/Export
| Feature | Status | Notes |
|---------|--------|-------|
| JSON backup/restore | Implemented | Full project |
| CSV export | Implemented | Phases/deliveries |
| Excel export (.xlsx) | Implemented | Formatted |
| PDF reports | Implemented | Summary reports |
| HTML export (standalone) | Implemented | Embedded CSS |
| ICS calendar export | Implemented | Deliveries |
| JIRA CSV import | Implemented | Epic/Task hierarchy |

#### Collaboration
| Feature | Status | Notes |
|---------|--------|-------|
| Comments on phases | Implemented | Threaded |
| Comments on deliveries | Implemented | Threaded |
| @mentions | Implemented | Team autocomplete |
| Activity log | Implemented | Change history |
| Shareable links | Implemented | URL-encoded |

#### Notes System
| Feature | Status | Notes |
|---------|--------|-------|
| Three-category notes | Implemented | Focus/Milestones/Future |
| Markdown support | Implemented | Preview rendering |

#### UI/UX Features
| Feature | Status | Notes |
|---------|--------|-------|
| Tab navigation | Implemented | Main sections |
| Light/dark themes | Implemented | Toggle |
| View density | Implemented | Compact/comfortable |
| Collapsible sections | Implemented | Dashboard/budget |
| Presentation mode | Implemented | Full-screen read-only |
| Keyboard shortcuts | Implemented | Quick actions |
| Tooltips | Implemented | Hints |
| Toast notifications | Implemented | Status feedback |
| Undo/redo | Implemented | History stack |

### FLAN Feature Gaps

| Gap | Priority | Notes |
|-----|----------|-------|
| Resource allocation/leveling | High | Optimize workload |
| Project portfolio management | High | Multi-project view |
| Earned value management (EVM) | Medium | Advanced tracking |
| Custom fields | Medium | User-defined data |
| Baseline snapshots comparison | Medium | Variance visualization |
| Mobile/responsive improvements | Medium | Touch optimization |
| Offline mode (service worker) | Low | Deferred |

---

## Part 3: Feature Overlap Analysis

### Areas of Significant Overlap

#### 1. Vendor Management

| PLUM | FLAN |
|------|------|
| AVL (Approved Vendor List) | Vendor registry |
| Vendor-to-part mapping | Vendor contact info |
| Vendor status tracking | Per-vendor spend tracking |

**Recommendation:** Consolidate vendor management in SYERP. PLUM references vendors for AVL purposes. FLAN references vendors for expense tracking.

#### 2. Financial/Cost Management

| PLUM | FLAN |
|------|------|
| Product pricing | Project budget |
| Cost roll-up | Expense ledger |
| Margin analysis | Budget vs actual |
| Distributor discounts | Purchase orders |

**Recommendation:**
- PLUM keeps product cost/pricing (part of product definition)
- FLAN keeps project budget linking (project context)
- Detailed expense tracking, POs, invoicing moves to SYERP

#### 3. Document Attachments

| PLUM | FLAN |
|------|------|
| (Not implemented) | CAPEX documents |
| (Not implemented) | Receipts/invoices |

**Recommendation:** Implement document management infrastructure that can be shared across suites.

---

## Part 4: Misplaced Features

### Features in Wrong Suite

| Feature | Currently In | Should Be In | Rationale |
|---------|--------------|--------------|-----------|
| Manufacturing facilities | PLUM (planned) | MOUSSE | MES manages production facilities |
| Work centers | PLUM (planned) | MOUSSE | MES manages shop floor resources |
| Production routings | PLUM (planned) | MOUSSE | MES executes routings |
| Work instructions | PLUM (planned) | MOUSSE | Shop floor execution |
| Tooling management | PLUM (planned) | MOUSSE | Production tooling |
| Quality checkpoints | PLUM (planned) | CRISP | QMS manages inspections |
| Expense ledger | FLAN | SYERP | ERP handles financials |
| Purchase orders | FLAN | SYERP | ERP handles procurement |
| Vendor registry | FLAN | SYERP | ERP handles vendors |
| Invoice generation | FLAN | SYERP | ERP handles invoicing |
| Multi-currency | FLAN (planned) | SYERP | ERP handles currencies |

### Features Correctly Placed

| Feature | Suite | Rationale |
|---------|-------|-----------|
| Part/BOM management | PLUM | Core PLM function |
| Product pricing | PLUM | Product definition |
| Margin analysis | PLUM | Product economics |
| Project phases/tasks | FLAN | Core PM function |
| Team management | FLAN | Project resources |
| Time tracking | FLAN | Project labor |
| Gantt/timeline | FLAN | Project visualization |
| Risk/milestones | FLAN | Project governance |

---

## Part 5: Recommendations

### Immediate Actions

#### 1. Do NOT Implement Phase 20 in PLUM
The Manufacturing Operations features (facilities, work centers, routings) belong in MOUSSE. Implementing them in PLUM would:
- Create massive feature duplication when MOUSSE is built
- Blur the distinction between product definition (PLM) and manufacturing execution (MES)
- Make future integration more complex

**Action:** Mark Phase 20 as "Relocated to MOUSSE" in the PLUM roadmap.

#### 2. Plan SYERP to Receive Financial Features
When SYERP is built, migrate the following from FLAN:
- Expense ledger
- Purchase orders
- Vendor registry
- Invoice generation

**Action:** Create SYERP requirements based on FLAN's existing implementation.

#### 3. Define Integration Points
Create formal integration specifications for:

| Source | Target | Data Flow |
|--------|--------|-----------|
| PLUM | FLAN | Product development projects reference PLUM products |
| PLUM | MOUSSE | BOMs and part specs flow to manufacturing |
| PLUM | SYERP | Product costs flow to ERP for financial planning |
| FLAN | MOUSSE | Manufacturing projects coordinate with production |
| FLAN | CRISP | Quality milestones and deliverables |

### Medium-Term Actions

#### 4. Add Document Management to PLUM
High-priority gap. PLM systems require:
- CAD file references
- Specification documents
- Compliance certificates
- Engineering drawings

#### 5. Add ECO Workflow to PLUM
Engineering Change Orders are fundamental to PLM:
- Change request creation
- Impact analysis
- Approval workflow
- Implementation tracking

#### 6. Streamline FLAN Budget Features
Keep project budget linking but simplify:
- Remove vendor registry (move to SYERP)
- Remove purchase orders (move to SYERP)
- Keep expense-to-phase mapping (project context)
- Keep budget overview (project visibility)

### Long-Term Architecture

```
                    ┌─────────────┐
                    │   CRUMB     │
                    │    (CRM)    │
                    └──────┬──────┘
                           │ Customer orders
                           ▼
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│    PLUM     │────▶│   SYERP     │◀────│   FLAN      │
│    (PLM)    │     │    (ERP)    │     │   (PM)      │
└──────┬──────┘     └──────┬──────┘     └─────────────┘
       │ BOM/specs         │ Inventory
       ▼                   ▼
┌─────────────┐     ┌─────────────┐
│   MOUSSE    │◀───▶│   GELATO    │
│    (MES)    │     │    (WMS)    │
└──────┬──────┘     └─────────────┘
       │ Quality data
       ▼
┌─────────────┐
│   CRISP     │
│    (QMS)    │
└─────────────┘
```

### Shared Infrastructure Needs

| Component | Purpose | Priority |
|-----------|---------|----------|
| User authentication | Cross-suite login | High |
| Shared vendor master | Single source of truth | High |
| Document storage | Attachments across suites | High |
| Notification system | Cross-suite alerts | Medium |
| Reporting engine | Unified analytics | Medium |
| API layer | Inter-suite communication | Medium |

---

## Part 6: Technical Observations

### Architecture

Both applications share similar architecture:
- Single-file HTML with embedded CSS and JavaScript
- LocalStorage for persistence
- No external dependencies (except xlsx.js, jspdf.js)
- Dark theme by default
- ~1.3-1.6MB file size

### Code Quality

**Strengths:**
- Comprehensive feature sets
- Consistent UI patterns
- Good use of CSS custom properties
- Modular JavaScript functions
- Clear naming conventions

**Areas for Improvement:**
- No TypeScript (type safety)
- No unit tests
- No build process (bundling, minification)
- Inline everything (harder to maintain)
- No API abstraction layer

### Data Storage

**PLUM:**
- Primary key: `plm_database` (or custom)
- Multi-database support with checkout/checkin
- JSON structure for parts, products, packages

**FLAN:**
- Primary key: `prj_mgmt_project_{id}` (isolated per project)
- Project list at `prj_mgmt_project_list`
- JSON structure for phases, deliveries, team, budget

### Size Comparison

| Metric | PLUM (v54) | FLAN (v24) |
|--------|------------|------------|
| File size | ~1.3MB | ~1.6MB |
| CSS lines | ~1500 | ~1200 |
| JS functions | ~150 | ~180 |
| Views/tabs | ~10 | ~12 |

---

## Appendix A: Feature Matrix by Suite

| Feature Category | PLUM | FLAN | CRUMB | SYERP | MOUSSE | CRISP | GELATO |
|-----------------|------|------|-------|-------|--------|-------|--------|
| Part management | ✅ | - | - | - | - | - | - |
| BOM management | ✅ | - | - | - | Read | - | - |
| Product pricing | ✅ | - | - | Read | - | - | - |
| Project management | - | ✅ | - | - | - | - | - |
| Task tracking | - | ✅ | - | - | - | - | - |
| Team management | - | ✅ | - | - | ✅ | - | - |
| Customer management | - | - | ✅ | - | - | - | - |
| Sales pipeline | - | - | ✅ | - | - | - | - |
| General ledger | - | - | - | ✅ | - | - | - |
| Accounts payable | - | - | - | ✅ | - | - | - |
| Accounts receivable | - | - | - | ✅ | - | - | - |
| Inventory | - | - | - | ✅ | - | - | ✅ |
| Purchase orders | ❌ Move | ❌ Move | - | ✅ | - | - | - |
| Vendor management | ❌ Move | ❌ Move | - | ✅ | - | - | - |
| Work orders | - | - | - | - | ✅ | - | - |
| Production scheduling | - | - | - | - | ✅ | - | - |
| Shop floor control | - | - | - | - | ✅ | - | - |
| Routings | ❌ Cancel | - | - | - | ✅ | - | - |
| Work centers | ❌ Cancel | - | - | - | ✅ | - | - |
| Inspections | - | - | - | - | - | ✅ | - |
| Non-conformance | - | - | - | - | - | ✅ | - |
| CAPA | - | - | - | - | - | ✅ | - |
| Location management | - | - | - | - | - | - | ✅ |
| Pick/pack/ship | - | - | - | - | - | - | ✅ |
| Lot/serial tracking | - | - | - | ✅ | ✅ | ✅ | ✅ |

Legend: ✅ = Should have | ❌ Move = Move elsewhere | ❌ Cancel = Don't implement here | Read = Read-only integration

---

## Appendix B: Roadmap Corrections

### PLUM Roadmap Changes

| Phase | Status | Recommendation |
|-------|--------|----------------|
| Phase 19 (Pricing/Margins) | Complete | Keep - correct placement |
| Phase 20 (Manufacturing) | Planned | **Cancel** - Move to MOUSSE |

### FLAN Roadmap Changes

| Phase | Status | Recommendation |
|-------|--------|----------------|
| Phase 18 (Budget) | Partial | **Split** - Keep budget linking, move detailed financials to SYERP |
| Phase 18.8 (Approval workflow) | Next | Keep for project context |
| Phase 18.12 (Budget export) | Planned | Keep - project reporting |
| Phase 18.13 (Multi-currency) | Planned | **Move to SYERP** |

---

## Conclusion

Both PLUM and FLAN are mature, feature-rich applications that demonstrate solid engineering. However, as the BizNiceSweets suite expands to include ERP (SYERP) and MES (MOUSSE), careful attention must be paid to:

1. **Preventing feature duplication** by not implementing manufacturing in PLUM
2. **Planning for feature migration** from FLAN to SYERP for financial features
3. **Defining integration contracts** between suites early
4. **Building shared infrastructure** for common needs (auth, documents, vendors)

The recommended approach is evolutionary: keep the existing applications working while gradually extracting features to their proper homes as new suites are developed.

---

*Report generated as part of task `chore-analysis-report`*