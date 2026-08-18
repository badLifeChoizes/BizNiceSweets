# Work Log — Milestone v4.0 "Infra-debt + quality paydown"

**Closed:** 2026-08-18 · **Tag:** `v4.0` · **Author:** ne1ne
**Audit:** `.zj/MILESTONE-v4.0-AUDIT.md` (goal-backward vs the five-clause DoD; verdict recorded there)

## Scope

v4.0 shipped **no new end-user capability**. It paid down p1 infra debt that had ridden unpaid
for three milestones and hardened the shared inventory ledger. Chosen at the v3.0 close (D-M3-3)
over the FLAN port and PLUM-advanced, on the reasoning that correctness had rested entirely on
standalone `verify_*` scripts and Vitest **run by hand** since v1.0, while the class of bug that
ships when tests silently skip had already bitten once (a `SyerpPartner` 500 shipped through four
plans because the live-DB tests never ran — v1.0 audit G3 / D-P7-4).

Definition of done, five clauses (D-M4-1, traces PRD-12; **C4 amended at close, D-M4-4**): *the
full test suite runs green in a GitHub Actions CI pipeline on every push; both lint gates enforce
a zero-violation baseline; the inventory ledger is race-safe across every writer; every shipped UI
flow has a documented, runnable human check — so a new deploy is trustworthy without a manual
`verify_*` run.*

Delivered across six phases: **1** (lint gates fixed-to-clean), **2a** (pytest harness repair),
**2b** (port the `verify_*` cruxes into pytest), **3** (GitHub Actions CI), **4** (inventory
ledger race-safety), **5** (human click-through UAT → the standing QA checklist). Phase 2 split
2a/2b at plan (D-P2a-2), mirroring 9a/b/c. Build order was dependency-first: make the lint tree
clean and the tests runnable so CI had meaningful green to enforce, land the race-safety refactor
under CI protection, and run the UAT work last against the fully-hardened stack.

## Effort

**187 commits** (86 docs · 47 test · 28 chore · 12 fix · 9 feat · 4 ci · 1 refactor · 2 reverts —
the reverts are the Phase-3 red-demos, deliberate), sole author ne1ne, over **~31.0 hours across
15 inferred work sessions**, 2026-07-20 → 2026-08-18. The `feat:`/`fix:` ratio inverts against
every prior milestone — as designed for an infra-hardening milestone, most of the work is tests,
configuration and documentation rather than product code.

Two phases produced **zero product-code change** by construction (`git diff -- backend/app/` empty
at both 2a and 2b). The calendar span is three weeks longer than the working span: Phase 5 stalled
at 22/41 tasks from 2026-07-26 to 2026-08-17 waiting on an owner sitting that never came — the
single largest cost in the milestone, and now an owner preference (see LEARNINGS).

Pace: 07-21 (35 commits, Phase 1), 07-24 (39, Phase 2b), 07-25 (25, Phases 3+4), 07-26 (41, Phase
5 open), 08-17 (33, Phase 5 rescope + verify fix loop), 08-18 (retro + close).
(`/zj:timeline` renders the visual; `.zj/logs/timeline.html`.)

## Shipped work, by phase

### Phase 1 — Lint gates fixed-to-clean (NFR-6)
Both gates had been non-functional for three phases running. Frontend moved to a flat
`frontend/eslint.config.js` (`.eslintrc.cjs` deleted, `lint` script de-`--ext`'d,
`@typescript-eslint` + react-hooks + react-refresh devDeps added); backend got `ruff` installed and
wired. Every existing violation fixed to a **zero-violation baseline** rather than a
baseline-and-ratchet (D-M4-3) — an honest green from day one. Both gates red→green-proven by
planted violation. The build surfaced D-P1-1: `npm install` pulled
`eslint-plugin-react-hooks@7.1.1`, whose `recommended` preset had been silently redefined to bundle
the whole React-Compiler ruleset — 54 errors across 41 files instead of the intended 11. Pinned to
`^5`. Reviewer 0 findings. Tag `zj/good-01-lint-gates-clean`.

### Phase 2a — Pytest harness repair (NFR-5)
Fixed all four D-P7-4 root causes at the harness layer, with **zero product-code change**: a
libpq-keyword DSN probe (the original passed a SQLAlchemy URL to raw `psycopg2.connect()`, so the
probe was *always* False), a NullPool session-scoped engine (the module-level async engine was bound
to a different event loop than each test), a per-test `admin-user` identity seed (RBAC resolves
permissions from the DB user, not the token claim — D-P2a-4), and per-test isolation via a dedicated
`biznice_test` database plus `TRUNCATE … RESTART IDENTITY CASCADE` + reseed (D-P2a-1, chosen over
savepoint-rollback because the service layer commits pervasively). ~100 never-run tests went to
**219 passed / 0 skipped**, twice back-to-back. The verify fix loop made a database a **hard**
requirement — no-DB now fails loud, `skip_if_no_db` retired — and added
`tests/test_harness_selfcheck.py` to pin the zero-silent-skip invariant so this exact regression can
never return quietly. Resolved the 3-milestone-old p1 "PLUM live-DB harness never runs" debt.
Tag `zj/good-02a-pytest-harness-repair`.

### Phase 2b — Port the `verify_*` cruxes into pytest (NFR-5)
Test-only, again `git diff -- backend/app/` empty. Ported the DoD-named cruxes — inventory
moving-average, GL/AP/AR ties, MOUSSE WIP-clears-to-zero, CRUMB reservation, GELATO ship COGS — as
7 service-layer files plus 5 HTTP audit/RBAC files, each headline Decimal asserted against an
**independent oracle** rather than against the implementation. The concurrency mutation-proofs
stayed in `verify_*` by design (D-P2a-2): they need real cross-session concurrent commits, which no
rollback-isolation model can host. Suite to **232 passed / 0 skipped**. SC2 non-vacuity re-driven on
a 3/7 sample, each mutation flipping a *named* test red. Reviewer's one minor is the phase's best
lesson: the MOUSSE happy-path crux cannot catch its own advertised mutation because the arithmetic
divides evenly. Tag `zj/good-02b-port-verify-cruxes`.

### Phase 3 — CI pipeline, GitHub Actions (NFR-4)
`.github/workflows/ci.yml` — four independent blocking jobs (`frontend`: npm ci → lint → tsc →
vitest → build; `backend-lint`: ruff; `backend-tests`: pytest against a live `postgres:17` service;
`verify-scripts`: migrate + seed then the non-API `verify_*` sweep), on every push and PR, with
required-status branch protection on `master`. Red-proven on real Actions runs by deliberately
breaking a test and planting lint violations, then reverting (the two `Revert` commits in this
milestone's history). Infra-only: `git diff -- backend/app/ frontend/src/` empty. The build surfaced
D-P3-4 — conftest's DB-reachability probe checked the not-yet-created `biznice_test` instead of the
always-present maintenance `postgres` database, so on a **fresh** server (exactly the ephemeral CI
service) it aborted the whole session. The 2a/2b "232 passed" runs had only ever worked because
`biznice_test` persisted locally from earlier sessions. Reviewer **0 findings**.
Tag `zj/good-03-ci-pipeline`.

### Phase 4 — Inventory ledger race-safety (NFR-7)
The shared `SELECT … FOR UPDATE` discipline (sorted-id order, the `create_bill`/`record_payment`
template) extended across `post_receipt`/`post_adjustment`/`post_transfer`, with `receive_line`
locking the PO header and a documented PO→item lock order. `post_receipt` re-reads its row under the
lock so the moving-average recompute cannot lose an update. The three remaining bin-blind draw
primitives became bin-aware per D-P4-1/5/6 (explicit-or-unbinned; no server-side auto-allocation —
traceability-first, the ledger records what the operator actually did). New
`verify_inventory_race.py`: 4 barrier races including the SRD-named MOUSSE-issue × SYERP-adjust pair,
**all 4 mutations executed RED→GREEN**. The verify fix loop caught the reviewer's major — the
bin-awareness transform had silently dropped MOUSSE's per-location floor — plus a `post_transfer`
leg-cost refresh under lock. Tag `zj/good-04-inventory-race-safety`.

### Phase 5 — Human click-through UAT → the standing QA checklist (NFR-8)
Rescoped mid-flight (D-P5-11): **the checklist is the deliverable, the owner's reading is not.**
Twelve tasks had a `Done when` only the owner could satisfy; the phase stalled at 22/41 for three
weeks and held the whole milestone behind a ~3 h sitting. Delivered `.zj/QA.md` — 61 judgeable
residue checks re-keyed from phase success criteria onto **SRD requirement IDs** so it survives
phase closure and can express coverage (31 of 47 requirements; §5 names zero real gaps), over
fixtures reproducible on a fresh volume (275 derived literals byte-identical across four re-seeds).

**Three defects, all found by engineering before anyone clicked** — and two of them blockers that
five phases of green gates had never been able to see:
- **`U2` (blocker):** the API image **could not be built at all**. `COPY frontend/package*.json`
  never matched the dotfile `frontend/.npmrc`, so `npm ci` ran without `legacy-peer-deps=true` and
  died on the peer range introduced by Phase 1's own lint devDeps. Masked for five phases because
  everyone worked against a long-lived stale image and a dev overlay that bind-mounts over
  `frontend/dist` anyway.
- **`U0` (blocker):** on a **fresh volume** the `db` container never received `POSTGRES_PASSWORD` —
  it was interpolated from a `compose/.env` that does not exist. Invisible for the life of a volume,
  so it blocks only a first-ever deploy: precisely the self-hoster. Fixed by the dedicated `.env.db`
  split (D-P5-10), which keeps the documented deploy command unchanged — the thing `U0` broke.
- **`U1` (major):** duplicate-email user create returned HTTP 500.

The verify fix loop turned the four unpinned criteria into tests (`verify_qa_doc.py`,
`verify_qa_citations.py`, a seed-idempotency step carrying both a manifest and a 47-table row
census, and a **`container-image` CI job that builds the shipped artifact on every push**), fixed
the phase's one product-behaviour hole (`post_adjustment` accepted an **archived** bin), and gated
`seed_uat_fixtures.py` against seeding a self-hoster's live books. Final gate: pytest 245 passed /
0 skipped, 17/17 non-API + 9/9 API `verify_*`, both lint gates 0, vitest 148/45, CI 5/5.
**Not delivered, by design:** any human reading. Tag `zj/good-05-human-uat`.

## Decisions and why

- **D-M4-1** — scope = CI + lint + harness repair + race-safety + human UAT; CRISP-01 and NFR-3
  (offline) groundwork deferred *because they add end-user surface and dilute an infra-hardening
  milestone*.
- **D-M4-2** — CI platform = GitHub Actions, because the repo already lives on GitHub: free
  runners, a Postgres service container, and status directly on each commit. Chosen over a
  self-hosted Forgejo/Gitea robot.
- **D-M4-3** — lint enforcement = fix-to-clean, not baseline-and-ratchet, for an honest green from
  day one.
- **D-P2a-1/2** — dedicated test DB + truncate-reset over savepoint-rollback (the service layer
  commits pervasively, so a rollback bound to one connection cannot isolate another); concurrency
  proofs stay in `verify_*`, which is exactly what lets the isolation model stay simple.
- **D-P4-1** — bin semantics = explicit-or-unbinned, no server-side auto-allocation, on
  traceability grounds inherited from the medical-device origin.
- **D-P5-11** — the QA checklist is the deliverable, the reading is not. **Consciously accepted:**
  NFR-8 no longer evidences that a human exercised the flows.
- **D-M4-4** (this close) — the DoD's C4 clause amended to match D-P5-11, rather than holding the
  milestone open for a sitting the `QA docs: non-blocking` preference forbids blocking on.

## Close audit

The milestone audit returned **GAPS FOUND** — 1 blocker-to-close, 3 major, 4 minor — against a
milestone whose own five phases had all passed verification. Clause verdicts: **C2 MET**;
**C1/C3/C5 PARTIAL**; **C4 NOT MET**. Every gap was fixed at close (owner triage: fix all).

The two that matter most, because both are the milestone's own subject matter turned back on it:

- **GAP-2** — `execute_pick` was the one inventory-ledger writer still outside the lock discipline
  NFR-7 established. The auditor reproduced *both* failure modes under a barrier: two concurrent
  first-picks of one sales order produced **two open shipments**, and opposite-order line picks
  deadlocked **6/6 iterations**. Because GELATO exposes no list-shipments-for-an-SO route, the
  second shipment's picked stock was unreachable without DB surgery. NFR-7 was true *as written* —
  its Statement simply never listed `pick` among the writers, while the DoD said *every* writer.
- **GAP-4** — `origin/master` carried **no `.github/` at all**. A fresh clone got none of v4.0: no
  CI, no flat ESLint config, no race-safety locks, no harness repair, and the pre-`U0`/`U2` compose
  and Containerfile. Fourth consecutive milestone of master-merge debt.

Also fixed: the 9 `verify_*_api.py` scripts (161 assertions, including the *only* automated
coverage of the financial-reporting HTTP surface) ran in no CI job; the `container-image` job built
an artifact it never booted; branch protection omitted the artifact job and let admins bypass.
