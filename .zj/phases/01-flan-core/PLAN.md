# Plan: 01 — FLAN core
Goal: A user can create a FLAN project with phases and tasks, staff it from a project team roster, and see each phase's dates and % complete derived from its tasks — as a registered, RBAC-gated, audited module.
Status: approved — planned 2026-08-18, ready for /zj:build 1

## Success criteria

Verbatim from `.zj/SRD.md` **FLAN-01** (traces PRD-6). Each is cited as `FLAN-01.N` on the tasks below.

1. **FLAN-01.1 — Project CRUD.** Create/view/edit/**archive** a project (name, category, description,
   currency, start date, gate/target date, tags). Archive is a soft delete: an archived project
   retains all data and rejects writes (4xx). The project id is immutable; duplicate project names
   are allowed.
2. **FLAN-01.2 — Phases.** A phase belongs to exactly one project (name, order, status
   `pending|in-progress|complete`, description). Deleting a phase **cascades to its tasks**. A phase's
   **start date, due date and % complete are derived from its tasks** (D-V5-1) — earliest task start,
   latest task due, and the share of its tasks in status `Done` — and are **never hand-set**; a phase
   with no tasks reports no dates and 0%.
3. **FLAN-01.3 — Tasks.** A task belongs to exactly one phase (hence one project) and carries: a
   **key** unique within the project (auto-numbered `<PREFIX>-####`, **numeric-safe** per D-P8-6),
   summary, status **`To Do | In Progress | Done`**, start date, due date, assignees, risk level
   **`none|low|medium|high`**, a **pinned** flag, and tags (FLAN-04). `due == start` is a valid
   zero-duration **milestone task**; `due < start` is rejected server-side (4xx).
4. **FLAN-01.4 — Team roster.** A team member carries name, role, email, colour and an hourly rate,
   and **may optionally reference a platform user account** (D-V5-2); a member with no user link is a
   valid collaborator. Deleting or deactivating a user account **does not** delete the roster row or
   any of its history; removing a roster member clears their assignments but leaves the tasks intact.
   **No cost is derived from the hourly rate in v5.0** — stored, nothing reads it.
5. **FLAN-01.5 — Assignment.** A phase or task carries zero or more assignees drawn from the project
   roster; the board can be filtered by assignee.
6. **FLAN-01.6 — Multi-project.** The module lists every project the user may see and makes one
   active; no view mixes two projects' data.
7. **FLAN-01.7 — Audit + RBAC.** Every mutation emits an attributable audit event (NFR-1); all
   endpoints are gated by **`flan:read` / `flan:write`** (D-P10-6) and refused server-side regardless
   of UI (CORE-05); navigation is gated on FLAN enabled ∩ `flan:read` (CORE-07/08).

**Named verification (SRD):** live-Postgres `backend/scripts/verify_flan.py` — phase-derived dates
and % against hand-built task sets **including the empty-phase case**; key uniqueness and
numeric-safe increment across `PRJ-9 → PRJ-10`; `due < start` 4xx; roster removal leaves tasks;
archived project rejects writes — plus `verify_flan_api.py` (HTTP RBAC + audit). Ported into the
ordinary pytest suite (NFR-5). FE Vitest + `npm run build`.

---

## Context

### The one crux this phase proves

**Phase-derived dates and % complete (D-V5-1, FLAN-01.2).** A phase carries **no** `start_date`,
`due_date` or `percent_complete` column. Those three values are computed on every read from the
phase's tasks. Storing them would make "never hand-set" a rule someone must remember; omitting the
columns makes it structural. The empty-phase case (`no tasks → dates None, percent "0.00"`) is the
case a happy-path fixture will not have — the SRD names it explicitly and Task 27 fixtures it first.

### Binding owner decisions (from `CONTEXT.md`, do not relitigate)

- **D-V5P1-1** — one full-stack phase in wave order; no sub-split.
- **D-V5P1-2** — task key prefix is a per-project `key_prefix` column, defaulted from the project name
  at create, editable until the first task exists, **immutable after**. The v45 prototype's
  majority-inference (`keyPrefix()`, `flan/app/schedule_gate-v45.html:3197-3207`) is **not** ported.
- **D-V5P1-3** — the active project is URL-scoped: `/flan/projects/:projectId/...`, with a switcher in
  the FLAN nav that simply navigates.
- **D-V5P1-4** — refresh `.zj/codebase/MAP.md` at the end of this phase (Wave E).

### Codebase facts the plan builds on (verified 2026-08-18)

| Fact | Evidence |
|---|---|
| Alembic head is `0017`; this phase adds `0018` | `backend/alembic/versions/0017_syerp_ar_invoicing.py:74` |
| The aggregator line is present but commented out | `backend/app/core/models.py`: `# from app.modules.flan import models as flan_models` |
| `flan` is **already** seeded in the module catalog (disabled by default) | `backend/app/core/modules_seed.py:26` — `("flan", "FLAN — Project Management", False, 30)` |
| `flan:read`/`flan:write` are **not** seeded | `backend/app/modules/auth/seed.py` `_PERMISSIONS` (l.32ff) and `_USER_ROLE_PERMS` (l.47ff) — both idempotent upserts |
| Module registration idiom | `backend/app/modules/gelato/__init__.py` (MODULE_NAME + `import router` + `registry.register`) then `importlib.import_module("app.modules.flan")` in `backend/app/main.py` (add alongside lines 78-83) |
| Audit is written at the **router** layer after the service commit | `backend/app/modules/gelato/router.py:56` (`from app.modules.auth.service import write_audit`) and its call sites, e.g. `create_bin_endpoint` |
| Service is a **package** from day one | `backend/app/modules/gelato/service/`, `backend/app/modules/crumb/service/` |
| Numeric-safe key generator exemplar | `backend/app/modules/crumb/service/quotes.py:68-90` — regex filter **before** the cast |
| Archived-entity write rejection precedent | `backend/app/modules/gelato/service/putaway.py:175-179` — HTTP **422** with a naming detail |
| Sidebar auto-renders one NavLink per visible module at `/<module.key>`; visibility is `enabled ∩ <key>:read` (admin wildcard) | `frontend/src/components/Sidebar.tsx`, `frontend/src/components/AppShell.tsx:33-44` |
| Suite route folder shape | `frontend/src/routes/gelato/` — `hooks.ts`, `components/`, colocated `*.test.tsx`; routes registered in `frontend/src/App.tsx` |
| CI `verify-scripts` / `verify-scripts-api` jobs are **glob-driven** — no workflow edit needed | `.github/workflows/ci.yml:275`, `:484` (`for s in scripts/verify_*.py` / `verify_*_api.py`) |
| No ORM column in the repo uses `ARRAY`/`JSON` today | `grep -rn "ARRAY\|JSONB\|JSON(" backend/app/modules/*/models.py` → no matches |

### How to run things (paste-able; commands below assume these)

```bash
export BNS=/home/zack/Projects/BizNiceSweets
# secrets live in $BNS/.env (JWT_SECRET, BNS_ADMIN_PASSWORD) and $BNS/.env.db (POSTGRES_PASSWORD)
export PGTEST='POSTGRES_HOST=localhost POSTGRES_PORT=5432 TEST_POSTGRES_DB=biznice_test'
```

- **Dev stack up:** `cd $BNS && podman-compose -f compose/compose.yml -f compose/compose.dev.yml up -d`
- **Verify scripts (in-container, needs `PYTHONPATH=/app` — recurring tax, 7 phases running):**
  `podman exec -e PYTHONPATH=/app compose_api_1 python scripts/verify_flan.py`
- **⚠ The backend pytest suite CANNOT run in-container.** `pytest` is absent from the image and the
  bind-mounted `backend/.venv/bin/pytest` carries host-path shebangs (`.zj/STATE.md:348`). Run it
  **from the host venv against a host-reachable Postgres** (publish the compose `db` port
  temporarily, or point at a local Postgres — compose `db` is never host-mapped by default):
  `cd $BNS/backend && env $PGTEST POSTGRES_PASSWORD=<from .env.db> JWT_SECRET=<from .env> BNS_ADMIN_PASSWORD=<from .env> .venv/bin/python -m pytest -q`
- **Backend lint:** `cd $BNS/backend && .venv/bin/ruff check .` (must exit 0)
- **Frontend:** `cd $BNS/frontend && npm run lint && npm run test && npm run build` (all exit 0)

### Design constraints this plan fixes (not open questions)

- **No stored rollup columns.** `flan_phase` has no `start_date`/`due_date`/`percent_complete`.
  `service/rollup.py` computes them in ONE grouped query per read
  (`MIN(start_date), MAX(due_date), COUNT(*), COUNT(*) FILTER (WHERE status='Done')` grouped by
  `phase_id`), and phases absent from the result set are the empty-phase case.
- **`percent_complete` is a `Decimal` quantized to `0.01`, serialized as a string** (D-11 house rule:
  never float across the wire). Empty phase → `"0.00"`.
- **`flan_task` carries BOTH `phase_id` and `project_id`.** The key-uniqueness constraint is
  `UniqueConstraint(project_id, key)`, which needs the column; the service enforces
  `task.project_id == phase.project_id` on every write.
- **Archived-project guard is one shared helper** (`service/_common.py::require_writable_project`),
  called by every mutating service function including phase/task/roster/assignment writes — "an
  archived project rejects writes" means all writes inside it, not just to the project row. Status
  **422**, mirroring the archived-bin precedent.
- **Key generation casts to `Numeric`, never `Integer`.** The PLUM-01 Phase-7 defect
  (`7562a02`) was exactly this: an `int4` cast made every auto-numbered create 500 *permanently* once
  a legal 10-digit suffix existed. `key_prefix` is validated `^[A-Za-z][A-Za-z0-9]{0,9}$` at the
  schema layer so it can be interpolated into the `~` regex safely.
- **The key-collision retry is narrow and bounded.** Catch `IntegrityError` only when the
  `uq_flan_task_project_key` constraint name appears in the error; retry at most 3 times; re-raise
  everything else. (LEARNINGS keeper: FLAN's task insert also carries a `phase_id` FK and assignee
  links, so a broad `except IntegrityError → retry` is the Phase-13 `create_invoice`
  unbounded-recursion 500 waiting to happen.) The project row is `SELECT ... FOR UPDATE`-locked
  before key generation; concurrency is *not* a phase-1 verify crux.
- **`flan_team_member.user_id` FK is `ondelete="SET NULL"`.** A `RESTRICT` default would make
  deleting a platform user fail — the roster row and its assignment history must survive
  (FLAN-01.4). Auth's own path is deactivation (`user.deactivated`,
  `backend/app/modules/auth/router.py:346`), which touches nothing here.
- **Endpoint surface** (mount_all adds `/api/v1`; every route carries `Depends(require_permission(...))`):
  `GET/POST /flan/projects`, `GET/PATCH /flan/projects/{id}`, `POST /flan/projects/{id}/archive`,
  `GET/POST /flan/projects/{id}/phases`, `PATCH/DELETE /flan/phases/{id}`,
  `GET/POST /flan/projects/{id}/tasks`, `GET/PATCH/DELETE /flan/tasks/{id}`,
  `GET/POST /flan/projects/{id}/team`, `PATCH/DELETE /flan/team/{id}`,
  `PUT /flan/tasks/{id}/assignees`, `PUT /flan/phases/{id}/assignees`.
- **FLAN is seeded ENABLED, so its nav appears as soon as the module registers.** Corrected at
  plan review: the `False` in `("flan", "FLAN — Project Management", False, 30)`
  (`backend/app/core/modules_seed.py:26`) is `always_on`, not `enabled` — the insert three lines
  below hardcodes `enabled=True` (`:52`, comment "new modules default ON"), and the `0003`
  migration gives the column `server_default=true`. So no admin toggle is needed to see FLAN.
  Two consequences: a UI verify step must **not** be written as "enable FLAN first, then assert the
  nav appears" (it would pass vacuously); and the CORE-07/08 gating assertion has to be made the
  other way round — toggle FLAN **off** at `/settings/modules`, assert the nav item disappears,
  toggle it back on. Note that on an existing dev database `flan` was already seeded at Phase 3,
  so confirm its current `enabled` value rather than assuming either way:
  `podman exec compose_db_1 psql -U biznice -d biznice -c "select key, enabled, always_on from modules where key='flan'"`.
- **Branch:** `feature-flan-core`. Checklist: `docs/tasks/feature-flan-core.md`. Conventional
  commits; **never** a co-authored / generated-with-Claude line.

---

## Decisions taken at plan review

Resolved with the owner on 2026-08-18 before build. **Binding — do not relitigate.** Appended to
`.zj/DECISIONS.md`. (ID namespace: `D-V5P1-*` = milestone v5.0, Phase 1 — `D-P1-*` was already
spent by v4.0's Phase 1.)

### D-V5P1-5 — Tags live in two join tables

`flan_project_tag(project_id, tag)` and `flan_task_tag(task_id, tag)`, tag stored as a plain
normalized string exactly as both prototypes hold it (`schedule_gate-v45.html:1513`, `:860` parse
`Facet:Value` at read, they do not store it decomposed).

*Why:* FLAN-02.6's `in-plan` basis filter and FLAN-03.4's group-by-facet are both SQL aggregations
over tags, and a join table answers them with a plain `JOIN … GROUP BY` — the shape 2a needs, and
one 2a can add facet validation to without a migration. It also keeps the codebase's
zero-exotic-column-types record intact: **no `ARRAY`, `JSONB` or `JSON` column exists anywhere in
`backend/app/modules/*/models.py` today** (verified). *Rejected:* an `ARRAY(String)` column (one
column instead of two tables and a 1:1 match to the prototype's in-memory shape, but group-by-facet
in 2a then needs Postgres-specific `unnest`, and it would be the codebase's first array column); and
deferring tags to 2a entirely (smallest Phase 1, but AC1 and AC3 both name tags literally, so
FLAN-01 could not be marked complete at this phase's verify and the roadmap's phase→FR mapping would
have needed amending).

*Phase-1 scope of this decision:* store, read and round-trip tags. **No facet semantics** — no
exclusivity rules, no reserved-facet validation, no `Facet:Value` parsing. Those are FLAN-04, next
phase. A Phase-1 tag is an opaque string.

### D-V5P1-6 — Removing a roster member is a soft-remove

`remove_member` sets `active=False` on the `flan_team_member` row and deletes that member's
`flan_task_assignee` / `flan_phase_assignee` rows in the same transaction. Removed members are
excluded from assignee pickers and from `list_members` by default (`include_removed=False`).

*Why:* it makes FLAN-01.4's "leaves its history untouched" true by construction rather than by care
— a removed member's name stays resolvable behind any past reference, which FLAN-05/06/10 (risks,
notes, comments, the activity log) will all need — and it matches the archive-not-delete precedent
every other suite already follows (`crumb_lead.active`, `gelato_bin.active`, `syerp_partner.active`).
*Rejected:* hard-deleting the row after clearing assignments — the literal reading of "removing" and
the simplest service code, but a later phase rendering who *used* to own a task finds a dangling id,
and any future FK from FLAN-05/06 to a member would have to be nullable-and-orphanable.

### D-V5P1-7 — Task keys are unpadded: `PRJ-1`, `PRJ-9`, `PRJ-10`

*Why:* it is what the SRD's own verification literal says (`PRJ-9 → PRJ-10`) and what both
prototypes do (`schedule_gate-v45.html:3205`, `return pre+'-'+(max+1)`). A task key is a handle
people type and say aloud, inherited from the prototypes — not a document number like `QUOTE-0001`.
The digit-boundary defect D-P8-6 exists to prevent lives in the **numeric cast**, not in the
padding, so it is caught either way (Task 13 difference 2, `Numeric` not `Integer`).
*Rejected:* zero-padding to `<PREFIX>-####`, which matches the SRD's format sketch and the
platform's other generated series (`QUOTE-`/`SO-`/`WO-####`) and sorts correctly as a plain string,
but disagrees with both prototypes and would force verify scenario (B) to hand-insert a legacy
`PRJ-9` to reach the digit boundary instead of arriving there naturally.

*Consequence for sorting:* a plain string sort over unpadded keys puts `PRJ-10` before `PRJ-9`. Any
UI or service list that orders by key must sort on the **numeric suffix**, not the raw string.

---

## Tasks

### [x] 1. Open the `feature-flan-core` branch with its task checklist
- **Files:** `docs/tasks/feature-flan-core.md` (new)
- **Do:** Branch from `master` as `feature-flan-core` (project rule: `feature-*`). Create the
  checklist file listing tasks 2–35 of this plan verbatim as unchecked items, each with its
  FLAN-01.N citation. This is the artifact `CLAUDE.md` requires for every code-changing task; it is
  updated before each commit and archived to `docs/tasks/_completed/` at phase close.
- **Done when:** `git branch --show-current` prints `feature-flan-core`; the checklist file exists
  with 34 unchecked items.
- **Verify:** `cd $BNS && git branch --show-current && grep -c '^- \[ \]' docs/tasks/feature-flan-core.md`
- **Parallel-ok:** no (gates everything)

---

## Wave A — schema

### [x] 2. Define the Project, Phase and Task ORM models
- **Serves:** FLAN-01.1, FLAN-01.2, FLAN-01.3
- **Files:** `backend/app/modules/flan/models.py` (new), `backend/app/modules/flan/__init__.py`
  (new, empty placeholder for now — registration is Task 5), `backend/app/core/models.py` (uncomment
  the waiting `from app.modules.flan import models as flan_models  # noqa: F401` line)
- **Do:** Follow `backend/app/modules/crumb/models.py` exactly — `String(36)` uuid PKs with
  `default=lambda: str(uuid.uuid4())`, `Numeric(18,6)` for money, ABOUTME header, per-class
  docstrings naming why each column exists.
  - `Project` → `flan_project`: `id`, `name` (not null, duplicates allowed — **no** unique
    constraint), `key_prefix` `String(10)` not null (D-V5P1-2), `category` `String(30)` nullable
    (`work|personal|client|none`, from `flan/app/prj-mgmt-v24.html:2457`), `description` nullable,
    `currency` `String(3)` not null default `"USD"`, `start_date` `Date` nullable, `gate_date` `Date`
    nullable, `active` `Boolean` default `True` (the archive flag), `created_at`, `updated_at`.
  - `Phase` → `flan_phase`: `id`, `project_id` FK `flan_project.id` not null indexed, `name`,
    `sort_order` `Integer` not null default 0, `status` `String(20)` default `"pending"`,
    `description` nullable, `created_at`. **Deliberately no `start_date`, `due_date` or
    `percent_complete` column** — state that in the class docstring citing D-V5-1.
  - `Task` → `flan_task`: `id`, `phase_id` FK `flan_phase.id` **`ondelete="CASCADE"`** not null
    indexed, `project_id` FK `flan_project.id` not null indexed, `key` `String(20)` not null,
    `summary` not null, `status` `String(20)` default `"To Do"`, `start_date` `Date` nullable,
    `due_date` `Date` nullable, `risk_level` `String(10)` default `"none"`, `pinned` `Boolean`
    default `False`, `created_at`, `updated_at`; `__table_args__ =
    (UniqueConstraint("project_id", "key", name="uq_flan_task_project_key"),)`.
  - `ProjectTag` → `flan_project_tag` and `TaskTag` → `flan_task_tag` (D-V5P1-5): composite PK
    `(project_id, tag)` / `(task_id, tag)`, FK `ondelete="CASCADE"`, `tag` `String(60)` not null.
    Phase 1 stores an **opaque normalized string** — no `Facet:Value` parsing, no exclusivity, no
    reserved facets; that is FLAN-04 next phase. Index `tag` on both, since 2a groups by it.
- **Done when:** `python -c "import app.core.models; from app.core.base import Base; print(sorted(t for t in Base.metadata.tables if t.startswith('flan_')))"` lists the flan tables; no other module's
  tables change.
- **Verify:** `cd $BNS/backend && env $PGTEST POSTGRES_PASSWORD=x JWT_SECRET=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx BNS_ADMIN_PASSWORD=x .venv/bin/python -c "import app.core.models; from app.core.base import Base; print([t for t in Base.metadata.tables if t.startswith('flan_')])" && .venv/bin/ruff check .`
- **Parallel-ok:** no

### [x] 3. Define the TeamMember model and the two assignment join tables
- **Serves:** FLAN-01.4, FLAN-01.5
- **Files:** `backend/app/modules/flan/models.py`
- **Do:**
  - `TeamMember` → `flan_team_member`: `id` uuid, `project_id` FK not null indexed, `name` not null,
    `role` nullable, `email` nullable, `color` `String(7)` nullable, `hourly_rate` `Numeric(18,6)`
    nullable (docstring: **stored, read by nothing in v5.0** — D-V5-2 / D-M5-2), `user_id`
    `String(36)` FK `users.id` **`ondelete="SET NULL"`** nullable, `active` `Boolean` default `True`,
    `created_at`. `UniqueConstraint("project_id", "user_id", name="uq_flan_member_project_user")`
    (Postgres permits many NULLs, so unlinked members are unconstrained).
  - `TaskAssignee` → `flan_task_assignee`: composite PK `(task_id, member_id)`; `task_id` FK
    `flan_task.id` `ondelete="CASCADE"`, `member_id` FK `flan_team_member.id` (no cascade — clearing
    assignments is an explicit, audited service action).
  - `PhaseAssignee` → `flan_phase_assignee`: composite PK `(phase_id, member_id)`, same FK shape
    against `flan_phase.id`.
- **Done when:** the metadata print from Task 2 additionally lists `flan_team_member`,
  `flan_task_assignee`, `flan_phase_assignee`.
- **Verify:** same command as Task 2 (list must now include the three new table names), then
  `cd $BNS/backend && .venv/bin/ruff check .`
- **Parallel-ok:** no (same file as Task 2)

### [x] 4. Seed the `flan:read` and `flan:write` permissions
- **Serves:** FLAN-01.7 (CORE-05, D-P10-6)
- **Files:** `backend/app/modules/auth/seed.py`
- **Do:** Add `("flan:read", "Read access to FLAN (project management)")` and
  `("flan:write", "Write access to FLAN")` to `_PERMISSIONS` (line 32ff), and both codes to
  `_USER_ROLE_PERMS` (line 47ff). Both structures are idempotent upserts, so this is safe against an
  existing database. Update the module docstring's permission list.
- **Done when:** after a stack restart, `SELECT code FROM permissions WHERE code LIKE 'flan:%'`
  returns exactly two rows, and the seeded `user` role holds both.
- **Verify:** `cd $BNS && podman-compose -f compose/compose.yml -f compose/compose.dev.yml restart api && sleep 15 && podman exec compose_db_1 psql -U postgres -d biznice -c "SELECT p.code FROM permissions p JOIN role_permissions rp ON rp.permission_id=p.id JOIN roles r ON r.id=rp.role_id WHERE p.code LIKE 'flan:%' AND r.name='user' ORDER BY 1;"`
- **Parallel-ok:** yes (independent of Tasks 2/3)

### [x] 5. Register the flan module with the app registry
- **Serves:** FLAN-01.7 (CORE-07)
- **Files:** `backend/app/modules/flan/__init__.py`, `backend/app/modules/flan/router.py` (new —
  stub carrying `router = APIRouter()` and the endpoint-surface docstring; routes land in Tasks 17-18),
  `backend/app/main.py`
- **Do:** Mirror `backend/app/modules/gelato/__init__.py` line for line: ABOUTME header,
  `MODULE_NAME = "flan"`, `from app.modules.flan.router import router  # noqa: F401`,
  `registry.register(sys.modules[__name__])`. Add `importlib.import_module("app.modules.flan")` in
  `backend/app/main.py` alongside lines 78-83.
- **Done when:** the API boots with `flan` registered and mounted; a **cold** process (not a
  `--reload` restart) starts clean — the LEARNINGS keeper about adding a module to `main.py`'s import
  list and a table to shared metadata (a cross-module FK-resolution 500 that pre-warmed fixtures miss).
- **Verify:** `cd $BNS && podman-compose -f compose/compose.yml -f compose/compose.dev.yml down && podman-compose -f compose/compose.yml -f compose/compose.dev.yml up -d && sleep 25 && curl -sf http://localhost:8000/api/v1/health && curl -s http://localhost:8000/openapi.json | grep -c '/flan'`
- **Parallel-ok:** no (needs Task 2)

### [x] 6. Generate and apply Alembic migration 0018 for the FLAN tables
- **Serves:** FLAN-01.1, .2, .3, .4, .5
- **Files:** `backend/alembic/versions/0018_flan_core.py` (new)
- **Do:** Autogenerate against the running dev DB, then hand-review: `revision = "0018"`,
  `down_revision = "0017"`, every table prefixed `flan_`, the `ondelete="CASCADE"` on
  `flan_task.phase_id` and `flan_task_assignee.task_id`, the `SET NULL` on
  `flan_team_member.user_id`, and both unique constraints present by name. Write a real `downgrade()`
  dropping the tables in FK-safe order. Note: autogenerate is **blind without the aggregator line**
  from Task 2 (Pitfall 1); if the migration comes out empty, that line is the cause.
  ⚠ Autogenerate must run from the **host venv** — writing to the bind-mounted
  `backend/alembic/versions/` from inside the container hits `PermissionError` (`.zj/LEARNINGS.md:1024`).
- **Done when:** `alembic upgrade head` reports `Running upgrade 0017 -> 0018`; every `flan_*` table
  exists in the database; `alembic downgrade 0017` then `upgrade head` round-trips cleanly.
- **Verify:** `cd $BNS/backend && env $PGTEST POSTGRES_PASSWORD=<from .env.db> JWT_SECRET=<from .env> BNS_ADMIN_PASSWORD=<from .env> .venv/bin/python -m pytest tests/test_migrations.py -q` then `podman exec compose_db_1 psql -U postgres -d biznice -c "\dt flan_*"`
- **Parallel-ok:** no (needs Tasks 2, 3)

---

## Wave B — service + router

### [x] 7. Write the project and phase Pydantic schemas
- **Serves:** FLAN-01.1, FLAN-01.2
- **Files:** `backend/app/modules/flan/schemas.py` (new)
- **Do:** Mirror `backend/app/modules/gelato/schemas.py` (ConfigDict `from_attributes=True`, field
  docstrings, `Decimal` serialized as string). `ProjectCreate` (name required; `key_prefix` optional —
  the service derives it from the name when omitted, pattern `^[A-Za-z][A-Za-z0-9]{0,9}$`),
  `ProjectUpdate` (all optional; **no** `id`, **no** `active`), `ProjectRead`.
  `PhaseCreate`, `PhaseUpdate` (name/sort_order/status/description only — **no date or percent
  fields anywhere in the write schemas**, D-V5-1), and `PhaseRead` carrying the three **derived**
  fields `derived_start_date: date | None`, `derived_due_date: date | None`,
  `percent_complete: str` plus `task_count` and `done_count`. Both `ProjectRead` and `ProjectCreate`
  carry `tags: list[str]` (D-V5P1-5), defaulting to `[]`, validated non-empty-after-strip and
  deduplicated case-sensitively.
- **Done when:** `PhaseUpdate.model_fields` contains no date or percent key; `PhaseRead` validates
  a rollup with all-None dates and `percent_complete="0.00"`.
- **Verify:** `cd $BNS/backend && .venv/bin/python -c "from app.modules.flan.schemas import PhaseUpdate, PhaseRead; assert not {'start_date','due_date','percent_complete'} & set(PhaseUpdate.model_fields), PhaseUpdate.model_fields; print('ok')" && .venv/bin/ruff check .`
- **Parallel-ok:** yes (with Task 8, if the two authors split the file cleanly)

### [x] 8. Write the task, roster and assignment Pydantic schemas
- **Serves:** FLAN-01.3, FLAN-01.4, FLAN-01.5
- **Files:** `backend/app/modules/flan/schemas.py`
- **Do:** `TaskCreate` (phase_id, summary required; `key` is **never** client-supplied — the service
  generates it; status `Literal["To Do","In Progress","Done"]`, risk_level
  `Literal["none","low","medium","high"]`, start_date/due_date optional, pinned, assignee_ids),
  `TaskUpdate` (all optional, `key` and `project_id` absent), `TaskRead` (includes `key` and
  `assignee_ids`). `TeamMemberCreate/Update/Read` (name, role, email, color, `hourly_rate: Decimal |
  None`, `user_id: str | None`, `active`). `AssigneeSet` — `{ "member_ids": [...] }`, the full
  replacement list for `PUT .../assignees`. Add a **model validator on `TaskCreate`/`TaskUpdate`
  rejecting `due_date < start_date`** so the 4xx is a 422 from the schema layer *and* re-checked in
  the service (Task 14) for the PATCH-merges-with-stored-row case.
- **Done when:** `TaskCreate(summary="x", phase_id="p", start_date=date(2026,1,10), due_date=date(2026,1,9))` raises `ValidationError`; the same call with equal dates constructs (zero-duration milestone).
- **Verify:** `cd $BNS/backend && .venv/bin/python -c "
from datetime import date; from pydantic import ValidationError
from app.modules.flan.schemas import TaskCreate
try: TaskCreate(phase_id='p', summary='x', start_date=date(2026,1,10), due_date=date(2026,1,9)); raise SystemExit('FAIL: due<start accepted')
except ValidationError: pass
TaskCreate(phase_id='p', summary='x', start_date=date(2026,1,10), due_date=date(2026,1,10)); print('ok')"`
- **Parallel-ok:** yes (with Task 7)

### [x] 9. Build the flan service package skeleton with the archived-project guard
- **Serves:** FLAN-01.1
- **Files:** `backend/app/modules/flan/service/__init__.py` (new),
  `backend/app/modules/flan/service/_common.py` (new)
- **Do:** Mirror `backend/app/modules/crumb/service/_common.py` and
  `backend/app/modules/gelato/service/__init__.py` (package that re-exports the public surface).
  `_common.py` provides:
  - `get_project_or_404(db, project_id) -> Project`
  - `require_writable_project(db, project_id) -> Project` — 404 if missing, **422** if
    `active is False`, detail `f"Project {project_id} is archived and rejects writes."` (mirrors
    `gelato/service/putaway.py:175`).
  - `resolve_phase(db, phase_id)` / `resolve_task(db, task_id)` returning the row **and** its owning
    project id, so every downstream mutation can call `require_writable_project` with one lookup.
  Lazy imports of models inside functions (house idiom).
- **Done when:** `from app.modules.flan.service import require_writable_project` resolves;
  `ruff check .` exits 0.
- **Verify:** `cd $BNS/backend && .venv/bin/python -c "from app.modules.flan.service import require_writable_project; print('ok')" && .venv/bin/ruff check .`
- **Parallel-ok:** no

### [x] 10. Implement project CRUD and archive in the service
- **Serves:** FLAN-01.1, FLAN-01.6
- **Files:** `backend/app/modules/flan/service/projects.py` (new),
  `backend/app/modules/flan/service/__init__.py`
- **Do:** `list_projects(db, include_archived=False)`, `get_project`, `create_project`,
  `update_project`, `archive_project`. `create_project` derives `key_prefix` from the name when the
  client omits it — first 4 alphanumeric-uppercase characters of the name (e.g. `"Crisis
  Simulator"` → `"CRIS"`), falling back to `"PRJ"` if the name yields nothing; **duplicate names are
  allowed** so there is no uniqueness pre-check. `update_project` refuses to change `id`, and
  refuses `key_prefix` once `SELECT 1 FROM flan_task WHERE project_id = :id LIMIT 1` returns a row
  (**422**, D-V5P1-2); it calls `require_writable_project` first. `archive_project` sets
  `active=False` and is idempotent.
- **Done when:** creating two projects with the same name succeeds; patching `key_prefix` succeeds
  on a task-free project and 422s once one task exists; every write against an archived project 422s.
- **Verify:** covered end-to-end by `verify_flan.py` scenario (E) in Task 28; for this commit:
  `cd $BNS/backend && .venv/bin/ruff check . && .venv/bin/python -c "from app.modules.flan.service import create_project, archive_project, list_projects; print('ok')"`
- **Parallel-ok:** no

### [x] 11. Implement the phase-derived dates and % rollup  ⟵ **THE CRUX**
- **Serves:** FLAN-01.2 (D-V5-1)
- **Files:** `backend/app/modules/flan/service/rollup.py` (new),
  `backend/app/modules/flan/service/__init__.py`
- **Do:** One public function
  `async def phase_rollups(db, phase_ids: Sequence[str]) -> dict[str, PhaseRollup]`, plus a pure
  helper `def _percent(done: int, total: int) -> Decimal` so the arithmetic is unit-testable without
  a DB (the `_next_quote_number` precedent).
  - ONE grouped query:
    `select(Task.phase_id, func.min(Task.start_date), func.max(Task.due_date), func.count(), func.count().filter(Task.status == "Done")).where(Task.phase_id.in_(phase_ids)).group_by(Task.phase_id)`
  - Every requested phase id appears in the returned dict. Ids **absent from the query result have
    no tasks** → `PhaseRollup(derived_start_date=None, derived_due_date=None, percent_complete=Decimal("0.00"), task_count=0, done_count=0)`. There is no division to guard because the
    zero branch never reaches `_percent`.
  - `_percent` returns `(Decimal(done) / Decimal(total) * 100).quantize(Decimal("0.01"), ROUND_HALF_UP)`.
  - Docstring must state that SQL `MIN`/`MAX` skip NULLs, so a phase whose tasks all lack dates
    reports no dates but a real percentage — and that this is intended.
  - **Never** write these values to any column.
- **Done when:** the pure helper satisfies `_percent(0,3)=="0.00"`, `_percent(1,3)=="33.33"`,
  `_percent(3,3)=="100.00"`; `phase_rollups(db, [id_of_empty_phase])` returns the empty-phase shape.
- **Verify:** `cd $BNS/backend && .venv/bin/python -c "
from decimal import Decimal
from app.modules.flan.service.rollup import _percent
assert str(_percent(0,3))=='0.00' and str(_percent(1,3))=='33.33' and str(_percent(3,3))=='100.00'
print('ok')" && .venv/bin/ruff check .`
- **Parallel-ok:** no

### [x] 12. Implement phase CRUD with delete-cascades-to-tasks
- **Serves:** FLAN-01.2
- **Files:** `backend/app/modules/flan/service/phases.py` (new),
  `backend/app/modules/flan/service/__init__.py`
- **Do:** `list_phases(db, project_id)` — ordered by `sort_order` then `name`, and it attaches the
  Task-11 rollup to every returned `PhaseRead` in **one** batched `phase_rollups` call (no N+1).
  `create_phase`, `update_phase` (name/sort_order/status/description only), `delete_phase` — issues
  `DELETE FROM flan_phase WHERE id = :id` and lets the DB `ondelete="CASCADE"` remove the tasks, then
  returns the count of tasks removed (read before the delete) so the router audit detail can name it.
  Every mutation calls `require_writable_project`.
- **Done when:** `list_phases` on a project with one empty phase and one 3-task phase returns both,
  the empty one with `percent_complete == "0.00"` and null dates; deleting a phase with 3 tasks
  leaves 0 rows in `flan_task` for that phase.
- **Verify:** proven live by `verify_flan.py` scenarios (A) and (F), Tasks 27/28; for this commit:
  `cd $BNS/backend && .venv/bin/ruff check . && .venv/bin/python -c "from app.modules.flan.service import list_phases, delete_phase; print('ok')"`
- **Parallel-ok:** no

### [x] 13. Implement the numeric-safe task key generator
- **Serves:** FLAN-01.3 (D-P8-6)
- **Files:** `backend/app/modules/flan/service/keys.py` (new),
  `backend/app/modules/flan/service/__init__.py`
- **Do:** Port `generate_quote_number` (`backend/app/modules/crumb/service/quotes.py:68-90`) with
  three deliberate differences, each of which must be named in the docstring:
  1. it is **project-scoped** (`Task.project_id == project_id`) and uses the project's stored
     `key_prefix`, not a literal;
  2. the cast target is **`Numeric`, not `Integer`** — the PLUM-01 Phase-7 defect `7562a02` (a legal
     10-digit suffix made every auto-numbered create 500 permanently);
  3. the regex `^{prefix}-[0-9]+$` filter runs **before** the cast (a bare cast over `LIKE` throws on
     a non-numeric key), and `prefix` is safe to interpolate because the schema validates it against
     `^[A-Za-z][A-Za-z0-9]{0,9}$`.
  Expose a pure `_next_key(prefix, existing_max: int | None) -> str` returning
  `f"{prefix}-{n}"` — **unpadded** (D-V5P1-7). `None` → `-1`. Unlike the platform's document series
  (`QUOTE-0001`, `SO-0001`, `WO-0001`) a task key is a handle people type and say aloud, and the
  SRD's own verification names the literal `PRJ-9 → PRJ-10`; both prototypes agree
  (`schedule_gate-v45.html:3205`, `return pre+'-'+(max+1)`). The digit-boundary defect D-P8-6
  guards against lives in the **cast**, not the padding, so difference (2) below still catches it.
- **Done when:** `_next_key("PRJ", 9) == "PRJ-10"` and `_next_key("PRJ", None) == "PRJ-1"`;
  against a live project holding `PRJ-9`, the generator returns `PRJ-10`-series numbering rather than
  a lexicographic sibling of `PRJ-9`.
- **Verify:** `cd $BNS/backend && .venv/bin/python -c "
from app.modules.flan.service.keys import _next_key
assert _next_key('PRJ', 9)=='PRJ-10' and _next_key('PRJ', None)=='PRJ-1'; print('ok')" && .venv/bin/ruff check .`
  (live `PRJ-9 → PRJ-10` proof is `verify_flan.py` scenario (B), Task 28)
- **Parallel-ok:** yes (independent of Tasks 11/12)

### [x] 14. Implement task CRUD with server-side date validation
- **Serves:** FLAN-01.3
- **Files:** `backend/app/modules/flan/service/tasks.py` (new),
  `backend/app/modules/flan/service/__init__.py`
- **Do:** `list_tasks(db, project_id, phase_id=None, assignee_id=None)` (the assignee filter is
  FLAN-01.5's "board can be filtered by assignee"), `get_task`, `create_task`, `update_task`,
  `delete_task`.
  - `create_task`: `require_writable_project`, resolve the phase and set `project_id` from
    `phase.project_id` (never from the client), `SELECT ... FOR UPDATE` the project row, call
    `generate_task_key`, insert. Wrap the insert in a **bounded 3-attempt** retry that catches
    `IntegrityError` **only when `"uq_flan_task_project_key"` appears in `str(exc.orig)`** and
    re-raises anything else — the phase FK and the assignee links can raise `IntegrityError` too, and
    a broad catch here is the Phase-13 `create_invoice` unbounded-recursion 500 (LEARNINGS keeper).
  - `update_task`: merge the patch onto the stored row, then re-check `due_date >= start_date` over
    the **merged** values (422) — the schema validator alone cannot see a PATCH that moves only one
    of the two dates. `key` and `project_id` are immutable. Moving a task between phases within the
    same project is allowed; across projects is 422.
  - **⚠ ADDED AT BUILD (see `## Deviations`): `create_task` MUST consume `assignee_ids` and `tags`,
    and `update_task` must apply them too.** Task 8 put both on `TaskCreate`/`TaskUpdate`, but this
    task's text describes only the insert and the key retry — so a literal reading builds a service
    that accepts both fields over the wire and **silently drops them**. That is the 11a/11b
    "green backend, dead through the UI" defect exactly. Assert the round-trip through
    `TaskRead.model_validate(...)`, not just service-side, the way Task 10 closed the same trap for
    project tags.
- **Done when:** creating a task with `due == start` succeeds; `due < start` 422s on both POST and
  PATCH (including the patch-one-date case); a created task's `key` matches `^<PREFIX>-\d+$` and
  its `project_id` equals its phase's.
- **Verify:** live proof in `verify_flan.py` scenarios (B)/(C), Task 28; for this commit:
  `cd $BNS/backend && .venv/bin/ruff check . && .venv/bin/python -m pytest tests/flan -q` (no-op
  until Task 31 adds the package — acceptable, ruff is the gate here)
- **Parallel-ok:** no (needs Task 13)

### [x] 15. Implement team-roster CRUD with removal clearing assignments
- **Serves:** FLAN-01.4
- **Files:** `backend/app/modules/flan/service/roster.py` (new),
  `backend/app/modules/flan/service/__init__.py`
- **Do:** `list_members(db, project_id, include_removed=False)`, `create_member`, `update_member`,
  `remove_member`. `create_member`/`update_member` accept an optional `user_id`; validate it names an
  existing row in `users` (404 if not) and that no other **active** member of the project already
  links it (422, backed by `uq_flan_member_project_user`). `hourly_rate` is stored and read by
  nothing — say so in the docstring citing D-M5-2. `remove_member` is a **soft-remove** (D-V5P1-6):
  set `active=False` on the member row, and delete the member's `flan_task_assignee` and
  `flan_phase_assignee` rows in the same transaction while **touching no task row** — the deletes
  must be scoped by `member_id`, never by `task_id`. `list_members` excludes `active=False` members
  unless `include_removed=True`; assignee pickers use the default.
- **Done when:** removing a member with 2 assigned tasks leaves both tasks present and unmodified
  (`updated_at` unchanged) with 0 assignee rows for that member; a member created with no `user_id`
  is fully usable as an assignee.
- **Verify:** live proof in `verify_flan.py` scenario (D), Task 28; for this commit:
  `cd $BNS/backend && .venv/bin/ruff check . && .venv/bin/python -c "from app.modules.flan.service import remove_member, create_member; print('ok')"`
- **Parallel-ok:** yes (independent of Tasks 13/14)

### [x] 16. Implement phase and task assignment set/clear
- **Serves:** FLAN-01.5
- **Files:** `backend/app/modules/flan/service/assignments.py` (new),
  `backend/app/modules/flan/service/__init__.py`
- **Do:** `set_task_assignees(db, task_id, member_ids)` and `set_phase_assignees(db, phase_id,
  member_ids)` — full-replacement semantics (delete the existing rows, insert the given set). Every
  `member_id` must be an **active** member of the **same project** as the target (422 naming the
  offending id) — this is what makes "assignees drawn from the project roster" enforced rather than
  conventional. An empty list is valid (zero assignees). `require_writable_project` first.
- **Done when:** assigning a member from project A to a task in project B 422s; setting `[]` clears
  the rows and returns an empty list; re-setting the same list twice is idempotent (row count stays).
- **Verify:** `cd $BNS/backend && .venv/bin/ruff check . && .venv/bin/python -c "from app.modules.flan.service import set_task_assignees, set_phase_assignees; print('ok')"` — behaviour proven over HTTP in Task 30
- **Parallel-ok:** no (needs Task 15)

### [x] 17. Expose the project and phase endpoints on the FLAN router
- **Serves:** FLAN-01.1, FLAN-01.2, FLAN-01.6, FLAN-01.7 (NFR-1, CORE-05)
- **Files:** `backend/app/modules/flan/router.py`
- **Do:** Mirror `backend/app/modules/gelato/router.py` exactly — thin endpoints, full path spelled
  per route (no router prefix), `Depends(require_permission("flan:read"))` on GETs and
  `("flan:write")` on mutations, `write_audit(...)` **after** the service returns, GETs write no
  audit row. Routes: `GET/POST /flan/projects`, `GET/PATCH /flan/projects/{project_id}`,
  `POST /flan/projects/{project_id}/archive`, `GET/POST /flan/projects/{project_id}/phases`,
  `PATCH/DELETE /flan/phases/{phase_id}`. Audit actions: `project.created`, `project.updated`,
  `project.archived`, `phase.created`, `phase.updated`, `phase.deleted` (detail names the cascaded
  task count), each with `target_type` `"flan_project"`/`"flan_phase"` and `target_id=str(...)`.
  Document the whole endpoint + audit surface in the module docstring, gelato-style.
- **Done when:** `/openapi.json` lists all eight routes; each mutation carries a security dependency;
  a project create over HTTP writes exactly one `audit_log` row attributable to the caller.
- **Verify:** `cd $BNS && curl -s http://localhost:8000/openapi.json | python3 -c "import json,sys; p=json.load(sys.stdin)['paths']; print(sorted(k for k in p if k.startswith('/api/v1/flan')))"`
- **Parallel-ok:** no

### [ ] 18. Expose the task, roster and assignment endpoints on the FLAN router
- **Serves:** FLAN-01.3, FLAN-01.4, FLAN-01.5, FLAN-01.7 (NFR-1, CORE-05)
- **Files:** `backend/app/modules/flan/router.py`
- **Do:** `GET/POST /flan/projects/{project_id}/tasks` (GET takes `phase_id` and `assignee_id` query
  filters), `GET/PATCH/DELETE /flan/tasks/{task_id}`, `GET/POST /flan/projects/{project_id}/team`,
  `PATCH/DELETE /flan/team/{member_id}`, `PUT /flan/tasks/{task_id}/assignees`,
  `PUT /flan/phases/{phase_id}/assignees`. Same RBAC and post-commit audit discipline. Audit actions:
  `task.created` (detail names the generated key), `task.updated`, `task.deleted`,
  `team_member.created`, `team_member.updated`, `team_member.removed` (detail names the count of
  assignments cleared), `task.assignees_set`, `phase.assignees_set`.
- **Done when:** `/openapi.json` lists all twelve routes; every mutation has a `flan:write`
  dependency and every GET a `flan:read` one; `POST /flan/projects/{id}/tasks` returns 201 with a
  populated `key`.
- **Verify:** `cd $BNS && curl -s http://localhost:8000/openapi.json | python3 -c "import json,sys; p=json.load(sys.stdin)['paths']; ks=[k for k in p if k.startswith('/api/v1/flan')]; print(len(ks)); print('\n'.join(sorted(ks)))"` (expect 20 endpoints across the two tasks)
- **Parallel-ok:** no

---

## Wave C — UI

### [x] 19. Add the FLAN project and phase query hooks
- **Serves:** FLAN-01.1, FLAN-01.2, FLAN-01.6
- **Files:** `frontend/src/routes/flan/hooks.ts` (new)
- **Do:** Mirror `frontend/src/routes/gelato/hooks.ts` — ABOUTME header, exported query-key
  factories in one place, TanStack Query hooks over the single `@/api/client` axios instance.
  Types `Project`, `Phase` (with `derived_start_date`, `derived_due_date`, `percent_complete` typed
  **`string`** — D-11, render as-is, never `parseFloat`), keys `projectsKey()`,
  `projectKey(id)`, `phasesKey(projectId)`; hooks `useProjects`, `useProject`, `usePhases`,
  `useCreateProject`, `useUpdateProject`, `useArchiveProject`, `useCreatePhase`, `useUpdatePhase`,
  `useDeletePhase`. Phase mutations invalidate `phasesKey(projectId)`.
- **Done when:** `npm run lint` and `tsc -b` pass with the hooks imported nowhere yet (exports are
  used from Task 22 onward).
- **Verify:** `cd $BNS/frontend && npm run lint && npx tsc -b`
- **Parallel-ok:** yes (with Task 20)

### [x] 20. Add the FLAN task, roster and assignment query hooks
- **Serves:** FLAN-01.3, FLAN-01.4, FLAN-01.5
- **Files:** `frontend/src/routes/flan/hooks.ts`
- **Do:** Types `Task` (with `key`, `assignee_ids`), `TeamMember` (`hourly_rate: string | null`);
  keys `tasksKey(projectId, phaseId?, assigneeId?)`, `taskKey(id)`, `teamKey(projectId)`; hooks
  `useTasks`, `useTask`, `useCreateTask`, `useUpdateTask`, `useDeleteTask`, `useTeam`,
  `useCreateMember`, `useUpdateMember`, `useRemoveMember`, `useSetTaskAssignees`,
  `useSetPhaseAssignees`. Task mutations invalidate both `tasksKey` and `phasesKey` — **a task write
  changes its phase's derived dates and %**, so a stale phase list is the first way this crux dies
  in the UI.
- **Done when:** every task mutation's `onSuccess` invalidates `phasesKey(projectId)`; lint and
  `tsc -b` pass.
- **Verify:** `cd $BNS/frontend && grep -c "phasesKey" src/routes/flan/hooks.ts && npm run lint && npx tsc -b`
- **Parallel-ok:** yes (with Task 19)

### [x] 21. Build the FLAN nav with the project switcher
- **Serves:** FLAN-01.6 (D-V5P1-3)
- **Files:** `frontend/src/routes/flan/components/FlanNav.tsx` (new)
- **Do:** Mirror `frontend/src/routes/gelato/components/GelatoNav.tsx`. Renders the per-project
  sub-nav (Phases / Tasks / Team) plus a shadcn `Select` project switcher populated from
  `useProjects()`; choosing a project calls
  `navigate('/flan/projects/' + id + '/' + currentSection)` — it holds **no** local "active project"
  state, because the URL is the active project (D-V5P1-3). Include a link back to `/flan/projects`.
- **Done when:** switching projects changes the URL segment and nothing else; the component reads
  `useParams().projectId` for its current value.
- **Verify:** `cd $BNS/frontend && npm run lint && npx tsc -b` (behaviour asserted by the screen
  tests in Tasks 22-25)
- **Parallel-ok:** no (needs Task 19)

### [x] 22. Build the FLAN Projects list screen
- **Serves:** FLAN-01.1, FLAN-01.6
- **Files:** `frontend/src/routes/flan/Projects.tsx` (new),
  `frontend/src/routes/flan/Projects.test.tsx` (new),
  `frontend/src/routes/flan/components/ProjectCreateDialog.tsx` (new)
- **Do:** Table of projects (name, category, currency, start date, gate date, key prefix, archived
  badge) with a "Show archived" switch, a create dialog, and an archive action with confirmation.
  Row click navigates to `/flan/projects/:id/phases`. Surface 4xx `detail` strings through
  `toast.error` (the `apiError.ts` helper pattern from `routes/crumb/components/`).
- **Done when:** the colocated Vitest, modelled on `frontend/src/routes/gelato/Bins.test.tsx`,
  asserts (a) rows render from a mocked GET **and the key-prefix cell renders its actual value**
  (LEARNINGS counter-measure: assert the column renders its value, not just that it exists),
  (b) the create dialog POSTs the exact payload shape the router accepts, (c) archived rows are
  hidden until the switch is on.
- **Verify:** `cd $BNS/frontend && npx vitest run src/routes/flan/Projects.test.tsx`
- **Parallel-ok:** yes (with Tasks 23-25)

### [ ] 22a. Build the project edit dialog  ⟵ **ADDED AT BUILD (owner decision)**
- **Serves:** FLAN-01.1 (the "**edit**" verb, which no planned task covered)
- **Files:** `frontend/src/routes/flan/components/ProjectEditDialog.tsx` (new),
  `frontend/src/routes/flan/Projects.tsx`, `frontend/src/routes/flan/Projects.test.tsx`
- **Why this task exists:** FLAN-01.1 reads "Create/view/**edit**/archive a project". Tasks 22-26 as
  planned build create, view and archive — **nothing edits a project**. Phases, Tasks and Team each
  got an edit dialog; Project was the only one that did not. The backend has supported it since Task
  10 (`update_project`, verified) and Task 19 wrote `useUpdateProject`, which no screen called. Found
  by Task 22's engineer; the owner chose to close it in-phase rather than narrow the SRD.
- **Do:** Mirror `ProjectCreateDialog.tsx`. Fields: name, category, currency, description,
  start_date, gate_date, and `key_prefix`. Wire it to `useUpdateProject` from a row action on the
  Projects table. `key_prefix` is **editable until the project's first task exists, then immutable**
  (D-V5P1-2) — the server returns **422** with a `detail` naming the reason, which must surface
  through `toast.error`. Do **not** try to predict the lock client-side; let the server decide and
  render its message.
- **Done when:** the colocated Vitest asserts (a) the dialog opens pre-filled with the row's **actual
  values** (assert the rendered values, not just that inputs exist — the standing LEARNINGS
  counter-measure), (b) the PATCH body contains only keys present in `ProjectUpdate.model_fields`
  and omits `id` and `active`, (c) a mocked 422 on `key_prefix` surfaces the server's `detail` via
  `toast.error`.
- **Verify:** `cd $BNS/frontend && npx vitest run src/routes/flan/Projects.test.tsx && npm run lint && npx tsc -b --force`,
  plus the real-schema field-set check that Tasks 22 and 23 used:
  `podman run --rm --network compose_default -v "$PWD/backend:/app:z" -w /app --env-file .env --env-file .env.db -e PYTHONPATH=/app compose_api python -c "from app.modules.flan.schemas import ProjectUpdate; print(sorted(ProjectUpdate.model_fields))"`
- **Parallel-ok:** no (shares `Projects.tsx` / `Projects.test.tsx` with Task 22, which has landed)

### [x] 23. Build the project Phases screen showing the derived dates and %
- **Serves:** FLAN-01.2
- **Files:** `frontend/src/routes/flan/Phases.tsx` (new),
  `frontend/src/routes/flan/Phases.test.tsx` (new)
- **Do:** Scoped to `/flan/projects/:projectId/phases`. Table of phases in `sort_order` with columns
  **Derived start**, **Derived due**, **% complete** and task count, each rendered read-only with a
  tooltip "derived from this phase's tasks — not editable" (D-V5-1). The create/edit dialog exposes
  name, order, status and description **only** — no date or percent input anywhere. Delete shows a
  confirmation naming how many tasks will be cascaded.
- **Done when:** the colocated Vitest asserts (a) a phase row **renders the literal
  `percent_complete` string from the API** (e.g. `33.33%`) rather than a recomputed number,
  (b) an empty phase renders an em-dash for both dates and `0.00%`, (c) the edit dialog contains no
  date or percent input (`queryByLabelText(/start|due|percent/i)` is null).
- **Verify:** `cd $BNS/frontend && npx vitest run src/routes/flan/Phases.test.tsx`
- **Parallel-ok:** yes (with Tasks 22, 24, 25)

### [x] 24. Build the project Tasks screen
- **Serves:** FLAN-01.3, FLAN-01.5
- **Files:** `frontend/src/routes/flan/Tasks.tsx` (new),
  `frontend/src/routes/flan/Tasks.test.tsx` (new),
  `frontend/src/routes/flan/components/TaskSheet.tsx` (new)
- **Do:** Scoped to `/flan/projects/:projectId/tasks`. Table with **key**, summary, phase, status,
  start, due, risk, pinned, assignees; filters for phase and **assignee** (FLAN-01.5). A create/edit
  Sheet with status, risk, dates, pinned and a multi-select assignee picker fed by `useTeam` —
  **no key input** (server-generated). A `due < start` 422 surfaces as a toast carrying the server's
  `detail`.
- **Done when:** the colocated Vitest asserts (a) the **key cell renders the value returned by the
  API**, (b) the create POST body matches the router's `TaskCreate` shape exactly and contains no
  `key` field, (c) selecting the assignee filter re-fetches with `assignee_id` in the params,
  (d) a mocked 422 surfaces via `toast.error` with the server detail text.
- **Verify:** `cd $BNS/frontend && npx vitest run src/routes/flan/Tasks.test.tsx`
- **Parallel-ok:** yes (with Tasks 22, 23, 25)

### [ ] 25. Build the project Team roster screen
- **Serves:** FLAN-01.4
- **Files:** `frontend/src/routes/flan/Team.tsx` (new),
  `frontend/src/routes/flan/Team.test.tsx` (new),
  `frontend/src/routes/flan/components/MemberDialog.tsx` (new)
- **Do:** Scoped to `/flan/projects/:projectId/team`. Table of members (name, role, email, colour
  swatch, hourly rate, linked user or "—"). The dialog's platform-user link is an **optional** Select
  populated from the users endpoint with an explicit "No platform user" option, and the hourly-rate
  field carries the helper text "stored for a later milestone; no cost is derived from it in v5.0".
  Remove action confirms and names that assignments will be cleared.
- **Done when:** the colocated Vitest asserts (a) a member row **renders its hourly-rate string
  as returned** (no float formatting), (b) saving with "No platform user" POSTs `user_id: null`,
  (c) the remove confirmation copy names the assignment clearing.
- **Verify:** `cd $BNS/frontend && npx vitest run src/routes/flan/Team.test.tsx`
- **Parallel-ok:** yes (with Tasks 22-24)

### [ ] 26. Wire the FLAN routes into App.tsx with the `/flan` redirect
- **Serves:** FLAN-01.6, FLAN-01.7 (CORE-07/08)
- **Files:** `frontend/src/App.tsx`
- **Do:** Add the import block and, following the `/gelato` and `/crumb` precedent:
  `<Route path="/flan" element={<Navigate to="/flan/projects" replace />} />`,
  `/flan/projects`, `/flan/projects/:projectId/phases`, `/flan/projects/:projectId/tasks`,
  `/flan/projects/:projectId/team`. Keep the static `projects` segment **before** any `/:projectId`
  route. The Sidebar needs no change — it auto-renders a NavLink at `/flan` once the module is
  enabled and the user holds `flan:read` (`AppShell.tsx:33-44`). FLAN is seeded **enabled**, so
  assert the gate by toggling it **off** — see the corrected Context note; "enable it, then see the
  nav" would pass vacuously.
- **Done when:** a "FLAN — Project Management" nav item appears and lands on the projects list;
  toggling FLAN **off** at `/settings/modules` makes the nav item disappear and toggling it back on
  restores it; a user without `flan:read` sees no FLAN nav item; `npm run build` exits 0.
- **Verify:** `cd $BNS/frontend && npm run lint && npm run build` then, with the dev stack up,
  browse `http://localhost:5173/flan` and confirm it redirects to `/flan/projects`; then toggle FLAN
  off at `/settings/modules` and confirm the nav item is gone before toggling it back on
- **Parallel-ok:** no (needs Tasks 22-25)

---

## Wave D — verification

### [ ] 27. Write `verify_flan.py` scenario (A) — the phase-rollup crux including the empty phase
- **Serves:** FLAN-01.2 (the SRD's named verification)
- **Files:** `backend/scripts/verify_flan.py` (new)
- **Do:** ⚠ **ADDED AT BUILD:** the script MUST `import app.modules.auth.models` (or
  `app.core.models`) **before** touching `flan_team_member`, or SQLAlchemy raises
  `NoReferencedTableError` resolving `flan_team_member.user_id → users.id`. Found by Task 16's
  engineer. Note also that `backend/scripts/verify_gelato.py`'s own header documents the wrong
  container and psql role (`compose_api_1`, `-U postgres`) — the working values are `compose_api`
  and `-U app`; do not copy that header verbatim.
  Mirror `backend/scripts/verify_gelato.py`'s structure: ABOUTME header, a WHY-THIS-EXISTS
  docstring, its **own** async engine + sessionmaker from `POSTGRES_*` env (never the test conftest),
  `PASS:`/`FAIL:` prints, a `_FAILURES` counter, `main()` returning non-zero, and a `finally` cleanup
  making it re-runnable. **Drive the REAL service through the REAL schemas the router sends**
  (`create_project(db, ProjectCreate(...))`, `create_task(db, TaskCreate(...))`) — never hand-insert
  ORM rows for the headline assertions (11a/11b keeper).
  Scenario (A), four phases in one project:
  - **A0 — the empty phase, built FIRST:** a phase with zero tasks →
    `derived_start_date is None`, `derived_due_date is None`, `percent_complete == Decimal("0.00")`,
    `task_count == 0`.
    **⚠ AMENDED AT BUILD (see `## Deviations`) — A0 MUST assert the empty phase inside a BATCH in
    which a NON-empty phase comes first**, e.g. `phase_rollups(db, [dated_phase, empty_phase, ...])`.
    A solo `phase_rollups(db, [empty_phase_id])` is **vacuous against Task 29's mutation 3**: when
    the batch holds only the empty phase, `phase_ids[0]` *is* that phase, so the mutated
    fall-through returns the empty shape anyway and the assertion stays GREEN. Task 11's engineer
    hit exactly this. Assert the solo call too if you like, but the batch-with-a-non-empty-phase-
    first call is the one that carries the proof.
  - **A1 — dates:** 3 tasks with starts 2026-03-05 / 2026-03-01 / 2026-03-09 and dues 2026-03-20 /
    2026-03-11 / 2026-03-14 → derived start `2026-03-01`, derived due `2026-03-20` (proves MIN/MAX,
    not first/last inserted).
  - **A2 — percent:** 0/3 → `"0.00"`, 1/3 → `"33.33"`, 3/3 → `"100.00"`, flipping statuses through
    the real `update_task`.
  - **A3 — dates skip NULLs:** a 4th task with no dates joins A1's phase; derived dates are unchanged
    but `task_count` rises and the percentage changes.
  - **A4 — nothing is stored:** after all of the above, assert
    `[c.name for c in Phase.__table__.columns]` contains none of `start_date`, `due_date`,
    `percent_complete` — the structural half of "never hand-set".
- **Done when:** the script exits 0 with every (A) assertion PASS, and re-running it immediately
  also exits 0 (self-cleaning).
- **Verify:** `podman exec -e PYTHONPATH=/app compose_api_1 python scripts/verify_flan.py && podman exec -e PYTHONPATH=/app compose_api_1 python scripts/verify_flan.py`
- **Parallel-ok:** no

### [ ] 28. Add `verify_flan.py` scenarios (B)–(F) — keys, dates, roster, cascade, archive
- **Serves:** FLAN-01.1, FLAN-01.3, FLAN-01.4
- **Files:** `backend/scripts/verify_flan.py`
- **Do:**
  - **(B) numeric-safe keys:** a project whose tasks have been driven up to `PRJ-9`; the next
    `create_task` must produce the `PRJ-10` numeric successor, **not** a lexicographic one. Then
    force a legal 10-digit suffix (`PRJ-9999999999`) and assert the next create still succeeds —
    the `Numeric`-not-`Integer` cast guard (PLUM-01 `7562a02`). Also assert two tasks in the same
    project can never share a key and that two *different* projects may both hold `PRJ-1`.
  - **(C) date validation:** `due < start` raises 422 on create **and** on a PATCH that moves only
    `start_date`; `due == start` succeeds and is readable back as a zero-duration milestone task.
  - **(D) roster removal:** a member assigned to 2 tasks and 1 phase; `remove_member` →
    both tasks still exist with their summaries and dates **unchanged**, the phase still exists, and
    0 assignee rows remain for that member. Then, separately, deactivate the linked platform user
    and assert the roster row and its remaining assignment rows are untouched.
  - **(E) archived project rejects writes:** archive a project, then assert **422** from
    `create_phase`, `create_task`, `update_task`, `create_member`, `set_task_assignees` and
    `update_project` — and that a **read** of the same project still returns all its data.
  - **(F) phase delete cascades:** a phase with 3 tasks; `delete_phase` → `SELECT count(*) FROM
    flan_task WHERE phase_id = :id` is 0, sibling phases' tasks in the same project are untouched.
- **Done when:** the script exits 0 with all of (A)–(F) PASS and is re-runnable.
- **Verify:** `podman exec -e PYTHONPATH=/app compose_api_1 python scripts/verify_flan.py`
- **Parallel-ok:** no

### [ ] 29. Mutation-prove the phase-rollup assertions turn RED
- **Serves:** FLAN-01.2 (NFR-5 non-vacuity discipline)
- **Files:** `backend/app/modules/flan/service/rollup.py` (temporarily), `docs/tasks/feature-flan-core.md`
- **Do:** Execute three documented mutations one at a time, run `verify_flan.py` after each, record
  the exact RED output line in the checklist file, then revert:
  1. `func.min(Task.start_date)` → `func.max(Task.start_date)` — A1's derived start must go RED.
  2. Return `Decimal("0.00")` unconditionally from `_percent` — A2's `33.33` must go RED.
  3. Make the empty-phase branch fall through to a `phase_ids[0]` default instead of the
     no-tasks shape — **A0 must go RED** (this is the mutation that proves the empty-phase case is
     genuinely covered rather than incidentally passing).
- **Done when:** the checklist file holds a 3-row table of `mutation → the exact FAIL line it
  produced`, and `git diff -- backend/app/modules/flan/service/rollup.py` is empty afterwards.
- **Verify:** `cd $BNS && git diff --stat -- backend/app/modules/flan/service/rollup.py && grep -c 'FAIL:' docs/tasks/feature-flan-core.md`
- **Parallel-ok:** no (needs Task 27)

### [ ] 30. Write `verify_flan_api.py` for HTTP RBAC and audit
- **Serves:** FLAN-01.7 (CORE-05, NFR-1)
- **Files:** `backend/scripts/verify_flan_api.py` (new)
- **Do:** Mirror `backend/scripts/verify_gelato_api.py`. Mint three throwaway users backed by
  throwaway roles (`require_permission` reads roles from the **DB**, not the JWT claim): `writer`
  (`flan:read`+`flan:write`), `reader` (`flan:read` only), `noperm` (no roles). Drive **every one of
  the 20 endpoints** over real HTTP with stdlib `urllib` (httpx is not in the image) and assert per
  route: writer → 2xx, reader → 403 on mutations / 200 on reads, noperm → 403, unauthenticated → 401.
  Then assert each of the 14 audit actions exists as an `audit_log` row with the writer's
  `actor_id`, the right `target_type`, and `target_id` as a **string** (the GELATO int-PK lesson
  `136e98d` — all FLAN PKs are uuid strings, so assert the shape rather than assume it). Confirm the
  read endpoints wrote **no** audit rows. Clean up in a `finally`.
- **Done when:** the script exits 0 with every RBAC and audit assertion PASS and is re-runnable
  against the same database.
- **Verify:** `podman exec -e PYTHONPATH=/app compose_api_1 python scripts/verify_flan_api.py`
- **Parallel-ok:** no

### [ ] 31. Port the rollup crux into the pytest suite
- **Serves:** FLAN-01.2 (NFR-5)
- **Files:** `backend/tests/flan/__init__.py` (new), `backend/tests/flan/test_rollup.py` (new)
- **Do:** Follow `backend/tests/gelato/test_shipments.py` — module docstring naming the ported
  scenarios and the SC2 red-on-revert mutation. Port scenarios (A0)–(A4), (B) `PRJ-9 → PRJ-10`,
  (C) `due < start` / `due == start`, (D) roster removal and (F) cascade as ordinary async pytest
  tests against the migrated `biznice_test` database, driving the same real service + schema path.
  Add pure unit tests for `_percent` and `_next_key` that need no DB.
- **Done when:** `pytest tests/flan -q` reports all tests passed with **0 skipped**
  (`test_harness_selfcheck.py` pins the zero-silent-skip invariant).
- **Verify:** `cd $BNS/backend && env $PGTEST POSTGRES_PASSWORD=<from .env.db> JWT_SECRET=<from .env> BNS_ADMIN_PASSWORD=<from .env> .venv/bin/python -m pytest tests/flan/test_rollup.py -q`
- **Parallel-ok:** yes (with Task 32)

### [ ] 32. Port the RBAC and audit assertions into the pytest suite
- **Serves:** FLAN-01.7 (NFR-5)
- **Files:** `backend/tests/flan/test_api.py` (new)
- **Do:** Follow `backend/tests/gelato/test_api.py` — the ASGI-transport client with role-backed
  users, asserting 401/403/2xx on a representative mutation and read for each of the five entity
  groups (project, phase, task, member, assignment), plus one `audit_log` attribution assertion per
  group.
- **Done when:** `pytest tests/flan/test_api.py -q` passes with 0 skipped.
- **Verify:** `cd $BNS/backend && env $PGTEST POSTGRES_PASSWORD=<from .env.db> JWT_SECRET=<from .env> BNS_ADMIN_PASSWORD=<from .env> .venv/bin/python -m pytest tests/flan/test_api.py -q`
- **Parallel-ok:** yes (with Task 31)

### [ ] 33. Run the full regression gate
- **Serves:** all seven criteria (the phase's own definition of not-broken)
- **Files:** none (gate only); any fix lands in the file it belongs to
- **Do:** In order — (1) both lint gates at the zero-violation baseline; (2) the full backend suite
  from the **host venv** (see Context — it cannot run in-container); (3) every non-API `verify_*`
  script and every `verify_*_api.py` script, not just FLAN's, so an adjacent untouched surface
  proves itself on a **cold** process (the LEARNINGS keeper: adding a module to `main.py` and a
  table to shared metadata is exactly how a cross-module FK-resolution 500 hid behind four green
  suites); (4) the frontend gate; (5) confirm the trial balance still nets zero — FLAN posts no GL,
  so any movement is a regression.
- **Done when:** ruff 0, eslint 0, pytest all-passed/0-skipped, every `verify_*` script exit 0,
  Vitest green, `npm run build` exit 0, TB `in_balance` true.
- **Verify:**
  ```bash
  cd $BNS/backend && .venv/bin/ruff check .
  cd $BNS/frontend && npm run lint && npm run test && npm run build
  cd $BNS && podman-compose -f compose/compose.yml -f compose/compose.dev.yml down && podman-compose -f compose/compose.yml -f compose/compose.dev.yml up -d && sleep 30
  for s in $BNS/backend/scripts/verify_*.py; do n=$(basename $s); echo "== $n"; podman exec -e PYTHONPATH=/app compose_api_1 python scripts/$n || echo "FAILED $n"; done
  cd $BNS/backend && env $PGTEST POSTGRES_PASSWORD=<from .env.db> JWT_SECRET=<from .env> BNS_ADMIN_PASSWORD=<from .env> .venv/bin/python -m pytest -q
  ```
- **Parallel-ok:** no

---

## Wave E — close

### [ ] 34. Refresh `.zj/codebase/MAP.md` (D-V5P1-4)
- **Serves:** D-V5P1-4 (phase-close hygiene for phases 2a–7)
- **Files:** `.zj/codebase/MAP.md`
- **Do:** Regenerate/edit so the map covers FLAN, and **fix the four false claims in `## Concerns`**
  that would otherwise mislead the next six phases' architects: (1) Concern 1 calls the Phase-7-fixed
  `SyerpPartner` import a live BLOCKER; (2) Concern 5 claims "No CI: no `.github/`, no pipeline
  config anywhere (verified)" when v4.0 Phase 3 shipped six required jobs with branch protection;
  (3) it cites the deleted `frontend/.eslintrc.cjs` as the lint config (the live one is the flat
  `frontend/eslint.config.js`); (4) its registered-module list omits `gelato` — and now `flan`.
  Every claim must carry a file:line or command citation, per the map's own convention.
- **Done when:** the four claims are corrected with evidence, `flan` appears in the module list and
  directory layout, and no remaining Concern references a file that does not exist.
- **Verify:** `cd $BNS && grep -n "eslintrc\|No CI\|SyerpPartner" .zj/codebase/MAP.md; for f in $(grep -oE '(backend|frontend|compose|\.github)/[A-Za-z0-9_./-]+' .zj/codebase/MAP.md | sort -u); do [ -e "$f" ] || echo "MISSING: $f"; done`
- **Parallel-ok:** yes (with Task 35)

### [ ] 35. Record FLAN-01 in the requirements-progress table
- **Serves:** project rule (`CLAUDE.md` → Feature Alignment step 3)
- **Files:** `docs/features/requirements-progress.md`
- **Do:** Add a `## FLAN Module` section with a FLAN-01 row in the established column shape
  (Requirement | Description | Phase | Plans | Evidence | Status), citing the migration number, the
  commit hashes for each wave, the `verify_flan.py` / `verify_flan_api.py` PASS counts, the pytest
  and Vitest results, and D-V5P1-5/6/7 as built. Update the document's trailing
  "Prior:" status line. Do **not** edit `CHANGELOG.md` (generated from commits).
- **Done when:** the FLAN-01 row exists with real hashes and real counts, and `git status` shows
  `CHANGELOG.md` untouched.
- **Verify:** `cd $BNS && grep -n "FLAN-01" docs/features/requirements-progress.md && git status --porcelain CHANGELOG.md`
- **Parallel-ok:** yes (with Task 34)

---

## Risks

| Risk | Early-warning sign | Response |
|---|---|---|
| **The rollup goes stale in the UI even though the service is right.** A task write changes its phase's derived values, but the phase query is cached separately. This is exactly the class of defect that shipped twice (11a/11b: green backend, dead through the UI). | Task 24's test passes but a manual create leaves the Phases screen showing the old `%`. | Task 20 makes every task mutation invalidate `phasesKey`; Task 23's test asserts the rendered literal, not a recomputed value. If it still drifts, add a phase-rollup assertion to the Tasks screen test. |
| **Autogenerate produces an empty migration 0018.** Pitfall 1 — the aggregator import in `app/core/models.py` is commented out today. | `alembic revision --autogenerate` writes a migration with an empty `upgrade()`. | Task 2 uncomments the line and its Verify prints the `flan_*` table list *before* Task 6 runs. |
| **The key-collision retry swallows a real FK error into a 500 loop.** FLAN's task insert carries a `phase_id` FK and assignee links, so `IntegrityError` is not uniquely a key collision (the Phase-13 `create_invoice` precedent). | A task create against a deleted phase hangs or returns 500 instead of 404/422. | Task 14 narrows the catch to the named constraint and bounds retries at 3; Task 28 (B) exercises the collision path explicitly. |
| **Unpadded keys sort wrong as plain strings** (D-V5P1-7) — `PRJ-10` orders before `PRJ-9`. | A task list ordered by key looks scrambled the moment a project passes 9 tasks; it will read as a UI bug, not a sort bug. | Every list ordering by key sorts on the **numeric suffix**, service-side; Task 24's Done-when asserts a 12-task project renders `PRJ-9` before `PRJ-10`. |
| **A cold-start cross-module FK-resolution 500.** FLAN adds a module to `main.py`'s import list and tables to shared metadata; a `--reload` restart pre-warms models and hides it. | Nothing fails until a fresh container start. | Task 5 and Task 33 both use a full `down`/`up`, never `restart`. |
| **The backend suite cannot be run at all** because compose `db` is not host-published and `pytest` is absent from the image. | Task 31's Verify errors with a connection refusal. | Publish `db:5432` temporarily in a local compose override, or point `POSTGRES_HOST` at a local Postgres — documented in Context, and this is the fourth phase to pay this tax. |

## Out of scope

Everything the CONTEXT names as a non-goal, restated so build cannot drift:

- **FLAN-02** dependency links, topological auto-move, pins-as-scheduling-semantics, snap/sweep,
  projected finish, gate verdict, calculation basis, baselines (phase 2a). The `pinned` **column**
  ships here (FLAN-01.3 names it); the *behaviour* it drives does not.
- **FLAN-04** facet taxonomy and its exclusive-facet rules (phase 2a) — only the storage decided at
  **D-V5P1-5** ships here — a Phase-1 tag is an opaque string.
- **FLAN-03** timeline/board/calendar/search/flags (phase 2b). The Tasks screen is a plain table.
- **FLAN-05** risks/milestones/decisions, **FLAN-06** deliveries/notes, **FLAN-07** budget,
  **FLAN-08** SYERP roll-up and estimate promotion (the v5.0 DoD crux, phase 4b), **FLAN-09**
  analytics, **FLAN-10** exports/comments/undo/deep links, **FLAN-11** the coverage matrix.
- **Labor/time capture and any cost derived from `hourly_rate`** — out of the whole milestone (D-M5-2).
  The column is written and read by nothing.
- **No prototype data migration** (D-V5-4) — `flan/data/Crisis.json` is not a requirements source and
  no importer is built.
- **Splitting `plum/service.py`** (~3,000 lines) — stays BACKLOG p2.
- **Regenerating `.zj/atlas/atlas.html`** — deferred to the v5.0 close.
- **A concurrency crux.** The project-row lock in Task 14 is defensive; no barrier race is verified
  in this phase.
- **A server-side module-enable gate** — the standing p2 gap; FLAN inherits the existing behaviour.

---

## Deviations

Recorded during `/zj:build 1`. Trivial fixes taken in-task; material ones went to the owner.

- **Preflight — the plan's Context block was stale on three command details.** The compose db user
  is **`app`** with database `biznice` (`.env.db`), not `postgres`/`biznice`; health routes are
  **`/health/live` / `/health/ready`**, not `/api/v1/health`; and the stack that was actually
  running was the **prod-only** compose (no source bind mount, no `--reload`), so backend edits
  would have been invisible to the API container. The dev overlay is now up. Full corrected-command
  table lives in `docs/tasks/feature-flan-core.md` → "Build notes".

- **Preflight — "the backend pytest suite CANNOT run in-container" is wrong, and this retires the
  tax the Context says has ridden four phases.** The blocker was never the container; it was the
  **mount point**. Two separate walls: `backend/tests/conftest.py` has no no-DB run mode, so a host
  venv run aborts at collection against the unpublished compose `db`; and under the dev overlay's
  `-v ../backend:/app`, `tests/test_compose_config.py` and `tests/test_containerfile_config.py`
  resolve the repo root by walking up from `__file__`, land on `/`, and give `3 failed, 236 passed,
  6 errors`. Mounting the **repo root** clears both:

  ```bash
  podman run --rm --user root --network compose_default -v "$PWD:/repo:z" -w /repo/backend \
    --env-file .env --env-file .env.db \
    -e POSTGRES_HOST=db -e PYTHONPATH=/repo/backend -e TEST_POSTGRES_DB=biznice_test \
    compose_api sh -c "pip install -q -r requirements-dev.txt >/dev/null 2>&1; python -m pytest -q"
  ```

  Verified at preflight: those 9 layout tests go **9 passed** under it. This is the runner for
  Tasks 31, 32 and 33 wherever the plan says "host venv … pytest". Note the Risks table's last row
  ("The backend suite cannot be run at all") is therefore resolved, not merely worked around.

- **Preflight — `flan/app/schedule_gate-v45.html` was untracked.** D-V5P1-2 and D-V5P1-7 cite it by
  line number (`:3197-3207`, `:3205`), so two binding decisions referenced a file that existed only
  on the owner's disk. Committed as a frozen reference (`49567ff`) on `master` before branching,
  with the owner's agreement.

- **Task 4 — placement within the seed lists.** The plan said "line 32ff / 47ff" without specifying
  position. The pair went after the `gelato:*` pair and before `settings:manage` in `_PERMISSIONS`,
  and last in `_USER_ROLE_PERMS`, matching the file's suite-by-suite ordering with `settings:manage`
  kept as the trailing non-suite entry.

- **Task 2 — the uncommented aggregator import had to move.** `ruff` raised `I001` (un-sorted
  import block) where the commented placeholder sat, so `app/core/models.py` now carries the flan
  import in alphabetical position between `crumb` and `gelato`. Same import, different line;
  required to hold the zero-violation baseline.
- **Task 2 — `flan_task.project_id` carries no `ondelete`.** The plan specified `CASCADE` only for
  `flan_task.phase_id`. Project deletion is not a supported operation (archive is a soft delete), so
  the plain FK is as written, not an omission.
- **Task 2 — `description` columns are bare `String`** (unbounded) on both `flan_project` and
  `flan_phase`, matching the CRUMB exemplar; the plan said "nullable" without naming a length.

- **Task 3 — verified from a throwaway container, not `compose_api_1`.** Task 5's concurrent
  cold-start check took the whole `compose_*` stack down mid-run. The Task-3 check is pure
  SQLAlchemy metadata introspection and needs no database, so it ran the identical Python in a
  throwaway container off the same `compose_api` image with `backend/` mounted at `/app` and both
  env files passed (`app.modules.auth.router` instantiates `Settings()` at import, which has no
  defaults for the three secrets). Real import path, no stub. Deviation is in the runner, not the
  check.

- **Task 5 — two wrong paths in the plan's Verify, corrected.** `/api/v1/health` does not exist
  (health routes are unprefixed `/health/live` and `/health/ready`), and `/api/v1/modules` does not
  exist either — `modules_router` carries `prefix="/core/modules"`, so the real path is
  **`/api/v1/core/modules`**, and it is auth-gated. Logging in to read it uses an OAuth2 **form**
  body (`username=`/`password=`); a JSON POST to `/api/v1/auth/login` 422s. Later tasks reusing
  these commands should take the corrected forms.
- **Task 5 — `backend/app/core/registry.py` exposes no `registered()` accessor**, only `register()`
  and `mount_all()`. Verification read the module-level `_registry` list directly. No accessor was
  added (out of scope for this task).
- **Task 5 — the `flan` import sits between `gelato` and `auth`** in `main.py`, not at the end of
  the block: `auth` is deliberately last there and that ordering was preserved.
- **Task 5 — `/api/v1/flan` OpenAPI route count is legitimately 0.** The router is a stub this task;
  routes land in Tasks 17-18. Mounting was proven by identity (`r.original_router is flan.router`)
  instead, since this FastAPI version wraps includes in `_IncludedRouter` whose `.path`/`.tags` are
  `None`.

- **Task 6 — the migration is hand-authored from the autogenerated draft, not the draft renamed.**
  Two reasons, both material. (a) The draft's `upgrade()` also carried **seven destructive
  `op.drop_constraint` / `drop_index` calls against PLUM and SYERP tables** — pre-existing
  metadata-vs-DB drift, entirely out of scope, and shipping them would have dropped live unique
  constraints on five other suites' tables. They were removed. (b) Every migration from `0015` on is
  hand-authored in a fixed house style (ABOUTME header, per-table commentary, explicitly named
  `fk_<table>_<col>` constraints, FK-safe ordered downgrade), so `0018` matches `0017`. The
  hash-named draft was deleted.
- **Task 6 — FK constraints are explicitly named** though the models do not name them, following
  `0015`-`0017`. Drift-free: Alembic does not compare FK names when the metadata side is unnamed,
  and `alembic check` reports no `flan_*` operations at all.
- **Task 6 — the plan's "autogenerate must run from the host venv" is unusable.** Compose `db` is
  not published to the host, so a host-side alembic has nothing to connect to. The stated reason for
  avoiding the container (a `PermissionError` writing to the bind-mounted versions directory) applies
  only to the non-root long-lived `compose_api_1`; a throwaway container run `--user root` maps
  container-root to the host UID under rootless podman and writes host-owned files. Confirmed: the
  generated file landed `zack:zack`, and `find . ! -user zack` came back empty.

- **Tasks 7/9 — the shared checklist file is a contention point, so the MANAGER now owns it.**
  Task 9's engineer ticked item 9, then Task 7's engineer staged
  `docs/tasks/feature-flan-core.md` wholesale and swept that tick into commit `cde26d9` alongside
  their own. Net repo state stayed correct and nobody's edit was destroyed, but the attribution is
  wrong and a future collision could silently revert a tick. **From Task 8 onward, engineers are
  instructed not to touch the checklist at all**; the manager ticks it after verifying.
- **Task 7 — `ProjectUpdate` carries `tags` too.** The plan names tags only on `ProjectCreate` and
  `ProjectRead`, but FLAN-01.1 says a user can *edit* a project, and AC1 lists tags among its
  fields. `tags: list[str] | None = None` — `None` means "not supplied", a list replaces.
- **Task 7 — `PhaseRead.percent_complete` has a `mode="before"` validator** formatting a `Decimal`
  to `f"{v:.2f}"`. Task 11's rollup returns a `Decimal`; without this every call site would have to
  stringify. A `float` is still refused by the `str` annotation, so D-11 is enforced rather than
  weakened.
- **Task 7 — `PhaseCreate` deliberately has no `project_id`.** Task 17's route is
  `POST /flan/projects/{project_id}/phases`, so the service takes it from the path and never from
  the client. Task 12's `create_phase` therefore takes `project_id` as an argument.
- **Task 9 — `get_project_or_404` does NOT check the archive flag**, by design and documented:
  reads of an archived project must keep working. Only `require_writable_project` guards, and the
  live probe proved all three arms (live → passes, archived → 422, missing → 404).
- **Task 9 — `resolve_phase`/`resolve_task` return a 2-tuple** `(row, project_id)`; the plan said
  "the row and its owning project id" without fixing a shape. `resolve_task` reads the denormalized
  `Task.project_id` directly rather than joining through `flan_phase`.

- **Task 8 — `active` is on `TeamMemberRead` only**, not on `TeamMemberCreate`/`TeamMemberUpdate`,
  though the plan's parenthetical field list names it for all three. Rationale: soft-removal is
  `DELETE /flan/team/{member_id}`, which must *also* delete the member's assignment rows in the same
  transaction (D-V5P1-6). A PATCH able to flip `active=False` on its own would leave those rows
  orphaned — the exact invariant D-V5P1-6 exists to hold. Mirrors Task 7's `ProjectUpdate`, which
  omits `active` because archiving is its own endpoint. **Consequence: there is no reactivation path
  for a removed member.** FLAN-01.4 does not ask for one, so this is in scope as built; if one is
  ever wanted it should be an explicit endpoint, not a PATCH field. Flagged to the owner.
- **Task 8 — added `_normalize_member_ids`** (strip, order-preserving dedupe, reject blank) on
  `TaskCreate.assignee_ids`, `TaskUpdate.assignee_ids` and `AssigneeSet.member_ids`. Not in the task
  text; 12 lines that stop a duplicated id reaching the `(task_id, member_id)` composite PK as a 500
  during Task 16's full-replacement insert.
- **Task 8 — `tags` added to `TaskCreate`/`TaskUpdate`/`TaskRead`**, not in the task's field list but
  required by its binding design points and by `flan_task_tag` existing (D-V5P1-5).
- **Task 8 — `phase_id` IS on `TaskUpdate`**, since Task 14 allows moving a task between phases of
  the same project. Only `key` and `project_id` are absent, per the task text.
- **Manager — extended `schemas.py`'s ABOUTME header** (`9cfbf66`) to name FLAN-01.3/.4/.5. It
  described the module as project+phase schemas only, stale once Task 8 landed, and sat above Task
  8's insertion banner so that engineer correctly left it alone.

- **⚠ Task 27 A0 AMENDED — the plan's own non-vacuity check was itself vacuous.** Task 11's engineer
  found that asserting the empty phase via a **solo** `phase_rollups(db, [empty_phase_id])` is immune
  to Task 29's mutation 3: with a one-element batch, `phase_ids[0]` *is* the empty phase, so the
  mutated fall-through returns the empty shape and the assertion stays GREEN. They hit it on their
  first run. Task 27's A0 text is amended in place to require the empty phase be asserted inside a
  **batch where a non-empty phase comes first**. This is the single most valuable finding of Wave B:
  the phase's headline crux had a verification that would have passed while broken — the exact
  failure mode the SRD called out the empty-phase case to prevent.
- **Task 11 — `PhaseRollup` defined in `rollup.py`** as a frozen `@dataclass(slots=True)`; it was
  undefined anywhere and the plan assigns it to no task. Plus a module constant `NO_TASKS` holding
  the empty-phase shape, so the case is named once and shared safely rather than constructed inline.
  `NO_TASKS` is intentionally not re-exported from the package.
- **Task 11 — `phase_rollups` de-duplicates `phase_ids`** (`dict.fromkeys`) and returns `{}` for
  empty input rather than issuing an `IN ()`. Not in the plan text; no behavioural change for any
  non-degenerate call.
- **Task 11 — all three of Task 29's mutations were pre-run and each turned RED**, with the file
  restored and `git diff --stat` empty afterwards. Task 29 still runs formally to record the FAIL
  lines in the checklist, but the risk is retired: the assertions are known non-vacuous.

- **Task 19 — `useProjects` takes an `includeArchived = false` argument** sending
  `params: { include_archived: … }`, with the flag in the query key. The task text did not spell the
  signature; it was taken from the service contract (`list_projects(db, include_archived=False)`)
  and Task 22's "Show archived" switch. `projectsKey()` itself stays `['flan','projects']` so a
  mutation invalidates every archived-variant at once.
- **Task 19 — `useDeletePhase` takes `{ id, projectId }`.** A deleted phase cannot supply its own
  `project_id` in the response, so the id is passed in to invalidate `phasesKey(projectId)`. Mirrors
  `useDeleteQuoteLine` in `routes/crumb/hooks.ts`. Task 20 inherits this precedent for task deletes.
- **Task 19 — one doc line reworded** from "never parseFloat it" to "never float math, never
  reformat it", because the literal token `parseFloat` inside a comment tripped the task's own
  regression grep for float coercion. The prohibition still stands in the type docstring and ABOUTME.
- **Manager — synced `docs/tasks/feature-flan-core.md` to `PLAN.md`'s ticks.** It had fallen behind
  once engineers stopped touching it; the manager now ticks both together after verifying.

- **Task 10 — `derive_key_prefix` falls back to `PRJ` in one more case than the plan spells out.**
  The plan says fall back "if the name yields nothing"; it also falls back when the derived prefix
  does not **start with a letter** (`"3M Widgets"` → `"3MWI"` → `"PRJ"`). This is load-bearing, not
  cosmetic: the schema pattern is `^[A-Za-z][A-Za-z0-9]{0,9}$`, and **Task 13 interpolates
  `key_prefix` into a `^{prefix}-[0-9]+$` regex on the strength of that pattern**. A derived prefix
  violating it would be the one value in the column the key generator's safety argument does not
  cover. Verified: `Crisis Simulator → CRIS`, `!!! → PRJ`, `3M Widgets → PRJ`.
- **Task 10 — `update_project` skips explicit nulls aimed at NOT NULL columns** (`name`,
  `key_prefix`, `currency`), named `_NOT_NULL_FIELDS`. `exclude_unset` alone (the gelato `update_bin`
  idiom) lets an explicit null legitimately clear a *nullable* field like `category`, but those three
  are typed `X | None` on the update schema, so `{"currency": null}` would otherwise reach the DB as
  an IntegrityError 500.
- **Task 10 — `archive_project` deliberately does NOT call `require_writable_project`.** That guard
  would 422 the second call and break the required idempotency. It uses `get_project_or_404`.
- **Task 10 — tags are attached via a plain non-mapped `.tags` attribute** on the returned ORM
  instance, read by `ProjectRead.tags` through `from_attributes`. `Project` has no ORM relationship
  to `ProjectTag` (the join-table decision D-V5P1-5). The engineer additionally proved
  `ProjectRead.model_validate(...)` carries the tags on all three read paths — create, get and list —
  which is the assertion that actually closes the silent-no-op trap, since a service-side round-trip
  alone would not have caught a serialization gap.
- **Task 10 — list ordering is `ORDER BY name, created_at`** (unspecified in the plan). Alphabetical
  reads better in the project switcher (D-V5P1-3), and since duplicate names are legal, `created_at`
  is the tiebreak that keeps ordering stable between reads.

- **Task 20 — `tasksKey` deliberately omits fixed filter slots**, and this closes the plan's
  top-listed risk more completely than the plan's own wording would have. TanStack invalidation is
  **prefix-based**: with trailing `null` slots, `invalidateQueries(tasksKey(projectId))` would not
  match an assignee-filtered list, so the filtered board would stay stale after a task write — the
  crux dying through the UI by a different route than the one the plan anticipated. The unfiltered
  key is now a strict prefix of every filtered one, so a single invalidation sweeps them all, and it
  still varies by filter as FLAN-01.5 requires.
- **Task 20 — `taskKey(id)` is `['flan','task',id]` (singular)** so a task's detail is not swept by
  the list key's prefix, unlike `projectKey`, where Task 19 deliberately nested detail under the list.
- **Task 20 — `useRemoveMember` also invalidates `tasksKey`** (not required by the task text):
  soft-removal clears the member's assignment rows in the same transaction (D-V5P1-6), so every task
  that named them has a shorter `assignee_ids`. It deliberately does **not** invalidate `phasesKey` —
  `PhaseRead` exposes no assignees, and an assignment change moves no date or percentage.
- **Task 20 — `useDeleteTask` / `useSetTaskAssignees` take `projectId` from mutation variables**,
  not from the response, so invalidation never depends on a DELETE or PUT returning a body.
- **Manager — Wave C screens are released per-screen as their SERVICE layer lands**, not as a block.
  The original hold (all of 22-25 until Tasks 17-18) was too coarse. The rule applied instead: a
  screen is released once the service behind it is built **and verified**, because the payload shape
  a screen must be "exact" against is `schemas.py` + the service contract — the router is thin and
  adds paths, not shapes. So **22 released** (its service is Task 10, done) and **23 released** (Task
  12, done); **24 and 25 stay held** pending Tasks 14 and 15. Each released screen's brief requires
  it to check its POST body against the real `model_fields` of the schema, so a key the schema does
  not have is caught at build rather than as a 422 in production that a mocked test would never see.

- **Task 12 — `list_phases` does NOT 404 on an unknown project id**, returning `[]` instead. This
  matches the house idiom for parent-scoped list functions (`crumb/service/interactions.py::
  list_customer_timeline`, `crumb/service/quotes.py::list_quotes`) and a 404 was not in the task
  text. **Task 17's router may want the 404 at its own layer** — flagged there rather than decided
  here.
- **Task 12 — `delete_phase` uses a Core `delete(Phase).where(...)`** rather than
  `db.delete(orm_obj)`, matching the plan's literal `DELETE FROM flan_phase WHERE id = :id`.
  Behaviourally identical (`Phase` declares no ORM relationships), but it keeps the cascade
  unambiguously the **database's**, which is the property the live check proves.

- **Task 21 — a colocated `FlanNav.test.tsx` was added that the plan does not ask for.** Task 21's
  Verify is only `npm run lint && npx tsc -b`, deferring behaviour to "the screen tests in Tasks
  22-25" — but those tasks build the Projects/Phases/Tasks/Team screens and assert screen behaviour,
  so **nothing would ever have exercised the switcher**, and section-preservation is the one place
  D-V5P1-3 can regress silently. The engineer mutation-checked it: hardcoding the target section to
  `phases` turned the section-preservation test RED, then restored.
- **Task 21 — the test mocks `@/api/client`, not `useProjects`.** Every existing test under
  `frontend/src/routes/` mocks the axios client and lets the real hook run; mocking the hook module
  would have been the only such test in the repo. Navigation is asserted on a real `MemoryRouter`
  with a location probe, so it proves the **URL changed** rather than that a function was called.
- **Task 21 — the tab strip renders only when `projectId` is present** (otherwise its hrefs would be
  `/flan/projects//phases` on the projects-list screen), and the `Select` value is
  `projectId ?? undefined` so Radix shows its placeholder rather than treating `''` as a value.

- **⚠ Task 14's Done-when regex was WRONG and is amended in place.** It read
  `^<PREFIX>-\d{4,}$` — the pre-D-V5P1-7 zero-padded expectation — which directly contradicts the
  decision the same plan records: keys are **unpadded**, so `PRJ-1` has one digit and would have
  failed its own acceptance check. Corrected to `^<PREFIX>-\d+$`. Found by Task 13's engineer.
- **⚠ Task 14's `Do:` amended to require `create_task`/`update_task` to CONSUME `assignee_ids` and
  `tags`.** Task 8 put both on the write schemas, but Task 14's original text described only the
  insert and the key retry, so a literal reading would have built a service that accepts both over
  the wire and silently drops them — the 11a/11b defect exactly. The amendment also requires the
  round-trip be asserted through `TaskRead.model_validate(...)`, the way Task 10 closed the same trap
  for project tags (a service-side assertion alone would miss a serialization gap).
- **Task 13 — the `Integer`-cast defect was DEMONSTRATED, not asserted.** The engineer ran the
  identical query twice over the same rows, differing only in cast target: `Numeric` returned
  `PRJ-9999999999`; `Integer` raised
  `asyncpg.exceptions.NumericValueOutOfRangeError: value "9999999999" is out of range for type
  integer`. So one legal 10-digit key makes **every** subsequent auto-numbered create in that project
  500 permanently — PLUM-01 Phase-7 `7562a02` exactly. They also showed a naive `MAX(key)` string
  aggregate returns `PRJ-9` at the boundary, i.e. would have re-issued an existing key.
- **Task 13 — `generate_task_key(db, project_id, key_prefix)` takes two scalars**, not a `Project`
  instance, keeping `keys.py` free of a model import; Task 14 already holds the locked project row.

- **⚠ OWNER DECISION — Task 22a added: FLAN-01.1's "edit" verb was covered by no task.** The
  criterion reads "Create/view/**edit**/archive a project"; Tasks 22-26 build create, view and
  archive only. Phases, Tasks and Team each got an edit dialog — Project was the sole omission, and
  the backend had supported it since Task 10 with `useUpdateProject` written and called by nothing.
  Found by Task 22's engineer. The owner chose to **close it in-phase** rather than narrow the SRD,
  so Task 22a is inserted into Wave C. Without it, verify could not have honestly marked FLAN-01
  complete.
- **⚠ OWNER DECISION — no reactivation path for a soft-removed roster member, deliberately.**
  FLAN-01.4 does not ask for one; the member row and its history survive, so a later phase can add
  it additively. Task 15's brief records the omission as a decision in the module docstring so it
  does not read as an oversight later.
- **⚠ DEFECT FIXED IN-BUILD (`5b3d09f`) — `useDeletePhase` invalidated only `phasesKey`.**
  `flan_task.phase_id` carries `ondelete="CASCADE"`, so deleting a phase destroys its tasks in the
  database; the Tasks screen would have gone on listing rows that no longer exist. Found by Task 23's
  engineer. This is the same stale-cache class as the plan's top-listed risk but on the **delete**
  path, which the Risks table's row covers only for writes — worth carrying into LEARNINGS as a
  widening of that rule: *a cascade is a write to a table you did not name*.
- **Task 14 — `create_task(db, data, project_id=None)` takes an optional scope argument.** Task 18's
  route is `POST /flan/projects/{project_id}/tasks`; without it the router would have to re-derive
  and compare the phase's project itself, or a task posted to project A with a phase in project B
  would silently land in B. `Task.project_id` still comes from `phase.project_id`, never the client.
- **Task 14 — exhausting the 3 key-generation attempts raises 409**, not a re-raised `IntegrityError`
  (the plan set the bound but not the terminal status). 409 is the house status for a unique-key
  conflict and avoids a 500 on a path that is a conflict, not a bug.
- **Task 14 — `list_tasks` orders by `CAST(substring(key, '[0-9]+$') AS NUMERIC)`,** `NUMERIC` never
  `INTEGER` per D-P8-6, with the regex form returning NULL rather than throwing on a hand-edited
  non-numeric key. This is the D-V5P1-7 sorting consequence discharged.
- **Task 23 — rows are deliberately NOT clickable.** Navigating a phase row to a phase-filtered Tasks
  screen would have guessed Task 24's query-param contract before it existed.

- **⚠ Task 15 — the plan's `user_id` conflict rule would have 500'd, and was widened.** The plan says
  422 when "no other **active** member of the project already links it". But
  `uq_flan_member_project_user` is on `(project_id, user_id)` with **no `active` predicate** — it is
  not a partial index — so a literal implementation lets a re-link past the service check and then
  raises `IntegrityError` at flush: a 500 on a user-input path. `_require_linkable_user` therefore
  422s in **both** cases, with distinct details ("already linked to member X" vs "still linked to
  removed member X; a removed member keeps its user link"). A later phase wanting re-link-after-removal
  needs either a partial unique index or a link-clearing step in `remove_member`.
- **Task 15 — the real auth column is `is_active`, not `deactivated`** (`auth/models.py:64`), and it
  is deliberately **not** checked. Refusing a deactivated user's link would contradict FLAN-01.4
  ("deactivating a user account does not delete the roster row or any of its history"). Proven by
  scenario (f): the roster row, its `user_id` and its assignment rows all survive deactivation.
- **Task 15 — `remove_member` returns `int`** (assignments cleared) for Task 18's audit detail,
  mirroring `delete_phase`'s cascaded-task count. The FE hook types the result `void`, so both are
  satisfied.

- **Task 16 — the membership rule is genuinely ONE implementation.** `assignments.py` imports
  `require_project_members` from `tasks.py`; a grep proved exactly one `def` and one copy of each of
  the two 422 messages across the whole FLAN package. Two divergent copies of "assignees are drawn
  from the project roster" is how that rule quietly stops being enforced on one of the two paths.
  Left in `tasks.py` per its own docstring — this is the second caller, not the third.
- **Task 16 — `set_*_assignees` returns the ids read back from the DB after commit**, ordered by
  `member_id`, matching `tasks.py::_load_assignees` so the response equals a subsequent `GET`. The
  plan named no return type; this is what makes its "setting `[]` … returns an empty list" literal.
- **Task 16 — `tasks.py::_replace_assignees` was deliberately NOT reused.** It is module-private and
  task-only; `assignments.py` has one generic `_replace_assignee_rows(model, target_field, …)`
  serving both join tables. Only the *validation rule* is shared, as instructed — the row write
  carries no business rule.
- **Task 16 — both paths verified independently, not assumed symmetric.** Phases and tasks each got
  their own cross-project-422, clear-to-empty and idempotency checks. A bug in one is invisible from
  the other.

- **Task 17 — `GET /flan/projects/{id}/phases` 404s on an unknown project** (the choice the manager
  flagged rather than decided). The router calls `get_project_or_404` first. Reasoning: `list_phases`
  returns `[]` for both "no phases" and "no such project", and only the HTTP layer can tell them
  apart — a 200 `[]` for a typo'd or deleted id makes a nonexistent project read as an empty one,
  the same ambiguity `GET /flan/projects/{id}` already refuses. The service keeps its house idiom;
  the router owns the 404. Task 18 applies the same to `/tasks` and `/team`.
- **Task 17 — the plan's "eight routes" is a miscount; the surface is NINE operations across five
  paths.** The plan's own route list enumerates nine. All nine shipped; nothing added or dropped.
- **Task 17 — OpenAPI cannot prove RBAC**, and this is worth carrying: `security` records only the
  bearer *scheme*, never *which* permission. The engineer introspected the live app's dependency
  graph to assert `flan:read` on every GET and `flan:write` on every mutation. A verify that only
  greps `security` in the schema would pass on a route gated by the wrong permission.
- **Task 24 — both mutation checks turned RED then green.** A hardcoded key literal broke two
  assertions (the fixtures carry `PRJ-9` and `PRJ-10`, so no single literal satisfies them), and
  adding a client-side `.sort()` on the key string flipped the rendered order — which is the check
  that pins D-V5P1-7's consequence, since the service orders by numeric suffix and a browser sort
  would put `PRJ-10` before `PRJ-9`.
- **Task 24 — no delete action on the Tasks screen.** The task text specifies table + filters +
  create/edit sheet only. `DELETE /flan/tasks/{id}` and `useDeleteTask` both exist; the Phases screen
  *does* have delete, so this is an asymmetry. **Not an acceptance-criteria gap** — FLAN-01.3 lists a
  task's fields and lifecycle, never a delete verb (unlike FLAN-01.1's explicit "archive"). Left as
  built; flagged so it is a known asymmetry rather than an oversight.

## Noticed

Unrelated defects found in passing. **Not fixed mid-task**; reported to the owner at phase end.

- **`backend/app/modules/auth/seed.py`'s module docstring enumerates a stale permission list.** Its
  step-1 enumeration runs only through `plum:*` — it omits `mousse:*`, `crumb:*`, `gelato:*` and
  `settings:manage`. Task 4 appended `flan:read`/`flan:write` as instructed but deliberately did not
  back-fill the other four suites' codes. A one-line doc fix; no behaviour depends on it.

- **No `flan_*` `project_id` FK carries an `ondelete`**, so a future *hard* delete of a project
  would be refused by FK RESTRICT. Consistent with the archive-not-delete posture this phase
  builds, but any later phase wanting a real project delete needs a migration for it.
- **Alembic will emit `ix_flan_project_tag_tag` / `ix_flan_task_tag_tag` as separate
  `CREATE INDEX` statements** — they come from `index=True` on a column that is also part of a
  composite PK. Worth confirming in Task 6's hand-review of `0018` rather than assuming.

- **A module `__init__.py` that imports a not-yet-existing `router` breaks `import app.core.models`
  repo-wide** — Alembic's `env.py` included — for the whole window. It happened here between Task 5
  writing `flan/__init__.py` and Task 5 writing `flan/router.py`, and self-resolved. Worth knowing
  because the failure mode is a spurious `ModuleNotFoundError` in an *unrelated* command: retry
  before debugging.
- **`podman exec … compose_api_1` is a fragile default for DB-free checks** given the stack gets
  cycled several times across a phase (Task 5 and Task 33 both require a full `down`/`up`). For any
  check that needs no database, the throwaway-container form is the more robust idiom.

- **`crisp` is seeded in `modules` with `enabled=true` despite having no code at all.** Harmless
  today because nothing registers it, but it is a nav/gating surprise waiting for whoever builds
  CRISP — or for anyone reading the modules list as ground truth.

- **⚠ Pre-existing autogenerate drift, 7 items, unrelated to FLAN — a live footgun for the next
  engineer.** `alembic check` fails on the dev database because these unique constraints exist in
  Postgres but not in `Base.metadata`: `uq_plum_part_number`, `uq_plum_part_one_released` (a partial
  index), `uq_syerp_gl_account_code`, `uq_syerp_inventory_item_code`, `uq_syerp_partner_code`,
  `uq_syerp_purchase_order_po_number`, `uq_syerp_stock_location_name`. **Every future
  `--autogenerate` in this repo will propose DROPPING all seven**, and Task 6's draft did exactly
  that. An engineer who ships an unreviewed draft drops live constraints on five suites' tables.
  Likely cause: they were hand-named in old migrations while the models declare plain `unique=True`,
  and `Base.metadata` carries no `naming_convention`. Worth a BACKLOG entry — either name them in the
  models or add a `naming_convention`.
- **`backend/tests/conftest.py:290` emits a `SAWarning`** about an unresolvable FK cycle between
  `crumb_lead` and `crumb_opportunity`, which SQLAlchemy says "may raise an error in a future
  release." Benign today; a version-bump tripwire.

- **`status.HTTP_422_UNPROCESSABLE_ENTITY` is deprecated in the pinned Starlette.** `backend/app/`
  has **99** uses of the old name and **0** of the replacement `HTTP_422_UNPROCESSABLE_CONTENT`.
  Task 9 matched the existing 99 for consistency rather than starting a split convention. A
  repo-wide rename wants its own chore commit — and it will become forced, not optional, on the next
  Starlette major.

- **⚠ `TaskCreate.assignee_ids` and `TaskCreate.tags` can silently no-op.** The schemas accept both
  at create time, but Task 14's `create_task` spec describes only the insert and the key retry — it
  never says it consumes them. If the service ignores them the API accepts the fields and quietly
  drops the data, which is precisely the "green backend, dead through the UI" class that shipped
  twice in 11a/11b. **Task 14's brief must require both to be applied and asserted.**
- **No reactivation path exists for a soft-removed roster member** (see the Task 8 deviation above).
  Out of scope for FLAN-01.4 as written, but a real product gap the owner should decide on before
  the roster UI (Task 25) sets an expectation.

- **`func.count().filter(...)` is the codebase's first aggregate `FILTER`** — it renders as real
  Postgres `count(*) FILTER (WHERE ...)`. No compatibility concern on PG 17, noted only because it
  is a new idiom here.

- **`frontend/src/routes/gelato/hooks.ts` and `routes/crumb/hooks.ts` are not Prettier-clean**
  (`npx prettier --check` exits 1 on both). Prettier is a devDependency but nothing runs it, so the
  repo has a formatter it does not enforce. A formatting gate alongside the lint baseline would be a
  standalone chore — flagged, not started.
- **`PhaseRead.status` is a plain `str` in the backend schema** while `PhaseCreate`/`PhaseUpdate`
  use the `PhaseStatus` Literal. The frontend mirrors that asymmetry, as CRUMB does for
  `Lead.status`. Harmless, but any screen wanting an exhaustive status switch needs a narrow first.

- **A shared tag/link helper is emerging.** `Project` has no ORM relationship to `ProjectTag`, so
  Task 10 hand-rolled `_load_tags`/`_attach_tags`/`_replace_tags`. Tasks 14 (`flan_task_tag`) and 16
  (assignee links) need the same trio. If a third copy appears, extract it — flagged now so the
  duplication is a decision rather than an accident.

- **`GET /flan/projects/{project_id}/team` has no `include_removed` query param** in the router
  contract, so `useTeam(projectId)` takes none. D-V5P1-6 excludes soft-removed members from the
  *default* listing, which implies a non-default exists; the service signature
  (`list_members(db, project_id, include_removed=False)`) already supports it. If the roster UI needs
  to show removed members, the param must be added to the endpoint **and** to `teamKey`.

- **`backend/scripts/verify_gelato.py` documents the wrong container and psql role** — it names
  `compose_api_1` and `psql -U postgres`, but the role `postgres` does not exist on this database
  (the compose user is `app`). A pre-existing doc defect in a shipped script, same family as the
  plan's Context errors. Anyone following that script's header verbatim gets an auth failure.

- **`sectionFromPath` in `FlanNav.tsx` reads the 4th path segment.** Task 26 wires three literal
  sibling routes (`/flan/projects/:projectId/phases|tasks|team`) rather than one `:section` route,
  which works either way — but if FLAN is ever nested under an extra path segment, that helper needs
  updating. Worth a glance when Task 26 lands.

- **⚠ `podman run --rm` WITHOUT `-i` makes a `python -` heredoc silently vacuous.** stdin is not
  attached, so `python -` reads an empty program, prints nothing and **exits 0** — a pass that proves
  nothing. Task 13's engineer hit it. Every later task using the `python -` idiom must pass
  `--rm -i`. This is a verification-integrity hazard, not a convenience: it is indistinguishable from
  a green run in a transcript.
- **`Task.key` is `String(20)` and keys are unpadded**, so a 10-char prefix leaves 9 digits; a key
  like `ABCDEFGHIJ-999999999` would increment to 21 chars and hit the column limit. Needs ~10^9 tasks
  in one project, and Postgres would raise on insert rather than truncate, so it is not a live risk —
  but `String(20)` → `String(32)` in a later migration is the cheap airtight fix.

- **Task 14's engineer reported the `app/core/models.py` aggregator line as still commented out —
  that is WRONG.** Verified at `backend/app/core/models.py:22`: `from app.modules.flan import models
  as flan_models  # noqa: F401`, uncommented by Task 2 in `fdf556c`. Recorded because an incorrect
  Noticed entry is itself a hazard — a later engineer acting on it would "fix" a line that is already
  correct.
- **`delete_phase` returns the pre-delete task count, which no UI consumes.** The confirmation copy is
  built *before* the call from `PhaseRead.task_count`, and `useDeletePhase` types the result `void`.
  The returned count is used only by the router's audit detail (Task 17). Not a defect — a redundancy
  worth knowing before someone "simplifies" the return away.

- **⚠ Any script touching `flan_team_member` outside the app must import `app.modules.auth.models`
  first**, or SQLAlchemy raises `NoReferencedTableError` resolving `flan_team_member.user_id →
  users.id`. Task 27/28's `verify_flan.py` text has been amended in place to require it. This is the
  cross-module FK-resolution trap the LEARNINGS keeper warns about, arriving exactly where predicted.

- **⚠ WAVE D HAZARD — on FastAPI 0.138, `app.routes` no longer yields flattened `APIRoute`s.**
  Includes are wrapped in `_IncludedRouter`; you must walk `.original_router`. A verify script or
  test that iterates `app.routes` directly finds **zero** module routes and **passes vacuously**
  rather than failing loudly. Task 17's engineer hit this. Tasks 30 and 32 must not iterate
  `app.routes` naively. This is the same family as the `podman -i` hazard: a check that silently
  measures nothing.
- **Dev-DB residue from Task 17's verification:** an archived probe project
  `c07b0ae6-e2b7-479f-ac7c-4d7f5d81c26f` ("Task17 Audit Probe") and audit rows 110-115 remain in the
  running UAT database. Audit rows are append-only (D-14) so they were deliberately not deleted, and
  the project was left archived so it stays out of default lists. A `--fresh` stack restart clears it;
  Task 33's cold `down`/`up` is the natural moment.
