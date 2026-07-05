# DECISIONS — BizNiceSweets
Updated: 2026-07-04

Recovered decisions are marked `(recovered)` with their original source (now archived).
Numbering is append-only.

## Product & Architecture

- **D-1 (recovered, 2025-12-20):** Business domain = hybrid open-source business suite of 7
  integrated suites (SYERP, PLUM, FLAN, MOUSSE, CRUMB, GELATO, CRISP), each usable standalone
  but integrating when present. *Source: archived `docs/decisions.md` #1.*
- **D-2 (recovered, 2025-12-20):** Manufacturing (facilities, work centers, routings) lives
  in MOUSSE, not PLUM — PLUM is product *development*; released products hand off to MOUSSE.
  *Source: archived `docs/decisions.md` #2.*
- **D-3 (recovered, 2025-12-21):** Modular monolith over one shared PostgreSQL database,
  **SYERP as hub**, modules integrate via foreign keys — simpler ops than microservices at
  this scale. *Source: archived `docs/ROADMAP.md`; realized in `backend/app/core/registry.py`.*
- **D-4 (recovered, 2025-12-21):** Full rewrite of all suites onto FastAPI + SQLAlchemy 2.0 +
  PostgreSQL / React + TypeScript + Tailwind + shadcn/ui, deployed via Podman Compose.
  Supersedes the earlier client-side DataService/localStorage plan (archived
  `docs/decisions.md` #4) — prototypes can't scale to a shared team system.
- **D-5 (recovered, 2025-12-21):** Self-hosted + offline-capable + open-core licensing —
  user ownership, no SaaS lock-in, permissive deps only.
- **D-6 (recovered, 2026-06-22):** Dependency-first phase order (Foundation → Product Dev →
  Operations → Customer/Logistics → Quality); a value-first reorder was considered and
  explicitly rejected. *Source: archived `.planning/PROJECT.md`.*
- **D-7 (recovered, 2026-06-22):** Milestone 1 = thin foundation + the PLUM port together,
  so the milestone ends with a usable tool, not just plumbing.

## Technical (recovered from GSD phase work, June 2026)

- **D-8 (recovered):** Auth = PyJWT 2.13 + pwdlib[argon2] — not python-jose (CVEs), not
  passlib (abandoned). Access token lives only in a module-level JS variable
  (`frontend/src/auth/token.ts`), never web storage; refresh via httpOnly cookie with
  single-flight axios 401 interceptor.
- **D-9 (recovered):** RBAC = User↔Role↔Permission M2M with `module:action` permission codes;
  UI gating is convenience only — backend 403 is the authz boundary.
- **D-10 (recovered):** Seeds are idempotent select-before-insert, run at startup lifespan;
  migrations auto-apply on container boot (`backend/entrypoint.sh`).
- **D-11 (recovered):** All PLUM cost/qty math uses `Numeric(18,6)`/Python `Decimal` — never
  float; export serializes Decimal as string.
- **D-12 (recovered):** One-Released-revision-per-part enforced at DB level (partial unique
  index), not just in service code.
- **D-13 (recovered):** Effective-cost resolution order = vendor price → manual cost → BOM
  roll-up → uncosted; cost snapshot frozen at release time.
- **D-14 (recovered):** Import is two-step preview/commit, upsert-never-delete, stateless
  re-parse on commit, 10MB guard.
- **D-15 (recovered):** Tailwind v4 requires shadcn color tokens registered via
  `@theme inline` in `src/index.css`, or panels render transparent app-wide.

## Adoption decisions (2026-07-04)

- **D-ADOPT-1:** Project adopted into ZJ. `.zj/` is the sole planning source of truth; the
  GSD system (`.planning/`) and the superseded program-planning docs (`docs/ROADMAP.md`,
  `docs/decisions.md`) are archived under `archive/`. Requirement IDs (CORE/SYERP/PLUM/FLAN)
  carried over verbatim into `.zj/SRD.md`.
- **D-ADOPT-2 (owner):** Phase 7 (close v1.0 gaps) adopted **as-is** from the GSD plans —
  same 4-plan scope; `/zj:plan 7` translates rather than re-derives.
- **D-ADOPT-3 (owner):** Next milestone after v1.0 = **SYERP extended + MOUSSE**
  (dependency-first confirmed), ahead of the FLAN port and PLUM advanced.
- **D-ADOPT-4 (owner):** HTML prototypes (`plum/app/plm_v54.html`, `flan/app/prj-mgmt-v24.html`)
  are **frozen reference only** — no further development or bug fixes; they exist as
  domain-logic reference for porting.
- **D-ADOPT-5 (owner):** The unfinished suite-documentation and integration-spec items from
  `docs/tasks/chore-architecture-planning.md` are kept as backlog, not abandoned.
- **D-ADOPT-6:** Requirement-status corrections at adoption: `docs/features/requirements-progress.md`
  claims PLUM-04..10 "Complete" — contradicted by the live audit (PLUM-07/10 broken at
  runtime, rest unverified). SRD statuses follow the code/audit, not the progress doc;
  reconciliation is Phase 7 scope.

## Phase 7 planning (2026-07-04)

- **D-P7-1 (owner):** Phase-7 human-verify runs against the **Vite dev server (http://localhost:5173)
  only** — no `frontend/dist` / container-image rebuild task. *Why:* the served :8000 bundle
  predates Phase 3 (stale UI), but Vite dev always reflects current source, so it verifies the
  fixes without build work; the stale production bundle stays a separate backlog item
  ("Rebuild frontend/dist + container image").
- **D-P7-2 (owner):** Phase 7 stays scoped to the adopted 4 GSD plans **plus one task** to
  correct the root `CLAUDE.md` "Technology Stack" / "Architecture" sections (they still describe
  the frozen vanilla-JS prototypes — "No server-side runtime", "no npm"). *Why:* cheap, sits
  right next to the work, and reduces future-agent confusion. CI (the process gap that let the
  `SyerpPartner` bug ship) was explicitly **not** folded in — it stays a p1 backlog item for
  its own phase, honoring D-ADOPT-2 (adopt Phase 7 as-is).

## Phase 7 build (2026-07-04)

- **D-P7-3 (owner, at build):** `bugfix-plum-v1-gaps` is branched off
  **`chore-architecture-planning`**, not `master` as the PLAN originally stated. *Why:* `master`
  (HEAD `f4e2bd3`, 2025-12-20) predates the entire re-platform — it contains only the legacy
  prototypes and has **no `backend/`, `frontend/`, or `.zj/`**. All 212 commits of real work,
  including the code Phase 7 fixes and the plan itself, live on `chore-architecture-planning`
  (a strict superset of master). Branching off master would give an empty tree with nothing to
  fix. Eventual integration of `chore-architecture-planning` → `master` is a separate concern
  outside Phase 7. The plan's dedicated-branch intent is preserved; only the base changed.

- **D-P7-4 (owner, at build):** The PLUM live-DB test harness is **fundamentally broken and its
  repair is deferred** ("until it becomes blocking or it's asked for"). Discovered at build: the
  `skip_if_no_db` suite has always silently skipped (broken psycopg2-URL probe), and once the
  probe is fixed all 33 PLUM tests fail on a module-level async-engine/event-loop mismatch, plus
  missing `admin-user` seeding and no per-test isolation (full root-cause list in BACKLOG.md p1).
  Fixing it is real test-infra work outside the adopted 4-plan scope. *Consequence:* **SC4 is
  relaxed** for Phase 7 — the PLUM fixes are proven by the Task 6 human-verify at :5173 (D-P7-1,
  regression checks 9–12 cover SC1/SC2/SC3 end-to-end) plus lightweight standalone async scripts
  run against live Postgres, **not** by the pytest suite. The `pytest tests/plum/` "green" clause
  in Tasks 1/2/5 Done-when is superseded by these. Harness repair tracked as BACKLOG p1.
