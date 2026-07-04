# Phase 4: SYERP Core Hub - Context

**Gathered:** 2026-06-26
**Status:** Ready for planning

<domain>
## Phase Boundary

Deliver the **master-data backbone** of the suite: the vendor and customer
records every other module FKs into, plus a browsable chart-of-accounts
skeleton. SYERP is the always-on hub (Phase 1 D-06); this phase fills its
empty module stub (`backend/app/modules/syerp/`) with its first real tables,
APIs, and screens.

**Delivers (SYERP-01 … SYERP-05):**
- **Vendor** create/view/edit/delete + search & filter (SYERP-01, SYERP-02).
- **Customer** create/view/edit/delete + search & filter (SYERP-03, SYERP-04).
- **GL chart-of-accounts skeleton** — visible and browsable (SYERP-05).

**NOT in this phase:**
- Purchasing, POs, AP/AR, invoicing, inventory, sales orders, financial
  reporting — later SYERP-extended phases (out of Milestone 1 per REQUIREMENTS.md).
- The actual **PLUM AVL link** (part → vendor FK) — that lands in Phase 6
  (PLUM-07). This phase only makes vendors *linkable* (stable partner rows that
  survive archival).
- Editable GL accounts / GL postings / journal entries — the skeleton is
  read-only browse in v1 (see D-11).
- Multi-user real-time concerns beyond auth + shared DB.

</domain>

<decisions>
## Implementation Decisions

### Partner Data Model
- **D-01:** **Unified business-partner table.** A single `syerp_partner` table
  with boolean role flags `is_vendor` / `is_customer` (Odoo/SAP `res.partner`
  style). A company that both supplies and buys is **one row**, not two — chosen
  deliberately over separate tables and over "separate-now-partner-ready"
  because the user's manufacturing partners are frequently both. FKs from PLUM
  (AVL, Phase 6) and future purchasing/sales target `syerp_partner.id`,
  qualified by the relevant role flag.
- **D-02:** **Surfaced as separate Vendor and Customer screens.** Two nav
  entries / list screens, each a **filtered view** of the partner table
  (`is_vendor = true` / `is_customer = true`), over a **shared edit form** whose
  role flags control which list(s) a partner appears in. This satisfies the
  literal SYERP success-criteria wording ("vendor list", "customer list") while
  keeping one underlying entity. A partner flagged both appears in both lists.
  (Rejected: a single unified "Partners" screen with a type filter; and building
  both unified + separate.)

### Partner Record Fields
- **D-03:** **Manufacturer-grade record in v1.** Fields group into:
  - *Identity:* `name`, `code`, `is_vendor`, `is_customer`, `active`.
  - *Address:* one address block (line1/line2, city, state/region, postal,
    country) — single embedded address in v1, not a one-to-many.
  - *Contact:* one primary contact (`contact_name`, `email`, `phone`) — single
    embedded contact in v1.
  - *Commerce:* `payment_terms`, `tax_id` (EIN/VAT), `currency`,
    `country_of_origin`, `notes`.
  (Rejected: lean name+contact-only core, to avoid Phase 6 schema churn.)
  Exact column types/lengths and nullability are the planner's call; align with
  the PLUM prototype's vendor fields (`plum/app/plm_v54.html`, ~771 vendor refs)
  where it doesn't conflict.
- **D-04:** **Partner code is auto-generated but editable.** On create, the
  system prefills the next sequential code; the user may override before save.
  Code is **unique** (DB constraint). Series scheme (per-role `V-####` / `C-####`
  vs a single `P-####`) is builder's discretion — a single unified series is
  natural given the unified table, but a role-prefixed display is acceptable.
  (Rejected: mandatory manual code; optional/name-only.)

### Delete Behavior
- **D-05:** **Soft-delete / archive — no hard delete in v1.** "Delete" sets the
  record inactive (`active = false`, or an `archived_at` timestamp — planner's
  choice) and hides it from default lists. The row is **retained** so future FK
  references (PLUM AVL Phase 6, later POs/orders) never orphan, and the audit
  trail stays intact — directly serving the medical-device traceability posture
  (PROJECT.md). Lists default to active-only with a **"show archived" toggle**
  to surface/restore. (Rejected: hard delete; and the guarded
  hard-delete-when-unreferenced variant — unnecessary in v1 since nothing
  references partners until Phase 6.)

### GL Chart-of-Accounts Skeleton
- **D-06:** **Seeded standard small-business CoA, browsable read-only.** Ship a
  `syerp_gl_account` table (e.g. `id`, `code`, `name`, `type`, `parent_id`,
  `active`) **seeded** with a conventional CoA — the five account types
  (Assets / Liabilities / Equity / Revenue / Expenses) with standard numeric
  ranges (1000s / 2000s / 3000s / 4000s / 5000s) and a sensible set of common
  sub-accounts. Rendered as a **grouped, expandable, read-only tree**. This
  satisfies "visible and browsable" out of the box.
- **D-11 (scope guard):** **No GL CRUD, postings, or journal entries this
  phase.** Accounts are seeded + browsed only; add/edit/deactivate of accounts
  and any actual ledger activity are deferred to when financials land. Seed
  follows the established **idempotent select-before-insert** pattern
  (Phase 2/3) so repeated `podman-compose up` stays safe.

### Search & Filter (success-criteria "instantly")
- **D-07:** **Builder's-discretion default (user delegated):** server-side
  search via query param across `name` + `code` + primary-contact fields, plus
  an **active/archived** filter; the vendor/customer split (D-02) is the implicit
  primary filter. Debounced live search for the "instantly" feel. Reuse the
  `Users.tsx` table interaction pattern. Client-side filtering is acceptable as a
  fallback given small single-shop record counts, but server-side is preferred to
  match the existing API style and scale. Planner picks the precise mechanism.

### Backend / API Shape
- **D-08:** **Fill the existing SYERP module stub**, following the auth module
  package layout (`models.py`, `schemas.py`, `service.py`, `router.py`). Routes
  mount under `/api/v1/syerp/...` (the `mount_all()` prefix adds `/api/v1` —
  routers must NOT include it). Table names use the `syerp_` prefix
  (`syerp_partner`, `syerp_gl_account`) per the stub's documented convention.
- **D-09:** **Gate writes with `syerp:write`, reads with `syerp:read`** — both
  permissions already exist and are exercised by the `_rbac_probe` /
  RBAC tests. Use `require_permission(...)` (Phase 2 dependency). Planner
  confirms exact granularity (e.g. whether GL browse needs its own permission or
  rides `syerp:read`).
- **D-10:** **Audit partner mutations** via the existing `write_audit` helper
  (create / update / archive), consistent with the medical-device traceability
  posture and the Phase 2/3 pattern. Actions e.g. `partner.created`,
  `partner.updated`, `partner.archived`.

### Claude's Discretion (delegated to planner/researcher)
- Exact `syerp_partner` / `syerp_gl_account` column sets, types, lengths,
  nullability, and indexes (esp. search indexes on `name`/`code`).
- Partner code series scheme (unified `P-####` vs role-prefixed display).
- `active=false` vs `archived_at` timestamp for the soft-delete marker.
- The precise standard CoA seed contents (which sub-accounts, exact numbering).
- Search/filter mechanism details per D-07 (server query vs client filter,
  debounce timing, which columns are filterable beyond name/code/contact).
- Whether GL browse is gated by `syerp:read` or a dedicated permission.
- Frontend: separate route files per Vendor/Customer screen vs a shared
  partner-list component parameterized by role; shared edit-form composition.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase scope & requirements (authoritative)
- `.planning/ROADMAP.md` §"Phase 4: SYERP Core Hub" — phase goal and the 5
  success criteria this phase is verified against (vendor CRUD; vendor
  search/filter instant; customer CRUD; customer search/filter instant; GL
  skeleton visible & browsable).
- `.planning/REQUIREMENTS.md` — SYERP-01 (vendor CRUD), SYERP-02 (vendor
  search/filter), SYERP-03 (customer CRUD), SYERP-04 (customer search/filter),
  SYERP-05 (chart-of-accounts skeleton).
- `.planning/PROJECT.md` — locked stack (FastAPI + SQLAlchemy 2.0 + PostgreSQL;
  React/TS/Tailwind/shadcn; TanStack Query), modular-monolith + **SYERP-as-hub**,
  self-hosted, and the **medical-device audit/traceability posture** that drives
  the soft-delete (D-05) and audit-logging (D-10) decisions.

### Prior-phase decisions this phase builds on (authoritative for integration)
- `.planning/phases/01-project-scaffolding-deployment/01-CONTEXT.md` — **D-06**
  (SYERP is the always-on bundled hub), **D-03** (single Alembic history — one
  migration adds the SYERP tables), **D-09/D-10** (auto-migrate + idempotent
  seed on startup — the CoA seed D-06 follows this).
- `.planning/phases/02-authentication-users/02-CONTEXT.md` — **D-08**
  (`module:action` RBAC; `syerp:read` / `syerp:write` exist), **D-10**
  (`require_permission(...)` gate), and the `write_audit` audit-log pattern
  (D-10 here reuses it).
- `.planning/phases/03-app-shell-settings/03-CONTEXT.md` — **D-04** (nav shows a
  module iff enabled AND user permitted — the Vendor/Customer nav entries land
  here), **D-11** (settings hold **locale defaults incl. default currency** that
  the partner `currency` field and later costing consume).

### Existing code this phase extends (authoritative)
- `backend/app/modules/syerp/{models,schemas,service,router}.py` — the empty
  Phase-1 SYERP stub these tables/APIs fill. `models.py` documents the
  `Base`-inheritance + `syerp_` table-name conventions; `router.py` documents
  the no-`/api/v1`-prefix rule.
- `backend/app/modules/auth/router.py` — **closest backend analog**: the
  `GET/POST/PATCH /users` admin CRUD endpoints with `require_permission` gating
  and `write_audit` calls. Mirror this shape for partner + GL routes.
- `backend/app/modules/auth/{service,schemas,dependencies}.py` — service-layer
  pattern, Pydantic schema pattern, and `require_permission` / `get_current_user`
  dependencies the new routers consume.
- `backend/app/core/models.py` — central model aggregator Alembic imports; the
  new SYERP models must be importable here so autogenerate discovers them.
- `backend/app/core/seed.py` (`run_seeds()`) — idempotent seed hook; the
  standard-CoA seed (D-06) plugs in here.
- `frontend/src/routes/admin/Users.tsx` — **closest frontend analog**: table +
  create/edit dialog + deactivate, TanStack Query, shadcn primitives. The Vendor
  and Customer screens follow this pattern.
- `frontend/src/components/ui/` — installed shadcn primitives to reuse:
  `table`, `dialog`, `input`, `label`, `select`, `button`, `card`, `badge`,
  `switch`, `separator`, `dropdown-menu`.

### Reference (informational, not authoritative)
- `plum/app/plm_v54.html` — the PLUM prototype's vendor data (~771 refs) is a
  useful field-set reference for D-03; it is the functional reference, **not**
  the target schema.
- `docs/features/syerp/README.md` — high-level SYERP vision stub (GL, AP/AR,
  inventory, POs). Most of it is out of Milestone 1 scope; informational only.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `modules/auth/router.py` admin-user CRUD — copy the endpoint shape
  (list/create/update gated by `require_permission`, audited) for partners.
- `core/seed.py` `run_seeds()` + the idempotent select-before-insert seed
  pattern — reuse to seed the standard CoA (D-06).
- `modules/auth/dependencies.py` `require_permission("syerp:read"|"syerp:write")`
  — gates the new routes; permissions already exist (used by `_rbac_probe`).
- `write_audit(...)` — partner create/update/archive audit entries (D-10).
- `frontend/.../admin/Users.tsx` — table + dialog + TanStack Query template for
  the Vendor/Customer screens; no new frontend deps needed.

### Established Patterns
- **Module-as-package** (`backend/app/modules/syerp/`) with
  `models/schemas/service/router` — fill the existing stub, don't add a new
  package.
- **Single Alembic history** — one autogenerated migration adds `syerp_partner`
  + `syerp_gl_account`; register models in `core/models.py`.
- **`syerp_` table-name prefix** and **`Base` inheritance** — required for
  Alembic discovery (documented in the stub).
- **Routers omit `/api/v1`** — `mount_all()` adds it.

### Integration Points
- The Vendor + Customer nav entries are the **first real business-module nav
  items** to appear in the Phase-3 shell (D-04 visibility: enabled ∩ permitted).
- `syerp_partner` is the FK target PLUM AVL (Phase 6, PLUM-07) will reference —
  the soft-delete decision (D-05) exists specifically to keep that FK stable.
- The partner `currency` field consumes the Phase-3 settings **default currency**
  (D-11) as its create-form default.

</code_context>

<specifics>
## Specific Ideas

- User explicitly chose the **unified-partner (res.partner-style) model** over
  separate tables — a deliberate ERP-grade architecture call grounded in their
  manufacturing reality (suppliers who are also customers).
- User wants the unified model **hidden behind separate Vendor/Customer
  screens**, not exposed as a single "Partners" list — UX should read like
  conventional ERP master-data screens.
- Soft-delete was chosen with the **medical-device traceability posture**
  explicitly in mind — partner rows must never be physically destroyed in v1.

</specifics>

<deferred>
## Deferred Ideas

- **GL account CRUD + ledger postings / journal entries** — beyond the
  "skeleton"; deferred to a later financials phase (D-11).
- **Purchasing, POs, AP/AR, sales orders, inventory, financial reporting** —
  SYERP-extended scope, out of Milestone 1 (REQUIREMENTS.md Out of Scope).
- **Guarded hard-delete (delete-when-unreferenced)** — considered and rejected
  for v1; could revisit if a real "purge" need emerges.
- **Multiple addresses / multiple contacts per partner** (one-to-many) — v1 uses
  a single embedded address + contact (D-03); a contacts/addresses child table
  is an additive later change.
- **Unified "Partners" management screen** (single list with type filter) —
  considered; not built. The underlying unified table leaves room to add it later.

None of these block Phase 4.

</deferred>

---

*Phase: 4-SYERP Core Hub*
*Context gathered: 2026-06-26*
