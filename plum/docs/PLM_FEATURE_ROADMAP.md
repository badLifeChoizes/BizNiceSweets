# PRJ-MGMT Tool -- Product Roadmap

**Document Version:** 3.0  
**Created:** December 19, 2025  
**Last Updated:** December 20, 2025  
**Status:** Active - v54 Released (Phase 19 Complete)

---

## Executive Summary

This roadmap outlines planned features, capabilities, and improvements for the PRJ-MGMT Tool -- a browser-based project management application. Features are organized into phases based on priority, complexity, and user value.

**Version 2.0 Note:** This revision corrects feature statuses based on a comprehensive code audit of v14. Several features previously marked [DONE] were not actually implemented and have been rescheduled for implementation in new phases. Previous versions (v1-v13) are archived and available for reference when reimplementing lost features.

---

## Current State (v54.0)

### Verified Capabilities

| Category | Features |
|----------|----------|
| **Projects** | Create, save, load, delete projects; LocalStorage persistence; Categories; Search, Pin, Recent projects; **Isolated storage per project; Remember last project; Delete current project** |
| **Phases (Epics)** | Add/edit/delete phases; progress slider (0-100%); status tracking; assignees; context menus; start/due dates; schedule modal; duration calculation; overdue alerts; **Hide/unhide phases; Double-click to edit** |
| **Tasks** | Subtasks within phases; start/due dates; completion dates; overdue indicators; edit modal |
| **Deliveries** | Date-based deliverables; countdown timers; urgency indicators; assignees; context menus; **Link to phases; Double-click to edit** |
| **Notes** | Three-category system (Focus, Milestones, Future Plans); Markdown preview support |
| **Budget** | Estimated vs actual costs; currency settings; tax rates |
| **Time Tracking** | Log hours per phase; team member rates; labor cost calculation |
| **Resources** | Track materials/equipment; quantity and cost; status (needed/ordered/received) |
| **Team** | Team members with roles, rates, and avatar colors |
| **Import/Export** | JSON, CSV, Budget reports, PDF reports, HTML reports, ICS Calendar, Excel (.xlsx); JIRA hierarchical CSV import (Epic/Task mapping) |
| **Snapshots** | Point-in-time project snapshots for comparison |
| **Invoice** | Generate invoices from tracked time and costs |
| **Presentation** | Full-screen mode; read-only view for meetings |
| **Print** | Optimized print stylesheet for project reports |
| **UI** | Tab navigation; KPI dashboard; keyboard shortcuts; light/dark themes; view density toggle; collapsible Dashboard sections; **Dashboard default collapsed for new users; Save button clarity** |
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
| **PLM Pricing & Margins** | **Product/package sale prices; Distributor discounts; Labor cost roll-up (all BOM levels); Margin dashboards; Comparison visualizations** |

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

### Phase 2: Core Enhancements [PARTIAL]
**Timeline:** 3-4 Weeks  
**Theme:** Essential productivity features

| ID | Feature | Description | Effort | Impact | Status |
|----|---------|-------------|--------|--------|--------|
| 2.1 | Undo/Redo | History stack for reversing changes (Ctrl+Z/Y) | Medium | High | [DONE] |
| 2.2 | Drag & drop reorder | Reorder phases and deliveries by dragging | Medium | High | [DONE] |
| 2.3 | Global search | Search across phases, deliveries, notes (Ctrl+F) | Medium | High | [DONE] |
| 2.4 | Delivery status | Open/Pending/Delivered status for deliveries | Low | Medium | [DONE] |
| 2.5 | Theme toggle | Light/Dark mode with system preference detection | Low | Medium | [DONE] |
| 2.6 | Auto-backup | Periodic backup to separate storage key | Medium | High | [NOT IMPLEMENTED] |
| 2.7 | Keyboard navigation | Full keyboard control of UI elements | Medium | Medium | [NOT IMPLEMENTED] |

---

### Phase 3: Planning Tools [PARTIAL]
**Timeline:** 3-4 Weeks  
**Theme:** Enhanced planning and tracking

| ID | Feature | Description | Effort | Impact | Status |
|----|---------|-------------|--------|--------|--------|
| 3.1 | Subtasks | Add subtasks to phases with progress tracking | Medium | High | [DONE] |
| 3.2 | Templates | Save phases as templates for reuse | Low | Medium | [DONE] |
| 3.3 | Categories | Add category field for grouping phases | Low | Medium | [DONE] |
| 3.4 | Alerts | Configurable notification for deadlines/milestones | Medium | High | [DONE] |
| 3.5 | Time estimates | Estimated vs actual hours per phase | Low | High | [DONE] |
| 3.6 | Dependencies | Link phases to show predecessor/successor relationships | High | High | [DONE] |
| 3.7 | Priority levels | High/Medium/Low priority for phases | Low | Medium | [DONE] |

---

### Phase 4: Visualizations [DONE]
**Timeline:** 2-3 Weeks  
**Theme:** Visual project understanding

| ID | Feature | Description | Effort | Impact | Status |
|----|---------|-------------|--------|--------|--------|
| 4.1 | Gantt chart | Interactive Gantt with date awareness | High | High | [DONE] |
| 4.2 | Calendar view | Monthly/weekly calendar of deliveries | Medium | High | [DONE] |
| 4.3 | Timeline view | Horizontal timeline of phases and deliveries | Medium | High | [DONE] |
| 4.4 | Progress charts | Pie/bar charts for phase completion | Low | Medium | [DONE] |
| 4.5 | Burndown chart | Track remaining work over time | Medium | Medium | [DONE] |

---

### Phase 5: Team & Resources [PARTIAL]
**Timeline:** 3-4 Weeks  
**Theme:** Collaboration and resource management

| ID | Feature | Description | Effort | Impact | Status |
|----|---------|-------------|--------|--------|--------|
| 5.1 | Team members | Add team with roles, rates, and avatars | Medium | High | [DONE] |
| 5.2 | Assignees | Assign team members to phases | Low | High | [DONE] |
| 5.3 | Activity log | Track all project changes with timestamps | Medium | Medium | [DONE] |
| 5.4 | Resource tracking | Track materials, equipment, costs | Medium | High | [DONE] |
| 5.5 | Workload view | See team member allocation across phases | Medium | Medium | [DONE] |
| 5.6 | Time tracking | Log actual hours worked per team member | Medium | High | [DONE] |

---

### Phase 6: Advanced Features [PARTIAL]
**Timeline:** 4-6 Weeks  
**Theme:** Power user capabilities

| ID | Feature | Description | Effort | Impact | Status |
|----|---------|-------------|--------|--------|--------|
| 6.1 | Risk register | Track risks with likelihood/impact matrix | Medium | High | [DONE] |
| 6.2 | Milestones | Key project milestones with timeline view | Medium | High | [DONE] |
| 6.3 | Decision log | Track decisions with rationale and dates | Low | Medium | [DONE] |
| 6.4 | Custom fields | User-defined fields for phases | High | Medium | [NOT IMPLEMENTED] |
| 6.5 | Recurring items | Templates for repeating phases | Medium | Medium | [DONE] |
| 6.6 | Critical path | Highlight critical path in visualizations | High | High | [DONE] |

---

### Phase 7: Export & Reporting [PARTIAL]
**Timeline:** 2-3 Weeks  
**Theme:** Get data out of the system

| ID | Feature | Description | Effort | Impact | Status |
|----|---------|-------------|--------|--------|--------|
| 7.1 | Export to JSON | Full project export for backup/transfer | Low | High | [DONE] |
| 7.2 | Export to CSV | Tabular export of phases and deliveries | Low | Medium | [DONE] |
| 7.3 | Budget report | Detailed cost breakdown report | Medium | High | [DONE] |
| 7.4 | PDF export | Generate PDF project report | Medium | High | [DONE] |
| 7.5 | Print stylesheet | Optimized print layout | Low | Medium | [DONE] |
| 7.6 | HTML export | Shareable standalone HTML report | Medium | Medium | [DONE] |
| 7.7 | API export | JSON API-ready output format | Medium | Low | [DEFERRED] |

---

### Phase 8: Integration & Import [DONE]
**Timeline:** 2-3 Weeks  
**Theme:** Connect with other tools

| ID | Feature | Description | Effort | Impact | Status |
|----|---------|-------------|--------|--------|--------|
| 8.1 | ICS Calendar | Export deliveries to calendar apps | Medium | High | [DONE] |
| 8.2 | Excel export | .xlsx export with formatting | Medium | High | [DONE] |
| 8.3 | Snapshots | Point-in-time project snapshots | Medium | High | [DONE] |
| 8.4 | Import from CSV | Import phases from spreadsheet | Medium | Medium | [DONE] |
| 8.5 | JIRA import | Import from JIRA CSV with Epic/Task hierarchy | Medium | High | [DONE] |

---

### Phase 9: Analytics & Insights [DONE]
**Timeline:** 3-4 Weeks  
**Theme:** Data-driven project management

| ID | Feature | Description | Effort | Impact | Status |
|----|---------|-------------|--------|--------|--------|
| 9.1 | Project health score | Composite metric for project status | Medium | High | [DONE] |
| 9.2 | Team workload | Analyze resource allocation | Medium | Medium | [DONE] |
| 9.3 | Estimate vs actual | Compare planned vs actual metrics | Low | High | [DONE] |
| 9.4 | Velocity tracking | Track completion rate over time | Medium | Medium | [DONE] |

---

### Phase 10: Polish & Performance [PARTIAL]
**Timeline:** 2-3 Weeks  
**Theme:** Production-ready quality

| ID | Feature | Description | Effort | Impact | Status |
|----|---------|-------------|--------|--------|--------|
| 10.1 | Accessibility audit | WCAG 2.1 AA compliance | High | Medium | [NOT IMPLEMENTED] |
| 10.2 | Performance optimization | Handle 200+ phases smoothly | Medium | Medium | [NOT IMPLEMENTED] |
| 10.3 | Mobile responsiveness | Touch-friendly layout for tablets | High | Medium | [NOT IMPLEMENTED] |
| 10.4 | Error handling | Graceful error messages and recovery | Medium | High | [PARTIAL] |
| 10.5 | Loading states | Progress indicators for all operations | Low | Medium | [DONE] |

---

### Phase 11: Advanced Export [DONE]
**Timeline:** 2-3 Weeks  
**Theme:** Professional output formats

| ID | Feature | Description | Effort | Impact | Status |
|----|---------|-------------|--------|--------|--------|
| 11.1 | Invoice generation | Create invoices from time tracking | Medium | High | [DONE] |
| 11.2 | Presentation mode | Full-screen read-only for meetings | Low | Medium | [DONE] |
| 11.3 | Custom report builder | Configurable report templates | High | Medium | [NOT IMPLEMENTED] |

---

### Phase 12: AI-Assisted Features [NOT IMPLEMENTED]
**Timeline:** 4-6 Weeks  
**Theme:** Smart automation

| ID | Feature | Description | Effort | Impact | Status |
|----|---------|-------------|--------|--------|--------|
| 12.1 | Smart scheduling | AI-suggested phase ordering | High | High | [NOT IMPLEMENTED] |
| 12.2 | Risk prediction | Identify potential delays | High | High | [NOT IMPLEMENTED] |
| 12.3 | Resource optimization | Suggest optimal team allocation | High | Medium | [NOT IMPLEMENTED] |
| 12.4 | Status summaries | AI-generated project summaries | Medium | Medium | [NOT IMPLEMENTED] |

---

### Phase 13: Visualization Restoration [DONE]
**Timeline:** 1 Week  
**Theme:** Restore visualization features from v7

| ID | Feature | Description | Effort | Impact | Status |
|----|---------|-------------|--------|--------|--------|
| 13.1 | Visualizations tab | Restore tab navigation for charts | Low | High | [DONE] |
| 13.2 | Timeline view | Horizontal timeline of phases | Medium | High | [DONE] |
| 13.3 | Calendar view | Monthly calendar of deliveries | Medium | High | [DONE] |
| 13.4 | Gantt chart | Basic Gantt with phase bars | Medium | High | [DONE] |
| 13.5 | Progress charts | Pie and bar charts for completion | Low | Medium | [DONE] |
| 13.6 | Burndown summary | Work remaining over time | Low | Medium | [DONE] |

---

### Phase 14: Schedule Management [DONE]
**Timeline:** 1-2 Weeks  
**Theme:** Full schedule tracking with planned vs actual variance

| ID | Feature | Description | Effort | Impact | Status |
|----|---------|-------------|--------|--------|--------|
| 14.1 | Phase start/due dates | Add startDate, dueDate to phases | Low | High | [DONE] |
| 14.2 | Task start/due/completed | Add scheduling fields to tasks | Low | High | [DONE] |
| 14.3 | Schedule modal | Dedicated modal for editing phase schedule | Medium | High | [DONE] |
| 14.4 | Overdue indicators | Visual indicators on overdue items | Low | Medium | [DONE] |
| 14.5 | Schedule-aware Gantt | Gantt chart uses actual date data | Medium | High | [DONE] |
| 14.6 | KPI: Overdue count | Dashboard KPI showing overdue phases/tasks | Low | Medium | [DONE] |
| 14.7 | JIRA CSV import | Import with Epic/Task hierarchy mapping | Medium | High | [DONE] |

---

### Phase 15: Missing Core Features [DONE]
**Timeline:** 1-2 Weeks  
**Theme:** Implement features marked DONE but never built

| ID | Feature | Description | Effort | Impact | Status |
|----|---------|-------------|--------|--------|--------|
| 15.1 | Drag & drop reorder | Native HTML5 drag for phases | Medium | High | [DONE] |
| 15.2 | Priority levels | High/Medium/Low with visual indicators | Low | Medium | [DONE] |
| 15.3 | Tags/Labels | Project-level tag library with colors | Medium | Medium | [DONE] |
| 15.4 | Bulk actions | Select multiple items, batch operations | Medium | High | [DONE] |
| 15.5 | Archive items | Soft delete with "Show Archived" toggle | Low | Medium | [DONE] |
| 15.6 | Dependency UI | Modal to manage phase dependencies | Medium | High | [DONE] |
| 15.7 | Collapsible dashboard | Collapse/expand dashboard sections | Low | Medium | [DONE] |

---

### Phase 16: Collaboration Features [DONE]
**Timeline:** 1-2 Weeks  
**Theme:** Team communication and sharing

| ID | Feature | Description | Effort | Impact | Status |
|----|---------|-------------|--------|--------|--------|
| 16.1 | Comments on phases | Add threaded comments to phases | Medium | High | [DONE] |
| 16.2 | Comments on deliveries | Add threaded comments to deliveries | Medium | High | [DONE] |
| 16.3 | @mentions | Tag team members in comments with autocomplete | Medium | Medium | [DONE] |
| 16.4 | Shareable links | Generate URL-encoded shareable project links | Medium | High | [DONE] |
| 16.5 | HTML export enhanced | Standalone HTML with embedded CSS and dark theme | Low | Medium | [DONE] |

---

### Phase 17: UX Polish & Project Architecture [DONE]
**Timeline:** 1-2 Weeks  
**Theme:** Improve user experience and project data management

| ID | Feature | Description | Effort | Impact | Status |
|----|---------|-------------|--------|--------|--------|
| 17.1 | Remember last project | Auto-load last used project on startup | Low | High | [DONE] |
| 17.2 | Project isolation | Each project uses separate localStorage key | Medium | High | [DONE] |
| 17.3 | Dashboard default collapsed | New users see collapsed dashboard sections | Low | Medium | [DONE] |
| 17.4 | Delete current project | Delete button in header with confirmation | Low | Medium | [DONE] |
| 17.5 | Save button clarity | Rename to "Save Now" with tooltip explanation | Low | Low | [DONE] |
| 17.6 | Hide/unhide phases | Context menu option to hide phases; toggle to show | Medium | Medium | [DONE] |
| 17.7 | Link deliverables to phases | Dropdown to associate delivery with phase | Medium | Medium | [DONE] |
| 17.8 | Double-click to expand | Double-click phases/deliveries opens edit modal | Low | Medium | [DONE] |

---

### Phase 18: Enhanced Budget Management [NOT IMPLEMENTED]
**Timeline:** 4-6 Weeks  
**Theme:** Comprehensive budget tracking, expenses, and financial reporting
**Priority:** HIGH - Essential for accurate project financial management

#### Overview

This phase transforms the basic budget tracking into a full financial management module. It adds expense categorization, receipt attachments, budget vs actual dashboards, approval workflows, purchase orders, and vendor management.

#### Features

| ID | Feature | Description | Effort | Impact | Status |
|----|---------|-------------|--------|--------|--------|
| **18.1** | **Project Budget Overview** | Dashboard showing total budget, CAPEX allocation, remaining funds | Medium | High | [NOT IMPLEMENTED] |
| **18.2** | **CAPEX Document Attachments** | Attach capital expenditure approval documents to budget items | Medium | Medium | [NOT IMPLEMENTED] |
| **18.3** | **Expense Ledger** | Itemized expense table with date, category, amount, description | Medium | High | [NOT IMPLEMENTED] |
| **18.4** | **Receipt/Invoice Attachments** | Attach receipts/invoices to expense entries (base64 storage) | Medium | Medium | [NOT IMPLEMENTED] |
| **18.5** | **Budget vs Actual Dashboard** | Visual comparison of budgeted vs actual spending by category | High | High | [NOT IMPLEMENTED] |
| **18.6** | **Expense Categories** | Customizable expense categories (Labor, Materials, Travel, etc.) | Low | Medium | [NOT IMPLEMENTED] |
| **18.7** | **Budget Alerts** | Threshold alerts when spending exceeds % of budget | Medium | High | [NOT IMPLEMENTED] |
| **18.8** | **Expense Approval Workflow** | Submit/Approve/Reject flow for expenses with audit trail | High | Medium | [NOT IMPLEMENTED] |
| **18.9** | **Budget Forecast** | Project remaining budget based on burn rate | Medium | Medium | [NOT IMPLEMENTED] |
| **18.10** | **Purchase Orders** | Create and track POs linked to budget items | High | Medium | [NOT IMPLEMENTED] |
| **18.11** | **Vendor Management** | Vendor registry with contact info, payment terms | Medium | Medium | [NOT IMPLEMENTED] |
| **18.12** | **Enhanced Budget Export** | Export budget report with expenses, attachments, and charts | Medium | High | [NOT IMPLEMENTED] |
| **18.13** | **Multi-Currency Expenses** | Log expenses in different currencies with conversion | Medium | Low | [NOT IMPLEMENTED] |
| **18.14** | **Expense Notes** | Add notes/justification to individual expenses | Low | Low | [NOT IMPLEMENTED] |

---

### Phase 19: PLM Pricing & Margin Analysis [DONE]
**Timeline:** 3-4 Weeks  
**Theme:** Product and package pricing, margin tracking, and profitability analysis
**Priority:** HIGH - Critical for sales and financial planning

#### Overview

This phase adds comprehensive pricing and margin analysis capabilities to the PLM system. Products and packages gain sale price and distributor discount fields, enabling margin calculations at both individual product and package levels. The dashboard is enhanced with profitability metrics and comparison visualizations.

**Key Insight from Code Audit:** The current `generateFlatBom()` function correctly avoids double-counting material costs by only summing leaf parts. However, labor costs on intermediate sub-assemblies are NOT included in the roll-up. Feature 19.5 addresses this gap.

#### Features

| ID | Feature | Description | Effort | Impact | Status |
|----|---------|-------------|--------|--------|--------|
| **19.1** | **Product Sale Price Field** | Add `salePrice` field to products; editable in product detail view | Low | High | [DONE] |
| **19.2** | **Product Distributor Discount** | Add `distributorDiscount` percentage field to products (0-100%) | Low | High | [DONE] |
| **19.3** | **Package Sale Price Field** | Add `salePrice` field to packages; independent of contained product prices | Low | High | [DONE] |
| **19.4** | **Package Distributor Discount** | Add `distributorDiscount` percentage field to packages; does NOT stack with product discounts | Low | High | [DONE] |
| **19.5** | **Assembly Labor Cost Roll-up** | Modify cost calculation to include labor costs from intermediate sub-assemblies, not just leaf parts | Medium | High | [DONE] |
| **19.6** | **Product Margin Dashboard** | Display margin metrics on product detail: Direct Margin, Margin %, Distributor Price, Profit After Distributor | Medium | High | [DONE] |
| **19.7** | **Package Margin Dashboard** | Display margin metrics on package detail with same calculations; package discount applies independently | Medium | High | [DONE] |
| **19.8** | **Margin Comparison Visualizations** | Charts comparing products/packages by margin, margin %, and profitability | High | Medium | [DONE] |
| **19.9** | **Overhead Cost Field** | Optional: Add `overheadCost` field to parts/assemblies for indirect costs (future enhancement) | Low | Medium | [DEFERRED] |

#### Data Schema

```javascript
// Product schema additions
part.salePrice = 150.00;              // User-set sale price
part.distributorDiscount = 15;        // Percentage discount for distributors (0-100)

// Package schema additions  
package.salePrice = 500.00;           // User-set package sale price (independent of product prices)
package.distributorDiscount = 20;     // Package-level distributor discount (does NOT stack)

// Future: Overhead cost tracking
part.overheadCost = 5.00;             // Indirect costs (facilities, utilities, etc.)
```

#### Calculation Formulas

```javascript
// For Products
const totalCost = Parts.getRolledUpCostWithLabor(productId);  // Material + ALL labor (including sub-assembly labor)
const salePrice = product.salePrice || 0;
const directMargin = salePrice - totalCost;
const directMarginPercent = salePrice > 0 ? (directMargin / salePrice) * 100 : 0;
const distributorDiscount = product.distributorDiscount || 0;
const distributorPrice = salePrice * (1 - distributorDiscount / 100);
const profitAfterDistributor = distributorPrice - totalCost;

// For Packages (discounts do NOT stack - only package discount applies)
const packageTotalCost = products.reduce((sum, p) => sum + Parts.getRolledUpCostWithLabor(p.id), 0);
const packageSalePrice = package.salePrice || 0;  // User-set, not sum of products
const packageDirectMargin = packageSalePrice - packageTotalCost;
const packageDirectMarginPercent = packageSalePrice > 0 ? (packageDirectMargin / packageSalePrice) * 100 : 0;
const packageDistributorDiscount = package.distributorDiscount || 0;  // Only this discount applies
const packageDistributorPrice = packageSalePrice * (1 - packageDistributorDiscount / 100);
const packageProfitAfterDistributor = packageDistributorPrice - packageTotalCost;
```

#### 19.5 Assembly Labor Cost Roll-up Implementation

Current behavior (`generateFlatBom`):
- Recursively traverses BOM tree
- Only adds LEAF parts (parts with no BOM) to the cost sum
- Labor costs on intermediate assemblies are LOST

Fixed behavior (`getRolledUpCostWithLabor`):
```javascript
getRolledUpCostWithLabor(partId, visitedIds = new Set()) {
  if (visitedIds.has(partId)) return 0;
  visitedIds.add(partId);
  
  const part = this.getById(partId);
  if (!part) return 0;
  
  // Start with this part's labor cost (even for assemblies)
  let total = this.getLaborCost(part);
  
  if (!part.bom || part.bom.length === 0) {
    // Leaf part: add material cost + labor
    return this.getEffectiveCost(part);  // Already includes labor
  }
  
  // Assembly: add labor for THIS assembly, then recurse
  for (const item of part.bom) {
    const childCost = this.getRolledUpCostWithLabor(item.partId, new Set(visitedIds));
    total += childCost * item.qty;
  }
  
  return total;
}
```

#### New Parts Module Functions

```javascript
// Get total cost including all labor at every BOM level
getRolledUpCostWithLabor(partId, visitedIds = new Set())

// Get only material costs (no labor) rolled up
getRolledUpMaterialCost(partId, visitedIds = new Set())

// Get total labor costs from all BOM levels
getRolledUpLaborCost(partId, visitedIds = new Set())
```

#### MarginAnalysis Module

```javascript
const MarginAnalysis = {
  // Get comprehensive pricing for a single product
  getProductPricing(productId) {
    // Returns: { totalCost, materialCost, laborCost, salePrice, distributorDiscount,
    //            directMargin, directMarginPercent, distributorPrice, 
    //            profitAfterDistributor, distributorMarginPercent, status }
  },
  
  // Get comprehensive pricing for a package
  getPackagePricing(packageId) {
    // Same structure, but calculates total cost from all products
    // Package discount applied independently (does NOT stack)
  },
  
  // Get margin data for all products
  getProductMargins() { /* ... */ },
  
  // Get margin data for all packages
  getPackageMargins() { /* ... */ },
  
  // Get combined comparison data
  getComparisonData(options) { /* sortBy: 'margin' | 'profit' | 'name' */ },
  
  // Get summary statistics
  getSummary() {
    // Returns: { averageMargin, blendedDistributorMargin, totalRevenue,
    //            totalProfit, totalDistributorRevenue, totalDistributorProfit,
    //            marginHealth: { good, warning, poor } }
  }
};
```

#### UI Components

**Margins View with Tabs**
- Products Tab: Table with material cost, labor cost, total cost, sale price, distributor %, distributor price, margin
- Packages Tab: Package-level pricing with product count, costs, margins
- Comparison Tab: Side-by-side horizontal bar chart

**Features**
- Toggle "Show Distributor Pricing" checkbox
- Sort comparison by margin %, profit $, or name
- Quick edit buttons open dedicated pricing modals
- Summary cards: blended margin, total profit, margin health distribution, best performer

**Pricing Modals**
- Product Pricing Modal: Edit sale price and distributor discount with live margin preview
- Package Pricing Modal: Edit package pricing with cost breakdown

#### Implementation Notes

1. **Load Order**: Pricing functions added to existing `Parts` module and `MarginAnalysis` module

2. **Backward Compatibility**: Products/packages without `salePrice` default to 0 (shows "Not Set")

3. **Validation**: 
   - `salePrice` must be >= 0
   - `distributorDiscount` must be 0-100 (clamped with Math.min/max)
   
4. **Dashboard Integration**: Margin section added to product/package detail views

5. **Margin Status Thresholds**:
   - Good: >= 30%
   - Warning: 15-30%
   - Poor: < 15%

6. **Non-Stacking Discount Logic**: When calculating package margins, use ONLY the package's `distributorDiscount`, ignoring any discounts set on individual products within the package

---

### Phase 20: Manufacturing Operations [NOT IMPLEMENTED]
**Timeline:** 6-8 Weeks  
**Theme:** Production facilities, work centers, routings, and manufacturing cost calculation
**Priority:** HIGH - Essential for accurate labor costing and production planning

#### Overview

This phase introduces comprehensive manufacturing operations capabilities to the PLM system. It enables modeling of production facilities, work centers with detailed cost structures, and production routings that define how parts are manufactured. Labor costs are automatically calculated based on routing operations rather than manual entry, providing accurate and auditable cost buildup.

#### Features

| ID | Feature | Description | Effort | Impact | Status |
|----|---------|-------------|--------|--------|--------|
| **20.1** | **Facility Management** | Create/edit manufacturing facilities with location, timezone, operating hours, and overhead rates | Medium | High | [NOT IMPLEMENTED] |
| **20.2** | **Facility Configuration** | Facility-specific settings: default currency, labor burden rate, overhead allocation method | Low | Medium | [NOT IMPLEMENTED] |
| **20.3** | **Work Center Registry** | Master list of work centers: ID, name, description, capability type, associated facility | Medium | High | [NOT IMPLEMENTED] |
| **20.4** | **Work Center Costing** | Setup labor time/cost, run labor rate ($/hr), machine rate ($/hr), overhead rate per work center | Medium | High | [NOT IMPLEMENTED] |
| **20.5** | **Work Center Capacity** | Capacity units/hour, efficiency %, availability hours/day, utilization tracking | Medium | Medium | [NOT IMPLEMENTED] |
| **20.6** | **Production Routing** | Define sequence of operations for manufactured parts (type MD); link routing to part | High | High | [NOT IMPLEMENTED] |
| **20.7** | **Routing Operations** | Each operation: sequence #, work center, setup time, run time/unit, description | High | High | [NOT IMPLEMENTED] |
| **20.8** | **Calculated Labor Cost** | Auto-calculate part labor cost from routing: SUM((setup + run*qty) * laborRate) | High | High | [NOT IMPLEMENTED] |
| **20.9** | **Alternative Routings** | Multiple routing options per part (e.g., standard vs. rush); select active routing | Medium | Medium | [NOT IMPLEMENTED] |
| **20.10** | **Operation Work Instructions** | Attach instructions, diagrams, or notes to individual operations | Low | Medium | [NOT IMPLEMENTED] |
| **20.11** | **Tooling Requirements** | Link required tools/fixtures to operations; track tool costs | Medium | Low | [NOT IMPLEMENTED] |
| **20.12** | **Quality Checkpoints** | Define inspection operations in routing with pass/fail criteria | Medium | Medium | [NOT IMPLEMENTED] |
| **20.13** | **Scrap & Yield Factors** | Expected scrap % per operation; affects quantity planning and cost | Low | Medium | [NOT IMPLEMENTED] |
| **20.14** | **Manufacturing Lead Time** | Auto-calculate lead time from routing (setup + run + queue + move times) | Medium | High | [NOT IMPLEMENTED] |
| **20.15** | **Queue & Move Times** | Configurable wait time before operation and move time to next work center | Low | Low | [NOT IMPLEMENTED] |
| **20.16** | **Routing Cost Breakdown** | Visual breakdown of labor, machine, and overhead costs per operation | Medium | High | [NOT IMPLEMENTED] |
| **20.17** | **Multi-Facility Routing** | Routing can span multiple facilities; track inter-facility transfer costs | Medium | Medium | [NOT IMPLEMENTED] |
| **20.18** | **Routing Version Control** | Revision history for routings; compare versions; effectivity dates | Medium | Medium | [NOT IMPLEMENTED] |
| **20.19** | **Manufacturing BOM (MBOM)** | Optional: Separate manufacturing BOM structure from engineering BOM | High | Medium | [DEFERRED] |
| **20.20** | **Phantom Assemblies** | Mark sub-assemblies as "phantom" (logical grouping, not physically built) | Low | Low | [DEFERRED] |

#### Data Schema

```javascript
// Facility schema
DB.facilities = [
  {
    id: 'fac-001',
    code: 'PLT-EAST',                    // Short identifier
    name: 'East Coast Manufacturing',
    address: '123 Industrial Blvd, Newark, NJ',
    timezone: 'America/New_York',
    status: 'active',                    // active | maintenance | decommissioned
    
    // Operating parameters
    operatingHours: {
      weekday: { start: '06:00', end: '22:00' },  // 2 shifts
      saturday: { start: '06:00', end: '14:00' },
      sunday: null                       // Closed
    },
    
    // Cost parameters
    currency: 'USD',
    laborBurdenRate: 35,                 // % added to labor for benefits, taxes
    facilityOverheadRate: 12.50,         // $/hour facility overhead
    overheadAllocationMethod: 'labor-hours',  // labor-hours | machine-hours | direct-labor-cost
    
    created: '2025-01-15T10:00:00Z',
    modified: '2025-03-20T14:30:00Z'
  }
];

// Work Center schema
DB.workCenters = [
  {
    id: 'wc-001',
    code: 'CNC-01',                       // Short identifier for routing display
    name: 'CNC Machining Center 1',
    description: '3-axis vertical milling',
    facilityId: 'fac-001',               // Parent facility
    status: 'available',                 // available | maintenance | offline
    
    // Capability classification
    capabilityType: 'machining',         // machining | assembly | welding | painting | 
                                         // testing | inspection | packaging | other
    capabilities: ['milling', 'drilling', 'tapping'],  // Specific capabilities
    
    // Time parameters (in minutes unless noted)
    defaultSetupTime: 30,                // Default setup if not specified in operation
    queueTime: 60,                       // Average wait time before processing
    moveTime: 15,                        // Time to move to next work center
    
    // Cost parameters
    laborRate: 45.00,                    // $/hour for operator labor
    laborHeadcount: 1,                   // Operators required
    machineRate: 85.00,                  // $/hour for machine time (depreciation, maintenance)
    overheadRate: 25.00,                 // $/hour work center specific overhead
    
    // Capacity parameters
    capacityUnitsPerHour: 12,            // Theoretical output
    efficiency: 85,                      // % of theoretical capacity typically achieved
    availableHoursPerDay: 16,            // Operating hours
    
    // Utilization tracking (calculated/updated)
    currentUtilization: 72,              // % current load
    
    created: '2025-01-15T10:00:00Z',
    modified: '2025-03-20T14:30:00Z'
  }
];

// Production Routing schema (linked to part)
part.routings = [
  {
    id: 'rtg-001',
    name: 'Standard Routing',
    revision: 'A',
    status: 'released',                  // draft | released | obsolete
    isActive: true,                      // Currently selected routing for costing
    effectiveDate: '2025-02-01',
    obsoleteDate: null,
    
    // Routing-level parameters
    lotSize: 100,                        // Standard lot size for time calculations
    notes: 'Primary manufacturing method',
    
    // Operations sequence
    operations: [
      {
        id: 'op-001',
        sequence: 10,                    // Operation sequence number
        workCenterId: 'wc-001',          // Link to work center
        workCenterCode: 'CNC-01',        // Denormalized for display
        name: 'Rough Machining',
        description: 'Machine rough profile from blank',
        
        // Time parameters (in minutes)
        setupTime: 45,                   // Fixed setup time
        runTimePerUnit: 8.5,             // Time per piece
        
        // Optional: Override work center rates for this operation
        laborRateOverride: null,         // null = use work center rate
        machineRateOverride: null,
        
        // Quality
        isInspectionPoint: false,
        inspectionCriteria: null,
        
        // Yield/Scrap
        expectedScrapPercent: 2,         // 2% expected scrap at this operation
        
        // Work instructions
        instructions: 'See drawing DWG-12345 for dimensions',
        attachments: [],                 // File references
        
        // Tooling
        toolingRequired: ['T-001', 'T-002'],  // Tool IDs
        
        // Calculated costs (computed, not stored)
        // calculatedLaborCost, calculatedMachineCost, calculatedOverhead
      }
    ]
  }
];

// Tooling registry
DB.tooling = [
  {
    id: 'T-001',
    code: 'EM-0.500-4FL',
    name: '1/2" 4-Flute End Mill',
    type: 'cutting',                     // cutting | holding | fixture | gauge
    cost: 45.00,                         // Tool cost for amortization
    expectedLife: 500,                   // Units before replacement
    currentUsage: 127,                   // Units processed
    status: 'active'                     // active | worn | replaced
  }
];
```

#### Calculation Formulas

```javascript
// Calculate operation cost (for 1 unit)
function calculateOperationCost(operation, workCenter, lotSize = 1) {
  const laborRate = operation.laborRateOverride || workCenter.laborRate;
  const machineRate = operation.machineRateOverride || workCenter.machineRate;
  const overheadRate = workCenter.overheadRate;
  
  // Time in hours
  const setupHours = operation.setupTime / 60;
  const runHours = (operation.runTimePerUnit * lotSize) / 60;
  const totalHours = setupHours + runHours;
  
  // Costs
  const laborCost = totalHours * laborRate * workCenter.laborHeadcount;
  const machineCost = totalHours * machineRate;
  const overheadCost = totalHours * overheadRate;
  
  // Per-unit cost (amortize setup across lot)
  const totalCost = laborCost + machineCost + overheadCost;
  const perUnitCost = totalCost / lotSize;
  
  return {
    laborCost: perUnitCost * (laborCost / totalCost),
    machineCost: perUnitCost * (machineCost / totalCost),
    overheadCost: perUnitCost * (overheadCost / totalCost),
    totalPerUnit: perUnitCost
  };
}

// Calculate routing total cost
function calculateRoutingCost(routing, lotSize = routing.lotSize) {
  let totalLabor = 0, totalMachine = 0, totalOverhead = 0;
  
  for (const op of routing.operations) {
    const workCenter = getWorkCenter(op.workCenterId);
    const opCost = calculateOperationCost(op, workCenter, lotSize);
    totalLabor += opCost.laborCost;
    totalMachine += opCost.machineCost;
    totalOverhead += opCost.overheadCost;
  }
  
  return {
    laborCost: totalLabor,
    machineCost: totalMachine,
    overheadCost: totalOverhead,
    totalPerUnit: totalLabor + totalMachine + totalOverhead
  };
}

// Calculate manufacturing lead time
function calculateLeadTime(routing, quantity, workCenters) {
  let totalMinutes = 0;
  
  for (const op of routing.operations) {
    const wc = workCenters[op.workCenterId];
    totalMinutes += wc.queueTime;           // Wait before processing
    totalMinutes += op.setupTime;            // Setup time
    totalMinutes += op.runTimePerUnit * quantity;  // Run time
    totalMinutes += wc.moveTime;             // Move to next
  }
  
  // Convert to working days (assuming 8-hour days)
  const workingDays = totalMinutes / 60 / 8;
  return Math.ceil(workingDays);
}
```

---

## Implementation Priority Order

### Sprint 1-6: Core Restoration (v15-v16) [DONE]
1. **Phase 13** - Visualization tab and all chart types
2. **Phase 14.1-14.4** - Schedule fields and modal
3. **Phase 14.5-14.6** - Schedule-aware Gantt and KPI
4. **Phase 14.7** - JIRA import
5. **Phase 15.1-15.3** - Drag & drop, priorities, tags
6. **Phase 15.4-15.7** - Bulk actions, archive, dependencies, dashboard

### Sprint 7-9: Collaboration (v17-v18) [DONE]
7. **Phase 16.1-16.3** - Comments and @mentions
8. **Phase 16.4-16.5** - Shareable links and HTML export
9. **Phase 17.1-17.8** - UX polish and project architecture

### Sprint 10-12: PLM Pricing [DONE]
10. **Phase 19.1, 19.2** - Product sale price and distributor discount fields
11. **Phase 19.3, 19.4** - Package sale price and distributor discount fields
12. **Phase 19.5** - Assembly labor cost roll-up fix
13. **Phase 19.6, 19.7** - Product and package margin dashboards
14. **Phase 19.8** - Margin comparison visualizations

### Sprint 13-18: Enhanced Budget Management [NEXT]
15. **Phase 18.1, 18.5, 18.6** - Budget overview, dashboard, categories
16. **Phase 18.3, 18.4** - Expense ledger and attachments
17. **Phase 18.2, 18.7** - CAPEX documents and alerts
18. **Phase 18.8, 18.9** - Approval workflow and forecasting
19. **Phase 18.10, 18.11, 18.12** - POs, vendors, enhanced export
20. **Phase 18.13, 18.14** - Multi-currency and expense notes

### Sprint 19-26: Manufacturing Operations [PLANNED]
21. **Phase 20.1, 20.2** - Facility management foundation
22. **Phase 20.3, 20.4, 20.5** - Work center registry and costing
23. **Phase 20.6, 20.7** - Production routing and operations
24. **Phase 20.8, 20.16** - Calculated labor cost and breakdown
25. **Phase 20.14, 20.15** - Lead time calculation
26. **Phase 20.9, 20.18** - Alternative routings and version control
27. **Phase 20.10, 20.11, 20.12** - Work instructions, tooling, QC
28. **Phase 20.13, 20.17** - Scrap/yield and multi-facility

---

## Success Metrics

| Metric | v1.0 | v15.0 | v16.0 | v17.0 | v18.0 | v19.0 | v54.0 (Current) | v55.0 (Target) | v56.0 (Target) |
|--------|------|-------|-------|-------|-------|-------|-----------------|----------------|----------------|
| Features implemented | 15 | 85 | 92 | 98 | 104 | 112 | 120 | 134 | 152 |
| Features working as claimed | - | 85 | 92 | 98 | 104 | 112 | 120 | 134 | 152 |
| Visualization views | 0 | 6 | 6 | 6 | 6 | 6 | 6 | 7 | 8 |
| Export formats | 2 | 6 | 6 | 6 | 7 | 7 | 7 | 8 | 9 |
| Schedule management | 0 | 0 | Full | Full | Full | Full | Full | Full | Full |
| Organization features | 0 | 0 | 0 | Full | Full | Full | Full | Full | Full |
| Collaboration features | 0 | 0 | 0 | 0 | Full | Full | Full | Full | Full |
| Budget management | Basic | Basic | Basic | Basic | Basic | Basic | Basic | **Enhanced** | Enhanced |
| Pricing & margin analysis | None | None | None | None | None | None | **Full** | Full | Full |
| Manufacturing operations | None | None | None | None | None | None | None | None | **Full** |
| Project architecture | Basic | Basic | Basic | Basic | Basic | Isolated | Isolated | Isolated | Isolated |
| Data loss incidents | Unknown | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| Accessibility score | Unknown | 75% | 75% | 75% | 75% | 75% | 75% | 80% | 80% |
| Load time (cold start) | ~1s | <1s | <1s | <1s | <1s | <1s | <1s | <1s | <1s |

---

## Appendix: Changelog

| Version | Date | Changes |
|---------|------|---------|
| 3.0 | Dec 20, 2025 | **v54 RELEASE**: Phase 19 complete - All PLM Pricing & Margin Analysis features implemented. Added product/package sale price and distributor discount fields. Fixed assembly labor cost roll-up to include labor from ALL BOM levels (intermediate sub-assemblies). New Parts module functions: getRolledUpCostWithLabor(), getRolledUpMaterialCost(), getRolledUpLaborCost(). Enhanced MarginAnalysis module with getProductPricing(), getPackagePricing(), getComparisonData(). New Margins view with Products/Packages/Comparison tabs. Toggle for distributor pricing visibility. Pricing modals with live margin preview. Summary cards showing blended margin, profit, margin health. Margin status thresholds: good (>=30%), warning (15-30%), poor (<15%). Package discounts do NOT stack with product discounts. Updated Success Metrics with v54 as current, moved Pricing & margin analysis to "Full" status. |
| 2.9 | Dec 20, 2025 | **ROADMAP UPDATE**: Added Phase 20 (Manufacturing Operations) with 20 features: Facility Management (multi-site support with timezone, operating hours, overhead rates), Facility Configuration, Work Center Registry (capability types, status tracking), Work Center Costing (setup/run labor rates, machine rates, overhead), Work Center Capacity (units/hour, efficiency, utilization), Production Routing (sequence of operations linked to parts), Routing Operations (setup time, run time/unit, work center assignment), Calculated Labor Cost (auto-calculate from routing replacing manual entry), Alternative Routings (multiple routing options per part), Operation Work Instructions, Tooling Requirements, Quality Checkpoints (inspection operations), Scrap & Yield Factors, Manufacturing Lead Time (auto-calculated from routing), Queue & Move Times, Routing Cost Breakdown (visual labor/machine/overhead breakdown), Multi-Facility Routing, Routing Version Control, Manufacturing BOM (deferred), Phantom Assemblies (deferred). Added comprehensive data schemas for facilities, work centers, routings, operations, and tooling. Added calculation formulas for routing costs and lead times. Added UI mockups for all views. Updated Implementation Priority with Sprint 24-31. Updated Success Metrics with v22 targets and new "Manufacturing operations" row. |
| 2.8 | Dec 20, 2025 | **ROADMAP UPDATE**: Added Phase 19 (PLM Pricing & Margin Analysis) with 9 features: Product Sale Price Field, Product Distributor Discount %, Package Sale Price Field, Package Distributor Discount %, Assembly Labor Cost Roll-up fix (addresses gap where labor costs on intermediate sub-assemblies were not included in cost roll-up), Product Margin Dashboard (Direct Margin, Margin %, Distributor Price, Profit After Distributor), Package Margin Dashboard (same metrics with non-stacking discount logic), Margin Comparison Visualizations, and Overhead Cost Field (deferred). Added data schema, calculation formulas, UI mockups. Updated Implementation Priority Order with Sprint 19-23. Updated Success Metrics with v21 targets and new "Pricing & margin analysis" row. Key clarification: package discounts do NOT stack with product discounts. |
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
