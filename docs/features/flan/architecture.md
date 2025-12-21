# FLAN Architecture

Data models, state machines, events, and APIs.

---

## Data Model Overview

```text
Project
├── id: string (UUID)
├── name: string
├── category: string
├── created: datetime
├── modified: datetime
├── phases: Phase[]
├── deliveries: Delivery[]
├── notes: ProjectNotes
├── team: TeamMember[]
├── timeEntries: TimeEntry[]
├── budget: BudgetSettings
├── expenses: Expense[]
├── risks: Risk[]
├── milestones: Milestone[]
├── decisions: Decision[]
└── recurringTemplates: RecurringTemplate[]
```

---

## Core Entities

### Project

The top-level container for all project data.

```typescript
Project
├── id: string                    // UUID, primary key
├── name: string                  // Project title
├── category: string              // Project category/type
├── created: datetime             // ISO 8601 timestamp
├── modified: datetime            // Last modification time
├── phases: Phase[]               // List of phases/epics
├── deliveries: Delivery[]        // Key deliverables
├── notes: ProjectNotes           // Markdown notes sections
├── team: TeamMember[]            // Project team members
├── timeEntries: TimeEntry[]      // Time logged against phases
├── budget: BudgetSettings        // Budget configuration
├── expenses: Expense[]           // Project expenses
├── risks: Risk[]                 // Risk register
├── milestones: Milestone[]       // Key milestone dates
├── decisions: Decision[]         // Decision log
└── recurringTemplates: Template[]// Reusable phase templates
```

| Field | Type | Description |
|-------|------|-------------|
| `id` | `string` | UUID generated on creation |
| `name` | `string` | User-visible project name |
| `category` | `string` | Optional category for grouping |
| `phases` | `Phase[]` | Ordered list of project phases |
| `budget` | `BudgetSettings` | CAPEX and budget configuration |

---

### Phase

A major work chunk within a project.

```typescript
Phase
├── id: string                    // UUID
├── label: string                 // Phase code (e.g., "P1", "P2")
├── name: string                  // Phase title
├── progress: number              // 0-100 percentage
├── status: PhaseStatus           // pending | in-progress | complete
├── startDate: date               // Planned start
├── dueDate: date                 // Planned end
├── actualStart: date             // Actual start (optional)
├── actualEnd: date               // Actual completion (optional)
├── priority: Priority            // low | medium | high | critical
├── tags: string[]                // Labels/tags
├── subtasks: Subtask[]           // Checklist items
├── assignees: string[]           // Team member IDs
├── dependencies: string[]        // IDs of predecessor phases
├── comments: Comment[]           // Discussion thread
├── budgetEstimate: number        // Estimated cost
└── budgetActual: number          // Actual cost
```

| Field | Type | Description |
|-------|------|-------------|
| `progress` | `number` | 0-100, used for progress bar |
| `status` | `enum` | Workflow state |
| `dependencies` | `string[]` | Phase IDs that must complete first |
| `subtasks` | `Subtask[]` | Nested checklist items |

---

### Subtask

A checklist item within a phase.

```typescript
Subtask
├── id: string                    // UUID
├── name: string                  // Task description
├── completed: boolean            // Checkbox state
├── jiraKey: string               // Optional JIRA ticket reference
├── startDate: date               // Optional start date
├── dueDate: date                 // Optional due date
└── assignee: string              // Optional team member ID
```

---

### Delivery

A key deliverable with a target date.

```typescript
Delivery
├── id: string                    // UUID
├── title: string                 // Deliverable name
├── date: date                    // Target delivery date
├── destination: string           // Where/to whom delivered
├── status: DeliveryStatus        // pending | in-progress | complete
├── linkedPhases: string[]        // Associated phase IDs
└── notes: string                 // Additional details
```

---

### TeamMember

A person assigned to the project.

```typescript
TeamMember
├── id: string                    // UUID
├── name: string                  // Display name
├── role: string                  // Job title/role
├── email: string                 // Contact email
├── avatarColor: string           // Hex color for avatar
├── hourlyRate: number            // Rate for cost calculations
└── userId: string                // FK to Core.users (future)
```

---

### TimeEntry

Hours logged by a team member.

```typescript
TimeEntry
├── id: string                    // UUID
├── phaseId: string               // FK to Phase
├── teamMemberId: string          // FK to TeamMember
├── date: date                    // Date of work
├── hours: number                 // Hours worked
├── notes: string                 // Work description
└── billable: boolean             // Whether billable
```

---

### BudgetSettings

Project-level budget configuration.

```typescript
BudgetSettings
├── totalBudget: number           // Total CAPEX budget
├── fiscalYear: string            // Fiscal year (e.g., "FY25")
├── approvalStatus: ApprovalStatus// draft | pending | approved | rejected
├── contingencyPercent: number    // Contingency buffer percentage
├── currencyCode: string          // Currency (e.g., "USD")
└── alertThresholds: Thresholds   // Warning thresholds (75%, 90%)
```

---

### Expense

A project expense entry.

```typescript
Expense
├── id: string                    // UUID
├── category: ExpenseCategory     // labor | materials | equipment | services | travel | other
├── description: string           // What was purchased
├── amount: number                // Cost in project currency
├── date: date                    // Date of expense
├── status: ExpenseStatus         // pending | approved | rejected | reimbursed
├── phaseId: string               // FK to Phase (optional mapping)
├── vendorId: string              // FK to SYERP.vendors (future)
├── poNumber: string              // Reference to Purchase Order
└── receipts: Attachment[]        // Attached receipt files
```

---

### Risk

A project risk register entry.

```typescript
Risk
├── id: string                    // UUID
├── title: string                 // Risk description
├── impact: ImpactLevel           // low | medium | high | critical
├── probability: ProbabilityLevel // unlikely | possible | likely | certain
├── status: RiskStatus            // open | mitigating | resolved | accepted
├── mitigation: string            // Mitigation plan
├── owner: string                 // Team member ID responsible
└── dueDate: date                 // Target resolution date
```

---

### Milestone

A key project milestone.

```typescript
Milestone
├── id: string                    // UUID
├── title: string                 // Milestone name
├── date: date                    // Target date
├── status: MilestoneStatus       // upcoming | achieved | missed
└── linkedPhases: string[]        // Associated phase IDs
```

---

### Decision

A decision log entry.

```typescript
Decision
├── id: string                    // UUID
├── title: string                 // Decision topic
├── date: date                    // Decision date
├── status: DecisionStatus        // pending | decided | deferred
├── outcome: string               // What was decided
├── rationale: string             // Why this decision
└── participants: string[]        // Team member IDs involved
```

---

## State Machines

### Phase Status

```text
pending ──[Start Work]──► in-progress ──[Complete]──► complete
                               │
                         [Re-open]
                               │
                               ▼
                           pending
```

| State | Description | Allowed Actions |
|-------|-------------|-----------------|
| **pending** | Work not started | Start, Edit, Delete |
| **in-progress** | Actively being worked | Update progress, Complete, Re-open |
| **complete** | Work finished | Re-open, Archive |

### Transitions

| From | To | Trigger | Side Effects |
|------|-----|---------|--------------|
| pending | in-progress | Start Work | Sets actualStart if empty |
| in-progress | complete | Complete | Sets progress to 100%, sets actualEnd |
| complete | pending | Re-open | Clears actualEnd, resets progress |

---

### Delivery Status

```text
pending ──[Begin]──► in-progress ──[Deliver]──► complete
```

### Budget Approval Status

```text
draft ──[Submit]──► pending ──[Approve]──► approved
                       │
                  [Reject]
                       │
                       ▼
                   rejected
```

---

## Events

| Event | Payload | When Emitted |
|-------|---------|--------------|
| `project:created` | `{ projectId, name }` | New project created |
| `project:updated` | `{ projectId, changes }` | Project modified |
| `phase:created` | `{ projectId, phaseId, name }` | Phase added |
| `phase:progress` | `{ phaseId, oldProgress, newProgress }` | Progress slider changed |
| `phase:status_change` | `{ phaseId, oldStatus, newStatus }` | Status transitioned |
| `subtask:toggled` | `{ phaseId, subtaskId, completed }` | Subtask checkbox changed |
| `time:logged` | `{ phaseId, teamMemberId, hours }` | Time entry added |
| `expense:added` | `{ projectId, expenseId, amount }` | Expense recorded |
| `budget:alert` | `{ projectId, threshold, current }` | Budget threshold exceeded |

---

## API Endpoints (Planned)

### Projects

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/flan/projects` | List all projects |
| POST | `/api/flan/projects` | Create project |
| GET | `/api/flan/projects/{id}` | Get project details |
| PUT | `/api/flan/projects/{id}` | Update project |
| DELETE | `/api/flan/projects/{id}` | Delete project |

### Phases

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/flan/projects/{id}/phases` | List phases |
| POST | `/api/flan/projects/{id}/phases` | Create phase |
| PUT | `/api/flan/phases/{id}` | Update phase |
| DELETE | `/api/flan/phases/{id}` | Delete phase |
| POST | `/api/flan/phases/{id}/subtasks` | Add subtask |

### Time Entries

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/flan/projects/{id}/time-entries` | List time entries |
| POST | `/api/flan/time-entries` | Log time |
| PUT | `/api/flan/time-entries/{id}` | Update entry |
| DELETE | `/api/flan/time-entries/{id}` | Delete entry |

### Budget & Expenses

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/flan/projects/{id}/budget` | Get budget details |
| PUT | `/api/flan/projects/{id}/budget` | Update budget settings |
| GET | `/api/flan/projects/{id}/expenses` | List expenses |
| POST | `/api/flan/expenses` | Add expense |

---

## Database Schema (PostgreSQL)

```sql
-- Projects
CREATE TABLE flan_projects (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    category VARCHAR(100),
    notes JSONB DEFAULT '{}',
    budget_settings JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by UUID REFERENCES core_users(id),
    is_archived BOOLEAN DEFAULT FALSE
);

-- Phases
CREATE TABLE flan_phases (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES flan_projects(id) ON DELETE CASCADE,
    label VARCHAR(20),
    name VARCHAR(255) NOT NULL,
    progress INTEGER DEFAULT 0 CHECK (progress >= 0 AND progress <= 100),
    status VARCHAR(20) DEFAULT 'pending',
    priority VARCHAR(20) DEFAULT 'medium',
    start_date DATE,
    due_date DATE,
    actual_start DATE,
    actual_end DATE,
    budget_estimate DECIMAL(12,2),
    budget_actual DECIMAL(12,2),
    sort_order INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Subtasks
CREATE TABLE flan_subtasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    phase_id UUID NOT NULL REFERENCES flan_phases(id) ON DELETE CASCADE,
    name VARCHAR(500) NOT NULL,
    completed BOOLEAN DEFAULT FALSE,
    jira_key VARCHAR(50),
    start_date DATE,
    due_date DATE,
    assignee_id UUID,
    sort_order INTEGER DEFAULT 0
);

-- Team Members
CREATE TABLE flan_team_members (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES flan_projects(id) ON DELETE CASCADE,
    user_id UUID REFERENCES core_users(id),
    name VARCHAR(255) NOT NULL,
    role VARCHAR(100),
    email VARCHAR(255),
    avatar_color VARCHAR(7),
    hourly_rate DECIMAL(10,2)
);

-- Time Entries
CREATE TABLE flan_time_entries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES flan_projects(id) ON DELETE CASCADE,
    phase_id UUID REFERENCES flan_phases(id) ON DELETE SET NULL,
    team_member_id UUID REFERENCES flan_team_members(id) ON DELETE SET NULL,
    entry_date DATE NOT NULL,
    hours DECIMAL(5,2) NOT NULL CHECK (hours > 0),
    notes TEXT,
    billable BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Deliveries
CREATE TABLE flan_deliveries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES flan_projects(id) ON DELETE CASCADE,
    title VARCHAR(255) NOT NULL,
    target_date DATE,
    destination VARCHAR(255),
    status VARCHAR(20) DEFAULT 'pending',
    notes TEXT
);

-- Expenses (maps to phases, references SYERP vendors)
CREATE TABLE flan_expenses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES flan_projects(id) ON DELETE CASCADE,
    phase_id UUID REFERENCES flan_phases(id) ON DELETE SET NULL,
    category VARCHAR(50) NOT NULL,
    description VARCHAR(500),
    amount DECIMAL(12,2) NOT NULL,
    expense_date DATE NOT NULL,
    status VARCHAR(20) DEFAULT 'pending',
    vendor_id UUID, -- FK to syerp_vendors when integrated
    po_number VARCHAR(50),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Phase Assignees (many-to-many)
CREATE TABLE flan_phase_assignees (
    phase_id UUID NOT NULL REFERENCES flan_phases(id) ON DELETE CASCADE,
    team_member_id UUID NOT NULL REFERENCES flan_team_members(id) ON DELETE CASCADE,
    PRIMARY KEY (phase_id, team_member_id)
);

-- Phase Dependencies (many-to-many)
CREATE TABLE flan_phase_dependencies (
    phase_id UUID NOT NULL REFERENCES flan_phases(id) ON DELETE CASCADE,
    depends_on_id UUID NOT NULL REFERENCES flan_phases(id) ON DELETE CASCADE,
    PRIMARY KEY (phase_id, depends_on_id),
    CHECK (phase_id != depends_on_id)
);

-- Indexes
CREATE INDEX idx_flan_phases_project ON flan_phases(project_id);
CREATE INDEX idx_flan_phases_status ON flan_phases(status);
CREATE INDEX idx_flan_time_entries_date ON flan_time_entries(entry_date);
CREATE INDEX idx_flan_expenses_project ON flan_expenses(project_id);
```

---

## Key Implementation Files (Future)

| Component | Location |
|-----------|----------|
| Models | `src/modules/flan/models.py` |
| Schemas | `src/modules/flan/schemas.py` |
| Routes | `src/modules/flan/routes.py` |
| Services | `src/modules/flan/services/` |
| Frontend Views | `src/frontend/modules/flan/` |
| Tests | `tests/modules/flan/` |