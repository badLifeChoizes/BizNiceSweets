# Task: bugfix-plum-v1-gaps (Phase 7 — Close v1.0 gaps)

Plan: `.zj/phases/07-close-v1-0-gaps/PLAN.md`
Branch: `bugfix-plum-v1-gaps` (off `chore-architecture-planning`, D-P7-3)

## Checklist

- [ ] 0. Branch setup + record branch-base deviation (D-P7-3)
- [ ] 1. Alias `Partner as SyerpPartner` at 4 sites + cover vendor code paths live (SC1)
- [ ] 2. Numeric-safe `generate_part_number` + digit-boundary regression test (SC2)
- [ ] 3. Invalidate `['plum','parts']` on import commit success (SC3)
- [ ] 4. Refresh root `CLAUDE.md` Technology Stack + Architecture to live stack (SC6)
- [ ] 5. Bring Podman stack up, confirm API container + `alembic 0006`, run full live-DB PLUM suite (SC4)
- [ ] 6. Consolidated human-verify — 7 PLUM flows + 4 regression checks (BLOCKING) (SC4)
- [ ] 7. Reconcile `.zj/SRD.md` + `docs/features/requirements-progress.md` to verified reality (SC5)

## Notes

- Live-DB tests MUST run inside the API container (host pytest silently skips).
- Discover container name at runtime: `API=$(podman ps --format '{{.Names}}' | grep -E 'api' | head -1)`.
