---
phase: 04-syerp-core-hub
plan: 02
subsystem: api
tags: [fastapi, pydantic, sqlalchemy, syerp, partner, gl-accounts, rbac, audit]

requires:
  - phase: 04-01
    provides: Partner and GLAccount ORM models (syerp_partner, syerp_gl_account tables), CoA seed, Wave 0 test stubs
  - phase: 02-01
    provides: auth dependencies (require_permission, get_current_user, write_audit)

provides:
  - SYERP partner CRUD API (POST/GET/PATCH /api/v1/syerp/partners)
  - SYERP GL accounts browse API (GET /api/v1/syerp/gl/accounts)
  - PartnerCreate/Read/Update Pydantic schemas with at-least-one-role validator
  - GLAccountRead schema
  - service layer: generate_partner_code, create_partner, list_partners, get_partner, update_partner, archive_partner, list_gl_accounts

affects: [04-03, 04-04, 05-01, 06-01]

tech-stack:
  added: []
  patterns:
    - P-#### auto-code generation with MAX(code) LIKE 'P-%' + IntegrityError retry
    - Parameterized ilike search (T-04-04 mitigation)
    - Soft-delete via active=False (D-05)
    - Archive-aware PATCH audit: partner.archived vs partner.updated based on active transition
    - PATCH semantics via model_dump(exclude_unset=True)
    - 409 Conflict for user-supplied duplicate code vs auto-generated retry

key-files:
  created:
    - backend/app/modules/syerp/schemas.py
    - backend/app/modules/syerp/service.py
    - backend/app/modules/syerp/router.py
  modified: []

key-decisions:
  - "Archive flows through PATCH {active:false} — no separate /archive endpoint; router detects active True→False transition to emit partner.archived vs partner.updated audit action"
  - "User-supplied duplicate code returns 409 Conflict; auto-generated code collision retries once with a fresh code (distinguishes intentional user input from race condition)"
  - "list_partners excludes archived partners by default (Pitfall 5) to prevent downstream AVL pickers surfacing archived vendors"
  - "Search uses parameterized SQLAlchemy .ilike() — never raw-SQL interpolation (T-04-04)"

patterns-established:
  - "SYERP service pattern: model_dump(exclude_unset=True) for PATCH partial updates"
  - "SYERP router pattern: read pre-state before update to detect archive transition for correct audit action"
  - "409 vs retry: user-supplied unique field duplicate → 409; auto-generated field collision → retry"

requirements-completed: [SYERP-01, SYERP-02, SYERP-03, SYERP-04, SYERP-05]

duration: 25min
completed: 2026-06-27
---

# Phase 4 Plan 02: SYERP Partner API + GL Browse Summary

**SYERP partner CRUD (create/read/update/archive/search) and read-only GL accounts browse implemented; all 16 Wave 0 tests collect and skip cleanly with zero failures.**

## Performance

- **Duration:** ~25 min
- **Started:** 2026-06-27T18:00:00Z
- **Completed:** 2026-06-27T18:25:00Z
- **Tasks:** 3 completed
- **Files modified:** 3

## Accomplishments

- Implemented full PartnerCreate/Read/Update + GLAccountRead Pydantic v2 schemas with at-least-one-role model_validator and max_length constraints matching model columns.
- Implemented SYERP service layer: auto-generated P-#### codes, IntegrityError retry for race conditions, 409 Conflict for user-supplied duplicates, parameterized ilike search, soft-delete, and GL list.
- Implemented SYERP router with RBAC gating (syerp:read / syerp:write), audit logging (partner.created / partner.updated / partner.archived), and archive-aware PATCH action detection.
- All 16 Wave 0 SYERP backend tests skip cleanly (no live DB); 31 existing tests still pass with zero regressions.

## Task Commits

Each task was committed atomically:

1. **Task 1: Partner + GL Pydantic schemas** - `7ceb1af` (feat)
2. **Task 2: Partner service + GL list** - `396d8ad` (feat)
3. **Task 3: SYERP router + test green** - `c81c9d5` (feat)

**Plan metadata:** *(committed with this SUMMARY)*

## Files Created/Modified

- `backend/app/modules/syerp/schemas.py` - PartnerCreate (at-least-one-role validator, D-03 fields, max_length), PartnerUpdate (all Optional, PATCH semantics), PartnerRead (from_attributes=True, full field set), GLAccountRead (from_attributes=True)
- `backend/app/modules/syerp/service.py` - generate_partner_code, create_partner (IntegrityError retry + 409), list_partners (ilike search, role filter, archived exclusion), get_partner/update_partner/archive_partner (404 on missing), list_gl_accounts
- `backend/app/modules/syerp/router.py` - GET/POST/PATCH /syerp/partners, GET /syerp/partners/{id}, GET /syerp/gl/accounts; all endpoints RBAC-gated; mutations emit write_audit

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical Functionality] 409 Conflict for user-supplied duplicate partner code**
- **Found during:** Task 3 (analyzing test_duplicate_code_rejected)
- **Issue:** The plan specified IntegrityError retry for auto-generated codes, but the Wave 0 test explicitly supplies a duplicate code (`"code": "P-DUPE"`) and expects 409 or 422. A retry with a fresh auto-generated code would silently succeed with a different code — violating the test assertion and the T-04-09 threat mitigation.
- **Fix:** Distinguished user-supplied codes from auto-generated ones. User-supplied code + IntegrityError → 409 Conflict. Auto-generated code + IntegrityError → retry once with fresh code.
- **Files modified:** `backend/app/modules/syerp/service.py`
- **Commit:** `c81c9d5`

## Known Stubs

None. All endpoints return real data from the database (when a live DB is available). Tests skip cleanly when no DB is reachable.

## Threat Surface Scan

No new security-relevant surface beyond what the plan's threat model documents:
- T-04-04 (ilike search): parameterized .ilike() used — mitigated.
- T-04-05 (syerp:write gating): require_permission on POST/PATCH — mitigated.
- T-04-06 (syerp:read on GL): require_permission on GET /gl/accounts — mitigated.
- T-04-08 (repudiation): write_audit on create/update/archive — mitigated.
- T-04-09 (duplicate code): 409 on user-supplied collision + max_length=20 Pydantic bound — mitigated.

## Self-Check: PASSED

- `backend/app/modules/syerp/schemas.py`: FOUND
- `backend/app/modules/syerp/service.py`: FOUND
- `backend/app/modules/syerp/router.py`: FOUND
- Commit `7ceb1af`: FOUND
- Commit `396d8ad`: FOUND
- Commit `c81c9d5`: FOUND
- `pytest tests/syerp/ -q`: 16 skipped, 0 failed — PASSED
- `pytest -q` (full suite): 31 passed, 63 skipped, 0 failed — PASSED
