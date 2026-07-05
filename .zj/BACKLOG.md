# BACKLOG — BizNiceSweets
Updated: 2026-07-04 (seeded at adoption from the v1.0 milestone audit, codebase map, and the
kept items of `docs/tasks/chore-architecture-planning.md` — owner decision D-ADOPT-5)

## p1 — quality/infra debt that already bit once

- [ ] **CI pipeline** — no CI exists anywhere (no `.github/`, no pipeline config). Lint/test
  are manual; the `SyerpPartner` bug shipped through 4 plans because live-DB tests never ran.
  Minimum: ruff + pytest + eslint + vitest on push; stretch: a live-Postgres test job so
  `skip_if_no_db` tests actually run.
- [ ] **PLUM live-DB test harness never runs (4 root causes confirmed 2026-07-04, Phase 7)** —
  deferred by owner (D-P7-4) until blocking/asked. The `skip_if_no_db` suite has *always*
  silently skipped, even inside the API container. Confirmed causes: (1) `tests/conftest.py`
  `_check_db_available()` passes the `postgresql+psycopg2://` SQLAlchemy URL to raw
  `psycopg2.connect()`, which errors `invalid dsn` → probe always False → all 33 PLUM tests
  skip (1-line fix: `.replace("+psycopg2","")`); (2) with the probe fixed, every test fails
  `sqlalchemy.exc.InterfaceError` — the module-level async engine (`app/core/db.py`) is bound
  to a different event loop than each pytest-asyncio test (needs NullPool or a per-test
  engine/session fixture); (3) no `admin-user` User is seeded though tests auth as
  `subject="admin-user"`; (4) no per-test isolation → `uq_plum_part_number` IntegrityError
  collisions on rerun against the persistent dev DB. This is the exact silent-skip that let
  the `SyerpPartner` 500 ship. Until fixed, PLUM fixes are proven by human-verify (D-P7-1) +
  standalone async scripts, not the pytest suite.
- [ ] **Seed/startup integration test** — admin-seed path has no DB-backed regression test
  (a `MissingGreenlet` slipped past unit tests in Phase 2).
- [ ] **Rebuild `frontend/dist` + container image** — production bundle predates Phase 3;
  `:8000` serving doesn't reflect Phases 3–6 UI until rebuilt. (May fold into Phase 7 verify.)
- [x] **Refresh root `CLAUDE.md` stack/architecture sections** — done in Phase 7 Task 4
  (commit `5db8278`); Technology Stack + Architecture now describe the live FastAPI/React stack
  and cite `.zj/codebase/MAP.md`. (Any remaining Windows-path references elsewhere are out of
  that task's scope.)

## p2 — architecture & docs

- [ ] **Split `backend/app/modules/plum/service.py` (~3,000 lines)** before MOUSSE/CRISP copy
  the pattern — the monolith-file smell the prototypes suffered from. Target: before/at
  Phase 10 (MOUSSE).
- [ ] **Integration specs** (kept from chore-architecture-planning): PLUM↔MOUSSE,
  PLUM↔SYERP, FLAN↔SYERP, shared vendor/document infrastructure.
- [ ] **Suite documentation sets** (kept): SYERP, CRUMB, MOUSSE, CRISP, GELATO under
  `docs/features/{suite}/` per `_templates/`.
- [ ] **Remove dead `frontend/src/components/ProtectedRoute.tsx`** — replaced by AppShell;
  only its own test references it.
- [ ] **Dependency license audit** (NFR-2) — required before public open-source release.

## p3 — hygiene

- [ ] **Linux-native stack launcher** — only launcher is PowerShell (`scripts/uat.ps1`);
  add a bash equivalent or document the manual compose commands prominently.
- [ ] **Root placeholder suite dirs** (`syerp/`, `crumb/`, `mousse/`, `crisp/`, `gelato/`
  contain only CLAUDE.md) — confusing next to real code at `backend/app/modules/`; prune or
  clearly mark.
- [ ] **Repo weight** — `plum/` 33 MB + `flan/` 8.7 MB of frozen prototypes/archives (22
  archived FLAN versions, 2.6 MB JSON DB). Consider pruning archives or git-lfs once ports
  supersede them (prototypes are frozen per D-ADOPT-4).
- [ ] **Milestone bookkeeping** — GSD Wave-0 `wave_0_complete` flags were never set for any
  phase (historical; relevant only if auditing the archive).
