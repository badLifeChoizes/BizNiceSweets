---
phase: 04-syerp-core-hub
plan: "01"
subsystem: backend/syerp
tags: [models, migration, seed, tests, syerp]
dependency_graph:
  requires: [03-03-SUMMARY]
  provides: [syerp_partner table, syerp_gl_account table, CoA seed, Wave 0 test scaffold]
  affects: [backend/app/modules/syerp, backend/app/core/seed.py, backend/alembic]
tech_stack:
  added: []
  patterns: [SQLAlchemy 2.0 Mapped[] style, idempotent select-before-insert seed, hand-authored Alembic migration]
key_files:
  created:
    - backend/app/modules/syerp/coa_seed.py
    - backend/alembic/versions/0004_syerp_tables.py
    - backend/tests/syerp/__init__.py
    - backend/tests/syerp/test_partners.py
    - backend/tests/syerp/test_gl.py
  modified:
    - backend/app/modules/syerp/models.py
    - backend/app/core/seed.py
decisions:
  - "Hand-authored migration 0004 (no live DB available); follows 0002/0003 hand-author convention"
  - "CoA seed uses parent_code key in data dict (not parent_id); resolved to DB integer IDs at seed time via two-pass insert"
  - "_STANDARD_COA has 44 accounts (plan minimum was 40); extra accounts cover full asset/expense sub-structure"
metrics:
  duration: ~25min
  completed: 2026-06-27
  tasks_completed: 3
  files_changed: 7
---

# Phase 4 Plan 1: SYERP Backend Data Foundation Summary

SYERP two-table schema foundation (`syerp_partner`, `syerp_gl_account`) with hand-authored Alembic migration, idempotent 44-account CoA seed wired into startup, and 16-test Wave 0 scaffold ready for Plan 02 to green.

## Tasks Completed

| Task | Name | Commit | Key Files |
|------|------|--------|-----------|
| 1 | Define Partner + GLAccount models and migration 0004 | f60f89a | models.py, 0004_syerp_tables.py |
| 2 | Idempotent CoA seed wired into run_seeds() | ad05312 | coa_seed.py, core/seed.py |
| 3 | Wave 0 SYERP backend test scaffold | a65ccce | tests/syerp/test_partners.py, tests/syerp/test_gl.py |

## What Was Built

### Task 1: Models + Migration

`backend/app/modules/syerp/models.py` replaced the Phase 1 stub with two SQLAlchemy 2.0 models:

**Partner** (`syerp_partner`): UUID string PK; `code` String(20) unique+indexed; `name` indexed; `is_vendor`/`is_customer` boolean flags; `active` boolean (soft-delete, NOT `is_active`); full address block (addr_line1..addr_country); contact block (contact_name/email/phone); commerce fields (payment_terms, tax_id, currency, country_of_origin, notes); timezone-aware timestamps with `onupdate`.

**GLAccount** (`syerp_gl_account`): Integer autoincrement PK; `code` String(10) unique+indexed; `name`; `account_type` String(20) (NOT `type`); self-referential `parent_id` ForeignKey; `active` boolean.

`backend/alembic/versions/0004_syerp_tables.py` hand-authored (no live DB) following the 0002/0003 convention. Chains `down_revision = "0003"`. Creates both tables with unique constraints on `code` (T-04-01) and the self-referential FK on `parent_id` (T-04-03). Includes named indexes on `syerp_partner.name`, `syerp_partner.active`, and `syerp_gl_account.code`.

`backend/app/core/models.py` was NOT modified — the existing `from app.modules.syerp import models as syerp_models` import on line 15 (Phase 1 stub) auto-registers both new classes with `Base.metadata` for Alembic.

### Task 2: CoA Seed

`backend/app/modules/syerp/coa_seed.py` exports `_STANDARD_COA` (44 accounts) and `seed_gl_accounts(db)`.

Account breakdown:
- ASSET (10): 1000 Assets root → 1100 Current Assets (Cash, AR, Inventory, WIP, Prepaid) → 1200 Fixed Assets (Equipment, Accumulated Depreciation)
- LIABILITY (8): 2000 root → 2100 Current (AP, Accrued, Sales Tax, Payroll) → 2200 Long-Term Debt
- EQUITY (5): 3000 root → 3100 Owner's Equity (Capital, Retained Earnings, Current Year Net Income)
- REVENUE (6): 4000 root → 4100 Product Sales (Product Revenue, Service Revenue) → 4200 Other Income (Interest)
- EXPENSE (15): 5000 root → 5100 COGS (Direct Materials, Direct Labor, Manufacturing Overhead) → 5200 Operating (Salaries, Rent, Utilities, Insurance, Depreciation, R&D, Marketing, G&A, Professional Services)

The seed uses `parent_code` strings (not `parent_id` integers) in the data dict. At runtime `seed_gl_accounts()` performs a two-pass insert: Pass 1 inserts root accounts and flushes to get DB integer IDs; Pass 2 inserts children with resolved `parent_id`. A pre-pass loads all existing accounts into `code_to_id` so re-runs skip already-present rows (T-04-02 idempotency).

`backend/app/core/seed.py` `run_seeds()` updated: added `from app.modules.syerp.coa_seed import seed_gl_accounts` and `await seed_gl_accounts(db)` after `seed_default_settings` (Phase 4 position in seed order).

### Task 3: Wave 0 Test Scaffold

`backend/tests/syerp/__init__.py` — empty package marker.

`backend/tests/syerp/test_partners.py` — 13 tests covering SYERP-01..04:
- `test_create_vendor`, `test_create_requires_role`, `test_update_partner_writes_audit`, `test_archive_partner`, `test_archived_excluded_by_default`, `test_create_requires_syerp_write`, `test_duplicate_code_rejected`, `test_search_by_name`, `test_search_by_code`, `test_vendor_role_filter`, `test_create_customer`, `test_customer_role_filter`, `test_dual_role_appears_in_both`

`backend/tests/syerp/test_gl.py` — 3 tests covering SYERP-05:
- `test_gl_accounts_seeded`, `test_gl_seed_idempotent`, `test_gl_requires_syerp_read`

All 16 tests collect cleanly (`pytest tests/syerp/ --collect-only -q`). Tests are real behavior assertions targeting `/api/v1/syerp/` routes using `client` + `skip_if_no_db` fixtures and `create_access_token` for RBAC minting. No `xfail` marks — tests will fail/skip until Plan 02 greens them.

## Deviations from Plan

### Auto-fixed Issues

None — plan executed exactly as written.

### Notes

**Hand-authored migration:** `alembic revision --autogenerate` requires a live PostgreSQL connection. The development environment does not run a local DB (Podman is the deployment target). Migrations 0002 and 0003 were also hand-authored for the same reason. Migration 0004 follows the established convention exactly — hand-authored from the ORM models with no live DB at plan time.

**CoA count 44 vs plan minimum 40:** The plan specified >= 40 accounts. The seed data includes 44 accounts to provide complete sub-structure coverage matching the RESEARCH.md standard CoA list. The extra 4 accounts (3130 Current Year Net Income, 4200 Other Income, 4210 Interest Income, 2130 Sales Tax Payable) are standard manufacturing-business accounts. No plan deviation — the plan requirement was a minimum.

**parent_code design:** The plan described parent_id resolution but the `_STANDARD_COA` data in RESEARCH.md showed `parent_id: None` as placeholders for all rows. The implementation uses a `parent_code` string key in the data dict and resolves to integer DB IDs at seed time — cleaner than raw integer IDs in the constant (which would be environment-specific).

## Threat Mitigations Applied

| Threat | Status |
|--------|--------|
| T-04-01: partner code uniqueness | Mitigated — UniqueConstraint on syerp_partner.code in migration 0004 |
| T-04-02: CoA seed re-run duplicates | Mitigated — select-before-insert idempotency; test_gl_seed_idempotent asserts it |
| T-04-03: self-referential FK violation at seed | Mitigated — two-pass parent-before-child insert ordering in seed_gl_accounts |

## Known Stubs

None — all plan deliverables are fully implemented. The test scaffold intentionally tests routes that don't exist yet; this is by design (Wave 0 stub pattern), not a stub in this plan's output.

## Self-Check

Files exist:
- backend/app/modules/syerp/models.py — FOUND
- backend/app/modules/syerp/coa_seed.py — FOUND
- backend/app/core/seed.py (modified) — FOUND
- backend/alembic/versions/0004_syerp_tables.py — FOUND
- backend/tests/syerp/__init__.py — FOUND
- backend/tests/syerp/test_partners.py — FOUND
- backend/tests/syerp/test_gl.py — FOUND

Commits verified:
- f60f89a — Task 1 models + migration
- ad05312 — Task 2 CoA seed
- a65ccce — Task 3 test scaffold

## Self-Check: PASSED
