# Task: feature-mousse-work-orders (Phase 10 — MOUSSE materials-only WO core)

Requirement: **MOUSSE-01**. Plan: `.zj/phases/10-mousse-work-orders/PLAN.md` (20 tasks).
Branch `feature-mousse-work-orders` cut off the D-P10-4 chore tip `6293c96` (syerp `service/`
split present), NOT tag `zj/good-09c` — owner chose chore-first (PLAN Task-1 deviation).

Goal: a WO consumes a PLUM single-level BOM + SYERP inventory to produce a finished good;
material cost flows **Dr 1140 WIP / Cr 1130** on issue and **Dr 1130 / Cr 1140** on completion
so the WO's 1140 balance returns to zero (Decimal-exact). Closes the last v2.0 DoD clause.

## Checklist
- [x] 1. Cut build branch off chore tip + open this checklist (branch: `feature-mousse-work-orders`)
- [x] 2. MOUSSE ORM models (WorkOrder, WorkOrderComponent, WorkOrderIssue) + package stub
- [x] 3. Alembic migration 0012 (three `mousse_*` tables)
- [x] 4. Seed `mousse:read` / `mousse:write` permissions
- [x] 5. MOUSSE Pydantic schemas
- [x] 6. Service — create WO, wo_number gen, list/get, detail loader
- [x] 7. Service — FSM validator + release (BOM snapshot) + cancel + hold/resume
- [x] 8. Service — issue components (row locks, floor guard, txn + JE Dr1140/Cr1130, atomic)
- [x] 9. Service — complete WO (WIP clears to zero, FG receipt, Dr1130/Cr1140, under-issue guard)
- [x] 10. Router — 9 endpoints with RBAC + audit
- [x] 11. Register MOUSSE module (`__init__` + main.py import)
- [x] 12. `verify_mousse.py` — lifecycle + WIP-clears-to-zero + rejects + hold/resume + override
- [x] 13. Concurrency scenario (two concurrent issues via asyncio.gather)
- [x] 14. `verify_mousse_api.py` — HTTP RBAC + audit rows
- [ ] 15. Full regression suite (8 verify scripts exit 0; TB nets zero)
- [ ] 16. Frontend — WO list, hooks, route, nav wiring
- [ ] 17. Frontend — WO create dialog
- [ ] 18. Frontend — WO detail + snapshot lines + Issue action + hold/resume
- [ ] 19. Frontend — Complete action (with override-incomplete warning)
- [ ] 20. Frontend — Vitest coverage of key flows
