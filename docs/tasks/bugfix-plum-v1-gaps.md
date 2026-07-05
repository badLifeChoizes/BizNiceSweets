# Task: bugfix-plum-v1-gaps (Phase 7 — Close v1.0 gaps)

Plan: `.zj/phases/07-close-v1-0-gaps/PLAN.md`
Branch: `bugfix-plum-v1-gaps` (off `chore-architecture-planning`, D-P7-3)

## Checklist

- [x] 0. Branch setup + record branch-base deviation (D-P7-3)
- [x] 1. Alias `Partner as SyerpPartner` at 4 sites + cover vendor code paths live (SC1) — `5c33ed8` (verified: import resolves live; harness deferred D-P7-4)
- [x] 2. Numeric-safe `generate_part_number` + digit-boundary regression test (SC2) — `1b8bfa1` (verified: live-DB standalone `P100000`→`P100001` + SQL cast-safety)
- [x] 3. Invalidate `['plum','parts']` on import commit success (SC3) — `37b5f97`
- [x] 4. Refresh root `CLAUDE.md` Technology Stack + Architecture to live stack (SC6) — `5db8278`
- [x] 5. Stack up; API container `compose_api_1`; `alembic current == 0006`; suite runs but all skip (harness deferred D-P7-4) — fixes proven via live-DB standalone proofs (SC4)
- [ ] 6. Consolidated human-verify — 7 PLUM flows + 4 regression checks (BLOCKING) (SC4) — **PAUSED, awaiting user**
- [ ] 7. Reconcile `.zj/SRD.md` + `docs/features/requirements-progress.md` to verified reality (SC5)

## Notes

- Live-DB tests MUST run inside the API container (host pytest silently skips).
- Discover container name at runtime: `API=$(podman ps --format '{{.Names}}' | grep -E 'api' | head -1)`.
