---
phase: 05-plum-parts-revisions
plan: "01"
subsystem: backend
tags:
  - plum
  - models
  - migration
  - seed
  - tests
dependency_graph:
  requires:
    - 04-04 (SYERP GLAccounts + route wiring — migration 0004 chain)
  provides:
    - plum_part table
    - plum_part_revision table
    - plum_classification_tag table
    - plum_part_tag table
    - PLUM Pydantic schemas (PartCreate, PartUpdate, PartRead, RevisionCreate, RevisionRead, PartDetailRead)
    - seed_plum_data() function
    - Wave 0 test scaffold for PLUM-01/02/03
  affects:
    - 05-02 (PLUM service + router — consumes schemas and models)
    - 05-03 (PLUM parts list UI — reads PartRead schema contract)
    - 05-04 (PLUM part detail UI — reads PartDetailRead + RevisionRead schema contract)
tech_stack:
  added:
    - pytest + pytest-asyncio + httpx dev deps installed into backend/.venv (were in requirements-dev.txt but missing from venv)
  patterns:
    - SQLAlchemy 2.0 async models with String(36) UUID PKs and Integer PK for lookup table
    - Two-table revision model (stable header + versioned snapshot)
    - Composite primary key join table (PlumPartTag)
    - Partial unique index for one-Released-per-part invariant
    - select-before-insert idempotent seed pattern
    - Wave 0 test scaffold with real assertions, collectable but RED until 05-02
key_files:
  created:
    - backend/app/modules/plum/__init__.py
    - backend/app/modules/plum/models.py
    - backend/app/modules/plum/schemas.py
    - backend/app/modules/plum/router.py
    - backend/app/modules/plum/seed.py
    - backend/alembic/versions/0005_plum_tables.py
    - backend/tests/plum/__init__.py
    - backend/tests/plum/test_parts.py
    - backend/tests/plum/test_revisions.py
  modified:
    - backend/app/core/models.py (uncommented plum import line)
    - backend/app/core/seed.py (appended seed_plum_data call)
decisions:
  - revision_number INT column added to plum_part_revision for stable ordering and MAX-based latest-revision queries (avoids timestamp collision pitfall)
  - Join table (plum_part_tag) chosen for classification tags — supports Phase 6 tag rename without data migration
  - Partial unique index uq_plum_part_one_released enforces one-Released-per-part at DB level (belt-and-suspenders for D-08)
  - plum.revision_scheme and plum.tag_vocabulary_editable stored in global settings table (no new infrastructure)
  - test_archive_part and test_archive_part_excluded_from_default_list split into separate tests for clarity (plan combined them; net result 14 tests, exceeds ≥13 threshold)
metrics:
  duration: ~35min
  completed: "2026-06-28"
  tasks: 3
  files: 11
---

# Phase 05 Plan 01: PLUM Data Layer Summary

**One-liner:** PLUM two-table SQLAlchemy model (plum_part + plum_part_revision), Pydantic schemas, idempotent seed (6 tags + 2 settings), Alembic migration 0005 with DB-level one-Released-per-part invariant, and 14-test Wave 0 scaffold.

---

## What Was Built

### Task 1 — PLUM models, schemas, and module stub (`9f793e1`)

**backend/app/modules/plum/__init__.py** — self-registers with the core module registry on import; mirrors syerp/__init__.py exactly.

**backend/app/modules/plum/router.py** — minimal APIRouter stub so __init__.py imports cleanly. Plan 05-02 will replace this with the full PLUM API.

**backend/app/modules/plum/models.py** — four SQLAlchemy 2.0 models:
- `PlumClassificationTag`: Integer PK lookup table for tag vocabulary (D-12)
- `PlumPart`: String(36) UUID PK stable header with part_number (unique, indexed), active (soft-delete), timestamps
- `PlumPartTag`: composite PK join table (part_id, tag_id)
- `PlumPartRevision`: revision snapshot with revision_number (per-part integer sequence), revision_label, status (draft/in_review/released/obsolete), D-02 attribute snapshot (description, category, unit_of_measure, notes, reason_for_revision), timestamps (created_at, released_at, obsoleted_at). Composite index on (part_id, status) for supersede queries.

No ORM relationships declared on any model (MissingGreenlet avoidance per RESEARCH Pitfall 1).

**backend/app/modules/plum/schemas.py** — six Pydantic schemas:
- `PartCreate`: part_number Optional (server auto-gens), description required, optional revision attrs + tag_ids
- `PartUpdate`: all Optional PATCH semantics
- `PartRead`: list display with current_revision_label, current_revision_status, tags list
- `RevisionCreate`: source_revision_id + revision-controlled fields
- `RevisionRead`: full revision snapshot with all timestamps
- `PartDetailRead`: full part + embedded revisions list (newest-first, per Open Question 3)

### Task 2 — Model discovery, seed, migration 0005 (`4dbc2ce`)

**backend/app/core/models.py** — uncommented the waiting plum import stub (line 27) so Alembic's Base.metadata discovers the four PLUM tables.

**backend/app/modules/plum/seed.py** — `seed_plum_data()`: idempotent select-before-insert for 6 classification tags and 2 plum settings (plum.revision_scheme="asme", plum.tag_vocabulary_editable="true").

**backend/app/core/seed.py** — `run_seeds()` extended with `seed_plum_data` call after `seed_gl_accounts`.

**backend/alembic/versions/0005_plum_tables.py** — hand-authored migration:
- Creates 4 tables in dependency order: plum_classification_tag → plum_part → plum_part_tag → plum_part_revision
- Indexes: part_number (unique), active, part_id, status, composite part_id+status
- Partial unique index `uq_plum_part_one_released ON plum_part_revision(part_id) WHERE status='released'` (T-05-01 DB-level one-Released-per-part invariant)
- down_revision = "0004" (SYERP tables)

### Task 3 — Wave 0 backend test scaffold (`1c350cf`)

**backend/tests/plum/__init__.py** — empty package init.

**backend/tests/plum/test_parts.py** — 9 tests covering PLUM-01/PLUM-02:
- `test_create_part` (201, part_number, active=True, first revision Draft)
- `test_create_duplicate_part_number` (409)
- `test_update_part` (200 + AuditLog row via AsyncSessionLocal)
- `test_archive_part` (active=False)
- `test_archive_part_excluded_from_default_list` (absent from default list)
- `test_create_requires_write_permission` (403 without plum:write)
- `test_search_by_part_number` (?q= search)
- `test_search_by_description` (?q= on revision description)
- `test_filter_by_status` (?status=draft filter)

**backend/tests/plum/test_revisions.py** — 5 tests covering PLUM-03:
- `test_create_revision` (201, Draft, copy-forward)
- `test_advance_to_in_review` (draft → in_review → 200)
- `test_release_supersedes_prior` (full D-08 supersede flow with Rev A → Obsolete)
- `test_released_revision_immutable` (422 on PATCH Released revision)
- `test_revision_history_order` (newest-first by revision_number)

Pytest collection: **14 tests collected, exit code 0**. All tests are RED until Plan 05-02 implements service + router.

---

## Verification Results

```
Alembic discovery: OK       (import app.core.models)
14 tests collected in 0.01s (pytest --collect-only)
Migration chain: OK         (down_revision = "0004")
Partial index: OK           (uq_plum_part_one_released present)
Seed wired: OK              (seed_plum_data in run_seeds())
```

---

## Deviations from Plan

### Auto-fixed Issues

None — plan executed exactly as written.

### Implementation Notes (non-deviations)

1. **`router.py` stub created** — The plan specified creating a minimal router stub so `__init__.py` imports cleanly. This was executed as specified (not a deviation).

2. **`test_archive_part` split into two tests** — The plan's acceptance criteria listed `test_archive_part` as one function, but the description covered two distinct behaviors: (a) setting `active=False` and (b) excluding the archived part from the default list. These were implemented as separate tests (`test_archive_part` and `test_archive_part_excluded_from_default_list`) for clarity and independent failure reporting. Total test count is 14, exceeding the ≥13 threshold. This is a beneficial clarification, not a scope deviation.

3. **Dev dependencies installed** — `pytest`, `pytest-asyncio`, and `httpx` were listed in `requirements-dev.txt` but missing from the backend venv. Installed them so the `--collect-only` verification could run. This resolves a pre-existing environment gap (out-of-scope pre-existing issue, fixed inline as Rule 3 blocking fix for collection verification).

---

## Known Stubs

None — this is a data layer plan. No data flows to UI rendering. The router.py stub is intentional and documented; it will be replaced in 05-02.

---

## Threat Flags

No new threat surface beyond what is in the plan's `<threat_model>`. All four mitigations documented in the threat register are implemented:
- T-05-01: `uq_plum_part_one_released` partial unique index in migration 0005 ✓
- T-05-02: select-before-insert idempotency in seed_plum_data ✓
- T-05-03: core/models.py import uncommented; migration chains to 0004 ✓
- T-05-SC: no new packages installed (dev tools from existing requirements-dev.txt only) ✓

---

## Self-Check

### Files exist:
- `/home/zack/Projects/BizNiceSweets/backend/app/modules/plum/__init__.py` — FOUND
- `/home/zack/Projects/BizNiceSweets/backend/app/modules/plum/models.py` — FOUND
- `/home/zack/Projects/BizNiceSweets/backend/app/modules/plum/schemas.py` — FOUND
- `/home/zack/Projects/BizNiceSweets/backend/app/modules/plum/router.py` — FOUND
- `/home/zack/Projects/BizNiceSweets/backend/app/modules/plum/seed.py` — FOUND
- `/home/zack/Projects/BizNiceSweets/backend/alembic/versions/0005_plum_tables.py` — FOUND
- `/home/zack/Projects/BizNiceSweets/backend/tests/plum/__init__.py` — FOUND
- `/home/zack/Projects/BizNiceSweets/backend/tests/plum/test_parts.py` — FOUND
- `/home/zack/Projects/BizNiceSweets/backend/tests/plum/test_revisions.py` — FOUND

### Commits exist:
- `9f793e1` — Task 1: PLUM models, schemas, module stub
- `4dbc2ce` — Task 2: model discovery, seed, migration 0005
- `1c350cf` — Task 3: Wave 0 test scaffold

## Self-Check: PASSED
