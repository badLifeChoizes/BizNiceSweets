# Task: feature-flan-core

ZJ phase **v5.0 Phase 1 — FLAN core** (`.zj/phases/01-flan-core/PLAN.md`), delivering SRD
**FLAN-01**: project/phase/task core, team roster with an optional platform-user link,
assignment, RBAC `flan:read`/`flan:write`, audit.

Task 1 of the plan (open this branch and write this file) is complete by the existence of
this file on branch `feature-flan-core`. The 34 items below are plan tasks 2–35 verbatim,
each with its FLAN-01.N citation. One atomic commit per item; update this file before each.

## Checklist

### Wave A — schema

- [x] 2. Define the Project, Phase and Task ORM models — _FLAN-01.1, FLAN-01.2, FLAN-01.3_
- [x] 3. Define the TeamMember model and the two assignment join tables — _FLAN-01.4, FLAN-01.5_
- [x] 4. Seed the `flan:read` and `flan:write` permissions — _FLAN-01.7 (CORE-05, D-P10-6)_
- [x] 5. Register the flan module with the app registry — _FLAN-01.7 (CORE-07)_
- [x] 6. Generate and apply Alembic migration 0018 for the FLAN tables — _FLAN-01.1, .2, .3, .4, .5_

### Wave B — service + router

- [x] 7. Write the project and phase Pydantic schemas — _FLAN-01.1, FLAN-01.2_
- [x] 8. Write the task, roster and assignment Pydantic schemas — _FLAN-01.3, FLAN-01.4, FLAN-01.5_
- [x] 9. Build the flan service package skeleton with the archived-project guard — _FLAN-01.1_
- [x] 10. Implement project CRUD and archive in the service — _FLAN-01.1, FLAN-01.6_
- [x] 11. Implement the phase-derived dates and % rollup  ⟵ **THE CRUX** — _FLAN-01.2 (D-V5-1)_
- [x] 12. Implement phase CRUD with delete-cascades-to-tasks — _FLAN-01.2_
- [x] 13. Implement the numeric-safe task key generator — _FLAN-01.3 (D-P8-6)_
- [x] 14. Implement task CRUD with server-side date validation — _FLAN-01.3_
- [x] 15. Implement team-roster CRUD with removal clearing assignments — _FLAN-01.4_
- [x] 16. Implement phase and task assignment set/clear — _FLAN-01.5_
- [x] 17. Expose the project and phase endpoints on the FLAN router — _FLAN-01.1, FLAN-01.2, FLAN-01.6, FLAN-01.7 (NFR-1, CORE-05)_
- [x] 18. Expose the task, roster and assignment endpoints on the FLAN router — _FLAN-01.3, FLAN-01.4, FLAN-01.5, FLAN-01.7 (NFR-1, CORE-05)_

### Wave C — UI

- [x] 19. Add the FLAN project and phase query hooks — _FLAN-01.1, FLAN-01.2, FLAN-01.6_
- [x] 20. Add the FLAN task, roster and assignment query hooks — _FLAN-01.3, FLAN-01.4, FLAN-01.5_
- [x] 21. Build the FLAN nav with the project switcher — _FLAN-01.6 (D-V5P1-3)_
- [x] 22. Build the FLAN Projects list screen — _FLAN-01.1, FLAN-01.6_
- [x] 22a. Build the project edit dialog (ADDED AT BUILD, owner decision) — _FLAN-01.1_
- [x] 23. Build the project Phases screen showing the derived dates and % — _FLAN-01.2_
- [x] 24. Build the project Tasks screen — _FLAN-01.3, FLAN-01.5_
- [x] 25. Build the project Team roster screen — _FLAN-01.4_
- [x] 26. Wire the FLAN routes into App.tsx with the `/flan` redirect — _FLAN-01.6, FLAN-01.7 (CORE-07/08)_

### Wave D — verification

- [x] 27. Write `verify_flan.py` scenario (A) — the phase-rollup crux including the empty phase — _FLAN-01.2 (the SRD's named verification)_
- [x] 28. Add `verify_flan.py` scenarios (B)–(F) — keys, dates, roster, cascade, archive — _FLAN-01.1, FLAN-01.3, FLAN-01.4_
- [x] 29. Mutation-prove the phase-rollup assertions turn RED — _FLAN-01.2 (NFR-5 non-vacuity discipline)_
- [x] 30. Write `verify_flan_api.py` for HTTP RBAC and audit — _FLAN-01.7 (CORE-05, NFR-1)_
- [x] 31. Port the rollup crux into the pytest suite — _FLAN-01.2 (NFR-5)_
- [x] 32. Port the RBAC and audit assertions into the pytest suite — _FLAN-01.7 (NFR-5)_
- [x] 33. Run the full regression gate — _all seven criteria (the phase's own definition of not-broken)_

### Wave E — close

- [x] 34. Refresh `.zj/codebase/MAP.md` (D-V5P1-4) — _D-V5P1-4 (phase-close hygiene for phases 2a–7)_
- [x] 35. Record FLAN-01 in the requirements-progress table — _project rule (`CLAUDE.md` → Feature Alignment step 3)_
## Build notes — corrections to the plan's paste-able commands

Found at build preflight (2026-08-18). The plan's Context block has three stale command
details; these are the working forms.

| Plan says | Reality | Correct form |
|---|---|---|
| `psql -U postgres` / `psql -U biznice` | `.env.db` sets `POSTGRES_USER=app`, `POSTGRES_DB=biznice` | `podman exec compose_db_1 psql -U app -d biznice -c "..."` |
| `curl .../api/v1/health` | health routes are unprefixed | `curl -sf http://localhost:8000/health/ready` |
| backend pytest "cannot run in-container; use the host venv against a host-reachable Postgres" | compose `db` is not host-published, and `backend/tests/conftest.py` has **no no-DB run mode** — a host run aborts at collection. But a throwaway container on `compose_default` with the **repo root** mounted runs the whole suite green, layout tests included. | see the runner below |

### The backend pytest runner (use this everywhere the plan says "host venv … pytest")

```bash
cd /home/zack/Projects/BizNiceSweets
podman run --rm --user root --network compose_default -v "$PWD:/repo:z" -w /repo/backend \
  --env-file .env --env-file .env.db \
  -e POSTGRES_HOST=db -e PYTHONPATH=/repo/backend -e TEST_POSTGRES_DB=biznice_test \
  compose_api sh -c "pip install -q -r requirements-dev.txt >/dev/null 2>&1; python -m pytest -q"
```

Mounting the **repo root** (not `backend/`) is the load-bearing part: `tests/test_compose_config.py`
and `tests/test_containerfile_config.py` resolve the repo root by walking up from `__file__`, so
under the plan's `-v ../backend:/app` dev mount they look for `/.env.db.example` and fail 3 + error 6.
With `/repo` they pass. Verified: those 9 tests **9 passed** under this runner.

**Pre-build baseline** (recorded before any FLAN code): the dev-overlay in-container run
(`-v ../backend:/app`) gave `3 failed, 236 passed, 6 errors` — all 9 non-green in those two layout
files, all path artifacts, none a real regression. The `/repo` runner above is the gate for Task 33.

### Stack

The dev overlay must be up — the prod-only stack has no source bind mount, so backend edits are
invisible to the API container:

```bash
podman-compose -f compose/compose.yml -f compose/compose.dev.yml up -d
```

`verify_*` scripts still run in the long-lived api container:
`podman exec -e PYTHONPATH=/app compose_api_1 python scripts/verify_flan.py`

## Mutation proof (Task 29 — NFR-5 non-vacuity)

`verify_flan.py` is worthless if its assertions cannot fail. Three mutations were applied to
`backend/app/modules/flan/service/rollup.py` **one at a time** — each applied, run, recorded, then
reverted and confirmed clean before the next. Every run was
`podman exec -e PYTHONPATH=/app compose_api_1 python scripts/verify_flan.py`, and each run was
preceded, in the same `podman exec`, by an `inspect.getsource` check that the container had actually
loaded the mutant (the dev overlay's `WATCHFILES_FORCE_POLLING` bind mount can lag, and measuring
pre-mutation code would fabricate a green). Baseline before and after: **38 PASS, exit 0**.

| # | Mutation | Result | The exact FAIL line it produced |
|---|---|---|---|
| 1 | `func.min(Task.start_date)` → `func.max(Task.start_date)` | RED — exit 1, 35 PASS / 3 FAIL | `FAIL: (A1/FLAN-01.2) derived start == 2026-03-01 (the EARLIEST task start, inserted 2nd) and derived due == 2026-03-20 (the LATEST task due, inserted 1st) — MIN/MAX, not first/last inserted — PhaseRollup(derived_start_date=datetime.date(2026, 3, 9), derived_due_date=datetime.date(2026, 3, 20), percent_complete=Decimal('0.00'), task_count=3, done_count=0)` |
| 2 | `_percent` returns `Decimal("0.00")` unconditionally | RED — exit 1, 32 PASS / 6 FAIL | `FAIL: (A2/FLAN-01.2) 1 of 3 Done through the REAL update_task → "33.33" (Decimal, ROUND_HALF_UP — never a float) — PhaseRollup(derived_start_date=None, derived_due_date=None, percent_complete=Decimal('0.00'), task_count=3, done_count=1)` |
| 3 | empty-phase branch falls through to a `phase_ids[0]` default (`rollups.get(requested[0], NO_TASKS)`) instead of `NO_TASKS` | RED — exit 1, 36 PASS / 2 FAIL | `FAIL: (A0c/FLAN-01.2 CRUX) phase_rollups([dated, EMPTY, percent, undated]) — the empty phase asserted inside a batch whose FIRST member is a non-empty phase — still reports derived_start_date None, derived_due_date None, percent_complete Decimal("0.00") and 0/0 tasks, and does NOT inherit the leading phase's rollup — empty=PhaseRollup(derived_start_date=datetime.date(2026, 3, 1), derived_due_date=datetime.date(2026, 3, 20), percent_complete=Decimal('25.00'), task_count=4, done_count=1) leading_dated=PhaseRollup(derived_start_date=datetime.date(2026, 3, 1), derived_due_date=datetime.date(2026, 3, 20), percent_complete=Decimal('25.00'), task_count=4, done_count=1)` |

### The line that matters most: A0b stays GREEN under mutation 3

Mutation 3 is the one the A0 amendment exists for. Under it the **solo-batch** form of the
empty-phase assertion **still passes**, because when the batch holds only the empty phase,
`phase_ids[0]` *is* that phase and the mutant returns the empty shape anyway:

```text
PASS: (A0b/FLAN-01.2) solo phase_rollups([empty]) → no dates, 0.00%, 0/0 (the weak form — see A0c for the assertion that carries the proof)
```

Only the **batched** forms see the mutation — `A0c` (batch led by the dated phase) and `A0d`
(through `list_phases`, the read the router serves) both go RED. `A0a` (rollup attached by
`create_phase`) also stays GREEN, for the same reason: it is a solo read.

**Do not "simplify" A0c/A0d down to A0b.** The plan's original solo-only A0 would have certified
this phase green with the crux broken. That is the whole of NFR-5 here, and this table is the
evidence.

### Full FAIL output per mutation

**Mutation 1 — MIN → MAX on the derived start (3 FAIL)**

```text
FAIL: (A1/FLAN-01.2) derived start == 2026-03-01 (the EARLIEST task start, inserted 2nd) and derived due == 2026-03-20 (the LATEST task due, inserted 1st) — MIN/MAX, not first/last inserted — PhaseRollup(derived_start_date=datetime.date(2026, 3, 9), derived_due_date=datetime.date(2026, 3, 20), percent_complete=Decimal('0.00'), task_count=3, done_count=0)
FAIL: (A3/FLAN-01.2) a 4th UNDATED task joins the dated phase: the derived dates are UNCHANGED (2026-03-01 → 2026-03-20) while task_count rises 3 → 4 and the percentage moves 33.33 → 25.00 — MIN/MAX skip NULLs but the undated task is still counted work — before=PhaseRollup(derived_start_date=datetime.date(2026, 3, 9), derived_due_date=datetime.date(2026, 3, 20), percent_complete=Decimal('33.33'), task_count=3, done_count=1) after=PhaseRollup(derived_start_date=datetime.date(2026, 3, 9), derived_due_date=datetime.date(2026, 3, 20), percent_complete=Decimal('25.00'), task_count=4, done_count=1)
FAIL: (A0c/FLAN-01.2) the same batch still answers every OTHER phase with its own real aggregates — the empty branch does not flatten its neighbours — dated=PhaseRollup(derived_start_date=datetime.date(2026, 3, 9), derived_due_date=datetime.date(2026, 3, 20), percent_complete=Decimal('25.00'), task_count=4, done_count=1) percent=PhaseRollup(derived_start_date=None, derived_due_date=None, percent_complete=Decimal('100.00'), task_count=3, done_count=3) undated=PhaseRollup(derived_start_date=None, derived_due_date=None, percent_complete=Decimal('33.33'), task_count=3, done_count=1)
```

**Mutation 2 — _percent returns Decimal("0.00") unconditionally (6 FAIL)**

```text
FAIL: (A2/FLAN-01.2) 1 of 3 Done through the REAL update_task → "33.33" (Decimal, ROUND_HALF_UP — never a float) — PhaseRollup(derived_start_date=None, derived_due_date=None, percent_complete=Decimal('0.00'), task_count=3, done_count=1)
FAIL: (A2/FLAN-01.2) "In Progress" does NOT count as done — still "33.33" with 1 of 3 done — PhaseRollup(derived_start_date=None, derived_due_date=None, percent_complete=Decimal('0.00'), task_count=3, done_count=1)
FAIL: (A2/FLAN-01.2) 3 of 3 Done → "100.00" exactly — PhaseRollup(derived_start_date=None, derived_due_date=None, percent_complete=Decimal('0.00'), task_count=3, done_count=3)
FAIL: (A3/FLAN-01.2) a 4th UNDATED task joins the dated phase: the derived dates are UNCHANGED (2026-03-01 → 2026-03-20) while task_count rises 3 → 4 and the percentage moves 33.33 → 25.00 — MIN/MAX skip NULLs but the undated task is still counted work — before=PhaseRollup(derived_start_date=datetime.date(2026, 3, 1), derived_due_date=datetime.date(2026, 3, 20), percent_complete=Decimal('0.00'), task_count=3, done_count=1) after=PhaseRollup(derived_start_date=datetime.date(2026, 3, 1), derived_due_date=datetime.date(2026, 3, 20), percent_complete=Decimal('0.00'), task_count=4, done_count=1)
FAIL: (A3/FLAN-01.2) a phase whose tasks ALL lack dates reports no dates but a REAL "33.33" over 3 tasks — no-dates is not the same state as no-tasks — PhaseRollup(derived_start_date=None, derived_due_date=None, percent_complete=Decimal('0.00'), task_count=3, done_count=1)
FAIL: (A0c/FLAN-01.2) the same batch still answers every OTHER phase with its own real aggregates — the empty branch does not flatten its neighbours — dated=PhaseRollup(derived_start_date=datetime.date(2026, 3, 1), derived_due_date=datetime.date(2026, 3, 20), percent_complete=Decimal('0.00'), task_count=4, done_count=1) percent=PhaseRollup(derived_start_date=None, derived_due_date=None, percent_complete=Decimal('0.00'), task_count=3, done_count=3) undated=PhaseRollup(derived_start_date=None, derived_due_date=None, percent_complete=Decimal('0.00'), task_count=3, done_count=1)
```

**Mutation 3 — empty-phase branch falls through to phase_ids[0] (2 FAIL)**

```text
FAIL: (A0c/FLAN-01.2 CRUX) phase_rollups([dated, EMPTY, percent, undated]) — the empty phase asserted inside a batch whose FIRST member is a non-empty phase — still reports derived_start_date None, derived_due_date None, percent_complete Decimal("0.00") and 0/0 tasks, and does NOT inherit the leading phase's rollup — empty=PhaseRollup(derived_start_date=datetime.date(2026, 3, 1), derived_due_date=datetime.date(2026, 3, 20), percent_complete=Decimal('25.00'), task_count=4, done_count=1) leading_dated=PhaseRollup(derived_start_date=datetime.date(2026, 3, 1), derived_due_date=datetime.date(2026, 3, 20), percent_complete=Decimal('25.00'), task_count=4, done_count=1)
FAIL: (A0d/FLAN-01.2 CRUX) through list_phases — the batched read GET /flan/projects/{id}/phases actually serves, which returns the dated phase FIRST (sort_order 1) and the empty phase second — the empty phase still shows no dates, "0.00" and 0 tasks — order=['A1 dated 610144ea', 'A0 empty 610144ea', 'A2 percent 610144ea', 'A3 undated 610144ea'] empty=(start=datetime.date(2026, 3, 1) due=datetime.date(2026, 3, 20) pct=Decimal('25.00') count=4)
```

After the third revert, `git diff -- backend/app/modules/flan/service/rollup.py` is empty and the
file is byte-identical to HEAD (sha256 `1c4c70e8e73a865bc4fca7764eb6d1f9a2724fb54d9099722d0d6eada1dc3a6c`,
matching `git show HEAD:...`); the final clean run is **38 PASS, exit 0**.

## Deviations

_(appended as they occur; mirrored to `PLAN.md` `## Deviations`)_

- **Task 1** — the plan's Verify greps `'^- \[ \]'` for 34 items; written as `- [ ] N. title — _serves_`
  grouped under the plan's five wave headings, which matches.

## Noticed

_(unrelated defects found in passing; reported at phase end, not fixed mid-task)_

- **`HTTP_422_UNPROCESSABLE_ENTITY` is deprecated** in favour of `HTTP_422_UNPROCESSABLE_CONTENT`;
  `flan/service/tasks.py` and `assignments.py` emit a `StarletteDeprecationWarning` on every 422
  path. Suite-wide and pre-existing.
- **`tests/conftest.py:290`** — `SAWarning: Cannot correctly sort tables; there are unresolvable
  cycles between tables "crumb_lead, crumb_opportunity"`. The truncate helper's table sort;
  "may raise an error in a future release".
- **Concurrent agents share one git index.** Staging and committing in one command is not enough;
  `git commit --only <paths>` is. One engineer's staged backend files were briefly swept into
  another's frontend commit and had to be split back out.
- **Two pytest runs against one test DB fail in confusing ways** — `DeadlockDetectedError`,
  duplicate-key on `ix_permissions_code`, and bogus 401s at fixture setup, all of which read like
  product bugs. A conftest advisory lock on the test DB would end it (BACKLOG p2 already filed).
- **`getVisibleModules`** (`frontend/src/components/AppShell.tsx:37-46`) carries its own copy of the
  admin-wildcard rule and could now call the new `hasPermission` helper.
- **`flan_task_assignee.member_id` / `flan_phase_assignee.member_id` carry no index** — the
  composite PKs lead with `task_id`/`phase_id`, so the board's assignee filter seq-scans the
  cross-project join table. One line in the next migration.
- **A phase's derived window can read backwards** — `MIN(start_date)` and `MAX(due_date)` are
  computed independently over tasks that may each carry only one of the two dates, so a phase can
  render as starting after it is due. Arguably the honest derivation, but it is the one rollup
  output a user is likely to report as a bug.
- **Archiving a project is a one-way door** — no `active` on `ProjectUpdate`, no un-archive route.
  The roster's equivalent is a recorded owner decision; the project one is not recorded anywhere.

---

## Verify fix loop (`/zj:verify 1`, 2026-08-19)

Verify returned **GAPS** — 0 blockers, 7 major, 7 minor. Owner approved fixing all of it. Four
engineers on disjoint files with separate test databases.

- [x] **R1** — `key_prefix` row lock actually serializes: `populate_existing` on `create_task`'s
      locked select, and `update_project` takes the lock before `_project_has_tasks` (`af2f426`)
- [x] **R2** — `derive_key_prefix` re-validates against its own pattern (`c343d72`)
- [x] **A-tests** — `tests/flan/test_key_prefix_lock.py`, 10 items, mutation-proven (`b845c81`)
- [x] **G2–G6, G8** — tags, cross-project scoping, roster-scoped assignees, duplicate names +
      immutable id, user-delete, literal rejection: `verify_flan.py` 38 → **50 PASS**,
      `test_rollup.py` 16 → **29** (`3df78ce`, `9943846`)
- [x] **G1** — tag editor + tag columns; opaque strings only, D-V5P1-5 (`b1ded29`)
- [x] **R3** — assignee hooks typed `AssigneeSet` (`033e2a8`)
- [x] **R4** — `hourly_rate` gated on the new `flan:rates` permission, D-V5P1-8
      (`56ec0cf`, `d025897`, `aa7d3a9`)
- [x] **Flaky gate** — vitest `testTimeout: 15000`; the form-filling suites were failing at 5s
      under load **before any FLAN change** (`c8f05df`)
- [x] **G7** — `CLAUDE.md` Suite Status corrected for FLAN **and** GELATO (`1e08aca`)
- [x] **G9/G10** — `.zj/QA.md` §4.8 landed with the eight `C-FLAN-*` checks, **plus** the eleven
      rows missing since the v5.0 spec; `verify_qa_doc.py` green, merge unblocked
- [x] **Full re-verification** — 295 pytest / 0 skipped, 28/28 `verify_*`, 51 files / 203 Vitest,
      ruff 0, eslint 0, build 0, trial balance in balance

---

## Retro (`/zj:retro 1`, 2026-08-19)

- [x] Learnings banked → `.zj/LEARNINGS.md` "Phase 01 — FLAN core"
- [x] Roadmap trued up — Phase 1 `[done — verified + retro'd]`; **no phase resized**
- [x] Deferred items homed — 4 new p2, 3 grouped p3 (15 residue items), p1 QA.md item **RESOLVED**,
      p3 "suite cannot run in-container" trued up with the working repo-root-mount recipe
- [x] Owner calls: project **un-archive** → BACKLOG p2, homed at Phase 2b; frontend
      **code-splitting** → BACKLOG p2, not a chore phase
- [x] `.zj/STATE.md` → next action `/zj:ship`
