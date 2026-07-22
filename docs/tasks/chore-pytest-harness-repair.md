# Task: chore-pytest-harness-repair (v4.0 Phase 2a — NFR-5)

Repair the backend pytest harness so every DB-backed test runs against a live PostgreSQL
database with **zero silent skips**, fixing the four D-P7-4 root causes, and green the ~100
currently-skipped auth/plum/syerp/core tests — per-test-isolated, back-to-back-rerunnable,
pointable at both the in-container `db` host and a CI localhost Postgres.

Plan: `.zj/phases/02a-pytest-harness-repair/PLAN.md`
Branch: `chore-pytest-harness-repair` off `93de57d` (code-identical to `dd401d1` /
`zj/good-01-lint-gates-clean`; cut off the plan-carrying tip so PLAN.md travels — Task-0 deviation).

## Checklist

- [x] 0. Cut branch and open checklist
- [x] 1. Fix the DSN probe (SC1)
- [x] 2. Point the harness at a dedicated, migrated test database (SC6 + isolation foundation)
- [ ] 3. NullPool test engine + resolve the app's session to it (SC2)
- [ ] 4. Per-test truncate+reseed isolation, incl. the `admin-user` identity (SC3 + SC4)
- [ ] 5. Green the auth package
- [ ] 6. Green the core package
- [ ] 7. Green the plum package
- [ ] 8. Green the syerp DB-backed tests
- [ ] 9. Green the root tests
- [ ] 10. Prove non-vacuity (SC5)
- [ ] 11. Document + prove env-pointability (SC6)
- [ ] 12. Regression keepers: boot + verify_* + full-suite zero-skip green (SC5 + keepers)

## Deviations

- **Task 0 branch point:** plan says cut off `dd401d1`; cut off `93de57d` instead (the plan
  commit, `.zj/`-docs-only, code-identical to `dd401d1`) so PLAN.md travels onto the branch.
  Same "bare tag drops the plan" precedent logged on phases 12a/12b/13.

- **Env prerequisite:** container `compose_api_1` python (3.13) lacked pytest/httpx/pytest-asyncio
  (pytest never ran here — the whole point of NFR-5). Installed `requirements-dev.txt` into the
  container's system site-packages as root (`podman exec --user root … pip install`). Ephemeral —
  lost on image rebuild. **Durable fix (bake dev deps into a test image) → Phase 3 / NFR-4.**

## Noticed

(populated during Wave B — every xfail/skip listed with reason + follow-up owner)
- Container dev-deps install is not durable across rebuild — Phase 3 must bake a test image
  (see Deviations). Documented for SC6 / Task 11.
