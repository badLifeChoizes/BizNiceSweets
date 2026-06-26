---
phase: 03-app-shell-settings
plan: "01"
subsystem: backend/core
tags: [orm, migrations, seeds, permissions, tests]
dependency_graph:
  requires: [02-04]
  provides: [modules-table, settings-table, settings-manage-permission, core-test-scaffold]
  affects: [03-02, 03-03]
tech_stack:
  added: []
  patterns:
    - SQLAlchemy 2.0 natural string PK (Module.key)
    - PostgreSQL partial unique index WHERE owner_id IS NULL (uq_settings_global)
    - Surrogate int PK with partial index for nullable composite uniqueness (Setting.id)
    - Static seed catalog pattern (7-suite list, not registry._registry)
    - Wave 0 RED test scaffold (contract tests for 03-02 API)
key_files:
  created:
    - backend/app/core/modules_model.py
    - backend/app/core/settings_model.py
    - backend/app/core/modules_seed.py
    - backend/app/core/settings_seed.py
    - backend/alembic/versions/0003_add_modules_settings_tables.py
    - backend/tests/core/__init__.py
    - backend/tests/core/conftest.py
    - backend/tests/core/test_modules.py
    - backend/tests/core/test_settings.py
  modified:
    - backend/app/core/models.py
    - backend/app/core/seed.py
    - backend/app/modules/auth/seed.py
decisions:
  - "Natural string PK for Module.key (matches MODULE_NAME across the codebase; mirrors Permission.code pattern)"
  - "Surrogate int PK for Setting.id with partial unique index — avoids a breaking PK migration when per-user settings arrive (D-13)"
  - "Static _MODULE_SEEDS catalog (not registry._registry) — registry only holds modules imported under active Compose profile; static list keeps admin catalog complete for all 7 suites"
  - "settings:manage permission: new code (not reusing users:manage) — keeps concerns separated per research Pattern 4"
  - "settings:manage excluded from _USER_ROLE_PERMS — admin-only via wildcard grant (D-12)"
  - "Wave 0 test stubs write real assertions that go GREEN when 03-02 ships (not pass/xfail)"
metrics:
  duration: 282s
  completed: "2026-06-26"
  tasks_completed: 3
  files_changed: 12
---

# Phase 03 Plan 01: Backend Data Layer for Modules and Settings Summary

**One-liner:** `modules` table (7-suite static catalog, SYERP always_on=True) and key-value `settings` table (6 defaults, surrogate PK + partial unique index for per-user groundwork) with idempotent seeds, Alembic revision 0003, admin-only `settings:manage` permission, and Wave 0 RED test scaffold encoding the CORE-06/07 API contract.

## Tasks Completed

| Task | Name | Commit | Key Files |
|------|------|--------|-----------|
| 1 | ORM models for modules and settings + Alembic discovery wiring | ef4a029 | modules_model.py, settings_model.py, models.py |
| 2 | Idempotent seeds + settings:manage permission + Alembic revision + wiring | 41a7c84 | modules_seed.py, settings_seed.py, seed.py, auth/seed.py, 0003_add_modules_settings_tables.py |
| 3 | Wave 0 — backend/tests/core test scaffold (failing/red stubs for CORE-06/07) | 3773567 | tests/core/__init__.py, tests/core/conftest.py, test_modules.py, test_settings.py |

## Deviations from Plan

None — plan executed exactly as written.

## Verification Results

All plan-level verification gates passed:

- `python -c "import app.core.models"` registers `modules` and `settings` in Base.metadata (9 tables total)
- All 11 new/modified Python files parse cleanly (AST verify)
- `settings:manage` present in `_PERMISSIONS`, absent from `_USER_ROLE_PERMS` (admin-only, D-12)
- `run_seeds()` calls `seed_modules_table` and `seed_default_settings` after `seed_admin_user`
- Migration 0003 chains to 0002, creates both tables, creates `uq_settings_global` partial unique index
- `pytest tests/core/ --collect-only` collects exactly 7 tests with no import errors

## Known Stubs

None — this plan delivers the data layer only. The Wave 0 tests in `test_modules.py` (3 endpoint tests) and `test_settings.py` (2 endpoint tests) are intentionally RED until plan 03-02 ships the API routers. `test_seed_defaults` passes immediately with a live DB.

## Threat Flags

No new network endpoints or auth paths introduced in this plan (data layer only). Threat mitigations from the plan's threat register:

| Threat ID | Mitigation Applied |
|-----------|-------------------|
| T-03-01 | owner_id never settable by client in v1; server always writes scope="global", owner_id=None in seed |
| T-03-02 | always_on set only by seed (SYERP=True); no API to mutate always_on (API enforcement in 03-02) |
| T-03-03 | settings:manage granted to admin role only; explicitly excluded from _USER_ROLE_PERMS |
| T-03-09 | uq_settings_global partial index ships in migration 0003 |

## Self-Check: PASSED

Files exist:
- backend/app/core/modules_model.py: FOUND
- backend/app/core/settings_model.py: FOUND
- backend/app/core/modules_seed.py: FOUND
- backend/app/core/settings_seed.py: FOUND
- backend/alembic/versions/0003_add_modules_settings_tables.py: FOUND
- backend/tests/core/__init__.py: FOUND
- backend/tests/core/conftest.py: FOUND
- backend/tests/core/test_modules.py: FOUND
- backend/tests/core/test_settings.py: FOUND

Commits exist:
- ef4a029: feat(03-01): ORM models for modules and settings + Alembic discovery wiring
- 41a7c84: feat(03-01): idempotent seeds + settings:manage permission + Alembic revision 0003
- 3773567: test(03-01): Wave 0 test scaffold for CORE-06/07 (core test package)
