---
phase: 5
slug: plum-parts-revisions
status: ready
nyquist_compliant: true
wave_0_complete: false
created: 2026-06-28
updated: 2026-06-29
---

# Phase 5 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework (backend)** | pytest 7.x + pytest-asyncio (`asyncio_mode = "auto"`) |
| **Framework (frontend)** | vitest + @testing-library/react (jsdom) |
| **Config file (backend)** | `backend/pyproject.toml` (`[tool.pytest.ini_options]`) |
| **Config file (frontend)** | `frontend/vite.config.ts` (`test.environment = "jsdom"`) |
| **Quick run command (backend)** | `cd backend && python -m pytest tests/plum/ -x` |
| **Quick run command (frontend)** | `cd frontend && npx vitest run src/routes/plum/` |
| **Full suite (backend)** | `cd backend && python -m pytest` |
| **Full suite (frontend)** | `cd frontend && npx vitest run` |
| **Estimated runtime** | ~30 seconds (quick) / ~90 seconds (full) |

---

## Sampling Rate

- **After every task commit:** Run the quick run command for the side touched (backend or frontend).
- **After every plan wave:** Run the full suite for the side touched.
- **Before `/gsd:verify-work`:** Both full suites must be green.
- **Max feedback latency:** ~90 seconds.

Note: backend integration tests require a live PostgreSQL DB; without one they `skip` cleanly via `skip_if_no_db` (collection/import must still succeed). The frontend smoke test mocks `@/api/client` and needs no DB.

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 05-01-01 | 01 | 1 | PLUM-01/02/03 | T-05-01 | Models define plum_ tables; no ORM relationships | import | `cd backend && python -c "from app.modules.plum import models, schemas"` | ❌ W0 | ⬜ pending |
| 05-01-02 | 01 | 1 | PLUM-01/02/03 | T-05-01/02/03 | Migration 0005 + partial unique index + idempotent seed | import + grep | `cd backend && python -c "import app.core.models"` | ❌ W0 | ⬜ pending |
| 05-01-03 | 01 | 1 | PLUM-01/02/03 | — | Wave 0 backend test scaffold collectable | collect | `cd backend && python -m pytest tests/plum/ --collect-only -q` | ❌ W0 (creates) | ⬜ pending |
| 05-02-01 | 02 | 2 | PLUM-01/02 | T-05-06/07 | CRUD + search + label/part-number gen + FSM table | import + assert | `cd backend && python -c "from app.modules.plum import service"` | ✅ (05-01) | ⬜ pending |
| 05-02-02 | 02 | 2 | PLUM-01/02/03 | T-05-04/05/08/09 | FSM + supersede + RBAC + audit endpoints green | integration | `cd backend && python -m pytest tests/plum/ -x -q` | ✅ (05-01) | ⬜ pending |
| 05-03-01 | 03 | 3 | PLUM-01/02 | T-05-10 | PlumNav/ArchivePartDialog/PartSheet type-check | type | `cd frontend && npx tsc --noEmit` | ❌ W0 (creates) | ⬜ pending |
| 05-03-02 | 03 | 3 | PLUM-01/02 | T-05-11 | Parts list renders + empty state smoke test | unit | `cd frontend && npx vitest run src/routes/plum/PartsList.test.tsx` | ❌ W0 (creates) | ⬜ pending |
| 05-04-01 | 04 | 4 | PLUM-03 | T-05-12/14 | NewRevisionDialog/AdvanceStatusDialog type-check | type | `cd frontend && npx tsc --noEmit` | ✅ (05-03) | ⬜ pending |
| 05-04-02 | 04 | 4 | PLUM-01/03 | T-05-12/13 | PartDetail + timeline + App.tsx routes; smoke green | unit + type | `cd frontend && npx vitest run src/routes/plum/` | ✅ (05-03) | ⬜ pending |
| 05-04-03 | 04 | 4 | PLUM-01/02/03 | T-05-07/14 | End-to-end lifecycle (manual) | human-check | manual (see 05-04 Task 3) | n/a | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

**Sampling continuity:** No 3 consecutive tasks lack an automated verify. 05-04-03 is the only human-check task and it is the terminal checkpoint, immediately preceded by two automated tasks (05-04-01, 05-04-02).

---

## Wave 0 Requirements

- [ ] `backend/tests/plum/__init__.py` — test package init (05-01 Task 3)
- [ ] `backend/tests/plum/test_parts.py` — PLUM-01/02 backend tests (05-01 Task 3, mirrors `tests/syerp/test_partners.py`)
- [ ] `backend/tests/plum/test_revisions.py` — PLUM-03 revision FSM tests (05-01 Task 3)
- [ ] `frontend/src/routes/plum/PartsList.test.tsx` — smoke test (05-03 Task 2, mirrors `Vendors.test.tsx`)

Framework is already installed (pytest + vitest from Phases 1-4); no framework install needed.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Full part + revision lifecycle (create → search/filter → detail → submit → release → new revision → supersede → archive/restore → immutability) | PLUM-01/02/03 | Visual + interactive flow across multiple screens; release confirmation and timeline rendering need human eyes | 05-04 Task 3 `how-to-verify` steps 1-10 |

The underlying behaviors (FSM transitions, supersede, immutability 422, search/filter) each have automated backend coverage in `tests/plum/`; the manual check confirms the end-to-end UX integration.

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or are Wave 0 / human-check terminal checkpoints
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references (4 scaffold files created in 05-01 Task 3 + 05-03 Task 2)
- [x] No watch-mode flags (all vitest runs use `run`, pytest uses `-x`)
- [x] Feedback latency < 90s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-06-29
