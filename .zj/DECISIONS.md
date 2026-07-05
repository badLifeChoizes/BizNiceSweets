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

- **D-P7-5 (owner, at build):** **Human-UAT moves from a per-phase blocking gate to a
  milestone-close activity.** Under the ZJ workflow the atomic, bisectable commit history makes
  regressions cheap to localize, so full click-through UAT runs once at `/zj:milestone` rather
  than blocking each phase. *Consequence for Phase 7:* Task 6 is unblocked — the two checks run
  (check 1 BOM-add-on-Draft, check 8 Released-read-only) **passed**; the remaining checks
  (2–7, 9–12) are captured as TODO in `.zj/UAT-v1.0.md` for the v1.0 milestone UAT. Task 7
  reconciles traceability honestly against this: the code fixes are marked on their
  automated/standalone-verified evidence, and flow-level UI confirmation is annotated
  "human-UAT deferred to v1.0 milestone" rather than claimed complete (preserves SC5 — nothing
  marked Complete on an unrun check).

## v2.0 / Phase 8 spec — SYERP-10/11 expansion (2026-07-05)

- **D-P8-1 (owner):** **Inventory and purchasing are SYERP, not MOUSSE or GELATO** — reaffirmed
  when the owner questioned suite ownership at spec time. SYERP is the ERP hub and owns the
  inventory *ledger* (what is stocked, how much, what it's worth) and *procurement* (POs to
  vendors); MOUSSE *consumes* inventory + PLUM BOMs to build (later); GELATO adds *physical*
  warehouse detail (bins, receiving floor, pick/pack/ship, lot/serial) on top of SYERP inventory
  (later). Both MOUSSE and GELATO depend on SYERP inventory existing first — hence the
  dependency-first sequencing (D-6). *Source: PROJECT.md ("SYERP … inventory — the hub"), PRD-7.*
- **D-P8-2 (owner):** **Hybrid item↔PLUM identity.** An inventory item is its own SYERP record
  with a **nullable** FK to a PLUM part. Rationale: a real shop stocks non-designed goods (raw
  materials, packaging, consumables) that are not PLUM parts, and SYERP inventory should not
  hard-depend on the PLUM module being enabled. Rejected: "every item is a PLUM part" (can't
  stock non-parts; hard PLUM coupling) and "independent item master" (duplicates part data,
  weakens the MOUSSE BOM-consumption story).
- **D-P8-3 (owner):** **Flat named stock locations only** in SYERP inventory for v2.0; bins,
  zones, warehouse hierarchy, pick/pack/ship, and lot/serial are **deferred to GELATO-01** to
  avoid building the warehouse layer twice. Rejected: single implicit location (needs a schema
  change the moment locations arrive) and a full bin hierarchy now (overlaps GELATO scope).
- **D-P8-4 (owner):** **Moving weighted-average valuation.** Each receipt updates the item's
  moving-average unit cost; on-hand value = qty × avg cost; all math Decimal/`Numeric(18,6)`
  (D-11). Gives MOUSSE a real inventory cost to consume and flow back to SYERP (PRD-7 acceptance
  signal). Rejected: quantity-only (defers the cost-flow capability MOUSSE needs) and
  standard-cost-from-PLUM (misses purchase-price variance).
- **D-P8-5 (owner):** **PO depth = Draft → Approve → Receive-into-inventory, no AP.** Receiving
  posts SYERP-10 receipt transactions at PO unit cost; the workflow stops before vendor-invoice
  matching and payment, which stay SYERP-12. Rejected: pulling basic AP invoice-match forward
  (scope growth into SYERP-12) and PO-history-only with no receiving integration (weakest
  integration; would need manual stock adjustments).
- **D-P8-6:** Both the inventory-item `code` and the PO number use a **numeric-safe
  auto-generator** (order by integer cast, never lexicographic `MAX`) — carrying forward the
  PLUM `generate_part_number` defect lesson (Phase 7 `1b8bfa1`) so the same digit-boundary bug
  is not re-introduced in a new generator.
- **D-P8-7:** v2.0 **rejects** issues/adjustments/transfers that would drive a location negative,
  and **rejects** PO over-receipt beyond ordered qty (both HTTP 4xx). Backorder / negative-stock
  policy and over-receipt tolerance are deferred — sensible strict defaults now, revisited if a
  real workflow needs them.

## Phase 8 planning (2026-07-05)

- **D-P8-8 (owner):** Phase 8 is **one full-stack phase**, delivered in wave order: inventory
  backend → inventory UI → purchasing backend → purchasing UI → verify. PO receiving is built and
  verified on a working inventory ledger; the receipt→moving-average integration is proven
  end-to-end. Rejected: split by capability (inventory Phase 8 / purchasing Phase 9) and
  backend-first-UI-later — owner wants a complete, demoable operations slice in one phase.
- **D-P8-9 (owner):** **UI folded into the plan — no separate DESIGN.md.** Item and location CRUD
  reuse the existing SYERP list+sheet+archive template (`Vendors.tsx`/`Customers.tsx`/`PartnerSheet`);
  the novel screens (on-hand-by-location, adjust/transfer, PO create/approve/receive) are specified
  directly in the tasks. *Why:* the SYERP CRUD template is a strong enough starting point that a
  separate design pass wasn't worth the step.
- **D-P8-10 (owner):** **A single `syerp:write` gates all mutations, including PO approval**
  (Draft→Approved); reads use `syerp:read`. No separate approve permission. Approver identity is
  captured via the audit event (`po.approved` + `approved_by`). *Why:* keeps Phase-8 RBAC scope
  tight and matches the current SYERP pattern; approval-authority separation can be added later
  without a data migration. Rejected: a distinct `syerp:approve` code.
- **D-P8-11 (owner):** Phase 8 branch = **`feature-syerp-inventory-purchasing` cut from the current
  `bugfix-plum-v1-gaps` tip**, NOT from `master`. *Why:* `master` (HEAD `f4e2bd3`, 2025-12-20)
  predates the entire re-platform and contains no `backend/`/`frontend/`/`.zj/` (the same trap
  documented in D-P7-3); only the current tip carries the real codebase plus the Phase-7 fixes.
  Phase 8 therefore builds atop unmerged Phase 7 — consistent with the owner's choice to plan 8
  before formally closing v1.0.
- **D-P8-12 (owner):** **Moving-average valuation is stored** as a `moving_avg_cost Numeric(18,6)`
  column on `syerp_inventory_item`, recomputed transactionally on each receipt. On-hand *quantity*
  stays a derived `SUM(quantity)` over the immutable ledger, and every receipt's `unit_cost` is
  retained in the ledger, so the average remains auditable/replayable — a mutated-by-design column,
  not a violation of the "on-hand is derived" rule (D-P8-4). Rejected: full ledger-replay on every
  read (more code, slower reads, no offsetting benefit at single-shop scale).
- **D-P8-13 (owner):** Auto-generated code prefixes — inventory items **`ITEM-0001`**, purchase
  orders **`PO-0001`** — both via the numeric-safe generator (regex-filter then integer-cast order,
  D-P8-6), distinct from partner `P-0001`.
- **D-P8-14 (owner):** A fresh deploy **seeds one idempotent `Main` stock location** (upsert-by-name,
  mirroring `coa_seed.py`) so receiving/adjustments work out-of-the-box. Rejected: no seed (adds a
  manual setup step before any stock movement).
- **D-P8-15:** PO line `qty_received` is a **stored accumulator** on the line (POs are mutable
  working documents, not the immutable ledger), cross-checkable against `SUM(quantity)` of the
  receipt transactions whose `source_id` = the line id.
