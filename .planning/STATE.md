---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: verifying
last_updated: "2026-06-25T18:58:38.378Z"
progress:
  total_phases: 6
  completed_phases: 2
  total_plans: 7
  completed_plans: 7
  percent: 100
---

# STATE — BizNiceSweets Milestone 1

**Last updated:** 2026-06-25
**Milestone:** 1 — Foundation + PLUM

---

## Project Reference

**Core value:** A small manufacturer can run their real product lifecycle on a suite they self-host and own — no per-seat SaaS lock-in.

**Milestone goal:** Can deploy it, log in, manage vendors/customers, and design parts with multi-level BOMs and cost roll-up.

**Current focus:** Phase 02 — authentication-users COMPLETE (4/4 plans) — ready for verification

---

## Current Position

Phase: 02 (authentication-users) — COMPLETE
Plan: 4 of 4 (all complete)
**Last plan:** 02-04 (frontend auth UI) — human-verify checkpoint passed
**Status:** Phase complete — ready for verification

**Progress:**

[██████████] 100%

**Last session:** 2026-06-24T00:55:19.362Z

---

## Phase Summary

| Phase | Name | Requirements | Status |
|-------|------|--------------|--------|
| 1 | Project Scaffolding & Deployment | CORE-01, CORE-09 | Complete |
| 2 | Authentication & Users | CORE-02, CORE-03, CORE-04, CORE-05 | Complete (4/4 plans) — ready for verification |
| 3 | App Shell & Settings | CORE-06, CORE-07, CORE-08 | Not started |
| 4 | SYERP Core Hub | SYERP-01..05 | Not started |
| 5 | PLUM Parts & Revisions | PLUM-01, PLUM-02, PLUM-03 | Not started |
| 6 | PLUM BOM, Costing & Integration | PLUM-04..10 | Not started |

---

## Performance Metrics

- Phases planned: 6
- Requirements covered: 24/24
- Plans created: 7
- Plans completed: 7
- Phase 02 Plan 01: 3 tasks, 19 files, 704s
- Phase 02 Plan 02: 2 tasks, 9 files, 900s
- Phase 02 Plan 03: 2 tasks, 9 files, 1440s
- Phase 02 Plan 04: 3 tasks, 14 files, ~4500s (frontend auth UI; human-verify passed)

---

## Accumulated Context

### Key Decisions

- **Stack:** FastAPI + SQLAlchemy 2.0 + PostgreSQL (backend); React 18 + TypeScript + Tailwind + shadcn/ui (frontend)
- **Deployment:** Podman Compose (rootless containers)
- **Architecture:** Modular monolith, SYERP as hub, FK integration between modules
- **Structure chosen:** Horizontal layers with dependency-first ordering
- **Source reference:** PLUM HTML prototype (`plum/app/plm_v54.html`) is functional reference for domain logic — not code to reuse
- **PLUM-07 constraint:** Part-to-vendor links require SYERP vendors table to exist (FK); Phase 4 must precede Phase 6
- **Auth library:** PyJWT 2.13.0 + pwdlib[argon2] 0.3.0 (not python-jose — 4 CVEs; not passlib — abandoned)
- **JWT env var:** jwt_secret field reads JWT_SECRET (pydantic-settings field→env convention; no BNS_ prefix unlike bns_admin_password)
- **RBAC schema:** User↔Role↔Permission M2M with module:action codes; lazy=selectin on collection relationships for async SQLAlchemy safety
- **Seed pattern:** select-before-insert for idempotent upsert of permissions and roles (not ON CONFLICT — SQLAlchemy ORM upsert semantics vary by dialect)
- **Login audit:** auth.login_success (actor_id=user.id) and auth.login_failed (actor_id=None) written unconditionally on every login attempt (D-14 mandatory events)
- **RBAC probe:** /auth/_rbac_probe diagnostic endpoint (syerp:read gate) added for CORE-05 testing without Phase 4 SYERP routes
- **Frontend token storage:** access token held only in a module-level JS variable (`src/auth/token.ts`) — never localStorage/sessionStorage (D-06, T-02-18)
- **Silent refresh:** axios single-flight 401 interceptor (`isRefreshing` flag + `failedQueue`) serializes concurrent refreshes to avoid rotation self-logout (Pitfall 4, T-02-21); `withCredentials` sends the httpOnly refresh cookie
- **Auth UI:** ProtectedRoute layout guard (isLoading→spinner / no-user→Navigate /login / Outlet) + `useAuth` TanStack Query `/auth/me` hook; UI gating is convenience only — backend 403 is the real authz boundary (T-02-20)
- **Dev cookie:** `DEBUG=true` in `.env` disables the cookie `Secure` flag so the refresh cookie persists over `http://localhost`; prod container bakes the SPA into the image
- **Phase-2 deploy fixes (cross-plan):** added `email-validator` + documented auth env vars (`2ae8ebd`, 02-01); fixed admin-seed `MissingGreenlet` via `AsyncAttrs`/`awaitable_attrs` (`272db33`, 02-03)

### Deferred (v2)

- FLAN port
- PLUM advanced: document management, ECO workflow
- MOUSSE, CRUMB, GELATO, CRISP
- SYERP extended: inventory, POs, AP/AR
- Offline capability / Service Worker sync

### Blockers

None.

### Open Questions

None at roadmap stage.

### Deferred Follow-ups (from Phase 02, do not block phase)

- No in-app navigation shell / logout control linking Landing <-> /admin/users — deferred to Phase 3 (App Shell, CORE-06..08).
- Admin-seed/startup path has no DB-backed regression test (seed tests skip without a live DB) — the `MissingGreenlet` slipped past unit tests; recommend a seed integration test during gap-closure.

---

## Session Continuity

**To resume:** Phase 02 is complete and ready for verification. Run `/gsd-verify-work` for Phase 02, then `/gsd-transition` to Phase 03 (App Shell & Settings).

**Files on disk:**

- `.planning/PROJECT.md` — project vision and constraints
- `.planning/REQUIREMENTS.md` — 24 v1 requirements with traceability
- `.planning/ROADMAP.md` — 6-phase milestone roadmap
- `.planning/STATE.md` — this file
- `.planning/config.json` — workflow config (mode: yolo, granularity: standard)
- `.planning/codebase/` — architecture map of existing HTML prototypes

---

*State initialized: 2026-06-22*
