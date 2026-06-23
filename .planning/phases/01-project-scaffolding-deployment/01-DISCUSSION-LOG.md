# Phase 1: Project Scaffolding & Deployment - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-23
**Phase:** 1-Project Scaffolding & Deployment
**Areas discussed:** Repo & module layout, Module dependencies, Frontend build tool, Fresh-deploy bootstrap, Local dev workflow

User requested all four pre-identified areas be discussed, with each option explained including the "why" behind it (low prior confidence in these decisions). Discussion was run in a teaching style — trade-offs laid out before each choice.

---

## Repo & Module Layout — module structure

| Option | Description | Selected |
|--------|-------------|----------|
| A. Module-as-package (feature-based) | One self-contained package per suite with own models/router/schemas/service; shared core/; single Alembic history | ✓ |
| C. Plugin distributions | Each suite its own installable Python package with entry-points; third-party add-ons; heavy machinery now | |
| B. Layer-based | Group by code kind (models/, routers/, services/); scatters modules, no clean disable boundary | |

**User's choice:** A — with a critical added requirement (see notes), realized as A + registry + compose profiles, graduate-able to C.
**Notes:** User stated a hard requirement: "a user can download just PLUM and run it on its own, but also if they want to expand they need to be able to run the suites together in a unified way." This ruled out B, confirmed A as the structure, and added a module registry + per-module Compose profiles to ship subsets.

---

## Module Dependencies — handling cross-module FKs when run standalone

| Option | Description | Selected |
|--------|-------------|----------|
| 1. SYERP = always-on foundation (bundled hub) | "Just PLUM" = platform + SYERP + PLUM; FKs always resolve; no missing-dependency paths | ✓ |
| 2. Declared dependencies (auto-pull) | Modules declare requirements; installing PLUM auto-installs SYERP; more machinery | |
| 3. Graceful degradation | PLUM runs with no SYERP; vendor features hide; complex, harder to audit | |

**User's choice:** 1 — SYERP as always-on foundation.
**Notes:** Resolves the standalone-vs-unified requirement cleanly while preserving the FK hub model and avoiding degradation branches (better for medical-device audit posture).

---

## Frontend Build Tool

| Option | Description | Selected |
|--------|-------------|----------|
| Vite + React SPA | Static-file SPA + React Router + TanStack Query against FastAPI; best for internal/authed/offline/self-hosted | ✓ |
| Next.js | Full framework w/ SSR + own API layer; redundant with FastAPI, fights offline-first, adds Node runtime | |

**User's choice:** Vite + React SPA.
**Notes:** Production static build served by the backend container (one deployable unit); separate nginx container deferred.

---

## Fresh-Deploy Bootstrap

| Option | Description | Selected |
|--------|-------------|----------|
| Auto-migrate on startup (entrypoint) | Wait for PG healthy → alembic upgrade head → start API; one command, automatic | ✓ |
| Dedicated migration service | Separate one-shot service runs migrations; distinct/auditable step; extra service now | |
| Manual migration step | Operator migrates by hand; breaks "single command" criterion | |

**User's choice:** Auto-migrate on startup.
**Notes:** Real seed data deferred to Phase 2 (no user model yet); seed hook scaffolded now.

---

## Local Dev Workflow

| Option | Description | Selected |
|--------|-------------|----------|
| Both: containerized canonical + native documented | One-command containerized dev (overlay, mounts + hot-reload) + documented native escape hatch | ✓ |
| Fully containerized only | One command; best parity but Windows file-watching slow/flaky | |
| Hybrid: DB in container, app native | Fastest debug loop but every contributor manages Python + Node versions | |

**User's choice:** Both — containerized canonical, native documented.
**Notes:** Native path matters because the user develops on Windows 10 where container file-watching can be slow.

---

## Claude's Discretion

- Phase 1 baseline migration contents (minimal/empty baseline acceptable).
- Health-check depth (liveness vs readiness incl. DB).
- CI / pre-commit / linter-formatter setup (not discussed).
- Config/secrets conventions (`.env` templates, env-var names) — must support operator-configured DB credentials.
- Naming of dev compose overlay and profile names.

## Deferred Ideas

- True plugin distributions (graduate from module-as-package later).
- Declared-dependency / graceful-degradation module models.
- Dedicated one-shot migration service (if audit needs grow).
- Separate nginx/static frontend container.
- Real seed data (admin/demo) — Phase 2.
- CI / pre-commit / linter-formatter pipeline.
