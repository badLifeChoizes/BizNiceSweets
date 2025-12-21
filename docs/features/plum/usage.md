# PLUM Usage

User workflows, UI descriptions, and example scenarios.

---

## User Experience Overview

PLUM enables a single product owner to manage their entire product catalog:

- Create and organize parts with part numbers and revisions
- Build multi-level Bills of Materials
- Track which vendors can supply each part
- Set pricing and analyze profit margins
- Import/export data for backup and migration

---

## Core Workflows

### Creating a New Part

**Goal:** Add a new component to the product catalog

**Steps:**

1. Click **+ New Part** or press `Ctrl+N`
2. Enter part number (or let system auto-generate)
3. Fill in name, description, type, and class
4. Set unit cost and labor cost if known
5. Click **Save** - part is created in Draft status

**Result:** New part appears in parts list, ready for BOM assignment

---

### Building a BOM (Bill of Materials)

**Goal:** Define what parts make up an assembly

**Steps:**

1. Open the parent assembly part
2. Navigate to **BOM** tab
3. Click **+ Add Component**
4. Search for and select child part
5. Enter quantity and optional reference designator
6. Repeat for all components
7. View **BOM Tree** for hierarchy or **Flat BOM** for totals

**Result:** Assembly now has a complete BOM with cost roll-up calculated

---

### Checking Where-Used

**Goal:** See which products use a specific part before making changes

**Steps:**

1. Open the part in question
2. Navigate to **Where-Used** tab
3. View the tree of parent assemblies
4. Expand nodes to see full impact chain

**Result:** Understand change impact before modifying or obsoleting a part

---

### Managing Approved Vendors

**Goal:** Track which vendors can supply a purchased part

**Steps:**

1. Open a purchased part (type = PUR)
2. Navigate to **AVL** tab
3. Click **+ Add Vendor**
4. Select vendor from SYERP list
5. Enter vendor part number, lead time, price
6. Set status (Approved, Preferred, Conditional, etc.)

**Result:** Part has approved sourcing options visible

---

### Releasing a Part

**Goal:** Lock a part for production use

**Steps:**

1. Open the Draft part
2. Verify BOM is complete (if assembly)
3. Verify costs are set
4. Click **Release** button
5. Confirm in dialog

**Result:** Part status changes to Released, editing is disabled

---

### Creating a New Revision

**Goal:** Make changes to a released part

**Steps:**

1. Open the Released part
2. Click **Revise** button
3. System creates copy with next revision letter (B, C, etc.)
4. Edit the new Draft revision
5. Release when ready

**Result:** New revision available, previous revision remains for reference

---

### Setting Pricing and Viewing Margins

**Goal:** Establish sale price and analyze profitability

**Steps:**

1. Open a product (top-level assembly)
2. Navigate to **Pricing** section
3. Enter sale price
4. Optionally set distributor discount %
5. View calculated margins in dashboard:
   - Total cost (rolled up)
   - Direct margin
   - Margin percentage
   - Distributor price and profit

**Result:** Clear visibility into product profitability

---

### Exporting Data

**Goal:** Backup the entire database

**Steps:**

1. Click **Export** in toolbar
2. Select format (JSON recommended for full backup)
3. Choose location and filename
4. Click **Save**

**Result:** Complete database exported to file

---

### Importing Data

**Goal:** Restore from backup or bulk-load parts

**Steps:**

1. Click **Import** in toolbar
2. Select file (JSON or Excel)
3. Preview import data
4. Resolve any conflicts (duplicate part numbers)
5. Click **Import**

**Result:** Data loaded into database

---

## UI Components

### Parts List

**Location:** Main view, left panel

**Purpose:** Browse and search all parts

**Key Elements:**

- Search bar with advanced syntax (`status:Released type:ASM`)
- Column headers for sorting
- Part number, name, revision, status columns
- Click to select, double-click to open detail

---

### Part Detail View

**Location:** Main view, right panel (or modal)

**Purpose:** View and edit part information

**Key Elements:**

- Header with part number, revision, status badge
- Tabs: General, BOM, Where-Used, AVL, Substitutes, Pricing
- Edit button (Draft parts only)
- Release/Revise/Obsolete action buttons

---

### BOM Tree View

**Location:** Part Detail > BOM tab

**Purpose:** Visualize product structure

**Key Elements:**

- Expandable/collapsible tree nodes
- Quantity at each level
- Rolled-up cost displayed
- Drag to reorder (sequence)

---

### Margins Dashboard

**Location:** Part Detail > Pricing tab

**Purpose:** Analyze profitability

**Key Elements:**

- Cost breakdown (material, labor)
- Sale price input
- Distributor discount input
- Calculated margins with visual indicators
- Comparison charts across products

---

### Command Palette

**Location:** Overlay, triggered by `Ctrl+K`

**Purpose:** Quick navigation and actions

**Key Elements:**

- Search for parts by number or name
- Quick actions (New Part, Export, etc.)
- Recent items list

---

## Example Scenarios

### Scenario: New Product Development

**Context:** Launching a new medical training simulator model

**User Actions:**

1. Create top-level assembly part (type ASM)
2. Create or find component parts
3. Build BOM with quantities
4. Add vendors to AVL for purchased parts
5. Set labor costs for manufactured parts
6. Set sale price and review margins
7. Release when design is finalized

**Expected Outcome:** Complete product definition with accurate costing

---

### Scenario: Part Change Impact Analysis

**Context:** Vendor discontinuing a component

**User Actions:**

1. Open the affected part
2. Go to Where-Used tab
3. See all products using this part
4. Evaluate substitutes (Substitutes tab)
5. If no substitute: create new part, update BOMs
6. Obsolete the old part

**Expected Outcome:** Smooth transition with documented impact

---

### Scenario: Cost Reduction Analysis

**Context:** Looking to improve margins

**User Actions:**

1. Go to Margins view (all products)
2. Sort by margin % to find low performers
3. Open product with lowest margin
4. Drill into BOM to find high-cost components
5. Check AVL for alternative vendors with lower prices
6. Use cost simulator for what-if analysis

**Expected Outcome:** Identified cost reduction opportunities

---

## Edge Cases

| Situation | Expected Behavior |
|-----------|-------------------|
| Delete part used in BOM | Error: "Part is used in X assemblies" |
| Circular BOM reference | Error: "Circular reference detected" |
| Release part with no BOM | Warning (optional): "No BOM defined" |
| Import duplicate part number | Prompt: Skip, Overwrite, or Rename |
| Vendor deleted in SYERP | AVL entry marked as orphaned, warning shown |
| Zero quantity in BOM | Error: "Quantity must be greater than 0" |

---

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl+K` | Open command palette |
| `Ctrl+N` | New part |
| `Ctrl+S` | Save current part |
| `Ctrl+F` | Focus search |
| `Esc` | Close modal/panel |