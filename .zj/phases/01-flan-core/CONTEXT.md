# Phase 1 — FLAN core: planning context
Written by the manager at `/zj:plan 1`, 2026-08-18. Inputs to the architect.

## Target

**Roadmap phase 1 of milestone v5.0 "FLAN port"** (D-V5-8): delivers **SRD FLAN-01** —
project/phase/task core, team roster (optional user link), assignment, RBAC
`flan:read`/`flan:write`, audit. Roadmap rationale: *"Nothing else has anything to attach to.
Establishes the unified task model (D-V5-1): a phase derives its dates and % from its tasks."*

FLAN-01's 7 acceptance criteria and its named verification are in `.zj/SRD.md` (line 260ff) —
read them verbatim; they are the success criteria for this phase.

## Owner decisions taken at plan (2026-08-18) — these are binding

- **D-V5P1-1 — One full-stack phase, wave order.** Not sub-split. Waves: models+migration →
  service package + router (project / phase / task / roster / assignment) → UI → verify.
  Mirrors D-P8-8 and Phase 11a (CRUMB core). *Why:* FLAN-01 has exactly one provable crux —
  phase-derived dates and % including the empty-phase case — and the v3.0 keeper is "sub-split
  when a phase has two provable cruxes."
- **D-V5P1-2 — Task key prefix is a per-project field, locked after the first task.** Projects
  carry a `key_prefix` column, defaulted from the project name at create (e.g. "Crisis
  Simulator" → `CRIS`), editable until the first task is issued, **immutable after**. Rejected:
  always-editable (leaves one project holding a mixed `PRJ-1..PRJ-9` + `CRIS-10..` series that
  the numeric-safe generator must scan) and a fixed global `TASK-` prefix (kills the per-project
  identity both prototypes had, and makes a key meaningless in FLAN-10's deep links and exports).
  Note the v45 prototype *infers* the prefix from the majority of existing keys
  (`keyPrefix()`/`nextKey()`, `flan/app/schedule_gate-v45.html:3197-3207`) — that inference is
  deliberately **not** ported; the platform stores the prefix.
- **D-V5P1-3 — Active project is URL-scoped, with a switcher.** Routes are
  `/flan/projects/:projectId/...`; a project switcher in the FLAN nav simply navigates. *Why:*
  it makes FLAN-01.6 ("no view mixes two projects' data") structural rather than a service-layer
  rule to remember — a view cannot mix two projects because it only ever receives one id — needs
  no server-side session state, and is already the shape FLAN-10's authenticated deep links
  (D-V5-6) will require. Rejected: server-persisted active project with flat routes (kills
  deep-linkability); URL-scoped with no switcher (round trip through the list on every change).
- **D-V5P1-4 — Refresh `.zj/codebase/MAP.md` at the end of this phase.** One task, run after FLAN
  exists so the map gains the new module. *Why:* the map's body is current through v3.0 but its
  **Concerns** section carries four false claims that will actively mislead the architects and
  engineers of phases 2a–7: Concern 1 calls the Phase-7-fixed `SyerpPartner` import a live
  BLOCKER; Concern 5 says "No CI: no `.github/`, no pipeline config anywhere (verified)" when
  v4.0 Phase 3 shipped six required jobs with branch protection; it cites the deleted
  `frontend/.eslintrc.cjs` as the lint config; and its registered-module list omits `gelato`.
  **Out of scope, explicitly:** splitting `plum/service.py` (~3,000 lines — stays BACKLOG p2, a
  refactor whose blast radius is PLUM's whole test surface does not belong on the critical path
  to the v5.0 DoD), and regenerating `.zj/atlas/atlas.html` (frozen at 2026-07-04; better done
  at the v5.0 close when FLAN is whole).

## Spec decisions this phase must honor

- **D-V5-1 — unified task model.** `Project → Phase → Task`. The **Task** carries the full
  `schedule_gate-v45` field set; a **Phase's** start date, due date and % complete are *computed*
  from its tasks (earliest start, latest due, share `Done`) and **never hand-set**. v24's
  hand-dragged progress slider is **not** ported. Accepted cost: a phase can no longer be marked
  "80% done" by judgement.
- **D-V5-2 — roster with an optional platform-user link.** A FLAN team member is a
  **project-owned** row (name, role, email, colour, hourly rate) that *may* reference a CORE-04
  user but need not. Deleting or deactivating a user must **never** delete the roster row or its
  history. **No cost is derived from the hourly rate in v5.0** (labor costing is out per D-M5-2)
  — the field is stored and nothing reads it.
- **D-P8-6 — numeric-safe key generation.** Order by integer cast, never lexicographic MAX.
  `PRJ-9 → PRJ-10` must hold. Exemplar: `generate_quote_number`
  (`backend/app/modules/crumb/service/quotes.py:68-90`) — regex filter *before* the cast.
- **D-P10-6 — RBAC scope pair.** `flan:read` / `flan:write`, mirroring `crumb`/`gelato`.
- **CORE-05** — refused server-side regardless of UI. **CORE-07/08** — navigation gated on FLAN
  enabled ∩ `flan:read`. **NFR-1** — every mutation emits an attributable audit event.
  **NFR-5** — the verify cruxes are also ported into the ordinary pytest suite.

## Codebase facts the plan must build on (verified 2026-08-18)

- **Module registration:** `backend/app/modules/<name>/__init__.py` defines `MODULE_NAME`,
  imports `router`, calls `registry.register(sys.modules[__name__])`. `backend/app/main.py`
  then needs `importlib.import_module("app.modules.flan")` added alongside the other five.
  Exemplar: `backend/app/modules/gelato/__init__.py`.
- **`flan` is already seeded in the module catalog** — `backend/app/core/modules_seed.py`
  carries `("flan", "FLAN — Project Management", False, 30)`. No seed change needed there.
- **`flan:read`/`flan:write` are NOT yet seeded** — `backend/app/modules/auth/seed.py`
  `_PERMISSIONS` (line 31ff) and `_USER_ROLE_PERMS` (line 47ff) both need the pair added.
  Both lists are idempotent upserts, so adding entries is safe on an existing database.
- **Model aggregation:** `backend/app/core/models.py` has a commented-out
  `# from app.modules.flan import models as flan_models` line waiting to be uncommented.
  Alembic autogenerate sees nothing without it (Pitfall 1).
- **Alembic head is `0017`** (`0017_syerp_ar_invoicing.py`). This phase adds `0018`.
- **Service package from day one** — a new suite starts as `service/` (a package), never a
  single `service.py`. Settled practice, zero refactor debt. See `crumb/service/` and
  `gelato/service/`.
- **Audit is written at the ROUTER layer, after the service commit**, via
  `write_audit` from `app.modules.auth.service`. See `backend/app/modules/gelato/router.py:56`
  and its call sites. Read-only endpoints write no audit row.
- **Frontend route pattern:** per-suite folder `frontend/src/routes/flan/` with a local
  `components/` subfolder, a `hooks.ts` of TanStack Query hooks, and colocated `*.test.tsx`.
  Routes are registered in `frontend/src/App.tsx`; the Sidebar auto-renders one NavLink per
  visible module pointing at `/<module.key>`, so `/flan` must redirect to a landing route
  (compare the `/gelato` → `/gelato/bins` and `/crumb` → `/crumb/leads` redirects).
- **Verify scripts:** live-Postgres standalone scripts in `backend/scripts/`, in pairs — a
  service-level `verify_flan.py` and an HTTP-level `verify_flan_api.py` (the paired API script
  proves router audit + RBAC that a service script structurally cannot). Exemplars:
  `verify_gelato.py` / `verify_gelato_api.py`. The CI `verify-scripts` job runs the non-API set.
- **Both lint gates are enforcing at a zero-violation baseline** — `npm run lint` from
  `frontend/`, `ruff check .` from `backend/` — and CI runs six required jobs on every push.
  New code must land clean.

## Standing keepers from LEARNINGS that apply here

- **Mirroring an exemplar retires architectural risk, never correctness risk — the copy is
  un-audited exactly where your case differs.** This phase mirrors CRUMB/GELATO heavily. Before
  copying a block, name the property that makes the exemplar safe and check FLAN shares it. The
  concrete trap for this phase: a broad `except IntegrityError → retry` around key generation is
  safe only if a key collision is the *only* IntegrityError that path can raise — FLAN's task
  insert also carries a `phase_id` FK and an assignee link, so narrow the except to the specific
  constraint and bound the retry (this is the Phase-13 `create_invoice` unbounded-recursion 500,
  exactly).
- **Build verify inputs in the SAME shape the router/UI sends.** Two separate defects (11a, 11b)
  shipped because verify hand-fed a field name the UI never sends.
- **Assert the column actually renders its value** in the frontend tasks — this counter-measure
  caught the dead-through-UI trap in-build on two straight phases.
- **Assert the adjacent untouched surface still works on a cold process.** FLAN adds a module to
  `main.py`'s import list and a table to the shared metadata; Phase 13's equivalent check caught
  a cross-module FK-resolution 500 that four green suites had missed because their fixtures
  pre-warmed the models.
- **A green assertion is not proof when its fixture doesn't match reality.** For the phase-derived
  rollup crux specifically, the empty-phase case is called out in the SRD verification because it
  is the case a hand-built happy-path fixture will not have.

## Non-goals for this phase

Dependency links / scheduling / gate verdict (FLAN-02, phase 2a), tags and the facet taxonomy
(FLAN-04, phase 2a), the timeline/board/calendar surfaces (FLAN-03, phase 2b), risks/milestones/
decisions (FLAN-05), deliveries/notes (FLAN-06), budget (FLAN-07), the SYERP roll-up and estimate
promotion (FLAN-08 — the DoD crux, phase 4b), analytics (FLAN-09), exports/comments/undo
(FLAN-10), the coverage matrix (FLAN-11). Labor/time capture is out of the whole milestone.
No prototype **data** is migrated (D-V5-4) — `flan/data/Crisis.json` is not a requirements source.
