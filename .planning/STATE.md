---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: executing
last_updated: "2026-06-29T02:33:32.294Z"
progress:
  total_phases: 6
  completed_phases: 4
  total_plans: 18
  completed_plans: 16
  percent: 67
---

# STATE — BizNiceSweets Milestone 1

**Last updated:** 2026-06-28
**Milestone:** 1 — Foundation + PLUM

---

## Project Reference

**Core value:** A small manufacturer can run their real product lifecycle on a suite they self-host and own — no per-seat SaaS lock-in.

**Milestone goal:** Can deploy it, log in, manage vendors/customers, and design parts with multi-level BOMs and cost roll-up.

**Current focus:** Phase 05 — plum-parts-revisions

---

## Current Position

Phase: 05 (plum-parts-revisions) — EXECUTING
Plan: 3 of 4
**Last plan:** 05-02 (PLUM service + router; Wave 0 tests green)
**Status:** Ready to execute

**Progress:**

[█████████░] 89%

**Last session:** 2026-06-29T02:33:32.279Z

---

## Phase Summary

| Phase | Name | Requirements | Status |
|-------|------|--------------|--------|
| 1 | Project Scaffolding & Deployment | CORE-01, CORE-09 | Complete |
| 2 | Authentication & Users | CORE-02, CORE-03, CORE-04, CORE-05 | Complete (4/4 plans) — ready for verification |
| 3 | App Shell & Settings | CORE-06, CORE-07, CORE-08 | Complete (3/3 plans) — ready for verification |
| 4 | SYERP Core Hub | SYERP-01..05 | Complete (4/4 plans) — human-verify approved |
| 5 | PLUM Parts & Revisions | PLUM-01, PLUM-02, PLUM-03 | Not started |
| 6 | PLUM BOM, Costing & Integration | PLUM-04..10 | Not started |

---

## Performance Metrics

- Phases planned: 6
- Requirements covered: 24/24
- Plans created: 10
- Plans completed: 10
- Phase 02 Plan 01: 3 tasks, 19 files, 704s
- Phase 02 Plan 02: 2 tasks, 9 files, 900s
- Phase 02 Plan 03: 2 tasks, 9 files, 1440s
- Phase 02 Plan 04: 3 tasks, 14 files, ~4500s (frontend auth UI; human-verify passed)
- Phase 03 Plan 01: 3 tasks, 12 files, 282s (backend data layer: modules + settings tables)
- Phase 03 Plan 02: 2 tasks, 9 files, 420s (modules + settings API routers, /me permissions)
- Phase 03 Plan 03: 4 tasks, 14 files, ~30min (app shell, settings, modules UI; human-verify approved)
- Phase 04 Plan 01: 3 tasks, 7 files, ~25min (SYERP data foundation: models, migration 0004, CoA seed, Wave 0 tests)
- Phase 04 Plan 02: 3 tasks, 3 files, ~25min (SYERP Partner API: schemas, service, router; Wave 0 tests green)
- Phase 04 Plan 03: 2 tasks, 6 files, ~5min (SYERP Partner UI: Vendors, Customers, PartnerSheet, PartnerArchiveDialog; Wave 0 tests green)
- Phase 04 Plan 04: 2 tasks (1 auto + human-verify), 7 files, ~20min (GLAccounts read-only CoA screen + SYERP route wiring; human-verify approved after UAT; 4 UAT follow-up fixes: Tailwind v4 tokens, country validation/error toast, catch-all route, SYERP sub-nav tab strip)
- Phase 05 Plan 01: 3 tasks, 11 files, ~35min (PLUM data foundation: models, migration 0005, seed, Wave 0 tests; 14 tests collected)
- Phase 05 Plan 02: 2 tasks, 2 files, ~30min (PLUM service + router; FSM, RBAC, audit, label generation; Wave 0 tests green/skip)

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
- **App shell (Phase 3):** `AppShell` layout route merges the auth guard (replaces ProtectedRoute; no nested layout routes — Pitfall 3). Client-side nav = enabled modules ∩ `user.permissions`, admin role is wildcard (D-04). `useModules` overrides global staleTime/refetchOnWindowFocus for toggle propagation; toggle mutation invalidates the exact `['core','modules']` key the sidebar reads (D-09). Company name renders for all authenticated users (settings GET is any-auth, not admin)
- **Toast infra (Phase 3):** added `sonner` as the project's first toast library (no toast infra existed) — Settings save + Module toggle feedback
- **Dist staleness (Phase 3):** production `frontend/dist` predates Phase 3 (built in Phase 1); Phase-3 UI verified via Vite dev overlay (:5173). A `frontend/dist` + image rebuild is needed before production `:8000` serving reflects the new shell
- **SYERP migration convention (Phase 4):** migration 0004 hand-authored (no live DB available in dev) following 0002/0003 convention; down_revision chains onto 0003
- **SYERP CoA seed (Phase 4):** `_STANDARD_COA` uses `parent_code` string keys (not raw integer IDs); two-pass insert resolves parent codes to DB integer IDs at seed time — portable across environments
- **SYERP archive pattern (Phase 4, 04-02):** Archive flows through PATCH `{active: false}`; router compares pre-state active flag to emit `partner.archived` vs `partner.updated` audit action — no separate /archive endpoint
- **SYERP partner code uniqueness (Phase 4, 04-02):** User-supplied duplicate code returns 409 Conflict; auto-generated code collision retries once with fresh code (distinguishes user intent from race condition)
- **PartnerRead type location (Phase 4, 04-03):** PartnerRead TypeScript interface exported from PartnerSheet.tsx — consumed by Vendors, Customers, and PartnerArchiveDialog to keep a single source of truth without a separate types file
- **Partner currency default (Phase 4, 04-03):** formCurrency initializes to 'USD' in React state; corrects to settings default_currency on first TanStack Query cache hit — avoids uncontrolled Select issues while supporting the settings-driven default
- **SYERP nav landing (Phase 4, 04-04):** sidebar renders one NavLink per module at `/${mod.key}`, so SYERP lands on `/syerp`; App.tsx adds a `Navigate replace` redirect `/syerp → /syerp/vendors` so the entry resolves to a real screen while keeping the sidebar convention generic
- **GLAccounts read-only CoA (Phase 4, 04-04):** groups the flat `GET /gl/accounts` list by `account_type` into 5 fixed-order Cards; round-hundred codes (`/0+$/`) render bold/no-indent as top-level, all others `pl-6` — no recursive tree component for the shallow seeded CoA (D-11 read-only: no toolbar/mutations/accent)
- **Tailwind v4 token registration (Phase 4, 04-04 UAT, `41d2fb7`):** shadcn color tokens must be registered via `@theme inline` in `src/index.css`, otherwise Tailwind v4 does not emit `bg-background`/`bg-card`/etc. utilities and Sheet/Dialog/form panels render transparent app-wide
- **Partner country validation UX (Phase 4, 04-04 UAT, `a3f50da`):** `addr_country`/`country_of_origin` constrained to ISO 2-letter (maxLength + uppercase + helper text) and the API's real validation detail surfaced in the toast (was an opaque "Failed to save")
- **Catch-all + SYERP sub-nav (Phase 4, 04-04 UAT, `2e78af8`/`d88d55e`):** App.tsx catch-all redirects unknown paths to Home (no blank screen); a `SyerpNav.tsx` tab strip (Vendors | Customers | Chart of Accounts) was added to all three SYERP screens since the sidebar only exposes the module root
- **PLUM revision_number (Phase 5, 05-01):** `revision_number INT` added to `plum_part_revision` for stable per-part ordering; latest-revision resolved via MAX query (avoids timestamp collision edge case)
- **PLUM tag storage (Phase 5, 05-01):** Classification tags stored as join table (`plum_part_tag`) for Phase 6 extensibility — tag rename won't require data migration
- **PLUM one-Released invariant (Phase 5, 05-01):** Partial unique index `uq_plum_part_one_released ON plum_part_revision(part_id) WHERE status='released'` enforces D-08 at DB level (belt-and-suspenders for race condition safety)
- **PLUM service list/update dict return (Phase 5, 05-02):** list_parts and update_part return dicts (not ORM instances) because PartRead contains virtual fields (current_revision_label, current_revision_status, tags) not present as ORM columns on PlumPart — enriched post-query
- **PLUM revision label timing (Phase 5, 05-02):** SemVer label is major-bumped at release time (inside advance_revision_status); ASME label is set at creation time and unchanged on release
- **PLUM advance endpoint body (Phase 5, 05-02):** AdvanceStatusBody(target_status:str) defined inline in router.py — avoids a separate schema file for a single-field body
- **PLUM audit colocation (Phase 5, 05-02):** revision FSM audit events (revision.submitted/released/rejected/obsoleted) written inside service; part-level events (part.created/updated/archived) written in router — keeps FSM logic and audit collocated

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

- ~~No in-app navigation shell / logout control linking Landing <-> /admin/users — deferred to Phase 3 (App Shell, CORE-06..08).~~ **CLOSED in Phase 3 (03-03):** AppShell sidebar+topbar chrome with a working Log out control in the user menu.
- Admin-seed/startup path has no DB-backed regression test (seed tests skip without a live DB) — the `MissingGreenlet` slipped past unit tests; recommend a seed integration test during gap-closure.

---

## Session Continuity

**To resume:** Phase 05 Plan 02 COMPLETE. PLUM service + router implemented: 7 endpoints with RBAC/audit, revision FSM, supersede-on-release, ASME/SemVer label generation. Wave 0 tests (14) skip cleanly without DB (ready to run green with live DB). Next: Plan 05-03 (PLUM parts list UI). Note: rebuild `frontend/dist` + container image before production `:8000` serving reflects the Phase-3/4 UI.

**Files on disk:**

- `.planning/PROJECT.md` — project vision and constraints
- `.planning/REQUIREMENTS.md` — 24 v1 requirements with traceability
- `.planning/ROADMAP.md` — 6-phase milestone roadmap
- `.planning/STATE.md` — this file
- `.planning/config.json` — workflow config (mode: yolo, granularity: standard)
- `.planning/codebase/` — architecture map of existing HTML prototypes

---

*State initialized: 2026-06-22*
