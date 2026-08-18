# STATE — BizNiceSweets
Updated: 2026-08-18 (**v5.0 Phase 1 "FLAN core" BUILD IN FLIGHT — `/zj:build 1`.**
Branch `feature-flan-core`; checklist `docs/tasks/feature-flan-core.md`. Task 1 done (`74e4b30`).
Wave A under way. **Next: resume `/zj:build 1` at the first unticked task in `PLAN.md`.**)

## Position: v5.0 Phase 1 — build in flight on `feature-flan-core`

**Current task:** Wave A complete (1-6). **Wave B at 5/12** — tasks **7, 8, 9, 11** done and
verified. In flight: **10** (project CRUD + archive, `service/projects.py` + `service/__init__.py`)
and **19** (frontend project/phase query hooks, `frontend/src/routes/flan/hooks.ts`).

**Next:** 12 → 13 → 14 → 15 → 16 → 17 → 18, then Wave C. Tasks 10, 12, 13, 14, 15, 16 **all touch
`service/__init__.py`**, so they cannot run concurrently with one another — pair each with a
frontend task (19, 20, 22-25) instead. Tasks 19 and 20 share `hooks.ts`, so those two also
serialize against each other.

**⚠ THE CRUX IS BUILT AND ITS VERIFICATION WAS FIXED.** Task 11 (`service/rollup.py`, `ffdbc01`) is
done: one grouped query proven by a cursor tap counting statements (1, not N+1), `MIN`/`MAX` not
first/last inserted, NULL dates skipped, and `flan_phase` stores none of the three derived columns.
All three of Task 29's mutations were pre-run and each turned RED, file restored.

**But Task 27's scenario A0 was amended in place, and this is the single most important carry-forward
of the phase.** As the plan originally wrote it, A0 asserts the empty phase via a **solo**
`phase_rollups(db, [empty_phase_id])` — which is **immune to Task 29's mutation 3**: with a
one-element batch, `phase_ids[0]` *is* the empty phase, so the mutated fall-through returns the empty
shape and the assertion stays GREEN while the code is broken. Task 11's engineer hit it on their
first run. A0 now **requires the empty phase be asserted inside a batch where a non-empty phase comes
first**. The amendment is written into Task 27's own text in `PLAN.md`, not only into Deviations.

**Engineers no longer touch `docs/tasks/feature-flan-core.md` — the manager owns it** (two parallel
engineers collided on it; one swept the other's tick into commit `cde26d9`).

**⚠ Open trap for Task 14.** `TaskCreate` accepts `assignee_ids` and `tags`, but the plan's Task 14
spec never says `create_task` consumes them. If it does not, the API accepts both and silently drops
the data — the "green backend, dead through the UI" class that shipped in 11a and 11b. Task 14's
brief must require both applied and asserted. Same trap handled for Task 10's project tags.

**Owner decision pending (not blocking):** there is **no reactivation path for a soft-removed roster
member**. Task 8 correctly omitted `active` from the roster write schemas — a PATCH flipping
`active=False` alone would orphan the assignment rows D-V5P1-6 requires be deleted in the same
transaction. FLAN-01.4 does not ask for reactivation, so it is out of scope as built, but the roster
UI (Task 25) will set an expectation either way.

Ticked tasks are marked `### [x]` in `.zj/phases/01-flan-core/PLAN.md`; **resume at the first
`### [ ]`** — revert and re-run any in-flight task rather than trusting a partial edit. An untracked
`frontend/src/routes/flan/` is Task 19 mid-write; an uncommitted `service/projects.py` is Task 10.

**Wave A verified live by the manager, not taken on report:** `alembic_version` = `0018`; all eight
`flan_*` tables; all five load-bearing constraint shapes in the database (`flan_task.phase_id`,
`flan_task_assignee.task_id`, `flan_phase_assignee.phase_id` → `CASCADE`;
`flan_team_member.user_id` → `SET NULL`; **both** `member_id` FKs → `NO ACTION`, which D-V5P1-6's
soft-remove depends on); both named unique constraints; `registry` lists `flan` among seven modules;
cold `down`/`up` boot clean; `ruff` 0.

**⚠ Standing warning for every later autogenerate.** Task 6's draft proposed **seven destructive
drops** against PLUM and SYERP unique constraints — pre-existing metadata-vs-DB drift, not FLAN's
doing. Removed from `0018`, but the drift remains and every future `--autogenerate` proposes them
again. Worth a BACKLOG entry.

**Corrected commands** (the plan's Context block is wrong on all four; table in
`docs/tasks/feature-flan-core.md` → "Build notes"):
- `psql -U app -d biznice` — not `-U postgres` / `-U biznice`
- `/health/ready` — not `/api/v1/health`
- `/api/v1/core/modules`, auth-gated via OAuth2 **form** login — not `/api/v1/modules`
- alembic and pytest run from a **throwaway container, repo root at `/repo`, `--user root`, on
  `--network compose_default`**; for DB-free import checks mount `backend/` at `/app` instead.
  **Mounting the scratchpad into a container hits `Permission denied`** — pipe probe scripts in on
  stdin via `python -`.

Commits: `74e4b30` (T1), `fdf556c` (T2), `ae13509` (T3), `dadbf58` (T4), `9dfd406` (T5),
`67e191d` (T6), `cde26d9` (T7), `c97bac8` (T8), `f0be8f1` (T9), `ffdbc01` (T11), plus the
`docs(zj):` bookkeeping commits and `9cfbf66` (ABOUTME fix).

## Position (as planned): v5.0 Phase 1 planned — build not started

**Phase 1 = SRD FLAN-01** (project/phase/task core, team roster with an optional platform-user link,
assignment, RBAC `flan:read`/`flan:write`, audit) — the first phase of the 7-phase v5.0 FLAN port
mapped at D-V5-8. It stacks on nothing unverified: v4.0 closed and tagged, every phase archived
with a PASS verdict.

**Plan shape (`/zj:plan 1`, architect + manager goal-backward check):** one full-stack phase in wave
order (D-V5P1-1) — **A** schema (5 tasks: models, roster + assignment join tables, permission seed,
module registration, migration `0018`) → **B** service + router (12) → **C** UI (8) → **D**
verification (7) → **E** close (2). 35 tasks, one atomic commit each.

**The one crux: phase-derived dates and % complete (FLAN-01.2, D-V5-1).** A phase carries **no**
`start_date`, `due_date` or `percent_complete` column at all — the three values are computed on
every read from the phase's tasks in one grouped query. Storing them would make "never hand-set" a
rule someone must remember; omitting the columns makes it structural. The **empty-phase case** (no
tasks → null dates, `"0.00"`) is fixtured **first** in `verify_flan.py` scenario (A) and is one of
the three mutations Task 29 must drive RED — it is precisely the case a happy-path fixture would
miss.

**7 owner decisions at plan → D-V5P1-1..7** (ID namespace note: `D-P1-*` was already spent by v4.0's
Phase 1, so v5.0 phase decisions are `D-V5P1-*`):
1. **One full-stack phase, not sub-split** — FLAN-01 has one provable crux, and the standing rule is
   to sub-split at two.
2. **Task key prefix = per-project `key_prefix` column**, defaulted from the project name, **locked
   once the first task is issued**. v45's majority-inference is not ported.
3. **Active project is URL-scoped** — `/flan/projects/:projectId/...` + a switcher that merely
   navigates. Makes FLAN-01.6's "no view mixes two projects" structural, and is the shape FLAN-10's
   deep links need.
4. **Refresh `.zj/codebase/MAP.md` at phase close.** `plum/service.py` split and the atlas stay out.
5. **Tags = two join tables** (`flan_project_tag`, `flan_task_tag`) holding **opaque strings** — no
   facet semantics in Phase 1, that is FLAN-04 at 2a.
6. **Roster removal is a soft-remove** (`active=False` + delete that member's assignment rows).
7. **Task keys are unpadded** — `PRJ-9 → PRJ-10`, per the SRD's own verification literal.

**Two errors caught at the manager's plan review, both now corrected in `PLAN.md`:**
- **FLAN seeds `enabled=True`, not disabled.** The `False` in `("flan", …, False, 30)`
  (`backend/app/core/modules_seed.py:26`) is `always_on`; the insert at `:52` hardcodes
  `enabled=True`. The draft plan asserted the opposite, which would have made the CORE-07/08
  nav-gating check **pass vacuously** ("enable it, then see the nav"). It is now asserted the other
  way — toggle FLAN **off**, assert the nav item disappears, toggle back on.
- **The key format contradicted its own verify scenario** — padded `PRJ-0001` while scenario (B)
  drove a project to `PRJ-9` and demanded `PRJ-10`, which padding makes unreachable. Resolved
  unpadded (D-V5P1-7), with the string-sort consequence (`PRJ-10` before `PRJ-9`) carried into the
  plan's risk table and Task 24's Done-when.

**Standing debt carried in, not scheduled:** the human QA checklist stays unrun by design (BACKLOG
p1, `.zj/QA.md` §6 holds zero readings — non-blocking per owner preference); pick-path race `Q2`
open (p2); no server-side module-enable gate (p2); `plum/service.py` ~3,000 lines unsplit (p2).

**Also known going in:** the backend pytest suite **cannot** run in-container (`pytest` is absent
from the image and the bind-mounted venv carries host-path shebangs) — run it from the host venv
against a reachable Postgres. Verify scripts need `PYTHONPATH=/app` in-container. CI needs no
workflow edit: the `verify-scripts` jobs are glob-driven, so `verify_flan.py` and
`verify_flan_api.py` are picked up automatically.

## Prior position: v5.0 spec'd — Phase 1 not yet planned

**v4.0 "Infra-debt + quality paydown" is closed.** Six phases (1, 2a, 2b, 3, 4, 5), 187 commits,
~31.0 h across 15 sessions, 2026-07-20 → 2026-08-18. No new end-user capability — CI on every push,
both lint gates at a zero-violation baseline, the inventory ledger race-safe across every writer,
and a standing requirement-keyed QA checklist.

**The close audit returned GAPS** (`.zj/MILESTONE-v4.0-AUDIT.md`) against a milestone whose every
phase had already passed verification: 1 blocker-to-close, 3 major, 4 minor. **All eight fixed.**

- **C4 was amended, not met** (D-M4-4). `.zj/QA.md` §6 holds **zero readings** — v4.0 ships with
  **no human-exercised UI evidence**, deliberately and on the record. The p1 backlog item stays open.
- **GAP-2** — `execute_pick` was the last ledger writer outside the NFR-7 lock discipline, because
  NFR-7's Statement never listed `pick` (D-M4-5). Both modes reproduced under a barrier; fixed
  `4dc3154` with each half mutation-proven in isolation.
- **GAP-4** — the merge cleared **four consecutive milestones** of master-merge debt. Until PR #5,
  `origin/master` carried **no `.github/` at all**.
- Branch protection now requires **all six** jobs (`frontend`, `backend-lint`, `backend-tests`,
  `verify-scripts`, `verify-scripts-api`, `container-image`) with `enforce_admins: true`.

**Records:** `CHANGELOG.md` v4.0 section · `.zj/logs/milestone-v4.0.md` · `.zj/LEARNINGS.md`
"Milestone v4.0" · `.zj/DECISIONS.md` index regenerated (171, matches body exactly) ·
phases archived to `.zj/history/v4.0/phases/`. `zj doctor`: **0 errors**.

## Next milestone: v5.0 — FLAN port (D-M5-1)

**DoD (owner-approved, D-M5-2 — traces PRD-6):** *"Can create a project with phases and tasks,
assign team members, track a timeline and a budget, and see project cost roll up from SYERP
actuals — with `flan/app/prj-mgmt-v24.html` retired as a reference."*

A straight parity port was offered and declined — the SYERP cost roll-up clause is what makes FLAN
land as a suite member rather than an island. Labor/time capture is **out**; CRISP-01 and NFR-3
offline stay deferred (PRD-9/PRD-10).

### Spec complete — 2026-08-18 (`/zj:spec`, D-V5-1..8)

PRD-6 rewritten from "port the prototype" into project planning whose estimates become SYERP spend.
SRD **FLAN-01** expanded from one line into **FLAN-01..11 + NFR-9** — 11 requirements, 75
acceptance criteria, every one with a named verification. No ID renumbered (append-only).

**Two things changed the shape of the milestone at this spec, both owner calls:**

1. **A second source prototype (D-V5-3).** `flan/app/schedule_gate-v45.html` (~3.8k lines) — a
   dependency-scheduling and deadline-gate engine written *after* BizNiceSweets was first planned:
   `blocks`/`blockedBy` links, topological auto-move, pins, snap/sweep, projected finish, a
   **gate verdict** (`ON TRACK` / `MISSES GATE` / `NO BASIS`), a named calculation basis
   (`in-plan` | `all` | `visible` | `marked`), a `Facet:Value` tag taxonomy with exclusive facets,
   and baselines. Its capabilities are in scope alongside **all four** `prj-mgmt-v24.html` groups.
   **v5.0 is materially larger than a parity port** — managed by phase order, not by trimming.
   ⚠ The file is **untracked in git today**; FLAN-11.2 commits it.
2. **No prototype data migration (D-V5-4).** A `Crisis.json` importer was offered as objective
   retirement evidence and declined — that data belongs to the first prototype the owner used, not
   to FLAN. **FLAN-11's capability-coverage matrix replaces it**: every capability of both
   prototypes mapped to the requirement that delivers it or to a dated deferral.

**The hub clause resolved (D-V5-5) — this is the crux, FLAN-08.** SYERP keeps sole ownership of
spend. A FLAN project holds **estimate lines**; an approved line is **promoted** into a real SYERP
purchase order carrying an optional `flan_project_id` (also on `syerp_bill` and
`mousse_work_order`); the project then reports **Estimated / Committed / Actual** with **Actual
GL-posted**. FLAN never writes a SYERP table directly. The hard verification: **Committed must
retire exactly as Actual appears**, no double count, trial balance still nets zero.

**Other decisions:** unified task model — a phase *derives* dates and % from its tasks, v24's
progress slider not ported (D-V5-1); team roster with an **optional** platform-user link, since real
teams include people who never hold a login (D-V5-2); server-native sharing/undo — deep links that
enforce `flan:read`, server baselines, one-step undo, and **no public share tokens** (D-V5-6);
NFR-9's deliberately generous 1 s / 500-task schedule bound (D-V5-7).

**Phase → FR mapping (D-V5-8) — 7 phases, 9 units** (table in `ROADMAP.md`):
1 (FLAN-01 core) → 2a (FLAN-02 engine + FLAN-04 taxonomy) → 2b (FLAN-03 board) → 3 (FLAN-05/06) →
4a (FLAN-07 budget) → **4b (FLAN-08 — the DoD crux)** → 5 (FLAN-09) → 6 (FLAN-10) → 7 (FLAN-11).
Analytics and exports sit **after** the crux on purpose: a long milestone then risks the tail, not
the definition of done.

**Open, owner-facing:** nothing blocks planning. Two items to be aware of — the milestone is large
by the owner's own scoping, and `schedule_gate-v45.html` needs committing before FLAN-11 can verify.

**Carried in as standing debt, not scheduled:** the human QA checklist is unrun by design
(BACKLOG p1); pick-path race **Q2** is still open (p2 — a pick can append to a shipment a
concurrent pack just flipped to `packed`); module enable/disable has no server-side gate (p2);
`plum/service.py` is ~3,000 lines and wants splitting **before** FLAN adds a suite;
`.zj/codebase/MAP.md` is stale (generated 2026-07-04, pre-v2.0).

## Next action

```
/zj:build 1
```
Execute `.zj/phases/01-flan-core/PLAN.md` — 35 tasks, wave order, one atomic commit each, on a
`feature-flan-core` branch off master with its `docs/tasks/feature-flan-core.md` checklist.
Read `CONTEXT.md` alongside it: it carries the binding decisions, the verified codebase facts, and
the LEARNINGS keepers that apply (chief among them — this phase mirrors CRUMB/GELATO heavily, and
*mirroring an exemplar retires architectural risk, never correctness risk; the copy is un-audited
exactly where your case differs*. The named trap here is the key-collision retry: FLAN's task insert
carries a `phase_id` FK the quote exemplar lacks, so the `except IntegrityError` must be narrowed to
`uq_flan_task_project_key` and bounded — that is the Phase-13 `create_invoice` unbounded-recursion
500 in miniature).

*(Superseded, kept for the record: the previous next action was `/zj:spec`, now done — PRD-6
rewritten, SRD FLAN-01..11 + NFR-9, D-V5-1..8.)*

*(One open item first if you want it clean: **PR #6** from `chore-v4-close-rollforward` carries
this roll-forward plus the archived milestone-close checklist and needs merging to master — the
branch protection applied at close means even a docs-only change now goes through all six checks,
admins included. Nothing in `.zj/` depends on it landing; `/zj:spec` can start either way.)*

*Noticed at close, not acted on (out of scope, owner's call): three v4.0 phase task files were
never archived and still sit in `docs/tasks/` as if active — `chore-ci-pipeline.md`,
`chore-port-verify-cruxes.md`, `chore-pytest-harness-repair.md`. All three phases are closed and
tagged.*

---
## Prior state (v4.0 Phase 5 retro, 2026-08-18)

Updated: 2026-08-18 (**v4.0 Phase 5 RETRO'D — `/zj:retro 5`. Phase CLOSED**, ROADMAP Phase 5 →
`[done — verified 2026-08-17 + retro'd 2026-08-18]`. **This closes the final phase of milestone v4.0.**

**LEARNINGS Phase 05 banked.** Headline keepers, in cost order:
1. **Five phases of green gates never once proved the artifact a self-hoster actually gets.** `U2`
   (the API image could not be built **at all** — `COPY frontend/package*.json` never matched the
   dotfile `.npmrc`) and `U0` (fresh-volume deploy blocked — `db` got its password by interpolation
   from a `compose/.env` that does not exist) are the *same blind spot at two layers*, and both were
   invisible precisely because everyone worked against a long-lived stale image on an already-
   initialized volume. Both now CI-resident (`container-image` job; `test_compose_config.py`).
2. **A config-pinning test can go green against the exact broken config it was written to catch** —
   the pre-fix `compose.yml` carried a comment stating the intent it never implemented. Pin on
   parsed, comment-stripped structure; RED-drive with the prose left intact.
3. **A runbook nobody has executed verbatim is prose.** Running the phase's own bring-up block found
   three doc bugs in one sitting, including a prose *"wait a few seconds"* where a command belonged
   (the bare `curl` after it returns `Connection reset` — the owner concludes the stack is broken).
4. **The fixture can manufacture a *false* defect no balance assertion can see** — total assets
   **−258.25** while the books were perfectly `in_balance` (an unfunded cash account). Fixture layers
   need domain invariants beyond "it balances", asserted every seed run.
5. **"Don't point it at prod" is not a safeguard when podman-compose names both stacks `compose`.**
   A destructive seed needs an explicit env opt-in a copy-pasted command cannot satisfy.
6. **Aggregate ledger figures on a shared dev DB are litter** (+50.00 per `verify_*` sweep, 4950.00
   accumulated) — never quote a whole-ledger total as a fixture literal.

**Biggest cost sink, and it was structural:** twelve tasks whose `Done when` only the owner could
satisfy **stalled the phase at 22/41 for three weeks and held the entire milestone** behind one ~3 h
sitting. Now an owner preference (`QA docs: non-blocking`) and a standing rule: never write a plan
task gated on the owner running something. Second: the plan disagreed with itself about size from day
one (D-P5-1's "~40–50 checks" vs. its own per-suite maxima summing to exactly 59) — reconcile
aggregate estimates against per-unit targets at plan time.

**Five previously unhomed items filed** (PLAN `## Noticed` + reviewer questions): **p2 — module
enable/disable has no server-side gate** (`/api/v1/<module>/*` still serves a disabled module; CORE-07
*as written* is satisfied, so it is an unbuilt capability, but the three Phase-4 dialogs' docstrings
are wrong about why they hide — the docstring half is cheap and should be done now); **p3** — the
commented `compose.yml` module templates that re-introduce `U0`, the unencoded `POSTGRES_PASSWORD` in
the DSN (an `@` in a first-time self-hoster's password = opaque asyncpg error on first boot),
operator-facing error copy naming entities by numeric id, and Receipts/Payments having no human
document number.

**No future-phase resize** — Phase 5 was the last of v4.0. The module-gate item is homed as a
**Quality & release** candidate rather than forced into this milestone (v4.0's DoD ships no new
end-user capability). The **p1 human-UAT backlog item stays open by design** — `.zj/QA.md` §6 holds
zero readings, and per D-P5-11 it ticks only when a person clicks.

**Next action:** `/zj:milestone` — close out v4.0. **The owner's call there:** whether v4.0 ships on a
checklist nobody has run. NFR-8 as re-worded does not claim a human exercised any flow, and the
per-module "UI flow still UAT-pending" caveats stay. Read NFR-8's "NOT evidenced" bullet first. Also
offered: `/zj:log phase 5` to file the formal work log for the record. The stack is up and seeded at
**http://localhost:8000**. **An engineer must still never tick an owner check or infer a pass.**)

Prior: 2026-08-17 (**v4.0 Phase 5 VERIFIED — `/zj:verify 5`, verdict PASS after a full fix loop.**
Tip `bbd795b`, tag **`zj/good-05-human-uat`**. **This closes the final phase of milestone v4.0.**

**First pass was GAPS, honestly.** Verifier: 5 major / 5 minor. Reviewer: 4 major / 3 minor, 0 blocker.
The owner chose the **full fix loop** (four serialized engineer waves, 11 commits `fd7ca87..d3e68e2`);
re-verification at `d3e68e2` returned **PASS — 0 blocker, 0 major, 6 minor**, with every gap re-driven
empirically rather than read from the engineers' reports.

**The rescope held up under adversarial review.** D-P5-11 was the top thing I asked the verifier to
attack — SC4 moved from "zero `todo` rows at close" to "unrun checks are not a failure", which is
exactly the shape of a criterion quietly redefined to match what got built. It is **not** that: the
decision is owner-attributed, names the decisions it supersedes (D-P5-6, D-P5-7), preserves every
struck SC's original wording inline, and repeats "NOT evidenced, by design" across SRD/ROADMAP/
BACKLOG/requirements-progress. **Evidenced:** 61 judgeable checks against reproducible fixtures.
**Not evidenced:** that any human clicked anything. Both halves stay stated.

**What the fix loop actually caught — two of these could have hurt a real user.**
(1) **The phase's own product change had a hole:** `post_adjustment` validated bin existence and
location membership but **not `active`**, while `execute_putaway` validates all three — so stock could
be booked into an archived bin `list_bins` hides, making the location total and the per-bin split
disagree. That is precisely the failure SC8's docstring says it exists to close. Fixed `fd7ca87`,
pinned `947e5d6` as scenario **(G5)**; RED `status=None rows 3->4` (no exception at all, ledger row
appended) with G1–G4 still PASS, so nothing hijacked red.
(2) **`seed_uat_fixtures.py` could seed a self-hoster's live books.** podman-compose derives its
project name from the first compose file's directory — `compose/` for **both** stacks — so the
runbook's copy-paste `podman exec … compose_api_1 …` targets whichever is up, posting an
opening-capital JE, a bill, a payment and an AR invoice **irreversibly** (append-only), plus an active
login whose password is committed to the repo. Now two gates (`3a6ce35`): `BNS_ALLOW_UAT_SEED=1`, set
by the dev overlay only, and a foreign-ledger refusal. **The subtle part:** the guard must match on
the seed **actor**, not just a `UAT-` memo prefix — only 2 of the 8 seeded JEs carry that prefix, so a
prefix-only guard would have refused every second seed and broken SC2's idempotency contract.
(3) The `.env`/`.env.db` split broke **existing** deployments on upgrade (later `env_file` wins, so
`api` picks up the template password against an initialized volume — U0's exact class); `uat.ps1` was
never ported while the new docs claimed it was; and a promised p2 BACKLOG item had never been filed.

**Criteria became tests — the headline durable outcome.** Four SCs were true only because someone
hand-checked them. All four now re-run every push, each proven non-vacuous by mutation:
`verify_qa_doc.py` (coverage arithmetic, both directions), `verify_qa_citations.py` (224 citations
resolve), a seed-idempotency `verify-scripts` step on its **own** database (asserts a byte-identical
manifest **and** a 47-table row census — the census earns its place: making `_ensure_cost`
unconditional again grows `audit_log 100→104` while the manifest stays identical), and a
**`container-image` CI job that builds the shipped artifact**. That last one matters most: `U2` — *the
image could not be built at all* — hid for five phases precisely because nothing ever built it.
⚠ `container-image` is **not yet a required status context** — that needs a repo-settings change no
workflow file can make.

**Final gate at `d3e68e2`:** pytest **245 passed / 0 skipped**, **17/17** non-API + **9/9** API
`verify_*`, ruff + eslint 0, vitest 148/45, **CI run `32072598536` 5/5 success** (first real-runner
green for `container-image`). Prod stack re-driven at `:8000` on a fresh volume — the verification
caught **the artifact going stale again** (`fd7ca87` postdated the built image, the v1.0 G2 class), so
it rebuilt from HEAD and re-drove SC7 plus both SC8 rejections live. `.zj/QA.md` now carries a
precondition: the image must be newer than the last product commit.

**6 minors homed p3**, none blocking: the two new QA guard scripts can't run the in-container way
(`.zj/` isn't in the image, so the house recipe yields 15/17); `verify_qa_citations.py` erodes silently
if a citation loses its *shape*; three `verify_gl.py` citations are only weakly pinned (that script
letters scenarios lower-case). NFR-8 stamped `- **Verified:** d3e68e2`; ROADMAP Phase 5 → `[verified]`.

**Next action:** `/zj:retro 5` — this phase produced real keepers (a criterion whose only proof is the
verifier's own hand-check is not protected; a fixture-guard's matcher must be derived from what the
fixture actually writes, not from its naming convention; and "the artifact is stale" has now cost two
milestones). Then `/zj:milestone v4.0`, where **whether v4.0 ships on an unrun checklist is the owner's
call** — `.zj/QA.md` §6 still holds zero readings, by design. The stack is up and seeded at
**http://localhost:8000**. **An engineer must still never tick an owner check or infer a pass.**)

Prior: 2026-08-17 (**v4.0 Phase 5 BUILD COMPLETE — every task done; next `/zj:verify 5`.**
Branch `chore-human-uat`, now pushed to `origin`. Tasks 0–19 (engineering, previously done), then
**32–35, 37–38** this session. Tasks **20–31 and 36 were struck** by **D-P5-11**, not skipped.

**D-P5-11, the rescope.** Twelve tasks had a `Done when` only the owner could satisfy ("every row
`pass` or a defect ID; zero `todo`"). The phase stalled at 22/41 for three weeks and held the v4.0
milestone behind a ~3 h sitting — the shape the owner preference **`QA docs: non-blocking`** forbids.
Struck as plan tasks; restated as a parallel twelve-sitting to-do with dependency order preserved.
**The deliverable is the checklist, not the reading.**

**`.zj/QA.md`** (`493e185`, extended `fbac89b`) — the standing regression checklist. **61 checks**,
all judgeable, re-keyed from phase success criteria onto **SRD requirement IDs**, so it survives
phase closure and can express coverage: **31 of 47** requirements checked, §5 names **zero real
gaps**. §6 result log is the resumable state; §7 is the defect ledger. `UAT-v1.0/v2.0/v4.0` carry
pointer lines and are history.

**Three defects, every one found by engineering before anyone clicked.** `U0` blocker (fresh-volume
deploy) `4ace2c4`+pin `d870233`; `U1` major (500 on duplicate email) `f508554`+pin `f67f085`; and
**`U2` blocker — the API image could not be built at all**: `COPY frontend/package*.json ./` never
matched the dotfile `frontend/.npmrc`, so `npm ci` ran without `legacy-peer-deps=true` and died on
the `eslint-plugin-react-hooks@5` peer range. Introduced by Phase 1's lint devDeps and **masked for
five phases by the stale image the p1 backlog item was about** — Task 34's rebuild was the first
attempt since, and it failed on the first try. Fixed `8d61cca`, pinned `f82ec38`, RED on revert.

**Two corrections to previously recorded facts, both found by executing.** The `verify_*` sweep
drifts the seeded fixtures by **`+100.00`**, not the `+50.00` attributed to `verify_purchasing.py`
alone — so a second leaker exists and is **unidentified** (p3 re-worded to say so). And **NFR-1 has
no human surface at all**: `write_audit` is called throughout the backend, but no audit endpoint is
exposed and nothing in `frontend/src/` reads audit events — re-triaged from "real gap" to
machine-only. Also: `podman-compose build` printed `exit code: 1` and **returned 0**, which nearly
hid U2 — never trust its exit status, grep for `Error: building at STEP`.

**Gate at `81a8f55`:** pytest **243 passed / 0 skipped** (baseline 232), 24/24 `verify_*`, ruff +
eslint 0, vitest 148/45. CI 4/4 success at phase HEAD: run **32064085911** @ `1954b56`; the
first-push run **32059723558** @ `81a8f55` was also 4/4 but predates the `U2` fix and its pin. Prod stack verified on a **fresh volume** at `:8000`: `/` 200
serving `index-BQmUVhcG.js`, byte-identical to the host bundle, `alembic current` `0017 (head)`,
all 275 derived fixture literals identical to the Task-8 record, admin login + authed reads 200.
NFR-8 stamped `done`; ROADMAP/BACKLOG/DECISIONS trued up (D-P5-1..11, 137→148); checklist archived.

**What is deliberately NOT done: anyone has run the checklist.** `.zj/QA.md` §6 holds **zero**
readings. Under D-P5-11 that blocks nothing — but NFR-8 no longer evidences that a human exercised
the flows, the module rows caveated "UI-flow UAT-pending" **stay** caveated, and the p1 backlog UAT
item **stays open** by design. **Whether v4.0 ships on an unrun checklist is an owner call at
`/zj:milestone`.**

**Next action:** `/zj:verify 5`. The owner run is a parallel to-do with no due date — the prod stack
is up and seeded at **http://localhost:8000** (dev `:5173` is down; `compose.yml` alone has no
frontend service). **An engineer must still never tick an owner check or infer a pass.**)

Prior: 2026-08-17 (**v4.0 Phase 5 RESCOPED — D-P5-11; build resumes at Task 32.** The phase had
stalled at 22/41 for three weeks because twelve of its tasks (20–31, 36) had a `Done when` only the
owner could satisfy — "every row has `pass` or a defect ID; zero `todo`". The new owner preference
**`QA docs: non-blocking`** forbids that shape outright, so those tasks are **struck** and restated as
a parallel to-do with their dependency order preserved (`PLAN.md`).
**The deliverable is now the checklist, not the reading.** `.zj/QA.md` (`493e185`, 1,595 lines) is the
standing regression checklist: all 59 checks carried over **verbatim** from `UAT-v4.0.md` but re-keyed
from phase success criteria onto **SRD requirement IDs**, so it stays true as phases close and can
express what a phase-shaped doc could not — **coverage**. After Task 32: **31 of 47** requirements
carry a human check and §5 lists **zero real gaps** — CORE-01 and CORE-09 were closed by two new
checks (`C-CORE-08` prod-stack deploy smoke, `C-CORE-09` fresh-volume-reaches-head), and **NFR-1 was
re-triaged as machine-only**: `write_audit` is called throughout the backend but no audit endpoint is
exposed and nothing in `frontend/src/` reads audit events, so there is nothing for a human to look at.
The remaining 16 are 9 not-built, 6 machine-only, and NFR-8 itself. `C-SC6-a/b/c` were re-keyed onto
SYERP-10 and MOUSSE-01 — they cited `SC6`, a phase criterion meaningless outside Phase 5.
SC1/SC4/SC6/SC7 amended; NFR-8's Statement and Verification rewritten; `UAT-v1.0/v2.0/v4.0` all now
carry pointer lines to `.zj/QA.md` and are history.
**Consciously accepted:** NFR-8 is now satisfiable by a checklist nobody has run. That is the point —
it stops an unrun checklist blocking a milestone — but it means NFR-8 no longer evidences that a human
exercised the flows, so the module rows caveated "UI-flow UAT-pending" **stay** caveated, and whether
v4.0 ships on an unrun checklist is a separate owner call at `/zj:milestone`.
**Next action: Task 32** (reconcile the checklist — audits the checklist, never the readings), then
33–35, 37–38. The owner run is a parallel to-do with no due date; readings go in `.zj/QA.md` §6.
**An engineer must still never tick an owner check or infer a pass.**)

Prior: 2026-07-26 (**v4.0 Phase 5 BUILD IN FLIGHT — `/zj:build 5`, engineering complete through
Task 19; PAUSED AWAITING THE OWNER RUN.** Branch `chore-human-uat` (cut off `c02d80b` per D-P5-9 then
fast-forwarded to the plan-carrying tip `4171605` — docs-only, code-identical; trivial deviation, same
pattern as Phases 3/4/13). Task count grew **39 → 41**: two defect-fix tasks added mid-build (8a, 10a).
**Done: Tasks 0–8, 8a, 9, 10, 10a, 11–17, 18, 19** — all engineering complete; only the `[OWNER]`
sittings (20–31, 36) and close-out (32–35, 37–38) remain.
**SC8 met** (`e57c1ff` + pin `0a7a89f`): `post_adjustment` now rejects a non-null `bin_id` that does not
exist or does not belong to `location_id` — one raw-SQL probe, **no gelato import** (D-P12a-3 holds),
422 + nothing persisted, pinned as `verify_gelato.py` scenario **(G)**. RED was unambiguous
(`status=None rows 1->2` — no exception at all, stock booked into a bin at the wrong location) and
provably attributable: G1 uses a **positive** delta, which D-P4-6 gives no floor guard, and the FK is
satisfied because the other location's bin genuinely exists — so the membership probe is the only guard
that could reject it. The **NULL path is confirmed untouched**, which is what keeps the SC6 fixture
design valid.
**SC2 met:** NEW `backend/scripts/seed_uat_fixtures.py` builds seven fixture layers and is **proven
idempotent on a genuinely fresh volume** (43 named keys, 361-line manifest recorded verbatim in
`docs/tasks/chore-human-uat.md` as the authoritative literals). Load-bearing literals: `UAT-P104`
roll-up **99.15** / margin **−59.15 / −59.66 %** / flat-BOM dedupe **UAT-P102 qty 11**; `UAT-ITEM-1`
moving avg **6.669231**, on-hand value **86.700003**; `UAT-ITEM-4` unbinned pool **0** at `UAT-LOC-A`
(the fixture SC6's pool-floor rejection depends on); AP **57.75** in 31-60, AR **84.25** in 61-90.
Every fixture layer picks anti-coincidence arithmetic on purpose (a second costed leaf so no single flat
row equals the roll-up; a divisor making ROUND_HALF_UP load-bearing; disjoint documents so Task 27's
receiving and Task 30/31's ship→invoice cannot move Task 23/24's literals).
**SC3 met:** `PREFLIGHT.md` maps **59 checks** (ID scheme `C-`-prefixed, suite-local, so a check can
never be confused with an SRD requirement), **309 citations verified, zero misses**; 49 cited, 9
machine-unproven, 1 probed (`getVisibleModules`, mutation-exercised — wildcard-first ordering would make
`C-SC6-d` silently pass while broken).
**SC1 met:** `.zj/UAT-v4.0.md`, 1,574 lines, **59 checks / 59 status rows, perfect 1:1, all `todo`**;
63 quoted literals all traced to the manifest (the tracer caught two quoted from a live query, not the
manifest). **Three defects found and homed BEFORE any human clicked** — SC3 paying for itself:
**`U0` (blocker, fixed `4ace2c4` + pin `d870233`)** the compose stack could not start on a fresh volume
at all (`db` got `POSTGRES_PASSWORD` by interpolation only; `compose/.env` doesn't exist → empty →
Postgres refuses to init; invisible for the life of a volume, so five phases never hit it; blocked
Task 35/SC7 and every first-ever self-hosted deploy) → **D-P5-10** dedicated `.env.db`, pinned by
`backend/tests/test_compose_config.py` whose matcher **strips comments** because the pre-fix file's own
comment claimed the fix was already there; **`U1` (major, fixed `f508554` + pin `f67f085`)** duplicate-email
user create returned **500**, now a clean 409 matching the house convention, narrowed to `ix_users_email`
(users has two unique indexes, so a broad except would misreport a PK collision — the Phase-13
`create_invoice` failure in miniature), no-partial-row proven; plus a **false defect averted** — on a
fresh volume the Balance Sheet showed **negative total assets** because the fixture spent from an
unfunded Cash account, which the owner would reasonably have reported at Task 23 (fixed with an opening
capital contribution; `report()` now asserts `total_assets > 0`).
**Two owner decisions mid-build (AskUserQuestion ×2):** **D-P5-10** (U0 fix = dedicated db env file,
rejecting `env_file: ../.env` on db because it spreads `JWT_SECRET` into a container that needs it not);
and **D-P5-1 amended — keep all 59 checks** (the overage is structural: 59 is the exact sum of the plan's
own per-suite maxima, so "~40–50" and the per-suite ranges never agreed; full coverage was the binding
half of D-P5-1). Runbook estimate **~3 h** across eleven suggested sittings.
**Corrections to the plan's own facts, all found by executing rather than reading** (Phase-03 keeper,
now fired four times): in-container `pytest` **does not work** (absent from the image; the bind-mounted
`.venv/bin/pytest` has host-path shebangs) → Task 33 must use the host venv against a reachable
Postgres; the runbook's health-check was **prose** where a command was needed and failed with
`curl: (56)`; the seed is **~5 s, not ~40 s** and the whole bring-up **~30 s**.
**Neither product tripwire fired** — no Alembic migration (head still `0017`), no GL/JE posting-rule
change. Tree clean except the owner's `.vscode/settings.json` (left dirty per D-P5-9).
**Next action: the owner run — Task 20, the CORE sitting**, then 21→31 one sitting per suite,
read-only before mutating, money loop last. Stack is up and seeded at **http://localhost:5173**
(admin from `.env`; DB keys now live in `.env.db`). The status table in `.zj/UAT-v4.0.md` is the
resumable state — a paused run is normal. **An engineer must never tick an owner check or infer a pass.**
Then close-out 32–38. Full detail in `PLAN.md` `## Deviations` / `## Noticed`.)

Prior: 2026-07-26 (**v4.0 Phase 5 PLANNED — `/zj:plan 5`.** Phase 5 = **human click-through UAT
(NFR-8)** — the FINAL v4.0 phase, closing the DoD's last clause. **39 tasks, 13 of them `[OWNER]`**
(`.zj/phases/05-human-uat/PLAN.md`): fixtures (T1–8 NEW idempotent `backend/scripts/seed_uat_fixtures.py`,
proven twice-identical on a genuinely fresh volume) → pre-flight (T9–10 `PREFLIGHT.md` maps every check
to the existing `verify_*`/pytest/vitest assertion that already proves its backend; T10 adds the missing
`getVisibleModules` probe) → checklist (T11–15 author ONE consolidated `.zj/UAT-v4.0.md`; T16 **executes
every runbook command once at build time**; T17 pointer lines on the old docs) → SC8 (T18–19 the
positive-adjust bin-membership check + `verify_gelato.py` scenario G, mutation-proven) → **owner run
(T20–31, one sitting per suite, read-only before mutating** so no check poisons a later fixture; money
loop last) → close-out (T32 zero-`todo` reconcile, T33 full regression gate, T34–36 rebuild dist+image
then prod-stack smoke at :8000 on a fresh volume, T37–38 bookkeeping). **9 SCs.** **9 owner decisions
(AskUserQuestion ×2 rounds) → D-P5-1..9:** breadth = **residue-only, full coverage** (~40–50 checks,
est. 2–3 h — each check names only what a machine can't confirm; the v1.0 "what the machine already
proved" shape); env = **Vite :5173 for the click-through + one prod-stack smoke** (D-P7-1 precedent, and
under the dev overlay :8000 serves no SPA at all); fixtures = **seed script on a fresh DB** (the v1.0 UAT
was burned when the dev volume was recreated and its named fixtures vanished); defects = **fix
blocker/major in-phase with a pinning test, home minor to BACKLOG with a `U#` ID**; **ADD** the p2
positive-adjust bin-membership check (resolves the owner call the Phase-4 retro flagged); **one**
`.zj/UAT-v4.0.md` (amends NFR-8's literal three-doc wording — trued up at T37); run mechanics =
**interactive, suite by suite**, the status table is the resumable state; **CORE surfaces IN scope**
(~6 checks — needed anyway for the GELATO-off path); branch = fresh `chore-human-uat` off `c02d80b`.
**Two STOP-and-flag tripwires:** any Alembic migration, any GL/JE posting change — v4.0 ships no new
capability, so the only authorized product code is UAT defect fixes + the SC8 check. Keepers baked in:
fresh-volume-or-it's-unproven (P3), execute-the-runbook-before-trusting-it (P3), hand-checked ≠ pinned +
RED-must-fail-for-the-intended-reason (P4), and the dead-through-UI trap this UAT is the counter-measure
for. Top risk: **reading a machine pass as a human pass** (exactly the v1.0 G1 failure) — countered by a
hand-back protocol that forbids an engineer ticking or inferring an owner check. Two plan findings:
**there is no server-side module gate** (toggling GELATO off only filters the sidebar; the three Phase-4
dialogs' "hidden when GELATO off" docstrings are likely wrong about the cause — T15/T26 record the truth),
and **7 route screens have no colocated vitest** (Home, Settings, Modules, GLAccounts, LeadDetail,
OpportunityDetail, Quotes) = the genuinely machine-unproven set, weighted heaviest in the run.
**Next action:** `/zj:build 5`.)

Prior: 2026-07-25 (**v4.0 Phase 4 CLOSED — `/zj:retro 4` done.** LEARNINGS Phase 04 banked:
(1) one transform applied across N sibling writers dropped MOUSSE's per-location floor while its
two siblings kept it — the review artifact is the **cross-sibling guard diff**, since a dropped
guard reads as normal code in isolation and only a legacy-desynced fixture can expose it;
(2) **hand-checked ≠ pinned** — "all six SCs empirically true" was still correctly GAPS because
the proof was the verifier's own throwaway script; verify must classify each SC's proof as
*pinned* (CI assertion) vs *observed*; (3) a mutation-proof's RED must fail for the **intended**
reason — G2's fixture needed a real moving-avg cost (10 @ 5) or the zero-value JE guard would
have hijacked the red, and M3's actual RED signature (double receipt + lost-update accumulator)
differed from the predicted `qty_received > qty_ordered`; plus 12a's pinned boundary making its
own closure a planned task, and Phase 3's CI glob making the new pins free. ROADMAP Phase 4 row
→ `[done — verified + retro'd]`; **Phase 5's UAT scope amended** to cover this phase's three bin
pickers incl. the GELATO-off degraded path. BACKLOG: two unhomed PLAN `## Noticed` items filed p3
(pre-lock `moving_avg_cost` staleness in `post_issue`/`post_putaway`; `verify_purchasing.py`
orphan JEs); the p2 positive-adjust bin-membership item **still needs an owner call** — natural
companion to Phase 5. **Next action:** `/zj:plan 5` (Human click-through UAT, NFR-8 — the last
v4.0 phase). Optional: `/zj:log phase 4` to file the formal work log. Verify history below.)

Verify record: (**v4.0 Phase 4 VERIFY — `/zj:verify 4`, fix loop complete.**
Verifier + reviewer both ran on `7a71fd0..3126c48`: initial verdict **GAPS** (REVIEW.md: 1 major —
MOUSSE `issue_components` dropped its per-location floor going pool-aware, bin-named issue on
legacy-desynced data could drive location on-hand negative + book WIP for nonexistent stock;
2 minor. VERIFICATION.md: all six SCs empirically true but transfer/MOUSSE/positive-adjust
bin behaviors had NO automated pin — hand-check only). **Fix loop done, tip now `3253917`:**
`2a87f6d` restores the location floor beside the pool floor (mutation-proven RED→GREEN via new
`verify_mousse.py` scenario G2 legacy-desync fixture — guard off ⇒ issue succeeds, location
−10.000000); `5a45a7b` `db.refresh(item)` under the post_transfer lock (stale leg-cost provenance);
`c692498` `verify_gelato.py` scenario F pins binned transfer (NULL-422, out-leg-binned/in-leg-NULL
D-P4-5) + D-P4-6 positive-into-bin; `3f45685` scenario G pins binned MOUSSE issue; `3253917`
checklist addendum. Post-fix gates: ruff clean, in-container pytest 232/0-skipped, sweep 15/15
SWEEP_OK, CI run 30185233894 4/4 green on `3253917`. Deferred to BACKLOG: positive-adjust
unvalidated bin_id (p2, **owner decision needed**: membership check vs accept), `pick_for_shipment`
unsorted item locks (p2), `TransactionRead` bin_id omission (p3) — PLAN `## Noticed` has the full
fix-loop record. **Verifier re-verification of the new tip is running** (will rewrite
VERIFICATION.md's verdict). **Next action:** on fresh `Verdict: PASS` — close out `/zj:verify 4`
(ROADMAP `[verified]`, SRD NFR-7 verified + `- **Verified:** 3253917` stamp, check off the two
claimed BACKLOG p2 items, commit artifacts, tag `zj/good-04-inventory-race-safety`, then
`/zj:retro 4`).)

Prior: 2026-07-25 (**v4.0 Phase 4 BUILD COMPLETE — `/zj:build 4`.** All 14 tasks (0–13) on branch
`chore-inventory-race-safety` (cut at T0 `378fb34` off the plan-carrying tip `7a71fd0`,
code-identical to the D-P4-4 base `db725fd`); checklist archived to
`docs/tasks/_completed/2026-07-25-chore-inventory-race-safety.md`. **NFR-7 delivered in two waves:**
(locks, `73e45c2`/`e1dc5c0`) `post_receipt`/`post_adjustment`/`post_transfer` take the item-master
`SELECT … FOR UPDATE` before any floor/aggregate read — post_receipt additionally re-reads the row
under the lock (T1 trivial fix-forward: the identity map would otherwise serve a stale
`moving_avg_cost`, leaving the lost-update it claims to fix) — and `receive_line` locks the PO
header via `_get_po_row(for_update=True)` (PO→item lock order documented); (bin-aware,
`4285202`/`b80cb37`/`455cf5c`/`4ae2b2c`) `AdjustmentCreate.bin_id`, `TransferCreate.from_bin_id`
(out leg binned, in leg lands unbinned per D-P4-5), MOUSSE per-line `IssueComponentLine.bin_id`
(floor key widened to item/location/bin via `get_bin_on_hand`), trust-boundary docs trued up.
**Proofs:** NEW `verify_inventory_race.py` (`f394408`) runs 4 `asyncio.Barrier` races (MOUSSE-issue
× SYERP-adjust — the SRD-named pair; adjust × transfer; receive×receive on one PO line;
receipt×receipt moving-avg) — **all 4 mutations EXECUTED RED→GREEN** (M1 on-hand −4 both writers
landed — proves the discipline is SHARED; M2 source pool −4; M3 both receives landed + double GL
post with the accumulator lying at 7; M4 avg 10.000000 vs correct 9.583333), table filled in the
archived checklist; `verify_gelato.py` scenario E flipped from pinning the desync to asserting the
fix (`ad6a35d`). **T9 sweep (`2692b47`): 15/15 non-API + 9/9 API `verify_*` exit 0, pytest 232
passed / 0 skipped, TB nets zero — ZERO D-P4-1 fixture reconciliations needed** (the plan's top
risk didn't materialize). **FE (SC4):** bin pickers on StockAdjust/StockTransfer/IssueComponents
dialogs with real-payload Vitests both ways (`6d55d72`/`b270161`/`886193a`; T12 wired a required
`targetLocationId` prop from WorkOrderDetail — the dialog had no location in scope); full FE gate
44 files / 139 Vitest + eslint + `tsc -b` + build exit 0. **No GL/JE change, no migration — both
tripwires unfired.** Deviations all trivial (logged in PLAN `## Deviations`); engineers serialized
per 2b precedent (shared test DB + git index). Noticed (triage at verify/retro): identity-map
staleness shape in transfer/putaway/issue `unit_cost` legs (valuation metadata only); product-wide
`HTTP_422_UNPROCESSABLE_ENTITY` deprecation warnings; `verify_purchasing.py` leaves orphan JEs;
`useBins` lacks `retry: false`. SRD NFR-7 → done pending verify; requirements-progress NFR-7 row;
D-P4-1..6 appended to DECISIONS.md. Branch pushed, all four CI jobs green on the tip (the new race
script auto-ran in `verify-scripts`). **Next action:** `/zj:verify 4`.)

Prior: 2026-07-25 (**v4.0 Phase 4 PLANNED — `/zj:plan 4`.** Phase 4 = **inventory ledger
race-safety (NFR-7)** — the shared sorted-id `SELECT … FOR UPDATE` discipline extended to the four
still-unlocked writers (`post_receipt`/`post_adjustment`/`post_transfer` in
`syerp/service/inventory.py`; purchasing `receive_line` via a PO-header lock), AND the three
remaining bin-blind draw primitives (`post_adjustment`, `post_transfer`, MOUSSE `issue_components`)
made bin-aware. **14 tasks** (`.zj/phases/04-inventory-race-safety/PLAN.md`): T0 branch → lock wave
(T1–2) → bin-aware wave (T3–5 + T6 doc truth-up) → verify wave (T7 NEW
`verify_inventory_race.py` — 4 mixed-path `asyncio.Barrier` races incl. the SRD-named MOUSSE-issue
× SYERP-adjust pair, each mutation-proven per a 4-row M1–M4 table; T8 `verify_gelato.py` scenario E
revised from pinning the desync to asserting the fix; T9 behavior-change sweep classifying every
breakage intended-change vs regression) → FE wave (T10–12 bin pickers + real-payload Vitests) →
T13 full gate + bookkeeping. **6 decisions at plan (owner via AskUserQuestion ×2 rounds):**
D-P4-1 bin semantics = **explicit-or-unbinned** (optional `bin_id`; NULL draws ONLY the unbinned
pool, 422 when insufficient — no auto-allocation; accepted behavior change at fully-binned
locations); D-P4-2 **single phase** (no 4a/4b — same four functions); D-P4-3 GELATO pick-path Q1/Q2
races stay BACKLOG p2; D-P4-4 branch = fresh `chore-inventory-race-safety` off the Phase-3 tip
`db725fd` (unmerged v4.0 stack); D-P4-5 transfer in-leg lands UNBINNED at destination (putaway
directs it — confirmed); D-P4-6 positive adjustments may target a bin, additions take no floor
guard (confirmed). Recorded in PLAN `## Decisions`, appended to DECISIONS.md at T13. **No GL/JE
change, no migration expected — both STOP-and-flag tripwires.** Top risk: D-P4-1 ripples through
GELATO/MOUSSE fixtures that putaway-then-draw-bin-blind (T9 owns the reconciliation). BACKLOG p2
inventory-race + bin-desync(inbound) items marked claimed. Keepers baked in: only-the-guard-under-
test-can-reject fixtures (12b), indivisible-remainder quantities (2b), verify-recipe run-in-env
(P3), dead-through-UI wiring per FE task. CI from Phase 3 now guards every push of this branch;
the new verify script auto-runs in the `verify-scripts` job. **Next action:** `/zj:build 4`.)

Prior: 2026-07-25 (**v4.0 Phase 3 RETRO'D — `/zj:retro 3`. Phase CLOSED**, ROADMAP Phase 3 →
`[done — verified + retro'd 2026-07-25]`, tag `zj/good-03-ci-pipeline` stands. **LEARNINGS Phase 03
banked (2 surprises + 4 repeats):** (surprise 1, the headline) *"X self-provisions from a bare server"
is unproven until run against a genuinely EMPTY environment* — conftest's probe targeted `biznice_test`,
the very DB provisioning was about to create, so fresh CI aborted before provisioning; 2a/2b's "232
passed" only worked because the DB persisted locally (D-P3-4). Keepers: probe a resource that exists
*before* bootstrap (maintenance `postgres` DB), and CI's fresh-per-run service is itself the standing
protection for the bootstrap path — a class local dev can't provide. (surprise 2) *a recipe derived by
READING code confirms what code doesn't do, not what the environment must already have* — the plan's
verify-scripts recipe missed `PYTHONPATH` + the lifespan seeds because its own Verify line was never
executed at plan time; run the plan's verify command once before trusting it. (repeats) engineer out the
check-name↔branch-protection footgun (explicit `name:` + read contexts from a real run before the PUT);
a CI phase's deliverable is proven RED, not just green (SC3/SC4 demos); job isolation dissolves
DB-contract collisions (per-job `postgres:17` services); verify-the-verifier (authed `gh` live re-check +
fresh-container reproduction with `pg_database` before/after). **BACKLOG trued up:** p1 **CI pipeline**
item → RESOLVED (Phase 3); its Phase-1/2a folded residuals + the verify's 4 minors → new **p3 "CI
hardening niceties"** (enforce-smoke, 0-skipped guard, pytest rerun, ci.yml meta-test, Node-20 action
bump, duplicate push+PR runs, `.npmrc` peer-mask caveat); true-up: p1 "Port Phase-8 verify-script
assertions" was delivered by Phase 2b → checked off. **No roadmap resize** — Phase 4 (NFR-7 inventory
ledger race-safety) stands, now guarded by this CI; PR #4 stays OPEN (merge via `/zj:ship`, out of
phase scope). **Next action:** `/zj:plan 4` (NFR-7 — shared FOR-UPDATE lock across
issue/adjust/receive/transfer/ship + make `post_transfer`/`post_adjustment`/MOUSSE-issue bin-aware,
mutation-proven mixed-path concurrency). Optional: `/zj:log phase 3` for the formal work log. Verify
detail in the prior entry below.)

Prior: 2026-07-25 (**v4.0 Phase 3 VERIFIED — `/zj:verify 3`. Verdict PASS**, tag
`zj/good-03-ci-pipeline`. Verifier + reviewer ran in parallel, both **empirically**. **All 7 SCs PASS:**
the verifier's authed `gh` re-confirmed **live** (not on trust) every claimed run ID — all-green
**30140504003**, broken-test **30140642516**→revert **30140733237**, lint **30140870255**→revert
**30140959653** — plus **PR #4** (base `master`, CLEAN, four required checks pass) and branch-protection
`required_status_checks.contexts=[frontend, backend-lint, backend-tests, verify-scripts]`; AND it
**reproduced every CI check locally against a FRESH `postgres:17`** (podman): `pytest` **232 passed / 0
skipped** with `biznice_test` self-provisioning confirmed by querying `pg_database` before/after (proves
the D-P3-4 probe fix genuinely works on an empty server), **14/14** non-API `verify_*` exit 0, FE
lint/tsc/vitest(131)/build all exit 0. **Product-code boundary CLEAN** — `git diff 4960d32..cf2a805 --
backend/app/ frontend/src/` **empty** (only `backend/tests/conftest.py` changed, the authorized D-P3-4
test-infra fix). **Reviewer: 0 blocker / 0 major / 0 minor** — traced every gate-masking vector and none
holds: no `continue-on-error`/`|| true`/masking `if:`; verify-scripts loop runs under `set -e` with
scripts that `sys.exit(main())`; the four job `name:` values exactly match the branch-protection contexts
(classic footgun avoided); both Postgres services have `pg_isready` health checks; the conftest repoint
only governs the loud-abort gate so it can't turn "DB unreachable" into a silent skip. **4 minor items,
none blocking, all already homed** (p3 in PLAN `## Noticed` / backlog): no meta-test on workflow shape;
SC3/SC4 red-demos are one-time (standing protection = the jobs run every push; 0-skip invariant already
pinned by 2a's `test_harness_selfcheck.py`); Node-20 action-deprecation warning (cosmetic). Owner chose
**close out as-is** (no enforce-smoke nicety built). SRD NFR-4 → **verified**, stamped `cf2a805`; ROADMAP
Phase 3 → `[verified]`; requirements-progress NFR-4 row flipped; artifacts `VERIFICATION.md` + `REVIEW.md`
committed. **Next action:** `/zj:retro 3` (bank the CI-gate keepers — job-name↔branch-protection-context
alignment, fresh-DB provisioning as the D-P3-4 protection) or `/zj:plan 4` (NFR-7 inventory ledger
race-safety). Full build detail in the prior entry below.)

Prior: 2026-07-24 (**v4.0 Phase 3 BUILD COMPLETE — `/zj:build 3`.** Branch `chore-ci-pipeline` cut
off the plan-carrying tip `8a27a46` (code-identical to `4960d32` + the plan doc; trivial T0 deviation,
matches 2a/2b). **All 9 tasks (0–8) done, atomic commits; tree clean** (only the owner's
`.vscode/settings.json` unstaged). **`.github/workflows/ci.yml` live** — 4 independent jobs (no `needs:`):
`frontend` (npm ci→lint→tsc -b→vitest→build, Node 22), `backend-lint` (`ruff check .`, Py 3.13),
`backend-tests` (`pytest -q` vs a live `postgres:17` service — **232 passed / 0 skipped**; conftest
self-provisions `biznice_test`), `verify-scripts` (migrate+seed `biznice`, then the **14 non-API
`verify_*` — 14/14 exit 0**; glob excludes `*_api.py`). **All 6 SCs proven on REAL Actions runs:**
all-green **run 30140504003** (SC1/2/5); broken test → **30140642516** red (only `backend-tests`) →
revert **30140733237** green (SC3); lint violation (ruff F401 + eslint no-unused-vars) → **30140870255**
red (`backend-lint`+`frontend`) → revert **30140959653** green (SC4); **PR #4 → `master`** required-status
gated — four checks green, PR **BLOCKED→CLEAN**, branch protection `contexts=[frontend, backend-lint,
backend-tests, verify-scripts]` (SC6); final wrap-up **run 30141201881** all-green. **Two build deviations:**
(1) **MATERIAL → owner, D-P3-4** — the plan's "pytest self-provisions from a bare postgres" was wrong on a
*fresh* server: conftest's reachability probe hit the not-yet-created `biznice_test` and aborted before
provisioning (2a/2b "232 passed" only worked because the DB persisted locally); owner chose to fix the probe
to target the maintenance `postgres` DB (test-infra only, no `backend/app/` change) — verified fresh
`postgres:17` self-provisions → 232/0. (2) **build correction** — the plan's verify-scripts recipe omitted
`PYTHONPATH` (scripts do `from app…`) and the **seed step** (scripts need the app-lifespan CoA seeds — "GL
account 5100 not seeded" otherwise); added both. **Noticed:** Node-20 action-deprecation warning
(cosmetic); duplicate check runs per PR (both `push`+`pull_request` fire for a same-repo branch) — Phase 4+
scoping nicety. Checklist `docs/tasks/chore-ci-pipeline.md` (all 9 ticked; archive at finish/ship). SRD NFR-4
→ **done (pending `/zj:verify 3`)**, requirements-progress NFR-4 row + footer added, D-P3-4 recorded. **PR #4
left OPEN — merge is out of scope** (Phase 3 delivers the demonstrated blocking pipeline, not the merge).
**Next action:** `/zj:verify 3`.)

Prior: 2026-07-24 (**v4.0 Phase 3 PLANNED — `/zj:plan 3`.** Phase 3 = **CI pipeline (GitHub
Actions, NFR-4, D-M4-2)** — every push/PR runs a blocking pipeline: ruff + eslint + `tsc -b` +
vitest + `npm run build` + `pytest`-against-live-`postgres:17` (0 silent skips, 232 passed) + a
**service-layer `verify_*` regression job** (the D-P2a-2 concurrency-proof CI home). **9 tasks**
(`.zj/phases/03-ci-pipeline/PLAN.md`), sequential (one shared `ci.yml` + live-demo deps): T0 branch
cut → T1 frontend+backend-lint jobs → T2 backend-tests job → T3 verify-scripts job → T4 push+prove
all-green → T5 broken-test-red → T6 broken-lint-red → T7 real PR→master + required-status branch
protection → T8 flip NFR-4 → done. **3 owner decisions (AskUserQuestion, all Rec.) → D-P3-1..3:**
(1) CI runs the **14 non-API `verify_*` only** (the 9 `*_api.py` need a booted uvicorn; their
RBAC/audit was ported to pytest in 2b — redundant); (2) backend runner = **setup-python@3.13 + pip
+ `postgres:17` service** (not a baked image — matches conftest's documented localhost invocation,
self-provisions `biznice_test`); (3) **full live demo + branch protection** (gh authed as
`badLifeChoizes`; owner-authorized outward push of the unmerged stack's branch). **DB-naming risk
resolved:** pytest self-creates/migrates `biznice_test` off the maintenance `postgres` DB; the
non-API `verify_*` assume a pre-migrated `biznice` and self-create nothing → **separate jobs, each
its own `postgres:17` service** (verify job sets service `POSTGRES_DB=biznice` + runs `alembic
upgrade head` first). Secrets are test-only throwaway `env:` values (no repo Secrets). No
`## Decisions needed` open; plan checked goal-backward (every SC → ≥1 task, every task → SC + NFR-4,
real files + runnable verify). **Branch (D-P3):** fresh `chore-ci-pipeline` off the 2b tip
`chore-port-verify-cruxes` HEAD (`4960d32`) so the repaired harness + ported cruxes are present for a
meaningful `pytest` run; unmerged v4.0 stack. **Next action:** `/zj:build 3`.)

Prior: 2026-07-24 (**v4.0 Phase 2b RETRO'D — `/zj:retro 2b`. Phase closed `[done]`.** Roadmap
Phase 2b flipped `[verified]` → `[done — verified + retro'd]`. **LEARNINGS Phase 02b banked (2
surprises + 2 repeats):** (1) *a crux whose arithmetic divides evenly can't guard its own advertised
mutation* — the wrong formula yields the right number (MOUSSE 210/10), so the residual sibling
(100/3) is the real red-on-revert guard; pick indivisible-remainder fixtures or the happy-path test
is decorative; (2) *the SC2 mutation table is the highest-signal audit artifact* — the one real
defect surfaced from reading its claims against the arithmetic, not from re-running (a green suite
hides a vacuous test); (repeat) lift the `verify_*` fixture builders + independent oracles verbatim;
(repeat) spend known keepers (drive-the-real-flow D-P2b-5) at plan time, not after a bug. **Deferred
→ BACKLOG p2:** CRUMB `crumb_lead`/`crumb_opportunity` latent TRUNCATE-skip (FK cycle drops them from
`sorted_tables`; mitigated this phase, will bite the first ported test that touches
leads/opportunities). Nothing changed the roadmap picture — Phase 3 (CI, NFR-4) unchanged. **Next
action:** `/zj:plan 3` (CI pipeline — ruff + eslint + `tsc -b` + vitest + `npm run build` + `pytest`
on push/PR, NFR-4, D-M4-2). Optional: `/zj:log phase 2b` to file the formal work log. Verify detail
in the prior entry below.)

Prior: 2026-07-24 (**v4.0 Phase 2b VERIFIED — `/zj:verify 2b`. Verdict PASS**, tag
`zj/good-02b-port-verify-cruxes`. Verifier + reviewer ran in parallel, both **empirically** (not
trusting the build report): all 6 SCs PASS — verifier ran the full suite twice in-container
(**232 passed / 0 skipped** both runs), read all 7 crux tests (each headline Decimal asserted via
the REAL service path against an independent oracle anchored to a literal), independently re-drove
**3/7 SC2 mutations** (inventory/CRUMB/GELATO — each flips a NAMED pytest test RED, all reverted,
`backend/app/` clean), 23/23 `verify_*` exit 0, ruff exit 0, cold boot ok, `git diff -- backend/app/`
**empty** (TEST-ONLY honored), NFR-5 caveats dropped + D-P2b-1..6 recorded (SC6). **Reviewer: 0
blocker / 0 major / 1 minor** — MOUSSE happy-path `test_wip_clears_to_zero_crux` divides evenly
(210/10) so the documented WIP credit-source mutation leaves it green; its SC2 regression guard is
the sibling residual test `test_under_issue_override_clears_wip_and_ties_subledger` (100/3), which
DOES flip RED — the crux stays protected. **Fix loop (minor, `0cb625f`, docstring-only):** corrected
the file-header red-on-revert claim to point at the (D) test, confirmed no sequential `verify_*`
assert was dropped under D-P2b-2, logged both to `## Noticed`; MOUSSE file re-run green (2 passed).
SRD NFR-5 stamped `- **Verified (2b portion):** 0cb625f`; ROADMAP Phase 2b → `[verified]`; artifacts
`VERIFICATION.md` + `REVIEW.md` committed. **Next action:** `/zj:retro 2b` (bank the
"a crux that divides evenly can't guard its own residual mutation — the residual sibling is the real
guard" keeper) or `/zj:plan 3` (CI pipeline, NFR-4). Full build detail in the prior entry below.)

Prior: 2026-07-24 (**v4.0 Phase 2b BUILD COMPLETE — `/zj:build 2b`.** All 17 tasks on branch
`chore-port-verify-cruxes` (off `3f71900`); TEST-ONLY, **`git diff -- backend/app/` empty**. The DoD-named
`verify_*` cruxes now run inside the ordinary `pytest` suite (7 new service-layer crux files + 5 HTTP
audit/RBAC files + shared `seeded_ledger_db` fixture); **SC2 non-vacuity proven** — 7 product mutations each
flip a NAMED pytest test RED, all reverted. Gates: **full suite 232 passed / 0 skipped ×2**, 23/23 `verify_*`
exit 0, ruff exit 0, cold boot ok, `test_harness_selfcheck` green. SRD NFR-5 → **done**, D-P2b-1..6 recorded,
requirements-progress NFR-5 row added. Engineers serialized (shared `biznice_test` DB). **Next action:**
`/zj:verify 2b`. Full task/commit detail in the `## Position` build-complete entry below.)

Prior: 2026-07-24 (**v4.0 Phase 2b PLANNED — `/zj:plan 2b`.** Phase 2b = **port the DoD-named `verify_*`
cruxes into the repaired pytest suite** (NFR-5, the 2b half of the D-P2a-2 split) so reverting a crux turns
a *pytest* test RED, not only a `verify_*` script. **17 tasks** (`.zj/phases/02b-port-verify-cruxes/PLAN.md`),
3 waves: **A** (Tasks 1–8) = one NEW service-layer test file per crux — inventory moving-avg SERVICE path,
GL/AP/AR posting ties, MOUSSE WIP-clears (+1130↔subledger+5190), CRUMB reservation math, GELATO ship-COGS —
plus a shared opt-in `seeded_ledger_db` fixture (the repaired `_isolate` truncates the CoA/location every
test, seeds auth only); **B** (Tasks 9–13) = one HTTP audit/RBAC test per NEW module surface
(MOUSSE/CRUMB/GELATO/AR) + inventory, driving the `client` fixture for 401/403/2xx + attributable `AuditLog`;
**C** (Tasks 14–16) = per-crux non-vacuity sweep (7 documented product mutations each flip a NAMED pytest RED,
then revert — `git diff -- backend/app/` empty), full-suite 0-skip ×2 + 23/23 verify_* still-green + selfcheck +
cold boot, then drop the SRD "script-only" caveats (NFR-5 → done) + `requirements-progress`. **TEST-ONLY phase**
— zero product-code change expected; a surfaced product bug gets a minimal flagged fix, a schema/Alembic need
STOPS-and-flags. **Owner calls at plan (3 AskUserQuestion):** (1) **single phase 2b** (no sub-split — each crux
is a bounded sequential assertion, no concurrency to port); (2) coverage depth = **headline + key supporting
asserts** per crux (control↔subledger EQUALITY, negative-path rejects — not a full re-port, not minimal-only);
(3) audit/RBAC = **one HTTP test per NEW module** + inventory (rest service-layer). Concurrency mutation-proofs
STAY in `verify_*` (D-P2a-2). **6 decisions D-P2b-1..6** (owner 1–3 + architect: local RBAC identities not the
shared roster; AR fixture drives the REAL ship flow — the 11a/11b dead-through-UI keeper; new test files leave
the pure ones untouched) captured in PLAN `## Decisions`, recorded to DECISIONS.md at Task 16. No
`## Decisions needed` open; plan checked goal-backward (every SC → ≥1 task, every task → an SC + NFR-5, real
files + runnable `pytest` verify). **Branch (D-P2b):** build on a fresh `chore-port-verify-cruxes` off the
current `chore-pytest-harness-repair` tip `f97b21a` (retro docs atop verified 2a code `14d838b`, tag
`zj/good-02a-pytest-harness-repair`); unmerged v4.0 stack. **Next action:** `/zj:build 2b`.)

Prior: 2026-07-22 (**v4.0 Phase 2a RETRO'D — `/zj:retro 2a`. Phase CLOSED, ROADMAP `[done — verified]`.**
Banked **LEARNINGS Phase 02a** — 5 keepers: (repeat) pre-decide the *mechanism* not just the diagnosis
when repairing already-diagnosed infra (D-P2a-1 locked the isolation model before a line was written →
zero Wave-A surprises); parallel empirical verifier+reviewer converged on the same design seam (no-DB
contradiction). (surprises) **"all 6 SCs PASS" ≠ phase done** — first-pass green still needed 1+2+2 fixes,
because SCs measure *works now* not *stays working/self-consistent*; **a phase fixing "X silently passes"
MUST ship a test that goes RED when X regresses** — else the exact bug recurs invisibly (the reason
`test_harness_selfcheck.py` exists); **an autouse fixture needing a resource silently makes it mandatory**
and turns any graceful-degrade path into dead code (→ DB is a hard requirement, `skip_if_no_db` retired);
**`"python"` isn't on PATH on standard Debian/CI → `sys.executable`**. Truing-up: the **p1 BACKLOG item
"PLUM live-DB test harness never runs" → RESOLVED + checked off** (2a paid this exact debt); two residual
harness checks (back-to-back rerun automation; committed non-vacuity) folded p3 into the CI backlog item,
their natural home. No roadmap resize — 2b and Phase 3 (CI) stand as-is. **Next action:** `/zj:plan 2b`
(port the DoD-named `verify_*` cruxes into the repaired suite) — the harness it needs is now green. Optional:
`/zj:log phase 2a` to file the formal work log.)

Prior: 2026-07-22 (**v4.0 Phase 2a VERIFIED — `/zj:verify 2a`. Verdict PASS**, tag
`zj/good-02a-pytest-harness-repair`. Verifier + reviewer ran in parallel, both **empirically** (not
trusting the build report): all 6 SCs PASS — full suite **217 passed / 0 skipped twice back-to-back**
(SC4/SC5), `git diff zj/good-01..HEAD -- backend/app/` **empty** (the "zero product-code changes" claim
is TRUE — RBAC test rewrites are genuine strengthenings, not force-green), non-vacuity **re-driven**
(`partners.py is_vendor=False` → `test_create_vendor` RED → revert GREEN, tree clean), 23/23 `verify_*`
exit 0, cold boot `boot-ok`, `biznice_test` migrated head 0017 with live `biznice` intact, no hard-coded
host. **Fix loop closed 1 verifier major + 2 minors + 2 reviewer majors** (commit `a2bb5a6`, TEST-ONLY):
(1) provisioning shelled out to a bare `python` (absent on standard Debian/CI hosts → `FileNotFoundError`
aborts the session, defeating SC6) → `sys.executable`; (2) **owner decision — DB is now a HARD
REQUIREMENT**: no-DB runs `pytest.exit` loud instead of silently skipping; `skip_if_no_db` retired to a
documented no-op alias (avoids a 28-file param-strip); docstrings de-staled; (3) **new
`tests/test_harness_selfcheck.py`** asserts `db_available() is True` so a re-introduced DSN break fails
loud not skips — pins the phase's own zero-silent-skip invariant (verifier's "central deliverable
unprotected" major); (4) SRD NFR-5 → `partial (2a done/2b pending)` stamped `a2bb5a6`, MAP.md test row
de-staled. **Re-verified after fix: full suite 219 passed / 0 skipped** (217 + 2 self-check), ruff exit
0, cold boot ok. SRD NFR-5 stamped; ROADMAP Phase 2a → `[done — verified]`. **Next action:** `/zj:retro
2a` (bank the fix-loop learnings — the silent-skip-invariant-needs-its-own-test keeper + the
DB-hard-requirement decision), or `/zj:plan 2b` (port the `verify_*` cruxes). 2b porting stays deferred.)

Prior: 2026-07-21 (**v4.0 Phase 2a PLANNED — `/zj:plan 2`.** Phase 2 (NFR-5, pytest harness repair)
**split 2a/2b** at plan (owner, D-P2a-2 — mirrors 9a/b/c & 11a/b). **This plan = 2a only:** repair the
harness so the ~100 already-written-but-silently-skipped auth/plum/syerp/core DB-backed tests RUN
0-silent-skip green, fixing the four D-P7-4 root causes. **2b** (separate later phase) ports the
DoD-named `verify_*` cruxes; the **concurrency mutation-proofs STAY in `verify_*`** (not ported, D-P2a-2)
— which is what keeps 2a's isolation model simple. **13 tasks** (`.zj/phases/02a-pytest-harness-repair/PLAN.md`),
3 waves: **A** = 4 root-cause fixes at the harness layer (SC1 DSN probe → libpq kwargs; SC2 NullPool
test engine resolving the app's `get_db`/`AsyncSessionLocal`; SC3+SC4 per-test TRUNCATE…RESTART IDENTITY
CASCADE + reseed on a dedicated `biznice_test` DB, incl. a seeded `User(id="admin-user")`); **B** = green
each package (auth/core/plum/syerp/root), triaging the LATENT breakage these never-run tests will surface
(fix or xfail-with-reason, no blanket skips); **C** = non-vacuity mutation proof + env-pointability (SC6,
in-container `db` AND CI localhost) + regression keepers (cold boot + 23/23 `verify_*` + full 0-skip suite).
**Owner calls at plan:** split 2a/2b; port depth = DoD-named set (2b); concurrency stays in `verify_*`;
isolation = dedicated-DB truncate-reset over savepoint (D-P2a-1, service layer commits pervasively).
**Architect recon de-risked SC3:** RBAC resolves permissions from the DB user, not the token claim
(`dependencies.py`), so tokens minted `subject="admin-user"` need a real `User(id="admin-user")` row
(D-P2a-4). No `## Decisions needed` open; D-P2a-1..4 recorded. **Branch (D-P2a-3):** `chore-pytest-harness-repair`
off `zj/good-01-lint-gates-clean` @ `dd401d1`; unmerged stack. **Next action:** `/zj:build 2a`.)

Prior: 2026-07-21 (**v4.0 Phase 1 RETRO'D — `/zj:retro 1`.** Phase closed `[done — verified +
retro'd]`; tag `zj/good-01-lint-gates-clean` stands. **3 LEARNINGS keepers banked** (LEARNINGS.md
"Phase 01"): (1) a lint plugin's `recommended` preset is a moving target across majors — pin the
major before scoping (react-hooks v7 `recommended` bundled the React-Compiler ruleset = 54 errors/42
behavior-sensitive; `^5` pin/D-P1-1 restored the classic 2-rule set); (2) autofix on a self-registering
modular monolith needs guard-first (`# noqa: F401` side-effect imports before `--fix`) + a cold-boot
gate (`import app.main`) — trust the boot, not the linter's "unused"; (3) re-derive the post-`--fix`
residual from `--statistics` (safe-fix left ~71, not the 18 hand-enumerated — map every rule category to
an owning task, none riding the backstop). **Deferred items homed:** SC4 enforce-smoke + `.npmrc`
global peer-masking → Phase 3 CI backlog item (BACKLOG:18); both stale-doc gaps already fixed at verify
close-out. ROADMAP Phase 1 → `[done]`. **Next action:** `/zj:plan 2` (NFR-5 pytest harness repair +
port `verify_*`). Optional: `/zj:log phase 1` for the formal work log.)

Prior: 2026-07-21 (**v4.0 Phase 1 VERIFIED — `/zj:verify 1`.** Verdict **PASS**, tag
`zj/good-01-lint-gates-clean`. Verifier + reviewer both ran **empirically** (not trusting the build
report): all 5 SCs pass — SC1 flat config/devDeps/deleted `.eslintrc.cjs`/fixed `lint` script wired
(print-config confirms rules loaded); SC2 `npm run lint` **exit 0**; SC3 `ruff 0.15.18 check .` **exit
0**; SC4 both gates' red→green enforce proof **re-run independently** (planted → exit 1, revert → exit
0, tree left clean); SC5 **23/23 `verify_*`** in-container + **Vitest 131/131** (the build's "44/131"
resolved to 44 files/131 tests, **0 fail/skip**) + `tsc -b && vite build` exit 0 + cold-boot `import
app.main` BOOT_OK. **Reviewer: 0 findings** — F401 import sets byte-identical in every load-bearing file
(only I001 reorder, `# noqa: F401` guards intact, full FK graph resolves), F821 via real `TYPE_CHECKING`,
`seeded_db` collapse scope-safe, `l`→`line` rename complete, removed F841 locals side-effect-free, 4
deleted exhaustive-deps disables genuinely stale. `npm ci --dry-run` exit 0 with tracked `.npmrc`.
**3 minor gaps, none undermine the goal — 2 fixed in the verify close-out:** stale `CLAUDE.md:72`
("lint gates non-functional") corrected; `BACKLOG.md:44` p1 item marked resolved (CI item stays open).
**Logged (not built):** SC4 has no standing automated enforce-test → deferred to Phase 3 CI (PLAN.md
`## Noticed`). SRD NFR-6 → **verified** + stamped `ee11674`; ROADMAP Phase 1 → `[verified]`; artifacts
`VERIFICATION.md`/`REVIEW.md` committed. **Next action:** `/zj:retro 1` (bank the D-P1-1 react-hooks-preset
+ F401-side-effect-guard lessons), then `/zj:plan 2` (NFR-5 pytest harness repair + port `verify_*`).)

Prior: 2026-07-21 (**v4.0 Phase 1 BUILD COMPLETE** — `/zj:build 1` on branch `chore-lint-gates-clean`
(cut off the plan-carrying tip `a6ee1fb`, code-identical to `origin/master`; Task-0 branch-point
deviation logged). **All 13 tasks (0–12) done, atomic commits, tree clean.** NFR-6 delivered: **both
lint gates fixed-to-clean + proven enforcing.** Wave A (frontend ESLint 10 flat gate): flat
`eslint.config.js`, `.eslintrc.cjs` deleted, `lint` de-`--ext`'d, `npm run lint` **exit 0**. Wave B
(backend `ruff` gate): ~1159 violations fixed-to-clean (1139 safe-autofix + F821×4 via `TYPE_CHECKING` +
F811 `seeded_db`→`tests/auth/conftest.py` + E741/F841 hand-fixed + 51 load-bearing `syerp/service`
re-exports `# noqa: F401`), `ruff check .` **exit 0**. Wave C: **23/23 `verify_*` exit 0** in-container +
**cold boot** (`/health/ready` 200, `import app.main` BOOT_OK) + Vitest **44/131** + `tsc -b && vite
build` exit 0; **red→green enforce proof** on both gates (planted violation → non-zero, revert → 0).
**One MATERIAL deviation → owner decision D-P1-1:** installed `eslint-plugin-react-hooks@7.1.1`
redefined `recommended` to bundle the React-Compiler ruleset (54 errors/41 files) — out of NFR-6 scope;
owner chose **pin to `^5`** (classic 2-rule recommended = plan intent). Added `frontend/.npmrc`
`legacy-peer-deps=true` (v5 peer-declares eslint≤^9) + re-declared `@testing-library/dom` — **both flagged
for NFR-4/Phase-3 CI** (`npm ci` must keep them). SRD NFR-6 → `implemented` (CI-wiring clause deferred to
NFR-4/Phase 3); `requirements-progress.md` NFR row added; checklist archived to
`docs/tasks/_completed/2026-07-21-chore-lint-gates-clean.md`. Unrelated `.vscode/settings.json` cosmetic
edit **stashed** at owner request (restore with `git stash pop`). **Noticed (non-blocking):** the
transient-red intermediate commit `e7c6e18` (testing-lib restored next commit; tip green); root
`tests/conftest.py` + `tests/core/conftest.py` predate the ABOUTME-header standard (future sweep).
**Next action:** `/zj:verify 1`.)

Prior: 2026-07-20 (**v4.0 Phase 1 PLAN COMPLETE** — `/zj:plan 1`. Phase 1 = **lint gates
fixed-to-clean (NFR-6)**; artifacts in `.zj/phases/01-lint-gates-clean/PLAN.md`. **13 tasks** (Task 0
branch + 12 work) in 3 waves — **A: frontend gate** (add `@eslint/js`/`eslint-plugin-react-hooks`/
`eslint-plugin-react-refresh`; write flat `eslint.config.js`; fix the `--ext`-broken `lint` script;
delete `.eslintrc.cjs`; fix to zero) · **B: backend gate** (ruff availability + convention; safe
`--fix`; audit/`# noqa`-guard side-effect imports FIRST; resolve the ~71 survivors — F821×4, F811/E741/
F841, UP035×~23, 2 unsafe) · **C: regression + enforce-proof** (23/23 verify_* in-container + Vitest +
build + **cold boot**; red→green gate proof; flip NFR-6 status). **Recon done at plan** (grounds the
scope): FE is near-clean already (`tsc -b` `noUnusedLocals`/`strict` keeps unused out; only 6
pre-existing `react-hooks/exhaustive-deps` disables, which prove react-hooks was the intended
ruleset) — deps `eslint@10.5.0`+`typescript-eslint@8.62.0` already installed, just no flat config;
BE has **1159 ruff violations, 1088 SAFE-auto-fixable**, config already committed in `pyproject.toml`
(E/F/I/UP), ruff pinned in `requirements-dev.txt` but absent from `.venv`/image. **Top risk (handled):**
blind F401 `--fix` could strip a load-bearing side-effect import (module self-registration /
`app/main.py` `import app.core.models`) and re-introduce the Phase-13 cold-boot 500 — sequenced as
audit-and-`# noqa`-first (Task 6) → review every deleted-import line (Task 7) → empirical cold-boot +
23/23 gate (Task 10). **3 owner decisions bound at plan:** D-M4-3 fix-to-clean (not ratchet);
**rule strictness = recommended sets only** (no tseslint recommendedTypeChecked, no ruff B/SIM/RUF);
**formatter scope = lint-check only** (no `ruff format`/`prettier --check`; E501 stays ignored).
No `## Decisions needed` open (one conditional escalation: if an F821 is a real runtime bug, stop +
surface). **Branch:** cut fresh `chore-lint-gates-clean` off `origin/master` (current
`feature-syerp-ar-invoicing` is fully merged, 0 ahead; it may be deleted). **Next action:**
`/zj:build 1`.)

Prior: 2026-07-20 (**v3.0 SHIPPED to master** — `/zj:ship`. The 11a→13 stack (135 commits) merged to
`master` via **PR #3**, fast-forward `3b762ba..87fb79d` preserving SHAs (same known-good pattern as v2.0's
PR #2) — `origin/master == 87fb79d`, PR #3 MERGED, all `zj/good-*` tags + annotated `v3.0` (→`e92b91d`)
pushed and reachable from master. **The standing `/zj:ship` master-merge debt is now CLEARED** (it had
carried since v2.0). Preflight was a fresh green on the branch tip: **23/23** live `verify_*` exit 0 +
**131/131** Vitest / 44 files + `npm run build` exit 0 (lint gates still non-functional, BACKLOG p1 — the
v4.0 headline). Changelog already carried v3.0 (generated at milestone close); `.zj/` + `docs/tasks/`
artifacts shipped in the merge per repo convention.

**v4.0 "Infra-debt + quality paydown" SPEC'D** (`/zj:spec`, 2026-07-20) — DoD confirmed into 5 clauses,
**NFR-4..8** written under new **PRD-12** (trustworthy engineering baseline; no new end-user capability).
Scope (D-M4-1, owner): NFR-4 CI (GitHub Actions, D-M4-2) + NFR-5 pytest-harness repair & `verify_*`
ported into the suite + NFR-6 both lint gates fixed-to-clean (D-M4-3) + NFR-7 shared inventory
FOR-UPDATE lock & inbound bin-blind fix + NFR-8 human UAT; **CRISP/offline deferred.** Proposed 5-phase
mapping in ROADMAP (lint → harness → CI → race-safety → UAT; dependency-first). Owner note: asked what
"CI" was → confirmed the milestone hardens the foundation, adds nothing users click. **Next action:**
`/zj:plan 1` (Phase 1 = lint gates fixed-to-clean, NFR-6). Post-merge housekeeping: delete the merged
`feature-syerp-ar-invoicing` branch when Phase 1 branches off master.

Prior: 2026-07-19 (**Milestone v3.0 "Customer & logistics" CLOSED + tagged `v3.0`** — `/zj:milestone`
done. DoD audited goal-backward (`.zj/MILESTONE-v3.0-AUDIT.md`): the WHOLE money loop driven on ONE
sales order end-to-end (order→reserve→pick→pack→partial-ship→invoice-from-shipment→post→partial+full
receipt→auto-Paid), all 3 clauses MET, 19/19 + 23/23 live `verify_*` + build + 131 Vitest. **Two gaps
found, BOTH FIXED at close (owner, D-M3-1/2, `97b977b`):** GAP-1 (AR aging falsely tripped a negative
1120 tie-out when a receipt predated its invoice_date — prepayment reclassified in `ar_aging_report`,
pinned by `verify_ar` scenario G, load-bearing) + GAP-2 (invoice picker bare UUID → resolved
`item_label`). **Records:** CHANGELOG v3.0 + milestone-close fixes, `.zj/logs/milestone-v3.0.md`
(130 commits, ~14.6h/10 sessions), LEARNINGS `## Milestone v3.0` (headline: review-not-verify caught
the defect on all 5 phases), DECISIONS D-M3-1..4 + index regenerated 73→134. Phases 11a/11b/12a/12b/13
archived to `.zj/history/v3.0/`. **Next milestone = v4.0 Infra-debt + quality paydown (D-M3-3).**
**Next action:** `/zj:spec` (sharpen the v4.0 DoD into clauses) then `/zj:plan 1`. Optional: `/zj:ship`
to merge the 11a+11b+12a+12b+13 stack to master.

Prior: 2026-07-19 (**Phase 13 RETRO'D** — `/zj:retro 13`. Roadmap already marked
`[done — verified 2026-07-19]`; no future phase resized. **LEARNINGS Phase 13 banked (1 surprise +
3 patterns):** (1) **the headline — mirroring a broad `except IntegrityError → retry` is only sound
if the mirrored fn can't raise a *different* IntegrityError, and adding a nullable FK the exemplar
lacks silently breaks that** (`create_invoice` copied `create_bill`'s number-collision retry but also
took an unvalidated `sales_order_id` FK → a bad id raised an FK error the retry misread as a collision
→ unbounded recursion/500; keeper = narrow the except to the specific constraint + bound it, AND
up-front-validate every FK the mirror doesn't have); (2) **a mandated adjacent-untouched-surface
regression assertion caught a real production-boot 500** the phase that introduced it (12a) had
mislabeled a "dev-only `--reload` race" — the `syerp_inventory_txn.bin_id→gelato_bin` metadata gap,
fixed by importing `app.core.models` at boot; keeper = the "assert the neighbour still works" task is
the only gate that exercises a cold process like production; (3) **dead-through-UI trap caught in-build
a 2nd straight phase** (`qty_invoiced`) — counter-measure now reliable; (4) **5th consecutive phase
where the review, not the verify suite, caught the defect that mattered** — budget both every phase.
Deferred items homed → BACKLOG p3: invoice void/credit-memo functional gap, dead `partially_paid` FE
badge, late-invoice COGS/revenue period split. **Phase 13 was the FINAL v3.0 phase (DoD clause 3
closed) — v3.0 milestone is now complete pending close-out.** Artifacts:
`.zj/phases/13-syerp-ar-invoicing/{PLAN,VERIFICATION,REVIEW}.md`, `.zj/LEARNINGS.md` Phase 13.
**Next action:** `/zj:milestone` (audit the v3.0 DoD, tag the release, archive phases 11–13, roll the
roadmap to the next milestone). Optional: `/zj:log phase 13` (formal work log); `/zj:ship` to merge the
11a+11b+12a+12b+13 stack to master.)

Prior: 2026-07-19 (**Phase 13 VERIFIED** — `/zj:verify 13`, tag `zj/good-13-syerp-ar-invoicing`.
Both checks ran in parallel; all 7 SYERP-13 success criteria PASS empirically — `verify_ar.py` 17/17
+ `verify_ar_api.py` 29/29 + **23/23 full regression**, aging ties Decimal-exact to the debit-normal
1120 (no negation), TB nets zero WITH AR posted, BS balances, RBAC 401/403/200 on all 8 routes,
attributable audit rows; verifier mutation-proved the record_receipt lock (revert `for_update` →
over-collected 120/100). **Fix loop landed 1 REVIEW MAJOR + 3 doc gaps:** `create_invoice` took a
client-supplied nullable `sales_order_id` FK **unvalidated** → a bad id failed only on the header flush,
was misread as an invoice-number collision, and **recursed forever** (RecursionError/500); fixed with
up-front 404 validation + a one-attempt-bounded retry (`7610e63`), pinned by new `verify_ar.py` scenario
**(D2)** (bogus id → clean 404, persists nothing); doc gaps closed — SYERP-13 row added to
`requirements-progress.md`, SRD:478 flipped `planned`→`verified` (stamped `7610e63`), MAP migration head
refreshed `0012`/`0014`→`0017`. Closes v3.0 DoD clause 3 (the FINAL v3.0 phase). Artifacts:
`.zj/phases/13-syerp-ar-invoicing/{VERIFICATION,REVIEW}.md`. **Next action:** `/zj:retro 13` (banks the
mirror-exemplar-shares-no-FK-surface + unvalidated-FK→unbounded-retry learnings), then v3.0 milestone.)

Prior: 2026-07-19 (**Phase 13 BUILD COMPLETE** — `/zj:build 13` on fresh branch
`feature-syerp-ar-invoicing` (cut off the code-identical 12b tip carrying the plan; a bare-tag branch
would have dropped the plan — 12a/12b precedent). **All 18 tasks shipped**, SYERP-13 AR & sell-side
books end-to-end; **v3.0 DoD clause 3 closed**. Wave A: Invoice/InvoiceLine + Receipt/ReceiptAllocation
models + `qty_invoiced` accumulator on `crumb_sales_order_line` (dead-through-UI keeper: model→schema→FE
render→Vitest) + migration **0017** (clean up/down round-trip) + AR schemas. Wave B: `service/ar.py`
(`create_invoice` FOR-UPDATE lock on SO-line rows + price locked to SO `unit_price` + stamps qty_invoiced;
`post_invoice` → **Dr 1120 / Cr 4110** JE `entry_date=invoice_date`; `record_receipt` FOR-UPDATE lock on
invoice rows + reused `bills._is_overpayment` + **Dr cash / Cr 1120** JE + auto-Paid at zero) + `ar_aging_report`
(**NO negation** — 1120 debit-normal) + thin RBAC router `/syerp/ar/*` audit-after-commit. Wave C:
`verify_ar.py` **16 asserts green** — end-to-end tie-out (asserts the 12b COGS-on-ship JE, does not rebuild),
aging **grand_total == 1120 control Decimal-exact**, over-invoice/over-receipt 422, and **BOTH concurrency
locks mutation-proven** (revert record_receipt lock → 120-vs-100 over-collect; revert create_invoice lock →
joint 12-vs-10 over-invoice + qty_invoiced lost-update; restore → one success/one 422) — the 12b "only the
guard under test can reject" discipline honored; `verify_ar_api.py` **29 asserts** (HTTP 401/403/200 triad on
all 8 routes + attributable audit + inventory-receipt regression lock); **full regression 23/23 green**, TB
nets zero, BS balances. Wave D: Invoices list/create-from-shipment/detail + Receipts + AR Aging screen + nav +
routes; FE **44 files / 131 tests green**, `npm run build` exit 0. **Two material handlings, both fixed:**
(1) the AR `ReceiptCreate` schema (Task 5) **shadowed** the inventory costed-receipt `ReceiptCreate`, silently
breaking `POST /inventory/items/{id}/receipts` → renamed to `ArReceiptCreate`, regression-locked in
verify_ar_api; (2) the Task-13 regression assertion surfaced a **pre-existing 12a production 500** —
`syerp_inventory_txn.bin_id → gelato_bin` FK unresolvable on a fresh process (lazy gelato model imports +
importlib registration) → fixed in `main.py` by importing the `app.core.models` aggregator at boot
(**D-P13-8**; D-P12a-3 preserved). Plus a phantom-`partially_paid` docstring corrected (real FSM is
draft→posted→paid). Lint gates still non-functional (BACKLOG p1); correctness rests on verify_* (23/23) +
Vitest (131). Checklist (all 18 ticked): `docs/tasks/feature-syerp-ar-invoicing.md`. **Next action:**
`/zj:verify 13`.)

Prior: 2026-07-19 (**Phase 13 PLAN COMPLETE** — `/zj:plan 13` on branch
`feature-gelato-pick-pack-ship` (planning artifacts; build branches fresh). **Phase 13 = SYERP-13 AR &
sell-side books, the FINAL v3.0 phase** — closes v3.0 DoD clause 3. **Single phase** (owner, D-P13-1 — not
sub-split; AR aging is a thin copy of AP aging, TB/P&L/BS already exist from 9c). **18 tasks in 4 waves**
(`.zj/phases/13-syerp-ar-invoicing/PLAN.md`): Wave A schema (Invoice+InvoiceLine, Receipt+ReceiptAllocation
models mirroring Bill/Payment, `qty_invoiced` accumulator on `crumb_sales_order_line`, migration **0017**,
schemas) → Wave B service (`service/ar.py`: uninvoiced-shipments query, `create_invoice`, `post_invoice`
→ Dr 1120 AR/Cr 4110 Revenue JE, `record_receipt` + allocations + FOR-UPDATE guard → Dr cash/Cr 1120 JE +
auto-Paid; `ar_aging_report` in reports.py; thin RBAC router `/syerp/ar/*` audit-after-commit) → Wave C
verify (`verify_ar.py` control-tie + invoice-from-shipment match + overpayment reject + COGS-on-ship tie +
**two load-bearing concurrency scenarios** — over-receipt AND double-invoice, both mutation-proven;
`verify_ar_api.py` HTTP RBAC/audit; full regression + TB nets zero) → Wave D frontend (Invoices
list/create-from-shipment/detail, Receipts, AR Aging screen + nav; Vitest asserts real payload shape incl.
`qty_invoiced` render). **Key facts:** COGS-on-ship JE (Dr 5100/Cr 1130) **already shipped in 12b** —
Phase 13 asserts it, doesn't rebuild (D-P13-3); invoice price **locks to SO-line `unit_price`** (owner,
D-P13-2); `qty_invoiced` claimed at draft-create mirroring AP (D-P13-5); AR aging control-tie has **NO sign
negation** (1120 debit-normal — top risk, D-P13-7). All 5 recurring keepers baked in (concurrency-from-start
with the 12b "only the guard under test can reject" fixture discipline, subledger↔control as EQUALITY not
zero, dead-through-UI field wired end-to-end in Task 3, non-optional HTTP audit/RBAC script, full regression
gate). Decisions D-P13-1..7 recorded; no `## Decisions needed` open; plan checked goal-backward at manager
review (every SC → ≥1 task, every task → an AC, real files + runnable verify). **Branch (D-P13-6):** build
on a fresh `feature-syerp-ar-invoicing` off tag `zj/good-12b-gelato-pick-pack-ship` (`553bcfb`); migration
0017. **Next action:** `/zj:build 13`.)

Prior: 2026-07-19 (**Phase 12b RETRO'D** — `/zj:retro 12b` on branch
`feature-gelato-pick-pack-ship`, tag `zj/good-12b-gelato-pick-pack-ship` over `553bcfb`. Roadmap
marked `[done — verified + retro'd]`; **CRUMB→GELATO outbound loop complete** (v3.0 DoD clause 2 closed).
**LEARNINGS Phase 12b banked (4 keepers):** (1) **the headline — a forced-interleave concurrency test can
pass for the WRONG reason and mask the exact bug it targets**: scenario g's staging bin was seeded to
*exactly* the ship qty, so `post_issue`'s floor guard (a *bystander* guard) rejected the duplicate while
the real defect — an UNLOCKED shipment-status FSM gate letting two ships of one packed shipment double-post
COGS — sailed through untested; keeper = build concurrency fixtures so ONLY the guard under test can reject
(scenario h: order 10 ship 5, ample staging, only the shipment-row lock can 409 the duplicate; mutation-proven);
(2) **mirroring an exemplar's lock is safe only if your transition shares its safety property** — MOUSSE
`issue_components`' status-before-lock shape is safe because issuing is *repeatable*; ship is a *one-shot
terminal* transition, so the copied item locks are necessary-but-not-sufficient — the fix locks the Shipment
row (`SELECT … FOR UPDATE`) before the FSM gate; (3) **the dead-through-UI trap was caught IN-BUILD this time**
(qty_shipped serialization on `SalesOrderLineRead`) — the counter-measure works; (4) **parallel
verifier+reviewer, reviewer-blocker-overrides-PASS, is load-bearing 4 phases running** (11a/11b/12a/12b).
Deferred items all homed at verify, trued up at retro: pick-path races Q1/Q2 → BACKLOG p2; bin-blind-desync
p2 **outbound half now closed** (inbound `post_transfer`/`post_adjustment`/MOUSSE-issue still open); downgrade
test → p3. Artifacts: VERIFICATION.md + REVIEW.md + LEARNINGS.md Phase 12b. **Next action:** `/zj:plan 13`
(SYERP-13 AR + invoice-from-shipment + customer receipts + AR aging tie-out — closes v3.0 DoD clause 3).
Optional: `/zj:log phase 12b` (formal work log); `/zj:ship` to merge the 11a+11b+12a+12b stack.)

Prior: 2026-07-19 (**Phase 12b VERIFIED** — `/zj:verify 12b` PASS on branch
`feature-gelato-pick-pack-ship`, tag `zj/good-12b-gelato-pick-pack-ship` over `553bcfb`. Verifier +
reviewer ran in parallel; the **reviewer caught a BLOCKER the verifier's concurrency test masked**:
`execute_ship` gated on an UNLOCKED shipment status and locked only the `InventoryItem` rows, so two
concurrent ships of ONE packed shipment could both pass the FSM gate → **double inventory issue +
double Dr 5100 / Cr 1130 COGS JE + double reservation relief**. Scenario g missed it (its staging bin
held exactly the ship qty, so `post_issue`'s floor guard incidentally rejected the duplicate). **Fixed**
(`553bcfb`): load the shipment `SELECT … FOR UPDATE` before the FSM gate. **New durable test**
`verify_gelato_ship.py` scenario (h) — one packed shipment partially fulfilling its SO (order 10, ship 5)
shipped twice concurrently; mutation-proven (reverting the lock → 2 JEs / qty_shipped 10 / staging drawn
twice). Full regression re-run **21/21 verify_* exit 0**, TB nets zero WITH the ship COGS JE, 1130 ties
to subledger; `verify_gelato_ship.py` **21/21**, `verify_gelato_ship_api.py` **23/23**. Two lower-severity
pick-path shipment-header races (review Q1/Q2) → BACKLOG p2; migration-downgrade automated-test gap → p3;
all recorded in PLAN `## Noticed`. Closes v3.0 DoD clause 2 (warehouse fulfillment outbound). Artifacts:
VERIFICATION.md + REVIEW.md in the phase dir. **Next action:** `/zj:retro 12b` (banks the "review catches
what the verifier's own test masks" keeper + the same-shipment-lock class) then `/zj:plan 13`.)

Prior: 2026-07-18 (**Phase 12b BUILD COMPLETE** — `/zj:build 12b` done on branch
`feature-gelato-pick-pack-ship` (cut off the 12a docs-on-top tip `bde5b77`, code-identical to tag
`zj/good-12a-gelato-bins-putaway`, D-P12b-8). **All 15 tasks shipped**, GELATO outbound pick → pack →
ship end-to-end. Wave A: migration **0016** (Shipment + ShipmentLine tables, `qty_picked`/`qty_shipped`
on `crumb_sales_order_line`) round-trips clean; shipment schemas. Wave B: NEW SYERP bin-aware
`post_issue` (single signed `issue` leg, item-master FOR-UPDATE before floor read); GELATO
`service/shipments.py` pick (net-zero pick-bin→staging via `post_putaway`, stamps qty_picked, SO
confirmed→fulfilling) / pack (FSM picking→packed, partial-pack trims staged qty) / **ship** (bin-aware
`post_issue` from staging + ONE balanced **Dr 5100 COGS / Cr 1130 Inventory** JE atomic via single
`db.commit()`, relieves qty_reserved + stamps qty_shipped, FSM→shipped); thin RBAC-gated router with
`write_audit(target_id=str(shipment.id))`. Wave C: `verify_gelato_ship.py` **22 asserts green**
(accounting crux Decimal-exact, reservation relief, partial-ship, negative space, control↔subledger tie,
**load-bearing concurrency Barrier — mutation-proven**) + `verify_gelato_ship_api.py` **23 asserts**
(HTTP 401/403/200 + attributable audit + int-PK target_id string guard); **full regression 19/19 green,
TB nets zero WITH the ship COGS JE, 1130 ties to subledger**. Wave D: shipment hooks + Fulfillment
pick→pack→ship screen + SO-detail Fulfill/Ship affordance; FE **38 files / 116 tests green**, `npm run
build` exit 0. **Three material handlings:** (1) `post_putaway` had no `commit` param → added
backwards-compatible `commit=True` so pick batches atomically (engineer correctly STOPPED, forced fix,
Deviations); (2) task-4 shipment FK schema fields mistyped `Optional[int]` → `Optional[str]` (String(36));
(3) **the recurring dead-through-UI trap CAUGHT** — SO-detail `qty_shipped` column rendered from a field
`SalesOrderLineRead` did not serialize → added `qty_picked`/`qty_shipped` to the read schema. Lint gates
remain non-functional (BACKLOG p1); correctness rests on verify_* (19/19) + Vitest (116), per project
convention. Noticed (non-blocking): belt-and-suspenders redundant ship locks; a dev-only `--reload`
FK-race on `syerp_inventory_txn.bin_id→gelato_bin` (production unaffected). **Next action:**
`/zj:verify 12b`.)

## Position

- **Step:** build — **v4.0 Phase 4 (inventory ledger race-safety, NFR-7) BUILD COMPLETE**
  (`/zj:build 4`, 2026-07-25). All 14 tasks done on `chore-inventory-race-safety` (T0 `378fb34` off
  the plan-carrying tip `7a71fd0`, code-identical to the D-P4-4 base `db725fd`); atomic commits
  `73e45c2`/`e1dc5c0` (locks), `4285202`/`b80cb37`/`455cf5c`/`4ae2b2c` (bin-aware + doc truth-up),
  `f394408` (verify_inventory_race.py, 4 mutations RED→GREEN), `ad6a35d` (scenario E), `2692b47`
  (sweep: 24/24 verify_*, pytest 232/0, zero reconciliations), `6d55d72`/`b270161`/`886193a` (FE
  pickers). Checklist archived. CI green on the pushed tip. **Next action:** `/zj:verify 4`.

- **Step:** retro — **v4.0 Phase 3 (CI pipeline, NFR-4) CLOSED** (`/zj:retro 3`, 2026-07-25; verified
  PASS 2026-07-25, tag `zj/good-03-ci-pipeline`, reviewer 0 findings). Branch `chore-ci-pipeline` off
  the plan tip `8a27a46`. `.github/workflows/ci.yml` with four independent blocking jobs proven green
  AND red on real Actions runs (all-green 30140504003; 232 passed / 0 skipped; 14/14 verify_*;
  broken-test red 30140642516; lint red 30140870255; each reverted green), required-status branch
  protection gating PR #4 → master. D-P3-4: conftest probe → maintenance `postgres` DB so a fresh CI
  Postgres self-provisions (test-infra only; product boundary clean). SRD NFR-4 verified. LEARNINGS
  Phase 03 banked; BACKLOG p1 CI item resolved, residuals → p3 "CI hardening niceties". PR #4 left
  open — merge via `/zj:ship`, out of phase scope. **Next action:** `/zj:plan 4` (NFR-7).

- **Step:** build — **v4.0 Phase 2b (port `verify_*` cruxes into pytest, NFR-5) BUILD COMPLETE**
  (`/zj:build 2b`, 2026-07-24). Branch `chore-port-verify-cruxes` cut off `3f71900` (the plan-doc
  tip carrying PLAN.md, not the bare `f97b21a` — trivial deviation, PLAN `## Deviations`). **All 17
  tasks (0–16) done, atomic commits, tree clean** (only owner's `.vscode/settings.json` unstaged).
  TEST-ONLY phase — **`git diff -- backend/app/` empty (zero product-code change).**
  **Wave A** (1–8, service-layer cruxes, 0 skips): scaffold+`seeded_ledger_db` (`521648f`),
  inventory moving-avg (`6a50420`), GL ties (`0ae185b`), AP GR/IR-clears (`0777467`), AR aging↔1120
  via REAL ship flow (`e589bbd`), MOUSSE WIP-clears+5190 (`0335fb0`), CRUMB reservation (`6a63194`),
  GELATO ship-COGS (`e7fcb3a`). **Wave B** (9–13, HTTP audit/RBAC per surface, 401/403/2xx +
  attributable AuditLog): MOUSSE (`6241fa3`), CRUMB (`beff018`/`56ae777`), GELATO int-PK
  (`0cadde4`), AR (`8cde0fe`), inventory receipt — new, no prior coverage (`13a27cf`). **Wave C**:
  SC2 non-vacuity — 7 product mutations each flip a NAMED pytest RED, all reverted, tree clean
  (`79b56e7`); regression — **full suite 232 passed / 0 skipped ×2**, 23/23 verify_* exit 0, ruff
  exit 0 (one I001 fixed `56ae777`), cold boot ok; SRD NFR-5 → **done**, D-P2b-1..6 recorded,
  requirements-progress NFR-5 row added (`15382ae`). Engineers serialized (shared `biznice_test`
  DB). Checklist: `docs/tasks/chore-port-verify-cruxes.md` (all 17 ticked). **Next action:**
  `/zj:verify 2b`.

- **Step:** plan — **v4.0 Phase 2b PLANNED** (`/zj:plan 2b`, 2026-07-24). 17 tasks / 3 waves in
  `.zj/phases/02b-port-verify-cruxes/PLAN.md`; TEST-ONLY. Owner decisions: single phase,
  headline+supporting depth, one HTTP audit/RBAC test per new module. Concurrency stays in
  `verify_*` (D-P2a-2).

- **Step:** verify — **v4.0 Phase 2a (pytest harness repair, NFR-5) VERIFIED — Verdict PASS**, tag
  `zj/good-02a-pytest-harness-repair`. All 6 SCs pass empirically; fix loop closed 1 major + 2 minors +
  2 reviewer majors (commit `a2bb5a6`, test-only — DB now a hard requirement, `sys.executable`,
  `test_harness_selfcheck.py` self-check); re-verified full suite **219 passed / 0 skipped**, 23/23
  `verify_*`, cold boot ok. **Next action:** `/zj:retro 2a` or `/zj:plan 2b`. (Prior build detail below.)

- **Step:** build — **v4.0 Phase 2a (pytest harness repair, NFR-5) BUILD COMPLETE** on branch
  `chore-pytest-harness-repair` (cut off `93de57d`, code-identical to `zj/good-01-lint-gates-clean`
  / `dd401d1`; Task-0 deviation to carry PLAN.md). **All 13 tasks (0–12) done, atomic commits, tree
  clean** (only the owner's `.vscode/settings.json` stays unstaged). **Headline: the ~100 never-run
  DB-backed tests now RUN — full suite 217 passed / 0 failed / 0 skipped on one shared DB, 167s.**
  Wave A fixed the four D-P7-4 root causes at the harness layer: DSN probe→libpq kwargs (`afa5798`);
  dedicated migrated `biznice_test` DB (head `0017`, app `biznice` untouched, `fe6a223`); NullPool test
  engine wired to the app's `get_db`/`AsyncSessionLocal` — no InterfaceError (`6ad45c9`); per-test
  `TRUNCATE … RESTART IDENTITY CASCADE` + reseed + seeded `User(id="admin-user")` (`871998c`). Wave B
  greened all packages — first run 32 failed, ALL triaged as TEST drift (zero product-code changes):
  auth 65 (`592faac`+`7ebf821`), core 13 (`3ce7394`), root (`52e7926`), plum 40 (`39d1ec0`), syerp 99
  (`b12d711`). **Owner decision D-P2a-5** (the never-run tests assumed claim-based tokens; shipped RBAC
  derives perms from the DB user): seeded a test-identity roster (min churn) + forced `BNS_ADMIN_*` creds
  + per-package domain-drift fixes. Wave C: non-vacuity proven (mutate `create_partner.is_vendor` →
  `test_create_vendor` RED → revert green, Task 10); env-pointability documented, no hard-coded host
  (SC6, Task 11); **regression gate green — cold boot `BOOT_OK` + 23/23 `verify_*` exit 0 + 217/0/0
  suite** (Task 12); ruff gate held (one auto-fixed I001). **No xfail/skip needed.** Container dev-deps
  install is ephemeral (bake a test image → Phase 3). **Next action:** `/zj:verify 2a`.
  Checklist: `docs/tasks/chore-pytest-harness-repair.md`.

- **Step:** milestone — **v3.0 "Customer & logistics" CLOSED + tagged `v3.0`** (`/zj:milestone`,
  2026-07-19). DoD audited goal-backward — whole money loop on one order end-to-end, all 3 clauses MET,
  19/19 + all 23 `verify_*` + build + 131 Vitest; 2 audit gaps BOTH fixed at close (D-M3-1/2, `97b977b`,
  pinned by `verify_ar` scenario G + FE tests). Records produced; phases 11a/11b/12a/12b/13 archived to
  `.zj/history/v3.0/`; roadmap + PROJECT rolled to **v4.0 Infra-debt + quality paydown (D-M3-3)**.
  **Next action:** `/zj:spec` (sharpen the v4.0 DoD into clauses) then `/zj:plan 1`. Optional:
  `/zj:ship` to merge the 11a+11b+12a+12b+13 stack to master.

- **(historical) Step:** **RETRO'D** — **Phase 13 (SYERP-13 AR & sell-side books — the FINAL v3.0 phase) closed
  2026-07-19** (`/zj:retro 13`), tag `zj/good-13-syerp-ar-invoicing`. Roadmap marked
  `[done — verified 2026-07-19]`; **v3.0 DoD clause 3 closed → v3.0 milestone complete pending close-out.**
  LEARNINGS Phase 13 banked (mirror-a-retry-only-safe-if-no-new-FK headline; adjacent-surface regression
  caught a real boot 500; in-build dead-through-UI catch a 2nd phase; review-caught-the-defect 5 phases
  running). Deferred → BACKLOG p3: invoice void/credit-memo, dead `partially_paid` badge, late-invoice
  COGS/revenue period split. **Next action:** `/zj:milestone` (v3.0 close). Optional: `/zj:log phase 13`;
  `/zj:ship` to merge the 11a+11b+12a+12b+13 stack.

- **(historical) Step:** **BUILD COMPLETE** — **Phase 13 (SYERP-13 AR & sell-side books — the FINAL v3.0 phase)
  built 2026-07-19** (`/zj:build 13`) on branch `feature-syerp-ar-invoicing`. All 18 tasks, **v3.0 DoD
  clause 3 closed**. Delivers the invoice (Dr 1120/Cr 4110) + receipt (Dr cash/Cr 1120) JEs + AR aging
  tying Decimal-exactly to the 1120 control (the COGS-on-ship JE was asserted, not rebuilt — D-P13-3).
  Proof: `verify_ar.py` 16 asserts (both concurrency locks mutation-proven) + `verify_ar_api.py` 29 asserts
  + **23/23** full regression (TB nets zero, BS balances) + FE **44 files / 131 tests** + `npm run build`
  exit 0. Decisions D-P13-1..8 (D-P13-8 = the app.core.models boot import). Plan + checklist all ticked.

- **(historical) Step:** **RETRO'D** — **Phase 12b (GELATO outbound: pick → pack → ship) closed 2026-07-19**
  (`/zj:retro 12b`), tag `zj/good-12b-gelato-pick-pack-ship` at `553bcfb`. Roadmap marked
  `[done — verified + retro'd]`. **v3.0 DoD clause 2 (warehouse fulfillment outbound) closed** and the
  sell-side **COGS** JE (Dr 5100 / Cr 1130) posts atomically on ship. Retro banked LEARNINGS Phase 12b
  (4 keepers — the forced-interleave-test-passes-for-the-wrong-reason headline, the mirror-an-exemplar's-lock
  caveat for one-shot vs repeatable transitions, the in-build dead-through-UI catch, and review-overrides-PASS
  now load-bearing 4 phases running). Deferred items homed: pick-path races Q1/Q2 → BACKLOG p2;
  bin-blind-desync outbound half closed (inbound still open, p2); downgrade test → p3. **Next action:**
  `/zj:plan 13` (SYERP-13 AR + invoice-from-shipment). Optional: `/zj:log phase 12b`; `/zj:ship` to merge
  the 11a+11b+12a+12b stack.

- **(historical) Step:** **BUILD COMPLETE** — **Phase 12b (GELATO outbound: pick → pack → ship) built 2026-07-18.**
  All **15 tasks** on branch `feature-gelato-pick-pack-ship`. Closes the v3.0 DoD clause 2 (warehouse
  fulfillment outbound) and posts the sell-side **COGS** JE (Dr 5100 / Cr 1130). Proof: `verify_gelato_ship.py`
  22 asserts + `verify_gelato_ship_api.py` 23 asserts + **19/19** full regression (TB nets zero with the
  new JE, 1130↔subledger tie) + FE **38 files/116 tests** + `npm run build` exit 0. Checklist (all 15
  ticked): `docs/tasks/feature-gelato-pick-pack-ship.md`.

## (historical) Position

- **(historical) Step:** **PLAN COMPLETE** — **Phase 12b (GELATO outbound: pick → pack → ship) planned 2026-07-18.**
  Closes the v3.0 DoD clause 2 (warehouse fulfillment outbound) and posts the sell-side **COGS** JE
  (Dr 5100 / Cr 1130) — the first half of SYERP-13's sell-side books; invoice-from-shipment + AR stay
  Phase 13. **15 tasks:** Wave A schema (Shipment + ShipmentLine models, `qty_picked`/`qty_shipped` on
  `crumb_sales_order_line`, migration **0016**, schemas) → Wave B backend (NEW SYERP bin-aware
  `post_issue` → GELATO `shipments.py` pick/pack/ship → router+boot) → Wave C verify
  (`verify_gelato_ship.py` incl. the accounting crux + control-vs-subledger tie + reservation-relief +
  partial-ship + the load-bearing Barrier; `verify_gelato_ship_api.py` HTTP RBAC/audit; full regression
  + TB-nets-zero) → Wave D frontend (shipment hooks, a Fulfillment pick→pack→ship screen, an SO-detail
  ship affordance, colocated Vitest asserting the real payload shape). Recurring keepers baked in: real
  router/UI payload shape in verify + Vitest (11a/11b/12a trap); the non-optional HTTP audit/RBAC script
  + `write_audit(target_id=str(shipment.id))` (12a int-PK bug — Shipment is int-PK); the pre-planned
  FOR-UPDATE lock + `asyncio.Barrier` two-concurrent-ship scenario; a control-account-ties-to-subledger
  assertion (not just TB nets zero — Phase 10 keeper). **Next action:** `/zj:build 12b`.

- **Branch (D-P12b-8):** build 12b on a fresh `feature-gelato-pick-pack-ship` cut off the verified 12a
  tip (tag `zj/good-12a-gelato-bins-putaway`, `52eb481`) — 11a/11b/12a unmerged; 12b stacks. Lint gates
  remain non-functional (BACKLOG p1); correctness rests on verify_* + Vitest, per project convention.

## (historical) Position

- **(historical) Step:** **RETRO'D** — **Phase 12a (GELATO bins & directed putaway) closed 2026-07-18** (`/zj:retro 12a`),
  tag `zj/good-12a-gelato-bins-putaway` at `52eb481`. Roadmap marked `[done — verified + retro'd]`. Retro banked
  **LEARNINGS Phase 12a**, five keepers: (1) **the headline lesson — adding a new dimension (`bin_id`) to a
  shared ledger silently corrupts it for every existing writer that ignores the dimension, and it's a
  SEQUENTIAL-correctness bug, not a race** (bin-blind `post_transfer`/`post_adjustment`/MOUSSE-issue leave the
  bin overstated + unbinned pool negative even single-threaded; the SC3 roll-up identity stays exact so every
  green assertion missed it — same shape as the 09c/10 zero-sum-identity blindness, now on a physical
  dimension); (2) **a value clamp that hides the symptom can break the invariant you just proved** — clamping
  `get_bin_on_hand` would have broken SC3, so the mitigation surfaced-and-pinned the boundary (scenario E)
  instead; (3) **the paired HTTP script earned its keep a 3rd suite running — GELATO's `Bin` is the first
  int-PK audited entity and its int→`VARCHAR(36)` `target_id` coercion bug 500'd the mutation after commit;
  keeper: `write_audit(target_id=...)` must `str()` the id** (reviewer confirmed no other int-PK target exists,
  so no repo sweep owed); (4) **concurrency pre-empted by design → clean review on that axis, the 9b rule
  paying off a 3rd time**; (5) **reverse-hub string table-name FK** avoids the import cycle when a hub-core
  table must reference a satellite table. Deferred items all homed: bin-split MAJOR → BACKLOG p2 (added at
  verify); int-PK audit sweep resolved (folded to LEARNINGS, no backlog entry); 422 sweep already BACKLOG p3.
  Artifacts: `.zj/phases/12a-gelato-bins-putaway/{PLAN,VERIFICATION,REVIEW}.md`, `.zj/LEARNINGS.md` Phase 12a.
  **Next action:** `/zj:plan 12b`. Optional: `/zj:log phase 12a` (formal work log); `/zj:ship` to merge the
  11a+11b+12a stack.

- **(historical) Step:** **BUILD COMPLETE** — **Phase 12a (GELATO bins & directed putaway) built 2026-07-17.**
  All **14 tasks** shipped on a fresh `feature-gelato-bins-putaway` branch (cut off HEAD `da9474e` = the
  verified 11b code tip + plan docs; see PLAN Deviations — bare tag `fec334f` would have dropped the plan).
  Delivered: `gelato` module self-registers (mirrors mousse/crumb new-module package shape); migration
  **0015** adds `gelato_bin` + nullable `bin_id` on `syerp_inventory_txn` (hub-inversion string FK,
  D-P12a-3), round-trips clean; `gelato:read`/`gelato:write` seeded; bin CRUD (unique-within-location,
  archive-hides) + directed putaway. The **SYERP-owned bin-aware primitive** `post_putaway`/`get_bin_on_hand`
  (D-P12a-7) clones `post_transfer` intra-location + bin-dimensioned, **locks `InventoryItem` FOR UPDATE
  before the floor read** (corrected from the plan's "InventoryTxn" prose — the append-only ledger isn't the
  contention point); GELATO's thin `service/` validates bins-belong-to-location then delegates. Router thin,
  RBAC-gated, audit-after-commit. **Proof:** `verify_gelato.py` (roll-up Decimal-exact + net-zero + floor +
  the **Barrier two-concurrent-putaway scenario, proven load-bearing** — lock removed → 2 successes → FAIL,
  restored → green) + `verify_gelato_api.py` (30 asserts, HTTP 401/403/200 + attributable audit) + all 17
  existing verify_* → **19/19 green**, Trial Balance `in_balance` True (12a posts **NO GL**); FE full suite
  **37 files/108 tests**, `npm run build` exit 0; nav gating data-driven (enabled ∩ `gelato:read`).
  **Two material findings, both handled:** (1) the paired HTTP script **caught a real router-audit bug** —
  bin routes passed integer `Bin.id` to `write_audit(target_id=...)` (VARCHAR col) → asyncpg `DataError`,
  bins committed then 500'd on the audit write (audit-trail violation); fixed `str(bin_.id)`, commit
  `136e98d` (the 9a/11a keeper recurring — GELATO's `Bin` is the **first int-PK audited entity**, worth a
  repo-wide `write_audit(target_id=)` sweep, logged under PLAN `## Noticed`); (2) the 11b dead-through-UI
  trap pre-empted — verify + the Putaway Vitest both assert the **real `PutawayRequest` payload shape**.
  **Next action:** `/zj:verify 12a`.

- **Branch (D-P12a-4, amended):** `feature-gelato-bins-putaway` off HEAD `da9474e` (code-identical to tag
  `zj/good-11b-crumb-sales-orders`/`fec334f`, docs on top). 11a/11b unmerged; 12a stacks. Checklist (all 14
  ticked): `docs/tasks/feature-gelato-bins-putaway.md`. Lint gates remain non-functional (BACKLOG p1) —
  correctness rests on verify_* (19/19) + Vitest (108), per project convention.

## (historical) Position

- **(historical) Step:** **PLAN COMPLETE** — **Phase 12a (GELATO bins & directed putaway) planned 2026-07-17.**
  Phase 12 (GELATO-01, 8 ACs) **split 12a/12b at plan** (D-P12a-1, owner — mirrors 9a/b/c + 11a/b):
  **12a** = bins CRUD + directed putaway (inbound foundation; covers GELATO-01 AC1/AC2 + the putaway
  portion of AC7/AC8; **NO GL, NO sales-order/reservation, NO pick/pack/ship**); **12b** = pick → pack
  → ship + reservation relief + COGS JE (the outbound + GL crux; AC3/4/5 + ship-side AC7/AC8). Three
  owner decisions set the shape: (1) **split 12a/12b, plan 12a now**; (2) **bin_id on the existing
  `syerp_inventory_txn` ledger** — one ledger, one bin dimension, roll-up to the location total
  guaranteed by construction (D-P12a-2); (3) **full staging-bin moves in 12b** (D-P12a-4, binds 12b).
  PLAN.md = **14 tasks** in 4 waves (models → migration 0015 [`gelato_bin` + `bin_id` col] → perms →
  schemas → SYERP `post_putaway`/`get_bin_on_hand` primitive → thin GELATO `service/` package → router
  + self-register → `verify_gelato.py` + `verify_gelato_api.py` → full regression → FE nav/Bins/Putaway/
  tests). Recurring keepers baked in: verify inputs built in the **real router/UI payload shape** (the
  11a/11b dead-through-UI trap), the non-optional **HTTP-level audit/RBAC** script, and a **load-bearing
  `asyncio.Barrier` concurrency** scenario on putaway-vs-putaway (FOR UPDATE, D-V3-18). Decisions
  D-P12a-1..9 recorded; no `## Decisions needed` open. Plan checked goal-backward at manager review
  (every SC → ≥1 task, every task → an SC, real files + runnable verify). **Next action:** `/zj:build 12a`.

- **Branch (D-P12a-5):** build 12a on a fresh `feature-gelato-bins-putaway` cut off the verified 11b
  tip (tag `zj/good-11b-crumb-sales-orders`, `fec334f`) — 11a/11b unmerged; 12a stacks. Lint gates
  remain non-functional (BACKLOG p1, known); correctness rests on the verify_* suite + Vitest.

- **(historical) Step:** **RETRO'D** — **Phase 11b (CRUMB sales orders + soft-reservation) closed 2026-07-17**,
  tag `zj/good-11b-crumb-sales-orders` (`fec334f`). **CRUMB-01 complete (all ACs).** Roadmap marked
  `[done — verified + retro'd]`. Retro banked three keepers (LEARNINGS Phase 11b): (1) **verify built
  its inputs in a shape the UI never sends** — `item_id=` hand-fed while the UI sends `plum_part_id`
  only — so 17/17 green certified a dead-through-UI headline feature; the 11a "green-but-broken"
  pattern recurred with a nameable mechanism (verify inputs must match the real router/UI contract);
  (2) **run verifier + reviewer in parallel and let a reviewer BLOCKER override a verifier PASS** — it
  has now caught the one defect that mattered on two consecutive phases; (3) **a multi-entry invariant
  needs one shared resolver wired into every door** (the `_resolve_and_validate_item_id` fix).
  Deferred items each have a home: quote→SO idempotency guard → BACKLOG p3; `plum_part_id` non-unique
  → accepted for single-shop; Closed-SO stale `qty_reserved` → cosmetic, recorded. **Next action:**
  `/zj:plan 12` (GELATO warehouse core — ship posts the COGS JE; realizes the D-P8-3 bin deferral).
  Optional: `/zj:log phase 11b` to file the formal work log; `/zj:ship` to merge the 11a+11b stack.

- **(historical) Step:** **BUILD COMPLETE** — **Phase 11b (CRUMB sales orders + soft-reservation) built 2026-07-17.**
  All **17 tasks** shipped on branch `feature-crumb-sales-orders` (cut off the verified 11a code tip
  `a8191cf`; tag `zj/good-11a-crumb-crm-pipeline` is docs-behind at `7c573d3`, code identical — see PLAN
  Deviations). CRUMB-01 completed (all ACs): SO models + migration 0014; direct SO CRUD + `SO-####`
  numeric-safe numbering + FSM (Draft→Confirmed→Fulfilling→Closed, +Cancelled from Draft/Confirmed);
  accepted-quote→SO conversion (item_id resolved from `plum_part_id`, free-text→NULL, source_quote/opp
  stamped); the **soft-reservation crux** — confirm reserves `min(qty_ordered, available)` with
  `available = get_item_on_hand − Σ open (confirmed/fulfilling) reservations ≥ 0`, `InventoryItem` rows
  `FOR UPDATE` locked in sorted-id order BEFORE the read (bills.py template), cancel releases; router
  audit + `crumb:read`/`crumb:write` RBAC; SO list/create/detail (ordered/reserved/shortage) + Convert-to-SO
  affordance. 11b posts **NO GL** (TB still nets zero). **Mandated Task-8 adversarial review → VERDICT
  PASS** (`REVIEW-task8.md`): invariant holds under concurrency; Medium finding (reservation not
  serialized vs raw stock write-offs) = **D-V3-18 by-design** (narrow lock; SYERP floor-guard deferred
  to Phase 12). **Proof:** backend `verify_crumb_so.py` (25 asserts incl. concurrency scenario F,
  mutation-tested load-bearing) + `verify_crumb_so_api.py` (40 asserts HTTP RBAC+audit) + all 15 existing
  verify_* → **17/17 green**; FE full suite **35 files/100 tests**; `npm run build` exit 0. **Next
  action:** `/zj:verify 11b`.

- **Branch (D-V3-19):** `feature-crumb-sales-orders` — 11a is unmerged; 11b stacks on it. Checklist
  (all ticked): `docs/tasks/feature-crumb-sales-orders.md`. Lint gates remain non-functional (BACKLOG
  p1, known) — correctness rests on the verify_* suite + Vitest, per project convention.

- **(historical) Step:** **RETRO'd** — **Phase 11a (CRUMB CRM & pipeline) verified + retro'd 2026-07-16.** Branch
  `feature-crumb-crm-pipeline` (cut off master `039c409`, D-V3-13), tip `efcf2e6`, tagged
  `zj/good-11a-crumb-crm-pipeline`. Retro (`/zj:retro 11a`) appended LEARNINGS Phase 11a
  (new-module-as-a-package from day one; mirror the newest exemplar; the two-tier verify pair earns
  SC6; **and the keeper — 20 green verify assertions missed a major defect that the code review
  caught**, so the adversarial review is not redundant with verify). Deferred items homed: the Task-2
  alembic unique-constraint drift and the 422 deprecation sweep were re-hit by crumb and noted on the
  existing p1/p3 BACKLOG entries (not duplicated); AC4 (sales orders + soft-reservation) +
  accepted-quote→SO conversion remain Phase 11b (D-V3-10). All 19 build tasks + the fix loop
  (`a697c69`, `efcf2e6`, 4 gaps) committed; VERIFICATION.md + REVIEW.md written. **Proof (post-fix):**
  `verify_crumb.py` **22/22** + `verify_crumb_api.py` **54/54** (SC6 HTTP RBAC+audit gate) + 13/13
  regression verify_* exit 0 + FE crumb Vitest 4/4 + `npm run build` exit 0. **Next action:**
  `/zj:plan 11b`. Phase 11
  (CRUMB-01, the largest single FR) was **split into 11a + 11b** at plan (D-V3-10): **11a** = the
  inventory-free CRM chain (leads → opportunities → quotes + communication log), **11b** = sales
  orders + accepted-quote→SO conversion + the soft-reservation crux. PLAN.md for 11a holds **19 tasks**
  in 5 waves (models → migration 0013 → perms → schemas → 4-entity `crumb/service/` package →
  router+register → `verify_crumb.py` + `verify_crumb_api.py` + regression → frontend nav/4 pages/tests).
  Every in-scope CRUMB-01 AC (1/2/3−/5/6/7) maps to a task; **AC4 (sales orders + reservation) is
  deferred to 11b**. Six decisions recorded (**D-V3-10..15**). Plan reviewed goal-backward; one
  architect error caught and fixed at manager check — the hub FK columns are `String(36)` (Partner/
  plum_part PKs are UUIDs, not int).

- **Project:** BizNiceSweets
- **Milestone:** **v3.0 Customer & logistics — CLOSED + tagged `v3.0`** 2026-07-19 (all phases verified +
  retro'd; DoD audited goal-backward, 2 gaps fixed at close; phases archived to `.zj/history/v3.0/`).
  **Next milestone = v4.0 Infra-debt + quality paydown (D-M3-3).** v2.0 + v1.0 closed + tagged.
- **Branch:** v4.0 Phase 2a **BUILD COMPLETE** on `chore-pytest-harness-repair` (off `93de57d`,
  code-identical to tag `zj/good-01-lint-gates-clean`/`dd401d1`). All 13 tasks committed, tree clean.
  Unmerged v4.0 stack (Phase 1 + 2a) ships at milestone close. The merged `feature-syerp-ar-invoicing`
  branch may be deleted.
- **Last update:** 2026-07-22
- **Next action:** **`/zj:retro 2a`** (bank the fix-loop learnings) or **`/zj:plan 2b`** (port the
  `verify_*` cruxes). Phase 2a is **verified — Verdict PASS**, tag `zj/good-02a-pytest-harness-repair`.
  (Historical verify target, now satisfied:) verify v4.0 Phase 2a goal-backward against the 6 SCs:
  SC1 DSN probe connects (`afa5798`); SC2 no InterfaceError, one loop-safe NullPool engine shared by
  direct-session fixtures AND the ASGI `client` (`6ad45c9`); SC3 token identities resolve (admin-user +
  D-P2a-5 roster, `871998c`/`592faac`); SC4 back-to-back reruns, 0 IntegrityError (truncate-reset);
  SC5 **217 passed / 0 failed / 0 skipped** + non-vacuity proven (Task 10); SC6 env-pointable, no
  hard-coded host (Task 11). Regression: cold boot `BOOT_OK` + **23/23 `verify_*`** + ruff exit 0.
  D-P2a-5 recorded (RBAC test-identity roster). **Watch at verify:** container dev-deps are ephemeral
  (Phase-3 test-image bake); `_isolate` reseeds auth+roster only (GL tests self-seed COA); all 32
  first-run failures were TEST drift (no product code touched) — confirm none masks a real bug.
  Porting `verify_*` cruxes stays **2b**.

## Next action (detail)

**`/zj:plan 13`** — SYERP-13 AR + invoicing from the shipment/SO — the last v3.0 clause. **Alternative —
pay down infra debt first:** the BACKLOG **p1** items (CI, live-DB pytest harness repair, both lint gates)
are now two milestones old; a debt-paydown phase is reasonable if the owner wants it (raise at `/zj:ideate`).
Also standing: the pick-path shipment-header races (BACKLOG p2, Q1/Q2) and the inbound half of the
bin-blind-desync item (p2) — weigh the shared cross-path row-lock refactor when a multi-writer deploy nears.

### (historical) Phase 11b verify target
**`/zj:verify 11b`** verified goal-backward against the 6 SCs: SO model/migration/wiring (SC1); direct
CRUD + FSM (SC2); accepted-quote→SO conversion (SC3); the soft-reservation invariant incl. the
concurrency crux (SC4 — re-run `verify_crumb_so.py` scenario F, it is mutation-tested load-bearing);
router audit + RBAC at HTTP level (SC5 — `verify_crumb_so_api.py`); FE + regression 17/17 + TB nets zero
(SC6). Deviations to review: SO list omits a cosmetic "total" column (header schema has no `total_value`);
branch cut off `a8191cf` not the bare tag (code-identical). Noticed follow-ups (all deferred, non-blocking):
Closed-SO stale `qty_reserved` (cosmetic), item→InventoryItem ambiguity (single-shop OK), 422 deprecation
sweep (BACKLOG p3).

### (historical) Phase 11a build — CRUMB-01 inventory-free portion
**`/zj:build 11a`** built a new `crumb` module (mirrors the
MOUSSE new-module pattern, D-P10-6) with a `crumb/service/` package split by entity, leads →
opportunities (stage FSM) → quotes (PLUM-derived 30% markup default, `QUOTE-####` numeric-safe, Draft
→Sent→Accepted/Rejected/Expired FSM), and an append-only customer communication log. Server-enforced
FSMs, audit at the router layer, `crumb:read`/`crumb:write` RBAC. Proven by `verify_crumb.py` (service)
+ `verify_crumb_api.py` (HTTP RBAC + audit) + FE Vitest/build; the 13 existing `verify_*` stay green.

**Before building:** fast-forward `chore-spec-v3-customer-logistics` → `master`, then cut
`feature-crumb-crm-pipeline` off master (D-V3-13).

**After 11a verifies:** `/zj:plan 11b` — sales orders + the soft-reservation crux (`qty_reserved`
accumulator on the SO line, D-V3-11; `available = on-hand − Σ reserved ≥ 0`, D-V3-8) + accepted-quote
→SO conversion. Then Phase 12 (GELATO ship, posts COGS JE) → Phase 13 (SYERP-13 AR). The DoD, not the
phase count, is the contract.

**Alternative — pay down infra debt first:** the BACKLOG **p1** items (CI pipeline, live-DB pytest
harness repair, both lint gates) are now two milestones old. A debt-paydown phase is reasonable if the
owner wants it (raise at `/zj:ideate`).

## Deferred at the v2.0 close (owner-approved — do not lose)

- **Human click-through UAT** (`.zj/UAT-v2.0.md` 14 checks + owed v1.0 round-2) → BACKLOG **p1**
  pre-public-release gate (D-M2-2). Tag rests on backend live-proof + the wired-UI audit; extend the
  checklist with GL/AP/reports/MOUSSE UI flows before running it.
- **BACKLOG p1 infra debt** — no CI, live-DB pytest harness broken (100 skips, D-P7-4), both lint
  gates non-functional. Correctness rests on `verify_*` + Vitest. Carried into v3.0.
- **`/zj:ship` master-merge** (D-M2-3) — **RESOLVED 2026-07-16** (PR #2, fast-forward to `35f9b66`).

## Standing context

- **Stack for verification:** `podman-compose -f compose/compose.yml -f compose/compose.dev.yml up -d`;
  run verify scripts in-container: `podman exec -e PYTHONPATH=/app compose_api_1 python scripts/<name>.py`.
  Vite dev server for UI/UAT at `http://localhost:5173`.
- **v2.0 tag placement (D-M2-3, mirrors D-M1-1):** the `v2.0` tag (`d6c91cb`) was applied on the
  then-unmerged branch tip; the fast-forward ship (PR #2) preserved the SHA and it is now reachable
  from `master`. Debt cleared.
- **Adoption note:** adopted from GSD 2026-07-04; prior systems archived under `archive/`. `.zj/` is
  self-contained.
