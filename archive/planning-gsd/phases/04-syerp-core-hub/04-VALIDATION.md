---
phase: 4
slug: syerp-core-hub
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-26
---

# Phase 4 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (backend) / vitest (frontend) — confirm against existing config during Wave 0 |
| **Config file** | backend: `backend/pyproject.toml` or `pytest.ini`; frontend: `frontend/vitest.config.ts` (planner to confirm) |
| **Quick run command** | `cd backend && pytest tests/modules/syerp -q` |
| **Full suite command** | `cd backend && pytest -q` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run the quick run command
- **After every plan wave:** Run the full suite command
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 4-01-01 | 01 | 1 | SYERP-01 | T-4-01 / — | partner create/update gated by `syerp:write`; reads by `syerp:read` | unit | `pytest tests/modules/syerp/test_partner_api.py -q` | ❌ W0 | ⬜ pending |
| 4-01-02 | 01 | 1 | SYERP-01 | — | partner code unique + auto-generated, override allowed | unit | `pytest tests/modules/syerp/test_partner_code.py -q` | ❌ W0 | ⬜ pending |
| 4-01-03 | 01 | 1 | SYERP-01 | — | soft-delete sets inactive; default list excludes archived | unit | `pytest tests/modules/syerp/test_partner_archive.py -q` | ❌ W0 | ⬜ pending |
| 4-02-01 | 02 | 1 | SYERP-02, SYERP-04 | — | search across name/code/contact returns matches; vendor/customer role filter | unit | `pytest tests/modules/syerp/test_partner_search.py -q` | ❌ W0 | ⬜ pending |
| 4-03-01 | 03 | 1 | SYERP-05 | — | CoA seed idempotent (select-before-insert); browse returns seeded tree | unit | `pytest tests/modules/syerp/test_gl_seed.py -q` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

*Task IDs are provisional — planner finalizes the plan/wave/task breakdown.*

---

## Wave 0 Requirements

- [ ] `tests/modules/syerp/test_partner_api.py` — stubs for SYERP-01, SYERP-03 (CRUD + RBAC)
- [ ] `tests/modules/syerp/test_partner_code.py` — stubs for SYERP-01 (code generation + uniqueness)
- [ ] `tests/modules/syerp/test_partner_archive.py` — stubs for SYERP-01 (soft-delete filtering)
- [ ] `tests/modules/syerp/test_partner_search.py` — stubs for SYERP-02, SYERP-04 (search/filter)
- [ ] `tests/modules/syerp/test_gl_seed.py` — stubs for SYERP-05 (CoA seed idempotency + browse)
- [ ] `tests/modules/syerp/conftest.py` — shared fixtures (auth/session/permission, partner factory)

*Reuse the existing auth-module test fixtures (DB session, authenticated client, permission grants) rather than building new infrastructure.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Vendor/Customer nav entries appear iff module enabled AND user permitted | SYERP-01, SYERP-03 | Shell visibility integration (Phase 3 D-04) crosses module + RBAC + UI state | Log in as a `syerp:read` user → Vendor + Customer nav entries visible; revoke permission → entries hidden |
| Search "feels instant" (debounced live filter) | SYERP-02, SYERP-04 | Perceived-latency UX is not unit-testable | Type in the vendor search box → list narrows within ~300ms without a full reload |
| CoA renders as a grouped expandable read-only tree | SYERP-05 | Visual tree rendering | Open Chart of Accounts → 5 type groups expand/collapse; no add/edit controls present |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
