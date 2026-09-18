# Review: 49567ff..dbbcba9 (v5.0 Phase 1 — FLAN core, FLAN-01.1–.6)
Date: 2026-08-19

Scope reviewed: migration 0018 and the eight `flan_*` models, the whole
`flan/service/` package (rollup, keys, projects, phases, tasks, roster,
assignments, `_common`), all 20 router operations with their RBAC and audit
wiring, the `flan:read`/`flan:write` seeding, and the four FE screens plus
every mutation hook in `routes/flan/hooks.ts`.

The four hardest things in this phase are right. **The rollup** is a single
grouped query (`MIN`/`MAX`/`COUNT(*)`/`COUNT(*) FILTER (WHERE status='Done')`)
batched from both `list_phases` and `create/update_phase`, so there is no N+1;
the empty-phase case is an explicit named branch returning `NO_TASKS`, which is
also why `_percent` can never see `total == 0`; the percentage is a `Decimal`
quantized `ROUND_HALF_UP` to `0.01` and reaches the wire as a two-place string
(D-11 holds end to end — the FE types it `string` and renders it verbatim,
never `parseFloat`s it). **The key generator** casts to `Numeric`, filters with
`~ '^{prefix}-[0-9]+$'` *before* the cast, and the regex is a bound parameter,
so `PRJ-9999999999` neither overflows nor 500s (D-P8-6 / `7562a02` avoided);
the retry is genuinely narrow (`_is_task_key_collision` requires the constraint
name, checking `orig.__cause__.constraint_name` first) and bounded at 3 with a
409, not the Phase-13 `create_invoice` recursion. **The archive guard** is
called by all fourteen mutating service functions — phase, task, roster *and*
assignment writes included — at 422, matching `gelato/putaway.py:175`; the one
omission (`archive_project`) is deliberate and correct for idempotency.
**RBAC/audit** is complete: 20 routes, 20 `require_permission` dependencies,
correct verb-to-permission mapping on every one, and every mutation writes an
attributable audit row after the service commit. The `5b3d09f` cascade lesson
was applied properly and generalized — every task write also invalidates
`phasesKey` (the rollup is a derived read of a table the mutation did not
name), `useRemoveMember` invalidates `tasksKey`, and `tasksKey(projectId)` is a
strict prefix of every filtered key. Migration 0018 matches the models
column-for-column (`flan_task.phase_id` CASCADE, `flan_team_member.user_id`
SET NULL, `uq_flan_task_project_key` named exactly as the retry greps for), and
the downgrade drops children before parents. `ruff check .` exits 0.

## Findings

### 1. [major] The project-row lock does not actually serialize `key_prefix` against task creation — D-V5P1-2's "prefix frozen once a task exists" invariant breaks under concurrency, and the resulting mismatch is unrepairable through the API
- **Where:** `backend/app/modules/flan/service/tasks.py:486-489` (the lock) and
  `backend/app/modules/flan/service/projects.py:286-300` (no lock at all)
- **Failure:** Two independent mechanisms, both producing the same corrupt end state.

  *(a) The locked read is stale.* `create_task` calls
  `require_writable_project` → `_common.get_project_or_404` → `db.get(Project, id)`,
  which puts the Project in the identity map. It then issues
  `select(Project).where(...).with_for_update()` and reads `key_prefix` off
  `locked.scalar_one()`. SQLAlchemy returns the **already-mapped instance
  without repopulating its attributes** (no `populate_existing`), so the value
  read is the pre-lock snapshot, not what the lock just serialized against.
  Verified empirically: after `db.get` loads `key_prefix='PRJ'`, a committed
  concurrent `UPDATE ... SET key_prefix='CRIS'`, and a re-`select` of the full
  entity, the attribute still reads `'PRJ'`; only `db.refresh` yields `'CRIS'`.
  This is precisely the identity-map staleness `post_receipt` was given
  `await db.refresh(item)` for at `syerp/service/inventory.py:279-286`.

  *(b) The other writer never takes the lock.* `update_project` reaches
  `_project_has_tasks` through a plain `db.get` — it never acquires the row
  lock, so `create_task`'s `FOR UPDATE` has nothing to block.

  Concrete interleaving (project `P`, prefix `PRJ`, zero tasks): T1 `PATCH
  /flan/projects/P {"key_prefix":"CRIS"}` reads `_project_has_tasks` → False.
  T2 `POST /flan/projects/P/tasks` loads P (prefix `PRJ`), takes the lock, reads
  the stale `PRJ`, inserts `PRJ-1`, commits. T1 sets `key_prefix='CRIS'` and
  commits. End state: project P advertises prefix `CRIS` but holds task `PRJ-1`;
  the next create issues `CRIS-1`. Because P now has a task, `update_project`
  422s on every subsequent `key_prefix` change forever — the state cannot be
  repaired through any endpoint, only by hand-editing `flan_project`. That
  mismatched-prefix state is exactly what D-V5P1-2 and the lock exist to prevent.
- **Fix:** In `create_task`, add
  `.execution_options(populate_existing=True)` to the `with_for_update()` select
  (or `await db.refresh(project)` immediately after it, the `post_receipt`
  precedent). In `update_project`, take
  `select(Project).where(Project.id == project_id).with_for_update()` before the
  `_project_has_tasks` check and hold it to the commit, so the prefix edit and
  the first task create contend on the same row.

### 2. [minor] `derive_key_prefix` can emit a prefix that violates the shape its own regex-safety argument rests on, and can overflow `String(10)` into an unhandled 500
- **Where:** `backend/app/modules/flan/service/projects.py:104-106`, consumed at
  `:245` and interpolated at `keys.py` (`rf"^{key_prefix}-[0-9]+$"`)
- **Failure:** `str.isalnum()` and `str.upper()` are Unicode-aware, and the
  `[:4]` slice happens *before* `.upper()`. `POST /flan/projects
  {"name":"ﬃﬃﬃﬃ"}` (U+FB03 LATIN SMALL LIGATURE FFI — `isalnum()` true) derives
  `"FFIFFIFFIFFI"`, 12 characters, into `flan_project.key_prefix
  VARCHAR(10)` → Postgres `22001 string_data_right_truncation` → unhandled 500
  on the create, with no validator in the path (client-supplied prefixes are
  pattern-checked; derived ones are not). Less exotically,
  `{"name":"Café Simulator"}` derives `"CAFÉ"`, which does **not** match
  `KEY_PREFIX_PATTERN` — the invariant `keys.py`'s module docstring explicitly
  claims ("a derived prefix must honour the same shape a client-supplied one
  does") and on which its "no regex metacharacter survives that shape"
  argument is built. The argument survives by luck rather than by the stated
  reason: no `isalnum()` character is a regex metacharacter, so there is no
  injection and the `~` filter still matches — but the guarantee as written is
  false, and the next person to widen the derivation has no real guard.
- **Fix:** Re-validate the derived value against `KEY_PREFIX_PATTERN` and fall
  back to `DEFAULT_KEY_PREFIX` when it fails — one `re.fullmatch` at the end of
  `derive_key_prefix`, which closes both the length overflow and the
  non-conforming-charset case in the same line.

### 3. [minor] Both assignee mutation hooks declare a response type the endpoint does not return, and TypeScript cannot catch it
- **Where:** `frontend/src/routes/flan/hooks.ts:588-602` (`useSetTaskAssignees`,
  typed `Task`) and `:609-623` (`useSetPhaseAssignees`, typed `Phase`); the
  routes are `response_model=AssigneeSet` (`router.py:679`, `:714`)
- **Failure:** `PUT /flan/tasks/{id}/assignees` answers `{"member_ids":[...]}`,
  not a Task. The `apiClient.put<Task>` generic is an unchecked assertion, so
  the first consumer that writes
  `onSuccess: (task) => toast.success(\`Task ${task.key} saved\`)` compiles
  clean, passes `tsc -b`, and renders "Task undefined saved" at runtime — and
  anything reading `task.project_id` for an invalidation key would silently
  invalidate `['flan','tasks',undefined]`, leaving the board stale. Latent
  today only because no screen calls either hook (the Task sheet sets assignees
  through `PATCH /flan/tasks/{id}`), which is what makes it a trap rather than a
  live bug.
- **Fix:** Type both `useMutation<AssigneeSetPayload, ...>` and
  `apiClient.put<AssigneeSetPayload>`, matching the router's `AssigneeSet`.

### 4. [minor] Every authenticated user can read (and write) every roster member's pay rate
- **Where:** `backend/app/modules/flan/schemas.py:526` (`TeamMemberRead.hourly_rate`),
  served by `GET /flan/projects/{id}/team` gated on `flan:read`
  (`router.py:544-548`); `backend/app/modules/auth/seed.py` grants both
  `flan:read` and `flan:write` to the `user` role; rendered at
  `frontend/src/routes/flan/Team.tsx:264`
- **Failure:** A rostered contractor holding only the default `user` role opens
  `/flan/projects/{id}/team` (or curls it) and reads every teammate's
  `hourly_rate` in a column on screen — and, with the same `flan:write` the role
  carries by default, can PATCH them. No other suite in the platform puts a
  compensation figure behind a suite-wide read permission. The field is
  documented as "stored and read by nothing in v5.0" (D-V5-2 / D-M5-2), which is
  true of the *service* layer but not of the wire: it is on the read schema and
  on the screen.
- **Fix:** Either drop `hourly_rate` from `TeamMemberRead` and the Team table
  until something consumes it, or gate it on a distinct permission
  (`flan:rates`) not granted to `user` — and record the choice as a decision,
  since a later costing rollup will have to answer the same question.

## Questions
- **Archiving a project is a one-way door.** `ProjectUpdate` carries no `active`,
  `archive_project` only ever sets `False`, and there is no un-archive route —
  so an accidental archive (a single button in `Projects.tsx` behind one
  confirm) permanently freezes every write in that project with no API path back.
  The roster's equivalent one-way door is an explicit owner decision recorded in
  PLAN.md:1232; the project one is not recorded anywhere I could find, and
  FLAN-01.1 reads "Create/view/edit/archive" without saying which way. Worth a
  decision entry either way before a real project gets archived by mistake.
- **`flan_task_assignee.member_id` / `flan_phase_assignee.member_id` carry no
  index** (the composite PKs lead with `task_id`/`phase_id`). Both
  `remove_member`'s two scoped `DELETE`s and `list_tasks`' assignee filter
  (`IN (SELECT task_id FROM flan_task_assignee WHERE member_id = :id)`) therefore
  seq-scan the whole cross-project join table. Fine at one shop's scale, and I
  could not construct a wrong *outcome* — flagging only because the board's
  filter-by-assignee is a hot read and the index is one line in the next migration.
- **A phase's derived window can read backwards.** `MIN(start_date)` and
  `MAX(due_date)` are computed independently over tasks that may each carry only
  one of the two dates, so a phase holding task A (start 2026-03-01, no due) and
  task B (no start, due 2026-01-01) renders on the Phases screen as starting
  after it is due. That is arguably the honest derivation and the module
  docstring does address NULL-skipping — but it does not address this pairing,
  and it is the one rollup output a user is likely to report as a bug.
