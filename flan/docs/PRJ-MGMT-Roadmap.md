# PRJ-MGMT Tool -- Product Roadmap

**Document Version:** 3.3  
**Created:** December 19, 2025  
**Last Updated:** December 20, 2025  
**Status:** Active - v23 Released

---

## Executive Summary

This roadmap outlines planned features, capabilities, and improvements for the PRJ-MGMT Tool -- a browser-based project management application. Features are organized into phases based on priority, complexity, and user value.

**Version 2.0 Note:** This revision corrects feature statuses based on a comprehensive code audit of v14. Several features previously marked [DONE] were not actually implemented and have been rescheduled for implementation in new phases. Previous versions (v1-v13) are archived and available for reference when reimplementing lost features.

---

## Current State (v23.0)

### Verified Capabilities

| Category | Features |
|----------|----------|
| **Projects** | Create, save, load, delete projects; LocalStorage persistence; Categories; Search, Pin, Recent projects; **Isolated storage per project; Remember last project; Delete current project** |
| **Phases (Epics)** | Add/edit/delete phases; progress slider (0-100%); status tracking; assignees; context menus; start/due dates; schedule modal; duration calculation; overdue alerts; **Hide/unhide phases; Double-click to edit** |
| **Tasks** | Subtasks within phases; start/due dates; completion dates; overdue indicators; edit modal |
| **Deliveries** | Date-based deliverables; countdown timers; urgency indicators; assignees; context menus; **Link to phases; Double-click to edit** |
| **Notes** | Three-category system (Focus, Milestones, Future Plans); Markdown preview support |
| **Budget** | Estimated vs actual costs; currency settings; tax rates; **CAPEX budget overview; fiscal year tracking; approval status; budget utilization progress bar; burn rate calculation; forecast at completion; expense categories (7 types); expense ledger with CRUD; budget alerts at configurable thresholds; CAPEX document attachments; receipt/invoice attachments on expenses; purchase orders with status workflow; vendor management registry; expense import from Excel/CSV; collapsible budget sections; double-click expense editing; auto-map expenses to phases by date** |
| **Time Tracking** | Log hours per phase; team member rates; labor cost calculation |
| **Resources** | Track materials/equipment; quantity and cost; status (needed/ordered/received) |
| **Team** | Team members with roles, rates, and avatar colors |
| **Import/Export** | JSON, CSV, Budget reports, PDF reports, HTML reports, ICS Calendar, Excel (.xlsx); JIRA hierarchical CSV import (Epic/Task mapping); **Expense import from spreadsheets** |
| **Snapshots** | Point-in-time project snapshots for comparison |
| **Invoice** | Generate invoices from tracked time and costs |
| **Presentation** | Full-screen mode; read-only view for meetings |
| **Print** | Optimized print stylesheet for project reports |
| **UI** | Tab navigation; KPI dashboard; keyboard shortcuts; light/dark themes; view density toggle; collapsible Dashboard sections; collapsible Budget sections; **Dashboard default collapsed for new users; Save button clarity** |
| **Risk Register** | Likelihood/impact matrix; risk scoring; mitigation tracking |
| **Milestones** | Key decision points with timeline view; status tracking |
| **Decisions** | Decision log with rationale; searchable; filterable by phase |
| **Recurring** | Templates for repeating work; create phases from templates |
| **Critical Path** | Auto-identify phases affecting project end date (calculation only) |
| **Analytics** | Project health score; team workload view; estimate vs actual; velocity tracking |
| **Visualizations** | Timeline view, Calendar view, Gantt chart (date-aware), Progress charts (pie/bar), Burndown summary |
| **Schedule Management** | Phase/Task scheduling; planned vs actual variance; overdue KPI; schedule-aware Gantt |
| **Organization** | Drag & drop reorder; Priority levels (High/Medium/Low); Tags/Labels; Bulk actions; Archive with toggle |
| **Dependencies** | Dependency UI modal; visual dependency indicators on phases |
| **Collaboration** | Comments on phases/deliveries; @mentions with team member autocomplete; Shareable project links (URL-encoded) |
| **Project Architecture** | **Isolated storage (one key per project); Auto-load last project; Migration from legacy storage** |

### Known Issues & Polish Items (Future Releases)

| Category | Issue/Enhancement |
|----------|-------------------|
| **Accessibility** | Keyboard navigation could be improved; Screen reader support needs audit |
| **Mobile** | Touch interactions not optimized; Responsive layout needs work |
| **Performance** | Large projects (100+ phases) may slow down |

---

## Roadmap Phases

### Phase 1: Foundation & Quick Wins [DONE]
**Timeline:** 1-2 Weeks  
**Theme:** Polish existing features, improve reliability

| ID | Feature | Description | Effort | Impact | Status |
|----|---------|-------------|--------|--------|--------|
| 1.1 | Auto-save | Save changes automatically with debounce (2s delay) | Low | High | [DONE] |
| 1.2 | Progress auto-status | Setting 100% automatically marks phase "Complete" | Low | Medium | [DONE] |
| 1.3 | Sort deliveries | Chronological ordering option for deliveries | Low | Medium | [DONE] |
| 1.4 | Empty state UI | Friendly graphics/messages when no data exists | Low | Medium | [DONE] |
| 1.5 | Tooltip hints | Hover tooltips explaining keyboard shortcuts | Low | Low | [DONE] |
| 1.6 | Confirmation dialogs | Enhanced delete confirmations with item names | Low | Medium | [DONE] |
| 1.7 | Duplicate project | Clone existing project as new starting point | Low | High | [DONE] |
| 1.8 | Data validation | Prevent invalid dates, empty required fields | Medium | High | [DONE] |

---

### Phase 2: Core Enhancements [COMPLETE]
**Timeline:** 3-4 Weeks  
**Theme:** Essential productivity features
**Status:** All features implemented or reimplemented in later phases

| ID | Feature | Description | Effort | Impact | Status |
|----|---------|-------------|--------|--------|--------|
| 2.1 | Undo/Redo | History stack for reversing changes (Ctrl+Z/Y) | Medium | High | [DONE] |
| 2.2 | Drag & drop reorder | Reorder phases and deliveries by dragging | Medium | High | [REIMPLEMENTED in Phase 15.1] |
| 2.3 | Search & filter | Find items by name, status, or date range | Medium | High | [DONE] |
| 2.4 | Delivery status | Add Shipped/Pending/Delayed states to deliveries | Low | Medium | [DONE] |
| 2.5 | Priority levels | High/Medium/Low priority markers for items | Low | Medium | [REIMPLEMENTED in Phase 15.2] |
| 2.6 | Bulk actions | Multi-select for status changes or deletion | Medium | Medium | [REIMPLEMENTED in Phase 15.4] |
| 2.7 | Archive items | Hide completed items without deleting them | Medium | Medium | [REIMPLEMENTED in Phase 15.5] |
| 2.8 | Theme toggle | Light/dark mode switch | Medium | Medium | [DONE] |

---

### Phase 3: Organization & Structure [COMPLETE]
**Timeline:** 4-6 Weeks  
**Theme:** Better data organization
**Status:** All features implemented or reimplemented (3.4 Custom Fields deferred)

| ID | Feature | Description | Effort | Impact | Status |
|----|---------|-------------|--------|--------|--------|
| 3.1 | Tags/Labels | Categorize items with colored tags | Medium | High | [REIMPLEMENTED in Phase 15.3] |
| 3.2 | Subtasks | Break phases into smaller checklist items | Medium | High | [DONE] |
| 3.3 | Phase dependencies | Link phases (one can't start until another completes) | High | High | [REIMPLEMENTED in Phase 15.6] |
| 3.4 | Custom fields | User-defined fields per phase or delivery | High | Medium | [DEFERRED] |
| 3.5 | Templates | Preset phase structures for common project types | Medium | High | [DONE] |
| 3.6 | Project categories | Group projects into folders/categories | Medium | Medium | [DONE] |
| 3.7 | Due date alerts | Visual/audio warnings for approaching deadlines | Medium | High | [DONE] |

---

### Phase 4: Visualization [COMPLETE]
**Timeline:** 6-8 Weeks  
**Theme:** Visual project tracking  
**Status:** All features reimplemented in Phase 13 (4.6 Dashboard Widgets deferred)

| ID | Feature | Description | Effort | Impact | Status |
|----|---------|-------------|--------|--------|--------|
| 4.1 | Gantt chart | Timeline visualization of phases | High | High | [REIMPLEMENTED in Phase 13.2] |
| 4.2 | Calendar view | Monthly calendar with deliveries | High | High | [REIMPLEMENTED in Phase 13.3] |
| 4.3 | Timeline view | Horizontal milestone timeline | Medium | Medium | [REIMPLEMENTED in Phase 13.4] |
| 4.4 | Progress charts | Pie/bar charts for project status | Medium | Medium | [REIMPLEMENTED in Phase 13.5] |
| 4.5 | Burndown chart | Work remaining over time | Medium | Medium | [REIMPLEMENTED in Phase 13.6] |
| 4.6 | Dashboard widgets | Customizable dashboard cards | High | Medium | [DEFERRED] |

---

### Phase 5: Team Features [DONE]
**Timeline:** 3-4 Weeks  
**Theme:** Collaboration and team management

| ID | Feature | Description | Effort | Impact | Status |
|----|---------|-------------|--------|--------|--------|
| 5.1 | Team members | Add team members with roles | Medium | High | [DONE] |
| 5.2 | Assignees | Assign phases/deliveries to team members | Medium | High | [DONE] |
| 5.3 | Activity log | Track all changes with timestamps | Medium | High | [DONE] |
| 5.4 | Member rates | Hourly rates per team member | Low | Medium | [DONE] |
| 5.5 | Avatar colors | Visual identification for team members | Low | Low | [DONE] |

---

### Phase 6: Budget & Resources [DONE]
**Timeline:** 3-4 Weeks  
**Theme:** Financial tracking

| ID | Feature | Description | Effort | Impact | Status |
|----|---------|-------------|--------|--------|--------|
| 6.1 | Budget tracking | Estimated vs actual costs per phase | Medium | High | [DONE] |
| 6.2 | Currency settings | Support multiple currencies | Low | Medium | [DONE] |
| 6.3 | Tax rates | Include tax in calculations | Low | Low | [DONE] |
| 6.4 | Resource tracking | Materials, equipment, supplies | Medium | Medium | [DONE] |
| 6.5 | Budget reports | Export budget summaries | Medium | High | [DONE] |

---

### Phase 7: Advanced Export [PARTIAL]
**Timeline:** 2-3 Weeks  
**Theme:** Data portability

| ID | Feature | Description | Effort | Impact | Status |
|----|---------|-------------|--------|--------|--------|
| 7.1 | CSV export | Export phases and deliveries to CSV | Low | High | [DONE] |
| 7.2 | CSV import | Import phases and deliveries from CSV | Medium | High | [DONE] |
| 7.3 | JSON backup | Full project backup/restore | Low | High | [DONE] |
| 7.4 | PDF export | Generate PDF reports | High | High | [DONE] |
| 7.5 | Print stylesheet | Optimized print layout | Medium | Medium | [DONE] |
| 7.6 | Markdown export | Export notes as Markdown | Low | Low | [DEFERRED] |
| 7.7 | Image export | Export charts as PNG | Medium | Medium | [DEFERRED] |

---

### Phase 8: Extended Features [PARTIAL]
**Timeline:** 3-4 Weeks  
**Theme:** Power user features

| ID | Feature | Description | Effort | Impact | Status |
|----|---------|-------------|--------|--------|--------|
| 8.1 | ICS calendar export | Export deliveries to calendar apps | Medium | High | [DONE] |
| 8.2 | Excel export | Export with formatting to .xlsx | Medium | High | [DONE] |
| 8.3 | Project snapshots | Point-in-time project states | Medium | High | [DONE] |
| 8.4 | Offline mode | Service worker for offline access | High | Medium | [DEFERRED] |
| 8.5 | Keyboard shortcuts | Full keyboard navigation | Medium | Medium | [DONE] |

---

### Phase 9: Advanced Tracking [DONE]
**Timeline:** 3-4 Weeks  
**Theme:** Comprehensive project oversight

| ID | Feature | Description | Effort | Impact | Status |
|----|---------|-------------|--------|--------|--------|
| 9.1 | Risk register | Track project risks with severity | Medium | High | [DONE] |
| 9.2 | Milestones | Key decision points and checkpoints | Medium | High | [DONE] |
| 9.3 | Time tracking | Log hours per phase | Medium | High | [DONE] |
| 9.4 | Invoice generation | Create invoices from time/costs | High | High | [DONE] |
| 9.5 | Decision log | Track key decisions and rationale | Medium | Medium | [DONE] |
| 9.6 | Recurring tasks | Templates for repeating work | Medium | Medium | [DONE] |

---

### Phase 10: Analytics [DONE]
**Timeline:** 2-3 Weeks  
**Theme:** Project insights

| ID | Feature | Description | Effort | Impact | Status |
|----|---------|-------------|--------|--------|--------|
| 10.1 | Project health score | Overall status indicator | Medium | High | [DONE] |
| 10.2 | Team workload | Show work distribution | Medium | Medium | [DONE] |
| 10.3 | Estimate vs actual | Compare planned to actual | Medium | High | [DONE] |
| 10.4 | Critical path | Identify phases affecting end date | High | High | [DONE] |
| 10.5 | Velocity tracking | Work completed per period | Medium | Medium | [DONE] |

---

### Phase 11: Notes Enhancement [DONE]
**Timeline:** 1-2 Weeks  
**Theme:** Rich note-taking

| ID | Feature | Description | Effort | Impact | Status |
|----|---------|-------------|--------|--------|--------|
| 11.1 | Markdown support | Render Markdown in notes preview | Medium | High | [DONE] |
| 11.2 | Note categories | Focus, Milestones, Future Plans sections | Low | Medium | [DONE] |
| 11.3 | Note timestamps | Show when notes were last edited | Low | Low | [DONE] |

---

### Phase 12: UI/UX Polish [DONE]
**Timeline:** 2-3 Weeks  
**Theme:** User experience refinement

| ID | Feature | Description | Effort | Impact | Status |
|----|---------|-------------|--------|--------|--------|
| 12.1 | Presentation mode | Full-screen read-only mode for meetings | Medium | High | [DONE] |
| 12.2 | View density | Toggle between compact and comfortable | Low | Medium | [DONE] |
| 12.3 | Collapsible sections | Collapse/expand KPI and notes areas | Low | Medium | [DONE] |
| 12.4 | Loading states | Skeleton screens while loading | Low | Low | [DONE] |

---

### Phase 13: Visualization Restoration [DONE]
**Timeline:** 2-3 Weeks  
**Theme:** Restore lost visualization features from v7
**Status:** COMPLETE in v15

| ID | Feature | Description | Effort | Impact | Status |
|----|---------|-------------|--------|--------|--------|
| 13.1 | Visualizations tab | New tab for all chart/graph views | Low | High | [DONE] |
| 13.2 | Gantt chart | Timeline visualization of phases with dependencies | High | High | [DONE] |
| 13.3 | Calendar view | Monthly calendar showing deliveries and milestones | High | High | [DONE] |
| 13.4 | Timeline view | Horizontal timeline of key dates | Medium | Medium | [DONE] |
| 13.5 | Progress charts | Pie and bar charts for status breakdown | Medium | Medium | [DONE] |
| 13.6 | Burndown summary | Simple burndown indicator (not full chart) | Medium | Medium | [DONE] |

---

### Phase 14: Schedule Management [DONE]
**Timeline:** 2-3 Weeks  
**Theme:** Date-aware project tracking
**Status:** COMPLETE in v16

| ID | Feature | Description | Effort | Impact | Status |
|----|---------|-------------|--------|--------|--------|
| 14.1 | Phase scheduling | Start/due dates on phases; actual start/end tracking | Medium | High | [DONE] |
| 14.2 | Task scheduling | Start/due dates on tasks; completion date | Medium | High | [DONE] |
| 14.3 | Schedule variance | Planned vs actual duration tracking | Medium | High | [DONE] |
| 14.4 | Overdue indicators | Visual markers for past-due items | Low | High | [DONE] |
| 14.5 | Schedule modal | Dedicated UI for editing phase dates | Medium | Medium | [DONE] |
| 14.6 | Gantt date integration | Gantt chart uses actual dates (not just sequence) | High | High | [DONE] |

---

### Phase 15: Missing Core Features [DONE]
**Timeline:** 3-4 Weeks  
**Theme:** Implement features that were never completed
**Status:** COMPLETE in v17

| ID | Feature | Description | Effort | Impact | Status |
|----|---------|-------------|--------|--------|--------|
| 15.1 | Drag & drop reorder | Reorder phases via drag handle | Medium | High | [DONE] |
| 15.2 | Priority levels | High/Medium/Low with visual indicators | Low | Medium | [DONE] |
| 15.3 | Tags/Labels | Create and assign colored tags to items | Medium | High | [DONE] |
| 15.4 | Bulk actions | Multi-select with toolbar for batch operations | Medium | Medium | [DONE] |
| 15.5 | Archive items | Archive toggle with "Show Archived" filter | Medium | Medium | [DONE] |
| 15.6 | Dependency UI | Modal to add/remove dependencies between phases | Medium | High | [DONE] |

---

### Phase 16: Collaboration & Integration [DONE]
**Timeline:** 3-4 Weeks  
**Theme:** Team collaboration and external tool integration
**Status:** COMPLETE in v18

| ID | Feature | Description | Effort | Impact | Status |
|----|---------|-------------|--------|--------|--------|
| 16.1 | Comments | Add comments to phases and deliveries | Medium | High | [DONE] |
| 16.2 | @mentions | Tag team members in comments with autocomplete | Medium | Medium | [DONE] |
| 16.3 | JIRA CSV import | Import JIRA exports with Epic/Task hierarchy | Medium | High | [DONE] |
| 16.4 | Shareable links | Generate URL with embedded project data | Medium | High | [DONE] |
| 16.5 | JIRA field mapping | Map JIRA fields to PRJ-MGMT fields on import | Low | Medium | [DONE] |
| 16.6 | HTML report export | Generate standalone HTML report with embedded CSS | Medium | Medium | [DONE] |

---

### Phase 17: UX Polish & Project Architecture [DONE]
**Timeline:** 2-3 Weeks  
**Theme:** User experience improvements and data architecture
**Status:** COMPLETE in v19

| ID | Feature | Description | Effort | Impact | Status |
|----|---------|-------------|--------|--------|--------|
| 17.1 | Remember last project | Auto-load most recently opened project on startup | Low | High | [DONE] |
| 17.2 | Project isolation | Each project stored as separate JSON in localStorage (key: `prj-mgmt-project-{projectId}`); project selector loads specific project | Medium | High | [DONE] |
| 17.3 | Dashboard default collapsed | Dashboard sections (KPIs, Notes, etc.) start collapsed; expand on click | Low | Medium | [DONE] |
| 17.4 | Delete project | Add "Delete Project" option to header with confirmation; remove from project list | Low | High | [DONE] |
| 17.5 | Save button clarity | Renamed to "Save Now" with tooltip explaining auto-save is active | Low | Low | [DONE] |
| 17.6 | Hide/unhide phases | Toggle phase visibility without archiving; "Show Hidden" filter toggle | Medium | Medium | [DONE] |
| 17.7 | Link deliverables to phases | Add `linkedPhaseId` field to deliverables; show link in UI with click-to-navigate | Medium | High | [DONE] |
| 17.8 | Double-click to expand | Double-click on phases opens schedule modal; double-click on deliveries opens context menu | Low | Medium | [DONE] |

**Implementation Notes:**
- 17.1: On init, check `localStorage.getItem('prj_mgmt_last_project')`; if exists, auto-load that project
- 17.2: New storage architecture: each project at `prj_mgmt_project_{id}` key. Project list stored at `prj_mgmt_project_list`. Migration from legacy `prj_mgmt_projects` array happens automatically. Benefits: better isolation, no cross-contamination, easier backup/restore per project
- 17.3: First-time users see dashboard sections collapsed (except KPIs). State tracked via `prj_mgmt_initialized` flag
- 17.4: "Delete" button in header calls `deleteCurrentProject()` with confirmation dialog; clears last project reference
- 17.5: Button now reads "Save Now" with tooltip "Force Save (auto-saves are on)"
- 17.6: `isHidden` boolean on phases (distinct from `isArchived`); hidden phases don't show unless "Show Hidden" checked; context menu has Hide/Unhide option
- 17.7: Schema: `delivery.linkedPhaseId`; UI shows linked phase name as badge with click-to-navigate; dropdown to link/unlink
- 17.8: `ondblclick` handlers on phase-card and delivery-card; phases open schedule modal, deliveries open context menu
- **v19 Implementation Complete:** Dec 20, 2025

---

### Phase 18: Enhanced Budget Management [PARTIAL - Sprint 4 Complete]
**Timeline:** 4-6 Weeks  
**Theme:** Comprehensive financial tracking, CAPEX management, and expense documentation
**Priority:** HIGH - Major feature enhancement
**Status:** Sprint 4 (18.19) complete in v23

#### Overview

This phase transforms the basic budget tracking (Phase 6) into a full-featured financial management system suitable for enterprise projects. It introduces project-level budget allocation, document attachments, expense tracking, and financial analytics.

#### Features

| ID | Feature | Description | Effort | Impact | Status |
|----|---------|-------------|--------|--------|--------|
| **18.1** | **Project Budget Overview** | Top-level budget allocation panel with total CAPEX budget, fiscal year, approval status | Medium | High | [DONE] |
| **18.2** | **CAPEX Document Attachments** | Attach capital expenditure authorization documents (store as base64 or file references) | High | High | [DONE] |
| **18.3** | **Expense Ledger** | Itemized expense table: name, category, amount, date, vendor, reference doc, linked phase | Medium | High | [DONE] |
| **18.4** | **Receipt/Invoice Attachments** | Attach receipts and invoices to individual expenses (image/PDF support) | High | High | [DONE] |
| **18.5** | **Budget vs Actual Dashboard** | Visual KPI showing spent vs allocated; progress bar; remaining budget; burn rate | Medium | High | [DONE] |
| **18.6** | **Expense Categories** | Predefined categories: Labor, Materials, Equipment, Services, Travel, Contingency, Other | Low | Medium | [DONE] |
| **18.7** | **Budget Alerts** | Configurable thresholds (50%, 75%, 90%, 100%); visual warnings when exceeded | Medium | High | [DONE] |
| **18.8** | **Expense Approval Workflow** | Status field: Pending, Approved, Rejected, Reimbursed; approver tracking | Medium | Medium | [PARTIAL - Status field only] |
| **18.9** | **Budget Forecast** | Project remaining spend based on burn rate; estimated completion cost | Medium | Medium | [DONE] |
| **18.10** | **Purchase Orders** | Track POs with status: Draft, Submitted, Approved, Received, Closed | Medium | Medium | [DONE] |
| **18.11** | **Vendor Management** | Vendor registry with contact info; link expenses to vendors | Low | Low | [DONE] |
| **18.12** | **Budget Export (Enhanced)** | Export budget report with expense details, attachments list, variance analysis | Medium | High | [NOT IMPLEMENTED] |
| **18.13** | **Multi-Currency Expenses** | Track expenses in different currencies; auto-convert to project currency | Medium | Medium | [NOT IMPLEMENTED] |
| **18.14** | **Expense Notes & Comments** | Add notes to individual expenses for audit trail | Low | Low | [DONE] |
| **18.15** | **Expense Import Wizard** | Batch import expenses from spreadsheets (Excel/CSV) with smart column detection and field mapping UI | High | High | [DONE] |
| **18.16** | **Collapsible Budget Sections** | Make each section in Budget tab expandable/collapsible to reduce visual clutter | Low | High | [DONE] |
| **18.17** | **Fix Spent Report Calculation** | Budget summary "Spent" should include expense ledger data, not just phase actuals | Low | High | [DONE] |
| **18.18** | **Separate Invoice/Settings** | Move Budget Settings and Generate Invoice to separate area from spending reports | Low | Medium | [DONE] |
| **18.19** | **Auto-Map Expenses to Phases** | Automatically assign expenses to phases by date range; allow user to edit mapping | Medium | High | [DONE] |
| **18.20** | **Double-Click Edit Expenses** | Enable double-click on expense rows to open edit modal (consistent with phases/deliveries) | Low | Medium | [DONE] |

#### Data Schema

```javascript
// Project-level budget configuration
project.budget = {
  totalBudget: 500000,           // Total approved CAPEX
  currency: 'USD',
  fiscalYear: '2025',
  approvalDate: '2025-01-15',
  approvalStatus: 'approved',   // draft | pending | approved | rejected
  approvedBy: 'Jane Smith',
  alertThresholds: [50, 75, 90, 100],
  contingencyPercent: 10,       // Reserve percentage
  
  // CAPEX documents
  capexDocuments: [
    {
      id: 'doc-001',
      name: 'CAPEX Approval Form 2025.pdf',
      type: 'application/pdf',
      size: 245000,
      uploadedAt: '2025-01-10T10:30:00Z',
      uploadedBy: 'John Doe',
      data: 'base64...'         // Or external reference
    }
  ]
};

// Expense ledger (array of expenses)
project.expenses = [
  {
    id: 'exp-001',
    name: 'Server Hardware',
    category: 'equipment',      // labor | materials | equipment | services | travel | contingency | other
    amount: 15000,
    currency: 'USD',
    date: '2025-02-15',
    vendor: 'Dell Technologies',
    vendorId: 'vendor-001',     // Optional link to vendor registry
    linkedPhaseId: 'phase-002', // Optional link to project phase
    purchaseOrderId: 'po-001',  // Optional link to PO
    status: 'approved',         // pending | approved | rejected | reimbursed
    approvedBy: 'Jane Smith',
    approvedAt: '2025-02-16T09:00:00Z',
    notes: 'Rack server for production environment',
    
    // Attached receipts/invoices
    attachments: [
      {
        id: 'att-001',
        name: 'Dell Invoice INV-2025-1234.pdf',
        type: 'application/pdf',
        size: 89000,
        uploadedAt: '2025-02-15T14:00:00Z',
        data: 'base64...'
      }
    ],
    
    createdAt: '2025-02-15T10:00:00Z',
    createdBy: 'John Doe'
  }
];

// Purchase Orders
project.purchaseOrders = [
  {
    id: 'po-001',
    number: 'PO-2025-0042',
    vendor: 'Dell Technologies',
    vendorId: 'vendor-001',
    description: 'Server hardware procurement',
    amount: 15000,
    currency: 'USD',
    status: 'received',         // draft | submitted | approved | received | closed
    createdDate: '2025-02-01',
    approvedDate: '2025-02-05',
    receivedDate: '2025-02-14',
    linkedPhaseId: 'phase-002',
    attachments: []
  }
];

// Vendor Registry
project.vendors = [
  {
    id: 'vendor-001',
    name: 'Dell Technologies',
    contact: 'sales@dell.com',
    phone: '1-800-999-3355',
    address: '1 Dell Way, Round Rock, TX',
    category: 'hardware',
    notes: 'Preferred hardware vendor'
  }
];
```

#### UI Components

**18.1 Budget Overview Panel (Dashboard)**
```
+------------------------------------------------------------------+
| PROJECT BUDGET                                           [Edit]   |
+------------------------------------------------------------------+
| Total CAPEX Budget:     $500,000.00                              |
| Fiscal Year:            2025                                      |
| Approval Status:        [Approved] by Jane Smith on Jan 15       |
| CAPEX Documents:        [View 2 documents]                        |
+------------------------------------------------------------------+
| SPENDING SUMMARY                                                  |
| ================================================================ |
| [=============================                    ] 58% ($290,000)|
| ================================================================ |
|                                                                   |
| Total Spent:            $290,000.00                              |
| Committed (POs):        $45,000.00                               |
| Available:              $165,000.00                              |
| Contingency Reserve:    $50,000.00 (10%)                         |
|                                                                   |
| Burn Rate:              $48,333/month                            |
| Forecast at Completion: $520,000 [!Warning: Over budget]         |
+------------------------------------------------------------------+
```

**18.3 Expense Ledger Table**
```
+-----------------------------------------------------------------------------+
| EXPENSES                                    [+ Add Expense] [Export] [Filter]|
+-----------------------------------------------------------------------------+
| Name              | Category   | Amount      | Date       | Status   | Docs |
|-------------------|------------|-------------|------------|----------|------|
| Server Hardware   | Equipment  | $15,000.00  | 2025-02-15 | Approved | [1]  |
| AWS Q1 Services   | Services   | $8,500.00   | 2025-03-01 | Approved | [2]  |
| Team Travel - NYC | Travel     | $3,200.00   | 2025-03-10 | Pending  | [3]  |
| Contractor Hours  | Labor      | $12,000.00  | 2025-03-15 | Approved | [1]  |
|-------------------|------------|-------------|------------|----------|------|
| TOTAL             |            | $38,700.00  |            |          |      |
+-----------------------------------------------------------------------------+
```

**18.4 Expense Detail Modal**
```
+------------------------------------------------------------------+
| EXPENSE DETAILS                                         [X Close] |
+------------------------------------------------------------------+
| Name:           [Server Hardware                              ]   |
| Category:       [Equipment          v]                            |
| Amount:         [$] [15000.00      ]   Currency: [USD v]          |
| Date:           [2025-02-15]                                      |
| Vendor:         [Dell Technologies  v]  [+ New Vendor]            |
| Linked Phase:   [Phase 2: Infrastructure v]                       |
| Purchase Order: [PO-2025-0042      v]                             |
|                                                                   |
| Status:         ( ) Pending  (x) Approved  ( ) Rejected           |
| Approved By:    Jane Smith on Feb 16, 2025                        |
|                                                                   |
| Notes:                                                            |
| [Rack server for production environment                       ]   |
|                                                                   |
| ATTACHMENTS                                           [+ Upload]  |
| +------------------------------------------------------------+   |
| | [PDF] Dell Invoice INV-2025-1234.pdf  89KB  [View] [Delete]|   |
| | [IMG] Receipt photo.jpg               245KB [View] [Delete]|   |
| +------------------------------------------------------------+   |
|                                                                   |
|                              [Cancel] [Save Expense]              |
+------------------------------------------------------------------+
```

#### Implementation Notes

1. **File Storage Strategy**: Since this is a browser-based app using localStorage:
   - Small files (<500KB): Store as base64 in localStorage
   - Large files: Show warning about storage limits
   - Future: Consider IndexedDB for larger file support (Phase 19+)
   - Export: Include attachments in JSON backup

2. **Load Order**: New files should be numbered appropriately:
   - `14-budget-enhanced.js` - Budget management module
   - Add budget UI components to existing files or create `budget-ui.js`

3. **Migration**: Existing `project.budget` data (currency, taxRate) must be preserved and migrated to new schema

4. **Budget Tab**: Consider dedicated "Budget" tab or enhance existing Budget section in Dashboard

5. **Calculations**:
   ```javascript
   // Budget calculations
   const totalSpent = expenses.reduce((sum, e) => sum + e.amount, 0);
   const committed = purchaseOrders
     .filter(po => po.status !== 'closed')
     .reduce((sum, po) => sum + po.amount, 0);
   const available = totalBudget - totalSpent - committed;
   const burnRate = totalSpent / monthsElapsed;
   const forecastAtCompletion = totalSpent + (burnRate * monthsRemaining);
   ```

6. **Alert Logic**:
   ```javascript
   const spentPercent = (totalSpent / totalBudget) * 100;
   const alerts = alertThresholds.filter(t => spentPercent >= t);
   // Show highest triggered alert
   ```

7. **Expense Import Wizard** (18.15):
   - Step 1: File Upload - Accept .xlsx, .xls, .csv files
   - Step 2: Column Detection - Auto-detect common column names
   - Step 3: Field Mapping - User maps source columns to expense fields
   - Step 4: Preview & Import - Show preview, allow corrections, bulk import

**18.15 Expense Import Wizard UI**
```
+------------------------------------------------------------------+
| IMPORT EXPENSES FROM SPREADSHEET                         [X Close]|
+------------------------------------------------------------------+
| Step 2 of 4: Map Columns to Fields                                |
|                                                                   |
| We detected 7 columns in your file. Please map them to expense    |
| fields. Columns marked with * are required.                       |
|                                                                   |
| SOURCE COLUMN          ->    EXPENSE FIELD                        |
| +--------------------------------------------------------+        |
| | Date                  | -> | [Date *           v] |   |        |
| | Vendor                | -> | [Vendor            v] |   |        |
| | Description           | -> | [Name *            v] |   |        |
| | Capex#                | -> | [Notes             v] |   |        |
| | Invoice #             | -> | [Notes (append)    v] |   |        |
| | PO#                   | -> | [Notes (append)    v] |   |        |
| | Amount                | -> | [Amount *          v] |   |        |
| +--------------------------------------------------------+        |
|                                                                   |
| SMART DETECTION:                                                  |
| [x] Auto-detect categories from vendor/description                |
| [x] Skip rows with empty amounts                                  |
| [x] Set all imported expenses to "Approved" status                |
|                                                                   |
|                        [< Back] [Preview Import >]                |
+------------------------------------------------------------------+
```

```
+------------------------------------------------------------------+
| IMPORT EXPENSES FROM SPREADSHEET                         [X Close]|
+------------------------------------------------------------------+
| Step 4 of 4: Preview & Confirm                                    |
|                                                                   |
| Ready to import 40 expenses totaling $527,885.84                  |
|                                                                   |
| PREVIEW (first 5 of 40):                                          |
| +------------------------------------------------------------+   |
| | Date       | Name                    | Vendor     | Amount  |   |
| |------------|-------------------------|------------|---------|   |
| | 2025-10-24 | FRAMED NICKEL CRISIS... | Adv. Elec. | $6,050  |   |
| | 2025-09-19 | Crisis extended forearm | Adv. Elec. | $12,950 |   |
| | 2025-03-05 | Philips heartstart      | All State  | $2,675  |   |
| | 2025-09-15 | Philips heartstart MRX  | All State  | $2,500  |   |
| | 2025-03-11 | Electrode Red dot cloth | Amazon     | $94.91  |   |
| +------------------------------------------------------------+   |
|                                                                   |
| CATEGORY BREAKDOWN:                                               |
| - Services:  31 items ($493,451.68)                              |
| - Materials:  5 items ($20,306.59)                               |
| - Equipment:  4 items ($14,127.57)                               |
|                                                                   |
| [ ] Create vendors from unique vendor names (8 new vendors)       |
|                                                                   |
|                        [< Back] [Import 40 Expenses]              |
+------------------------------------------------------------------+
```

#### Phase 18 Implementation Priority

| Sprint | Features | Notes | Status |
|--------|----------|-------|--------|
| Sprint 1 | 18.1, 18.3, 18.5, 18.6, 18.7, 18.9, 18.14 | Core budget overview, expense ledger, categories, alerts, forecast, notes | COMPLETE (v20) |
| Sprint 2 | 18.2, 18.4, 18.10, 18.11, 18.15 | CAPEX docs, receipts, POs, vendors, import wizard | COMPLETE (v21) |
| Sprint 3 | 18.16, 18.17, 18.18, 18.20 | UX polish: collapsible sections, fix spent calc, reorganize settings, dbl-click edit | COMPLETE (v22) |
| Sprint 4 | 18.19 | Auto-map expenses to phases by date with user-editable mapping | COMPLETE (v23) |
| Sprint 5 | 18.8 | Full approval workflow with approver tracking | NEXT |
| Sprint 6 | 18.12 | Enhanced budget export with variance analysis | |
| Sprint 7 | 18.13 | Multi-currency expense support | |

---

## Implementation Priority Order

### Sprint 1-2: Critical Foundation [COMPLETE]
1. **Phase 14** - Schedule Management (required for Gantt)
2. **Phase 13.1-13.2** - Visualizations tab + Gantt chart

### Sprint 3-4: Core Visualization [COMPLETE]
3. **Phase 13.3-13.4** - Calendar + Timeline views
4. **Phase 15.6** - Dependency UI (enhances Gantt)

### Sprint 5-6: Organization [COMPLETE]
5. **Phase 15.1** - Drag & drop
6. **Phase 15.3** - Tags/Labels
7. **Phase 15.2** - Priority levels

### Sprint 7-8: Remaining Features [COMPLETE]
8. **Phase 13.5-13.6** - Progress charts + Burndown
9. **Phase 15.4-15.5** - Bulk actions + Archive

### Sprint 9-10: Collaboration [COMPLETE]
10. **Phase 16.1-16.3** - Comments + @mentions + JIRA import
11. **Phase 16.4-16.6** - Shareable links + HTML export

### Sprint 11-12: UX Polish [COMPLETE]
12. **Phase 17.1-17.8** - All UX improvements and project architecture

### Sprint 13-18: Enhanced Budget Management [IN PROGRESS]
13. **Phase 18.1, 18.3, 18.5, 18.6, 18.7, 18.9, 18.14** - Budget overview, expense ledger, dashboard, categories, alerts, forecast, notes [COMPLETE in v20]
14. **Phase 18.2, 18.4, 18.10, 18.11, 18.15** - CAPEX docs, receipts, POs, vendors, import wizard [COMPLETE in v21]
15. **Phase 18.16, 18.17, 18.18, 18.20** - UX polish: collapsible sections, fix spent calc, reorganize settings, dbl-click edit [COMPLETE in v22]
16. **Phase 18.19** - Auto-map expenses to phases by date [COMPLETE in v23]
17. **Phase 18.8** - Full approval workflow (approver tracking) [NEXT]
18. **Phase 18.12** - Enhanced budget export
19. **Phase 18.13** - Multi-currency expenses

---

## Success Metrics

| Metric | v1.0 | v15.0 | v16.0 | v17.0 | v18.0 | v19.0 | v20.0 | v21.0 | v22.0 | v23.0 (Current) | v24.0 (Target) |
|--------|------|-------|-------|-------|-------|-------|-------|-------|-------|-----------------|----------------|
| Features implemented | 15 | 85 | 92 | 98 | 104 | 112 | 120 | 125 | 129 | 130 | 132 |
| Features working as claimed | - | 85 | 92 | 98 | 104 | 112 | 120 | 125 | 129 | 130 | 132 |
| Visualization views | 0 | 6 | 6 | 6 | 6 | 6 | 6 | 6 | 6 | 6 | 6 |
| Export formats | 2 | 6 | 6 | 6 | 7 | 7 | 7 | 7 | 7 | 7 | 8 |
| Schedule management | 0 | 0 | Full | Full | Full | Full | Full | Full | Full | Full | Full |
| Organization features | 0 | 0 | 0 | Full | Full | Full | Full | Full | Full | Full | Full |
| Collaboration features | 0 | 0 | 0 | 0 | Full | Full | Full | Full | Full | Full | Full |
| Budget management | Basic | Basic | Basic | Basic | Basic | Basic | Enhanced | Full | Full+ | **Full++** | Full++ |
| Project architecture | Basic | Basic | Basic | Basic | Basic | Isolated | Isolated | Isolated | Isolated | Isolated | Isolated |
| Data loss incidents | Unknown | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| Accessibility score | Unknown | 75% | 75% | 75% | 75% | 75% | 75% | 75% | 75% | 75% | 80% |
| Load time (cold start) | ~1s | <1s | <1s | <1s | <1s | <1s | <1s | <1s | <1s | <1s | <1s |

---

## Appendix: Changelog

| Version | Date | Changes |
|---------|------|---------|
| 3.3 | Dec 20, 2025 | **v23 RELEASE**: Phase 18 Sprint 4 complete - Auto-Map Expenses to Phases. New feature: (18.19) Auto-Map Expenses to Phases with modal showing unmapped expenses, auto-detection of phase matches based on expense date falling within phase start/due date range, user-editable phase dropdowns, select-all checkbox, stats display (unmapped/auto-detected/selected counts), and bulk apply functionality. Added "Phase" column to expense ledger table showing linked phase badges. Removed expense auto-mapping from Known Issues (now implemented). Budget management now at "Full++" level with 13 of 15 Phase 18 features complete. |
| 3.2 | Dec 20, 2025 | **v22 RELEASE**: Phase 18 Sprint 3 complete - Budget UX polish. New features: (18.16) Collapsible Budget Sections with Expand All/Collapse All buttons, state persisted in localStorage, sensible defaults for new users. (18.17) Fixed Spent Report Calculation - now includes ALL expenses from expense ledger (except rejected), not just phase actuals. Both the main budget overview panel and legacy phase budget summary now correctly reflect total spending. (18.18) Separated Invoice/Settings - Budget Settings and Generate Invoice moved to dedicated collapsible "Settings & Invoicing" section at bottom of Budget tab, collapsed by default. (18.20) Double-Click Edit Expenses - expense rows now support double-click to open edit modal, consistent with phases and deliveries. Added expense count badge in section header. Removed 4 items from Known Issues (all fixed). |
| 3.1 | Dec 20, 2025 | **ROADMAP UPDATE**: Added 5 new Phase 18 features based on user feedback: (18.16) Collapsible Budget Sections - make each section expandable/collapsible to reduce visual clutter. (18.17) Fix Spent Report Calculation - bug where budget summary "Spent" doesn't include expense ledger data. (18.18) Separate Invoice/Settings - move Budget Settings and Generate Invoice away from spending reports. (18.19) Auto-Map Expenses to Phases - automatically assign expenses to phases by date range with user-editable mapping. (18.20) Double-Click Edit Expenses - enable double-click on expense rows to open edit modal. Updated Known Issues section and Implementation Priority to prioritize UX polish in Sprint 3. |
| 3.0 | Dec 20, 2025 | **v21 RELEASE**: Phase 18 Sprint 2 complete - Full budget management system. New features: (18.2) CAPEX Document Attachments with upload, view, delete for PDF/images up to 5MB stored as base64. (18.4) Receipt/Invoice Attachments on expenses with multi-file upload, receipt count badge in ledger. (18.10) Purchase Orders with full table view, status workflow (Draft/Submitted/Approved/Received/Closed), vendor linking, phase linking, expected/received dates. (18.11) Vendor Management registry with contact info, address, per-vendor spend tracking, expense counts, vendor dropdown in expense modal. (18.15) Expense Import Wizard - 3-step process: file upload (Excel/CSV), smart column mapping with auto-detection, preview with category breakdown and import options (skip empty, create vendors, default status). Budget management now considered "Full" with 12 of 15 Phase 18 features complete. |
| 2.9 | Dec 20, 2025 | **ROADMAP UPDATE**: Added 18.15 Expense Import Wizard feature - batch import expenses from Excel/CSV spreadsheets with 4-step wizard: (1) File upload accepting .xlsx/.xls/.csv, (2) Smart column detection with auto-mapping, (3) User field mapping UI with dropdowns, (4) Preview with category breakdown and bulk import. Features include auto-category detection from vendor/description, skip empty amounts option, configurable default status, and optional vendor creation from unique names. Added UI mockups for mapping and preview steps. Updated Phase 18 implementation priority with Sprint 7 for import wizard. |
| 2.8 | Dec 20, 2025 | **v20 RELEASE**: Phase 18 Sprint 1 complete - Enhanced Budget Management foundation. New Budget Overview Panel with CAPEX total budget, fiscal year, approval status (draft/pending/approved/rejected), and configurable alert thresholds. Budget vs Actual Dashboard with visual progress bar (color-coded by threshold), stats grid (Total/Spent/Committed/Available/Contingency), monthly burn rate calculation, and forecast at completion with over-budget warnings. Expense Categories with 7 predefined types (Labor, Materials, Equipment, Services, Travel, Contingency, Other) displayed as visual cards. Full Expense Ledger with add/edit/delete, category assignment, vendor tracking, phase linking, status workflow (Pending/Approved/Rejected/Reimbursed), and notes. Budget Alerts trigger at configurable thresholds (50%, 75%, 90%, 100%). New data schema: `project.budgetOverview`, `project.expenses[]`, `project.purchaseOrders[]`, `project.vendors[]`. Backward compatible - existing projects auto-migrate. |
| 2.7 | Dec 20, 2025 | **ROADMAP UPDATE**: Added Phase 18 (Enhanced Budget Management) with 14 new features: Project Budget Overview with CAPEX allocation, CAPEX Document Attachments, Expense Ledger table, Receipt/Invoice Attachments, Budget vs Actual Dashboard, Expense Categories, Budget Alerts with thresholds, Expense Approval Workflow, Budget Forecast with burn rate, Purchase Orders tracking, Vendor Management registry, Enhanced Budget Export, Multi-Currency Expenses, Expense Notes. Added data schema, UI mockups, and implementation notes. Updated Success Metrics for v20 targets. |
| 2.6 | Dec 20, 2025 | **v19 RELEASE**: Phase 17 complete - All UX polish and project architecture features implemented. Remember last project auto-loads on startup. Project isolation stores each project in separate localStorage key with automatic migration from legacy storage. Dashboard sections default collapsed for new users. Delete current project button in header with confirmation. Save button renamed to "Save Now" with clarity tooltip. Hide/unhide phases via context menu with "Show Hidden" toggle. Link deliverables to phases with dropdown and click-to-navigate badge. Double-click phases opens schedule modal, double-click deliveries opens context menu. |
| 2.5 | Dec 20, 2025 | **ROADMAP UPDATE**: Added Phase 17 (UX Polish & Project Architecture) with 8 new features: Remember last project, Project isolation, Dashboard default collapsed, Delete project, Save button clarity, Hide/unhide phases, Link deliverables to phases, Double-click to expand. Added "Known Issues & Polish Items" section to Current State. Updated Success Metrics for v19 goals. |
| 2.4 | Dec 20, 2025 | **v18 RELEASE**: Phase 16 complete - All collaboration features implemented. Added comments system with threaded UI on phases and deliveries. @mentions with team member autocomplete dropdown. Shareable project links via URL encoding (base64); auto-imports when URL contains #share=. HTML report export generates standalone file with embedded CSS, dark theme. New Share button in header with Ctrl+L shortcut. Context menu shows Comments option with count. |
| 2.3 | Dec 20, 2025 | **v17 RELEASE**: Phase 15 complete - All missing core features implemented. Added drag & drop reorder for phases (native HTML5). Priority levels with click-to-cycle (high/medium/low). Tags/Labels system with project-level tag library. Bulk actions toolbar (select multiple, change status, archive, delete). Archive items with "Show Archived" toggle. Dependency UI modal to add/remove phase dependencies. **UX Fix**: Dashboard sections now collapsible with Expand/Collapse All buttons, state persisted in localStorage. |
| 2.2 | Dec 20, 2025 | **v16 RELEASE**: Phase 14 complete - Full schedule management for phases and tasks. Added startDate/dueDate/actualStartDate/actualEndDate to phases; startDate/dueDate/completedDate to tasks. Schedule modal with variance tracking. Overdue indicators on cards/Gantt. KPI shows overdue count. JIRA CSV import with Epic/Task hierarchy mapping. Gantt chart now uses actual dates. |
| 2.1 | Dec 20, 2025 | **v15 RELEASE**: Phase 13 complete - Restored all visualization features from v7. Added Visualizations tab with Timeline view, Calendar view, Gantt chart, Progress charts (pie/bar), and Burndown summary. All features working with current v14 data structures. |
| 2.0 | Dec 20, 2025 | **AUDIT REVISION**: Comprehensive code audit revealed 21 features marked [DONE] were not implemented. Corrected all status markers. Added Phases 13-16 for reimplementation. Updated Current State to reflect verified capabilities only. Added implementation priority order. Previous versions (v1-v13) archived and available for feature reference. |
| 1.8 | Dec 19, 2025 | Phase 8 completed: ICS Calendar Export (8.1), Excel Export with formatting (8.2), Project Snapshots (8.3). Marked remaining Phase 7 items as DEFERRED. |
| 1.7 | Dec 19, 2025 | Implemented 7.4 (PDF Export) and 7.5 (Print Stylesheet) |
| 1.6 | Dec 19, 2025 | Added Phases 8-12 |
| 1.5 | Dec 19, 2025 | Phase 5 partial: Team Members, Assignees, Activity Log |
| 1.4 | Dec 19, 2025 | Phase 4 claimed complete (later found to be regression) |
| 1.3 | Dec 19, 2025 | Phase 3 partial: Subtasks, Templates, Categories, Alerts |
| 1.2 | Dec 19, 2025 | Phase 2 partial: Undo/Redo, Search, Delivery status, Theme |
| 1.1 | Dec 19, 2025 | Phase 1 completed |
| 1.0 | Dec 19, 2025 | Initial roadmap created |

---

## Appendix: Archived Versions Reference

Previous versions are archived and available upon request for reimplementation reference:

| Version | Key Features to Reference |
|---------|--------------------------|
| **v7** | Complete Visualizations tab: Gantt chart, Calendar view, Timeline, Progress charts, Burndown chart. CSS classes: `.gantt-*`, `.calendar-*`, `.timeline-*`. Functions: `renderGanttChart()`, `renderCalendarView()`, `renderTimeline()` |
| **v1-v6** | Earlier iterations, may contain alternative implementations |

When reimplementing lost features, request the specific archived version for code reference.

---

*This is a living document. Update as priorities shift and features are completed.*
