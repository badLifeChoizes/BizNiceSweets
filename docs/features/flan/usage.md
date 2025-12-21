# FLAN Usage

User workflows, UI descriptions, and example scenarios.

---

## User Experience Overview

FLAN provides project managers and team members with tools to plan, track, and complete projects. Users can create projects, break them into phases with subtasks, assign team members, log time, and monitor progress through dashboards and visualizations.

---

## Core Workflows

### Creating a New Project

**Goal:** Start tracking a new project with basic setup.

**Steps:**

1. Click "Projects" dropdown in the header
2. Click "New Project" button
3. Enter project name
4. Optionally set category
5. Project opens with empty phase list

**Result:** New project created with unique ID, ready for phases.

---

### Adding and Managing Phases

**Goal:** Break project into trackable work chunks.

**Steps:**

1. Click "Add Phase" button at bottom of phases list
2. Enter phase name in the inline input
3. Set start and due dates using date pickers
4. Assign priority (Low/Medium/High/Critical)
5. Add tags for categorization
6. Drag phases to reorder

**Result:** Phases appear in project, ready for progress tracking.

---

### Tracking Phase Progress

**Goal:** Update completion status as work progresses.

**Steps:**

1. Locate the phase in the phases list
2. Drag the progress slider (0-100%)
3. Or select status from dropdown (Pending/In Progress/Complete)
4. Progress updates reflect immediately in KPIs

**Result:** Project dashboard updates with new progress metrics.

---

### Managing Subtasks

**Goal:** Create detailed checklists within phases.

**Steps:**

1. Click expand button on a phase
2. Click "Add Subtask" in expanded area
3. Enter subtask description
4. Optionally add JIRA key, dates
5. Click checkbox to mark complete

**Result:** Subtask completion tracked, visible in phase card.

---

### Assigning Team Members

**Goal:** Track who is working on what.

**Steps:**

1. Go to Team tab or click assignee avatars on a phase
2. Add new team member with name, role, hourly rate
3. Click "+" avatar on phase to assign members
4. Select team members from dropdown
5. Multiple members can be assigned per phase

**Result:** Team workload visible in Team tab, assignees shown on phases.

---

### Logging Time

**Goal:** Record hours worked for labor cost tracking.

**Steps:**

1. Go to Budget tab or click time icon on a phase
2. Click "Log Time" button
3. Select phase and team member
4. Enter date, hours, and notes
5. Save time entry

**Result:** Time entry recorded, labor costs updated in budget summary.

---

### Tracking Deliverables

**Goal:** Monitor key delivery dates with urgency indicators.

**Steps:**

1. Go to Deliverables section (Dashboard tab)
2. Click "Add Deliverable"
3. Enter title, target date, destination
4. Delivery shows countdown to due date
5. Color-coded urgency (red = overdue, yellow = soon)

**Result:** Upcoming deliveries visible with automatic urgency tracking.

---

### Managing Project Budget

**Goal:** Set budget and track expenses against it.

**Steps:**

1. Go to Budget tab
2. Click settings to set total budget, fiscal year
3. Add expenses with category, amount, vendor reference
4. View burn rate and variance
5. Receive alerts at threshold levels (75%, 90%)

**Result:** Budget health visible with spending vs budget comparison.

---

### Using Timeline/Gantt View

**Goal:** Visualize project schedule with date-aware chart.

**Steps:**

1. Go to Timeline tab
2. View phases as horizontal bars by date
3. Dependencies shown as connecting lines
4. Scroll horizontally to navigate timeline
5. Click phase bar to edit details

**Result:** Visual schedule showing phase overlaps and dependencies.

---

### Exporting Project Data

**Goal:** Backup or share project information.

**Steps:**

1. Click Export dropdown in header
2. Select format: JSON, CSV, Excel, PDF, or ICS
3. File downloads with project data
4. JSON preserves full structure for backup/restore

**Result:** Project data exported in selected format.

---

## UI Components

### Header Bar

**Location:** Top of application

**Purpose:** Project selection, global actions, quick access

**Key Elements:**

- Logo and app name
- Project selector dropdown with search
- Import/Export buttons
- Theme toggle
- Undo/Redo buttons
- Save indicator

---

### KPI Dashboard

**Location:** Top of main content area

**Purpose:** At-a-glance project health metrics

**Key Elements:**

- Total phases count
- Complete/In Progress/Pending counts
- Overall progress percentage
- Budget utilization
- Upcoming deliveries count

---

### Phases List

**Location:** Main content area, Phases tab

**Purpose:** Manage all project phases

**Key Elements:**

- Drag handle for reordering
- Phase label (P1, P2, etc.)
- Phase name (editable inline)
- Progress slider (0-100%)
- Status dropdown
- Date range display
- Assignee avatars
- Subtask count badge
- Delete button

---

### Phase Detail (Expanded)

**Location:** Below phase card when expanded

**Purpose:** Subtask management and phase details

**Key Elements:**

- Subtask list with checkboxes
- JIRA key display
- Due date indicators
- Add subtask button
- Comments section

---

### Team Grid

**Location:** Team tab

**Purpose:** Manage project team members

**Key Elements:**

- Team member cards with avatar
- Name, role, email
- Hourly rate
- Edit/Delete buttons
- Workload summary

---

### Budget Overview Panel

**Location:** Budget tab

**Purpose:** Financial tracking and budget management

**Key Elements:**

- Total budget with fiscal year
- Approval status badge
- Progress bar (spent vs budget)
- Stats grid (Spent, Committed, Available)
- Burn rate indicator
- Expense category breakdown

---

### Timeline View

**Location:** Timeline tab

**Purpose:** Gantt-style schedule visualization

**Key Elements:**

- Date axis (horizontal)
- Phase bars (sized by duration)
- Today marker line
- Dependency arrows
- Phase tooltips on hover

---

## Example Scenarios

### Scenario: New Product Development Project

**Context:** Starting a 6-month project to develop a new product with design, prototyping, and testing phases.

**User Actions:**

1. Create project "Product X Development"
2. Add phases: "Requirements", "Design", "Prototype", "Testing", "Launch"
3. Set phase dependencies (each depends on previous)
4. Add team members: PM, 2 Engineers, Designer
5. Assign engineers to Design and Prototype phases
6. Set budget at $150,000
7. Create milestone "Prototype Complete" at 3-month mark

**Expected Outcome:** Project visible in dashboard with timeline showing 6-month schedule, team workload distributed, budget tracking ready.

---

### Scenario: Weekly Status Update

**Context:** Team lead reviewing project progress for weekly meeting.

**User Actions:**

1. Open project dashboard
2. Review KPIs (phases complete, overall progress)
3. Check Timeline for any overdue phases (red indicators)
4. Review upcoming deliveries
5. Check Budget tab for spending vs estimates
6. Export PDF report for stakeholders

**Expected Outcome:** Clear view of project health, any issues highlighted, report ready to share.

---

### Scenario: Logging Weekly Time

**Context:** Team member logging their hours for the week.

**User Actions:**

1. Open project, go to Budget tab
2. Click "Log Time"
3. Select phase they worked on
4. Enter date, hours (e.g., 8 hours)
5. Add notes describing work done
6. Repeat for each work day/phase
7. View total hours in summary

**Expected Outcome:** Time entries recorded, labor costs updated, visible in budget rollup.

---

## Edge Cases

| Situation | Expected Behavior |
|-----------|-------------------|
| Deleting a phase with subtasks | Subtasks deleted with phase (cascade) |
| Deleting team member with time entries | Time entries preserved, member removed from assignees |
| Setting due date before start date | Validation error, prevent save |
| Progress set to 100% but status not complete | Status auto-updated to "Complete" |
| Circular phase dependency | Validation error, prevent save |
| Budget exceeded (over 100%) | Alert displayed, progress bar shows overage |
| Overdue delivery date | Red urgency indicator, appears in alerts panel |
| Empty project (no phases) | Empty state with "Add Phase" prompt |

---

## Keyboard Shortcuts (Prototype)

| Shortcut | Action |
|----------|--------|
| `Ctrl/Cmd + N` | New phase |
| `Ctrl/Cmd + S` | Force save |
| `Ctrl/Cmd + Z` | Undo |
| `Ctrl/Cmd + Shift + Z` | Redo |
| `Ctrl/Cmd + E` | Export JSON |
| `Escape` | Close modal/dropdown |

---

## Accessibility Notes

- All interactive elements keyboard-accessible
- Progress sliders can be adjusted with arrow keys
- Color-coded status has text labels as well
- High-contrast mode via theme toggle
- Screen reader friendly labels on buttons and inputs