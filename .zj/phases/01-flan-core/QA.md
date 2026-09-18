# QA — v5.0 Phase 1 "FLAN core" (SRD **FLAN-01**, AC1–AC7)

Phase checklist, written in the house format of `.zj/QA.md` (`C-<REQ>-NN` ids, exact fixture
literals, exact expected results). Per the owner's standing preference **QA docs: non-blocking** —
an unrun or red check here never blocks a build, a phase close, or a merge. Record the reading and
move on.

**Scope of this file:** the checks a *human* is the pin for. Everything else about this phase is
pinned by machine and listed under "✅ Machine already proved" inside each check — **do not
re-check those**.

> ## ⚠ Read `.zj/QA.md` §4.8 instead — this file is the phase's record, not the runbook
>
> These eight checks were **landed into the standing checklist** at the phase close, renumbered
> `C-FLAN-01` … `C-FLAN-08`, and **revised there for what the verify fix loop changed**. The
> canonical, as-shipped versions live in `.zj/QA.md` §4.8; both QA scripts
> (`verify_qa_doc.py`, `verify_qa_citations.py`) pass over them, so every citation there is
> re-greppable. This file is kept as the phase artefact — the record of what the verifier wrote
> before the fix loop ran.
>
> **What changed after this file was written** (and is therefore corrected only in §4.8):
> `C-FLAN-01`/`-02`/`-05` gained **tag** steps, because tags went from unreachable to editable;
> `C-FLAN-06` gained the note that the **Hourly rate** column is visible to you only because you
> are an admin — pay rates are now gated on `flan:rates` (D-V5P1-8), which the default `user` role
> does not hold.

---

## 1. What changed, in a tester's terms

FLAN — the project-management suite — went from a frozen HTML prototype to a real module in the
app. There is now a **FLAN** item in the left sidebar. Behind it:

- a **Projects** list where you create, edit and archive projects;
- per project, a **Phases** screen, a **Tasks** screen and a **Team** screen, reached through a
  project switcher in the FLAN sub-nav;
- a phase's **start date, due date and % complete are not typed in** — they are computed from the
  phase's tasks every time you look, and there is deliberately no field to type them into;
- task **keys** (`PRJ-1`, `PRJ-2`, …) are issued by the server, not by you;
- the **Team** roster is per project; members may — but need not — be linked to a login account.

Nothing about money, stock, or the ledger changed. FLAN posts nothing to the general ledger.

## 2. Preconditions

```bash
cd /home/zack/Projects/BizNiceSweets
./scripts/uat.sh --fresh --detach       # or: podman-compose -f compose/compose.yml -f compose/compose.dev.yml up -d
```

- Click through at **http://localhost:5173**. Log in with `BNS_ADMIN_EMAIL` /
  `BNS_ADMIN_PASSWORD` from `.env`.
- **There are no seeded FLAN fixtures.** `backend/scripts/seed_uat_fixtures.py` creates none, so
  every check below tells you exactly what to type. Create the data in the order given —
  `C-FLAN-01-02` onward depend on the project made in `C-FLAN-01-01`.
- The FLAN module ships **enabled**, so the sidebar item is there on first login. You do **not**
  need to enable anything first (a check written as "enable FLAN, then look for the nav item"
  would pass without proving anything — see `C-FLAN-01-08`, which tests it the other way round).

## 3. Coverage map

**All 7 of FLAN-01's acceptance criteria have at least one human check below.**

| AC | What a human is pinning | Checks |
|---|---|---|
| FLAN-01.1 Project CRUD + archive | that create/edit/archive are reachable and the archive copy is honest | `C-FLAN-01-01`, `C-FLAN-01-02` |
| FLAN-01.2 Phases, derived dates/%, cascade | that the derived values *move on screen* when tasks change, and that the cascade warning names a real number | `C-FLAN-01-03`, `C-FLAN-01-04` |
| FLAN-01.3 Tasks, keys, dates | that keys appear without you typing one, and that a bad date range is a legible toast rather than a crash | `C-FLAN-01-05` |
| FLAN-01.4 Team roster | that the remove confirmation tells the truth about what it clears | `C-FLAN-01-06` |
| FLAN-01.5 Assignment | that the assignee filter narrows the board and removed members vanish from pickers | `C-FLAN-01-06`, `C-FLAN-01-07` |
| FLAN-01.6 Multi-project | that switching projects never shows you the other project's rows | `C-FLAN-01-07` |
| FLAN-01.7 Audit + RBAC + nav gating | that the nav item obeys the module toggle | `C-FLAN-01-08` |

## 4. The checks

### FLAN-01.1 — Project CRUD, archive-as-soft-delete

#### C-FLAN-01-01 · Create a project and confirm it lands in the list

**Fixture (type exactly):** Name `Crisis Simulator`, Category `Client`, Currency `USD`,
Start date `2026-03-01`, Gate date `2026-09-30`. Leave **Key prefix** blank.

- ✅ **Machine already proved:** `Projects.test.tsx "POSTs the ProjectCreate payload from the create
  dialog"`, `"sends key_prefix null when the field is left blank (server derives it)"`,
  `"renders a row per project, each with its OWN key prefix"`,
  `"surfaces a 4xx detail from create as an error toast"`; `verify_flan_api.py (A)`.
- **Do:** sidebar → **FLAN** (it lands on **Projects**). Click **New Project**, fill the fixture,
  click **Create Project**.
- 👁 **You are confirming:**
  - a row appears **without a page refresh**, reading `Crisis Simulator` | `CRIS` | `Client` |
    `USD` | `2026-03-01` | `2026-09-30` | `Active`
  - the **Key prefix** cell says `CRIS` — the server derived it from the name; you never typed it
  - the `Active` indicator is legible as **text**, not colour alone
- ✗ **Would be wrong:** an empty Key prefix cell, a `PRJ` fallback, or having to press F5 to see
  the new row.

#### C-FLAN-01-02 · Edit, then archive — and read the archive copy

**Fixture:** create a **second** project also named `Crisis Simulator` (same name, nothing else
filled). Then edit the *first* one's Description to `Q3 rebuild`.

- ✅ **Machine already proved:** `Projects.test.tsx "opens the edit dialog pre-filled with the
  edited row's OWN values"`, `"PATCHes a ProjectUpdate body carrying neither id nor active"`,
  `"archives a project only after the confirmation is accepted"`, `"hides archived projects until
  the Show archived switch is on"`, `"surfaces the server's 422 detail when a key prefix can no
  longer change"`; `verify_flan.py (E)` proves the archived project refuses all six write kinds and
  still reads back complete.
- **Do:** create the duplicate-named project. Open the **Actions** menu (⋯) on the *second* row →
  **Edit**; check the dialog is filled with **that** row's values, not the first row's; cancel.
  Edit the *first* row, set Description `Q3 rebuild`, **Save Project**. Then Actions → **Archive**
  on the second project and read the dialog before accepting. Accept. Then toggle **Show archived**.
- 👁 **You are confirming:**
  - two rows with the **same name** coexist — duplicate project names are allowed by design
  - the edit dialog opens pre-filled with the row you clicked (a stale-dialog bug shows the
    previously-opened row's values)
  - the archive dialog says the project **keeps all of its phases, tasks and team, and stays
    readable — only writes inside it are refused**, and that it is hidden until "Show archived" is on
  - after accepting, the row disappears; with **Show archived** on it returns badged `Archived`,
    and its Actions menu offers **no** Edit and **no** Archive
- ✗ **Would be wrong:** the archive dialog using the word "delete" without saying the data
  survives; the archived row still offering Edit; the duplicate name being refused.
- ⓘ There is **no un-archive**. Archiving is currently a one-way door in the UI — see §6.

### FLAN-01.2 — Phases: derived dates and % complete, and the cascade

#### C-FLAN-01-03 · The empty phase, and watching the derived values move

**Fixture:** in `Crisis Simulator`, create two phases — `Design` (Order `1`, Status `Pending`) and
`Build` (Order `2`, Status `Pending`). Then, on **Tasks**, create three tasks **in `Design`**:

| Summary | Start | Due |
|---|---|---|
| `Wireframes` | `2026-03-05` | `2026-03-20` |
| `Schematics` | `2026-03-01` | `2026-03-11` |
| `Enclosure`  | `2026-03-09` | `2026-03-14` |

- ✅ **Machine already proved:** `Phases.test.tsx "renders each phase's derived dates and the API's
  OWN percent string"`, `"renders an em-dash for both dates and 0.00% on a phase with no tasks"`,
  `"offers no date and no percent input in the edit dialog"`, `"tells the user the percentage is
  derived from the tasks and not editable"`; `verify_flan.py (A0)–(A4)` (mutation-proven RED);
  `backend/tests/flan/test_rollup.py::test_phase_rollup_crux`.
- **Do:** create the two phases, look at the **Phases** table **before** adding any task. Open
  **Edit Phase** on `Design` and look at the fields, then cancel. Add the three tasks on the
  **Tasks** screen. Return to **Phases**. Then set `Wireframes` to **Done** and return again; then
  set all three to **Done** and return again.
- 👁 **You are confirming:**
  - with no tasks, **both** `Derived start` and `Derived due` show an **em-dash (—)** and
    `% complete` reads exactly **`0.00%`** — not blank, not `0%`, not `NaN`
  - the **Edit Phase** dialog offers **no** date field and **no** percent field at all, and says the
    percentage comes from the tasks
  - after the three tasks, `Design` reads `Derived start` **2026-03-01** and `Derived due`
    **2026-03-20** — the earliest start and the latest due, *not* the first or last task you typed
  - `% complete` goes `0.00%` → **`33.33%`** (1 of 3 Done) → **`100.00%`** (3 of 3), each time
    **without a page refresh**
  - `Build`, still empty, stays at `—` / `—` / `0.00%` throughout
- ✗ **Would be wrong:** derived start showing `2026-03-05` (the first task you entered);
  `33.33333…%`; the percentage failing to move until you reload; any date or percent input
  appearing in the phase dialog.

#### C-FLAN-01-04 · Deleting a phase names the tasks it will take with it

**Fixture:** `Design` now holds 3 tasks; `Build` holds 0.

- ✅ **Machine already proved:** `Phases.test.tsx "names the cascaded task count and deletes only
  after the confirmation"`, `"says a phase has no tasks when nothing will be cascaded"`;
  `verify_flan.py (F)` and `test_rollup.py::test_phase_delete_cascades_to_its_tasks_only` prove the
  database cascade and that the sibling phase is untouched.
- **Do:** on **Phases**, Actions → **Delete phase** on `Build`; read the dialog; cancel. Do the same
  on `Design`; read the dialog; **cancel** (do not delete — later checks need these tasks).
- 👁 **You are confirming:**
  - `Build`'s dialog says the phase has **no tasks**
  - `Design`'s dialog names **3 tasks** explicitly, in words, before you can confirm
  - cancelling leaves both phases and all three tasks present
- ✗ **Would be wrong:** a generic "Are you sure?" that never mentions the tasks — the tasks are
  destroyed with the phase, and a tester who deletes a phase expecting the tasks to survive has
  been misled.
- ⓘ If you *do* delete a phase, its tasks must vanish from the **Tasks** screen immediately (this
  was a real in-build defect, fixed in `5b3d09f` — see §5).

### FLAN-01.3 — Tasks: server-issued keys, dates

#### C-FLAN-01-05 · Keys you never type, and a rejected date range

**Fixture:** in `Crisis Simulator` / phase `Design`, create tasks until you have **ten**, then try
one more with Start `2026-05-10` and Due `2026-05-09`, then one with Start `2026-06-01` and Due
`2026-06-01`.

- ✅ **Machine already proved:** `Tasks.test.tsx "POSTs a TaskCreate body with no key field (the
  server assigns the key)"`, `"renders each task's server-generated key in the order the API
  returned"`, `"offers no key input in the sheet and no removed member in the pickers"`,
  `"surfaces a 422 due<start as an error toast in the server's own words"`, `"PATCHes a TaskUpdate
  body from the edit sheet, showing the key read-only"`; `verify_flan.py (B1)–(B5)`, `(C1)–(C3)`;
  `test_rollup.py::test_task_keys_are_numeric_safe`;
  `tests/flan/test_api.py::test_task_create_refuses_due_before_start_on_the_wire`.
- **Do:** open **New Task** and look for a Key field (there is none). Create tasks until the list
  holds ten. Then create one with Due **before** Start. Then create one with Due **equal to** Start.
  Finally open **Edit Task** on any row.
- 👁 **You are confirming:**
  - keys read `CRIS-1` … `CRIS-9`, **`CRIS-10`** — and `CRIS-10` sorts **after** `CRIS-9` in the
    list, not between `CRIS-1` and `CRIS-2`
  - the Due-before-Start create shows a **legible error toast in the server's own words** and the
    sheet stays open — no blank screen, no 500, no silently-created task
  - the Due-**equals**-Start task is **accepted** (a zero-duration milestone is legal)
  - in **Edit Task** the Key is shown **read-only**
- ✗ **Would be wrong:** `CRIS-0001`-style padding; `CRIS-10` ordered before `CRIS-9`; the bad-date
  create producing a raw `422 Unprocessable Entity` string or a crash instead of a readable message.

### FLAN-01.4 / FLAN-01.5 — Roster and assignment

#### C-FLAN-01-06 · Remove a member and confirm the tasks survive

**Fixture:** on **Team**, add `Ada Lovelace` — Role `Engineer`, Email `ada@example.com`, Colour any,
Hourly rate `125.50`, Platform user **No platform user**. Add `Grace Hopper` with name only. Then on
**Tasks**, assign **both** to `CRIS-1` and **Ada only** to `CRIS-2`.

- ✅ **Machine already proved:** `Team.test.tsx "renders the name, role, email, colour and linked
  user, em-dashing the rest"`, `"renders a member's hourly rate as the string the API returned"`,
  `"says the rate is stored but unused, and derives no cost from it"`, `"POSTs user_id: null when
  the member is saved with 'No platform user'"`, `"names the assignment clearing in the remove
  confirmation, then DELETEs"`, `"offers no reactivate action and no way to list removed members"`;
  `verify_flan.py (D1)` proves the two tasks come back **byte-identical** (including `updated_at`)
  and `(D2)` proves deactivating the linked login leaves the roster row untouched.
- **Do:** add both members, make the assignments, then Actions → **Remove member** on `Ada
  Lovelace`. **Read the dialog** before accepting. Accept. Return to **Tasks**.
- 👁 **You are confirming:**
  - the roster shows `125.50`-style rate text and **nowhere** multiplies it by anything — no cost,
    total or budget column appears anywhere in FLAN
  - a member with **no** platform user is fully usable as an assignee (Ada is)
  - the remove dialog states that removing Ada **clears her task and phase assignments** and that
    **the tasks themselves are left intact** — before you accept
  - after accepting: Ada is gone from the roster **and from the assignee pickers**; `CRIS-1` still
    exists and still lists **Grace Hopper**; `CRIS-2` still exists with **no** assignee; neither
    task's summary, status or dates changed
- ✗ **Would be wrong:** `CRIS-2` disappearing along with Ada; Grace being cleared off `CRIS-1` too;
  a rate-derived number appearing anywhere.
- ⓘ There is deliberately **no reactivate** action and no "show removed" toggle — see §6.

#### C-FLAN-01-07 · The assignee filter, and two projects that never mix

**Fixture:** the second `Crisis Simulator` was archived in `C-FLAN-01-02`. Create a third project
`Bench Rig` (Key prefix blank) with one phase `Fixtures`, one task `Mount plate`, and one team
member `Katherine Johnson`.

- ✅ **Machine already proved:** `Tasks.test.tsx "re-fetches with assignee_id in the params when the
  assignee filter is set"`, `"re-fetches with phase_id in the params when the phase filter is
  set"`; `FlanNav.test.tsx "renders one switcher option per project"`, `"shows the project from
  useParams().projectId, not the first in the list"`, `"switching projects preserves the current
  section"`, `"points the sub-nav links at the current project"`;
  `tests/flan/test_api.py::test_flan_assignment_rbac_and_audit`.
- **Do:** on `Crisis Simulator` / **Tasks**, set the assignee filter to `Grace Hopper`, then back to
  **All assignees**; set the phase filter to `Design`, then back to **All phases**. Now use the
  project switcher in the FLAN sub-nav to move to `Bench Rig`, staying on the **Tasks** tab. Look at
  the URL. Switch back.
- 👁 **You are confirming:**
  - filtering by `Grace Hopper` narrows the list to `CRIS-1` only; clearing it restores all rows
  - the switcher lists **both live projects** and the archived one is **not** offered
  - switching to `Bench Rig` keeps you on the **Tasks** tab, changes the URL to
    `/flan/projects/<other-id>/tasks`, and the table shows **only** `Mount plate` — **no `CRIS-*`
    row is visible**, not even briefly
  - the **Team** tab under `Bench Rig` shows only `Katherine Johnson`, never `Grace Hopper`
- ✗ **Would be wrong:** any `CRIS-*` key appearing under `Bench Rig`, even for a flash while
  loading; the switcher jumping you back to the Phases tab; the assignee dropdown offering a member
  of the other project.

### FLAN-01.7 — Nav gating

#### C-FLAN-01-08 · Turn FLAN off, confirm the nav item goes away, turn it back on

- ✅ **Machine already proved:** `AppShell.test.tsx` (9 cases over `getVisibleModules` — enabled ∩
  `<key>:read`, admin wildcard, disabled-module exclusion); `verify_flan_api.py (B)/(C)` proves all
  20 endpoints refuse a token without `flan:write`/`flan:read` over real HTTP; `(D)` proves every
  mutation writes exactly one attributable `audit_log` row and the reads write none.
- **Do:** go to **Settings → Modules** (`/settings/modules`), switch **FLAN** off, and look at the
  sidebar. Switch it back on.
- 👁 **You are confirming:**
  - with FLAN off, the **FLAN** sidebar item disappears **without a page refresh**
  - switching it back on brings the item back, and `/flan` still lands on the Projects list
- ✗ **Would be wrong:** the item staying visible with the module off, or needing F5 either way.
- ⓘ Turning the module off hides the **navigation** only — the `/api/v1/flan/*` endpoints keep
  answering, exactly as PLUM's and every other suite's do. That is the platform's current CORE-07
  behaviour, not a FLAN defect (the server-side module gate is a standing p2 backlog item).

## 5. The failure this phase fixed

One defect was found and fixed **during** the build, and it is worth knowing the old behaviour so
you can recognise a regression:

- **`5b3d09f` — deleting a phase used to leave its tasks on screen.** `useDeletePhase` refreshed
  only the phase list, but the database deletes a phase's tasks with it. Before the fix, deleting a
  phase and switching to **Tasks** listed rows that no longer existed; clicking one failed. If you
  ever see a deleted phase's tasks still listed, that is this bug back.

## 6. Known limitations — do not re-file these

- ~~**Tags cannot be set anywhere in the UI.**~~ **NO LONGER TRUE — fixed in the verify fix loop
  (`b1ded29`).** This was gap **G1**: the API stored project and task tags but no dialog offered a
  field, so an element named in both AC1 and AC3 was unreachable. Both project dialogs and the task
  sheet now carry a chip editor (Enter or comma commits, × removes), and Projects and Tasks each
  have a **Tags** column. Tags remain **opaque strings** — D-V5P1-5 forbids facet semantics until
  FLAN-04, so there is deliberately no vocabulary, no colour mapping and no autocomplete.
- **A soft-removed roster member cannot be reactivated**, and removed members cannot be listed.
  Deliberate owner decision at plan review; FLAN-01.4 does not ask for one. Recorded in
  `backend/app/modules/flan/service/roster.py`'s module docstring and in `.zj/STATE.md`.
- **An archived project cannot be un-archived from the UI.** Noted as an open question in
  `.zj/phases/01-flan-core/REVIEW.md`.
- **A task key is re-issued after you delete the highest-numbered task.** Delete `CRIS-10` and the
  next task you create is `CRIS-10` again. Owner-accepted for Phase 1 (FLAN-01.3 requires only
  uniqueness among live rows); filed **p2** in `.zj/BACKLOG.md:166` to be fixed by FLAN-10 at the
  latest.
- **`Hourly rate` is stored and read by nothing** — no cost, budget or utilisation is derived from
  it in v5.0 (D-M5-2). Its absence from every total is correct. **Changed in the verify fix loop:**
  it is now gated on a new **`flan:rates`** permission (D-V5P1-8) that the default `user` role does
  **not** hold — a non-holder gets no rate column, no dialog input, and the key does not cross the
  wire at all. You see it because `require_permission` has an admin wildcard.
- **No scheduling, board, timeline, calendar, risks, deliveries, budgets, exports or analytics.**
  Those are FLAN-02 … FLAN-11, phases 2a–7. The Tasks screen is deliberately a plain table.

## 7. What `.zj/QA.md` needed in order to absorb these checks — ✅ **ALL LANDED**

> **Done at the phase close.** §3 gained the FLAN-01 row (retitled, status `verified`) **and the
> eleven rows that were missing entirely** — `FLAN-02..11` plus `NFR-9`; the headline moved from
> "31 of 47" to **"32 of 58"**; §4.8 was added with the eight checks; §5's "Not built yet" bucket
> lost FLAN-01 and gained the eleven. `verify_qa_doc.py` and `verify_qa_citations.py` both exit 0.
> **That also cleared the inherited red** which had been failing on `master` — and with it the
> merge block on the required `verify-scripts` status context. The original plan follows, for the
> record.

`verify_qa_doc.py` enforces the master doc's arithmetic, so these edits must land together:

1. **§3 coverage map — add one row**, in FLAN's place in the suite ordering:
   `| **FLAN-01** — Project, work-breakdown & team core | implemented | C-FLAN-01, C-FLAN-02, C-FLAN-03, C-FLAN-04, C-FLAN-05, C-FLAN-06, C-FLAN-07, C-FLAN-08 |`
   The **Status cell must be the first word of FLAN-01's `**Status: …**` in `.zj/SRD.md`** — which
   today still reads `planned` (gap **G7**). Flip the SRD to `implemented` **first**, or the
   status-cell cross-check will fail.
2. **§3 headline** — currently "**31 of 47 requirements have at least one human check.**" The
   denominator is already wrong (the SRD holds **58**). After adding FLAN-01 the covered count
   becomes **32**; the headline must read **32 of 58** *and* §5 must itemise the remaining **26**,
   or `verify_qa_doc.py`'s "buckets + covered == total" assertion still fails. That means absorbing
   `FLAN-02..FLAN-11` and `NFR-9` into a §5 bucket in the same edit — which is exactly the
   pre-existing red already filed p1 at `.zj/BACKLOG.md:61`.
3. **§4 — add a `### FLAN-01 — Project, work-breakdown & team core` section** (a new `#### 4.8`
   suite heading, "FLAN — project management (8 checks)"), carrying the eight checks above
   **renumbered `C-FLAN-01` … `C-FLAN-08`** to match the master doc's `C-<SUITE>-NN` convention.
4. **§5** — remove nothing; FLAN-01 moves out of the "Not built yet" bucket if it is listed there,
   and `FLAN-02..11` + `NFR-9` go **into** it.
5. **§2 named fixtures** — these checks currently ask the tester to type their own data because
   `backend/scripts/seed_uat_fixtures.py` seeds **no** FLAN rows. Either add a `### 2.9 FLAN` block
   quoting the literals above as tester-created, or extend the seed script with a FLAN project so
   §4's FLAN checks can quote manifest literals like every other suite does (gap **G9**).
6. `verify_qa_citations.py` will then check that every `verify_flan.py (X)` scenario id cited above
   really exists in the script — the ones cited here (`A0`–`A4`, `B1`–`B5`, `C1`–`C3`, `D1`, `D2`,
   `E`, `F`) all do.

## 8. Result

| Field | Value |
|---|---|
| Tester | _(unrun)_ |
| Date | |
| Build / commit | phase closed post-fix-loop; see `.zj/ROADMAP.md` and tag `zj/good-01-flan-core` |
| Verdict | **pending** |
| Notes | |

Record each check as **PASS** or **FAIL**, and for a FAIL *what you actually saw* — the verbatim
label, number, or absent element. Never a guess, never "looks right".
