# Task: feature-crumb-sales-orders (Phase 11b — CRUMB sales orders + soft-reservation)

Plan: `.zj/phases/11b-crumb-sales-orders/PLAN.md` — completes CRUMB-01 (all ACs).
Branch cut off the verified 11a tip (`a8191cf`; tag `zj/good-11a-crumb-crm-pipeline` is docs-behind at `7c573d3`, code identical).

## Backend
- [ ] 1. Add SalesOrder + SalesOrderLine ORM models
- [ ] 2. Hand-author Alembic migration 0014 for the SO tables
- [ ] 3. Define SO Pydantic schemas
- [ ] 4. Add SO_TRANSITIONS to _common.py
- [ ] 5. Add get_item_on_hand helper to SYERP inventory service
- [ ] 6. Sales-orders service — generator, direct create, read/list, draft-only edits, status FSM
- [ ] 7. Sales-orders service — accepted-quote→SO conversion
- [ ] 8. Sales-orders service — confirm (reserve, FOR UPDATE lock) + cancel (release) — THE crux
- [ ] 9. Router endpoints + audit for sales orders + conversion
- [ ] 10. verify_crumb_so.py — service-level live-Postgres verification
- [ ] 11. verify_crumb_so_api.py — HTTP RBAC + audit verification
- [ ] 12. Regression — all 15 existing verify_*.py + both 11a crumb scripts still exit 0

## Frontend
- [ ] 13. SO hooks, routes, nav item
- [ ] 14. Sales Orders list + create (Draft line editor)
- [ ] 15. Sales Order detail (ordered/reserved/shortage + FSM actions)
- [ ] 16. "Convert to SO" affordance on an Accepted quote
- [ ] 17. Frontend tests + build gate

## Adversarial review gate
- [ ] Full adversarial review of Task 8 (reserve/lock/release) before /zj:verify — 11a keeper.
