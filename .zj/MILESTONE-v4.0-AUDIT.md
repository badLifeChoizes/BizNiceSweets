# Milestone v4.0 "Infra-debt + quality paydown" — goal-backward close-out audit

Date: 2026-08-18 | Auditor: ZJ verifier (adversarial, evidence-only)
Tip audited: `ad05c7a` (branch `chore-human-uat`) | Range: `9903f1f..ad05c7a` (185 commits)
Method: re-ran every gate from a cold start against a **throwaway `postgres:17`** (never the
owner's UAT database), read every inventory lock in code, drove PLUM-01 CRUD + numbering through
the real HTTP router, and wrote a new concurrency probe for the one writer the phase gates never
raced. Authed `gh` (account `badLifeChoizes`) was used to check runs, jobs and branch protection
live — nothing about CI is taken from a document. The prod stack at `:8000` was read only
(health, SPA, login, one GET); no audit write beyond one login event. Working tree left clean,
throwaway Postgres destroyed.

## Overall verdict: GAPS FOUND — 1 blocker-to-close, 3 major, 4 minor

The engineering half of this milestone is real and is better than its own paperwork claims.
Every number the Phase-5 close asserted reproduced **exactly** on a fresh database: pytest
**245 passed / 0 skipped**, **17/17** non-API + **9/9** API `verify_*` exit 0, ruff 0, eslint 0,
vitest **148 tests / 45 files**, `tsc -b` + `vite build` clean. CI is not theatre — the workflow
exists, fires on every push, and its latest run is genuinely green with those same figures.

But the Definition of Done is a five-clause sentence and **two of its five clauses are not true**,
one of them by the owner's own conscious decision:

- **C4 is flatly NOT MET.** The DoD says "every shipped UI flow **has passed** a documented human
  click-through." `.zj/QA.md` §6 holds one empty row. No human has run one check. D-P5-11
  rescoped **NFR-8** so the reading is non-blocking — it did **not** amend the milestone DoD text,
  which still says *has passed*. The milestone cannot honestly close against its own sentence
  until the owner either runs the checklist or amends the sentence.
- **C3 is PARTIAL, and I reproduced it live.** GELATO `execute_pick` is the one ledger writer
  outside the sorted-id lock discipline. Two concurrent picks of one SO produced **two open
  `picking` shipments** (first attempt), and two picks ordering the same two items oppositely
  **deadlocked in 6 of 6 iterations** — a 500, not a clean 409. Both are logged p2
  accepted-risk, so this is honest debt, not a hidden defect — but "race-safe across **every**
  writer" is not true.

Also load-bearing and not previously named: **the entire SYERP financial-reporting HTTP surface
has zero CI coverage.** `grep` over `backend/tests/` returns **0** references to
`/ap/aging`, `/reports/trial-balance`, `/reports/profit-loss`, `/reports/balance-sheet`. Their
only guard is `verify_reports_api.py`, which **no CI job runs** — including the P&L
missing-bound 422 that was the v2.0 milestone audit's own gap fix. That is exactly the failure
mode clause C5 exists to eliminate.

And a shipping fact that undercuts the whole "trustworthy deploy" framing: **`master` contains no
v4.0 work at all.** `origin/master` is `9903f1f`; `.github/workflows/ci.yml` does not exist on it;
PR #4 is still **OPEN**. The branch that carries branch protection is the branch with no CI file.

---

## DoD clause verdicts

| # | Clause | Verdict |
|---|---|---|
| C1 | Full suite green in a GitHub Actions CI pipeline on every push | **PARTIAL** |
| C2 | Both lint gates enforce a zero-violation baseline | **MET** |
| C3 | The inventory ledger is race-safe across every writer | **PARTIAL** |
| C4 | Every shipped UI flow has passed a documented human click-through | **NOT MET** |
| C5 | A new deploy is trustworthy without a manual `verify_*` run | **PARTIAL** |

### Clause 1 — CI green on every push: PARTIAL

| Truth | Evidence |
|---|---|
| Workflow exists, fires on push AND pull_request | `.github/workflows/ci.yml`, `on: push: / pull_request:` with **no branch filter** — every branch triggers |
| Five jobs, independent (no `needs:`) | `container-image`, `frontend`, `backend-lint`, `backend-tests`, `verify-scripts` |
| Latest run green with real numbers | `gh run view 32074897581` → conclusion `success`, all 5 jobs `success`. Log: `245 passed`, `45 passed (45)` files / `148 passed (148)` tests, `All checks passed!` (ruff), 17 `== scripts/verify_*.py ==` banners, `image built from Containerfile, log clean`, `manifest byte-identical across two runs` |
| Branch protection is real | `gh api .../branches/master/protection` → `required_status_checks.contexts = ["frontend","backend-lint","backend-tests","verify-scripts"]`, `allow_force_pushes: false`, `allow_deletions: false` |
| **All jobs blocking** | **FALSE.** `container-image` is **not** a required context (the workflow's own comment admits it). It reports; it does not block. |
| **Protection is unbypassable** | **FALSE.** `enforce_admins: {"enabled": false}`. The only human on this repo is an admin. |
| **Latest run is on the audited tip** | **FALSE.** `origin/chore-human-uat` = `67edf3e`; the tip `ad05c7a` is **unpushed** and `gh api .../commits/ad05c7a/check-runs` returns HTTP 422 "No commit found". The delta is docs-only (`.zj/BACKLOG.md`, `LEARNINGS.md`, `ROADMAP.md`, `STATE.md`) — low risk, but literally: the commit this milestone closes on has never been through CI. |
| **CI protects the release branch** | **FALSE.** `git ls-tree -r origin/master` has no `.github/` at all. PR #4 (`chore-ci-pipeline` → `master`) is still **OPEN**, unmerged. |

### Clause 2 — Both lint gates zero-violation: MET

| Truth | Exists | Wired | Works | Evidence |
|---|---|---|---|---|
| Frontend flat ESLint config, gate exits 0 | ✓ | ✓ CI `frontend` job (required context) | ✓ | `npm run lint` from `frontend/` → **exit 0**; eslint v10.5.0; `--report-unused-disable-directives --max-warnings 0`; **166 files linted** (164 `.ts/.tsx` under `src/` + 2) |
| Backend ruff gate exits 0 | ✓ | ✓ CI `backend-lint` job (required context) | ✓ | `backend/.venv/bin/ruff check .` → `All checks passed!` **exit 0**; ruff 0.15.18; **175 files** in scope |

Nits, not gaps: `frontend/eslint.config.js` is the sole `.js` file and falls outside the config's
own `files: ['**/*.{ts,tsx}']` block, so the lint config itself is unlinted (and any future `.js`
would be too). `[tool.ruff.lint] select = ["E","F","I","UP"]` with `E501` ignored is a narrow
ruleset — "zero violations" means zero of *those*.

### Clause 3 — Race-safe across EVERY writer: PARTIAL

**Locks read in code — the discipline holds for every ledger-mutating primitive:**

| Writer | Lock | Precedes floor/aggregate read? |
|---|---|---|
| `post_receipt` | item-master `FOR UPDATE` + re-read under lock | ✓ `inventory.py:479-484` |
| `post_adjustment` | item-master `FOR UPDATE` | ✓ `inventory.py:647-652` |
| `post_transfer` | item-master `FOR UPDATE` | ✓ `inventory.py:273-279` |
| `post_putaway` | item-master `FOR UPDATE` | ✓ `inventory.py:895-900` |
| `post_issue` | item-master `FOR UPDATE` | ✓ `inventory.py:1060-1064` |
| MOUSSE `issue_components` | item rows `FOR UPDATE`, **sorted id** | ✓ `mousse/service.py:698-705` |
| `receive_line` | PO header `FOR UPDATE` (PO→item order documented) | ✓ `purchasing.py:206, 626` |
| GELATO `execute_ship` | shipment row `FOR UPDATE` before FSM gate, then item rows **sorted id** | ✓ `shipments.py:583, 613-619` |
| CRUMB `confirm_sales_order` | item rows `FOR UPDATE`, **sorted id** | ✓ `sales_orders.py:612-619` |
| **GELATO `execute_pick`** | **no shipment/SO lock; per-line `post_putaway` locks in REQUEST-LINE order** | **✗ `shipments.py:344-395`** |

**Ran live:** `verify_inventory_race.py` **exit 0** on a fresh DB — scenarios A–D (MOUSSE issue ×
SYERP adjust, adjust × transfer, receive × receive, receipt × receipt moving-avg `9.583333`).
It is in the CI `verify-scripts` glob, so this is CI-resident, not hand-checked.

**Probe I wrote and ran (the phase gates never race the pick path):**

- **P1 — duplicate open shipments (BACKLOG Q1):** two barrier-synchronised first-picks of one
  confirmed SO, one line each, same staging bin. **Both succeeded**; the SO ended with
  `total=2 open_picking=2 ids=[29,30]`. Reproduced on the first attempt.
- **P2 — opposite-order item locks (BACKLOG "unsorted pick locks"):** two picks whose lines order
  the same two items oppositely. **`asyncpg.exceptions.DeadlockDetectedError` in 6 of 6
  iterations** (6 aborts across 12 concurrent calls) — Postgres kills one transaction; the
  operator gets a 500.

Neither corrupts the ledger (the per-item `post_putaway` lock holds the floor), so this is a
PARTIAL, not a failure. But NFR-7's Statement enumerates only *"issue, adjust, receive, transfer,
ship"* — **`pick` is not in it** — while the milestone DoD says *"every writer"*. The FR was
written narrower than the DoD it traces, and Phase 4 verified the FR. That gap is the finding.

### Clause 4 — Every shipped UI flow has passed a documented human click-through: NOT MET

**What IS evidenced:**
- `.zj/QA.md` exists, is keyed to SRD requirement IDs, and carries **61 distinct check ids**
  (counted independently: `grep -oE "C-[A-Z0-9]+-[0-9a-z]+" | sort -u` → 61).
- Its coverage arithmetic (**31 of 47** requirements checked) and its **224 citations** are
  machine-pinned and re-proven: `verify_qa_doc.py` and `verify_qa_citations.py` both **exit 0**
  in my run, and both are in the CI `verify-scripts` glob.
- §5 names **zero real gaps**; the uncovered requirements are 9 not-built, 6 machine-only,
  and NFR-8 itself. That triage is sound (NFR-1's re-triage is correct — no audit endpoint is
  exposed and nothing in `frontend/src/` reads audit events).
- The fixture seed is idempotent, pinned by manifest + a 47-table row census in CI.

**What is NOT evidenced — stated without softening:** that **any human has run any check**.
`.zj/QA.md` §6 "Result log" contains exactly one empty table row: `| | | | | |`. Zero runs, zero
dates, zero builds, zero verdicts. Not one of the 61 checks has been ticked by a person.
The clause's verb is *"has passed"*. Nothing has passed; a checklist has been written.

D-P5-11 is explicit that this is a *"consciously accepted cost"* and that *"whether v4.0 ships on
an unrun checklist is a separate owner call at `/zj:milestone`."* This audit is that call's
input, and the answer to the clause as written is **no**.

### Clause 5 — Trustworthy without a manual `verify_*` run: PARTIAL

**What CI now carries (all re-run locally and reproduced):**

| Gate | CI job | Blocking | My local result |
|---|---|---|---|
| ruff | `backend-lint` | ✓ required | exit 0 |
| eslint + `tsc -b` + vitest + build | `frontend` | ✓ required | 0 / clean / 148 tests, 45 files / built |
| pytest vs live Postgres | `backend-tests` | ✓ required | **245 passed, 0 skipped** (fresh `postgres:17`, `biznice_test` self-provisioned) |
| **17/17 non-API `verify_*`** | `verify-scripts` | ✓ required | 17/17 exit 0 (glob-driven — new scripts auto-enrol) |
| UAT-seed idempotency | `verify-scripts` | ✓ required | (CI log: manifest + census byte-identical) |
| Container image builds | `container-image` | **✗ not required** | (CI log: `image built from Containerfile, log clean`) |

**What still depends on a human running something:**

- **The 9 `verify_*_api.py` scripts — 161 `check()` assertions — run in no CI job.** They were
  "ported to the pytest HTTP suite in 2b", but D-P2b-3 scoped that to *one* RBAC/audit test per
  new module. There are exactly **5** such tests (`test_mousse_work_order_create_rbac_and_audit`,
  `test_crumb_sales_order_create_rbac_and_audit`, `test_gelato_shipment_pick_rbac_and_audit`,
  `test_ar_invoice_create_rbac_and_audit`, `test_inventory_receipt_rbac_and_audit`). 161
  assertions did not become 5 tests; 161 assertions became manual.
- **Worst case within that: the financial-reporting HTTP surface has NO automated coverage at
  all.** `grep -rn "profit-loss\|trial-balance\|balance-sheet\|ap/aging\|reports/"
  backend/tests/` → **0 matches**. `verify_reports_api.py`'s 4 endpoints × (200/401/403) plus the
  P&L missing-bound 422 — *the v2.0 milestone audit's own gap fix* — are guarded only by a script
  nobody's CI runs. Delete the `syerp:read` dependency from a report route today and every CI job
  stays green.
- **No CI job runs the artifact it builds.** `container-image` does `docker build` and asserts the
  log, then stops. Nothing composes the stack, waits for Postgres, runs `entrypoint.sh`, or curls
  `/health/ready`. `U0`'s class (fresh-volume deploy) is pinned only by *static* parsing of
  `compose.yml` (`tests/test_compose_config.py`, 6 assertions) and of `Containerfile`
  (`tests/test_containerfile_config.py`, 3 assertions). A boot-order or entrypoint regression
  reaches a self-hoster before it reaches CI.

**Positive:** I did verify the shipped artifact is real and current. The running `compose_api_1`
image was built at `2026-08-17 21:45Z`, and a sha256 census of every `.py` under `app/` and
`scripts/` inside the container is **byte-identical** to the working tree — so, unlike the Phase-5
and v1.0-G2 experience, **no stale image hid anything from this audit**. The prod stack answered
`/health/ready` 200, served the SPA, issued a JWT, and returned seeded PLUM parts.

---

## FR verdicts (SRD status claims re-tested at `ad05c7a`)

| FR | SRD status claim | True of current code? | Evidence |
|---|---|---|---|
| **NFR-4** — CI on every push | verified | **TRUE** | Every job the Statement names (ruff, eslint, `tsc -b`, vitest, `npm run build`, pytest vs live PG) sits in a **required, blocking** job; run 32074897581 green with reproduced numbers; protection contexts confirmed via authed `gh`. Caveats (non-blocking 5th job, `enforce_admins:false`, master has no CI) are outside the Statement's wording — see GAP-4/5. |
| **NFR-5** — Runnable integration coverage | done | **TRUE as narrowed** | `pytest -q` on a fresh DB: **245 passed / 0 skipped** (up from the 232 stamped at Phase 3 — 13 net new). All 7 ported service cruxes present and green. But the Statement's phrase *"the crux behaviors currently proven only by standalone `verify_*` shall be covered"* is satisfied only under D-P2b-2/3's narrowing; the 161 API-layer assertions were never ported. See GAP-3. |
| **NFR-6** — Enforced lint gates | verified | **TRUE** | `npm run lint` exit 0 (166 files), `ruff check .` exit 0 (175 files); both wired as required CI jobs, closing the "pending for NFR-4/Phase 3" clause the row still carries. |
| **NFR-7** — Concurrency-safe inventory ledger | verified | **TRUE as written; MISLEADING vs the DoD** | Every writer the Statement enumerates is locked (table above) and `verify_inventory_race.py` exits 0 in CI. The Statement omits `pick`, which the DoD's "every writer" includes and which I broke twice on demand. See GAP-2. |
| **NFR-8** — Human-verified release readiness | verified (checklist delivered; readings pending) | **TRUE and honestly caveated** | The row's own "**NOT evidenced:** that any human has run the checklist… zero readings" is correct — I confirmed §6 empty. The rewritten Statement (D-P5-11) asks for a *documented, runnable* check, which exists. The row is the most honest artifact in `.zj/`. |
| **PLUM-01** — Part CRUD (stale-verified) | implemented, stamped `a88431c` | **RE-STAMPABLE at `ad05c7a`** | See below. |

### PLUM-01 re-verification (stale-verified flag from `zj doctor`)

The three evidence files changed exactly once since the stamp, all in `d2b9b9c`
*"refactor(backend): apply safe ruff autofixes (E/F/I/UP)"*. I read the whole diff: it is
`from typing import Sequence` → `from collections.abc`, `Optional[str]` → `str | None`,
`datetime.timezone.utc` → `UTC`, and import re-sorting. **Zero semantic change.**

Behaviour re-driven through the **real HTTP router** on a throwaway stack:

| Truth | Result |
|---|---|
| Create with explicit part number | 201, `part_number: "AUDIT-PLUM01"` |
| Create with no part number → auto-generate | `P00001` |
| **int4-overflow blocker (`7562a02`) still fixed** | planted legal `P9999999999` (201); next auto-create → **201, `P10000000000`** — no 500, no "value out of range for type integer" |
| **Digit-width boundary (`5c33ed8`) still fixed** | with `P10000000000` present, next auto = `P10000000001` (numeric ordering, not lexicographic) |
| Non-numeric P-series does not break the generator | planted `P-DUPE-01`; next auto = `P10000000002` |
| Read / update / duplicate-reject / archive | GET 200; PATCH renames; duplicate create → **409**; PATCH `active:false` → `active: false` |
| Guards green | `verify_part_numbering.py` exit 0 (also runs in CI); `pytest tests/plum/test_part_number.py tests/plum/test_parts.py` → **14 passed** |

**Verdict: not broken. Re-stamp PLUM-01 at `ad05c7a`.** The stale flag was a false positive
caused by a repo-wide autofix commit touching every Python file.

---

## Ranked gaps

### GAP-1 (BLOCKER-to-close) — DoD clause C4 is false, and only the FR was amended
- **What:** the milestone DoD sentence still reads *"every shipped UI flow **has passed** a
  documented human click-through."* `.zj/QA.md` §6 contains one empty row. Zero of 61 checks
  have been run by a person. D-P5-11 rewrote **NFR-8**'s Statement to make the reading
  non-blocking, and `.zj/ROADMAP.md:405-409` still carries the original, unamended DoD text.
- **Failure scenario:** v4.0 is tagged and the roadmap records that every shipped flow passed a
  human click-through. Six months later a UI regression is traced to a v1.0 PLUM flow, and the
  written record says a human confirmed it worked. Nobody did. The same class of trust the
  milestone was created to establish is undermined by the record of the milestone itself.
- **Fix (owner's call, one of):** (a) run the checklist — even partially; §6 explicitly permits
  a partial run — and record the rows; or (b) log a decision amending the **DoD text** in
  `.zj/ROADMAP.md` to match D-P5-11 (e.g. *"…has a documented, runnable human click-through"*),
  so the shipped record does not claim a reading that never happened. Do **not** close on the
  current wording.

### GAP-2 (MAJOR) — `execute_pick` is outside the lock discipline; both failure modes reproduced
- **Where:** `backend/app/modules/gelato/service/shipments.py:260-395`. No shipment/SO lock
  before the get-or-create (`_get_open_shipment`, line 239) and `post_putaway` called per line in
  **request order** (line 387) rather than sorted item-id order.
- **Reproduced (throwaway DB, barrier-synchronised, self-contained probe):**
  - Two concurrent first-picks of one SO → **two open `picking` shipments** (`ids=[29,30]`).
  - Two picks with two shared items in opposite order → **`DeadlockDetectedError` 6/6 iterations**.
- **Failure scenario (reachable through the normal UI):** two warehouse operators start picking
  the same sales order in the same second. Both get a 201 and a shipment id. `_get_open_shipment`
  orders by id and `.limit(1)`, so every subsequent pick, and every pick-list bin suggestion,
  binds to shipment 29 forever. Shipment 30's picked stock sits in the staging bin attached to a
  shipment that **cannot be rediscovered** — GELATO exposes no "list shipments for an SO" route
  (`router.py` has only `GET /gelato/shipments/{id}`), so unless that operator's browser still
  holds the id, the stock is stranded: it can never be packed, never shipped, its reservation
  never relieved, and the SO can never reach fully-shipped without DB surgery. The deadlock case
  is milder but uglier to the user: a red 500 on a routine pick, not a 409/422.
- **Fix:** sort `req.lines` by `item_id` before the loop (one line, kills the deadlock), and
  either lock the SO row `FOR UPDATE` at step (a) or add a unique partial index
  `(sales_order_id) WHERE status='picking'`. Pin both as `verify_gelato_ship.py` barrier
  scenarios in the shape of the existing scenario (h) — that file already runs in CI.
- **Note:** both are already logged BACKLOG p2 as accepted-risk. This audit's contribution is
  that they are no longer theoretical: they are 100%-reproducible under a barrier.

### GAP-3 (MAJOR) — the financial-reporting HTTP surface has zero automated coverage anywhere in CI
- **Where:** `backend/scripts/verify_reports_api.py` (`REPORT_PATHS = /ap/aging,
  /reports/trial-balance, /reports/profit-loss, /reports/balance-sheet`) plus the P&L
  missing-bound 422. `grep -rn "profit-loss\|trial-balance\|balance-sheet\|ap/aging\|reports/"
  backend/tests/` → **0 matches**. The CI `verify-scripts` job explicitly `continue`s on
  `*_api.py`.
- **Failure scenario:** someone removes or mistypes `Depends(require_permission("syerp:read"))`
  on `/reports/balance-sheet`, or relaxes `date_to: date = Query(alias="to")` to an optional
  param. Every one of CI's five jobs stays green. A self-hoster's balance sheet becomes readable
  without permission, or the P&L 422 boundary — **the fix for the v2.0 milestone audit's own
  gap** — silently re-opens. The v2.0 audit's remediation is currently unprotected.
- **Fix (cheapest first):** add a `verify-scripts-api` CI job that boots `uvicorn` against the
  service Postgres and runs the 9 `*_api.py` scripts (I did exactly this locally in ~3 minutes:
  `uvicorn app.main:app --port 8099` + `BNS_API_BASE_URL`; 9/9 exit 0). Then wire it into
  `master`'s required contexts. Porting 161 assertions to pytest is the nicer end state but is
  not needed to close the hole.

### GAP-4 (MAJOR) — `master` carries no v4.0 work; the audited tip was never pushed
- **Evidence:** `origin/master` = `9903f1f`; `git ls-tree -r origin/master` has **no `.github/`**,
  no `eslint.config.js`, no `verify_inventory_race.py`. PR #4 (`chore-ci-pipeline` → `master`) is
  **OPEN**, `mergedAt: null`. `origin/chore-human-uat` = `67edf3e`, one commit behind the audited
  tip `ad05c7a`; `gh api .../commits/ad05c7a/check-runs` → 422 "No commit found".
- **Failure scenario:** the DoD's closing phrase is *"so a new deploy is trustworthy."* A
  self-hoster who clones the repo gets `master` — a tree with no CI pipeline, no flat ESLint
  config, no race-safety locks, no harness repair, and the pre-`U0`/`U2` compose and Containerfile.
  Every single thing this milestone paid for is invisible on the branch a new deploy comes from.
  This is the 4th consecutive milestone with master-merge debt (D-M3-4 cleared it for v3.0; it is
  back).
- **Fix:** push `ad05c7a`, confirm CI green on it, then `/zj:ship` the v4.0 stack to `master`
  (PR #4 is stale — the CI branch is 180+ commits behind; open a fresh PR from
  `chore-human-uat`). Do not tag `v4.0` on a commit CI has never seen.

### GAP-5 (MINOR) — the artifact-build job does not block, and an admin can bypass everything
- `container-image` is not in `required_status_checks.contexts` (the workflow file says so
  itself: *"it reports but does not block"*). `enforce_admins: {"enabled": false}` — the sole
  contributor is an admin and can push past all four required checks.
- **Failure scenario:** `U2` recurs (a new dotfile, a moved `COPY`, a base-image bump), the
  `container-image` job goes red, the four required checks stay green, the merge proceeds, and
  the image is unbuildable again — the exact five-phase blind spot the job was created for.
- **Fix:** two repo-settings changes — add `container-image` to the required contexts, and set
  `enforce_admins: true`. Neither is possible from a workflow file; both are one `gh api` call.

### GAP-6 (MINOR) — nothing in CI ever runs the stack it builds
- `container-image` builds and stops. `tests/test_compose_config.py` (6 assertions) and
  `tests/test_containerfile_config.py` (3) parse text; they never boot anything.
- **Failure scenario:** a change to `backend/entrypoint.sh` (the Postgres wait, `alembic upgrade
  head`, the seed order) or to the `.env`/`.env.db` wiring passes every static assertion and
  every green job, and the first person to discover it is a self-hoster on a fresh volume — the
  literal `U0` story, one layer over.
- **Fix:** extend the `container-image` job by ~10 lines — `docker run` the built image against a
  Postgres service and `curl -f /health/ready`. That converts the boot path from asserted to
  exercised, and would have caught `U0` directly.

### GAP-7 (MINOR) — `.zj/QA.md`'s own coverage map contradicts the SRD on NFR-8
- `.zj/QA.md` §3 lists `**NFR-8** — Human-verified release readiness | planned`, while
  `.zj/SRD.md` says `Status: verified`. `verify_qa_doc.py` pins the coverage *arithmetic* but
  not the *status strings* against the SRD, so the drift passes CI.
- **Fix:** correct the row, and extend `verify_qa_doc.py` to cross-check each status cell against
  the SRD heading it names — otherwise the next status change drifts the same way.

### GAP-8 (nit) — the lint config is itself unlinted
- `frontend/eslint.config.js` is the only `.js` file and falls outside its own
  `files: ['**/*.{ts,tsx}']` block, so no rule applies to it. Cosmetic today; it means a future
  `.js` or `.mjs` added anywhere in `frontend/` is silently ungated.

---

## Seams probed that held (adversarial, no gap found)

- **Stale-image trap (v1.0 G2 / Phase-5 `U2` class):** explicitly tested rather than assumed. A
  sha256 census of every `.py` under `app/` and `scripts/` inside `compose_api_1` is
  **byte-identical** to the working tree. No stale image concealed anything from this audit.
- **CI numbers are not inflated:** every figure in the Phase-5 close reproduced independently on a
  cold `postgres:17` — pytest 245/0-skipped, 17/17 non-API, 9/9 API, vitest 148/45, ruff 0,
  eslint 0, `tsc -b` + build clean. Zero deltas.
- **`verify-scripts` is glob-driven** (`for s in scripts/verify_*.py`, with `set -e` and an
  `*_api.py` `continue`), so a newly added non-API script enrols in CI for free — which is how
  `verify_qa_doc.py`, `verify_qa_citations.py` and `verify_inventory_race.py` all became
  CI-resident without a workflow edit. Good design; it is why GAP-3's fix is cheap.
- **`backend-tests` fails loud with no database.** Running pytest with no reachable Postgres
  aborts with `_pytest.outcomes.Exit: A live PostgreSQL database is required…` and a non-zero
  status — the D-P7-4 silent-skip cannot come back disguised as a pass.
- **Race-safety proof is CI-resident, not hand-checked.** `verify_inventory_race.py` sits in the
  `verify-scripts` glob, so the Phase-4 mutation-proven barrier races re-run on every push. That
  is a genuine improvement over the Phase-4 verifier's "hand-checked ≠ pinned" learning.
- **The seeded QA fixtures are reproducible.** `verify_qa_doc.py` + `verify_qa_citations.py` exit
  0 against a database seeded from scratch; the CI seed-idempotency step diffs both the manifest
  and a whole-database 47-table row census across two runs.
- **`P9999999999` int4 overflow stays fixed** (v1.0 Phase-7 blocker `7562a02`) — re-driven live
  through the router, not read from a test name.

## What was run

- **Gates, all from cold** against a throwaway `postgres:17` on `:55432`: `alembic upgrade head`
  + seeds → `pytest -q` (**245 passed, 0 skipped**, 210 s) → 17 non-API `verify_*` (**17/17**) →
  local `uvicorn` on `:8099` → 9 `verify_*_api.py` (**9/9**). Frontend: `npm run lint` (0),
  `npx vitest run` (**148/45**), `npx tsc -b`, `npm run build` — all clean. Backend
  `ruff check .` → `All checks passed!`
- **Live CI interrogation** via authed `gh`: `run list`, `run view 32074897581 --json jobs`,
  `run view --log`, `api .../branches/master/protection`, `api .../commits/ad05c7a/check-runs`,
  `pr list --state all`.
- **Code reading:** every `with_for_update()` call site in `backend/app/` (24 sites), plus the
  full bodies of `post_putaway`, `post_issue`, `execute_pick`, `_get_open_shipment`,
  `_resolve_fulfilling_location`, `generate_part_number`.
- **New concurrency probe** (`asyncio.Barrier(2)`, two independent sessions, real
  `PickRequest`/`SalesOrderCreate` schemas — never hand-stamped rows): P1 duplicate-shipment,
  P2 opposite-order deadlock. 6 iterations.
- **PLUM-01 live CRUD + numbering drive** through the real HTTP router (7 scenarios).
- **Prod-stack smoke, read-only:** `/health/ready` 200, SPA 200, login → JWT (411 chars),
  `GET /plum/parts` returning seeded `UAT-P101`/`UAT-P102`.
- **Not run (and therefore not claimed):** a red-demo mutation proving CI stays green while a
  report route breaks. The edit was blocked by this environment's write policy, so GAP-3 rests on
  coverage analysis (`grep` → 0 matches in `backend/tests/`), not on an executed RED→GREEN.
- **Cleanup:** throwaway Postgres and local uvicorn destroyed; working tree `git status` clean;
  the owner's UAT stack untouched apart from one login audit event.
