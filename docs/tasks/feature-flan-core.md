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
- [ ] 16. Implement phase and task assignment set/clear — _FLAN-01.5_
- [ ] 17. Expose the project and phase endpoints on the FLAN router — _FLAN-01.1, FLAN-01.2, FLAN-01.6, FLAN-01.7 (NFR-1, CORE-05)_
- [ ] 18. Expose the task, roster and assignment endpoints on the FLAN router — _FLAN-01.3, FLAN-01.4, FLAN-01.5, FLAN-01.7 (NFR-1, CORE-05)_

### Wave C — UI

- [x] 19. Add the FLAN project and phase query hooks — _FLAN-01.1, FLAN-01.2, FLAN-01.6_
- [x] 20. Add the FLAN task, roster and assignment query hooks — _FLAN-01.3, FLAN-01.4, FLAN-01.5_
- [x] 21. Build the FLAN nav with the project switcher — _FLAN-01.6 (D-V5P1-3)_
- [x] 22. Build the FLAN Projects list screen — _FLAN-01.1, FLAN-01.6_
- [ ] 22a. Build the project edit dialog (ADDED AT BUILD, owner decision) — _FLAN-01.1_
- [x] 23. Build the project Phases screen showing the derived dates and % — _FLAN-01.2_
- [ ] 24. Build the project Tasks screen — _FLAN-01.3, FLAN-01.5_
- [ ] 25. Build the project Team roster screen — _FLAN-01.4_
- [ ] 26. Wire the FLAN routes into App.tsx with the `/flan` redirect — _FLAN-01.6, FLAN-01.7 (CORE-07/08)_

### Wave D — verification

- [ ] 27. Write `verify_flan.py` scenario (A) — the phase-rollup crux including the empty phase — _FLAN-01.2 (the SRD's named verification)_
- [ ] 28. Add `verify_flan.py` scenarios (B)–(F) — keys, dates, roster, cascade, archive — _FLAN-01.1, FLAN-01.3, FLAN-01.4_
- [ ] 29. Mutation-prove the phase-rollup assertions turn RED — _FLAN-01.2 (NFR-5 non-vacuity discipline)_
- [ ] 30. Write `verify_flan_api.py` for HTTP RBAC and audit — _FLAN-01.7 (CORE-05, NFR-1)_
- [ ] 31. Port the rollup crux into the pytest suite — _FLAN-01.2 (NFR-5)_
- [ ] 32. Port the RBAC and audit assertions into the pytest suite — _FLAN-01.7 (NFR-5)_
- [ ] 33. Run the full regression gate — _all seven criteria (the phase's own definition of not-broken)_

### Wave E — close

- [ ] 34. Refresh `.zj/codebase/MAP.md` (D-V5P1-4) — _D-V5P1-4 (phase-close hygiene for phases 2a–7)_
- [ ] 35. Record FLAN-01 in the requirements-progress table — _project rule (`CLAUDE.md` → Feature Alignment step 3)_
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

## Deviations

_(appended as they occur; mirrored to `PLAN.md` `## Deviations`)_

- **Task 1** — the plan's Verify greps `'^- \[ \]'` for 34 items; written as `- [ ] N. title — _serves_`
  grouped under the plan's five wave headings, which matches.

## Noticed

_(unrelated defects found in passing; reported at phase end, not fixed mid-task)_
