# BACKLOG — BizNiceSweets
Updated: 2026-07-04 (seeded at adoption from the v1.0 milestone audit, codebase map, and the
kept items of `docs/tasks/chore-architecture-planning.md` — owner decision D-ADOPT-5)

## p1 — quality/infra debt that already bit once

- [ ] **CI pipeline** — no CI exists anywhere (no `.github/`, no pipeline config). Lint/test
  are manual; the `SyerpPartner` bug shipped through 4 plans because live-DB tests never ran.
  Minimum: ruff + pytest + eslint + vitest on push; stretch: a live-Postgres test job so
  `skip_if_no_db` tests actually run.
- [ ] **Seed/startup integration test** — admin-seed path has no DB-backed regression test
  (a `MissingGreenlet` slipped past unit tests in Phase 2).
- [ ] **Rebuild `frontend/dist` + container image** — production bundle predates Phase 3;
  `:8000` serving doesn't reflect Phases 3–6 UI until rebuilt. (May fold into Phase 7 verify.)
- [ ] **Refresh root `CLAUDE.md` stack/architecture sections** — they still describe only the
  vanilla-JS prototypes ("no server-side runtime", "no npm") and contradict the live
  FastAPI/React codebase; also Windows-path references on a now-Linux workspace.

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
