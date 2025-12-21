# FLAN Invariants

Rules that must ALWAYS be true. Violating any of these breaks the feature.

**Read this entire file before implementing any FLAN-related code.**

---

## Project Identity

| Rule | If You Break It |
|------|-----------------|
| Every project MUST have a unique UUID | Data corruption, duplicate key errors |
| Project names CAN be duplicated | N/A (allowed) |
| Project IDs are immutable after creation | Foreign key references break, data orphaned |
| Archived projects MUST retain all data | Historical records lost, reports incorrect |

**Implementation:** `src/modules/flan/models.py` → `Project`

---

## Phase Management

| Rule | If You Break It |
|------|-----------------|
| Phase progress MUST be 0-100 inclusive | UI breaks, calculations wrong |
| Phase status MUST be one of: pending, in-progress, complete | State machine fails |
| Phases MUST belong to exactly one project | Orphaned data, query failures |
| Phase deletion MUST cascade to subtasks | Orphaned subtasks pollute database |
| Phase dependencies CANNOT be circular | Infinite loops, deadlocks |

**Implementation:** `src/modules/flan/models.py` → `Phase`

---

## Subtask Rules

| Rule | If You Break It |
|------|-----------------|
| Subtasks MUST belong to exactly one phase | Orphaned subtasks |
| Subtask completed state is boolean only | UI checkbox breaks |
| Subtask deletion does NOT affect phase progress | Phase progress is slider-based, not subtask-based |

**Implementation:** `src/modules/flan/models.py` → `Subtask`

---

## Time Entry Integrity

| Rule | If You Break It |
|------|-----------------|
| Time entry hours MUST be positive | Negative labor costs, reports wrong |
| Time entries MUST have a valid date | Sorting, filtering breaks |
| Time entries SHOULD reference a phase | Cost roll-up by phase fails |
| Time entries SHOULD reference a team member | Labor cost calculation fails |
| Deleting a team member MUST NOT delete their time entries | Historical data lost |

**Implementation:** `src/modules/flan/models.py` → `TimeEntry`

---

## Budget & Expense Rules

| Rule | If You Break It |
|------|-----------------|
| Budget amounts MUST be non-negative | Financial reports wrong |
| Expense amounts MUST be positive | Ledger corrupted |
| Budget approval status MUST follow state machine | Invalid workflow states |
| Expense status MUST be one of: pending, approved, rejected, reimbursed | Status tracking breaks |
| Phase budget estimates are independent of actual expenses | Estimates become unreliable |

**Implementation:** `src/modules/flan/models.py` → `BudgetSettings`, `Expense`

---

## Team Member Rules

| Rule | If You Break It |
|------|-----------------|
| Team members CAN have the same name | N/A (allowed for duplicate names) |
| Hourly rate MUST be non-negative | Labor cost calculations wrong |
| Deleting a team member MUST NOT cascade to time entries | Historical data lost |
| Deleting a team member MUST remove them from phase assignees | Orphan references in UI |

**Implementation:** `src/modules/flan/models.py` → `TeamMember`

---

## Delivery Rules

| Rule | If You Break It |
|------|-----------------|
| Deliveries MUST belong to exactly one project | Orphaned deliveries |
| Delivery dates CAN be in the past | Valid for tracking completed deliveries |
| Delivery status MUST follow state machine | Invalid workflow states |

**Implementation:** `src/modules/flan/models.py` → `Delivery`

---

## Risk & Governance Rules

| Rule | If You Break It |
|------|-----------------|
| Risk impact/probability MUST use defined levels | Risk matrix calculations fail |
| Milestones MUST have a date | Timeline views break |
| Decisions MUST have a status | Decision log filtering fails |

**Implementation:** `src/modules/flan/models.py` → `Risk`, `Milestone`, `Decision`

---

## Data Persistence Rules

| Rule | If You Break It |
|------|-----------------|
| All timestamps MUST be ISO 8601 format | Parsing errors, timezone issues |
| All UUIDs MUST be valid UUID format | Key lookups fail |
| Project modified timestamp MUST update on any change | Sync detection fails |
| Soft-delete (archive) MUST NOT physically remove data | Data recovery impossible |

**Implementation:** All models, database constraints

---

## Cross-Module Integration

| Rule | If You Break It |
|------|-----------------|
| FLAN MUST NOT directly modify SYERP data | Data ownership violations |
| Vendor references MUST validate against SYERP | Invalid FK references |
| User references MUST validate against Core | Invalid FK references |
| Project links to PLUM are optional, not required | Standalone project use blocked |

**Implementation:** Integration services

---

## Quick Reference

**Total invariants:** 31

**Most critical:**

1. Phase progress must be 0-100 inclusive
2. Phase dependencies cannot be circular
3. Time entry hours must be positive
4. Budget/expense amounts must be valid numbers
5. Deleting team members must not delete time entries

**Common violations to watch for:**

- Setting progress outside 0-100 range
- Creating circular phase dependencies
- Negative time entries (corrections should be separate entries)
- Orphaning subtasks when deleting phases without cascade
- Modifying archived project data (should be read-only)
- Direct writes to SYERP tables from FLAN code

---

## Validation Checklist

Before any FLAN commit:

- [ ] Progress values validated (0-100)?
- [ ] Status values from allowed enum?
- [ ] Time entry hours positive?
- [ ] Budget amounts non-negative?
- [ ] Circular dependency check for phases?
- [ ] Cascade rules correct for deletions?
- [ ] Timestamps in ISO 8601 format?
- [ ] Cross-module access through APIs only?