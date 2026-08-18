# Task — v4.0 milestone close (`/zj:milestone`)

Branch: `chore-human-uat` · Opened: 2026-08-18
Phase-5 work is complete and archived (`docs/tasks/_completed/2026-08-17-chore-human-uat.md`).
This checklist covers the **milestone close** only.

Audit: `.zj/MILESTONE-v4.0-AUDIT.md` — GAPS FOUND (1 blocker-to-close, 3 major, 4 minor).
Owner triage at `/zj:milestone`: amend the C4 DoD clause, fix **all** gaps, merge to master
before tagging.

## Audit remediation

- [x] **GAP-1** (blocker-to-close) — amend DoD clause C4 in `PROJECT.md` + `ROADMAP.md` to match
      D-P5-11; record the accepted cost as D-M4-4
- [x] **GAP-2** (major) — `execute_pick` outside the lock discipline: sort lines by `item_id`
      (kills the reproduced deadlock) + lock the SO row (kills the duplicate open shipment);
      both mutation-pinned as `verify_gelato_ship.py` barrier scenarios (i) and (j). Isolation
      mutation proof on live PG: drop only the SO `FOR UPDATE` → (i) RED `shipments_for_so=[101,
      102]`, (j) green; drop only `prepared.sort(...)` → (j) RED
      `asyncpg.exceptions.DeadlockDetectedError`, (i) green; both restored → 23/23 PASS.
      Gate: 17/17 non-API `verify_*` exit 0, `pytest -q` 245 passed, `ruff check .` exit 0
- [x] **GAP-3** (major) — new glob-driven `verify-scripts-api` job boots uvicorn on :8099
      against the Postgres service and runs the 9 `verify_*_api.py`. Locally reproduced on a
      fresh `postgres:17`: **9/9 exit 0, 251 PASS assertions**. **Negative control executed** —
      the audit's own scenario (`require_permission("syerp:reed")` on `/reports/balance-sheet`)
      → `verify_reports_api.py` exit 1, `FAIL: … status=403`; router restored byte-identical.
      This closes the one claim the audit itself could not prove.
- [ ] **GAP-4** (major) — push the audited tip, get CI green, merge the v4.0 stack to `master`
      (4th consecutive milestone of master-merge debt)
- [ ] **GAP-5** (minor) — branch protection: add `container-image` (+ the new API job) to the
      required contexts, set `enforce_admins: true` — **after** the merge
- [x] **GAP-6** (minor) — `container-image` now runs the image it builds against a
      `postgres:17-alpine` service (the image `compose.yml` pins), with `.env`/`.env.db` built
      from the tracked templates. Locally: entrypoint wait → `alembic 0001→0017` → startup
      complete → `/health/ready` `{"status":"ok","db":"connected"}`. **Negative control:** omit
      `--env-file .env.db` → never ready, dies on `postgres_password Field required` — i.e. it
      reproduces U0 on demand.
- [x] **GAP-7** (minor) — two rows were drifted, not one: NFR-8 (`planned` vs SRD `verified`)
      and NFR-7 (`verified` vs SRD `implemented`, drifted by this close's own edit). Both
      corrected. `verify_qa_doc.py` gained scenario 5 cross-checking all **47** status cells
      against the SRD, comparing the first word only (the SRD elaborates in prose that QA.md
      abbreviates — MOUSSE-01/GELATO-01 mirror it faithfully and must not false-positive).
      Mutation-proven: restore NFR-8 to `planned` → exit 1 with the row and both values named;
      restore → exit 0, QA.md byte-identical. CI-resident via the `verify-scripts` glob.
- [x] **GAP-8** (nit) — second config block gates `**/*.{js,mjs,cjs}` so the config lints
      itself. Coverage demonstrated: planted `no-empty` violation caught (exit 1) against the new
      config, **exit 0 / 0 problems** against the reconstructed old one; a new `.js` file is also
      caught. `npm run lint` exit 0.

## Doctor / spec hygiene

- [x] `SRD.md` PLUM-01 re-stamped at `ad05c7a` (was stale-verified since `a88431c`)
- [ ] `SRD.md` NFR-7 status `verified` → vocabulary word + `Evidence:` line; Statement extended
      to name `pick` as a writer once GAP-2 lands
- [x] `DECISIONS.md` index regenerated — 148 → 167 entries, verified to match the body exactly

## Documentation truth (`/zj:milestone` step 1 spot check)

- [x] `README.md` — was 8 months stale (last touched 2025-12-21, predating the whole
      re-platform): four shipped suites listed "Planned", Quick Start pointed at an HTML file,
      "no build tools or dependencies required", zero mention of Podman / `.env` / `.env.db`
- [x] `docs/features/requirements-progress.md` — the D-P7-4 "these tests have never actually
      run / harness repair is BACKLOG p1" caveat was resolved by this milestone's own Phase 2a

## Records

- [ ] `CHANGELOG.md` — v4.0 section generated from commits (never hand-edit beyond generation)
- [ ] `.zj/logs/milestone-v4.0.md` — work log
- [ ] `.zj/LEARNINGS.md` — `## Milestone v4.0` roll-up distilled from the six phase retros
- [ ] `.zj/DECISIONS.md` — close decisions D-M4-4..n

## Close

- [ ] Tag `v4.0` on `master` (semver against `v3.0`), owner-approved
- [ ] Archive `.zj/phases/` → `.zj/history/v4.0/phases/`
- [ ] `ROADMAP.md` — milestone closed at top, next milestone seeded
- [ ] `PROJECT.md` — new Definition of done, owner-approved
- [ ] `STATE.md` — next action
