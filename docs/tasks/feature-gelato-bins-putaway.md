# Task: feature-gelato-bins-putaway (Phase 12a — GELATO bins & directed putaway)

Plan: `.zj/phases/12a-gelato-bins-putaway/PLAN.md` (14 tasks). Requirement: GELATO-01 (AC1/AC2 + putaway portion of AC7/AC8).

## Checklist

- [x] 1. GELATO ORM models (`gelato_bin`) + `bin_id` mapped column on `InventoryTxn`
- [x] 2. Register GELATO models in aggregator + wire module import
- [ ] 3. Hand-author migration 0015 (create `gelato_bin`, add `bin_id`)
- [x] 4. Seed `gelato:read` / `gelato:write` permissions
- [x] 5. Define GELATO Pydantic schemas
- [ ] 6. SYERP bin-aware primitives: `post_putaway` + `get_bin_on_hand`
- [ ] 7. GELATO service package: bin CRUD + putaway orchestration
- [ ] 8. GELATO router + self-register (RBAC-gated, audit-after-commit)
- [ ] 9. `verify_gelato.py` — service invariants (roll-up + net-zero + floor + concurrency)
- [ ] 10. `verify_gelato_api.py` — HTTP-level RBAC + audit
- [ ] 11. Full backend regression (TB nets zero)
- [ ] 12. Frontend: GELATO API hooks + nav gating
- [ ] 13. Frontend: Bins screen (list/create/edit/archive)
- [ ] 14. Frontend: Putaway screen (unbinned → suggested bin → confirm)
