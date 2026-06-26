---
phase: 3
slug: app-shell-settings
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-06-26
---

# Phase 3 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest + httpx ASGITransport (pytest-asyncio auto mode) [backend]; TypeScript `tsc --noEmit` [frontend] |
| **Config file** | `backend/pyproject.toml` `[tool.pytest.ini_options]` (frontend: tsconfig — no Vitest suite added this phase) |
| **Quick run command** | `cd backend && pytest tests/core/ -x -q` |
| **Full suite command** | `cd backend && pytest tests/ -v` (frontend: `cd frontend && npm run build` / `tsc --noEmit`) |
| **Estimated runtime** | ~15 seconds (backend core subset; full suite ~30s) |

---

## Sampling Rate

- **After every task commit:** Run `cd backend && pytest tests/core/ -x -q`
- **After every plan wave:** Run `cd backend && pytest tests/ -v`
- **Before `/gsd-verify-work`:** Full backend suite green + `cd frontend && tsc --noEmit` clean + manual browser smoke (03-03 T4)
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 03-01-T1 | 01 | 1 | CORE-06 / CORE-07 | T-03-01 | Models register in Base.metadata; `owner_id`/`scope` server-controlled | smoke | `cd backend && python -c "import app.core.models; from app.core.base import Base; assert {'modules','settings'} <= set(Base.metadata.tables)"` | ✅ | ⬜ pending |
| 03-01-T2 | 01 | 1 | CORE-06 / CORE-07 | T-03-02 / T-03-03 / T-03-09 | SYERP seeded `always_on=True`; `settings:manage` admin-only; `uq_settings_global` partial index | smoke | `cd backend && python -c "import ast; [ast.parse(open(f).read()) for f in [...seed+migration files]]"` (AST + wiring greps) | ✅ | ⬜ pending |
| 03-01-T3 | 01 | 1 | CORE-06 / CORE-07 | T-03-02 / T-03-03 | Wave 0 scaffold — RED contract tests for list/toggle/always-on/admin-gate + settings list/update/seed | integration (RED) | `cd backend && pytest tests/core/ -q --collect-only` (≥7 collected) | ❌ W0 | ⬜ pending |
| 03-02-T1 | 02 | 2 | CORE-06 / CORE-07 | T-03-04 / T-03-03 | Always-on disable → 422; admin gate via `settings:manage`; PATCH partial-update only | integration | `cd backend && pytest tests/core/test_modules.py tests/core/test_settings.py -x` | ✅ (greens W0) | ⬜ pending |
| 03-02-T2 | 02 | 2 | CORE-08 | — | `/auth/me` exposes flat `permissions: string[]` | integration | `cd backend && pytest tests/auth/test_login.py::test_me_includes_permissions -x` | ✅ | ⬜ pending |
| 03-03-T1..T3 | 03 | 3 | CORE-08 | — | Permission-filtered nav; admin-only menu; disabled-module nav hidden | type-check | `cd frontend && tsc --noEmit` | ✅ (type only) | ⬜ pending |
| 03-03-T4 | 03 | 3 | CORE-08 | — | Shell render, settings persistence, toggle propagation (visual/interactive) | manual (checkpoint) | Human-verify checkpoint — see Manual-Only Verifications | N/A | ⬜ pending |

**Automated test inventory (8 backend tests from RESEARCH §Validation → Test Map):**
- `test_modules.py::test_list_modules_returns_enabled_flag` (CORE-07) — scaffolded 03-01-T3, greened 03-02-T1
- `test_modules.py::test_toggle_module` (CORE-07) — scaffolded 03-01-T3, greened 03-02-T1
- `test_modules.py::test_cannot_disable_always_on` (CORE-07, 422 guard) — scaffolded 03-01-T3, greened 03-02-T1
- `test_modules.py::test_toggle_requires_admin` (CORE-07, 403) — scaffolded 03-01-T3, greened 03-02-T1
- `test_settings.py::test_list_settings_admin` (CORE-06) — scaffolded 03-01-T3, greened 03-02-T1
- `test_settings.py::test_update_setting` (CORE-06) — scaffolded 03-01-T3, greened 03-02-T1
- `test_settings.py::test_seed_defaults` (CORE-06) — scaffolded 03-01-T3, green at seed time
- `test_login.py::test_me_includes_permissions` (CORE-08) — added 03-02-T2

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `backend/tests/core/__init__.py` — empty test-package marker (03-01-T3)
- [ ] `backend/tests/core/conftest.py` — `seeded_core_db` fixture (admin + modules + settings), `skip_if_no_db`-gated (03-01-T3)
- [ ] `backend/tests/core/test_modules.py` — RED stubs for CORE-07 (list / toggle / always-on guard / 403), created 03-01-T3, greened 03-02-T1
- [ ] `backend/tests/core/test_settings.py` — RED stubs for CORE-06 (seed defaults / list / update), created 03-01-T3, greened 03-02-T1

*Framework already installed (pytest + httpx + pytest-asyncio per `backend/pyproject.toml`) — no framework install needed. The core test package is created RED in 03-01-T3 and goes GREEN automatically when the 03-02 endpoints ship.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Shell renders with sidebar nav (smoke) | CORE-08 | e2e/manual per RESEARCH §Validation Test Map — React shell chrome has no automated suite this phase; covered by the 03-03 T4 human-verify checkpoint | Start backend + frontend, log in as admin, confirm sidebar + topbar + nav render (03-03 T4 steps) |
| Disabled-module nav entry disappears after toggle | CORE-08 | e2e/manual per RESEARCH §Validation Test Map — nav-filter / admin-menu / toggle-propagation depend on `tsc --noEmit` plus interactive browser verification, not a frontend unit test | In Modules screen, disable PLUM, confirm PLUM nav entry disappears without reload (03-03 T4) |
| Settings form persistence (company name in header) | CORE-08 | e2e/manual — visual confirmation that a saved setting round-trips to the DB and re-renders in the topbar | Edit company name in Settings, save, reload, confirm header reflects new value (03-03 T4) |

*Frontend automated coverage omission is intentional and recorded here: CORE-08 shell behaviors are marked `e2e/manual` in RESEARCH's test map. No new frontend test task was added (not trivial); the thorough 03-03 T4 human-verify checkpoint plus `tsc --noEmit` is the accepted verification path.*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references (core test package created 03-01-T3)
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
