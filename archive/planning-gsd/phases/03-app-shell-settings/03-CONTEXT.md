# Phase 3: App Shell & Settings - Context

**Gathered:** 2026-06-25
**Status:** Ready for planning

<domain>
## Phase Boundary

Deliver the first real **application chrome** for the suite plus the two admin
configuration surfaces it implies. Today the SPA has only bare routes (Landing,
Login, `/admin/users`) behind `ProtectedRoute`; this phase wraps them in a
coherent navigation shell and adds system-wide configuration.

**Delivers (CORE-06, CORE-07, CORE-08):**
- A **navigation shell** (persistent chrome) that lists the modules a user can
  reach and lets them switch between them (CORE-08).
- **System settings** — an admin screen + backend to configure company info and
  defaults, persisted across sessions (CORE-06).
- **Module enable/disable** — an admin screen + backend to toggle which modules
  are active at runtime; toggling a module off removes its nav entry (CORE-07).

**NOT in this phase:**
- Any SYERP / PLUM business feature code or real module screens (Phases 4–6) —
  this phase is module-agnostic chrome; nav entries may point at stubs.
- New auth/identity primitives — Phase 2 already shipped RBAC (`module:action`
  permissions, `require_permission`) and user CRUD; Phase 3 consumes them.
- Live push / real-time broadcast of module-toggle changes to open clients —
  explicitly deferred to a future milestone (see Deferred Ideas).
- Per-user preferences as a feature — settings are global/admin in v1; the model
  only leaves room for per-user later (D-13).

</domain>

<decisions>
## Implementation Decisions

### Shell Layout & Chrome
- **D-01:** **Sidebar + top bar layout.** A persistent left sidebar for module
  navigation, plus a thin top bar for global controls. Sidebar collapses to a
  shadcn `sheet` drawer on narrow screens (component already installed).
- **D-02:** **Persistent chrome contains all of:** configured company name /
  branding (from CORE-06 settings, surfaced in the header), a user menu with a
  **logout control** (closes the Phase-2 deferred follow-up: no in-app logout
  existed), an **active-module indicator** (highlight current section in nav),
  and an **admin/settings entry** visible to admins only.
- **D-03:** **Admin screens are reached via a settings/user menu in the chrome**
  (gear icon or user-menu dropdown), not as top-level business-nav items. This
  groups Users (existing `/admin/users`), System Settings (new), and Modules
  (new) away from the business-module nav, keeping the main sidebar focused on
  suites. Admin entry is gated to admin users.

### Navigation Visibility Logic
- **D-04:** **Nav shows a module only if it is ENABLED *and* the user is
  PERMITTED.** A module appears iff it is enabled (CORE-07 runtime state) **and**
  the user holds the relevant `module:action` permission (Phase 2 D-08 RBAC).
  This means the nav never offers a module the user would get a 403 on. The
  literal CORE-08 ("listing enabled modules") is satisfied as a superset — the
  per-user view is the enabled set filtered by permission.
- **D-05:** **Friendly empty state.** If a user has no visible modules (none
  enabled, or none they're permitted for), the shell still fully renders (chrome,
  user menu, logout) and the content area shows a "No modules available — contact
  your admin" message. The shell is never a blank/broken page.
- **D-06:** **Post-login landing is a neutral home/dashboard** at `/`, not a
  module redirect. A greeting/overview placeholder; the user picks a module from
  the nav. Keeps Phase 3 module-agnostic since real SYERP/PLUM screens arrive in
  Phases 4–6.

### Module Enable/Disable Model
- **D-07:** **A DB-backed `modules` table, idempotently seeded from the code
  registry on startup.** Columns along the lines of `key`, `display_name`,
  `enabled`, `always_on` (planner refines). Deploy-time Podman Compose profiles
  (Phase 1 D-04) still decide which modules are **present**; this table decides
  which present modules are **on**. The admin toggle flips `enabled`. Seeding
  follows the established idempotent select-before-insert seed pattern so
  repeated `podman-compose up` stays safe, and the table autogenerates into the
  single Alembic history (Phase 1 D-03).
- **D-08:** **SYERP always-on is enforced via a non-disablable flag.** SYERP (and
  any platform/admin core) carries `always_on = true`. The toggle UI shows it but
  disables the control with an explanatory tooltip, and the **backend rejects**
  any request to disable an always-on module. This enforces Phase 1 D-06 (SYERP
  is the bundled hub, no graceful-degradation paths) at the data + API layer, not
  just the UI.
- **D-09:** **"Disappears immediately for all users" is satisfied by refetch, not
  live push.** The nav reads enabled modules from an API; a TanStack Query
  refetch (after a toggle, on navigation, and/or on window focus) picks up the
  change within seconds without WebSockets/SSE. Pragmatic for a single-instance
  self-hosted deployment. (Live push is captured as a deferred backlog item.)

### System Settings Model & Scope
- **D-10:** **Key-value settings table.** A flexible `settings` table (e.g.
  `key`, `value`, `type`/`category`) so new settings can be added later without a
  migration each time — fits a suite that will accumulate config knobs across
  modules. (Trade-off vs typed single-row config noted and accepted: weaker
  static typing in exchange for additive growth.)
- **D-11:** **v1 settings cover company identity + locale defaults.** Company
  identity (company name — surfaced in the shell header per D-02; logo/address
  optional) **and** locale defaults (default currency, date format, timezone,
  units) that PLUM costing (Phase 6) and SYERP will later consume. (Note: this is
  broader than a strict "company name only" minimum — chosen to lay the defaults
  groundwork now.)
- **D-12:** **Settings are global and admin-only in v1**, gated by an admin
  permission (e.g. `users:manage` or an equivalent settings permission —
  planner's call within the Phase 2 RBAC model). No per-user preferences ship in
  this phase.
- **D-13:** **Model settings so per-user preferences can layer on later.** Keep
  the v1 store global, but design the schema/keys so a per-user override layer is
  an additive change, not a rewrite (e.g. leave room for an optional owner/scope
  dimension). Groundwork only — no per-user behavior in Phase 3.

### Claude's Discretion (delegated to planner/researcher)
- Exact column sets for the `modules` and `settings` tables, and whether
  `settings` carries a `scope`/`owner` column now or reserves the room logically.
- The precise admin permission string gating Settings and Module toggles within
  the Phase 2 `module:action` model.
- Shell component structure (layout wrapper vs nested routes), how the
  active-module indicator is computed from the router, and which existing shadcn
  primitives are composed (`sheet`, `dropdown-menu`, `separator`, `button`).
- The TanStack Query refetch triggers/cadence that make a toggle propagate
  "immediately" (focus refetch, invalidation on toggle mutation, etc.).
- Whether enabled-modules + visible-nav is one API response or composed
  client-side from a modules endpoint + the user's permissions from `/auth/me`.
- Seed details for the `modules` table (display names, ordering, icons).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase scope & requirements (authoritative)
- `.planning/ROADMAP.md` §"Phase 3: App Shell & Settings" — phase goal and the 4
  success criteria this phase is verified against (nav shell lists enabled
  modules + switch; admin updates settings that persist; toggle module off →
  nav entry disappears for all users; re-enable → reappears).
- `.planning/REQUIREMENTS.md` — CORE-06 (admin configures company info/defaults),
  CORE-07 (admin enable/disable individual modules), CORE-08 (nav shell lists
  enabled modules + switch).
- `.planning/PROJECT.md` — locked tech stack (FastAPI + SQLAlchemy 2.0 +
  PostgreSQL; React/TS/Tailwind/shadcn; TanStack Query), self-hosted +
  modular-monolith constraints, SYERP-as-hub, medical-device audit posture.

### Prior-phase decisions this phase builds on (authoritative for integration)
- `.planning/phases/01-project-scaffolding-deployment/01-CONTEXT.md` — **D-04**
  (lightweight module registry + per-module Compose profiles; deploy-time module
  selection), **D-06** (SYERP always-on bundled hub, no graceful-degradation),
  **D-03** (single Alembic history), **D-09/D-10** (auto-migrate + idempotent
  seed on startup). These bound D-07/D-08 here.
- `.planning/phases/02-authentication-users/02-CONTEXT.md` — **D-08** (`module:action`
  permission RBAC), **D-10** (`require_permission(...)` FastAPI gate). The nav
  visibility (D-04) and admin gating (D-12) consume these directly. Also: the
  Phase-2 deferred follow-up "no in-app navigation shell / logout control" is
  closed by D-01/D-02 here.

### Existing code this phase extends (authoritative)
- `backend/app/core/registry.py` — the in-memory module registry (`register`,
  `mount_all`, `MODULE_NAME`); the `modules` DB table (D-07) is seeded from what
  this registry knows. May need a display-name/metadata addition (planner's call).
- `backend/app/core/models.py` — central model aggregator Alembic imports; add a
  `core` settings/modules models import here so autogenerate discovers the new
  tables.
- `backend/app/core/seed.py` — `run_seeds()` hook; module-table seed plugs in
  alongside the Phase-2 admin/role seeds (idempotent).
- `backend/app/core/config.py` — `pydantic-settings` + `SecretStr` pattern.
- `backend/app/modules/auth/dependencies.py` — `require_permission` /
  `get_current_user` dependencies that gate the new settings + module-toggle
  routers and feed nav permission filtering.
- `frontend/src/App.tsx` — current React Router tree (Landing, Login, ProtectedRoute,
  admin/Users); the shell wraps the protected routes here.
- `frontend/src/components/ProtectedRoute.tsx`, `frontend/src/hooks/useAuth.ts` —
  the auth guard + `/auth/me` hook the shell reads user + permissions from.
- `frontend/src/components/ui/` — installed shadcn primitives to reuse: `sheet`
  (drawer), `dropdown-menu` (user/settings menu), `separator`, `button`, `card`,
  `table`, `input`, `label`, `select`, `dialog`.

### No dedicated app-shell/settings spec
- No standalone shell/settings ADR exists in `docs/`. The decisions above are the
  authoritative source for this phase. **UI hint: yes** — `/gsd-ui-phase 3` can
  produce a UI-SPEC.md design contract before building screens (recommended for
  the shell + admin screens).

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `core/registry.py` — source of truth for which modules exist in code; seed the
  `modules` table from it (D-07).
- `core/seed.py:run_seeds()` — idempotent seed hook; add module-table seed here.
- `modules/auth/dependencies.py` `require_permission` — gates new admin routers
  and informs nav permission filtering (D-04, D-12).
- Frontend `hooks/useAuth.ts` + `/auth/me` — current user + permissions the shell
  filters nav against; no new state lib needed (TanStack Query already in place).
- shadcn primitives in `components/ui/` (`sheet`, `dropdown-menu`, `separator`,
  `button`, etc.) — the shell chrome composes these rather than adding new deps.

### Established Patterns
- **Module-as-package** (`backend/app/modules/<suite>/`) — settings/modules logic
  likely lives in `core/` (cross-cutting) rather than a suite package; planner
  confirms placement.
- **Single Alembic history** — one migration adds the `modules` + `settings`
  tables; register them in `core/models.py`.
- **Idempotent select-before-insert seed** (Phase 2 pattern) — reuse for seeding
  the `modules` table so repeated startups are safe.
- **`ProtectedRoute` layout-route wrapping** — the shell becomes (or wraps) the
  protected layout in `App.tsx`; admin screens nest under it.

### Integration Points
- Nav visibility = enabled modules (`modules` table) ∩ user permissions
  (`/auth/me`) — the first feature to **join Phase-2 RBAC with Phase-1 module
  registry** (D-04). Get the enabled-modules API shape right; Phases 4–6 add nav
  entries by landing their routers + registry entries.
- The `modules` table + `always_on` flag is the runtime counterpart to Phase 1's
  deploy-time Compose profiles — keep the two concepts distinct (present vs on).
- Company name from `settings` surfaces in the shell header (D-02), the first
  consumer of the settings store; later phases (PLUM costing, SYERP) consume the
  locale defaults (D-11).

</code_context>

<specifics>
## Specific Ideas

- Closes the Phase-2 deferred follow-up explicitly: the shell must provide the
  in-app navigation + logout control that Phase 2 left undone (D-01/D-02).
- User flagged that **live push of module-toggle changes** is desirable but
  belongs in a future milestone backlog, not this phase (D-09 / Deferred).
- Settings scope chosen as "global now, model for per-user later" rather than the
  strict minimum — a deliberate groundwork choice (D-13).

</specifics>

<deferred>
## Deferred Ideas

- **Live push of module enable/disable to all open clients** (WebSocket/SSE
  broadcast so nav updates instantly without refetch) — **add to backlog for a
  future milestone** (user request). Phase 3 uses refetch (D-09); the API shape
  leaves room to add push later.
- **Per-user preferences / settings** — only the data-model groundwork is in
  scope (D-13); actual per-user preference behavior is a later phase.
- **Rich company branding** (logo upload, address blocks, themes) beyond a company
  name string — optional/later; v1 surfaces company name (D-11).
- **Module-level metadata in nav** (icons, ordering, grouping, descriptions) —
  basic version is builder's discretion; richer module catalog UI is later.

None of these block Phase 3.

</deferred>

---

*Phase: 3-App Shell & Settings*
*Context gathered: 2026-06-25*
