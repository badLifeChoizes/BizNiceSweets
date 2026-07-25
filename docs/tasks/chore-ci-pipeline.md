# Task: chore-ci-pipeline — v4.0 Phase 3 (CI pipeline, NFR-4)

Branch: `chore-ci-pipeline` (off `chore-port-verify-cruxes` plan tip `8a27a46`).
Plan: `.zj/phases/03-ci-pipeline/PLAN.md`. Goal: every push/PR runs a blocking GitHub
Actions pipeline (ruff + eslint + `tsc -b` + vitest + `npm run build` + pytest-vs-live-
postgres + non-API `verify_*`) — red blocks merge.

## Checklist

- [x] 0. Cut `chore-ci-pipeline` branch + open this checklist
- [x] 1. Author `frontend` + `backend-lint` jobs of `.github/workflows/ci.yml` (SC1, SC7)
- [x] 2. Add `backend-tests` job — pytest vs `postgres:17` service (SC1, SC2, SC5)
- [x] 3. Add `verify-scripts` job — 14 non-API `verify_*` vs migrated `biznice` (SC1, SC5)
- [x] 4. Commit workflow + push; prove all jobs green on real Actions run (SC2)
      — run 30140504003 = **success** (4/4 green); backend-tests 232 passed / 0 skipped; 14/14 verify_*
- [ ] 5. Demonstrate red on deliberately-broken backend test, then revert (SC3)
- [ ] 6. Demonstrate red on lint violation (ruff AND eslint), then revert (SC4)
- [ ] 7. Open PR → `master` + configure required-status branch protection (SC6)
- [ ] 8. Flip NFR-4 status + `requirements-progress.md`; archive this checklist (SC1–7)
