# Verification: 01 — FLAN core (v5.0 Phase 1)
Date: 2026-08-19 | Commits: `49567ff..dbbcba9` (86 commits, branch `feature-flan-core`)
Requirement: SRD **FLAN-01** (AC1–AC7) · touches NFR-1, NFR-5, CORE-05, CORE-07/08
Verdict: PASS (first pass GAPS — all 14 findings fixed and the whole verification re-run; see the closing section)
Depth: full (the reviewer ran — see `REVIEW.md`; all 14 findings fixed and re-verified)

**Summary.** The phase goal is **true**. Every one of the seven acceptance criteria was driven
empirically — over real HTTP against the live stack, at the SQL level, through the pytest suite and
through Vitest — and every load-bearing assertion was **mutation-proven** to turn RED. Nothing in
the build's self-reported gate turned out to be inflated: I re-proved `268 passed / 0 skipped`,
`verify_flan.py 38 PASS`, `verify_flan_api.py 123 PASS`, `Vitest 51 files / 196 tests`, both lint
gates at 0, and the inherited `verify_qa_doc.py` red as pre-existing on `master`.

The verdict is GAPS, not PASS, for **regression protection and reachability**, not for behaviour:

- **Tags — an element named literally in AC1 *and* AC3 — have no UI surface and no automated test
  anywhere.** No FLAN screen or dialog can set or display a tag, and `grep -n 'tags=' backend/scripts/verify_flan.py`
  and `backend/tests/flan/` return **nothing** — every automated tag assertion compares an empty
  list to an empty list. The API round-trip works (I proved it by hand today); nothing would
  notice if it stopped.
- **Five explicit AC sentences have no automated pin at all** (duplicate names allowed, project id
  immutable, assignees drawn from the project roster, no view mixes two projects' data, deleting a
  platform user leaves the roster row).
- Documentation still says FLAN is unbuilt in two places (`.zj/SRD.md:260`, `CLAUDE.md:94`).

---

## What I ran (all commands, all exit codes checked)

| Command | Result |
|---|---|
| `backend/.venv/bin/ruff check .` | `All checks passed!` — **exit 0** |
| `frontend: npm run lint` | **exit 0** (eslint, `--max-warnings 0`) |
| `frontend: npm run test -- --run` | **51 files / 196 tests passed** — exit 0 |
| `frontend: npx vitest --run src/routes/flan` | **5 files / 39 tests passed** — exit 0 |
| `frontend: npm run build` | **exit 0** (chunk-size advisory only) |
| `pytest -q` (host venv, dedicated Postgres) | **268 passed, 0 skipped**, 213.77 s — **exit 0** |
| `pytest tests/flan -q` | **23 passed** (16 `test_rollup.py` + 7 `test_api.py`), 0 skipped |
| `podman exec … python scripts/verify_flan.py` | **38 PASS / 0 FAIL** — exit 0 (re-run and cold-process run also 0) |
| `podman exec … python scripts/verify_flan_api.py` | **123 PASS / 0 FAIL** — exit 0 |
| all 28 `backend/scripts/verify_*.py` in-container, exit code captured per script | **26 exit 0**; `verify_qa_doc.py` and `verify_qa_citations.py` exit 1 |
| `verify_qa_citations.py` from the **host** | **exit 0** (its in-container red is a `/.zj` path artefact, not a content failure) |
| `alembic downgrade 0017 && alembic upgrade head` | round-trips cleanly, `alembic current` → `0018 (head)` |
| `alembic check` | drift exists but **zero `flan_*` entries** — 0018 matches the models exactly; every drift item is pre-existing PLUM/SYERP constraint noise |
| cold `podman-compose down` + `up -d` | `/health/ready` **200**, `grep -c ' 500 ' api log` → **0**, 5 verify scripts green on the cold process |
| `GET /api/v1/syerp/reports/trial-balance` | `in_balance: true`, `total_debit == total_credit == 8697.250000` (moved from the build's 8547.250000 purely by my own re-runs of the GL-posting verify scripts — FLAN posts no GL) |
| my own independent HTTP drive of all 7 criteria (`44` assertions) | **44 pass / 0 fail** |

**Note on a hazard I hit myself.** `podman exec … psql <<'SQL'` **without `-i`** printed nothing and
**exited 0** — exactly silent-failure hazard #1 from `.zj/STATE.md`. Adding `-i` produced the real
output. Every result above was read from an explicitly captured exit code, never from `|| echo`.

---

## Criteria

### FLAN-01.1 — Project CRUD (create / view / edit / archive, tags, immutable id, duplicate names) — **PASS on the API; FAIL on the `tags` element through the UI**

| Truth | Exists | Wired | Works | Evidence |
|---|---|---|---|---|
| Create with name/category/description/currency/start/gate | ✅ | ✅ | ✅ | `POST /api/v1/flan/projects` → 201, all six fields echoed (`category=client`, `currency=EUR`, `start_date=2026-01-05`, `gate_date=2026-12-01`) |
| **Tags round-trip** | ✅ | ⚠ API only | ✅ (API) | `tags:["red","blue"]` → read back `["blue","red"]`; PATCH `tags:["green"]` replaces the set and survives re-read. **No UI can set or show a tag** — `ProjectCreateDialog.tsx:28`, `ProjectEditDialog.tsx:26-27`, `TaskSheet.tsx:35` each say "`tags` is omitted" |
| View | ✅ | ✅ | ✅ | `GET /flan/projects/{id}` → 200 |
| **Edit** (Task 22a) | ✅ | ✅ | ✅ | `PATCH` → 200, persisted across re-read; UI pinned by `Projects.test.tsx "PATCHes a ProjectUpdate body carrying neither id nor active"` and `"opens the edit dialog pre-filled with the edited row's OWN values"` |
| Archive = soft delete, retains all data | ✅ | ✅ | ✅ | `POST …/archive` → 200 `active:false`; read-back still returns name, prefix, category, tags, phases with rollups, tasks, roster (`verify_flan.py` (E)) |
| Archived project **rejects every write** 4xx | ✅ | ✅ | ✅ | 6/6 writes 422 over HTTP (`create_phase`, `create_task`, `update_project`, `create_member`, `update_phase`, `set_phase_assignees`); `verify_flan.py` (E) asserts the same set in-process |
| Project id immutable | ✅ | ✅ | ✅ | `PATCH {"id":"hacked"}` leaves the id unchanged (Pydantic drops the unknown key) |
| Duplicate names allowed | ✅ | ✅ | ✅ | two projects created with the identical name, both 201, distinct ids |
| `key_prefix` derived and locked after the first task (D-V5P1-2) | ✅ | ✅ | ✅ | name `"Prefix Test …"` → `PREF`; PATCH to `ABCD` accepted while task-free; after the first task (`ABCD-1`) a PATCH returns **422** *"…already has tasks, so its key prefix (ABCD) can no longer be changed."* |

### FLAN-01.2 — Phases; delete cascades; **dates and % derived from tasks, never hand-set** (THE CRUX) — **PASS**

| Truth | Exists | Wired | Works | Evidence |
|---|---|---|---|---|
| No stored rollup columns (structural) | ✅ | ✅ | ✅ | `flan_phase` has no `start_date`/`due_date`/`percent_complete` (`\d flan_phase`); `verify_flan.py` (A4) asserts it against `Phase.__table__.columns` |
| **Empty phase → null dates, `"0.00"`** | ✅ | ✅ | ✅ | over the wire: `GET …/phases` returns `derived_start_date:null, derived_due_date:null, percent_complete:"0.00", task_count:0` |
| Derived start = MIN(task start), due = MAX(task due) | ✅ | ✅ | ✅ | tasks 03-05/03-01/03-09 → derived start `2026-03-01`; dues 03-20/03-11/03-14 → derived due `2026-03-20` |
| % = share in `Done`, Decimal string | ✅ | ✅ | ✅ | 0/3 `"0.00"` → 1/3 `"33.33"` → `In Progress` does **not** count (still `"33.33"`) → 3/3 `"100.00"` |
| Hand-setting is impossible | ✅ | ✅ | ✅ | `PATCH /flan/phases/{id} {"start_date":…,"due_date":…,"percent_complete":"99.00"}` changes nothing — the phase still reports null/`0.00`; `PhaseUpdate.model_fields` carries no such key |
| Status literal `pending\|in-progress\|complete` | ✅ | ✅ | ✅ | all three accepted; `"blocked"` → **422** |
| Ordered by `sort_order` then name | ✅ | ✅ | ✅ | live list came back `(1,Zeta) (1,complete) (1,in-progress) (1,pending) (2,Mid) (3,Alpha)` |
| **Delete cascades to tasks** | ✅ | ✅ | ✅ | HTTP: `DELETE /flan/phases/{id}` 204, the 3 tasks vanish from `GET …/tasks`; SQL (rolled-back txn): `DELETE FROM flan_phase` → `count(*) FROM flan_task` = 0; `verify_flan.py` (F) also asserts the **sibling** phase's tasks are untouched |

**Mutation proof (this is the phase's one crux, so I re-proved sensitivity myself):**

| Mutation to `service/rollup.py` | `verify_flan.py` | `pytest tests/flan/test_rollup.py` |
|---|---|---|
| `func.min(Task.start_date)` → `func.max(...)` | **exit 1**, 3 FAIL incl. `(A1) … derived_start_date=datetime.date(2026, 3, 9)` | — |
| `_percent` returns `Decimal("0.00")` unconditionally | **exit 1**, 6 FAIL incl. `(A2) 1 of 3 Done → "33.33"` | — |
| empty-phase branch falls through to `requested[0]` | **exit 1**, 2 FAIL: `(A0c … CRUX)` and `(A0d … through list_phases)` | **1 failed**: `test_phase_rollup_crux — AssertionError: empty inherited PhaseRollup(derived_start_date=datetime.date(2026, 3, 1) …)` |

The third mutation is the one that matters: the amended A0 (empty phase asserted **inside a batch
whose first member is non-empty**) goes RED, and so does the pytest port. The plan's claim that the
original solo-form check was vacuous is confirmed — only the batched forms fired.
`git diff --stat -- backend/app/modules/flan/service/rollup.py` is empty after each restore.

### FLAN-01.3 — Tasks (numeric-safe key, literals, milestone, `due < start` 4xx) — **PASS**

| Truth | Exists | Wired | Works | Evidence |
|---|---|---|---|---|
| Key auto-numbered, unpadded, **numeric-safe** | ✅ | ✅ | ✅ | 10 creates over HTTP → `PRJ-1 … PRJ-9, PRJ-10` exactly (D-V5P1-7). `verify_flan.py` (B2) shows the naive `MAX(key)` string aggregate would re-issue the live `PRJ-10`; (B4) drives `PRJ-9999999999` (int4 overflow) and the next create still succeeds as `PRJ-10000000000` — the `Numeric`-not-`Integer` cast (D-P8-6 / `7562a02`) |
| Key unique **per project**, not globally | ✅ | ✅ | ✅ | a second project also issues `PRJ-1`; `uq_flan_task_project_key` refuses a second `PRJ-1` in one project (`verify_flan.py` B3) |
| Task belongs to exactly one phase → one project | ✅ | ✅ | ✅ | `POST /flan/projects/{A}/tasks` with a phase from project B → **422** |
| Status / risk literals | ✅ | ✅ | ✅ | `"To Do"/"In Progress"/"Done"` accepted; `"Blocked"` → 422; `risk_level "extreme"` → 422 |
| `pinned`, `tags`, `assignee_ids` round-trip | ✅ | ✅ (API) | ✅ | `POST` with `pinned:true, tags:["t1","t2"], status:"In Progress", risk_level:"high"` → all four echoed on `TaskRead`. **No UI tag editor** (see gap G1) |
| `due == start` is a valid milestone | ✅ | ✅ | ✅ | 201, reads back `start_date == due_date == 2026-06-01` |
| **`due < start` rejected server-side (4xx) — on the wire** | ✅ | ✅ | ✅ | `POST` → 422; one-date `PATCH` that moves only `start_date` past the stored due → 422 **and the stored row is untouched**. Pinned by `tests/flan/test_api.py::test_task_create_refuses_due_before_start_on_the_wire` and `::test_one_date_task_patch_refuses_due_before_start_on_the_wire` |

**Mutation proof:** neutering **both** guards (`schemas.py::_check_date_order` and
`service/tasks.py::_require_date_order`) turns exactly those two wire tests RED —
`2 failed, 5 passed`. The plan's fifth "verification gap" (nothing proved the wire status) is
genuinely closed.

### FLAN-01.4 — Team roster (optional user link, removal clears assignments, rate read by nothing) — **PASS**

| Truth | Exists | Wired | Works | Evidence |
|---|---|---|---|---|
| Member carries name/role/email/colour/hourly_rate | ✅ | ✅ | ✅ | `POST …/team` 201, `hourly_rate:"125.500000"` returned as an exact **string** (D-11) |
| A member with **no** user link is valid | ✅ | ✅ | ✅ | `user_id:null` member created and used as an assignee |
| Optional platform-user link | ✅ | ✅ | ✅ | `flan_team_member.user_id → users.id`, `uq_flan_member_project_user` (`\d flan_team_member`) |
| **Deactivating** a user leaves the roster row | ✅ | ✅ | ✅ | `verify_flan.py` (D2): after the real auth `update_user` sets `is_active=False`, every roster field is byte-identical and the member keeps her task + phase assignment |
| **Deleting** a user leaves the roster row | ✅ | ✅ | ✅ | `ON DELETE SET NULL` proven in a rolled-back transaction: after `DELETE FROM users`, the member row survives with `user_id` NULL, `active=t`, and its `flan_task_assignee` row intact. **Not pinned by any test** — gap G6 |
| Removal clears assignments, leaves tasks intact | ✅ | ✅ | ✅ | HTTP: after `DELETE /flan/team/{id}` both tasks still exist, the removed member's assignments are gone and the **other** member keeps hers on the shared task. `verify_flan.py` (D1 LITERAL) asserts summary, status, dates **and `updated_at`** unchanged — no task row was even loaded |
| Soft-remove (D-V5P1-6), hidden from the roster | ✅ | ✅ | ✅ | the row survives with `active` cleared; `GET …/team` no longer lists it |
| **No cost derived from `hourly_rate`** | ✅ | ✅ | ✅ | `grep -rn hourly_rate backend/app/modules/flan frontend/src/routes/flan` — every hit is a schema field, a docstring, or `Team.tsx:264` rendering the raw string. No arithmetic anywhere. Pinned by `Team.test.tsx "says the rate is stored but unused, and derives no cost from it"` |

### FLAN-01.5 — Assignment (zero or more assignees from the roster; filter by assignee) — **PASS**

| Truth | Exists | Wired | Works | Evidence |
|---|---|---|---|---|
| Task assignees, set on create and by `PUT` | ✅ | ✅ | ✅ | `assignee_ids` echoed on create; `PUT /flan/tasks/{id}/assignees` → 200 |
| Phase assignees | ✅ | ✅ | ✅ | `PUT /flan/phases/{id}/assignees` → 200; `verify_flan.py` (D1) proves the phase link is cleared on removal |
| **Assignees must be on that project's roster** | ✅ | ✅ | ✅ | assigning project B's member to a project A task → **422** *"Member … is not on project …'s roster."* **Not pinned by any test** — gap G4 |
| Board filters by assignee | ✅ | ✅ | ✅ | `GET …/tasks?assignee_id=<m2>` returns exactly the one task m2 is on; pinned by `tests/flan/test_api.py::test_flan_assignment_rbac_and_audit` and `Tasks.test.tsx "re-fetches with assignee_id in the params…"` |
| Board filters by phase | ✅ | ✅ | ✅ | `GET …/tasks?phase_id=…` returns only that phase's tasks |

### FLAN-01.6 — Multi-project (lists every visible project, one active, no view mixes two) — **PASS**

| Truth | Exists | Wired | Works | Evidence |
|---|---|---|---|---|
| Lists every project | ✅ | ✅ | ✅ | `GET /flan/projects` contained all four projects I created; archived ones hidden until `include_archived` |
| One active project, URL-scoped (D-V5P1-3) | ✅ | ✅ | ✅ | routes `/flan/projects/:projectId/{phases,tasks,team}` + `/flan → /flan/projects` redirect (`App.tsx:132-140`); pinned by `FlanNav.test.tsx "shows the project from useParams().projectId, not the first in the list"` and `"switching projects preserves the current section"` |
| **No view mixes two projects' data** | ✅ | ✅ | ✅ | every `GET …/tasks` row carried the requested `project_id`; every `GET …/phases` row likewise; two projects' rosters returned `['A']` and `['B']` respectively. **Not pinned server-side by any test** — gap G3 |

### FLAN-01.7 — Audit + RBAC + nav gating — **PASS**

| Truth | Exists | Wired | Works | Evidence |
|---|---|---|---|---|
| The module is registered and mounted | ✅ | ✅ | ✅ | live OpenAPI lists **exactly 20** `/api/v1/flan` operations — and that set is **identical** to the 20 `verify_flan_api.py` declares, so nothing is ungated by omission |
| `flan:read` / `flan:write` seeded and held by `admin` + `user` | ✅ | ✅ | ✅ | `SELECT p.code, r.name … WHERE p.code LIKE 'flan:%'` → 4 rows |
| Every **write** refuses `flan:read`-only, no-perm, anonymous | ✅ | ✅ | ✅ | `verify_flan_api.py` (B): 14 routes × {403, 403, 401} over real HTTP |
| Every **read** refuses no-perm and anonymous | ✅ | ✅ | ✅ | `verify_flan_api.py` (C): 6 routes × {200, 403, 401} |
| Every mutation emits an attributable audit row (NFR-1) | ✅ | ✅ | ✅ | after my own HTTP drive, `audit_log` holds **14 distinct FLAN actions** (`project.created/updated/archived`, `phase.created/updated/deleted/assignees_set`, `task.created/updated/deleted/assignees_set`, `team_member.created/updated/removed`) all with `actor_id → admin@example.com`; `verify_flan_api.py` (D) additionally asserts uuid-shaped string `target_id`, one row per successful mutation, and **zero** rows for the six GETs and for the refused reader/noperm calls |
| Nav gated on FLAN enabled ∩ `flan:read` | ✅ | ✅ | ✅ | `modules` row `flan / enabled=t / always_on=f`; `PATCH /core/modules/flan {"enabled":false}` flips it and back; `AppShell.tsx::getVisibleModules` intersects `enabled` with `<key>:read` (admin wildcard), pinned by 9 `AppShell.test.tsx` cases |

**Mutation proof of the RBAC assertions.** Changing one route's dependency
(`router.py:187`, `POST /flan/projects`) from `flan:write` to `flan:read` turned RED:
`tests/flan/test_api.py::test_flan_project_rbac_and_audit` **failed**, and `verify_flan_api.py`
exited **1** with `FAIL: (B) flan:read-only token → 403 on POST /flan/projects — status=201` plus a
second failure on the audit-row count (`expected=18 actual=19`). Neither check is vacuous, and
neither relies on the OpenAPI `security` block (silent-failure hazard #3) nor on walking
`app.routes` (hazard #2 — the script says so at `verify_flan_api.py:37-39` and declares the 20
routes as data instead; I cross-checked that data against the live OpenAPI myself).

---

## Regression protection

| Criterion / rule | Pinned by |
|---|---|
| **FLAN-01.1** archive rejects writes, read survives | `backend/scripts/verify_flan.py` (E) — CI `verify-scripts` runs it via the `scripts/verify_*.py` glob under `set -e` (`.github/workflows/ci.yml:272-281`) |
| FLAN-01.1 create/edit through the UI | `frontend/src/routes/flan/Projects.test.tsx::"POSTs the ProjectCreate payload from the create dialog"`, `::"PATCHes a ProjectUpdate body carrying neither id nor active"` |
| FLAN-01.1 archive through the UI | `Projects.test.tsx::"archives a project only after the confirmation is accepted"`, `::"hides archived projects until the Show archived switch is on"` |
| FLAN-01.1 `key_prefix` locks after the first task | `Projects.test.tsx::"surfaces the server's 422 detail when a key prefix can no longer change"` (UI only — no backend test; `verify_flan.py` does not cover it) |
| FLAN-01.1 **duplicate project names allowed** | **MISSING (gap G5)** |
| FLAN-01.1 **project id immutable** | **MISSING (gap G5)** |
| FLAN-01.1 / FLAN-01.3 **tags round-trip** | **MISSING (gap G2)** — no automated check anywhere creates a project or task *with* a tag |
| **FLAN-01.2 rollup crux (incl. empty phase)** | `backend/tests/flan/test_rollup.py::test_phase_rollup_crux` + `verify_flan.py` (A0a–A4) — both mutation-proven RED today |
| FLAN-01.2 `_percent` arithmetic | `test_rollup.py::test_percent_rounds_half_up_to_two_places`, `::test_percent_is_a_quantized_decimal_never_a_float` |
| FLAN-01.2 delete cascades to tasks only | `test_rollup.py::test_phase_delete_cascades_to_its_tasks_only` + `verify_flan.py` (F) |
| FLAN-01.2 UI renders the API's own strings, offers no date/percent input | `Phases.test.tsx::"renders each phase's derived dates and the API's OWN percent string"`, `::"renders an em-dash for both dates and 0.00% on a phase with no tasks"`, `::"offers no date and no percent input in the edit dialog"` |
| FLAN-01.3 numeric-safe keys | `test_rollup.py::test_task_keys_are_numeric_safe`, `::test_next_key_crosses_the_single_digit_boundary`, `::test_next_key_increments_past_the_int4_boundary` + `verify_flan.py` (B1–B5) |
| FLAN-01.3 `due < start` 4xx **on the wire** | `tests/flan/test_api.py::test_task_create_refuses_due_before_start_on_the_wire`, `::test_one_date_task_patch_refuses_due_before_start_on_the_wire` — mutation-proven RED today |
| FLAN-01.3 `due == start` milestone | `test_rollup.py::test_task_date_order_is_enforced_and_milestones_are_valid` + `verify_flan.py` (C3) |
| FLAN-01.3 status / risk literals | *structural* — Pydantic `Literal`; no test asserts the 422 (minor, gap G8) |
| FLAN-01.4 removal clears assignments, tasks byte-identical | `test_rollup.py::test_roster_removal_clears_assignments_and_leaves_tasks_intact` + `verify_flan.py` (D1) |
| FLAN-01.4 **deactivating** a user leaves the roster | `verify_flan.py` (D2) |
| FLAN-01.4 **deleting** a user leaves the roster | **MISSING (gap G6)** — the `ON DELETE SET NULL` behaviour has no test |
| FLAN-01.4 rate stored and unread | `Team.test.tsx::"says the rate is stored but unused, and derives no cost from it"`, `::"renders a member's hourly rate as the string the API returned"` |
| FLAN-01.5 assignee filter | `tests/flan/test_api.py::test_flan_assignment_rbac_and_audit` + `Tasks.test.tsx::"re-fetches with assignee_id in the params when the assignee filter is set"` |
| FLAN-01.5 **assignees must be on the project roster** | **MISSING (gap G4)** |
| FLAN-01.6 URL-scoped active project | `FlanNav.test.tsx::"shows the project from useParams().projectId, not the first in the list"`, `::"switching projects preserves the current section"`, `::"points the sub-nav links at the current project"` |
| FLAN-01.6 **no view mixes two projects' data (server-side)** | **MISSING (gap G3)** |
| FLAN-01.7 RBAC on all 20 routes | `verify_flan_api.py` (A)(B)(C) + `tests/flan/test_api.py` (5 group tests) — mutation-proven RED today |
| FLAN-01.7 audit attribution, uuid `target_id`, no rows for reads | `verify_flan_api.py` (D) + the audit assertion in each of the 5 pytest group tests |
| FLAN-01.7 nav gating mechanism | `frontend/src/components/AppShell.test.tsx` (9 cases over `getVisibleModules`) — generic, not FLAN-specific (acceptable: the mechanism is key-driven) |
| FLAN-01.7 `flan:read`/`flan:write` rows exist | `verify_flan_api.py:252` fails loudly if the seeded permissions are absent |
| Migration 0018 ↔ models agreement | `alembic check` shows no `flan_*` drift; `tests/test_migrations.py::test_alembic_upgrade_head_live` |
| Human-visible surface for FLAN-01 | **manual** — `.zj/phases/01-flan-core/QA.md` (this phase's checklist). `.zj/QA.md` carries **no** FLAN rows and `backend/scripts/seed_uat_fixtures.py` seeds **no** FLAN fixtures (gap G9) |

---

## Documentation truth

| File:line | What it says | Truth |
|---|---|---|
| `.zj/SRD.md:260` | `## FLAN-01: … **Status: planned**` | **Stale.** All 7 ACs are built and verified. Every other implemented requirement in that file carries `**Status: implemented**` |
| `CLAUDE.md:94` | `\| FLAN (Project Mgmt) \| — (legacy flan/app/prj-mgmt-v24.html) \| Prototype only, not yet re-platformed \|` | **Stale.** `backend/app/modules/flan/` and `frontend/src/routes/flan/` both exist and are live. `.zj/codebase/MAP.md:164` already flags this exact line as a Concern |
| `.zj/ROADMAP.md:495` | Phase-1 row still reads `**1** ✅planned` and there is no shipped-phase entry with evidence for v5.0 Phase 1 | **Stale** (normally landed at ship, but it currently lies about the phase's state) |
| `.zj/codebase/MAP.md` | FLAN in the module list, directory layout, migration list, service-package pattern, FE routes, test counts; the four false Concerns fixed | **Accurate.** I spot-checked: 7 registered modules, head `0018`, 8 `flan_*` tables, 20 router operations, `frontend/eslint.config.js` present, `.eslintrc.cjs` absent |
| `docs/features/requirements-progress.md:112` | Full FLAN-01 row with real hashes and counts, status `AC1–AC7 … pending /zj:verify 1`, and both owner-accepted limitations named | **Accurate and honest.** Its numbers (38/38, 123/123, 23 tests, 268/0, 51/196) all re-proved today |
| `.zj/QA.md` §3/§4 | no FLAN-01 human checks | **Stale** relative to a shipped module (gap G9) |
| `docs/tasks/feature-flan-core.md` | 35 ticked items, 14 recorded `FAIL:` mutation lines | Present; not yet archived to `docs/tasks/_completed/` (a ship-time step) |

### The inherited `verify_qa_doc.py` red — **claim CONFIRMED**

`git log master..feature-flan-core -- .zj/QA.md .zj/SRD.md backend/scripts/verify_qa_doc.py` →
**empty**; `git diff --stat` over the same paths → **empty**. Run from the host at `HEAD`
(`dbbcba9`) it exits 1 with 3 failures; run from a worktree at the merge-base `49567ff` — which is
**identical to `master`** (`git rev-parse master` == `49567ff`) — it exits 1 with the **byte-identical**
3 failures:

```
FAIL: every `.zj/SRD.md` requirement has a §3 coverage-map row — … MISSING …: FLAN-02 … FLAN-11, NFR-9
FAIL: §3 headline's total matches `.zj/SRD.md` — §3 prose says 47 requirements; `.zj/SRD.md` has 58
FAIL: §5's buckets plus §3's covered count sum to the `.zj/SRD.md` total — 16 bucketed + 31 covered = 47, but … 58
```

Pre-existing on `master`, untouched by this branch. Per the owner's standing **QA docs:
non-blocking** preference it is not a phase blocker — but `verify-scripts` is a *required*
branch-protection context, so it does block the merge and must be fixed on `master` before ship.
Note also that `verify_qa_citations.py`'s in-container exit 1 is a **false red**: it is a
`FileNotFoundError: '/.zj/SRD.md'` because `.zj/` is not mounted into the API container. From the
host it exits **0**.

---

## Gaps

### G1 — [major] Tags have no UI surface, so an AC1/AC3 element is unreachable by a user
- **Where:** `frontend/src/routes/flan/components/ProjectCreateDialog.tsx:28`,
  `ProjectEditDialog.tsx:26-27`, `TaskSheet.tsx:35` — each explicitly omits `tags`; no FLAN screen
  renders a tag either.
- **Failure scenario:** a user opens FLAN, creates the project the SRD describes, and finds no way
  to tag it. FLAN-01.1 reads "create/view/edit/archive a project (…, **tags**)" and FLAN-01.3 lists
  tags among a task's fields. This is the same class of omission as the Task-22a "edit verb" the
  owner chose to close in-phase.
- **Fix:** either add a minimal tag input to the project dialogs and `TaskSheet` (opaque strings —
  D-V5P1-5 already forbids facet semantics until FLAN-04), or record an owner decision narrowing
  Phase-1 tags to a storage-only API contract and defer the editor to FLAN-04 (phase 2a).

### G2 — [major] No automated check anywhere writes a tag, so both tag tables are unpinned
- **Where:** `grep -n 'tags=' backend/scripts/verify_flan.py` → no match; `grep -rn 'tags' backend/tests/flan/`
  → no match. The only tag assertion (`verify_flan.py:1174`, `tuple(project.tags)` in scenario (E))
  compares an **empty tuple to an empty tuple** and would pass with tags entirely broken.
- **Failure scenario:** a refactor drops the `flan_project_tag` / `flan_task_tag` write path (or the
  `TaskCreate.tags` consumption the plan's Task-14 amendment was added to force). Every gate stays
  green — ruff, eslint, 268 pytest, 38 + 123 verify assertions, 196 Vitest — and the defect surfaces
  in FLAN-04 when the facet engine finds no rows.
- **Fix:** add to `verify_flan.py` (E) a project created with `tags=["alpha","beta"]` and a task
  created with `tags=["x"]`, asserting both come back through `get_project` / `get_task`; mirror it
  as one pytest case in `tests/flan/test_rollup.py`.

### G3 — [major] FLAN-01.6's "no view mixes two projects' data" has no server-side test
- **Where:** `backend/tests/flan/` and `backend/scripts/verify_flan.py` — no assertion builds two
  projects and checks a list endpoint returns only one project's rows. Only the FE switcher is
  pinned (`FlanNav.test.tsx`).
- **Failure scenario:** a `list_tasks` refactor drops the `project_id` filter (e.g. when
  `phase_id`/`assignee_id` filtering is extended in FLAN-03). Both `verify_flan.py` and
  `test_rollup.py` use one project per scenario, so nothing notices — and the first symptom is one
  customer's project showing another's tasks.
- **Fix:** one pytest case: two projects, one phase + one task + one member each; assert
  `list_phases`, `list_tasks` and `list_members` each return exactly their own project's rows.

### G4 — [major] "Assignees drawn from the project roster" is enforced but untested
- **Where:** the 422 comes from `backend/app/modules/flan/service/assignments.py` /
  `tasks.py` (message: *"Member … is not on project …'s roster."*); no test or verify assertion
  exercises it.
- **Failure scenario:** the roster check is dropped in a refactor; a task in project A can be
  assigned to project B's member, and FLAN-01.5's "drawn from the project roster" silently stops
  holding. Every gate stays green.
- **Fix:** one assertion in `verify_flan.py` (D) or `tests/flan/test_rollup.py`.

### G5 — [major] Two explicit FLAN-01.1 rules have no pin: duplicate names allowed, project id immutable
- **Where:** no occurrence of a duplicate-name or id-immutability assertion in
  `backend/scripts/verify_flan.py` or `backend/tests/flan/`.
- **Failure scenario:** someone "helpfully" adds `UniqueConstraint("name")` to `flan_project` (every
  other suite's master table has a unique code), and the whole suite stays green while a rule the
  SRD states explicitly is broken. Symmetrically, adding `id` to `ProjectUpdate` would go unnoticed.
- **Fix:** two short assertions — create the same name twice; PATCH with an `id` key and re-read.

### G6 — [major] "Deleting a user account does not delete the roster row" is untested
- **Where:** `verify_flan.py` (D2) covers **deactivation** only. The delete path rests on
  `fk_flan_team_member_user_id … ON DELETE SET NULL` (`backend/app/modules/flan/models.py:393`,
  migration `0018`), which I proved by hand today in a rolled-back transaction.
- **Failure scenario:** a future migration regenerates the FK without `ondelete="SET NULL"` (the
  Alembic default is `NO ACTION`); deleting a platform user then either fails or, with a different
  default, cascades. FLAN-01.4 says the roster row and its history must survive, and nothing checks.
- **Fix:** extend `verify_flan.py` (D2) to delete the throwaway user and assert the member row
  survives with `user_id is None` and its assignment rows intact.

### G7 — [minor] Two documents still say FLAN is not built
- `.zj/SRD.md:260` — FLAN-01 `**Status: planned**`; `CLAUDE.md:94` — "Prototype only, not yet
  re-platformed"; `.zj/ROADMAP.md:495` has no shipped entry.
- **Failure scenario:** the next planner reads the SRD, sees `planned`, and re-plans FLAN-01 — or a
  future `verify_qa_doc.py` status-cell cross-check (which compares `.zj/QA.md` §3 statuses to the
  SRD's) locks in the wrong status.
- **Fix:** flip FLAN-01 to `implemented` with this file as evidence; update the `CLAUDE.md` Suite
  Status row; add the v5.0 Phase 1 shipped entry to `.zj/ROADMAP.md`.

### G8 — [minor] Status/risk literal rejection is structural only
- Pydantic `Literal` guarantees the 422 (I confirmed `"Blocked"` → 422, `"extreme"` → 422), but no
  test asserts it. If someone widens the type to `str` to "fix" an import, nothing fails.
- **Fix:** one parametrised pytest case posting an illegal `status` and `risk_level`.

### G9 — [minor] `.zj/QA.md` has no FLAN row and `seed_uat_fixtures.py` seeds no FLAN fixtures
- **Where:** `.zj/QA.md` §3 coverage map (no `FLAN-01` row), §4 (no `### FLAN-01` section);
  `grep -ci flan backend/scripts/seed_uat_fixtures.py` → 0.
- **Failure scenario:** the human tester runs the standing checklist after a later phase and never
  touches FLAN, because the master doc does not know it exists. Non-blocking per the owner's QA
  preference, but it means FLAN-01's manual pins live nowhere durable.
- **Fix:** land the §3/§4 additions specified in the closing section of
  `.zj/phases/01-flan-core/QA.md`; optionally extend `seed_uat_fixtures.py` with a FLAN project so
  the checks can quote fixture literals instead of asking the tester to type them.

### G10 — [minor, inherited] `verify_qa_doc.py` is red on `master` and blocks the merge
- Proven pre-existing above; already filed p1 in `.zj/BACKLOG.md:61-63`. Not a Phase-1 defect and
  not a phase blocker (owner: QA docs non-blocking) — but `verify-scripts` is a required status
  context, so the branch cannot merge until `.zj/QA.md` §3/§5 absorbs `FLAN-02..11` and `NFR-9`.

**No blockers.**

---

---

## Fix loop — all 14 findings closed, then the whole verification re-run

Owner approved fixing everything rather than logging any of it. Four engineers on disjoint files
with **separate test databases**, because this build had already lost a run to two pytest suites
sharing `biznice_test`.

| Finding | Closed by | Note |
|---|---|---|
| **R1** [major] `key_prefix` lock does not serialize | `af2f426` | `populate_existing` on `create_task`'s locked select; `update_project` takes the lock **before** `_project_has_tasks` and holds it to commit — conditionally, only on the branch that changes the prefix, so a name/tag PATCH no longer contends with task creation |
| **R2** [minor] `derive_key_prefix` violates its own invariant | `c343d72` | re-validates against `KEY_PREFIX_PATTERN`, falling back to `DEFAULT_KEY_PREFIX`; closes both the `VARCHAR(10)` overflow 500 and the non-conforming charset |
| **G1** [major] tags unreachable in the UI | `b1ded29` | `TagInput` chip editor in both project dialogs and the task sheet + `TagList` columns; opaque strings only (D-V5P1-5) |
| **G2–G6, G8** missing regression pins | `3df78ce`, `9943846` | `verify_flan.py` **38 → 50 PASS** (new scenarios `(G)` identity, `(H)` cross-project scoping); `tests/flan/test_rollup.py` **16 → 29** |
| **R3** [minor] assignee hooks mistyped | `033e2a8` | `AssigneeSet` replaces the `Task`/`Phase` assertions |
| **R4** [minor] `hourly_rate` exposed to every user | `56ec0cf`, `d025897`, `aa7d3a9` | new **`flan:rates`** permission, D-V5P1-8 |
| **G7** [minor] three docs said FLAN was unbuilt | `1e08aca` + this close | `CLAUDE.md`, `.zj/SRD.md`, `.zj/ROADMAP.md` |
| **G9/G10** `.zj/QA.md` had no FLAN coverage, and was red | this close | §4.8 landed **plus** the 11 rows missing since the v5.0 spec |

### Two decisions the fix loop forced

1. **`hourly_rate`: the owner's first choice was unsafe and was reversed on new information.**
   Dropping the field from `TeamMemberRead` alone would have made `MemberDialog` — which seeds its
   input from `member.hourly_rate` and sends it on every save — **silently wipe every stored rate on
   any member edit**, a worse defect than the exposure. Gated on `flan:rates` instead. The key is
   **omitted**, never nulled (null is indistinguishable from "no rate recorded"), and a write
   carrying it from a non-holder is **403**, not a silent drop, keyed off `model_fields_set` so an
   explicit `null` still counts as a write.
2. **The frontend gate was flaky before any FLAN change** — a baseline run with all FLAN work
   stashed already failed four tests at vitest's 5s default under parallel backend runs. Raised to
   15s (`c8f05df`) rather than making the tests shallower. A gate whose result depends on host load
   is not a gate.

### Three traps worth carrying into LEARNINGS

- **The SQLAlchemy identity map is weak.** Engineer A's first lock test **passed against the
  reverted fix**, because the unreferenced `Project` was garbage-collected and the next `db.get`
  silently re-read it from the database. The test now deliberately holds a reference. A mutation
  proof that depends on GC timing proves nothing.
- **A blocking test does not always discriminate.** For "does `update_project` hold the row lock",
  the obvious test — session 2 blocks — stays **green against the mutation**, because without the
  lock the plain `UPDATE` blocks on the held row anyway at commit. A `FOR UPDATE NOWAIT` probe
  (55P03 = held) was needed instead.
- **A uniqueness constraint can make a test pass for the wrong reason.** `roles.name` is unique, so
  a second role named `admin` is impossible and a wildcard assertion against the seeded admin —
  which holds every permission — would have passed without proving the wildcard. The fixture strips
  the explicit grant first.

### Re-verification after the fixes — the full gate, not a partial re-check

| Command | Result |
|---|---|
| `pytest -q` (whole suite, host venv) | **295 passed, 0 skipped** — exit 0 (was 268) |
| `pytest tests/flan --collect-only` | **49 tests** (was 23) |
| `backend/.venv/bin/ruff check .` | `All checks passed!` — exit 0 |
| all 28 `backend/scripts/verify_*.py`, exit code captured per script | **26 exit 0 in-container**; `verify_qa_doc.py` + `verify_qa_citations.py` exit 0 **on the host** — their in-container red is `FileNotFoundError: '/.zj/SRD.md'`, i.e. `.zj/` is not mounted into the API container, not a content failure. **28/28 in their correct environment** |
| `verify_flan.py` | **50 PASS / 0 FAIL** — exit 0 |
| `verify_flan_api.py` | **134 PASS / 0 FAIL** — exit 0 |
| `verify_qa_doc.py` (host) | **16/16 PASS** — 58 requirements, 32 covered, 26 bucketed. **The inherited red is cleared**, unblocking the merge |
| `verify_qa_citations.py` (host) | **PASS** — 270 citations across 69 blocks all resolve |
| `npm run lint` / `test -- --run` / `build` | exit 0 / **51 files, 203 tests** / exit 0 |
| `GET /api/v1/syerp/reports/trial-balance` | `in_balance: true`, debit == credit — FLAN posts no GL, so any movement here would itself have been the regression |

All ten gaps and four review findings are closed. No finding was logged rather than fixed.

---

Verdict: PASS
