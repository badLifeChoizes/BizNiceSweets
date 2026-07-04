---
phase: 7
slug: close-v1-0-gaps-fix-plum-syerp-partner-import-plum-07-10-par
status: approved
nyquist_compliant: true
wave_0_complete: false
created: 2026-07-02
---

# Phase 7 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

### Backend (pytest — MUST run inside the API container)

| Property | Value |
|----------|-------|
| **Framework** | pytest (`asyncio_mode = "auto"`, `testpaths = ["tests"]`) |
| **Config file** | `backend/pyproject.toml` `[tool.pytest.ini_options]` |
| **Runner** | `podman exec compose_api_1 pytest` — **NOT** host `backend/.venv/bin/pytest` |
| **Quick run command** | `podman exec compose_api_1 pytest tests/plum/test_avl.py tests/plum/test_import_export.py tests/plum/test_parts.py -x -q` |
| **Full suite command** | `podman exec compose_api_1 pytest` |
| **Live-DB precondition** | `podman exec compose_api_1 alembic current` reports `0006` before trusting any green run |
| **Estimated runtime** | ~30 seconds (3 plum files), ~60 seconds (full) |

> **Why `podman exec`, not host pytest (RESEARCH Pitfall 1):** `POSTGRES_HOST=db` only resolves inside the compose network; `compose/compose.yml` deliberately does not publish the DB port (`T-01-12`). Running host-side pytest makes every `skip_if_no_db` test silently skip (`31 passed, 94 skipped`), giving false green — the exact failure mode that let these bugs ship in Phase 6. All backend commands in this contract run via `podman exec compose_api_1`.

### Frontend (Vitest — no live DB needed)

| Property | Value |
|----------|-------|
| **Framework** | Vitest (`"test": "vitest"`) |
| **Config file** | `frontend/package.json` / `frontend/vite.config.ts` |
| **Quick run command** | `cd frontend && npx tsc --noEmit && npm run test -- --run ImportExport` |
| **Full suite command** | `cd frontend && npm run test -- --run` |
| **Type gate** | `cd frontend && npx tsc --noEmit` |
| **Estimated runtime** | ~20 seconds |

---

## Sampling Rate

- **After every task commit:** run the targeted test file for the touched code — `podman exec compose_api_1 pytest tests/plum/test_avl.py tests/plum/test_import_export.py -x -q` after 07-01-01, `podman exec compose_api_1 pytest tests/plum/test_parts.py -x -q` after 07-01-02, `cd frontend && npx tsc --noEmit && npm run test -- --run ImportExport` after 07-02-01.
- **After every plan wave:** `podman exec compose_api_1 pytest tests/plum/ -q` (full PLUM suite) + `cd frontend && npm run test -- --run`.
- **Before `/gsd:verify-work`:** full backend suite green (`podman exec compose_api_1 pytest`) with **0 unexpected skips** on `test_avl.py`, `test_import_export.py`, `test_parts.py`, plus the frontend suite green — then the 07-03 human-verify checkpoint passes.
- **Max feedback latency:** ~30 seconds (plum subset).

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 07-01-01 | 01 | 1 | PLUM-07, PLUM-10, PLUM-08 | T-07-01 | AVL/import/export vendor lookups stay restricted to `is_vendor` Partners — WHERE filter preserved verbatim at all 4 sites (upholds T-06-07); import-alias-only diff, no widening | integration (live DB) | `podman exec compose_api_1 pytest tests/plum/test_avl.py tests/plum/test_import_export.py -x -q` | ✅ (test_avl exists; test_import_export extended to seed a `PlumAvlLink` row exercising site 2139) | ⬜ pending |
| 07-01-02 | 01 | 1 | PLUM-01 | T-07-02 / T-07-03 | `^P[0-9]+$` regex filter runs *before* the integer cast so malformed part_numbers (`"P-DUPE-01"`) never reach the cast → no `DataError` 500; regex is a fixed literal (no request-derived input → no injection/ReDoS) | unit/integration (live DB) | `podman exec compose_api_1 pytest tests/plum/test_parts.py -x -q` | ❌ W0 (`test_generate_part_number_digit_boundary` is net-new) | ⬜ pending |
| 07-02-01 | 02 | 1 | PLUM-10 | T-07-04 | Invalidation scoped to `commitImportMutation` only; no auth/permission logic touched; global `staleTime` untouched | type gate + unit (Vitest) | `cd frontend && npx tsc --noEmit && npm run test -- --run ImportExport` | ✅ (3 existing smoke tests) | ⬜ pending |
| 07-03-01 | 03 | 2 | PLUM-04..10 | — | Manual UAT against the already-RBAC-gated live stack; no code, no new surface | manual (human-verify, `gate="blocking"`) | see Manual-Only Verifications | N/A | ⬜ pending |
| 07-04-01 | 04 | 3 | PLUM-04..10, CORE-01, CORE-09 | — | Documentation reconciliation only; status changes gated on the 07-03 outcome (no Complete without verified evidence) | grep gate (docs) | `grep -c "Complete" .planning/REQUIREMENTS.md && grep -Eic "plum-0[4-9]\|plum-10" docs/features/requirements-progress.md` | N/A | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

*File Exists column: ✅ = verifier already exists (may be extended in-place); ❌ W0 = Wave 0 must create the test first; N/A = grep/type gate or manual, no pytest/vitest file required.*

### Sampling continuity

Five tasks, one manual (07-03-01). Every code-producing task (07-01-01, 07-01-02, 07-02-01) has a live automated command; the terminal docs task (07-04-01) has an automated grep gate. No 3 consecutive tasks lack an automated verify.

---

## Wave 0 Requirements

- [ ] `backend/tests/plum/test_parts.py::test_generate_part_number_digit_boundary` — **net-new** (created in Plan 07-01 Task 2). Seed `P99999` and `P100000` via explicit-part_number POSTs, call auto-generation, assert the returned value has a numeric suffix strictly greater than every pre-existing `^P[0-9]+$` row (numeric MAX + 1) and collides with none. Must assert robustly (not a hardcoded `"P100001"`) because the shared live dev DB already holds rows past the boundary (RESEARCH Runtime State Inventory).
- [ ] `backend/tests/plum/test_import_export.py` — **extended in-place** (Plan 07-01 Task 1). Ensure at least one test seeds a `PlumAvlLink` row before the JSON export so the vendor-lookup path at `service.py:2139` (`build_json_export`) actually executes rather than short-circuiting on empty `vendor_ids`; ensure an import-commit case carries a valid vendor `code` in `avl_links` so `commit_import` at 2740 executes. Sites 1634 (`add_avl_link`) and 2607 (`validate_import`) are already covered by `test_avl.py::test_add_avl_link` and `test_import_export.py::test_import_preview_unknown_vendor` — these existing tests are *run against the live DB* for the first time this phase.

All other backend tests re-run existing files that were written but never executed against Postgres. `wave_0_complete` flips to `true` once both items above collect and run (not skip) under `podman exec compose_api_1 pytest`.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Consolidated Phase-6 + Phase-7 UAT — the 8 Phase-6 ROADMAP success criteria (BOM tree add/expand, flat roll-up footer, where-used direct/indirect labels, AVL vendor link + preferred, effective-cost source transitions, margin/negative-margin red, JSON+Excel export/round-trip import with no deletes + >10 MB rejection, frozen "Released at" cost) PLUS 4 Phase-7 regression checks (AVL add no-500, vendor-ref import no-500, Parts List auto-refresh after commit, auto-part-number create past the P99999→P100000 boundary with no collision) | PLUM-04..10 (+ regression on PLUM-01/07/10) | Visual/interactive behavior across the running stack (tree expand/collapse, currency suffix, file downloads, drag-drop import preview, red negative-margin styling) cannot be asserted by unit tests. Per RESEARCH Pitfall 2, unit-test-green already slipped a 500 through once — PLUM-07/10 are NOT closed on green tests alone. Per Pitfall 4 this is ONE consolidated pass, not two. The cache-invalidation refresh (PLUM-10) is not practically unit-testable without a query-client harness the project lacks. | Precondition: `podman ps` shows compose_db_1 / compose_api_1 / compose_frontend_1 running and `podman exec compose_api_1 alembic current` reports `0006`. Then follow the 12-flow checklist in Plan 07-03 Task 1 `<how-to-verify>` (flows 1-8 = Phase-6 criteria, 9-12 = Phase-7 regressions). Blocking human-verify checkpoint; user types "approved" or lists failing flows → routes to `/gsd:plan-phase --gaps`. |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies — 07-01-01/07-01-02/07-02-01 have live automated commands, 07-04-01 has a grep gate; the sole manual task (07-03-01) is a deliberate `checkpoint:human-verify` for UI criteria that unit tests cannot assert (and that already slipped a regression through once)
- [x] Sampling continuity: no 3 consecutive tasks without automated verify (only 07-03-01 is manual)
- [x] Wave 0 covers all MISSING references — the net-new `test_generate_part_number_digit_boundary` plus the extended `test_import_export.py` AVL-seed coverage
- [x] No watch-mode flags (all commands use `-x -q` / `--run`; none use `--watch`)
- [x] Feedback latency < 30s (plum subset via `podman exec`)
- [x] Live-DB run mechanism enforced — quick/full commands use `podman exec compose_api_1 pytest` (not host pytest), with an `alembic current` == 0006 precondition, per RESEARCH Pitfall 1
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-07-02
