# Phase 1: Project Scaffolding & Deployment - Context

**Gathered:** 2026-06-23
**Status:** Ready for planning

<domain>
## Phase Boundary

Stand up the target-stack skeleton so developers can `podman-compose up` the entire stack locally and an operator can self-host it, with Alembic migrations applying cleanly on a fresh PostgreSQL instance.

**Delivers (CORE-01, CORE-09):**
- A FastAPI backend (SQLAlchemy 2.0 + PostgreSQL) that serves a health-check endpoint and auto-generated OpenAPI docs at `/docs`.
- A React/TypeScript/Tailwind/shadcn frontend skeleton.
- Alembic migrations wired up and applying cleanly on a fresh DB (initial schema/baseline).
- Podman Compose deployment that reaches a known, repeatable state from a single command.
- The directory/module skeleton that all later suites (SYERP, PLUM, …) will be built into.

**NOT in this phase:** auth/users (Phase 2), app shell/settings/module-toggle UI (Phase 3), any SYERP or PLUM feature code (Phases 4–6). Phase 1 establishes the *structure and deployment*, not the modules' business logic.

</domain>

<decisions>
## Implementation Decisions

### Repo & Module Layout
- **D-01:** Top-level repo gains `backend/`, `frontend/`, and `compose/` directories alongside the existing HTML prototype folders (`plum/`, `flan/`, etc.) and `docs/` / `.planning/`. The prototypes are left untouched as functional reference — they are NOT the deployment target and are not ported as code.
- **D-02:** Backend uses a **module-as-package (feature-based)** structure. Each suite is a self-contained Python package: `backend/app/modules/<suite>/` containing its own `models.py`, `router.py`, `schemas.py`, `service.py`. Shared concerns (DB session, config, base classes, the module registry) live in `backend/app/core/`.
- **D-03:** A **single Alembic migration history** for the whole application (one `alembic/` tree), not per-module histories.
- **D-04:** A lightweight **module registry** + **per-module Podman Compose profiles** so a deployment can ship a subset of modules — e.g. `podman-compose --profile plum up` ships PLUM standalone, `--profile full` ships everything — over the same shared PostgreSQL database. This is what satisfies the "run a suite individually, or run suites together unified" requirement.
- **D-05:** Structure must be **graduate-able to true plugin distributions** (each suite as its own installable Python package with entry-points) later, without a rewrite. Phase 1 does NOT build the plugin machinery — it just keeps module boundaries clean enough that the move is a packaging step.
- **D-06:** **SYERP is the always-on foundation (bundled hub), not an optional module.** "Download just PLUM" means *platform + SYERP-hub + PLUM*, so cross-module FKs (e.g. PLUM part → SYERP vendor, PLUM-07) always resolve. Optional installable modules are PLUM/FLAN/MOUSSE/CRUMB/GELATO/CRISP. There are deliberately **no "what if the dependency is missing" / graceful-degradation code paths** in the chosen model.

### Frontend Build Tool
- **D-07:** Frontend is a **Vite + React SPA** (single-page app, static-file output). Client-side routing via **React Router**; data-fetching via **TanStack Query** against the FastAPI backend. Chosen because the suite is internal/behind-auth (no SEO need), offline-capable later (service worker + IndexedDB is far simpler in a plain SPA), and trivially self-hosted (static files next to the API). Next.js was considered and rejected — its server/API layer is redundant with FastAPI, SSR fights offline-first, and it adds a Node runtime to self-host.
- **D-08:** In production the built static frontend assets are **served by the backend container** (one module = one deployable unit). A separate nginx/static container is deferred (see Deferred Ideas).

### Fresh-Deploy Bootstrap
- **D-09:** **Auto-migrate on startup via the backend container entrypoint:** wait for Postgres to be healthy → run `alembic upgrade head` → launch the API (uvicorn). Single `podman-compose up` reaches a known schema state with no manual step. Safe because the deployment is single-instance self-hosted (no multi-replica migration race). A dedicated one-shot migration service was considered and deferred (see Deferred Ideas).
- **D-10:** **Real seed data is deferred to Phase 2** (the first admin/user model arrives with auth). Phase 1 only **scaffolds the seed hook/pattern** so it's ready to use later.

### Local Dev Workflow
- **D-11:** Provide **both** paths: the **containerized one-command setup is the canonical/onboarding path** — a dev Compose overlay with source volume mounts + hot-reload (`uvicorn --reload`, Vite HMR). The **native-run option is documented** (own Python venv + Node, DB optionally still in a container) as a fast-debug escape hatch, important because the user develops on Windows 10 where container file-watching can be slow/flaky.

### Claude's Discretion
- Exact contents of the Phase 1 baseline migration (may be minimal — the migration framework wired up with an initial/empty baseline is acceptable; substantive tables arrive with their owning modules in later phases).
- Health-check depth (liveness vs readiness incl. DB connectivity) — planner/researcher decides.
- CI, pre-commit, linter/formatter (ruff/black, eslint/prettier) setup — not discussed; planner may scaffold sensible defaults or defer.
- Config/secrets conventions (`.env` templates, env-var names) — planner may choose standard patterns; must support an operator configuring DB credentials for a repeatable self-hosted deploy.
- Naming of the dev compose overlay (`compose.dev.yml` / override / profile) and exact profile names.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project constraints & decisions (authoritative for stack/architecture)
- `.planning/PROJECT.md` — locked tech stack, modular-monolith architecture, SYERP-as-hub, self-hosted + offline + open-core constraints, and Key Decisions table.
- `.planning/REQUIREMENTS.md` — CORE-01 (containerized Podman Compose deployment) and CORE-09 (versioned Alembic migrations applying cleanly on fresh deploy) are the two requirements this phase satisfies.
- `.planning/ROADMAP.md` §"Phase 1" — phase goal and the 4 success criteria this phase is verified against.

### Background / existing-asset reference (context, not a build target)
- `.planning/codebase/STACK.md`, `.planning/codebase/ARCHITECTURE.md`, `.planning/codebase/STRUCTURE.md`, `.planning/codebase/CONVENTIONS.md`, `.planning/codebase/CONCERNS.md` — describe the **existing HTML prototypes** (PLUM v54, FLAN v24). Useful to understand the domain being re-platformed; the prototypes are NOT the target stack and are not ported as code.
- `docs/decisions.md`, `docs/features/INDEX.md` — pre-GSD architecture decisions and the 221-requirement feature catalog; background reference for the broader vision.

No external ADR/spec dictates the scaffolding specifics beyond the constraints in PROJECT.md — the implementation decisions above are the authoritative source for this phase.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **None as code.** This phase is greenfield for the target stack — the repo currently contains only single-file HTML prototypes (`plum/app/plm_v54.html`, `flan/app/prj-mgmt-v24.html`) which are vanilla-JS/localStorage and explicitly NOT reused. They serve only as the functional reference for later module phases.

### Established Patterns
- The project's locked conventions (PascalCase domain namespaces, camelCase functions) in `.planning/codebase/CONVENTIONS.md` describe the *prototypes* and do not bind the new Python/TypeScript stack. New stack should follow idiomatic FastAPI/SQLAlchemy and React/TS conventions.

### Integration Points
- This phase produces the skeleton that every later phase plugs into: `backend/app/core/` (DB session, config, module registry), `backend/app/modules/<suite>/` (where SYERP lands in Phase 4, PLUM in Phases 5–6), the single Alembic history, and the Compose profile mechanism. Get these boundaries right — they are the integration surface for the whole milestone.

</code_context>

<specifics>
## Specific Ideas

- Hard requirement that drove the architecture: **a user can download and run a single suite (e.g. PLUM) on its own, AND can later run multiple suites together in a unified way** over a shared database. Realized via module-as-package + module registry + per-module Compose profiles, with SYERP bundled as the always-on hub so dependent modules' FKs always resolve.
- Strong preference for **simplest-operator-experience**: one `podman-compose up` command should reach a fully working, repeatable state with no manual migration or setup step.

</specifics>

<deferred>
## Deferred Ideas

- **True plugin distributions** (each suite as its own installable Python package with entry-points; enables third-party / open-core premium add-ons) — structure now keeps this cheap, but the machinery is a later milestone.
- **Declared-dependency (auto-pull) or graceful-degradation module models** — only if a real need to run a module *without* SYERP appears. Current model is SYERP-as-foundation.
- **Dedicated one-shot migration service** (migration as a distinct, observable, auditable Compose step) — revisit if medical-device audit needs grow; current model is entrypoint auto-migrate.
- **Separate nginx/static frontend container** — current model serves static assets from the backend container.
- **Real seed data** (first admin account, demo dataset) — Phase 2, once the user/auth model exists.
- **CI / pre-commit / linter-formatter pipeline** — not decided in discussion; can be scaffolded by the planner or deferred.

None of these are blockers for Phase 1.

</deferred>

---

*Phase: 1-Project Scaffolding & Deployment*
*Context gathered: 2026-06-23*
