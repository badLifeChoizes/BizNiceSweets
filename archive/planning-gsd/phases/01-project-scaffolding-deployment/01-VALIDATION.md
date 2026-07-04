---
phase: 1
slug: project-scaffolding-deployment
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-23
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.x + pytest-asyncio 1.x + httpx |
| **Config file** | `backend/pyproject.toml` (`[tool.pytest.ini_options]`, `asyncio_mode = "auto"`) — Wave 0 installs |
| **Quick run command** | `pytest backend/tests/test_health.py -x` |
| **Full suite command** | `pytest backend/tests/ -x` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest backend/tests/test_health.py -x`
- **After every plan wave:** Run `pytest backend/tests/ -x`
- **Before `/gsd-verify-work`:** Full suite must be green AND the 4 smoke commands pass
- **Max feedback latency:** ~15 seconds

---

## Per-Task Verification Map

> Filled by the planner / Nyquist auditor as tasks are written. Seeded from RESEARCH.md requirement→test map.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| TBD | TBD | TBD | CORE-01 | — | API + frontend + DB start without manual steps | smoke | `podman-compose up -d && curl -f http://localhost:8000/health/live` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | CORE-01 | — | OpenAPI docs reachable | smoke | `curl -f http://localhost:8000/docs` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | CORE-09 | — | Alembic migrations apply on fresh DB | integration | `pytest backend/tests/test_migrations.py -x` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | CORE-09 | — | `/health/ready` 200 with DB connected | integration | `pytest backend/tests/test_health.py::test_readiness -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `backend/tests/__init__.py` — test package
- [ ] `backend/tests/conftest.py` — async test client + DB session fixtures
- [ ] `backend/tests/test_health.py` — liveness + readiness (CORE-01, CORE-09)
- [ ] `backend/tests/test_migrations.py` — verifies `alembic upgrade head` runs clean on a fresh/empty DB (CORE-09)
- [ ] `backend/pyproject.toml` — `[tool.pytest.ini_options]` with `asyncio_mode = "auto"`
- [ ] Framework install via `requirements-dev.txt` (`pytest`, `pytest-asyncio`, `httpx`)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| `podman-compose up` reaches a repeatable healthy state from a single command on a clean host | CORE-01 | Full container orchestration on the operator host (podman/WSL2) is environment-specific and not reproducible inside the unit-test sandbox | From repo root: `podman-compose up -d`; wait for healthchecks; confirm `curl -f localhost:8000/health/ready` (200), `curl -f localhost:8000/docs` (200), frontend served; `podman-compose down -v` then `up` again reaches the same state |

*Scripted smoke commands above reduce but do not fully replace this manual gate.*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
