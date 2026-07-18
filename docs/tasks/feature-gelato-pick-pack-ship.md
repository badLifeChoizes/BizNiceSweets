# Task: feature-gelato-pick-pack-ship (Phase 12b — GELATO outbound pick → pack → ship)

Plan: `.zj/phases/12b-gelato-pick-pack-ship/PLAN.md` — 15 tasks, 4 waves.

## Wave A — schema
- [ ] 1. Author `Shipment` + `ShipmentLine` ORM models (gelato/models.py)
- [ ] 2. Add `qty_picked` + `qty_shipped` accumulators to `SalesOrderLine` (crumb/models.py)
- [ ] 3. Hand-author migration 0016 (shipment tables + SO-line accumulators)
- [ ] 4. Define GELATO shipment Pydantic schemas (gelato/schemas.py)

## Wave B — backend logic
- [ ] 5. Add SYERP bin-aware `post_issue` primitive
- [ ] 6. GELATO shipment service — pick (bin-aware, net-zero to staging)
- [ ] 7. GELATO shipment service — pack (FSM picking → packed)
- [ ] 8. GELATO shipment service — ship (issue + COGS JE + reservation relief, atomic)
- [ ] 9. GELATO router: pick/pack/ship endpoints + boot

## Wave C — verify
- [ ] 10. `verify_gelato_ship.py` — service invariants (accounting crux + concurrency + negative space)
- [ ] 11. `verify_gelato_ship_api.py` — HTTP-level RBAC + audit
- [ ] 12. Full backend regression + TB nets zero

## Wave D — frontend
- [ ] 13. Frontend: shipment API hooks + Fulfillment nav link
- [ ] 14. Frontend: Fulfillment screen (pick → pack → ship) + colocated test
- [ ] 15. Frontend: Sales-order-detail ship affordance + colocated test
